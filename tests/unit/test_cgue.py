"""Unit tests for CGUE (Court of Justice of the European Union) client and tools.

Tests are written against mocked httpx responses — no real network calls.
SPARQL and HTML fixtures mirror the actual CELLAR API structure.
"""

import re

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.cgue.client import (
    CORTI,
    TIPI_DOCUMENTO,
    MATERIE_KEYWORDS,
    CaseResult,
    _build_search_query,
    _excerpt,
    _parse_results,
    _parse_title,
    _parse_html_text,
    _term_filter,
    celex_of,
    fetch_case_metadata,
    format_result,
    format_full,
    normalize_riferimento,
    official_case_number,
    search_giurisprudenza,
)

from src.lib._result import SearchResult
from src.tools.cgue import (
    _cerca_giurisprudenza_cgue_impl,
    _leggi_sentenza_cgue_impl,
    _giurisprudenza_cgue_su_norma_impl,
    _ultime_sentenze_cgue_impl,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SPARQL_RESPONSE = {
    "head": {"vars": ["celex", "ecli", "date", "title", "type_code", "year", "case_num", "court", "cellar_exp"]},
    "results": {
        "bindings": [
            {
                "celex": {"type": "literal", "value": "62024CJ0008"},
                "ecli": {"type": "literal", "value": "ECLI:EU:C:2026:210"},
                "date": {"type": "literal", "value": "2026-03-17"},
                "title": {"type": "literal", "value": "Sentenza della Corte (Grande Sezione) del 17 marzo 2026.##Rinvio pregiudiziale \u2013 IVA \u2013 Sesta direttiva"},
                "type_code": {"type": "literal", "value": "CJ"},
                "year": {"type": "literal", "value": "2024"},
                "case_num": {"type": "literal", "value": "8"},
                "court": {"type": "uri", "value": "http://publications.europa.eu/resource/authority/corporate-body/CJ"},
                "cellar_exp": {"type": "literal", "value": "http://publications.europa.eu/resource/cellar/abc123.0006"},
            },
            {
                "celex": {"type": "literal", "value": "62023TJ0100"},
                "ecli": {"type": "literal", "value": "ECLI:EU:T:2025:500"},
                "date": {"type": "literal", "value": "2025-06-15"},
                "title": {"type": "literal", "value": "Sentenza del Tribunale (Seconda Sezione) del 15 giugno 2025.#Alfa Srl contro Commissione.#Concorrenza \u2013 Aiuti di Stato"},
                "type_code": {"type": "literal", "value": "TJ"},
                "year": {"type": "literal", "value": "2023"},
                "case_num": {"type": "literal", "value": "100"},
                "court": {"type": "uri", "value": "http://publications.europa.eu/resource/authority/corporate-body/TFP"},
                "cellar_exp": {"type": "literal", "value": "http://publications.europa.eu/resource/cellar/def456.0002"},
            },
        ]
    }
}

_SPARQL_RESPONSE_EMPTY = {
    "head": {"vars": ["celex"]},
    "results": {"bindings": []}
}

_JUDGMENT_HTML = """
<html><body>
<p>Edizione provvisoria</p>
<p>SENTENZA DELLA CORTE (Grande Sezione)</p>
<p>17 marzo 2026 (*)</p>
<p>&laquo; Rinvio pregiudiziale \u2013 IVA \u2013 Sesta direttiva &raquo;</p>
<p>Nella causa C-8/2024,</p>
<p>avente ad oggetto la domanda di pronuncia pregiudiziale proposta...</p>
<p>LA CORTE (Grande Sezione),</p>
<p>composta da...</p>
<p>ha pronunciato la seguente</p>
<p>Sentenza</p>
<script>var x = 1; alert("test");</script>
<style>body { color: red; }</style>
<p>1. La domanda di pronuncia pregiudiziale verte sull'interpretazione dell'articolo 168 della direttiva 2006/112/CE.</p>
<p>Per questi motivi, la Corte (Grande Sezione) dichiara:</p>
<p>L'articolo 168 della direttiva 2006/112/CE deve essere interpretato nel senso che...</p>
</body></html>
"""


# ---------------------------------------------------------------------------
# Tests: _build_search_query
# ---------------------------------------------------------------------------

class TestBuildSearchQuery:
    def test_no_filters(self):
        q = _build_search_query(keywords=[], limit=10)
        assert "PREFIX cdm:" in q
        assert "PREFIX xsd:" in q
        assert "ORDER BY DESC(?date)" in q
        assert "LIMIT 10" in q

    def test_keyword_filter(self):
        q = _build_search_query(keywords=["iva", "sesta direttiva"])
        assert 'CONTAINS(LCASE(?title), "iva")' in q
        assert 'CONTAINS(LCASE(?title), "sesta direttiva")' in q
        assert "||" in q

    def test_single_keyword(self):
        q = _build_search_query(keywords=["concorrenza"])
        assert 'CONTAINS(LCASE(?title), "concorrenza")' in q
        assert "||" not in q.split("FILTER")[1]  # no OR for single keyword

    def test_court_filter_cj(self):
        q = _build_search_query(keywords=[], court_code="CJ")
        assert '"CJ"' in q
        assert '"CC"' in q

    def test_court_filter_tj(self):
        q = _build_search_query(keywords=[], court_code="TJ")
        assert '"TJ"' in q
        assert '"TO"' in q

    def test_no_court_means_decisions_only(self):
        # Without a court the query still keeps the decisions of both courts and drops the
        # Official Journal notices (types CA, CB, TA, TB): they repeat a decision, no ECLI
        q = _build_search_query(keywords=[], court_code="")
        assert 'FILTER(STR(?type_code) IN ("CJ", "CC", "CO", "TJ", "TO"))' in q

    def test_type_filter_judg(self):
        q = _build_search_query(keywords=[], doc_type="JUDG")
        assert "resource-type/JUDG" in q

    def test_type_filter_order(self):
        q = _build_search_query(keywords=[], doc_type="ORDER")
        assert "resource-type/ORDER" in q

    def test_type_filter_opin_ag(self):
        q = _build_search_query(keywords=[], doc_type="OPIN_AG")
        assert "resource-type/OPIN_AG" in q

    def test_no_type_filter_when_empty(self):
        q = _build_search_query(keywords=[], doc_type="")
        assert "work_has_resource-type" not in q

    def test_date_range_from(self):
        q = _build_search_query(keywords=[], year_from="2020")
        assert '"2020-01-01"^^xsd:date' in q
        assert "FILTER(?date >=" in q

    def test_date_range_to(self):
        q = _build_search_query(keywords=[], year_to="2024")
        assert '"2024-12-31"^^xsd:date' in q
        assert "FILTER(?date <=" in q

    def test_date_range_both(self):
        q = _build_search_query(keywords=[], year_from="2020", year_to="2024")
        assert '"2020-01-01"^^xsd:date' in q
        assert '"2024-12-31"^^xsd:date' in q

    def test_celex_filters(self):
        q = _build_search_query(keywords=[])
        assert 'STRSTARTS(STR(?celex), "6")' in q
        assert 'CONTAINS(STR(?celex), "_")' in q

    def test_limit(self):
        q = _build_search_query(keywords=[], limit=25)
        assert "LIMIT 25" in q


# ---------------------------------------------------------------------------
# Tests: _execute_sparql (mocked)
# ---------------------------------------------------------------------------

class TestExecuteSparql:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.lib.cgue.client import _execute_sparql

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=_SPARQL_RESPONSE)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _execute_sparql("SELECT * WHERE {}")

        assert len(result) == 2
        assert result[0]["celex"]["value"] == "62024CJ0008"

    @pytest.mark.asyncio
    async def test_empty_results(self):
        from src.lib.cgue.client import _execute_sparql

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=_SPARQL_RESPONSE_EMPTY)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _execute_sparql("SELECT * WHERE {}")

        assert result == []

    @pytest.mark.asyncio
    async def test_http_error(self):
        from src.lib.cgue.client import _execute_sparql

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.RequestError):
                await _execute_sparql("SELECT * WHERE {}")


