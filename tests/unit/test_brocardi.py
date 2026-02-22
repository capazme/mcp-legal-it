"""Tests for the standalone Brocardi scraper and cerca_brocardi tool."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bs4 import BeautifulSoup

from src.lib.brocardi.client import (
    BrocardiResult,
    Massima,
    Relazione,
    parse_massime_references,
    _clean_text,
    _extract_position,
    _parse_single_massima,
    _extract_brocardi_adagi,
    _extract_ratio,
    _extract_spiegazione,
    _extract_massime,
    _extract_footnotes,
    _extract_cross_references,
    _extract_related_articles,
    find_article_url,
    fetch_brocardi,
)
from src.tools.legal_citations import _cerca_brocardi_impl


# ---------------------------------------------------------------------------
# Massima dataclass
# ---------------------------------------------------------------------------

class TestMassima:
    def test_estremi_complete(self):
        m = Massima(autorita="Cass. civ.", numero="12345", anno="2024", testo="Testo.")
        assert m.estremi == "Cass. civ. n. 12345/2024"

    def test_estremi_incomplete(self):
        m = Massima(autorita="Cass.", testo="Testo senza numero.")
        assert m.estremi is None

    def test_is_cassazione_true(self):
        m = Massima(autorita="Cass. civ. sez. III", numero="1", anno="2024", testo="T")
        assert m.is_cassazione is True

    def test_is_cassazione_false(self):
        m = Massima(autorita="Trib. Milano", numero="1", anno="2024", testo="T")
        assert m.is_cassazione is False

    def test_is_cassazione_none(self):
        m = Massima(testo="T")
        assert m.is_cassazione is False


# ---------------------------------------------------------------------------
# BrocardiResult
# ---------------------------------------------------------------------------

class TestBrocardiResult:
    def test_cassazione_references(self):
        result = BrocardiResult(
            massime=[
                Massima(autorita="Cass. civ.", numero="100", anno="2024", testo="A"),
                Massima(autorita="Trib. Roma", numero="200", anno="2023", testo="B"),
                Massima(autorita="Cass. pen.", numero="300", anno="2022", testo="C"),
            ]
        )
        refs = result.cassazione_references
        assert len(refs) == 2
        assert refs[0].numero == "100"
        assert refs[1].numero == "300"

    def test_to_markdown_error(self):
        result = BrocardiResult(error="Not found")
        md = result.to_markdown()
        assert "Errore" in md
        assert "Not found" in md

    def test_to_markdown_full(self):
        result = BrocardiResult(
            url="https://www.brocardi.it/codice-civile/art2043.html",
            position="Codice Civile > Libro IV > Art. 2043",
            ratio="La norma tutela il danneggiato.",
            spiegazione="L'art. 2043 disciplina il risarcimento.",
            brocardi=["Neminem laedere"],
            massime=[
                Massima(autorita="Cass. civ.", numero="12345", anno="2024", testo="Massima test.")
            ],
            relazioni=[
                Relazione(
                    tipo="codice_civile",
                    titolo="Relazione al Codice Civile (1942)",
                    testo="Il legislatore ha inteso...",
                )
            ],
            footnotes=[{"numero": 1, "testo": "Nota test."}],
        )
        md = result.to_markdown()
        assert "brocardi.it" in md
        assert "Ratio Legis" in md
        assert "Spiegazione" in md
        assert "Neminem laedere" in md
        assert "12345/2024" in md
        assert "Massima test" in md
        assert "Relazione al Codice Civile" in md
        assert "Nota test" in md

    def test_to_markdown_empty(self):
        result = BrocardiResult(url="https://example.com")
        md = result.to_markdown()
        assert "example.com" in md
        assert "Ratio" not in md


# ---------------------------------------------------------------------------
# parse_massime_references
# ---------------------------------------------------------------------------

class TestParseMassimeReferences:
    def test_extracts_cassazione_only(self):
        massime = [
            Massima(autorita="Cass. civ.", numero="100", anno="2024", testo="A"),
            Massima(autorita="Trib. Milano", numero="200", anno="2023", testo="B"),
            Massima(autorita="Cass. pen.", numero="300", anno="2022", testo="C"),
        ]
        refs = parse_massime_references(massime)
        assert len(refs) == 2
        assert refs[0] == {"autorita": "Cass. civ.", "numero": 100, "anno": 2024}
        assert refs[1] == {"autorita": "Cass. pen.", "numero": 300, "anno": 2022}

    def test_deduplicates(self):
        massime = [
            Massima(autorita="Cass. civ.", numero="100", anno="2024", testo="A"),
            Massima(autorita="Cass. civ.", numero="100", anno="2024", testo="B"),
        ]
        refs = parse_massime_references(massime)
        assert len(refs) == 1

    def test_empty_list(self):
        assert parse_massime_references([]) == []

    def test_no_cassazione(self):
        massime = [
            Massima(autorita="Trib. Milano", numero="1", anno="2024", testo="A"),
        ]
        assert parse_massime_references(massime) == []


# ---------------------------------------------------------------------------
# Internal extraction helpers
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_collapses_whitespace(self):
        assert _clean_text("  hello   world  ") == "hello world"

    def test_fixes_missing_space_after_tag(self):
        assert ">" not in _clean_text(">word") or "> word" in _clean_text(">word")

    def test_empty(self):
        assert _clean_text("") == ""
        assert _clean_text(None) == ""


class TestExtractPosition:
    def test_extracts_breadcrumb(self):
        html = '<div id="breadcrumb">Brocardi.it > Codice Civile > Libro IV > Art. 2043</div>'
        soup = BeautifulSoup(html, "lxml")
        assert "Codice Civile" in _extract_position(soup)
        assert "Brocardi.it" not in _extract_position(soup)

    def test_no_breadcrumb(self):
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        assert _extract_position(soup) == ""


class TestParseSingleMassima:
    def test_structured_cassazione(self):
        html = '<div class="sentenza"><strong>Cass. civ. n. 12345/2024</strong> Il danno va risarcito.</div>'
        tag = BeautifulSoup(html, "lxml").find("div", class_="sentenza")
        m = _parse_single_massima(tag)
        assert m is not None
        assert m.autorita == "Cass. civ."
        assert m.numero == "12345"
        assert m.anno == "2024"
        assert "danno" in m.testo

    def test_tribunale(self):
        html = '<div class="sentenza"><strong>Trib. Milano n. 500/2023</strong> Testo massima.</div>'
        tag = BeautifulSoup(html, "lxml").find("div", class_="sentenza")
        m = _parse_single_massima(tag)
        assert m is not None
        assert "Trib" in m.autorita
        assert m.numero == "500"
        assert m.anno == "2023"

    def test_no_header(self):
        html = '<div class="sentenza">Solo testo senza header.</div>'
        tag = BeautifulSoup(html, "lxml").find("div", class_="sentenza")
        m = _parse_single_massima(tag)
        assert m is not None
        assert m.testo == "Solo testo senza header."
        assert m.autorita is None

    def test_empty_div(self):
        html = '<div class="sentenza"></div>'
        tag = BeautifulSoup(html, "lxml").find("div", class_="sentenza")
        m = _parse_single_massima(tag)
        assert m is None


class TestExtractBrocardiAdagi:
    def test_extracts_adagi(self):
        html = """
        <div class="panes-condensed panes-w-ads content-ext-guide content-mark">
            <div class="brocardi-content">Neminem laedere</div>
            <div class="brocardi-content">Pacta sunt servanda</div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        corpo = soup.find("div", class_="panes-condensed")
        result = BrocardiResult()
        _extract_brocardi_adagi(corpo, result)
        assert len(result.brocardi) == 2
        assert "Neminem laedere" in result.brocardi[0]


