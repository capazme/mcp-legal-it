import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.risarcimento_danni")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# danno_biologico_micro
# ---------------------------------------------------------------------------

class TestDannoBiologicoMicro:
    def test_invalidita_1_eta_30_solo_permanente(self):
        res = _call("danno_biologico_micro", percentuale_invalidita=1, eta_vittima=30)
        assert res["percentuale_invalidita"] == 1
        assert res["eta_vittima"] == 30
        # punto_base=963.40, coeff[1]=1.0, riduzione=0.90 (eta 30 → anni_sopra=20 → 1-0.005*20) → 867.06
        assert res["danno_permanente"] == pytest.approx(867.06, abs=0.01)
        assert res["danno_temporaneo"]["totale"] == 0.0
        assert res["totale_risarcimento"] == pytest.approx(867.06, abs=0.01)
        assert "Art. 139" in res["riferimento_normativo"]

    def test_invalidita_5_eta_10_con_itt(self):
        # età 10 = eta_decremento_da → riduzione=1.0
        res = _call(
            "danno_biologico_micro",
            percentuale_invalidita=5,
            eta_vittima=10,
            giorni_itt=10,
        )
        assert res["riduzione_eta"] == pytest.approx(1.0)
        # ITT: 10 * 56.18 = 561.80
        assert res["danno_temporaneo"]["itt"]["importo"] == pytest.approx(561.80, abs=0.01)

    def test_invalidita_9_eta_0_tutte_componenti_temporanee(self):
        res = _call(
            "danno_biologico_micro",
            percentuale_invalidita=9,
            eta_vittima=0,
            giorni_itt=5,
            giorni_itp75=3,
            giorni_itp50=2,
            giorni_itp25=1,
        )
        assert res["danno_temporaneo"]["itt"]["giorni"] == 5
        assert res["danno_temporaneo"]["itp_75"]["giorni"] == 3
        assert res["danno_temporaneo"]["itp_50"]["giorni"] == 2
        assert res["danno_temporaneo"]["itp_25"]["giorni"] == 1
        # itp_25 = 1 * 14.05
        assert res["danno_temporaneo"]["itp_25"]["importo"] == pytest.approx(14.05, abs=0.01)

    def test_riduzione_eta_oltre_decremento(self):
        # età 30 → anni_sopra=20, riduzione = 1 - 0.005*20 = 0.90
        res = _call("danno_biologico_micro", percentuale_invalidita=1, eta_vittima=30)
        assert res["riduzione_eta"] == pytest.approx(0.90, abs=0.0001)

    def test_riduzione_eta_molto_anziana(self):
        # età 220 → riduzione clamped a 0
        res = _call("danno_biologico_micro", percentuale_invalidita=1, eta_vittima=120)
        assert res["riduzione_eta"] >= 0.0

    def test_personalizzazione_applica_maggiorazione(self):
        res_no = _call("danno_biologico_micro", percentuale_invalidita=3, eta_vittima=20)
        res_si = _call(
            "danno_biologico_micro",
            percentuale_invalidita=3,
            eta_vittima=20,
            personalizzazione_pct=10.0,
        )
        assert res_si["totale_risarcimento"] > res_no["totale_risarcimento"]
        assert res_si["maggiorazione_morale"] == pytest.approx(
            res_si["danno_base"] * 0.10, abs=0.01
        )

    def test_dettaglio_punti_lunghezza(self):
        res = _call("danno_biologico_micro", percentuale_invalidita=4, eta_vittima=25)
        assert len(res["dettaglio_punti"]) == 4

    def test_errore_percentuale_zero(self):
        res = _call("danno_biologico_micro", percentuale_invalidita=0, eta_vittima=30)
        assert "errore" in res

    def test_errore_percentuale_10(self):
        res = _call("danno_biologico_micro", percentuale_invalidita=10, eta_vittima=30)
        assert "errore" in res

    def test_errore_eta_negativa(self):
        res = _call("danno_biologico_micro", percentuale_invalidita=3, eta_vittima=-1)
        assert "errore" in res

    def test_errore_personalizzazione_oltre_limite(self):
        res = _call(
            "danno_biologico_micro",
            percentuale_invalidita=3,
            eta_vittima=30,
            personalizzazione_pct=25.0,
        )
        assert "errore" in res

    def test_errore_personalizzazione_negativa(self):
        res = _call(
            "danno_biologico_micro",
            percentuale_invalidita=3,
            eta_vittima=30,
            personalizzazione_pct=-1.0,
        )
        assert "errore" in res


