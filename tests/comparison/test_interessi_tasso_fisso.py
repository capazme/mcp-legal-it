"""Comparison: interessi_tasso_fisso vs avvocatoandreani.it/servizi/interessi_tasso_fisso.php

Site convention: simple interest = C x S x N / 36500 (365-day divisor even in
leap years); compound = capitalisation at fixed calendar dates (radio
"Anatocismo": 0 none, 3/6/12 months), last partial period simple interest.
Tool convention: simple = divisor of the start year (366 if leap); compound =
(1+i)^(days/365). Tolerance: 0.01 EUR on amounts (brief).
Norma: artt. 1282-1284 c.c. (interessi), art. 1283 c.c. (anatocismo).
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import time

import pytest

import src.server  # noqa: F401  (registers all tool modules)
from src.tools.tassi_interessi import interessi_tasso_fisso as _tool

from .conftest import accept_cookies, assert_close, extract_amount

fn = getattr(_tool, "fn", _tool)
URL = "https://www.avvocatoandreani.it/servizi/interessi_tasso_fisso.php"
TOL = 0.01


def _it(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _site(page, capitale, tasso, inizio, fine, anatocismo="0") -> float:
    """Drive the form, return 'Totale interessi' shown by the site."""
    time.sleep(1.5)
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("input[name='Tasso']", _it(tasso))
    page.fill("input[name='Capitale']", _it(capitale))
    for k, v in (("Inizio", inizio), ("Fine", fine)):
        y, m, d = v.split("-")
        page.select_option(f"select[name='Giorno{k}']", d)
        page.select_option(f"select[name='Mese{k}']", m)
        page.select_option(f"select[name='Anno{k}']", y)
    # set the radio through the DOM: Playwright's check() raises when the radio is already selected
    page.evaluate(
        "v => { document.querySelector(`input[name='Anatocismo'][value='${v}']`).checked = true; }",
        anatocismo,
    )
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    val = extract_amount(page.inner_text("body"), "Totale interessi")
    if val is None:  # the site is occasionally slow: one longer wait before giving up
        page.wait_for_timeout(4000)
        val = extract_amount(page.inner_text("body"), "Totale interessi")
    assert val is not None, "Totale interessi non trovato nella pagina"
    return val


def _cmp(page, capitale, tasso, inizio, fine, tipo, anatocismo, label):
    r = fn(capitale=capitale, tasso_annuo=tasso, data_inizio=inizio, data_fine=fine, tipo=tipo)
    assert "errore" not in r, r
    s = _site(page, capitale, tasso, inizio, fine, anatocismo)
    assert_close(r["interessi"], s, TOL, label)


def test_semplici_inizio_bisestile(page):
    # Piano: 366 gg, 501,37 col sito (C*S*N/36500); il tool divide per 366 -> 500,00. Limite: divisore.
    _cmp(page, 10000, 5, "2024-01-01", "2025-01-01", "semplici", "0", "semplici inizio bisestile")


def test_semplici_periodo_con_29_febbraio(page):
    # Piano: inizio non bisestile, periodo con 29/2 -> 501,37 (concordano). Limite: anno bisestile nel periodo.
    _cmp(page, 10000, 5, "2023-07-01", "2024-07-01", "semplici", "0", "semplici con 29 feb")


def test_composti_due_anni(page):
    # Piano: tool (1,05)^(731/365) = 1.026,47; sito capitalizzazione annuale alle date fisse. Limite: opzione enumerata (12 mesi).
    _cmp(page, 10000, 5, "2024-01-01", "2026-01-01", "composti", "12", "composti 2 anni annuale")


def test_semplici_infrannuale(page):
    # Piano: 184 gg, 25.000 x 3,5 x 184 / 36500 = 441,10 (anno non bisestile).
    _cmp(page, 25000, 3.5, "2025-03-15", "2025-09-15", "semplici", "0", "semplici infrannuale")


def test_semplici_inizio_29_febbraio_bisestile(page):
    # Limite: inizio 29/2 di anno bisestile, fine 28/2 dell'anno dopo: divisore 366 (tool) vs 365 (sito).
    _cmp(page, 10000, 4, "2024-02-29", "2025-02-28", "semplici", "0", "semplici da 29 feb")


def test_semplici_pluriennale_a_cavallo_bisestile(page):
    # Limite: 2023-01-01 -> 2025-12-31 (3 anni, un bisestile in mezzo): tool divisore 365, sito 365.
    _cmp(page, 50000, 7.25, "2023-01-01", "2025-12-31", "semplici", "0", "semplici triennio")


def test_semplici_agosto_un_giorno(page):
    # Limite: periodo di un solo giorno a cavallo di agosto/settembre (nessuna sospensione feriale per gli interessi).
    _cmp(page, 100000, 12, "2025-08-31", "2025-09-01", "semplici", "0", "semplici 1 giorno")


def test_composti_infrannuale(page):
    # Limite: composti con periodo < 1 anno: tool (1+i)^(g/365), sito capitalizzazione annuale -> interessi semplici sul residuo.
    _cmp(page, 25000, 5, "2025-03-15", "2025-09-15", "composti", "12", "composti infrannuale")


def test_composti_tre_anni_con_bisestile(page):
    # Limite: composti su tre anni con 29/2 2028 nel periodo (2025-03-01 -> 2028-03-01 = 1096 gg).
    _cmp(page, 10000, 5, "2025-03-01", "2028-03-01", "composti", "12", "composti 3 anni bisestile")


def test_composti_semestrale_non_offerto_dal_tool():
    pytest.skip("Il tool capitalizza solo annualmente (tipo 'composti'); il sito offre anche 3 e 6 mesi: nessuna opzione equivalente.")
