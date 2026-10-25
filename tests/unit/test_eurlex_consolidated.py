# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_eurlex_consolidated.py at b2f7a30f: TestConsolidatedArticleText, TestOneLinePerPoint,
# TestNoSpaceBeforePunctuation, TestStripAmendmentMarkers and TestWhitespaceRunsAreLinear (the tree,
# rubriche and title classes are in test_eurlex_tree.py); this package's own tests follow them.
# Generated (scratch gen_eurlex_tests.py): VisuaLex's assertions as they are; the extractor and
# the tree reader are plain functions here, the fixtures are tests/fixtures/visualex/eurlex.
"""EU consolidated texts: VisuaLex's reader, and how a consolidated version is asked for.

For regulations and directives the Official Journal page is the act as published. That is the
wrong text for an act that has been amended: Dir. 2002/58/CE without the 2009 amendment has no
cookie rule in art. 5(3). EUR-Lex publishes consolidated versions under a sector-0 CELEX
("02002L0058-20091219"); a request may name one and it is served (from CELLAR).
"""

import re
from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from mcp_legal_it.lib.visualex.eurlex_text import (
    DocumentNotFoundError,
    extract_article_text,
    strip_amendment_markers,
)
from mcp_legal_it.lib.visualex.eurlex_tree import _parse_eurlex_tree

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "eurlex"
CONSOLIDATED = "https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:02002L0058-20091219"


def soup_of(name):
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


