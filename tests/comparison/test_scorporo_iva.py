"""Comparison tests: scorporo_iva vs avvocatoandreani.it (Scorporo IVA e Calcolo IVA Inversa).

Norma: DPR 633/1972 (aliquote 4, 5, 10, 22%).
Site page: /servizi/scorporo-iva-calcoli-percentuali-frequenti.php
  - "Scorporo IVA"   (X(01) importo, Y(01) aliquota, Op01)  -> imponibile ("al netto dell'IVA")
  - "Iva Scorporata" (Y(02) aliquota, X(02) importo, Op02)  -> IVA scorporata
  NumDec is left at 2 (default).
Rounding convention: the tool rounds the imponibile and gets the IVA as importo - imponibile
(computed on unrounded values, then rounded); the site rounds each result independently,
so a one-cent divergence on the IVA is possible (see the boundary cases).

Phase 3 verdict: convention. DPR 633/1972 fixes no rounding rule for scorporo; the only euro
rounding rule (reg. CE 1103/97 art. 5, half up, for conversions) does not govern it. Both
sides are defensible: the tool keeps imponibile + iva == importo_ivato, the site rounds
each figure alone (so on 1,17 at 4% it shows 1,13 + 0,05 = 1,18 != 1,17). The two boundary
cases (0,13 and 1,17 at 4%) fail by one cent on exact half cents; the tool's float round()
is not half-up there (open point for the coordinator, no code change made).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/scorporo-iva-calcoli-percentuali-frequenti.php"


def _tool(importo, aliquota):
    from src.tools.varie import scorporo_iva
    fn = getattr(scorporo_iva, "fn", scorporo_iva)
    return fn(importo_ivato=importo, aliquota=aliquota)


def _fmt(v):
    return str(v).replace(".", ",")


def _run_op(page, op, fields):
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    for name, val in fields.items():
        page.fill(f"input[name='{name}']", val)
    # plain click (force=True does not trigger the POST on this form)
    page.click(f"input[name='{op}']")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3500)
    # the result is printed after the inputs, in the same cell as the pressed button
    cell = page.locator(f"td.c:has(input[name='{op}'])").first.inner_text()
    nums = re.findall(r"\d[\d\.]*,\d+|\d[\d\.]*", cell.replace("\xa0", " ").split("%")[-1])
    assert nums, f"nessun risultato letto dal sito: {cell!r}"
    return parse_euro(nums[-1])


def _site(page, importo, aliquota):
    imp = _run_op(page, "Op01", {"X(01)": _fmt(importo), "Y(01)": _fmt(aliquota)})
    iva = _run_op(page, "Op02", {"X(02)": _fmt(importo), "Y(02)": _fmt(aliquota)})
    return imp, iva


def _compare(page, importo, aliquota, label):
    r = _tool(importo, aliquota)
    imp, iva = _site(page, importo, aliquota)
    assert_close(r["imponibile"], imp, tolerance=0.01, label=f"imponibile_{label}")
    assert_close(r["iva"], iva, tolerance=0.01, label=f"iva_{label}")


class TestScorporoIvaSito:

    def test_122_al_22(self, page):
        """Piano: imponibile 100,00; IVA 22,00."""
        _compare(page, 122, 22, "122_22")

    def test_1000_al_22(self, page):
        """Piano: imponibile 819,67; IVA 180,33."""
        _compare(page, 1000, 22, "1000_22")

    def test_100_al_4(self, page):
        """Piano: imponibile 96,15; IVA 3,85."""
        _compare(page, 100, 4, "100_4")

    def test_105_al_5(self, page):
        """Piano: imponibile 100,00; IVA 5,00 (Tabella A)."""
        _compare(page, 105, 5, "105_5")

    def test_1234_56_al_10(self, page):
        """Piano: imponibile 1.122,33; IVA 112,23."""
        _compare(page, 1234.56, 10, "1234_56_10")

    def test_importo_minimo_0_01(self, page):
        """Piano: imponibile 0,01; IVA 0,00 (limite: arrotondamento)."""
        _compare(page, 0.01, 22, "0_01_22")

    def test_limite_arrotondamento_0_13_al_4(self, page):
        """Limite: 0,13 al 4% -> imponibile 0,125 (0,13), IVA esatta 0,005 (0,01);
        il tool ottiene l'IVA per differenza (0,00)."""
        _compare(page, 0.13, 4, "0_13_4")

    def test_limite_arrotondamento_1_17_al_4(self, page):
        """Limite: 1,17 al 4% -> imponibile 1,125 (1,13), IVA esatta 0,045 (0,05);
        per differenza il tool darebbe 0,04."""
        _compare(page, 1.17, 4, "1_17_4")

    def test_importo_grande(self, page):
        """Limite: importo elevato 99999,99 al 22%."""
        _compare(page, 99999.99, 22, "99999_99_22")

    def test_aliquota_non_prevista_21(self, page):
        """Piano: errore, aliquota non tra 4, 5, 10, 22. Il sito accetta ogni aliquota."""
        r = _tool(100, 21)
        assert "errore" in r
        pytest.skip("il sito accetta qualunque aliquota: nessun confronto possibile (tool: errore)")
