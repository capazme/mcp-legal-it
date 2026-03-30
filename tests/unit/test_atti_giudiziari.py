"""Unit tests for src/tools/atti_giudiziari.py."""

import importlib

import pytest


def _call(fn_name, **kwargs):
    mod = importlib.import_module("src.tools.atti_giudiziari")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


# ---------------------------------------------------------------------------
# contributo_unificato
# ---------------------------------------------------------------------------


class TestContributoUnificato:

    def test_cognizione_primo_grado_scaglione_basso(self):
        r = _call("contributo_unificato", valore_causa=1000, tipo_procedimento="cognizione", grado="primo")
        assert r["importo_dovuto"] == 43
        assert r["moltiplicatore"] == 1.0

    def test_cognizione_primo_grado_scaglione_alto(self):
        # 30000 rientra nello scaglione fino_a=52000 → 518
        r = _call("contributo_unificato", valore_causa=30000, tipo_procedimento="cognizione", grado="primo")
        assert r["importo_dovuto"] == 518

    def test_monitorio_dimezzato(self):
        r = _call("contributo_unificato", valore_causa=5000, tipo_procedimento="monitorio", grado="primo")
        assert r["importo_dovuto"] == 49

    def test_esecuzione_immobiliare_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="esecuzione_immobiliare", grado="primo")
        assert r["importo_dovuto"] == 278

    def test_esecuzione_mobiliare_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="esecuzione_mobiliare", grado="primo")
        assert r["importo_dovuto"] == 43

    def test_separazione_consensuale_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="separazione_consensuale", grado="primo")
        assert r["importo_dovuto"] == 43

    def test_divorzio_giudiziale_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="divorzio_giudiziale", grado="primo")
        assert r["importo_dovuto"] == 98

    def test_cautelari_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="cautelari", grado="primo")
        assert r["importo_dovuto"] == 147

    def test_lavoro_primo_grado_esente(self):
        r = _call("contributo_unificato", valore_causa=50000, tipo_procedimento="lavoro", grado="primo")
        assert r["importo_dovuto"] == 0.0

    def test_tributario_scaglione(self):
        r = _call("contributo_unificato", valore_causa=10000, tipo_procedimento="tributario", grado="primo")
        assert r["importo_dovuto"] == 120

    def test_tar_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="tar", grado="primo")
        assert r["importo_dovuto"] == 650

    def test_appello_moltiplicatore(self):
        # 30000 → scaglione 518, appello × 1.5 = 777
        r = _call("contributo_unificato", valore_causa=30000, tipo_procedimento="cognizione", grado="appello")
        assert r["moltiplicatore"] == 1.5
        assert r["importo_dovuto"] == pytest.approx(518 * 1.5, abs=0.01)

    def test_cassazione_raddoppio(self):
        # 30000 → scaglione 518, cassazione × 2.0 = 1036
        r = _call("contributo_unificato", valore_causa=30000, tipo_procedimento="cognizione", grado="cassazione")
        assert r["moltiplicatore"] == 2.0
        assert r["importo_dovuto"] == pytest.approx(518 * 2.0, abs=0.01)

    def test_lavoro_appello_fascia_zero(self):
        r = _call("contributo_unificato", valore_causa=2000, tipo_procedimento="lavoro", grado="appello")
        assert r["importo_dovuto"] == 0

    def test_lavoro_appello_fascia_media(self):
        r = _call("contributo_unificato", valore_causa=10000, tipo_procedimento="lavoro", grado="appello")
        assert r["importo_dovuto"] == 112.5

    def test_lavoro_appello_fascia_alta(self):
        r = _call("contributo_unificato", valore_causa=100000, tipo_procedimento="lavoro", grado="appello")
        assert r["importo_dovuto"] == 225

    def test_returns_normativo(self):
        r = _call("contributo_unificato", valore_causa=5000, tipo_procedimento="cognizione", grado="primo")
        assert "DPR 115/2002" in r["riferimento_normativo"]

    def test_oltre_soglia_massima(self):
        r = _call("contributo_unificato", valore_causa=1_000_000, tipo_procedimento="cognizione", grado="primo")
        assert r["importo_dovuto"] == 1686


# ---------------------------------------------------------------------------
# diritti_copia
# ---------------------------------------------------------------------------


