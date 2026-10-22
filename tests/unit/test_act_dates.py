# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_act_dates.py at eca698dc.
# Adapted: only the title reader's tests (TestDateFromTitle and its fixtures, unchanged);
# the network half is tested on scraper.with_full_date (tests/unit/test_legal_citations_fixes.py).
"""The date of an act read from its Normattiva page's title. No network."""

import pytest

from mcp_legal_it.lib.visualex import act_dates


# The shape Normattiva gives every act page's title (measured on eight kinds, 2 Oct 2026).
PAGE = """<html><head><title>LEGGE 4 maggio 1983, n. 184 - Normattiva</title></head><body>
<p>Gazzetta Ufficiale 17 maggio 1983</p>
<h2>LEGGE 4 maggio 1983, n. 184</h2>
<p>Disciplina dell'adozione</p></body></html>"""

LEGGE_184 = "urn:nir:stato:legge:1983;184"


def page_titled(title):
    return f"<html><head><title>{title} - Normattiva</title></head><body><h2>{title}</h2></body></html>"


# kind, title (without the " - Normattiva" tail), year, number, ISO date.
EIGHT_KINDS = [
    ("legge", "LEGGE 4 maggio 1983, n. 184", "1983", "184", "1983-05-04"),
    ("decreto.legislativo", "DECRETO LEGISLATIVO 23 febbraio 2006, n. 109", "2006", "109", "2006-02-23"),
    ("decreto.legge", "DECRETO-LEGGE 4 giugno 2013, n. 61", "2013", "61", "2013-06-04"),
    (
        "decreto.del.presidente.della.repubblica",
        "DECRETO DEL PRESIDENTE DELLA REPUBBLICA 23 gennaio 1973, n. 43",
        "1973", "43", "1973-01-23",
    ),
    ("regio.decreto", "REGIO DECRETO 18 giugno 1931, n. 773", "1931", "773", "1931-06-18"),
    ("legge.costituzionale", "LEGGE COSTITUZIONALE 18 ottobre 2001, n. 3", "2001", "3", "2001-10-18"),
    ("regio.decreto.legge", "REGIO DECRETO-LEGGE 4 ottobre 1935, n. 1827", "1935", "1827", "1935-10-04"),
    ("decreto", "DECRETO 28 marzo 2003, n. 123", "2003", "123", "2003-03-28"),
    # The table's ninth entry: not among the eight measured, a synthetic title of the same shape.
    ("regio.decreto.legislativo", "REGIO DECRETO LEGISLATIVO 5 maggio 1948, n. 77", "1948", "77", "1948-05-05"),
]


class TestDateFromTitle:
    def test_reads_the_title_not_the_gazette_date(self):
        assert act_dates.date_from_title(PAGE, "legge", "1983", "184") == "1983-05-04"

    @pytest.mark.parametrize("kind,title,year,number,iso", EIGHT_KINDS)
    def test_every_kind_reads_its_own_title(self, kind, title, year, number, iso):
        assert act_dates.date_from_title(page_titled(title), kind, year, number) == iso

    def test_every_resolvable_kind_is_in_the_table_test(self):
        assert {row[0] for row in EIGHT_KINDS} == set(act_dates._TITLES)

    def test_number_must_match(self):
        assert act_dates.date_from_title(PAGE, "legge", "1983", "185") is None

    def test_year_must_match(self):
        assert act_dates.date_from_title(PAGE, "legge", "1984", "184") is None

    def test_a_longer_number_is_not_the_same_number(self):
        assert act_dates.date_from_title(page_titled("LEGGE 4 maggio 1983, n. 1841"), "legge", "1983", "184") is None

    def test_number_and_year_compare_as_integers(self):
        assert act_dates.date_from_title(PAGE, "legge", "1983", "0184") == "1983-05-04"

    def test_the_act_type_must_match(self):
        title = page_titled("DECRETO-LEGGE 19 febbraio 2001, n. 17")
        assert act_dates.date_from_title(title, "legge", "2001", "17") is None
        assert act_dates.date_from_title(title, "decreto.legge", "2001", "17") == "2001-02-19"

    def test_a_short_type_does_not_claim_a_longer_one(self):
        decree = page_titled("DECRETO LEGISLATIVO 23 febbraio 2006, n. 109")
        assert act_dates.date_from_title(decree, "decreto", "2006", "109") is None
        constitutional = page_titled("LEGGE COSTITUZIONALE 18 ottobre 2001, n. 3")
        assert act_dates.date_from_title(constitutional, "legge", "2001", "3") is None
        royal = page_titled("REGIO DECRETO-LEGGE 4 ottobre 1935, n. 1827")
        assert act_dates.date_from_title(royal, "decreto.legge", "1935", "1827") is None

    def test_ordinal_day_and_capitals(self):
        page = page_titled("DECRETO LEGISLATIVO 1º Febbraio 2006, n. 109")
        assert act_dates.date_from_title(page, "decreto.legislativo", "2006", "109") == "2006-02-01"

    def test_degree_sign_day(self):
        page = page_titled("LEGGE 1° agosto 2003, n. 206")
        assert act_dates.date_from_title(page, "legge", "2003", "206") == "2003-08-01"

    def test_entities_and_whitespace_in_the_title_are_normalised(self):
        page = "<html><head><title>\n  LEGGE&nbsp;4  maggio\n1983,\tn.&#32;184 - Normattiva </title></head></html>"
        assert act_dates.date_from_title(page, "legge", "1983", "184") == "1983-05-04"

    def test_a_title_tag_with_attributes_is_read(self):
        page = '<head><TITLE lang="it">LEGGE 4 maggio 1983, n. 184 - Normattiva</TITLE></head>'
        assert act_dates.date_from_title(page, "legge", "1983", "184") == "1983-05-04"

    def test_the_act_must_open_the_title(self):
        page = page_titled("Testo coordinato: LEGGE 4 maggio 1983, n. 184")
        assert act_dates.date_from_title(page, "legge", "1983", "184") is None

    def test_a_date_in_the_body_is_not_the_title(self):
        page = "<html><head><title>Normattiva</title></head><body><h2>LEGGE 4 maggio 1983, n. 184</h2></body></html>"
        assert act_dates.date_from_title(page, "legge", "1983", "184") is None

    def test_no_title_no_date(self):
        assert act_dates.date_from_title("<html></html>", "legge", "1983", "184") is None

    def test_an_unknown_month_is_not_a_date(self):
        page = page_titled("LEGGE 4 maggi 1983, n. 184")
        assert act_dates.date_from_title(page, "legge", "1983", "184") is None

    @pytest.mark.parametrize("title", ["LEGGE 31 febbraio 1983, n. 184", "LEGGE 0 maggio 1983, n. 184"])
    def test_a_day_that_does_not_exist_is_not_a_date(self, title):
        assert act_dates.date_from_title(page_titled(title), "legge", "1983", "184") is None

    def test_a_kind_outside_the_table_has_no_title_to_match(self):
        assert act_dates.date_from_title(PAGE, "ordinanza", "1983", "184") is None

    def test_a_hostile_page_is_read_in_linear_time(self):
        page = "<title " * 20000 + "LEGGE " * 20000
        assert act_dates.date_from_title(page, "legge", "1983", "184") is None


