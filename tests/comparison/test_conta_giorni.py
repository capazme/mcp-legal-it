"""Comparison tests: conta_giorni vs avvocatoandreani.it/servizi/calcolo-giorni-tra-date-e-ricorrenze.php."""

import re
from tests.comparison.conftest import goto


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

    page.click("#btn-calc")
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
