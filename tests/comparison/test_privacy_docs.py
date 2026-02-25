"""Comparison tests for privacy GDPR tools.

Verifies that parameters passed to tools appear in the generated text
and that normative references are correct.
"""

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
# Shared test data
# ---------------------------------------------------------------------------

_TITOLARE = "Acme S.r.l. - Via Roma 10, 00100 Roma"
_FINALITA = ["gestione contrattuale", "marketing diretto"]
_BASI = ["art. 6(1)(b) - esecuzione contratto", "art. 6(1)(a) - consenso"]
_CATEGORIE_DATI = ["dati anagrafici", "dati di contatto", "email"]
_DESTINATARI = ["dipendenti autorizzati", "responsabili IT"]
_PERIODO = "10 anni dalla cessazione del rapporto contrattuale"


# ---------------------------------------------------------------------------
# TestParametriInTesto
# ---------------------------------------------------------------------------


class TestParametriInTesto:
    def test_informativa_titolare_in_testo(self):
        result = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE_DATI,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert _TITOLARE in result["testo"]

    def test_informativa_finalita_in_testo(self):
        result = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=["marketing diretto"],
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE_DATI,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert "marketing diretto" in result["testo"]

    def test_cookie_sito_in_testo(self):
        result = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["session_id"],
            sito_web="www.example.com",
        )
        assert "www.example.com" in result["testo"]

    def test_cookie_tecnici_in_tabella(self):
        result = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["session_id"],
            sito_web="www.example.com",
        )
        assert any(c["nome"] == "session_id" for c in result["tabella_cookie"])

    def test_dpa_titolare_e_responsabile(self):
        result = _genera_dpa_impl(
            titolare="Alpha S.r.l.",
            responsabile="Beta S.p.A.",
            oggetto="hosting e gestione CRM",
            durata="per tutta la durata del contratto",
            categorie_interessati=["clienti"],
            categorie_dati=_CATEGORIE_DATI,
            misure_sicurezza=["controllo accessi"],
        )
        assert "Alpha S.r.l." in result["testo"]
        assert "Beta S.p.A." in result["testo"]

    def test_dpa_misure_in_testo(self):
        result = _genera_dpa_impl(
            titolare=_TITOLARE,
            responsabile="Cloud Provider S.r.l.",
            oggetto="hosting applicativo",
            durata="per tutta la durata del contratto",
            categorie_interessati=["clienti"],
            categorie_dati=_CATEGORIE_DATI,
            misure_sicurezza=["cifratura AES-256"],
        )
        assert "cifratura AES-256" in result["testo"]

    def test_registro_trattamento_in_scheda(self):
        result = _genera_registro_trattamenti_impl(
            titolare=_TITOLARE,
            trattamento="Gestione paghe",
            finalita="amministrazione del personale",
            base_giuridica="art. 6(1)(b) - esecuzione contratto",
            categorie_interessati=["dipendenti"],
            categorie_dati=_CATEGORIE_DATI,
            destinatari=_DESTINATARI,
            termine_cancellazione=_PERIODO,
            misure_sicurezza=["controllo accessi"],
        )
        assert result["scheda"]["nome_trattamento"] == "Gestione paghe"

    def test_dpia_rischi_in_matrice(self):
        desc_rischio = "Accesso non autorizzato ai dati sensibili"
        result = _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="Sistema di analisi comportamentale",
            finalita="profilazione utenti per personalizzazione servizi",
            necessita_proporzionalita="necessario per erogare il servizio richiesto",
            rischi=[{"desc": desc_rischio, "probabilita": "media", "gravita": "alta"}],
            misure_mitigazione=[
                {"misura": "cifratura dati", "rischio_mitigato": desc_rischio, "efficacia": "alta"}
            ],
        )
        assert any(r["descrizione"] == desc_rischio for r in result["matrice_rischi"])

    def test_breach_notifica_titolare(self):
        result = _genera_notifica_data_breach_impl(
            titolare="Test Corp S.r.l.",
            data_violazione="2026-02-20T08:00",
            data_scoperta="2026-02-20T10:00",
            descrizione="Accesso non autorizzato al server di produzione",
            categorie_dati=_CATEGORIE_DATI,
            n_interessati=500,
            conseguenze="Potenziale accesso a dati di contatto",
            misure_adottate=["blocco accessi", "reset credenziali"],
        )
        assert "Test Corp S.r.l." in result["testo"]

    def test_breach_descrizione_in_testo(self):
        desc = "Accesso non autorizzato al database"
        result = _genera_notifica_data_breach_impl(
            titolare=_TITOLARE,
            data_violazione="2026-02-20T08:00",
            data_scoperta="2026-02-20T10:00",
            descrizione=desc,
            categorie_dati=_CATEGORIE_DATI,
            n_interessati=100,
            conseguenze="Rischio furto identità",
            misure_adottate=["blocco sistema"],
        )
        assert desc in result["testo"]


