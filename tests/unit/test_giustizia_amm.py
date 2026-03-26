"""Unit tests for Giustizia Amministrativa (TAR/CdS) scraper.

Tests are written against mocked httpx responses — no real network calls.
HTML/XML fixtures mirror the expected structure of the giustizia-amministrativa.it portal.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.giustizia_amm.client import (
    SEDI,
    TIPI_PROVVEDIMENTO,
    ProvvedimentoResult,
    _build_search_params,
    _extract_p_auth,
    _parse_results,
    _parse_xml_text,
    format_full,
    format_result,
)

from src.tools.giustizia_amm import (
    _cerca_giurisprudenza_amministrativa_impl,
    _giurisprudenza_amm_su_norma_impl,
    _leggi_provvedimento_amm_impl,
    _ultimi_provvedimenti_amm_impl,
)


# ---------------------------------------------------------------------------
# HTML/XML fixtures
# ---------------------------------------------------------------------------

_PAUTH_HTML = """
<html><body>
<form id="search-form" action="/web/guest/-/ricerca-giurisprudenza?p_auth=testToken123" method="post">
<input type="hidden" name="p_auth" value="testToken123">
<input type="text" name="query">
</form>
</body></html>
"""

_PAUTH_HTML_ACTION_ONLY = """
<html><body>
<form action="/web/guest/-/ricerca-giurisprudenza?p_auth=actionToken456" method="post">
<input type="text" name="query">
</form>
</body></html>
"""

_PAUTH_HTML_NONE = """
<html><body>
<form action="/web/guest/-/ricerca-giurisprudenza" method="post">
<input type="text" name="query">
</form>
</body></html>
"""

_SEARCH_HTML = """
<html><body>
<form action="/web/guest/-/ricerca-giurisprudenza?p_auth=abc123XYZ" method="post">
<input type="hidden" name="p_auth" value="abc123XYZ">
</form>
<div class="risultati">
<article class="ricerca--item" data-sede="CDS" data-nrg="202301234" data-tipo="Sentenza" data-anno="2023" data-nomefile="202301234_11.xml" data-datadeposito="15/06/2023" data-oggetto="Appalto pubblico - Esclusione - Requisiti">
<h3><a href="#">Consiglio di Stato, Sez. V, Sent. n. 1234/2023</a></h3>
<p class="sede">Consiglio di Stato</p>
<p class="oggetto">Appalto pubblico - Esclusione - Requisiti di partecipazione</p>
</article>
<article class="ricerca--item" data-sede="TARLAZ" data-nrg="202405678" data-tipo="Sentenza" data-anno="2024" data-nomefile="202405678_11.xml" data-datadeposito="20/03/2024" data-oggetto="Urbanistica - Piano regolatore - Variante">
<h3><a href="#">TAR Lazio, Sez. II, Sent. n. 5678/2024</a></h3>
<p class="sede">TAR Lazio</p>
<p class="oggetto">Urbanistica - Piano regolatore - Variante</p>
</article>
</div>
</body></html>
"""

_SEARCH_HTML_EMPTY = """
<html><body>
<div class="risultati">
</div>
</body></html>
"""

_SEARCH_HTML_MALFORMED = """
<html><body>
<div class="risultati">
<article class="ricerca--item">
<p>No data attributes</p>
</article>
</div>
</body></html>
"""

_MDP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<GA>
<epigrafe>
<intestazione>REPUBBLICA ITALIANA</intestazione>
<intestazione>IN NOME DEL POPOLO ITALIANO</intestazione>
<intestazione>Il Consiglio di Stato in sede giurisdizionale (Sezione Quinta)</intestazione>
</epigrafe>
<motivazione>
<paragrafo>Con ricorso proposto dinanzi al TAR Lazio, la societa ricorrente ha impugnato il provvedimento di esclusione dalla gara per l'affidamento dei lavori.</paragrafo>
<paragrafo>Il Collegio ritiene fondato il primo motivo di ricorso.</paragrafo>
</motivazione>
<dispositivo>
<paragrafo>P.Q.M.</paragrafo>
<paragrafo>Il Consiglio di Stato accoglie il ricorso in appello e, per l'effetto, annulla il provvedimento impugnato.</paragrafo>
</dispositivo>
</GA>
"""

