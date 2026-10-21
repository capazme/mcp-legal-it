# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_normattiva_validity.py at eca698dc.
# Adapted: the imports name this package; TestReadValidity (VisuaLex's cache reader, not
# imported) and the tz-database case (today comes from lib/_clock here) left out.
"""What a Normattiva article page says about its own validity window.

The pages are third-party HTML. The tests read the captured pages in
`fixtures/normattiva/` for the facts that are on them, and build the rest in the
portal's own markup: a "Testo in vigore" block in front of a `div.bodyTesto`.
`test_normattiva_validity_live.py` repeats the main cases against the portal
(`-m live`).
"""
import time
from datetime import date

import pytest

from mcp_legal_it.lib.visualex import normattiva_validity as validity_module
from mcp_legal_it.lib.visualex.normattiva_validity import (
    ValidationError,
    extract_validity,
    is_historical_request,
    reject_future_version_date,
)

from .validity_pages import page, synthetic, window


class TestWindowShapes:
    def test_a_closed_window_is_a_historical_text(self):
        v = extract_validity(
            synthetic(dal="25-12-2003", al="29-12-2007", version=7, updated="11/08/2026"), article="7",
        )
        assert v == {
            "state": "historical",
            "valid_from": "2003-12-25",
            "valid_to": "2007-12-29",
            "version_number": 7,
            "act_updated": "2026-08-11",
            "request_in_window": None,
        }

    def test_an_open_window_is_the_text_in_force(self):
        v = extract_validity(synthetic(dal="28-12-2025"), article="7")
        assert v["state"] == "current"
        assert (v["valid_from"], v["valid_to"]) == ("2025-12-28", None)

    def test_a_window_that_only_ends_is_an_article_that_did_not_exist_yet(self):
        v = extract_validity(
            synthetic(al="12-9-2014", content="<span>ARTICOLO NON ANCORA ESISTENTE O VIGENTE</span>"), article="7",
        )
        assert v["state"] == "not_yet"
        assert (v["valid_from"], v["valid_to"]) == (None, "2014-09-12")

    def test_a_window_that_only_ends_is_not_guessed_when_the_notice_is_missing(self):
        assert extract_validity(synthetic(al="12-9-2014"), article="7") is None

    def test_dates_are_day_first_and_unpadded(self):
        v = extract_validity(synthetic(dal="1-2-2003"), article="7")
        assert v["valid_from"] == "2003-02-01"

    def test_a_date_that_is_not_a_day_makes_the_whole_window_unreadable(self):
        assert extract_validity(synthetic(dal="31-2-2020"), article="7") is None

    @pytest.mark.parametrize("separator", [" ", " - ", ", ", " – "])
    def test_what_sits_between_the_two_dates_does_not_matter(self, separator):
        raw = synthetic(dal="25-12-2003").replace(
            "</div><div", f'{separator}<span>al:</span> <span>&nbsp;29-12-2007</span></div><div', 1,
        )
        v = extract_validity(raw, article="7")
        assert (v["valid_from"], v["valid_to"]) == ("2003-12-25", "2007-12-29")

    def test_a_page_without_the_block_says_nothing(self):
        raw = '<html><body><div class="bodyTesto"><h2>Art. 7</h2>testo</div></body></html>'
        assert extract_validity(raw, article="7") is None

    def test_a_block_that_states_no_window_says_nothing(self):
        assert extract_validity(synthetic(), article="7") is None

    def test_a_page_without_a_body_says_nothing(self):
        assert extract_validity(f"<html><body>{window(dal='1-1-2000')}</body></html>", article="7") is None

    @pytest.mark.parametrize("raw", ["", None, "<html></html>", "plain text"])
    def test_garbage_says_nothing(self, raw):
        assert extract_validity(raw, article="7") is None


