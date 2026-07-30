# Analisi Fornitori Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `analisi-fornitori` feature: 2 new MCP tools (`verifica_partita_iva_vies`, `genera_report_fornitori`) + VIES client lib + the `analisi-fornitori` plugin skill, per the approved spec `docs/specs/2026-07-30-analisi-fornitori-design.md`.

**Architecture:** LLM does the irregular work (reading messy ledgers, web research, guided legal judgement); deterministic tools do what must be identical every run (VIES lookup, standard Excel). The skill orchestrates 6 phases with a resumable JSON checkpoint; canonical supplier records are the contract between all parts.

**Tech Stack:** Python ≥3.10, FastMCP (`@mcp.tool`), httpx async, openpyxl (new dep), pytest + pytest-asyncio (`asyncio_mode=auto`).

## Global Constraints

- Branch: `feature/analisi-fornitori` (already created from `origin/develop`). Commits: Conventional Commits, English.
- **`src` at repo root is a symlink to `plugin/server/src`** — the canonical tree. Use `src/...` paths in commands; git history lands on `plugin/server/src/...`. Never create a real `src/` directory.
- Repo root (worktree): `/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it/.claude/worktrees/supplier-scan-automation-76554f`. Run all commands from here.
- Tests: `.venv/bin/python -m pytest tests/ -m "not live"` must stay green. New network tests must be mocked; live tests get `@pytest.mark.live`.
- Libs must NOT import `src.server` (repo convention). Tools import `from src.server import mcp`.
- Wire values lowercase snake_case (`responsabile`, `da_verificare`); display labels only inside the xlsx renderer.
- Tool docstrings in Italian with `Vigenza:`/`Precisione:` lines (see `src/tools/varie.py:680` for the house style).
- Do NOT touch: `docs/tools-catalog.md`, `docs/strumenti.md` (already stale, out of scope), `CHANGELOG.md` (release-time), manifest versions/descriptions (the `legal-it:release` skill recounts them).
- New dependency floor: `openpyxl>=3.1`, pure Python.

## File structure

```
pyproject.toml                          # MODIFY: +openpyxl (root = packaging for pip/Docker)
plugin/server/pyproject.toml            # MODIFY: +openpyxl (packaged server copy)
plugin/start_server.sh                  # MODIFY: +openpyxl in BOTH lists (uv --with; venv pip install)
dxt/manifest.json                       # MODIFY: +openpyxl in the uv --with args
CLAUDE.md                               # MODIFY: dep snippets, counts 216→218, module tree, tool tables
src/lib/vies/__init__.py                # CREATE: re-exports
src/lib/vies/client.py                  # CREATE: checksum + VIES REST client
src/tools/analisi_fornitori.py          # CREATE: the 2 tools
src/server.py                           # MODIFY: import module; instructions; docstring count
plugin/skills/analisi-fornitori/SKILL.md              # CREATE
plugin/skills/analisi-fornitori/references/metodologia.md      # CREATE
plugin/skills/analisi-fornitori/references/classificazione.md  # CREATE
plugin/skills/analisi-fornitori/references/dpa-whitelist.md    # CREATE
tests/unit/test_vies.py                 # CREATE: lib + VIES tool tests
tests/unit/test_analisi_fornitori.py    # CREATE: validation + xlsx tests
```

---

### Task 1: openpyxl dependency wiring + dev environment

**Files:**
- Modify: `pyproject.toml` (root), `plugin/server/pyproject.toml`, `plugin/start_server.sh`, `dxt/manifest.json`, `CLAUDE.md`
- Create: `.venv/` in the worktree (gitignored)

**Interfaces:**
- Produces: a worktree venv at `.venv/` with the package installed editable; `import openpyxl` works. All later tasks run tests with `.venv/bin/python -m pytest`.

- [ ] **Step 1: Add openpyxl to both pyproject files**

In `pyproject.toml` AND `plugin/server/pyproject.toml`, the `dependencies` list currently ends with `"python-docx>=1.0",`. Add after it:

```toml
    "openpyxl>=3.1",
```

- [ ] **Step 2: Add openpyxl to plugin/start_server.sh (two places)**

Line ~22 (uv path): change

```bash
    --with "lxml>=5.0" --with "fpdf2>=2.7" --with "python-docx>=1.0" \
```
to
```bash
    --with "lxml>=5.0" --with "fpdf2>=2.7" --with "python-docx>=1.0" --with "openpyxl>=3.1" \
```

Line ~47 (venv fallback): change

```bash
    "fastmcp>=2.0,<4" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7" "python-docx>=1.0"
```
to
```bash
    "fastmcp>=2.0,<4" "httpx>=0.27" "beautifulsoup4>=4.12" "lxml>=5.0" "fpdf2>=2.7" "python-docx>=1.0" "openpyxl>=3.1"
```

- [ ] **Step 3: Add openpyxl to dxt/manifest.json**

In the `args` array (lines ~26-31), after `"--with", "python-docx>=1.0",` add:

```json
        "--with", "openpyxl>=3.1",
```

- [ ] **Step 4: Update the two dep snippets in CLAUDE.md**

At CLAUDE.md lines ~506 and ~536 (`grep -n "python-docx" CLAUDE.md`), both JSON examples show:
```
        "--with", "fpdf2>=2.7", "--with", "python-docx>=1.0",
```
Change both to:
```
        "--with", "fpdf2>=2.7", "--with", "python-docx>=1.0", "--with", "openpyxl>=3.1",
```

- [ ] **Step 5: Create the worktree venv and install**

```bash
python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"
.venv/bin/python -c "import openpyxl; print(openpyxl.__version__)"
```
Expected: a version ≥3.1 printed.

- [ ] **Step 6: Baseline — full suite green before any code**

```bash
.venv/bin/python -m pytest tests/ -m "not live" -q | tail -3
```
Expected: all pass (this is the pre-existing suite; record the pass count for later comparison).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml plugin/server/pyproject.toml plugin/start_server.sh dxt/manifest.json CLAUDE.md
git commit -m "chore: add openpyxl dependency for supplier report generation"
```

---

### Task 2: VIES client lib (`src/lib/vies/`)

**Files:**
- Create: `src/lib/vies/__init__.py`, `src/lib/vies/client.py`
- Test: `tests/unit/test_vies.py`

**Interfaces:**
- Consumes: `src.lib._http.retry_request(client, method, url, *, max_retries, backoff_base, **kwargs) -> httpx.Response` (existing).
- Produces (used by Task 3):
  - `checksum_partita_iva(piva: str) -> bool` — pure, no I/O.
  - `async check_vat(vat_number: str, country_code: str = "IT") -> dict` with keys `disponibile: bool`, `valido: bool | None`, `denominazione: str | None`, `indirizzo: str | None`, `errore: str | None`. Never raises.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_vies.py`:

