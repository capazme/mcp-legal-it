#!/usr/bin/env python3
"""Measure what mcp-legal-it costs the model in tokens, before and after a change.

A measuring instrument, nothing else: it changes no shipped behaviour and calls
no LLM API. Two measures, each written as JSON so two runs can be diffed.

    # 1. tools/list as a client receives it (deterministic, no network)
    python scripts/token_report.py tools
    python scripts/token_report.py tools --profile normativa --json /tmp/normativa.json
    python scripts/token_report.py tools --include-tags normativa,giurisprudenza,autorita

    # 2. the answers of a fixed set of calls, replayed from a recorded tape
    python scripts/token_report.py outputs --record             # once, network
    python scripts/token_report.py outputs --json /tmp/out.json  # offline

    # 3. before/after: any two JSON reports of the same measure
    python scripts/token_report.py compare base.json head.json

``tools`` builds the server in-process from this checkout (``plugin/server``)
and reads ``initialize`` and ``tools/list`` through the FastMCP in-memory client,
exactly the JSON a client gets. ``--profile`` sets ``LEGAL_PROFILE`` before the
import; ``--include-tags``/``--exclude-tags`` go through ``crea_server``.

"Model-visible" means name + description + inputSchema (compact JSON), which is
what a client hands the model for each tool; ``wire`` is the whole tool object,
outputSchema, annotations and ``_meta`` included.

``outputs`` replays the tape with the transport of ``replay_mcp_outputs.py``
(pinned clock, disk caches off, fixed hash seed), so a run without ``--record``
never touches the network. The worker drops every ``LEGAL_*``/``AKN_*`` variable
of the shell, so only the pinned ones reach the server. NEVER COMMIT THE TAPE: it
holds third-party content (see ``replay_mcp_outputs.py``); the default path is
git-ignored and a path inside the repo that git does not ignore is refused.
Record it on the base ref before a cut. A request missing from the tape is
counted per call: ``outputs`` and ``compare`` then exit 1, because a failed
replay is not a smaller answer.

Token counts are ESTIMATES. No tokenizer for Claude models runs offline, so the
script uses the same rule as the 27 Oct 2026 analysis: characters / 3.5 for prose
(descriptions, result text) and characters / 3 for JSON structure. Compare runs
with each other, not with an invoice.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "plugin" / "server"

PROSE_CHARS_PER_TOKEN = 3.5
JSON_CHARS_PER_TOKEN = 3.0
ESTIMATOR = (f"estimate: prose chars / {PROSE_CHARS_PER_TOKEN}, JSON chars / {JSON_CHARS_PER_TOKEN} "
             "(no offline tokenizer for Claude models)")

#: The fixed calls of the output measure. Stable documents only, so a later
#: re-record answers the same: change this list and the tape must be recorded again.
OUTPUT_CALLS: list[tuple[str, dict]] = [
    # norms
    ("cite_law", {"reference": "art. 1284 c.c."}),
    ("cite_law", {"reference": "art. 6 GDPR"}),
    ("fetch_full_act", {"reference": "legge 20 maggio 1970, n. 300"}),
    # case law: search, then read
    ("cerca_giurisprudenza", {"query": "danno biologico terminale"}),
    ("leggi_sentenza", {"numero": 21332, "anno": 2024, "archivio": "civile"}),
    # CGUE: C-311/19 Bonver Win (the CELEX replay_mcp_outputs.py already uses)
    ("leggi_sentenza_cgue", {"cellar_uri": "http://publications.europa.eu/resource/celex/62019CJ0311"}),
    # CeRDEF: Cass. SS.UU. 24823/2015 (GUID from tests/unit/test_cerdef_live.py)
    ("cerdef_leggi_provvedimento", {"guid": "{B0F76E21-B5FA-4415-9D1D-44FF7B5741C1}"}),
    # Gazzetta Ufficiale: D.Lgs. 101/2018 (tests/unit/test_gazzetta_live.py)
    ("leggi_atto_gazzetta", {"codice_redazionale": "18G00129", "data_pubblicazione": "2018-09-04"}),
    # calculators (local, the tape is not used)
    ("interessi_legali", {"capitale": 10000, "data_inizio": "2020-01-01", "data_fine": "2025-12-31"}),
    ("rivalutazione_monetaria", {"capitale": 10000, "data_inizio": "2015-01-01", "data_fine": "2025-12-31"}),
    ("danno_biologico_micro", {"percentuale_invalidita": 5, "eta_vittima": 40}),
    ("parcella_avvocato_civile", {"valore_causa": 30000}),
]

#: Description lines that open a repeated block (Vigenza/Precisione) or a usage note.
BLOCK_LABELS = {
    "vigenza": ("Vigenza",),
    "precisione": ("Precisione",),
    "usage": ("Restituisce", "Usa questo", "USARE quando", "Chaining", "NON usare", "Dopo questo tool"),
}
_NEXT_LABEL = re.compile(r"\s*[A-Z][A-Za-zÀ-ú ]{2,25}:")
_ADDL_FALSE = '"additionalProperties":false'
#: Process switches that narrow the surface besides LEGAL_PROFILE: recorded in the report.
SWITCHES = ("LEGAL_PREVIGENTE", "LEGAL_BROCARDI")


# ---------------------------------------------------------------------------
# Estimation helpers
# ---------------------------------------------------------------------------


def compact(obj) -> int:
    """Length of ``obj`` as compact JSON, non-ASCII kept (what a JSON-RPC frame carries)."""
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def tokens(prose: int, json_chars: int) -> int:
    return round(prose / PROSE_CHARS_PER_TOKEN + json_chars / JSON_CHARS_PER_TOKEN)


def schema_prose(obj) -> int:
    """Characters of every ``description`` string in a JSON schema, at any depth."""
    if isinstance(obj, dict):
        return sum(len(v) if k == "description" and isinstance(v, str) else schema_prose(v)
                   for k, v in obj.items())
    if isinstance(obj, list):
        return sum(schema_prose(v) for v in obj)
    return 0


def value_prose(obj) -> int:
    """Characters of every string value in a result (all of it is content)."""
    if isinstance(obj, str):
        return len(obj)
    if isinstance(obj, dict):
        return sum(value_prose(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(value_prose(v) for v in obj)
    return 0


def value_tokens(obj) -> int:
    if obj is None:
        return 0
    prose = value_prose(obj)
    return tokens(prose, compact(obj) - prose)


def block_chars(description: str, labels: tuple[str, ...]) -> int:
    """Characters of the blocks opened by ``labels``: the label line and its continuation lines.

    A block runs until a blank line or the next ``Label:`` line, as in the 27 Oct
    analysis, so an unlabelled sentence right after it is counted in: an upper bound.
    """
    total = 0
    lines = description.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith(labels):
            total += len(lines[i]) + 1
            j = i + 1
            while j < len(lines) and lines[j].strip() and not _NEXT_LABEL.match(lines[j]):
                total += len(lines[j]) + 1
                j += 1
            i = j
        else:
            i += 1
    return total


def anyof_null_overhead(obj) -> tuple[int, int]:
    """(count, chars) of ``anyOf [{X}, {"type": "null"}]`` (+ ``default: null``) over plain ``{X}``."""
    count = chars = 0
    if isinstance(obj, dict):
        branches = obj.get("anyOf")
        if isinstance(branches, list) and len(branches) == 2 and {"type": "null"} in branches:
            other = next(b for b in branches if b != {"type": "null"})
            plain = {k: v for k, v in obj.items() if k != "anyOf"}
            plain.update(other)
            if plain.get("default", 0) is None:
                plain.pop("default")
            count, chars = 1, compact(obj) - compact(plain)
        for v in obj.values():
            c, n = anyof_null_overhead(v)
            count, chars = count + c, chars + n
    elif isinstance(obj, list):
        for v in obj:
            c, n = anyof_null_overhead(v)
            count, chars = count + c, chars + n
    return count, chars


def whitespace_waste(text: str) -> int:
    return len(text) - len(re.sub(r"\n[ \t]+", "\n", re.sub(r"[ \t]{2,}", " ", text)))


def git_state() -> dict:
    def git(*args: str) -> str:
        out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
        return out.stdout.strip()

    return {"sha": git("rev-parse", "--short", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


# ---------------------------------------------------------------------------
# tools: the tools/list surface
# ---------------------------------------------------------------------------


def _import_server():
    sys.path.insert(0, str(PACKAGE))
    import mcp_legal_it
    import mcp_legal_it.server as server

    if not Path(mcp_legal_it.__file__).resolve().is_relative_to(PACKAGE.resolve()):
        sys.exit(f"imported {mcp_legal_it.__file__}, not this checkout's {PACKAGE}")
    return server


async def _read_surface(server_obj, stock) -> tuple[str, list[dict], dict[str, object]]:
    from fastmcp import Client

    async with Client(server_obj) as client:
        # FastMCP 3 exposes the InitializeResult, FastMCP 4 the instructions themselves.
        init = getattr(client, "initialize_result", None)
        instructions = (getattr(client, "instructions", None) if init is None else init.instructions) or ""
        listed = await client.list_tools_mcp()
    wire = [t.model_dump(by_alias=True, exclude_none=True, mode="json") for t in listed.tools]
    # Module and tags come from the stock server: a crea_server subset mounts it, and a
    # mounted tool has no ``fn``. Names are the same (the mount has no namespace).
    internal = {t.name: t for t in await stock.list_tools()}
    return instructions, wire, internal


def measure_tools(args) -> dict:
    # Only --profile narrows the measure: a switch inherited from the shell would change
    # the numbers without showing up in the report.
    os.environ.pop("LEGAL_PROFILE", None)
    if args.profile:
        os.environ["LEGAL_PROFILE"] = args.profile
    switches = {k: os.environ[k] for k in SWITCHES if k in os.environ}
    server = _import_server()
    include = [t for t in (args.include_tags or "").split(",") if t]
    exclude = [t for t in (args.exclude_tags or "").split(",") if t]
    target = server.mcp
    if include or exclude:
        target = server.crea_server(include_tags=include or None, exclude_tags=exclude or None)
    instructions, wire, internal = asyncio.run(_read_surface(target, server.mcp))

    from mcp_legal_it.tool_taxonomy import KINDS

    rows = []
    # "prose" is the part of "chars" estimated as prose; the rest is JSON structure.
    blocks = collections.defaultdict(lambda: {"count": 0, "chars": 0, "prose": 0})
    for w in wire:
        name = w["name"]
        desc = w.get("description", "") or ""
        schema = w.get("inputSchema", {})
        tool = internal.get(name)
        fn = getattr(tool, "fn", None)
        module = (getattr(fn, "__module__", None) or "?").rsplit(".", 1)[-1]
        tags = sorted(getattr(tool, "tags", None) or [])
        kind = next((t for t in tags if t in KINDS), "?")
        param_prose = schema_prose(schema)
        schema_chars = compact(schema)
        prose = len(desc) + param_prose
        json_chars = schema_chars - param_prose + len(name)
        rows.append({
            "name": name, "module": module, "kind": kind, "tags": tags,
            "params": len(schema.get("properties", {})),
            "description_chars": len(desc), "param_description_chars": param_prose,
            "input_schema_chars": schema_chars,
            "model_chars": len(name) + len(desc) + schema_chars,
            "tokens": tokens(prose, json_chars),
            "wire_chars": compact(w),
        })
        for label, starts in BLOCK_LABELS.items():
            n = block_chars(desc, starts)
            if n:
                blocks[label]["count"] += 1
                blocks[label]["chars"] += n
                blocks[label]["prose"] += n
        accetta = schema.get("properties", {}).get("accetta_precisione")
        if accetta is not None:
            blocks["accetta_precisione"]["count"] += 1
            blocks["accetta_precisione"]["chars"] += compact({"accetta_precisione": accetta}) - 1
            blocks["accetta_precisione"]["prose"] += schema_prose(accetta)
        c, n = anyof_null_overhead(schema)
        blocks["anyof_null"]["count"] += c
        blocks["anyof_null"]["chars"] += n
        n = json.dumps(schema, separators=(",", ":")).count(_ADDL_FALSE)
        blocks["additional_properties_false"]["count"] += n
        blocks["additional_properties_false"]["chars"] += n * (len(_ADDL_FALSE) + 1)
        n = whitespace_waste(desc) + sum(whitespace_waste(p.get("description", ""))
                                         for p in schema.get("properties", {}).values())
        blocks["whitespace"]["count"] += 1 if n else 0
        blocks["whitespace"]["chars"] += n
        blocks["whitespace"]["prose"] += n

    for b in blocks.values():
        b["tokens"] = tokens(b["prose"], b["chars"] - b["prose"])

    def group(key: str) -> dict:
        out: dict[str, dict] = {}
        for r in rows:
            g = out.setdefault(r[key], {"tools": 0, "model_chars": 0, "tokens": 0})
            g["tools"] += 1
            g["model_chars"] += r["model_chars"]
            g["tokens"] += r["tokens"]
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["model_chars"]))

    tools_tokens = sum(r["tokens"] for r in rows)
    totals = {
        "tools": len(rows),
        "model_chars": sum(r["model_chars"] for r in rows),
        "description_chars": sum(r["description_chars"] for r in rows),
        "param_description_chars": sum(r["param_description_chars"] for r in rows),
        "input_schema_chars": sum(r["input_schema_chars"] for r in rows),
        "tokens": tools_tokens,
        "wire_chars": sum(r["wire_chars"] for r in rows),
        "instructions_chars": len(instructions),
        "instructions_tokens": tokens(len(instructions), 0),
        "total_tokens": tools_tokens + tokens(len(instructions), 0),
    }
    import fastmcp

    return {
        "measure": "tools",
        "meta": {**git_state(), "fastmcp": fastmcp.__version__, "profile": args.profile or "full",
                 "switches": switches,
                 "include_tags": include, "exclude_tags": exclude, "estimator": ESTIMATOR},
        "totals": totals,
        "by_kind": group("kind"),
        "by_module": group("module"),
        "blocks": dict(sorted(blocks.items())),
        "tools": sorted(rows, key=lambda r: -r["model_chars"]),
    }


def print_tools(report: dict, top: int) -> None:
    t, m = report["totals"], report["meta"]
    print(f"## tools/list — {m['sha']}{' (dirty)' if m['dirty'] else ''}, profile {m['profile']}"
          + (f", include {m['include_tags']}" if m["include_tags"] else "")
          + (f", exclude {m['exclude_tags']}" if m["exclude_tags"] else "")
          + "".join(f", {k}={v}" for k, v in (m.get("switches") or {}).items())
          + f", fastmcp {m['fastmcp']}\n")
    print(f"_{m['estimator']}_\n")
    print("| Item | Chars | Tokens (est.) |\n|---|---:|---:|")
    print(f"| {t['tools']} tools, model-visible (name + description + inputSchema) "
          f"| {t['model_chars']:,} | {t['tokens']:,} |")
    print(f"| of which tool descriptions | {t['description_chars']:,} | |")
    print(f"| of which parameter descriptions | {t['param_description_chars']:,} | |")
    print(f"| server instructions | {t['instructions_chars']:,} | {t['instructions_tokens']:,} |")
    print(f"| **total sent at session start** | {t['model_chars'] + t['instructions_chars']:,} "
          f"| **{t['total_tokens']:,}** |")
    print(f"| tools/list wire (outputSchema, annotations, _meta too) | {t['wire_chars']:,} | |\n")

    print("### By kind\n\n| Kind | Tools | Chars | Tokens | Share |\n|---|---:|---:|---:|---:|")
    for k, g in report["by_kind"].items():
        print(f"| {k} | {g['tools']} | {g['model_chars']:,} | {g['tokens']:,} "
              f"| {100 * g['model_chars'] / t['model_chars']:.1f}% |")
    print("\n### By module (top 12)\n\n| Module | Tools | Chars | Tokens |\n|---|---:|---:|---:|")
    for k, g in list(report["by_module"].items())[:12]:
        print(f"| {k} | {g['tools']} | {g['model_chars']:,} | {g['tokens']:,} |")
    print(f"\n### Top {top} tools\n\n| Tool | Module | Desc | Params desc | Schema | Chars | Tokens |\n"
          "|---|---|---:|---:|---:|---:|---:|")
    for r in report["tools"][:top]:
        print(f"| {r['name']} | {r['module']} | {r['description_chars']:,} | {r['param_description_chars']:,} "
              f"| {r['input_schema_chars']:,} | {r['model_chars']:,} | {r['tokens']:,} |")
    print("\n### Repeated blocks\n\n| Block | Occurrences | Chars | Tokens |\n|---|---:|---:|---:|")
    for k, b in report["blocks"].items():
        print(f"| {k} | {b['count']} | {b['chars']:,} | {b['tokens']:,} |")


# ---------------------------------------------------------------------------
# outputs: the answers of OUTPUT_CALLS, replayed from a tape
# ---------------------------------------------------------------------------


def _outputs_worker(mode: str, tape: str, out: str) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from replay_mcp_outputs import install_tape_transport, save_tape

    misses: list[str] = []
    recorded = install_tape_transport(mode, tape, misses)
    server = _import_server()

    async def run() -> list[dict]:
        from fastmcp import Client

        results = []
        async with Client(server.mcp) as client:
            for name, call_args in OUTPUT_CALLS:
                before = len(misses)
                try:
                    r = await client.call_tool_mcp(name, call_args)
                    wire = r.model_dump(by_alias=True, exclude_none=True, mode="json")
                except Exception as exc:  # noqa: BLE001 - reported as that call's answer
                    wire = {"isError": True, "content": [{"type": "text", "text": f"exception: {exc!r}"}]}
                results.append({"tool": name, "args": call_args, "wire": wire,
                                "missed_requests": len(misses) - before})
        return results

    results = asyncio.run(run())
    Path(out).write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    if mode == "record":
        save_tape(recorded, tape)


#: Environment variables the server reads (clock, caches, switches, AKN export).
_SERVER_ENV_PREFIXES = ("LEGAL_", "AKN_")
#: Default tape: inside the repo, but under .replay-tapes/, which git ignores.
DEFAULT_TAPE = REPO / ".replay-tapes" / "token-calls.json.gz"


def _worker_env(pinned: dict[str, str]) -> dict[str, str]:
    """The shell's environment without any server variable, plus the pinned ones.

    A ``LEGAL_TODAY`` or ``LEGAL_PROFILE`` left in the shell would change the answers
    while the report still names the pinned clock.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith(_SERVER_ENV_PREFIXES)}
    return {**env, **pinned}


