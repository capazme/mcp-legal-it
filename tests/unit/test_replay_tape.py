"""``scripts/replay_mcp_outputs.py``: what the recorder keeps, and what it hands the live client."""

import gzip
import importlib.util
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
SESSIONE = "JSESSIONID=abc123"


def _replay_module():
    spec = importlib.util.spec_from_file_location("replay_mcp_outputs", REPO / "scripts" / "replay_mcp_outputs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sito(request: httpx.Request) -> httpx.Response:
    """A source with a session, like Normattiva: the second page needs the first page's cookie."""
    if request.url.path == "/pagina":
        return httpx.Response(200, text="pagina", headers={"set-cookie": f"{SESSIONE}; Path=/"})
    if request.url.path == "/tabella":
        if SESSIONE in request.headers.get("cookie", ""):
            return httpx.Response(200, text="tabella")
        return httpx.Response(200, text="pagina di sessione")
    return httpx.Response(404)


async def test_the_live_client_keeps_its_session_and_the_tape_keeps_no_cookie(tmp_path, monkeypatch):
    class Rete(httpx.MockTransport):
        def __init__(self, verify=True):
            super().__init__(_sito)

    replay = _replay_module()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", Rete)
    original = httpx.AsyncClient.__init__
    try:
        tape = replay.install_tape_transport("record", str(tmp_path / "unused"))
        async with httpx.AsyncClient(base_url="https://fonte.example") as client:
            await client.get("/pagina")
            tabella = (await client.get("/tabella")).text
    finally:
        httpx.AsyncClient.__init__ = original
    assert tabella == "tabella"  # the session reached the second request
    path = tmp_path / "tape.json.gz"
    replay.save_tape(tape, str(path))
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        raw = fh.read().lower()
    assert "set-cookie" not in raw and "abc123" not in raw
