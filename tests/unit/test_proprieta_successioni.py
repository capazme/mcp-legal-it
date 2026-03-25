import asyncio
import importlib
import inspect

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.proprieta_successioni")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    if inspect.iscoroutinefunction(actual):
        return asyncio.get_event_loop().run_until_complete(actual(**kwargs))
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# calcolo_eredita
# ---------------------------------------------------------------------------

class TestCalcoloEredita:

    def test_coniuge_solo(self):
        r = _call("calcolo_eredita", massa_ereditaria=300000, eredi={"coniuge": True})
        assert r["quota_disponibile"] == pytest.approx(150000.0)
        assert r["percentuale_disponibile"] == "50.0%"
        assert any(q["erede"] == "coniuge" for q in r["quote"])
        coniuge_q = next(q for q in r["quote"] if q["erede"] == "coniuge")
        assert coniuge_q["quota_legittima"] == "1/2"
        assert coniuge_q["valore"] == pytest.approx(150000.0)

    def test_coniuge_un_figlio(self):
        r = _call("calcolo_eredita", massa_ereditaria=300000, eredi={"coniuge": True, "figli": 1})
        assert r["quota_disponibile"] == pytest.approx(100000.0)
        assert len(r["quote"]) == 2
        eredi_nomi = {q["erede"] for q in r["quote"]}
        assert "coniuge" in eredi_nomi
        assert "figlio" in eredi_nomi

    def test_coniuge_due_figli(self):
        r = _call("calcolo_eredita", massa_ereditaria=400000, eredi={"coniuge": True, "figli": 2})
        assert r["quota_disponibile"] == pytest.approx(100000.0)
        assert len(r["quote"]) == 3
        coniuge_q = next(q for q in r["quote"] if q["erede"] == "coniuge")
        assert coniuge_q["quota_legittima"] == "1/4"

    def test_coniuge_tre_figli(self):
        r = _call("calcolo_eredita", massa_ereditaria=600000, eredi={"coniuge": True, "figli": 3})
        assert len(r["quote"]) == 4
        figli_quote = [q for q in r["quote"] if q["erede"].startswith("figlio_")]
        assert len(figli_quote) == 3
        for q in figli_quote:
            assert q["valore"] == pytest.approx(100000.0)

    def test_solo_figlio(self):
        r = _call("calcolo_eredita", massa_ereditaria=200000, eredi={"figli": 1})
        assert r["quota_disponibile"] == pytest.approx(100000.0)
        figlio_q = next(q for q in r["quote"] if q["erede"] == "figlio")
        assert figlio_q["quota_legittima"] == "1/2"

    def test_due_figli_senza_coniuge(self):
        r = _call("calcolo_eredita", massa_ereditaria=300000, eredi={"figli": 2})
        assert r["quota_disponibile"] == pytest.approx(100000.0)
        for q in r["quote"]:
            assert q["valore"] == pytest.approx(100000.0)

    def test_coniuge_ascendenti(self):
        r = _call("calcolo_eredita", massa_ereditaria=400000, eredi={"coniuge": True, "ascendenti": True})
        assert r["quota_disponibile"] == pytest.approx(100000.0)
        nomi = {q["erede"] for q in r["quote"]}
        assert "coniuge" in nomi
        assert "ascendenti" in nomi

    def test_solo_ascendenti(self):
        r = _call("calcolo_eredita", massa_ereditaria=300000, eredi={"ascendenti": True})
        assert r["quota_disponibile"] == pytest.approx(200000.0)
        asc_q = next(q for q in r["quote"] if q["erede"] == "ascendenti")
        assert asc_q["quota_legittima"] == "1/3"

    def test_solo_fratelli(self):
        r = _call("calcolo_eredita", massa_ereditaria=120000, eredi={"fratelli": 3})
        assert r["quota_disponibile"] == 0.0
        fratelli_q = [q for q in r["quote"] if q["erede"].startswith("fratello_")]
        assert len(fratelli_q) == 3
        for q in fratelli_q:
            assert q["valore"] == pytest.approx(40000.0)

    def test_nessun_legittimario(self):
        r = _call("calcolo_eredita", massa_ereditaria=100000, eredi={})
        assert r["quota_disponibile"] == pytest.approx(100000.0)
        assert r["percentuale_disponibile"] == "100.0%"

    def test_massa_zero(self):
        r = _call("calcolo_eredita", massa_ereditaria=0, eredi={"coniuge": True})
        assert r["quota_disponibile"] == 0.0

    def test_riferimento_normativo_presente(self):
        r = _call("calcolo_eredita", massa_ereditaria=100000, eredi={"figli": 2})
        assert "riferimento_normativo" in r
        assert "536" in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# imposte_successione
