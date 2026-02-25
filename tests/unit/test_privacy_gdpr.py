"""Unit tests for GDPR/Privacy compliance tools (12 tools)."""

import pytest

from src.tools.privacy_gdpr import (
    _genera_informativa_privacy_impl,
    _genera_informativa_cookie_impl,
    _genera_informativa_dipendenti_impl,
    _genera_informativa_videosorveglianza_impl,
    _genera_dpa_impl,
    _genera_registro_trattamenti_impl,
    _genera_dpia_impl,
    _analisi_base_giuridica_impl,
    _verifica_necessita_dpia_impl,
    _valutazione_data_breach_impl,
    _calcolo_sanzione_gdpr_impl,
    _genera_notifica_data_breach_impl,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TITOLARE = "Acme S.r.l., Via Roma 1, 20100 Milano"
_FINALITA = ["gestione clienti", "invio newsletter"]
_BASI = ["art. 6(1)(b) - contratto", "art. 6(1)(a) - consenso"]
_CATEGORIE = ["dati anagrafici", "dati di contatto"]
_DESTINATARI = ["dipendenti autorizzati", "commercialista"]
_PERIODO = "10 anni per obblighi fiscali"


# ---------------------------------------------------------------------------
# TestGeneraInformativaPrivacy
# ---------------------------------------------------------------------------

class TestGeneraInformativaPrivacy:

    def test_art13_basic(self):
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert "testo" in r
        assert "elementi_obbligatori_verificati" in r
        assert "tutti_elementi_presenti" in r
        assert "riferimento_normativo" in r

    def test_art14_has_fonte_section(self):
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            tipo="art14",
        )
        assert "FONTE DEI DATI" in r["testo"]

    def test_invalid_type(self):
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            tipo="invalid",
        )
        assert "errore" in r

    def test_checklist_all_true(self):
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            dpo="dpo@acme.it",
            trasferimento_extra_ue="Trasferimento verso USA sulla base di SCC",
        )
        assert r["tutti_elementi_presenti"] is True

    def test_titolare_in_text(self):
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert _TITOLARE in r["testo"]

    def test_dpo_section_present(self):
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            dpo="dpo@acme.it",
        )
        assert "DPO" in r["testo"]
        assert "dpo@acme.it" in r["testo"]

    def test_trasferimento_section(self):
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            trasferimento_extra_ue="Trasferimento verso USA sulla base di SCC",
        )
        assert "TRASFERIMENTO VERSO PAESI TERZI" in r["testo"]


# ---------------------------------------------------------------------------
# TestGeneraInformativaCookie
# ---------------------------------------------------------------------------

class TestGeneraInformativaCookie:

    def test_basic_tecnici_only(self):
        r = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["PHPSESSID", "csrf_token"],
            sito_web="https://www.acme.it",
        )
        assert "testo" in r
        assert "tabella_cookie" in r

    def test_with_profilazione(self):
        r = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["PHPSESSID"],
            sito_web="https://www.acme.it",
            cookie_profilazione=["_fbp", "IDE"],
        )
        assert "consenso" in r["banner_testo_suggerito"].lower()

    def test_tabella_structure(self):
        r = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["PHPSESSID"],
            sito_web="https://www.acme.it",
            cookie_analytics=["_ga"],
        )
        for cookie in r["tabella_cookie"]:
            assert "nome" in cookie
            assert "tipo" in cookie
            assert "finalita" in cookie
            assert "durata" in cookie

    def test_no_profilazione_banner(self):
        r = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["PHPSESSID"],
            sito_web="https://www.acme.it",
        )
        assert "Non utilizziamo" in r["banner_testo_suggerito"]


# ---------------------------------------------------------------------------
# TestGeneraInformativaDipendenti
# ---------------------------------------------------------------------------

class TestGeneraInformativaDipendenti:

    def test_basic(self):
        r = _genera_informativa_dipendenti_impl(titolare=_TITOLARE)
        assert "testo" in r
        assert "DIPENDENTI" in r["testo"].upper() or "DIPENDENTE" in r["testo"].upper()

    def test_videosorveglianza_adempimenti(self):
        r = _genera_informativa_dipendenti_impl(titolare=_TITOLARE, videosorveglianza=True)
        assert (
            "videosorveglianza" in r["testo"].lower()
            or any("videosorveglianza" in a.lower() for a in r["adempimenti_aggiuntivi"])
        )

    def test_geolocalizzazione_adempimenti(self):
        r = _genera_informativa_dipendenti_impl(titolare=_TITOLARE, geolocalizzazione=True)
        assert (
            "geolocalizzazione" in r["testo"].lower()
            or any("geolocalizzazione" in a.lower() for a in r["adempimenti_aggiuntivi"])
        )


