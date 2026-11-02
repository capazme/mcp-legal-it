#!/usr/bin/env python3
"""The plugin folder still passes the Claude directory's automated checks.

Anthropic's directory reads the plugin straight from this repository (folder
`plugin/`, tracked branch `main`) and scans every new commit before it can be
published. Its rules are in the plugin pre-submission checklist
(claude.com/docs/plugins/pre-submission-checklist). This script replays the
ones that can be checked from the repository, so a change that would block
the listing, or add a reason for a manual review, fails CI instead of the
next directory scan.

Two severities, mirroring the portal's report:

    BLOCKS  the portal refuses the version (or stops validating the repository)
    HOLD    the version waits for an Anthropic reviewer

Known holds that cannot be removed are listed in ACCEPTED_HOLDS with the
reason, so they are reported but do not fail the run.

    python3 scripts/check_directory_readiness.py          # tracked files at HEAD
    python3 scripts/check_directory_readiness.py --rev v2.17.0

Stdlib plus `git`, so it runs in CI with no dependency install.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import PurePosixPath

PLUGIN = "plugin"

KIB = 1024
MIB = 1024 * KIB

IMAGE_FONT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
              ".ttf", ".otf", ".woff", ".woff2"}
OS_JUNK = {".DS_Store", "Thumbs.db", "desktop.ini"}
PACKAGE_SOURCE_FILES = {".npmrc", "bunfig.toml", "uv.toml", "pip.conf", ".pypirc"}
RESERVED_NAMES = {"claude", "anthropic", "official", "plugin", "mcp", "test"}
SETTINGS_KEYS_THAT_LOAD = {"agent", "subagentStatusLine"}
LAUNCHERS = ("npx", "bunx", "uvx", "pipx")
WINDOWS_DEVICE = re.compile(r"^(con|prn|aux|nul|com\d|lpt\d)(\..*)?$", re.I)
OTHER_VARIABLE = re.compile(r"\$\{(?!CLAUDE_PLUGIN_ROOT\})[^}]*\}|\$[A-Za-z_]")
SECRET = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"
    r"|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[bp]-[A-Za-z0-9-]{20,}"
)

#: Holds the directory raises by design and that this plugin cannot avoid.
ACCEPTED_HOLDS = {
    "uv-run-frozen": (
        "the local MCP server starts through `uv run --frozen`: "
        "the directory always holds a launcher that installs packages, even "
        "pinned ones (\"Runs a pinned npx or uvx package\"). A Python server "
        "with compiled dependencies cannot ship without one (accepted by the owner)"
    ),
    "subfolder-program": (
        "the server and the hook run Python files from a plugin that lives in "
        "a subfolder of the repository (\"Scripts the validator couldn't "
        "follow\"); it collapses into the same review as uv-run-frozen"
    ),
}


class Report:
    def __init__(self) -> None:
        self.blocks: list[str] = []
        self.holds: list[str] = []
        self.accepted: set[str] = set()

    def block(self, message: str) -> None:
        self.blocks.append(message)

    def hold(self, message: str) -> None:
        self.holds.append(message)

    def accept(self, key: str) -> None:
        self.accepted.add(key)


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def tree(rev: str) -> list[tuple[str, str, int, str]]:
    """(mode, type, size, path) for every tracked entry of `rev`."""
    entries = []
    for line in git("ls-tree", "-r", "-l", "-z", rev).split(b"\0"):
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, _sha, size = meta.split()
        entries.append((mode.decode(), kind.decode(),
                        int(size) if size != b"-" else 0, path.decode()))
    return entries


def blob(rev: str, path: str) -> bytes:
    return git("show", f"{rev}:{path}")


def check_repository(rev: str, entries, report: Report) -> None:
    for _mode, _kind, _size, path in entries:
        if PurePosixPath(path).name != ".gitattributes":
            continue
        for line in blob(rev, path).decode("utf-8", "replace").splitlines():
            fields = line.split("#", 1)[0].split()
            if any(f in ("export-ignore", "export-subst") or f.startswith("filter")
                   for f in fields[1:]):
                report.block(f"{path}: `{line.strip()}` stops directory validation")

    names = [path for *_rest, path in entries]
    for path in names:
        for part in PurePosixPath(path).parts:
            if (re.search(r'[:<>"|?*\\]', part) or part.endswith((".", " "))
                    or WINDOWS_DEVICE.match(part)):
                report.block(f"{path}: name not valid on Windows or macOS")
    folded = Counter(path.lower() for path in names)
    for path in names:
        if folded[path.lower()] > 1:
            report.block(f"{path}: differs from another path only by capitalization")

    unpacked = sum(size for _m, _k, size, _p in entries)
    archive = len(gzip.compress(git("archive", "--format=tar", rev), compresslevel=6))
    if archive >= 50 * MIB or unpacked >= 256 * MIB or len(entries) >= 10_000:
        report.block(f"repository too large: {archive / MIB:.1f} MiB archived, "
                     f"{unpacked / MIB:.1f} MiB unpacked, {len(entries)} files")


def check_manifest(rev: str, files: dict[str, tuple[str, int]], report: Report) -> None:
    manifest_path = f"{PLUGIN}/.claude-plugin/plugin.json"
    if manifest_path not in files:
        report.block(f"{manifest_path} missing")
        return
    manifest = json.loads(blob(rev, manifest_path))
    name = manifest.get("name", "")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?", name):
        report.block(f"plugin name {name!r}: lowercase letters, digits, hyphens, max 64")
    if name in RESERVED_NAMES:
        report.block(f"plugin name {name!r} is reserved")
    for key in ("description", "author", "version"):
        if not manifest.get(key):
            report.hold(f"plugin.json: `{key}` missing (warning in the portal)")

    readme = next((p for p in files if p.lower() == f"{PLUGIN}/readme.md"), None)
    if readme is None:
        report.block("README missing in the plugin folder")
    else:
        text = re.sub(r"```.*?```", " ", blob(rev, readme).decode("utf-8"), flags=re.S)
        if len(text.split()) < 40:
            report.block("README shorter than 40 words outside code blocks")
    if f"{PLUGIN}/LICENSE" not in files and not manifest.get("license"):
        report.block("no LICENSE file and no `license` in plugin.json")

    settings = f"{PLUGIN}/settings.json"
    if settings in files:
        extra = set(json.loads(blob(rev, settings))) - SETTINGS_KEYS_THAT_LOAD
        if extra:
            report.hold(f"{settings}: keys {sorted(extra)} are dropped at load and "
                        "read as a permission change by the security scan")


def check_files(rev: str, files: dict[str, tuple[str, int]], report: Report) -> None:
    if len(files) > 512:
        report.hold(f"plugin folder has {len(files)} files (limit 512)")
    for path, (mode, size) in files.items():
        name = PurePosixPath(path).name
        suffix = PurePosixPath(path).suffix.lower()
        if mode == "120000":
            report.block(f"{path}: symlink in the plugin folder")
            continue
        if mode == "160000":
            report.block(f"{path}: git submodule in the plugin folder")
            continue
        if name in OS_JUNK or "__MACOSX" in path:
            report.block(f"{path}: macOS or Windows system file")
        if name in PACKAGE_SOURCE_FILES:
            report.block(f"{path}: package-source configuration next to a launcher")
        if size >= 5 * MIB:
            report.block(f"{path}: {size / MIB:.1f} MiB (limit 5 MiB)")
        if suffix in IMAGE_FONT:
            continue
        if size >= 256 * KIB:
            report.hold(f"{path}: {size / KIB:.0f} KiB (limit 256 KiB for non-images)")
        data = blob(rev, path)
        if data.startswith(b"version ") and b"\noid sha256:" in data[:200]:
            report.block(f"{path}: Git LFS pointer")
        if b"\0" in data[:8192]:
            report.hold(f"{path}: binary file the validator cannot inspect")
            continue
        text = data.decode("utf-8", "replace")
        if SECRET.search(text):
            report.block(f"{path}: looks like a credential")
        if path.endswith(".md") and re.search(r"(^|[\s(])!`[^`\n]+`", text, re.M):
            report.hold(f"{path}: inline `!` command in a skill or command")


# `uv run` options that take a value (as the next argument or after "="). The command
# uv runs starts at the first argument that is neither an option nor an option's value.
UV_VALUE_OPTIONS = {
    "--python", "-p", "--project", "--directory", "--with", "-w", "--with-editable",
    "--with-requirements", "--index", "--index-url", "-i", "--extra-index-url", "--default-index",
    "--find-links", "-f", "--env-file", "--package", "--extra", "--group", "--only-group",
    "--no-group", "--config-file", "--cache-dir", "--python-preference", "--exclude-newer",
    "--index-strategy", "--keyring-provider", "--resolution", "--prerelease", "--link-mode",
    "--color", "--upgrade-package", "-P", "--reinstall-package", "--refresh-package",
    "--no-binary-package", "--no-build-package", "--python-platform", "--allow-insecure-host",
}
UV_SWITCHES = {
    "--frozen", "--locked", "--no-sync", "--no-project", "--isolated", "--no-config", "--active",
    "--no-dev", "--all-extras", "--all-groups", "--no-default-groups", "--offline", "--no-cache",
    "-n", "--quiet", "-q", "--verbose", "-v", "--no-progress", "--native-tls", "--no-python-downloads",
    "--managed-python", "--no-managed-python", "--no-editable", "--exact", "--inexact",
    "--no-env-file", "--refresh", "--reinstall", "--upgrade", "-U", "--compile-bytecode",
    "--script", "-s", "--gui-script", "--module", "-m", "--no-build-isolation",
}


def uv_run_options(args: list[str]) -> "tuple[list[str], dict[str, str], list[str], list[str]]":
    """`uv run ...` split: (option names, their values, unknown names, the command it runs).

    Short options may be grouped («-qw six», «-wsix»): each letter is an option, and one
    that takes a value takes the rest of the token, or the next argument.
    """
    names: list[str] = []
    values: dict[str, str] = {}
    unknown: list[str] = []
    i = 1  # args[0] == "run"
    while i < len(args):
        token = args[i]
        if token == "--":
            i += 1
            break
        if not token.startswith("-") or token == "-":
            break
        if token.startswith("--"):
            name, eq, value = token.partition("=")
            names.append(name)
            if name in UV_VALUE_OPTIONS:
                if not eq and i + 1 < len(args):
                    value = args[i + 1]
                    i += 1
                values[name] = value
            elif name not in UV_SWITCHES:
                unknown.append(name)
            i += 1
            continue
        lettere = token[1:]
        for k, lettera in enumerate(lettere):
            name = f"-{lettera}"
            names.append(name)
            if name in UV_VALUE_OPTIONS:
                value = lettere[k + 1:].lstrip("=")
                if not value and i + 1 < len(args):
                    value = args[i + 1]
                    i += 1
                values[name] = value
                break
            if name not in UV_SWITCHES:
                unknown.append(name)
        i += 1
    return names, values, unknown, args[i:]


# The only folders a launcher may start uv from: the plugin's (or, in a .mcpb, the bundle's).
_CARTELLA_DEL_PLUGIN = re.compile(r"^\$\{(?:CLAUDE_PLUGIN_ROOT|__dirname)\}(?:/|$)")

_INLINE_SCRIPT = re.compile(r"^# /// script\s*$", re.M)


def uv_installs(names: list[str], comando: list[str], leggi=None) -> bool:
    """Whether `uv run` resolves and installs packages: --with*, --script, or a script with
    inline metadata («# /// script») run as the command, which uv reads without --script."""
    if any(n.startswith("--with") or n in ("-w", "--script", "-s", "--gui-script") for n in names):
        return True
    if comando and comando[0].endswith((".py", ".pyw")):
        testo = leggi(comando[0]) if leggi is not None else None
        return testo is None or bool(_INLINE_SCRIPT.search(testo))  # unreadable: assume it does
    return False


def check_command(where: str, command: str, args: list[str], report: Report,
                  files: dict[str, tuple[str, int]] | None = None, leggi=None) -> None:
    """*leggi*: the text of a file the command names (``${CLAUDE_PLUGIN_ROOT}/…``), or None."""
    line = " ".join([command, *args])
    if OTHER_VARIABLE.search(line) or "$(" in line or "`" in line:
        report.block(f"{where}: variable other than ${{CLAUDE_PLUGIN_ROOT}} or "
                     "command substitution")
    if re.search(r"(^|\s)-c(\s|$)", line):
        report.block(f"{where}: inline program (-c)")
    if command in ("bash", "sh", "zsh", "cmd", "powershell", "pwsh"):
        report.hold(f"{where}: starts through a shell")
    if command == "uv" and args[:1] == ["run"]:
        # Only the options before the command count: «--with» in the script's own
        # arguments installs nothing, and an option after the command is not uv's.
        names, values, unknown, comando = uv_run_options(args)
        for name in unknown:
            report.block(f"{where}: `uv run` option {name} the validator does not know")
        frozen = "--frozen" in names or "--locked" in names
        if "--no-project" in names and not uv_installs(names, comando, leggi):
            pass  # a bare interpreter: nothing is resolved or installed
        elif not frozen:
            report.block(f"{where}: `uv run` without --frozen or --locked")
        else:
            report.accept("uv-run-frozen")
        for opzione in ("--directory", "--project"):
            cartella = values.get(opzione)
            if cartella is not None and (not _CARTELLA_DEL_PLUGIN.match(cartella) or ".." in cartella):
                report.block(f"{where}: `uv run {opzione} {cartella}` is not inside the plugin's own folder")
        if "--project" not in names and "--directory" not in names:
            # Started from the user's folder, uv runs the Python environment it finds there
            # (its .pth files execute) and reads its uv.toml.
            report.block(f"{where}: `uv run` with neither --project nor --directory starts "
                         "from the user's folder")
        report.accept("subfolder-program")
        if "--project" in values and files is not None:
            lock = values["--project"].replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN) + "/uv.lock"
            if frozen and lock not in files:
                report.block(f"{where}: `uv run --frozen/--locked` needs {lock}, "
                             "which is not tracked (check .gitignore)")
    if command in LAUNCHERS:
        package = next((a for a in args if not a.startswith("-")), "")
        if not re.search(r"(@|==)\d", package):
            report.block(f"{where}: {command} package not pinned to an exact version")


