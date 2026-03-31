"""Comprehensive unit tests for src/tools/dichiarazione_redditi.py."""

import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


# ---------------------------------------------------------------------------
# calcolo_irpef
# ---------------------------------------------------------------------------

class TestCalcoloIrpef:

    def test_autonomo_first_bracket(self):
        r = _call("calcolo_irpef", reddito_complessivo=20000, tipo_reddito="autonomo")
        assert r["imposta_lorda"] == pytest.approx(4600.0, abs=1.0)
        assert r["detrazioni"]["lavoro"] == 0

    def test_dipendente_has_detrazioni_lavoro(self):
        r = _call("calcolo_irpef", reddito_complessivo=25000, tipo_reddito="dipendente")
        assert r["detrazioni"]["lavoro"] > 0
        assert r["imposta_netta"] < r["imposta_lorda"]

    def test_pensionato_has_detrazioni_pensione(self):
        r = _call("calcolo_irpef", reddito_complessivo=15000, tipo_reddito="pensionato")
        assert r["detrazioni"]["lavoro"] > 0

    def test_deduzioni_reduce_imponibile(self):
        r_no = _call("calcolo_irpef", reddito_complessivo=30000, deduzioni=0)
        r_yes = _call("calcolo_irpef", reddito_complessivo=30000, deduzioni=5000)
        assert r_yes["reddito_imponibile"] == 25000
        assert r_yes["imposta_lorda"] < r_no["imposta_lorda"]

    def test_detrazioni_extra_reduce_net(self):
        r = _call("calcolo_irpef", reddito_complessivo=30000, tipo_reddito="autonomo", detrazioni_extra=500)
        assert r["detrazioni"]["extra"] == 500

    def test_addizionali_positive(self):
        r = _call("calcolo_irpef", reddito_complessivo=40000)
        assert r["addizionali"]["regionale"] > 0
        assert r["addizionali"]["comunale"] > 0
        assert r["addizionali"]["totale"] > 0

    def test_reddito_netto_equals_reddito_minus_imposte(self):
        r = _call("calcolo_irpef", reddito_complessivo=50000, tipo_reddito="autonomo")
        assert r["reddito_netto"] == pytest.approx(
            r["reddito_complessivo"] - r["totale_imposte"], abs=0.01
        )

    def test_aliquota_effettiva_positive(self):
        r = _call("calcolo_irpef", reddito_complessivo=35000)
        assert 0 < r["aliquota_effettiva_pct"] < 100

    def test_returns_required_keys(self):
        r = _call("calcolo_irpef", reddito_complessivo=30000)
        for key in ("imposta_lorda", "imposta_netta", "totale_imposte", "reddito_netto",
                    "dettaglio_scaglioni", "detrazioni", "addizionali"):
            assert key in r

    def test_negative_income_error(self):
        r = _call("calcolo_irpef", reddito_complessivo=-1000)
        assert "errore" in r

    def test_zero_income_error(self):
        r = _call("calcolo_irpef", reddito_complessivo=0)
        assert "errore" in r

    def test_high_income_dipendente_zero_detrazione(self):
        r = _call("calcolo_irpef", reddito_complessivo=55000, tipo_reddito="dipendente")
        assert r["detrazioni"]["lavoro"] == 0.0


# ---------------------------------------------------------------------------
# regime_forfettario
# ---------------------------------------------------------------------------

