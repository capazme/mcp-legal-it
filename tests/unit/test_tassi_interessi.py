import importlib
import json
from datetime import date
from pathlib import Path

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.tassi_interessi")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# interessi_legali
# ---------------------------------------------------------------------------


class TestInteressiLegali:
    def test_happy_path_semplici(self):
        r = _call(
            "interessi_legali",
            capitale=10000,
            data_inizio="2024-01-01",
            data_fine="2025-01-01",
        )
        assert r["capitale"] == 10000
        assert r["tipo"] == "semplici"
        # 2024 tasso 2.5%, 365 giorni: 10000 * 0.025 * 365/365 ≈ 250
        assert r["totale_interessi"] == pytest.approx(250.0, abs=1.0)
        assert r["montante"] == pytest.approx(10250.0, abs=1.0)
        assert isinstance(r["periodi"], list)
        assert len(r["periodi"]) >= 1

    def test_happy_path_composti(self):
        r = _call(
            "interessi_legali",
            capitale=1000,
            data_inizio="2024-01-01",
            data_fine="2024-12-31",
            tipo="composti",
        )
        assert r["tipo"] == "composti"
        assert r["totale_interessi"] > 0
        assert r["montante"] == pytest.approx(r["capitale"] + r["totale_interessi"], abs=0.01)

    def test_multi_year_splits_periodi(self):
        r = _call(
            "interessi_legali",
            capitale=5000,
            data_inizio="2023-01-01",
            data_fine="2025-01-01",
        )
        # 2023 tasso 5%, 2024 tasso 2.5% → at least 2 periods
        assert len(r["periodi"]) >= 2
        rates = {p["tasso_pct"] for p in r["periodi"]}
        assert 5.0 in rates
        assert 2.5 in rates

    def test_dies_a_quo_not_counted(self):
        r1 = _call(
            "interessi_legali",
            capitale=10000,
            data_inizio="2024-01-01",
            data_fine="2024-01-02",
        )
        # Only 1 day counted (dies a quo not counted → 1 day accrues)
        assert r1["totale_interessi"] == pytest.approx(10000 * 0.025 / 365, abs=0.01)

    def test_equal_dates_error(self):
        r = _call(
            "interessi_legali",
            capitale=1000,
            data_inizio="2024-06-01",
            data_fine="2024-06-01",
        )
        assert "errore" in r

    def test_inverted_dates_error(self):
        r = _call(
            "interessi_legali",
            capitale=1000,
            data_inizio="2024-12-31",
            data_fine="2024-01-01",
        )
        assert "errore" in r

    def test_periodi_fields(self):
        r = _call(
            "interessi_legali",
            capitale=2000,
            data_inizio="2025-01-01",
            data_fine="2025-06-01",
        )
        p = r["periodi"][0]
        for key in ("dal", "al", "giorni", "tasso_pct", "interessi"):
            assert key in p


# ---------------------------------------------------------------------------
# interessi_mora
# ---------------------------------------------------------------------------


class TestInteressiMora:
    def test_happy_path(self):
        r = _call(
            "interessi_mora",
            capitale=5000,
            data_inizio="2024-01-01",
            data_fine="2024-07-01",
        )
        assert r["capitale"] == 5000
        assert r["totale_interessi"] > 0
        assert r["totale_dovuto"] == pytest.approx(r["capitale"] + r["totale_interessi"], abs=0.01)
        assert "D.Lgs. 231/2002" in r["riferimento_normativo"]

    def test_bce_plus_8_rate(self):
        # Jan 2024: BCE=4.50 mora=12.50 — single period within semester
        r = _call(
            "interessi_mora",
            capitale=10000,
            data_inizio="2024-01-01",
            data_fine="2024-01-31",
        )
        assert r["periodi"][0]["tasso_mora_pct"] == 12.50
        assert r["periodi"][0]["tasso_bce_pct"] == 4.50

    def test_period_split_at_semester(self):
        # Spans the Jul 2024 semester boundary: Jan→Jun at 12.50, Jul→Dec at 12.25
        r = _call(
            "interessi_mora",
            capitale=10000,
            data_inizio="2024-01-01",
            data_fine="2024-12-31",
        )
        assert len(r["periodi"]) >= 2

    def test_equal_dates_error(self):
        r = _call(
            "interessi_mora",
            capitale=1000,
            data_inizio="2024-05-01",
            data_fine="2024-05-01",
        )
        assert "errore" in r

    def test_inverted_dates_error(self):
        r = _call(
            "interessi_mora",
            capitale=1000,
            data_inizio="2024-06-01",
            data_fine="2024-01-01",
        )
        assert "errore" in r

    def test_periodi_fields(self):
        r = _call(
            "interessi_mora",
            capitale=3000,
            data_inizio="2025-01-01",
            data_fine="2025-03-01",
        )
        p = r["periodi"][0]
        for key in ("dal", "al", "giorni", "tasso_bce_pct", "tasso_mora_pct", "interessi"):
            assert key in p


