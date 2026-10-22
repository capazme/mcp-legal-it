# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_eurlex_consolidated.py at 36ed6942: TestConsolidatedRubriche, TestEurlexTitle and
# TestConsolidatedTree (TestTreeFailuresAreNotKept tests VisuaLex's Playwright cache, not imported).
# Generated (scratch gen_eurlex_tests.py): VisuaLex's assertions as they are; the extractor and
# the tree reader are plain functions here, the fixtures are tests/fixtures/visualex/eurlex.
"""The EU tree, rubriche and title, as VisuaLex reads them (``eurlex_tree``)."""

from pathlib import Path

from bs4 import BeautifulSoup

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
