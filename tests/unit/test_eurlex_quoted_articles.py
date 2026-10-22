"""An article an amending act quotes is not the act's own article.

Dir. 2009/136/CE rewrites articles of dir. 2002/22/CE, quoting each one inside its own art. 1:
«Articolo 23 Disponibilità di servizi …» in a table cell. VisuaLex's extractor takes the first
heading it meets, so «art. 23 dir. 2009/136» was served art. 23 of dir. 2002/22 as amended (and
so were 21, 22 and 27). The fixture is CELLAR's page of 32009L0136 trimmed to its arts. 1 and 2
(tests/fixtures/visualex/eurlex/README.md).
"""

from pathlib import Path

import pytest

from mcp_legal_it.lib.visualex.scraper import _extract_eurlex_article

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "eurlex"
DIR_2009_136 = (FIXTURES / "dir2009_136_oj_art1_2_trimmed.html").read_text(encoding="utf-8")


def _non_trovato(article):
    return f"[Articolo {article} non trovato nel documento EUR-Lex]"


class TestTheAmendingAct:
    @pytest.mark.parametrize("article", ["21", "22", "23", "27"])
    def test_a_quoted_article_is_not_the_act_s(self, article):
        assert _extract_eurlex_article(DIR_2009_136, article) == _non_trovato(article)

    @pytest.mark.parametrize("article,rubrica", [
        ("1", "Modifiche alla direttiva 2002/22/CE (direttiva servizio universale)"),
        ("2", "Modifiche alla direttiva 2002/58/CE (Direttiva relativa alla vita privata e alle comunicazioni "
              "elettroniche)"),
    ])
    def test_the_act_s_own_articles_are_served(self, article, rubrica):
        text = _extract_eurlex_article(DIR_2009_136, article)
        assert text.split("\n")[0] == f"Articolo\xa0{article}"
        assert text.split("\n")[1].replace("\xa0", " ") == rubrica

    async def test_through_the_api_it_is_not_found(self, monkeypatch):
        from mcp_legal_it import api
        from mcp_legal_it.lib.visualex import scraper

        async def pagina(norma):
            return DIR_2009_136, "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32009L0136"

        monkeypatch.setattr(scraper, "_fetch_eurlex_html", pagina)
        nd = api.riferimento_da_parametri("direttiva ue", "23", data="2009", numero_atto="136").norma_data[0]
        t = await api.testo_articolo(nd, canale="html")
        assert t.esito == "articolo_non_trovato" and t.article_text == ""


class TestTheRule:
    def test_a_quotation_before_the_own_article_is_never_served_as_it(self):
        # The own art. 3 comes after a quoted «Articolo 3» without guillemets: the extractor
        # meets the quotation first, and its text is refused (never served as the act's).
        html = ('<html><body>'
                '<div class="eli-subdivision" id="art_1"><p class="oj-ti-art">Articolo 1</p>'
                '<p class="oj-sti-art">Modifiche</p><table><tr><td>'
                '<p class="oj-ti-art">Articolo 3</p><p class="oj-sti-art">Citato</p><p class="oj-normal">Testo citato.</p>'
                '</td></tr></table></div>'
                '<div class="eli-subdivision" id="art_3"><p class="oj-ti-art">Articolo 3</p>'
                '<p class="oj-sti-art">Proprio</p><p class="oj-normal">Testo proprio.</p></div>'
                '</body></html>')
        assert "Testo citato" not in _extract_eurlex_article(html, "3")

    def test_a_class_less_page_judges_the_first_heading(self):
        quoted = ('<html><body><p>Articolo 1</p><p>Modifiche</p><table><tr><td><p>«Articolo 4</p>'
                  '<p>Testo citato.</p></td></tr><tr><td><p>Articolo 23</p><p>Altro citato.</p></td></tr>'
                  '</table></body></html>')
        assert _extract_eurlex_article(quoted, "4") == _non_trovato("4")
        assert _extract_eurlex_article(quoted, "23") == _non_trovato("23")
        assert _extract_eurlex_article(quoted, "1").startswith("Articolo 1")

    @pytest.mark.parametrize("name,article", [
        ("gdpr_oj_trimmed.html", "1"), ("gdpr_oj_trimmed.html", "17"),
        ("eprivacy_oj_legacy.html", "5"), ("eprivacy_consolidated_20091219.html", "5"),
        ("eidas_consolidated_20241018_trimmed.html", "50"),
    ])
    def test_the_other_pages_are_unchanged(self, name, article):
        from bs4 import BeautifulSoup

        from mcp_legal_it.lib.visualex.eurlex_text import extract_article_text

        html = (FIXTURES / name).read_text(encoding="utf-8")
        assert _extract_eurlex_article(html, article) == extract_article_text(BeautifulSoup(html, "html.parser"),
                                                                              article)


