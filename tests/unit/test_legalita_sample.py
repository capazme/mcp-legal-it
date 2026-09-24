"""Corpus sampling for the LegalITA replica benchmark.

The sample must be reproducible and must not depend on relevance ranking.
These tests pin both properties; the live Solr call itself is not unit-tested.
"""

import random
from datetime import date

import pytest

from benchmarks.legalita.corpus.sample import (
    DOMAIN_QUOTAS,
    WINDOW_END,
    WINDOW_START,
    SeedDecision,
    _scalar,
    build_enumeration_params,
    decision_from_doc,
    in_window,
    parse_datdep,
    select_sample,
)


def _decision(n: int, materia: str = "civil") -> SeedDecision:
    return SeedDecision(
        doc_id=f"doc-{n}",
        number=n,
        year=2025,
        deposited=date(2025, 3, 1),
        section="II",
        materia=materia,
        dispositivo="massima",
    )


def test_window_matches_the_paper():
    assert WINDOW_START == date(2025, 1, 7)
    assert WINDOW_END == date(2025, 5, 30)


def test_quotas_sum_to_thirty():
    assert DOMAIN_QUOTAS == {"civil": 13, "labour": 8, "tax": 9}
    assert sum(DOMAIN_QUOTAS.values()) == 30


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("20250315", date(2025, 3, 15)),
        ("2025-03-15", date(2025, 3, 15)),
        ("2025-03-15T00:00:00Z", date(2025, 3, 15)),
        ("15/03/2025", date(2025, 3, 15)),
    ],
)
def test_parse_datdep_accepts_the_shapes_solr_returns(raw, expected):
    assert parse_datdep(raw) == expected


def test_parse_datdep_returns_none_on_garbage():
    assert parse_datdep("") is None
    assert parse_datdep("non una data") is None


def test_parse_datdep_accepts_the_raw_multi_valued_solr_shape():
    """`datdep` is observed live as a list (`['20250315']`). `parse_datdep`
    is a public interface the not-yet-written live sampling script will
    call directly, so it must not rely on callers pre-normalising it."""
    assert parse_datdep(["20250315"]) == date(2025, 3, 15)
    assert parse_datdep("20250315") == date(2025, 3, 15)


def test_scalar_takes_the_first_element_of_a_multi_valued_field():
    """A Cassazione decision has exactly one number/date/section, so a
    multi-valued field is a storage artefact — taking the first element
    is deliberate, not an arbitrary truncation."""
    assert _scalar(["20250315", "20250316"]) == "20250315"
    assert _scalar([]) == ""
    assert _scalar(None) == ""
    assert _scalar("20250315") == "20250315"


def test_in_window_is_inclusive_at_both_ends():
    assert in_window(date(2025, 1, 7))
    assert in_window(date(2025, 5, 30))
    assert not in_window(date(2025, 1, 6))
    assert not in_window(date(2025, 5, 31))


def test_enumeration_params_never_carry_a_semantic_query():
    params = build_enumeration_params(sezioni=["1", "2", "3"], rows=50, start=0)
    assert params["q"] == "*:*"
    assert "score" not in params["sort"]
    assert "qf" not in params and "pf" not in params
    assert "anno:[2025 TO 2025]" in params["fq"]


def test_enumeration_params_paginate():
    assert build_enumeration_params(["5"], rows=50, start=100)["start"] == 100


def test_enumeration_params_filter_the_window_directly_in_solr():
    """Enumerate from the window's start via a Solr-side datdep range, not
    by paging past ~15,000 documents sorted the other way."""
    params = build_enumeration_params(sezioni=["1", "2", "3"], rows=50, start=0)
    assert params["sort"] == "pd asc, id asc"
    expected_clause = f"datdep:[{WINDOW_START:%Y%m%d} TO {WINDOW_END:%Y%m%d}]"
    assert expected_clause in params["fq"]


def test_enumeration_params_sort_has_a_unique_tie_breaker():
    """`pd` is day-granular with hundreds of decisions sharing a day, so
    pagination needs a unique secondary key or Solr can silently
    duplicate/skip documents across paged requests."""
    params = build_enumeration_params(sezioni=["5"], rows=50, start=0)
    assert params["sort"] == "pd asc, id asc"


