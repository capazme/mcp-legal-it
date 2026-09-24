"""Citation extraction for the grounding track.

The hard requirement is symmetry: an answer that names a decision and an
answer that only gestures at 'consolidated case law' must BOTH produce
entries, because GOG divides issue-covering citations by citations produced.
Dropping the unidentifiable ones would hand a free pass to exactly the
failure mode the white paper found in GPT-5.5.
"""

from benchmarks.legalita.score.citations import extract_citations, parse_citation


def _raws(text: str) -> list[str]:
    return [c.raw for c in extract_citations(text, task_id="T", arm="bare")]


def test_parses_canonical_form():
    parsed = parse_citation("Cass. civ., sez. II, n. 12345/2025")
    assert parsed == {
        "court": "Cass. civ.",
        "section": "II",
        "number": 12345,
        "year": 2025,
    }


def test_parses_without_section():
    assert parse_citation("Cass. civ. n. 987/2024")["number"] == 987


def test_parses_sezioni_unite():
    parsed = parse_citation("Cass. civ., Sez. Un., n. 8500/2025")
    assert parsed["section"] == "Un."
    assert parsed["number"] == 8500


def test_parses_labour_section():
    assert parse_citation("Cass. sez. lav. n. 111/2025")["section"] == "lav."


def test_returns_none_on_unparseable_text():
    assert parse_citation("la giurisprudenza consolidata") is None


