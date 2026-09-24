"""The paper's equations 1-9, plus judge agreement and confidence intervals.

These are the numbers the whole experiment reports, so they are tested
against hand-computed values rather than golden files.
"""

import math

import pytest

from benchmarks.legalita.schema import Citation, Criterion, Task
from benchmarks.legalita.score.metrics import (
    all_pass,
    bonus_rate,
    bootstrap_ci,
    cohens_kappa,
    coverage,
    criterion_rate,
    gog,
    mcnemar_exact,
    mdd_score,
)


def _cit(task_id, *, grounded):
    c = Citation(task_id=task_id, arm="bare", index=0, raw="x")
    if grounded:
        c.identifiable, c.resolved, c.covers_issue = True, True, True
    return c


def _task(task_id, criteria):
    """Minimal Task fixture — constructed directly, bypassing from_dict
    validation, since these tests only exercise required/bonus filtering."""
    return Task(
        id=task_id,
        track="jurisprudential",
        domain="civil",
        query="q",
        criteria=criteria,
        issue_status="settled",
        issue_summary="",
        seed_citation=None,
        builder_confidence="high",
        curated=False,
    )


def _required(*ids):
    return [Criterion(id=i, text=i, required=True) for i in ids]


def _all_criteria_required(tasks_criteria):
    """Build a tasks dict where every criterion id present is required."""
    return {
        task_id: _task(task_id, _required(*ids))
        for task_id, ids in tasks_criteria.items()
    }


def test_all_pass_requires_every_required_criterion():
    verdicts = {
        "T1": {"C-001": True, "C-002": True},   # passes
        "T2": {"C-001": True, "C-002": False},  # fails
        "T3": {"C-001": False},                 # fails
        "T4": {"C-001": True},                  # passes
    }
    tasks = _all_criteria_required(
        {"T1": ["C-001", "C-002"], "T2": ["C-001", "C-002"], "T3": ["C-001"], "T4": ["C-001"]}
    )
    assert all_pass(verdicts, tasks) == pytest.approx(0.5)


def test_all_pass_of_empty_set_is_zero():
    assert all_pass({}, {}) == 0.0


def test_all_pass_ignores_bonus_criteria():
    # The required criterion passes; the bonus criterion fails. all_pass
    # must stay 1.0 — a failing bonus can never drag down the pass/fail
    # verdict. This is the invariant Finding 1 protects structurally.
    task = _task(
        "T1",
        [
            Criterion(id="C-001", text="required", required=True),
            Criterion(id="B-001", text="bonus", required=False),
        ],
    )
    verdicts = {"T1": {"C-001": True, "B-001": False}}
    assert all_pass(verdicts, {"T1": task}) == pytest.approx(1.0)


def test_criterion_rate_counts_criteria_not_tasks():
    verdicts = {"T1": {"C-001": True, "C-002": True}, "T2": {"C-001": False}}
    tasks = _all_criteria_required({"T1": ["C-001", "C-002"], "T2": ["C-001"]})
    assert criterion_rate(verdicts, tasks) == pytest.approx(2 / 3)


def test_criterion_rate_ignores_bonus_verdicts():
    task = _task(
        "T1",
        [
            Criterion(id="C-001", text="required", required=True),
            Criterion(id="B-001", text="bonus", required=False),
        ],
    )
    # Bonus verdict is False but must not count toward criterion_rate.
    verdicts = {"T1": {"C-001": True, "B-001": False}}
    assert criterion_rate(verdicts, {"T1": task}) == pytest.approx(1.0)


def test_bonus_rate_is_independent_of_pass_fail():
    task = _task(
        "T1",
        [
            Criterion(id="C-001", text="required", required=True),
            Criterion(id="B-001", text="bonus", required=False),
            Criterion(id="B-002", text="bonus", required=False),
        ],
    )
    verdicts = {"T1": {"C-001": True, "B-001": True, "B-002": False}}
    assert bonus_rate(verdicts, {"T1": task}) == pytest.approx(0.5)


def test_all_pass_raises_when_a_required_criterion_has_no_verdict():
    # C-002 is required on the task but a judge omitted it from the verdicts
    # dict. This must never silently count as a pass.
    task = _task("T1", _required("C-001", "C-002"))
    with pytest.raises(ValueError, match=r"T1.*C-002"):
        all_pass({"T1": {"C-001": True}}, {"T1": task})


def test_criterion_rate_raises_when_a_required_criterion_has_no_verdict():
    task = _task("T1", _required("C-001", "C-002"))
    with pytest.raises(ValueError, match=r"T1.*C-002"):
        criterion_rate({"T1": {"C-001": True}}, {"T1": task})


def test_all_pass_and_criterion_rate_work_when_required_criteria_are_fully_covered():
    task = _task("T1", _required("C-001", "C-002"))
    verdicts = {"T1": {"C-001": True, "C-002": True}}
    tasks = {"T1": task}
    assert all_pass(verdicts, tasks) == pytest.approx(1.0)
    assert criterion_rate(verdicts, tasks) == pytest.approx(1.0)