class TestDirittiCopia:

    def test_digitale_semplice_gratuita(self):
        r = _call("diritti_copia", n_pagine=10, tipo="semplice", formato="digitale")
        assert r["totale"] == 0.0

    def test_digitale_autentica_fascia_4_pagine(self):
        r = _call("diritti_copia", n_pagine=4, tipo="autentica", formato="digitale")
        assert r["totale"] == 1.62

    def test_digitale_autentica_fascia_10_pagine(self):
        r = _call("diritti_copia", n_pagine=10, tipo="autentica", formato="digitale")
        assert r["totale"] == 4.05

    def test_digitale_autentica_fascia_20_pagine(self):
        r = _call("diritti_copia", n_pagine=20, tipo="autentica", formato="digitale")
        assert r["totale"] == 6.48

    def test_digitale_autentica_fascia_50_pagine(self):
        r = _call("diritti_copia", n_pagine=50, tipo="autentica", formato="digitale")
        assert r["totale"] == 8.11

    def test_digitale_autentica_oltre_50(self):
        r = _call("diritti_copia", n_pagine=100, tipo="autentica", formato="digitale")
        assert r["totale"] == pytest.approx(10.13 + 1 * 1.62, abs=0.01)

    def test_cartaceo_semplice(self):
        r = _call("diritti_copia", n_pagine=10, tipo="semplice", formato="cartaceo")
        assert r["totale"] == pytest.approx(10 * 0.30, abs=0.01)

    def test_cartaceo_autentica(self):
        r = _call("diritti_copia", n_pagine=5, tipo="autentica", formato="cartaceo")
        assert r["totale"] == pytest.approx(5 * 0.70, abs=0.01)

    def test_cartaceo_urgente_maggiorazione(self):
        r = _call("diritti_copia", n_pagine=10, tipo="semplice", formato="cartaceo", urgente=True)
        subtotale = 10 * 0.30
        assert r["totale"] == pytest.approx(subtotale * 1.5, abs=0.01)
        assert "maggiorazione_urgenza" in r

    def test_formato_non_valido(self):
        r = _call("diritti_copia", n_pagine=10, tipo="semplice", formato="fax")
        assert "errore" in r

    def test_tipo_non_valido(self):
        r = _call("diritti_copia", n_pagine=10, tipo="notarile", formato="cartaceo")
        assert "errore" in r

    def test_esecutiva_digitale(self):
        r = _call("diritti_copia", n_pagine=8, tipo="esecutiva", formato="digitale")
        assert r["totale"] == 4.05


# ---------------------------------------------------------------------------
# pignoramento_stipendio
# ---------------------------------------------------------------------------


class TestPignoramentoStipendio:

    def test_ordinario_un_quinto(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, tipo_credito="ordinario")
        assert r["importo_pignorabile"] == pytest.approx(400.0, abs=0.01)
        assert r["quota_pignorabile"] == pytest.approx(0.2, abs=0.0001)

    def test_alimentare_un_terzo(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=3000, tipo_credito="alimentare")
        assert r["importo_pignorabile"] == pytest.approx(1000.0, abs=0.01)

    def test_fiscale_scaglione_basso(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, tipo_credito="fiscale")
        assert r["importo_pignorabile"] == pytest.approx(200.0, abs=0.01)
        assert "1/10" in r["descrizione"]

    def test_fiscale_scaglione_medio(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=3500, tipo_credito="fiscale")
        assert r["importo_pignorabile"] == pytest.approx(3500 / 7, abs=0.01)
        assert "1/7" in r["descrizione"]

    def test_fiscale_scaglione_alto(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=6000, tipo_credito="fiscale")
        assert r["importo_pignorabile"] == pytest.approx(6000 / 5, abs=0.01)
        assert "1/5" in r["descrizione"]

    def test_concorso_crediti_meta(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=4000, tipo_credito="concorso_crediti")
        assert r["importo_pignorabile"] == pytest.approx(2000.0, abs=0.01)

    def test_non_pignorabile_complementare(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, tipo_credito="ordinario")
        assert r["importo_non_pignorabile"] == pytest.approx(1600.0, abs=0.01)

    def test_tipo_invalido(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, tipo_credito="speciale")
        assert "errore" in r

    def test_contiene_minimo_vitale(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=1000, tipo_credito="ordinario")
        assert "minimo_vitale_pensioni" in r
        assert r["minimo_vitale_pensioni"] == 534.41


# ---------------------------------------------------------------------------
# sollecito_pagamento
# ---------------------------------------------------------------------------


class TestSollecitoPagemento:

    def test_genera_testo(self):
        r = _call(
            "sollecito_pagamento",
            creditore="Rossi SRL",
            debitore="Bianchi SPA",
            importo=5000.0,
            data_scadenza="2024-01-01",
            data_sollecito="2024-04-01",
            tasso_mora=10.0,
        )
        assert "testo_lettera" in r
        assert "Bianchi SPA" in r["testo_lettera"]
        assert "Rossi SRL" in r["testo_lettera"]

    def test_calcoli_interessi_tasso_personalizzato(self):
        r = _call(
            "sollecito_pagamento",
            creditore="A",
            debitore="B",
            importo=10000.0,
            data_scadenza="2024-01-01",
            data_sollecito="2024-07-01",
            tasso_mora=10.0,
        )
        interessi = r["calcoli"]["interessi_mora"]
        assert interessi > 0
        assert r["calcoli"]["totale_dovuto"] == pytest.approx(10000 + interessi, abs=0.01)

    def test_tasso_mora_default(self):
        r = _call(
            "sollecito_pagamento",
            creditore="A",
            debitore="B",
            importo=1000.0,
            data_scadenza="2024-01-01",
            data_sollecito="2024-04-01",
        )
        assert r["calcoli"]["interessi_mora"] > 0
        assert r["calcoli"]["giorni_ritardo"] == 91

    def test_data_non_successiva_errore(self):
        r = _call(
            "sollecito_pagamento",
            creditore="A",
            debitore="B",
            importo=1000.0,
            data_scadenza="2024-06-01",
            data_sollecito="2024-01-01",
        )
        assert "errore" in r

    def test_stessa_data_errore(self):
        r = _call(
            "sollecito_pagamento",
            creditore="A",
            debitore="B",
            importo=1000.0,
            data_scadenza="2024-01-01",
            data_sollecito="2024-01-01",
        )
        assert "errore" in r


