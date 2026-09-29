"""Benchmark scadenza_processuale vs avvocatoandreani.it (calcolo_scadenze_termini_udienze.php).

Norma: art. 155 c.p.c. (dies a quo escluso; proroga al primo giorno non festivo,
sabato compreso, co. 4-5); L. 742/1969 (sospensione feriale 1-31 agosto);
L. 260/1949 come modificata dalla L. 151/2025 (4 ottobre festivo dal 2026).

Il sito e' un benchmark, non una fonte: gli scostamenti restano tali.
"""

import datetime as dt
import os
import re
import sys

os.environ["LEGAL_TODAY"] = "2026-09-25"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest  # noqa: E402

import src.server  # noqa: E402,F401
from src.tools.scadenze_termini import scadenza_processuale  # noqa: E402

from tests.comparison.conftest import accept_cookies  # noqa: E402

_fn = getattr(scadenza_processuale, "fn", scadenza_processuale)
URL = "https://www.avvocatoandreani.it/servizi/calcolo_scadenze_termini_udienze.php"


def _sito(page, data_evento: str, giorni: int, sospensione: bool) -> dt.date:
    y, m, d = data_evento.split("-")
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("select[name='GiornoInizio1']", d)
    page.select_option("select[name='MeseInizio1']", m)
    page.select_option("select[name='AnnoInizio1']", y)
    page.fill("input[name='NumeroGiorni']", str(giorni))
    page.check("input[name='PrimaDopo'][value='dopo']")
    cb = page.locator("input[name='SospensioneFeriale']").first
    if sospensione:
        cb.check()
    else:
        cb.uncheck()
    page.locator("input[name='Calcola']").first.click(force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    txt = page.inner_text("body")
    # Il sito mostra "La data di scadenza calcolata e': [Giorno] dd/mm/yyyy" e, se cade in
    # domenica o festivo, una riga "Primo giorno successivo non festivo: dd/mm/yyyy".
    mm = re.search(
        r"scadenza calcolata è:\s*(?:\w+\s+)?(\d{2})/(\d{2})/(\d{4})", txt
    )
    assert mm, f"risultato non trovato: {txt[-400:]}"
    pf = re.search(r"Primo giorno successivo non festivo:\s*(\d{2})/(\d{2})/(\d{4})", txt)
    mm = pf or mm
    page.wait_for_timeout(1500)
    return dt.date(int(mm.group(3)), int(mm.group(2)), int(mm.group(1)))


def _confronta(page, data_evento, giorni, sospensione=False, atteso=None):
    r = _fn(data_evento=data_evento, giorni=giorni, sospensione_feriale=sospensione)
    assert "errore" not in r, r
    tool = dt.date.fromisoformat(r["scadenza"])
    sito = _sito(page, data_evento, giorni, sospensione)
    if atteso:
        assert tool.isoformat() == atteso, f"tool {tool} != norma {atteso}"
    assert tool == sito, f"tool {tool} ({tool:%A}) != sito {sito} ({sito:%A})"


def test_feriale_30_giorni_da_luglio(page):
    # Piano: 2025-09-19 (21-31 luglio = 11 gg, agosto sospeso, 1-19 settembre = 19 gg).
    # Art. 155 co. 1 c.p.c.; art. 1 L. 742/1969.
    _confronta(page, "2025-07-20", 30, True, atteso="2025-09-19")


def test_feriale_dies_a_quo_in_agosto(page):
    # LIMITE (agosto). Piano: 2025-09-30, decorso differito alla fine della sospensione
    # (art. 1 L. 742/1969, secondo periodo).
    _confronta(page, "2025-08-10", 30, True, atteso="2025-09-30")


def test_scadenza_su_4_ottobre_2027(page):
    # LIMITE (festivita' nuova). Piano: 2027-10-05, il 4 ottobre 2027 e' festivo
    # (L. 151/2025 su L. 260/1949) e prorogato ex art. 155 co. 4 c.p.c.
    _confronta(page, "2027-09-04", 30, False, atteso="2027-10-05")


def test_scadenza_di_sabato(page):
    # LIMITE (sabato). Piano: 2025-06-09 per termine processuale (sabato prorogato,
    # art. 155 co. 5 c.p.c.); per termine sostanziale resterebbe 2025-06-07.
    _confronta(page, "2025-06-01", 6, False, atteso="2025-06-09")


def test_scadenza_di_domenica(page):
    # Domenica 8 giugno 2025 -> lunedi' 9 (art. 155 co. 4 c.p.c.).
    _confronta(page, "2025-06-02", 6, False, atteso="2025-06-09")


def test_scadenza_25_aprile_festivo(page):
    # 25 aprile 2025 (venerdi', festivita' nazionale) -> sabato 26 -> lunedi' 28
    # (art. 155 co. 4-5 c.p.c.).
    _confronta(page, "2025-04-20", 5, False, atteso="2025-04-28")


def test_scadenza_lunedi_dell_angelo(page):
    # Pasquetta 21 aprile 2025 -> martedi' 22 (art. 155 co. 4 c.p.c.).
    _confronta(page, "2025-04-14", 7, False, atteso="2025-04-22")


def test_ferragosto_senza_sospensione(page):
    # LIMITE (agosto senza sospensione). 15 agosto 2025 venerdi' festivo -> sabato 16
    # -> lunedi' 18 (art. 155 co. 4-5 c.p.c.).
    _confronta(page, "2025-08-01", 14, False, atteso="2025-08-18")


def test_natale_santo_stefano_sabato(page):
    # LIMITE (festivi consecutivi + sabato + domenica). 25/12 e 26/12/2025 festivi, 27 sabato,
    # 28 domenica -> lunedi' 29 dicembre (art. 155 co. 4-5 c.p.c.).
    _confronta(page, "2025-12-24", 1, False, atteso="2025-12-29")


def test_feriale_dies_a_quo_31_luglio(page):
    # LIMITE (confine sospensione). 31 luglio + 1 giorno con sospensione: agosto non si conta,
    # 1 settembre 2025 (lunedi') (art. 1 L. 742/1969).
    _confronta(page, "2025-07-31", 1, True, atteso="2025-09-01")


def test_anno_bisestile(page):
    # LIMITE (29 febbraio). 28/02/2028 + 2 gg = 01/03/2028 (2028 bisestile).
    _confronta(page, "2028-02-28", 2, False, atteso="2028-03-01")


def test_cambio_anno_epifania_non_toccata(page):
    # LIMITE (cambio anno). 20/12/2025 + 15 = domenica 04/01/2026 -> lunedi' 05/01/2026.
    _confronta(page, "2025-12-20", 15, False, atteso="2026-01-05")


def test_4_ottobre_2028_feriale(page):
    # LIMITE (4 ottobre in giorno feriale, mercoledi'). Norma: festivo dal 2026 (L. 151/2025)
    # -> 2028-10-05 (art. 155 co. 4 c.p.c.).
    _confronta(page, "2028-09-04", 30, False, atteso="2028-10-05")


def test_lavorativi_non_confrontabile(page):
    # Piano: 2025-04-28 (giorni utili 18, 22, 23, 24, 28 aprile). Il sito non offre il
    # conteggio a giorni lavorativi: solo aritmetica sul tool.
    r = _fn(data_evento="2025-04-17", giorni=5, tipo="lavorativi")
    assert r["scadenza"] == "2025-04-28"
    pytest.skip("il sito non offre l'opzione giorni lavorativi (solo giorni di calendario)")


# Benchmark phase 3 verdicts (2026-09-29). The failing cases below are site deviations, not tool errors.
# - Saturday: art. 155 co. 5 c.p.c. extends the co. 4 proroga to procedural acts done outside the
#   hearing that expire on a Saturday; the site treats Saturday as a working day (site wrong).
# - 4 October: L. 151/2025 art. 1 co. 2 adds it to art. 2 L. 260/1949 (national holiday from 2026);
#   the tool applies it via festivita.json (dal_anno 2026), the site does not (site wrong).
