"""Live gate: the crisis tools against the vigente text of the CCII and of the OCC fee decrees.

`src/tools/crisi_impresa.py` hard-codes thresholds, terms and references taken from the
Codice della crisi d'impresa e dell'insolvenza (D.Lgs. 14/2019, CCII) and from the fee
regime of the organismi di composizione della crisi (D.M. 202/2014, which refers to the
curatore percentages of D.M. 30/2012):

- `test_crisi_impresa`: art. 3 CCII (orizzonte di dodici mesi, segnali del co. 4) and
  art. 25-novies co. 1 (soglie dei creditori pubblici qualificati);
- `composizione_negoziata`: art. 2 co. 1 lett. d) (impresa minore), artt. 12, 17 co. 7,
  18, 20, 22, 24 and 25-quater CCII;
- `concordato_preventivo`: artt. 84, 85 and 109 CCII;
- `compenso_occ`: artt. 14 and 16 D.M. 202/2014, art. 1 D.M. 30/2012, art. 15 CCII (the
  article the tool cites) and art. 2 co. 1 lett. t) CCII.

Each test reads the article through `cite_law()` (Normattiva, vigente text) and asserts the
words the code relies on; where the tool departs from the text, the test also runs the tool
and asserts what the norm requires, so a genuine divergence shows up as a failure with the
exact provision in the message. Art. 25-novies is read through the HTML path
(`AKN_DISABLED=1`): the AKN export parsed by `cite_law` drops co. 1 lett. c) (Agenzia delle
entrate) and co. 4 lett. b), which the HTML page carries.

It needs the network and is skipped by default:

    .venv/bin/pytest tests/unit/test_norme_live_crisi_impresa.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import inspect
from functools import lru_cache

import pytest

from tests.unit._norme_live import contiene
from tests.unit._norme_live import testo_vigente as _testo_vigente

pytestmark = pytest.mark.live

CCII = "D.Lgs. 14/2019"
DM_OCC = "DM 24 settembre 2014 n. 202"
DM_CURATORE = "DM 25 gennaio 2012 n. 30"


@lru_cache(maxsize=None)
def _testo(reference: str) -> str:
    return _testo_vigente(reference)


def _assert_testo(reference: str, *frasi: str) -> str:
    testo = _testo(reference)
    missing = contiene(testo, *frasi)
    assert not missing, f"{reference}: il testo vigente non contiene {missing}"
    return testo


def _tool(name: str):
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.tools import crisi_impresa

    obj = getattr(crisi_impresa, name)
    return getattr(obj, "fn", obj)


@pytest.fixture(scope="module")
def testo_25_novies() -> str:
    """Art. 25-novies CCII read through the HTML path (the AKN parse drops co. 1 lett. c)."""
    mp = pytest.MonkeyPatch()
    mp.setenv("AKN_DISABLED", "1")
    try:
        return _testo_vigente(f"art. 25-novies {CCII}")
    finally:
        mp.undo()


# ---------------------------------------------------------------------------
# test_crisi_impresa — art. 3 and art. 25-novies CCII
# ---------------------------------------------------------------------------


def test_art_3_ccii_segnali_del_co_4_e_orizzonte_di_dodici_mesi():
    """Art. 3 co. 3 lett. b) and co. 4 lett. a)-d) CCII: the words the tool's indicators stand on."""
    _assert_testo(
        f"art. 3 {CCII}",
        "almeno per i dodici mesi successivi",
        "retribuzioni scaduti da almeno trenta giorni",
        "oltre la met",
        "fornitori scaduti da almeno novanta giorni",
        "scadute da pi",
        "sessanta giorni",
        "almeno il cinque per cento del totale delle esposizioni",
        "25-novies, comma 1",
    )


