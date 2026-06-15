"""Unit tests for the Gazzetta Ufficiale scraper (client + tools).

Tests run against mocked httpx responses — no real network calls. Fixtures are
small but faithful to the live structure captured from gazzettaufficiale.it:
RSS feed, parametric-search results page, ELI atto head (RDFa), vediMenuHTML,
caricaArticolo, and a sommario page.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib._result import SearchResult
from src.lib.gazzetta.client import (
    RSS_CODE,
    SERIE,
    AttoDetail,
    AttoResult,
    _build_search_data,
    _eli_atto_url,
    _menu_url,
    _parse_article_text,
    _parse_atto_header,
    _parse_eli_metadata,
    _parse_menu_article_urls,
    _parse_rss,
    _parse_search_results,
    _parse_sommario,
    _search_result_count,
    _sommario_url,
    format_detail,
    format_result,
    format_sommario,
    pdf_url,
)

from src.tools.gazzetta import (
    _cerca_gazzetta_ufficiale_impl,
    _leggi_atto_gazzetta_impl,
    _resolve_rss_code,
    _resolve_serie_path,
    _scarica_pdf_gazzetta_impl,
    _sommario_gazzetta_impl,
    _ultime_gazzette_impl,
)


# ---------------------------------------------------------------------------
# Fixtures (faithful to live structure)
# ---------------------------------------------------------------------------

_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>Gazzetta Ufficiale - Serie Generale - Sommario</title>
    <link>http://www.gazzettaufficiale.it/eli/gu/2026/06/13/135/SG/html</link>
    <description>Gazzetta Ufficiale - Serie Generale n. 135 del 13-06-2026</description>
    <language>it</language>
    <item>
      <title>MINISTERO DELLE IMPRESE E DEL MADE IN ITALY - DECRETO 17 febbraio 2026</title>
      <link>http://www.gazzettaufficiale.it/eli/id/2026/06/13/26A02924/SG</link>
      <content:encoded>Modifica del decreto 16 gennaio 1997 concernente criteri per la
determinazione dei compensi spettanti ai commissari liquidatori. (26A02924)</content:encoded>
      <pubDate>Sat, 13 Jun 2026 11:01:19 GMT</pubDate>
    </item>
    <item>
      <title>MINISTERO DELLE IMPRESE E DEL MADE IN ITALY - DECRETO 22 maggio 2026</title>
      <link>http://www.gazzettaufficiale.it/eli/id/2026/06/13/26A02808/SG</link>
      <content:encoded>Liquidazione coatta amministrativa della Multiservizi 2000 societa'
cooperativa sociale, in Supino e nomina del commissario liquidatore. (26A02808)</content:encoded>
      <pubDate>Sat, 13 Jun 2026 11:01:16 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

_RSS_XML_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Vuoto</title></channel></rss>
"""

# Two result spans, the first preceded by an <span class="emettitore">.
# The title carries Gazzetta highlight markup (<strong><FONT>...) + a trailing
# (codice) and a <span class="riferimento">.
_SEARCH_HTML = """
<html><body>
<div class="count_risultati">Risultati della ricerca: 223 atti</div>
<div class="risultati_ricerca">
  <span class="emettitore">BANCA D'ITALIA</span>
  <span class="risultato">
    <a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-05-22&atto.codiceRedazionale=26A02532">
      <span class="data">
            COMUNICATO


      </span>
    </a>
    <a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-05-22&atto.codiceRedazionale=26A02532">Revoca dell'autorizzazione all'esercizio dell'attivita' di Iremit Consulting S.p.a. in <strong><FONT COLOR=#370AED>liquidazione</FONT></strong> <strong><FONT COLOR=#370AED>coatta</FONT></strong>. (26A02532)
      <span class="riferimento">(GU n.117 del 22-5-2026)</span>
    </a>
  </span>
  <span class="emettitore">MINISTERO DELLE IMPRESE E DEL MADE IN ITALY</span>
  <span class="risultato">
    <a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-02-06&atto.codiceRedazionale=26A00412">
      <span class="data">
            DECRETO



            3 dicembre 2025
      </span>
    </a>
    <a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-02-06&atto.codiceRedazionale=26A00412">Liquidazione coatta amministrativa della societa' cooperativa Nonsolopane. (26A00412)
      <span class="riferimento">(GU n.30 del 6-2-2026)</span>
    </a>
  </span>
</div>
</body></html>
"""

