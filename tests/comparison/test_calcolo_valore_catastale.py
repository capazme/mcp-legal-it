"""Comparison: calcolo_valore_catastale vs avvocatoandreani.it.

Site page: calcolo-valore-catastale-immobili-asse-ereditario.php
Form fields: CategoriaCatastale (select), GiornoInizio/MeseInizio/AnnoInizio
(reference date, default today), RenditaCatastale (text),
AbitazionePrincipale (checkbox, disabled for categories where the first-home
multiplier cannot apply, e.g. A/10, B, D, E, T). Result rows:
"Rendita catastale rivalutata al 5%", "Moltiplicatore catastale",
"Valore catastale immobile" (or "Valore catastale terreno" for T).

The site computes ONE value, valid (per its notes) for inheritance tax and for
registration taxes on the "prezzo-valore" basis; it has no IMU mode (it warns
that IMU multipliers differ) and no separate "compravendita" branch.

Norms: DPR 131/1986 art. 52 co. 5-bis; D.Lgs. 346/1990 art. 34;
DL 168/2004 art. 1-bis co. 7-10; DL 262/2006 art. 2 co. 45 (gruppo B: 140).
"""

import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo-valore-catastale-immobili-asse-ereditario.php"


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers all tools)
    from src.tools.proprieta_successioni import calcolo_valore_catastale

    fn = getattr(calcolo_valore_catastale, "fn", calcolo_valore_catastale)
    return fn(**kwargs)


def _site(page, categoria, rendita, abitazione_principale=False, data=None):
    """Drive the site; return (moltiplicatore_text, valore_float)."""
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("select[name='CategoriaCatastale']", categoria)
    if data:
        g, m, a = data
        page.select_option("select[name='GiornoInizio']", g)
        page.select_option("select[name='MeseInizio']", m)
        page.select_option("select[name='AnnoInizio']", a)
    page.fill("input[name='RenditaCatastale']", rendita)
    cb = page.locator("input[name='AbitazionePrincipale']")
    if not cb.is_disabled():
        page.set_checked("input[name='AbitazionePrincipale']", abitazione_principale, force=True)
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    mv = re.search(r"Valore catastale (?:immobile|terreno)\s*€\s*([\d.,]+)", body)
    mm = re.search(r"Moltiplicatore catastale[^\t\n]*\t\s*([\d.,]+)", body)
    assert mv, "site result not found"
    return (mm.group(1) if mm else None), parse_euro(mv.group(1))


def test_a2_successione(page):
    """A/2, rendita 1.000, successione, non prima casa.
    Atteso piano: 1.000 x 1,05 x 120 = 126.000,00 (art. 52 co. 5-bis DPR 131/1986)."""
    r = _tool(rendita_catastale=1000, categoria="A/2", tipo="successione", prima_casa=False)
    molt, v = _site(page, "A/2", "1000", abitazione_principale=False)
    assert molt == "120"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="A/2 successione")


def test_a2_prima_casa_compravendita(page):
    """A/2, rendita 1.000, compravendita prima casa.
    Atteso piano: 1.000 x 1,05 x 110 = 115.500,00 (art. 52 co. 5-bis DPR 131/1986)."""
    r = _tool(rendita_catastale=1000, categoria="A/2", tipo="compravendita", prima_casa=True)
    molt, v = _site(page, "A/2", "1000", abitazione_principale=True)
    assert molt == "110"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="A/2 prima casa")


def test_a10_compravendita(page):
    """A/10, rendita 1.000, compravendita non prima casa.
    Atteso piano: 1.000 x 1,05 x 60 = 63.000,00 -- il 60 incorpora gia' il +20%
    dell'art. 1-bis DL 168/2004 (50 x 1,2); il tool aggiunge un ulteriore +20%
    (coefficiente 72 -> 75.600,00). Il sito non ha un ramo compravendita: il suo
    valore unico vale per successione e registro (prezzo-valore)."""
    r = _tool(rendita_catastale=1000, categoria="A/10", tipo="compravendita", prima_casa=False)
    molt, v = _site(page, "A/10", "1000")
    assert molt == "60"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="A/10 compravendita")


def test_a10_successione(page):
    """A/10, rendita 1.000, successione. Atteso: 1.000 x 1,05 x 60 = 63.000,00
    (art. 34 D.Lgs. 346/1990 rinvia all'art. 52 DPR 131/1986)."""
    r = _tool(rendita_catastale=1000, categoria="A/10", tipo="successione")
    molt, v = _site(page, "A/10", "1000")
    assert molt == "60"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="A/10 successione")