# ---------------------------------------------------------------------------
# decreto_ingiuntivo
# ---------------------------------------------------------------------------


class TestDecretoIngiuntivo:

    def test_importo_basso_giudice_pace(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000)
        assert r["riepilogo"]["giudice_competente"] == "Giudice di Pace"

    def test_importo_alto_tribunale(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=50000)
        assert r["riepilogo"]["giudice_competente"] == "Tribunale"

    def test_contributo_unificato_presente(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000)
        assert r["riepilogo"]["contributo_unificato"] > 0

    def test_provvisoria_esecuzione_professionale(self):
        r = _call(
            "decreto_ingiuntivo",
            creditore="A",
            debitore="B",
            importo=5000,
            tipo_credito="professionale",
            provvisoria_esecuzione=True,
        )
        assert r["riepilogo"]["provvisoria_esecuzione"] is True
        assert len(r["riepilogo"]["motivi_pe"]) == 1
        assert "parcella" in r["riepilogo"]["motivi_pe"][0]

    def test_provvisoria_esecuzione_cambiale(self):
        r = _call(
            "decreto_ingiuntivo",
            creditore="A",
            debitore="B",
            importo=5000,
            tipo_credito="cambiale",
            provvisoria_esecuzione=True,
        )
        assert "cambiale" in r["riepilogo"]["motivi_pe"][0]

    def test_senza_pe_motivi_none(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000)
        assert r["riepilogo"]["motivi_pe"] is None

    def test_bozza_contiene_importo(self):
        r = _call("decreto_ingiuntivo", creditore="Creditor SRL", debitore="Debtor SPA", importo=12345.67)
        # Python {:,.2f} usa separatore US: "12,345.67"
        assert "12,345.67" in r["bozza_ricorso"]

    def test_condominiale_pe_motivo(self):
        r = _call(
            "decreto_ingiuntivo",
            creditore="Condominio",
            debitore="B",
            importo=3000,
            tipo_credito="condominiale",
            provvisoria_esecuzione=True,
        )
        assert "delibera" in r["riepilogo"]["motivi_pe"][0]


# ---------------------------------------------------------------------------
# calcolo_hash
# ---------------------------------------------------------------------------


class TestCalcoloHash:

    def test_deterministico(self):
        r1 = _call("calcolo_hash", testo="ciao")
        r2 = _call("calcolo_hash", testo="ciao")
        assert r1["hash"] == r2["hash"]

    def test_sha256_noto(self):
        r = _call("calcolo_hash", testo="abc")
        assert r["hash"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        assert r["algoritmo"] == "SHA-256"

    def test_lunghezza_input(self):
        testo = "hello world"
        r = _call("calcolo_hash", testo=testo)
        assert r["lunghezza_input"] == len(testo)

    def test_hash_diverso_per_testi_diversi(self):
        r1 = _call("calcolo_hash", testo="documento1")
        r2 = _call("calcolo_hash", testo="documento2")
        assert r1["hash"] != r2["hash"]


# ---------------------------------------------------------------------------
# tassazione_atti
# ---------------------------------------------------------------------------


class TestTassazioneAtti:

    def test_sentenza_condanna_proporzionale(self):
        r = _call("tassazione_atti", tipo_atto="sentenza_condanna", valore=10000)
        assert r["imposta_registro"] == pytest.approx(300.0, abs=0.01)
        assert r["aliquota_pct"] == 3.0

    def test_sentenza_condanna_minimo(self):
        r = _call("tassazione_atti", tipo_atto="sentenza_condanna", valore=100)
        assert r["imposta_registro"] == 200.0

    def test_sentenza_condanna_valore_zero(self):
        r = _call("tassazione_atti", tipo_atto="sentenza_condanna", valore=0)
        assert r["imposta_registro"] == 200.0
        assert r["aliquota_pct"] == 0

    def test_decreto_ingiuntivo_3pct(self):
        r = _call("tassazione_atti", tipo_atto="decreto_ingiuntivo", valore=20000)
        assert r["imposta_registro"] == pytest.approx(600.0, abs=0.01)

    def test_verbale_conciliazione_ordinario(self):
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=10000)
        assert r["imposta_registro"] == pytest.approx(300.0, abs=0.01)

    def test_verbale_conciliazione_prima_casa(self):
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=100000, prima_casa=True)
        assert r["aliquota_pct"] == 2.0
        assert r["imposta_registro"] == pytest.approx(2000.0, abs=0.01)

    def test_verbale_conciliazione_prima_casa_minimo(self):
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=100, prima_casa=True)
        assert r["imposta_registro"] == 1000.0

    def test_ordinanza_fissa(self):
        r = _call("tassazione_atti", tipo_atto="ordinanza", valore=999999)
        assert r["imposta_registro"] == 200.0
        assert r["aliquota_pct"] == 0

    def test_tipo_invalido(self):
        r = _call("tassazione_atti", tipo_atto="inesistente", valore=1000)
        assert "errore" in r


