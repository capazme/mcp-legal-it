"""Unit tests for GPDP (Garante Privacy) scraper.

Tests are written against mocked httpx responses — no real network calls.
HTML fixtures mirror the actual Liferay portlet structure of garanteprivacy.it.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.gpdp.client import (
    DocResult,
    _build_search_params,
    _parse_doc,
    _parse_results,
    format_full,
    format_result,
)

# Import _impl functions at module level to avoid metaclass conflict when patching httpx
from src.tools.gpdp import (
    _cerca_provvedimenti_garante_impl,
    _leggi_provvedimento_garante_impl,
    _ultimi_provvedimenti_garante_impl,
)

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

_SEARCH_HTML = """
<html><body>
<div class="blocco-risultati mt-5">

<div class="card-risultato">
  <div class="d-flex flex-wrap flex-md-nowrap justify-content-between align-items-md-center">
    <div class="label-risultato d-flex flex-row w-75">
      <div class="col-auto pl-0 pr-2">
        <p class="mb-1 ricercaArgomentiPar">Tipologia:</p>
      </div>
      <div class="col px-0">
        <p class="ml-sm-3">
          <span class="badge badge-pill">
            <a class="vertical-align-top font-weight-600 text-14p text-decoration-none"
               href="/home/ricerca/-/search/tipologia/Provvedimento">Provvedimento</a>
          </span>
        </p>
      </div>
    </div>
    <div class="data-risultato">
      <p class="">14/01/2026</p>
    </div>
  </div>
  <div class="d-flex">
    <div>
      <strong>
        <a class="titolo-risultato text-justify"
           href="/web/guest/home/docweb/-/docweb-display/docweb/10220271"
           title="Provvedimento di ingiunzione - Rossi Srl [10220271]">
          Provvedimento di ingiunzione - Rossi Srl [10220271]
        </a>
      </strong>
      <p class="estratto-risultato text-justify">
        Il Garante ha ordinato il pagamento di euro 50.000 per violazione GDPR.
      </p>
    </div>
  </div>
  <div class="d-flex flex-column flex-lg-row">
    <div class="row ml-0">
      <div class="col-sm-auto px-sm-0">
        <p class="mb-1 ricercaArgomentiPar">Argomenti:</p>
      </div>
      <div class="col px-sm-0">
        <p class="ml-sm-3">
          <span class="badge badge-pill">
            <a class="vertical-align-top" href="/argomento/1">GDPR</a>
          </span>
          <span class="badge badge-pill">
            <a class="vertical-align-top" href="/argomento/2">Sanzione</a>
          </span>
        </p>
      </div>
    </div>
  </div>
</div>

<div class="card-risultato">
  <div class="d-flex flex-wrap flex-md-nowrap justify-content-between align-items-md-center">
    <div class="label-risultato d-flex flex-row w-75">
      <div class="col-auto pl-0 pr-2">
        <p class="mb-1 ricercaArgomentiPar">Tipologia:</p>
      </div>
      <div class="col px-0">
        <p class="ml-sm-3">
          <span class="badge badge-pill">
            <a class="vertical-align-top font-weight-600 text-14p text-decoration-none"
               href="/home/ricerca/-/search/tipologia/Parere+del+Garante">Parere del Garante</a>
          </span>
        </p>
      </div>
    </div>
    <div class="data-risultato">
      <p class="">20/03/2025</p>
    </div>
  </div>
  <div class="d-flex">
    <div>
      <strong>
        <a class="titolo-risultato text-justify"
           href="/web/guest/home/docweb/-/docweb-display/docweb/9900001"
           title="Parere su schema di decreto sicurezza dati [9900001]">
          Parere su schema di decreto sicurezza dati [9900001]
        </a>
      </strong>
      <p class="estratto-risultato text-justify">
        Parere favorevole con osservazioni sulla sicurezza dei dati.
      </p>
    </div>
  </div>
  <div class="d-flex flex-column flex-lg-row">
    <div class="row ml-0">
      <div class="col-sm-auto px-sm-0">
        <p class="mb-1 ricercaArgomentiPar">Argomenti:</p>
      </div>
      <div class="col px-sm-0">
        <p class="ml-sm-3">
          <span class="badge badge-pill">
            <a class="vertical-align-top" href="/argomento/3">Sicurezza</a>
          </span>
        </p>
      </div>
    </div>
  </div>
