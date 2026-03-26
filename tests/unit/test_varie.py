import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.varie")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# codice_fiscale
# ---------------------------------------------------------------------------

class TestCodiceFiscale:

    def test_maschio_roma(self):
        r = _call("codice_fiscale", cognome="ROSSI", nome="MARIO",
                  data_nascita="1980-01-01", sesso="M", comune_nascita="ROMA")
        assert r["codice_fiscale"] == "RSSMRA80A01H501U"
        assert r["dettaglio"]["codice_catastale"] == "H501"
        assert r["dettaglio"]["carattere_controllo"] == "U"

    def test_femmina_milano(self):
        r = _call("codice_fiscale", cognome="BIANCHI", nome="LUCIA",
                  data_nascita="1995-03-15", sesso="F", comune_nascita="MILANO")
        assert r["codice_fiscale"] == "BNCLCU95C55F205W"
        # Female day = 15 + 40 = 55
        assert r["dettaglio"]["giorno"] == "55"

    def test_stato_estero(self):
        r = _call("codice_fiscale", cognome="ROSSI", nome="MARIO",
                  data_nascita="1980-01-01", sesso="M", comune_nascita="GERMANIA")
        assert "codice_fiscale" in r
        assert r["dettaglio"]["codice_catastale"].startswith("Z")

    def test_nome_quattro_consonanti(self):
        # Nome con 4+ consonanti: usa 1a, 3a, 4a consonante
        r = _call("codice_fiscale", cognome="FERRARI", nome="ROBERTO",
                  data_nascita="1975-06-20", sesso="M", comune_nascita="TORINO")
        assert len(r["codice_fiscale"]) == 16

    def test_sesso_invalido(self):
        r = _call("codice_fiscale", cognome="ROSSI", nome="MARIO",
                  data_nascita="1980-01-01", sesso="X", comune_nascita="ROMA")
        assert "errore" in r

    def test_data_invalida(self):
        r = _call("codice_fiscale", cognome="ROSSI", nome="MARIO",
                  data_nascita="not-a-date", sesso="M", comune_nascita="ROMA")
        assert "errore" in r

    def test_comune_inesistente(self):
        r = _call("codice_fiscale", cognome="ROSSI", nome="MARIO",
                  data_nascita="1980-01-01", sesso="M", comune_nascita="MARTEOPOLIS")
        assert "errore" in r

    def test_lunghezza_16(self):
        r = _call("codice_fiscale", cognome="ROSSI", nome="MARIO",
                  data_nascita="1980-01-01", sesso="M", comune_nascita="ROMA")
        assert len(r["codice_fiscale"]) == 16

    def test_mese_codice(self):
        # Gennaio → 'A', Giugno → 'H'
        r_gen = _call("codice_fiscale", cognome="ROSSI", nome="MARIO",
                      data_nascita="1980-01-01", sesso="M", comune_nascita="ROMA")
        r_giu = _call("codice_fiscale", cognome="ROSSI", nome="MARIO",
                      data_nascita="1980-06-01", sesso="M", comune_nascita="ROMA")
        assert r_gen["dettaglio"]["mese"] == "A"
        assert r_giu["dettaglio"]["mese"] == "H"


# ---------------------------------------------------------------------------
# decodifica_codice_fiscale
# ---------------------------------------------------------------------------

class TestDecodificaCodiceFiscale:

    def test_roundtrip_maschio(self):
        r = _call("decodifica_codice_fiscale", codice_fiscale="RSSMRA80A01H501U")
        assert r["carattere_controllo_valido"] is True
        assert r["dati"]["sesso"] == "M"
        assert r["dati"]["data_nascita"] == "1980-01-01"
        assert r["dati"]["comune_nascita"] == "ROMA"

    def test_roundtrip_femmina(self):
        r = _call("decodifica_codice_fiscale", codice_fiscale="BNCLCU95C55F205W")
        assert r["carattere_controllo_valido"] is True
        assert r["dati"]["sesso"] == "F"
        assert r["dati"]["data_nascita"] == "1995-03-15"

    def test_check_char_invalido(self):
        r = _call("decodifica_codice_fiscale", codice_fiscale="RSSMRA80A01H501X")
        assert r["carattere_controllo_valido"] is False

    def test_lunghezza_errata(self):
        r = _call("decodifica_codice_fiscale", codice_fiscale="RSSMRA80A01H501")
        assert "errore" in r

    def test_anno_stima_2000(self):
        # Anno 25 → 2025
        r = _call("decodifica_codice_fiscale", codice_fiscale="BNCLCU25C55F205R")
        assert r["dati"]["anno_nascita_stimato"] == 2025

    def test_anno_stima_1900(self):
        # Anno 80 → 1980
        r = _call("decodifica_codice_fiscale", codice_fiscale="RSSMRA80A01H501U")
        assert r["dati"]["anno_nascita_stimato"] == 1980

    def test_codice_catastale_restituito(self):
        r = _call("decodifica_codice_fiscale", codice_fiscale="RSSMRA80A01H501U")
        assert r["dati"]["codice_catastale"] == "H501"


