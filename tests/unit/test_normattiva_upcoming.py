# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_text_in_force.py at 4aa59a9d:
# TestTheWindow and TestTheRequestGuard, the tests of ``normattiva_validity``'s own functions.
# Adapted: the imports name this package, today is passed (VisuaLex patches its clock), and
# the guard's HTTP case (VisuaLex's controller) is left out; the controller's behaviour is
# this package's own, tested in test_testo_di_oggi.py and test_versione_futura.py.
"""When a Normattiva page's text comes into force after today, and what the later text does."""
from datetime import date
from pathlib import Path

import pytest

from mcp_legal_it.lib.visualex.normattiva_validity import (
    ValidationError,
    extract_validity,
    read_upcoming_request,
    starts_after_today,
    upcoming_change,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "normattiva"
LATER = (FIXTURES / "dpr131_1986_art3_undated_abrogato_2027_trimmed.html").read_text(encoding="utf-8")
TODAY_PAGE = (FIXTURES / "dpr131_1986_art3_at_2026-10-21_in_force_trimmed.html").read_text(encoding="utf-8")
TODAY = date(2026, 10, 21)


class TestTheWindow:
    def test_a_window_starting_after_today(self):
        later = extract_validity(LATER, article="3", today=TODAY)
        assert starts_after_today(later, TODAY) is True
        assert upcoming_change(later) == {"change": "abrogated", "valid_from": "2027-01-01", "version_number": 2}

    def test_a_window_already_open(self):
        assert starts_after_today(extract_validity(TODAY_PAGE, article="3", today=TODAY), TODAY) is False

    @pytest.mark.parametrize("valid_from,expected", [("2026-10-21", False), ("2026-10-22", True), (None, False)])
    def test_today_itself_is_in_force(self, valid_from, expected):
        assert starts_after_today({"valid_from": valid_from}, TODAY) is expected

    def test_a_later_text_that_is_not_a_repeal_is_an_amendment(self):
        assert upcoming_change({"state": "current", "valid_from": "2027-01-01", "version_number": 3}) == \
            {"change": "amended", "valid_from": "2027-01-01", "version_number": 3}


class TestTheRequestGuard:
    @pytest.mark.parametrize("version,day,ok", [
        (None, None, True), ("vigente", "2027-01-01", True),
        ("originale", None, False), (None, "2026-10-21", False), (None, "2020-01-01", False),
        (None, "ieri", False),
    ])
    def test_upcoming_with_what(self, version, day, ok):
        if ok:
            read_upcoming_request(version, day, today=TODAY)
        else:
            with pytest.raises(ValidationError):
                read_upcoming_request(version, day, today=TODAY)
