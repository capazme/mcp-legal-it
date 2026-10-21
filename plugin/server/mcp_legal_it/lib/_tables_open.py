"""Which hand-maintained tables the running call has read, right now.

The recording itself, kept apart from the machinery that fills it: `_ledger`
wraps the table constants in traced containers and reports the result to the
host, while `_data` needs the same set to decide what a footer should name. This
module imports nothing but the standard library on purpose -- `_data` is loaded
by every tool at import time, and pulling the MCP framework in there would make
a table loader depend on a web framework.

Nothing is recorded outside a `recording()` block, so prompts, resources and
projections computed at import cost nothing.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

#: The set being filled by the current tool call, or None outside one.
CURRENT: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar(
    "legal_it_opened_tables", default=None
)


def note(dataset: str) -> None:
    """Record that the current call read `dataset` (a no-op outside a call)."""
    active = CURRENT.get()
    if active is not None and dataset:
        active.add(dataset)


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
