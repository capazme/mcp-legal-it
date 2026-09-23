"""Equating (DESIGN §4.3, §5): anchors make different bank_sha comparable.

The score of wave N+1 is expressed on wave N's scale through the shared
anchors: the anchoring delta is the anchors' pass-rate difference between
waves, and a private score is reported both raw and equated. Anchors never
grow a posteriori; if the anchor pass rate moves beyond the drift guard,
the cross-wave comparison is flagged instead of silently normalized.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaveScores:
    wave: str
    anchor_passes: int
    anchor_total: int
    private_passes: int
    private_total: int


def anchor_delta(current: WaveScores, previous: WaveScores) -> float | None:
    """Anchoring delta on the shared anchor stratum (0.0 = same difficulty)."""
    if current.anchor_total == 0 or previous.anchor_total == 0:
        return None
    return (current.anchor_passes / current.anchor_total) - (
        previous.anchor_passes / previous.anchor_total
    )


def equated_private(current: WaveScores, previous: WaveScores) -> float | None:
    """Private pass rate adjusted by the anchor delta (linear equating)."""
    if current.private_total == 0:
        return None
    delta = anchor_delta(current, previous)
    if delta is None:
        return None
    return current.private_passes / current.private_total - delta


def drift_guard(current: WaveScores, previous: WaveScores, max_drift: float = 0.2) -> dict:
    """Flag anchor drift: beyond the guard, the equating is not applied —
    the waves measure something different and must be compared by hand."""
    delta = anchor_delta(current, previous)
    if delta is None:
        return {"applicable": False, "reason": "no anchors"}
    drift = abs(delta)
    return {
        "applicable": drift <= max_drift,
        "anchor_delta": delta,
        "max_drift": max_drift,
        "reason": None if drift <= max_drift else "anchor drift beyond guard",
    }
