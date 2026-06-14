#!/usr/bin/env python3
"""Benchmark: AKN XML fetch vs HTML scraping for Normattiva.

Measures THREE access patterns x {HTML, AKN} x {cold, warm} to validate the
three binding success criteria from the design
(docs/specs/2026-06-11-akn-xml-fetch-design.md):

    1. No latency regression on the single-article hot path (AKN <= HTML).
    2. Clear full-text advantage (AKN whole-act vs N AJAX HTML calls).
    3. More structure / better formatting (eyeball the char counts + dumps).

Access patterns:
    (1) single-article-scattered  — one article, cold cache on every call.
    (2) multiple-articles-same-act — several articles of one act; AKN is warm
        after the first (cache hit), HTML re-fetches every time.
    (3) full-text-whole-act       — entire act in one shot.

Each pattern is run twice on each engine: COLD (cache cleared before the cell)
and WARM (cache primed by a throwaway call, then measured). For the HTML engine
"warm" is identical to "cold" — HTML has no parsed-act cache — but we still emit
the cell so the table is symmetric and the no-op is explicit.

ENGINE SELECTION
    HTML : fetch_article / fetch_normattiva_full_text with AKN_DISABLED=1 in the
           environment. The routing phase (scraper.py) is expected to honour this
           flag and skip the AKN path entirely, exercising the legacy HTML code.
    AKN  : the same functions with AKN enabled (default). Cold-vs-warm is driven
           by clear_akn_cache() from akn_fetch between runs.

HTTP request counting is observed by wrapping httpx.AsyncClient.get with a
counter, so it works regardless of which internal path executes.

This harness is written BEFORE the akn_fetch / akn_parser modules exist. All
optional imports are guarded; if the AKN modules are missing the AKN cells are
reported as skipped with a clear message, and only the HTML baseline runs.

USAGE
    cd /Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it
    .venv/bin/python benchmarks/akn_vs_html.py
    # optional overrides:
    BENCH_RUNS=5 .venv/bin/python benchmarks/akn_vs_html.py        # N runs per cell
    BENCH_PATTERNS=full .venv/bin/python benchmarks/akn_vs_html.py # subset (csv)
    BENCH_ENGINES=akn .venv/bin/python benchmarks/akn_vs_html.py   # subset (csv)

OUTPUT
    - a markdown table to stdout
    - raw JSON to benchmarks/akn_vs_html_results.json

NOTE: this hits LIVE Normattiva. It is a manual benchmark tool, NOT a unit test.
Do not run it in CI. Requires the project .venv (Python 3.12); system python3
(3.9) will not import the 3.10+ type syntax in the library.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- make the project importable when run as a script -----------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# --- core (always present) --------------------------------------------------
from src.lib.visualex.models import Norma, NormaVisitata  # noqa: E402
from src.lib.visualex import scraper  # noqa: E402

# --- AKN cache control (may not exist yet) ----------------------------------
# The cache-clear hook lives in akn_fetch. Guard the import so this file parses
# and the HTML baseline still runs even before the AKN modules are written.
_AKN_IMPORT_ERROR: str | None = None
try:
    from src.lib.visualex.akn_fetch import (  # noqa: E402
        clear_akn_cache,
        fetch_act_akn,  # imported to assert the module is wired; not called directly here
    )

    _AKN_AVAILABLE = True
except Exception as exc:  # ImportError, or partial module
    _AKN_AVAILABLE = False
    _AKN_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

    def clear_akn_cache() -> None:  # type: ignore[misc]
        """No-op shim: akn_fetch.clear_akn_cache not importable yet."""
        return None


RESULTS_PATH = _PROJECT_ROOT / "benchmarks" / "akn_vs_html_results.json"


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

@dataclass
class CorpusAct:
    """One act in the benchmark corpus.

    `articles` is the ordered list of article numbers used for the
    single-article (first element) and multiple-articles (all elements)
    patterns.
    """

    label: str
    tipo_atto: str
    data: str
    numero_atto: str
    articles: list[str]
    structure: str  # "flat" | "component" — informational, mirrors STRUCTURE.md

    def norma(self) -> Norma:
        return Norma(tipo_atto=self.tipo_atto, data=self.data, numero_atto=self.numero_atto)

    def nv(self, articolo: str) -> NormaVisitata:
        return NormaVisitata(norma=self.norma(), numero_articolo=articolo)


# Corpus from the task brief. The extra article numbers per act feed the
# "multiple articles, same act" pattern (and let AKN warm-cache pay off).
CORPUS: list[CorpusAct] = [
    CorpusAct("c.c.", "codice civile", "", "", ["2043", "2", "1218", "1453"], "component"),
    CorpusAct("c.p.", "codice penale", "", "", ["575", "1", "624", "640"], "component"),
    CorpusAct("Cost.", "costituzione", "", "", ["117", "3", "21", "32"], "flat"),
    CorpusAct("L. 241/1990", "legge", "1990-08-07", "241", ["3", "1", "7", "2-bis"], "flat"),
    CorpusAct("D.Lgs. 231/2001", "decreto legislativo", "2001-06-08", "231", ["6", "5", "7", "25"], "flat"),
    CorpusAct("D.Lgs. 152/2006", "decreto legislativo", "2006-04-03", "152", ["1", "2", "3", "29-bis"], "flat"),
]


# ---------------------------------------------------------------------------
# HTTP request counting (observable across both code paths)
# ---------------------------------------------------------------------------

class _HttpCounter:
    """Wraps httpx.AsyncClient.get to count outgoing requests during a measured
    block. Re-entrant-safe via a single module-global integer; we read it before
    and after each timed call to get the delta."""

    def __init__(self) -> None:
        import httpx

        self._httpx = httpx
        self._orig_get = httpx.AsyncClient.get
        self.count = 0
        self._installed = False

    def install(self) -> None:
        if self._installed:
            return
        counter = self

        async def _counting_get(self_client, *args, **kwargs):  # type: ignore[no-untyped-def]
            counter.count += 1
            return await counter._orig_get(self_client, *args, **kwargs)

        self._httpx.AsyncClient.get = _counting_get  # type: ignore[assignment]
        self._installed = True

    def uninstall(self) -> None:
        if not self._installed:
            return
        self._httpx.AsyncClient.get = self._orig_get  # type: ignore[assignment]
        self._installed = False

    def snapshot(self) -> int:
        return self.count


_HTTP = _HttpCounter()


# ---------------------------------------------------------------------------
# Engine env toggling
# ---------------------------------------------------------------------------

def _set_engine(engine: str) -> None:
    """Toggle the AKN routing flag the scraper is expected to honour.

    engine == "html" -> AKN_DISABLED=1 (force legacy HTML path)
    engine == "akn"  -> AKN enabled (clear the flag)
    """
    if engine == "html":
        os.environ["AKN_DISABLED"] = "1"
    else:
        os.environ.pop("AKN_DISABLED", None)


# ---------------------------------------------------------------------------
# Measurement primitives
# ---------------------------------------------------------------------------

@dataclass
class CellResult:
    pattern: str
    engine: str
    cache: str          # "cold" | "warm"
    act: str
    structure: str
    runs: int
    median_ms: float | None
    p95_ms: float | None
    min_ms: float | None
    max_ms: float | None
    http_requests: int | None   # request count of the (last) measured run
    success: bool
    char_count: int
    article_count: int | None
    error: str | None = None
    samples_ms: list[float] = field(default_factory=list)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


async def _measure(
    coro_factory,
    *,
    pattern: str,
    engine: str,
    cache: str,
    act: CorpusAct,
    runs: int,
    extract_text,
    extract_article_count,
    prime: bool,
) -> CellResult:
    """Run `coro_factory()` `runs` times, timing each, and aggregate.

    coro_factory: 0-arg callable returning a fresh awaitable for one measured op.
    extract_text: callable(result) -> str  (the text used for success/char_count)
    extract_article_count: callable(result) -> int | None
    prime: if True, run one warm-up call (not timed) before the measured runs,
           leaving the AKN parsed-act cache populated. For cold cells, prime is
           False and we clear the cache before EACH measured run.
    """
    _set_engine(engine)

    samples: list[float] = []
    last_http = None
    last_result = None
    err: str | None = None

    try:
        if prime:
            # Warm the cache once (untimed). For HTML this is a harmless extra
            # fetch; for AKN it populates the LRU so the timed runs are hits.
            await coro_factory()

        for _ in range(runs):
            if not prime and engine == "akn":
                # Cold AKN: ensure no cached parsed act leaks across runs.
                clear_akn_cache()
            _HTTP.count = 0
            before = _HTTP.snapshot()
            t0 = time.perf_counter()
            last_result = await coro_factory()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            last_http = _HTTP.snapshot() - before
            samples.append(elapsed_ms)
    except Exception as exc:  # noqa: BLE001 — benchmark must not crash on one cell
        err = f"{type(exc).__name__}: {exc}"

    text = ""
    art_count = None
    if last_result is not None and err is None:
        try:
            text = extract_text(last_result) or ""
            art_count = extract_article_count(last_result)
        except Exception as exc:  # noqa: BLE001
            err = f"extract: {type(exc).__name__}: {exc}"

    success = bool(samples) and err is None and len(text.strip()) > 0

    return CellResult(
        pattern=pattern,
        engine=engine,
        cache=cache,
        act=act.label,
        structure=act.structure,
        runs=len(samples),
        median_ms=round(statistics.median(samples), 1) if samples else None,
        p95_ms=round(_percentile(samples, 0.95), 1) if samples else None,
        min_ms=round(min(samples), 1) if samples else None,
        max_ms=round(max(samples), 1) if samples else None,
        http_requests=last_http,
        success=success,
        char_count=len(text),
        article_count=art_count,
        error=err,
        samples_ms=[round(s, 1) for s in samples],
    )


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

def _text_from_article(res: dict) -> str:
    return res.get("text", "") if isinstance(res, dict) else ""


def _text_from_fulltext(res: dict) -> str:
    return res.get("text", "") if isinstance(res, dict) else ""


def _count_one(_res: dict) -> int | None:
    return 1


def _count_fulltext(res: dict) -> int | None:
    return res.get("article_count") if isinstance(res, dict) else None


async def run_pattern_single(act: CorpusAct, engine: str, runs: int) -> list[CellResult]:
    """Pattern 1: single article, scattered. Cold cache on every call.

    Only a COLD cell is meaningful here (the whole point is no warm reuse).
    """
    articolo = act.articles[0]

    def factory():
        return scraper.fetch_article(act.nv(articolo))

    cold = await _measure(
        factory,
        pattern="single-article-scattered",
        engine=engine,
        cache="cold",
        act=act,
        runs=runs,
        extract_text=_text_from_article,
        extract_article_count=_count_one,
        prime=False,
    )
    return [cold]


async def run_pattern_multiple(act: CorpusAct, engine: str, runs: int) -> list[CellResult]:
    """Pattern 2: several articles of the SAME act.

    The measured operation fetches ALL of act.articles in sequence. AKN should
    pay for the act once then serve the rest from cache (warm cell). HTML
    re-fetches each article every time. We emit:
      - cold: cache cleared before each measured run (AKN re-downloads the act)
      - warm: act pre-fetched once, then the multi-article run is timed (AKN hits)
    """
    arts = act.articles

    async def fetch_all():
        out = []
        for a in arts:
            out.append(await scraper.fetch_article(act.nv(a)))
        return out

    def factory():
        return fetch_all()

    def _text_join(res_list) -> str:
        if not isinstance(res_list, list):
            return ""
        return "\n".join(r.get("text", "") for r in res_list if isinstance(r, dict))

    def _count_all(res_list) -> int | None:
        if not isinstance(res_list, list):
            return None
        return sum(1 for r in res_list if isinstance(r, dict) and r.get("text", "").strip())

    cold = await _measure(
        factory,
        pattern="multiple-articles-same-act",
        engine=engine,
        cache="cold",
        act=act,
        runs=runs,
        extract_text=_text_join,
        extract_article_count=_count_all,
        prime=False,
    )
    warm = await _measure(
        factory,
        pattern="multiple-articles-same-act",
        engine=engine,
        cache="warm",
        act=act,
        runs=runs,
        extract_text=_text_join,
        extract_article_count=_count_all,
        prime=True,
    )
    return [cold, warm]


async def run_pattern_fulltext(act: CorpusAct, engine: str, runs: int) -> list[CellResult]:
    """Pattern 3: full text, whole act.

    cold: cache cleared each run; warm: act primed then timed (AKN serves the
    parsed act from cache → near-instant).
    """

    def factory():
        return scraper.fetch_normattiva_full_text(act.norma())

    cold = await _measure(
        factory,
        pattern="full-text-whole-act",
        engine=engine,
        cache="cold",
        act=act,
        runs=runs,
        extract_text=_text_from_fulltext,
        extract_article_count=_count_fulltext,
        prime=False,
    )
    warm = await _measure(
        factory,
        pattern="full-text-whole-act",
        engine=engine,
        cache="warm",
        act=act,
        runs=runs,
        extract_text=_text_from_fulltext,
        extract_article_count=_count_fulltext,
        prime=True,
    )
    return [cold, warm]


_PATTERN_RUNNERS = {
    "single": run_pattern_single,
    "multiple": run_pattern_multiple,
    "full": run_pattern_fulltext,
}


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "NO"
    return str(v)


def render_markdown(results: list[CellResult]) -> str:
    lines: list[str] = []
    lines.append("# AKN vs HTML benchmark")
    lines.append("")
    if not _AKN_AVAILABLE:
        lines.append(
            f"> **AKN modules unavailable** ({_AKN_IMPORT_ERROR}). "
            "AKN cells reflect the current scraper routing (likely identical to "
            "HTML until akn_fetch is wired). Re-run after implementing "
            "`src/lib/visualex/akn_fetch.py` + `akn_parser.py`."
        )
        lines.append("")

    # Group rows by pattern for readability.
    patterns_order = ["single-article-scattered", "multiple-articles-same-act", "full-text-whole-act"]
    by_pattern: dict[str, list[CellResult]] = {}
    for r in results:
        by_pattern.setdefault(r.pattern, []).append(r)

    header = (
        "| Act | Struct | Engine | Cache | median ms | p95 ms | HTTP | OK | chars | arts | error |"
    )
    sep = "|---|---|---|---|---:|---:|---:|:--:|---:|---:|---|"

    for pat in patterns_order:
        rows = by_pattern.get(pat)
        if not rows:
            continue
        lines.append(f"## {pat}")
        lines.append("")
        lines.append(header)
        lines.append(sep)
        # stable sort: act, then engine, then cache (cold before warm)
        rows_sorted = sorted(
            rows,
            key=lambda r: (r.act, r.engine, 0 if r.cache == "cold" else 1),
        )
        for r in rows_sorted:
            lines.append(
                "| {act} | {struct} | {engine} | {cache} | {med} | {p95} | {http} | {ok} | {chars} | {arts} | {err} |".format(
                    act=r.act,
                    struct=r.structure,
                    engine=r.engine,
                    cache=r.cache,
                    med=_fmt(r.median_ms),
                    p95=_fmt(r.p95_ms),
                    http=_fmt(r.http_requests),
                    ok=_fmt(r.success),
                    chars=_fmt(r.char_count),
                    arts=_fmt(r.article_count),
                    err=(r.error or "")[:60],
                )
            )
        lines.append("")

    # Compact criteria read-out (best-effort, only when both engines present).
    lines.append("## Success criteria read-out")
    lines.append("")
    lines.append(_criteria_summary(results))
    lines.append("")
    return "\n".join(lines)


def _criteria_summary(results: list[CellResult]) -> str:
    def cell(pattern, engine, cache, act):
        for r in results:
            if r.pattern == pattern and r.engine == engine and r.cache == cache and r.act == act:
                return r
        return None

    acts = [a.label for a in CORPUS]
    out: list[str] = []

    # Criterion 1: single-article cold, AKN <= HTML
    out.append("**C1 — single-article hot path (AKN should be <= HTML, cold):**")
    for a in acts:
        h = cell("single-article-scattered", "html", "cold", a)
        k = cell("single-article-scattered", "akn", "cold", a)
        if h and k and h.median_ms and k.median_ms:
            verdict = "OK" if k.median_ms <= h.median_ms * 1.10 else "REGRESSION"
            out.append(f"- {a}: HTML {h.median_ms} ms vs AKN {k.median_ms} ms → {verdict}")
        else:
            out.append(f"- {a}: insufficient data")

    # Criterion 2: full-text, AKN cold should beat HTML cold
    out.append("")
    out.append("**C2 — full-text whole-act (AKN cold should beat HTML cold):**")
    for a in acts:
        h = cell("full-text-whole-act", "html", "cold", a)
        k = cell("full-text-whole-act", "akn", "cold", a)
        if h and k and h.median_ms and k.median_ms:
            verdict = "OK" if k.median_ms <= h.median_ms else "slower"
            out.append(
                f"- {a}: HTML {h.median_ms} ms ({_fmt(h.http_requests)} req) vs "
                f"AKN {k.median_ms} ms ({_fmt(k.http_requests)} req) → {verdict}"
            )
        else:
            out.append(f"- {a}: insufficient data")

    # Criterion 3: structure/formatting — surfaced as char counts; manual review.
    out.append("")
    out.append("**C3 — structure/formatting:** compare `chars` per article between "
               "engines and eyeball the JSON `samples`/text dumps; not auto-scored.")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

async def main() -> int:
    runs = int(os.environ.get("BENCH_RUNS", "3"))
    patterns = [p.strip() for p in os.environ.get("BENCH_PATTERNS", "single,multiple,full").split(",") if p.strip()]
    engines = [e.strip() for e in os.environ.get("BENCH_ENGINES", "html,akn").split(",") if e.strip()]
    # BENCH_ACTS: comma-separated case-insensitive label substrings to restrict
    # the corpus. Useful to keep the HTML full-text AJAX walk off the giant codici
    # (c.c./c.p. full-text via HTML = thousands of sequential live requests).
    act_filters = [a.strip().lower() for a in os.environ.get("BENCH_ACTS", "").split(",") if a.strip()]
    corpus = (
        [a for a in CORPUS if any(f in a.label.lower() for f in act_filters)]
        if act_filters
        else CORPUS
    )

    invalid_pat = [p for p in patterns if p not in _PATTERN_RUNNERS]
    if invalid_pat:
        print(f"Unknown BENCH_PATTERNS: {invalid_pat}. Valid: {list(_PATTERN_RUNNERS)}", file=sys.stderr)
        return 2

    print(
        f"Running benchmark: patterns={patterns} engines={engines} runs={runs} "
        f"acts={[a.label for a in corpus]} | AKN modules available={_AKN_AVAILABLE}",
        file=sys.stderr,
    )
    if not _AKN_AVAILABLE and "akn" in engines:
        print(
            f"  NOTE: akn_fetch not importable ({_AKN_IMPORT_ERROR}); "
            "'akn' cells will exercise whatever the scraper currently does.",
            file=sys.stderr,
        )

    _HTTP.install()
    all_results: list[CellResult] = []
    try:
        for engine in engines:
            for act in corpus:
                for pat in patterns:
                    runner = _PATTERN_RUNNERS[pat]
                    print(f"  [{engine}] {act.label} :: {pat} ...", file=sys.stderr, flush=True)
                    cells = await runner(act, engine, runs)
                    all_results.extend(cells)
    finally:
        _HTTP.uninstall()
        _set_engine("akn")  # leave env clean (AKN default)

    md = render_markdown(all_results)
    print(md)

    payload = {
        "meta": {
            "runs": runs,
            "patterns": patterns,
            "engines": engines,
            "akn_available": _AKN_AVAILABLE,
            "akn_import_error": _AKN_IMPORT_ERROR,
            "corpus": [asdict(a) for a in CORPUS],
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "cells": [asdict(r) for r in all_results],
    }
    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRaw JSON written to {RESULTS_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
