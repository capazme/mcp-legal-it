"""LEGAL_PROFILE narrows the tool surface and leaves prompts and resources alone.

The profiles silently stopped working when FastMCP 3 dropped the
`include_tags` attribute (the assignment in server.py became a no-op and every
profile exposed all the tools). The server is imported in a subprocess because
the profile is read once at import time.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SNIPPET = """
import asyncio, json, sys
sys.path.insert(0, "plugin/server")
from fastmcp import Client
from mcp_legal_it.server import mcp
async def main():
    async with Client(mcp) as c:
        tools = await c.list_tools()
        return {"tools": sorted(t.name for t in tools),
                "prompts": len(await c.list_prompts()),
                "resources": len(await c.list_resources())}
print(json.dumps(asyncio.run(main())))
"""


def _surface(profile: str, home: Path) -> dict:
    # A throwaway HOME so the import never touches the real cache directory.
    env = {"LEGAL_PROFILE": profile, "PATH": "/usr/bin:/bin", "HOME": str(home), "LEGAL_CACHE": "off"}
    out = subprocess.run([sys.executable, "-c", SNIPPET], cwd=REPO, env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("profile,must_have,must_not_have", [
    ("penale", "prescrizione_reato", "calcolo_irpef"),
    ("privacy", "genera_dpia", "rendimento_btp"),
    ("cowork", "cite_law", "calcolo_imu"),
])
def test_profile_narrows_tools_and_keeps_prompts_and_resources(profile, must_have, must_not_have, tmp_path):
    full = _surface("full", tmp_path)
    narrowed = _surface(profile, tmp_path)
    assert len(full["tools"]) == 228
    assert 0 < len(narrowed["tools"]) < len(full["tools"]), f"{profile}: {len(narrowed['tools'])} tools"
    assert must_have in narrowed["tools"]
    assert must_not_have not in narrowed["tools"]
    assert narrowed["prompts"] == full["prompts"] == 23
    assert narrowed["resources"] == full["resources"] == 15


@pytest.mark.parametrize("profile", ["nonexistent", "calcolo", "Calcoli"])
def test_an_unknown_profile_refuses_to_start(profile, tmp_path):
    # #76: it used to fall back to `full` in silence, exposing the online tools a reduced
    # profile was asked to leave out.
    env = {"LEGAL_PROFILE": profile, "PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "LEGAL_CACHE": "off"}
    out = subprocess.run([sys.executable, "-c", SNIPPET], cwd=REPO, env=env, capture_output=True, text=True)
    assert out.returncode != 0
    assert f"LEGAL_PROFILE={profile!r} non è un profilo" in out.stderr
    assert "calcoli" in out.stderr  # the valid names are listed


def test_the_console_script_prints_the_refusal_without_a_traceback(tmp_path):
    env = {"LEGAL_PROFILE": "nonexistent", "PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "LEGAL_CACHE": "off",
           "PYTHONPATH": str(REPO / "plugin" / "server")}
    out = subprocess.run([sys.executable, "-m", "mcp_legal_it.cli"], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 1
    assert out.stderr.startswith("mcp-legal-it: LEGAL_PROFILE='nonexistent' non è un profilo")
    assert "Traceback" not in out.stderr


@pytest.mark.parametrize("profile", ["", "  "])
def test_a_blank_profile_is_full(profile, tmp_path):
    assert len(_surface(profile, tmp_path)["tools"]) == 228


def test_the_calcoli_profile_never_goes_online(tmp_path):
    # Documented as "solo calcoli, nessuna connessione": every tool it exposes is local.
    from mcp_legal_it.source_bindings import TOOL_SOURCES
    from mcp_legal_it.tool_annotations import OPEN_WORLD

    tools = set(_surface("calcoli", tmp_path)["tools"])
    assert len(tools) == 144
    assert "interessi_legali" in tools and "stato_server" in tools
    assert not tools & set(OPEN_WORLD)
    assert not {name for name in tools if TOOL_SOURCES.get(name)}
