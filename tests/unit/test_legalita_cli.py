"""CLI argument handling and resumability."""

import argparse
import json
from datetime import date
from pathlib import Path

import pytest

import benchmarks.legalita.run.cli as cli
from benchmarks.legalita.corpus.sample import SeedDecision
from benchmarks.legalita.run.cli import (
    _agreed_with_reasoning,
    _audit_id,
    _citations_by_arm_task,
    _covers_issue_map,
    _excluded_error_runs,
    _fmt_p,
    _grounding_agreed_and_disagreements,
    _grounding_agreement,
    _load_jsonl,
    _paired_mcnemar,
    _paired_verdicts,
    _parse_audit_id,
    _pending_grounding_by_arm,
    _per_task_gog_values,
    _per_task_pass_values,
    _stability_arm_metrics,
    _stability_task_entry,
    _task_coverage_map,
    _task_pass_map,
    _write_audit_manifest,
    build_parser,
    count_bonus_judged,
    drop_incomplete,
    export_audit_markdown,
    export_leakage_markdown,
    load_seeds,
    merge_verdicts,
    parse_audit_markdown,
    parse_leakage_markdown,
    pending_runs,
    save_seeds,
    stability_subset,
)
from benchmarks.legalita.run.variants import VariantError, VariantState
from benchmarks.legalita.schema import (
    ARMS,
    Citation,
    Criterion,
    RunRecord,
    Task,
    Verdict,
    save_tasks,
)


def test_parser_exposes_every_pipeline_stage():
    parser = build_parser()
    for command in (
        "sample", "build", "review-export", "review-apply",
        "run", "judge", "audit-export", "audit-apply",
        "leakage-export", "leakage-apply", "score", "stability",
    ):
        assert parser.parse_args([command]).command == command


def test_stability_defaults_model_and_max_turns():
    args = build_parser().parse_args(["stability"])
    assert args.model == "opus"
    assert args.max_turns == 30


def test_run_defaults_to_every_declared_arm():
    # The default must stay exactly the declared arm set — adding a future
    # variant arm to schema.ARMS makes it part of the default comparison
    # automatically, never silently omitted.
    assert build_parser().parse_args(["run"]).arms == list(ARMS)


def test_parser_exposes_the_variants_stage():
    parser = build_parser()
    assert parser.parse_args(["variants"]).command == "variants"
    assert parser.parse_args(["variants", "--force"]).force is True
    assert parser.parse_args(["variants"]).force is False


def test_run_accepts_an_arm_subset():
    args = build_parser().parse_args(["run", "--arms", "mcp"])
    assert args.arms == ["mcp"]


def test_run_rejects_an_unknown_arm():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--arms", "tools"])


def test_pending_runs_is_the_full_cross_product_when_nothing_is_done():
    pending = pending_runs(["T1", "T2"], ["bare", "mcp"], done=set())
    assert pending == [("T1", "bare"), ("T1", "mcp"), ("T2", "bare"), ("T2", "mcp")]


def test_pending_runs_skips_completed_work():
    pending = pending_runs(["T1", "T2"], ["bare", "mcp"], done={("T1", "bare")})
    assert ("T1", "bare") not in pending
    assert len(pending) == 3


def test_pending_runs_is_empty_when_everything_is_done():
    done = {("T1", "bare"), ("T1", "mcp")}
    assert pending_runs(["T1"], ["bare", "mcp"], done=done) == []


# --- Seed (de)serialisation ------------------------------------------------


def _decision(n: int) -> SeedDecision:
    return SeedDecision(
        doc_id=f"doc-{n}", number=n, year=2025, deposited=date(2025, 3, 1),
        section="II", materia="civile", dispositivo="massima",
    )


def test_seeds_round_trip_through_json(tmp_path):
    picked = {"civil": [_decision(1), _decision(2)], "labour": [_decision(3)]}
    path = tmp_path / "seeds.json"
    save_seeds(picked, path)
    restored = load_seeds(path)
    assert restored == picked


# --- JSONL loading: resumability and corrupt-tail tolerance ----------------


def _run_record(task_id="T1", arm="bare") -> RunRecord:
    return RunRecord(
        task_id=task_id, arm=arm, model="m", answer="a",
        tool_calls=[], num_turns=1, duration_ms=1, usage={}, error=None,
    )


