"""Regression tests for the norm-retrieval tools of src/tools/legal_citations.py (benchmark phase 3).

Each test pins a value checked by hand against the primary source on 2026-09-29, with mocked
HTTP (fixtures copied from the real markup: no network). The live counterparts are in
tests/unit/test_legal_citations_live.py.

Sources: Regulation (EU) 2016/679, recitals 1 and 42, Italian text on CELLAR (div#rct_N);
Legge 7 ottobre 1969 n. 742 on Normattiva (eli:date_document, eli:title, AKN export);
Brocardi.it pages; Italgiure (Corte di cassazione) index.
"""

import json
from pathlib import Path

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib.visualex import akn_fetch, scraper
from src.lib.visualex.models import Norma, NormaVisitata
from src.lib.visualex.scraper import (
    _eurlex_urls,
    _extract_eurlex_article,
    act_display_title,
    act_page_metadata,
    with_full_date,
)
from src.tools import legal_citations as lc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "akn"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fake httpx client (routes: substring of the URL -> body, first match wins)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, body, url="", status_code=200):
        self.text = body if isinstance(body, str) else body.decode("latin-1")
        self.content = body if isinstance(body, bytes) else body.encode("utf-8")
        self.status_code = status_code
        self.url = url
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("error", request=None, response=None)


class _Client:
    def __init__(self, routes, calls, **kwargs):
        self._routes, self._calls, self._headers = routes, calls, kwargs.get("headers", {})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        self._calls.append((url, {**self._headers, **kwargs.get("headers", {})}))
        for needle, body in self._routes.items():
            if needle in url:
                return _Resp(body, url=url)
        return _Resp("", url=url, status_code=404)


def _install(monkeypatch, routes: dict) -> list:
    """Patch httpx.AsyncClient in the scraper module (and akn_fetch); return the call log."""
    calls: list = []

    def factory(*args, **kwargs):
        return _Client(routes, calls, **kwargs)

    monkeypatch.setattr(scraper.httpx, "AsyncClient", factory)
    monkeypatch.setattr(akn_fetch.httpx, "AsyncClient", factory)
    return calls


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    akn_fetch.clear_akn_cache(disk=True)
    yield
    akn_fetch.clear_akn_cache(disk=True)


# ---------------------------------------------------------------------------
# cite_law: recitals (Reg. UE 2016/679, considerando 42 and 1)
# ---------------------------------------------------------------------------

# Copied from the CELLAR XHTML of Reg. (UE) 2016/679 (Italian expression): a recital is a
# two-cell table row, the number in the first cell and the text in the second.
_RCT_42 = (
    '<div class="eli-subdivision" id="rct_42"><table border="0" cellpadding="0" cellspacing="0" width="100%">'
    '<col width="4%"/><col width="96%"/><tbody><tr>'
    '<td valign="top"><p class="oj-normal">(42)</p></td>'
    '<td valign="top"><p class="oj-normal">Per i trattamenti basati sul consenso dell\'interessato, il titolare '
    "del trattamento dovrebbe essere in grado di dimostrare che l'interessato ha acconsentito al trattamento. "
    "In conformità della direttiva 93/13/CEE del Consiglio "
    '<a href="#ntr10-L_2016119IT.01000101-E0010" id="ntc10-L_2016119IT.01000101-E0010">'
    '(<span class="oj-super oj-note-tag">10</span>)</a> è opportuno prevedere una dichiarazione di consenso '
    "predisposta dal titolare del trattamento. Il consenso non dovrebbe essere considerato liberamente espresso "
    "se l'interessato non è in grado di operare una scelta autenticamente libera o è nell'impossibilità di "
    "rifiutare o revocare il consenso senza subire pregiudizio.</p></td></tr></tbody></table></div>"
)
_RCT_1 = (
    '<div class="eli-subdivision" id="rct_1"><table border="0" cellpadding="0" cellspacing="0" width="100%">'
    '<col width="4%"/><col width="96%"/><tbody><tr>'
    '<td valign="top"><p class="oj-normal">(1)</p></td>'
    '<td valign="top"><p class="oj-normal">La protezione delle persone fisiche con riguardo al trattamento dei '
    "dati di carattere personale è un diritto fondamentale.</p></td></tr></tbody></table></div>"
)
_CELLAR_DOC = f"<html><body>{_RCT_1}{_RCT_42}</body></html>"


