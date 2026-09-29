"""Comparison: termini_memorie_repliche vs avvocatoandreani.it.

Page: calcolo-termini-memorie-integrative-comparse-repliche.php (button 'Memorie
Integrative 171-ter'). Norm: art. 171-ter c.p.c. (40/20/10 days before the
art. 183 hearing), L. 742/1969 (sospensione feriale 1-31 August), art. 155 c.p.c.
Dates are compared exactly. The site's 'Sospensione straordinaria' checkbox
(pandemic suspension) is unchecked: it is irrelevant for 2025+ hearings.
"""
import asyncio
import os

os.environ["LEGAL_TODAY"] = "2026-09-25"

import re
import sys
from datetime import date

import pytest

sys.path.insert(0, "/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it")
import src.server  # noqa: F401,E402
from src.tools.scadenze_termini import termini_memorie_repliche  # noqa: E402

from tests.comparison.conftest import accept_cookies  # noqa: E402

URL = ("https://www.avvocatoandreani.it/servizi/"
       "calcolo-termini-memorie-integrative-comparse-repliche.php")
MESI = {m: i + 1 for i, m in enumerate(
    ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
     "agosto", "settembre", "ottobre", "novembre", "dicembre"])}


def _tool(data, feriale=True):
    fn = getattr(termini_memorie_repliche, "fn", termini_memorie_repliche)
    r = fn(data_udienza=data, sospensione_feriale=feriale)
    if asyncio.iscoroutine(r):
        r = asyncio.run(r)
    assert "errore" not in r, r
    out = {}
    for s in r["scadenze"]:
        d = next(v for k, v in s.items() if isinstance(v, str)
                 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) and k in
                 ("scadenza", "data", "data_scadenza", "data_effettiva"))
        out[s["termine"]] = d
    return out


def _sito(page, data, feriale=True):
    y, m, d = data.split("-")
    page.goto(URL, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("#GiornoInizio", d)
    page.select_option("#MeseInizio", m)
    page.select_option("#AnnoInizio", y)
    page.evaluate('document.getElementById("SospensioneStraordinaria").checked=false')
    page.evaluate(f'document.getElementById("SospensioneFeriale").checked={str(feriale).lower()}')
    page.click("#button1", force=True)
    page.wait_for_timeout(2500)
    txt = page.inner_text("body")
    dates = re.findall(
        r"Termine per la (prima|seconda|terza) memoria integrativa:.*?"
        r"\)\s*(?:Luned|Marted|Mercoled|Gioved|Venerd|Sabat|Domenic)\w*\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", txt, re.S)
    assert len(dates) == 3, txt[-1500:]
    keys = {"prima": "memoria_integrativa", "seconda": "replica",
            "terza": "prova_contraria"}
    return {keys[o]: date(int(a), MESI[me.lower()], int(g)).isoformat()
            for o, g, me, a in dates}


def _confronta(page, data, feriale=True):
    t = _tool(data, feriale)
    page.wait_for_timeout(1000)
    s = _sito(page, data, feriale)
    assert t == s, f"tool={t} sito={s}"


def test_ottobre_con_feriale(page):
    # Piano: memoria 2025-07-22, replica 2025-09-11, prova contraria 2025-09-19
    # (art. 171-ter; agosto escluso; 21/9 domenica anticipa a venerdi 19).
    _confronta(page, "2025-10-01")


def test_ottobre_senza_feriale(page):
    # Piano: 2025-08-22, 2025-09-11, 2025-09-19 (materia esclusa, art. 3 L. 742/1969).
    _confronta(page, "2025-10-01", feriale=False)


def test_scadenze_weekend(page):
    # Piano: memoria 2025-07-04 (domenica 6/7 anticipata), replica 2025-07-25
    # (sabato 26/7 anticipato), prova contraria 2025-09-05 (art. 155 c.p.c.).
    _confronta(page, "2025-09-15")


def test_limite_udienza_inizio_settembre(page):
    # Limite: udienza 2025-09-03, i termini attraversano tutto agosto (art. 1 L. 742/1969).
    _confronta(page, "2025-09-03")


def test_limite_udienza_1_settembre_feriale(page):
    # Limite: udienza il 1 settembre, il 31 agosto e' sospeso.
    _confronta(page, "2026-09-01")


def test_limite_natale_epifania(page):
    # Limite: termini a ritroso attraverso Natale, Santo Stefano, Capodanno, Epifania.
    _confronta(page, "2026-01-08")


def test_limite_anno_bisestile(page):
    # Limite: 40 giorni a ritroso attraversano il 29 febbraio 2028.
    _confronta(page, "2028-03-15")


def test_limite_pasqua_lunedi_angelo(page):
    # Limite: scadenza in prossimita' di Pasqua/Pasquetta 2026 (5-6 aprile).
    _confronta(page, "2026-04-16")