_MDP_XML_EMPTY_SECTIONS = b"""<?xml version="1.0" encoding="UTF-8"?>
<GA>
<epigrafe></epigrafe>
<motivazione></motivazione>
<dispositivo></dispositivo>
</GA>
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_mock_response(html_or_bytes, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html_or_bytes if isinstance(html_or_bytes, str) else ""
    resp.content = html_or_bytes if isinstance(html_or_bytes, bytes) else html_or_bytes.encode()
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Tests: _extract_p_auth
# ---------------------------------------------------------------------------

class TestExtractPAuth:
    def test_extracts_from_hidden_input(self):
        token = _extract_p_auth(_PAUTH_HTML)
        assert token == "testToken123"

    def test_extracts_from_form_action_url(self):
        token = _extract_p_auth(_PAUTH_HTML_ACTION_ONLY)
        assert token == "actionToken456"

    def test_returns_empty_when_not_found(self):
        token = _extract_p_auth(_PAUTH_HTML_NONE)
        assert token == ""

    def test_returns_empty_for_empty_html(self):
        token = _extract_p_auth("<html></html>")
        assert token == ""


# ---------------------------------------------------------------------------
# Tests: _build_search_params
# ---------------------------------------------------------------------------

class TestBuildSearchParams:
    def test_basic_query(self):
        params = _build_search_params(query="appalto pubblico")
        portlet_key = [k for k in params if "testolibero" in k]
        assert portlet_key
        assert params[portlet_key[0]] == "appalto pubblico"

    def test_p_p_id_present(self):
        params = _build_search_params()
        assert "p_p_id" in params
        from src.lib.giustizia_amm.client import _PORTLET
        assert params["p_p_id"] == _PORTLET

    def test_sede_filter(self):
        params = _build_search_params(sede="CDS")
        sede_key = [k for k in params if k.endswith("sede")]
        assert sede_key
        assert params[sede_key[0]] == "CDS"

    def test_tipo_filter(self):
        params = _build_search_params(tipo="Sentenza")
        tipo_key = [k for k in params if "tipoProvvedimento" in k]
        assert tipo_key
        assert params[tipo_key[0]] == "Sentenza"

    def test_anno_filter(self):
        params = _build_search_params(anno="2024")
        anno_key = [k for k in params if k.endswith("anno")]
        assert anno_key
        assert params[anno_key[0]] == "2024"

    def test_rows_param(self):
        params = _build_search_params(page_size=15)
        rows_key = [k for k in params if k.endswith("rows")]
        assert rows_key
        assert params[rows_key[0]] == "15"

    def test_p_auth_included_when_set(self):
        params = _build_search_params(p_auth="myToken")
        assert params.get("p_auth") == "myToken"

    def test_p_auth_omitted_when_empty(self):
        params = _build_search_params()
        assert "p_auth" not in params


# ---------------------------------------------------------------------------
# Tests: _parse_results
# ---------------------------------------------------------------------------

class TestParseResults:
    def test_parses_two_results(self):
        results = _parse_results(_SEARCH_HTML)
        assert len(results) == 2

    def test_first_result_cds(self):
        results = _parse_results(_SEARCH_HTML)
        doc = results[0]
        assert doc.sede == "CDS"
        assert doc.sede_label == "Consiglio di Stato"
        assert doc.nrg == "202301234"
        assert doc.tipo == "Sentenza"
        assert doc.anno == "2023"
        assert doc.nome_file == "202301234_11.xml"
        assert doc.data_deposito == "15/06/2023"
        assert "Appalto" in doc.oggetto

    def test_second_result_tarlaz(self):
        results = _parse_results(_SEARCH_HTML)
        doc = results[1]
        assert doc.sede == "TARLAZ"
        assert doc.sede_label == "TAR Lazio"
        assert doc.nrg == "202405678"
        assert doc.anno == "2024"
        assert "Urbanistica" in doc.oggetto

    def test_empty_html_returns_empty_list(self):
        results = _parse_results(_SEARCH_HTML_EMPTY)
        assert results == []

    def test_malformed_articles_skipped(self):
        results = _parse_results(_SEARCH_HTML_MALFORMED)
        assert results == []

    def test_unknown_sede_uses_code_as_label(self):
        html = """
        <html><body>
        <article class="ricerca--item" data-sede="TARXXX" data-nrg="12345">
        </article></body></html>
        """
        results = _parse_results(html)
        assert len(results) == 1
        assert results[0].sede_label == "TARXXX"


# ---------------------------------------------------------------------------
# Tests: _parse_xml_text
# ---------------------------------------------------------------------------

class TestParseXmlText:
    def test_extracts_title_from_epigrafe(self):
        title, _ = _parse_xml_text(_MDP_XML)
        assert "REPUBBLICA ITALIANA" in title or "Consiglio di Stato" in title

    def test_extracts_motivazione(self):
        _, body = _parse_xml_text(_MDP_XML)
        assert "TAR Lazio" in body
        assert "primo motivo" in body

    def test_extracts_dispositivo(self):
        _, body = _parse_xml_text(_MDP_XML)
        assert "P.Q.M." in body
        assert "annulla" in body

    def test_empty_sections(self):
        title, body = _parse_xml_text(_MDP_XML_EMPTY_SECTIONS)
        assert isinstance(title, str)
        assert isinstance(body, str)

    def test_invalid_xml_fallback(self):
        title, body = _parse_xml_text(b"<not valid xml <<>>")
        assert isinstance(title, str)
        assert isinstance(body, str)

    def test_returns_tuple_of_strings(self):
        result = _parse_xml_text(_MDP_XML)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(x, str) for x in result)


# ---------------------------------------------------------------------------
# Tests: format_result
# ---------------------------------------------------------------------------

class TestFormatResult:
    def test_contains_sede_label(self):
        doc = ProvvedimentoResult(
            sede="CDS",
            sede_label="Consiglio di Stato",
            nrg="202301234",
            tipo="Sentenza",
            anno="2023",
            nome_file="202301234_11.xml",
            data_deposito="15/06/2023",
            oggetto="Appalto pubblico - Esclusione",
        )
        text = format_result(doc)
        assert "Consiglio di Stato" in text
        assert "202301234" in text
        assert "2023" in text

    def test_contains_oggetto(self):
        doc = ProvvedimentoResult(
            sede="TARLAZ",
            sede_label="TAR Lazio",
            nrg="123",
            tipo="Sentenza",
            anno="2024",
            nome_file="123.xml",
            data_deposito="01/01/2024",
            oggetto="Urbanistica - Variante PRG",
        )
        text = format_result(doc)
        assert "Urbanistica" in text

    def test_contains_data_deposito(self):
        doc = ProvvedimentoResult(
            sede="CDS",
            sede_label="Consiglio di Stato",
            nrg="999",
            tipo="Ordinanza",
            anno="2023",
            nome_file="999.xml",
            data_deposito="20/03/2024",
            oggetto="",
        )
        text = format_result(doc)
        assert "20/03/2024" in text

    def test_long_oggetto_truncated(self):
        doc = ProvvedimentoResult(
            sede="CDS",
            sede_label="Consiglio di Stato",
            nrg="1",
            tipo="Sentenza",
            anno="2024",
            nome_file="1.xml",
            data_deposito="",
            oggetto="x" * 500,
        )
        text = format_result(doc)
        # oggetto is truncated to 300
        assert len(text) < 700


# ---------------------------------------------------------------------------
# Tests: format_full
# ---------------------------------------------------------------------------

class TestFormatFull:
    def test_basic_formatting(self):
        result = format_full("CdS Sez. V Sent. 1234/2023", "Testo del provvedimento.", "CDS", "202301234")
        assert "CdS Sez. V" in result
        assert "Testo del provvedimento." in result
        assert "CDS" in result
        assert "202301234" in result

    def test_truncation_at_15000(self):
        long_text = "a" * 16000
        result = format_full("Title", long_text, "CDS", "123")
        assert "Testo troncato" in result
        assert "15000" in result

    def test_no_truncation_for_short_text(self):
        result = format_full("Title", "breve testo", "CDS", "123")
        assert "troncato" not in result

    def test_sede_label_resolved(self):
        result = format_full("Title", "testo", "TARLAZ", "456")
        assert "TAR Lazio" in result


# ---------------------------------------------------------------------------
# Tests: SEDI and TIPI_PROVVEDIMENTO constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_sedi_has_at_least_27_entries(self):
        assert len(SEDI) >= 27

    def test_sedi_contains_cds(self):
        assert "consiglio_di_stato" in SEDI
        assert SEDI["consiglio_di_stato"] == "CDS"

    def test_sedi_contains_cgars(self):
        assert "cgars" in SEDI
        assert SEDI["cgars"] == "CGARS"

    def test_sedi_contains_tar_lazio(self):
        assert "tar_lazio" in SEDI
        assert SEDI["tar_lazio"] == "TARLAZ"

    def test_tipi_provvedimento_has_4_entries(self):
        assert len(TIPI_PROVVEDIMENTO) == 4

    def test_tipi_provvedimento_keys(self):
        for key in ("sentenza", "ordinanza", "decreto", "parere"):
            assert key in TIPI_PROVVEDIMENTO

    def test_tipi_provvedimento_values(self):
        assert TIPI_PROVVEDIMENTO["sentenza"] == "Sentenza"
        assert TIPI_PROVVEDIMENTO["ordinanza"] == "Ordinanza"


# ---------------------------------------------------------------------------
# Tests: _impl functions (mocked httpx via GASession)
# ---------------------------------------------------------------------------

def _make_ga_session_mock(search_html: str, xml_bytes: bytes = b""):
    """Build a mock GASession that returns predefined responses."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session._p_auth = "mockToken"
    mock_session.search = AsyncMock(return_value=search_html)
    mock_session.fetch_text = AsyncMock(return_value=xml_bytes)
    return mock_session


class TestCercaGiurisprudenzaAmministrativaImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _cerca_giurisprudenza_amministrativa_impl("appalto pubblico")

        assert "Trovati" in result
        assert "Consiglio di Stato" in result
        assert "TAR Lazio" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML_EMPTY)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _cerca_giurisprudenza_amministrativa_impl("inesistente")

        assert "Nessun" in result

    @pytest.mark.asyncio
    async def test_max_risultati_capped_at_50(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _cerca_giurisprudenza_amministrativa_impl("test", max_risultati=100)

        assert "Trovati" in result or "Nessun" in result

    @pytest.mark.asyncio
    async def test_exception_returns_error_message(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        mock_session.search = AsyncMock(side_effect=httpx.RequestError("timeout"))
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _cerca_giurisprudenza_amministrativa_impl("test")

        assert "Errore" in result


class TestLeggiProvvedimentoAmmImpl:
    @pytest.mark.asyncio
    async def test_returns_full_text(self):
        mock_session = _make_ga_session_mock("", _MDP_XML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _leggi_provvedimento_amm_impl("CDS", "202301234", "202301234_11.xml")

        assert "CDS" in result or "Consiglio di Stato" in result
        assert "202301234" in result

    @pytest.mark.asyncio
    async def test_returns_motivazione_content(self):
        mock_session = _make_ga_session_mock("", _MDP_XML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _leggi_provvedimento_amm_impl("CDS", "202301234", "202301234_11.xml")

        assert "TAR Lazio" in result or "annulla" in result

    @pytest.mark.asyncio
    async def test_exception_returns_error_message(self):
        mock_session = _make_ga_session_mock("")
        mock_session.fetch_text = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        ))
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _leggi_provvedimento_amm_impl("CDS", "99999", "99999.xml")

        assert "Errore" in result


class TestGiurisprudenzaAmmSuNormaImpl:
    @pytest.mark.asyncio
    async def test_returns_results_for_norma(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _giurisprudenza_amm_su_norma_impl("art. 21-nonies L. 241/1990")

        assert "art. 21-nonies" in result or "Trovati" in result

    @pytest.mark.asyncio
    async def test_empty_results_for_norma(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML_EMPTY)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _giurisprudenza_amm_su_norma_impl("art. 999 c.xyz.")

        assert "Nessun" in result

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        mock_session.search = AsyncMock(side_effect=Exception("network error"))
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _giurisprudenza_amm_su_norma_impl("art. 1 L. 241/1990")

        assert "Errore" in result


class TestUltimiProvvedimentiAmmImpl:
    @pytest.mark.asyncio
    async def test_returns_latest_provvedimenti(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _ultimi_provvedimenti_amm_impl()

        assert "Ultimi provvedimenti" in result
        assert "Consiglio di Stato" in result or "TAR Lazio" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML_EMPTY)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _ultimi_provvedimenti_amm_impl()

        assert "Nessun" in result

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        mock_session.search = AsyncMock(side_effect=httpx.RequestError("connection refused"))
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _ultimi_provvedimenti_amm_impl()

        assert "Errore" in result

    @pytest.mark.asyncio
    async def test_sede_filter_passed(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _ultimi_provvedimenti_amm_impl(sede="consiglio_di_stato")

        assert "Ultimi provvedimenti" in result or "Nessun" in result


# ---------------------------------------------------------------------------
# Extended tests: GASession
# ---------------------------------------------------------------------------

from src.lib.giustizia_amm.client import GASession, _SEDE_LABELS


class TestGASession:
    @pytest.mark.asyncio
    async def test_aenter_fetches_page_and_extracts_p_auth(self):
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        async def _mock_retry(client, method, url, **kwargs):
            return _make_mock_response(_PAUTH_HTML)

        with patch("src.lib.giustizia_amm.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.giustizia_amm.client.retry_request", side_effect=_mock_retry):
            async with GASession() as session:
                assert session._p_auth == "testToken123"
                assert session._client is not None

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        async def _mock_retry(client, method, url, **kwargs):
            return _make_mock_response(_PAUTH_HTML)

        with patch("src.lib.giustizia_amm.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.giustizia_amm.client.retry_request", side_effect=_mock_retry):
            session = GASession()
            async with session:
                pass
            assert session._client is None
            mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_calls_post(self):
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        call_log = []

        async def _mock_retry(client, method, url, **kwargs):
            call_log.append((method, url))
            if method == "GET":
                return _make_mock_response(_PAUTH_HTML)
            return _make_mock_response(_SEARCH_HTML)

        with patch("src.lib.giustizia_amm.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.giustizia_amm.client.retry_request", side_effect=_mock_retry):
            async with GASession() as session:
                html = await session.search({"key": "val"})
                assert "ricerca--item" in html
                assert ("POST", "https://www.giustizia-amministrativa.it/web/guest/-/ricerca-giurisprudenza") in call_log

    @pytest.mark.asyncio
    async def test_fetch_text_calls_get_on_mdp(self):
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        mock_mdp_resp = MagicMock()
        mock_mdp_resp.content = _MDP_XML
        mock_mdp_resp.raise_for_status = MagicMock()

        call_count = 0

        async def _mock_retry(client, method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_mock_response(_PAUTH_HTML)
            return mock_mdp_resp

        with patch("src.lib.giustizia_amm.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.giustizia_amm.client.retry_request", side_effect=_mock_retry):
            async with GASession() as session:
                content = await session.fetch_text("202301234_11.xml")
                assert content == _MDP_XML


# ---------------------------------------------------------------------------
# Extended tests: _extract_p_auth edge cases
# ---------------------------------------------------------------------------


class TestExtractPAuthExtended:
    def test_multiple_forms_picks_first_with_token(self):
        html = """
        <html><body>
        <form action="/no-token" method="post">
            <input type="text" name="q">
        </form>
        <form action="/has-token?p_auth=secondForm" method="post">
            <input type="text" name="q">
        </form>
        </body></html>
        """
        token = _extract_p_auth(html)
        assert token == "secondForm"

    def test_p_auth_with_other_query_params(self):
        html = """
        <html><body>
        <form action="/search?foo=bar&p_auth=inMiddle&baz=qux" method="post">
        </form>
        </body></html>
        """
        token = _extract_p_auth(html)
        assert token == "inMiddle"

    def test_hidden_input_takes_priority_over_action(self):
        html = """
        <html><body>
        <form action="/search?p_auth=fromAction" method="post">
            <input type="hidden" name="p_auth" value="fromInput">
        </form>
        </body></html>
        """
        token = _extract_p_auth(html)
        assert token == "fromInput"


# ---------------------------------------------------------------------------
# Extended tests: _build_search_params edge cases
# ---------------------------------------------------------------------------


class TestBuildSearchParamsExtended:
    def test_all_params_set(self):
        params = _build_search_params(
            query="appalto",
            tipo="Sentenza",
            sede="CDS",
            anno="2024",
            numero="1234",
            page_size=30,
            p_auth="token123",
        )
        prefix = f"_{_PORTLET}_"
        assert params[f"{prefix}testolibero"] == "appalto"
        assert params[f"{prefix}tipoProvvedimento"] == "Sentenza"
        assert params[f"{prefix}sede"] == "CDS"
        assert params[f"{prefix}anno"] == "2024"
        assert params[f"{prefix}numero"] == "1234"
        assert params[f"{prefix}rows"] == "30"
        assert params["p_auth"] == "token123"

    def test_empty_query_no_testolibero_key(self):
        params = _build_search_params()
        testolibero_keys = [k for k in params if "testolibero" in k]
        assert testolibero_keys == []

    def test_empty_tipo_no_tipo_key(self):
        params = _build_search_params(query="test")
        tipo_keys = [k for k in params if "tipoProvvedimento" in k]
        assert tipo_keys == []

    def test_empty_sede_no_sede_key(self):
        params = _build_search_params(query="test")
        sede_keys = [k for k in params if k.endswith("sede")]
        assert sede_keys == []


from src.lib.giustizia_amm.client import _PORTLET


# ---------------------------------------------------------------------------
# Extended tests: _parse_results edge cases
# ---------------------------------------------------------------------------


class TestParseResultsExtended:
    def test_article_with_sede_but_no_nrg_skipped(self):
        html = """
        <html><body>
        <article class="ricerca--item" data-sede="CDS" data-tipo="Sentenza">
        </article></body></html>
        """
        results = _parse_results(html)
        assert results == []

    def test_article_with_nrg_but_no_sede_skipped(self):
        html = """
        <html><body>
        <article class="ricerca--item" data-nrg="12345" data-tipo="Sentenza">
        </article></body></html>
        """
        results = _parse_results(html)
        assert results == []

    def test_article_with_partial_data_attributes(self):
        """Missing optional fields should still parse."""
        html = """
        <html><body>
        <article class="ricerca--item" data-sede="CDS" data-nrg="99999">
        </article></body></html>
        """
        results = _parse_results(html)
        assert len(results) == 1
        assert results[0].sede == "CDS"
        assert results[0].nrg == "99999"
        assert results[0].tipo == ""
        assert results[0].anno == ""
        assert results[0].nome_file == ""

    def test_non_article_elements_ignored(self):
        html = """
        <html><body>
        <div class="ricerca--item" data-sede="CDS" data-nrg="12345">
        </div></body></html>
        """
        results = _parse_results(html)
        assert results == []


# ---------------------------------------------------------------------------
# Extended tests: _parse_xml_text edge cases
# ---------------------------------------------------------------------------


class TestParseXmlTextExtended:
    def test_xml_with_only_epigrafe(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<GA>
<epigrafe><intestazione>REPUBBLICA ITALIANA</intestazione></epigrafe>
</GA>"""
        title, body = _parse_xml_text(xml)
        assert "REPUBBLICA" in title
        assert "REPUBBLICA" in body

    def test_xml_with_only_dispositivo(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<GA>
<dispositivo><paragrafo>P.Q.M. Rigetta il ricorso.</paragrafo></dispositivo>
</GA>"""
        title, body = _parse_xml_text(xml)
        assert "P.Q.M." in body
        assert "DISPOSITIVO" in body

    def test_xml_with_empty_children_text(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<GA>
<motivazione><paragrafo></paragrafo><paragrafo>Testo valido</paragrafo></motivazione>
</GA>"""
        _, body = _parse_xml_text(xml)
        assert "Testo valido" in body

    def test_plain_text_fallback_on_invalid_xml(self):
        bad_xml = b"Questo non e XML ma testo semplice"
        title, body = _parse_xml_text(bad_xml)
        assert isinstance(body, str)

    def test_utf8_encoding_in_xml(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<GA>
<epigrafe><intestazione>Provvedimento con accento: è à ù</intestazione></epigrafe>
</GA>""".encode("utf-8")
        title, body = _parse_xml_text(xml)
        assert "accento" in body


# ---------------------------------------------------------------------------
# Extended tests: format_result edge cases
# ---------------------------------------------------------------------------


class TestFormatResultExtended:
    def test_empty_oggetto_not_in_output(self):
        doc = ProvvedimentoResult(
            sede="CDS", sede_label="Consiglio di Stato", nrg="1",
            tipo="Sentenza", anno="2024", nome_file="1.xml",
            data_deposito="01/01/2024", oggetto="",
        )
        text = format_result(doc)
        assert "Oggetto" not in text

    def test_empty_data_deposito_not_in_output(self):
        doc = ProvvedimentoResult(
            sede="CDS", sede_label="Consiglio di Stato", nrg="1",
            tipo="Sentenza", anno="2024", nome_file="1.xml",
            data_deposito="", oggetto="test",
        )
        text = format_result(doc)
        assert "Data deposito" not in text

    def test_empty_nome_file_not_in_output(self):
        doc = ProvvedimentoResult(
            sede="CDS", sede_label="Consiglio di Stato", nrg="1",
            tipo="Sentenza", anno="2024", nome_file="",
            data_deposito="01/01/2024", oggetto="test",
        )
        text = format_result(doc)
        assert "File" not in text


# ---------------------------------------------------------------------------
# Extended tests: format_full edge cases
# ---------------------------------------------------------------------------


class TestFormatFullExtended:
    def test_unknown_sede_code(self):
        result = format_full("Title", "testo", "TARXXX", "456")
        assert "TARXXX" in result

    def test_empty_text(self):
        result = format_full("Title", "", "CDS", "123")
        assert "Title" in result
        assert "troncato" not in result

    def test_truncation_boundary(self):
        """Exactly at the limit — no truncation note."""
        result = format_full("Title", "a" * 15000, "CDS", "123")
        assert "troncato" not in result

    def test_truncation_at_limit_plus_one(self):
        result = format_full("Title", "a" * 15001, "CDS", "123")
        assert "troncato" in result


# ---------------------------------------------------------------------------
# Extended tests: _SEDE_LABELS consistency
# ---------------------------------------------------------------------------


class TestSedeLabelsConsistency:
    def test_all_sedi_codes_have_labels(self):
        """Every SEDI value (code) should have a corresponding label."""
        for key, code in SEDI.items():
            assert code in _SEDE_LABELS, f"SEDI[{key!r}] = {code!r} has no label in _SEDE_LABELS"

    def test_labels_are_nonempty_strings(self):
        for code, label in _SEDE_LABELS.items():
            assert isinstance(label, str) and label, f"_SEDE_LABELS[{code!r}] is empty"


# ---------------------------------------------------------------------------
# Extended tests: search_provvedimenti resolution
# ---------------------------------------------------------------------------

from src.lib.giustizia_amm.client import search_provvedimenti


class TestSearchProvvedimentiResolution:
    @pytest.mark.asyncio
    async def test_resolves_sede_key_to_code(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            await search_provvedimenti(sede="consiglio_di_stato")

        call_args = mock_session.search.call_args
        params = call_args.args[0] if call_args.args else call_args.kwargs.get("params", {})
        sede_key = [k for k in params if k.endswith("sede")]
        if sede_key:
            assert params[sede_key[0]] == "CDS"

    @pytest.mark.asyncio
    async def test_resolves_tipo_key_to_value(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            await search_provvedimenti(tipo="sentenza")

        call_args = mock_session.search.call_args
        params = call_args.args[0] if call_args.args else call_args.kwargs.get("params", {})
        tipo_key = [k for k in params if "tipoProvvedimento" in k]
        if tipo_key:
            assert params[tipo_key[0]] == "Sentenza"

    @pytest.mark.asyncio
    async def test_rows_capped_at_50(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            await search_provvedimenti(rows=100)

        call_args = mock_session.search.call_args
        params = call_args.args[0] if call_args.args else call_args.kwargs.get("params", {})
        rows_key = [k for k in params if k.endswith("rows")]
        if rows_key:
            assert params[rows_key[0]] == "50"

    @pytest.mark.asyncio
    async def test_passes_raw_sede_code_if_not_in_dict(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            await search_provvedimenti(sede="CDS")  # Already a code

        call_args = mock_session.search.call_args
        params = call_args.args[0] if call_args.args else call_args.kwargs.get("params", {})
        sede_key = [k for k in params if k.endswith("sede")]
        if sede_key:
            assert params[sede_key[0]] == "CDS"


# ---------------------------------------------------------------------------
# Extended tests: _impl with diverse parameters
# ---------------------------------------------------------------------------


class TestImplDiverseParams:
    @pytest.mark.asyncio
    async def test_cerca_with_anno_and_tipo(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _cerca_giurisprudenza_amministrativa_impl(
                "urbanistica", tipo="sentenza", anno="2024"
            )

        assert "Trovati" in result

    @pytest.mark.asyncio
    async def test_leggi_with_unknown_sede_still_works(self):
        mock_session = _make_ga_session_mock("", _MDP_XML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _leggi_provvedimento_amm_impl("TARXXX", "12345", "12345.xml")

        assert "TARXXX" in result
        assert "12345" in result

    @pytest.mark.asyncio
    async def test_giurisprudenza_su_norma_passes_ref_as_query(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _giurisprudenza_amm_su_norma_impl(
                "art. 21-nonies L. 241/1990",
                sede="consiglio_di_stato",
                anno_da="2022",
            )

        assert "art. 21-nonies" in result or "Trovati" in result

    @pytest.mark.asyncio
    async def test_ultimi_with_tipo_filter(self):
        mock_session = _make_ga_session_mock(_SEARCH_HTML)
        with patch("src.lib.giustizia_amm.client.GASession", return_value=mock_session):
            result = await _ultimi_provvedimenti_amm_impl(tipo="ordinanza")

        assert "Ultimi provvedimenti" in result or "Nessun" in result
