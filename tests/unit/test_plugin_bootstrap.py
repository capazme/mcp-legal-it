"""The plugin's two-phase start (plugin/server/bootstrap.py).

On a first start the server's libraries are not installed yet, and Claude Code
gives a stdio server 30 seconds to answer `initialize`. The bootstrap answers
at once, installs the libraries in the background, then hands the session to
the real server: these tests drive that sequence against a stand-in server.
"""
from __future__ import annotations

import importlib.util
import json
import os
import queue
import sys
import textwrap
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "plugin" / "server" / "bootstrap.py"


def load_bootstrap():
    spec = importlib.util.spec_from_file_location("legal_it_bootstrap", BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap = load_bootstrap()

FAKE_SERVER = textwrap.dedent('''
    import json, sys
    for raw in sys.stdin:
        msg = json.loads(raw)
        if "id" not in msg:
            continue
        if msg["method"] == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "Legal IT", "version": "real"}}
        elif msg["method"] == "tools/list":
            result = {"tools": [{"name": "cite_law", "inputSchema": {"type": "object"}}]}
        else:
            result = {"echo": msg["method"]}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\\n")
        sys.stdout.flush()
''')


class Session:
    """A client on one side of the relay, with the real server stubbed out."""

    def __init__(self, tmp_path: Path, sync) -> None:
        server = tmp_path / "server.py"
        server.write_text(FAKE_SERVER, encoding="utf-8")
        to_relay_r, self._to_relay_w = os.pipe()
        from_relay_r, from_relay_w = os.pipe()
        self._in = os.fdopen(to_relay_r, "rb")
        self._out = os.fdopen(from_relay_w, "wb")
        self.replies = os.fdopen(from_relay_r, "rb")
        self.exit_codes: list[int] = []
        self.relay = bootstrap.Relay(self._in, self._out, sync,
                                     [sys.executable, str(server)],
                                     on_server_exit=self.exit_codes.append)
        self.thread = threading.Thread(target=self.relay.run, daemon=True)
        self.thread.start()
        self.inbox: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for raw in iter(self.replies.readline, b""):
            self.inbox.put(json.loads(raw))

    def send(self, message: dict) -> None:
        os.write(self._to_relay_w, json.dumps(message).encode() + b"\n")

    def request(self, request_id: int, method: str, params: dict | None = None) -> dict:
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method,
                   "params": params or {}})
        return self.next(lambda m: m.get("id") == request_id)

    def next(self, match, timeout: float = 10) -> dict:
        while True:
            message = self.inbox.get(timeout=timeout)
            if match(message):
                return message

    def close(self) -> None:
        os.close(self._to_relay_w)
        self.thread.join(timeout=10)


def handshake(session: Session) -> dict:
    reply = session.request(1, "initialize", {"protocolVersion": "2025-06-18"})
    session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return reply


def test_first_start_answers_at_once_then_hands_over_to_the_server(tmp_path):
    release = threading.Event()
    session = Session(tmp_path, sync=lambda: release.wait(10) and None)

    reply = handshake(session)
    capabilities = reply["result"]["capabilities"]
    assert capabilities["tools"] == {"listChanged": True}
    assert session.request(2, "tools/list")["result"] == {"tools": []}
    call = session.request(3, "tools/call", {"name": "cite_law", "arguments": {}})
    assert call["result"]["isError"] is True
    assert "si sta preparando" in call["result"]["content"][0]["text"]

    release.set()  # the libraries are in
    session.next(lambda m: m.get("method") == "notifications/tools/list_changed")
    tools = session.request(4, "tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["cite_law"]
    # The replayed initialize was swallowed, not sent twice to the client.
    assert session.request(5, "ping")["result"] == {"echo": "ping"}
    session.close()


def test_a_failed_install_says_so_on_every_tool_call(tmp_path):
    session = Session(tmp_path, sync=lambda: "uv sync exit 2")
    handshake(session)
    session.relay.got_init.wait(5)
    for _ in range(50):  # the sync thread records the failure
        if session.relay.failure:
            break
        threading.Event().wait(0.05)
    call = session.request(2, "tools/call", {"name": "cite_law", "arguments": {}})
    assert call["result"]["isError"] is True
    assert "uv sync exit 2" in call["result"]["content"][0]["text"]
    assert session.request(3, "tools/list")["result"] == {"tools": []}
    session.close()


def test_unknown_requests_get_an_error_not_silence(tmp_path):
    session = Session(tmp_path, sync=lambda: threading.Event().wait(10) and None)
    handshake(session)
    reply = session.request(2, "prompts/get", {"name": "parere_legale"})
    assert reply["error"]["code"] == -32603
    session.close()


def test_the_environment_counts_as_ready_only_for_this_lock(tmp_path, monkeypatch):
    lock = tmp_path / "uv.lock"
    lock.write_text("version = 1\n", encoding="utf-8")
    marker = tmp_path / ".legal-it-synced"
    monkeypatch.setattr(bootstrap, "LOCK", lock)
    monkeypatch.setattr(bootstrap, "MARKER", marker)
    assert not bootstrap.in_sync()
    marker.write_text(bootstrap.lock_digest(), encoding="utf-8")
    assert bootstrap.in_sync()
    lock.write_text("version = 2\n", encoding="utf-8")  # a plugin update
    assert not bootstrap.in_sync()


def test_the_sync_is_frozen_on_the_plugin_project(monkeypatch):
    monkeypatch.setenv("UV", "/opt/uv")
    command = bootstrap.sync_command()
    assert command[:3] == ["/opt/uv", "sync", "--frozen"]
    assert command[command.index("--project") + 1] == str(BOOTSTRAP.parent)


def test_the_bootstrap_uses_only_the_standard_library():
    """It runs before the libraries are installed: nothing else exists yet."""
    imported = {
        line.split()[1].split(".")[0]
        for line in BOOTSTRAP.read_text(encoding="utf-8").splitlines()
        if line.startswith(("import ", "from ")) and not line.startswith("from __future__")
    }
    assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)