class TestRegimeForfettario:

    def test_startup_aliquota_5pct(self):
        r = _call("regime_forfettario", ricavi=50000, coefficiente_redditivita=78, anni_attivita=3)
        assert r["aliquota_pct"] == 5
        assert r["tipo_aliquota"] == "startup (primi 5 anni)"
        assert r["imposta_sostitutiva"] == pytest.approx(50000 * 0.78 * 0.05, abs=1.0)

    def test_ordinario_aliquota_15pct(self):
        r = _call("regime_forfettario", ricavi=50000, coefficiente_redditivita=78, anni_attivita=6)
        assert r["aliquota_pct"] == 15
        assert r["tipo_aliquota"] == "ordinaria"

    def test_contributi_inps_deducibili(self):
        r = _call("regime_forfettario", ricavi=40000, coefficiente_redditivita=78,
                  anni_attivita=6, contributi_inps=3000)
        reddito_lordo = 40000 * 0.78
        assert r["reddito_imponibile"] == pytest.approx(reddito_lordo - 3000, abs=0.01)

    def test_contributi_inps_non_negative_imponibile(self):
        r = _call("regime_forfettario", ricavi=10000, coefficiente_redditivita=78,
                  anni_attivita=1, contributi_inps=20000)
        assert r["reddito_imponibile"] == 0.0

    def test_confronto_ordinario_present(self):
        r = _call("regime_forfettario", ricavi=40000)
        assert "confronto_ordinario" in r
        assert "risparmio_forfettario" in r["confronto_ordinario"]

    def test_ricavi_exceed_limit_error(self):
        r = _call("regime_forfettario", ricavi=90000)
        assert "errore" in r
        assert "85.000" in r["errore"] or "85000" in str(r["errore"])

    def test_reddito_netto_calculation(self):
        r = _call("regime_forfettario", ricavi=30000, coefficiente_redditivita=78,
                  anni_attivita=10, contributi_inps=1000)
        expected = 30000 - 1000 - r["imposta_sostitutiva"]
        assert r["reddito_netto"] == pytest.approx(expected, abs=0.01)

    def test_returns_required_keys(self):
        r = _call("regime_forfettario", ricavi=40000)
        for key in ("ricavi", "reddito_imponibile", "aliquota_pct", "imposta_sostitutiva",
                    "reddito_netto", "confronto_ordinario"):
            assert key in r


# ---------------------------------------------------------------------------
# calcolo_tfr
# ---------------------------------------------------------------------------

class TestCalcoloTfr:

    def test_basic_accantonamento(self):
        r = _call("calcolo_tfr", retribuzione_annua_lorda=30000, anni_servizio=5)
        assert r["accantonamento_annuo"] == pytest.approx(30000 / 13.5, abs=0.01)

    def test_tfr_lordo_grows_with_years(self):
        r5 = _call("calcolo_tfr", retribuzione_annua_lorda=30000, anni_servizio=5)
        r10 = _call("calcolo_tfr", retribuzione_annua_lorda=30000, anni_servizio=10)
        assert r10["tfr_lordo"] > r5["tfr_lordo"]

    def test_tasso_rivalutazione_formula(self):
        r = _call("calcolo_tfr", retribuzione_annua_lorda=30000, anni_servizio=5,
                  rivalutazione_media_pct=2.0)
        assert r["tasso_rivalutazione_pct"] == pytest.approx(1.5 + 0.75 * 2.0, abs=0.01)

    def test_tfr_netto_less_than_lordo(self):
        r = _call("calcolo_tfr", retribuzione_annua_lorda=40000, anni_servizio=10)
        assert r["tfr_netto"] < r["tfr_lordo"]

    def test_tassazione_separata_keys(self):
        r = _call("calcolo_tfr", retribuzione_annua_lorda=35000, anni_servizio=8)
        ts = r["tassazione_separata"]
        for key in ("reddito_riferimento", "aliquota_media_pct", "imposta"):
            assert key in ts

    def test_zero_anni_error(self):
        r = _call("calcolo_tfr", retribuzione_annua_lorda=30000, anni_servizio=0)
        assert "errore" in r

    def test_negative_anni_error(self):
        r = _call("calcolo_tfr", retribuzione_annua_lorda=30000, anni_servizio=-3)
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call("calcolo_tfr", retribuzione_annua_lorda=30000, anni_servizio=5)
        for key in ("tfr_lordo", "tfr_netto", "accantonamento_annuo", "tasso_rivalutazione_pct"):
            assert key in r


# ---------------------------------------------------------------------------
# ravvedimento_operoso
# ---------------------------------------------------------------------------

