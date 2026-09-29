"""Benchmark termini_esecuzioni (termini del precetto) contro avvocatoandreani.it.

Pagina indicata dal piano: /servizi/calcolo-termini-esecuzioni.php. Quella pagina NON calcola i
termini del precetto: calcola i termini successivi al pignoramento (iscrizione a ruolo artt. 518,
543, 557, 521-bis; istanza di vendita art. 497), quindi non e' confrontabile col tool.
Il riscontro utile e' la pagina secondaria /servizi/calcolo-termini-processuali-civili.php, che
espone le voci "481 cpc: Cessazione efficacia del precetto (90 giorni)" e "617 cpc: Termini per
opposizione agli atti esecutivi (20 giorni)" oltre a un termine manuale in giorni.

Convenzioni: il sito proroga i termini che cadono di sabato/domenica/festivo (art. 155 c.p.c.),
come il tool; la sospensione feriale e' una spunta del sito ("SospensioneFeriale") e il tool non la
applica mai (art. 3 L. 742/1969: opposizioni esecutive escluse; termine ex art. 481 sostanziale).
Per questo i confronti si fanno con la sospensione feriale DISATTIVATA.
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import re
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import src.server  # noqa: F401,E402  (registra i moduli)
from src.tools.scadenze_termini import termini_esecuzioni  # noqa: E402

from tests.comparison.conftest import accept_cookies, goto  # noqa: E402

_fn = getattr(termini_esecuzioni, "fn", termini_esecuzioni)

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_ID_481 = "72"  # 481 cpc: Cessazione efficacia del precetto (90 giorni)
_ID_617 = "87"  # 617 cpc: Termini per opposizione agli atti esecutivi (20 giorni)


def _sito(page, dies_a_quo: str, id_termine: str | None = None, giorni_manuali: int | None = None,
          sospensione_feriale: bool = False) -> date:
    """Guida la pagina dei termini processuali civili e ritorna 'Termine ultimo'."""
    goto(page, "calcolo-termini-processuali-civili.php")
    accept_cookies(page)
    y, m, g = dies_a_quo.split("-")
    page.select_option("#GiornoInizio", g)
    page.select_option("#MeseInizio", m)
    page.select_option("#AnnoInizio", y)
    if giorni_manuali is not None:
        page.select_option("#TipoTermine", "1")
        page.fill("#Termine1", str(giorni_manuali))
    else:
        page.select_option("#IdTermine", id_termine)
    page.evaluate(
        "document.getElementById('SospensioneFeriale').checked = %s"
        % ("true" if sospensione_feriale else "false")
    )
    with page.expect_navigation(timeout=20000, wait_until="domcontentloaded"):
        page.evaluate(
            "document.getElementById('Termini').requestSubmit(document.querySelector('input[name=Op]'))"
        )
    page.wait_for_timeout(1500)
    text = page.inner_text("body")
    mt = re.search(r"Termine ultimo:\s*\w+\s+(\d+)\S*\s+(\w+)\s+(\d{4})", text)
    assert mt, f"Termine ultimo non trovato: {text[:500]!r}"
    d = date(int(mt.group(3)), _MESI[mt.group(2).lower()], int(mt.group(1)))
    page.wait_for_timeout(1500)  # cortesia verso il sito
    return d


def _tool(data: str, tipo: str) -> dict:
    r = _fn(data_notifica_titolo=data, tipo=tipo)
    assert "errore" not in r, r
    return r


def _efficacia(data: str, tipo: str = "pignoramento_mobiliare") -> date:
    return date.fromisoformat(_tool(data, tipo)["scadenza_efficacia_precetto"]["data"])


def _opposizione(data: str) -> date:
    return date.fromisoformat(_tool(data, "opposizione_esecuzione")["scadenza_opposizione"])


# ---------------------------------------------------------------- efficacia del precetto (art. 481)

def test_efficacia_precetto_sabato_prorogato(page):
    """Piano: notifica 2025-06-01, il 90 giorno e' sabato 2025-08-30 -> tool 2025-09-01 (art. 481 +
    art. 155 co. 5). Sito senza sospensione feriale: lunedi 1 settembre 2025."""
    assert _efficacia("2025-06-01") == _sito(page, "2025-06-01", _ID_481)


def test_efficacia_precetto_santo_stefano_marzo(page):
    """Piano: notifica 2025-12-16 -> efficacia 2026-03-16 (lunedi) (art. 481)."""
    assert _efficacia("2025-12-16", "pignoramento_presso_terzi") == _sito(page, "2025-12-16", _ID_481)


def test_efficacia_precetto_ferragosto_limite(page):
    """LIMITE (festivita' + sabato): notifica 2025-05-17, il 90 giorno e' venerdi 15 agosto
    (Assunzione), poi sabato 16 -> lunedi 2025-08-18 (art. 481, art. 155 co. 4-5)."""
    assert _efficacia("2025-05-17") == _sito(page, "2025-05-17", _ID_481)


def test_efficacia_precetto_attraversa_anno_epifania_limite(page):
    """LIMITE (anno diverso): notifica 2025-10-08, il 90 giorno e' martedi 6 gennaio 2026
    (Epifania) -> 2026-01-07 (art. 481, art. 155 co. 4)."""
    assert _efficacia("2025-10-08", "pignoramento_immobiliare") == _sito(page, "2025-10-08", _ID_481)


def test_efficacia_precetto_pasqua_2024_limite(page):
    """LIMITE (anno bisestile + Pasqua): notifica 2024-01-01, il 90 giorno e' domenica 31 marzo
    2024 (Pasqua), lunedi 1 aprile Pasquetta -> martedi 2024-04-02 (art. 481, art. 155)."""
    assert _efficacia("2024-01-01") == _sito(page, "2024-01-01", _ID_481)


def test_efficacia_precetto_tutti_i_tipi_enumerati(page):
    """Opzioni enumerate: i tre tipi di pignoramento condividono il termine di 90 giorni (art. 481).
    Notifica 2026-03-10 -> 2026-06-08 (lunedi). Il sito ha una sola voce (481)."""
    atteso = _sito(page, "2026-03-10", _ID_481)
    for tipo in ("pignoramento_mobiliare", "pignoramento_immobiliare", "pignoramento_presso_terzi"):
        assert _efficacia("2026-03-10", tipo) == atteso, tipo


# ------------------------------------------------- opposizione agli atti esecutivi (art. 617, 20 gg)

def test_opposizione_atti_esecutivi_sabato(page):
    """Piano: notifica 2025-06-01 -> 2025-06-23: 20 giorni, il 21 giugno e' sabato (art. 617 co. 1,
    art. 155 co. 5)."""
    assert _opposizione("2025-06-01") == _sito(page, "2025-06-01", _ID_617)


def test_opposizione_attraversa_agosto_senza_sospensione_limite(page):
    """LIMITE (agosto). Piano: notifica 2025-07-20 -> 2025-08-11 senza sospensione feriale
    (art. 3 L. 742/1969, art. 92 R.D. 12/1941), il 9 agosto e' sabato. Sito con sospensione OFF:
    lunedi 11 agosto 2025."""
    assert _opposizione("2025-07-20") == _sito(page, "2025-07-20", _ID_617)


def test_opposizione_pasquetta_limite(page):
    """LIMITE (festivita' mobile): notifica 2025-04-01, il 20 giorno e' lunedi 21 aprile 2025
    (Pasquetta) -> martedi 2025-04-22 (art. 617, art. 155 co. 4)."""
    assert _opposizione("2025-04-01") == _sito(page, "2025-04-01", _ID_617)


def test_opposizione_natale_santo_stefano_sabato_limite(page):
    """LIMITE (festivita' + sabato): notifica 2025-12-05, il 20 giorno e' giovedi 25 dicembre,
    26 festivo, 27 sabato -> lunedi 2025-12-29 (art. 617, art. 155)."""
    assert _opposizione("2025-12-05") == _sito(page, "2025-12-05", _ID_617)


# ------------------------------------------------ termine dilatorio (art. 482), solo aritmetica

def test_dilatorio_10_giorni_aritmetica(page):
    """Il sito non ha una voce per l'art. 482; si usa il termine manuale di 10 giorni (aritmetica
    +10 con proroga). Piano: notifica 2025-06-01, il tool apre la finestra il 2025-06-11 (il piano
    nota che giuridicamente il pignoramento e' eseguibile dall'undicesimo giorno, 2025-06-12: e'
    una questione di norma, non di confronto col sito)."""
    d = date.fromisoformat(_tool("2025-06-01", "pignoramento_mobiliare")["termine_minimo_10gg"]["data"])
    assert d == _sito(page, "2025-06-01", giorni_manuali=10)


def test_dilatorio_10_giorni_santo_stefano_limite(page):
    """LIMITE. Piano: notifica 2025-12-16, dieci giorni al 26 dicembre (festivo): il tool indica
    2025-12-29 (26 festivo, 27 sabato). Il piano ritiene che per un termine dilatorio la proroga
    non serva (eseguibile da sabato 27/12): il sito, con termine manuale, proroga come un termine
    ordinario. Si confronta il tool con l'aritmetica del sito."""
    d = date.fromisoformat(_tool("2025-12-16", "pignoramento_presso_terzi")["termine_minimo_10gg"]["data"])
    assert d == _sito(page, "2025-12-16", giorni_manuali=10)


# ------------------------------------------------------------------------------ non confrontabili

def test_sospensione_feriale_attiva_non_confrontabile(page):
    """Il sito consente di attivare la sospensione feriale (con notifica 2025-07-20 l'opposizione
    dell'art. 617 diventa 2025-09-09; l'efficacia ex art. 481 del 2025-06-01 diventa 2025-09-30);
    il tool non ha il parametro e la esclude per legge (art. 3 L. 742/1969). Registrare i valori
    del sito ma non asserire uguaglianza."""
    sito = _sito(page, "2025-07-20", _ID_617, sospensione_feriale=True)
    pytest.skip(f"Il tool non applica mai la sospensione feriale (opposizioni esecutive escluse); "
                f"il sito con spunta attiva restituisce {sito.isoformat()}, tool {_opposizione('2025-07-20')}")


def test_pagina_primaria_termini_post_pignoramento_non_confrontabile():
    """calcolo-termini-esecuzioni.php calcola iscrizione a ruolo (15/30/45 gg, artt. 518, 521-bis,
    543, 557) e istanza di vendita (art. 497) dalla data del pignoramento; il tool calcola
    dilatorio (art. 482), efficacia del precetto (art. 481) e opposizione (art. 617)."""
    pytest.skip("La pagina primaria calcola termini diversi (post-pignoramento): nessun output "
                "corrisponde a quelli del tool")


# CONVENTION (phase 2-3): the failing cases are a deadline that art. 155 co. 4 moves from a
# holiday (15/8, 26/12) onto a Saturday. Co. 5 extends only terms that "scadono nella giornata del
# sabato" and co. 6 makes Saturday a working day, so whether the extended date needs a second
# extension is not settled by the text. The tool goes to Monday, the site stops on Saturday.
# Not decidable from the primary source: no change. Art. 482 (10 days) is a dilatory term whose
# reading (last day vs first day to execute) is also open.
