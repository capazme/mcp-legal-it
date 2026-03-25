"""Unit tests for src.tools.fatturazione_avvocati."""

import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.fatturazione_avvocati")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


# ---------------------------------------------------------------------------
# parcella_avvocato_civile
# ---------------------------------------------------------------------------

class TestParcellaAvvocatoCivile:

    def test_happy_path_all_fasi(self):
        r = _call("parcella_avvocato_civile", valore_causa=10000.0)
        assert r["valore_causa"] == 10000.0
        assert r["livello"] == "medio"
        assert len(r["fasi"]) == 4
        assert r["totale_compenso"] > 0
        assert "DM 55/2014" in r["riferimento_normativo"]

    def test_scaglione_1100(self):
        r = _call("parcella_avvocato_civile", valore_causa=1000.0, livello="medio")
        # scaglione fino_a 1100: studio=131, introduttiva=131, istruttoria=200, decisionale=200
        assert r["totale_compenso"] == pytest.approx(131 + 131 + 200 + 200, abs=0.01)
        assert "1100" in r["scaglione"]

    def test_scaglione_5200(self):
        r = _call("parcella_avvocato_civile", valore_causa=5000.0, livello="medio")
        assert r["totale_compenso"] == pytest.approx(425 + 425 + 851 + 851, abs=0.01)

    def test_scaglione_26000(self):
        r = _call("parcella_avvocato_civile", valore_causa=20000.0, livello="medio")
        assert r["totale_compenso"] == pytest.approx(919 + 777 + 1680 + 1701, abs=0.01)

    def test_fasi_parziali(self):
        r = _call("parcella_avvocato_civile", valore_causa=10000.0, fasi=["studio", "introduttiva"])
        assert len(r["fasi"]) == 2
        assert r["totale_compenso"] == pytest.approx(919 + 777, abs=0.01)

    def test_livello_min(self):
        r_min = _call("parcella_avvocato_civile", valore_causa=10000.0, livello="min")
        r_max = _call("parcella_avvocato_civile", valore_causa=10000.0, livello="max")
        assert r_min["totale_compenso"] < r_max["totale_compenso"]

    def test_livello_invalido(self):
        r = _call("parcella_avvocato_civile", valore_causa=10000.0, livello="sbagliato")
        assert "errore" in r

    def test_fase_invalida(self):
        r = _call("parcella_avvocato_civile", valore_causa=10000.0, fasi=["studio", "inesistente"])
        assert "errore" in r

    def test_scaglione_oltre(self):
        r = _call("parcella_avvocato_civile", valore_causa=50_000_000.0, livello="medio")
        assert "oltre" in r["scaglione"]
        assert r["totale_compenso"] > 0

    def test_dettaglio_fasi_structure(self):
        r = _call("parcella_avvocato_civile", valore_causa=10000.0)
        for fase in r["fasi"]:
            assert "fase" in fase
            assert "importo" in fase
            assert fase["importo"] > 0


# ---------------------------------------------------------------------------
# parcella_avvocato_penale
# ---------------------------------------------------------------------------

