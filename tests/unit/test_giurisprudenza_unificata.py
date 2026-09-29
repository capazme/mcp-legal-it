"""Unit tests for cerca_giurisprudenza_unificata — unified cross-source jurisprudence search."""

from unittest.mock import AsyncMock, patch
import pytest

from src.tools.giurisprudenza_unificata import _cerca_giurisprudenza_unificata_impl
from src.lib._result import SearchResult
from src.lib.cgue.client import CaseResult
from src.lib.giustizia_amm.client import ProvvedimentoResult


def _sr_ok(source: str, num: int, text: str) -> SearchResult:
    return SearchResult(success=True, source=source, num_found=num, results_text=text)


def _sr_no_results(source: str) -> SearchResult:
    return SearchResult(success=False, source=source, error_type="no_results", results_text="Nessun risultato.")


def _sr_down(source: str) -> SearchResult:
    return SearchResult(success=False, source=source, error_type="source_down", error_message="timeout")


def _make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue):
    """Return a _get_fonti-compatible dict with given mocks."""
    return {
        "cassazione": ("Cassazione (Italgiure)", mock_cass),
        "tributaria": ("Tributaria (CeRDEF)", mock_cer),
        "amministrativa": ("Amministrativa (TAR/CdS)", mock_amm),
        "ue": ("CGUE", mock_cgue),
    }


_PATCH_GET_FONTI = "src.tools.giurisprudenza_unificata._get_fonti"
_PATCH_GA_SEARCH = "src.lib.giustizia_amm.client.search_provvedimenti"
_PATCH_CGUE_SEARCH = "src.lib.cgue.client.search_giurisprudenza"


def _ga(anno: str, numero: str = "1") -> ProvvedimentoResult:
    return ProvvedimentoResult(
        sede="tar_rm", sede_label="TAR Lazio - Roma", nrg="202500001", tipo="SENTENZA", anno=anno,
        nome_file=f"{anno}{numero}.xml", data_deposito="", oggetto="concessioni demaniali", numero=numero,
    )


def _case(celex: str = "62022CJ0001", title: str = "Sentenza della Corte.") -> CaseResult:
    return CaseResult(
        celex=celex, ecli="ECLI:EU:C:2022:1", case_number="C-1/2022", date="2022-01-01",
        title=title, court="CJ", doc_type="JUDG", cellar_uri="http://publications.europa.eu/resource/cellar/x",
    )


@pytest.mark.asyncio
async def test_all_sources_succeed():
    """All 4 sources return results — all 4 sections present in output."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 3, "Cass. results"))
    mock_cer = AsyncMock(return_value=_sr_ok("cerdef", 2, "CeRDEF results"))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 4, "GA results"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "CGUE results"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("responsabilità medica")

    assert "## Cassazione (Italgiure)" in result
    assert "## Tributaria (CeRDEF)" in result
    assert "## Amministrativa (TAR/CdS)" in result
    assert "## CGUE" in result
    assert "Cass. results" in result
    assert "CeRDEF results" in result
    assert "GA results" in result
    assert "CGUE results" in result
    assert "responsabilità medica" in result


@pytest.mark.asyncio
async def test_one_source_exception():
    """One source raises an exception — error noted, other 3 sections present."""
    mock_cass = AsyncMock(side_effect=ConnectionError("SSL error"))
    mock_cer = AsyncMock(return_value=_sr_ok("cerdef", 2, "CeRDEF results"))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 1, "GA results"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "CGUE results"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("appalto pubblico")

    assert "errore:" in result
    assert "## Cassazione (Italgiure)" in result
    assert "CeRDEF results" in result
    assert "GA results" in result
    assert "CGUE results" in result
    assert "errore" in result


@pytest.mark.asyncio
async def test_one_source_no_results():
    """One source returns no_results — shown as 0 risultati, no crash."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 5, "Cass. results"))
    mock_cer = AsyncMock(return_value=_sr_no_results("cerdef"))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 2, "GA results"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "CGUE results"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("nichilismo giuridico")

    assert "0 risultati" in result
    assert "Cass. results" in result


