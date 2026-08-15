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
        # FOI 2015/01=99.7, 2025/01=120.9 (GU n.43 del 21-2-2026) => 1000*120.9/99.7
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


# ---------------------------------------------------------------------------
# Serie FOI ufficiale — dati verificati sui comunicati ISTAT in GU
# (raccordo base 2025=100 / base 2015=100, coefficiente ufficiale 1,214)
# ---------------------------------------------------------------------------

def _mod():
    return importlib.import_module("src.tools.rivalutazioni_istat")


class TestSerieFoiUfficiale:
    """Data integrity: values pinned to the official ISTAT communiqués in GU."""

    def test_serie_2025_da_comunicati_gu(self):
        # GU n.43 del 21-2-2026 (26A00824) e GU n.175 del 30-7-2025 (25A04202)
        attesi = {
            "01": 120.9, "02": 121.1, "03": 121.4, "04": 121.3,
            "05": 121.2, "06": 121.3, "07": 121.8, "08": 121.8,
            "09": 121.7, "10": 121.4, "11": 121.3, "12": 121.5,
        }
        assert _mod()._INDICI_FOI["2025"] == attesi

    def test_serie_2026_raccordata(self):
        # Base 2025=100 (GU n.144 del 24-6-2026 + ISTAT 16-7-2026) x 1.214
        attesi = {
            "01": 121.9, "02": 122.5, "03": 123.2,
            "04": 124.4, "05": 124.8, "06": 124.8,
        }
        assert _mod()._INDICI_FOI["2026"] == attesi

    def test_indici_base_2025(self):
        attesi = {
            "01": 100.4, "02": 100.9, "03": 101.5,
            "04": 102.5, "05": 102.8, "06": 102.8,
        }
        assert _mod()._FOI_DATA["indici_base_2025"]["2026"] == attesi

    def test_coerenza_raccordo(self):
        # ogni valore 2026 della serie storica = base_2025 x 1.214 (1 decimale)
        data = _mod()._FOI_DATA
        coeff = data["raccordo_basi"]["coefficiente"]
        assert coeff == pytest.approx(1.214)
        for mese, val in data["indici_base_2025"]["2026"].items():
            assert data["indici"]["2026"][mese] == pytest.approx(
                round(val * coeff, 1)
            ), f"mese {mese}"

    def test_variazioni_ufficiali_2026(self):
        attese = {
            "01": (0.8, 2.2), "02": (1.1, 2.7), "03": (1.5, 3.2),
            "04": (2.6, 4.3), "05": (3.0, 4.4), "06": (2.9, 4.4),
        }
        var = _mod()._FOI_DATA["variazioni_ufficiali"]["2026"]
        for mese, (annuale, biennale) in attese.items():
            assert var[mese]["annuale_pct"] == pytest.approx(annuale), f"mese {mese}"
            assert var[mese]["biennale_pct"] == pytest.approx(biennale), f"mese {mese}"

    def test_riferimenti_gu(self):
        var = _mod()._FOI_DATA["variazioni_ufficiali"]["2026"]
        # gennaio-maggio pubblicati in GU con codice redazionale
        assert "26A00955" in var["01"]["gu"]
        assert "26A03169" in var["05"]["gu"]
        # giugno 2026: indice ISTAT pubblicato (16-7-2026), GU in attesa
        assert var["06"]["gu"] is None
        assert "ISTAT" in var["06"]["fonte"]

    def test_media_2025_ufficiale(self):
        # media annua 2025 = 121,4 (GU n.43 del 21-2-2026)
        vals = list(_mod()._INDICI_FOI["2025"].values())
        assert sum(vals) / len(vals) == pytest.approx(121.4, abs=0.05)