# ---------------------------------------------------------------------------
# copie_processo_tributario
# ---------------------------------------------------------------------------


class TestCopieProcessoTributario:

    def test_semplice(self):
        r = _call("copie_processo_tributario", n_pagine=10, tipo="semplice")
        assert r["totale"] == pytest.approx(10 * 0.25, abs=0.01)

    def test_autentica(self):
        r = _call("copie_processo_tributario", n_pagine=10, tipo="autentica")
        assert r["totale"] == pytest.approx(10 * 0.50, abs=0.01)

    def test_urgente_maggiorazione(self):
        r = _call("copie_processo_tributario", n_pagine=10, tipo="semplice", urgente=True)
        assert r["totale"] == pytest.approx(10 * 0.25 * 1.5, abs=0.01)
        assert "maggiorazione_urgenza" in r

    def test_urgente_importo_maggiorazione(self):
        r = _call("copie_processo_tributario", n_pagine=20, tipo="autentica", urgente=True)
        expected_sub = 20 * 0.50
        assert r["maggiorazione_urgenza"] == pytest.approx(expected_sub * 0.5, abs=0.01)

    def test_non_urgente_no_maggiorazione_key(self):
        r = _call("copie_processo_tributario", n_pagine=10, tipo="semplice", urgente=False)
        assert "maggiorazione_urgenza" not in r


# ---------------------------------------------------------------------------
# note_iscrizione_ruolo
# ---------------------------------------------------------------------------


class TestNoteIscrizioneRuolo:

    def test_cognizione_ordinaria(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="cognizione_ordinaria", valore_causa=5000)
        assert r["contributo_unificato"] > 0
        assert r["tipo_procedimento"] == "cognizione_ordinaria"

    def test_monitorio_cu(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="monitorio", valore_causa=5000)
        assert r["contributo_unificato"] == 49

    def test_lavoro_cu_zero(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="lavoro", valore_causa=10000)
        assert r["contributo_unificato"] == 0.0

    def test_locazione_ha_codici(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="locazione", valore_causa=5000)
        assert isinstance(r["codici_oggetto_suggeriti"], list)

    def test_senza_valore_non_crasha(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="cognizione_ordinaria")
        assert "contributo_unificato" in r


# ---------------------------------------------------------------------------
# codici_iscrizione_ruolo
# ---------------------------------------------------------------------------


class TestCodiciIscrizioneRuolo:

    def test_contratto_restituisce_risultati(self):
        r = _call("codici_iscrizione_ruolo", materia="contratto")
        assert r["totale"] > 0
        assert len(r["risultati"]) > 0

    def test_keyword_case_insensitive(self):
        r_lower = _call("codici_iscrizione_ruolo", materia="contratto")
        r_upper = _call("codici_iscrizione_ruolo", materia="CONTRATTO")
        assert r_lower["totale"] == r_upper["totale"]

    def test_materia_inesistente(self):
        r = _call("codici_iscrizione_ruolo", materia="xyznonexistent999")
        assert r["totale"] == 0
        assert r["risultati"] == []

    def test_risultati_hanno_codice(self):
        r = _call("codici_iscrizione_ruolo", materia="locazione")
        if r["totale"] > 0:
            assert "codice" in r["risultati"][0]


# ---------------------------------------------------------------------------
# fascicolo_di_parte
# ---------------------------------------------------------------------------


class TestFascicoloDiParte:

    def test_contiene_parti(self):
        r = _call(
            "fascicolo_di_parte",
            avvocato="Mario Rossi",
            parte="Tizio",
            controparte="Caio",
            tribunale="Tribunale di Milano",
        )
        assert "TIZIO" in r["testo"]
        assert "CAIO" in r["testo"]
        assert "TRIBUNALE DI MILANO" in r["testo"]

    def test_con_rg_numero(self):
        r = _call(
            "fascicolo_di_parte",
            avvocato="Mario Rossi",
            parte="Tizio",
            controparte="Caio",
            tribunale="Tribunale di Roma",
            rg_numero="1234/2025",
        )
        assert "R.G. n. 1234/2025" in r["testo"]

    def test_senza_rg_placeholder(self):
        r = _call(
            "fascicolo_di_parte",
            avvocato="Mario Rossi",
            parte="Tizio",
            controparte="Caio",
            tribunale="Tribunale di Roma",
        )
        assert "R.G. n. ___/____" in r["testo"]

    def test_tipo_atto(self):
        r = _call(
            "fascicolo_di_parte",
            avvocato="A",
            parte="B",
            controparte="C",
            tribunale="T",
        )
        assert r["tipo_atto"] == "fascicolo_di_parte"


