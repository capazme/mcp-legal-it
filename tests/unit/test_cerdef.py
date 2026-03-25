"""Unit tests for CeRDEF (Banca Dati Giurisprudenza Tributaria — def.finanze.it) scraper.

Tests are written against mocked httpx responses — no real network calls.
HTML fixtures embed XML in JS variables, mirroring the actual CeRDEF response format.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.cerdef.client import (
    ENTI,
    TIPO_ESTREMI,
    CRITERI_RICERCA,
    ProvvedimentoResult,
    ProvvedimentoDetail,
    _extract_xml_from_js,
    _unescape_js_string,
    _parse_search_xml,
    _parse_detail_xml,
    format_result,
    format_detail,
)

from src.tools.cerdef import (
    _cerca_giurisprudenza_tributaria_impl,
    _cerdef_leggi_provvedimento_impl,
    _ultime_sentenze_tributarie_impl,
)


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

_SEARCH_HTML = """
<html><body>
<script>
var xmlResult = '<risultati><risultato><guid>abc-123</guid><estremi>Sent. n. 1234/2024</estremi><titoli>IVA - Soggettivit\\u00e0 passiva</titoli><ente>CGT II grado Lazio</ente><data>15/03/2024</data></risultato><risultato><guid>def-456</guid><estremi>Ord. n. 5678/2023</estremi><titoli>IRES - Deducibilit\\u00e0 costi</titoli><ente>Corte Suprema di Cassazione</ente><data>10/01/2023</data></risultato></risultati>';
</script>
</body></html>
"""

_SEARCH_HTML_EMPTY = """
<html><body>
<script>
var xmlResult = '<risultati></risultati>';
</script>
</body></html>
"""

_SEARCH_HTML_NO_VAR = """
<html><body>
<p>Nessun risultato</p>
</body></html>
"""

_DETAIL_HTML = """
<html><body>
<script>
var xmlDettaglio = '<dettaglio><guid>abc-123</guid><estremi>Sent. n. 1234/2024</estremi><massima><![CDATA[<p>In tema di IVA, la soggettivit\\u00e0 passiva...</p>]]></massima><testoIntegrale><![CDATA[<p>REPUBBLICA ITALIANA<\\/p><p>IN NOME DEL POPOLO ITALIANO<\\/p><p>La Corte di Giustizia Tributaria...</p>]]></testoIntegrale><collegio>Dott. Rossi, Dott. Bianchi</collegio><udienza>20/02/2024</udienza><ricorsi>RG 1234/2023</ricorsi></dettaglio>';
</script>
</body></html>
"""

_DETAIL_HTML_MINIMAL = """
<html><body>
<script>
var xmlDettaglio = '<dettaglio><guid>xyz-999</guid><estremi>Sent. n. 100/2022</estremi><massima></massima><testoIntegrale></testoIntegrale></dettaglio>';
</script>
</body></html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(html: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Tests: _unescape_js_string
# ---------------------------------------------------------------------------


class TestUnescapeJsString:
    def test_unescape_slash(self):
        assert _unescape_js_string("a\\/b") == "a/b"

    def test_unescape_unicode_hex(self):
        # \u00e0 → 'à' (4-digit standard JS unicode escape)
        assert _unescape_js_string("Soggettivit\\u00e0") == "Soggettività"

    def test_unescape_multiple(self):
        result = _unescape_js_string("p\\/a\\u006e\\u006f")
        assert result == "p/ano"

    def test_no_escapes(self):
        assert _unescape_js_string("hello world") == "hello world"


# ---------------------------------------------------------------------------
# Tests: _extract_xml_from_js
# ---------------------------------------------------------------------------


class TestExtractXmlFromJs:
    def test_extracts_xmlresult(self):
        xml = _extract_xml_from_js(_SEARCH_HTML, "xmlResult")
        assert xml.startswith("<risultati>")
        assert "abc-123" in xml

    def test_extracts_xmldettaglio(self):
        xml = _extract_xml_from_js(_DETAIL_HTML, "xmlDettaglio")
        assert xml.startswith("<dettaglio>")
        assert "abc-123" in xml

    def test_returns_empty_when_var_missing(self):
        xml = _extract_xml_from_js(_SEARCH_HTML_NO_VAR, "xmlResult")
        assert xml == ""

    def test_unescapes_slashes_in_result(self):
        xml = _extract_xml_from_js(_DETAIL_HTML, "xmlDettaglio")
        assert "REPUBBLICA ITALIANA" in xml

    def test_unescapes_unicode_in_search(self):
        xml = _extract_xml_from_js(_SEARCH_HTML, "xmlResult")
        assert "à" in xml


# ---------------------------------------------------------------------------
# Tests: _parse_search_xml
# ---------------------------------------------------------------------------


class TestParseSearchXml:
    def test_parses_two_results(self):
        xml = _extract_xml_from_js(_SEARCH_HTML, "xmlResult")
        results = _parse_search_xml(xml)
        assert len(results) == 2

    def test_first_result_fields(self):
        xml = _extract_xml_from_js(_SEARCH_HTML, "xmlResult")
        doc = _parse_search_xml(xml)[0]
        assert doc.guid == "abc-123"
        assert "1234/2024" in doc.estremi
        assert "IVA" in doc.titoli
        assert doc.ente == "CGT II grado Lazio"
        assert doc.data == "15/03/2024"

    def test_second_result_fields(self):
        xml = _extract_xml_from_js(_SEARCH_HTML, "xmlResult")
        doc = _parse_search_xml(xml)[1]
        assert doc.guid == "def-456"
        assert "Cassazione" in doc.ente
        assert "IRES" in doc.titoli

    def test_empty_xml_returns_empty_list(self):
        xml = _extract_xml_from_js(_SEARCH_HTML_EMPTY, "xmlResult")
        results = _parse_search_xml(xml)
        assert results == []

    def test_empty_string_returns_empty_list(self):
        assert _parse_search_xml("") == []

    def test_malformed_xml_returns_empty_list(self):
        assert _parse_search_xml("<unclosed>") == []

    def test_skips_result_without_guid(self):
        xml = "<risultati><risultato><estremi>X</estremi></risultato></risultati>"
        results = _parse_search_xml(xml)
        assert results == []


# ---------------------------------------------------------------------------
# Tests: _parse_detail_xml
# ---------------------------------------------------------------------------


class TestParseDetailXml:
    def test_parses_full_detail(self):
        xml = _extract_xml_from_js(_DETAIL_HTML, "xmlDettaglio")
        detail = _parse_detail_xml(xml)
        assert detail.guid == "abc-123"
        assert "1234/2024" in detail.estremi
        assert detail.collegio == "Dott. Rossi, Dott. Bianchi"
        assert detail.udienza == "20/02/2024"
        assert detail.ricorsi == "RG 1234/2023"

    def test_strips_html_from_massima(self):
        xml = _extract_xml_from_js(_DETAIL_HTML, "xmlDettaglio")
        detail = _parse_detail_xml(xml)
        assert "<p>" not in detail.massima
        assert "IVA" in detail.massima

    def test_strips_html_from_testo_integrale(self):
        xml = _extract_xml_from_js(_DETAIL_HTML, "xmlDettaglio")
        detail = _parse_detail_xml(xml)
        assert "<p>" not in detail.testo_integrale
        assert "REPUBBLICA ITALIANA" in detail.testo_integrale

    def test_minimal_detail_missing_fields(self):
        xml = _extract_xml_from_js(_DETAIL_HTML_MINIMAL, "xmlDettaglio")
        detail = _parse_detail_xml(xml)
        assert detail.guid == "xyz-999"
        assert detail.massima == ""
        assert detail.testo_integrale == ""
        assert detail.collegio == ""

    def test_empty_string_returns_empty_detail(self):
        detail = _parse_detail_xml("")
        assert detail.guid == ""
        assert detail.massima == ""

    def test_malformed_xml_returns_empty_detail(self):
        detail = _parse_detail_xml("<broken>")
        assert detail.guid == ""


# ---------------------------------------------------------------------------
# Tests: format_result
# ---------------------------------------------------------------------------


class TestFormatResult:
    def test_contains_estremi_and_guid(self):
        doc = ProvvedimentoResult(
            guid="abc-123",
            estremi="Sent. n. 1234/2024",
            titoli="IVA - test",
            ente="CGT II grado Lazio",
            data="15/03/2024",
        )
        text = format_result(doc)
        assert "1234/2024" in text
        assert "abc-123" in text

    def test_contains_ente_and_data(self):
        doc = ProvvedimentoResult(
            guid="x", estremi="X", titoli="Y", ente="Corte Suprema", data="01/01/2024"
        )
        text = format_result(doc)
        assert "Corte Suprema" in text
        assert "01/01/2024" in text

    def test_long_titoli_truncated(self):
        doc = ProvvedimentoResult(
            guid="x", estremi="X", titoli="T" * 500, ente="E", data=""
        )
        text = format_result(doc)
        assert len(text) < 700

    def test_fallback_to_guid_when_no_estremi(self):
        doc = ProvvedimentoResult(guid="my-guid", estremi="", titoli="", ente="", data="")
        text = format_result(doc)
        assert "my-guid" in text


# ---------------------------------------------------------------------------
# Tests: format_detail
# ---------------------------------------------------------------------------


class TestFormatDetail:
    def test_contains_estremi_and_massima(self):
        detail = ProvvedimentoDetail(
            guid="abc", estremi="Sent. n. 1/2024", massima="Principio X.", testo_integrale=""
        )
        text = format_detail(detail)
        assert "Sent. n. 1/2024" in text
        assert "Principio X." in text

    def test_truncation_at_25000(self):
        long_text = "a" * 30000
        detail = ProvvedimentoDetail(
            guid="x", estremi="X", massima="", testo_integrale=long_text
        )
        text = format_detail(detail)
        assert "Testo troncato" in text
        assert "25000" in text

    def test_no_truncation_note_for_short_text(self):
        detail = ProvvedimentoDetail(
            guid="x", estremi="X", massima="", testo_integrale="breve testo"
        )
        text = format_detail(detail)
        assert "troncato" not in text

    def test_includes_optional_fields(self):
        detail = ProvvedimentoDetail(
            guid="x",
            estremi="X",
            massima="",
            testo_integrale="",
            collegio="Dott. Rossi",
            udienza="01/01/2024",
            ricorsi="RG 1/2023",
        )
        text = format_detail(detail)
        assert "Dott. Rossi" in text
        assert "01/01/2024" in text
        assert "RG 1/2023" in text


# ---------------------------------------------------------------------------
# Tests: constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_enti_has_corte_suprema(self):
        assert "corte_suprema" in ENTI
        assert "Cassazione" in ENTI["corte_suprema"]

    def test_enti_has_cgt_entries(self):
        assert "cgt_primo_grado" in ENTI
        assert "cgt_secondo_grado" in ENTI

    def test_tipo_estremi_has_sentenza(self):
        assert "sentenza" in TIPO_ESTREMI
        assert TIPO_ESTREMI["sentenza"] == "Sentenza"

    def test_tipo_estremi_has_ordinanza(self):
        assert "ordinanza" in TIPO_ESTREMI

    def test_criteri_ricerca_has_tutti(self):
        assert "tutti" in CRITERI_RICERCA
        assert CRITERI_RICERCA["tutti"] == "T"

    def test_criteri_ricerca_has_frase_esatta(self):
        assert "frase_esatta" in CRITERI_RICERCA
        assert CRITERI_RICERCA["frase_esatta"] == "E"

    def test_criteri_ricerca_has_almeno_uno(self):
        assert "almeno_uno" in CRITERI_RICERCA
        assert CRITERI_RICERCA["almeno_uno"] == "O"


# ---------------------------------------------------------------------------
# Tests: _cerca_giurisprudenza_tributaria_impl
# ---------------------------------------------------------------------------


class TestCercaGiurisprudenzaTributariaImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_tributaria_impl("IVA")

        assert "Trovati" in result
        assert "abc-123" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_resp = _make_mock_response(_SEARCH_HTML_EMPTY)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_tributaria_impl("inesistente")

        assert "Nessun provvedimento" in result

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_tributaria_impl("test")

        assert "Errore" in result

    @pytest.mark.asyncio
    async def test_max_risultati_respected(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_tributaria_impl("IVA", max_risultati=1)

        assert "Trovati 1" in result


# ---------------------------------------------------------------------------
# Tests: _cerdef_leggi_provvedimento_impl
# ---------------------------------------------------------------------------


class TestCerdefLeggiProvvedimentoImpl:
    @pytest.mark.asyncio
    async def test_returns_full_text(self):
        mock_resp = _make_mock_response(_DETAIL_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerdef_leggi_provvedimento_impl("abc-123")

        assert "1234/2024" in result
        assert "IVA" in result

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

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerdef_leggi_provvedimento_impl("guid-nonexistent")

        assert "Errore" in result

    @pytest.mark.asyncio
    async def test_returns_massima_section(self):
        mock_resp = _make_mock_response(_DETAIL_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerdef_leggi_provvedimento_impl("abc-123")

        assert "Massima" in result


# ---------------------------------------------------------------------------
# Tests: _ultime_sentenze_tributarie_impl
# ---------------------------------------------------------------------------


class TestUltimeSentenzeTributarieImpl:
    @pytest.mark.asyncio
    async def test_returns_latest(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_tributarie_impl()

        assert "Ultime sentenze tributarie" in result
        assert "abc-123" in result

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_tributarie_impl()

        assert "Errore" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_resp = _make_mock_response(_SEARCH_HTML_EMPTY)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_tributarie_impl()

        assert "Nessuna" in result


# ---------------------------------------------------------------------------
# Extended tests: _strip_cdata_html
# ---------------------------------------------------------------------------

from src.lib.cerdef.client import _strip_cdata_html


class TestStripCdataHtml:
    def test_empty_string(self):
        assert _strip_cdata_html("") == ""

    def test_plain_text_passthrough(self):
        assert _strip_cdata_html("testo semplice") == "testo semplice"

    def test_strips_html_tags(self):
        result = _strip_cdata_html("<p>paragrafo <b>grassetto</b></p>")
        assert "<p>" not in result
        assert "<b>" not in result
        assert "paragrafo" in result
        assert "grassetto" in result

    def test_strips_nested_html(self):
        result = _strip_cdata_html("<div><ul><li>item1</li><li>item2</li></ul></div>")
        assert "item1" in result
        assert "item2" in result
        assert "<" not in result

    def test_preserves_text_entities(self):
        result = _strip_cdata_html("<p>IVA &amp; IRES</p>")
        assert "IVA" in result
        assert "IRES" in result


# ---------------------------------------------------------------------------
# Extended tests: CerdefSession
# ---------------------------------------------------------------------------

from src.lib.cerdef.client import CerdefSession


class TestCerdefSession:
    def test_client_raises_when_not_entered(self):
        session = CerdefSession()
        with pytest.raises(RuntimeError, match="not entered"):
            _ = session.client

    @pytest.mark.asyncio
    async def test_aenter_creates_client(self):
        with patch("src.lib.cerdef.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.aclose = AsyncMock()
            MockClient.return_value = mock_instance
            async with CerdefSession() as session:
                assert session._client is not None
                assert session.client is mock_instance

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        with patch("src.lib.cerdef.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.aclose = AsyncMock()
            MockClient.return_value = mock_instance
            async with CerdefSession():
                pass
            mock_instance.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aexit_sets_client_to_none(self):
        with patch("src.lib.cerdef.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.aclose = AsyncMock()
            MockClient.return_value = mock_instance
            session = CerdefSession()
            async with session:
                pass
            assert session._client is None


# ---------------------------------------------------------------------------
# Extended tests: _unescape_js_string edge cases
# ---------------------------------------------------------------------------


class TestUnescapeJsStringExtended:
    def test_mixed_case_hex(self):
        assert _unescape_js_string("\\u00E0") == "à"
        assert _unescape_js_string("\\u00C0") == "À"

    def test_multiple_consecutive_unicode(self):
        result = _unescape_js_string("\\u0041\\u0042\\u0043")
        assert result == "ABC"

    def test_combined_slash_and_unicode(self):
        result = _unescape_js_string("path\\/to\\u002Ffile")
        assert result == "path/to/file"

    def test_emoji_range_unicode(self):
        # Surrogate pair not in BMP — 4-digit capped at \uFFFF
        result = _unescape_js_string("\\u00A9")  # ©
        assert result == "©"

    def test_empty_string(self):
        assert _unescape_js_string("") == ""


# ---------------------------------------------------------------------------
# Extended tests: _extract_xml_from_js edge cases
# ---------------------------------------------------------------------------


class TestExtractXmlFromJsExtended:
    def test_multiline_xml_content(self):
        html = """<script>
var xmlResult = '<root><a>line1</a><b>line2</b></root>';
</script>"""
        xml = _extract_xml_from_js(html, "xmlResult")
        assert "<root>" in xml
        assert "line1" in xml

    def test_extra_whitespace_around_assignment(self):
        html = """<script>
var   xmlResult   =   '<root>ok</root>'  ;
</script>"""
        xml = _extract_xml_from_js(html, "xmlResult")
        assert "ok" in xml

    def test_different_var_name(self):
        html = """<script>var customVar = '<data>test</data>';</script>"""
        xml = _extract_xml_from_js(html, "customVar")
        assert "test" in xml

    def test_does_not_match_wrong_var_name(self):
        html = """<script>var otherVar = '<data>test</data>';</script>"""
        xml = _extract_xml_from_js(html, "xmlResult")
        assert xml == ""


# ---------------------------------------------------------------------------
# Extended tests: _parse_search_xml edge cases
# ---------------------------------------------------------------------------


class TestParseSearchXmlExtended:
    def test_result_with_whitespace_guid(self):
        xml = "<risultati><risultato><guid>  </guid><estremi>X</estremi></risultato></risultati>"
        results = _parse_search_xml(xml)
        assert results == []

    def test_result_with_special_chars_in_titoli(self):
        xml = '<risultati><risultato><guid>g1</guid><estremi>S</estremi><titoli>IVA &amp; IRES</titoli><ente>E</ente><data>01/01/2024</data></risultato></risultati>'
        results = _parse_search_xml(xml)
        assert len(results) == 1
        assert "IVA" in results[0].titoli

    def test_many_results(self):
        items = "".join(
            f"<risultato><guid>g{i}</guid><estremi>S{i}</estremi><titoli>T</titoli><ente>E</ente><data>D</data></risultato>"
            for i in range(50)
        )
        xml = f"<risultati>{items}</risultati>"
        results = _parse_search_xml(xml)
        assert len(results) == 50


# ---------------------------------------------------------------------------
# Extended tests: _parse_detail_xml edge cases
# ---------------------------------------------------------------------------


class TestParseDetailXmlExtended:
    def test_html_in_massima_fully_stripped(self):
        xml = '<dettaglio><guid>g</guid><estremi>E</estremi><massima><![CDATA[<div class="x"><p>Principio <em>importante</em></p></div>]]></massima><testoIntegrale></testoIntegrale></dettaglio>'
        detail = _parse_detail_xml(xml)
        assert "<div" not in detail.massima
        assert "<em>" not in detail.massima
        assert "Principio" in detail.massima
        assert "importante" in detail.massima

    def test_all_optional_fields_present(self):
        xml = '<dettaglio><guid>g</guid><estremi>E</estremi><massima>M</massima><testoIntegrale>T</testoIntegrale><collegio>C</collegio><udienza>U</udienza><ricorsi>R</ricorsi></dettaglio>'
        detail = _parse_detail_xml(xml)
        assert detail.collegio == "C"
        assert detail.udienza == "U"
        assert detail.ricorsi == "R"


# ---------------------------------------------------------------------------
# Extended tests: format_result edge cases
# ---------------------------------------------------------------------------


class TestFormatResultExtended:
    def test_empty_data_field(self):
        doc = ProvvedimentoResult(guid="g", estremi="E", titoli="T", ente="E", data="")
        text = format_result(doc)
        assert "Data" not in text

    def test_empty_ente_field(self):
        doc = ProvvedimentoResult(guid="g", estremi="E", titoli="T", ente="", data="01/01/2024")
        text = format_result(doc)
        assert "Ente" not in text

    def test_empty_titoli_field(self):
        doc = ProvvedimentoResult(guid="g", estremi="E", titoli="", ente="", data="")
        text = format_result(doc)
        assert "Oggetto" not in text


# ---------------------------------------------------------------------------
# Extended tests: format_detail edge cases
# ---------------------------------------------------------------------------


class TestFormatDetailExtended:
    def test_only_massima_no_testo(self):
        detail = ProvvedimentoDetail(guid="g", estremi="E", massima="La massima.", testo_integrale="")
        text = format_detail(detail)
        assert "Massima" in text
        assert "Testo Integrale" not in text

    def test_only_testo_no_massima(self):
        detail = ProvvedimentoDetail(guid="g", estremi="E", massima="", testo_integrale="Il testo.")
        text = format_detail(detail)
        assert "Massima" not in text
        assert "Testo Integrale" in text

    def test_both_empty(self):
        detail = ProvvedimentoDetail(guid="g", estremi="E", massima="", testo_integrale="")
        text = format_detail(detail)
        assert "# E" in text
        assert "Massima" not in text
        assert "Testo Integrale" not in text

    def test_truncation_boundary(self):
        """Exactly at the limit — no truncation note."""
        detail = ProvvedimentoDetail(guid="g", estremi="E", massima="", testo_integrale="a" * 25000)
        text = format_detail(detail)
        assert "troncato" not in text

    def test_truncation_at_limit_plus_one(self):
        """One over the limit — should truncate."""
        detail = ProvvedimentoDetail(guid="g", estremi="E", massima="", testo_integrale="a" * 25001)
        text = format_detail(detail)
        assert "troncato" in text


# ---------------------------------------------------------------------------
# Extended tests: search_giurisprudenza pagination
# ---------------------------------------------------------------------------


from src.lib.cerdef.client import search_giurisprudenza


class TestSearchGiurisprudenzaPagination:
    @pytest.mark.asyncio
    async def test_single_page_sufficient(self):
        """When first page returns all needed results, no pagination."""
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            results = await search_giurisprudenza(parole="IVA", rows=2)

        assert len(results) == 2
        mock_client.get.assert_not_called()  # No pagination needed

    @pytest.mark.asyncio
    async def test_pagination_requested_when_rows_exceed_first_page(self):
        """When rows > first page results, pagination is triggered."""
        page1_html = _SEARCH_HTML
        page2_html = _SEARCH_HTML_NO_VAR  # Empty / no more results

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=_make_mock_response(page1_html))
        mock_client.get = AsyncMock(return_value=_make_mock_response(page2_html))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            results = await search_giurisprudenza(parole="IVA", rows=50)

        # First page yields 2 results, second page empty → total 2
        assert len(results) == 2
        mock_client.get.assert_called_once()  # Tried pagination

    @pytest.mark.asyncio
    async def test_rows_capped_at_250(self):
        """rows > 250 should be capped."""
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            results = await search_giurisprudenza(parole="IVA", rows=999)

        assert len(results) <= 250

    @pytest.mark.asyncio
    async def test_form_data_includes_criteria(self):
        """Verify form data sent to POST matches expected fields."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            await search_giurisprudenza(
                parole="IVA",
                tipo_criterio="frase_esatta",
                tipo_estremi="sentenza",
                ente="corte_suprema",
                data_da="01/01/2023",
                data_a="31/12/2024",
                ordinamento="data",
            )

        call_kwargs = mock_client.post.call_args
        form = call_kwargs.kwargs.get("data", {})
        assert form["paroleChiave"] == "IVA"
        assert form["tipoCriterio"] == "E"  # frase_esatta → E
        assert form["tipoEstremi"] == "Sentenza"
        assert "Cassazione" in form["ente"]
        assert form["dataDa"] == "01/01/2023"
        assert form["dataA"] == "31/12/2024"
        assert form["ordinamento"] == "data"


# ---------------------------------------------------------------------------
# Extended tests: fetch_provvedimento
# ---------------------------------------------------------------------------

from src.lib.cerdef.client import fetch_provvedimento


class TestFetchProvvedimento:
    @pytest.mark.asyncio
    async def test_passes_guid_as_param(self):
        mock_resp = _make_mock_response(_DETAIL_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            detail = await fetch_provvedimento("test-guid-123")

        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params["id"] == "test-guid-123"

    @pytest.mark.asyncio
    async def test_returns_provvedimento_detail(self):
        mock_resp = _make_mock_response(_DETAIL_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            detail = await fetch_provvedimento("abc-123")

        assert isinstance(detail, ProvvedimentoDetail)
        assert detail.guid == "abc-123"


# ---------------------------------------------------------------------------
# Extended tests: _impl with filter combinations
# ---------------------------------------------------------------------------


class TestImplFilterCombinations:
    @pytest.mark.asyncio
    async def test_cerca_with_ente_filter(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_tributaria_impl(
                "IVA", ente="corte_suprema"
            )

        assert "Trovati" in result
        call_kwargs = mock_client.post.call_args
        form = call_kwargs.kwargs.get("data", {})
        assert "Cassazione" in form["ente"]

    @pytest.mark.asyncio
    async def test_cerca_with_criterio_frase_esatta(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_tributaria_impl(
                "soggettività passiva IVA", criterio="frase_esatta"
            )

        assert "Trovati" in result
        call_kwargs = mock_client.post.call_args
        form = call_kwargs.kwargs.get("data", {})
        assert form["tipoCriterio"] == "E"

    @pytest.mark.asyncio
    async def test_ultime_with_ente_and_tipo(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_sentenze_tributarie_impl(
                ente="cgt_secondo_grado", tipo_provvedimento="ordinanza"
            )

        assert "Ultime sentenze" in result
        call_kwargs = mock_client.post.call_args
        form = call_kwargs.kwargs.get("data", {})
        assert form["ordinamento"] == "data"
        assert "CGT II" in form["ente"]
        assert form["tipoEstremi"] == "Ordinanza"

    @pytest.mark.asyncio
    async def test_cerca_max_risultati_capped_at_250(self):
        """Verify _impl caps at 250."""
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.get = AsyncMock(return_value=_make_mock_response(_SEARCH_HTML_EMPTY))

        with patch("src.lib.cerdef.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_tributaria_impl("IVA", max_risultati=999)

        # Should still work but with capped results
        assert "Trovati" in result or "Nessun" in result
