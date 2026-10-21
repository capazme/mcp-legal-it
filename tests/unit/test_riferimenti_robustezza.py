"""Article strings that used to cost seconds or come back as the wrong article."""

import time

import pytest

from mcp_legal_it.lib.visualex.models import (
    IntervalloArticoli,
    Norma,
    NormaVisitata,
    intervallo_articoli,
    split_annex,
)


# --- split_annex: linear on any input -------------------------------------------

@pytest.mark.parametrize("reference", [
    "allegato I art. 1" + "1" * 5000 + "!",
    "allegato I art. 1" + "1a" * 5000 + "!",
    "allegato I art. 1" + " 1" * 5000 + "!",
    "allegato I art. 1" + "-a" * 5000 + "!",
    "allegato I" + " ," * 5000 + "art. 1!",
], ids=["digits", "digit-letter", "spaced", "dashed", "separators"])
def test_split_annex_is_linear(reference):
    # "(?:[-/.\s]?\w+)*" split a run of word characters in exponentially many ways:
    # 0.44 s at 20 characters, x4 every 2 more.
    start = time.perf_counter()
    assert split_annex(reference) is None
    assert time.perf_counter() - start < 0.1


@pytest.mark.parametrize("reference, expected", [
    ("allegato I.7 art. 30", ("I.7", "30")),
    ("Allegato III", ("III", "")),
    ("allegato I.7, articolo 30.1", ("I.7", "30.1")),
    ("allegato II art. 3-quater.1", ("II", "3-quater.1")),
    ("allegato I art. 2 bis", ("I", "2 bis")),
    ("allegato I art. 2bis", ("I", "2bis")),
    ("allegato 1 art. 4/2", ("1", "4/2")),
])
def test_split_annex_keeps_every_article_form(reference, expected):
    assert split_annex(reference) == expected


# --- a range of articles is never a number ----------------------------------------

@pytest.mark.parametrize("article", ["3-5", "3 - 5", "art. 3-5", "12-15bis"])
def test_range_is_recognised(article):
    assert "intervallo di articoli" in intervallo_articoli(article)


@pytest.mark.parametrize("article", ["3", "2-bis", "3-quater.1", "13 bis", "4/2", ""])
def test_single_article_is_not_a_range(article):
    assert intervallo_articoli(article) is None


def test_range_never_becomes_a_urn():
    # "3-5" used to become ~art35 and serve art. 35 c.c.
    nv = NormaVisitata(norma=Norma(tipo_atto="codice civile"), numero_articolo="3-5")
    with pytest.raises(IntervalloArticoli):
        nv.url()


async def test_entry_points_refuse_a_range_before_any_request():
    import json

    import mcp_legal_it.server  # noqa: F401
    from mcp_legal_it import api
    from mcp_legal_it.tools import legal_citations as lc

    cite = getattr(lc.cite_law, "fn", lc.cite_law)
    fetch = getattr(lc.fetch_law_article, "fn", lc.fetch_law_article)
    assert "intervallo" in json.loads(await cite(reference="art. 3-5 c.c.", formato="json"))["errore"]
    assert (await cite(reference="art. 3-5 c.c.")).startswith("**Errore**: «3-5» indica un intervallo")
    assert (await fetch(act_type="codice civile", article="3-5")).startswith("**Errore**: «3-5»")
    assert api.riferimento_da_parametri(tipo_atto="codice civile", numero_articolo="3-5").esito == "riferimento_non_valido"
    assert api.leggi_riferimento("art. 3-5 c.c.").esito == "riferimento_non_valido"


# --- verifica_citazioni: the court a decision belongs to ---------------------------

@pytest.mark.parametrize("reference, corte", [
    ("Corte cost. n. 238/2014", "corte_cost"),
    ("C. cost. 238/2014", "corte_cost"),
    ("Cons. St. n. 1/2020", "giustizia_amm"),
    ("Cons. St., sez. VI, n. 1/2020", "giustizia_amm"),
    ("TAR Lazio n. 123/2021", "giustizia_amm"),
    ("CGUE n. 1/2020", "cgue"),
    ("CTP Milano n. 5/2019", "tributaria"),
    ("Trib. Milano n. 100/2022", "merito"),
    ("Cass. sez. III n. 12345/2024", "cassazione"),
    ("Cass. sez. trib. n. 1/2024", "cassazione"),
    ("sez. lav. n. 5/2023", "cassazione"),
    ("n. 12345/2024", "cassazione"),
])
def test_court_named_by_the_citation(reference, corte):
    import mcp_legal_it.server  # noqa: F401
    from mcp_legal_it.tools import legal_citations as lc

    assert lc._corte_citata(reference) == corte
    assert lc._classify_citazione(reference) == "sentenza"


async def test_corte_costituzionale_is_checked_on_its_own_archive():
    from unittest.mock import AsyncMock, patch

    import mcp_legal_it.server  # noqa: F401
    from mcp_legal_it.lib._result import SearchResult
    from mcp_legal_it.tools import legal_citations as lc

    trovata = AsyncMock(return_value=SearchResult(success=True, source="corte_cost", results_text="x"))
    italgiure = AsyncMock(side_effect=AssertionError("Italgiure must not be asked"))
    with patch("mcp_legal_it.tools.corte_cost._leggi_pronuncia_costituzionale_impl", trovata), \
         patch("mcp_legal_it.tools.italgiure._leggi_sentenza_impl", italgiure):
        verdetto, nota = await lc._verifica_sentenza("Corte cost. n. 238/2014", "tutti")
    assert verdetto == "verificata" and "Corte cost. n. 238/2014" in nota
    trovata.assert_awaited_once_with(238, 2014)

    assente = AsyncMock(return_value=SearchResult(success=False, source="corte_cost", error_type="no_results"))
    with patch("mcp_legal_it.tools.corte_cost._leggi_pronuncia_costituzionale_impl", assente):
        assert (await lc._verifica_sentenza("Corte cost. n. 9999/2014", "tutti"))[0] == "inesistente"


@pytest.mark.parametrize("reference", ["Cons. St. n. 1/2020", "TAR Lazio n. 123/2021", "Trib. Milano n. 100/2022"])
async def test_other_courts_are_not_verifiable_and_never_sent_to_italgiure(reference):
    from unittest.mock import AsyncMock, patch

    import mcp_legal_it.server  # noqa: F401
    from mcp_legal_it.tools import legal_citations as lc

    italgiure = AsyncMock(side_effect=AssertionError("Italgiure must not be asked"))
    with patch("mcp_legal_it.tools.italgiure._leggi_sentenza_impl", italgiure):
        verdetto, nota = await lc._verifica_sentenza(reference, "tutti")
    assert verdetto == "non verificabile"
    assert "non è sull'archivio della Cassazione" in nota
