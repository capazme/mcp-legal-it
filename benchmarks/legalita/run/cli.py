"""Pipeline entry point.

Stages are separate subcommands because two of them stop for a human:
`review-apply` waits for gold-set curation, `audit-apply` waits for the
tiebreak audit. A single end-to-end command would invite skipping them.

Artifacts:
    DATA_DIR (versioned):    seeds.json, tasks.json, review.md
    RESULTS_DIR (gitignored): runs.jsonl, judgments.jsonl, grounding.jsonl,
                              citations.json, audit.md, audit_resolutions.json,
                              report.md, stability_runs.jsonl,
                              stability_resolutions.jsonl, stability.json,
                              leakage.md, leakage_report.json

`stability` (Amendment A3) is a self-contained side pipeline: a 10-task
jurisprudential subset repeated 3x per arm (bare/mcp) to measure grounding
stability under LLM non-determinism. It never feeds `score` and shares no
artifact with the main run/judge/score chain except reading tasks.json.

`leakage-export`/`leakage-apply` (Amendment A5) is a full, unsampled human
spot-check for seed-decision leakage: builder, subject and judges are all
Claude, so a query that telegraphs the seed decision's identity or its
specific holding lets the subject recall instead of reason. It reads
tasks.json and seeds.json and writes leakage.md then leakage_report.json;
it NEVER writes back to tasks.json — a task flagged "trapela" is re-curated
by hand through review-export/review-apply, same as any other gold-set
edit.

Every artifact that has a schema type (Task, RunRecord, Verdict, Citation)
round-trips through it. `SeedDecision` has no schema type (it never leaves
this pipeline), so its (de)serialisation lives here.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from benchmarks.legalita.build.mdd import build_mdd_tasks, load_mdd_seeds
from benchmarks.legalita.build.review import (
    apply_review,
    export_review_markdown,
    needs_review,
    parse_review_markdown,
)
from benchmarks.legalita.build.tasks import build_prompt, parse_builder_output
from benchmarks.legalita.corpus.sample import (
    DOMAIN_FILTERS,
    DOMAIN_QUOTAS,
    SeedDecision,
    build_enumeration_params,
    decision_from_doc,
    in_window,
    select_sample,
)
from benchmarks.legalita.run import arms
from benchmarks.legalita.run.variants import (
    VARIANT_REFS,
    VariantError,
    VariantState,
    ensure_worktrees,
)
from benchmarks.legalita.schema import (
    ARMS,
    VARIANT_ARMS,
    Citation,
    RunRecord,
    Task,
    Verdict,
    load_tasks,
    save_tasks,
)
from benchmarks.legalita.score.citations import extract_citations
from benchmarks.legalita.score.judges import (
    JUDGE_MODELS,
    audit_sample,
    build_grounding_prompt,
    build_judge_prompt,
    parse_grounding_output,
    parse_judge_output,
    reconcile,
)
from benchmarks.legalita.score.metrics import (
    all_pass,
    bonus_rate,
    bootstrap_ci,
    cohens_kappa,
    coverage,
    criterion_rate,
    gog,
    mcnemar_exact,
    mdd_score,
)
from benchmarks.legalita.score.report import ArmResult, build_report
from benchmarks.legalita.score.resolve import resolve_citations

RESULTS_DIR = Path("benchmarks/legalita/results")
DATA_DIR = Path("benchmarks/legalita/data")

# The directory that materialise_mcp_config's "PLUGIN_ROOT/run_server.py"
# template is filled in with — the plugin's server dir, not the repo root.
PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "plugin" / "server"

# Repo root and the variants base: one pinned git worktree per plugin arm
# (plugin-v2, plugin-v3) materialised under benchmarks/legalita/variants/.
# Gitignored run infrastructure, like results/ — rebuilt by `variants`.
REPO_ROOT = Path(__file__).resolve().parents[3]
VARIANTS_DIR = Path("benchmarks/legalita/variants")

_DOMAIN_CODE = {"civil": "CIV", "labour": "LAB", "tax": "TAX"}

_SEED = 20250107

# Amendment A3 — grounding stability repeats (pass^k subset). Owner-scoped,
# no CLI flags: 10 jurisprudential tasks, arms fixed to bare+mcp (the two
# extremes of tool availability -- web is not part of this comparison), 3
# repeats per (task, arm).
_STABILITY_K = 10
_STABILITY_ARMS: tuple[str, ...] = ("bare", "mcp")
_STABILITY_REPEATS: tuple[int, ...] = (1, 2, 3)

_PLAIN_SYSTEM_PROMPT = (
    "Rispondi seguendo esattamente le istruzioni fornite nel messaggio "
    "dell'utente, senza premesse né testo fuori dal formato richiesto."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legalita",
        description="LegalITA replica benchmark. Hits live services; never run in CI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sample", help="draw seed decisions from Italgiure")

    build_cmd = sub.add_parser("build", help="generate tasks from the seed decisions")
    build_cmd.add_argument("--builder-model", default="opus")
    build_cmd.add_argument(
        "--force", action="store_true",
        help="overwrite tasks.json even if it already has curated tasks",
    )

    review_export = sub.add_parser("review-export", help="write the curation markdown")
    review_export.add_argument(
        "--force", action="store_true",
        help="overwrite review.md even if it already has ticked decisions",
    )
    sub.add_parser("review-apply", help="read the curation markdown back")

    variants_cmd = sub.add_parser(
        "variants",
        help="provision the pinned plugin worktrees for the plugin-v2/plugin-v3 arms",
    )
    variants_cmd.add_argument(
        "--force", action="store_true",
        help="re-check-out a worktree even if it already sits at the pinned commit",
    )

    run = sub.add_parser("run", help="execute tasks through the arms")
    run.add_argument("--arms", nargs="+", choices=list(ARMS), default=list(ARMS))
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--model", default="opus")
    # Same value as arms.run_arm's default: the turn cap is a parity control
    # (see run/arms.py) and must not differ between arms.
    run.add_argument("--max-turns", type=int, default=30)

    sub.add_parser("judge", help="run the two-judge panel")

    audit_export = sub.add_parser("audit-export", help="write the human audit queue")
    audit_export.add_argument(
        "--force", action="store_true",
        help="overwrite audit.md even if it already has ticked resolutions",
    )
    sub.add_parser("audit-apply", help="read the human audit queue back")

    leakage_export = sub.add_parser(
        "leakage-export", help="write the human seed-decision leakage spot-check queue"
    )
    leakage_export.add_argument(
        "--force", action="store_true",
        help="overwrite leakage.md even if it already has ticked decisions",
    )
    sub.add_parser("leakage-apply", help="read the human leakage spot-check queue back")

    sub.add_parser("score", help="compute metrics and render the report")

    stability = sub.add_parser(
        "stability",
        help="repeat a fixed 10-task jurisprudential subset x bare/mcp x3 to measure grounding stability (pass^k)",
    )
    stability.add_argument("--model", default="opus")
    stability.add_argument("--max-turns", type=int, default=30)

    return parser


# --- variants ----------------------------------------------------------------


def cmd_variants(args: argparse.Namespace) -> int:
    """Provision one pinned worktree per plugin arm (idempotent).

    Standalone so a human can inspect what each plugin arm will load —
    `benchmarks/legalita/variants/<arm>/` is a real checkout of the pinned
    version, and manifest.json records the exact SHAs — before any `claude -p`
    spend. `run` re-invokes this internally and would refuse to execute a
    variant arm without a provisioned worktree (see cmd_run).
    """
    try:
        states = ensure_worktrees(REPO_ROOT, force=args.force)
    except VariantError as exc:
        print(f"variants: FAILED: {exc}")
        return 1
    for arm, state in states.items():
        print(f"variants: {arm} = {VARIANT_REFS[arm]} @ {state.sha[:12]} -> {state.plugin_dir}")
    return 0


def pending_runs(
    task_ids: list[str],
    arms_: list[str],
    done: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Work still to do, in a stable order so reruns are predictable."""
    return [
        (task_id, arm)
        for task_id in task_ids
        for arm in arms_
        if (task_id, arm) not in done
    ]


def stability_subset(task_ids: list[str], k: int = _STABILITY_K, seed: int = _SEED) -> list[str]:
    """Deterministic task subset for the Amendment A3 pass^k stability check.

    Pure -- no filesystem, no printing. `cmd_stability` is responsible for
    building `task_ids` (sorted jurisprudential, curated/high-confidence
    eligible task ids -- the same eligibility gate `cmd_run` applies) and for
    printing the shortfall when the pool is smaller than `k`.

    Mirrors `select_sample`'s determinism recipe: the input is canonicalised
    by sorting BEFORE drawing (so the draw depends only on the seed and the
    *set* of ids, never on caller iteration order), the RNG is seeded on a
    dedicated `f"{seed}:stability"` namespace so this draw never collides
    with the corpus sample's or the audit sample's draws even when they
    share the same base seed, and the output is sorted again so a resumed
    `stability` run's checkpoint file is keyed on a stable subset.
    """
    pool = sorted(task_ids)
    if len(pool) <= k:
        return pool
    rng = random.Random(f"{seed}:stability")
    return sorted(rng.sample(pool, k))


# --- Generic JSONL helpers (runs.jsonl, judgments.jsonl, grounding.jsonl) --


