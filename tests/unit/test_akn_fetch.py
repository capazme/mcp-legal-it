"""Unit tests for the AKN network/cache layer (src/lib/visualex/akn_fetch.py).

Network is fully mocked: a fake ``httpx.AsyncClient`` is injected via monkeypatch
and records every GET so we can assert on round-trip counts. No live calls.
"""

import json
from pathlib import Path

import pytest

from src.lib.visualex import akn_fetch
from src.lib.visualex.akn_fetch import (
    _akn_cache_stats,
    _extract_params,
    clear_akn_cache,
    fetch_act_akn,
)
from src.lib.visualex.akn_parser import ParsedAct
from src.lib.visualex.models import Norma

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "akn"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fake httpx client
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200, url: str = ""):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("httpx").HTTPStatusError(
                "error", request=None, response=None
            )


class _FakeClient:
    """Async-context-manager stand-in for httpx.AsyncClient.

    ``routes`` maps a substring of the requested URL to the response text.
    Every GET is recorded in the shared ``calls`` list.
    """

    def __init__(self, routes: dict, calls: list, **kwargs):
        self._routes = routes
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        self._calls.append(url)
        for needle, text in self._routes.items():
            if needle in url:
                return _FakeResponse(text, url=url)
        return _FakeResponse("", status_code=404, url=url)