def test_extracts_multiple_identifiable_citations():
    text = (
        "Si vedano Cass. civ., sez. II, n. 12345/2025 e "
        "Cass. civ., sez. III, n. 6789/2025."
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert [c.parsed["number"] for c in citations] == [12345, 6789]
    assert all(c.identifiable for c in citations)
    assert [c.index for c in citations] == [0, 1]


def test_extracts_narrative_reference_as_unidentifiable():
    citations = extract_citations(
        "Secondo la giurisprudenza consolidata il committente non risponde.",
        task_id="T",
        arm="bare",
    )
    assert len(citations) == 1
    assert citations[0].identifiable is False
    assert citations[0].parsed is None
    assert citations[0].resolved is None


def test_mixed_answer_counts_both_kinds():
    text = (
        "La Corte ha piu volte affermato il principio; da ultimo "
        "Cass. civ., sez. I, n. 4321/2025."
    )
    citations = extract_citations(text, task_id="T", arm="web")
    assert [c.identifiable for c in citations] == [False, True]


def test_no_double_counting_when_narrative_introduces_a_named_decision():
    # 'orientamento consolidato' immediately followed by an identifiable
    # citation is ONE grounded claim, not one narrative plus one named.
    text = "Per orientamento consolidato (Cass. civ., sez. II, n. 100/2025) il patto e nullo."
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 1
    assert citations[0].identifiable is True


def test_empty_answer_produces_no_citations():
    assert extract_citations("", task_id="T", arm="bare") == []


def test_deduplicates_repeated_identical_citation():
    text = "Cass. civ., sez. II, n. 12345/2025 ... come detto, Cass. civ., sez. II, n. 12345/2025."
    assert len(extract_citations(text, task_id="T", arm="mcp")) == 1


def test_narrative_citations_are_never_deduplicated():
    # Two independent narrative hand-waves supporting two different claims
    # must both count as produced citations. Deduplicating them would shrink
    # the GOG denominator (issue-covering citations / citations produced)
    # and inflate the score -- rewarding exactly the ungrounded, unresolvable
    # hand-waving this metric exists to punish.
    text = (
        "Secondo la giurisprudenza consolidata il contratto e valido. "
        "Secondo la giurisprudenza consolidata anche l'atto collegato lo e."
    )
    citations = extract_citations(text, task_id="T", arm="bare")
    assert len(citations) == 2
    assert all(c.identifiable is False for c in citations)


def test_absorption_is_structural_not_a_character_count():
    # A 21-char gap with no sentence boundary must still be absorbed: proves
    # the rule is about clause structure (no '.', ';', ':', '!', '?', '\n'
    # between marker and citation), not an arbitrary distance threshold.
    text = "per giurisprudenza costante, si veda ad esempio Cass. civ. n. 1/2025."
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 1
    assert citations[0].identifiable is True


def test_absorption_survives_long_but_unbroken_clause():
    text = (
        "secondo la costante giurisprudenza in materia di responsabilita "
        "contrattuale, si veda Cass. civ. n. 10/2025"
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 1
    assert citations[0].identifiable is True


def test_abbreviation_dot_now_splits_ad_es():
    # There is no abbreviation masking any more: the period in "ad es." reads
    # as a sentence boundary like any other, so this now counts as 2 entries
    # instead of 1. This is the accepted under-absorption cost -- a single
    # grounded claim gets split -- traded deliberately against the unsafe
    # alternative (an allow-list that inflates GOG whenever a listed
    # abbreviation happens to end a real sentence). See the module docstring.
    text = "per giurisprudenza costante, si veda, ad es. Cass. civ. n. 1/2025."
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_abbreviation_dot_now_splits_cfr():
    # Same trade-off as above for "cfr." -- under-absorption accepted on
    # purpose, see the module docstring.
    text = "secondo la giurisprudenza consolidata, cfr. Cass. civ. n. 5/2025"
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_ecc_dot_splits_the_claim():
    # Regression: the case that motivated deleting the abbreviation
    # allow-list entirely. "ecc." sat in the surviving list of a previous
    # round and wrongly merged this into one citation -- "ecc." can end a
    # real sentence just like every other candidate abbreviation, so no
    # allow-list of them is safe. With masking removed, this now splits
    # correctly into 2 entries.
    text = (
        "Per giurisprudenza costante in materia di contratti, appalti, "
        "forniture, ecc. Cass. civ. n. 5/2025 affronta un tema diverso."
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2


def test_c_c_dot_splits_the_claim():
    # "c.c." ends real sentences constantly in Italian pleadings
    # ("la responsabilita ex art. 2043 c.c."). No masking -> it splits.
    text = "per orientamento costante, v. art. 2043 c.c. e Cass. civ. n. 7/2025"
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_anonymising_initial_l_splits_the_claim():
    # "L." is the standard Italian convention for anonymising a surname and
    # routinely ends a real sentence. Without masking it always splits --
    # under-absorption, the accepted cost.
    text = (
        "Secondo la giurisprudenza costante, il convenuto era stato citato "
        "con la sigla L. Il giudizio successivo riguarda una vicenda "
        "estranea, decisa da Cass. civ. n. 1/2025."
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_anonymising_initial_p_splits_the_claim():
    # Same as above for "p." ("pagina", but here another anonymising
    # initial) ending a real sentence.
    text = (
        "Secondo la giurisprudenza costante, il ricorrente era identificato "
        "con la sigla P. Il caso successivo riguarda una vicenda estranea, "
        "decisa da Cass. civ. n. 2/2025."
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_real_full_stop_still_separates_marker_from_citation():
    # Proves the sentence-boundary check itself works on a genuine full
    # stop: a real end-of-sentence period followed by a new sentence must
    # keep the narrative marker and the named citation apart.
    text = "La Corte ha piu volte affermato il principio. Da ultimo Cass. civ. n. 9/2025."
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_em_dash_between_marker_and_citation_splits_the_claim():
    # Regression (round 5): an em dash used as a clause break was not in the
    # original boundary set, so this wrongly absorbed into 1 entry. Unlike a
    # legal abbreviation's period, an em dash never occurs inside an Italian
    # abbreviation, so admitting it is unambiguous.
    text = (
        "Secondo la giurisprudenza costante il committente non risponde "
        "— tuttavia si consideri anche Cass. civ. n. 100/2025, che "
        "riguarda una fattispecie affatto diversa."
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_ellipsis_between_marker_and_citation_splits_the_claim():
    # Regression (round 5): an ellipsis used to trail off one clause before
    # starting the next was not in the original boundary set.
    text = (
        "Secondo la giurisprudenza costante il contratto e nullo … "
        "Cass. civ. n. 1/2025 riguarda pero un tema del tutto diverso."
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_numbered_list_marker_between_marker_and_citation_splits_the_claim():
    # Regression (round 5): a numbered-list marker ("2)") introducing the
    # second, independent claim was not in the original boundary set.
    text = (
        "1) Secondo la giurisprudenza costante il contratto e nullo "
        "2) Cass. civ. n. 1/2025 riguarda un tema del tutto diverso"
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_spaced_hyphen_bullet_between_marker_and_citation_splits_the_claim():
    # Regression (round 5): a hyphen used as a dash/bullet, with whitespace
    # on both sides, is treated as a boundary -- unlike a hyphen glued
    # inside a compound word (no surrounding whitespace), which is
    # deliberately left alone (see the module docstring's residual-gap
    # note): a hyphen between two words is far more often a compound than a
    # clause break, so no heuristic is applied to the glued case.
    text = (
        "- Secondo la giurisprudenza costante il contratto e nullo "
        "- Cass. civ. n. 1/2025 riguarda un tema del tutto diverso"
    )
    citations = extract_citations(text, task_id="T", arm="mcp")
    assert len(citations) == 2
    assert [c.identifiable for c in citations] == [False, True]


def test_parses_date_form_citation():
    parsed = parse_citation("Cass. civ., sentenza del 3 marzo 2025, n. 12345")
    assert parsed["number"] == 12345
    assert parsed["year"] == 2025


def test_parses_date_form_with_section_and_ordinanza():
    parsed = parse_citation("Cass. civ. sez. II, ordinanza del 12 gennaio 2025 n. 987")
    assert parsed["section"] == "II"
    assert parsed["number"] == 987
    assert parsed["year"] == 2025


def test_date_form_citation_extracted_as_identifiable():
    citations = extract_citations(
        "Come stabilito da Cass. civ., sentenza del 3 marzo 2025, n. 12345, "
        "il contratto e nullo.",
        task_id="T",
        arm="mcp",
    )
    assert len(citations) == 1
    assert citations[0].identifiable is True
    assert citations[0].parsed["number"] == 12345
    assert citations[0].parsed["year"] == 2025


# --- NARRATIVE_MARKERS accent tolerance -------------------------------------
#
# Prompts now use correct Italian orthography (Amendment A1), so evaluated
# models will typically answer in correctly-accented Italian too. A marker
# that only matched the unaccented spelling would silently miss those
# narrative citations, shrinking the GOG denominator and inflating GOG --
# the exact failure mode this metric exists to punish. Both spellings must
# match for every accent-bearing marker.


def test_narrative_marker_piu_volte_matches_accented_form():
    citations = extract_citations(
        "La Suprema Corte ha più volte affermato che il committente risponde.",
        task_id="T",
        arm="bare",
    )
    assert len(citations) == 1
    assert citations[0].identifiable is False


def test_narrative_marker_piu_volte_matches_unaccented_form():
    citations = extract_citations(
        "La Suprema Corte ha piu volte affermato che il committente risponde.",
        task_id="T",
        arm="bare",
    )
    assert len(citations) == 1
    assert citations[0].identifiable is False


def test_narrative_marker_e_principio_matches_accented_form():
    citations = extract_citations(
        "È principio consolidato che il committente risponde per fatto dell'appaltatore.",
        task_id="T",
        arm="bare",
    )
    assert len(citations) == 1
    assert citations[0].identifiable is False


def test_narrative_marker_e_principio_matches_unaccented_form():
    citations = extract_citations(
        "E principio pacifico che il committente risponde per fatto dell'appaltatore.",
        task_id="T",
        arm="bare",
    )
    assert len(citations) == 1
    assert citations[0].identifiable is False
