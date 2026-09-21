"""Per-call provenance for online sources: observed, declared, and never noisy.

`scripts/audit_tool_annotations.py` derives the committed policy
(`source_bindings.py`) from the call graph; this file checks the runtime half,
where a bug would be quiet: a middleware that stamps an empty block on an
offline answer (the field would mean nothing), a record that carries the
caller's search terms in a URL (a provenance line must not leak them), a
consulted source the policy does not list (the walk missed a fetcher), and a
tool name the committed bindings no longer know.
"""

from __future__ import annotations

import asyncio

from fastmcp import Client, FastMCP

from src.lib import _sources
from src.lib._ledger import CONSULTED_SOURCES_KEY, apply_table_ledger


def probe(tool_sources: dict[str, tuple[str, ...]] | None = None) -> FastMCP:
    server = FastMCP("sources-probe")

    @server.tool()
    def consults_a_source() -> dict:
        _sources.note(
            "corte_cost",
            "https://www.cortecostituzionale.it/actionSchedaPronuncia.do"
            "?anno=2024&numero=1&query=segreta",
        )
        return {"esito": "ok"}

    @server.tool()
    def consults_two_sources() -> dict:
        _sources.note("brocardi", "https://www.brocardi.it/articolo-2/")
        _sources.note("brocardi", "https://www.brocardi.it/articolo-2/")
        _sources.note("cgue", None)
        return {"esito": "ok"}

    @server.tool()
    def goes_nowhere() -> dict:
        return {"esito": "locale"}

    apply_table_ledger(server, {}, {}, tool_sources=tool_sources)
    return server


def call(server: FastMCP, names: list[str]) -> dict:
    async def run():
        async with Client(server) as client:
            return {name: await client.call_tool(name, {}) for name in names}

    return asyncio.run(run())


def test_the_middleware_stamps_only_answers_that_consulted_a_source():
    results = call(probe(), ["consults_a_source", "goes_nowhere"])

    blocco = results["consults_a_source"].meta[CONSULTED_SOURCES_KEY]
    assert len(blocco["fonti"]) == 1, "one entry for one source"
    entry = blocco["fonti"][0]
    assert entry["fonte"] == "corte_cost"
    assert "?" not in entry["url"] and "segreta" not in entry["url"], (
        "the provenance line keeps the scheme://host//path prefix only: "
        "no query string, no caller's search terms"
    )
    assert entry["url"].startswith("https://")
    assert blocco["consultate_al"], "the stamp names the moment of the consult"

    offline = results["goes_nowhere"].meta or {}
    assert CONSULTED_SOURCES_KEY not in offline, (
        "an answer that consulted nothing must not carry an empty block"
    )


def test_two_fetches_of_one_source_are_one_line_and_a_fetch_without_url_is_kept():
    results = call(probe(), ["consults_two_sources"])

    fonti = results["consults_two_sources"].meta[CONSULTED_SOURCES_KEY]["fonti"]
    assert [f["fonte"] for f in fonti] == ["brocardi", "cgue"]
    brocardi = fonti[0]
    assert brocardi["url"] == "https://www.brocardi.it/articolo-2/", (
        "the same source fetched twice is deduplicated to one line"
    )
    assert fonti[1]["url"] == "", "a consult without a URL is still a consult"


def test_a_source_outside_the_policy_is_flagged_as_undeclared():
    """The middleware must say so, not silently extend the policy."""
    results = call(probe({"consults_a_source": ("brocardi",)}), ["consults_a_source"])

    blocco = results["consults_a_source"].meta[CONSULTED_SOURCES_KEY]
    assert blocco["non_dichiarate"] == ["corte_cost"], (
        "the observation saw a fetch the committed policy does not list: "
        "the walk missed a fetcher, and the answer says so"
    )
    assert blocco["fonti"], "the observation is still reported"


def test_every_tool_named_by_the_committed_bindings_exists_on_the_server():
    """A stale binding would silently stop matching any middleware pass."""
    from src.server import mcp  # noqa: F401  (the real server registers the tools)
    from src.source_bindings import TOOL_SOURCES

    assert TOOL_SOURCES, "the committed policy is not empty"

    async def names():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            return {tool.name for tool in tools}

    registered = asyncio.run(names())
    sconosciuti = sorted(set(TOOL_SOURCES) - registered)
    assert not sconosciuti, (
        "source_bindings.py names tools the server no longer registers: %s" % sconosciuti
    )


def test_note_outside_a_call_is_a_noop():
    _sources.note("corte_cost", "https://example.com/x")
    assert _sources.consulted() == []
    with _sources.recording() as seen:
        _sources.note("corte_cost", "https://example.com/x")
        assert seen == {("corte_cost", "https://example.com/x")}
        assert [f["fonte"] for f in _sources.consulted()] == ["corte_cost"]
    assert _sources.consulted() == [], "the recording ends with its block"