class TestRavvedimentoOperoso:

    def test_sprint_14_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=7,
                  tipo="omesso_versamento")
        assert r["tipo_ravvedimento"] == "sprint (entro 14 giorni)"
        assert r["sanzione"] < 1000

    def test_breve_30_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=20)
        assert r["tipo_ravvedimento"] == "breve (15-30 giorni)"

    def test_intermedio_90_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=60)
        assert r["tipo_ravvedimento"] == "intermedio (31-90 giorni)"

    def test_lungo_365_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=180)
        assert r["tipo_ravvedimento"] == "lungo (91 giorni - 1 anno)"

    def test_biennale_730_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=500)
        assert r["tipo_ravvedimento"] == "biennale (1-2 anni)"

    def test_ultrannuale_oltre_730_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=800)
        assert r["tipo_ravvedimento"] == "ultrannuale (oltre 2 anni)"

    def test_dichiarazione_tardiva_sanzione_base_120(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=7,
                  tipo="dichiarazione_tardiva")
        assert r["sanzione_base_pct"] == 120

    def test_omesso_versamento_sanzione_base_25(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=7,
                  tipo="omesso_versamento")
        assert r["sanzione_base_pct"] == 25

    def test_totale_dovuto_sum(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=500, giorni_ritardo=30)
        assert r["totale_dovuto"] == pytest.approx(
            r["imposta_dovuta"] + r["sanzione"] + r["interessi_legali"]["importo"], abs=0.01
        )

    def test_interessi_legali_positive(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=100)
        assert r["interessi_legali"]["importo"] > 0
        assert r["interessi_legali"]["tasso_pct"] > 0

    def test_zero_giorni_error(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=0)
        assert "errore" in r

    def test_negative_giorni_error(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=-5)
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=30)
        for key in ("sanzione", "totale_dovuto", "tipo_ravvedimento", "sanzione_ridotta_pct"):
            assert key in r


# ---------------------------------------------------------------------------
# assegno_unico
# ---------------------------------------------------------------------------

class TestAssegnoUnico:

    def test_isee_basso_max_importo(self):
        r = _call("assegno_unico", isee=5000, n_figli=1)
        assert r["importo_base_per_figlio"] == pytest.approx(203.80, abs=0.01)

    def test_isee_alto_min_importo(self):
        r = _call("assegno_unico", isee=50000, n_figli=1)
        assert r["importo_base_per_figlio"] == pytest.approx(58.30, abs=0.01)

    def test_isee_zero_max_importo(self):
        r = _call("assegno_unico", isee=0, n_figli=2)
        assert r["importo_base_per_figlio"] == pytest.approx(203.80, abs=0.01)

    def test_genitore_solo_maggiorazione_30pct(self):
        r_no = _call("assegno_unico", isee=10000, n_figli=1, genitore_solo=False)
        r_yes = _call("assegno_unico", isee=10000, n_figli=1, genitore_solo=True)
        assert r_yes["totale_mensile"] == pytest.approx(r_no["totale_mensile"] * 1.30, abs=0.05)
        assert r_yes["maggiorazione_genitore_solo"] > 0

    def test_figlio_under_1_anno_maggiorazione(self):
        r = _call("assegno_unico", isee=5000, n_figli=1, eta_figli=[0])
        figlio = r["dettaglio_figli"][0]
        assert any(m["tipo"] == "figlio < 1 anno" for m in figlio["maggiorazioni"])
        assert figlio["importo_mensile"] > r["importo_base_per_figlio"]

    def test_tre_figli_1_3_anni_maggiorazione(self):
        r = _call("assegno_unico", isee=5000, n_figli=3, eta_figli=[2, 2, 2])
        for figlio in r["dettaglio_figli"]:
            assert any("1-3 anni" in m["tipo"] for m in figlio["maggiorazioni"])

    def test_totale_annuo_equals_mensile_x12(self):
        r = _call("assegno_unico", isee=20000, n_figli=2)
        assert r["totale_annuo"] == pytest.approx(r["totale_mensile"] * 12, abs=0.01)

    def test_multiple_figli_sum(self):
        r1 = _call("assegno_unico", isee=15000, n_figli=1)
        r2 = _call("assegno_unico", isee=15000, n_figli=2)
        assert r2["totale_mensile"] > r1["totale_mensile"]

    def test_zero_figli_error(self):
        r = _call("assegno_unico", isee=10000, n_figli=0)
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call("assegno_unico", isee=10000, n_figli=2)
        for key in ("importo_base_per_figlio", "totale_mensile", "totale_annuo", "dettaglio_figli"):
            assert key in r


# ---------------------------------------------------------------------------
# detrazione_figli
# ---------------------------------------------------------------------------