_SEARCH_HTML_EMPTY = """
<html><body>
<div class="count_risultati">Risultati della ricerca: 0 atti</div>
<div class="risultati_ricerca"></div>
</body></html>
"""

# ELI atto head: RDFa <meta> tags carry the canonical metadata.
_ELI_HEAD_HTML = """
<html><head>
<meta about="gu:id/2026/06/13/26A02808/sg" property="eli:id_local" content="26A02808" />
<meta about="gu:id/2026/06/13/26A02808/sg" property="eli:type_document" resource="gu:tables/resource-type#DECRETO"/>
<meta about="gu:id/2026/06/13/26A02808/sg" property="eli:passed_by" resource="gu:tables/issuers#IMPRESE_ITALY_MADE_MINISTERO"/>
<meta about="gu:id/2026/06/13/26A02808/sg" property="eli:date_document" content="2026-05-22" datatype="xsd:date" />
<meta about="gu:id/2026/06/13/26A02808/sg" property="eli:date_publication" content="2026-06-13" datatype="xsd:date" />
</head><body>
<span about="gu:id/2026/06/13/26A02808/sg/ita" property="eli:title">Liquidazione coatta amministrativa della Multiservizi 2000.</span>
</body></html>
"""

# vediMenuHTML: anchors to the exact caricaArticolo URLs (must be harvested).
_MENU_HTML = """
<html><body>
<ul class="menu_atto">
  <li><a href="/atto/serie_generale/caricaArticolo?art.versione=1&art.idGruppo=0&art.flagTipoArticolo=0&art.codiceRedazionale=26A02808&art.idArticolo=1&art.idSottoArticolo=1">Art. 1</a></li>
  <li><a href="/atto/serie_generale/caricaArticolo?art.versione=1&art.idGruppo=0&art.flagTipoArticolo=0&art.codiceRedazionale=26A02808&art.idArticolo=2&art.idSottoArticolo=1">Art. 2</a></li>
  <li><a href="/atto/serie_generale/altro?x=1">Altro (non articolo)</a></li>
</ul>
</body></html>
"""

_ARTICLE_HTML = """
<html><body>
<div class="dettaglio_atto_testo">
<script>var x=1;</script>
IL MINISTRO DELLE IMPRESE E DEL MADE IN ITALY
Visto l'art. 2545-terdecies del codice civile;
DECRETA: la liquidazione coatta amministrativa della cooperativa.
</div>
</body></html>
"""

_SOMMARIO_HTML = """
<html><body>
<h2 class="testata">Sommario</h2>
<ul>
  <li><a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-06-13&atto.codiceRedazionale=26A02924&elenco30giorni=false">DECRETO 17 febbraio 2026 (26A02924)</a></li>
  <li><a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-06-13&atto.codiceRedazionale=26A02808&elenco30giorni=false">DECRETO 22 maggio 2026 (26A02808)</a></li>
</ul>
</body></html>
"""