class TestWindowEndingAgainstToday:
    """A closed window is historical only when its last day is before today (Rome)."""

    TODAY = date(2026, 10, 2)

    def read(self, **kwargs):
        today = kwargs.pop("today", self.TODAY)
        return extract_validity(synthetic(**kwargs), article="7", today=today)

    def test_a_window_ending_in_the_future_is_the_text_in_force(self):
        v = self.read(dal="1-1-2026", al="31-12-2026")
        assert v["state"] == "current"
        assert (v["valid_from"], v["valid_to"]) == ("2026-01-01", "2026-12-31")

    def test_a_window_ending_today_is_the_text_in_force(self):
        v = self.read(dal="1-1-2026", al="2-10-2026")
        assert v["state"] == "current"
        assert v["valid_to"] == "2026-10-02"

    def test_a_window_that_ended_yesterday_is_historical(self):
        v = self.read(dal="1-1-2026", al="1-10-2026")
        assert v["state"] == "historical"
        assert v["valid_to"] == "2026-10-01"

    def test_a_window_closed_long_ago_is_historical(self):
        v = self.read(dal="25-12-2003", al="29-12-2007")
        assert (v["state"], v["valid_to"]) == ("historical", "2007-12-29")

    @pytest.mark.parametrize("requested,expected", [
        ("2026-06-01", True),
        ("2026-01-01", True),
        ("2026-12-31", True),
        ("2027-01-01", False),
        ("2025-12-31", False),
    ])
    def test_the_request_is_still_judged_against_the_window_as_stated(self, requested, expected):
        raw = synthetic(dal="1-1-2026", al="31-12-2026")
        v = extract_validity(raw, article="7", requested_date=requested, today=self.TODAY)
        assert v["state"] == "current"
        assert v["request_in_window"] is expected

    def test_an_abrogated_page_stays_abrogated_whatever_its_end(self):
        content = '<div class="ins-akn art_abrogato-akn">((ARTICOLO ABROGATO DALLA L. 1 GENNAIO 2026, N. 1))</div>'
        v = self.read(dal="1-1-2026", al="31-12-2026", content=content)
        assert (v["state"], v["valid_to"]) == ("abrogated", "2026-12-31")

    def test_a_not_yet_page_stays_not_yet_whatever_its_end(self):
        v = self.read(al="31-12-2026", content="<span>ARTICOLO NON ANCORA ESISTENTE O VIGENTE</span>")
        assert (v["state"], v["valid_to"]) == ("not_yet", "2026-12-31")

    def test_without_a_day_given_today_is_the_clock_of_rome(self, monkeypatch):
        monkeypatch.setattr(validity_module, "_today_in_rome", lambda: date(2026, 10, 2))
        assert extract_validity(synthetic(dal="1-1-2026", al="2-10-2026"), article="7")["state"] == "current"
        assert extract_validity(synthetic(dal="1-1-2026", al="1-10-2026"), article="7")["state"] == "historical"


class TestCapturedPages:
    """Whole pages the repository already holds (August 2026)."""

    def test_the_text_of_art_2043_c_c_has_been_in_force_since_1942(self):
        v = extract_validity(page("attachment.html"), article="2043")
        assert v == {
            "state": "current",
            "valid_from": "1942-04-19",
            "valid_to": None,
            "version_number": None,  # never amended: the page has no update link
            "act_updated": "2026-06-12",
            "request_in_window": None,
        }

    def test_an_amended_article_names_its_version(self):
        v = extract_validity(page("akn_comma_div.html"), article="3")
        assert (v["state"], v["valid_from"], v["version_number"]) == ("current", "2005-03-08", 2)
        assert v["act_updated"] == "2026-04-20"

    def test_a_repealed_article_is_abrogated_from_the_day_of_the_repeal(self):
        v = extract_validity(page("abrogato.html"), article="3")
        assert (v["state"], v["valid_from"], v["valid_to"], v["version_number"]) == (
            "abrogated", "2018-09-19", None, 2,
        )

    def test_a_label_with_a_suffix_is_matched(self):
        v = extract_validity(page("fallback.html"), article="6-bis")
        assert (v["state"], v["valid_from"], v["version_number"]) == ("current", "2012-11-28", 1)

    def test_the_constitution_art_3_has_been_in_force_since_1948(self):
        v = extract_validity(page("akn_just_text.html"), article="3")
        assert (v["state"], v["valid_from"]) == ("current", "1948-01-01")

    @pytest.mark.parametrize("name,article", [
        ("cp_544_abrogato_trimmed.html", "544"),
        ("cp_524_abrogato_malformed_trimmed.html", "524"),
    ])
    def test_the_trimmed_repeal_pages_are_abrogated_once_they_have_a_window(self, name, article):
        """Both shapes, the healthy one and the malformed one whose notice
        html.parser moves out of the span the text extractor reads."""
        raw = page(name).replace("<body>", "<body>" + window(dal="1-1-1996"), 1)
        v = extract_validity(raw, article=article)
        assert v["state"] == "abrogated"