def test_art_3_ccii_vigente_non_contiene_dscr_ne_rapporto_debiti_attivo():
    """Art. 3 CCII (testo sostituito dal D.Lgs. 83/2022) and art. 13 (no more 'indici della crisi').

    The DSCR and the 80% debiti/attivo ratio of the tool come from the original art. 13 CCII
    (indici elaborati dal CNDCEC), replaced by the piattaforma telematica and the test pratico.
    """
    testo = _testo(f"art. 3 {CCII}")
    for assente in ("dscr", "debt service", "servizio del debito", "ottanta per cento", "80 per cento"):
        assert assente not in testo, f"art. 3 CCII contiene '{assente}': rivedere test_crisi_impresa"
    _assert_testo(f"art. 13 {CCII}", "piattaforma telematica nazionale", "test pratico")


def test_esposizioni_bancarie_al_5_per_cento_sono_segnale_art_3_co_4_lett_c():
    """Art. 3 co. 4 lett. c) CCII: the signal fires at 'almeno il cinque per cento', 5% included."""
    _assert_testo(f"art. 3 {CCII}", "almeno il cinque per cento del totale delle esposizioni")
    r = _tool("test_crisi_impresa")(dscr=1.2, esposizioni_scadute_pct=5.0)
    assert r["numero_indicatori"] >= 1, (
        "art. 3 co. 4 lett. c) CCII: esposizioni scadute che 'rappresentino complessivamente almeno "
        f"il cinque per cento del totale' sono segnale; il tool con 5,0% non lo attiva (usa > 5): {r}"
    )


def test_dscr_orizzonte_dodici_mesi_art_3_co_3_lett_b():
    """Art. 3 co. 3 lett. b) and art. 2 co. 1 lett. a) CCII: sustainability over twelve months."""
    _assert_testo(f"art. 3 {CCII}", "almeno per i dodici mesi successivi")
    _assert_testo(f"art. 2 {CCII}", "nei successivi dodici mesi")
    r = _tool("test_crisi_impresa")(dscr=0.8)
    testo_indicatore = " ".join(r["indicatori_attivati"]).lower()
    assert "12 mesi" in testo_indicatore or "dodici mesi" in testo_indicatore, (
        "art. 3 co. 3 lett. b) CCII: sostenibilita' dei debiti 'almeno per i dodici mesi successivi'; "
        f"l'indicatore DSCR del tool misura 6 mesi: {r['indicatori_attivati']}"
    )


def test_art_25_novies_inps_oltre_novanta_giorni_con_soglie_di_importo(testo_25_novies):
    """Art. 25-novies co. 1 lett. a) CCII: >90 days AND amount thresholds (30% and 15.000 / 5.000)."""
    missing = contiene(
        testo_25_novies,
        "ritardo di oltre novanta giorni nel versamento di contributi previdenziali",
        "30 per cento di quelli dovuti nell'anno precedente",
        "euro 15.000",
        "euro 5.000",
    )
    assert not missing, f"art. 25-novies CCII: il testo vigente non contiene {missing}"
    fn = _tool("test_crisi_impresa")
    # The day threshold is 'oltre novanta giorni' (more than 90): 90 no, 91 yes, but only together
    # with the amounts. Days alone are not a signal: the tool lists it as non determinabile.
    con_importi = dict(debito_inps=15_000.01, contributi_inps_anno_precedente=50_000.0)
    assert fn(giorni_ritardo_inps=90, **con_importi)["numero_indicatori"] == 0
    assert fn(giorni_ritardo_inps=91, **con_importi)["numero_indicatori"] == 1
    solo_giorni = fn(dscr=1.2, giorni_ritardo_inps=91)
    assert solo_giorni["numero_indicatori"] == 0 and solo_giorni["segnali_non_determinabili"], solo_giorni
    # Imprese senza lavoratori: threshold 5.000 euro (n. 2).
    assert fn(giorni_ritardo_inps=91, debito_inps=5_000.01, impresa_con_lavoratori=False)["numero_indicatori"] == 1


