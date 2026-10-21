"""The network rules of ``core/_http``: host guard, per-source limits, «not before», circuit breaker.

The cases follow VisuaLex's own tests of the rules they port (VisuaLexAPI
``services/visualex/tests/test_http_client_retries.py``, ``test_circuit_breaker.py``,
``test_egress_allowlist.py`` and ``test_tls_italgiure.py`` at ``eca698dc``, MPL-2.0),
rewritten for httpx: VisuaLex tests an aiohttp client of its own, here the rules
sit in a transport around the client's.
"""

from __future__ import annotations

import asyncio
import email.utils
import time

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.core import _http
from mcp_legal_it.core._http import (
    FontePausata,
    FonteSospesa,
    HostNonConsentito,
    async_client,
    con_regole,
    pausa_dichiarata,
)
from mcp_legal_it.lib import _brocardi_switch, _egress
from mcp_legal_it.lib._http import retry_request

NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241"


class Copione:
    """A server that answers the scripted responses in order, then the last one for ever."""

    def __init__(self, *risposte):
        self.risposte = list(risposte) or [httpx.Response(200, text="ok")]
        self.richieste: list[httpx.Request] = []
        self.inizi: list[float] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.richieste.append(request)
        self.inizi.append(time.monotonic())
        r = self.risposte.pop(0) if len(self.risposte) > 1 else self.risposte[0]
        if callable(r):
            return r(request)
        return httpx.Response(r.status_code, headers=r.headers, content=r.content)


def cliente(fonte: str, copione, **kwargs) -> httpx.AsyncClient:
    """The client the library would build for *fonte*, with *copione* in place of the network."""
    client = async_client(fonte, **kwargs)
    client._transport.interno = httpx.MockTransport(copione)
    return client


# ---------------------------------------------------------------------------
# httpx internals the rules rely on
# ---------------------------------------------------------------------------

