import asyncio
import importlib
import inspect

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.investimenti")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    if inspect.iscoroutinefunction(actual):
        return asyncio.run(actual(**kwargs))
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# rendimento_bot
# ---------------------------------------------------------------------------

class TestRendimentoBot:
    def test_happy_path_basic(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=182)
        assert r["valore_nominale"] == 10000
        assert r["prezzo_acquisto"] == 9800
        assert r["giorni_scadenza"] == 182
        assert r["plusvalenza_lorda"] == pytest.approx(200.0)
        assert r["imposta_sostitutiva_pct"] == 12.5
        assert r["imposta"] == pytest.approx(200 * 0.125, abs=0.01)
        assert r["commissione"] == 0.0
        assert r["guadagno_netto"] == pytest.approx(200 - 200 * 0.125, abs=0.01)
        assert r["rendimento_lordo_annuo_pct"] > 0
        assert r["rendimento_netto_annuo_pct"] > 0
        assert r["rendimento_netto_annuo_pct"] < r["rendimento_lordo_annuo_pct"]
        assert "D.Lgs. 239/1996" in r["riferimento_normativo"]

    def test_with_commissione(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800,
                  giorni_scadenza=182, commissione_pct=0.15)
        expected_commissione = 10000 * 0.15 / 100
        assert r["commissione"] == pytest.approx(expected_commissione, abs=0.01)
        assert r["guadagno_netto"] < _call(
            "rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=182
        )["guadagno_netto"]

    def test_no_plusvalenza_when_price_above_nominal(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=10100, giorni_scadenza=90)
        assert r["plusvalenza_lorda"] == pytest.approx(-100.0)
        assert r["imposta"] == 0.0
        assert r["guadagno_netto"] < 0

    def test_annualized_rendimento_formula(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=365)
        expected_lordo = (200 / 9800) * 100
        assert r["rendimento_lordo_annuo_pct"] == pytest.approx(expected_lordo, rel=1e-4)

    def test_error_giorni_zero(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=0)
        assert "errore" in r

    def test_error_giorni_negative(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=-5)
        assert "errore" in r

    def test_error_prezzo_zero(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=0, giorni_scadenza=90)
        assert "errore" in r

    def test_error_prezzo_negative(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=-100, giorni_scadenza=90)
        assert "errore" in r

    def test_short_duration_bot(self):
        r = _call("rendimento_bot", valore_nominale=5000, prezzo_acquisto=4980, giorni_scadenza=91)
        assert isinstance(r["rendimento_netto_annuo_pct"], float)
        assert r["guadagno_netto"] > 0


# ---------------------------------------------------------------------------
# rendimento_btp
# ---------------------------------------------------------------------------

class TestRendimentoBtp:
    def test_happy_path_semestrale(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=980,
                  cedola_annua_pct=3.5, anni_scadenza=5)
        assert r["valore_nominale"] == 1000
        assert r["frequenza_cedola"] == 2
        n_cedole = 5 * 2
        cedola_singola = 1000 * 0.035 / 2
        totale_lordo = cedola_singola * n_cedole
        assert r["totale_cedole_lordo"] == pytest.approx(totale_lordo, abs=0.01)
        assert r["imposta_cedole"] == pytest.approx(totale_lordo * 0.125, abs=0.01)
        assert r["totale_cedole_netto"] == pytest.approx(totale_lordo * 0.875, abs=0.01)
        assert r["plusvalenza_lorda"] == pytest.approx(20.0)
        assert r["imposta_plusvalenza"] == pytest.approx(20 * 0.125, abs=0.01)
        assert len(r["flusso_cedole"]) == n_cedole
        assert "D.Lgs. 239/1996" in r["riferimento_normativo"]

    def test_cedola_annuale(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=1000,
                  cedola_annua_pct=4.0, anni_scadenza=3, frequenza_cedola=1)
        assert r["frequenza_cedola"] == 1
        assert len(r["flusso_cedole"]) == 3
        cedola = r["flusso_cedole"][0]
        assert cedola["lorda"] == pytest.approx(40.0)
        assert cedola["netta"] == pytest.approx(40.0 * 0.875, abs=0.01)

    def test_no_plusvalenza_at_par(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=1000,
                  cedola_annua_pct=2.0, anni_scadenza=2)
        assert r["plusvalenza_lorda"] == pytest.approx(0.0)
        assert r["imposta_plusvalenza"] == pytest.approx(0.0)
        assert r["guadagno_netto_totale"] == pytest.approx(r["totale_cedole_netto"], abs=0.01)

    def test_negative_plusvalenza_no_tax(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=1050,
                  cedola_annua_pct=2.0, anni_scadenza=3)
        assert r["plusvalenza_lorda"] == pytest.approx(-50.0)
        assert r["imposta_plusvalenza"] == pytest.approx(0.0)
        assert r["plusvalenza_netta"] == pytest.approx(-50.0)

    def test_rendimento_netto_annuo_formula(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=950,
                  cedola_annua_pct=3.0, anni_scadenza=10)
        guadagno = r["guadagno_netto_totale"]
        expected = (guadagno / 950 / 10) * 100
        assert r["rendimento_netto_annuo_pct"] == pytest.approx(expected, rel=1e-4)

    def test_error_anni_zero(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=980,
                  cedola_annua_pct=3.5, anni_scadenza=0)
        assert "errore" in r

    def test_error_anni_negative(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=980,
                  cedola_annua_pct=3.5, anni_scadenza=-2)
        assert "errore" in r

    def test_error_prezzo_zero(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=0,
                  cedola_annua_pct=3.5, anni_scadenza=5)
        assert "errore" in r