_SOMMARIO_HTML_EMPTY = """<html><body><h2 class="testata">Sommario</h2><ul></ul></body></html>"""


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_resp(text: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def _client_with_get(get_side):
    """Build an async-context-manager mock client with a .get side effect."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = AsyncMock(side_effect=get_side) if isinstance(get_side, list) else AsyncMock(return_value=get_side)
    client.post = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# _build_search_data
# ---------------------------------------------------------------------------

class TestBuildSearchData:
    def test_complete_field_set(self):
        data = _build_search_data()
        # every field the Spring controller demands must be present (else HTTP 500)
        required = {
            "numeroProvvedimento", "giornoProvvedimento", "meseProvvedimento",
            "annoProvvedimento", "attiNumerati", "descrizioneTipoProvvedimento",
            "codiceTipoProvvedimento", "descrizioneEmettitore", "codiceEmettitore",
            "descrizioneMateria", "codiceMateria", "tipoRicercaTitolo", "titolo",
            "titoloNot", "tipoRicercaTesto", "testo", "testoNot",
            "giornoPubblicazioneDa", "mesePubblicazioneDa", "annoPubblicazioneDa",
            "giornoPubblicazioneA", "mesePubblicazioneA", "annoPubblicazioneA",
            "cerca",
        }
        assert required.issubset(data.keys())

    def test_values_passed_through(self):
        data = _build_search_data(
            titolo="liquidazione", testo="cooperativa", anno_da="2024", anno_a="2026",
            descrizione_tipo_provvedimento="DECRETO",
            descrizione_emettitore="MINISTERO", descrizione_materia="SOCIETA",
        )
        assert data["titolo"] == "liquidazione"
        assert data["testo"] == "cooperativa"
        assert data["annoPubblicazioneDa"] == "2024"
        assert data["annoPubblicazioneA"] == "2026"
        assert data["descrizioneTipoProvvedimento"] == "DECRETO"
        assert data["descrizioneEmettitore"] == "MINISTERO"
        assert data["descrizioneMateria"] == "SOCIETA"

    def test_cerca_flag(self):
        assert _build_search_data()["cerca"] == "cerca"

    def test_atti_numerati_default_false(self):
        assert _build_search_data()["attiNumerati"] == "false"


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

class TestUrlBuilders:
    def test_eli_atto_url(self):
        url = _eli_atto_url("2026-06-13", "26A02808")
        assert url == "https://www.gazzettaufficiale.it/eli/id/2026/06/13/26A02808/sg"

    def test_menu_url(self):
        url = _menu_url("serie_generale", "2026-06-13", "26A02808")
        assert "vediMenuHTML" in url
        assert "atto.codiceRedazionale=26A02808" in url
        assert "tipoSerie=serie_generale" in url
        assert "tipoVigenza=originario" in url

    def test_sommario_url(self):
        url = _sommario_url("2026-06-13", "135")
        assert url == "https://www.gazzettaufficiale.it/eli/gu/2026/06/13/135/sg"

    def test_pdf_url(self):
        url = pdf_url("2026-06-13", "135")
        assert url == "https://www.gazzettaufficiale.it/eli/gu/2026/06/13/135/sg/pdf"


# ---------------------------------------------------------------------------
# _parse_rss
# ---------------------------------------------------------------------------

class TestParseRss:
    def test_parses_two_items(self):
        res = _parse_rss(_RSS_XML)
        assert len(res) == 2

    def test_first_item_fields(self):
        res = _parse_rss(_RSS_XML)
        a = res[0]
        assert a.codice_redazionale == "26A02924"
        assert a.data_pubblicazione == "2026-06-13"
        assert a.emettitore == "MINISTERO DELLE IMPRESE E DEL MADE IN ITALY"
        assert "DECRETO 17 febbraio 2026" == a.tipo
        assert a.pub_date == "2026-06-13"
        assert "Modifica del decreto" in a.title
        # the trailing (codice) marker is stripped from the subject
        assert "(26A02924)" not in a.title

    def test_eli_url_built(self):
        res = _parse_rss(_RSS_XML)
        assert res[0].eli_url == "https://www.gazzettaufficiale.it/eli/id/2026/06/13/26A02924/SG"

    def test_empty_feed(self):
        assert _parse_rss(_RSS_XML_EMPTY) == []


# ---------------------------------------------------------------------------
# _parse_search_results / _search_result_count
# ---------------------------------------------------------------------------

class TestParseSearchResults:
    def test_parses_two_results(self):
        res = _parse_search_results(_SEARCH_HTML)
        assert len(res) == 2

    def test_first_result_fields(self):
        res = _parse_search_results(_SEARCH_HTML)
        a = res[0]
        assert a.codice_redazionale == "26A02532"
        assert a.data_pubblicazione == "2026-05-22"
        assert a.emettitore == "BANCA D'ITALIA"
        assert a.tipo == "COMUNICATO"
        assert a.riferimento == "(GU n.117 del 22-5-2026)"
        # highlight markup is flattened, (codice) + riferimento stripped from title
        assert "Iremit" in a.title
        assert "liquidazione" in a.title
        assert "(26A02532)" not in a.title
        assert "GU n.117" not in a.title

    def test_decreto_tipo_whitespace_collapsed(self):
        res = _parse_search_results(_SEARCH_HTML)
        a = res[1]
        assert a.tipo == "DECRETO 3 dicembre 2025"
        assert "\n" not in a.tipo

    def test_emettitore_tracking(self):
        res = _parse_search_results(_SEARCH_HTML)
        assert res[1].emettitore == "MINISTERO DELLE IMPRESE E DEL MADE IN ITALY"

    def test_eli_url_built(self):
        res = _parse_search_results(_SEARCH_HTML)
        assert res[0].eli_url.endswith("/eli/id/2026/05/22/26A02532/SG")

    def test_empty_results(self):
        assert _parse_search_results(_SEARCH_HTML_EMPTY) == []

    def test_result_count(self):
        assert _search_result_count(_SEARCH_HTML) == 223

    def test_result_count_with_thousands_separator(self):
        html = "<html>Risultati della ricerca: 1.234 atti</html>"
        assert _search_result_count(html) == 1234

    def test_result_count_absent(self):
        assert _search_result_count("<html>nulla</html>") == 0


# ---------------------------------------------------------------------------
# _parse_eli_metadata / _parse_atto_header
# ---------------------------------------------------------------------------

class TestParseEliMetadata:
    def test_extracts_all_keys(self):
        meta = _parse_eli_metadata(_ELI_HEAD_HTML)
        assert meta["id_local"] == "26A02808"
        assert meta["type_document"] == "DECRETO"
        assert meta["passed_by"] == "IMPRESE_ITALY_MADE_MINISTERO"
        assert meta["date_document"] == "2026-05-22"
        assert meta["date_publication"] == "2026-06-13"

    def test_missing_metadata_returns_empty_dict(self):
        assert _parse_eli_metadata("<html><head></head></html>") == {}

    def test_atto_header_absent_classes_returns_empty(self):
        # the ELI head has no emettitore/tipo/titolo CSS classes
        assert _parse_atto_header(_ELI_HEAD_HTML) == ("", "", "")


# ---------------------------------------------------------------------------
# _parse_menu_article_urls / _parse_article_text
# ---------------------------------------------------------------------------

class TestParseMenu:
    def test_harvests_carica_articolo_urls(self):
        urls = _parse_menu_article_urls(_MENU_HTML)
        assert len(urls) == 2
        assert all("caricaArticolo?" in u for u in urls)
        assert all(u.startswith("https://www.gazzettaufficiale.it") for u in urls)

    def test_skips_non_article_anchors(self):
        urls = _parse_menu_article_urls(_MENU_HTML)
        assert not any("altro?" in u for u in urls)

    def test_deduplicates(self):
        html = (
            '<a href="/atto/serie_generale/caricaArticolo?art.idArticolo=1#x">A</a>'
            '<a href="/atto/serie_generale/caricaArticolo?art.idArticolo=1">A again</a>'
        )
        # the #fragment is stripped, so both collapse to one URL
        assert len(_parse_menu_article_urls(html)) == 1


class TestParseArticleText:
    def test_extracts_body(self):
        text = _parse_article_text(_ARTICLE_HTML)
        assert "IL MINISTRO" in text
        assert "DECRETA" in text

    def test_strips_scripts(self):
        text = _parse_article_text(_ARTICLE_HTML)
        assert "var x" not in text

    def test_missing_container_returns_empty(self):
        assert _parse_article_text("<html><body><p>no container</p></body></html>") == ""


# ---------------------------------------------------------------------------
# _parse_sommario
# ---------------------------------------------------------------------------

class TestParseSommario:
    def test_heading_and_atti(self):
        heading, atti = _parse_sommario(_SOMMARIO_HTML)
        assert heading == "Sommario"
        assert len(atti) == 2
        assert atti[0].codice_redazionale == "26A02924"
        assert atti[1].codice_redazionale == "26A02808"

    def test_codice_dedup(self):
        html = _SOMMARIO_HTML.replace("26A02808", "26A02924")  # duplicate codice
        _, atti = _parse_sommario(html)
        assert len(atti) == 1

    def test_empty(self):
        heading, atti = _parse_sommario(_SOMMARIO_HTML_EMPTY)
        assert atti == []


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class TestFormatters:
    def test_format_result(self):
        atto = AttoResult(
            codice_redazionale="26A02808", data_pubblicazione="2026-06-13",
            title="Liquidazione coatta", emettitore="MINISTERO", tipo="DECRETO",
            riferimento="(GU n.135 del 13-6-2026)",
            eli_url="https://www.gazzettaufficiale.it/eli/id/2026/06/13/26A02808/SG",
        )
        out = format_result(atto)
        assert "MINISTERO" in out
        assert "DECRETO" in out
        assert "26A02808" in out
        assert "2026-06-13" in out
        assert "GU n.135" in out
        assert "gazzettaufficiale.it" in out

    def test_format_detail_metadata_only(self):
        d = AttoDetail(
            codice_redazionale="26A02808", data_pubblicazione="2026-06-13",
            serie="serie_generale", title="Liquidazione", tipo="DECRETO",
            emettitore="MINISTERO", metadata_only=True,
            eli_url="https://www.gazzettaufficiale.it/eli/id/2026/06/13/26A02808/sg",
        )
        out = format_detail(d)
        assert "Solo metadati" in out
        assert "DECRETO" in out

    def test_format_detail_with_text(self):
        d = AttoDetail(
            codice_redazionale="26A02808", data_pubblicazione="2026-06-13",
            serie="serie_generale", title="Liquidazione", text="Corpo dell'atto.",
        )
        out = format_detail(d)
        assert "Corpo dell'atto." in out
        assert "troncato" not in out

    def test_format_detail_truncation(self):
        d = AttoDetail(
            codice_redazionale="X", data_pubblicazione="2026-06-13",
            serie="serie_generale", text="a" * 30000,
        )
        out = format_detail(d)
        assert "troncato" in out
        assert "25000" in out

    def test_format_sommario(self):
        atti = [
            AttoResult(codice_redazionale="26A02924", data_pubblicazione="2026-06-13", title="DECRETO 1"),
            AttoResult(codice_redazionale="26A02808", data_pubblicazione="2026-06-13", title="DECRETO 2"),
        ]
        out = format_sommario("Sommario", atti)
        assert "Atti**: 2" in out
        assert "26A02924" in out
        assert "26A02808" in out


# ---------------------------------------------------------------------------
# Serie / RSS resolution
# ---------------------------------------------------------------------------

class TestResolution:
    def test_serie_map_complete(self):
        assert set(SERIE.keys()) == {
            "serie_generale", "unione_europea", "regioni", "corte_costituzionale",
            "parte_seconda", "contratti", "concorsi",
        }

    def test_rss_code_map(self):
        assert RSS_CODE["serie_generale"] == "SG"
        assert RSS_CODE["unione_europea"] == "S1"
        assert RSS_CODE["parte_seconda"] == "P2"

    def test_resolve_serie_path_known(self):
        assert _resolve_serie_path("Corte Costituzionale") == "corte_costituzionale"

    def test_resolve_serie_path_unknown_defaults(self):
        assert _resolve_serie_path("inesistente") == "serie_generale"

    def test_resolve_rss_code_known(self):
        assert _resolve_rss_code("unione_europea") == "S1"

    def test_resolve_rss_code_unknown_defaults(self):
        assert _resolve_rss_code("inesistente") == "SG"


# ---------------------------------------------------------------------------
# _impl: ultime_gazzette (RSS-based)
# ---------------------------------------------------------------------------

class TestUltimeGazzetteImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        client = _client_with_get(_make_resp(_RSS_XML))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _ultime_gazzette_impl()
        assert isinstance(result, SearchResult)
        assert result.success
        out = result.to_str()
        assert "Ultimi atti" in out
        assert "26A02924" in out

    @pytest.mark.asyncio
    async def test_empty_feed(self):
        client = _client_with_get(_make_resp(_RSS_XML_EMPTY))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _ultime_gazzette_impl()
        assert not result.success
        assert "Nessun atto" in result.to_str()

    @pytest.mark.asyncio
    async def test_source_down(self):
        client = _client_with_get(_make_resp(""))
        client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _ultime_gazzette_impl()
        assert not result.success
        assert "Errore" in result.to_str()


# ---------------------------------------------------------------------------
# _impl: cerca_gazzetta_ufficiale (seed GET + POST)
# ---------------------------------------------------------------------------

class TestCercaGazzettaImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        client = _client_with_get(_make_resp("<html>seed</html>"))
        # first POST returns results, second POST returns empty -> loop stops
        client.post = AsyncMock(side_effect=[_make_resp(_SEARCH_HTML), _make_resp(_SEARCH_HTML_EMPTY)])
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_gazzetta_ufficiale_impl(query="liquidazione")
        assert isinstance(result, SearchResult)
        assert result.success
        out = result.to_str()
        assert "Trovati 223 atti" in out
        assert "Iremit" in out

    @pytest.mark.asyncio
    async def test_no_results(self):
        client = _client_with_get(_make_resp("<html>seed</html>"))
        client.post = AsyncMock(return_value=_make_resp(_SEARCH_HTML_EMPTY))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_gazzetta_ufficiale_impl(query="inesistente")
        assert not result.success
        assert "Nessun atto" in result.to_str()

    @pytest.mark.asyncio
    async def test_query_sent_as_titolo(self):
        client = _client_with_get(_make_resp("<html>seed</html>"))
        client.post = AsyncMock(side_effect=[_make_resp(_SEARCH_HTML), _make_resp(_SEARCH_HTML_EMPTY)])
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            await _cerca_gazzetta_ufficiale_impl(query="liquidazione")
        # the POST data must carry query in the titolo field
        first_post = client.post.call_args_list[0]
        data = first_post.kwargs.get("data", {})
        assert data.get("titolo") == "liquidazione"

    @pytest.mark.asyncio
    async def test_source_down(self):
        client = _client_with_get(_make_resp("<html>seed</html>"))
        client.post = AsyncMock(side_effect=httpx.RequestError("500"))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_gazzetta_ufficiale_impl(query="x")
        assert not result.success
        assert "Errore" in result.to_str()


# ---------------------------------------------------------------------------
# _impl: leggi_atto_gazzetta (head -> menu -> articles)
# ---------------------------------------------------------------------------

class TestLeggiAttoImpl:
    @pytest.mark.asyncio
    async def test_full_text_assembled(self):
        # call order: head, menu, article1, article2
        responses = [
            _make_resp(_ELI_HEAD_HTML),
            _make_resp(_MENU_HTML),
            _make_resp(_ARTICLE_HTML),
            _make_resp(_ARTICLE_HTML),
        ]
        client = _client_with_get(responses)
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _leggi_atto_gazzetta_impl("26A02808", "2026-06-13")
        assert isinstance(result, SearchResult)
        assert result.success
        out = result.to_str()
        assert "DECRETO" in out
        assert "IL MINISTRO" in out
        assert "2026-05-22" in out  # date_document from RDFa

    @pytest.mark.asyncio
    async def test_metadata_only(self):
        client = _client_with_get([_make_resp(_ELI_HEAD_HTML)])
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _leggi_atto_gazzetta_impl("26A02808", "2026-06-13", solo_metadati=True)
        assert result.success
        out = result.to_str()
        assert "Solo metadati" in out
        # only ONE GET (the head) should have been issued
        assert client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_no_text_available(self):
        # head ok, menu has no article anchors -> empty assembled text
        responses = [_make_resp(_ELI_HEAD_HTML), _make_resp("<html><body>vuoto</body></html>")]
        client = _client_with_get(responses)
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _leggi_atto_gazzetta_impl("26A02808", "2026-06-13")
        assert not result.success
        assert "Testo non disponibile" in result.to_str()

    @pytest.mark.asyncio
    async def test_source_down(self):
        client = _client_with_get(_make_resp(""))
        client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _leggi_atto_gazzetta_impl("X", "2026-06-13")
        assert not result.success
        assert "Errore" in result.to_str()


# ---------------------------------------------------------------------------
# _impl: sommario_gazzetta
# ---------------------------------------------------------------------------

class TestSommarioImpl:
    @pytest.mark.asyncio
    async def test_returns_atti(self):
        client = _client_with_get(_make_resp(_SOMMARIO_HTML))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _sommario_gazzetta_impl("135", "2026-06-13")
        assert result.success
        out = result.to_str()
        assert "26A02924" in out
        assert "26A02808" in out

    @pytest.mark.asyncio
    async def test_empty(self):
        client = _client_with_get(_make_resp(_SOMMARIO_HTML_EMPTY))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _sommario_gazzetta_impl("999", "2026-06-13")
        assert not result.success
        assert "Nessun atto" in result.to_str()

    @pytest.mark.asyncio
    async def test_source_down(self):
        client = _client_with_get(_make_resp(""))
        client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _sommario_gazzetta_impl("135", "2026-06-13")
        assert not result.success
        assert "Errore" in result.to_str()


# ---------------------------------------------------------------------------
# _impl: scarica_pdf_gazzetta (URL only, no network)
# ---------------------------------------------------------------------------

class TestScaricaPdfImpl:
    @pytest.mark.asyncio
    async def test_returns_url(self):
        result = await _scarica_pdf_gazzetta_impl("135", "2026-06-13")
        assert result.success
        out = result.to_str()
        assert "https://www.gazzettaufficiale.it/eli/gu/2026/06/13/135/sg/pdf" in out
        assert "135" in out

    @pytest.mark.asyncio
    async def test_invalid_date(self):
        result = await _scarica_pdf_gazzetta_impl("135", "not-a-date")
        assert not result.success
        assert "Errore" in result.to_str()


# ---------------------------------------------------------------------------
# Optional live E2E (skipped by default; run with -m live)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLive:
    @pytest.mark.asyncio
    async def test_ultime_gazzette_live(self):
        result = await _ultime_gazzette_impl(max_risultati=3)
        assert result.success
        assert result.num_found > 0

    @pytest.mark.asyncio
    async def test_search_live(self):
        result = await _cerca_gazzetta_ufficiale_impl(
            titolo="liquidazione coatta", anno_da="2026", anno_a="2026", max_risultati=3
        )
        assert result.success
