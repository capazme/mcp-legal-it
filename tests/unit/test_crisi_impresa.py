import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.crisi_impresa")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# test_crisi_impresa
# ---------------------------------------------------------------------------

class TestCrisiImpresa:
    def test_nessun_indicatore_dscr_alto(self):
        result = _call("test_crisi_impresa", dscr=1.5)
        assert result["alert"] is False
        assert result["severita"] == "nessuno"
        assert result["numero_indicatori"] == 0
        assert result["indicatori_attivati"] == []

    def test_nessun_dato_nessun_segnale(self):
        # Art. 3 co. 4 CCII: no figure supplied, no signal (and the DSCR is no longer required).
        result = _call("test_crisi_impresa")
        assert result["alert"] is False
        assert result["segnali_art_3_co_4"] == []
        assert result["segnali_non_determinabili"] == []

    def test_dscr_basso_e_indice_di_prassi_a_12_mesi(self):
        # Art. 3 co. 3 lett. b) CCII: sustainability of debts "almeno per i dodici mesi successivi".
        # The DSCR itself is not in the text: it is reported as a convention ("prassi").
        result = _call("test_crisi_impresa", dscr=0.5)
        assert result["alert"] is True
        assert result["severita"] == "moderato"
        assert result["numero_indicatori"] == 1
        assert result["numero_segnali_normativi"] == 0
        assert any("DSCR" in s and "12 mesi" in s and "prassi" in s for s in result["indicatori_attivati"])
        assert "6 mesi" not in " ".join(result["indicatori_attivati"])

    def test_debiti_vs_attivo_e_indice_di_prassi(self):
        # Not in art. 3 CCII vigente (D.Lgs. 83/2022): kept only as a labelled convention.
        result = _call("test_crisi_impresa", dscr=1.5, debiti_vs_attivo_pct=85.0)
        assert result["numero_segnali_normativi"] == 0
        assert result["indicatori_di_prassi"] and "prassi" in result["indicatori_di_prassi"][0]

    def test_soglia_dscr_esattamente_1(self):
        result = _call("test_crisi_impresa", dscr=1.0)
        assert result["alert"] is False

    def test_esposizioni_bancarie_almeno_5_per_cento(self):
        # Art. 3 co. 4 lett. c) CCII: "almeno il cinque per cento del totale delle esposizioni",
        # so 5,00% already fires the signal and 4,99% does not.
        sotto = _call("test_crisi_impresa", dscr=1.2, esposizioni_scadute_pct=4.99)
        al_limite = _call("test_crisi_impresa", dscr=1.2, esposizioni_scadute_pct=5.0)
        sopra = _call("test_crisi_impresa", dscr=1.2, esposizioni_scadute_pct=5.1)
        assert sotto["alert"] is False
        assert al_limite["alert"] is True and al_limite["numero_segnali_normativi"] == 1
        assert "lett. c)" in al_limite["segnali_art_3_co_4"][0]
        assert sopra["alert"] is True

    def test_retribuzioni_oltre_la_meta_del_monte_mensile(self):
        # Art. 3 co. 4 lett. a) CCII: debts for wages overdue >= 30 days "pari a oltre la meta'"
        # of the monthly total: 5.000 of 10.000 is exactly half (no signal), 5.001 is over half.
        meta = _call(
            "test_crisi_impresa", retribuzioni_scadute_30gg=5_000.0, monte_retribuzioni_mensile=10_000.0
        )
        oltre = _call(
            "test_crisi_impresa", retribuzioni_scadute_30gg=5_001.0, monte_retribuzioni_mensile=10_000.0
        )
        assert meta["numero_segnali_normativi"] == 0
        assert oltre["numero_segnali_normativi"] == 1 and "lett. a)" in oltre["segnali_art_3_co_4"][0]

    def test_retribuzioni_senza_monte_non_determinabile(self):
        result = _call("test_crisi_impresa", retribuzioni_scadute_30gg=5_000.0)
        assert result["numero_segnali_normativi"] == 0
        assert len(result["segnali_non_determinabili"]) == 1

    def test_fornitori_scaduti_superiori_ai_non_scaduti(self):
        # Art. 3 co. 4 lett. b) CCII: overdue >= 90 days "di ammontare superiore" to the debts not yet due.
        pari = _call(
            "test_crisi_impresa", debiti_fornitori_scaduti_90gg=100_000.0, debiti_fornitori_non_scaduti=100_000.0
        )
        oltre = _call(
            "test_crisi_impresa", debiti_fornitori_scaduti_90gg=100_000.01, debiti_fornitori_non_scaduti=100_000.0
        )
        assert pari["numero_segnali_normativi"] == 0
        assert oltre["numero_segnali_normativi"] == 1 and "lett. b)" in oltre["segnali_art_3_co_4"][0]

    def test_inps_solo_giorni_non_basta(self):
        # Art. 25-novies co. 1 lett. a) CCII needs the delay (> 90 days) AND the amounts:
        # days alone are not determinable, they must not raise an alert.
        result = _call("test_crisi_impresa", dscr=1.2, giorni_ritardo_inps=91)
        assert result["alert"] is False
        assert len(result["segnali_non_determinabili"]) == 1
        assert "INPS" in result["segnali_non_determinabili"][0]

    def test_inps_con_lavoratori_giorni_e_importi(self):
        # Art. 25-novies co. 1 lett. a) n. 1): > 90 days and debt > 30% of the contributions due in the
        # previous year (30% of 50.000 = 15.000) and > 15.000 euro.
        segnale = _call(
            "test_crisi_impresa",
            giorni_ritardo_inps=91,
            debito_inps=15_000.01,
            contributi_inps_anno_precedente=50_000.0,
        )
        assert segnale["numero_segnali_normativi"] == 1
        assert "INPS" in segnale["segnali_art_3_co_4"][0]
        # exactly 15.000 is not "superiore" to 15.000
        al_limite = _call(
            "test_crisi_impresa",
            giorni_ritardo_inps=91,
            debito_inps=15_000.0,
            contributi_inps_anno_precedente=1_000.0,
        )
        assert al_limite["numero_segnali_normativi"] == 0
        # over 15.000 but not over 30% of 100.000 (= 30.000)
        sotto_30pct = _call(
            "test_crisi_impresa",
            giorni_ritardo_inps=91,
            debito_inps=20_000.0,
            contributi_inps_anno_precedente=100_000.0,
        )
        assert sotto_30pct["numero_segnali_normativi"] == 0
        # "oltre novanta giorni": 90 is not enough
        novanta = _call(
            "test_crisi_impresa",
            giorni_ritardo_inps=90,
            debito_inps=1_000_000.0,
            contributi_inps_anno_precedente=1.0,
        )
        assert novanta["numero_segnali_normativi"] == 0

    def test_inps_con_lavoratori_senza_contributi_anno_precedente_non_determinabile(self):
        result = _call("test_crisi_impresa", giorni_ritardo_inps=91, debito_inps=20_000.0)
        assert result["numero_segnali_normativi"] == 0
        assert len(result["segnali_non_determinabili"]) == 1

    def test_inps_senza_lavoratori_soglia_5000(self):
        # Art. 25-novies co. 1 lett. a) n. 2): imprese senza lavoratori, debt > 5.000 euro.
        al_limite = _call(
            "test_crisi_impresa", giorni_ritardo_inps=91, debito_inps=5_000.0, impresa_con_lavoratori=False
        )
        oltre = _call(
            "test_crisi_impresa", giorni_ritardo_inps=91, debito_inps=5_000.01, impresa_con_lavoratori=False
        )
        assert al_limite["numero_segnali_normativi"] == 0
        assert oltre["numero_segnali_normativi"] == 1

    def test_inail_oltre_90_giorni_e_5000_euro(self):
        # Art. 25-novies co. 1 lett. b): premi scaduti da oltre 90 giorni, debt > 5.000 euro.
        al_limite = _call("test_crisi_impresa", giorni_ritardo_inail=91, debito_inail=5_000.0)
        oltre = _call("test_crisi_impresa", giorni_ritardo_inail=91, debito_inail=5_000.01)
        novanta = _call("test_crisi_impresa", giorni_ritardo_inail=90, debito_inail=50_000.0)
        assert al_limite["numero_segnali_normativi"] == 0
        assert oltre["numero_segnali_normativi"] == 1
        assert novanta["numero_segnali_normativi"] == 0

    def test_ade_nessuna_soglia_a_giorni(self):
        # Art. 25-novies co. 1 lett. c) CCII: the Agenzia delle entrate signal is on the IVA amount;
        # a delay in days alone is not a criterion (it used to raise an alert at > 90 days).
        result = _call("test_crisi_impresa", dscr=1.2, giorni_ritardo_ade=120)
        assert result["alert"] is False
        assert result["avvertenze"] and "giorni_ritardo_ade" in result["avvertenze"][0]

    def test_ade_debito_iva_oltre_20000_in_ogni_caso(self):
        # Art. 25-novies co. 1 lett. c): "in ogni caso ... se il debito e' superiore all'importo di euro 20.000".
        al_limite = _call("test_crisi_impresa", debito_iva_ade=20_000.0, volume_affari_anno_precedente=1_000_000.0)
        oltre = _call("test_crisi_impresa", debito_iva_ade=20_000.01, volume_affari_anno_precedente=1_000_000.0)
        assert al_limite["numero_segnali_normativi"] == 0  # 20.000 is below 10% of 1.000.000
        assert oltre["numero_segnali_normativi"] == 1

    def test_ade_debito_iva_5000_e_10_per_cento_volume_affari(self):
        # Art. 25-novies co. 1 lett. c): debt > 5.000 euro and "non inferiore al 10 per cento" of the
        # volume d'affari: with volume 150.000 the debt of 15.000 is exactly 10% (fires),
        # with volume 150.001 it is below (does not fire); 5.000 is not over 5.000.
        al_10 = _call("test_crisi_impresa", debito_iva_ade=15_000.0, volume_affari_anno_precedente=150_000.0)
        sotto_10 = _call("test_crisi_impresa", debito_iva_ade=15_000.0, volume_affari_anno_precedente=150_001.0)
        sotto_5000 = _call("test_crisi_impresa", debito_iva_ade=5_000.0, volume_affari_anno_precedente=1.0)
        assert al_10["numero_segnali_normativi"] == 1
        assert sotto_10["numero_segnali_normativi"] == 0
        assert sotto_5000["numero_segnali_normativi"] == 0

    def test_ade_debito_iva_senza_volume_affari_non_determinabile(self):
        result = _call("test_crisi_impresa", debito_iva_ade=10_000.0)
        assert result["numero_segnali_normativi"] == 0
        assert len(result["segnali_non_determinabili"]) == 1

    def test_ader_soglie_per_forma_giuridica(self):
        # Art. 25-novies co. 1 lett. d): carichi scaduti da oltre 90 giorni, "superiori" a 100.000
        # (imprese individuali), 200.000 (societa' di persone), 500.000 (altre societa').
        casi = [
            ("impresa_individuale", 100_000.0, 0),
            ("impresa_individuale", 100_000.01, 1),
            ("societa_di_persone", 200_000.0, 0),
            ("societa_di_persone", 200_000.01, 1),
            ("altra_societa", 500_000.0, 0),
            ("altra_societa", 500_000.01, 1),
        ]
        for forma, importo, atteso in casi:
            r = _call(
                "test_crisi_impresa",
                debito_ader=importo,
                giorni_ritardo_ader=91,
                forma_giuridica=forma,
            )
            assert r["numero_segnali_normativi"] == atteso, (forma, importo)
        novanta = _call(
            "test_crisi_impresa", debito_ader=900_000.0, giorni_ritardo_ader=90, forma_giuridica="altra_societa"
        )
        assert novanta["numero_segnali_normativi"] == 0

    def test_ader_senza_forma_giuridica_non_determinabile(self):
        result = _call("test_crisi_impresa", debito_ader=300_000.0, giorni_ritardo_ader=91)
        assert result["numero_segnali_normativi"] == 0
        assert len(result["segnali_non_determinabili"]) == 1

    def test_forma_giuridica_non_valida_errore(self):
        with pytest.raises(ValueError):
            _call("test_crisi_impresa", debito_ader=1.0, giorni_ritardo_ader=91, forma_giuridica="srl")

    def test_tre_indicatori_critico(self):
        # Three art. 3 co. 4 signals (lett. c bank, lett. a wages, lett. d INPS); the ladder is a convention.
        result = _call(
            "test_crisi_impresa",
            esposizioni_scadute_pct=6.0,
            retribuzioni_scadute_30gg=6_000.0,
            monte_retribuzioni_mensile=10_000.0,
            giorni_ritardo_inps=120,
            debito_inps=20_000.0,
            contributi_inps_anno_precedente=50_000.0,
        )
        assert result["alert"] is True
        assert result["numero_segnali_normativi"] == 3
        assert result["severita"] == "critico"
        assert "prassi" in result["severita_criterio"]

    def test_due_indicatori_significativo(self):
        result = _call(
            "test_crisi_impresa",
            dscr=0.9,
            esposizioni_scadute_pct=10.0,
        )
        assert result["severita"] == "significativo"
        assert result["numero_indicatori"] == 2

    def test_dscr_negativo_errore(self):
        with pytest.raises(ValueError):
            _call("test_crisi_impresa", dscr=-0.1)

    def test_importo_negativo_errore(self):
        with pytest.raises(ValueError):
            _call("test_crisi_impresa", debito_inps=-1.0)

    def test_riferimento_normativo(self):
        # The rubric of art. 3 CCII vigente is "Adeguatezza delle misure e degli assetti"; "Indicatori
        # della crisi" was the rubric of the original art. 13 (now the piattaforma telematica).
        result = _call("test_crisi_impresa", dscr=1.0)
        assert "Art. 3" in result["riferimento_normativo"]
        assert "CCII" in result["riferimento_normativo"]
        assert "Adeguatezza delle misure e degli assetti" in result["riferimento_normativo"]
        assert "Indicatori della crisi" not in result["riferimento_normativo"]
        assert "25-novies" in result["riferimento_normativo"]

    def test_raccomandazione_presente(self):
        result = _call("test_crisi_impresa", dscr=0.5)
        assert isinstance(result["raccomandazione"], str)
        assert len(result["raccomandazione"]) > 0


