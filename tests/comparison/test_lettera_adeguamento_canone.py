"""Comparison: lettera_adeguamento_canone vs avvocatoandreani.it.

Site page: servizi/lettera-adeguamento-canone-locazione.php (form
LetteraAdeguamentoCanone). The site only offers the 12-month variation of the
FOI index for one of the last twelve published months (Settembre 2025 ..
Agosto 2026 as of 2026-09-25), at 75%, 100% or a free percentage (AltraPct).
There is no 24-month option and no not-yet-published month, so those plan
cases are skipped.

Norms: art. 32 L. 392/1978 (adeguamento su richiesta, max 75% FOI);
art. 81 L. 392/1978 (variazione ufficiale ISTAT pubblicata in GU);
L. 431/1998 (art. 2 co. 3 per i concordati, contratto per i liberi).

Notes on driving the site: a Playwright click on #btn-calc does not submit
the form (the page layout swallows the click); `form.requestSubmit(btn)` does.
The resulting letter is rendered in the page body.
"""

import os
import re
import sys

import pytest

from .conftest import accept_cookies, assert_close, parse_euro

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import src.server  # noqa: E402,F401  (registers all tool modules)
from src.tools.rivalutazioni_istat import lettera_adeguamento_canone  # noqa: E402

_fn = getattr(lettera_adeguamento_canone, "fn", lettera_adeguamento_canone)

URL = "https://www.avvocatoandreani.it/servizi/lettera-adeguamento-canone-locazione.php"
MESI = {
    "01": "Gennaio", "02": "Febbraio", "03": "Marzo", "04": "Aprile",
    "05": "Maggio", "06": "Giugno", "07": "Luglio", "08": "Agosto",
    "09": "Settembre", "10": "Ottobre", "11": "Novembre", "12": "Dicembre",
}
BASE = dict(
    locatore="Mario Rossi",
    conduttore="Luca Bianchi",
    indirizzo_immobile="Via Roma 1, 20121 Milano",
)


def _tool(canone, stipula, adeguamento, pct):
    r = _fn(
        canone_attuale=canone,
        data_stipula=stipula,
        data_adeguamento=adeguamento,
        percentuale_istat=pct,
        **BASE,
    )
    assert "errore" not in r, r
    return r