# ---------------------------------------------------------------------------
# Tests: _parse_results
# ---------------------------------------------------------------------------

class TestParseResults:
    def test_two_results(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        assert len(results) == 2

    def test_first_result_cj(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        doc = results[0]
        assert doc.celex == "62024CJ0008"
        assert doc.ecli == "ECLI:EU:C:2026:210"
        assert doc.date == "2026-03-17"
        assert doc.doc_type == "JUDG"
        assert doc.cellar_uri == "http://publications.europa.eu/resource/cellar/abc123.0006"

    def test_first_result_case_number_cj(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        doc = results[0]
        # Official form: the Court writes the year with two digits (C-311/18), not C-311/2018
        assert doc.case_number == "C-8/24"

    def test_second_result_tj(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        doc = results[1]
        assert doc.celex == "62023TJ0100"
        assert doc.ecli == "ECLI:EU:T:2025:500"
        assert doc.date == "2025-06-15"

    def test_second_result_case_number_tj(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        doc = results[1]
        assert doc.case_number == "T-100/23"

    def test_court_derived_from_type_code(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        # CELLAR's work_created_by_agent lists a corporate body AND a CELLAR UUID per work:
        # the court is read from the CELEX type code instead (CJ/CC/CO -> CJ, TJ/TO -> TJ)
        assert results[0].court == "CJ"
        assert results[1].court == "TJ"

    def test_title_parsed(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        # First result has ## separator (no parties, directly subject)
        assert "Sentenza della Corte" in results[0].title
        # Second result has three parts: header # parties # subject
        assert "Alfa Srl" in results[1].title

    def test_empty_bindings(self):
        results = _parse_results([])
        assert results == []

    def test_tj_doc_type_is_judg(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        assert results[1].doc_type == "JUDG"

    def _type_binding(self, celex, type_code, title):
        return {
            "celex": {"type": "literal", "value": celex},
            "ecli": {"type": "literal", "value": "ECLI:EU:C:2024:1"},
            "date": {"type": "literal", "value": "2024-01-10"},
            "title": {"type": "literal", "value": title},
            "type_code": {"type": "literal", "value": type_code},
            "year": {"type": "literal", "value": "2024"},
            "case_num": {"type": "literal", "value": "1"},
            "cellar_exp": {"type": "literal", "value": "http://publications.europa.eu/resource/cellar/xyz.0006"},
        }

    def test_co_type_code_gives_order(self):
        # CELEX type CO = order of the Court (62024CO0491 "Ordinanza della Corte (Decima Sezione)")
        results = _parse_results([self._type_binding("62024CO0001", "CO", "Ordinanza.")])
        assert results[0].doc_type == "ORDER"
        assert results[0].case_number == "C-1/24"

    def test_cc_type_code_gives_ag_opinion(self):
        # CELEX type CC = AG opinion (62022CC0769 "Conclusioni dell'avvocato generale T. Capeta")
        results = _parse_results([self._type_binding("62024CC0001", "CC", "Conclusioni.")])
        assert results[0].doc_type == "OPIN_AG"
        assert results[0].court == "CJ"


# ---------------------------------------------------------------------------
# Tests: _parse_title
# ---------------------------------------------------------------------------

class TestParseTitle:
    def test_double_hash_separator(self):
        raw = "Sentenza della Corte (Grande Sezione) del 17 marzo 2026.##Rinvio pregiudiziale – IVA"
        header, parties, subject = _parse_title(raw)
        assert "Sentenza della Corte" in header
        assert parties == "Rinvio pregiudiziale \u2013 IVA"
        assert subject == ""

    def test_single_hash_three_parts(self):
        raw = "Sentenza del Tribunale.#Alfa Srl contro Commissione.#Concorrenza – Aiuti di Stato"
        header, parties, subject = _parse_title(raw)
        assert "Sentenza del Tribunale" in header
        assert parties == "Alfa Srl contro Commissione."
        assert "Concorrenza" in subject

    def test_no_separator(self):
        raw = "Sentenza senza separatori"
        header, parties, subject = _parse_title(raw)
        assert header == "Sentenza senza separatori"
        assert parties == ""
        assert subject == ""

    def test_empty_string(self):
        header, parties, subject = _parse_title("")
        assert header == ""
        assert parties == ""
        assert subject == ""

    def test_strips_whitespace(self):
        raw = " Header .## Parti . # Subject "
        header, parties, subject = _parse_title(raw)
        assert header == "Header ."
        assert parties == "Parti ."


# ---------------------------------------------------------------------------
# Tests: _fetch_html and _parse_html_text
# ---------------------------------------------------------------------------

class TestFetchHtmlText:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.lib.cgue.client import _fetch_html

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = _JUDGMENT_HTML

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_html("http://publications.europa.eu/resource/cellar/abc.0006")

        assert "CORTE" in result

    @pytest.mark.asyncio
    async def test_http_error(self):
        from src.lib.cgue.client import _fetch_html

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_404
        ))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await _fetch_html("http://publications.europa.eu/resource/cellar/notfound.0006")


class TestParseHtmlText:
    def test_removes_scripts(self):
        text = _parse_html_text(_JUDGMENT_HTML)
        assert "var x = 1" not in text
        assert "alert" not in text

    def test_removes_styles(self):
        text = _parse_html_text(_JUDGMENT_HTML)
        assert "color: red" not in text

    def test_preserves_content(self):
        text = _parse_html_text(_JUDGMENT_HTML)
        assert "CORTE" in text
        assert "Rinvio pregiudiziale" in text
        assert "articolo 168" in text

    def test_empty_html(self):
        text = _parse_html_text("<html><body></body></html>")
        assert text == ""


# ---------------------------------------------------------------------------
# Tests: format_result
# ---------------------------------------------------------------------------

class TestFormatResult:
    def _make_doc(self):
        return CaseResult(
            celex="62024CJ0008",
            ecli="ECLI:EU:C:2026:210",
            case_number="C-8/2024",
            date="2026-03-17",
            title="Sentenza della Corte (Grande Sezione) del 17 marzo 2026. | Rinvio pregiudiziale – IVA",
            court="CJ",
            doc_type="JUDG",
            cellar_uri="http://publications.europa.eu/resource/cellar/abc123.0006",
        )

    def test_contains_case_number(self):
        doc = self._make_doc()
        text = format_result(doc)
        assert "C-8/2024" in text

    def test_contains_celex(self):
        doc = self._make_doc()
        text = format_result(doc)
        assert "62024CJ0008" in text

    def test_contains_ecli(self):
        doc = self._make_doc()
        text = format_result(doc)
        assert "ECLI:EU:C:2026:210" in text

    def test_contains_date(self):
        doc = self._make_doc()
        text = format_result(doc)
        assert "2026-03-17" in text

    def test_contains_cellar_uri(self):
        doc = self._make_doc()
        text = format_result(doc)
        assert "abc123.0006" in text

    def test_long_title_truncated(self):
        doc = CaseResult(
            celex="1", ecli="E", case_number="C-1/2024", date="2024-01-01",
            title="x" * 1500, court="CJ", doc_type="JUDG",
            cellar_uri="http://example.com/uri",
        )
        text = format_result(doc)
        # The title is one long summary line (parties, subject, norms applied): kept up to 1000 chars
        assert "x" * 1000 in text
        assert "x" * 1001 not in text

    def test_no_ecli_omits_ecli_line(self):
        doc = CaseResult(
            celex="62024CJ0008", ecli="", case_number="C-8/2024", date="2026-03-17",
            title="Sentenza.", court="CJ", doc_type="JUDG",
            cellar_uri="http://example.com/uri",
        )
        text = format_result(doc)
        assert "**ECLI**" not in text


# ---------------------------------------------------------------------------
# Tests: format_full
# ---------------------------------------------------------------------------

class TestFormatFull:
    def test_basic_formatting(self):
        result = format_full("C-8/2024", "Testo della sentenza.", "ECLI:EU:C:2026:210")
        assert "# C-8/2024" in result
        assert "ECLI:EU:C:2026:210" in result
        assert "Testo della sentenza." in result

    def test_truncation_at_25000(self):
        long_text = "a" * 30000
        result = format_full("C-1/2024", long_text, "ECLI:EU:C:2024:1")
        assert "Testo troncato" in result
        assert "25000" in result

    def test_no_truncation_for_short_text(self):
        result = format_full("C-1/2024", "breve testo", "ECLI:EU:C:2024:1")
        assert "troncato" not in result

    def test_empty_ecli_omitted(self):
        result = format_full("C-1/2024", "Testo.", "")
        assert "**ECLI**" not in result

    def test_ecli_in_header(self):
        result = format_full("C-8/2024", "Testo.", "ECLI:EU:C:2026:210")
        assert "ECLI:EU:C:2026:210" in result


# ---------------------------------------------------------------------------
# Tests: Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_corti_has_corte_di_giustizia(self):
        assert "corte_di_giustizia" in CORTI
        assert CORTI["corte_di_giustizia"] == "CJ"

    def test_corti_has_tribunale(self):
        assert "tribunale" in CORTI
        assert CORTI["tribunale"] == "TJ"

    def test_corti_has_tutte(self):
        assert "tutte" in CORTI
        assert CORTI["tutte"] == ""

    def test_tipi_documento_has_sentenza(self):
        assert "sentenza" in TIPI_DOCUMENTO
        assert TIPI_DOCUMENTO["sentenza"] == "JUDG"

    def test_tipi_documento_has_ordinanza(self):
        assert "ordinanza" in TIPI_DOCUMENTO
        assert TIPI_DOCUMENTO["ordinanza"] == "ORDER"

    def test_tipi_documento_has_conclusioni_ag(self):
        assert "conclusioni_ag" in TIPI_DOCUMENTO
        assert TIPI_DOCUMENTO["conclusioni_ag"] == "OPIN_AG"

    def test_materie_keywords_has_iva(self):
        assert "iva" in MATERIE_KEYWORDS
        assert "iva" in MATERIE_KEYWORDS["iva"]

    def test_materie_keywords_has_concorrenza(self):
        assert "concorrenza" in MATERIE_KEYWORDS

    def test_materie_keywords_has_7_entries(self):
        assert len(MATERIE_KEYWORDS) == 7


# ---------------------------------------------------------------------------
# Tests: _cerca_giurisprudenza_cgue_impl
# ---------------------------------------------------------------------------

def _make_sparql_mock(response_data):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=response_data)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


class TestCercaGiurisprudenzaCgueImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("IVA")

        assert isinstance(result, SearchResult)
        assert result.success
        assert "Trovate" in result.results_text
        assert "C-8/24" in result.results_text

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("inesistente")

        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "no_results"
        assert "Nessuna" in result.to_str()

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("IVA")

        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "source_down"
        assert "Errore" in result.to_str()

    @pytest.mark.asyncio
    async def test_max_risultati_capped_at_50(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("IVA", max_risultati=100)

        assert isinstance(result, SearchResult)
        assert result.success
        assert "Trovate" in result.results_text

    @pytest.mark.asyncio
    async def test_with_corte_filter(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("IVA", corte="corte_di_giustizia")

        assert isinstance(result, SearchResult)
        assert "Trovate" in result.to_str() or "Nessuna" in result.to_str()

    @pytest.mark.asyncio
    async def test_empty_query_still_works(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("")

        assert isinstance(result, SearchResult)
        assert "Trovate" in result.to_str() or "Nessuna" in result.to_str()


# ---------------------------------------------------------------------------
# Tests: _leggi_sentenza_cgue_impl
# ---------------------------------------------------------------------------

class TestLeggiSentenzaCgueImpl:
    @pytest.mark.asyncio
    async def test_returns_full_text(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = _JUDGMENT_HTML

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_sentenza_cgue_impl(
                "http://publications.europa.eu/resource/cellar/abc123.0006"
            )

        assert isinstance(result, SearchResult)
        assert result.success
        assert "CORTE" in result.results_text
        assert "articolo 168" in result.results_text

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_404
        ))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_sentenza_cgue_impl(
                "http://publications.europa.eu/resource/cellar/notfound.0006"
            )

        assert isinstance(result, SearchResult)
        assert not result.success
        assert "Errore" in result.to_str()


# ---------------------------------------------------------------------------
# Tests: _giurisprudenza_cgue_su_norma_impl
# ---------------------------------------------------------------------------

class TestGiurisprudenzaCgueSuNormaImpl:
    @pytest.mark.asyncio
    async def test_delegates_to_search(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_cgue_su_norma_impl("art. 101 TFUE")

        assert isinstance(result, SearchResult)
        assert result.success
        assert "Sentenze CGUE che citano" in result.results_text
        assert "art. 101 TFUE" in result.results_text

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_cgue_su_norma_impl("art. 999 TFUE")

        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "no_results"
        assert "Nessuna" in result.to_str()

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_cgue_su_norma_impl("art. 101 TFUE")

        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "source_down"
        assert "Errore" in result.to_str()


# ---------------------------------------------------------------------------
# Tests: _ultime_sentenze_cgue_impl
# ---------------------------------------------------------------------------

class TestUltimeSentenzeCgueImpl:
    @pytest.mark.asyncio
    async def test_returns_latest(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl()

        assert isinstance(result, SearchResult)
        assert result.success
        assert "Ultime sentenze CGUE" in result.results_text

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl()

        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "no_results"
        assert "Nessuna" in result.to_str()

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl()

        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "source_down"
        assert "Errore" in result.to_str()

    @pytest.mark.asyncio
    async def test_with_court_filter(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl(corte="tribunale")

        assert isinstance(result, SearchResult)
        assert "Ultime sentenze CGUE" in result.to_str() or "Nessuna" in result.to_str()

    @pytest.mark.asyncio
    async def test_with_materia_filter(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl(materia="iva")

        assert isinstance(result, SearchResult)
        assert "Ultime sentenze CGUE" in result.to_str() or "Nessuna" in result.to_str()


# ---------------------------------------------------------------------------
# Corrections of the CGUE benchmark (2026-09): values checked on CELLAR
# ---------------------------------------------------------------------------

def _binding(celex, exp, *, type_code="CJ", year="2018", case_num="311", ecli="ECLI:EU:C:2020:559",
             date="2020-07-16", title="Sentenza della Corte (Grande Sezione) del 16 luglio 2020."):
    return {
        "celex": {"type": "literal", "value": celex},
        "ecli": {"type": "literal", "value": ecli},
        "date": {"type": "literal", "value": date},
        "title": {"type": "literal", "value": title},
        "type_code": {"type": "literal", "value": type_code},
        "year": {"type": "literal", "value": year},
        "case_num": {"type": "literal", "value": case_num},
        "cellar_exp": {"type": "literal", "value": exp},
    }


def _sent_query(mock_client):
    return mock_client.post.call_args.kwargs["data"]["query"]


class TestCourtFilterUsesStr:
    """cdm:resource_legal_type is an xsd:string literal: a plain "CJ" never equals it in Virtuoso
    (COUNT = 0 on CELEX 62018CJ0311, CELLAR SPARQL 2026-09-28), so the filter must go through STR()."""

    def test_corte_di_giustizia(self):
        q = _build_search_query(keywords=[], court_code="CJ")
        assert 'FILTER(STR(?type_code) IN ("CJ", "CC", "CO"))' in q
        assert "FILTER(?type_code IN" not in q

    def test_tribunale(self):
        q = _build_search_query(keywords=[], court_code="TJ")
        assert 'FILTER(STR(?type_code) IN ("TJ", "TO"))' in q
        assert "FILTER(?type_code IN" not in q

    def test_court_not_in_projection(self):
        # work_created_by_agent has one value per body plus a CELLAR UUID: it multiplied each decision
        q = _build_search_query(keywords=[])
        select = q.split("WHERE")[0]
        assert "?court" not in select
        assert "work_created_by_agent" not in q

    def test_stable_order(self):
        q = _build_search_query(keywords=[])
        assert "ORDER BY DESC(?date) ?celex ?cellar_exp" in q


class TestOfficialCaseNumber:
    # The Court writes C-311/18 (two-digit year): ECLI:EU:C:2020:559, CURIA and EUR-Lex
    def test_court_of_justice(self):
        assert official_case_number("CJ", "311", "2018") == "C-311/18"

    def test_general_court(self):
        assert official_case_number("TJ", "100", "2023") == "T-100/23"

    def test_order(self):
        assert official_case_number("CO", "491", "2024") == "C-491/24"


class TestParseResultsDeduplication:
    def test_same_celex_listed_once(self):
        # 62018CJ0311 has two works / three rows on CELLAR: one decision, one entry
        rows = [
            _binding("62018CJ0311", "http://publications.europa.eu/resource/cellar/c93f72bb.0003"),
            _binding("62018CJ0311", "http://publications.europa.eu/resource/cellar/d17ef5a0.0003"),
            _binding("62018CJ0311", "http://publications.europa.eu/resource/cellar/d17ef5a0.0004"),
            _binding("62019CJ0693", "http://publications.europa.eu/resource/cellar/spv.0003",
                     year="2019", case_num="693", ecli="ECLI:EU:C:2022:395", date="2022-05-17"),
        ]
        docs = _parse_results(rows)
        assert [d.celex for d in docs] == ["62018CJ0311", "62019CJ0693"]
        assert docs[0].case_number == "C-311/18"
        assert docs[0].court == "CJ"
        assert docs[0].cellar_uri.endswith("c93f72bb.0003")

    @pytest.mark.asyncio
    async def test_limit_counts_decisions_not_rows(self):
        rows = [_binding("62018CJ0311", f"http://x/{i}") for i in range(3)] + [
            _binding("62019CJ0693", "http://x/spv", year="2019", case_num="693", ecli="E2"),
            _binding("62020CJ0001", "http://x/a", year="2020", case_num="1", ecli="E3"),
        ]
        mock_client = _make_sparql_mock({"results": {"bindings": rows}})
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            docs = await search_giurisprudenza(keywords=[], limit=2)
        assert [d.celex for d in docs] == ["62018CJ0311", "62019CJ0693"]
        # more rows than wanted are requested, because several rows can be one decision
        assert re.search(r"LIMIT (\d+)", _sent_query(mock_client)).group(1) == "6"


class TestMateriaNarrows:
    """`materia` is an AND filter (docstring: "Filtra"), it used to add words in OR."""

    @pytest.mark.asyncio
    async def test_materia_is_a_separate_filter(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            await search_giurisprudenza(keywords=["Schrems"], materia="protezione_dati")
        q = _sent_query(mock_client)
        filters = [line for line in q.splitlines() if line.startswith("  FILTER(") and "LCASE" in line]
        assert len(filters) == 2
        keyword_filter = next(f for f in filters if '"schrems"' in f)
        assert "dati personali" not in keyword_filter
        materia_filter = next(f for f in filters if "dati personali" in f)
        assert '"schrems"' not in materia_filter
        # words of the materia are alternatives among themselves
        assert "vita privata" in materia_filter and "||" in materia_filter

    @pytest.mark.asyncio
    async def test_comma_words_stay_alternatives(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_cgue_impl("clausole abusive, ingiunzione")
        q = _sent_query(mock_client)
        line = next(ln for ln in q.splitlines() if '"clausole abusive"' in ln)
        assert '"ingiunzione"' in line and "||" in line


class TestTermFilter:
    @staticmethod
    def _pattern(flt: str) -> str:
        # REGEX(REPLACE(LCASE(STR(?title)), "<nbsp>", " "), "<pattern>")
        return re.search(r'", " "\), "(.*)"\)$', flt).group(1)

    def _matches(self, term: str, title: str) -> bool:
        return re.search(self._pattern(_term_filter(term)), title.lower().replace("\xa0", " ")) is not None

    def test_article_matches_cited_number(self):
        assert self._matches("articolo 101", "Concorrenza – Articolo 101 TFUE – Intesa")
        # "paragrafo 2" is not an article: "Articolo 101, paragrafo 2, TFUE" cites 101 only
        assert self._matches("articolo 101", "Articolo 101, paragrafo 2, TFUE")
        assert not self._matches("articolo 2", "Articolo 101, paragrafo 2, TFUE")

    def test_article_number_is_not_a_prefix(self):
        assert not self._matches("articolo 7", "Articolo 70 del regolamento")
        assert not self._matches("articolo 1", "Articolo 101 TFUE")

    def test_article_in_a_list(self):
        # "Articoli 7, 8 e 47" of the Charter cites all three
        title = "Carta dei diritti fondamentali – Articoli 7, 8 e 47 – Regolamento (UE) 2016/679"
        assert self._matches("articolo 7", title)
        assert self._matches("articolo 8", title)
        assert self._matches("articolo 47", title)
        assert not self._matches("articolo 4", title)

    def test_no_break_space_read_as_space(self):
        # titles carry U+00A0 ("Articolo\xa07"): the filter replaces it before matching
        assert 'REPLACE(LCASE(STR(?title)), "\xa0", " ")' in _term_filter("articolo 7")
        assert self._matches("articolo 7", "Articolo\xa07, 8 e\xa047")

    def test_suffix(self):
        assert self._matches("articolo 7 bis", "Articolo 7 bis del regolamento")
        assert not self._matches("articolo 7 ter", "Articolo 7 bis del regolamento")

    def test_short_acronym_needs_word_boundaries(self):
        assert self._matches("iva", "Rinvio pregiudiziale – IVA – Sesta direttiva")
        assert not self._matches("iva", "Direttiva 2006/112/CE")

    def test_long_term_is_substring(self):
        assert _term_filter("2006/112").startswith("CONTAINS(")
        assert '"2006/112"' in _term_filter("2006/112")


class TestNormalizeRiferimento:
    # CELLAR titles write "Articolo 101 TFUE" / "direttiva 2006/112/CE", never "art. 101 TFUE"
    @pytest.mark.parametrize("ref, terms", [
        ("art. 101 TFUE", ["articolo 101", "tfue"]),
        ("Articolo 101 TFUE", ["articolo 101", "tfue"]),
        ("art.101 TFUE", ["articolo 101", "tfue"]),
        ("art. 7 GDPR", ["articolo 7", "2016/679"]),
        ("direttiva 2006/112", ["2006/112"]),
        ("direttiva 2006/112/CE", ["2006/112"]),
        ("regolamento (UE) 2016/679", ["2016/679"]),
        ("art. 34 TFUE libera circolazione merci", ["articolo 34", "tfue", "libera", "circolazione", "merci"]),
        ("artt. 7 e 8 CDFUE", ["articolo 7", "articolo 8", "carta dei diritti fondamentali"]),
        ("art. 7 bis", ["articolo 7 bis"]),
        ("principio di proporzionalità", ["principio", "proporzionalità"]),
        ("", []),
        ("  ", []),
    ])
    def test_terms(self, ref, terms):
        assert normalize_riferimento(ref) == terms

    def test_paragraph_number_is_not_an_article(self):
        assert normalize_riferimento("art. 101, paragrafo 2, TFUE") == ["articolo 101", "paragrafo", "2", "tfue"]


class TestSuNormaSendsAndOfTerms:
    @pytest.mark.asyncio
    async def test_art_abbreviato_becomes_articolo_and_tfue(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_cgue_su_norma_impl("art. 101 TFUE", anno_da="2020")
        assert result.success
        q = _sent_query(mock_client)
        # "art. 101 TFUE" as one substring matches no title; two ANDed conditions do
        assert 'CONTAINS(LCASE(?title), "art. 101 tfue")' not in q
        assert "articol[oi]" in q and "101" in q
        assert "tfue" in q
        conditions = [ln for ln in q.splitlines() if ln.startswith("  FILTER(REGEX(")]
        assert len(conditions) == 2
        assert '"2020-01-01"^^xsd:date' in q

    @pytest.mark.asyncio
    async def test_corte_filter_with_reference_uses_str(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            await _giurisprudenza_cgue_su_norma_impl("direttiva 2006/112", corte="corte_di_giustizia", anno_da="2025")
        q = _sent_query(mock_client)
        assert 'FILTER(STR(?type_code) IN ("CJ", "CC", "CO"))' in q
        assert 'CONTAINS(REPLACE(LCASE(STR(?title)), "\xa0", " "), "2006/112")' in q

    @pytest.mark.asyncio
    async def test_empty_reference_is_bad_input(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_cgue_su_norma_impl("   ")
        assert not result.success
        assert result.error_type == "bad_input"
        mock_client.post.assert_not_called()


class TestParseTitleHeadnote:
    # Preliminary references have four '#' segments: header, parties, referring court,
    # headnote with the norms applied, then the case reference ("Causa C-311/18.")
    RAW = (
        "Sentenza della Corte (Grande Sezione) del 16 luglio 2020.#"
        "Data Protection Commissioner contro Facebook Ireland Limited e Maximillian Schrems.#"
        "Domanda di pronuncia pregiudiziale proposta dalla High Court (Irlanda).#"
        "Rinvio pregiudiziale – Regolamento (UE) 2016/679 – Articolo 45.#"
        "Causa C-311/18."
    )

    def test_headnote_with_norms_is_kept(self):
        header, parties, subject = _parse_title(self.RAW)
        assert "16 luglio 2020" in header
        assert parties.startswith("Data Protection Commissioner")
        assert "Regolamento (UE) 2016/679" in subject
        assert "Articolo 45" in subject
        assert "High Court" in subject

    def test_trailing_case_reference_dropped(self):
        _, _, subject = _parse_title(self.RAW)
        assert "Causa C-311/18" not in subject

    def test_three_segments_unchanged(self):
        header, parties, subject = _parse_title("Sentenza.#Alfa contro Beta.#Concorrenza")
        assert (header, parties, subject) == ("Sentenza.", "Alfa contro Beta.", "Concorrenza")


class TestExcerptKeepsOperativePart:
    """The operative part of Schrems II starts at char 185425 of 189410 ("Per questi motivi, la Corte
    (Grande Sezione) dichiara", point 5: decision 2016/1250 invalid): cutting only the head lost it
    (art. 87, lett. i), Regolamento di procedura della Corte: the judgment contains the operative part)."""

    DISPOSITIVO = (
        "Per questi motivi, la Corte (Grande Sezione) dichiara:\n"
        "5)\nLa decisione di esecuzione (UE) 2016/1250 della Commissione, del 12 luglio 2016, e' invalida.\n"
        "Firme"
    )

    def _long(self, body_len=100000):
        return "Nella causa C-311/18, la Corte. " + "x" * body_len + "\n" + self.DISPOSITIVO

    def test_operative_part_beyond_the_limit_is_appended(self):
        text = self._long()
        body, note = _excerpt(text)
        assert body.startswith("Nella causa C-311/18")
        assert body.endswith("Firme")
        assert "Per questi motivi, la Corte (Grande Sezione) dichiara" in body
        assert "e' invalida" in body
        assert f"su {len(text)} totali" in body  # note of the omitted characters
        assert "Omessi i caratteri 25001-" in body
        assert note == ""  # operative part complete

    def test_omitted_range_is_exact(self):
        text = self._long()
        start = text.rindex("Per questi motivi")
        body, _ = _excerpt(text)
        assert f"Omessi i caratteri 25001-{start} su {len(text)} totali" in body

    def test_last_occurrence_opens_the_operative_part(self):
        # "Per questi motivi" can appear in quotations inside the reasoning
        text = "y" * 30000 + " la clausola 'Per questi motivi' del contratto " + "z" * 50000 + "\n" + self.DISPOSITIVO
        body, _ = _excerpt(text)
        assert body.endswith("Firme")
        assert body.count("Per questi motivi") == 1  # the quotation is inside the omitted part

    def test_long_operative_part_is_capped(self):
        text = "x" * 60000 + "Per questi motivi, dichiara:\n" + "d" * 20000
        body, note = _excerpt(text)
        assert "Per questi motivi, dichiara" in body
        assert len(body) < 25000 + 8000 + 400
        assert "dopo il dispositivo" in note

    def test_operative_part_inside_the_first_block(self):
        text = "x" * 20000 + "Per questi motivi, dichiara:\n" + "d" * 12000 + "\n" + "w" * 20000
        body, note = _excerpt(text)
        assert "Per questi motivi" in body
        # the block is extended to cover 8000 characters from the formula
        assert len(body) == 20000 + 8000
        assert "Testo troncato a" in note

    def test_no_formula_falls_back_to_head_truncation(self):
        body, note = _excerpt("a" * 30000)
        assert body == "a" * 25000
        assert note == "*[Testo troncato a 25000 caratteri su 30000 totali]*"

    def test_short_text_unchanged(self):
        assert _excerpt("breve Per questi motivi") == ("breve Per questi motivi", "")

    def test_format_full_header_carries_case_number_ecli_and_date(self):
        out = format_full(
            "62018CJ0311", self._long(), "ECLI:EU:C:2020:559", case_ref="C-311/18", date="2020-07-16",
        )
        head = out.split("\n\n", 1)[0]
        assert head.splitlines() == [
            "# 62018CJ0311", "**Causa**: C-311/18", "**ECLI**: ECLI:EU:C:2020:559", "**Data**: 2020-07-16",
        ]
        assert "e' invalida" in out


def _celex_lookup_response(ecli="ECLI:EU:C:2020:559"):
    row = {
        "date": {"type": "literal", "value": "2020-07-16"},
        "type_code": {"type": "literal", "value": "CJ"},
        "year": {"type": "literal", "value": "2018"},
        "case_num": {"type": "literal", "value": "311"},
    }
    rows = []
    if ecli is not None:
        rows.append({**row, "ecli": {"type": "literal", "value": ecli}})
    rows.append(dict(row))  # a second work of the same CELEX without ECLI
    return {"results": {"bindings": rows}}


class TestCaseMetadata:
    def test_celex_from_alias_uri(self):
        assert celex_of("http://publications.europa.eu/resource/celex/62018CJ0311") == "62018CJ0311"

    def test_celex_from_first_line_of_text(self):
        uri = "http://publications.europa.eu/resource/cellar/c93f72bb.0003"
        assert celex_of(uri, "62018CJ0311\nSENTENZA") == "62018CJ0311"

    def test_no_celex(self):
        assert celex_of("http://publications.europa.eu/resource/cellar/abc123.0006", "SENTENZA DELLA CORTE") == ""

    @pytest.mark.asyncio
    async def test_lookup_returns_official_case_number_and_ecli(self):
        mock_client = _make_sparql_mock(_celex_lookup_response())
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            meta = await fetch_case_metadata("62018CJ0311")
        assert meta == {"case_ref": "C-311/18", "date": "2020-07-16", "ecli": "ECLI:EU:C:2020:559"}
        assert '"62018CJ0311"^^xsd:string' in _sent_query(mock_client)

    @pytest.mark.asyncio
    async def test_lookup_prefers_the_row_with_ecli(self):
        response = _celex_lookup_response()
        response["results"]["bindings"].reverse()  # row without ECLI first
        mock_client = _make_sparql_mock(response)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            meta = await fetch_case_metadata("62018CJ0311")
        assert meta["ecli"] == "ECLI:EU:C:2020:559"

    @pytest.mark.asyncio
    async def test_lookup_is_fail_open(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            assert await fetch_case_metadata("62018CJ0311") == {}

    @pytest.mark.asyncio
    async def test_lookup_rejects_a_malformed_celex_without_a_request(self):
        mock_client = _make_sparql_mock(_celex_lookup_response())
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            assert await fetch_case_metadata('62018CJ0311"; DROP') == {}
        mock_client.post.assert_not_called()


class TestLeggiSentenzaHeader:
    def _client(self, html, sparql):
        get_resp = MagicMock()
        get_resp.raise_for_status = MagicMock()
        get_resp.text = html
        post_resp = MagicMock()
        post_resp.raise_for_status = MagicMock()
        post_resp.json = MagicMock(return_value=sparql)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=get_resp)
        mock_client.post = AsyncMock(return_value=post_resp)
        return mock_client

    @pytest.mark.asyncio
    async def test_header_has_case_number_ecli_and_date(self):
        long_html = (
            "<html><body><p>62018CJ0311</p><p>SENTENZA DELLA CORTE (Grande Sezione)</p>"
            + "<p>" + "x" * 40000 + "</p>"
            + "<p>Per questi motivi, la Corte (Grande Sezione) dichiara:</p>"
            + "<p>La decisione di esecuzione (UE) 2016/1250 della Commissione e' invalida.</p></body></html>"
        )
        mock_client = self._client(long_html, _celex_lookup_response())
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_sentenza_cgue_impl("http://publications.europa.eu/resource/celex/62018CJ0311")
        assert result.success
        text = result.results_text
        assert text.startswith("# 62018CJ0311\n**Causa**: C-311/18\n**ECLI**: ECLI:EU:C:2020:559\n**Data**: 2020-07-16")
        # the operative part reaches the reader although the text is far over the limit
        assert "Per questi motivi, la Corte (Grande Sezione) dichiara" in text
        assert "e' invalida" in text
        assert "Omessi i caratteri" in text

    @pytest.mark.asyncio
    async def test_metadata_failure_still_returns_the_text(self):
        html = "<html><body><p>62018CJ0311</p><p>" + "Testo della sentenza. " * 30 + "</p></body></html>"
        mock_client = self._client(html, _celex_lookup_response())
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_sentenza_cgue_impl("http://publications.europa.eu/resource/celex/62018CJ0311")
        assert result.success
        assert result.results_text.startswith("# 62018CJ0311\n")
        assert "**ECLI**" not in result.results_text
        assert "Testo della sentenza." in result.results_text