def test_load_jsonl_reads_every_well_formed_line(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text(
        "\n".join(json.dumps(_run_record(f"T{i}").to_dict()) for i in range(3)) + "\n",
        encoding="utf-8",
    )
    items, skipped = _load_jsonl(path, RunRecord.from_dict)
    assert [r.task_id for r in items] == ["T0", "T1", "T2"]
    assert skipped == 0


def test_load_jsonl_tolerates_a_truncated_trailing_line(tmp_path):
    path = tmp_path / "runs.jsonl"
    good = json.dumps(_run_record("T0").to_dict())
    path.write_text(good + "\n" + '{"task_id": "T1", "arm": "bare"' , encoding="utf-8")
    items, skipped = _load_jsonl(path, RunRecord.from_dict)
    assert [r.task_id for r in items] == ["T0"]
    assert skipped == 1


def test_load_jsonl_raises_on_corrupt_non_trailing_line(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text('{"broken"\n' + json.dumps(_run_record("T0").to_dict()) + "\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _load_jsonl(path, RunRecord.from_dict)


def test_load_jsonl_of_a_missing_file_is_empty():
    items, skipped = _load_jsonl(Path("/nonexistent/path/does-not-exist.jsonl"), RunRecord.from_dict)
    assert items == []
    assert skipped == 0


# --- Merge/drop contract: the mandatory step before scoring -----------------


def _task_with(task_id: str, *, required=("C-001",), bonus=()) -> Task:
    criteria = [Criterion(id=cid, text=cid, required=True) for cid in required]
    criteria += [Criterion(id=cid, text=cid, required=False) for cid in bonus]
    return Task(
        id=task_id, track="jurisprudential", domain="civil", query="q", criteria=criteria,
        issue_status="settled", issue_summary="", seed_citation=None,
        builder_confidence="high", curated=True,
    )


def test_merge_verdicts_overlays_resolutions_onto_agreed():
    agreed = {("T1", "mcp", "C-001"): True}
    resolutions = {_audit_id("criterion", "T1", "mcp", "C-002"): False}
    merged = merge_verdicts(agreed, resolutions)
    assert merged == {("T1", "mcp", "C-001"): True, ("T1", "mcp", "C-002"): False}


def test_merge_verdicts_resolution_overrides_an_agreed_entry():
    agreed = {("T1", "mcp", "C-001"): True}
    resolutions = {_audit_id("criterion", "T1", "mcp", "C-001"): False}
    assert merge_verdicts(agreed, resolutions) == {("T1", "mcp", "C-001"): False}


def test_merge_verdicts_ignores_grounding_resolutions():
    agreed = {("T1", "mcp", "C-001"): True}
    resolutions = {_audit_id("grounding", "T1", "mcp", "0"): True}
    assert merge_verdicts(agreed, resolutions) == agreed


def test_drop_incomplete_keeps_a_task_arm_with_full_required_coverage():
    tasks = {"T1": _task_with("T1", required=("C-001", "C-002"))}
    merged = {("T1", "mcp", "C-001"): True, ("T1", "mcp", "C-002"): False}
    by_arm, unresolved = drop_incomplete(merged, tasks, [("T1", "mcp")])
    assert by_arm == {"mcp": {"T1": {"C-001": True, "C-002": False}}}
    assert unresolved == 0


def test_drop_incomplete_drops_a_task_arm_missing_a_required_verdict():
    tasks = {"T1": _task_with("T1", required=("C-001", "C-002"))}
    merged = {("T1", "mcp", "C-001"): True}  # C-002 never resolved
    by_arm, unresolved = drop_incomplete(merged, tasks, [("T1", "mcp")])
    assert by_arm == {}
    assert unresolved == 1


def test_drop_incomplete_drops_a_task_arm_with_no_verdicts_at_all():
    tasks = {"T1": _task_with("T1")}
    by_arm, unresolved = drop_incomplete({}, tasks, [("T1", "mcp")])
    assert by_arm == {}
    assert unresolved == 1


def test_drop_incomplete_counts_drops_independently_per_pair():
    tasks = {
        "T1": _task_with("T1", required=("C-001",)),
        "T2": _task_with("T2", required=("C-001",)),
    }
    merged = {("T1", "mcp", "C-001"): True}  # T2/mcp has nothing
    by_arm, unresolved = drop_incomplete(merged, tasks, [("T1", "mcp"), ("T2", "mcp")])
    assert by_arm == {"mcp": {"T1": {"C-001": True}}}
    assert unresolved == 1


def test_drop_incomplete_keeps_a_partial_bonus_verdict_alongside_full_required():
    # A bonus criterion missing its verdict must never block the pair —
    # only required criteria gate the drop.
    tasks = {"T1": _task_with("T1", required=("C-001",), bonus=("B-001", "B-002"))}
    merged = {("T1", "mcp", "C-001"): True, ("T1", "mcp", "B-001"): True}
    by_arm, unresolved = drop_incomplete(merged, tasks, [("T1", "mcp")])
    assert by_arm == {"mcp": {"T1": {"C-001": True, "B-001": True}}}
    assert unresolved == 0


def test_count_bonus_judged_counts_only_bonus_criteria():
    tasks = {"T1": _task_with("T1", required=("C-001",), bonus=("B-001", "B-002"))}
    verdicts_for_arm = {"T1": {"C-001": True, "B-001": True, "B-002": False}}
    assert count_bonus_judged(verdicts_for_arm, tasks) == 2


def test_count_bonus_judged_is_zero_when_no_bonus_verdict_survived():
    tasks = {"T1": _task_with("T1", required=("C-001",), bonus=("B-001",))}
    verdicts_for_arm = {"T1": {"C-001": True}}
    assert count_bonus_judged(verdicts_for_arm, tasks) == 0


def test_count_bonus_judged_sums_across_tasks():
    tasks = {
        "T1": _task_with("T1", required=("C-001",), bonus=("B-001",)),
        "T2": _task_with("T2", required=("C-001",), bonus=("B-001", "B-002")),
    }
    verdicts_for_arm = {
        "T1": {"C-001": True, "B-001": True},
        "T2": {"C-001": True, "B-001": True, "B-002": True},
    }
    assert count_bonus_judged(verdicts_for_arm, tasks) == 3


# --- Citation-grounding: the agreement rule and its "queued" behaviour -----


def test_grounding_agreement_both_true_grounds_the_citation():
    assert _grounding_agreement(True, True) is True


def test_grounding_agreement_both_false_does_not_ground_the_citation():
    assert _grounding_agreement(False, False) is False


def test_grounding_agreement_disagreement_is_none_not_guessed():
    assert _grounding_agreement(True, False) is None
    assert _grounding_agreement(False, True) is None


def test_covers_issue_map_resolves_only_pairs_both_judges_answered():
    records = [
        {"task_id": "T1", "arm": "mcp", "index": 0, "judge": "A", "covers": True, "reasoning": ""},
        # No judge B entry yet for this citation — must stay absent, not guessed.
    ]
    assert _covers_issue_map(records) == {}


def test_covers_issue_map_agreement_grounds_the_citation():
    records = [
        {"task_id": "T1", "arm": "mcp", "index": 0, "judge": "A", "covers": True, "reasoning": ""},
        {"task_id": "T1", "arm": "mcp", "index": 0, "judge": "B", "covers": True, "reasoning": ""},
    ]
    assert _covers_issue_map(records) == {("T1", "mcp", "0"): True}


def test_covers_issue_map_disagreement_is_queued_as_none():
    records = [
        {"task_id": "T1", "arm": "mcp", "index": 0, "judge": "A", "covers": True, "reasoning": ""},
        {"task_id": "T1", "arm": "mcp", "index": 0, "judge": "B", "covers": False, "reasoning": ""},
    ]
    assert _covers_issue_map(records) == {("T1", "mcp", "0"): None}


# --- Audit-id round trip and markdown parsing -------------------------------


def test_audit_id_round_trips_for_a_criterion_item():
    audit_id = _audit_id("criterion", "JUR-CIV-001", "mcp", "C-002")
    assert _parse_audit_id(audit_id) == ("criterion", ("JUR-CIV-001", "mcp", "C-002"))


def test_audit_id_round_trips_for_a_grounding_item():
    audit_id = _audit_id("grounding", "JUR-CIV-001", "mcp", "3")
    assert _parse_audit_id(audit_id) == ("grounding", ("JUR-CIV-001", "mcp", "3"))


def _agreement_item(kind="criterion"):
    return {
        "task_id": "JUR-CIV-001", "arm": "mcp", "criterion_id": "C-001",
        "verdict": True, "reasoning_a": "ok", "reasoning_b": "ok",
        "kind": kind, "stratum": "agreement",
    }


def _disagreement_item(kind="criterion"):
    return {
        "task_id": "JUR-CIV-001", "arm": "mcp", "criterion_id": "C-002",
        "reasoning_a": "cita l'articolo", "reasoning_b": "non lo cita",
        "kind": kind, "stratum": "disagreement",
    }


def test_export_audit_markdown_contains_a_checkbox_block_per_item():
    text = export_audit_markdown([_agreement_item(), _disagreement_item()])
    assert "## JUR-CIV-001--MCP--CRITERION--C-001" in text
    assert "## JUR-CIV-001--MCP--CRITERION--C-002" in text
    assert text.count("- [ ] vero") == 2
    assert text.count("- [ ] falso") == 2


def test_parse_audit_markdown_reads_ticked_boxes():
    text = export_audit_markdown([_disagreement_item()]).replace("- [ ] vero", "- [x] vero")
    resolutions = parse_audit_markdown(text)
    assert resolutions == {"JUR-CIV-001--MCP--CRITERION--C-002": True}


def test_parse_audit_markdown_rejects_both_boxes_ticked():
    text = (
        export_audit_markdown([_disagreement_item()])
        .replace("- [ ] vero", "- [x] vero")
        .replace("- [ ] falso", "- [x] falso")
    )
    with pytest.raises(ValueError, match="both vero and falso"):
        parse_audit_markdown(text)


def test_parse_audit_markdown_leaves_untouched_items_absent():
    text = export_audit_markdown([_disagreement_item()])
    assert parse_audit_markdown(text) == {}


def test_parse_audit_markdown_treats_a_ticked_box_with_trailing_text_as_deferred():
    text = export_audit_markdown([_disagreement_item()]).replace(
        "- [ ] vero", "- [x] vero (con riserva)"
    )
    assert parse_audit_markdown(text) == {}


# --- Reasoning reattachment for agreed items --------------------------------


def _v(task_id, arm, cid, judge, verdict, reasoning=""):
    return Verdict(task_id=task_id, arm=arm, criterion_id=cid, judge=judge, verdict=verdict, reasoning=reasoning)


def test_agreed_with_reasoning_reattaches_both_judges_reasoning():
    agreed = {("T1", "mcp", "C-001"): True}
    verdicts_a = [_v("T1", "mcp", "C-001", "A", True, "cita l'articolo")]
    verdicts_b = [_v("T1", "mcp", "C-001", "B", True, "corretto")]
    items = _agreed_with_reasoning(agreed, verdicts_a, verdicts_b)
    assert items == [{
        "task_id": "T1", "arm": "mcp", "criterion_id": "C-001", "verdict": True,
        "reasoning_a": "cita l'articolo", "reasoning_b": "corretto",
    }]


# --- Bootstrap-CI input helpers and citation grouping -----------------------


def test_per_task_pass_values_is_one_iff_every_required_criterion_passed():
    tasks = {
        "T1": _task_with("T1", required=("C-001", "C-002")),
        "T2": _task_with("T2", required=("C-001",)),
    }
    verdicts_for_arm = {
        "T1": {"C-001": True, "C-002": False},
        "T2": {"C-001": True},
    }
    assert _per_task_pass_values(verdicts_for_arm, tasks) == [0.0, 1.0]


# --- Amendment A2: per-task pass/coverage maps and paired McNemar ----------


def test_task_pass_map_matches_per_task_pass_values_formula():
    # _per_task_pass_values is refactored to sit on top of _task_pass_map --
    # pin that both agree on the same hand-computed case, keyed by task id.
    tasks = {
        "T1": _task_with("T1", required=("C-001", "C-002")),
        "T2": _task_with("T2", required=("C-001",)),
    }
    verdicts_for_arm = {
        "T1": {"C-001": True, "C-002": False},
        "T2": {"C-001": True},
    }
    assert _task_pass_map(verdicts_for_arm, tasks) == {"T1": False, "T2": True}
    assert _per_task_pass_values(verdicts_for_arm, tasks) == [0.0, 1.0]


def test_task_pass_map_is_empty_for_empty_verdicts():
    assert _task_pass_map({}, {}) == {}


def test_task_coverage_map_is_true_iff_any_citation_is_grounded():
    citations_for_arm = {
        "T1": [_citation("T1", "mcp", 0, grounded=True), _citation("T1", "mcp", 1, grounded=False)],
        "T2": [_citation("T2", "mcp", 0, grounded=False)],
        "T3": [],
    }
    assert _task_coverage_map(citations_for_arm) == {"T1": True, "T2": False, "T3": False}


def test_paired_mcnemar_pairs_only_the_intersection_of_task_ids():
    # T1, T2 appear in both maps (T1 concordant True/True, T2 discordant
    # True/False). T3 is bare-only and T4 is mcp-only -- neither is paired.
    map_bare = {"T1": True, "T2": True, "T3": False}
    map_mcp = {"T1": True, "T2": False, "T4": True}
    result = _paired_mcnemar(map_bare, map_mcp)
    assert result["pairable"] == 2
    assert result["b"] == 1  # T2: bare True, mcp False
    assert result["c"] == 0
    assert result["discordant"] == 1
    assert result["p_value"] == pytest.approx(1.0)


def test_paired_mcnemar_of_disjoint_maps_has_zero_pairable_and_null_p():
    result = _paired_mcnemar({"T1": True}, {"T2": True})
    assert result == {"b": 0, "c": 0, "discordant": 0, "p_value": None, "pairable": 0}


# --- Fix-round (code review): null-safe kappa + p-value display floor -----


def test_fmt_p_is_null_safe():
    assert _fmt_p(None) == "null"


def test_fmt_p_renders_normal_values_with_four_decimals():
    assert _fmt_p(0.0625) == "0.0625"
    assert _fmt_p(1.0) == "1.0000"


def test_fmt_p_floors_values_below_the_display_precision():
    # b=20, c=0 -> p = 2 * comb(20,0) / 2**20 ~= 1.9e-6 -- far below what
    # 4 decimals can represent; must never render as the impossible "0.0000".
    tiny = 2 / (2**20)
    assert _fmt_p(tiny) == "<0.0001"


def test_fmt_p_boundary_at_exactly_the_floor_is_not_below_it():
    assert _fmt_p(0.0001) == "0.0001"


def _citation(task_id, arm, index, *, grounded):
    c = Citation(task_id=task_id, arm=arm, index=index, raw="x")
    if grounded:
        c.identifiable, c.resolved, c.covers_issue = True, True, True
    return c


def test_per_task_gog_values_scores_zero_for_an_empty_citation_list():
    assert _per_task_gog_values({"T1": []}) == [0.0]


def test_per_task_gog_values_matches_hand_computed_ratio():
    citations_for_arm = {
        "T1": [_citation("T1", "mcp", 0, grounded=True), _citation("T1", "mcp", 1, grounded=False)],
    }
    assert _per_task_gog_values(citations_for_arm) == [0.5]


def test_citations_by_arm_task_seeds_an_empty_list_for_a_run_with_no_citations():
    tasks = {"T1": _task_with("T1")}
    by_arm_task = _citations_by_arm_task([], tasks, [("T1", "mcp")])
    assert by_arm_task == {"mcp": {"T1": []}}


def test_citations_by_arm_task_excludes_mdd_tasks():
    tasks = {
        "T1": Task(
            id="T1", track="mdd", domain="civil", query="q",
            criteria=[Criterion(id="C-001", text="x", required=True)],
            issue_status=None, issue_summary="", seed_citation=None,
            builder_confidence="high", curated=True,
        )
    }
    by_arm_task = _citations_by_arm_task([], tasks, [("T1", "mcp")])
    assert by_arm_task == {}


def test_paired_verdicts_keeps_disagreements_unlike_reconcile():
    verdicts_a = [_v("T1", "mcp", "C-001", "A", True), _v("T1", "mcp", "C-002", "A", True)]
    verdicts_b = [_v("T1", "mcp", "C-001", "B", True), _v("T1", "mcp", "C-002", "B", False)]
    pa, pb = _paired_verdicts(verdicts_a, verdicts_b)
    assert pa == [True, True]
    assert pb == [True, False]


def test_paired_verdicts_tolerates_a_one_sided_judge():
    verdicts_a = [_v("T1", "mcp", "C-001", "A", True)]
    verdicts_b: list[Verdict] = []
    assert _paired_verdicts(verdicts_a, verdicts_b) == ([], [])


# =============================================================================
# Fix-round tests (coordinator review: 3 Critical, 7 Important)
# =============================================================================


# --- CRITICAL 1: _append_jsonl must self-heal a truncated trailing line ----


def test_append_jsonl_self_heals_a_truncated_trailing_line(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text('{"a": 1}\n{"b": 2, "trunca', encoding="utf-8")  # no closing brace, no newline
    cli._append_jsonl(path, {"c": 3})
    items, skipped = _load_jsonl(path, lambda d: d)
    assert skipped == 0
    assert items == [{"a": 1}, {"c": 3}]


def test_append_jsonl_is_a_no_op_truncation_when_file_already_ends_cleanly(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text('{"a": 1}\n', encoding="utf-8")
    cli._append_jsonl(path, {"b": 2})
    items, skipped = _load_jsonl(path, lambda d: d)
    assert skipped == 0
    assert items == [{"a": 1}, {"b": 2}]


def test_append_jsonl_survives_repeated_truncated_appends(tmp_path):
    """The original bug only manifested on the SECOND append after a
    truncation, once the merged line was no longer the file's last line —
    pin that it stays clean across several rounds, not just one."""
    path = tmp_path / "x.jsonl"
    path.write_text("", encoding="utf-8")
    for i in range(5):
        cli._append_jsonl(path, {"n": i})
        # Simulate a crash mid-write: truncate the last few bytes so the
        # file no longer ends in a complete, newline-terminated line.
        raw = path.read_bytes()
        path.write_bytes(raw[:-3])
    cli._append_jsonl(path, {"n": "final"})
    items, skipped = _load_jsonl(path, lambda d: d)
    assert skipped == 0
    assert items[-1] == {"n": "final"}


def test_run_self_heals_a_truncated_trailing_line_through_the_stage(tmp_path, monkeypatch):
    """Stage-level (IMPORTANT 9a): a truncated runs.jsonl must not brick
    `run` — after a resumed run appends, the file must reload cleanly."""
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1"), _task_with("T2")], data_dir / "tasks.json")

    results_dir.mkdir(parents=True)
    runs_path = results_dir / "runs.jsonl"
    good = json.dumps(_run_record("T1", "bare").to_dict())
    # A truncated trailing record for T2 — no closing brace, no newline.
    runs_path.write_text(good + "\n" + '{"task_id": "T2", "arm": "bare", "trunca', encoding="utf-8")

    def fake_run_arm(task, arm, workdir, plugin_root, model, max_turns):
        return _run_record(task.id, arm)

    monkeypatch.setattr(cli.arms, "run_arm", fake_run_arm)

    args = argparse.Namespace(arms=["bare"], limit=None, model="opus", max_turns=12)
    rc = cli.cmd_run(args)
    assert rc == 0

    items, skipped = _load_jsonl(runs_path, RunRecord.from_dict)
    assert skipped == 0
    assert sorted((r.task_id, r.arm) for r in items) == [("T1", "bare"), ("T2", "bare")]


def test_run_provisions_variant_worktrees_and_passes_the_pin_to_the_arm(
    tmp_path, monkeypatch,
):
    """`run --arms plugin-v3` must provision the variant worktrees BEFORE any
    spend, pass the provisioned plugin_dir and variant_sha into run_arm, and
    record the pin on the persisted record — a comparison number without the
    commit it ran against is not reproducible. Provisioning's git behaviour
    is covered by test_legalita_variants.py; here it is faked at the CLI seam.
    """
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")

    plugin_dir = tmp_path / "variant" / "plugin"
    plugin_dir.mkdir(parents=True)
    fake_state = VariantState(
        arm="plugin-v3", ref="v3-test", sha="a" * 40,
        worktree=plugin_dir.parent, plugin_dir=plugin_dir,
    )
    monkeypatch.setattr(cli, "ensure_worktrees", lambda repo, **kw: {"plugin-v3": fake_state})

    calls = []

    def fake_run_arm(task, arm, workdir, plugin_root, model, max_turns,
                     plugin_dir=None, variant_sha=None):
        calls.append((arm, plugin_dir, variant_sha))
        return RunRecord(
            task_id=task.id, arm=arm, model=model, answer="a", tool_calls=[],
            num_turns=1, duration_ms=1, usage={}, error=None, variant_sha=variant_sha,
        )

    monkeypatch.setattr(cli.arms, "run_arm", fake_run_arm)

    args = argparse.Namespace(arms=["plugin-v3"], limit=None, model="opus", max_turns=12)
    rc = cli.cmd_run(args)
    assert rc == 0
    assert calls == [("plugin-v3", plugin_dir, "a" * 40)]

    records, _ = _load_jsonl(results_dir / "runs.jsonl", RunRecord.from_dict)
    assert records[0].variant_sha == "a" * 40


def test_run_refuses_variant_arms_when_provisioning_fails(tmp_path, monkeypatch):
    """A broken pin (missing ref, unresolvable SHA) must stop the stage with
    a refusal — never a batch of degraded runs that look like data."""
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")

    def boom(repo, **kw):
        raise VariantError("cannot resolve variant ref 'release/ghost'")

    monkeypatch.setattr(cli, "ensure_worktrees", boom)
    monkeypatch.setattr(
        cli.arms, "run_arm",
        lambda *a, **kw: pytest.fail("run_arm must not be called after a provisioning failure"),
    )

    args = argparse.Namespace(arms=["plugin-v2"], limit=None, model="opus", max_turns=12)
    rc = cli.cmd_run(args)
    assert rc == 1
    assert not (results_dir / "runs.jsonl").exists()


# --- CRITICAL 2: audit-apply gate must use the exported manifest, and ------
# --- must always persist collected resolutions before returning non-zero --


def test_write_audit_manifest_splits_mandatory_and_optional(tmp_path):
    items = [_agreement_item(), _disagreement_item()]
    manifest = _write_audit_manifest(items, tmp_path / "manifest.json")
    assert manifest["mandatory"] == [_audit_id("criterion", "JUR-CIV-001", "mcp", "C-002")]
    assert manifest["optional"] == [_audit_id("criterion", "JUR-CIV-001", "mcp", "C-001")]
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == manifest


def test_export_audit_markdown_without_overflow_has_no_warning():
    text = export_audit_markdown([_disagreement_item()])
    assert "copertura parziale" not in text


def test_export_audit_markdown_with_overflow_shows_the_warning():
    text = export_audit_markdown([_disagreement_item()], overflow={"criterion": 20, "grounding": 0})
    assert "copertura parziale" in text
    assert "20" in text


def test_audit_export_apply_manifest_gate_survives_cap_overflow(tmp_path, monkeypatch):
    """Stage-level (IMPORTANT 9b / CRITICAL 2): with 60 disagreements the
    export caps the mandatory queue at 40 — apply must gate on exactly
    those 40, not the full 60, or the gate is permanently unsatisfiable."""
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)
    results_dir.mkdir(parents=True)

    verdicts = []
    for i in range(60):
        tid = f"T{i:03d}"
        verdicts.append(Verdict(task_id=tid, arm="mcp", criterion_id="C-001", judge="A", verdict=True, reasoning="a"))
        verdicts.append(Verdict(task_id=tid, arm="mcp", criterion_id="C-001", judge="B", verdict=False, reasoning="b"))
    (results_dir / "judgments.jsonl").write_text(
        "\n".join(json.dumps(v.to_dict()) for v in verdicts) + "\n", encoding="utf-8"
    )

    args = argparse.Namespace(force=False)
    rc = cli.cmd_audit_export(args)
    assert rc == 0

    manifest = json.loads((results_dir / "audit_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["mandatory"]) == 40  # capped, not 60

    audit_text = (results_dir / "audit.md").read_text(encoding="utf-8")
    assert "copertura parziale" in audit_text
    ticked = audit_text.replace("- [ ] vero", "- [x] vero")
    (results_dir / "audit.md").write_text(ticked, encoding="utf-8")

    rc = cli.cmd_audit_apply()
    assert rc == 0  # succeeds even though 20 of the 60 disagreements were never exported

    resolutions = json.loads((results_dir / "audit_resolutions.json").read_text(encoding="utf-8"))
    assert len(resolutions) == 40


def test_audit_apply_persists_partial_resolutions_even_when_blocked(tmp_path, monkeypatch):
    """Stage-level: a still-BLOCKED apply must not discard the resolutions
    the human already ticked."""
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)
    results_dir.mkdir(parents=True)

    manifest = {"mandatory": ["T1--MCP--CRITERION--C-001", "T2--MCP--CRITERION--C-001"], "optional": []}
    (results_dir / "audit_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    audit_md = (
        "## T1--MCP--CRITERION--C-001\n\n- [x] vero\n- [ ] falso\n\n"
        "## T2--MCP--CRITERION--C-001\n\n- [ ] vero\n- [ ] falso\n"
    )
    (results_dir / "audit.md").write_text(audit_md, encoding="utf-8")

    rc = cli.cmd_audit_apply()
    assert rc == 1

    resolutions = json.loads((results_dir / "audit_resolutions.json").read_text(encoding="utf-8"))
    assert resolutions == {"T1--MCP--CRITERION--C-001": True}


# --- CRITICAL 3: errored runs must be excluded from judging and scoring ----


def _errored_record(task_id="T1", arm="mcp", error="timeout after 900s") -> RunRecord:
    return RunRecord(
        task_id=task_id, arm=arm, model="m", answer="",
        tool_calls=[], num_turns=0, duration_ms=1, usage={}, error=error,
    )


def test_excluded_error_runs_splits_by_error_presence():
    clean = _run_record("T1", "bare")
    errored = _errored_record("T2", "mcp")
    pairs, excluded = _excluded_error_runs([clean, errored])
    assert pairs == [("T1", "bare")]
    assert excluded == {"mcp": 1}


def test_excluded_error_runs_counts_multiple_per_arm():
    records = [_errored_record("T1", "mcp"), _errored_record("T2", "mcp"), _run_record("T3", "bare")]
    pairs, excluded = _excluded_error_runs(records)
    assert pairs == [("T3", "bare")]
    assert excluded == {"mcp": 2}


def test_judge_excludes_errored_records_through_the_stage(tmp_path, monkeypatch):
    """Stage-level (IMPORTANT 9c): an errored run must never be judged."""
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")

    results_dir.mkdir(parents=True)
    clean = RunRecord(
        task_id="T1", arm="bare", model="m", answer="Risposta pulita senza citazioni.",
        tool_calls=[], num_turns=1, duration_ms=1, usage={}, error=None,
    )
    errored = _errored_record("T1", "mcp")
    (results_dir / "runs.jsonl").write_text(
        json.dumps(clean.to_dict()) + "\n" + json.dumps(errored.to_dict()) + "\n", encoding="utf-8"
    )

    def fake_plain_call(prompt, model, max_turns=1):
        return json.dumps({"verdicts": [{"criterion_id": "C-001", "verdict": True, "reasoning": "ok"}]})

    monkeypatch.setattr(cli, "_plain_claude_call", fake_plain_call)

    rc = cli.cmd_judge()
    assert rc == 0

    verdicts, _ = _load_jsonl(results_dir / "judgments.jsonl", Verdict.from_dict)
    assert {(v.task_id, v.arm, v.judge) for v in verdicts} == {("T1", "bare", "A"), ("T1", "bare", "B")}


def test_score_excludes_errored_runs_and_reports_it(tmp_path, monkeypatch, capsys):
    """Stage-level: an errored run must not count toward any scored arm,
    and the exclusion must be visible in stdout, report.md and scores.json."""
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    task = _task_with("T1")
    save_tasks([task], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    clean = _run_record("T1", "bare")
    errored = _errored_record("T1", "mcp")
    (results_dir / "runs.jsonl").write_text(
        json.dumps(clean.to_dict()) + "\n" + json.dumps(errored.to_dict()) + "\n", encoding="utf-8"
    )

    verdicts = [
        Verdict(task_id="T1", arm="bare", criterion_id="C-001", judge="A", verdict=True, reasoning=""),
        Verdict(task_id="T1", arm="bare", criterion_id="C-001", judge="B", verdict=True, reasoning=""),
    ]
    (results_dir / "judgments.jsonl").write_text(
        "\n".join(json.dumps(v.to_dict()) for v in verdicts) + "\n", encoding="utf-8"
    )

    pending_citation = Citation(
        task_id="T1", arm="bare", index=0, raw="Cass. civ. n. 1/2025",
        identifiable=True, resolved=True, covers_issue=None,
    )
    (results_dir / "citations.json").write_text(
        json.dumps([pending_citation.to_dict()]), encoding="utf-8"
    )

    rc = cli.cmd_score()
    assert rc == 0

    out = capsys.readouterr().out
    assert "excluding" in out and "mcp" in out
    assert "pending grounding" in out

    scores = json.loads((results_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["excluded_error_runs_by_arm"] == {"mcp": 1}
    assert scores["pending_grounding_by_arm"] == {"bare": 1}
    assert "mcp" not in scores["arms"] or scores["arms"]["mcp"]["all_pass"] == 0.0

    report_text = (results_dir / "report.md").read_text(encoding="utf-8")
    assert "Note operative" in report_text
    assert "esclusi dallo scoring" in report_text


# --- Amendment A4: per-kind audit_error_rate --------------------------------


def test_score_reports_audit_error_rate_by_kind(tmp_path, monkeypatch):
    """A synthetic audited-agreement re-check on a criterion overturns the
    panel; no grounding item was ever audited, so 'grounding' must be null
    (fail-closed), never 0.0."""
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    clean = _run_record("T1", "bare")
    (results_dir / "runs.jsonl").write_text(json.dumps(clean.to_dict()) + "\n", encoding="utf-8")

    # Both judges agreed C-001 = True.
    verdicts = [
        Verdict(task_id="T1", arm="bare", criterion_id="C-001", judge="A", verdict=True, reasoning=""),
        Verdict(task_id="T1", arm="bare", criterion_id="C-001", judge="B", verdict=True, reasoning=""),
    ]
    (results_dir / "judgments.jsonl").write_text(
        "\n".join(json.dumps(v.to_dict()) for v in verdicts) + "\n", encoding="utf-8"
    )

    # Human audit re-checked the agreement-stratum criterion and overturned it.
    audit_id = _audit_id("criterion", "T1", "bare", "C-001")
    (results_dir / "audit_resolutions.json").write_text(
        json.dumps({audit_id: False}), encoding="utf-8"
    )

    rc = cli.cmd_score()
    assert rc == 0

    scores = json.loads((results_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["audit_error_rate_by_kind"] == {"criterion": 1.0, "grounding": None}
    # Pooled rate is unaffected by the new breakdown.
    assert scores["audit_error_rate"] == 1.0


def test_score_audit_error_rate_by_kind_is_null_when_nothing_audited(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    clean = _run_record("T1", "bare")
    (results_dir / "runs.jsonl").write_text(json.dumps(clean.to_dict()) + "\n", encoding="utf-8")

    rc = cli.cmd_score()
    assert rc == 0

    scores = json.loads((results_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["audit_error_rate_by_kind"] == {"criterion": None, "grounding": None}
    # I2/I6: never measured means null, and n=0 items were audited.
    assert scores["audit_error_rate"] is None
    assert scores["audited_agreement"] == 0
    assert scores["audited_by_kind"] == {"criterion": 0, "grounding": 0}


# --- Final-review fix I6: audited_agreement / audited_by_kind sample size -


def test_score_reports_audited_agreement_total_and_by_kind(tmp_path, monkeypatch):
    """README Limitations #6 tells a reader to compute a binomial CI 'from
    the reported n' -- scores.json must actually report that n:
    `audited_agreement` (total across both verdict kinds) and
    `audited_by_kind` (criterion/grounding split), plus the same total
    surfaced in the report's reliability line.
    """
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    clean = _run_record("T1", "bare")
    (results_dir / "runs.jsonl").write_text(json.dumps(clean.to_dict()) + "\n", encoding="utf-8")

    # Both judges agreed C-001 = True (a criterion agreement-stratum item).
    verdicts = [
        _v("T1", "bare", "C-001", "A", True),
        _v("T1", "bare", "C-001", "B", True),
    ]
    (results_dir / "judgments.jsonl").write_text(
        "\n".join(json.dumps(v.to_dict()) for v in verdicts) + "\n", encoding="utf-8"
    )

    # Both judges agreed the citation covers the issue (a grounding
    # agreement-stratum item).
    grounding_rows = [
        {"task_id": "T1", "arm": "bare", "index": 0, "judge": "A", "covers": True, "reasoning": ""},
        {"task_id": "T1", "arm": "bare", "index": 0, "judge": "B", "covers": True, "reasoning": ""},
    ]
    (results_dir / "grounding.jsonl").write_text(
        "\n".join(json.dumps(r) for r in grounding_rows) + "\n", encoding="utf-8"
    )

    # Human audit re-checked BOTH agreement-stratum items and confirmed both.
    resolutions = {
        _audit_id("criterion", "T1", "bare", "C-001"): True,
        _audit_id("grounding", "T1", "bare", "0"): True,
    }
    (results_dir / "audit_resolutions.json").write_text(json.dumps(resolutions), encoding="utf-8")

    rc = cli.cmd_score()
    assert rc == 0

    scores = json.loads((results_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["audited_agreement"] == 2
    assert scores["audited_by_kind"] == {"criterion": 1, "grounding": 1}
    assert scores["audit_error_rate"] == 0.0  # both confirmed, neither overturned

    report_text = (results_dir / "report.md").read_text(encoding="utf-8")
    assert "2 accordi auditati" in report_text


# --- Amendment A2: paired McNemar comparisons + grounding kappa in scores --


def _mdd_task_with(task_id: str, *, required=("C-001",)) -> Task:
    criteria = [Criterion(id=cid, text=cid, required=True) for cid in required]
    return Task(
        id=task_id, track="mdd", domain="civil", query="q", criteria=criteria,
        issue_status=None, issue_summary="", seed_citation=None,
        builder_confidence="high", curated=True,
    )


def test_score_writes_paired_comparisons_and_grounding_kappa(tmp_path, monkeypatch):
    """Stage-level, hand-computed: two jurisprudential tasks (J1, J2) and one
    MDD task (M1), run through `bare` and `mcp` only -- `web` never ran, so
    every comparison involving it must show pairable=0 and p_value=None,
    proving the survivor-intersection pairing (not a fixed task list) drives
    the count. bare/mcp diverge by design so every metric has a hand-checked
    non-trivial McNemar table; grounding.jsonl is built so kappa comes out
    to exactly 0.0 by hand computation (see inline comments).
    """
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    tasks = [
        _task_with("J1", required=("C-001",)),
        _task_with("J2", required=("C-001",)),
        _mdd_task_with("M1", required=("C-001",)),
    ]
    save_tasks(tasks, data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    # --- runs: bare and mcp only, web never ran ---
    runs = [
        _run_record("J1", "bare"), _run_record("J2", "bare"), _run_record("M1", "bare"),
        _run_record("J1", "mcp"), _run_record("J2", "mcp"), _run_record("M1", "mcp"),
    ]
    (results_dir / "runs.jsonl").write_text(
        "\n".join(json.dumps(r.to_dict()) for r in runs) + "\n", encoding="utf-8"
    )

    # --- judgments: both judges agree on every required criterion (no audit
    # needed). bare passes J1, J2, M1; mcp passes J1 only, fails J2 and M1.
    def _agree(task_id, arm, verdict):
        return [
            _v(task_id, arm, "C-001", "A", verdict),
            _v(task_id, arm, "C-001", "B", verdict),
        ]

    verdicts = (
        _agree("J1", "bare", True) + _agree("J2", "bare", True) + _agree("M1", "bare", True)
        + _agree("J1", "mcp", True) + _agree("J2", "mcp", False) + _agree("M1", "mcp", False)
    )
    (results_dir / "judgments.jsonl").write_text(
        "\n".join(json.dumps(v.to_dict()) for v in verdicts) + "\n", encoding="utf-8"
    )

    # --- citations (jurisprudential only): bare covers J1 not J2, mcp covers
    # J2 not J1 -- a perfect swap, so gog_coverage bare-vs-mcp is b=1, c=1.
    citations = [
        _citation("J1", "bare", 0, grounded=True),
        _citation("J2", "bare", 0, grounded=False),
        _citation("J1", "mcp", 0, grounded=False),
        _citation("J2", "mcp", 0, grounded=True),
    ]
    (results_dir / "citations.json").write_text(
        json.dumps([c.to_dict() for c in citations]), encoding="utf-8"
    )

    # --- grounding.jsonl: raw per-judge covers verdicts backing a hand-
    # computed kappa of exactly 0.0. Sorted pairing order is (J1,bare),
    # (J1,mcp), (J2,bare), (J2,mcp): a=[T,T,F,F], b=[T,F,F,T] -> po=2/4=0.5,
    # p_a(T)=p_b(T)=0.5 -> pe=0.5 -> kappa=(0.5-0.5)/0.5=0.0.
    grounding_rows = [
        {"task_id": "J1", "arm": "bare", "index": 0, "judge": "A", "covers": True, "reasoning": ""},
        {"task_id": "J1", "arm": "bare", "index": 0, "judge": "B", "covers": True, "reasoning": ""},
        {"task_id": "J1", "arm": "mcp", "index": 0, "judge": "A", "covers": True, "reasoning": ""},
        {"task_id": "J1", "arm": "mcp", "index": 0, "judge": "B", "covers": False, "reasoning": ""},
        {"task_id": "J2", "arm": "bare", "index": 0, "judge": "A", "covers": False, "reasoning": ""},
        {"task_id": "J2", "arm": "bare", "index": 0, "judge": "B", "covers": False, "reasoning": ""},
        {"task_id": "J2", "arm": "mcp", "index": 0, "judge": "A", "covers": False, "reasoning": ""},
        {"task_id": "J2", "arm": "mcp", "index": 0, "judge": "B", "covers": True, "reasoning": ""},
    ]
    (results_dir / "grounding.jsonl").write_text(
        "\n".join(json.dumps(r) for r in grounding_rows) + "\n", encoding="utf-8"
    )

    rc = cli.cmd_score()
    assert rc == 0

    scores = json.loads((results_dir / "scores.json").read_text(encoding="utf-8"))

    assert scores["grounding_kappa"] == pytest.approx(0.0)

    paired = scores["paired_comparisons"]
    # Three original arms + the two plugin arms: every unordered pair gets a
    # comparison entry, whether or not either side ever ran.
    assert set(paired) == {
        "bare_vs_web", "bare_vs_mcp", "web_vs_mcp",
        "bare_vs_plugin-v2", "bare_vs_plugin-v3", "web_vs_plugin-v2",
        "web_vs_plugin-v3", "mcp_vs_plugin-v2", "mcp_vs_plugin-v3",
        "plugin-v2_vs_plugin-v3",
    }
    for key in paired:
        assert set(paired[key]) == {"jurisprudential_all_pass", "mdd_pass", "gog_coverage"}

    # web never ran: every web-involving comparison is fully unpaired.
    for pair_key in ("bare_vs_web", "web_vs_mcp"):
        for track in ("jurisprudential_all_pass", "mdd_pass", "gog_coverage"):
            entry = paired[pair_key][track]
            assert entry == {"b": 0, "c": 0, "discordant": 0, "p_value": None, "pairable": 0}

    # The plugin arms never ran either: every comparison involving one is
    # fully unpaired (pairable=0, p undefined) — absence of evidence rendered
    # as null, never as a confirmed zero difference.
    for pair_key in (
        "bare_vs_plugin-v2", "bare_vs_plugin-v3", "web_vs_plugin-v2",
        "web_vs_plugin-v3", "mcp_vs_plugin-v2", "mcp_vs_plugin-v3",
        "plugin-v2_vs_plugin-v3",
    ):
        for track in ("jurisprudential_all_pass", "mdd_pass", "gog_coverage"):
            entry = paired[pair_key][track]
            assert entry == {"b": 0, "c": 0, "discordant": 0, "p_value": None, "pairable": 0}

    # bare vs mcp, jurisprudential all-pass: J1 concordant (True/True), J2
    # discordant bare=True/mcp=False -> b=1, c=0, n=1 -> p=1.0 (n=1 always).
    jap = paired["bare_vs_mcp"]["jurisprudential_all_pass"]
    assert jap == {"b": 1, "c": 0, "discordant": 1, "p_value": pytest.approx(1.0), "pairable": 2}

    # bare vs mcp, MDD pass: M1 discordant bare=True/mcp=False -> b=1, c=0,
    # n=1 -> p=1.0.
    mdd = paired["bare_vs_mcp"]["mdd_pass"]
    assert mdd == {"b": 1, "c": 0, "discordant": 1, "p_value": pytest.approx(1.0), "pairable": 1}

    # bare vs mcp, GOG coverage: J1 bare=True/mcp=False (b+=1), J2
    # bare=False/mcp=True (c+=1) -> b=1, c=1, n=2 -> p capped at 1.0.
    cov = paired["bare_vs_mcp"]["gog_coverage"]
    assert cov == {"b": 1, "c": 1, "discordant": 2, "p_value": pytest.approx(1.0), "pairable": 2}


def test_score_grounding_kappa_is_null_when_no_grounding_verdicts(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    clean = _run_record("T1", "bare")
    (results_dir / "runs.jsonl").write_text(json.dumps(clean.to_dict()) + "\n", encoding="utf-8")

    rc = cli.cmd_score()
    assert rc == 0

    scores = json.loads((results_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["grounding_kappa"] is None


def _reject_nan_token(token: str):
    raise ValueError(f"scores.json contains a non-JSON constant token: {token!r}")


def test_score_criteria_kappa_is_null_and_scores_json_has_no_nan_when_no_judgments(tmp_path, monkeypatch):
    """Code-review fix: `cohens_kappa(pa, pb)` was unguarded in cmd_score, so
    a run with no judgments at all (pa=pb=[]) wrote the literal `NaN` token
    into scores.json -- invalid JSON, and "**nan**" in the rendered report.
    Mirror the grounding_kappa guard: None (json null) when there is
    nothing paired to measure agreement over.

    The judge panel is entirely absent here (no judgments.jsonl), but every
    required criterion is instead resolved directly by human audit override
    (`audit_resolutions.json`) for all three arms -- a legitimate pipeline
    state (e.g. a resumed run whose judge stage never completed) that keeps
    every arm's per-task pass values non-degenerate. This isolates the
    exact defect under test (`kappa` from zero PAIRED JUDGE verdicts) from
    the unrelated, pre-existing `bootstrap_ci([])` -> NaN behaviour that an
    arm with literally zero surviving tasks would otherwise also trigger --
    that behaviour is intentional (pinned by
    `test_bootstrap_ci_of_empty_sample_is_nan` in metrics.py) and out of
    scope for this fix.
    """
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    runs = [_run_record("T1", "bare"), _run_record("T1", "web"), _run_record("T1", "mcp")]
    (results_dir / "runs.jsonl").write_text(
        "\n".join(json.dumps(r.to_dict()) for r in runs) + "\n", encoding="utf-8"
    )
    # No judgments.jsonl at all -> verdicts_a == verdicts_b == [] -> kappa's
    # pairing is empty regardless of arm. Every task/arm is instead resolved
    # straight through human audit, so drop_incomplete keeps all three arms.
    resolutions = {
        _audit_id("criterion", "T1", arm, "C-001"): True for arm in ("bare", "web", "mcp")
    }
    (results_dir / "audit_resolutions.json").write_text(json.dumps(resolutions), encoding="utf-8")

    rc = cli.cmd_score()
    assert rc == 0

    raw_text = (results_dir / "scores.json").read_text(encoding="utf-8")
    # json.loads accepts the bare `NaN` token by default (Python extension,
    # not valid JSON) unless a `parse_constant` hook is supplied to reject
    # it -- this is the actual regression check, not just "kappa is None".
    scores = json.loads(raw_text, parse_constant=_reject_nan_token)
    assert scores["kappa"] is None
    assert scores["grounding_kappa"] is None
    # Sanity on the arms that actually ran: real data, not a degenerate arm.
    # The plugin arms have no run record at all here — they appear in
    # scores["arms"] with n_jur=0 (the never-run shape, whose null-CI
    # rendering is pinned by test_score_zero_survivor_arm_reports_null_cis_not_nan).
    for arm, r in scores["arms"].items():
        if r["n_jur"]:
            assert r["all_pass"] == pytest.approx(1.0), arm
    assert scores["arms"]["plugin-v2"]["n_jur"] == 0
    assert scores["arms"]["plugin-v3"]["n_jur"] == 0

    report_text = (results_dir / "report.md").read_text(encoding="utf-8")
    assert "nan" not in report_text.lower()
    assert "n/d" in report_text


# --- Final-review fix I3: zero-survivor arm must report null CIs, never --
# --- the NaN pair bootstrap_ci([]) produces, and must carry a visible N --
# --- so a never-run arm reads differently from a zero-scoring one       --


def test_score_zero_survivor_arm_reports_null_cis_not_nan(tmp_path, monkeypatch):
    """`web` and `mcp` never ran at all -- only `bare` did. Before the fix,
    `bootstrap_ci([])` was called unconditionally for every arm and wrote
    the literal `NaN` token into scores.json for the two never-run arms
    (invalid JSON) and rendered the meaningless "nan" in report.md. After
    the fix, an arm with zero surviving jurisprudential tasks reports
    `all_pass_ci`/`gog_ci` as JSON null (never NaN) and `n_jur: 0`, so a
    never-run arm is visibly distinct from an arm that ran and scored zero.
    """
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    # Only `bare` ran -- `web` and `mcp` have no run record at all.
    (results_dir / "runs.jsonl").write_text(
        json.dumps(_run_record("T1", "bare").to_dict()) + "\n", encoding="utf-8"
    )
    verdicts = [
        _v("T1", "bare", "C-001", "A", True),
        _v("T1", "bare", "C-001", "B", True),
    ]
    (results_dir / "judgments.jsonl").write_text(
        "\n".join(json.dumps(v.to_dict()) for v in verdicts) + "\n", encoding="utf-8"
    )

    rc = cli.cmd_score()
    assert rc == 0

    raw_text = (results_dir / "scores.json").read_text(encoding="utf-8")
    # Strict: json.loads accepts the bare `NaN`/`Infinity` tokens by default
    # (a Python extension, not valid JSON) unless `parse_constant` rejects
    # them -- this is the actual regression check, not just "is None".
    scores = json.loads(raw_text, parse_constant=_reject_nan_token)

    for arm in ("web", "mcp"):
        assert scores["arms"][arm]["all_pass_ci"] is None
        assert scores["arms"][arm]["gog_ci"] is None
        assert scores["arms"][arm]["n_jur"] == 0
        assert scores["arms"][arm]["n_mdd"] == 0

    # Sanity: the arm that actually ran keeps a real CI, not collateral null.
    assert scores["arms"]["bare"]["all_pass_ci"] is not None
    assert scores["arms"]["bare"]["n_jur"] == 1

    report_text = (results_dir / "report.md").read_text(encoding="utf-8")
    assert "nan" not in report_text.lower()
    assert "n/d" in report_text
    assert "| `web` | 0 |" in report_text  # N column makes the never-run arm visible
    assert "| `mcp` | 0 |" in report_text


# --- IMPORTANT 4: citation resolution must be cached and never downgraded --


def test_judge_caches_citation_resolution_and_never_downgrades(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    record = RunRecord(
        task_id="T1", arm="mcp", model="m",
        answer="Come stabilito da Cass. civ. n. 123/2025, la responsabilita e del committente.",
        tool_calls=[], num_turns=1, duration_ms=1, usage={}, error=None,
    )
    (results_dir / "runs.jsonl").write_text(json.dumps(record.to_dict()) + "\n", encoding="utf-8")

    def fake_plain_call(prompt, model, max_turns=1):
        if "CITAZIONE PRODOTTA" in prompt:
            return json.dumps({"covers": True, "reasoning": "ok"})
        return json.dumps({"verdicts": [{"criterion_id": "C-001", "verdict": True, "reasoning": "ok"}]})

    monkeypatch.setattr(cli, "_plain_claude_call", fake_plain_call)

    resolve_calls = []

    async def fake_resolve_citations(citations):
        from benchmarks.legalita.score.resolve import apply_resolution

        resolve_calls.append(len(citations))
        report = "\n".join(
            f"| 1 | x | Sentenza | verificata | Cass. n. {c.parsed['number']}/{c.parsed['year']} reperita. |"
            for c in citations
            if c.identifiable and c.parsed
        )
        return apply_resolution(citations, report)

    monkeypatch.setattr(cli, "resolve_citations", fake_resolve_citations)

    rc = cli.cmd_judge()
    assert rc == 0
    assert resolve_calls == [1]

    citations = json.loads((results_dir / "citations.json").read_text(encoding="utf-8"))
    assert citations[0]["resolved"] is True

    cached = json.loads((results_dir / "resolutions.jsonl").read_text(encoding="utf-8").strip())
    assert cached["resolved"] is True

    async def raising_resolve_citations(citations):
        raise AssertionError("resolve_citations must not be called for an already-cached citation")

    monkeypatch.setattr(cli, "resolve_citations", raising_resolve_citations)

    rc2 = cli.cmd_judge()
    assert rc2 == 0

    citations2 = json.loads((results_dir / "citations.json").read_text(encoding="utf-8"))
    assert citations2[0]["resolved"] is True  # never downgraded by the (unreached) second call


# --- IMPORTANT 5: unpaired grounding verdicts must be dropped, not raise ---


def test_grounding_agreed_and_disagreements_drops_unpaired_rows(tmp_path, capsys):
    path = tmp_path / "grounding.jsonl"
    rows = [
        {"task_id": "T1", "arm": "mcp", "index": 0, "judge": "A", "covers": True, "reasoning": ""},
        {"task_id": "T1", "arm": "mcp", "index": 0, "judge": "B", "covers": True, "reasoning": ""},
        {"task_id": "T2", "arm": "mcp", "index": 0, "judge": "A", "covers": True, "reasoning": ""},
        # No judge B row for T2 -- unpaired, must not make reconcile raise.
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    agreed, disagreements, va, vb, unpaired = _grounding_agreed_and_disagreements(path)
    assert agreed == {("T1", "mcp", "0"): True}
    assert disagreements == []
    assert unpaired == 1
    assert "unpaired" in capsys.readouterr().out


def test_grounding_agreed_and_disagreements_empty_file_is_a_no_op(tmp_path):
    path = tmp_path / "grounding.jsonl"
    agreed, disagreements, va, vb, unpaired = _grounding_agreed_and_disagreements(path)
    assert (agreed, disagreements, va, vb, unpaired) == ({}, [], [], [], 0)


# --- Final-review fix I4: criteria-side unpaired verdicts, mirroring the ---
# --- grounding-side tolerance above, must not permanently block the      ---
# --- pipeline either.                                                    ---


def test_criteria_agreed_and_disagreements_drops_unpaired_rows(tmp_path, capsys):
    path = tmp_path / "judgments.jsonl"
    verdicts = [
        _v("T1", "bare", "C-001", "A", True),
        _v("T1", "bare", "C-001", "B", True),
        _v("T2", "bare", "C-001", "A", True),
        # No judge B verdict for T2 -- unpaired, must not make reconcile raise.
    ]
    path.write_text("\n".join(json.dumps(v.to_dict()) for v in verdicts) + "\n", encoding="utf-8")

    agreed, disagreements, va, vb, unpaired = cli._criteria_agreed_and_disagreements(path)
    assert agreed == {("T1", "bare", "C-001"): True}
    assert disagreements == []
    assert unpaired == 1
    assert "unpaired" in capsys.readouterr().out


def test_audit_export_and_score_survive_an_unpaired_criterion_verdict(tmp_path, monkeypatch, capsys):
    """The exact failure mode fixed by I4: judge A answered a criterion,
    judge B never did (failed call, or a resumed pipeline caught between
    the two judge calls). Before the fix, `reconcile()`'s hard `JudgeError`
    on any key mismatch made this permanently block both `audit-export` and
    `score`. After the fix, both stages succeed, print a warning, and the
    affected (task, arm) pair falls out through `drop_incomplete`'s
    unresolved accounting -- exactly like a real judge disagreement would.
    """
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("T1")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    (results_dir / "runs.jsonl").write_text(
        json.dumps(_run_record("T1", "bare").to_dict()) + "\n", encoding="utf-8"
    )
    # Judge A only -- judge B never answered for this (task, arm, criterion).
    only_a = _v("T1", "bare", "C-001", "A", True)
    (results_dir / "judgments.jsonl").write_text(
        json.dumps(only_a.to_dict()) + "\n", encoding="utf-8"
    )

    rc_export = cli.cmd_audit_export(argparse.Namespace(force=False))
    export_out = capsys.readouterr().out
    assert rc_export == 0
    assert "unpaired" in export_out

    manifest = json.loads((results_dir / "audit_manifest.json").read_text(encoding="utf-8"))
    assert manifest == {"mandatory": [], "optional": []}  # nothing to reconcile, nothing to audit

    rc_score = cli.cmd_score()
    score_out = capsys.readouterr().out
    assert rc_score == 0
    assert "unpaired" in score_out

    scores = json.loads((results_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["unresolved_criteria_pairs"] == 1  # T1/bare dropped, criterion never resolved
    assert scores["arms"]["bare"]["all_pass"] == 0.0
    assert scores["arms"]["bare"]["n_jur"] == 0


# --- IMPORTANT 6: pending grounding verdicts must be counted, not silent --


def test_pending_grounding_by_arm_counts_resolved_but_ungrounded_citations():
    c1 = Citation(task_id="T1", arm="mcp", index=0, raw="x", identifiable=True, resolved=True, covers_issue=None)
    c2 = Citation(task_id="T1", arm="mcp", index=1, raw="y", identifiable=True, resolved=True, covers_issue=True)
    c3 = Citation(task_id="T2", arm="bare", index=0, raw="z", identifiable=False, resolved=False, covers_issue=None)
    assert _pending_grounding_by_arm([c1, c2, c3]) == {"mcp": 1}


def test_pending_grounding_by_arm_is_empty_when_everything_is_settled():
    c1 = Citation(task_id="T1", arm="mcp", index=0, raw="x", identifiable=True, resolved=True, covers_issue=True)
    c2 = Citation(task_id="T1", arm="mcp", index=1, raw="y", identifiable=True, resolved=False, covers_issue=None)
    assert _pending_grounding_by_arm([c1, c2]) == {}


# --- IMPORTANT 7: MDD seeds must load before any builder call --------------


def test_build_loads_mdd_seeds_before_any_builder_call(tmp_path, monkeypatch):
    """Stage-level (IMPORTANT 9d): a malformed mdd_seeds.json must fail
    before a single builder call is spent, and must exit non-zero."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)

    seeds = {
        "civil": [_decision(i) for i in range(13)],
        "labour": [_decision(100 + i) for i in range(8)],
        "tax": [_decision(200 + i) for i in range(9)],
    }
    save_seeds(seeds, data_dir / "seeds.json")
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "mdd_seeds.json").write_text(
        json.dumps([{"id": "MDD-001", "query": "x", "missing_documents": [], "domain": "civil"}]),
        encoding="utf-8",
    )

    calls = []

    def fake_plain_call(prompt, model, max_turns=1):
        calls.append(prompt)
        return "{}"

    monkeypatch.setattr(cli, "_plain_claude_call", fake_plain_call)

    args = argparse.Namespace(builder_model="opus", force=False)
    with pytest.raises(ValueError, match="missing_documents"):
        cli.cmd_build(args)

    assert calls == []  # no builder call was ever made


# --- IMPORTANT 8: review-export / audit-export must not clobber human work-


def _curated_review_task() -> Task:
    return Task(
        id="T1", track="jurisprudential", domain="civil", query="q",
        criteria=[Criterion(id="C-001", text="x", required=True)],
        issue_status="settled", issue_summary="", seed_citation=None,
        builder_confidence="low", curated=False,
    )


def test_review_export_refuses_to_overwrite_a_ticked_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    save_tasks([_curated_review_task()], data_dir / "tasks.json")

    review_path = data_dir / "review.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    original = "## T1\n\n- [x] approva\n- [ ] scarta\n"
    review_path.write_text(original, encoding="utf-8")

    rc = cli.cmd_review_export(argparse.Namespace(force=False))
    assert rc == 1
    assert review_path.read_text(encoding="utf-8") == original


def test_review_export_force_overwrites_a_ticked_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    save_tasks([_curated_review_task()], data_dir / "tasks.json")

    review_path = data_dir / "review.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text("## T1\n\n- [x] approva\n- [ ] scarta\n", encoding="utf-8")

    rc = cli.cmd_review_export(argparse.Namespace(force=True))
    assert rc == 0
    assert "**Quesito**" in review_path.read_text(encoding="utf-8")


def test_review_export_plain_reexport_over_untouched_file_is_allowed(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    save_tasks([_curated_review_task()], data_dir / "tasks.json")

    review_path = data_dir / "review.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text("# stale export, nothing ticked\n\n## T1\n\n- [ ] approva\n- [ ] scarta\n", encoding="utf-8")

    rc = cli.cmd_review_export(argparse.Namespace(force=False))
    assert rc == 0


def test_audit_export_refuses_to_overwrite_a_ticked_file(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)
    results_dir.mkdir(parents=True)

    audit_path = results_dir / "audit.md"
    original = "## T1--MCP--CRITERION--C-001\n\n- [x] vero\n- [ ] falso\n"
    audit_path.write_text(original, encoding="utf-8")

    rc = cli.cmd_audit_export(argparse.Namespace(force=False))
    assert rc == 1
    assert audit_path.read_text(encoding="utf-8") == original
    assert not (results_dir / "audit_manifest.json").exists()


def test_audit_export_force_overwrites_a_ticked_file(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)
    results_dir.mkdir(parents=True)

    audit_path = results_dir / "audit.md"
    audit_path.write_text("## T1--MCP--CRITERION--C-001\n\n- [x] vero\n- [ ] falso\n", encoding="utf-8")

    rc = cli.cmd_audit_export(argparse.Namespace(force=True))
    assert rc == 0
    assert (results_dir / "audit_manifest.json").exists()


def test_audit_export_plain_reexport_over_untouched_file_is_allowed(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)
    results_dir.mkdir(parents=True)

    audit_path = results_dir / "audit.md"
    audit_path.write_text("# stale, nothing ticked\n", encoding="utf-8")

    rc = cli.cmd_audit_export(argparse.Namespace(force=False))
    assert rc == 0


# --- Final-review fix I5: `build` must not clobber curated tasks.json -----


def test_build_refuses_to_overwrite_tasks_json_containing_curated_tasks_without_force(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    save_tasks([_task_with("T1")], data_dir / "tasks.json")  # curated=True by default
    original = (data_dir / "tasks.json").read_text(encoding="utf-8")

    calls = []
    monkeypatch.setattr(cli, "_plain_claude_call", lambda *a, **k: calls.append(1) or "{}")

    rc = cli.cmd_build(argparse.Namespace(builder_model="opus", force=False))
    assert rc == 1
    assert (data_dir / "tasks.json").read_text(encoding="utf-8") == original
    assert calls == []  # no builder call was ever made


def test_build_force_bypasses_the_curated_guard(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    save_tasks([_task_with("T1")], data_dir / "tasks.json")  # curated=True by default
    # Deliberately short seed mix: with --force the guard must be skipped
    # and control must reach the (separate, later) domain-quota shortfall
    # check -- proven by "BLOCKED" (shortfall), never "REFUSED" (the guard
    # this test targets), appearing in stdout.
    save_seeds({"civil": [], "labour": [], "tax": []}, data_dir / "seeds.json")

    rc = cli.cmd_build(argparse.Namespace(builder_model="opus", force=True))
    out = capsys.readouterr().out
    assert rc == 1
    assert "BLOCKED" in out
    assert "REFUSED" not in out


def test_build_guard_does_not_fire_on_a_fresh_tasks_json(tmp_path, monkeypatch, capsys):
    """A first-time build (no tasks.json yet) must never hit the curated
    guard, force or not -- there is nothing to clobber."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    assert not (data_dir / "tasks.json").exists()
    save_seeds({"civil": [], "labour": [], "tax": []}, data_dir / "seeds.json")

    rc = cli.cmd_build(argparse.Namespace(builder_model="opus", force=False))
    out = capsys.readouterr().out
    assert rc == 1
    assert "BLOCKED" in out
    assert "REFUSED" not in out


# --- Amendment A3: grounding stability repeats (pass^k subset) -------------


def test_stability_subset_is_deterministic_regardless_of_input_order():
    ids = [f"JUR-CIV-{i:03d}" for i in range(1, 21)]
    first = stability_subset(ids, k=10, seed=20250107)
    second = stability_subset(list(reversed(ids)), k=10, seed=20250107)
    assert first == second
    assert first == sorted(first)
    assert len(first) == 10


def test_stability_subset_is_a_subset_of_the_input_pool():
    ids = [f"JUR-CIV-{i:03d}" for i in range(1, 21)]
    result = stability_subset(ids, k=10, seed=20250107)
    assert set(result) <= set(ids)


def test_stability_subset_takes_all_when_pool_is_smaller_than_k():
    ids = ["JUR-CIV-002", "JUR-CIV-001"]
    result = stability_subset(ids, k=10, seed=20250107)
    assert result == ["JUR-CIV-001", "JUR-CIV-002"]


def test_stability_subset_different_seed_can_change_the_draw():
    ids = [f"JUR-CIV-{i:03d}" for i in range(1, 21)]
    a = stability_subset(ids, k=10, seed=1)
    b = stability_subset(ids, k=10, seed=2)
    assert a != b  # extremely unlikely to collide by chance with a real RNG


def test_stability_task_entry_is_null_when_no_repeat_is_usable():
    assert _stability_task_entry({}) == {"resolved_counts": None, "covered": None}


def test_stability_task_entry_orders_by_repeat_id_and_marks_coverage():
    entry = _stability_task_entry({3: 0, 1: 2})
    assert entry == {"resolved_counts": [2, 0], "covered": [True, False]}


def test_stability_arm_metrics_hand_computed_fixture():
    """T1: all 3 repeats usable, all covered -> spread 2-1=1.
    T2: repeat 2 excluded (errored), repeats 1 and 3 usable, only one
    covered -> spread 1-0=1.
    T3: every repeat errored -> zero usable repeats, excluded from the
    aggregates entirely and reported in tasks_without_usable_repeats.

    Hand computation:
        usable tasks = {T1, T2}  (T3 excluded)
        coverage_all_k = 1/2 = 0.5   (only T1 covered in ALL its usable repeats)
        coverage_any_k = 2/2 = 1.0   (both T1 and T2 have >=1 covered repeat)
        mean_citation_spread = mean([1, 1]) = 1.0
    """
    task_entries = {
        "T1": _stability_task_entry({1: 2, 2: 1, 3: 2}),
        "T2": _stability_task_entry({1: 0, 3: 1}),
        "T3": _stability_task_entry({}),
    }
    metrics = _stability_arm_metrics(task_entries)
    assert metrics["coverage_all_k"] == 0.5
    assert metrics["coverage_any_k"] == 1.0
    assert metrics["mean_citation_spread"] == 1.0
    assert metrics["tasks_without_usable_repeats"] == ["T3"]


def test_stability_arm_metrics_is_null_when_nothing_is_usable():
    task_entries = {"T1": _stability_task_entry({}), "T2": _stability_task_entry({})}
    metrics = _stability_arm_metrics(task_entries)
    assert metrics["coverage_all_k"] is None
    assert metrics["coverage_any_k"] is None
    assert metrics["mean_citation_spread"] is None
    assert metrics["tasks_without_usable_repeats"] == ["T1", "T2"]


def test_stability_refuses_without_a_curated_task_set(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    uncurated = Task(
        id="JUR-CIV-001", track="jurisprudential", domain="civil", query="q",
        criteria=[Criterion(id="C-001", text="x", required=True)],
        issue_status="settled", issue_summary="", seed_citation=None,
        builder_confidence="low", curated=False,
    )
    save_tasks([uncurated], data_dir / "tasks.json")

    args = argparse.Namespace(model="opus", max_turns=12)
    rc = cli.cmd_stability(args)
    assert rc == 1
    assert "BLOCKED" in capsys.readouterr().out
    assert not (results_dir / "stability_runs.jsonl").exists()


def test_stability_resumability_only_runs_missing_triples(tmp_path, monkeypatch):
    """2 (task, arm, repeat) triples are pre-seeded as done; with 2 tasks x
    2 arms x 3 repeats = 12 total triples, only the missing 10 must trigger
    a `run_arm` call."""
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("JUR-CIV-001"), _task_with("JUR-CIV-002")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    runs_path = results_dir / "stability_runs.jsonl"
    seeded = [
        {**_run_record("JUR-CIV-001", "bare").to_dict(), "repeat": 1},
        {**_run_record("JUR-CIV-002", "mcp").to_dict(), "repeat": 2},
    ]
    runs_path.write_text("\n".join(json.dumps(d) for d in seeded) + "\n", encoding="utf-8")

    calls = []

    def fake_run_arm(task, arm, workdir, plugin_root, model, max_turns):
        calls.append((task.id, arm))
        return _run_record(task.id, arm)  # answer "a" -- no citations, no live resolve call

    monkeypatch.setattr(cli.arms, "run_arm", fake_run_arm)

    args = argparse.Namespace(model="opus", max_turns=12)
    rc = cli.cmd_stability(args)
    assert rc == 0
    assert len(calls) == 10

    all_records, skipped = _load_jsonl(runs_path, lambda d: d)
    assert skipped == 0
    triples = {(d["task_id"], d["arm"], d["repeat"]) for d in all_records}
    assert len(triples) == 12
    assert ("JUR-CIV-001", "bare", 1) in triples
    assert ("JUR-CIV-002", "mcp", 2) in triples

    # A second invocation with nothing missing must call run_arm zero times.
    calls.clear()
    rc2 = cli.cmd_stability(args)
    assert rc2 == 0
    assert calls == []


def test_stability_excludes_errored_repeats_from_metrics_but_keeps_them_in_the_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("JUR-CIV-001")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    def fake_run_arm(task, arm, workdir, plugin_root, model, max_turns):
        if arm == "mcp":
            return RunRecord(
                task_id=task.id, arm=arm, model="m", answer="",
                tool_calls=[], num_turns=0, duration_ms=1, usage={},
                error="timeout after 900s",
            )
        return RunRecord(
            task_id=task.id, arm=arm, model="m",
            answer="Cass. civ. n. 123/2025 conferma quanto sostenuto.",
            tool_calls=[], num_turns=1, duration_ms=1, usage={}, error=None,
        )

    monkeypatch.setattr(cli.arms, "run_arm", fake_run_arm)

    async def fake_resolve_citations(citations):
        from benchmarks.legalita.score.resolve import apply_resolution

        report = "\n".join(
            f"Cass. sez. x n. {c.parsed['number']}/{c.parsed['year']} verificata."
            for c in citations
            if c.identifiable and c.parsed
        )
        return apply_resolution(citations, report)

    monkeypatch.setattr(cli, "resolve_citations", fake_resolve_citations)

    args = argparse.Namespace(model="opus", max_turns=12)
    rc = cli.cmd_stability(args)
    assert rc == 0

    # The file records every repeat, errored ones included.
    all_records, _ = _load_jsonl(results_dir / "stability_runs.jsonl", lambda d: d)
    mcp_records = [d for d in all_records if d["arm"] == "mcp"]
    assert len(mcp_records) == 3
    assert all(d["error"] is not None for d in mcp_records)

    stability = json.loads((results_dir / "stability.json").read_text(encoding="utf-8"))
    assert stability["excluded_error_runs"] == {"mcp": 3}
    # All 3 mcp repeats errored for this task -> zero usable repeats.
    assert stability["arms"]["mcp"]["tasks"]["JUR-CIV-001"]["resolved_counts"] is None
    assert stability["arms"]["mcp"]["tasks_without_usable_repeats"] == ["JUR-CIV-001"]
    # bare succeeded on all 3 repeats, one resolved citation each.
    assert stability["arms"]["bare"]["tasks"]["JUR-CIV-001"]["resolved_counts"] == [1, 1, 1]
    assert stability["arms"]["bare"]["tasks_without_usable_repeats"] == []


def test_stability_uses_a_dedicated_resolution_cache_never_touching_the_main_one(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_task_with("JUR-CIV-001")], data_dir / "tasks.json")
    results_dir.mkdir(parents=True)

    sentinel = {
        "task_id": "SENTINEL", "arm": "mcp", "index": 0,
        "resolved": True, "resolution_note": "pre-existing main-pipeline cache entry",
    }
    (results_dir / "resolutions.jsonl").write_text(json.dumps(sentinel) + "\n", encoding="utf-8")

    def fake_run_arm(task, arm, workdir, plugin_root, model, max_turns):
        return RunRecord(
            task_id=task.id, arm=arm, model="m",
            answer="Cass. civ. n. 123/2025 conferma quanto sostenuto.",
            tool_calls=[], num_turns=1, duration_ms=1, usage={}, error=None,
        )

    monkeypatch.setattr(cli.arms, "run_arm", fake_run_arm)

    resolve_call_sizes = []

    async def fake_resolve_citations(citations):
        from benchmarks.legalita.score.resolve import apply_resolution

        resolve_call_sizes.append(len(citations))
        report = "\n".join(
            f"Cass. sez. x n. {c.parsed['number']}/{c.parsed['year']} verificata."
            for c in citations
            if c.identifiable and c.parsed
        )
        return apply_resolution(citations, report)

    monkeypatch.setattr(cli, "resolve_citations", fake_resolve_citations)

    args = argparse.Namespace(model="opus", max_turns=12)
    rc = cli.cmd_stability(args)
    assert rc == 0

    # The main pipeline's cache is untouched -- still exactly the sentinel.
    main_lines = (results_dir / "resolutions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(main_lines) == 1
    assert json.loads(main_lines[0])["task_id"] == "SENTINEL"

    dedicated_path = results_dir / "stability_resolutions.jsonl"
    assert dedicated_path.exists()
    dedicated, _ = _load_jsonl(dedicated_path, lambda d: d)
    # 1 task x 2 arms x 3 repeats, one identifiable citation resolved each.
    assert len(dedicated) == 6
    assert all("repeat" in d for d in dedicated)
    assert all(d["resolved"] is True for d in dedicated)

    # Re-running must hit the dedicated cache, not call resolve_citations again.
    resolve_call_sizes.clear()

    async def raising_resolve_citations(citations):
        raise AssertionError("resolve_citations must not be called for already-cached repeats")

    monkeypatch.setattr(cli, "resolve_citations", raising_resolve_citations)
    rc2 = cli.cmd_stability(args)
    assert rc2 == 0
    stability = json.loads((results_dir / "stability.json").read_text(encoding="utf-8"))
    assert stability["arms"]["bare"]["tasks"]["JUR-CIV-001"]["resolved_counts"] == [1, 1, 1]


# =============================================================================
# Amendment A5: human leakage spot-check round trip
# =============================================================================


def _seed_citation(number: int, year: int = 2025, section: str = "II", court: str = "Cass. civ.") -> dict:
    return {"court": court, "section": section, "number": number, "year": year}


def _jur_task(
    task_id: str,
    *,
    query: str = "Quesito di test",
    seed_citation: dict | None = None,
    curated: bool = True,
    builder_confidence: str = "high",
) -> Task:
    return Task(
        id=task_id, track="jurisprudential", domain="civil", query=query,
        criteria=[Criterion(id="C-001", text="x", required=True)],
        issue_status="settled", issue_summary="", seed_citation=seed_citation,
        builder_confidence=builder_confidence, curated=curated,
    )


# --- Pure helpers: seed join and eligibility --------------------------------


def test_seed_index_flattens_across_domains():
    picked = {"civil": [_decision(1)], "labour": [_decision(2)]}
    index = cli._seed_index(picked)
    assert index == {(1, 2025): _decision(1), (2, 2025): _decision(2)}


def test_seed_key_reads_number_and_year_from_seed_citation():
    task = _jur_task("T1", seed_citation=_seed_citation(42, 2025))
    assert cli._seed_key(task) == (42, 2025)


def test_seed_key_is_unjoinable_for_a_missing_seed_citation():
    task = _jur_task("T1", seed_citation=None)
    assert cli._seed_key(task) == (None, None)


def test_leakage_eligible_tasks_filters_track_and_confidence():
    # Eligible: curated (regardless of confidence) or high-confidence.
    jur_curated_low_conf = _jur_task("J1", curated=True, builder_confidence="low")
    jur_uncurated_high_conf = _jur_task("J2", curated=False, builder_confidence="high")
    # Not eligible: neither curated nor high-confidence, and mdd track
    # (mdd tasks carry no seed decision and cannot leak one).
    jur_uncurated_low_conf = _jur_task("J3", curated=False, builder_confidence="low")
    mdd = _mdd_task_with("M1")
    result = cli._leakage_eligible_tasks([jur_curated_low_conf, jur_uncurated_high_conf, jur_uncurated_low_conf, mdd])
    assert {t.id for t in result} == {"J1", "J2"}


# --- export_leakage_markdown / parse_leakage_markdown: pure round trip -----


def test_export_leakage_markdown_contains_quesito_and_pronuncia_seme():
    decision = _decision(7)
    task = _jur_task(
        "JUR-CIV-001",
        query="Il termine di prescrizione decorre dalla scoperta del danno?",
        seed_citation=_seed_citation(7),
    )
    text = export_leakage_markdown([task], {(7, 2025): decision})
    assert "## JUR-CIV-001" in text
    assert "**Quesito**: Il termine di prescrizione decorre dalla scoperta del danno?" in text
    assert "**Pronuncia seme**: Cass. civ. sez. II n. 7/2025" in text
    assert "massima" in text  # SeedDecision.dispositivo fixture value
    assert text.count("- [ ] trapela") == 1
    assert text.count("- [ ] non trapela") == 1
    assert "NON modifica" in text  # header: outcome never auto-modifies the gold set


def test_export_leakage_markdown_flags_an_unjoined_seed_in_header_and_block():
    task = _jur_task("JUR-CIV-002", seed_citation=_seed_citation(999))
    text = export_leakage_markdown([task], {})  # empty seed index -> nothing joins
    assert "Semi non trovati (join con seeds.json fallita): 1" in text
    assert "JUR-CIV-002" in text
    assert "SEME NON TROVATO" in text


def test_export_leakage_markdown_no_unjoined_seeds_reports_zero():
    task = _jur_task("JUR-CIV-001", seed_citation=_seed_citation(1))
    text = export_leakage_markdown([task], {(1, 2025): _decision(1)})
    assert "Semi non trovati (join con seeds.json fallita): 0" in text
    assert "SEME NON TROVATO" not in text


def test_parse_leakage_markdown_reads_ticked_trapela():
    text = export_leakage_markdown(
        [_jur_task("T1", seed_citation=_seed_citation(1))], {(1, 2025): _decision(1)}
    ).replace("- [ ] trapela", "- [x] trapela")
    assert parse_leakage_markdown(text) == {"T1": True}


def test_parse_leakage_markdown_reads_ticked_non_trapela():
    text = export_leakage_markdown(
        [_jur_task("T1", seed_citation=_seed_citation(1))], {(1, 2025): _decision(1)}
    ).replace("- [ ] non trapela", "- [x] non trapela")
    assert parse_leakage_markdown(text) == {"T1": False}


def test_parse_leakage_markdown_rejects_both_boxes_ticked():
    text = (
        export_leakage_markdown([_jur_task("T1", seed_citation=_seed_citation(1))], {(1, 2025): _decision(1)})
        .replace("- [ ] trapela", "- [x] trapela")
        .replace("- [ ] non trapela", "- [x] non trapela")
    )
    with pytest.raises(ValueError, match="T1: both trapela and non trapela"):
        parse_leakage_markdown(text)


def test_parse_leakage_markdown_treats_a_ticked_box_with_trailing_text_as_untouched():
    text = export_leakage_markdown(
        [_jur_task("T1", seed_citation=_seed_citation(1))], {(1, 2025): _decision(1)}
    ).replace("- [ ] trapela", "- [x] trapela (forse)")
    assert parse_leakage_markdown(text) == {}


def test_parse_leakage_markdown_leaves_untouched_blocks_absent():
    text = export_leakage_markdown(
        [_jur_task("T1", seed_citation=_seed_citation(1))], {(1, 2025): _decision(1)}
    )
    assert parse_leakage_markdown(text) == {}


# --- Stage-level: eligibility filter honored at export time -----------------


def test_leakage_export_only_exports_eligible_jurisprudential_tasks(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    eligible = _jur_task("J1", curated=True, builder_confidence="low", seed_citation=_seed_citation(1))
    low_conf_uncurated = _jur_task("J2", curated=False, builder_confidence="low", seed_citation=_seed_citation(2))
    mdd = _mdd_task_with("M1")
    save_tasks([eligible, low_conf_uncurated, mdd], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1), _decision(2)]}, data_dir / "seeds.json")

    rc = cli.cmd_leakage_export(argparse.Namespace(force=False))
    assert rc == 0

    text = (results_dir / "leakage.md").read_text(encoding="utf-8")
    assert "## J1" in text
    assert "## J2" not in text
    assert "## M1" not in text


# --- Stage-level: full round trip ------------------------------------------


def test_leakage_round_trip_untouched_is_all_undecided_and_blocks(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    tasks = [
        _jur_task("J1", seed_citation=_seed_citation(1)),
        _jur_task("J2", seed_citation=_seed_citation(2)),
    ]
    save_tasks(tasks, data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1), _decision(2)]}, data_dir / "seeds.json")

    rc = cli.cmd_leakage_export(argparse.Namespace(force=False))
    assert rc == 0

    rc2 = cli.cmd_leakage_apply()
    assert rc2 == 1  # human gate: nothing decided yet

    report = json.loads((results_dir / "leakage_report.json").read_text(encoding="utf-8"))
    assert report["summary"] == {"checked": 2, "leaking": 0, "clean": 0, "undecided": 2, "unjoined": 0}
    assert sorted(report["undecided_ids"]) == ["J1", "J2"]
    assert report["tasks"] == {}


def test_leakage_apply_ticked_trapela_marks_leaks_true(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_jur_task("J1", seed_citation=_seed_citation(1))], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1)]}, data_dir / "seeds.json")

    cli.cmd_leakage_export(argparse.Namespace(force=False))
    leakage_path = results_dir / "leakage.md"
    leakage_path.write_text(
        leakage_path.read_text(encoding="utf-8").replace("- [ ] trapela", "- [x] trapela"),
        encoding="utf-8",
    )

    rc = cli.cmd_leakage_apply()
    assert rc == 0

    report = json.loads((results_dir / "leakage_report.json").read_text(encoding="utf-8"))
    assert report["tasks"] == {"J1": {"leaks": True}}
    assert report["summary"] == {"checked": 1, "leaking": 1, "clean": 0, "undecided": 0, "unjoined": 0}

    # tasks.json must never be touched by this stage.
    tasks_after = json.loads((data_dir / "tasks.json").read_text(encoding="utf-8"))
    assert tasks_after[0]["curated"] is True  # unchanged from the fixture


def test_leakage_apply_ticked_non_trapela_marks_leaks_false(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_jur_task("J1", seed_citation=_seed_citation(1))], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1)]}, data_dir / "seeds.json")

    cli.cmd_leakage_export(argparse.Namespace(force=False))
    leakage_path = results_dir / "leakage.md"
    leakage_path.write_text(
        leakage_path.read_text(encoding="utf-8").replace("- [ ] non trapela", "- [x] non trapela"),
        encoding="utf-8",
    )

    rc = cli.cmd_leakage_apply()
    assert rc == 0

    report = json.loads((results_dir / "leakage_report.json").read_text(encoding="utf-8"))
    assert report["tasks"] == {"J1": {"leaks": False}}
    assert report["summary"]["clean"] == 1
    assert report["summary"]["leaking"] == 0


def test_leakage_apply_both_ticked_raises_hard_error_naming_the_task(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_jur_task("J1", seed_citation=_seed_citation(1))], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1)]}, data_dir / "seeds.json")

    cli.cmd_leakage_export(argparse.Namespace(force=False))
    leakage_path = results_dir / "leakage.md"
    leakage_path.write_text(
        leakage_path.read_text(encoding="utf-8")
        .replace("- [ ] trapela", "- [x] trapela")
        .replace("- [ ] non trapela", "- [x] non trapela"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="J1: both trapela and non trapela"):
        cli.cmd_leakage_apply()


def test_leakage_apply_ticked_with_trailing_text_is_undecided(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    save_tasks([_jur_task("J1", seed_citation=_seed_citation(1))], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1)]}, data_dir / "seeds.json")

    cli.cmd_leakage_export(argparse.Namespace(force=False))
    leakage_path = results_dir / "leakage.md"
    leakage_path.write_text(
        leakage_path.read_text(encoding="utf-8").replace(
            "- [ ] trapela", "- [x] trapela (con riserva)"
        ),
        encoding="utf-8",
    )

    rc = cli.cmd_leakage_apply()
    assert rc == 1

    report = json.loads((results_dir / "leakage_report.json").read_text(encoding="utf-8"))
    assert report["undecided_ids"] == ["J1"]
    assert report["summary"]["undecided"] == 1


def test_leakage_apply_counts_and_surfaces_an_unjoined_seed(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)

    # seed_citation points at decision 999, absent from seeds.json.
    save_tasks([_jur_task("J1", seed_citation=_seed_citation(999))], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1)]}, data_dir / "seeds.json")

    rc = cli.cmd_leakage_export(argparse.Namespace(force=False))
    assert rc == 0
    text = (results_dir / "leakage.md").read_text(encoding="utf-8")
    assert "Semi non trovati (join con seeds.json fallita): 1" in text
    assert "SEME NON TROVATO" in text

    # A human can still judge leakage from the query alone even if the
    # automatic join failed -- the unjoined count must still surface.
    leakage_path = results_dir / "leakage.md"
    leakage_path.write_text(text.replace("- [ ] non trapela", "- [x] non trapela"), encoding="utf-8")

    rc = cli.cmd_leakage_apply()
    assert rc == 0
    report = json.loads((results_dir / "leakage_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["unjoined"] == 1
    assert report["unjoined_ids"] == ["J1"]


# --- Overwrite guard: identical contract to review-export/audit-export -----


def test_leakage_export_refuses_to_overwrite_a_ticked_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)
    save_tasks([_jur_task("J1", seed_citation=_seed_citation(1))], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1)]}, data_dir / "seeds.json")
    results_dir.mkdir(parents=True)

    leakage_path = results_dir / "leakage.md"
    original = "## J1\n\n- [x] trapela\n- [ ] non trapela\n"
    leakage_path.write_text(original, encoding="utf-8")

    rc = cli.cmd_leakage_export(argparse.Namespace(force=False))
    assert rc == 1
    assert leakage_path.read_text(encoding="utf-8") == original


def test_leakage_export_force_overwrites_a_ticked_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)
    save_tasks([_jur_task("J1", seed_citation=_seed_citation(1))], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1)]}, data_dir / "seeds.json")
    results_dir.mkdir(parents=True)

    leakage_path = results_dir / "leakage.md"
    leakage_path.write_text("## J1\n\n- [x] trapela\n- [ ] non trapela\n", encoding="utf-8")

    rc = cli.cmd_leakage_export(argparse.Namespace(force=True))
    assert rc == 0
    assert "**Quesito**" in leakage_path.read_text(encoding="utf-8")


def test_leakage_export_plain_reexport_over_untouched_file_is_allowed(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    monkeypatch.setattr(cli, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli, "RESULTS_DIR", results_dir)
    save_tasks([_jur_task("J1", seed_citation=_seed_citation(1))], data_dir / "tasks.json")
    save_seeds({"civil": [_decision(1)]}, data_dir / "seeds.json")
    results_dir.mkdir(parents=True)

    leakage_path = results_dir / "leakage.md"
    leakage_path.write_text(
        "# stale export, nothing ticked\n\n## J1\n\n- [ ] trapela\n- [ ] non trapela\n",
        encoding="utf-8",
    )

    rc = cli.cmd_leakage_export(argparse.Namespace(force=False))
    assert rc == 0
