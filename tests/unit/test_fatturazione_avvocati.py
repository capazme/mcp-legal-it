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

    def test_forfettario_no_iva_no_ritenuta_con_bollo(self):
        r = _call("fattura_avvocato", imponibile=1000.0, regime="forfettario")
        assert r["iva_22pct"] == 0.0
        assert r["ritenuta_acconto_20pct"] == 0.0
        # Fattura senza IVA oltre 77,47 euro: bollo di 2 euro (DPR 642/1972)
        assert r["bollo"] == 2.0
        assert r["totale_fattura"] == pytest.approx(1042.0, abs=0.01)

    def test_forfettario_no_cpa(self):
        r = _call("fattura_avvocato", imponibile=1000.0, regime="forfettario", cpa=False)
        assert r["cpa_4pct"] == 0.0
        assert r["totale_fattura"] == pytest.approx(1002.0, abs=0.01)

    def test_forfettario_sotto_soglia_bollo(self):
        r = _call("fattura_avvocato", imponibile=50.0, regime="forfettario", cpa=False)
        assert r["bollo"] == 0.0
        assert r["totale_fattura"] == pytest.approx(50.0, abs=0.01)

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
        # DM 55/2014 Tab. VIII: the monitorio is paid on a single phase, not on the
        # cognizione phases studio + introduttiva (that was the old, wrong table)
        assert [f["fase"] for f in d["fasi"]] == ["unica"]

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
        # art. 13 co. 1 lett. c DPR 115/2002: 237 for 5.200-26.000, halved for the monitorio (co. 3)
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
        # art. 30 DPR 115/2002: the 27 euro forfait is not due for a precetto
        assert "marca_da_bollo" not in sv and "anticipazione_forfettaria_art_30" not in sv

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


# ---------------------------------------------------------------------------
# modello_notula: each proceeding on its own table of the DM 55/2014 (agg. DM 147/2022)
# ---------------------------------------------------------------------------

def _notula(tipo, valore, livello="medio", fasi=None):
    return _call("modello_notula", tipo_procedimento=tipo, avvocato="A", cliente="B",
                 valore_causa=valore, livello=livello, fasi=fasi)["dettaglio_calcoli"]