# ---------------------------------------------------------------------------
# composizione_negoziata
# ---------------------------------------------------------------------------

class TestComposizioneNegoziata:
    def test_commerciale_accesso_ordinario_art_12(self):
        # Art. 12 co. 1 CCII: "L'imprenditore commerciale e agricolo puo' chiedere la nomina di un esperto".
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
            tipo_impresa="commerciale",
        )
        assert result["ammissibile"] is True
        assert "commerciale" in result["tipo_impresa"]
        assert result["impresa_minore"] is False
        assert "Art. 12 co. 1" in result["accesso"]

    def test_agricola_non_minore_accede_ex_art_12_co_1(self):
        # Art. 12 co. 1 CCII names the "imprenditore commerciale e agricolo"; art. 25-quater ("Imprese
        # sotto soglia") applies only to those with the joint requirements of art. 2 co. 1 lett. d).
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
            tipo_impresa="agricola",
        )
        assert result["ammissibile"] is True
        assert "Art. 12 co. 1" in result["accesso"]
        assert "25-quater" not in result["accesso"]
        assert any("art. 12" in r for r in result["requisiti_soddisfatti"])
        assert not any("accesso ex art. 25-quater" in r for r in result["requisiti_soddisfatti"])

    def test_agricola_minore_accede_ex_art_25_quater(self):
        # Art. 25-quater co. 1 CCII: imprenditore agricolo con i requisiti congiunti dell'art. 2 co. 1 lett. d).
        result = _call(
            "composizione_negoziata",
            fatturato=150_000.0,
            attivo=250_000.0,
            dipendenti=3,
            debito_totale=100_000.0,
            tipo_impresa="agricola",
        )
        assert result["ammissibile"] is True
        assert result["impresa_minore"] is True
        assert "Art. 25-quater co. 1" in result["accesso"]

    def test_sotto_soglia_ai_limiti_e_impresa_minore(self):
        # Art. 2 co. 1 lett. d) CCII: "non superiore" to 300.000 (attivo), 200.000 (ricavi), 500.000 (debiti).
        result = _call(
            "composizione_negoziata",
            fatturato=200_000.0,
            attivo=300_000.0,
            dipendenti=3,
            debito_totale=500_000.0,
            tipo_impresa="sotto_soglia",
        )
        assert result["impresa_minore"] is True
        assert result["requisiti_mancanti"] == []
        assert "Art. 25-quater co. 1" in result["accesso"]
        assert result["ammissibile"] is True

    def test_sotto_soglia_un_solo_requisito_mancante(self):
        # Art. 2 co. 1 lett. d): joint requirements; ricavi 200.000,01 > 200.000 is the only one missing
        # (attivo 100.000 and debiti 100.000 are within the limits). Not an impresa minore, but the
        # imprenditore commerciale/agricolo still accedes ex art. 12 co. 1.
        result = _call(
            "composizione_negoziata",
            fatturato=200_000.01,
            attivo=100_000.0,
            dipendenti=3,
            debito_totale=100_000.0,
            tipo_impresa="sotto_soglia",
        )
        assert result["impresa_minore"] is False
        assert len(result["requisiti_mancanti"]) == 1 and "Ricavi" in result["requisiti_mancanti"][0]
        assert len(result["requisiti_soddisfatti"]) >= 3  # attivo, debiti and the access line
        assert "nessuna soglia" not in " ".join(result["requisiti_soddisfatti"]).lower()
        assert "Art. 12 co. 1" in result["accesso"]
        assert result["ammissibile"] is True

    def test_sotto_soglia_nessun_requisito_accesso_ordinario(self):
        result = _call(
            "composizione_negoziata",
            fatturato=400_000.0,
            attivo=500_000.0,
            dipendenti=5,
            debito_totale=600_000.0,
            tipo_impresa="sotto_soglia",
        )
        assert result["impresa_minore"] is False
        assert len(result["requisiti_mancanti"]) == 3
        assert "Art. 12 co. 1" in result["accesso"]

    def test_commerciale_minore_accede_ex_art_25_quater(self):
        result = _call(
            "composizione_negoziata",
            fatturato=180_000.0,
            attivo=250_000.0,
            dipendenti=2,
            debito_totale=400_000.0,
        )
        assert result["impresa_minore"] is True
        assert "Art. 25-quater co. 1" in result["accesso"]

    def test_cause_ostative_art_25_quinquies(self):
        # Art. 25-quinquies co. 1 CCII: no istanza while a domanda di accesso a uno strumento di
        # regolazione is pending, nor within four months of a renunciation to it.
        base = dict(fatturato=500_000.0, attivo=800_000.0, dipendenti=10, debito_totale=300_000.0)
        pendente = _call("composizione_negoziata", procedimento_regolazione_pendente=True, **base)
        rinuncia = _call("composizione_negoziata", rinuncia_domanda_ultimi_4_mesi=True, **base)
        libero = _call("composizione_negoziata", **base)
        assert pendente["ammissibile"] is False and "25-quinquies" in pendente["ostacoli_art_25_quinquies"][0]
        assert rinuncia["ammissibile"] is False and "quattro mesi" in rinuncia["ostacoli_art_25_quinquies"][0]
        assert libero["ammissibile"] is True and libero["ostacoli_art_25_quinquies"] == []

    def test_condizioni_art_12_co_1_da_verificare(self):
        # Art. 12 co. 1 CCII: squilibrio + risanamento ragionevolmente perseguibile (art. 13 co. 2: test pratico).
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
        )
        testo = " ".join(result["condizioni_da_verificare"])
        assert "art. 12 co. 1" in testo.lower() and "art. 13 co. 2" in testo.lower()

    def test_indicatori_debito_fatturato_informativi(self):
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=1_000_000.0,
            dipendenti=10,
            debito_totale=800_000.0,
        )
        assert result["indicatori"]["rapporto_debito_fatturato"] == pytest.approx(1.6, abs=0.01)
        assert result["indicatori"]["rapporto_debito_attivo_pct"] == pytest.approx(80.0, abs=0.01)

    def test_risanamento_non_deciso_dal_rapporto_debito_fatturato(self):
        # The CCII fixes no debt/turnover threshold: the ragionevole perseguibilita' of the risanamento
        # is checked with the test pratico (art. 13 co. 2). The tool no longer answers yes/no on it.
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=1_000_000.0,
        )
        assert "risanamento_ragionevole" not in result["indicatori"]
        assert result["indicatori"]["euristica_di_prassi_debito_inferiore_a_2x_fatturato"] is False
        assert "art. 13 co. 2" in result["indicatori"]["nota_risanamento"]

    def test_dipendenti_non_incide_sull_accesso(self):
        # Art. 2 co. 1 lett. d) CCII does not consider the number of employees.
        a = _call("composizione_negoziata", fatturato=150_000.0, attivo=250_000.0, dipendenti=0, debito_totale=100_000.0)
        b = _call("composizione_negoziata", fatturato=150_000.0, attivo=250_000.0, dipendenti=500, debito_totale=100_000.0)
        assert a == b

    def test_durata_incarico_art_17_co_7(self):
        # Art. 17 co. 7 CCII: 180 days from the acceptance, extension "per non oltre centottanta giorni".
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
        )
        assert result["durata_max"].count("180") == 2 and "art. 17 co. 7" in result["durata_max"]

    def test_misure_e_effetti_artt_18_20_22_24(self):
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
        )
        citati = " ".join(result["misure_protettive"])
        assert len(result["misure_protettive"]) == 4
        # art. 18 co. 1: protective measures are requested; art. 22 co. 1 lett. a): prededuzione of
        # financings AUTHORISED by the tribunal; art. 24 co. 2: exemption from art. 166 co. 2 clawback.
        assert "su richiesta" in citati and "art. 18" in citati
        assert "art. 20" in citati
        assert "autorizzati dal tribunale" in citati and "art. 22 co. 1 lett. a)" in citati
        assert "art. 24 co. 2" in citati
        assert "interinali" not in citati

    def test_impresa_minore_art_24_solo_co_3_e_4(self):
        # Art. 25-quater co. 5 CCII recalls, for imprese sotto soglia, only art. 24 commi 3 e 4.
        result = _call(
            "composizione_negoziata",
            fatturato=150_000.0,
            attivo=250_000.0,
            dipendenti=3,
            debito_totale=100_000.0,
        )
        art_24 = [m for m in result["misure_protettive"] if "art. 24" in m]
        assert len(art_24) == 1 and "co. 3 e 4" in art_24[0] and "non si applica l'esenzione" in art_24[0]

    def test_tipo_non_valido_errore(self):
        with pytest.raises(ValueError):
            _call(
                "composizione_negoziata",
                fatturato=500_000.0,
                attivo=800_000.0,
                dipendenti=5,
                debito_totale=300_000.0,
                tipo_impresa="invalido",
            )

    def test_valore_negativo_errore(self):
        with pytest.raises(ValueError):
            _call(
                "composizione_negoziata",
                fatturato=-100.0,
                attivo=800_000.0,
                dipendenti=5,
                debito_totale=300_000.0,
            )

    def test_riferimento_normativo(self):
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
        )
        assert "art. 12" in result["riferimento_normativo"].lower() or "Artt. 12" in result["riferimento_normativo"]


