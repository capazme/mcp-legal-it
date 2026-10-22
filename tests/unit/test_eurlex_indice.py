"""An EU act's index, tree and recitals through the api (VisuaLex's EU tree and recitals reader).

The pages are VisuaLex's fixtures and this package's (tests/fixtures/visualex/eurlex/README.md);
CELLAR is faked, and so is the consolidation lookup.
"""

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import eurlex_consolidate as ec
from mcp_legal_it.lib.visualex import scraper
from mcp_legal_it.lib.visualex.eurlex_tree import _extract_eurlex_rubriche, _parse_eurlex_tree

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "eurlex"
CELLAR = "https://publications.europa.eu/resource/celex/"


def _page(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class _Cellar:
    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def __call__(self, fonte, **kwargs):
        pages, asked = self.pages, self.asked

        class _Resp:
            def __init__(self, url, text):
                self.url, self.text, self.status_code = url, text, 200

            def raise_for_status(self):
                return None

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url):
                asked.append(url)
                return _Resp(url, pages[url])

        return _Client()


class TestOurAdaptations:
    """(A) and (B) in eurlex_tree.py's header: VisuaLex adopts both in its PR #312."""

    def test_an_oj_article_keeps_its_ordinal_in_the_tree_and_the_rubriche(self):
        soup = BeautifulSoup(_page("synthetic_oj_article_15_bis.html"), "html.parser")
        result, count, metadata = _parse_eurlex_tree(soup, "https://eur-lex.europa.eu/eli/reg/2099/1/oj/ita")
        numeri = [item["numero"] for item in result if isinstance(item, dict)]
        assert "15-bis" in numeri and "15" not in numeri
        assert "15-bis" in metadata["rubriche"] and "15" not in metadata["rubriche"]

    def test_the_articles_an_amending_act_quotes_are_not_in_its_index(self):
        soup = BeautifulSoup(_page("dir2009_136_oj_art1_2_trimmed.html"), "html.parser")
        result, count, metadata = _parse_eurlex_tree(soup, "https://eur-lex.europa.eu/eli/dir/2009/136/oj/ita")
        assert [item["numero"] for item in result if isinstance(item, dict)] == ["1", "2"] and count == 2
        assert set(_extract_eurlex_rubriche(soup)) == {"1", "2"}

    @pytest.mark.parametrize("spelling", ["15 bis", "15-bis", "15bis"])
    def test_the_suffixed_article_opens_in_any_spelling(self, spelling):
        assert "Articolo inserito" in scraper._extract_eurlex_article(_page("synthetic_oj_article_15_bis.html"),
                                                                      spelling).replace("\xa0", " ")

    def test_our_suffix_guard_is_still_needed_on_a_class_less_glued_page(self):
        # VisuaLex #309 checks the ordinal after the number, but here the heading's text runs
        # into the next words («Articolo 15 bisTesto»): only our wrapper refuses it.
        html = '<html><body><div class="eli-subdivision"><p>Articolo 15 bis</p><p>Testo.</p></div></body></html>'
        assert scraper._extract_eurlex_article(html, "15") == "[Articolo 15 non trovato nel documento EUR-Lex]"


@pytest.fixture
def no_lookup(monkeypatch):
    async def nessuna(celex_base):
        return {"data_gu": None, "in_vigore_dal": None, "versioni": []}

    monkeypatch.setattr(ec, "consolidazioni", nessuna)