class TestRecapturedPages:
    """Trimmed pages captured from the portal on 2026-10-02 (`fixtures/normattiva/README.md`).

    They assert what the portal printed, so a change in its markup shows up here first.
    """

    def test_a_middle_version_states_both_ends_of_its_window(self):
        v = extract_validity(
            page("art1284_cc_at_2007-12-29_trimmed.html"), article="1284", requested_date="2007-12-29",
        )
        assert (v["state"], v["valid_from"], v["valid_to"], v["version_number"]) == (
            "historical", "2003-12-25", "2007-12-29", 7,
        )
        assert v["request_in_window"] is True
        assert date.fromisoformat(v["act_updated"])  # the day of the consolidation, not a fact of the text

    def test_an_article_that_did_not_exist_yet_states_only_the_end(self):
        v = extract_validity(
            page("art183bis_cpc_at_2010-01-01_not_yet_trimmed.html"), article="183-bis", requested_date="2010-01-01",
        )
        assert (v["state"], v["valid_from"], v["valid_to"], v["request_in_window"]) == (
            "not_yet", None, "2014-09-12", True,
        )

    def test_a_partial_abrogation_is_not_an_abrogation(self):
        requested = "2015-01-01"
        v = extract_validity(
            page("art183_cpc_at_2015-01-01_partial_abrogation_trimmed.html"), article="183", requested_date=requested,
        )
        assert v["state"] in ("historical", "current")
        assert v["valid_from"] <= requested <= (v["valid_to"] or "9999-12-31")
        assert v["request_in_window"] is True


class TestAbrogation:
    def test_a_partial_notice_is_not_an_abrogation(self):
        """art. 183 c.p.c. carries "COMMA ABROGATO" in the middle of other commi."""
        content = (
            '<div class="art-commi-div-akn">'
            '<div class="art-comma-div-akn"><span class="comma-num-akn">1. </span>'
            '<span class="art_text_in_comma">Il debitore paga.</span></div>'
            '<div class="art-comma-div-akn"><div class="ins-akn art_abrogato-akn">'
            "((COMMA ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))</div></div>"
            "</div>"
        )
        v = extract_validity(synthetic(dal="1-1-2000", al="31-12-2005", label="Art. 183", content=content), article="183")
        assert v["state"] == "historical"

    def test_a_whole_article_notice_is_an_abrogation_even_with_a_closed_window(self):
        content = '<div class="ins-akn art_abrogato-akn">((ARTICOLO ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))</div>'
        v = extract_validity(synthetic(dal="1-1-2000", al="31-12-2005", content=content), article="7")
        assert (v["state"], v["valid_to"]) == ("abrogated", "2005-12-31")


def _notes(number, text="Il D.Lgs. 1 gennaio 2000, n. 1 ha disposto che il testo cambia."):
    """An update-notes block as the portal serves it, shaped like art. 183-bis c.p.c."""
    return (
        '<div class="art_aggiornamento-akn">'
        '<div class="art_aggiornamento_separator-akn">---------------</div>'
        f'<div class="art_aggiornamento_title-akn">AGGIORNAMENTO ({number})</div>'
        f'<div class="art_aggiornamento_testo-akn"><br> {text} </div>'
        "</div>"
    )


