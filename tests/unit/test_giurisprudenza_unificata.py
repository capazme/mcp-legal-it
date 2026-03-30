"""Unit tests for cerca_giurisprudenza_unificata — unified cross-source jurisprudence search."""

from unittest.mock import AsyncMock, patch
import pytest

from src.tools.giurisprudenza_unificata import _cerca_giurisprudenza_unificata_impl
from src.lib._result import SearchResult


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

    with patch(_PATCH_GET_FONTI, return_value=_make_fonti(mock_cass, mock_cer, mock_amm, mock_cgue)):
        await _cerca_giurisprudenza_unificata_impl("contratto", anno_da="2020", anno_a="2024")

    # Cassazione receives integer years
    _, kwargs = mock_cass.call_args
    assert kwargs.get("anno_da") == 2020
    assert kwargs.get("anno_a") == 2024

    # CeRDEF receives ISO date strings
    _, kwargs = mock_cer.call_args
    assert kwargs.get("data_da") == "2020-01-01"
    assert kwargs.get("data_a") == "2024-12-31"

    # GA receives anno string
    _, kwargs = mock_amm.call_args
    assert kwargs.get("anno") == "2020"

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
