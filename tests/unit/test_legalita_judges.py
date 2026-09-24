"""Judge panel: prompt construction, verdict parsing, reconciliation."""

import json

import pytest

from benchmarks.legalita.schema import Citation, Criterion, RunRecord, Task, Verdict
from benchmarks.legalita.score.judges import (
    JudgeError,
    audit_sample,
    build_grounding_prompt,
    build_judge_prompt,
    parse_grounding_output,
    parse_judge_output,
    reconcile,
)


def _task() -> Task:
    return Task(
        id="T1", track="jurisprudential", domain="civil", query="Quesito?",
        criteria=[
            Criterion(id="C-001", text="Cita l'art. 2043", required=True),
            Criterion(id="C-002", text="Distingue il nudus minister", required=True),
        ],
        issue_status="settled", issue_summary="Questione.",
        seed_citation=None, builder_confidence="high", curated=True,
    )


def _record(arm: str = "mcp") -> RunRecord:
    return RunRecord(
        task_id="T1", arm=arm, model="claude-opus-5", answer="La risposta del modello.",
        tool_calls=[], num_turns=1, duration_ms=1, usage={}, error=None,
    )


def _v(criterion_id, judge, verdict):
    return Verdict(
        task_id="T1", arm="mcp", criterion_id=criterion_id,
        judge=judge, verdict=verdict, reasoning="",
    )


def test_prompt_never_reveals_which_arm_produced_the_answer():
    for arm in ("bare", "web", "mcp"):
        prompt = build_judge_prompt(_task(), _record(arm), _task().criteria)
        assert arm not in prompt.lower().split()
        assert "mcp" not in prompt.lower()
        assert "websearch" not in prompt.lower()


def test_prompt_contains_query_answer_and_every_criterion():
    prompt = build_judge_prompt(_task(), _record(), _task().criteria)
    assert "Quesito?" in prompt
    assert "La risposta del modello." in prompt
    assert "C-001" in prompt and "C-002" in prompt


def test_prompt_demands_a_separate_justification_per_criterion():
    prompt = build_judge_prompt(_task(), _record(), _task().criteria)
    assert "motivazione" in prompt.lower()


def test_parses_grouped_verdicts():
    payload = json.dumps(
        {"verdicts": [
            {"criterion_id": "C-001", "verdict": True, "reasoning": "cita"},
            {"criterion_id": "C-002", "verdict": False, "reasoning": "non distingue"},
        ]}
    )
    verdicts = parse_judge_output(payload, "T1", "mcp", "A", ["C-001", "C-002"])
    assert [v.criterion_id for v in verdicts] == ["C-001", "C-002"]
    assert [v.verdict for v in verdicts] == [True, False]
    assert all(v.judge == "A" for v in verdicts)


def test_parsing_rejects_a_missing_criterion():
    payload = json.dumps({"verdicts": [{"criterion_id": "C-001", "verdict": True}]})
    with pytest.raises(JudgeError, match="C-002"):
        parse_judge_output(payload, "T1", "mcp", "A", ["C-001", "C-002"])


def test_parsing_rejects_an_unexpected_criterion():
    payload = json.dumps(
        {"verdicts": [
            {"criterion_id": "C-001", "verdict": True},
            {"criterion_id": "C-999", "verdict": True},
        ]}
    )
    with pytest.raises(JudgeError, match="C-999"):
        parse_judge_output(payload, "T1", "mcp", "A", ["C-001"])


def test_parsing_rejects_non_json():
    with pytest.raises(JudgeError, match="JSON"):
        parse_judge_output("boh", "T1", "mcp", "A", ["C-001"])


def test_reconcile_keeps_agreements_and_queues_disagreements():
    a = [_v("C-001", "A", True), _v("C-002", "A", True)]
    b = [_v("C-001", "B", True), _v("C-002", "B", False)]
    agreed, disagreements = reconcile(a, b)
    assert agreed == {("T1", "mcp", "C-001"): True}
    assert [d["criterion_id"] for d in disagreements] == ["C-002"]


def test_reconcile_never_invents_a_third_verdict():
    a = [_v("C-001", "A", True)]
    b = [_v("C-001", "B", False)]
    agreed, disagreements = reconcile(a, b)
    assert agreed == {}
    assert len(disagreements) == 1
    assert "verdict" not in disagreements[0]