class TestRecitals:
    def test_recital_returns_number_and_text(self):
        # Reg. (UE) 2016/679, considerando 42: the tool used to return only "(42)".
        text = _extract_eurlex_article(_CELLAR_DOC, "rec_42")
        assert text.startswith("(42) Per i trattamenti basati sul consenso dell'interessato")
        assert text != "(42)"
        assert text.endswith("senza subire pregiudizio.")
        # The OJ footnote call keeps its own spaces: "Consiglio (10) è", not "Consiglio(10)è".
        assert "direttiva 93/13/CEE del Consiglio (10) è opportuno" in text

    def test_recital_one_is_complete(self):
        # Reg. (UE) 2016/679, considerando 1 (verified on CELLAR 2026-09-29).
        assert _extract_eurlex_article(_CELLAR_DOC, "rec_1") == (
            "(1) La protezione delle persone fisiche con riguardo al trattamento dei dati di "
            "carattere personale è un diritto fondamentale."
        )

    def test_recital_without_div_id_takes_the_whole_row(self):
        html = (
            "<html><body><table><tr><td><p>(7)</p></td>"
            "<td><p>Testo del considerando sette.</p></td></tr></table></body></html>"
        )
        assert _extract_eurlex_article(html, "rec_7") == "(7) Testo del considerando sette."

    def test_recital_missing(self):
        assert "non trovato" in _extract_eurlex_article(_CELLAR_DOC, "rec_999")

    @pytest.mark.asyncio
    async def test_cite_law_considerando_end_to_end(self, monkeypatch):
        _install(monkeypatch, {"publications.europa.eu": _CELLAR_DOC})
        out = await lc._cite_law_impl("considerando 42 GDPR")
        assert "(42) Per i trattamenti basati sul consenso" in out
        # The reader is shown the quotable EUR-Lex page, not the CELLAR expression URL.
        assert "**Fonte**: Eurlex — https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679" in out


class TestEurlexCitableUrl:
    def test_regulation_display_url_is_the_eurlex_page(self):
        fetch_url, display_url = _eurlex_urls(Norma(tipo_atto="regolamento ue", data="2016", numero_atto="679"))
        assert fetch_url == "https://publications.europa.eu/resource/celex/32016R0679"
        assert display_url == "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679"


# ---------------------------------------------------------------------------
# cite_law / fetch_full_act: act cited with the year only (L. 7 ottobre 1969 n. 742)
# ---------------------------------------------------------------------------

_LANDING_742 = _load("landing_legge_742_1969.html")
_ART1_HTML = (
    '<html><body><div class="bodyTesto"><h2 class="article-num-akn">Art. 1</h2>'
    '<div class="art-comma-div-akn">Il decorso dei termini processuali è sospeso di diritto dal 1º al 31 '
    "agosto di ciascun anno.</div></div></body></html>"
)


class TestYearOnlyActDate:
    def test_page_metadata_reads_the_acts_own_identity(self):
        # Normattiva page of L. 7 ottobre 1969 n. 742 (GU 6 novembre 1969, 069U0742).
        meta = act_page_metadata(_LANDING_742)
        assert meta["date"] == "1969-10-07"
        assert meta["heading"] == "LEGGE 7 ottobre 1969, n. 742"
        assert meta["title"] == "Sospensione dei termini processuali nel periodo feriale"
        assert act_display_title(meta) == (
            "LEGGE 7 ottobre 1969, n. 742 - Sospensione dei termini processuali nel periodo feriale"
        )

    @pytest.mark.asyncio
    async def test_with_full_date_replaces_the_placeholder_date(self, monkeypatch):
        _install(monkeypatch, {"1969-01-01;742": _LANDING_742})
        norma = await with_full_date(Norma(tipo_atto="legge", data="1969", numero_atto="742"))
        assert norma.data == "1969-10-07"
        assert norma.url() == "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1969-10-07;742"

    @pytest.mark.asyncio
    async def test_with_full_date_leaves_complete_dates_and_codici_alone(self, monkeypatch):
        calls = _install(monkeypatch, {})
        full = Norma(tipo_atto="legge", data="1969-10-07", numero_atto="742")
        assert await with_full_date(full) is full
        codice = Norma(tipo_atto="codice civile")
        assert await with_full_date(codice) is codice
        assert calls == []  # no network for either

    @pytest.mark.asyncio
    async def test_with_full_date_never_accepts_a_date_of_another_year(self, monkeypatch):
        wrong_year = _LANDING_742.replace('content="1969-10-07"', 'content="1970-10-07"')
        _install(monkeypatch, {"1969-01-01;742": wrong_year})
        norma = Norma(tipo_atto="legge", data="1969", numero_atto="742")
        assert await with_full_date(norma) is norma

    @pytest.mark.asyncio
    async def test_cite_law_json_urn_carries_the_real_date(self, monkeypatch):
        # art. 1 L. 742/1969: the URN is urn:nir:stato:legge:1969-10-07;742~art1 (legge 7 ottobre 1969),
        # not the 1969-01-01 placeholder built from the bare year.
        monkeypatch.setenv("AKN_DISABLED", "1")
        _install(monkeypatch, {"1969-10-07;742~art1": _ART1_HTML, "1969-01-01;742": _LANDING_742})
        payload = json.loads(await lc._cite_law_impl("art. 1 L. 742/1969", formato="json"))
        assert payload["errore"] is None
        assert payload["urn"] == "urn:nir:stato:legge:1969-10-07;742~art1"
        assert payload["url"].endswith("urn:nir:stato:legge:1969-10-07;742~art1")
        assert payload["atto"]["data"] == "1969-10-07"
        assert "1969-10-07" in payload["atto"]["descrizione"]
        assert "sospeso di diritto dal 1º al 31 agosto" in payload["testo"]

    @pytest.mark.asyncio
    async def test_cite_law_json_urn_is_null_when_the_date_cannot_be_read(self, monkeypatch):
        # The landing page is unreachable: the URL still works but its date is a placeholder,
        # so no URN is presented as the act's own.
        monkeypatch.setenv("AKN_DISABLED", "1")
        _install(monkeypatch, {"~art1": _ART1_HTML})
        payload = json.loads(await lc._cite_law_impl("art. 1 L. 742/1969", formato="json"))
        assert payload["testo"]
        assert payload["urn"] is None
        assert payload["atto"]["data"] == "1969"

    @pytest.mark.asyncio
    async def test_cite_law_full_date_citation_keeps_its_urn(self, monkeypatch):
        monkeypatch.setenv("AKN_DISABLED", "1")
        calls = _install(monkeypatch, {"1969-10-07;742~art1": _ART1_HTML})
        payload = json.loads(await lc._cite_law_impl("art. 1 legge 7 ottobre 1969, n. 742", formato="json"))
        assert payload["urn"] == "urn:nir:stato:legge:1969-10-07;742~art1"
        assert len(calls) == 1  # only the article: no identity lookup for a complete date


