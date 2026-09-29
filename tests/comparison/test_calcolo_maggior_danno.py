"""Benchmark calcolo_maggior_danno vs avvocatoandreani.it (criterio ISTAT/FOI).

Norma: art. 1224 co. 2 c.c.; Cass. SU 19499/2008; indici FOI ISTAT.
Pagina: calcolo-maggior-danno-obbligazioni-pecuniarie.php, TipoCalcolo=4
(tasso d'inflazione Istat FOI), sviluppo annuale (TipoTassoMedio=1).
Il sito sviluppa il calcolo anno per anno (FOI medio annuo vs saggio legale);
il tool confronta la rivalutazione FOI dell'intero periodo con la somma degli
interessi. Tolleranza 0,01 euro (brief), non allargata.
"""

import os
import re

os.environ["LEGAL_TODAY"] = "2026-09-25"

import pytest

import src.server  # noqa: F401,E402
from src.tools.tassi_interessi import calcolo_maggior_danno  # noqa: E402
from tests.comparison.conftest import accept_cookies, assert_close, parse_euro  # noqa: E402

URL = "https://www.avvocatoandreani.it/servizi/calcolo-maggior-danno-obbligazioni-pecuniarie.php"
_fn = getattr(calcolo_maggior_danno, "fn", calcolo_maggior_danno)
TOL = 0.01


def _sito(page, capitale, inizio, fine, tipo="4", sviluppo="1"):
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("input[name=Capitale]", f"{capitale:.2f}".replace(".", ","))
    for pref, d in (("Inizio", inizio), ("Fine", fine)):
        y, m, g = d.split("-")
        page.select_option(f"select[name=Giorno{pref}]", g)
        page.select_option(f"select[name=Mese{pref}]", m)
        page.select_option(f"select[name=Anno{pref}]", y)
    page.evaluate(
        "([t,s])=>{document.querySelector(`input[name=TipoCalcolo][value='${t}']`).click();"
        "document.querySelector(`input[name=TipoTassoMedio][value='${s}']`).click();}",
        [tipo, sviluppo],
    )
    page.click("#btn-calc", force=True)
    page.wait_for_timeout(3000)
    txt = page.inner_text("body")
    md = re.search(r"Totale Maggior Danno:\s*€?\s*([\d.,]+)", txt)
    ii = re.search(r"Totale interessi legali:\s*€?\s*([\d.,]+)", txt)
    assert ii, "risultato non letto dal sito"
    return (parse_euro(md.group(1)) if md else 0.0), parse_euro(ii.group(1))


def _confronta(page, capitale, inizio, fine):
    r = _fn(capitale=capitale, data_inizio=inizio, data_fine=fine)
    assert "errore" not in r, r
    md, ii = _sito(page, capitale, inizio, fine)
    assert_close(r["interessi_legali"], ii, TOL, "interessi legali")
    assert_close(r["maggior_danno"], md, TOL, "maggior danno")


def test_biennio_2022_2023(page):
    # Piano: tool 451,72 (FOI), sito criterio ISTAT deve coincidere. Art. 1224 co.2 c.c.
    _confronta(page, 10000, "2022-01-01", "2024-01-01")


def test_anno_2011(page):
    # Piano: tool 127,50 su serie FOI 2011 da riscontrare. Art. 1224 co.2 c.c.
    _confronta(page, 10000, "2011-01-01", "2012-01-01")


def test_deflazione_2020(page):
    # Piano: FOI 102,7 -> 102,3, maggior danno 0, interessi 4,59 (0,05%). Caso al limite (deflazione).
    _confronta(page, 10000, "2020-01-15", "2020-12-15")


def test_attraversa_cambio_base_2026_e_agosto(page):
    # Limite: periodo 2025 -> 31/08/2026 (data massima del sito, base FOI 2025=100 dal 2026, agosto).
    _confronta(page, 10000, "2025-01-01", "2026-08-31")


def test_anno_2015_a_cavallo_agosto(page):
    # Limite: date infrannuali a cavallo di agosto e anno 2016 (tasso legale 0,2%).
    _confronta(page, 5000, "2015-08-10", "2016-08-10")
