"""Unit tests for Giustizia Amministrativa (TAR/CdS) scraper.

Tests are written against mocked httpx responses — no real network calls, except
the @pytest.mark.live tests at the bottom (skipped by default).

The HTML/XML fixtures below are trimmed copies of the REAL markup served by
giustizia-amministrativa.it after the 2026 portal reorganisation (issue #32).
Do not "simplify" them: the previous fixtures were invented, matched nothing on
the live site, and let a total outage of both tools pass CI unnoticed.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.giustizia_amm.client import (
    SEDI,
    TIPI_PROVVEDIMENTO,
    ProvvedimentoResult,
    _build_search_params,
    _compose_numero,
    _extract_form_action,
    _extract_p_auth,
    _extract_portlet_id,
    _is_error_page,
    _parse_results,
    _parse_total,
    _parse_xml_text,
    _resolve_schema,
    _SEARCH_PATH,
    build_document_url,
    citation_number,
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
# HTML/XML fixtures — trimmed from live responses
# ---------------------------------------------------------------------------

_PORTLET = "decisioni_pareri_web_DecisioniPareriWebPortlet_INSTANCE_XKc17mrB8J10"
_ACTION = (
    "https://www.giustizia-amministrativa.it/web/guest/dcsnprr"
    f"?p_p_id={_PORTLET}&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view"
    f"&_{_PORTLET}_javax.portlet.action=search&p_auth=6O8im78W"
)

# The real search page: the portlet id and p_auth live only in the form action.
_SEARCH_PAGE_HTML = f"""
<html><body>
<form id="_{_PORTLET}_provvedimentiForm" action="{_ACTION}" method="post">
<input type="text" name="_{_PORTLET}_searchtextProvvedimenti" value="">
<select name="_{_PORTLET}_sedeProvvedimenti"><option value=""></option>
<option value="Roma">Roma</option></select>
</form>
</body></html>
"""

_PAUTH_HTML_HIDDEN_INPUT = """
<html><body>
<form action="/web/guest/dcsnprr" method="post">
<input type="hidden" name="p_auth" value="testToken123">
</form>
</body></html>
"""

_PAUTH_HTML_NONE = """
<html><body><form action="/web/guest/dcsnprr" method="post"></form></body></html>
"""

# Two real result items (TAR Roma + Consiglio di Stato) plus the pagination
# footer, which is ALSO an <article class="ricerca--item"> and must be skipped.
_SEARCH_HTML = """
<html><body>
<article class="ricerca--item">
 <div class="ricerca--item__footer row">
  <div class="col-sm-12">
   <a class="visited-provvedimenti clickable" data-idprovv="Ob28x58BHkNp04hX6Cof"
      data-nrg="202510565" data-sede="tar_rm"
      href="https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&amp;schema=tar_rm&amp;nrg=202510565&amp;nomeFile=202614035_01.html&amp;subDir=Provvedimenti"
      target="_blank"><img alt="Apri il documento html originale"/></a>
   <a class="visited-provvedimenti clickable visualizza-provvedimento-h" href="#">
    202614035 (ROMA, SEZIONE 3Q) html
   </a>
  </div>
  <div class="col-sm-12">
   <b>SENTENZA</b> sede di <b>ROMA</b>, sezione <b>SEZIONE 3Q</b>, numero provv.: <b>202614035</b>
  </div>
  <div class="col-sm-12 snippet">
   ...Si tratterebbe di criticit&agrave; rilevanti anche dal punto di vista degli operatori
   economici e non solo dell'interesse <em>pubblico</em>. 2....
  </div>
  <div class="col-sm-12">Numero ricorso: <b>202510565</b></div>
  <div class="col-sm-12"><b>ECLI:IT:TARLAZ:2026:14035SENT</b></div>
 </div>
</article>
<article class="ricerca--item">
 <div class="ricerca--item__footer row">
  <div class="col-sm-12">
   <a class="visited-provvedimenti clickable" data-nrg="202401476" data-sede="cds"
      href="https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&amp;schema=cds&amp;nrg=202401476&amp;nomeFile=202605674_18.html&amp;subDir=Provvedimenti"
      target="_blank"><img alt="Apri il documento html originale"/></a>
   <a class="visited-provvedimenti clickable visualizza-provvedimento-h" href="#">
    202605674 (CONSIGLIO DI STATO, SEZIONE 5) html
   </a>
  </div>
  <div class="col-sm-12">
   <b>ORDINANZA</b> sede di <b>CONSIGLIO DI STATO</b>, sezione <b>SEZIONE 5</b>, numero provv.: <b>202605674</b>
  </div>
  <div class="col-sm-12 snippet">...appalto di servizi e <em>esclusione</em> dalla gara...</div>
  <div class="col-sm-12">Numero ricorso: <b>202401476</b></div>
  <div class="col-sm-12"><b>ECLI:IT:CDS:2026:5674ORD</b></div>
 </div>
</article>
<article class="ricerca--item">
 <div class="ricerca--item__footer row">
  <div class="col-sm-12">Risultati da 1 a 20 di 16297 totali</div>
  <div class="col-sm-12"><a href="#">Primo</a><a href="#">Successivo</a></div>
 </div>