def _lettore(rev: str, files: dict[str, tuple[str, int]]):
    """The text of a plugin file a launcher names, at *rev*; None when it is not tracked."""
    def leggi(percorso: str) -> "str | None":
        path = percorso.replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN)
        if path not in files:
            return None
        return blob(rev, path).decode("utf-8", "replace")
    return leggi


def check_runtime(rev: str, files: dict[str, tuple[str, int]], report: Report) -> None:
    mcp = f"{PLUGIN}/.mcp.json"
    if mcp in files:
        try:
            servers = json.loads(blob(rev, mcp))["mcpServers"]
        except (ValueError, KeyError) as exc:
            report.block(f"{mcp} can't be parsed: {exc}")
            servers = {}
        for name, server in servers.items():
            if server.get("url"):
                if not re.match(r"(https|wss)://", server["url"]):
                    report.block(f"{mcp} {name}: URL is not https")
                continue
            check_command(f"{mcp} {name}", server.get("command", ""),
                          server.get("args", []), report, files, _lettore(rev, files))

    hooks_path = f"{PLUGIN}/hooks/hooks.json"
    if hooks_path in files:
        try:
            hooks = json.loads(blob(rev, hooks_path))["hooks"]
        except (ValueError, KeyError) as exc:
            report.block(f"{hooks_path} is invalid: {exc}")
            hooks = {}
        for event, groups in hooks.items():
            for group in groups:
                for hook in group.get("hooks", []):
                    if hook.get("type") != "command":
                        continue
                    words = re.findall(r'"[^"]*"|\S+', hook["command"])
                    words = [w.strip('"') for w in words]
                    check_command(f"{hooks_path} {event}", words[0], words[1:],
                                  report, files, _lettore(rev, files))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rev", default="HEAD")
    rev = parser.parse_args().rev

    entries = tree(rev)
    files = {path: (mode, size) for mode, _kind, size, path in entries
             if path.startswith(f"{PLUGIN}/")}
    report = Report()
    check_repository(rev, entries, report)
    check_manifest(rev, files, report)
    check_files(rev, files, report)
    check_runtime(rev, files, report)

    for message in report.blocks:
        print(f"BLOCKS  {message}")
    for message in report.holds:
        print(f"HOLD    {message}")
    for key in sorted(report.accepted):
        print(f"ACCEPTED HOLD  {key}: {ACCEPTED_HOLDS[key]}")
    if report.blocks or report.holds:
        print(f"\nFAIL: {len(report.blocks)} blocking, {len(report.holds)} held "
              f"for a reviewer ({PLUGIN}/ at {rev}).")
        return 1
    print(f"OK: {PLUGIN}/ at {rev} passes the directory checks this script "
          f"replays ({len(files)} files; {len(report.accepted)} accepted holds).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