def test_enumeration_params_window_clause_tracks_the_window_constants():
    """The range must be derived from WINDOW_START/WINDOW_END, not a
    hard-coded literal — changing the constants must change the clause."""
    import benchmarks.legalita.corpus.sample as sample_module

    original_start = sample_module.WINDOW_START
    try:
        sample_module.WINDOW_START = date(2025, 2, 1)
        params = build_enumeration_params(sezioni=["5"], rows=50, start=0)
        assert (
            f"datdep:[20250201 TO {sample_module.WINDOW_END:%Y%m%d}]"
            in params["fq"]
        )
    finally:
        sample_module.WINDOW_START = original_start


def test_decision_from_doc_handles_the_real_solr_shape():
    """`datdep` is observed live as a multi-valued list (`['20250315']`)
    while `numdec`/`anno`/`szdec` are observed as plain scalar strings —
    the reader must not assume either shape uniformly."""
    doc = {
        "id": "SN_SS20250315X34933CI0300",
        "numdec": "34933",
        "anno": "2025",
        "datdep": ["20250315"],
        "szdec": "3",
        "materia": "responsabilit",
        "tipoprov": "Ordinanza",
        "ocrdis": "rigetta il ricorso",
        "kind": "snciv",
    }
    decision = decision_from_doc(doc)
    assert decision is not None
    assert decision.doc_id == "SN_SS20250315X34933CI0300"
    assert decision.number == 34933
    assert decision.year == 2025
    assert decision.deposited == date(2025, 3, 15)
    assert decision.section == "3"
    assert in_window(decision.deposited)


def test_decision_from_doc_returns_none_when_date_is_unparseable():
    doc = {"id": "x", "numdec": "1", "anno": "2025", "datdep": ["garbage"], "szdec": "1"}
    assert decision_from_doc(doc) is None


def test_decision_from_doc_returns_none_when_a_numeric_field_is_missing():
    """A malformed document (missing `numdec`) must be dropped, not abort
    the whole enumeration with an uncaught ValueError from `int("")`."""
    doc = {"id": "x", "anno": "2025", "datdep": ["20250315"], "szdec": "1"}
    assert decision_from_doc(doc) is None


def test_select_sample_is_deterministic_for_a_fixed_seed():
    candidates = {"civil": [_decision(i) for i in range(100)]}
    first = select_sample(candidates, {"civil": 13}, seed=20250107)
    second = select_sample(candidates, {"civil": 13}, seed=20250107)
    assert [d.doc_id for d in first["civil"]] == [d.doc_id for d in second["civil"]]


def test_select_sample_honours_the_quota():
    candidates = {"civil": [_decision(i) for i in range(100)]}
    assert len(select_sample(candidates, {"civil": 13}, seed=20250107)["civil"]) == 13


def test_select_sample_takes_everything_when_short_of_quota():
    candidates = {"labour": [_decision(i) for i in range(5)]}
    assert len(select_sample(candidates, {"labour": 8}, seed=20250107)["labour"]) == 5


def test_different_seeds_give_different_samples():
    candidates = {"civil": [_decision(i) for i in range(100)]}
    a = [d.doc_id for d in select_sample(candidates, {"civil": 13}, seed=1)["civil"]]
    b = [d.doc_id for d in select_sample(candidates, {"civil": 13}, seed=2)["civil"]]
    assert a != b


def test_sample_is_returned_in_stable_order():
    candidates = {"civil": [_decision(i) for i in range(40)]}
    picked = select_sample(candidates, {"civil": 13}, seed=20250107)["civil"]
    assert [d.number for d in picked] == sorted(d.number for d in picked)


def test_select_sample_is_invariant_to_the_arrival_order_of_the_pool():
    """`rng.sample` draws by index, so reproducibility for a fixed seed
    must not depend on the order Solr happened to return documents in
    across separate paginated requests — the pool is canonicalised by
    doc_id before drawing. This is the test that would have caught a
    pipeline where the same seed produces a different sample because the
    fetch order differed between two runs."""
    ordered = [_decision(i) for i in range(100)]
    shuffled = ordered[:]
    random.Random("shuffle-fixture").shuffle(shuffled)
    assert [d.doc_id for d in shuffled] != [d.doc_id for d in ordered]

    from_ordered = select_sample({"civil": ordered}, {"civil": 13}, seed=20250107)
    from_shuffled = select_sample({"civil": shuffled}, {"civil": 13}, seed=20250107)
    assert (
        [d.doc_id for d in from_ordered["civil"]]
        == [d.doc_id for d in from_shuffled["civil"]]
    )