# ---------------------------------------------------------------------------

class TestImposteSuccessione:

    def test_coniuge_sotto_franchigia(self):
        r = _call("imposte_successione", valore_beni=500000, parentela="coniuge_linea_retta")
        assert r["imposta_successione"] == 0.0
        assert r["base_imponibile"] == 0.0
        assert r["totale_imposte"] == 0.0

    def test_coniuge_sopra_franchigia(self):
        r = _call("imposte_successione", valore_beni=1500000, parentela="coniuge_linea_retta")
        assert r["base_imponibile"] == pytest.approx(500000.0)
        assert r["aliquota_pct"] == 4
        assert r["imposta_successione"] == pytest.approx(20000.0)

    def test_fratelli_sorelle(self):
        r = _call("imposte_successione", valore_beni=300000, parentela="fratelli_sorelle")
        assert r["base_imponibile"] == pytest.approx(200000.0)
        assert r["aliquota_pct"] == 6
        assert r["imposta_successione"] == pytest.approx(12000.0)

    def test_parenti_fino_4_grado(self):
        r = _call("imposte_successione", valore_beni=200000, parentela="parenti_fino_4_grado_affini_fino_3")
        assert r["franchigia"] == 0
        assert r["aliquota_pct"] == 6
        assert r["imposta_successione"] == pytest.approx(12000.0)

    def test_altri_aliquota_8(self):
        r = _call("imposte_successione", valore_beni=100000, parentela="altri")
        assert r["aliquota_pct"] == 8
        assert r["imposta_successione"] == pytest.approx(8000.0)

    def test_con_immobili_seconda_casa(self):
        r = _call("imposte_successione", valore_beni=500000, parentela="altri", immobili=True)
        assert "imposta_ipotecaria" in r
        assert "imposta_catastale" in r
        assert r["totale_imposte"] > r["imposta_successione"]

    def test_con_immobili_prima_casa(self):
        r = _call("imposte_successione", valore_beni=500000, parentela="coniuge_linea_retta", immobili=True, prima_casa=True)
        assert r["imposta_ipotecaria"] == 200
        assert r["imposta_catastale"] == 200
        assert "nota_prima_casa" in r

    def test_parentela_invalida(self):
        r = _call("imposte_successione", valore_beni=100000, parentela="sconosciuto")
        assert "errore" in r

    def test_immobili_minimo_ipocatastale(self):
        # Valore piccolo: imposta ipocatastale deve rispettare il minimo di 200€
        r = _call("imposte_successione", valore_beni=5000, parentela="altri", immobili=True)
        assert r["imposta_ipotecaria"] >= 200
        assert r["imposta_catastale"] >= 200


# ---------------------------------------------------------------------------
# calcolo_usufrutto
# ---------------------------------------------------------------------------