# ---------------------------------------------------------------------------
# TestGeneraInformativaVideosorveglianza
# ---------------------------------------------------------------------------

class TestGeneraInformativaVideosorveglianza:

    def test_basic(self):
        r = _genera_informativa_videosorveglianza_impl(
            titolare=_TITOLARE,
            finalita=["sicurezza persone", "tutela patrimonio"],
            tempo_conservazione="72 ore",
            aree_riprese=["ingresso principale", "magazzino"],
        )
        assert "informativa_breve" in r
        assert "informativa_estesa" in r

    def test_cartello_edpb(self):
        r = _genera_informativa_videosorveglianza_impl(
            titolare=_TITOLARE,
            finalita=["sicurezza persone"],
            tempo_conservazione="24 ore",
            aree_riprese=["ingresso"],
        )
        breve = r["informativa_breve"]
        assert _TITOLARE in breve
        assert "24 ore" in breve
        assert "VIDEOSORVEGLIATA" in breve.upper() or "videosorvegli" in breve.lower()


# ---------------------------------------------------------------------------
# TestGeneraDpa
# ---------------------------------------------------------------------------

class TestGeneraDpa:

    def _base_dpa(self, **kwargs):
        params = dict(
            titolare=_TITOLARE,
            responsabile="CloudPro S.r.l., Via Monti 5, Milano",
            oggetto="hosting e gestione CRM aziendale",
            durata="per tutta la durata del contratto di servizio",
            categorie_interessati=["clienti", "prospect"],
            categorie_dati=["dati anagrafici", "dati di contatto"],
            misure_sicurezza=["cifratura AES-256", "controllo accessi", "backup giornaliero"],
        )
        params.update(kwargs)
        return _genera_dpa_impl(**params)

    def test_basic(self):
        r = self._base_dpa()
        assert "testo" in r
        assert "clausole_obbligatorie_art28" in r

    def test_8_clausole(self):
        r = self._base_dpa()
        assert len(r["clausole_obbligatorie_art28"]) == 8

    def test_sub_responsabili(self):
        r = self._base_dpa(sub_responsabili=["AWS EMEA S.a.r.l.", "Mailchimp / Intuit"])
        assert "AWS EMEA" in r["testo"] or "sub-responsabili" in r["testo"].lower()


# ---------------------------------------------------------------------------
# TestGeneraRegistroTrattamenti
# ---------------------------------------------------------------------------

class TestGeneraRegistroTrattamenti:

    def _base(self):
        return _genera_registro_trattamenti_impl(
            titolare=_TITOLARE,
            trattamento="Gestione clienti CRM",
            finalita="gestione del rapporto commerciale con i clienti",
            base_giuridica="art. 6(1)(b) - esecuzione contratto",
            categorie_interessati=["clienti", "prospect"],
            categorie_dati=["dati anagrafici", "dati di contatto"],
            destinatari=["ufficio commerciale", "CRM provider"],
            termine_cancellazione="10 anni dalla cessazione del rapporto",
            misure_sicurezza=["cifratura", "controllo accessi"],
        )

    def test_basic(self):
        r = self._base()
        assert isinstance(r["scheda"], dict)
        assert isinstance(r["testo"], str)

    def test_scheda_fields(self):
        r = self._base()
        scheda = r["scheda"]
        required = [
            "titolare",
            "nome_trattamento",
            "finalita",
            "base_giuridica_art6",
            "categorie_interessati",
            "categorie_dati_personali",
            "destinatari_terzi",
            "termine_cancellazione",
            "misure_sicurezza_art32",
        ]
        for field in required:
            assert field in scheda


# ---------------------------------------------------------------------------
# TestGeneraDpia
# ---------------------------------------------------------------------------