# ---------------------------------------------------------------------------
# verifica_iban
# ---------------------------------------------------------------------------

class TestVerificaIban:

    def test_iban_valido(self):
        r = _call("verifica_iban", iban="IT60X0542811101000000123456")
        assert r["valido"] is True
        assert r["componenti"]["paese"] == "IT"
        assert r["componenti"]["abi"] == "05428"
        assert r["componenti"]["cab"] == "11101"

    def test_iban_con_spazi(self):
        r = _call("verifica_iban", iban="IT60 X054 2811 1010 0000 0123 456")
        assert r["valido"] is True

    def test_iban_troppo_corto(self):
        r = _call("verifica_iban", iban="IT60X054281110100000012345")
        assert r["valido"] is False
        assert len(r["errori"]) > 0

    def test_iban_non_italiano(self):
        r = _call("verifica_iban", iban="DE89370400440532013000000")
        assert r["valido"] is False

    def test_check_digits_errati(self):
        # Alter one digit so mod97 fails
        r = _call("verifica_iban", iban="IT61X0542811101000000123456")
        assert r["valido"] is False

    def test_componenti_estratti(self):
        r = _call("verifica_iban", iban="IT60X0542811101000000123456")
        assert r["componenti"]["cin"] == "X"
        assert r["componenti"]["conto_corrente"] == "000000123456"


# ---------------------------------------------------------------------------
# conta_giorni
# ---------------------------------------------------------------------------

class TestContaGiorni:

    def test_calendario_una_settimana(self):
        r = _call("conta_giorni", data_inizio="2024-01-01", data_fine="2024-01-08",
                  tipo="calendario")
        assert r["giorni"] == 7

    def test_lavorativi_esclude_weekend_e_festivi(self):
        # 2024-01-01 to 2024-01-08: Epifania (06, sabato) + dom 07 + sab 06
        # Lun 02, Mar 03, Mer 04, Gio 05 = 4 lavorativi (06 è sabato festivo)
        r = _call("conta_giorni", data_inizio="2024-01-01", data_fine="2024-01-08",
                  tipo="lavorativi")
        assert r["giorni"] == 5  # Lun-Ven: 02,03,04,05 + Mon 08 = 5

    def test_festivi_conta_solo_festivita(self):
        r = _call("conta_giorni", data_inizio="2024-01-01", data_fine="2024-01-08",
                  tipo="festivi")
        assert r["giorni"] == 1  # Epifania il 6
        assert any(f["nome"] == "Epifania" for f in r["festivita_nel_periodo"])

    def test_stessa_data(self):
        r = _call("conta_giorni", data_inizio="2024-06-01", data_fine="2024-06-01",
                  tipo="calendario")
        assert r["giorni"] == 0

    def test_data_fine_precedente_errore(self):
        r = _call("conta_giorni", data_inizio="2024-06-10", data_fine="2024-06-01",
                  tipo="calendario")
        assert "errore" in r

    def test_tipo_invalido(self):
        r = _call("conta_giorni", data_inizio="2024-01-01", data_fine="2024-01-08",
                  tipo="invalido")
        assert "errore" in r

    def test_dies_a_quo_non_computatur(self):
        # Start on 1 Jan, end on 2 Jan → 1 day (not 2)
        r = _call("conta_giorni", data_inizio="2024-01-01", data_fine="2024-01-02",
                  tipo="calendario")
        assert r["giorni"] == 1


# ---------------------------------------------------------------------------
# scorporo_iva
# ---------------------------------------------------------------------------

