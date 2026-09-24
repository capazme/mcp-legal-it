"""The LegalITA metrics.

Three tracks, reported separately and never combined into a single score.
The white paper argues the capabilities dissociate — a system can reason well
and ground badly — and averaging them hides exactly the risk profile a lawyer
needs to see.

Notation follows the paper:
    R_i        task i passes iff every required criterion passes   (eq. 1)
    AllPass    mean of R_i over tasks                              (eq. 2)
    GOG_i      |G_i| / |C_i|, zero when the answer cited nothing   (eq. 6)
    GOG        unweighted mean of GOG_i over tasks                 (eq. 7)
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping, Sequence

from benchmarks.legalita.schema import Citation, Task

Verdicts = Mapping[str, Mapping[str, bool]]
CitationsByTask = Mapping[str, Sequence[Citation]]
Tasks = Mapping[str, Task]


def _require_full_coverage(task_id: str, subset_ids: set[str], criteria: Mapping[str, bool]) -> None:
    """Raise if any criterion id in `subset_ids` has no verdict in `criteria`.

    A missing verdict is a pipeline bug (an incomplete judge output), not a
    legal finding — it must never be silently treated as a pass (dropped from
    the denominator) nor as a fail (which would corrupt the measurement in
    the other direction while hiding the same bug).
    """
    missing = subset_ids - criteria.keys()
    if missing:
        raise ValueError(
            f"task {task_id!r} is missing verdicts for required criteria "
            f"{sorted(missing)}"
        )


def _criteria_rate(
    verdicts: Verdicts, tasks: Tasks, selector, *, strict: bool
) -> float:
    """Shared engine for criterion_rate/bonus_rate: rate over a criterion subset.

    `selector` picks the subset (required or bonus) off a `Task`; the caller
    never has to know which criterion ids belong to which subset — the
    function looks it up itself from `tasks[task_id]`. When `strict` is True,
    every id in the subset must have a verdict or the call raises (see
    `_require_full_coverage`). A verdict key with no matching criterion on
    the `Task` is always ignored silently — it belongs to a different subset
    (e.g. a bonus verdict passed alongside required ones) and is scored by
    whichever call handles that subset.
    """
    total = 0
    passed = 0
    for task_id, criteria in verdicts.items():
        subset_ids = {c.id for c in selector(tasks[task_id])}
        if strict:
            _require_full_coverage(task_id, subset_ids, criteria)
        for criterion_id, verdict in criteria.items():
            if criterion_id in subset_ids:
                total += 1
                if verdict:
                    passed += 1
    if total == 0:
        return 0.0
    return passed / total


def all_pass(verdicts: Verdicts, tasks: Tasks) -> float:
    """eq. 1-2. A task passes only if every one of its required criteria passed.

    The required set is selected internally via `Task.required_criteria()` —
    bonus verdicts present in the same dict are filtered out before scoring,
    so a failing bonus criterion can never drag down all_pass. Every required
    criterion must have a verdict; a required criterion absent from `verdicts`
    raises rather than being silently treated as a pass (see
    `_require_full_coverage`).
    """
    if not verdicts:
        return 0.0
    passed = 0.0
    for task_id, criteria in verdicts.items():
        required_ids = {c.id for c in tasks[task_id].required_criteria()}
        _require_full_coverage(task_id, required_ids, criteria)
        required_verdicts = [v for cid, v in criteria.items() if cid in required_ids]
        if required_verdicts and all(required_verdicts):
            passed += 1.0
    return passed / len(verdicts)


def criterion_rate(verdicts: Verdicts, tasks: Tasks) -> float:
    """eq. 3. Partial credit across all required criteria, ignoring task boundaries.

    The required set is selected internally via `Task.required_criteria()`.
    Strict: a required criterion absent from `verdicts` raises rather than
    silently dropping out of the denominator.
    """
    return _criteria_rate(verdicts, tasks, lambda t: t.required_criteria(), strict=True)


def bonus_rate(verdicts: Verdicts, tasks: Tasks) -> float:
    """eq. 4. Same shape as criterion_rate, computed over bonus criteria only.

    The bonus set is selected internally via `Task.bonus_criteria()`. Kept
    separate, with its own selector, so a bonus verdict can never leak into
    the required-only computations of all_pass/criterion_rate and vice versa.

    Deliberately NOT strict, unlike criterion_rate: judges commonly skip
    bonus evaluation once a task has already failed on its required
    criteria, so a missing bonus verdict is expected pipeline behaviour, not
    a bug. It is simply excluded from both the numerator and denominator —
    the rate is computed over whichever bonus criteria were actually judged.
    """
    return _criteria_rate(verdicts, tasks, lambda t: t.bonus_criteria(), strict=False)


def gog(citations_by_task: CitationsByTask) -> float:
    """eq. 6-7. Grounding on the legal issue, averaged per task.

    A task that produced no citations scores 0, not undefined: refusing to
    cite is a grounding failure, not an absence of evidence.
    """
    if not citations_by_task:
        return 0.0
    per_task = []
    for citations in citations_by_task.values():
        if not citations:
            per_task.append(0.0)
            continue
        grounded = sum(1 for c in citations if c.counts_as_grounded())
        per_task.append(grounded / len(citations))
    return sum(per_task) / len(per_task)


def coverage(citations_by_task: CitationsByTask) -> float:
    """eq. 8-9. Share of tasks with at least one issue-covering citation."""
    if not citations_by_task:
        return 0.0
    hits = sum(
        1.0
        for citations in citations_by_task.values()
        if any(c.counts_as_grounded() for c in citations)
    )
    return hits / len(citations_by_task)


def mdd_score(outcomes: Iterable[bool]) -> float:
    """eq. 5. Share of adversarial tasks where criterion C-001 passed."""
    values = list(outcomes)
    if not values:
        return 0.0
    return sum(1.0 for v in values if v) / len(values)


def cohens_kappa(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Chance-corrected agreement between two judges on binary verdicts.

    When both judges give the same single constant verdict across the whole
    sample, expected agreement `pe` is exactly 1 and the kappa denominator
    `(1 - pe)` is zero: kappa is mathematically undefined there, because
    there is no chance agreement left to correct for. Algebraically, `pe == 1`
    forces `po == 1` too (both sequences are the same constant, so they agree
    on every item) — this function returns 1.0 for that case, which reads as
    "perfect agreement" rather than "nothing to correct for".

    That reading is safe for the aggregate kappa over the full verdict set,
    where a fully degenerate sample (every single verdict identical, across
    every task and criterion) is implausible. It is NOT safe to assume for a
    per-subgroup kappa — per criterion, per domain, per arm — where a small
    subgroup can legitimately be fully degenerate (e.g. every judge agrees
    "pass" on one easy criterion). Returning 1.0 there would misrepresent an
    absence of variance as perfect agreement. Callers computing kappa per
    subgroup must check for degeneracy (`pe == 1`) themselves before trusting
    the result.
    """
    if len(a) != len(b):
        raise ValueError("judge verdict sequences must have the same length")
    n = len(a)
    if n == 0:
        return float("nan")

    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    p_a = sum(1 for x in a if x) / n
    p_b = sum(1 for y in b if y) / n
    expected = p_a * p_b + (1 - p_a) * (1 - p_b)

    if math.isclose(expected, 1.0):
        return 1.0
    return (observed - expected) / (1 - expected)


