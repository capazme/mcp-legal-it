"""Probe a supplier's own domain for a published art. 28 processor designation.

Knows URL conventions, never vendor names: a list of conventions ages far more
slowly than a list of individual links.
"""

import hashlib
import re
from dataclasses import dataclass, field

import httpx

from src.lib._http import retry_request
from src.lib.dpa_probe.judge import (
    VERDETTO_NON_TROVATO,
    giudica_html,
    giudica_pdf,
)

VERDETTO_BLOCCATO = "bloccato"
VERDETTO_IRRAGGIUNGIBILE = "dominio_irraggiungibile"

PERCORSI: tuple[str, ...] = (
    "/legal/dpa",
    "/dpa",
    "/legal/data-processing-addendum",
    "/legal/data-processing",
    "/privacy/dpa",
    "/legal/terms/dataprocessing",
    "/trust/gdpr",
    "/gdpr",
)

_SONDA_404 = "/__dpa_probe_404__"
_TIMEOUT = httpx.Timeout(20.0, connect=8.0)
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36"
)
_PATH_LEGALE = re.compile(r"/(legal|privacy|dpa|gdpr|trust|termini|condizioni)", re.I)


@dataclass
class EsitoSonda:
    verdetto: str
    url_evidenza: str | None = None
    marcatori: list[str] = field(default_factory=list)
    evidenza: str | None = None
    errore: str | None = None


def normalizza_dominio(valore: str) -> str:
    """`https://www.Example.com/legal/` → `example.com`."""
    v = valore.strip().lower()
    v = re.sub(r"^[a-z]+://", "", v)
    v = v.split("/")[0].split("?")[0]
    return v[4:] if v.startswith("www.") else v


def _impronta(testo: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", testo).strip().encode("utf-8", "ignore")).hexdigest()


async def sonda_dominio(dominio: str) -> EsitoSonda:
    """Probe conventional DPA paths. Never raises.

    This is a boundary function: its input ultimately comes from a supplier
    ledger with dirty real-world data, and both the cache and the MCP tool
    that sit on top of it assume it always returns an `EsitoSonda`. The
    branches below already give a precise `errore` for the failure modes we
    anticipated (unreachable host, transport errors, anti-bot blocks). This
    outer guard exists for the ones we didn't — e.g. `httpx.InvalidURL` from
    a malformed domain string (`"example.com:abc"`), which inherits directly
    from `Exception` and would otherwise slip past every handler below.
    """
    try:
        return await _sonda_dominio(dominio)
    except Exception as exc:  # noqa: BLE001 - never raise out of the public API
        return EsitoSonda(VERDETTO_IRRAGGIUNGIBILE, errore=f"{exc.__class__.__name__}")


async def _sonda_dominio(dominio: str) -> EsitoSonda:
    host = normalizza_dominio(dominio)
    if not host:
        return EsitoSonda(VERDETTO_IRRAGGIUNGIBILE, errore="dominio vuoto")
    base = f"https://{host}"
    headers = {"User-Agent": _UA}

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as client:
        # Learn the domain's error-page fingerprint so soft-404s can be spotted.
        impronta_404: str | None = None
        try:
            r = await client.get(base + _SONDA_404)
            if r.status_code == 200:
                impronta_404 = _impronta(r.text)
        except httpx.TransportError as exc:
            return EsitoSonda(VERDETTO_IRRAGGIUNGIBILE, errore=f"{exc.__class__.__name__}")

        bloccato = False
        for percorso in PERCORSI:
            url = base + percorso
            try:
                resp = await retry_request(client, "get", url, max_retries=1)
            except httpx.HTTPStatusError as exc:
                # 401/403/400 from a non-browser client is an anti-bot block, not an absence.
                if exc.response.status_code in (400, 401, 403, 429):
                    bloccato = True
                continue
            except httpx.TransportError:
                continue

            finale = str(resp.url)
            if normalizza_dominio(finale) != host or not _PATH_LEGALE.search(finale):
                continue

            tipo = (resp.headers.get("content-type") or "").lower()
            if "application/pdf" in tipo:
                g = giudica_pdf(finale)
            else:
                if impronta_404 and _impronta(resp.text) == impronta_404:
                    continue
                # The final URL is part of the evidence: it is what lets a
                # genuine DPA served under a generic page title still confirm.
                g = giudica_html(resp.text, finale)

            if g.verdetto != VERDETTO_NON_TROVATO:
                return EsitoSonda(g.verdetto, finale, g.marcatori, g.evidenza)

    if bloccato:
        return EsitoSonda(VERDETTO_BLOCCATO, errore="risposta di blocco a client non-browser")
    return EsitoSonda(VERDETTO_NON_TROVATO)