class TestParcellaAvvocatoPenale:

    def test_tribunale_monocratico_all_fasi(self):
        r = _call("parcella_avvocato_penale", competenza="tribunale_monocratico")
        assert r["competenza"] == "tribunale_monocratico"
        assert r["totale_compenso"] == pytest.approx(473 + 567 + 1134 + 1418, abs=0.01)
        assert "Tribunale" in r["label"]

    def test_cassazione_no_istruttoria(self):
        # cassazione.istruttoria is null in parametri — should be excluded from default fasi
        r = _call("parcella_avvocato_penale", competenza="cassazione")
        fasi_nomi = [f["fase"] for f in r["fasi"]]
        assert "istruttoria" not in fasi_nomi

    def test_giudice_pace(self):
        r = _call("parcella_avvocato_penale", competenza="giudice_pace", livello="medio")
        assert r["totale_compenso"] == pytest.approx(378 + 473 + 756 + 662, abs=0.01)

    def test_livello_max(self):
        r_medio = _call("parcella_avvocato_penale", competenza="tribunale_monocratico", livello="medio")
        r_max = _call("parcella_avvocato_penale", competenza="tribunale_monocratico", livello="max")
        assert r_max["totale_compenso"] > r_medio["totale_compenso"]

    def test_fasi_parziali(self):
        r = _call("parcella_avvocato_penale", competenza="tribunale_monocratico", fasi=["studio"])
        assert len(r["fasi"]) == 1
        assert r["totale_compenso"] == pytest.approx(473, abs=0.01)

    def test_fase_non_disponibile_per_competenza(self):
        # cassazione does not have istruttoria
        r = _call("parcella_avvocato_penale", competenza="cassazione", fasi=["istruttoria"])
        assert "errore" in r

    def test_competenza_invalida(self):
        r = _call("parcella_avvocato_penale", competenza="corte_dei_conti")
        assert "errore" in r

    def test_livello_invalido(self):
        r = _call("parcella_avvocato_penale", competenza="giudice_pace", livello="altissimo")
        assert "errore" in r

    def test_fase_invalida(self):
        r = _call("parcella_avvocato_penale", competenza="giudice_pace", fasi=["inesistente"])
        assert "errore" in r

    def test_returns_riferimento_normativo(self):
        r = _call("parcella_avvocato_penale", competenza="corte_appello")
        assert "DM 55/2014" in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# parcella_stragiudiziale
# ---------------------------------------------------------------------------

class TestParcellaStratragiudiziale:

    def test_happy_path(self):
        r = _call("parcella_stragiudiziale", valore_pratica=10000.0)
        assert r["valore_pratica"] == 10000.0
        assert r["livello"] == "medio"
        assert r["compenso"] > 0

    def test_scaglione_1100(self):
        r = _call("parcella_stragiudiziale", valore_pratica=1000.0, livello="medio")
        assert r["compenso"] == 284

    def test_scaglione_5200(self):
        r = _call("parcella_stragiudiziale", valore_pratica=5000.0, livello="medio")
        assert r["compenso"] == 1276

    def test_scaglione_26000(self):
        r = _call("parcella_stragiudiziale", valore_pratica=20000.0, livello="medio")
        assert r["compenso"] == 1985

    def test_livello_min_less_than_max(self):
        r_min = _call("parcella_stragiudiziale", valore_pratica=10000.0, livello="min")
        r_max = _call("parcella_stragiudiziale", valore_pratica=10000.0, livello="max")
        assert r_min["compenso"] < r_max["compenso"]

    def test_scaglione_oltre(self):
        r = _call("parcella_stragiudiziale", valore_pratica=1_000_000.0)
        assert "oltre" in r["scaglione"]

    def test_livello_invalido(self):
        r = _call("parcella_stragiudiziale", valore_pratica=10000.0, livello="sbagliato")
        assert "errore" in r


# ---------------------------------------------------------------------------
# parcella_volontaria_giurisdizione
# ---------------------------------------------------------------------------

class TestParcellaVolontariaGiurisdizione:

    def test_happy_path(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=10000.0)
        assert r["valore_causa"] == 10000.0
        assert len(r["fasi"]) == 2
        assert r["totale_compenso"] > 0

    def test_scaglione_5200(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=5000.0, livello="medio")
        # scaglione fino_a 5200: studio=213, trattazione=212
        assert r["totale_compenso"] == pytest.approx(213 + 212, abs=0.01)

    def test_scaglione_26000(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=20000.0, livello="medio")
        assert r["totale_compenso"] == pytest.approx(709 + 709, abs=0.01)

    def test_fase_studio_only(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=10000.0, fasi=["studio"])
        assert len(r["fasi"]) == 1

    def test_livello_invalido(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=10000.0, livello="sbagliato")
        assert "errore" in r

    def test_fase_invalida(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=10000.0, fasi=["istruttoria"])
        assert "errore" in r

    def test_scaglione_oltre(self):
        r = _call("parcella_volontaria_giurisdizione", valore_causa=1_000_000.0)
        assert "oltre" in r["scaglione"]


# ---------------------------------------------------------------------------
# preventivo_volontaria_giurisdizione
# ---------------------------------------------------------------------------