class TestCalcoloUsufrutto:

    def test_eta_giovane(self):
        # Età 20, coefficiente 38, tasso 2.5%
        r = _call("calcolo_usufrutto", valore_piena_proprieta=100000, eta_usufruttuario=20)
        assert r["coefficiente"] == 38.0
        assert r["tasso_legale_pct"] == 2.5
        expected_usufrutto = round(100000 * 0.025 * 38, 2)
        assert r["valore_usufrutto"] == pytest.approx(expected_usufrutto)
        assert r["valore_nuda_proprieta"] == pytest.approx(100000 - expected_usufrutto)

    def test_eta_anziana(self):
        # Età 80, coefficiente 10
        r = _call("calcolo_usufrutto", valore_piena_proprieta=200000, eta_usufruttuario=80)
        assert r["coefficiente"] == 10.0
        expected = round(200000 * 0.025 * 10, 2)
        assert r["valore_usufrutto"] == pytest.approx(expected)

    def test_percentuali_somma_100(self):
        r = _call("calcolo_usufrutto", valore_piena_proprieta=100000, eta_usufruttuario=50)
        assert r["percentuale_usufrutto"] + r["percentuale_nuda_proprieta"] == pytest.approx(100.0, abs=0.01)

    def test_nuda_proprieta_piu_piccola_per_giovani(self):
        r_giovane = _call("calcolo_usufrutto", valore_piena_proprieta=100000, eta_usufruttuario=20)
        r_anziano = _call("calcolo_usufrutto", valore_piena_proprieta=100000, eta_usufruttuario=90)
        assert r_giovane["valore_usufrutto"] > r_anziano["valore_usufrutto"]

    def test_eta_fuori_range(self):
        r = _call("calcolo_usufrutto", valore_piena_proprieta=100000, eta_usufruttuario=130)
        assert "errore" in r

    def test_eta_zero(self):
        r = _call("calcolo_usufrutto", valore_piena_proprieta=100000, eta_usufruttuario=0)
        assert r["coefficiente"] == 38.0

    def test_eta_100(self):
        r = _call("calcolo_usufrutto", valore_piena_proprieta=100000, eta_usufruttuario=100)
        assert r["coefficiente"] == 2.0

    def test_rendita_annua(self):
        r = _call("calcolo_usufrutto", valore_piena_proprieta=100000, eta_usufruttuario=50)
        assert r["rendita_annua"] == pytest.approx(2500.0)  # 100000 * 2.5%


# ---------------------------------------------------------------------------
# calcolo_imu
# ---------------------------------------------------------------------------

class TestCalcoloImu:

    def test_categoria_a2_seconda_casa(self):
        # A/2: moltiplicatore 160, rivalutata = 800 * 1.05 = 840, base = 840 * 160 = 134400
        r = _call("calcolo_imu", rendita_catastale=800, categoria="A/2", aliquota_comunale=0.86)
        assert r["moltiplicatore"] == 160
        assert r["rendita_rivalutata"] == pytest.approx(840.0)
        assert r["base_imponibile"] == pytest.approx(134400.0)
        assert r["imu_annua"] == pytest.approx(round(134400 * 0.86 / 100, 2))

    def test_prima_casa_ordinaria_esente(self):
        r = _call("calcolo_imu", rendita_catastale=800, categoria="A/2", prima_casa=True)
        assert r["imu_annua"] == 0.0
        assert r["imu_semestrale"] == 0.0
        assert "esente" in r["nota"].lower()

    def test_prima_casa_lusso_a1(self):
        # A/1 prima casa: IMU dovuta con detrazione 200€
        r = _call("calcolo_imu", rendita_catastale=1000, categoria="A/1", aliquota_comunale=0.86, prima_casa=True)
        assert r["detrazione_prima_casa"] == 200.0
        assert "lusso" in r["nota"].lower() or "A/1" in r["nota"]

    def test_categoria_c1_moltiplicatore(self):
        r = _call("calcolo_imu", rendita_catastale=1000, categoria="C/1")
        assert r["moltiplicatore"] == 55

    def test_categoria_d_moltiplicatore(self):
        r = _call("calcolo_imu", rendita_catastale=1000, categoria="D/1")
        assert r["moltiplicatore"] == 65

    def test_categoria_d5_moltiplicatore(self):
        r = _call("calcolo_imu", rendita_catastale=1000, categoria="D/5")
        assert r["moltiplicatore"] == 80

    def test_categoria_a10_moltiplicatore(self):
        r = _call("calcolo_imu", rendita_catastale=1000, categoria="A/10")
        assert r["moltiplicatore"] == 80

    def test_imu_semestrale_meta_annua(self):
        r = _call("calcolo_imu", rendita_catastale=800, categoria="A/2")
        assert r["imu_semestrale"] == pytest.approx(r["imu_annua"] / 2, abs=0.01)

    def test_categoria_invalida(self):
        r = _call("calcolo_imu", rendita_catastale=800, categoria="Z/99")
        assert "errore" in r

    def test_categoria_lowercase_normalizzata(self):
        r = _call("calcolo_imu", rendita_catastale=800, categoria="a/2")
        assert r["categoria"] == "A/2"

    def test_b_moltiplicatore(self):
        r = _call("calcolo_imu", rendita_catastale=500, categoria="B/1")
        assert r["moltiplicatore"] == 140


