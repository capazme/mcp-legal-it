"""Live gate: the company-law tools against the vigente text of the civil code.

`src/tools/diritto_societario.py` hard-codes three sets of rules:

- `quorum_assembleari`: the quorum costitutivi and deliberativi of artt. 2368-2369 (s.p.a.),
  2479 and 2479-bis (s.r.l.), 2484/2487 (scioglimento) and 2538 (cooperative);
- `soglie_organo_controllo_srl`: the limits of art. 2477 co. 2 lett. c) (4 million of attivo,
  4 million of ricavi, 20 dipendenti, exceeded for two consecutive esercizi);
- `scadenze_societarie`: the terms of artt. 2364 co. 2 (120/180 days), 2366 co. 2 (15 days),
  2479-bis co. 1 (8 days), 2429 co. 3 (15 days), 2435 co. 1 and 2478-bis co. 2 (30 days).

Each test first reads the article through `cite_law()` (Normattiva, vigente text) and checks
the words the rule rests on; the `*_tool_*` tests then run the tool on the benchmark cases
(docs/benchmark/piano-benchmark-andreani.json) and compare its answer with the one the text
gives. A tool test that fails is a genuine divergence between the tool and the norm, recorded
in the Fase 4 benchmark report: it is left failing on purpose.

Needs the network and is excluded from the default run:

    .venv/bin/pytest tests/unit/test_norme_live_diritto_societario.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

from functools import lru_cache

import pytest

from tests.unit import _norme_live  # module import: a bare `testo_vigente` would be collected as a test

pytestmark = pytest.mark.live


@lru_cache(maxsize=None)
def _testo(reference: str) -> str:
    """Vigente text of a norm, fetched once per module run."""
    return _norme_live.testo_vigente(reference)


def _assert_parole(reference: str, *frasi: str) -> str:
    testo = _testo(reference)
    missing = _norme_live.contiene(testo, *frasi)
    assert not missing, f"{reference}: il testo vigente non contiene {missing}"
    return testo


def _tool(name: str):
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.tools import diritto_societario

    obj = getattr(diritto_societario, name)
    return getattr(obj, "fn", obj)


# ---------------------------------------------------------------------------
# quorum_assembleari — artt. 2368, 2369, 2479, 2479-bis, 2484, 2487, 2538 c.c.
# ---------------------------------------------------------------------------


def test_art_2368_co1_ordinaria_meta_del_capitale_e_maggioranza_assoluta():
    """Art. 2368 co. 1: ordinaria costituita con almeno la metà del capitale, delibera a maggioranza assoluta."""
    _assert_parole(
        "art. 2368 c.c.",
        "l'assemblea ordinaria e' regolarmente costituita quando e' rappresentata almeno la meta' del capitale sociale"
        "|l'assemblea ordinaria è regolarmente costituita quando è rappresentata almeno la metà del capitale sociale",
        "essa delibera a maggioranza assoluta",
    )


def test_art_2368_co2_straordinaria_spa_chiusa_piu_della_meta_del_capitale():
    """Art. 2368 co. 2: la straordinaria delibera con il voto favorevole di più della metà del capitale;
    metà presente e due terzi del rappresentato valgono solo per chi fa ricorso al mercato del capitale di rischio."""
    testo = _assert_parole(
        "art. 2368 c.c.",
        "piu' della meta' del capitale sociale|più della metà del capitale sociale",
        "nelle societa' che fanno ricorso al mercato del capitale di rischio l'assemblea straordinaria"
        "|nelle società che fanno ricorso al mercato del capitale di rischio l'assemblea straordinaria",
        "almeno i due terzi del capitale rappresentato in assemblea",
    )
    # The two-thirds rule is the exception, stated AFTER the general rule of the first period.
    assert testo.index("capitale di rischio") > testo.index("del capitale sociale, se lo statuto")


def test_art_2369_co3_co5_seconda_convocazione_straordinaria_oltre_un_terzo():
    """Art. 2369 co. 3: in seconda convocazione la straordinaria si costituisce con oltre un terzo del capitale
    e delibera con i due terzi del rappresentato; co. 5: per lo scioglimento anticipato (s.p.a. chiuse)
    serve anche il voto favorevole di più di un terzo del capitale sociale."""
    _assert_parole(
        "art. 2369 c.c.",
        "qualunque sia la parte di capitale rappresentata",
        "con la partecipazione di oltre un terzo del capitale sociale",
        "almeno i due terzi del capitale rappresentato in assemblea",
        "piu' di un terzo del capitale sociale|più di un terzo del capitale sociale",
        "lo scioglimento anticipato",
    )


def test_art_2479_bis_co3_srl_meta_del_capitale_maggioranza_assoluta():
    """Art. 2479-bis co. 3: s.r.l. costituita con almeno metà del capitale, delibera a maggioranza assoluta;
    per le materie dell'art. 2479 co. 2 n. 4 e 5 serve il voto favorevole di almeno metà del capitale."""
    _assert_parole(
        "art. 2479-bis c.c.",
        "regolarmente costituita con la presenza di tanti soci che rappresentano almeno la meta' del capitale sociale"
        "|regolarmente costituita con la presenza di tanti soci che rappresentano almeno la metà del capitale sociale",
        "delibera a maggioranza assoluta",
        "numeri 4) e 5) del secondo comma dell'articolo 2479",
        "con il voto favorevole dei soci che rappresentano almeno la meta' del capitale sociale"
        "|con il voto favorevole dei soci che rappresentano almeno la metà del capitale sociale",
    )
    _assert_parole("art. 2479 c.c.", "4) le modificazioni dell'atto costitutivo")


