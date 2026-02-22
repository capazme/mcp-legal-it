"""Comparison tests: interessi_legali vs avvocatoandreani.it/servizi/interessi_legali.php."""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro


def _fill_and_calc(page, capitale, data_inizio, data_fine, anatocismo=False):
    """Fill the interessi_legali form and return the site's total interest."""
    goto(page, "interessi_legali.php")

    # Parse dates (YYYY-MM-DD) → day, month, year for the form
    ai, mi, gi = data_inizio.split("-")
    af, mf, gf = data_fine.split("-")

    page.fill("input[name='Capitale']", str(int(capitale)))
    page.fill("input[name='GiornoInizio']", gi)
    page.fill("input[name='MeseInizio']", mi)
    page.fill("input[name='AnnoInizio']", ai)
    page.fill("input[name='GiornoFine']", gf)
    page.fill("input[name='MeseFine']", mf)
    page.fill("input[name='AnnoFine']", af)

    # Anatocismo: 0=none, 3=trimestrale, 6=semestrale, 12=annuale
    value = "12" if anatocismo else "0"
    page.click(f"input[name='Anatocismo'][value='{value}']")

    page.click("#btn-calc")
    page.wait_for_timeout(2000)

    return _parse_totale(page)


def _parse_totale(page) -> float:
    """Extract 'Totale interessi legali: € X' from the result tables."""
    tables = page.query_selector_all("table")
    for table in tables:
        text = table.inner_text()
        m = re.search(r"[Tt]otale\s+interessi\s+legali[:\s]*€?\s*([\d.]+,\d{2})", text)
        if m:
            return parse_euro(m.group(1))
    # Fallback: search full page
    full = page.inner_text("body")
    m = re.search(r"[Tt]otale\s+interessi\s+legali[:\s]*€?\s*([\d.]+,\d{2})", full)
    if m:
        return parse_euro(m.group(1))
    raise ValueError("Could not parse 'Totale interessi legali' from site")


def _our_interessi(capitale, data_inizio, data_fine, tipo="semplici"):
    """Call our interessi_legali tool."""
    from src.tools.tassi_interessi import interessi_legali
    fn = getattr(interessi_legali, "fn", interessi_legali)
    return fn(capitale=capitale, data_inizio=data_inizio, data_fine=data_fine, tipo=tipo)


class TestInteressiLegaliComparison:

    def test_same_year_no_rate_change(self, page):
        """Single year, no rate boundary crossing."""
        capitale = 10000
        di, df = "2023-06-01", "2023-12-01"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_interessi(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.02, label="same_year")

    def test_cross_year_rate_change(self, page):
        """Crosses year boundary where rate changes (5% → 2.5%)."""
        capitale = 10000
        di, df = "2023-01-01", "2024-01-01"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_interessi(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.02, label="cross_year")

    def test_multi_year_multiple_rates(self, page):
        """Spans multiple years with different rates."""
        capitale = 50000
        di, df = "2021-01-01", "2024-01-01"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_interessi(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.10, label="multi_year")

    def test_mid_year_to_mid_year(self, page):
        """Mid-year to mid-year crossing one rate boundary."""
        capitale = 25000
        di, df = "2023-06-15", "2024-06-15"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_interessi(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.05, label="mid_year")

    def test_short_period_same_rate(self, page):
        """Short period within same rate."""
        capitale = 5000
        di, df = "2024-03-01", "2024-06-01"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_interessi(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.02, label="short_period")

    def test_large_capital_long_period(self, page):
        """Large capital over many years."""
        capitale = 100000
        di, df = "2018-01-01", "2025-01-01"
        site = _fill_and_calc(page, capitale, di, df)
        ours = _our_interessi(capitale, di, df)
        assert_close(ours["totale_interessi"], site, tolerance=0.50, label="large_long")
