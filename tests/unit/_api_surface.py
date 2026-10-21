"""How the frozen public surface of ``mcp_legal_it.api`` is described (see test_api_surface.py)."""

import dataclasses
import inspect
import typing

from mcp_legal_it import api


def _describe(obj) -> str:
    if dataclasses.is_dataclass(obj) and isinstance(obj, type):
        parts = []
        for f in dataclasses.fields(obj):
            has_default = f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING
            parts.append(f"{f.name}: {f.type}" + (" = ..." if has_default else ""))
        return "dataclass(" + ", ".join(parts) + ")"
    if inspect.isfunction(obj):
        kind = "async def" if inspect.iscoroutinefunction(obj) else "def"
        return f"{kind}{inspect.signature(obj)}"
    if typing.get_origin(obj) is typing.Literal:
        return "Literal" + repr(typing.get_args(obj))
    if isinstance(obj, (str, tuple)):
        return f"{type(obj).__name__} = {obj!r}"
    return "alias"


def describe_surface() -> dict[str, str]:
    return {name: _describe(getattr(api, name)) for name in sorted(api.__all__)}