# ---------------------------------------------------------------------------
# imposte_compravendita
# ---------------------------------------------------------------------------

class TestImposteCompravendita:

    def test_prima_casa_da_privato(self):
        # 2% registro su 200000, minimo 1000 → registro = max(4000, 1000) = 4000
        r = _call("imposte_compravendita", prezzo=200000, tipo_immobile="abitazione", prima_casa=True)
        assert r["imposta_registro"] == pytest.approx(4000.0)
        assert r["imposta_ipotecaria"] == 50
        assert r["imposta_catastale"] == 50
        assert r["totale_imposte"] == pytest.approx(4100.0)

    def test_seconda_casa_da_privato(self):
        # 9% su 200000 = 18000
        r = _call("imposte_compravendita", prezzo=200000, tipo_immobile="abitazione", prima_casa=False)
        assert r["imposta_registro"] == pytest.approx(18000.0)
        assert r["totale_imposte"] == pytest.approx(18100.0)

    def test_da_costruttore_prima_casa(self):
        # IVA 4%
        r = _call("imposte_compravendita", prezzo=300000, prima_casa=True, da_costruttore=True)
        assert r["iva_aliquota_pct"] == 4
        assert r["iva"] == pytest.approx(12000.0)

    def test_da_costruttore_seconda_casa(self):
        # IVA 10%
        r = _call("imposte_compravendita", prezzo=300000, prima_casa=False, da_costruttore=True)
        assert r["iva_aliquota_pct"] == 10
        assert r["iva"] == pytest.approx(30000.0)

    def test_da_costruttore_lusso(self):
        # IVA 22%
        r = _call("imposte_compravendita", prezzo=1000000, tipo_immobile="lusso", da_costruttore=True)
        assert r["iva_aliquota_pct"] == 22
        assert r["iva"] == pytest.approx(220000.0)

    def test_terreno_agricolo(self):
        # 15% registro su 50000 = 7500; minimo 1000 → 7500
        r = _call("imposte_compravendita", prezzo=50000, tipo_immobile="terreno_agricolo")
        assert r["imposta_registro"] == pytest.approx(7500.0)

    def test_terreno_agricolo_minimo_registro(self):
        # Prezzo piccolo → minimo 1000
        r = _call("imposte_compravendita", prezzo=5000, tipo_immobile="terreno_agricolo")
        assert r["imposta_registro"] == pytest.approx(1000.0)

    def test_prezzo_valore_prima_casa(self):
        # Con rendita catastale: base = rendita * 115.5
        r = _call("imposte_compravendita", prezzo=300000, tipo_immobile="abitazione", prima_casa=True, rendita_catastale=600)
        base = round(600 * 115.5, 2)
        assert r["base_prezzo_valore"] == pytest.approx(base)
        assert r["imposta_registro"] == pytest.approx(max(round(base * 2 / 100, 2), 1000))

    def test_prezzo_valore_seconda_casa(self):
        r = _call("imposte_compravendita", prezzo=300000, tipo_immobile="abitazione", prima_casa=False, rendita_catastale=600)
        base = round(600 * 126.0, 2)
        assert r["base_prezzo_valore"] == pytest.approx(base)


