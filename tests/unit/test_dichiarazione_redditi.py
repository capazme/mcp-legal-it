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
        # Art. 13 co. 5 lett. b) TUIR (autonomo): 500 + 765 x (8.000/22.500 = 0,3555)
        # = 771,96; the tool used to return zero for this type.
        assert r["detrazioni"]["lavoro"] == pytest.approx(771.96, abs=0.001)

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

    def test_dipendente_30000_maggiorazione_65_e_quoziente_troncato(self):
        # Art. 13 co. 1 lett. c) TUIR: 1.910 x (20.000/22.000 = 0,909090 -> 0,9090) = 1.736,19,
        # plus 65 euro (co. 1.1, income above 25.000 and up to 35.000) = 1.801,19.
        # Gross tax 2026: 28.000 x 23% + 2.000 x 33% = 7.100; net 5.298,81.
        r = _call("calcolo_irpef", reddito_complessivo=30000, tipo_reddito="dipendente",
                  anno_fiscale=2026)
        assert r["detrazioni"]["lavoro"] == pytest.approx(1801.19, abs=0.001)
        assert r["imposta_netta"] == pytest.approx(5298.81, abs=0.001)

    def test_dipendente_28000_maggiorazione_65(self):
        # Art. 13 co. 1 lett. c) TUIR at 28.000: 1.910 x 1 = 1.910, plus 65 (co. 1.1) = 1.975.
        r = _call("calcolo_irpef", reddito_complessivo=28000, tipo_reddito="dipendente",
                  anno_fiscale=2025)
        assert r["detrazioni"]["lavoro"] == pytest.approx(1975.00, abs=0.001)

    def test_pensionato_27000_maggiorazione_50(self):
        # Art. 13 co. 3 lett. b) TUIR: 700 + 1.255 x (1.000/19.500 = 0,0512) = 764,26,
        # plus 50 euro (co. 3-bis, income above 25.000 and up to 29.000) = 814,26.
        r = _call("calcolo_irpef", reddito_complessivo=27000, tipo_reddito="pensionato",
                  anno_fiscale=2026)
        assert r["detrazioni"]["lavoro"] == pytest.approx(814.26, abs=0.001)

    def test_autonomo_30000_detrazione_comma_5(self):
        # Art. 13 co. 5 lett. b-bis) TUIR: 500 x (20.000/22.000 -> 0,9090) = 454,50.
        r = _call("calcolo_irpef", reddito_complessivo=30000, tipo_reddito="autonomo",
                  anno_fiscale=2026)
        assert r["detrazioni"]["lavoro"] == pytest.approx(454.50, abs=0.001)
        assert r["imposta_netta"] == pytest.approx(6645.50, abs=0.001)

    def test_autonomo_comma_5_ter_maggiorazione_50(self):
        # Art. 13 co. 5 lett. b) + co. 5-ter TUIR at 15.000: 500 + 765 x (13.000/22.500 =
        # 0,5777) = 941,9405, plus 50 euro (income above 11.000 and up to 17.000) = 991,94.
        r = _call("calcolo_irpef", reddito_complessivo=15000, tipo_reddito="autonomo",
                  anno_fiscale=2025)
        assert r["detrazioni"]["lavoro"] == pytest.approx(991.94, abs=0.001)

    def test_autonomo_50000_nessuna_detrazione(self):
        # Art. 13 co. 5 lett. b-bis) TUIR: (50.000 - 50.000)/22.000 = 0.
        r = _call("calcolo_irpef", reddito_complessivo=50000, tipo_reddito="autonomo",
                  anno_fiscale=2025)
        assert r["detrazioni"]["lavoro"] == 0.0

    def test_detrazione_sul_reddito_complessivo_non_sull_imponibile(self):
        # Art. 13 co. 1 and 6-bis TUIR: the deduction is computed on the total income
        # (30.000), not on income net of deductible charges (28.000): 1.801,19, not 1.975.
        r = _call("calcolo_irpef", reddito_complessivo=30000, tipo_reddito="dipendente",
                  deduzioni=2000, anno_fiscale=2026)
        assert r["reddito_imponibile"] == 28000
        assert r["imposta_lorda"] == pytest.approx(6440.0, abs=0.001)
        assert r["detrazioni"]["lavoro"] == pytest.approx(1801.19, abs=0.001)
        assert r["imposta_netta"] == pytest.approx(4638.81, abs=0.001)

    def test_anno_anteriore_al_2024_rifiutato(self):
        # Art. 11 TUIR before 2024 had four brackets (23-25-35-43%): applying the 2026
        # brackets silently would be wrong, so the tool refuses.
        r = _call("calcolo_irpef", reddito_complessivo=30000, tipo_reddito="autonomo",
                  anno_fiscale=2023)
        assert "errore" in r


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

    def test_imposta_sostitutiva_and_revalued_amounts_out_of_taxable_base(self):
        # Hand check, 2 years 2019-2020, quota 13.500/13,5 = 1.000, no FOI increase.
        # Art. 2120 c. 4 c.c.: revaluation 1,5% of 1.000 = 15,00 at 31/12/2020.
        # Art. 11 c. 3 D.Lgs. 47/2000: 17% (revaluations from 2015) = 2,55 withheld from the fund.
        # Art. 19 c. 1 TUIR: taxable = fund 2.012,45 - revaluation 15,00 = 1.997,45;
        # reference income 1.997,45 x 12 / 2 = 11.984,70 -> average rate 23% (2020 first bracket);
        # tax 1.997,45 x 23% = 459,41 (previous code taxed the gross 2.015,00 and the revaluation twice).
        r = _call("calcolo_tfr", retribuzione_annua_lorda=13500, anni_servizio=2,
                  rivalutazione_media_pct=0, anno_cessazione=2020, imponibile_previdenziale=0)
        assert r["tfr_lordo"] == pytest.approx(2015.00, abs=0.01)
        assert r["imposta_sostitutiva_rivalutazioni"] == pytest.approx(2.55, abs=0.01)
        assert r["tfr_al_netto_imposta_sostitutiva"] == pytest.approx(2012.45, abs=0.01)
        assert r["imponibile"] == pytest.approx(1997.45, abs=0.01)
        assert r["tassazione_separata"]["reddito_riferimento"] == pytest.approx(11984.70, abs=0.01)
        assert r["tassazione_separata"]["aliquota_media_pct"] == pytest.approx(23.0, abs=0.01)
        assert r["tassazione_separata"]["imposta"] == pytest.approx(459.41, abs=0.01)
        assert r["tfr_netto"] == pytest.approx(1553.04, abs=0.01)

    def test_negative_foi_does_not_reduce_revaluation(self):
        # Art. 2120 c. 4 c.c.: 75% of the INCREASE of the index; a falling index leaves the fixed 1,5%.
        r = _call("calcolo_tfr", retribuzione_annua_lorda=13500, anni_servizio=2,
                  rivalutazione_media_pct=-0.1951219512195, anno_cessazione=2020,
                  imponibile_previdenziale=0)
        assert r["tasso_rivalutazione_pct"] == pytest.approx(1.5, abs=0.001)
        assert r["rivalutazioni_lorde"] == pytest.approx(15.00, abs=0.01)

    def test_contributo_aggiuntivo_0_50_pct_deducted_from_quota(self):
        # Art. 3 L. 297/1982 (0,30% + 0,20% of the taxable pay, deducted from the TFR quota):
        # 27.000 x 0,5% = 135,00 -> fund 2.000 - 135 = 1.865; RR 22.380 -> 23%; tax 1.865 x 23% = 428,95.
        r = _call("calcolo_tfr", retribuzione_annua_lorda=27000, anni_servizio=1, anno_cessazione=2025)
        assert r["contributo_aggiuntivo_annuo"] == pytest.approx(135.00, abs=0.01)
        assert r["tfr_lordo"] == pytest.approx(1865.00, abs=0.01)
        assert r["tassazione_separata"]["reddito_riferimento"] == pytest.approx(22380.00, abs=0.01)
        assert r["tassazione_separata"]["imposta"] == pytest.approx(428.95, abs=0.01)
        assert r["tfr_netto"] == pytest.approx(1436.05, abs=0.01)

    def test_brackets_follow_year_of_cessation(self):
        # Art. 19 c. 1 TUIR: rate of the year in which the right accrued.
        # RR 36.000: 2025 (23/35/43) tax 6.440 + 8.000 x 35% = 9.240 -> 25,67%;
        # 2026 (L. 199/2025, second bracket 33%) 6.440 + 8.000 x 33% = 9.080 -> 25,22%.
        r25 = _call("calcolo_tfr", retribuzione_annua_lorda=40500, anni_servizio=1,
                    anno_cessazione=2025, imponibile_previdenziale=0)
        r26 = _call("calcolo_tfr", retribuzione_annua_lorda=40500, anni_servizio=1,
                    anno_cessazione=2026, imponibile_previdenziale=0)
        assert r25["tassazione_separata"]["aliquota_media_pct"] == pytest.approx(25.67, abs=0.01)
        assert r26["tassazione_separata"]["aliquota_media_pct"] == pytest.approx(25.22, abs=0.01)

    def test_detrazione_tempo_determinato_art_19_c_1_ter(self):
        # Art. 19 c. 1-ter TUIR: fixed-term contract up to two years, lire 120.000 (61,97 euro) per year.
        # 27.000, 1 year, RR 24.000 -> 23% -> 460,00 - 61,97 = 398,03.
        base = _call("calcolo_tfr", retribuzione_annua_lorda=27000, anni_servizio=1,
                     anno_cessazione=2025, imponibile_previdenziale=0)
        td = _call("calcolo_tfr", retribuzione_annua_lorda=27000, anni_servizio=1,
                   anno_cessazione=2025, imponibile_previdenziale=0, tempo_determinato=True)
        assert base["tassazione_separata"]["imposta"] == pytest.approx(460.00, abs=0.01)
        assert td["tassazione_separata"]["imposta"] == pytest.approx(398.03, abs=0.01)
        # not available beyond two years
        long = _call("calcolo_tfr", retribuzione_annua_lorda=27000, anni_servizio=3,
                     anno_cessazione=2025, imponibile_previdenziale=0, tempo_determinato=True)
        assert long["tassazione_separata"]["detrazione_tempo_determinato"] == 0


