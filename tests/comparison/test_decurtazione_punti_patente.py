"""Benchmark decurtazione_punti_patente vs avvocatoandreani.it (tabella punti patente).

Il sito non e' un calcolatore: pubblica la tabella allegata all'art. 126-bis
D.Lgs. 285/1992 (aggiornata alla L. 177/2024), consultabile per punteggio o per
ricerca testuale. Le 8 tabelle per punteggio (10, 8, 6, 5, 4, 3, 2, 1) vengono
lette una sola volta e i punti del tool si confrontano voce per voce, agganciando
la riga del sito per articolo e comma. Le voci a 0 punti non compaiono nella
tabella del sito: per il confronto "assente dalla tabella" equivale a 0 punti.
Sanzioni pecuniarie/accessorie non sono pubblicate dal sito: non confrontabili.
"""

import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

import src.server  # noqa: F401  (registra i moduli)
from src.tools.varie import decurtazione_punti_patente

from tests.comparison.conftest import accept_cookies

_fn = getattr(decurtazione_punti_patente, "fn", decurtazione_punti_patente)
URL = "https://www.avvocatoandreani.it/servizi/tabella-decurtazione-punti-patente.php"
PUNTEGGI = ["10", "8", "6", "5", "4", "3", "2", "1"]
_ROW = re.compile(r"^(.*?) (\d{1,2}) (art\. \d+.*)$")


@pytest.fixture(scope="module")
def sito(browser):
    """Righe (descrizione, punti, articolo) della tabella del sito, tutti i punteggi."""
    ctx = browser.new_context(locale="it-IT")
    pg = ctx.new_page()
    righe = []
    try:
        for p in PUNTEGGI:
            pg.goto(URL, timeout=60000, wait_until="domcontentloaded")
            pg.wait_for_timeout(1500)
            accept_cookies(pg)
            pg.select_option("select[name='idmenu']", label=p)
            pg.wait_for_timeout(2500)
            testi = pg.eval_on_selector_all(
                "tr", "els=>els.map(e=>e.innerText.replace(/\\s+/g,' ').trim())"
            )
            for t in testi:
                m = _ROW.match(t)
                if m and int(m.group(2)) == int(p):
                    righe.append((m.group(1), int(m.group(2)), m.group(3)))
    finally:
        pg.close()
        ctx.close()
    assert len(righe) > 100, "tabella del sito non letta"
    return righe


def _punti_sito(sito, pattern):
    """Insieme dei punti delle righe del sito il cui articolo corrisponde a pattern."""
    rx = re.compile(pattern)
    return sorted({p for (_d, p, art) in sito if rx.search(art)})


# chiave del tool -> (regex sull'articolo del sito, riferimento normativo)
VOCI = {
    # Art. 173 c.3-bis primo periodo (L. 177/2024): 5 punti
    "cellulare": (r"^art\. 173, comma 3 bis, primo periodo", "art. 173 c.3-bis"),
    "cintura": (r"^art\. 172, comma 1[01]$", "art. 172 c.10-11"),
    "semaforo_rosso": (r"^art\. 146, comma 3$", "art. 146 c.3"),
    "eccesso_velocita_10": (r"^art\. 142, comma 7$", "art. 142 c.7 (0 punti)"),
    "eccesso_velocita_40": (r"^art\. 142, comma 8$", "art. 142 c.8"),
    "eccesso_velocita_60": (r"^art\. 142, comma 9$", "art. 142 c.9"),
    "eccesso_velocita_oltre_60": (r"^art\. 142, comma 9 bis$", "art. 142 c.9-bis"),
    "guida_ebbra": (r"^art\. 186, comma 2 e 7", "art. 186 c.2 e 7"),
    "sorpasso": (r"^art\. 148, comma 15 con riferimento al comma 2$", "art. 148 c.15/c.2"),
    "precedenza": (r"^art\. 145, comma 10$", "art. 145 c.10"),
    "stop": (r"^art\. 145, comma 5$", "art. 145 c.5"),
    "contromano": (r"^art\. 143, comma 11$", "art. 143 c.11"),
    "contromano_curve_dossi": (r"^art\. 143, comma 12$", "art. 143 c.12"),
    "strisce_pedonali": (r"^art\. 191, comma 1$", "art. 191 c.1"),
    "distanza_sicurezza": (r"^art\. 149, comma 4$", "art. 149 c.4"),
    "distanza_sicurezza_collisione": (r"^art\. 149, comma 5, secondo periodo", "art. 149 c.5"),
    "distanza_sicurezza_lesioni": (r"^art\. 149, comma 6$", "art. 149 c.6"),
    "casco": (r"^art\. 171, comma 2$", "art. 171 c.2"),
    "fuga_incidente": (r"^art\. 189, comma 6$", "art. 189 c.6"),
    "fuga_incidente_cose": (r"^art\. 189, comma 5 primo periodo", "art. 189 c.5"),
    "patente_scaduta": (r"^art\. 126\b", "art. 126 (0 punti)"),
    "revisione_scaduta": (r"^art\. 80\b", "art. 80 (0 punti)"),
    "assicurazione": (r"^art\. 193\b", "art. 193 c.2"),
}


