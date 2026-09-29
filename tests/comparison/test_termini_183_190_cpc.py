"""Comparison: termini_183_190_cpc vs avvocatoandreani.it (calcolo-termini-memorie-183-comparse-190.php).

Norma: artt. 183 co. 6 e 190 c.p.c. nel testo anteriore al D.Lgs. 149/2022 (regime
PREVIGENTE, cause iscritte a ruolo prima del 28/02/2023, art. 35 co. 1 D.Lgs. 149/2022);
art. 155 co. 4-5 c.p.c. (proroga sabato/festivi); L. 742/1969 art. 1 (sospensione feriale).

The site offers two modes:
- default ("non prudenziale"): each subsequent term runs from the POSTPONED deadline of the
  previous one (Cass. 13201/2006, Cass. 10741/1997);
- "Modalita' prudenziale": each subsequent term runs from the previous deadline computed
  WITHOUT the art. 155 co. 4-5 postponement.
The tool counts every term from the hearing (30/60/80 days; 60/80 for art. 190), which is
arithmetically the prudential mode. Both modes are exercised below; a failure in the
default mode is a genuine methodological divergence, not a tolerance issue.

Tolerance: dates must match exactly.
"""

import os
import re
import sys

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: E402,F401  (registers all tool modules)
from src.tools.scadenze_termini import termini_183_190_cpc  # noqa: E402

from .conftest import goto  # noqa: E402

PAGE = "calcolo-termini-memorie-183-comparse-190.php"

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_ROW = re.compile(
    r"(Memoria n\. \d|Comparsa|Replica):\s*\d+\s+giorni\s+entro\s+\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})"
)


def _tool(data_udienza, sospensione_feriale=True):
    fn = getattr(termini_183_190_cpc, "fn", termini_183_190_cpc)
    r = fn(data_udienza=data_udienza, sospensione_feriale=sospensione_feriale)
    assert "errore" not in r, r
    # The previgente regime block must always be present (audit settembre 2026).
    reg = r.get("regime_normativo") or {}
    assert reg.get("stato") == "previgente"
    assert {"termini_memorie_repliche", "termini_processuali_civili"} <= set(reg.get("tool_vigenti", []))
    return {s["termine"]: s["scadenza"] for s in r["scadenze"]}