class TestInteressiMoraRegime:
    """Spread of the reference rate: art. 5 c.1 D.Lgs. 231/2002 original text (+7) for
    transactions concluded up to 31/12/2012, art. 2 c.1 lett. e) as replaced by D.Lgs. 192/2012
    (+8) afterwards (art. 3 c.1 D.Lgs. 192/2012)."""

    def test_2012_uses_seven_points(self):
        # 2012: BCE 1.00% both semesters, +7 = 8.00%. Days 2012-01-02..2012-12-31 = 365.
        # 10000 * 8% * 365/365 = 800.00 (hand computed)
        r = _call("interessi_mora", capitale=10000, data_inizio="2012-01-01", data_fine="2012-12-31")
        assert r["maggiorazione_punti"] == 7
        assert r["totale_interessi"] == pytest.approx(800.00, abs=0.01)
        assert {p["tasso_mora_pct"] for p in r["periodi"]} == {8.0}

    def test_regime_follows_start_date_across_2013(self):
        # start 31/12/2012 -> pre-2013 transaction, +7 also on 2013 days: BCE 0.75 + 7 = 7.75%
        # 31 days (2013-01-01..2013-01-31): 10000 * 7.75% * 31/365 = 65.82
        r = _call("interessi_mora", capitale=10000, data_inizio="2012-12-31", data_fine="2013-01-31")
        assert r["maggiorazione_punti"] == 7
        assert r["totale_interessi"] == pytest.approx(65.82, abs=0.01)

    def test_2013_start_uses_eight_points(self):
        # 2013: 8.75% for 180 days (2013-01-02..06-30), 8.50% for 184 days:
        # 10000*(0.0875*180 + 0.0850*184)/365 = 860.00
        r = _call("interessi_mora", capitale=10000, data_inizio="2013-01-01", data_fine="2013-12-31")
        assert r["maggiorazione_punti"] == 8
        assert r["totale_interessi"] == pytest.approx(860.00, abs=0.01)

    def test_explicit_pre_2013_contract_with_later_due_date(self):
        # contract concluded before 1/1/2013, due in 2013: old text still applies (art. 3 D.Lgs. 192/2012)
        r = _call(
            "interessi_mora", capitale=10000, data_inizio="2013-01-01", data_fine="2013-01-31",
            contratto_ante_2013=True,
        )
        assert r["periodi"][0]["tasso_mora_pct"] == 7.75

    def test_2003_rates(self):
        # 2003 H1 BCE 2.85 + 7 = 9.85%, H2 2.10 + 7 = 9.10% (D.Lgs. 231/2002 art. 5 original)
        r = _call("interessi_mora", capitale=10000, data_inizio="2003-01-01", data_fine="2003-12-31")
        assert [p["tasso_mora_pct"] for p in r["periodi"]] == [9.85, 9.10]

    def test_beyond_table_warns_instead_of_silent_zero(self):
        r = _call("interessi_mora", capitale=10000, data_inizio="2026-12-31", data_fine="2027-01-31")
        assert r["totale_interessi"] == 0
        assert "avvertenza" in r


# ---------------------------------------------------------------------------
# interessi_tasso_fisso
# ---------------------------------------------------------------------------


