"""Task generation from a seed decision.

Only the parsing is unit-tested; calling the builder model is live. The
parser must be strict, because a malformed task silently corrupts every
downstream metric.
"""

import json
from datetime import date

import pytest

from benchmarks.legalita.build.tasks import (
    BuilderError,
    build_prompt,
    parse_builder_output,
)
from benchmarks.legalita.corpus.sample import SeedDecision

_DECISION = SeedDecision(
    doc_id="d1", number=12345, year=2025, deposited=date(2025, 3, 1),
    section="II", materia="civile", dispositivo="Massima di riferimento.",
)

_GOOD = {
    "query": "Il committente risponde dei danni cagionati a terzi dall'appaltatore?",
    "issue_summary": "Responsabilita del committente per fatto dell'appaltatore.",
    "issue_status": "settled",
    "builder_confidence": "high",
    "criteria": [
        {"text": "Afferma l'autonomia dell'appaltatore", "required": True},
        {"text": "Richiama l'eccezione del nudus minister", "required": True},
        {"text": "Cita la culpa in eligendo", "required": False},
    ],
}


def test_prompt_contains_the_decision_and_asks_for_a_standalone_query():
    prompt = build_prompt(_DECISION, domain="civil")
    assert "12345" in prompt
    assert "Massima di riferimento." in prompt
    assert "standalone" in prompt.lower() or "autonom" in prompt.lower()


def test_parses_a_well_formed_builder_response():
    task = parse_builder_output(
        json.dumps(_GOOD), task_id="JUR-CIV-001", domain="civil", decision=_DECISION
    )
    assert task.id == "JUR-CIV-001"
    assert task.track == "jurisprudential"
    assert task.domain == "civil"
    assert task.issue_status == "settled"
    assert [c.id for c in task.criteria] == ["C-001", "C-002", "C-003"]
    assert [c.required for c in task.criteria] == [True, True, False]
    assert task.curated is False


def test_seed_citation_is_taken_from_the_decision_not_the_model():
    task = parse_builder_output(
        json.dumps({**_GOOD, "seed_citation": {"number": 999, "year": 1999}}),
        task_id="JUR-CIV-001", domain="civil", decision=_DECISION,
    )
    assert task.seed_citation["number"] == 12345
    assert task.seed_citation["year"] == 2025


def test_parses_response_wrapped_in_a_fenced_code_block():
    fenced = "Ecco il task:\n```json\n" + json.dumps(_GOOD) + "\n```\n"
    task = parse_builder_output(fenced, "JUR-CIV-001", "civil", _DECISION)
    assert task.query.startswith("Il committente")


def test_rejects_output_that_is_not_json():
    with pytest.raises(BuilderError, match="JSON"):
        parse_builder_output("non ho capito", "T", "civil", _DECISION)


def test_rejects_a_task_with_no_required_criterion():
    payload = {**_GOOD, "criteria": [{"text": "solo bonus", "required": False}]}
    with pytest.raises(BuilderError):
        parse_builder_output(json.dumps(payload), "T", "civil", _DECISION)


def test_rejects_an_unknown_issue_status():
    payload = {**_GOOD, "issue_status": "obiter dictum"}
    with pytest.raises(BuilderError):
        parse_builder_output(json.dumps(payload), "T", "civil", _DECISION)


def test_rejects_a_query_that_leaks_the_decision_number():
    payload = {**_GOOD, "query": "Secondo Cass. n. 12345/2025, il committente risponde?"}
    with pytest.raises(BuilderError, match="leak"):
        parse_builder_output(json.dumps(payload), "T", "civil", _DECISION)


def test_low_confidence_is_preserved_for_the_curation_queue():
    payload = {**_GOOD, "builder_confidence": "low"}
    task = parse_builder_output(json.dumps(payload), "T", "civil", _DECISION)
    assert task.builder_confidence == "low"