</div>

</div>
</body></html>
"""

_SEARCH_HTML_EMPTY = "<html><body><div class='blocco-risultati mt-5'></div></body></html>"

_DOC_PRINT_HTML = """
<html><body>
<script>print();</script>
<nav>menu di navigazione</nav>
<h1>Linee guida sull'uso dei cookie - Versione 2021</h1>
<p>Registro dei Provvedimenti n. 231 del 10 giugno 2021</p>
<div class="docweb-corpo">
Il Garante per la protezione dei dati personali, nella riunione del 10 giugno 2021,
ha adottato le seguenti linee guida in materia di cookie e altri strumenti di tracciamento.

PREMESSA
Le presenti linee guida sostituiscono il provvedimento del 2014 e tengono conto
delle indicazioni delle linee guida del Comitato europeo.
</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Tests: _build_search_params
# ---------------------------------------------------------------------------

class TestBuildSearchParams:
    def test_basic_query(self):
        params = _build_search_params(query="cookie consenso")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_text"] == "cookie consenso"
        assert params["p_p_id"] == "g_gpdp5_search_GGpdp5SearchPortlet"
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_cur"] == "1"

    def test_sort_and_page(self):
        params = _build_search_params(query="test", page=3, sort_by="rilevanza")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_cur"] == "3"
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_ordinamentoTipo"] == "rilevanza"

    def test_date_filters(self):
        params = _build_search_params(query="", data_da="01/01/2023", data_a="31/12/2023")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_dataInizio"] == "01/01/2023"
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_dataFine"] == "31/12/2023"

    def test_order_is_desc_by_default(self):
        params = _build_search_params(query="")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_ordinamentoPer"] == "DESC"

    def test_mvcRenderCommandName(self):
        params = _build_search_params(query="test")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_mvcRenderCommandName"] == "/renderSearch"


# ---------------------------------------------------------------------------
# Tests: _parse_results
# ---------------------------------------------------------------------------

class TestParseResults:
    def test_parses_two_results(self):
        results = _parse_results(_SEARCH_HTML)
        assert len(results) == 2

    def test_first_result_fields(self):
        results = _parse_results(_SEARCH_HTML)
        doc = results[0]
        assert doc.docweb_id == 10220271
        assert "Rossi" in doc.title
        assert doc.date == "14/01/2026"
        assert doc.tipologia == "Provvedimento"
        assert "GDPR" in doc.argomenti
        assert "Sanzione" in doc.argomenti

    def test_second_result_fields(self):
        results = _parse_results(_SEARCH_HTML)
        doc = results[1]
        assert doc.docweb_id == 9900001
        assert doc.tipologia == "Parere del Garante"
        assert "Sicurezza" in doc.argomenti

    def test_abstract_stripped_of_docweb_ref(self):
        results = _parse_results(_SEARCH_HTML)
        doc = results[0]
        assert "doc. web" not in doc.abstract
        assert "10220271" not in doc.abstract
        assert "50.000" in doc.abstract

    def test_empty_html_returns_empty_list(self):
        results = _parse_results(_SEARCH_HTML_EMPTY)
        assert results == []

    def test_malformed_missing_strong(self):
        html = "<html><body><div class='risultato-ricerca'><p>No strong here</p></div></body></html>"
        results = _parse_results(html)
        assert results == []


# ---------------------------------------------------------------------------
# Tests: _parse_doc
# ---------------------------------------------------------------------------