# ---------------------------------------------------------------------------
# fetch_full_act / download_law_pdf: short acts and the act's title (L. 742/1969)
# ---------------------------------------------------------------------------


class TestShortActFullText:
    @pytest.mark.asyncio
    async def test_akn_export_of_a_short_act_is_accepted(self, monkeypatch):
        # The real AKN export of L. 742/1969 is 24,555 bytes: below the old 40,000-byte floor,
        # it was discarded and the HTML walker took over.
        xml = _load("legge_742_1969.xml")
        assert len(xml) < 40000
        _install(monkeypatch, {"caricaAKN": xml, "uri-res": _LANDING_742})
        act = await akn_fetch.fetch_act_akn(
            Norma(tipo_atto="legge", data="1969-10-07", numero_atto="742"), data_vigenza="20260929"
        )
        assert act is not None
        assert act.order == ["1", "2", "2-bis", "3", "4", "5", "6"]
        assert "sospeso di diritto dal 1º al 31 agosto di ciascun anno" in act.article("1")

    @pytest.mark.asyncio
    async def test_error_page_still_rejected_by_structure(self, monkeypatch):
        xhtml_error = '<?xml version="1.0"?><html><body>' + ("x" * 30000) + "</body></html>"
        _install(monkeypatch, {"caricaAKN": xhtml_error, "uri-res": _LANDING_742})
        act = await akn_fetch.fetch_act_akn(
            Norma(tipo_atto="legge", data="1969-10-07", numero_atto="742"), data_vigenza="20260929"
        )
        assert act is None

    @pytest.mark.asyncio
    async def test_full_act_title_is_the_acts_not_the_portal_banner(self, monkeypatch):
        # L. 7 ottobre 1969 n. 742: "LEGGE 7 ottobre 1969, n. 742 - Sospensione dei termini processuali
        # nel periodo feriale" (Normattiva <title> + eli:title); never "Normattiva - Il portale della
        # legge vigente", the sr-only <h1> of the page.
        _install(monkeypatch, {"caricaAKN": _load("legge_742_1969.xml"), "uri-res": _LANDING_742})
        out = await lc._fetch_full_act_impl("L. 742/1969")
        first = out.splitlines()[0]
        assert first == (
            "# LEGGE 7 ottobre 1969, n. 742 - Sospensione dei termini processuali nel periodo feriale"
        )
        assert "urn:nir:stato:legge:1969-10-07;742" in out
        assert "sospeso di diritto dal 1º al 31 agosto di ciascun anno" in out

    @pytest.mark.asyncio
    async def test_html_fallback_title_skips_the_sr_only_banner(self, monkeypatch):
        monkeypatch.setenv("AKN_DISABLED", "1")
        _install(monkeypatch, {"uri-res": _LANDING_742})
        result = await scraper.fetch_normattiva_full_text(
            Norma(tipo_atto="legge", data="1969", numero_atto="742")
        )
        assert result["title"] == (
            "LEGGE 7 ottobre 1969, n. 742 - Sospensione dei termini processuali nel periodo feriale"
        )
        assert result["url"].endswith("urn:nir:stato:legge:1969-10-07;742")

    def test_page_title_falls_back_to_the_page_title_without_metadata(self):
        from bs4 import BeautifulSoup

        html = (
            '<html><head><title>DECRETO LEGISLATIVO 8 giugno 2001, n. 231 - Normattiva</title></head>'
            '<body><h1 class="sr-only">Normattiva - Il portale della legge vigente</h1></body></html>'
        )
        assert scraper._normattiva_page_title(html, BeautifulSoup(html, "lxml")) == (
            "DECRETO LEGISLATIVO 8 giugno 2001, n. 231"
        )


