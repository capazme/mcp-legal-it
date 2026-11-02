"""Every uv launcher we ship starts from our own folder, never from the one the user opened.

The citation hook and the MCP server run with the user's folder as working directory.
Started from there, `uv run --no-project` (with or without `--isolated --no-config`)
discovers a Python `.venv` in that folder or above it and *executes its interpreter*
to read its facts, so the environment's `.pth` files run; it also reads that folder's
`uv.toml`. Opening an untrusted repository would run its code at every end of turn.

Two forms are safe, and every launcher must use one:
- `--directory <our folder>` (with `--isolated --no-config`): discovery starts from
  the plugin or the server's folder;
- `--project <our server>`: uv uses the project's own environment and configuration.

Not covered, because the user controls them: an active virtual environment
(`VIRTUAL_ENV`) and a `.venv` in a folder that contains ours are still used.

The `.pth` tests build a NEW `.venv` in tmp_path for every run: uv caches an
interpreter's facts per path and mtime, so a reused `.venv` looks clean when it is not.
The counter-test runs the hook's command without `--directory` and must see the
`.pth` run, or the test proves nothing.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugin"
SERVER = PLUGIN / "server"

sys.path.insert(0, str(ROOT / "scripts"))
import check_directory_readiness as readiness  # noqa: E402

sys.path.pop(0)

# Where a shipped launcher may start uv: the plugin's folder, or the .mcpb bundle's.
_CARTELLA_SPEDITA = re.compile(r"^\$\{(?:CLAUDE_PLUGIN_ROOT|__dirname)\}(?:/|$)")
# A launcher the user copies into their own configuration names the checkout instead.
_CARTELLA_DOCUMENTATA = re.compile(r"^/path/to/mcp-legal-it/plugin/server$")
_DOCUMENTATI = ("config.toml.example", "docs/openai.md")


# --- the launchers we ship or document --------------------------------------------------

def _hook_commands() -> dict[str, list[str]]:
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    return {f"hooks.json {event}": shlex.split(h["command"])
            for event, groups in hooks.items() for g in groups for h in g["hooks"] if h.get("type") == "command"}


def _mcp_json(path: Path) -> dict[str, list[str]]:
    servers = json.loads(path.read_text(encoding="utf-8"))["mcpServers"]
    return {f"{path.name} {name}": [s["command"], *s["args"]] for name, s in servers.items() if s.get("command")}


def _manifest(path: Path = ROOT / "dxt" / "manifest.json") -> dict[str, list[str]]:
    config = json.loads(path.read_text(encoding="utf-8"))["server"]["mcp_config"]
    return {str(path.relative_to(ROOT)): [config["command"], *config["args"]]}


def _uvx_lines() -> dict[str, list[str]]:
    """`uvx … mcp-legal-it` in the user docs: a tool environment, never the folder's (tested below)."""
    out = {}
    for path in (ROOT / "README.md", ROOT / "docs" / "migration" / "2.x-to-3.0.md"):
        for i, riga in enumerate(re.findall(r"^\s*(uvx [^\n]*)", path.read_text(encoding="utf-8"), re.M)):
            out[f"{path.relative_to(ROOT)} uvx #{i}"] = shlex.split(riga)
    assert out, "no uvx launcher in the docs any more: update this test"
    return out


def _toml_args(text: str) -> list[str]:
    tomllib = pytest.importorskip("tomllib")
    server = tomllib.loads(text)["mcp_servers"]["legal_it"]
    return [server["command"], *server["args"]]


def _codex_config() -> dict[str, list[str]]:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import build_targets
    finally:
        sys.path.pop(0)
    return {"config.toml.example": _toml_args(build_targets._OPENAI_CONFIG_TOML_EXAMPLE)}


def _openai_docs() -> dict[str, list[str]]:
    text = (ROOT / "docs" / "openai.md").read_text(encoding="utf-8")
    blocchi = [b for b in re.findall(r"```toml\n(.*?)```", text, re.S) if 'command = "uv"' in b]
    assert blocchi, "docs/openai.md has no uv launcher block any more: update this test"
    return {f"docs/openai.md #{i}": _toml_args(b) for i, b in enumerate(blocchi)}


def _skill_lines() -> dict[str, list[str]]:
    out = {}
    for path in [*(ROOT / "content" / "skills").rglob("*.md"), *(PLUGIN / "skills").rglob("*.md")]:
        testo = path.read_text(encoding="utf-8").replace("\\\n", " ")
        for i, riga in enumerate(re.findall(r"^\s*(uv run [^\n]*)", testo, re.M)):
            out[f"{path.relative_to(ROOT)} #{i}"] = shlex.split(riga)
    return out