class TestDetrazioneFigli:

    def test_reddito_basso_detrazione_piena(self):
        r = _call("detrazione_figli", reddito_complessivo=20000, n_figli_over21=1)
        assert r["detrazione_totale"] > 0

    def test_reddito_oltre_95000_zero_detrazione(self):
        r = _call("detrazione_figli", reddito_complessivo=100000, n_figli_over21=1)
        assert r["detrazione_totale"] == 0.0

    def test_figlio_disabile_maggiore_detrazione(self):
        r_norm = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=1,
                       n_figli_disabili=0)
        r_disab = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=1,
                        n_figli_disabili=1)
        assert r_disab["detrazione_totale"] > r_norm["detrazione_totale"]

    def test_multiple_figli_proportional(self):
        r1 = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=1)
        r2 = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=2)
        assert r2["detrazione_totale"] == pytest.approx(r1["detrazione_totale"] * 2, abs=0.01)

    def test_zero_figli_error(self):
        r = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=0)
        assert "errore" in r

    def test_disabili_exceed_totale_error(self):
        r = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=1,
                  n_figli_disabili=2)
        assert "errore" in r

    def test_dettaglio_has_correct_items(self):
        r = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=2,
                  n_figli_disabili=1)
        assert len(r["dettaglio"]) == 2
        types = [d["tipo"] for d in r["dettaglio"]]
        assert "ordinario" in types
        assert "disabile" in types


# ---------------------------------------------------------------------------
# detrazione_coniuge
# ---------------------------------------------------------------------------

class TestDetrazioneConiuge:

    def test_fascia_sotto_15000(self):
        r = _call("detrazione_coniuge", reddito_complessivo=10000)
        assert r["fascia"] == "fino a 15.000€"
        assert r["detrazione"] > 0

    def test_fascia_15001_40000(self):
        r = _call("detrazione_coniuge", reddito_complessivo=25000)
        assert r["fascia"] == "15.001-40.000€"
        assert r["detrazione"] == pytest.approx(690, abs=0.01)

    def test_fascia_40001_80000(self):
        r = _call("detrazione_coniuge", reddito_complessivo=60000)
        assert r["fascia"] == "40.001-80.000€"
        assert 0 < r["detrazione"] < 690

    def test_oltre_80000_zero(self):
        r = _call("detrazione_coniuge", reddito_complessivo=90000)
        assert r["fascia"] == "oltre 80.000€"
        assert r["detrazione"] == 0.0

    def test_reddito_zero_error(self):
        r = _call("detrazione_coniuge", reddito_complessivo=0)
        assert "errore" in r

    def test_reddito_negativo_error(self):
        r = _call("detrazione_coniuge", reddito_complessivo=-1000)
        assert "errore" in r

    def test_returns_limite_coniuge(self):
        r = _call("detrazione_coniuge", reddito_complessivo=20000)
        assert r["limite_reddito_coniuge"] == pytest.approx(2840.51)
        assert r["limite_reddito_coniuge_under24"] == 4000


# ---------------------------------------------------------------------------
# detrazione_altri_familiari
# ---------------------------------------------------------------------------

class TestDetrazioneAltriFamiliari:

    def test_reddito_basso_full_detrazione(self):
        r = _call("detrazione_altri_familiari", reddito_complessivo=10000, n_familiari=1)
        expected = 750 * (80000 - 10000) / 80000
        assert r["detrazione_totale"] == pytest.approx(expected, abs=0.01)

    def test_reddito_oltre_80000_zero(self):
        r = _call("detrazione_altri_familiari", reddito_complessivo=90000, n_familiari=2)
        assert r["detrazione_totale"] == 0.0

    def test_multiple_familiari_proportional(self):
        r1 = _call("detrazione_altri_familiari", reddito_complessivo=40000, n_familiari=1)
        r2 = _call("detrazione_altri_familiari", reddito_complessivo=40000, n_familiari=2)
        assert r2["detrazione_totale"] == pytest.approx(r1["detrazione_totale"] * 2, abs=0.01)

    def test_zero_familiari_error(self):
        r = _call("detrazione_altri_familiari", reddito_complessivo=30000, n_familiari=0)
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call("detrazione_altri_familiari", reddito_complessivo=30000, n_familiari=1)
        for key in ("detrazione_unitaria_teorica", "detrazione_per_familiare", "detrazione_totale"):
            assert key in r