def _refuse_a_committable_tape(tape: Path) -> None:
    """A tape holds third-party content: inside any git repo it must be on an ignored path.

    The repo is the one that contains the tape, not this checkout: from a worktree,
    a path in the main checkout or in a superproject belongs to that repo.
    """
    anchor = tape.parent
    while not anchor.exists():
        anchor = anchor.parent
    top = subprocess.run(["git", "-C", str(anchor), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if top.returncode != 0:
        return  # not inside a git repo
    ignored = subprocess.run(["git", "-C", top.stdout.strip(), "check-ignore", "-q", str(tape)],
                             capture_output=True).returncode == 0
    if not ignored:
        sys.exit(f"refusing tape {tape}: it is inside the git repo {top.stdout.strip()} on a path git does "
                 f"not ignore (use {DEFAULT_TAPE.relative_to(REPO)} or a path outside any repo)")


def _call_problem(row: dict) -> str:
    """Why a replayed answer is not a measurement of the code ('' when it is one)."""
    missed = row.get("missed_requests", 0) or (1 if row.get("not_on_tape") else 0)
    if missed:
        return f"{missed} request(s) not on tape"
    return "error" if row.get("is_error") else ""


def output_row(r: dict) -> dict:
    """The sizes of one replayed call, from the worker's ``{tool, args, wire, missed_requests}``."""
    w = r["wire"]
    text = "".join(b.get("text", "") for b in w.get("content", []) if b.get("type") == "text")
    structured = w.get("structuredContent")
    meta = w.get("_meta")
    try:  # calculators answer JSON: their text is the structuredContent serialized
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    text_tokens = value_tokens(parsed) if isinstance(parsed, (dict, list)) else tokens(len(text), 0)
    duplicate = structured is not None and (structured == {"result": text} or structured == parsed)
    return {
        "call": f"{r['tool']} {json.dumps(r['args'], ensure_ascii=False)}",
        "tool": r["tool"], "args": r["args"], "is_error": bool(w.get("isError")),
        "missed_requests": r["missed_requests"],
        "text_chars": len(text), "text_tokens": text_tokens,
        "structured_chars": compact(structured) if structured is not None else 0,
        "structured_tokens": value_tokens(structured),
        "structured_duplicates_text": duplicate,
        "meta_chars": compact(meta) if meta is not None else 0,
        "wire_chars": compact(w),
    }


def measure_outputs(args) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from replay_mcp_outputs import _ENV

    tape = args.tape.expanduser().resolve()
    _refuse_a_committable_tape(tape)
    if args.record:
        tape.parent.mkdir(parents=True, exist_ok=True)
    elif not tape.exists():
        sys.exit(f"no tape at {tape}: record one first (outputs --record --tape {tape})")
    with tempfile.TemporaryDirectory(prefix="token-outputs-") as tmp:
        out = Path(tmp) / "wire.json"
        env = _worker_env(_ENV)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "_outputs_worker",
                        "record" if args.record else "replay", str(tape), str(out)], env=env, check=True)
        results = json.loads(out.read_text(encoding="utf-8"))

    rows = [output_row(r) for r in results]
    import fastmcp

    totals = {k: sum(r[k] for r in rows) for k in
              ("text_chars", "text_tokens", "structured_chars", "structured_tokens", "meta_chars", "wire_chars")}
    return {
        "measure": "outputs",
        "meta": {**git_state(), "fastmcp": fastmcp.__version__, "tape": str(tape), "clock": _ENV["LEGAL_NOW"],
                 "env": dict(sorted((k, env[k]) for k in env if k.startswith(_SERVER_ENV_PREFIXES))),
                 "estimator": ESTIMATOR},
        "totals": totals,
        "calls": rows,
    }