def launchers() -> dict[str, list[str]]:
    found = {**_hook_commands(), **_mcp_json(PLUGIN / ".mcp.json"), **_mcp_json(ROOT / ".mcp.json.example"),
             **_manifest(), **_manifest(SERVER / "manifest.json"), **_codex_config(), **_openai_docs(),
             **_skill_lines()}
    return {where: argv for where, argv in found.items() if argv[:2] == ["uv", "run"]}


# Files that hold a launcher, each read by one of the functions above. A new file with a
# uv launcher of our programs fails test_no_launcher_is_left_out until it is read here.
_FILE_LETTI = {".mcp.json.example", "plugin/.mcp.json", "plugin/hooks/hooks.json", "dxt/manifest.json",
               "plugin/server/manifest.json", "scripts/build_targets.py", "docs/openai.md", "README.md",
               "docs/migration/2.x-to-3.0.md"}
# Files that mention uv in prose, run it inside this repository (CONTRIBUTING's dev commands)
# or call it with --project (bootstrap.py).
_SOLO_TESTO = {"SECURITY.md", "docs/plugin.md", "release.py", "plugin/server/bootstrap.py", "CONTRIBUTING.md",
               "Dockerfile", "plugin/README.md", "plugin/server/pyproject.toml"}


def test_every_launcher_starts_from_our_folder():
    found = launchers()
    assert len(found) >= 8, found.keys()
    for where, argv in found.items():
        names, values, unknown, _comando = readiness.uv_run_options(argv[1:])
        assert not unknown, (where, unknown)
        for opzione in ("--directory", "--project"):
            assert ".." not in values.get(opzione, ""), (where, opzione, values[opzione])
        if "--project" in names:
            continue  # the server's own environment and configuration
        assert "--directory" in names, f"{where}: uv starts from the user's folder"
        cartella = _CARTELLA_DOCUMENTATA if where.startswith(_DOCUMENTATI) else _CARTELLA_SPEDITA
        assert cartella.match(values["--directory"]), (where, values["--directory"])
        if "--no-project" in names:
            assert "--isolated" in names and "--no-config" in names, where
        # Without --no-project, --directory names our server's project: its own environment.


def test_the_uvx_launchers_run_a_tool_environment():
    for where, argv in _uvx_lines().items():
        assert argv[0] == "uvx" and argv[-1] == "mcp-legal-it", (where, argv)


def test_the_codex_docs_are_the_generated_configuration():
    # Every argument, not only the options: a pin that drifts here is what users copy.
    generato = _codex_config()["config.toml.example"]
    for where, argv in _openai_docs().items():
        assert argv == generato, where