def test_art_25_novies_agenzia_entrate_segnale_su_debito_iva(testo_25_novies):
    """Art. 25-novies co. 1 lett. c) and d) CCII: AdE on the IVA amount, AdER on 90 days + amount."""
    missing = contiene(
        testo_25_novies,
        "per l'agenzia delle entrate, l'esistenza di un debito scaduto e non versato relativo all'imposta sul valore aggiunto",
        "non inferiore al 10 per cento dell'ammontare del volume d'affari",
        "euro 20.000",
        "scaduti da oltre novanta giorni",
        "euro 100.000",
        "euro 200.000",
        "euro 500.000",
    )
    assert not missing, f"art. 25-novies CCII: il testo vigente non contiene {missing}"
    fn = _tool("test_crisi_impresa")
    # AdE: no threshold in days (the old 'ritardo AdE > 90 giorni' had no basis); the signal is on the amount.
    assert fn(dscr=1.2, giorni_ritardo_ade=120)["numero_indicatori"] == 0
    assert fn(debito_iva_ade=20_000.01)["numero_indicatori"] == 1
    assert fn(debito_iva_ade=10_000, volume_affari_anno_precedente=100_000)["numero_indicatori"] == 1
    assert fn(debito_iva_ade=10_000, volume_affari_anno_precedente=100_001)["numero_indicatori"] == 0
    # AdER: over 90 days and over 100.000 / 200.000 / 500.000 euro by legal form.
    assert fn(debito_ader=100_000.01, giorni_ritardo_ader=91, forma_giuridica="impresa_individuale")["numero_indicatori"] == 1
    assert fn(debito_ader=200_000, giorni_ritardo_ader=91, forma_giuridica="societa_di_persone")["numero_indicatori"] == 0
    assert fn(debito_ader=500_000.01, giorni_ritardo_ader=91, forma_giuridica="altra_societa")["numero_indicatori"] == 1


def test_art_3_co_4_lett_a_e_b_retribuzioni_e_fornitori():
    """Art. 3 co. 4 lett. a) and b) CCII: the two signals the tool used to lack."""
    fn = _tool("test_crisi_impresa")
    assert fn(retribuzioni_scadute_30gg=5_001, monte_retribuzioni_mensile=10_000)["numero_indicatori"] == 1
    assert fn(retribuzioni_scadute_30gg=5_000, monte_retribuzioni_mensile=10_000)["numero_indicatori"] == 0
    assert fn(debiti_fornitori_scaduti_90gg=100_001, debiti_fornitori_non_scaduti=100_000)["numero_indicatori"] == 1
    assert fn(debiti_fornitori_scaduti_90gg=100_000, debiti_fornitori_non_scaduti=100_000)["numero_indicatori"] == 0


# ---------------------------------------------------------------------------
# composizione_negoziata — artt. 2, 12, 17, 18, 20, 22, 24, 25-quater CCII
# ---------------------------------------------------------------------------


def test_impresa_minore_soglie_congiunte_art_2_co_1_lett_d():
    """Art. 2 co. 1 lett. d) CCII: 300.000 attivo, 200.000 ricavi, 500.000 debiti, 'non superiore', joint."""
    _assert_testo(
        f"art. 2 {CCII}",
        "presenta congiuntamente i seguenti requisiti",
        "non superiore ad euro trecentomila",
        "non superiore ad euro duecentomila",
        "non superiore ad euro cinquecentomila",
        "tre esercizi antecedenti",
    )
    fn = _tool("composizione_negoziata")
    ai_limiti = fn(fatturato=200_000, attivo=300_000, dipendenti=3, debito_totale=500_000, tipo_impresa="sotto_soglia")
    assert ai_limiti["impresa_minore"] is True and "25-quater" in ai_limiti["accesso"], ai_limiti
    oltre = fn(fatturato=200_000.01, attivo=100_000, dipendenti=3, debito_totale=100_000, tipo_impresa="sotto_soglia")
    # Not an impresa minore (ricavi over the limit), but not excluded from the composizione negoziata:
    # art. 12 co. 1 is open to every imprenditore commerciale e agricolo.
    assert oltre["impresa_minore"] is False and "Art. 12 co. 1" in oltre["accesso"], oltre


