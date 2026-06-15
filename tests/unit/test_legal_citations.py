"""Tests for legal citation tools — parse, resolve, cite_law, and download_law_pdf with mocked HTTP."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.legal_citations import (
    _parse_reference, _resolve_act, _build_nv, _cite_law_impl,
    _download_law_pdf_impl, _generate_pdf_from_text, _sanitize_for_pdf, _safe_filename,
    _split_citazioni, _starts_new_reference, _classify_citazione, _sentenza_num_anno,
    _normalize_sezione, _parse_resolved_estremi, _norma_misquote, _verifica_citazioni_impl,
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
# _parse_reference — extended (paragraph stripping + recitals)
# ---------------------------------------------------------------------------

class TestParseReferenceExtended:
    def test_art_with_paragraph_number(self):
        article, act = _parse_reference("art. 4 n. 11 GDPR")
        assert article == "4"
        assert act.lower() == "gdpr"

    def test_art_with_comma(self):
        article, act = _parse_reference("art. 13 co. 2 GDPR")
        assert article == "13"
        assert act.lower() == "gdpr"

    def test_art_with_comma_full(self):
        article, act = _parse_reference("art. 6 comma 1 lett. a) GDPR")
        assert article == "6"
        assert act.lower() == "gdpr"

    def test_considerando(self):
        article, act = _parse_reference("considerando 42 GDPR")
        assert article == "rec_42"
        assert act.lower() == "gdpr"

    def test_recital_english(self):
        article, act = _parse_reference("recital 47 GDPR")
        assert article == "rec_47"
        assert act.lower() == "gdpr"

    def test_standard_art_unchanged(self):
        article, act = _parse_reference("art. 2043 c.c.")
        assert article == "2043"
        assert "c.c." in act

    def test_art_with_punto(self):
        article, act = _parse_reference("art. 4 punto 11 GDPR")
        assert article == "4"
        assert act.lower() == "gdpr"

    def test_art_with_par(self):
        article, act = _parse_reference("art. 82 par. 1 GDPR")
        assert article == "82"
        assert act.lower() == "gdpr"


# ---------------------------------------------------------------------------
# _resolve_act — GDPR after paragraph stripping
# ---------------------------------------------------------------------------

class TestResolveActGDPR:
    def test_gdpr_resolves(self):
        result = _resolve_act("GDPR")
        assert result is not None
        assert str(result["numero_atto"]) == "679"


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
    async def test_cite_law_normattiva(self, monkeypatch):
        # Exercise the HTML path deterministically: disable the AKN-first branch
        # so the mocked scraper.httpx client (not akn_fetch.httpx) is used.
        monkeypatch.setenv("AKN_DISABLED", "1")
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
    async def test_normattiva_pdf_generation(self, monkeypatch):
        """Normattiva: mock full text fetch and PDF generation for codice civile."""
        # Disable the AKN-first branch so the mocked scraper.httpx client is used
        # (the AJAX full-text walker), not the unmocked akn_fetch network path.
        monkeypatch.setenv("AKN_DISABLED", "1")
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
# verifica_citazioni — input splitting & classification (pure helpers)
# ---------------------------------------------------------------------------

class TestVerificaSplit:
    def test_split_newlines(self):
        refs = _split_citazioni("art. 2043 c.c.\nart. 13 GDPR")
        assert refs == ["art. 2043 c.c.", "art. 13 GDPR"]

    def test_split_blank_lines_ignored(self):
        refs = _split_citazioni("art. 2043 c.c.\n\n  \nart. 13 GDPR\n")
        assert refs == ["art. 2043 c.c.", "art. 13 GDPR"]

    def test_split_comma_separated_list(self):
        refs = _split_citazioni("art. 2043 c.c., art. 13 GDPR")
        assert refs == ["art. 2043 c.c.", "art. 13 GDPR"]

    def test_comma_inside_sentenza_not_broken(self):
        # The comma separates section from number — must stay one reference.
        refs = _split_citazioni("Cass. sez. III, n. 12345/2024")
        assert refs == ["Cass. sez. III, n. 12345/2024"]

    def test_mixed_list_with_internal_comma(self):
        refs = _split_citazioni("Cass. sez. III, n. 12345/2024, art. 2043 c.c.")
        assert refs == ["Cass. sez. III, n. 12345/2024", "art. 2043 c.c."]

    def test_empty_input(self):
        assert _split_citazioni("") == []
        assert _split_citazioni("\n  \n") == []

    def test_starts_new_reference(self):
        assert _starts_new_reference("art. 2043 c.c.")
        assert _starts_new_reference("Cass. n. 1/2024")
        assert _starts_new_reference("considerando 42 GDPR")
        assert _starts_new_reference("12345/2024")
        assert not _starts_new_reference("n. 12345/2024")
        assert not _starts_new_reference("del 22 aprile 2024")


class TestVerificaClassify:
    def test_sentenza_full_form(self):
        assert _classify_citazione("Cass. sez. III n. 12345/2024") == "sentenza"

    def test_sentenza_bare_with_marker(self):
        assert _classify_citazione("Cass. 12345/2024") == "sentenza"

    def test_sentenza_n_del_anno(self):
        assert _classify_citazione("Cass. n. 12345 del 2024") == "sentenza"

    def test_norma(self):
        assert _classify_citazione("art. 2043 c.c.") == "norma"

    def test_norma_gdpr(self):
        assert _classify_citazione("art. 13 GDPR") == "norma"

    def test_non_interpretabile(self):
        assert _classify_citazione("una frase qualsiasi senza riferimento") == "non interpretabile"

    def test_dlgs_number_not_a_sentenza(self):
        # "D.Lgs. 196/2003" must classify as norma-ish, never as a sentenza:
        # the bare 196/2003 has no Cass. marker so the sentenza regex is skipped.
        assert _classify_citazione("art. 1 D.Lgs. 196/2003") == "norma"
        # Without article it is non-interpretabile (no Cass. marker → not sentenza).
        assert _classify_citazione("D.Lgs. 196/2003") == "non interpretabile"

    def test_sentenza_num_anno_extraction(self):
        assert _sentenza_num_anno("Cass. sez. III n. 12345/2024") == (12345, 2024)
        assert _sentenza_num_anno("Cass. 999 del 2021") == (999, 2021)
        assert _sentenza_num_anno("art. 2043 c.c.") is None
        # bare number/year without court marker → not a sentenza
        assert _sentenza_num_anno("196/2003") is None


class TestVerificaHelpers:
    def test_normalize_sezione_roman(self):
        assert _normalize_sezione("III") == "3"

    def test_normalize_sezione_unite(self):
        assert _normalize_sezione("Unite") == "SU"
        assert _normalize_sezione("U") == "SU"

    def test_normalize_sezione_lavoro(self):
        assert _normalize_sezione("Lavoro") == "L"

    def test_parse_resolved_estremi(self):
        text = "# Cass. civ., sez. III, n. 12345/2024, dep. 22/04/2024\n**Materia**: x"
        out = _parse_resolved_estremi(text)
        assert out["numero"] == 12345
        assert out["anno"] == 2024
        assert out["sezione"] == "3"

    def test_parse_resolved_estremi_ssuu(self):
        text = "# Cass. civ., sez. SS.UU., n. 500/2023, dep. 01/02/2023"
        out = _parse_resolved_estremi(text)
        assert out["numero"] == 500
        assert out["sezione"] == "SU"

    def test_norma_misquote_comma_present(self):
        # Article text with comma "2." present → no misquote.
        text = "**Fonte**: Normattiva\n1. Primo comma.\n2. Secondo comma."
        assert _norma_misquote("art. 13 co. 2 GDPR", text) is False

    def test_norma_misquote_comma_absent(self):
        text = "**Fonte**: Normattiva\n1. Unico comma presente."
        assert _norma_misquote("art. 13 co. 5 GDPR", text) is True

    def test_norma_misquote_lettera_present(self):
        text = "**Fonte**: Normattiva\nIl titolare fornisce: a) i dati; b) le finalità."
        assert _norma_misquote("art. 6 comma 1 lett. b) GDPR", text) is False

    def test_norma_misquote_no_marker(self):
        # No comma/lettera named in the reference → never a misquote.
        text = "**Fonte**: Normattiva\nTesto qualsiasi."
        assert _norma_misquote("art. 2043 c.c.", text) is False


# ---------------------------------------------------------------------------
# verifica_citazioni — end-to-end (mocked fetch_article + solr_query)
# ---------------------------------------------------------------------------

def _solr_doc(numero: int, anno: int, sez: str = "3", kind: str = "snciv") -> dict:
    return {
        "id": f"{kind}{anno}{sez}{numero}S",
        "numdec": str(numero),
        "anno": str(anno),
        "datdep": ["20240422"],
        "szdec": sez,
        "materia": ["RESPONSABILITA CIVILE"],
        "tipoprov": "Sentenza",
        "kind": kind,
        "ocr": ["Testo della sentenza " + "x" * 50],
        "ocrdis": ["P.Q.M. La Corte rigetta il ricorso."],
    }


def _solr_response(docs: list[dict]) -> dict:
    return {
        "responseHeader": {"status": 0},
        "response": {"numFound": len(docs), "start": 0, "docs": docs},
    }


def _patch_solr(response_by_call):
    """Build an AsyncMock for solr_query that returns canned responses in order.

    response_by_call: a single dict (always returned) or a list of dicts
    (returned in sequence per call).
    """
    if isinstance(response_by_call, list):
        return AsyncMock(side_effect=response_by_call)
    return AsyncMock(return_value=response_by_call)


def _fake_session():
    """A no-op async context manager standing in for SolrSession."""
    sess = MagicMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    return sess


class TestVerificaCitazioniE2E:
    @pytest.mark.asyncio
    async def test_norma_exists(self):
        async def fake_fetch_article(nv):
            return {
                "text": "Qualunque fatto doloso o colposo obbliga a risarcire il danno.",
                "url": "https://normattiva.it/art2043",
                "source": "normattiva",
            }

        with patch("src.tools.legal_citations.fetch_article", side_effect=fake_fetch_article):
            out = await _verifica_citazioni_impl("art. 2043 c.c.")
        assert "| 1 |" in out
        assert "Norma" in out
        assert "verificata" in out
        assert "esistenza" in out  # disclaimer present

    @pytest.mark.asyncio
    async def test_norma_not_found(self):
        async def fake_fetch_article(nv):
            return {"text": "", "url": "https://normattiva.it/x", "source": "", "error": "404"}

        with patch("src.tools.legal_citations.fetch_article", side_effect=fake_fetch_article):
            out = await _verifica_citazioni_impl("art. 9999 D.Lgs. 231/2001")
        assert "non trovata" in out

    @pytest.mark.asyncio
    async def test_norma_misquote_comma_absent(self):
        async def fake_fetch_article(nv):
            return {
                "text": "1. Unico comma dell'articolo.",
                "url": "https://normattiva.it/art13",
                "source": "normattiva",
            }

        with patch("src.tools.legal_citations.fetch_article", side_effect=fake_fetch_article):
            out = await _verifica_citazioni_impl("art. 13 co. 7 D.Lgs. 196/2003")
        assert "metadati discordanti" in out

    @pytest.mark.asyncio
    async def test_sentenza_exists(self):
        resp = _solr_response([_solr_doc(12345, 2024, sez="3")])
        with patch("src.tools.italgiure.solr_query", _patch_solr(resp)), \
             patch("src.tools.italgiure.SolrSession", return_value=_fake_session()):
            out = await _verifica_citazioni_impl("Cass. sez. III n. 12345/2024")
        assert "Sentenza" in out
        assert "verificata" in out

    @pytest.mark.asyncio
    async def test_sentenza_not_found(self):
        empty = _solr_response([])
        # leggi_sentenza tries up to 4 queries — all empty → no_results
        with patch("src.tools.italgiure.solr_query", _patch_solr(empty)), \
             patch("src.tools.italgiure.SolrSession", return_value=_fake_session()):
            out = await _verifica_citazioni_impl("Cass. n. 99999/2024")
        assert "inesistente" in out

    @pytest.mark.asyncio
    async def test_sentenza_pre_2020_not_verifiable(self):
        # No HTTP should be touched: the year gate short-circuits.
        out = await _verifica_citazioni_impl("Cass. n. 5000/2015")
        assert "non verificabile" in out
        assert "2020" in out
        assert "inesistente" not in out

    @pytest.mark.asyncio
    async def test_sentenza_metadata_mismatch_sezione(self):
        # User says sez. I, but resolved decision is sez. III → discordanti.
        resp = _solr_response([_solr_doc(12345, 2024, sez="3")])
        with patch("src.tools.italgiure.solr_query", _patch_solr(resp)), \
             patch("src.tools.italgiure.SolrSession", return_value=_fake_session()):
            out = await _verifica_citazioni_impl("Cass. sez. I n. 12345/2024")
        assert "metadati discordanti" in out

    @pytest.mark.asyncio
    async def test_sentenza_fallback_returns_different_decision(self):
        # The 4-step fallback can surface a DIFFERENT decision — must be inesistente.
        # First two lookups empty, then step-4 full-text returns n. 88888/2024.
        wrong = _solr_response([_solr_doc(88888, 2024, sez="3")])
        empty = _solr_response([])
        # leggi_sentenza(numero=12345): step1 empty (no sezione passed → step2 skipped),
        # step3 empty, step4 returns the wrong doc.
        with patch("src.tools.italgiure.solr_query", _patch_solr([empty, empty, wrong])), \
             patch("src.tools.italgiure.SolrSession", return_value=_fake_session()):
            out = await _verifica_citazioni_impl("Cass. n. 12345/2024")
        assert "inesistente" in out
        assert "88888" in out

    @pytest.mark.asyncio
    async def test_non_interpretabile(self):
        out = await _verifica_citazioni_impl("questo non e un riferimento valido")
        assert "Non interpretabile" in out

    @pytest.mark.asyncio
    async def test_empty_input_error(self):
        out = await _verifica_citazioni_impl("   \n  ")
        assert "Errore" in out

    @pytest.mark.asyncio
    async def test_mixed_batch_table_shape(self):
        async def fake_fetch_article(nv):
            return {
                "text": "Testo articolo.",
                "url": "https://normattiva.it/x",
                "source": "normattiva",
            }

        resp = _solr_response([_solr_doc(12345, 2024, sez="3")])
        with patch("src.tools.legal_citations.fetch_article", side_effect=fake_fetch_article), \
             patch("src.tools.italgiure.solr_query", _patch_solr(resp)), \
             patch("src.tools.italgiure.SolrSession", return_value=_fake_session()):
            out = await _verifica_citazioni_impl(
                "Cass. sez. III n. 12345/2024\nart. 2043 c.c.\nfrase non valida"
            )
        # Header + 3 data rows
        assert out.count("\n| ") >= 3
        assert "| 1 |" in out and "| 2 |" in out and "| 3 |" in out
        assert "Sentenza" in out and "Norma" in out and "Non interpretabile" in out


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
