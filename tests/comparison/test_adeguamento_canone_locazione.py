"""Comparison: adeguamento_canone_locazione vs avvocatoandreani.it.

Site page: /servizi/calcolo_adeguamento_istat_canone_locazione.php
The site only computes the ANNUAL (12-month) FOI variation ending in the chosen
month of the rolling last-12-months window (Sept 2025 .. Aug 2026 as of
2026-09-25), with 75%, 100% or an integer "Altro" percentage.  It rounds the
variation to one decimal (as the official ISTAT communiqué ex art. 81
L. 392/1978 does) and applies it to the rent.  Biennial periods, arbitrary
stipulation dates and months outside the window cannot be reproduced.

Norms: L. 392/1978 art. 32 (and art. 81 for the official variation);
L. 431/1998 art. 2 co. 3 (75% cap for "concordati").
"""

import os
import re
import sys

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: E401,F401  (registers every tool module)
from src.tools.rivalutazioni_istat import adeguamento_canone_locazione as _tool

from tests.comparison.conftest import accept_cookies, assert_close, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo_adeguamento_istat_canone_locazione.php"
_fn = getattr(_tool, "fn", _tool)


def _euro_it(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _site(page, canone: float, mese: str, pct: int) -> dict:
    """Drive the site; pct 75 / 100 use the radios, anything else 'Altro'."""
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("input[name='Canone']", _euro_it(canone))
    page.select_option("select[name='MeseRif']", mese)
    if pct == 75:
        page.check("input[name='TipoCalcolo'][value='1']", force=True)
    elif pct == 100:
        page.check("input[name='TipoCalcolo'][value='2']", force=True)
    else:
        page.fill("input[name='AltraPct']", str(pct))
    page.click("form#AdeguamentoIstat input[type=submit]", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    m_var = re.search(r"Variazione percentuale dell'indice\s*([\d,]+)%", text)
    m_can = re.search(r"CANONE RIVALUTATO\s*€\s*([\d.,]+)", text)
    m_dec = re.search(r"Decorrenza della rivalutazione\s*(\S+ \d{4})", text)
    assert m_var and m_can, "site result not found"
    page.wait_for_timeout(1500)  # be gentle with the site
    return {
        "variazione": float(m_var.group(1).replace(",", ".")),
        "canone": parse_euro(m_can.group(1)),
        "decorrenza": m_dec.group(1) if m_dec else None,
    }


def _compare(page, canone, stipula, adeguamento, pct, mese, decorrenza):
    r = _fn(canone_annuo=canone, data_stipula=stipula,
            data_adeguamento=adeguamento, percentuale_istat=pct)
    assert "errore" not in r, r
    s = _site(page, canone, mese, int(pct))
    assert s["decorrenza"] == decorrenza, s
    assert_close(r["variazione_foi_piena_pct"], s["variazione"], tolerance=0.0001,
                 label="variazione FOI piena %")
    assert_close(r["canone_annuo_aggiornato"], s["canone"], tolerance=0.01,
                 label="canone rivalutato")


def test_12_mesi_maggio_2026_75(page):
    # Piano: variazione ufficiale maggio 2026 su maggio 2025 +3,0% (GU n. 144
    # del 24/06/2026); 75% = 2,25%; canone 12.270,00 (art. 32 L. 392/1978).
    _compare(page, 12000, "2025-05-01", "2026-05-01", 75, "05", "Maggio 2026")


def test_12_mesi_agosto_2026_comunicato_non_in_gu(page):
    # Piano: variazione agosto 2026 +3,4% (ISTAT 16/09/2026, comunicato non
    # ancora in GU); 75% = 2,55%; canone 9.844,80. Limit: last available month.
    _compare(page, 9600, "2025-08-01", "2026-08-01", 75, "08", "Agosto 2026")


def test_12_mesi_gennaio_2026_ribasamento_100(page):
    # Limit: first month of base 2025=100 (period straddles the rebasing).
    # Official variation Jan 2026 / Jan 2025 +0,8% (GU n. 50 del 02/03/2026);
    # 100% -> 12.096,00. Art. 32 L. 392/1978, art. 81 for the official value.
    _compare(page, 12000, "2025-01-01", "2026-01-01", 100, "01", "Gennaio 2026")


def test_12_mesi_settembre_2025_pre_2026_arrotondamento(page):
    # Limit: period ending BEFORE 2026 (stand-in for the plan's May 2025 case,
    # which the site no longer offers).  Official art. 81 variation is published
    # at one decimal (+1,4%): 75% = 1,05%, canone 12.126,00.  The tool uses the
    # unrounded index ratio 121,7/120,0 - 1 = 1,4167% -> expected mismatch.
    _compare(page, 12000, "2024-09-01", "2025-09-01", 75, "09", "Settembre 2025")


def test_12_mesi_dicembre_2025_altro_60(page):
    # Limit: enumerated option "Altro" (60%) on a pre-2026 period.  Official
    # variation Dec 2025 / Dec 2024 +1,1%; 60% = 0,66%; canone 12.079,20.
    # The tool uses 1,0815% unrounded -> expected mismatch.
    _compare(page, 12000, "2024-12-01", "2025-12-01", 60, "12", "Dicembre 2025")


def test_24_mesi_giugno_2026_100():
    # Piano: variazione biennale ufficiale giugno 2026 +4,4% (GU n. 201 del
    # 31/08/2026); canone 12.528,00.
    pytest.skip("Il sito calcola solo la variazione annuale (12 mesi): biennale non disponibile")


def test_12_mesi_maggio_2025_pre_2026():
    # Piano: variazione ufficiale maggio 2025 +1,4%; 75% = 1,05%; 12.126,00
    # (tool 12.128,03). Covered by the September/December 2025 cases.
    pytest.skip("Il sito offre solo gli ultimi 12 mesi (set 2025-ago 2026): maggio 2025 non selezionabile")


def test_15_mesi_cavallo_ribasamento():
    # Piano: 124,8/121,4 - 1 = 2,80%; 75% = 2,10%; canone 12.252,06.
    pytest.skip("Il sito non accetta una data di stipula: solo periodi di 12 mesi")


def test_percentuale_oltre_massimo():
    # Piano: errore "percentuale_istat deve essere compresa tra 0 e 100".
    r = _fn(canone_annuo=12000, data_stipula="2025-05-01",
            data_adeguamento="2026-05-01", percentuale_istat=100.5)
    assert r.get("errore") == "percentuale_istat deve essere compresa tra 0 e 100"
    pytest.skip("Il campo 'Altro' del sito accetta due cifre intere: 100,5% non inseribile")
