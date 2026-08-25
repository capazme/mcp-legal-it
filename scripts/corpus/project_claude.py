"""Project the content/ corpus onto a target tree (claude-code by default).

content/skills   -> <out>/<out.skills>    (strip 'tools:'/'prompt:', prefix tool names)
content/agents   -> <out>/<out.agents>    (strip 'tools:', prefix tool names)
content/commands -> <out>/<out.commands>  ('tools:' line -> 'allowed-tools:' line, prefix)
content/references -> <out>/<out.references> (verbatim copy)

Optional target capabilities (see content/targets.yaml, load_targets()):
  supports: [skills, agents, commands, mcp_prompts, mcp_resources, hooks]
    Which kinds this target projects natively. Absent = full claude behavior
    (all four filesystem kinds, backward compatible).
  merge_into_skills: [agents, commands]
    Project these SOURCE kinds INTO the skills out-dir instead of their own:
    each X.md becomes X/SKILL.md with frontmatter REBUILT as just `name` +
    `description` (standalone-description wins if present); tools:/model/
    color/argument-hint are dropped. Bypasses command semantics entirely —
    no allowed-tools, no command_tool_namespace requirement, even when the
    source declares vocabulary tools.
  exclude: [commands/release, skills/cookie-audit]
    Kind-qualified source names to skip outright.
  description_max_chars: 150
    Applied to every projected skill description (native skills AND merged
    agents/commands): read the full frontmatter block (multi-line aware),
    normalize whitespace, truncate at a word boundary, then trim a trailing
    dangling connector left over from naive truncation, and re-emit as ONE
    description: line.

Run from the repo root:  python scripts/corpus/project_claude.py [--out DIR]
Without --out it writes into the working tree (the generated dirs are committed:
the Claude marketplace installs the plugin/ tree straight from git).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import frontmatter as fm  # noqa: E402
import targets as tg  # noqa: E402
import toolnames as tn  # noqa: E402

ROOT = _HERE.parents[1]


def _parse_tools(fm_lines: list[str], path: Path) -> list[str]:
    rng = fm.block_range(fm_lines, "tools")
    if rng is None:
        return []
    if rng[1] - rng[0] != 1:
        raise SystemExit(
            f"{path}: 'tools:' must be a single-line flow list — multi-line blocks are silently truncated"
        )
    raw = fm_lines[rng[0]].split(":", 1)[1].strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip() for t in raw.split(",") if t.strip()]


def _check_no_prefix(path: Path, text: str) -> None:
    if "legal-it:" in text:
        raise SystemExit(f"{path}: corpus files must use bare tool names, found 'legal-it:'")


def _check_undeclared(path: Path, body: str, vocab: set[str], declared: list[str]) -> None:
    hits = tn.find_bare_tools(body, sorted(vocab - set(declared)))
    if hits:
        raise SystemExit(f"{path}: undeclared tool name(s) in body: {hits} — add them to tools: or rephrase")


def _load_vocab(root: Path) -> set[str]:
    return set(json.loads((root / "content" / "tool-vocabulary.json").read_text(encoding="utf-8")))


# Trailing words that "..." truncation can strand right before the ellipsis,
# leaving a dangling connector instead of a clean sentence fragment (measured
# against the real corpus: 34/42 descriptions cut mid-trigger otherwise).
# Longest-first so "Usa quando" is tried before the "Usa" it contains.
_DANGLING_CONNECTORS = ("Usa quando", "Usa", "con", "per", "es.")


def _trim_dangling_connector(text: str) -> str:
    for word in _DANGLING_CONNECTORS:
        if text == word or text.endswith(" " + word):
            return text[: len(text) - len(word)].rstrip()
    return text


def _cap_description(desc: str, max_chars: int) -> str:
    """truncate_description() plus a trailing dangling-connector trim.

    The shared fm.truncate_description() is used AS-IS (build_claude_web
    keeps calling it directly, unaffected by this). The connector trim is
    layered on top here, only when truncation actually happened.
    """
    normalized = " ".join(desc.split())
    capped = fm.truncate_description(desc, max_chars)
    if capped.endswith("...") and capped != normalized:
        body = capped[:-3].rstrip()
        trimmed = _trim_dangling_connector(body)
        if trimmed != body:
            capped = trimmed + "..."
    return capped


def _apply_description_cap(lines: list[str], max_chars: int) -> list[str]:
    """Replace a (possibly multi-line) description: block with ONE capped line."""
    rng = fm.block_range(lines, "description")
    if rng is None:
        return lines
    full = fm.read_field(lines, "description")
    if full is None:
        return lines
    capped = _cap_description(full, max_chars)
    return lines[: rng[0]] + [f"description: {capped}"] + lines[rng[1] :]


def _project_doc(
    path: Path,
    text: str,
    vocab: set[str],
    *,
    command: bool,
    tool_template: str,
    command_template: str,
    strip_keys: list[str],
    description_max_chars: int | None = None,
) -> str:
    lines, body = fm.split(text)
    tools = _parse_tools(lines, path)
    _check_undeclared(path, body, vocab, tools)
    # allowed-tools may carry NON-MCP entries (Bash, CronCreate, ...): only
    # vocabulary members get the legal-it namespace; the rest pass through
    # verbatim, in both the allowed-tools line and the body rewrite.
    mcp_tools = [t for t in tools if t in vocab]
    if command and tools:
        if mcp_tools and not command_template:
            raise SystemExit(
                f"{path}: target declares commands but no command_tool_namespace in targets.yaml"
            )
        allowed = ", ".join(command_template.format(t) if t in vocab else t for t in tools)
        lines = fm.replace_line(lines, "tools", f"allowed-tools: {allowed}")
        remaining_keys = [k for k in strip_keys if k != "tools"]
    else:
        remaining_keys = strip_keys
    lines = fm.strip_keys(lines, remaining_keys)
    if description_max_chars is not None:
        lines = _apply_description_cap(lines, description_max_chars)
    return fm.join(lines, tn.add_prefixes(body, mcp_tools, tool_template))


def _project_merged_doc(
    path: Path,
    text: str,
    vocab: set[str],
    *,
    tool_template: str,
    description_max_chars: int | None,
) -> str:
    """Merge an agent/command doc into a skill.

    Frontmatter is REBUILT (not filtered) as just `name` + one `description`
    line — standalone-description wins over description when present; tools:,
    model, color, argument-hint are all dropped. This BYPASSES command
    semantics entirely: no allowed-tools emission, no command_tool_namespace
    requirement, even when the source is a command declaring vocabulary
    tools. Bodies still get the target's tool namespacing and go through the
    same bare-name / multi-line-tools / undeclared-name guards as any other
    projected doc.
    """
    lines, body = fm.split(text)
    tools = _parse_tools(lines, path)
    _check_undeclared(path, body, vocab, tools)
    mcp_tools = [t for t in tools if t in vocab]

    name = fm.read_field(lines, "name")
    if name is None:
        raise SystemExit(f"{path}: merged doc missing required 'name:' frontmatter field")
    desc = fm.read_field(lines, "standalone-description")
    if desc is None:
        desc = fm.read_field(lines, "description")
    if desc is None:
        raise SystemExit(
            f"{path}: merged doc missing 'description:' (or 'standalone-description:') frontmatter field"
        )
    desc = (
        _cap_description(desc, description_max_chars)
        if description_max_chars is not None
        else " ".join(desc.split())
    )

    new_lines = [f"name: {name}", f"description: {desc}"]
    return fm.join(new_lines, tn.add_prefixes(body, mcp_tools, tool_template))


def project(root: Path, out: Path, cfg: dict | None = None) -> None:
    if cfg is None:
        cfg = tg.get_target(root, "claude-code")
    # The manifest spells the placeholder as NAMED ({tool}) for readability;
    # toolnames.add_prefixes formats POSITIONALLY. Convert once here.
    tool_template = cfg["tool_namespace"].replace("{tool}", "{}")
    command_template = (cfg.get("command_tool_namespace") or "").replace("{tool}", "{}")
    strip_keys = cfg["strip_frontmatter_keys"]
    out_map = cfg["out"]
    exclude = set(cfg.get("exclude") or [])
    merge_into_skills = set(cfg.get("merge_into_skills") or [])
    description_max_chars = cfg.get("description_max_chars")

    # Absent supports = full claude behavior (backward compatible): all four
    # filesystem kinds, exactly as this function always behaved pre-Task 2.
    supports = cfg.get("supports")
    active = set(supports) if supports is not None else {"skills", "agents", "commands", "mcp_resources"}

    merge_agents = "agents" in merge_into_skills
    merge_commands = "commands" in merge_into_skills
    write_skills = "skills" in active
    write_agents = "agents" in active and not merge_agents
    write_commands = "commands" in active and not merge_commands
    write_refs = "mcp_resources" in active

    content = root / "content"
    vocab = _load_vocab(root)

    # Single up-front rmtree of the DISTINCT skills/agents/commands out-dir
    # set: merge_into_skills writes agents/commands INTO the skills out-dir,
    # so a per-kind rmtree would wipe whichever kind was written first.
    skills_needed = write_skills or merge_agents or merge_commands
    out_dirs: set[Path] = set()
    if skills_needed:
        out_dirs.add(out / out_map["skills"])
    if write_agents:
        out_dirs.add(out / out_map["agents"])
    if write_commands:
        out_dirs.add(out / out_map["commands"])
    for d in out_dirs:
        if d.exists():
            shutil.rmtree(d)

    skills_out = out / out_map["skills"] if skills_needed else None
    if skills_out is not None:
        skills_out.mkdir(parents=True, exist_ok=True)

    if write_skills:
        for skill_dir in sorted((content / "skills").iterdir()):
            if not skill_dir.is_dir():
                continue
            if f"skills/{skill_dir.name}" in exclude:
                continue
            dest = skills_out / skill_dir.name
            skill_path = skill_dir / "SKILL.md"
            skill_text = skill_path.read_text(encoding="utf-8")
            _check_no_prefix(skill_path, skill_text)
            fm_lines, _ = fm.split(skill_text)
            tools = _parse_tools(fm_lines, skill_path)
            for src_file in sorted(skill_dir.rglob("*")):
                if not src_file.is_file():
                    continue
                rel = src_file.relative_to(skill_dir)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if rel == Path("SKILL.md"):
                    target.write_text(
                        _project_doc(
                            skill_path, skill_text, vocab,
                            command=False, tool_template=tool_template,
                            command_template=command_template, strip_keys=strip_keys,
                            description_max_chars=description_max_chars,
                        ),
                        encoding="utf-8",
                    )
                elif src_file.suffix == ".md":
                    text = src_file.read_text(encoding="utf-8")
                    _check_no_prefix(src_file, text)
                    _check_undeclared(src_file, text, vocab, tools)
                    target.write_text(
                        tn.add_prefixes(text, [t for t in tools if t in vocab], tool_template),
                        encoding="utf-8",
                    )
                else:
                    shutil.copy2(src_file, target)

    for kind, is_command in (("agents", False), ("commands", True)):
        do_native = write_agents if kind == "agents" else write_commands
        do_merge = merge_agents if kind == "agents" else merge_commands
        if not (do_native or do_merge):
            continue
        src_kind = content / kind
        kind_out = None
        if do_native:
            kind_out = out / out_map[kind]
            kind_out.mkdir(parents=True, exist_ok=True)
        if not src_kind.is_dir():
            continue
        for src_file in sorted(src_kind.glob("*.md")):
            if f"{kind}/{src_file.stem}" in exclude:
                continue
            text = src_file.read_text(encoding="utf-8")
            _check_no_prefix(src_file, text)
            if do_native:
                (kind_out / src_file.name).write_text(
                    _project_doc(
                        src_file, text, vocab,
                        command=is_command, tool_template=tool_template,
                        command_template=command_template, strip_keys=strip_keys,
                    ),
                    encoding="utf-8",
                )
            if do_merge:
                merged_dir = skills_out / src_file.stem
                merged_dir.mkdir(parents=True, exist_ok=True)
                (merged_dir / "SKILL.md").write_text(
                    _project_merged_doc(
                        src_file, text, vocab,
                        tool_template=tool_template,
                        description_max_chars=description_max_chars,
                    ),
                    encoding="utf-8",
                )

    if write_refs:
        refs_src = content / "references"
        if refs_src.is_dir():
            refs_out = out / out_map["references"]
            if refs_out.exists():
                shutil.rmtree(refs_out)
            refs_out.mkdir(parents=True, exist_ok=True)
            for src_file in sorted(refs_src.glob("*.md")):
                shutil.copy2(src_file, refs_out / src_file.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()
    project(ROOT, args.out)
    print(f"projected content/ -> {args.out}")


if __name__ == "__main__":
    main()