def test_art_2484_e_2487_scioglimento_senza_maggioranza_dei_due_terzi():
    """Art. 2484 co. 1 n. 6 non fissa maggioranze (nessun 'due terzi'); art. 2487 co. 1 rinvia alle
    maggioranze previste per le modificazioni dell'atto costitutivo."""
    testo = _assert_parole("art. 2484 c.c.", "6) per deliberazione dell'assemblea")
    assert "due terzi" not in testo and "2/3" not in testo
    _assert_parole(
        "art. 2487 c.c.",
        "con le maggioranze previste per le modificazioni dell'atto costitutivo o dello statuto",
    )


def test_art_2538_quorum_cooperativa_fissati_dall_atto_costitutivo():
    """Art. 2538 co. 5: le maggioranze per costituzione e deliberazioni sono determinate dall'atto costitutivo
    e calcolate sui voti spettanti ai soci; nessuna 'metà più uno' legale."""
    testo = _assert_parole(
        "art. 2538 c.c.",
        "ciascun socio cooperatore ha un voto",
        "le maggioranze richieste per la costituzione delle assemblee e per la validita' delle deliberazioni"
        " sono determinate dall'atto costitutivo"
        "|le maggioranze richieste per la costituzione delle assemblee e per la validità delle deliberazioni"
        " sono determinate dall'atto costitutivo",
        "calcolate secondo il numero dei voti spettanti ai soci",
    )
    assert "piu' uno" not in testo and "più uno" not in testo


# Benchmark cases with the outcome the vigente text gives (first convocation, no statutory clause,
# s.p.a. that does not raise risk capital on the market).
_QUORUM_CASI = [
    pytest.param(
        dict(tipo_societa="spa", tipo_delibera="straordinaria",
             capitale_totale=100000, capitale_presente=60000, voti_favorevoli=45000),
        False, id="spa_straordinaria_45_su_100_non_approvata_art2368_co2",
    ),
    pytest.param(
        dict(tipo_societa="spa", tipo_delibera="straordinaria",
             capitale_totale=100000, capitale_presente=90000, voti_favorevoli=55000),
        True, id="spa_straordinaria_55_su_100_approvata_art2368_co2",
    ),
    pytest.param(
        dict(tipo_societa="spa", tipo_delibera="ordinaria",
             capitale_totale=100000, capitale_presente=50000, voti_favorevoli=25000),
        False, id="spa_ordinaria_parita_non_approvata_art2368_co1",
    ),
    pytest.param(
        dict(tipo_societa="spa", tipo_delibera="ordinaria",
             capitale_totale=100000, capitale_presente=50000, voti_favorevoli=25001),
        True, id="spa_ordinaria_un_voto_oltre_la_parita_art2368_co1",
    ),
    pytest.param(
        dict(tipo_societa="srl", tipo_delibera="ordinaria",
             capitale_totale=100000, capitale_presente=60000, voti_favorevoli=40000),
        True, id="srl_ordinaria_40_su_60_presenti_approvata_art2479bis_co3",
    ),
    pytest.param(
        dict(tipo_societa="srl", tipo_delibera="modifica_statuto",
             capitale_totale=100000, capitale_presente=100000, voti_favorevoli=50000),
        True, id="srl_modifica_meta_esatta_approvata_art2479bis_co3",
    ),
    pytest.param(
        dict(tipo_societa="srl", tipo_delibera="scioglimento",
             capitale_totale=100000, capitale_presente=100000, voti_favorevoli=60000),
        True, id="srl_scioglimento_60_approvata_art2487_co1_2479bis_co3",
    ),
    pytest.param(
        dict(tipo_societa="spa", tipo_delibera="scioglimento",
             capitale_totale=100000, capitale_presente=40000, voti_favorevoli=40000),
        False, id="spa_scioglimento_40_prima_conv_non_approvata_art2368_co2",
    ),
]


