"""Unit tests for CGUE (Court of Justice of the European Union) client and tools.

Tests are written against mocked httpx responses — no real network calls.
SPARQL and HTML fixtures mirror the actual CELLAR API structure.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.cgue.client import (
    CORTI,
    TIPI_DOCUMENTO,
    MATERIE_KEYWORDS,
    CaseResult,
    _build_search_query,
    _parse_results,
    _parse_title,
    _parse_html_text,
    format_result,
    format_full,
)

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

    def test_no_court_filter_when_empty(self):
        q = _build_search_query(keywords=[], court_code="")
        assert "type_code IN" not in q

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
        assert doc.case_number == "C-8/2024"

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
        assert doc.case_number == "T-100/2023"

    def test_court_extracted_from_uri(self):
        bindings = _SPARQL_RESPONSE["results"]["bindings"]
        results = _parse_results(bindings)
        # Court URI last segment: CJ
        assert results[0].court == "CJ"
        # Court URI last segment: TFP
        assert results[1].court == "TFP"

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

    def test_cc_type_code_gives_order(self):
        binding = {
            "celex": {"type": "literal", "value": "62024CC0001"},
            "ecli": {"type": "literal", "value": "ECLI:EU:C:2024:1"},
            "date": {"type": "literal", "value": "2024-01-10"},
            "title": {"type": "literal", "value": "Ordinanza."},
            "type_code": {"type": "literal", "value": "CC"},
            "year": {"type": "literal", "value": "2024"},
            "case_num": {"type": "literal", "value": "1"},
            "court": {"type": "uri", "value": "http://publications.europa.eu/resource/authority/corporate-body/CJ"},
            "cellar_exp": {"type": "literal", "value": "http://publications.europa.eu/resource/cellar/xyz.0006"},
        }
        results = _parse_results([binding])
        assert results[0].doc_type == "ORDER"
        assert results[0].case_number == "C-1/2024"


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
            title="x" * 500, court="CJ", doc_type="JUDG",
            cellar_uri="http://example.com/uri",
        )
        text = format_result(doc)
        # Title is truncated to 400 chars max
        assert "x" * 401 not in text

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

        assert "Trovate" in result
        assert "C-8/2024" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("inesistente")

        assert "Nessuna" in result

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("IVA")

        assert "Errore" in result

    @pytest.mark.asyncio
    async def test_max_risultati_capped_at_50(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("IVA", max_risultati=100)

        # Should succeed, capped to 50
        assert "Trovate" in result

    @pytest.mark.asyncio
    async def test_with_corte_filter(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("IVA", corte="corte_di_giustizia")

        assert "Trovate" in result or "Nessuna" in result

    @pytest.mark.asyncio
    async def test_empty_query_still_works(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_cgue_impl("")

        assert "Trovate" in result or "Nessuna" in result


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

        assert "CORTE" in result
        assert "articolo 168" in result

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

        assert "Errore" in result


# ---------------------------------------------------------------------------
# Tests: _giurisprudenza_cgue_su_norma_impl
# ---------------------------------------------------------------------------

class TestGiurisprudenzaCgueSuNormaImpl:
    @pytest.mark.asyncio
    async def test_delegates_to_search(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_cgue_su_norma_impl("art. 101 TFUE")

        assert "Sentenze CGUE che citano" in result
        assert "art. 101 TFUE" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_cgue_su_norma_impl("art. 999 TFUE")

        assert "Nessuna" in result

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_cgue_su_norma_impl("art. 101 TFUE")

        assert "Errore" in result


# ---------------------------------------------------------------------------
# Tests: _ultime_sentenze_cgue_impl
# ---------------------------------------------------------------------------

class TestUltimeSentenzeCgueImpl:
    @pytest.mark.asyncio
    async def test_returns_latest(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl()

        assert "Ultime sentenze CGUE" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE_EMPTY)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl()

        assert "Nessuna" in result

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl()

        assert "Errore" in result

    @pytest.mark.asyncio
    async def test_with_court_filter(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl(corte="tribunale")

        assert "Ultime sentenze CGUE" in result or "Nessuna" in result

    @pytest.mark.asyncio
    async def test_with_materia_filter(self):
        mock_client = _make_sparql_mock(_SPARQL_RESPONSE)
        with patch("src.lib.cgue.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_cgue_impl(materia="iva")

        assert "Ultime sentenze CGUE" in result or "Nessuna" in result
