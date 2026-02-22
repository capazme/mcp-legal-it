"""Comparison tests: interessi_mora vs avvocatoandreani.it/servizi/interessi_moratori.php."""

import re
from tests.comparison.conftest import assert_close, goto, parse_euro


def _fill_and_calc(page, capitale, data_inizio, data_fine):
    goto(page, "interessi_moratori.php")
    ai, mi, gi = data_inizio.split("-")
    af, mf, gf = data_fine.split("-")

    page.fill("input[name='Capitale']", str(int(capitale)))
    page.select_option("select[name='GiornoInizio']", gi)
    page.select_option("select[name='MeseInizio']", mi)
    page.select_option("select[name='AnnoInizio']", ai)
    page.select_option("select[name='GiornoFine']", gf)
    page.select_option("select[name='MeseFine']", mf)
    page.select_option("select[name='AnnoFine']", af)

    page.click("input[name='Calcola']")
    page.wait_for_timeout(2000)
    return _parse_totale(page)


def _parse_totale(page) -> float:
    for table in page.query_selector_all("table"):
        text = table.inner_text()
        m = re.search(r"[Tt]otale\s+interessi\s+moratori[:\s]*€?\s*([\d.]+,\d{2})", text)
        if m:
            return parse_euro(m.group(1))
    raise ValueError("Could not parse totale interessi moratori")


def _our_mora(capitale, data_inizio, data_fine):
    from src.tools.tassi_interessi import interessi_mora
    fn = getattr(interessi_mora, "fn", interessi_mora)
    return fn(capitale=capitale, data_inizio=data_inizio, data_fine=data_fine)


class TestInteressiMoraComparison:

    def test_full_year_2023(self, page):
        capitale = 10000
        di, df = "2023-01-01", "2024-01-01"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_mora(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.02, label="full_year_2023")

    def test_half_year(self, page):
        capitale = 20000
        di, df = "2023-01-01", "2023-07-01"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_mora(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.02, label="half_year")

    def test_cross_semester(self, page):
        capitale = 15000
        di, df = "2023-03-15", "2023-09-15"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_mora(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.05, label="cross_semester")

    def test_multi_year(self, page):
        capitale = 50000
        di, df = "2022-01-01", "2024-01-01"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_mora(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.10, label="multi_year")