```python
"""Unit tests for the VIES client lib and the verifica_partita_iva_vies tool.

Mocked httpx responses — no real network calls except the @pytest.mark.live test.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.vies.client import VIES_ENDPOINT, check_vat, checksum_partita_iva


def _mock_async_client(json_payload=None, exc=None, status=200):
    """Build a patched httpx.AsyncClient whose post() returns the payload or raises."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.json.return_value = json_payload or {}
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=resp
        )
    client = MagicMock()
    if exc is not None:
        client.post = AsyncMock(side_effect=exc)
    else:
        client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestChecksum:
    def test_valid_piva(self):
        assert checksum_partita_iva("12345670017") is True

    def test_invalid_check_digit(self):
        assert checksum_partita_iva("12345670018") is False

    def test_non_numeric(self):
        assert checksum_partita_iva("1234567001X") is False

    def test_wrong_length(self):
        assert checksum_partita_iva("1234567001") is False

    def test_strips_spaces(self):
        assert checksum_partita_iva(" 12345670017 ") is True


class TestCheckVat:
    async def test_valid_with_name(self):
        payload = {"valid": True, "name": "ACME SRL", "address": "VIA ROMA 1 MILANO"}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out == {
            "disponibile": True,
            "valido": True,
            "denominazione": "ACME SRL",
            "indirizzo": "VIA ROMA 1 MILANO",
            "errore": None,
        }

    async def test_valid_without_data(self):
        payload = {"valid": True, "name": "---", "address": ""}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out["valido"] is True
        assert out["denominazione"] is None
        assert out["indirizzo"] is None

    async def test_invalid_vat(self):
        payload = {"valid": False, "name": "---", "address": "---"}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out["valido"] is False
        assert out["disponibile"] is True

    async def test_isvalid_key_variant(self):
        # Newer VIES REST deployments use isValid instead of valid.
        payload = {"isValid": True, "name": "ACME SRL", "address": "VIA ROMA 1"}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out["valido"] is True

    async def test_ms_unavailable(self):
        payload = {"userError": "MS_UNAVAILABLE"}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out["disponibile"] is False
        assert out["valido"] is None
        assert "MS_UNAVAILABLE" in out["errore"]

    async def test_transport_error(self):
        exc = httpx.ConnectTimeout("timeout")
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(exc=exc)):
            out = await check_vat("12345670017")
        assert out["disponibile"] is False
        assert out["valido"] is None
        assert out["errore"]

    async def test_http_5xx(self):
        with patch(
            "src.lib.vies.client.httpx.AsyncClient",
            return_value=_mock_async_client({"error": "boom"}, status=500),
        ):
            out = await check_vat("12345670017")
        assert out["disponibile"] is False


@pytest.mark.live
class TestLive:
    async def test_real_vies_roundtrip(self):
        # Ferrari S.p.A. — stable, well-known Italian VAT number.
        out = await check_vat("00159560366")
        assert out["disponibile"] is True
        assert out["valido"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/test_vies.py -q 2>&1 | tail -3
```
Expected: collection error — `ModuleNotFoundError: No module named 'src.lib.vies'`.

- [ ] **Step 3: Implement the lib**

Create `src/lib/vies/client.py`:

```python
"""VIES (VAT Information Exchange System) REST client.

Free EU service for VAT number validation. For Italian numbers, a local
checksum pre-check avoids useless network calls. Member-state data
(name/address) is returned when the MS provides it; "---" means withheld.
"""

import httpx

from src.lib._http import retry_request

VIES_ENDPOINT = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def checksum_partita_iva(piva: str) -> bool:
    """Luhn-like checksum for Italian 11-digit VAT numbers (DPR 633/1972 art. 35)."""
    piva = piva.strip().replace(" ", "")
    if not piva.isdigit() or len(piva) != 11:
        return False
    somma = 0
    for i, c in enumerate(piva[:10]):
        digit = int(c)
        if i % 2 == 0:
            somma += digit
        else:
            doubled = digit * 2
            somma += doubled if doubled < 10 else doubled - 9
    return (10 - (somma % 10)) % 10 == int(piva[10])


def _clean(value: object) -> str | None:
    """VIES returns '---' or '' when the member state withholds the datum."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and value != "---" else None


async def check_vat(vat_number: str, country_code: str = "IT") -> dict:
    """Query VIES for a VAT number. Never raises: errors land in the dict.

    Returns: {disponibile, valido, denominazione, indirizzo, errore}.
    """
    payload = {"countryCode": country_code.upper(), "vatNumber": vat_number.strip().replace(" ", "")}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await retry_request(client, "post", VIES_ENDPOINT, json=payload)
            data = resp.json()
    except (httpx.TransportError, httpx.HTTPStatusError) as exc:
        return {
            "disponibile": False,
            "valido": None,
            "denominazione": None,
            "indirizzo": None,
            "errore": f"VIES non raggiungibile: {exc.__class__.__name__}",
        }

    valid = data.get("valid", data.get("isValid"))
    user_error = data.get("userError", "")
    if valid is None:
        return {
            "disponibile": False,
            "valido": None,
            "denominazione": None,
            "indirizzo": None,
            "errore": f"VIES: {user_error or 'risposta senza esito'}",
        }
    return {
        "disponibile": True,
        "valido": bool(valid),
        "denominazione": _clean(data.get("name")),
        "indirizzo": _clean(data.get("address")),
        "errore": None,
    }
```

Create `src/lib/vies/__init__.py`:

```python
from src.lib.vies.client import VIES_ENDPOINT, check_vat, checksum_partita_iva

__all__ = ["VIES_ENDPOINT", "check_vat", "checksum_partita_iva"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/unit/test_vies.py -m "not live" -q 2>&1 | tail -3
```
Expected: 12 passed (5 checksum + 7 check_vat), live test deselected.

- [ ] **Step 5: Commit**

```bash
git add src/lib/vies/ tests/unit/test_vies.py
git commit -m "feat(lib): add VIES REST client with IT checksum pre-check"
```

---

### Task 3: tool `verifica_partita_iva_vies` + server registration

**Files:**
- Create: `src/tools/analisi_fornitori.py`
- Modify: `src/server.py` (import list only, line ~62-93)
- Test: `tests/unit/test_vies.py` (append tool tests)

**Interfaces:**
- Consumes: `check_vat`, `checksum_partita_iva` from `src.lib.vies` (Task 2).
- Produces: `verifica_partita_iva_vies(partita_iva: str, codice_paese: str = "IT") -> dict` — async MCP tool, tags `{"privacy", "utility"}`. Returns `{partita_iva, codice_paese, checksum_valido, disponibile, valido, denominazione, indirizzo, errore}`. `disponibile` is `None` when VIES was not consulted (failed checksum). Task 5 registers the second tool in this same module.

- [ ] **Step 1: Append the failing tool tests**

Append to `tests/unit/test_vies.py`:

```python
# ---------------------------------------------------------------------------
# Tool: verifica_partita_iva_vies
# ---------------------------------------------------------------------------

import importlib


def _tool(fn_name: str):
    mod = importlib.import_module("src.tools.analisi_fornitori")
    fn = getattr(mod, fn_name)
    return fn.fn if hasattr(fn, "fn") else fn


class TestVerificaPartitaIvaViesTool:
    async def test_checksum_failure_skips_network(self):
        with patch("src.tools.analisi_fornitori.check_vat", new=AsyncMock()) as mocked:
            out = await _tool("verifica_partita_iva_vies")(partita_iva="12345670018")
        mocked.assert_not_awaited()
        assert out["checksum_valido"] is False
        assert out["valido"] is False
        assert out["disponibile"] is None
        assert "checksum" in out["errore"]

    async def test_valid_flow_merges_lib_result(self):
        lib_result = {
            "disponibile": True,
            "valido": True,
            "denominazione": "ACME SRL",
            "indirizzo": "VIA ROMA 1",
            "errore": None,
        }
        with patch("src.tools.analisi_fornitori.check_vat", new=AsyncMock(return_value=lib_result)):
            out = await _tool("verifica_partita_iva_vies")(partita_iva=" 12345670017 ")
        assert out["partita_iva"] == "12345670017"
        assert out["codice_paese"] == "IT"
        assert out["checksum_valido"] is True
        assert out["valido"] is True
        assert out["denominazione"] == "ACME SRL"

    async def test_non_it_skips_checksum(self):
        lib_result = {
            "disponibile": True,
            "valido": True,
            "denominazione": "GMBH",
            "indirizzo": None,
            "errore": None,
        }
        with patch("src.tools.analisi_fornitori.check_vat", new=AsyncMock(return_value=lib_result)) as mocked:
            out = await _tool("verifica_partita_iva_vies")(partita_iva="DE123456789", codice_paese="DE")
        mocked.assert_awaited_once()
        assert out["checksum_valido"] is None
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/unit/test_vies.py -m "not live" -q 2>&1 | tail -3
```
Expected: errors — `ModuleNotFoundError: No module named 'src.tools.analisi_fornitori'`.

- [ ] **Step 3: Implement the tool module (first tool only)**

Create `src/tools/analisi_fornitori.py`:

