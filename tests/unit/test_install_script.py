"""install.py and the Claude configuration files it edits (#133)."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("install_script", ROOT / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_desktop_config_saved_with_a_bom_keeps_its_other_servers(tmp_path, monkeypatch):
    """On Windows an editor may save the Claude Desktop config with a BOM. Read as plain
    UTF-8 it was «not valid» and rewritten from scratch, dropping the user's other servers
    (a .bak was kept); read in the locale encoding it could not be parsed at all."""
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