# ---------------------------------------------------------------------------
# procura_alle_liti
# ---------------------------------------------------------------------------


class TestProcuraAlleLiti:

    def test_generale_intestazione(self):
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi",
            avvocato="Avv. Luigi Bianchi",
            cf_avvocato="BNCLLG80A01H501X",
            foro="Milano",
            oggetto_causa="risarcimento danni",
        )
        assert "PROCURA ALLE LITI" in r["testo"]
        assert r["tipo_procura"] == "generale"

    def test_speciale_intestazione(self):
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi",
            avvocato="Avv. Luigi Bianchi",
            cf_avvocato="BNCLLG80A01H501X",
            foro="Milano",
            oggetto_causa="risarcimento danni",
            tipo="speciale",
        )
        assert "PROCURA SPECIALE ALLE LITI" in r["testo"]
        assert r["tipo_procura"] == "speciale"

    def test_appello_intestazione(self):
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi",
            avvocato="Avv. Luigi Bianchi",
            cf_avvocato="BNCLLG80A01H501X",
            foro="Milano",
            oggetto_causa="appello causa civile",
            tipo="appello",
        )
        assert "APPELLO" in r["testo"]

    def test_contiene_gdpr(self):
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi",
            avvocato="Avv. Luigi Bianchi",
            cf_avvocato="BNCLLG80A01H501X",
            foro="Roma",
            oggetto_causa="recupero credito",
        )
        assert "GDPR" in r["testo"] or "2016/679" in r["testo"]

    def test_contiene_avvocato(self):
        r = _call(
            "procura_alle_liti",
            parte="Sig. Tizio",
            avvocato="Avv. Caio Verde",
            cf_avvocato="CF123456",
            foro="Napoli",
            oggetto_causa="locazione",
        )
        assert "Avv. Caio Verde" in r["testo"]
        assert "Napoli" in r["testo"]


# ---------------------------------------------------------------------------
# attestazione_conformita
# ---------------------------------------------------------------------------


class TestAttestazioneDiConformita:

    def test_estratto_default(self):
        r = _call(
            "attestazione_conformita",
            avvocato="Mario Rossi",
            tipo_documento="verbale di causa",
            estremi_originale="R.G. 1234/2024, pag. 1-3",
        )
        assert "ATTESTAZIONE DI CONFORMITA'" in r["testo"]
        assert r["modalita"] == "estratto"

    def test_copia_informatica(self):
        r = _call(
            "attestazione_conformita",
            avvocato="Mario Rossi",
            tipo_documento="sentenza",
            estremi_originale="Trib. Milano n. 100/2024",
            modalita="copia_informatica",
        )
        assert "analogico" in r["testo"]
        assert r["modalita"] == "copia_informatica"

    def test_duplicato(self):
        r = _call(
            "attestazione_conformita",
            avvocato="Mario Rossi",
            tipo_documento="atto notarile",
            estremi_originale="Rep. 500/2024",
            modalita="duplicato",
        )
        assert "duplicato informatico" in r["testo"]

    def test_contiene_avvocato(self):
        r = _call(
            "attestazione_conformita",
            avvocato="Avv. Anna Neri",
            tipo_documento="doc",
            estremi_originale="R.G. 1/2024",
        )
        assert "Avv. Anna Neri" in r["testo"]


# ---------------------------------------------------------------------------
# relata_notifica_pec
# ---------------------------------------------------------------------------


class TestRelataNoficaPec:

    def test_genera_testo(self):
        r = _call(
            "relata_notifica_pec",
            avvocato="Mario Rossi",
            destinatario="Bianchi SPA",
            pec_destinatario="bianchi@pec.it",
            atto_notificato="ricorso per decreto ingiuntivo",
            data_invio="2024-03-15",
        )
        assert "RELATA DI NOTIFICAZIONE" in r["testo"]
        assert "bianchi@pec.it" in r["testo"]

    def test_data_formattata(self):
        r = _call(
            "relata_notifica_pec",
            avvocato="A",
            destinatario="B",
            pec_destinatario="b@pec.it",
            atto_notificato="atto",
            data_invio="2024-06-01",
        )
        assert "01/06/2024" in r["testo"]

    def test_campi_risultato(self):
        r = _call(
            "relata_notifica_pec",
            avvocato="A",
            destinatario="Dest",
            pec_destinatario="d@pec.it",
            atto_notificato="atto",
            data_invio="2024-01-01",
        )
        assert r["tipo_atto"] == "relata_notifica_pec"
        assert r["pec_destinatario"] == "d@pec.it"
        assert r["destinatario"] == "Dest"


