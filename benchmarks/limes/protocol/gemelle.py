"""S-layer mechanical scoring and twin discrimination (DESIGN §4.2).

The metric for a `coppia gemella` is not "ha ragione?" but
**discriminazione**: do the two answers diverge in the direction the law
requires? Each family member declares what correct looks like *for its
variant* (orientation and/or citation markers, plus forbidden moves), and
the family passes only when both members match their own expectation —
structure, not points; largely immune to length and style bias.

A member's mechanical verdict:
    pass = expected orientation matches (if declared)
           AND all expected citation markers present (if declared)
           AND no disqualifier fired.
A disqualifier hit also flags `violation: True` — the A dimension floors the
whole cell to zero on any disqualifying violation (DESIGN §5: "analogia
(con violazioni disqualificanti)").
"""

from __future__ import annotations

from typing import Iterable

from benchmarks.limes.bank.schema.item import Bank, Item
from benchmarks.limes.protocol.citations import has_marker
from benchmarks.limes.protocol.hedge import orientation_matches


def score_s(item: Item, answer: str) -> dict:
    """Score one S item mechanically. Raises on non-S items or on S items
    with no mechanical expectation (those are judge-only and simply have no
    mechanical verdict)."""
    if item.layer != "S":
        raise ValueError(f"score_s: {item.id} is not an S item")
    if not item.has_mechanical_expectation():
        raise ValueError(f"score_s: {item.id} has no mechanical expectation")

    violations = [m for m in item.disqualifiers if has_marker(answer, m)]
    markers_missing = [m for m in item.expected_markers if not has_marker(answer, m)]
    orientation_ok: bool | None = None
    if item.correct_orientation is not None:
        orientation_ok = orientation_matches(answer, item.correct_orientation)

    passed = (
        not violations
        and not markers_missing
        and orientation_ok is not False
    )
    return {
        "item_id": item.id,
        "construct": item.construct,
        "family": item.family,
        "orientation_ok": orientation_ok,
        "markers_missing": markers_missing,
        "violations": violations,
        "violation": bool(violations),
        "passed": passed,
    }


def score_twin_family(a: Item, b: Item, answer_a: str, answer_b: str) -> dict:
    """Discrimination verdict for one twin family.

    The family diverges correctly when BOTH members match their own
    expectations. A pair whose members pass identical expectations (e.g.
    both `affermare`) adds nothing to discrimination — that is by design:
    those twins verify direction-specific reasoning via their markers.
    """
    if not (a.is_twin() and b.is_twin() and a.family == b.family):
        raise ValueError("score_twin_family: items are not a twin family")
    return {
        "family": a.family,
        "construct": a.construct,
        "member_a": score_s(a, answer_a),
        "member_b": score_s(b, answer_b),
        "discriminated": score_s(a, answer_a)["passed"]
        and score_s(b, answer_b)["passed"],
    }


def discrimination_rate(bank: Bank, answers: dict[str, str]) -> dict:
    """Aggregate discrimination over all complete twin families with answers.

    Families with any missing answer are skipped from the rate and counted
    in `incomplete` (never silently dropped from the report).
    """
    rates: list[int] = []
    report: list[dict] = []
    for family, (a, b) in sorted(bank.twin_families().items()):
        if a.id not in answers or b.id not in answers:
            report.append({"family": family, "construct": a.construct, "state": "incomplete"})
            continue
        verdict = score_twin_family(a, b, answers[a.id], answers[b.id])
        rates.append(1 if verdict["discriminated"] else 0)
        report.append(
            {
                "family": family,
                "construct": a.construct,
                "state": "scored",
                "discriminated": verdict["discriminated"],
            }
        )
    scored = [r for r in report if r["state"] == "scored"]
    return {
        "rate": (sum(rates) / len(rates)) if rates else None,
        "families_scored": len(scored),
        "families_incomplete": len(report) - len(scored),
        "families": report,
    }


def iter_mechanical_s(bank: Bank, answers: dict[str, str]) -> Iterable[dict]:
    """Yield mechanical S verdicts for every S item that has expectations
    and an answer; judge-only items are skipped (M stays n/d without judges,
    DESIGN §6)."""
    for item in bank.items:
        if item.layer != "S" or not item.has_mechanical_expectation():
            continue
        if item.id not in answers:
            continue
        yield score_s(item, answers[item.id])
