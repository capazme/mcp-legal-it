"""The one place where the libraries open an HTTP client, and the network rules.

Every ``httpx.AsyncClient`` in ``mcp_legal_it.lib`` is made by ``async_client``,
which names the source (``fonte``) it is for. Two kinds of rule hang on that name.

**Guards** (security, cannot be switched off). A ``request`` hook checks every
request, each redirect hop included, before it leaves: scheme http(s), no
credentials in the URL, and a host the source may reach (``HOST_PER_FONTE``, a
subset of ``lib/_egress.ALLOWED_HOSTS``). A refused request raises
``HostNonConsentito`` and nothing reaches the network. The hook is passed in the
client's ``event_hooks``, so ``GUARDIE`` re-applies it to a client an injected
factory returns.

**Limits** (politeness towards the sources), per source and shared by every
client of the process, ported from VisuaLex's ``ThrottledHttpClient`` and
``CircuitBreaker`` (VisuaLexAPI ``services/visualex/visualex_api/services/http_client.py``
and ``tools/circuit_breaker.py`` at ``eca698dc``, MPL-2.0):

* at most ``Politica.concorrenza`` requests in flight to a source (3), body
  included, and at least ``Politica.intervallo`` seconds between two requests to
  it (0.5 s);
* a 429 or 503 that states a ``Retry-After`` pauses the source: the next request
  to it, from any caller, waits the pause out first, or is refused at once
  (``FontePausata``) when more than ``MAX_ATTESA_PAUSA`` (30 s) is left. Our own
  backoff never pauses a source (``lib/_http.retry_request`` owns retries);
* an optional circuit breaker (``LEGAL_CIRCUIT_BREAKER=on``; off by default):
  after 3 consecutive failures (a network error, a 5xx or a 429, never a 404 or
  another 4xx) the source is refused for 300 s (``FonteSospesa``), then one trial
  request decides.

A source with no host list (``dpa_probe``: whatever site the caller names) keeps
its limits per host, so one site's pause or failures never hold another's.

The limits live in a transport wrapped around the client's own (and around any
proxy transport httpx mounted from the environment), so they count real network
requests. A client an injected ``client_factory`` returns is the factory's: the
limits apply to it only if it builds its network transport with ``con_regole``
(so a cache it puts above that transport serves its hits without waiting).
"""

from __future__ import annotations

import asyncio
import email.utils
import math
import os
import time
import weakref
from dataclasses import dataclass, field

import httpx

from mcp_legal_it.core import _config

__all__ = [
    "GUARDIE",
    "HOST_PER_FONTE",
    "MAX_ATTESA_PAUSA",
    "FontePausata",
    "FonteSospesa",
    "HostNonConsentito",
    "Politica",
    "RifiutoLocale",
    "async_client",
    "con_regole",
    "pausa_dichiarata",
]

#: The hosts each source may reach. ``None``: any public host, by design
#: (``dpa_probe`` reads the vendor's own site, behind its own DNS and redirect
#: checks in ``lib/dpa_probe``). VisuaLex additionally reaches
#: ``www.portaledelmassimario.ipzs.it`` for its massimario, which stays in VisuaLex.
HOST_PER_FONTE: dict[str, frozenset[str] | None] = {
    "normattiva": frozenset({"www.normattiva.it"}),
    "eur_lex": frozenset({"eur-lex.europa.eu", "publications.europa.eu"}),
    "italgiure": frozenset({"www.italgiure.giustizia.it"}),
    "corte_cost": frozenset({"dati.cortecostituzionale.it"}),
    "cerdef": frozenset({"def.finanze.it"}),
    "giustizia_amm": frozenset({"www.giustizia-amministrativa.it", "mdp.giustizia-amministrativa.it"}),
    "cgue": frozenset({"publications.europa.eu"}),
    "brocardi": frozenset({"www.brocardi.it"}),
    "gazzetta": frozenset({"www.gazzettaufficiale.it"}),
    "gpdp": frozenset({"www.garanteprivacy.it", "servizi.gpdp.it"}),
    "consob": frozenset({"www.consob.it"}),
    "parlamento_senato": frozenset({"dati.senato.it"}),
    "parlamento_camera": frozenset({"dati.camera.it"}),
    "tmview": frozenset({"www.tmdn.org"}),
    "vies": frozenset({"ec.europa.eu"}),
    "dpa_probe": None,
}


#: Settings a factory cannot drop: they are re-applied to the client it returns.
#: ``event_hooks`` carry the request guards (the host check above on every
#: client; ``dpa_probe`` adds its own check against private addresses);
#: ``follow_redirects=False`` is a guard too. A factory may add hooks of its own;
#: the library's run first.
GUARDIE = ("event_hooks", "follow_redirects")