# ---------------------------------------------------------------------------
# indice_documenti
# ---------------------------------------------------------------------------


class TestIndiceDocumenti:

    def test_base(self):
        docs = [
            {"numero": 1, "descrizione": "Contratto", "pagine": 5},
            {"numero": 2, "descrizione": "Fattura", "pagine": 3},
        ]
        r = _call("indice_documenti", documenti=docs)
        assert r["totale_documenti"] == 2
        assert r["totale_pagine"] == 8

    def test_testo_contiene_descrizioni(self):
        docs = [{"numero": 1, "descrizione": "Verbale assemblea", "pagine": 2}]
        r = _call("indice_documenti", documenti=docs)
        assert "Verbale assemblea" in r["testo"]

    def test_lista_vuota(self):
        r = _call("indice_documenti", documenti=[])
        assert r["totale_documenti"] == 0
        assert r["totale_pagine"] == 0

    def test_tipo_atto(self):
        r = _call("indice_documenti", documenti=[])
        assert r["tipo_atto"] == "indice_documenti"


# ---------------------------------------------------------------------------
# note_trattazione_scritta
# ---------------------------------------------------------------------------


class TestNoteTrattazioneScritta:

    def test_genera_bozza(self):
        r = _call(
            "note_trattazione_scritta",
            avvocato="Mario Rossi",
            parte="Tizio",
            tribunale="Tribunale di Milano",
            rg_numero="1234/2025",
            giudice="Dott. Verdi",
            conclusioni="Si chiede il rigetto.",
        )
        assert "NOTE DI TRATTAZIONE SCRITTA" in r["testo"]
        assert "127-ter" in r["testo"]

    def test_contiene_conclusioni(self):
        r = _call(
            "note_trattazione_scritta",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="10/2025",
            giudice="G",
            conclusioni="Piaccia al Tribunale accogliere la domanda.",
        )
        assert "Piaccia al Tribunale accogliere la domanda." in r["testo"]

    def test_rg_numero_in_risposta(self):
        r = _call(
            "note_trattazione_scritta",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="999/2024",
            giudice="G",
            conclusioni="Conclusioni.",
        )
        assert r["rg_numero"] == "999/2024"
        assert "999/2024" in r["testo"]

    def test_tribunale_uppercase_in_testo(self):
        r = _call(
            "note_trattazione_scritta",
            avvocato="A",
            parte="B",
            tribunale="tribunale di roma",
            rg_numero="1/2025",
            giudice="G",
            conclusioni="ok",
        )
        assert "TRIBUNALE DI ROMA" in r["testo"]


# ---------------------------------------------------------------------------
# sfratto_morosita
# ---------------------------------------------------------------------------


class TestSfrattoMorosita:

    def test_totale_dovuto(self):
        r = _call(
            "sfratto_morosita",
            locatore="Luigi Rossi",
            conduttore="Mario Bianchi",
            immobile="Via Roma 1, Milano",
            canone_mensile=800.0,
            mensilita_insolute=3,
            data_contratto="2020-01-15",
        )
        assert r["totale_dovuto"] == pytest.approx(2400.0, abs=0.01)

    def test_dati_nel_testo(self):
        r = _call(
            "sfratto_morosita",
            locatore="Luigi Rossi",
            conduttore="Mario Bianchi",
            immobile="Via Verdi 10",
            canone_mensile=600.0,
            mensilita_insolute=2,
            data_contratto="2021-06-01",
        )
        assert "Mario Bianchi" in r["testo"]
        assert "Luigi Rossi" in r["testo"]

    def test_data_contratto_formattata(self):
        r = _call(
            "sfratto_morosita",
            locatore="A",
            conduttore="B",
            immobile="C",
            canone_mensile=500.0,
            mensilita_insolute=1,
            data_contratto="2022-03-10",
        )
        assert "10/03/2022" in r["testo"]

    def test_tipo_atto(self):
        r = _call(
            "sfratto_morosita",
            locatore="A",
            conduttore="B",
            immobile="C",
            canone_mensile=500.0,
            mensilita_insolute=1,
            data_contratto="2022-01-01",
        )
        assert r["tipo_atto"] == "sfratto_morosita"


# ---------------------------------------------------------------------------
# atto_di_precetto
# ---------------------------------------------------------------------------


