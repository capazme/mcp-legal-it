"""crea_server: a FastMCP server with only the selected tools, the stock one untouched.

A host that mounts mcp-legal-it into its own surface (design spec §4.3) must see
only what it asked for: a tool left out is absent from `list_tools`, not listed
and then refused. The tools it keeps must be the stock tools, with their names,
schemas, annotations and `_meta`.
"""
from __future__ import annotations

import asyncio

import pytest
from fastmcp import Client, FastMCP

from mcp_legal_it.server import crea_server, mcp
from mcp_legal_it.tool_taxonomy import KINDS


async def _surface(server: FastMCP) -> dict:
    async with Client(server) as client:
        tools = await client.list_tools()
        return {
            "tools": {t.name: t for t in tools},
            "prompts": len(await client.list_prompts()),
            "resources": len(await client.list_resources()),
        }


def surface(server: FastMCP) -> dict:
    return asyncio.run(_surface(server))


STOCK = surface(mcp)


def _kind(tool) -> str:
    tags = set((tool.meta or {}).get("fastmcp", {}).get("tags", []))
    (kind,) = tags & set(KINDS)
    return kind


def test_without_filters_it_is_the_stock_surface():
    built = surface(crea_server())
    assert set(built["tools"]) == set(STOCK["tools"])
    assert len(built["tools"]) == 228
    assert built["prompts"] == STOCK["prompts"] == 23
    assert built["resources"] == STOCK["resources"] == 15


def test_a_sources_subset_lists_no_calculator():
    built = surface(crea_server(include_tags={"normativa", "giurisprudenza"}))
    kinds = {_kind(t) for t in built["tools"].values()}
    assert kinds == {"normativa", "giurisprudenza"}
    assert {"cite_law", "leggi_sentenza", "cerca_giurisprudenza_cgue", "leggi_provvedimento_amm"} <= set(built["tools"])
    assert not {"interessi_legali", "contributo_unificato", "cerca_marchi", "stato_server"} & set(built["tools"])


def test_excluded_tools_are_absent_and_unknown_when_called():
    server = crea_server(include_tags={"normativa"}, exclude_tags={"parlamento"})
    built = surface(server)
    assert "cite_law" in built["tools"]
    assert not {"cerca_ddl", "iter_ddl", "ddl_su_norma", "interessi_legali"} & set(built["tools"])

    async def call():
        async with Client(server) as client:
            return await client.call_tool("interessi_legali", {"capitale": 1000, "data_inizio": "2020-01-01",
                                                               "data_fine": "2021-01-01"}, raise_on_error=False)

    result = asyncio.run(call())
    assert result.is_error
    assert "Unknown tool" in result.content[0].text


def test_kept_tools_are_the_stock_tools():
    built = surface(crea_server(include_tags={"interessi"}))
    for name, tool in built["tools"].items():
        # Name, description, schemas, annotations and listing _meta, field by field.
        assert tool.model_dump() == STOCK["tools"][name].model_dump(), name


def test_a_call_carries_the_ledger_meta():
    async def call():
        async with Client(crea_server(include_tags={"interessi"})) as client:
            return await client.call_tool("interessi_legali", {"capitale": 1000, "data_inizio": "2020-01-01",
                                                               "data_fine": "2021-01-01"})

    result = asyncio.run(call())
    assert "mcp-legal-it/opened_tables" in (result.meta or {})


def test_the_stock_server_is_not_changed():
    crea_server(include_tags={"calcolo"}, exclude_tags={"brocardi"}, brocardi=False, prompts=False)
    assert set(surface(mcp)["tools"]) == set(STOCK["tools"])


def test_two_subsets_coexist():
    a = surface(crea_server(include_tags={"penale"}))
    b = surface(crea_server(include_tags={"lavoro"}))
    assert set(a["tools"]) == {n for n, t in STOCK["tools"].items() if "penale" in t.meta["fastmcp"]["tags"]}
    assert set(b["tools"]) == {n for n, t in STOCK["tools"].items() if "lavoro" in t.meta["fastmcp"]["tags"]}


def test_prompts_and_resources_can_be_left_out():
    kept = surface(crea_server(include_tags={"calcolo"}))
    assert kept["prompts"] == 23 and kept["resources"] == 15
    dropped = surface(crea_server(include_tags={"calcolo"}, prompts=False))
    assert dropped["prompts"] == 0 and dropped["resources"] == 0
    assert len(dropped["tools"]) == 141


def test_excluding_brocardi_differs_from_switching_it_off():
    excluded = set(surface(crea_server(exclude_tags={"brocardi"}))["tools"])
    off = set(surface(crea_server(brocardi=False))["tools"])
    assert "cite_law" not in excluded and "cite_law" in off
    assert len(excluded) == 223 and len(off) == 226


def test_the_name_is_reported():
    server = crea_server(name="Fonti")
    assert server.name == "Fonti"


@pytest.mark.parametrize("kwargs,error", [
    ({"include_tags": {"normatica"}}, ValueError),
    ({"exclude_tags": {"giurisprudenza", "tar"}}, ValueError),
    ({"include_tags": "normativa"}, TypeError),
])
def test_bad_tags_are_refused(kwargs, error):
    with pytest.raises(error):
        crea_server(**kwargs)
