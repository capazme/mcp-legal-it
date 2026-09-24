"""Data types for the LegalITA replica benchmark.

Every type round-trips through plain dicts so the gold set and the run
artifacts are readable JSON that a human can review and git can diff.
Validation is strict and fail-closed: an unknown enum value raises rather
than silently degrading a score.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TRACKS = ("jurisprudential", "mdd")
DOMAINS = ("civil", "labour", "tax")
ISSUE_STATUSES = ("settled", "revirement", "active_conflict")
ARMS = ("bare", "web", "mcp", "plugin-v2", "plugin-v3")
# Plugin arms: each loads the FULL product of one pinned server version via
# `--plugin-dir` (MCP server + skills + agents + commands + hooks), so the
# comparison between them measures the whole deliverable — not only the MCP
# surface. The ref each arm pins is resolved at provisioning time
# (benchmarks/legalita/run/variants.py) and recorded per-run in
# RunRecord.variant_sha; the arm NAME is deliberately ref-free so historical
# runs stay comparable when the ref moves forward.
VARIANT_ARMS = ("plugin-v2", "plugin-v3")
JUDGES = ("A", "B", "human")
CONFIDENCES = ("high", "low")


class ValidationError(ValueError):
    """Raised when a payload does not satisfy the benchmark schema."""


def _require(value: Any, allowed: tuple[str, ...], field_name: str) -> Any:
    if value not in allowed:
        raise ValidationError(
            f"{field_name}: expected one of {allowed}, got {value!r}"
        )
    return value


@dataclass(frozen=True)
class Criterion:
    id: str
    text: str
    required: bool

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Criterion:
        missing = {"id", "text", "required"} - set(d)
        if missing:
            raise ValidationError(f"criterion: missing keys {sorted(missing)}")
        return cls(id=str(d["id"]), text=str(d["text"]), required=bool(d["required"]))


@dataclass
class Task:
    id: str
    track: str
    domain: str
    query: str
    criteria: list[Criterion]
    issue_status: str | None
    issue_summary: str
    seed_citation: dict | None
    builder_confidence: str
    curated: bool

    def required_criteria(self) -> list[Criterion]:
        return [c for c in self.criteria if c.required]

    def bonus_criteria(self) -> list[Criterion]:
        return [c for c in self.criteria if not c.required]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "track": self.track,
            "domain": self.domain,
            "query": self.query,
            "criteria": [c.to_dict() for c in self.criteria],
            "issue_status": self.issue_status,
            "issue_summary": self.issue_summary,
            "seed_citation": self.seed_citation,
            "builder_confidence": self.builder_confidence,
            "curated": self.curated,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Task:
        track = _require(d.get("track"), TRACKS, "track")
        domain = _require(d.get("domain"), DOMAINS, "domain")
        confidence = _require(
            d.get("builder_confidence"), CONFIDENCES, "builder_confidence"
        )

        issue_status = d.get("issue_status")
        if track == "jurisprudential":
            _require(issue_status, ISSUE_STATUSES, "issue_status")
        elif issue_status is not None:
            raise ValidationError("issue_status: must be null on mdd tasks")

        criteria = [Criterion.from_dict(c) for c in d.get("criteria", [])]
        if not criteria:
            raise ValidationError(f"{d.get('id')}: at least one criterion required")
        ids = [c.id for c in criteria]
        if len(set(ids)) != len(ids):
            raise ValidationError(f"{d.get('id')}: duplicate criterion ids in {ids}")
        if not any(c.required for c in criteria):
            raise ValidationError(f"{d.get('id')}: at least one required criterion")

        return cls(
            id=str(d["id"]),
            track=track,
            domain=domain,
            query=str(d["query"]),
            criteria=criteria,
            issue_status=issue_status,
            issue_summary=str(d.get("issue_summary", "")),
            seed_citation=d.get("seed_citation"),
            builder_confidence=confidence,
            curated=bool(d.get("curated", False)),
        )


@dataclass
class RunRecord:
    task_id: str
    arm: str
    model: str
    answer: str
    tool_calls: list[str]
    num_turns: int
    duration_ms: int
    usage: dict
    error: str | None
    # For plugin arms: the exact commit SHA the variant worktree was pinned
    # to when THIS run executed (None for bare/web/mcp). Written on every
    # record rather than in a side manifest alone, so a results file is
    # self-describing even when the worktrees have moved on since.
    variant_sha: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> RunRecord:
        _require(d.get("arm"), ARMS, "arm")
        return cls(
            task_id=str(d["task_id"]),
            arm=d["arm"],
            model=str(d["model"]),
            answer=str(d["answer"]),
            tool_calls=list(d.get("tool_calls", [])),
            num_turns=int(d.get("num_turns", 0)),
            duration_ms=int(d.get("duration_ms", 0)),
            usage=dict(d.get("usage", {})),
            error=d.get("error"),
            # Pre-variant artifacts lack the key; .get (not d[...]) keeps
            # every historical runs.jsonl line loadable.
            variant_sha=d.get("variant_sha"),
        )


@dataclass
class Verdict:
    task_id: str
    arm: str
    criterion_id: str
    judge: str
    verdict: bool
    reasoning: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Verdict:
        _require(d.get("arm"), ARMS, "arm")
        _require(d.get("judge"), JUDGES, "judge")
        return cls(
            task_id=str(d["task_id"]),
            arm=d["arm"],
            criterion_id=str(d["criterion_id"]),
            judge=d["judge"],
            verdict=bool(d["verdict"]),
            reasoning=str(d.get("reasoning", "")),
        )


@dataclass
class Citation:
    """One citation produced by one arm on one task.

    `identifiable` is False for narrative references that carry no court,
    number or year. Those still count in the GOG denominator, which is the
    whole point: a system that gestures at case law without identifying it
    has not grounded anything.
    """

    task_id: str
    arm: str
    index: int
    raw: str
    parsed: dict | None = None
    identifiable: bool = False
    resolved: bool | None = None
    resolution_note: str = ""
    covers_issue: bool | None = None

    def counts_as_grounded(self) -> bool:
        return self.identifiable and self.resolved is True and self.covers_issue is True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Citation:
        _require(d.get("arm"), ARMS, "arm")
        return cls(
            task_id=str(d["task_id"]),
            arm=d["arm"],
            index=int(d["index"]),
            raw=str(d["raw"]),
            parsed=d.get("parsed"),
            identifiable=bool(d.get("identifiable", False)),
            resolved=d.get("resolved"),
            resolution_note=str(d.get("resolution_note", "")),
            covers_issue=d.get("covers_issue"),
        )


def load_tasks(path: Path) -> list[Task]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Task.from_dict(item) for item in payload]


def save_tasks(tasks: list[Task], path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps([t.to_dict() for t in tasks], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
