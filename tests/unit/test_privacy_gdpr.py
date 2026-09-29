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
        # Art. 13(1)(f) and 13(2)(e) GDPR: with a transfer the safeguards (and the way to get a
        # copy) and the nature of the provision of data must be supplied for the checklist to
        # close; the text no longer claims completeness on its own.
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            dpo="dpo@acme.it",
            trasferimento_extra_ue="Trasferimento verso USA sulla base di SCC",
            conferimento="Obbligatorio per la conclusione del contratto; senza i dati il contratto non si conclude",
            garanzia_trasferimento="Clausole contrattuali standard (art. 46(2)(c)); copia su richiesta al titolare",
        )
        assert r["tutti_elementi_presenti"] is True
        assert r["campi_da_completare"] == []
        assert "[DA COMPLETARE" not in r["testo"]

    def test_checklist_open_when_case_specific_elements_missing(self):
        # Art. 13(2)(e) and 13(1)(f) GDPR: no input for the nature of the provision of data or
        # for the transfer safeguards, so the checklist must NOT report the notice as complete.
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            trasferimento_extra_ue="server negli Stati Uniti",
        )
        el = r["elementi_obbligatori_verificati"]
        assert el["conferimento_e_conseguenze"] is False
        assert el["trasferimento_extra_ue_se_presente"] is False
        assert r["tutti_elementi_presenti"] is False
        assert r["campi_da_completare"] == ["garanzia_trasferimento", "conferimento"]
        assert "[DA COMPLETARE" in r["testo"]

    def test_art13_legittimi_interessi_art13_1_d(self):
        # Art. 13(1)(d) GDPR: when a basis is art. 6(1)(f) the notice names the legitimate
        # interests pursued by the controller or by a third party.
        basi = ["art. 6(1)(b) GDPR - contratto", "art. 6(1)(f) GDPR - legittimo interesse"]
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=basi,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert "LEGITTIMI INTERESSI PERSEGUITI DAL TITOLARE O DA TERZI" in r["testo"]
        assert r["elementi_obbligatori_verificati"]["legittimi_interessi_se_art_6_1_f"] is False
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=basi,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            legittimi_interessi="prevenzione delle frodi nei pagamenti",
        )
        assert "prevenzione delle frodi nei pagamenti" in r["testo"]
        assert r["elementi_obbligatori_verificati"]["legittimi_interessi_se_art_6_1_f"] is True

    def test_no_legittimi_interessi_section_without_art_6_1_f(self):
        # Art. 13(1)(d) GDPR applies only "qualora il trattamento si basi sull'articolo 6,
        # paragrafo 1, lettera f)": no such section for contract/consent bases.
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert "LEGITTIMI INTERESSI" not in r["testo"]
        assert r["elementi_obbligatori_verificati"]["legittimi_interessi_se_art_6_1_f"] is True

    def test_art13_conferimento_art13_2_e(self):
        # Art. 13(2)(e) GDPR: nature of the provision of data and consequences of not providing.
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            conferimento="Facoltativo: il rifiuto impedisce solo l'invio della newsletter",
        )
        assert "CONFERIMENTO DEI DATI" in r["testo"]
        assert "il rifiuto impedisce solo l'invio della newsletter" in r["testo"]
        assert r["elementi_obbligatori_verificati"]["conferimento_e_conseguenze"] is True

    def test_art14_has_no_conferimento_section(self):
        # Art. 13(2)(e) is an art. 13 element: data not collected from the data subject
        # (art. 14) have no "conferimento" by the data subject.
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            tipo="art14",
            fonte_dati="registro delle imprese (fonte accessibile al pubblico)",
        )
        assert "CONFERIMENTO" not in r["testo"]
        assert "conferimento_e_conseguenze" not in r["elementi_obbligatori_verificati"]

    def test_decisioni_automatizzate_art13_2_f(self):
        # Art. 13(2)(f) / 14(2)(g) GDPR: existence (with logic, significance, consequences)
        # or absence of automated decision-making, including profiling, is always stated.
        base = dict(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        senza = _genera_informativa_privacy_impl(**base)
        assert "non adotta alcun processo decisionale unicamente automatizzato" in senza["testo"]
        assert len(senza["avvertenze"]) == 1
        con = _genera_informativa_privacy_impl(
            **base, decisioni_automatizzate="punteggio di affidabilita' calcolato sul pagamento storico"
        )
        assert "Il Titolare adotta un processo decisionale automatizzato" in con["testo"]
        assert "punteggio di affidabilita' calcolato sul pagamento storico" in con["testo"]
        assert con["avvertenze"] == []

    def test_art14_fonte_dati_art14_2_f(self):
        # Art. 14(2)(f) GDPR: the specific source of the data and whether it is publicly
        # accessible. The checklist reports the element only when the caller supplied it.
        base = dict(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            tipo="art14",
        )
        senza = _genera_informativa_privacy_impl(**base)
        assert senza["elementi_obbligatori_verificati"]["fonte_dati"] is False
        assert senza["tutti_elementi_presenti"] is False
        assert "Fonti accessibili al pubblico (registri" not in senza["testo"]  # no fixed list of sources
        con = _genera_informativa_privacy_impl(**base, fonte_dati="elenco clienti del partner Gamma S.r.l.")
        assert "elenco clienti del partner Gamma S.r.l." in con["testo"]
        assert con["elementi_obbligatori_verificati"]["fonte_dati"] is True

    def test_trasferimento_garanzie_e_copia_art13_1_f(self):
        # Art. 13(1)(f) / 14(1)(f) GDPR: adequacy decision or safeguards, and the means to
        # obtain a copy or the place where they are available.
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
            trasferimento_extra_ue="server negli Stati Uniti",
            garanzia_trasferimento="decisione di adeguatezza (EU-US Data Privacy Framework)",
        )
        assert "decisione di adeguatezza (EU-US Data Privacy Framework)" in r["testo"]
        assert "copia delle garanzie" in r["testo"]
        assert "art. 46(2)(c) GDPR)." not in r["testo"]  # the fixed 'art. 45 ovvero art. 46(2)(c)' is gone
        assert r["elementi_obbligatori_verificati"]["trasferimento_extra_ue_se_presente"] is True

    def test_numerazione_progressiva_senza_salti(self):
        # The optional DPO and transfer sections used to carry fixed numbers 5 and 6, leaving a
        # 1,2,3,4,7,8,9 sequence when omitted: numbering is now progressive.
        import re

        for kwargs in (
            {},
            {"dpo": "dpo@acme.it"},
            {"trasferimento_extra_ue": "USA"},
            {"tipo": "art14", "dpo": "dpo@acme.it", "trasferimento_extra_ue": "USA"},
        ):
            r = _genera_informativa_privacy_impl(
                titolare=_TITOLARE,
                finalita=_FINALITA,
                basi_giuridiche=["art. 6(1)(f) GDPR - legittimo interesse"],
                categorie_dati=_CATEGORIE,
                destinatari=_DESTINATARI,
                periodo_conservazione=_PERIODO,
                **kwargs,
            )
            numeri = [int(n) for n in re.findall(r"(?m)^(\d+)\. [A-ZÀ-Ú]", r["testo"])]
            assert numeri == list(range(1, len(numeri) + 1)), (kwargs, numeri)

    def test_persone_autorizzate_e_recapiti_garante(self):
        # Art. 29 GDPR and art. 2-quaterdecies D.Lgs. 196/2003 replace the 'incaricato' of the
        # repealed art. 30 Codice; the Garante's official contacts are protocollo@gpdp.it and
        # protocollo@pec.gpdp.it (garanteprivacy.it/home/footer/contatti).
        r = _genera_informativa_privacy_impl(
            titolare=_TITOLARE,
            finalita=_FINALITA,
            basi_giuridiche=_BASI,
            categorie_dati=_CATEGORIE,
            destinatari=_DESTINATARI,
            periodo_conservazione=_PERIODO,
        )
        assert "incaricati" not in r["testo"]
        assert "persone autorizzate al trattamento" in r["testo"]
        assert "art. 2-quaterdecies D.Lgs. 196/2003" in r["testo"]
        assert "garante@gpdp.it" not in r["testo"]
        assert "E-mail: protocollo@gpdp.it" in r["testo"]
        assert "PEC: protocollo@pec.gpdp.it" in r["testo"]

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

    def test_banner_avvertenza_chiusura_con_x(self):
        # Garante cookie guidelines 10/06/2021, par. 7.1, point i): the banner must warn that
        # closing it with the X keeps the default settings, i.e. browsing without cookies other
        # than technical ones.
        for kwargs in ({"cookie_analytics": ["_ga"]}, {"cookie_profilazione": ["_fbp"]}):
            r = _genera_informativa_cookie_impl(
                titolare=_TITOLARE,
                cookie_tecnici=["PHPSESSID"],
                sito_web="https://www.acme.it",
                **kwargs,
            )
            banner = r["banner_testo_suggerito"]
            assert "X in alto a destra" in banner
            assert "impostazioni di default" in banner
            assert "diversi da quelli tecnici" in banner

    def test_analytics_condizioni_par_7_2(self):
        # Garante cookie guidelines 10/06/2021, par. 7.2: third-party analytics are equated to
        # technical cookies (no consent) only if the IP is masked at least in its fourth
        # component, the statistics are aggregate on a single site, and the provider neither
        # combines the data nor passes them on. A transfer outside the EU is NOT the criterion.
        r = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["PHPSESSID"],
            sito_web="https://www.acme.it",
            cookie_analytics=["_ga", "_gid"],
        )
        testo = r["testo"]
        assert "quarta componente" in testo
        assert "statistiche aggregate" in testo
        assert "non combina i dati con altre elaborazioni" in testo
        assert "extra-UE, è richiesto il consenso" not in testo
        assert "capo V del GDPR" in testo
        riga = next(c for c in r["tabella_cookie"] if c["nome"] == "_ga")
        assert "non trasferiti a terzi" not in riga["base_giuridica"]
        assert "quarta componente" in riga["base_giuridica"]
        assert len(r["condizioni_equiparazione_analytics"]) == 3
        assert r["consenso_richiesto_analytics"] is True  # prudential default

    def test_no_analytics_conditions_without_analytics(self):
        r = _genera_informativa_cookie_impl(
            titolare=_TITOLARE, cookie_tecnici=["PHPSESSID"], sito_web="https://www.acme.it"
        )
        assert "condizioni_equiparazione_analytics" not in r
        assert "note_implementazione_banner" not in r
        assert "3. COOKIE ANALITICI" not in r["testo"]

    def test_scroll_e_sei_mesi_come_note_di_implementazione(self):
        # Garante cookie guidelines 10/06/2021, par. 6.1 (scrolling is never consent), par. 6.2
        # (no re-proposal of the banner before 6 months) and 7.1 (X with equal prominence): rules
        # for the consent mechanism, returned as implementation notes and stated in the policy.
        r = _genera_informativa_cookie_impl(
            titolare=_TITOLARE,
            cookie_tecnici=["PHPSESSID"],
            sito_web="https://www.acme.it",
            cookie_profilazione=["_fbp"],
        )
        note = " ".join(r["note_implementazione_banner"])
        assert "scroll" in note and "6 mesi" in note and "X" in note
        assert "non costituisce consenso" in r["testo"]


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

    def test_autorizzazione_itl_art4_comma_1(self):
        # Art. 4 L. 300/1970 (text after D.Lgs. 151/2015): the collective agreement and, failing
        # it, the authorisation of the territorial office of the Ispettorato nazionale del lavoro
        # are BOTH in paragraph 1 (third sentence); paragraph 2 only exempts work tools and
        # attendance recorders. The notice used to attribute the authorisation to paragraph 2.
        r = _genera_informativa_dipendenti_impl(
            titolare=_TITOLARE, videosorveglianza=True, geolocalizzazione=True
        )
        assert "Ispettorato Territoriale del Lavoro (art. 4(1) L. 300/1970)" in r["testo"]
        assert "Ispettorato Territoriale del Lavoro (art. 4(2)" not in r["testo"]

    def test_strumenti_aziendali_art4_commi_2_e_3(self):
        # Art. 4(2) L. 300/1970: tools used to perform the work are outside paragraph 1 (no
        # agreement or authorisation); art. 4(3): the information gathered is usable for every
        # purpose connected with the employment relationship if the worker is adequately informed
        # of how the tools are used and how checks are made, and D.Lgs. 196/2003 is respected.
        r = _genera_informativa_dipendenti_impl(titolare=_TITOLARE, strumenti_aziendali=True)
        testo = r["testo"]
        assert "non richiedono accordo sindacale" in testo
        assert "(art. 4(2) L. 300/1970)" in testo
        assert "adeguata informazione delle modalità d'uso degli strumenti" in testo
        assert "(art. 4(3) L. 300/1970)" in testo
        # the purposes "organizzative, produttive, di sicurezza, tutela del patrimonio" belong to
        # art. 4(1) and are no longer attached to paragraph 2
        assert "per ragioni organizzative, produttive" not in testo

    def test_riferimenti_art88_113_114_non_111_bis(self):
        # Art. 111-bis D.Lgs. 196/2003 governs only "curricula spontaneamente trasmessi"; the
        # employment-relationship anchors are art. 88 GDPR and artt. 113-114 D.Lgs. 196/2003
        # (which refer back to art. 8 and art. 4 L. 300/1970).
        r = _genera_informativa_dipendenti_impl(titolare=_TITOLARE)
        doc = r["testo"] + r["riferimento_normativo"]
        assert "111-bis" not in doc
        assert "art. 88" in doc
        assert "art. 113" in doc
        assert "art. 114 D.Lgs. 196/2003" in doc
        assert "L. 300/1970" in r["riferimento_normativo"]

    def test_conservazione_cartella_sanitaria_art25_1_e(self):
        # Art. 25(1)(e) D.Lgs. 81/2008: the employer keeps the original health file "per almeno
        # dieci anni, salvo il diverso termine previsto da altre disposizioni"; forty years are
        # INAIL's retention for carcinogens/mutagens (art. 243(6)), asbestos (art. 260(4)) and
        # some biological agents (art. 280(4)), not the employer's rule under art. 25(1)(a).
        r = _genera_informativa_dipendenti_impl(titolare=_TITOLARE)
        testo = r["testo"]
        assert "40 anni (art. 25(1)(a)" not in testo
        assert "per almeno 10 anni (art. 25(1)(e) D.Lgs. 81/2008)" in testo
        assert "art. 243(6) D.Lgs. 81/2008" in testo
        assert "art. 260(4) D.Lgs. 81/2008" in testo
        assert "art. 280(4) D.Lgs. 81/2008" in testo
        assert "l'INAIL conserva la documentazione" in testo

    def test_persone_autorizzate_non_incaricato(self):
        # D.Lgs. 101/2018 repealed art. 30 of the Codice (the "incaricato"); the current figure is
        # the person authorised under art. 29 GDPR and art. 2-quaterdecies D.Lgs. 196/2003.
        r = _genera_informativa_dipendenti_impl(titolare=_TITOLARE)
        assert not any("incaricato" in a.lower() for a in r["adempimenti_aggiuntivi"])
        assert any("art. 2-quaterdecies D.Lgs. 196/2003" in a for a in r["adempimenti_aggiuntivi"])
        assert len(r["adempimenti_aggiuntivi"]) == 4


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

    # Art. 28(3), second sub-paragraph, GDPR: "con riguardo alla lettera h) del primo comma, il
    # responsabile del trattamento informa immediatamente il titolare del trattamento qualora,
    # a suo parere, un'istruzione violi il presente regolamento o altre disposizioni, nazionali
    # o dell'Unione, relative alla protezione dei dati" (EUR-Lex CELEX 32016R0679).
    def test_avviso_istruzione_illecita_art28_3_secondo_comma(self):
        for sub in (None, ["AWS EMEA S.a.r.l."]):
            r = self._base_dpa(sub_responsabili=sub)
            t = " ".join(r["testo"].split())
            assert "informa immediatamente il Titolare" in t
            assert "un'istruzione violi il Regolamento" in t
            assert r["avviso_istruzione_illecita_art28_3"] is True
            assert r["tutte_clausole_presenti"] is True

    # Art. 28(4) GDPR: the sub-processor gets "gli stessi obblighi in materia di protezione dei
    # dati" of the DPA (not "analoghi") and the initial processor keeps "l'intera responsabilità".
    def test_sub_responsabili_stessi_obblighi_art28_4(self):
        r = self._base_dpa(sub_responsabili=["AWS EMEA S.a.r.l."])
        t = " ".join(r["testo"].split())
        assert "gli stessi obblighi in materia di protezione dei dati" in t
        assert "analoghi" not in t
        assert "l'intera responsabilità" in t
        assert "[art. 28(3)(d), art. 28(2) e (4)]" in t

    # Art. 28(3)(d) with art. 28(2) and (4): even without named sub-processors the clause carries
    # the general-authorisation notice (28(2), second sentence) and the 28(4) obligations.
    def test_senza_sub_responsabili_condizioni_art28_2_e_4(self):
        r = self._base_dpa()
        t = " ".join(r["testo"].split())
        assert "previa autorizzazione scritta specifica o generale" in t
        assert "l'opportunità di opporsi a tali modifiche" in t
        assert "gli stessi obblighi in materia di protezione dei dati" in t
        assert "l'intera responsabilità" in t

    # Art. 28(10) GDPR: a processor that determines purposes and means is considered a controller.
    def test_responsabile_titolare_art28_10(self):
        assert "art. 28(10) GDPR" in " ".join(self._base_dpa()["testo"].split())

    # The checklist is derived from the text: dropping a clause label flips its flag.
    def test_checklist_derivata_dal_testo(self):
        r = self._base_dpa()
        assert all(r["clausole_obbligatorie_art28"].values())
        assert "[art. 28(3)(h)]" in r["testo"] and "[art. 28(3)(d)" in r["testo"]


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

    # Art. 36(1) GDPR: prior consultation when the DPIA shows a high risk that the controller's
    # measures do not attenuate; recital 84/94 and WP248 rev.01 look at the RESIDUAL risk. The
    # 2-step reduction for "alta" efficacy is a tool convention (STIMATO), not fixed by the norm.
    _BIOMETRIA_RISCHIO = [
        {"desc": "accesso abusivo ai template biometrici", "probabilita": "alta", "gravita": "alta"},
    ]
    _BIOMETRIA_MISURA = [
        {
            "misura": "template cifrato sul badge in possesso del dipendente",
            "rischio_mitigato": "accesso abusivo ai template biometrici",
            "efficacia": "alta",
        },
    ]

    def _biometria(self, misure):
        return _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="Rilevazione presenze con impronta digitale",
            finalita="controllo accessi e presenze",
            necessita_proporzionalita="alternative meno invasive valutate e scartate",
            rischi=self._BIOMETRIA_RISCHIO,
            misure_mitigazione=misure,
        )

    def test_residual_risk_takes_measures_into_account(self):
        # alta x alta = 9 (molto_alto) inherent; the best measure (efficacia alta) removes 2 steps
        senza = self._biometria([])
        con = self._biometria(self._BIOMETRIA_MISURA)
        assert senza["matrice_rischi"][0]["score"] == 9
        assert senza["matrice_rischi"][0]["livello_residuo"] == "molto_alto"
        assert senza["rischio_residuo"].startswith("molto_alto")
        assert con["matrice_rischi"][0]["livello_rischio"] == "molto_alto"  # inherent unchanged
        assert con["matrice_rischi"][0]["livello_residuo"] == "medio"
        assert con["rischio_residuo"].startswith("medio")
        assert con["rischio_inerente"] == "molto_alto"
        assert con["consultazione_preventiva_necessaria"] is False
        assert senza["consultazione_preventiva_necessaria"] is True

    def test_efficacia_media_leaves_high_residual_and_consultation(self):
        # media = 1 step: molto_alto -> alto, still a high risk after the measure (art. 36(1))
        misura = [{**self._BIOMETRIA_MISURA[0], "efficacia": "media"}]
        r = self._biometria(misura)
        assert r["matrice_rischi"][0]["livello_residuo"] == "alto"
        assert r["consultazione_preventiva_necessaria"] is True

    def test_efficacia_bassa_does_not_reduce(self):
        misura = [{**self._BIOMETRIA_MISURA[0], "efficacia": "bassa"}]
        r = self._biometria(misura)
        assert r["matrice_rischi"][0]["livello_residuo"] == "molto_alto"

    def test_measure_matching_no_risk_is_ignored_with_warning(self):
        misura = [{"misura": "altra", "rischio_mitigato": "rischio inesistente", "efficacia": "alta"}]
        r = self._biometria(misura)
        assert r["matrice_rischi"][0]["livello_residuo"] == "molto_alto"
        assert r["avvisi"] and "non corrisponde a nessun rischio" in r["avvisi"][0]

    # Art. 36(1) GDPR: a single risk scored 6 ("alto", the tool's own label for elevated) with no
    # measure at all is an elevated risk not attenuated: prior consultation is required.
    def test_alto_without_measures_requires_consultation(self):
        r = _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="Scoring creditizio automatizzato",
            finalita="valutazione del merito creditizio",
            necessita_proporzionalita="necessario",
            rischi=[{"desc": "decisione automatizzata discriminatoria", "probabilita": "media", "gravita": "alta"}],
            misure_mitigazione=[],
        )
        assert r["matrice_rischi"][0]["score"] == 6
        assert r["matrice_rischi"][0]["livello_rischio"] == "alto"
        assert r["consultazione_preventiva_necessaria"] is True
        assert "art. 36(1)" in r["testo"]

    # Art. 36(1): with a medio residual level (score 3-4) the consultation is not required.
    def test_medio_residual_no_consultation(self):
        r = _genera_dpia_impl(
            titolare=_TITOLARE,
            descrizione="x",
            finalita="y",
            necessita_proporzionalita="z",
            rischi=[{"desc": "perdita dati per guasto", "probabilita": "bassa", "gravita": "molto_alta"}],
            misure_mitigazione=[],
        )
        assert r["matrice_rischi"][0]["score"] == 4
        assert r["consultazione_preventiva_necessaria"] is False

    # Art. 36(2) GDPR: eight weeks, extendable by six.
    def test_consultation_terms_art36_2(self):
        r = self._biometria([])
        assert "8 settimane" in r["testo"] and "6 settimane" in r["testo"]


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

    def test_trasferimento_extra_ue_non_e_un_criterio_wp248(self):
        # Garante provv. 467/2018: the nine WP248 rev.01 criteria include no transfer outside the
        # EU. Large-scale CRM with servers in the USA is one criterion (5), below the threshold of 2.
        r = _verifica_necessita_dpia_impl(
            tipo_trattamento="CRM su larga scala con server negli USA",
            larga_scala=True,
            trasferimento_extra_ue=True,
        )
        assert r["n_criteri"] == 1
        assert r["dpia_necessaria"] is False
        assert any("paesi terzi" in a for a in r["avvertenze"])

    def test_decisioni_automatizzate_da_sole_richiedono_la_dpia(self):
        # Art. 35(3)(a) GDPR and item 2 of the Garante's list (Allegato 1 to provv. 467/2018):
        # one feature is enough, whatever the WP248 count (here 1).
        r = _verifica_necessita_dpia_impl(tipo_trattamento="scoring bancario", valutazione_scoring=True)
        assert r["n_criteri"] == 1
        assert r["dpia_necessaria"] is True
        assert any(c.startswith("Art. 35(3)(a)") for c in r["art35_3"])
        assert any(v.startswith("Voce 2:") for v in r["lista_garante_match"])

    @pytest.mark.parametrize(
        ("voce", "parametri"),
        [
            (3, {"monitoraggio_sistematico": True}),  # item 3: no large-scale qualifier
            (5, {"rapporto_di_lavoro": True}),  # item 5: employment relationship, remote control
            (9, {"incrocio_dataset": True}),  # item 9: interconnection, combination, comparison
        ],
    )
    def test_voci_autonome_dell_elenco_del_garante(self, voce, parametri):
        # Art. 35(4) GDPR: processing on the Garante's list is subject to the assessment; items
        # 3, 5 and 9 carry neither "larga scala" nor "almeno un altro dei criteri".
        r = _verifica_necessita_dpia_impl(tipo_trattamento="x", **parametri)
        assert r["dpia_necessaria"] is True
        assert any(v.startswith(f"Voce {voce}:") for v in r["lista_garante_match"])

    def test_voce_10_dati_art9_interconnessi(self):
        # Item 10: art. 9/10 data interconnected with data collected for other purposes.
        r = _verifica_necessita_dpia_impl(tipo_trattamento="x", dati_sensibili=True, incrocio_dataset=True)
        assert any(v.startswith("Voce 10:") for v in r["lista_garante_match"])

    def test_voce_6_richiede_la_larga_scala(self):
        # Item 6 concerns "trattamenti non occasionali" = large scale (Garante's clarification).
        senza = _verifica_necessita_dpia_impl(tipo_trattamento="x", soggetti_vulnerabili=True)
        assert senza["lista_garante_match"] == []
        assert any(v.startswith("Voce 6:") for v in senza["lista_garante_da_verificare"])
        con = _verifica_necessita_dpia_impl(tipo_trattamento="x", soggetti_vulnerabili=True, larga_scala=True)
        assert any(v.startswith("Voce 6:") for v in con["lista_garante_match"])

    def test_voce_7_richiede_un_altro_criterio_wp248(self):
        # Item 7: innovative technology "ogniqualvolta ricorra anche almeno un altro" WP248 criterion.
        solo = _verifica_necessita_dpia_impl(tipo_trattamento="x", nuove_tecnologie=True)
        assert solo["lista_garante_match"] == []
        assert solo["dpia_necessaria"] is False
        assert any(v.startswith("Voce 7:") for v in solo["lista_garante_da_verificare"])
        con = _verifica_necessita_dpia_impl(tipo_trattamento="x", nuove_tecnologie=True, profilazione=True)
        assert any(v.startswith("Voce 7:") for v in con["lista_garante_match"])

    @pytest.mark.parametrize(("parametro", "voce"), [("dati_biometrici", 11), ("dati_genetici", 12)])
    def test_voci_11_e_12_biometrici_e_genetici_sistematici(self, parametro, voce):
        # Items 11 and 12: "trattamenti sistematici" = large scale (Garante's clarification).
        senza = _verifica_necessita_dpia_impl(tipo_trattamento="x", **{parametro: True})
        assert senza["n_criteri"] == 1  # art. 9 data: WP248 criterion 4
        assert senza["dpia_necessaria"] is False
        assert any(v.startswith(f"Voce {voce}:") for v in senza["lista_garante_da_verificare"])
        con = _verifica_necessita_dpia_impl(tipo_trattamento="x", larga_scala=True, **{parametro: True})
        assert any(v.startswith(f"Voce {voce}:") for v in con["lista_garante_match"])
        assert con["dpia_necessaria"] is True

    def test_art35_3_b_categorie_particolari_su_larga_scala(self):
        # Art. 35(3)(b) GDPR: large-scale processing of art. 9 or art. 10 data.
        r = _verifica_necessita_dpia_impl(tipo_trattamento="x", dati_sensibili=True, larga_scala=True)
        assert any(c.startswith("Art. 35(3)(b)") for c in r["art35_3"])
        assert r["dpia_necessaria"] is True

    def test_elenco_garante_riproduce_le_dodici_voci_dell_allegato_1(self):
        # Allegato 1 to provv. 467/2018 (GU n. 269 of 19/11/2018): twelve items, numbered.
        from src.tools.privacy_gdpr import _DPIA

        elenco = _DPIA["lista_garante_italiano"]
        assert [v.split(".")[0] for v in elenco] == [str(n) for n in range(1, 13)]
        assert "controllo a distanza dell’attività dei dipendenti" in elenco[4]  # item 5
        assert "interconnessi con altri dati personali raccolti per finalità diverse" in elenco[9]  # item 10
        assert "minori, disabili, anziani, infermi di mente, pazienti, richiedenti asilo" in elenco[5]  # item 6
        assert not any("biometrici di dipendenti" in v for v in elenco)

    def test_esenzione_art_35_10_richiede_la_valutazione_generale(self):
        # Art. 35(10) GDPR: besides the legal basis of art. 6(1)(c)/(e), a general impact assessment
        # must already have been carried out when that legal basis was adopted.
        r = _verifica_necessita_dpia_impl(tipo_trattamento="x")
        art_10 = [e for e in r["esenzioni_possibili"] if e.startswith("Art. 35(10)")]
        assert len(art_10) == 1
        assert "valutazione d'impatto generale" in art_10[0]
        assert "6(1), lett. c) o e)" in art_10[0]


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

    def _caso_sanitario(self, tipo, misure):
        # 50 data subjects, health data, high impact: 3 + 1 (special data) -> "molto probabile".
        return _valutazione_data_breach_impl(
            tipo_violazione=tipo,
            categorie_dati=["dati sanitari"],
            n_interessati=50,
            dati_particolari=True,
            misure_protezione=misure,
            impatto="alto",
        )

    @pytest.mark.parametrize("tipo", ["disponibilita", "integrita"])
    def test_cifratura_non_esclude_comunicazione_per_perdita_o_alterazione(self, tipo):
        # Art. 34(3)(a) GDPR: exemption for measures that make the data unintelligible, i.e. for
        # confidentiality. EDPB Guidelines 9/2022 par. 76 and 79: even if encrypted, a loss or
        # alteration can harm data subjects and "communication to data subjects would be required".
        r = self._caso_sanitario(tipo, ["cifratura AES-256"])
        assert r["livello_rischio"] == "molto probabile"
        assert r["comunicazione_interessati"] is True
        assert r["esenzione_art34_3_a"] is False
        assert r["cifratura_attiva"] is True

    def test_cifratura_esclude_comunicazione_per_riservatezza(self):
        # Art. 34(3)(a) + EDPB 9/2022 par. 76: encrypted data with the key intact are unintelligible.
        r = self._caso_sanitario("confidenzialita", ["cifratura AES-256"])
        assert r["comunicazione_interessati"] is False
        assert r["esenzione_art34_3_a"] is True
        assert r["notifica_garante"] is True  # prudential: the tool cannot know the key is intact

    def test_pseudonimizzazione_non_esclude_comunicazione(self):
        # EDPB 9/2022 par. 112: "pseudonymisation techniques alone cannot be regarded as making the
        # data unintelligible"; art. 4(5) GDPR: pseudonymised data remain attributable.
        r = self._caso_sanitario("confidenzialita", ["pseudonimizzazione"])
        assert r["comunicazione_interessati"] is True
        assert r["esenzione_art34_3_a"] is False
        assert r["cifratura_attiva"] is False
        assert any("112" in a for a in r["azioni_consigliate"])

    def test_pseudonimizzazione_e_cifratura_insieme_riservatezza(self):
        # The encryption alone carries the exemption; pseudonymisation next to it changes nothing.
        r = self._caso_sanitario("confidenzialita", ["pseudonimizzazione", "cifratura AES-256"])
        assert r["comunicazione_interessati"] is False
        assert r["esenzione_art34_3_a"] is True

    def test_soglia_100000_interessati_e_convenzione_del_tool(self):
        # Neither art. 33-34 nor EDPB 9/2022 par. 118 fixes a numeric threshold: the +1 above
        # 100,000 data subjects is the tool's convention (boundary 100,000 / 100,001).
        base = dict(tipo_violazione="confidenzialita", categorie_dati=["email"], impatto="medio")
        assert _valutazione_data_breach_impl(n_interessati=100_000, **base)["livello_rischio"] == "possibile"
        assert _valutazione_data_breach_impl(n_interessati=100_001, **base)["livello_rischio"] == "probabile"


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

    def test_criteri_art83_2_lettere_a_k(self):
        # Art. 83(2) GDPR lists eleven elements, a) to k); k) is the residual clause
        # "eventuali altri fattori aggravanti o attenuanti ... benefici finanziari conseguiti
        # o perdite evitate".
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_4")
        assert [c["id"] for c in r["criteri_art83_2"]] == list("abcdefghijk")
        assert "benefici finanziari" in r["criteri_art83_2"][-1]["parametro"]

    @pytest.mark.parametrize(
        ("tipo", "fatturato", "atteso"),
        [
            ("art83_5", 1_000_000_000, 40_000_000),  # art. 83(5): 4% of 1 bn = 40 mln > 20 mln
            ("art83_5", 500_000_000, 20_000_000),  # boundary: 4% = 20 mln = fixed amount
            ("art83_5", 400_000_000, 20_000_000),  # 4% = 16 mln < 20 mln: fixed amount
            ("art83_4", 1_000_000_000, 20_000_000),  # art. 83(4): 2% of 1 bn = 20 mln > 10 mln
            ("art83_6", 1_000_000_000, 40_000_000),  # art. 83(6): same 20 mln / 4% pair
        ],
    )
    def test_massimale_effettivo_strutturato(self, tipo, fatturato, atteso):
        # "se superiore": the applicable maximum is the higher of the fixed amount and the
        # percentage of the total worldwide annual turnover (art. 83(4)-(6)); it is exposed in
        # a structured field, not only in the note.
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione=tipo, fatturato_annuo=fatturato)
        assert r["massimale"]["effettivo_euro"] == atteso

    def test_fasce_di_gravita_edpb_senza_fatturato(self):
        # EDPB Guidelines 04/2022 v2.1 par. 60: starting amount 0-10% (low), 10-20% (medium),
        # 20-100% (high) of the applicable legal maximum; art. 83(4) maximum is 10 mln.
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_4")
        assert r["range_per_gravita"] == {
            "bassa": {"minimo": 0, "massimo": 1_000_000},
            "media": {"minimo": 1_000_000, "massimo": 2_000_000},
            "alta": {"minimo": 2_000_000, "massimo": 10_000_000},
        }
        assert r["gravita"] == "bassa"
        assert "Gravità non indicata" in r["avvertenza"]

    def test_gravita_esplicita_seleziona_la_fascia(self):
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5", gravita="media")
        # par. 60: medium = 10-20% of 20 mln
        assert (r["range_stimato"]["minimo"], r["range_stimato"]["massimo"]) == (2_000_000, 4_000_000)
        assert "Gravità non indicata" not in r["avvertenza"]

    def test_gravita_non_valida(self):
        assert "errore" in _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5", gravita="grave")

    def test_esempio_6b_linee_guida_edpb_microimpresa(self):
        # EDPB 04/2022 Example 6b: turnover EUR 500,000, high seriousness, art. 83(5): starting
        # amount 4-20 mln (20-100% of 20 mln); the size adjustment of par. 65 (turnover <= 2 mln:
        # 0.2%-0.4% of the starting amount) gives 4 mln x 0.2% = 8,000 to 20 mln x 0.4% = 80,000.
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5", fatturato_annuo=500_000, gravita="alta")
        assert r["punto_di_partenza_edpb"]["rettifica_fatturato_pct"] == [0.2, 0.4]
        assert r["range_stimato"]["minimo"] == pytest.approx(8_000)
        assert r["range_stimato"]["massimo"] == pytest.approx(80_000)

    def test_esempio_6a_linee_guida_edpb_catena_da_450_milioni(self):
        # EDPB 04/2022 Example 6a: turnover EUR 450 mln, low seriousness, art. 83(5): starting
        # amount between 0 and 2 mln (0-10% of 20 mln); tier 250-500 mln keeps 40%-100% of it.
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5", fatturato_annuo=450_000_000, gravita="bassa")
        assert r["massimale"]["effettivo_euro"] == 20_000_000
        assert r["punto_di_partenza_edpb"]["rettifica_fatturato_pct"] == [40, 100]
        assert r["range_stimato"]["minimo"] == pytest.approx(0)
        assert r["range_stimato"]["massimo"] == pytest.approx(2_000_000)

    @pytest.mark.parametrize(
        ("fatturato", "rettifica"),
        [
            (2_000_000, [0.2, 0.4]),  # par. 65: "not exceeding 2 million"
            (2_000_001, [0.3, 2]),
            (10_000_000, [0.3, 2]),  # "not exceeding 10 million"
            (10_000_001, [1.5, 10]),
            (50_000_000, [1.5, 10]),
            (50_000_001, [8, 20]),  # par. 66: 50 to 100 mln
            (100_000_001, [15, 50]),
            (250_000_001, [40, 100]),
            (500_000_000, [40, 100]),
            (500_000_001, None),  # above 500 mln: no adjustment (par. 66, last indent)
        ],
    )
    def test_rettifica_per_fatturato_confini_edpb(self, fatturato, rettifica):
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_4", fatturato_annuo=fatturato)
        assert r["punto_di_partenza_edpb"]["rettifica_fatturato_pct"] == rettifica

    def test_oltre_500_milioni_nessuna_rettifica_gravita_alta(self):
        # EDPB par. 66: above 500 mln no size adjustment; art. 83(5) with 1 bn: dynamic maximum
        # 40 mln, high band 20-100% = 8-40 mln (par. 60).
        r = _calcolo_sanzione_gdpr_impl(tipo_violazione="art83_5", fatturato_annuo=1_000_000_000, gravita="alta")
        assert (r["range_stimato"]["minimo"], r["range_stimato"]["massimo"]) == (8_000_000, 40_000_000)

    def test_correttivi_mai_oltre_il_massimale(self):
        # Art. 83(4)-(6): the fine can never exceed the applicable maximum, whatever the correction.
        r = _calcolo_sanzione_gdpr_impl(
            tipo_violazione="art83_5",
            fattori_aggravanti=["a"] * 5,
            precedenti=True,
            gravita="alta",
        )
        assert r["fattori_analisi"]["moltiplicatore_applicato"] == 2.75
        assert r["range_stimato"]["massimo"] == 20_000_000
        assert r["range_stimato"]["minimo"] <= 20_000_000

    def test_microimpresa_con_cinque_attenuanti_sotto_il_tetto_edpb(self):
        # Turnover 2 mln, art. 83(4): even the top of the high band (100% of 10 mln) after the
        # 0.4% adjustment of par. 65 is 40,000; five mitigating factors only lower it.
        r = _calcolo_sanzione_gdpr_impl(
            tipo_violazione="art83_4",
            fatturato_annuo=2_000_000,
            fattori_attenuanti=["a"] * 5,
            gravita="alta",
        )
        assert r["range_stimato"]["massimo"] <= 40_000


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
            dpo="Mario Rossi — dpo@example.com",
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

    # Art. 33(3)(b) GDPR: "il nome e i dati di contatto del responsabile della protezione dei dati
    # o di altro punto di contatto presso cui ottenere più informazioni".
    def test_altro_punto_di_contatto_soddisfa_lett_b(self):
        r = self._base(dpo="", punto_contatto="Ufficio privacy, privacy@example.com")
        assert r["elementi_art33_3"]["b_contatti_dpo"] is True
        assert r["tutti_elementi_presenti"] is True
        assert "privacy@example.com" in r["testo"]

    def test_senza_dpo_ne_punto_di_contatto_lett_b_mancante(self):
        r = self._base(dpo="")
        assert r["elementi_art33_3"]["b_contatti_dpo"] is False
        assert r["tutti_elementi_presenti"] is False

    # The contact section is letter b), not a): art. 33(3)(a) is the nature of the breach.
    def test_sezione_contatti_etichettata_lett_b(self):
        r = self._base()
        riga = next(line for line in r["testo"].splitlines() if line.startswith("1. "))
        assert "[art. 33(3)(b)]" in riga

    # Art. 33(3)(a): also "le categorie e il numero approssimativo di registrazioni dei dati
    # personali in questione".
    def test_numero_registrazioni_lett_a(self):
        r = self._base(n_registrazioni=4800)
        assert "Numero approssimativo di registrazioni dei dati personali in questione: 4.800" in r["testo"]
        senza = self._base()
        assert "registrazioni dei dati personali in questione: [indicare, ove possibile]" in senza["testo"]
        assert self._base(n_registrazioni=-1)["errore"]

    # Italian document: thousands separator is the dot.
    def test_numero_interessati_formato_italiano(self):
        assert "Numero approssimativo di interessati: 1.200" in self._base()["testo"]

    # A breach cannot follow the moment the controller became aware of it (art. 33(1): the 72
    # hours run from awareness of the breach).
    def test_violazione_dopo_la_scoperta_avviso(self):
        r = self._base(data_violazione="2025-01-16", data_scoperta="2025-01-15")
        assert "errore" not in r
        assert "date incoerenti" in r["avvisi"][0]
        assert "ATTENZIONE: date incoerenti" in r["testo"]
        # the 72 h deadline still runs from the discovery date
        assert "18/01/2025" in r["termine_scadenza"]
        # same instant is coherent
        ok = self._base(data_violazione="2025-01-15T08:00", data_scoperta="2025-01-15T08:00")
        assert ok["avvisi"] == [] and "date incoerenti" not in ok["testo"]

    # Since 1 July 2021 (provv. Garante 27/05/2021 n. 209) the channel is the on-line procedure;
    # the heading no longer carries unofficial e-mail boxes.
    def test_intestazione_solo_procedura_telematica(self):
        t = self._base()["testo"]
        assert "https://servizi.gpdp.it/databreach/" in t
        assert "datibreach@gpdp.it" not in t and "garante@gpdp.it" not in t

    # Art. 33(1): 72 hours from awareness (unchanged by the correction).
    def test_termine_72_ore_invariato(self):
        r = self._base(data_scoperta="2026-09-22T12:00", data_violazione="2026-09-20T22:00")
        assert r["termine_scadenza"] == "25/09/2026 ore 12:00"
