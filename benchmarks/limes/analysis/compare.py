"""Cross comparison (DESIGN §5, trasversale): two configs or two models on
the same items, paired. McNemar on binary outcomes, rank-biserial effect
size, bootstrap CI on the pass-rate difference. Ereditato concettualmente
da LegalITA.
"""

from __future__ import annotations

from statistics import mean

from dataclasses import dataclass

from benchmarks.limes.analysis.stats import (
    bootstrap_ci,
    mcnemar_exact,
    rank_biserial_binary,
)


@dataclass(frozen=True)
class Comparison:
    a: str
    b: str
    n_paired: int
    n_missing: int
    a_pass: int
    b_pass: int
    mcnemar: dict
    effect: float | None
    diff_ci: tuple[float, float] | None

    def render(self) -> str:
        lines = [
            f"confronto paired: {self.a} vs {self.b}",
            f"  coppie={self.n_paired}  mancanti={self.n_missing}  "
            f"pass {self.a_pass}/{self.n_paired} vs {self.b_pass}/{self.n_paired}",
        ]
        if self.n_paired:
            lines.append(
                f"  McNemar p={self.mcnemar['p_value']:.4f} "
                f"(discordanti b={self.mcnemar['b']}, c={self.mcnemar['c']})"
            )
        if self.effect is not None:
            lines.append(f"  rank-biserial={self.effect:+.3f}")
        if self.diff_ci is not None:
            lines.append(
                f"  delta={self.b_pass / self.n_paired - self.a_pass / self.n_paired:+.3f} "
                f"CI95=[{self.diff_ci[0]:+.3f}, {self.diff_ci[1]:+.3f}]"
            )
        return "\n".join(lines)


# The binary outcome of a verdict map entry: `passed` (S layer and
# runner-written Q verdicts) or, in its absence, `matched` (Q layer scored
# directly). A verdict with neither key never pretends to be a fail — it
# is an unscorable pair, reported as missing.
_PASS_KEYS = ("passed", "matched")


def _outcome(verdict: dict) -> bool | None:
    for key in _PASS_KEYS:
        if key in verdict:
            return bool(verdict[key])
    return None


def paired_outcomes(
    a: dict[str, dict], b: dict[str, dict]
) -> tuple[list[bool], list[bool], int]:
    """Extract paired binary outcomes from two verdict maps keyed by item.

    Only items present in BOTH maps and scorable on both sides are paired;
    everything else is counted and reported as missing (never silently
    dropped from the report, though it does not enter the paired test).
    """
    common = sorted(set(a) & set(b))
    pairs = [(i, _outcome(a[i]), _outcome(b[i])) for i in common]
    xa = [x for _, x, y in pairs if x is not None and y is not None]
    xb = [y for _, x, y in pairs if x is not None and y is not None]
    return xa, xb, len(xa)


def compare_cells(
    label_a: str,
    label_b: str,
    verdicts_a: dict[str, dict],
    verdicts_b: dict[str, dict],
    seed: int = 20260922,
) -> Comparison:
    """Full paired comparison between two cells of the matrix."""
    xa, xb, n = paired_outcomes(verdicts_a, verdicts_b)
    n_missing = max(len(verdicts_a), len(verdicts_b)) - n
    b_only = sum(1 for x, y in zip(xa, xb) if y and not x)
    a_only = sum(1 for x, y in zip(xa, xb) if x and not y)
    mcn = mcnemar_exact(a_only, b_only)
    effect = rank_biserial_binary(xa, xb) if xa else None
    diff_ci = None
    if n:
        values = [1.0 * y - 1.0 * x for x, y in zip(xa, xb)]
        # CI on the same scale as delta: mean per-item difference (rates),
        # not the sum (counts) — printing [-26, -18] next to delta=-0.815
        # would be an apples-to-oranges CI.
        diff_ci = bootstrap_ci(values, statistic=mean, seed=seed, n_resamples=2000)
    return Comparison(
        a=label_a,
        b=label_b,
        n_paired=n,
        n_missing=n_missing,
        a_pass=sum(xa),
        b_pass=sum(xb),
        mcnemar=mcn,
        effect=effect,
        diff_ci=diff_ci,
    )