def test_no_launcher_is_left_out():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    lancio = re.compile(r'uv run|uvx|uv tool run|"command":\s*"uv"|command\s*=\s*"uv"')
    programma = re.compile(r"(run_server|bootstrap|citation-gate)\.py|mcp_legal_it|mcp-legal-it")
    for name in tracked:
        if name.startswith(("tests/", "docs/specs/", "docs/release-notes/", "content/", "plugin/skills/")) \
                or "CHANGELOG" in name:
            continue
        try:
            testo = (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if lancio.search(testo) and programma.search(testo):
            assert name in _FILE_LETTI | _SOLO_TESTO, f"{name} holds a uv launcher this test does not read"


# --- the directory checker reads the same options --------------------------------------

def _check(argv: list[str], leggi=None) -> readiness.Report:
    report = readiness.Report()
    readiness.check_command("x", argv[0], argv[1:], report, None, leggi)
    return report


@pytest.mark.parametrize("argv", [
    ["uv", "run", "--no-project", "--isolated", "--no-config", "--directory", "${CLAUDE_PLUGIN_ROOT}",
     "--python", "3.12", "python", "${CLAUDE_PLUGIN_ROOT}/hooks/citation-gate.py", "--with", "x"],
    ["uv", "run", "--frozen", "--no-sync", "--python", "3.12", "--project", "${CLAUDE_PLUGIN_ROOT}/server",
     "python", "${CLAUDE_PLUGIN_ROOT}/server/bootstrap.py"],
], ids=["hook-with-after-the-command", "server-project"])
def test_the_checker_accepts_our_launchers(argv):
    assert _check(argv).blocks == []


@pytest.mark.parametrize("argv, motivo", [
    (["uv", "run", "--no-project", "--python", "3.12", "python", "g.py"], "user's folder"),
    (["uv", "run", "--no-project", "--directory", "d", "-w", "x", "python", "g.py"], "--frozen"),
    (["uv", "run", "--no-project", "--directory", "d", "--with=x", "python", "g.py"], "--frozen"),
    (["uv", "run", "--no-project", "--directory", "d", "--with-requirements", "r.txt", "python", "g.py"], "--frozen"),
    (["uv", "run", "--no-project", "--directory", "d", "--script", "g.py"], "--frozen"),
    (["uv", "run", "--no-project", "--directory", "d", "-s", "g.py"], "--frozen"),
    (["uv", "run", "--no-project", "--directory", "d", "--made-up", "python", "g.py"], "does not know"),
    (["uv", "run", "--no-project", "--directory", "d", "-qw", "six", "python", "g.py"], "--frozen"),
    (["uv", "run", "--no-project", "--directory", "d", "-wsix", "python", "g.py"], "--frozen"),
    (["uv", "run", "--no-project", "--directory", "d", "-qs", "g.py"], "--frozen"),
    (["uv", "run", "--no-project", "--directory", "d", "-qx", "python", "g.py"], "does not know"),
], ids=["no-directory", "-w", "--with=", "--with-requirements", "--script", "-s", "unknown-option",
        "grouped-qw", "glued-wsix", "grouped-qs", "grouped-unknown"])
def test_the_checker_blocks(argv, motivo):
    blocks = _check(argv).blocks
    assert any(motivo in b for b in blocks), blocks


@pytest.mark.parametrize("opzione, cartella", [
    ("--directory", "/tmp/elsewhere"),
    ("--directory", "."),
    ("--directory", "${CLAUDE_PLUGIN_ROOT}/../.."),
    ("--directory", "${HOME}"),
    ("--project", "${CLAUDE_PLUGIN_ROOT}/../other"),
    ("--project", "server"),
], ids=["absolute-elsewhere", "dot", "dotdot", "home", "project-dotdot", "project-relative"])
def test_the_checker_blocks_a_folder_outside_the_plugin(opzione, cartella):
    argv = ["uv", "run", "--frozen", "--no-sync", opzione, cartella, "python", "${CLAUDE_PLUGIN_ROOT}/g.py"]
    blocks = _check(argv).blocks
    assert any("is not inside the plugin's own folder" in b for b in blocks), blocks


@pytest.mark.parametrize("testo, blocca", [
    ("# /// script\n# dependencies = ['six']\n# ///\nimport six\n", True),  # uv reads it without --script
    (None, True),  # a script the checker cannot read: assumed to install
    ("import sys\n", False),
], ids=["inline-metadata", "unreadable", "plain"])
def test_a_script_run_as_the_command_is_read_for_inline_metadata(testo, blocca):
    argv = ["uv", "run", "--no-project", "--directory", "${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PLUGIN_ROOT}/g.py"]
    blocks = _check(argv, lambda percorso: testo).blocks
    assert any("--frozen" in b for b in blocks) is blocca, blocks


def test_the_hook_runs_python_so_its_file_is_never_read_as_a_script():
    # «python g.py»: uv does not read inline metadata of a file given to the interpreter.
    argv = _hook_commands()["hooks.json Stop"]
    assert _check(argv, lambda percorso: "# /// script\n# ///\n").blocks == []


# --- the .pth of the opened folder never runs (a NEW .venv every run) -------------------

def _uv():
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not on PATH")
    return uv


def _cartella_ostile(tmp_path: Path) -> tuple[Path, Path]:
    """A folder with a fresh Python 3.12 .venv whose .pth leaves a mark, and a uv.toml."""
    uv = _uv()
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    made = subprocess.run([uv, "venv", "-q", "--python", "3.12", str(repo / ".venv")],
                          capture_output=True, text=True, timeout=180)
    if made.returncode != 0:
        pytest.skip(f"uv cannot make a Python 3.12 venv here: {made.stderr[-300:]}")
    python = next(p for p in (repo / ".venv" / "bin" / "python", repo / ".venv" / "Scripts" / "python.exe")
                  if p.exists())
    site = subprocess.run([str(python), "-c", "import site; print(site.getsitepackages()[0])"],
                          capture_output=True, text=True, timeout=60, check=True).stdout.strip()
    segno = tmp_path / "pth-ran"
    (Path(site) / "zz_untrusted.pth").write_text(
        f"import pathlib; pathlib.Path({str(segno)!r}).write_text('ran')\n", encoding="utf-8")
    (repo / "uv.toml").write_text(f'cache-dir = "{(tmp_path / "foreign-cache").as_posix()}"\n', encoding="utf-8")
    return repo / "sub", segno


def _lancia(argv: list[str], cwd: Path, *, stdin: str = "") -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "UV_CACHE_DIR")}
    return subprocess.run(argv, cwd=cwd, input=stdin, capture_output=True, text=True, timeout=300, env=env)


