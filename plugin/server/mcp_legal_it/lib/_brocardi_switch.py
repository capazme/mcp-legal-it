"""Whether this process may use Brocardi, and the gate every Brocardi request passes.

Brocardi.it is the server's only private source: doctrinal notes and case-law
abstracts, never the text of a norm (that always comes from Normattiva or
EUR-Lex). It stays on by default. A deployment that must not use it (rights,
policy, a commercial subset) switches it off in one of three ways:

* ``LEGAL_BROCARDI=off`` (or ``0``, ``false``, ``no``) in the environment, for the
  stock server, the plugin and every library call in the process;
* ``crea_server(brocardi=False)``, for one server built in code: its tool calls run
  with Brocardi off, whatever else the process does;
* ``disabled()`` (a context manager) or ``set_default(False)``, for library code
  that calls the scrapers directly.

An *off* always wins: code cannot switch Brocardi back on inside a process whose
operator switched it off in the environment, and ``set_default(True)`` is
refused there rather than ignored silently.

What *off* means, and where each part is enforced:

* the tools tagged ``solo_brocardi`` (their answer is nothing but Brocardi content)
  are not listed at all (``server.py``, ``crea_server``);
* the tools tagged ``brocardi`` that have other content (``cite_law`` with
  annotations, ``giurisprudenza_articolo``, ``mappa_orientamento``) answer without
  it and say so, in ``DISABLED_NOTE``;
* no request reaches brocardi.it: the two scrapers that build Brocardi URLs
  (``lib/brocardi/client.py`` and ``lib/visualex/scraper.py``) call ``guard()``
  before any network I/O and return their usual error shape when it refuses.
  ``tests/unit/test_brocardi_switch.py`` mocks the network and fails if any
  Brocardi tool, or either scraper, still issues a request.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator
from urllib.parse import urlparse

#: The environment switch.
ENV_SWITCH = "LEGAL_BROCARDI"
#: The tag of every tool whose answer can contain Brocardi content.
TAG = "brocardi"
#: The tag of the tools whose answer is Brocardi content only: hidden when off.
TAG_SOLO = "solo_brocardi"
#: The hosts that are Brocardi.
HOSTS = frozenset({"www.brocardi.it", "brocardi.it"})
#: What a tool says in place of the Brocardi part of its answer when it is off.
DISABLED_NOTE = (
    "Brocardi disattivato in questa installazione (LEGAL_BROCARDI=off): "
    "nessuna annotazione dottrinale né massima da brocardi.it"
)

_OFF_VALUES = {"off", "0", "false", "no"}

#: Per-context override: set by ``disabled()`` and by the middleware ``crea_server`` installs.
_context: ContextVar[bool | None] = ContextVar("mcp_legal_it_brocardi", default=None)
#: Process-wide default set by library code with ``set_default``.
_process_default: bool | None = None


class BrocardiDisabled(RuntimeError):
    """Raised by ``guard()`` for a Brocardi request while Brocardi is off."""

    def __init__(self) -> None:
        super().__init__(DISABLED_NOTE)


def off_by_environment(value: str | None = None) -> bool:
    """Whether the environment (or the given value of ``LEGAL_BROCARDI``) switches Brocardi off."""
    raw = os.environ.get(ENV_SWITCH) if value is None else value
    return (raw or "").strip().lower() in _OFF_VALUES


def enabled() -> bool:
    """Whether a Brocardi request is allowed right now.

    The environment's *off* wins; then the current context (``disabled()``, a
    ``crea_server(brocardi=False)`` call); then ``set_default``; default on.
    """
    if off_by_environment():
        return False
    ctx = _context.get()
    if ctx is not None:
        return ctx
    if _process_default is not None:
        return _process_default
    return True


def set_default(value: bool | None) -> None:
    """Set (``True``/``False``) or clear (``None``) the process-wide default.

    ``True`` cannot override an environment *off*: it raises instead.
    """
    global _process_default
    if value and off_by_environment():
        raise ValueError(f"{ENV_SWITCH}=off is set in the environment: Brocardi cannot be switched back on")
    _process_default = value


@contextmanager
def disabled() -> Iterator[None]:
    """Run a block with Brocardi off (for this context only)."""
    token = _context.set(False)
    try:
        yield
    finally:
        _context.reset(token)


def set_for_context(value: bool) -> object:
    """Low-level: set the override for the current context; returns the token for ``reset``."""
    return _context.set(value)


def reset(token: object) -> None:
    """Undo ``set_for_context``."""
    _context.reset(token)  # type: ignore[arg-type]


def is_brocardi_url(url: str) -> bool:
    return (urlparse(url).hostname or "").lower() in HOSTS


def guard(url: str = "https://www.brocardi.it/") -> None:
    """Refuse a Brocardi request while Brocardi is off. No-op for any other host."""
    if is_brocardi_url(url) and not enabled():
        raise BrocardiDisabled()
