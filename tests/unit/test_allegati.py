"""Annexes (allegati) of Italian and EU acts — issue #47.

1. D.Lgs. 36/2023 (Codice dei contratti pubblici): the AKN export carries the
   233 articles of the Code in the body and each annex as component ``<doc>``
   elements. The parser used to let the largest annex (Allegato I.7, 50 articles)
   replace the body, so ``art. 30`` returned "Cronoprogramma" (Allegato I.7)
   instead of "Uso di procedure automatizzate". The body is now the default and
   an annex is served only when asked for ("allegato I.7 art. 30"), or labelled
   when it is the act's main text (a decree that approves a code in an annex).
2. Reg. (UE) 2024/1689 (AI Act): annexes were not retrievable. CELLAR marks each
   one as ``div#anx_<N>``.

Fixtures are trimmed copies of the real documents (no network):
``akn/dlgs_36_2023_trimmed.xml`` (Normattiva caricaAKN, vigenza 2026-10-01: body
artt. 1-10, 18, 30, 31, 50 and a few annex articles) and
``eurlex_ai_act_annex_trimmed.xhtml`` (CELLAR, Italian expression: art. 6,
Allegati II and III).
"""

import json
import re
from pathlib import Path

import pytest

import mcp_legal_it.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from mcp_legal_it.lib.visualex import akn_fetch, scraper
from mcp_legal_it.lib.visualex.akn_parser import parse_akn
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata, split_annex
from mcp_legal_it.lib.visualex.scraper import _extract_eurlex_article, fetch_article
from mcp_legal_it.tools import legal_citations as lc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def codice_appalti():
    return parse_akn((FIXTURES / "akn" / "dlgs_36_2023_trimmed.xml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def codice_appalti_posizioni():
    """D.Lgs. 36/2023 with every part of the export (texts only for I.7 artt. 1, 30, I.11 art. 1):
    the parts' Normattiva positions are the real ones (Allegato I.7 is :8, checked live)."""
    return parse_akn((FIXTURES / "akn" / "dlgs_36_2023_positions.xml").read_text(encoding="utf-8"))


def _pagina_da_export(testo: str) -> str:
    """A Normattiva annex page carrying *testo* (an export article) as the page writes it:
    no "### Art." heading, real accents for the export's transliterated ones."""
    corpo = re.sub(r"^#+[^\n]*\n+", "", testo)
    corpo = re.sub(r"\b([A-Za-z]*)e'(?![A-Za-z])", lambda m: m.group(1) + "è", corpo)
    corpo = re.sub(r"\b([A-Za-z]+)a'(?![A-Za-z])", lambda m: m.group(1) + "à", corpo)
    return ('<html><body><div class="bodyTesto"><span class="attachment-just-text">'
            + " ".join(corpo.split()) + "</span></div></body></html>")


#: The page of art. 30 of Allegato I.7 (";36:8~art30"), in the attachment shape of annex pages.
_PAGINA_I7_ART30 = _pagina_da_export(
    parse_akn((FIXTURES / "akn" / "dlgs_36_2023_positions.xml").read_text(encoding="utf-8"))
    .annex_article("I.7", "30"))
#: Art. 1 of Allegato I.11: what a page of the wrong part would serve under the same number.
_PAGINA_I11_ART1 = _pagina_da_export(
    parse_akn((FIXTURES / "akn" / "dlgs_36_2023_positions.xml").read_text(encoding="utf-8"))
    .annex_article("I.11", "1"))


@pytest.fixture(scope="module")
def ai_act_html() -> str:
    return (FIXTURES / "eurlex_ai_act_annex_trimmed.xhtml").read_text(encoding="utf-8")


# A decree whose own body is a single article and whose main text is the code
# approved in Allegato 1 (the shape of D.Lgs. 104/2010, codice del processo
# amministrativo). Markup copied from the component docs of the real export.
_CODE_IN_ANNEX = """<?xml version="1.0" encoding="UTF-8"?>
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act>
<preface><docTitle>Codice in allegato</docTitle></preface>
<body><article eId="art_1"><num>Art. 1.</num><heading>Approvazione</heading>
<paragraph eId="art_1__para_1"><num>1.</num><content><p>E' approvato il codice allegato.</p></content></paragraph>
</article></body>
<attachments>
<attachment><doc name="Allegato 1-art. 1"><mainBody><paragraph><content><p>Art. 1. Effettivita.</p></content></paragraph></mainBody></doc></attachment>
<attachment><doc name="Allegato 1-art. 2"><mainBody><paragraph><content><p>Art. 2. Giusto processo.</p></content></paragraph></mainBody></doc></attachment>
<attachment><doc name="Allegato 1-art. 3"><mainBody><paragraph><content><p>Art. 3. Dovere di motivazione.</p></content></paragraph></mainBody></doc></attachment>
</attachments></act></akomaNtoso>"""


def _serve_akn(monkeypatch, act, pagine: "dict[str, str] | None" = None):
    """Make fetch_article read ``act`` as the AKN export; HTML only from *pagine* (url suffix -> page)."""

    async def fake_fetch_act_akn(norma, data_vigenza=None):
        return act

    class _Risposta:
        def __init__(self, url, text):
            self.url, self.text, self.status_code = url, text, 200

        def raise_for_status(self):
            return None

    class _NoNetwork:
        def __init__(self, *a, **k):
            if not pagine:
                raise AssertionError("the HTML fallback must not be reached")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            for suffisso, pagina in pagine.items():
                if url.endswith(suffisso):
                    return _Risposta(url, pagina)
            raise AssertionError(f"unexpected request: {url}")

    async def fake_metadata(norma):
        # Real date of an act cited with the year only, as the Normattiva page gives it.
        return {"date": "2023-03-31"} if norma.numero_atto == "36" else {}

    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", fake_fetch_act_akn)
    monkeypatch.setattr(scraper, "_act_metadata", fake_metadata)
    monkeypatch.setattr(scraper.httpx, "AsyncClient", _NoNetwork)


def _serve_eurlex(monkeypatch, html):
    async def fake(norma):
        return html, "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32024R1689"

    monkeypatch.setattr(scraper, "_fetch_eurlex_html", fake)


def _codice_appalti(article: str) -> NormaVisitata:
    return NormaVisitata(
        norma=Norma(tipo_atto="decreto legislativo", data="2023-03-31", numero_atto="36"),
        numero_articolo=article,
    )


# ---------------------------------------------------------------------------
# Parser: the body of D.Lgs. 36/2023 is the default, the annexes are kept apart
# ---------------------------------------------------------------------------

class TestCodiceAppaltiParser:
    @pytest.mark.parametrize(
        "article,rubrica",
        [
            ("1", "Principio del risultato"),
            ("18", "Il contratto e la sua stipulazione"),
            ("30", "Uso di procedure automatizzate"),
            ("31", "Anagrafe degli operatori economici"),
            ("50", "Procedure per l'affidamento"),
        ],
    )
    def test_body_article_is_the_default(self, codice_appalti, article, rubrica):
        text = codice_appalti.article(article)
        assert text is not None and rubrica in text
        assert "ALLEGATO" not in text and "Cronoprogramma" not in text

    def test_the_body_is_not_reported_as_an_annex(self, codice_appalti):
        assert codice_appalti.main_part == ""

    def test_annex_article_on_request(self, codice_appalti):
        assert "Cronoprogramma" in codice_appalti.annex_article("I.7", "30")
        assert "Cronoprogramma" in codice_appalti.annex_article("i.7", "art. 18")
        assert "Elenco prezzi unitari" in codice_appalti.annex_article("I.7", "31")

    def test_annex_lookup_is_exact_not_by_prefix(self, codice_appalti):
        # "I.1" must never land on "I.11" (or the reverse).
        i_1 = codice_appalti.annex_article("I.1", "1")
        i_11 = codice_appalti.annex_article("I.11", "1")
        assert i_1 and i_11 and i_1 != i_11

    def test_unknown_annex_or_article(self, codice_appalti):
        assert codice_appalti.annex_article("IX.9", "1") is None
        assert codice_appalti.annex_article("I.7", "999") is None

    def test_annex_doc_names_without_the_dot_are_parsed(self, codice_appalti):
        # Real names in the export: "Allegato I.4-art 1", "Allegati - Allegato I.01 art. 1".
        names = codice_appalti.annex_names()
        assert "Allegato I.4" in names
        assert "Allegato I.01" in names
        assert codice_appalti.annex_article("I.4", "1")

    def test_code_in_an_annex_stays_the_default_and_is_named(self):
        act = parse_akn(_CODE_IN_ANNEX)
        assert "Giusto processo" in act.article("2")
        assert act.main_part == "Allegato 1"

    def test_codici_unchanged(self):
        cp = parse_akn((FIXTURES / "akn" / "codice_penale.xml").read_text(encoding="utf-8"))
        assert cp.structure == "component"
        assert cp.main_part == "Codice Penale"
        assert "Omicidio" in cp.article("575")


# ---------------------------------------------------------------------------
# Reference syntax
# ---------------------------------------------------------------------------

class TestAnnexSyntax:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("allegato I.7 art. 30", ("I.7", "30")),
            ("Allegato III", ("III", "")),
            ("allegato 1, articolo 2-bis", ("1", "2-bis")),
            ("30", None),
            ("rec_42", None),
            ("", None),
        ],
    )
    def test_split_annex(self, raw, expected):
        assert split_annex(raw) == expected

    @pytest.mark.parametrize(
        "reference,expected",
        [
            ("allegato I.7 art. 30 D.Lgs. 36/2023", ("allegato I.7 art. 30", "D.Lgs. 36/2023")),
            ("art. 30 allegato I.7 D.Lgs. 36/2023", ("allegato I.7 art. 30", "D.Lgs. 36/2023")),
            ("art. 30 dell'allegato I.7 al D.Lgs. 36/2023", ("allegato I.7 art. 30", "D.Lgs. 36/2023")),
            ("art. 30, comma 1, dell'allegato I.7 al D.Lgs. 36/2023", ("allegato I.7 art. 30", "D.Lgs. 36/2023")),
            ("Allegato III Regolamento (UE) 2024/1689", ("allegato III", "Regolamento (UE) 2024/1689")),
            ("allegato III, punto 4, lett. a) AI Act", ("allegato III", "AI Act")),
            ("art. 30 D.Lgs. 36/2023", ("30", "D.Lgs. 36/2023")),
        ],
    )
    def test_parse_reference(self, reference, expected):
        assert lc._parse_reference(reference) == expected

    def test_annex_url_is_the_acts_not_a_body_article(self):
        # An annex article has no ~artN of its own in the act URN: pointing at the
        # body article with the same number is exactly the confusion of issue #47.
        assert _codice_appalti("allegato I.7 art. 30").url() == (
            "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2023-03-31;36"
        )