class TestConsolidatedArticleText:
    def test_flat_consolidated_page(self):
        text = extract_article_text(
            soup_of("eprivacy_consolidated_20091219.html"), "5")
        lines = text.split("\n")
        assert lines[0] == "Articolo 5"
        assert lines[1] == "Riservatezza delle comunicazioni"
        assert lines[2].startswith("1. Gli Stati membri assicurano")
        assert "▼" not in text, "modref markers are not text"
        assert "Articolo 6" not in text, "the next article must not leak in"

    def test_suffixed_article_in_both_spellings(self):
        soup = soup_of("eprivacy_consolidated_20091219.html")
        hyphen = extract_article_text(soup, "14-bis")
        space = extract_article_text(soup, "14 bis")
        assert hyphen == space
        assert hyphen.startswith("Articolo 14 bis\nProcedura di comitato\n1. La Commissione")

    def test_subdivision_wrapped_consolidated_page(self):
        text = extract_article_text(
            soup_of("eidas_consolidated_20241018_trimmed.html"), "50")
        assert text.startswith("Articolo 50\nAbrogazione\n1. La direttiva 1999/93/CE")
        assert "2. I riferimenti alla direttiva abrogata" in text
        assert "Articolo 51" not in text

    def test_paragraph_numbers_are_separated_from_their_text(self):
        # eIDAS renders "1." in a <span class="no-parag"> beside the text; a
        # bare get_text(strip=True) would glue them into "1.Il presente".
        text = extract_article_text(
            soup_of("eidas_consolidated_20241018_trimmed.html"), "2")
        assert "\n1. " in text or text.split("\n")[2].startswith("1. ")

    def test_the_last_article_does_not_swallow_the_annex(self):
        # A flat page (no eli-subdivision wrapper) ends its articles with an
        # `title-annex-*` heading; the sibling walk must stop there.
        html = ('<html><body>'
                '<p class="title-article-norm">Articolo 52</p>'
                '<p class="stitle-article-norm">Entrata in vigore</p>'
                '<p class="norm">Il presente regolamento entra in vigore.</p>'
                '<p class="title-annex-1">ALLEGATO I</p>'
                '<p class="title-annex-2">REQUISITI PER I CERTIFICATI QUALIFICATI</p>'
                '<p class="norm">I certificati qualificati contengono:</p>'
                '</body></html>')
        text = extract_article_text(BeautifulSoup(html, "html.parser"), "52")
        assert text == "Articolo 52\nEntrata in vigore\nIl presente regolamento entra in vigore."

    def test_missing_article_raises(self):
        with pytest.raises(DocumentNotFoundError):
            extract_article_text(
                soup_of("eidas_consolidated_20241018_trimmed.html"), "999")

    def test_oj_pages_take_the_old_path(self):
        text = extract_article_text(soup_of("gdpr_oj_trimmed.html"), "1")
        assert text.startswith("Articolo 1")
        assert "Oggetto e finalità" in text

    def test_oj_missing_article_is_not_served_as_a_longer_number(self):
        # "Articolo 17" starts with "Articolo 1": a page without art. 1 used to
        # answer a request for it with art. 17 (inventory row 3.1).
        soup = soup_of("gdpr_oj_trimmed.html")
        soup.find("p", class_="oj-ti-art", string="Articolo 1").decompose()
        with pytest.raises(DocumentNotFoundError):
            extract_article_text(soup, "1")
        text17 = extract_article_text(soup, "17")
        assert text17.startswith("Articolo 17")

    def test_oj_missing_article_in_a_class_less_page(self):
        # The legacy page reaches the eli-subdivision strategy last; the same
        # guard holds there.
        html = ('<html><body><div class="eli-subdivision">'
                '<p>Articolo 17</p><p>Diritto alla cancellazione</p>'
                '</div></body></html>')
        with pytest.raises(DocumentNotFoundError):
            extract_article_text(BeautifulSoup(html, "html.parser"), "1")

    @pytest.mark.parametrize("markup", ["oj-ti-art, nbsp", "oj-ti-art", "class with art", "class-less", "eli-subdivision"])
    def test_oj_article_15_is_never_served_as_15_bis(self, markup):
        # Synthetic page (fixtures/eurlex/README.md): its only article 15 is «Articolo 15 bis».
        # A request for art. 15 was served art. 15 bis, the wrong article as the one asked
        # (the class of inventory row 3.1). The suffix served must be the one asked, none for none.
        html = (FIXTURES / "synthetic_oj_article_15_bis.html").read_text(encoding="utf-8")
        if markup != "oj-ti-art, nbsp":
            html = html.replace("&nbsp;", " ")
        if markup == "class with art":
            html = html.replace('class="oj-ti-art"', 'class="title-art"')
        elif markup == "class-less":
            html = re.sub(r' class="[^"]*"', "", html)
        elif markup == "eli-subdivision":
            html = re.sub(r' class="[^"]*"', "", html).replace("<body>", '<body><div class="eli-subdivision">')
        with pytest.raises(DocumentNotFoundError):
            extract_article_text(BeautifulSoup(html, "html.parser"), "15")
        if markup != "eli-subdivision":  # one subdivision holds every article: no boundary to test
            text14 = extract_article_text(BeautifulSoup(html, "html.parser"), "14")
            assert text14.split("\n")[:3] == ["Articolo\xa014" if "nbsp" in markup else "Articolo 14",
                                               "Disposizioni generali", "Testo dell'articolo 14."]
        # The article that is there opens, asked in any spelling, non-breaking spaces included.
        for spelling in ("15 bis", "15-bis", "15bis"):
            asked = extract_article_text(BeautifulSoup(html, "html.parser"), spelling)
            assert asked.replace("\xa0", " ").split("\n")[:2] == ["Articolo 15 bis", "Articolo inserito"], spelling

    @pytest.mark.parametrize("heading,article,heads", [
        ("Articolo 15 bis", "15", False),
        ("Articolo 15bis", "15", False),
        ("Articolo 15-ter", "15", False),
        ("Articolo 15 quinquiesdecies", "15", False),
        ("Articolo 15 bis", "15 bis", True),
        ("Articolo 15 bis decies", "15 bis", False),
        ("Articolo 150", "15", False),
        ("Articolo 15", "15", True),
        ("Articolo 15Terzi", "15", True),     # a rubrica run on, not an ordinal
        ("Articolo 15 Bisogna", "15", True),
    ])
    def test_the_number_ends_with_the_heading(self, heading, article, heads):
        from mcp_legal_it.lib.visualex.eurlex_text import _heads_article
        assert _heads_article(heading, f"Articolo {article}") is heads

    def test_inline_amendment_markers_are_not_text(self):
        soup = soup_of("eprivacy_consolidated_20091219.html")
        text4 = extract_article_text(soup, "4")
        assert text4.split("\n")[1] == "Sicurezza del trattamento"
        text13 = extract_article_text(soup, "13")
        assert "►" not in text13 and "◄" not in text13

    @pytest.mark.parametrize("fixture", [
        "eprivacy_consolidated_20091219.html",
        "eidas_consolidated_20241018_trimmed.html",
    ])
    def test_no_article_carries_a_marker_or_a_deletion_placeholder(self, fixture):
        # Every article the tree yields, on both consolidated markups: no
        # "►M2 … ◄" inline marker, no "▼M2" block marker, no "—————" left by a
        # deleted point. The markers are not text (gotcha 23).
        soup = soup_of(fixture)
        result, count, _ = _parse_eurlex_tree(soup, CONSOLIDATED, link=False, details=False)
        assert count > 0
        for item in result:
            text = extract_article_text(soup, item["numero"])
            assert not re.search(r"[►◄▼]", text), (fixture, item["numero"])
            assert not re.search(r"—{3,}", text), (fixture, item["numero"])

    def test_markers_nested_in_the_body_are_not_text(self):
        # On the 2024 eIDAS consolidation the "▼M2" / "▼B" markers sit inside
        # `div.norm` and the point grids, not beside the title, so a class
        # check on the article's siblings never sees them: art. 12 read
        # "…internazionali; ▼M2 c) facilita…" and art. 24 "…qualificati: ▼M2
        # a) informa…", with a "▼M2 ————— ▼B" where a point was deleted.
        soup = soup_of("eidas_consolidated_20241018_trimmed.html")
        text12 = extract_article_text(soup, "12")
        assert "▼" not in text12 and "—————" not in text12
        assert "norme europee e internazionali;\nc) facilita" in text12
        assert "8. Entro il 18 settembre 2025" in text12
        text24 = extract_article_text(soup, "24")
        assert "▼" not in text24 and "—————" not in text24
        assert "servizi fiduciari qualificati:\na) informa l’organismo di vigilanza" in text24
        assert "lettera i);\nk) se i prestatori" in text24


