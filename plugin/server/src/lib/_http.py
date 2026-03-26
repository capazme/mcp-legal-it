"""Shared HTTP retry helper for government site clients.

Italian government sites (Italgiure, GA, CeRDEF, CONSOB) are notoriously
unreliable. This module provides a simple retry-with-backoff wrapper around
httpx requests.
"""

import asyncio

import httpx


async def retry_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 2,
    backoff_base: float = 1.0,
    **kwargs,
) -> httpx.Response:
    """HTTP request with retry and exponential backoff.

    Retries on transport errors (connection, timeout) and 5xx status codes.
    Does NOT retry on 4xx (client errors are not transient).

    Returns the successful response or re-raises the last exception.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            fn = getattr(client, method.lower())
            resp = await fn(url, **kwargs)
            resp.raise_for_status()
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                raise
            last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(backoff_base * (2 ** attempt))
    raise last_exc  # type: ignore[misc]