# ---------------------------------------------------------------------------
# fetch_article / cite_law on Normattiva
# ---------------------------------------------------------------------------

class TestNormattivaAnnexes:
    @pytest.mark.asyncio
    async def test_art_30_is_the_codes_article(self, monkeypatch, codice_appalti):
        _serve_akn(monkeypatch, codice_appalti)
        result = await fetch_article(_codice_appalti("30"), canale="akn")
        assert "Uso di procedure automatizzate" in result["text"]
        assert result["source"] == "normattiva-akn"
        assert not result.get("allegato")

    @pytest.mark.asyncio
    async def test_annex_article_is_served_and_labelled(self, monkeypatch, codice_appalti_posizioni):
        # The annex the act calls "I.7" is Normattiva's part :8: its article has an URN of its
        # own, never the body article's ";36~art30" (issue #47).
        _serve_akn(monkeypatch, codice_appalti_posizioni)
        result = await fetch_article(_codice_appalti("allegato I.7 art. 30"), canale="akn")
        assert "Cronoprogramma" in result["text"]
        assert result["allegato"] == "Allegato I.7" and result["source"] == "normattiva-akn"
        assert result["url"].endswith(";36:8~art30")

    @pytest.mark.asyncio
    async def test_html_channel_an_annex_article_is_its_page(self, monkeypatch, codice_appalti_posizioni):
        # The export says which part the act calls "I.7"; the text is that part's page.
        _serve_akn(monkeypatch, codice_appalti_posizioni, pagine={";36:8~art30": _PAGINA_I7_ART30})
        result = await fetch_article(_codice_appalti("allegato I.7 art. 30"))
        assert result["text"].startswith("Articolo 30. Cronoprogramma.") and "è corredato" in result["text"]
        assert result["source"] == "normattiva" and result["allegato"] == "Allegato I.7"
        assert result["url"].endswith(";36:8~art30")

    @pytest.mark.asyncio
    async def test_html_channel_a_page_that_is_another_article_leaves_the_export(self, monkeypatch,
                                                                                codice_appalti_posizioni):
        altra = _PAGINA_I7_ART30.replace("Articolo 30.", "Articolo 1.")
        _serve_akn(monkeypatch, codice_appalti_posizioni, pagine={";36:8~art30": altra})
        result = await fetch_article(_codice_appalti("allegato I.7 art. 30"))
        assert result["source"] == "normattiva-akn" and "Cronoprogramma" in result["text"]

    @pytest.mark.asyncio
    async def test_html_channel_a_page_of_another_part_with_the_same_number_is_refused(
            self, monkeypatch, codice_appalti_posizioni):
        # Were :8 not I.7, its page would serve another annex's article under the number
        # asked for: the export's text, which knows the part, refuses it.
        fuori_parte = _PAGINA_I11_ART1.replace("Articolo 1.", "Articolo 30.", 1)
        _serve_akn(monkeypatch, codice_appalti_posizioni, pagine={";36:8~art30": fuori_parte})
        result = await fetch_article(_codice_appalti("allegato I.7 art. 30"))
        assert result["source"] == "normattiva-akn" and "Cronoprogramma" in result["text"]

    @pytest.mark.asyncio
    async def test_unknown_annex_lists_the_available_ones(self, monkeypatch, codice_appalti):
        _serve_akn(monkeypatch, codice_appalti)
        result = await fetch_article(_codice_appalti("allegato IX.9 art. 1"))
        assert not result["text"]
        assert "Allegato I.7" in result["error"]

    @pytest.mark.asyncio
    async def test_annex_without_akn_is_an_error_not_the_body(self, monkeypatch):
        # The HTML fallback only knows body articles: it must not answer for an annex.
        _serve_akn(monkeypatch, None)
        result = await fetch_article(_codice_appalti("allegato I.7 art. 30"))
        assert not result["text"]
        assert result["error"]

    @pytest.mark.asyncio
    async def test_code_in_an_annex_is_labelled(self, monkeypatch):
        _serve_akn(monkeypatch, parse_akn(_CODE_IN_ANNEX))
        nv = NormaVisitata(
            norma=Norma(tipo_atto="decreto legislativo", data="2010-07-02", numero_atto="104"),
            numero_articolo="2",
        )
        result = await fetch_article(nv, canale="akn")
        assert "Giusto processo" in result["text"]
        assert result["allegato"] == "Allegato 1"
        # The decree's own number serves the code's article: the URL is the code's (part :1 here).
        assert result["url"].endswith(";104:1~art2")

    @pytest.mark.asyncio
    async def test_html_channel_a_code_in_an_annex_is_served_from_the_export_and_labelled(self, monkeypatch):
        """Art. 2 of a decree whose body has one article and whose main text is a code in an
        annex: Normattiva's page for ~art2 serves the decree's art. 1. The default channel must
        neither answer «non esiste» nor serve the decree's article: the code's art. 2, labelled,
        from the export when the code's own page (";104:1~art2") does not confirm it."""
        pagina = ('<html><body><div class="bodyTesto"><h2 class="article-num-akn" id="art_1">Art. 1</h2>'
                  '<div class="article-heading-akn">(Approvazione)</div><div class="art-comma-div-akn">'
                  "1. E' approvato il codice allegato.</div></div></body></html>")
        _serve_akn(monkeypatch, parse_akn(_CODE_IN_ANNEX), pagine={";104~art2": pagina, ";104:1~art2": pagina})
        nv = NormaVisitata(
            norma=Norma(tipo_atto="decreto legislativo", data="2010-07-02", numero_atto="104"),
            numero_articolo="2",
        )
        result = await fetch_article(nv)
        assert "Giusto processo" in result["text"], result
        assert result["allegato"] == "Allegato 1" and result["source"] == "normattiva-akn"
        assert result["url"].endswith(";104:1~art2")

    @pytest.mark.asyncio
    async def test_html_channel_a_code_in_an_annex_is_read_from_its_own_page(self, monkeypatch):
        """Art. 120 of d.lgs. 104/2010 cited as the decree's: the codice del processo
        amministrativo is Normattiva's part :2 ("Indice generale" is :1), and its page is the
        text, VisuaLex's article_text, under the code's own URN."""
        act = parse_akn((FIXTURES / "akn" / "dlgs_104_2010_trimmed.xml").read_text(encoding="utf-8"))
        decreto = ('<html><body><div class="bodyTesto"><h2 class="article-num-akn" id="art_2">Art. 2</h2>'
                   '<div class="art-comma-div-akn">1. Il presente decreto entra in vigore il 16 settembre '
                   "2010.</div></div></body></html>")
        codice = _pagina_da_export(act.article("120"))
        _serve_akn(monkeypatch, act, pagine={";104~art120": decreto, ";104:2~art120": codice})
        nv = NormaVisitata(
            norma=Norma(tipo_atto="decreto legislativo", data="2010-07-02", numero_atto="104"),
            numero_articolo="120",
        )
        result = await fetch_article(nv)
        assert result["text"].startswith("Art. 120 (Disposizioni specifiche") and result["source"] == "normattiva"
        assert result["url"].endswith(";104:2~art120")
        assert result["allegato"] == "Allegato 1 Codice del processo amministrativo"

    @pytest.mark.asyncio
    async def test_cite_law_markdown_says_where_the_text_comes_from(self, monkeypatch, codice_appalti_posizioni):
        _serve_akn(monkeypatch, codice_appalti_posizioni, pagine={";36:8~art30": _PAGINA_I7_ART30})
        out = await lc._cite_law_impl("art. 30 dell'allegato I.7 al D.Lgs. 36/2023")
        assert "Cronoprogramma" in out
        header = out.split("###")[0]
        assert "Testo tratto dall'Allegato I.7" in header

    @pytest.mark.asyncio
    async def test_cite_law_json_carries_the_annex(self, monkeypatch, codice_appalti_posizioni):
        # The body article comes from its page (HTML channel); an annex article from the page
        # of the part the export names, under that part's URN.
        pagina = ('<html><body><div class="bodyTesto"><h2 class="article-num-akn" id="art_30">Art. 30</h2>'
                  '<div class="article-heading-akn">(Uso di procedure automatizzate nel ciclo di vita dei '
                  'contratti)</div><div class="art-comma-div-akn">1. Per migliorare l\'efficienza...</div>'
                  '</div></body></html>')
        _serve_akn(monkeypatch, codice_appalti_posizioni,
                   pagine={";36~art30": pagina, ";36:8~art30": _PAGINA_I7_ART30})
        body = json.loads(await lc._cite_law_impl("art. 30 D.Lgs. 36/2023", formato="json"))
        assert body["allegato"] is None
        assert "Uso di procedure automatizzate" in body["testo"]
        annex = json.loads(await lc._cite_law_impl("allegato I.7 art. 30 D.Lgs. 36/2023", formato="json"))
        assert annex["allegato"] == "Allegato I.7"
        assert annex["urn"] == "urn:nir:stato:decreto.legislativo:2023-03-31;36:8~art30"


