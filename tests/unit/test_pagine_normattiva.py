"""The HTML channel's page cache, and the shared lookup of an act's full date."""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import pagine_normattiva as pn
from mcp_legal_it.lib.visualex import scraper
from mcp_legal_it.lib.visualex.models import Norma

URL = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043"


class TestCachePagine:
    def test_a_record_is_read_back_from_memory_and_disk(self):
        pn.scrivi(URL, "Art. 2043. testo", "2043")
        assert pn.leggi(URL)["testo"] == "Art. 2043. testo"
        pn.svuota_memoria()
        rec = pn.leggi(URL)
        assert rec["testo"] == "Art. 2043. testo" and rec["servito"] == "2043"

    def test_a_record_older_than_a_day_is_not_read_and_is_deleted(self, monkeypatch):
        pn.scrivi(URL, "vecchio", "2043")
        pn.svuota_memoria()
        dopo = time.time() + pn.TTL_SECONDI + 1
        monkeypatch.setattr(pn.time, "time", lambda: dopo)
        assert pn.leggi(URL) is None
        assert not list(pn._dir().glob("*.json"))

    def test_another_url_or_schema_is_not_read(self):
        pn.scrivi(URL, "testo", "2043")
        pn.svuota_memoria()
        path = next(pn._dir().glob("*.json"))
        rec = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps({**rec, "schema": pn.SCHEMA + 1}), encoding="utf-8")
        assert pn.leggi(URL) is None

    def test_cache_off_writes_nothing_to_disk(self, monkeypatch):
        monkeypatch.setenv("LEGAL_CACHE", "off")
        pn.scrivi(URL, "testo", "2043")
        assert pn.leggi(URL)["testo"] == "testo"  # memory still serves the process
        assert not pn._dir().exists()

    def test_the_disk_is_capped_oldest_first(self, monkeypatch):
        monkeypatch.setattr(pn, "MAX_SU_DISCO", 3)
        monkeypatch.setattr(pn, "OGNI_QUANTE_SCRITTURE", 1)
        for i in range(5):
            pn.scrivi(f"{URL}#{i}", f"t{i}", None)
            time.sleep(0.01)
        assert len(list(pn._dir().glob("*.json"))) == 3
        pn.svuota_memoria()
        assert pn.leggi(f"{URL}#0") is None and pn.leggi(f"{URL}#4")["testo"] == "t4"


class TestDataCompletaCondivisa:
    async def test_articles_of_one_year_only_act_asked_at_once_share_one_request(self, monkeypatch):
        monkeypatch.setattr(scraper, "_full_date_cache", {})
        chieste = []

        async def handler(request):
            chieste.append(str(request.url))
            await asyncio.sleep(0.05)
            return httpx.Response(200, text='<html><head><meta property="eli:date_document" '
                                             'content="1990-08-07"></head></html>')

        def factory(fonte, **kwargs):
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        with api.configurazione(client_factory=factory):
            norme = await asyncio.gather(*(scraper.with_full_date(Norma("legge", "1990", "241")) for _ in range(3)))
        assert [n.data for n in norme] == ["1990-08-07"] * 3
        assert len(chieste) == 1

    async def test_a_failed_shared_lookup_fails_for_every_waiter_and_is_not_kept(self, monkeypatch):
        monkeypatch.setattr(scraper, "_full_date_cache", {})

        async def handler(request):
            await asyncio.sleep(0.02)
            return httpx.Response(503)

        def factory(fonte, **kwargs):
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        with api.configurazione(client_factory=factory):
            norme = await asyncio.gather(*(scraper.with_full_date(Norma("legge", "1990", "241")) for _ in range(3)))
        assert [n.data for n in norme] == ["1990"] * 3  # never guessed
        assert scraper._date_in_corso == {} and scraper._full_date_cache == {}


async def test_a_cancelled_leader_does_not_cancel_the_waiters(monkeypatch):
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    iniziata = asyncio.Event()

    async def handler(request):
        iniziata.set()
        await asyncio.sleep(10)
        return httpx.Response(200, text="")

    def factory(fonte, **kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    with api.configurazione(client_factory=factory):
        capo = asyncio.create_task(scraper.with_full_date(Norma("legge", "1990", "241")))
        await iniziata.wait()
        altro = asyncio.create_task(scraper.with_full_date(Norma("legge", "1990", "241")))
        await asyncio.sleep(0.01)
        capo.cancel()
        with pytest.raises(asyncio.CancelledError):
            await capo
        norma = await altro  # not cancelled: a lookup that failed, the year kept
    assert not altro.cancelled() and norma.data == "1990"