def _site(page, data_udienza, sospensione_feriale, prudenziale, button):
    """Drive the site. button: '#button1' (Memorie 183) or '#button2' (Comparsa e Replica 190)."""
    y, m, d = data_udienza.split("-")
    goto(page, PAGE)
    page.select_option("#GiornoInizio", d)
    page.select_option("#MeseInizio", m)
    page.select_option("#AnnoInizio", y)
    # The checkboxes are styled (a click does not toggle them) and a plain click on the
    # submit button after the cookie handling does not submit: set state and submit via JS.
    page.evaluate(
        "([s, p, b]) => {"
        " document.getElementById('SospensioneFeriale').checked = s;"
        " document.getElementById('Prudenziale').checked = p;"
        " document.getElementById('Termini').requestSubmit(document.querySelector(b)); }",
        [sospensione_feriale, prudenziale, button],
    )
    page.wait_for_url("**#Res", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    text = page.inner_text("body")
    out = {}
    for label, dd, mm, yy in _ROW.findall(text):
        out[label] = f"{int(yy):04d}-{_MESI[mm.lower()]:02d}-{int(dd):02d}"
    assert out, "site returned no result rows"
    return out


def _site_memorie(page, data_udienza, sospensione_feriale=True, prudenziale=False):
    s = _site(page, data_udienza, sospensione_feriale, prudenziale, "#button1")
    return {
        "memoria_183_n1": s["Memoria n. 1"],
        "memoria_183_n2": s["Memoria n. 2"],
        "memoria_183_n3": s["Memoria n. 3"],
    }


def _site_190(page, data_udienza, sospensione_feriale=True, prudenziale=False):
    s = _site(page, data_udienza, sospensione_feriale, prudenziale, "#button2")
    return {"comparsa_conclusionale": s["Comparsa"], "memoria_replica_190": s["Replica"]}


def _compare(tool, site):
    diffs = {k: (tool[k], v) for k, v in site.items() if tool[k] != v}
    assert not diffs, f"tool != sito (tool, sito): {diffs}"


# --- Case 1 (piano) ------------------------------------------------------------------
# Atteso piano: memoria_183_n1 2025-06-03 (31/5 sabato, 1/6 domenica, 2/6 festivo),
# n2 2025-06-30, n3 2025-07-21 contati dall'udienza; se il sito fa decorrere i termini
# successivi dalla scadenza prorogata ottiene 2025-07-03 e 2025-07-23.
def test_memorie_2025_05_01_default(page):
    _compare(_tool("2025-05-01"), _site_memorie(page, "2025-05-01"))


# Same hearing, site in "modalita' prudenziale" (no chaining on the postponed deadline).
def test_memorie_2025_05_01_prudenziale(page):
    _compare(_tool("2025-05-01"), _site_memorie(page, "2025-05-01", prudenziale=True))


# Atteso piano: comparsa 2025-06-30, replica 2025-07-21 (art. 190 previgente: 60 + 20).
def test_190_2025_05_01(page):
    _compare(_tool("2025-05-01"), _site_190(page, "2025-05-01"))


# --- Case 2 (piano, limite: attraversa agosto con sospensione feriale) --------------
# Atteso piano: n1 2025-07-31, n2 2025-09-30, n3 2025-10-20; comparsa 2025-09-30,
# replica 2025-10-20. L. 742/1969 art. 1.
def test_memorie_2025_07_01_feriale(page):
    _compare(_tool("2025-07-01"), _site_memorie(page, "2025-07-01"))


def test_190_2025_07_01_feriale(page):
    _compare(_tool("2025-07-01"), _site_190(page, "2025-07-01"))


# --- Case 3 (piano, limite: senza sospensione, n2 cade sabato 30/8) -----------------
# Atteso piano: n1 2025-07-31, n2 2025-09-01 (30/8 sabato), n3 2025-09-19 (dall'udienza).
# Con decorrenza dalla scadenza prorogata del n2: 1/9 + 20 = 21/9 domenica -> 22/9.
def test_memorie_2025_07_01_senza_feriale(page):
    _compare(_tool("2025-07-01", False), _site_memorie(page, "2025-07-01", sospensione_feriale=False))


# --- Case 4 (limite: comparsa cade di sabato, replica successiva) --------------------
# Udienza PC 2022-01-04 (causa pre-Cartabia): comparsa 4/1 + 60 = sabato 5/3/2022 -> 7/3;
# replica dall'udienza (80 gg) venerdi 25/3/2022; dalla comparsa prorogata 7/3 + 20 =
# domenica 27/3 -> 28/3. Art. 190 c.p.c. previgente, art. 155 co. 4-5.
def test_190_2022_01_04_comparsa_sabato(page):
    _compare(_tool("2022-01-04"), _site_190(page, "2022-01-04"))


# --- Case 5 (limite: udienza 20/6/2022, n2 attraversa agosto, n3 cade domenica) ------
# Tool: n1 2022-07-20, n2 2022-09-19, n3 2022-10-10 (9/10 domenica).
def test_memorie_2022_06_20_feriale(page):
    _compare(_tool("2022-06-20"), _site_memorie(page, "2022-06-20"))


# --- Case 6 (limite: udienza durante la sospensione feriale) -------------------------
# Udienza 10/8/2022: il decorso inizia dal 1/9 (L. 742/1969). n1 = 30/9/2022.
def test_memorie_2022_08_10_udienza_in_agosto(page):
    _compare(_tool("2022-08-10"), _site_memorie(page, "2022-08-10"))


# --- Prudential-mode counterparts of cases 3 and 4 -----------------------------------
# Confirm that the tool's convention (every term counted from the hearing) equals the
# site's "modalita' prudenziale" also when an intermediate deadline is postponed.
def test_memorie_2025_07_01_senza_feriale_prudenziale(page):
    _compare(
        _tool("2025-07-01", False),
        _site_memorie(page, "2025-07-01", sospensione_feriale=False, prudenziale=True),
    )


def test_190_2022_01_04_comparsa_sabato_prudenziale(page):
    _compare(_tool("2022-01-04"), _site_190(page, "2022-01-04", prudenziale=True))