def test_durata_incarico_esperto_180_piu_180_giorni_art_17_co_7():
    """Art. 17 co. 7 CCII: conclusion after 180 days, extension 'per non oltre centottanta giorni'."""
    _assert_testo(f"art. 17 {CCII}", "decorsi centottanta giorni", "non oltre centottanta giorni")
    r = _tool("composizione_negoziata")(fatturato=500_000, attivo=800_000, dipendenti=10, debito_totale=300_000)
    assert r["durata_max"].count("180") == 2 and "art. 17" in r["durata_max"], r["durata_max"]


def test_impresa_agricola_non_minore_accede_ex_art_12_co_1():
    """Art. 12 co. 1 CCII: 'l'imprenditore commerciale e agricolo'; art. 25-quater is for imprese sotto soglia."""
    _assert_testo(f"art. 12 {CCII}", "l'imprenditore commerciale e agricolo")
    _assert_testo(f"art. 25-quater {CCII}", "imprese sotto soglia", "articolo 2, comma 1, lettera d)")
    r = _tool("composizione_negoziata")(
        fatturato=500_000, attivo=800_000, dipendenti=10, debito_totale=300_000, tipo_impresa="agricola"
    )
    requisiti = " ".join(r["requisiti_soddisfatti"])
    assert "art. 12" in requisiti and "25-quater" not in requisiti, (
        "art. 12 co. 1 CCII: l'impresa agricola (qui non minore: attivo 800.000) accede ex art. 12; "
        f"l'art. 25-quater riguarda le imprese sotto soglia. Il tool dice: {r['requisiti_soddisfatti']}"
    )


def test_sotto_soglia_con_un_solo_requisito_mancante():
    """Art. 2 co. 1 lett. d) and art. 25-quater co. 1 CCII: one missing requirement excludes the impresa minore.

    The impresa is not "sotto soglia", but it keeps the ordinary access of art. 12 co. 1; the message
    must name the missing requirement and must not say that no threshold is met when two are.
    """
    _assert_testo(f"art. 25-quater {CCII}", "presenta congiuntamente i requisiti")
    _assert_testo(f"art. 12 {CCII}", "l'imprenditore commerciale e agricolo")
    r = _tool("composizione_negoziata")(
        fatturato=200_000.01, attivo=100_000, dipendenti=3, debito_totale=100_000, tipo_impresa="sotto_soglia"
    )
    assert r["impresa_minore"] is False and "Art. 12 co. 1" in r["accesso"]
    assert len(r["requisiti_mancanti"]) == 1 and "Ricavi" in r["requisiti_mancanti"][0], r["requisiti_mancanti"]
    messaggio = " ".join(r["requisiti_soddisfatti"])
    assert "nessuna soglia rispettata" not in messaggio, (
        "attivo 100.000 <= 300.000 e debiti 100.000 <= 500.000 sono rispettati, manca solo il requisito "
        f"dei ricavi (200.000,01 > 200.000): il messaggio del tool e' '{messaggio}'"
    )


def test_cause_ostative_art_25_quinquies_e_richiami_art_25_quater_co_5():
    """Art. 25-quinquies co. 1 CCII (bars to the istanza) and art. 25-quater co. 5 (art. 24 commi 3 e 4 only)."""
    _assert_testo(
        f"art. 25-quinquies {CCII}",
        "non puo' essere presentata dall'imprenditore in pendenza del procedimento",
        "nei quattro mesi precedenti",
    )
    _assert_testo(f"art. 25-quater {CCII}", "24, commi 3 e 4")
    fn = _tool("composizione_negoziata")
    base = dict(fatturato=500_000, attivo=800_000, dipendenti=10, debito_totale=300_000)
    assert fn(procedimento_regolazione_pendente=True, **base)["ammissibile"] is False
    assert fn(rinuncia_domanda_ultimi_4_mesi=True, **base)["ammissibile"] is False
    minore = fn(fatturato=150_000, attivo=250_000, dipendenti=3, debito_totale=100_000)
    art_24 = " ".join(m for m in minore["misure_protettive"] if "art. 24" in m)
    assert "co. 3 e 4" in art_24, art_24