```python
"""MCP tools for supplier-ledger privacy screening (analisi mastrino fornitori).

TRIGGER: usare quando l'utente deve analizzare il mastrino fornitori di un cliente
ai fini GDPR (individuare i responsabili ex art. 28 da nominare), verificare una
P.IVA sul VIES, o produrre il report Excel standard dell'analisi fornitori.
"""

from src.lib.vies import check_vat, checksum_partita_iva
from src.server import mcp


@mcp.tool(tags={"privacy", "utility"})
async def verifica_partita_iva_vies(partita_iva: str, codice_paese: str = "IT") -> dict:
    """Verifica una partita IVA sul VIES (servizio UE gratuito): validità e, se disponibili, denominazione e indirizzo registrati.

    Per le P.IVA italiane esegue prima il checksum locale: se fallisce, il VIES non
    viene interrogato. Usare per agganciare con certezza l'identità di un fornitore
    (es. durante l'analisi del mastrino fornitori). `disponibile: false` significa
    VIES/stato membro momentaneamente non raggiungibile: procedere con la sola
    ricerca web e annotarlo.

    Vigenza: Regolamento (UE) 904/2010 (cooperazione amministrativa IVA); DPR 633/1972 art. 35 per il checksum.
    Precisione: ESATTO per validità; denominazione/indirizzo dipendono dai dati forniti dallo stato membro.

    Args:
        partita_iva: Numero IVA senza prefisso paese (per l'Italia: 11 cifre)
        codice_paese: Codice ISO dello stato membro (default "IT")
    """
    piva = partita_iva.strip().replace(" ", "")
    paese = codice_paese.strip().upper() or "IT"
    checksum: bool | None = checksum_partita_iva(piva) if paese == "IT" else None

    if checksum is False:
        return {
            "partita_iva": piva,
            "codice_paese": paese,
            "checksum_valido": False,
            "disponibile": None,
            "valido": False,
            "denominazione": None,
            "indirizzo": None,
            "errore": "checksum non valido — VIES non interrogato",
        }

    esito = await check_vat(piva, paese)
    return {
        "partita_iva": piva,
        "codice_paese": paese,
        "checksum_valido": checksum,
        **esito,
    }
```

- [ ] **Step 4: Register the module in `src/server.py`**

In the `from src.tools import (...)` block (line ~62), the list is roughly load-order; add after `procure_quotazioni,`:

```python
    analisi_fornitori,
```

- [ ] **Step 5: Run tests + import smoke**

```bash
.venv/bin/python -m pytest tests/unit/test_vies.py -m "not live" -q 2>&1 | tail -3
.venv/bin/python -c "import src.server; print('server import OK')"
```
Expected: 15 passed; `server import OK`.

- [ ] **Step 6: Commit**

```bash
git add src/tools/analisi_fornitori.py src/server.py tests/unit/test_vies.py
git commit -m "feat(tools): add verifica_partita_iva_vies (VIES lookup)"
```

---

### Task 4: `genera_report_fornitori` — canonical-record validation

**Files:**
- Modify: `src/tools/analisi_fornitori.py` (add validation layer; tool comes in Task 5)
- Test: `tests/unit/test_analisi_fornitori.py` (create)

**Interfaces:**
- Produces (used by Task 5):
  - `QUALIFICAZIONI = {"responsabile", "titolare_autonomo", "fuori_perimetro"}`
  - `CONFIDENZE = {"alto", "medio", "basso"}`
  - `PROBABILITA = {"alta", "media", "bassa"}`
  - `DPA_VALORI = {"si", "no", "da_verificare"}`
  - `_valida_fornitori(fornitori: list) -> list[str]` — returns ALL violation messages (`"riga N: ..."`, 1-based), empty list when valid. Pure, no I/O.

- [ ] **Step 1: Write the failing validation tests**

Create `tests/unit/test_analisi_fornitori.py`:

```python
"""Unit tests for genera_report_fornitori: validation and xlsx rendering."""

import importlib

import pytest

from src.tools.analisi_fornitori import _valida_fornitori


def _tool(fn_name: str):
    mod = importlib.import_module("src.tools.analisi_fornitori")
    fn = getattr(mod, fn_name)
    return fn.fn if hasattr(fn, "fn") else fn


def _riga_ok(**overrides) -> dict:
    """A fully valid 'responsabile' canonical record; override per-test."""
    base = {
        "denominazione_mastrino": "ACME CLOUD SRL",
        "piva_cf": "01234567890",
        "fonte_piva": "mastrino",
        "attivita": "Hosting e SaaS gestionale",
        "categorie_dati": "Dati di clienti/utenti del titolare",
        "qualificazione": "responsabile",
        "motivazione": "SaaS che tratta dati per conto del titolare",
        "probabilita_responsabile": "alta",
        "dpa_proprio": "no",
        "confidenza": "medio",
        "fonti": ["https://esempio.it"],
        "note": "",
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None or k in overrides}


class TestValidazione:
    def test_lista_valida(self):
        assert _valida_fornitori([_riga_ok()]) == []

    def test_lista_vuota(self):
        errs = _valida_fornitori([])
        assert len(errs) == 1 and "vuota" in errs[0]

    def test_non_lista(self):
        errs = _valida_fornitori("non una lista")
        assert len(errs) == 1

    def test_riga_non_dict(self):
        errs = _valida_fornitori(["stringa"])
        assert errs and errs[0].startswith("riga 1:")

    def test_campi_obbligatori_mancanti(self):
        errs = _valida_fornitori([_riga_ok(denominazione_mastrino="", motivazione=None)])
        joined = " | ".join(errs)
        assert "denominazione_mastrino" in joined and "motivazione" in joined

    def test_enum_qualificazione(self):
        errs = _valida_fornitori([_riga_ok(qualificazione="RESPONSABILE")])
        assert errs and "qualificazione" in errs[0]

    def test_enum_confidenza(self):
        errs = _valida_fornitori([_riga_ok(confidenza="altissimo")])
        assert errs and "confidenza" in errs[0]

    def test_responsabile_richiede_probabilita_e_dpa(self):
        errs = _valida_fornitori([_riga_ok(probabilita_responsabile=None, dpa_proprio=None)])
        joined = " | ".join(errs)
        assert "probabilita_responsabile" in joined and "dpa_proprio" in joined

    def test_non_responsabile_vieta_campi_responsabile(self):
        riga = _riga_ok(qualificazione="titolare_autonomo")
        errs = _valida_fornitori([riga])
        joined = " | ".join(errs)
        assert "probabilita_responsabile" in joined and "dpa_proprio" in joined

    def test_titolare_autonomo_valido(self):
        riga = _riga_ok(
            qualificazione="titolare_autonomo",
            probabilita_responsabile=None,
            dpa_proprio=None,
        )
        riga.pop("probabilita_responsabile")
        riga.pop("dpa_proprio")
        assert _valida_fornitori([riga]) == []

    def test_fonti_non_lista(self):
        errs = _valida_fornitori([_riga_ok(fonti="https://esempio.it")])
        assert errs and "fonti" in errs[0]

    def test_indici_multipli(self):
        errs = _valida_fornitori([_riga_ok(), _riga_ok(confidenza="x"), _riga_ok(qualificazione="y")])
        assert any(e.startswith("riga 2:") for e in errs)
        assert any(e.startswith("riga 3:") for e in errs)
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/unit/test_analisi_fornitori.py -q 2>&1 | tail -3
```
Expected: `ImportError: cannot import name '_valida_fornitori'`.

- [ ] **Step 3: Implement validation in `src/tools/analisi_fornitori.py`**

Add below the imports (before the VIES tool):

