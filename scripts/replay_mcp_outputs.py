#!/usr/bin/env python3
"""Prove that a refactor leaves the MCP tools' answers byte-identical.

Records real HTTP exchanges once, then replays them offline against two
checkouts and compares every tool answer (text, error flag and ``_meta``),
taken through the FastMCP in-memory client.

    # 1. once, with network: record the tape on the BASE checkout
    git worktree add --detach /tmp/base origin/develop
    python scripts/replay_mcp_outputs.py record --checkout /tmp/base
    git worktree remove /tmp/base

    # 2. offline: replay against the same ref and the working tree, and compare
    python scripts/replay_mcp_outputs.py compare --base origin/develop

The tape (default ``.replay-tapes/mcp-calls.json.gz``, ``--tape`` to move it)
is rebuilt the same way whenever it is missing or stale: record it again on
the base ref before the refactor starts. Record on the base, not on the
branch, so the tape holds what the code before the change asked for.

NEVER COMMIT THE TAPE, not even a reduced one. It holds what the sources
served: Italgiure decisions and Brocardi pages, whose terms limit reuse, whole
Akoma Ntoso acts and the Constitutional Court's open-data bundles (hundreds of
MB). ``.replay-tapes/`` and ``*.tape.json.gz`` are in ``.gitignore``.

Replays pin the clock (``LEGAL_NOW``), turn the disk caches off
(``LEGAL_CACHE=off``) and fix ``PYTHONHASHSEED``, so two replays of one
checkout are identical. Every ``httpx.AsyncClient`` the process creates gets a
recording or replaying transport keyed by method, URL and body hash; repeated
identical requests are served in recorded order. A request missing from the
tape fails like a network error: if a branch adds requests, the answers differ
and the comparison says so.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
#: Where the tape lives unless --tape says otherwise (ignored by git: never commit it).
DEFAULT_TAPE = REPO / ".replay-tapes" / "mcp-calls.json.gz"

#: The calls replayed: every norm and case-law tool family, with error paths.
CALLS: list[tuple[str, dict]] = [
    ("cite_law", {"reference": "art. 2043 c.c."}),
    ("cite_law", {"reference": "art. 2043 c.c.", "formato": "json"}),
    ("cite_law", {"reference": "art. 2043 c.c.", "include_annotations": True}),
    ("cite_law", {"reference": "art. 6 GDPR"}),
    ("cite_law", {"reference": "art. 6 GDPR", "formato": "json"}),
    ("cite_law", {"reference": "art. 18 Statuto dei lavoratori", "formato": "json"}),
    ("cite_law", {"reference": "art. 99999 c.c.", "formato": "json"}),
    ("cite_law", {"reference": "art. 5 legge inventata 1/1900"}),
    ("cite_law", {"reference": "art. 13 D.Lgs. 196/2003", "formato": "json"}),
    ("cite_law", {"reference": "art. 1 L. 241/1990"}),
    ("fetch_law_article", {"act_type": "codice penale", "article": "575"}),
    ("fetch_law_annotations", {"act_type": "codice civile", "article": "1176"}),
    ("cerca_brocardi", {"reference": "art. 2043 c.c."}),
    ("fetch_act_index", {"reference": "D.Lgs. 231/2001"}),
    ("fetch_full_act", {"reference": "legge 20 maggio 1970, n. 300"}),
    ("leggi_sentenza", {"numero": 12345, "anno": 2023}),
    ("leggi_sentenza", {"numero": 1, "anno": 2024, "archivio": "civile"}),
    ("cerca_giurisprudenza", {"query": "danno da perdita di chance", "max_risultati": 3}),
    ("cerca_giurisprudenza", {"query": "usura sopravvenuta", "archivio": "civile", "anno_da": 2023}),
    ("giurisprudenza_su_norma", {"riferimento": "art. 2043 c.c.", "max_risultati": 3}),
    ("giurisprudenza_articolo", {"riferimento": "art. 2051 c.c."}),
    ("ultime_pronunce", {"materia": "lavoro"}),
    ("cerca_pronuncia_costituzionale", {"query": "fine vita", "anno_da": 2019, "anno_a": 2020}),
    ("leggi_pronuncia_costituzionale", {"numero": 242, "anno": 2019}),
    ("pronunce_cost_su_norma", {"riferimento": "art. 580 c.p.", "anno_da": 2019, "anno_a": 2020}),
    ("cerca_giurisprudenza_tributaria", {"query": "IVA soggettività passiva", "max_risultati": 3}),
    ("cerca_giurisprudenza_amministrativa", {"query": "esclusione appalto", "sede": "CDS"}),
    ("cerca_giurisprudenza_amministrativa", {"query": "accesso agli atti"}),
    ("ultime_sentenze_tributarie", {}),
    ("ultime_sentenze_cgue", {}),
    ("leggi_sentenza_cgue", {"cellar_uri": "http://publications.europa.eu/resource/celex/62019CJ0311"}),
    ("cerca_giurisprudenza_cgue", {"query": "trasferimento dati personali", "anno_da": "2020"}),
    ("giurisprudenza_cgue_su_norma", {"riferimento": "art. 82 GDPR"}),
    ("cerca_giurisprudenza_unificata", {"query": "responsabilità medica", "max_risultati": 2}),
    ("verifica_citazioni", {"citazioni": "art. 2043 c.c.; Cass. n. 12345/2023; art. 99999 c.c."}),
    ("orientamento_su_norma", {"riferimento": "art. 2051 c.c."}),
]

_ENV = {"LEGAL_NOW": "2026-10-21T12:00:00", "LEGAL_CACHE": "off", "PYTHONHASHSEED": "0"}


# ---------------------------------------------------------------------------
# Worker: runs inside a process whose PYTHONPATH points at one checkout
# ---------------------------------------------------------------------------


def install_tape_transport(mode: str, tape_path: str) -> dict[str, list[dict]]:
    """Route every ``httpx.AsyncClient`` of this process through the tape.

    ``mode`` is ``record`` (real network, every exchange appended to the returned
    dict: save it with ``save_tape``) or ``replay`` (served from ``tape_path``, a
    request missing from it fails like a network error). Also used by
    ``scripts/token_report.py``.
    """
    import httpx

    tape: dict[str, list[dict]] = {}
    if mode == "replay":
        with gzip.open(tape_path, "rt", encoding="utf-8") as fh:
            tape = json.load(fh)
    cursor: dict[str, int] = {}

    def key(request: httpx.Request) -> str:
        return f"{request.method} {request.url} {hashlib.sha256(request.content or b'').hexdigest()[:16]}"

    class Recorder(httpx.AsyncBaseTransport):
        def __init__(self, verify=True):
            self._inner = httpx.AsyncHTTPTransport(verify=verify)

        async def handle_async_request(self, request):
            await request.aread()
            resp = await self._inner.handle_async_request(request)
            content = await resp.aread()
            headers = [(k, v) for k, v in resp.headers.items()
                       if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")]
            tape.setdefault(key(request), []).append(
                {"status": resp.status_code, "headers": headers, "body": base64.b64encode(content).decode()})
            return httpx.Response(resp.status_code, headers=headers, content=content, request=request)

    class Replayer(httpx.AsyncBaseTransport):
        def __init__(self, verify=True):
            pass

        async def handle_async_request(self, request):
            await request.aread()
            k = key(request)
            entries = tape.get(k)
            if not entries:
                raise httpx.ConnectError(f"not on tape: {k}", request=request)
            i = cursor.get(k, 0)
            cursor[k] = i + 1
            e = entries[min(i, len(entries) - 1)]
            return httpx.Response(e["status"], headers=e["headers"], content=base64.b64decode(e["body"]),
                                  request=request)

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        verify = kwargs.pop("verify", True)
        kwargs.pop("transport", None)
        kwargs["transport"] = (Recorder if mode == "record" else Replayer)(verify=verify)
        original_init(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = patched_init
    return tape


def save_tape(tape: dict[str, list[dict]], tape_path: str) -> None:
    with gzip.open(tape_path, "wt", encoding="utf-8") as fh:
        json.dump(tape, fh)


def _worker(mode: str, tape_path: str, out_path: str) -> None:
    tape = install_tape_transport(mode, tape_path)

    async def run() -> list[dict]:
        from fastmcp import Client
        from mcp_legal_it.server import mcp

        results = []
        async with Client(mcp) as client:
            for name, args in CALLS:
                try:
                    r = await client.call_tool(name, args, raise_on_error=False)
                    results.append({"tool": name, "args": args, "is_error": r.is_error,
                                     "text": "\n".join(getattr(c, "text", "") for c in r.content),
                                     "meta": getattr(r, "meta", None)})
                except Exception as exc:  # noqa: BLE001 - recorded as part of the answer
                    results.append({"tool": name, "args": args, "exception": repr(exc)})
        return results

    results = asyncio.run(run())
    Path(out_path).write_text(json.dumps(results, ensure_ascii=False, indent=1, sort_keys=True, default=str),
                              encoding="utf-8")
    if mode == "record":
        save_tape(tape, tape_path)
    print(f"{mode}: {len(results)} calls, {len(tape)} distinct requests", file=sys.stderr)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _run_worker(checkout: Path, mode: str, tape: Path, out: Path) -> None:
    package = checkout / "plugin" / "server"
    if not (package / "mcp_legal_it").is_dir():
        sys.exit(f"not a checkout of mcp-legal-it: {checkout}")
    env = {**os.environ, **_ENV, "PYTHONPATH": str(package)}
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "_worker", mode, str(tape), str(out)],
                   env=env, check=True)


def _compare(base_out: Path, head_out: Path) -> int:
    a = json.loads(base_out.read_text(encoding="utf-8"))
    b = json.loads(head_out.read_text(encoding="utf-8"))
    if len(a) != len(b):
        print(f"different number of calls: {len(a)} vs {len(b)}")
        return 1
    text = [f"{x['tool']} {x['args']}" for x, y in zip(a, b)
            if (x.get("text"), x.get("is_error"), x.get("exception")) != (y.get("text"), y.get("is_error"), y.get("exception"))]
    meta = [f"{x['tool']} {x['args']}" for x, y in zip(a, b) if x.get("meta") != y.get("meta")]
    print(f"{len(a)} calls | text/is_error differ: {text or 'none'} | _meta differ: {meta or 'none'}")
    return 1 if text else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="record a tape (network) against a checkout")
    rec.add_argument("--tape", type=Path, default=DEFAULT_TAPE)
    rec.add_argument("--checkout", type=Path, default=REPO)
    rec.add_argument("--out", type=Path, help="also keep the recorded answers here")
    rep = sub.add_parser("replay", help="replay a tape offline against a checkout")
    rep.add_argument("--tape", type=Path, default=DEFAULT_TAPE)
    rep.add_argument("--checkout", type=Path, default=REPO)
    rep.add_argument("--out", type=Path, required=True)
    cmp_ = sub.add_parser("compare", help="replay a tape against a git ref and a checkout, and compare")
    cmp_.add_argument("--tape", type=Path, default=DEFAULT_TAPE)
    cmp_.add_argument("--base", required=True, help="git ref of the base (e.g. origin/develop)")
    cmp_.add_argument("--head", type=Path, default=REPO, help="checkout to compare (default: this one)")
    w = sub.add_parser("_worker")
    w.add_argument("mode")
    w.add_argument("tape")
    w.add_argument("out")
    args = parser.parse_args()

    if args.command == "_worker":
        _worker(args.mode, args.tape, args.out)
        return 0
    if args.command != "record" and not args.tape.expanduser().exists():
        sys.exit(f"no tape at {args.tape}: record one on the base ref first (see the module docstring)")
    if args.command == "record":
        args.tape.expanduser().parent.mkdir(parents=True, exist_ok=True)
        out = args.out or Path(tempfile.mkdtemp()) / "recorded.json"
        _run_worker(args.checkout, "record", args.tape.expanduser(), out)
        return 0
    if args.command == "replay":
        _run_worker(args.checkout, "replay", args.tape.expanduser(), args.out)
        return 0
    work = Path(tempfile.mkdtemp(prefix="replay-mcp-"))
    base = work / "base"
    subprocess.run(["git", "-C", str(REPO), "worktree", "add", "--detach", str(base), args.base], check=True,
                   capture_output=True)
    try:
        _run_worker(base, "replay", args.tape.expanduser(), work / "base.json")
        _run_worker(args.head, "replay", args.tape.expanduser(), work / "head.json")
        return _compare(work / "base.json", work / "head.json")
    finally:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(base)], check=False,
                       capture_output=True)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