@pytest.mark.asyncio
async def test_one_source_down():
    """One source is down (source_down) — shown as non raggiungibile."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 2, "Cass. results"))
    mock_cer = AsyncMock(return_value=_sr_ok("cerdef", 1, "CeRDEF results"))
    mock_amm = AsyncMock(return_value=_sr_down("giustizia_amm"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "CGUE results"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("urbanistica")

    assert "non raggiungibile" in result
    assert "Cass. results" in result
    assert "CeRDEF results" in result


@pytest.mark.asyncio
async def test_one_source_error_is_not_zero_results():
    """A source that answered with an error page (source_error) is an error, not "0 risultati" (#46)."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 2, "Cass. results"))
    mock_cer = AsyncMock(return_value=SearchResult(
        success=False, source="cerdef", error_type="source_error",
        error_message="il portale ha rifiutato la ricerca (Errore: Ambito di ricerca non valido)",
    ))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 1, "TAR results"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "CGUE results"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("IVA")

    assert "Tributaria (CeRDEF) (errore)" in result
    assert "Tributaria (CeRDEF) (0 risultati)" not in result
    assert "Ambito di ricerca non valido" in result


@pytest.mark.asyncio
async def test_single_source_filter_cassazione():
    """fonti='cassazione' — only Italgiure queried, others not called."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 3, "Cass. results"))
    mock_cer = AsyncMock(return_value=_sr_ok("cerdef", 1, "CeRDEF results"))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 1, "GA results"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "CGUE results"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("dolo", fonti="cassazione")

    mock_cass.assert_awaited_once()
    mock_cer.assert_not_awaited()
    mock_amm.assert_not_awaited()
    mock_cgue.assert_not_awaited()
    assert "## Cassazione (Italgiure)" in result
    assert "## Tributaria (CeRDEF)" not in result


@pytest.mark.asyncio
async def test_two_source_filter():
    """fonti='cassazione,ue' — only Italgiure and CGUE queried."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 2, "Cass."))
    mock_cer = AsyncMock(return_value=_sr_ok("cerdef", 1, "CeRDEF"))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 1, "GA"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 3, "CGUE"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("IVA", fonti="cassazione,ue")

    mock_cass.assert_awaited_once()
    mock_cgue.assert_awaited_once()
    mock_cer.assert_not_awaited()
    mock_amm.assert_not_awaited()
    assert "## Cassazione (Italgiure)" in result
    assert "## CGUE" in result
    assert "## Tributaria (CeRDEF)" not in result
    assert "## Amministrativa (TAR/CdS)" not in result


@pytest.mark.asyncio
async def test_footer_shows_correct_counts():
    """Footer line summarises results per source."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 5, "..."))
    mock_cer = AsyncMock(return_value=_sr_no_results("cerdef"))
    mock_amm = AsyncMock(return_value=_sr_down("giustizia_amm"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 3, "..."))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("test query")

    assert "**Fonti consultate**" in result
    assert "5 risultati" in result
    assert "0 risultati" in result
    assert "non raggiungibile" in result
    assert "3 risultati" in result


@pytest.mark.asyncio
async def test_empty_query_all_sources_queried():
    """Empty query string — all 4 sources still queried."""
    mock_cass = AsyncMock(return_value=_sr_no_results("italgiure"))
    mock_cer = AsyncMock(return_value=_sr_no_results("cerdef"))
    mock_amm = AsyncMock(return_value=_sr_no_results("giustizia_amm"))
    mock_cgue = AsyncMock(return_value=_sr_no_results("cgue"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("")

    mock_cass.assert_awaited_once()
    mock_cer.assert_awaited_once()
    mock_amm.assert_awaited_once()
    mock_cgue.assert_awaited_once()
    assert "## Cassazione (Italgiure)" in result
    assert "## Tributaria (CeRDEF)" in result
    assert "## Amministrativa (TAR/CdS)" in result
    assert "## CGUE" in result


@pytest.mark.asyncio
async def test_anno_da_anno_a_forwarded():
    """anno_da and anno_a are passed to each source in the correct format."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 1, "ok"))
    mock_cer = AsyncMock(return_value=_sr_ok("cerdef", 1, "ok"))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 1, "ok"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "ok"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)), \
         patch(_PATCH_GA_SEARCH, new=AsyncMock(return_value=[])) as ga_search:
        await _cerca_giurisprudenza_unificata_impl("contratto", anno_da="2020", anno_a="2024")

    # Cassazione receives integer years
    _, kwargs = mock_cass.call_args
    assert kwargs.get("anno_da") == 2020
    assert kwargs.get("anno_a") == 2024

    # CeRDEF receives DD/MM/YYYY date strings (the format its web form expects)
    _, kwargs = mock_cer.call_args
    assert kwargs.get("data_da") == "01/01/2020"
    assert kwargs.get("data_a") == "31/12/2024"

    # GA: with a year range the portal is asked for more rows and the range is applied here
    # (the source tool takes a single exact year and used to get anno_da only)
    mock_amm.assert_not_awaited()
    _, kwargs = ga_search.call_args
    assert kwargs.get("rows") == 50 and "anno" not in kwargs

    # CGUE receives string years
    _, kwargs = mock_cgue.call_args
    assert kwargs.get("anno_da") == "2020"
    assert kwargs.get("anno_a") == "2024"


