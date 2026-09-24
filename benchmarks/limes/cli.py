"""LIMES CLI: plan / check / run / score / compare.

    python -m benchmarks.limes.cli plan    [--root benchmarks/limes]
    python -m benchmarks.limes.cli check   --wave waves/wave-0.yaml
    python -m benchmarks.limes.cli run     --wave waves/wave-0.yaml [--dry-run]
                                           [--models m1,m2] [--configs c1,c2]
                                           [--only-items id1,id2]
                                           [--allow-unfrozen]
                                           [--with-judges]
    python -m benchmarks.limes.cli score   --cell results/wave-0/<model>/<config>
    python -m benchmarks.limes.cli compare --cell-a ... --cell-b ...
    python -m benchmarks.limes.cli analyze --wave wave-1

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

from benchmarks.limes.analysis.compare import (
    compare_cells,
    contamination_report,
    wave_analysis,
)
from benchmarks.limes.analysis.power import PowerError, enforce, power_check
from benchmarks.limes.analysis.scorecard import (
    build_scorecard,
    construct_key,
    discrimination_report,
)
from benchmarks.limes.bank.schema.item import Bank, load_bank
from benchmarks.limes.bank.schema.validate import print_wave_reports, validate_bank, validate_waves
from benchmarks.limes.protocol.citations import provenance_answer
from benchmarks.limes.protocol.rules import load_protocol
from benchmarks.limes.protocol.scorers_q import score_q
from benchmarks.limes.protocol import judges as judge_panel
from benchmarks.limes.runner.executor import RateLimited, build_argv, plugin_mcp_config, run_cell
from benchmarks.limes.runner.refs import materialize
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
    wave = load_wave(wave_file) if wave_file else None
    if wave is not None:
        bank = load_bank(root / "bank", wave.bank_slices, wave.require_validity, wave.excluded)
    else:
        bank = load_bank(root / "bank")
    manifests = _load_manifests(root / "configs")
    return protocol, bank, wave, manifests


def scored_items(bank: Bank) -> set[str]:
    """Items that enter the dimensions and the primary endpoint: every item
    except paraphrase probes, which restate another item and would count
    the same question twice (they feed only the contamination report)."""
    return {i.id for i in bank.items if not i.paraphrase_of}


def _frozen_paths(root: Path, wave: Wave, manifests: dict[str, Manifest], cells) -> list[Path]:
    """Everything a run reads that the tag must have frozen."""
    bank_dir = root / "bank"
    paths = [bank_dir / rel for rel in wave.bank_slices] or [bank_dir]
    if (bank_dir / "validity").is_dir():
        paths.append(bank_dir / "validity")
    paths.append(root / "protocol")
    for config_id in sorted({c for _, c in cells}):
        manifest = manifests[config_id]
        paths.append(manifest.source)
        if manifest.mcp_template is not None:
            paths.append(manifest.mcp_template)
    return paths


def _runner_commit(root: Path) -> dict:
    """The instrument's own code (runner/analysis) is outside the five SHA:
    record the commit and whether the worktree was clean, so a number can
    always be traced to the code that produced it."""
    import subprocess

    def _q(args):
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    return {"commit": _q(["rev-parse", "HEAD"]),
            "dirty": bool(_q(["status", "--porcelain", "--", "."]))}


def _coverage(bank: Bank) -> dict[str, dict]:
    table: dict[str, dict] = {}
    for item in bank.items:
        if item.paraphrase_of:
            continue
        key = construct_key(item.construct)
        row = table.setdefault(key, {"n": 0, "types": {}})
        row["n"] += 1
        if item.reasoning_type:
            row["types"][item.reasoning_type] = row["types"].get(item.reasoning_type, 0) + 1
    return table


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
    judges = (f"dichiarati {', '.join(protocol.judge.models)} (solo con --with-judges)"
              if protocol.judge_enabled else "meccanico-only")
    print(f"protocollo v{protocol.version} (seed {protocol.seed}); giudici: {judges}")
    coverage = _coverage(bank)
    print("copertura (item punteggiati per dimensione; tipi LegalBench):")
    for key in ("C", "P", "H", "A", "U", "M"):
        row = coverage.get(key, {"n": 0, "types": {}})
        types = ", ".join(f"{t}={n}" for t, n in sorted(row["types"].items())) or "-"
        print(f"  {key}  n={row['n']:<4} {types}")
    probes = [i for i in bank.items if i.paraphrase_of]
    if probes:
        print(f"sonde contaminazione: {len(probes)} parafrasi (fuori dalle dimensioni)")
    status_power = 0
    if wave is not None:
        report = power_check(wave.analysis.get("power"), len(scored_items(bank)))
        if report["declared"]:
            verdict = "OK" if report["satisfied"] else "INSUFFICIENTE"
            print(f"potenza {verdict}: {report['n_items']} item punteggiati, richiesti "
                  f"{report['required_items']} (NI appaiata); discordanti attesi "
                  f"{report['expected_discordant']} (min {report['min_discordant']}); "
                  f"McNemar esatto a split {report['mcnemar_split']}: "
                  f"{report['mcnemar_power_at_split']}")
            if not report["satisfied"]:
                status_power = 1
    print(f"matrice: {len(cells)} celle")
    for model, config_id in cells:
        manifest = manifests[config_id]
        print(f"  {model:<20} x {manifest.id:<32} surface={manifest.surface} "
              f"ref={manifest.ref or '-'} turns={manifest.max_turns}")
    status = freeze_status(root / "bank", root / "protocol")
    for label, info in status.items():
        state = "FROZEN" if info["frozen"] else "pending (committare + tag, DESIGN §2)"
        print(f"freeze {label:<9} {info['path']:<28} {state}")
    return status_power


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    ok = True
    try:
        summary = validate_bank(root / "bank")
        print("bank OK:", ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))
        print_wave_reports(validate_waves(root / "bank"))
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
    try:
        enforce(wave.analysis.get("power"), len(scored_items(bank)))
    except PowerError as exc:
        if not (args.dry_run or args.allow_unfrozen):
            raise SystemExit(f"run rifiutata: {exc}")
        print(f"ATTENZIONE: {exc}")
    if args.with_judges:
        judge_panel.enforce_heterogeneous(protocol.judge.models, sorted({m for m, _ in cells}))
        if not protocol.judge_enabled:
            raise SystemExit("--with-judges: nessun giudice dichiarato nel protocollo")

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
        freeze_guard(wave, shas, root, _frozen_paths(root, wave, manifests, cells))
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
            plugin_preview = Path("<plugin-dir>") if manifest.surface == "plugin" else None
            argv = build_argv(manifest.surface, model, manifest.max_turns,
                              manifest.system_prompt, mcp_preview, "<prompt>",
                              plugin_dir=plugin_preview, tools=manifest.tools)
            print(f"[dry] {model} x {manifest.id}: {' '.join(argv)}")
            continue
        plugin_dir = None
        if manifest.ref is not None:
            # The enhancement runs AT ITS REF (git archive), never from the
            # working tree: v2.14 and v3-beta must be different programs.
            plugin_dir = materialize(manifest.ref, root, root / "results" / ".refs")
        mcp_config = None
        if manifest.mcp_template is not None:
            import os

            mcp_config = manifest.resolve_mcp_config({
                **os.environ,
                "LIMES_REF_DIR": str(plugin_dir) if plugin_dir else "",
                "LIMES_LEGALIT_PROFILE": manifest.profile or "full",
            })
        elif manifest.surface == "plugin" and plugin_dir is not None:
            mcp_config = plugin_mcp_config(plugin_dir, manifest.profile)
        _run_matrix_cell(
            root=root, wave=wave, bank=bank, protocol=protocol, manifest=manifest,
            model=model, out_dir=out_dir, mcp_config=mcp_config,
            only_items=only_items, shas=shas, frozen=frozen,
            plugin_dir=plugin_dir if manifest.surface == "plugin" else None,
            with_judges=args.with_judges, resume=args.resume,
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
    plugin_dir: Path | None = None,
    with_judges: bool = False,
    resume: bool = False,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "wave.json").write_text(
        json.dumps(
            {
                "wave": wave.id,
                "tag": wave.tag,
                "frozen": frozen,
                "shas": shas.to_dict() if shas else None,
                "runner": _runner_commit(root),
                "ref": manifest.ref,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    outcomes: dict[str, dict] = {}
    for item in bank.items:
        if only_items and item.id not in only_items:
            continue
        outcome_path = out_dir / item.id / "outcome.json"
        if resume and outcome_path.is_file():
            # Resume: an item already answered in THIS cell is not re-asked
            # (a long matrix survives interruptions; re-asking would also
            # change the sample the scorecard is computed on).
            outcomes[item.id] = json.loads(outcome_path.read_text(encoding="utf-8"))
            continue
        try:
            outcome = run_cell(
                manifest=manifest, model=model, item_id=item.id, prompt=item.prompt,
                protocol=protocol, out_dir=out_dir / item.id, mcp_config=mcp_config,
                plugin_dir=plugin_dir,
            )
        except RateLimited as exc:
            # Account quota, not a property of the cell: stop cleanly, the
            # items answered so far are kept for --resume.
            raise SystemExit(f"run sospesa: {exc}") from None
        record = {**outcome.to_dict(), "answer": outcome.answer,
                  "n_tool_results": len(outcome.tool_results),
                  "tool_text": "\n".join(outcome.tool_results) if outcome.tool_results else None}
        outcomes[item.id] = record
        outcome_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        cost = f" ${outcome.cost_usd:.3f}" if outcome.cost_usd is not None else ""
        print(f"  {item.id:<10} {'ok' if outcome.ok else 'EXCLUDED'} "
              f"attempts={outcome.attempts} tools={len(outcome.tool_calls)}{cost}", flush=True)

    answers = {iid: oc["answer"] for iid, oc in outcomes.items() if oc.get("ok")}
    # No tool results -> fidelity n/d (None), never 0.0: the bare surface has
    # nothing to be faithful to, and a tool surface that received nothing
    # is a broken run, not an unfaithful one (citations.py contract).
    tool_texts = {iid: oc.get("tool_text") for iid, oc in outcomes.items() if oc.get("ok")}
    _write_verdicts(bank, protocol, answers, tool_texts, out_dir)
    if with_judges:
        _judge_cell(bank, protocol, answers, out_dir)
    scorecard = build_scorecard(
        bank=bank, model=model, config_id=manifest.id, answers=answers,
        tool_texts=tool_texts, protocol=protocol,
        attempts={iid: int(oc.get("attempts") or 0) for iid, oc in outcomes.items()},
        excluded=sum(1 for oc in outcomes.values() if oc.get("excluded")),
        run_meta=outcomes,
        scored=scored_items(bank),
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


def _residual_rubrics(item) -> dict[str, str]:
    return {r.id: r.text for r in item.rubrics if not r.mechanical}


def _judge_cell(bank: Bank, protocol, answers: dict[str, str], out_dir: Path) -> None:
    """Residual-rubric judging for every answered S item (B2)."""
    for item in bank.items:
        if item.layer != "S" or item.id not in answers:
            continue
        rubrics = _residual_rubrics(item)
        if not rubrics:
            continue
        result = judge_panel.judge_item(
            item_id=item.id, question=item.prompt, answer=answers[item.id],
            rubrics=rubrics, judges=protocol.judge.models, seed=protocol.seed,
            replicas=protocol.judge.replicas,
        )
        (out_dir / item.id / "judge.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
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


def _wave_cells(root: Path, wave: Wave) -> dict[tuple[str, str], Path]:
    base = wave_paths(root)["results"] / wave.id
    cells: dict[tuple[str, str], Path] = {}
    for model in wave.models:
        for config_id in wave.configs:
            cell = base / model / config_id
            if (cell / "scorecard.json").is_file():
                cells[(model, config_id)] = cell
    return cells


def gold_key(item_id: str, rubric_id: str, answer: str) -> str:
    import hashlib

    return hashlib.sha256(f"{item_id}|{rubric_id}|{answer}".encode("utf-8")).hexdigest()[:16]


def _judge_consensus(cells: dict[tuple[str, str], Path]) -> dict[str, bool]:
    consensus: dict[str, bool] = {}
    for cell in cells.values():
        for judge_path in cell.glob("*/judge.json"):
            result = json.loads(judge_path.read_text(encoding="utf-8"))
            outcome = json.loads((judge_path.parent / "outcome.json").read_text(encoding="utf-8"))
            for rid, verdict in result.get("consensus", {}).items():
                if verdict is not None:
                    consensus[gold_key(result["item_id"], rid, outcome.get("answer", ""))] = verdict
    return consensus


def cmd_analyze(args: argparse.Namespace) -> int:
    root = Path(args.root)
    protocol, bank, wave, _manifests = _load_context(root, _wave_file(root, args.wave))
    cells = _wave_cells(root, wave)
    if not cells:
        raise SystemExit(f"nessuna cella eseguita per {wave.id}")
    verdicts = {key: _load_cell_verdicts(cell) for key, cell in cells.items()}
    scored = scored_items(bank)
    print(f"wave {wave.id}: {len(cells)} celle eseguite su {len(wave.models) * len(wave.configs)}")
    print(f"{'modello':<20} {'config':<34} " + " ".join(f"{k:>6}" for k in "CPHAUM") + "   costo$")
    for (model, config_id), cell in sorted(cells.items()):
        card = json.loads((cell / "scorecard.json").read_text(encoding="utf-8"))
        dims = card["dimensions"]
        rates = []
        for key in "CPHAUM":
            rate = (dims.get(key) or {}).get("rate")
            rates.append("   n/d" if rate is None else f"{rate:6.1%}")
        cost = card["reliability"].get("cost_usd")
        suffix = f"   {cost:.2f}" if cost is not None else "   n/d"
        print(f"{model:<20} {config_id:<34} " + " ".join(rates) + suffix)
    report = {"wave": wave.id, "analysis": wave_analysis(verdicts, wave.analysis, scored)}
    for model, out in report["analysis"]["models"].items():
        print(f"\n[{model}] famiglia primaria vs {wave.analysis.get('primary', {}).get('baseline')} (Holm):")
        for treatment, row in out["primary"].items():
            if "p" not in row:
                print(f"  {treatment:<34} {row.get('state')}")
                continue
            print(f"  {treatment:<34} {row['baseline_rate']:.1%} -> {row['treatment_rate']:.1%}  "
                  f"(+{row['treatment_only']}/-{row['baseline_only']})  p={row['p']:.4f}  "
                  f"p_holm={row['p_holm']:.4f}  {'RIFIUTA H0' if row['rejected'] else 'non significativo'}")
        ni = out["non_inferiority"]
        if ni:
            print(f"  NI {ni['treated']} vs {ni['control']}: delta={ni['risk_difference']:+.3f} "
                  f"CI95=[{ni['ci_lower']:+.3f}, {ni['ci_upper']:+.3f}] margine -{ni['margin']} -> "
                  f"{'NON INFERIORE' if ni['non_inferior'] else 'non dimostrata'}")
    pairs = [(i.paraphrase_of, i.id) for i in bank.items if i.paraphrase_of]
    if pairs and protocol.contamination_max_gap is not None:
        report["contamination"] = {}
        print("\ncontaminazione (originali vs parafrasi):")
        for key, cell_verdicts in sorted(verdicts.items()):
            c = contamination_report(cell_verdicts, pairs, protocol.contamination_max_gap)
            report["contamination"]["/".join(key)] = c
            if c["pairs"]:
                print(f"  {'/'.join(key):<56} {c['original_rate']:.0%} vs {c['paraphrase_rate']:.0%} "
                      f"gap={c['gap']:+.2f} {'SEGNALATO' if c['flag'] else 'ok'}")
    gold_path = root / (protocol.judge.gold or "")
    if protocol.judge.gold and gold_path.is_file():
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        cal = judge_panel.calibration(gold.get("rows", []), _judge_consensus(cells),
                                      protocol.judge.calibration)
        report["judge_calibration"] = cal
        print(f"\ncalibrazione giudici: {'OK' if cal['calibrated'] else 'NON calibrati'} "
              f"(riferimento n={cal['reference_n']}, kappa={cal['judge_kappa']}, EO gap={cal['eo_gap']})")
    else:
        print("\ngiudici: nessun gold set umano — verdetti residui NON inferenziali")
    out_path = wave_paths(root)["results"] / wave.id / "analysis.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nanalisi scritta in {out_path}")
    return 0


def cmd_gold_export(args: argparse.Namespace) -> int:
    """Deterministic sample of (answer, residual rubric) pairs for two human
    labellers. Group = the configuration that produced the answer (the
    Equal Opportunity check compares the judge's recall across groups)."""
    import random

    root = Path(args.root)
    protocol, bank, wave, _manifests = _load_context(root, _wave_file(root, args.wave))
    cells = _wave_cells(root, wave)
    candidates = []
    for (model, config_id), cell in sorted(cells.items()):
        for item in bank.items:
            rubrics = _residual_rubrics(item) if item.layer == "S" else {}
            outcome_path = cell / item.id / "outcome.json"
            if not rubrics or not outcome_path.is_file():
                continue
            answer = json.loads(outcome_path.read_text(encoding="utf-8")).get("answer", "")
            if not answer:
                continue
            for rid, text in sorted(rubrics.items()):
                candidates.append({
                    "key": gold_key(item.id, rid, answer), "item_id": item.id,
                    "rubric_id": rid, "criterio": text, "domanda": item.prompt,
                    "risposta": answer, "group": config_id, "model": model,
                    "human": [],
                })
    rng = random.Random(protocol.seed)
    rng.shuffle(candidates)
    sample = candidates[: args.n]
    out = root / "bank" / "gold" / "judge-gold.todo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "$comment": "Due giuristi etichettano ogni riga in modo indipendente: human = "
                    "[etichetta_1, etichetta_2] con true/false. Rinominare in "
                    "judge-gold.json a etichettatura completa.",
        "rows": sample,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(sample)} righe da etichettare -> {out}")
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
    p_run.add_argument("--with-judges", dest="with_judges", action="store_true",
                       help="giudica le rubriche residue col pannello del protocollo")
    p_run.add_argument("--resume", action="store_true",
                       help="non ripete gli item già risposti nella cella")
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

    p_an = sub.add_parser("analyze", help="analisi pre-registrata di una wave eseguita")
    add_common(p_an)
    p_an.add_argument("--wave", required=True)
    p_an.set_defaults(func=cmd_analyze)

    p_gold = sub.add_parser("gold-export", help="campione di risposte da etichettare (gold set)")
    add_common(p_gold)
    p_gold.add_argument("--wave", required=True)
    p_gold.add_argument("--n", type=int, default=40)
    p_gold.set_defaults(func=cmd_gold_export)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