# ---------------------------------------------------------------------------
# download_law_pdf: EU acts come from CELLAR (EUR-Lex answers the WAF challenge)
# ---------------------------------------------------------------------------

_FAKE_PDF = b"%PDF-1.4 official italian text of the regulation"


class _PdfClient(_Client):
    """CELLAR serves a PDF only for the listed Accept flavours; EUR-Lex answers 202 (WAF)."""

    served_flavours: tuple = ("application/pdf;type=pdfa1a",)

    async def get(self, url, **kwargs):
        headers = {**self._headers, **kwargs.get("headers", {})}
        self._calls.append((url, headers))
        if "publications.europa.eu/resource/celex/" in url:
            if headers.get("Accept") in self.served_flavours:
                return _Resp(_FAKE_PDF, url=url)
            return _Resp("", url=url, status_code=404)
        if "eur-lex.europa.eu" in url:
            return _Resp(b"", url=url, status_code=202)  # WAF challenge: empty body
        return _Resp("", url=url, status_code=404)


def _install_pdf(monkeypatch, flavours) -> list:
    calls: list = []
    klass = type("PdfClient", (_PdfClient,), {"served_flavours": flavours})
    monkeypatch.setattr(scraper.httpx, "AsyncClient", lambda *a, **k: klass({}, calls, **k))
    return calls


class TestEurlexPdfFromCellar:
    @pytest.mark.asyncio
    async def test_gdpr_pdf_is_requested_from_cellar_by_content_negotiation(self, monkeypatch):
        # Reg. (UE) 2016/679 = CELEX 32016R0679. CELLAR serves the Italian PDF of the OJ edition for
        # "Accept: application/pdf;type=pdfa1a" + "Accept-Language: ita" (200, %PDF-1.4, ~1 MB).
        calls = _install_pdf(monkeypatch, ("application/pdf;type=pdfa1a",))
        pdf = await scraper.download_eurlex_pdf(
            Norma(tipo_atto="regolamento ue", data="2016", numero_atto="679")
        )
        assert pdf == _FAKE_PDF
        assert len(calls) == 1  # first flavour accepted: no EUR-Lex request at all
        url, headers = calls[0]
        assert url == "https://publications.europa.eu/resource/celex/32016R0679"
        assert headers["Accept"] == "application/pdf;type=pdfa1a"
        assert headers["Accept-Language"] == "ita"

    @pytest.mark.asyncio
    async def test_falls_back_to_the_next_flavour(self, monkeypatch):
        calls = _install_pdf(monkeypatch, ("application/pdf;type=pdfa2a",))
        pdf = await scraper.download_eurlex_pdf(
            Norma(tipo_atto="direttiva ue", data="2019", numero_atto="1937")
        )
        assert pdf == _FAKE_PDF
        assert [c[1]["Accept"] for c in calls] == ["application/pdf;type=pdfa1a", "application/pdf;type=pdfa2a"]
        assert calls[0][0] == "https://publications.europa.eu/resource/celex/32019L1937"

    @pytest.mark.asyncio
    async def test_waf_challenge_is_reported_not_returned_as_a_pdf(self, monkeypatch):
        _install_pdf(monkeypatch, ())
        with pytest.raises(ValueError, match="did not return a PDF"):
            await scraper.download_eurlex_pdf(
                Norma(tipo_atto="regolamento ue", data="2016", numero_atto="679")
            )

    @pytest.mark.asyncio
    async def test_treaties_have_no_pdf(self, monkeypatch):
        _install_pdf(monkeypatch, ())
        with pytest.raises(ValueError, match="treaties"):
            await scraper.download_eurlex_pdf(Norma(tipo_atto="tfue"))

    @pytest.mark.asyncio
    async def test_download_law_pdf_gdpr_end_to_end(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lc, "_PDF_OUTPUT_DIR", str(tmp_path))
        _install_pdf(monkeypatch, ("application/pdf;type=pdfa1a",))
        out = await lc._download_law_pdf_impl("GDPR")
        assert out.startswith("**PDF scaricato** (GDPR)")
        assert "https://eur-lex.europa.eu/legal-content/IT/TXT/PDF/?uri=CELEX:32016R0679" in out
        assert "CELLAR" in out
        path = out.split("File: `", 1)[1].split("`", 1)[0]
        assert Path(path).parent == tmp_path
        assert Path(path).read_bytes() == _FAKE_PDF

    @pytest.mark.asyncio
    async def test_download_law_pdf_reports_the_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lc, "_PDF_OUTPUT_DIR", str(tmp_path))
        _install_pdf(monkeypatch, ())
        out = await lc._download_law_pdf_impl("GDPR")
        assert out.startswith("**Errore** download PDF EUR-Lex")