def _risolvi(argv: list[str]) -> list[str]:
    return [a.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN)).replace("${__dirname}", str(PLUGIN)) for a in argv]


def test_the_hook_does_not_run_the_opened_folders_environment(tmp_path):
    cwd, segno = _cartella_ostile(tmp_path)
    argv = _risolvi(_hook_commands()["hooks.json Stop"])
    done = _lancia(argv, cwd, stdin="{}")
    assert done.returncode == 0, done.stderr[-500:]
    assert not segno.exists(), "the hook ran the opened folder's environment"
    assert not (tmp_path / "foreign-cache").exists(), "the hook read the opened folder's uv.toml"


def test_counter_test_without_directory_the_folders_environment_runs(tmp_path):
    # The same command without --directory: the .pth must run, or the test above proves nothing.
    cwd, segno = _cartella_ostile(tmp_path)
    argv = _hook_commands()["hooks.json Stop"]
    i = argv.index("--directory")
    done = _lancia(_risolvi(argv[:i] + argv[i + 2:]), cwd, stdin="{}")
    assert done.returncode == 0, done.stderr[-500:]
    assert segno.exists(), "uv no longer runs a .venv it discovers: revisit this test's premise"


def test_the_server_launcher_does_not_run_the_opened_folders_environment(tmp_path):
    # The .mcpb launcher's discovery options, with nothing to install and a probe as program.
    cwd, segno = _cartella_ostile(tmp_path)
    argv = _manifest()["dxt/manifest.json"]
    names_end = argv.index("${__dirname}/server/run_server.py")
    opzioni, i = [], 2
    while i < names_end:
        if argv[i] == "--with":
            i += 2
            continue
        opzioni.append(argv[i])
        i += 1
    probe = [*argv[:2], *opzioni, "python", "-c", "import os; print(os.getcwd())"]
    done = _lancia([a.replace("${__dirname}", str(PLUGIN)) for a in probe], cwd)
    assert done.returncode == 0, done.stderr[-500:]
    assert not segno.exists(), "the server launcher ran the opened folder's environment"
    assert Path(done.stdout.strip()) == SERVER


def test_the_project_launcher_does_not_run_the_opened_folders_environment(tmp_path):
    # plugin/.mcp.json and bootstrap.py: --project on the server's own lock, here on a copy.
    cwd, segno = _cartella_ostile(tmp_path)
    progetto = tmp_path / "server"
    progetto.mkdir()
    for nome in ("pyproject.toml", "uv.lock"):
        shutil.copy2(SERVER / nome, progetto / nome)
    done = _lancia([_uv(), "run", "--frozen", "--no-sync", "--python", "3.12", "--project", str(progetto),
                    "python", "-c", "pass"], cwd)
    assert done.returncode == 0, done.stderr[-500:]
    assert not segno.exists(), "the --project launcher ran the opened folder's environment"
    assert not (tmp_path / "foreign-cache").exists(), "the --project launcher read the opened folder's uv.toml"


def test_uvx_does_not_run_the_opened_folders_environment(tmp_path):
    # The README's `uvx --from git+… mcp-legal-it`, with a small tool already in uv's cache:
    # a tool environment, built on uv's own Python, never on the folder's .venv.
    cwd, segno = _cartella_ostile(tmp_path)
    done = _lancia([_uv(), "tool", "run", "--offline", "--python", "3.12", "--from", "httpx[cli]", "httpx",
                    "--help"], cwd)
    if done.returncode != 0:
        pytest.skip(f"httpx[cli] is not in uv's cache (offline run): {done.stderr[-200:]}")
    assert not segno.exists(), "uvx ran the opened folder's environment"
    assert not (tmp_path / "foreign-cache").exists(), "uvx read the opened folder's uv.toml"