class TestPreventivoVolontariaGiurisdizione:

    def test_happy_path_returns_testo(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000.0)
        assert "testo_preventivo" in r
        assert "PREVENTIVO VOLONTARIA" in r["testo_preventivo"]
        assert "dettaglio_calcoli" in r

    def test_calcoli_sg_cpa_iva(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000.0, livello="medio")
        d = r["dettaglio_calcoli"]
        tc = d["totale_compensi"]
        sg = round(tc * 0.15, 2)
        sub = round(tc + sg, 2)
        cpa = round(sub * 0.04, 2)
        imp_iva = round(sub + cpa, 2)
        iva = round(imp_iva * 0.22, 2)
        assert d["spese_generali_15pct"] == pytest.approx(sg, abs=0.01)
        assert d["cpa_4pct"] == pytest.approx(cpa, abs=0.01)
        assert d["iva_22pct"] == pytest.approx(iva, abs=0.01)
        assert d["totale_onorari"] == pytest.approx(round(imp_iva + iva, 2), abs=0.01)

    def test_no_spese_generali(self):
        r_con = _call("preventivo_volontaria_giurisdizione", valore_causa=10000.0, spese_generali=True)
        r_senza = _call("preventivo_volontaria_giurisdizione", valore_causa=10000.0, spese_generali=False)
        assert r_senza["dettaglio_calcoli"]["spese_generali_15pct"] == 0.0
        assert r_senza["dettaglio_calcoli"]["totale_onorari"] < r_con["dettaglio_calcoli"]["totale_onorari"]

    def test_no_iva(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000.0, iva=False)
        assert r["dettaglio_calcoli"]["iva_22pct"] == 0.0
        assert "IVA" not in r["testo_preventivo"]

    def test_no_cpa(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000.0, cpa=False)
        assert r["dettaglio_calcoli"]["cpa_4pct"] == 0.0

    def test_livello_invalido(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000.0, livello="sbagliato")
        assert "errore" in r

    def test_fase_invalida(self):
        r = _call("preventivo_volontaria_giurisdizione", valore_causa=10000.0, fasi=["istruttoria"])
        assert "errore" in r


# ---------------------------------------------------------------------------
# fattura_avvocato
# ---------------------------------------------------------------------------

class TestFatturaAvvocato:

    def test_ordinario_con_cpa(self):
        r = _call("fattura_avvocato", imponibile=1000.0)
        assert r["regime"] == "ordinario"
        assert r["imponibile"] == 1000.0
        assert r["cpa_4pct"] == pytest.approx(40.0, abs=0.01)
        assert r["imponibile_iva"] == pytest.approx(1040.0, abs=0.01)
        assert r["iva_22pct"] == pytest.approx(1040.0 * 0.22, abs=0.01)
        assert r["ritenuta_acconto_20pct"] == pytest.approx(200.0, abs=0.01)
        totale_atteso = round(1040.0 + 1040.0 * 0.22 - 200.0, 2)
        assert r["totale_fattura"] == pytest.approx(totale_atteso, abs=0.01)

    def test_forfettario_no_iva_no_ritenuta(self):
        r = _call("fattura_avvocato", imponibile=1000.0, regime="forfettario")
        assert r["iva_22pct"] == 0.0
        assert r["ritenuta_acconto_20pct"] == 0.0
        assert r["totale_fattura"] == pytest.approx(1040.0, abs=0.01)

    def test_forfettario_no_cpa(self):
        r = _call("fattura_avvocato", imponibile=1000.0, regime="forfettario", cpa=False)
        assert r["cpa_4pct"] == 0.0
        assert r["totale_fattura"] == pytest.approx(1000.0, abs=0.01)

    def test_ordinario_no_cpa(self):
        r = _call("fattura_avvocato", imponibile=1000.0, cpa=False)
        assert r["cpa_4pct"] == 0.0
        assert r["imponibile_iva"] == pytest.approx(1000.0, abs=0.01)

    def test_regime_invalido(self):
        r = _call("fattura_avvocato", imponibile=1000.0, regime="inesistente")
        assert "errore" in r

    def test_voci_ordinario(self):
        r = _call("fattura_avvocato", imponibile=500.0)
        descrizioni = [v["descrizione"] for v in r["voci"]]
        assert any("CPA" in d for d in descrizioni)
        assert any("IVA" in d for d in descrizioni)
        assert any("Ritenuta" in d for d in descrizioni)

    def test_voci_forfettario(self):
        r = _call("fattura_avvocato", imponibile=500.0, regime="forfettario")
        importi = [v["importo"] for v in r["voci"]]
        # IVA voce ha importo 0 in forfettario
        assert 0.0 in importi