# ---------------------------------------------------------------------------
# EU annexes (CELLAR div#anx_N)
# ---------------------------------------------------------------------------

class TestEurlexAnnexes:
    def test_annex_iii_text(self, ai_act_html):
        text = _extract_eurlex_article(ai_act_html, "allegato III")
        assert text.startswith("ALLEGATO III")
        assert "Sistemi di IA ad alto rischio di cui all'articolo 6, paragrafo 2" in text
        # Point number and its text on one line, letters below it.
        assert "1. Biometria, nella misura in cui" in text
        assert "a) i sistemi di identificazione biometrica remota." in text
        # Nested tables are rendered once, not repeated by the outer row.
        assert text.count("identificazione biometrica remota") == 1
        # Annex II is a different annex.
        assert "ALLEGATO II\n" not in text

    def test_unknown_annex_lists_the_available_ones(self, ai_act_html):
        text = _extract_eurlex_article(ai_act_html, "allegato XX")
        assert "non trovato" in text and "II, III" in text

    def test_articles_still_work(self, ai_act_html):
        assert "Regole di classificazione" in _extract_eurlex_article(ai_act_html, "6")

    @pytest.mark.asyncio
    async def test_cite_law_annex_iii(self, monkeypatch, ai_act_html):
        _serve_eurlex(monkeypatch, ai_act_html)
        out = await lc._cite_law_impl("Allegato III Regolamento (UE) 2024/1689")
        assert "Sistemi di IA ad alto rischio" in out
        assert "atto non riconosciuto" not in out

    @pytest.mark.asyncio
    async def test_fetch_law_article_annex(self, monkeypatch, ai_act_html):
        _serve_eurlex(monkeypatch, ai_act_html)
        out = await lc._fetch_law_article_impl("regolamento ue", "Allegato III", "2024", "1689")
        assert "Biometria" in out
        assert "non trovato" not in out


