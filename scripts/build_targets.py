#!/usr/bin/env python3
"""Unified builder for all Claude Legal IT distribution targets.

Targets:
  claude-code  project content/ onto the working tree + regenerate prompts.py
  claude-web   package plugin/skills/*/SKILL.md as per-skill ZIPs for Claude Web
  plugin-zip   package plugin/ as a Claude Code Plugin marketplace ZIP
  mcpb         package dxt/ + plugin/server as a Desktop Extension (.mcpb)
  openai       project content/ into a Codex/AGENTS-style skill bundle (dist/openai/)
  openai-zip   zip dist/openai/ for distribution
  all          the six targets above, in that order

Replaces (removed):
  scripts/build-plugin.sh, scripts/build-dxt.sh, scripts/build-all.sh,
  plugin/build-web-skills.py

Run from anywhere:
  python scripts/build_targets.py TARGET [TARGET ...] [--version X.Y.Z] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CORPUS = _HERE / "corpus"
sys.path.insert(0, str(_CORPUS))
import agents_md as am  # noqa: E402
import frontmatter as fm  # noqa: E402
import project_claude as pc  # noqa: E402
import targets as tg  # noqa: E402

ROOT = _HERE.parent

_TARGET_NAMES = ["claude-code", "claude-web", "plugin-zip", "mcpb", "openai", "openai-zip"]


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
        val = fm.read_field(fm_lines, key)
        if val is None:
            continue
        if key == "description":
            val = fm.truncate_description(val, max_chars)
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

        os.chmod(stage / "start_server.sh", 0o755)

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

        os.chmod(stage / "start_server.sh", 0o755)

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
# openai — Codex/AGENTS-style skill bundle
# ---------------------------------------------------------------------------

_OPENAI_CONFIG_TOML_EXAMPLE = """\
# Codex config.toml — MCP Legal IT (stdio, via uv)
#
# Copy this block into your Codex config.toml (usually ~/.codex/config.toml).
# Replace /path/to/mcp-legal-it with the path to a checkout of the
# mcp-legal-it server — this bundle ships skills only, no server.
#
# The server key MUST be `legal_it` (underscore, not hyphen): Codex rejects
# hyphenated MCP server names (see Codex issue #15832).

[mcp_servers.legal_it]
command = "uv"
args = [
  "run", "--python", "3.12",
  "--with", "fastmcp>=2.0,<4",
  "--with", "httpx>=0.27",
  "--with", "beautifulsoup4>=4.12",
  "--with", "lxml>=5.0",
  "--with", "fpdf2>=2.7",
  "--with", "python-docx>=1.0",
  "--with", "openpyxl>=3.1",
  "--with", "cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'",
  "/path/to/mcp-legal-it/plugin/server/run_server.py",
]

# Variante server remoto (Streamable HTTP), se preferisci non lanciare uv in
# locale (sostituisci www.esempio.it con il tuo host):
# [mcp_servers.legal_it]
# url = "https://www.esempio.it/mcp"
"""

_OPENAI_README = """\
# Legal IT — bundle OpenAI (Codex / ChatGPT)

Bundle di skill Legal IT in formato AGENTS/Codex, generato dal corpus di
`mcp-legal-it`. Contiene:

- `.agents/skills/` — le skill (una directory per skill, `SKILL.md` con
  frontmatter ridotto a `name` + `description`; i tool sono citati col nome
  bare nel testo)
- `AGENTS.md` — istruzioni del server, protocollo di grounding legale,
  workflow consigliati
- `config.toml.example` — configurazione MCP per Codex (stdio via `uv`, più
  variante Streamable HTTP commentata)

## Installazione — Codex

1. Copia `.agents/skills/` nella root del repository su cui lavori (Codex la
   legge da lì), oppure in `$HOME/.agents/skills/` per renderla disponibile
   globalmente.
2. Copia `AGENTS.md` nella root del progetto (o unisci il contenuto al tuo
   `AGENTS.md` esistente).
3. Aggiungi il blocco di `config.toml.example` al tuo `~/.codex/config.toml`
   (o esegui `codex mcp add`), sostituendo `/path/to/mcp-legal-it` con il
   percorso reale di un checkout del server MCP — il bundle non include il
   server, solo le skill.

## Installazione — ChatGPT

- **Skill**: carica il contenuto di `.agents/skills/` come istruzioni/
  knowledge personalizzate — upload manuale, ChatGPT non legge `AGENTS.md`
  nativamente.
- **Tool MCP**: serve un connector self-hosted con endpoint HTTPS pubblico
  (`MCP_TRANSPORT=http`). ChatGPT non supporta prompt MCP né risorse: solo i
  tool sono visibili.

## Approfondimenti

Guida completa: https://github.com/capazme/mcp-legal-it/blob/main/docs/openai.md
"""


def build_openai(root: Path) -> None:
    cfg = tg.get_target(root, "openai")
    # Projection FIRST: its rmtree only ever touches the projected skills
    # out-dir (dist/openai/.agents/skills). AGENTS.md / config.toml.example /
    # README.md live at dist/openai/ root, outside that subdir, so writing
    # them afterwards means they survive the projection's rmtree. Reversing
    # this order would wipe them on every rebuild.
    pc.project(root, root, cfg)

    # Bundle root derived from the manifest's own out.skills path — two path
    # segments above the skills dir (<bundle_root>/.agents/skills) — rather
    # than a hardcoded "dist/openai": a manifest edit to out.skills is the
    # only place that then needs to change.
    bundle_root = root / Path(cfg["out"]["skills"]).parents[1]
    (bundle_root / "AGENTS.md").write_text(am.generate(root), encoding="utf-8")
    (bundle_root / "config.toml.example").write_text(_OPENAI_CONFIG_TOML_EXAMPLE, encoding="utf-8")
    (bundle_root / "README.md").write_text(_OPENAI_README, encoding="utf-8")


def build_openai_zip(root: Path, version: str | None = None) -> Path:
    cfg = tg.get_target(root, "openai-zip")
    if version is None:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        version = pyproject["project"]["version"]

    output = root / cfg["artifact"].format(version=version)
    bundle_root = root / cfg["root"]
    _zip_dir(bundle_root, output)
    return output


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
            elif name == "openai":
                print("==> openai")
                build_openai(ROOT)
            elif name == "openai-zip":
                print("==> openai-zip")
                path = build_openai_zip(ROOT, version=args.version)
                print(f"Built: {path}")
        except (Exception, SystemExit) as exc:  # noqa: BLE001 — surface any build failure, no silent partials
            print(f"build_targets: target {name!r} failed: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
