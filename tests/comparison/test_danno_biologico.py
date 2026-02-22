"""Comparison tests: danno_biologico_micro vs avvocatoandreani.it/servizi/calcolo_danno_biologico.php."""

import re
from tests.comparison.conftest import assert_close, goto, parse_euro, submit_form


def _fill_and_calc(page, punti, eta, anno="2025"):
    goto(page, "calcolo_danno_biologico.php")

    page.select_option("select[name='Anno']", anno)
    page.select_option("select[name='Punti']", str(punti))
    page.select_option("select[name='Decimali']", "0")
    page.fill("input[name='Eta']", str(eta))
    page.fill("input[name='GgAss']", "0")

    submit_form(page, form_selector="#DannoBiologico")
    return _parse_result(page)


def _parse_result(page) -> dict:
    body = page.inner_text("body")
    result = {}

    m = re.search(r"Danno biologico permanente\s*€?\s*([\d.]+,\d{2})", body)
    if m:
        result["danno_permanente"] = parse_euro(m.group(1))

    m = re.search(r"Punto base danno permanente\s*€?\s*([\d.]+,\d{2})", body)
    if m:
        result["punto_base"] = parse_euro(m.group(1))

    m = re.search(r"TOTALE GENERALE[:\s]*€?\s*([\d.]+,\d{2})", body)
    if m:
        result["totale"] = parse_euro(m.group(1))

    if "danno_permanente" not in result:
        raise ValueError(f"Could not parse danno biologico results. Body excerpt: {body[:800]}")

    return result


def _our_danno(punti, eta):
    from src.tools.risarcimento_danni import danno_biologico_micro
    fn = getattr(danno_biologico_micro, "fn", danno_biologico_micro)
    return fn(percentuale_invalidita=punti, eta_vittima=eta)


class TestDannoBiologicoComparison:

    def test_5_punti_30_anni(self, page):
        site = _fill_and_calc(page, 5, 30)
        ours = _our_danno(5, 30)
        assert_close(ours["danno_permanente"], site["danno_permanente"], tolerance=1.0, label="danno_5pt_30y")

    def test_3_punti_50_anni(self, page):
        site = _fill_and_calc(page, 3, 50)
        ours = _our_danno(3, 50)
        assert_close(ours["danno_permanente"], site["danno_permanente"], tolerance=1.0, label="danno_3pt_50y")

    def test_9_punti_25_anni(self, page):
        site = _fill_and_calc(page, 9, 25)
        ours = _our_danno(9, 25)
        assert_close(ours["danno_permanente"], site["danno_permanente"], tolerance=1.0, label="danno_9pt_25y")

    def test_1_punto_40_anni(self, page):
        site = _fill_and_calc(page, 1, 40)
        ours = _our_danno(1, 40)
        assert_close(ours["danno_permanente"], site["danno_permanente"], tolerance=1.0, label="danno_1pt_40y")
