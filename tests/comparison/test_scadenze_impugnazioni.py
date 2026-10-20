"""Benchmark scadenze_impugnazioni vs avvocatoandreani.it.

Pagina: /servizi/termini-impugnazioni-civile-amministrativo-tributario.php
(processo Civile, sospensione feriale spuntata di default).
Norme: artt. 325-327 c.p.c. (termine breve 30/60 gg dalla notifica, lungo 6 mesi
dalla pubblicazione), art. 155 co. 4-5 c.p.c. (proroga festivo/sabato),
L. 742/1969 (sospensione feriale 1-31 agosto), art. 47 c.p.c.
Tolleranza: data esatta (nessun margine).
"""
import os

os.environ["LEGAL_TODAY"] = "2026-09-25"

import re
from datetime import date

import pytest

import src.server  # noqa: F401  (registra i moduli)
from src.tools.scadenze_termini import scadenze_impugnazioni
from tests.comparison.conftest import accept_cookies

URL = "https://www.avvocatoandreani.it/servizi/termini-impugnazioni-civile-amministrativo-tributario.php"
_fn = getattr(scadenze_impugnazioni, "fn", scadenze_impugnazioni)
_IMP = {"appello_sentenza": "1", "cassazione": "2", "revocazione": "3", "opposizione_terzo": "4"}
_MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
         "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}


def _tool(data, tipo, notificata, sosp=True):
    r = _fn(data_pubblicazione=data, tipo_impugnazione=tipo, notificata=notificata,
            sospensione_feriale=sosp)
    assert "errore" not in r, r
    return r["scadenza"]


def _sito(page, data, tipo, decorrenza, sosp=True):
    """decorrenza: 1 notifica, 2 pubblicazione, 3 scoperta dei vizi."""
    page.goto(URL, wait_until="domcontentloaded")
    accept_cookies(page)
    y, m, d = data.split("-")
    page.select_option("#Impugnazione", _IMP[tipo])
    page.select_option("#Decorrenza", str(decorrenza))
    page.select_option("#GiornoInizio", d)
    page.select_option("#MeseInizio", m)
    page.select_option("#AnnoInizio", y)
    page.set_checked("#SospensioneFeriale", sosp)
    page.click("#button1", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    txt = page.inner_text("body")
    mt = re.search(r"Termine ultimo:\s*\w+\s+(\d+)\S*\s+(\w+)\s+(\d{4})", txt)
    assert mt, "risultato non trovato: " + txt[-600:]
    out = date(int(mt.group(3)), _MESI[mt.group(2).lower()], int(mt.group(1))).isoformat()
    page.wait_for_timeout(1500)
    return out


def _confronta(page, data, tipo, notificata, decorrenza, sosp=True):
    t = _tool(data, tipo, notificata, sosp)
    s = _sito(page, data, tipo, decorrenza, sosp)
    assert t == s, f"tool={t} sito={s}"


def test_appello_breve_attraversa_agosto(page):
    # Piano: 2025-09-19 (30 gg dalla notifica, art. 325 co. 1; 11 luglio + 19 settembre)
    _confronta(page, "2025-07-20", "appello_sentenza", True, 1)


def test_appello_lungo_agosto_e_festivo(page):
    # Piano: 2026-01-02 (6 mesi art. 327 -> 2025-12-01, +31 gg sosp. = 1 gen festivo, art. 155 co. 4)
    _confronta(page, "2025-06-01", "appello_sentenza", False, 2)


def test_cassazione_lungo_pubblicazione_agosto(page):
    # Piano: tool 2028-02-29 (decorrenza dal 31 agosto); lettura dal 1 settembre = 2028-03-01.
    # Riportare entrambe: qui si asserisce tool == sito.
    _confronta(page, "2027-08-10", "cassazione", False, 2)


def test_cassazione_breve_domenica(page):
    # Piano: 2025-09-15 (60 gg, art. 325 co. 2; 14 set domenica, proroga al lunedi 15)
    _confronta(page, "2025-06-15", "cassazione", True, 1)


def test_regolamento_competenza_non_confrontabile(page):
    # Piano: 2025-09-09 (30 gg, art. 47 co. 2 c.p.c.). Il sito non offre il regolamento di competenza.
    assert _tool("2025-07-10", "regolamento_competenza", True) == "2025-09-09"
    pytest.skip("il sito non offre il regolamento di competenza tra le impugnazioni")


def test_revocazione_breve(page):
    # Art. 326 / 325 co. 1: 30 gg dalla notifica, 2025-09-19 attraversando agosto
    _confronta(page, "2025-07-20", "revocazione", True, 1)


def test_revocazione_lungo_pubblicazione(page):
    # Art. 327: 6 mesi da 2025-03-10 = 10 set + 31 gg sosp. = 11 ott sab -> lunedi 13 ott (art. 155 co. 5)
    _confronta(page, "2025-03-10", "revocazione", False, 2)


def test_opposizione_terzo_scoperta_dolo(page):
    # Art. 404 co. 2 / 326: 30 gg dalla scoperta del dolo; 2025-03-10 -> 2025-04-09.
    # Il tool la chiama con notificata=True; il sito usa "Scoperta dei vizi".
    _confronta(page, "2025-03-10", "opposizione_terzo", True, 3)


def test_opposizione_terzo_senza_termine_non_confrontabile(page):
    # Con notificata=False il tool restituisce null (art. 404 co. 1: nessun termine);
    # il sito offre solo "Scoperta dei vizi" e calcola comunque 30 gg.
    assert _tool("2025-03-10", "opposizione_terzo", False) is None
    pytest.skip("il sito calcola sempre 30 gg da scoperta dei vizi, il tool non ha termine lungo")


def test_limite_notifica_in_agosto(page):
    # Limite: decorrenza nel periodo di sospensione (5 agosto): il termine riparte dal 1 settembre -> 30 set
    _confronta(page, "2025-08-05", "appello_sentenza", True, 1)


def test_limite_notifica_31_luglio(page):
    # Limite: ultimo giorno prima della sospensione; 30 gg tutti dopo agosto -> 2025-09-30
    _confronta(page, "2025-07-31", "appello_sentenza", True, 1)


def test_limite_senza_sospensione_feriale(page):
    # Sospensione disattivata: 30 gg secchi, 2025-07-20 -> 2025-08-19
    _confronta(page, "2025-07-20", "appello_sentenza", True, 1, sosp=False)


def test_limite_lungo_senza_sospensione(page):
    # Termine lungo senza sospensione: 6 mesi da 2025-06-01 = 2025-12-01 (art. 327)
    _confronta(page, "2025-06-01", "appello_sentenza", False, 2, sosp=False)


def test_limite_lungo_fine_febbraio(page):
    # Limite: 28 feb + 6 mesi = 28 ago (in sospensione) + 31 gg = 28 set (dom) -> lunedi 29 set
    _confronta(page, "2025-02-28", "appello_sentenza", False, 2)


def test_limite_pubblicazione_31_agosto(page):
    # Convenzione agosto: dal 31 agosto -> 2028-02-29 (anno bisestile)
    _confronta(page, "2027-08-31", "cassazione", False, 2)


def test_limite_pubblicazione_1_settembre(page):
    # Convenzione agosto: dal 1 settembre -> 2028-03-01
    _confronta(page, "2027-09-01", "cassazione", False, 2)


def test_limite_cassazione_breve_agosto(page):
    # Art. 325 co. 2: 60 gg dalla notifica del 10 agosto 2025 (in sospensione) -> riparte 1 settembre
    _confronta(page, "2025-08-10", "cassazione", True, 1)