# ---------------------------------------------------------------------------
# danno_biologico_macro
# ---------------------------------------------------------------------------

class TestDannoBiologicoMacro:
    def test_invalidita_10_eta_40(self):
        # punto_base[10] = 2680, coeff_eta[31-40] = 1.20
        # danno_base = 2680 * 10 * 1.20 = 32160
        res = _call("danno_biologico_macro", percentuale_invalidita=10, eta_vittima=40)
        assert res["danno_base"] == pytest.approx(32160.0, abs=1.0)
        assert res["maggiorazione_morale"] == 0.0
        assert res["totale_risarcimento"] == res["danno_base"]

    def test_invalidita_50_eta_55(self):
        # punto_base[50]=18500, coeff_eta[51-60]=1.00
        # danno_base = 18500*50*1.00 = 925000
        res = _call("danno_biologico_macro", percentuale_invalidita=50, eta_vittima=55)
        assert res["danno_base"] == pytest.approx(925000.0, abs=1.0)

    def test_interpolazione_punto_base(self):
        # percentuale=12 → interpolato tra 10(2680) e 15(3800)
        # ratio=(12-10)/(15-10)=0.4 → 2680 + 0.4*(3800-2680) = 3128
        res = _call("danno_biologico_macro", percentuale_invalidita=12, eta_vittima=35)
        assert res["punto_base_interpolato"] == pytest.approx(3128.0, abs=1.0)

    def test_personalizzazione_50pct(self):
        res = _call(
            "danno_biologico_macro",
            percentuale_invalidita=20,
            eta_vittima=30,
            personalizzazione_pct=50.0,
        )
        assert res["maggiorazione_morale"] == pytest.approx(res["danno_base"] * 0.50, abs=0.01)
        assert res["totale_risarcimento"] == pytest.approx(res["danno_base"] * 1.50, abs=0.01)

    def test_coefficiente_eta_0_10(self):
        res = _call("danno_biologico_macro", percentuale_invalidita=10, eta_vittima=5)
        assert res["coefficiente_eta"] == pytest.approx(1.50)

    def test_coefficiente_eta_91_100(self):
        res = _call("danno_biologico_macro", percentuale_invalidita=10, eta_vittima=95)
        assert res["coefficiente_eta"] == pytest.approx(0.40)

    def test_invalidita_100_eta_20(self):
        # punto_base[100]=76000, coeff_eta[11-20]=1.40
        res = _call("danno_biologico_macro", percentuale_invalidita=100, eta_vittima=20)
        assert res["danno_base"] == pytest.approx(76000 * 100 * 1.40, abs=1.0)

    def test_errore_percentuale_9(self):
        res = _call("danno_biologico_macro", percentuale_invalidita=9, eta_vittima=30)
        assert "errore" in res

    def test_errore_percentuale_101(self):
        res = _call("danno_biologico_macro", percentuale_invalidita=101, eta_vittima=30)
        assert "errore" in res

    def test_errore_eta_negativa(self):
        res = _call("danno_biologico_macro", percentuale_invalidita=20, eta_vittima=-5)
        assert "errore" in res

    def test_errore_personalizzazione_oltre_50(self):
        res = _call(
            "danno_biologico_macro",
            percentuale_invalidita=20,
            eta_vittima=30,
            personalizzazione_pct=51.0,
        )
        assert "errore" in res

    def test_errore_personalizzazione_negativa(self):
        res = _call(
            "danno_biologico_macro",
            percentuale_invalidita=20,
            eta_vittima=30,
            personalizzazione_pct=-1.0,
        )
        assert "errore" in res


# ---------------------------------------------------------------------------
# danno_parentale
# ---------------------------------------------------------------------------

