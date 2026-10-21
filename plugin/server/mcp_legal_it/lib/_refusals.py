"""The refusal ledger: what the vintage policy actually blocked, as data.

`update-data.py` can rank the tables needing reconciliation by what they cost
statically (who reads them, at what declared grade), but a static ranking cannot
say what really happens in a studio: which refusals a caller actually hits,
which are negotiated away with `accetta_precisione`, and which never matter
because the caller supplies the alternative parameter every time. That is the
difference between *what could block* and *what blocked*, and it is the only
honest way to order a reconciliation backlog.

The middleware records one line per refusal and one per acceptance in a JSONL
file under the cache root (per-day, one JSON object per line, append-only):

    refuse:   {"ts": ..., "tool": ..., "tables": [...], "stati": [...],
               "dichiarata": ..., "concedibile": ...}
    accept:   {"ts": ..., "tool": ..., "accettata": ..., "dichiarata": ...}

The record is deliberately minimal: the tool, the tables that caused it, the
grade claimed and what happened. It is a counter, not a log of the studio's
work -- no case data ever reaches the file, so the ledger needs no
confidentiality regime of its own and can sit next to the cache.

Opt-in, like the cache. `LEGAL_REFUSAL_LEDGER=on` (also `1`/`yes`/`true`/
`enabled`) turns it on; the default is off, so a read-only tool that refuses
writes nothing to disk and a host opts in to telemetry it decides it wants.
Writing is best-effort exactly like the cache: an unwritable ledger must never
turn a refusal into an error, because the refusal is the answer; the ledger is
only the memory of it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import _cache, _clock

#: Switch that turns the refusal ledger on; off by default.
ENABLE_ENV = "LEGAL_REFUSAL_LEDGER"
ENABLED_VALUES = frozenset({"on", "1", "yes", "true", "enabled"})

#: File name under the cache root, rotated per day by suffix.
LEDGER_NAME = "refusals.jsonl"


def ledger_enabled() -> bool:
    """True when the host asked for refusal telemetry."""
    return os.environ.get(ENABLE_ENV, "").strip().lower() in ENABLED_VALUES


def ledger_path() -> Path:
    """Where the ledger lives: `<cache root>/refusals.jsonl`."""
    return _cache.cache_root() / LEDGER_NAME


def record(entry: dict) -> None:
    """Append one entry, best-effort, when the ledger is on.

    Any failure -- ledger off, unwritable directory, disk full -- leaves the
    call's answer untouched: the return value the caller sees is never worth
    less than it would have been without the ledger.
    """
    if not ledger_enabled():
        return
    try:
        path = ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Through `_clock`, like every calendar read in this server: the audit
        # enforces it, and a pinned `LEGAL_NOW` makes the ledger deterministic
        # in tests. The read happens after the call's precision decision was
        # taken, so it cannot change what the call was worth.
        line = json.dumps(
            {"ts": _clock.now().isoformat(timespec="seconds"), **entry},
            ensure_ascii=False,
            sort_keys=True,
        )
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _tally(path: Path, per_month: dict[str, dict] | None = None) -> dict:
    """Read the ledger once and count it.

    `per_month`, when a dict is passed, additionally receives one bucket per
    calendar month (`"2026-09"`), each shaped like the overall tally. The
    bucket key comes from each entry's own timestamp -- the same one `record`
    wrote through `_clock` -- so a ledger written under a pinned `LEGAL_NOW`
    aggregates deterministically too.
    """
    rifiuti: dict[str, int] = {}
    accettazioni: dict[str, int] = {}
    tabelle: dict[str, int] = {}
    totale = 0
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    voce = json.loads(line)
                except ValueError:
                    continue  # a truncated line is skipped, not fatal
                totale += 1
                tool = voce.get("tool") or "?"
                mese = str(voce.get("ts") or "")[:7]
                if voce.get("evento") == "accettazione":
                    _bump(accettazioni, tool)
                    if per_month is not None and mese:
                        _bump(per_month.setdefault(
                            mese, {"rifiuti": {}, "tabelle": {}, "accettazioni": {}, "totale": 0}
                        )["accettazioni"], tool)
                        per_month[mese]["totale"] += 1
                    continue
                _bump(rifiuti, tool)
                tables = voce.get("tables") or []
                for tabella in tables:
                    _bump(tabelle, tabella)
                if per_month is not None and mese:
                    bucket = per_month.setdefault(
                        mese, {"rifiuti": {}, "tabelle": {}, "accettazioni": {}, "totale": 0}
                    )
                    _bump(bucket["rifiuti"], tool)
                    for tabella in tables:
                        _bump(bucket["tabelle"], tabella)
                    bucket["totale"] += 1
    except OSError:
        return {"disponibile": False, "motivo": "verbale illeggibile"}
    return {
        "disponibile": True,
        "totale": totale,
        "rifiuti": rifiuti,
        "tabelle": tabelle,
        "accettazioni": accettazioni,
    }


def _ranked(tally: dict, limit: int) -> dict:
    """Sort the tallied counters most-requested-first, capped at `limit`."""
    out = dict(tally)
    for key in ("rifiuti", "tabelle", "accettazioni"):
        out[key] = dict(sorted(out[key].items(), key=lambda kv: -kv[1])[:limit])
    return out


#: Chart geometry: bar length, in blocks, at the window's maximum.
BAR_WIDTH = 32
#: One-row mark for a month with no events: visible, not empty.
ZERO_MARK = "·"
#: The fill block. Plain ASCII `#` would work; a full block reads as a bar.
BAR_FILL = "█"


def _bars(righe: list[dict], width: int = BAR_WIDTH) -> list[str]:
    """The series at a glance: one bar per month, scaled to the window's max.

    Bars carry no more information than the rows they mirror — the same
    totals, scaled so the worst month fills the width — so the chart can never
    contradict the table it illustrates, and a month at zero shows the zero
    mark instead of a blank line. Deterministic: a function of the data only,
    no clock, no locale.
    """
    massimo = max((riga["totale"] for riga in righe), default=0)
    out: list[str] = []
    for indice, riga in enumerate(righe):
        totale = riga["totale"]
        if massimo <= 0:
            barra = ZERO_MARK
        elif totale <= 0:
            barra = ZERO_MARK
        else:
            barra = BAR_FILL * round(totale / massimo * width)
        marker = "  <-- corrente" if indice == len(righe) - 1 else ""
        out.append("%s ▏%s %d%s" % (riga["mese"], barra, totale, marker))
    return out


def summarize(limit: int = 50) -> dict:
    """What the ledger says, if the host asked for it.

    Reads `<cache root>/refusals.jsonl` (the same file `record` writes, wherever
    `MCP_CACHE_DIR` points it), counts refusals per tool and per table, counts
    the acceptances that bought a number anyway, and aggregates the same events
    per calendar month (`per_mese`) so a host can answer "is this month worse
    than the last one?" without reading the file itself. Returns
    `{"disponibile": False, "motivo": ...}` when the ledger is off or absent,
    so a reader can tell "nothing happened" from "nobody was watching".
    """
    if not ledger_enabled():
        return {
            "disponibile": False,
            "motivo": "verbale non attivo: impostare LEGAL_REFUSAL_LEDGER=on",
        }
    path = ledger_path()
    if not path.exists():
        return {
            "disponibile": True,
            "totale": 0,
            "rifiuti": {},
            "tabelle": {},
            "accettazioni": {},
            "per_mese": {},
        }
    per_month: dict[str, dict] = {}
    tally = _tally(path, per_month)
    if not tally.get("disponibile"):
        return tally
    out = _ranked(tally, limit)
    out["per_mese"] = {
        mese: _ranked(bucket, limit)
        for mese, bucket in sorted(per_month.items(), reverse=True)
    }
    return out


def monthly(months: int = 6) -> dict:
    """The ledger rolled up by month, oldest first, ready to compare.

    The host-facing shape a monthly review needs: one row per month, the total
    and per-tool/per-table counts, each month side by side with the previous
    one (`delta`), and the `top_tool`/`top_tabella` that led each month. Months with no events are listed too, with zeroes: a silent
    month is a finding, not an absence. Reads the same file `record` writes,
    wherever `MCP_CACHE_DIR` points, so the report and the ledger never
    disagree about what happened.
    """
    months = max(1, min(int(months), 24))
    if not ledger_enabled():
        return {
            "disponibile": False,
            "motivo": "verbale non attivo: impostare LEGAL_REFUSAL_LEDGER=on",
        }
    path = ledger_path()
    per_month: dict[str, dict] = {}
    if path.exists():
        tally = _tally(path, per_month)
        if not tally.get("disponibile"):
            return tally
    else:
        per_month = {}
    # The covered window is the last `months` calendar months up to and
    # including the current one, from `_clock` like every date in the server.
    oggi = _clock.today()
    finestra: list[str] = []
    anno, mese = oggi.year, oggi.month
    for _ in range(months):
        finestra.append("%04d-%02d" % (anno, mese))
        mese -= 1
        if mese == 0:
            anno, mese = anno - 1, 12
    finestra.reverse()
    righe: list[dict] = []
    for indice, mese_key in enumerate(finestra):
        bucket = per_month.get(mese_key) or {}
        rifiuti = bucket.get("rifiuti") or {}
        tabelle = bucket.get("tabelle") or {}
        accettazioni = bucket.get("accettazioni") or {}
        totale = bucket.get("totale") or 0
        precedente = righe[-1] if righe else None
        delta = None
        if precedente is not None:
            delta = totale - precedente["totale"]
        righe.append(
            {
                "mese": mese_key,
                "totale": totale,
                "delta_mese_precedente": delta,
                "rifiuti": dict(sorted(rifiuti.items(), key=lambda kv: -kv[1])),
                "tabelle": dict(sorted(tabelle.items(), key=lambda kv: -kv[1])),
                "accettazioni": dict(sorted(accettazioni.items(), key=lambda kv: -kv[1])),
                "top_tool": next(iter(rifiuti), None),
                "top_tabella": next(iter(tabelle), None),
            }
        )
    return {
        "disponibile": True,
        "mesi": months,
        "serie": righe,
        "grafico": _bars(righe),
        "nota": (
            "conteggi per mese solare dal timestamp di ciascun evento; un mese "
            "senza eventi compare con zero, non scompare. `delta_mese_precedente` "
            "e' il confronto col mese prima; None per il primo della finestra. "
            "`grafico` e' la stessa serie in barre, una riga per mese, scala sul "
            "massimo della finestra: da mostrare cosi' com'e'."
        ),
    }
