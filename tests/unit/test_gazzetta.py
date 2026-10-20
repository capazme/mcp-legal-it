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
    ELI_SEGMENT,
    RSS_CODE,
    SERIE,
    AttoDetail,
    AttoResult,
    _build_search_data,
    _eli_atto_url,
    _menu_url,
    _parse_article_text,
    _parse_atto_header,
    _parse_detail_redirect,
    _parse_eli_metadata,
    _parse_menu_article_urls,
    _parse_menu_inline_text,
    _parse_rss,
    _parse_search_results,
    _parse_sommario,
    _search_result_count,
    _sommario_url,
    format_detail,
    format_result,
    format_sommario,
    pdf_url,
    search_atti,
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

# Sommario page, structure as served by /eli/gu/{y}/{m}/{d}/{n}/sg: fascicolo header in
# div.intestazione, section headings in span.rubrica, the issuer in span.emettitore and, per
# atto, TWO anchors (estremi + oggetto) followed by span.pagina ("Pag. N").
_SOMMARIO_HTML = """
<html><body>
<div id="elenco_hp">
  <div class="riga_t">
    <div class="colonna_ultima intestazione">
      Serie Generale
      n. <span class="estremi">135</span> del <span class="estremi">13-6-2026</span>
    </div>
  </div>
  <h2>Sommario</h2>
  <span class="rubrica"> DECRETI, DELIBERE E ORDINANZE MINISTERIALI</span>
  <span class="emettitore">MINISTERO DELLE IMPRESE E DEL MADE IN ITALY</span>
  <span class="risultato">
    <a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-06-13&atto.codiceRedazionale=26A02924&elenco30giorni=false">
      <span class="data">
        DECRETO 17 febbraio 2026
      </span>
    </a>
    <a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-06-13&atto.codiceRedazionale=26A02924&elenco30giorni=false">
      Modifica del decreto 16 gennaio 1997 concernente criteri per la
determinazione dei compensi spettanti ai commissari liquidatori. (26A02924)
      <span class="riferimento">
      </span>
      <span class="pagina">Pag. 1</span>
    </a>
  </span>
  <span class="rubrica"> ESTRATTI, SUNTI E COMUNICATI</span>
  <span class="risultato">
    <a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-06-13&atto.codiceRedazionale=26A02808&elenco30giorni=false">
      <span class="data">
        DECRETO 22 maggio 2026
      </span>
    </a>
    <a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-06-13&atto.codiceRedazionale=26A02808&elenco30giorni=false">
      Liquidazione coatta amministrativa della Multiservizi 2000 societa'
cooperativa sociale, in Supino. (26A02808)
      <span class="riferimento">
      </span>
      <span class="pagina">Pag. 2</span>
    </a>
  </span>
</div>
</body></html>
"""

# Search hit answered with the atto's own page (single result): estremi in h2.consultazione,
# oggetto + GU reference in h3.consultazione (structure of the real 22G00158 page).
_DETAIL_PAGE_HTML = """
<html><body>
<div id="testa_atto">
  <h2 class="consultazione">
    DECRETO LEGISLATIVO <span>
      10 ottobre 2022, n. 149&nbsp;
    </span>
  </h2>
  <h3 class="consultazione" style="border: none;">
    <span about="gu:id/2022/10/17/22G00158/sg/ita" property="eli:title">Attuazione della legge 26 novembre 2021, n. 206,  recante  delega  al
 Governo per l'efficienza del <strong><FONT COLOR=#370AED>processo</FONT></strong> <strong><FONT COLOR=#370AED>civile</FONT></strong>. (22G00158)
 </span>
    <span class="riferimento">
      <span class="link_gazzetta">
        <a target="_blank" href="https://www.gazzettaufficiale.it/eli/gu/2022/10/17/243/so/38/sg/pdf">(GU Serie Generale n.243 del 17-10-2022 - Suppl. Ordinario n. 38)</a>
      </span>
    </span>
  </h3>
</div>
</body></html>
"""
_DETAIL_URL = (
    "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario"
    "?atto.dataPubblicazioneGazzetta=2022-10-17&atto.codiceRedazionale=22G00158"
    "&isAnonimo=false&tipoSerie=serie_generale&tipoVigenza=originario&normativi=false&currentPage=1"
)