def _site(page, canone: float, mese: str, pct: float) -> dict:
    """Fill the form, submit, return the parsed letter."""
    page.wait_for_timeout(1500)  # be gentle with the site
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("#NomeMitt", BASE["locatore"])
    page.select_option("#TitoloCond", "2")
    page.fill("#NomeCond", BASE["conduttore"])
    page.fill("#IndirCond", BASE["indirizzo_immobile"])
    page.fill("#Canone", f"{canone:.2f}".replace(".", ","))
    page.select_option("#MeseRif", mese)
    if pct == 75:
        page.check("#TipoCalcolo-1", force=True)
    elif pct == 100:
        page.check("#TipoCalcolo-2", force=True)
    else:
        page.fill("#AltraPct", f"{pct:g}".replace(".", ","))
    page.evaluate(
        "document.getElementById('LetteraAdeguamentoCanone')"
        ".requestSubmit(document.getElementById('btn-calc'))"
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    m_new = re.search(r"sarà di €\s*([\d.,]+)", text)
    m_pct = re.search(
        r"nella misura (?:dello|della|del)\s*([\d,]+)%, corrispondente al\s*([\d,]+)% della variazione "
        r"accertata dall.ISTAT relativa al mese di (\w+ \d{4}) \(([+-]?[\d,]+)%\)",
        text,
    )
    assert m_new and m_pct, "letter not found in site output:\n" + text[:3000]
    return {
        "canone_nuovo": parse_euro(m_new.group(1)),
        "variazione_applicata": float(m_pct.group(1).replace(",", ".")),
        "percentuale": float(m_pct.group(2).replace(",", ".")),
        "mese": m_pct.group(3),
        "variazione_piena": float(m_pct.group(4).replace(",", ".")),
        "text": text,
    }


def _compare(page, canone, stipula, adeguamento, pct):
    tool = _tool(canone, stipula, adeguamento, pct)
    mese = adeguamento[5:7]
    site = _site(page, canone, mese, pct)
    assert site["mese"] == f"{MESI[mese]} {adeguamento[:4]}", site["mese"]
    assert site["percentuale"] == pct
    print(
        f"\nTOOL canone_nuovo={tool['canone_nuovo']} var_piena={tool['variazione_piena_pct']} "
        f"var_appl={tool['variazione_applicata_pct']} metodo={tool['metodo_variazione']}"
        f"\nSITE canone_nuovo={site['canone_nuovo']} var_piena={site['variazione_piena']} "
        f"var_appl={site['variazione_applicata']} mese={site['mese']}"
    )
    assert_close(tool["variazione_piena_pct"], site["variazione_piena"], 0.00005, "variazione piena %")
    assert_close(tool["canone_nuovo"], site["canone_nuovo"], 0.01, "canone nuovo")
    return tool, site


def test_maggio_2026_75pct(page):
    """Piano caso 1 - 12 mesi, maggio 2026, 75%.

    Atteso: canone nuovo 1.022,50 (+3,0% al 75%); il testo cita art. 32
    L. 392/1978, l'indice FOI e la fonte GU S.G. n. 144 del 24-06-2026
    (comunicato ISTAT 26A03169) ex art. 81 L. 392/1978.
    """
    tool, _ = _compare(page, 1000, "2025-05-01", "2026-05-01", 75)
    lettera = tool["lettera"]
    assert "art. 32" in lettera and "392/1978" in lettera
    assert "FOI" in lettera
    assert "n. 144 del 24-06-2026" in lettera and "26A03169" in lettera


def test_giugno_24_mesi_100pct(page):
    """Piano caso 2 - 24 mesi al 100% (giugno 2024 -> giugno 2026).

    Atteso: canone nuovo 783,00 (+4,4%, GU n. 201 del 31/08/2026, comunicato
    26A04494). Il sito calcola solo la variazione a 12 mesi: non confrontabile.
    Il caso a 12 mesi di giugno 2026 e' coperto da test_giugno_2026_100pct.
    """
    pytest.skip("il sito offre solo la variazione a 12 mesi (nessuna opzione biennale)")


def test_dicembre_2026_non_pubblicato(page):
    """Piano caso 3 - indice di dicembre 2026 non ancora pubblicato.

    Atteso: avvertenza INDICATIVO in coda alla lettera; 880,78 e' una stima.
    Il sito offre solo gli ultimi dodici mesi pubblicati (Dicembre = 2025).
    """
    pytest.skip("il sito non offre indici non ancora pubblicati (Dicembre = dicembre 2025)")


def test_giugno_2026_100pct(page):
    """12 mesi giugno 2025 -> giugno 2026 al 100% (sostituto confrontabile del caso 2).

    Variazione ufficiale GU n. 201 del 31-08-2026 (comunicato 26A04494), art. 81 L. 392/1978.
    """
    _compare(page, 750, "2025-06-01", "2026-06-01", 100)


def test_agosto_2026_ultimo_indice(page):
    """LIMITE - ultimo indice pubblicato (agosto 2026, comunicato GU non ancora uscito), 100%."""
    _compare(page, 1000, "2025-08-01", "2026-08-01", 100)


def test_gennaio_2026_primo_mese_base_2025(page):
    """LIMITE - gennaio 2026, primo mese della nuova base 2025=100 (raccordo 1,214), 75%.

    Variazione ufficiale GU n. 50 del 02-03-2026 (comunicato 26A00955).
    """
    _compare(page, 1000, "2025-01-01", "2026-01-01", 75)


def test_dicembre_2025_ultimo_mese_base_2015(page):
    """LIMITE - dicembre 2025, ultimo mese della vecchia base 2015=100, 100%.

    Il tool calcola la variazione sulla serie raccordata (metodo 'calcolata').
    """
    _compare(page, 1000, "2024-12-01", "2025-12-01", 100)


def test_settembre_2025_mese_piu_vecchio(page):
    """LIMITE - settembre 2025, il mese piu' vecchio offerto dal sito, 75%, canone con centesimi."""
    _compare(page, 1234.56, "2024-09-01", "2025-09-01", 75)


def test_marzo_2026_altra_percentuale_50(page):
    """LIMITE (opzione enumerata 'Altro') - marzo 2026 al 50%.

    Variazione ufficiale GU n. 97 del 28-04-2026 (comunicato 26A02007).
    """
    _compare(page, 800, "2025-03-01", "2026-03-01", 50)