def test_reconcile_rejects_unpaired_verdicts():
    with pytest.raises(JudgeError, match="unpaired"):
        reconcile([_v("C-001", "A", True)], [])


def test_audit_sample_takes_all_disagreements_when_under_the_cap():
    disagreements = [{"criterion_id": f"C-{i:03d}"} for i in range(10)]
    sample = audit_sample(agreed=[], disagreements=disagreements, seed=20250107)
    assert len(sample) == 10


def test_audit_sample_caps_disagreements_at_forty():
    disagreements = [{"criterion_id": f"C-{i:03d}"} for i in range(70)]
    agreed = [{"criterion_id": f"A-{i:03d}"} for i in range(200)]
    sample = audit_sample(agreed=agreed, disagreements=disagreements, seed=20250107)
    kinds = [item["stratum"] for item in sample]
    assert kinds.count("disagreement") == 40
    # Amendment A4: agreement budget default raised 20 -> 30 (deliberate
    # spec change). These 200 items carry no "arm" key, so they fall into
    # the single "_all" stratum and the whole budget goes to it.
    assert kinds.count("agreement") == 30


def test_audit_sample_is_deterministic():
    agreed = [{"criterion_id": f"A-{i:03d}"} for i in range(200)]
    disagreements = [{"criterion_id": f"C-{i:03d}"} for i in range(70)]
    first = audit_sample(agreed, disagreements, seed=20250107)
    second = audit_sample(agreed, disagreements, seed=20250107)
    assert first == second


@pytest.mark.parametrize("bad_output,match_pattern", [
    ('[]', "expected dict"),
    ('{"verdicts": {"C-001": true}}', "'verdicts' must be a list"),
    ('{"verdicts": [1,2,3]}', "each verdict must be a dict"),
    ('null', "expected dict"),
    ('{"verdicts": [{"verdict": true}]}', "missing 'criterion_id'"),
])
def test_parse_judge_output_rejects_wrong_shape(bad_output, match_pattern):
    with pytest.raises(JudgeError, match=match_pattern):
        parse_judge_output(bad_output, "T1", "mcp", "A", ["C-001"])


def test_audit_sample_agreement_stratum_independent_of_disagreement_count():
    """Regression: disagreement count must not perturb agreement sample."""
    agreed = [{"criterion_id": f"A-{i:03d}"} for i in range(200)]

    disagreements_small = [{"criterion_id": f"C-{i:03d}"} for i in range(5)]
    disagreements_large = [{"criterion_id": f"C-{i:03d}"} for i in range(999)]

    sample_small = audit_sample(agreed, disagreements_small, seed=20250107)
    sample_large = audit_sample(agreed, disagreements_large, seed=20250107)

    # Extract agreement strata from both samples
    agreements_small = [item for item in sample_small if item["stratum"] == "agreement"]
    agreements_large = [item for item in sample_large if item["stratum"] == "agreement"]

    # They should be identical despite different disagreement counts
    assert agreements_small == agreements_large


# --- Amendment A4: stratified agreement sampling -------------------------


def test_audit_sample_agreement_sample_keyword_overrides_default():
    agreed = [{"criterion_id": f"A-{i:03d}"} for i in range(200)]
    sample = audit_sample(agreed=agreed, disagreements=[], seed=20250107, agreement_sample=10)
    kinds = [item["stratum"] for item in sample]
    assert kinds.count("agreement") == 10


def test_audit_sample_agreement_stratified_by_arm():
    """Sizes 100/10/4 with budget 30: every non-empty arm gets at least
    min(5, its size); the total never exceeds the budget; the smallest arm
    (mcp, 4 items - below the floor) is taken in full."""
    agreed = (
        [{"criterion_id": f"BARE-{i:03d}", "arm": "bare"} for i in range(100)]
        + [{"criterion_id": f"WEB-{i:03d}", "arm": "web"} for i in range(10)]
        + [{"criterion_id": f"MCP-{i:03d}", "arm": "mcp"} for i in range(4)]
    )
    sample = audit_sample(agreed=agreed, disagreements=[], seed=20250107)
    agreements = [item for item in sample if item["stratum"] == "agreement"]
    by_arm: dict[str, int] = {}
    for item in agreements:
        by_arm[item["arm"]] = by_arm.get(item["arm"], 0) + 1

    assert len(agreements) <= 30
    assert by_arm["bare"] >= 5
    assert by_arm["web"] >= 5
    assert by_arm["mcp"] == 4


