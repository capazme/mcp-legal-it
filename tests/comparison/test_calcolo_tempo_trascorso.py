"""Benchmark calcolo_tempo_trascorso vs avvocatoandreani.it.

Pagina del sito: /servizi/calcolo-giorni-tra-date-e-ricorrenze.php ("Conta i
Giorni tra due Date"). La pagina "Calcolo Tempo Trascorso" del sito
(calcolo-tempo-trascorso-differenza-ore.php) riguarda le ORE, non le date.

Il sito restituisce SOLO i giorni totali ("Tra mercoledi 31 gennaio 2024 e
venerdi 1 marzo 2024 intercorrono 30 giorni"), NON la scomposizione in anni,
mesi e giorni. Quindi:
- test *_giorni_totali: tool.giorni_totali == sito (date esatte);
- test *_scomposizione: il sito non calcola la scomposizione; il riferimento e'
  il computo civile dell'art. 2963 co. 4-5 c.c. (mesi e anni si computano
  secondo il calendario comune; se nel mese di scadenza manca il giorno, il
  termine si compie l'ultimo giorno del mese). Oracolo indipendente locale.
"""

import calendar
import re
from datetime import date

import pytest

from tests.comparison.conftest import accept_cookies

@pytest.fixture()
def page_it(browser):
    """Contesto con locale it-IT: senza locale il modulo del sito non si invia in modo
    affidabile in headless (verificato: il risultato non compare), quindi non si usa
    la fixture `page` di conftest."""
    ctx = browser.new_context(locale="it-IT")
    pg = ctx.new_page()
    yield pg
    pg.close()
    ctx.close()


URL = "https://www.avvocatoandreani.it/servizi/calcolo-giorni-tra-date-e-ricorrenze.php"


def _tool(**kw):
    import src.server  # noqa: F401  (registra i moduli)
    from src.tools.varie import calcolo_tempo_trascorso

    fn = getattr(calcolo_tempo_trascorso, "fn", calcolo_tempo_trascorso)
    return fn(**kw)


def _sito_giorni(page, d1: str, d2: str) -> int:
    """Guida il modulo del sito; fino a 3 tentativi (il sito a volte non risponde al primo invio)."""
    y1, m1, g1 = d1.split("-")
    y2, m2, g2 = d2.split("-")
    for tentativo in range(3):
        page.wait_for_timeout(2000 * (tentativo + 1))  # cortesia verso il sito
        page.goto(URL, timeout=60000, wait_until="domcontentloaded")
        accept_cookies(page)
        page.select_option("select[name='RicorrenzaDal']", "")
        page.select_option("select[name='GiornoDal']", g1)
        page.select_option("select[name='MeseDal']", m1)
        page.select_option("select[name='AnnoDal']", y1)
        page.select_option("select[name='GiornoAl']", g2)
        page.select_option("select[name='MeseAl']", m2)
        page.select_option("select[name='AnnoAl']", y2)
        page.click("#btn-calc", force=True)
        try:
            page.wait_for_function(
                "/intercorr\\w+\\s+-?[\\d.]+\\s+giorn/.test(document.body.innerText)",
                timeout=8000,
            )
        except Exception:
            continue
        m = re.search(r"intercorr\w+\s+(-?[\d\.]+)\s+giorn", page.inner_text("body"))
        if m:
            return int(m.group(1).replace(".", ""))
    raise AssertionError("risultato 'intercorrono N giorni' non trovato sul sito (3 tentativi)")


def _add_months(d: date, n: int) -> date:
    idx = d.year * 12 + (d.month - 1) + n
    y, mo = divmod(idx, 12)
    mo += 1
    return date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))


def _oracolo_2963(d1: date, d2: date):
    """Mesi interi compiuti (art. 2963 co. 5: ultimo giorno del mese se manca il giorno)."""
    n = (d2.year - d1.year) * 12 + d2.month - d1.month
    while n > 0 and _add_months(d1, n) > d2:
        n -= 1
    resto = (d2 - _add_months(d1, n)).days
    return n // 12, n % 12, resto


