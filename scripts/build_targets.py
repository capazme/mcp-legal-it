#!/usr/bin/env python3
"""Unified builder for all Claude Legal IT distribution targets.

Targets:
  claude-code  project content/ onto the working tree + regenerate prompts.py
  claude-web   package plugin/skills/*/SKILL.md as per-skill ZIPs for Claude Web
  plugin-zip   package plugin/ as a Claude Code Plugin marketplace ZIP
  mcpb         package dxt/ + plugin/server as a Desktop Extension (.mcpb)
  all          the four targets above, in that order

Replaces (removed):
  scripts/build-plugin.sh, scripts/build-dxt.sh, scripts/build-all.sh,
  plugin/build-web-skills.py

Run from anywhere:
  python scripts/build_targets.py TARGET [TARGET ...] [--version X.Y.Z] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CORPUS = _HERE / "corpus"
sys.path.insert(0, str(_CORPUS))
import frontmatter as fm  # noqa: E402
import project_claude as pc  # noqa: E402
import targets as tg  # noqa: E402

ROOT = _HERE.parent

_TARGET_NAMES = ["claude-code", "claude-web", "plugin-zip", "mcpb"]


# ---------------------------------------------------------------------------
# claude-code — project content/ onto the working tree + regenerate prompts
# ---------------------------------------------------------------------------

def build_claude_code(root: Path) -> None:
    cfg = tg.get_target(root, "claude-code")
    pc.project(root, root, cfg)
    subprocess.run(
        [sys.executable, str(root / "scripts" / "corpus" / "generate_prompts.py")],
        cwd=root,
        check=True,
    )


# ---------------------------------------------------------------------------
# claude-web — port of plugin/build-web-skills.py
# ---------------------------------------------------------------------------

def _read_field(fm_lines: list[str], key: str) -> str | None:
    """Extract a (possibly multi-line) frontmatter field's raw value.

    Reuses frontmatter.py's block_range() for the split; the value assembly
    mirrors the legacy script's generic per-line field parser.
    """
    rng = fm.block_range(fm_lines, key)
    if rng is None:
        return None
    first = fm_lines[rng[0]]
    _, _, after = first.partition(":")
    val_lines = [after.lstrip()] + list(fm_lines[rng[0] + 1 : rng[1]])
    return "\n".join(val_lines).strip()


def _truncate_description(desc: str, max_chars: int) -> str:
    """Normalize whitespace UNCONDITIONALLY, then truncate at a word boundary."""
    desc = " ".join(desc.split())
    if len(desc) <= max_chars:
        return desc
    truncated = desc[: max_chars - 3]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."


def _emit_web_frontmatter(fields: dict[str, str], keep: list[str]) -> str:
    """A value with a newline or >80 chars becomes a folded scalar; else plain."""
    out = "---\n"
    for key in keep:
        if key not in fields:
            continue
        val = fields[key]
        if "\n" in val or len(val) > 80:
            out += f"{key}: >\n"
            for vline in val.split("\n"):
                out += f"  {vline.strip()}\n"
        else:
            out += f"{key}: {val}\n"
    out += "---\n"
    return out


def _convert_skill_md(text: str, cfg: dict) -> str:
    fm_lines, body = fm.split(text)
    keep = cfg["keep_frontmatter"]
    max_chars = cfg["description_max_chars"]
    fields: dict[str, str] = {}
    for key in keep:
        val = _read_field(fm_lines, key)
        if val is None:
            continue
        if key == "description":
            val = _truncate_description(val, max_chars)
        fields[key] = val
    return _emit_web_frontmatter(fields, keep) + body


def build_claude_web(root: Path, out_dir: Path | None = None) -> int:
    cfg = tg.get_target(root, "claude-web")
    src_cfg = tg.get_target(root, cfg["from"])
    skills_dir = root / src_cfg["out"]["skills"]
    target_out = Path(out_dir) if out_dir is not None else root / cfg["out_dir"]
    target_out.mkdir(parents=True, exist_ok=True)

    count = 0
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        skill_name = skill_dir.name
        converted = _convert_skill_md(skill_md.read_text(encoding="utf-8"), cfg)
        member = cfg["zip_member"].format(name=skill_name)
        zip_path = target_out / f"{skill_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(member, converted)
        count += 1

    print(f"{count} ZIP generati in {target_out}")
    return count


# ---------------------------------------------------------------------------
# shared staging helpers for plugin-zip / mcpb
# ---------------------------------------------------------------------------

def _purge_caches(stage: Path) -> None:
    for d in list(stage.rglob("__pycache__")):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    for f in list(stage.rglob("*.pyc")):
        if f.is_file():
            f.unlink()


def _rewrite_manifest_version(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _zip_dir(stage: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(stage.rglob("*")):
            if not f.is_file():
                continue
            if f.suffix == ".pyc" or "__pycache__" in f.parts:
                continue
            zf.write(f, str(f.relative_to(stage)))


# ---------------------------------------------------------------------------
# plugin-zip — port of scripts/build-plugin.sh
# ---------------------------------------------------------------------------

def build_plugin_zip(root: Path, version: str | None = None) -> Path:
    cfg = tg.get_target(root, "plugin-zip")
    plugin_root = root / cfg["root"]
    manifest_rel = cfg["version_manifest"]
    manifest_path = plugin_root / manifest_rel
    explicit_version = version is not None
    if version is None:
        version = json.loads(manifest_path.read_text(encoding="utf-8"))["version"]

    output = root / cfg["artifact"].format(version=version)
    output.parent.mkdir(parents=True, exist_ok=True)

    stage = Path(tempfile.mkdtemp(prefix="legal-it-plugin-"))
    try:
        for item in cfg["include"]:
            src = plugin_root / item
            dst = stage / item
            if not src.exists():
                raise FileNotFoundError(f"plugin-zip: missing include item {src}")
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        _purge_caches(stage)

        if explicit_version:
            _rewrite_manifest_version(stage / manifest_rel, version)

        _zip_dir(stage, output)
        return output
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# ---------------------------------------------------------------------------
# mcpb — port of scripts/build-dxt.sh
# ---------------------------------------------------------------------------

def build_mcpb(root: Path, version: str | None = None) -> Path:
    cfg = tg.get_target(root, "mcpb")
    dxt_dir = root / "dxt"
    manifest_rel = cfg["version_manifest"]
    manifest_path = dxt_dir / manifest_rel
    explicit_version = version is not None
    if version is None:
        version = json.loads(manifest_path.read_text(encoding="utf-8"))["version"]

    output = root / cfg["artifact"].format(version=version)
    output.parent.mkdir(parents=True, exist_ok=True)

    stage = Path(tempfile.mkdtemp(prefix="legal-it-mcpb-"))
    try:
        shutil.copy2(manifest_path, stage / "manifest.json")
        shutil.copy2(dxt_dir / ".mcpbignore", stage / ".mcpbignore")
        shutil.copy2(root / "pyproject.toml", stage / "pyproject.toml")
        shutil.copy2(root / "plugin" / "start_server.sh", stage / "start_server.sh")
        shutil.copytree(root / "plugin" / "server", stage / "server")

        _purge_caches(stage)

        if explicit_version:
            _rewrite_manifest_version(stage / "manifest.json", version)

        if shutil.which("mcpb"):
            subprocess.run(["mcpb", "pack", str(stage), str(output)], check=True)
        else:
            _zip_dir(stage, output)

        return output
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _expand(names: list[str]) -> list[str]:
    if "all" in names:
        return list(_TARGET_NAMES)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "targets",
        nargs="+",
        choices=[*_TARGET_NAMES, "all"],
        help="One or more build targets, or 'all'.",
    )
    parser.add_argument("--version", default=None, help="Override the artifact version (plugin-zip, mcpb).")
    parser.add_argument("--out", type=Path, default=None, help="Output dir override (claude-web only).")
    args = parser.parse_args(argv)

    for name in _expand(args.targets):
        try:
            if name == "claude-code":
                print("==> claude-code")
                build_claude_code(ROOT)
            elif name == "claude-web":
                print("==> claude-web")
                build_claude_web(ROOT, out_dir=args.out)
            elif name == "plugin-zip":
                print("==> plugin-zip")
                path = build_plugin_zip(ROOT, version=args.version)
                print(f"Built: {path}")
            elif name == "mcpb":
                print("==> mcpb")
                path = build_mcpb(ROOT, version=args.version)
                print(f"Built: {path}")
        except Exception as exc:  # noqa: BLE001 — surface any build failure, no silent partials
            print(f"build_targets: target {name!r} failed: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