class TestExtractRatio:
    def test_extracts_ratio(self):
        html = """
        <div class="panes-condensed panes-w-ads content-ext-guide content-mark">
            <div class="container-ratio">
                <div class="corpoDelTesto">La ratio dell'art. 2043 è tutelare il danneggiato.</div>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        corpo = soup.find("div", class_="panes-condensed")
        result = BrocardiResult()
        _extract_ratio(corpo, result)
        assert "ratio" in result.ratio.lower() or "tutelare" in result.ratio.lower()


class TestExtractSpiegazione:
    def test_extracts_spiegazione(self):
        html = """
        <div class="panes-condensed panes-w-ads content-ext-guide content-mark">
            <h3>Spiegazione dell'art. 2043</h3>
            <div class="text">L'articolo disciplina la responsabilità aquiliana.</div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        corpo = soup.find("div", class_="panes-condensed")
        result = BrocardiResult()
        _extract_spiegazione(corpo, result)
        assert "responsabilità" in result.spiegazione or "aquiliana" in result.spiegazione


class TestExtractMassime:
    def test_extracts_multiple_massime(self):
        html = """
        <div class="panes-condensed panes-w-ads content-ext-guide content-mark">
            <h3>Massime relative all'art. 2043</h3>
            <div class="text">
                <div class="sentenza"><strong>Cass. civ. n. 100/2024</strong> Prima massima.</div>
                <div class="sentenza"><strong>Cass. pen. n. 200/2023</strong> Seconda massima.</div>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        corpo = soup.find("div", class_="panes-condensed")
        result = BrocardiResult()
        _extract_massime(corpo, result)
        assert len(result.massime) == 2
        assert result.massime[0].numero == "100"
        assert result.massime[1].numero == "200"

    def test_no_massime_header(self):
        html = """
        <div class="panes-condensed panes-w-ads content-ext-guide content-mark">
            <h3>Altro contenuto</h3>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        corpo = soup.find("div", class_="panes-condensed")
        result = BrocardiResult()
        _extract_massime(corpo, result)
        assert len(result.massime) == 0