class TestAbrogationWithNotes:
    """A repealed article keeps its note marker and its update notes on the page.

    They are not its text: art. 183-bis c.p.c., in force today, was shown "In vigore"
    when the first version of the rule counted them as substance.
    """

    def test_the_real_page_of_a_repealed_article_that_carries_its_notes(self):
        v = extract_validity(
            page("art183bis_cpc_in_force_abrogated_with_notes_trimmed.html"), article="183-bis"
        )
        assert v["state"] == "abrogated"
        assert v["valid_from"] == "2024-11-26"
        assert v["valid_to"] is None
        assert v["version_number"] == 4
        assert v["act_updated"] == "2026-06-12"
        assert v["request_in_window"] is None

    def test_the_structural_rule_alone_ignores_the_marker_and_the_notes(self):
        """The notice does not say "ARTICOLO ABROGATO": only the structure decides."""
        content = (
            '<div class="ins-akn art_abrogato-akn">((DISPOSIZIONE SOPPRESSA DALLA L. 1 GENNAIO 2000, N. 1))</div>'
            '<div class="ins-akn">((12))</div>'
            + _notes(12)
        )
        v = extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        assert v["state"] == "abrogated"

    @pytest.mark.parametrize(
        "notice",
        [
            "(( ARTICOLO ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))",
            "((articolo abrogato dalla l. 1 gennaio 2000, n. 1))",
            "((ARTICOLO   ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))",
            "((ARTICOLO ABROGATA DALLA L. 1 GENNAIO 2000, N. 1))",
            "  ((ARTICOLO\n ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))",
        ],
    )
    def test_a_whole_article_notice_is_decisive_whatever_else_is_left(self, notice):
        content = (
            '<span class="art-just-text-akn">(Rubrica rimasta)</span>'
            f'<div class="ins-akn art_abrogato-akn">{notice}</div>'
        )
        v = extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        assert v["state"] == "abrogated"

    def test_a_whole_article_notice_alone_is_an_abrogation(self):
        content = '<div class="ins-akn art_abrogato-akn">((ARTICOLO ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))</div>'
        v = extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        assert v["state"] == "abrogated"

    def test_a_partial_notice_with_a_marker_and_notes_is_not_an_abrogation(self):
        content = (
            '<div class="art-commi-div-akn">'
            '<div class="art-comma-div-akn"><span class="comma-num-akn">1. </span>'
            '<span class="art_text_in_comma">Il debitore paga.</span></div>'
            '<div class="art-comma-div-akn"><div class="ins-akn art_abrogato-akn">'
            "((COMMA ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))</div>"
            '<div class="ins-akn">((12))</div></div>'
            "</div>"
            + _notes(12)
        )
        v = extract_validity(synthetic(dal="1-1-2000", label="Art. 183", content=content), article="183")
        assert v["state"] == "current"

    def test_notes_that_say_the_article_is_repealed_are_not_a_notice_without_an_ins_akn(self):
        """The notes hold no `ins-akn` here: the bare words in them decide nothing.

        (Notes that wrap the words in an `ins-akn` are `TestAbrogationHostile`'s case.)
        """
        content = (
            '<span class="art-just-text-akn">Il testo dell\'articolo.</span>'
            + _notes(3, "ARTICOLO ABROGATO DALLA L. 1 GENNAIO 2000, N. 1")
        )
        v = extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        assert v["state"] == "current"

    def test_a_whole_article_notice_followed_by_two_thousand_notes_blocks(self):
        content = (
            '<div class="ins-akn art_abrogato-akn">((ARTICOLO ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))</div>'
            + "".join(_notes(n) for n in range(2_000))
        )
        found, elapsed = TestHostilePages._timed(
            lambda: extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        )
        assert found["state"] == "abrogated"
        assert elapsed < TestHostilePages.BOUND

    def test_one_block_of_fifty_thousand_markers_in_an_update_notes_block_beside_real_text_is_current(self):
        content = (
            '<span class="art-just-text-akn">Il testo dell\'articolo.</span>'
            '<div class="art_aggiornamento-akn">' + "((1))" * 50_000 + "</div>"
        )
        found, elapsed = TestHostilePages._timed(
            lambda: extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        )
        assert found["state"] == "current"
        assert elapsed < TestHostilePages.BOUND


