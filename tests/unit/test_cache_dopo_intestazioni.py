"""Records kept before the heading check knew the historical types are never read (G-440).

Before the historical heading types were known (now ``scraper._INTESTAZIONI_ELI``), a
«r.d.lgs. 512/1946» (or a legge, r.d., r.d.l. n. 512 of 1946) got the page of the D.Lgt. 30 marzo 1946, n. 512 and kept it as its own. Each cache
that keeps what such a page said carries a version raised with that fix: a record of the
previous one is another act's, possibly, and is not served (the next reading asks again).
"""

import json
import time

import pytest

from mcp_legal_it.lib.visualex import aggiornamenti, akn_fetch, pagine_normattiva

URL = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto.legislativo:1946-03-30;512~art1"
URN = "urn:nir:stato:regio.decreto.legislativo:1946-03-30;512~art1"


@pytest.fixture(autouse=True)
def _cache(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    pagine_normattiva.svuota_memoria()
    monkeypatch.setattr(akn_fetch, "_url_params", {})
    monkeypatch.setattr(akn_fetch, "_url_params_loaded", False)
    yield
    pagine_normattiva.svuota_memoria()


def test_the_versions_were_raised():
    assert pagine_normattiva.SCHEMA == 6
    assert aggiornamenti.SCHEMA == 3
    assert akn_fetch._VERIFICATA == "intestazione-2"


class TestPagineNormattiva:
    def _scrivi_su_disco(self, schema):
        cartella = pagine_normattiva._dir()
        cartella.mkdir(parents=True, exist_ok=True)
        (cartella / f"{pagine_normattiva._chiave(URL)}.json").write_text(json.dumps({
            "schema": schema, "url": URL, "salvato": time.time(), "testo": "Art. 1 del D.Lgt. 512/1946",
            "servito": "1", "validita": None, "note": None, "parti": [], "parte_servita": None}), encoding="utf-8")

    def test_a_record_of_the_previous_schema_is_not_served(self):
        self._scrivi_su_disco(5)
        assert pagine_normattiva.leggi(URL) is None
        # and it is dropped, so it is not met again
        assert not (pagine_normattiva._dir() / f"{pagine_normattiva._chiave(URL)}.json").exists()

    def test_a_record_of_this_schema_is(self):
        self._scrivi_su_disco(pagine_normattiva.SCHEMA)
        assert pagine_normattiva.leggi(URL)["testo"] == "Art. 1 del D.Lgt. 512/1946"


class TestAknUrlParams:
    def _scrivi(self, marcatore):
        path = akn_fetch._url_params_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({URL: ["046U0512", "1946-06-22", marcatore]}), encoding="utf-8")

    def test_an_entry_of_the_blind_check_is_not_read(self):
        self._scrivi("intestazione")
        assert akn_fetch._get_url_params(URL) is None

    def test_an_entry_of_this_check_is(self):
        self._scrivi(akn_fetch._VERIFICATA)
        assert akn_fetch._get_url_params(URL) == ("046U0512", "1946-06-22")

    def test_a_new_entry_carries_the_new_marker(self):
        akn_fetch._set_url_params(URL, "046U0512", "1946-06-22")
        raw = json.loads(akn_fetch._url_params_path().read_text(encoding="utf-8"))
        assert raw[URL] == ["046U0512", "1946-06-22", "intestazione-2"]


class TestAggiornamenti:
    def _scrivi(self, schema):
        path = aggiornamenti._file_cache(URN, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema": schema, "salvato": time.time(), "finestra": ["1946-06-22", None],
                                    "righe": []}), encoding="utf-8")

    def test_a_record_of_the_previous_schema_is_not_served(self):
        self._scrivi(2)
        assert aggiornamenti.leggi_versione(URN, 1) is None

    def test_a_record_of_this_schema_is(self):
        self._scrivi(aggiornamenti.SCHEMA)
        assert aggiornamenti.leggi_versione(URN, 1)["finestra"] == ["1946-06-22", None]
