"""Paired analysis (DESIGN §5): McNemar on binary outcomes, rank-biserial
effect size, bootstrap confidence intervals, pre-registered non-inferiority.

All functions are pure and exact (no RNG where a closed formula exists);
the bootstrap uses the protocol seed so the CI is reproducible. The
non-inferiority test is declared BEFORE looking at data: margin in the wave
tag, one-sided risk difference with the Newcombe hybrid-score interval.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


def mcnemar_exact(b: int, c: int) -> dict:
    """Exact binomial McNemar on discordant pairs (b: 0->1, c: 1->0).

    Two-sided p-value = 2 * P(X <= min(b, c)) under Bin(min(b+c), 1/2),
    computed by direct summation (exact for every n, no approximations).
    """
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "n_discordant": 0, "p_value": 1.0, "statistic": None}
    k = min(b, c)
    p_le = sum(math.comb(n, i) for i in range(0, k + 1)) / 2**n
    p_two = min(1.0, 2.0 * p_le)
    return {
        "b": b,
        "c": c,
        "n_discordant": n,
        "p_value": p_two,
        "statistic": k,
    }


def rank_biserial(x: list[float], y: list[float]) -> float | None:
    """Rank-biserial correlation for paired samples (Kerby simple difference
    of matched-pair ranks). None when any pair is uninformative (missing)."""
    if len(x) != len(y) or not x:
        return None
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if not pairs:
        return None
    ranks: list[float] = []
    for i, (a, b) in enumerate(pairs):
        combined = [a, b]
        # Ranks within the pair: 1 and 2 (ties share the average).
        ordered = sorted(range(2), key=lambda j: combined[j])
        r = [0.0, 0.0]
        if combined[ordered[0]] == combined[ordered[1]]:
            r[ordered[0]] = 1.5
            r[ordered[1]] = 1.5
        else:
            r[ordered[0]] = 1.0
            r[ordered[1]] = 2.0
        ranks.extend(r)
    x_ranks = ranks[0::2]
    y_ranks = ranks[1::2]
    # Kerby simple difference: normalize by the number of pairs, so a
    # sample where x always exceeds y reaches +1.0 (and all-loses -1.0),
    # regardless of n. (Dividing by the rank sum would cap the statistic
    # at 1/3 and shrink it further as n grows.)
    return (sum(x_ranks) - sum(y_ranks)) / len(pairs)


def bootstrap_ci(
    values: list[float],
    statistic=sum,
    n_resamples: int = 2000,
    seed: int = 20260922,
    alpha: float = 0.05,
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for a statistic over resample-with-replacement."""
    if not values:
        return None
    rng = random.Random(seed)
    stats: list[float] = []
    n = len(values)
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        stats.append(float(statistic(sample)))
    stats.sort()
    lo_idx = max(0, int(math.floor(alpha / 2 * n_resamples)))
    hi_idx = min(n_resamples - 1, int(math.ceil((1 - alpha / 2) * n_resamples)) - 1)
    return (stats[lo_idx], stats[hi_idx])


def risk_difference_newcombe(
    x1: int, n1: int, x2: int, n2: int
) -> tuple[float, float, float]:
    """Risk difference with the Newcombe hybrid-score (Wilson) interval.

    Returns (rd, lo, hi). Used by the pre-registered non-inferiority test:
    the margin applies to the LOWER bound of the difference.
    """
    if n1 <= 0 or n2 <= 0:
        raise ValueError("Newcombe: both n must be positive")

    def wilson(x: int, n: int) -> tuple[float, float]:
        z = 1.959963984540054  # two-sided 95%
        p = x / n
        denom = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denom
        half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
        return center - half, center + half

    lo1, hi1 = wilson(x1, n1)
    lo2, hi2 = wilson(x2, n2)
    d = x1 / n1 - x2 / n2
    return d, d - math.sqrt((x1 / n1 - lo1) ** 2 + (hi2 - x2 / n2) ** 2), d + math.sqrt(
        (hi1 - x1 / n1) ** 2 + (x2 / n2 - lo2) ** 2
    )


def non_inferiority(
    treated_pass: int,
    treated_n: int,
    control_pass: int,
    control_n: int,
    margin: float,
) -> dict:
    """Pre-registered one-sided non-inferiority on the risk difference.

    `treated` is the new arm, `control` the reference. Non-inferior when the
    lower bound of the Newcombe interval is above -margin. The margin comes
    from the wave tag — never chosen after seeing the data.
    """
    if not (0 < margin < 1):
        raise ValueError("margin must be in (0, 1)")
    rd, lo, _hi = risk_difference_newcombe(treated_pass, treated_n, control_pass, control_n)
    return {
        "risk_difference": rd,
        "ci_lower": lo,
        "margin": margin,
        "non_inferior": lo > -margin,
        "treated_pass_rate": treated_pass / treated_n,
        "control_pass_rate": control_pass / control_n,
    }


def pass_at_k(outcomes: list[bool], k: int) -> float | None:
    """Empirical pass^k over k repetitions of the same item-config cell."""
    if k <= 0 or len(outcomes) < k:
        return None
    wins = 0
    total = 0
    for i in range(len(outcomes) - k + 1):
        window = outcomes[i : i + k]
        wins += 1 if all(window) else 0
        total += 1
    return wins / total if total else None


def rank_biserial_binary(x: list[bool], y: list[bool]) -> float | None:
    """Convenience: rank-biserial on binary paired outcomes."""
    return rank_biserial([1.0 if v else 0.0 for v in x], [1.0 if v else 0.0 for v in y])
