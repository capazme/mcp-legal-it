"""Comparison tests: scorporo_iva — arithmetic verification.

The site's scorporo calculator loads via iframe and is impractical to automate.
Since scorporo IVA is a deterministic formula (importo / (1 + aliquota/100)),
we verify our implementation against known correct values.
"""

from tests.comparison.conftest import assert_close


def _our_scorporo(importo_ivato, aliquota=22):
    from src.tools.varie import scorporo_iva
    fn = getattr(scorporo_iva, "fn", scorporo_iva)
    return fn(importo_ivato=importo_ivato, aliquota=aliquota)


class TestScorporoIva:

    def test_122_euro_22pct(self):
        """122 ivato al 22% => imponibile=100, iva=22."""
        r = _our_scorporo(122, 22)
        assert_close(r["imponibile"], 100.0, tolerance=0.01, label="scorporo_122")
        assert_close(r["iva"], 22.0, tolerance=0.01, label="iva_122")

    def test_1000_euro_22pct(self):
        """1000 ivato al 22% => imponibile=819.67, iva=180.33."""
        r = _our_scorporo(1000, 22)
        assert_close(r["imponibile"], 819.67, tolerance=0.01, label="scorporo_1000")
        assert_close(r["iva"], 180.33, tolerance=0.01, label="iva_1000")

    def test_110_euro_10pct(self):
        """110 ivato al 10% => imponibile=100, iva=10."""
        r = _our_scorporo(110, 10)
        assert_close(r["imponibile"], 100.0, tolerance=0.01, label="scorporo_110")
        assert_close(r["iva"], 10.0, tolerance=0.01, label="iva_110")

    def test_104_euro_4pct(self):
        """104 ivato al 4% => imponibile=100, iva=4."""
        r = _our_scorporo(104, 4)
        assert_close(r["imponibile"], 100.0, tolerance=0.01, label="scorporo_104")
        assert_close(r["iva"], 4.0, tolerance=0.01, label="iva_104")

    def test_sum_equals_input(self):
        """Imponibile + IVA must equal importo_ivato."""
        for importo in [50, 122, 500, 1000, 9999.99]:
            for aliquota in [4, 5, 10, 22]:
                r = _our_scorporo(importo, aliquota)
                assert_close(r["imponibile"] + r["iva"], importo,
                             tolerance=0.01, label=f"sum_{importo}_{aliquota}")
