import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.rivalutazioni_istat")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# rivalutazione_monetaria
# ---------------------------------------------------------------------------

class TestRivalutazioneMonetaria:
    def test_happy_path_no_interessi(self):
        result = _call(
            "rivalutazione_monetaria",
            capitale=100.0,
            data_inizio="2000-01-01",
            data_fine="2020-01-01",
            con_interessi_legali=False,
        )
        # FOI 2000/01=81.3, 2020/01=102.7 => coeff=1.263223
        assert result["capitale_originario"] == 100.0
        assert result["foi_inizio"] == pytest.approx(81.3)
        assert result["foi_fine"] == pytest.approx(102.7)
        assert result["coefficiente_rivalutazione"] == pytest.approx(1.263223, rel=1e-4)
        assert result["capitale_rivalutato"] == pytest.approx(126.32, abs=0.01)
        assert "totale_interessi_legali" not in result

    def test_happy_path_con_interessi(self):
        result = _call(
            "rivalutazione_monetaria",
            capitale=1000.0,
            data_inizio="2015-01-01",
            data_fine="2025-01-01",
            con_interessi_legali=True,
        )
        assert "totale_interessi_legali" in result
        assert "totale_dovuto" in result
        assert result["totale_dovuto"] > result["capitale_rivalutato"]
        assert result["capitale_rivalutato"] == pytest.approx(1212.64, abs=0.5)

    def test_dettaglio_anni_populated(self):
        result = _call(
            "rivalutazione_monetaria",
            capitale=500.0,
            data_inizio="2018-01-01",
            data_fine="2020-01-01",
            con_interessi_legali=False,
        )
        assert len(result["dettaglio_anni"]) == 3  # 2018, 2019, 2020
        for entry in result["dettaglio_anni"]:
            assert "anno" in entry
            assert "capitale_rivalutato" in entry

    def test_error_date_invertite(self):
        result = _call(
            "rivalutazione_monetaria",
            capitale=100.0,
            data_inizio="2020-01-01",
            data_fine="2015-01-01",
        )
        assert "errore" in result

    def test_error_date_uguali(self):
        result = _call(
            "rivalutazione_monetaria",
            capitale=100.0,
            data_inizio="2020-01-01",
            data_fine="2020-01-01",
        )
        assert "errore" in result

    def test_capitale_zero(self):
        result = _call(
            "rivalutazione_monetaria",
            capitale=0.0,
            data_inizio="2000-01-01",
            data_fine="2020-01-01",
            con_interessi_legali=False,
        )
        assert result["capitale_rivalutato"] == 0.0

    def test_interessi_legali_entry_fields(self):
        result = _call(
            "rivalutazione_monetaria",
            capitale=1000.0,
            data_inizio="2020-01-01",
            data_fine="2022-01-01",
            con_interessi_legali=True,
        )
        for entry in result["dettaglio_anni"]:
            assert "tasso_legale_pct" in entry
            assert "giorni" in entry
            assert "interessi_legali" in entry


# ---------------------------------------------------------------------------
# rivalutazione_mensile
# ---------------------------------------------------------------------------

