"""Comparison: termini_separazione_divorzio vs avvocatoandreani.it

Pagina indicata dal piano: calcolo-termini-separazione-divorzio.php. Quella pagina NON calcola la
durata della separazione: calcola le memorie dell'art. 473-bis.17 c.p.c. e gli atti dell'art.
473-bis.28 c.p.c. (campi: data udienza, sospensioni; risultati: "Termine per la prima memoria
dell'attore" ecc.), cioe' un'aritmetica a ritroso che il tool non esegue. Nessun confronto diretto
e' quindi possibile su quella pagina.

Riscontro usato (pagina secondaria indicata dal piano): calcolo-termini-processuali-civili.php,
con TipoTermine = "Mesi" (calcolo ex nominatione dierum), sospensione feriale DISATTIVATA
(termine sostanziale: i 6/12 mesi dell'art. 3 n. 2 lett. b L. 898/1970 non sono un termine
processuale, quindi L. 742/1969 non si applica) e "termine libero" disattivato. Cosi' il sito
fornisce l'aritmetica dei mesi di calendario (art. 155 co. 2 c.p.c.; clamp a fine mese, art. 2963
co. 4 c.c.) e la proroga al primo giorno non festivo (art. 155 co. 4-5 c.p.c.), che sono esattamente
le convenzioni che il tool applica. Il sito e' solo un benchmark: qualifica giuridica del risultato
(data di compimento vs primo giorno utile) resta da valutare a parte.

Tolleranza: date esatte.
"""

import os
import re
import sys

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: E402,F401  (registers all tool modules)
from src.tools.scadenze_termini import termini_separazione_divorzio  # noqa: E402

from .conftest import accept_cookies  # noqa: E402

PAGE = "https://www.avvocatoandreani.it/servizi/calcolo-termini-processuali-civili.php"

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_MESI_TIPO = {
    "separazione_consensuale": 6,
    "separazione_giudiziale": 12,
    "negoziazione_assistita": 6,
}


def _tool(data_evento, tipo):
    fn = getattr(termini_separazione_divorzio, "fn", termini_separazione_divorzio)
    return fn(data_evento=data_evento, tipo=tipo)


def _site_mesi(page, data_evento, mesi, feriale=False):
    y, m, d = data_evento.split("-")
    page.goto(PAGE, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("#GiornoInizio", d)
    page.select_option("#MeseInizio", m)
    page.select_option("#AnnoInizio", y)
    page.select_option("#TipoTermine", "2")  # Mesi
    page.fill("#Termine1", str(mesi))
    page.set_checked("#SospensioneFeriale", feriale, force=True)
    page.set_checked("#TermineLibero", False, force=True)
    page.click("#button1", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body").replace("\xa0", " ")
    mm = re.search(r"Termine ultimo:\s*\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    assert mm, "risultato del sito non leggibile: " + text[-600:]
    return f"{int(mm.group(3)):04d}-{_MESI[mm.group(2).lower()]:02d}-{int(mm.group(1)):02d}"


def _confronta(page, data_evento, tipo):
    r = _tool(data_evento, tipo)
    assert "errore" not in r, r
    assert r["mesi_termine"] == _MESI_TIPO[tipo]
    tool_data = r["scadenza"]
    site_data = _site_mesi(page, data_evento, _MESI_TIPO[tipo])
    assert tool_data == site_data, f"tool={tool_data} sito={site_data} ({data_evento}, {tipo})"


def test_consensuale_sei_mesi(page):
    # Piano: 2025-09-15 (lunedi), sei mesi dalla comparizione (art. 3 n. 2 lett. b L. 898/1970),
    # computo a calendario comune (art. 155 co. 2 c.p.c.).
    _confronta(page, "2025-03-15", "separazione_consensuale")


def test_giudiziale_dodici_mesi_domenica(page):
    # Piano: compimento 2026-03-15 (domenica); il tool restituisce 2026-03-16 (proroga art. 155
    # co. 4 c.p.c.). Caso al limite: proroga di domenica.
    _confronta(page, "2025-03-15", "separazione_giudiziale")


def test_dies_a_quo_31_agosto_febbraio_sabato(page):
    # Piano: compimento 2026-02-28 (ultimo giorno di febbraio, art. 2963 co. 4 c.c.), sabato:
    # il tool restituisce 2026-03-02. Caso al limite: clamp a fine mese + sabato + agosto.
    _confronta(page, "2025-08-31", "separazione_consensuale")


def test_negoziazione_assistita_agosto(page):
    # Piano: 2026-08-10 (lunedi), sei mesi dalla data certificata (art. 3 n. 2 lett. b L. 898/1970
    # come mod. DL 132/2014); L. 742/1969 non applicabile. Caso al limite: scadenza in agosto,
    # sospensione feriale disattivata sul sito.
    _confronta(page, "2026-02-10", "negoziazione_assistita")


def test_ricorso_modifica_nessun_termine():
    # Piano: scadenza null (art. 473-bis.29 c.p.c.; art. 9 L. 898/1970). Il sito non ha un
    # calcolatore per un termine inesistente: non confrontabile.
    r = _tool("2025-06-01", "ricorso_modifica")
    assert r["scadenza"] is None
    pytest.skip("non confrontabile: il sito non offre un'opzione 'nessun termine'")


def test_limite_29_febbraio_dodici_mesi(page):
    # Limite: dies a quo 29/02/2024 + 12 mesi -> febbraio 2025 senza il 29: ultimo giorno (28,
    # venerdi) (art. 2963 co. 4 c.c.).
    _confronta(page, "2024-02-29", "separazione_giudiziale")


def test_limite_natale_proroga_sabato(page):
    # Limite: 25/06/2025 + 6 mesi = 25/12/2025 (Natale, giovedi); S. Stefano venerdi, poi sabato.
    # Il tool fa scorrere anche il sabato (2025-12-29); il sito, dopo la catena Natale/S. Stefano,
    # si ferma al sabato 27 (art. 155 co. 4 e 6 c.p.c.: il sabato e' giorno utile se ci si arriva
    # da un festivo, mentre il co. 5 lo proroga solo se la scadenza calcolata cade di sabato).
    # Scostamento genuino: resta fallito per la fase 2.
    _confronta(page, "2025-06-25", "separazione_consensuale")


def test_limite_fine_mese_30_giugno_sei_mesi(page):
    # Limite: 30/06/2025 + 6 mesi = 30/12/2025 (martedi), nessun clamp; controllo di regolarita'.
    _confronta(page, "2025-06-30", "separazione_consensuale")


def test_limite_31_agosto_2024_febbraio_venerdi(page):
    # Limite: 31/08/2024 + 6 mesi -> 28/02/2025 (venerdi, clamp senza slittamento).
    _confronta(page, "2024-08-31", "separazione_consensuale")


# CONVENTION (phase 2-3): the only mismatch is 25/12/2025 -> Saturday 27/12 (site) vs Monday
# 29/12 (tool), the same open question as termini_esecuzioni (art. 155 co. 4-6 c.p.c.). Also open:
# the 6/12 months of art. 3 n. 2 lett. b) L. 898/1970 are a substantive minimum duration, so the
# applicability of art. 155 is itself a convention. Tool is the later (prudent) date: no change.