```python
QUALIFICAZIONI = {"responsabile", "titolare_autonomo", "fuori_perimetro"}
CONFIDENZE = {"alto", "medio", "basso"}
PROBABILITA = {"alta", "media", "bassa"}
DPA_VALORI = {"si", "no", "da_verificare"}

_CAMPI_OBBLIGATORI = ("denominazione_mastrino", "qualificazione", "motivazione", "confidenza")


def _valida_fornitori(fornitori) -> list[str]:
    """Collect-all validation of canonical supplier records (1-based row indexes)."""
    if not isinstance(fornitori, list):
        return ["'fornitori' deve essere una lista di oggetti"]
    if not fornitori:
        return ["'fornitori' è una lista vuota: nessun fornitore da riportare"]

    errori: list[str] = []
    for i, riga in enumerate(fornitori, start=1):
        if not isinstance(riga, dict):
            errori.append(f"riga {i}: non è un oggetto")
            continue
        for campo in _CAMPI_OBBLIGATORI:
            valore = riga.get(campo)
            if not isinstance(valore, str) or not valore.strip():
                errori.append(f"riga {i}: campo obbligatorio '{campo}' mancante o vuoto")
        qualificazione = riga.get("qualificazione")
        if isinstance(qualificazione, str) and qualificazione and qualificazione not in QUALIFICAZIONI:
            errori.append(
                f"riga {i}: 'qualificazione' non valida ({qualificazione!r}); ammessi: {sorted(QUALIFICAZIONI)}"
            )
        confidenza = riga.get("confidenza")
        if isinstance(confidenza, str) and confidenza and confidenza not in CONFIDENZE:
            errori.append(f"riga {i}: 'confidenza' non valida ({confidenza!r}); ammessi: {sorted(CONFIDENZE)}")

        probabilita = riga.get("probabilita_responsabile")
        dpa = riga.get("dpa_proprio")
        if qualificazione == "responsabile":
            if probabilita not in PROBABILITA:
                errori.append(
                    f"riga {i}: 'probabilita_responsabile' obbligatoria per i responsabili; ammessi: {sorted(PROBABILITA)}"
                )
            if dpa not in DPA_VALORI:
                errori.append(
                    f"riga {i}: 'dpa_proprio' obbligatorio per i responsabili; ammessi: {sorted(DPA_VALORI)}"
                )
        elif qualificazione in QUALIFICAZIONI:
            if probabilita is not None:
                errori.append(
                    f"riga {i}: 'probabilita_responsabile' presente ma la qualificazione non è 'responsabile'"
                )
            if dpa is not None:
                errori.append(f"riga {i}: 'dpa_proprio' presente ma la qualificazione non è 'responsabile'")

        fonti = riga.get("fonti", [])
        if fonti is not None and not isinstance(fonti, list):
            errori.append(f"riga {i}: 'fonti' deve essere una lista di URL")
    return errori
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/unit/test_analisi_fornitori.py -q 2>&1 | tail -3
```
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/tools/analisi_fornitori.py tests/unit/test_analisi_fornitori.py
git commit -m "feat(tools): add canonical supplier record validation (collect-all)"
```

---

### Task 5: `genera_report_fornitori` — sorting, xlsx rendering, tool

**Files:**
- Modify: `src/tools/analisi_fornitori.py`
- Test: `tests/unit/test_analisi_fornitori.py` (append)

**Interfaces:**
- Consumes: `_valida_fornitori`, enum sets (Task 4).
- Produces: `genera_report_fornitori(fornitori: list[dict], cliente: str, data_analisi: str = "", file_sorgente: str = "", nome_file: str = "") -> str` — sync MCP tool, tags `{"privacy", "utility"}`. Returns `"File salvato: <path> (<KB> KB)"` or `"Errore di validazione: riga N: ...; riga M: ..."`. Also `_ordina(fornitori) -> list[dict]` (sort key exposed for tests).

- [ ] **Step 1: Append the failing rendering tests**

Append to `tests/unit/test_analisi_fornitori.py`:

```python
# ---------------------------------------------------------------------------
# Rendering xlsx
# ---------------------------------------------------------------------------

from openpyxl import load_workbook

from src.tools.analisi_fornitori import _ordina

_HEADER_ATTESO = [
    "Denominazione (da mastrino)",
    "P.IVA / CF",
    "Attività / servizi",
    "Categorie di dati presumibilmente trattate",
    "Qualificazione ipotizzata",
    "Motivazione sintetica",
    "Probabilità che tratti dati come responsabile",
    "DPA proprio del fornitore disponibile?",
    "Confidenza dell'identificazione",
    "Fonte (URL)",
    "Note / flag",
]


def _fuori(nome="CARTOLERIA ROSSI"):
    riga = _riga_ok(
        denominazione_mastrino=nome,
        qualificazione="fuori_perimetro",
        motivazione="Fornitore di soli beni",
    )
    riga.pop("probabilita_responsabile")
    riga.pop("dpa_proprio")
    return riga


def _titolare(nome="STUDIO BIANCHI COMMERCIALISTI"):
    riga = _riga_ok(
        denominazione_mastrino=nome,
        qualificazione="titolare_autonomo",
        motivazione="Determina autonomamente finalità e mezzi",
    )
    riga.pop("probabilita_responsabile")
    riga.pop("dpa_proprio")
    return riga


class TestOrdina:
    def test_ordinamento_gruppi_e_alfabetico(self):
        righe = [
            _fuori("ZETA CANCELLERIA"),
            _titolare(),
            _riga_ok(denominazione_mastrino="B-CLOUD", dpa_proprio="si"),
            _riga_ok(denominazione_mastrino="A-CLOUD", dpa_proprio="no"),
            _riga_ok(denominazione_mastrino="C-CLOUD", dpa_proprio="da_verificare"),
            _riga_ok(denominazione_mastrino="AA-CLOUD", dpa_proprio="no"),
        ]
        ordinate = [r["denominazione_mastrino"] for r in _ordina(righe)]
        assert ordinate == [
            "A-CLOUD", "AA-CLOUD",              # responsabili dpa=no, alfabetico
            "C-CLOUD",                            # dpa=da_verificare
            "B-CLOUD",                            # dpa=si
            "STUDIO BIANCHI COMMERCIALISTI",      # titolari autonomi
            "ZETA CANCELLERIA",                   # fuori perimetro
        ]