class TestAggancio:
    def test_the_default_client_carries_the_rules_on_its_transport_and_proxy_mounts(self, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy.esempio.it:3128")
        client = async_client("normattiva")
        assert isinstance(client._transport, _http._TrasportoConRegole)
        assert client._transport.fonte == "normattiva"
        mounts = [t for t in client._mounts.values() if t is not None]
        assert mounts and all(isinstance(t, _http._TrasportoConRegole) for t in mounts)

    def test_the_tls_context_still_reaches_the_network_transport(self):
        from mcp_legal_it.lib.italgiure.client import tls_context

        client = async_client("italgiure", verify=tls_context())
        pool = client._transport.interno._pool
        assert pool._ssl_context is tls_context()

    def test_an_unknown_source_is_a_programming_error(self):
        with pytest.raises(ValueError):
            async_client("luna")


# ---------------------------------------------------------------------------
# Host guard
# ---------------------------------------------------------------------------

class TestGuardiaHost:
    async def test_a_host_outside_the_source_is_refused_before_it_leaves(self):
        copione = Copione()
        async with cliente("normattiva", copione) as client:
            with pytest.raises(HostNonConsentito):
                await client.get("https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita")
            with pytest.raises(HostNonConsentito):
                await client.get("http://169.254.169.254/latest/meta-data/")
        assert copione.richieste == []

    async def test_a_redirect_to_another_host_is_refused(self):
        copione = Copione(httpx.Response(302, headers={"Location": "http://127.0.0.1:8080/admin"}))
        async with cliente("normattiva", copione, follow_redirects=True) as client:
            with pytest.raises(HostNonConsentito):
                await client.get(NORMATTIVA)
        assert [r.url.host for r in copione.richieste] == ["www.normattiva.it"]

    async def test_a_cellar_redirect_on_the_same_host_passes(self):
        cellar = "http://publications.europa.eu/resource/cellar/3e485e15/DOC_1"
        copione = Copione(httpx.Response(303, headers={"Location": cellar}), httpx.Response(200, text="<html/>"))
        async with cliente("eur_lex", copione, follow_redirects=True) as client:
            r = await client.get("https://publications.europa.eu/resource/celex/32016R0679")
        assert r.status_code == 200 and str(copione.richieste[-1].url) == cellar

    @pytest.mark.parametrize("url", [
        "https://user:pw@www.normattiva.it/",
        "ftp://www.normattiva.it/",
    ])
    async def test_credentials_and_other_schemes_are_refused(self, url):
        with pytest.raises((HostNonConsentito, httpx.UnsupportedProtocol)):
            async with cliente("normattiva", Copione()) as client:
                await client.get(url)

    async def test_brocardi_switched_off_is_refused_at_request_time(self):
        with _brocardi_switch.disabled():
            async with cliente("brocardi", Copione()) as client:
                with pytest.raises(HostNonConsentito):
                    await client.get("https://www.brocardi.it/codice-civile/")

    async def test_the_guard_survives_a_factory_that_drops_every_kwarg(self):
        chiamate = []

        def factory(fonte, **kwargs):
            return httpx.AsyncClient(transport=httpx.MockTransport(lambda r: chiamate.append(r) or httpx.Response(200)))

        with api.configurazione(client_factory=factory):
            async with async_client("italgiure") as client:
                with pytest.raises(HostNonConsentito):
                    await client.get("http://10.0.0.1/")
        assert chiamate == []

    def test_every_source_host_is_on_the_published_allowlist(self):
        for fonte, hosts in _http.HOST_PER_FONTE.items():
            assert hosts is None or hosts <= set(_egress.ALLOWED_HOSTS), fonte


class TestIsAllowed:
    """``lib/_egress.is_allowed`` reads the host as a browser would (VisuaLex's cases)."""

    @pytest.mark.parametrize("url,expected", [
        ("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge", True),
        ("https://eur-lex.europa.eu/eli/reg/2016/679/oj/ita", True),
        ("https://www.normattiva.it.evil.test/phish", False),
        ("http://169.254.169.254/latest/meta-data/", False),
        ("not-a-url", False),
        ("http://169.254.169.254\\@eur-lex.europa.eu/", False),
        ("https://www.normattiva.it\\.evil.test/", False),
        ("http://169.254.169.254\t@eur-lex.europa.eu/", False),
        ("https://user:pw@www.normattiva.it/", False),
        ("ftp://www.normattiva.it/", False),
        ("file://www.normattiva.it/etc/passwd", False),
        ("https://brocardi.it/x", False),
    ])
    def test_is_allowed(self, url, expected):
        assert _egress.is_allowed(url) is expected

    def test_brocardi_follows_its_switch(self):
        assert _egress.is_allowed("https://www.brocardi.it/codice-civile/")
        with _brocardi_switch.disabled():
            assert not _egress.is_allowed("https://www.brocardi.it/codice-civile/")


# ---------------------------------------------------------------------------
# Concurrency and interval
# ---------------------------------------------------------------------------

class TestLimiti:
    async def test_requests_to_a_source_are_spaced_by_the_interval(self, monkeypatch):
        monkeypatch.setattr(_http, "POLITICA", _http.Politica(intervallo=0.1))
        copione = Copione()
        async with cliente("normattiva", copione) as client:
            for _ in range(3):
                await client.get(NORMATTIVA)
        gaps = [b - a for a, b in zip(copione.inizi, copione.inizi[1:])]
        assert all(g >= 0.095 for g in gaps), gaps

    async def test_the_interval_is_per_source(self, monkeypatch):
        monkeypatch.setattr(_http, "POLITICA", _http.Politica(intervallo=0.5))
        normattiva, italgiure = Copione(), Copione()
        t0 = time.monotonic()
        async with cliente("normattiva", normattiva) as a, cliente("italgiure", italgiure) as b:
            await a.get(NORMATTIVA)
            await b.get("https://www.italgiure.giustizia.it/sncass/")
        assert time.monotonic() - t0 < 0.4

    async def test_at_most_three_requests_are_in_flight_to_a_source(self):
        in_volo = massimo = 0

        async def lento(request):
            nonlocal in_volo, massimo
            in_volo += 1
            massimo = max(massimo, in_volo)
            await asyncio.sleep(0.05)
            in_volo -= 1
            return httpx.Response(200, stream=httpx.ByteStream(b"ok"))

        client = async_client("normattiva")
        client._transport.interno = httpx.MockTransport(lento)
        async with client:
            await asyncio.gather(*(client.get(NORMATTIVA) for _ in range(8)))
        assert massimo == 3

    async def test_the_slot_is_held_until_the_body_is_read(self):
        def handler(request):
            # A body still to be read, as the network gives it (text= would arrive already read).
            return httpx.Response(200, stream=httpx.ByteStream(b"ok"))

        client = async_client("normattiva")
        client._transport.interno = httpx.MockTransport(handler)
        async with client:
            async with client.stream("GET", NORMATTIVA) as r:
                assert _http._fonte("normattiva").in_volo == 1
                await r.aread()
            assert _http._fonte("normattiva").in_volo == 0

    async def test_a_failed_request_gives_its_slot_back(self):
        def rotto(request):
            raise httpx.ConnectError("refused", request=request)

        client = async_client("normattiva")
        client._transport.interno = httpx.MockTransport(rotto)
        async with client:
            for _ in range(5):
                with pytest.raises(httpx.ConnectError):
                    await client.get(NORMATTIVA)
        assert _http._fonte("normattiva").in_volo == 0


class TestTraThread:
    """The limits are per process: several threads, each with its own event loop, share them."""

    def test_three_threads_never_exceed_the_cap_nor_the_interval(self, monkeypatch):
        import threading

        monkeypatch.setattr(_http, "POLITICA", _http.Politica(concorrenza=3, intervallo=0.05))
        lock = threading.Lock()
        in_volo = massimo = 0
        # The start times the limiter reserves (``_prendi_posto``, under its lock). The
        # interval is checked on them, not on when the transport ran: a loaded machine
        # (a CI runner, a suite next to live measures) can wake a thread late, and a
        # late wake-up is not two requests closer than the interval.
        riservati: list[float] = []

        class _Spia(_http._StatoFonte):
            def __setattr__(self, nome, valore):
                if nome == "ultima" and valore:
                    riservati.append(valore)
                super().__setattr__(nome, valore)

        with _http._LOCK:
            _http._stato["normattiva"] = _Spia()

        async def lento(request):
            nonlocal in_volo, massimo
            with lock:
                in_volo += 1
                massimo = max(massimo, in_volo)
            await asyncio.sleep(0.1)
            with lock:
                in_volo -= 1
            return httpx.Response(200, stream=httpx.ByteStream(b"ok"))

        async def lavora():
            client = async_client("normattiva")
            client._transport.interno = httpx.MockTransport(lento)
            async with client:
                await asyncio.gather(*(client.get(NORMATTIVA) for _ in range(4)))

        threads = [threading.Thread(target=lambda: asyncio.run(lavora())) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert len(riservati) == 12
        assert massimo <= 3
        riservati.sort()
        assert all(b - a >= 0.05 - 1e-9 for a, b in zip(riservati, riservati[1:])), riservati
        assert _http._fonte("normattiva").in_volo == 0


# ---------------------------------------------------------------------------
# Retry-After: the «not before» pause
# ---------------------------------------------------------------------------

class TestPausa:
    async def test_the_next_request_waits_out_a_stated_retry_after(self):
        copione = Copione(httpx.Response(429, headers={"Retry-After": "0.3"}), httpx.Response(200, text="ok"))
        async with cliente("italgiure", copione) as client:
            r = await client.get("https://www.italgiure.giustizia.it/sncass/")
            assert r.status_code == 429
            t0 = time.monotonic()
            r = await client.get("https://www.italgiure.giustizia.it/sncass/")
        assert r.status_code == 200 and time.monotonic() - t0 >= 0.25

    async def test_the_pause_holds_every_client_of_the_source_and_only_that_source(self):
        async with cliente("italgiure", Copione(httpx.Response(503, headers={"Retry-After": "0.3"}))) as a:
            await a.get("https://www.italgiure.giustizia.it/sncass/")
        t0 = time.monotonic()
        async with cliente("normattiva", Copione()) as altra:
            await altra.get(NORMATTIVA)
        assert time.monotonic() - t0 < 0.2
        async with cliente("italgiure", Copione()) as b:
            await b.get("https://www.italgiure.giustizia.it/sncass/")
        assert time.monotonic() - t0 >= 0.25

    async def test_our_own_backoff_does_not_pause_the_source(self):
        async with cliente("normattiva", Copione(httpx.Response(503))) as client:
            await client.get(NORMATTIVA)
        assert _http._fonte("normattiva").non_prima == 0.0

    async def test_a_long_retry_after_holds_the_source_only_up_to_the_cap(self, monkeypatch):
        """A 503 announcing an hour of maintenance: the others wait the cap, not the hour."""
        monkeypatch.setattr(_http, "MAX_ATTESA_PAUSA", 0.3)
        copione = Copione(httpx.Response(503, headers={"Retry-After": "3600"}), httpx.Response(200, text="ok"))
        async with cliente("italgiure", copione) as client:
            await client.get("https://www.italgiure.giustizia.it/sncass/")
            t0 = time.monotonic()
            r = await client.get("https://www.italgiure.giustizia.it/sncass/")  # the site is back
        assert r.status_code == 200 and 0.25 <= time.monotonic() - t0 < 1.0
        assert len(copione.richieste) == 2

    @pytest.mark.parametrize("valore", ["inf", "Infinity", "1e400", "nan"])
    def test_a_retry_after_that_is_not_finite_is_ignored(self, valore):
        assert pausa_dichiarata(httpx.Headers({"Retry-After": valore})) is None

    def test_the_statement_is_read_as_given_and_capped_only_when_recorded(self):
        assert pausa_dichiarata(httpx.Headers({"Retry-After": "3600"})) == 3600.0

    async def test_an_infinite_retry_after_does_not_hold_the_source(self):
        copione = Copione(httpx.Response(429, headers={"Retry-After": "inf"}), httpx.Response(200, text="ok"))
        async with cliente("italgiure", copione) as client:
            await client.get("https://www.italgiure.giustizia.it/sncass/")
            assert (await client.get("https://www.italgiure.giustizia.it/sncass/")).status_code == 200

    async def test_a_source_without_a_host_list_is_paused_per_host(self, monkeypatch):
        monkeypatch.setattr(_http, "MAX_ATTESA_PAUSA", 0.3)

        def handler(request):
            if request.url.host == "lento.example.com":
                return httpx.Response(429, headers={"Retry-After": "120"})
            return httpx.Response(200, text="ok")

        async with cliente("dpa_probe", handler) as client:
            await client.get("https://lento.example.com/")
            t0 = time.monotonic()
            assert (await client.get("https://altro.example.com/legal/dpa")).status_code == 200
            assert time.monotonic() - t0 < 0.2  # another vendor is not held
            await client.get("https://lento.example.com/legal/dpa")
            assert time.monotonic() - t0 >= 0.25  # the slow one waited its pause

    def test_retry_after_as_an_http_date(self):
        fra_dieci = email.utils.formatdate(time.time() + 10, usegmt=True)
        assert 8 <= pausa_dichiarata(httpx.Headers({"Retry-After": fra_dieci})) <= 10
        assert pausa_dichiarata(httpx.Headers({"Retry-After": "domani"})) is None
        assert pausa_dichiarata(httpx.Headers({})) is None
        assert pausa_dichiarata(httpx.Headers({"Retry-After": "-5"})) == 0.0


# ---------------------------------------------------------------------------
# retry_request on top of the rules
# ---------------------------------------------------------------------------

class TestRetryRequest:
    async def test_a_429_is_retried_after_the_stated_wait(self):
        copione = Copione(httpx.Response(429, headers={"Retry-After": "0.2"}), httpx.Response(200, text="ok"))
        async with cliente("italgiure", copione) as client:
            t0 = time.monotonic()
            r = await retry_request(client, "GET", "https://www.italgiure.giustizia.it/sncass/", backoff_base=0.01)
        assert r.status_code == 200 and len(copione.richieste) == 2 and time.monotonic() - t0 >= 0.18

    async def test_a_stated_wait_over_the_limit_ends_the_call_without_retrying(self):
        copione = Copione(httpx.Response(503, headers={"Retry-After": "3600"}))
        async with cliente("italgiure", copione) as client:
            t0 = time.monotonic()
            with pytest.raises(FontePausata) as err:
                await retry_request(client, "GET", "https://www.italgiure.giustizia.it/sncass/", backoff_base=0.01)
        assert len(copione.richieste) == 1 and time.monotonic() - t0 < 0.1
        assert err.value.retry_after == 3600 and "3600 s" in str(err.value)
        # The source is held for the cap at most, never the hour it announced.
        assert _http._fonte("italgiure").non_prima - time.monotonic() <= _http.MAX_ATTESA_PAUSA

    async def test_a_spent_budget_gives_up_without_sleeping_through_retry_after(self):
        copione = Copione(httpx.Response(503, headers={"Retry-After": "20"}))
        async with cliente("italgiure", copione) as client:
            t0 = time.monotonic()
            with pytest.raises(httpx.HTTPStatusError):
                await retry_request(client, "GET", "https://www.italgiure.giustizia.it/sncass/", max_retries=0)
        assert time.monotonic() - t0 < 0.1
        # The pause is not lost: it holds the source's next request.
        assert _http._fonte("italgiure").non_prima - time.monotonic() > 15

    async def test_a_local_refusal_is_never_retried(self):
        copione = Copione()
        async with cliente("normattiva", copione) as client:
            with pytest.raises(HostNonConsentito):
                await retry_request(client, "GET", "https://eur-lex.europa.eu/", backoff_base=0.01)
        assert copione.richieste == []

    async def test_a_404_is_not_retried(self):
        copione = Copione(httpx.Response(404))
        async with cliente("normattiva", copione) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await retry_request(client, "GET", NORMATTIVA, backoff_base=0.01)
        assert len(copione.richieste) == 1


# ---------------------------------------------------------------------------
# Circuit breaker (opt-in)
# ---------------------------------------------------------------------------

class TestInterruttore:
    async def _fallisci(self, client, n, url=NORMATTIVA):
        for _ in range(n):
            await client.get(url)

    async def test_off_by_default(self):
        copione = Copione(httpx.Response(500))
        async with cliente("normattiva", copione) as client:
            await self._fallisci(client, 6)
        assert len(copione.richieste) == 6

    async def test_opens_after_three_failures_and_refuses_the_source(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")
        copione = Copione(httpx.Response(500))
        async with cliente("normattiva", copione) as client:
            await self._fallisci(client, 3)
            with pytest.raises(FonteSospesa):
                await client.get(NORMATTIVA)
        assert len(copione.richieste) == 3
        async with cliente("italgiure", Copione()) as altra:
            assert (await altra.get("https://www.italgiure.giustizia.it/sncass/")).status_code == 200

    async def test_a_404_or_another_4xx_never_counts(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")
        copione = Copione(httpx.Response(404), httpx.Response(404), httpx.Response(400), httpx.Response(404))
        async with cliente("normattiva", copione) as client:
            await self._fallisci(client, 4)
        assert _http._fonte("normattiva").aperto_da is None

    async def test_429_and_network_errors_count(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")

        def rotto(request):
            raise httpx.ConnectTimeout("timeout", request=request)

        copione = Copione(httpx.Response(429), rotto, rotto)
        async with cliente("normattiva", copione) as client:
            await client.get(NORMATTIVA)
            for _ in range(2):
                with pytest.raises(httpx.ConnectTimeout):
                    await client.get(NORMATTIVA)
        assert _http._fonte("normattiva").aperto_da is not None

    async def test_a_success_resets_the_count(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")
        copione = Copione(httpx.Response(500), httpx.Response(500), httpx.Response(200), httpx.Response(500),
                          httpx.Response(500), httpx.Response(200))
        async with cliente("normattiva", copione) as client:
            await self._fallisci(client, 6)
        assert _http._fonte("normattiva").aperto_da is None

    async def test_after_the_cooldown_one_trial_decides(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")
        copione = Copione(httpx.Response(500), httpx.Response(500), httpx.Response(500), httpx.Response(200))
        async with cliente("normattiva", copione) as client:
            await self._fallisci(client, 3)
            _http._fonte("normattiva").aperto_da -= _http.SOSPENSIONE + 1
            assert (await client.get(NORMATTIVA)).status_code == 200
            assert (await client.get(NORMATTIVA)).status_code == 200

    async def test_a_failed_trial_opens_it_again(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")
        copione = Copione(httpx.Response(500))
        async with cliente("normattiva", copione) as client:
            await self._fallisci(client, 3)
            _http._fonte("normattiva").aperto_da -= _http.SOSPENSIONE + 1
            await client.get(NORMATTIVA)
            with pytest.raises(FonteSospesa):
                await client.get(NORMATTIVA)

    async def test_a_cancelled_trial_does_not_keep_the_source_suspended(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")

        async def appeso(request):
            await asyncio.sleep(10)
            return httpx.Response(200)

        client = async_client("normattiva")
        client._transport.interno = httpx.MockTransport(appeso)
        stato = _http._fonte("normattiva")
        stato.guasti, stato.aperto_da = 3, time.monotonic() - _http.SOSPENSIONE - 1
        async with client:
            prova = asyncio.create_task(client.get(NORMATTIVA))
            await asyncio.sleep(0.02)
            prova.cancel()
            with pytest.raises(asyncio.CancelledError):
                await prova
            client._transport.interno = httpx.MockTransport(lambda r: httpx.Response(200))
            assert (await client.get(NORMATTIVA)).status_code == 200  # a new trial is admitted
        assert stato.aperto_da is None and stato.in_volo == 0

    async def test_a_trial_cancelled_before_it_leaves_does_not_keep_the_source_suspended(self, monkeypatch):
        """Cancelled while it waits for the interval: it never reached the network."""
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")
        monkeypatch.setattr(_http, "POLITICA", _http.Politica(intervallo=0.5))
        client = cliente("normattiva", Copione())
        stato = _http._fonte("normattiva")
        stato.guasti, stato.aperto_da = 3, time.monotonic() - _http.SOSPENSIONE - 1
        stato.ultima = time.monotonic()  # the trial must wait the interval first
        async with client:
            prova = asyncio.create_task(client.get(NORMATTIVA))
            await asyncio.sleep(0.05)
            assert stato.prova_in_corso
            prova.cancel()
            with pytest.raises(asyncio.CancelledError):
                await prova
            assert not stato.prova_in_corso
            assert (await client.get(NORMATTIVA)).status_code == 200  # a new trial is admitted
        assert stato.aperto_da is None

    async def test_only_one_trial_at_a_time(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CIRCUIT_BREAKER", "on")

        async def lento(request):
            await asyncio.sleep(0.05)
            return httpx.Response(200)

        client = async_client("normattiva")
        client._transport.interno = httpx.MockTransport(lento)
        stato = _http._fonte("normattiva")
        stato.guasti, stato.aperto_da = 3, time.monotonic() - _http.SOSPENSIONE - 1
        async with client:
            esiti = await asyncio.gather(*(client.get(NORMATTIVA) for _ in range(3)), return_exceptions=True)
        assert sum(isinstance(e, FonteSospesa) for e in esiti) == 2


# ---------------------------------------------------------------------------
# A factory that wants the limits under its own cache
# ---------------------------------------------------------------------------

async def test_con_regole_puts_the_limits_under_a_factory_cache(monkeypatch):
    monkeypatch.setattr(_http, "POLITICA", _http.Politica(intervallo=0.2))
    rete = Copione()
    cache: dict = {}

    class Cache(httpx.AsyncBaseTransport):
        def __init__(self, sotto):
            self.sotto = sotto

        async def handle_async_request(self, request):
            key = str(request.url)
            if key not in cache:
                r = await self.sotto.handle_async_request(request)
                cache[key] = await r.aread()
                await r.aclose()
            return httpx.Response(200, content=cache[key])

    def factory(fonte, **kwargs):
        return httpx.AsyncClient(transport=Cache(con_regole(fonte, httpx.MockTransport(rete))),
                                 event_hooks=kwargs.get("event_hooks"))

    with api.configurazione(client_factory=factory):
        async with async_client("normattiva") as client:
            await client.get(NORMATTIVA)
            t0 = time.monotonic()
            for _ in range(5):
                await client.get(NORMATTIVA)  # cache hits: no interval to wait
    assert len(rete.richieste) == 1 and time.monotonic() - t0 < 0.1