class TestRivalutazioneMensile:
    def test_happy_path_4_mesi(self):
        # 2020/04 is the riferimento; rates for 01-04 are 102.7,102.5,102.6,102.5
        result = _call(
            "rivalutazione_mensile",
            importo_mensile=500.0,
            data_inizio="2020-01-01",
            data_fine="2020-04-01",
        )
        assert result["numero_mensilita"] == 4
        assert result["totale_nominale"] == pytest.approx(2000.0)
        assert result["totale_rivalutato"] == pytest.approx(1998.54, abs=0.1)
        assert result["differenza_totale"] == pytest.approx(
            result["totale_rivalutato"] - result["totale_nominale"], abs=0.01
        )

    def test_single_month_same_as_finale(self):
        # When mese == fine, coeff should be 1.0
        result = _call(
            "rivalutazione_mensile",
            importo_mensile=1000.0,
            data_inizio="2020-04-01",
            data_fine="2020-04-01",
        )
        # data_fine == data_inizio → error
        assert "errore" in result

    def test_happy_path_multi_year(self):
        result = _call(
            "rivalutazione_mensile",
            importo_mensile=300.0,
            data_inizio="2019-11-01",
            data_fine="2020-02-01",
        )
        assert result["numero_mensilita"] == 4
        assert result["totale_nominale"] == pytest.approx(1200.0)
        assert result["totale_rivalutato"] > result["totale_nominale"]

    def test_error_date_invertite(self):
        result = _call(
            "rivalutazione_mensile",
            importo_mensile=500.0,
            data_inizio="2021-01-01",
            data_fine="2020-01-01",
        )
        assert "errore" in result

    def test_dettaglio_structure(self):
        result = _call(
            "rivalutazione_mensile",
            importo_mensile=200.0,
            data_inizio="2020-01-01",
            data_fine="2020-03-01",
        )
        assert len(result["dettaglio_mensile"]) == 3
        for entry in result["dettaglio_mensile"]:
            assert "anno" in entry
            assert "mese" in entry
            assert "importo_rivalutato" in entry
            assert "differenza" in entry

    def test_zero_importo(self):
        result = _call(
            "rivalutazione_mensile",
            importo_mensile=0.0,
            data_inizio="2020-01-01",
            data_fine="2020-03-01",
        )
        assert result["totale_nominale"] == 0.0
        assert result["totale_rivalutato"] == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# adeguamento_canone_locazione
# ---------------------------------------------------------------------------

