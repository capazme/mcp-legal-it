# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_eurlex_fixtures.py at 493a8dd1.
# Adapted: the fixtures folder is tests/fixtures/visualex/eurlex.
"""The EUR-Lex fixtures carry the markers the parsers are written against.

If a fixture is re-captured and a marker disappears, the parser tests would
fail for the wrong reason; this file names the real one.
"""
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "eurlex"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_modern_oj_fixture_has_recitals_articles_and_headings():
    html = _read("gdpr_oj_trimmed.html")
    for marker in ('id="rct_1"', 'id="rct_173"', 'class="oj-ti-art"', 'oj-sti-art',
                   'oj-ti-section-1', 'considerando quanto segue'):
        assert marker in html, marker


def test_legacy_oj_fixture_is_class_less():
    html = _read("eprivacy_oj_legacy.html")
    assert "considerando quanto segue" in html
    assert "<p>(1) " in html
    assert "oj-ti-art" not in html and "title-article-norm" not in html


def test_consolidated_fixtures_use_norm_classes():
    for name in ("eprivacy_consolidated_20091219.html",
                 "eidas_consolidated_20241018_trimmed.html"):
        html = _read(name)
        assert "title-article-norm" in html, name
        assert "stitle-article-norm" in html, name
        assert 'class="modref"' in html, name
        assert "rct_" not in html, name  # consolidated texts have no preamble


def test_consolidated_eprivacy_has_a_suffixed_article():
    html = _read("eprivacy_consolidated_20091219.html")
    assert 'Articolo 14 <span class="norm">bis</span>' in html


def test_consolidated_eidas_nests_modref_markers_inside_the_body():
    # A recent consolidation puts the "▼M2" marker inside `div.norm` and the
    # point grids, not beside the article title: the fixture must carry that
    # shape or the marker-leak test would pass for the wrong reason.
    html = _read("eidas_consolidated_20241018_trimmed.html")
    assert 'id="art_12"' in html
    assert 'id="art_24"' in html
    assert ('<div class="norm inline-element">\n'
            '<p class="norm inline-element">Un prestatore di servizi fiduciari qualificato '
            'che presta servizi fiduciari qualificati:</p>\n'
            '<p class="modref">') in html
    assert '>▼M2</a>\xa0—————</p>' in html, "the deleted-point placeholder lives in a modref"
