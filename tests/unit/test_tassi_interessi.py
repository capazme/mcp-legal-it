import importlib

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

    def test_default_trimestre_resolves_to_current_quarter(self):
        # No trimestre provided — should auto-detect and return a valid quarter key
        r = _call("verifica_usura", tasso_applicato=5.0, tipo_operazione="mutuo_prima_casa")
        assert "trimestre" in r
        assert r["trimestre"].startswith("20")
        # Should resolve to 2026-Q1 (current date: 2026-03-30)
        assert r["trimestre"] == "2026-Q1"
        assert r["tegm_pct"] == 3.96


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
        r = _call(
            "interessi_acconti",
            capitale=10000,
            data_inizio="2024-01-01",
            acconti=[{"data": "2024-04-01", "importo": 3000}],
            data_fine="2025-01-01",
        )
        assert r["capitale_residuo_finale"] == pytest.approx(7000.0, abs=0.01)

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