class TestOneLinePerPoint:
    """Ruling: one line per lettered point, wherever EUR-Lex put the grid.

    The OJ path already gives one row per line (`extract_table_text`); the
    consolidated text is the offset space the archive anchors on (gotcha 23),
    so its shape must not depend on whether the points are siblings of the
    title, nested in the paragraph's own `div.norm`, or class-less divs.
    """

    def test_sibling_points_are_one_line_each(self):
        # eIDAS art. 3: 48 definitions as `grid-list` siblings of the title.
        text = extract_article_text(
            soup_of("eidas_consolidated_20241018_trimmed.html"), "3")
        lines = text.split("\n")
        assert lines[:3] == ["Articolo 3", "Definizioni",
                             "Ai fini del presente regolamento si intende per:"]
        assert lines[3].startswith("1) «identificazione elettronica»")
        assert lines[4].startswith("2) «mezzi di identificazione elettronica»")
        assert sum(1 for line in lines if re.match(r"\d+\) ", line)) >= 40

    def test_points_nested_in_a_paragraph_start_their_own_lines(self):
        # eIDAS art. 12 §3: the grid sits inside the paragraph's div.norm.
        text = extract_article_text(
            soup_of("eidas_consolidated_20241018_trimmed.html"), "12")
        lines = text.split("\n")
        i = lines.index("3. Il quadro di interoperabilità risponde ai seguenti criteri:")
        assert lines[i + 1].startswith("a) mira a essere neutrale")
        assert lines[i + 2].startswith("b) segue, ove possibile")
        assert lines[i + 3].startswith("c) facilita l’applicazione")
        assert lines[i + 4].startswith("4. Il quadro di interoperabilità è composto da:")

    def test_sub_points_of_a_point_start_their_own_lines(self):
        # eIDAS art. 3 n. 16 lists a) to d) inside the definition.
        text = extract_article_text(
            soup_of("eidas_consolidated_20241018_trimmed.html"), "3")
        lines = text.split("\n")
        i = next(k for k, line in enumerate(lines) if line.startswith("16) «servizio fiduciario»"))
        assert lines[i].endswith("elementi seguenti:")
        assert lines[i + 1].startswith("a) il rilascio di certificati")
        assert lines[i + 2].startswith("b) la convalida di certificati")
        j = next(k for k, line in enumerate(lines) if line.startswith("17) «servizio fiduciario qualificato»"))
        assert all(re.match(r"[a-z]\) ", line) for line in lines[i + 1:j]), "n. 16 ends where n. 17 starts"

    def test_lettered_points_of_the_flat_page_are_text(self):
        # ePrivacy art. 2 renders each point as a class-less
        # <div style="margin-left: 24pt"><p class="norm">a) …</p></div>; the
        # walk used to drop them all — 13 points across art. 2, 4 and 10.
        soup = soup_of("eprivacy_consolidated_20091219.html")
        text = extract_article_text(soup, "2")
        lines = text.split("\n")
        assert lines[3] == "Si applicano inoltre le seguenti definizioni:"
        assert lines[4].startswith("a) «utente»: qualsiasi persona fisica")
        assert lines[5].startswith("b) «dati relativi al traffico»")
        assert lines[-1].startswith("i) «violazione dei dati personali»")
        assert len(lines) == 12  # e) was deleted by Dir. 2009/136/CE
        text4 = extract_article_text(soup, "4")
        assert sum(1 for line in text4.split("\n") if line.startswith("— ")) == 3
        text10 = extract_article_text(soup, "10")
        assert text10.split("\n")[3].startswith("a) possa annullare, in via temporanea")

    def test_the_openings_the_other_tests_pin_are_unchanged(self):
        eidas = soup_of("eidas_consolidated_20241018_trimmed.html")
        text1 = extract_article_text(eidas, "1")
        assert text1.startswith("Articolo 1\nOggetto\n")
        text50 = extract_article_text(eidas, "50")
        assert text50.startswith("Articolo 50\nAbrogazione\n1. La direttiva 1999/93/CE")


