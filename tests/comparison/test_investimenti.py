"""Arithmetic verification tests for Sezione 10 — Investimenti."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.investimenti")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestRendimentoBot:

    def test_bot_6mesi(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9850,
                   giorni_scadenza=182, commissione_pct=0.15)
        plusvalenza = 150  # 10000 - 9850
        imposta = 150 * 12.5 / 100  # 18.75
        commissione = 10000 * 0.15 / 100  # 15
        netto = 150 - 18.75 - 15
        assert_close(r["plusvalenza_lorda"], 150.0, tolerance=0.01, label="bot_plus")
        assert_close(r["imposta"], 18.75, tolerance=0.01, label="bot_imp")
        assert_close(r["guadagno_netto"], round(netto, 2), tolerance=0.01, label="bot_netto")

    def test_rendimento_annualizzato(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9700,
                   giorni_scadenza=365)
        # Plus 300, imposta 37.5, netto 262.5
        rend = (262.5 / 9700) * 100
        assert_close(r["rendimento_netto_annuo_pct"], round(rend, 4), tolerance=0.01, label="bot_rend")


class TestRendimentoBtp:

    def test_btp_5_anni(self):
        r = _call("rendimento_btp", valore_nominale=10000, prezzo_acquisto=9800,
                   cedola_annua_pct=3.0, anni_scadenza=5)
        cedola_annua_lorda = 10000 * 3 / 100  # 300
        totale_cedole = 300 * 5  # 1500
        imposta_cedole = 1500 * 12.5 / 100  # 187.5
        cedole_nette = 1500 - 187.5  # 1312.5
        plusvalenza = 200
        imp_plus = 200 * 12.5 / 100  # 25
        assert_close(r["totale_cedole_lordo"], 1500.0, tolerance=0.01, label="btp_ced")
        assert_close(r["imposta_cedole"], 187.5, tolerance=0.01, label="btp_imp_ced")
        assert_close(r["plusvalenza_lorda"], 200.0, tolerance=0.01, label="btp_plus")


class TestProntiTermine:

    def test_pct_titoli_stato(self):
        r = _call("pronti_termine", capitale=100000, tasso_lordo_pct=3.5, giorni=90,
                   tipo_sottostante="titoli_stato")
        interessi = 100000 * 3.5 / 100 * 90 / 365
        imposta = interessi * 12.5 / 100
        netti = interessi - imposta
        assert_close(r["interessi_lordi"], round(interessi, 2), tolerance=0.01, label="pct_lordi")
        assert_close(r["interessi_netti"], round(netti, 2), tolerance=0.01, label="pct_netti")

    def test_pct_altro(self):
        r = _call("pronti_termine", capitale=50000, tasso_lordo_pct=4.0, giorni=180,
                   tipo_sottostante="altro")
        interessi = 50000 * 4.0 / 100 * 180 / 365
        imposta = interessi * 26 / 100
        assert_close(r["aliquota_pct"], 26.0, tolerance=0.01, label="pct_aliq")
        assert_close(r["imposta"], round(imposta, 2), tolerance=0.01, label="pct_imp_altro")


class TestRendimentoBuoniPostali:

    def test_ordinario_5_anni(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=5)
        assert r["anni"] == 5
        assert r["montante_lordo"] > 10000
        assert r["montante_netto"] < r["montante_lordo"]
        assert r["imposta_sostitutiva_pct"] == 12.5

    def test_tipo_invalido(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="inesistente", anni=5)
        assert "errore" in r


class TestConfrontoInvestimenti:

    def test_confronto_2_strumenti(self):
        r = _call("confronto_investimenti", importo=100000, investimenti=[
            {"nome": "BTP", "rendimento_lordo_pct": 3.5, "tipo_tassazione": "titoli_stato", "durata_anni": 5},
            {"nome": "Corporate bond", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "altro", "durata_anni": 5},
        ])
        assert len(r["classifica"]) == 2
        # BTP: 3.5 * (1 - 12.5/100) = 3.0625
        # Corp: 4.0 * (1 - 26/100) = 2.96
        assert r["migliore"] == "BTP"  # BTP has higher net yield