class TestAttoDiPrecetto:

    def test_totale_calcolato(self):
        r = _call(
            "atto_di_precetto",
            creditore="Banca X",
            debitore="Mario Rossi",
            titolo_esecutivo="Sentenza Trib. Milano n. 100/2024",
            importo_capitale=10000.0,
            interessi=500.0,
            spese=200.0,
        )
        assert r["totale_intimato"] == pytest.approx(10700.0, abs=0.01)

    def test_testo_contiene_totale(self):
        r = _call(
            "atto_di_precetto",
            creditore="A",
            debitore="B",
            titolo_esecutivo="Decreto ingiuntivo n. 50/2024",
            importo_capitale=5000.0,
            interessi=100.0,
            spese=50.0,
        )
        # Python {:,.2f} usa separatore US: "5,150.00"
        assert "5,150.00" in r["testo"]

    def test_solo_capitale_senza_accessori(self):
        r = _call(
            "atto_di_precetto",
            creditore="A",
            debitore="B",
            titolo_esecutivo="Sent. n. 1/2024",
            importo_capitale=3000.0,
        )
        assert r["totale_intimato"] == 3000.0

    def test_tipo_atto(self):
        r = _call(
            "atto_di_precetto",
            creditore="A",
            debitore="B",
            titolo_esecutivo="T",
            importo_capitale=1000.0,
        )
        assert r["tipo_atto"] == "atto_di_precetto"


# ---------------------------------------------------------------------------
# nota_precisazione_credito
# ---------------------------------------------------------------------------


class TestNotaPrecisazioneCredito:

    def test_totale_sommato(self):
        r = _call(
            "nota_precisazione_credito",
            creditore="Banca Y",
            debitore="Sig. X",
            procedura_esecutiva="R.G.E. 100/2024",
            capitale=8000.0,
            interessi=400.0,
            spese_legali=300.0,
            spese_esecuzione=100.0,
        )
        assert r["totale_credito"] == pytest.approx(8800.0, abs=0.01)

    def test_testo_contiene_procedura(self):
        r = _call(
            "nota_precisazione_credito",
            creditore="A",
            debitore="B",
            procedura_esecutiva="R.G.E. 999/2024",
            capitale=1000.0,
            interessi=0.0,
            spese_legali=0.0,
            spese_esecuzione=0.0,
        )
        assert "R.G.E. 999/2024" in r["testo"]

    def test_tipo_atto(self):
        r = _call(
            "nota_precisazione_credito",
            creditore="A",
            debitore="B",
            procedura_esecutiva="R.G.E. 1/2024",
            capitale=100.0,
            interessi=0.0,
            spese_legali=0.0,
            spese_esecuzione=0.0,
        )
        assert r["tipo_atto"] == "nota_precisazione_credito"

    def test_zero_accessori(self):
        r = _call(
            "nota_precisazione_credito",
            creditore="A",
            debitore="B",
            procedura_esecutiva="R.G.E. 1/2024",
            capitale=5000.0,
            interessi=0.0,
            spese_legali=0.0,
            spese_esecuzione=0.0,
        )
        assert r["totale_credito"] == 5000.0


# ---------------------------------------------------------------------------
# dichiarazione_553_cpc
# ---------------------------------------------------------------------------


class TestDichiarazione553Cpc:

    def test_conto_corrente_default(self):
        r = _call(
            "dichiarazione_553_cpc",
            terzo_pignorato="Banca ABC",
            debitore="Mario Rossi",
            procedura="R.G.E. 200/2024",
        )
        assert r["tipo_rapporto"] == "conto_corrente"
        assert "Conto corrente" in r["testo"]

    def test_stipendio(self):
        r = _call(
            "dichiarazione_553_cpc",
            terzo_pignorato="Azienda SRL",
            debitore="Mario Rossi",
            procedura="R.G.E. 200/2024",
            tipo_rapporto="stipendio",
        )
        assert "dipendente" in r["testo"]
        assert r["tipo_rapporto"] == "stipendio"

    def test_altro(self):
        r = _call(
            "dichiarazione_553_cpc",
            terzo_pignorato="Terzo",
            debitore="Debitore",
            procedura="R.G.E. 300/2024",
            tipo_rapporto="altro",
        )
        assert r["tipo_rapporto"] == "altro"

    def test_contiene_procedura(self):
        r = _call(
            "dichiarazione_553_cpc",
            terzo_pignorato="Banca",
            debitore="Sig.",
            procedura="R.G.E. 555/2025",
        )
        assert "R.G.E. 555/2025" in r["testo"]


# ---------------------------------------------------------------------------
# testimonianza_scritta
# ---------------------------------------------------------------------------


class TestTestimonianzaScritta:

    def test_numero_capitoli(self):
        r = _call(
            "testimonianza_scritta",
            teste="Giovanni Verdi",
            capitoli_prova=["Il 01/01/2024 ero presente.", "Ho firmato il contratto."],
        )
        assert r["numero_capitoli"] == 2

    def test_testo_contiene_teste(self):
        r = _call(
            "testimonianza_scritta",
            teste="Anna Bianchi",
            capitoli_prova=["Capitolo di prova."],
        )
        assert "Anna Bianchi" in r["testo"]

    def test_capitoli_nel_testo(self):
        r = _call(
            "testimonianza_scritta",
            teste="T",
            capitoli_prova=["Il teste era presente alle ore 10."],
        )
        assert "Il teste era presente alle ore 10." in r["testo"]

    def test_tipo_atto(self):
        r = _call(
            "testimonianza_scritta",
            teste="T",
            capitoli_prova=[],
        )
        assert r["tipo_atto"] == "testimonianza_scritta"

    def test_lista_vuota_capitoli(self):
        r = _call(
            "testimonianza_scritta",
            teste="T",
            capitoli_prova=[],
        )
        assert r["numero_capitoli"] == 0