@pytest.mark.parametrize(("kwargs", "valida_per_la_norma"), _QUORUM_CASI)
def test_quorum_assembleari_tool_esito_come_la_norma(kwargs, valida_per_la_norma):
    """The tool's `delibera_valida` equals the outcome of artt. 2368, 2479-bis and 2487 c.c."""
    r = _tool("quorum_assembleari")(**kwargs)
    assert r["delibera_valida"] is valida_per_la_norma, (
        f"tool: delibera_valida={r['delibera_valida']} ({r['quorum_deliberativo']}); "
        f"norma: {valida_per_la_norma}"
    )


def test_quorum_assembleari_tool_srl_quorum_costitutivo_art_2479_bis_co3():
    """Art. 2479-bis co. 3: with 40% of the capital present the s.r.l. assembly is not constituted."""
    r = _tool("quorum_assembleari")(
        tipo_societa="srl", tipo_delibera="ordinaria",
        capitale_totale=100000, capitale_presente=40000, voti_favorevoli=40000,
    )
    assert r["raggiunto_costitutivo"] is False, r["quorum_costitutivo_prima_conv"]


def test_quorum_assembleari_tool_spa_scioglimento_seconda_convocazione_art_2369():
    """Art. 2369 co. 3 and 5: in seconda convocazione the scioglimento needs over one third, not half."""
    r = _tool("quorum_assembleari")(
        tipo_societa="spa", tipo_delibera="scioglimento",
        capitale_totale=100000, capitale_presente=40000, voti_favorevoli=40000,
    )
    assert "terzo" in r["quorum_costitutivo_seconda_conv"].lower(), r["quorum_costitutivo_seconda_conv"]


def test_quorum_assembleari_tool_cooperativa_rinvia_all_atto_costitutivo_art_2538():
    """Art. 2538 co. 5: the cooperative quorum is set by the atto costitutivo, not by law."""
    r = _tool("quorum_assembleari")(
        tipo_societa="cooperativa", tipo_delibera="ordinaria",
        capitale_totale=100, capitale_presente=40, voti_favorevoli=30,
    )
    assert "atto costitutivo" in r["quorum_costitutivo_prima_conv"].lower(), r["quorum_costitutivo_prima_conv"]


# ---------------------------------------------------------------------------
# soglie_organo_controllo_srl — art. 2477 c.c.
# ---------------------------------------------------------------------------


def test_art_2477_co2_lett_c_limiti_4_milioni_4_milioni_20_dipendenti():
    """Art. 2477 co. 2 lett. c): 4 milioni di attivo, 4 milioni di ricavi, 20 dipendenti, superati per due
    esercizi consecutivi; co. 3: l'obbligo cessa dopo tre esercizi sotto i limiti; co. 5: nomina entro trenta giorni."""
    testo = _assert_parole(
        "art. 2477 c.c.",
        "ha superato per due esercizi consecutivi almeno uno dei seguenti limiti",
        "totale dell'attivo dello stato patrimoniale: 4 milioni di euro",
        "ricavi delle vendite e delle prestazioni: 4 milioni di euro",
        "dipendenti occupati in media durante l'esercizio: 20 unita'|dipendenti occupati in media durante l'esercizio: 20 unità",
        "e' tenuta alla redazione del bilancio consolidato|è tenuta alla redazione del bilancio consolidato",
        "controlla una societa' obbligata alla revisione legale dei conti|controlla una società obbligata alla revisione legale dei conti",
        "per tre esercizi consecutivi",
        "entro trenta giorni",
    )
    assert "2 milioni" not in testo and "10 unita'" not in testo


