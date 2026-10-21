"""The one place where the libraries open an HTTP client.

Every ``httpx.AsyncClient`` in ``mcp_legal_it.lib`` is made by ``async_client``,
which names the source it is for. Today that buys one thing: a library caller
can hand in its own factory (``Configurazione.client_factory``), to add a cache
or a test transport, and every source keeps the headers, timeouts and TLS
settings it needs.

It is also where the network rules shared with VisuaLex will live (migration
phase, not implemented yet): a per-source rate limit and «not before» time
(from ``Retry-After``, capped at 30 s), a retry budget, and the host allowlist
(today a test over ``lib/_egress.py``, then enforced here). The ``fonte`` name each
call site passes is the key those rules will need.
"""

from __future__ import annotations

import httpx

from mcp_legal_it.core import _config

__all__ = ["async_client"]


def async_client(fonte: str, **kwargs) -> httpx.AsyncClient:
    """A new ``httpx.AsyncClient`` for *fonte*, built with *kwargs*.

    Without an injected factory this is exactly ``httpx.AsyncClient(**kwargs)``
    (looked up at call time, so tests that patch ``httpx.AsyncClient`` still see
    every client).
    """
    factory = _config.attuale().client_factory
    if factory is None:
        return httpx.AsyncClient(**kwargs)
    return factory(fonte, **kwargs)
