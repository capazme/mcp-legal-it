#!/usr/bin/env python3
"""Two-phase start of the plugin's MCP server.

Claude Code gives a stdio server 30 seconds to answer `initialize`, and a
plugin cannot change that. On a first start the server's libraries are not
installed yet: `uv` has to download ~40 MB, which on a slow or crowded network
takes longer, so the server showed up as "failed" until the user ran
`/mcp` -> Reconnect.

This launcher needs only the standard library, so `uv` can run it as soon as
Python itself is available:

* environment already in sync with uv.lock (every start after the first):
  run the real server in this process's stdio and step aside;
* otherwise: answer `initialize` at once, install the locked libraries in the
  background (`uv sync --frozen`, no time limit), then start the real server,
  replay the handshake to it, tell the client that tools, prompts and
  resources changed, and relay messages both ways from then on.

Until the libraries are in, tool calls get a plain message instead of an
error. Nothing here touches the network itself: only `uv sync` does, against
the sources listed in the plugin README.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO, Callable

HERE = Path(__file__).resolve().parent
LOCK = HERE / "uv.lock"
SERVER = HERE / "run_server.py"
# The environment `uv run --project` created for this process (.venv).
MARKER = Path(sys.prefix) / ".legal-it-synced"

PREPARING = (
    "Legal IT si sta preparando: al primo avvio scarica Python e le librerie "
    "del server (da qualche secondo a un paio di minuti). Gli strumenti "
    "compaiono da soli appena il download finisce: riprova tra poco."
)
FAILED = (
    "Legal IT non è riuscito a installare le sue librerie ({reason}). Controlla "
    "la connessione, poi chiudi e riapri la sessione oppure /mcp -> Reconnect."
)

# Requests answered while the libraries are still being installed.
EMPTY_RESULTS = {
    "ping": {},
    "logging/setLevel": {},
    "tools/list": {"tools": []},
    "prompts/list": {"prompts": []},
    "resources/list": {"resources": []},
    "resources/templates/list": {"resourceTemplates": []},
    "completion/complete": {"completion": {"values": []}},
}
CHANGED = (
    "notifications/tools/list_changed",
    "notifications/prompts/list_changed",
    "notifications/resources/list_changed",
)


def lock_digest() -> str:
    return hashlib.sha256(LOCK.read_bytes()).hexdigest()


def in_sync() -> bool:
    try:
        return MARKER.read_text(encoding="utf-8").strip() == lock_digest()
    except OSError:
        return False


def server_version() -> str:
    text = (HERE / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else "0"


def sync_command() -> list[str]:
    uv = os.environ.get("UV") or shutil.which("uv") or "uv"
    return [uv, "sync", "--frozen", "--python", "3.12", "--project", str(HERE)]


def run_sync() -> str | None:
    """Install the locked libraries. None on success, else a short reason."""
    try:
        done = subprocess.run(sync_command(), stdin=subprocess.DEVNULL,
                              stdout=sys.stderr, stderr=sys.stderr)
    except OSError as exc:
        return str(exc)
    if done.returncode != 0:
        return f"uv sync exit {done.returncode}"
    MARKER.write_text(lock_digest(), encoding="utf-8")
    return None


class Relay:
    """Speaks MCP until the real server is up, then forwards between the two."""

    def __init__(self, stdin: IO[bytes], stdout: IO[bytes],
                 sync: Callable[[], str | None], server_cmd: list[str],
                 on_server_exit: Callable[[int], object] = os._exit) -> None:
        self.stdin = stdin
        self.stdout = stdout
        self.sync = sync
        self.server_cmd = server_cmd
        self.on_server_exit = on_server_exit
        self.state = threading.Lock()  # guards everything below
        self.out = threading.Lock()  # one writer at a time on stdout
        self.child: subprocess.Popen[bytes] | None = None
        self.init_line: bytes | None = None
        self.initialized = False
        self.failure: str | None = None
        self.got_init = threading.Event()

    # --- output -------------------------------------------------------------
    def send(self, message: dict) -> None:
        data = json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
        self.send_raw(data)

    def send_raw(self, data: bytes) -> None:
        with self.out:
            self.stdout.write(data)
            self.stdout.flush()

    # --- before the server is up --------------------------------------------
    def answer_locally(self, line: bytes, message: dict) -> None:
        method = message.get("method")
        request_id = message.get("id")
        if method == "initialize":
            self.init_line = line
            self.got_init.set()
            params = message.get("params") or {}
            self.send({"jsonrpc": "2.0", "id": request_id, "result": {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {"listChanged": True},
                                 "prompts": {"listChanged": True},
                                 "resources": {"listChanged": True}},
                "serverInfo": {"name": "Legal IT", "version": server_version()},
                "instructions": PREPARING,
            }})
            return
        if method == "notifications/initialized":
            self.initialized = True
            return
        if request_id is None:  # any other notification
            return
        text = FAILED.format(reason=self.failure) if self.failure else PREPARING
        if method == "tools/call":
            self.send({"jsonrpc": "2.0", "id": request_id, "result": {
                "content": [{"type": "text", "text": text}], "isError": True}})
        elif method in EMPTY_RESULTS:
            self.send({"jsonrpc": "2.0", "id": request_id,
                       "result": EMPTY_RESULTS[method]})
        else:
            self.send({"jsonrpc": "2.0", "id": request_id,
                       "error": {"code": -32603, "message": text}})

    # --- switching over -----------------------------------------------------
    def start_server(self) -> None:
        """Runs in its own thread: install, start, replay, announce."""
        reason = self.sync()
        if reason is not None:
            with self.state:
                self.failure = reason
            return
        self.got_init.wait()
        with self.state:
            child = subprocess.Popen(self.server_cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=sys.stderr)
            init = json.loads(self.init_line)
            child.stdin.write(self.init_line)
            child.stdin.flush()
            for raw in iter(child.stdout.readline, b""):  # the replayed answer
                try:
                    if json.loads(raw).get("id") == init.get("id"):
                        break
                except ValueError:
                    continue
            if self.initialized:
                child.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                child.stdin.flush()
            self.child = child
            threading.Thread(target=self.pump_server, daemon=True).start()
            for method in CHANGED:
                self.send({"jsonrpc": "2.0", "method": method})

    def pump_server(self) -> None:
        assert self.child is not None and self.child.stdout is not None
        for raw in iter(self.child.stdout.readline, b""):
            self.send_raw(raw)
        # The server ended: so does the session.
        self.on_server_exit(self.child.wait())

    # --- main loop ----------------------------------------------------------
    def run(self) -> int:
        threading.Thread(target=self.start_server, daemon=True).start()
        for line in iter(self.stdin.readline, b""):
            if not line.strip():
                continue
            with self.state:
                if self.child is not None:
                    self.child.stdin.write(line)
                    self.child.stdin.flush()
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict):
                    self.answer_locally(line, message)
        with self.state:
            if self.child is not None:
                self.child.stdin.close()
                return self.child.wait()
        return 0


def main() -> int:
    server = [sys.executable, str(SERVER)]
    if in_sync():
        # Warm start: the real server inherits this process's stdio.
        return subprocess.call(server)
    return Relay(sys.stdin.buffer, sys.stdout.buffer, run_sync, server).run()


if __name__ == "__main__":
    sys.exit(main())
