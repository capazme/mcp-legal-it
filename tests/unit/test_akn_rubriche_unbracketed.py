# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_akn_rubriche_unbracketed.py at 0f1477c2.
# Adapted: the imports name this package; the existence check and the smart lookup,
# methods of VisuaLex's Quart controller there, are this package's pure functions
# (albero_normattiva.articolo_nell_albero, grafia_dell_atto); the AKN-index fallback test,
# which is the controller's only, is left out.
"""Rubriche an amendment rewrote without brackets, and ordinals split in two words.

`fixtures/akn/codice_civile_trimmed.xml` is the codice civile's AKN export of 21
October 2026 cut to 24 articles (the act-level metadata emptied: the parser does not
read it). On the whole export `/fetch_rubriche` read 2840 of 3249 articles; 159 are
repealed, and about 250 write their rubrica without brackets («Art. 45.» /
«Domicilio dei coniugi, del minore e dell'interdetto.» / body), or repeat the
article number in the other spelling of its ordinal. Now 3039, and no rubrica read
before changed.
"""
from pathlib import Path

import pytest

from mcp_legal_it.lib.visualex.akn_parser import comparable_article_key, normalize_article_key, parse_akn

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "akn"


def _act(name):
    return parse_akn((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cc():
    return _act("codice_civile_trimmed.xml")


class TestUnbracketedRubriche:
    @pytest.mark.parametrize("key,rubrica", [
        ("2043", "Risarcimento per fatto illecito"),        # in brackets, as before
        ("2", "Maggiore età. Capacità di agire"),
        ("45", "Domicilio dei coniugi, del minore e dell'interdetto"),
        ("84", "Età"),                                       # rewritten «((Eta'))»
        ("87", "Parentela, affinità, adozione ..."),
        ("336", "Legittimazione ad agire"),                  # note calls «(321)(322)» left out
        ("1159-bis", "Usucapione speciale per la piccola proprietà rurale"),  # «Art. 1159.» repeated
        ("2545-quindecies", "Controllo giudiziario"),       # «Art. 2545-quinquiesdecies.» repeated
    ])
    def test_read(self, cc, key, rubrica):
        assert cc.rubriche()[key] == rubrica

    @pytest.mark.parametrize("key", [
        "147",       # the text starts at once: no rubrica
        "155",       # its only line, then a separator
        "1469-ter",  # «Il D.Lgs. 6 settembre 2005, n. 206 ha disposto …»
        "2384-bis",  # «ARTICOLO NON PIU' PREVISTO …»
    ])
    def test_a_notice_or_a_body_is_no_rubrica(self, cc, key):
        assert key in cc.articles
        assert key not in cc.rubriche()

    def test_an_act_without_bracketed_rubriche_reads_no_body_line(self):
        # The Costituzione has no rubriche; its articles' first lines are short sentences.
        assert _act("costituzione.xml").rubriche() == {}

    @pytest.mark.parametrize("name,count", [
        ("dlgs_231_2001.xml", 104), ("legge_241_1990.xml", 50), ("codice_penale_trimmed.xml", 39)])
    def test_acts_with_headings_or_brackets_are_unchanged(self, name, count):
        assert len(_act(name).rubriche()) == count


class TestUnbracketedCleanup:
    """Shapes of the codice di procedura civile's export (21 October 2026)."""

    @pytest.mark.parametrize("text,key,rubrica", [
        # a bare note number after the final period (art. 473-bis)
        ("### Art. 473 bis\n\nArt. 473-bis\n\nAmbito di applicazione. Mutamento del rito. 178.\n\nLe disposizioni …",
         "473-bis", "Ambito di applicazione. Mutamento del rito"),
        # the closing bracket of the form it had (art. 807)
        ("### Art. 807\n\nArt. 807.\nCompromesso).\nIl compromesso deve …", "807", "Compromesso"),
        # note calls in brackets, no final period (art. 375)
        ("### Art. 375\n\nArt. 375.\nPronuncia in udienza pubblica o in camera di consiglio (171) (173)\nLa Corte …",
         "375", "Pronuncia in udienza pubblica o in camera di consiglio"),
    ])
    def test_cleaned(self, text, key, rubrica):
        from mcp_legal_it.lib.visualex.akn_parser import _unbracketed_rubrica
        assert _unbracketed_rubrica(text, key) == rubrica


class TestSplitOrdinal:
    """Normattiva's tree writes «135 sex decies» (codice del consumo, captured 21
    October 2026), its URN «135sexdecies»; a request may use either."""

    @pytest.mark.parametrize("spellings,key", [
        (["135 sex decies", "135-sex-decies", "135-sexdecies", "135sexdecies"], "135-sexdecies"),
        (["135 septies decies", "135-septiesdecies"], "135-septiesdecies"),
        (["2 quater decies.1", "2-quaterdecies.1"], "2-quaterdecies.1"),
    ])
    def test_both_spellings_compare_alike(self, spellings, key):
        assert {comparable_article_key(s) for s in spellings} == {key}

    @pytest.mark.parametrize("raw,key", [
        ("135 vicies semel", "135-vicies-semel"),   # not a word of the table joined
        ("2 bis", "2-bis"), ("171 octies 1", "171-octies.1"), ("2043", "2043")])
    def test_other_shapes_are_normalize_article_key(self, raw, key):
        assert comparable_article_key(raw) == key == normalize_article_key(raw)

    def test_the_answered_key_keeps_the_split(self):
        # /fetch_rubriche and the fingerprints answer normalize_article_key's keys.
        assert normalize_article_key("135 sex decies") == "135-sex-decies"

    TREE = [{"numero": "135 quindecies", "allegato": None},
            {"numero": "135 sex decies", "allegato": None},
            {"numero": "135 vicies semel", "allegato": None}]

    @pytest.mark.parametrize("article", ["135-sexdecies", "135-sex-decies", "135 sex decies"])
    def test_the_existence_check_finds_it(self, article):
        from mcp_legal_it.lib.visualex.albero_normattiva import articolo_nell_albero
        assert articolo_nell_albero(self.TREE, article, None) is True


class TestRepeatedNumberIsLinear:
    """`\\d+[\\w./-]*\\.?` overlapped: «Art. » + 20,000 digits + «!» took 7 s."""

    @pytest.mark.parametrize("line", ["Art. " + "1" * 20_000 + "!", "Art." + " " * 20_000 + "1!"])
    def test_hostile_line(self, line):
        import time
        from mcp_legal_it.lib.visualex.akn_parser import _REPEATED_NUMBER
        started = time.perf_counter()
        assert _REPEATED_NUMBER.fullmatch(line) is None
        assert time.perf_counter() - started < 0.5

    @pytest.mark.parametrize("line,matches", [
        ("Art. 1159.", True), ("Art. 2545-quinquiesdecies.", True), ("Art.1", True), ("art 25 bis", False),
        ("Art. 270-bis.1", True), ("Art.", False), ("Arte 1", False),
    ])
    def test_same_lines(self, line, matches):
        from mcp_legal_it.lib.visualex.akn_parser import _REPEATED_NUMBER
        assert bool(_REPEATED_NUMBER.fullmatch(line)) is matches


@pytest.mark.parametrize("asked", ["135-sexdecies", "135 sex decies", "135-sexiesdecies"])
def test_a_split_ordinal_only_in_an_annex_is_read_there(asked):
    """The tree's «135 sex decies» in annex 1 is the request's «135-sexdecies» (or its other
    spelling): the act's spelling is found there, never the dispositivo's art. 1."""
    from mcp_legal_it.lib.visualex.albero_normattiva import grafia_dell_atto
    tree = [{"numero": "1", "allegato": None}, {"numero": "135 sex decies", "allegato": "1"}]
    articolo, esiste = grafia_dell_atto(tree, asked, "1")
    assert esiste is True
