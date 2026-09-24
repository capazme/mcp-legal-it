"""Citation resolution against Italgiure via verifica_citazioni."""

from benchmarks.legalita.schema import Citation
from benchmarks.legalita.score.resolve import apply_resolution, format_for_verification


def _cit(index: int, number: int | None, raw: str) -> Citation:
    parsed = (
        {"court": "Cass. civ.", "section": "II", "number": number, "year": 2025}
        if number
        else None
    )
    return Citation(
        task_id="T1", arm="bare", index=index, raw=raw,
        parsed=parsed, identifiable=parsed is not None,
    )


def test_only_identifiable_citations_are_sent_for_verification():
    citations = [_cit(0, 123, "Cass. civ. n. 123/2025"), _cit(1, None, "la giurisprudenza")]
    payload = format_for_verification(citations)
    assert "123/2025" in payload
    assert "giurisprudenza" not in payload
    assert payload.count("\n") == 0


def test_format_emits_one_citation_per_line():
    citations = [_cit(0, 1, "a"), _cit(1, 2, "b")]
    assert len(format_for_verification(citations).splitlines()) == 2


def test_empty_input_yields_empty_payload():
    assert format_for_verification([]) == ""
    assert format_for_verification([_cit(0, None, "narrativa")]) == ""


def test_unidentifiable_citations_stay_unresolved_and_never_pass():
    citations = apply_resolution([_cit(0, None, "la giurisprudenza")], report="")
    assert citations[0].resolved is False
    assert citations[0].counts_as_grounded() is False


def test_a_confirmed_citation_is_marked_resolved():
    report = (
        "| 1 | Cass. civ. n. 123/2025 | Sentenza | verificata "
        "| Cass. n. 123/2025 reperita su Italgiure. |"
    )
    citations = apply_resolution([_cit(0, 123, "Cass. civ. n. 123/2025")], report)
    assert citations[0].resolved is True
    assert "verificata" in citations[0].resolution_note


def test_a_missing_citation_is_marked_unresolved():
    report = (
        "| 1 | Cass. civ. n. 123/2025 | Sentenza | inesistente "
        "| Decisione n. 123/2025 non trovata negli archivi della Cassazione. |"
    )
    citations = apply_resolution([_cit(0, 123, "Cass. civ. n. 123/2025")], report)
    assert citations[0].resolved is False


def test_non_verificata_does_not_falsely_match_the_verificata_marker():
    """'non verificata' CONTAINS 'verificata' as a substring — the negative
    marker must win, or an unreachable-source verdict would be misread as a
    positive confirmation and silently mark a hallucinated citation as resolved."""
    report = (
        "| 1 | Cass. civ. n. 123/2025 | Sentenza | non verificata "
        "| Italgiure non raggiungibile: timeout. |"
    )
    citations = apply_resolution([_cit(0, 123, "Cass. civ. n. 123/2025")], report)
    assert citations[0].resolved is False


def test_metadati_discordanti_is_unresolved():
    report = (
        "| 1 | Cass. civ. n. 123/2025 | Sentenza | metadati discordanti "
        "| Sezione citata (II) diversa dalla sezione effettiva (III). Cass. n. 123/2025. |"
    )
    citations = apply_resolution([_cit(0, 123, "Cass. civ. n. 123/2025")], report)
    assert citations[0].resolved is False
    assert "metadati discordanti" in citations[0].resolution_note


def test_resolution_is_fail_closed_when_the_report_says_nothing():
    citations = apply_resolution([_cit(0, 123, "Cass. civ. n. 123/2025")], report="")
    assert citations[0].resolved is False
    assert "no verdict" in citations[0].resolution_note.lower()


def test_covers_issue_is_left_untouched_by_resolution():
    report = (
        "| 1 | x | Sentenza | verificata | Cass. n. 123/2025 reperita su Italgiure. |"
    )
    citations = apply_resolution([_cit(0, 123, "x")], report)
    assert citations[0].covers_issue is None
