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
    holm,
    mcnemar_exact,
    paired_non_inferiority,
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


def _paired_lists(a: dict[str, dict], b: dict[str, dict], items: set[str] | None = None):
    common = sorted(set(a) & set(b) & (items if items is not None else set(a)))
    xa, xb = [], []
    for item_id in common:
        oa, ob = _outcome(a[item_id]), _outcome(b[item_id])
        if oa is None or ob is None:
            continue
        xa.append(oa)
        xb.append(ob)
    return xa, xb


def wave_analysis(
    cells: dict[tuple[str, str], dict[str, dict]],
    spec: dict,
    scored_items: set[str] | None = None,
) -> dict:
    """The pre-registered analysis of a wave (B5), per model.

    `cells` maps (model, config) -> verdict map. `spec` is the wave file's
    `analysis` block:

    - `primary.baseline` + `primary.treatments`: the confirmatory family
      (each treatment vs baseline, exact McNemar), Holm-corrected WITHIN
      each model at `alpha`;
    - `non_inferiority`: treated vs control, paired Newcombe lower bound
      against the margin (one pre-specified test per model, outside the
      Holm family: it answers a different question).

    `scored_items` restricts the endpoint (e.g. excludes canaries and
    paraphrases, which are contamination probes, not measurement items).
    """
    alpha = float(spec.get("alpha", 0.05))
    primary = spec.get("primary") or {}
    ni = spec.get("non_inferiority") or {}
    models = sorted({m for m, _ in cells})
    report: dict = {"alpha": alpha, "models": {}}
    for model in models:
        out: dict = {"primary": {}, "non_inferiority": None}
        baseline = primary.get("baseline")
        p_values: dict[str, float] = {}
        if baseline and (model, baseline) in cells:
            for treatment in primary.get("treatments", []):
                if (model, treatment) not in cells:
                    out["primary"][treatment] = {"state": "missing cell"}
                    continue
                xa, xb = _paired_lists(cells[(model, baseline)], cells[(model, treatment)], scored_items)
                b_only = sum(1 for x, y in zip(xa, xb) if y and not x)
                a_only = sum(1 for x, y in zip(xa, xb) if x and not y)
                test = mcnemar_exact(a_only, b_only)
                out["primary"][treatment] = {
                    "n_pairs": len(xa),
                    "baseline_rate": sum(xa) / len(xa) if xa else None,
                    "treatment_rate": sum(xb) / len(xb) if xb else None,
                    "treatment_only": b_only,
                    "baseline_only": a_only,
                    "p": test["p_value"],
                }
                p_values[treatment] = test["p_value"]
            for name, adj in holm(p_values, alpha).items():
                out["primary"][name].update({"p_holm": adj["p_holm"], "rejected": adj["rejected"]})
        treated, control = ni.get("treated"), ni.get("control")
        if treated and control and (model, treated) in cells and (model, control) in cells:
            x_control, x_treated = _paired_lists(
                cells[(model, control)], cells[(model, treated)], scored_items
            )
            if x_treated:
                out["non_inferiority"] = {
                    "treated": treated,
                    "control": control,
                    **paired_non_inferiority(x_treated, x_control, float(ni["margin"])),
                }
        report["models"][model] = out
    return report


def contamination_report(
    verdicts: dict[str, dict], pairs: list[tuple[str, str]], max_gap: float
) -> dict:
    """Paraphrase/canary probe (B4; Chen et al. 2025): pass rate on the
    originals vs on their private restatements. A model that solves the
    public wording but not the same question reworded shows memorization,
    not method: a gap above the pre-registered `max_gap` is flagged."""
    scored = [
        (_outcome(verdicts[o]), _outcome(verdicts[p]))
        for o, p in pairs
        if o in verdicts and p in verdicts
    ]
    scored = [(o, p) for o, p in scored if o is not None and p is not None]
    if not scored:
        return {"pairs": 0, "flag": None}
    original = sum(1 for o, _ in scored if o) / len(scored)
    paraphrase = sum(1 for _, p in scored if p) / len(scored)
    gap = original - paraphrase
    return {
        "pairs": len(scored),
        "original_rate": original,
        "paraphrase_rate": paraphrase,
        "gap": gap,
        "max_gap": max_gap,
        "flag": gap > max_gap,
    }
