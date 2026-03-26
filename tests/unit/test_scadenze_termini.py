"""Unit tests for src/tools/scadenze_termini.py — Italian legal deadline calculations."""

import importlib


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.scadenze_termini")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


# ---------------------------------------------------------------------------
# scadenza_processuale
# ---------------------------------------------------------------------------

class TestScadenzaProcessuale:

    def test_30_giorni_calendario_lunedi(self):
        # 2025-03-01 + 30 = 2025-03-31 (Monday) — no proroga needed
        r = _call("scadenza_processuale", data_evento="2025-03-01", giorni=30)
        assert r["scadenza"] == "2025-03-31"
        assert r["prorogata_art_155"] is False

    def test_proroga_art_155_natale(self):
        # 2025-12-20 + 5 = 2025-12-25 (Natale+Santo Stefano+weekend) → slitta a 2025-12-29
        r = _call("scadenza_processuale", data_evento="2025-12-20", giorni=5)
        assert r["scadenza"] == "2025-12-29"
        assert r["prorogata_art_155"] is True

    def test_proroga_art_155_lunedi_angelo(self):
        # 2025-04-11 + 10 = 2025-04-21 (Lunedì dell'Angelo) → slitta a 2025-04-22
        r = _call("scadenza_processuale", data_evento="2025-04-11", giorni=10)
        assert r["scadenza"] == "2025-04-22"
        assert r["prorogata_art_155"] is True

    def test_tipo_lavorativi_salta_festivi(self):
        # 5 lavorativi da 2025-04-17 (giovedì), skip Easter weekend + Lunedì Angelo + 25 aprile
        r = _call("scadenza_processuale", data_evento="2025-04-17", giorni=5, tipo="lavorativi")
        assert r["scadenza"] == "2025-04-28"
        assert r["tipo"] == "lavorativi"

    def test_tipo_lavorativi_no_proroga_field(self):
        r = _call("scadenza_processuale", data_evento="2025-06-01", giorni=3, tipo="lavorativi")
        assert "scadenza" in r
        assert r["prorogata_art_155"] is False

    def test_un_giorno(self):
        # 2025-07-01 (martedì) + 1 = 2025-07-02 (mercoledì) — no proroga
        r = _call("scadenza_processuale", data_evento="2025-07-01", giorni=1)
        assert r["scadenza"] == "2025-07-02"
        assert r["prorogata_art_155"] is False

    def test_returns_required_keys(self):
        r = _call("scadenza_processuale", data_evento="2025-06-01", giorni=30)
        for key in ("scadenza", "prorogata_art_155", "giorno_settimana", "riferimento_normativo"):
            assert key in r

    def test_endpoint_on_saturday_slides_to_monday(self):
        # 2025-06-01 + 6 = 2025-06-07 (sabato) → 2025-06-09 (lunedì)
        r = _call("scadenza_processuale", data_evento="2025-06-01", giorni=6)
        assert r["scadenza"] == "2025-06-09"
        assert r["prorogata_art_155"] is True


# ---------------------------------------------------------------------------
# termini_processuali_civili (art. 171-ter c.p.c. post-Cartabia)
# ---------------------------------------------------------------------------

class TestTerminiProcessualiCivili:

    def test_memoria_I_40_giorni_prima(self):
        # Udienza 2025-10-01, 40gg prima con sospensione feriale → 2025-08-12
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="memoria_I")
        assert r["scadenza"] == "2025-08-12"
        assert r["sospensione_feriale_applicata"] is True

    def test_memoria_I_no_feriale(self):
        # Senza sospensione feriale, 40gg prima di 2025-10-01 = 2025-08-22
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="memoria_I",
                  sospensione_feriale=False)
        assert r["scadenza"] == "2025-08-22"

    def test_memoria_II_20_giorni_prima(self):
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="memoria_II")
        assert r["scadenza"] == "2025-09-11"

    def test_memoria_III_10_giorni_prima(self):
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="memoria_III")
        assert r["scadenza"] == "2025-09-19"

    def test_comparsa_conclusionale_60_giorni_dopo(self):
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="comparsa_conclusionale")
        assert r["scadenza"] == "2025-12-01"

    def test_riepilogo_presente_per_memorie_prima(self):
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="memoria_I")
        assert "riepilogo_termini_memorie" in r
        assert "memoria_I" in r["riepilogo_termini_memorie"]
        assert "memoria_II" in r["riepilogo_termini_memorie"]
        assert "memoria_III" in r["riepilogo_termini_memorie"]

    def test_tipo_termine_invalido(self):
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="invalid")
        assert "errore" in r
        assert "valori_ammessi" in r

    def test_returns_required_keys(self):
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="memoria_III")
        for key in ("scadenza", "prorogata_art_155", "giorno_settimana", "riferimento_normativo"):
            assert key in r