def test_misure_citate_esistono_negli_artt_18_20_22_24():
    """Artt. 18 co. 3, 20 co. 1, 22 co. 1 lett. a), 24 co. 2 CCII: the effects the tool lists."""
    _assert_testo(f"art. 18 {CCII}", "iniziare o proseguire azioni esecutive e cautelari")
    _assert_testo(f"art. 20 {CCII}", "2484, primo comma, numero 4)")
    _assert_testo(f"art. 22 {CCII}", "ai fini del riconoscimento della prededuzione")
    _assert_testo(f"art. 24 {CCII}", "non sono soggetti all'azione revocatoria")
    r = _tool("composizione_negoziata")(fatturato=500_000, attivo=800_000, dipendenti=10, debito_totale=300_000)
    citati = " ".join(r["misure_protettive"])
    for art in ("art. 18", "art. 20", "art. 22", "art. 24"):
        assert art in citati, (art, r["misure_protettive"])


# ---------------------------------------------------------------------------
# concordato_preventivo — artt. 84, 85, 109 CCII
# ---------------------------------------------------------------------------


def test_liquidatorio_soglia_del_20_per_cento_art_84_co_4():
    """Art. 84 co. 4 CCII: 'in misura non inferiore al 20 per cento', 20% included."""
    _assert_testo(f"art. 84 {CCII}", "in misura non inferiore al 20 per cento del loro ammontare complessivo")
    fn = _tool("concordato_preventivo")
    al_20 = fn(creditori_privilegiati=200_000, creditori_chirografari=500_000, proposta_pct_chirografari=20, tipo="liquidatorio")
    assert al_20["ammissibile"] is True
    assert al_20["proposta_chirografari_euro"] == pytest.approx(100_000, abs=0.01)
    assert al_20["proposta_totale"] == pytest.approx(300_000, abs=0.01)
    sotto = fn(creditori_privilegiati=200_000, creditori_chirografari=500_000, proposta_pct_chirografari=19.99, tipo="liquidatorio")
    assert sotto["ammissibile"] is False


def test_liquidatorio_apporto_esterno_10_per_cento_dell_attivo_disponibile():
    """Art. 84 co. 4 CCII (testo del D.Lgs. 83/2022): external resources raise the ATTIVO by 10%.

    The pre-2022 text measured the 10% on the satisfaction of the chirografari against the
    liquidazione giudiziale: the tool's note still describes that superseded version.
    """
    _assert_testo(
        f"art. 84 {CCII}",
        "apporto di risorse esterne che incrementi di almeno il 10 per cento",
        "attivo disponibile al momento della presentazione della domanda",
    )
    r = _tool("concordato_preventivo")(
        creditori_privilegiati=200_000, creditori_chirografari=500_000, proposta_pct_chirografari=20, tipo="liquidatorio"
    )
    assert "attivo disponibile" in r["nota_soglia"], (
        "art. 84 co. 4 CCII vigente: l'apporto esterno deve incrementare 'di almeno il 10 per cento "
        "l'attivo disponibile al momento della presentazione della domanda'; il tool dice: "
        f"{r['nota_soglia']}"
    )


def test_liquidatorio_20_per_cento_include_i_privilegiati_degradati():
    """Art. 84 co. 4 and 5 CCII: the 20% is measured on chirografari + privilegiati degradati per incapienza."""
    _assert_testo(
        f"art. 84 {CCII}",
        "creditori chirografari e dei creditori privilegiati degradati per incapienza",
        "la quota residua del credito e' trattata come credito chirografario|la quota residua del credito è trattata come credito chirografario",
    )
    r = _tool("concordato_preventivo")(
        creditori_privilegiati=200_000,
        creditori_chirografari=500_000,
        proposta_pct_chirografari=21,
        proposta_pct_privilegiati=70,
        tipo="liquidatorio",
    )
    degradati = 200_000 * (1 - 0.70)  # 60.000 incapienti, trattati come chirografari (co. 5)
    base = 500_000 + degradati  # 560.000
    offerto_su_base = r["proposta_chirografari_euro"]  # il tool non offre nulla sulla quota degradata
    pct = offerto_su_base / base * 100  # 18,75%
    assert r["ammissibile"] is False or pct >= 20, (
        f"art. 84 co. 4-5 CCII: {offerto_su_base:,.2f} su {base:,.2f} (chirografari + 60.000 degradati) = "
        f"{pct:.2f}% < 20%; il tool misura i soli chirografari e dichiara ammissibile: {r['nota_soglia']}"
    )


