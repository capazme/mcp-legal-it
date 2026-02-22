"""Tests for legal citation tools — parse, resolve, cite_law, and download_law_pdf with mocked HTTP."""

import os
import pytest
from unittest.mock import AsyncMock, patch

from src.tools.legal_citations import (
    _parse_reference, _resolve_act, _build_nv, _cite_law_impl,
    _download_law_pdf_impl, _generate_pdf_from_text, _sanitize_for_pdf, _safe_filename,
)
from src.lib.visualex.models import Norma, NormaVisitata
from src.lib.visualex.map import resolve_atto, normalize_act_type, find_brocardi_url


# ---------------------------------------------------------------------------
# _parse_reference
# ---------------------------------------------------------------------------

class TestParseReference:
    def test_standard_format(self):
        article, act = _parse_reference("art. 13 GDPR")
        assert article == "13"
        assert act == "GDPR"

    def test_no_dot(self):
        article, act = _parse_reference("art 13 GDPR")
        assert article == "13"
        assert act == "GDPR"

    def test_uppercase(self):
        article, act = _parse_reference("ART 117 Costituzione")
        assert article == "117"
        assert act == "Costituzione"

    def test_extension_bis(self):
        article, act = _parse_reference("art. 2-ter D.Lgs. 196/2003")
        assert article == "2-ter"
        assert act == "D.Lgs. 196/2003"

    def test_codice_civile(self):
        article, act = _parse_reference("art. 2043 c.c.")
        assert article == "2043"
        assert act == "c.c."

    def test_multi_word_act(self):
        article, act = _parse_reference("art. 6 D.Lgs. 231/2001")
        assert article == "6"
        assert act == "D.Lgs. 231/2001"

    def test_no_article_prefix(self):
        article, act = _parse_reference("GDPR")
        assert article == ""
        assert act == "GDPR"

    def test_article_with_slash(self):
        article, act = _parse_reference("art. 4/1 GDPR")
        assert article == "4/1"
        assert act == "GDPR"


# ---------------------------------------------------------------------------
# _resolve_act
# ---------------------------------------------------------------------------

class TestResolveAct:
    def test_gdpr(self):
        result = _resolve_act("GDPR")
        assert result is not None
        assert result["tipo_atto"] == "regolamento ue"
        assert result["numero_atto"] == "679"

    def test_gdpr_lowercase(self):
        result = _resolve_act("gdpr")
        assert result is not None
        assert result["tipo_atto"] == "regolamento ue"

    def test_codice_civile_abbreviation(self):
        result = _resolve_act("c.c.")
        assert result is not None
        assert result["tipo_atto"] == "codice civile"

    def test_codice_penale(self):
        result = _resolve_act("c.p.")
        assert result is not None
        assert result["tipo_atto"] == "codice penale"

    def test_costituzione(self):
        result = _resolve_act("Costituzione")
        assert result is not None
        assert result["tipo_atto"] == "costituzione"

    def test_dlgs_pattern(self):
        result = _resolve_act("D.Lgs. 196/2003")
        assert result is not None
        assert result["tipo_atto"] == "decreto legislativo"
        assert result["numero_atto"] == "196"
        assert result["data"] == "2003-06-30"  # full date from ATTI_NOTI (more precise than year-only pattern)

    def test_legge_pattern(self):
        result = _resolve_act("L. 241/1990")
        assert result is not None
        assert result["tipo_atto"] == "legge"
        assert result["numero_atto"] == "241"
        assert result["data"] == "1990"

    def test_dora(self):
        result = _resolve_act("DORA")
        assert result is not None
        assert result["tipo_atto"] == "regolamento ue"
        assert result["numero_atto"] == "2554"

    def test_ai_act(self):
        result = _resolve_act("AI Act")
        assert result is not None
        assert result["tipo_atto"] == "regolamento ue"

    def test_unknown_act(self):
        result = _resolve_act("unknown_fantasy_law_12345")
        assert result is None


# ---------------------------------------------------------------------------
# Norma / NormaVisitata URL generation
# ---------------------------------------------------------------------------

