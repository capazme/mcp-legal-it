"""Permission rules and the command roster of the distributed plugin.

Claude Code names a tool by where the server comes from: `mcp__legal-it__<tool>`
when the user registers the server as `legal-it` (.mcp.json, Desktop), but
`mcp__plugin_legal-it_legal-it__<tool>` when it arrives through the plugin. A rule
written for only one prefix silently stops matching under the other, and every
slash command then asks for confirmation on a tool it declares as allowed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ROOT / "plugin" / "commands"
MANUAL = "mcp__legal-it__"
PLUGIN = "mcp__plugin_legal-it_legal-it__"


def allowed_tools(path: Path) -> list[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("allowed-tools:"):
            return [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]
    return []


def test_plugin_settings_allow_both_tool_prefixes():
    allow = json.loads((ROOT / "plugin" / "settings.json").read_text())["permissions"]["allow"]
    assert MANUAL + "*" in allow
    assert PLUGIN + "*" in allow


def test_every_command_allows_each_mcp_tool_under_both_prefixes():
    seen = 0
    for path in sorted(COMMANDS.glob("*.md")):
        tools = set(allowed_tools(path))
        for tool in tools:
            if tool.startswith(MANUAL):
                seen += 1
                twin = PLUGIN + tool[len(MANUAL):]
                assert twin in tools, f"{path.name}: {tool} has no plugin-prefixed twin"
            elif tool.startswith(PLUGIN):
                assert MANUAL + tool[len(PLUGIN):] in tools, f"{path.name}: {tool} has no manual twin"
    assert seen, "no command declares an MCP tool: the check would pass vacuously"


def test_the_maintainer_only_release_command_is_not_distributed():
    assert not (COMMANDS / "release.md").exists()
    assert (ROOT / ".claude" / "commands" / "release.md").exists()


def test_the_advertised_command_count_matches_the_roster():
    n = len(list(COMMANDS.glob("*.md")))
    for rel in ("plugin/.claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        found = re.findall(r"(\d+) slash command", text)
        assert found == [str(n)], f"{rel} advertises {found}, the plugin ships {n}"