# ---------------------------------------------------------------------------
# detrazione_lavoro_dipendente
# ---------------------------------------------------------------------------

class TestDetrazioneLavoroDipendente:

    def test_reddito_sotto_15000_max_detrazione(self):
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=10000)
        assert r["fascia"] == "fino a 15.000€"
        assert r["detrazione_rapportata"] > 0

    def test_fascia_15001_28000(self):
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=20000)
        assert r["fascia"] == "15.001-28.000€"
        assert r["detrazione_rapportata"] > 0

    def test_fascia_28001_50000(self):
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=40000)
        assert r["fascia"] == "28.001-50.000€"
        assert r["detrazione_rapportata"] > 0

    def test_oltre_50000_zero(self):
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=60000)
        assert r["fascia"] == "oltre 50.000€"
        assert r["detrazione_rapportata"] == 0.0

    def test_giorni_parziali_proportional(self):
        r_full = _call("detrazione_lavoro_dipendente", reddito_complessivo=20000, giorni_lavoro=365)
        r_half = _call("detrazione_lavoro_dipendente", reddito_complessivo=20000, giorni_lavoro=182)
        assert r_half["detrazione_rapportata"] < r_full["detrazione_rapportata"]

    def test_giorni_clamped_to_1_365(self):
        r_low = _call("detrazione_lavoro_dipendente", reddito_complessivo=20000, giorni_lavoro=0)
        r_high = _call("detrazione_lavoro_dipendente", reddito_complessivo=20000, giorni_lavoro=500)
        assert r_low["giorni_lavoro"] == 1
        assert r_high["giorni_lavoro"] == 365


# ---------------------------------------------------------------------------
# detrazione_pensione
# ---------------------------------------------------------------------------

class TestDetrazionePensione:

    def test_sotto_8500(self):
        r = _call("detrazione_pensione", reddito_complessivo=7000)
        assert r["fascia"] == "fino a 8.500€"
        assert r["detrazione_rapportata"] == pytest.approx(1955, abs=0.01)

    def test_fascia_8501_28000(self):
        r = _call("detrazione_pensione", reddito_complessivo=18000)
        assert r["fascia"] == "8.501-28.000€"
        expected_annua = 700 + 1255 * (28000 - 18000) / (28000 - 8500)
        assert r["detrazione_annua_piena"] == pytest.approx(expected_annua, abs=0.01)

    def test_fascia_28001_50000(self):
        r = _call("detrazione_pensione", reddito_complessivo=38000)
        assert r["fascia"] == "28.001-50.000€"
        assert 0 < r["detrazione_rapportata"] < 700

    def test_oltre_50000_zero(self):
        r = _call("detrazione_pensione", reddito_complessivo=55000)
        assert r["fascia"] == "oltre 50.000€"
        assert r["detrazione_rapportata"] == 0.0

    def test_giorni_parziali(self):
        r_full = _call("detrazione_pensione", reddito_complessivo=10000, giorni=365)
        r_partial = _call("detrazione_pensione", reddito_complessivo=10000, giorni=180)
        assert r_partial["detrazione_rapportata"] < r_full["detrazione_rapportata"]

    def test_giorni_clamped(self):
        r = _call("detrazione_pensione", reddito_complessivo=10000, giorni=400)
        assert r["giorni"] == 365


# ---------------------------------------------------------------------------
# detrazione_assegno_coniuge
# ---------------------------------------------------------------------------

class TestDetrazioneAssegnoConiuge:

    def test_sotto_5500(self):
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=4000)
        assert r["fascia"] == "fino a 5.500€"
        assert r["detrazione"] == pytest.approx(1265, abs=0.01)

    def test_fascia_5501_28000(self):
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=15000)
        assert r["fascia"] == "5.501-28.000€"
        assert 500 < r["detrazione"] < 1265

    def test_fascia_28001_50000(self):
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=40000)
        assert r["fascia"] == "28.001-50.000€"
        assert 0 < r["detrazione"] < 500

    def test_oltre_50000_zero(self):
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=60000)
        assert r["fascia"] == "oltre 50.000€"
        assert r["detrazione"] == 0.0

    def test_zero_reddito_error(self):
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=0)
        assert "errore" in r

    def test_nota_present(self):
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=10000)
        assert "nota" in r


