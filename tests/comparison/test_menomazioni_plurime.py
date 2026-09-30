"""Benchmark menomazioni_plurime vs avvocatoandreani.it (calcolo riduzionistico).

Page: https://www.avvocatoandreani.it/servizi/calcolo-riduzionistico-menomazioni-plurime.php
Form: MetodoCalcolo (1 = Balthazard, 2 = Salomonica), Invalidita (textarea, values
separated by spaces/newlines, comma or dot as decimal separator), Decimali (0/1/2).
Result label: "Invalidità risultante con la Formula di Balthazard: NN,NN%".

Source: D.M. 5 febbraio 1992 (G.U. n. 47 del 26/02/1992), tabella indicativa delle
percentuali d'invalidità civile - calcolo riduzionistico (Balthazard) for
coexisting impairments. The tool implements Balthazard only.

Tolerance: the site is driven with Decimali=2 and the tool rounds to 2 decimals, so
both values are compared at 1e-4 (brief: four decimals on percentages).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies

URL = "https://www.avvocatoandreani.it/servizi/calcolo-riduzionistico-menomazioni-plurime.php"
TOL = 1e-4


def _tool(percentuali):
    import src.server  # noqa: F401  registers every module
    from src.tools.risarcimento_danni import menomazioni_plurime

    fn = getattr(menomazioni_plurime, "fn", menomazioni_plurime)
    return fn(percentuali=percentuali)


def _site(page, percentuali, metodo="1", decimali="2"):
    page.goto(URL, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("#MetodoCalcolo", metodo)
    page.fill("#Invalidita", " ".join(str(p).replace(".", ",") for p in percentuali))
    page.select_option("#Decimali", decimali)
    page.click("#btn-calc", force=True)
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    m = re.search(r"Invalidit\S+ risultante con la Formula[^:]*:\s*([\d.,]+)\s*%", body)
    if not m:
        return None, body
    return float(m.group(1).replace(".", "").replace(",", ".")), body


def _compare(page, percentuali):
    r = _tool(percentuali)
    assert "errore" not in r, r
    ours = r["invalidita_complessiva_pct"]
    site, body = _site(page, percentuali)
    assert site is not None, "site returned no result"
    print(f"{percentuali}: tool={ours} site={site}")
    assert abs(ours - site) <= TOL, f"{percentuali}: tool {ours} != site {site}"


def test_due_menomazioni_15_10(page):
    # Piano: 23,50% (1 - 0,85 x 0,90); somma aritmetica 25. D.M. 5/2/1992.
    _compare(page, [15, 10])


def test_tre_menomazioni_20_10_5(page):
    # Piano: 31,60% (1 - 0,80 x 0,90 x 0,95). D.M. 5/2/1992.
    _compare(page, [20, 10, 5])


def test_ordine_crescente_10_20(page):
    # Piano: 28,00%, formula commutativa (docstring asks for descending order,
    # result does not depend on it). D.M. 5/2/1992.
    _compare(page, [10, 20])


def test_menomazione_totale_100_50(page):
    # Limit case. Piano: 100% (residual is zero). D.M. 5/2/1992.
    _compare(page, [100, 50])


def test_micropermanenti_confine_10(page):
    # Limit case. Piano: 9,69% (1 - 0,95 x 0,97 x 0,98): stays below 10 (art. 139
    # cod. ass.), while the arithmetic sum (10) would reach art. 138.
    _compare(page, [5, 3, 2])


def test_arrotondamento_mezzo_centesimo_5_5_5(page):
    # Limit case (rounding): exact value 14,2625% sits on the half-hundredth;
    # half-up gives 14,27, round-half-even / float truncation gives 14,26.
    _compare(page, [5, 5, 5])


def test_decimali_12_5_7_25(page):
    # Decimal inputs: 1 - 0,875 x 0,9275 = 18,84375% -> 18,84.
    _compare(page, [12.5, 7.25])


def test_zero_e_30(page):
    # Limit case: a 0% impairment is neutral -> tool 30%. The site rejects a 0 value
    # silently (no result block is rendered), so the case is not comparable.
    r = _tool([0, 30])
    assert r["invalidita_complessiva_pct"] == 30.0
    site, _ = _site(page, [0, 30])
    if site is None:
        pytest.skip("sito_non_calcola: the site renders no result when a value is 0")
    assert abs(r["invalidita_complessiva_pct"] - site) <= TOL


def test_una_sola_percentuale():
    # Piano: error, at least two values required. The site renders no result for a
    # single value either (checked 2026-09-28), so there is no value to compare.
    r = _tool([40])
    assert "errore" in r
    pytest.skip("non confrontabile: the tool refuses a single value by design")


def test_formula_salomonica_non_offerta():
    # The site offers MetodoCalcolo=2 (Formula Salomonica, concurrent impairments on
    # the same apparatus); the tool implements Balthazard only.
    pytest.skip("non confrontabile: the tool has no Salomonica (concurrent impairments) option")
