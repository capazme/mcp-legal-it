"""Live gate: the labour-law tools apply the numbers the vigente text states.

Three tools in `src/tools/diritto_lavoro.py` hard-code figures taken from the law:

- `indennita_licenziamento`: 6-36 mensilita (art. 3 co. 1 D.Lgs. 23/2015 after Corte cost.
  194/2018), halved to 3-18 for employers below the art. 18 St. lav. threshold (art. 9 co. 1,
  whose cap of six mensilita was struck down by Corte cost. 118/2025), and a cap of twelve
  mensilita on the damages that go with reinstatement (art. 3 co. 2);
- `offerta_conciliativa`: one mensilita per year between 3 and 27 (art. 6 co. 1), halved for
  small employers (art. 9 co. 1), fractions of a year pro rata (art. 8);
- `scadenze_licenziamento`: 60 days to challenge the dismissal, 180 days from the challenge to
  file or ask for conciliation, 60 days from the refusal (art. 6 L. 604/1966), calendar days with
  no summer suspension (art. 3 L. 742/1969).

A reform or a new Constitutional Court ruling can move any of them without touching this
repository, so each test reads the article through `cite_law()` (Normattiva, vigente text and
its AGGIORNAMENTO notes, which is where the Court's rulings are recorded) and checks the words
the code relies on; then it runs the tool on the benchmark cases and compares the result with
what the norm yields. Two tests fail on purpose while the reinstatement branch of
`indennita_licenziamento` disagrees with art. 3 co. 2 and art. 9 co. 1: they record a genuine
deviation, not a flaky fetch.

Needs the network and is skipped by default:

    .venv/bin/pytest tests/unit/test_norme_live_diritto_lavoro.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import functools
import importlib
from datetime import date

import pytest

from tests.unit._norme_live import contiene, normalizza
from tests.unit._norme_live import testo_vigente as _testo_vigente  # aliased: a bare test* name would be collected

pytestmark = pytest.mark.live


@functools.lru_cache(maxsize=None)
def _testo(reference: str) -> str:
    """Vigente text, fetched once per reference for the whole module."""
    return _testo_vigente(reference)


def _assert_parole(reference: str, *frasi: str) -> str:
    testo = _testo(reference)
    missing = contiene(testo, *frasi)
    assert not missing, f"{reference}: il testo vigente non contiene {missing}"
    return testo


def _aggiornamento(testo: str, marcatore: str) -> str:
    """The AGGIORNAMENTO note that mentions `marcatore` (e.g. the ruling number)."""
    blocchi = [b for b in testo.split("aggiornamento") if normalizza(marcatore) in b]
    assert blocchi, f"nessuna nota di aggiornamento con {marcatore!r}"
    return blocchi[0]


def _call(name: str, **kwargs):
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)

    mod = importlib.import_module("src.tools.diritto_lavoro")
    fn = getattr(mod, name)
    return getattr(fn, "fn", fn)(**kwargs)


# ---------------------------------------------------------------------------
# indennita_licenziamento — artt. 3 e 9 D.Lgs. 23/2015
# ---------------------------------------------------------------------------


def test_art3_co1_dlgs_23_2015_indennita_tra_sei_e_trentasei_mensilita_dopo_ccost_194_2018():
    """Art. 3 co. 1: 'non inferiore a sei e non superiore a trentasei mensilita''.

    The words 'di importo pari a due mensilita' ... per ogni anno di servizio' are still printed
    in the body but Corte cost. 194/2018 struck them down (note 2): the tool's 'anni x 2' is only
    a starting point, which is why it declares Precisione INDICATIVO and exposes the range.
    """
    testo = _assert_parole(
        "art. 3 d.lgs. 23/2015",
        "non inferiore a sei e non superiore a trentasei mensilit",
        "ultima retribuzione di riferimento per il calcolo del trattamento di fine rapporto",
    )
    nota_194 = _aggiornamento(testo, "n. 194")
    assert not contiene(nota_194, "limitatamente alle parole", "due mensilit", "per ogni anno di servizio"), nota_194

    grande_min = _call("indennita_licenziamento", anni_servizio=2, retribuzione_mensile=2000)
    assert (grande_min["minimo_mensilita"], grande_min["massimo_mensilita"]) == (6, 36)
    assert grande_min["mensilita"] == 6 and grande_min["importo"] == 12000
    grande_max = _call("indennita_licenziamento", anni_servizio=20, retribuzione_mensile=1000)
    assert grande_max["mensilita"] == 36 and grande_max["importo"] == 36000


def test_art9_co1_dlgs_23_2015_dimezzamento_senza_tetto_di_sei_dopo_ccost_118_2025():
    """Art. 9 co. 1: amounts of artt. 3 co. 1, 4 co. 1 and 6 co. 1 'e'' dimezzato'.

    Corte cost. 118/2025 (note 11) struck down 'e non puo'' in ogni caso superare il limite di sei
    mensilita''' with no 'nella parte in cui' limitation: the cap falls for every amount of the
    sentence, so the small-employer range is 3-18 (indemnity) and 1.5-13.5 (art. 6 offer).
    """
    testo = _assert_parole("art. 9 d.lgs. 23/2015", "dimezzato", "requisiti dimensionali")
    nota_118 = _aggiornamento(testo, "n. 118")
    assert not contiene(nota_118, "2025", "limitatamente alle parole", "superare il limite di sei mensilit"), nota_118

    piccola_max = _call("indennita_licenziamento", anni_servizio=20, retribuzione_mensile=1000, dimensione_azienda="piccola")
    assert (piccola_max["minimo_mensilita"], piccola_max["massimo_mensilita"]) == (3, 18)
    assert piccola_max["importo"] == 18000
    piccola_min = _call("indennita_licenziamento", anni_servizio=1, retribuzione_mensile=2000, dimensione_azienda="piccola")
    assert piccola_min["mensilita"] == 3 and piccola_min["importo"] == 6000


def test_art3_co2_dlgs_23_2015_reintegra_indennita_per_il_periodo_fino_a_dodici_mensilita():
    """Art. 3 co. 2: with reinstatement the damages run 'dal giorno del licenziamento fino a quello
    dell'effettiva reintegrazione', less what the worker earned elsewhere, and 'non puo'' essere
    superiore a dodici mensilita''.

    Nothing ties them to seniority. The tool returns 'min(anni x 2, 12)' and calls it the
    maximum: for three years it says 6 mensilita (12,000 euro) while the ceiling the law sets is
    12 (24,000 euro) whatever the seniority. Expected to FAIL until the branch is rewritten.
    """
    _assert_parole(
        "art. 3 d.lgs. 23/2015",
        "corrispondente al periodo dal giorno del licenziamento fino a quello dell'effettiva reintegrazione",
        "dedotto quanto il lavoratore abbia percepito",
        "superiore a dodici mensilit",
    )
    r3 = _call("indennita_licenziamento", anni_servizio=3, retribuzione_mensile=2000, tipo="reintegra")
    r8 = _call("indennita_licenziamento", anni_servizio=8, retribuzione_mensile=2000, tipo="reintegra")
    assert r3["massimo_mensilita"] == 12
    assert r3["mensilita"] == r8["mensilita"] == 12, (
        "art. 3 co. 2 D.Lgs. 23/2015: il risarcimento massimo con la reintegra e' 12 mensilita' "
        "indipendentemente dall'anzianita'; il tool restituisce "
        f"{r3['mensilita']} mensilita' per 3 anni e {r8['mensilita']} per 8 ({r3['dettaglio_formula']})"
    )


def test_art9_co1_dlgs_23_2015_reintegra_esclusa_per_i_datori_sotto_soglia():
    """Art. 9 co. 1: below the art. 18 St. lav. threshold 'non si applica l'articolo 3, comma 2'.

    The tool computes the reinstatement damages for dimensione_azienda='piccola' as well (6
    mensilita for three years). It should refuse the combination or fall back to the halved
    indemnity (3-18 mensilita). Expected to FAIL until it does.
    """
    _assert_parole("art. 9 d.lgs. 23/2015", "non si applica l'articolo 3, comma 2")
    try:
        r = _call("indennita_licenziamento", anni_servizio=3, retribuzione_mensile=2000,
                  dimensione_azienda="piccola", tipo="reintegra")
    except ValueError:
        return
    assert r["tipo"] != "reintegra" and (r["minimo_mensilita"], r["massimo_mensilita"]) == (3, 18), (
        "art. 9 co. 1 D.Lgs. 23/2015 esclude la reintegra dell'art. 3 co. 2 per i datori sotto soglia; "
        f"il tool la calcola comunque: {r['mensilita']} mensilita', {r['importo']} euro"
    )


def test_art3_co2_ccost_128_2024_riguarda_il_giustificato_motivo_oggettivo():
    """Note 10 of art. 3: Corte cost. 128/2024 extends reinstatement to the objective-reason
    dismissal whose material fact is proven non-existent. It is not a small-employer ruling,
    although the tool's docstring lists it 'per le piccole imprese' (wording to fix)."""
    testo = _testo("art. 3 d.lgs. 23/2015")
    nota_128 = _aggiornamento(testo, "n. 128")
    assert not contiene(nota_128, "comma 2", "giustificato motivo oggettivo", "fatto materiale"), nota_128


# ---------------------------------------------------------------------------
# offerta_conciliativa — artt. 6, 8 e 9 D.Lgs. 23/2015
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "mensilita", "importo"),
    [
        ({"anni_servizio": 5, "retribuzione_mensile": 2000}, 5, 10000),
        ({"anni_servizio": 2, "retribuzione_mensile": 2000}, 3, 6000),
        ({"anni_servizio": 30, "retribuzione_mensile": 1000}, 27, 27000),
        ({"anni_servizio": 30, "retribuzione_mensile": 1000, "dimensione_azienda": "piccola"}, 13.5, 13500),
        ({"anni_servizio": 1, "retribuzione_mensile": 2000, "dimensione_azienda": "piccola"}, 1.5, 3000),
        ({"anni_servizio": 3.5, "retribuzione_mensile": 2000}, 3.5, 7000),
    ],
    ids=["grande-5", "grande-2-minimo", "grande-30-massimo", "piccola-30-tetto", "piccola-1-minimo", "frazione-3.5"],
)
def test_art6_co1_art8_art9_dlgs_23_2015_offerta_una_mensilita_per_anno_tra_tre_e_ventisette(kwargs, mensilita, importo):
    """Art. 6 co. 1: 'una mensilita'' ... per ogni anno di servizio, in misura comunque non
    inferiore a tre e non superiore a ventisette'; art. 8: fractions of a year pro rata; art. 9
    co. 1: halved, with no six-mensilita cap after Corte cost. 118/2025 (1.5-13.5)."""
    _assert_parole(
        "art. 6 d.lgs. 23/2015",
        "una mensilit",
        "per ogni anno di servizio",
        "non inferiore a tre e non superiore a ventisette mensilit",
        "entro i termini di impugnazione stragiudiziale",
        "assegno circolare",
    )
    _assert_parole(
        "art. 8 d.lgs. 23/2015",
        "all'articolo 6, sono riproporzionati",
        "uguali o superiori a quindici giorni si computano come mese intero",
    )
    r = _call("offerta_conciliativa", **kwargs)
    assert r["mensilita"] == pytest.approx(mensilita, abs=1e-9)
    assert r["importo"] == pytest.approx(importo, abs=0.01)


# ---------------------------------------------------------------------------
# scadenze_licenziamento — art. 6 L. 604/1966, art. 3 L. 742/1969
# ---------------------------------------------------------------------------


def test_art6_l604_1966_sessanta_centottanta_e_sessanta_giorni():
    """Art. 6 L. 604/1966 (testo artt. 32 L. 183/2010 e 1 co. 38 L. 92/2012): 60 days from the
    receipt of the written notice; the challenge lapses unless followed 'entro il successivo
    termine di centottanta giorni' by the filing or the request for conciliation/arbitration;
    60 days from the refusal. Calendar days, dies a quo excluded (art. 2963 co. 2 c.c.).

    The 180 days run from the SENDING of the challenge (Cass. 29045/2023 and the consolidated
    line it cites), which is what `data_impugnazione` means in the tool."""
    _assert_parole(
        "art. 6 legge 604/1966",
        "a pena di decadenza entro sessanta giorni dalla ricezione della sua comunicazione",
        "entro il successivo termine di centottanta giorni",
        "richiesta di tentativo di conciliazione o arbitrato",
        "entro sessanta giorni dal rifiuto o dal mancato accordo",
    )
    r = _call("scadenze_licenziamento", data_licenziamento="2025-01-01")
    s = r["scadenze"]
    assert s["impugnazione_stragiudiziale"]["data"] == "2025-03-02"  # 1 gen + 60
    assert s["deposito_ricorso"]["data"] == "2025-08-29"  # 60th day + 180

    r = _call("scadenze_licenziamento", data_licenziamento="2025-06-01", data_impugnazione="2025-06-10",
              data_rifiuto_conciliazione="2025-10-01")
    s = r["scadenze"]
    assert s["impugnazione_stragiudiziale"]["data"] == "2025-07-31"
    assert s["deposito_ricorso"]["data"] == "2025-12-07"  # 10 giu + 180
    assert s["post_conciliazione"]["data"] == "2025-11-30"  # 1 ott + 60

    tardiva = _call("scadenze_licenziamento", data_licenziamento="2025-06-01", data_impugnazione="2025-08-01")
    assert any("decadenza" in a for a in tardiva["avvertimenti"]), tardiva["avvertimenti"]


def test_art3_l742_1969_nessuna_sospensione_feriale_per_le_cause_di_lavoro():
    """Art. 3 L. 742/1969: the August suspension 'non si applica' to labour disputes (the old
    artt. 429 and 459 c.p.c. it names). The art. 6 terms are substantive anyway: a notice
    received on 15 July 2026 must be challenged by 13 September 2026, not 14 October."""
    _assert_parole("art. 3 legge 742/1969", "l'articolo 1 non si applica", "429")
    r = _call("scadenze_licenziamento", data_licenziamento="2026-07-15")
    s = r["scadenze"]
    assert s["impugnazione_stragiudiziale"]["data"] == "2026-09-13"
    assert s["deposito_ricorso"]["data"] == "2027-03-12"


def test_art6_l604_1966_pronunce_costituzionali_212_2020_e_111_2025():
    """Notes 15 and 27 of art. 6: Corte cost. 212/2020 (a pre-trial interim application under
    artt. 669-bis ss. and 700 c.p.c. also satisfies the 180-day term) and Corte cost. 111/2025
    (a worker lacking capacity is exempt from the prior challenge and has 240 days from receipt).
    The tool's descriptions mention neither: this test pins the rulings so the gap stays visible."""
    testo = _testo("art. 6 legge 604/1966")
    nota_212 = _aggiornamento(testo, "n. 212")
    assert not contiene(nota_212, "centottanta giorni", "ricorso cautelare", "700"), nota_212
    nota_111 = _aggiornamento(testo, "n. 111")
    assert not contiene(nota_111, "incapacit", "duecentoquaranta giorni"), nota_111


def test_artt_2963_2964_cc_proroga_festiva_scritta_per_la_prescrizione():
    """Art. 2963 co. 3 c.c. prorogues a term expiring on a holiday, but the text speaks of
    prescription; art. 2964 excludes for decadenza only the rules on interruption and suspension.
    Whether the Sunday proroga reaches the art. 6 L. 604/1966 terms is left to case law: the
    tool never prorogues (2 March 2025, 7 December 2025 and 13 September 2026 are Sundays).
    This test records the textual basis of that open point; it asserts nothing about the tool."""
    _assert_parole("art. 2963 c.c.", "se il termine scade in giorno festivo", "prorogato di diritto al giorno seguente non festivo")
    _assert_parole("art. 2964 c.c.", "non si applicano le norme relative all'interruzione della prescrizione")
    for giorno in ("2025-03-02", "2025-12-07", "2025-11-30", "2026-09-13"):
        assert date.fromisoformat(giorno).weekday() == 6, giorno
