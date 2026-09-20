"""Shared HTTP retry helper for government site clients.

Italian government sites (Italgiure, GA, CeRDEF, CONSOB) are notoriously
unreliable. This module provides a simple retry-with-backoff wrapper around
httpx requests.

Every successful response is also noted as provenance for the current call
(`src.lib._sources`): the middleware turns the note into the answer's
`fonti_consultate` declaration. `dataset` is the stable source name the audit
policy uses (TOOL_SOURCES in `src/table_bindings.py`), so a fetcher that skips
the note shows up as a difference between observation and policy and the suite
fails on it.
"""

import asyncio

import httpx

from . import _sources


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

    Retries on transport errors (connection, timeout) and 5xx status codes.
    Does NOT retry on 4xx (client errors are not transient). On success, notes
    the consult as provenance for the current call when `dataset` is given.

    Returns the successful response or re-raises the last exception.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            fn = getattr(client, method.lower())
            resp = await fn(url, **kwargs)
            resp.raise_for_status()
            if dataset:
                note_source(dataset, str(resp.url) if hasattr(resp, "url") else url)
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                raise
            last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(backoff_base * (2 ** attempt))
    raise last_exc  # type: ignore[misc]