class TestDannoParentale:
    def test_milano_figlio_genitore_minimo(self):
        res = _call(
            "danno_parentale",
            vittima="figlio",
            superstite="genitore",
            tabella="milano",
            personalizzazione_pct=0.0,
        )
        assert res["importo_liquidato"] == pytest.approx(195551.59, abs=0.01)

    def test_milano_figlio_genitore_massimo(self):
        res = _call(
            "danno_parentale",
            vittima="figlio",
            superstite="genitore",
            tabella="milano",
            personalizzazione_pct=100.0,
        )
        assert res["importo_liquidato"] == pytest.approx(391103.18, abs=0.01)

    def test_milano_figlio_genitore_mediano(self):
        res = _call(
            "danno_parentale",
            vittima="figlio",
            superstite="genitore",
            tabella="milano",
            personalizzazione_pct=50.0,
        )
        expected = (195551.59 + 391103.18) / 2
        assert res["importo_liquidato"] == pytest.approx(expected, abs=0.01)

    def test_roma_coniuge_coniuge(self):
        res = _call(
            "danno_parentale",
            vittima="coniuge",
            superstite="coniuge",
            tabella="roma",
        )
        assert "importo_liquidato" in res
        assert res["tabella"] == "roma"

    def test_milano_fratello_fratello(self):
        res = _call(
            "danno_parentale",
            vittima="fratello",
            superstite="fratello",
            tabella="milano",
            personalizzazione_pct=0.0,
        )
        assert res["importo_liquidato"] == pytest.approx(28301.23, abs=0.01)

    def test_tabella_case_insensitive(self):
        res = _call(
            "danno_parentale",
            vittima="Coniuge",
            superstite="Coniuge",
            tabella="MILANO",
        )
        assert "importo_liquidato" in res

    def test_errore_tabella_invalida(self):
        res = _call(
            "danno_parentale",
            vittima="figlio",
            superstite="genitore",
            tabella="napoli",
        )
        assert "errore" in res

    def test_errore_rapporto_non_trovato(self):
        res = _call(
            "danno_parentale",
            vittima="zio",
            superstite="nipote",
            tabella="milano",
        )
        assert "errore" in res
        assert "rapporti_disponibili" in res

    def test_errore_personalizzazione_oltre_100(self):
        res = _call(
            "danno_parentale",
            vittima="figlio",
            superstite="genitore",
            tabella="milano",
            personalizzazione_pct=101.0,
        )
        assert "errore" in res

    def test_errore_personalizzazione_negativa(self):
        res = _call(
            "danno_parentale",
            vittima="figlio",
            superstite="genitore",
            tabella="milano",
            personalizzazione_pct=-1.0,
        )
        assert "errore" in res


# ---------------------------------------------------------------------------
# menomazioni_plurime
# ---------------------------------------------------------------------------

class TestMenomazioni:
    def test_due_menomazioni_classico(self):
        # 20% + 10%: IT = 1 - (0.80 * 0.90) = 1 - 0.72 = 0.28 → 28%
        res = _call("menomazioni_plurime", percentuali=[20.0, 10.0])
        assert res["invalidita_complessiva_pct"] == pytest.approx(28.0, abs=0.01)

    def test_tre_menomazioni(self):
        # 30% + 20% + 10%: IT = 1 - 0.70*0.80*0.90 = 1 - 0.504 = 0.496 → 49.6%
        res = _call("menomazioni_plurime", percentuali=[30.0, 20.0, 10.0])
        assert res["invalidita_complessiva_pct"] == pytest.approx(49.6, abs=0.01)

    def test_riduzione_rispetto_somma_aritmetica(self):
        res = _call("menomazioni_plurime", percentuali=[20.0, 10.0])
        assert res["somma_aritmetica_pct"] == pytest.approx(30.0)
        assert res["riduzione_pct"] > 0

    def test_passi_calcolo_lunghezza(self):
        res = _call("menomazioni_plurime", percentuali=[15.0, 10.0, 5.0])
        assert len(res["passi_calcolo"]) == 3

    def test_menomazione_zero(self):
        # 0% non contribuisce — prodotto invariato
        res = _call("menomazioni_plurime", percentuali=[10.0, 0.0])
        assert res["invalidita_complessiva_pct"] == pytest.approx(10.0, abs=0.01)

    def test_menomazione_100(self):
        # 100% + qualsiasi: IT = 1 - 0 = 100%
        res = _call("menomazioni_plurime", percentuali=[100.0, 20.0])
        assert res["invalidita_complessiva_pct"] == pytest.approx(100.0, abs=0.01)

    def test_formula_riportata(self):
        res = _call("menomazioni_plurime", percentuali=[10.0, 5.0])
        assert "Balthazard" in res["formula"] or "Π" in res["formula"]

    def test_errore_lista_singola(self):
        res = _call("menomazioni_plurime", percentuali=[10.0])
        assert "errore" in res

    def test_errore_lista_vuota(self):
        res = _call("menomazioni_plurime", percentuali=[])
        assert "errore" in res

    def test_errore_percentuale_negativa(self):
        res = _call("menomazioni_plurime", percentuali=[10.0, -5.0])
        assert "errore" in res

    def test_errore_percentuale_oltre_100(self):
        res = _call("menomazioni_plurime", percentuali=[10.0, 105.0])
        assert "errore" in res