# ---------------------------------------------------------------------------
# pronti_termine
# ---------------------------------------------------------------------------

class TestProntiTermine:
    def test_titoli_stato_aliquota_125(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=90,
                  tipo_sottostante="titoli_stato")
        interessi_lordi = 10000 * 0.03 * 90 / 365
        imposta = interessi_lordi * 0.125
        assert r["aliquota_pct"] == 12.5
        assert r["interessi_lordi"] == pytest.approx(interessi_lordi, abs=0.01)
        assert r["imposta"] == pytest.approx(imposta, abs=0.01)
        assert r["interessi_netti"] == pytest.approx(interessi_lordi - imposta, abs=0.01)
        assert "D.Lgs. 239/1996" in r["riferimento_normativo"]

    def test_altro_aliquota_26(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=90,
                  tipo_sottostante="altro")
        assert r["aliquota_pct"] == 26.0
        interessi_lordi = 10000 * 0.03 * 90 / 365
        imposta = interessi_lordi * 0.26
        assert r["imposta"] == pytest.approx(imposta, abs=0.01)

    def test_default_tipo_sottostante(self):
        r = _call("pronti_termine", capitale=5000, tasso_lordo_pct=2.5, giorni=30)
        assert r["tipo_sottostante"] == "titoli_stato"
        assert r["aliquota_pct"] == 12.5

    def test_rendimento_netto_annuo_formula(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=365,
                  tipo_sottostante="titoli_stato")
        assert r["rendimento_netto_annuo_pct"] == pytest.approx(3.0 * 0.875, rel=1e-4)

    def test_error_giorni_zero(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=2.0, giorni=0)
        assert "errore" in r

    def test_error_giorni_negative(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=2.0, giorni=-1)
        assert "errore" in r

    def test_error_capitale_zero(self):
        r = _call("pronti_termine", capitale=0, tasso_lordo_pct=2.0, giorni=30)
        assert "errore" in r

    def test_error_capitale_negative(self):
        r = _call("pronti_termine", capitale=-1000, tasso_lordo_pct=2.0, giorni=30)
        assert "errore" in r

    def test_higher_tax_for_altro(self):
        r_stato = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=180,
                        tipo_sottostante="titoli_stato")
        r_altro = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=180,
                        tipo_sottostante="altro")
        assert r_altro["imposta"] > r_stato["imposta"]
        assert r_altro["interessi_netti"] < r_stato["interessi_netti"]


# ---------------------------------------------------------------------------
# rendimento_buoni_postali
# ---------------------------------------------------------------------------

