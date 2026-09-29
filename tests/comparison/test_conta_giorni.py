"""Comparison tests: conta_giorni vs avvocatoandreani.it.

Calendario: calcolo-giorni-tra-date-e-ricorrenze.php.
Lavorativi e festivi: calcolo-giorni-lavorativi-festivi.php (modulo GiorniLavorativi,
"Tra le due date intercorrono N giorni lavorativi"). Il sito non ha una modalita'
"festivi": il numero di festivita' si ricava per differenza tra il conteggio senza
esclusioni e quello con la sola opzione "festivita' nazionali" (una festivita' che cade
di sabato/domenica conta una volta, come nel tool). Dies a quo escluso, dies ad quem
incluso (Compreso spento) in entrambi.
"""

import re
import pytest
from tests.comparison.conftest import goto, accept_cookies



def _fill_and_calc(page, data_inizio, data_fine):
    goto(page, "calcolo-giorni-tra-date-e-ricorrenze.php")
    ai, mi, gi = data_inizio.split("-")  # YYYY-MM-DD
    af, mf, gf = data_fine.split("-")

    # All date fields are SELECTs with zero-padded values ("01", "02", etc.)
    page.select_option("select[name='GiornoDal']", gi)
    page.select_option("select[name='MeseDal']", mi)
    page.select_option("select[name='AnnoDal']", ai)
    page.select_option("select[name='GiornoAl']", gf)
    page.select_option("select[name='MeseAl']", mf)
    page.select_option("select[name='AnnoAl']", af)

    accept_cookies(page)
    page.click("#btn-calc", force=True)
    page.wait_for_timeout(2000)
    return _parse_result(page)


def _parse_result(page) -> int:
    body = page.inner_text("body")
    # Look for "X giorni" pattern with number > 10 (to skip small noise)
    matches = re.findall(r"(\d+)\s*giorni", body, re.IGNORECASE)
    for m in matches:
        val = int(m)
        if val > 10:
            return val
    # Fallback: any number before "giorni"
    if matches:
        return int(matches[0])
    raise ValueError(f"Could not parse days count. Body excerpt: {body[:500]}")


def _our_conta_giorni(data_inizio, data_fine, tipo="calendario"):
    from src.tools.varie import conta_giorni
    fn = getattr(conta_giorni, "fn", conta_giorni)
    return fn(data_inizio=data_inizio, data_fine=data_fine, tipo=tipo)


class TestContaGiorniComparison:

    def test_same_month(self, page):
        di, df = "2024-03-01", "2024-03-31"
        site = _fill_and_calc(page, di, df)
        ours = _our_conta_giorni(di, df)
        assert ours["giorni"] == site, f"giorni: nostro={ours['giorni']}, sito={site}"

    def test_cross_month(self, page):
        di, df = "2024-01-15", "2024-04-15"
        site = _fill_and_calc(page, di, df)
        ours = _our_conta_giorni(di, df)
        assert ours["giorni"] == site, f"giorni: nostro={ours['giorni']}, sito={site}"

    def test_full_year(self, page):
        di, df = "2024-01-01", "2025-01-01"
        site = _fill_and_calc(page, di, df)
        ours = _our_conta_giorni(di, df)
        assert ours["giorni"] == site, f"giorni: nostro={ours['giorni']}, sito={site}"


# ---------------------------------------------------------------------------
# Lavorativi / festivi: pagina calcolo-giorni-lavorativi-festivi.php
# ---------------------------------------------------------------------------

URL_LAV = "https://www.avvocatoandreani.it/servizi/calcolo-giorni-lavorativi-festivi.php"


def _site_lav(page, di, df, sabati=True, domeniche=True, feste=True):
    """Giorni lavorativi tra due date secondo il sito (Compreso spento)."""
    page.goto(URL_LAV, wait_until="domcontentloaded")
    accept_cookies(page)
    y, m, d = di.split("-")
    y2, m2, d2 = df.split("-")
    page.select_option("select[name='GiornoInizio']", d)
    page.select_option("select[name='MeseInizio']", m)
    page.select_option("select[name='AnnoInizio']", y)
    page.select_option("select[name='GiornoFine']", d2)
    page.select_option("select[name='MeseFine']", m2)
    page.select_option("select[name='AnnoFine']", y2)
    for name, val in (("Sabati", sabati), ("Domeniche", domeniche),
                      ("FesteNazionali", feste), ("Compreso", False)):
        page.set_checked(f"input[name='{name}']", val, force=True)
    page.click("input[name='Calcola1']", force=True)
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    mt = re.search(r"intercorrono\s+(\d+)\s+giorn", body)
    if not mt:
        raise ValueError("risultato non trovato: " + body[-800:])
    return int(mt.group(1))