class TestInteressiTassoFisso:
    def test_semplici_one_year(self):
        r = _call(
            "interessi_tasso_fisso",
            capitale=10000,
            tasso_annuo=5.0,
            data_inizio="2024-01-01",
            data_fine="2025-01-01",
        )
        # 2024 is leap: giorni=366, anno=366 → 10000 * 0.05 * 366/366 = 500
        assert r["giorni"] == 366
        assert r["interessi"] == pytest.approx(500.0, abs=0.01)
        assert r["montante"] == pytest.approx(10500.0, abs=0.01)
        assert r["tipo"] == "semplici"

    def test_composti_one_year(self):
        r = _call(
            "interessi_tasso_fisso",
            capitale=10000,
            tasso_annuo=10.0,
            data_inizio="2024-01-01",
            data_fine="2025-01-01",
            tipo="composti",
        )
        # 365 giorni / 365 ≈ 1 anno → montante ≈ 11000
        assert r["tipo"] == "composti"
        assert r["montante"] == pytest.approx(11000.0, abs=5.0)

    def test_zero_rate(self):
        r = _call(
            "interessi_tasso_fisso",
            capitale=5000,
            tasso_annuo=0.0,
            data_inizio="2024-01-01",
            data_fine="2024-07-01",
        )
        assert r["interessi"] == 0.0
        assert r["montante"] == 5000.0

    def test_equal_dates_error(self):
        r = _call(
            "interessi_tasso_fisso",
            capitale=1000,
            tasso_annuo=5.0,
            data_inizio="2024-06-01",
            data_fine="2024-06-01",
        )
        assert "errore" in r

    def test_inverted_dates_error(self):
        r = _call(
            "interessi_tasso_fisso",
            capitale=1000,
            tasso_annuo=5.0,
            data_inizio="2024-12-31",
            data_fine="2024-01-01",
        )
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call(
            "interessi_tasso_fisso",
            capitale=2000,
            tasso_annuo=3.0,
            data_inizio="2025-01-01",
            data_fine="2025-07-01",
        )
        for key in ("capitale", "tasso_annuo_pct", "giorni", "tipo", "interessi", "montante"):
            assert key in r


# ---------------------------------------------------------------------------
# calcolo_ammortamento
# ---------------------------------------------------------------------------


class TestCalcoloAmmortamento:
    def test_francese_rata_costante(self):
        r = _call(
            "calcolo_ammortamento",
            capitale=100000,
            tasso_annuo=3.0,
            durata_mesi=240,
            tipo="francese",
        )
        assert r["tipo"] == "francese"
        assert len(r["piano"]) == 240
        # All rates should be equal (French amortization)
        rate_vals = {p["rata"] for p in r["piano"]}
        assert len(rate_vals) <= 2  # last may differ by rounding
        assert r["totale_pagato"] == pytest.approx(r["capitale"] + r["totale_interessi"], abs=1.0)

    def test_italiano_quota_costante(self):
        r = _call(
            "calcolo_ammortamento",
            capitale=60000,
            tasso_annuo=4.0,
            durata_mesi=120,
            tipo="italiano",
        )
        assert r["tipo"] == "italiano"
        assert len(r["piano"]) == 120
        quota_capitale_vals = {p["quota_capitale"] for p in r["piano"]}
        assert len(quota_capitale_vals) == 1  # constant capital quota
        # Rata decreasing: first > last
        assert r["piano"][0]["rata"] > r["piano"][-1]["rata"]

    def test_zero_rate(self):
        r = _call(
            "calcolo_ammortamento",
            capitale=12000,
            tasso_annuo=0.0,
            durata_mesi=12,
        )
        assert r["totale_interessi"] == pytest.approx(0.0, abs=0.01)
        assert r["piano"][0]["rata"] == pytest.approx(1000.0, abs=0.01)

    def test_returns_required_keys(self):
        r = _call(
            "calcolo_ammortamento",
            capitale=50000,
            tasso_annuo=2.5,
            durata_mesi=60,
        )
        for key in ("capitale", "tasso_annuo_pct", "durata_mesi", "rata_iniziale", "totale_interessi", "totale_pagato", "piano"):
            assert key in r

    def test_first_piano_entry_keys(self):
        r = _call(
            "calcolo_ammortamento",
            capitale=10000,
            tasso_annuo=5.0,
            durata_mesi=12,
        )
        p = r["piano"][0]
        for key in ("rata_n", "rata", "quota_capitale", "quota_interessi", "debito_residuo"):
            assert key in p

    def test_last_debito_residuo_zero(self):
        r = _call(
            "calcolo_ammortamento",
            capitale=10000,
            tasso_annuo=5.0,
            durata_mesi=12,
        )
        assert r["piano"][-1]["debito_residuo"] == pytest.approx(0.0, abs=1.0)


# ---------------------------------------------------------------------------
# verifica_usura
# ---------------------------------------------------------------------------