# ---------------------------------------------------------------------------
# fetch_law_annotations / cerca_brocardi: the article text and the rubrica from Brocardi
# ---------------------------------------------------------------------------

from bs4 import BeautifulSoup  # noqa: E402

from src.lib.brocardi import client as brocardi  # noqa: E402

# Copied from https://www.brocardi.it/codice-civile/libro-quarto/titolo-ix/art2043.html (2026-09-29):
# the article text is <div class="corpoDelTesto dispositivo"> (no id), with footnote calls
# <sup><a class="nota-ref"> and links to the legal dictionary.
_B2043_DISPOSITIVO = (
    '<div class="corpoDelTesto dispositivo"><p class="comma"><sup><a class="nota-ref" href="#nota_17870">(1)</a></sup>'
    '<sup><a class="nota-ref" href="#nota_17850">(2)</a></sup>Qualunque fatto<sup><a class="nota-ref" href="#nota_4603">(3)</a></sup> '
    '<a href="/dizionario/2404.html" title="Dizionario Giuridico: Dolo (diritto civile)">doloso</a> o '
    '<a href="/dizionario/2405.html" title="Dizionario Giuridico: Colpa (diritto civile)">colposo</a>'
    '<sup><a class="nota-ref" href="#nota_4604">(4)</a></sup>, che cagiona<sup><a class="nota-ref" href="#nota_4605">(5)</a></sup> '
    'ad altri un <a href="/dizionario/2406.html" title="Dizionario Giuridico: Danno">danno ingiusto</a>'
    '<sup><a class="nota-ref" href="#nota_4606">(6)</a></sup>, obbliga colui che ha commesso il fatto a '
    '<a href="/dizionario/3912.html" title="Dizionario Giuridico: Risarcimento danni">risarcire</a> il danno '
    '[<a href="/codice-civile/libro-quarto/titolo-ix/art2058.html" title="Risarcimento in forma specifica">2058</a>]'
    '<sup><a class="nota-ref" href="#nota_4607">(7)</a></sup>.</p></div>'
)
_B2043_PAGE = (
    "<html><head><title>Art. 2043 codice civile - Risarcimento per fatto illecito - Brocardi.it</title></head><body>"
    '<div id="breadcrumb"><span>Tu sei qui:</span><span><a href="/codice-civile/">Codice Civile</a> &gt; </span>'
    '<span><a href="/codice-civile/libro-quarto/titolo-ix/art2043.html">Articolo 2043</a></span></div>'
    '<div class="panes-condensed panes-w-ads content-ext-guide content-mark">'
    '<h1 class="hbox-header"><span>Articolo</span><span>2043</span><span>Codice Civile</span></h1>'
    '<h2 class="hbox-header">(R.D. 16 marzo 1942, n. 262)</h2>'
    '<h3 class="hbox-content">Risarcimento per fatto illecito</h3>'
    '<h2 class="tab-title">Dispositivo dell\'art. 2043 Codice Civile</h2>'
    f"{_B2043_DISPOSITIVO}"
    '<div class="nota"><a name="nota_4607"></a>(7) Nota di prova sul risarcimento.</div>'
    "</div></body></html>"
)
# Art. 6 D.Lgs. 231/2001 (Brocardi): a text with lettered lists.
_B231_ART6_DISPOSITIVO = (
    '<div class="corpoDelTesto dispositivo"><p class="comma">1. Se il reato è stato commesso dalle persone indicate '
    "nell'articolo 5, comma 1, lettera a), l'ente non risponde se prova che:</p><ol>\n<li>\n\t\ta) l'organo dirigente "
    "ha adottato ed efficacemente attuato, prima della commissione del fatto, modelli di organizzazione e di "
    "gestione idonei a prevenire reati della specie di quello verificatosi;</li>\n<li>\n\t\td) non vi è stata omessa "
    "o insufficiente vigilanza da parte dell'organismo di cui alla lettera b).</li>\n</ol></div>"
)