# 1a Serie speciale atto page: no RDFa, header without a type/date meta; the oggetto is the
# text of h3.consultazione (with the "(codice)") and 1<sup>a</sup> sits in the GU reference.
_ELI_S1_HTML = """
<html><body>
<div id="testa_atto">
  <h2 class="consultazione">
    N. 230
    ORDINANZA (Atto di promovimento)
    4 agosto 2025
  </h2>
  <h3 class="consultazione" style="border:none;">Ripubblicazione dell'ordinanza del 4 agosto  2025  del  Tribunale  di
 Verona nel procedimento <strong><FONT COLOR=#370AED>civile</FONT></strong> promosso da R. V. M.. 
 (26C00185)
    <span class="riferimento">
      <span class="link_gazzetta">
        <a target="_blank" href="https://www.gazzettaufficiale.it/eli/gu/2026/09/23/38/s1/pdf">(GU 1<sup>a</sup> Serie Speciale - Corte Costituzionale  n.38 del 23-9-2026)</a>
      </span>
    </span>
  </h3>
</div>
</body></html>
"""

# vediMenuHTML of a special-series atto: no caricaArticolo links, the whole text is inline in
# div.stampami (<pre>).
_MENU_INLINE_HTML = """
<html><body class="stampa">
<div id="testa_atto_preview">
  <p class="grassetto">N. 230 ORDINANZA (Atto di promovimento) 4 agosto 2025</p>
  <pre>Ripubblicazione dell'ordinanza del 4 agosto 2025 del Tribunale di Verona.</pre>
</div>
<div class="stampami">
  <div class="wrapper_pre">
    <PRE>
                    TRIBUNALE ORDINARIO DI VERONA
                       Seconda sezione civile
    Il Collegio ha pronunciato la seguente ordinanza ex art. 23, legge 11 marzo
1953, n. 87;
    </PRE>
  </div>
</div>
<script>var x = 1;</script>
</body></html>
"""

# RSS of the 1a Serie speciale (links keep the series segment "S1") and of the 2a Serie
# speciale, whose items link to the paginated PDF and carry the code as "(26CE2412)".
_RSS_S1_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>Gazzetta Ufficiale - 1a Serie Speciale - Corte Costituzionale - Sommario</title>
    <item>
      <title>n. 230 ORDINANZA (Atto di promovimento) 4 agosto 2025</title>
      <link>http://www.gazzettaufficiale.it/eli/id/2026/09/23/26C00185/S1</link>
      <content:encoded>Ripubblicazione dell'ordinanza del 4 agosto  2025  del  Tribunale  di
Verona nel procedimento civile promosso da R. V. M.. 
 
.........(26C00185)</content:encoded>
      <pubDate>Sun, 03 Aug 2025 22:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

_RSS_S2_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>Gazzetta Ufficiale - 2a Serie Speciale - Unione Europea - Sommario</title>
    <item>
      <title>DECISIONE 11 maggio 2026, n. 1510</title>
      <link>http://www.gazzettaufficiale.it/do/gazzetta/unione_europea/3/pdfPaginato?numPagina=1062&amp;dataPubblicazioneGazzetta=20260928&amp;numeroGazzetta=76&amp;tipoSerie=S2&amp;tipoSupplemento=GU&amp;numeroSupplemento=0&amp;edizione=0&amp;elenco30giorni=false</link>
      <content:encoded>Decisione (UE) 2026/1510 del Consiglio, dell'11 maggio 2026, relativa
alla firma dell'accordo di partenariato strategico. 
(26CE2413)</content:encoded>
      <pubDate>Sun, 27 Sep 2026 22:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Item without a readable code</title>
      <link>http://www.gazzettaufficiale.it/do/gazzetta/unione_europea/3/pdfPaginato?numPagina=1&amp;dataPubblicazioneGazzetta=20260928</link>
      <content:encoded>Nessun codice qui.</content:encoded>
    </item>
  </channel>