def print_outputs(report: dict) -> None:
    m, t = report["meta"], report["totals"]
    print(f"## Outputs — {m['sha']}{' (dirty)' if m['dirty'] else ''}, replayed at {m['clock']}\n")
    print(f"_{m['estimator']}_\n")
    print("| Call | Text chars | Text tok | structuredContent | dup of text | _meta | Wire chars |\n"
          "|---|---:|---:|---:|:-:|---:|---:|")
    for r in report["calls"]:
        flag = _call_problem(r)
        flag = f" ⚠ {flag}" if flag else ""
        print(f"| `{r['call']}`{flag} | {r['text_chars']:,} | {r['text_tokens']:,} | {r['structured_chars']:,} "
              f"| {'yes' if r['structured_duplicates_text'] else 'no'} | {r['meta_chars']:,} "
              f"| {r['wire_chars']:,} |")
    print(f"| **total** | {t['text_chars']:,} | {t['text_tokens']:,} | {t['structured_chars']:,} | "
          f"| {t['meta_chars']:,} | {t['wire_chars']:,} |")


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def _delta(a: int, b: int) -> str:
    pct = f" ({100 * (b - a) / a:+.1f}%)" if a else ""
    return f"{a:,} → {b:,}{pct}"


def compare(base_path: Path, head_path: Path, top: int) -> int:
    base = json.loads(base_path.read_text(encoding="utf-8"))
    head = json.loads(head_path.read_text(encoding="utf-8"))
    if base["measure"] != head["measure"]:
        sys.exit(f"different measures: {base['measure']} vs {head['measure']}")
    print(f"## {base['measure']}: {base['meta']['sha']} → {head['meta']['sha']}\n")
    # Different setups give deltas the code did not cause: FastMCP 4 adds serverInfo to
    # every result's _meta, a different clock or switch changes the answers.
    setup = ("fastmcp",) + (("profile", "include_tags", "exclude_tags", "switches") if base["measure"] == "tools"
                            else ("clock", "env"))
    for k in setup:
        if (base["meta"].get(k) or None) != (head["meta"].get(k) or None):  # absent == empty
            print(f"Note: {k} differs ({base['meta'].get(k)} vs {head['meta'].get(k)}): "
                  "part of the delta comes from the setup, not the code.\n")
    print("| Total | Base → head |\n|---|---|")
    for k in base["totals"]:
        print(f"| {k} | {_delta(base['totals'][k], head['totals'].get(k, 0))} |")
    if base["measure"] == "tools":
        print("\n| Block | Base → head (chars) |\n|---|---|")
        for k in sorted(set(base["blocks"]) | set(head["blocks"])):
            print(f"| {k} | {_delta(base['blocks'].get(k, {}).get('chars', 0), head['blocks'].get(k, {}).get('chars', 0))} |")
        a = {r["name"]: r for r in base["tools"]}
        b = {r["name"]: r for r in head["tools"]}
        added, removed = sorted(b.keys() - a.keys()), sorted(a.keys() - b.keys())
        if added:
            print(f"\nAdded tools ({len(added)}): {', '.join(added)}")
        if removed:
            print(f"\nRemoved tools ({len(removed)}): {', '.join(removed)}")
        changed = sorted(((b[n]["model_chars"] - a[n]["model_chars"], n) for n in a.keys() & b.keys()
                          if b[n]["model_chars"] != a[n]["model_chars"]), key=lambda x: -abs(x[0]))
        if changed:
            print(f"\n{len(changed)} tools changed; largest {min(top, len(changed))}:\n")
            print("| Tool | Chars | Tokens |\n|---|---|---|")
            for _, n in changed[:top]:
                print(f"| {n} | {_delta(a[n]['model_chars'], b[n]['model_chars'])} "
                      f"| {_delta(a[n]['tokens'], b[n]['tokens'])} |")
    else:
        a = {r["call"]: r for r in base["calls"]}
        print("\n| Call | Text chars | structuredContent | Wire |\n|---|---|---|---|")
        for r in head["calls"]:
            x = a.get(r["call"])
            if x is None:
                print(f"| `{r['call']}` (new) | {r['text_chars']:,} | {r['structured_chars']:,} | {r['wire_chars']:,} |")
                continue
            print(f"| `{r['call']}` | {_delta(x['text_chars'], r['text_chars'])} "
                  f"| {_delta(x['structured_chars'], r['structured_chars'])} | {_delta(x['wire_chars'], r['wire_chars'])} |")
        gone = sorted(a.keys() - {r["call"] for r in head["calls"]})
        if gone:
            print(f"\nCalls only in the base ({len(gone)}): " + ", ".join(f"`{c}`" for c in gone))
        # A replay that missed the tape or failed measures nothing: its size says nothing
        # about the code, so the comparison fails instead of showing a saving.
        problems = [(side, r["call"], _call_problem(r)) for side, rep in (("base", base), ("head", head))
                    for r in rep["calls"] if _call_problem(r)]
        if problems:
            print(f"\nFAILED: {len(problems)} call(s) did not replay cleanly, their sizes are not measurements:")
            for side, call, why in problems:
                print(f"- {side}: `{call}`: {why}")
            return 1
    return 0


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("tools", help="measure tools/list and the server instructions")
    t.add_argument("--profile", help="LEGAL_PROFILE to measure (default: full)")
    t.add_argument("--include-tags", help="comma-separated tags, through crea_server")
    t.add_argument("--exclude-tags", help="comma-separated tags, through crea_server")
    t.add_argument("--json", type=Path, help="also write the full report here")
    t.add_argument("--top", type=int, default=10)
    o = sub.add_parser("outputs", help="measure the answers of the fixed calls, replayed from a tape")
    o.add_argument("--tape", type=Path, default=DEFAULT_TAPE,
                   help=f"the tape (default {DEFAULT_TAPE.relative_to(REPO)}, git-ignored; never commit it)")
    o.add_argument("--record", action="store_true", help="record the tape (network) instead of replaying it")
    o.add_argument("--json", type=Path, help="also write the full report here")
    c = sub.add_parser("compare", help="diff two JSON reports of the same measure")
    c.add_argument("base", type=Path)
    c.add_argument("head", type=Path)
    c.add_argument("--top", type=int, default=15)
    w = sub.add_parser("_outputs_worker")
    w.add_argument("mode")
    w.add_argument("tape")
    w.add_argument("out")
    args = parser.parse_args()

    if args.command == "_outputs_worker":
        _outputs_worker(args.mode, args.tape, args.out)
        return 0
    if args.command == "compare":
        return compare(args.base, args.head, args.top)
    if args.command == "tools":
        report = measure_tools(args)
        print_tools(report, args.top)
    else:
        report = measure_outputs(args)
        print_outputs(report)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.command == "outputs" and any(_call_problem(r) for r in report["calls"]):
        print("\nFAILED: some calls did not replay cleanly (⚠ above): re-record the tape on the base ref.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
