"""Paged reading of long texts (src/lib/_paging.py): the da_carattere contract."""

import pytest

from src.lib._paging import invalid_start, page, resume_hint


class TestPage:
    def test_window_and_next_start(self):
        body, note = page("abcdefghij", 3, 4)
        assert body == "cdef"
        assert note == "*[Caratteri 3-6 su 10 totali: per leggere il seguito ripetere la chiamata con da_carattere=7]*"

    def test_last_window_says_the_text_is_over(self):
        body, note = page("abcdefghij", 7, 4)
        assert body == "ghij"
        assert note == "*[Caratteri 7-10 su 10 totali: fine del testo]*"

    def test_windows_cover_the_text_without_gaps_or_overlaps(self):
        text = "".join(chr(65 + i % 26) for i in range(103))
        read, start = "", 1
        while True:
            body, note = page(text, start, 25)
            read += body
            if "fine del testo" in note:
                break
            start = int(note.rsplit("=", 1)[1].rstrip("]*"))
        assert read == text

    def test_start_beyond_the_end(self):
        body, note = page("abc", 4, 10)
        assert body == ""
        assert "oltre la fine del testo (3 caratteri)" in note


class TestInvalidStart:
    @pytest.mark.parametrize("value", [0, -5, True, "2", 2.0])
    def test_rejected(self, value):
        assert invalid_start(value)

    @pytest.mark.parametrize("value", [1, 25001])
    def test_accepted(self, value):
        assert invalid_start(value) is None


def test_resume_hint():
    assert resume_hint(25001) == "per leggere il seguito ripetere la chiamata con da_carattere=25001"