#: The longest «not before» pause a request waits out; past it the request is refused.
MAX_ATTESA_PAUSA = 30.0

#: Statuses whose ``Retry-After`` pauses the source.
STATI_LIMITE = frozenset({429, 503})

#: The longest pause a ``Retry-After`` can set (a day): a larger statement is read as this.
PAUSA_MASSIMA = 86400.0

#: The real class, kept before any test patches ``httpx.AsyncClient`` with a stand-in.
_ASYNC_CLIENT = httpx.AsyncClient


class RifiutoLocale(httpx.TransportError):
    """A request this process refused before it left: never retried by ``retry_request``.

    A ``TransportError``, so a caller that turns a network failure into "source
    unreachable" does the same with these.
    """


class HostNonConsentito(RifiutoLocale):
    """The request named a host, scheme or credentials its source may not use."""


class FontePausata(RifiutoLocale):
    """The source asked for a pause longer than ``MAX_ATTESA_PAUSA``; ``retry_after`` is what is left."""

    def __init__(self, message: str, *, retry_after: float, request: httpx.Request | None = None) -> None:
        super().__init__(message, request=request)
        self.retry_after = retry_after


class FonteSospesa(RifiutoLocale):
    """The circuit breaker holds the source after repeated failures (``LEGAL_CIRCUIT_BREAKER=on``)."""


@dataclass(frozen=True)
class Politica:
    """The limits of one source. VisuaLex's defaults: 3 in flight, 0.5 s apart."""

    concorrenza: int = 3
    intervallo: float = 0.5


#: The limits every source gets unless ``POLITICHE`` names it.
POLITICA = Politica()
#: Per-source exceptions to ``POLITICA`` (none today).
POLITICHE: dict[str, Politica] = {}

#: Circuit breaker: consecutive failures that open it, and how long it stays open.
SOGLIA_GUASTI = 3
SOSPENSIONE = 300.0


def politica(fonte: str) -> Politica:
    return POLITICHE.get(fonte, POLITICA)


def interruttore_attivo() -> bool:
    """The circuit breaker is opt-in: ``LEGAL_CIRCUIT_BREAKER=on`` (read at call time)."""
    return os.environ.get("LEGAL_CIRCUIT_BREAKER", "").strip().lower() in {"on", "1", "true", "yes"}


def async_client(fonte: str, **kwargs) -> httpx.AsyncClient:
    """A new ``httpx.AsyncClient`` for *fonte*, built with *kwargs* plus the guards and limits.

    Without an injected factory the client is ``httpx.AsyncClient(**kwargs)``
    (looked up at call time, so tests that patch ``httpx.AsyncClient`` still see
    every client) with the host guard first in its ``request`` hooks and the
    limits around its transports. With a factory, the factory gets the same
    kwargs (the guard among the hooks) and the guards in ``GUARDIE`` are
    re-applied to what it returns, so no factory can switch them off.
    """
    if fonte not in HOST_PER_FONTE:
        raise ValueError(f"unknown source {fonte!r}: add it to HOST_PER_FONTE")
    kwargs = _con_guardia_host(fonte, kwargs)
    factory = _config.attuale().client_factory
    if factory is None:
        client = httpx.AsyncClient(**kwargs)
        if isinstance(client, _ASYNC_CLIENT):  # a test may patch the class with a stand-in
            _avvolgi_trasporti(client, fonte)
        return client
    client = factory(fonte, **kwargs)
    _riapplica_guardie(client, kwargs)
    return client


def con_regole(fonte: str, transport: httpx.AsyncBaseTransport) -> httpx.AsyncBaseTransport:
    """*transport* with the limits of *fonte* around it: for a ``client_factory`` that builds its own."""
    return _TrasportoConRegole(fonte, transport)


# ---------------------------------------------------------------------------
# Guard: the host each request names
# ---------------------------------------------------------------------------

def _con_guardia_host(fonte: str, kwargs: dict) -> dict:
    hooks = {kind: list(fns) for kind, fns in (kwargs.get("event_hooks") or {}).items()}
    hooks["request"] = [_guardia_host(fonte), *hooks.get("request", [])]
    return {**kwargs, "event_hooks": hooks}


def _guardia_host(fonte: str):
    async def guardia(request: httpx.Request) -> None:
        motivo = motivo_rifiuto_host(fonte, request.url)
        if motivo:
            raise HostNonConsentito(f"{fonte}: {motivo} ({str(request.url)[:120]})", request=request)

    guardia.fonte = fonte  # type: ignore[attr-defined]
    return guardia