# ---------------------------------------------------------------------------
# pensione_reversibilita
# ---------------------------------------------------------------------------

class TestPensioneReversibilita:

    def test_coniuge_solo(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000, beneficiari={"coniuge": True})
        assert r["quota_pct"] == 60
        assert r["pensione_lorda_annua"] == pytest.approx(12000.0)
        assert r["pensione_lorda_mensile"] == pytest.approx(round(12000 / 13, 2))

    def test_coniuge_un_figlio(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000, beneficiari={"coniuge": True, "figli": 1})
        assert r["quota_pct"] == 80

    def test_coniuge_due_figli(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000, beneficiari={"coniuge": True, "figli": 2})
        assert r["quota_pct"] == 100

    def test_un_figlio_solo(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000, beneficiari={"figli": 1})
        assert r["quota_pct"] == 70

    def test_due_figli_soli(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000, beneficiari={"figli": 2})
        assert r["quota_pct"] == 80

    def test_tre_figli_soli(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000, beneficiari={"figli": 3})
        assert r["quota_pct"] == 100

    def test_genitori(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000, beneficiari={"genitori": 2})
        assert r["quota_pct"] == 30

    def test_riduzione_cumulo_oltre_3x(self):
        # reddito > 3 * 7781.93 = 23345.79 → riduzione 25%
        r = _call("pensione_reversibilita", pensione_de_cuius=20000,
                  beneficiari={"coniuge": True}, reddito_beneficiario=25000)
        assert r["riduzione_cumulo"]["riduzione_pct"] == 25
        assert r["pensione_netta_annua"] < r["pensione_lorda_annua"]

    def test_riduzione_cumulo_oltre_4x(self):
        # reddito > 4 * 7781.93 = 31127.72 → riduzione 40%
        r = _call("pensione_reversibilita", pensione_de_cuius=20000,
                  beneficiari={"coniuge": True}, reddito_beneficiario=35000)
        assert r["riduzione_cumulo"]["riduzione_pct"] == 40

    def test_riduzione_cumulo_oltre_5x(self):
        # reddito > 5 * 7781.93 = 38909.65 → riduzione 50%
        r = _call("pensione_reversibilita", pensione_de_cuius=20000,
                  beneficiari={"coniuge": True}, reddito_beneficiario=50000)
        assert r["riduzione_cumulo"]["riduzione_pct"] == 50

    def test_nessun_beneficiario(self):
        r = _call("pensione_reversibilita", pensione_de_cuius=20000, beneficiari={})
        assert "errore" in r


# ---------------------------------------------------------------------------
# grado_parentela
# ---------------------------------------------------------------------------

class TestGradoParentela:

    def test_figlio_grado_1(self):
        r = _call("grado_parentela", relazione="figlio")
        assert r["grado"] == 1
        assert r["linea"] == "retta"

    def test_fratello_grado_2(self):
        r = _call("grado_parentela", relazione="fratello")
        assert r["grado"] == 2
        assert r["linea"] == "collaterale"

    def test_zio_grado_3(self):
        r = _call("grado_parentela", relazione="zio")
        assert r["grado"] == 3

    def test_cugino_grado_4(self):
        r = _call("grado_parentela", relazione="cugino")
        assert r["grado"] == 4

    def test_nonno_grado_2_retta(self):
        r = _call("grado_parentela", relazione="nonno")
        assert r["grado"] == 2
        assert r["linea"] == "retta"

    def test_catena_passi_fratello(self):
        r = _call("grado_parentela", relazione="genitore,figlio")
        assert r["grado"] == 2
        assert r["linea"] == "collaterale"

    def test_catena_passi_retta(self):
        r = _call("grado_parentela", relazione="figlio,figlio")
        assert r["grado"] == 2
        assert r["linea"] == "retta"

    def test_cugino_secondo_grado_6(self):
        r = _call("grado_parentela", relazione="cugino_secondo")
        assert r["grado"] == 6

    def test_relazione_non_riconosciuta(self):
        r = _call("grado_parentela", relazione="parente_lontano")
        assert "errore" in r
        assert "relazioni_disponibili" in r

    def test_rilevanza_oltre_6_grado(self):
        r = _call("grado_parentela", relazione="genitore,genitore,genitore,figlio,figlio,figlio,figlio")
        assert "6°" in r["rilevanza_successoria"] or "nessun effetto" in r["rilevanza_successoria"]

    def test_imposta_successione_in_risultato(self):
        r = _call("grado_parentela", relazione="fratello")
        assert "imposta_successione" in r
        assert "100.000" in r["imposta_successione"]