# ---------------------------------------------------------------------------
# istanza_visibilita_fascicolo
# ---------------------------------------------------------------------------


class TestIstanzaVisibilitaFascicolo:

    def test_costituzione_default(self):
        r = _call(
            "istanza_visibilita_fascicolo",
            avvocato="Mario Rossi",
            parte="Tizio",
            tribunale="Tribunale di Milano",
            rg_numero="1234/2025",
        )
        assert r["motivo"] == "costituzione"
        assert "1234/2025" in r["testo"]

    def test_consultazione(self):
        r = _call(
            "istanza_visibilita_fascicolo",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="10/2024",
            motivo="consultazione",
        )
        assert r["motivo"] == "consultazione"

    def test_intervento(self):
        r = _call(
            "istanza_visibilita_fascicolo",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="10/2024",
            motivo="intervento",
        )
        assert "art. 105 c.p.c." in r["testo"]

    def test_rg_in_testo(self):
        r = _call(
            "istanza_visibilita_fascicolo",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="777/2025",
        )
        assert "777/2025" in r["testo"]


# ---------------------------------------------------------------------------
# cerca_ufficio_giudiziario
# ---------------------------------------------------------------------------


class TestCercaUfficioGiudiziario:

    def test_roma_trovato(self):
        r = _call("cerca_ufficio_giudiziario", comune="Roma")
        assert r["trovato"] is True
        assert "Roma" in r["ufficio_competente"]

    def test_milano_trovato(self):
        r = _call("cerca_ufficio_giudiziario", comune="Milano")
        assert r["trovato"] is True
        assert "Milano" in r["ufficio_competente"]

    def test_giudice_pace(self):
        r = _call("cerca_ufficio_giudiziario", comune="Roma", tipo="giudice_pace")
        assert r["trovato"] is True
        assert "Pace" in r["ufficio_competente"]

    def test_comune_non_trovato(self):
        r = _call("cerca_ufficio_giudiziario", comune="Comuneinesistente99")
        assert r["trovato"] is False

    def test_case_insensitive(self):
        r = _call("cerca_ufficio_giudiziario", comune="ROMA")
        assert r["trovato"] is True

    def test_suggerimenti_su_parziale(self):
        r = _call("cerca_ufficio_giudiziario", comune="mil")
        if not r["trovato"]:
            assert "suggerimenti" in r
        else:
            assert r["trovato"] is True


# ---------------------------------------------------------------------------
# esporta_atto_docx (modelli_atti)
# ---------------------------------------------------------------------------


def _call_modelli(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.modelli_atti")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestEsportaAttoDocx:

    def test_basic_export(self):
        result = _call_modelli("esporta_atto_docx", testo="# Titolo\n\nParagrafo di testo.", titolo="Test")
        assert "docx" in result.lower()
        assert "errore" not in result.lower()

    def test_empty_text_error(self):
        result = _call_modelli("esporta_atto_docx", testo="", titolo="Vuoto")
        assert "errore" in result.lower()

    def test_markdown_formatting(self):
        md = "# Intestazione\n\n## Sottotitolo\n\n**Grassetto** e *corsivo*.\n\n- Punto 1\n- Punto 2"
        result = _call_modelli("esporta_atto_docx", testo=md, titolo="Format Test")
        assert "docx" in result.lower()

    def test_file_created(self):
        import os
        result = _call_modelli("esporta_atto_docx", testo="# Atto\n\nContenuto.", titolo="Atto Prova")
        # Result contains the file path
        assert "File salvato" in result
        path = result.split("File salvato: ")[1].split(" (")[0]
        assert os.path.isfile(path)

    def test_numbered_list(self):
        md = "1. Prima voce\n2. Seconda voce\n3. Terza voce"
        result = _call_modelli("esporta_atto_docx", testo=md, titolo="Lista Numerata")
        assert "docx" in result.lower()

    def test_blockquote(self):
        md = "> Citazione normativa art. 2043 c.c."
        result = _call_modelli("esporta_atto_docx", testo=md, titolo="Blockquote Test")
        assert "docx" in result.lower()

    def test_autore_nei_metadati(self):
        result = _call_modelli(
            "esporta_atto_docx",
            testo="# Test\n\nTesto.",
            titolo="Parere",
            autore="Avv. Mario Rossi",
        )
        assert "docx" in result.lower()
        assert "errore" not in result.lower()
