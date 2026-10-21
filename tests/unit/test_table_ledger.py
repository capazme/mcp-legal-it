"""The runtime ledger: which table a call actually read, observed not derived.

`tests/unit/test_golden_calcoli.py` checks the *declaration* over the wire on the
whole local surface. This file checks the machinery underneath it, where a bug
would be quiet: a wrapper that records outside a call (every answer would claim
every table), one that records nothing (the declaration would silently empty),
an `install` that double-wraps or wraps a scalar, and a middleware that
overwrites the meta FastMCP already set for a tool returning a string.
"""

from __future__ import annotations

import asyncio
import sys
import types

from fastmcp import Client, FastMCP

from mcp_legal_it.lib import _data
from mcp_legal_it.lib._ledger import (
    DATA_WARNINGS_KEY,
    OPENED_TABLES_KEY,
    TableDict,
    TableList,
    apply_table_ledger,
    install,
    opened,
    recording,
)


def test_a_wrapped_table_notes_itself_only_inside_a_call():
    table = TableDict({"civile": {"cognizione": []}}, "contributo_unificato")
    listing = TableList(["commercio"], "preavviso_ccnl")

    # Outside a call: prompts, resources and import-time projections read the
    # same objects, and none of them may claim anything.
    _ = table["civile"], table.get("nope"), list(table), "commercio" in listing
    assert opened() == []

    with recording() as seen:
        _ = table["civile"]
        assert seen == {"contributo_unificato"}
        _ = listing[0]
        assert seen == {"contributo_unificato", "preavviso_ccnl"}

    assert opened() == [], "the recording has to end with its block"
    _ = table["civile"]
    assert opened() == []


def test_the_wrapper_stays_a_dict_and_a_list():
    """Transparency is the whole reason the payload can be wrapped at all."""
    table = TableDict({"a": 1}, "comuni")
    assert isinstance(table, dict)
    assert table == {"a": 1}
    assert dict(table) == {"a": 1}
    assert sorted(table) == ["a"]
    assert json_of(table) == '{"a": 1}'

    listing = TableList([1, 2], "comuni")
    assert isinstance(listing, list)
    assert listing == [1, 2]
    assert listing[1:] == [2]


def json_of(value) -> str:
    import json

    return json.dumps(value)


def test_install_wraps_imported_modules_and_leaves_the_rest_alone():
    module = types.ModuleType("probe_module")
    module._TABLE = {"rows": [1, 2, 3]}
    module._ROWS = [1, 2, 3]
    module._SCALAR = 3
    sys.modules["probe_module"] = module

    wrapped = install(
        {
            "probe_module": {"_TABLE": "comuni", "_ROWS": "festivita", "_SCALAR": "comuni"},
            "never_imported": {"_TABLE": "comuni"},
        }
    )
    # Two containers wrapped; the scalar is skipped (nothing to observe on an
    # int) and the unimported module is not imported to be wrapped.
    assert wrapped == 2
    assert isinstance(module._TABLE, TableDict)
    assert isinstance(module._ROWS, TableList)
    assert module._SCALAR == 3
    assert "never_imported" not in sys.modules

    assert install({"probe_module": {"_TABLE": "comuni"}}) == 0, "double wrap"


def test_the_real_bindings_wrapped_the_real_constants():
    """`mcp_legal_it.server` installs the ledger, so importing it must show up here.

    The install runs at server import for the modules bound by then. One tool
    module (`privacy_gdpr`) imports `mcp_legal_it.server` itself before binding its own
    dicts, so in a process that imports it first those three land after the
    first install -- a wrap-placement order artifact that never changes an
    answer (the tools read the dicts at call time). The check keeps its teeth
    by rerunning the install exactly as the server entrypoint does and failing
    if anything *beyond* that known trio is left out, or if a second pass
    wraps anything at all.
    """
    import mcp_legal_it.server  # noqa: F401  (importing the server is what installs it)
    from mcp_legal_it.lib._ledger import install
    from mcp_legal_it.table_bindings import TABLE_CONSTANTS
    from mcp_legal_it.tools import varie

    late = install(TABLE_CONSTANTS)
    assert late <= 3, (
        "modules mcp_legal_it.server imports directly stopped being wrapped at import: "
        "%d constants now wrap late" % late
    )
    assert isinstance(varie._COMUNI, TableDict), "the server stopped installing the ledger"
    assert "_COMUNI" in TABLE_CONSTANTS["mcp_legal_it.tools.varie"]
    assert install(TABLE_CONSTANTS) == 0, "the constants were already wrapped once"