class TestNoSpaceBeforePunctuation:
    """EUR-Lex closes a span early and the get_text separator lands before
    the punctuation: "1 quater ." where "1 bis." reads correctly, "f bis )",
    "articolo 14 bis , paragrafo 2". Normalised in the consolidated path only,
    before any text is stored."""

    def test_unit_cases(self):
        from mcp_legal_it.lib.visualex.eurlex_text import _cons_text
        assert _cons_text(BeautifulSoup("<p>1 quater .</p>", "html.parser")) == "1 quater."
        assert _cons_text(BeautifulSoup("<p>lettera a )</p>", "html.parser")) == "lettera a)"
        assert _cons_text(BeautifulSoup("<p>articolo 14 bis , paragrafo 2 ;</p>", "html.parser")) == \
            "articolo 14 bis, paragrafo 2;"
        assert _cons_text(BeautifulSoup("<p>1. Il presente regolamento</p>", "html.parser")) == \
            "1. Il presente regolamento"
        # The opening side: a footnote reference reads "( 1 )" on the page.
        assert _cons_text(BeautifulSoup("<p>nota ( 1 ) fine</p>", "html.parser")) == "nota (1) fine"
        assert _cons_text(BeautifulSoup("<p>« testo</p>", "html.parser")) == "«testo"
        # A real footnote reference: literal parens around a superscript link.
        assert _cons_text(BeautifulSoup(
            '<p>del Consiglio (<a href="#E0001"><span class="superscript">1</span></a>).</p>',
            "html.parser")) == "del Consiglio (1)."

    def test_the_real_lines_that_had_the_wart(self):
        eidas = soup_of("eidas_consolidated_20241018_trimmed.html")
        text24 = extract_article_text(eidas, "24")
        lines = text24.split("\n")
        assert any(line.startswith("1 quater. Entro il 21 maggio 2025") for line in lines)
        assert any(line.startswith("f bis) fatto salvo") for line in lines)
        assert " ." not in text24 and " )" not in text24 and " ," not in text24
        eprivacy = soup_of("eprivacy_consolidated_20091219.html")
        text4 = extract_article_text(eprivacy, "4")
        assert any(line.startswith("1 bis. Fatta salva la direttiva 95/46/CE") for line in text4.split("\n"))
        assert "articolo 14 bis, paragrafo 2." in text4

    def test_footnote_references_read_as_the_page_shows_them(self):
        # "( 1 )" — literal parens around a superscript link — is "(1)".
        eidas = soup_of("eidas_consolidated_20241018_trimmed.html")
        text2 = extract_article_text(eidas, "2")
        assert "del Parlamento europeo e del Consiglio (1)." in text2
        text3 = extract_article_text(eidas, "3")
        assert "del Parlamento europeo e del Consiglio (2);" in text3
        eprivacy = soup_of("eprivacy_consolidated_20091219.html")
        text2 = extract_article_text(eprivacy, "2")
        assert "(direttiva quadro) (1)." in text2
        assert "( " not in text2 and "( " not in text3

    @pytest.mark.parametrize("fixture", [
        "eprivacy_consolidated_20091219.html",
        "eidas_consolidated_20241018_trimmed.html",
    ])
    def test_no_line_keeps_a_space_before_punctuation(self, fixture):
        soup = soup_of(fixture)
        result, _, _ = _parse_eurlex_tree(soup, CONSOLIDATED, link=False, details=False)
        for item in result:
            text = extract_article_text(soup, item["numero"])
            assert not re.search(r"\s[.,;:)]", text), (fixture, item["numero"])
            assert not re.search(r"[(«]\s", text), (fixture, item["numero"])

    def test_the_oj_path_is_untouched(self):
        # The normalisation lives in _cons_text; an OJ page never reaches it.
        with patch("mcp_legal_it.lib.visualex.eurlex_text._cons_text",
                   side_effect=AssertionError("the OJ path must not use _cons_text")):
            text = extract_article_text(soup_of("gdpr_oj_trimmed.html"), "4")
        assert text.startswith("Articolo 4")
        assert "Definizioni" in text