# ---------------------------------------------------------------------------
# nota_spese
# ---------------------------------------------------------------------------

class TestNotaSpese:

    def test_happy_path_compenso_only(self):
        voci = [{"descrizione": "Fase studio", "importo": 1000.0, "tipo": "compenso"}]
        r = _call("nota_spese", voci=voci)
        assert r["totale_compensi"] == pytest.approx(1000.0, abs=0.01)
        assert r["totale_spese_generali_15pct"] == 0.0

    def test_spese_generali_15pct(self):
        voci = [{"descrizione": "Compenso base", "importo": 1000.0, "tipo": "spese_generali_15pct"}]
        r = _call("nota_spese", voci=voci)
        assert r["totale_spese_generali_15pct"] == pytest.approx(150.0, abs=0.01)

    def test_cpa_e_iva_calcolati(self):
        voci = [{"descrizione": "Compenso", "importo": 1000.0, "tipo": "compenso"}]
        r = _call("nota_spese", voci=voci)
        assert r["cpa_4pct"] == pytest.approx(1000.0 * 0.04, abs=0.01)
        assert r["iva_22pct"] == pytest.approx(round(1000.0 * 1.04 * 0.22, 2), abs=0.01)

    def test_spese_vive_non_in_cpa(self):
        voci = [
            {"descrizione": "Contributo unificato", "importo": 237.0, "tipo": "spese_vive"},
        ]
        r = _call("nota_spese", voci=voci)
        assert r["totale_spese_vive"] == pytest.approx(237.0, abs=0.01)
        # spese vive non entrano nell'imponibile CPA/IVA
        assert r["cpa_4pct"] == 0.0

    def test_tipo_invalido(self):
        voci = [{"descrizione": "Prova", "importo": 100.0, "tipo": "tipo_sconosciuto"}]
        r = _call("nota_spese", voci=voci)
        assert "errore" in r

    def test_mix_voci(self):
        voci = [
            {"descrizione": "Compenso", "importo": 1000.0, "tipo": "compenso"},
            {"descrizione": "Spese generali", "importo": 1000.0, "tipo": "spese_generali_15pct"},
            {"descrizione": "Notifica", "importo": 27.0, "tipo": "spese_vive"},
        ]
        r = _call("nota_spese", voci=voci)
        assert r["totale_compensi"] == pytest.approx(1000.0, abs=0.01)
        assert r["totale_spese_generali_15pct"] == pytest.approx(150.0, abs=0.01)
        assert r["totale_spese_vive"] == pytest.approx(27.0, abs=0.01)
        assert r["totale_nota_spese"] > 0

    def test_spese_documentate(self):
        voci = [{"descrizione": "Fattura consulente", "importo": 500.0, "tipo": "spese_documentate"}]
        r = _call("nota_spese", voci=voci)
        assert r["totale_spese_vive"] == pytest.approx(500.0, abs=0.01)


# ---------------------------------------------------------------------------
# preventivo_civile
# ---------------------------------------------------------------------------