# ---------------------------------------------------------------------------
# Disk cache: acts parsed by the old parser are not reused
# ---------------------------------------------------------------------------

def test_disk_cache_from_an_older_parser_is_ignored(tmp_path, monkeypatch, codice_appalti):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    key = ("23G00044", "20230331", "20261001")
    akn_fetch._disk_store(key, codice_appalti)
    assert akn_fetch._disk_load(key) is not None
    path = akn_fetch._disk_path(key)
    stale = json.loads(path.read_text(encoding="utf-8"))
    stale.pop("schema", None)
    path.write_text(json.dumps(stale), encoding="utf-8")
    assert akn_fetch._disk_load(key) is None


# ---------------------------------------------------------------------------
# Review follow-ups: an annex reference never falls back to the body
# ---------------------------------------------------------------------------

class TestAnnexEdgeCases:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("allegato I.7 art. 30.1", ("I.7", "30.1")),
            ("allegato II art. 3-quater.1", ("II", "3-quater.1")),
            ("allegato I.7 art. 2 bis", ("I.7", "2 bis")),
        ],
    )
    def test_split_annex_accepts_every_article_form_of_the_reference_parser(self, raw, expected):
        assert split_annex(raw) == expected

    @pytest.mark.asyncio
    async def test_dotted_annex_article_stays_on_the_annex_path(self, monkeypatch, codice_appalti):
        _serve_akn(monkeypatch, codice_appalti)
        article, act = lc._parse_reference("art. 30.1 dell'allegato I.7 al D.Lgs. 36/2023")
        assert split_annex(article) == ("I.7", "30.1")
        result = await fetch_article(_codice_appalti(article))
        assert not result["text"] and result["error"]
        assert "~art" not in result["url"]

    @pytest.mark.asyncio
    async def test_unparsable_annex_designation_is_an_error_not_the_body(self, monkeypatch, codice_appalti):
        _serve_akn(monkeypatch, codice_appalti)
        result = await fetch_article(_codice_appalti("allegato di cui all'art. 30"))
        assert not result["text"] and result["error"]

    def test_verifica_citazioni_keeps_the_comma_form_together(self):
        assert lc._split_citazioni("art. 30, allegato I.7, D.Lgs. 36/2023") == [
            "art. 30, allegato I.7, D.Lgs. 36/2023"
        ]
        assert lc._parse_reference("art. 30, allegato I.7, D.Lgs. 36/2023") == (
            "allegato I.7 art. 30", "D.Lgs. 36/2023"
        )
        # A list of complete references is still split.
        assert lc._split_citazioni("art. 6 AI Act, allegato III AI Act") == ["art. 6 AI Act", "allegato III AI Act"]

    @pytest.mark.asyncio
    async def test_unknown_eu_annex_is_an_error(self, monkeypatch, ai_act_html):
        _serve_eurlex(monkeypatch, ai_act_html)
        body = json.loads(await lc._cite_law_impl("Allegato XX AI Act", formato="json"))
        assert body["errore"] and "II, III" in body["errore"]
        assert body["testo"] == ""
        verdetto, _ = await lc._verifica_norma("Allegato XX AI Act")
        assert verdetto == "non trovata"

    @pytest.mark.asyncio
    async def test_cerca_brocardi_on_an_annex_does_not_search(self, monkeypatch):
        async def boom(*a, **k):
            raise AssertionError("Brocardi has no annex pages")

        monkeypatch.setattr(lc, "fetch_brocardi", boom)
        out = await lc._cerca_brocardi_impl("allegato I.7 art. 30 D.Lgs. 36/2023")
        assert "allegat" in out.lower()