def _confronta(sito, chiave):
    pattern, rif = VOCI[chiave]
    r = _fn(violazione=chiave)
    assert "errore" not in r, r
    dal_sito = _punti_sito(sito, pattern) or [0]  # assente dalla tabella = 0 punti
    assert [r["punti"]] == dal_sito, (
        f"{chiave} ({rif}): tool={r['punti']} punti, sito={dal_sito} punti"
    )


# --- casi del piano -------------------------------------------------------

def test_velocita_oltre_60(sito):
    # Piano: 10 punti (art. 142 c.9-bis, tabella art. 126-bis). Sanzioni: non sul sito.
    _confronta(sito, "eccesso_velocita_oltre_60")


def test_ricerca_velocita_quattro_fasce(sito):
    # Piano: quattro voci co.7 (0), co.8 (3), co.9 (6), co.9-bis (10).
    # Il sito non elenca il co.7 (0 punti): si confrontano le voci con punti > 0
    # dell'art. 142 e si verifica che il co.7 sia assente dalla tabella.
    r = _fn(violazione="velocita")
    voci = {v["violazione"]: v["punti"] for v in r["risultati"] if "Art. 142" in v["articolo"]}
    assert len(voci) == 4, voci
    tool_punti = sorted(p for p in voci.values() if p > 0)
    sito_punti = sorted(p for (_d, p, art) in sito if re.match(r"^art\. 142, comma (8|9|9 bis)$", art))
    assert tool_punti == sito_punti, (tool_punti, sito_punti)
    assert voci["eccesso_velocita_10"] == 0
    assert _punti_sito(sito, r"^art\. 142, comma 7$") == []


def test_cellulare(sito):
    # Piano: 5 punti (art. 173 c.3-bis nel testo L. 177/2024). Il sito distingue
    # 5 punti (primo periodo) da 10 (recidiva nel biennio, secondo periodo).
    _confronta(sito, "cellulare")


def test_cellulare_recidiva_biennio(sito):
    # Caso al limite: L. 177/2024 art. 173 c.3-bis secondo periodo, recidiva nel
    # biennio = 10 punti sul sito. Il tool ha una sola voce 'cellulare' a 5 punti.
    r = _fn(violazione="cellulare")
    sito_punti = _punti_sito(sito, r"^art\. 173, comma 3 bis")
    assert sito_punti == [5, 10], sito_punti
    assert sorted({r["punti"]}) == sito_punti, (
        f"tool espone solo {r['punti']} punti, il sito anche 10 punti per la recidiva biennale"
    )


def test_precedenza_e_stop(sito):
    # Piano: precedenza 5 (art. 145 c.10), stop 6 (art. 145 c.5).
    _confronta(sito, "precedenza")
    _confronta(sito, "stop")


def test_violazione_assente_monopattino(page):
    # Piano: 'monopattino' non trovata -> errore con elenco chiavi. Sito: la
    # ricerca testuale non restituisce alcuna riga di violazione (il messaggio
    # "Nessuna violazione trovata!" non e' stabile: compare solo in alcune sessioni).
    r = _fn(violazione="monopattino")
    assert "errore" in r and "violazioni_disponibili" in r
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("input[name='Ricerca']", "monopattino")
    page.click("input[name=CERCA]", force=True)
    page.wait_for_timeout(2500)
    righe = page.eval_on_selector_all(
        "tr", "els=>els.map(e=>e.innerText.replace(/\\s+/g,' ').trim())"
    )
    assert not [t for t in righe if _ROW.match(t)], righe


# --- casi al limite / copertura completa -----------------------------------

@pytest.mark.parametrize(
    "chiave",
    [
        # confini tra fasce di velocita': 0 / 3 / 6 / 10 punti (art. 142 c.7, 8, 9, 9-bis)
        "eccesso_velocita_10",
        "eccesso_velocita_40",
        "eccesso_velocita_60",
        # sorpasso (c.15 rif. c.2) e distanza: ipotesi base vs aggravate
        "sorpasso",
        "distanza_sicurezza",
        "distanza_sicurezza_collisione",
        "distanza_sicurezza_lesioni",
        # contromano base vs curva/dosso
        "contromano",
        "contromano_curve_dossi",
        # fuga: sole cose (c.5) vs persone (c.6)
        "fuga_incidente_cose",
        "fuga_incidente",
        "cintura",
        "semaforo_rosso",
        "guida_ebbra",
        "strisce_pedonali",
        "casco",
        # voci a 0 punti: assenti dalla tabella del sito
        "patente_scaduta",
        "revisione_scaduta",
        # art. 193 c.2: il tool assegna 5 punti; il sito non ha alcuna riga art. 193
        "assicurazione",
    ],
)
def test_punti_per_voce(sito, chiave):
    _confronta(sito, chiave)
