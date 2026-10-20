"""Benchmark interessi_corso_causa vs avvocatoandreani.it/servizi/calcolo-interessi-corso-causa.php.

Norma: art. 1284 co. 4 c.c. (L. 162/2014, art. 17 DL 132/2014); D.Lgs. 231/2002.

Convenzioni del sito: il modulo ha "Decorrenza credito", "Domanda giudiziale" e
"Calcola interessi al". Per confrontare la sola parte in corso di causa si pone la
decorrenza del credito uguale alla data della domanda; "Tasso fisso" spento,
"Rivaluta annualmente" spento. Il sito conta il giorno della domanda (dies a quo
incluso) e l'ultimo giorno; il tool somma due periodi (causa + post sentenza) con
arrotondamento per periodo, il sito arrotonda per semestre: scarti di 0,01 euro
sull'aggregato sono attesi e rientrano nella tolleranza di 0,01 euro.
"""

import os

os.environ["LEGAL_TODAY"] = "2026-09-25"

import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import src.server  # noqa: E402,F401
from src.tools.tassi_interessi import interessi_corso_causa  # noqa: E402

from tests.comparison.conftest import accept_cookies, assert_close, parse_euro  # noqa: E402

_fn = getattr(interessi_corso_causa, "fn", interessi_corso_causa)
URL = "https://www.avvocatoandreani.it/servizi/calcolo-interessi-corso-causa.php"
# 0,01 euro (brief) + epsilon per il rumore dei float sul confronto di due arrotondamenti
TOL = 0.01 + 1e-9


def _sito(page, capitale, data_inizio, data_causa, data_fine):
    """Guida il modulo; ritenta una volta se il risultato non compare (il sito e' lento a rispondere)."""
    body = ""
    for _ in range(2):
        page.wait_for_timeout(2000)  # cortesia verso il sito
        page.goto(URL, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        accept_cookies(page)
        page.fill("input[name='Capitale']", str(capitale))
        for pre, d in (("Inizio", data_inizio), ("Causa", data_causa), ("Fine", data_fine)):
            y, m, g = d.split("-")
            page.select_option(f"select[name='Giorno{pre}']", g)
            page.select_option(f"select[name='Mese{pre}']", m)
            page.select_option(f"select[name='Anno{pre}']", y)
        page.evaluate("document.querySelector('input[name=TassoFisso]').checked=false")
        page.evaluate("document.querySelector('input[name=Rivaluta]').checked=false")
        page.click("input[type=submit]", force=True)
        page.wait_for_load_state("domcontentloaded")
        try:
            page.wait_for_function("document.body.innerText.includes('Totale interessi:')", timeout=12000)
        except Exception:
            continue
        body = page.inner_text("body")
        break
    m = re.search(r"Totale interessi:\s*€\s*([\d.,]+)", body)
    assert m, "risultato non trovato sul sito"
    tipo = "moratori" if "Totale interessi moratori" in body else "legali"
    return parse_euro(m.group(1)), tipo, body


def _confronta(page, cap, cit, sent, pag=None):
    kw = dict(capitale=cap, data_citazione=cit, data_sentenza=sent)
    if pag:
        kw["data_pagamento"] = pag
    r = _fn(**kw)
    assert "errore" not in r, r
    sito, tipo, _ = _sito(page, cap, cit, cit, pag or sent)
    return r["totale_interessi"], sito, tipo


def test_causa_2022_2024_salti_bce(page):
    # Piano: 12.236,99 (8,00%, 10,50%, 12,00%, 12,50%); art. 1284 co. 4 c.c.
    tool, sito, tipo = _confronta(page, 50000, "2022-01-01", "2024-06-01")
    assert tipo == "moratori"
    assert_close(tool, sito, TOL, "totale interessi")


def test_primo_giorno_applicazione_11_12_2014(page):
    # CONFINE. Piano: 805,55 (8,15% al 31/12/2014, 8,05% nel 2015); procedimento iniziato l'11/12/2014.
    tool, sito, tipo = _confronta(page, 10000, "2014-12-11", "2015-12-11")
    assert tipo == "moratori"
    assert_close(tool, sito, TOL, "totale interessi")


def test_vigilia_entrata_in_vigore_10_12_2014(page):
    # CONFINE. Domanda del 10/12/2014, un giorno prima: art. 17 co. 2 DL 132/2014 esclude la mora,
    # si applica il saggio legale (art. 1284 co. 1). Il tool applica comunque la mora.
    tool, sito, tipo = _confronta(page, 10000, "2014-12-10", "2015-12-10")
    assert tipo == "legali", "il sito dovrebbe applicare il saggio legale"
    assert_close(tool, sito, TOL, "totale interessi (ante 11/12/2014)")


def test_procedimento_ante_2014(page):
    # Piano: saggio legale 1,0%/0,5%/0,2% = 116,30 (art. 17 co. 2 DL 132/2014); il tool dà 1.618,73.
    tool, sito, tipo = _confronta(page, 10000, "2014-06-03", "2016-06-03")
    assert tipo == "legali"
    assert_close(tool, sito, TOL, "totale interessi (ante 11/12/2014)")


def test_post_sentenza_a_cavallo_semestre_2026(page):
    # Piano: causa 1.991,26 + post sentenza 1.247,29 = 3.238,55 (11,15%, 10,15%, 10,40%).
    tool, sito, tipo = _confronta(page, 20000, "2025-03-10", "2026-02-20", "2026-09-30")
    assert tipo == "moratori"
    assert_close(tool, sito, TOL, "totale interessi")


def test_anno_bisestile_2019_2020(page):
    # CONFINE (anno bisestile, cambio di anno). Mora D.Lgs. 231/2002 su 7.500 euro, 15/06/2019 - 01/03/2020.
    tool, sito, tipo = _confronta(page, 7500, "2019-06-15", "2020-03-01")
    assert_close(tool, sito, TOL, "totale interessi")


def test_un_solo_giorno_a_cavallo_anno(page):
    # CONFINE. 31/12/2021 -> 01/01/2022: differenza di un giorno, cambio semestre e tasso (dies a quo/ad quem).
    tool, sito, tipo = _confronta(page, 100000, "2021-12-31", "2022-01-01")
    assert_close(tool, sito, TOL, "totale interessi")


def test_periodo_oltre_2026(page):
    # CONFINE. Il tool smette di contare oltre il 31/12/2026 (tabella tassi): il sito ha tassi solo fino al semestre corrente.
    kw = dict(capitale=20000, data_citazione="2026-09-01", data_sentenza="2027-03-01")
    r = _fn(**kw)
    try:
        sito, tipo, _ = _sito(page, 20000, "2026-09-01", "2026-09-01", "2027-03-01")
    except AssertionError:
        pytest.skip("il sito non calcola periodi oltre il 2026")
    assert_close(r["totale_interessi"], sito, TOL, "totale interessi oltre 2026")
