"""The one place where the libraries open an HTTP client.

Every ``httpx.AsyncClient`` in ``mcp_legal_it.lib`` is made by ``async_client``,
which names the source it is for. Today that buys one thing: a library caller
can hand in its own factory (``Configurazione.client_factory``), to add a cache
or a test transport, and every source keeps the headers, timeouts and TLS
settings it needs.

It is also where the network rules shared with VisuaLex will live (migration
phase, not implemented yet). Two different keys:

* the ``fonte`` name each call site passes keys the per-source limits: maximum
  concurrency, minimum interval between requests, retry budget, and the «not
  before» time read from ``Retry-After`` (capped at 30 s), with per-caller
  overrides. VisuaLex's defaults today: concurrency 3, interval 0.5 s, 4 retries;
* the allowlist stays on HOSTNAMES, because a hostname check is what stops a
  request built from caller input from reaching an internal address (SSRF).
  ``HOST_PER_FONTE`` below maps each source to the hosts it may reach; every
  host is in ``lib/_egress.ALLOWED_HOSTS`` (``tests/unit/test_api.py`` checks both
  directions for the call sites in ``lib/``).
"""

from __future__ import annotations

import httpx

from mcp_legal_it.core import _config

__all__ = ["GUARDIE", "HOST_PER_FONTE", "async_client"]

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
#: ``event_hooks`` carry the request guards (``dpa_probe`` checks every request,
#: redirects included, against private addresses); ``follow_redirects=False`` is
#: a guard too. A factory may add hooks of its own; the library's run first.
GUARDIE = ("event_hooks", "follow_redirects")


def async_client(fonte: str, **kwargs) -> httpx.AsyncClient:
    """A new ``httpx.AsyncClient`` for *fonte*, built with *kwargs*.

    Without an injected factory this is exactly ``httpx.AsyncClient(**kwargs)``
    (looked up at call time, so tests that patch ``httpx.AsyncClient`` still see
    every client). With one, the guards in ``GUARDIE`` are re-applied to what the
    factory returns, so no factory, set for a block or for the whole process,
    can switch them off.
    """
    factory = _config.attuale().client_factory
    if factory is None:
        return httpx.AsyncClient(**kwargs)
    client = factory(fonte, **kwargs)
    _riapplica_guardie(client, kwargs)
    return client


def _riapplica_guardie(client, kwargs: dict) -> None:
    hooks = kwargs.get("event_hooks") or {}
    vieta_redirect = kwargs.get("follow_redirects") is False
    if not hooks and not vieta_redirect:
        return
    if not isinstance(client, httpx.AsyncClient):
        raise TypeError("client_factory must return an httpx.AsyncClient")
    if hooks:
        attuali = {kind: list(fns) for kind, fns in client.event_hooks.items()}
        for kind, guardie in hooks.items():
            altri = [fn for fn in attuali.get(kind, []) if fn not in guardie]
            attuali[kind] = list(guardie) + altri
        client.event_hooks = attuali
    if vieta_redirect:
        client.follow_redirects = False
