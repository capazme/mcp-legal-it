"""Comparison: prescrizione_diritti vs avvocatoandreani.it/servizi/calcolo-prescrizione-diritti.php

Il sito ha un menu IdDiritto (a0..a39, b0..b9) + data di riferimento (giorno/mese/anno,
anni 2016-2036) e risponde "Il diritto si e' prescritto il <giorno> <Mese> <anno>" con la
"Norma di Riferimento". Mappatura tool -> voce del sito:
  ordinaria                -> a21 Fornitori (art. 2946, 10 anni)
  risarcimento_danni       -> a31 fatto illecito (art. 2947, 5 anni)
  risarcimento_rca         -> a32 circolazione veicoli (art. 2947, sito: 2 anni)
  diritti_lavoro           -> a26 indennita' di fine rapporto (art. 2948, 5 anni)
  crediti_professionisti   -> a29 professionisti (art. 2956, sito: 3 anni)
  canoni_locazione         -> a0 affitti (art. 2948, 5 anni)
  contributi_previdenziali -> b2 INPS (art. 3 co. 9 L. 335/1995, 5 anni)
  vizi_vendita, garanzia_appalto -> assenti dal sito (skip).

Il tool e' pinnato a LEGAL_TODAY=2026-09-25; il sito usa la data reale del server, quindi il
flag "prescritto" si confronta solo quando la scadenza dista >10 giorni dal 25/09/2026.
Tolleranza: date esatte.
"""
import os

os.environ["LEGAL_TODAY"] = "2026-09-25"

import re
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import src.server  # noqa: F401,E402
from src.tools.varie import prescrizione_diritti  # noqa: E402

from .conftest import accept_cookies  # noqa: E402

fn = getattr(prescrizione_diritti, "fn", prescrizione_diritti)

URL = "https://www.avvocatoandreani.it/servizi/calcolo-prescrizione-diritti.php"
MESI = {m: i + 1 for i, m in enumerate(
    ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
     "settembre", "ottobre", "novembre", "dicembre"])}
OGGI = date(2026, 9, 25)


def _sito(page, voce: str, data_evento: str):
    a, m, g = data_evento.split("-")
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("select[name='IdDiritto']", voce)
    page.select_option("select[name='GiornoInizio']", g)
    page.select_option("select[name='MeseInizio']", m)
    page.select_option("select[name='AnnoInizio']", a)
    with page.expect_navigation():
        page.click("form input[type=submit]", force=True)
    page.wait_for_timeout(1500)
    testo = page.inner_text("body")
    r = re.search(r"Il diritto\s+(si\s+[^\n]*?)\s*(?:il|l')\s*(\d{1,2})\s+([A-Za-zà-ù]+)\s+(\d{4})", testo)
    assert r, f"risultato non trovato: {testo[-800:]}"
    data = date(int(r.group(4)), MESI[r.group(3).lower()], int(r.group(2)))
    return data, "prescritto" in r.group(1)


def _confronta(page, tipo, voce, data_evento):
    t = fn(tipo_diritto=tipo, data_evento=data_evento)
    assert "errore" not in t, t
    dt_tool = date.fromisoformat(t["data_prescrizione"])
    dt_sito, prescritto_sito = _sito(page, voce, data_evento)
    assert dt_tool == dt_sito, f"tool={dt_tool} sito={dt_sito} ({tipo}, {data_evento})"
    if abs((dt_tool - OGGI).days) > 10:
        assert t["prescritto"] == prescritto_sito


def test_ordinaria_scadenza_domenica_festiva(page):
    # Piano: 2026-10-05 (04/10/2026 domenica e festa nazionale, art. 2963 co. 3 c.c.;
    # oggi il tool restituisce 2026-10-04). CASO AL LIMITE (proroga festivo).
    _confronta(page, "ordinaria", "a21", "2016-10-04")


def test_risarcimento_danni_ferragosto(page):
    # Piano: 2027-08-16 (15/08/2027 domenica e Ferragosto, art. 2963 co. 3; nessuna
    # sospensione feriale sulla prescrizione sostanziale). CASO AL LIMITE (agosto).
    _confronta(page, "risarcimento_danni", "a31", "2022-08-15")


def test_rca_biennale_da_29_febbraio(page):
    # Piano: 2026-02-28 (art. 2947 co. 2; manca il 29/2, art. 2963 co. 5 ultimo giorno
    # del mese). CASO AL LIMITE (bisestile). Il sito calcola 2 anni per a32.
    _confronta(page, "risarcimento_rca", "a32", "2024-02-29")


def test_canoni_locazione_scadenza_sabato(page):
    # Piano: 2026-09-26 (art. 2948 n. 3; il sabato non e' festivo). CASO AL LIMITE (sabato).
    _confronta(page, "canoni_locazione", "a0", "2021-09-26")


def test_crediti_professionisti_triennale(page):
    # Piano: 2026-09-25 (art. 2956 n. 2; si compie allo spirare del giorno, art. 2963 co. 2).
    # CASO AL LIMITE (confine "oggi"). Il sito applica il termine a fine giornata (+1 giorno).
    _confronta(page, "crediti_professionisti", "a29", "2023-09-25")


def test_ordinaria_da_29_febbraio(page):
    # Art. 2946 + art. 2963 co. 5: 29/02/2016 + 10 anni -> manca il 29/2/2026 -> 28/02/2026
    # (sabato, non festivo). CASO AL LIMITE (bisestile).
    _confronta(page, "ordinaria", "a21", "2016-02-29")


def test_diritti_lavoro_quinquennale(page):
    # Art. 2948 c.c. (n. 4-5): 5 anni. Data ordinaria senza festivi: 2019-03-11 -> 2024-03-11 (lunedi').
    _confronta(page, "diritti_lavoro", "a26", "2019-03-11")


def test_contributi_previdenziali(page):
    # Art. 3 co. 9 L. 335/1995: 5 anni. 2020-05-15 -> 2025-05-15 (giovedi').
    _confronta(page, "contributi_previdenziali", "b2", "2020-05-15")


def test_vizi_vendita_non_confrontabile(page):
    pytest.skip("Il sito non offre una voce per la garanzia per vizi (art. 1495 c.c., 1 anno)")


def test_garanzia_appalto_non_confrontabile(page):
    pytest.skip("Il sito non offre una voce per la garanzia dell'appaltatore (art. 1667 c.c., 2 anni)")
