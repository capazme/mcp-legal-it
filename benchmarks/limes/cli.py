"""LIMES CLI: plan / check / run / score / compare.

    python -m benchmarks.limes.cli plan    [--root benchmarks/limes]
    python -m benchmarks.limes.cli check   --wave waves/wave-0.yaml
    python -m benchmarks.limes.cli run     --wave waves/wave-0.yaml [--dry-run]
                                           [--models m1,m2] [--configs c1,c2]
                                           [--only-items id1,id2]
                                           [--allow-unfrozen]
    python -m benchmarks.limes.cli score   --cell results/wave-0/<model>/<config>
    python -m benchmarks.limes.cli compare --cell-a ... --cell-b ...

`run` computes the five SHA and enforces the freeze guard (DESIGN §2): no
run without a tag freezing bank/protocol/configs. `--allow-unfrozen` is the
explicit dev override — recorded in wave.json as `"frozen": false`, so an
unfrozen number can never masquerade as a frozen one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmarks.limes.analysis.compare import compare_cells
from benchmarks.limes.analysis.scorecard import (
    build_scorecard,
    construct_key,
    discrimination_report,
)
from benchmarks.limes.bank.schema.item import Bank, load_bank
from benchmarks.limes.bank.schema.validate import validate_bank
from benchmarks.limes.protocol.citations import provenance_answer
from benchmarks.limes.protocol.gemelle import iter_mechanical_s
from benchmarks.limes.protocol.rules import load_protocol
from benchmarks.limes.protocol.scorers_q import score_q
from benchmarks.limes.runner.executor import RunOutcome, build_argv, run_cell
from benchmarks.limes.runner.manifests import Manifest, load_manifest
from benchmarks.limes.runner.shas import Shas, collect
from benchmarks.limes.runner.waves import (
    Wave,
    freeze_guard,
    freeze_status,
    load_wave,
    wave_paths,
)


def _default_root() -> Path:
    return Path(__file__).resolve().parent


def _wave_file(root: Path, wave_arg: str | None) -> Path | None:
    if not wave_arg:
        # No wave named: default to the newest declared wave (a benchmark
        # with a single wave is the common case; plan must show its matrix).
        waves = sorted((root / "waves").glob("*.yaml"))
        waves += sorted((root / "waves").glob("*.yml"))
        return waves[-1] if waves else None
    path = Path(wave_arg)
    if not path.is_absolute():
        path = root / "waves" / path
    if path.suffix not in (".yaml", ".yml"):
        path = path.with_suffix(".yaml")
    return path


def _load_context(root: Path, wave_file: Path | None):
    protocol = load_protocol(root / "protocol" / "protocol.yaml")
    bank = load_bank(root / "bank")
    wave = load_wave(wave_file) if wave_file else None
    manifests = _load_manifests(root / "configs")
    return protocol, bank, wave, manifests


def _load_manifests(configs_dir: Path) -> dict[str, Manifest]:
    out: dict[str, Manifest] = {}
    for path in sorted(configs_dir.glob("*.yaml")):
        manifest = load_manifest(path)
        out[manifest.id] = manifest
    return out


def _select(
    wave: Wave | None, manifests: dict[str, Manifest], models: str | None, configs: str | None
) -> list[tuple[str, str]]:
    wave_models = wave.models if wave else []
    wave_configs = wave.configs if wave else list(manifests)
    sel_models = [m.strip() for m in models.split(",")] if models else wave_models
    sel_configs = [c.strip() for c in configs.split(",")] if configs else wave_configs
    cells = [(m, c) for m in sel_models for c in sel_configs]
    for _, config_id in cells:
        if config_id not in manifests:
            raise SystemExit(f"config sconosciuta: {config_id!r}")
    return cells


def cmd_plan(args: argparse.Namespace) -> int:
    root = Path(args.root)
    protocol, bank, wave, manifests = _load_context(root, _wave_file(root, args.wave))
    cells = _select(wave, manifests, args.models, args.configs)
    print(f"bank: {len(bank.items)} item ({len(bank.anchor_items())} anchor, "
          f"{len(bank.private_items())} private); "
          f"Q={len(bank.items_of_layer('Q'))} S={len(bank.items_of_layer('S'))}; "
          f"gemelle={len(bank.twin_families())} famiglie")
    print(f"protocollo v{protocol.version} (seed {protocol.seed}); "
          f"giudici: {'attivi' if protocol.judge_enabled else 'meccanico-only'}")
    print(f"matrice: {len(cells)} celle")
    for model, config_id in cells:
        manifest = manifests[config_id]
        print(f"  {model:<20} x {manifest.id:<32} surface={manifest.surface} "
              f"ref={manifest.ref or '-'} turns={manifest.max_turns}")
    status = freeze_status(root / "bank", root / "protocol")
    for label, info in status.items():
        state = "FROZEN" if info["frozen"] else "pending (committare + tag, DESIGN §2)"
        print(f"freeze {label:<9} {info['path']:<28} {state}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    ok = True
    try:
        summary = validate_bank(root / "bank")
        print("bank OK:", ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))
    except Exception as exc:  # ValidationError and JSON errors both fail the check
        print(f"bank INVALID: {exc}", file=sys.stderr)
        ok = False
    try:
        protocol = load_protocol(root / "protocol" / "protocol.yaml")
        print(f"protocol OK: v{protocol.version}, seed {protocol.seed}")
    except Exception as exc:
        print(f"protocol INVALID: {exc}", file=sys.stderr)
        ok = False
    try:
        manifests = _load_manifests(root / "configs")
        print(f"configs OK: {len(manifests)} manifest "
              f"({', '.join(sorted(manifests))})")
    except Exception as exc:
        print(f"configs INVALID: {exc}", file=sys.stderr)
        ok = False
    status = freeze_status(root / "bank", root / "protocol")
    for label, info in status.items():
        if not info["frozen"]:
            print(f"freeze PENDING {label}: {info['path']} "
                  f"(committed={info['committed']}, dirty={info['dirty']})")
    return 0 if ok else 1


def _cell_dir(root: Path, wave: Wave, model: str, config_id: str) -> Path:
    return wave_paths(root)["results"] / wave.id / model / config_id


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    protocol, bank, wave, manifests = _load_context(root, _wave_file(root, args.wave))
    if wave is None:
        raise SystemExit("--wave è obbligatorio per run")
    cells = _select(wave, manifests, args.models, args.configs)
    only_items = set(args.only_items.split(",")) if args.only_items else None

    shas: Shas | None = None
    frozen = False
    if args.allow_unfrozen:
        print("ATTENZIONE: --allow-unfrozen — il record sarà 'frozen: false'")
    elif args.dry_run:
        # Dry-run is a planning aid: the freeze guard is diagnostic here,
        # never a crash — `plan`/`run --dry-run` must work before the tag.
        status = freeze_status(root / "bank", root / "protocol")
        pending = [k for k, v in status.items() if not v.get("frozen")]
        if pending:
            print(f"ATTENZIONE: freeze PENDING su {', '.join(pending)} (dry-run: non bloccante)")
    else:
        shas = collect(root / "bank", root / "protocol", cells[0][0], manifests[cells[0][1]].source)
        freeze_guard(wave, shas, root)
        frozen = True
        print(f"freeze OK: tag {wave.tag} @ {shas.bank_sha[:8]}…")

    dry = args.dry_run
    for model, config_id in cells:
        manifest = manifests[config_id]
        out_dir = _cell_dir(root, wave, model, config_id)
        if dry:
            # The dry-run shows the argv shape: an mcp config is rendered
            # per-item at run time, so a placeholder keeps the preview
            # usable without requiring the template's ${VARS} in env.
            mcp_preview = Path("<mcp-config>") if manifest.mcp_template is not None else None
            argv = build_argv(manifest.surface, model, manifest.max_turns,
                              manifest.system_prompt, mcp_preview, "<prompt>")
            print(f"[dry] {model} x {manifest.id}: {' '.join(argv)}")
            continue
        mcp_config = (
            manifest.resolve_mcp_config() if manifest.mcp_template is not None else None
        )
        _run_matrix_cell(
            root=root, wave=wave, bank=bank, protocol=protocol, manifest=manifest,
            model=model, out_dir=out_dir, mcp_config=mcp_config,
            only_items=only_items, shas=shas, frozen=frozen,
        )
    print("run completata." if not dry else "dry-run completata.")
    return 0


def _run_matrix_cell(
    root: Path,
    wave: Wave,
    bank: Bank,
    protocol,
    manifest: Manifest,
    model: str,
    out_dir: Path,
    mcp_config: dict | None,
    only_items: set[str] | None,
    shas: Shas | None,
    frozen: bool,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "wave.json").write_text(
        json.dumps(
            {
                "wave": wave.id,
                "tag": wave.tag,
                "frozen": frozen,
                "shas": shas.to_dict() if shas else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    outcomes: dict[str, RunOutcome] = {}
    for item in bank.items:
        if only_items and item.id not in only_items:
            continue
        outcome = run_cell(
            manifest=manifest, model=model, item_id=item.id, prompt=item.prompt,
            protocol=protocol, out_dir=out_dir / item.id, mcp_config=mcp_config,
        )
        outcomes[item.id] = outcome
        (out_dir / item.id / "outcome.json").write_text(
            json.dumps(
                {**outcome.to_dict(), "answer": outcome.answer,
                 "n_tool_results": len(outcome.tool_results)},
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"  {item.id:<8} {'ok' if outcome.ok else 'EXCLUDED'} "
              f"attempts={outcome.attempts}")

    answers = {iid: oc.answer for iid, oc in outcomes.items() if oc.ok}
    tool_texts = {
        iid: "\n".join(oc.tool_results) for iid, oc in outcomes.items() if oc.ok
    }
    _write_verdicts(bank, protocol, answers, tool_texts, out_dir)
    scorecard = build_scorecard(
        bank=bank, model=model, config_id=manifest.id, answers=answers,
        tool_texts=tool_texts, protocol=protocol,
        attempts={iid: oc.attempts for iid, oc in outcomes.items()},
        excluded=sum(1 for oc in outcomes.values() if oc.excluded),
    )
    (out_dir / "scorecard.json").write_text(
        json.dumps(scorecard.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "discrimination.json").write_text(
        json.dumps(discrimination_report(bank, answers), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(scorecard.render())


def _write_verdicts(bank, protocol, answers, tool_texts, out_dir: Path) -> None:
    for item in bank.items:
        if item.id not in answers:
            continue
        answer = answers[item.id]
        if item.layer == "Q":
            verdict = score_q(item, answer, protocol)
            verdict["passed"] = verdict["matched"]  # paired-comparison contract
        else:
            mechanical = None
            if item.has_mechanical_expectation():
                from benchmarks.limes.protocol.gemelle import score_s

                mechanical = score_s(item, answer)
            verdict = {
                "item_id": item.id,
                "construct": item.construct,
                "mechanical": mechanical,
                "provenance": provenance_answer(
                    answer, tool_texts.get(item.id)
                ),
                "passed": bool(mechanical and mechanical["passed"]),
            }
        (out_dir / item.id / "verdict.json").write_text(
            json.dumps(verdict, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )


def _load_cell_verdicts(cell: Path) -> dict[str, dict]:
    verdicts: dict[str, dict] = {}
    for verdict_path in sorted(cell.glob("*/verdict.json")):
        payload = json.loads(verdict_path.read_text(encoding="utf-8"))
        verdicts[verdict_path.parent.name] = payload
    return verdicts


def cmd_score(args: argparse.Namespace) -> int:
    root = Path(args.root)
    cell = Path(args.cell)
    protocol, bank, _wave, _manifests = _load_context(root, None)
    verdicts = _load_cell_verdicts(cell)
    if not verdicts:
        raise SystemExit(f"nessun verdict.json sotto {cell}")
    answers = {}
    tool_texts = {}
    attempts = {}
    excluded = 0
    for item_id, verdict in verdicts.items():
        outcome_path = cell / item_id / "outcome.json"
        if not outcome_path.is_file():
            continue
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        if outcome.get("ok"):
            answers[item_id] = outcome.get("answer", "")
            # Re-score without transcript: fidelity stays n/d, never 0.0 —
            # absence of evidence here is not unfaithfulness.
            tool_texts[item_id] = None
        # R must reflect what actually happened (attempts and exclusions
        # live in outcome.json): recomputing without it would fabricate
        # mean_attempts=1.0 and excluded_rate=0 in the persisted scorecard.
        if outcome.get("attempts") is not None:
            attempts[item_id] = int(outcome["attempts"])
        if outcome.get("excluded"):
            excluded += 1
    scorecard = build_scorecard(
        bank=bank, model=cell.parent.name, config_id=cell.name, answers=answers,
        tool_texts=tool_texts, protocol=protocol, attempts=attempts,
        excluded=excluded,
    )
    print(scorecard.render())
    (cell / "scorecard.json").write_text(
        json.dumps(scorecard.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    pa, pb = Path(args.cell_a), Path(args.cell_b)
    va = _load_cell_verdicts(pa)
    vb = _load_cell_verdicts(pb)
    if not va or not vb:
        raise SystemExit("entrambe le celle devono contenere verdict.json")
    # A cell is (wave/)/model/config: the model must appear in the label,
    # or comparing two models on the same config reads "bare vs bare".
    def _label(p: Path) -> str:
        return f"{p.parent.name}/{p.name}"

    comparison = compare_cells(_label(pa), _label(pb), va, vb)
    print(comparison.render())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="limes")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", default=str(_default_root()),
                       help="radice del benchmark (default: benchmarks/limes)")

    p_plan = sub.add_parser("plan", help="mostra matrice, bank e stato freeze")
    add_common(p_plan)
    p_plan.add_argument("--wave", default=None)
    p_plan.add_argument("--models", default=None)
    p_plan.add_argument("--configs", default=None)
    p_plan.set_defaults(func=cmd_plan)

    p_check = sub.add_parser("check", help="valida bank, protocollo e manifesti")
    add_common(p_check)
    p_check.set_defaults(func=cmd_check)

    p_run = sub.add_parser("run", help="esegue la matrice con freeze guard")
    add_common(p_run)
    p_run.add_argument("--wave", required=True)
    p_run.add_argument("--models", default=None)
    p_run.add_argument("--configs", default=None)
    p_run.add_argument("--only-items", dest="only_items", default=None)
    p_run.add_argument("--dry-run", dest="dry_run", action="store_true")
    p_run.add_argument("--allow-unfrozen", dest="allow_unfrozen", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_score = sub.add_parser("score", help="scorecard da una cella eseguita")
    add_common(p_score)
    p_score.add_argument("--cell", required=True)
    p_score.set_defaults(func=cmd_score)

    p_cmp = sub.add_parser("compare", help="confronto paired fra due celle")
    add_common(p_cmp)
    p_cmp.add_argument("--cell-a", required=True)
    p_cmp.add_argument("--cell-b", required=True)
    p_cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