def test_privilegiati_non_integrali_senza_consenso_art_84_co_5():
    """Art. 84 co. 5 CCII: privileged may be paid non integrally if not below the attested liquidation value."""
    _assert_testo(
        f"art. 84 {CCII}",
        "possono essere soddisfatti anche non integralmente",
        "attestato da professionista indipendente",
    )
    _assert_testo(f"art. 109 {CCII}", "sono equiparati ai chirografari per la parte residua del credito")
    r = _tool("concordato_preventivo")(
        creditori_privilegiati=200_000,
        creditori_chirografari=500_000,
        proposta_pct_chirografari=21,
        proposta_pct_privilegiati=70,
        tipo="liquidatorio",
    )
    assert "consensuale" not in r["nota_privilegiati"], (
        "art. 84 co. 5 CCII: il pagamento non integrale dei privilegiati non richiede il loro consenso ma "
        "l'attestazione del valore di realizzo; la parte incapiente e' chirografaria (art. 109 co. 4). "
        f"Il tool dice: {r['nota_privilegiati']}"
    )


def test_voto_requisito_art_109_e_classi_art_85():
    """Art. 109 co. 1 and 5, art. 85 co. 3 CCII: majorities and mandatory classes in continuity."""
    _assert_testo(f"art. 85 {CCII}", "nel concordato in continuita' aziendale la suddivisione dei creditori in classi e' in ogni caso obbligatoria|nel concordato in continuità aziendale la suddivisione dei creditori in classi è in ogni caso obbligatoria")
    _assert_testo(
        f"art. 109 {CCII}",
        "maggioranza dei crediti ammessi al voto",
        "nel maggior numero di classi",
        "approvato se tutte le classi votano a favore",
    )
    fn = _tool("concordato_preventivo")
    continuita = fn(creditori_privilegiati=200_000, creditori_chirografari=500_000, proposta_pct_chirografari=5, tipo="continuita")
    # Art. 84 co. 3: no minimum percentage in continuity — this part coincides.
    assert continuita["ammissibile"] is True and continuita["soglia_minima_pct"] == 0.0
    liquidatorio = fn(creditori_privilegiati=200_000, creditori_chirografari=500_000, proposta_pct_chirografari=25, tipo="liquidatorio")
    errori = []
    if "tutte le classi" not in continuita["voto_requisito"]:
        errori.append(
            "continuita: art. 109 co. 5 richiede il voto favorevole di tutte le classi (classi obbligatorie, "
            f"art. 85 co. 3); il tool dice '{continuita['voto_requisito']}'"
        )
    if "maggior numero di classi" not in liquidatorio["voto_requisito"]:
        errori.append(
            "liquidatorio: art. 109 co. 1 richiede la maggioranza dei crediti ammessi al voto e, con classi, "
            f"anche nel maggior numero di classi; il tool dice '{liquidatorio['voto_requisito']}'"
        )
    assert not errori, errori


# ---------------------------------------------------------------------------
# compenso_occ — artt. 14 and 16 D.M. 202/2014, art. 1 D.M. 30/2012, artt. 2 and 15 CCII
# ---------------------------------------------------------------------------


