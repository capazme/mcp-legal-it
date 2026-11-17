"""Whether this process may use Brocardi, and the gate every Brocardi request passes.

Brocardi.it is the server's only private source: doctrinal notes and case-law
abstracts, never the text of a norm (that always comes from Normattiva or
EUR-Lex). It is **off by default** (decision LI-079): with nothing set, no request
reaches brocardi.it and the tools whose answer is Brocardi content only are not
listed. Every other source stays on.

The environment variable ``LEGAL_BROCARDI`` is the operator's switch, for the stock
server, the plugin, the ``.mcpb`` bundle and every library call in the process:

* unset or empty: off (the default);
* ``on``, ``1``, ``true`` or ``yes`` (any case): on;
* ``off``, ``0``, ``false`` or ``no`` (any case): off, explicitly;
* any other value: off (fail closed). An unrecognised value counts as an explicit
  off, since the operator's intent is unknown: code cannot switch Brocardi back
  on, and the stock server reports the value on stderr at start-up and in
  ``stato_server``.

Code can choose too, inside what the environment allows:

* ``crea_server(brocardi=True)``, ``configurazione(brocardi=True)`` or
  ``set_default(True)`` switch it on, for one server, one block or the whole
  process; ``crea_server()`` with no argument follows the process;
* ``crea_server(brocardi=False)``, ``configurazione(brocardi=False)``,
  ``disabled()`` (a context manager) or ``set_default(False)`` switch it off, also
  where the environment says ``on``.

An operator's *off* always wins: code cannot switch Brocardi on inside a process
whose environment says off (or says something unrecognised), and every attempt
(``set_default(True)``, ``configurazione(brocardi=True)``,
``crea_server(brocardi=True)``) raises ``ValueError`` rather than being ignored
silently. The order is: the environment's off; the current context (``disabled()``,
``configurazione``, the middleware ``crea_server`` installs); ``set_default``; the
environment's on; off.

What *off* means, and where each part is enforced:

* the tools tagged ``solo_brocardi`` (their answer is nothing but Brocardi content)
  are not listed and cannot be called. The stock server carries a visibility
  transform (``server.py``) that hides them whenever Brocardi is off for the
  listing or the call in progress, so ``crea_server(brocardi=True)``, which mounts
  the stock server and switches Brocardi on for its own requests, lists them again;
* the tools tagged ``brocardi`` that have other content (``cite_law`` with
  annotations, ``giurisprudenza_articolo``, ``mappa_orientamento``) answer without
  it and say so in one line, ``DISABLED_NOTE``, where the Brocardi part would have been;
* no request reaches brocardi.it: the two scrapers that build Brocardi URLs
  (``lib/brocardi/client.py`` and ``lib/visualex/scraper.py``) call ``guard()``
  before any network I/O and return their usual error shape when it refuses, and
  the egress checks (``lib/_egress.py``, ``core/_http.py``) refuse the host.
  ``tests/unit/test_brocardi_switch.py`` mocks the network and fails if any
  Brocardi tool, or either scraper, still issues a request.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Literal
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
#: Neutral on purpose: off is the normal state, and how to switch it on is for the
#: operator documentation, not for the model or the user.
DISABLED_NOTE = (
    "Brocardi non attivo in questa installazione: "
    "nessuna annotazione dottrinale né massima da brocardi.it"
)

#: The values of ``LEGAL_BROCARDI`` that switch Brocardi on (compared case-insensitively).
ON_VALUES = ("on", "1", "true", "yes")
#: The values of ``LEGAL_BROCARDI`` that switch Brocardi off (compared case-insensitively).
OFF_VALUES = ("off", "0", "false", "no")

EnvironmentState = Literal["unset", "on", "off", "unrecognised"]

#: Per-context override: set by ``disabled()``, ``configurazione`` and the middleware ``crea_server`` installs.
_context: ContextVar[bool | None] = ContextVar("mcp_legal_it_brocardi", default=None)
#: Process-wide default set by library code with ``set_default``.
_process_default: bool | None = None


class BrocardiDisabled(RuntimeError):
    """Raised by ``guard()`` for a Brocardi request while Brocardi is off."""

    def __init__(self) -> None:
        super().__init__(DISABLED_NOTE)


def environment_value(value: str | None = None) -> str:
    """The raw value of ``LEGAL_BROCARDI`` (or ``value``), stripped; ``""`` when unset."""
    raw = os.environ.get(ENV_SWITCH) if value is None else value
    return (raw or "").strip()


def environment_state(value: str | None = None) -> EnvironmentState:
    """What the environment (or the given value of ``LEGAL_BROCARDI``) says."""
    raw = environment_value(value).lower()
    if not raw:
        return "unset"
    if raw in ON_VALUES:
        return "on"
    if raw in OFF_VALUES:
        return "off"
    return "unrecognised"


def unrecognised_value(value: str | None = None) -> str | None:
    """The value of ``LEGAL_BROCARDI`` when it is not one of the accepted ones, else ``None``."""
    return environment_value(value) if environment_state(value) == "unrecognised" else None


def on_by_environment(value: str | None = None) -> bool:
    """Whether the environment switches Brocardi on (``on``, ``1``, ``true``, ``yes``)."""
    return environment_state(value) == "on"


def off_by_environment(value: str | None = None) -> bool:
    """Whether the operator switched Brocardi off: an off value, or one not recognised.

    Unset is not an operator off: Brocardi is off by default, but code may switch it on.
    """
    return environment_state(value) in ("off", "unrecognised")


def accepted_values() -> str:
    """The accepted values, for error messages and the start-up warning."""
    return f"on: {', '.join(ON_VALUES)}; off: {', '.join(OFF_VALUES)}"


def refusal(value: str | None = None) -> str:
    """Why code may not switch Brocardi on here (``""`` when it may)."""
    state = environment_state(value)
    if state == "off":
        return (f"{ENV_SWITCH}={environment_value(value)!r} is set in the environment: "
                "Brocardi cannot be switched back on")
    if state == "unrecognised":
        return (f"{ENV_SWITCH}={environment_value(value)!r} is not a recognised value, so Brocardi "
                f"stays off and cannot be switched on from code (accepted values: {accepted_values()})")
    return ""


def check_can_switch_on() -> None:
    """Raise ``ValueError`` if the environment forbids switching Brocardi on."""
    motivo = refusal()
    if motivo:
        raise ValueError(motivo)


def enabled() -> bool:
    """Whether a Brocardi request is allowed right now.

    The environment's off (explicit or unrecognised) wins; then the current context
    (``disabled()``, ``configurazione``, a ``crea_server`` call); then ``set_default``;
    then the environment's on; default off.
    """
    state = environment_state()
    if state in ("off", "unrecognised"):
        return False
    ctx = _context.get()
    if ctx is not None:
        return ctx
    if _process_default is not None:
        return _process_default
    return state == "on"


def set_default(value: bool | None) -> None:
    """Set (``True``/``False``) or clear (``None``) the process-wide default.

    ``True`` cannot override an environment off (explicit or unrecognised): it raises instead.
    """
    global _process_default
    if value:
        check_can_switch_on()
    _process_default = value


@contextmanager
def disabled() -> Iterator[None]:
    """Run a block with Brocardi off (for this context only)."""
    token = _context.set(False)
    try:
        yield
    finally:
        _context.reset(token)


def context_value() -> bool | None:
    """The override set for the current context (``None``: none)."""
    return _context.get()


def set_for_context(value: bool | None) -> object:
    """Low-level: set the override for the current context; returns the token for ``reset``.

    ``None`` clears it (the process default and the environment decide). Does not check
    the environment: ``enabled()`` lets the environment's off win anyway.
    """
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
