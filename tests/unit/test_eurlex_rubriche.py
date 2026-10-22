# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_eurlex_rubriche.py at 36ed6942.
# Generated (scratch gen_eurlex_tests.py): VisuaLex's assertions as they are; the extractor and
# the tree reader are plain functions here, the fixtures are tests/fixtures/visualex/eurlex.
"""Article titles for EUR-Lex acts.

Unlike Normattiva — whose article tree carries bare numbers and whose titles
live in a separate 10 MB Akoma Ntoso export — EUR-Lex puts the title in the very
page the tree is parsed from, as an `oj-sti-art` right after the `oj-ti-art`
carrying the number. So the whole index can be labelled without one extra
request, and the extraction happens during the same parse.
"""
from bs4 import BeautifulSoup

from mcp_legal_it.lib.visualex.eurlex_tree import _extract_eurlex_rubriche


def soup(html):
    return BeautifulSoup(html, "html.parser")


class TestEurlexRubriche:
    def test_pairs_the_number_with_the_title_that_follows(self):
        html = (
            '<p class="oj-ti-art">Articolo 1</p>'
            '<p class="oj-sti-art">Oggetto e finalità</p>'
            '<p>1. Il presente regolamento…</p>'
            '<p class="oj-ti-art">Articolo 17</p>'
            '<p class="oj-sti-art">Diritto alla cancellazione</p>'
        )
        assert _extract_eurlex_rubriche(soup(html)) == {
            "1": "Oggetto e finalità",
            "17": "Diritto alla cancellazione",
        }

    def test_accepts_the_eli_title_spelling(self):
        html = (
            '<p class="oj-ti-art">Articolo 2</p>'
            '<p class="eli-title">Ambito di applicazione materiale</p>'
        )
        assert _extract_eurlex_rubriche(soup(html)) == {"2": "Ambito di applicazione materiale"}

    def test_english_documents_work_too(self):
        html = '<p class="oj-ti-art">Article 4</p><p class="oj-sti-art">Definitions</p>'
        assert _extract_eurlex_rubriche(soup(html)) == {"4": "Definitions"}

    def test_an_article_without_a_title_is_absent_not_empty(self):
        html = (
            '<p class="oj-ti-art">Articolo 1</p>'
            '<p>1. Testo senza rubrica…</p>'
            '<p class="oj-ti-art">Articolo 2</p>'
            '<p class="oj-sti-art">Definizioni</p>'
        )
        assert _extract_eurlex_rubriche(soup(html)) == {"2": "Definizioni"}

    def test_the_title_marker_is_not_mistaken_for_a_number(self):
        # `oj-sti-art` contains "ti-art" as a substring; a naive match would
        # treat every title as an article marker and pair it with the next one.
        html = (
            '<p class="oj-ti-art">Articolo 1</p>'
            '<p class="oj-sti-art">Oggetto e finalità</p>'
        )
        assert list(_extract_eurlex_rubriche(soup(html))) == ["1"]

    def test_empty_document(self):
        assert _extract_eurlex_rubriche(soup("<div>nulla</div>")) == {}