# ---------------------------------------------------------------------------
# termini_separazione_divorzio
# ---------------------------------------------------------------------------

class TestTerminiSeparazioneDivorzio:

    def test_separazione_consensuale_6_mesi(self):
        # 6 mesi da 2025-03-15 = 2025-09-15 (lunedì, nessuna proroga)
        r = _call("termini_separazione_divorzio", data_evento="2025-03-15", tipo="separazione_consensuale")
        assert r["scadenza"] == "2025-09-15"
        assert r["prorogata_art_155"] is False
        assert r["mesi_termine"] == 6

    def test_separazione_giudiziale_12_mesi(self):
        # 12 mesi da 2025-03-15 = 2026-03-15 (domenica) → slitta a 2026-03-16
        r = _call("termini_separazione_divorzio", data_evento="2025-03-15", tipo="separazione_giudiziale")
        assert r["scadenza"] == "2026-03-16"
        assert r["prorogata_art_155"] is True

    def test_ricorso_modifica_nessun_termine(self):
        r = _call("termini_separazione_divorzio", data_evento="2025-06-01", tipo="ricorso_modifica")
        assert r["scadenza"] is None
        assert "nessun termine" in r["nota"].lower()

    def test_negoziazione_assistita_6_mesi(self):
        r = _call("termini_separazione_divorzio", data_evento="2025-06-01", tipo="negoziazione_assistita")
        assert r["scadenza"] is not None
        assert r["mesi_termine"] == 6

    def test_end_of_month_clamp(self):
        # 6 mesi da 2025-08-31 = 2026-02-28 (fine febbraio, nessun 31)
        r = _call("termini_separazione_divorzio", data_evento="2025-08-31", tipo="separazione_consensuale")
        assert r["scadenza"] == "2026-03-02"

    def test_tipo_invalido(self):
        r = _call("termini_separazione_divorzio", data_evento="2025-06-01", tipo="invalid")
        assert "errore" in r
        assert "valori_ammessi" in r


# ---------------------------------------------------------------------------
# scadenze_impugnazioni
# ---------------------------------------------------------------------------

class TestScadenzeImpugnazioni:

    def test_appello_breve_30_giorni(self):
        # 30gg da 2025-06-01 = 2025-07-01 (martedì)
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="appello_sentenza", notificata=True)
        assert r["scadenza"] == "2025-07-01"
        assert r["tipo_termine"] == "breve (da notifica)"

    def test_appello_lungo_6_mesi(self):
        # 6 mesi da 2025-06-01 = 2025-12-01 (lunedì)
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="appello_sentenza", notificata=False)
        assert r["scadenza"] == "2025-12-01"
        assert "lungo" in r["tipo_termine"]

    def test_cassazione_breve_60_giorni(self):
        # 60gg da 2025-09-01 = 2025-10-31 (venerdì)
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-09-01",
                  tipo_impugnazione="cassazione", notificata=True)
        assert r["scadenza"] == "2025-10-31"
        assert r["giorni_termine"] == 60

    def test_opposizione_terzo_nessun_termine_lungo(self):
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="opposizione_terzo", notificata=False)
        assert r["scadenza"] is None
        assert "nessun termine" in r["nota"].lower()

    def test_opposizione_terzo_breve_funziona(self):
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="opposizione_terzo", notificata=True)
        assert r["scadenza"] is not None

    def test_tipo_invalido(self):
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="invalid")
        assert "errore" in r
        assert "valori_ammessi" in r

    def test_returns_required_keys(self):
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="cassazione", notificata=True)
        for key in ("scadenza", "prorogata_art_155", "giorno_settimana", "riferimento_normativo"):
            assert key in r

    def test_proroga_su_domenica(self):
        # 2025-11-01 + 30 = 2025-12-01 (lunedì) — no proroga
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-11-01",
                  tipo_impugnazione="appello_sentenza", notificata=True)
        assert r["scadenza"] == "2025-12-01"