def test_verdict_key_with_no_matching_criterion_is_ignored_silently():
    # C-999 has no corresponding Criterion on the Task at all (not required,
    # not bonus) — it must be ignored rather than raising or affecting the
    # rate, exactly as before this fix round.
    task = _task("T1", _required("C-001"))
    verdicts = {"T1": {"C-001": True, "C-999": False}}
    tasks = {"T1": task}
    assert all_pass(verdicts, tasks) == pytest.approx(1.0)
    assert criterion_rate(verdicts, tasks) == pytest.approx(1.0)


def test_bonus_rate_tolerates_a_missing_bonus_verdict():
    # B-002 is a bonus criterion on the task but has no verdict — judges
    # commonly skip bonus evaluation once required criteria have failed.
    # This must not raise; the rate is computed over judged bonus criteria.
    task = _task(
        "T1",
        [
            Criterion(id="C-001", text="required", required=True),
            Criterion(id="B-001", text="bonus", required=False),
            Criterion(id="B-002", text="bonus", required=False),
        ],
    )
    verdicts = {"T1": {"C-001": True, "B-001": True}}
    assert bonus_rate(verdicts, {"T1": task}) == pytest.approx(1.0)


def test_gog_averages_per_task_not_per_citation():
    # T1: 1 of 4 grounded (0.25). T2: 1 of 1 grounded (1.0). Mean = 0.625.
    # A citation-weighted mean would give 2/5 = 0.4 — the task mean is what
    # stops a single citation-heavy answer from dominating.
    citations = {
        "T1": [_cit("T1", grounded=True)] + [_cit("T1", grounded=False) for _ in range(3)],
        "T2": [_cit("T2", grounded=True)],
    }
    assert gog(citations) == pytest.approx(0.625)


def test_gog_scores_zero_when_no_citations_produced():
    assert gog({"T1": []}) == 0.0


def test_gog_scores_zero_when_citations_are_all_narrative():
    assert gog({"T1": [_cit("T1", grounded=False)]}) == 0.0


def test_coverage_is_share_of_tasks_with_at_least_one_grounded_citation():
    citations = {
        "T1": [_cit("T1", grounded=True), _cit("T1", grounded=False)],
        "T2": [_cit("T2", grounded=False)],
        "T3": [],
        "T4": [_cit("T4", grounded=True)],
    }
    assert coverage(citations) == pytest.approx(0.5)


def test_unresolved_citation_never_counts_as_grounded():
    c = Citation(task_id="T1", arm="mcp", index=0, raw="Cass. civ. n. 1/2025")
    c.identifiable, c.resolved, c.covers_issue = True, True, None
    assert gog({"T1": [c]}) == 0.0
    assert coverage({"T1": [c]}) == 0.0


def test_mdd_score_is_share_of_passing_tasks():
    assert mdd_score([True, True, False, False, True]) == pytest.approx(0.6)


def test_mdd_score_of_empty_is_zero():
    assert mdd_score([]) == 0.0


def test_cohens_kappa_perfect_agreement():
    assert cohens_kappa([True, False, True], [True, False, True]) == pytest.approx(1.0)


def test_cohens_kappa_hand_computed():
    # 10 items. Both judges say True on 6, both False on 2, disagree on 2.
    a = [True] * 7 + [False] * 3
    b = [True] * 6 + [False] * 1 + [True] * 1 + [False] * 2
    # po = 8/10 = 0.8
    # p_a(True)=0.7, p_b(True)=0.7 -> pe = 0.7*0.7 + 0.3*0.3 = 0.58
    # kappa = (0.8 - 0.58) / (1 - 0.58) = 0.22 / 0.42
    assert cohens_kappa(a, b) == pytest.approx(0.22 / 0.42)


def test_cohens_kappa_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        cohens_kappa([True], [True, False])


def test_cohens_kappa_degenerate_when_both_judges_always_agree_on_one_label():
    # pe == 1: kappa is undefined; we return 1.0 on perfect agreement.
    assert cohens_kappa([True, True], [True, True]) == pytest.approx(1.0)


def test_cohens_kappa_degenerate_with_disagreement_returns_zero():
    assert cohens_kappa([True, True], [True, False]) == pytest.approx(0.0)


def test_bootstrap_ci_is_deterministic_for_a_fixed_seed():
    values = [1.0] * 30 + [0.0] * 20
    first = bootstrap_ci(values, seed=20250107, iterations=2000)
    second = bootstrap_ci(values, seed=20250107, iterations=2000)
    assert first == second


def test_bootstrap_ci_brackets_the_sample_mean():
    values = [1.0] * 30 + [0.0] * 20
    lo, hi = bootstrap_ci(values, seed=20250107, iterations=2000)
    assert lo < 0.6 < hi
    assert 0.0 <= lo <= hi <= 1.0


