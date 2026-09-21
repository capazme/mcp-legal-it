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
from src.server import mcp
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
    assert len(full["tools"]) == 227
    assert 0 < len(narrowed["tools"]) < len(full["tools"]), f"{profile}: {len(narrowed['tools'])} tools"
    assert must_have in narrowed["tools"]
    assert must_not_have not in narrowed["tools"]
    assert narrowed["prompts"] == full["prompts"] == 23
    assert narrowed["resources"] == full["resources"] == 15


def test_unknown_profile_falls_back_to_the_full_surface(tmp_path):
    assert len(_surface("nonexistent", tmp_path)["tools"]) == 227
