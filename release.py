#!/usr/bin/env python3
"""
Release automation for mcp-legal-it.

Supports three modes:
  --from-develop   Git Flow: release branch → merge main → tag → back-merge develop
  --tag-only       Tag current main + push
  --plugin-only    Bump plugin only (no git tag, no pyproject, no Git Flow)

Usage:
  python3 release.py                                # interactive
  python3 release.py 0.4.0 --from-develop --dry-run
  python3 release.py 0.4.0 --from-develop --push
  python3 release.py 0.3.1 --tag-only --no-plugin-bump
  python3 release.py 1.1.0 --plugin-only --dry-run
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
PYPROJECT_TOML = PROJECT_DIR / "pyproject.toml"
PLUGIN_JSON = PROJECT_DIR / "plugin" / ".claude-plugin" / "plugin.json"
BUILD_WEB_SKILLS = PROJECT_DIR / "plugin" / "build-web-skills.py"

CHANGELOG_ROOT = PROJECT_DIR / "CHANGELOG.md"
CHANGELOG_PLUGIN = PROJECT_DIR / "plugin" / "CHANGELOG.md"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
PYPROJECT_VERSION_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE)

# Conventional commit type → Keep a Changelog section
_CC_MAP = {
    "feat": "Added",
    "fix": "Fixed",
    "refactor": "Changed",
    "perf": "Changed",
    "docs": "Other",
    "chore": "Other",
    "test": "Other",
    "ci": "Other",
    "build": "Other",
    "style": "Other",
}

# ---------------------------------------------------------------------------
# Output helpers (same pattern as install.py)
# ---------------------------------------------------------------------------

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

_step_counter = 0


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}" if _supports_color() else text


def banner(version: str, mode: str, dry_run: bool) -> None:
    print()
    print(c(BOLD, "  MCP Legal IT — Release"))
    label = f"v{version}  ({mode})"
    if dry_run:
        label += "  [DRY RUN]"
    print(c(DIM, f"  {label}"))
    print(c(DIM, "  " + "-" * 55))
    print()


def section(title: str) -> None:
    print()
    print(c(BOLD + BLUE, f"  ── {title} ──"))
    print()


def step(msg: str) -> None:
    global _step_counter
    _step_counter += 1
    print(f"  {c(BOLD, f'[{_step_counter:>2}]')} {msg}")


def info(msg: str) -> None:
    print(f"       {c(BLUE, '>')} {msg}")


def success(msg: str) -> None:
    print(f"       {c(GREEN, '✓')} {msg}")


def warn(msg: str) -> None:
    print(f"       {c(YELLOW, '!')} {msg}")


def error(msg: str) -> None:
    print(f"       {c(RED, '✗')} {msg}")


def fatal(msg: str) -> None:
    error(msg)
    sys.exit(1)


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"  {c(BOLD, '?')} {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return answer or default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "S/n" if default else "s/N"
    answer = ask(f"{prompt} ({hint})", "s" if default else "n")
    return answer.lower() in ("s", "si", "sì", "y", "yes")


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def read_pyproject_version() -> str:
    text = PYPROJECT_TOML.read_text()
    m = PYPROJECT_VERSION_RE.search(text)
    if not m:
        fatal(f"Cannot find version in {PYPROJECT_TOML}")
    return m.group(2)


def write_pyproject_version(version: str, *, dry_run: bool) -> None:
    text = PYPROJECT_TOML.read_text()
    new_text = PYPROJECT_VERSION_RE.sub(rf'\g<1>{version}\3', text)
    if dry_run:
        info(f"[DRY RUN] pyproject.toml version → {version}")
        return
    PYPROJECT_TOML.write_text(new_text)
    success(f"pyproject.toml version → {version}")


def read_plugin_version() -> str:
    if not PLUGIN_JSON.exists():
        return "0.0.0"
    data = json.loads(PLUGIN_JSON.read_text())
    return data.get("version", "0.0.0")


def write_plugin_version(version: str, *, dry_run: bool) -> None:
    data = json.loads(PLUGIN_JSON.read_text())
    data["version"] = version
    if dry_run:
        info(f"[DRY RUN] plugin.json version → {version}")
        return
    PLUGIN_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    success(f"plugin.json version → {version}")


def bump_part(current: str, part: str) -> str:
    """Bump a specific semver part: 'major', 'minor', or 'patch'."""
    parts = [int(x) for x in current.split(".")]
    if part == "major":
        parts = [parts[0] + 1, 0, 0]
    elif part == "minor":
        parts = [parts[0], parts[1] + 1, 0]
    else:
        parts[2] += 1
    return ".".join(str(p) for p in parts)


def auto_bump_patch(current: str) -> str:
    return bump_part(current, "patch")


def build_web_skills(*, dry_run: bool) -> None:
    if not BUILD_WEB_SKILLS.exists():
        warn(f"build-web-skills.py not found, skipping")
        return
    if dry_run:
        info(f"[DRY RUN] python3 {BUILD_WEB_SKILLS.name}")
        return
    result = subprocess.run(
        [sys.executable, str(BUILD_WEB_SKILLS)],
        capture_output=True,
        text=True,
        cwd=str(BUILD_WEB_SKILLS.parent),
    )
    if result.returncode != 0:
        warn(f"build-web-skills.py failed: {result.stderr[:200]}")
    else:
        success("Web skills ZIP rebuilt")


# ---------------------------------------------------------------------------
# CHANGELOG helpers
# ---------------------------------------------------------------------------

_CC_RE = re.compile(r"^[0-9a-f]+ (\w+)(?:\(.+?\))?!?:\s*(.+)$")


def generate_changelog_entry(version: str, from_tag: str | None) -> str:
    """Generate a Keep a Changelog entry from conventional commits since `from_tag`."""
    if not from_tag:
        return f"## [{version}] - {date.today().isoformat()}\n\nInitial release.\n"

    result = subprocess.run(
        ["git", "log", "--oneline", f"{from_tag}..HEAD"],
        capture_output=True, text=True, cwd=str(PROJECT_DIR),
    )
    lines = [l for l in result.stdout.strip().split("\n") if l] if result.returncode == 0 else []

    sections: dict[str, list[str]] = {"Added": [], "Fixed": [], "Changed": [], "Other": []}
    for line in lines:
        m = _CC_RE.match(line)
        if m:
            cc_type, msg = m.group(1), m.group(2)
            section = _CC_MAP.get(cc_type, "Other")
            sections[section].append(msg.strip())
        else:
            # Non-conventional commit — strip hash prefix
            msg = line.split(" ", 1)[1] if " " in line else line
            sections["Other"].append(msg.strip())

    parts = [f"## [{version}] - {date.today().isoformat()}"]
    for section_name in ("Added", "Fixed", "Changed", "Other"):
        items = sections[section_name]
        if items:
            parts.append(f"\n### {section_name}")
            for item in items:
                parts.append(f"- {item}")

    return "\n".join(parts) + "\n"


def write_changelog(path: Path, entry: str, *, dry_run: bool) -> None:
    """Write a CHANGELOG entry at the top of the file (after the header)."""
    if dry_run:
        info(f"[DRY RUN] Scrivi CHANGELOG entry in {path.name}")
        return

    header = (
        "# Changelog\n\n"
        "All notable changes to this project will be documented in this file.\n\n"
        "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),\n"
        "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n"
    )

    if path.exists():
        content = path.read_text()
        # Find the end of the header (first ## line)
        idx = content.find("\n## ")
        if idx >= 0:
            new_content = content[:idx] + "\n" + entry + "\n" + content[idx + 1:]
        else:
            new_content = content.rstrip() + "\n\n" + entry
    else:
        new_content = header + "\n" + entry

    path.write_text(new_content)
    success(f"CHANGELOG aggiornato: {path.name}")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def run_git(*args: str, dry_run: bool = False, capture: bool = True) -> str:
    cmd = ["git"] + list(args)
    if dry_run:
        info(f"[DRY RUN] {' '.join(cmd)}")
        return ""
    result = subprocess.run(
        cmd, capture_output=capture, text=True, cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() if capture else ""
        raise RuntimeError(f"git {args[0]} failed: {stderr}")
    return result.stdout.strip() if capture else ""


def git_current_branch() -> str:
    return run_git("rev-parse", "--abbrev-ref", "HEAD")


def git_tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "tag", "-l", tag],
        capture_output=True, text=True, cwd=str(PROJECT_DIR),
    )
    return bool(result.stdout.strip())


def git_latest_tag() -> str | None:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True, text=True, cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_commits_since_tag(tag: str) -> int:
    result = subprocess.run(
        ["git", "rev-list", "--count", f"{tag}..HEAD"],
        capture_output=True, text=True, cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        return 0
    return int(result.stdout.strip())


def git_log_oneline(tag: str, limit: int = 10) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--oneline", f"{tag}..HEAD", f"-{limit}"],
        capture_output=True, text=True, cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.strip().split("\n") if line]


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

def check_clean_tree() -> None:
    step("Verifica working tree pulito — nessuna modifica non committata")
    output = run_git("status", "--porcelain")
    if output:
        fatal(f"Working tree non pulito. Committa o stasha prima di rilasciare:\n{output}")
    success("Working tree pulito — nessun file modificato o non tracciato")


def check_branch(expected: str) -> None:
    step(f"Verifica branch corrente — deve essere '{expected}'")
    current = git_current_branch()
    if current != expected:
        fatal(f"Branch corrente: {current} — devi essere su '{expected}' per questo flusso")
    success(f"Branch corretto: {current}")


def check_remote_sync(branch: str) -> None:
    step(f"Sincronizzazione con origin/{branch} — fetch + confronto commit")
    run_git("fetch", "origin")
    behind = run_git("rev-list", "--count", f"HEAD..origin/{branch}")
    ahead = run_git("rev-list", "--count", f"origin/{branch}..HEAD")
    if int(behind) > 0:
        fatal(
            f"Branch locale è {behind} commit dietro origin/{branch}\n"
            f"       Esegui: git pull origin {branch}"
        )
    if int(ahead) > 0:
        warn(f"Branch locale è {ahead} commit avanti a origin/{branch} — verranno pushati")
    else:
        success(f"In sync con origin/{branch}")


def check_semver(version: str) -> None:
    step(f"Validazione formato semver — '{version}'")
    if not SEMVER_RE.match(version):
        fatal(f"Versione '{version}' non valida — formato atteso: X.Y.Z (es. 0.4.0)")
    success(f"Formato valido: {version}")


def check_version_gt(new: str, current: str) -> None:
    step(f"Confronto versioni — {new} deve essere > {current} (pyproject.toml)")
    new_parts = tuple(int(x) for x in new.split("."))
    cur_parts = tuple(int(x) for x in current.split("."))
    if new_parts <= cur_parts:
        warn(f"{new} non è maggiore di {current} — procedo comunque (potrebbe essere un re-tag)")
    else:
        success(f"Upgrade confermato: {current} → {new}")


def check_tag_not_exists(version: str) -> None:
    tag = f"v{version}"
    step(f"Verifica unicità tag — '{tag}' non deve esistere nel repo")
    if git_tag_exists(tag):
        fatal(f"Tag '{tag}' esiste già — scegli una versione diversa o elimina il tag")
    success(f"Tag '{tag}' disponibile")


def check_version_sync() -> None:
    """Warn if pyproject.toml version is out of sync with the latest git tag."""
    step("Verifica allineamento pyproject.toml ↔ ultimo git tag")
    latest_tag = git_latest_tag()
    if not latest_tag:
        info("Nessun tag trovato — skip controllo allineamento")
        return
    tag_ver = latest_tag.lstrip("v")
    pyproject_ver = read_pyproject_version()
    if tag_ver == pyproject_ver:
        success(f"Versione allineata: pyproject.toml={pyproject_ver}, tag={latest_tag}")
    else:
        warn(f"pyproject.toml ({pyproject_ver}) non allineato con ultimo tag ({latest_tag})")
        info(f"Suggerimento: aggiorna pyproject.toml a {tag_ver} o crea un nuovo tag")


def run_tests(*, skip: bool) -> None:
    step("Esecuzione test suite — pytest -m 'not live' (solo unit test)")
    if skip:
        warn("Test saltati (--skip-tests) — usare solo per hotfix urgenti")
        return
    info("Esecuzione in corso (output streaming)...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "not live", "-q"],
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        fatal("Test falliti — correggi prima di rilasciare (o usa --skip-tests per hotfix)")
    success("Tutti i test passano")


# ---------------------------------------------------------------------------
# Plugin marketplace
# ---------------------------------------------------------------------------

def update_marketplace(*, dry_run: bool) -> None:
    step("Aggiornamento plugin Claude Code marketplace")
    claude_bin = shutil.which("claude")
    if not claude_bin:
        warn("CLI 'claude' non trovata nel PATH — skip marketplace update")
        info("Per installare: https://docs.anthropic.com/en/docs/claude-code/overview")
        return
    if dry_run:
        info(f"[DRY RUN] claude plugin marketplace add {PROJECT_DIR}")
        info("[DRY RUN] claude plugin install legal-it@mcp-legal-it")
        return
    info("Registro sorgente marketplace locale...")
    result = subprocess.run(
        ["claude", "plugin", "marketplace", "add", str(PROJECT_DIR)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 and "already" not in result.stderr.lower():
        warn(f"marketplace add: {result.stderr.strip()[:200]}")
    info("Installo/aggiorno plugin legal-it...")
    result = subprocess.run(
        ["claude", "plugin", "install", "legal-it@mcp-legal-it"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        warn(f"plugin install: {result.stderr.strip()[:200]}")
    else:
        success("Plugin marketplace aggiornato")


def verify_marketplace(*, dry_run: bool) -> None:
    """Verify marketplace registration and plugin install persisted."""
    if dry_run:
        info("[DRY RUN] Verifica registrazione marketplace")
        return

    claude_bin = shutil.which("claude")
    if not claude_bin:
        return

    step("Verifica registrazione marketplace")

    # Check marketplace list
    result = subprocess.run(
        ["claude", "plugin", "marketplace", "list"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0 and "mcp-legal-it" in result.stdout:
        success("Sorgente marketplace registrata correttamente")
    else:
        warn("Sorgente marketplace non trovata in 'claude plugin marketplace list'")
        info("Riprova manualmente: claude plugin marketplace add " + str(PROJECT_DIR))

    # Check plugin list
    result = subprocess.run(
        ["claude", "plugin", "list"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0 and "legal-it" in result.stdout:
        success("Plugin legal-it installato e visibile")
    else:
        warn("Plugin legal-it non trovato in 'claude plugin list'")
        info("Riprova manualmente: claude plugin install legal-it@mcp-legal-it")


def update_claude_desktop(*, dry_run: bool) -> None:
    """Offer to update Claude Desktop config after release."""
    if dry_run:
        info("[DRY RUN] Aggiornamento config Claude Desktop")
        return

    if not ask_yes_no("Aggiornare la configurazione Claude Desktop?", default=False):
        return

    import platform as _platform

    _desktop_paths = {
        "Darwin": Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        "Linux": Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
    }
    config_path = _desktop_paths.get(_platform.system())
    if not config_path:
        warn(f"Sistema {_platform.system()} non supportato per Claude Desktop")
        return

    venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
    run_server = PROJECT_DIR / "run_server.py"
    cache_dir = Path.home() / ".cache" / "mcp-legal-it"

    entry = {
        "command": str(venv_python),
        "args": [str(run_server)],
    }
    env = {}
    if cache_dir.exists():
        env["MCP_CACHE_DIR"] = str(cache_dir)
    if env:
        entry["env"] = env

    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["legal-it"] = entry

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
        success(f"Claude Desktop config aggiornato: {config_path}")
    except OSError as e:
        warn(f"Impossibile scrivere config: {e}")


# ---------------------------------------------------------------------------
# Rollback context manager
# ---------------------------------------------------------------------------

class RollbackContext:
    """LIFO stack of undo actions, executed on exception."""

    def __init__(self, *, dry_run: bool):
        self._stack: list[tuple[str, callable]] = []
        self._dry_run = dry_run

    def register(self, description: str, fn: callable) -> None:
        self._stack.append((description, fn))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        if self._dry_run:
            return False
        print()
        error(f"Errore durante la release: {exc_val}")
        print()
        if not self._stack:
            return False
        warn(f"Rollback automatico — {len(self._stack)} azioni da annullare...")
        for desc, fn in reversed(self._stack):
            try:
                info(f"Rollback: {desc}")
                fn()
                success(f"OK: {desc}")
            except Exception as e:
                warn(f"Rollback fallito ({desc}): {e}")
        print()
        return False


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def interactive_setup() -> argparse.Namespace:
    """Gather release parameters interactively."""
    print()
    print(c(BOLD, "  MCP Legal IT — Release interattiva"))
    print(c(DIM, "  " + "-" * 55))

    # --- Current state ---
    print()
    print(c(BOLD, "  Stato corrente:"))
    print()

    branch = git_current_branch()
    print(f"    Branch:          {c(BOLD, branch)}")

    pyproject_ver = read_pyproject_version()
    plugin_ver = read_plugin_version()
    print(f"    pyproject.toml:  {c(BOLD, pyproject_ver)}")
    print(f"    plugin.json:     {c(BOLD, plugin_ver)}")

    latest_tag = git_latest_tag()
    if latest_tag:
        commits = git_commits_since_tag(latest_tag)
        print(f"    Ultimo tag:      {c(BOLD, latest_tag)} ({commits} commit dopo)")
        log = git_log_oneline(latest_tag, limit=8)
        if log:
            print()
            print(c(DIM, "    Commit dal tag:"))
            for line in log:
                print(f"      {c(DIM, line)}")
            if commits > len(log):
                print(f"      {c(DIM, f'... e altri {commits - len(log)} commit')}")
    else:
        print(f"    Ultimo tag:      {c(DIM, 'nessuno')}")

    # --- Detect dirty tree early (informational only) ---
    dirty = run_git("status", "--porcelain")
    if dirty:
        print()
        warn("Working tree non pulito — la release fallirà al preflight.")
        info("Committa o stasha le modifiche prima di procedere.")

    # --- Mode ---
    print()
    print(c(BOLD, "  Scegli la modalità di release:"))
    print()
    print(f"    {c(BOLD, '1.')} from-develop  {c(DIM, '— Git Flow completo: release branch → main → tag → develop')}")
    print(f"    {c(BOLD, '2.')} tag-only      {c(DIM, '— Solo tag su main + push (per release già mergiate)')}")
    print(f"    {c(BOLD, '3.')} plugin-only   {c(DIM, '— Solo plugin: bump + CHANGELOG + marketplace (no tag, no Git Flow)')}")

    # Auto-suggest based on branch
    if branch == "develop":
        default_mode = "1"
        info(f"Consigliato: from-develop (sei su '{branch}')")
    elif branch == "main":
        default_mode = "2"
        info(f"Consigliato: tag-only (sei su '{branch}')")
    else:
        default_mode = "3"
        info(f"Consigliato: plugin-only (sei su '{branch}' — non è main/develop)")

    print()
    mode_choice = ask("Modalità", default_mode)
    plugin_only = mode_choice == "3"
    from_develop = mode_choice == "1"

    # --- Version ---
    if plugin_only:
        # Plugin-only: version refers to the plugin
        print()
        print(c(BOLD, "  Scegli la versione del plugin:"))
        print()

        base = plugin_ver
        patch = bump_part(base, "patch")
        minor = bump_part(base, "minor")
        major = bump_part(base, "major")

        print(f"    {c(BOLD, '1.')} {patch}  {c(DIM, '— patch (bug fix, miglioramenti skills/hooks)')}")
        print(f"    {c(BOLD, '2.')} {minor}  {c(DIM, '— minor (nuove skill, nuovi agenti)')}")
        print(f"    {c(BOLD, '3.')} {major}  {c(DIM, '— major (breaking change nel plugin)')}")
        print(f"    {c(BOLD, '4.')} custom {c(DIM, '— inserisci manualmente')}")

        print()
        ver_choice = ask("Versione plugin", "1")
        if ver_choice == "1":
            version = patch
        elif ver_choice == "2":
            version = minor
        elif ver_choice == "3":
            version = major
        else:
            version = ask("Inserisci versione plugin (X.Y.Z)")
            if not SEMVER_RE.match(version):
                fatal(f"Versione '{version}' non valida — formato: X.Y.Z")

        # --- Options ---
        print()
        print(c(BOLD, "  Opzioni aggiuntive:"))
        print()
        dry_run = ask_yes_no("Dry run? (mostra i passi senza eseguire)", default=False)

        # --- Recap ---
        print()
        print(c(DIM, "  " + "-" * 55))
        print()
        print(c(BOLD, "  Riepilogo:"))
        print()
        print(f"    Plugin:       {plugin_ver} → {c(BOLD, version)}")
        print(f"    Modalità:     {c(BOLD, 'plugin-only')}")
        print(f"    Dry run:      {'sì' if dry_run else 'no'}")
        print()

        if not ask_yes_no("Procedere?"):
            print()
            info("Release annullata.")
            sys.exit(0)

        return argparse.Namespace(
            version=version,
            from_develop=False,
            tag_only=False,
            plugin_only=True,
            plugin_version=None,
            no_plugin_bump=False,
            skip_tests=True,
            dry_run=dry_run,
            push=False,
        )

    # --- Version (server release) ---
    print()
    print(c(BOLD, "  Scegli la versione:"))
    print()

    # Compute base for suggestions
    base = latest_tag.lstrip("v") if latest_tag else pyproject_ver
    patch = bump_part(base, "patch")
    minor = bump_part(base, "minor")
    major = bump_part(base, "major")

    print(f"    {c(BOLD, '1.')} {patch}  {c(DIM, '— patch (bug fix, miglioramenti interni)')}")
    print(f"    {c(BOLD, '2.')} {minor}  {c(DIM, '— minor (nuovi tool, nuove feature)')}")
    print(f"    {c(BOLD, '3.')} {major}  {c(DIM, '— major (breaking change nelle API)')}")
    print(f"    {c(BOLD, '4.')} custom {c(DIM, '— inserisci manualmente')}")

    print()
    ver_choice = ask("Versione", "1")
    if ver_choice == "1":
        version = patch
    elif ver_choice == "2":
        version = minor
    elif ver_choice == "3":
        version = major
    else:
        version = ask("Inserisci versione (X.Y.Z)")
        if not SEMVER_RE.match(version):
            fatal(f"Versione '{version}' non valida — formato: X.Y.Z")

    # --- Plugin ---
    print()
    print(c(BOLD, "  Opzioni plugin:"))
    print()
    print(f"    Plugin attuale: {c(BOLD, plugin_ver)}")

    plugin_bump = ask_yes_no("Aggiornare anche il plugin?")
    explicit_plugin_ver = None
    if plugin_bump:
        plugin_patch = auto_bump_patch(plugin_ver)
        print()
        print(f"    {c(BOLD, '1.')} {plugin_patch}  {c(DIM, '— auto-bump patch')}")
        print(f"    {c(BOLD, '2.')} {version}  {c(DIM, '— allinea alla versione server')}")
        print(f"    {c(BOLD, '3.')} custom   {c(DIM, '— inserisci manualmente')}")
        print()
        pv_choice = ask("Versione plugin", "1")
        if pv_choice == "2":
            explicit_plugin_ver = version
        elif pv_choice == "3":
            explicit_plugin_ver = ask("Versione plugin (X.Y.Z)")
        # else: None → auto_bump_patch will be used

    # --- Options ---
    print()
    print(c(BOLD, "  Opzioni aggiuntive:"))
    print()
    skip_tests = ask_yes_no("Saltare i test? (solo per hotfix urgenti)", default=False)
    dry_run = ask_yes_no("Dry run? (mostra i passi senza eseguire)", default=False)
    push = False
    if not dry_run:
        push = ask_yes_no("Push automatico senza conferma?", default=False)

    # --- Recap ---
    print()
    print(c(DIM, "  " + "-" * 55))
    print()
    print(c(BOLD, "  Riepilogo:"))
    print()
    mode_label = "from-develop" if from_develop else "tag-only"
    print(f"    Versione:     {c(BOLD, version)}")
    print(f"    Modalità:     {c(BOLD, mode_label)}")
    if plugin_bump:
        eff_pv = explicit_plugin_ver or auto_bump_patch(plugin_ver)
        print(f"    Plugin:       {plugin_ver} → {c(BOLD, eff_pv)}")
    else:
        print(f"    Plugin:       {c(DIM, 'invariato')}")
    print(f"    Test:         {'skip' if skip_tests else 'eseguiti'}")
    print(f"    Dry run:      {'sì' if dry_run else 'no'}")
    print(f"    Auto-push:    {'sì' if push else 'chiederà conferma'}")
    print()

    if not ask_yes_no("Procedere con la release?"):
        print()
        info("Release annullata.")
        sys.exit(0)

    # Build Namespace
    return argparse.Namespace(
        version=version,
        from_develop=from_develop,
        tag_only=not from_develop,
        plugin_only=False,
        plugin_version=explicit_plugin_ver,
        no_plugin_bump=not plugin_bump,
        skip_tests=skip_tests,
        dry_run=dry_run,
        push=push,
    )


# ---------------------------------------------------------------------------
# Flow: --from-develop
# ---------------------------------------------------------------------------

def run_from_develop(version: str, plugin_ver: str | None, args: argparse.Namespace) -> None:
    global _step_counter
    _step_counter = 0
    dry = args.dry_run
    tag = f"v{version}"
    current_pyproject = read_pyproject_version()
    current_plugin = read_plugin_version()

    # Resolve plugin version
    if args.no_plugin_bump:
        effective_plugin = current_plugin
    elif plugin_ver:
        effective_plugin = plugin_ver
    else:
        effective_plugin = auto_bump_patch(current_plugin)

    banner(version, "from-develop", dry)

    # --- Preflight ---
    section("Preflight checks")

    check_clean_tree()
    check_branch("develop")
    check_remote_sync("develop")
    check_semver(version)
    check_version_sync()
    check_version_gt(version, current_pyproject)
    check_tag_not_exists(version)
    run_tests(skip=args.skip_tests)

    with RollbackContext(dry_run=dry) as rb:
        # Save original file contents for rollback
        orig_pyproject = PYPROJECT_TOML.read_text()
        orig_plugin = PLUGIN_JSON.read_text() if PLUGIN_JSON.exists() else None

        # --- Version bump ---
        section("Version bump")

        step(f"Aggiornamento pyproject.toml — versione {current_pyproject} → {version}")
        write_pyproject_version(version, dry_run=dry)
        rb.register("restore pyproject.toml", lambda: PYPROJECT_TOML.write_text(orig_pyproject))

        if not args.no_plugin_bump:
            step(f"Aggiornamento plugin.json — versione {current_plugin} → {effective_plugin}")
            write_plugin_version(effective_plugin, dry_run=dry)
            if orig_plugin:
                rb.register("restore plugin.json", lambda: PLUGIN_JSON.write_text(orig_plugin))

            step("Rigenerazione ZIP web skills per upload Claude Web")
            build_web_skills(dry_run=dry)

        # --- CHANGELOG ---
        section("CHANGELOG")

        latest_tag = git_latest_tag()
        step("Generazione entry CHANGELOG da conventional commits")
        entry = generate_changelog_entry(version, latest_tag)
        print()
        print(c(DIM, "    --- CHANGELOG preview ---"))
        for line in entry.strip().split("\n"):
            print(f"    {c(DIM, line)}")
        print(c(DIM, "    --- fine preview ---"))
        print()

        if ask_yes_no("Scrivere il CHANGELOG?"):
            write_changelog(CHANGELOG_ROOT, entry, dry_run=dry)
            if not args.no_plugin_bump:
                write_changelog(CHANGELOG_PLUGIN, entry, dry_run=dry)
        else:
            info("CHANGELOG non scritto — puoi aggiornarlo manualmente")

        # --- Git Flow ---
        section("Git Flow")

        release_branch = f"release/{version}"

        step(f"Creazione branch '{release_branch}' da develop")
        run_git("checkout", "-b", release_branch, dry_run=dry)
        rb.register(f"delete branch {release_branch}", lambda: (
            run_git("checkout", "develop"),
            run_git("branch", "-D", release_branch),
        ))

        step(f"Commit delle versioni aggiornate sul branch di release")
        files_to_add = [str(PYPROJECT_TOML)]
        if not args.no_plugin_bump:
            files_to_add.append(str(PLUGIN_JSON))
            dist_dir = BUILD_WEB_SKILLS.parent / "dist" / "web-skills"
            if dist_dir.exists():
                files_to_add.append(str(dist_dir))
        if CHANGELOG_ROOT.exists():
            files_to_add.append(str(CHANGELOG_ROOT))
        if CHANGELOG_PLUGIN.exists():
            files_to_add.append(str(CHANGELOG_PLUGIN))
        if not dry:
            run_git("add", *files_to_add)
            run_git("commit", "-m", f"chore(release): bump version to {version}")
            success(f"Commit: chore(release): bump version to {version}")
        else:
            info(f"[DRY RUN] git add + commit 'chore(release): bump version to {version}'")

        step(f"Checkout main e sincronizzazione con origin")
        run_git("checkout", "main", dry_run=dry)
        run_git("pull", "origin", "main", dry_run=dry)
        rb.register("checkout develop", lambda: run_git("checkout", "develop"))
        if not dry:
            success("main aggiornato da origin")

        step(f"Merge {release_branch} → main con --no-ff (preserva storia branch)")
        run_git("merge", "--no-ff", release_branch, "-m",
                f"merge: {release_branch} into main", dry_run=dry)
        if not dry:
            success(f"Release mergiata in main")

        step(f"Creazione tag annotato '{tag}' su main")
        run_git("tag", "-a", tag, "-m", f"Release {tag}", dry_run=dry)
        rb.register(f"delete tag {tag}", lambda: run_git("tag", "-d", tag))
        if not dry:
            success(f"Tag {tag} creato")

        step(f"Back-merge main → develop (riallinea develop con il rilascio)")
        run_git("checkout", "develop", dry_run=dry)
        run_git("merge", "--no-ff", "main", "-m",
                f"merge: main ({tag}) back into develop", dry_run=dry)
        if not dry:
            success(f"develop riallineato con main ({tag})")

        step(f"Pulizia branch locale '{release_branch}'")
        run_git("branch", "-d", release_branch, dry_run=dry)
        if not dry:
            success(f"Branch {release_branch} eliminato")

        # --- Plugin marketplace ---
        if not args.no_plugin_bump:
            section("Plugin marketplace")
            update_marketplace(dry_run=dry)
            verify_marketplace(dry_run=dry)

        # --- Push ---
        section("Push")

        if dry:
            step("Push main + develop + tags (dry run)")
            info("[DRY RUN] git push origin main develop")
            info(f"[DRY RUN] git push origin --tags")
            info(f"[DRY RUN] git push origin --delete {release_branch}")
        else:
            if not args.push:
                print()
                if not ask_yes_no(f"Pushare main, develop e tag {tag} su origin?"):
                    warn("Push annullato — esegui manualmente:")
                    info("git push origin main develop && git push origin --tags")
                    print_summary(version, effective_plugin, current_pyproject, current_plugin,
                                  "from-develop", dry, pushed=False)
                    return
                print()

            step("Push branch main e develop su origin")
            run_git("push", "origin", "main", "develop", dry_run=dry)
            success("Branch main e develop pushati")

            step(f"Push tag {tag} su origin")
            run_git("push", "origin", "--tags", dry_run=dry)
            success(f"Tag {tag} pushato")

            step(f"Pulizia branch remoto '{release_branch}' (se presente)")
            try:
                run_git("push", "origin", "--delete", release_branch, dry_run=dry)
                success(f"Branch remoto {release_branch} eliminato")
            except RuntimeError:
                info("Branch remoto non presente — nulla da eliminare")

        # --- Post-release ---
        if not dry:
            section("Post-release")
            update_claude_desktop(dry_run=dry)

    print_summary(version, effective_plugin, current_pyproject, current_plugin,
                  "from-develop", dry, pushed=not dry)


# ---------------------------------------------------------------------------
# Flow: --tag-only
# ---------------------------------------------------------------------------

def run_tag_only(version: str, plugin_ver: str | None, args: argparse.Namespace) -> None:
    global _step_counter
    _step_counter = 0
    dry = args.dry_run
    tag = f"v{version}"
    current_pyproject = read_pyproject_version()
    current_plugin = read_plugin_version()

    # Resolve plugin version
    if args.no_plugin_bump:
        effective_plugin = current_plugin
    elif plugin_ver:
        effective_plugin = plugin_ver
    else:
        effective_plugin = auto_bump_patch(current_plugin)

    banner(version, "tag-only", dry)

    # --- Preflight ---
    section("Preflight checks")

    check_clean_tree()
    check_branch("main")
    check_remote_sync("main")
    check_semver(version)
    check_version_sync()
    check_version_gt(version, current_pyproject)
    check_tag_not_exists(version)
    run_tests(skip=args.skip_tests)

    with RollbackContext(dry_run=dry) as rb:
        # --- Optional version bump ---
        needs_commit = False

        if current_pyproject != version:
            section("Version bump")

            step(f"Aggiornamento pyproject.toml — versione {current_pyproject} → {version}")
            orig_pyproject = PYPROJECT_TOML.read_text()
            write_pyproject_version(version, dry_run=dry)
            rb.register("restore pyproject.toml", lambda: PYPROJECT_TOML.write_text(orig_pyproject))
            needs_commit = True

        if not args.no_plugin_bump and current_plugin != effective_plugin:
            if not needs_commit:
                section("Version bump")

            step(f"Aggiornamento plugin.json — versione {current_plugin} → {effective_plugin}")
            orig_plugin = PLUGIN_JSON.read_text()
            write_plugin_version(effective_plugin, dry_run=dry)
            rb.register("restore plugin.json", lambda: PLUGIN_JSON.write_text(orig_plugin))

            step("Rigenerazione ZIP web skills per upload Claude Web")
            build_web_skills(dry_run=dry)
            needs_commit = True

        # --- CHANGELOG ---
        section("CHANGELOG")

        latest_tag = git_latest_tag()
        step("Generazione entry CHANGELOG da conventional commits")
        entry = generate_changelog_entry(version, latest_tag)
        print()
        print(c(DIM, "    --- CHANGELOG preview ---"))
        for line in entry.strip().split("\n"):
            print(f"    {c(DIM, line)}")
        print(c(DIM, "    --- fine preview ---"))
        print()

        if ask_yes_no("Scrivere il CHANGELOG?"):
            write_changelog(CHANGELOG_ROOT, entry, dry_run=dry)
            if not args.no_plugin_bump:
                write_changelog(CHANGELOG_PLUGIN, entry, dry_run=dry)
            needs_commit = True
        else:
            info("CHANGELOG non scritto — puoi aggiornarlo manualmente")

        if needs_commit:
            step("Commit delle versioni aggiornate su main")
            files_to_add = [str(PYPROJECT_TOML)]
            if not args.no_plugin_bump:
                files_to_add.append(str(PLUGIN_JSON))
                dist_dir = BUILD_WEB_SKILLS.parent / "dist" / "web-skills"
                if dist_dir.exists():
                    files_to_add.append(str(dist_dir))
            if CHANGELOG_ROOT.exists():
                files_to_add.append(str(CHANGELOG_ROOT))
            if CHANGELOG_PLUGIN.exists():
                files_to_add.append(str(CHANGELOG_PLUGIN))
            if not dry:
                run_git("add", *files_to_add)
                run_git("commit", "-m", f"chore(release): bump version to {version}")
                success(f"Commit: chore(release): bump version to {version}")
            else:
                info(f"[DRY RUN] git add + commit 'chore(release): bump version to {version}'")

        # --- Tag ---
        section("Tagging")

        step(f"Creazione tag annotato '{tag}' su main")
        run_git("tag", "-a", tag, "-m", f"Release {tag}", dry_run=dry)
        rb.register(f"delete tag {tag}", lambda: run_git("tag", "-d", tag))
        if not dry:
            success(f"Tag {tag} creato")

        # --- Plugin marketplace ---
        if not args.no_plugin_bump:
            section("Plugin marketplace")
            update_marketplace(dry_run=dry)
            verify_marketplace(dry_run=dry)

        # --- Push ---
        section("Push")

        if dry:
            step("Push main + tags (dry run)")
            info("[DRY RUN] git push origin main")
            info("[DRY RUN] git push origin --tags")
        else:
            if not args.push:
                print()
                if not ask_yes_no(f"Pushare main e tag {tag} su origin?"):
                    warn("Push annullato — esegui manualmente:")
                    info("git push origin main && git push origin --tags")
                    print_summary(version, effective_plugin, current_pyproject, current_plugin,
                                  "tag-only", dry, pushed=False)
                    return
                print()

            step("Push branch main su origin")
            run_git("push", "origin", "main", dry_run=dry)
            success("Branch main pushato")

            step(f"Push tag {tag} su origin")
            run_git("push", "origin", "--tags", dry_run=dry)
            success(f"Tag {tag} pushato")

        # --- Post-release ---
        if not dry:
            section("Post-release")
            update_claude_desktop(dry_run=dry)

    print_summary(version, effective_plugin, current_pyproject, current_plugin,
                  "tag-only", dry, pushed=not dry)


# ---------------------------------------------------------------------------
# Flow: --plugin-only
# ---------------------------------------------------------------------------

def run_plugin_only(version: str, args: argparse.Namespace) -> None:
    global _step_counter
    _step_counter = 0
    dry = args.dry_run
    current_plugin = read_plugin_version()

    banner(version, "plugin-only", dry)

    # --- Preflight ---
    section("Preflight checks")

    check_clean_tree()
    check_semver(version)

    step(f"Confronto versioni plugin — {version} deve essere > {current_plugin}")
    new_parts = tuple(int(x) for x in version.split("."))
    cur_parts = tuple(int(x) for x in current_plugin.split("."))
    if new_parts <= cur_parts:
        warn(f"{version} non è maggiore di {current_plugin} — procedo comunque")
    else:
        success(f"Upgrade plugin confermato: {current_plugin} → {version}")

    # --- Version bump ---
    section("Plugin version bump")

    orig_plugin = PLUGIN_JSON.read_text() if PLUGIN_JSON.exists() else None

    step(f"Aggiornamento plugin.json — versione {current_plugin} → {version}")
    write_plugin_version(version, dry_run=dry)

    step("Rigenerazione ZIP web skills per upload Claude Web")
    build_web_skills(dry_run=dry)

    # --- CHANGELOG ---
    section("CHANGELOG")

    latest_tag = git_latest_tag()
    step("Generazione entry CHANGELOG da conventional commits")
    entry = generate_changelog_entry(version, latest_tag)
    print()
    print(c(DIM, "    --- CHANGELOG preview ---"))
    for line in entry.strip().split("\n"):
        print(f"    {c(DIM, line)}")
    print(c(DIM, "    --- fine preview ---"))
    print()

    if ask_yes_no("Scrivere il CHANGELOG?"):
        write_changelog(CHANGELOG_PLUGIN, entry, dry_run=dry)
    else:
        info("CHANGELOG non scritto — puoi aggiornarlo manualmente")

    # --- Commit ---
    section("Commit")

    step(f"Commit plugin bump su branch corrente")
    files_to_add = [str(PLUGIN_JSON)]
    if CHANGELOG_PLUGIN.exists():
        files_to_add.append(str(CHANGELOG_PLUGIN))
    dist_dir = BUILD_WEB_SKILLS.parent / "dist" / "web-skills"
    if dist_dir.exists():
        files_to_add.append(str(dist_dir))

    if not dry:
        run_git("add", *files_to_add)
        run_git("commit", "-m", f"chore(plugin): bump plugin to {version}")
        success(f"Commit: chore(plugin): bump plugin to {version}")
    else:
        info(f"[DRY RUN] git add + commit 'chore(plugin): bump plugin to {version}'")

    # --- Plugin marketplace ---
    section("Plugin marketplace")

    update_marketplace(dry_run=dry)
    verify_marketplace(dry_run=dry)

    # --- Summary ---
    print()
    print(c(DIM, "  " + "-" * 55))
    print()
    if dry:
        print(c(BOLD + YELLOW, "  DRY RUN completato — nessuna modifica effettuata"))
    else:
        print(c(BOLD + GREEN, "  Plugin release completata!"))
    print()
    print(f"  {'plugin.json':20s} {current_plugin:>12s}   {c(BOLD, f'{version:>12s}')}")
    print()
    print(f"  {c(BOLD, 'Modalità')}:  plugin-only")
    print(f"  {c(BOLD, 'Branch')}:   {git_current_branch()}")
    print()
    if not dry:
        info("Ricorda di pushare il commit e, se necessario, aprire una PR.")
    print()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(
    version: str,
    plugin_ver: str,
    old_pyproject: str,
    old_plugin: str,
    mode: str,
    dry_run: bool,
    *,
    pushed: bool,
) -> None:
    print()
    print(c(DIM, "  " + "-" * 55))
    print()
    if dry_run:
        print(c(BOLD + YELLOW, "  DRY RUN completato — nessuna modifica effettuata"))
    else:
        print(c(BOLD + GREEN, "  Release completata!"))
    print()

    # Version table
    header = f"  {'':20s} {'Prima':>12s}   {'Dopo':>12s}"
    print(header)
    print(f"  {'pyproject.toml':20s} {old_pyproject:>12s}   {c(BOLD, f'{version:>12s}')}")
    print(f"  {'plugin.json':20s} {old_plugin:>12s}   {c(BOLD, f'{plugin_ver:>12s}')}")
    print()

    print(f"  {c(BOLD, 'Modalità')}:  {mode}")
    print(f"  {c(BOLD, 'Tag')}:       v{version}")
    print(f"  {c(BOLD, 'Push')}:      {'completato' if pushed else 'non effettuato'}")

    if pushed:
        print()
        info(f"GitHub: https://github.com/gpuzio/mcp-legal-it/releases/tag/v{version}")

    if not pushed and not dry_run:
        print()
        info("Per completare manualmente:")
        if mode == "from-develop":
            info("  git push origin main develop && git push origin --tags")
        else:
            info("  git push origin main && git push origin --tags")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace | None:
    """Parse CLI args. Returns None if no args provided (interactive mode)."""
    if len(sys.argv) == 1:
        return None

    parser = argparse.ArgumentParser(
        description="Release automation for mcp-legal-it",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python3 release.py                                    # interactive
              python3 release.py 0.4.0 --from-develop --dry-run
              python3 release.py 0.4.0 --from-develop --push
              python3 release.py 0.3.1 --tag-only --no-plugin-bump
              python3 release.py 0.4.0 --from-develop --plugin-version 1.1.0
              python3 release.py 1.1.0 --plugin-only --dry-run
        """),
    )
    parser.add_argument(
        "version",
        help="Release version in semver format (X.Y.Z)",
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--from-develop",
        action="store_true",
        help="Full Git Flow: release branch → merge main → tag → back-merge develop",
    )
    mode_group.add_argument(
        "--tag-only",
        action="store_true",
        help="Tag current main + push (no release branch)",
    )
    mode_group.add_argument(
        "--plugin-only",
        action="store_true",
        help="Bump plugin only (no git tag, no pyproject bump, no Git Flow)",
    )

    parser.add_argument(
        "--plugin-version",
        metavar="VER",
        help="Explicit plugin.json version (default: auto-bump patch)",
    )
    parser.add_argument(
        "--no-plugin-bump",
        action="store_true",
        help="Don't touch plugin.json, skip marketplace update",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest (for urgent hotfixes)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show steps without executing",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push without asking for confirmation",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Interactive mode
    if args is None:
        args = interactive_setup()

    if getattr(args, "plugin_version", None) and getattr(args, "no_plugin_bump", False):
        fatal("--plugin-version and --no-plugin-bump are mutually exclusive")

    if getattr(args, "plugin_only", False):
        run_plugin_only(args.version, args)
    elif args.from_develop:
        run_from_develop(args.version, getattr(args, "plugin_version", None), args)
    else:
        run_tag_only(args.version, getattr(args, "plugin_version", None), args)


if __name__ == "__main__":
    main()