class TestAbrogationWhateverTheNoticeClass:
    """The portal does not always give a repeal notice the `art_abrogato-akn` class.

    A whole-article notice is sometimes a plain `ins-akn` (art. 155-ter c.c.), and the
    notice of a whole repealed act ("PROVVEDIMENTO ABROGATO") always is: both were shown
    "In vigore". The words decide, in any `ins-akn`.
    """

    def test_art_155ter_cc_whole_article_notice_in_a_plain_ins_akn(self):
        v = extract_validity(
            page("art155ter_cc_in_force_abrogated_plain_notice_trimmed.html"), article="155-ter"
        )
        assert v["state"] == "abrogated"
        assert v["valid_from"] == "2014-02-07"
        assert v["valid_to"] is None
        assert v["version_number"] == 2

    def test_art_1_dlgs_163_2006_the_act_is_repealed(self):
        v = extract_validity(page("dlgs163_2006_art1_provvedimento_abrogato_trimmed.html"), article="1")
        assert v["state"] == "abrogated"
        assert v["valid_from"] == "2016-04-19"
        assert v["valid_to"] is None

    def test_art_1_tuir_as_served_for_a_future_day_says_the_act_is_repealed(self):
        v = extract_validity(page("tuir_art1_at_2027-01-01_provvedimento_abrogato_trimmed.html"), article="1")
        assert v["state"] == "abrogated"
        assert v["valid_from"] == "2027-01-01"
        assert v["valid_to"] is None
        assert v["version_number"] == 3

    def test_a_closure_announced_for_the_future_leaves_the_text_current(self):
        v = extract_validity(
            page("tuir_art1_in_force_closing_2026-12-31_trimmed.html"),
            article="1",
            today=date(2026, 10, 2),
        )
        assert v["state"] == "current"
        assert v["valid_from"] == "2004-01-01"
        assert v["valid_to"] == "2026-12-31"
        assert v["version_number"] == 2

    @pytest.mark.parametrize(
        "notice",
        [
            "((ARTICOLO ABROGATO DAL D.LGS. 1 GENNAIO 2000, N. 1))",
            "(( ARTICOLO ABROGATO DAL D.LGS. 1 GENNAIO 2000, N. 1 ))",
            "((PROVVEDIMENTO ABROGATO DAL D.LGS. 1 GENNAIO 2000, N. 1))",
            "((ARTICOLO SOPPRESSO DAL D.LGS. 1 GENNAIO 2000, N. 1))",
            "((PROVVEDIMENTO SOPPRESSO DAL D.LGS. 1 GENNAIO 2000, N. 1))",
            "((articolo abrogato dal d.lgs. 1 gennaio 2000, n. 1))",
            "((provvedimento  abrogato   dal d.lgs. 1 gennaio 2000, n. 1))",
        ],
    )
    def test_a_plain_ins_akn_notice_decides_by_its_words(self, notice):
        content = (
            '<span class="art-just-text-akn">(Rubrica rimasta)</span>'
            f'<div class="ins-akn">{notice}</div>'
        )
        v = extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        assert v["state"] == "abrogated"

    @pytest.mark.parametrize(
        "notice",
        [
            "((COMMA ABROGATO DAL D.LGS. 1 GENNAIO 2000, N. 1))",
            "((PERIODO SOPPRESSO DAL D.LGS. 1 GENNAIO 2000, N. 1))",
            "((NUMERO ABROGATO DAL D.LGS. 1 GENNAIO 2000, N. 1))",
            "((LETTERA SOPPRESSA DAL D.LGS. 1 GENNAIO 2000, N. 1))",
        ],
    )
    def test_a_partial_plain_notice_among_other_commi_is_not_an_abrogation(self, notice):
        content = (
            '<div class="art-commi-div-akn">'
            '<div class="art-comma-div-akn"><span class="comma-num-akn">1. </span>'
            '<span class="art_text_in_comma">Il debitore paga.</span></div>'
            f'<div class="art-comma-div-akn"><div class="ins-akn">{notice}</div></div>'
            "</div>"
        )
        v = extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        assert v["state"] == "current"

    def test_a_plain_note_marker_beside_the_text_is_not_an_abrogation(self):
        content = (
            '<span class="art-just-text-akn">Il testo dell\'articolo.</span>'
            '<div class="ins-akn">((12))</div>'
        )
        v = extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        assert v["state"] == "current"

    @pytest.mark.parametrize("words", ["PROVVEDIMENTO ABROGATO", "ARTICOLO ABROGATO"])
    def test_the_bare_words_in_the_update_notes_are_not_a_notice(self, words):
        """The notes hold no `ins-akn` here: the bare words in them decide nothing."""
        content = (
            '<span class="art-just-text-akn">Il testo dell\'articolo.</span>'
            + _notes(3, f"{words} DAL D.LGS. 1 GENNAIO 2000, N. 1")
        )
        v = extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        assert v["state"] == "current"

    def test_five_thousand_plain_markers_and_no_repeal(self):
        content = (
            '<span class="art-just-text-akn">Il testo dell\'articolo.</span>'
            + "".join(f'<div class="ins-akn">(({n}))</div>' for n in range(5_000))
        )
        found, elapsed = TestHostilePages._timed(
            lambda: extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        )
        assert found["state"] == "current"
        assert elapsed < TestHostilePages.BOUND

    def test_five_thousand_plain_markers_then_a_whole_article_notice(self):
        content = (
            '<span class="art-just-text-akn">Il testo dell\'articolo.</span>'
            + "".join(f'<div class="ins-akn">(({n}))</div>' for n in range(5_000))
            + '<div class="ins-akn">((ARTICOLO ABROGATO DAL D.LGS. 1 GENNAIO 2000, N. 1))</div>'
        )
        found, elapsed = TestHostilePages._timed(
            lambda: extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        )
        assert found["state"] == "abrogated"
        assert elapsed < TestHostilePages.BOUND