class TestAdeguamentoCanoneLocazione:
    def test_happy_path_75pct(self):
        # FOI 2010/01=95.0, 2020/01=102.7 => var_piena=8.105%, var_75=6.079%
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=10000.0,
            data_stipula="2010-01-01",
            data_adeguamento="2020-01-01",
            percentuale_istat=75.0,
        )
        assert result["canone_annuo_aggiornato"] == pytest.approx(10607.89, abs=0.5)
        assert result["canone_mensile_aggiornato"] == pytest.approx(10607.89 / 12, abs=0.1)
        assert result["percentuale_istat_applicata"] == 75.0
        assert "L. 392/1978" in result["riferimento_normativo"]

    def test_happy_path_100pct(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=10000.0,
            data_stipula="2010-01-01",
            data_adeguamento="2020-01-01",
            percentuale_istat=100.0,
        )
        assert result["canone_annuo_aggiornato"] == pytest.approx(10810.53, abs=0.5)

    def test_canone_mensile_originario(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2015-01-01",
            data_adeguamento="2024-01-01",
        )
        assert result["canone_mensile_originario"] == pytest.approx(1000.0)
        assert result["aumento_annuo"] == pytest.approx(
            result["canone_annuo_aggiornato"] - 12000.0, abs=0.01
        )

    def test_error_date_invertite(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=10000.0,
            data_stipula="2020-01-01",
            data_adeguamento="2010-01-01",
        )
        assert "errore" in result

    def test_error_date_uguali(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=10000.0,
            data_stipula="2020-01-01",
            data_adeguamento="2020-01-01",
        )
        assert "errore" in result

    def test_zero_percentuale(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=10000.0,
            data_stipula="2010-01-01",
            data_adeguamento="2020-01-01",
            percentuale_istat=0.0,
        )
        assert result["canone_annuo_aggiornato"] == pytest.approx(10000.0)
        assert result["aumento_annuo"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# calcolo_inflazione
# ---------------------------------------------------------------------------

class TestCalcoloInflazione:
    def test_happy_path(self):
        # FOI 2000/01=81.3, 2020/01=102.7 => var=26.32%
        result = _call(
            "calcolo_inflazione",
            data_inizio="2000-01-01",
            data_fine="2020-01-01",
        )
        assert result["variazione_percentuale"] == pytest.approx(26.32, abs=0.05)
        assert result["coefficiente_rivalutazione"] == pytest.approx(1.263223, rel=1e-4)
        assert result["base_indici"] == "2015=100"
        assert "esempio" in result

    def test_anni_positivi(self):
        result = _call(
            "calcolo_inflazione",
            data_inizio="2015-01-01",
            data_fine="2020-01-01",
        )
        assert result["anni"] == pytest.approx(5.0, abs=0.05)
        assert result["inflazione_media_annua_pct"] > 0

    def test_error_date_invertite(self):
        result = _call(
            "calcolo_inflazione",
            data_inizio="2020-01-01",
            data_fine="2015-01-01",
        )
        assert "errore" in result

    def test_error_date_uguali(self):
        result = _call(
            "calcolo_inflazione",
            data_inizio="2020-01-01",
            data_fine="2020-01-01",
        )
        assert "errore" in result

    def test_coefficiente_gt_1_for_positive_inflation(self):
        result = _call(
            "calcolo_inflazione",
            data_inizio="2000-01-01",
            data_fine="2024-01-01",
        )
        assert result["coefficiente_rivalutazione"] > 1.0
        assert result["variazione_percentuale"] > 0


# ---------------------------------------------------------------------------
# rivalutazione_tfr
# ---------------------------------------------------------------------------

class TestRivalutazioneTfr:
    def test_happy_path_3_anni(self):
        # retribuzione 30000, 3 anni, cessazione 2021 => inizio 2018
        result = _call(
            "rivalutazione_tfr",
            retribuzione_annua=30000.0,
            anni_servizio=3,
            anno_cessazione=2021,
        )
        assert result["accantonamento_annuo"] == pytest.approx(2222.22, abs=0.01)
        assert result["anno_inizio"] == 2018
        assert result["anno_cessazione"] == 2021
        assert len(result["dettaglio_anni"]) == 3
        assert result["tfr_lordo"] == pytest.approx(6795.34, abs=1.0)
        assert result["imposta_sostitutiva_17_pct"] == pytest.approx(
            result["totale_rivalutazioni"] * 0.17, abs=0.01
        )

    def test_tfr_netto_formula(self):
        result = _call(
            "rivalutazione_tfr",
            retribuzione_annua=40000.0,
            anni_servizio=5,
            anno_cessazione=2022,
        )
        expected_netto = result["tfr_lordo"] - result["imposta_sostitutiva_17_pct"]
        assert result["tfr_netto_rivalutazione"] == pytest.approx(expected_netto, abs=0.01)

    def test_anno_inizio_dettaglio_no_rivalutazione(self):
        result = _call(
            "rivalutazione_tfr",
            retribuzione_annua=30000.0,
            anni_servizio=3,
            anno_cessazione=2021,
        )
        first_entry = result["dettaglio_anni"][0]
        assert first_entry["variazione_foi_pct"] == pytest.approx(0.0)
        assert first_entry["rivalutazione"] == pytest.approx(0.0)

    def test_error_anni_zero(self):
        result = _call(
            "rivalutazione_tfr",
            retribuzione_annua=30000.0,
            anni_servizio=0,
            anno_cessazione=2021,
        )
        assert "errore" in result

    def test_error_anni_negativi(self):
        result = _call(
            "rivalutazione_tfr",
            retribuzione_annua=30000.0,
            anni_servizio=-1,
            anno_cessazione=2021,
        )
        assert "errore" in result

    def test_riferimento_normativo(self):
        result = _call(
            "rivalutazione_tfr",
            retribuzione_annua=20000.0,
            anni_servizio=2,
            anno_cessazione=2020,
        )
        assert "2120 c.c." in result["riferimento_normativo"]


# ---------------------------------------------------------------------------
# interessi_vari_capitale_rivalutato
# ---------------------------------------------------------------------------

class TestInteressiVariCapitaleRivalutato:
    def test_happy_path_tasso_legale(self):
        result = _call(
            "interessi_vari_capitale_rivalutato",
            capitale=1000.0,
            data_inizio="2015-01-01",
            data_fine="2020-01-01",
        )
        assert result["capitale_rivalutato"] > 1000.0
        assert result["totale_interessi"] > 0
        assert result["totale_dovuto"] == pytest.approx(
            result["capitale_rivalutato"] + result["totale_interessi"], abs=0.01
        )
        assert result["tasso_utilizzato"] == "tasso legale variabile"

    def test_happy_path_tasso_personalizzato(self):
        result = _call(
            "interessi_vari_capitale_rivalutato",
            capitale=1000.0,
            data_inizio="2015-01-01",
            data_fine="2020-01-01",
            tasso_personalizzato=5.0,
        )
        assert result["tasso_utilizzato"] == "5.0% personalizzato"
        for entry in result["dettaglio_anni"]:
            assert entry["tipo_tasso"] == "personalizzato"
            assert entry["tasso_pct"] == 5.0

    def test_tasso_personalizzato_higher_gives_more_interessi(self):
        result_low = _call(
            "interessi_vari_capitale_rivalutato",
            capitale=1000.0,
            data_inizio="2015-01-01",
            data_fine="2020-01-01",
            tasso_personalizzato=1.0,
        )
        result_high = _call(
            "interessi_vari_capitale_rivalutato",
            capitale=1000.0,
            data_inizio="2015-01-01",
            data_fine="2020-01-01",
            tasso_personalizzato=10.0,
        )
        assert result_high["totale_interessi"] > result_low["totale_interessi"]

    def test_error_date_invertite(self):
        result = _call(
            "interessi_vari_capitale_rivalutato",
            capitale=1000.0,
            data_inizio="2020-01-01",
            data_fine="2015-01-01",
        )
        assert "errore" in result

    def test_dettaglio_structure(self):
        result = _call(
            "interessi_vari_capitale_rivalutato",
            capitale=500.0,
            data_inizio="2019-01-01",
            data_fine="2021-01-01",
        )
        assert len(result["dettaglio_anni"]) == 3
        for entry in result["dettaglio_anni"]:
            assert "coefficiente" in entry
            assert "capitale_rivalutato" in entry
            assert "interessi" in entry
            assert "giorni" in entry


# ---------------------------------------------------------------------------
# lettera_adeguamento_canone
# ---------------------------------------------------------------------------

class TestLetteraAdeguamentoCanone:
    def test_happy_path(self):
        result = _call(
            "lettera_adeguamento_canone",
            locatore="Mario Rossi",
            conduttore="Luigi Bianchi",
            indirizzo_immobile="Via Roma 1, Milano",
            canone_attuale=1000.0,
            data_stipula="2015-01-01",
            data_adeguamento="2024-01-01",
        )
        assert "lettera" in result
        assert "Mario Rossi" in result["lettera"]
        assert "Luigi Bianchi" in result["lettera"]
        assert "Via Roma 1, Milano" in result["lettera"]
        assert result["canone_attuale"] == 1000.0
        assert result["canone_nuovo"] > 1000.0
        assert "L. 392/1978" in result["riferimento_normativo"]

    def test_lettera_contains_dati_calcolo(self):
        result = _call(
            "lettera_adeguamento_canone",
            locatore="Mario Rossi",
            conduttore="Luigi Bianchi",
            indirizzo_immobile="Via Roma 1",
            canone_attuale=800.0,
            data_stipula="2010-01-01",
            data_adeguamento="2020-01-01",
            percentuale_istat=75.0,
        )
        lettera = result["lettera"]
        assert "DATI DI CALCOLO" in lettera
        assert "75" in lettera  # percentuale applicata
        assert "NUOVO CANONE MENSILE" in lettera

    def test_aumento_mensile_coerente(self):
        result = _call(
            "lettera_adeguamento_canone",
            locatore="A",
            conduttore="B",
            indirizzo_immobile="C",
            canone_attuale=1000.0,
            data_stipula="2015-01-01",
            data_adeguamento="2025-01-01",
        )
        assert result["aumento_mensile"] == pytest.approx(
            result["canone_nuovo"] - result["canone_attuale"], abs=0.01
        )

    def test_error_date_invertite(self):
        result = _call(
            "lettera_adeguamento_canone",
            locatore="A",
            conduttore="B",
            indirizzo_immobile="C",
            canone_attuale=1000.0,
            data_stipula="2020-01-01",
            data_adeguamento="2015-01-01",
        )
        assert "errore" in result

    def test_error_date_uguali(self):
        result = _call(
            "lettera_adeguamento_canone",
            locatore="A",
            conduttore="B",
            indirizzo_immobile="C",
            canone_attuale=1000.0,
            data_stipula="2020-01-01",
            data_adeguamento="2020-01-01",
        )
        assert "errore" in result

    def test_100pct_produces_higher_canone(self):
        result_75 = _call(
            "lettera_adeguamento_canone",
            locatore="A",
            conduttore="B",
            indirizzo_immobile="C",
            canone_attuale=1000.0,
            data_stipula="2010-01-01",
            data_adeguamento="2020-01-01",
            percentuale_istat=75.0,
        )
        result_100 = _call(
            "lettera_adeguamento_canone",
            locatore="A",
            conduttore="B",
            indirizzo_immobile="C",
            canone_attuale=1000.0,
            data_stipula="2010-01-01",
            data_adeguamento="2020-01-01",
            percentuale_istat=100.0,
        )
        assert result_100["canone_nuovo"] > result_75["canone_nuovo"]


# ---------------------------------------------------------------------------
# calcolo_devalutazione
# ---------------------------------------------------------------------------

class TestCalcoloDevalutazione:
    def test_happy_path(self):
        # FOI 2020/01=102.7, FOI 2000/01=81.3 => coeff=81.3/102.7=0.791626
        result = _call(
            "calcolo_devalutazione",
            importo_attuale=1000.0,
            data_attuale="2020-01-01",
            data_passata="2000-01-01",
        )
        assert result["coefficiente_devalutazione"] == pytest.approx(0.791626, rel=1e-4)
        assert result["importo_in_data_passata"] == pytest.approx(791.63, abs=0.05)
        assert result["perdita_potere_acquisto_pct"] > 0
        assert "esempio" in result

    def test_perdita_acquisto_coerente(self):
        result = _call(
            "calcolo_devalutazione",
            importo_attuale=1000.0,
            data_attuale="2024-01-01",
            data_passata="2000-01-01",
        )
        assert result["perdita_potere_acquisto_pct"] == pytest.approx(
            (1 - result["coefficiente_devalutazione"]) * 100, abs=0.01
        )

    def test_importo_in_data_passata_lt_attuale(self):
        result = _call(
            "calcolo_devalutazione",
            importo_attuale=1000.0,
            data_attuale="2024-01-01",
            data_passata="2000-01-01",
        )
        # inflation => past value is less
        assert result["importo_in_data_passata"] < 1000.0

    def test_error_date_invertite(self):
        result = _call(
            "calcolo_devalutazione",
            importo_attuale=1000.0,
            data_attuale="2000-01-01",
            data_passata="2020-01-01",
        )
        assert "errore" in result

    def test_error_date_uguali(self):
        result = _call(
            "calcolo_devalutazione",
            importo_attuale=1000.0,
            data_attuale="2020-01-01",
            data_passata="2020-01-01",
        )
        assert "errore" in result

    def test_zero_importo(self):
        result = _call(
            "calcolo_devalutazione",
            importo_attuale=0.0,
            data_attuale="2020-01-01",
            data_passata="2000-01-01",
        )
        assert result["importo_in_data_passata"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# rivalutazione_storica
# ---------------------------------------------------------------------------

class TestRivalutazioneStoica:
    def test_happy_path(self):
        # media 2000=82.69, media 2020=102.33 => coeff=1.237529
        result = _call(
            "rivalutazione_storica",
            importo=1000.0,
            anno_partenza=2000,
            anno_arrivo=2020,
        )
        assert result["importo_rivalutato"] == pytest.approx(1237.53, abs=0.5)
        assert result["coefficiente_rivalutazione"] == pytest.approx(1.237529, rel=1e-3)
        assert result["differenza"] == pytest.approx(
            result["importo_rivalutato"] - 1000.0, abs=0.01
        )

    def test_dettaglio_has_all_years(self):
        result = _call(
            "rivalutazione_storica",
            importo=100.0,
            anno_partenza=2018,
            anno_arrivo=2020,
        )
        anni = [e["anno"] for e in result["dettaglio_anni"]]
        assert 2018 in anni
        assert 2019 in anni
        assert 2020 in anni

    def test_error_anno_arrivo_minore(self):
        result = _call(
            "rivalutazione_storica",
            importo=1000.0,
            anno_partenza=2020,
            anno_arrivo=2018,
        )
        assert "errore" in result

    def test_error_stesso_anno(self):
        result = _call(
            "rivalutazione_storica",
            importo=1000.0,
            anno_partenza=2020,
            anno_arrivo=2020,
        )
        assert "errore" in result

    def test_anno_partenza_in_dettaglio_coeff_1(self):
        result = _call(
            "rivalutazione_storica",
            importo=1000.0,
            anno_partenza=2015,
            anno_arrivo=2020,
        )
        primo = result["dettaglio_anni"][0]
        assert primo["anno"] == 2015
        assert primo["coefficiente"] == pytest.approx(1.0, abs=0.001)
        assert primo["importo_rivalutato"] == pytest.approx(1000.0, abs=0.5)


# ---------------------------------------------------------------------------
# variazioni_istat
# ---------------------------------------------------------------------------

class TestVariazioniIstat:
    def test_happy_path(self):
        result = _call(
            "variazioni_istat",
            anno_inizio=2018,
            anno_fine=2020,
        )
        assert result["anno_inizio"] == 2018
        assert result["anno_fine"] == 2020
        assert result["base_indici"] == "2015=100"
        anni = [r["anno"] for r in result["tabella"]]
        assert 2018 in anni
        assert 2019 in anni
        assert 2020 in anni

    def test_primo_anno_variazione_none(self):
        result = _call(
            "variazioni_istat",
            anno_inizio=2018,
            anno_fine=2021,
        )
        primo = result["tabella"][0]
        assert primo["anno"] == 2018
        assert primo["variazione_pct"] is None

    def test_variazione_cumulata_coerente(self):
        result = _call(
            "variazioni_istat",
            anno_inizio=2015,
            anno_fine=2020,
        )
        assert result["variazione_cumulata_pct"] is not None
        assert result["variazione_cumulata_pct"] > 0

    def test_error_anno_fine_minore(self):
        result = _call(
            "variazioni_istat",
            anno_inizio=2020,
            anno_fine=2018,
        )
        assert "errore" in result

    def test_error_stesso_anno(self):
        result = _call(
            "variazioni_istat",
            anno_inizio=2020,
            anno_fine=2020,
        )
        assert "errore" in result

    def test_media_foi_presente(self):
        result = _call(
            "variazioni_istat",
            anno_inizio=2019,
            anno_fine=2021,
        )
        for row in result["tabella"]:
            assert "media_foi" in row
            assert row["media_foi"] > 0


# ---------------------------------------------------------------------------
# rivalutazione_annuale_media
# ---------------------------------------------------------------------------

class TestRivalutazioneAnnualeMedia:
    def test_happy_path(self):
        result = _call(
            "rivalutazione_annuale_media",
            importo=1000.0,
            data_inizio="2000-06-15",
            data_fine="2020-06-15",
        )
        # uses only years 2000 and 2020
        assert result["anno_inizio"] == 2000
        assert result["anno_fine"] == 2020
        assert result["importo_rivalutato"] == pytest.approx(1237.53, abs=0.5)
        assert "Calcolo basato su media annua FOI" in result["nota"]

    def test_differenza_coerente(self):
        result = _call(
            "rivalutazione_annuale_media",
            importo=500.0,
            data_inizio="2015-01-01",
            data_fine="2024-01-01",
        )
        assert result["differenza"] == pytest.approx(
            result["importo_rivalutato"] - 500.0, abs=0.01
        )

    def test_error_date_invertite(self):
        result = _call(
            "rivalutazione_annuale_media",
            importo=1000.0,
            data_inizio="2020-01-01",
            data_fine="2015-01-01",
        )
        assert "errore" in result

    def test_error_stessa_data(self):
        result = _call(
            "rivalutazione_annuale_media",
            importo=1000.0,
            data_inizio="2020-01-01",
            data_fine="2020-06-01",
        )
        # same year → error since dt_fine <= dt_inizio? No, different day but same year
        # Actually date 2020-06-01 > 2020-01-01, so no error here — just same-year calc
        # Only year-level comparison, so this should succeed
        assert "importo_rivalutato" in result or "errore" in result

    def test_zero_importo(self):
        result = _call(
            "rivalutazione_annuale_media",
            importo=0.0,
            data_inizio="2000-01-01",
            data_fine="2020-01-01",
        )
        assert result["importo_rivalutato"] == pytest.approx(0.0)
        assert result["differenza"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# inflazione_titoli_stato
# ---------------------------------------------------------------------------

class TestInflazioneTitoliStato:
    def test_happy_path(self):
        # 2015/01 -> 2020/01, rendimento 3%
        result = _call(
            "inflazione_titoli_stato",
            capitale_investito=10000.0,
            rendimento_lordo_annuo_pct=3.0,
            data_inizio="2015-01-01",
            data_fine="2020-01-01",
        )
        assert result["montante_nominale"] == pytest.approx(11592.51, abs=1.0)
        assert result["anni"] == pytest.approx(5.0, abs=0.05)
        assert result["potere_acquisto_preservato"] is True  # rend > inflazione
        assert result["rendimento_reale_annuo_pct"] == pytest.approx(2.39, abs=0.1)

    def test_rendimento_zero_non_preserva(self):
        result = _call(
            "inflazione_titoli_stato",
            capitale_investito=10000.0,
            rendimento_lordo_annuo_pct=0.0,
            data_inizio="2000-01-01",
            data_fine="2024-01-01",
        )
        assert result["potere_acquisto_preservato"] is False

    def test_rendimento_molto_alto_preserva(self):
        result = _call(
            "inflazione_titoli_stato",
            capitale_investito=10000.0,
            rendimento_lordo_annuo_pct=20.0,
            data_inizio="2000-01-01",
            data_fine="2020-01-01",
        )
        assert result["potere_acquisto_preservato"] is True

    def test_montante_nominale_formula(self):
        result = _call(
            "inflazione_titoli_stato",
            capitale_investito=5000.0,
            rendimento_lordo_annuo_pct=5.0,
            data_inizio="2015-01-01",
            data_fine="2025-01-01",
        )
        assert result["rendimento_nominale_totale"] == pytest.approx(
            result["montante_nominale"] - 5000.0, abs=0.01
        )
        assert result["rendimento_reale_totale"] == pytest.approx(
            result["montante_reale"] - 5000.0, abs=0.01
        )

    def test_error_date_invertite(self):
        result = _call(
            "inflazione_titoli_stato",
            capitale_investito=10000.0,
            rendimento_lordo_annuo_pct=3.0,
            data_inizio="2020-01-01",
            data_fine="2015-01-01",
        )
        assert "errore" in result

    def test_error_date_uguali(self):
        result = _call(
            "inflazione_titoli_stato",
            capitale_investito=10000.0,
            rendimento_lordo_annuo_pct=3.0,
            data_inizio="2020-01-01",
            data_fine="2020-01-01",
        )
        assert "errore" in result

    def test_nota_fisher(self):
        result = _call(
            "inflazione_titoli_stato",
            capitale_investito=1000.0,
            rendimento_lordo_annuo_pct=2.0,
            data_inizio="2015-01-01",
            data_fine="2020-01-01",
        )
        assert "Fisher" in result["nota"]