class TestStripAmendmentMarkers:
    def test_examples(self):
        assert strip_amendment_markers("►M2 Sicurezza del trattamento ◄") == "Sicurezza del trattamento"
        assert strip_amendment_markers("personali»: ◄ violazione") == "personali»: violazione"
        assert strip_amendment_markers("Articolo 5") == "Articolo 5"


class TestWhitespaceRunsAreLinear:
    """`\\s*[►◄▼]…` and `\\s+([.,;:)])` restarted at every blank of a run and scanned the rest of
    it each time: 0.85 s a pass on 20,000 blanks, three passes per element (consolidated path).
    Matched now only from a run's first blank, with the same result."""

    OLD_MARK = re.compile(r"\s*[►◄▼](?:[A-Z]\d*)?\s*")
    OLD_PUNCT = re.compile(r"\s+([.,;:)])")

    def test_same_result_as_the_quadratic_patterns(self):
        import random
        from mcp_legal_it.lib.visualex.eurlex_text import _SPACE_BEFORE_PUNCTUATION
        from mcp_legal_it.lib.visualex.eurlex_text import _AMENDMENT_MARK

        rng = random.Random(20261022)
        alphabet = [" ", " ", "\xa0", "\n", "\t", "►", "◄", "▼", "M", "B", "2", "a", "x", ".", ",", ";", ")", "("]
        for _ in range(5000):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24)))
            assert _AMENDMENT_MARK.sub(" ", text) == self.OLD_MARK.sub(" ", text), repr(text)
            assert _SPACE_BEFORE_PUNCTUATION.sub(r"\1", text) == self.OLD_PUNCT.sub(r"\1", text), repr(text)

    @pytest.mark.parametrize("blank", [" ", "\xa0", "\n"])
    def test_a_long_run_of_blanks_costs_linear_time(self, blank):
        import time
        from mcp_legal_it.lib.visualex.eurlex_text import _cons_text

        text = "x" + blank * 50_000 + "x"
        start = time.perf_counter()
        assert strip_amendment_markers(text) == (text if blank == "\n" else "x x")
        _cons_text(BeautifulSoup(f"<p>{text}</p>", "html.parser"))
        # Before: about 5 s for these 50,000 blanks. A linear pass takes milliseconds.
        assert time.perf_counter() - start < 0.5


# --- this package's: the model, the api, the page cache --------------------------------

CONSOLIDATED = "https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:02002L0058-20091219"
OJ = "https://eur-lex.europa.eu/eli/dir/2002/58/oj/ita"