class TestPreventivoCivile:

    def test_happy_path(self):
        r = _call("preventivo_civile", valore_causa=10000.0)
        assert "testo_preventivo" in r
        assert "PREVENTIVO CAUSA CIVILE" in r["testo_preventivo"]
        d = r["dettaglio_calcoli"]
        assert d["totale_compensi"] > 0
        assert d["totale_spese_vive"] > 0
        assert d["totale_preventivo"] > 0

    def test_contributo_unificato_incluso(self):
        r = _call("preventivo_civile", valore_causa=10000.0)
        assert "contributo_unificato" in r["dettaglio_calcoli"]["spese_vive"]
        assert r["dettaglio_calcoli"]["spese_vive"]["contributo_unificato"] == 237

    def test_contributo_unificato_1100(self):
        r = _call("preventivo_civile", valore_causa=1000.0)
        assert r["dettaglio_calcoli"]["spese_vive"]["contributo_unificato"] == 43

    def test_contributo_unificato_5200(self):
        r = _call("preventivo_civile", valore_causa=5000.0)
        assert r["dettaglio_calcoli"]["spese_vive"]["contributo_unificato"] == 98

    def test_no_spese_generali(self):
        r = _call("preventivo_civile", valore_causa=10000.0, spese_generali=False)
        assert r["dettaglio_calcoli"]["spese_generali_15pct"] == 0.0

    def test_no_iva(self):
        r = _call("preventivo_civile", valore_causa=10000.0, iva=False)
        assert r["dettaglio_calcoli"]["iva_22pct"] == 0.0

    def test_no_cpa(self):
        r = _call("preventivo_civile", valore_causa=10000.0, cpa=False)
        assert r["dettaglio_calcoli"]["cpa_4pct"] == 0.0

    def test_livello_invalido(self):
        r = _call("preventivo_civile", valore_causa=10000.0, livello="sbagliato")
        assert "errore" in r

    def test_fase_invalida(self):
        r = _call("preventivo_civile", valore_causa=10000.0, fasi=["inesistente"])
        assert "errore" in r

    def test_totale_preventivo_somma_corretta(self):
        r = _call("preventivo_civile", valore_causa=10000.0)
        d = r["dettaglio_calcoli"]
        assert d["totale_preventivo"] == pytest.approx(
            d["totale_onorari"] + d["totale_spese_vive"], abs=0.01
        )

    def test_spese_vive_stimate_keys(self):
        r = _call("preventivo_civile", valore_causa=10000.0)
        sv = r["dettaglio_calcoli"]["spese_vive"]
        for k in ("contributo_unificato", "marca_da_bollo_iscrizione", "notifica_pec",
                  "notifica_ufficiale_giudiziario", "diritti_copia"):
            assert k in sv


# ---------------------------------------------------------------------------
# preventivo_stragiudiziale
# ---------------------------------------------------------------------------

class TestPreventivoStragiudiziale:

    def test_happy_path(self):
        r = _call("preventivo_stragiudiziale", valore_pratica=10000.0)
        assert "testo_preventivo" in r
        assert "STRAGIUDIZIALE" in r["testo_preventivo"]
        d = r["dettaglio_calcoli"]
        assert d["compenso_base"] > 0
        assert d["totale"] > d["compenso_base"]

    def test_calcoli_corretti(self):
        r = _call("preventivo_stragiudiziale", valore_pratica=10000.0, livello="medio")
        d = r["dettaglio_calcoli"]
        compenso = d["compenso_base"]
        sg = round(compenso * 0.15, 2)
        sub = round(compenso + sg, 2)
        cpa = round(sub * 0.04, 2)
        imp_iva = round(sub + cpa, 2)
        iva = round(imp_iva * 0.22, 2)
        assert d["spese_generali_15pct"] == pytest.approx(sg, abs=0.01)
        assert d["cpa_4pct"] == pytest.approx(cpa, abs=0.01)
        assert d["totale"] == pytest.approx(round(imp_iva + iva, 2), abs=0.01)

    def test_no_spese_generali(self):
        r = _call("preventivo_stragiudiziale", valore_pratica=10000.0, spese_generali=False)
        assert r["dettaglio_calcoli"]["spese_generali_15pct"] == 0.0

    def test_no_iva(self):
        r = _call("preventivo_stragiudiziale", valore_pratica=10000.0, iva=False)
        assert r["dettaglio_calcoli"]["iva_22pct"] == 0.0

    def test_livello_invalido(self):
        r = _call("preventivo_stragiudiziale", valore_pratica=10000.0, livello="sbagliato")
        assert "errore" in r

    def test_scaglione_label_in_testo(self):
        r = _call("preventivo_stragiudiziale", valore_pratica=1000.0)
        assert "1100" in r["testo_preventivo"]


# ---------------------------------------------------------------------------
# spese_trasferta_avvocati
# ---------------------------------------------------------------------------