class TestBrocardiArticleText:
    def test_dispositivo_is_read_from_the_class_without_id(self):
        # Art. 2043 c.c. (R.D. 16 marzo 1942 n. 262), text as on Normattiva; Brocardi adds only the
        # link to art. 2058 in square brackets. The footnote calls (1)...(7) are not part of it.
        soup = BeautifulSoup(_B2043_PAGE, "lxml")
        result = brocardi.BrocardiResult()
        brocardi._extract_dispositivo(soup, result)
        assert result.dispositivo == (
            "Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga colui che "
            "ha commesso il fatto a risarcire il danno [2058]."
        )

    def test_footnote_calls_stay_in_the_page_for_the_notes_section(self):
        soup = BeautifulSoup(_B2043_PAGE, "lxml")
        brocardi._extract_dispositivo(soup, brocardi.BrocardiResult())
        assert len(soup.find_all("a", class_="nota-ref")) == 7  # the copy was cleaned, not the page

    def test_rubrica_is_the_h3_not_the_estremi(self):
        soup = BeautifulSoup(_B2043_PAGE, "lxml")
        result = brocardi.BrocardiResult()
        brocardi._extract_rubrica(soup, result)
        assert result.rubrica == "Risarcimento per fatto illecito"  # not "(R.D. 16 marzo 1942, n. 262)"

    def test_lettered_list_of_art_6_dlgs_231_2001_is_kept(self):
        soup = BeautifulSoup(f"<html><body>{_B231_ART6_DISPOSITIVO}</body></html>", "lxml")
        result = brocardi.BrocardiResult()
        brocardi._extract_dispositivo(soup, result)
        assert result.dispositivo.startswith("1. Se il reato è stato commesso dalle persone indicate")
        assert "l'ente non risponde se prova che: a) l'organo dirigente ha adottato" in result.dispositivo
        assert result.dispositivo.endswith("di cui alla lettera b).")

    def test_legacy_id_markup_still_works(self):
        html = '<html><body><div id="dispositivo"><div class="corpoDelTesto">Testo <sup><a class="nota-ref" href="#nota_1">(1)</a></sup>vecchio.</div></div></body></html>'
        result = brocardi.BrocardiResult()
        brocardi._extract_dispositivo(BeautifulSoup(html, "lxml"), result)
        assert result.dispositivo == "Testo vecchio."

    def test_markdown_has_rubrica_and_article_text(self):
        result = brocardi.BrocardiResult(
            url="https://www.brocardi.it/codice-civile/libro-quarto/titolo-ix/art2043.html",
            rubrica="Risarcimento per fatto illecito",
            dispositivo="Qualunque fatto doloso o colposo.",
        )
        md = result.to_markdown()
        assert "**Rubrica**: Risarcimento per fatto illecito" in md
        assert "## Testo dell'articolo\nQualunque fatto doloso o colposo." in md

    @pytest.mark.asyncio
    async def test_fetch_law_annotations_returns_the_article_text(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CACHE", "off")
        monkeypatch.setattr(brocardi, "_url_cache", {})
        index = '<a href="/codice-civile/libro-quarto/titolo-ix/art2043.html">Art. 2043</a>'
        _install(monkeypatch, {"art2043.html": _B2043_PAGE, "brocardi.it/codice-civile/": index})
        out = await lc._fetch_law_annotations_impl("codice civile", "2043")
        assert "**Rubrica**: Risarcimento per fatto illecito" in out
        assert "## Testo dell'articolo\nQualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto" in out
        assert "(1)(2)Qualunque" not in out


# ---------------------------------------------------------------------------
# Italgiure archive window: verifica_citazioni and cerca_brocardi
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, patch  # noqa: E402

from src.lib._result import SearchResult  # noqa: E402
from src.lib.brocardi.client import BrocardiResult, Massima  # noqa: E402


@pytest.fixture
def pinned_today(monkeypatch):
    """2026-09-29: the day the archive was measured (civil archive from 17/02/2021)."""
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
    monkeypatch.setattr(lc, "_archive_start_cache", {})


def _archive_start(year=2021, date="2021-02-17"):
    async def start(archivio="tutti"):
        return year, date

    return start


def _found(heading: str) -> SearchResult:
    return SearchResult(success=True, source="italgiure", num_found=1, results_text=f"# {heading}\n\ntesto")


_NOT_FOUND = SearchResult(success=False, source="italgiure", error_type="no_results")


class TestArchiveStart:
    @pytest.mark.asyncio
    async def test_start_is_read_from_the_oldest_decision(self, pinned_today):
        # Italgiure, civil archive on 2026-09-25: the oldest decision is deposited 17/02/2021
        # (Cass. civ. 4215/2021); nothing is indexed for 2020.
        response = {"response": {"docs": [{"id": "x", "anno": "2021", "datdep": ["20210217"], "kind": "snciv"}]}}
        solr = AsyncMock(return_value=response)
        with patch("src.tools.italgiure.solr_query", solr):
            assert await lc._italgiure_archive_start("civile") == (2021, "2021-02-17")
            assert await lc._italgiure_archive_start("civile") == (2021, "2021-02-17")
        assert solr.await_count == 1  # cached for the day
        params = solr.await_args.args[0]
        assert params["sort"] == "pd asc" and params["rows"] == 1
        assert params["q"] == '(kind:"snciv")'

    @pytest.mark.asyncio
    async def test_all_archives_are_probed_together(self, pinned_today):
        solr = AsyncMock(return_value={"response": {"docs": [{"datdep": ["20210127"], "kind": "snpen"}]}})
        with patch("src.tools.italgiure.solr_query", solr):
            assert await lc._italgiure_archive_start("tutti") == (2021, "2021-01-27")
        assert 'kind:"snciv"' in solr.await_args.args[0]["q"] and 'kind:"snpen"' in solr.await_args.args[0]["q"]

    @pytest.mark.asyncio
    async def test_probe_failure_falls_back_to_the_window_rule_and_is_not_cached(self, pinned_today):
        solr = AsyncMock(side_effect=RuntimeError("Italgiure down"))
        with patch("src.tools.italgiure.solr_query", solr):
            assert await lc._italgiure_archive_start("civile") == (2021, "")  # 2026 - 5
            await lc._italgiure_archive_start("civile")
        assert solr.await_count == 2


class TestVerificaSentenzaArchiveWindow:
    @pytest.mark.asyncio
    async def test_cass_10579_2021_not_found_is_not_verifiable_not_inexistent(self, pinned_today):
        # Cass. civ. sez. III n. 10579/2021 (ord. 21/04/2021) exists but is not in the Italgiure
        # index, which covers 2021 only in part (from 17/02/2021, ~16k decisions against 35-38k
        # of a full year): the verdict is "non verificabile", never "inesistente".
        lookup = AsyncMock(return_value=_NOT_FOUND)
        with patch("src.tools.legal_citations._italgiure_archive_start", _archive_start()), \
             patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            verdetto, nota = await lc._verifica_sentenza("Cass. civ. sez. III n. 10579/2021", "civile")
        assert verdetto == "non verificabile"
        assert "solo in parte" in nota and "17/02/2021" in nota

    @pytest.mark.asyncio
    async def test_not_found_in_a_fully_covered_year_is_inexistent(self, pinned_today):
        # 2023 is inside the window: Cass. civ. n. 99999/2023 does not exist.
        lookup = AsyncMock(return_value=_NOT_FOUND)
        with patch("src.tools.legal_citations._italgiure_archive_start", AsyncMock(side_effect=AssertionError)), \
             patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            verdetto, _ = await lc._verifica_sentenza("Cass. civ. n. 99999/2023", "civile")
        assert verdetto == "inesistente"  # and no probe was needed: 2023 cannot precede the window

    @pytest.mark.asyncio
    async def test_decision_before_the_start_is_not_looked_up(self, pinned_today):
        lookup = AsyncMock(side_effect=AssertionError("lookup of a decision before the archive"))
        with patch("src.tools.legal_citations._italgiure_archive_start", _archive_start()), \
             patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            # Cass. civ. n. 29711/2020: not indexed (0 results), the archive starts on 17/02/2021.
            verdetto, nota = await lc._verifica_sentenza("Cass. civ. n. 29711/2020", "tutti")
        assert verdetto == "non verificabile"
        assert "anteriore all'archivio" in nota and "17/02/2021" in nota

    @pytest.mark.asyncio
    async def test_first_year_found_is_verified(self, pinned_today):
        lookup = AsyncMock(return_value=_found("Cass. civ., sez. un., n. 41994/2021, dep. 30/12/2021"))
        with patch("src.tools.legal_citations._italgiure_archive_start", _archive_start()), \
             patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            verdetto, _ = await lc._verifica_sentenza("Cass. SS.UU. n. 41994/2021", "civile")
        assert verdetto == "verificata"

    @pytest.mark.asyncio
    async def test_probe_failure_stays_conservative_on_the_edge_year(self, pinned_today):
        # No archive start available: the assumed window (2026 - 5 = 2021) still stops a
        # decision of 2021 from being called inexistent.
        lookup = AsyncMock(return_value=_NOT_FOUND)
        with patch("src.tools.italgiure.solr_query", AsyncMock(side_effect=RuntimeError("down"))), \
             patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            verdetto, _ = await lc._verifica_sentenza("Cass. civ. n. 10579/2021", "civile")
        assert verdetto == "non verificabile"

    @pytest.mark.asyncio
    async def test_cass_pen_selects_the_criminal_archive(self, pinned_today):
        # 41994/2021 exists in both archives: Cass. pen. sez. 2 (dep. 17/11/2021) and Cass. civ.
        # SS.UU. (dep. 30/12/2021). "Cass. pen. sez. II" with archivio "tutti" must be verified
        # against the criminal decision, not reported as discordant with the civil namesake.
        lookup = AsyncMock(return_value=_found("Cass. pen., sez. II, n. 41994/2021, dep. 17/11/2021"))
        with patch("src.tools.legal_citations._italgiure_archive_start", _archive_start()), \
             patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            verdetto, _ = await lc._verifica_sentenza("Cass. pen. sez. II n. 41994/2021", "tutti")
        assert verdetto == "verificata"
        assert lookup.await_args.kwargs == {"sezione": "2", "archivio": "penale"}

    @pytest.mark.asyncio
    async def test_cass_civ_selects_the_civil_archive_and_lavoro_is_civil(self, pinned_today):
        lookup = AsyncMock(return_value=_found("Cass. civ., lav., n. 12345/2024, dep. 22/04/2024"))
        with patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            await lc._verifica_sentenza("Cass. lav. n. 12345/2024", "tutti")
        assert lookup.await_args.kwargs["archivio"] == "civile"
        with patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            await lc._verifica_sentenza("Cassazione civile n. 12345/2024", "tutti")
        assert lookup.await_args.kwargs["archivio"] == "civile"

    @pytest.mark.asyncio
    async def test_explicit_archive_is_not_overridden_by_the_citation(self, pinned_today):
        lookup = AsyncMock(return_value=_found("Cass. civ., sez. III, n. 12345/2024, dep. 22/04/2024"))
        with patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            await lc._verifica_sentenza("Cass. pen. n. 12345/2024", "civile")
        assert lookup.await_args.kwargs["archivio"] == "civile"

    @pytest.mark.asyncio
    async def test_section_is_passed_with_the_solr_code(self, pinned_today):
        lookup = AsyncMock(return_value=_found("Cass. civ., sez. un., n. 41994/2021, dep. 30/12/2021"))
        with patch("src.tools.legal_citations._italgiure_archive_start", _archive_start()), \
             patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            await lc._verifica_sentenza("Cass. sez. un. n. 41994/2021", "civile")
        assert lookup.await_args.kwargs["sezione"] == "U"  # Sezioni Unite = szdec:U

    @pytest.mark.asyncio
    async def test_wrong_section_is_still_a_mismatch(self, pinned_today):
        # Cass. sez. I n. 41994/2021 is a Sezioni Unite decision (civil, dep. 30/12/2021).
        lookup = AsyncMock(return_value=_found("Cass. civ., sez. un., n. 41994/2021, dep. 30/12/2021"))
        with patch("src.tools.legal_citations._italgiure_archive_start", _archive_start()), \
             patch("src.tools.italgiure._leggi_sentenza_impl", lookup):
            verdetto, nota = await lc._verifica_sentenza("Cass. sez. I n. 41994/2021", "civile")
        assert verdetto == "metadati discordanti"
        assert "(SU)" in nota


class TestCercaBrocardiArchiveWindow:
    @staticmethod
    def _result():
        return BrocardiResult(
            url="https://www.brocardi.it/codice-civile/libro-quarto/titolo-ix/art2043.html",
            massime=[
                Massima(autorita="Cass. civ.", numero="887", anno="2002", testo="massima del 2002"),
                Massima(autorita="Cass. civ.", numero="29711", anno="2020", testo="massima del 2020"),
                Massima(autorita="Cass. civ.", numero="10579", anno="2021", testo="massima del 2021"),
                Massima(autorita="Cass. pen.", numero="100", anno="2024", testo="massima del 2024"),
            ],
        )

    @pytest.mark.asyncio
    async def test_references_before_the_archive_are_listed_apart(self, pinned_today):
        # Cass. civ. 887/2002 and 29711/2020 exist but leggi_sentenza answers "non trovata"
        # (Italgiure holds only decisions from 17/02/2021): they are not offered for leggi_sentenza.
        with patch("src.tools.legal_citations.fetch_brocardi", AsyncMock(return_value=self._result())), \
             patch("src.tools.legal_citations._italgiure_archive_start", _archive_start()):
            out = await lc._cerca_brocardi_impl("art. 2043 c.c.")
        block = out.split("**Riferimenti Cassazione**", 1)[1]
        readable, apart = block.split("**Fuori archivio Italgiure**", 1)
        assert "- Cass. civ. n. 10579/2021" in readable and "- Cass. pen. n. 100/2024" in readable
        assert "887/2002" not in readable and "29711/2020" not in readable
        assert "anteriori al 17/02/2021" in apart
        assert "- Cass. civ. n. 887/2002" in apart and "- Cass. civ. n. 29711/2020" in apart

    @pytest.mark.asyncio
    async def test_recent_references_need_no_archive_probe(self, pinned_today):
        recent = BrocardiResult(
            url="https://www.brocardi.it/codice-civile/libro-quarto/titolo-ix/art2043.html",
            massime=[Massima(autorita="Cass. civ.", numero="100", anno="2024", testo="t")],
        )
        with patch("src.tools.legal_citations.fetch_brocardi", AsyncMock(return_value=recent)), \
             patch("src.tools.legal_citations._italgiure_archive_start", AsyncMock(side_effect=AssertionError)):
            out = await lc._cerca_brocardi_impl("art. 2043 c.c.")
        assert "- Cass. civ. n. 100/2024" in out
        assert "Fuori archivio" not in out


# Placeholder so later sections of this module can be appended tool by tool.
_ = NormaVisitata