# ---------------------------------------------------------------------------
# TestRiferimentiNormativi
# ---------------------------------------------------------------------------


class TestRiferimentiNormativi:
    def test_informativa_art13_ref(self):
        result = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE_DATI,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            tipo="art13",
        )
        assert "Art. 13" in result["riferimento_normativo"]

    def test_informativa_art14_ref(self):
        result = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE_DATI,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            tipo="art14",
        )
        assert "Art. 14" in result["riferimento_normativo"]

    def test_cookie_ref(self):
        result = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["session_id"],
            sito_web="www.example.com",
        )
        ref = result["riferimento_normativo"]
        assert "D.Lgs. 196/2003" in ref or "Linee Guida" in ref

    def test_dipendenti_ref(self):
        result = _genera_informativa_dipendenti_impl(titolare=_TITOLARE)
        ref = result["riferimento_normativo"]
        assert "Art. 13" in ref
        assert "L. 300/1970" in ref

    def test_videosorveglianza_ref(self):
        result = _genera_informativa_videosorveglianza_impl(
            titolare=_TITOLARE,
            finalita=["sicurezza persone", "tutela patrimonio"],
            tempo_conservazione="72 ore",
            aree_riprese=["ingresso principale"],
        )
        ref = result["riferimento_normativo"]
        assert "EDPB" in ref or "Art. 13" in ref

    def test_dpa_ref(self):
        result = _genera_dpa_impl(
            titolare=_TITOLARE,
            responsabile="Provider S.r.l.",
            oggetto="hosting",
            durata="per tutta la durata del contratto",
            categorie_interessati=["clienti"],
            categorie_dati=_CATEGORIE_DATI,
            misure_sicurezza=["cifratura"],
        )
        assert "Art. 28" in result["riferimento_normativo"]

    def test_registro_ref(self):
        result = _genera_registro_trattamenti_impl(
            titolare=_TITOLARE,
            trattamento="Gestione clienti",
            finalita="gestione rapporto commerciale",
            base_giuridica="art. 6(1)(b)",
            categorie_interessati=["clienti"],
            categorie_dati=_CATEGORIE_DATI,
            destinatari=_DESTINATARI,
            termine_cancellazione=_PERIODO,
            misure_sicurezza=["controllo accessi"],
        )
        assert "Art. 30" in result["riferimento_normativo"]

    def test_dpia_ref(self):
        result = _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="Trattamento dati biometrici",
            finalita="controllo accessi",
            necessita_proporzionalita="proporzionale alla finalità di sicurezza",
            rischi=[{"desc": "Furto dati biometrici", "probabilita": "bassa", "gravita": "alta"}],
            misure_mitigazione=[
                {"misura": "cifratura", "rischio_mitigato": "Furto dati biometrici", "efficacia": "alta"}
            ],
        )
        assert "Art. 35" in result["riferimento_normativo"]

    def test_base_giuridica_ref(self):
        result = _analisi_base_giuridica_impl(
            tipo_trattamento="invio newsletter",
            contesto="B2C",
            finalita="marketing diretto",
        )
        assert "Art. 6" in result["riferimento_normativo"]

    def test_dpia_verifica_ref(self):
        result = _verifica_necessita_dpia_impl(
            tipo_trattamento="sistema biometrico presenze",
            dati_sensibili=True,
            larga_scala=True,
        )
        ref = result["riferimento_normativo"]
        assert "WP248" in ref or "Art. 35" in ref

    def test_breach_ref(self):
        result = _valutazione_data_breach_impl(
            tipo_violazione="confidenzialita",
            categorie_dati=_CATEGORIE_DATI,
            n_interessati=200,
            impatto="medio",
        )
        ref = result["riferimento_normativo"]
        assert "Art. 33" in ref or "Art. 34" in ref

    def test_sanzione_ref(self):
        result = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5")
        assert "Art. 83" in result["riferimento_normativo"]

    def test_notifica_breach_ref(self):
        result = _genera_notifica_data_breach_impl(
            titolare=_TITOLARE,
            data_violazione="2026-02-20T08:00",
            data_scoperta="2026-02-20T10:00",
            descrizione="Violazione accesso sistema",
            categorie_dati=_CATEGORIE_DATI,
            n_interessati=50,
            conseguenze="Rischio accesso non autorizzato",
            misure_adottate=["blocco accessi"],
        )
        assert "Art. 33" in result["riferimento_normativo"]