class TestSpeseTrasfertaAvvocati:

    def test_auto_meno_4_ore(self):
        r = _call("spese_trasferta_avvocati", km_distanza=100.0, ore_assenza=3.0)
        assert r["rimborso_km"] == pytest.approx(100.0 * 0.30, abs=0.01)
        assert r["percentuale_indennita"] == 10
        assert r["indennita_trasferta"] == pytest.approx(540.0 * 0.10, abs=0.01)
        assert r["totale_stimato"] == pytest.approx(30.0 + 54.0, abs=0.01)

    def test_auto_8_ore(self):
        r = _call("spese_trasferta_avvocati", km_distanza=50.0, ore_assenza=6.0)
        assert r["percentuale_indennita"] == 20
        assert r["indennita_trasferta"] == pytest.approx(540.0 * 0.20, abs=0.01)

    def test_auto_oltre_8_ore(self):
        r = _call("spese_trasferta_avvocati", km_distanza=50.0, ore_assenza=10.0)
        assert r["percentuale_indennita"] == 40
        assert r["indennita_trasferta"] == pytest.approx(540.0 * 0.40, abs=0.01)

    def test_treno_no_rimborso_km(self):
        r = _call("spese_trasferta_avvocati", km_distanza=100.0, ore_assenza=4.0, mezzo="treno")
        assert r["rimborso_km"] == 0.0
        # totale_stimato = indennita only
        assert r["totale_stimato"] == r["indennita_trasferta"]

    def test_aereo_no_rimborso_km(self):
        r = _call("spese_trasferta_avvocati", km_distanza=500.0, ore_assenza=8.0, mezzo="aereo")
        assert r["rimborso_km"] == 0.0

    def test_pernottamento(self):
        r = _call("spese_trasferta_avvocati", km_distanza=100.0, ore_assenza=4.0, pernottamento=True)
        assert r["pernottamento"] is True
        assert r["nota_pernottamento"] is not None
        assert "piè di lista" in r["nota_pernottamento"]
        voci_nomi = [v["voce"] for v in r["voci"]]
        assert any("Pernottamento" in n for n in voci_nomi)

    def test_no_pernottamento(self):
        r = _call("spese_trasferta_avvocati", km_distanza=100.0, ore_assenza=4.0)
        assert r["nota_pernottamento"] is None

    def test_mezzo_invalido(self):
        r = _call("spese_trasferta_avvocati", km_distanza=100.0, ore_assenza=4.0, mezzo="bici")
        assert "errore" in r

    def test_km_zero(self):
        r = _call("spese_trasferta_avvocati", km_distanza=0.0, ore_assenza=2.0)
        assert r["rimborso_km"] == 0.0
        assert r["totale_stimato"] == r["indennita_trasferta"]


# ---------------------------------------------------------------------------
# modello_notula
# ---------------------------------------------------------------------------

class TestModelloNotula:

    def test_decreto_ingiuntivo(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="decreto_ingiuntivo",
            avvocato="Mario Rossi",
            cliente="Acme Srl",
            valore_causa=5000.0,
        )
        assert "testo_notula" in r
        assert "Mario Rossi" in r["testo_notula"]
        assert "Acme Srl" in r["testo_notula"]
        assert "decreto ingiuntivo" in r["testo_notula"].lower()
        d = r["dettaglio_calcoli"]
        # decreto_ingiuntivo usa fasi_default: studio, introduttiva
        fasi_nomi = [f["fase"] for f in d["fasi"]]
        assert "studio" in fasi_nomi
        assert "introduttiva" in fasi_nomi

    def test_decreto_ingiuntivo_cu_dimezzato(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="decreto_ingiuntivo",
            avvocato="A",
            cliente="B",
            valore_causa=10000.0,
        )
        sv = r["dettaglio_calcoli"]["spese_vive"]
        assert "contributo_unificato_dimezzato" in sv
        assert sv["contributo_unificato_dimezzato"] == pytest.approx(237.0 / 2, abs=0.01)

    def test_precetto(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="precetto",
            avvocato="A",
            cliente="B",
            valore_causa=5000.0,
        )
        sv = r["dettaglio_calcoli"]["spese_vive"]
        assert "notifica" in sv
        assert sv["notifica"] == 27.0

    def test_esecuzione_immobiliare_ha_trascrizione(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="esecuzione_immobiliare",
            avvocato="A",
            cliente="B",
            valore_causa=50000.0,
        )
        sv = r["dettaglio_calcoli"]["spese_vive"]
        assert "trascrizione" in sv
        assert sv["trascrizione"] == 300.0

    def test_totale_notula_somma_corretta(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="decreto_ingiuntivo",
            avvocato="A",
            cliente="B",
            valore_causa=10000.0,
        )
        d = r["dettaglio_calcoli"]
        assert d["totale_notula"] == pytest.approx(
            d["totale_onorari"] + d["totale_spese_vive"], abs=0.01
        )

    def test_tipo_procedimento_invalido(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="inesistente",
            avvocato="A",
            cliente="B",
            valore_causa=5000.0,
        )
        assert "errore" in r

    def test_livello_invalido(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="precetto",
            avvocato="A",
            cliente="B",
            valore_causa=5000.0,
            livello="sbagliato",
        )
        assert "errore" in r

    def test_fase_invalida(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="precetto",
            avvocato="A",
            cliente="B",
            valore_causa=5000.0,
            fasi=["inesistente"],
        )
        assert "errore" in r

    def test_cpa_e_iva_incluse(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="precetto",
            avvocato="A",
            cliente="B",
            valore_causa=5000.0,
        )
        d = r["dettaglio_calcoli"]
        assert d["cpa_4pct"] > 0
        assert d["iva_22pct"] > 0

    def test_fasi_custom(self):
        r = _call(
            "modello_notula",
            tipo_procedimento="esecuzione_mobiliare",
            avvocato="A",
            cliente="B",
            valore_causa=5000.0,
            fasi=["studio"],
        )
        assert len(r["dettaglio_calcoli"]["fasi"]) == 1