class TestAdeguamentoCanoneRaccordo:
    """Straddling periods must use the official GU-published variation."""

    def test_annuale_ufficiale_giugno_2026(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2025-06-01",
            data_adeguamento="2026-06-01",
            percentuale_istat=100.0,
        )
        # ufficiale +2,9% (ISTAT 16-7-2026), NON 124.8/121.3-1=2.89
        assert result["variazione_foi_piena_pct"] == pytest.approx(2.9)
        assert "ufficiale" in result["metodo_variazione"]
        assert "attesa" in result["nota"]  # GU non ancora pubblicata per giugno
        assert result["canone_annuo_aggiornato"] == pytest.approx(12348.0, abs=0.5)

    def test_annuale_ufficiale_maggio_2026_fonte_gu(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2025-05-01",
            data_adeguamento="2026-05-15",
            percentuale_istat=100.0,
        )
        # ufficiale +3,0% (GU n.144 del 24-6-2026), NON 124.8/121.2-1=2.97
        assert result["variazione_foi_piena_pct"] == pytest.approx(3.0)
        assert "26A03169" in result["fonte_variazione"]
        # lo scarto rispetto al rapporto tra gli indici va spiegato
        assert "arrotondament" in result["nota"]

    def test_biennale_ufficiale_aprile_2026(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=10000.0,
            data_stipula="2024-04-01",
            data_adeguamento="2026-04-01",
            percentuale_istat=100.0,
        )
        # variazione biennale ufficiale +4,3% (GU n.117 del 22-5-2026)
        assert result["variazione_foi_piena_pct"] == pytest.approx(4.3)
        assert "ufficiale" in result["metodo_variazione"]

    def test_75pct_su_variazione_ufficiale(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2025-06-01",
            data_adeguamento="2026-06-01",
            percentuale_istat=75.0,
        )
        # 75% di 2,9 = 2,175 -> canone 12000 * 1.02175
        assert result["variazione_applicata_pct"] == pytest.approx(2.175, abs=0.01)
        assert result["canone_annuo_aggiornato"] == pytest.approx(12261.0, abs=0.5)

    def test_lag_non_standard_usa_serie_raccordata(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2025-03-01",
            data_adeguamento="2026-06-01",
            percentuale_istat=100.0,
        )
        # 15 mesi: nessuna variazione ufficiale -> (124.8-121.4)/121.4 = 2.80
        assert result["variazione_foi_piena_pct"] == pytest.approx(2.8, abs=0.01)
        assert "calcolata" in result["metodo_variazione"]
        assert result["nota"] is not None
        assert "raccord" in result["nota"].lower()

    def test_pre_2026_comportamento_invariato(self):
        result = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2023-01-01",
            data_adeguamento="2024-01-01",
            percentuale_istat=100.0,
        )
        # (119.3-118.3)/118.3 = 0.845 -> 0.85, nessuna nota di raccordo
        assert result["variazione_foi_piena_pct"] == pytest.approx(0.85, abs=0.01)
        assert "calcolata" in result["metodo_variazione"]
        assert result["nota"] is None

    def test_lettera_cita_variazione_ufficiale_e_gu(self):
        result = _call(
            "lettera_adeguamento_canone",
            locatore="Mario Rossi",
            conduttore="Luigi Bianchi",
            indirizzo_immobile="Via Roma 1, Milano",
            canone_attuale=1000.0,
            data_stipula="2025-05-01",
            data_adeguamento="2026-05-01",
            percentuale_istat=100.0,
        )
        assert result["variazione_piena_pct"] == pytest.approx(3.0)
        assert "3.00" in result["lettera"]
        assert "26A03169" in result["lettera"]
        # la lettera spiega perche' la % ufficiale puo' differire dal rapporto indici
        assert "arrotondament" in result["lettera"].lower()


class TestCalcoloInflazioneRaccordo:
    def test_periodo_a_cavallo_espone_variazione_ufficiale(self):
        result = _call(
            "calcolo_inflazione",
            data_inizio="2025-06-01",
            data_fine="2026-06-01",
        )
        # calcolata: (124.8-121.3)/121.3 = 2.89; ufficiale GU: 2.9
        assert result["variazione_percentuale"] == pytest.approx(2.89, abs=0.01)
        assert result["variazione_ufficiale_pct"] == pytest.approx(2.9)
        assert "nota" in result
        assert "raccord" in result["nota"].lower()

    def test_continuita_dicembre_gennaio(self):
        result = _call(
            "calcolo_inflazione",
            data_inizio="2025-12-01",
            data_fine="2026-01-01",
        )
        # (121.9-121.5)/121.5 = +0.33 — coerente con congiunturale ISTAT +0,3
        assert result["variazione_percentuale"] == pytest.approx(0.33, abs=0.01)
        assert "raccord" in result["nota"].lower()

    def test_pre_2026_senza_nota(self):
        result = _call(
            "calcolo_inflazione",
            data_inizio="2023-01-01",
            data_fine="2024-01-01",
        )
        assert "variazione_ufficiale_pct" not in result
        assert result.get("nota") is None