class TestRendimentoBuoniPostali:
    def test_ordinario_10_anni(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=10)
        assert r["tipo"] == "ordinario"
        assert r["anni"] == 10
        assert r["importo"] == 10000
        assert r["montante_lordo"] > 10000
        assert r["interessi_lordi"] > 0
        assert r["imposta"] == pytest.approx(r["interessi_lordi"] * 0.125, abs=0.01)
        assert r["montante_netto"] == pytest.approx(r["montante_lordo"] - r["imposta"], abs=0.01)
        assert r["interessi_netti"] == pytest.approx(r["interessi_lordi"] - r["imposta"], abs=0.01)
        assert r["rendimento_netto_annuo_pct"] > 0
        assert len(r["dettaglio_annuale"]) == 10
        assert "D.Lgs. 239/1996" in r["riferimento_normativo"]

    def test_tipo_3x4(self):
        r = _call("rendimento_buoni_postali", importo=5000, tipo="3x4", anni=12)
        assert r["tipo"] == "3x4"
        assert r["anni"] == 12

    def test_tipo_4x4(self):
        r = _call("rendimento_buoni_postali", importo=5000, tipo="4x4", anni=8)
        assert r["anni"] == 8
        assert r["montante_lordo"] > 5000

    def test_tipo_dedicato_minori(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="dedicato_minori", anni=18)
        assert r["anni"] == 18
        assert len(r["dettaglio_annuale"]) == 18

    def test_anni_capped_at_max(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="ordinario", anni=100)
        assert r["anni"] == 20

    def test_anni_capped_3x4(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="3x4", anni=99)
        assert r["anni"] == 12

    def test_dettaglio_yearly_compounding(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=3)
        d = r["dettaglio_annuale"]
        assert d[0]["anno"] == 1
        assert d[1]["anno"] == 2
        assert d[2]["anno"] == 3
        assert d[1]["montante_lordo"] > d[0]["montante_lordo"]

    def test_error_importo_zero(self):
        r = _call("rendimento_buoni_postali", importo=0, tipo="ordinario", anni=5)
        assert "errore" in r

    def test_error_importo_negative(self):
        r = _call("rendimento_buoni_postali", importo=-500, tipo="ordinario", anni=5)
        assert "errore" in r

    def test_error_anni_zero(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="ordinario", anni=0)
        assert "errore" in r

    def test_error_tipo_invalido(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="inesistente", anni=5)
        assert "errore" in r
        assert "inesistente" in r["errore"]

    def test_rendimento_netto_annuo_formula(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=5)
        expected = ((r["montante_netto"] / 10000) ** (1 / 5) - 1) * 100
        assert r["rendimento_netto_annuo_pct"] == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# confronto_investimenti
# ---------------------------------------------------------------------------

class TestConfronto:
    _INVESTIMENTI_BASE = [
        {"nome": "BOT", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        {"nome": "Obbligazione", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "altro", "durata_anni": 1},
    ]

    def test_happy_path_two_instruments(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=self._INVESTIMENTI_BASE)
        assert r["importo"] == 10000
        assert len(r["classifica"]) == 2
        assert r["migliore"] is not None
        assert "nota" in r

    def test_titoli_stato_vs_altro_tax_impact(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "BTP", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
            {"nome": "Corp", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "altro", "durata_anni": 1},
        ])
        classifica = {x["nome"]: x for x in r["classifica"]}
        assert classifica["BTP"]["aliquota_pct"] == 12.5
        assert classifica["Corp"]["aliquota_pct"] == 26.0
        assert classifica["BTP"]["rendimento_netto_pct"] > classifica["Corp"]["rendimento_netto_pct"]
        assert r["migliore"] == "BTP"

    def test_sorted_by_rendimento_netto_desc(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "A", "rendimento_lordo_pct": 2.0, "tipo_tassazione": "altro", "durata_anni": 1},
            {"nome": "B", "rendimento_lordo_pct": 5.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
            {"nome": "C", "rendimento_lordo_pct": 1.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        ])
        rendimenti = [x["rendimento_netto_pct"] for x in r["classifica"]]
        assert rendimenti == sorted(rendimenti, reverse=True)

    def test_montante_netto_formula(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "X", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "titoli_stato", "durata_anni": 2},
        ])
        item = r["classifica"][0]
        expected_lordo = 10000 * (1.04 ** 2)
        expected_imposta = (expected_lordo - 10000) * 0.125
        expected_netto = expected_lordo - expected_imposta
        assert item["montante_lordo"] == pytest.approx(expected_lordo, abs=0.01)
        assert item["imposta"] == pytest.approx(expected_imposta, abs=0.01)
        assert item["montante_netto"] == pytest.approx(expected_netto, abs=0.01)
        assert item["guadagno_netto"] == pytest.approx(expected_netto - 10000, abs=0.01)

    def test_default_tipo_tassazione_altro(self):
        r = _call("confronto_investimenti", importo=5000, investimenti=[
            {"nome": "Z", "rendimento_lordo_pct": 3.0},
        ])
        assert r["classifica"][0]["aliquota_pct"] == 26.0

    def test_single_instrument_migliore(self):
        r = _call("confronto_investimenti", importo=1000, investimenti=[
            {"nome": "Solo", "rendimento_lordo_pct": 2.5, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        ])
        assert r["migliore"] == "Solo"
        assert len(r["classifica"]) == 1

    def test_error_importo_zero(self):
        r = _call("confronto_investimenti", importo=0, investimenti=self._INVESTIMENTI_BASE)
        assert "errore" in r

    def test_error_importo_negative(self):
        r = _call("confronto_investimenti", importo=-100, investimenti=self._INVESTIMENTI_BASE)
        assert "errore" in r

    def test_error_empty_list(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[])
        assert "errore" in r

    def test_guadagno_netto_correct(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "T", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        ])
        item = r["classifica"][0]
        assert item["guadagno_netto"] == pytest.approx(item["montante_netto"] - 10000, abs=0.01)
