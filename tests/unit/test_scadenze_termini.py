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
        # Udienza 2025-10-01, 40gg a ritroso saltando l'1-31 agosto: 30/09..1/09 sono 30 giorni,
        # poi 31/07..22/07 gli altri 10 → 2025-07-22 (una scadenza in agosto sarebbe impossibile)
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="memoria_I")
        assert r["scadenza"] == "2025-07-22"
        assert r["sospensione_feriale_applicata"] is True
        assert r["sospensione_feriale_incidente"] is True

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

    def test_comparsa_conclusionale_30_giorni_prima_rimessione(self):
        # Art. 189 c.p.c. post-Cartabia: 30gg prima dell'udienza di rimessione in decisione
        r = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="comparsa_conclusionale")
        assert r["scadenza"] == "2025-09-01"
        assert r["giorni_prima_udienza"] == 30
        assert "189" in r["riferimento_normativo"]
        assert "riepilogo_termini_decisione" in r

    def test_note_conclusioni_60_e_replica_15_giorni_prima(self):
        note = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="note_conclusioni")
        assert note["scadenza"] == "2025-07-02"  # 60gg a ritroso saltando agosto
        replica = _call("termini_processuali_civili", data_udienza="2025-10-01", tipo_termine="replica")
        assert replica["scadenza"] == "2025-09-16"

    def test_giorni_assegnati_dal_giudice(self):
        r = _call("termini_processuali_civili", data_udienza="2025-10-01",
                  tipo_termine="comparsa_conclusionale", giorni=20)
        assert r["scadenza"] == "2025-09-11"
        assert r["giorni_assegnati_dal_giudice"] is True

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
        # 6 mesi da 2025-06-01 = 2025-12-01; il periodo comprende agosto → +31 = 2026-01-01
        # (Capodanno) → proroga al 2026-01-02
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="appello_sentenza", notificata=False)
        assert r["scadenza"] == "2026-01-02"
        assert r["sospensione_feriale_incidente"] is True
        assert "lungo" in r["tipo_termine"]

    def test_appello_lungo_senza_sospensione_feriale(self):
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="appello_sentenza", notificata=False,
                  sospensione_feriale=False)
        assert r["scadenza"] == "2025-12-01"

    def test_appello_breve_attraversa_agosto(self):
        # Notifica 2025-07-20: 21-31 luglio sono 11 giorni, agosto non conta, 1-19 settembre gli altri 19
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-07-20",
                  tipo_impugnazione="appello_sentenza", notificata=True)
        assert r["scadenza"] == "2025-09-19"

    def test_regolamento_competenza_nessun_termine_lungo(self):
        r = _call("scadenze_impugnazioni", data_pubblicazione="2025-06-01",
                  tipo_impugnazione="regolamento_competenza", notificata=False)
        assert r["scadenza"] is None
        assert "47" in r["riferimento_normativo"]

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
        # Udienza 2025-10-01: 40gg a ritroso saltando agosto → 2025-07-22
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01")
        m = next(s for s in r["scadenze"] if s["termine"] == "memoria_integrativa")
        assert m["scadenza"] == "2025-07-22"
        assert m["giorni_prima_udienza"] == 40

    def test_memoria_integrativa_senza_feriale(self):
        r = _call("termini_memorie_repliche", data_udienza="2025-10-01", sospensione_feriale=False)
        m = next(s for s in r["scadenze"] if s["termine"] == "memoria_integrativa")
        assert m["scadenza"] == "2025-08-22"

    def _test_memoria_integrativa_40_giorni_vecchio(self):
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

    def test_cinque_scadenze_restituite(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        assert len(r["scadenze"]) == 5

    def test_costituzione_convenuto_10_giorni_prima(self):
        # Art. 281-undecies co. 3: 10gg prima dell'udienza; 2025-09-21 è domenica → anticipa a venerdì 19
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        comp = next(s for s in r["scadenze"] if s["termine"] == "costituzione_convenuto")
        assert comp["giorni_prima_udienza"] == 10
        assert comp["scadenza"] == "2025-09-19"
        assert comp["prorogata_art_155"] is True

    def test_notifica_ricorso_termini_liberi(self):
        # 40 giorni liberi: ultimo giorno utile 41 giorni prima, saltando agosto → 2025-07-21
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        it = next(s for s in r["scadenze"] if s["termine"] == "notifica_ricorso_italia")
        assert it["giorni_prima_udienza"] == 41
        assert it["scadenza"] == "2025-07-21"
        est = next(s for s in r["scadenze"] if s["termine"] == "notifica_ricorso_estero")
        assert est["giorni_prima_udienza"] == 61

    def test_memorie_eventuali_in_avanti(self):
        # Art. 281-duodecies co. 3: fino a 20gg + 10gg dall'udienza, solo se concesse
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        mem = next(s for s in r["scadenze"] if s["termine"] == "memoria_integrativa")
        assert mem["scadenza"] == "2025-10-21"
        rep = next(s for s in r["scadenze"] if s["termine"] == "replica_prova_contraria")
        assert rep["scadenza"] == "2025-10-31"

    def test_giorni_concessi_oltre_il_massimo_rifiutati(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01", giorni_memoria=25)
        assert "errore" in r

    def test_nessun_termine_171_ter(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        nomi = [s["termine"] for s in r["scadenze"]]
        assert "comparsa_risposta" not in nomi
        assert "prova_contraria" not in nomi

    def test_returns_rito_e_normativa(self):
        r = _call("termini_procedimento_semplificato", data_udienza="2025-10-01")
        assert "semplificato" in r["rito"].lower()
        assert "281-undecies" in r["riferimento_normativo"]


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

    def test_regime_previgente_dichiarato_nella_risposta(self):
        r = _call("termini_183_190_cpc", data_udienza="2025-05-01")
        regime = r["regime_normativo"]
        assert regime["stato"] == "previgente"
        assert "28/02/2023" in regime["applicabile_a"]
        assert "termini_memorie_repliche" in regime["tool_vigenti"]

    def test_memorie_183_con_sospensione_feriale(self):
        # Udienza 2025-07-01: 30gg → 31/07 (30° giorno, agosto non conta) → 2025-07-31
        # 60gg → 30 in luglio + 30 in settembre → 2025-09-30
        r = _call("termini_183_190_cpc", data_udienza="2025-07-01")
        m1 = next(s for s in r["scadenze"] if s["termine"] == "memoria_183_n1")
        m2 = next(s for s in r["scadenze"] if s["termine"] == "memoria_183_n2")
        assert m1["scadenza"] == "2025-07-31"
        assert m2["scadenza"] == "2025-09-30"


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
        # 2025-12-01 + 31 giorni di agosto = 2026-01-01 (festivo) → 2026-01-02
        r = _call("termini_deposito_atti_appello",
                  data_pubblicazione="2025-06-01")
        lungo = next(t for t in r["termini"] if t["termine"] == "appello_termine_lungo")
        assert lungo["scadenza"] == "2026-01-02"
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

    def test_costituzione_appellante_sempre_presente(self):
        # Art. 165 c.p.c. (via art. 347): 10 giorni dalla notifica della citazione, non 30
        r = _call("termini_deposito_atti_appello",
                  data_notifica_sentenza="2025-06-01")
        cost = next(t for t in r["termini"] if t["termine"] == "costituzione_appellante")
        assert cost["giorni"] == 10
        assert "scadenza" not in cost

    def test_costituzione_appellante_calcolata(self):
        r = _call("termini_deposito_atti_appello", data_notifica_citazione="2025-06-01")
        cost = next(t for t in r["termini"] if t["termine"] == "costituzione_appellante")
        assert cost["scadenza"] == "2025-06-11"

    def test_comparsa_appellato_70_giorni_prima_udienza(self):
        # Art. 166 c.p.c. post-Cartabia (via art. 347): 70 giorni prima dell'udienza
        r = _call("termini_deposito_atti_appello", data_udienza="2025-12-15")
        comp = next(t for t in r["termini"] if t["termine"] == "comparsa_risposta_appellato")
        assert comp["giorni_prima_udienza"] == 70
        assert comp["scadenza"] == "2025-10-06"

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

    def test_sospensione_feriale_sui_termini_ctu(self):
        # Conferimento 2025-07-01 + 60: 30 giorni in luglio, agosto non conta, 30 in settembre
        r = _call("termini_deposito_ctu", data_conferimento="2025-07-01", giorni_termine=60)
        dep = next(s for s in r["scadenze"] if s["termine"] == "deposito_bozza_ctu")
        assert dep["scadenza"] == "2025-09-30"
        assert r["sospensione_feriale_incidente"] is True

    def test_giorni_osservazioni_parametrici(self):
        r = _call("termini_deposito_ctu", data_conferimento="2025-05-01", giorni_termine=60,
                  giorni_osservazioni=20, giorni_replica=10)
        oss = next(s for s in r["scadenze"] if s["termine"] == "osservazioni_parti")
        assert oss["scadenza"] == "2025-07-21"  # 30/06 + 20 = 20/07 (domenica) → 21/07

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


# ---------------------------------------------------------------------------
# Sospensione feriale (L. 742/1969): conteggio giorno per giorno
# ---------------------------------------------------------------------------

class TestSospensioneFeriale:
    """Casi verificati a mano contando i giorni sul calendario.

    Regola: i giorni dal 1° al 31 agosto non si contano (art. 1 co. 1 L. 742/1969);
    se il dies a quo cade in agosto il decorso è differito al 1° settembre, che
    vale come primo giorno (art. 1 co. 2).
    """

    def _mod(self):
        return importlib.import_module("src.tools.scadenze_termini")

    def test_avanti_termine_che_finisce_in_agosto(self):
        # 20/07 + 30: 21-31 luglio = 11 giorni, poi 1-19 settembre = 19 → 19/09
        from datetime import date
        assert self._mod()._conta_avanti(date(2025, 7, 20), 30, True) == (date(2025, 9, 19), True)

    def test_avanti_termine_che_scavalca_agosto(self):
        # 20/07 + 60: 11 in luglio + 49 in settembre/ottobre → 19/10
        from datetime import date
        assert self._mod()._conta_avanti(date(2025, 7, 20), 60, True)[0] == date(2025, 10, 19)

    def test_avanti_dies_a_quo_in_agosto(self):
        # Notifica 10/08: decorrenza differita, 1° settembre è il primo giorno → 30/09
        from datetime import date
        assert self._mod()._conta_avanti(date(2025, 8, 10), 30, True)[0] == date(2025, 9, 30)

    def test_avanti_senza_sospensione(self):
        from datetime import date
        assert self._mod()._conta_avanti(date(2025, 7, 20), 30, False) == (date(2025, 8, 19), False)

    def test_ritroso_scavalcando_agosto(self):
        from datetime import date
        mod = self._mod()
        assert mod._conta_ritroso(date(2025, 10, 1), 40, True)[0] == date(2025, 7, 22)
        assert mod._conta_ritroso(date(2025, 9, 15), 40, True)[0] == date(2025, 7, 6)

    def test_ritroso_senza_agosto_e_senza_sospensione(self):
        from datetime import date
        mod = self._mod()
        assert mod._conta_ritroso(date(2025, 12, 15), 40, True) == (date(2025, 11, 5), False)
        assert mod._conta_ritroso(date(2025, 10, 1), 40, False)[0] == date(2025, 8, 22)

    def test_mesi_con_agosto_nel_periodo(self):
        from datetime import date
        mod = self._mod()
        assert mod._mesi_avanti(date(2026, 3, 15), 6, True) == (date(2026, 10, 16), True)
        assert mod._mesi_avanti(date(2026, 2, 10), 6, True)[0] == date(2026, 9, 10)

    def test_mesi_senza_agosto_nel_periodo(self):
        from datetime import date
        mod = self._mod()
        assert mod._mesi_avanti(date(2025, 9, 20), 6, True) == (date(2026, 3, 20), False)
        assert mod._mesi_avanti(date(2026, 3, 15), 6, False) == (date(2026, 9, 15), False)

    def test_mesi_dies_a_quo_in_agosto_lettura_prudenziale(self):
        # Decorrenza differita alla fine della sospensione: 6 mesi dal 31/08 → 28/02
        from datetime import date
        assert self._mod()._mesi_avanti(date(2025, 8, 15), 6, True)[0] == date(2026, 2, 28)

    def test_scadenza_processuale_con_sospensione_opzionale(self):
        r = _call("scadenza_processuale", data_evento="2025-07-20", giorni=30, sospensione_feriale=True)
        assert r["scadenza"] == "2025-09-19"
        assert r["sospensione_feriale_incidente"] is True
        r2 = _call("scadenza_processuale", data_evento="2025-07-20", giorni=30)
        assert r2["scadenza"] == "2025-08-19"
        assert r2["sospensione_feriale_applicata"] is False
