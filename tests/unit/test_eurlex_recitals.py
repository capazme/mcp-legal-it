# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_eurlex_recitals.py at b2f7a30f.
# Generated (scratch gen_eurlex_tests.py): VisuaLex's assertions as they are; the extractor and
# the tree reader are plain functions here, the fixtures are tests/fixtures/visualex/eurlex.
"""Recitals (considerando) of EU acts.

Two markups: the modern OJ page wraps each recital in
`<div class="eli-subdivision" id="rct_N">` with the number in the first table
cell; the legacy page (pre-2010 acts) has class-less `<p>(N) text</p>`
paragraphs between "considerando quanto segue:" and the enacting formula.
Consolidated texts have no preamble at all and must yield nothing.
"""
from pathlib import Path

from bs4 import BeautifulSoup

from mcp_legal_it.lib.visualex.eurlex_text import extract_recitals

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "eurlex"


def soup_of(name):
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


class TestModernMarkup:
    def test_reads_number_and_text_from_the_rct_divs(self):
        recitals = extract_recitals(soup_of("gdpr_oj_trimmed.html"))
        numbers = [r["number"] for r in recitals]
        assert numbers == ["1", "2", "3", "173"]
        assert recitals[0]["text"].startswith("La protezione delle persone fisiche")

    def test_the_number_cell_is_not_part_of_the_text(self):
        first = extract_recitals(soup_of("gdpr_oj_trimmed.html"))[0]
        assert not first["text"].startswith("(1)")

    def test_footnote_call_outs_are_dropped(self):
        # Recital 173 cites Dir. 2002/58/CE with a footnote "(18)" rendered as
        # <a>(<span class="oj-super oj-note-tag">18</span>)</a>.
        last = extract_recitals(soup_of("gdpr_oj_trimmed.html"))[-1]
        assert "(18)" not in last["text"]
        assert "direttiva 2002/58/CE" in last["text"]

    def test_multi_paragraph_recital_keeps_paragraph_breaks(self):
        html = (
            '<div class="eli-subdivision" id="rct_9"><table><tbody><tr>'
            '<td><p class="oj-normal">(9)</p></td>'
            '<td><p class="oj-normal">Primo capoverso.</p>'
            '<p class="oj-normal">Secondo capoverso.</p></td>'
            '</tr></tbody></table></div>'
        )
        assert extract_recitals(BeautifulSoup(html, "html.parser")) == [
            {"number": "9", "text": "Primo capoverso.\nSecondo capoverso."}
        ]


class TestLegacyMarkup:
    def test_reads_the_paragraph_sequence_after_the_preamble_marker(self):
        recitals = extract_recitals(soup_of("eprivacy_oj_legacy.html"))
        assert [r["number"] for r in recitals[:3]] == ["1", "2", "3"]
        assert recitals[0]["text"].startswith("La direttiva 95/46/CE")
        # Dir. 2002/58/CE has 49 recitals.
        assert recitals[-1]["number"] == "49"
        assert len(recitals) == 49

    def test_stops_at_the_enacting_formula(self):
        html = (
            "<p>considerando quanto segue:</p>"
            "<p>(1) Primo.</p><p>(2) Secondo.</p>"
            "<p>HANNO ADOTTATO LA PRESENTE DIRETTIVA:</p>"
            "<p>(1) Questo è il paragrafo 1 dell'articolo 1, non un considerando.</p>"
        )
        recitals = extract_recitals(BeautifulSoup(html, "html.parser"))
        assert [r["number"] for r in recitals] == ["1", "2"]

    def test_numbers_must_be_consecutive(self):
        # A "(4)" footnote reference paragraph between recitals is not recital 4
        # if recital 3 has not been seen.
        html = (
            "<p>considerando quanto segue:</p>"
            "<p>(1) Primo.</p><p>(4) Nota a piè di pagina.</p><p>(2) Secondo.</p>"
            "<p>HA ADOTTATO IL PRESENTE REGOLAMENTO:</p>"
        )
        recitals = extract_recitals(BeautifulSoup(html, "html.parser"))
        assert [r["number"] for r in recitals] == ["1", "2"]


class TestNoRecitals:
    def test_consolidated_text_yields_nothing(self):
        assert extract_recitals(soup_of("eprivacy_consolidated_20091219.html")) == []
        assert extract_recitals(soup_of("eidas_consolidated_20241018_trimmed.html")) == []

    def test_empty_document(self):
        assert extract_recitals(BeautifulSoup("<div>nulla</div>", "html.parser")) == []
