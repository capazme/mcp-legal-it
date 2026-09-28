"""stato_server: the self-report that tells the caller WHAT it is talking to.

Scopus servers answer `get_quota_status` / `check_capabilities`; this server now
answers with its own identity: package version, active surface (after the
`LEGAL_PROFILE` transform), pinned clock, cache switch, hostname. The counts are
derived from the audited annotation policy — the same numbers the CI enforces —
so the tool cannot drift from the audit into a second handwritten 227.
"""

import asyncio
import platform

from src.cli_version import package_version
from src.lib import _clock
from src.server import mcp
from src.tool_annotations import READ_ONLY, WRITES_FILES
from src.tools.varie import stato_server


def test_stato_reports_version_surface_and_flags(monkeypatch):
    monkeypatch.delenv("LEGAL_PROFILE", raising=False)
    monkeypatch.delenv("LEGAL_TODAY", raising=False)
    monkeypatch.delenv("LEGAL_NOW", raising=False)
    monkeypatch.setenv("LEGAL_CACHE", "off")
    monkeypatch.delenv("MCP_CACHE_DIR", raising=False)

    r = asyncio.run(stato_server())

    assert r["server"] == "mcp-legal-it"
    assert r["versione"] == package_version()
    # The active surface is whatever the server would actually list right now:
    # same number a Client would see, profile transform included.
    assert r["tools_attivi"] == len(asyncio.run(mcp.list_tools()))
    assert r["profilo"] == "full"
    assert r["orologio"]["oggi"] == _clock.today().isoformat()
    assert r["orologio"]["pinnato"] is False
    assert r["orologio"]["override"] is None
    assert r["cache"]["abilitata"] is False
    assert r["cache"]["sovrascritto"] is False
    assert r["macchina"] == platform.node()
    assert isinstance(r["fastmcp"], str) and r["fastmcp"]


def test_stato_reports_pinned_clock_and_cache_dir(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2030-01-31")
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    monkeypatch.setenv("MCP_CACHE_DIR", "/tmp/stato-cache-test")

    r = asyncio.run(stato_server())

    assert r["orologio"]["oggi"] == "2030-01-31"
    assert r["orologio"]["pinnato"] is True
    assert r["orologio"]["override"] == "2030-01-31"
    assert r["cache"]["abilitata"] is True
    assert r["cache"]["percorso"] == "/tmp/stato-cache-test"
    assert r["cache"]["sovrascritto"] is True


def test_stato_counts_come_from_the_annotation_policy():
    """The declared total is the audited policy, not a second handwritten number."""
    r = asyncio.run(stato_server())

    assert r["tools_totali"] == len(READ_ONLY | WRITES_FILES)
    # The diagnostics tool itself is audited (read-only, local-only): the policy
    # --write run picked it up, otherwise this assertion and policy-sync fail
    # together and the drift is visible instead of silent.
    assert "stato_server" in READ_ONLY