class TestTheApi:
    async def test_the_index_of_an_oj_text(self, monkeypatch, no_lookup):
        pages = _Cellar({CELLAR + "32016R0679": _page("gdpr_oj_trimmed.html")})
        monkeypatch.setattr(scraper, "async_client", pages)
        i = await api.indice_atto("GDPR")
        assert i.esito == "trovato" and i.rubriche["1"] == "Oggetto e finalità" and i.count == len(i.rubriche)
        assert i.consolidato is None and i.consolidato_verificato is True and pages.asked == [CELLAR + "32016R0679"]

    @pytest.mark.consolidazioni_reali
    async def test_the_index_of_the_text_in_force_is_the_consolidation_s(self, monkeypatch):
        async def una(celex_base):
            return {"data_gu": "2002-07-31", "in_vigore_dal": "2002-07-31", "versioni": [
                {"celex": "02002L0058-20091219", "data": "2009-12-19",
                 "modifiche": [{"celex": "32009L0136", "atto": "direttiva 2009/136"}]}]}

        monkeypatch.setattr(ec, "consolidazioni", una)
        pages = _Cellar({CELLAR + "02002L0058-20091219": _page("eprivacy_consolidated_20091219.html")})
        monkeypatch.setattr(scraper, "async_client", pages)
        i = await api.indice_atto("direttiva 2002/58/CE")
        assert i.rubriche["14-bis"] == "Procedura di comitato" and i.consolidato["celex"] == "02002L0058-20091219"
        assert i.title.startswith("relativa al trattamento dei dati personali")
        t = await api.albero_atto("direttiva 2002/58/CE", dettagli=True)
        assert t.count == 23 and t.consolidato["celex"] == "02002L0058-20091219"
        assert len(pages.asked) == 1  # one page for the index and the tree

    async def test_the_tree_with_links(self, monkeypatch, no_lookup):
        pages = _Cellar({CELLAR + "32016R0679": _page("gdpr_oj_trimmed.html")})
        monkeypatch.setattr(scraper, "async_client", pages)
        t = await api.albero_atto("GDPR", link=True)
        assert t.esito == "trovato" and t.articles[0] == {
            "numero": "1", "url": "https://eur-lex.europa.eu/eli/reg/2016/679/art_1/oj"}

    async def test_the_recitals(self, monkeypatch, no_lookup):
        pages = _Cellar({CELLAR + "32016R0679": _page("gdpr_oj_trimmed.html")})
        monkeypatch.setattr(scraper, "async_client", pages)
        c = await api.considerando("GDPR")
        assert c.esito == "trovato" and [r["number"] for r in c.considerando] == ["1", "2", "3", "173"]
        assert not c.considerando[0]["text"].startswith("(")

    @pytest.mark.parametrize("atto", ["art. 2043 c.c.", "TFUE"])
    async def test_recitals_only_for_eu_regulations_and_directives(self, atto):
        assert (await api.considerando(atto)).esito == "non_supportata"

    async def test_cite_law_prints_the_recital_s_number_as_its_label(self, monkeypatch, no_lookup):
        from mcp_legal_it.tools import legal_citations as lc

        pages = _Cellar({CELLAR + "32016R0679": _page("gdpr_oj_trimmed.html")})
        monkeypatch.setattr(scraper, "async_client", pages)
        md = await lc._cite_law_impl("considerando 1 GDPR")
        assert "(1) La protezione delle persone fisiche" in md
        out = json.loads(await lc._cite_law_impl("considerando 1 GDPR", formato="json"))
        assert out["testo"].startswith("La protezione delle persone fisiche")  # VisuaLex's text, no label


async def test_a_consolidated_title_in_the_first_lines_only(monkeypatch, no_lookup):
    # The GDPR's consolidation names the act in `title-doc-first` and keeps only the EEA note in
    # `title-doc-last`: VisuaLex's reader gave no title.
    from mcp_legal_it.lib.visualex.models import Norma

    page = ('<html><body><p class="title-doc-first">REGOLAMENTO (UE) 2016/679 DEL PARLAMENTO EUROPEO E DEL '
            'CONSIGLIO</p><p class="title-doc-first">del 27 aprile 2016</p><p class="title-doc-first">relativo '
            'alla protezione delle persone fisiche</p><p class="title-doc-last">(Testo rilevante ai fini del SEE)</p>'
            '<p class="title-article-norm">Articolo 1</p><p class="stitle-article-norm">Oggetto e finalità</p>'
            '</body></html>')

    async def pagina(norma):
        return page, "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:02016R0679-20160504"

    monkeypatch.setattr(scraper, "_fetch_eurlex_html", pagina)
    r = await scraper.fetch_eurlex_tree(Norma("regolamento ue", "2016", "679"))
    assert r["metadata"]["title"] == "relativo alla protezione delle persone fisiche"