class TestParseDoc:
    def test_extracts_title(self):
        title, text = _parse_doc(_DOC_PRINT_HTML, 9677876)
        assert "Linee guida" in title
        assert "cookie" in title.lower()

    def test_removes_scripts_and_nav(self):
        _, text = _parse_doc(_DOC_PRINT_HTML, 9677876)
        assert "print()" not in text
        assert "menu di navigazione" not in text

    def test_body_text_contains_content(self):
        _, text = _parse_doc(_DOC_PRINT_HTML, 9677876)
        assert "Garante" in text
        assert "cookie" in text.lower()

    def test_fallback_title_when_no_h1(self):
        html = "<html><body><p>Solo testo</p></body></html>"
        title, _ = _parse_doc(html, 9999)
        assert "9999" in title

    def test_multiple_newlines_collapsed(self):
        html = "<html><body><h1>T</h1><p>a</p><p></p><p></p><p>b</p></body></html>"
        _, text = _parse_doc(html, 1)
        assert "\n\n\n" not in text


# ---------------------------------------------------------------------------
# Tests: format_result
# ---------------------------------------------------------------------------

class TestFormatResult:
    def test_contains_title(self):
        doc = DocResult(
            docweb_id=12345,
            title="Provvedimento contro Acme Srl",
            date="01/06/2024",
            tipologia="Ordinanza ingiunzione",
            argomenti=["GDPR", "Sanzione"],
            abstract="Sanzione di euro 100.000 per violazione art. 5 GDPR.",
        )
        text = format_result(doc)
        assert "Provvedimento contro Acme Srl" in text
        assert "12345" in text
        assert "01/06/2024" in text
        assert "Ordinanza ingiunzione" in text
        assert "GDPR" in text
        assert "100.000" in text

    def test_url_in_output(self):
        doc = DocResult(docweb_id=9677876, title="T", date="", tipologia="", argomenti=[])
        text = format_result(doc)
        assert "9677876" in text
        assert "docweb" in text

    def test_long_abstract_truncated(self):
        doc = DocResult(
            docweb_id=1,
            title="T",
            date="",
            tipologia="",
            argomenti=[],
            abstract="x" * 500,
        )
        text = format_result(doc)
        assert "…" in text


# ---------------------------------------------------------------------------
# Tests: format_full
# ---------------------------------------------------------------------------

class TestFormatFull:
    def test_basic_formatting(self):
        result = format_full("Titolo Provvedimento", "Testo del documento.", 9677876)
        assert "# Titolo Provvedimento" in result
        assert "9677876" in result
        assert "Testo del documento." in result

    def test_truncation_note(self):
        long_text = "a" * 7000
        result = format_full("T", long_text, 1)
        assert "Testo troncato" in result

    def test_no_truncation_note_for_short_text(self):
        result = format_full("T", "breve testo", 1)
        assert "troncato" not in result


# ---------------------------------------------------------------------------
# Tests: _impl functions (mocked httpx)
# ---------------------------------------------------------------------------

def _make_mock_response(html: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


class TestCercaProvvedimentiImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_provvedimenti_garante_impl("cookie")

        assert "Trovati" in result
        assert "Rossi" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_resp = _make_mock_response(_SEARCH_HTML_EMPTY)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_provvedimenti_garante_impl("inesistente")

        assert "Nessun" in result

    @pytest.mark.asyncio
    async def test_tipologia_filter(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_provvedimenti_garante_impl("cookie", tipologia="parere")

        # Only the "Parere del Garante" should pass the filter
        assert "Parere" in result
        assert "Rossi" not in result

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_provvedimenti_garante_impl("test")

        assert "Errore" in result


class TestLeggiProvvedimentoImpl:
    @pytest.mark.asyncio
    async def test_returns_full_text(self):
        mock_resp = _make_mock_response(_DOC_PRINT_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_provvedimento_garante_impl(9677876)

        assert "Linee guida" in result
        assert "cookie" in result.lower()
        assert "9677876" in result

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        ))

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_provvedimento_garante_impl(9999999)

        assert "Errore" in result


class TestUltimiProvvedimentiImpl:
    @pytest.mark.asyncio
    async def test_returns_latest(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultimi_provvedimenti_garante_impl()

        assert "Ultimi provvedimenti" in result
        assert "Rossi" in result

    @pytest.mark.asyncio
    async def test_tipologia_filter(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultimi_provvedimenti_garante_impl(tipologia="ordinanza")

        # Neither result matches "ordinanza" so should return empty message
        assert "Nessun" in result