# ---------------------------------------------------------------------------
# risarcimento_inail
# ---------------------------------------------------------------------------

class TestRisarcimentoInail:
    def test_temporanea_calcola_giornaliero(self):
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=36500.0,
            percentuale_invalidita=0.0,
            tipo="temporanea",
        )
        assert res["tipo"] == "temporanea"
        assert res["retribuzione_giornaliera"] == pytest.approx(100.0, abs=0.01)
        assert res["dal_4_al_90_giorno"]["indennita_giornaliera"] == pytest.approx(60.0, abs=0.01)
        assert res["dal_91_giorno"]["indennita_giornaliera"] == pytest.approx(75.0, abs=0.01)

    def test_temporanea_case_insensitive(self):
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=36500.0,
            percentuale_invalidita=0.0,
            tipo="TEMPORANEA",
        )
        assert res["tipo"] == "temporanea"

    def test_permanente_sotto_6_nessun_indennizzo(self):
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=5.0,
            tipo="permanente",
        )
        assert res["esito"] == "Nessun indennizzo"

    def test_permanente_tra_6_e_15_capitale(self):
        # 10% → coefficiente=7.0*10=70%, indennizzo = 30000 * 70/100 = 21000
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=10.0,
            tipo="permanente",
        )
        assert res["forma"] == "capitale"
        assert res["indennizzo_capitale"] == pytest.approx(21000.0, abs=0.01)

    def test_permanente_oltre_16_rendita(self):
        # 20% invalidità, 30000 retribuzione
        # quota_biologica = 30000 * 0.20 * 0.40 = 2400
        # quota_patrimoniale = 30000 * (20-16)/100 * 0.60 = 720
        # rendita_annua = 3120
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=20.0,
            tipo="permanente",
        )
        assert res["forma"] == "rendita"
        assert res["rendita_annua"] == pytest.approx(3120.0, abs=0.01)
        assert res["rendita_mensile"] == pytest.approx(260.0, abs=0.01)

    def test_permanente_16_quota_patrimoniale_zero(self):
        # esattamente 16%: quota_patrimoniale = 0 (condizione >16 non soddisfatta)
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=16.0,
            tipo="permanente",
        )
        assert res["forma"] == "rendita"
        assert res["quota_danno_patrimoniale"] == pytest.approx(0.0, abs=0.01)

    def test_errore_tipo_invalido(self):
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=10.0,
            tipo="altro",
        )
        assert "errore" in res

    def test_errore_percentuale_negativa(self):
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=-1.0,
            tipo="permanente",
        )
        assert "errore" in res

    def test_errore_percentuale_oltre_100(self):
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=101.0,
            tipo="permanente",
        )
        assert "errore" in res


# ---------------------------------------------------------------------------
# danno_non_patrimoniale
# ---------------------------------------------------------------------------

