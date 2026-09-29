"""Comparison: tasso_alcolemico vs avvocatoandreani.it (calcolo-tasso-alcolemico-teorico.php).

Norma: art. 186 D.Lgs. 285/1992 (soglie 0,5 / 0,8 / 1,5 g/l). La stima di Widmark
non e' regola di legge: il sito la offre in tre metodi. Si confronta il metodo
"Formula di Widmark base" (Alcolemia = Pa * 1,055 / (P * Fw), Fw 0,73 M / 0,66 F),
il piu' vicino al tool (Pa / (P * r), r 0,70 M / 0,60 F, senza costante 1,055).

Il sito mostra un solo valore (il picco, a 2 decimali) e le ore per tornare sobri
con eliminazione 0,15 g/l/h: NON accetta le ore trascorse ne' lo stomaco pieno
(nel metodo Widmark "non tiene conto della condizione fisica"). Percio' si
confronta `tasso_picco_g_l` con il valore del sito e `ore_smaltimento` con le ore
"per tornare sobri". Tolleranza 0,005 g/l: mezza unita' dell'ultima cifra
mostrata (entrambi i valori sono arrotondati a 2 decimali).

Una unita' alcolica del tool = 12 g; sul sito si inserisce una bevanda al 15% vol
di 100 ml per UA (100 ml * 0,15 * 0,8 g/ml = 12 g).
"""

import asyncio
import json
import os
import re

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import src.server  # noqa: F401,E402
from src.tools import varie  # noqa: E402

from .conftest import accept_cookies, assert_close  # noqa: E402

URL = "https://www.avvocatoandreani.it/servizi/calcolo-tasso-alcolemico-teorico.php"
TOL = 0.005


def _tool(**kw):
    fn = getattr(varie.tasso_alcolemico, "fn", varie.tasso_alcolemico)
    r = fn(**kw)
    if asyncio.iscoroutine(r):
        r = asyncio.run(r)
    if isinstance(r, str):
        r = json.loads(r)
    return r


def _sito(page, sesso, peso, ua, metodo="2", stomaco="V"):
    page.goto(URL, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("#Metodo", metodo)
    page.evaluate(f"document.querySelector('#Genere-{sesso}').click()")  # click nativo: check(force) non aziona il modulo per F
    page.select_option("#Peso", str(int(peso)))
    if page.is_visible(f"#Stomaco-{stomaco}"):
        page.check(f"#Stomaco-{stomaco}", force=True)
    page.select_option("#Tipo-0", "70")
    page.fill("#Gradi-0", "15")
    page.fill("#Qta-0", str(int(round(ua * 100))))
    page.evaluate("document.querySelector('#btn-calc').click()")
    page.wait_for_timeout(2500)
    txt = page.inner_text("body")
    m = re.search(r"Alcolemia stimata\s*=\s*([\d,\.]+)", txt)
    assert m, "risultato non trovato sul sito"
    val = float(m.group(1).replace(",", "."))
    h = re.search(r"servono indicativamente (\d+) or\w+(?:,\s*(\d+) minut)?", txt)
    ore = None
    if h:
        ore = int(h.group(1)) + (int(h.group(2)) / 60 if h.group(2) else 0)
    return val, ore, txt


def _confronta(page, sesso, peso, ua, ore=0):
    t = _tool(sesso=sesso, peso_kg=peso, unita_alcoliche=ua, ore_trascorse=ore)
    assert "errore" not in t, t
    s, _, _ = _sito(page, sesso, peso, ua)
    assert_close(t["tasso_picco_g_l"], s, TOL, "tasso picco g/l")


def test_uomo_60kg_0_5_gl(page):
    # Piano: 0,50 g/l (21 g / (60 x 0,70)); lett. a) richiede tasso superiore a 0,5.
    # Norma: art. 186 co. 2 D.Lgs. 285/1992. Caso al limite (soglia 0,5).
    _confronta(page, "M", 60, 1.75)


def test_uomo_60kg_0_8_gl(page):
    # Piano: 0,80 g/l; lett. a) (non superiore a 0,8). Caso al limite (soglia 0,8).
    _confronta(page, "M", 60, 2.8)


def test_uomo_60kg_1_5_gl(page):
    # Piano: 1,50 g/l; lett. b). Caso al limite (soglia 1,5).
    _confronta(page, "M", 60, 5.25)


def test_donna_60kg_un_ora_dopo(page):
    # Piano: picco 1,00 g/l (36 g / 36), attuale 0,85 g/l dopo 1 h: lett. b).
    # Il sito non ha le ore trascorse: si confronta solo il picco.
    _confronta(page, "F", 60, 3, ore=1)


def test_ore_per_tornare_sobri(page):
    # Eliminazione 0,15 g/l/h su entrambi: ore_smaltimento_totale = picco / 0,15.
    t = _tool(sesso="M", peso_kg=60, unita_alcoliche=1.75, ore_trascorse=0)
    _, ore, _ = _sito(page, "M", 60, 1.75)
    if ore is None:
        pytest.skip("il sito non riporta le ore di smaltimento")
    assert_close(t["ore_smaltimento_totale"], ore, 0.05, "ore per tornare sobri")


def test_stomaco_pieno_non_confrontabile(page):
    # Il tool riduce del 30% l'alcol a stomaco pieno; il metodo Widmark del sito
    # dichiara di non considerare la condizione fisica (solo il Metodo D lo fa,
    # con un coefficiente diverso). Verifica: il sito ignora lo stomaco.
    page.goto(URL, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("#Metodo", "2")
    if not page.is_visible("#Stomaco-P"):
        pytest.skip("il sito (Widmark base) non offre l'opzione stomaco pieno: non confrontabile")
    v, _, _ = _sito(page, "M", 80, 4, stomaco="V")
    p, _, _ = _sito(page, "M", 80, 4, stomaco="P")
    if v == p:
        pytest.skip("il sito (Widmark base) ignora lo stomaco pieno: opzione non confrontabile")
    t = _tool(sesso="M", peso_kg=80, unita_alcoliche=4, ore_trascorse=0, stomaco_pieno=True)
    assert_close(t["tasso_picco_g_l"], p, TOL, "picco stomaco pieno")
