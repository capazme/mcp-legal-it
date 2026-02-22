"""Arithmetic verification tests for Sezione 12 — Applicazioni Varie (extra tools)."""

from tests.comparison.conftest import assert_close


def _call_varie(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.varie")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestDecodificaCodiceFiscale:

    def test_known_cf(self):
        # RSSMRA85M01H501Z is a typical test CF for Mario Rossi born in Rome 01/08/1985
        r = _call_varie("decodifica_codice_fiscale", codice_fiscale="RSSMRA85M01H501Z")
        assert r["dati"]["sesso"] == "M"
        assert r["dati"]["anno_nascita_stimato"] == 1985

    def test_donna(self):
        r = _call_varie("decodifica_codice_fiscale", codice_fiscale="RSSMRA85M41H501E")
        assert r["dati"]["sesso"] == "F"


class TestVerificaIban:

    def test_valid_italian_iban(self):
        r = _call_varie("verifica_iban", iban="IT60X0542811101000000123456")
        assert r["valido"] is True
        assert r["componenti"]["paese"] == "IT"

    def test_invalid_iban(self):
        r = _call_varie("verifica_iban", iban="IT00X0542811101000000123456")
        assert r["valido"] is False


class TestCalcoloEtaAnagrafica:

    def test_basic(self):
        r = _call_varie("calcolo_eta_anagrafica", data_nascita="1990-06-15", data_riferimento="2025-06-15")
        assert r["eta_anni"] == 35


class TestPrescrizioneDiritti:

    def test_ordinaria(self):
        r = _call_varie("prescrizione_diritti", tipo_diritto="ordinaria", data_evento="2020-01-01")
        assert r["termine_anni"] == 10
        assert "2030" in r["data_prescrizione"]

    def test_risarcimento(self):
        r = _call_varie("prescrizione_diritti", tipo_diritto="risarcimento_danni", data_evento="2022-06-01")
        assert r["termine_anni"] == 5


class TestTassoAlcolemico:

    def test_basic(self):
        r = _call_varie("tasso_alcolemico", peso_kg=80, sesso="M",
                        unita_alcoliche=1, ore_trascorse=0)
        assert r["tasso_attuale_g_l"] > 0
        assert "fascia_sanzione_cds" in r

    def test_donna_piu_alto(self):
        params = dict(peso_kg=60, unita_alcoliche=2, ore_trascorse=0)
        r_m = _call_varie("tasso_alcolemico", sesso="M", **params)
        r_f = _call_varie("tasso_alcolemico", sesso="F", **params)
        # Women have higher BAC for same intake/weight (lower Widmark coefficient)
        assert r_f["tasso_attuale_g_l"] > r_m["tasso_attuale_g_l"]