def test_bootstrap_ci_of_constant_sample_is_a_point():
    lo, hi = bootstrap_ci([0.5] * 10, seed=20250107, iterations=500)
    assert lo == pytest.approx(0.5)
    assert hi == pytest.approx(0.5)


def test_bootstrap_ci_of_empty_sample_is_nan():
    lo, hi = bootstrap_ci([], seed=20250107, iterations=100)
    assert math.isnan(lo) and math.isnan(hi)


def test_bootstrap_ci_rejects_too_few_iterations():
    with pytest.raises(ValueError, match="iterations"):
        bootstrap_ci([0.1, 0.9, 0.5], iterations=1)


def test_bootstrap_ci_rejects_iterations_just_below_the_floor():
    with pytest.raises(ValueError, match="iterations"):
        bootstrap_ci([0.1, 0.9, 0.5], iterations=99)


def test_bootstrap_ci_accepts_iterations_at_the_floor():
    lo, hi = bootstrap_ci([0.1, 0.9, 0.5], iterations=100)
    assert 0.0 <= lo <= hi <= 1.0


def test_bootstrap_ci_rejects_alpha_outside_open_unit_interval():
    with pytest.raises(ValueError, match="alpha"):
        bootstrap_ci([0.1, 0.9, 0.5], iterations=100, alpha=1.5)
    with pytest.raises(ValueError, match="alpha"):
        bootstrap_ci([0.1, 0.9, 0.5], iterations=100, alpha=0.0)
    with pytest.raises(ValueError, match="alpha"):
        bootstrap_ci([0.1, 0.9, 0.5], iterations=100, alpha=1.0)


# --- Amendment A2: mcnemar_exact ---------------------------------------


def test_mcnemar_exact_hand_computed_b5_c0():
    # All 5 discordant pairs favour the first arm (b=5, c=0). Exact two-sided
    # binomial p=0.5 over n=5 trials: P(0 or 5 successes) = 2 * C(5,0)/2**5
    # = 2 * 1/32 = 0.0625 -- hand-computed in the brief.
    pairs = [(True, False)] * 5
    result = mcnemar_exact(pairs)
    assert result["b"] == 5
    assert result["c"] == 0
    assert result["discordant"] == 5
    assert result["p_value"] == pytest.approx(0.0625)


def test_mcnemar_exact_b1_c1_caps_at_one():
    # n=2, k=min(1,1)=1: tail = C(2,0)+C(2,1) = 1+2 = 3.
    # p = 2*3/4 = 1.5 -- must be capped at 1.0, never reported raw.
    pairs = [(True, False), (False, True)]
    result = mcnemar_exact(pairs)
    assert result["b"] == 1
    assert result["c"] == 1
    assert result["discordant"] == 2
    assert result["p_value"] == pytest.approx(1.0)


def test_mcnemar_exact_zero_discordant_pairs_returns_none_not_one():
    # Both arms agree on every task (all concordant) -- fail-closed: "no
    # evidence either way" must never render as p=1.0 ("confirmed equal").
    pairs = [(True, True), (False, False), (True, True)]
    result = mcnemar_exact(pairs)
    assert result["b"] == 0
    assert result["c"] == 0
    assert result["discordant"] == 0
    assert result["p_value"] is None


def test_mcnemar_exact_empty_pairs_is_zero_discordant():
    result = mcnemar_exact([])
    assert result == {"b": 0, "c": 0, "discordant": 0, "p_value": None}


def test_mcnemar_exact_is_symmetric_under_swapping_arms():
    # Swapping which arm is "first" in every pair swaps b and c but must
    # leave the p-value unchanged -- McNemar tests the discordant split,
    # not which arm is which.
    pairs = [(True, False), (True, False), (False, True), (True, True), (False, False)]
    swapped = [(y, x) for x, y in pairs]
    original = mcnemar_exact(pairs)
    flipped = mcnemar_exact(swapped)
    assert flipped["b"] == original["c"]
    assert flipped["c"] == original["b"]
    assert flipped["p_value"] == pytest.approx(original["p_value"])


def test_mcnemar_exact_hand_computed_asymmetric_case():
    # n=10 discordant, b=2, c=8: k=min(2,8)=2.
    # tail = C(10,0)+C(10,1)+C(10,2) = 1+10+45 = 56.
    # p = 2*56/1024 = 112/1024 = 0.109375.
    pairs = [(True, False)] * 2 + [(False, True)] * 8
    result = mcnemar_exact(pairs)
    assert result["p_value"] == pytest.approx(0.109375)


def test_mcnemar_exact_concordant_pairs_are_excluded_from_the_count():
    # Concordant pairs (both True or both False) carry no discordance
    # information and must not inflate b, c or n.
    pairs = [(True, True)] * 3 + [(False, False)] * 3 + [(True, False)]
    result = mcnemar_exact(pairs)
    assert result["b"] == 1
    assert result["c"] == 0
    assert result["discordant"] == 1