def test_audit_sample_agreement_without_arm_key_uses_single_stratum():
    """Backward shape: items with no 'arm' key still sample, in one
    fallback stratum, without crashing."""
    agreed = [{"criterion_id": f"A-{i:03d}"} for i in range(50)]
    sample = audit_sample(agreed=agreed, disagreements=[], seed=20250107)
    agreements = [item for item in sample if item["stratum"] == "agreement"]
    assert len(agreements) == 30
    assert all("arm" not in item or item["arm"] is None for item in agreements)


def test_audit_sample_stratified_is_deterministic():
    agreed = (
        [{"criterion_id": f"BARE-{i:03d}", "arm": "bare"} for i in range(100)]
        + [{"criterion_id": f"WEB-{i:03d}", "arm": "web"} for i in range(10)]
        + [{"criterion_id": f"MCP-{i:03d}", "arm": "mcp"} for i in range(4)]
    )
    first = audit_sample(agreed=agreed, disagreements=[], seed=20250107)
    second = audit_sample(agreed=agreed, disagreements=[], seed=20250107)
    assert first == second


# --- Citation-grounding validation --------------------------------------


def _citation(**overrides) -> Citation:
    defaults = dict(
        task_id="T1", arm="mcp", index=0, raw="Cass. civ. n. 123/2025",
        parsed={"court": "Cass. civ.", "section": None, "number": 123, "year": 2025},
        identifiable=True, resolved=True,
        resolution_note="Cass. n. 123/2025 reperita su Italgiure: verificata.",
    )
    defaults.update(overrides)
    return Citation(**defaults)


def test_grounding_prompt_never_reveals_which_arm_produced_the_citation():
    task = _task()
    for arm in ("bare", "web", "mcp"):
        prompt = build_grounding_prompt(task, _citation(arm=arm))
        assert arm not in prompt.lower().split()


def test_grounding_prompt_contains_query_issue_and_citation():
    task = _task()
    citation = _citation()
    prompt = build_grounding_prompt(task, citation)
    assert task.query in prompt
    assert task.issue_summary in prompt
    assert citation.raw in prompt
    assert citation.resolution_note in prompt


def test_parse_grounding_output_parses_a_positive_verdict():
    covers, reasoning = parse_grounding_output(
        json.dumps({"covers": True, "reasoning": "copre la questione"})
    )
    assert covers is True
    assert reasoning == "copre la questione"


def test_parse_grounding_output_parses_a_negative_verdict():
    covers, reasoning = parse_grounding_output(json.dumps({"covers": False, "reasoning": "tema diverso"}))
    assert covers is False
    assert reasoning == "tema diverso"


def test_parse_grounding_output_accepts_a_fenced_code_block():
    fenced = "Ecco:\n```json\n" + json.dumps({"covers": True, "reasoning": "ok"}) + "\n```\n"
    covers, _ = parse_grounding_output(fenced)
    assert covers is True


def test_parse_grounding_output_defaults_missing_reasoning_to_empty_string():
    covers, reasoning = parse_grounding_output(json.dumps({"covers": True}))
    assert covers is True
    assert reasoning == ""


def test_parse_grounding_output_is_fail_closed_on_non_json():
    with pytest.raises(JudgeError, match="JSON"):
        parse_grounding_output("boh")


def test_parse_grounding_output_rejects_a_non_dict_payload():
    with pytest.raises(JudgeError, match="expected dict"):
        parse_grounding_output("[]")


def test_parse_grounding_output_rejects_a_missing_covers_key():
    with pytest.raises(JudgeError, match="covers"):
        parse_grounding_output(json.dumps({"reasoning": "x"}))


def test_parse_grounding_output_rejects_a_non_bool_covers_value():
    with pytest.raises(JudgeError, match="bool"):
        parse_grounding_output(json.dumps({"covers": "true", "reasoning": "x"}))
