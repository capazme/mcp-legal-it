"""The shape of the `tools/list` answer: the same tools, said in fewer characters.

The model reads every tool definition at the start of a session (about 116k
tokens for the 231 tools), so the listing drops what carries no meaning for it.
Nothing here changes what a tool accepts: FastMCP validates every call against
the function's own signature, not against the schema it publishes.

- An optional parameter is published as ``type: [X, "null"]`` with
  ``default: null`` instead of ``anyOf [{"type": X}, {"type": "null"}]``: the
  same contract (it may be left out or be null), in one branch instead of two.
  Hosts that read a property's top-level ``type`` now find it. The null stays in
  the type on purpose: a client that converts the schema to OpenAI's strict
  mode makes every property required, and without a legal null the model would
  have to invent a value (an ``accetta_precisione`` it never chose).
- ``additionalProperties: false`` is left out of the input schemas. A call with
  an argument the tool does not have is still refused, by the server, with the
  same validation error; only a client that checks arguments before sending no
  longer refuses it itself.
- The indentation that docstrings leave at the start of continuation lines is
  dropped from descriptions. The words, and the line breaks, stay.
- The tools are listed by name, so the order is stable whatever the import
  order of the modules, profile or subset.
"""

from __future__ import annotations

import re
from typing import Any

from fastmcp.server.middleware import Middleware

_NULL = {"type": "null"}
_INDENT = re.compile(r"\n[ \t]+")


def compact_schema(schema: Any) -> Any:
    """``schema`` with the optional branches collapsed and no ``additionalProperties: false``."""
    if isinstance(schema, list):
        return [compact_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out = {
        key: compact_schema(value)
        for key, value in schema.items()
        if not (key == "additionalProperties" and value is False)
    }
    branches = out.get("anyOf")
    if (
        isinstance(branches, list)
        and len(branches) == 2
        and _NULL in branches
        and "default" in out
        and out["default"] is None
    ):
        others = [b for b in branches if b != _NULL]
        plain = others[0] if len(others) == 1 else None
        if (
            isinstance(plain, dict)
            and isinstance(plain.get("type"), str)
            and not (plain.keys() & out.keys() - {"anyOf"})
        ):
            rest = {key: value for key, value in out.items() if key != "anyOf"}
            # The type first, where the anyOf stood: the rest keeps its order.
            out = {**plain, "type": [plain["type"], "null"], **rest}
    return out


def tidy_description(text: str | None) -> str | None:
    """``text`` without the indentation at the start of its continuation lines."""
    if not text:
        return text
    return _INDENT.sub("\n", text)


def _tidy_properties(schema: dict) -> dict:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return schema
    tidied = {}
    for name, prop in properties.items():
        if isinstance(prop, dict) and isinstance(prop.get("description"), str):
            prop = {**prop, "description": tidy_description(prop["description"])}
        tidied[name] = prop
    return {**schema, "properties": tidied}


class ListingMiddleware(Middleware):
    """Publish every tool with the compact schema and description, sorted by name."""

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        listed = [
            tool.model_copy(
                update={
                    "parameters": _tidy_properties(compact_schema(tool.parameters)),
                    "description": tidy_description(tool.description),
                }
            )
            for tool in tools
        ]
        return sorted(listed, key=lambda tool: tool.name)


def apply_listing(server) -> None:
    """Install the listing middleware on a FastMCP server."""
    server.add_middleware(ListingMiddleware())
