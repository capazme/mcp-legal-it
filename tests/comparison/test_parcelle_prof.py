"""Arithmetic verification tests for Sezione 6 — Parcelle Professionisti."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.parcelle_professionisti")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestFatturaProfessionista:

    def test_ingegnere_ordinario(self):
        r = _call("fattura_professionista", imponibile=1000, tipo="ingegnere", regime="ordinario")
        rivalsa = 1000 * 4 / 100  # 40
        base = 1000 + 40  # 1040
        iva = base * 22 / 100  # 228.80
        ritenuta = base * 20 / 100  # 208
        netto = base + iva - ritenuta
        assert_close(r["rivalsa_inps"], 40.0, tolerance=0.01, label="rivalsa")
        assert_close(r["iva"], 228.80, tolerance=0.01, label="iva")
        assert_close(r["ritenuta_acconto"], 208.0, tolerance=0.01, label="ritenuta")
        assert_close(r["netto_a_pagare"], round(netto, 2), tolerance=0.01, label="netto")

    def test_forfettario(self):
        r = _call("fattura_professionista", imponibile=1000, tipo="architetto", regime="forfettario")
        assert r["iva"] == 0.0
        assert r["ritenuta_acconto"] == 0.0
        assert r["bollo"] == 2.0  # >77.47
        assert_close(r["netto_a_pagare"], 1000 + 40 + 2, tolerance=0.01, label="forf_netto")

    def test_psicologo(self):
        r = _call("fattura_professionista", imponibile=500, tipo="psicologo", regime="ordinario")
        assert_close(r["rivalsa_inps"], 25.0, tolerance=0.01, label="psi_rivalsa")  # 5%


class TestRitenutaAcconto:

    def test_1000_euro(self):
        r = _call("ritenuta_acconto", compenso_lordo=1000)
        assert_close(r["ritenuta"], 200.0, tolerance=0.01, label="rit_1000")
        assert_close(r["netto_percepito"], 800.0, tolerance=0.01, label="netto_1000")

    def test_custom_aliquota(self):
        r = _call("ritenuta_acconto", compenso_lordo=5000, aliquota=23)
        assert_close(r["ritenuta"], 1150.0, tolerance=0.01, label="rit_23pct")


class TestSpeseMediazione:

    def test_valore_15k_positivo(self):
        r = _call("spese_mediazione", valore_controversia=15000, esito="positivo")
        # 15000 falls in 10001-25000 bracket: positivo=480
        assert_close(r["indennita_per_parte"], 480.0, tolerance=0.01, label="med_15k")
        assert_close(r["iva_22_per_parte"], 480 * 22 / 100, tolerance=0.01, label="med_iva")

    def test_valore_3k_negativo(self):
        r = _call("spese_mediazione", valore_controversia=3000, esito="negativo")
        # 3000 falls in 1001-5000 bracket: negativo=100
        assert_close(r["indennita_per_parte"], 100.0, tolerance=0.01, label="med_3k_neg")


class TestCompensoOrario:

    def test_2h30_mezz_ora(self):
        r = _call("compenso_orario", tariffa_oraria=100, ore=2, minuti=30, arrotondamento="mezz_ora")
        assert_close(r["compenso"], 250.0, tolerance=0.01, label="2h30_mh")  # exactly 2.5h

    def test_2h10_mezz_ora(self):
        r = _call("compenso_orario", tariffa_oraria=100, ore=2, minuti=10, arrotondamento="mezz_ora")
        # 130 min → ceil(130/30)*30 = 150 min = 2.5h → 250€
        assert_close(r["compenso"], 250.0, tolerance=0.01, label="2h10_mh")

    def test_1h15_quarto_ora(self):
        r = _call("compenso_orario", tariffa_oraria=80, ore=1, minuti=15, arrotondamento="quarto_ora")
        # 75 min → ceil(75/15)*15 = 75 min = 1.25h → 100€
        assert_close(r["compenso"], 100.0, tolerance=0.01, label="1h15_qh")


class TestCompensoDellegatiVendite:

    def test_50k(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=50000)
        expected = max(50000 * 2.6 / 100, 1100)
        assert_close(r["compenso"], expected, tolerance=0.01, label="del_50k")

    def test_200k(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=200000)
        prima = 100000 * 2.6 / 100  # 2600
        seconda = 100000 * 1.5 / 100  # 1500
        assert_close(r["compenso"], round(prima + seconda, 2), tolerance=0.01, label="del_200k")


class TestFatturaEnasarco:

    def test_provvigioni_10k(self):
        r = _call("fattura_enasarco", provvigioni=10000)
        contributo = 10000 * 17 / 100  # 1700
        quota_agente = 850
        iva = 10000 * 22 / 100  # 2200
        ritenuta = 10000 * 50 / 100 * 23 / 100  # 1150
        totale = 10000 + iva
        netto = totale - ritenuta - quota_agente
        assert_close(r["contributo_enasarco"]["contributo_totale"], 1700, tolerance=0.01, label="enasarco_contr")
        assert_close(r["ritenuta_acconto"]["importo"], 1150, tolerance=0.01, label="enasarco_rit")
        assert_close(r["netto_a_pagare"], round(netto, 2), tolerance=0.01, label="enasarco_netto")


class TestTariffeMediazione:

    def test_valore_30k(self):
        r = _call("tariffe_mediazione", valore_controversia=30000)
        # 30000 falls in 25001-50000 bracket
        assert r["esito_negativo"]["indennita_per_parte"] == 360
        assert r["esito_positivo"]["indennita_per_parte"] == 720
