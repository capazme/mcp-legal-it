"""Export tasks for human curation and read the verdicts back."""

import pytest

from benchmarks.legalita.build.review import (
    apply_review,
    export_review_markdown,
    needs_review,
    parse_review_markdown,
)
from benchmarks.legalita.schema import Criterion, Task


def _task(task_id: str, confidence: str = "low") -> Task:
    return Task(
        id=task_id, track="jurisprudential", domain="civil",
        query="Quesito?", criteria=[Criterion(id="C-001", text="Criterio", required=True)],
        issue_status="settled", issue_summary="Questione.",
        seed_citation={"court": "Cass. civ.", "section": "II", "number": 1, "year": 2025},
        builder_confidence=confidence, curated=False,
    )


def test_only_low_confidence_tasks_enter_the_queue():
    tasks = [_task("A", "low"), _task("B", "high"), _task("C", "low")]
    assert [t.id for t in needs_review(tasks)] == ["A", "C"]


def test_already_curated_tasks_are_not_re_queued():
    task = _task("A", "low")
    task.curated = True
    assert needs_review([task]) == []


def test_export_shows_the_reviewer_everything_needed_to_judge():
    text = export_review_markdown([_task("A")])
    assert "A" in text
    assert "Quesito?" in text
    assert "Criterio" in text
    assert "settled" in text
    assert "1/2025" in text
    assert "[ ] approva" in text


def test_round_trip_of_an_untouched_export_approves_nothing():
    text = export_review_markdown([_task("A")])
    assert parse_review_markdown(text) == {}


def test_parses_an_approval():
    text = export_review_markdown([_task("A")]).replace("[ ] approva", "[x] approva")
    assert parse_review_markdown(text) == {"A": {"action": "approve"}}


def test_parses_a_rejection():
    text = export_review_markdown([_task("A")]).replace("[ ] scarta", "[x] scarta")
    assert parse_review_markdown(text) == {"A": {"action": "reject"}}


def test_approval_marks_the_task_curated():
    result = apply_review([_task("A")], {"A": {"action": "approve"}})
    assert len(result) == 1
    assert result[0].curated is True


def test_rejection_drops_the_task():
    assert apply_review([_task("A")], {"A": {"action": "reject"}}) == []


def test_untouched_tasks_pass_through_unchanged():
    original = _task("A")
    assert apply_review([original], {}) == [original]


def test_a_decision_for_an_unknown_task_is_an_error():
    with pytest.raises(KeyError, match="ZZZ"):
        apply_review([_task("A")], {"ZZZ": {"action": "approve"}})


def test_both_boxes_ticked_is_an_error():
    text = export_review_markdown([_task("A")])
    text = text.replace("[ ] approva", "[x] approva").replace("[ ] scarta", "[x] scarta")
    with pytest.raises(ValueError, match="both"):
        parse_review_markdown(text)


def test_checkbox_style_notes_are_ignored():
    """Free-text notes that resemble checkboxes do not trigger decisions."""
    text = export_review_markdown([_task("A")])
    # Insert checkbox-style note lines; canonical boxes remain untouched
    text = text.replace("- [ ] approva", "- [x] approvativa la revisione già fatta\n- [ ] approva")
    text = text.replace("- [ ] scarta", "- [x] scartabile per difetti di merito\n- [ ] scarta")
    assert parse_review_markdown(text) == {}


def test_a_ticked_box_with_trailing_text_is_not_a_decision():
    """A checkbox with trailing text (e.g., a qualifier) is not recognized as a decision."""
    text = export_review_markdown([_task("A")])
    # Replace canonical checkbox with one that has trailing text
    text = text.replace("[ ] approva", "[x] approva (con riserva)")
    # Should parse as untouched (no decision) because trailing text makes it non-canonical
    assert parse_review_markdown(text) == {}
