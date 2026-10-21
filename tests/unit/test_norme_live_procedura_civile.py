"""Live gate: the procedura_civile tools against the vigente c.p.c., D.Lgs. 116/2017, CCII and D.Lgs. 28/2010.

`src/tools/procedura_civile.py` hard-codes the rules it applies:

- `competenza_giudice`: the thresholds of art. 7 co. 1 and co. 2 c.p.c. (10.000 and 25.000
  euro, in force since 28/02/2023 through D.Lgs. 149/2022), a comment dating the D.Lgs.
  116/2017 thresholds (art. 27, entry into force governed by art. 32 co. 3) and a list of
  matters it treats as reserved to the tribunale "ex art. 9 c.p.c." (locazione, condominio,
  lavoro, famiglia, fallimento, crisi d'impresa); every other matter falls through to the
  "beni mobili" rule of art. 7 co. 1.
- `verifica_mediazione_obbligatoria`: the table `src/data/mediazione_obbligatoria.json`
  (the matters of art. 5 co. 1 D.Lgs. 28/2010 and a list of exclusions) matched against the
  input by substring.

Each test reads the provision through `cite_law()` (Normattiva, vigente text), asserts the
words the code relies on, and runs the tool on the cases of the benchmark plan
(docs/benchmark/piano-benchmark-andreani.json). Where the tool departs from the text the test
asserts what the norm requires, so a genuine divergence shows up as a failure that names the
provision.

Caveat on art. 7 c.p.c.: Normattiva already shows the text as amended by art. 27 D.Lgs.
116/2017 (co. 3 n. 2 "cause in materia di condominio negli edifici", n. 3-ter..3-undecies,
the new fourth comma on usucapione up to 30.000 euro), with a note that art. 27 enters into
force only on 31 ottobre 2027 (art. 32 co. 3 D.Lgs. 116/2017 as amended by art. 5 co. 1
lett. b) D.L. 12 giugno 2026 n. 100, conv. L. 7 agosto 2026 n. 145). Until then co. 3 n. 2
still reads "cause relative alla misura ed alle modalita' d'uso dei servizi di condominio di
case" and there is no fourth comma. The assertions below hold under both wordings; the tests
that depend on the 2027 date must be revisited on 31/10/2027.

It needs the network and is skipped by default:

    .venv/bin/pytest tests/unit/test_norme_live_procedura_civile.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import inspect
import json
import re
from functools import lru_cache
from pathlib import Path

import pytest

from tests.unit._norme_live import contiene, normalizza
from tests.unit._norme_live import testo_vigente as _testo_vigente

pytestmark = pytest.mark.live

CPC = "c.p.c."
DLGS_116 = "D.Lgs. 116/2017"
DL_100_2026 = "D.L. 100/2026"
CCII = "D.Lgs. 14/2019"
DLGS_28 = "D.Lgs. 28/2010"

_TABELLA = Path(__file__).resolve().parents[2] / "src" / "data" / "mediazione_obbligatoria.json"


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
    from src.tools import procedura_civile

    obj = getattr(procedura_civile, name)
    return getattr(obj, "fn", obj)


def _competenza(valore_causa: float, materia: str = "civile") -> dict:
    return _tool("competenza_giudice")(valore_causa=valore_causa, materia=materia)


def _mediazione(materia: str) -> dict:
    return _tool("verifica_mediazione_obbligatoria")(materia=materia)


def _comma(testo: str, inizio: str, fine: str) -> str:
    """The slice of a normalised article between two markers (both normalised)."""
    i = testo.find(normalizza(inizio))
    assert i >= 0, f"marcatore iniziale '{inizio}' assente"
    j = testo.find(normalizza(fine), i + 1)
    return testo[i : j if j > i else None]


# ---------------------------------------------------------------------------
# competenza_giudice — art. 7 co. 1-2 c.p.c. (soglie per valore)
# ---------------------------------------------------------------------------


def test_art_7_co_1_e_2_cpc_soglie_diecimila_e_venticinquemila():
    """Art. 7 co. 1 c.p.c. (beni mobili fino a 10.000 euro) and co. 2 (circolazione fino a 25.000 euro)."""
    _assert_testo(
        f"art. 7 {CPC}",
        "cause relative a beni mobili di valore non superiore a diecimila euro",
        "circolazione di veicoli e di natanti",
        "non superi venticinquemila euro",
    )
    casi = [
        (10_000.00, "civile", "Giudice di Pace"),
        (10_000.01, "civile", "Tribunale"),
        (25_000.00, "circolazione_stradale", "Giudice di Pace"),
        (25_000.01, "circolazione_stradale", "Tribunale"),
    ]
    for valore, materia, atteso in casi:
        r = _competenza(valore, materia)
        assert r["giudice_competente"] == atteso, f"art. 7 c.p.c.: {valore} {materia} -> {atteso}, tool {r}"


def test_art_32_co_3_dlgs_116_2017_soglie_di_30_e_50_mila_rinviate_al_31_ottobre_2027():
    """Art. 32 co. 3 D.Lgs. 116/2017 (mod. art. 5 co. 1 lett. b) D.L. 100/2026): art. 27 in force on 31/10/2027.

    Until that date the 10.000/25.000 thresholds apply: a 20.000 euro claim on beni mobili is
    for the tribunale.
    """
    _assert_testo(f"art. 32 {DLGS_116}", "le disposizioni dell'articolo 27 entrano in vigore il", "31 ottobre 2027")
    _assert_testo(f"art. 5 {DL_100_2026}", "all'articolo 32, comma 3", "31 ottobre 2026", "31 ottobre 2027")
    r = _competenza(20_000.0, "civile")
    assert r["giudice_competente"] == "Tribunale", r


def test_commento_del_codice_allineato_al_rinvio_del_dl_100_2026():
    """Art. 32 co. 3 D.Lgs. 116/2017 vigente: 31 ottobre 2027, not 31/10/2026 as the code comments say.

    The comments next to the thresholds date the D.Lgs. 116/2017 thresholds on 31/10/2026, the
    date set by D.L. 117/2025 and moved to 31/10/2027 by art. 5 co. 1 lett. b) D.L. 12 giugno
    2026 n. 100 (conv. L. 7 agosto 2026 n. 145). A maintainer following the comment would switch
    the thresholds a year early.
    """
    _assert_testo(f"art. 32 {DLGS_116}", "31 ottobre 2027")
    sorgente = inspect.getsource(_tool("competenza_giudice"))
    assert "31/10/2026" not in sorgente, (
        "art. 32 co. 3 D.Lgs. 116/2017 (testo vigente, mod. D.L. 100/2026): 'Le disposizioni "
        "dell'articolo 27 entrano in vigore il 31 ottobre 2027'; il commento di competenza_giudice "
        "indica ancora la decorrenza 31/10/2026"
    )


# ---------------------------------------------------------------------------
# competenza_giudice — materie "riservate" e materie non elencate
# ---------------------------------------------------------------------------


def test_condominio_non_e_riservato_al_tribunale_art_9_e_art_7_co_3_n_2_cpc():
    """Art. 9 c.p.c. does not reserve condominio; art. 7 co. 3 n. 2 gives condominium causes to the GdP.

    A condominium credit of 3.000 euro is for the giudice di pace (art. 7 co. 1, money is a bene
    mobile), and so are the causes on the measure and use of condominium services (co. 3 n. 2 in
    force; from 31/10/2027 every "causa in materia di condominio negli edifici").
    """
    art9 = _assert_testo(f"art. 9 {CPC}", "tutte le cause che non sono di competenza di altro giudice")
    assert "condomin" not in art9, "art. 9 c.p.c. ora menziona il condominio: rivedere il test"
    _assert_testo(f"art. 7 {CPC}", "qualunque ne sia il valore", "condominio")
    r = _competenza(3_000.0, "condominio")
    assert r["giudice_competente"] == "Giudice di Pace" and not r["materia_riservata"], (
        "art. 7 co. 1 e co. 3 n. 2 c.p.c.: credito condominiale di 3.000 euro al giudice di pace; "
        f"l'art. 9 c.p.c. non riserva il condominio al tribunale. Tool: {r}"
    )


def test_usucapione_immobile_non_e_causa_su_beni_mobili_art_7_co_1_e_art_9_co_1_cpc():
    """Art. 7 co. 1 c.p.c. covers beni mobili only; usucapione of immovables stays with the tribunale.

    The GdP competence on usucapione up to 30.000 euro (new fourth comma of art. 7, art. 27
    D.Lgs. 116/2017) enters into force on 31/10/2027 (art. 32 co. 3). The tool treats every
    matter it does not list as a cause on beni mobili.
    """
    _assert_testo(f"art. 7 {CPC}", "cause relative a beni mobili")
    _assert_testo(f"art. 9 {CPC}", "tutte le cause che non sono di competenza di altro giudice")
    _assert_testo(f"art. 32 {DLGS_116}", "31 ottobre 2027")
    r = _competenza(5_000.0, "usucapione")
    assert r["giudice_competente"] == "Tribunale", (
        "artt. 7 co. 1 e 9 co. 1 c.p.c.: l'usucapione di un immobile non e' causa su beni mobili "
        f"(competenza GdP ex art. 7 co. 4 n. 1 solo dal 31/10/2027). Tool: {r}"
    )


def test_querela_di_falso_competenza_esclusiva_del_tribunale_art_9_co_2_cpc():
    """Art. 9 co. 2 c.p.c.: querela di falso (with imposte e tasse, stato e capacita', esecuzione forzata,
    sistemi di intelligenza artificiale and valore indeterminabile) is exclusively for the tribunale."""
    _assert_testo(
        f"art. 9 {CPC}",
        "esclusivamente competente",
        "imposte e tasse",
        "querela di falso",
        "esecuzione forzata",
        "intelligenza artificiale",
        "valore indeterminabile",
    )
    r = _competenza(1_000.0, "querela_di_falso")
    assert r["giudice_competente"] == "Tribunale", (
        "art. 9 co. 2 c.p.c.: 'Il tribunale e' altresi' esclusivamente competente ... per la querela di "
        f"falso'; il tool la tratta come causa su beni mobili. Tool: {r}"
    )


def test_famiglia_tribunale_art_9_co_2_ma_artt_706_ss_cpc_abrogati():
    """Art. 9 co. 2 c.p.c. (stato e capacita' delle persone) and art. 473-bis (rito unificato):
    the tool's citation "artt. 706 ss. c.p.c." points to articles repealed by D.Lgs. 149/2022."""
    _assert_testo(f"art. 9 {CPC}", "stato e alla capacita' delle persone|stato e alla capacità delle persone")
    _assert_testo(f"art. 706 {CPC}", "abrogato dal d.lgs. 10 ottobre 2022, n. 149")
    _assert_testo(f"art. 473-bis {CPC}", "procedimenti relativi allo stato delle persone, ai minorenni e alle famiglie")
    r = _competenza(50_000.0, "famiglia")
    assert r["giudice_competente"] == "Tribunale", r
    assert "706" not in r["articolo"], (
        "art. 706 c.p.c.: 'ARTICOLO ABROGATO DAL D.LGS. 10 OTTOBRE 2022, N. 149'; il rito della "
        f"famiglia e' agli artt. 473-bis ss. c.p.c. Tool: {r['articolo']}"
    )


def test_crisi_impresa_sezione_specializzata_solo_per_grandi_imprese_art_27_ccii():
    """Art. 27 co. 1-2 CCII: the tribunale sede delle sezioni specializzate only for imprese assoggettabili
    ad amministrazione straordinaria and gruppi di rilevante dimensione; otherwise the tribunale of the COMI."""
    _assert_testo(
        f"art. 27 {CCII}",
        "imprese assoggettabili ad amministrazione straordinaria",
        "gruppi di imprese di rilevante dimensione",
        "tribunale sede delle sezioni specializzate in materia di imprese",
        "diversi da quelli di cui al comma 1",
        "tribunale nel cui circondario il debitore ha il centro degli interessi principali",
    )
    for materia in ("crisi_impresa", "fallimento"):
        r = _competenza(200_000.0, materia)
        assert "specializzata" not in r["giudice_competente"].lower(), (
            "art. 27 co. 2 CCII: per le imprese diverse da quelle del co. 1 'e' competente il tribunale "
            "nel cui circondario il debitore ha il centro degli interessi principali'; il tool indica "
            f"sempre la sezione specializzata. Tool ({materia}): {r['giudice_competente']}"
        )


def test_lavoro_tribunale_in_funzione_di_giudice_del_lavoro_art_413_cpc():
    """Art. 413 co. 1 c.p.c.: the controversies of art. 409 go to the tribunale as giudice del lavoro."""
    _assert_testo(f"art. 413 {CPC}", "le controversie previste dall'articolo 409", "in funzione di giudice del lavoro")
    r = _competenza(500.0, "lavoro")
    assert r["giudice_competente"].startswith("Tribunale") and "lavoro" in r["giudice_competente"].lower(), r


def test_locazione_immobiliare_al_tribunale_art_7_co_1_e_art_447_bis_cpc():
    """Locazione of immovables: not a cause on beni mobili (art. 7 co. 1), special rite of art. 447-bis;
    the tribunale is competent (residual art. 9 co. 1, former pretore competence moved by D.Lgs. 51/1998)."""
    _assert_testo(f"art. 7 {CPC}", "cause relative a beni mobili")
    _assert_testo(f"art. 447-bis {CPC}", "controversie in materia di locazione e di comodato di immobili urbani")
    r = _competenza(1_000.0, "locazione")
    assert r["giudice_competente"] == "Tribunale", r


# ---------------------------------------------------------------------------
# verifica_mediazione_obbligatoria — art. 5 co. 1 e co. 6 D.Lgs. 28/2010
# ---------------------------------------------------------------------------

# Table key -> words of art. 5 co. 1 D.Lgs. 28/2010 (vigente) that key stands for.
_MATERIE_ART_5 = {
    "condominio": "condominio",
    "diritti_reali": "diritti reali",
    "divisione": "divisione",
    "successioni_ereditarie": "successioni ereditarie",
    "patti_di_famiglia": "patti di famiglia",
    "locazione": "locazione",
    "comodato": "comodato",
    "affitto_aziende": "affitto di aziende",
    "responsabilita_medica": "responsabilita' medica e sanitaria|responsabilità medica e sanitaria",
    "diffamazione_stampa": "diffamazione con il mezzo della stampa o con altro mezzo di pubblicit",
    "contratti_assicurativi": "contratti assicurativi",
    "contratti_bancari": "assicurativi, bancari e finanziari",
    "contratti_finanziari": "bancari e finanziari",
    "associazione_in_partecipazione": "associazione in partecipazione",
    "consorzio": "consorzio",
    "franchising": "franchising",
    "contratti_opera": " opera,",
    "reti_impresa": " rete,",
    "somministrazione": "somministrazione",
    "societa_di_persone": "societa' di persone|società di persone",
    "subfornitura": "subfornitura",
}


def _art_5_co(n: int) -> str:
    testo = _testo(f"art. 5 {DLGS_28}")
    marcatori = {1: ("1. chi intende", "2. nelle controversie"), 5: ("5. lo svolgimento", "6. il comma 1"),
                 6: ("6. il comma 1", "aggiornamento")}
    return _comma(testo, *marcatori[n])


def test_art_5_co_1_dlgs_28_2010_elenco_coincide_con_la_tabella():
    """Art. 5 co. 1 D.Lgs. 28/2010 vigente: the 21 matters of the table, no more and no less."""
    co1 = _art_5_co(1)
    missing = contiene(co1, *_MATERIE_ART_5.values())
    assert not missing, f"art. 5 co. 1 D.Lgs. 28/2010: non contiene {missing}"
    assert "e' tenuto preliminarmente a esperire il procedimento di mediazione" in co1 or \
        "è tenuto preliminarmente a esperire il procedimento di mediazione" in co1
    tabella = json.loads(_TABELLA.read_text(encoding="utf-8"))
    assert {m["nome"] for m in tabella["materie"]} == set(_MATERIE_ART_5), (
        "la tabella mediazione_obbligatoria.json non corrisponde alle 21 materie dell'art. 5 co. 1"
    )
    for chiave in _MATERIE_ART_5:
        r = _mediazione(chiave)
        assert r["obbligatoria"] is True and r["materia_trovata"] == chiave, r


def test_circolazione_stradale_fuori_dall_art_5_co_1_e_soggetta_a_negoziazione_assistita():
    """Art. 5 co. 1 D.Lgs. 28/2010 no longer lists circolazione (removed by D.L. 69/2013); art. 3 co. 1
    D.L. 132/2014 makes negoziazione assistita the condition of procedibility instead."""
    assert "circolazione" not in _art_5_co(1)
    _assert_testo("art. 3 D.L. 132/2014", "risarcimento del danno da circolazione di veicoli e natanti",
                  "negoziazione assistita")
    r = _mediazione("circolazione_stradale")
    assert r["obbligatoria"] is False, r


def test_contratto_di_rete_e_in_elenco_art_5_co_1():
    """Art. 5 co. 1 D.Lgs. 28/2010 lists 'rete' (contratto di rete, added by D.Lgs. 149/2022).

    The table stores it as 'reti_impresa', which neither 'rete' nor 'contratto di rete' matches
    by substring: the tool answers false.
    """
    assert " rete," in _art_5_co(1)
    for materia in ("rete", "contratto di rete"):
        r = _mediazione(materia)
        assert r["obbligatoria"] is True, (
            "art. 5 co. 1 D.Lgs. 28/2010: '... franchising, opera, rete, somministrazione ...'; "
            f"il tool risponde obbligatoria={r['obbligatoria']} per '{materia}'"
        )


def test_materie_scritte_con_le_lettere_accentate():
    """Art. 5 co. 1 D.Lgs. 28/2010 reads "responsabilita' medica e sanitaria" and "societa' di persone":
    the same words written with the Italian accent must match."""
    _assert_testo(f"art. 5 {DLGS_28}", _MATERIE_ART_5["responsabilita_medica"], _MATERIE_ART_5["societa_di_persone"])
    for materia in ("responsabilità medica", "società di persone"):
        r = _mediazione(materia)
        assert r["obbligatoria"] is True, (
            f"art. 5 co. 1 D.Lgs. 28/2010: '{materia}' e' in elenco; il tool non normalizza gli accenti "
            f"e risponde obbligatoria={r['obbligatoria']}"
        )


def test_input_generico_o_vuoto_non_e_una_materia_dell_art_5_co_1():
    """Art. 5 co. 1 D.Lgs. 28/2010 names only some contracts: 'contratti' in general is not a listed
    matter, and neither is an empty string. The substring match hooks them to the first entry that
    contains them (contratti_assicurativi, condominio)."""
    co1 = _art_5_co(1)
    assert "contratti assicurativi, bancari e finanziari" in co1
    for materia in ("contratti", ""):
        r = _mediazione(materia)
        assert r["obbligatoria"] is not True, (
            f"art. 5 co. 1 D.Lgs. 28/2010 non elenca i contratti in genere; per {materia!r} il tool "
            f"risponde obbligatoria=True agganciando '{r['materia_trovata']}'"
        )


def test_somministrazione_e_il_contratto_degli_artt_1559_ss_cc():
    """Art. 5 co. 1 D.Lgs. 28/2010 lists 'somministrazione' (the contract of artt. 1559 ss. c.c., as the
    table's note says). Whether 'somministrazione_lavoro' (D.Lgs. 81/2015) is covered is left open in
    the benchmark (da_chiarire): this test only pins the text and the entry the tool matches."""
    assert "somministrazione" in _art_5_co(1)
    r = _mediazione("somministrazione")
    assert r["obbligatoria"] is True and "1559" in r["note"], r


def test_esclusioni_art_5_co_5_e_co_6_dlgs_28_2010():
    """Art. 5 co. 6 D.Lgs. 28/2010 lists eight exclusions (lett. a-h); co. 5 keeps urgent and precautionary
    measures available without excluding them. The table lists five, one of which (cautelari) is not in co. 6."""
    co6 = _art_5_co(6)
    esclusioni_norma = {
        "a) ingiunzione, inclusa l'opposizione": "procedimenti per ingiunzione, inclusa l'opposizione",
        "b) convalida di licenza o sfratto": "convalida di licenza o sfratto",
        "c) consulenza tecnica preventiva (696-bis)": "696-bis",
        "d) procedimenti possessori": "procedimenti possessori",
        "e) opposizioni esecutive": "relativi all'esecuzione forzata",
        "f) camera di consiglio": "camera di consiglio",
        "g) azione civile nel processo penale": "azione civile esercitata nel processo penale",
        "h) azione inibitoria del codice del consumo": "azione inibitoria",
    }
    missing = contiene(co6, *esclusioni_norma.values())
    assert not missing, f"art. 5 co. 6 D.Lgs. 28/2010: non contiene {missing}"
    assert "cautelar" not in co6
    assert contiene(_art_5_co(5), "non preclude in ogni caso la concessione dei provvedimenti urgenti e cautelari") == []

    tool = normalizza(" | ".join(_mediazione("condominio")["esclusioni_applicabili"]))
    chiavi_tool = {
        "a) ingiunzione, inclusa l'opposizione": "ingiunzione",
        "b) convalida di licenza o sfratto": "sfratto",
        "c) consulenza tecnica preventiva (696-bis)": "696-bis|consulenza tecnica preventiva",
        "d) procedimenti possessori": "possessori",
        "e) opposizioni esecutive": "esecuzione forzata|opposizioni esecutive",
        "f) camera di consiglio": "camera di consiglio",
        "g) azione civile nel processo penale": "processo penale",
        "h) azione inibitoria del codice del consumo": "inibitoria",
    }
    assenti = [k for k, v in chiavi_tool.items() if not any(normalizza(a) in tool for a in v.split("|"))]
    estranee = ["cautelari (art. 5 co. 5: la mediazione non li preclude, non sono esclusi)"] if "cautelar" in tool else []
    assert not assenti and not estranee, (
        f"art. 5 co. 6 D.Lgs. 28/2010: esclusioni mancanti nel tool {assenti}; voci che la norma non "
        f"prevede come esclusioni {estranee}"
    )


def test_ingiunzione_esclusa_fino_alla_provvisoria_esecuzione_inclusa_l_opposizione():
    """Art. 5 co. 6 lett. a) D.Lgs. 28/2010: 'fino alla pronuncia sulle istanze di concessione e sospensione
    della provvisoria esecuzione', opposition included; the table says 'fino alla pronuncia sulle istanze
    cautelari'."""
    co6 = _art_5_co(6)
    assert contiene(co6, "fino alla pronuncia sulle istanze di concessione e sospensione della provvisoria esecuzione") == []
    voce = next(e for e in _mediazione("condominio")["esclusioni_applicabili"] if "ingiunzione" in e.lower())
    assert "provvisoria esecuzione" in voce.lower() and "opposizione" in voce.lower(), (
        "art. 5 co. 6 lett. a) D.Lgs. 28/2010: 'nei procedimenti per ingiunzione, inclusa l'opposizione, "
        "fino alla pronuncia sulle istanze di concessione e sospensione della provvisoria esecuzione'; "
        f"il tool dice: '{voce}'"
    )


def test_guardia_sui_marcatori_dei_commi_dell_art_5():
    """Guard: the comma slices used above are non-empty and ordered (catches a change of layout)."""
    co1, co6 = _art_5_co(1), _art_5_co(6)
    assert len(co1) > 200 and len(co6) > 200
    assert re.search(r"subfornitura", co1) and not re.search(r"subfornitura", co6)
