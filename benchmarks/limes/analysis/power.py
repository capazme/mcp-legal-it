"""A priori power (B1): a wave declares, BEFORE any run, the power its
primary endpoint needs, and `plan`/`run` refuse a wave whose bank cannot
deliver it.

The primary endpoint is the pooled paired pass/fail over every scored item
of a matrix cell (what `compare` tests). Two conditions, both pre-registered
in the wave file under `analysis.power`:

1. **non-inferiority size** — the items needed for the paired NI test at
   the declared margin, one-sided alpha, power and expected discordance
   (`stats.ni_required_pairs`);
2. **discordant floor** — the expected number of discordant items
   (n x discordance) must reach `min_discordant`: the exact McNemar test is
   conditional on the discordant pairs, and below ~30 of them it cannot
   reach 0.80 power even at a 75/25 split (`stats.mcnemar_exact_power`).
"""

from __future__ import annotations

from benchmarks.limes.analysis.stats import mcnemar_exact_power, ni_required_pairs

REQUIRED_KEYS = ("margin", "alpha_one_sided", "power", "expected_discordance", "min_discordant")


class PowerError(ValueError):
    """Raised when a wave's power declaration is missing or not satisfied."""


def power_check(spec: dict | None, n_items: int) -> dict:
    """Evaluate the declared power against the bank size. Never raises for
    an unsatisfied check (the report says so); raises on a malformed spec."""
    if not spec:
        return {"declared": False, "satisfied": None}
    missing = [k for k in REQUIRED_KEYS if k not in spec]
    if missing:
        raise PowerError(f"analysis.power: missing {missing}")
    margin = float(spec["margin"])
    alpha = float(spec["alpha_one_sided"])
    power = float(spec["power"])
    discordance = float(spec["expected_discordance"])
    min_discordant = int(spec["min_discordant"])
    split = float(spec.get("mcnemar_split", 0.75))
    required = ni_required_pairs(margin, discordance, alpha=alpha, power=power)
    expected_discordant = n_items * discordance
    mcnemar_power = mcnemar_exact_power(int(expected_discordant), split, alpha=2 * alpha)
    satisfied = n_items >= required and expected_discordant >= min_discordant
    return {
        "declared": True,
        "n_items": n_items,
        "required_items": required,
        "expected_discordant": round(expected_discordant, 1),
        "min_discordant": min_discordant,
        "mcnemar_power_at_split": round(mcnemar_power, 3),
        "mcnemar_split": split,
        "satisfied": satisfied,
    }


def enforce(spec: dict | None, n_items: int) -> dict:
    """`power_check`, fail-closed: a declared-but-unsatisfied power aborts."""
    report = power_check(spec, n_items)
    if report["declared"] and not report["satisfied"]:
        raise PowerError(
            f"potenza insufficiente: bank di {n_items} item, richiesti "
            f"{report['required_items']} per la non-inferiorità e "
            f"{report['min_discordant']} discordanti attesi "
            f"(attesi {report['expected_discordant']}) — estendere la bank, "
            f"non abbassare le soglie dopo averla vista"
        )
    return report
