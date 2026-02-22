"""Arithmetic verification tests for volontaria giurisdizione tools."""
from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.fatturazione_avvocati")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestParcellaVolontaria:
    def test_basic(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=10000, livello="medio")
        assert r["totale_compenso"] > 0
        assert len(r["fasi"]) == 2  # studio + trattazione

    def test_min_max(self):
        r_min = _call("parcella_volontaria_giurisdizione", valore_causa=10000, livello="min")
        r_max = _call("parcella_volontaria_giurisdizione", valore_causa=10000, livello="max")
        assert r_min["totale_compenso"] < r_max["totale_compenso"]

    def test_fasi_selection(self):
        r_all = _call("parcella_volontaria_giurisdizione", valore_causa=10000, livello="medio")
        r_studio = _call("parcella_volontaria_giurisdizione", valore_causa=10000, livello="medio", fasi=["studio"])
        assert len(r_studio["fasi"]) == 1
        assert r_studio["totale_compenso"] < r_all["totale_compenso"]

    def test_invalid_livello(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=10000, livello="sbagliato")
        assert "errore" in r

    def test_invalid_fase(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=10000, fasi=["istruttoria"])
        assert "errore" in r

    def test_scaglioni_crescenti(self):
        v1 = _call("parcella_volontaria_giurisdizione", valore_causa=3000, livello="medio")
        v2 = _call("parcella_volontaria_giurisdizione", valore_causa=15000, livello="medio")
        v3 = _call("parcella_volontaria_giurisdizione", valore_causa=40000, livello="medio")
        v4 = _call("parcella_volontaria_giurisdizione", valore_causa=150000, livello="medio")
        v5 = _call("parcella_volontaria_giurisdizione", valore_causa=400000, livello="medio")
        assert v1["totale_compenso"] < v2["totale_compenso"]
        assert v2["totale_compenso"] < v3["totale_compenso"]
        assert v3["totale_compenso"] < v4["totale_compenso"]
        assert v4["totale_compenso"] < v5["totale_compenso"]

    def test_oltre_scaglione(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=600000, livello="medio")
        assert r["scaglione"] == "oltre 520.000€"
        assert r["totale_compenso"] > 0

    def test_tabella_scaglione_5200_medio(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=3000, livello="medio")
        assert_close(r["totale_compenso"], 425.0, tolerance=1.0, label="vj_5200_medio")

    def test_tabella_scaglione_26000_medio(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=15000, livello="medio")
        assert_close(r["totale_compenso"], 1418.0, tolerance=1.0, label="vj_26000_medio")

    def test_tabella_scaglione_52000_medio(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=40000, livello="medio")
        assert_close(r["totale_compenso"], 2336.0, tolerance=1.0, label="vj_52000_medio")

    def test_tabella_scaglione_260000_medio(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=150000, livello="medio")
        assert_close(r["totale_compenso"], 3329.0, tolerance=1.0, label="vj_260000_medio")

    def test_tabella_scaglione_520000_medio(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=400000, livello="medio")
        assert_close(r["totale_compenso"], 4536.0, tolerance=1.0, label="vj_520000_medio")


class TestPreventivoVolontaria:
    def test_arithmetic(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000, livello="medio")
        d = r["dettaglio_calcoli"]
        # SG 15%
        assert_close(d["spese_generali_15pct"], round(d["totale_compensi"] * 0.15, 2), tolerance=0.01, label="vg_sg")
        # CPA 4%
        subtotale = d["totale_compensi"] + d["spese_generali_15pct"]
        assert_close(d["cpa_4pct"], round(subtotale * 0.04, 2), tolerance=0.01, label="vg_cpa")

    def test_iva_arithmetic(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000, livello="medio")
        d = r["dettaglio_calcoli"]
        assert_close(d["iva_22pct"], round(d["imponibile_iva"] * 0.22, 2), tolerance=0.01, label="vg_iva")

    def test_no_sg(self):
        r_sg = _call("preventivo_volontaria_giurisdizione", valore_causa=10000, livello="medio", spese_generali=True)
        r_no = _call("preventivo_volontaria_giurisdizione", valore_causa=10000, livello="medio", spese_generali=False)
        assert r_no["dettaglio_calcoli"]["spese_generali_15pct"] == 0.0
        assert r_sg["dettaglio_calcoli"]["totale_onorari"] > r_no["dettaglio_calcoli"]["totale_onorari"]

    def test_no_iva(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000, livello="medio", iva=False)
        assert r["dettaglio_calcoli"]["iva_22pct"] == 0.0

    def test_testo_preventivo_presente(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000, livello="medio")
        assert "PREVENTIVO VOLONTARIA GIURISDIZIONE" in r["testo_preventivo"]
        assert "TOTALE ONORARI" in r["testo_preventivo"]

    def test_riferimento_normativo(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000, livello="medio")
        assert "DM 147/2022" in r["riferimento_normativo"]
        assert "Tab. 7" in r["riferimento_normativo"]