# ---------------------------------------------------------------------------
# calcolo_notula_penale
# ---------------------------------------------------------------------------

class TestCalcoloNotulaPenale:

    def test_tribunale_monocratico(self):
        r = _call("calcolo_notula_penale", competenza="tribunale_monocratico")
        assert r["competenza"] == "tribunale_monocratico"
        assert r["totale"] > r["totale_compensi"]
        assert r["cpa_4pct"] > 0
        assert r["iva_22pct"] > 0

    def test_spese_generali_incluse(self):
        r_con = _call("calcolo_notula_penale", competenza="giudice_pace", spese_generali=True)
        r_senza = _call("calcolo_notula_penale", competenza="giudice_pace", spese_generali=False)
        assert r_con["spese_generali_15pct"] == pytest.approx(
            round(r_con["totale_compensi"] * 0.15, 2), abs=0.01
        )
        assert r_senza["spese_generali_15pct"] == 0.0
        assert r_con["totale"] > r_senza["totale"]

    def test_cassazione_no_istruttoria(self):
        r = _call("calcolo_notula_penale", competenza="cassazione")
        fasi_nomi = [f["fase"] for f in r["fasi"]]
        assert "istruttoria" not in fasi_nomi

    def test_calcoli_corretti(self):
        r = _call("calcolo_notula_penale", competenza="giudice_pace", livello="medio")
        tc = r["totale_compensi"]
        sg = round(tc * 0.15, 2)
        sub = round(tc + sg, 2)
        cpa = round(sub * 0.04, 2)
        imp_iva = round(sub + cpa, 2)
        iva = round(imp_iva * 0.22, 2)
        assert r["spese_generali_15pct"] == pytest.approx(sg, abs=0.01)
        assert r["cpa_4pct"] == pytest.approx(cpa, abs=0.01)
        assert r["iva_22pct"] == pytest.approx(iva, abs=0.01)
        assert r["totale"] == pytest.approx(round(imp_iva + iva, 2), abs=0.01)

    def test_competenza_invalida(self):
        r = _call("calcolo_notula_penale", competenza="giudice_tributario")
        assert "errore" in r

    def test_livello_invalido(self):
        r = _call("calcolo_notula_penale", competenza="giudice_pace", livello="sbagliato")
        assert "errore" in r

    def test_fasi_parziali(self):
        r = _call("calcolo_notula_penale", competenza="tribunale_monocratico", fasi=["studio"])
        assert len(r["fasi"]) == 1

    def test_fase_invalida(self):
        r = _call("calcolo_notula_penale", competenza="giudice_pace", fasi=["inesistente"])
        assert "errore" in r

    def test_riferimento_normativo(self):
        r = _call("calcolo_notula_penale", competenza="corte_assise")
        assert "DM 55/2014" in r["riferimento_normativo"]
