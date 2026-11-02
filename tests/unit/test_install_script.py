"""install.py configures only a local server: no remote option, no hard-coded tunnel URL.

The 2.x installer offered a "remote (SSE)" plugin mode pointing at a personal ngrok address
written in the code of a public repository. The 3.0 line drops it: the plugin always runs the
server on the user's machine.
"""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "install.py").read_text(encoding="utf-8")


def _load():
    spec = importlib.util.spec_from_file_location("install_script", ROOT / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_tunnel_or_remote_url_in_the_installer():
    assert "ngrok" not in SOURCE.lower()
    assert not re.search(r"https?://[^\s\"']*/(?:sse|mcp)\b", SOURCE), "a remote MCP endpoint in install.py"


def test_no_remote_mode_option():
    assert '"--mode"' not in SOURCE and "select_plugin_mode" not in SOURCE


def test_the_plugin_config_runs_the_server_locally():
    config = _load()._build_plugin_mcp_config()
    entry = config["mcpServers"]["legal-it"]
    assert "url" not in entry and "command" in entry


def test_a_desktop_config_saved_with_a_bom_keeps_its_other_servers(tmp_path, monkeypatch):
    """#133: on Windows an editor may save the Claude Desktop config with a BOM. Read as
    plain UTF-8 it was «not valid» and rewritten from scratch, dropping the user's other
    servers (a .bak was kept); read in the locale encoding it could not be parsed at all."""
    import json

    install = _load()
    config = tmp_path / "claude_desktop_config.json"
    config.write_bytes(b"\xef\xbb\xbf" + json.dumps(
        {"mcpServers": {"altro": {"command": "altro-server", "args": ["--perché"]}}},
        ensure_ascii=False).encode("utf-8"))
    monkeypatch.setattr(install, "_CLAUDE_DESKTOP_PATHS", {install.platform.system(): config})
    monkeypatch.setattr(install, "_is_claude_desktop_running", lambda: False)

    assert install.install_claude_desktop(["full"], non_interactive=True)
    written = json.loads(config.read_text(encoding="utf-8"))
    assert written["mcpServers"]["altro"] == {"command": "altro-server", "args": ["--perché"]}
    assert "legal-it" in written["mcpServers"]