def _load_jsonl(path: Path, from_dict) -> tuple[list, int]:
    """Read a JSONL file, tolerating ONE corrupt trailing line.

    A file being appended to line-by-line can be interrupted mid-write,
    leaving a truncated last line — that must resume cleanly, not abort the
    whole pipeline. A corrupt line anywhere else in the file is a real
    problem and is allowed to raise. Returns `(items, skipped)`.
    """
    if not path.exists():
        return [], 0
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    items = []
    skipped = 0
    for i, line in enumerate(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                skipped += 1
                continue
            raise
        items.append(from_dict(payload))
    return items, skipped


def _append_jsonl(path: Path, obj: dict) -> None:
    """Append one JSON line, self-healing a truncated trailing line first.

    A crash mid-write can leave the file ending in a partial, non-newline-
    terminated line. Appending straight onto that would concatenate the new
    record onto the tail of the old one, producing ONE permanently corrupt
    line that is no longer the file's last line the next time this function
    runs again — `_load_jsonl` only tolerates a corrupt LAST line, so that
    merged line would raise on every future load, bricking the stage. The
    truncated tail is dropped (its record was never confirmed complete
    anyway) so every append leaves the file in a fully newline-terminated,
    loadable state.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        content = path.read_bytes()
        if content and not content.endswith(b"\n"):
            last_newline = content.rfind(b"\n")
            path.write_bytes(content[: last_newline + 1])
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()


# --- SeedDecision (de)serialisation — no schema.py type for it -------------


def _seed_to_dict(d: SeedDecision) -> dict:
    return {
        "doc_id": d.doc_id,
        "number": d.number,
        "year": d.year,
        "deposited": d.deposited.isoformat(),
        "section": d.section,
        "materia": d.materia,
        "dispositivo": d.dispositivo,
    }


def _seed_from_dict(d: dict) -> SeedDecision:
    return SeedDecision(
        doc_id=str(d["doc_id"]),
        number=int(d["number"]),
        year=int(d["year"]),
        deposited=date.fromisoformat(d["deposited"]),
        section=str(d["section"]),
        materia=str(d["materia"]),
        dispositivo=str(d["dispositivo"]),
    )


def save_seeds(picked: dict[str, list[SeedDecision]], path: Path) -> None:
    payload = {domain: [_seed_to_dict(d) for d in decisions] for domain, decisions in picked.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_seeds(path: Path) -> dict[str, list[SeedDecision]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {domain: [_seed_from_dict(d) for d in items] for domain, items in payload.items()}


# --- One-shot, tool-less `claude -p` call, shared by build and judge -------


def _plain_claude_call(prompt: str, model: str, max_turns: int = 1, timeout_s: int = 300) -> str:
    """One-shot, tool-less `claude -p` call for the builder and judge
    subroutines — never for the arms under test (those go through
    `arms.run_arm`). Reuses `arms.isolation_env` (the operator's global
    citation-gate Stop hook is neutralised the same way it is for a real
    run) and `arms.parse_cli_json` (arm="bare", since a tool-less call is
    exactly that shape) so a malformed or contaminated response fails the
    same way a malformed arm run does, through one parser, not two.
    """
    workdir = Path(tempfile.mkdtemp(prefix="legalita-plain-"))
    try:
        argv = [
            "claude", "-p",
            "--model", model,
            "--system-prompt", _PLAIN_SYSTEM_PROMPT,
            "--settings", "{}",
            "--setting-sources", "project",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--output-format", "json",
            "--max-turns", str(max_turns),
            "--permission-mode", "bypassPermissions",
            "--tools", "",
        ]
        env = {**os.environ, **arms.isolation_env(workdir)}
        completed = subprocess.run(
            argv, input=prompt, cwd=workdir, env=env,
            capture_output=True, text=True, timeout=timeout_s, check=False,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"_plain_claude_call: unparseable CLI output (returncode="
            f"{completed.returncode}): stdout={completed.stdout[:200]!r} "
            f"stderr={completed.stderr[:200]!r}"
        ) from exc

    record = arms.parse_cli_json(payload, task_id="_plain", arm="bare", duration_ms=0)
    if record.error:
        raise RuntimeError(f"_plain_claude_call: {record.error}")
    return record.answer


# --- sample ------------------------------------------------------------


async def cmd_sample() -> int:
    from src.lib.italgiure.client import SolrSession, solr_query

    tallies = {"fetched": 0, "converted": 0, "in_window": 0}
    candidates: dict[str, list[SeedDecision]] = {}
    async with SolrSession() as session:
        for domain, sezioni in DOMAIN_FILTERS.items():
            decisions: list[SeedDecision] = []
            start = 0
            rows = 200
            while True:
                params = build_enumeration_params(sezioni, rows=rows, start=start)
                response = await solr_query(params, session=session)
                body = response.get("response", {})
                docs = body.get("docs", [])
                num_found = int(body.get("numFound", 0))
                if not docs:
                    break
                tallies["fetched"] += len(docs)
                for doc in docs:
                    decision = decision_from_doc(doc)
                    if decision is None:
                        continue
                    tallies["converted"] += 1
                    if in_window(decision.deposited):
                        tallies["in_window"] += 1
                        decisions.append(decision)
                start += rows
                if start >= num_found:
                    break
            candidates[domain] = decisions

    picked = select_sample(candidates, DOMAIN_QUOTAS, seed=_SEED)
    sampled = sum(len(v) for v in picked.values())
    print(
        f"sample: fetched={tallies['fetched']} converted={tallies['converted']} "
        f"in_window={tallies['in_window']} sampled={sampled}"
    )
    seeds_path = DATA_DIR / "seeds.json"
    save_seeds(picked, seeds_path)
    print(f"sample: seeds written to {seeds_path}")
    return 0


# --- build ---------------------------------------------------------------


def cmd_build(args: argparse.Namespace) -> int:
    # `build` is the one non-checkpointed stage (LLM task generation has no
    # per-task resume granularity — see the README's "How to reproduce"
    # section) and unconditionally overwrites tasks.json. Without this
    # guard a re-invocation after `review-apply` has curated the gold set
    # silently regenerates every task from scratch, discarding every
    # `curated: true` flag human review set. Same refuse-unless-`--force`
    # style as `cmd_review_export`/`cmd_audit_export`.
    tasks_path = DATA_DIR / "tasks.json"
    if tasks_path.exists() and not args.force:
        curated = [t for t in load_tasks(tasks_path) if t.curated]
        if curated:
            print(
                f"REFUSED: {tasks_path} already has {len(curated)} curated task(s) — "
                "re-running build would discard human curation. Pass --force to overwrite anyway."
            )
            return 1

    seeds = load_seeds(DATA_DIR / "seeds.json")
    shortfall = {
        domain: {"quota": quota, "actual": len(seeds.get(domain, []))}
        for domain, quota in DOMAIN_QUOTAS.items()
        if len(seeds.get(domain, [])) != quota
    }
    if shortfall:
        print(f"BLOCKED: seed mix does not fill the domain quotas: {shortfall}")
        return 1

    # Load and validate the MDD seeds BEFORE spending a single builder call:
    # a malformed mdd_seeds.json must never discard 30 successful builder
    # calls' worth of spend by failing only after the jurisprudential loop
    # below has already run.
    mdd_tasks = build_mdd_tasks(load_mdd_seeds(DATA_DIR / "mdd_seeds.json"))

    tasks: list[Task] = []
    failures: list[dict] = []
    for domain in DOMAIN_QUOTAS:
        for i, decision in enumerate(seeds[domain], start=1):
            task_id = f"JUR-{_DOMAIN_CODE[domain]}-{i:03d}"
            try:
                prompt = build_prompt(decision, domain)
                text = _plain_claude_call(prompt, model=args.builder_model, max_turns=1)
                task = parse_builder_output(text, task_id, domain, decision)
            except Exception as exc:  # BuilderError, AttributeError (bad criteria shape), etc.
                failures.append({"doc_id": decision.doc_id, "task_id": task_id, "error": str(exc)})
                continue
            tasks.append(task)

    tasks += mdd_tasks

    save_tasks(tasks, DATA_DIR / "tasks.json")
    n_jur = len(tasks) - len(mdd_tasks)
    print(f"build: built {n_jur} jurisprudential + {len(mdd_tasks)} mdd tasks, {len(failures)} failed")
    for f in failures:
        print(f"  failed: {f}")
    return 1 if failures else 0


# --- review-export / review-apply -----------------------------------------


def cmd_review_export(args: argparse.Namespace) -> int:
    tasks = load_tasks(DATA_DIR / "tasks.json")
    pending = needs_review(tasks)
    review_path = DATA_DIR / "review.md"

    if review_path.exists() and not args.force:
        existing = parse_review_markdown(review_path.read_text(encoding="utf-8"))
        if existing:
            print(
                f"REFUSED: {review_path} already has {len(existing)} ticked decision(s) — "
                "re-exporting would discard human curation. Pass --force to overwrite anyway."
            )
            return 1

    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(export_review_markdown(pending), encoding="utf-8")
    print(f"review-export: queued {len(pending)} tasks -> {review_path}")
    return 0


def cmd_review_apply() -> int:
    tasks = load_tasks(DATA_DIR / "tasks.json")
    review_path = DATA_DIR / "review.md"
    decisions = parse_review_markdown(review_path.read_text(encoding="utf-8"))

    pending_ids = {t.id for t in needs_review(tasks)}
    undecided = sorted(pending_ids - set(decisions))
    if undecided:
        print(
            f"BLOCKED: {len(undecided)} low-confidence tasks are still uncurated "
            f"and undecided in review.md: {undecided}"
        )
        return 1

    approved = sum(1 for tid, d in decisions.items() if tid in pending_ids and d["action"] == "approve")
    rejected = sum(1 for tid, d in decisions.items() if tid in pending_ids and d["action"] == "reject")
    deferred = len(pending_ids) - approved - rejected

    save_tasks(apply_review(tasks, decisions), DATA_DIR / "tasks.json")
    print(f"review-apply: queued={len(pending_ids)} approved={approved} rejected={rejected} deferred={deferred}")
    return 0


# --- run -------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    tasks_all = load_tasks(DATA_DIR / "tasks.json")
    eligible = [t for t in tasks_all if t.curated or t.builder_confidence == "high"]
    excluded = len(tasks_all) - len(eligible)
    print(f"run: {len(eligible)} eligible tasks, {excluded} excluded (uncurated and low-confidence)")

    # Variant arms execute against pinned worktrees of the actual server
    # versions. Provision (or re-verify) them BEFORE any spend: every run of
    # this invocation must record the same pin, and a broken worktree must
    # fail loudly here, not as a batch of degraded runs.
    variant_states: dict[str, VariantState] = {}
    if any(arm in VARIANT_ARMS for arm in args.arms):
        try:
            provisioned = ensure_worktrees(REPO_ROOT)
        except VariantError as exc:
            print(f"run: REFUSED — variant provisioning failed: {exc}")
            return 1
        for arm in (a for a in args.arms if a in VARIANT_ARMS):
            state = provisioned[arm]
            variant_states[arm] = state
            print(
                f"run: variant {arm} pinned to {VARIANT_REFS[arm]} "
                f"({state.sha[:12]}) at {state.plugin_dir}"
            )

    runs_path = RESULTS_DIR / "runs.jsonl"
    records, skipped = _load_jsonl(runs_path, RunRecord.from_dict)
    if skipped:
        print(f"run: warning — skipped {skipped} corrupt/partial trailing line(s) in {runs_path}")
    done = {(r.task_id, r.arm) for r in records}

    task_ids = [t.id for t in eligible]
    pending = pending_runs(task_ids, args.arms, done)
    if args.limit is not None:
        pending = pending[: args.limit]
    print(f"run: {len(pending)} pending task/arm pairs")

    # A pin that moved between invocations does not invalidate anything —
    # each record carries its own variant_sha — but it must be SEEN, because
    # an unnoticed pin change would let one arm's label silently mix two
    # server versions inside the same comparison table.
    for arm, state in variant_states.items():
        prior_shas = {
            r.variant_sha for r in records
            if r.arm == arm and r.variant_sha and r.variant_sha != state.sha
        }
        if prior_shas:
            print(
                f"run: WARNING — variant {arm} pin moved: earlier run(s) in "
                f"{runs_path} were executed against "
                f"{', '.join(sorted(s[:12] for s in prior_shas))}; new runs "
                f"record {state.sha[:12]}. Each record keeps its own sha, but "
                "declare the pin change in any write-up."
            )

    tasks_by_id = {t.id: t for t in eligible}
    for i, (task_id, arm) in enumerate(pending, start=1):
        task = tasks_by_id[task_id]
        workdir = Path(tempfile.mkdtemp(prefix="legalita-run-"))
        try:
            state = variant_states.get(arm)
            if state is not None:
                record = arms.run_arm(
                    task, arm, workdir, PLUGIN_ROOT,
                    model=args.model, max_turns=args.max_turns,
                    plugin_dir=state.plugin_dir, variant_sha=state.sha,
                )
            else:
                record = arms.run_arm(
                    task, arm, workdir, PLUGIN_ROOT,
                    model=args.model, max_turns=args.max_turns,
                )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        _append_jsonl(runs_path, record.to_dict())
        print(f"run [{i}/{len(pending)}] {task_id}/{arm}: {'error' if record.error else 'ok'}")
    return 0


# --- stability (Amendment A3: grounding stability repeats, pass^k) ---------
#
# Measures stability of CITATION PRODUCTION AND RESOLUTION only, under LLM
# non-determinism (tau-bench's pass^k rationale, arXiv:2406.12045) -- no
# judge calls, no covers_issue/GOG. `score` stays entirely ignorant of this
# stage; it reads only runs.jsonl/judgments.jsonl/citations.json.


def _stability_task_entry(counts_by_repeat: dict[int, int]) -> dict:
    """One task's per-repeat resolved-citation counts, keyed by repeat id,
    with errored repeats already absent from `counts_by_repeat` (the caller
    excludes them before calling this).

    Empty input -- every repeat for this (task, arm) errored -- is the "zero
    usable repeats" case: both fields are JSON null (never an empty list),
    so a report reader can tell "no usable data" apart from "usable data
    that happens to show zero resolved citations everywhere".
    """
    if not counts_by_repeat:
        return {"resolved_counts": None, "covered": None}
    ordered_counts = [counts_by_repeat[r] for r in sorted(counts_by_repeat)]
    return {"resolved_counts": ordered_counts, "covered": [c > 0 for c in ordered_counts]}


def _stability_arm_metrics(task_entries: dict[str, dict]) -> dict:
    """Aggregate one arm's per-task stability entries (`_stability_task_entry`
    values) into the pass^k coverage/spread metrics.

    Tasks with zero usable repeats (`covered is None`) are excluded from
    every aggregate below -- both numerator and denominator -- per the
    brief, and are surfaced separately in `tasks_without_usable_repeats`
    rather than silently dropped. All three aggregates are null (never 0.0,
    never NaN) when NOT ONE task in the subset has a usable repeat: 0.0
    would misread as "measured and found zero stability" rather than
    "nothing to measure".
    """
    without = sorted(task_id for task_id, entry in task_entries.items() if entry["covered"] is None)
    usable = {
        task_id: entry for task_id, entry in task_entries.items() if entry["covered"] is not None
    }
    if not usable:
        return {
            "coverage_all_k": None,
            "coverage_any_k": None,
            "mean_citation_spread": None,
            "tasks_without_usable_repeats": without,
        }
    n = len(usable)
    coverage_all_k = sum(1 for entry in usable.values() if all(entry["covered"])) / n
    coverage_any_k = sum(1 for entry in usable.values() if any(entry["covered"])) / n
    spreads = [max(entry["resolved_counts"]) - min(entry["resolved_counts"]) for entry in usable.values()]
    mean_citation_spread = sum(spreads) / len(spreads)
    return {
        "coverage_all_k": coverage_all_k,
        "coverage_any_k": coverage_any_k,
        "mean_citation_spread": mean_citation_spread,
        "tasks_without_usable_repeats": without,
    }


def cmd_stability(args: argparse.Namespace) -> int:
    tasks_all = load_tasks(DATA_DIR / "tasks.json")

    # Same eligibility gate `cmd_run` applies (curated OR high-confidence),
    # restricted to the jurisprudential track -- the mdd track has no
    # citations to resolve. If review-apply has never curated anything and
    # the builder produced no high-confidence jurisprudential task either,
    # there is no legitimate pool to draw the subset from.
    eligible_jur_ids = sorted(
        t.id for t in tasks_all
        if t.track == "jurisprudential" and (t.curated or t.builder_confidence == "high")
    )
    if not eligible_jur_ids:
        print(
            "BLOCKED: stability requires a curated task set -- run review-apply "
            "first (no curated/high-confidence jurisprudential tasks found)"
        )
        return 1

    subset = stability_subset(eligible_jur_ids, k=_STABILITY_K, seed=_SEED)
    if len(subset) < _STABILITY_K:
        print(
            f"stability: shortfall -- only {len(subset)} eligible jurisprudential "
            f"task(s) available, expected {_STABILITY_K}"
        )
    print(f"stability: subset ({len(subset)} tasks) = {subset}")

    tasks_by_id = {t.id: t for t in tasks_all}
    subset_set = set(subset)

    runs_path = RESULTS_DIR / "stability_runs.jsonl"
    raw_runs, skipped = _load_jsonl(runs_path, lambda d: d)
    if skipped:
        print(f"stability: warning — skipped {skipped} corrupt/partial trailing line(s) in {runs_path}")
    done = {(d["task_id"], d["arm"], int(d["repeat"])) for d in raw_runs}

    pending = [
        (task_id, arm, repeat)
        for task_id in subset
        for arm in _STABILITY_ARMS
        for repeat in _STABILITY_REPEATS
        if (task_id, arm, repeat) not in done
    ]
    print(f"stability: {len(pending)} pending (task, arm, repeat) triples")

    for i, (task_id, arm, repeat) in enumerate(pending, start=1):
        task = tasks_by_id[task_id]
        workdir = Path(tempfile.mkdtemp(prefix="legalita-stability-"))
        try:
            record = arms.run_arm(
                task, arm, workdir, PLUGIN_ROOT, model=args.model, max_turns=args.max_turns,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        payload = record.to_dict()
        payload["repeat"] = repeat
        _append_jsonl(runs_path, payload)
        print(f"stability [{i}/{len(pending)}] {task_id}/{arm}/repeat{repeat}: {'error' if record.error else 'ok'}")

    # Recompute from the FULL accumulated file (this run's writes plus any
    # prior partial run), so a resumed stage's metrics reflect everything
    # recorded so far, not just this invocation's own work.
    raw_runs, _ = _load_jsonl(runs_path, lambda d: d)
    excluded_by_arm: dict[str, int] = {}
    usable_runs: list[tuple[str, str, int, RunRecord]] = []
    for d in raw_runs:
        if d["task_id"] not in subset_set or d["arm"] not in _STABILITY_ARMS:
            continue  # stale entry from an earlier, different subset draw
        record = RunRecord.from_dict(d)
        repeat = int(d["repeat"])
        if record.error is not None:
            excluded_by_arm[record.arm] = excluded_by_arm.get(record.arm, 0) + 1
            continue
        usable_runs.append((record.task_id, record.arm, repeat, record))
    if excluded_by_arm:
        print(f"stability: excluding {sum(excluded_by_arm.values())} errored run(s) from metrics: {excluded_by_arm}")

    # A DEDICATED resolution cache, keyed with `repeat` -- the main
    # pipeline's resolutions.jsonl key (task_id, arm, index) has no repeat
    # dimension, so sharing it would let one repeat's resolution silently
    # answer for another repeat's citation at the same index, and would
    # write stability-only entries into the file `judge` treats as
    # authoritative for the main pipeline. Never share it.
    resolutions_path = RESULTS_DIR / "stability_resolutions.jsonl"
    cached_raw, _ = _load_jsonl(resolutions_path, lambda d: d)
    resolution_cache: dict[tuple[str, str, int, int], tuple[bool, str]] = {
        (r["task_id"], r["arm"], int(r["repeat"]), int(r["index"])): (r["resolved"], r["resolution_note"])
        for r in cached_raw
    }

    async def _resolve_all() -> tuple[dict[tuple[str, str, int], list[Citation]], list[dict]]:
        by_triple: dict[tuple[str, str, int], list[Citation]] = {}
        failures: list[dict] = []
        for task_id, arm, repeat, record in usable_runs:
            citations = extract_citations(record.answer, task_id, arm)

            cached: list[Citation] = []
            to_resolve: list[Citation] = []
            for c in citations:
                cache_key = (c.task_id, c.arm, repeat, c.index)
                if cache_key in resolution_cache:
                    c.resolved, c.resolution_note = resolution_cache[cache_key]
                    cached.append(c)
                else:
                    to_resolve.append(c)
            if to_resolve:
                try:
                    to_resolve = await resolve_citations(to_resolve)
                except Exception as exc:  # live verification call — never crash the stage
                    failures.append({
                        "task_id": task_id, "arm": arm, "repeat": repeat, "error": str(exc),
                    })
                    # Leave these citations exactly as extract_citations produced
                    # them (resolved stays at its unset default) -- fail-closed,
                    # never fabricates a resolved=False, never touches the cache.
                else:
                    for c in to_resolve:
                        _append_jsonl(resolutions_path, {
                            "task_id": c.task_id, "arm": c.arm, "repeat": repeat,
                            "index": c.index, "resolved": c.resolved,
                            "resolution_note": c.resolution_note,
                        })
                        resolution_cache[(c.task_id, c.arm, repeat, c.index)] = (c.resolved, c.resolution_note)
            by_triple[(task_id, arm, repeat)] = cached + to_resolve
        return by_triple, failures

    citations_by_triple, resolve_failures = asyncio.run(_resolve_all())
    if resolve_failures:
        print(f"stability: {len(resolve_failures)} citation-resolution failure(s): {resolve_failures}")

    arms_out: dict[str, dict] = {}
    for arm in _STABILITY_ARMS:
        task_entries: dict[str, dict] = {}
        for task_id in subset:
            counts_by_repeat: dict[int, int] = {}
            for repeat in _STABILITY_REPEATS:
                key = (task_id, arm, repeat)
                if key not in citations_by_triple:
                    continue  # errored or not yet run -- excluded, not zero
                counts_by_repeat[repeat] = sum(
                    1 for c in citations_by_triple[key] if c.resolved is True
                )
            task_entries[task_id] = _stability_task_entry(counts_by_repeat)
        arms_out[arm] = {"tasks": task_entries, **_stability_arm_metrics(task_entries)}

    payload = {
        "tasks": subset,
        "repeats": len(_STABILITY_REPEATS),
        "excluded_error_runs": excluded_by_arm,
        "arms": arms_out,
    }
    stability_path = RESULTS_DIR / "stability.json"
    stability_path.parent.mkdir(parents=True, exist_ok=True)
    stability_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for arm, entry in arms_out.items():
        print(
            f"stability: arm={arm} coverage_all_k={entry['coverage_all_k']} "
            f"coverage_any_k={entry['coverage_any_k']} "
            f"mean_citation_spread={entry['mean_citation_spread']} "
            f"tasks_without_usable_repeats={entry['tasks_without_usable_repeats']}"
        )
    print(f"stability: written to {stability_path}")
    return 0


# --- judge (criteria panel + citation-grounding validation) ---------------


def _grounding_agreement(a: bool, b: bool) -> bool | None:
    """The citation-grounding tiebreak rule: both true -> True, both false
    -> False, anything else -> None (never guessed, queued for the human
    audit exactly like a criteria disagreement). No Judge C."""
    if a and b:
        return True
    if not a and not b:
        return False
    return None


def _covers_issue_map(grounding_records: list[dict]) -> dict[tuple[str, str, str], bool | None]:
    """Apply the grounding agreement rule to accumulated per-judge raw
    verdicts. A citation with only one judge's verdict so far is simply
    absent (not yet determined, resumable); a citation with both judges'
    verdicts present maps to True/False (agreement) or None (disagreement —
    left for `audit-export`/`audit-apply` to queue and resolve)."""
    by_key: dict[tuple[str, str, str], dict[str, bool]] = {}
    for r in grounding_records:
        key = (r["task_id"], r["arm"], str(r["index"]))
        by_key.setdefault(key, {})[r["judge"]] = bool(r["covers"])
    result: dict[tuple[str, str, str], bool | None] = {}
    for key, by_judge in by_key.items():
        if "A" not in by_judge or "B" not in by_judge:
            continue
        result[key] = _grounding_agreement(by_judge["A"], by_judge["B"])
    return result


def _grounding_verdict_list(records: list[dict], judge: str) -> list[Verdict]:
    """Wrap raw grounding.jsonl rows as `Verdict`s so `reconcile()`/`audit_sample()`
    can be reused verbatim for citation-grounding disagreements — the
    citation index takes the place of `criterion_id`."""
    return [
        Verdict(
            task_id=r["task_id"], arm=r["arm"], criterion_id=str(r["index"]),
            judge=judge, verdict=bool(r["covers"]), reasoning=str(r.get("reasoning", "")),
        )
        for r in records
        if r["judge"] == judge
    ]


def cmd_judge() -> int:
    tasks = {t.id: t for t in load_tasks(DATA_DIR / "tasks.json")}
    runs_path = RESULTS_DIR / "runs.jsonl"
    all_records, skipped = _load_jsonl(runs_path, RunRecord.from_dict)
    if skipped:
        print(f"judge: warning — skipped {skipped} corrupt/partial trailing line(s) in {runs_path}")

    # A run that errored (timeout, unparseable output, tool-shape mismatch,
    # Stop-hook contamination — anything that set `record.error`) is not a
    # substantive answer and must never be judged or scored as one. Count
    # and surface the exclusion per arm rather than silently dropping it.
    excluded_by_arm: dict[str, int] = {}
    records: list[RunRecord] = []
    for r in all_records:
        if r.error is not None:
            excluded_by_arm[r.arm] = excluded_by_arm.get(r.arm, 0) + 1
            continue
        records.append(r)
    if excluded_by_arm:
        print(f"judge: excluding {sum(excluded_by_arm.values())} errored/timed-out run(s) from judging: {excluded_by_arm}")

    judgments_path = RESULTS_DIR / "judgments.jsonl"
    done_verdicts, _ = _load_jsonl(judgments_path, Verdict.from_dict)
    done_keys = {(v.task_id, v.arm, v.criterion_id, v.judge) for v in done_verdicts}

    failures: list[dict] = []
    judged = 0
    for record in records:
        task = tasks.get(record.task_id)
        if task is None:
            failures.append({"task_id": record.task_id, "arm": record.arm, "error": "task not in tasks.json"})
            continue
        criterion_ids = [c.id for c in task.criteria]
        for judge, model in JUDGE_MODELS.items():
            if all((record.task_id, record.arm, cid, judge) in done_keys for cid in criterion_ids):
                continue
            try:
                prompt = build_judge_prompt(task, record, task.criteria)
                text = _plain_claude_call(prompt, model=model, max_turns=1)
                verdicts = parse_judge_output(text, record.task_id, record.arm, judge, criterion_ids)
            except Exception as exc:  # JudgeError and any transport failure alike
                failures.append({"task_id": record.task_id, "arm": record.arm, "judge": judge, "error": str(exc)})
                continue
            for v in verdicts:
                _append_jsonl(judgments_path, v.to_dict())
                judged += 1
    print(f"judge: {judged} criteria verdicts written, {len(failures)} failures")

    # --- citation-grounding validation (jurisprudential tasks only) -------
    grounding_path = RESULTS_DIR / "grounding.jsonl"
    done_grounding, _ = _load_jsonl(grounding_path, lambda d: d)
    done_grounding_keys = {(r["task_id"], r["arm"], r["index"], r["judge"]) for r in done_grounding}

    # Citation resolution is a LIVE call and must be cached: re-verifying an
    # already-resolved citation on every `judge` re-issue is wasteful, and
    # a transient failure on a re-verification must never downgrade an
    # already-confirmed resolved=True. resolutions.jsonl is the cache; a
    # citation already in it is never passed to resolve_citations again.
    resolutions_path = RESULTS_DIR / "resolutions.jsonl"
    cached_resolutions, _ = _load_jsonl(resolutions_path, lambda d: d)
    resolution_cache: dict[tuple[str, str, int], tuple[bool, str]] = {
        (r["task_id"], r["arm"], r["index"]): (r["resolved"], r["resolution_note"])
        for r in cached_resolutions
    }

    async def _grounding_pass() -> tuple[list[Citation], list[dict]]:
        all_citations: list[Citation] = []
        gfailures: list[dict] = []
        for record in records:
            task = tasks.get(record.task_id)
            if task is None or task.track != "jurisprudential":
                continue
            citations = extract_citations(record.answer, record.task_id, record.arm)

            cached: list[Citation] = []
            to_resolve: list[Citation] = []
            for c in citations:
                cache_key = (c.task_id, c.arm, c.index)
                if cache_key in resolution_cache:
                    c.resolved, c.resolution_note = resolution_cache[cache_key]
                    cached.append(c)
                else:
                    to_resolve.append(c)
            if to_resolve:
                try:
                    to_resolve = await resolve_citations(to_resolve)
                except Exception as exc:  # live verification call — never let it crash the pass
                    gfailures.append({
                        "stage": "resolve_citations", "task_id": record.task_id,
                        "arm": record.arm, "error": str(exc),
                    })
                    # Leave these citations exactly as extract_citations produced them
                    # (resolved stays at its unset default) — a transient failure must
                    # never fabricate a resolved=False, and never touches the cache.
                else:
                    for c in to_resolve:
                        _append_jsonl(resolutions_path, {
                            "task_id": c.task_id, "arm": c.arm, "index": c.index,
                            "resolved": c.resolved, "resolution_note": c.resolution_note,
                        })
                        resolution_cache[(c.task_id, c.arm, c.index)] = (c.resolved, c.resolution_note)
            citations = cached + to_resolve
            all_citations.extend(citations)

            for citation in citations:
                if citation.resolved is not True:
                    continue  # unresolved citations are never judged
                for judge, model in JUDGE_MODELS.items():
                    key = (citation.task_id, citation.arm, citation.index, judge)
                    if key in done_grounding_keys:
                        continue
                    try:
                        prompt = build_grounding_prompt(task, citation)
                        text = _plain_claude_call(prompt, model=model, max_turns=1)
                        covers, reasoning = parse_grounding_output(text)
                    except Exception as exc:
                        gfailures.append(
                            {"stage": "grounding_judge", "task_id": citation.task_id, "arm": citation.arm,
                             "index": citation.index, "judge": judge, "error": str(exc)}
                        )
                        continue
                    _append_jsonl(grounding_path, {
                        "task_id": citation.task_id, "arm": citation.arm, "index": citation.index,
                        "judge": judge, "covers": covers, "reasoning": reasoning,
                    })
        return all_citations, gfailures

    all_citations, gfailures = asyncio.run(_grounding_pass())
    failures += gfailures
    print(f"judge: grounding pass — {len(all_citations)} citations extracted, {len(gfailures)} failures")

    # Recompute covers_issue from the FULL accumulated grounding.jsonl (this
    # run's writes plus any prior partial run), so a resumed judge stage
    # reflects verdicts recorded earlier too.
    all_grounding, _ = _load_jsonl(grounding_path, lambda d: d)
    covers_map = _covers_issue_map(all_grounding)
    for citation in all_citations:
        citation.covers_issue = covers_map.get((citation.task_id, citation.arm, str(citation.index)))

    citations_path = RESULTS_DIR / "citations.json"
    citations_path.parent.mkdir(parents=True, exist_ok=True)
    citations_path.write_text(
        json.dumps([c.to_dict() for c in all_citations], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"judge: citations written to {citations_path}")

    return 1 if failures else 0


# --- audit-export / audit-apply --------------------------------------------
#
# The human audit queue combines criteria disagreements (Task 9's
# `reconcile`) and citation-grounding disagreements (this module's
# `_grounding_verdict_list` + the same `reconcile`) into one markdown file,
# using a composite, review.py-style checkbox block per item.

_AUDIT_ID_SEP = "--"


def _audit_id(kind: str, task_id: str, arm: str, sub_id: str) -> str:
    """Composite id for one audit-queue item, safe for a `[A-Z0-9-]+`
    markdown header: task ids, criterion ids and citation indices never
    contain '--' in this schema, so the join is reversible."""
    return _AUDIT_ID_SEP.join((task_id, arm.upper(), kind.upper(), sub_id))


def _parse_audit_id(audit_id: str) -> tuple[str, tuple[str, str, str]]:
    """Inverse of `_audit_id`. Returns `(kind, (task_id, arm, sub_id))`."""
    task_id, arm, kind, sub_id = audit_id.split(_AUDIT_ID_SEP)
    return kind.lower(), (task_id, arm.lower(), sub_id)


def _agreed_with_reasoning(
    agreed: dict[tuple[str, str, str], bool],
    verdicts_a: list[Verdict],
    verdicts_b: list[Verdict],
) -> list[dict]:
    """Turn `reconcile()`'s agreed dict back into review-friendly items,
    reattaching each judge's original reasoning (which `reconcile` drops
    for agreed entries, keeping only the boolean)."""
    def key(v: Verdict) -> tuple[str, str, str]:
        return (v.task_id, v.arm, v.criterion_id)

    index_a = {key(v): v for v in verdicts_a}
    index_b = {key(v): v for v in verdicts_b}
    items = []
    for (task_id, arm, criterion_id), verdict in agreed.items():
        items.append({
            "task_id": task_id,
            "arm": arm,
            "criterion_id": criterion_id,
            "verdict": verdict,
            "reasoning_a": index_a[(task_id, arm, criterion_id)].reasoning,
            "reasoning_b": index_b[(task_id, arm, criterion_id)].reasoning,
        })
    return items


_AUDIT_BLOCK_RE = re.compile(
    r"^##\s+(?P<id>[A-Z0-9\-]+)\s*$(?P<body>.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL
)
_TRUE_RE = re.compile(r"^-\s*\[(?P<mark>[ xX])\]\s*vero\s*$", re.MULTILINE)
_FALSE_RE = re.compile(r"^-\s*\[(?P<mark>[ xX])\]\s*falso\s*$", re.MULTILINE)


def export_audit_markdown(items: list[dict], overflow: dict[str, int] | None = None) -> str:
    """`overflow` (optional) reports how many disagreements did NOT make it
    into this export because `audit_sample` caps the disagreement stratum —
    e.g. `{"criterion": 20, "grounding": 0}`. Surfaced in the header so the
    operator knows the queue's mandatory coverage is partial, not silent."""
    lines = [
        "# Audit umano — LegalITA benchmark",
        "",
        "Per ogni voce spunta `vero` o `falso` per indicare il verdetto finale.",
        "Le voci `disagreement` sono OBBLIGATORIE: il pannello dei giudici non ha",
        "raggiunto un accordo e la pipeline resta bloccata finché non vengono",
        "risolte. Le voci `agreement` servono a stimare il tasso di errore del",
        "pannello: rispondile pure, ma non bloccano la pipeline. Le note libere",
        "sono ignorate dal parser.",
        "",
    ]
    if overflow and any(overflow.values()):
        lines += [
            "**ATTENZIONE — copertura parziale**: il numero di disaccordi supera il "
            "tetto del campione umano. Disaccordi NON esportati in questa coda "
            f"(non fanno parte del gate obbligatorio): {overflow}.",
            "",
        ]
    for item in items:
        audit_id = _audit_id(item["kind"], item["task_id"], item["arm"], item["criterion_id"])
        lines += [
            f"## {audit_id}",
            "",
            f"**Tipo**: {item['kind']} · **Stratum**: {item['stratum']} · "
            f"**Task**: {item['task_id']} · **Braccio**: {item['arm']}",
        ]
        if "verdict" in item:
            lines.append(f"**Verdetto del pannello**: {item['verdict']}")
        lines += [
            f"**Giudice A**: {item.get('reasoning_a', '')}",
            f"**Giudice B**: {item.get('reasoning_b', '')}",
            "",
            "- [ ] vero",
            "- [ ] falso",
            "",
        ]
    return "\n".join(lines) + "\n"