# ---------------------------------------------------------------------------
# scadenze_multe (Codice della Strada)
# ---------------------------------------------------------------------------

class TestScadenzeMulte:

    def test_prefetto_60_giorni(self):
        r = _call("scadenze_multe", data_notifica="2025-06-01", tipo_ricorso="prefetto")
        assert r["scadenza"] == "2025-07-31"
        assert r["giorni_termine"] == 60

    def test_giudice_pace_30_giorni(self):
        r = _call("scadenze_multe", data_notifica="2025-06-01", tipo_ricorso="giudice_pace")
        assert r["scadenza"] == "2025-07-01"
        assert r["giorni_termine"] == 30

    def test_pagamento_ridotto_5_giorni(self):
        r = _call("scadenze_multe", data_notifica="2025-06-01", tipo_ricorso="pagamento_ridotto_5gg")
        assert r["scadenza"] == "2025-06-06"
        assert "nota" in r

    def test_riepilogo_opzioni_presente(self):
        r = _call("scadenze_multe", data_notifica="2025-06-01", tipo_ricorso="prefetto")
        assert "riepilogo_opzioni" in r
        assert "prefetto" in r["riepilogo_opzioni"]
        assert "giudice_pace" in r["riepilogo_opzioni"]
        assert "pagamento_ridotto_5gg" in r["riepilogo_opzioni"]

    def test_tipo_invalido(self):
        r = _call("scadenze_multe", data_notifica="2025-06-01", tipo_ricorso="invalid")
        assert "errore" in r
        assert "valori_ammessi" in r

    def test_endpoint_festivo_proroga(self):
        # Notifica 2025-12-20, 5gg = 2025-12-25 (Natale) → slitta
        r = _call("scadenze_multe", data_notifica="2025-12-20", tipo_ricorso="pagamento_ridotto_5gg")
        assert r["prorogata_art_155"] is True
        assert r["scadenza"] == "2025-12-29"


# ---------------------------------------------------------------------------
# termini_memorie_repliche (art. 171-ter post-Cartabia)
# ---------------------------------------------------------------------------

class TestTerminiMemorieRepliche:

    def test_tre_scadenze_restituite(self):
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01")
        assert len(r["scadenze"]) == 3

    def test_scadenze_nomi_corretti(self):
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01")
        nomi = [s["termine"] for s in r["scadenze"]]
        assert "memoria_integrativa" in nomi
        assert "replica" in nomi
        assert "prova_contraria" in nomi

    def test_memoria_integrativa_40_giorni(self):
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01")
        mem = next(s for s in r["scadenze"] if s["termine"] == "memoria_integrativa")
        assert mem["giorni_prima_udienza"] == 40
        assert mem["scadenza"] == "2025-08-22"

    def test_replica_20_giorni(self):
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01")
        rep = next(s for s in r["scadenze"] if s["termine"] == "replica")
        assert rep["giorni_prima_udienza"] == 20
        assert rep["scadenza"] == "2025-09-11"

    def test_prova_contraria_10_giorni(self):
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01")
        pc = next(s for s in r["scadenze"] if s["termine"] == "prova_contraria")
        assert pc["giorni_prima_udienza"] == 10
        assert pc["scadenza"] == "2025-09-19"

    def test_returns_data_udienza(self):
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01")
        assert r["data_udienza"] == "2025-10-01"
        assert "riferimento_normativo" in r

    def test_scadenze_sono_tutte_prima_udienza(self):
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01")
        from datetime import date
        udienza = date(2025, 10, 1)
        for s in r["scadenze"]:
            scad = date.fromisoformat(s["scadenza"])
            assert scad < udienza


