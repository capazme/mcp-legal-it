"""Comparison tests: calcolo_usufrutto vs avvocatoandreani.it/servizi/calcolo_usufrutto_nuda_proprieta.php."""

import re
from tests.comparison.conftest import assert_close, goto, parse_euro


def _fill_and_calc(page, valore, eta):
    goto(page, "calcolo_usufrutto_nuda_proprieta.php")

    page.fill("input[name='Valore']", str(int(valore)))
    page.click("input[name='TipoCalcolo'][value='1']")  # vitalizio
    page.fill("input[name='Eta']", str(eta))

    page.click("#btn-calc")
    page.wait_for_timeout(2000)

    return _parse_result(page)


def _parse_result(page) -> dict:
    body = page.inner_text("body")
    result = {}

    # Look for "Valore Usufrutto: € X" or similar
    m = re.search(r"[Vv]alore\s+(?:dell[''])?[Uu]sufrutto[:\s]*€?\s*([\d.]+,\d{2})", body)
    if m:
        result["usufrutto"] = parse_euro(m.group(1))

    m = re.search(r"[Vv]alore\s+(?:della\s+)?[Nn]uda\s+[Pp]ropriet[àa][:\s]*€?\s*([\d.]+,\d{2})", body)
    if m:
        result["nuda_proprieta"] = parse_euro(m.group(1))

    if not result:
        # Fallback: look for percentage patterns
        m = re.search(r"[Uu]sufrutto[:\s]*([\d,]+(?:\.\d+)?)\s*%", body)
        if m:
            pct = float(m.group(1).replace(",", "."))
            result["usufrutto_pct"] = pct
            return result

        raise ValueError(f"Could not parse usufrutto results. Body excerpt: {body[:500]}")

    return result


def _our_usufrutto(valore, eta):
    from src.tools.proprieta_successioni import calcolo_usufrutto
    fn = getattr(calcolo_usufrutto, "fn", calcolo_usufrutto)
    return fn(valore_piena_proprieta=valore, eta_usufruttuario=eta)


class TestUsufruttoComparison:

    def test_age_30(self, page):
        site = _fill_and_calc(page, 100000, 30)
        ours = _our_usufrutto(100000, 30)
        assert_close(ours["valore_usufrutto"], site["usufrutto"], tolerance=0.01, label="usufrutto_30")

    def test_age_50(self, page):
        site = _fill_and_calc(page, 200000, 50)
        ours = _our_usufrutto(200000, 50)
        assert_close(ours["valore_usufrutto"], site["usufrutto"], tolerance=0.01, label="usufrutto_50")

    def test_age_70(self, page):
        site = _fill_and_calc(page, 150000, 70)
        ours = _our_usufrutto(150000, 70)
        assert_close(ours["valore_usufrutto"], site["usufrutto"], tolerance=0.01, label="usufrutto_70")

    def test_age_85(self, page):
        site = _fill_and_calc(page, 300000, 85)
        ours = _our_usufrutto(300000, 85)
        assert_close(ours["valore_usufrutto"], site["usufrutto"], tolerance=0.01, label="usufrutto_85")