def test_parametri_art_16_dm_202_2014_e_art_1_dm_30_2012():
    """Art. 16 D.M. 202/2014 (attivo + passivo, riduzione 15-40%, tetto 5%/10%) and art. 1 D.M. 30/2012."""
    _assert_testo(
        f"art. 16 {DM_OCC}",
        "percentuale sull'ammontare dell'attivo realizzato",
        "percentuale sull'ammontare del passivo",
        "ridotti in una misura compresa tra il 15% e il 40%",
        "non puo' comunque essere superiore al 5%|non può comunque essere superiore al 5%",
        "al 10% sul medesimo ammontare",
        "inferiore ad euro 20.000",
    )
    _assert_testo(
        f"art. 1 {DM_CURATORE}",
        "dal 12% al 14%",
        "16.227,08",
        "0,19%",
        "0,94%",
        "81.131,38",
        "0,06%",
        "0,46%",
    )
    _assert_testo(f"art. 2 {CCII}", "24 settembre 2014, n. 202")


def test_compenso_occ_si_calcola_su_attivo_e_passivo_art_16_dm_202_2014():
    """Art. 16 co. 1-2 D.M. 202/2014: the fee is a percentage of the attivo AND of the passivo."""
    _assert_testo(f"art. 16 {DM_OCC}", "attivo realizzato", "sull'ammontare dell'attivo e del passivo")
    fn = _tool("compenso_occ")
    parametri = set(inspect.signature(fn).parameters)
    r = fn(passivo=100_000)
    # D.M. 30/2012 art. 1 co. 2 on 100.000 of passivo: 165,47-849,43 euro; reduced by 15-40%
    # (art. 16 co. 4): 99,28-722,02 euro. The attivo share (art. 1 co. 1) is on top of it.
    assert "attivo" in parametri, (
        "art. 16 D.M. 202/2014: compenso = percentuale sull'attivo (art. 1 co. 1 D.M. 30/2012) + "
        "percentuale sul passivo (art. 1 co. 2), ridotto del 15-40%; il tool chiede il solo passivo "
        f"({sorted(parametri)}) e con passivo 100.000 da' {r['compenso']:,.2f} contro 99,28-722,02 della "
        "sola componente passivo"
    )


def test_minimi_1500_e_2000_non_sono_nel_dm_202_2014():
    """Artt. 14 co. 4 and 16 D.M. 202/2014: no minimum fee; numeric thresholds are not binding."""
    _assert_testo(f"art. 14 {DM_OCC}", "non sono vincolanti per la liquidazione")
    testo = _testo(f"art. 16 {DM_OCC}") + " " + _testo(f"art. 14 {DM_OCC}")
    r = _tool("compenso_occ")(passivo=20_000)
    assert r["minimo_applicato"] is True and r["minimo_di_legge"] == 1_500.0
    mancanti = contiene(testo, "1.500", "2.000")
    assert not mancanti, (
        "artt. 14 e 16 D.M. 202/2014 non fissano un minimo: il tool espone 'minimo_di_legge' "
        f"1.500 (ristrutturazione) e 2.000 (liquidazione) senza fonte; assenti: {mancanti}"
    )


def test_riferimento_art_15_co_9_ccii_non_disciplina_i_compensi_occ():
    """Art. 15 CCII (the article the tool cites) has a single comma on the piattaforma telematica.

    The rule the tool means is art. 15 co. 9 of L. 3/2012, abrogated by the CCII; the vigente
    link to D.M. 202/2014 is art. 2 co. 1 lett. t) CCII.
    """
    _assert_testo(f"art. 2 {CCII}", "organismi di composizione delle crisi da sovraindebitamento disciplinati dal decreto del ministro della giustizia del 24 settembre 2014, n. 202")
    r = _tool("compenso_occ")(passivo=100_000)
    assert "art. 15 co. 9 D.Lgs. 14/2019" in r["riferimento_normativo"]
    testo_15 = _testo(f"art. 15 {CCII}")
    assert "compens" in testo_15, (
        "art. 15 CCII ('Scambio di documentazione e di dati contenuti nella piattaforma telematica "
        "nazionale...') ha un solo comma e non parla di compensi: il riferimento del tool "
        f"'{r['riferimento_normativo']}' e' errato (art. 15 co. 9 L. 3/2012, abrogata; oggi art. 2 co. 1 lett. t CCII)"
    )