def motivo_rifiuto_host(fonte: str, url: httpx.URL) -> str | None:
    """Why *fonte* may not send a request to *url*; ``None`` when it may."""
    if url.scheme not in ("http", "https"):
        return f"schema non consentito: {url.scheme!r}"
    if url.userinfo:
        return "credenziali nell'URL"
    if fonte == "brocardi":
        from mcp_legal_it.lib import _brocardi_switch

        if not _brocardi_switch.enabled():
            return "Brocardi è disattivato"
    ammessi = HOST_PER_FONTE.get(fonte, frozenset())
    if ammessi is not None and url.host not in ammessi:
        return f"host non previsto per la fonte: {url.host!r}"
    return None


def _riapplica_guardie(client, kwargs: dict) -> None:
    hooks = kwargs.get("event_hooks") or {}
    vieta_redirect = kwargs.get("follow_redirects") is False
    if not hooks and not vieta_redirect:
        return
    if not isinstance(client, _ASYNC_CLIENT):
        raise TypeError("client_factory must return an httpx.AsyncClient")
    if hooks:
        attuali = {kind: list(fns) for kind, fns in client.event_hooks.items()}
        for kind, guardie in hooks.items():
            altri = [fn for fn in attuali.get(kind, []) if fn not in guardie]
            attuali[kind] = list(guardie) + altri
        client.event_hooks = attuali
    if vieta_redirect:
        client.follow_redirects = False


# ---------------------------------------------------------------------------
# Limits: concurrency, interval, «not before», circuit breaker
# ---------------------------------------------------------------------------

def _avvolgi_trasporti(client: httpx.AsyncClient, fonte: str) -> None:
    """Put the limits around the client's transport and its proxy mounts.

    httpx exposes no public way to wrap the transports of a client built from
    kwargs (``transport=`` would drop ``verify`` and the environment's proxies),
    so this reaches ``_transport`` and ``_mounts``; ``tests/unit/test_http_rules.py``
    fails if a new httpx renames them.
    """
    client._transport = _TrasportoConRegole(fonte, client._transport)
    client._mounts = {
        pattern: (None if t is None else _TrasportoConRegole(fonte, t)) for pattern, t in client._mounts.items()
    }


@dataclass
class _StatoFonte:
    non_prima: float = 0.0  # monotonic time before which no request goes to the source
    guasti: int = 0
    aperto_da: float | None = None  # monotonic time the breaker opened
    prova_in_corso: bool = False
    ultima: float = 0.0  # monotonic time the last request to the source started


@dataclass
class _StatoCiclo:
    """What must be bound to one event loop: the semaphores and the interval locks."""

    semafori: dict[str, asyncio.Semaphore] = field(default_factory=dict)
    lucchetti: dict[str, asyncio.Lock] = field(default_factory=dict)


_stato: dict[str, _StatoFonte] = {}
_per_ciclo: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _StatoCiclo]" = weakref.WeakKeyDictionary()


def _azzera_stato() -> None:
    """Forget every pause, failure count and interval (tests)."""
    _stato.clear()
    _per_ciclo.clear()


def _fonte(fonte: str) -> _StatoFonte:
    return _stato.setdefault(fonte, _StatoFonte())


def _ciclo() -> _StatoCiclo:
    loop = asyncio.get_running_loop()
    stato = _per_ciclo.get(loop)
    if stato is None:
        stato = _per_ciclo[loop] = _StatoCiclo()
    return stato


def pausa_dichiarata(headers: httpx.Headers | dict) -> float | None:
    """The pause a ``Retry-After`` states, in seconds (number or HTTP date); ``None`` when absent or unreadable."""
    valore = (headers.get("Retry-After") or "").strip()
    if not valore:
        return None
    try:
        secondi = float(valore)
    except ValueError:
        pass
    else:
        # «inf», «nan» or «1e400» would hold the source for ever: not a statement we can honour.
        return min(max(0.0, secondi), PAUSA_MASSIMA) if math.isfinite(secondi) else None
    try:
        quando = email.utils.parsedate_to_datetime(valore)
    except (TypeError, ValueError):
        return None
    if quando is None or quando.tzinfo is None:
        return None
    return min(max(0.0, quando.timestamp() - time.time()), PAUSA_MASSIMA)


