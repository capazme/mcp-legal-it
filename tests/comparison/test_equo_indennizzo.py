"""Benchmark fase 1: equo_indennizzo vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-equo-indennizzo-causa-servizio.php

Modulo ``CalcoloEquoIndennizzo`` (POST). Campi: ``StipendioTabellare`` (testo),
``Categoria`` (select 1-8 + ``9`` = "Indennita' una tantum"), ``Eta`` (select 18-70).
Invio: ``form#CalcoloEquoIndennizzo input[type=submit]``. Risultato: la frase
"L'equo indennizzo calcolato ammonta a € X".

Il sito NON chiede la percentuale di invalidita': la misura dipende dalla sola
categoria della tabella A (o B, "una tantum") DPR 834/1981, dallo stipendio
tabellare (L. 724/1994, commi 210-211 L. 266/2005) e dall'eta' (riduzioni per
eta'). Dai valori osservati: base = 2 x stipendio x percentuale di categoria
(1a = 100%, 5a = 44%, 6a = 27%, 8a = 6%, una tantum = 3%), ridotta del 25% per
eta' 51-60 e del 50% oltre 60 (DPR 461/2001 art. 50 / DPR 349/1994).

Il tool ``equo_indennizzo(categoria_tabella, percentuale_invalidita, stipendio_annuo)``
(src/tools/risarcimento_danni.py) calcola invece stipendio x coefficiente di
categoria (0,7-8) x percentuale di invalidita', senza eta'. Il confronto usa per
il sito un'eta' fuori dalle riduzioni (30 anni) salvo i casi al limite sull'eta'.

Tolleranza: 0,01 euro (brief). Il sito e' un benchmark, non una fonte.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: E402,F401  registra i moduli
from src.tools.risarcimento_danni import equo_indennizzo as _tool  # noqa: E402

from .conftest import accept_cookies, assert_close, parse_euro  # noqa: E402

URL = "https://www.avvocatoandreani.it/servizi/calcolo-equo-indennizzo-causa-servizio.php"
TOL = 0.01

_fn = getattr(_tool, "fn", _tool)


def _sito(page, stipendio: float, categoria: str, eta: int) -> float:
    page.goto(URL, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("input[name='StipendioTabellare']", f"{stipendio:.0f}")
    page.select_option("select[name='Categoria']", categoria)
    page.select_option("select[name='Eta']", str(eta))
    page.click("form#CalcoloEquoIndennizzo input[type=submit]", force=True)
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    m = re.search(r"L'equo indennizzo calcolato ammonta a\s*(€\s*[\d.,]+)", text)
    assert m, "risultato non trovato sulla pagina"
    page.wait_for_timeout(1000)
    return parse_euro(m.group(1))


def _tool_val(**kw) -> float:
    r = _fn(**kw)
    assert "errore" not in r, r
    return r["equo_indennizzo"]


# (id, input tool, eta' sul sito)
CASI = [
    # Piano 1: cat. 5, 35%, 30.000, eta' 45. Atteso piano: "da leggere dal sito; il
    # tool da' 31.500". Norma: DPR 834/1981 tab. A cat. 5; DPR 461/2001.
    ("cat5_eta45", dict(categoria_tabella="5", percentuale_invalidita=35, stipendio_annuo=30000), 45),
    # Piano 1 (seconda eta'): eta' 55 -> riduzione del 25% sul sito (limite: eta').
    ("cat5_eta55", dict(categoria_tabella="5", percentuale_invalidita=35, stipendio_annuo=30000), 55),
    # Piano 2: cat. 1, 90%, 40.000. Atteso piano: tool 288.000 (oltre 7 annualita'),
    # verificare l'ordine di grandezza. Norma: tab. A cat. 1 = doppio dello stipendio.
    ("cat1_max", dict(categoria_tabella="1", percentuale_invalidita=90, stipendio_annuo=40000), 30),
    # Piano 3: cat. 8, 10%, 25.000. Atteso piano: tool 1.750.
    ("cat8_min", dict(categoria_tabella="8", percentuale_invalidita=10, stipendio_annuo=25000), 30),
    # Piano 4: cat. 6, 25%, 28.000 (confine pensione privilegiata per il tool).
    # Atteso piano: tool 17.500, niente pensione privilegiata.
    ("cat6_confine_pensione", dict(categoria_tabella="6", percentuale_invalidita=25, stipendio_annuo=28000), 30),
    # Limite eta': 50 anni (ultima eta' senza riduzione sul sito).
    ("cat5_eta50_limite", dict(categoria_tabella="5", percentuale_invalidita=35, stipendio_annuo=30000), 50),
    # Limite eta': 61 anni (prima eta' con riduzione del 50% sul sito).
    ("cat5_eta61_limite", dict(categoria_tabella="5", percentuale_invalidita=35, stipendio_annuo=30000), 61),
]


@pytest.mark.parametrize("caso_id,inp,eta", CASI, ids=[c[0] for c in CASI])
def test_equo_indennizzo_vs_sito(page, caso_id, inp, eta):
    tool = _tool_val(**inp)
    sito = _sito(page, inp["stipendio_annuo"], inp["categoria_tabella"], eta)
    assert_close(tool, sito, TOL, f"{caso_id} (eta' sito {eta})")


def test_categoria_9_una_tantum(page):
    """Piano 5: categoria '9' inesistente. Atteso piano: errore (categorie 1-8 tab. A).

    Il sito usa invece il valore 9 per l'"Indennita' una tantum" (tab. B DPR
    834/1981): calcola un importo che il tool non offre. Non confrontabile.
    """
    r = _fn(categoria_tabella="9", percentuale_invalidita=10, stipendio_annuo=25000)
    assert "errore" in r
    sito = _sito(page, 25000, "9", 30)
    pytest.skip(f"non confrontabile: il tool rifiuta la cat. 9, il sito calcola l'una tantum ({sito:.2f})")