class TestGeneraReport:
    def test_errore_validazione_non_scrive_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.tools.analisi_fornitori._OUTPUT_DIR", str(tmp_path))
        out = _tool("genera_report_fornitori")(
            fornitori=[_riga_ok(confidenza="x")], cliente="Cliente Srl"
        )
        assert out.startswith("Errore di validazione: riga 1:")
        assert list(tmp_path.iterdir()) == []

    def test_file_generato_struttura(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.tools.analisi_fornitori._OUTPUT_DIR", str(tmp_path))
        out = _tool("genera_report_fornitori")(
            fornitori=[_riga_ok(), _titolare(), _fuori()],
            cliente="Cliente Srl",
            data_analisi="30/07/2026",
            file_sorgente="mastrino.xlsx",
        )
        assert out.startswith("File salvato: ")
        files = list(tmp_path.glob("analisi_fornitori_cliente_srl_*.xlsx"))
        assert len(files) == 1

        wb = load_workbook(files[0])
        assert wb.sheetnames == ["Avvertenze", "Analisi fornitori"]

        ws = wb["Analisi fornitori"]
        header = [c.value for c in ws[1]]
        assert header == _HEADER_ATTESO
        assert ws.freeze_panes == "A2"

        prima_riga = [c.value for c in ws[2]]
        assert prima_riga[0] == "ACME CLOUD SRL"
        assert prima_riga[4] == "Responsabile del trattamento"
        assert prima_riga[6] == "Alta"
        assert prima_riga[7] == "No"
        assert prima_riga[8] == "Medio"
        assert prima_riga[9] == "https://esempio.it"

        riga_titolare = [c.value for c in ws[3]]
        assert riga_titolare[4] == "Titolare autonomo"
        assert riga_titolare[6] == "—"
        assert riga_titolare[7] == "—"

        riga_fuori = [c.value for c in ws[4]]
        assert riga_fuori[4] == "Fuori perimetro privacy"

    def test_avvertenze_contenuto(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.tools.analisi_fornitori._OUTPUT_DIR", str(tmp_path))
        _tool("genera_report_fornitori")(
            fornitori=[_riga_ok(), _titolare(), _fuori()],
            cliente="Cliente Srl",
            data_analisi="30/07/2026",
            file_sorgente="mastrino.xlsx",
        )
        wb = load_workbook(next(tmp_path.glob("*.xlsx")))
        testo = " ".join(str(c.value) for row in wb["Avvertenze"].iter_rows() for c in row if c.value)
        assert "Cliente Srl" in testo
        assert "30/07/2026" in testo
        assert "mastrino.xlsx" in testo
        assert "3" in testo                      # totale fornitori
        assert "validare" in testo               # disclaimer
        assert "Basso" in testo                  # review warning

    def test_fonti_multiple_su_piu_righe(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.tools.analisi_fornitori._OUTPUT_DIR", str(tmp_path))
        _tool("genera_report_fornitori")(
            fornitori=[_riga_ok(fonti=["https://a.it", "https://b.it"])],
            cliente="X",
        )
        wb = load_workbook(next(tmp_path.glob("*.xlsx")))
        cella = wb["Analisi fornitori"].cell(row=2, column=10).value
        assert cella == "https://a.it\nhttps://b.it"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/unit/test_analisi_fornitori.py -q 2>&1 | tail -3
```
Expected: `ImportError: cannot import name '_ordina'`.

- [ ] **Step 3: Implement sorting + rendering + tool**

Add to `src/tools/analisi_fornitori.py`. Top of file, extend imports:

```python
import os
import re
import tempfile
import uuid
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
```

Then add below the validation layer:

```python
_OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "mcp-legal-it")

_HEADERS = (
    "Denominazione (da mastrino)",
    "P.IVA / CF",
    "Attività / servizi",
    "Categorie di dati presumibilmente trattate",
    "Qualificazione ipotizzata",
    "Motivazione sintetica",
    "Probabilità che tratti dati come responsabile",
    "DPA proprio del fornitore disponibile?",
    "Confidenza dell'identificazione",
    "Fonte (URL)",
    "Note / flag",
)
_COL_WIDTHS = (30, 16, 34, 34, 20, 40, 16, 16, 14, 32, 40)

_LABEL_QUALIFICAZIONE = {
    "responsabile": "Responsabile del trattamento",
    "titolare_autonomo": "Titolare autonomo",
    "fuori_perimetro": "Fuori perimetro privacy",
}
_LABEL_PROBABILITA = {"alta": "Alta", "media": "Media", "bassa": "Bassa"}
_LABEL_DPA = {"si": "Sì", "no": "No", "da_verificare": "Da verificare"}
_LABEL_CONFIDENZA = {"alto": "Alto", "medio": "Medio", "basso": "Basso"}

_DISCLAIMER = (
    "Analisi automatica di primo livello, da validare con il cliente e con i contratti. "
    "Ove manchi la P.IVA alcune identificazioni sono incerte: verificare manualmente le "
    "voci con Confidenza \"Basso\" e i flag \"controverso\" nelle Note."
)

_ORDINE_DPA = {"no": 0, "da_verificare": 1, "si": 2}


def _chiave_ordinamento(riga: dict) -> tuple:
    qualificazione = riga["qualificazione"]
    if qualificazione == "responsabile":
        gruppo = _ORDINE_DPA[riga["dpa_proprio"]]
    elif qualificazione == "titolare_autonomo":
        gruppo = 3
    else:
        gruppo = 4
    return (gruppo, riga["denominazione_mastrino"].upper())


def _ordina(fornitori: list[dict]) -> list[dict]:
    """No-DPA responsabili first (they need a nomina), then the rest; A-Z within groups."""
    return sorted(fornitori, key=_chiave_ordinamento)


def _sanitize_filename(name: str) -> str:
    name = name.lower().replace(" ", "_")
    name = re.sub(r"[^a-z0-9_\-]", "", name)
    return name[:50] or "cliente"


def _scrivi_avvertenze(ws, cliente: str, data_analisi: str, file_sorgente: str, fornitori: list[dict]) -> None:
    conte = {"responsabile": 0, "titolare_autonomo": 0, "fuori_perimetro": 0}
    nomine = 0
    for riga in fornitori:
        conte[riga["qualificazione"]] += 1
        if riga["qualificazione"] == "responsabile" and riga["dpa_proprio"] == "no":
            nomine += 1

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 90
    righe = [
        ("Analisi privacy fornitori", ""),
        ("Cliente (titolare)", cliente),
        ("Data analisi", data_analisi),
        ("File sorgente", file_sorgente or "—"),
        ("Totale fornitori analizzati", len(fornitori)),
        ("Responsabili del trattamento", conte["responsabile"]),
        ("— di cui senza DPA proprio (nomina da predisporre)", nomine),
        ("Titolari autonomi", conte["titolare_autonomo"]),
        ("Fuori perimetro privacy", conte["fuori_perimetro"]),
        ("", ""),
        ("AVVERTENZE", _DISCLAIMER),
    ]
    for r, (etichetta, valore) in enumerate(righe, start=1):
        ws.cell(row=r, column=1, value=etichetta).font = Font(bold=True)
        cella = ws.cell(row=r, column=2, value=valore)
        cella.alignment = Alignment(wrap_text=True, vertical="top")


def _scrivi_analisi(ws, fornitori: list[dict]) -> None:
    intestazione_font = Font(bold=True, color="FFFFFF")
    intestazione_fill = PatternFill("solid", fgColor="4472C4")
    for col, (header, width) in enumerate(zip(_HEADERS, _COL_WIDTHS), start=1):
        cella = ws.cell(row=1, column=col, value=header)
        cella.font = intestazione_font
        cella.fill = intestazione_fill
        cella.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A2"

    for r, riga in enumerate(fornitori, start=2):
        responsabile = riga["qualificazione"] == "responsabile"
        valori = (
            riga["denominazione_mastrino"],
            riga.get("piva_cf") or "",
            riga.get("attivita") or "",
            riga.get("categorie_dati") or "",
            _LABEL_QUALIFICAZIONE[riga["qualificazione"]],
            riga["motivazione"],
            _LABEL_PROBABILITA[riga["probabilita_responsabile"]] if responsabile else "—",
            _LABEL_DPA[riga["dpa_proprio"]] if responsabile else "—",
            _LABEL_CONFIDENZA[riga["confidenza"]],
            "\n".join(riga.get("fonti") or []),
            riga.get("note") or "",
        )
        for col, valore in enumerate(valori, start=1):
            cella = ws.cell(row=r, column=col, value=valore)
            cella.alignment = Alignment(wrap_text=True, vertical="top")


@mcp.tool(tags={"privacy", "utility"})
def genera_report_fornitori(
    fornitori: list[dict],
    cliente: str,
    data_analisi: str = "",
    file_sorgente: str = "",
    nome_file: str = "",
) -> str:
    """Genera l'Excel standard dell'analisi privacy del mastrino fornitori (foglio Avvertenze + 11 colonne).

    Riceve le righe già classificate nel formato canonico dell'analisi fornitori
    (vedi skill analisi-fornitori) e produce SEMPRE lo stesso layout: responsabili
    senza DPA proprio in cima (sono le nomine da predisporre), poi gli altri
    responsabili, i titolari autonomi e i fuori perimetro. Valida ogni riga e in
    caso di errori li restituisce tutti insieme senza scrivere il file.

    Vigenza: art. 28 GDPR (nomina responsabile); art. 4 GDPR (definizioni).
    Precisione: ESATTO per il layout; il contenuto riflette l'analisi ricevuta.

    Args:
        fornitori: Lista di record canonici (denominazione_mastrino, qualificazione,
            motivazione, confidenza obbligatori; probabilita_responsabile e
            dpa_proprio solo per i responsabili; piva_cf, attivita, categorie_dati,
            fonti, note opzionali)
        cliente: Denominazione del titolare (il cliente dello studio)
        data_analisi: Data dell'analisi in formato gg/mm/aaaa (default: oggi)
        file_sorgente: Nome del file mastrino analizzato (mostrato in Avvertenze)
        nome_file: Nome file di output personalizzato (default generato dal cliente)
    """
    errori = _valida_fornitori(fornitori)
    if errori:
        return "Errore di validazione: " + "; ".join(errori)
    if not cliente or not cliente.strip():
        return "Errore di validazione: 'cliente' è obbligatorio"

    data_analisi = data_analisi.strip() or date.today().strftime("%d/%m/%Y")
    ordinate = _ordina(fornitori)

    wb = Workbook()
    ws_avvertenze = wb.active
    ws_avvertenze.title = "Avvertenze"
    _scrivi_avvertenze(ws_avvertenze, cliente.strip(), data_analisi, file_sorgente.strip(), ordinate)
    _scrivi_analisi(wb.create_sheet("Analisi fornitori"), ordinate)

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    if not nome_file.strip():
        nome_file = f"analisi_fornitori_{_sanitize_filename(cliente)}_{uuid.uuid4().hex[:8]}.xlsx"
    elif not nome_file.endswith(".xlsx"):
        nome_file = nome_file.strip() + ".xlsx"
    filepath = os.path.join(_OUTPUT_DIR, os.path.basename(nome_file))
    wb.save(filepath)
    size_kb = round(os.path.getsize(filepath) / 1024, 1)
    return f"File salvato: {filepath} ({size_kb} KB)"
```

- [ ] **Step 4: Run the full new-module tests**

```bash
.venv/bin/python -m pytest tests/unit/test_analisi_fornitori.py tests/unit/test_vies.py -m "not live" -q 2>&1 | tail -3
```
Expected: all pass (12 validation + 5 rendering + 15 vies = 32).

- [ ] **Step 5: Commit**

```bash
git add src/tools/analisi_fornitori.py tests/unit/test_analisi_fornitori.py
git commit -m "feat(tools): add genera_report_fornitori xlsx report generator"
```

---

### Task 6: skill package `analisi-fornitori`

**Files:**
- Create: `plugin/skills/analisi-fornitori/SKILL.md`
- Create: `plugin/skills/analisi-fornitori/references/metodologia.md`
- Create: `plugin/skills/analisi-fornitori/references/classificazione.md`
- Create: `plugin/skills/analisi-fornitori/references/dpa-whitelist.md`

**Interfaces:**
- Consumes: `verifica_partita_iva_vies` (Task 3), `genera_report_fornitori` (Task 5), existing `genera_dpa` tool.
- Produces: the user-facing skill. No code; verification is structural (frontmatter parses, files exist).

The four files below are complete — create them verbatim.

- [ ] **Step 1: Create `SKILL.md`**

````markdown
---
name: analisi-fornitori
description: Usa questa skill quando il cliente invia il mastrino fornitori (o un elenco fatture/fornitori) e serve lo screening privacy — es. «analizza il mastrino fornitori», «chi dobbiamo nominare responsabile ex art. 28», «screening fornitori GDPR», «analisi fornitori per la nomina», «il cliente ci ha mandato l'elenco dei fornitori/fatture». Estrae i fornitori da qualunque formato (Excel, CSV, PDF, scansioni, corpo mail), li deduplica, li identifica via web e VIES, ipotizza il ruolo privacy di ciascuno (Responsabile art. 28 / Titolare autonomo / Fuori perimetro) con confidenza tarata, produce l'Excel standard con genera_report_fornitori e, su conferma, le bozze di nomina ex art. 28 con genera_dpa per i responsabili senza DPA proprio.
---

# Analisi fornitori — screening privacy del mastrino

Qualifica ogni fornitore del mastrino rispetto al ruolo privacy nel rapporto con il
**cliente dello studio (il titolare del trattamento)**. È uno screening di primo
livello: la qualifica dipende dalla prestazione CONCRETA resa al cliente, che il
mastrino non rivela — l'esito va validato con cliente e contratti, e la Confidenza
deve rifletterlo.

## Regole d'oro (valgono in ogni fase)

1. **Mai inventare**: attività, P.IVA e servizi si affermano solo con una fonte
   (URL) o con conferma VIES. Fornitore non identificabile → categoria più
   probabile + Confidenza `basso` + alternative in `note`.
2. **Gli importi sono irrilevanti**: ignorarli sempre.
3. **Confidenza al ribasso**: nel dubbio, abbassa. `alto` SOLO con identificazione
   univoca confermata (P.IVA presente o agganciata via VIES). Senza P.IVA nel
   mastrino, `alto` è l'eccezione.
4. **Contratto canonico**: ogni fornitore analizzato è un oggetto JSON con i campi
   di `references/metodologia.md` §Contratto. I tool lo validano — rispettalo.

## Fase 0 — Setup

Chiedi (se non già noti): denominazione del **cliente titolare** e file del
mastrino. Crea `analisi_fornitori_checkpoint.json` accanto al mastrino (fallback:
directory corrente). Se esiste già un checkpoint per quel mastrino, proponi di
riprendere dal primo fornitore non analizzato invece di ripartire.

Struttura del checkpoint:

```json
{
  "versione": 1,
  "cliente": "...",
  "file_mastrino": "...",
  "creato": "ISO-8601",
  "fase": "estrazione | dedup | ricerca | completata",
  "fornitori_estratti": [],
  "fornitori_unici": [],
  "analisi": []
}
```

Aggiorna il checkpoint dopo OGNI mutazione (fine estrazione, fine dedup, fine di
ogni blocco di ricerca).

## Fase 1 — Estrazione

Leggi il mastrino nel formato in cui arriva (guida per formato in
`references/metodologia.md` §Estrazione). Estrai per ogni riga: denominazione
e P.IVA/CF se presente. Se il file è illeggibile (scansione pessima, corrotto):
fermati e chiedi una copia migliore. Salva in `fornitori_estratti`.

## Fase 2 — Dedup e gate

Applica le regole di `references/metodologia.md` §Dedup. Salva in
`fornitori_unici` (con le varianti unificate in `varianti`). Poi **fermati** e
chiedi: *«N fornitori unici (da M righe). Procedo con la ricerca? [tempo stimato:
~X min]»*. Sopra ~40 fornitori proponi anche la modalità parallela (sotto).

## Fase 3 — Ricerca e classificazione

A blocchi di ~15 fornitori. Per ciascuno:

1. **Aggancio**: se ha P.IVA → `verifica_partita_iva_vies(partita_iva=...)`. Se
   `valido` e `denominazione` compatibile → identità confermata (`fonte_piva`
   resta `"mastrino"`; annota la conferma). Se il VIES è indisponibile
   (`disponibile: false`) → prosegui web-only e annotalo in `note`.
2. **Ricerca web**: attività e servizi reali (strategia e query in
   `references/metodologia.md` §Identificazione). Cita sempre la fonte in `fonti`.
3. **Classificazione**: applica `references/classificazione.md` (3 categorie,
   casi controversi con default e flag).
4. **DPA** (solo responsabili): consulta `references/dpa-whitelist.md`; se non in
   lista, ricerca mirata «{fornitore} data processing agreement / DPA / nomina
   responsabile»; esito `si`/`no`/`da_verificare`.
5. **Confidenza**: tabella in `references/metodologia.md` §Confidenza.

Appendi ogni record completato ad `analisi` nel checkpoint a fine blocco.

### Modalità parallela (>~40 fornitori, su conferma dell'utente)

Dispatch di un subagent generico per blocco (~15 fornitori) con questo prompt,
compilando i placeholder:

> Sei un DPO esperto di GDPR e prassi del Garante. Analizza questi fornitori del
> cliente «{CLIENTE}» (titolare del trattamento) e restituisci SOLO un array JSON
> di record canonici, nessun altro testo. Per ogni fornitore: (1) se ha P.IVA
> usa il tool verifica_partita_iva_vies per confermare l'identità; (2) ricerca
> web per attività/servizi, cita gli URL in `fonti`, non inventare nulla; (3)
> classifica secondo le regole che seguono; (4) per i responsabili valuta se il
> fornitore pubblica un proprio DPA standard; (5) taratura confidenza: `alto`
> solo con P.IVA confermata, nel dubbio abbassa. Fornitore non identificabile o
> omonimia → categoria più probabile, confidenza `basso`, alternative in `note`.
> REGOLE DI CLASSIFICAZIONE: {contenuto integrale di references/classificazione.md}
> CONTRATTO RECORD: {sezione Contratto di references/metodologia.md}
> WHITELIST DPA: {contenuto di references/dpa-whitelist.md}
> FORNITORI DA ANALIZZARE: {blocco JSON da fornitori_unici}

Al merge di ogni blocco applica i **guardrail**:
- record con `confidenza: "alto"` senza P.IVA confermata → declassa a `"medio"`;
- record che non rispettano il contratto → scarta e rifai quel blocco in
  modalità sequenziale.

## Fase 4 — Report

Chiama `genera_report_fornitori(fornitori=<analisi dal checkpoint>,
cliente=..., data_analisi=..., file_sorgente=...)`. Se restituisce errori di
validazione, correggi i record indicati e richiama. Consegna il file all'utente
e imposta `fase: "completata"` (report e nomine sono rigenerabili in qualsiasi
momento dai dati del checkpoint).

## Fase 5 — Nomine ex art. 28 (su conferma)

Elenca i responsabili con `dpa_proprio: "no"` e chiedi UNA conferma per
generarle tutte. Per ciascuno chiama `genera_dpa` con titolare = cliente,
responsabile = fornitore (usa denominazione confermata e P.IVA se nota) e la
descrizione del trattamento derivata da `attivita`/`categorie_dati`. Un DOCX
per fornitore. Ricorda all'utente che per i responsabili `da_verificare` va
prima chiarito il rapporto contrattuale.
````

- [ ] **Step 2: Create `references/metodologia.md`**

````markdown
# Metodologia — estrazione, dedup, identificazione, confidenza

## Contratto (record canonico per fornitore)

```json
{
  "denominazione_mastrino": "obbligatorio — come appare nel mastrino",
  "piva_cf": "11 cifre P.IVA o 16 caratteri CF, oppure null",
  "fonte_piva": "mastrino | vies | web | null",
  "attivita": "sintesi dalla ricerca (con fonte)",
  "categorie_dati": "categorie di dati presumibilmente trattate",
  "qualificazione": "responsabile | titolare_autonomo | fuori_perimetro",
  "motivazione": "obbligatoria, sintetica",
  "probabilita_responsabile": "alta | media | bassa — SOLO se responsabile",
  "dpa_proprio": "si | no | da_verificare — SOLO se responsabile",
  "confidenza": "alto | medio | basso",
  "fonti": ["URL"],
  "note": "flag controverso, omonimie, VIES indisponibile, ecc."
}
```

Valori in snake_case minuscolo: il tool `genera_report_fornitori` valida e
rifiuta tutto il lotto elencando le righe errate.

## Estrazione per formato

- **Excel/CSV** (export gestionali: TeamSystem, Zucchetti, Danea…): cerca le
  colonne denominazione/ragione sociale/fornitore e P.IVA/CF/partita IVA. Righe
  di subtotale, saldo o riporto NON sono fornitori. Un file può avere più fogli.
- **PDF nativo**: tabelle estraibili come testo; attenzione alle denominazioni
  spezzate su due righe (ricomponile).
- **Scansione**: OCR; i numeri di P.IVA sono i più soggetti a errori OCR (0/O,
  1/I, 8/B) — se il checksum fallisce, trascrivi in `note` il dubbio invece di
  «correggere» a caso.
- **Corpo mail / elenco libero**: estrai le denominazioni così come scritte.
- In OGNI formato: gli importi si ignorano; l'IBAN non è un identificativo del
  ruolo privacy.

## Dedup e normalizzazione

1. Chiave primaria: **P.IVA/CF** quando presente (stessa P.IVA = stesso
   fornitore, qualunque sia la grafia).
2. Altrimenti **denominazione normalizzata**: maiuscole, senza punteggiatura,
   senza forme societarie (SRL, S.R.L., SPA, SNC, SAS, SS, DITTA, SOC. COOP.),
   spazi compressi.
3. Unifica le varianti evidenti («ACME», «ACME SRL», «ACME S.R.L. — MILANO»),
   registrandole in `varianti`. NON unificare nomi simili ma plausibilmente
   diversi («ROSSI SRL» vs «ROSSI COSTRUZIONI SRL»): meglio due voci che una
   fusione sbagliata.

## Identificazione (ricerca web)

- Query utili: `"{denominazione}" partita iva`, `"{denominazione}" {città se
  nota}`, `"{denominazione}" sito ufficiale`.
- Fonti preferite, in ordine: sito ufficiale del fornitore; directory camerali
  (ufficiocamerale.it, registroimprese.it e derivati); pagine social aziendali
  solo in mancanza d'altro.
- Se trovi una P.IVA via web: confermala con `verifica_partita_iva_vies` e, se
  valida e compatibile con la denominazione, imposta `fonte_piva: "web"` (o
  `"vies"` se è il VIES a fornire la denominazione decisiva).
- **Omonimia** (più soggetti plausibili) o nome generico: NON scegliere a caso.
  Categoria più probabile, `confidenza: "basso"`, alternative in `note`.

## Confidenza (taratura)

| Livello | Quando |
|---------|--------|
| `alto` | Identificazione univoca E confermata: P.IVA dal mastrino con VIES valido/denominazione compatibile, oppure P.IVA reperita e confermata senza soggetti alternativi |
| `medio` | Identificazione probabile ma non certa (nome distintivo, attività coerente, nessuna conferma P.IVA) |
| `basso` | Nome comune/generico, ambiguo, non identificato, o solo fonti deboli |

Nel dubbio, abbassa. Il VIES indisponibile non alza né abbassa: annota e procedi.
````

- [ ] **Step 3: Create `references/classificazione.md`**

````markdown
# Classificazione — tassonomia, casi controversi, categorie di dati

Il ruolo va ipotizzato rispetto al rapporto con **il cliente dello studio
(titolare)**. Nota di metodo: la qualifica dipende dalla prestazione concreta
resa, che il mastrino non rivela — è uno screening da validare con cliente e
contratti; la Confidenza deve rifletterlo.

## Le tre categorie (una sola per fornitore)

### `responsabile` — Responsabile del trattamento (art. 28 GDPR)
Tratta dati personali PER CONTO del titolare, su sue istruzioni.
Esempi: cloud/hosting/SaaS, software gestionali con accesso ai dati, agenzie
marketing/adv che gestiscono liste o campagne del titolare, piattaforme di
e-mail marketing, payroll gestito per conto, manutentori IT con accesso ai
sistemi, call center, società di archiviazione/distruzione documenti.

### `titolare_autonomo` — Titolare autonomo
Determina autonomamente finalità e mezzi del trattamento.
Esempi: commercialista, avvocati e notai esterni, banche e istituti di
pagamento, assicurazioni, medico competente, agenzie interinali, e — di norma —
consulente del lavoro / studio paghe.

### `fuori_perimetro` — Fuori perimetro privacy
Non tratta dati personali per conto del cliente.
Esempi: fornitori di soli beni, cancelleria, utenze (luce/gas/acqua),
carburante, hardware senza accesso ai sistemi, manutenzioni edili/impianti,
ristorazione, pulizie (senza accesso sistematico a dati).

## Casi controversi — default + flag

Assegna il default, scrivi `controverso` in `note`, Confidenza MAI sopra `medio`:

| Fornitore | Default | Perché è controverso |
|-----------|---------|----------------------|
| Consulente del lavoro / studio paghe | `titolare_autonomo` | Prassi e giurisprudenza oscillano; se opera su istruzioni stringenti può essere responsabile |
| Corrieri / spedizionieri | `titolare_autonomo` | Trattano i dati dei destinatari con autonomia organizzativa propria |
| Recupero crediti | dipende dalla ricerca | Mandato su istruzioni = `responsabile`; acquisto del credito = `titolare_autonomo`. Confidenza `basso` |
| Telefonia / TLC business | `titolare_autonomo` | Titolari per i dati di traffico; ma servizi gestiti (centralino cloud) possono renderli responsabili |
| Software house locale con assistenza | `responsabile` | Se ha accesso anche solo occasionale ai sistemi/dati; verificare il contratto di assistenza |

## Categorie di dati presumibilmente trattate (per compilare `categorie_dati`)

- Responsabili IT/cloud: «dati di clienti/utenti/dipendenti del titolare
  ospitati o accessibili nei sistemi».
- Payroll/consulenti lavoro: «dati dei dipendenti, anche particolari
  (salute: assenze, visite) e giudiziari ove previsti».
- Marketing: «dati di contatto e comportamentali di clienti/prospect».
- Corrieri: «dati identificativi e di recapito dei destinatari».
- Professionisti (commercialista, legali): «dati contabili/fiscali/giudiziari
  pertinenti all'incarico».
- Fuori perimetro: «nessuno per conto del titolare» (o vuoto).
````

- [ ] **Step 4: Create `references/dpa-whitelist.md`**

````markdown
# Whitelist DPA — fornitori con DPA proprio standard

Per i RESPONSABILI: se il fornitore mette a disposizione un proprio DPA
standard (tipicamente incorporato nei termini di servizio), impostare
`dpa_proprio: "si"` — di norma NON serve una nomina del titolare, ma va
verificato che il DPA sia effettivamente accettato/richiamato nel contratto.
Verificare sempre la versione vigente al link.

| Fornitore | DPA |
|-----------|-----|
| Google (Workspace, Cloud, Ads) | https://business.safety.google/adsprocessorterms/ e https://cloud.google.com/terms/data-processing-addendum |
| Microsoft (365, Azure) | https://www.microsoft.com/licensing/docs/view/Microsoft-Products-and-Services-Data-Protection-Addendum-DPA |
| Amazon AWS | https://aws.amazon.com/it/compliance/gdpr-center/ |
| Meta (Business Tools) | https://www.facebook.com/legal/terms/dataprocessing |
| LinkedIn | https://www.linkedin.com/legal/l/dpa |
| Stripe | https://stripe.com/legal/dpa |
| PayPal | https://www.paypal.com/legalhub/paypal/dataprotection-full |
| Shopify | https://www.shopify.com/legal/dpa |
| Mailchimp (Intuit) | https://mailchimp.com/legal/data-processing-addendum/ |
| HubSpot | https://legal.hubspot.com/dpa |
| Salesforce | https://www.salesforce.com/company/legal/agreements/ |
| Zoom | https://explore.zoom.us/en/gdpr/ |
| Dropbox | https://www.dropbox.com/security/GDPR |
| Slack | https://slack.com/intl/it-it/terms-of-service/data-processing |
| Atlassian | https://www.atlassian.com/legal/data-processing-addendum |
| Aruba | https://www.aruba.it/documenti-contrattuali.aspx (atto di nomina nei documenti contrattuali) |
| Register.it | https://www.register.it/company/legal/ |
| TeamSystem | https://www.teamsystem.com/legal (condizioni servizi cloud) |
| Zucchetti | https://www.zucchetti.it/website/cms/privacy.html (addendum servizi SaaS) |

PMI locale / fornitore non in lista e senza DPA pubblicato → quasi sempre
`dpa_proprio: "no"` (serve la nomina del titolare, tool `genera_dpa`).
Nel dubbio: `da_verificare`.
````

- [ ] **Step 5: Structural verification**

```bash
python3 - <<'EOF'
import pathlib, re
base = pathlib.Path("plugin/skills/analisi-fornitori")
skill = (base / "SKILL.md").read_text()
fm = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
assert fm, "frontmatter mancante"
assert "name: analisi-fornitori" in fm.group(1)
assert "description:" in fm.group(1)
for ref in ["metodologia.md", "classificazione.md", "dpa-whitelist.md"]:
    p = base / "references" / ref
    assert p.exists() and p.stat().st_size > 500, f"{ref} mancante o vuoto"
    assert f"references/{ref}" in skill, f"{ref} non citato in SKILL.md"
print("skill package OK")
EOF
```
Expected: `skill package OK`.

- [ ] **Step 6: Commit**

```bash
git add plugin/skills/analisi-fornitori/
git commit -m "feat(skills): add analisi-fornitori supplier screening skill"
```

---

### Task 7: server instructions + CLAUDE.md counts and docs

**Files:**
- Modify: `src/server.py` (docstring + instructions string)
- Modify: `CLAUDE.md` (submodule root)

**Interfaces:**
- Consumes: tool names from Tasks 3 and 5 (`verifica_partita_iva_vies`, `genera_report_fornitori`), skill name from Task 6 (`analisi-fornitori`).

- [ ] **Step 1: `src/server.py` — docstring count**

Line 1: replace `216 Italian legal tools` with `218 Italian legal tools`.

- [ ] **Step 2: `src/server.py` — instructions string**

In the instructions block: the line starting `- GDPR/PRIVACY COMPLIANCE:` (line ~29) — append to its end:

```
, analisi mastrino fornitori (verifica_partita_iva_vies per VIES, genera_report_fornitori per l'Excel standard)
```

After the workflow line `Compliance GDPR → analisi_base_giuridica → ...` (line ~51) add a new line:

```
Analisi fornitori → verifica_partita_iva_vies → genera_report_fornitori → genera_dpa (nomine per i responsabili senza DPA)
```

- [ ] **Step 3: `CLAUDE.md` — counts and sections**

Run `grep -n "216\|31 moduli\|22 skill" CLAUDE.md` and apply:

1. Header quote (`> MCP server con 216 tool...`): `216` → `218`.
2. `## Tool disponibili (31 moduli, 216 tool)` → `(32 moduli, 218 tool)`.
3. Compatibility table rows `216 tool di calcolo e ricerca` → `218 tool...`; `22 skills + 8 comandi + 6 agenti` → `23 skills + 8 comandi + 6 agenti` (and the note below the table mentioning `216`/`22` if present).
4. In the `Struttura` tree, under `src/tools/`, after the `procure_quotazioni.py` line add:
   ```
   │       └── analisi_fornitori.py   # verifica_partita_iva_vies, genera_report_fornitori
   ```
   and under `src/lib/` add:
   ```
   │   │   └── vies/                  # Client VIES (validazione P.IVA UE)
   │   │       └── client.py          # check_vat(), checksum_partita_iva()
   ```
5. In the `### Privacy/GDPR Compliance` tool table add two rows:
   ```
   | `verifica_partita_iva_vies(partita_iva, codice_paese?)` | Verifica P.IVA sul VIES: validità + denominazione/indirizzo registrati |
   | `genera_report_fornitori(fornitori, cliente, ...)` | Excel standard dell'analisi privacy del mastrino fornitori (11 colonne + Avvertenze) |
   ```
6. In the tests tree add:
   ```
   │   ├── test_vies.py               # Test client VIES + tool verifica_partita_iva_vies
   │   ├── test_analisi_fornitori.py  # Test validazione + report xlsx fornitori
   ```
7. In the numbered calculation-category list (`14. Recupero crediti seriale (2 tool)` is last), append:
   ```
   15. Analisi fornitori (2 tool) — `verifica_partita_iva_vies` (VIES), `genera_report_fornitori` (Excel standard screening privacy mastrino)
   ```

Do NOT touch `docs/tools-catalog.md` / `docs/strumenti.md` (stale, separate cleanup) nor CHANGELOG/manifest versions (release-time).

- [ ] **Step 4: Verify**

```bash
grep -c "218" CLAUDE.md src/server.py; grep -n "analisi_fornitori\|analisi-fornitori" CLAUDE.md | head
.venv/bin/python -c "import src.server; print('OK')"
```
Expected: non-zero counts, tree/table hits, `OK`.

- [ ] **Step 5: Commit**

```bash
git add src/server.py CLAUDE.md
git commit -m "docs: register analisi-fornitori tools in server instructions and CLAUDE.md"
```

---

### Task 8: final verification + handoff

**Files:** none new.

- [ ] **Step 1: Full suite**

```bash
.venv/bin/python -m pytest tests/ -m "not live" -q 2>&1 | tail -3
```
Expected: baseline count from Task 1 Step 6 **+ 32** new tests, 0 failures.

- [ ] **Step 2: Server registration smoke**

```bash
.venv/bin/python - <<'EOF'
import asyncio, src.server
tools = asyncio.run(src.server.mcp.get_tools())
names = set(tools)
assert "verifica_partita_iva_vies" in names, "vies tool non registrato"
assert "genera_report_fornitori" in names, "report tool non registrato"
print(f"tools totali: {len(names)}")
EOF
```
Expected: both asserts pass; total = 218.

- [ ] **Step 3: (Optional, network) one live VIES roundtrip**

```bash
.venv/bin/python -m pytest tests/unit/test_vies.py -m live -q 2>&1 | tail -2
```
Expected: 1 passed (skip gracefully if offline — do not block on this).

- [ ] **Step 4: Review branch state and STOP for the user**

```bash
git log --oneline origin/develop..HEAD
git status -sb
```

Then report to the user and **wait for their decision** — do NOT push without
confirmation. Options to present: (a) push `feature/analisi-fornitori` and open
a PR to `develop` (Git Flow), (b) keep local for manual testing first. Version
bump to 2.11.0 happens later via the `legal-it:release` skill, on user request.

---

## Plan self-review notes

- Spec coverage: dependency wiring (T1), VIES lib+tool (T2-T3), validation
  (T4), rendering/sort/Avvertenze (T5), skill+references+parallel
  mode+checkpoint+nomine (T6), registration+docs (T7), verification+Git Flow
  stop (T8). Error-handling spec items map to: VIES-down (T2/T3 + skill),
  unreadable ledger + resume + guardrails (T6 SKILL.md), malformed rows (T4/T5).
- Checksum test vectors verified by hand: `12345670017` valid, `12345670018`
  invalid.
- Test-count expectations: T2=12, T3=+3 (15), T4=12, T5=+5 (17); total new
  tests 32.
- `{PLACEHOLDER}` tokens inside the Task 6 subagent prompt are runtime template
  slots for the skill, not plan gaps.