# ---------------------------------------------------------------------------
# detrazione_canone_locazione
# ---------------------------------------------------------------------------

class TestDetrazioneCanoneLocazione:

    def test_libero_reddito_basso(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=10000,
                  tipo_contratto="libero")
        assert r["detrazione"] == 300

    def test_libero_reddito_medio(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=20000,
                  tipo_contratto="libero")
        assert r["detrazione"] == 150

    def test_libero_reddito_alto_zero(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=40000,
                  tipo_contratto="libero")
        assert r["detrazione"] == 0

    def test_concordato_reddito_basso(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=10000,
                  tipo_contratto="concordato")
        assert r["detrazione"] == pytest.approx(495.80, abs=0.01)

    def test_concordato_reddito_medio(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=20000,
                  tipo_contratto="concordato")
        assert r["detrazione"] == pytest.approx(247.90, abs=0.01)

    def test_giovani_under31_reddito_basso(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=10000,
                  tipo_contratto="giovani_under31")
        assert r["detrazione"] == 2000

    def test_giovani_under31_reddito_alto_zero(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=20000,
                  tipo_contratto="giovani_under31")
        assert r["detrazione"] == 0

    def test_tipo_non_valido_error(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=10000,
                  tipo_contratto="invalido")
        assert "errore" in r

    def test_nota_giovani_only_for_giovani(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=10000,
                  tipo_contratto="giovani_under31")
        assert r["nota_giovani"] is not None
        r2 = _call("detrazione_canone_locazione", reddito_complessivo=10000,
                   tipo_contratto="libero")
        assert r2["nota_giovani"] is None


# ---------------------------------------------------------------------------
# acconto_irpef
# ---------------------------------------------------------------------------

class TestAccontoIrpef:

    def test_no_acconto_sotto_soglia(self):
        r = _call("acconto_irpef", imposta_anno_precedente=50.0)
        assert r["acconto_dovuto"] is False
        assert "51.65" in r["motivo"]

    def test_acconto_dovuto(self):
        r = _call("acconto_irpef", imposta_anno_precedente=1000.0)
        assert r["acconto_dovuto"] is True
        assert r["primo_acconto"]["importo"] == pytest.approx(400.0, abs=0.01)
        assert r["secondo_acconto"]["importo"] == pytest.approx(600.0, abs=0.01)

    def test_acconto_totale_sum(self):
        r = _call("acconto_irpef", imposta_anno_precedente=2500.0)
        assert (r["primo_acconto"]["importo"] + r["secondo_acconto"]["importo"]) == pytest.approx(
            r["acconto_totale"], abs=0.01
        )

    def test_metodo_storico(self):
        r = _call("acconto_irpef", imposta_anno_precedente=1000.0, metodo="storico")
        assert r["metodo"] == "storico"
        assert r["nota_previsionale"] is None

    def test_metodo_previsionale_nota(self):
        r = _call("acconto_irpef", imposta_anno_precedente=1000.0, metodo="previsionale")
        assert r["metodo"] == "previsionale"
        assert r["nota_previsionale"] is not None

    def test_metodo_invalido_error(self):
        r = _call("acconto_irpef", imposta_anno_precedente=1000.0, metodo="invalido")
        assert "errore" in r

    def test_percentuali_40_60(self):
        r = _call("acconto_irpef", imposta_anno_precedente=5000.0)
        assert r["primo_acconto"]["percentuale"] == 40
        assert r["secondo_acconto"]["percentuale"] == 60


# ---------------------------------------------------------------------------
# acconto_cedolare_secca
# ---------------------------------------------------------------------------

class TestAccontoCedolareSecca:

    def test_no_acconto_sotto_soglia(self):
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=30.0)
        assert r["acconto_dovuto"] is False

    def test_acconto_dovuto_split_40_60(self):
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=1000.0)
        assert r["acconto_dovuto"] is True
        assert r["primo_acconto"]["importo"] == pytest.approx(400.0, abs=0.01)
        assert r["secondo_acconto"]["importo"] == pytest.approx(600.0, abs=0.01)

    def test_acconto_totale_sum(self):
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=3000.0)
        assert (r["primo_acconto"]["importo"] + r["secondo_acconto"]["importo"]) == pytest.approx(
            r["acconto_totale"], abs=0.01
        )

    def test_scadenze_present(self):
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=500.0)
        assert "scadenza" in r["primo_acconto"]
        assert "scadenza" in r["secondo_acconto"]

    def test_border_51_65_no_acconto(self):
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=51.65)
        assert r["acconto_dovuto"] is False

    def test_border_51_66_acconto_dovuto(self):
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=51.66)
        assert r["acconto_dovuto"] is True