</article>
</body></html>
"""

_SEARCH_HTML_EMPTY = """<html><body><div class="risultati"></div></body></html>"""

# Real <GA> shape: sections are nested under <Provvedimento>, never direct
# children of the root, and their text sits inside namespaced HTML <div>s.
_H = 'xmlns:h="http://www.w3.org/HTML/1998/html4"'
_MDP_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<GA {_H}>
<Provvedimento>
<meta id="2025105652026" descrizione="appalto equivalenza" ricorrente="-OMISSIS-">
<descrittori><registro anno="2025" n="10565"/><fascicolo anno="2026" n="14035"/></descrittori>
<tipologia>Sentenza</tipologia>
<dataPubblicazione>03/08/2026</dataPubblicazione>
</meta>
<epigrafe>
<adunanza>Il Tribunale Amministrativo Regionale per il Lazio (Sezione Terza Quater)
ha pronunciato la presente SENTENZA</adunanza>
<oggetto>per l'annullamento della procedura di gara aperta ex art. 71 del D.Lgs. n. 36/2023</oggetto>
<ricorrenti>sul ricorso numero di registro generale 10565 del 2025 proposto da Roche Diagnostics s.p.a.</ricorrenti>
</epigrafe>
<premessa>
<h:div>FATTO e DIRITTO</h:div>
<h:div>1. Con l'atto introduttivo del giudizio la Societa ha impugnato il bando di gara.</h:div>
<h:div><h:span>13.5 Il secondo ricorso per motivi aggiunti si rivela pertanto infondato.</h:span></h:div>
</premessa>
<motivazione></motivazione>
<dispositivo>
<h:div>P.Q.M.</h:div>
<h:div>Il Tribunale Amministrativo Regionale per il Lazio respinge il ricorso.</h:div>
</dispositivo>
</Provvedimento>
</GA>
""".encode()

# Older/other provvedimenti do carry <motivazione> instead of <premessa>.
_MDP_XML_MOTIVAZIONE = f"""<?xml version="1.0" encoding="UTF-8"?>
<GA {_H}>
<Provvedimento>
<epigrafe><adunanza>Il Consiglio di Stato (Sezione Quinta)</adunanza></epigrafe>
<motivazione><h:div>Il Collegio ritiene fondato il primo motivo di appello.</h:div></motivazione>
<dispositivo><h:div>P.Q.M.</h:div><h:div>accoglie l'appello e annulla il provvedimento.</h:div></dispositivo>
</Provvedimento>
</GA>
""".encode()

_MDP_XML_EMPTY_SECTIONS = f"""<?xml version="1.0" encoding="UTF-8"?>
<GA {_H}><Provvedimento><epigrafe></epigrafe><dispositivo></dispositivo></Provvedimento></GA>
""".encode()