class TestVerificaUsura:
    def test_non_usurario(self):
        # mutuo_prima_casa 2026-Q1: TEGM=3.96, soglia=min(3.96*1.25+4, 3.96+8)=min(8.95, 11.96)=8.95
        r = _call("verifica_usura", tasso_applicato=5.0, tipo_operazione="mutuo_prima_casa")
        assert r["usurario"] is False
        assert r["tasso_applicato_pct"] == 5.0
        assert r["tasso_soglia_pct"] > 5.0

    def test_usurario(self):
        # carte_revolving 2026-Q1: TEGM=15.77, soglia=min(15.77*1.25+4, 15.77+8)=min(23.7125, 23.77)=23.7125
        r = _call("verifica_usura", tasso_applicato=30.0, tipo_operazione="carte_revolving")
        assert r["usurario"] is True
        assert r["margine"] < 0

    def test_prossimo_a_usura(self):
        # credito_personale 2025-Q3: TEGM=11.02, soglia=17.775, 90%=15.9975
        # tasso 16.0 > 90% threshold but < soglia → prossimo_a_usura
        r = _call(
            "verifica_usura",
            tasso_applicato=16.0,
            tipo_operazione="credito_personale",
            trimestre="2025-Q3",
        )
        assert r["usurario"] is False
        assert r["prossimo_a_usura"] is True

    def test_formula_key_present(self):
        r = _call("verifica_usura", tasso_applicato=5.0)
        assert "formula" in r
        assert "TEGM" in r["formula"]

    def test_default_tipo_operazione(self):
        r = _call("verifica_usura", tasso_applicato=10.0)
        # Default falls back to credito_personale when not specified
        assert "tipo_operazione" in r
        assert r["tegm_pct"] > 0

    def test_returns_required_keys(self):
        r = _call("verifica_usura", tasso_applicato=8.0, tipo_operazione="leasing")
        for key in ("tasso_applicato_pct", "tipo_operazione", "tegm_pct", "tasso_soglia_pct", "usurario", "margine", "riferimento_normativo"):
            assert key in r

    def test_explicit_trimestre_q3_2025(self):
        # credito_personale 2025-Q3: TEGM=11.02, soglia=min(11.02*1.25+4, 11.02+8)=min(17.775, 19.02)=17.775
        r = _call(
            "verifica_usura",
            tasso_applicato=10.0,
            tipo_operazione="credito_personale",
            trimestre="2025-Q3",
        )
        assert r["trimestre"] == "2025-Q3"
        assert r["tegm_pct"] == 11.02
        assert r["tasso_soglia_pct"] == pytest.approx(17.775, abs=0.01)
        assert r["usurario"] is False

    def test_different_quarters_yield_different_rates(self):
        r_q1 = _call(
            "verifica_usura",
            tasso_applicato=5.0,
            tipo_operazione="mutuo_prima_casa",
            trimestre="2025-Q1",
        )
        r_q4 = _call(
            "verifica_usura",
            tasso_applicato=5.0,
            tipo_operazione="mutuo_prima_casa",
            trimestre="2025-Q4",
        )
        # Q1 2025: TEGM=3.39, Q4 2025: TEGM=3.58 — different rates
        assert r_q1["tegm_pct"] != r_q4["tegm_pct"]
        assert r_q1["tasso_soglia_pct"] != r_q4["tasso_soglia_pct"]

    def test_leasing_strumentale_2025_q1_matches_mef_decree(self):
        # MEF decree, Allegato A, application 1 Jan - 31 Mar 2025: leasing strumentale
        # up to 25.000 has TEGM 9,75 and soglia 16,1875 (9,75 x 1,25 + 4). The table
        # used to carry 7,44, which is the "oltre 25.000" class (soglia 13,3000).
        r = _call("verifica_usura", tasso_applicato=15.0, tipo_operazione="leasing", trimestre="2025-Q1")
        assert r["tegm_pct"] == 9.75
        assert r["tasso_soglia_decreto_pct"] == 16.1875
        assert r["tasso_soglia_pct"] == 16.19
        assert r["usurario"] is False

    def test_soglia_keeps_four_decimals_of_the_decree(self):
        # Art. 2 c. 4 L. 108/1996: mutuo fisso 2025-Q4 TEGM 3,58 -> 3,58 x 1,25 + 4 = 8,475
        # exactly; the rate 8,48 is above it, 8,47 is below (no binary rounding of the limit).
        alto = _call("verifica_usura", tasso_applicato=8.48, trimestre="2025-Q4")
        basso = _call("verifica_usura", tasso_applicato=8.47, trimestre="2025-Q4")
        assert alto["tasso_soglia_decreto_pct"] == 8.475
        assert alto["tasso_soglia_pct"] == 8.48  # half-up, not the binary-float 8.47
        assert alto["usurario"] is True
        assert basso["usurario"] is False

    def test_unknown_category_is_an_error_not_a_fallback(self):
        # Art. 2 c. 1 L. 108/1996: one limit per category; no silent substitution.
        r = _call("verifica_usura", tasso_applicato=10.0, tipo_operazione="anticipi_sconti")
        assert "errore" in r
        assert "credito_personale" in r["tipi_operazione_disponibili"]

    def test_unknown_quarter_is_an_error_not_a_substitution(self):
        r = _call("verifica_usura", tasso_applicato=10.0, tipo_operazione="credito_personale", trimestre="2024-Q1")
        assert "errore" in r
        assert "2025-Q1" in r["trimestri_disponibili"]

    def test_default_trimestre_resolves_to_current_quarter(self):
        # No trimestre provided — resolves to the quarter containing today,
        # falling back to the latest available one. Data-driven (not pinned
        # to a hardcoded quarter) so it stays valid across quarter rollovers
        # as long as the data-freshness workflow keeps tegm.json current.
        r = _call("verifica_usura", tasso_applicato=5.0, tipo_operazione="mutuo_prima_casa")
        trimestri = json.loads(
            (Path(__file__).parents[2] / "src" / "data" / "tegm.json").read_text()
        )["trimestri"]
        today = date.today().isoformat()
        expected = next(
            (key for key, q in trimestri.items() if q["dal"] <= today <= q["al"]),
            max(trimestri),
        )
        assert r["trimestre"] == expected
        assert r["tegm_pct"] == trimestri[expected]["categorie"]["mutuo_prima_casa"]["tegm"]


