"""Generate src/prompts.py from content/skills/*/SKILL.md 'prompt:' blocks.

Run from the repo root:  python scripts/corpus/generate_prompts.py [--out FILE]
Deterministic: functions are emitted in alphabetical order of prompt name.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import frontmatter as fm  # noqa: E402

ROOT = _HERE.parents[1]
_TYPES = {"str": "str", "float": "float", "int": "int"}

_HEADER = '''"""MCP Prompts — GENERATED from content/skills/*/SKILL.md 'prompt:' blocks.

Do not edit by hand: run  python scripts/corpus/generate_prompts.py
23 guided legal workflow prompts, for MCP clients that support prompts.
"""

from src.server import mcp

'''


def _collect() -> list[tuple[dict, str]]:
    found = []
    for skill_dir in sorted((ROOT / "content" / "skills").iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        lines, body = fm.split(skill_md.read_text(encoding="utf-8"))
        rng = fm.block_range(lines, "prompt")
        if rng is None:
            continue
        meta = json.loads(lines[rng[0]].split(":", 1)[1])
        found.append((meta, body.strip("\n") + "\n"))
    return sorted(found, key=lambda x: x[0]["name"])


def _emit(meta: dict, body: str) -> str:
    name = meta["name"]
    const = f"_BODY_{name.upper()}"
    escaped = body.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    params = []
    for a in meta["args"]:
        p = f"{a['name']}: {_TYPES[a['type']]}"
        if "default" in a:
            p += f" = {a['default']!r}"
        params.append(p)
    dati = "".join(
        f'        f"- {a["name"]}: {{{a["name"]}}}\\n"\n' for a in meta["args"]
    )
    return (
        f'{const} = """\\\n{escaped}"""\n\n\n'
        f"@mcp.prompt(description={meta['description']!r})\n"
        f"def {name}({', '.join(params)}) -> str:\n"
        f"    return (\n"
        f'        "DATI:\\n"\n'
        f"{dati}"
        f'        "\\n"\n'
        f"        + {const}\n"
        f"    )\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "plugin" / "server" / "src" / "prompts.py"
    )
    args = parser.parse_args()
    items = _collect()
    code = _HEADER + "\n\n".join(_emit(m, b) for m, b in items)
    args.out.write_text(code, encoding="utf-8")
    print(f"{len(items)} prompts -> {args.out}")


if __name__ == "__main__":
    main()
