"""Dump the registered MCP tool names to content/tool-vocabulary.json.

Run from the repo root:  python scripts/corpus/dump_vocabulary.py
Uses mcp.list_tools() (FastMCP 3.4.7 — get_tools() no longer exists).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugin" / "server"))


async def main() -> None:
    from mcp_legal_it.lib import _brocardi_switch
    from mcp_legal_it.server import mcp  # imports all 33 tool modules

    # The vocabulary is every registered tool, Brocardi's included: Brocardi is off by
    # default (LI-079), so its tools are listed only with the switch on for this listing.
    _brocardi_switch.check_can_switch_on()
    token = _brocardi_switch.set_for_context(True)
    try:
        tools = await mcp.list_tools()
    finally:
        _brocardi_switch.reset(token)
    names = sorted(t.name for t in tools)
    out = ROOT / "content" / "tool-vocabulary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(names, indent=0) + "\n", encoding="utf-8")
    print(f"{len(names)} tool names -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