# ---------------------------------------------------------------------------
# interessi_acconti
# ---------------------------------------------------------------------------


class TestInteressiAcconti:
    def test_single_acconto(self):
        r = _call(
            "interessi_acconti",
            capitale=10000,
            data_inizio="2024-01-01",
            acconti=[{"data": "2024-07-01", "importo": 5000}],
            data_fine="2025-01-01",
        )
        assert r["capitale_iniziale"] == 10000
        assert r["numero_acconti"] == 1
        assert r["totale_acconti"] == 5000
        assert r["totale_interessi"] > 0
        # Two sub-periods: before and after acconto
        assert len(r["periodi"]) == 2

    def test_no_acconti(self):
        r_acc = _call(
            "interessi_acconti",
            capitale=5000,
            data_inizio="2024-01-01",
            acconti=[],
            data_fine="2025-01-01",
        )
        r_leg = _call(
            "interessi_legali",
            capitale=5000,
            data_inizio="2024-01-01",
            data_fine="2025-01-01",
        )
        # Without acconti, result should be close to interessi_legali
        # (small difference: interessi_acconti uses _days_in_year; interessi_legali uses 365 fixed)
        assert r_acc["totale_interessi"] == pytest.approx(r_leg["totale_interessi"], rel=0.01)

    def test_acconto_reduces_capital(self):
        # imputazione="capitale": payment straight to capital, admitted only with the creditor's
        # consent (art. 1194 co. 1 c.c.); the default imputes to interest first
        r = _call(
            "interessi_acconti",
            capitale=10000,
            data_inizio="2024-01-01",
            acconti=[{"data": "2024-04-01", "importo": 3000}],
            data_fine="2025-01-01",
            imputazione="capitale",
        )
        assert r["capitale_residuo_finale"] == pytest.approx(7000.0, abs=0.01)

    def test_art_1194_default_imputes_to_interest_first(self):
        # art. 1194 c.c.: payment imputed first to accrued interest, the rest to capital.
        # 10000 at 5% from 2023-01-01 to 2023-07-01 (181 days): 247.95 interest; acconto 5000
        # -> 247.95 to interest, 4752.05 to capital -> capital 5247.95.
        # 2023-07-02..2023-12-31 (183 d) at 5% + 2024-01-01 (1 d) at 2.5% on 5247.95 = 131.92.
        # Due = 5247.95 + 131.92 = 5379.87 (5379.86 unrounded; +-0.01 rounding convention)
        r = _call(
            "interessi_acconti",
            capitale=10000,
            data_inizio="2023-01-01",
            acconti=[{"data": "2023-07-01", "importo": 5000}],
            data_fine="2024-01-01",
        )
        assert r["imputazione"] == "interessi"
        assert r["capitale_residuo_finale"] == pytest.approx(5247.95, abs=0.011)
        assert r["interessi_residui"] == pytest.approx(131.92, abs=0.011)
        assert r["totale_dovuto"] == pytest.approx(5379.87, abs=0.011)

    def test_art_1194_two_acconti_across_rate_change(self):
        # 10000 from 2025-06-30, acconti 2000 (2025-10-01) and 1000 (2026-02-15), to 2026-06-30;
        # rates 2% (2025) and 1.6% (2026); art. 1194 imputation: due 7149.40 (7149.39 with per-period rounding)
        r = _call(
            "interessi_acconti",
            capitale=10000,
            data_inizio="2025-06-30",
            acconti=[{"data": "2025-10-01", "importo": 2000}, {"data": "2026-02-15", "importo": 1000}],
            data_fine="2026-06-30",
        )
        assert r["totale_dovuto"] == pytest.approx(7149.40, abs=0.011)
        assert r["capitale_residuo_finale"] == pytest.approx(7107.34, abs=0.011)

    def test_acconto_on_final_date_reduces_residual(self):
        # 10000 at 2% for 2025-01-01..2025-12-31 (364 d): 199.45; acconto 2000 on the final day
        # (dies ad quem included): 199.45 to interest, 1800.55 to capital -> due 8199.45
        r = _call(
            "interessi_acconti",
            capitale=10000,
            data_inizio="2025-01-01",
            acconti=[{"data": "2025-12-31", "importo": 2000}],
            data_fine="2025-12-31",
        )
        assert r["totale_dovuto"] == pytest.approx(8199.45, abs=0.01)
        r2 = _call(
            "interessi_acconti",
            capitale=10000,
            data_inizio="2025-01-01",
            acconti=[{"data": "2025-12-31", "importo": 2000}],
            data_fine="2025-12-31",
            imputazione="capitale",
        )
        assert r2["capitale_residuo_finale"] == pytest.approx(8000.0, abs=0.01)
        assert r2["totale_dovuto"] == pytest.approx(8199.45, abs=0.01)

    def test_acconto_exceeding_credit_is_rejected(self):
        # payment larger than capital plus accrued interest cannot be imputed (art. 1194 c.c.)
        r = _call(
            "interessi_acconti",
            capitale=3000,
            data_inizio="2024-03-01",
            acconti=[{"data": "2024-08-15", "importo": 4000}],
            data_fine="2024-12-31",
        )
        assert "errore" in r

    def test_acconto_outside_period_is_rejected(self):
        before = _call(
            "interessi_acconti", capitale=1000, data_inizio="2024-03-01",
            acconti=[{"data": "2024-02-01", "importo": 100}], data_fine="2024-12-31",
        )
        after = _call(
            "interessi_acconti", capitale=1000, data_inizio="2024-03-01",
            acconti=[{"data": "2025-01-05", "importo": 100}], data_fine="2024-12-31",
        )
        assert "errore" in before and "errore" in after

    def test_invalid_imputazione(self):
        r = _call(
            "interessi_acconti", capitale=1000, data_inizio="2024-03-01",
            acconti=[], data_fine="2024-12-31", imputazione="altro",
        )
        assert "errore" in r

    def test_inverted_dates_error(self):
        r = _call(
            "interessi_acconti",
            capitale=5000,
            data_inizio="2024-12-01",
            acconti=[],
            data_fine="2024-01-01",
        )
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call(
            "interessi_acconti",
            capitale=2000,
            data_inizio="2025-01-01",
            acconti=[],
            data_fine="2025-12-31",
        )
        for key in ("capitale_iniziale", "numero_acconti", "totale_acconti", "capitale_residuo_finale", "totale_interessi", "totale_dovuto", "periodi"):
            assert key in r