# ---------------------------------------------------------------------------
# concordato_preventivo
# ---------------------------------------------------------------------------

class TestConcordatoPreventivo:
    def test_liquidatorio_15pct_non_ammissibile(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=200_000.0,
            creditori_chirografari=500_000.0,
            proposta_pct_chirografari=15.0,
            tipo="liquidatorio",
        )
        assert result["ammissibile"] is False
        assert result["soglia_minima_pct"] == 20.0

    def test_liquidatorio_25pct_ammissibile(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=200_000.0,
            creditori_chirografari=500_000.0,
            proposta_pct_chirografari=25.0,
            tipo="liquidatorio",
        )
        assert result["ammissibile"] is True
        assert result["proposta_chirografari_euro"] == pytest.approx(125_000.0)

    def test_liquidatorio_esattamente_20pct_ammissibile(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=300_000.0,
            proposta_pct_chirografari=20.0,
            tipo="liquidatorio",
        )
        assert result["ammissibile"] is True

    def test_continuita_no_soglia_minima(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=400_000.0,
            proposta_pct_chirografari=5.0,
            tipo="continuita",
        )
        assert result["ammissibile"] is True
        assert result["soglia_minima_pct"] == 0.0

    def test_calcolo_totale_debito(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=200_000.0,
            creditori_chirografari=800_000.0,
            proposta_pct_chirografari=30.0,
        )
        assert result["totale_debito"] == pytest.approx(1_000_000.0)

    def test_calcolo_proposta_totale(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=200_000.0,
            proposta_pct_chirografari=50.0,
            proposta_pct_privilegiati=100.0,
        )
        assert result["proposta_privilegiati_euro"] == pytest.approx(100_000.0)
        assert result["proposta_chirografari_euro"] == pytest.approx(100_000.0)
        assert result["proposta_totale"] == pytest.approx(200_000.0)

    def test_privilegiati_parziali_nota(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=200_000.0,
            creditori_chirografari=500_000.0,
            proposta_pct_chirografari=25.0,
            proposta_pct_privilegiati=80.0,
        )
        assert "degradazione" in result["nota_privilegiati"].lower()

    def test_percentuale_fuori_range_errore(self):
        with pytest.raises(ValueError):
            _call(
                "concordato_preventivo",
                creditori_privilegiati=100_000.0,
                creditori_chirografari=200_000.0,
                proposta_pct_chirografari=110.0,
            )

    def test_tipo_non_valido_errore(self):
        with pytest.raises(ValueError):
            _call(
                "concordato_preventivo",
                creditori_privilegiati=100_000.0,
                creditori_chirografari=200_000.0,
                proposta_pct_chirografari=25.0,
                tipo="invalido",
            )

    def test_voto_requisito_presente(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=200_000.0,
            proposta_pct_chirografari=25.0,
        )
        assert isinstance(result["voto_requisito"], str)
        assert len(result["voto_requisito"]) > 0

    def test_riferimento_normativo(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=200_000.0,
            proposta_pct_chirografari=25.0,
        )
        assert "84" in result["riferimento_normativo"]
        assert "CCII" in result["riferimento_normativo"]


