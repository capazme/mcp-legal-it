# DPA probe — live determination of `dpa_proprio` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-maintained DPA whitelist with a deterministic HTTP probe that decides, at analysis time, whether a supplier publishes its own art. 28 processor designation.

**Architecture:** A new `src/lib/dpa_probe/` package with three separated units — a pure content judge, a network prober, a TTL cache — exposed through one MCP tool `verifica_dpa_fornitore`. The `analisi-fornitori` skill calls the tool with the domain it already discovered during identification, and falls back to its existing targeted web search only when the probe returns nothing usable. Task 6 is independent of the probe: it makes `genera_report_fornitori` reject supplier sets in which one class of supplier carries more than one qualification — the cross-block incoherence that parallel analysis cannot otherwise detect.

**Tech Stack:** Python ≥ 3.10, FastMCP, httpx (async), BeautifulSoup4 + lxml, pytest + pytest-asyncio.

**Design spec:** [`docs/specs/2026-07-31-dpa-probe-design.md`](2026-07-31-dpa-probe-design.md)

## Global Constraints

- **No new dependencies.** `pypdf` must NOT be added. PDFs are judged from URL + `content-type` only, with `evidenza: "url"`. Allowed imports: stdlib, `httpx`, `bs4`, `lxml`.
- **Python ≥ 3.10**, matching `pyproject.toml`.
- **Libs never import `src.server`** — only `src/tools/*.py` does (project convention).
- **Cache directory**: `Path(os.environ.get("MCP_CACHE_DIR", Path.home() / ".cache" / "mcp-legal-it"))`, identical to `src/lib/brocardi/client.py:39`.
- **HTTP goes through `retry_request`** from `src.lib._http` (signature: `retry_request(client, method, url, *, max_retries=2, backoff_base=1.0, **kwargs)`). It raises on 4xx and retries 5xx/transport errors.
- **Never raise out of the public API.** Like `check_vat`, errors land in the returned structure.
- **Time is injected, never read inside the units** — every function that needs "now" takes an `adesso: datetime` parameter. Tests must not sleep or monkeypatch clocks.
- **Code, identifiers, docstrings and specs in English. Skill files (`plugin/skills/**`) stay in Italian** — they are read by an Italian-language legal workflow.
- **Git Flow**: work on `feature/dpa-probe-impl` created from `develop`. Never commit directly to `develop` or `main`. Commit after every task.
- **Verdict vocabulary is fixed** (used verbatim across all tasks): `dpa_dedicato`, `clausola_in_condizioni`, `non_trovato`, `bloccato`, `dominio_irraggiungibile`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/lib/dpa_probe/__init__.py` | Public re-exports |
| `src/lib/dpa_probe/judge.py` | **Pure**: given HTML (or a PDF's URL + content-type), decide the verdict. No I/O. |
| `src/lib/dpa_probe/client.py` | Network: soft-404 fingerprint, path iteration, redirect guard, anti-bot detection. |
| `src/lib/dpa_probe/cache.py` | On-disk TTL cache. Persists determinations only. |
| `src/tools/analisi_fornitori.py` | Adds the `verifica_dpa_fornitore` MCP tool (existing file). |
| `tests/unit/test_dpa_probe.py` | Unit tests for all three units. |
| `tests/fixtures/dpa/*.html` | Trimmed real pages (see Task 1). |
| `plugin/skills/analisi-fornitori/SKILL.md` | Step 4 + parallel-mode prompt rewritten (Task 5); merge guardrail added (Task 6). |
| `plugin/skills/analisi-fornitori/references/dpa-whitelist.md` | **Deleted.** |
| `plugin/skills/analisi-fornitori/references/metodologia.md` | Record contract gains `classe_attivita` (Task 6). |
| `tests/unit/test_analisi_fornitori.py` | Class-consistency tests appended (Task 6). |

Split rationale: the judge is the part that must be exhaustively tested and it is far easier to test as a pure function; the client is the part that touches the network and needs mocking; the cache is the part with an invariant (never persist failures) that deserves its own tests. Keeping them in one file would make all three harder to test in isolation.

---

### Task 1: Content judge (pure)

> **⚠️ Superseded in part — amended 2026-07-31 after review.** The confirmation
> threshold in Step 4 below ("one strong marker plus one supporting marker,
> anywhere in the text") is **wrong and must not be re-implemented as written**.
> Review demonstrated it confirms a generic "chi siamo" page containing
> *"…non ricorre mai a un sub-processor… vedi anche l'art. 28 del nostro
> regolamento interno aziendale"* as a dedicated DPA — the exact false positive
> this module exists to prevent. The governing rule is now
> [the design spec's "Proximity and anchoring"](2026-07-31-dpa-probe-design.md#judging-rules):
> `art. 28` counts as strong only in GDPR context, and strong and supporting
> markers must co-occur (strong in heading + support in body, or both in the
> same two-sentence window). The shipped implementation in
> `src/lib/dpa_probe/judge.py` is authoritative; the Step 2 tests below are also
> superseded by the wider set in `tests/unit/test_dpa_probe.py`, which adds the
> adversarial and fixture-substance cases. Everything else in this task —
> files, names, signatures, the PDF decision, the fixtures — stands.

**Files:**
- Create: `src/lib/dpa_probe/__init__.py`
- Create: `src/lib/dpa_probe/judge.py`
- Create: `tests/fixtures/dpa/` (5 files, see Step 1)
- Test: `tests/unit/test_dpa_probe.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Giudizio` dataclass with fields `verdetto: str`, `marcatori: list[str]`, `evidenza: str` (`"contenuto"` or `"url"`).
  - `giudica_html(html: str) -> Giudizio`
  - `giudica_pdf(url: str) -> Giudizio`
  - Constants `VERDETTO_DEDICATO`, `VERDETTO_CLAUSOLA`, `VERDETTO_NON_TROVATO`.

- [ ] **Step 1: Fetch and trim the real fixtures**

Fixtures must be real pages, not hand-written HTML. Run this script once; it strips scripts/styles/svg and collapses whitespace, taking each file from hundreds of KB to a few tens.

```bash
mkdir -p tests/fixtures/dpa
cat > /tmp/grab_fixture.py <<'PY'
import sys, re, httpx
from bs4 import BeautifulSoup
url, dest = sys.argv[1], sys.argv[2]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
r = httpx.get(url, headers={"User-Agent": UA}, follow_redirects=True, timeout=30)
soup = BeautifulSoup(r.text, "lxml")
for tag in soup(["script", "style", "svg", "noscript", "iframe"]):
    tag.decompose()
html = re.sub(r"\s+", " ", str(soup))
open(dest, "w", encoding="utf-8").write(html)
print(dest, r.status_code, len(html))
PY
.venv/bin/python /tmp/grab_fixture.py https://www.zucchetti.it/it/cms/service/privacy.html      tests/fixtures/dpa/zucchetti_privacy_notice.html
.venv/bin/python /tmp/grab_fixture.py https://www.teamsystem.com/legal                          tests/fixtures/dpa/teamsystem_product_page.html
.venv/bin/python /tmp/grab_fixture.py https://legal.hubspot.com/dpa                             tests/fixtures/dpa/hubspot_dpa.html
.venv/bin/python /tmp/grab_fixture.py https://www.atlassian.com/legal/data-processing-addendum   tests/fixtures/dpa/atlassian_dpa.html
.venv/bin/python /tmp/grab_fixture.py https://www.aruba.it/termini-condizioni.aspx               tests/fixtures/dpa/aruba_terms.html
```

If a page has changed shape since 2026-07-31 and no longer matches its expected verdict, do NOT weaken the judge to accommodate it — record the discrepancy in the task notes and keep the remaining fixtures. The Zucchetti and TeamSystem negatives are the ones that must hold.

- [ ] **Step 2: Write the failing tests**

```python
"""Unit tests for the DPA probe lib.

Fixtures are trimmed copies of real pages captured on 2026-07-31.
"""

from pathlib import Path

import pytest

from src.lib.dpa_probe.judge import (
    VERDETTO_CLAUSOLA,
    VERDETTO_DEDICATO,
    VERDETTO_NON_TROVATO,
    giudica_html,
    giudica_pdf,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "dpa"


def _fx(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestJudgeNegatives:
    def test_website_privacy_notice_is_not_a_dpa(self):
        """Zucchetti's own privacy notice must never confirm — the regression
        that motivated replacing the whitelist."""
        assert giudica_html(_fx("zucchetti_privacy_notice.html")).verdetto == VERDETTO_NON_TROVATO

    def test_product_page_is_not_a_dpa(self):
        """TeamSystem /legal returned HTTP 200 while landing on a product page."""
        assert giudica_html(_fx("teamsystem_product_page.html")).verdetto == VERDETTO_NON_TROVATO

    def test_gdpr_mention_alone_does_not_confirm(self):
        html = "<html><head><title>GDPR</title></head><body>Il GDPR e il trattamento dei dati personali sono importanti.</body></html>"
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_strong_marker_without_support_does_not_confirm(self):
        html = "<html><head><title>Data Processing Addendum</title></head><body>Coming soon.</body></html>"
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO


class TestJudgePositives:
    def test_hubspot_dpa_is_dedicated(self):
        g = giudica_html(_fx("hubspot_dpa.html"))
        assert g.verdetto == VERDETTO_DEDICATO
        assert g.evidenza == "contenuto"
        assert g.marcatori

    def test_atlassian_dpa_is_dedicated(self):
        assert giudica_html(_fx("atlassian_dpa.html")).verdetto == VERDETTO_DEDICATO

    def test_article_28_plus_two_duties_confirms(self):
        html = (
            "<html><head><title>Designazione a responsabile</title></head><body>"
            "Ai sensi dell'art. 28 del Regolamento, il responsabile tratta i dati"
            " solo su istruzione documentata del titolare e non ricorre a un"
            " sub-responsabile senza autorizzazione scritta.</body></html>"
        )
        g = giudica_html(html)
        assert g.verdetto == VERDETTO_DEDICATO
        assert len(g.marcatori) >= 2


class TestJudgeClauseInsideTerms:
    def test_general_conditions_with_art28_is_a_clause(self):
        """Aruba publishes no standalone DPA: the appointment is a clause inside
        each service's general conditions."""
        html = (
            "<html><head><title>Condizioni Generali di Fornitura</title></head><body>"
            "<h1>Condizioni generali</h1>"
            "21. Nomina a responsabile del trattamento. Il Cliente designa Aruba"
            " quale responsabile del trattamento ai sensi dell'art. 28 GDPR; il"
            " responsabile agisce su istruzione documentata e il sub-responsabile"
            " assume gli stessi obblighi.</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_CLAUSOLA

    def test_real_terms_page_is_not_dedicated(self):
        assert giudica_html(_fx("aruba_terms.html")).verdetto != VERDETTO_DEDICATO


class TestJudgePdf:
    def test_pdf_named_dpa_confirms_on_url_evidence(self):
        g = giudica_pdf("https://example.com/legal/data-processing-addendum.pdf")
        assert g.verdetto == VERDETTO_DEDICATO
        assert g.evidenza == "url"

    def test_unrelated_pdf_does_not_confirm(self):
        assert giudica_pdf("https://example.com/brochure.pdf").verdetto == VERDETTO_NON_TROVATO
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.dpa_probe'`

- [ ] **Step 4: Implement the judge**

```python
"""Decide whether a fetched document is an art. 28 processor designation.

Pure: no I/O. A page that merely discusses GDPR must not confirm — that is the
defect this module exists to prevent (a whitelist entry once pointed at a
vendor's own website privacy notice, which would have suppressed a required
appointment).
"""

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

VERDETTO_DEDICATO = "dpa_dedicato"
VERDETTO_CLAUSOLA = "clausola_in_condizioni"
VERDETTO_NON_TROVATO = "non_trovato"


@dataclass
class Giudizio:
    verdetto: str
    marcatori: list[str] = field(default_factory=list)
    evidenza: str = "contenuto"


# A strong marker names the designation itself, not the topic of privacy.
_FORTI: dict[str, re.Pattern] = {
    "art_28": re.compile(
        r"\b(?:art(?:icolo|icle)?\.?\s*28)\b|"
        r"2016/679[^.]{0,80}\b(?:responsabile|processor)\b",
        re.I,
    ),
    "titolo_dpa": re.compile(
        r"data\s+process(?:ing|or)\s+(?:agreement|addendum)|"
        r"data\s+protection\s+addendum|"
        r"(?:designazione|nomina)\s+(?:a|del|di)\s+responsabile",
        re.I,
    ),
}

# Supporting markers are the art. 28(3) duties.
_SUPPORTO: dict[str, re.Pattern] = {
    "istruzione_documentata": re.compile(r"istruzione\s+documentata|documented\s+instructions", re.I),
    "sub_responsabile": re.compile(r"sub-?responsabile|sub-?processor", re.I),
    "diritti_interessato": re.compile(r"diritti\s+dell'interessato|data\s+subject\s+rights", re.I),
    "audit": re.compile(r"\baudit\b|attività\s+di\s+revisione|ispezion", re.I),
    "cancellazione_restituzione": re.compile(
        r"cancelli\s+o\s+(?:gli\s+)?restituisca|(?:delete|return)\s+(?:all\s+)?(?:the\s+)?personal\s+data", re.I
    ),
}

_TITOLO_CONDIZIONI = re.compile(
    r"condizioni\s+(?:generali|di\s+fornitura|contrattuali)|termini\s+e\s+condizioni|"
    r"terms\s+(?:and|&)\s+conditions|general\s+conditions",
    re.I,
)

_URL_DPA = re.compile(r"data[-_]process(?:ing|or)[-_](?:agreement|addendum)|[-_/]dpa[-_.]", re.I)


def _intestazione(soup: BeautifulSoup) -> str:
    parti = []
    if soup.title and soup.title.string:
        parti.append(soup.title.string)
    for tag in soup.find_all(["h1", "h2"], limit=8):
        parti.append(tag.get_text(" ", strip=True))
    return " ".join(parti)


def giudica_html(html: str) -> Giudizio:
    """Judge a fetched HTML document. Confirmation must be earned."""
    soup = BeautifulSoup(html, "lxml")
    testo = soup.get_text(" ", strip=True)
    intestazione = _intestazione(soup)

    forti = [nome for nome, rx in _FORTI.items() if rx.search(testo)]
    supporto = [nome for nome, rx in _SUPPORTO.items() if rx.search(testo)]

    if not forti or not supporto:
        return Giudizio(VERDETTO_NON_TROVATO, [])

    marcatori = forti + supporto
    intestazione_dpa = bool(_FORTI["titolo_dpa"].search(intestazione))
    intestazione_condizioni = bool(_TITOLO_CONDIZIONI.search(intestazione))

    if intestazione_condizioni and not intestazione_dpa:
        return Giudizio(VERDETTO_CLAUSOLA, marcatori)
    return Giudizio(VERDETTO_DEDICATO, marcatori)


def giudica_pdf(url: str) -> Giudizio:
    """Judge a PDF from its URL alone.

    Deliberately shallow: parsing PDFs would require a new dependency (see the
    design spec). A PDF served on a conventional path and named after a DPA is
    already strong evidence, flagged as `evidenza: "url"` so the caller knows
    what the verdict rests on.
    """
    if _URL_DPA.search(url):
        return Giudizio(VERDETTO_DEDICATO, ["url_dpa"], evidenza="url")
    return Giudizio(VERDETTO_NON_TROVATO, [], evidenza="url")
```

And the package init:

```python
from src.lib.dpa_probe.judge import (
    VERDETTO_CLAUSOLA,
    VERDETTO_DEDICATO,
    VERDETTO_NON_TROVATO,
    Giudizio,
    giudica_html,
    giudica_pdf,
)

__all__ = [
    "VERDETTO_CLAUSOLA",
    "VERDETTO_DEDICATO",
    "VERDETTO_NON_TROVATO",
    "Giudizio",
    "giudica_html",
    "giudica_pdf",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -v`
Expected: PASS, all 11 tests.

If `test_hubspot_dpa_is_dedicated` or `test_atlassian_dpa_is_dedicated` fails, inspect the fixture — do not relax `_FORTI`/`_SUPPORTO` to force a pass. If a negative test fails, the judge is too permissive and must be tightened.

- [ ] **Step 6: Commit**

```bash
git add src/lib/dpa_probe/ tests/unit/test_dpa_probe.py tests/fixtures/dpa/
git commit -m "feat(dpa-probe): content judge for art. 28 processor designations"
```

---

### Task 2: Network prober

**Files:**
- Create: `src/lib/dpa_probe/client.py`
- Modify: `src/lib/dpa_probe/__init__.py` (add re-exports)
- Test: `tests/unit/test_dpa_probe.py` (append)

**Interfaces:**
- Consumes: `Giudizio`, `giudica_html`, `giudica_pdf`, the three verdict constants from Task 1.
- Produces:
  - `EsitoSonda` dataclass: `verdetto: str`, `url_evidenza: str | None`, `marcatori: list[str]`, `evidenza: str | None`, `errore: str | None`.
  - `async def sonda_dominio(dominio: str) -> EsitoSonda`
  - `def normalizza_dominio(valore: str) -> str`
  - Constants `PERCORSI: tuple[str, ...]`, `VERDETTO_BLOCCATO`, `VERDETTO_IRRAGGIUNGIBILE`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_dpa_probe.py`:

```python
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.dpa_probe.client import (
    VERDETTO_BLOCCATO,
    VERDETTO_IRRAGGIUNGIBILE,
    EsitoSonda,
    normalizza_dominio,
    sonda_dominio,
)


def _resp(status=200, text="", content_type="text/html", url="https://x.test/legal/dpa"):
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = text
    r.headers = {"content-type": content_type}
    r.url = httpx.URL(url)
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = httpx.HTTPStatusError("err", request=MagicMock(), response=r)
    return r


def _client_with(handler):
    """Patch httpx.AsyncClient so every request is served by `handler(url)`."""
    client = MagicMock()
    async def _get(url, **kwargs):
        return handler(url)
    client.get = AsyncMock(side_effect=_get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


DPA_HTML = (
    "<html><head><title>Data Processing Agreement</title></head><body>"
    "Ai sensi dell'art. 28 il responsabile tratta i dati su istruzione documentata"
    " e non ricorre a un sub-responsabile senza autorizzazione.</body></html>"
)
ERROR_PAGE = "<html><head><title>404</title></head><body>Pagina non trovata</body></html>"


class TestNormalizzaDominio:
    def test_strips_scheme_www_and_path(self):
        assert normalizza_dominio("https://www.Example.com/legal/") == "example.com"

    def test_bare_host(self):
        assert normalizza_dominio("Example.COM") == "example.com"


class TestSondaDominio:
    @pytest.mark.asyncio
    async def test_finds_dedicated_dpa(self):
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            if url.endswith("/legal/dpa"):
                return _resp(200, DPA_HTML, url=url)
            return _resp(404, ERROR_PAGE)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_DEDICATO
        assert esito.url_evidenza.endswith("/legal/dpa")

    @pytest.mark.asyncio
    async def test_soft_404_does_not_confirm(self):
        """A 200 that is really the domain's error page must not be trusted."""
        def handler(url):
            return _resp(200, ERROR_PAGE, url=url)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_NON_TROVATO

    @pytest.mark.asyncio
    async def test_anti_bot_block_is_not_a_negative(self):
        """Meta answers 400 to non-browser clients although the page is valid.
        A false negative would generate an unnecessary appointment."""
        def handler(url):
            return _resp(400, "Error", url=url)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_BLOCCATO

    @pytest.mark.asyncio
    async def test_unreachable_domain(self):
        def handler(url):
            raise httpx.ConnectError("dns")

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("nowhere.test")
        assert esito.verdetto == VERDETTO_IRRAGGIUNGIBILE
        assert esito.errore

    @pytest.mark.asyncio
    async def test_redirect_to_other_host_is_rejected(self):
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            return _resp(200, DPA_HTML, url="https://elsewhere.test/marketing")

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_NON_TROVATO

    @pytest.mark.asyncio
    async def test_pdf_is_judged_from_url(self):
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            if url.endswith("/dpa"):
                return _resp(
                    200, "%PDF-1.4", content_type="application/pdf",
                    url="https://example.com/legal/data-processing-addendum.pdf",
                )
            return _resp(404, ERROR_PAGE)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_DEDICATO
        assert esito.evidenza == "url"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -k "Sonda or Normalizza" -v`
Expected: FAIL — `ImportError: cannot import name 'sonda_dominio'`

- [ ] **Step 3: Implement the prober**

```python
"""Probe a supplier's own domain for a published art. 28 processor designation.

Knows URL conventions, never vendor names: a list of conventions ages far more
slowly than a list of individual links.
"""

import hashlib
import re
from dataclasses import dataclass, field

import httpx

from src.lib._http import retry_request
from src.lib.dpa_probe.judge import (
    VERDETTO_DEDICATO,
    VERDETTO_NON_TROVATO,
    giudica_html,
    giudica_pdf,
)

VERDETTO_BLOCCATO = "bloccato"
VERDETTO_IRRAGGIUNGIBILE = "dominio_irraggiungibile"

PERCORSI: tuple[str, ...] = (
    "/legal/dpa",
    "/dpa",
    "/legal/data-processing-addendum",
    "/legal/data-processing",
    "/privacy/dpa",
    "/legal/terms/dataprocessing",
    "/trust/gdpr",
    "/gdpr",
)

_SONDA_404 = "/__dpa_probe_404__"
_TIMEOUT = httpx.Timeout(20.0, connect=8.0)
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36"
)
_PATH_LEGALE = re.compile(r"/(legal|privacy|dpa|gdpr|trust|termini|condizioni)", re.I)


@dataclass
class EsitoSonda:
    verdetto: str
    url_evidenza: str | None = None
    marcatori: list[str] = field(default_factory=list)
    evidenza: str | None = None
    errore: str | None = None


def normalizza_dominio(valore: str) -> str:
    """`https://www.Example.com/legal/` → `example.com`."""
    v = valore.strip().lower()
    v = re.sub(r"^[a-z]+://", "", v)
    v = v.split("/")[0].split("?")[0]
    return v[4:] if v.startswith("www.") else v


def _impronta(testo: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", testo).strip().encode("utf-8", "ignore")).hexdigest()


async def sonda_dominio(dominio: str) -> EsitoSonda:
    """Probe conventional DPA paths. Never raises."""
    host = normalizza_dominio(dominio)
    if not host:
        return EsitoSonda(VERDETTO_IRRAGGIUNGIBILE, errore="dominio vuoto")
    base = f"https://{host}"
    headers = {"User-Agent": _UA}

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as client:
        # Learn the domain's error-page fingerprint so soft-404s can be spotted.
        impronta_404: str | None = None
        try:
            r = await client.get(base + _SONDA_404)
            if r.status_code == 200:
                impronta_404 = _impronta(r.text)
        except httpx.TransportError as exc:
            return EsitoSonda(VERDETTO_IRRAGGIUNGIBILE, errore=f"{exc.__class__.__name__}")

        bloccato = False
        for percorso in PERCORSI:
            url = base + percorso
            try:
                resp = await retry_request(client, "get", url, max_retries=1)
            except httpx.HTTPStatusError as exc:
                # 401/403/400 from a non-browser client is an anti-bot block, not an absence.
                if exc.response.status_code in (400, 401, 403, 429):
                    bloccato = True
                continue
            except httpx.TransportError:
                continue

            finale = str(resp.url)
            if normalizza_dominio(finale) != host or not _PATH_LEGALE.search(finale):
                continue

            tipo = (resp.headers.get("content-type") or "").lower()
            if "application/pdf" in tipo:
                g = giudica_pdf(finale)
            else:
                if impronta_404 and _impronta(resp.text) == impronta_404:
                    continue
                g = giudica_html(resp.text)

            if g.verdetto != VERDETTO_NON_TROVATO:
                return EsitoSonda(g.verdetto, finale, g.marcatori, g.evidenza)

    if bloccato:
        return EsitoSonda(VERDETTO_BLOCCATO, errore="risposta di blocco a client non-browser")
    return EsitoSonda(VERDETTO_NON_TROVATO)
```

Extend `src/lib/dpa_probe/__init__.py`:

```python
from src.lib.dpa_probe.client import (
    PERCORSI,
    VERDETTO_BLOCCATO,
    VERDETTO_IRRAGGIUNGIBILE,
    EsitoSonda,
    normalizza_dominio,
    sonda_dominio,
)
from src.lib.dpa_probe.judge import (
    VERDETTO_CLAUSOLA,
    VERDETTO_DEDICATO,
    VERDETTO_NON_TROVATO,
    Giudizio,
    giudica_html,
    giudica_pdf,
)

__all__ = [
    "PERCORSI",
    "VERDETTO_BLOCCATO",
    "VERDETTO_CLAUSOLA",
    "VERDETTO_DEDICATO",
    "VERDETTO_IRRAGGIUNGIBILE",
    "VERDETTO_NON_TROVATO",
    "EsitoSonda",
    "Giudizio",
    "giudica_html",
    "giudica_pdf",
    "normalizza_dominio",
    "sonda_dominio",
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -v`
Expected: PASS, all tests from Tasks 1 and 2.

- [ ] **Step 5: Add the live canary tests**

These hit real vendors and are excluded from the default run by
`addopts = "-m 'not live'"`. They exist to tell us when the URL conventions
drift — a vendor redesigning its site must not break CI.

Append to `tests/unit/test_dpa_probe.py`:

```python
@pytest.mark.live
class TestSondaLive:
    """Canary on URL conventions. Excluded from the default suite.

    Run explicitly: .venv/bin/pytest tests/unit/test_dpa_probe.py -m live -v
    """

    @pytest.mark.asyncio
    async def test_hubspot_publishes_a_dpa(self):
        esito = await sonda_dominio("legal.hubspot.com")
        assert esito.verdetto in (VERDETTO_DEDICATO, VERDETTO_CLAUSOLA)

    @pytest.mark.asyncio
    async def test_atlassian_publishes_a_dpa(self):
        esito = await sonda_dominio("atlassian.com")
        assert esito.verdetto in (VERDETTO_DEDICATO, VERDETTO_CLAUSOLA)

    @pytest.mark.asyncio
    async def test_unregistered_domain_is_unreachable(self):
        esito = await sonda_dominio("dominio-che-non-esiste-mcp-legal-it.invalid")
        assert esito.verdetto == VERDETTO_IRRAGGIUNGIBILE
```

- [ ] **Step 6: Run the live tests once, by hand**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -m live -v`
Expected: PASS.

If a vendor's DPA is no longer on a conventional path, do NOT add that vendor's
specific URL to `PERCORSI` — a vendor-specific path is a whitelist entry in
disguise, which is what this work removes. Either the path is a genuine
convention used by several vendors and belongs in the list, or the vendor
resolves through the skill's search fallback. Note the finding and move on.

- [ ] **Step 7: Verify the default suite still excludes them**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -v | tail -3`
Expected: the three live tests are deselected, not run.

- [ ] **Step 8: Commit**

```bash
git add src/lib/dpa_probe/ tests/unit/test_dpa_probe.py
git commit -m "feat(dpa-probe): domain prober with soft-404 and anti-bot guards"
```

---

### Task 3: TTL cache

**Files:**
- Create: `src/lib/dpa_probe/cache.py`
- Modify: `src/lib/dpa_probe/__init__.py` (add re-exports)
- Test: `tests/unit/test_dpa_probe.py` (append)

**Interfaces:**
- Consumes: `EsitoSonda` and the verdict constants from Tasks 1–2.
- Produces:
  - `TTL_GIORNI: int = 90`
  - `VERDETTI_PERSISTIBILI: frozenset[str]`
  - `def percorso_cache() -> Path`
  - `def leggi(dominio: str, adesso: datetime) -> dict | None`
  - `def scrivi(dominio: str, esito: EsitoSonda, adesso: datetime) -> None`

The stored dict shape is `{"verdetto", "url_evidenza", "marcatori", "evidenza", "verificato_il"}` where `verificato_il` is an ISO-8601 date string.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_dpa_probe.py`:

```python
from datetime import datetime, timedelta

from src.lib.dpa_probe import cache as dpa_cache


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    return tmp_path


ADESSO = datetime(2026, 7, 31, 12, 0, 0)


class TestCache:
    def test_roundtrip(self, cache_dir):
        esito = EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa", ["art_28"], "contenuto")
        dpa_cache.scrivi("example.com", esito, ADESSO)
        letto = dpa_cache.leggi("example.com", ADESSO)
        assert letto["verdetto"] == VERDETTO_DEDICATO
        assert letto["url_evidenza"] == "https://example.com/legal/dpa"
        assert letto["verificato_il"] == "2026-07-31"

    def test_domain_is_normalised_on_write_and_read(self, cache_dir):
        dpa_cache.scrivi("https://WWW.Example.com/legal", EsitoSonda(VERDETTO_NON_TROVATO), ADESSO)
        assert dpa_cache.leggi("example.com", ADESSO) is not None

    def test_miss_returns_none(self, cache_dir):
        assert dpa_cache.leggi("unknown.test", ADESSO) is None

    def test_entry_expires_after_ttl(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_DEDICATO, "u"), ADESSO)
        dopo = ADESSO + timedelta(days=dpa_cache.TTL_GIORNI + 1)
        assert dpa_cache.leggi("example.com", dopo) is None

    def test_entry_alive_within_ttl(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_DEDICATO, "u"), ADESSO)
        dopo = ADESSO + timedelta(days=dpa_cache.TTL_GIORNI - 1)
        assert dpa_cache.leggi("example.com", dopo) is not None


class TestCacheNeverPersistsFailures:
    """Caching a transient failure would freeze it for 90 days — recreating the
    whitelist's defect through the back door."""

    def test_blocked_is_not_written(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_BLOCCATO, errore="403"), ADESSO)
        assert dpa_cache.leggi("example.com", ADESSO) is None

    def test_unreachable_is_not_written(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_IRRAGGIUNGIBILE, errore="dns"), ADESSO)
        assert dpa_cache.leggi("example.com", ADESSO) is None

    def test_failure_does_not_create_the_file(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_IRRAGGIUNGIBILE), ADESSO)
        assert not dpa_cache.percorso_cache().exists()

    def test_failure_leaves_existing_entries_untouched(self, cache_dir):
        dpa_cache.scrivi("good.test", EsitoSonda(VERDETTO_DEDICATO, "u"), ADESSO)
        prima = dpa_cache.percorso_cache().read_text()
        dpa_cache.scrivi("bad.test", EsitoSonda(VERDETTO_BLOCCATO), ADESSO)
        assert dpa_cache.percorso_cache().read_text() == prima

    def test_corrupt_cache_file_is_ignored(self, cache_dir):
        dpa_cache.percorso_cache().write_text("{not json", encoding="utf-8")
        assert dpa_cache.leggi("example.com", ADESSO) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -k "Cache" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.dpa_probe.cache'`

- [ ] **Step 3: Implement the cache**

```python
"""On-disk cache of DPA determinations, bounded by a TTL.

Only determinations are persisted. Transient failures are never written: a
timeout today must not become a truth for 90 days.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from src.lib.dpa_probe.client import EsitoSonda, normalizza_dominio
from src.lib.dpa_probe.judge import (
    VERDETTO_CLAUSOLA,
    VERDETTO_DEDICATO,
    VERDETTO_NON_TROVATO,
)

TTL_GIORNI = 90
VERDETTI_PERSISTIBILI = frozenset({VERDETTO_DEDICATO, VERDETTO_CLAUSOLA, VERDETTO_NON_TROVATO})

_NOME_FILE = "dpa_probe.json"


def percorso_cache() -> Path:
    base = Path(os.environ.get("MCP_CACHE_DIR", Path.home() / ".cache" / "mcp-legal-it"))
    return base / _NOME_FILE


def _carica() -> dict:
    percorso = percorso_cache()
    if not percorso.exists():
        return {}
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return dati if isinstance(dati, dict) else {}


def leggi(dominio: str, adesso: datetime) -> dict | None:
    """Return the cached determination, or None on miss / expiry / corruption."""
    voce = _carica().get(normalizza_dominio(dominio))
    if not isinstance(voce, dict):
        return None
    try:
        verificato = datetime.fromisoformat(voce["verificato_il"])
    except (KeyError, TypeError, ValueError):
        return None
    if (adesso - verificato).days > TTL_GIORNI:
        return None
    return voce


def scrivi(dominio: str, esito: EsitoSonda, adesso: datetime) -> None:
    """Persist a determination. No-op for transient failures."""
    if esito.verdetto not in VERDETTI_PERSISTIBILI:
        return
    percorso = percorso_cache()
    dati = _carica()
    dati[normalizza_dominio(dominio)] = {
        "verdetto": esito.verdetto,
        "url_evidenza": esito.url_evidenza,
        "marcatori": esito.marcatori,
        "evidenza": esito.evidenza,
        "verificato_il": adesso.date().isoformat(),
    }
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
```

Add to `src/lib/dpa_probe/__init__.py`:

```python
from src.lib.dpa_probe.cache import TTL_GIORNI, VERDETTI_PERSISTIBILI, leggi, percorso_cache, scrivi
```

and append `"TTL_GIORNI"`, `"VERDETTI_PERSISTIBILI"`, `"leggi"`, `"percorso_cache"`, `"scrivi"` to `__all__`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -v`
Expected: PASS, all tests from Tasks 1–3.

- [ ] **Step 5: Commit**

```bash
git add src/lib/dpa_probe/ tests/unit/test_dpa_probe.py
git commit -m "feat(dpa-probe): TTL cache that never persists transient failures"
```

---

### Task 4: MCP tool

**Files:**
- Modify: `src/tools/analisi_fornitori.py` (append the new tool)
- Modify: `CLAUDE.md` (tool count and catalogue)
- Modify: `README.md` (tool count)
- Test: `tests/unit/test_dpa_probe.py` (append)

**Interfaces:**
- Consumes: `sonda_dominio`, `EsitoSonda`, `cache.leggi`, `cache.scrivi`.
- Produces: MCP tool `verifica_dpa_fornitore(dominio: str, nome_fornitore: str = "") -> dict`, returning
  `{dominio, verdetto, url_evidenza, marcatori, evidenza, verificato_il, da_cache, errore}`.

`src/server.py` needs **no change** — it already imports the `analisi_fornitori` module at line 95, and the new tool registers via its decorator.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_dpa_probe.py`:

```python
from src.tools.analisi_fornitori import verifica_dpa_fornitore

_tool_fn = getattr(verifica_dpa_fornitore, "fn", verifica_dpa_fornitore)


class TestToolVerificaDpaFornitore:
    @pytest.mark.asyncio
    async def test_probe_result_is_returned_and_cached(self, cache_dir):
        esito = EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa", ["art_28"], "contenuto")
        with patch("src.tools.analisi_fornitori.sonda_dominio", AsyncMock(return_value=esito)):
            out = await _tool_fn(dominio="https://www.example.com/")
        assert out["verdetto"] == VERDETTO_DEDICATO
        assert out["dominio"] == "example.com"
        assert out["da_cache"] is False
        assert dpa_cache.leggi("example.com", datetime.fromisoformat(out["verificato_il"])) is not None

    @pytest.mark.asyncio
    async def test_second_call_is_served_from_cache_without_probing(self, cache_dir):
        esito = EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa", ["art_28"], "contenuto")
        with patch("src.tools.analisi_fornitori.sonda_dominio", AsyncMock(return_value=esito)):
            await _tool_fn(dominio="example.com")
        sonda = AsyncMock(return_value=EsitoSonda(VERDETTO_NON_TROVATO))
        with patch("src.tools.analisi_fornitori.sonda_dominio", sonda):
            out = await _tool_fn(dominio="example.com")
        assert out["da_cache"] is True
        assert out["verdetto"] == VERDETTO_DEDICATO
        sonda.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocked_is_reported_and_not_cached(self, cache_dir):
        esito = EsitoSonda(VERDETTO_BLOCCATO, errore="403")
        with patch("src.tools.analisi_fornitori.sonda_dominio", AsyncMock(return_value=esito)):
            out = await _tool_fn(dominio="example.com")
        assert out["verdetto"] == VERDETTO_BLOCCATO
        assert out["errore"]
        assert not dpa_cache.percorso_cache().exists()

    @pytest.mark.asyncio
    async def test_empty_domain_is_rejected_without_network(self, cache_dir):
        sonda = AsyncMock()
        with patch("src.tools.analisi_fornitori.sonda_dominio", sonda):
            out = await _tool_fn(dominio="   ")
        assert out["verdetto"] == VERDETTO_IRRAGGIUNGIBILE
        sonda.assert_not_awaited()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -k "Tool" -v`
Expected: FAIL — `ImportError: cannot import name 'verifica_dpa_fornitore'`

- [ ] **Step 3: Implement the tool**

Add these imports at the top of `src/tools/analisi_fornitori.py`, next to the existing `from src.lib.vies import ...`:

```python
from datetime import datetime, timezone

from src.lib.dpa_probe import cache as dpa_cache
from src.lib.dpa_probe.client import (
    VERDETTO_IRRAGGIUNGIBILE,
    EsitoSonda,
    normalizza_dominio,
    sonda_dominio,
)
```

Append at the end of the file:

```python
@mcp.tool(tags={"privacy", "utility"})
async def verifica_dpa_fornitore(dominio: str, nome_fornitore: str = "") -> dict:
    """Verifica se un fornitore pubblica un proprio atto di nomina a responsabile ex art. 28 GDPR, sondandone il dominio.

    Sostituisce la vecchia whitelist statica: l'esito è accertato al momento
    dell'analisi, non letto da una tabella. Usare durante l'analisi del mastrino
    fornitori, passando il dominio del sito ufficiale già individuato in fase di
    identificazione.

    Esiti: `dpa_dedicato` (documento autonomo) e `clausola_in_condizioni`
    (art. 28 dentro le condizioni generali di servizio: la copertura dipende dal
    servizio effettivamente acquistato) → `dpa_proprio: "si"`. `non_trovato`,
    `bloccato` e `dominio_irraggiungibile` NON sono un "no": vanno seguiti da
    ricerca mirata prima di concludere.

    Vigenza: art. 28 GDPR (nomina responsabile).
    Precisione: INDIZIARIO — accerta che il fornitore pubblichi un DPA, non che
    quel DPA sia richiamato nel contratto del cliente.

    Args:
        dominio: Dominio o URL del sito ufficiale del fornitore (es. "example.com")
        nome_fornitore: Denominazione, solo per leggibilità dell'output
    """
    host = normalizza_dominio(dominio)
    adesso = datetime.now(timezone.utc).replace(tzinfo=None)

    if not host:
        return {
            "dominio": "",
            "nome_fornitore": nome_fornitore.strip() or None,
            "verdetto": VERDETTO_IRRAGGIUNGIBILE,
            "url_evidenza": None,
            "marcatori": [],
            "evidenza": None,
            "verificato_il": adesso.date().isoformat(),
            "da_cache": False,
            "errore": "dominio mancante",
        }

    voce = dpa_cache.leggi(host, adesso)
    if voce is not None:
        return {
            "dominio": host,
            "nome_fornitore": nome_fornitore.strip() or None,
            "verdetto": voce["verdetto"],
            "url_evidenza": voce.get("url_evidenza"),
            "marcatori": voce.get("marcatori", []),
            "evidenza": voce.get("evidenza"),
            "verificato_il": voce["verificato_il"],
            "da_cache": True,
            "errore": None,
        }

    esito: EsitoSonda = await sonda_dominio(host)
    dpa_cache.scrivi(host, esito, adesso)
    return {
        "dominio": host,
        "nome_fornitore": nome_fornitore.strip() or None,
        "verdetto": esito.verdetto,
        "url_evidenza": esito.url_evidenza,
        "marcatori": esito.marcatori,
        "evidenza": esito.evidenza,
        "verificato_il": adesso.date().isoformat(),
        "da_cache": False,
        "errore": esito.errore,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_dpa_probe.py -v`
Expected: PASS, all tests from Tasks 1–4.

- [ ] **Step 5: Run the whole suite for regressions**

Run: `.venv/bin/pytest tests/ -m "not live"`
Expected: PASS. `test_analisi_fornitori.py` must be unaffected — the record contract did not change.

- [ ] **Step 6: Update the counts in the docs**

The project gains one tool. Recount and update rather than trusting the old number:

```bash
grep -rc "@mcp.tool" src/tools/*.py | awk -F: '{s+=$2} END {print "tool totali:", s}'
```

In `CLAUDE.md`: update the header line `> MCP server con N tool…`, the section title `## Tool disponibili (32 moduli, N tool)`, the cross-provider compatibility table row `| N tool di calcolo e ricerca |`, and add to the Privacy/GDPR tool table:

```markdown
| `verifica_dpa_fornitore(dominio, nome_fornitore?)` | Sonda il dominio del fornitore per un DPA/nomina ex art. 28 pubblicato (sostituisce la whitelist statica) |
```

Also update the line `15. Analisi fornitori (2 tool)` to `(3 tool)` and add `verifica_dpa_fornitore` to its list. In `README.md`, update every occurrence of the old count.

- [ ] **Step 7: Commit**

```bash
git add src/tools/analisi_fornitori.py tests/unit/test_dpa_probe.py CLAUDE.md README.md
git commit -m "feat(dpa-probe): verifica_dpa_fornitore MCP tool with cache-first lookup"
```

---

### Task 5: Skill rewrite and whitelist removal

**Files:**
- Modify: `plugin/skills/analisi-fornitori/SKILL.md` (step 4 at lines 77–79, parallel-mode prompt at lines 92–101)
- Delete: `plugin/skills/analisi-fornitori/references/dpa-whitelist.md`

**Interfaces:**
- Consumes: the MCP tool `verifica_dpa_fornitore` from Task 4.
- Produces: nothing consumed by later tasks. This is the final task.

Skill files are in Italian. The fallback rule and the guard note currently living at the bottom of `dpa-whitelist.md` **must survive the deletion** — that file is their only home.

- [ ] **Step 1: Verify the current text before editing**

Run: `sed -n '77,79p;92,101p' plugin/skills/analisi-fornitori/SKILL.md`
Expected: step 4 mentioning `references/dpa-whitelist.md`, and the prompt line `> WHITELIST DPA: {contenuto di references/dpa-whitelist.md}`.

- [ ] **Step 2: Replace step 4**

Replace these three lines:

```markdown
4. **DPA** (solo responsabili): consulta `references/dpa-whitelist.md`; se non in
   lista, ricerca mirata «{fornitore} data processing agreement / DPA / nomina
   responsabile»; esito `si`/`no`/`da_verificare`.
```

with:

```markdown
4. **DPA** (solo responsabili): chiama `verifica_dpa_fornitore(dominio=...)` con
   il dominio del sito ufficiale già trovato al passo 2. Mappatura dell'esito:
   - `dpa_dedicato` → `dpa_proprio: "si"`; l'URL dell'evidenza va in `fonti`.
   - `clausola_in_condizioni` → `dpa_proprio: "si"` **e annota obbligatoriamente
     in `note`** che la nomina è una clausola interna alle condizioni del
     servizio, quindi la copertura dipende dal servizio effettivamente
     acquistato (caso Aruba).
   - `non_trovato` / `bloccato` / `dominio_irraggiungibile` → NON sono un «no»:
     fai la ricerca mirata «{fornitore} data processing agreement / DPA / nomina
     responsabile». Se anche la ricerca non trova nulla: PMI locale o fornitore
     senza DPA pubblicato → `dpa_proprio: "no"` (serve la nomina del titolare,
     tool `genera_dpa`); nel dubbio → `da_verificare`.

   **Una pagina che parla di GDPR non è un DPA.** Prima di scrivere `si` il
   riferimento deve portare a un testo contrattuale che designa il fornitore
   responsabile ex art. 28 — non all'informativa privacy del sito, non a una
   pagina divulgativa sulla conformità.
```

- [ ] **Step 3: Update the parallel-mode prompt**

In the subagent prompt, replace point (4):

```markdown
> classifica secondo le regole che seguono; (4) per i responsabili valuta se il
> fornitore pubblica un proprio DPA standard; (5) taratura confidenza: `alto`
```

with:

```markdown
> classifica secondo le regole che seguono; (4) per i responsabili chiama
> verifica_dpa_fornitore col dominio del sito ufficiale e applica la mappatura
> del passo 4 della skill, ricadendo sulla ricerca mirata se l'esito è
> non_trovato/bloccato/dominio_irraggiungibile; (5) taratura confidenza: `alto`
```

and delete this line entirely:

```markdown
> WHITELIST DPA: {contenuto di references/dpa-whitelist.md}
```

- [ ] **Step 4: Delete the whitelist**

```bash
git rm plugin/skills/analisi-fornitori/references/dpa-whitelist.md
```

- [ ] **Step 5: Verify no dangling references remain**

```bash
grep -rn "dpa-whitelist" plugin/ src/ tests/ || echo "OK: nessun riferimento residuo"
```

Expected: `OK: nessun riferimento residuo`. Hits under `docs/specs/` are historical planning records and must be left alone.

- [ ] **Step 6: Verify the rules survived the deletion**

```bash
grep -c "genera_dpa" plugin/skills/analisi-fornitori/SKILL.md
grep -c "non è un DPA" plugin/skills/analisi-fornitori/SKILL.md
```

Expected: both ≥ 1. If either is 0, the fallback rule or the guard note was lost — restore it into step 4 before committing.

- [ ] **Step 7: Run the full suite one last time**

Run: `.venv/bin/pytest tests/ -m "not live"`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add plugin/skills/analisi-fornitori/SKILL.md
git commit -m "refactor(skills): replace static DPA whitelist with live probe

Step 4 now calls verifica_dpa_fornitore instead of consulting a curated
table, and the parallel-mode prompt no longer injects the whitelist. The
fallback rule (local SME without published DPA -> no) and the guard note
(a GDPR-themed page is not a DPA) moved into the step, which was the
whitelist's only home for them."
```

---

### Task 6: Class-consistency check at merge

**Files:**
- Modify: `src/tools/analisi_fornitori.py` (`_CAMPI_OBBLIGATORI` and `_valida_fornitori`)
- Modify: `plugin/skills/analisi-fornitori/references/metodologia.md` (record contract)
- Modify: `plugin/skills/analisi-fornitori/SKILL.md` (merge guardrails)
- Test: `tests/unit/test_analisi_fornitori.py` (append)

**Interfaces:**
- Consumes: nothing from Tasks 1–5. This task is independent of the DPA probe and could ship on its own.
- Produces: `classe_attivita` becomes a required field of the canonical record; `_verifica_coerenza_classi(fornitori: list[dict]) -> list[str]` returns one error string per incoherent class.

**Why this exists:** in the real Stand out run, parallel mode split 16 INPGI journalists across blocks and they came back 11 `fuori_perimetro` / 5 `titolare_autonomo` — the split tracked *which block processed them*, not the suppliers. Every one of those records passed the existing guardrails: an incoherent set can be perfectly well-formed. See the design spec's Class-consistency check section.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_analisi_fornitori.py`:

```python
class TestCoerenzaClassi:
    """A well-formed but incoherent set must not produce a report.

    Regression guard for the Stand out run: 16 journalists qualified two
    different ways depending only on which parallel block saw them.
    """

    def _rec(self, nome, qual, classe, **extra):
        base = {
            "denominazione_mastrino": nome,
            "qualificazione": qual,
            "motivazione": "test",
            "confidenza": "medio",
            "classe_attivita": classe,
        }
        if qual == "responsabile":
            base["probabilita_responsabile"] = "media"
            base["dpa_proprio"] = "no"
        base.update(extra)
        return base

    def test_missing_classe_attivita_is_rejected(self):
        r = self._rec("ACME SRL", "fuori_perimetro", "cancelleria")
        del r["classe_attivita"]
        errori = _valida_fornitori([r])
        assert any("classe_attivita" in e for e in errori)

    def test_coherent_class_passes(self):
        recs = [
            self._rec("NERI VALENTINA", "titolare_autonomo", "giornalista"),
            self._rec("GAGLIANO GIULIA", "titolare_autonomo", "giornalista"),
        ]
        assert _valida_fornitori(recs) == []

    def test_same_class_two_qualifications_is_rejected(self):
        recs = [
            self._rec("NERI VALENTINA", "fuori_perimetro", "giornalista"),
            self._rec("DIGIACOMO ERIKA", "titolare_autonomo", "giornalista"),
        ]
        errori = _valida_fornitori(recs)
        assert len(errori) == 1
        assert "giornalista" in errori[0]
        assert "fuori_perimetro" in errori[0]
        assert "titolare_autonomo" in errori[0]
        assert "NERI VALENTINA" in errori[0]
        assert "DIGIACOMO ERIKA" in errori[0]

    def test_class_label_is_normalised(self):
        """'Giornalista ' and 'giornalista' are the same class."""
        recs = [
            self._rec("A", "fuori_perimetro", "Giornalista "),
            self._rec("B", "titolare_autonomo", "  giornalista"),
        ]
        assert len(_valida_fornitori(recs)) == 1

    def test_distinct_classes_may_differ(self):
        recs = [
            self._rec("A", "fuori_perimetro", "ristorazione"),
            self._rec("B", "responsabile", "hosting/cloud"),
        ]
        assert _valida_fornitori(recs) == []

    def test_long_conflict_reports_a_count_not_a_truncation(self):
        """Never silently drop names: say how many were not listed."""
        recs = [self._rec(f"FP{i}", "fuori_perimetro", "giornalista") for i in range(9)]
        recs.append(self._rec("TA1", "titolare_autonomo", "giornalista"))
        errori = _valida_fornitori(recs)
        assert len(errori) == 1
        assert "+4 altri" in errori[0]

    def test_report_is_not_written_on_incoherence(self, tmp_path):
        recs = [
            self._rec("A", "fuori_perimetro", "giornalista"),
            self._rec("B", "titolare_autonomo", "giornalista"),
        ]
        fn = getattr(genera_report_fornitori, "fn", genera_report_fornitori)
        esito = fn(fornitori=recs, cliente="Test Srl")
        assert esito.startswith("Errore di validazione")
        assert "giornalista" in esito
```

Add `_valida_fornitori` and `genera_report_fornitori` to that file's imports from `src.tools.analisi_fornitori` if they are not already imported.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_analisi_fornitori.py -k Coerenza -v`
Expected: FAIL — the coherent-class cases pass trivially, the incoherent ones return `[]`, and `test_missing_classe_attivita_is_rejected` finds no such error.

- [ ] **Step 3: Implement the check**

In `src/tools/analisi_fornitori.py`, extend the required-fields tuple:

```python
_CAMPI_OBBLIGATORI = ("denominazione_mastrino", "qualificazione", "motivazione", "confidenza", "classe_attivita")
```

Add above `_valida_fornitori`:

```python
_MAX_NOMI_PER_QUALIFICA = 5


def _normalizza_classe(valore: str) -> str:
    return re.sub(r"\s+", " ", valore).strip().lower()


def _elenca(nomi: list[str]) -> str:
    """List names, and say how many were left out — never truncate silently."""
    if len(nomi) <= _MAX_NOMI_PER_QUALIFICA:
        return ", ".join(nomi)
    mostrati = ", ".join(nomi[:_MAX_NOMI_PER_QUALIFICA])
    return f"{mostrati} (+{len(nomi) - _MAX_NOMI_PER_QUALIFICA} altri)"


def _verifica_coerenza_classi(fornitori: list[dict]) -> list[str]:
    """Reject sets where the same kind of supplier carries different roles.

    Parallel analysis splits suppliers across blocks that cannot see each
    other, so the same profile can come back qualified two ways with no
    reconciliation. Every such record is individually well-formed, which is
    exactly why the per-record validation above cannot catch it.
    """
    classi: dict[str, dict[str, list[str]]] = {}
    for riga in fornitori:
        if not isinstance(riga, dict):
            continue
        classe = riga.get("classe_attivita")
        qualificazione = riga.get("qualificazione")
        nome = riga.get("denominazione_mastrino")
        if not isinstance(classe, str) or not classe.strip():
            continue
        if qualificazione not in QUALIFICAZIONI or not isinstance(nome, str):
            continue
        classi.setdefault(_normalizza_classe(classe), {}).setdefault(qualificazione, []).append(nome)

    errori: list[str] = []
    for classe, per_qualifica in sorted(classi.items()):
        if len(per_qualifica) < 2:
            continue
        dettaglio = "; ".join(
            f"{qual}: {_elenca(nomi)}" for qual, nomi in sorted(per_qualifica.items())
        )
        errori.append(
            f"classe '{classe}': qualificazioni incoerenti fra blocchi diversi ({dettaglio}). "
            "Allinea le qualificazioni oppure separa la classe in sottoclassi distinte."
        )
    return errori
```

At the end of `_valida_fornitori`, before its `return errori`, append the coherence pass:

```python
    errori.extend(_verifica_coerenza_classi(fornitori))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_analisi_fornitori.py -v`
Expected: PASS, including the pre-existing tests in that file. Some pre-existing tests build records without `classe_attivita` and will now fail validation — update those fixtures to include a class; do NOT weaken the required-field rule to keep them green.

- [ ] **Step 5: Update the record contract**

In `plugin/skills/analisi-fornitori/references/metodologia.md`, add the field to the §Contratto JSON block, immediately after `attivita`:

```json
  "classe_attivita": "obbligatorio — etichetta breve minuscola del TIPO di fornitore (es. giornalista, social media manager, hosting/cloud, ristorazione). Fornitori dello stesso tipo DEVONO avere la stessa qualificazione: il tool rifiuta il lotto se una classe ne porta due.",
```

- [ ] **Step 6: Add the merge guardrail to the skill**

In `plugin/skills/analisi-fornitori/SKILL.md`, in the parallel-mode guardrails list, append a third bullet after the two existing ones:

```markdown
- **coerenza di classe**: raggruppa i record per `classe_attivita` e verifica che
  ogni classe porti UNA sola qualificazione. Blocchi diversi non si vedono fra
  loro, quindi fornitori dello stesso tipo possono tornare qualificati in modo
  diverso senza che nulla lo segnali. Se una classe è incoerente, decidi la
  qualificazione corretta per l'intera classe e riallinea i record prima di
  chiamare `genera_report_fornitori` — che comunque rifiuta il lotto.
```

- [ ] **Step 7: Verify the whole suite**

Run: `.venv/bin/pytest tests/ -m "not live"`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/tools/analisi_fornitori.py tests/unit/test_analisi_fornitori.py plugin/skills/analisi-fornitori/references/metodologia.md plugin/skills/analisi-fornitori/SKILL.md
git commit -m "feat(analisi-fornitori): reject sets where one class carries two qualifications

Parallel blocks cannot see each other, so suppliers of the same kind came
back qualified two different ways with nothing to flag it: in the Stand out
run, 16 INPGI journalists split 11 fuori_perimetro / 5 titolare_autonomo
purely by which block processed them. Every record was well-formed, so the
existing guardrails passed them.

Records now declare classe_attivita and genera_report_fornitori refuses the
batch when one class carries more than one qualificazione, naming the class,
the conflicting values and the suppliers on each side."
```

**Backfill for checkpoints produced before this change** (they lack the field and will now fail validation). This is not scriptable — assigning a class is a judgement over each supplier's `attivita`, not a string transformation. Drive it from the tool's own error output: run the report, read which records are rejected, assign classes, re-run. For the Stand out checkpoint (296 records) the `attivita` text is already present, so it is one classification pass over short strings, not a re-analysis.

---

## Handoff

After Task 6, propose the merge to `develop` and wait for confirmation — never merge or push unprompted:

```bash
git checkout develop && git merge --no-ff feature/dpa-probe-impl -m "merge: feature/dpa-probe-impl into develop" && git push origin develop
```

The design spec's Known Limitations section applies unchanged after implementation: vendors publishing their DPA on a different top-level domain (verified case: Zucchetti) will miss the probe and resolve through the search path on first encounter.
