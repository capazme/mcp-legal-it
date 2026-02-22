"""Arithmetic verification tests for Sezione 1 — Rivalutazioni ISTAT."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.rivalutazioni_istat")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestRivalutazioneMonetaria:

    def test_basic(self):
        r = _call("rivalutazione_monetaria", capitale=10000,
                   data_inizio="2015-01-01", data_fine="2023-12-31", con_interessi_legali=False)
        assert r["capitale_rivalutato"] > 10000
        assert r["coefficiente_rivalutazione"] > 1.0
        assert len(r["dettaglio_anni"]) > 0

    def test_con_interessi(self):
        r = _call("rivalutazione_monetaria", capitale=10000,
                   data_inizio="2015-01-01", data_fine="2023-12-31", con_interessi_legali=True)
        assert "totale_interessi_legali" in r
        assert r["totale_interessi_legali"] > 0
        assert r["totale_dovuto"] > r["capitale_rivalutato"]

    def test_date_inverse(self):
        r = _call("rivalutazione_monetaria", capitale=10000,
                   data_inizio="2023-01-01", data_fine="2020-01-01")
        assert "errore" in r

    def test_consistency(self):
        """coefficiente_rivalutazione = foi_fine / foi_inizio."""
        r = _call("rivalutazione_monetaria", capitale=5000,
                   data_inizio="2018-06-01", data_fine="2022-06-01", con_interessi_legali=False)
        expected_coeff = r["foi_fine"] / r["foi_inizio"]
        assert_close(r["coefficiente_rivalutazione"], round(expected_coeff, 6),
                     tolerance=0.000001, label="riv_coeff")
        assert_close(r["capitale_rivalutato"], round(5000 * expected_coeff, 2),
                     tolerance=0.01, label="riv_cap")


class TestRivalutazioneMensile:

    def test_12_mesi(self):
        r = _call("rivalutazione_mensile", importo_mensile=1000,
                   data_inizio="2022-01-01", data_fine="2022-12-31")
        assert r["numero_mensilita"] == 12
        assert r["totale_nominale"] == 12000.0
        assert r["totale_rivalutato"] >= r["totale_nominale"]  # FOI increased

    def test_differenza_positiva(self):
        r = _call("rivalutazione_mensile", importo_mensile=500,
                   data_inizio="2015-01-01", data_fine="2023-01-01")
        # Over 8 years with inflation, difference should be positive
        assert r["differenza_totale"] > 0


class TestAdeguamentoCanone:

    def test_base(self):
        r = _call("adeguamento_canone_locazione", canone_annuo=12000,
                   data_stipula="2020-01-01", data_adeguamento="2023-01-01")
        assert r["canone_annuo_aggiornato"] > 12000
        assert r["variazione_foi_piena_pct"] > 0

    def test_percentuale_100(self):
        r = _call("adeguamento_canone_locazione", canone_annuo=12000,
                   data_stipula="2020-01-01", data_adeguamento="2023-01-01",
                   percentuale_istat=100)
        r75 = _call("adeguamento_canone_locazione", canone_annuo=12000,
                     data_stipula="2020-01-01", data_adeguamento="2023-01-01",
                     percentuale_istat=75)
        # 100% ISTAT should give higher adjustment
        assert r["canone_annuo_aggiornato"] > r75["canone_annuo_aggiornato"]

    def test_mensile(self):
        r = _call("adeguamento_canone_locazione", canone_annuo=12000,
                   data_stipula="2020-01-01", data_adeguamento="2023-01-01")
        assert_close(r["canone_mensile_originario"], 1000.0, tolerance=0.01, label="mens_orig")
        assert_close(r["canone_mensile_aggiornato"],
                     round(r["canone_annuo_aggiornato"] / 12, 2), tolerance=0.01, label="mens_agg")


class TestCalcoloInflazione:

    def test_basic(self):
        r = _call("calcolo_inflazione", data_inizio="2015-01-01", data_fine="2023-01-01")
        assert r["variazione_percentuale"] > 0
        assert r["coefficiente_rivalutazione"] > 1.0

    def test_coeff_consistency(self):
        r = _call("calcolo_inflazione", data_inizio="2015-06-01", data_fine="2020-06-01")
        expected = r["foi_fine"] / r["foi_inizio"]
        assert_close(r["coefficiente_rivalutazione"], round(expected, 6),
                     tolerance=0.000001, label="infl_coeff")


class TestRivalutazioneTfr:

    def test_10_anni(self):
        r = _call("rivalutazione_tfr", retribuzione_annua=30000, anni_servizio=10,
                   anno_cessazione=2024)
        assert r["accantonamento_annuo"] == round(30000 / 13.5, 2)
        assert r["tfr_lordo"] > r["accantonamento_annuo"] * 10  # rivalutato
        assert r["imposta_sostitutiva_17_pct"] > 0

    def test_1_anno(self):
        r = _call("rivalutazione_tfr", retribuzione_annua=30000, anni_servizio=1,
                   anno_cessazione=2024)
        # First year has no rivalutazione
        assert_close(r["tfr_lordo"], round(30000 / 13.5, 2), tolerance=0.01, label="tfr_1anno")
        assert r["totale_rivalutazioni"] == 0.0


class TestCalcoloDevalutazione:

    def test_basic(self):
        r = _call("calcolo_devalutazione", importo_attuale=10000,
                   data_attuale="2023-01-01", data_passata="2015-01-01")
        assert r["importo_in_data_passata"] < 10000
        assert r["perdita_potere_acquisto_pct"] > 0

    def test_consistency_with_rivalutazione(self):
        """Devalutazione coefficient should be inverse of rivalutazione."""
        r_riv = _call("calcolo_inflazione", data_inizio="2015-01-01", data_fine="2023-01-01")
        r_dev = _call("calcolo_devalutazione", importo_attuale=10000,
                       data_attuale="2023-01-01", data_passata="2015-01-01")
        # coeff_dev ≈ 1/coeff_riv
        product = r_riv["coefficiente_rivalutazione"] * r_dev["coefficiente_devalutazione"]
        assert_close(product, 1.0, tolerance=0.001, label="riv_dev_inverse")


class TestRivalutazioneStorica:

    def test_basic(self):
        r = _call("rivalutazione_storica", importo=10000, anno_partenza=2015, anno_arrivo=2023)
        assert r["importo_rivalutato"] > 10000
        assert len(r["dettaglio_anni"]) == 9  # 2015-2023 inclusive

    def test_coeff_consistency(self):
        r = _call("rivalutazione_storica", importo=5000, anno_partenza=2018, anno_arrivo=2022)
        # media_foi values in response are rounded to 2dp, so re-dividing them
        # introduces rounding error vs the coefficient (computed from raw values)
        expected = r["media_foi_arrivo"] / r["media_foi_partenza"]
        assert_close(r["coefficiente_rivalutazione"], round(expected, 6),
                     tolerance=0.001, label="stor_coeff")


class TestVariazioniIstat:

    def test_basic(self):
        r = _call("variazioni_istat", anno_inizio=2018, anno_fine=2023)
        assert len(r["tabella"]) > 0
        assert r["tabella"][0]["variazione_pct"] is None  # first year
        assert r["variazione_cumulata_pct"] is not None