def test_limiti_2477_vengono_dal_dl_32_2019_non_dal_dlgs_14_2019():
    """Art. 379 D.Lgs. 14/2019 introduced 2 milioni / 2 milioni / 10 unità; the vigente 4 / 4 / 20 are
    from art. 2-bis co. 2 D.L. 32/2019 (conv. L. 55/2019)."""
    _assert_parole("art. 379 D.Lgs. 14/2019", "2 milioni di euro", "10 unita'|10 unità")
    _assert_parole("art. 2-bis D.L. 32/2019", "all'articolo 2477 del codice civile", "4 milioni di euro", "20 unita'|20 unità")


_SOGLIE_CASI = [
    pytest.param(dict(ricavi=4000000, attivo=4000000, dipendenti=20), [], id="valori_pari_ai_limiti_nessuno_superato"),
    pytest.param(dict(ricavi=4000000.01, attivo=1000000, dipendenti=5), ["ricavi"], id="ricavi_un_centesimo_sopra"),
    pytest.param(dict(ricavi=1000000, attivo=1000000, dipendenti=21), ["dipendenti"], id="ventuno_dipendenti"),
    pytest.param(dict(ricavi=1000000, attivo=4000001, dipendenti=0), ["attivo"], id="attivo_un_euro_sopra"),
    pytest.param(dict(ricavi=3000000, attivo=3000000, dipendenti=15), [], id="sopra_i_limiti_dlgs_14_2019_sotto_i_vigenti"),
]


@pytest.mark.parametrize(("kwargs", "superati"), _SOGLIE_CASI)
def test_soglie_organo_controllo_srl_tool_limiti_superati_art_2477(kwargs, superati):
    """The limits the tool applies are those of art. 2477 co. 2 lett. c), exceeded strictly."""
    r = _tool("soglie_organo_controllo_srl")(**kwargs)
    assert r["soglie"] == {"ricavi_euro": 4_000_000.0, "attivo_euro": 4_000_000.0, "dipendenti": 20}
    assert r["limiti_superati"] == superati


def test_soglie_organo_controllo_srl_tool_un_solo_esercizio_non_basta_art_2477():
    """Art. 2477 co. 2 lett. c): the obligation needs two consecutive esercizi over a limit. The tool reads one
    esercizio only, so it cannot state `obbligo_nomina=True` on those data."""
    r = _tool("soglie_organo_controllo_srl")(ricavi=4000000.01, attivo=1000000, dipendenti=5)
    assert r["obbligo_nomina"] is not True, r


def test_soglie_organo_controllo_srl_tool_riferimento_cita_il_dl_32_2019():
    """The 4 / 4 / 20 limits come from D.L. 32/2019: a reference to D.Lgs. 14/2019 alone points to 2 / 2 / 10."""
    r = _tool("soglie_organo_controllo_srl")(ricavi=0, attivo=0, dipendenti=0)
    assert "32/2019" in r["riferimento_normativo"], r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# scadenze_societarie — artt. 2364, 2366, 2429, 2435, 2436, 2478-bis, 2479-bis c.c.
# ---------------------------------------------------------------------------


def test_art_2364_co2_centoventi_giorni_e_maggior_termine_statutario_di_centottanta():
    """Art. 2364 co. 2: entro centoventi giorni dalla chiusura; lo statuto può prevedere fino a centottanta."""
    _assert_parole(
        "art. 2364 c.c.",
        "non superiore a centoventi giorni dalla chiusura dell'esercizio sociale",
        "lo statuto puo' prevedere un maggior termine|lo statuto può prevedere un maggior termine",
        "non superiore a centottanta giorni",
        "le ragioni della dilazione",
    )
    _assert_parole(
        "art. 2478-bis c.c.",
        "non superiore a centoventi giorni dalla chiusura dell'esercizio sociale",
        "secondo comma dell'articolo 2364",
        "entro trenta giorni dalla decisione dei soci di approvazione del bilancio",
    )


def test_art_2366_co2_e_2479_bis_co1_preavviso_quindici_e_otto_giorni():
    """Art. 2366 co. 2: avviso almeno quindici giorni prima (co. 3: otto con statuto, s.p.a. chiuse);
    art. 2479-bis co. 1: raccomandata almeno otto giorni prima dell'adunanza."""
    _assert_parole(
        "art. 2366 c.c.",
        "almeno quindici giorni prima di quello fissato per l'assemblea",
        "almeno otto giorni prima dell'assemblea",
    )
    _assert_parole("art. 2479-bis c.c.", "almeno otto giorni prima dell'adunanza")