@pytest.mark.asyncio
async def test_invalid_fonti_falls_back_to_all():
    """Invalid source names in fonti fall back to querying all sources."""
    mock_cass = AsyncMock(return_value=_sr_ok("italgiure", 1, "ok"))
    mock_cer = AsyncMock(return_value=_sr_ok("cerdef", 1, "ok"))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 1, "ok"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "ok"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        await _cerca_giurisprudenza_unificata_impl("test", fonti="nonsense,invalid")

    mock_cass.assert_awaited_once()
    mock_cer.assert_awaited_once()
    mock_amm.assert_awaited_once()
    mock_cgue.assert_awaited_once()


@pytest.mark.asyncio
async def test_plain_string_result_included():
    """A plain string return (e.g. legacy) is included as-is in the section body."""
    mock_cass = AsyncMock(return_value="plain string from italgiure")
    mock_cer = AsyncMock(return_value=_sr_ok("cerdef", 1, "CeRDEF ok"))
    mock_amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 1, "GA ok"))
    mock_cgue = AsyncMock(return_value=_sr_ok("cgue", 1, "CGUE ok"))

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        result = await _cerca_giurisprudenza_unificata_impl("legacy test")

    assert "plain string from italgiure" in result



# ---------------------------------------------------------------------------
# Corrections of the italgiure_orientamento benchmark cluster (2026-09-29)
# ---------------------------------------------------------------------------

def _fonti_only(amm=None, cgue=None):
    ok = lambda src: AsyncMock(return_value=_sr_ok(src, 1, "ok"))  # noqa: E731
    return _make_fonti(ok("italgiure"), ok("cerdef"), amm or ok("giustizia_amm"), cgue or ok("cgue"))


@pytest.mark.asyncio
async def test_amministrativa_range_keeps_both_years():
    """anno_da=2025, anno_a=2026 must not become the exact year 2025 (read 2026-09-25: the same
    query without years returns TAR Lazio n. 202615210 of 2026, but with the range the section
    was '0 risultati' because anno=anno_da and anno_a was dropped)."""
    docs = [_ga("2026", "202615210"), _ga("2026", "202615138"), _ga("2025", "202501000"), _ga("2021", "202100017")]
    amm = AsyncMock()
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only(amm=amm)), \
         patch(_PATCH_GA_SEARCH, new=AsyncMock(return_value=docs)) as ga_search:
        out = await _cerca_giurisprudenza_unificata_impl(
            "concessioni demaniali marittime", fonti="amministrativa", anno_da="2025", anno_a="2026",
        )
    amm.assert_not_awaited()
    assert ga_search.call_args.kwargs["rows"] == 50
    assert "n. 202615210 (2026)" in out and "n. 202615138 (2026)" in out and "n. 202501000 (2025)" in out
    assert "(2021)" not in out
    assert "Amministrativa (TAR/CdS) (3 risultati)" in out