</rss>
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
        # the ELI segment of the atto's own series (serie_generale -> sg)
        assert res[0].eli_url.endswith("/eli/id/2026/05/22/26A02532/sg")

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
        # the fascicolo header (series, number, date), not the generic "Sommario" h2
        assert heading == "Serie Generale n. 135 del 13-6-2026"
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
        assert out.endswith(
            "*[Testo troncato a 25000 caratteri su 30000 totali: "
            "per leggere il seguito ripetere la chiamata con da_carattere=25001]*"
        )

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
        # Official numbering, from the channel titles of /rss/{code} (read 2026-09-29):
        # SG Serie Generale, S1 1a Corte Costituzionale, S2 2a Unione Europea, S3 3a Regioni,
        # S4 4a Concorsi ed esami, S5 5a Contratti Pubblici, P2 Parte Seconda.
        assert RSS_CODE == {
            "serie_generale": "SG",
            "corte_costituzionale": "S1",
            "unione_europea": "S2",
            "regioni": "S3",
            "concorsi": "S4",
            "contratti": "S5",
            "parte_seconda": "P2",
        }

    def test_resolve_serie_path_known(self):
        assert _resolve_serie_path("Corte Costituzionale") == "corte_costituzionale"

    def test_resolve_serie_path_unknown_defaults(self):
        assert _resolve_serie_path("inesistente") == "serie_generale"

    def test_resolve_rss_code_known(self):
        assert _resolve_rss_code("unione_europea") == "S2"
        assert _resolve_rss_code("Corte Costituzionale") == "S1"

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
# Corrections from the benchmark (source: www.gazzettaufficiale.it, read 2026-09-25/29)
# ---------------------------------------------------------------------------