def _install_client(monkeypatch, routes: dict) -> list:
    """Patch httpx.AsyncClient with a fake; return the shared call log."""
    calls: list = []

    def factory(*args, **kwargs):
        return _FakeClient(routes, calls, **kwargs)

    monkeypatch.setattr(akn_fetch.httpx, "AsyncClient", factory)
    return calls


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Each test gets a clean in-memory LRU and an isolated on-disk cache dir."""
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    clear_akn_cache(disk=True)
    yield
    clear_akn_cache(disk=True)


# ---------------------------------------------------------------------------
# Param extraction
# ---------------------------------------------------------------------------

class TestParamExtraction:
    def test_from_landing_fixture(self):
        html = _load("landing_legge_241_1990.html")
        params = _extract_params(html)
        assert params == ("090G0294", "19900818")

    def test_fallback_eli_and_datapub(self):
        html = (
            'foo <meta property="eli:id_local" content="090G0294" /> bar '
            "baz dataPubblicazioneGazzetta=1990-08-18 qux"
        )
        assert _extract_params(html) == ("090G0294", "19900818")

    def test_no_params_returns_none(self):
        assert _extract_params("<html>nothing useful here</html>") is None

    def test_missing_data_gu_returns_none(self):
        html = '<meta property="eli:id_local" content="090G0294" />'
        assert _extract_params(html) is None


# ---------------------------------------------------------------------------
# fetch_act_akn — happy path
# ---------------------------------------------------------------------------

class TestFetchHappyPath:
    @pytest.fixture
    def norma(self):
        return Norma(tipo_atto="legge", data="1990", numero_atto="241")

    @pytest.fixture
    def routes(self):
        return {
            "uri-res": _load("landing_legge_241_1990.html"),
            "caricaAKN": _load("legge_241_1990.xml"),
        }

    async def test_returns_parsed_act(self, monkeypatch, norma, routes):
        _install_client(monkeypatch, routes)
        act = await fetch_act_akn(norma, data_vigenza="20260614")
        assert isinstance(act, ParsedAct)
        assert act.structure == "flat"
        assert act.article_count == 51
        assert act.article("3") is not None

    async def test_two_network_calls_on_cold_fetch(self, monkeypatch, norma, routes):
        calls = _install_client(monkeypatch, routes)
        await fetch_act_akn(norma, data_vigenza="20260614")
        assert len(calls) == 2  # landing + caricaAKN
        assert any("caricaAKN" in c for c in calls)


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

class TestCaching:
    @pytest.fixture
    def norma(self):
        return Norma(tipo_atto="legge", data="1990", numero_atto="241")

    @pytest.fixture
    def routes(self):
        return {
            "uri-res": _load("landing_legge_241_1990.html"),
            "caricaAKN": _load("legge_241_1990.xml"),
        }

    async def test_second_call_skips_all_network(self, monkeypatch, norma, routes):
        calls = _install_client(monkeypatch, routes)
        await fetch_act_akn(norma, data_vigenza="20260614")
        first_count = len(calls)
        assert first_count == 2  # cold: landing + caricaAKN

        act2 = await fetch_act_akn(norma, data_vigenza="20260614")
        # Warm: the act URL -> params index lets us resolve the cache key with NO
        # network at all — not even the landing page. No session is needed when we
        # answer from cache without calling caricaAKN.
        assert act2 is not None
        assert len(calls) == first_count  # zero new round-trips

    async def test_memory_cache_populated(self, monkeypatch, norma, routes):
        _install_client(monkeypatch, routes)
        await fetch_act_akn(norma, data_vigenza="20260614")
        stats = _akn_cache_stats()
        assert stats["memory_entries"] == 1
        assert ("090G0294", "19900818", "20260614") in stats["memory_keys"]

    async def test_lru_eviction_at_max(self, monkeypatch, norma, routes):
        _install_client(monkeypatch, routes)
        # Force the LRU to size 1 for the duration of this test.
        monkeypatch.setattr(akn_fetch, "_CACHE_MAX", 1)

        await fetch_act_akn(norma, data_vigenza="20260101")
        await fetch_act_akn(norma, data_vigenza="20260202")  # different key

        stats = _akn_cache_stats()
        assert stats["memory_entries"] == 1
        # The most recent key survives; the older one is evicted.
        assert ("090G0294", "19900818", "20260202") in stats["memory_keys"]
        assert ("090G0294", "19900818", "20260101") not in stats["memory_keys"]


# ---------------------------------------------------------------------------
# On-disk round trip
# ---------------------------------------------------------------------------

class TestDiskPersistence:
    @pytest.fixture
    def norma(self):
        return Norma(tipo_atto="legge", data="1990", numero_atto="241")

    @pytest.fixture
    def routes(self):
        return {
            "uri-res": _load("landing_legge_241_1990.html"),
            "caricaAKN": _load("legge_241_1990.xml"),
        }

    async def test_disk_round_trip(self, monkeypatch, tmp_path, norma, routes):
        _install_client(monkeypatch, routes)
        await fetch_act_akn(norma, data_vigenza="20260614")

        # The parsed act is on disk.
        disk_dir = tmp_path / "cache" / "akn_acts"
        files = list(disk_dir.glob("090G0294_19900818_20260614.json"))
        assert len(files) == 1
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        assert payload["structure"] == "flat"
        assert len(payload["articles"]) == 51

        # Drop the in-memory LRU; the next fetch must hit disk, not caricaAKN.
        clear_akn_cache(disk=False)
        calls = _install_client(monkeypatch, routes)
        act = await fetch_act_akn(norma, data_vigenza="20260614")
        assert act is not None
        assert act.article_count == 51
        assert not any("caricaAKN" in c for c in calls)

    async def test_hit_counter_written(self, monkeypatch, tmp_path, norma, routes):
        _install_client(monkeypatch, routes)
        await fetch_act_akn(norma, data_vigenza="20260614")
        await fetch_act_akn(norma, data_vigenza="20260614")  # cache hit, +1

        hits_file = tmp_path / "cache" / "akn_acts" / "akn_hits.json"
        assert hits_file.exists()
        hits = json.loads(hits_file.read_text(encoding="utf-8"))
        assert hits["090G0294|19900818|20260614"] == 2


# ---------------------------------------------------------------------------
# Failure paths → None
# ---------------------------------------------------------------------------

class TestFailures:
    @pytest.fixture
    def norma(self):
        return Norma(tipo_atto="legge", data="1990", numero_atto="241")

    async def test_error_page_returns_none(self, monkeypatch, norma):
        # caricaAKN returns the 32254-byte HTML error page (not XML).
        wrapper = "<html><body>" + "</body></html>"
        error_page = "<html><body>" + ("x" * (32254 - len(wrapper))) + "</body></html>"
        assert len(error_page) == 32254
        routes = {
            "uri-res": _load("landing_legge_241_1990.html"),
            "caricaAKN": error_page,
        }
        _install_client(monkeypatch, routes)
        act = await fetch_act_akn(norma, data_vigenza="20260614")
        assert act is None

    async def test_landing_without_params_returns_none(self, monkeypatch, norma):
        routes = {"uri-res": "<html>no params at all</html>"}
        calls = _install_client(monkeypatch, routes)
        act = await fetch_act_akn(norma, data_vigenza="20260614")
        assert act is None
        # Should NOT have attempted caricaAKN (no params to build the URL).
        assert not any("caricaAKN" in c for c in calls)

    async def test_short_xml_returns_none(self, monkeypatch, norma):
        routes = {
            "uri-res": _load("landing_legge_241_1990.html"),
            "caricaAKN": '<?xml version="1.0"?><akomaNtoso/>',
        }
        _install_client(monkeypatch, norma and routes)
        act = await fetch_act_akn(norma, data_vigenza="20260614")
        assert act is None

    async def test_empty_url_returns_none(self, monkeypatch):
        # An act with no resolvable URL (year-only date missing for plain act).
        norma = Norma(tipo_atto="legge", data="", numero_atto="241")
        calls = _install_client(monkeypatch, {})
        act = await fetch_act_akn(norma)
        assert act is None
        assert calls == []  # no network attempted

    async def test_exception_during_fetch_returns_none(self, monkeypatch, norma):
        def boom(*args, **kwargs):
            raise RuntimeError("network exploded")

        monkeypatch.setattr(akn_fetch.httpx, "AsyncClient", boom)
        act = await fetch_act_akn(norma, data_vigenza="20260614")
        assert act is None