# ---------------------------------------------------------------------------
# calcolo_maggior_danno
# ---------------------------------------------------------------------------


class TestCalcoloMaggiorDanno:
    def test_happy_path_returns_result(self):
        r = _call(
            "calcolo_maggior_danno",
            capitale=10000,
            data_inizio="2015-01-01",
            data_fine="2020-01-01",
        )
        assert "errore" not in r
        assert r["capitale"] == 10000
        assert r["maggior_danno"] >= 0
        assert r["criterio_applicato"] in ("rivalutazione", "interessi_legali")

    def test_totale_dovuto_composition(self):
        r = _call(
            "calcolo_maggior_danno",
            capitale=5000,
            data_inizio="2010-01-01",
            data_fine="2020-01-01",
        )
        assert r["totale_dovuto"] == pytest.approx(r["capitale"] + r["importo_spettante"], abs=0.01)

    def test_importo_spettante_is_max(self):
        r = _call(
            "calcolo_maggior_danno",
            capitale=8000,
            data_inizio="2018-01-01",
            data_fine="2023-01-01",
        )
        assert r["importo_spettante"] == pytest.approx(
            max(r["rivalutazione_istat"], r["interessi_legali"]), abs=0.01
        )

    def test_inverted_dates_error(self):
        r = _call(
            "calcolo_maggior_danno",
            capitale=5000,
            data_inizio="2024-12-01",
            data_fine="2024-01-01",
        )
        assert "errore" in r

    def test_returns_normativo(self):
        r = _call(
            "calcolo_maggior_danno",
            capitale=3000,
            data_inizio="2020-01-01",
            data_fine="2024-01-01",
        )
        assert "1224" in r["riferimento_normativo"]
        assert "19499" in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# interessi_corso_causa