class TestModel:
    # VisuaLex's TestModel, on this package's Norma (``url()`` is a method here).
    def test_without_the_field_the_oj_url_is_unchanged(self):
        from mcp_legal_it.lib.visualex.models import Norma

        assert Norma(tipo_atto="direttiva ue", data="2002", numero_atto="58").url() == OJ

    def test_the_field_selects_the_consolidated_url(self):
        from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

        norma = Norma(tipo_atto="direttiva ue", data="2002", numero_atto="58",
                      celex_consolidated="02002L0058-20091219")
        assert norma.url() == CONSOLIDATED
        assert NormaVisitata(norma=norma, numero_articolo="5").url() == CONSOLIDATED

    def test_str_names_the_consolidated_version(self):
        from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

        cons = Norma(tipo_atto="direttiva ue", data="2002", numero_atto="58", celex_consolidated="02002L0058-20091219")
        assert str(cons).endswith("2002, n. 58 (consolidato 02002L0058-20091219)")
        assert str(NormaVisitata(norma=cons, numero_articolo="99")).endswith("(consolidato 02002L0058-20091219) art. 99")

    def test_the_page_is_cellar_s_sector_0_document(self):
        from mcp_legal_it.lib.visualex.models import Norma
        from mcp_legal_it.lib.visualex.scraper import _eurlex_urls

        cons = Norma(tipo_atto="direttiva ue", data="2002", numero_atto="58", celex_consolidated="02002L0058-20091219")
        assert _eurlex_urls(cons) == (
            "https://publications.europa.eu/resource/celex/02002L0058-20091219",
            "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:02002L0058-20091219")


class TestTheApi:
    def _ref(self, **kw):
        from mcp_legal_it import api

        base = dict(tipo_atto="direttiva ue", numero_articolo="5", data="2002", numero_atto="58")
        return api.riferimento_da_parametri(**{**base, **kw})

    def test_a_consolidated_version_is_carried(self):
        nd = self._ref(celex_consolidated="02002L0058-20091219").norma_data[0]
        assert nd.celex_consolidated == "02002L0058-20091219" and nd.url == CONSOLIDATED
        assert self._ref().norma_data[0].celex_consolidated is None

    @pytest.mark.parametrize("celex", ["32002L0058", "02002L0058-20091219\n", "02002L0058-2009121", "02002L0058-٢٠٠٩١٢١٩"])
    def test_a_malformed_celex_is_refused(self, celex):
        r = self._ref(celex_consolidated=celex)
        assert r.esito == "riferimento_non_valido" and "non valido" in r.errore

    @pytest.mark.parametrize("celex", ["02016R0679-20160504", "02002R0058-20091219", "02003L0058-20091219"])
    def test_another_act_s_consolidation_is_refused(self, celex):
        r = self._ref(celex_consolidated=celex)
        assert r.esito == "riferimento_non_valido" and "non è una versione di questo atto" in r.errore

    def test_only_eu_regulations_and_directives(self):
        from mcp_legal_it import api

        r = api.riferimento_da_parametri("legge", "1", data="1990-08-07", numero_atto="241",
                                         celex_consolidated="02002L0058-20091219")
        assert r.esito == "riferimento_non_valido" and "solo per atti EUR-Lex" in r.errore

    def test_an_annex_of_a_consolidation_is_not_served_yet(self):
        r = self._ref(numero_articolo="allegato I", celex_consolidated="02002L0058-20091219")
        assert r.esito == "non_supportata" and "consolidata" in r.errore


class _Pages:
    """CELLAR, faked: the pages by URL, every request counted."""

    def __init__(self, pages):
        self.pages, self.asked, self.served_from = pages, [], {}

    def __call__(self, fonte, **kwargs):
        pages, asked, served_from = self.pages, self.asked, self.served_from

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
                return _Resp(served_from.get(url, url), pages[url])

        return _Client()


@pytest.fixture
def cellar(monkeypatch):
    from mcp_legal_it.lib.visualex import scraper

    pages = _Pages({
        "https://publications.europa.eu/resource/celex/02002L0058-20091219":
            (FIXTURES / "eprivacy_consolidated_20091219.html").read_text(encoding="utf-8"),
        "https://publications.europa.eu/resource/celex/32002L0058":
            (FIXTURES / "eprivacy_oj_legacy.html").read_text(encoding="utf-8"),
    })
    monkeypatch.setattr(scraper, "async_client", pages)
    return pages