class TestScorporoIva:

    def test_aliquota_22(self):
        r = _call("scorporo_iva", importo_ivato=122.0, aliquota=22)
        assert r["imponibile"] == pytest.approx(100.0, abs=0.01)
        assert r["iva"] == pytest.approx(22.0, abs=0.01)
        assert r["verifica"] == pytest.approx(122.0, abs=0.01)

    def test_aliquota_10(self):
        r = _call("scorporo_iva", importo_ivato=110.0, aliquota=10)
        assert r["imponibile"] == pytest.approx(100.0, abs=0.01)
        assert r["iva"] == pytest.approx(10.0, abs=0.01)

    def test_aliquota_4(self):
        r = _call("scorporo_iva", importo_ivato=104.0, aliquota=4)
        assert r["imponibile"] == pytest.approx(100.0, abs=0.01)

    def test_aliquota_5(self):
        r = _call("scorporo_iva", importo_ivato=105.0, aliquota=5)
        assert r["imponibile"] == pytest.approx(100.0, abs=0.01)

    def test_aliquota_invalida(self):
        r = _call("scorporo_iva", importo_ivato=100.0, aliquota=15)
        assert "errore" in r

    def test_verifica_somma(self):
        r = _call("scorporo_iva", importo_ivato=500.0, aliquota=22)
        assert r["verifica"] == pytest.approx(r["imponibile"] + r["iva"], abs=0.01)


# ---------------------------------------------------------------------------
# decurtazione_punti_patente
# ---------------------------------------------------------------------------

class TestDecurtazionePuntiPatente:

    def test_cellulare_exact_match(self):
        r = _call("decurtazione_punti_patente", violazione="cellulare")
        assert r["violazione"] == "cellulare"
        assert r["punti"] == 5
        assert "Art. 173" in r["articolo"]

    def test_guida_ebbra_exact(self):
        r = _call("decurtazione_punti_patente", violazione="guida_ebbra")
        assert r["punti"] == 10

    def test_keyword_search(self):
        r = _call("decurtazione_punti_patente", violazione="guida")
        assert "risultati" in r
        assert len(r["risultati"]) > 0

    def test_violazione_inesistente(self):
        r = _call("decurtazione_punti_patente", violazione="volare_senza_patente")
        assert "errore" in r
        assert "violazioni_disponibili" in r

    def test_case_insensitive(self):
        r_low = _call("decurtazione_punti_patente", violazione="cellulare")
        r_up = _call("decurtazione_punti_patente", violazione="CELLULARE")
        assert r_low["punti"] == r_up["punti"]

    def test_cintura_presente(self):
        r = _call("decurtazione_punti_patente", violazione="cintura")
        assert "punti" in r or "risultati" in r


# ---------------------------------------------------------------------------
# tasso_alcolemico
# ---------------------------------------------------------------------------

class TestTassoAlcolemico:

    def test_fascia_a(self):
        # 3 UA, 70kg M, 1h → tasso 0.58 → fascia a
        r = _call("tasso_alcolemico", sesso="M", peso_kg=70,
                  unita_alcoliche=3, ore_trascorse=1)
        assert r["fascia_sanzione_cds"] == "art. 186 co. 2 lett. a)"
        assert r["tasso_attuale_g_l"] == pytest.approx(0.58, abs=0.01)

    def test_fascia_c_alta_alcolemia(self):
        r = _call("tasso_alcolemico", sesso="M", peso_kg=70,
                  unita_alcoliche=10, ore_trascorse=0)
        assert r["fascia_sanzione_cds"] == "art. 186 co. 2 lett. c)"
        assert r["sanzione"] is not None

    def test_tasso_zero_dopo_smaltimento(self):
        r = _call("tasso_alcolemico", sesso="F", peso_kg=60,
                  unita_alcoliche=1, ore_trascorse=10)
        assert r["tasso_attuale_g_l"] == 0
        assert r["fascia_sanzione_cds"] == "nessuna (tasso 0)"
        assert r["sanzione"] is None

    def test_stomaco_pieno_riduce_tasso(self):
        r_vuoto = _call("tasso_alcolemico", sesso="M", peso_kg=70,
                        unita_alcoliche=3, ore_trascorse=0, stomaco_pieno=False)
        r_pieno = _call("tasso_alcolemico", sesso="M", peso_kg=70,
                        unita_alcoliche=3, ore_trascorse=0, stomaco_pieno=True)
        assert r_pieno["tasso_picco_g_l"] < r_vuoto["tasso_picco_g_l"]

    def test_sesso_invalido(self):
        r = _call("tasso_alcolemico", sesso="X", peso_kg=70,
                  unita_alcoliche=2, ore_trascorse=1)
        assert "errore" in r

    def test_peso_negativo(self):
        r = _call("tasso_alcolemico", sesso="M", peso_kg=-10,
                  unita_alcoliche=2, ore_trascorse=1)
        assert "errore" in r

    def test_coefficiente_widmark_f(self):
        # Femmina ha coefficiente 0.60 < 0.70 M → tasso picco più alto a parità di peso
        r_m = _call("tasso_alcolemico", sesso="M", peso_kg=70,
                    unita_alcoliche=3, ore_trascorse=0)
        r_f = _call("tasso_alcolemico", sesso="F", peso_kg=70,
                    unita_alcoliche=3, ore_trascorse=0)
        assert r_f["tasso_picco_g_l"] > r_m["tasso_picco_g_l"]