class TestModelloNotulaTabelleDedicate:

    def test_decreto_ingiuntivo_tab_viii(self):
        # Tab. VIII (procedimenti monitori), scaglione 5.200,01-26.000: 567 medio, phase unica.
        # Onorari: 567 + 15% sg 85.05 + CPA 4% 26.08 + IVA 22% 149.19 = 827.32 (hand check).
        d = _notula("decreto_ingiuntivo", 10000)
        assert d["totale_compensi"] == 567
        assert d["totale_onorari"] == pytest.approx(827.32, abs=0.01)
        # art. 13 DPR 115/2002 halved for the monitorio (237 / 2 = 118.50) + art. 30 forfait 27
        assert d["spese_vive"]["contributo_unificato_dimezzato"] == 118.5
        assert d["spese_vive"]["anticipazione_forfettaria_art_30"] == 27.0

    def test_decreto_ingiuntivo_max_primo_scaglione(self):
        # Tab. VIII, fino a 5.200: medio 473, max +50% = 709.50, whole euro half up = 710
        assert _notula("decreto_ingiuntivo", 5200, "max")["totale_compensi"] == 710

    def test_precetto_tab_vi_senza_bollo(self):
        # Tab. VI (atto di precetto), fino a 5.200: medio 142, min -50% = 71.
        d = _notula("precetto", 3000, "min")
        assert d["totale_compensi"] == 71
        assert d["totale_onorari"] == pytest.approx(103.60, abs=0.01)
        # art. 30 DPR 115/2002: the 27 euro forfait is due on ricorso / istanza di vendita,
        # a precetto is not a proceeding: no forfait, and no contributo unificato.
        assert "anticipazione_forfettaria_art_30" not in d["spese_vive"]
        assert not any(k.startswith("contributo_unificato") for k in d["spese_vive"])

    def test_esecuzione_mobiliare_tab_xvi(self):
        # Tab. XVI, 1.100,01-5.200: studio 368 + trattazione 184 = 552 medio
        d = _notula("esecuzione_mobiliare", 2000)
        assert [f["fase"] for f in d["fasi"]] == ["studio", "trattazione"]
        assert d["totale_compensi"] == 552
        assert d["totale_onorari"] == pytest.approx(805.43, abs=0.01)

    def test_esecuzione_mobiliare_cu_soglia_2500(self):
        # art. 13 co. 2 DPR 115/2002: 43 euro below 2.500, 139 from 2.500 (half of 278)
        assert _notula("esecuzione_mobiliare", 2499.99)["spese_vive"]["contributo_unificato"] == 43
        assert _notula("esecuzione_mobiliare", 2500)["spese_vive"]["contributo_unificato"] == 139

    def test_esecuzione_presso_terzi_tab_xvii(self):
        # Tab. XVII, 1.100,01-5.200: introduttiva 331 + trattazione e conclusiva 567 = 898 medio
        d = _notula("esecuzione_presso_terzi", 2000)
        assert d["totale_compensi"] == 898
        assert d["totale_onorari"] == pytest.approx(1310.29, abs=0.01)

    def test_esecuzione_immobiliare_tab_xviii(self):
        # Tab. XVIII, 52.000,01-260.000: introduttiva 1.433 + trattazione 982 = 2.415 medio;
        # contributo unificato fisso 278 (art. 13 co. 2 DPR 115/2002)
        d = _notula("esecuzione_immobiliare", 100000)
        assert [f["fase"] for f in d["fasi"]] == ["introduttiva", "trattazione"]
        assert d["totale_compensi"] == 2415
        assert d["totale_onorari"] == pytest.approx(3523.77, abs=0.01)
        assert d["spese_vive"]["contributo_unificato"] == 278

    def test_fasi_della_cognizione_rifiutate(self):
        r = _call("modello_notula", tipo_procedimento="decreto_ingiuntivo", avvocato="A",
                  cliente="B", valore_causa=10000, fasi=["studio", "introduttiva"])
        assert "errore" in r

    def test_oltre_520000_avvertenza(self):
        r = _call("modello_notula", tipo_procedimento="decreto_ingiuntivo", avvocato="A",
                  cliente="B", valore_causa=600000)
        assert r["dettaglio_calcoli"]["totale_compensi"] == 4394  # last row of Tab. VIII
        assert r["avvertenze"]


# ---------------------------------------------------------------------------
# parcella_avvocato_civile above 32 million: art. 6 co. 1 DM 55/2014, last sentence
# ---------------------------------------------------------------------------

class TestParcellaCivileOltre32Milioni:

    def test_primo_raddoppio_oltre_32_milioni(self):
        # Art. 6 co. 1: "tale ultimo criterio puo' essere utilizzato per ogni successivo
        # raddoppio del valore". 32-64 million = +30% on the 16-32 million medium, per phase:
        # 17.107 x 1,3 = 22.239 ; 11.284 x 1,3 = 14.669 ; 50.250 x 1,3 = 65.325 ; 29.753 x 1,3 = 38.679
        r = _call("parcella_avvocato_civile", valore_causa=32_000_000.01)
        assert [f["importo"] for f in r["fasi"]] == [22239, 14669, 65325, 38679]
        assert r["totale_compenso"] == 140912

    def test_secondo_raddoppio(self):
        # 64-128 million: +30% again on the rounded previous medium (22.239 x 1,3 = 28.911, ...)
        r = _call("parcella_avvocato_civile", valore_causa=70_000_000)
        assert [f["importo"] for f in r["fasi"]] == [28911, 19070, 84923, 50283]
        assert r["totale_compenso"] == 183187

    def test_confine_32_milioni_invariato(self):
        # 32.000.000 exactly stays in the closed 16-32 million band (108.394 medio)
        assert _call("parcella_avvocato_civile", valore_causa=32_000_000)["totale_compenso"] == 108394

    def test_raddoppio_esatto_64_milioni_resta_nel_primo(self):
        assert _call("parcella_avvocato_civile", valore_causa=64_000_000)["totale_compenso"] == 140912

    def test_minimo_massimo_oltre_32_milioni(self):
        # min/max = medium -/+ 50% (art. 4 co. 1 as amended by DM 147/2022), rounded
        r_min = _call("parcella_avvocato_civile", valore_causa=40_000_000, livello="min")
        r_max = _call("parcella_avvocato_civile", valore_causa=40_000_000, livello="max")
        assert [f["importo"] for f in r_min["fasi"]] == [11120, 7335, 32663, 19340]
        assert [f["importo"] for f in r_max["fasi"]] == [33359, 22004, 97988, 58019]