class TestReading:
    async def test_the_consolidated_text_is_read_and_one_page_serves_the_act(self, cellar):
        from mcp_legal_it import api

        def ref(art):
            return api.riferimento_da_parametri("direttiva ue", art, data="2002", numero_atto="58",
                                                celex_consolidated="02002L0058-20091219").norma_data[0]

        t5 = await api.testo_articolo(ref("5"), canale="html")
        t14 = await api.testo_articolo(ref("14-bis"), canale="html")
        assert t5.esito == "trovato" and t5.article_text.startswith("Articolo 5\nRiservatezza delle comunicazioni\n1. ")
        assert "▼" not in t5.article_text
        assert t14.article_text.startswith("Articolo 14 bis\nProcedura di comitato")
        assert len(cellar.asked) == 1  # one page, two articles
        assert t5.url == "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:02002L0058-20091219"

    async def test_the_oj_text_and_the_consolidation_are_different_pages(self, cellar):
        from mcp_legal_it import api

        oj = api.riferimento_da_parametri("direttiva ue", "5", data="2002", numero_atto="58").norma_data[0]
        cons = api.riferimento_da_parametri("direttiva ue", "5", data="2002", numero_atto="58",
                                            celex_consolidated="02002L0058-20091219").norma_data[0]
        t_oj = await api.testo_articolo(oj, canale="html")
        t_cons = await api.testo_articolo(cons, canale="html")
        assert t_oj.article_text != t_cons.article_text and len(cellar.asked) == 2

    async def test_an_article_the_consolidation_lacks_is_not_found(self, cellar):
        from mcp_legal_it import api

        nd = api.riferimento_da_parametri("direttiva ue", "99", data="2002", numero_atto="58",
                                          celex_consolidated="02002L0058-20091219").norma_data[0]
        t = await api.testo_articolo(nd, canale="html")
        assert t.esito == "articolo_non_trovato" and t.article_text == ""


class TestThePageCache:
    def test_a_page_is_kept_on_disk_and_read_back(self, tmp_path, monkeypatch):
        from mcp_legal_it.lib.visualex import pagine_eurlex as pe

        monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
        pe.scrivi("https://publications.europa.eu/resource/celex/X", "<html>pagina</html>",
                  "http://publications.europa.eu/resource/cellar/abc/DOC_1")
        pe.svuota_memoria()
        assert pe.leggi("https://publications.europa.eu/resource/celex/X") == (
            "<html>pagina</html>", "http://publications.europa.eu/resource/cellar/abc/DOC_1")
        assert len(list((tmp_path / "eurlex_pagine").glob("*.json.gz"))) == 1

    def test_an_old_or_broken_record_is_dropped(self, tmp_path, monkeypatch):
        import gzip
        import json
        import time

        from mcp_legal_it.lib.visualex import pagine_eurlex as pe

        monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
        url = "https://publications.europa.eu/resource/celex/Y"
        pe.scrivi(url, "<html>vecchia</html>")
        path = pe._path(url)
        path.write_bytes(gzip.compress(json.dumps({"schema": pe.SCHEMA, "url": url, "html": "<html>vecchia</html>",
                                                   "servito": url, "salvato": time.time() - pe.TTL_SECONDI - 1}).encode()))
        pe.svuota_memoria()
        assert pe.leggi(url) is None and not path.exists()
        path.write_bytes(b"not gzip")
        assert pe.leggi(url) is None and not path.exists()

    def test_nothing_on_disk_with_the_cache_off(self, tmp_path, monkeypatch):
        from mcp_legal_it.lib.visualex import pagine_eurlex as pe

        monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
        monkeypatch.setenv("LEGAL_CACHE", "off")
        pe.scrivi("https://publications.europa.eu/resource/celex/Z", "<html>p</html>")
        assert not (tmp_path / "eurlex_pagine").exists()
        assert pe.leggi("https://publications.europa.eu/resource/celex/Z")[0] == "<html>p</html>"  # memory only