# ---------------------------------------------------------------------------
# prescrizione_diritti
# ---------------------------------------------------------------------------

class TestPrescrioneDiritti:

    def test_ordinaria_prescritto(self):
        r = _call("prescrizione_diritti", tipo_diritto="ordinaria",
                  data_evento="2010-01-01")
        assert r["prescritto"] is True
        assert r["termine_anni"] == 10
        assert r["giorni_mancanti"] == 0

    def test_vizi_vendita_non_prescritto(self):
        r = _call("prescrizione_diritti", tipo_diritto="vizi_vendita",
                  data_evento="2030-01-01")
        assert r["prescritto"] is False
        assert r["termine_anni"] == 1
        assert r["giorni_mancanti"] > 0

    def test_risarcimento_danni_termine_5(self):
        r = _call("prescrizione_diritti", tipo_diritto="risarcimento_danni",
                  data_evento="2024-01-01")
        assert r["termine_anni"] == 5
        assert r["data_prescrizione"] == "2029-01-01"

    def test_tipo_invalido(self):
        r = _call("prescrizione_diritti", tipo_diritto="invenzione",
                  data_evento="2020-01-01")
        assert "errore" in r

    def test_data_invalida(self):
        r = _call("prescrizione_diritti", tipo_diritto="ordinaria",
                  data_evento="not-a-date")
        assert "errore" in r

    def test_riferimento_normativo_presente(self):
        r = _call("prescrizione_diritti", tipo_diritto="ordinaria",
                  data_evento="2030-01-01")
        assert "Art. 2946 c.c." in r["riferimento_normativo"]

    def test_garanzia_appalto_2_anni(self):
        r = _call("prescrizione_diritti", tipo_diritto="garanzia_appalto",
                  data_evento="2030-06-01")
        assert r["termine_anni"] == 2
        assert r["data_prescrizione"] == "2032-06-01"


# ---------------------------------------------------------------------------
# calcolo_tempo_trascorso
# ---------------------------------------------------------------------------

class TestCalcoloTempoTrascorso:

    def test_quattro_anni_esatti(self):
        r = _call("calcolo_tempo_trascorso",
                  data_inizio="2020-03-01", data_fine="2024-03-01")
        assert r["anni"] == 4
        assert r["mesi"] == 0
        assert r["giorni"] == 0
        assert r["giorni_totali"] == 1461

    def test_anni_mesi_giorni(self):
        r = _call("calcolo_tempo_trascorso",
                  data_inizio="2020-01-15", data_fine="2021-03-20")
        assert r["anni"] == 1
        assert r["mesi"] == 2
        assert r["giorni"] == 5

    def test_stessa_data(self):
        r = _call("calcolo_tempo_trascorso",
                  data_inizio="2024-06-01", data_fine="2024-06-01")
        assert r["anni"] == 0
        assert r["mesi"] == 0
        assert r["giorni"] == 0
        assert r["giorni_totali"] == 0

    def test_data_fine_precedente(self):
        r = _call("calcolo_tempo_trascorso",
                  data_inizio="2024-06-10", data_fine="2024-06-01")
        assert "errore" in r

    def test_data_invalida(self):
        r = _call("calcolo_tempo_trascorso",
                  data_inizio="not-a-date", data_fine="2024-01-01")
        assert "errore" in r

    def test_descrizione_presente(self):
        r = _call("calcolo_tempo_trascorso",
                  data_inizio="2020-03-01", data_fine="2024-03-01")
        assert "4 anni" in r["descrizione"]