class TestAbrogationHostile:
    """The abrogation rule stays linear whatever the page nests, and reads the notice's head.

    Nested `ins-akn` nodes used to cost the square of their depth (each one's text was
    read in full); the update notes are taken out before anything is read.
    """

    @staticmethod
    def _run(content):
        return TestHostilePages._timed(
            lambda: extract_validity(synthetic(dal="1-1-2000", content=content), article="7")
        )

    def test_a_chain_of_nested_ins_akn_divs_with_no_repeal_words(self):
        found, elapsed = self._run('<div class="ins-akn">' * 9_000 + "x" + "</div>" * 9_000)
        assert found["state"] == "current"
        assert elapsed < TestHostilePages.BOUND

    def test_a_chain_of_nested_ins_akn_divs_with_the_notice_at_the_bottom(self):
        found, elapsed = self._run(
            '<div class="ins-akn">' * 9_000
            + "((ARTICOLO ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))"
            + "</div>" * 9_000
        )
        assert found["state"] == "abrogated"
        assert elapsed < TestHostilePages.BOUND

    def test_a_chain_of_nested_ins_akn_with_text_at_every_level(self):
        found, elapsed = self._run('<i class="ins-akn">a ' * 9_000 + "x" + "</i>" * 9_000)
        assert found["state"] == "current"
        assert elapsed < TestHostilePages.BOUND

    def test_fifty_thousand_markers_beside_a_partial_structural_notice_leave_nothing(self):
        """Not "ARTICOLO ABROGATO": the structural rule runs and removes every marker."""
        content = (
            '<div class="ins-akn art_abrogato-akn">((DISPOSIZIONE SOPPRESSA DALLA L. 1 GENNAIO 2000, N. 1))</div>'
            "<span>" + "((1))" * 50_000 + "</span>"
        )
        found, elapsed = self._run(content)
        assert found["state"] == "abrogated"
        assert elapsed < TestHostilePages.BOUND

    def test_an_ins_akn_inside_the_update_notes_is_not_a_notice(self):
        content = (
            '<span class="art-just-text-akn">Il testo dell\'articolo.</span>'
            + _notes(3, '<div class="ins-akn">((ARTICOLO ABROGATO DALLA L. 1 GENNAIO 2000, N. 1))</div>')
        )
        found, _ = self._run(content)
        assert found["state"] == "current"

    def test_repeal_words_in_the_middle_of_a_partial_notice_are_not_a_whole_article_notice(self):
        content = (
            '<div class="art-commi-div-akn">'
            '<div class="art-comma-div-akn"><span class="comma-num-akn">1. </span>'
            '<span class="art_text_in_comma">Il debitore paga.</span></div>'
            '<div class="art-comma-div-akn"><div class="ins-akn">'
            "((COMMA ABROGATO DALLA L. 1 GENNAIO 2000, N. 1; ARTICOLO ABROGATO DAL D.LGS. 1 GENNAIO 2001, N. 2))"
            "</div></div></div>"
        )
        found, _ = self._run(content)
        assert found["state"] == "current"


