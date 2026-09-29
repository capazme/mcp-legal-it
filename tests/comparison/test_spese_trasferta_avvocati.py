"""Comparison: spese_trasferta_avvocati vs avvocatoandreani.it.

Site page: calcolo-spese-trasferta-avvocati.php (spreadsheet updated by JS,
no submit). Per trip column it computes:
  rimborso chilometrico = km x costo carburante/litro x PctRimborsoCarburante%
  (default 20% = one fifth, art. 27 DM 55/2014), plus pedaggi/parcheggio;
  albergo + 10% costi accessori; treno/aereo/altri trasporti; vitto; spese varie.
The site has NO indennita' di trasferta and NO field for hours of absence:
the tool's indennita' (10/20/40% of a fixed 540 euro by 4/8-hour thresholds)
is not comparable. The only comparable quantity is the mileage refund
(tool: flat 0.30 euro/km, i.e. equivalent to fuel at 1.50 euro/l).
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: F401,E402  (registers all tool modules)
from src.tools.fatturazione_avvocati import spese_trasferta_avvocati  # noqa: E402

from .conftest import accept_cookies, assert_close, goto, parse_euro  # noqa: E402

_fn = getattr(spese_trasferta_avvocati, "fn", spese_trasferta_avvocati)
PAGE = "calcolo-spese-trasferta-avvocati.php"


def _fmt(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def _site_trip(page, *, prezzo=None, km=None, albergo=None, treno=None) -> dict:
    """Fill trip column 1 and read the JS-computed totals."""
    goto(page, PAGE, wait_ms=1500)
    # The consent banner (#accept-btn) may appear after goto() has already
    # checked for it; while it is open the JS totals do not update. Dismiss again.
    accept_cookies(page)
    for fid, val in (("CostoCarburante0", prezzo), ("Chilometri0", km),
                     ("Albergo0", albergo), ("Treno0", treno)):
        if val is not None:
            page.fill(f"#{fid}", _fmt(val) if isinstance(val, float) else str(val))
            page.press(f"#{fid}", "Tab")
    page.wait_for_timeout(1000)
    out = {}
    for fid in ("TotCarburante0", "TotAlbergo0", "TotTrasporti0", "TotTrasferta0"):
        raw = page.input_value(f"#{fid}")
        out[fid] = parse_euro(raw) if raw.strip() else 0.0
    return out


def test_auto_200km_4h_carburante_180(page):
    """Piano caso 1: auto, 200 km, 4 ore.

    Atteso (piano): art. 27 DM 55/2014 -> indennita' chilometrica
    200 x (1,80/5) = 72,00 euro (oltre pedaggi/parcheggi); il tool
    applica 0,30 euro/km -> 60,00 (+ indennita' 54,00 = 114,00).
    Confronto sul solo rimborso chilometrico (il sito non calcola l'indennita').
    """
    r = _fn(km_distanza=200, ore_assenza=4, pernottamento=False, mezzo="auto",
            prezzo_carburante_litro=1.80)
    site = _site_trip(page, prezzo=1.80, km=200)
    assert_close(r["rimborso_km"], site["TotCarburante0"], 0.01,
                 "Rimborso km (carburante 1,80 euro/l, 20%)")


def test_auto_200km_carburante_150_punto_equivalenza(page):
    """Caso al limite: prezzo carburante 1,50 euro/l, unico prezzo per cui
    1/5 del costo al litro coincide con la tariffa fissa del tool (0,30 euro/km).

    Atteso: 200 x 1,50 x 20% = 60,00 = 200 x 0,30. Norma: art. 27 DM 55/2014.
    """
    r = _fn(km_distanza=200, ore_assenza=4.01, pernottamento=False, mezzo="auto",
            prezzo_carburante_litro=1.50)
    site = _site_trip(page, prezzo=1.50, km=200)
    assert_close(r["rimborso_km"], site["TotCarburante0"], 0.01,
                 "Rimborso km (carburante 1,50 euro/l)")


def test_auto_km_decimali_carburante_150(page):
    """Arrotondamento con km decimali: 137,5 km a 1,50 euro/l.

    Atteso dalla norma (art. 27 DM 55/2014, un quinto del carburante al litro per km):
    137,5 x 1,50 / 5 = 41,25 (il tool lo da'). Il sito accetta solo km interi e tronca
    a 137 (41,10): e' un limite di input del sito, non una regola della norma, che non
    prevede alcun troncamento (verdetto sito_errato sul decimale). Il confronto col sito
    si fa quindi a 137 km interi, dove tool e sito devono coincidere (41,10).
    """
    assert _fn(km_distanza=137.5, ore_assenza=2, pernottamento=False, mezzo="auto",
               prezzo_carburante_litro=1.50)["rimborso_km"] == 41.25
    r = _fn(km_distanza=137, ore_assenza=2, pernottamento=False, mezzo="auto",
            prezzo_carburante_litro=1.50)
    site = _site_trip(page, prezzo=1.50, km=137)
    assert_close(r["rimborso_km"], site["TotCarburante0"], 0.01,
                 "Rimborso km (137,5 km, 1,50 euro/l)")


def test_confine_4_ore_indennita(page):
    """Piano caso 2: confine delle 4 ore del tool (4,01 h).

    Atteso (piano): soglia non normativa del tool, indennita' 108,00,
    totale 168,00. Il sito non ha un campo ore ne' un'indennita' di trasferta.
    """
    r = _fn(km_distanza=200, ore_assenza=4.01, pernottamento=False, mezzo="auto")
    assert r["indennita_trasferta"] == 108.0 and r["totale_stimato"] == 168.0
    pytest.skip("Il sito non calcola l'indennita' di trasferta ne' ha un campo ore di assenza")


def test_treno_pernottamento_oltre_8_ore(page):
    """Piano caso 3: treno + pernottamento, 8,01 h.

    Atteso (piano): viaggio e albergo a pie' di lista; art. 27 -> albergo
    (limite 4 stelle) maggiorato del 10%; il tool restituisce solo
    l'indennita' 216,00 (40%). Il sito applica +10% all'albergo inserito
    (100 -> 110) ma il tool non accetta l'importo di albergo/treno.
    """
    r = _fn(km_distanza=0, ore_assenza=8.01, pernottamento=True, mezzo="treno")
    assert r["indennita_trasferta"] == 216.0 and r["rimborso_km"] == 0.0
    pytest.skip("Il tool non accetta gli importi di treno/albergo; il sito non calcola "
                "l'indennita' di trasferta: nessuna grandezza comune")
