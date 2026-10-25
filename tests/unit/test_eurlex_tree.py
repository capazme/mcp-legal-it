# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_eurlex_consolidated.py at b2f7a30f: TestConsolidatedRubriche, TestEurlexTitle,
# TestConsolidatedTree, TestQuotedArticles, TestEliTitleOfTheItalianExpression, TestGluedHeading
# and TestConsolidatedTitleFromTheFirstRun (TestTreeFailuresAreNotKept tests VisuaLex's
# Playwright cache, not imported).
# Generated (scratch gen_eurlex_tests.py): VisuaLex's assertions as they are; the extractor and
# the tree reader are plain functions here, the fixtures are tests/fixtures/visualex/eurlex.
"""The EU tree, rubriche and title, as VisuaLex reads them (``eurlex_tree``)."""

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from mcp_legal_it.lib.visualex.eurlex_text import DocumentNotFoundError, extract_article_text
from mcp_legal_it.lib.visualex.eurlex_tree import (
    _extract_eurlex_rubriche,
    _extract_eurlex_title,
    _parse_eurlex_tree,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "eurlex"


def soup_of(name):
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


class TestConsolidatedRubriche:
    def test_flat_page(self):
        rubriche = _extract_eurlex_rubriche(soup_of("eprivacy_consolidated_20091219.html"))
        assert rubriche["5"] == "Riservatezza delle comunicazioni"
        assert rubriche["14-bis"] == "Procedura di comitato"
        assert len(rubriche) == 23

    def test_subdivision_page(self):
        rubriche = _extract_eurlex_rubriche(soup_of("eidas_consolidated_20241018_trimmed.html"))
        assert rubriche["1"] == "Oggetto"
        assert rubriche["50"] == "Abrogazione"

    def test_oj_page_unchanged(self):
        rubriche = _extract_eurlex_rubriche(soup_of("gdpr_oj_trimmed.html"))
        assert rubriche["1"] == "Oggetto e finalità"
        assert rubriche["17"] == "Diritto alla cancellazione («diritto all'oblio»)"

    def test_inline_markers_are_stripped_from_rubriche(self):
        rubriche = _extract_eurlex_rubriche(soup_of("eprivacy_consolidated_20091219.html"))
        assert rubriche["4"] == "Sicurezza del trattamento"


# The title block of the OJ page of regulation (EU) 2016/679, as EUR-Lex and CELLAR serve it
# (13 October 2026); the trimmed fixture leaves it out. An annex heading shares the class.
GDPR_TITLE = """<html><body><hr class="oj-separator"/><div class="eli-container">
<div class="eli-main-title" id="tit_1">
<p class="oj-doc-ti" id="d1e40-1-1">
REGOLAMENTO (UE) 2016/679 DEL PARLAMENTO EUROPEO E DEL CONSIGLIO
</p>
<p class="oj-doc-ti">del 27 aprile 2016
</p>
<p class="oj-doc-ti">relativo alla protezione delle persone fisiche con riguardo al trattamento dei dati personali, nonché alla libera circolazione di tali dati e che abroga la direttiva 95/46/CE (regolamento generale sulla protezione dei dati)</p>
<p class="oj-doc-ti">(Testo rilevante ai fini del SEE)</p>
</div>
<div class="eli-subdivision" id="anx_1"><p class="oj-doc-ti">ALLEGATO I</p></div>
</div></body></html>"""


class TestEurlexTitle:
    def test_oj_page_gives_the_subject(self):
        title = _extract_eurlex_title(BeautifulSoup(GDPR_TITLE, "html.parser"))
        assert title == (
            "relativo alla protezione delle persone fisiche con riguardo al trattamento dei dati personali, "
            "nonché alla libera circolazione di tali dati e che abroga la direttiva 95/46/CE "
            "(regolamento generale sulla protezione dei dati)"
        )

    def test_consolidated_page(self):
        assert _extract_eurlex_title(soup_of("eprivacy_consolidated_20091219.html")) == (
            "relativa al trattamento dei dati personali e alla tutela della vita privata nel settore "
            "delle comunicazioni elettroniche (direttiva relativa alla vita privata e alle comunicazioni elettroniche)"
        )

    def test_legacy_page_reads_its_description(self):
        assert _extract_eurlex_title(soup_of("eprivacy_oj_legacy.html")) == (
            "relativa al trattamento dei dati personali e alla tutela della vita privata nel settore "
            "delle comunicazioni elettroniche (direttiva relativa alla vita privata e alle comunicazioni elettroniche)"
        )

    def test_an_eli_page_without_a_description_reads_its_italian_eli_title(self):
        # The /eli/ address of a legacy act (dir. 2002/58) has no DC.description: the title was ''.
        assert _extract_eurlex_title(soup_of("eprivacy_eli_legacy_trimmed.html")) == (
            "relativa al trattamento dei dati personali e alla tutela della vita privata nel settore "
            "delle comunicazioni elettroniche (direttiva relativa alla vita privata e alle comunicazioni elettroniche)"
        )

    def test_never_a_title_in_another_language(self):
        soup = soup_of("eprivacy_eli_legacy_trimmed.html")
        soup.find("meta", attrs={"property": "eli:title", "lang": "it"}).decompose()
        assert _extract_eurlex_title(soup) == ""

    def test_a_flat_page_takes_the_first_run_only(self):
        flat = GDPR_TITLE.replace('<div class="eli-main-title" id="tit_1">', "<div>").replace(
            '<div class="eli-subdivision" id="anx_1"><p class="oj-doc-ti">ALLEGATO I</p></div>',
            '<p class="oj-normal">IL PARLAMENTO EUROPEO</p><p class="oj-doc-ti">ALLEGATO I</p>')
        title = _extract_eurlex_title(BeautifulSoup(flat, "html.parser"))
        assert title.startswith("relativo alla protezione") and "ALLEGATO" not in title

    def test_a_title_without_a_date_is_not_a_subject(self):
        page = '<p class="oj-doc-ti">TRATTATO SUL FUNZIONAMENTO DELL\'UNIONE EUROPEA</p><p class="oj-doc-ti">ALLEGATO I</p>'
        assert _extract_eurlex_title(BeautifulSoup(page, "html.parser")) == ""

    def test_a_page_without_one_says_nothing(self):
        assert _extract_eurlex_title(soup_of("gdpr_oj_trimmed.html")) == ""

    def test_the_tree_carries_it(self):
        url = "https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:02002L0058-20091219"
        _, _, metadata = _parse_eurlex_tree(soup_of("eprivacy_consolidated_20091219.html"), url)
        assert metadata["title"].startswith("relativa al trattamento dei dati personali")


class TestConsolidatedTree:
    CONS = "https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:02002L0058-20091219"

    def test_flat_page_lists_suffixed_articles_in_order(self):
        result, count, metadata = _parse_eurlex_tree(
            soup_of("eprivacy_consolidated_20091219.html"), self.CONS, link=False, details=True)
        numbers = [item["numero"] for item in result if isinstance(item, dict)]
        assert count == 23
        assert numbers[13:17] == ["14", "14-bis", "15", "15-bis"]
        assert metadata["rubriche"]["14-bis"] == "Procedura di comitato"

    def test_headings_carry_their_title_and_precede_their_articles(self):
        result, count, _ = _parse_eurlex_tree(
            soup_of("eidas_consolidated_20241018_trimmed.html"), self.CONS, link=False, details=True)
        assert result[0] == "CAPO I DISPOSIZIONI GENERALI"
        assert result[1] == {"numero": "1"}
        assert count >= 6  # Capo I (art. 1-5) + art. 50

    def test_heading_title_survives_a_modref_between_number_and_title(self):
        # Live eIDAS: a "▼M2" marker sits between "SEZIONE 2" and its title,
        # and the index read a bare "SEZIONE 2".
        html = ('<html><body>'
                '<p class="title-division-1">SEZIONE 2</p>'
                '<p class="modref">▼M2</p>'
                '<p class="title-division-2">Servizi fiduciari non qualificati</p>'
                '<p class="title-article-norm">Articolo 17</p>'
                '<p class="stitle-article-norm">Requisiti generali</p>'
                '</body></html>')
        result, count, _ = _parse_eurlex_tree(
            BeautifulSoup(html, "html.parser"), self.CONS, link=False, details=True)
        assert result[0] == "SEZIONE 2 Servizi fiduciari non qualificati"
        assert result[1] == {"numero": "17"}
        assert count == 1

    def test_headings_are_omitted_without_details(self):
        result, _, _ = _parse_eurlex_tree(
            soup_of("eidas_consolidated_20241018_trimmed.html"), self.CONS, link=False, details=False)
        assert all(isinstance(item, dict) for item in result)

    def test_link_true_falls_back_to_an_anchor_on_the_consolidated_url(self):
        result, _, _ = _parse_eurlex_tree(
            soup_of("eprivacy_consolidated_20091219.html"), self.CONS, link=True, details=False)
        first = result[0]
        assert first["numero"] == "1"
        assert first["url"] == f"{self.CONS}#art_1"

    def test_oj_page_unchanged(self):
        result, count, metadata = _parse_eurlex_tree(
            soup_of("gdpr_oj_trimmed.html"), "https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita",
            link=False, details=True)
        numbers = [item["numero"] for item in result if isinstance(item, dict)]
        assert numbers == ["1", "2", "3", "4", "17"]
        assert "CAPO I" in result


class TestQuotedArticles:
    """An amending act's OJ page quotes, in table cells, the articles it replaces or inserts in
    another act. Dir. 2009/136 has six articles; it quotes art. 21, 22, 23, 23 bis and 27 of dir.
    2002/22 (and 14 bis, 15 bis of dir. 2002/58), which were listed in its index and served as
    its own: art. 23 asked was art. 23 of dir. 2002/22."""

    URL = "https://eur-lex.europa.eu/eli/dir/2009/136/oj/ita"

    def test_the_index_lists_the_acts_own_articles_only(self):
        result, count, metadata = _parse_eurlex_tree(soup_of("amending_dir_2009_136_trimmed.html"), self.URL)
        assert [item["numero"] for item in result] == ["1", "2", "3", "4", "5", "6"]
        assert count == 6
        assert sorted(metadata["rubriche"], key=int) == ["1", "2", "3", "4", "5", "6"]
        assert metadata["rubriche"]["6"] == "Destinatari"

    @pytest.mark.parametrize("article", ["21", "22", "23", "27", "23 bis", "14 bis", "15 bis", "20", "37"])
    def test_a_quoted_article_is_not_found(self, article):
        with pytest.raises(DocumentNotFoundError):
            extract_article_text(soup_of("amending_dir_2009_136_trimmed.html"), article)

    @pytest.mark.parametrize("article,rubrica", [("1", "Modifiche alla direttiva 2002/22/CE (direttiva servizio universale)"),
                                                 ("4", "Recepimento"), ("6", "Destinatari")])
    def test_the_acts_own_articles_are_served(self, article, rubrica):
        text = extract_article_text(soup_of("amending_dir_2009_136_trimmed.html"), article)
        assert text.split("\n")[:2] == [f"Articolo\xa0{article}", rubrica]

    @pytest.mark.parametrize("markup", ["oj-ti-art", "class-less", "eli-subdivision"])
    def test_a_quoted_heading_before_the_acts_own_article_of_that_number(self, markup):
        # Synthetic: art. 1 quotes, in a table cell and with no «, an «Articolo 3» of another
        # act; the act's own art. 3 comes after it and is the one served and listed.
        quoted = ('<table><tr><td><p class="oj-ti-art">Articolo 3</p>'
                  '<p class="oj-normal">Testo citato di un altro atto.</p></td></tr></table>')
        html = ('<html><body><p class="oj-ti-art">Articolo 1</p><p class="oj-normal">Modifiche.</p>' + quoted +
                '<p class="oj-ti-art">Articolo 3</p><p class="oj-normal">Testo proprio dell\'articolo 3.</p></body></html>')
        if markup == "class-less":
            html = re.sub(r' class="[^"]*"', "", html)
        elif markup == "eli-subdivision":
            html = (re.sub(r' class="[^"]*"', "", html)
                    .replace("<body>", '<body><div class="eli-subdivision">')
                    .replace("<p>Articolo 3</p><p>Testo proprio", '</div><div class="eli-subdivision"><p>Articolo 3</p><p>Testo proprio'))
        text = extract_article_text(BeautifulSoup(html, "html.parser"), "3")
        assert text.split("\n")[:2] == ["Articolo 3", "Testo proprio dell'articolo 3."]
        result, _, _ = _parse_eurlex_tree(BeautifulSoup(html, "html.parser"), self.URL)
        assert [item["numero"] for item in result] == ["1", "3"]

    def test_a_page_without_tables_keeps_every_article(self):
        # The legacy ELI page of dir. 2002/58: class-less paragraphs, no table cells, no «.
        result, count, _ = _parse_eurlex_tree(soup_of("eprivacy_eli_legacy_trimmed.html"),
                                                    "https://eur-lex.europa.eu/eli/dir/2002/58/oj/ita")
        assert [item["numero"] for item in result] == [str(n) for n in range(1, 22)]
        text = extract_article_text(soup_of("eprivacy_eli_legacy_trimmed.html"), "15")
        assert text.startswith("Articolo 15")

    def test_the_index_reads_the_suffix(self):
        # Synthetic page (fixtures/eurlex/README.md): «Articolo 15 bis» is article 15-bis, not 15.
        result, _, metadata = _parse_eurlex_tree(soup_of("synthetic_oj_article_15_bis.html"), self.URL)
        assert [item["numero"] for item in result] == ["14", "15-bis", "16"]
        assert metadata["rubriche"]["15-bis"] == "Articolo inserito"
        text = extract_article_text(soup_of("synthetic_oj_article_15_bis.html"), "15-bis")
        assert text.startswith("Articolo\xa015\xa0bis")


class TestEliTitleOfTheItalianExpression:
    def test_the_italian_meta_of_another_resource_is_not_the_title(self):
        soup = soup_of("eprivacy_eli_legacy_trimmed.html")
        soup.find("meta", attrs={"property": "eli:title", "lang": "it"})["about"] = "http://data.europa.eu/eli/dir/2002/58/oj"
        assert _extract_eurlex_title(soup) == ""


class TestGluedHeading:
    """A class-less page whose heading and text share an element reads «Articolo 15 bisTesto…»:
    the ordinal glued to the text was not taken for one, and art. 15 asked was served art. 15 bis
    (found by the mcp-legal-it review). Synthetic page (fixtures/eurlex/README.md)."""

    def test_art_15_is_not_found(self):
        with pytest.raises(DocumentNotFoundError):
            extract_article_text(soup_of("synthetic_classless_glued_15_bis.html"), "15")

    @pytest.mark.parametrize("article", ["15 bis", "15-bis", "15bis"])
    def test_art_15_bis_is_served_from_its_heading(self, article):
        text = extract_article_text(soup_of("synthetic_classless_glued_15_bis.html"), article)
        assert text == "Articolo 15 bis\nTesto dell'articolo 15 bis."

    def test_the_index_lists_15_bis_once(self):
        result, _, _ = _parse_eurlex_tree(soup_of("synthetic_classless_glued_15_bis.html"),
                                                "https://eur-lex.europa.eu/eli/reg/2000/1/oj/ita")
        assert [item["numero"] for item in result] == ["14", "15-bis", "16"]

    @pytest.mark.parametrize("heading,article,heads", [
        ("Articolo 15 bisTesto", "15", False),
        ("Articolo 15terDisposizioni", "15", False),
        ("Articolo 1 Bisogna", "1", True),
        ("Articolo 1Terzi", "1", True),
        ("Articolo 1Testo", "1", True),
    ])
    def test_a_glued_ordinal_is_an_ordinal(self, heading, article, heads):
        from mcp_legal_it.lib.visualex.eurlex_text import _heads_article
        assert _heads_article(heading, f"Articolo {article}") is heads


class TestConsolidatedTitleFromTheFirstRun:
    def test_the_gdpr_consolidated_has_its_subject_in_title_doc_first(self):
        # CELEX 02016R0679-20160504: `title-doc-last` holds only «(Testo rilevante ai fini del SEE)».
        assert _extract_eurlex_title(soup_of("gdpr_consolidated_20160504_title_trimmed.html")) == (
            "relativo alla protezione delle persone fisiche con riguardo al trattamento dei dati personali, "
            "nonché alla libera circolazione di tali dati e che abroga la direttiva 95/46/CE "
            "(regolamento generale sulla protezione dei dati)"
        )

    def test_a_name_split_over_two_lines_is_no_date_line(self):
        # «DEL PARLAMENTO EUROPEO…» opens with «del» but holds no date: the subject follows the date.
        page = ('<div class="eli-main-title"><p class="oj-doc-ti">REGOLAMENTO (UE) 2016/679</p>'
                '<p class="oj-doc-ti">DEL PARLAMENTO EUROPEO E DEL CONSIGLIO</p>'
                '<p class="oj-doc-ti">del 27 aprile 2016</p>'
                '<p class="oj-doc-ti">relativo alla protezione delle persone fisiche</p></div>')
        assert _extract_eurlex_title(BeautifulSoup(page, "html.parser")) == "relativo alla protezione delle persone fisiche"