# ---------------------------------------------------------------------------
# ravvedimento_operoso
# ---------------------------------------------------------------------------

class TestRavvedimentoOperoso:

    def test_sprint_14_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=7,
                  tipo="omesso_versamento")
        # art. 13, c. 1, D.Lgs. 471/1997: sprint applies up to 15 days included
        assert r["tipo_ravvedimento"] == "sprint (entro 15 giorni)"
        assert r["sanzione"] < 1000

    def test_breve_30_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=20)
        assert r["tipo_ravvedimento"] == "breve (16-30 giorni)"

    def test_intermedio_90_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=60)
        assert r["tipo_ravvedimento"] == "intermedio (31-90 giorni)"

    def test_lungo_365_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=180)
        assert r["tipo_ravvedimento"] == "lungo (91 giorni - 1 anno)"

    def test_biennale_730_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=500)
        # art. 13, c. 1, lett. b-bis) D.Lgs. 472/1997 (mod. D.Lgs. 87/2024): 1/7, no upper limit
        assert r["tipo_ravvedimento"].startswith("oltre il termine")
        assert r["sanzione"] == pytest.approx(35.71, abs=0.001)

    def test_ultrannuale_oltre_730_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=800)
        # b-ter) (1/6) needs the communication of the "schema d'atto": not 1/6 by days alone
        assert r["tipo_ravvedimento"].startswith("oltre il termine")
        assert r["sanzione"] == pytest.approx(35.71, abs=0.001)

    def test_sprint_exact_amount_art13(self):
        # 1000 x 25% / 2 / 15 x 5 / 10 = 4,1667 -> 4,17; interest 1000 x 1,6% x 5/365 = 0,22
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=5,
                  data_scadenza="2026-03-16")
        assert r["sanzione"] == pytest.approx(4.17, abs=0.001)
        assert r["interessi_legali"]["importo"] == pytest.approx(0.22, abs=0.001)

    def test_single_rounding_of_amount(self):
        # art. 13, c. 1, D.Lgs. 471/1997 + lett. a-bis) 472/1997: 100.000 x 12,5% / 9 = 1.388,888..
        # -> 1.388,89 (the percentage must not be rounded before applying it)
        r = _call("ravvedimento_operoso", imposta_dovuta=100000, giorni_ritardo=60,
                  data_scadenza="2026-03-16")
        assert r["sanzione"] == pytest.approx(1388.89, abs=0.001)

    def test_lett_b_threshold_is_dichiarazione_deadline(self):
        # Violation 16/09/2024: dichiarazione relativa al 2024 due 31/10/2025 (art. 2 D.P.R.
        # 322/1998). 410 days -> paid 31/10/2025 -> lett. b) 1/8 x 25% = 31,25;
        # 411 days -> 01/11/2025 -> lett. b-bis) 1/7 x 25% = 35,71.
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=410,
                  data_scadenza="2024-09-16")
        assert r["sanzione"] == pytest.approx(31.25, abs=0.001)
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=411,
                  data_scadenza="2024-09-16")
        assert r["sanzione"] == pytest.approx(35.71, abs=0.001)

    def test_interest_uses_rate_of_each_year(self):
        # art. 13, c. 2, D.Lgs. 472/1997: legal rate day by day. 16/12/2025 -> 15/01/2026:
        # 15 days at 2% (0,82) + 15 days at 1,6% (0,66) = 1,48 (divisor 365)
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=30,
                  data_scadenza="2025-12-16")
        assert r["interessi_legali"]["importo"] == pytest.approx(1.48, abs=0.001)
        # 16/09/2024 -> 17/09/2026: 106 d at 2,5% + 365 d at 2% + 260 d at 1,6% (2026 up to 17/09)
        # (7,26 + 20,00 + 11,40 = 38,66)
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=731,
                  data_scadenza="2024-09-16")
        assert r["interessi_legali"]["importo"] == pytest.approx(38.66, abs=0.011)

    def test_previgente_violation_refused(self):
        # art. 5, c. 1, D.Lgs. 87/2024: 25% applies to violations from 01/09/2024; before, 30%
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=800,
                  data_scadenza="2024-06-17")
        assert "errore" in r

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

    def test_isee_zero_min_importo(self):
        # Art. 4 c. 9 D.Lgs. 230/2021: without ISEE the minimum amounts apply (2026: 58,30)
        r = _call("assegno_unico", isee=0, n_figli=2)
        assert r["importo_base_per_figlio"] == pytest.approx(58.30, abs=0.01)

    def test_genitore_solo_has_no_legal_basis(self):
        # Art. 4 D.Lgs. 230/2021 has no 30% increase for a single parent: the flag changes nothing
        r_no = _call("assegno_unico", isee=10000, n_figli=1, genitore_solo=False)
        r_yes = _call("assegno_unico", isee=10000, n_figli=1, genitore_solo=True)
        assert r_yes["totale_mensile"] == r_no["totale_mensile"]
        assert r_yes["maggiorazione_genitore_solo"] == 0

    def test_figlio_under_1_anno_maggiorazione(self):
        r = _call("assegno_unico", isee=5000, n_figli=1, eta_figli=[0])
        figlio = r["dettaglio_figli"][0]
        assert any(m["tipo"] == "figlio < 1 anno" for m in figlio["maggiorazioni"])
        assert figlio["importo_mensile"] > r["importo_base_per_figlio"]

    def test_tre_figli_1_3_anni_maggiorazione(self):
        r = _call("assegno_unico", isee=5000, n_figli=3, eta_figli=[2, 2, 2])
        for figlio in r["dettaglio_figli"]:
            assert any("1-3 anni" in m["tipo"] for m in figlio["maggiorazioni"])

    def test_under_1_is_50_pct_of_base(self):
        # Art. 4 c. 1: +50% of the (revalued) amount: 203,80 + 101,90 = 305,70
        r = _call("assegno_unico", isee=5000, n_figli=1, eta_figli=[0])
        assert r["totale_mensile"] == pytest.approx(305.70, abs=0.01)

    def test_maggiorazione_figlio_successivo_al_secondo(self):
        # Art. 4 c. 3: third child adds the c. 3 amount (2026 full 99,10): 3 x 203,80 + 99,10 = 710,50
        r = _call("assegno_unico", isee=15000, n_figli=3, eta_figli=[5, 8, 10])
        assert r["totale_mensile"] == pytest.approx(710.50, abs=0.01)

    def test_plus_50_for_1_3_years_only_up_to_isee_threshold(self):
        # Art. 4 c. 1: +50% for children 1-3 in families with three children only up to ISEE 40.000
        # (46.582,71 revalued). Above it: 3 x 58,30 + c. 3 minimum 17,40 = 192,30, no +50%.
        r = _call("assegno_unico", isee=50000, n_figli=3, eta_figli=[2, 5, 8])
        assert r["totale_mensile"] == pytest.approx(192.30, abs=0.01)

    def test_adult_child_up_to_21(self):
        # Art. 4 c. 2: 18-20 years get the c. 2 amount (2026 99,10 -> 29,10), not the minor amount.
        # ISEE 25.000: 99,10 - 70 x (25.000-17.468,51)/(46.582,71-17.468,51) = 80,99. Over 21: nothing.
        r19 = _call("assegno_unico", isee=25000, n_figli=1, eta_figli=[19])
        r25 = _call("assegno_unico", isee=25000, n_figli=1, eta_figli=[25])
        assert r19["totale_mensile"] == pytest.approx(80.99, abs=0.01)
        assert r25["totale_mensile"] == 0

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

    def test_figlio_disabile_stessa_detrazione(self):
        # Art. 12 co. 1 lett. c) TUIR: the 400 euro increase for the disabled child was
        # suppressed by D.Lgs. 230/2021 (from 1 March 2022): 950 euro for every child.
        r_norm = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=1,
                       n_figli_disabili=0)
        r_disab = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=1,
                        n_figli_disabili=1)
        assert r_disab["detrazione_totale"] == r_norm["detrazione_totale"]

    def test_due_figli_reddito_30000_quoziente_troncato(self):
        # Art. 12 co. 1 lett. c) and co. 4 TUIR: threshold 95.000 + 15.000 = 110.000,
        # ratio 80.000/110.000 = 0,727272... truncated to 0,7272;
        # 950 x 2 x 0,7272 = 1.381,68 (not 1.381,82 with the full-precision ratio).
        r = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=2)
        assert r["rapporto"] == 0.7272
        assert r["detrazione_totale"] == pytest.approx(1381.68, abs=0.001)

    def test_figlio_disabile_reddito_40000_950_non_1350(self):
        # Art. 12 co. 1 lett. c) TUIR: 950 x (55.000/95.000 = 0,578947 -> 0,5789) = 549,955,
        # rounded half up to 549,96. The old regime (1.350 x 0,5789 = 781,52) no longer applies.
        r = _call("detrazione_figli", reddito_complessivo=40000, n_figli_over21=1,
                  n_figli_disabili=1)
        assert r["detrazione_totale"] == pytest.approx(549.96, abs=0.001)

    def test_rapporto_tronca_a_zero_sotto_soglia(self):
        # Art. 12 co. 4 TUIR: 1/110.000 = 0,0000090 truncated to 0,0000 -> the deduction
        # does not apply (the full-precision ratio gave 0,02).
        r = _call("detrazione_figli", reddito_complessivo=109999, n_figli_over21=2)
        assert r["detrazione_totale"] == 0.0

    def test_reddito_zero_rapporto_uno_non_compete(self):
        # Art. 12 co. 4 TUIR: "se i rapporti di cui al comma 1, lettere c) e d), sono ...
        # uguali a uno, le detrazioni non competono" (ratio 95.000/95.000 = 1 at zero income).
        r = _call("detrazione_figli", reddito_complessivo=0, n_figli_over21=1)
        assert r["detrazione_totale"] == 0.0

    def test_multiple_figli_proportional(self):
        r1 = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=1)
        r2 = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=2)
        # La soglia reddito sale di 15.000€ per ogni figlio oltre il primo (art. 12 TUIR):
        # con 2 figli il coefficiente è più alto, quindi il totale supera il doppio di 1 figlio.
        assert r2["detrazione_totale"] > r1["detrazione_totale"] * 2

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
        # art. 12 co. 2 TUIR: the 4,000 limit is for children up to 24, never for the spouse
        assert "limite_reddito_coniuge_under24" not in r

    def test_maggiorazioni_lett_b(self):
        # art. 12 co. 1 lett. b) TUIR: +10/+20/+30/+20/+10 on top of the 690 base
        for reddito, atteso in (
            (29000, 690), (29001, 700), (29200, 700), (29201, 710), (30000, 710),
            (34700, 710), (34701, 720), (35000, 720), (35001, 710), (35100, 710),
            (35101, 700), (35200, 700), (35201, 690),
        ):
            r = _call("detrazione_coniuge", reddito_complessivo=reddito)
            assert r["detrazione"] == pytest.approx(atteso, abs=0.005), reddito

    def test_quoziente_troncato_quattro_decimali(self):
        # art. 12 co. 4 TUIR: ratios are cut (not rounded) at the 4th decimal.
        # 10,000/15,000 = 0.6666 -> 800 - 110 x 0.6666 = 726.674
        assert _call("detrazione_coniuge", reddito_complessivo=10000)["detrazione"] == pytest.approx(726.67, abs=0.005)
        # 40,001: (80,000-40,001)/40,000 = 0.9999 -> 690 x 0.9999 = 689.931
        assert _call("detrazione_coniuge", reddito_complessivo=40001)["detrazione"] == pytest.approx(689.93, abs=0.005)
        # 79,999: ratio 0.000025 cut to 0 -> no deduction (co. 4)
        assert _call("detrazione_coniuge", reddito_complessivo=79999)["detrazione"] == 0.0