class _TrasportoConRegole(httpx.AsyncBaseTransport):
    def __init__(self, fonte: str, interno: httpx.AsyncBaseTransport) -> None:
        self.fonte = fonte
        self.interno = interno

    def _chiave(self, request: httpx.Request) -> str:
        """Whose limits a request counts against: the source, or for a source with no host list its host."""
        if HOST_PER_FONTE.get(self.fonte) is None:
            return f"{self.fonte}@{request.url.host}"
        return self.fonte

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        chiave = self._chiave(request)
        stato = _fonte(chiave)
        await self._attendi_pausa(stato, request)
        prova = self._ammetti(stato, request)
        esito_dato = False
        try:
            regole = politica(self.fonte)
            ciclo = _ciclo()
            semaforo = ciclo.semafori.setdefault(chiave, asyncio.Semaphore(max(1, regole.concorrenza)))
            await semaforo.acquire()
            rilasciato = False
            try:
                await self._attendi_pausa(stato, request)  # a pause may have started while we queued
                await self._rispetta_intervallo(chiave, stato, ciclo, regole)
                try:
                    response = await self.interno.handle_async_request(request)
                except httpx.TransportError:
                    self._esito(stato, prova, guasto=True)
                    esito_dato = True
                    raise
                self._registra_pausa(stato, response)
                self._esito(stato, prova, guasto=response.status_code >= 500 or response.status_code == 429)
                esito_dato = True
                if not response.is_closed:
                    # The body is still to come from the network: the slot goes with it.
                    response.stream = _FlussoCheRilascia(response.stream, semaforo)
                    rilasciato = True
                return response
            finally:
                if not rilasciato:
                    semaforo.release()
        finally:
            if not esito_dato:
                # Cancelled, refused for a pause or a local bug: no outcome, but a
                # half-open trial must not stay «in progress» for ever.
                self._esito(stato, prova, guasto=None)

    async def aclose(self) -> None:
        await self.interno.aclose()

    async def _attendi_pausa(self, stato: _StatoFonte, request: httpx.Request) -> None:
        resta = stato.non_prima - time.monotonic()
        if resta > MAX_ATTESA_PAUSA:
            raise FontePausata(
                f"{self.fonte}: la fonte ha chiesto di attendere ancora {round(resta)} s",
                retry_after=resta,
                request=request,
            )
        if resta > 0:
            await asyncio.sleep(resta)

    async def _rispetta_intervallo(self, chiave: str, stato: _StatoFonte, ciclo: _StatoCiclo,
                                   regole: Politica) -> None:
        if regole.intervallo <= 0:
            stato.ultima = time.monotonic()
            return
        lucchetto = ciclo.lucchetti.setdefault(chiave, asyncio.Lock())
        async with lucchetto:
            attesa = stato.ultima + regole.intervallo - time.monotonic()
            if attesa > 0:
                await asyncio.sleep(attesa)
            stato.ultima = time.monotonic()

    def _registra_pausa(self, stato: _StatoFonte, response: httpx.Response) -> None:
        if response.status_code not in STATI_LIMITE:
            return
        pausa = pausa_dichiarata(response.headers)
        if pausa is None:
            return
        fino = time.monotonic() + pausa
        if fino > stato.non_prima:
            stato.non_prima = fino

    def _ammetti(self, stato: _StatoFonte, request: httpx.Request) -> bool:
        """Whether the circuit breaker lets the request through; True when it is the half-open trial."""
        if not interruttore_attivo() or stato.aperto_da is None:
            return False
        if time.monotonic() - stato.aperto_da < SOSPENSIONE or stato.prova_in_corso:
            raise FonteSospesa(
                f"{self.fonte}: sospesa dopo {SOGLIA_GUASTI} errori consecutivi", request=request
            )
        stato.prova_in_corso = True
        return True

    def _esito(self, stato: _StatoFonte, prova: bool, *, guasto: bool | None) -> None:
        """Record a request's outcome; ``guasto=None`` (cancelled, a local bug) counts for nothing."""
        if prova:
            stato.prova_in_corso = False
        if guasto is None:
            return
        if not guasto:
            stato.guasti = 0
            stato.aperto_da = None
            return
        stato.guasti += 1
        if interruttore_attivo() and (prova or stato.guasti >= SOGLIA_GUASTI):
            stato.aperto_da = time.monotonic()


class _FlussoCheRilascia(httpx.AsyncByteStream):
    """The response body; the source's slot is released when the body is closed."""

    def __init__(self, interno, semaforo: asyncio.Semaphore) -> None:
        self._interno = interno
        self._semaforo = semaforo
        self._rilasciato = False

    async def __aiter__(self):
        async for parte in self._interno:
            yield parte

    async def aclose(self) -> None:
        try:
            if hasattr(self._interno, "aclose"):
                await self._interno.aclose()
        finally:
            if not self._rilasciato:
                self._rilasciato = True
                self._semaforo.release()