# ---------------------------------------------------------------------------
# compenso_occ
# ---------------------------------------------------------------------------

class TestCompensoOcc:
    def test_passivo_piccolo_minimo_ristrutturazione(self):
        result = _call("compenso_occ", passivo=10_000.0, tipo="ristrutturazione")
        # 10.000 * 5% = 500 < minimo 1.500
        assert result["compenso"] == 1_500.0
        assert result["minimo_applicato"] is True

    def test_passivo_piccolo_minimo_liquidazione(self):
        result = _call("compenso_occ", passivo=20_000.0, tipo="liquidazione")
        # 20.000 * 7% = 1.400 < minimo 2.000
        assert result["compenso"] == 2_000.0
        assert result["minimo_applicato"] is True

    def test_passivo_50000_ristrutturazione(self):
        result = _call("compenso_occ", passivo=50_000.0, tipo="ristrutturazione")
        # 50.000 * 5% = 2.500
        assert result["compenso"] == pytest.approx(2_500.0)
        assert result["minimo_applicato"] is False

    def test_passivo_100000_ristrutturazione(self):
        result = _call("compenso_occ", passivo=100_000.0, tipo="ristrutturazione")
        # 100.000 * 5% = 5.000
        assert result["compenso"] == pytest.approx(5_000.0)
        assert result["minimo_applicato"] is False

    def test_passivo_300000_progressivo_ristrutturazione(self):
        result = _call("compenso_occ", passivo=300_000.0, tipo="ristrutturazione")
        # 100.000 * 5% = 5.000
        # 200.000 * 3% = 6.000
        # totale = 11.000
        assert result["compenso"] == pytest.approx(11_000.0)
        assert len(result["dettaglio_fasce"]) == 2

    def test_passivo_600000_tre_fasce_ristrutturazione(self):
        result = _call("compenso_occ", passivo=600_000.0, tipo="ristrutturazione")
        # 100.000 * 5% = 5.000
        # 400.000 * 3% = 12.000
        # 100.000 * 1% = 1.000
        # totale = 18.000
        assert result["compenso"] == pytest.approx(18_000.0)
        assert len(result["dettaglio_fasce"]) == 3

    def test_passivo_300000_liquidazione(self):
        result = _call("compenso_occ", passivo=300_000.0, tipo="liquidazione")
        # 100.000 * 7% = 7.000
        # 200.000 * 4% = 8.000
        # totale = 15.000
        assert result["compenso"] == pytest.approx(15_000.0)

    def test_passivo_zero_minimo(self):
        result = _call("compenso_occ", passivo=0.0, tipo="ristrutturazione")
        assert result["compenso"] == 1_500.0
        assert result["minimo_applicato"] is True

    def test_passivo_negativo_errore(self):
        with pytest.raises(ValueError):
            _call("compenso_occ", passivo=-1.0)

    def test_tipo_non_valido_errore(self):
        with pytest.raises(ValueError):
            _call("compenso_occ", passivo=100_000.0, tipo="invalido")

    def test_dettaglio_fasce_struttura(self):
        result = _call("compenso_occ", passivo=300_000.0)
        for fascia in result["dettaglio_fasce"]:
            assert "fascia" in fascia
            assert "imponibile" in fascia
            assert "aliquota_pct" in fascia
            assert "importo" in fascia

    def test_riferimento_normativo(self):
        result = _call("compenso_occ", passivo=100_000.0)
        assert "D.M. 202/2014" in result["riferimento_normativo"]
        assert "OCC" in result["riferimento_normativo"]