# ---------------------------------------------------------------------------
# detrazione_altri_familiari
# ---------------------------------------------------------------------------

class TestDetrazioneAltriFamiliari:

    def test_reddito_basso_full_detrazione(self):
        r = _call("detrazione_altri_familiari", reddito_complessivo=10000, n_familiari=1)
        expected = 750 * (80000 - 10000) / 80000
        assert r["detrazione_totale"] == pytest.approx(expected, abs=0.01)

    def test_quoziente_troncato_tre_familiari(self):
        # Art. 12 co. 1 lett. d) and co. 4 TUIR: ratio (80.000 - 26.811)/80.000 = 0,6648625
        # truncated to 0,6648; 750 x 3 x 0,6648 = 1.495,80 (1.495,95 with the full ratio).
        r = _call("detrazione_altri_familiari", reddito_complessivo=26811, n_familiari=3)
        assert r["rapporto"] == 0.6648
        assert r["detrazione_totale"] == pytest.approx(1495.80, abs=0.001)

    def test_un_euro_sotto_soglia_tronca_a_zero(self):
        # Art. 12 co. 4 TUIR: 1/80.000 = 0,0000125 truncated to 0,0000: no deduction.
        r = _call("detrazione_altri_familiari", reddito_complessivo=79999, n_familiari=3)
        assert r["detrazione_totale"] == 0.0

    def test_reddito_zero_rapporto_uno_non_compete(self):
        # Art. 12 co. 4 TUIR: ratio equal to one (zero income) -> deduction does not apply.
        r = _call("detrazione_altri_familiari", reddito_complessivo=0, n_familiari=1)
        assert r["detrazione_totale"] == 0.0

    def test_sopra_soglia_e_float(self):
        r = _call("detrazione_altri_familiari", reddito_complessivo=80001, n_familiari=1)
        assert r["detrazione_totale"] == 0.0
        assert isinstance(r["detrazione_totale"], float)

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

    def test_aumento_65_comma_1_1(self):
        # art. 13 co. 1.1 TUIR: +65 for 25,000 < RC <= 35,000
        # 30,000: q = 20,000/22,000 = 0.9090 -> 1910 x 0.9090 = 1736.19, +65 = 1801.19
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=30000)
        assert r["detrazione_rapportata"] == pytest.approx(1801.19, abs=0.005)
        # 25,000 excluded, 35,001 excluded
        # 25,000: 1910 + 1190 x (3,000/13,000 = 0.2307) = 2184.533 (no +65)
        assert _call("detrazione_lavoro_dipendente", reddito_complessivo=25000)["detrazione_rapportata"] == pytest.approx(2184.53, abs=0.005)
        # 35,001: 1910 x (14,999/22,000 = 0.6817) = 1302.047 (no +65)
        assert _call("detrazione_lavoro_dipendente", reddito_complessivo=35001)["detrazione_rapportata"] == pytest.approx(1302.05, abs=0.005)

    def test_minimo_690_e_1380_tempo_determinato(self):
        # art. 13 co. 1 lett. a) TUIR: 1,955 x 90/365 = 482.05 < minimum 690 (1,380 if fixed term)
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=10000, giorni_lavoro=90)
        assert r["detrazione_rapportata"] == pytest.approx(690.0)
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=10000, giorni_lavoro=90, tempo_determinato=True)
        assert r["detrazione_rapportata"] == pytest.approx(1380.0)
        # above the minimum nothing changes: 1,955 x 200/365 = 1071.23
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=10000, giorni_lavoro=200)
        assert r["detrazione_rapportata"] == pytest.approx(1071.23, abs=0.005)

    def test_quoziente_troncato(self):
        # art. 13 co. 6 TUIR: 25,001 -> 2,999/13,000 = 0.2306 -> 1910 + 1190 x 0.2306 = 2184.414, +65 = 2249.41
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=25001)
        assert r["detrazione_rapportata"] == pytest.approx(2249.41, abs=0.005)


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
        # art. 13 co. 6 TUIR: 10,000/19,500 = 0.5128 (cut at 4 decimals)
        expected_annua = 700 + 1255 * 0.5128
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

    def test_aumento_50_comma_3_bis(self):
        # art. 13 co. 3-bis TUIR: +50 for 25,000 < RC <= 29,000.
        # 27,000: q = 1,000/19,500 = 0.0512 -> 700 + 1,255 x 0.0512 = 764.256, +50 = 814.26
        r = _call("detrazione_pensione", reddito_complessivo=27000)
        assert r["detrazione_rapportata"] == pytest.approx(814.26, abs=0.005)
        # 25,000 excluded (q = 3,000/19,500 = 0.1538 -> 893.02), 29,000 included (q = 21,000/22,000 = 0.9545 -> 668.15 + 50)
        assert _call("detrazione_pensione", reddito_complessivo=25000)["detrazione_rapportata"] == pytest.approx(893.02, abs=0.005)
        assert _call("detrazione_pensione", reddito_complessivo=29000)["detrazione_rapportata"] == pytest.approx(718.15, abs=0.005)
        assert _call("detrazione_pensione", reddito_complessivo=29001)["detrazione_rapportata"] == pytest.approx(668.15, abs=0.005)

    def test_minimo_713(self):
        # art. 13 co. 3 lett. a) TUIR: floor of 713 on the prorated amount (RC <= 8,500)
        # 1,955 x 100/365 = 535.62 -> 713; 1,955 x 133/365 = 712.37 -> 713
        assert _call("detrazione_pensione", reddito_complessivo=8000, giorni=100)["detrazione_rapportata"] == pytest.approx(713.0)
        assert _call("detrazione_pensione", reddito_complessivo=8000, giorni=133)["detrazione_rapportata"] == pytest.approx(713.0)
        # 1,955 x 200/365 = 1071.23 above the floor
        assert _call("detrazione_pensione", reddito_complessivo=8000, giorni=200)["detrazione_rapportata"] == pytest.approx(1071.23, abs=0.005)

    def test_quoziente_troncato(self):
        # art. 13 co. 6 TUIR: 15,000 -> 13,000/19,500 = 0.6666 -> 700 + 1,255 x 0.6666 = 1536.583
        r = _call("detrazione_pensione", reddito_complessivo=15000)
        assert r["detrazione_rapportata"] == pytest.approx(1536.58, abs=0.005)


