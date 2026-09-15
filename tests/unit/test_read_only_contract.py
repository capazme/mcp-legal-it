"""Prove the read-only annotations at runtime, not just from the source.

`test_tool_annotations.py` checks that the policy matches the audit, and the
audit derives `readOnlyHint` from the call graph. That is static evidence: a
tool could still write through a path the audit cannot follow (a library that
resolves a directory at import time, a subprocess, a cache module we do not
reach). This test supplies the dynamic half:

* the server is started in a sandbox -- its own `HOME`, its own
  `MCP_CACHE_DIR` -- so anything written under the user's home lands in the
  sandbox and is visible;
* every local read-only tool (no network) is called once with arguments
  generated from its input schema, plus curated values where the schema is not
  enough;
* the sandbox, the checkout and the real MCP cache are fingerprinted before and
  after, and any difference fails the test.

Tools that reach an external service are excluded: they need real upstream
data, they are exercised by the `live` marker suite instead.

Run just this file with:

    pytest tests/unit/test_read_only_contract.py -q
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
LAUNCHER_SERVER = REPO / "plugin/server/run_server.py"

# Arguments the schema cannot express well enough: enums worth pinning, names
# that look like dates but are not, free-form strings with a documented format.
CURATED = {
    "codice_fiscale": {"nome": "Mario", "cognome": "Rossi", "data_nascita": "1980-01-01",
                       "sesso": "M", "comune_nascita": "Roma"},
    "verifica_iban": {"iban": "IT60X0542811101000000123456"},
    "verifica_partita_iva": {"partita_iva": "12345678903"},
    "scorporo_iva": {"importo": 1220, "aliquota": 22},
    "calcolo_hash": {"testo": "contratto"},
    "cerca_codice_tributo": {"query": "1001"},
    "cerca_gazzetta_ufficiale": {"query": "decreto"},
    "verifica_mediazione_obbligatoria": {"materia": "condominio"},
}
# Free-form strings: an empty value usually makes the tool reject the call
# before doing any work, which would prove nothing.
STRING_HINTS = (
    ("query", "condominio"), ("testo", "testo di prova"), ("riferimento", "art. 2043 c.c."),
    ("articolo", "art. 2043 c.c."), ("norma", "art. 2043 c.c."), ("materia", "civile"),
    ("tipo", "ordinario"), ("nome", "Mario"), ("cognome", "Rossi"), ("titolo", "Atto"),
    ("descrizione", "descrizione"), ("iban", "IT60X0542811101000000123456"),
    ("piva", "12345678903"), ("testo_contratto", "locazione"), ("query_text", "eredità"),
)


def _value_for(name: str, schema: dict):
    if "enum" in schema:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    kind = schema.get("type")
    lowered = name.lower()
    if kind == "boolean":
        return True
    if kind == "array":
        item = schema.get("items") or {}
        if item.get("type") in ("integer", "number"):
            return [1]
        return ["x"]
    if kind in ("number", "integer"):
        if any(key in lowered for key in ("percentuale", "tasso", "aliquota", "pct", "interesse")):
            return 5.0 if kind == "number" else 5
        if lowered.startswith("anno") or lowered.endswith("_anno"):
            return 2024 if kind == "integer" else 2024.0
        if "giorni" in lowered:
            return 30 if kind == "integer" else 30.0
        if "mesi" in lowered:
            return 12 if kind == "integer" else 12.0
        if "anni" in lowered:
            return 10 if kind == "integer" else 10.0
        if any(key in lowered for key in ("n_", "numero", "num_", "quantita", "count")):
            return 2 if kind == "integer" else 2.0
        return 10000.0 if kind == "number" else 10000
    if kind == "string" or kind is None:
        if lowered.startswith("data") or lowered.endswith("_data"):
            return "2023-01-01"
        for hint, value in STRING_HINTS:
            if hint in lowered:
                return value
        return "x"
    return None


def _arguments(tool: dict) -> dict:
    name = tool["name"]
    if name in CURATED:
        return CURATED[name]
    schema = tool.get("inputSchema") or {}
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    args = {}
    for prop, spec in properties.items():
        if prop not in required and "default" in spec:
            continue
        value = _value_for(prop, spec)
        if value is not None:
            args[prop] = value
    return args


def _fingerprint(paths) -> dict:
    """Content hash of every non-generated file under each path."""
    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules",
                 ".ruff_cache", "dist", ".mypy_cache"}
    skip_suffixes = {".egg-info", ".pyc"}
    out = {}
    for root in paths:
        root = pathlib.Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if any(part in skip_dirs for part in path.parts):
                continue
            if any(str(path).endswith(suffix) for suffix in skip_suffixes):
                continue
            if not path.is_file():
                continue
            try:
                out[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
    return out


def _call_tools(env, tool_names, arguments_by_tool, timeout):
    """Start the server in `env` and call every tool, one request per tool."""
    proc = subprocess.Popen(
        [sys.executable, str(LAUNCHER_SERVER)],
        cwd=str(REPO),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    results = {}
    try:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "read-only-contract", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        ]
        request_id = 2
        by_id = {}
        for name in tool_names:
            requests.append({"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                             "params": {"name": name, "arguments": arguments_by_tool[name]}})
            by_id[request_id] = name
            request_id += 1
        for request in requests:
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
        deadline = time.time() + timeout
        while len(results) < len(tool_names) and time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                message = json.loads(line)
            except ValueError:
                continue
            name = by_id.get(message.get("id"))
            if name:
                results[name] = message
    finally:
        proc.terminate()
        try:
            proc.stderr.close()
        except Exception:
            pass
    return results


@pytest.mark.skipif(shutil.which("uv") is None, reason="no uv: cannot provision the server")
def test_local_read_only_tools_do_not_touch_the_disk(tmp_path):
    tools = _tools()
    local = [
        tool for tool in tools
        if (tool.get("annotations") or {}).get("readOnlyHint") is True
        and (tool.get("annotations") or {}).get("openWorldHint") is not True
    ]
    assert len(local) > 100, "the local read-only surface shrank unexpectedly: %d" % len(local)

    real_cache = pathlib.Path(os.environ.get("MCP_CACHE_DIR") or (pathlib.Path.home() / ".cache" / "mcp-legal-it"))
    sandbox = tmp_path / "home"
    (sandbox / ".cache").mkdir(parents=True)
    watched = [tmp_path, REPO, real_cache]
    before = _fingerprint(watched)

    env = {
        "HOME": str(sandbox),
        "XDG_CACHE_HOME": str(sandbox / ".cache"),
        "MCP_CACHE_DIR": str(sandbox / "mcp-cache"),
        "USER": os.environ.get("USER", "user"),
        "LOGNAME": os.environ.get("LOGNAME", "user"),
        "SHELL": "/bin/zsh",
        "TMPDIR": str(tmp_path),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
        # FastMCP itself would otherwise phone home to PyPI and drop a
        # version_cache.json in the (sandboxed) user data dir, which this test
        # would report as a write by a legal tool.
        "FASTMCP_CHECK_FOR_UPDATES": "off",
        "FASTMCP_SHOW_SERVER_BANNER": "false",
    }
    arguments = {tool["name"]: _arguments(tool) for tool in local}
    results = _call_tools(env, [tool["name"] for tool in local], arguments, timeout=600)

    after = _fingerprint(watched)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(path for path in set(before) & set(after) if before[path] != after[path])

    assert not added, "read-only tools created files: %s" % added[:5]
    assert not removed, "read-only tools deleted files: %s" % removed[:5]
    assert not changed, "read-only tools modified files: %s" % changed[:5]

    answered = [name for name, reply in results.items() if "result" in reply]
    errored = sorted(name for name, reply in results.items() if "result" not in reply)
    print(
        "\nread-only contract: %d tools called, %d answered, %d did not: %s"
        % (len(local), len(answered), len(errored), errored[:12])
    )
    # A coverage floor, not a correctness claim: the generated arguments must
    # keep actually exercising the tools. All 168 answered when this was
    # written, so a drop below 90% means the argument generation went stale.
    assert len(answered) >= 0.9 * len(local), (
        "only %d/%d read-only tools answered: %s" % (len(answered), len(local), errored[:8])
    )


@pytest.mark.live
def test_cache_writers_survive_an_unwritable_cache(tmp_path):
    """Caching is best-effort: a locked cache dir must not break the tool.

    Marked `live` because it needs the network to fetch something cacheable.
    """
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)
    env = {
        "HOME": str(tmp_path),
        "MCP_CACHE_DIR": str(locked),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "FASTMCP_CHECK_FOR_UPDATES": "off",
        "FASTMCP_SHOW_SERVER_BANNER": "false",
    }
    try:
        results = _call_tools(env, ["cite_law"], {"cite_law": {"reference": "art. 2043 c.c."}}, timeout=180)
        answer = results.get("cite_law", {})
        assert "result" in answer, answer
        text = answer["result"]["content"][0]["text"]
        assert "2043" in text
        assert list(locked.iterdir()) == [], "the cache dir was written to despite being read-only"
    finally:
        os.chmod(locked, 0o700)


def _tools():
    """The tool manifest, read from the server in a throwaway sandbox."""
    import asyncio

    from fastmcp import Client
    from src.server import mcp

    async def run():
        async with Client(mcp) as client:
            return await client.list_tools()

    return [
        {
            "name": tool.name,
            "inputSchema": tool.inputSchema,
            "annotations": tool.annotations.model_dump() if tool.annotations else None,
        }
        for tool in asyncio.run(run())
    ]