# ---------------------------------------------------------------------------
# calcolo_valore_catastale
# ---------------------------------------------------------------------------

class TestCalcoloValoreCatastale:

    def test_a2_successione(self):
        # coeff_succ = 120, rivalutata = 1000 * 1.05 = 1050, valore = 1050 * 120 = 126000
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="A/2", tipo="successione")
        assert r["coefficiente"] == 120.0
        assert r["valore_catastale"] == pytest.approx(126000.0)

    def test_a2_compravendita(self):
        # coeff_comp = 126
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="A/2", tipo="compravendita")
        assert r["coefficiente"] == 126.0
        assert r["valore_catastale"] == pytest.approx(132300.0)

    def test_a10_successione(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="A/10", tipo="successione")
        assert r["coefficiente"] == 63.0

    def test_c1_successione(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="C/1", tipo="successione")
        assert r["coefficiente"] == pytest.approx(42.84)

    def test_b_successione(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="B/1", tipo="successione")
        assert r["coefficiente"] == 140.0

    def test_imu_tipo(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="A/2", tipo="imu")
        assert r["coefficiente"] == 160.0

    def test_imu_c1(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="C/1", tipo="imu")
        assert r["coefficiente"] == 55.0

    def test_tipo_invalido(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="A/2", tipo="altro")
        assert "errore" in r

    def test_categoria_invalida(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="Z/1", tipo="successione")
        assert "errore" in r

    def test_rivalutazione_5_pct(self):
        r = _call("calcolo_valore_catastale", rendita_catastale=1000, categoria="A/2", tipo="successione")
        assert r["rendita_rivalutata"] == pytest.approx(1050.0)


# ---------------------------------------------------------------------------
# calcolo_superficie_commerciale
# ---------------------------------------------------------------------------

class TestCalcoloSuperficieCommerciale:

    def test_solo_calpestabile(self):
        r = _call("calcolo_superficie_commerciale", superficie_calpestabile=100)
        assert r["superficie_commerciale"] == pytest.approx(100.0)
        assert "calpestabile" in r["dettaglio"]

    def test_con_balconi(self):
        # 100 * 1.0 + 10 * 0.33 = 103.3
        r = _call("calcolo_superficie_commerciale", superficie_calpestabile=100, balconi=10)
        assert r["superficie_commerciale"] == pytest.approx(103.3)

    def test_tutte_le_superfici(self):
        r = _call("calcolo_superficie_commerciale",
                  superficie_calpestabile=80,
                  balconi=10,
                  terrazzi=20,
                  giardino=50,
                  cantina=15,
                  garage=20)
        expected = round(80 * 1.0 + 10 * 0.33 + 20 * 0.25 + 50 * 0.10 + 15 * 0.25 + 20 * 0.50, 2)
        assert r["superficie_commerciale"] == pytest.approx(expected)

    def test_giardino_coefficiente_10_pct(self):
        r = _call("calcolo_superficie_commerciale", superficie_calpestabile=0, giardino=100)
        assert r["superficie_commerciale"] == pytest.approx(10.0)

    def test_garage_coefficiente_50_pct(self):
        r = _call("calcolo_superficie_commerciale", superficie_calpestabile=0, garage=30)
        assert r["superficie_commerciale"] == pytest.approx(15.0)

    def test_superfici_zero_non_in_dettaglio(self):
        r = _call("calcolo_superficie_commerciale", superficie_calpestabile=100)
        assert "balconi" not in r["dettaglio"]
        assert "giardino" not in r["dettaglio"]

    def test_coefficienti_presenti(self):
        r = _call("calcolo_superficie_commerciale", superficie_calpestabile=50)
        assert r["coefficienti_applicati"]["calpestabile"] == 1.0
        assert r["coefficienti_applicati"]["balconi"] == 0.33