# ---------------------------------------------------------------------------
# detrazione_assegno_coniuge
# ---------------------------------------------------------------------------

class TestDetrazioneAssegnoConiuge:

    def test_sotto_8500(self):
        # art. 13 co. 5-bis TUIR: same measure as co. 3, 1,955 up to 8,500 (not the co. 5 figure of 1,265)
        for reddito in (4000, 5500, 8500):
            r = _call("detrazione_assegno_coniuge", reddito_complessivo=reddito)
            assert r["fascia"] == "fino a 8.500€"
            assert r["detrazione"] == pytest.approx(1955, abs=0.005)

    def test_fascia_8501_28000(self):
        # co. 3 lett. b) via 5-bis, quotient cut at 4 decimals (co. 6):
        # 12,000 -> 16,000/19,500 = 0.8205 -> 700 + 1,255 x 0.8205 = 1729.73
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=12000)
        assert r["fascia"] == "8.501-28.000€"
        assert r["detrazione"] == pytest.approx(1729.73, abs=0.005)
        # 8,501 -> 19,499/19,500 = 0.9999 -> 700 + 1,255 x 0.9999 = 1954.87
        assert _call("detrazione_assegno_coniuge", reddito_complessivo=8501)["detrazione"] == pytest.approx(1954.87, abs=0.005)
        # 28,000 -> quotient 0 -> 700
        assert _call("detrazione_assegno_coniuge", reddito_complessivo=28000)["detrazione"] == pytest.approx(700, abs=0.005)

    def test_fascia_28001_50000(self):
        # co. 3 lett. c) via 5-bis: 40,000 -> 10,000/22,000 = 0.4545 -> 700 x 0.4545 = 318.15
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=40000)
        assert r["fascia"] == "28.001-50.000€"
        assert r["detrazione"] == pytest.approx(318.15, abs=0.005)

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
        # Art. 16 co. 1-ter TUIR: without the rent, the legal minimum of 991,60 euro
        # ("euro 991,60, ovvero, se superiore, il 20 per cento del canone ... entro 2.000").
        assert r["detrazione"] == pytest.approx(991.60, abs=0.001)

    def test_giovani_under31_canone_6000_venti_per_cento(self):
        # Art. 16 co. 1-ter TUIR: 20% x 6.000 = 1.200 > 991,60 and <= 2.000.
        r = _call("detrazione_canone_locazione", reddito_complessivo=12000,
                  tipo_contratto="giovani_under31", canone_annuo=6000)
        assert r["detrazione"] == pytest.approx(1200.00, abs=0.001)

    def test_giovani_under31_canone_basso_minimo(self):
        # Art. 16 co. 1-ter TUIR: 20% x 4.000 = 800 < 991,60, the minimum applies.
        r = _call("detrazione_canone_locazione", reddito_complessivo=12000,
                  tipo_contratto="giovani_under31", canone_annuo=4000)
        assert r["detrazione"] == pytest.approx(991.60, abs=0.001)

    def test_giovani_under31_canone_alto_tetto_2000(self):
        # Art. 16 co. 1-ter TUIR: 20% x 12.000 = 2.400, capped at 2.000.
        r = _call("detrazione_canone_locazione", reddito_complessivo=12000,
                  tipo_contratto="giovani_under31", canone_annuo=12000)
        assert r["detrazione"] == pytest.approx(2000.00, abs=0.001)

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

    def test_unica_soluzione_boundary_art17_c3(self):
        # art. 17, c. 3, D.P.R. 435/2001: two rates unless the first rate (40%) does not
        # exceed euro 103. 257,51 x 40% = 103,004 -> 103,00 (single payment);
        # 257,52 x 40% = 103,008 -> 103,01 (two rates: 103,01 + 154,51).
        r = _call("acconto_irpef", imposta_anno_precedente=257.51)
        assert "unica_soluzione" in r
        assert r["unica_soluzione"]["importo"] == pytest.approx(257.51, abs=0.001)
        r = _call("acconto_irpef", imposta_anno_precedente=257.52)
        assert "unica_soluzione" not in r
        assert r["primo_acconto"]["importo"] == pytest.approx(103.01, abs=0.001)
        assert r["secondo_acconto"]["importo"] == pytest.approx(154.51, abs=0.001)

    def test_whole_euro_boundaries(self):
        # RN34 is in whole euro: 257 -> 102,80 first rate (single payment);
        # 258 -> 103,20 (two rates), art. 17, c. 3, D.P.R. 435/2001.
        assert "unica_soluzione" in _call("acconto_irpef", imposta_anno_precedente=257.0)
        r = _call("acconto_irpef", imposta_anno_precedente=258.0)
        assert r["primo_acconto"]["importo"] == pytest.approx(103.20, abs=0.001)
        assert r["secondo_acconto"]["importo"] == pytest.approx(154.80, abs=0.001)


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

    def test_unica_soluzione_boundary_art17_c3(self):
        # Same rule as IRPEF (art. 3, c. 4, D.Lgs. 23/2011 -> art. 17, c. 3, D.P.R. 435/2001):
        # 257,51 -> first rate 103,00 (single payment); 257,52 -> 103,01 (two rates).
        assert "unica_soluzione" in _call("acconto_cedolare_secca", imposta_anno_precedente=257.51)
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=257.52)
        assert r["primo_acconto"]["importo"] == pytest.approx(103.01, abs=0.001)
        assert r["secondo_acconto"]["importo"] == pytest.approx(154.51, abs=0.001)


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
        # art. 20, c. 4, D.Lgs. 241/1997: after the first installment, the 16th of each month
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=3,
                  data_prima_rata="2025-06-15")
        assert r["piano_rate"][0]["data_scadenza"] == "2025-06-15"
        assert r["piano_rate"][1]["data_scadenza"] == "2025-07-16"
        assert r["piano_rate"][2]["data_scadenza"] == "2025-08-16"

    def test_interest_on_each_installment_ade_table(self):
        # art. 20, c. 1-2, D.Lgs. 241/1997: interest on each installment from the first one.
        # 3.000 in 3 rates from 30/06/2026, 4%: 1.000 x 0,18% = 1,80; 1.000 x 0,51% = 5,10
        # (0,18 + 0,33 per month, AdE table) -> interest 6,90, total 3.006,90
        r = _call("rateizzazione_imposte", importo_totale=3000.0, n_rate=3,
                  data_prima_rata="2026-06-30")
        assert [x["interessi"] for x in r["piano_rate"]] == [0.0, 1.8, 5.1]
        assert r["totale_interessi"] == pytest.approx(6.90, abs=0.001)
        assert r["totale_versato"] == pytest.approx(3006.90, abs=0.001)

    def test_seven_rates_end_on_16_december(self):
        # art. 20, c. 1: payment completed by 16 December; 7 rates 30/06 ... 16/12/2026
        r = _call("rateizzazione_imposte", importo_totale=7000.0, n_rate=7,
                  data_prima_rata="2026-06-30")
        assert r["piano_rate"][-1]["data_scadenza"] == "2026-12-16"
        assert r["totale_interessi"] == pytest.approx(60.30, abs=0.001)

    def test_july_start_max_6_rates_and_surcharge(self):
        # art. 17, c. 2, D.P.R. 435/2001: +0,40% on the amount (6.000 -> 6.024);
        # art. 20, c. 1: 7 rates from 30/07 would end after 16 December -> refused
        r = _call("rateizzazione_imposte", importo_totale=6000.0, n_rate=6,
                  data_prima_rata="2026-07-30")
        assert r["maggiorazione_0_40"] == pytest.approx(24.00, abs=0.001)
        assert r["piano_rate"][0]["importo_capitale"] == pytest.approx(1004.0, abs=0.001)
        assert r["piano_rate"][-1]["data_scadenza"] == "2026-12-16"
        r = _call("rateizzazione_imposte", importo_totale=6000.0, n_rate=7,
                  data_prima_rata="2026-07-30")
        assert "errore" in r

    def test_rounding_remainder_on_last_installment(self):
        # equal installments (art. 20, c. 1): 1.000 in 3 -> 333,33 + 333,33 + 333,34
        r = _call("rateizzazione_imposte", importo_totale=1000.0, n_rate=3,
                  data_prima_rata="2026-06-30")
        assert [x["importo_capitale"] for x in r["piano_rate"]] == [333.33, 333.33, 333.34]

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

    # Codes below re-read on the AdE tables of 23/09/2026 (erariali e regionali),
    # 27/07/2026 (F24 ELIDE); cedolare secca = art. 3 D.Lgs. 23/2011, forfetario =
    # art. 1 c. 64 L. 190/2014.

    @staticmethod
    def _codes(query):
        import re
        r = _call("cerca_codice_tributo", query=query)
        return re.findall(r"^\| ([0-9A-Z]{4}) \|", r, flags=re.M)

    def test_cedolare_secca_codes_1840_1841_1842(self):
        assert self._codes("cedolare") == ["1840", "1841", "1842"]
        assert "acconto prima rata" in _call("cerca_codice_tributo", query="1840")
        assert "unica soluzione" in _call("cerca_codice_tributo", query="1841")
        assert "saldo" in _call("cerca_codice_tributo", query="1842")

    def test_regime_forfetario_codes_1790_1791_1792_both_spellings(self):
        assert self._codes("forfettario") == ["1790", "1791", "1792"]
        assert self._codes("forfetario") == ["1790", "1791", "1792"]

    def test_1550_1551_1552_are_atti_privati_not_cedolare(self):
        for code in ("1550", "1551", "1552"):
            r = _call("cerca_codice_tributo", query=code)
            assert "Atti privati" in r
            assert "edolare" not in r

    def test_addizionale_comunale_3843_acconto_3844_saldo(self):
        # ris. AdE 368/E del 12/12/2007
        assert "acconto" in _call("cerca_codice_tributo", query="3843")
        assert "saldo" in _call("cerca_codice_tributo", query="3844")

    def test_iva_acconto_6013_mensili_6035_trimestrali(self):
        assert "mensili" in _call("cerca_codice_tributo", query="6013")
        assert "trimestrali" in _call("cerca_codice_tributo", query="6035")

    def test_1668_interessi_pagamento_dilazionato_present(self):
        assert self._codes("1668") == ["1668"]

    def test_1038_suppressed_since_2017_and_merged_in_1040(self):
        # ris. AdE 13/E del 17/3/2016
        # searching "1038" no longer returns a 1038 row: it lands on 1040, whose text names it
        assert self._codes("1038") == ["1040"]
        assert "provvigioni" in _call("cerca_codice_tributo", query="1040")

    def test_no_f24_code_for_civil_contributo_unificato(self):
        # the tool must not invent 1630/1631/1632 as "contributo unificato" codes:
        # only the administrative-justice GA01-GA05 (F24 ELIDE) exist
        assert self._codes("contributo unificato") == ["GA01", "GA02", "GA03", "GA04", "GA05"]
        assert "Nessun codice tributo trovato" in _call("cerca_codice_tributo", query="1632")