def test_art_2429_deposito_in_sede_nei_quindici_giorni_e_comunicazione_ai_sindaci_a_trenta():
    """Art. 2429 co. 3: deposito in sede durante i quindici giorni che precedono l'assemblea;
    co. 1: comunicazione al collegio sindacale e al revisore almeno trenta giorni prima."""
    _assert_parole(
        "art. 2429 c.c.",
        "durante i quindici giorni che precedono l'assemblea",
        "almeno trenta giorni prima di quello fissato per l'assemblea",
    )


def test_art_2435_co1_deposito_entro_trenta_giorni_con_il_verbale_e_2436_solo_modifiche():
    """Art. 2435 co. 1: bilancio depositato entro trenta giorni con il verbale di approvazione;
    art. 2436 riguarda le deliberazioni di modifica dello statuto, non il bilancio."""
    _assert_parole(
        "art. 2435 c.c.",
        "entro trenta giorni dall'approvazione",
        "dal verbale di approvazione dell'assemblea",
    )
    testo = _assert_parole("art. 2436 c.c.", "la deliberazione di modifica dello statuto")
    assert "bilancio" not in testo


_SCADENZE_CASI = [
    pytest.param(
        dict(data_chiusura_esercizio="2025-12-31"),
        {"termine_approvazione_bilancio": "2026-04-30", "convocazione_assemblea_spa": "2026-04-15",
         "convocazione_assemblea_srl": "2026-04-22", "deposito_bilancio_sede_sociale": "2026-04-15",
         "deposito_cciaa": "2026-05-30"},
        id="chiusura_31_12_2025",
    ),
    pytest.param(
        dict(data_chiusura_esercizio="2023-12-31"),
        {"termine_approvazione_bilancio": "2024-04-29", "convocazione_assemblea_spa": "2024-04-14",
         "convocazione_assemblea_srl": "2024-04-21", "deposito_bilancio_sede_sociale": "2024-04-14",
         "deposito_cciaa": "2024-05-29"},
        id="anno_bisestile_29_febbraio_computato",
    ),
    pytest.param(
        dict(data_chiusura_esercizio="2025-12-31", bilancio_differito=True),
        {"termine_approvazione_bilancio": "2026-06-29", "convocazione_assemblea_spa": "2026-06-14",
         "convocazione_assemblea_srl": "2026-06-21", "deposito_bilancio_sede_sociale": "2026-06-14",
         "deposito_cciaa": "2026-07-29"},
        id="maggior_termine_180_giorni_art2364_co2",
    ),
    pytest.param(
        dict(data_chiusura_esercizio="2026-06-30"),
        {"termine_approvazione_bilancio": "2026-10-28", "convocazione_assemblea_spa": "2026-10-13",
         "convocazione_assemblea_srl": "2026-10-20", "deposito_bilancio_sede_sociale": "2026-10-13",
         "deposito_cciaa": "2026-11-27"},
        id="esercizio_non_solare_agosto_computato",
    ),
]


@pytest.mark.parametrize(("kwargs", "attese"), _SCADENZE_CASI)
def test_scadenze_societarie_tool_date_come_la_norma(kwargs, attese):
    """Calendar-day terms of artt. 2364 co. 2, 2366 co. 2, 2479-bis co. 1, 2429 co. 3, 2435 co. 1: no
    sospensione feriale (substantive terms), dies a quo not counted."""
    r = _tool("scadenze_societarie")(**kwargs)
    date = {k: v["data"] for k, v in r["scadenze"].items()}
    for voce, attesa in attese.items():
        assert date[voce] == attesa, f"{voce}: tool {date[voce]}, norma {attesa}"


def test_scadenze_societarie_tool_verbale_di_bilancio_cita_art_2435_non_2436():
    """The verbale approving the bilancio is filed with it under art. 2435 co. 1; art. 2436 governs the
    notary's filing of statutory amendments."""
    r = _tool("scadenze_societarie")(data_chiusura_esercizio="2025-12-31")
    nota = r["scadenze"]["iscrizione_verbale_assemblea"]["nota"]
    assert "2435" in nota and "2436" not in nota, nota
