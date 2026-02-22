"""Arithmetic verification tests for fattura_avvocato and nota_spese."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.fatturazione_avvocati")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestFatturaAvvocato:

    def test_base(self):
        r = _call("fattura_avvocato", imponibile=1000)
        cpa = 1000 * 0.04  # 40
        imponibile_iva = 1000 + cpa  # 1040
        iva = imponibile_iva * 0.22  # 228.80
        ritenuta = 1000 * 0.20  # 200 (on raw imponibile)
        totale = imponibile_iva + iva - ritenuta  # 1068.80
        assert_close(r["cpa_4pct"], 40.0, tolerance=0.01, label="cpa")
        assert_close(r["iva_22pct"], 228.80, tolerance=0.01, label="iva")
        assert_close(r["ritenuta_acconto_20pct"], 200.0, tolerance=0.01, label="ritenuta")
        assert_close(r["netto_a_pagare"], round(totale, 2), tolerance=0.01, label="netto")

    def test_forfettario(self):
        r = _call("fattura_avvocato", imponibile=2000, regime="forfettario")
        assert r["iva_22pct"] == 0.0
        assert r["ritenuta_acconto_20pct"] == 0.0
        cpa = 2000 * 0.04  # 80
        assert_close(r["cpa_4pct"], 80.0, tolerance=0.01, label="cpa_forf")
        assert_close(r["totale_fattura"], 2080.0, tolerance=0.01, label="totale_forf")

    def test_senza_cpa(self):
        r = _call("fattura_avvocato", imponibile=1000, cpa=False)
        assert r["cpa_4pct"] == 0.0
        # IVA on imponibile only (no CPA)
        assert_close(r["iva_22pct"], 220.0, tolerance=0.01, label="iva_no_cpa")


class TestNotaSpese:

    def test_base(self):
        r = _call("nota_spese", voci=[
            {"descrizione": "Compenso fase studio", "importo": 500, "tipo": "compenso"},
            {"descrizione": "Compenso fase introduttiva", "importo": 300, "tipo": "compenso"},
        ])
        assert r["totale_compensi"] == 800.0
        # CPA on subtotale (compensi + spese generali)
        subtotale = 800.0
        cpa = round(subtotale * 0.04, 2)
        assert_close(r["cpa_4pct"], cpa, tolerance=0.01, label="cpa_nota")
        assert r["totale_nota_spese"] > 0

    def test_con_spese_generali(self):
        r = _call("nota_spese", voci=[
            {"descrizione": "Compenso", "importo": 1000, "tipo": "compenso"},
            {"descrizione": "Compenso base", "importo": 1000, "tipo": "spese_generali_15pct"},
        ])
        # spese_generali_15pct: 1000 * 0.15 = 150
        assert_close(r["totale_spese_generali_15pct"], 150.0, tolerance=0.01, label="sg_nota")
        # subtotale = 1000 (compensi) + 150 (sg) = 1150
        assert_close(r["subtotale_compensi"], 1150.0, tolerance=0.01, label="sub_nota")
