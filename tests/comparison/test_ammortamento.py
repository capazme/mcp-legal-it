"""Comparison tests: calcolo_ammortamento vs avvocatoandreani.it/servizi/calcolo-ammortamento-mutuo.php."""

import re
from tests.comparison.conftest import assert_close, goto, parse_euro


def _fill_and_calc(page, capitale, tasso, anni, metodo="F"):
    goto(page, "calcolo-ammortamento-mutuo.php")

    page.fill("input[name='Capitale']", str(int(capitale)))
    page.fill("input[name='Tasso']", str(tasso))
    page.click("input[name='TipoDurata'][value='1']")  # years
    page.select_option("select[name='DurataAnni']", str(anni))
    page.select_option("select[name='Metodo']", metodo)
    page.select_option("select[name='Periodicita']", "12")  # monthly

    page.click("input[name='Calcola']")
    page.wait_for_timeout(2000)
    return _parse_result(page)


def _parse_result(page) -> dict:
    result = {}
    for table in page.query_selector_all("table"):
        text = table.inner_text()
        m = re.search(r"Importo di ogni singola Rata[:\s]*€?\s*([\d.]+,\d{2})", text)
        if m:
            result["rata"] = parse_euro(m.group(1))
        m = re.search(r"Interessi complessivi[^:]*[:\s]*€?\s*([\d.]+,\d{2})", text)
        if m:
            result["totale_interessi"] = parse_euro(m.group(1))
    return result


def _our_ammortamento(capitale, tasso, mesi, tipo="francese"):
    from src.tools.tassi_interessi import calcolo_ammortamento
    fn = getattr(calcolo_ammortamento, "fn", calcolo_ammortamento)
    return fn(capitale=capitale, tasso_annuo=tasso, durata_mesi=mesi, tipo=tipo)


class TestAmmortamentoComparison:

    def test_francese_20y_3_5pct(self, page):
        site = _fill_and_calc(page, 100000, 3.5, 20, "F")
        ours = _our_ammortamento(100000, 3.5, 240)
        assert_close(ours["rata_iniziale"], site["rata"], tolerance=0.01, label="rata_francese")
        assert_close(ours["totale_interessi"], site["totale_interessi"], tolerance=0.10, label="interessi_francese")

    def test_francese_10y_2pct(self, page):
        site = _fill_and_calc(page, 50000, 2.0, 10, "F")
        ours = _our_ammortamento(50000, 2.0, 120)
        assert_close(ours["rata_iniziale"], site["rata"], tolerance=0.01, label="rata_10y")
        assert_close(ours["totale_interessi"], site["totale_interessi"], tolerance=0.10, label="interessi_10y")

    def test_italiano_15y_4pct(self, page):
        site = _fill_and_calc(page, 200000, 4.0, 15, "I")
        ours = _our_ammortamento(200000, 4.0, 180, "italiano")
        assert_close(ours["totale_interessi"], site["totale_interessi"], tolerance=0.50, label="interessi_italiano")
