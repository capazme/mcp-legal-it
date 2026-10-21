"""Helpers shared by the API modules (provenance recording, source failures)."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Iterator

import httpx

from mcp_legal_it.lib import _sources
from mcp_legal_it.api.tipi import FonteConsultata, FontiConsultate


class Registro:
    """Collects the sources a call reaches; ``fonti()`` gives them as data."""

    def __init__(self) -> None:
        self.aperte: set[tuple[str, str]] = set()

    def fonti(self) -> FontiConsultate | None:
        if not self.aperte:
            return None
        return FontiConsultate(
            consultate_al=_sources.now_stamp(),
            fonti=tuple(FonteConsultata(fonte=d, url=u) for d, u in sorted(self.aperte)),
        )


@contextmanager
def registra() -> Iterator[Registro]:
    """Record the sources consulted inside the block.

    Inside an MCP tool call (a recording already open) the sources are also
    handed to it, so the call's ``fonti_consultate`` stays complete.
    """
    esterna = _sources.CURRENT.get()
    registro = Registro()
    with _sources.recording() as aperte:
        registro.aperte = aperte  # the live set: fonti() reads what is noted so far
        yield registro
    if esterna is not None:
        esterna |= registro.aperte


def fonte_giu(exc: BaseException) -> bool:
    """Whether an exception says the source is down, slow or limiting us."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        return status == 429 or status >= 500
    return isinstance(exc, (httpx.TransportError, asyncio.TimeoutError, TimeoutError, ConnectionError))