@pytest.mark.asyncio
async def test_amministrativa_range_open_ended_and_truncated_after_the_filter():
    docs = [_ga("2026", "3"), _ga("2024", "2"), _ga("2023", "1"), _ga("2019", "9")]
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only()), \
         patch(_PATCH_GA_SEARCH, new=AsyncMock(return_value=docs)):
        since = await _cerca_giurisprudenza_unificata_impl("x", fonti="amministrativa", anno_da="2023")
        until = await _cerca_giurisprudenza_unificata_impl("x", fonti="amministrativa", anno_a="2023")
        cut = await _cerca_giurisprudenza_unificata_impl(
            "x", fonti="amministrativa", anno_da="2020", max_risultati=2,
        )
    assert "(2019)" not in since and since.count("### TAR") == 3
    assert "(2026)" not in until and "(2024)" not in until and until.count("### TAR") == 2
    assert cut.count("### TAR") == 2  # truncated to max_risultati AFTER the year filter


@pytest.mark.asyncio
async def test_amministrativa_year_with_no_match_keeps_the_explanation():
    """The portal note on the year filter must survive: a bare '0 risultati' hid why (read 2026-09-25,
    concessioni demaniali marittime 2021: Cons. Stato Ad. plen. 17/2021 exists but is not among the newest)."""
    docs = [_ga("2026", "1"), _ga("2026", "2")]
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only()), \
         patch(_PATCH_GA_SEARCH, new=AsyncMock(return_value=docs)):
        out = await _cerca_giurisprudenza_unificata_impl(
            "concessioni demaniali marittime", fonti="amministrativa", anno_da="2021", anno_a="2021",
        )
    assert "non espone più un filtro per anno" in out
    assert "Amministrativa (TAR/CdS) (0 risultati)" in out


@pytest.mark.asyncio
async def test_amministrativa_without_years_uses_the_source_tool():
    amm = AsyncMock(return_value=_sr_ok("giustizia_amm", 1, "GA ok"))
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only(amm=amm)):
        await _cerca_giurisprudenza_unificata_impl("x", fonti="amministrativa", tipo_provvedimento="sentenza")
    amm.assert_awaited_once()
    assert amm.call_args.kwargs == {"tipo": "sentenza", "max_risultati": 5}


@pytest.mark.asyncio
async def test_amministrativa_source_down_with_a_range():
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only()), \
         patch(_PATCH_GA_SEARCH, new=AsyncMock(side_effect=ConnectionError("timeout"))):
        out = await _cerca_giurisprudenza_unificata_impl("x", fonti="amministrativa", anno_da="2025")
    assert "Amministrativa (TAR/CdS) (non raggiungibile)" in out


@pytest.mark.asyncio
async def test_no_results_keeps_the_text_of_the_source():
    """'0 risultati' replaced the source's explanation (e.g. 'Nessuna sentenza CGUE trovata per ...')."""
    cgue = AsyncMock(return_value=SearchResult(
        success=False, source="cgue", error_type="no_results",
        results_text="Nessuna sentenza CGUE trovata per: _rinvio_",
    ))
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only(cgue=cgue)):
        out = await _cerca_giurisprudenza_unificata_impl("rinvio", fonti="ue")
    assert "Nessuna sentenza CGUE trovata per: _rinvio_" in out
    assert "CGUE (0 risultati)" in out


@pytest.mark.asyncio
async def test_cgue_count_is_distinct_decisions_not_rows():
    """Read 2026-09-25: 'CGUE (20 risultati)' for 10 judgments, each listed twice (one SPARQL row per
    court agent)."""
    block = "### C-{n}/2022\n**CELEX**: 6202{n:02d}CJ00{n:02d}\n**Data**: 2022-05-17\n"
    text = "\n".join(block.format(n=n) for n in list(range(10)) * 2)
    cgue = AsyncMock(return_value=_sr_ok("cgue", 20, text))
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only(cgue=cgue)):
        out = await _cerca_giurisprudenza_unificata_impl("clausole abusive", fonti="ue")
    assert "CGUE (10 risultati)" in out


