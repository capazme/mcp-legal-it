"""Record, per tool call, which hand-maintained tables the call actually read.

`@sourced(...)` declares which tables a tool's answer rests on, and
`scripts/audit_tool_annotations.py` verifies that declaration against the source
-- statically. This module adds the runtime half of the same claim: the
module-level constants that hold a table (or a projection of one, such as
`_CATEGORIE = sorted({v["categoria"] for v in _CATALOGO.values()})`) are replaced
by dict and list subclasses that note their dataset when they are read, so the
server can report which tables a *call* opened rather than which ones the code
might open.

The two oracles are deliberately independent, and that is the point: the audit
walks the call graph and says what the code can read, the ledger observes the
process and says what it did read. A table the ledger reports that the audit does
not attribute to the tool means the walk misses a reader -- the failure mode that
hid `codici_tributo`, `modelli_atti` and `preavviso_ccnl` -- and the suite fails
on it instead of trusting the derivation.

The wrapping is shallow on purpose. Reaching the top of a table is what proves
the call consulted it, and leaving nested values plain keeps `json.dumps`, `==`
and the host's serialization working on exactly the same objects as before.

Nothing is recorded outside a `recording()` block, so prompts, resources and
import-time projections cost nothing.
"""

from __future__ import annotations

import contextvars
import sys
from contextlib import contextmanager
from typing import Any, Iterator

from fastmcp.server.middleware import Middleware

#: Key under which a call declares the tables it opened, in the result `_meta`.
OPENED_TABLES_KEY = "mcp-legal-it/opened_tables"

#: The set being filled by the current tool call, or None outside one.
CURRENT: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar(
    "legal_it_opened_tables", default=None
)


def _note(dataset: str) -> None:
    active = CURRENT.get()
    if active is not None and dataset:
        active.add(dataset)


class TableDict(dict):
    """A table payload that notes its dataset when it is read."""

    def __init__(self, payload: dict, dataset: str = "") -> None:
        super().__init__(payload)
        self.dataset = dataset

    def __getitem__(self, key: Any) -> Any:
        _note(self.dataset)
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        _note(self.dataset)
        return super().get(key, default)

    def keys(self):  # type: ignore[override]
        _note(self.dataset)
        return super().keys()

    def values(self):  # type: ignore[override]
        _note(self.dataset)
        return super().values()

    def items(self):  # type: ignore[override]
        _note(self.dataset)
        return super().items()

    def __iter__(self):
        _note(self.dataset)
        return super().__iter__()

    def __contains__(self, key: Any) -> bool:
        _note(self.dataset)
        return super().__contains__(key)


class TableList(list):
    """A table payload (or a projection of one) that notes its dataset."""

    def __init__(self, payload: list, dataset: str = "") -> None:
        super().__init__(payload)
        self.dataset = dataset

    def __getitem__(self, index: Any) -> Any:
        _note(self.dataset)
        return super().__getitem__(index)

    def __iter__(self):
        _note(self.dataset)
        return super().__iter__()

    def __contains__(self, item: Any) -> bool:
        _note(self.dataset)
        return super().__contains__(item)


@contextmanager
def recording() -> Iterator[set[str]]:
    """Collect, for the duration of the block, the tables read inside it."""
    opened: set[str] = set()
    token = CURRENT.set(opened)
    try:
        yield opened
    finally:
        CURRENT.reset(token)


def opened() -> list[str]:
    """Tables noted so far in the current recording, sorted."""
    active = CURRENT.get()
    return sorted(active or ())


def install(bindings: dict[str, dict[str, str]]) -> int:
    """Wrap the table-carrying constants of already-imported modules.

    Only modules already in `sys.modules` are touched: importing one here would
    run its module-level loads inside this function, and a table that no import
    reached is one no tool can read anyway. Constants whose value is already a
    wrapper are skipped, so calling this twice is not a double wrap.
    """
    wrapped = 0
    for module_name, constants in bindings.items():
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for name, dataset in constants.items():
            value = getattr(module, name, None)
            if isinstance(value, (TableDict, TableList)):
                continue
            replacement: Any = None
            if isinstance(value, dict):
                replacement = TableDict(value, dataset)
            elif isinstance(value, list):
                replacement = TableList(value, dataset)
            if replacement is None:
                continue
            setattr(module, name, replacement)
            wrapped += 1
    return wrapped


class TableLedgerMiddleware(Middleware):
    """Declare, on every tool result, the tables that call actually opened.

    The list lives in the result's `_meta`, next to the answer it belongs to, so
    a host can show it and a test can read it over the wire instead of trusting
    the source. An answer that reads nothing carries no key: absence is the
    honest report for a pure algorithm, and an empty list would look like a
    declaration nobody could distinguish from a missing one.
    """

    async def on_call_tool(self, context, call_next):
        with recording() as opened:
            result = await call_next(context)
        meta = getattr(result, "meta", None)
        if opened and meta is not None:
            result.meta = {**meta, OPENED_TABLES_KEY: sorted(opened)}
        elif opened and hasattr(result, "meta"):
            result.meta = {OPENED_TABLES_KEY: sorted(opened)}
        return result


def apply_table_ledger(server, bindings: dict[str, dict[str, str]]) -> int:
    """Wrap the table constants and install the ledger middleware.

    Returns how many constants were wrapped, which the server logs on startup so
    a bindings file that matches no imported module is visible instead of silent.
    """
    wrapped = install(bindings)
    server.add_middleware(TableLedgerMiddleware())
    return wrapped