class TestTheArticleAskedFor:
    def test_a_page_for_another_article_says_nothing(self):
        """Normattiva answers 200 for a URN that names something else: the decree
        that approves the code, when the code's annex is missing."""
        assert extract_validity(synthetic(dal="1-1-1942", label="Art. 1"), article="1284") is None

    @pytest.mark.parametrize("label,article", [
        ("Art. 183 bis", "183-bis"),
        ("Art. 183-bis.", "183 bis"),
        ("Art. 6-bis", "6-bis"),
        ("Art. 25 undecies", "25-undecies"),
        ("Art. 2409 octiesdecies", "2409-octiesdecies"),
        ("Art. 270-bis.1", "270-bis.1"),
        ("Art. 314/2", "314/2"),
        ("Codice Penale-art. 524", "524"),
        ("  Art. 2043. (Risarcimento per fatto illecito).", "2043"),
    ])
    def test_the_label_may_be_spelled_the_portals_way(self, label, article):
        assert extract_validity(synthetic(dal="1-1-1942", label=label), article=article)["state"] == "current"

    def test_a_suffix_of_the_wrong_article_does_not_match(self):
        assert extract_validity(synthetic(dal="1-1-1942", label="Art. 183 ter"), article="183-bis") is None

    def test_an_unreadable_label_says_nothing_when_an_article_was_asked_for(self):
        assert extract_validity(synthetic(dal="1-1-1942", label="Premessa"), article="7") is None

    def test_without_an_article_the_label_is_not_checked(self):
        assert extract_validity(synthetic(dal="1-1-1942", label="Premessa"))["state"] == "current"


class TestRequestedDate:
    CLOSED = synthetic(dal="25-12-2003", al="29-12-2007")

    @pytest.mark.parametrize("requested,expected", [
        ("2005-06-01", True),
        ("2003-12-25", True),   # the first day is in
        ("2007-12-29", True),   # and so is the last
        ("2003-12-24", False),
        ("2007-12-30", False),
    ])
    def test_the_window_is_inclusive_at_both_ends(self, requested, expected):
        assert extract_validity(self.CLOSED, article="7", requested_date=requested)["request_in_window"] is expected

    def test_without_a_date_there_is_no_verdict(self):
        assert extract_validity(self.CLOSED, article="7")["request_in_window"] is None

    @pytest.mark.parametrize("requested", ["29 dicembre 2007", " 2007-12-29 "])
    def test_the_italian_long_form_and_stray_spaces_are_understood(self, requested):
        assert extract_validity(self.CLOSED, article="7", requested_date=requested)["request_in_window"] is True

    @pytest.mark.parametrize("requested", ["ieri", "2007-13-45", "", 20071229])
    def test_a_date_that_cannot_be_read_gives_no_verdict(self, requested):
        assert extract_validity(self.CLOSED, article="7", requested_date=requested)["request_in_window"] is None

    def test_an_open_window_does_not_contain_a_date_before_its_start(self):
        v = extract_validity(synthetic(dal="8-3-2005"), article="7", requested_date="2000-01-01")
        assert v["request_in_window"] is False

    def test_a_not_yet_page_contains_the_days_up_to_its_end(self):
        raw = synthetic(al="12-9-2014", content="<span>NON ANCORA ESISTENTE O VIGENTE</span>")
        assert extract_validity(raw, article="7", requested_date="2010-01-01")["request_in_window"] is True
        assert extract_validity(raw, article="7", requested_date="2015-01-01")["request_in_window"] is False