# What mdp now serves for a stale URL: HTTP 200 with a 404 page in the body.
_MDP_404_PAGE = b"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><title>404 - Pagina non trovata</title></head>
<body><div class="container"><h1>404</h1><p>La pagina che stai cercando non esiste.</p></div></body></html>
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_mock_response(html_or_bytes, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html_or_bytes if isinstance(html_or_bytes, str) else html_or_bytes.decode()
    resp.content = html_or_bytes if isinstance(html_or_bytes, bytes) else html_or_bytes.encode()
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Tests: endpoint constants (the actual regression of issue #32)
# ---------------------------------------------------------------------------

class TestEndpoint:
    def test_search_path_is_dcsnprr(self):
        """The old /web/guest/-/ricerca-giurisprudenza path 404s since 2026."""
        assert _SEARCH_PATH == "/web/guest/dcsnprr"

    def test_search_path_is_not_the_dead_one(self):
        assert "ricerca-giurisprudenza" not in _SEARCH_PATH


# ---------------------------------------------------------------------------
# Tests: _extract_portlet_id / _extract_form_action / _extract_p_auth
# ---------------------------------------------------------------------------

class TestExtractPortletId:
    def test_extracts_instance_scoped_portlet_id(self):
        assert _extract_portlet_id(_SEARCH_PAGE_HTML) == _PORTLET

    def test_falls_back_to_default_when_absent(self):
        # Must never return "" — callers build parameter names from it.
        assert _extract_portlet_id("<html></html>").startswith("decisioni_pareri_web")


class TestExtractFormAction:
    def test_extracts_absolute_action_url(self):
        assert _extract_form_action(_SEARCH_PAGE_HTML) == _ACTION

    def test_returns_empty_when_no_form(self):
        assert _extract_form_action("<html></html>") == ""


class TestExtractPAuth:
    def test_extracts_from_form_action_url(self):
        assert _extract_p_auth(_SEARCH_PAGE_HTML) == "6O8im78W"

    def test_extracts_from_hidden_input(self):
        assert _extract_p_auth(_PAUTH_HTML_HIDDEN_INPUT) == "testToken123"

    def test_returns_empty_when_not_found(self):
        assert _extract_p_auth(_PAUTH_HTML_NONE) == ""


# ---------------------------------------------------------------------------
# Tests: _build_search_params
# ---------------------------------------------------------------------------

class TestBuildSearchParams:
    def test_query_uses_searchtext_field(self):
        params = _build_search_params(_PORTLET, query="appalto pubblico")
        assert params[f"_{_PORTLET}_searchtextProvvedimenti"] == "appalto pubblico"

    def test_no_legacy_testolibero_field(self):
        params = _build_search_params(_PORTLET, query="x")
        assert not any("testolibero" in k for k in params)

    def test_sede_uses_city_name(self):
        params = _build_search_params(_PORTLET, sede="Roma")
        assert params[f"_{_PORTLET}_sedeProvvedimenti"] == "Roma"

    def test_tipo_field(self):
        params = _build_search_params(_PORTLET, tipo="Sentenza")
        assert params[f"_{_PORTLET}_TipoProvvedimentoItem"] == "Sentenza"

    def test_page_size_field(self):
        params = _build_search_params(_PORTLET, page_size=40)
        assert params[f"_{_PORTLET}_pageSize"] == "40"

    def test_numero_field(self):
        params = _build_search_params(_PORTLET, numero="202301234")
        assert params[f"_{_PORTLET}_numeroProvvedimenti"] == "202301234"

    def test_mandatory_mode_fields_always_present(self):
        params = _build_search_params(_PORTLET)
        assert params[f"_{_PORTLET}_searchModeRadio"] == "provv"
        assert params[f"_{_PORTLET}_isAdvancedSearch"] == "false"

    def test_all_keys_are_portlet_scoped(self):
        params = _build_search_params(_PORTLET, query="x")
        assert all(k.startswith(f"_{_PORTLET}_") for k in params)


# ---------------------------------------------------------------------------
# Tests: _compose_numero — the portal matches the full YYYYNNNNN number
# ---------------------------------------------------------------------------

class TestComposeNumero:
    def test_pads_and_prefixes_with_year(self):
        assert _compose_numero("2023", "1234") == "202301234"

    def test_passes_through_full_number(self):
        assert _compose_numero("2023", "202301234") == "202301234"

    def test_numero_alone_is_kept(self):
        assert _compose_numero("", "1234") == "1234"

    def test_anno_alone_yields_nothing(self):
        """The portal dropped the standalone year filter; don't fake it."""
        assert _compose_numero("2023", "") == ""

    def test_non_numeric_numero_passes_through(self):
        assert _compose_numero("2023", "abc") == "abc"


# ---------------------------------------------------------------------------
# Tests: _resolve_schema / build_document_url
# ---------------------------------------------------------------------------

class TestResolveSchema:
    def test_schema_code_passes_through(self):
        assert _resolve_schema("tar_rm") == "tar_rm"
        assert _resolve_schema("cds") == "cds"

    def test_legacy_code_is_translated(self):
        """Old results (and LLM memory) still use TARLAZ/CDS."""
        assert _resolve_schema("TARLAZ") == "tar_rm"
        assert _resolve_schema("CDS") == "cds"

    def test_friendly_key_is_translated(self):
        assert _resolve_schema("tar_lazio") == "tar_rm"
        assert _resolve_schema("consiglio_di_stato") == "cds"


class TestBuildDocumentUrl:
    def test_uses_visualizza_endpoint(self):
        url = build_document_url("tar_rm", "202510565", "202614035_01.html")
        assert url.startswith("https://mdp.giustizia-amministrativa.it/visualizza/")

    def test_does_not_use_dead_mdp_atti_path(self):
        url = build_document_url("tar_rm", "202510565", "202614035_01.html")
        assert "/mdp/atti/" not in url

    def test_carries_all_required_params(self):
        url = build_document_url("cds", "202401476", "202605674_18.html")
        for frag in ("schema=cds", "nrg=202401476", "nomeFile=202605674_18.html",
                     "subDir=Provvedimenti"):
            assert frag in url

    def test_legacy_sede_code_resolved_in_url(self):
        assert "schema=tar_rm" in build_document_url("TARLAZ", "1", "f.html")


# ---------------------------------------------------------------------------
# Tests: _parse_results
# ---------------------------------------------------------------------------

class TestParseResults:
    def test_parses_two_results_and_skips_pagination_footer(self):
        results = _parse_results(_SEARCH_HTML)
        assert len(results) == 2

    def test_first_result_tar_roma(self):
        doc = _parse_results(_SEARCH_HTML)[0]
        assert doc.sede == "tar_rm"
        assert doc.sede_label == "TAR Lazio - Roma"
        assert doc.nrg == "202510565"
        assert doc.nome_file == "202614035_01.html"
        assert doc.numero == "202614035"
        assert doc.tipo == "SENTENZA"
        assert doc.anno == "2026"
        assert doc.sezione == "SEZIONE 3Q"
        assert doc.ecli == "ECLI:IT:TARLAZ:2026:14035SENT"
        assert "operatori" in doc.oggetto

    def test_second_result_consiglio_di_stato(self):
        doc = _parse_results(_SEARCH_HTML)[1]
        assert doc.sede == "cds"
        assert doc.sede_label == "Consiglio di Stato"
        assert doc.nrg == "202401476"
        assert doc.nome_file == "202605674_18.html"
        assert doc.tipo == "ORDINANZA"

    def test_empty_html_returns_empty_list(self):
        assert _parse_results(_SEARCH_HTML_EMPTY) == []

    def test_unknown_schema_uses_code_as_label(self):
        html = """<html><body><article class="ricerca--item">
        <a data-sede="tar_zz" data-nrg="1"
           href="https://mdp.giustizia-amministrativa.it/visualizza/?schema=tar_zz&nrg=1&nomeFile=x.html"></a>
        </article></body></html>"""
        results = _parse_results(html)
        assert len(results) == 1
        assert results[0].sede_label == "tar_zz"


# ---------------------------------------------------------------------------
# Tests: _is_error_page — mdp answers 200 with a 404 body
# ---------------------------------------------------------------------------

class TestIsErrorPage:
    def test_detects_404_html_body(self):
        assert _is_error_page(_MDP_404_PAGE) is True

    def test_real_xml_is_not_an_error_page(self):
        assert _is_error_page(_MDP_XML) is False


# ---------------------------------------------------------------------------
# Tests: _parse_xml_text
# ---------------------------------------------------------------------------

class TestParseXmlText:
    def test_extracts_title_from_nested_epigrafe(self):
        """<epigrafe> lives under <Provvedimento>, not directly under <GA>."""
        title, _ = _parse_xml_text(_MDP_XML)
        assert "Tribunale Amministrativo Regionale" in title

    def test_extracts_premessa_body(self):
        _, body = _parse_xml_text(_MDP_XML)
        assert "FATTO e DIRITTO" in body
        assert "impugnato il bando" in body

    def test_extracts_text_nested_deeper_than_one_level(self):
        _, body = _parse_xml_text(_MDP_XML)
        assert "motivi aggiunti si rivela pertanto infondato" in body

    def test_extracts_dispositivo(self):
        _, body = _parse_xml_text(_MDP_XML)
        assert "P.Q.M." in body
        assert "respinge il ricorso" in body

    def test_extracts_oggetto_from_epigrafe(self):
        _, body = _parse_xml_text(_MDP_XML)
        assert "D.Lgs. n. 36/2023" in body

    def test_supports_motivazione_variant(self):
        _, body = _parse_xml_text(_MDP_XML_MOTIVAZIONE)
        assert "primo motivo di appello" in body
        assert "annulla il provvedimento" in body

    def test_empty_sections_return_strings(self):
        title, body = _parse_xml_text(_MDP_XML_EMPTY_SECTIONS)
        assert isinstance(title, str) and isinstance(body, str)

    def test_invalid_xml_fallback(self):
        title, body = _parse_xml_text(b"<not valid xml <<>>")
        assert isinstance(title, str) and isinstance(body, str)

    def test_error_page_yields_empty_body(self):
        _, body = _parse_xml_text(_MDP_404_PAGE)
        assert body.strip() == ""


# ---------------------------------------------------------------------------
# Tests: format_result / format_full
# ---------------------------------------------------------------------------

def _sample_doc(**over) -> ProvvedimentoResult:
    base = dict(
        sede="tar_rm", sede_label="TAR Lazio - Roma", nrg="202510565", tipo="SENTENZA",
        anno="2026", nome_file="202614035_01.html", data_deposito="", numero="202614035",
        sezione="SEZIONE 3Q", ecli="ECLI:IT:TARLAZ:2026:14035SENT",
        oggetto="Appalto pubblico - Esclusione",
    )
    base.update(over)
    return ProvvedimentoResult(**base)


class TestFormatResult:
    def test_contains_sede_label_and_numero(self):
        text = format_result(_sample_doc())
        assert "TAR Lazio - Roma" in text
        assert "202614035" in text

    def test_contains_oggetto(self):
        assert "Esclusione" in format_result(_sample_doc())

    def test_exposes_params_needed_to_read_full_text(self):
        """An LLM must be able to call leggi_provvedimento_amm from this block."""
        text = format_result(_sample_doc())
        assert "tar_rm" in text
        assert "202510565" in text
        assert "202614035_01.html" in text

    def test_contains_sezione_and_ecli(self):
        text = format_result(_sample_doc())
        assert "SEZIONE 3Q" in text
        assert "ECLI:IT:TARLAZ:2026:14035SENT" in text

    def test_long_oggetto_truncated(self):
        assert len(format_result(_sample_doc(oggetto="x" * 900))) < 900


class TestFormatFull:
    def test_basic_formatting(self):
        result = format_full("CdS Sez. V", "Testo.", "cds", "202401476")
        assert "CdS Sez. V" in result
        assert "Testo." in result
        assert "202401476" in result

    def test_truncation_at_15000(self):
        result = format_full("Title", "a" * 16000, "cds", "123")
        assert "Testo troncato" in result
        assert "15000" in result

    def test_no_truncation_for_short_text(self):
        assert "troncato" not in format_full("Title", "breve", "cds", "123")

    def test_sede_label_resolved(self):
        assert "TAR Lazio" in format_full("Title", "testo", "tar_rm", "456")


# ---------------------------------------------------------------------------
# Tests: SEDI / TIPI_PROVVEDIMENTO constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_sedi_covers_all_31_portal_seats(self):
        assert len(SEDI) >= 31

    def test_sedi_values_are_portal_city_names(self):
        assert SEDI["consiglio_di_stato"] == "Consiglio di Stato"
        assert SEDI["tar_lazio"] == "Roma"
        assert SEDI["tar_lombardia"] == "Milano"
        assert SEDI["cgars"] == "C.G.A.R.S"

    def test_sedi_has_no_legacy_codes(self):
        assert "TARLAZ" not in SEDI.values()

    def test_second_seat_tars_are_addressable(self):
        assert SEDI["tar_lazio_latina"] == "Latina"
        assert SEDI["tar_lombardia_brescia"] == "Brescia"

    def test_tipi_provvedimento_values(self):
        assert TIPI_PROVVEDIMENTO["sentenza"] == "Sentenza"
        assert TIPI_PROVVEDIMENTO["ordinanza"] == "Ordinanza"
        assert TIPI_PROVVEDIMENTO["parere"] == "Parere"


# ---------------------------------------------------------------------------
# Tests: _impl functions (mocked network)
# ---------------------------------------------------------------------------

def _patch_session(search_html=_SEARCH_HTML, doc_bytes=_MDP_XML):
    """Patch GASession so no socket is opened."""
    session = AsyncMock()
    session.search = AsyncMock(return_value=search_html)
    session.fetch_text = AsyncMock(return_value=doc_bytes)
    session.portlet_id = _PORTLET
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return patch("src.lib.giustizia_amm.client.GASession", return_value=session)


class TestCercaImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        with _patch_session():
            result = await _cerca_giurisprudenza_amministrativa_impl(query="appalto")
        text = result.to_str()
        assert result.success is True
        assert "TAR Lazio - Roma" in text
        assert "Consiglio di Stato" in text

    @pytest.mark.asyncio
    async def test_no_results_message(self):
        with _patch_session(search_html=_SEARCH_HTML_EMPTY):
            result = await _cerca_giurisprudenza_amministrativa_impl(query="xyzzy")
        assert result.success is False
        assert result.error_type == "no_results"

    @pytest.mark.asyncio
    async def test_network_error_surfaces_as_source_down(self):
        with patch("src.lib.giustizia_amm.client.GASession") as mock:
            mock.return_value.__aenter__ = AsyncMock(
                side_effect=httpx.HTTPStatusError("boom", request=MagicMock(), response=MagicMock())
            )
            result = await _cerca_giurisprudenza_amministrativa_impl(query="appalto")
        assert result.success is False
        assert result.error_type == "source_down"


class TestYearFiltering:
    @pytest.mark.asyncio
    async def test_matching_year_kept_and_flagged(self):
        with _patch_session():
            result = await _cerca_giurisprudenza_amministrativa_impl(query="appalto", anno="2026")
        text = result.to_str()
        assert result.success is True
        assert "202614035" in text
        assert "non espone più un filtro per anno" in text

    @pytest.mark.asyncio
    async def test_non_matching_year_explains_why(self):
        """Silently returning 'nessun provvedimento' would look like a data gap."""
        with _patch_session():
            result = await _cerca_giurisprudenza_amministrativa_impl(query="appalto", anno="1999")
        assert result.success is False
        assert "non espone più un filtro per anno" in result.to_str()

    @pytest.mark.asyncio
    async def test_year_with_numero_goes_server_side(self):
        """anno+numero is a real portal filter — no client-side note needed."""
        with _patch_session():
            result = await _cerca_giurisprudenza_amministrativa_impl(
                query="", anno="2026", numero="14035"
            )
        assert "non espone più un filtro per anno" not in result.to_str()

    @pytest.mark.asyncio
    async def test_anno_da_keeps_newer_provvedimenti(self):
        with _patch_session():
            result = await _giurisprudenza_amm_su_norma_impl(riferimento="art. 71", anno_da="2020")
        assert result.success is True
        assert "202614035" in result.to_str()

    @pytest.mark.asyncio
    async def test_anno_da_in_the_future_drops_everything(self):
        with _patch_session():
            result = await _giurisprudenza_amm_su_norma_impl(riferimento="art. 71", anno_da="2099")
        assert result.success is False


class TestLeggiProvvedimentoImpl:
    @pytest.mark.asyncio
    async def test_returns_full_text(self):
        with _patch_session():
            result = await _leggi_provvedimento_amm_impl("tar_rm", "202510565", "202614035_01.html")
        assert result.success is True
        assert "P.Q.M." in result.to_str()

    @pytest.mark.asyncio
    async def test_stale_url_error_page_is_reported_not_silently_empty(self):
        with _patch_session(doc_bytes=_MDP_404_PAGE):
            result = await _leggi_provvedimento_amm_impl("tar_rm", "1", "stale.html")
        assert result.success is False


class TestGiurisprudenzaSuNormaImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        with _patch_session():
            result = await _giurisprudenza_amm_su_norma_impl(riferimento="art. 71 D.Lgs. 36/2023")
        assert result.success is True
        assert "202614035" in result.to_str()


class TestUltimiProvvedimentiImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        with _patch_session():
            result = await _ultimi_provvedimenti_amm_impl()
        assert result.success is True
        assert "TAR Lazio - Roma" in result.to_str()


# ---------------------------------------------------------------------------
# cerca_giurisprudenza_amministrativa: citation form, plenary bodies, portal
# total, and the date the search page does NOT carry (benchmark phase 3).
# Reference: Cons. Stato, Ad. plen., sentenza 9 novembre 2021 n. 17 (ricorso
# n. 14/2021 A.P., NRG 202105584), whose official XML reads
# <fascicolo anno="2021" n="00017"/>: the portal number 202100017 is YYYY + the
# five-digit progressive of the provvedimento, cited as "n. 17/2021".
# ---------------------------------------------------------------------------

# Trimmed copy of the REAL result item + footer for AP 17/2021 (query with
# anno=2021, numero=17: "Risultati da 1 a 1 di 1 totali").
_SEARCH_HTML_AP17 = """
<html><body>
<article class="ricerca--item">
 <div class="ricerca--item__footer row">
  <div class="col-sm-12">
   <a data-sede="cds" data-nrg="202105584" data-idprovv="c3xlSpMBITmkOkrmiUpf"
      href="https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&amp;schema=cds&amp;nrg=202105584&amp;nomeFile=202100017_11.html&amp;subDir=Provvedimenti"
      class="visited-provvedimenti clickable" target="_blank"><img alt="Apri il documento html originale"></a>
   <a data-word="" href="#" class="visited-provvedimenti clickable visualizza-provvedimento-h">202100017 (CONSIGLIO DI STATO, SEZIONE P) html
   </a>
  </div>
  <div class="col-sm-12">
   <b>SENTENZA</b> sede di <b>CONSIGLIO DI STATO</b>, sezione <b>SEZIONE P</b>, numero provv.: <b>202100017</b>
  </div>
  <div class="col-sm-12 snippet">...<em>demaniali</em> <em>marittime</em>. 38.2....</div>
  <div class="col-sm-12">Numero ricorso: <b>202105584</b></div>
  <div class="col-sm-12"><b>ECLI:IT:CDS:2021:17APLE</b></div>
 </div>
</article>
<article class="ricerca--item">
 <div class="ricerca--item__footer row">
  <div class="col-sm-12">

   Risultati da 1 a 1 di 1 totali
  </div>
 </div>
</article>
</body></html>
"""


class TestCitationForm:
    def test_citation_number_from_portal_number(self):
        # 202100017 = 2021 + 00017 -> "n. 17/2021" (XML <fascicolo anno="2021" n="00017"/>)
        assert citation_number("202100017") == "17/2021"
        assert citation_number("202614035") == "14035/2026"

    def test_citation_number_leaves_other_shapes_alone(self):
        assert citation_number("") == ""
        assert citation_number("17") == "17"

    def test_plenary_section_is_named_and_number_cited(self):
        doc = _parse_results(_SEARCH_HTML_AP17)[0]
        text = format_result(doc)
        assert "**Estremi**: Consiglio di Stato, Adunanza plenaria, sentenza n. 17/2021" in text
        # The portal's own labels stay, so an agent can still match them.
        assert "n. 202100017 (2021)" in text
        assert "**Sezione**: SEZIONE P" in text
        assert "ECLI:IT:CDS:2021:17APLE" in text

    def test_section_c_is_the_adunanza_generale_only_at_the_cds(self):
        cds = _sample_doc(sede="cds", sede_label="Consiglio di Stato", sezione="SEZIONE C",
                          tipo="PARERE", numero="202600012")
        assert "Adunanza generale, parere n. 12/2026" in format_result(cds)
        tar = _sample_doc(sezione="SEZIONE C")
        assert "Adunanza" not in format_result(tar)

    def test_ordinary_tar_result_gets_the_citation_form(self):
        text = format_result(_sample_doc())
        assert "**Estremi**: TAR Lazio - Roma, sentenza n. 14035/2026" in text


class TestPortalTotal:
    def test_parse_total_reads_the_results_footer(self):
        assert _parse_total(_SEARCH_HTML_AP17) == 1
        assert _parse_total(_SEARCH_HTML) == 16297
        assert _parse_total(_SEARCH_HTML_EMPTY) is None

    @pytest.mark.asyncio
    async def test_count_says_it_is_a_page_of_a_larger_answer(self):
        with _patch_session():
            result = await _cerca_giurisprudenza_amministrativa_impl(query="appalto")
        text = result.to_str()
        assert "**Trovati 2 provvedimenti TAR/CdS" in text
        assert "mostrati 2 su 16297 totali indicati dal portale" in text

    @pytest.mark.asyncio
    async def test_exact_lookup_does_not_claim_a_larger_answer(self):
        with _patch_session(search_html=_SEARCH_HTML_AP17):
            result = await _cerca_giurisprudenza_amministrativa_impl(
                query="concessioni demaniali marittime", sede="consiglio_di_stato",
                tipo="adunanza_plenaria", anno="2021", numero="17",
            )
        text = result.to_str()
        assert "**Trovati 1 provvedimenti TAR/CdS" in text
        assert "mostrati" not in text
        assert "Adunanza plenaria, sentenza n. 17/2021" in text


class TestNoDateOnTheSearchPage:
    """The search page carries no date: the answer says where to read it, and the
    docstring stops promising it (art. 89 c.p.a.: the date of publication is the
    one the segretario writes at the foot of the sentence, in the XML)."""

    @pytest.mark.asyncio
    async def test_answer_points_to_leggi_for_the_date(self):
        with _patch_session(search_html=_SEARCH_HTML_AP17):
            result = await _cerca_giurisprudenza_amministrativa_impl(query="concessioni")
        text = result.to_str()
        assert "non espone la data" in text
        assert "leggi_provvedimento_amm()" in text

    def test_docstring_does_not_promise_a_date(self):
        from src.tools import giustizia_amm as ga_tools

        fn = getattr(ga_tools.cerca_giurisprudenza_amministrativa, "fn",
                     ga_tools.cerca_giurisprudenza_amministrativa)
        doc = fn.__doc__
        assert "tipo, data e oggetto" not in doc
        assert "NON restituisce la data" in doc


# ---------------------------------------------------------------------------
# leggi_provvedimento_amm: dispositivo kept when the text is shortened, date of
# publication from the XML, PDF-only provvedimenti (benchmark phase 3).
# Reference: Cons. Stato, Ad. plen., sentenza n. 17/2021 (nrg 202105584): body of
# 106,448 characters, "P.Q.M." at 104,513, <dataPubblicazione>09/11/2021.
# Art. 88, co. 2, lett. e), d.lgs. 104/2010 (c.p.a.): the dispositivo is a
# necessary element of the sentence. Art. 89, co. 2-3, c.p.a.: the segretario
# writes the date of deposit at the foot of the sentence.
# ---------------------------------------------------------------------------

# Real <GA> shape of AP 17/2021 (note the leading space of <tipologia>, the
# zero-padded n="00017" and the dispositivo as the LAST section); the premessa
# is padded to the real length so the text overflows the 15,000-character cut.
_AP17_PQM = (
    "P.Q.M. Il Consiglio di Stato in sede giurisdizionale (Adunanza Plenaria) "
    "definitivamente pronunciando: a) dichiara inammissibili gli interventi; "
    "b) enuncia i principi di diritto di cui in motivazione; c) restituisce gli atti "
    "al Consiglio di Giustizia amministrativa per la Regione siciliana."
)
_MDP_XML_AP17 = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<GA {_H}><Provvedimento>
<meta id="20210558420211107183102616" descrizione="" ricorrente="-OMISSIS-">
<descrittori><registro anno="2021" n="00014"/><fascicolo anno="2021" n="00017"/></descrittori>
<tipologia> Sentenza</tipologia>
<dataPubblicazione>09/11/2021</dataPubblicazione>
</meta>
<epigrafe><adunanza><h:div>Il Consiglio di Stato</h:div><h:div>in sede giurisdizionale (Adunanza Plenaria)</h:div></adunanza>
<oggetto><h:div>per la riforma della sentenza del TAR Catania n. 504/2021</h:div></oggetto></epigrafe>
<premessa><h:div>{"Le concessioni demaniali marittime sono prorogate ex lege. " * 1900}</h:div></premessa>
<motivazione></motivazione>
<dispositivo><h:div>{_AP17_PQM}</h:div></dispositivo>
</Provvedimento></GA>
""".encode()

_PDF_BYTES = b"%PDF-1.7\n%\xb5\xb5\xb5\xb5\n1 0 obj\n<</Type/Catalog>>\nendobj\n5 0 obj\n<</Length 9>>\nstream\n\x00\x01\x02\nendstream\nendobj\n"


class TestXmlMeta:
    def test_reads_type_number_and_date_of_the_official_xml(self):
        from src.lib.giustizia_amm.client import _parse_xml_meta

        assert _parse_xml_meta(_MDP_XML_AP17) == {
            "tipologia": "Sentenza",          # leading space stripped
            "numero": "17/2021",              # n="00017" anno="2021"
            "data_pubblicazione": "09/11/2021",
        }

    def test_meta_empty_for_pdf_and_error_page(self):
        from src.lib.giustizia_amm.client import _parse_xml_meta

        assert _parse_xml_meta(_PDF_BYTES) == {}
        assert _parse_xml_meta(_MDP_404_PAGE) == {}

    def test_is_pdf_by_signature(self):
        from src.lib.giustizia_amm.client import is_pdf

        assert is_pdf(_PDF_BYTES)
        assert not is_pdf(_MDP_XML) and not is_pdf(_MDP_404_PAGE)

    def test_parse_xml_text_never_returns_pdf_bytes_as_text(self):
        assert _parse_xml_text(_PDF_BYTES) == ("", "")


class TestDispositivoSurvivesTruncation:
    _DISP = "P.Q.M. accoglie l'appello e annulla il provvedimento."

    def _text(self, filler: int, disp: str | None = None) -> str:
        return ("MOTIVAZIONE\n\n" + "a" * filler + "\n\nDISPOSITIVO\n\n" + (disp or self._DISP))

    def test_long_text_keeps_head_omission_marker_and_whole_dispositivo(self):
        text = self._text(106_000)
        out = format_full("Title", text, "cds", "123")
        assert out.count(self._DISP) == 1
        assert "DISPOSITIVO\n\n" + self._DISP in out
        assert "omissis" in out
        # about the declared size, not the whole text
        assert len(out) < 15_000 + 600
        assert f"su {len(text)} totali" in out
        assert "il DISPOSITIVO è riportato per intero" in out

    def test_omitted_count_is_exact(self):
        import re

        text = self._text(50_000)
        out = format_full("Title", text, "cds", "123")
        omitted = int(re.search(r"omissis: (\d+) caratteri", out).group(1))
        # the body follows the "**Sede**" line and a blank line
        body = out.split("**Sede**: ", 1)[1].split("\n\n", 1)[1]
        head_text = body.split("\n\n[... omissis")[0]
        idx = text.rfind("\n\nDISPOSITIVO\n\n")
        # kept head + omitted characters = everything that precedes the dispositivo
        assert omitted > 0 and len(head_text) + omitted == idx

    def test_oversized_dispositivo_is_capped_and_declared(self):
        big = "P.Q.M. " + "x" * 9000
        text = self._text(50_000, big)
        out = format_full("Title", text, "cds", "123")
        assert "il DISPOSITIVO è riportato per i primi 6000 caratteri su" in out
        assert len(out) < 15_000 + 800

    def test_text_without_dispositivo_is_cut_as_before(self):
        out = format_full("Title", "a" * 16000, "cds", "123")
        assert "omissis" not in out
        assert "Testo troncato a 15000 caratteri su 16000 totali" in out

    def test_short_text_is_untouched(self):
        text = self._text(100)
        out = format_full("Title", text, "cds", "123")
        assert text in out and "troncato" not in out and "omissis" not in out


class TestLeggiKeepsPqmAndDate:
    @pytest.mark.asyncio
    async def test_ap17_shape_pqm_and_publication_date_reach_the_reader(self):
        with _patch_session(doc_bytes=_MDP_XML_AP17):
            result = await _leggi_provvedimento_amm_impl("cds", "202105584", "202100017_11.html")
        text = result.to_str()
        assert result.success is True
        assert "P.Q.M." in text and "enuncia i principi di diritto" in text
        assert "**Estremi**: Sentenza n. 17/2021, pubblicata il 09/11/2021" in text
        assert "**Sede**: Consiglio di Stato (cds) — NRG: 202105584" in text  # unchanged line
        assert "(Adunanza Plenaria)" in text
        assert "omissis" in text and "Testo troncato a 15000 caratteri su" in text

    @pytest.mark.asyncio
    async def test_short_xml_shows_its_estremi_too(self):
        with _patch_session():
            result = await _leggi_provvedimento_amm_impl("tar_rm", "202510565", "202614035_01.html")
        assert "**Estremi**: Sentenza n. 14035/2026, pubblicata il 03/08/2026" in result.to_str()


class TestLeggiPdfOnly:
    @pytest.mark.asyncio
    async def test_pdf_is_declared_not_dumped(self):
        with _patch_session(doc_bytes=_PDF_BYTES):
            result = await _leggi_provvedimento_amm_impl("cds", "202508523", "202606915_11.pdf")
        text = result.to_str()
        assert result.success is False
        assert result.error_type == "pdf_only"
        assert "%PDF-" not in text and "endobj" not in text
        assert "solo in formato PDF" in text
        # the official document is one click away
        assert "schema=cds" in text and "nomeFile=202606915_11.pdf" in text
        assert "mdp.giustizia-amministrativa.it/visualizza/" in text

    @pytest.mark.asyncio
    async def test_error_page_keeps_its_own_message(self):
        with _patch_session(doc_bytes=_MDP_404_PAGE):
            result = await _leggi_provvedimento_amm_impl("cds", "202500000", "202500000_01.html")
        assert result.error_type == "no_results"
        assert "pagina di errore" in result.to_str()


# ---------------------------------------------------------------------------
# Live tests — hit the real portal. Run with: pytest -m live
# These are the guard-rail for issue #32: a silent endpoint move must fail here.
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.asyncio
async def test_live_search_returns_results():
    from src.lib.giustizia_amm.client import search_provvedimenti

    docs = await search_provvedimenti(query="appalto pubblico esclusione", rows=10)
    assert docs, "il portale non ha restituito provvedimenti"
    doc = docs[0]
    assert doc.sede and doc.nrg and doc.nome_file


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_full_text_roundtrip():
    from src.lib.giustizia_amm.client import fetch_provvedimento_text, search_provvedimenti

    docs = await search_provvedimenti(query="silenzio assenso", rows=20)
    assert docs
    # PDF-only provvedimenti (about 30% of the latest CdS ones) have no XML text:
    # the roundtrip is about the XML ones. Before phase 3 this test also passed on
    # the raw bytes of a PDF, which is why it now rejects them explicitly.
    xml_docs = [d for d in docs if d.nome_file.endswith(".html")]
    assert xml_docs, f"nessun provvedimento XML tra i risultati: {[d.nome_file for d in docs]}"
    doc = xml_docs[0]
    title, body = await fetch_provvedimento_text(doc.sede, doc.nrg, doc.nome_file)
    assert len(body) > 500, f"testo troppo corto: {body[:200]!r}"
    assert "%PDF-" not in body and "endobj" not in body


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_sede_filter():
    from src.lib.giustizia_amm.client import search_provvedimenti

    docs = await search_provvedimenti(query="", sede="consiglio_di_stato", rows=10)
    assert docs
    assert all(d.sede == "cds" for d in docs)