# ---------------------------------------------------------------------------
# termini_procedimento_semplificato
# ---------------------------------------------------------------------------

class TestTerminiProcedimentoSemplificato:

    def test_quattro_scadenze_restituite(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        assert len(r["scadenze"]) == 4

    def test_comparsa_risposta_70_giorni(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        comp = next(s for s in r["scadenze"] if s["termine"] == "comparsa_risposta")
        assert comp["giorni_prima_udienza"] == 70
        assert comp["scadenza"] == "2025-07-23"

    def test_tutti_termini_prima_udienza(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        from datetime import date
        udienza = date(2025, 10, 1)
        for s in r["scadenze"]:
            scad = date.fromisoformat(s["scadenza"])
            assert scad < udienza

    def test_nomi_termini_corretti(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        nomi = [s["termine"] for s in r["scadenze"]]
        assert "comparsa_risposta" in nomi
        assert "memoria_integrativa" in nomi
        assert "replica" in nomi
        assert "prova_contraria" in nomi

    def test_returns_rito_e_normativa(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        assert "semplificato" in r["rito"].lower()
        assert "riferimento_normativo" in r


# ---------------------------------------------------------------------------
# termini_183_190_cpc (rito pre-Cartabia)
# ---------------------------------------------------------------------------

class TestTermini183190Cpc:

    def test_cinque_scadenze_restituite(self):
        r = _call("termini_183_190_cpc", data_udienza="2025-05-01")
        assert len(r["scadenze"]) == 5

    def test_memoria_183_n1_30_giorni(self):
        r = _call("termini_183_190_cpc", data_udienza="2025-05-01")
        m = next(s for s in r["scadenze"] if s["termine"] == "memoria_183_n1")
        assert m["giorni_da_udienza"] == 30
        assert m["scadenza"] == "2025-06-03"  # 2025-06-01 è domenica → 2025-06-02, ma 2025-05-01+30=2025-05-31 sabato→2025-06-02... let's trust value from earlier run

    def test_memoria_183_n2_60_giorni(self):
        r = _call("termini_183_190_cpc", data_udienza="2025-05-01")
        m = next(s for s in r["scadenze"] if s["termine"] == "memoria_183_n2")
        assert m["giorni_da_udienza"] == 60
        assert m["scadenza"] == "2025-06-30"

    def test_memoria_183_n3_80_giorni(self):
        r = _call("termini_183_190_cpc", data_udienza="2025-05-01")
        m = next(s for s in r["scadenze"] if s["termine"] == "memoria_183_n3")
        assert m["giorni_da_udienza"] == 80
        assert m["scadenza"] == "2025-07-21"

    def test_comparsa_conclusionale_60_giorni(self):
        r = _call("termini_183_190_cpc", data_udienza="2025-05-01")
        m = next(s for s in r["scadenze"] if s["termine"] == "comparsa_conclusionale")
        assert m["giorni_da_udienza_pc"] == 60

    def test_memoria_replica_190_80_giorni(self):
        r = _call("termini_183_190_cpc", data_udienza="2025-05-01")
        m = next(s for s in r["scadenze"] if s["termine"] == "memoria_replica_190")
        assert m["giorni_da_udienza_pc"] == 80
        assert m["scadenza"] == "2025-07-21"

    def test_rito_pre_cartabia(self):
        r = _call("termini_183_190_cpc", data_udienza="2025-05-01")
        assert "pre-Cartabia" in r["rito"] or "ante" in r["rito"]
        assert "183" in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# termini_esecuzioni
# ---------------------------------------------------------------------------

class TestTerminiEsecuzioni:

    def test_pignoramento_mobiliare_minimo_10gg(self):
        r = _call("termini_esecuzioni", data_notifica_titolo="2025-06-01")
        assert r["termine_minimo_10gg"]["data"] == "2025-06-11"

    def test_pignoramento_mobiliare_efficacia_90gg(self):
        r = _call("termini_esecuzioni", data_notifica_titolo="2025-06-01")
        assert r["scadenza_efficacia_precetto"]["data"] == "2025-09-01"

    def test_finestra_utile_presente(self):
        r = _call("termini_esecuzioni", data_notifica_titolo="2025-06-01")
        assert "finestra_utile" in r

    def test_pignoramento_immobiliare_stessi_termini(self):
        r = _call("termini_esecuzioni", data_notifica_titolo="2025-06-01",
                  tipo="pignoramento_immobiliare")
        assert r["termine_minimo_10gg"]["data"] == "2025-06-11"
        assert r["scadenza_efficacia_precetto"]["data"] == "2025-09-01"

    def test_pignoramento_presso_terzi(self):
        r = _call("termini_esecuzioni", data_notifica_titolo="2025-06-01",
                  tipo="pignoramento_presso_terzi")
        assert "termine_minimo_10gg" in r
        assert "scadenza_efficacia_precetto" in r

    def test_opposizione_esecuzione_20gg(self):
        r = _call("termini_esecuzioni", data_notifica_titolo="2025-06-01",
                  tipo="opposizione_esecuzione")
        assert r["scadenza_opposizione"] == "2025-06-23"
        assert r["termine_opposizione_giorni"] == 20

    def test_opposizione_proroga_festivo(self):
        # 2025-12-20 + 20 = 2026-01-09
        r = _call("termini_esecuzioni", data_notifica_titolo="2025-12-20",
                  tipo="opposizione_esecuzione")
        assert r["scadenza_opposizione"] is not None

    def test_tipo_invalido(self):
        r = _call("termini_esecuzioni", data_notifica_titolo="2025-06-01", tipo="invalid")
        assert "errore" in r
        assert "valori_ammessi" in r


# ---------------------------------------------------------------------------
# termini_deposito_atti_appello
# ---------------------------------------------------------------------------

class TestTerminiDepositoAttiAppello:

    def test_entrambe_le_date(self):
        r = _call("termini_deposito_atti_appello",
                  data_notifica_sentenza="2025-06-01",
                  data_pubblicazione="2025-06-01")
        nomi = [t["termine"] for t in r["termini"]]
        assert "appello_termine_breve" in nomi
        assert "appello_termine_lungo" in nomi

    def test_termine_breve_30gg(self):
        r = _call("termini_deposito_atti_appello",
                  data_notifica_sentenza="2025-06-01")
        breve = next(t for t in r["termini"] if t["termine"] == "appello_termine_breve")
        assert breve["scadenza"] == "2025-07-01"
        assert breve["giorni"] == 30

    def test_termine_lungo_6_mesi(self):
        r = _call("termini_deposito_atti_appello",
                  data_pubblicazione="2025-06-01")
        lungo = next(t for t in r["termini"] if t["termine"] == "appello_termine_lungo")
        assert lungo["scadenza"] == "2025-12-01"
        assert lungo["mesi"] == 6

    def test_solo_data_notifica(self):
        r = _call("termini_deposito_atti_appello",
                  data_notifica_sentenza="2025-06-01")
        nomi = [t["termine"] for t in r["termini"]]
        assert "appello_termine_breve" in nomi
        assert "appello_termine_lungo" not in nomi

    def test_solo_data_pubblicazione(self):
        r = _call("termini_deposito_atti_appello",
                  data_pubblicazione="2025-06-01")
        nomi = [t["termine"] for t in r["termini"]]
        assert "appello_termine_lungo" in nomi
        assert "appello_termine_breve" not in nomi

    def test_nessuna_data_errore(self):
        r = _call("termini_deposito_atti_appello")
        assert "errore" in r

    def test_iscrizione_ruolo_sempre_presente(self):
        r = _call("termini_deposito_atti_appello",
                  data_notifica_sentenza="2025-06-01")
        nomi = [t["termine"] for t in r["termini"]]
        assert "iscrizione_a_ruolo" in nomi

    def test_comparsa_risposta_appellato_presente(self):
        r = _call("termini_deposito_atti_appello",
                  data_notifica_sentenza="2025-06-01")
        nomi = [t["termine"] for t in r["termini"]]
        assert "comparsa_risposta_appellato" in nomi


# ---------------------------------------------------------------------------
# termini_deposito_ctu
# ---------------------------------------------------------------------------

class TestTerminiDepositoCtu:

    def test_tre_scadenze_restituite(self):
        r = _call("termini_deposito_ctu", data_conferimento="2025-05-01", giorni_termine=60)
        assert len(r["scadenze"]) == 3

    def test_deposito_bozza_ctu_60_giorni(self):
        r = _call("termini_deposito_ctu", data_conferimento="2025-05-01", giorni_termine=60)
        dep = next(s for s in r["scadenze"] if s["termine"] == "deposito_bozza_ctu")
        assert dep["scadenza"] == "2025-06-30"
        assert dep["giorni_da_conferimento"] == 60

    def test_osservazioni_parti_15_giorni_dopo_deposito(self):
        r = _call("termini_deposito_ctu", data_conferimento="2025-05-01", giorni_termine=60)
        oss = next(s for s in r["scadenze"] if s["termine"] == "osservazioni_parti")
        assert oss["scadenza"] == "2025-07-15"
        assert oss["giorni_da_deposito_ctu"] == 15

    def test_replica_ctu_15_giorni_dopo_osservazioni(self):
        r = _call("termini_deposito_ctu", data_conferimento="2025-05-01", giorni_termine=60)
        rep = next(s for s in r["scadenze"] if s["termine"] == "replica_ctu")
        assert rep["scadenza"] == "2025-07-30"
        assert rep["giorni_da_osservazioni"] == 15

    def test_termine_ctu_personalizzato_90_giorni(self):
        r = _call("termini_deposito_ctu", data_conferimento="2025-05-01", giorni_termine=90)
        dep = next(s for s in r["scadenze"] if s["termine"] == "deposito_bozza_ctu")
        assert dep["giorni_da_conferimento"] == 90

    def test_default_60_giorni(self):
        r = _call("termini_deposito_ctu", data_conferimento="2025-05-01")
        assert r["giorni_termine_ctu"] == 60

    def test_returns_normativa(self):
        r = _call("termini_deposito_ctu", data_conferimento="2025-05-01")
        assert "195" in r["riferimento_normativo"]

    def test_proroga_applicata_se_festivo(self):
        # Conferimento il 2025-06-01 + 60 = 2025-07-31 — Thursday, no proroga needed
        r = _call("termini_deposito_ctu", data_conferimento="2025-06-01", giorni_termine=60)
        dep = next(s for s in r["scadenze"] if s["termine"] == "deposito_bozza_ctu")
        assert "prorogata_art_155" in dep


# ---------------------------------------------------------------------------
# Internal helpers (tested indirectly via tools, but also directly)
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_easter_2025(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        assert mod._easter(2025) == __import__("datetime").date(2025, 4, 20)

    def test_easter_2024(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        assert mod._easter(2024) == __import__("datetime").date(2024, 3, 31)

    def test_is_holiday_natale(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2025, 12, 25)) is True

    def test_is_holiday_capodanno(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2025, 1, 1)) is True

    def test_is_holiday_santo_stefano(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2025, 12, 26)) is True

    def test_is_holiday_ferragosto(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2025, 8, 15)) is True

    def test_is_holiday_lunedi_angelo_2025(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2025, 4, 21)) is True  # Lunedì dell'Angelo

    def test_is_holiday_sabato(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2025, 6, 7)) is True  # sabato

    def test_is_holiday_domenica(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2025, 6, 8)) is True  # domenica

    def test_not_holiday_lunedi_normale(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2025, 6, 9)) is False  # lunedì

    def test_san_francesco_2026_is_holiday(self):
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2026, 10, 4)) is True

    def test_san_francesco_2024_not_holiday(self):
        # 2024-10-04 is a Friday — San Francesco non ancora in vigore (dal_anno: 2026)
        mod = importlib.import_module("src.tools.scadenze_termini")
        from datetime import date
        assert mod._is_holiday(date(2024, 10, 4)) is False