def _site_festivi(page, di, df):
    totale = _site_lav(page, di, df, False, False, False)
    page.wait_for_timeout(1500)
    senza_feste = _site_lav(page, di, df, False, False, True)
    return totale - senza_feste


class TestContaGiorniLavorativiFestivi:

    def test_lavorativi_agosto_ferragosto_sabato(self, page):
        # Piano: 22 (21 feriali in agosto 2026, Ferragosto di sabato, piu' 1 settembre). L. 260/1949 art. 2.
        # Caso al limite: attraversa agosto.
        di, df = "2026-07-31", "2026-09-01"
        site = _site_lav(page, di, df)
        ours = _our_conta_giorni(di, df, "lavorativi")["giorni"]
        assert ours == site, f"lavorativi: nostro={ours}, sito={site}"

    def test_calendario_agosto(self, page):
        # Piano: 32 giorni (31 luglio escluso). Pagina calendario del sito. Caso al limite: agosto.
        di, df = "2026-07-31", "2026-09-01"
        site = _fill_and_calc(page, di, df)
        ours = _our_conta_giorni(di, df)["giorni"]
        assert ours == site, f"calendario: nostro={ours}, sito={site}"

    def test_lavorativi_4_ottobre_2024_non_festivo(self, page):
        # Piano: 5 (2, 3, 4, 7, 8 ottobre 2024). Prima della L. 151/2025 il 4 ottobre e' lavorativo.
        di, df = "2024-10-01", "2024-10-08"
        site = _site_lav(page, di, df)
        ours = _our_conta_giorni(di, df, "lavorativi")["giorni"]
        assert ours == site, f"lavorativi: nostro={ours}, sito={site}"

    def test_lavorativi_4_ottobre_2027_san_francesco(self, page):
        # Piano: 4 (5, 6, 7, 8 ottobre 2027; il 4 ottobre, lunedi', festivo per L. 8 ottobre 2025 n. 151).
        # Caso al limite: festa introdotta dal 2026.
        di, df = "2027-10-01", "2027-10-08"
        site = _site_lav(page, di, df)
        ours = _our_conta_giorni(di, df, "lavorativi")["giorni"]
        assert ours == site, f"lavorativi: nostro={ours}, sito={site}"

    def test_lavorativi_4_ottobre_2026_domenica(self, page):
        # 4 ottobre 2026 cade di domenica: attesi 5 (2, 5, 6, 7, 8 ottobre): la domenica non e' scomputata due volte.
        # Caso al limite: festa nuova che coincide con la domenica.
        di, df = "2026-10-01", "2026-10-08"
        site = _site_lav(page, di, df)
        ours = _our_conta_giorni(di, df, "lavorativi")["giorni"]
        assert ours == site, f"lavorativi: nostro={ours}, sito={site}"

    def test_lavorativi_pasqua_2026(self, page):
        # Piano: 6 (2, 3, 7, 8, 9, 10 aprile; Pasqua 5 e Lunedi' dell'Angelo 6 esclusi).
        di, df = "2026-04-01", "2026-04-10"
        site = _site_lav(page, di, df)
        ours = _our_conta_giorni(di, df, "lavorativi")["giorni"]
        assert ours == site, f"lavorativi: nostro={ours}, sito={site}"

    def test_lavorativi_cambio_anno(self, page):
        # 24 dicembre 2025 - 7 gennaio 2026: Natale, S. Stefano, Capodanno, Epifania (anni diversi).
        di, df = "2025-12-24", "2026-01-07"
        site = _site_lav(page, di, df)
        ours = _our_conta_giorni(di, df, "lavorativi")["giorni"]
        assert ours == site, f"lavorativi: nostro={ours}, sito={site}"

    def test_lavorativi_25_aprile_sabato(self, page):
        # 25 aprile 2026 cade di sabato: nessun doppio scomputo.
        di, df = "2026-04-20", "2026-04-30"
        site = _site_lav(page, di, df)
        ours = _our_conta_giorni(di, df, "lavorativi")["giorni"]
        assert ours == site, f"lavorativi: nostro={ours}, sito={site}"

    def test_festivi_anno_2026(self, page):
        # Piano: il tool conta le sole festivita' (12 nel 2026, comprese quelle di domenica); art. 2 L. 260/1949
        # considera festive anche le domeniche (61 = 52 + 9). Il sito, con la sola opzione festivita', da' la
        # differenza; qui si confronta la convenzione "sole festivita'".
        di, df = "2026-01-01", "2026-12-31"
        site = _site_festivi(page, di, df)
        ours = _our_conta_giorni(di, df, "festivi")["giorni"]
        assert ours == site, f"festivi: nostro={ours}, sito={site}"
