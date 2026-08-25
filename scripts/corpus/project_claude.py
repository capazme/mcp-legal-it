"""Project the content/ corpus onto the Claude target tree.

content/skills   -> <out>/plugin/skills    (strip 'tools:'/'prompt:', prefix tool names)
content/agents   -> <out>/plugin/agents    (strip 'tools:', prefix tool names)
content/commands -> <out>/plugin/commands  ('tools:' line -> 'allowed-tools:' line, prefix)
content/references -> <out>/plugin/server/src/data/references (verbatim copy)

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


def _project_doc(
    path: Path,
    text: str,
    vocab: set[str],
    *,
    command: bool,
    tool_template: str,
    command_template: str,
    strip_keys: list[str],
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
    return fm.join(lines, tn.add_prefixes(body, mcp_tools, tool_template))


def project(root: Path, out: Path, cfg: dict | None = None) -> None:
    if cfg is None:
        cfg = tg.get_target(root, "claude-code")
    # The manifest spells the placeholder as NAMED ({tool}) for readability;
    # toolnames.add_prefixes formats POSITIONALLY. Convert once here.
    tool_template = cfg["tool_namespace"].replace("{tool}", "{}")
    command_template = (cfg.get("command_tool_namespace") or "").replace("{tool}", "{}")
    strip_keys = cfg["strip_frontmatter_keys"]
    out_map = cfg["out"]

    content = root / "content"
    vocab = _load_vocab(root)

    skills_out = out / out_map["skills"]
    if skills_out.exists():
        shutil.rmtree(skills_out)
    for skill_dir in sorted((content / "skills").iterdir()):
        if not skill_dir.is_dir():
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
        kind_out = out / out_map[kind]
        if kind_out.exists():
            shutil.rmtree(kind_out)
        kind_out.mkdir(parents=True, exist_ok=True)
        src_kind = content / kind
        if not src_kind.is_dir():
            continue
        for src_file in sorted(src_kind.glob("*.md")):
            text = src_file.read_text(encoding="utf-8")
            _check_no_prefix(src_file, text)
            (kind_out / src_file.name).write_text(
                _project_doc(
                    src_file, text, vocab,
                    command=is_command, tool_template=tool_template,
                    command_template=command_template, strip_keys=strip_keys,
                ),
                encoding="utf-8",
            )

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