class TestIsHistoricalRequest:
    @pytest.mark.parametrize("version,version_date,expected", [
        ("vigente", None, False),
        ("vigente", "", False),
        ("vigente", "   ", False),
        (None, None, False),
        ("originale", None, True),
        ("ORIGINALE", "", True),
        ("vigente", "2007-12-29", True),
        (None, "2007-12-29", True),
        ("vigente", 20071229, False),
    ])
    def test_the_request_names_a_past_text_or_it_does_not(self, version, version_date, expected):
        assert is_historical_request(version, version_date) is expected


class TestRejectFutureVersionDate:
    TODAY = date(2026, 10, 1)

    @pytest.mark.parametrize("value", [
        None, "", "2026-10-01", "2000-01-01", "1 ottobre 2026",
        "ieri", "2026-02-31", "31 febbraio 2019", 20261002,
    ])
    def test_today_the_past_and_what_the_existing_parser_judges_pass(self, value):
        reject_future_version_date(value, today=self.TODAY)

    @pytest.mark.parametrize("value", ["2026-10-02", "2999-01-01", "2 ottobre 2026", " 2026-10-02 "])
    def test_a_later_day_is_refused_with_the_reason(self, value):
        with pytest.raises(ValidationError, match="futura"):
            reject_future_version_date(value, today=self.TODAY)

    def test_without_a_stated_today_the_clock_is_used(self):
        with pytest.raises(ValidationError):
            reject_future_version_date("2999-01-01")
        reject_future_version_date("2000-01-01")


class TestHostilePages:
    """A page the portal did not serve must not stall the server.

    `re` holds the GIL, so a quadratic pattern on a hostile page blocks the whole event
    loop even when it runs in a thread. With the first version of the patterns each case
    below took seconds; it takes milliseconds now, and the bound leaves a wide margin.
    """

    BOUND = 1.0  # seconds

    @staticmethod
    def _timed(call):
        start = time.perf_counter()
        result = call()
        return result, time.perf_counter() - start

    def test_a_run_of_unclosed_angle_brackets_in_the_window_block(self):
        hostile = '<div class="vigore my-5">' + "<" * 100_000 + "</div>"
        found, elapsed = self._timed(lambda: extract_validity(hostile))
        assert found is None
        assert elapsed < self.BOUND

    def test_a_page_of_div_openings_that_never_close(self):
        found, elapsed = self._timed(lambda: extract_validity("<div " * 20_000))
        assert found is None
        assert elapsed < self.BOUND

    def test_a_long_run_of_blanks_after_the_article_label(self):
        hostile = synthetic(
            dal="25-12-2003",
            label="Art. 7" + " " * 5_000 + ".",
            content='<div class="ins-akn art_abrogato-akn">ARTICOLO ABROGATO</div>',
        )
        found, elapsed = self._timed(lambda: extract_validity(hostile))
        assert found is not None and found["state"] == "abrogated"
        assert elapsed < self.BOUND

    @pytest.mark.parametrize("word", ["vigore", "bodyTesto"])
    @pytest.mark.parametrize("closing", ["", '"'])
    def test_a_class_value_that_repeats_the_searched_word(self, word, closing):
        hostile = '<div class="' + (word + " ") * 10_000 + closing
        found, elapsed = self._timed(lambda: extract_validity(hostile))
        assert found is None
        assert elapsed < self.BOUND

    def test_other_attributes_and_single_quotes_still_find_the_two_blocks(self):
        page = (
            "<html><body>"
            "<div id='w' class='note vigore my-5' data-x=\"1\">Testo in vigore dal: <span>25-12-2003</span></div>"
            "<div role=\"main\" class=\"bodyTesto\" data-y='2'><h2 class=\"article-num-akn\">Art. 7</h2>x</div>"
            "</body></html>"
        )
        found = extract_validity(page, article="7")
        assert found is not None
        assert found["state"] == "current"
        assert found["valid_from"] == "2003-12-25"
