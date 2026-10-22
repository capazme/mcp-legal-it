# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_akn_parser.py at 0f1477c2.
# Adapted: the imports name this package, and the codice penale fixture is the whole
# export (tests/fixtures/akn/codice_penale.xml) instead of VisuaLex's trimmed copy.
"""Pure parser tests. No network: XML string in, ParsedAct out."""
import re
from pathlib import Path

import pytest

from mcp_legal_it.lib.visualex.akn_parser import ParsedAct, normalize_article_key, parse_akn, presentable_title

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "akn"


@pytest.fixture(scope="module")
def l241():
    return parse_akn((FIXTURES / "legge_241_1990.xml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def costituzione():
    return parse_akn((FIXTURES / "costituzione.xml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cp():
    return parse_akn((FIXTURES / "codice_penale.xml").read_text(encoding="utf-8"))


class TestNormalizeArticleKey:
    @pytest.mark.parametrize("raw,expected", [
        ("2043", "2043"),
        ("art. 2 bis", "2-bis"),
        ("art_2-bis", "2-bis"),
        ("2 BIS", "2-bis"),
        ("2bis", "2-bis"),
        ("21-octies", "21-octies"),
        ("articolo 5", "5"),
        ("", ""),
    ])
    def test_canonical_form(self, raw, expected):
        assert normalize_article_key(raw) == expected


class TestFlatStructure:
    def test_detects_flat(self, l241):
        assert l241.structure == "flat"

    def test_article_count(self, l241):
        assert l241.article_count == 51

    def test_bis_forms_are_equivalent(self, l241):
        a = l241.article("2-bis")
        assert a
        assert l241.article("2 bis") == a
        assert l241.article("art. 2 bis") == a

    def test_modification_markers_are_stripped(self, l241):
        assert "((" not in l241.full_text()

    def test_missing_article_is_none(self, l241):
        assert l241.article("99999") is None

    def test_full_text_preserves_order(self, l241):
        text = l241.full_text()
        assert text.index("Art. 1") < text.index("Art. 3")


class TestComponentStructure:
    def test_detects_component(self, cp):
        assert cp.structure == "component"

    def test_articles_are_reachable(self, cp):
        assert cp.article("1")

    def test_dominant_part_is_mirrored_into_articles(self, cp):
        assert cp.articles
        assert cp.order


class TestSourceProperties:
    """Facts about Normattiva's export that the design depends on.

    These are not aspirations — they are why AKN is a fallback source and not
    the display text. If one of these ever starts failing, the design decision
    should be revisited.
    """

    def test_the_export_transliterates_accents(self, l241):
        text = l241.full_text()
        assert "attivita'" in text
        assert "attività" not in text

    def test_articles_carry_a_markdown_heading(self, l241):
        assert l241.article("3").startswith("### ")


class TestRobustness:
    def test_empty_xml_does_not_crash(self):
        act = parse_akn("")
        assert isinstance(act, ParsedAct)
        assert act.article_count == 0

    def test_garbage_does_not_crash(self):
        assert parse_akn("<nonsense/>").article_count == 0

    def test_entities_are_not_resolved(self, tmp_path):
        """XXE guard: an external entity must not be expanded."""
        evil = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            '<akomaNtoso><body><article eId="art_1">'
            '<num>Art. 1</num><content><p>&xxe;</p></content>'
            '</article></body></akomaNtoso>'
        )
        act = parse_akn(evil)
        assert "root:" not in act.full_text()


class TestRubriche:
    """Article titles for the index.

    Normattiva's article tree carries only bare numbers, so an index built from
    it can show nothing but numbers. The AKN export is where the titles are.
    """

    def test_flat_act_takes_the_rubrica_from_the_heading(self, l241):
        r = l241.rubriche()
        assert r["3"] == "Motivazione del provvedimento"
        assert r["1"] == "Principi generali dell'attività amministrativa"

    def test_component_act_takes_the_parenthesised_block(self, cp):
        # The codici carry no <heading>; the rubrica is its own block below the
        # repeated "Art. N." line.
        r = cp.rubriche()
        assert any(v for v in r.values()), "no rubrica extracted from a component act"

    def test_the_article_number_is_never_mistaken_for_a_rubrica(self, costituzione):
        """A heading with no title must yield nothing.

        "### Art. 1." previously matched the heading rule with "1." captured as
        the title, so every article of the Costituzione got its own number as
        its rubrica.
        """
        r = costituzione.rubriche()
        assert r == {}, f"the Costituzione has no rubriche, got {list(r.items())[:3]}"

    def test_articles_without_a_rubrica_are_absent_not_empty(self, l241):
        r = l241.rubriche()
        assert all(v.strip() for v in r.values())

    def test_accents_are_restored(self):
        from mcp_legal_it.lib.visualex.akn_parser import _restore_accents

        # The export transliterates every accented final vowel. In the article
        # TEXT that is left alone — it is a data contract — but a rubrica is a
        # title shown in a list, where it reads as a defect.
        assert _restore_accents("Responsabilita' del debitore") == "Responsabilità del debitore"
        assert _restore_accents("Liberta' personale") == "Libertà personale"
        assert _restore_accents("perche' e' cosi'") == "perché è così"

    def test_a_real_troncamento_keeps_its_apostrophe(self):
        from mcp_legal_it.lib.visualex.akn_parser import _restore_accents

        assert _restore_accents("un po' di tempo") == "un po' di tempo"
        assert _restore_accents("da' atto") == "da' atto"

    def test_extract_rubrica_handles_empty_input(self):
        from mcp_legal_it.lib.visualex.akn_parser import extract_rubrica

        assert extract_rubrica(None) is None
        assert extract_rubrica("") is None
        assert extract_rubrica("### Art. 1.") is None


class TestRubricheOnSuffixedArticles:
    """The ordinal suffix is part of the ID, not the title.

    "### Art. 2409 bis" is one article id with a space in it, while
    "### Art. 3. Motivazione" is an id followed by a rubrica. Nothing in the
    line itself distinguishes them, so the id is consumed by normalising
    against the key the caller already holds. Getting this wrong labelled every
    suffixed article of the codice civile with its own suffix: art. 2409-bis
    came back titled "bis".
    """

    def test_a_suffixed_article_gets_its_real_rubrica(self):
        from mcp_legal_it.lib.visualex.akn_parser import extract_rubrica

        # Exactly the shape the codice civile export emits for art. 2409-bis.
        text = ("### Art. 2409 bis\n\nArt. 2409-bis.\n\n"
                "(Revisione legale dei conti).\n\nLa revisione legale dei conti.")
        assert extract_rubrica(text, "2409-bis") == "Revisione legale dei conti"

    def test_the_suffix_is_never_returned_as_the_rubrica(self):
        from mcp_legal_it.lib.visualex.akn_parser import extract_rubrica

        # No parenthesised block at all: the heading's trailing "bis" belongs to
        # the id, so the honest answer is None, not "bis".
        text = "### Art. 2409 bis\n\nArt. 2409-bis.\n\nLa revisione legale dei conti."
        assert extract_rubrica(text, "2409-bis") is None

    def test_a_flat_act_keeps_its_inline_rubrica(self):
        from mcp_legal_it.lib.visualex.akn_parser import extract_rubrica

        # Consuming the id must not eat the title that sits on the same line —
        # and "Art. 3." carries a trailing dot the key does not.
        text = "### Art. 3. (Motivazione del provvedimento)\n\n1. Ogni provvedimento."
        assert extract_rubrica(text, "3") == "Motivazione del provvedimento"

    def test_trailing_punctuation_runs_are_tolerated(self):
        from mcp_legal_it.lib.visualex.akn_parser import extract_rubrica

        # The export writes ".." after the rubrica of art. 2409-octiesdecies.
        text = "### Art. 5\n\nArt. 5.\n\n(Comitato per il controllo sulla gestione)..\n\nSalvo diversa."
        assert extract_rubrica(text, "5") == "Comitato per il controllo sulla gestione"

    def test_an_abrogated_article_has_no_rubrica(self):
        from mcp_legal_it.lib.visualex.akn_parser import extract_rubrica

        text = "### Art. 2409 undecies\n\nArt. 2409-undecies.\n\nARTICOLO ABROGATO DAL D.LGS. 27 MARZO 2026, N. 47"
        assert extract_rubrica(text, "2409-undecies") is None


class TestPerArticleDates:
    """The date of the text currently in force, per article.

    Component acts (codici) give each article its own <doc> with its own FRBR
    metadata; the FRBRWork date there moves when the article is amended:
    art. 1 c.p. still reads 1931-07-01, art. 3-bis (d.lgs. 21/2018) reads
    2018-04-06. Flat acts have act-level metadata only, so no article date.
    """

    def test_component_act_dates_follow_each_article(self, cp):
        assert cp.dates["1"] == "1931-07-01"
        assert cp.dates["3-bis"] == "2018-04-06"

    def test_every_article_of_a_component_act_has_a_date(self, cp):
        assert set(cp.dates) == set(cp.order)

    def test_dates_are_iso_strings(self, cp):
        assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in cp.dates.values())

    def test_flat_acts_have_no_article_dates(self, l241):
        assert l241.dates == {}

    def test_parts_carry_their_own_dates(self, cp):
        main = cp.parts["Codice Penale"]
        assert main.dates["3-bis"] == "2018-04-06"
        assert cp.dates == main.dates


class TestPresentableTitle:
    """The act's title as a heading. The raw strings are the AKN `docTitle`s read live on 4 Oct 2026."""

    def test_the_gazzetta_code_goes(self):
        raw = "Nuova disciplina dell'ordinamento della professione forense. (13G00018)"
        assert presentable_title(raw) == "Nuova disciplina dell'ordinamento della professione forense"

    def test_another_act_of_the_same_shape(self):
        raw = "Disposizioni in materia di equo compenso delle prestazioni professionali. (23G00051)"
        assert presentable_title(raw) == "Disposizioni in materia di equo compenso delle prestazioni professionali"

    def test_amendment_brackets_are_unwrapped_and_accents_restored(self):
        raw = ("Codice in materia di protezione dei dati personali ((, recante disposizioni per "
               "l'adeguamento dell'ordinamento nazionale al regolamento (UE) n. 2016/679 del Parlamento "
               "europeo e del Consiglio, del 27 aprile 2016, relativo alla protezione delle persone "
               "fisiche con riguardo al trattamento dei dati personali, nonche' alla libera "
               "circolazione di tali dati e che abroga la direttiva 95/46/CE)).")
        assert presentable_title(raw) == (
            "Codice in materia di protezione dei dati personali, recante disposizioni per "
            "l'adeguamento dell'ordinamento nazionale al regolamento (UE) n. 2016/679 del Parlamento "
            "europeo e del Consiglio, del 27 aprile 2016, relativo alla protezione delle persone "
            "fisiche con riguardo al trattamento dei dati personali, nonché alla libera "
            "circolazione di tali dati e che abroga la direttiva 95/46/CE")

    def test_an_elision_is_not_an_accent(self):
        assert presentable_title("Norme sull'attivita' dell'ente.") == "Norme sull'attività dell'ente"

    def test_the_older_gazzetta_code_goes_too(self):
        # The shape of the older acts' code, from the codice penale's own AKN fixture.
        raw = "Approvazione del testo definitivo del Codice Penale. (030U1398)"
        assert presentable_title(raw) == "Approvazione del testo definitivo del Codice Penale"

    def test_brackets_closing_after_a_parenthesis_leave_no_space(self):
        raw = "Recepimento ((della direttiva 2014/24/UE (Testo rilevante ai fini del SEE)))."
        assert presentable_title(raw) == "Recepimento della direttiva 2014/24/UE (Testo rilevante ai fini del SEE)"

    def test_only_the_final_full_stop_goes_never_an_abbreviation(self):
        assert presentable_title("Modifiche al c.p.c.") == "Modifiche al c.p.c."
        assert presentable_title("Norme sulle S.p.A.") == "Norme sulle S.p.A."
        assert presentable_title("Norme generali..") == "Norme generali."

    def test_nothing_gives_nothing(self):
        assert presentable_title(None) == ""
        assert presentable_title("   ") == ""
        assert presentable_title("(13G00018)") == ""


class TestLinearOnWhitespace:
    """Adjacent whitespace runs made these quadratic or worse: an article number
    «1» + 8,000 spaces + «x» took 3 s in normalize_article_key (the number can come
    from a request), and a title ending in 2,000 spaces 3 s in the Gazzetta-code
    cleanup (cubic: a search from every position of the run; `presentable_title`
    collapses whitespace first, so that one is defensive). Sized so that a
    regression fails in about a second instead of stalling the suite."""

    SPACES = " " * 5_000

    @pytest.mark.parametrize("raw", [
        "1" + SPACES + "x", "1" + SPACES + "bisx", "1" + SPACES + "-" + SPACES + "x", "art. 1" + SPACES + "terx",
    ])
    def test_article_number(self, raw):
        import time
        started = time.perf_counter()
        normalize_article_key(raw)
        assert time.perf_counter() - started < 0.5

    # 3,000 spaces: the cubic search took about 10 s on it, so a regression fails here
    # instead of hanging the suite.
    @pytest.mark.parametrize("title", [
        "Titolo" + " " * 3_000 + "x", "Titolo" + " " * 3_000 + "." + " " * 3_000 + "x",
        "Titolo" + " " * 3_000 + "(13G0001",
    ])
    def test_gazzetta_code(self, title):
        import time
        from mcp_legal_it.lib.visualex.akn_parser import _GAZZETTA_CODE
        started = time.perf_counter()
        _GAZZETTA_CODE.sub("", title)
        presentable_title(title)
        assert time.perf_counter() - started < 0.5

    @pytest.mark.parametrize("raw,key", [
        ("2 bis", "2-bis"), ("2 - bis", "2-bis"), ("2-bis", "2-bis"), ("2bis", "2-bis"),
        ("2\t \tbis", "2-bis"), ("25  quinquiesdecies", "25-quinquiesdecies"),
    ])
    def test_same_keys(self, raw, key):
        assert normalize_article_key(raw) == key

    @pytest.mark.parametrize("title,clean", [
        ("Legge professionale forense. (13G00018)", "Legge professionale forense"),
        ("Codice penale (030U1398)", "Codice penale"),
        ("Codice penale.(030U1398)  ", "Codice penale"),
    ])
    def test_the_code_still_goes(self, title, clean):
        from mcp_legal_it.lib.visualex.akn_parser import _GAZZETTA_CODE
        assert _GAZZETTA_CODE.sub("", title) == clean