@pytest.mark.asyncio
async def test_cgue_phrase_without_commas_falls_back_to_all_words():
    """'clausole abusive consumatori' (no commas) is ONE title substring and finds nothing, although
    CELLAR titles read 'Clausole abusive nei contratti stipulati con i consumatori' (13 judgments of
    2022, SPV Project 1503 among them, read 2026-09-25)."""
    cgue = AsyncMock(return_value=SearchResult(
        success=False, source="cgue", error_type="no_results", results_text="Nessuna sentenza CGUE",
    ))
    found = [_case("62019CJ0693"), _case("62019CJ0831")]
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only(cgue=cgue)), \
         patch(_PATCH_CGUE_SEARCH, new=AsyncMock(return_value=found)) as search:
        out = await _cerca_giurisprudenza_unificata_impl(
            "clausole abusive consumatori", fonti="ue", anno_da="2022", anno_a="2022",
            tipo_provvedimento="sentenza", max_risultati=20,
        )
    kwargs = search.call_args.kwargs
    assert kwargs["keywords"] == ["clausole", "abusive", "consumatori"]
    assert kwargs["match_all"] is True
    assert (kwargs["year_from"], kwargs["year_to"], kwargs["doc_type"]) == ("2022", "2022", "sentenza")
    assert "cercate le parole clausole, abusive, consumatori tutte insieme nel titolo" in out
    assert "62019CJ0693" in out and "CGUE (2 risultati)" in out


@pytest.mark.asyncio
async def test_cgue_fallback_drops_stopwords_and_skips_comma_queries():
    cgue = AsyncMock(return_value=SearchResult(
        success=False, source="cgue", error_type="no_results", results_text="Nessuna",
    ))
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only(cgue=cgue)), \
         patch(_PATCH_CGUE_SEARCH, new=AsyncMock(return_value=[_case()])) as search:
        await _cerca_giurisprudenza_unificata_impl("responsabilità dei produttori", fonti="ue")
        assert search.call_args.kwargs["keywords"] == ["responsabilità", "produttori"]
        search.reset_mock()
        # commas mean OR: the caller already chose the semantics, no fallback
        out = await _cerca_giurisprudenza_unificata_impl("clausole abusive, consumatori", fonti="ue")
        search.assert_not_called()
        assert "CGUE (0 risultati)" in out


@pytest.mark.asyncio
async def test_cgue_fallback_keeps_the_original_answer_when_it_finds_nothing_or_fails():
    cgue = AsyncMock(return_value=SearchResult(
        success=False, source="cgue", error_type="no_results", results_text="Nessuna sentenza CGUE trovata",
    ))
    for search in (AsyncMock(return_value=[]), AsyncMock(side_effect=ConnectionError("down"))):
        with patch(_PATCH_GET_FONTI, return_value=_fonti_only(cgue=cgue)), \
             patch(_PATCH_CGUE_SEARCH, new=search):
            out = await _cerca_giurisprudenza_unificata_impl("alfa beta gamma", fonti="ue")
        assert "Nessuna sentenza CGUE trovata" in out and "CGUE (0 risultati)" in out


@pytest.mark.asyncio
async def test_single_word_query_is_not_retried_on_cgue():
    cgue = AsyncMock(return_value=SearchResult(
        success=False, source="cgue", error_type="no_results", results_text="Nessuna",
    ))
    with patch(_PATCH_GET_FONTI, return_value=_fonti_only(cgue=cgue)), \
         patch(_PATCH_CGUE_SEARCH, new=AsyncMock(return_value=[_case()])) as search:
        await _cerca_giurisprudenza_unificata_impl("appalti", fonti="ue")
    search.assert_not_called()