class TestModels:
    def test_norma_codice_civile_url(self):
        norma = Norma(tipo_atto="codice civile")
        url = norma.url(article="2043")
        # codice civile = allegato 2 of R.D. 262/1942 → must include :2 before ~art
        assert "262:2~art2043" in url

    def test_norma_codice_penale_url(self):
        norma = Norma(tipo_atto="codice penale")
        url = norma.url(article="110")
        # codice penale = allegato 1 of R.D. 1398/1930 → must include :1 before ~art
        assert "1398:1~art110" in url

    def test_norma_eurlex_url(self):
        norma = Norma(tipo_atto="regolamento ue", data="2016", numero_atto="679")
        url = norma.url()
        assert "eur-lex.europa.eu" in url
        assert "679" in url

    def test_norma_decreto_legislativo_url(self):
        norma = Norma(tipo_atto="decreto legislativo", data="2003", numero_atto="196")
        url = norma.url(article="13")
        assert "normattiva.it" in url
        assert "~art13" in url

    def test_norma_costituzione_url(self):
        norma = Norma(tipo_atto="costituzione")
        url = norma.url(article="117")
        assert "normattiva.it" in url
        assert "costituzione" in url
        assert "~art117" in url

    def test_normavisitata_str(self):
        norma = Norma(tipo_atto="codice civile")
        nv = NormaVisitata(norma=norma, numero_articolo="2043")
        assert "art. 2043" in str(nv)

    def test_norma_article_with_extension(self):
        norma = Norma(tipo_atto="decreto legislativo", data="2003", numero_atto="196")
        url = norma.url(article="2-ter")
        assert "~art2ter" in url


# ---------------------------------------------------------------------------
# Map functions
# ---------------------------------------------------------------------------

class TestMapFunctions:
    def test_normalize_act_type_dlgs(self):
        assert normalize_act_type("d.lgs.") == "decreto legislativo"

    def test_normalize_act_type_cc(self):
        assert normalize_act_type("c.c.") == "codice civile"

    def test_normalize_unknown(self):
        assert normalize_act_type("something_unknown") == "something_unknown"

    def test_resolve_atto_gdpr(self):
        result = resolve_atto("GDPR")
        assert result is not None
        assert result["tipo_atto"] == "regolamento ue"

    def test_resolve_atto_codice_civile(self):
        result = resolve_atto("codice civile")
        assert result is not None

    def test_find_brocardi_url_codice_civile(self):
        url = find_brocardi_url("codice civile")
        assert url is not None
        assert "brocardi.it" in url

    def test_find_brocardi_url_costituzione(self):
        url = find_brocardi_url("costituzione")
        assert url is not None
        assert "brocardi.it" in url

    def test_find_brocardi_url_unknown(self):
        url = find_brocardi_url("fantasy_law_xyz")
        assert url is None


# ---------------------------------------------------------------------------
# cite_law end-to-end (mocked HTTP)
# ---------------------------------------------------------------------------

class TestCiteLaw:
    @pytest.mark.asyncio
    async def test_cite_law_normattiva(self):
        mock_html = """
        <html><body>
        <div class="bodyTesto">
            <h2 class="article-num-akn">Art. 2043</h2>
            <div class="article-heading-akn">Risarcimento per fatto illecito</div>
            <div class="art-comma-div-akn">
                Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto,
                obbliga colui che ha commesso il fatto a risarcire il danno.
            </div>
        </div>
        </body></html>
        """
        with patch("src.lib.visualex.scraper.httpx.AsyncClient") as MockClient:
            mock_response = AsyncMock()
            mock_response.text = mock_html
            mock_response.raise_for_status = lambda: None

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await _cite_law_impl("art. 2043 c.c.")
            assert "Risarcimento" in result or "2043" in result
            assert "normattiva" in result.lower() or "Fonte" in result

    @pytest.mark.asyncio
    async def test_cite_law_eurlex(self):
        mock_html = """
        <html><body>
        <p class="ti-art">Articolo 13</p>
        <p>Informazioni da fornire qualora i dati personali siano raccolti presso l'interessato</p>
        <p>1. In caso di raccolta presso l'interessato di dati che lo riguardano, il titolare del trattamento fornisce...</p>
        </body></html>
        """
        with patch("src.lib.visualex.scraper.httpx.AsyncClient") as MockClient:
            mock_response = AsyncMock()
            mock_response.text = mock_html
            mock_response.raise_for_status = lambda: None

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await _cite_law_impl("art. 13 GDPR")
            assert "13" in result
            assert "eurlex" in result.lower() or "Fonte" in result

    @pytest.mark.asyncio
    async def test_cite_law_unknown_act(self):
        result = await _cite_law_impl("art. 1 LeggeInesistente12345")
        assert "Errore" in result or "non riconosciuto" in result

    @pytest.mark.asyncio
    async def test_cite_law_bad_format(self):
        result = await _cite_law_impl("")
        # Should handle gracefully
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# fetch_law_article routing
# ---------------------------------------------------------------------------

