#!/usr/bin/env python3
"""Build ZIP packages of all skills for Claude Web custom skills upload."""

import re
import zipfile
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"
OUT_DIR = Path(__file__).parent / "dist" / "web-skills"
MAX_DESC_LEN = 200


def truncate_description(desc: str) -> str:
    """Truncate description to 200 chars, cutting at last word boundary."""
    desc = " ".join(desc.split())  # normalize whitespace
    if len(desc) <= MAX_DESC_LEN:
        return desc
    truncated = desc[: MAX_DESC_LEN - 3]
    # Cut at last space to avoid breaking words
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."


def convert_skill_md(content: str) -> str:
    """Convert SKILL.md frontmatter to Claude Web Skill.md format."""
    # Extract frontmatter
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not match:
        return content

    frontmatter_text, body = match.group(1), match.group(2)

    # Parse YAML fields manually (simple key: value)
    fields = {}
    current_key = None
    current_val_lines = []

    for line in frontmatter_text.split("\n"):
        # Check if it's a new key
        key_match = re.match(r"^(\w[\w-]*):\s*(.*)", line)
        if key_match:
            if current_key:
                fields[current_key] = "\n".join(current_val_lines).strip()
            current_key = key_match.group(1)
            current_val_lines = [key_match.group(2)]
        elif current_key:
            current_val_lines.append(line)

    if current_key:
        fields[current_key] = "\n".join(current_val_lines).strip()

    # Truncate description
    if "description" in fields:
        fields["description"] = truncate_description(fields["description"])

    # Remove argument-hint (not supported in Web skills)
    fields.pop("argument-hint", None)
    # Remove model (not applicable)
    fields.pop("model", None)

    # Rebuild frontmatter
    new_frontmatter = "---\n"
    for key in ["name", "description"]:
        if key in fields:
            val = fields[key]
            if "\n" in val or len(val) > 80:
                new_frontmatter += f"{key}: >\n"
                for vline in val.split("\n"):
                    new_frontmatter += f"  {vline.strip()}\n"
            else:
                new_frontmatter += f"{key}: {val}\n"
    new_frontmatter += "---\n"

    return new_frontmatter + body


def build_zips():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    skill_dirs = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())
    count = 0

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        skill_name = skill_dir.name
        content = skill_md.read_text(encoding="utf-8")
        converted = convert_skill_md(content)

        zip_path = OUT_DIR / f"{skill_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{skill_name}/Skill.md", converted)

        count += 1
        print(f"  {skill_name}.zip")

    print(f"\n{count} ZIP generati in {OUT_DIR}")


if __name__ == "__main__":
    build_zips()
