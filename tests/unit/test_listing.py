"""The `tools/list` shape (mcp_legal_it/_listing.py): fewer characters, same contract."""

import asyncio
import json

import pytest
from fastmcp import Client

from mcp_legal_it import _listing
from mcp_legal_it._listing import compact_schema, tidy_description
from mcp_legal_it.server import crea_server, mcp


def _wire(obj) -> dict:
    return obj.model_dump(mode="json", by_alias=True, exclude_none=True)


async def _listed(server) -> list[dict]:
    async with Client(server) as client:
        return [_wire(t) for t in await client.list_tools()]


# ---------------------------------------------------------------------------
# the transforms
# ---------------------------------------------------------------------------


def test_optional_parameter_becomes_a_nullable_type():
    prop = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None, "description": "d"}
    assert compact_schema(prop) == {"type": ["string", "null"], "default": None, "description": "d"}


def test_optional_list_keeps_its_items():
    prop = {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": None}
    assert compact_schema(prop) == {"items": {"type": "string"}, "type": ["array", "null"], "default": None}


def test_nested_optionals_collapse_too():
    schema = {
        "type": "object",
        "properties": {
            "righe": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"nota": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}},
                },
            },
        },
    }
    assert compact_schema(schema) == {
        "type": "object",
        "properties": {
            "righe": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"nota": {"type": ["string", "null"], "default": None}},
                },
            },
        },
    }


def test_a_branch_key_that_clashes_stops_the_merge():
    # The branch's own description would be overwritten by the property's: keep the union.
    prop = {"anyOf": [{"type": "string", "description": "branch"}, {"type": "null"}],
            "default": None, "description": "property"}
    assert compact_schema(prop) == prop


def test_a_ref_branch_stays_a_union():
    prop = {"anyOf": [{"$ref": "#/$defs/Voce"}, {"type": "null"}], "default": None}
    assert compact_schema(prop) == prop


@pytest.mark.parametrize("branches", [
    [{"type": "null"}, {"type": "null"}],
    [{"type": "null"}, "null"],
    [{"type": ["string", "integer"]}, {"type": "null"}],
])
def test_odd_unions_never_break_the_listing(branches):
    prop = {"anyOf": branches, "default": None}
    assert compact_schema(prop) == prop


@pytest.mark.parametrize("prop", [
    # a real default: null is a value the client may want to send, keep the union
    {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": 5},
    # no default: the parameter is required and null is one of its values
    {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    # a union of two real types
    {"anyOf": [{"type": "integer"}, {"type": "string"}], "default": None},
    # three branches
    {"anyOf": [{"type": "integer"}, {"type": "string"}, {"type": "null"}], "default": None},
])
def test_other_unions_are_kept(prop):
    assert compact_schema(prop) == prop


def test_additional_properties_false_goes_true_stays():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"m": {"type": "object", "additionalProperties": True}},
    }
    assert compact_schema(schema) == {
        "type": "object",
        "properties": {"m": {"type": "object", "additionalProperties": True}},
    }


def test_description_loses_indentation_not_words_or_breaks():
    text = "Prima riga\n    seconda riga  con  spazi\n\n\tterza"
    assert tidy_description(text) == "Prima riga\nseconda riga  con  spazi\n\nterza"
    assert tidy_description("") == ""
    assert tidy_description(None) is None


# ---------------------------------------------------------------------------
# the listing
# ---------------------------------------------------------------------------


def test_tools_are_listed_by_name():
    names = [t["name"] for t in asyncio.run(_listed(mcp))]
    assert names == sorted(names)
    assert len(names) == len(set(names)) >= 231


def test_subset_server_is_listed_by_name_and_compact():
    tools = asyncio.run(_listed(crea_server(include_tags={"normativa", "giurisprudenza"})))
    names = [t["name"] for t in tools]
    assert names == sorted(names) and names
    dumped = json.dumps([t["inputSchema"] for t in tools])
    assert '"additionalProperties": false' not in dumped
    assert '{"type": "null"}' not in dumped


def test_listing_is_the_registered_tools_transformed():
    """Every published tool is its registered self through the transforms, nothing else."""

    async def registered():
        return {t.name: t for t in await mcp.local_provider.list_tools()}

    stock = asyncio.run(registered())
    for tool in asyncio.run(_listed(mcp)):
        own = stock[tool["name"]]
        assert tool["inputSchema"] == _listing._tidy_properties(compact_schema(own.parameters))
        assert tool.get("description") == tidy_description(own.description)
        # The words are the registered ones: only leading blanks of a line went.
        assert tool.get("description", "").split() == (own.description or "").split()


def test_no_optional_union_or_closed_schema_left():
    dumped = json.dumps([t["inputSchema"] for t in asyncio.run(_listed(mcp))])
    assert '{"type": "null"}' not in dumped
    assert '"additionalProperties": false' not in dumped


def test_listing_leaves_the_registered_tools_alone():
    async def registered():
        return {t.name: t.parameters for t in await mcp.local_provider.list_tools()}

    before = json.dumps(asyncio.run(registered()), sort_keys=True)
    asyncio.run(_listed(mcp))
    assert json.dumps(asyncio.run(registered()), sort_keys=True) == before


@pytest.mark.asyncio
async def test_unknown_argument_is_still_refused_by_the_server():
    async with Client(mcp) as client:
        result = _wire(await client.call_tool_mcp("cite_law", {"reference": "art. 1 c.c.", "pippo": 1}))
    assert result["isError"] is True
    assert "Unexpected keyword argument" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_optional_parameter_still_takes_null_and_absence():
    # accetta_precisione is published as {"type": ["string", "null"], "default": null}: the
    # server still takes an explicit null, and answers as if it were left out.
    args = {"capitale": 1000, "data_inizio": "2020-01-01", "data_fine": "2020-12-31"}
    async with Client(mcp) as client:
        tools = {t.name: _wire(t) for t in await client.list_tools()}
        published = tools["interessi_legali"]["inputSchema"]["properties"]["accetta_precisione"]
        explicit = _wire(await client.call_tool_mcp("interessi_legali", {**args, "accetta_precisione": None}))
        absent = _wire(await client.call_tool_mcp("interessi_legali", args))
    assert published["type"] == ["string", "null"] and published["default"] is None and "anyOf" not in published
    assert explicit["isError"] is False
    assert explicit["content"] == absent["content"]