class TestGeneraDpia:

    _RISKS = [
        {"desc": "accesso non autorizzato ai dati", "probabilita": "media", "gravita": "alta"},
        {"desc": "perdita dati per guasto", "probabilita": "bassa", "gravita": "media"},
    ]
    _MEASURES = [
        {"misura": "cifratura end-to-end", "rischio_mitigato": "accesso non autorizzato", "efficacia": "alta"},
    ]

    def test_basic(self):
        r = _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="Sistema di profilazione utenti",
            finalita="ottimizzazione campagne marketing",
            necessita_proporzionalita="Trattamento minimo necessario",
            rischi=self._RISKS,
            misure_mitigazione=self._MEASURES,
        )
        assert "testo" in r
        assert "matrice_rischi" in r
        assert "rischio_residuo" in r

    def test_risk_matrix(self):
        r = _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="Trattamento dati biometrici",
            finalita="controllo accessi",
            necessita_proporzionalita="Strettamente necessario",
            rischi=[
                {"desc": "furto identità biometrica", "probabilita": "bassa", "gravita": "molto_alta"},
            ],
            misure_mitigazione=[],
        )
        matrice = r["matrice_rischi"]
        assert len(matrice) == 1
        # probabilita bassa=1, gravita molto_alta=4 → score=4 → livello=medio
        assert matrice[0]["score"] == 4
        assert matrice[0]["livello_rischio"] == "medio"

    def test_very_high_risk_triggers_consultation(self):
        r = _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="Sorveglianza di massa",
            finalita="sicurezza nazionale",
            necessita_proporzionalita="Proporzionato",
            rischi=[
                {"desc": "esposizione su larga scala", "probabilita": "molto_alta", "gravita": "molto_alta"},
            ],
            misure_mitigazione=[],
        )
        assert r["consultazione_preventiva_necessaria"] is True
        assert "molto_alto" in r["rischio_residuo"]


# ---------------------------------------------------------------------------
# TestAnalisiBaseGiuridica
# ---------------------------------------------------------------------------

class TestAnalisiBaseGiuridica:

    def test_basic(self):
        r = _analisi_base_giuridica_impl(
            tipo_trattamento="invio newsletter",
            contesto="B2C",
            finalita="marketing diretto via email",
        )
        assert "basi_giuridiche_applicabili" in r
        assert "base_consigliata" in r
        assert "motivazione" in r

    def test_b2c_marketing_recommends_consenso(self):
        r = _analisi_base_giuridica_impl(
            tipo_trattamento="invio newsletter",
            contesto="B2C",
            finalita="marketing diretto via email a clienti nuovi",
        )
        assert "consenso" in r["base_consigliata"]

    def test_pa_no_legittimo_interesse(self):
        r = _analisi_base_giuridica_impl(
            tipo_trattamento="gestione pratiche amministrative",
            contesto="pubblica_amministrazione",
            finalita="erogazione servizi pubblici",
        )
        assert r["base_consigliata"] != "legittimo_interesse"

    def test_dati_particolari_adds_art9(self):
        r = _analisi_base_giuridica_impl(
            tipo_trattamento="gestione dossier sanitari",
            contesto="sanita",
            finalita="diagnosi e cura",
            dati_particolari=True,
        )
        assert "art. 9" in r["note_dati_particolari_art9"].lower() or "9" in r["note_dati_particolari_art9"]
        assert len(r["condizioni_art9_disponibili"]) > 0


# ---------------------------------------------------------------------------
# TestVerificaNecessitaDpia
# ---------------------------------------------------------------------------

class TestVerificaNecessitaDpia:

    def test_no_criteria_not_necessary(self):
        r = _verifica_necessita_dpia_impl(tipo_trattamento="archiviazione documenti cartacei")
        assert r["dpia_necessaria"] is False

    def test_two_criteria_necessary(self):
        r = _verifica_necessita_dpia_impl(
            tipo_trattamento="sistema di profilazione clienti su larga scala",
            profilazione=True,
            larga_scala=True,
        )
        assert r["dpia_necessaria"] is True

    def test_criteria_list(self):
        r = _verifica_necessita_dpia_impl(
            tipo_trattamento="sorveglianza sistematica con dati sensibili",
            dati_sensibili=True,
            monitoraggio_sistematico=True,
        )
        assert r["n_criteri"] == 2

    def test_single_criterion_not_necessary(self):
        r = _verifica_necessita_dpia_impl(
            tipo_trattamento="raccolta dati sanitari singolo studio medico",
            dati_sensibili=True,
        )
        assert r["dpia_necessaria"] is False


# ---------------------------------------------------------------------------
# TestValutazioneDataBreach
# ---------------------------------------------------------------------------