# ---------------------------------------------------------------------------
# rateizzazione_imposte
# ---------------------------------------------------------------------------

class TestRateizzazioneImposte:

    def test_basic_2_rate(self):
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=2,
                  data_prima_rata="2025-06-30")
        assert len(r["piano_rate"]) == 2
        assert r["piano_rate"][0]["importo_capitale"] == pytest.approx(500.0, abs=0.01)

    def test_7_rate(self):
        r = _call("rateizzazione_imposte", importo_totale=2100.0, n_rate=7,
                  data_prima_rata="2025-06-30")
        assert len(r["piano_rate"]) == 7

    def test_prima_rata_no_interessi(self):
        r = _call("rateizzazione_imposte", importo_totale=1200.0, n_rate=4,
                  data_prima_rata="2025-06-30")
        assert r["piano_rate"][0]["interessi"] == 0.0

    def test_successive_rate_have_interessi(self):
        r = _call("rateizzazione_imposte", importo_totale=1200.0, n_rate=4,
                  data_prima_rata="2025-06-30", tasso_interesse_annuo=2.0)
        for rata in r["piano_rate"][1:]:
            assert rata["interessi"] >= 0

    def test_totale_versato_equals_capitale_plus_interessi(self):
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=4,
                  data_prima_rata="2025-06-30")
        assert r["totale_versato"] == pytest.approx(
            r["importo_totale"] + r["totale_interessi"], abs=0.01
        )

    def test_date_scadenze_present(self):
        # source clamps day to min(day, 28), so 30 → 28
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=3,
                  data_prima_rata="2025-06-15")
        assert r["piano_rate"][0]["data_scadenza"] == "2025-06-15"
        assert r["piano_rate"][1]["data_scadenza"] == "2025-07-15"
        assert r["piano_rate"][2]["data_scadenza"] == "2025-08-15"

    def test_n_rate_1_error(self):
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=1,
                  data_prima_rata="2025-06-30")
        assert "errore" in r

    def test_n_rate_8_error(self):
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=8,
                  data_prima_rata="2025-06-30")
        assert "errore" in r

    def test_importo_zero_error(self):
        r = _call("rateizzazione_imposte", importo_totale=0.0, n_rate=3,
                  data_prima_rata="2025-06-30")
        assert "errore" in r

    def test_data_invalida_error(self):
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=3,
                  data_prima_rata="not-a-date")
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=3,
                  data_prima_rata="2025-06-30")
        for key in ("piano_rate", "totale_interessi", "totale_versato", "n_rate"):
            assert key in r


# ---------------------------------------------------------------------------
# cerca_codice_tributo
# ---------------------------------------------------------------------------

class TestCercaCodiceTributo:

    def test_by_exact_code(self):
        r = _call("cerca_codice_tributo", query="4001")
        assert "4001" in r
        assert "IRPEF" in r
        assert "Saldo" in r

    def test_by_description(self):
        r = _call("cerca_codice_tributo", query="IMU")
        assert "3918" in r
        assert "3912" in r
        assert "IMU" in r

    def test_by_category(self):
        r = _call("cerca_codice_tributo", query="IVA")
        assert "6001" in r
        assert "6099" in r

    def test_case_insensitive(self):
        r_upper = _call("cerca_codice_tributo", query="IRPEF")
        r_lower = _call("cerca_codice_tributo", query="irpef")
        assert r_upper == r_lower

    def test_not_found(self):
        r = _call("cerca_codice_tributo", query="xyz123")
        assert "Nessun codice tributo trovato" in r

    def test_partial_match(self):
        r = _call("cerca_codice_tributo", query="ravvedimento")
        assert "1989" in r
        assert "8901" in r
        assert "8904" in r
        assert "1991" in r
