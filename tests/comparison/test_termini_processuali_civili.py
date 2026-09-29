"""Comparison: termini_processuali_civili vs avvocatoandreani.it
(calcolo-termini-memorie-integrative-comparse-repliche.php, buttons "Memorie Integrative 171-ter"
and "Note Comparse e Repliche 189").

Norma: art. 171-ter co. 1 c.p.c. (memorie 40/20/10 giorni prima dell'udienza ex art. 183) e
art. 189 co. 1 c.p.c. (note 60, comparsa conclusionale 30, replica 15 giorni prima dell'udienza di
rimessione in decisione), D.Lgs. 149/2022; L. 742/1969 (sospensione feriale 1-31 agosto);
art. 155 c.p.c. (scadenza a ritroso in giorno festivo anticipata: convenzione prudenziale).

Site notes: the submit button does not react to a plain click in headless mode, so the form
is submitted with requestSubmit() on the real button. The site returns the three terms of the
group at once; the tool returns one term plus the group summary, so each test compares the
requested term (and the summary). The hidden "Sospensione straordinaria" checkbox is left at
its default (no effect on 2025-2027 dates).

Tolerance: dates must match exactly.
"""

import os
import re
import sys

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: E402,F401  (registers all tool modules)
from src.tools.scadenze_termini import termini_processuali_civili  # noqa: E402

from .conftest import goto  # noqa: E402

PAGE = "calcolo-termini-memorie-integrative-comparse-repliche.php"

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_DATE = r"\(\d+ giorni prima del[^)]*\)\s*\w+ (\d{1,2}) (\w+) (\d{4})"
_LABELS = {
    "button1": {
        "memoria_I": "Termine per la prima memoria integrativa:",
        "memoria_II": "Termine per la seconda memoria integrativa:",
        "memoria_III": "Termine per la terza memoria integrativa:",
    },
    "button2": {
        "note_conclusioni": "Termine per le note di precisazione delle conclusioni:",
        "comparsa_conclusionale": "Termine per la comparsa conclusionale:",
        "replica": "Termine per la memoria di replica:",
    },
}
_BTN = {
    "memoria_I": "button1", "memoria_II": "button1", "memoria_III": "button1",
    "note_conclusioni": "button2", "comparsa_conclusionale": "button2", "replica": "button2",
}


def _tool(data_udienza, tipo, feriale=True, giorni=None):
    fn = getattr(termini_processuali_civili, "fn", termini_processuali_civili)
    r = fn(data_udienza=data_udienza, tipo_termine=tipo, sospensione_feriale=feriale, giorni=giorni)
    assert "errore" not in r, r
    riep = r.get("riepilogo_termini_memorie") or r.get("riepilogo_termini_decisione")
    return r["scadenza"], riep


def _site(page, data_udienza, tipo, feriale=True):
    y, m, d = data_udienza.split("-")
    btn = _BTN[tipo]
    goto(page, PAGE)
    page.select_option("#GiornoInizio", d)
    page.select_option("#MeseInizio", m)
    page.select_option("#AnnoInizio", y)
    page.evaluate("f => document.getElementById('SospensioneFeriale').checked = f", feriale)
    page.evaluate(
        f"document.getElementById('TerminiIntegrativeRepliche')"
        f".requestSubmit(document.getElementById('{btn}'))"
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body").replace("\xa0", " ")
    out = {}
    for key, label in _LABELS[btn].items():
        mt = re.search(re.escape(label) + r"\s*" + _DATE, text)
        assert mt, f"site row missing: {label}"
        dd, mm, yy = mt.groups()
        out[key] = f"{int(yy):04d}-{_MESI[mm.lower()]:02d}-{int(dd):02d}"
    page.wait_for_timeout(1000)
    return out


def _confronta(page, data_udienza, tipo, feriale=True):
    scad, riep = _tool(data_udienza, tipo, feriale)
    site = _site(page, data_udienza, tipo, feriale)
    assert scad == site[tipo], f"{tipo} {data_udienza} feriale={feriale}: tool={scad} sito={site[tipo]}"
    assert riep == site, f"riepilogo {data_udienza} feriale={feriale}: tool={riep} sito={site}"
    return scad, riep


def test_memoria_I_attraverso_agosto(page):
    # Piano: 2025-07-22 (30 giorni in settembre, agosto escluso, 10 in luglio; art. 171-ter n. 1;
    # L. 742/1969); riepilogo memoria_II 2025-09-11, memoria_III 2025-09-19.
    scad, riep = _confronta(page, "2025-10-01", "memoria_I")
    assert scad == "2025-07-22"
    assert riep == {"memoria_I": "2025-07-22", "memoria_II": "2025-09-11", "memoria_III": "2025-09-19"}


def test_memoria_I_scadenza_di_domenica(page):
    # Piano: 2025-07-04 (40 giorni a ritroso = domenica 6/7, anticipato al venerdi; se il sito
    # prorogasse in avanti darebbe 2025-07-07). Caso al limite: convenzione festivo.
    scad, _ = _confronta(page, "2025-09-15", "memoria_I")
    assert scad == "2025-07-04"


def test_comparsa_conclusionale_attraverso_agosto(page):
    # Piano: 2026-07-22 (20 giorni in settembre, agosto escluso, 10 in luglio; art. 189 n. 2);
    # riepilogo note_conclusioni 2026-06-22, replica 2026-09-04.
    scad, riep = _confronta(page, "2026-09-21", "comparsa_conclusionale")
    assert scad == "2026-07-22"
    assert riep["note_conclusioni"] == "2026-06-22" and riep["replica"] == "2026-09-04"


def test_replica_15_giorni_domenica(page):
    # Piano: 2026-09-04 (15 giorni a ritroso = domenica 6/9, anticipato a venerdi 4; art. 189
    # n. 3). Caso al limite: convenzione festivo.
    scad, _ = _confronta(page, "2026-09-21", "replica")
    assert scad == "2026-09-04"


def test_note_conclusioni_60_giorni_attraverso_agosto(page):
    # Art. 189 n. 1 (60 giorni): a ritroso da 2026-09-21 il termine attraversa tutto agosto.
    # Caso al limite: termine piu' lungo, sospensione feriale incidente.
    _confronta(page, "2026-09-21", "note_conclusioni")


def test_comparsa_senza_sospensione_feriale(page):
    # Materia esclusa dalla sospensione (art. 3 L. 742/1969). Caso al limite: opzione enumerata
    # (checkbox). 30 giorni prima del 2026-09-21 e' sabato 22/8, anticipato a venerdi 21/8.
    scad, _ = _confronta(page, "2026-09-21", "comparsa_conclusionale", feriale=False)
    assert scad == "2026-08-21"


def test_memoria_III_udienza_1_settembre(page):
    # Caso al limite: udienza 2026-09-01, agosto interamente a ridosso dell'udienza; le memorie
    # da 40 e 20 giorni attraversano la sospensione, quella da 10 la sfiora (L. 742/1969).
    _confronta(page, "2026-09-01", "memoria_II")


def test_memoria_I_cavallo_di_anno(page):
    # Caso al limite: udienza 2027-01-15, a ritroso 40 giorni attraversano il 25/12 e il 1/1
    # (festivita) e il confine d'anno; art. 155 c.p.c.
    _confronta(page, "2027-01-15", "memoria_I")


def test_termine_giudice_giorni_20(page):
    # Piano: 2026-09-01 (20 giorni a ritroso senza sospensione; art. 189 fissa solo i massimi).
    pytest.skip("non_confrontabile: il sito non ha un campo per il termine piu' breve assegnato dal giudice")
