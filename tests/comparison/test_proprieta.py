"""Arithmetic verification tests for Sezione 9 — Proprietà e Successioni."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.proprieta_successioni")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestImposteSuccessione:

    def test_coniuge_sotto_franchigia(self):
        r = _call("imposte_successione", valore_beni=500000, parentela="coniuge_linea_retta")
        assert r["franchigia"] == 1_000_000
        assert r["imposta_successione"] == 0.0

    def test_coniuge_sopra_franchigia(self):
        r = _call("imposte_successione", valore_beni=1_500_000, parentela="coniuge_linea_retta")
        base = 500000  # 1.5M - 1M franchigia
        expected = base * 4 / 100
        assert_close(r["imposta_successione"], expected, tolerance=0.01, label="succ_coniuge")

    def test_fratelli(self):
        r = _call("imposte_successione", valore_beni=200000, parentela="fratelli_sorelle")
        base = max(200000 - 100000, 0)  # franchigia 100k
        expected = base * 6 / 100
        assert_close(r["imposta_successione"], expected, tolerance=0.01, label="succ_fratelli")

    def test_con_immobili_prima_casa(self):
        r = _call("imposte_successione", valore_beni=500000, parentela="coniuge_linea_retta",
                   immobili=True, prima_casa=True)
        assert r["imposta_ipotecaria"] == 200
        assert r["imposta_catastale"] == 200


class TestCalcoloImu:

    def test_a2_standard(self):
        r = _call("calcolo_imu", rendita_catastale=1000, categoria="A/2", aliquota_comunale=0.86)
        rivalutata = 1000 * 1.05  # 1050
        base = 1050 * 160  # 168000
        imu = base * 0.86 / 100
        assert_close(r["base_imponibile"], base, tolerance=0.01, label="imu_base")
        assert_close(r["imu_annua"], round(imu, 2), tolerance=0.01, label="imu_annua")

    def test_prima_casa_esente(self):
        r = _call("calcolo_imu", rendita_catastale=500, categoria="A/2", prima_casa=True)
        assert r["imu_annua"] == 0.0

    def test_prima_casa_lusso(self):
        r = _call("calcolo_imu", rendita_catastale=2000, categoria="A/1", prima_casa=True, aliquota_comunale=0.60)
        # A/1 prima casa: IMU dovuta ma con detrazione 200€
        assert r["imu_annua"] > 0 or r.get("detrazione_prima_casa") == 200

    def test_c1_negozio(self):
        r = _call("calcolo_imu", rendita_catastale=1000, categoria="C/1")
        # C/1: moltiplicatore 55
        base = 1000 * 1.05 * 55
        assert_close(r["base_imponibile"], base, tolerance=0.01, label="imu_c1")


class TestImposteCompravendita:

    def test_prima_casa_privato(self):
        r = _call("imposte_compravendita", prezzo=200000, tipo_immobile="abitazione", prima_casa=True)
        # 2% su prezzo, minimo 1000
        registro = max(200000 * 2 / 100, 1000)
        assert_close(r["imposta_registro"], registro, tolerance=0.01, label="comp_prima")
        assert r["imposta_ipotecaria"] == 50
        assert r["imposta_catastale"] == 50

    def test_seconda_casa_privato(self):
        r = _call("imposte_compravendita", prezzo=200000, tipo_immobile="abitazione", prima_casa=False)
        registro = max(200000 * 9 / 100, 1000)
        assert_close(r["imposta_registro"], registro, tolerance=0.01, label="comp_seconda")

    def test_da_costruttore_prima_casa(self):
        r = _call("imposte_compravendita", prezzo=200000, prima_casa=True, da_costruttore=True)
        iva = 200000 * 4 / 100  # 4% prima casa
        assert_close(r["iva"], iva, tolerance=0.01, label="comp_costr_iva")


class TestPensioneReversibilita:

    def test_coniuge_solo(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000,
                   beneficiari={"coniuge": True, "figli": 0})
        assert r["quota_pct"] == 60
        assert_close(r["pensione_lorda_annua"], 12000.0, tolerance=0.01, label="rev_coniuge")

    def test_coniuge_1figlio(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000,
                   beneficiari={"coniuge": True, "figli": 1})
        assert r["quota_pct"] == 80
        assert_close(r["pensione_lorda_annua"], 16000.0, tolerance=0.01, label="rev_coniuge_figlio")

    def test_con_riduzione_reddito(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000,
                   beneficiari={"coniuge": True, "figli": 0}, reddito_beneficiario=50000)
        # 50000 / 7781.93 ~ 6.4 > 5 → riduzione 50%
        assert r["riduzione_cumulo"]["riduzione_pct"] == 50
        assert_close(r["pensione_netta_annua"], 6000.0, tolerance=0.01, label="rev_ridotta")


class TestCedolareSecca:

    def test_libero(self):
        r = _call("cedolare_secca", canone_annuo=12000, tipo_contratto="libero", irpef_marginale=38)
        assert_close(r["cedolare_secca"]["imposta"], 12000 * 21 / 100, tolerance=0.01, label="ced_lib")
        irpef_base = 12000 * 0.95
        assert_close(r["irpef_ordinaria"]["base_imponibile_95_pct"], irpef_base, tolerance=0.01, label="ced_base")

    def test_concordato(self):
        r = _call("cedolare_secca", canone_annuo=12000, tipo_contratto="concordato")
        assert_close(r["cedolare_secca"]["imposta"], 12000 * 10 / 100, tolerance=0.01, label="ced_conc")


class TestGradoParentela:

    def test_figlio(self):
        r = _call("grado_parentela", relazione="figlio")
        assert r["grado"] == 1
        assert r["linea"] == "retta"

    def test_cugino(self):
        r = _call("grado_parentela", relazione="cugino")
        assert r["grado"] == 4

    def test_catena_custom(self):
        r = _call("grado_parentela", relazione="genitore,figlio")
        assert r["grado"] == 2  # fratello


class TestValoreCatastale:

    def test_a2_successione(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="A/2", tipo="successione")
        expected = 1000 * 1.05 * 120
        assert_close(r["valore_catastale"], expected, tolerance=0.01, label="val_cat_a2")

    def test_c1_imu(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=500, categoria="C/1", tipo="imu")
        expected = 500 * 1.05 * 55
        assert_close(r["valore_catastale"], expected, tolerance=0.01, label="val_cat_c1")

    def test_b1_successione(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=800, categoria="B/1", tipo="successione")
        expected = 800 * 1.05 * 140
        assert_close(r["valore_catastale"], expected, tolerance=0.01, label="val_cat_b1")


class TestSuperficieCommerciale:

    def test_base(self):
        r = _call("calcolo_superficie_commerciale", superficie_calpestabile=80, balconi=10, cantina=5, garage=15)
        expected = 80 * 1.0 + 10 * 0.33 + 5 * 0.25 + 15 * 0.50
        assert_close(r["superficie_commerciale"], round(expected, 2), tolerance=0.01, label="sup_comm")


class TestImpostaRegistroLocazioni:

    def test_libero(self):
        r = _call("imposta_registro_locazioni", canone_annuo=12000, durata_anni=4, tipo_contratto="libero")
        annua = 12000 * 2 / 100  # 240
        assert_close(r["imposta_prima_annualita"], max(annua, 67), tolerance=0.01, label="reg_loc_lib")

    def test_concordato(self):
        r = _call("imposta_registro_locazioni", canone_annuo=6000, durata_anni=4, tipo_contratto="concordato")
        annua = 6000 * 1 / 100  # 60 < 67 minimo
        assert_close(r["imposta_prima_annualita"], 67.0, tolerance=0.01, label="reg_loc_conc")