# ---------------------------------------------------------------------------
# TestSezioniObbligatorie
# ---------------------------------------------------------------------------


class TestSezioniObbligatorie:
    def test_informativa_has_diritti_section(self):
        result = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE_DATI,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert "DIRITTI" in result["testo"].upper()

    def test_informativa_has_reclamo_section(self):
        result = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE_DATI,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert "RECLAMO" in result["testo"].upper() or "garanteprivacy" in result["testo"]

    def test_cookie_has_banner(self):
        result = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["session_id"],
            sito_web="www.example.com",
        )
        assert isinstance(result["banner_testo_suggerito"], str)
        assert len(result["banner_testo_suggerito"]) > 0

    def test_dpa_has_durata(self):
        result = _genera_dpa_impl(
            titolare=_TITOLARE,
            responsabile="Provider S.r.l.",
            oggetto="hosting applicativo",
            durata="per tutta la durata del contratto di servizio",
            categorie_interessati=["clienti"],
            categorie_dati=_CATEGORIE_DATI,
            misure_sicurezza=["cifratura"],
        )
        testo_lower = result["testo"].lower()
        assert "durata" in testo_lower

    def test_dpia_has_matrice(self):
        result = _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="Profilazione utenti su larga scala",
            finalita="personalizzazione servizi",
            necessita_proporzionalita="necessario per il servizio",
            rischi=[
                {"desc": "Accesso non autorizzato", "probabilita": "media", "gravita": "alta"},
                {"desc": "Uso improprio dei dati", "probabilita": "bassa", "gravita": "media"},
            ],
            misure_mitigazione=[
                {"misura": "cifratura", "rischio_mitigato": "Accesso non autorizzato", "efficacia": "alta"}
            ],
        )
        assert isinstance(result["matrice_rischi"], list)
        assert len(result["matrice_rischi"]) > 0

    def test_notifica_has_termine(self):
        result = _genera_notifica_data_breach_impl(
            titolare=_TITOLARE,
            data_violazione="2026-02-20T08:00",
            data_scoperta="2026-02-20T10:00",
            descrizione="Violazione accesso sistema",
            categorie_dati=_CATEGORIE_DATI,
            n_interessati=50,
            conseguenze="Rischio accesso non autorizzato",
            misure_adottate=["blocco accessi"],
        )
        assert isinstance(result["termine_scadenza"], str)
        assert len(result["termine_scadenza"]) > 0
