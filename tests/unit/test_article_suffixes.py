"""The ordinal suffix table every article-number pattern reads.

The table is VisuaLex's (``lib/visualex/article_suffixes.py``, imported byte for
byte); VisuaLex's ``apps/web`` and ``apps/server`` mirror it in TypeScript and its
own tests pin the mirrors to it, so pinning our copy to VisuaLex's file keeps all
four in step. The cases of ``TestTable`` and ``TestNormalizeArticleKey`` are
VisuaLex's ``services/visualex/tests/test_article_suffixes.py`` (MPL-2.0, at
``eca698dc``); the rest are the places in mcp-legal-it that kept a private copy
stopping at "decies", where "art. 25-terdecies" was read as art. 25-ter.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.italgiure.client import build_norma_variants, norma_is_qualified
from mcp_legal_it.lib.visualex import article_suffixes
from mcp_legal_it.lib.visualex.akn_parser import normalize_article_key
from mcp_legal_it.lib.visualex.article_suffixes import ARTICLE_ORDINAL_SUFFIXES, ARTICLE_SUFFIX_ALTERNATION
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata
from mcp_legal_it.lib.visualex.scraper import _article_identity

#: sha256 of VisuaLex's ``services/visualex/visualex_api/tools/article_suffixes.py`` at
#: ``eca698dc``. A change on either side must be made on both, the TypeScript mirrors included.
VISUALEX_SHA256 = "eeda117e62581f533fe163c5f9c803366c2ce3dc6763850c71fea79f9a046688"

# The suffixes Normattiva actually returned (VisuaLex's tests/test_article_existence.py).
LIVE_SUFFIXES = [
    "bis", "ter", "quater", "quinquies", "sexies", "septies", "octies",
    "novies", "decies", "undecies", "terdecies", "quaterdecies",
    "quinquiesdecies", "septiesdecies", "octiesdecies", "noviesdecies",
    "duodevicies", "undevicies",
    # art. 21-nonies l. 241/1990, art. 25-nonies d.lgs. 231/2001
    "nonies",
]


def test_the_module_is_visualex_s_file_byte_for_byte():
    testo = Path(article_suffixes.__file__).read_bytes()
    corpo = testo[testo.index(b'"""'):]  # below the licence and provenance header
    assert hashlib.sha256(corpo).hexdigest() == VISUALEX_SHA256


class TestTable:
    @pytest.mark.parametrize("suffix", LIVE_SUFFIXES)
    def test_live_spellings_are_covered(self, suffix):
        assert suffix in ARTICLE_ORDINAL_SUFFIXES

    def test_alternation_is_ordered_longest_first(self):
        parts = ARTICLE_SUFFIX_ALTERNATION.split("|")
        assert parts == sorted(parts, key=len, reverse=True)

    @pytest.mark.parametrize("suffix", LIVE_SUFFIXES)
    def test_alternation_matches_the_whole_suffix(self, suffix):
        m = re.match(ARTICLE_SUFFIX_ALTERNATION, suffix, re.IGNORECASE)
        assert m is not None and m.group(0) == suffix

    def test_no_duplicates(self):
        assert len(set(ARTICLE_ORDINAL_SUFFIXES)) == len(ARTICLE_ORDINAL_SUFFIXES)


class TestPublicApi:
    def test_the_api_alternation_is_the_table_s(self):
        assert api.ARTICLE_SUFFIX_ALTERNATION == ARTICLE_SUFFIX_ALTERNATION

    def test_the_api_groups_cover_the_table_and_nothing_else(self):
        spellings = [s for gruppo in api.SUFFISSI_ARTICOLO for s in gruppo]
        assert len(spellings) == len(set(spellings))
        assert set(spellings) | {"semel"} == set(ARTICLE_ORDINAL_SUFFIXES)

    def test_the_groups_run_from_2_to_20(self):
        assert api.SUFFISSI_ARTICOLO[0] == ("bis",) and api.SUFFISSI_ARTICOLO[-1][0] == "vicies"
        assert len(api.SUFFISSI_ARTICOLO) == 19


class TestNormalizeArticleKey:
    """VisuaLex's normaliser: the canonical key agrees on every separator, at every length."""

    @pytest.mark.parametrize("raw,expected", [
        ("25 terdecies", "25-terdecies"),
        ("25-terdecies", "25-terdecies"),
        ("25terdecies", "25-terdecies"),
        ("art. 25 quinquiesdecies", "25-quinquiesdecies"),
        ("2409 NOVIESDECIES", "2409-noviesdecies"),
        ("25undevicies", "25-undevicies"),
        ("21 nonies", "21-nonies"),
        ("21-nonies", "21-nonies"),
        # shapes the table cannot spell: the fallback keeps them, a trailing digit is a sub-number
        ("270 bis.1", "270-bis.1"),
        ("171 octies 1", "171-octies.1"),
        ("135 sex decies", "135-sex-decies"),
        ("2 bis", "2-bis"),
        ("2043", "2043"),
    ])
    def test_canonical_form(self, raw, expected):
        assert normalize_article_key(raw) == expected


class TestNoPrivateCopyStopsAtDecies:
    def test_a_spaced_long_suffix_builds_a_urn_without_spaces(self):
        nv = NormaVisitata(Norma("decreto legislativo", "2001-06-08", "231"), "25 terdecies")
        assert nv.url().endswith("~art25terdecies")

    def test_italgiure_searches_the_article_asked_not_its_head(self):
        q = build_norma_variants("art. 25-terdecies d.lgs. 231/2001")
        assert '"art. 25-terdecies d.lgs. 231/2001"' in q
        assert "decies d.lgs" not in q.replace("terdecies d.lgs", "")

    def test_italgiure_sees_the_act_after_a_long_suffix(self):
        assert norma_is_qualified("art. 25-terdecies d.lgs. 231/2001")
        assert not norma_is_qualified("art. 25-terdecies")
        # "bisogna" is a word, not art. 5-bis followed by "ogna"
        assert norma_is_qualified("art. 5 bisogna")

    def test_the_act_index_reads_suffixes_past_sexiesdecies(self):
        from mcp_legal_it.api._norme import _VOCE_ARTICOLO

        m = _VOCE_ARTICOLO.match("25-septiesdecies- Delitti contro il patrimonio culturale")
        assert m and m.group(1) == "25-septiesdecies" and m.group(2).startswith("Delitti")

    @pytest.mark.parametrize("a,b", [
        ("2-duodevicies", "2-octiesdecies"),
        ("2-undevicies", "2-noviesdecies"),
        ("2-vices", "2-vicies"),
        ("21-nonies", "21-novies"),
    ])
    def test_spelling_variants_are_the_same_article(self, a, b):
        assert _article_identity(a) == _article_identity(b)