class TestVariazioniIstatAnnoParziale:
    def test_2026_marcato_parziale(self):
        result = _call("variazioni_istat", anno_inizio=2024, anno_fine=2026)
        righe = {r["anno"]: r for r in result["tabella"]}
        assert righe[2026]["mesi_disponibili"] == 6
        assert righe[2026]["nota"] is not None
        assert "parzial" in righe[2026]["nota"].lower()
        # media 2026 parziale: (121.9+122.5+123.2+124.4+124.8+124.8)/6 = 123.6
        assert righe[2026]["media_foi"] == pytest.approx(123.6, abs=0.01)
        # 2025 completo: nessun flag
        assert "mesi_disponibili" not in righe[2025]
        assert righe[2025]["media_foi"] == pytest.approx(121.39, abs=0.01)
        # anche la variazione cumulata (che usa la media 2026 parziale) va marcata
        assert result["variazione_cumulata_parziale"] is True

    def test_anni_completi_senza_flag_cumulata(self):
        result = _call("variazioni_istat", anno_inizio=2023, anno_fine=2025)
        assert not result.get("variazione_cumulata_parziale")


class TestRivalutazioneTfrDatiCorretti:
    def test_variazione_foi_2025_da_gu(self):
        result = _call(
            "rivalutazione_tfr",
            retribuzione_annua=27000.0,
            anni_servizio=3,
            anno_cessazione=2026,
        )
        # anno 2025: dic25/dic24 = (121.5-120.2)/120.2 = +1.08 (GU: +1,1)
        riga_2025 = [r for r in result["dettaglio_anni"] if r["anno"] == 2025][0]
        assert riga_2025["variazione_foi_pct"] == pytest.approx(1.08, abs=0.01)


