"""The shipped launchers never use the Python environment or the uv configuration of
the folder they start in.

Claude Code runs the plugin's hook, and Claude Desktop the `.mcpb` server, from a folder
the user chose. Looking for Python 3.12 there, `uv run --no-project` finds a `.venv` in
that folder or above it and runs its interpreter (`.pth` files included) to read its
facts, even with `--isolated`; it also reads a `uv.toml` there unless `--no-config`.
`--directory <our folder>` moves that search to the plugin's or extension's own folder.
`uv run --project <plugin>/server --frozen` (plugin/.mcp.json) is the other safe form:
uv works in the project, never in the starting folder.

uv caches what it read from an interpreter, keyed on its path, so a check on a `.venv`
uv has already seen proves nothing: each run below makes a new one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "plugin" / "hooks" / "hooks.json"
MCPB = REPO / "dxt" / "manifest.json"
PLUGIN_MCP = REPO / "plugin" / ".mcp.json"
SAFE = ("--no-project", "--isolated", "--no-config", "--directory")


def _uv_launches() -> list[tuple[str, list[str]]]:
    """(where, uv arguments) of every shipped `uv run`."""
    import shlex

    found = []
    for event, groups in json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                words = shlex.split(hook["command"])
                if words[0] == "uv":
                    found.append((f"hooks.json {event}", words[1:]))
    config = json.loads(MCPB.read_text(encoding="utf-8"))["server"]["mcp_config"]
    found.append(("dxt/manifest.json", config["args"]))
    for name, server in json.loads(PLUGIN_MCP.read_text(encoding="utf-8"))["mcpServers"].items():
        if server.get("command") == "uv":
            found.append((f"plugin/.mcp.json {name}", server["args"]))
    return found


def _options(args: list[str]) -> list[str]:
    """uv's own options, read as the directory check reads them."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_directory_readiness", REPO / "scripts" / "check_directory_readiness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.uv_run_options(args)


def test_the_launchers_are_found():
    where = [w for w, _ in _uv_launches()]
    assert any(w.startswith("hooks.json") for w in where)
    assert "dxt/manifest.json" in where
    assert any(w.startswith("plugin/.mcp.json") for w in where)


@pytest.mark.parametrize("where, args", _uv_launches(), ids=[w for w, _ in _uv_launches()])
def test_every_launcher_stays_out_of_the_starting_folder(where, args):
    assert args[0] == "run", where
    options = _options(args)
    if "--project" in options:
        assert "--frozen" in options or "--locked" in options, where
        assert "--no-project" not in options, where
        return
    missing = [flag for flag in SAFE if flag not in options]
    assert not missing, f"{where}: uv run without {missing}"


def _venv_with_marker(tmp_path: Path) -> tuple[Path, Path]:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not installed")
    project = tmp_path / "opened-folder"
    project.mkdir()
    made = subprocess.run([uv, "venv", "-q", "--python", "3.12", str(project / ".venv")],
                          capture_output=True, text=True, timeout=120)
    if made.returncode != 0:
        pytest.skip(f"no Python 3.12 for uv: {made.stderr.strip()[:200]}")
    site = next((project / ".venv" / "lib").glob("python3.12/site-packages"))
    marker = tmp_path / "marker"
    (site / "marker.pth").write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran')\n", encoding="utf-8")
    (project / "uv.toml").write_text("not = valid toml [\n", encoding="utf-8")
    return project, marker


def _run(command: list[str] | str, cwd: Path, env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")}
    env.update(env_extra)
    return subprocess.run(command, shell=isinstance(command, str), cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=180)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell and venv layout")
def test_the_hook_ignores_the_opened_folder(tmp_path):
    project, marker = _venv_with_marker(tmp_path)
    plugin = tmp_path / "plugin"
    (plugin / "hooks").mkdir(parents=True)
    (plugin / "hooks" / "citation-gate.py").write_text("print('gate')\n", encoding="utf-8")
    hook = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]

    done = _run(hook["command"], project, {"CLAUDE_PLUGIN_ROOT": str(plugin)})
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip() == "gate"
    assert not marker.exists(), "the hook ran the opened folder's .venv"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX venv layout")
def test_the_mcpb_launcher_ignores_the_starting_folder(tmp_path):
    """The `.mcpb` arguments with the packages left out (the flags are what is checked)."""
    project, marker = _venv_with_marker(tmp_path)
    extension = tmp_path / "extension"
    (extension / "server").mkdir(parents=True)
    (extension / "server" / "run_server.py").write_text("print('server')\n", encoding="utf-8")
    args = json.loads(MCPB.read_text(encoding="utf-8"))["server"]["mcp_config"]["args"]
    kept, words = [], iter(args)
    for word in words:
        if word == "--with":
            next(words)
            continue
        kept.append(word.replace("${__dirname}", str(extension)))

    done = _run([shutil.which("uv"), *kept], project, {})
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip() == "server"
    assert not marker.exists(), "the .mcpb launcher ran the starting folder's .venv"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell and venv layout")
def test_without_directory_the_folder_venv_runs(tmp_path):
    """The counter-check: the marker does appear for a launch without `--directory`,
    so the two tests above can fail."""
    project, marker = _venv_with_marker(tmp_path)
    script = tmp_path / "x.py"
    script.write_text("print('x')\n", encoding="utf-8")
    done = _run([shutil.which("uv"), "run", "--no-project", "--isolated", "--no-config",
                 "--python", "3.12", "python", str(script)], project, {})
    assert done.returncode == 0, done.stderr[-2000:]
    assert marker.exists()