# ---------------------------------------------------------------------------
# stragiudiziale above 520.000: art. 22 DM 55/2014, Tab. 25 (percentuale decrescente)
# ---------------------------------------------------------------------------

class TestStragiudizialeOltre520000:

    def test_600000_medio_3_per_cento(self):
        # Art. 22 DM 55/2014 + Tab. 25: 520.000,01-2.000.000 -> 3% of the value:
        # 600.000 x 3% = 18.000 (medio); min -50% = 9.000; max +50% = 27.000 (art. 19 co. 1)
        assert _call("parcella_stragiudiziale", valore_pratica=600000)["compenso"] == 18000
        assert _call("parcella_stragiudiziale", valore_pratica=600000, livello="min")["compenso"] == 9000
        assert _call("parcella_stragiudiziale", valore_pratica=600000, livello="max")["compenso"] == 27000

    def test_3_milioni_fascia_2_75(self):
        # 2.000.000,01-4.000.000 -> 2,75% on the whole value: 3.000.000 x 2,75% = 82.500
        assert _call("parcella_stragiudiziale", valore_pratica=3_000_000)["compenso"] == 82500

    def test_confini_fasce(self):
        # the bracket limit belongs to the lower bracket ("da 520.000,01 a 2.000.000,00")
        assert _call("parcella_stragiudiziale", valore_pratica=2_000_000)["compenso"] == 60000  # 3%
        assert _call("parcella_stragiudiziale", valore_pratica=2_000_000.01)["compenso"] == 55000  # 2,75%

    def test_oltre_22_milioni_0_25_per_cento(self):
        # last bracket: 0,25% -> 30.000.000 x 0,25% = 75.000
        assert _call("parcella_stragiudiziale", valore_pratica=30_000_000)["compenso"] == 75000

    def test_520000_esatti_restano_nello_scaglione_tabellare(self):
        assert _call("parcella_stragiudiziale", valore_pratica=520000)["compenso"] == 6164

    def test_preventivo_oltre_520000(self):
        # 600.000 max: compenso 27.000, sg 15% = 4.050, CPA 4% of 31.050 = 1.242, IVA off
        r = _call("preventivo_stragiudiziale", valore_pratica=600000, livello="max", iva=False)
        d = r["dettaglio_calcoli"]
        assert d["compenso_base"] == 27000
        assert d["spese_generali_15pct"] == 4050
        assert d["cpa_4pct"] == pytest.approx(1242, abs=0.01)
        assert d["percentuale_tab_25"] == 3.0  # Tab. 25, 520.000,01-2.000.000


# Half-cent rounding and art. 27 DM 55/2014 (benchmark phase 3, fatturazione_avvocati)
# ---------------------------------------------------------------------------

