"""Protocol rules: the pre-registered knobs every score reads.

Loaded from `protocol/protocol.yaml` (part of `protocol_sha`). Fail-closed:
missing keys, wrong types or unknown exclusion ids raise at load time — a
protocol that only half-loads would produce numbers whose provenance cannot
be stated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - dev dependency guard
    raise ModuleNotFoundError(
        "pyyaml is required to load the LIMES protocol "
        "(install the project dev extras: uv sync --extra dev)"
    ) from exc

KNOWN_EXCLUSIONS = ("errore_init_tool_shape", "hook_stop", "risposta_vuota")


class ProtocolError(ValueError):
    """Raised when protocol/protocol.yaml does not satisfy the rules schema."""


@dataclass(frozen=True)
class Conventions:
    day_count: str
    term_computation: str
    rounding: str
    date_format: str


@dataclass(frozen=True)
class JudgeConfig:
    models: list[str] = field(default_factory=list)
    family_blind: bool = True
    tiebreak: str = "human"
    replicas: int = 2
    # Human gold set + thresholds gating inferential use (B2 iv).
    gold: str | None = None
    calibration: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Protocol:
    version: int
    seed: int
    conventions: Conventions
    tolerance_defaults: dict  # {"absolute": float} and/or {"relative": float}
    retry_budget: int
    timeout_s: int
    exclusions: list[str]
    judge: JudgeConfig
    # Contamination probe threshold (B4): max original-vs-paraphrase gap.
    contamination_max_gap: float | None = None

    def default_tolerance(self) -> dict:
        return dict(self.tolerance_defaults)

    @property
    def judge_enabled(self) -> bool:
        return bool(self.judge.models)


def _need(mapping: dict, key: str, where: str) -> Any:
    if key not in mapping:
        raise ProtocolError(f"protocol: {where} missing {key!r}")
    return mapping[key]


def load_protocol(path: Path) -> Protocol:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ProtocolError(f"{path}: expected a mapping")

    version = _need(raw, "protocol_version", "root")
    seed = _need(raw, "seed", "root")
    if not isinstance(version, int) or not isinstance(seed, int):
        raise ProtocolError("protocol: protocol_version and seed must be integers")

    conv_raw = _need(raw, "conventions", "root")
    conventions = Conventions(
        day_count=str(_need(conv_raw, "day_count", "conventions")),
        term_computation=str(_need(conv_raw, "term_computation", "conventions")),
        rounding=str(_need(conv_raw, "rounding", "conventions")),
        date_format=str(_need(conv_raw, "date_format", "conventions")),
    )

    tolerance_defaults = _need(raw, "tolerance_defaults", "root")
    if not isinstance(tolerance_defaults, dict) or not (
        {"absolute", "relative"} & set(tolerance_defaults)
    ):
        raise ProtocolError(
            "protocol: tolerance_defaults needs 'absolute' and/or 'relative'"
        )

    retry_budget = _need(raw, "retry_budget", "root")
    timeout_s = _need(raw, "timeout_s", "root")
    if not isinstance(retry_budget, int) or retry_budget < 0:
        raise ProtocolError("protocol: retry_budget must be a non-negative integer")
    if not isinstance(timeout_s, int) or timeout_s <= 0:
        raise ProtocolError("protocol: timeout_s must be a positive integer")

    exclusions = _need(raw, "exclusions", "root")
    if not isinstance(exclusions, list) or not all(isinstance(e, str) for e in exclusions):
        raise ProtocolError("protocol: exclusions must be a list of strings")
    unknown = sorted(set(exclusions) - set(KNOWN_EXCLUSIONS))
    if unknown:
        raise ProtocolError(
            f"protocol: unknown exclusion ids {unknown} (known: {list(KNOWN_EXCLUSIONS)})"
        )

    judge_raw = _need(raw, "judge", "root")
    calibration_raw = judge_raw.get("calibration") or {}
    models = [str(m) for m in judge_raw.get("models", [])]
    if models:
        missing = [k for k in ("min_gold", "min_kappa", "max_eo_gap") if k not in calibration_raw]
        if missing:
            raise ProtocolError(
                f"protocol: judges declared without calibration thresholds {missing} "
                f"(no judge verdict is inferential without them)"
            )
    replicas = judge_raw.get("replicas", 2)
    if not isinstance(replicas, int) or replicas < 1:
        raise ProtocolError("protocol: judge.replicas must be a positive integer")
    judge = JudgeConfig(
        models=models,
        family_blind=bool(judge_raw.get("family_blind", True)),
        tiebreak=str(judge_raw.get("tiebreak", "human")),
        replicas=replicas,
        gold=str(judge_raw["gold"]) if judge_raw.get("gold") else None,
        calibration=dict(calibration_raw),
    )
    contamination = raw.get("contamination") or {}
    max_gap = contamination.get("max_gap")
    if max_gap is not None and not (0 < float(max_gap) < 1):
        raise ProtocolError("protocol: contamination.max_gap must be in (0, 1)")

    return Protocol(
        version=version,
        seed=seed,
        conventions=conventions,
        tolerance_defaults=tolerance_defaults,
        retry_budget=retry_budget,
        timeout_s=timeout_s,
        exclusions=list(exclusions),
        judge=judge,
        contamination_max_gap=float(max_gap) if max_gap is not None else None,
    )