class TestDannoNonPatrimoniale:
    def test_micro_invalidita_5_eta_30(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=5,
            eta_vittima=30,
        )
        assert "micropermanenti" in res["tipo_calcolo"]
        assert res["componenti"]["danno_biologico"] > 0
        assert res["totale_risarcimento"] > 0

    def test_macro_invalidita_20_eta_40(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=20,
            eta_vittima=40,
        )
        assert "macropermanenti" in res["tipo_calcolo"]

    def test_spese_mediche_incluse(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=5,
            eta_vittima=30,
            spese_mediche=5000.0,
        )
        assert res["componenti"]["danno_patrimoniale_emergente"]["spese_mediche"] == 5000.0
        assert res["componenti"]["danno_patrimoniale_emergente"]["totale"] >= 5000.0

    def test_itt_incluso(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=5,
            eta_vittima=30,
            giorni_itt=20,
        )
        # ITT 20 * 56.18 = 1123.6
        assert res["componenti"]["danno_patrimoniale_emergente"]["itt"]["importo"] == pytest.approx(1123.6, abs=0.01)

    def test_danno_morale_percentuale(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=5,
            eta_vittima=30,
            danno_morale_pct=25.0,
        )
        bio = res["componenti"]["danno_biologico"]
        morale = res["componenti"]["danno_morale"]["importo"]
        assert morale == pytest.approx(bio * 0.25, abs=0.01)

    def test_danno_esistenziale_percentuale(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=5,
            eta_vittima=30,
            danno_esistenziale_pct=10.0,
        )
        bio = res["componenti"]["danno_biologico"]
        esistenziale = res["componenti"]["danno_esistenziale"]["importo"]
        assert esistenziale == pytest.approx(bio * 0.10, abs=0.01)

    def test_totale_e_somma_componenti(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=8,
            eta_vittima=25,
            giorni_itt=5,
            spese_mediche=1000.0,
            danno_morale_pct=15.0,
            danno_esistenziale_pct=10.0,
        )
        c = res["componenti"]
        expected = (
            c["danno_biologico"]
            + c["danno_morale"]["importo"]
            + c["danno_esistenziale"]["importo"]
            + c["danno_patrimoniale_emergente"]["totale"]
        )
        assert res["totale_risarcimento"] == pytest.approx(expected, abs=0.01)

    def test_errore_percentuale_zero(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=0,
            eta_vittima=30,
        )
        assert "errore" in res

    def test_errore_percentuale_101(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=101,
            eta_vittima=30,
        )
        assert "errore" in res

    def test_errore_danno_morale_oltre_50(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=5,
            eta_vittima=30,
            danno_morale_pct=51.0,
        )
        assert "errore" in res

    def test_errore_danno_esistenziale_oltre_50(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=5,
            eta_vittima=30,
            danno_esistenziale_pct=51.0,
        )
        assert "errore" in res


# ---------------------------------------------------------------------------
# equo_indennizzo
# ---------------------------------------------------------------------------

class TestEquoIndennizzo:
    def test_categoria_1_stipendio_50000(self):
        # coeff=8.0, 100% invalidita → 50000 * 8.0 * 1.0 = 400000
        res = _call(
            "equo_indennizzo",
            categoria_tabella="1",
            percentuale_invalidita=100.0,
            stipendio_annuo=50000.0,
        )
        assert res["equo_indennizzo"] == pytest.approx(400000.0, abs=0.01)
        assert res["pensione_privilegiata"] is True
        assert "nota_pensione" in res

    def test_categoria_8_valore_corretto(self):
        # coeff=0.7, 10% → 30000 * 0.7 * 0.10 = 2100
        res = _call(
            "equo_indennizzo",
            categoria_tabella="8",
            percentuale_invalidita=10.0,
            stipendio_annuo=30000.0,
        )
        assert res["equo_indennizzo"] == pytest.approx(2100.0, abs=0.01)
        assert res["pensione_privilegiata"] is False
        assert "nota_pensione" not in res

    def test_categoria_5_pensione_privilegiata(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella="5",
            percentuale_invalidita=35.0,
            stipendio_annuo=40000.0,
        )
        assert res["pensione_privilegiata"] is True

    def test_categoria_6_no_pensione(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella="6",
            percentuale_invalidita=25.0,
            stipendio_annuo=40000.0,
        )
        assert res["pensione_privilegiata"] is False

    def test_avviso_abrogazione_presente(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella="3",
            percentuale_invalidita=55.0,
            stipendio_annuo=40000.0,
        )
        assert "ABROGATO" in res["attenzione"]
        assert "DL 201/2011" in res["attenzione"]

    def test_riferimento_normativo_presente(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella="2",
            percentuale_invalidita=70.0,
            stipendio_annuo=40000.0,
        )
        assert "DPR 834/1981" in res["riferimento_normativo"]

    def test_categoria_stringa_con_spazi(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella=" 4 ",
            percentuale_invalidita=45.0,
            stipendio_annuo=30000.0,
        )
        assert "equo_indennizzo" in res

    def test_errore_categoria_invalida(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella="9",
            percentuale_invalidita=50.0,
            stipendio_annuo=30000.0,
        )
        assert "errore" in res

    def test_errore_categoria_stringa_non_numerica(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella="A",
            percentuale_invalidita=50.0,
            stipendio_annuo=30000.0,
        )
        assert "errore" in res

    def test_categoria_tutti_i_valori_validi(self):
        for cat in ["1", "2", "3", "4", "5", "6", "7", "8"]:
            res = _call(
                "equo_indennizzo",
                categoria_tabella=cat,
                percentuale_invalidita=50.0,
                stipendio_annuo=30000.0,
            )
            assert "equo_indennizzo" in res, f"Categoria {cat} fallita"
