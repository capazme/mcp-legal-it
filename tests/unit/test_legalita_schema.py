"""Schema round-trip and validation for the LegalITA replica benchmark."""

import pytest

from benchmarks.legalita.schema import (
    Citation,
    Criterion,
    RunRecord,
    Task,
    ValidationError,
    Verdict,
)


def _task() -> Task:
    return Task(
        id="JUR-CIV-001",
        track="jurisprudential",
        domain="civil",
        query="Il committente risponde dei danni causati dall'appaltatore?",
        criteria=[
            Criterion(id="C-001", text="Cita l'art. 2043 c.c.", required=True),
            Criterion(id="C-002", text="Distingue l'ipotesi di nudus minister", required=False),
        ],
        issue_status="settled",
        issue_summary="Responsabilita del committente per fatto dell'appaltatore.",
        seed_citation={"court": "Cass. civ.", "section": "III", "number": 12345, "year": 2025},
        builder_confidence="high",
        curated=False,
    )


def test_task_round_trip_preserves_every_field():
    original = _task()
    restored = Task.from_dict(original.to_dict())
    assert restored == original


def test_required_criteria_filters_bonus():
    assert [c.id for c in _task().required_criteria()] == ["C-001"]
    assert [c.id for c in _task().bonus_criteria()] == ["C-002"]


def test_task_rejects_unknown_domain():
    with pytest.raises(ValidationError, match="domain"):
        Task.from_dict({**_task().to_dict(), "domain": "criminal"})


def test_task_rejects_unknown_issue_status():
    with pytest.raises(ValidationError, match="issue_status"):
        Task.from_dict({**_task().to_dict(), "issue_status": "obiter"})


def test_task_rejects_duplicate_criterion_ids():
    payload = _task().to_dict()
    payload["criteria"][1]["id"] = "C-001"
    with pytest.raises(ValidationError, match="duplicate"):
        Task.from_dict(payload)


def test_mdd_task_needs_no_seed_citation():
    task = Task.from_dict(
        {
            "id": "MDD-001",
            "track": "mdd",
            "domain": "civil",
            "query": "Analizza il contratto allegato.",
            "criteria": [{"id": "C-001", "text": "Rileva l'assenza", "required": True}],
            "issue_status": None,
            "issue_summary": "",
            "seed_citation": None,
            "builder_confidence": "high",
            "curated": True,
        }
    )
    assert task.track == "mdd"
    assert task.seed_citation is None


def test_run_record_round_trip():
    record = RunRecord(
        task_id="JUR-CIV-001",
        arm="mcp",
        model="claude-opus-5",
        answer="risposta",
        tool_calls=["cerca_giurisprudenza"],
        num_turns=3,
        duration_ms=4200,
        usage={"input_tokens": 10},
        error=None,
    )
    assert RunRecord.from_dict(record.to_dict()) == record


def test_run_record_variant_sha_round_trip():
    record = RunRecord(
        task_id="JUR-CIV-001",
        arm="plugin-v3",
        model="claude-opus-5",
        answer="risposta",
        tool_calls=["mcp__legal-it__cite_law"],
        num_turns=3,
        duration_ms=4200,
        usage={"input_tokens": 10},
        error=None,
        variant_sha="bb976f9c5d85a5eacdfe220d2e3208aab4f74dba",
    )
    assert RunRecord.from_dict(record.to_dict()) == record


def test_run_record_without_variant_sha_loads_legacy_artifacts():
    # Pre-variant runs.jsonl lines carry no variant_sha key: they must keep
    # loading (as None), or every historical artifact would become unreadable.
    legacy = {
        "task_id": "T", "arm": "bare", "model": "m", "answer": "a",
        "tool_calls": [], "num_turns": 0, "duration_ms": 1,
        "usage": {}, "error": None,
    }
    record = RunRecord.from_dict(legacy)
    assert record.variant_sha is None


def test_run_record_accepts_variant_arms():
    base = {
        "task_id": "T", "model": "m", "answer": "a", "tool_calls": [],
        "num_turns": 0, "duration_ms": 1, "usage": {}, "error": None,
    }
    for arm in ("plugin-v2", "plugin-v3"):
        record = RunRecord.from_dict({**base, "arm": arm})
        assert record.arm == arm


def test_run_record_rejects_unknown_arm():
    with pytest.raises(ValidationError, match="arm"):
        RunRecord.from_dict({**_run_dict(), "arm": "tools"})


def _run_dict() -> dict:
    return RunRecord(
        task_id="T", arm="bare", model="m", answer="a",
        tool_calls=[], num_turns=1, duration_ms=1, usage={}, error=None,
    ).to_dict()


def test_verdict_round_trip_and_judge_validation():
    verdict = Verdict(
        task_id="JUR-CIV-001", arm="bare", criterion_id="C-001",
        judge="A", verdict=True, reasoning="cita l'articolo",
    )
    assert Verdict.from_dict(verdict.to_dict()) == verdict
    with pytest.raises(ValidationError, match="judge"):
        Verdict.from_dict({**verdict.to_dict(), "judge": "D"})


def test_citation_defaults_are_fail_closed():
    citation = Citation(task_id="T", arm="bare", index=0, raw="la giurisprudenza consolidata")
    assert citation.identifiable is False
    assert citation.resolved is None
    assert citation.covers_issue is None
    assert Citation.from_dict(citation.to_dict()) == citation


@pytest.mark.parametrize(
    ("identifiable", "resolved", "covers_issue", "expected"),
    [
        # The only combination that grounds a citation.
        pytest.param(True, True, True, True, id="all_true"),
        # Each conjunct falsified individually while the other two hold.
        pytest.param(False, True, True, False, id="identifiable_false"),
        pytest.param(True, False, True, False, id="resolved_false"),
        pytest.param(True, True, False, False, id="covers_issue_false"),
        # Unset (not-yet-judged) fields must not count as grounded either.
        pytest.param(True, None, True, False, id="resolved_none"),
        pytest.param(True, True, None, False, id="covers_issue_none"),
    ],
)
def test_counts_as_grounded_mixed_states(identifiable, resolved, covers_issue, expected):
    citation = Citation(
        task_id="T",
        arm="bare",
        index=0,
        raw="raw",
        identifiable=identifiable,
        resolved=resolved,
        covers_issue=covers_issue,
    )
    assert citation.counts_as_grounded() is expected


@pytest.mark.parametrize("truthy_non_true_resolved", ["yes", 1])
def test_counts_as_grounded_rejects_truthy_non_true_resolved(truthy_non_true_resolved):
    # Pins `resolved is True` as an identity check. If this were rewritten as
    # a truthiness check (`if self.resolved`), a truthy-but-not-True value
    # like the string "yes" or the int 1 (`1 is True` is False in Python)
    # would start counting as grounded, silently inflating every grounding
    # metric in the benchmark.
    citation = Citation(
        task_id="T",
        arm="bare",
        index=0,
        raw="raw",
        identifiable=True,
        resolved=truthy_non_true_resolved,
        covers_issue=True,
    )
    assert citation.counts_as_grounded() is False
