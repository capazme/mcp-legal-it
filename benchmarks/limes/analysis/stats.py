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


_Z975 = 1.959963984540054  # two-sided 95% / one-sided 97.5%


def _wilson(x: int, n: int, z: float = _Z975) -> tuple[float, float]:
    p = x / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def paired_risk_difference_newcombe(
    both: int, treated_only: int, control_only: int, neither: int
) -> tuple[float, float, float]:
    """Paired risk difference with Newcombe's hybrid-score interval for
    PAIRED proportions (Newcombe 1998, Stat Med 17:2635, method 10).

    The two arms of a LIMES comparison answer the SAME items, so the
    independent-samples interval (`risk_difference_newcombe`) ignores the
    within-item correlation and is too wide or too narrow depending on it.
    Cells: `both` pass in both arms, `treated_only`/`control_only` the
    discordant pairs, `neither` fail in both. Returns (rd, lo, hi) with
    rd = p_treated - p_control.
    """
    n = both + treated_only + control_only + neither
    if n <= 0:
        raise ValueError("paired Newcombe: no pairs")
    p1 = (both + treated_only) / n
    p2 = (both + control_only) / n
    l1, u1 = _wilson(both + treated_only, n)
    l2, u2 = _wilson(both + control_only, n)
    # Correlation between the two binary outcomes (phi), set to 0 when a
    # margin is empty (Newcombe's convention).
    product = (
        (both + treated_only) * (control_only + neither)
        * (both + control_only) * (treated_only + neither)
    )
    phi = 0.0
    if product > 0:
        phi = (both * neither - treated_only * control_only) / math.sqrt(product)
    d = p1 - p2
    lo = d - math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    hi = d + math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return d, max(-1.0, lo), min(1.0, hi)


def paired_non_inferiority(
    treated: list[bool], control: list[bool], margin: float
) -> dict:
    """Pre-registered non-inferiority on paired binary outcomes: non-inferior
    when the lower bound of the paired Newcombe 95% interval (one-sided
    alpha 0.025) lies above -margin. The margin comes from the wave file."""
    if not (0 < margin < 1):
        raise ValueError("margin must be in (0, 1)")
    if len(treated) != len(control) or not treated:
        raise ValueError("paired non-inferiority needs equal, non-empty paired lists")
    both = sum(1 for t, c in zip(treated, control) if t and c)
    t_only = sum(1 for t, c in zip(treated, control) if t and not c)
    c_only = sum(1 for t, c in zip(treated, control) if c and not t)
    neither = len(treated) - both - t_only - c_only
    rd, lo, hi = paired_risk_difference_newcombe(both, t_only, c_only, neither)
    return {
        "n_pairs": len(treated),
        "discordant": t_only + c_only,
        "risk_difference": rd,
        "ci_lower": lo,
        "ci_upper": hi,
        "margin": margin,
        "non_inferior": lo > -margin,
    }


def holm(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Holm step-down correction over a pre-registered family of tests.

    Returns, per test, the Holm-adjusted p-value and whether it is rejected
    at the family-wise level `alpha`. The family is declared in the wave
    file BEFORE the data (never assembled from whatever came out
    significant)."""
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(ordered)
    out: dict[str, dict] = {}
    running = 0.0
    still_rejecting = True
    for rank, (name, p) in enumerate(ordered):
        adjusted = min(1.0, max(running, (m - rank) * p))
        running = adjusted
        still_rejecting = still_rejecting and p <= alpha / (m - rank)
        out[name] = {"p": p, "p_holm": adjusted, "rejected": still_rejecting}
    return out


def _z(q: float) -> float:
    """Standard normal quantile (Acklam's rational approximation; |err| <
    1.2e-9 — ample for a sample-size formula, and no scipy dependency)."""
    if not 0 < q < 1:
        raise ValueError("quantile must be in (0, 1)")
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    lo, hi = 0.02425, 1 - 0.02425
    if q < lo:
        r = math.sqrt(-2 * math.log(q))
        return (((((c[0] * r + c[1]) * r + c[2]) * r + c[3]) * r + c[4]) * r + c[5]) / (
            (((d[0] * r + d[1]) * r + d[2]) * r + d[3]) * r + 1)
    if q > hi:
        return -_z(1 - q)
    r = q - 0.5
    s = r * r
    return (((((a[0] * s + a[1]) * s + a[2]) * s + a[3]) * s + a[4]) * s + a[5]) * r / (
        ((((b[0] * s + b[1]) * s + b[2]) * s + b[3]) * s + b[4]) * s + 1)


def ni_required_pairs(
    margin: float, discordance: float, alpha: float = 0.025, power: float = 0.80,
    true_difference: float = 0.0,
) -> int:
    """A priori sample size for paired non-inferiority on a risk difference.

    Normal approximation on the paired difference (Nam 1997; the variance
    of the per-item difference is discordance - true_difference^2): the
    number of items needed so that, when the true difference is
    `true_difference`, the one-sided test at `alpha` rejects inferiority by
    `margin` with probability `power`. `discordance` is the pre-registered
    expected share of discordant items (p10 + p01).
    """
    if not (0 < margin < 1) or not (0 < discordance <= 1):
        raise ValueError("margin and discordance must be in (0, 1]")
    variance = discordance - true_difference ** 2
    effect = true_difference + margin
    if effect <= 0 or variance <= 0:
        raise ValueError("no finite sample size for these parameters")
    n = (_z(1 - alpha) + _z(power)) ** 2 * variance / effect ** 2
    return math.ceil(n)


def mcnemar_exact_power(discordant: int, split: float, alpha: float = 0.05) -> float:
    """Power of the exact two-sided McNemar test conditional on `discordant`
    pairs, when a share `split` of them favours one arm (e.g. 0.75)."""
    m = discordant
    null = [math.comb(m, k) / 2 ** m for k in range(m + 1)]
    cumulative_low = [sum(null[: k + 1]) for k in range(m + 1)]
    rejection = [
        k for k in range(m + 1)
        if 2 * min(cumulative_low[k], 1 - (cumulative_low[k - 1] if k else 0.0)) <= alpha
    ]
    return sum(math.comb(m, k) * split ** k * (1 - split) ** (m - k) for k in rejection)