def test_every_binding_key_names_a_module_that_imports():
    """A stale module key in the generated bindings drops the ledger silently.

    `install` skips a module it cannot find in `sys.modules` on purpose, so a
    key that no longer matches an import path (a package rename that skipped
    `audit_tool_annotations.py --write`) wraps nothing and fails nothing: every
    result just loses `opened_tables` and its `dati_applicati`. Here each key has
    to import under its own name, and each constant it names has to come out of
    the server import wrapped.
    """
    import importlib

    import mcp_legal_it.server  # noqa: F401  (importing the server is what installs it)
    from mcp_legal_it.table_bindings import TABLE_CONSTANTS

    install(TABLE_CONSTANTS)  # the late trio documented in the test above
    assert TABLE_CONSTANTS, "the generated bindings are empty"
    for module_name, constants in TABLE_CONSTANTS.items():
        assert module_name.startswith("mcp_legal_it."), (
            "%s is outside the package: regenerate the bindings" % module_name
        )
        module = importlib.import_module(module_name)
        for name in constants:
            assert hasattr(module, name), "%s.%s no longer exists" % (module_name, name)
            value = getattr(module, name)
            if isinstance(value, (dict, list)):
                assert isinstance(value, (TableDict, TableList)), (
                    "%s.%s was never wrapped by the ledger" % (module_name, name)
                )


def test_every_tool_named_by_the_bindings_is_registered():
    """The tool-keyed halves of the bindings name tools the server really lists."""
    # TOOL_ALTERNATIVES maps a tool to a parameter name: only its keys are tools.
    from mcp_legal_it.server import mcp
    from mcp_legal_it.source_bindings import TOOL_SOURCES
    from mcp_legal_it.table_bindings import TOOL_ALTERNATIVES, TOOL_TABLES

    registered = {tool.name for tool in asyncio.run(mcp.list_tools())}
    for label, keys in (
        ("TOOL_TABLES", set(TOOL_TABLES)),
        ("TOOL_ALTERNATIVES", set(TOOL_ALTERNATIVES)),
        ("TOOL_SOURCES", set(TOOL_SOURCES)),
    ):
        assert not keys - registered, "%s names unknown tools: %s" % (label, sorted(keys - registered))


def test_the_middleware_flags_the_vintage_of_the_tables_the_answer_rests_on():
    """Which tables the warning is about: observed when possible, declared when blind.

    Three cases, and the third is the one that is easy to get wrong. A call that
    read an unverified table is flagged for it; a call the ledger could not see
    (a table behind a scalar computed at import) is flagged from the tool's
    declared tables, because silence there would report a clean answer; and a
    tool that rests on no table gets no key at all, so the field means something
    whenever it appears.
    """
    server = FastMCP("ledger-vintage-probe")

    @server.tool()
    def reads_an_unverified_table() -> dict:
        return {"valore": _data.load("codici_ateco")["voci"]}

    @server.tool()
    def reads_nothing_but_declares_one() -> dict:
        return {"valore": 1.0}

    @server.tool()
    def rests_on_nothing() -> dict:
        return {"valore": 2.0}

    assert apply_table_ledger(
        server,
        {},
        {"reads_nothing_but_declares_one": ("codici_ateco",)},
    ) == 0

    async def run():
        async with Client(server) as client:
            return {
                name: await client.call_tool(name, {})
                for name in (
                    "reads_an_unverified_table",
                    "reads_nothing_but_declares_one",
                    "rests_on_nothing",
                )
            }

    results = asyncio.run(run())
    observed = results["reads_an_unverified_table"].meta[DATA_WARNINGS_KEY]
    assert [entry["tabella"] for entry in observed] == ["codici_ateco"]
    assert observed[0]["stato"] == "non_verificata"
    assert results["reads_an_unverified_table"].meta[OPENED_TABLES_KEY] == ["codici_ateco"]

    blind = results["reads_nothing_but_declares_one"].meta or {}
    assert OPENED_TABLES_KEY not in blind, "nothing was observed, so nothing is claimed"
    assert [entry["tabella"] for entry in blind[DATA_WARNINGS_KEY]] == [
        "codici_ateco"
    ], "the declaration is what the warning falls back to when the ledger is blind"

    assert DATA_WARNINGS_KEY not in (results["rests_on_nothing"].meta or {}), (
        "an answer that rests on no table must not carry an empty warning list"
    )


def test_the_middleware_declares_only_what_the_call_read():
    server = FastMCP("ledger-probe")
    tables = {"tassi_legali": TableDict({"2024": 2.5}, "tassi_legali")}

    @server.tool()
    def reads_a_table() -> dict:
        return {"valore": tables["tassi_legali"]["2024"]}

    @server.tool()
    def reads_nothing() -> dict:
        return {"valore": 1.0}

    @server.tool()
    def returns_a_string() -> str:
        _ = tables["tassi_legali"]["2024"]
        return "risposta"

    assert apply_table_ledger(server, {}) == 0

    async def run():
        async with Client(server) as client:
            return {
                name: await client.call_tool(name, {})
                for name in ("reads_a_table", "reads_nothing", "returns_a_string")
            }

    results = asyncio.run(run())
    assert results["reads_a_table"].meta[OPENED_TABLES_KEY] == ["tassi_legali"]
    assert OPENED_TABLES_KEY not in (results["reads_nothing"].meta or {}), (
        "a pure algorithm must declare nothing: an empty list would look like a "
        "declaration nobody can tell from a missing one"
    )
    declared = results["returns_a_string"].meta
    assert declared[OPENED_TABLES_KEY] == ["tassi_legali"]
    assert declared.get("fastmcp", {}).get("wrap_result") is True, (
        "the ledger overwrote the meta FastMCP had already set"
    )
