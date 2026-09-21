"""Per-call provenance for online sources: when did this answer consult the web.

The tables in `src/data` carry their vintage in the file (`_vintage`), the
footer names them (`dati_applicati`) and the policy in `_precision` decides what
an expired or unverified table does to the answer. The online half of the
server had no such discipline: a jurisprudence search also produced a number --
a hit count, a date, a "nothing found" -- with nothing recording that the answer
rests on what a government site returned *that time*.

This module gives online answers the same shape the tables get:

* the **recording** is a contextvar, exactly like `_tables_open`: a client that
  just fetched calls `note("corte_cost", url=...)` and the *current call* owns
  the fact;
* the **reporting** happens in the same middleware pass that stamps
  `opened_tables`/`data_warnings`/`precisione`, so a host reads one `_meta` to
  know what an answer rests on, tables and online sources alike;
* the **audit** (`scripts/audit_tool_annotations.py`, via
  `scripts/collect_sources.py`) fails the suite when a tool fetches online
  without being in the committed policy, which is what turns "the client
  documents its sources" from a claim into an assertion -- the same move
  `test_egress_allowlist.py` makes for hosts.

A fetch inside a client that nothing imports at runtime (the Brocardi
standalone scraper, exercised only by scripts) still notes its source, but a
tool that never reaches a client never sees the note -- the declaration is
about tools that actually answer over the wire.

Nothing here reads the wall clock through the recorded path: the timestamp
comes from `_clock.now_unrecorded()`, because "when we fetched" is provenance
of an event, not an anchor of the answer to the present.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

#: Key under which a call declares the online sources it consulted, in `_meta`.
CONSULTED_SOURCES_KEY = "mcp-legal-it/fonti_consultate"

#: The set being filled by the current tool call, or None outside one.
CURRENT: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar(
    "legal_it_consulted_sources", default=None
)


def note(dataset: str, url: str | None = None) -> None:
    """Record that the current call consulted `dataset` (no-op outside a call).

    Called by the shared HTTP clients after a fetch; `dataset` is the stable
    name the audit policy uses ("corte_cost", "brocardi", ...). Malformed or
    non-HTTP URLs are still recorded as a consult (the fetch happened) but the
    host value keeps only the scheme://host//path prefix, never a query string:
    a provenance line must not carry the caller's search terms.
    """
    active = CURRENT.get()
    if active is None or not dataset:
        return
    host = url or ""
    if "://" in host:
        head, _, rest = host.partition("://")
        host = head + "://" + rest.split("?", 1)[0].split("#", 1)[0]
    active.add((dataset, host))


def consulted() -> list[dict]:
    """What the current call consulted so far: one dict per source, sorted."""
    active = CURRENT.get() or set()
    return [
        {"fonte": dataset, "url": url}
        for dataset, url in sorted(active, key=lambda item: (item[0], item[1]))
    ]


@contextmanager
def recording() -> Iterator[set[tuple[str, str]]]:
    """Collect, for the duration of the block, the sources used inside it."""
    opened: set[tuple[str, str]] = set()
    token = CURRENT.set(opened)
    try:
        yield opened
    finally:
        CURRENT.reset(token)


def now_stamp() -> str:
    """ISO timestamp for the provenance block: the moment the fetch happened.

    Deliberately NOT a recorded clock read (see `_clock.now_unrecorded`): a
    call that answers from a cache or from a closed archive must not look
    anchored to the present merely because it declared where its data came
    from. A pinned `LEGAL_NOW` pins this stamp too, so the golden stays
    reproducible -- and the freshness claim testable.
    """
    from . import _clock

    return _clock.now_unrecorded().isoformat(timespec="seconds")


def block() -> dict:
    """The `fonti_consultate` payload: what was consulted, and when.

    The timestamp is one per call (the moment the readback happens, within
    seconds of the fetches): good enough to age a source, honest about being a
    call-level stamp rather than a per-request log.
    """
    fonti = consulted()
    if not fonti:
        return {}
    return {"consultate_al": now_stamp(), "fonti": fonti}