class TestExtractCrossReferences:
    def test_extracts_cross_refs(self):
        html = """
        <div class="panes-condensed panes-w-ads content-ext-guide content-mark">
            <div class="text">
                Vedi anche <a href="/codice-civile/art2059.html">art. 2059</a> e
                <a href="/codice-penale/art575.html">art. 575 c.p.</a>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        corpo = soup.find("div", class_="panes-condensed")
        result = BrocardiResult()
        _extract_cross_references(corpo, result)
        assert len(result.cross_references) == 2
        assert result.cross_references[0]["articolo"] == "2059"
        assert result.cross_references[0]["tipo_atto"] == "Codice Civile"
        assert result.cross_references[1]["tipo_atto"] == "Codice Penale"


class TestExtractRelatedArticles:
    def test_extracts_prev_next(self):
        html = """
        <html><body>
            <a href="/codice-civile/art2042.html" title="Art. 2042">Precedente</a>
            <a href="/codice-civile/art2044.html" title="Art. 2044">Successivo</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = BrocardiResult()
        _extract_related_articles(soup, result)
        assert "previous" in result.related_articles
        assert result.related_articles["previous"]["numero"] == "2042"
        assert "next" in result.related_articles
        assert result.related_articles["next"]["numero"] == "2044"


# ---------------------------------------------------------------------------
# find_article_url (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFindArticleUrl:
    @pytest.mark.asyncio
    async def test_direct_match(self):
        mock_resp = AsyncMock()
        mock_resp.text = '<a href="/codice-civile/art2043.html">Art. 2043</a>'
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        url = await find_article_url(mock_client, "https://www.brocardi.it/codice-civile/", "2043")
        assert url is not None
        assert "art2043.html" in url

    @pytest.mark.asyncio
    async def test_not_found(self):
        mock_resp = AsyncMock()
        mock_resp.text = "<html><body>No articles here</body></html>"
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        # Clear cache to avoid interference
        from src.lib.brocardi.client import _url_cache
        _url_cache.clear()

        url = await find_article_url(mock_client, "https://www.brocardi.it/test/", "9999")
        assert url is None


# ---------------------------------------------------------------------------
# fetch_brocardi (mocked HTTP)
# ---------------------------------------------------------------------------

_BROCARDI_HTML = """
<html>
<body>
<div id="breadcrumb">Brocardi.it > Codice Civile > Libro IV > Art. 2043</div>
<div class="panes-condensed panes-w-ads content-ext-guide content-mark">
    <div class="brocardi-content">Neminem laedere</div>
    <div class="container-ratio">
        <div class="corpoDelTesto">La norma tutela chi subisce un danno ingiusto.</div>
    </div>
    <h3>Spiegazione dell'art. 2043</h3>
    <div class="text">L'art. 2043 c.c. disciplina la responsabilità extracontrattuale.</div>
    <h3>Massime relative all'art. 2043</h3>
    <div class="text">
        <div class="sentenza"><strong>Cass. civ. n. 100/2024</strong> Il danno deve essere provato.</div>
        <div class="sentenza"><strong>Cass. civ. n. 200/2023</strong> La colpa è elemento essenziale.</div>
    </div>
</div>
</body>
</html>
"""


