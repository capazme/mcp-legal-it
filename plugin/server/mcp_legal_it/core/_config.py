"""The settings a library caller can inject: HTTP client factory, cache, Brocardi.

One ``Configurazione`` is in force at any moment: the one set for the current
context (``configurazione()``, a ContextVar, so concurrent tasks may differ), else
the process default (``configura()``), else the built-in default (every field
``None``: the environment decides, as for the stock server).

The environment keeps the last word on what an operator switched off:
``LEGAL_CACHE=off`` disables the disk caches whatever ``cache`` says, and
``LEGAL_BROCARDI=off`` disables Brocardi whatever ``brocardi`` says
(``lib/_cache.py``, ``lib/_brocardi_switch.py``).
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterator

if TYPE_CHECKING:  # pragma: no cover - typing only
    import httpx

#: ``factory(fonte, **kwargs) -> httpx.AsyncClient``. ``fonte`` is the stable source
#: name (``"normattiva"``, ``"italgiure"``, ...); ``kwargs`` are exactly what the
#: library would pass to ``httpx.AsyncClient`` (headers, timeout, ``verify=False``
#: for Italgiure, ...). The client is used as an async context manager and closed.
ClientFactory = Callable[..., "httpx.AsyncClient"]


@dataclass(frozen=True)
class Configurazione:
    """What a library caller may set. ``None`` means "as the environment says"."""

    #: Builds every HTTP client the libraries open (see ``ClientFactory``).
    client_factory: ClientFactory | None = None
    #: Directory of the disk caches, in place of ``MCP_CACHE_DIR``.
    cache_dir: str | Path | None = None
    #: ``False``: no disk cache (as ``LEGAL_CACHE=off``). ``True`` cannot override that variable.
    cache: bool | None = None
    #: ``False``: no Brocardi request (as ``LEGAL_BROCARDI=off``).
    brocardi: bool | None = None


_DEFAULT = Configurazione()
_process: Configurazione = _DEFAULT
_context: ContextVar[Configurazione | None] = ContextVar("mcp_legal_it_configurazione", default=None)


def attuale() -> Configurazione:
    """The configuration in force for the current context."""
    ctx = _context.get()
    return ctx if ctx is not None else _process


class _NonIndicato:
    """Marks a field the caller did not pass (``None`` is a value: "as the environment says")."""

    def __repr__(self) -> str:
        return "NON_INDICATO"


NON_INDICATO = _NonIndicato()


def _campi(**valori) -> dict:
    return {k: v for k, v in valori.items() if v is not NON_INDICATO}


def configura(
    *,
    client_factory: ClientFactory | None | _NonIndicato = NON_INDICATO,
    cache_dir: str | Path | None | _NonIndicato = NON_INDICATO,
    cache: bool | None | _NonIndicato = NON_INDICATO,
    brocardi: bool | None | _NonIndicato = NON_INDICATO,
) -> Configurazione:
    """Set fields of the process default (``configura(cache=False)``); returns the new default.

    Fields not passed keep their value; ``configura()`` with no field resets the
    default to the built-in one. ``brocardi=True`` is refused (``ValueError``) when
    ``LEGAL_BROCARDI=off`` is set.
    """
    global _process
    from mcp_legal_it.lib import _brocardi_switch

    campi = _campi(client_factory=client_factory, cache_dir=cache_dir, cache=cache, brocardi=brocardi)
    nuovo = replace(_process, **campi) if campi else _DEFAULT
    if "brocardi" in campi or not campi:
        _brocardi_switch.set_default(nuovo.brocardi)
    _process = nuovo
    return nuovo


@contextmanager
def configurazione(
    *,
    client_factory: ClientFactory | None | _NonIndicato = NON_INDICATO,
    cache_dir: str | Path | None | _NonIndicato = NON_INDICATO,
    cache: bool | None | _NonIndicato = NON_INDICATO,
    brocardi: bool | None | _NonIndicato = NON_INDICATO,
) -> Iterator[Configurazione]:
    """Run a block with these fields overriding the configuration in force (this context only).

    ``brocardi=True`` is refused (``ValueError``) when ``LEGAL_BROCARDI=off`` is set.
    """
    from mcp_legal_it.lib import _brocardi_switch

    campi = _campi(client_factory=client_factory, cache_dir=cache_dir, cache=cache, brocardi=brocardi)
    nuovo = replace(attuale(), **campi)
    if campi.get("brocardi") and _brocardi_switch.off_by_environment():
        # Same rule as set_default(True): refused, not silently ignored.
        raise ValueError(
            f"{_brocardi_switch.ENV_SWITCH}=off is set in the environment: Brocardi cannot be switched back on"
        )
    token = _context.set(nuovo)
    brocardi_token = _brocardi_switch.set_for_context(nuovo.brocardi) if nuovo.brocardi is not None else None
    try:
        yield nuovo
    finally:
        if brocardi_token is not None:
            _brocardi_switch.reset(brocardi_token)
        _context.reset(token)