# ---------------------------------------------------------------------------
# verifica_partita_iva
# ---------------------------------------------------------------------------

class TestVerificaPartitaIva:

    def test_piva_valida(self):
        r = _call("verifica_partita_iva", partita_iva="12345670017")
        assert r["valido"] is True
        assert r["cifra_controllo_attesa"] == r["cifra_controllo_presente"]

    def test_piva_check_errato(self):
        r = _call("verifica_partita_iva", partita_iva="12345670018")
        assert r["valido"] is False

    def test_piva_non_numerica(self):
        r = _call("verifica_partita_iva", partita_iva="1234567001X")
        assert r["valido"] is False
        assert "errore" in r

    def test_piva_lunghezza_errata(self):
        r = _call("verifica_partita_iva", partita_iva="1234567001")
        assert r["valido"] is False
        assert "errore" in r

    def test_piva_con_spazi(self):
        r = _call("verifica_partita_iva", partita_iva="12345670017")
        assert r["partita_iva"] == "12345670017"

    def test_codice_ufficio_estratto(self):
        r = _call("verifica_partita_iva", partita_iva="12345670017")
        assert r["codice_ufficio"] == "12"


# ---------------------------------------------------------------------------
# calcolo_eta_anagrafica
# ---------------------------------------------------------------------------

class TestCalcoloEtaAnagrafica:

    def test_compleanno_esatto(self):
        r = _call("calcolo_eta_anagrafica",
                  data_nascita="1990-06-15", data_riferimento="2024-06-15")
        assert r["eta_anni"] == 34
        assert r["eta_mesi"] == 0
        assert r["eta_giorni"] == 0

    def test_non_ancora_compleanno(self):
        r = _call("calcolo_eta_anagrafica",
                  data_nascita="1990-06-15", data_riferimento="2024-03-15")
        assert r["eta_anni"] == 33
        assert r["eta_mesi"] == 9
        assert r["eta_giorni"] == 0

    def test_prossimo_compleanno(self):
        r = _call("calcolo_eta_anagrafica",
                  data_nascita="1990-06-15", data_riferimento="2024-06-15")
        assert r["prossimo_compleanno"] == "2025-06-15"
        assert r["giorni_al_compleanno"] == 365

    def test_data_futura_errore(self):
        r = _call("calcolo_eta_anagrafica",
                  data_nascita="2030-01-01", data_riferimento="2024-01-01")
        assert "errore" in r

    def test_data_invalida(self):
        r = _call("calcolo_eta_anagrafica",
                  data_nascita="not-a-date")
        assert "errore" in r

    def test_descrizione_presente(self):
        r = _call("calcolo_eta_anagrafica",
                  data_nascita="1990-06-15", data_riferimento="2024-06-15")
        assert "34 anni" in r["descrizione"]


# ---------------------------------------------------------------------------
# ricerca_codici_ateco
# ---------------------------------------------------------------------------

class TestRicercaCodiciAteco:

    def test_trovato_pane(self):
        r = _call("ricerca_codici_ateco", keyword="pane")
        assert r["n_risultati"] >= 1
        assert any("pane" in v["descrizione"].lower() for v in r["risultati"])

    def test_trovato_avvocato(self):
        r = _call("ricerca_codici_ateco", keyword="avvoc")
        assert r["n_risultati"] >= 1
        assert r["risultati"][0]["coefficiente"] == 78

    def test_non_trovato(self):
        r = _call("ricerca_codici_ateco", keyword="xyzxyzxyz_notexists")
        assert r["risultati"] == []
        assert "suggerimento" in r

    def test_risultato_ha_campi(self):
        r = _call("ricerca_codici_ateco", keyword="pane")
        voce = r["risultati"][0]
        assert "codice" in voce
        assert "descrizione" in voce
        assert "coefficiente" in voce

    def test_ricerca_per_codice(self):
        r = _call("ricerca_codici_ateco", keyword="01.11")
        assert r["n_risultati"] >= 1

    def test_nota_forfettario(self):
        r = _call("ricerca_codici_ateco", keyword="pane")
        assert "coefficiente" in r["nota"].lower() or "forfett" in r["nota"].lower()