# ---------------------------------------------------------------------------
# cedolare_secca
# ---------------------------------------------------------------------------

class TestCedolareSecca:

    def test_contratto_libero_21_pct(self):
        r = _call("cedolare_secca", canone_annuo=10000, tipo_contratto="libero")
        assert r["cedolare_secca"]["aliquota_pct"] == 21.0
        assert r["cedolare_secca"]["imposta"] == pytest.approx(2100.0)

    def test_contratto_concordato_10_pct(self):
        r = _call("cedolare_secca", canone_annuo=10000, tipo_contratto="concordato")
        assert r["cedolare_secca"]["aliquota_pct"] == 10.0
        assert r["cedolare_secca"]["imposta"] == pytest.approx(1000.0)

    def test_contratto_brevi_26_pct(self):
        r = _call("cedolare_secca", canone_annuo=10000, tipo_contratto="brevi")
        assert r["cedolare_secca"]["aliquota_pct"] == 26.0
        assert r["cedolare_secca"]["imposta"] == pytest.approx(2600.0)

    def test_irpef_base_95_pct(self):
        r = _call("cedolare_secca", canone_annuo=10000, tipo_contratto="libero", irpef_marginale=43)
        assert r["irpef_ordinaria"]["base_imponibile_95_pct"] == pytest.approx(9500.0)

    def test_convenienza_cedolare_alta_aliquota_irpef(self):
        # Con aliquota IRPEF 43%, cedolare secca 21% è più conveniente
        r = _call("cedolare_secca", canone_annuo=10000, tipo_contratto="libero", irpef_marginale=43)
        assert r["opzione_conveniente"] == "cedolare_secca"
        assert r["risparmio_cedolare"] > 0

    def test_tipo_contratto_invalido(self):
        r = _call("cedolare_secca", canone_annuo=10000, tipo_contratto="sconosciuto")
        assert "errore" in r

    def test_risparmio_concordato_massimo(self):
        r = _call("cedolare_secca", canone_annuo=10000, tipo_contratto="concordato", irpef_marginale=43)
        assert r["risparmio_cedolare"] > r["cedolare_secca"]["imposta"] * 0.5


# ---------------------------------------------------------------------------
# imposta_registro_locazioni
# ---------------------------------------------------------------------------