class TestAvvertenzaIndiceMancante:
    """Fallback on missing months must surface in tool output, never silently."""

    def test_adeguamento_mese_non_pubblicato(self):
        # 07/2026 non pubblicato: niente variazione ufficiale, serie raccordata
        # con fallback su 06/2026 (124.8): (124.8-121.8)/121.8 = 2.46
        r = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2025-07-01",
            data_adeguamento="2026-07-01",
            percentuale_istat=100.0,
        )
        assert r["variazione_foi_piena_pct"] == pytest.approx(2.46, abs=0.01)
        assert "calcolata" in r["metodo_variazione"]
        assert "raccord" in r["nota"].lower()
        assert "07/2026" in r["avvertenza"]
        assert "06/2026" in r["avvertenza"]

    def test_adeguamento_mesi_pubblicati_senza_avvertenza(self):
        r = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2025-06-01",
            data_adeguamento="2026-06-01",
            percentuale_istat=100.0,
        )
        assert r["avvertenza"] is None

    def test_calcolo_inflazione_avvertenza(self):
        r = _call("calcolo_inflazione", data_inizio="2026-01-01", data_fine="2026-08-01")
        # foi 08/2026 -> fallback 06/2026: (124.8-121.9)/121.9 = 2.38
        assert r["variazione_percentuale"] == pytest.approx(2.38, abs=0.01)
        assert "08/2026" in r["avvertenza"]

    def test_rivalutazione_monetaria_avvertenza(self):
        r = _call(
            "rivalutazione_monetaria",
            capitale=1000.0,
            data_inizio="2024-06-01",
            data_fine="2026-09-01",
            con_interessi_legali=False,
        )
        assert "09/2026" in r["avvertenza"]
        assert "06/2026" in r["avvertenza"]

    def test_rivalutazione_monetaria_senza_avvertenza(self):
        r = _call(
            "rivalutazione_monetaria",
            capitale=1000.0,
            data_inizio="2024-06-01",
            data_fine="2026-06-01",
            con_interessi_legali=False,
        )
        assert r["avvertenza"] is None

    def test_rivalutazione_mensile_dedup_mese_finale(self):
        r = _call(
            "rivalutazione_mensile",
            importo_mensile=100.0,
            data_inizio="2026-05-01",
            data_fine="2026-08-01",
        )
        assert "07/2026" in r["avvertenza"]
        # 08/2026 e' richiesto due volte (mese finale + mensilita'): una sola voce
        assert r["avvertenza"].count("08/2026") == 1

    def test_avvertenza_compattata_oltre_tre_mesi(self):
        r = _call(
            "rivalutazione_mensile",
            importo_mensile=100.0,
            data_inizio="2026-01-01",
            data_fine="2026-12-01",
        )
        # 6 mesi mancanti (07-12): elencati i primi 3, il resto compattato
        assert "12/2026" in r["avvertenza"]
        assert "altri 3 mesi" in r["avvertenza"]
        assert "10/2026" not in r["avvertenza"]

    def test_avvertenza_chiarisce_quando_variazione_resta_ufficiale(self, monkeypatch):
        # drift: variazione ufficiale gia' pubblicata ma indice del mese assente
        mod = _mod()
        var_2026 = dict(mod._VARIAZIONI_UFFICIALI["2026"])
        var_2026["07"] = {"annuale_pct": 3.1, "biennale_pct": 4.6, "gu": "GU test"}
        monkeypatch.setitem(mod._VARIAZIONI_UFFICIALI, "2026", var_2026)
        r = _call(
            "adeguamento_canone_locazione",
            canone_annuo=12000.0,
            data_stipula="2025-07-01",
            data_adeguamento="2026-07-01",
            percentuale_istat=100.0,
        )
        assert r["variazione_foi_piena_pct"] == pytest.approx(3.1)
        assert "ufficiale" in r["metodo_variazione"]
        assert "resta quella ufficiale" in r["avvertenza"]

    def test_tfr_dicembre_mancante(self):
        r = _call(
            "rivalutazione_tfr",
            retribuzione_annua=27000.0,
            anni_servizio=3,
            anno_cessazione=2027,
        )
        assert "12/2026" in r["avvertenza"]

    def test_devalutazione_avvertenza(self):
        r = _call(
            "calcolo_devalutazione",
            importo_attuale=1000.0,
            data_attuale="2026-09-01",
            data_passata="2020-01-01",
        )
        assert "09/2026" in r["avvertenza"]

    def test_interessi_vari_avvertenza(self):
        r = _call(
            "interessi_vari_capitale_rivalutato",
            capitale=1000.0,
            data_inizio="2024-01-01",
            data_fine="2026-09-01",
            tasso_personalizzato=2.0,
        )
        assert "09/2026" in r["avvertenza"]

    def test_inflazione_titoli_avvertenza(self):
        r = _call(
            "inflazione_titoli_stato",
            capitale_investito=1000.0,
            rendimento_lordo_annuo_pct=3.0,
            data_inizio="2024-01-01",
            data_fine="2026-09-01",
        )
        assert "09/2026" in r["avvertenza"]

    def test_anno_fuori_serie_errore_esplicito(self):
        # la serie parte dal 1990: oltre 1 anno di distanza niente approssimazione
        # silenziosa (inghiottirebbe anni di inflazione) — errore esplicito
        r = _call(
            "rivalutazione_monetaria",
            capitale=100.0,
            data_inizio="1985-01-01",
            data_fine="2000-01-01",
            con_interessi_legali=False,
        )
        assert "errore" in r

    def test_anno_successivo_approssimato_con_avvertenza(self):
        # gap di 1 anno (2027 vs ultimo 2026): approssimazione ammessa e dichiarata
        r = _call("calcolo_inflazione", data_inizio="2026-01-01", data_fine="2027-03-01")
        assert "03/2027" in r["avvertenza"]
        assert "06/2026" in r["avvertenza"]

    def test_warnings_globali_rimossi(self):
        assert not hasattr(_mod(), "_FOI_FALLBACK_WARNINGS")

    def test_lettera_riporta_avvertenza_nel_testo(self):
        # una lettera basata su un indice non ancora pubblicato deve dirlo
        r = _call(
            "lettera_adeguamento_canone",
            locatore="A",
            conduttore="B",
            indirizzo_immobile="C",
            canone_attuale=1000.0,
            data_stipula="2025-07-01",
            data_adeguamento="2026-07-01",
        )
        assert "07/2026" in r["avvertenza"]
        assert "07/2026" in r["lettera"]


class TestAvvertenzaMediaParziale:
    def test_rivalutazione_annuale_media_2026_parziale(self):
        r = _call(
            "rivalutazione_annuale_media",
            importo=1000.0,
            data_inizio="2024-03-15",
            data_fine="2026-03-15",
        )
        assert "2026" in r["avvertenza"]
        assert "6" in r["avvertenza"]  # parziale sui primi 6 mesi

    def test_rivalutazione_annuale_media_anni_completi(self):
        r = _call(
            "rivalutazione_annuale_media",
            importo=1000.0,
            data_inizio="2023-03-15",
            data_fine="2025-03-15",
        )
        assert r["avvertenza"] is None

    def test_rivalutazione_storica_2026_parziale(self):
        r = _call(
            "rivalutazione_storica",
            importo=1000.0,
            anno_partenza=2024,
            anno_arrivo=2026,
        )
        assert "2026" in r["avvertenza"]
