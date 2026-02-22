"""Arithmetic verification tests for Sezione 2 — Tassi e Interessi (extra tools)."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.tassi_interessi")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestInteressiTassoFisso:

    def test_semplici(self):
        r = _call("interessi_tasso_fisso", capitale=10000, tasso_annuo=5,
                   data_inizio="2024-01-01", data_fine="2025-01-01", tipo="semplici")
        # 10000 * 5% * 366/366 = 500 (2024 is leap year)
        assert_close(r["interessi"], 500.0, tolerance=0.01, label="fisso_semplici")
        assert_close(r["montante"], 10500.0, tolerance=0.01, label="fisso_mont")

    def test_composti(self):
        r = _call("interessi_tasso_fisso", capitale=10000, tasso_annuo=5,
                   data_inizio="2024-01-01", data_fine="2026-01-01", tipo="composti")
        # 10000 * (1.05)^(731/365) = 10000 * 1.05^2.003 ≈ 11025
        assert r["interessi"] > 1000  # more than simple interest

    def test_365_days(self):
        r = _call("interessi_tasso_fisso", capitale=10000, tasso_annuo=10,
                   data_inizio="2023-01-01", data_fine="2024-01-01", tipo="semplici")
        # 2023 is not leap year, 365 days
        expected = 10000 * 10 / 100 * 365 / 365
        assert_close(r["interessi"], round(expected, 2), tolerance=0.01, label="fisso_365")


class TestVerificaUsura:

    def test_non_usurario(self):
        r = _call("verifica_usura", tasso_applicato=5, tipo_operazione="mutuo_prima_casa")
        assert r["usurario"] is False
        assert r["margine"] > 0

    def test_usurario(self):
        r = _call("verifica_usura", tasso_applicato=25, tipo_operazione="credito_personale")
        # TEGM 10.78 → soglia = min(10.78*1.25+4, 10.78+8) = min(17.475, 18.78) = 17.475
        # 25 > 17.475 → usurario
        assert r["usurario"] is True

    def test_formula(self):
        r = _call("verifica_usura", tasso_applicato=10, tipo_operazione="mutuo_prima_casa")
        # TEGM 4.41
        soglia_f = 4.41 * 1.25 + 4  # 9.5125
        soglia_t = 4.41 + 8  # 12.41
        soglia = min(soglia_f, soglia_t)
        assert_close(r["tasso_soglia_pct"], round(soglia, 2), tolerance=0.01, label="usura_soglia")


class TestInteressiAcconti:

    def test_basic(self):
        r = _call("interessi_acconti", capitale=10000, data_inizio="2023-01-01",
                   acconti=[{"data": "2023-07-01", "importo": 5000}],
                   data_fine="2024-01-01")
        assert len(r["periodi"]) == 2
        assert r["capitale_residuo_finale"] == 5000.0
        assert r["totale_interessi"] > 0

    def test_multiple_acconti(self):
        r = _call("interessi_acconti", capitale=10000, data_inizio="2023-01-01",
                   acconti=[
                       {"data": "2023-04-01", "importo": 3000},
                       {"data": "2023-08-01", "importo": 3000},
                   ],
                   data_fine="2024-01-01")
        assert r["capitale_residuo_finale"] == 4000.0
        assert r["totale_acconti"] == 6000.0


class TestCalcoloMaggiorDanno:

    def test_basic(self):
        r = _call("calcolo_maggior_danno", capitale=10000,
                   data_inizio="2015-01-01", data_fine="2023-01-01")
        assert r["rivalutazione_istat"] >= 0
        assert r["interessi_legali"] >= 0
        assert r["criterio_applicato"] in ("rivalutazione", "interessi_legali")
        assert r["importo_spettante"] == max(r["rivalutazione_istat"], r["interessi_legali"])


class TestInteressiCorsoCausa:

    def test_basic(self):
        r = _call("interessi_corso_causa", capitale=50000,
                   data_citazione="2022-01-01", data_sentenza="2024-06-01")
        assert r["totale_interessi"] > 0
        assert len(r["periodi"]) >= 1
        # Should use mora rate, which is much higher than legal rate
        # Mora rate ~8-11%, legal rate ~0.01-2.5%
        # For 50k over ~2.5 years at ~10% mora → ~12,500
        assert r["totale_interessi"] > 5000  # much higher than legal rate would give
        assert r["tasso_applicato"] == "mora D.Lgs. 231/2002 (art. 1284 co. 4 c.c.)"
        assert r["periodi"][0]["tasso_tipo"] == "mora D.Lgs. 231/2002"

    def test_con_pagamento(self):
        r = _call("interessi_corso_causa", capitale=50000,
                   data_citazione="2022-01-01", data_sentenza="2024-06-01",
                   data_pagamento="2024-12-01")
        assert len(r["periodi"]) == 2  # in causa + post sentenza
        assert r["periodi"][1]["tasso_tipo"] == "mora D.Lgs. 231/2002"


class TestCalcoloSurrogaMutuo:

    def test_conviene(self):
        # rata_attuale must be realistic for 150k/4.5%/240m ≈ 949€
        r = _call("calcolo_surroga_mutuo", debito_residuo=150000, rata_attuale=950,
                   tasso_attuale=4.5, tasso_nuovo=3.0, mesi_residui=240)
        assert r["conviene"] is True
        assert r["risparmio_rata_mensile"] > 0
        assert r["mutuo_surrogato"]["rata_mensile"] < 950

    def test_non_conviene(self):
        r = _call("calcolo_surroga_mutuo", debito_residuo=100000, rata_attuale=500,
                   tasso_attuale=2.0, tasso_nuovo=3.5, mesi_residui=120)
        assert r["conviene"] is False


class TestCalcoloTaeg:

    def test_basic(self):
        r = _call("calcolo_taeg", capitale=10000, rate=60, importi_rate=200)
        assert r["taeg_pct"] > 0
        assert r["tan_pct"] > 0
        assert r["costo_totale_credito"] == round(200 * 60 - 10000, 2)

    def test_con_spese(self):
        r_senza = _call("calcolo_taeg", capitale=10000, rate=60, importi_rate=200)
        r_con = _call("calcolo_taeg", capitale=10000, rate=60, importi_rate=200,
                       spese_iniziali=500, spese_periodiche=5)
        assert r_con["taeg_pct"] > r_senza["taeg_pct"]


class TestCalcoloAmmortamento:

    def test_francese_rata_costante(self):
        r = _call("calcolo_ammortamento", capitale=100000, tasso_annuo=3.0, durata_mesi=120,
                   tipo="francese")
        # All rates should be the same
        rate = [p["rata"] for p in r["piano"]]
        assert all(r == rate[0] for r in rate)
        assert r["totale_interessi"] > 0
        # Last debito_residuo should be 0
        assert_close(r["piano"][-1]["debito_residuo"], 0.0, tolerance=0.01, label="amm_residuo")

    def test_italiano_quota_costante(self):
        r = _call("calcolo_ammortamento", capitale=100000, tasso_annuo=3.0, durata_mesi=120,
                   tipo="italiano")
        # All capital quotes should be the same
        quote = [p["quota_capitale"] for p in r["piano"]]
        assert_close(quote[0], round(100000 / 120, 2), tolerance=0.01, label="amm_quota")
        # Rates should decrease
        assert r["piano"][0]["rata"] > r["piano"][-1]["rata"]
