"""Normattiva's HTML article page -> ``article_text``, VisuaLex's extractor kept byte for byte.

The cases and the frozen hashes are VisuaLex's ``services/visualex/tests/
test_normattiva_extraction.py`` (MPL-2.0, at ``eca698dc``), on its fixtures
(``tests/fixtures/visualex/normattiva/``, copied unchanged). A failing hash means
the extracted text changed, and with it every highlight and note VisuaLex anchors
to it: never re-record a hash to make this pass.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mcp_legal_it.lib.visualex import normattiva_html
from mcp_legal_it.lib.visualex.normattiva_html import ParsingError, estrai_da_html

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "normattiva"

CASES = [
    "akn_comma_div.html",
    "akn_just_text.html",
    "abrogato.html",
    "attachment.html",
    "fallback.html",
]

#: VisuaLex's FROZEN_TEXT_SHA256, unchanged.
FROZEN_TEXT_SHA256 = {
    "akn_comma_div.html": "c98b1ef2caecb3daf236cb912dfade4bbe4db3bb378d48221f586d374401f4f4",
    "akn_just_text.html": "154ba79f6ece9bbb6ec5915b84065aeb9c60950556a69fa4a5e70d559d873cce",
    "abrogato.html": "6d06df4c2674d688ec0024301b5ed04ddce42387ef4260e60d602b2b8911f6e5",
    "attachment.html": "d69cc4cfcd7ea042c1a230e5b9037d94564451408b637b929adbb5868fb20ef8",
    "fallback.html": "1181881d79d0dd1a31c7e79ea6ace6627022ee2f164c3498a497a9fd3b4fcaba",
    "cp_544_abrogato_trimmed.html": "5c06313f7d36e5f171cf3f63393029fcea1b83bf48cd539618efcb66f402a87a",
}


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("fixture_name,expected_sha256", sorted(FROZEN_TEXT_SHA256.items()))
def test_extracted_text_matches_the_frozen_sha256(fixture_name, expected_sha256):
    text = estrai_da_html(_html(fixture_name))
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == expected_sha256


@pytest.mark.parametrize("fixture_name", CASES)
def test_every_branch_yields_text(fixture_name):
    text = estrai_da_html(_html(fixture_name))
    assert isinstance(text, str) and len(text.strip()) > 50


def test_extraction_keeps_italian_accents():
    """The Akoma Ntoso export transliterates accents ("attivita'"); the HTML page does not."""
    text = estrai_da_html(_html("akn_comma_div.html"))
    assert any(ch in text for ch in "àèéìòù")


def test_a_page_without_the_article_body_is_an_error_not_a_text():
    with pytest.raises(ParsingError):
        estrai_da_html("<html><body>nothing useful here</body></html>")


@pytest.mark.parametrize("name", [
    "_estrai_testo_akn_dettagliato",
    "_estrai_testo_akn_semplice",
    "_estrai_testo_allegato",
    "_estrai_testo_fallback",
])
def test_a_broken_branch_raises_naming_itself(name):
    with pytest.raises(ParsingError) as exc:
        getattr(normattiva_html, name)("not a tag")
    assert name in str(exc.value)


class TestRepealedArticleWithMalformedMarkup:
    """c.p. art. 524: the repeal notice outside the attachment span is still read."""

    def test_orphan_abrogation_notice_is_appended(self):
        assert estrai_da_html(_html("cp_524_abrogato_malformed_trimmed.html")) == (
            "Codice Penale-art. 524\n\n((ARTICOLO ABROGATO DALLA L. 15 FEBBRAIO 1996, N. 66))"
        )

    def test_orphan_notice_link_is_collected(self):
        result = estrai_da_html(_html("cp_524_abrogato_malformed_trimmed.html"), get_link_dict=True)
        assert "ARTICOLO ABROGATO DALLA L. 15 FEBBRAIO 1996" in result["testo"]
        assert result["link"]["L. 15 FEBBRAIO 1996, N. 66"].endswith("legge:1996-02-15;66")

    def test_healthy_repealed_article_is_unchanged(self):
        assert estrai_da_html(_html("cp_544_abrogato_trimmed.html")) == (
            "Art. 544. \n\n((ARTICOLO ABROGATO DALLA L. 5 AGOSTO 1981, N. 442))"
        )


def test_the_amendment_markers_are_kept():
    """«(( … ))» says which words a later act inserted: part of the text a lawyer reads."""
    assert "((" in estrai_da_html(_html("cp_544_abrogato_trimmed.html"))


@pytest.mark.parametrize("contenuto", ["[]", '"x"', '{"schema": 1}', '{"url": "u", "testo": null}'])
def test_a_page_record_that_is_not_one_is_dropped(tmp_path, monkeypatch, contenuto):
    # A valid JSON that is not a record failed every read of that URL, for ever.
    from mcp_legal_it.lib.visualex import pagine_normattiva

    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    pagine_normattiva.svuota_memoria()
    url = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241~art1"
    path = pagine_normattiva._dir() / f"{pagine_normattiva._chiave(url)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contenuto, encoding="utf-8")
    assert pagine_normattiva.leggi(url) is None
    assert not path.exists()