class TestArrotondamentoMetaCentesimo:
    """Ties go to the upper cent (art. 5 Reg. CE 1103/97), never depending on the float bits.

    Every expected value is computed by hand on exact decimals.
    """

    def test_fattura_iva_tie_sale(self):
        # 1000.24 + CPA 4% (40.0096 -> 40.01) = 1040.25; IVA 22% = 228.855 exactly -> 228.86
        r = _call("fattura_avvocato", imponibile=1000.24)
        assert r["cpa_4pct"] == 40.01
        assert r["imponibile_iva"] == 1040.25
        assert r["iva_22pct"] == 228.86
        # withholding 20% of 1000.24 = 200.048 -> 200.05; net = 1040.25 + 228.86 - 200.05
        assert r["netto_a_pagare"] == 1069.06

    def test_fattura_iva_tie_gia_corretto_resta(self):
        # 1000.72 + 40.03 = 1040.75; IVA = 228.965 exactly -> 228.97
        r = _call("fattura_avvocato", imponibile=1000.72)
        assert r["iva_22pct"] == 228.97

    def test_nota_spese_sg_tie(self):
        # 15% of 1000.10 = 150.015 exactly -> 150.02; sum 1150.12; CPA 46.0048 -> 46.00;
        # taxable 1196.12; IVA 263.1464 -> 263.15; total 1459.27
        r = _call("nota_spese", voci=[
            {"descrizione": "c", "importo": 1000.1, "tipo": "compenso"},
            {"descrizione": "b", "importo": 1000.1, "tipo": "spese_generali_15pct"},
        ])
        assert r["totale_spese_generali_15pct"] == 150.02
        assert r["imponibile_iva"] == 1196.12
        assert r["iva_22pct"] == 263.15
        assert r["totale_nota_spese"] == 1459.27

    def test_nota_spese_iva_tie(self):
        # 503.61 + CPA 20.1444 -> 20.14 = 523.75; IVA 22% = 115.225 exactly -> 115.23
        r = _call("nota_spese", voci=[{"descrizione": "c", "importo": 503.61, "tipo": "compenso"}])
        assert r["iva_22pct"] == 115.23
        assert r["totale_nota_spese"] == 638.98

    def test_nota_spese_totali_aggregati_al_centesimo(self):
        r = _call("nota_spese", voci=[
            {"descrizione": "a", "importo": 0.1, "tipo": "compenso"},
            {"descrizione": "b", "importo": 0.2, "tipo": "compenso"},
        ])
        assert r["totale_compensi"] == 0.3

    def test_notula_penale_iva_tie(self):
        # DM 147/2022 penale, tribunale monocratico, studio+introduttiva+istruttoria at minimum:
        # 237+284+567 = 1088; SG 163.20; CPA 4% of 1251.20 = 50.048 -> 50.05; taxable 1301.25;
        # IVA 22% = 286.275 exactly -> 286.28; total 1587.53
        r = _call("calcolo_notula_penale", competenza="tribunale_monocratico",
                  fasi=["studio", "introduttiva", "istruttoria"], livello="min")
        assert r["imponibile_iva"] == 1301.25
        assert r["iva_22pct"] == 286.28
        assert r["totale"] == 1587.53


class TestSpeseTrasfertaArt27:

    def test_indennita_chilometrica_un_quinto_carburante(self):
        # art. 27 DM 55/2014: one fifth of the fuel cost per litre per km.
        # 200 km x 1.80 / 5 = 72.00 (0.36 euro/km)
        r = _call("spese_trasferta_avvocati", km_distanza=200.0, ore_assenza=4.0,
                  prezzo_carburante_litro=1.80)
        assert r["rimborso_km"] == 72.0

    def test_indennita_chilometrica_decimali(self):
        # 137.5 km x 1.50 / 5 = 41.25
        r = _call("spese_trasferta_avvocati", km_distanza=137.5, ore_assenza=2.0,
                  prezzo_carburante_litro=1.50)
        assert r["rimborso_km"] == 41.25

    def test_default_senza_prezzo_equivale_a_1_50_litro(self):
        r = _call("spese_trasferta_avvocati", km_distanza=200.0, ore_assenza=4.0)
        assert r["rimborso_km"] == 60.0

    def test_albergo_maggiorato_10_per_cento_e_pedaggi(self):
        # art. 27: documented hotel +10% accessory costs (100 -> 110); tolls and parking at cost.
        r = _call("spese_trasferta_avvocati", km_distanza=0.0, ore_assenza=9.0, mezzo="treno",
                  pernottamento=True, costo_albergo=100.0, pedaggi_parcheggi=12.5)
        assert r["albergo_maggiorato_10pct"] == 110.0
        # allowance 40% of 540 = 216.00; 216 + 110 + 12.50
        assert r["totale_stimato"] == 338.5

    def test_prezzo_negativo(self):
        r = _call("spese_trasferta_avvocati", km_distanza=10.0, ore_assenza=1.0,
                  prezzo_carburante_litro=-1.0)
        assert "errore" in r
