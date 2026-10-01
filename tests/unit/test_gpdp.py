"""Unit tests for GPDP (Garante Privacy) scraper.

Tests are written against mocked httpx responses — no real network calls.
HTML fixtures mirror the actual Liferay portlet structure of garanteprivacy.it.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.gpdp.client import (
    TIPOLOGIE,
    DocNotAvailable,
    DocResult,
    _build_search_params,
    _parse_doc,
    _parse_results,
    format_full,
    format_result,
    normalize_date,
    resolve_tipologia,
    tipologie_provvedimenti,
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
        # The portal's dataInizio/dataFine are <input type="date">: only AAAA-MM-GG is read,
        # GG/MM/AAAA (the format the tools document) answers "Nessun risultato trovato".
        params = _build_search_params(query="", data_da="01/01/2023", data_a="31/12/2023")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_dataInizio"] == "2023-01-01"
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_dataFine"] == "2023-12-31"

    def test_date_filters_iso_pass_through(self):
        params = _build_search_params(query="", data_da="2021-06-01", data_a="2021-06-30")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_dataInizio"] == "2021-06-01"
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_dataFine"] == "2021-06-30"

    def test_empty_dates_stay_empty(self):
        params = _build_search_params(query="")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_dataInizio"] == ""
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_dataFine"] == ""

    def test_invalid_date_is_an_error_not_an_empty_search(self):
        with pytest.raises(ValueError, match="data_da"):
            _build_search_params(query="", data_da="01-06-2021")

    def test_order_is_desc_by_default(self):
        params = _build_search_params(query="")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_ordinamentoPer"] == "DESC"

    def test_mvcRenderCommandName(self):
        params = _build_search_params(query="test")
        assert params["_g_gpdp5_search_GGpdp5SearchPortlet_mvcRenderCommandName"] == "/renderSearch"


# ---------------------------------------------------------------------------
# Tests: normalize_date / resolve_tipologia
# ---------------------------------------------------------------------------

class TestNormalizeDate:
    def test_gg_mm_aaaa_to_iso(self):
        assert normalize_date("01/06/2021") == "2021-06-01"
        assert normalize_date("30/06/2021") == "2021-06-30"

    def test_iso_unchanged(self):
        assert normalize_date("2023-03-30") == "2023-03-30"

    def test_empty(self):
        assert normalize_date("") == ""
        assert normalize_date("  ") == ""

    @pytest.mark.parametrize("bad", ["1/6/2021", "2021/06/01", "01-06-2021", "giugno 2021", "2021-6-1"])
    def test_other_formats_are_errors(self, bad):
        with pytest.raises(ValueError, match="non valida"):
            normalize_date(bad, "data_da")

    def test_nonexistent_day(self):
        # 31 June does not exist: an explicit error, not a silent empty search
        with pytest.raises(ValueError, match="giorno inesistente"):
            normalize_date("31/06/2021", "data_a")
        with pytest.raises(ValueError, match="giorno inesistente"):
            normalize_date("2021-02-29", "data_a")  # 2021 is not a leap year

    def test_leap_day(self):
        assert normalize_date("29/02/2024") == "2024-02-29"


class TestResolveTipologia:
    # Node ids read from the portal's jsTreeTipologia on 2026-09-29
    # (https://www.garanteprivacy.it/web/guest/home/ricerca): "Provvedimenti" = 10533,
    # "Linee guida" = 10516, "Ordinanza ingiunzione o revoca" = 10526,
    # "Parere del Garante" = 10527, "Prescrizioni del Garante" = 10529.

    def test_empty_means_no_filter(self):
        assert resolve_tipologia("") == []

    def test_linee_guida(self):
        assert resolve_tipologia("linee guida") == ["10516"]

    def test_ordinanza_alias(self):
        assert resolve_tipologia("ordinanza") == ["10526"]
        assert resolve_tipologia("Ordinanza ingiunzione o revoca") == ["10526"]

    def test_parere(self):
        assert resolve_tipologia("parere") == ["10527"]

    def test_prescrizioni_matches_both_nodes(self):
        # "Prescrizioni del Garante" (10529) and "Prescrizioni e divieto del Garante" (10530)
        assert resolve_tipologia("prescrizioni") == ["10529", "10530"]
        assert resolve_tipologia("Prescrizioni del Garante") == ["10529"]

    def test_provvedimento_is_the_whole_family(self):
        # The portal does NOT include the children of a node: "Provvedimenti" (10533) alone
        # returns only the cards classified directly as such, so the 23 child nodes (and the
        # two grandchildren under "Autorizzazione trasferimento dati estero") are sent too.
        ids = resolve_tipologia("provvedimento")
        assert ids[0] == "10533"
        figli = [i for i, _n, parent in TIPOLOGIE if parent == "10533"]
        assert len(figli) == 23
        assert set(figli) <= set(ids)
        assert {"2034211", "2024563"} <= set(ids)  # Bcr, Autorizzazione ... Paesi terzi
        assert len(ids) == len(set(ids)) == 1 + 23 + 2
        assert resolve_tipologia("Provvedimenti") == ids
        for foglia in ("10526", "10527", "10529", "10516"):
            assert foglia in ids

    def test_unknown_is_an_explicit_error(self):
        with pytest.raises(ValueError, match="tipologia non riconosciuta"):
            resolve_tipologia("pippo")

    def test_error_lists_valid_values(self):
        with pytest.raises(ValueError) as exc:
            resolve_tipologia("pippo")
        for nome in ("Linee guida", "Parere del Garante", "Prescrizioni del Garante"):
            assert nome in str(exc.value)

    def test_leaves_under_provvedimenti_helper(self):
        nomi = tipologie_provvedimenti()
        assert "Ordinanza ingiunzione o revoca" in nomi
        assert "Prescrizioni del Garante" in nomi
        assert "Provvedimenti" not in nomi


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

    def test_unavailable_page_is_not_a_document(self):
        # DocWeb 10000069 answers 200 with only the portal's own message (no heading)
        html = ("<html><body><div>Il contenuto o il file richiesto non è disponibile</div>"
                "</body></html>")
        with pytest.raises(DocNotAvailable) as exc:
            _parse_doc(html, 10000069)
        assert exc.value.docweb_id == 10000069

    def test_message_inside_a_real_document_is_kept(self):
        html = ("<html><body><h1>Provvedimento del 1 gennaio 2026 [1]</h1>"
                "<p>Il contenuto o il file richiesto non è disponibile</p></body></html>")
        title, text = _parse_doc(html, 1)
        assert title == "Provvedimento del 1 gennaio 2026"
        assert "non è disponibile" in text

    def test_toolbar_lines_are_stripped(self):
        # Toolbar block copied from the print page of DocWeb 9677876
        toolbar = ["Ascolta", "Menù azioni", "Stampa", "e-mail", "facebook", "linkedin",
                   "twitter", "Ascolta", "Stampa", "Condivisione", "e-mail", "facebook",
                   "linkedin", "twitter"]
        html = ("<html><body><h1>Linee guida cookie [9677876]</h1>"
                + "".join(f"<p>{x}</p>" for x in toolbar)
                + "<p>NELLA riunione odierna</p></body></html>")
        _, text = _parse_doc(html, 9677876)
        assert text.splitlines() == ["Linee guida cookie [9677876]", "NELLA riunione odierna"]

    def test_toolbar_word_in_the_body_is_kept(self):
        # only the top of the page is cleaned: a later line "Stampa" belongs to the document
        corpo = "".join(f"<p>riga {i}</p>" for i in range(30))
        html = f"<html><body><h1>T</h1>{corpo}<p>Stampa</p></body></html>"
        _, text = _parse_doc(html, 1)
        assert text.splitlines()[-1] == "Stampa"

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

    def test_link_is_absolute(self):
        # A relative /web/guest/... link does not open outside the portal
        doc = DocResult(docweb_id=9677876, title="T", date="", tipologia="", argomenti=[])
        assert ("(https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/"
                "docweb/9677876)") in format_result(doc)

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

    def test_link_is_absolute(self):
        result = format_full("T", "testo", 9677876)
        assert ("[9677876](https://www.garanteprivacy.it/web/guest/home/docweb/-/"
                "docweb-display/docweb/9677876)") in result

    def test_truncation_note(self):
        long_text = "a" * 7000
        result = format_full("T", long_text, 1)
        assert "Testo troncato" in result

    def test_no_truncation_note_for_short_text(self):
        result = format_full("T", "breve testo", 1)
        assert "troncato" not in result

    def test_truncation_note_carries_resume_position(self):
        result = format_full("T", "a" * 7000, 1)
        assert result.endswith(
            "*[Testo troncato a 6000 caratteri su 7000 totali: "
            "per leggere il seguito ripetere la chiamata con da_carattere=6001]*"
        )

    def test_da_carattere_starts_at_the_first_omitted_character(self):
        text = "".join(f"[{i:05d}]" for i in range(2000))[:14000]
        first = format_full("T", text, 1)
        assert text[:6000] in first and text[:6001] not in first
        second = format_full("T", text, 1, da_carattere=6001)
        assert second.startswith("# T\n**DocWeb**: [1](")
        assert text[6000:12000] in second and text[6000:12001] not in second
        assert text[5994:6000] not in second
        assert "*[Caratteri 6001-12000 su 14000 totali: per leggere il seguito " \
            "ripetere la chiamata con da_carattere=12001]*" in second

    def test_last_window_says_end_of_text(self):
        text = "b" * 14000
        last = format_full("T", text, 1, da_carattere=12001)
        assert last.endswith("*[Caratteri 12001-14000 su 14000 totali: fine del testo]*")

    def test_start_beyond_the_end_says_so(self):
        result = format_full("T", "breve", 1, da_carattere=50)
        assert "oltre la fine del testo (5 caratteri)" in result


# ---------------------------------------------------------------------------
# Tests: _impl functions (mocked httpx)
# ---------------------------------------------------------------------------

def _make_mock_response(html: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


_PFX = "_g_gpdp5_search_GGpdp5SearchPortlet_"


def _mock_client(html: str) -> AsyncMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = AsyncMock(return_value=_make_mock_response(html))
    return client


def _sent_params(client: AsyncMock) -> dict:
    """Query string of the first GET the client sent to the portal."""
    return client.get.call_args_list[0].kwargs["params"]


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
    async def test_tipologia_is_sent_to_the_portal_not_filtered_locally(self):
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_provvedimenti_garante_impl("cookie", tipologia="parere")

        # The portal filters by node id (10527 = "Parere del Garante"); the client keeps every
        # card the portal returns: the old local substring filter compared the typed word with
        # the leaf label and dropped real provvedimenti ("provvedimento" is no leaf label).
        assert _sent_params(mock_client)[_PFX + "idsTipologia"] == "10527"
        assert "Parere" in result
        assert "Rossi" in result

    @pytest.mark.asyncio
    async def test_provvedimento_sends_the_family_of_nodes(self):
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_provvedimenti_garante_impl("OpenAI ChatGPT", tipologia="provvedimento")

        ids = _sent_params(mock_client)[_PFX + "idsTipologia"].split(",")
        # "Provvedimenti" (10533) + its 23 children + 2 grandchildren; "Prescrizioni del
        # Garante" (10529) is the leaf of DocWeb 9870832 and 9874702 (OpenAI, 2023).
        assert ids[0] == "10533"
        assert "10529" in ids
        assert len(ids) == 26

    @pytest.mark.asyncio
    async def test_dates_gg_mm_aaaa_are_sent_as_iso(self):
        # plan case: linee guida cookie, 01/06/2021-30/06/2021 (DocWeb 9677876 of 10/06/2021)
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_provvedimenti_garante_impl(
                "linee guida cookie", data_da="01/06/2021", data_a="30/06/2021",
            )

        params = _sent_params(mock_client)
        assert params[_PFX + "dataInizio"] == "2021-06-01"
        assert params[_PFX + "dataFine"] == "2021-06-30"

    @pytest.mark.asyncio
    async def test_invalid_date_is_an_error_and_sends_nothing(self):
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_provvedimenti_garante_impl("x", data_da="2021/06/01")

        assert result.startswith("Errore:")
        assert "data_da" in result
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_tipologia_is_an_error_and_sends_nothing(self):
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_provvedimenti_garante_impl("x", tipologia="pippo")

        assert result.startswith("Errore:")
        assert "tipologia non riconosciuta" in result
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_tipologia_sends_no_node_filter(self):
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_provvedimenti_garante_impl("cookie")

        assert _sent_params(mock_client)[_PFX + "idsTipologia"] == ""

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

    @pytest.mark.asyncio
    async def test_unavailable_id_is_an_error_not_a_document(self):
        # DocWeb 10000069 answers 200 with only "Il contenuto o il file richiesto non è
        # disponibile": the tool returns an error, not "# Documento DocWeb 10000069" + link.
        html = ("<html><body><div>Il contenuto o il file richiesto non è disponibile</div>"
                "</body></html>")
        mock_client = _mock_client(html)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_provvedimento_garante_impl(10000069)

        assert result.startswith("Errore: DocWeb 10000069 non disponibile")
        assert "# Documento DocWeb" not in result
        assert "docweb-display" not in result

    @pytest.mark.asyncio
    async def test_full_text_link_is_absolute(self):
        mock_client = _mock_client(_DOC_PRINT_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_provvedimento_garante_impl(9677876)

        assert ("https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/"
                "docweb/9677876") in result

    @pytest.mark.asyncio
    async def test_da_carattere_threads_to_the_window(self):
        body = "x" * 3000 + "MARKER" + "y" * 6000
        html = f"<html><body><div class='doc'><p>{body}</p></div></body></html>"
        mock_client = _mock_client(html)
        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            first = await _leggi_provvedimento_garante_impl(1)
        assert "da_carattere=6001]*" in first
        mock_client = _mock_client(html)
        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            second = await _leggi_provvedimento_garante_impl(1, da_carattere=6001)
        assert "Caratteri 6001-" in second
        assert "MARKER" not in second

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [0, -3, "2", 1.5, True])
    async def test_invalid_da_carattere_errors_without_network(self, bad):
        with patch("src.lib.gpdp.client.httpx.AsyncClient") as client_cls:
            result = await _leggi_provvedimento_garante_impl(9677876, da_carattere=bad)
        assert result.startswith("Errore: da_carattere deve essere un intero")
        client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_mcp_tool_accepts_da_carattere(self):
        from src.tools.gpdp import leggi_provvedimento_garante
        fn = getattr(leggi_provvedimento_garante, "fn", leggi_provvedimento_garante)
        with patch("src.tools.gpdp._leggi_provvedimento_garante_impl",
                   new=AsyncMock(return_value="ok")) as impl:
            assert await fn(9677876, da_carattere=6001) == "ok"
        impl.assert_awaited_once_with(9677876, 6001)
        assert "da_carattere" in fn.__doc__

    def test_docstring_examples_are_labelled_correctly(self):
        # DocWeb 9870832 is the Provvedimento of 30/03/2023 (reg. n. 112, OpenAI/ChatGPT),
        # not "Linee guida AI 2023"; 10000069 does not exist on the portal.
        from src.tools.gpdp import leggi_provvedimento_garante
        doc = getattr(leggi_provvedimento_garante, "fn", leggi_provvedimento_garante).__doc__
        assert "9870832: Provvedimento 30 marzo 2023" in doc
        assert "Linee guida AI 2023" not in doc
        assert "10000069" not in doc
        assert "9874702" in doc


class TestUltimiProvvedimentiImpl:
    @pytest.mark.asyncio
    async def test_returns_latest(self):
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultimi_provvedimenti_garante_impl()

        # Without a filter the portal lists every kind of document (press reviews, news,
        # newsletters, provvedimenti): the heading says so and points to tipologia.
        assert "Ultimi documenti pubblicati dal Garante Privacy" in result
        assert 'tipologia="provvedimento"' in result
        assert "Rossi" in result
        assert _sent_params(mock_client)[_PFX + "idsTipologia"] == ""

    @pytest.mark.asyncio
    async def test_tipologia_is_sent_to_the_portal(self):
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultimi_provvedimenti_garante_impl(tipologia="ordinanza", max_risultati=5)

        # "Ordinanza ingiunzione o revoca" = node 10526 in the portal tree; the filter runs on
        # the whole archive server-side (the old local filter only saw the 15 latest cards,
        # mostly press reviews and news).
        params = _sent_params(mock_client)
        assert params[_PFX + "idsTipologia"] == "10526"
        assert "Ultimi provvedimenti del Garante Privacy** (tipologia: ordinanza)" in result
        assert "Rossi" in result

    @pytest.mark.asyncio
    async def test_provvedimento_sends_the_family_of_nodes(self):
        # plan case 2: tipologia "provvedimento" returned "Nessun provvedimento recente
        # trovato" although the portal has provvedimenti (e.g. DocWeb 10297334 of 06/08/2026,
        # "Ordinanza ingiunzione o revoca", child of "Provvedimenti" 10533).
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            await _ultimi_provvedimenti_garante_impl(tipologia="provvedimento", max_risultati=5)

        ids = _sent_params(mock_client)[_PFX + "idsTipologia"].split(",")
        assert ids[0] == "10533"
        assert "10526" in ids
        assert len(ids) == 26

    @pytest.mark.asyncio
    async def test_unknown_tipologia_is_an_error_and_sends_nothing(self):
        mock_client = _mock_client(_SEARCH_HTML)

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultimi_provvedimenti_garante_impl(tipologia="pippo")

        assert result.startswith("Errore:")
        assert "tipologia non riconosciuta" in result
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_result_message(self):
        mock_client = _mock_client("<html><body></body></html>")

        with patch("src.lib.gpdp.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultimi_provvedimenti_garante_impl(tipologia="parere")

        assert "Nessun" in result