class TestValutazioneDataBreach:

    def test_basic(self):
        r = _valutazione_data_breach_impl(
            tipo_violazione="confidenzialita",
            categorie_dati=["email", "nome", "cognome"],
            n_interessati=50,
        )
        assert "notifica_garante" in r
        assert "comunicazione_interessati" in r
        assert "livello_rischio" in r
        assert "azioni_consigliate" in r

    def test_high_risk_requires_notification(self):
        r = _valutazione_data_breach_impl(
            tipo_violazione="confidenzialita",
            categorie_dati=["dati sanitari", "codice fiscale"],
            n_interessati=5000,
            dati_particolari=True,
            impatto="molto_alto",
        )
        assert r["notifica_garante"] is True

    def test_encryption_excludes_communication(self):
        r = _valutazione_data_breach_impl(
            tipo_violazione="confidenzialita",
            categorie_dati=["email", "password hash"],
            n_interessati=200,
            misure_protezione=["cifratura AES-256"],
            impatto="medio",
        )
        assert r["comunicazione_interessati"] is False
        assert r["cifratura_attiva"] is True

    def test_low_risk(self):
        r = _valutazione_data_breach_impl(
            tipo_violazione="disponibilita",
            categorie_dati=["email aziendale"],
            n_interessati=3,
            impatto="basso",
        )
        assert r["livello_rischio"] in ("improbabile", "possibile")


# ---------------------------------------------------------------------------
# TestCalcoloSanzioneGdpr
# ---------------------------------------------------------------------------

class TestCalcoloSanzioneGdpr:

    def test_art83_5_massimale(self):
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5")
        assert r["massimale"]["euro"] == 20_000_000
        assert r["massimale"]["pct_fatturato"] == 4

    def test_art83_4_massimale(self):
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_4")
        assert r["massimale"]["euro"] == 10_000_000
        assert r["massimale"]["pct_fatturato"] == 2

    def test_with_fatturato(self):
        r = _calcolo_sanzione_gdpr_impl(
            tipo_violazione="art83_5",
            fatturato_annuo=1_000_000_000,
        )
        # 4% di 1B = 40M > 20M → massimale effettivo 40M → range > senza fatturato
        assert r["range_stimato"]["massimo"] > 800_000

    def test_aggravanti_increase_range(self):
        base = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5")
        con_aggravanti = _calcolo_sanzione_gdpr_impl(
            tipo_violazione="art83_5",
            fattori_aggravanti=["larga scala", "dati sensibili", "violazione dolosa"],
        )
        assert con_aggravanti["range_stimato"]["massimo"] > base["range_stimato"]["massimo"]

    def test_attenuanti_decrease_range(self):
        base = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5")
        con_attenuanti = _calcolo_sanzione_gdpr_impl(
            tipo_violazione="art83_5",
            fattori_attenuanti=["prima violazione", "cooperazione piena", "misure correttive immediate"],
        )
        assert con_attenuanti["range_stimato"]["massimo"] < base["range_stimato"]["massimo"]


# ---------------------------------------------------------------------------
# TestGeneraNotificaDataBreach
# ---------------------------------------------------------------------------

class TestGeneraNotificaDataBreach:

    def _base(self, **kwargs):
        params = dict(
            titolare=_TITOLARE,
            data_violazione="2025-01-14",
            data_scoperta="2025-01-15",
            descrizione="Accesso non autorizzato al database clienti tramite credenziali compromesse",
            categorie_dati=["email", "nome", "cognome", "telefono"],
            n_interessati=1200,
            conseguenze="Possibile utilizzo dei dati per phishing e furto d'identità",
            misure_adottate=["reset credenziali", "blocco accessi", "notifica interessati"],
        )
        params.update(kwargs)
        return _genera_notifica_data_breach_impl(**params)

    def test_basic(self):
        r = self._base()
        assert "testo" in r
        assert "termine_scadenza" in r
        assert "elementi_art33_3" in r

    def test_72h_deadline(self):
        r = self._base(data_scoperta="2025-01-15T08:00")
        # scoperta 15/01 ore 08:00 → scadenza 18/01 ore 08:00
        assert "18/01/2025" in r["termine_scadenza"]

    def test_4_elements(self):
        r = self._base()
        elementi = r["elementi_art33_3"]
        assert len(elementi) == 4
        assert all(elementi.values())

    def test_params_in_text(self):
        r = self._base()
        assert _TITOLARE in r["testo"]
        assert "Accesso non autorizzato" in r["testo"]