async def test_a_kept_page_reports_the_url_it_was_served_from(cellar, monkeypatch):
    # The provenance (_meta fonti_consultate) is the same whether the page was fetched or kept:
    # CELLAR's redirect end, not the CELEX URL asked.
    from mcp_legal_it.lib.visualex import scraper
    from mcp_legal_it.lib.visualex.models import Norma

    fine = "http://publications.europa.eu/resource/cellar/cb5af945/DOC_1"
    cellar.served_from = {"https://publications.europa.eu/resource/celex/32002L0058": fine}
    notate = []
    monkeypatch.setattr(scraper, "note_source", lambda fonte, url: notate.append((fonte, url)))
    norma = Norma(tipo_atto="direttiva ue", data="2002", numero_atto="58")
    await scraper._fetch_eurlex_html(norma)
    await scraper._fetch_eurlex_html(norma)
    assert notate == [("eur_lex", fine), ("eur_lex", fine)] and len(cellar.asked) == 1


class TestReviewOf74:
    @pytest.mark.parametrize("art", ["rec_2", "rec_42"])
    def test_a_recital_of_a_consolidation_is_not_served(self, art):
        # A consolidated text has no preamble: its «(2)» paragraphs are footnotes.
        from dataclasses import replace

        from mcp_legal_it import api

        r = api.riferimento_da_parametri("direttiva ue", art, data="2002", numero_atto="58",
                                         celex_consolidated="02002L0058-20091219")
        assert r.esito == "non_supportata" and "considerando" in r.errore
        oj = api.riferimento_da_parametri("direttiva ue", art, data="2002", numero_atto="58").norma_data[0]
        assert oj.celex_consolidated is None

    async def test_a_recital_given_as_normadati_with_a_consolidation(self, cellar):
        from dataclasses import replace

        from mcp_legal_it import api

        oj = api.riferimento_da_parametri("direttiva ue", "rec_2", data="2002", numero_atto="58").norma_data[0]
        t = await api.testo_articolo(replace(oj, celex_consolidated="02002L0058-20091219"), canale="html")
        assert t.esito == "non_supportata" and t.article_text == "" and cellar.asked == []

    async def test_an_empty_page_is_not_kept(self, cellar):
        # An empty 200 kept a day answered «Could not fetch» for every article of the act.
        from mcp_legal_it import api

        url = "https://publications.europa.eu/resource/celex/32002L0058"
        pagina = cellar.pages[url]
        cellar.pages[url] = ""
        nd = api.riferimento_da_parametri("direttiva ue", "5", data="2002", numero_atto="58").norma_data[0]
        assert (await api.testo_articolo(nd, canale="html")).esito != "trovato"
        cellar.pages[url] = pagina
        t = await api.testo_articolo(nd, canale="html")
        assert t.esito == "trovato" and t.article_text.startswith("Articolo 5") and len(cellar.asked) == 2

    def test_what_counts_as_a_page(self):
        from mcp_legal_it.lib.visualex.scraper import _pagina_eurlex

        for name in ("gdpr_oj_trimmed.html", "eprivacy_oj_legacy.html", "eprivacy_consolidated_20091219.html",
                     "eidas_consolidated_20241018_trimmed.html"):
            assert _pagina_eurlex((FIXTURES / name).read_text(encoding="utf-8")), name
        assert not _pagina_eurlex("") and not _pagina_eurlex("<html><body>Errore</body></html>")

    @pytest.mark.parametrize("html", [
        '<html><body><p class="oj-ti-art">Articolo 15 bis</p><p class="oj-normal">Testo del 15-bis.</p></body></html>',
        '<html><body><div class="eli-subdivision"><p>Articolo 15 bis</p><p>Testo del 15-bis.</p></div></body></html>',
    ])
    def test_a_plain_number_is_not_served_its_suffixed_neighbour(self, html):
        # VisuaLex's heading check stops a digit ("Articolo 17" is not art. 1), not a suffix.
        from mcp_legal_it.lib.visualex.scraper import _extract_eurlex_article

        assert _extract_eurlex_article(html, "15") == "[Articolo 15 non trovato nel documento EUR-Lex]"
        assert "Testo del 15-bis" in _extract_eurlex_article(html, "15 bis")

    def test_a_plain_number_whose_rubrica_reads_like_a_word_is_served(self):
        from mcp_legal_it.lib.visualex.scraper import _extract_eurlex_article

        html = '<html><body><p class="oj-ti-art">Articolo 15</p><p class="oj-sti-art">Bis in idem</p></body></html>'
        assert _extract_eurlex_article(html, "15").startswith("Articolo 15")