def _mock_httpx_brocardi(index_html: str, article_html: str):
    """Create a patched httpx.AsyncClient that serves index then article page."""
    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = AsyncMock()
        resp.raise_for_status = MagicMock()
        if call_count == 1:
            resp.text = index_html
        else:
            resp.text = article_html
        return resp

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestFetchBrocardi:
    @pytest.mark.asyncio
    async def test_unknown_act(self):
        result = await fetch_brocardi("legge_inesistente_xyz", "1")
        assert result.error
        assert "mapping" in result.error.lower() or "Nessun" in result.error

    @pytest.mark.asyncio
    async def test_empty_article(self):
        result = await fetch_brocardi("codice civile", "")
        assert result.error
        assert "articolo" in result.error.lower()

    @pytest.mark.asyncio
    async def test_success(self):
        index_html = '<a href="/codice-civile/art2043.html">Art. 2043</a>'

        # Clear URL cache
        from src.lib.brocardi.client import _url_cache
        _url_cache.clear()

        with patch("src.lib.brocardi.client.httpx.AsyncClient") as MockClient:
            MockClient.return_value = _mock_httpx_brocardi(index_html, _BROCARDI_HTML)

            result = await fetch_brocardi("codice civile", "2043")

            assert not result.error
            assert "art2043" in result.url
            assert "Codice Civile" in result.position
            assert len(result.brocardi) >= 1
            assert "Neminem laedere" in result.brocardi[0]
            assert "tutela" in result.ratio or "danno" in result.ratio
            assert "responsabilità" in result.spiegazione or "extracontrattuale" in result.spiegazione
            assert len(result.massime) == 2
            assert result.massime[0].numero == "100"
            assert result.massime[0].is_cassazione

    @pytest.mark.asyncio
    async def test_article_not_found(self):
        index_html = "<html><body>No articles</body></html>"

        from src.lib.brocardi.client import _url_cache
        _url_cache.clear()

        with patch("src.lib.brocardi.client.httpx.AsyncClient") as MockClient:
            MockClient.return_value = _mock_httpx_brocardi(index_html, "")

            result = await fetch_brocardi("codice civile", "9999")

            assert result.error
            assert "non trovato" in result.error.lower()


# ---------------------------------------------------------------------------
# cerca_brocardi tool (mocked HTTP)
# ---------------------------------------------------------------------------

class TestCercaBrocardiImpl:
    @pytest.mark.asyncio
    async def test_no_article(self):
        result = await _cerca_brocardi_impl("GDPR")
        assert "Errore" in result
        assert "articolo" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_act(self):
        result = await _cerca_brocardi_impl("art. 1 LeggeFantasia12345")
        assert "Errore" in result
        assert "non riconosciuto" in result

    @pytest.mark.asyncio
    async def test_success_with_cassazione_refs(self):
        index_html = '<a href="/codice-civile/art2043.html">Art. 2043</a>'

        from src.lib.brocardi.client import _url_cache
        _url_cache.clear()

        with patch("src.lib.brocardi.client.httpx.AsyncClient") as MockClient:
            MockClient.return_value = _mock_httpx_brocardi(index_html, _BROCARDI_HTML)

            result = await _cerca_brocardi_impl("art. 2043 c.c.")

            assert "Ratio Legis" in result
            assert "Spiegazione" in result
            assert "Neminem laedere" in result
            assert "Riferimenti Cassazione" in result
            assert "leggi_sentenza" in result
            assert "100/2024" in result
            assert "200/2023" in result

    @pytest.mark.asyncio
    async def test_empty_reference(self):
        result = await _cerca_brocardi_impl("")
        assert "Errore" in result


# ---------------------------------------------------------------------------
# Live tests (optional)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestBrocardiLive:
    @pytest.mark.asyncio
    async def test_fetch_art_2043_cc(self):
        result = await fetch_brocardi("codice civile", "2043")
        assert not result.error
        assert result.url
        assert result.position
        # Should have at least some content
        assert result.ratio or result.spiegazione or result.massime

    @pytest.mark.asyncio
    async def test_cerca_brocardi_art_2043(self):
        result = await _cerca_brocardi_impl("art. 2043 c.c.")
        assert "Errore" not in result
        assert "brocardi.it" in result.lower()
