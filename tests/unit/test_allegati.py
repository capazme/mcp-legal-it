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
from pathlib import Path

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib.visualex import akn_fetch, scraper
from src.lib.visualex.akn_parser import parse_akn
from src.lib.visualex.models import Norma, NormaVisitata, split_annex
from src.lib.visualex.scraper import _extract_eurlex_article, fetch_article
from src.tools import legal_citations as lc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def codice_appalti():
    return parse_akn((FIXTURES / "akn" / "dlgs_36_2023_trimmed.xml").read_text(encoding="utf-8"))


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


def _serve_akn(monkeypatch, act):
    """Make fetch_article read ``act`` as the AKN export, and fail on any HTML fetch."""

    async def fake_fetch_act_akn(norma, data_vigenza=None):
        return act

    class _NoNetwork:
        def __init__(self, *a, **k):
            raise AssertionError("the HTML fallback must not be reached")

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
        result = await fetch_article(_codice_appalti("30"))
        assert "Uso di procedure automatizzate" in result["text"]
        assert result["source"] == "normattiva-akn"
        assert not result.get("allegato")

    @pytest.mark.asyncio
    async def test_annex_article_is_served_and_labelled(self, monkeypatch, codice_appalti):
        _serve_akn(monkeypatch, codice_appalti)
        result = await fetch_article(_codice_appalti("allegato I.7 art. 30"))
        assert "Cronoprogramma" in result["text"]
        assert result["allegato"] == "Allegato I.7"
        assert "~art" not in result["url"]

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
        result = await fetch_article(nv)
        assert "Giusto processo" in result["text"]
        assert result["allegato"] == "Allegato 1"

    @pytest.mark.asyncio
    async def test_cite_law_markdown_says_where_the_text_comes_from(self, monkeypatch, codice_appalti):
        _serve_akn(monkeypatch, codice_appalti)
        out = await lc._cite_law_impl("art. 30 dell'allegato I.7 al D.Lgs. 36/2023")
        assert "Cronoprogramma" in out
        header = out.split("###")[0]
        assert "Testo tratto dall'Allegato I.7" in header

    @pytest.mark.asyncio
    async def test_cite_law_json_carries_the_annex(self, monkeypatch, codice_appalti):
        _serve_akn(monkeypatch, codice_appalti)
        body = json.loads(await lc._cite_law_impl("art. 30 D.Lgs. 36/2023", formato="json"))
        assert body["allegato"] is None
        assert "Uso di procedure automatizzate" in body["testo"]
        annex = json.loads(await lc._cite_law_impl("allegato I.7 art. 30 D.Lgs. 36/2023", formato="json"))
        assert annex["allegato"] == "Allegato I.7"
        assert annex["urn"] == "urn:nir:stato:decreto.legislativo:2023-03-31;36"


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