def parse_audit_markdown(text: str) -> dict[str, bool]:
    """Read the ticked boxes. A canonical checkbox is exactly `- [x] vero`
    or `- [x] falso` with nothing else on the line — a ticked box with
    trailing text is treated as untouched, mirroring `review.py`."""
    resolutions: dict[str, bool] = {}
    for block in _AUDIT_BLOCK_RE.finditer(text):
        audit_id = block.group("id")
        body = block.group("body")
        true_match = _TRUE_RE.search(body)
        false_match = _FALSE_RE.search(body)
        is_true = bool(true_match and true_match.group("mark").lower() == "x")
        is_false = bool(false_match and false_match.group("mark").lower() == "x")
        if is_true and is_false:
            raise ValueError(f"{audit_id}: both vero and falso are ticked")
        if is_true:
            resolutions[audit_id] = True
        elif is_false:
            resolutions[audit_id] = False
    return resolutions


def _reconcile_tolerant(
    verdicts_a: list[Verdict],
    verdicts_b: list[Verdict],
    *,
    label: str,
) -> tuple[dict[tuple[str, str, str], bool], list[dict], list[Verdict], list[Verdict], int]:
    """Pair judge A/B verdicts on the intersection of their keys and
    reconcile only the pairs.

    `reconcile()` raises `JudgeError` on ANY key mismatch between the two
    judge lists — which would make every downstream stage (audit-export,
    score) raise permanently the moment a single verdict is unpaired (one
    judge answered, the other failed the call, is still pending a retry, or
    the pipeline was interrupted between the two judge calls for one item).
    Unpaired keys are dropped, counted and printed instead — never silently
    resolved to a guessed verdict, never a hard crash. A dropped pair simply
    never enters `agreed`/`disagreements`, so it flows into
    `drop_incomplete`'s unresolved accounting the same way a real
    disagreement would.

    Shared by the criteria and citation-grounding reconcile paths (and by
    `cmd_score`, which needs the exact same tolerant pairing over the
    already-loaded judgments — see its "criteria" caller); `label` only
    changes the printed message so an operator can tell which verdict kind
    was affected.
    """
    if not verdicts_a and not verdicts_b:
        return {}, [], [], [], 0

    def key(v: Verdict) -> tuple[str, str, str]:
        return (v.task_id, v.arm, v.criterion_id)

    keys_a = {key(v) for v in verdicts_a}
    keys_b = {key(v) for v in verdicts_b}
    common = keys_a & keys_b
    unpaired = (keys_a | keys_b) - common
    if unpaired:
        print(
            f"{label}: dropping {len(unpaired)} unpaired verdict(s) "
            f"(only one judge has answered so far): {sorted(unpaired)}"
        )
    paired_a = [v for v in verdicts_a if key(v) in common]
    paired_b = [v for v in verdicts_b if key(v) in common]
    agreed, disagreements = reconcile(paired_a, paired_b)
    return agreed, disagreements, paired_a, paired_b, len(unpaired)