class TestReviewOf79:
    def test_an_amending_article_without_a_rubrica_is_served(self):
        # Art. 1 has no title of its own and quotes an article with one: the quotation's rubrica
        # is not the article's. Amending articles without a rubrica are common.
        html = ('<html><body><div class="eli-subdivision" id="art_1"><p class="oj-ti-art">Articolo 1</p>'
                '<p class="oj-normal">Il regolamento X è così modificato:</p><table><tr><td>'
                '<p class="oj-ti-art">Articolo 5</p><p class="oj-sti-art">Rubrica citata</p>'
                '<p class="oj-normal">Testo citato.</p></td></tr></table></div></body></html>')
        text = _extract_eurlex_article(html, "1")
        assert text.startswith("Articolo 1\nIl regolamento X è così modificato:")
        assert _extract_eurlex_article(html, "5") == _non_trovato("5")

    def test_a_guillemet_quotation_before_the_own_legacy_article_does_not_hide_it(self):
        html = ('<html><body><p>Articolo 1</p><p>Modifiche</p><p>«Articolo 2</p><p>Testo citato.»</p>'
                '<p>Articolo 2</p><p>Recepimento</p><p>Gli Stati membri recepiscono.</p></body></html>')
        text = _extract_eurlex_article(html, "2")
        assert text.startswith("Articolo 2") and "Recepimento" in text and "citato" not in text

    def test_a_suffixed_own_article_is_known_by_its_heading_whatever_its_id(self):
        html = ('<html><body><div class="eli-subdivision" id="art_16a"><p class="oj-ti-art">Articolo 16 bis</p>'
                '<div class="eli-title" id="art_16a.tit_1"><p class="oj-sti-art">Rubrica</p></div>'
                '<p class="oj-normal">Testo del 16-bis.</p></div></body></html>')
        assert "Testo del 16-bis" in _extract_eurlex_article(html, "16 bis")
        assert _extract_eurlex_article(html, "16") == _non_trovato("16")

    def test_the_own_title_s_rubrica_is_checked(self):
        # With its own title, the article's rubrica is the title's, still compared.
        html = ('<html><body><div class="eli-subdivision" id="art_3"><p class="oj-ti-art">Articolo 3</p>'
                '<div class="eli-title" id="art_3.tit_1"><p class="oj-sti-art">Definizioni</p></div>'
                '<p class="oj-normal">Testo.</p></div></body></html>')
        assert _extract_eurlex_article(html, "3").startswith("Articolo 3\nDefinizioni")


def test_an_own_article_opening_with_a_table_is_served():
    html = ('<html><body><div class="eli-subdivision" id="art_2"><p class="oj-ti-art">Articolo 2</p>'
            '<table><tr><td><p>a)</p></td><td><p>prima voce;</p></td></tr></table></div></body></html>')
    assert _extract_eurlex_article(html, "2").startswith("Articolo 2\na) prima voce;")


def test_an_article_without_its_own_div_is_served():
    # The TFUE page has no div#art_354: the ids do not cover every article, the headings decide.
    html = ('<html><body><div class="eli-subdivision" id="art_1"><p class="oj-ti-art">Articolo 1</p>'
            '<p class="oj-normal">Uno.</p></div><p class="oj-ti-art">Articolo 354</p>'
            '<p class="oj-sti-art">(ex articolo 309 del TCE)</p><p class="oj-normal">Testo.</p></body></html>')
    assert _extract_eurlex_article(html, "354").startswith("Articolo 354\n(ex articolo 309 del TCE)")