def test_b1_successione(page):
    """B/1, rendita 1.000, successione.
    Atteso piano: 1.000 x 1,05 x 140 = 147.000,00 (DL 262/2006 art. 2 co. 45)."""
    r = _tool(rendita_catastale=1000, categoria="B/1", tipo="successione")
    molt, v = _site(page, "B/1", "1000")
    assert molt == "140"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="B/1 successione")


def test_c1_successione(page):
    """C/1, rendita 1.000, successione.
    Atteso piano: 1.000 x 1,05 x 40,8 = 42.840,00 (art. 1-bis DL 168/2004: 34 x 1,2)."""
    r = _tool(rendita_catastale=1000, categoria="C/1", tipo="successione")
    molt, v = _site(page, "C/1", "1000")
    assert molt == "40,8"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="C/1 successione")


def test_e1_successione(page):
    """Caso al limite (gruppo E, opzione enumerata): E/1, rendita 1.000, successione.
    Atteso: 1.000 x 1,05 x 40,8 = 42.840,00 (art. 52 co. 5-bis DPR 131/1986)."""
    r = _tool(rendita_catastale=1000, categoria="E/1", tipo="successione")
    molt, v = _site(page, "E/1", "1000")
    assert molt == "40,8"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="E/1 successione")


def test_a3_rendita_decimale_arrotondamento(page):
    """Caso al limite (arrotondamento): A/3, rendita 723,45, successione.
    Atteso: 723,45 x 1,05 = 759,6225 (non arrotondata) x 120 = 91.154,70.
    Se si arrotondasse prima la rendita rivalutata (759,62) si otterrebbero 91.154,40."""
    r = _tool(rendita_catastale=723.45, categoria="A/3", tipo="successione")
    molt, v = _site(page, "A/3", "723,45", abitazione_principale=False)
    assert molt == "120"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="A/3 decimale")


def test_c2_pertinenza_prima_casa(page):
    """Caso al limite (pertinenza C/2 della prima casa, arrotondamento al mezzo centesimo):
    rendita 723,45 -> 759,6225 x 110 = 83.558,475 -> 83.558,48 (art. 52 co. 5-bis:
    il 110 si estende alle pertinenze)."""
    r = _tool(rendita_catastale=723.45, categoria="C/2", tipo="successione", prima_casa=True)
    molt, v = _site(page, "C/2", "723,45", abitazione_principale=True)
    assert molt == "110"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="C/2 prima casa")


def test_terreno_agricolo(page):
    """Caso al limite (opzione enumerata T): terreno agricolo, reddito dominicale 1.000.
    Atteso: 1.000 x 1,25 x 90 = 112.500,00 (art. 52 co. 4 DPR 131/1986; L. 662/1996).
    Il tool non gestisce i terreni e risponde con 'errore'."""
    r = _tool(rendita_catastale=1000, categoria="T", tipo="successione")
    molt, v = _site(page, "T", "1000")
    assert "errore" not in r, f"tool non calcola i terreni: {r.get('errore')} (sito: {v})"
    assert_close(r["valore_catastale"], v, tolerance=0.01, label="T terreno")


def test_d1_imu():
    """D/1, rendita 1.000, IMU. Atteso piano: 1.000 x 1,05 x 65 = 68.250,00
    (L. 160/2019 art. 1 co. 745). Non confrontabile: il sito non ha una modalita' IMU
    (avverte che i moltiplicatori IMU sono diversi e rinvia a un'altra utility)."""
    r = _tool(rendita_catastale=1000, categoria="D/1", tipo="imu")
    assert r["valore_catastale"] == 68250.0
    pytest.skip("sito senza modalita' IMU (pagina dedicata al valore per successione/registro)")


def test_e1_imu():
    """E/1, IMU. Atteso piano: errore o esenzione (gruppo E esente IMU, L. 160/2019
    art. 1 co. 759); il tool restituisce 126.000,00. Non confrontabile: il sito non ha IMU."""
    pytest.skip("sito senza modalita' IMU; il tool restituisce 126.000,00 anziche' esenzione")


def test_b1_data_storica_2005():
    """Caso al limite (anno diverso): B/1 al 15/06/2005 -- il sito applica il moltiplicatore
    storico 120 (126.000,00), prima del 140 del DL 262/2006. Il tool non ha data di
    riferimento e applica sempre il regime vigente."""
    pytest.skip("il tool non accetta una data di riferimento (sito: 120 al 15/06/2005)")
