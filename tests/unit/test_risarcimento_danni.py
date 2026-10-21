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
        # punto_base=988.45 (DM 20/07/2026), coeff[1]=1.0, riduzione=0.90 (eta 30 → anni_sopra=20 → 1-0.005*20) → 889.61
        assert res["danno_permanente"] == pytest.approx(889.61, abs=0.01)
        assert res["danno_temporaneo"]["totale"] == 0.0
        assert res["totale_risarcimento"] == pytest.approx(889.61, abs=0.01)
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
        # ITT: 10 * 57.64 = 576.40
        assert res["danno_temporaneo"]["itt"]["importo"] == pytest.approx(576.40, abs=0.01)

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
        # itp_25 = 1 * 14.41
        assert res["danno_temporaneo"]["itp_25"]["importo"] == pytest.approx(14.41, abs=0.01)

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

    def test_formula_art_139_valore_punto_per_punti(self):
        # Art. 139 co. 2 lett. a) e co. 6: valore punto = base x coefficiente del grado,
        # totale = valore punto x punti (come nelle tabelle allegate ai DM annuali)
        res = _call("danno_biologico_micro", percentuale_invalidita=9, eta_vittima=0)
        assert res["coefficiente_grado"] == 2.3
        assert res["valore_punto"] == pytest.approx(res["punto_base"] * 2.3, abs=0.01)
        assert res["danno_permanente"] == pytest.approx(res["punto_base"] * 2.3 * 9, abs=0.05)
        res4 = _call("danno_biologico_micro", percentuale_invalidita=4, eta_vittima=25)
        assert len(res4["dettaglio_punti"]) == 1
        assert res4["danno_permanente"] == pytest.approx(
            res4["punto_base"] * 1.3 * 4 * (1 - 0.005 * 15), abs=0.05
        )

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

    def test_personalizzazione_30pct_tetto_art_138(self):
        res = _call(
            "danno_biologico_macro",
            percentuale_invalidita=20,
            eta_vittima=30,
            personalizzazione_pct=30.0,
        )
        assert res["maggiorazione_morale"] == pytest.approx(res["danno_base"] * 0.30, abs=0.01)
        assert res["totale_risarcimento"] == pytest.approx(res["danno_base"] * 1.30, abs=0.01)
        assert "avvertenza" in res
        oltre = _call("danno_biologico_macro", percentuale_invalidita=20, eta_vittima=30,
                      personalizzazione_pct=50.0)
        assert "errore" in oltre

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
    def test_milano_cap_coincide_con_tabella_a_punti_2024(self):
        # Tribunale di Milano, Osservatorio, Tabelle integrate a punti ed. 2024: cap di
        # 391.103,18 (genitori/figli/coniuge, 3.911,00 x 100 rivalutato 1,162268 su 336.500)
        # e 169.830,60 (fratelli/nonni/nipoti). The site rounds them to 391.103 / 169.831.
        for vittima, superstite, cap in (("figlio", "genitore", 391103.18), ("fratello", "fratello", 169830.60)):
            res = _call("danno_parentale", vittima=vittima, superstite=superstite, tabella="milano",
                        personalizzazione_pct=100)
            assert res["importo_liquidato"] == pytest.approx(cap, abs=0.005)

    def test_avvertenza_minimo_non_e_pavimento(self):
        # Milano 2024: "calcolo risarcitorio: si parte da 0,00", so the range minimum is not a floor
        res = _call("danno_parentale", vittima="figlio", superstite="genitore", tabella="milano")
        assert "non e' un pavimento" in res["avvertenza"]
        roma = _call("danno_parentale", vittima="coniuge", superstite="coniuge", tabella="roma")
        assert "stima" in roma["avvertenza"]

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
        # 20% invalidity, 30000 retribuzione
        # quota_biologica (simplified, STIMATO) = 30000 * 0.20 * 0.40 = 2400
        # quota_patrimoniale = retribuzione x coefficient x grado (art. 13 co. 2 lett. b D.Lgs. 38/2000;
        #   Tabella dei coefficienti DM 12/07/2000: 16-20% -> 0.4) = 30000 * 0.4 * 0.20 = 2400
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=20.0,
            tipo="permanente",
        )
        assert res["forma"] == "rendita"
        assert res["quota_danno_patrimoniale"] == pytest.approx(2400.0, abs=0.01)
        assert res["rendita_annua"] == pytest.approx(4800.0, abs=0.01)
        assert res["rendita_mensile"] == pytest.approx(400.0, abs=0.01)

    def test_permanente_16_quota_patrimoniale(self):
        # exactly 16%: 30000 * 0.4 * 0.16 = 1920 (coefficient 0.4 for 16-20%, DM 12/07/2000);
        # the previous formula gave 0 at 16%
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=16.0,
            tipo="permanente",
        )
        assert res["forma"] == "rendita"
        assert res["quota_danno_patrimoniale"] == pytest.approx(1920.0, abs=0.01)

    def test_coefficienti_patrimoniali_per_fascia(self):
        # Tabella dei coefficienti, DM 12/07/2000: 21-25 -> 0.5, 26-35 -> 0.6, 36-50 -> 0.7,
        # 51-70 -> 0.8, 71-85 -> 0.9, 86-100 -> 1.0. Quota = 10000 * coeff * grado
        for grado, coeff in ((21, 0.5), (25, 0.5), (26, 0.6), (35, 0.6), (36, 0.7), (50, 0.7),
                             (51, 0.8), (70, 0.8), (71, 0.9), (85, 0.9), (86, 1.0), (100, 1.0)):
            res = _call(
                "risarcimento_inail",
                retribuzione_annua=10000.0,
                percentuale_invalidita=float(grado),
                tipo="permanente",
            )
            assert res["coefficiente_patrimoniale"] == coeff, grado
            assert res["quota_danno_patrimoniale"] == pytest.approx(10000.0 * coeff * grado / 100, abs=0.01)

    def test_temporanea_carenza_art_73(self):
        # art. 73 DPR 1124/1965: the employer pays the whole day of the accident and 60% for the
        # carenza days; art. 68: INAIL pays 60% from the fourth day after, 75% from the 91st
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=36500.0,
            percentuale_invalidita=0.0,
            tipo="temporanea",
        )
        assert "intera retribuzione" in res["giorno_infortunio"]
        assert "60%" in res["primi_3_giorni"]

    def test_confine_capitale_rendita_a_16(self):
        # art. 13 co. 2 lett. a: capital below 16%, rendita from 16% (15.5 is still capital)
        res = _call(
            "risarcimento_inail",
            retribuzione_annua=30000.0,
            percentuale_invalidita=15.5,
            tipo="permanente",
        )
        assert res["forma"] == "capitale"

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
        # ITT 20 * 57.64 = 1152.8: danno biologico temporaneo (art. 139 co. 1 lett. b), not patrimoniale
        assert res["componenti"]["danno_biologico_temporaneo"]["itt"]["importo"] == pytest.approx(1152.8, abs=0.01)
        assert "itt" not in res["componenti"]["danno_patrimoniale_emergente"]
        assert res["componenti"]["danno_patrimoniale_emergente"]["totale"] == 0.0

    def test_danno_morale_percentuale(self):
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=5,
            eta_vittima=30,
            danno_morale_pct=20.0,  # art. 139 co. 3: micro cap 20%
        )
        bio = res["componenti"]["danno_biologico"]
        morale = res["componenti"]["danno_morale"]["importo"]
        assert morale == pytest.approx(bio * 0.20, abs=0.01)

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
            danno_morale_pct=10.0,
            danno_esistenziale_pct=5.0,
        )
        c = res["componenti"]
        expected = (
            c["danno_biologico"]
            + c["danno_biologico_temporaneo"]["totale"]
            + c["danno_morale"]["importo"]
            + c["danno_esistenziale"]["importo"]
            + c["danno_patrimoniale_emergente"]["totale"]
        )
        assert res["totale_risarcimento"] == pytest.approx(expected, abs=0.01)

    def test_micro_biologico_moltiplica_punti_per_coefficiente_del_grado(self):
        # Art. 139 co. 1 lett. a) e co. 6 Cod. Ass.: valore punto = 988,45 x coeff(grado) x
        # (1 - 0,005 x (eta - 10)), moltiplicato per i punti (DM 20/07/2026).
        # 9 punti a 10 anni: 988,45 x 2,3 x 9 = 20.460,915 (il tool sommava i gradi: 13.937,15)
        res = _call("danno_non_patrimoniale", percentuale_invalidita=9, eta_vittima=10)
        assert res["componenti"]["danno_biologico"] == pytest.approx(20460.92, abs=0.01)
        # 2 punti a 11 anni: 988,45 x 1,1 x 0,995 x 2 = 2.163,72 (il tool sommava i gradi: 2.065,37)
        res = _call("danno_non_patrimoniale", percentuale_invalidita=2, eta_vittima=11)
        assert res["componenti"]["danno_biologico"] == pytest.approx(2163.72, abs=0.01)
        # 5 punti a 35 anni: 988,45 x 1,5 x 0,875 x 5 = 6.486,70
        res = _call("danno_non_patrimoniale", percentuale_invalidita=5, eta_vittima=35)
        assert res["componenti"]["danno_biologico"] == pytest.approx(6486.70, abs=0.01)

    def test_micro_biologico_coincide_con_danno_biologico_micro(self):
        a = _call("danno_non_patrimoniale", percentuale_invalidita=7, eta_vittima=55)
        b = _call("danno_biologico_micro", percentuale_invalidita=7, eta_vittima=55)
        assert a["componenti"]["danno_biologico"] == pytest.approx(b["danno_permanente"], abs=0.01)

    def test_micro_personalizzazione_oltre_20_rifiutata(self):
        # Art. 139 co. 3 Cod. Ass.: aumento "fino al 20 per cento", importo esaustivo: morale +
        # esistenziale non si cumulano oltre il 20%.
        res = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=4,
            eta_vittima=30,
            danno_morale_pct=15.0,
            danno_esistenziale_pct=10.0,
        )
        assert "errore" in res
        ok = _call(
            "danno_non_patrimoniale",
            percentuale_invalidita=4,
            eta_vittima=30,
            danno_morale_pct=15.0,
            danno_esistenziale_pct=5.0,
        )
        assert "errore" not in ok

    def test_itt_sopra_9_percento_57_64(self):
        # DPR 12/2025 art. 3 co. 1: temporary damage is liquidated as art. 139 co. 1 lett. b): 20 x 57,64
        res = _call("danno_non_patrimoniale", percentuale_invalidita=10, eta_vittima=40, giorni_itt=20)
        assert res["componenti"]["danno_biologico_temporaneo"]["totale"] == pytest.approx(1152.80, abs=0.01)

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
    # Rule: art. 1 co. 119 L. 662/1996 (Tabella 1): 2 x stipendio tabellare x category percentage
    # (1: 100, 2: 92, 3: 75, 4: 61, 5: 44, 6: 27, 7: 12, 8: 6, una tantum 3), then art. 49 DPR 686/1957
    # (-25% over 50, -50% over 60, age at the event) and art. 50 (halved with pensione privilegiata).
    def test_categoria_1_stipendio_50000(self):
        # 2 x 50000 x 100% = 100000; the invalidity percentage does not enter the formula
        res = _call(
            "equo_indennizzo",
            categoria_tabella="1",
            percentuale_invalidita=100.0,
            stipendio_annuo=50000.0,
        )
        assert res["equo_indennizzo"] == pytest.approx(100000.0, abs=0.01)

    def test_categoria_8_valore_corretto(self):
        # Tabella 1 L. 662/1996: cat. 8 = 6% -> 2 x 25000 x 0.06 = 3000
        res = _call(
            "equo_indennizzo",
            categoria_tabella="8",
            percentuale_invalidita=10.0,
            stipendio_annuo=25000.0,
        )
        assert res["equo_indennizzo"] == pytest.approx(3000.0, abs=0.01)

    def test_categoria_5_44_per_cento(self):
        # cat. 5 = 44% -> 2 x 30000 x 0.44 = 26400
        res = _call(
            "equo_indennizzo",
            categoria_tabella="5",
            percentuale_invalidita=35.0,
            stipendio_annuo=30000.0,
        )
        assert res["equo_indennizzo"] == pytest.approx(26400.0, abs=0.01)

    def test_categoria_6_27_per_cento_senza_limite_pensione(self):
        # cat. 6 = 27% -> 2 x 28000 x 0.27 = 15120; art. 50 halving is by circumstance, not by category
        res = _call(
            "equo_indennizzo",
            categoria_tabella="6",
            percentuale_invalidita=25.0,
            stipendio_annuo=28000.0,
        )
        assert res["equo_indennizzo"] == pytest.approx(15120.0, abs=0.01)
        res = _call(
            "equo_indennizzo",
            categoria_tabella="6",
            percentuale_invalidita=25.0,
            stipendio_annuo=28000.0,
            pensione_privilegiata=True,
        )
        assert res["equo_indennizzo"] == pytest.approx(7560.0, abs=0.01)

    def test_categorie_2_3_4_7_da_tabella_1(self):
        # Tabella 1 L. 662/1996: 92, 75, 61, 12 percent of 2 x 10000
        for cat, atteso in (("2", 18400.0), ("3", 15000.0), ("4", 12200.0), ("7", 2400.0)):
            res = _call(
                "equo_indennizzo",
                categoria_tabella=cat,
                percentuale_invalidita=50.0,
                stipendio_annuo=10000.0,
            )
            assert res["equo_indennizzo"] == pytest.approx(atteso, abs=0.01), cat

    def test_riduzione_per_eta_art_49(self):
        # art. 49 co. 2 DPR 686/1957: -25% if over 50, -50% if over 60 (age at the event)
        # cat. 5, stipendio 30000: base 26400 -> 26400 (50 y), 19800 (51 y), 19800 (60 y), 13200 (61 y)
        atteso = {50: 26400.0, 51: 19800.0, 60: 19800.0, 61: 13200.0}
        for eta, valore in atteso.items():
            res = _call(
                "equo_indennizzo",
                categoria_tabella="5",
                percentuale_invalidita=35.0,
                stipendio_annuo=30000.0,
                eta_evento=eta,
            )
            assert res["equo_indennizzo"] == pytest.approx(valore, abs=0.01), eta

    def test_una_tantum_tabella_b(self):
        # Tabella B: 3% of the first-category amount -> 2 x 25000 x 0.03 = 1500
        for cat in ("9", "B", "una_tantum"):
            res = _call(
                "equo_indennizzo",
                categoria_tabella=cat,
                percentuale_invalidita=10.0,
                stipendio_annuo=25000.0,
            )
            assert res["equo_indennizzo"] == pytest.approx(1500.0, abs=0.01), cat

    def test_avviso_abrogazione_presente(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella="3",
            percentuale_invalidita=55.0,
            stipendio_annuo=40000.0,
        )
        assert "ABROGATO" in res["attenzione"]
        assert "DL 201/2011" in res["attenzione"]
        # art. 6 co. 1 DL 201/2011: the abrogation does not reach the security and defence comparto
        assert "sicurezza" in res["attenzione"]

    def test_riferimento_normativo_presente(self):
        res = _call(
            "equo_indennizzo",
            categoria_tabella="2",
            percentuale_invalidita=70.0,
            stipendio_annuo=40000.0,
        )
        assert "L. 662/1996" in res["riferimento_normativo"]

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
            categoria_tabella="10",
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
        for cat in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            res = _call(
                "equo_indennizzo",
                categoria_tabella=cat,
                percentuale_invalidita=50.0,
                stipendio_annuo=30000.0,
            )
            assert "equo_indennizzo" in res, f"Categoria {cat} fallita"
