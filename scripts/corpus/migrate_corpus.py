"""ONE-SHOT migration: plugin corpus -> content corpus with bare tool names.

Run from the repo root AFTER:
  git mv plugin/skills content/skills
  git mv plugin/agents content/agents
  git mv plugin/commands content/commands

For every markdown file: strip 'legal-it:' prefixes. For skills/agents: declare
the union of stripped names + bare vocabulary names found in bodies as a
'tools: [...]' frontmatter line. For commands: turn the 'allowed-tools:' line
into a 'tools:' line (order preserved — the projector reverses it verbatim).
Kept in the repo for audit; rerunning on a migrated corpus is a no-op.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import frontmatter as fm  # noqa: E402
import toolnames as tn  # noqa: E402

ROOT = _HERE.parents[1]
VOCAB = json.loads((ROOT / "content" / "tool-vocabulary.json").read_text(encoding="utf-8"))


def migrate_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    md_files = [p for p in sorted(skill_dir.rglob("*.md"))]
    stripped: dict[Path, str] = {}
    tools: set[str] = set()
    for p in md_files:
        text, found = tn.strip_prefixes(p.read_text(encoding="utf-8"))
        stripped[p] = text
        tools.update(found)
    lines, body = fm.split(stripped[skill_md])
    tools.update(tn.find_bare_tools(body, VOCAB))
    for p in md_files:
        if p != skill_md:
            tools.update(tn.find_bare_tools(stripped[p], VOCAB))
            p.write_text(stripped[p], encoding="utf-8")
    if fm.block_range(lines, "tools") is None and tools:
        lines = fm.append_lines(lines, ["tools: [" + ", ".join(sorted(tools)) + "]"])
    skill_md.write_text(fm.join(lines, body), encoding="utf-8")


def migrate_agent(path: Path) -> None:
    text, found = tn.strip_prefixes(path.read_text(encoding="utf-8"))
    lines, body = fm.split(text)
    tools = set(found) | set(tn.find_bare_tools(body, VOCAB))
    if fm.block_range(lines, "tools") is None and tools:
        lines = fm.append_lines(lines, ["tools: [" + ", ".join(sorted(tools)) + "]"])
    path.write_text(fm.join(lines, body), encoding="utf-8")


def migrate_command(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lines, body = fm.split(text)
    rng = fm.block_range(lines, "allowed-tools")
    declared: list[str] = []
    if rng is not None:
        raw = lines[rng[0]].split(":", 1)[1]
        # Entries without the mcp__legal-it__ prefix (Bash, CronCreate, ...)
        # are harness tools: kept verbatim, re-emitted verbatim by the projector.
        declared = [
            t.strip().removeprefix("mcp__legal-it__") for t in raw.split(",") if t.strip()
        ]
        lines = fm.replace_line(lines, "allowed-tools", "tools: " + ", ".join(declared))
    body, found = tn.strip_prefixes(body)
    missing = set(found) - set(declared)
    if missing:
        raise SystemExit(f"{path}: body uses tools missing from allowed-tools: {sorted(missing)}")
    path.write_text(fm.join(lines, body), encoding="utf-8")


def main() -> None:
    for d in sorted((ROOT / "content" / "skills").iterdir()):
        if d.is_dir():
            migrate_skill(d)
    for p in sorted((ROOT / "content" / "agents").glob("*.md")):
        migrate_agent(p)
    for p in sorted((ROOT / "content" / "commands").glob("*.md")):
        migrate_command(p)
    leftovers = [
        str(p) for p in (ROOT / "content").rglob("*.md")
        if "legal-it:" in p.read_text(encoding="utf-8")
    ]
    if leftovers:
        raise SystemExit(f"prefix leftovers in content/: {leftovers}")
    print("migration complete; content/ uses bare tool names")


if __name__ == "__main__":
    main()