# ---------------------------------------------------------------------------


class TestInteressiCorsoCausa:
    def test_happy_path_no_payment(self):
        r = _call(
            "interessi_corso_causa",
            capitale=10000,
            data_citazione="2023-01-01",
            data_sentenza="2024-01-01",
        )
        assert r["capitale"] == 10000
        assert r["totale_interessi"] > 0
        assert "mora" in r["tasso_applicato"].lower()
        # No post-sentenza period when data_pagamento not provided
        assert len(r["periodi"]) == 1

    def test_with_payment_after_sentenza(self):
        r = _call(
            "interessi_corso_causa",
            capitale=5000,
            data_citazione="2023-01-01",
            data_sentenza="2024-01-01",
            data_pagamento="2024-07-01",
        )
        assert len(r["periodi"]) == 2
        assert r["periodi"][0]["tipo"] == "in_corso_causa"
        assert r["periodi"][1]["tipo"] == "post_sentenza"

    def test_totale_dovuto_composition(self):
        r = _call(
            "interessi_corso_causa",
            capitale=8000,
            data_citazione="2024-01-01",
            data_sentenza="2025-01-01",
        )
        assert r["totale_dovuto"] == pytest.approx(r["capitale"] + r["totale_interessi"], abs=0.01)

    def test_inverted_dates_error(self):
        r = _call(
            "interessi_corso_causa",
            capitale=5000,
            data_citazione="2024-12-01",
            data_sentenza="2024-01-01",
        )
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call(
            "interessi_corso_causa",
            capitale=3000,
            data_citazione="2024-01-01",
            data_sentenza="2024-12-31",
        )
        for key in ("capitale", "data_citazione", "data_sentenza", "totale_interessi", "totale_dovuto", "periodi"):
            assert key in r

    def test_mora_rate_applied(self):
        # 2024 mora is 12.50% for H1, higher than legal rate (2.5%)
        r = _call(
            "interessi_corso_causa",
            capitale=10000,
            data_citazione="2024-01-01",
            data_sentenza="2024-06-30",
        )
        # Mora rate should yield more than legal rate
        r_leg = _call(
            "interessi_legali",
            capitale=10000,
            data_inizio="2024-01-01",
            data_fine="2024-06-30",
        )
        assert r["totale_interessi"] > r_leg["totale_interessi"]


# ---------------------------------------------------------------------------
# calcolo_surroga_mutuo
# ---------------------------------------------------------------------------


