"""Shared HTTP retry helper for government site clients.

Italian government sites (Italgiure, GA, CeRDEF, CONSOB) are notoriously
unreliable. This module provides a simple retry-with-backoff wrapper around
httpx requests. The per-source limits (concurrency, interval, «not before»,
host guard) are not here: they are in the client's transport (`core/_http`),
so they hold for every request, retried or not.

Every successful response is also noted as provenance for the current call
(`mcp_legal_it.lib._sources`): the middleware turns the note into the answer's
`fonti_consultate` declaration. `dataset` is the stable source name the audit
policy uses (TOOL_SOURCES in `mcp_legal_it/table_bindings.py`), so a fetcher that skips
the note shows up as a difference between observation and policy and the suite
fails on it.
"""

import asyncio
import random

import httpx

from mcp_legal_it.core._http import MAX_ATTESA_PAUSA, STATI_LIMITE, RifiutoLocale, pausa_dichiarata

from . import _sources

#: Random extra seconds (0 to this) added to each backoff, so retries from parallel calls spread out.
JITTER = 0.3


def note_source(dataset: str, url: str | None) -> None:
    """Declare one online consult for the current call (no-op outside one)."""
    _sources.note(dataset, url)


async def retry_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    dataset: str = "",
    max_retries: int = 2,
    backoff_base: float = 1.0,
    **kwargs,
) -> httpx.Response:
    """HTTP request with retry and exponential backoff.

    Retries on transport errors (connection, timeout), 5xx and 429, at most
    `max_retries` times after the first attempt, waiting `backoff_base * 2**n`
    plus up to `JITTER` seconds, or the `Retry-After` a 429/503 states when it
    is longer. A stated wait over `MAX_ATTESA_PAUSA` (30 s) ends the call at
    once, and so does a spent budget: no wait is spent on an attempt that will
    not follow. Other 4xx are not retried (client errors are not transient), nor
    is a request this process refused before it left (`RifiutoLocale`: a host
    the source may not reach, a paused or suspended source). On success, notes
    the consult as provenance for the current call when `dataset` is given.

    The «not before» pause a 429/503 states is kept per source by the client's
    transport (`core/_http`), so every other call to the source honours it too.

    Returns the successful response or re-raises the last exception.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        stated: float | None = None
        try:
            fn = getattr(client, method.lower())
            resp = await fn(url, **kwargs)
            resp.raise_for_status()
            if dataset:
                note_source(dataset, str(resp.url) if hasattr(resp, "url") else url)
            return resp
        except RifiutoLocale:
            raise
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code
                if status < 500 and status != 429:
                    raise
                if status in STATI_LIMITE:
                    stated = pausa_dichiarata(exc.response.headers)
                    if stated is not None and stated > MAX_ATTESA_PAUSA:
                        raise
            last_exc = exc
            if attempt < max_retries:
                wait = backoff_base * (2 ** attempt) + random.uniform(0, JITTER)
                await asyncio.sleep(max(wait, stated or 0.0))
    raise last_exc  # type: ignore[misc]