def _criteria_agreed_and_disagreements(
    judgments_path: Path,
) -> tuple[dict[tuple[str, str, str], bool], list[dict], list[Verdict], list[Verdict], int]:
    """Like `_grounding_agreed_and_disagreements`, tolerant of an unpaired
    criterion verdict (judge A succeeded, judge B failed or is still
    pending) via the shared `_reconcile_tolerant` helper."""
    verdicts, _ = _load_jsonl(judgments_path, Verdict.from_dict)
    verdicts_a = [v for v in verdicts if v.judge == "A"]
    verdicts_b = [v for v in verdicts if v.judge == "B"]
    return _reconcile_tolerant(verdicts_a, verdicts_b, label="criteria")


def _grounding_agreed_and_disagreements(
    grounding_path: Path,
) -> tuple[dict[tuple[str, str, str], bool], list[dict], list[Verdict], list[Verdict], int]:
    """Like `_criteria_agreed_and_disagreements`, but for citation-grounding
    `covers_issue` verdicts, via the shared `_reconcile_tolerant` helper."""
    records, _ = _load_jsonl(grounding_path, lambda d: d)
    verdicts_a = _grounding_verdict_list(records, "A")
    verdicts_b = _grounding_verdict_list(records, "B")
    return _reconcile_tolerant(verdicts_a, verdicts_b, label="grounding")