class TestReviewOf64:
    @pytest.mark.asyncio
    async def test_an_unlabelled_page_of_the_decree_is_not_the_codes_article(self, monkeypatch):
        """Art. 2 of a decree whose main text is a code in an annex: the ~art2 page has no
        heading and holds the decree's own art. 1. It must not be served as art. 2: the
        code's art. 2 comes from the export, labelled with its part."""
        senza_titolo = ('<html><body><div class="bodyTesto"><span class="art-just-text-akn">'
                        "E' approvato il codice allegato.</span></div></body></html>")
        _serve_akn(monkeypatch, parse_akn(_CODE_IN_ANNEX), pagine={";104~art2": senza_titolo})
        nv = NormaVisitata(
            norma=Norma(tipo_atto="decreto legislativo", data="2010-07-02", numero_atto="104"),
            numero_articolo="2",
        )
        result = await fetch_article(nv)
        assert "approvato" not in result["text"], result
        assert "Giusto processo" in result["text"]
        assert result["source"] == "normattiva-akn" and result["allegato"] == "Allegato 1"

    @pytest.mark.asyncio
    async def test_an_unlabelled_page_of_a_code_named_by_its_urn_is_still_the_article(self, monkeypatch):
        # c.p. 524: the page lost its heading, the URN names the code (;1398:1): the page is it.
        cp = parse_akn((FIXTURES / "akn" / "codice_penale.xml").read_text(encoding="utf-8"))
        pagina = ('<html><body><div class="bodyTesto"><span class="art-just-text-akn">'
                  "((ARTICOLO ABROGATO DALLA L. 15 FEBBRAIO 1996, N. 66))</span></div></body></html>")
        _serve_akn(monkeypatch, cp, pagine={";1398:1~art524": pagina})
        result = await fetch_article(NormaVisitata(norma=Norma(tipo_atto="codice penale"), numero_articolo="524"))
        assert result["source"] == "normattiva" and "ARTICOLO ABROGATO" in result["text"]