def _confronta_giorni(page, d1, d2):
    r = _tool(data_inizio=d1, data_fine=d2)
    assert "errore" not in r, r
    sito = _sito_giorni(page, d1, d2)
    assert r["giorni_totali"] == sito, f"tool={r['giorni_totali']} sito={sito}"


def _confronta_scomposizione(d1, d2):
    r = _tool(data_inizio=d1, data_fine=d2)
    assert "errore" not in r, r
    atteso = _oracolo_2963(date.fromisoformat(d1), date.fromisoformat(d2))
    assert (r["anni"], r["mesi"], r["giorni"]) == atteso, (
        f"tool={(r['anni'], r['mesi'], r['giorni'])} art.2963={atteso}"
    )


# Piano: 0 anni, 1 mese, 1 giorno; 30 giorni totali (LIMITE: bisestile, 31/01 -> 01/03)
def test_fine_gennaio_marzo_bisestile_giorni_totali(page_it):
    _confronta_giorni(page_it, "2024-01-31", "2024-03-01")


def test_fine_gennaio_marzo_bisestile_scomposizione():
    # Sito non calcola la scomposizione: riferimento art. 2963 co. 5 c.c.
    _confronta_scomposizione("2024-01-31", "2024-03-01")


# Piano: 0 anni, 1 mese, 1 giorno; 29 giorni totali (LIMITE: non bisestile)
def test_fine_gennaio_marzo_non_bisestile_giorni_totali(page_it):
    _confronta_giorni(page_it, "2023-01-31", "2023-03-01")


def test_fine_gennaio_marzo_non_bisestile_scomposizione():
    _confronta_scomposizione("2023-01-31", "2023-03-01")


# Piano: 1 anno esatto (art. 2963 co. 5), 365 giorni totali (LIMITE: 29 febbraio)
def test_29_febbraio_al_28_febbraio_giorni_totali(page_it):
    _confronta_giorni(page_it, "2020-02-29", "2021-02-28")


def test_29_febbraio_al_28_febbraio_scomposizione():
    _confronta_scomposizione("2020-02-29", "2021-02-28")


# Piano: 10 anni, 0 mesi, 0 giorni; 3652 giorni totali (2 bisestili)
def test_dieci_anni_due_bisestili_giorni_totali(page_it):
    _confronta_giorni(page_it, "2016-09-25", "2026-09-25")


def test_dieci_anni_due_bisestili_scomposizione():
    _confronta_scomposizione("2016-09-25", "2026-09-25")


# Extra (LIMITE: attraversa agosto): 2025-07-15 -> 2025-09-10 = 57 giorni; 1 mese 26 gg
def test_attraverso_agosto_giorni_totali(page_it):
    _confronta_giorni(page_it, "2025-07-15", "2025-09-10")


def test_attraverso_agosto_scomposizione():
    _confronta_scomposizione("2025-07-15", "2025-09-10")


# Extra (LIMITE: cambio anno e 29/02): 2023-12-31 -> 2024-02-29 = 60 giorni
def test_cambio_anno_bisestile_giorni_totali(page_it):
    _confronta_giorni(page_it, "2023-12-31", "2024-02-29")


def test_cambio_anno_bisestile_scomposizione():
    _confronta_scomposizione("2023-12-31", "2024-02-29")


# Extra: data_fine omessa -> oggi pinnato a 2026-09-25 (il "Oggi" del sito e'
# la data reale, quindi sul sito si inserisce 25/09/2026 esplicitamente).
def test_data_fine_omessa_oggi_pinnato(page_it, monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-25")
    r = _tool(data_inizio="2026-01-01")
    assert "errore" not in r, r
    assert r["data_fine"] == "2026-09-25"
    sito = _sito_giorni(page_it, "2026-01-01", "2026-09-25")
    assert r["giorni_totali"] == sito, f"tool={r['giorni_totali']} sito={sito}"
