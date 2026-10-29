"""A tool that answers plain text sends that text once.

FastMCP gives a function annotated ``-> str`` an output schema
``{"result": string}`` flagged ``x-fastmcp-wrap-result``, and then sends every
answer twice: as the text block and again as ``structuredContent:
{"result": <the same text>}``. For the reading tools that doubled the wire size
of a 22,000-character decision. Each text tool is therefore declared with
``@mcp.tool(..., output_schema=None)``, the switch FastMCP 3 and 4 document for
this, and the answer travels as the text block only.

The tools that return a dict keep their ``structuredContent``: there the
structure is the answer. The text block is always there, because hosts such as
VisuaLex read only the text.
"""

import asyncio
import json
import typing

import pytest
from fastmcp import Client

from mcp_legal_it.server import mcp


def _registered():
    return asyncio.run(mcp.local_provider.list_tools())


def _wire(obj) -> dict:
    """``obj`` as it travels in the JSON-RPC frame (same field names on FastMCP 3 and 4)."""
    return obj.model_dump(mode="json", by_alias=True, exclude_none=True)


def _returns_text(tool) -> bool:
    hints = typing.get_type_hints(tool.fn)
    return hints.get("return") is str


def test_every_text_tool_has_no_output_schema():
    tools = _registered()
    text_tools = [t for t in tools if _returns_text(t)]
    assert len(text_tools) >= 60
    wrapped = sorted(t.name for t in text_tools if t.output_schema is not None)
    assert not wrapped, (
        "these tools return str but still declare an output schema, so FastMCP sends their "
        f"text twice: add output_schema=None to their @mcp.tool(...): {wrapped}"
    )


def test_no_tool_wraps_its_result():
    wrapped = sorted(
        t.name for t in _registered() if t.output_schema and t.output_schema.get("x-fastmcp-wrap-result")
    )
    assert not wrapped


def test_dict_tools_keep_their_schema():
    dict_tools = [t for t in _registered() if not _returns_text(t)]
    assert dict_tools
    assert all(t.output_schema is not None for t in dict_tools)


@pytest.mark.asyncio
async def test_text_tool_answer_is_the_text_block_only():
    async with Client(mcp) as client:
        listed = {t.name: _wire(t) for t in await client.list_tools()}
        # A refusal answered locally, without the network.
        result = _wire(await client.call_tool_mcp("cite_law", {"reference": "art. 5 legge inventata 1/1900"}))
    assert "outputSchema" not in listed["cite_law"]
    assert "structuredContent" not in result
    assert [c["type"] for c in result["content"]] == ["text"]
    assert result["content"][0]["text"].startswith("**Errore")


@pytest.mark.asyncio
async def test_dict_tool_answer_keeps_structured_content():
    async with Client(mcp) as client:
        result = _wire(await client.call_tool_mcp(
            "interessi_legali", {"capitale": 1000, "data_inizio": "2020-01-01", "data_fine": "2020-12-31"}
        ))
    assert result["structuredContent"]
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