class TestFetchLawArticle:
    @pytest.mark.asyncio
    async def test_normattiva_routing(self):
        """Verify that codice civile routes to Normattiva."""
        norma = Norma(tipo_atto="codice civile")
        nv = NormaVisitata(norma=norma, numero_articolo="1")
        assert "normattiva.it" in nv.url()

    @pytest.mark.asyncio
    async def test_eurlex_routing(self):
        """Verify that regolamento ue routes to EUR-Lex."""
        norma = Norma(tipo_atto="regolamento ue", data="2016", numero_atto="679")
        nv = NormaVisitata(norma=norma, numero_articolo="13")
        assert "eur-lex.europa.eu" in nv.url()

    @pytest.mark.asyncio
    async def test_costituzione_routing(self):
        """Verify that costituzione routes to Normattiva."""
        norma = Norma(tipo_atto="costituzione")
        nv = NormaVisitata(norma=norma, numero_articolo="1")
        assert "normattiva.it" in nv.url()
        assert "costituzione" in nv.url()


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

class TestPdfHelpers:
    def test_sanitize_for_pdf_replaces_smart_quotes(self):
        text = "\u201cHello\u201d \u2018world\u2019"
        result = _sanitize_for_pdf(text)
        assert '"' in result
        assert "'" in result
        assert "\u201c" not in result

    def test_sanitize_for_pdf_replaces_dashes(self):
        text = "art. 1\u2013bis\u2014nota"
        result = _sanitize_for_pdf(text)
        assert "\u2013" not in result
        assert "\u2014" not in result

    def test_safe_filename(self):
        assert _safe_filename("D.Lgs. 196/2003") == "D.Lgs._196-2003"
        assert _safe_filename("codice civile") == "codice_civile"
        assert _safe_filename("GDPR") == "GDPR"

    def test_generate_pdf_creates_file(self, tmp_path):
        output = str(tmp_path / "test.pdf")
        _generate_pdf_from_text("Test Title", "Test body text content here.", "https://example.com", output)
        assert os.path.exists(output)
        with open(output, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_generate_pdf_handles_italian_chars(self, tmp_path):
        output = str(tmp_path / "test_it.pdf")
        text = "L'articolo prevede che il titolare debba comunicare all'interessato le finalità del trattamento."
        _generate_pdf_from_text("Art. 13 — Informativa", text, "https://normattiva.it", output)
        assert os.path.exists(output)
        assert os.path.getsize(output) > 100


# ---------------------------------------------------------------------------
# download_law_pdf end-to-end (mocked HTTP)
# ---------------------------------------------------------------------------

class TestDownloadLawPdf:
    @pytest.mark.asyncio
    async def test_eurlex_pdf_download(self):
        """EUR-Lex: mock PDF download for GDPR."""
        fake_pdf = b"%PDF-1.4 fake pdf content for testing purposes"
        with patch("src.lib.visualex.scraper.httpx.AsyncClient") as MockClient:
            mock_response = AsyncMock()
            mock_response.content = fake_pdf
            mock_response.raise_for_status = lambda: None
            mock_response.headers = {"content-type": "application/pdf"}

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await _download_law_pdf_impl("GDPR")
            assert "PDF scaricato" in result
            assert "EUR-Lex" in result
            assert "GDPR" in result

    @pytest.mark.asyncio
    async def test_normattiva_pdf_generation(self):
        """Normattiva: mock full text fetch and PDF generation for codice civile."""
        mock_act_html = """
        <html><body>
        <a href="/esporta/attoCompleto?atto.dataPubblicazioneGazzetta=1942-04-04&amp;atto.codiceRedazionale=042U0262">Esporta</a>
        <div class="bodyTesto">
            <h1>Codice Civile</h1>
            <p>Testo del codice civile completo per test.</p>
        </div>
        </body></html>
        """
        mock_export_html = """
        <html><body>
        <h1>REGIO DECRETO 16 marzo 1942, n. 262</h1>
        <div class="bodyTesto">
            <p>Approvazione del testo del Codice civile.</p>
            <p>Art. 1. Capacita giuridica. La capacita giuridica si acquista dal momento della nascita.</p>
            <p>Art. 2. Maggiore eta. La maggiore eta e fissata al compimento del diciottesimo anno.</p>
        </div>
        </body></html>
        """
        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = AsyncMock()
            resp.raise_for_status = lambda: None
            if call_count == 1:
                resp.text = mock_act_html
            else:
                resp.text = mock_export_html
            return resp

        with patch("src.lib.visualex.scraper.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = mock_get
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await _download_law_pdf_impl("codice civile")
            assert "PDF generato" in result
            assert "Normattiva" in result
            assert ".pdf" in result

    @pytest.mark.asyncio
    async def test_unknown_act_returns_error(self):
        result = await _download_law_pdf_impl("LeggeInesistente12345")
        assert "Errore" in result
        assert "non riconosciuto" in result

    @pytest.mark.asyncio
    async def test_empty_reference_returns_error(self):
        result = await _download_law_pdf_impl("")
        assert "Errore" in result

    @pytest.mark.asyncio
    async def test_reference_with_article_ignores_article(self):
        """'art. 13 GDPR' should still download the full GDPR PDF."""
        fake_pdf = b"%PDF-1.4 fake pdf content"
        with patch("src.lib.visualex.scraper.httpx.AsyncClient") as MockClient:
            mock_response = AsyncMock()
            mock_response.content = fake_pdf
            mock_response.raise_for_status = lambda: None
            mock_response.headers = {"content-type": "application/pdf"}

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await _download_law_pdf_impl("art. 13 GDPR")
            assert "PDF scaricato" in result
            assert "EUR-Lex" in result


# ---------------------------------------------------------------------------
# Live tests (optional, marked with @pytest.mark.live)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLive:
    @pytest.mark.asyncio
    async def test_normattiva_live(self):
        """Live test: fetch art. 2043 c.c. from Normattiva."""
        result = await _cite_law_impl("art. 2043 c.c.")
        assert "danno" in result.lower() or "risarcimento" in result.lower()

    @pytest.mark.asyncio
    async def test_eurlex_live(self):
        """Live test: fetch art. 13 GDPR from EUR-Lex."""
        result = await _cite_law_impl("art. 13 GDPR")
        assert "interessato" in result.lower() or "titolare" in result.lower()

    @pytest.mark.asyncio
    async def test_brocardi_live(self):
        """Live test: fetch Brocardi annotations for art. 2043 c.c."""
        result = await _cite_law_impl("art. 2043 c.c.", include_annotations=True)
        assert "brocardi" in result.lower() or "Annotazioni" in result

    @pytest.mark.asyncio
    async def test_download_eurlex_pdf_live(self):
        """Live test: download GDPR PDF from EUR-Lex."""
        result = await _download_law_pdf_impl("GDPR")
        assert "PDF scaricato" in result or "PDF" in result

    @pytest.mark.asyncio
    async def test_download_normattiva_pdf_live(self):
        """Live test: generate PDF for codice civile from Normattiva."""
        result = await _download_law_pdf_impl("codice civile")
        assert "PDF generato" in result or "PDF" in result