class TestImpostaRegistroLocazioni:

    def test_contratto_libero_2_pct(self):
        # 10000 * 2% = 200, > minimo 67 → imposta prima annualità = 200
        r = _call("imposta_registro_locazioni", canone_annuo=10000, durata_anni=4, tipo_contratto="libero")
        assert r["aliquota_pct"] == 2.0
        assert r["imposta_prima_annualita"] == pytest.approx(200.0)
        assert r["minimo_applicato"] is False

    def test_contratto_concordato_1_pct(self):
        r = _call("imposta_registro_locazioni", canone_annuo=10000, durata_anni=3, tipo_contratto="concordato")
        assert r["aliquota_pct"] == 1.0
        assert r["imposta_prima_annualita"] == pytest.approx(100.0)

    def test_minimo_67_applicato(self):
        # Canone basso: 1000 * 2% = 20 < 67 → minimo applicato
        r = _call("imposta_registro_locazioni", canone_annuo=1000, durata_anni=4, tipo_contratto="libero")
        assert r["imposta_prima_annualita"] == pytest.approx(67.0)
        assert r["minimo_applicato"] is True

    def test_totale_durata_4_anni(self):
        # Prima annualità 200, successive 3 * 200 = 600, totale = 800
        r = _call("imposta_registro_locazioni", canone_annuo=10000, durata_anni=4, tipo_contratto="libero")
        assert r["totale_durata_contratto"] == pytest.approx(200.0 + 200.0 * 3)

    def test_tipo_contratto_invalido(self):
        r = _call("imposta_registro_locazioni", canone_annuo=10000, tipo_contratto="sconosciuto")
        assert "errore" in r

    def test_seconda_registrazione_no_minimo(self):
        r = _call("imposta_registro_locazioni", canone_annuo=1000, durata_anni=4,
                  tipo_contratto="libero", prima_registrazione=False)
        assert r["imposta_prima_annualita"] == pytest.approx(20.0)
        assert r["minimo_applicato"] is False


# ---------------------------------------------------------------------------
# spese_condominiali
# ---------------------------------------------------------------------------

class TestSpeseCondominiali:

    def test_ordinaria_millesimi(self):
        # 10000 * 100/1000 = 1000
        r = _call("spese_condominiali", importo_totale=10000, millesimi_proprietario=100, tipo_spesa="ordinaria")
        assert r["quota_unita"] == pytest.approx(1000.0)

    def test_straordinaria_millesimi(self):
        r = _call("spese_condominiali", importo_totale=5000, millesimi_proprietario=50, tipo_spesa="straordinaria")
        assert r["quota_unita"] == pytest.approx(250.0)

    def test_riscaldamento_millesimi(self):
        r = _call("spese_condominiali", importo_totale=8000, millesimi_proprietario=80, tipo_spesa="riscaldamento")
        assert r["quota_unita"] == pytest.approx(640.0)

    def test_ascensore_formula_mista(self):
        # 50% millesimi + 50% piano
        r = _call("spese_condominiali", importo_totale=2000, millesimi_proprietario=100,
                  tipo_spesa="ascensore", piano=5)
        assert "quota_unita" in r
        assert r["quota_unita"] > 0

    def test_locato_ordinaria_tutto_inquilino(self):
        r = _call("spese_condominiali", importo_totale=10000, millesimi_proprietario=100,
                  tipo_spesa="ordinaria", immobile_locato=True)
        assert r["ripartizione_locazione"]["quota_proprietario"] == 0.0
        assert r["ripartizione_locazione"]["quota_inquilino"] == pytest.approx(1000.0)

    def test_locato_straordinaria_tutto_proprietario(self):
        r = _call("spese_condominiali", importo_totale=10000, millesimi_proprietario=100,
                  tipo_spesa="straordinaria", immobile_locato=True)
        assert r["ripartizione_locazione"]["quota_inquilino"] == 0.0
        assert r["ripartizione_locazione"]["quota_proprietario"] == pytest.approx(1000.0)

    def test_locato_ascensore_meta_ciascuno(self):
        r = _call("spese_condominiali", importo_totale=2000, millesimi_proprietario=100,
                  tipo_spesa="ascensore", piano=3, immobile_locato=True)
        rip = r["ripartizione_locazione"]
        assert rip["quota_proprietario"] == pytest.approx(rip["quota_inquilino"])

    def test_tipo_spesa_invalido(self):
        r = _call("spese_condominiali", importo_totale=1000, millesimi_proprietario=100, tipo_spesa="invalida")
        assert "errore" in r

    def test_millesimi_massimi(self):
        r = _call("spese_condominiali", importo_totale=1000, millesimi_proprietario=1000, tipo_spesa="ordinaria")
        assert r["quota_unita"] == pytest.approx(1000.0)