class TestSeriesSegments:
    """ELI path segment of each series: /eli/id/... and /eli/gu/... answer only for it."""

    def test_eli_segment_map(self):
        # same numbering as the RSS feeds (sg, s1 Corte costituzionale, s2 UE, s3 Regioni,
        # s4 Concorsi, s5 Contratti, p2 Parte seconda)
        assert ELI_SEGMENT == {
            "serie_generale": "sg",
            "corte_costituzionale": "s1",
            "unione_europea": "s2",
            "regioni": "s3",
            "concorsi": "s4",
            "contratti": "s5",
            "parte_seconda": "p2",
        }

    def test_eli_atto_url_special_series(self):
        # 26C00185 is a 1a Serie speciale atto: /eli/id/2026/09/23/26C00185/s1 holds it, /sg does not
        assert _eli_atto_url("2026-09-23", "26C00185", "corte_costituzionale") == (
            "https://www.gazzettaufficiale.it/eli/id/2026/09/23/26C00185/s1"
        )

    def test_sommario_url_special_series(self):
        assert _sommario_url("2026-02-06", "10", "concorsi") == (
            "https://www.gazzettaufficiale.it/eli/gu/2026/02/06/10/s4"
        )

    def test_pdf_url_special_series(self):
        # 4a Serie speciale Concorsi n. 10 del 6-2-2026: .../s4/pdf is the PDF, .../sg/pdf redirects
        # to "pdf non trovato"
        assert pdf_url("2026-02-06", "10", "concorsi") == (
            "https://www.gazzettaufficiale.it/eli/gu/2026/02/06/10/s4/pdf"
        )

    def test_pdf_url_defaults_to_serie_generale(self):
        assert pdf_url("2018-09-04", "205").endswith("/2018/09/04/205/sg/pdf")

    def test_malformed_date_is_a_value_error(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            _eli_atto_url("17/10/2022", "22G00158")
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            _sommario_url("04/09/2018", "205")

    def test_search_result_link_uses_the_series_of_the_hit(self):
        html = _SEARCH_HTML.replace("/atto/serie_generale/", "/atto/concorsi/")
        assert _parse_search_results(html)[0].eli_url.endswith("/eli/id/2026/05/22/26A02532/s4")


def _results_page(codici):
    """A results page of the given codes (structure of the real result list)."""
    spans = "".join(
        f'<span class="risultato">'
        f'<a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-05-22&atto.codiceRedazionale={c}"><span class="data">DECRETO</span></a>'
        f'<a href="/atto/serie_generale/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=2026-05-22&atto.codiceRedazionale={c}">Oggetto {c}. ({c})</a>'
        f'</span>'
        for c in codici
    )
    return f'<html><body><div class="risultati_ricerca">{spans}</div></body></html>'


class TestSearchPaginationAndRedirect:
    @pytest.mark.asyncio
    async def test_pages_are_numbered_from_one(self):
        # /originario/0 and /originario/1 are the same page: starting at 0 lists every atto twice
        client = _client_with_get(_make_resp("<html>seed</html>"))
        client.post = AsyncMock(return_value=_make_resp(_SEARCH_HTML))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            total, docs = await search_atti("serie_generale", titolo="liquidazione")
        assert client.post.call_args_list[0].args[0].endswith("/do/ricerca/atto/serie_generale/originario/1")
        # a short page (< 100 results) is the last one: no second request, no duplicates
        assert client.post.call_count == 1
        assert [d.codice_redazionale for d in docs] == ["26A02532", "26A00412"]
        assert total == 223

    @pytest.mark.asyncio
    async def test_duplicates_across_pages_are_dropped(self):
        # a full page (100 raw results, two of them repeated) leaves 98 distinct atti: the loop
        # reads /originario/2, whose first entry repeats one already seen (the site does this at
        # the page boundary, checked on 2026-09-29) and must be counted once
        codici = [f"26A{n:05d}" for n in range(98)]
        first = _results_page(codici + codici[:2])
        second = _results_page(["26A00097", "26A00098", "26A00099", "26A00100"])
        client = _client_with_get(_make_resp("<html>seed</html>"))
        client.post = AsyncMock(side_effect=[_make_resp(first), _make_resp(second)])
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            total, docs = await search_atti("serie_generale", titolo="x", rows=100)
        assert client.post.call_count == 2
        assert client.post.call_args_list[0].args[0].endswith("/originario/1")
        assert client.post.call_args_list[1].args[0].endswith("/originario/2")
        got = [d.codice_redazionale for d in docs]
        assert len(got) == len(set(got)) == 100
        assert got[-1] == "26A00099"

    @pytest.mark.asyncio
    async def test_single_hit_redirect_to_the_atto_page(self):
        # the search answers a query with exactly one hit with the atto's own page
        client = _client_with_get(_make_resp("<html>seed</html>"))
        redirected = _make_resp(_DETAIL_PAGE_HTML)
        redirected.url = _DETAIL_URL
        client.post = AsyncMock(return_value=redirected)
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_gazzetta_ufficiale_impl(
                titolo="processo civile", tipo_provvedimento="DECRETO LEGISLATIVO",
                anno_da="2022", anno_a="2022",
            )
        assert result.success
        out = result.to_str()
        assert "Trovati 1 atti" in out
        assert "22G00158" in out
        assert "DECRETO LEGISLATIVO 10 ottobre 2022, n. 149" in out
        assert "Attuazione della legge 26 novembre 2021, n. 206" in out
        assert "GU Serie Generale n.243 del 17-10-2022 - Suppl. Ordinario n. 38" in out
        assert "2022-10-17" in out
        assert "/eli/id/2022/10/17/22G00158/sg" in out
        assert client.post.call_count == 1

    def test_parse_detail_redirect_takes_the_series_from_the_url(self):
        url = _DETAIL_URL.replace("/atto/serie_generale/", "/atto/corte_costituzionale/")
        atto = _parse_detail_redirect(_ELI_S1_HTML, url)[0]
        assert atto.eli_url.endswith("/eli/id/2022/10/17/22G00158/s1")

    def test_parse_detail_redirect_without_ids_is_empty(self):
        assert _parse_detail_redirect(_DETAIL_PAGE_HTML, "https://www.gazzettaufficiale.it/x") == []

    def test_count_of_long_result_lists(self):
        # long lists print "Sono stati trovati N atti", short ones "Risultati della ricerca: N atti"
        html = "<span>Sono stati trovati 715 atti.(&Eacute; possibile visualizzare solo i primi 500 atti)</span>"
        assert _search_result_count(html) == 715


class TestAttoHeader:
    def test_estremi_oggetto_riferimento(self):
        estremi, oggetto, riferimento = _parse_atto_header(_DETAIL_PAGE_HTML)
        assert estremi == "DECRETO LEGISLATIVO 10 ottobre 2022, n. 149"
        assert oggetto.startswith("Attuazione della legge 26 novembre 2021, n. 206, recante delega al Governo")
        assert oggetto.endswith("processo civile.")  # the "(22G00158)" marker is stripped
        assert riferimento == "(GU Serie Generale n.243 del 17-10-2022 - Suppl. Ordinario n. 38)"

    def test_special_series_header(self):
        estremi, oggetto, riferimento = _parse_atto_header(_ELI_S1_HTML)
        assert estremi == "N. 230 ORDINANZA (Atto di promovimento) 4 agosto 2025"
        assert oggetto == (
            "Ripubblicazione dell'ordinanza del 4 agosto 2025 del Tribunale di "
            "Verona nel procedimento civile promosso da R. V. M.."
        )
        assert riferimento == "(GU 1a Serie Speciale - Corte Costituzionale n.38 del 23-9-2026)"

    def test_format_detail_reports_the_oggetto(self):
        estremi, oggetto, riferimento = _parse_atto_header(_DETAIL_PAGE_HTML)
        d = AttoDetail(
            codice_redazionale="22G00158", data_pubblicazione="2022-10-17",
            serie="serie_generale", estremi=estremi, title=oggetto, riferimento=riferimento,
            metadata_only=True,
        )
        out = format_detail(d)
        assert out.startswith("# DECRETO LEGISLATIVO 10 ottobre 2022, n. 149")
        assert "**Oggetto**: Attuazione della legge 26 novembre 2021, n. 206" in out
        assert "**Riferimento**: (GU Serie Generale n.243" in out


class TestMenuInlineText:
    def test_reads_the_stampami_block(self):
        text = _parse_menu_inline_text(_MENU_INLINE_HTML)
        assert "TRIBUNALE ORDINARIO DI VERONA" in text
        assert "ex art. 23, legge 11 marzo" in text
        assert "var x" not in text
        # the preview above the text is not part of it
        assert "Ripubblicazione" not in text

    def test_without_stampami_returns_empty(self):
        assert _parse_menu_inline_text("<html><body>vuoto</body></html>") == ""


class TestSommarioStructure:
    def test_keeps_estremi_oggetto_and_issuer(self):
        _, atti = _parse_sommario(_SOMMARIO_HTML)
        first = atti[0]
        assert first.tipo == "DECRETO 17 febbraio 2026"
        assert first.emettitore == "MINISTERO DELLE IMPRESE E DEL MADE IN ITALY"
        assert first.title == (
            "Modifica del decreto 16 gennaio 1997 concernente criteri per la "
            "determinazione dei compensi spettanti ai commissari liquidatori."
        )
        # "Pag. N" is not part of the oggetto
        assert "Pag." not in first.title

    def test_section_heading_resets_the_issuer(self):
        # the second atto sits under a new rubrica with no issuer of its own
        _, atti = _parse_sommario(_SOMMARIO_HTML)
        assert atti[1].emettitore == ""

    def test_special_series_heading(self):
        html = _SOMMARIO_HTML.replace(
            "Serie Generale\n", "4<sup>a</sup> Serie Speciale - Concorsi ed Esami\n"
        )
        heading, _ = _parse_sommario(html)
        assert heading == "4a Serie Speciale - Concorsi ed Esami n. 135 del 13-6-2026"

    def test_format_sommario_lists_oggetto(self):
        heading, atti = _parse_sommario(_SOMMARIO_HTML)
        out = format_sommario(heading, atti)
        assert out.startswith("# Serie Generale n. 135 del 13-6-2026")
        assert "**Atti**: 2" in out
        assert "- **26A02924** — DECRETO 17 febbraio 2026 (MINISTERO DELLE IMPRESE E DEL MADE IN ITALY): Modifica del decreto" in out


class TestRssSeries:
    def test_special_series_link_keeps_its_segment(self):
        # the feed link is the permalink: rebuilding it with /SG opens a page without the atto
        a = _parse_rss(_RSS_S1_XML)[0]
        assert a.codice_redazionale == "26C00185"
        assert a.data_pubblicazione == "2026-09-23"
        assert a.eli_url == "https://www.gazzettaufficiale.it/eli/id/2026/09/23/26C00185/S1"
        assert a.tipo == "n. 230 ORDINANZA (Atto di promovimento) 4 agosto 2025"
        # filler dots of the truncated feed text are not printed as content
        assert not a.title.rstrip().endswith("....")

    def test_unione_europea_items_link_to_the_paginated_pdf(self):
        # 2a Serie speciale: no /eli/id/ link; code from "(26CE2413)", date from the link
        res = _parse_rss(_RSS_S2_XML)
        assert [a.codice_redazionale for a in res] == ["26CE2413"]  # the item without a code is skipped
        assert res[0].data_pubblicazione == "2026-09-28"
        assert "pdfPaginato" in res[0].eli_url
        assert res[0].title.startswith("Decisione (UE) 2026/1510 del Consiglio")
        assert "(26CE2413)" not in res[0].title

    @pytest.mark.asyncio
    async def test_ultime_corte_costituzionale_reads_the_s1_feed(self):
        client = _client_with_get(_make_resp(_RSS_S1_XML))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _ultime_gazzette_impl(serie="corte_costituzionale")
        assert result.success
        assert client.get.call_args_list[0].args[0].endswith("/rss/S1")
        assert "26C00185" in result.to_str()

    @pytest.mark.asyncio
    async def test_ultime_regioni_reads_the_s3_feed(self):
        client = _client_with_get(_make_resp(_RSS_S1_XML))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            await _ultime_gazzette_impl(serie="regioni")
        assert client.get.call_args_list[0].args[0].endswith("/rss/S3")


class TestSpecialSeriesTools:
    @pytest.mark.asyncio
    async def test_leggi_special_series_atto_reads_the_inline_text(self):
        # head (/s1) -> menu (no article links, text in div.stampami)
        client = _client_with_get([_make_resp(_ELI_S1_HTML), _make_resp(_MENU_INLINE_HTML)])
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _leggi_atto_gazzetta_impl(
                "26C00185", "2026-09-23", serie="corte_costituzionale",
            )
        assert result.success, result.to_str()
        out = result.to_str()
        assert client.get.call_args_list[0].args[0].endswith("/eli/id/2026/09/23/26C00185/s1")
        assert "tipoSerie=corte_costituzionale" in client.get.call_args_list[1].args[0]
        assert "# N. 230 ORDINANZA (Atto di promovimento) 4 agosto 2025" in out
        assert "**Oggetto**: Ripubblicazione dell'ordinanza" in out
        assert "TRIBUNALE ORDINARIO DI VERONA" in out

    @pytest.mark.asyncio
    async def test_leggi_unione_europea_has_no_atto_page(self):
        # the ELI permalink of a 2a Serie speciale atto answers HTTP 500: no request is made
        client = _client_with_get(_make_resp(""))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _leggi_atto_gazzetta_impl("26CE2412", "2026-09-28", serie="unione_europea")
        assert not result.success
        assert result.error_type == "no_results"
        assert "scarica_pdf_gazzetta" in result.to_str()
        assert client.get.call_count == 0

    @pytest.mark.asyncio
    async def test_leggi_bad_date_is_bad_input(self):
        result = await _leggi_atto_gazzetta_impl("22G00158", "17/10/2022")
        assert not result.success
        assert result.error_type == "bad_input"
        assert "data non valida" in result.to_str().lower()
        assert "non raggiungibile" not in result.to_str()

    @pytest.mark.asyncio
    async def test_sommario_special_series_requests_its_own_page(self):
        client = _client_with_get(_make_resp(_SOMMARIO_HTML))
        with patch("src.lib.gazzetta.client.httpx.AsyncClient", return_value=client):
            result = await _sommario_gazzetta_impl("10", "2026-02-06", serie="concorsi")
        assert result.success
        assert client.get.call_args_list[0].args[0] == "https://www.gazzettaufficiale.it/eli/gu/2026/02/06/10/s4"

    @pytest.mark.asyncio
    async def test_pdf_special_series_url(self):
        result = await _scarica_pdf_gazzetta_impl("10", "2026-02-06", serie="concorsi")
        assert result.success
        assert "https://www.gazzettaufficiale.it/eli/gu/2026/02/06/10/s4/pdf" in result.to_str()
        assert "/sg/pdf" not in result.to_str()

    @pytest.mark.asyncio
    async def test_pdf_bad_date_is_bad_input_not_source_down(self):
        result = await _scarica_pdf_gazzetta_impl("205", "04/09/2018")
        assert not result.success
        assert result.error_type == "bad_input"
        out = result.to_str()
        assert "data non valida" in out.lower()
        assert "non raggiungibile" not in out


# ---------------------------------------------------------------------------
# Paged reading (da_carattere)
# ---------------------------------------------------------------------------

def _long_detail(n: int = 60000) -> AttoDetail:
    # position-coded text: character i (1-based) is a letter that tells its 25k block
    text = "".join(chr(ord("a") + (i // 1000) % 26) for i in range(n))
    return AttoDetail(
        codice_redazionale="X", data_pubblicazione="2026-06-13",
        serie="serie_generale", title="Atto lungo", text=text,
    )


class TestPagedReading:
    def test_default_cut_note_says_where_to_resume(self):
        out = format_detail(_long_detail())
        assert "*[Testo troncato a 25000 caratteri su 60000 totali: " in out
        assert out.endswith("ripetere la chiamata con da_carattere=25001]*")

    def test_da_carattere_starts_at_the_first_omitted_character(self):
        d = _long_detail()
        out = format_detail(d, da_carattere=25001)
        body, _, note = out.partition("\n\n---\n")
        assert body.endswith(d.text[25000:50000])
        assert not body.endswith(d.text[24999:49999])
        assert note == (
            "*[Caratteri 25001-50000 su 60000 totali: "
            "per leggere il seguito ripetere la chiamata con da_carattere=50001]*"
        )
        assert "# Atto lungo" in out  # header kept

    def test_last_window_says_end_of_text(self):
        d = _long_detail()
        out = format_detail(d, da_carattere=50001)
        assert out.endswith(d.text[50000:] + "\n\n---\n*[Caratteri 50001-60000 su 60000 totali: fine del testo]*")

    def test_start_beyond_the_end(self):
        out = format_detail(_long_detail(100), da_carattere=500)
        assert "oltre la fine del testo (100 caratteri)" in out

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [0, -3, "7", 1.5, None, True])
    async def test_invalid_da_carattere_errors_without_network(self, bad):
        with patch("src.tools.gazzetta.fetch_atto", new=AsyncMock()) as fetch:
            result = await _leggi_atto_gazzetta_impl("X", "2026-06-13", da_carattere=bad)
        assert not result.success
        assert result.error_type == "bad_input"
        assert "da_carattere deve essere un intero maggiore o uguale a 1" in result.to_str()
        fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_impl_threads_da_carattere(self):
        d = _long_detail()
        with patch("src.tools.gazzetta.fetch_atto", new=AsyncMock(return_value=d)):
            result = await _leggi_atto_gazzetta_impl("X", "2026-06-13", da_carattere=25001)
        assert result.success
        assert "Caratteri 25001-50000 su 60000 totali" in result.to_str()

    @pytest.mark.asyncio
    async def test_mcp_tool_accepts_da_carattere(self):
        from src.tools.gazzetta import leggi_atto_gazzetta

        fn = getattr(leggi_atto_gazzetta, "fn", leggi_atto_gazzetta)
        d = _long_detail()
        with patch("src.tools.gazzetta.fetch_atto", new=AsyncMock(return_value=d)):
            out = await fn("X", "2026-06-13", da_carattere=50001)
        assert "fine del testo" in out
        assert "da_carattere" in (fn.__doc__ or "")


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