def mcnemar_exact(pairs: list[tuple[bool, bool]]) -> dict:
    """Exact two-sided McNemar test on paired binary outcomes.

    Why paired: the three arms answer the SAME tasks, so their outcomes are
    matched pairs, not independent samples. An arm-vs-arm comparison built
    from two separate bootstrap CIs (as elsewhere in this module) treats the
    two arms as if they had been run on different task sets, which throws
    away the correlation induced by sharing tasks and can call a difference
    significant (or not) for the wrong reason. McNemar conditions on that
    correlation by looking only at the pairs where the two arms disagree
    (Card et al., EMNLP 2020, on paired significance testing for NLP system
    comparisons; this is standard McNemar practice for paired classifiers).

    `b` counts pairs where the first arm passed and the second failed;
    `c` counts the reverse. Concordant pairs (both pass or both fail) carry
    no information about which arm is better and are excluded from both the
    count and the test. `n = b + c` is the discordant count the exact
    binomial test runs over, under the null hypothesis that a discordant
    pair is equally likely to favour either arm (p=0.5 per trial).

    The p-value is `min(1.0, 2 * sum(comb(n, k) for k in 0..min(b, c)) /
    2**n)` -- twice the one-sided tail probability of seeing an imbalance at
    least as extreme as observed, computed exactly via `math.comb` rather
    than a normal/chi-square approximation (unreliable at the ~30-task scale
    this benchmark runs). The `min(b, c) == n/2` case double-counts the
    central bin in both tails, which is why the result must be capped at
    1.0 rather than trusted raw.

    `n == 0` (no discordant pairs -- the two arms agreed on literally every
    paired task) returns `p_value=None` (JSON null), never `1.0`. A p-value
    of 1.0 would read as "confirmed no difference"; zero discordant pairs is
    simply the absence of any evidence either way, which is a different
    claim and must never be conflated with it -- the fail-closed rule this
    whole benchmark applies to undefined statistics elsewhere too.
    """
    b = sum(1 for first, second in pairs if first and not second)
    c = sum(1 for first, second in pairs if not first and second)
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "discordant": n, "p_value": None}
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    p_value = min(1.0, 2 * tail / (2**n))
    return {"b": b, "c": c, "discordant": n, "p_value": p_value}


def bootstrap_ci(
    values: Sequence[float],
    seed: int = 20250107,
    iterations: int = 10000,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for the mean.

    Deterministic for a fixed seed, because a benchmark whose confidence
    intervals move between runs is not a benchmark.

    Rejects `iterations < 100` and `alpha` outside the open interval (0, 1):
    too few resamples produces a CI that is noise dressed as precision, and
    an out-of-range alpha can silently invert the interval (lo > hi) — the
    kind of thing nobody notices in a published report until someone else
    does.
    """
    if iterations < 100:
        raise ValueError(
            f"iterations must be >= 100, got {iterations}; fewer resamples "
            "produce a confidence interval that is noise dressed as precision"
        )
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in the open interval (0, 1), got {alpha!r}")

    if not values:
        return (float("nan"), float("nan"))

    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(iterations):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()

    lo_index = int((alpha / 2) * iterations)
    hi_index = min(int((1 - alpha / 2) * iterations), iterations - 1)
    return (means[lo_index], means[hi_index])
