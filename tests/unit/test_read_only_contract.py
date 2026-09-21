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
import os
import pathlib
import shutil

import pytest

from .mcp_harness import (
    REPO,
    arguments_for as _arguments,
    call_tools as _call_tools,
    server_env,
    tools as _tools,
)


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

    env = server_env(sandbox, tmp_path)
    arguments = {tool['name']: _arguments(tool) for tool in local}
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
    # keep actually exercising the tools. Every local tool answered when this was
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