class TestCalcoloSurrogaMutuo:
    def test_lower_rate_conviene(self):
        # Use the actual ammortamento rata so totale_attuale is consistent
        r_amm = _call("calcolo_ammortamento", capitale=100000, tasso_annuo=4.5, durata_mesi=180)
        rata_reale = r_amm["rata_iniziale"]
        r = _call(
            "calcolo_surroga_mutuo",
            debito_residuo=100000,
            rata_attuale=rata_reale,
            tasso_attuale=4.5,
            tasso_nuovo=2.5,
            mesi_residui=180,
        )
        assert r["conviene"] is True
        assert r["risparmio_totale_interessi"] > 0
        assert r["mutuo_surrogato"]["rata_mensile"] < r["mutuo_attuale"]["rata_mensile"]

    def test_higher_rate_not_conviene(self):
        r = _call(
            "calcolo_surroga_mutuo",
            debito_residuo=50000,
            rata_attuale=400,
            tasso_attuale=2.0,
            tasso_nuovo=4.0,
            mesi_residui=120,
        )
        assert r["conviene"] is False
        assert r["risparmio_totale_interessi"] < 0

    def test_zero_mesi_error(self):
        r = _call(
            "calcolo_surroga_mutuo",
            debito_residuo=100000,
            rata_attuale=600,
            tasso_attuale=4.5,
            tasso_nuovo=3.0,
            mesi_residui=0,
        )
        assert "errore" in r

    def test_zero_rate_new(self):
        r = _call(
            "calcolo_surroga_mutuo",
            debito_residuo=12000,
            rata_attuale=1050,
            tasso_attuale=5.0,
            tasso_nuovo=0.0,
            mesi_residui=12,
        )
        assert r["mutuo_surrogato"]["rata_mensile"] == pytest.approx(1000.0, abs=0.01)

    def test_returns_required_keys(self):
        r = _call(
            "calcolo_surroga_mutuo",
            debito_residuo=80000,
            rata_attuale=500,
            tasso_attuale=3.5,
            tasso_nuovo=2.5,
            mesi_residui=120,
        )
        for key in ("debito_residuo", "mutuo_attuale", "mutuo_surrogato", "risparmio_rata_mensile", "risparmio_totale_interessi", "conviene"):
            assert key in r

    def test_normativo_bersani(self):
        r = _call(
            "calcolo_surroga_mutuo",
            debito_residuo=50000,
            rata_attuale=450,
            tasso_attuale=3.0,
            tasso_nuovo=2.0,
            mesi_residui=100,
        )
        assert "Bersani" in r["riferimento_normativo"] or "120-quater" in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# calcolo_taeg
# ---------------------------------------------------------------------------


class TestCalcoloTaeg:
    def test_happy_path_no_spese(self):
        # 10000 capital, 12 payments of ~855 ≈ TAN 5%
        r = _call(
            "calcolo_taeg",
            capitale=10000,
            rate=12,
            importi_rate=855.0,
        )
        assert "errore" not in r
        assert r["taeg_pct"] > 0
        assert r["tan_pct"] > 0
        assert r["taeg_pct"] >= r["tan_pct"]

    def test_spese_aumentano_taeg(self):
        r_base = _call(
            "calcolo_taeg",
            capitale=10000,
            rate=24,
            importi_rate=440.0,
        )
        r_spese = _call(
            "calcolo_taeg",
            capitale=10000,
            rate=24,
            importi_rate=440.0,
            spese_iniziali=200,
            spese_periodiche=5,
        )
        assert r_spese["taeg_pct"] > r_base["taeg_pct"]

    def test_zero_rate_error(self):
        r = _call(
            "calcolo_taeg",
            capitale=10000,
            rate=0,
            importi_rate=500,
        )
        assert "errore" in r

    def test_spese_iniziali_exceed_capitale_error(self):
        r = _call(
            "calcolo_taeg",
            capitale=1000,
            rate=12,
            importi_rate=100,
            spese_iniziali=1500,
        )
        assert "errore" in r

    def test_returns_required_keys(self):
        r = _call(
            "calcolo_taeg",
            capitale=5000,
            rate=12,
            importi_rate=430.0,
        )
        for key in ("capitale", "rate", "tan_pct", "taeg_pct", "totale_pagato", "costo_totale_credito", "riferimento_normativo"):
            assert key in r

    def test_normativo_tub(self):
        r = _call(
            "calcolo_taeg",
            capitale=5000,
            rate=12,
            importi_rate=430.0,
        )
        assert "TUB" in r["riferimento_normativo"] or "2008/48" in r["riferimento_normativo"]


@pytest.mark.usefixtures("foi_serie_fissa")
class TestMaggiorDannoAvvertenza:
    """Runs on the FOI series frozen at 06/2026 (see conftest.foi_serie_fissa)."""

    def test_avvertenza_mese_non_pubblicato(self):
        r = _call(
            "calcolo_maggior_danno",
            capitale=10000.0,
            data_inizio="2024-01-01",
            data_fine="2026-09-01",
        )
        assert "09/2026" in r["avvertenza"]
        assert "06/2026" in r["avvertenza"]

    def test_senza_avvertenza_su_mesi_pubblicati(self):
        r = _call(
            "calcolo_maggior_danno",
            capitale=10000.0,
            data_inizio="2024-01-01",
            data_fine="2026-06-01",
        )
        assert r["avvertenza"] is None

    def test_pre_1990_errore_esplicito(self):
        # prima della serie (1990) il tool deve fallire, non troncare la
        # rivalutazione al 1990 mentre gli interessi corrono dal 1985
        r = _call(
            "calcolo_maggior_danno",
            capitale=10000.0,
            data_inizio="1985-01-01",
            data_fine="2020-01-01",
        )
        assert "errore" in r
