"""Comparison: calcolo_inflazione vs avvocatoandreani.it/servizi/calcolo-inflazione.php.

Norm / source: indici FOI ISTAT (base 2015=100 raccordata; from January 2026
base 2025=100, official linking coefficient 1.214); official 12/24-month
variations published in GU ex art. 81 L. 392/1978.

Site convention (observed): the site prints the variation with ONE decimal
("Inflazione calcolata con indici Istat: 18,9%") and derives the "somma
equivalente" as capitale / (1 + pct_rounded/100). So the only comparable
quantity is the percentage at one decimal: the tolerance is the site's own
display precision (the brief's four-decimal rule cannot apply because the site
does not publish more digits). The equivalent amount is not compared: it is a
function of the rounded percentage on the site and of the full-precision
coefficient in the tool.
"""

import os
import re
import sys

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

from tests.comparison.conftest import goto

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import src.server  # noqa: E402,F401  (registers every tool module)
from src.tools.rivalutazioni_istat import calcolo_inflazione  # noqa: E402

_fn = getattr(calcolo_inflazione, "fn", calcolo_inflazione)
_PAGE = "calcolo-inflazione.php"


def _site_pct(page, data_inizio: str, data_fine: str) -> float:
    """Drive the site with Istat indices and return the variation (one decimal)."""
    goto(page, _PAGE)
    page.fill("#Capitale", "1000000")
    page.select_option("#MeseInizio", data_inizio[5:7])
    page.select_option("#AnnoInizio", data_inizio[:4])
    page.select_option("#MeseFine", data_fine[5:7])
    page.select_option("#AnnoFine", data_fine[:4])
    # A late-loading page script swallows the click on #btn-calc once the page
    # has fully loaded (force=True included): submit the form natively with the
    # button as submitter so the "Op=Calcola" pair is posted.
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "(() => { const b = document.getElementById('btn-calc'); b.form.requestSubmit(b); })()"
        )
    page.wait_for_timeout(1500)
    text = page.inner_text("body")
    m = re.search(r"(?:In|De)flazione calcolata con indici Istat:\s*(-?[\d.,]+)%", text)
    assert m, "risultato del sito non trovato"
    return float(m.group(1).replace(".", "").replace(",", "."))


def _tool_pct(data_inizio: str, data_fine: str) -> tuple[float, dict]:
    r = _fn(data_inizio=data_inizio, data_fine=data_fine)
    assert "errore" not in r, r
    raw = (r["foi_fine"] - r["foi_inizio"]) / r["foi_inizio"] * 100
    return raw, r


def _compare(page, data_inizio, data_fine):
    raw, r = _tool_pct(data_inizio, data_fine)
    site = _site_pct(page, data_inizio, data_fine)
    ours = round(raw, 1)
    assert abs(ours - site) < 1e-9, (
        f"{data_inizio}->{data_fine}: tool={raw:.4f}% (1 dec {ours}), sito={site}% "
        f"(FOI tool {r['foi_inizio']} -> {r['foi_fine']})"
    )
    return r, site


# --- casi del piano ---------------------------------------------------------

def test_dic2013_dic2023_tratto_sospetto(page):
    """Piano: atteso +18,90% (coeff. ISTAT 1,189 = 118,9 x 1,071 / 107,1);
    il tool restituisce 18,07 per l'indice di dicembre 2013 in tabella (100,7).
    Norma: FOI ISTAT, raccordo base 2010->2015 coefficiente 1,071."""
    _compare(page, "2013-12-01", "2023-12-01")


def test_ago2025_ago2026_ribasamento(page):
    """Piano: variazione ufficiale +3,4% (ISTAT 16/09/2026) in
    variazione_ufficiale_pct; calcolata sulla serie raccordata 3,37.
    Norma: art. 81 L. 392/1978; base 2025=100, raccordo 1,214. Caso al limite
    (12 mesi a cavallo del ribasamento)."""
    r, site = _compare(page, "2025-08-01", "2026-08-01")
    assert r.get("variazione_ufficiale_pct") == site


def test_giu2024_giu2026_biennale(page):
    """Piano: variazione biennale ufficiale +4,4% (GU n. 201 del 31/08/2026);
    calcolata 4,44; media annua 2,20. Norma: art. 81 L. 392/1978."""
    r, site = _compare(page, "2024-06-01", "2026-06-01")
    assert r.get("variazione_ufficiale_pct") == site


def test_dic1989_fuori_serie(page):
    """Piano: dicembre 1989 fuori serie, il tool usa gennaio 1990 con avvertenza
    INDICATIVO (6,16%); il sito (serie dal 1947) restituisce il valore esatto.
    Caso al limite (inizio della serie del tool)."""
    _compare(page, "1989-12-01", "1991-01-01")


# --- casi al limite aggiunti ------------------------------------------------

def test_dic2025_gen2026_confine_base_2025(page):
    """Limite: un mese a cavallo del ribasamento 2025=100 (gennaio 2026).
    Atteso: 121,5 -> 121,9 serie raccordata = +0,3%."""
    _compare(page, "2025-12-01", "2026-01-01")


def test_dic2015_gen2016_confine_base_2015(page):
    """Limite: primo mese della serie base 2015=100 pubblicata da ISTAT
    (gennaio 2016). Atteso -0,2% (deflazione)."""
    _compare(page, "2015-12-01", "2016-01-01")


def test_gen2020_mag2020_deflazione(page):
    """Limite: variazione negativa (il sito cambia etichetta in "Deflazione").
    Atteso -0,4%."""
    _compare(page, "2020-01-01", "2020-05-01")


def test_dic2021_dic2022_annuale(page):
    """Dodici mesi dicembre/dicembre, anno di inflazione alta. Atteso +11,3%
    (variazione ISTAT dic 2022 su dic 2021)."""
    _compare(page, "2021-12-01", "2022-12-01")


def test_gen2016_dic2020(page):
    """Serie base 2015 interamente pubblicata. Atteso dal sito +2,6%."""
    _compare(page, "2016-01-01", "2020-12-01")


def test_gen2015_gen2023_mese_base_2010(page):
    """Limite: gennaio 2015 e' ancora pubblicato da ISTAT in base 2010
    (107 circa, raccordo 1,071). Atteso dal sito +19,0%."""
    _compare(page, "2015-01-01", "2023-01-01")


def test_giu2011_giu2016_tratto_2011_2013(page):
    """Limite: parte dal tratto 2011-2013 della serie del tool segnalato nel
    piano. Atteso dal sito +4,3%."""
    _compare(page, "2011-06-01", "2016-06-01")


def test_giu1995_giu2005_anni_novanta(page):
    """Anni diversi della tabella (base 1995, lira/euro). Atteso dal sito +25,0%."""
    _compare(page, "1995-06-01", "2005-06-01")


# Phase 3 verdict (2026-09-29). The FOI series was rebuilt from the ISTAT original bases and spliced with the
# ISTAT coefficients (1,373 and 1,071; note NM_variazioni_coefficienti.pdf): every case now matches the site
# except test_dic1989_fuori_serie, a convention: the tool series starts in January 1990 and substitutes the
# missing month (INDICATIVO warning), the site starts from 1947.