def _write_audit_manifest(all_items: list[dict], path: Path) -> dict:
    """Persist exactly which item ids were exported and in which stratum.

    `audit-apply`'s gate MUST read this back rather than recompute
    disagreements fresh: `audit_sample` caps the disagreement stratum at a
    fixed ceiling, so past that cap a freshly recomputed "all current
    disagreements" set is a strict superset of what a human could ever see
    in `audit.md`, making the gate permanently unsatisfiable.
    """
    def item_id(item: dict) -> str:
        return _audit_id(item["kind"], item["task_id"], item["arm"], item["criterion_id"])

    manifest = {
        "mandatory": sorted({item_id(i) for i in all_items if i["stratum"] == "disagreement"}),
        "optional": sorted({item_id(i) for i in all_items if i["stratum"] == "agreement"}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def cmd_audit_export(args: argparse.Namespace) -> int:
    audit_path = RESULTS_DIR / "audit.md"
    if audit_path.exists() and not args.force:
        existing = parse_audit_markdown(audit_path.read_text(encoding="utf-8"))
        if existing:
            print(
                f"REFUSED: {audit_path} already has {len(existing)} ticked resolution(s) — "
                "re-exporting would discard human audit work. Pass --force to overwrite anyway."
            )
            return 1

    agreed, disagreements, va, vb, unpaired_criteria = _criteria_agreed_and_disagreements(
        RESULTS_DIR / "judgments.jsonl"
    )
    agreed_items = [{**item, "kind": "criterion"} for item in _agreed_with_reasoning(agreed, va, vb)]
    disagreement_items = [{**d, "kind": "criterion"} for d in disagreements]
    criteria_audit = audit_sample(agreed_items, disagreement_items, seed=_SEED)
    criteria_overflow = len(disagreement_items) - sum(
        1 for i in criteria_audit if i["stratum"] == "disagreement"
    )

    agreed_g, disagreements_g, vag, vbg, unpaired_g = _grounding_agreed_and_disagreements(
        RESULTS_DIR / "grounding.jsonl"
    )
    agreed_g_items = [{**item, "kind": "grounding"} for item in _agreed_with_reasoning(agreed_g, vag, vbg)]
    disagreement_g_items = [{**d, "kind": "grounding"} for d in disagreements_g]
    grounding_audit = audit_sample(agreed_g_items, disagreement_g_items, seed=_SEED)
    grounding_overflow = len(disagreement_g_items) - sum(
        1 for i in grounding_audit if i["stratum"] == "disagreement"
    )

    all_items = criteria_audit + grounding_audit
    overflow = {"criterion": criteria_overflow, "grounding": grounding_overflow}

    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(export_audit_markdown(all_items, overflow=overflow), encoding="utf-8")
    manifest = _write_audit_manifest(all_items, RESULTS_DIR / "audit_manifest.json")

    n_mandatory = len(manifest["mandatory"])
    n_optional = len(manifest["optional"])
    print(
        f"audit-export: {len(all_items)} items -> {audit_path} "
        f"({n_mandatory} disagreements mandatory, {n_optional} agreement-sample optional)"
    )
    if any(overflow.values()):
        print(f"audit-export: WARNING — cap overflow, disagreements NOT exported: {overflow}")
    if unpaired_criteria:
        print(f"audit-export: {unpaired_criteria} unpaired criterion verdict(s) excluded from this export")
    if unpaired_g:
        print(f"audit-export: {unpaired_g} unpaired grounding verdict(s) excluded from this export")
    return 0


def cmd_audit_apply() -> int:
    manifest_path = RESULTS_DIR / "audit_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mandatory_ids = set(manifest.get("mandatory", []))

    audit_path = RESULTS_DIR / "audit.md"
    resolutions = parse_audit_markdown(audit_path.read_text(encoding="utf-8"))

    # Persist whatever the human has resolved so far BEFORE checking the
    # gate: a partial pass must never discard completed audit work just
    # because some mandatory items are still pending.
    resolutions_path = RESULTS_DIR / "audit_resolutions.json"
    resolutions_path.parent.mkdir(parents=True, exist_ok=True)
    resolutions_path.write_text(json.dumps(resolutions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pending = sorted(mandatory_ids - set(resolutions))
    if pending:
        print(f"BLOCKED: {len(pending)} disagreements still unresolved in audit.md: {pending}")
        print(f"audit-apply: persisted {len(resolutions)} resolution(s) collected so far to {resolutions_path}")
        return 1

    n_criterion = sum(1 for k in resolutions if _parse_audit_id(k)[0] == "criterion")
    n_grounding = len(resolutions) - n_criterion
    print(f"audit-apply: resolved {len(resolutions)} items ({n_criterion} criteria, {n_grounding} grounding)")
    return 0


# --- leakage-export / leakage-apply (Amendment A5: human leakage check) ----
#
# Builder, subject and judges are all Claude; a task query that telegraphs
# the seed decision's identity or its specific holding lets the subject
# "recall instead of reason" (methodology review, SWE-bench Illusion
# transfer). This is a FULL, unsampled human spot-check over every
# curated-or-high-confidence jurisprudential task — the same
# curated-OR-high-confidence gate `cmd_run`/`cmd_stability` apply,
# restricted to the jurisprudential track (mdd tasks carry no
# `seed_citation` and cannot leak a seed decision). The outcome NEVER
# auto-modifies the gold set: a task flagged "trapela" is re-curated by
# hand through review-export/review-apply, exactly like any other gold-set
# edit — this module only reads tasks.json, never writes it.

_LEAKAGE_BLOCK_RE = re.compile(
    r"^##\s+(?P<id>[A-Z0-9\-]+)\s*$(?P<body>.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL
)
_LEAKS_RE = re.compile(r"^-\s*\[(?P<mark>[ xX])\]\s*trapela\s*$", re.MULTILINE)
_CLEAN_RE = re.compile(r"^-\s*\[(?P<mark>[ xX])\]\s*non trapela\s*$", re.MULTILINE)


def _leakage_eligible_tasks(tasks: list[Task]) -> list[Task]:
    """Same curated-OR-high-confidence gate as `cmd_run`/`cmd_stability`,
    restricted to the jurisprudential track — mdd tasks have no seed
    decision behind them and cannot leak one."""
    return [
        t for t in tasks
        if t.track == "jurisprudential" and (t.curated or t.builder_confidence == "high")
    ]


def _seed_index(seeds: dict[str, list[SeedDecision]]) -> dict[tuple[int, int], SeedDecision]:
    """Flatten the domain-grouped seeds.json into one (number, year) ->
    SeedDecision map. Decision numbers are unique within the cassazione
    civile archive for a given year regardless of section (see
    `corpus.sample`'s `DOMAIN_FILTERS` note), so this join key is safe
    across domains without also keying on domain/section."""
    index: dict[tuple[int, int], SeedDecision] = {}
    for decisions in seeds.values():
        for d in decisions:
            index[(d.number, d.year)] = d
    return index


def _seed_key(task: Task) -> tuple[object, object]:
    """The (number, year) a task's `seed_citation` claims to come from —
    the join key into `_seed_index`. Missing/malformed fields fall back to
    `None`, which never matches a real `SeedDecision` key, so a task with a
    broken `seed_citation` is correctly treated as unjoined rather than
    raising."""
    seed = task.seed_citation or {}
    return (seed.get("number"), seed.get("year"))


def export_leakage_markdown(
    tasks: list[Task], seed_index: dict[tuple[int, int], SeedDecision]
) -> str:
    """`tasks` is already the eligible (curated-or-high-confidence,
    jurisprudential) set — this function exports every one of them, no
    sampling. A task whose `seed_citation` cannot be joined against
    `seed_index` is still exported (fail-visible), flagged inline as "SEME
    NON TROVATO", and counted in the header rather than silently skipped.
    """
    joined = [(t, seed_index.get(_seed_key(t))) for t in tasks]
    unjoined_ids = sorted(t.id for t, decision in joined if decision is None)

    lines = [
        "# Controllo di trapelamento (spot-check umano) — LegalITA benchmark",
        "",
        "Ogni quesito giurisprudenziale nasce da una pronuncia seme che il",
        "modello costruttore ha visto ma che il sistema sotto test non deve",
        "MAI vedere. Se il quesito rivela o ricalca quella pronuncia, il",
        "sistema sotto test può richiamarla a memoria invece di ragionare sul",
        "diritto — e poiché costruttore, sistema sotto test e giudici sono",
        "tutti Claude, questo rischio (\"SWE-bench Illusion\") va verificato da",
        "un umano, non da un altro modello.",
        "",
        "**\"trapela\"** = il quesito rivela gli estremi della pronuncia seme",
        "(numero, sezione, anno) o ne ricalca la formulazione al punto da",
        "permettere il richiamo mnemonico della pronuncia stessa, anziché",
        "richiedere un ragionamento giuridico autonomo.",
        "",
        "**Importante**: l'esito di questo controllo NON modifica",
        "automaticamente il gold set. I task segnalati come `trapela` vanno",
        "ripresi a mano attraverso il consueto flusso di curatela",
        "(`review-export` / `review-apply`).",
        "",
        "Per ogni task spunta `trapela` o `non trapela`. Lascia entrambe le",
        "caselle vuote per rimandare la decisione. Le note libere sono",
        "ignorate dal parser.",
        "",
        f"Task esaminati: {len(tasks)} · Semi non trovati (join con "
        f"seeds.json fallita): {len(unjoined_ids)}"
        + (f" — {unjoined_ids}" if unjoined_ids else ""),
        "",
    ]
    for task, decision in joined:
        seed = task.seed_citation or {}
        lines += [f"## {task.id}", "", f"**Quesito**: {task.query}", ""]
        if decision is not None:
            lines += [
                f"**Pronuncia seme**: {seed.get('court', '')} sez. "
                f"{seed.get('section', '')} n. {seed.get('number', '')}/"
                f"{seed.get('year', '')}",
                "",
                f"> {decision.dispositivo}",
                "",
            ]
        else:
            lines += [
                "**Pronuncia seme**: SEME NON TROVATO — join fallita su "
                f"seeds.json (seed_citation numero={seed.get('number')!r} "
                f"anno={seed.get('year')!r})",
                "",
            ]
        lines += ["- [ ] trapela", "- [ ] non trapela", ""]
    return "\n".join(lines) + "\n"


def parse_leakage_markdown(text: str) -> dict[str, bool]:
    """Read the ticked boxes. A canonical checkbox is exactly `- [x] trapela`
    or `- [x] non trapela` with nothing else on the line — mirrors
    `review.py`/`parse_audit_markdown`. Maps task id -> True (leaks) or
    False (clean); untouched blocks are absent from the result."""
    decisions: dict[str, bool] = {}
    for block in _LEAKAGE_BLOCK_RE.finditer(text):
        task_id = block.group("id")
        body = block.group("body")
        leaks_match = _LEAKS_RE.search(body)
        clean_match = _CLEAN_RE.search(body)
        leaks = bool(leaks_match and leaks_match.group("mark").lower() == "x")
        clean = bool(clean_match and clean_match.group("mark").lower() == "x")
        if leaks and clean:
            raise ValueError(f"{task_id}: both trapela and non trapela are ticked")
        if leaks:
            decisions[task_id] = True
        elif clean:
            decisions[task_id] = False
    return decisions


def cmd_leakage_export(args: argparse.Namespace) -> int:
    tasks = load_tasks(DATA_DIR / "tasks.json")
    eligible = _leakage_eligible_tasks(tasks)
    seeds = load_seeds(DATA_DIR / "seeds.json")
    seed_index = _seed_index(seeds)

    leakage_path = RESULTS_DIR / "leakage.md"
    if leakage_path.exists() and not args.force:
        existing = parse_leakage_markdown(leakage_path.read_text(encoding="utf-8"))
        if existing:
            print(
                f"REFUSED: {leakage_path} already has {len(existing)} ticked decision(s) — "
                "re-exporting would discard human spot-check work. Pass --force to overwrite anyway."
            )
            return 1

    unjoined = sum(1 for t in eligible if _seed_key(t) not in seed_index)
    leakage_path.parent.mkdir(parents=True, exist_ok=True)
    leakage_path.write_text(export_leakage_markdown(eligible, seed_index), encoding="utf-8")
    print(
        f"leakage-export: {len(eligible)} jurisprudential tasks -> {leakage_path} "
        f"({unjoined} seme/i non trovato/i)"
    )
    return 0


def cmd_leakage_apply() -> int:
    tasks = load_tasks(DATA_DIR / "tasks.json")
    eligible = _leakage_eligible_tasks(tasks)
    seeds = load_seeds(DATA_DIR / "seeds.json")
    seed_index = _seed_index(seeds)

    exported_ids = sorted(t.id for t in eligible)
    unjoined_ids = sorted(t.id for t in eligible if _seed_key(t) not in seed_index)

    leakage_path = RESULTS_DIR / "leakage.md"
    decisions = parse_leakage_markdown(leakage_path.read_text(encoding="utf-8"))

    # Persist whatever the human has resolved so far BEFORE checking the
    # gate — same write-before-refuse pattern as `cmd_audit_apply`: a
    # partial pass must never discard completed spot-check work just
    # because some exported task is still undecided.
    per_task = {tid: {"leaks": decisions[tid]} for tid in exported_ids if tid in decisions}
    undecided = sorted(set(exported_ids) - set(decisions))

    leaking = sum(1 for v in per_task.values() if v["leaks"])
    clean = sum(1 for v in per_task.values() if not v["leaks"])
    summary = {
        "checked": len(exported_ids),
        "leaking": leaking,
        "clean": clean,
        "undecided": len(undecided),
        "unjoined": len(unjoined_ids),
    }

    report_path = RESULTS_DIR / "leakage_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "tasks": per_task,
                "summary": summary,
                "undecided_ids": undecided,
                "unjoined_ids": unjoined_ids,
            },
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    if undecided:
        print(f"BLOCKED: {len(undecided)} tasks still undecided in leakage.md: {undecided}")
        print(f"leakage-apply: persisted {len(per_task)} decision(s) collected so far to {report_path}")
        return 1

    print(
        f"leakage-apply: checked={summary['checked']} leaking={summary['leaking']} "
        f"clean={summary['clean']} unjoined={summary['unjoined']}"
    )
    return 0


# --- score: merge/drop contract, then metrics ------------------------------


def merge_verdicts(
    agreed: dict[tuple[str, str, str], bool],
    resolutions: dict[str, bool],
) -> dict[tuple[str, str, str], bool]:
    """Combine panel agreement with human audit resolutions.

    `resolutions` is the flat `audit_id -> bool` dict written by
    `audit-apply`; only the `criterion` kind feeds the criteria merge
    (grounding resolutions are applied separately, directly onto
    `Citation.covers_issue`). A resolution overrides an agreed entry too —
    the audit legitimately re-checks agreement-stratum items.
    """
    merged = dict(agreed)
    for audit_id, verdict in resolutions.items():
        kind, key = _parse_audit_id(audit_id)
        if kind == "criterion":
            merged[key] = verdict
    return merged


def drop_incomplete(
    merged: dict[tuple[str, str, str], bool],
    tasks: dict[str, Task],
    run_pairs: list[tuple[str, str]],
) -> tuple[dict[str, dict[str, dict[str, bool]]], int]:
    """Group merged verdicts by arm/task, dropping any (task, arm) pair
    still missing a verdict for one of its required criteria.

    This is the mandatory merge contract from the task-9 review: passing
    `reconcile()`'s raw `agreed` straight to the metrics raises, because it
    omits every criterion the judges disagreed on. Returns
    `(verdicts_by_arm, unresolved)`: `verdicts_by_arm[arm][task_id]` is
    exactly the shape `metrics.py` expects, and `unresolved` is the count
    of (task, arm) pairs dropped — the report's `unresolved` figure.
    """
    by_pair: dict[tuple[str, str], dict[str, bool]] = {}
    for (task_id, arm, criterion_id), verdict in merged.items():
        by_pair.setdefault((task_id, arm), {})[criterion_id] = verdict

    verdicts_by_arm: dict[str, dict[str, dict[str, bool]]] = {}
    unresolved = 0
    for task_id, arm in run_pairs:
        task = tasks[task_id]
        required_ids = {c.id for c in task.required_criteria()}
        criteria = by_pair.get((task_id, arm), {})
        if not required_ids <= criteria.keys():
            unresolved += 1
            continue
        verdicts_by_arm.setdefault(arm, {})[task_id] = criteria
    return verdicts_by_arm, unresolved


def count_bonus_judged(verdicts_for_arm: dict[str, dict[str, bool]], tasks: dict[str, Task]) -> int:
    """Cross-task contract with `report.py`'s `ArmResult.bonus_judged`:
    count of bonus criteria with a merged (kept, post-drop) verdict."""
    total = 0
    for task_id, criteria in verdicts_for_arm.items():
        bonus_ids = {c.id for c in tasks[task_id].bonus_criteria()}
        total += sum(1 for cid in criteria if cid in bonus_ids)
    return total


def _task_pass_map(verdicts_for_arm: dict[str, dict[str, bool]], tasks: dict[str, Task]) -> dict[str, bool]:
    """Per-task R_i (eq. 1) keyed by task id: True iff every required
    criterion passed. Used both for `_per_task_pass_values` (the all_pass
    bootstrap CI, which only needs the values) and for the Amendment A2
    paired McNemar comparisons (which need the task id to match the SAME
    task across two arms' survivor sets -- a bare list of values in
    dict-iteration order cannot be paired safely once the two arms'
    survivor sets diverge, e.g. one arm drops a task to an unresolved
    criterion disagreement that the other arm's run of the same task
    survived).
    """
    result: dict[str, bool] = {}
    for task_id, criteria in verdicts_for_arm.items():
        required_ids = {c.id for c in tasks[task_id].required_criteria()}
        required_verdicts = [v for cid, v in criteria.items() if cid in required_ids]
        result[task_id] = bool(required_verdicts) and all(required_verdicts)
    return result


def _per_task_pass_values(verdicts_for_arm: dict[str, dict[str, bool]], tasks: dict[str, Task]) -> list[float]:
    """Per-task R_i values (eq. 1), for the all_pass bootstrap CI."""
    return [1.0 if passed else 0.0 for passed in _task_pass_map(verdicts_for_arm, tasks).values()]


def _task_coverage_map(citations_for_arm: dict[str, list[Citation]]) -> dict[str, bool]:
    """Per-task binary GOG coverage (|G_i| > 0) keyed by task id -- the same
    predicate `metrics.coverage()` aggregates over all tasks, but kept per
    task so it can be paired against another arm's survivor set for the
    Amendment A2 McNemar comparison, the same way `_task_pass_map` is."""
    return {
        task_id: any(c.counts_as_grounded() for c in citations)
        for task_id, citations in citations_for_arm.items()
    }


def _paired_mcnemar(map_a: dict[str, bool], map_b: dict[str, bool]) -> dict:
    """Pair two arms' per-task binary outcome maps on the intersection of
    their task ids (the survivor-set intersection, NOT the full task list)
    and run the exact McNemar test on the paired outcomes.

    The three arms do not necessarily survive `drop_incomplete` (or produce
    a citation) on the exact same task subset -- one arm can lose a task to
    an unresolved criterion disagreement while another arm's run of the
    same task survived, or one arm may simply never have been run at all.
    McNemar needs genuine pairs, so anything outside the intersection is
    silently excluded; `pairable` reports how large that intersection was,
    so a report reader can see how much of the paired test's statistical
    power was lost to asymmetric survivorship rather than mistaking a small
    `pairable` count for a small discordant count.
    """
    common = sorted(set(map_a) & set(map_b))
    pairs = [(map_a[task_id], map_b[task_id]) for task_id in common]
    result = mcnemar_exact(pairs)
    result["pairable"] = len(common)
    return result


_P_VALUE_FLOOR = 0.0001


def _fmt_p(p_value: float | None) -> str:
    """stdout rendering for an exact McNemar p-value: "null" when undefined
    (mirrors `_fmt_rate`'s None handling), and "<0.0001" below the display
    floor rather than the impossible "0.0000" -- reachable at ~15+ one-way
    discordant pairs (e.g. b=20, c=0 gives p ~= 1.9e-6). Mirrors
    `report._p_value_str`, which applies the same floor to the markdown
    table; kept as a separate function because the two callers use
    different tokens for "undefined" ("null" for the machine-readable
    stdout log line, "n/d" for the human-facing report).
    """
    if p_value is None:
        return "null"
    if p_value < _P_VALUE_FLOOR:
        return "<0.0001"
    return f"{p_value:.4f}"


def _per_task_gog_values(citations_for_arm: dict[str, list[Citation]]) -> list[float]:
    """Per-task GOG_i values (eq. 6), for the GOG bootstrap CI."""
    values = []
    for citations in citations_for_arm.values():
        if not citations:
            values.append(0.0)
            continue
        grounded = sum(1 for c in citations if c.counts_as_grounded())
        values.append(grounded / len(citations))
    return values


def _citations_by_arm_task(
    citations: list[Citation],
    tasks: dict[str, Task],
    run_pairs: list[tuple[str, str]],
) -> dict[str, dict[str, list[Citation]]]:
    """Group citations by arm then task, seeded with an empty list for
    every jurisprudential task actually run — `gog()`/`coverage()` score a
    task with zero citations as 0, but only if its key is present at all."""
    out: dict[str, dict[str, list[Citation]]] = {}
    for task_id, arm in run_pairs:
        task = tasks.get(task_id)
        if task is None or task.track != "jurisprudential":
            continue
        out.setdefault(arm, {}).setdefault(task_id, [])
    for c in citations:
        task = tasks.get(c.task_id)
        if task is None or task.track != "jurisprudential":
            continue
        out.setdefault(c.arm, {}).setdefault(c.task_id, []).append(c)
    return out


def _paired_verdicts(verdicts_a: list[Verdict], verdicts_b: list[Verdict]) -> tuple[list[bool], list[bool]]:
    """Every (task, arm, criterion) both judges answered, in stable order —
    unlike `reconcile`'s `agreed`, this keeps disagreements too (kappa
    needs to see them) and tolerates a partially-judged set instead of
    raising."""
    def key(v: Verdict) -> tuple[str, str, str]:
        return (v.task_id, v.arm, v.criterion_id)

    index_a = {key(v): v for v in verdicts_a}
    index_b = {key(v): v for v in verdicts_b}
    common = sorted(set(index_a) & set(index_b))
    return [index_a[k].verdict for k in common], [index_b[k].verdict for k in common]


def _excluded_error_runs(run_records: list[RunRecord]) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """Split run records into scoreable pairs and a per-arm count of runs
    excluded because `record.error` was set (timeout, unparseable output,
    tool-shape mismatch, Stop-hook contamination, ...). An errored run is
    not a substantive answer and must never be judged or scored as one."""
    pairs: list[tuple[str, str]] = []
    excluded_by_arm: dict[str, int] = {}
    for r in run_records:
        if r.error is not None:
            excluded_by_arm[r.arm] = excluded_by_arm.get(r.arm, 0) + 1
            continue
        pairs.append((r.task_id, r.arm))
    return pairs, excluded_by_arm


def _pending_grounding_by_arm(citations: list[Citation]) -> dict[str, int]:
    """Count, per arm, resolved citations whose `covers_issue` is still
    None — either because the disagreement hasn't been resolved by the
    human audit yet, or because it was never fully judged by both judges.
    Both cases equally deflate GOG/coverage by omission, so they are
    reported together as one 'pending grounding' completeness signal."""
    pending: dict[str, int] = {}
    for c in citations:
        if c.resolved is True and c.covers_issue is None:
            pending[c.arm] = pending.get(c.arm, 0) + 1
    return pending


def cmd_score() -> int:
    tasks = {t.id: t for t in load_tasks(DATA_DIR / "tasks.json")}

    run_records, _ = _load_jsonl(RESULTS_DIR / "runs.jsonl", RunRecord.from_dict)
    run_pairs, excluded_by_arm = _excluded_error_runs(run_records)
    if excluded_by_arm:
        print(f"score: excluding {sum(excluded_by_arm.values())} errored/timed-out run(s) from scoring: {excluded_by_arm}")

    verdicts, _ = _load_jsonl(RESULTS_DIR / "judgments.jsonl", Verdict.from_dict)
    verdicts_a = [v for v in verdicts if v.judge == "A"]
    verdicts_b = [v for v in verdicts if v.judge == "B"]
    # Tolerant, not the raw `reconcile()`: a criterion verdict pending its
    # second judge (one succeeded, one failed/still queued) must never make
    # `score` raise forever — it is dropped, counted and printed instead,
    # and the affected (task, arm) pair falls out naturally through
    # `drop_incomplete`'s unresolved accounting below.
    agreed, _disagreements, _pa, _pb, _unpaired_criteria = _reconcile_tolerant(
        verdicts_a, verdicts_b, label="criteria"
    )

    resolutions_path = RESULTS_DIR / "audit_resolutions.json"
    resolutions: dict[str, bool] = (
        json.loads(resolutions_path.read_text(encoding="utf-8")) if resolutions_path.exists() else {}
    )

    merged = merge_verdicts(agreed, resolutions)
    verdicts_by_arm, unresolved = drop_incomplete(merged, tasks, run_pairs)

    # Citations: load, then fold in any human-resolved grounding disagreements.
    citations_path = RESULTS_DIR / "citations.json"
    citations = (
        [Citation.from_dict(d) for d in json.loads(citations_path.read_text(encoding="utf-8"))]
        if citations_path.exists()
        else []
    )
    for citation in citations:
        audit_id = _audit_id("grounding", citation.task_id, citation.arm, str(citation.index))
        if audit_id in resolutions:
            citation.covers_issue = resolutions[audit_id]

    citations_by_arm_task = _citations_by_arm_task(citations, tasks, run_pairs)
    pending_grounding_by_arm = _pending_grounding_by_arm(citations)
    if pending_grounding_by_arm:
        print(
            "score: pending grounding verdicts (unresolved disagreement or not yet "
            f"judged by both judges — GOG/coverage omit these): {pending_grounding_by_arm}"
        )

    # audit_error_rate: share of audited AGREEMENT-stratum items (criteria
    # and grounding combined) whose human verdict overturned the panel.
    # audit_error_rate_by_kind (Amendment A4) splits the same tally by
    # "criterion" vs "grounding" — fail-closed: a kind with zero audited
    # agreements reports null, never 0.0 (0.0 would misread as "audited
    # and found perfect" rather than "never audited").
    audited_agreement = 0
    overturned = 0
    audited_by_kind = {"criterion": 0, "grounding": 0}
    overturned_by_kind = {"criterion": 0, "grounding": 0}
    agreed_g, _disagreements_g, vag, vbg, _unpaired_g = _grounding_agreed_and_disagreements(
        RESULTS_DIR / "grounding.jsonl"
    )
    for audit_id, human_verdict in resolutions.items():
        kind, (task_id, arm, sub_id) = _parse_audit_id(audit_id)
        key = (task_id, arm, sub_id)
        panel = agreed.get(key) if kind == "criterion" else agreed_g.get(key)
        if panel is None:
            continue  # this id resolved a disagreement, not an agreement re-check
        audited_agreement += 1
        audited_by_kind[kind] += 1
        if human_verdict != panel:
            overturned += 1
            overturned_by_kind[kind] += 1
    # Fail-closed the same way every other "never measured" statistic in
    # this pipeline is: zero audited agreements means the rate was never
    # computed, not that it was computed and found to be zero.
    audit_error_rate = overturned / audited_agreement if audited_agreement else None
    audit_error_rate_by_kind = {
        kind: (overturned_by_kind[kind] / audited_by_kind[kind] if audited_by_kind[kind] else None)
        for kind in ("criterion", "grounding")
    }

    # Amendment A2: per-arm, per-task binary outcome maps, collected
    # alongside the aggregate metrics below so the paired McNemar
    # comparisons after the loop can pair the SAME task across two arms'
    # independently-surviving sets, not just report two separate rates.
    jur_pass_by_arm: dict[str, dict[str, bool]] = {}
    mdd_pass_by_arm: dict[str, dict[str, bool]] = {}
    gog_coverage_by_arm: dict[str, dict[str, bool]] = {}

    results: list[ArmResult] = []
    for arm in ARMS:
        arm_verdicts = verdicts_by_arm.get(arm, {})
        jur_verdicts = {tid: c for tid, c in arm_verdicts.items() if tasks[tid].track == "jurisprudential"}
        mdd_verdicts = {tid: c for tid, c in arm_verdicts.items() if tasks[tid].track == "mdd"}

        ap = all_pass(jur_verdicts, tasks)
        cr = criterion_rate(jur_verdicts, tasks)
        br = bonus_rate(jur_verdicts, tasks)
        bj = count_bonus_judged(jur_verdicts, tasks)

        cits = citations_by_arm_task.get(arm, {})
        g = gog(cits)
        cov = coverage(cits)

        mdd_pass_map = _task_pass_map(mdd_verdicts, tasks)
        m = mdd_score(mdd_pass_map.values())

        # Fail-closed: bootstrap_ci([]) is (nan, nan) -- not valid JSON and
        # meaningless as a CI. An arm with zero surviving jurisprudential
        # tasks (never run, or every task dropped by drop_incomplete) never
        # calls bootstrap_ci at all; it reports None (JSON null, rendered
        # "n/d" by the report) instead of a NaN-filled interval.
        per_task_pass = _per_task_pass_values(jur_verdicts, tasks)
        per_task_gog = _per_task_gog_values(cits)
        ap_ci = bootstrap_ci(per_task_pass, seed=_SEED) if per_task_pass else None
        gog_ci = bootstrap_ci(per_task_gog, seed=_SEED) if per_task_gog else None

        results.append(ArmResult(
            arm=arm, all_pass=ap, criterion_rate=cr, gog=g, coverage=cov, mdd=m,
            all_pass_ci=ap_ci, gog_ci=gog_ci, bonus_rate=br, bonus_judged=bj,
            n_jur=len(jur_verdicts), n_mdd=len(mdd_verdicts),
        ))

        jur_pass_by_arm[arm] = _task_pass_map(jur_verdicts, tasks)
        mdd_pass_by_arm[arm] = mdd_pass_map
        gog_coverage_by_arm[arm] = _task_coverage_map(cits)

    # Fail-closed the same way `grounding_kappa` below already does:
    # `cohens_kappa` returns `float("nan")` for an empty pair (n == 0),
    # which is not valid JSON and renders as the meaningless "nan" in the
    # report -- a run with no judgments at all (pa == pb == []) must report
    # None (json null), never a NaN literal.
    pa, pb = _paired_verdicts(verdicts_a, verdicts_b)
    kappa = cohens_kappa(pa, pb) if pa else None

    # Amendment A2: grounding kappa reuses the SAME judge-A/judge-B pairing
    # already built for grounding reconcile (`vag`/`vbg` above) rather than
    # re-deriving it from grounding.jsonl a second time. Fail-closed to
    # None (never nan/0.0) when there is nothing paired to measure
    # agreement over — e.g. no jurisprudential citations were ever judged.
    ga, gb = _paired_verdicts(vag, vbg)
    grounding_kappa = cohens_kappa(ga, gb) if ga else None

    # Amendment A2: paired McNemar comparisons per arm pair per track. Pairs
    # are built on the intersection of each pair's per-task outcome maps
    # (the survivor sets), not on the full task list — see `_paired_mcnemar`.
    paired_comparisons: dict[str, dict[str, dict]] = {}
    for arm_a, arm_b in itertools.combinations(ARMS, 2):
        paired_comparisons[f"{arm_a}_vs_{arm_b}"] = {
            "jurisprudential_all_pass": _paired_mcnemar(jur_pass_by_arm[arm_a], jur_pass_by_arm[arm_b]),
            "mdd_pass": _paired_mcnemar(mdd_pass_by_arm[arm_a], mdd_pass_by_arm[arm_b]),
            "gog_coverage": _paired_mcnemar(gog_coverage_by_arm[arm_a], gog_coverage_by_arm[arm_b]),
        }

    # Denominator split, printed explicitly because the two families of
    # numbers in this report are NOT counted over the same population:
    # all_pass/criterion_rate/bonus_rate run over the post-merge,
    # post-drop_incomplete survivors (excluded-error runs AND unresolved
    # required-criterion pairs both removed); GOG/coverage run over every
    # run pair that wasn't excluded for a run error, regardless of whether
    # its criteria verdicts ever resolved.
    print(
        "score: denominator note — reasoning metrics (all_pass/criterion_rate/"
        "bonus_rate) run over post-drop survivors only; grounding metrics "
        "(GOG/coverage) run over all non-errored run pairs, independent of "
        "criteria resolution."
    )

    report_md = build_report(
        results, kappa=kappa, unresolved=unresolved, audit_error_rate=audit_error_rate,
        paired=paired_comparisons, grounding_kappa=grounding_kappa,
        audited_agreement=audited_agreement,
    )
    report_md += (
        "\n## Note operative\n\n"
        f"- Run esclusi dallo scoring per errore/timeout: **{sum(excluded_by_arm.values())}** {excluded_by_arm}\n"
        f"- Verdetti di grounding ancora pendenti (disaccordo non risolto o non "
        f"ancora giudicato da entrambi i giudici): **{sum(pending_grounding_by_arm.values())}** "
        f"{pending_grounding_by_arm}\n"
        "- Le metriche di ragionamento (all_pass/criterion_rate/bonus_rate) sono "
        "calcolate solo sui pair task/braccio sopravvissuti al merge/drop; le "
        "metriche di grounding (GOG/coverage) sono calcolate su tutti i pair "
        "eseguiti non esclusi per errore, indipendentemente dalla risoluzione "
        "dei criteri.\n"
    )
    report_path = RESULTS_DIR / "report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")

    scores_path = RESULTS_DIR / "scores.json"
    scores_path.write_text(
        json.dumps(
            {
                "unresolved_criteria_pairs": unresolved,
                "audit_error_rate": audit_error_rate,
                "audit_error_rate_by_kind": audit_error_rate_by_kind,
                # Amendment/finding I6: the sample size behind audit_error_rate.
                # README Limitations #6 tells a reader to compute a binomial CI
                # "from the reported n" -- these are that n, fail-open (0 is a
                # legitimate "nothing audited yet" count here, unlike the rate
                # itself, because a count of zero is never ambiguous the way a
                # rate of 0.0 would be).
                "audited_agreement": audited_agreement,
                "audited_by_kind": audited_by_kind,
                "kappa": kappa,
                "grounding_kappa": grounding_kappa,
                "paired_comparisons": paired_comparisons,
                "excluded_error_runs_by_arm": excluded_by_arm,
                "pending_grounding_by_arm": pending_grounding_by_arm,
                "arms": {
                    r.arm: {
                        "all_pass": r.all_pass, "criterion_rate": r.criterion_rate,
                        "gog": r.gog, "coverage": r.coverage, "mdd": r.mdd,
                        "bonus_rate": r.bonus_rate, "bonus_judged": r.bonus_judged,
                        "all_pass_ci": list(r.all_pass_ci) if r.all_pass_ci is not None else None,
                        "gog_ci": list(r.gog_ci) if r.gog_ci is not None else None,
                        "n_jur": r.n_jur, "n_mdd": r.n_mdd,
                    }
                    for r in results
                },
            },
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    def _fmt_rate(x: float | None) -> str:
        return f"{x:.3f}" if x is not None else "null"

    by_kind_str = (
        f"criterion={_fmt_rate(audit_error_rate_by_kind['criterion'])} "
        f"grounding={_fmt_rate(audit_error_rate_by_kind['grounding'])}"
    )
    print(
        f"score: unresolved={unresolved} audit_error_rate={_fmt_rate(audit_error_rate)} "
        f"(n={audited_agreement}) audit_error_rate_by_kind[{by_kind_str}] "
        f"kappa={_fmt_rate(kappa)} grounding_kappa={_fmt_rate(grounding_kappa)}"
    )
    for pair_key, tracks in paired_comparisons.items():
        for track_key, entry in tracks.items():
            print(
                f"score: mcnemar {pair_key}/{track_key}: pairable={entry['pairable']} "
                f"b={entry['b']} c={entry['c']} discordant={entry['discordant']} "
                f"p={_fmt_p(entry['p_value'])}"
            )
    print(f"score: report written to {report_path}, scores written to {scores_path}")
    return 0


# --- dispatch ----------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "sample": lambda: asyncio.run(cmd_sample()),
        "build": lambda: cmd_build(args),
        "review-export": lambda: cmd_review_export(args),
        "review-apply": cmd_review_apply,
        "variants": lambda: cmd_variants(args),
        "run": lambda: cmd_run(args),
        "judge": cmd_judge,
        "audit-export": lambda: cmd_audit_export(args),
        "audit-apply": cmd_audit_apply,
        "leakage-export": lambda: cmd_leakage_export(args),
        "leakage-apply": cmd_leakage_apply,
        "score": cmd_score,
        "stability": lambda: cmd_stability(args),
    }
    try:
        return handlers[args.command]()
    except Exception as exc:  # fail visibly, never a silent stack trace only
        print(f"ERROR: stage {args.command!r} failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
