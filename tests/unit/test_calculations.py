"""Unit tests for core calculation tools."""

import pytest


def _call(module_path, fn_name, **kwargs):
    import importlib
    mod = importlib.import_module(module_path)
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestInteressiLegali:

    def test_basic_semplici(self):
        r = _call("src.tools.tassi_interessi", "interessi_legali",
                  capitale=1000, data_inizio="2020-01-01", data_fine="2021-01-01", tipo="semplici")
        assert r["capitale"] == 1000
        assert r["totale_interessi"] > 0
        assert r["montante"] == pytest.approx(r["capitale"] + r["totale_interessi"], abs=0.01)

    def test_date_order_error(self):
        r = _call("src.tools.tassi_interessi", "interessi_legali",
                  capitale=1000, data_inizio="2021-01-01", data_fine="2020-01-01")
        assert "errore" in r

    def test_returns_periodi(self):
        r = _call("src.tools.tassi_interessi", "interessi_legali",
                  capitale=5000, data_inizio="2019-01-01", data_fine="2020-01-01")
        assert isinstance(r["periodi"], list)
        assert len(r["periodi"]) >= 1
        assert "tasso_pct" in r["periodi"][0]


class TestCalcoloIrpef:

    def test_first_bracket_autonomo(self):
        # 20000 reddito → all in first bracket (23%) → imposta_lorda = 4600
        r = _call("src.tools.dichiarazione_redditi", "calcolo_irpef",
                  reddito_complessivo=20000, tipo_reddito="autonomo")
        assert r["imposta_lorda"] == pytest.approx(4600.0, abs=1.0)

    def test_negative_income_error(self):
        r = _call("src.tools.dichiarazione_redditi", "calcolo_irpef",
                  reddito_complessivo=-1000)
        assert "errore" in r

    def test_dipendente_has_detrazioni(self):
        r = _call("src.tools.dichiarazione_redditi", "calcolo_irpef",
                  reddito_complessivo=20000, tipo_reddito="dipendente")
        assert r["detrazioni"]["lavoro"] > 0
        assert r["imposta_netta"] < r["imposta_lorda"]

    def test_returns_required_keys(self):
        r = _call("src.tools.dichiarazione_redditi", "calcolo_irpef",
                  reddito_complessivo=30000)
        for key in ("imposta_lorda", "imposta_netta", "totale_imposte", "reddito_netto"):
            assert key in r


class TestRivalutazioneMonetaria:

    def test_basic_no_interessi(self):
        r = _call("src.tools.rivalutazioni_istat", "rivalutazione_monetaria",
                  capitale=1000, data_inizio="2010-01-01", data_fine="2015-01-01",
                  con_interessi_legali=False)
        assert r["capitale_rivalutato"] == pytest.approx(1049.47, abs=1.0)
        assert r["coefficiente_rivalutazione"] > 1.0

    def test_date_order_error(self):
        r = _call("src.tools.rivalutazioni_istat", "rivalutazione_monetaria",
                  capitale=1000, data_inizio="2020-01-01", data_fine="2019-01-01")
        assert "errore" in r

    def test_rivalutato_greater_than_original(self):
        r = _call("src.tools.rivalutazioni_istat", "rivalutazione_monetaria",
                  capitale=1000, data_inizio="2010-01-01", data_fine="2020-01-01",
                  con_interessi_legali=False)
        assert r["capitale_rivalutato"] > 1000


class TestContributoUnificato:

    def test_scaglione_basso(self):
        r = _call("src.tools.atti_giudiziari", "contributo_unificato",
                  valore_causa=5000, tipo_procedimento="cognizione", grado="primo")
        assert r["importo_dovuto"] == pytest.approx(98.0, abs=1.0)

    def test_scaglione_alto(self):
        r = _call("src.tools.atti_giudiziari", "contributo_unificato",
                  valore_causa=200000, tipo_procedimento="cognizione", grado="primo")
        assert r["importo_dovuto"] == pytest.approx(759.0, abs=1.0)

    def test_appello_maggiorazione(self):
        r_primo = _call("src.tools.atti_giudiziari", "contributo_unificato",
                        valore_causa=50000, tipo_procedimento="cognizione", grado="primo")
        r_appello = _call("src.tools.atti_giudiziari", "contributo_unificato",
                          valore_causa=50000, tipo_procedimento="cognizione", grado="appello")
        assert r_appello["importo_dovuto"] > r_primo["importo_dovuto"]

    def test_returns_norma(self):
        r = _call("src.tools.atti_giudiziari", "contributo_unificato",
                  valore_causa=10000)
        assert "DPR 115/2002" in r["riferimento_normativo"]


class TestDannoBiologicoMicro:

    def test_basic(self):
        r = _call("src.tools.risarcimento_danni", "danno_biologico_micro",
                  percentuale_invalidita=3, eta_vittima=30)
        assert r["danno_permanente"] == pytest.approx(2861.3, abs=5.0)
        assert r["totale_risarcimento"] > 0

    def test_out_of_range_error(self):
        r = _call("src.tools.risarcimento_danni", "danno_biologico_micro",
                  percentuale_invalidita=10, eta_vittima=30)
        assert "errore" in r

    def test_age_reduces_value(self):
        r_young = _call("src.tools.risarcimento_danni", "danno_biologico_micro",
                        percentuale_invalidita=5, eta_vittima=10)
        r_old = _call("src.tools.risarcimento_danni", "danno_biologico_micro",
                      percentuale_invalidita=5, eta_vittima=70)
        assert r_young["danno_permanente"] > r_old["danno_permanente"]

    def test_personalizzazione_increases_total(self):
        r_base = _call("src.tools.risarcimento_danni", "danno_biologico_micro",
                       percentuale_invalidita=3, eta_vittima=30, personalizzazione_pct=0)
        r_pers = _call("src.tools.risarcimento_danni", "danno_biologico_micro",
                       percentuale_invalidita=3, eta_vittima=30, personalizzazione_pct=20)
        assert r_pers["totale_risarcimento"] > r_base["totale_risarcimento"]
