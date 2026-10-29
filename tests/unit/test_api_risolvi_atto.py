"""``api.risolvi_atto``: an act's full date and URN from its Normattiva page. Network mocked.

The pages are trimmed copies of what Normattiva served (``tests/fixtures/akn``,
``tests/fixtures/normattiva``): L. 241/1990 (a type its title names), D.M. 55/2014 (a type
dated by the ELI metadata only) and the page Normattiva serves for an act it does not have.
"""

import asyncio
from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import act_dates, scraper

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
L241 = (FIXTURES / "akn" / "landing_legge_241_1990.html").read_text(encoding="utf-8")
DM55 = (FIXTURES / "normattiva" / "landing_dm_55_2014.html").read_text(encoding="utf-8")
ERRORE = (FIXTURES / "normattiva" / "landing_atto_inesistente.html").read_text(encoding="utf-8")

N2LS = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    act_dates.svuota_memoria()
    api.configura()
    yield
    api.configura()
    act_dates.svuota_memoria()


def _normattiva(routes: dict, chieste: list, attesa: float = 0):
    """A client factory answering each URL from *routes* (URN suffix -> response), after *attesa* s."""

    async def handler(request):
        await asyncio.sleep(attesa)
        url = str(request.url)
        chieste.append(url)
        for suffisso, risposta in routes.items():
            if url.endswith(suffisso):
                if isinstance(risposta, Exception):
                    raise risposta
                return risposta if isinstance(risposta, httpx.Response) else httpx.Response(200, text=risposta)
        return httpx.Response(200, text=ERRORE)

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


async def _risolvi(routes, *args):
    chieste: list = []
    with api.configurazione(client_factory=_normattiva(routes, chieste)):
        return await api.risolvi_atto(*args), chieste


class TestTrovato:
    async def test_a_year_is_resolved_from_the_page_title(self):
        r, chieste = await _risolvi({"legge:1990-01-01;241": L241}, "legge", "241", "1990")
        assert r.esito == "trovato" and r.errore is None
        assert (r.tipo_atto, r.numero_atto, r.data) == ("legge", "241", "1990-08-07")
        assert r.urn == "urn:nir:stato:legge:1990-08-07;241"
        assert r.url == N2LS + "legge:1990-08-07;241"
        assert r.precisione == "ESATTO"
        # The act's own page, asked by its year: never its art. 1.
        assert chieste == [N2LS + "legge:1990-01-01;241"]
        assert [(f.fonte, f.url) for f in r.fonti.fonti] == [("normattiva", "https://www.normattiva.it/uri-res/N2Ls")]

    @pytest.mark.parametrize("data", ["1990-08-07", "7 agosto 1990", "7° agosto 1990"])
    async def test_a_date_that_is_the_acts_own_is_found(self, data):
        r, _ = await _risolvi({"legge:1990-01-01;241": L241}, "L.", " 241 ", data)
        assert r.esito == "trovato" and r.data == "1990-08-07" and r.tipo_atto == "legge"

    async def test_leading_zeros_of_the_number_are_dropped(self):
        r, chieste = await _risolvi({"legge:1990-01-01;241": L241}, "legge", "0241", "1990")
        assert r.esito == "trovato" and r.numero_atto == "241"
        assert chieste == [N2LS + "legge:1990-01-01;241"]

    async def test_a_type_the_titles_do_not_cover_is_dated_by_the_eli_date(self):
        r, _ = await _risolvi({"decreto.ministeriale:2014-01-01;55": DM55}, "decreto ministeriale", "55", "2014")
        assert r.esito == "trovato" and r.data == "2014-03-10"
        assert r.urn == "urn:nir:stato:decreto.ministeriale:2014-03-10;55"
        assert r.precisione == "INDICATIVO"


class TestTipiVerificati:
    def test_the_declared_types_are_the_titles_types_it_accepts(self):
        from mcp_legal_it.api import _norme
        from mcp_legal_it.lib.visualex.map import normalize_act_type
        from mcp_legal_it.lib.visualex.models import Norma

        accettati = {k.replace(".", " ") for k in act_dates._TITLES} & _norme._TIPI_NOTI
        assert set(api.TIPI_ATTO_VERIFICATI) == accettati
        for tipo in api.TIPI_ATTO_VERIFICATI:
            assert normalize_act_type(tipo).lower() == tipo
            assert scraper._tipo_urn(Norma(tipo_atto=tipo)) in act_dates._TITLES

    @pytest.mark.parametrize("tipo", ["regio decreto legislativo", "decreto"])
    async def test_a_title_type_the_library_does_not_accept_is_refused(self, tipo):
        r, chieste = await _risolvi({}, tipo, "1", "2000")
        assert r.esito == "atto_non_riconosciuto" and chieste == []


class TestCache:
    async def test_a_found_date_is_read_again_without_the_network(self):
        await _risolvi({"legge:1990-01-01;241": L241}, "legge", "241", "1990")
        scraper._full_date_cache.clear()
        act_dates.svuota_memoria()  # a new process: only the disk remains
        r, chieste = await _risolvi({}, "legge", "241", "1990")
        assert r.esito == "trovato" and r.data == "1990-08-07" and r.precisione == "ESATTO"
        assert chieste == [] and r.fonti is None

    async def test_concurrent_calls_for_one_act_share_one_request(self):
        chieste: list = []
        # The page answers late, so all three calls are waiting for it at once.
        with api.configurazione(client_factory=_normattiva({"legge:1990-01-01;241": L241}, chieste, attesa=0.05)):
            esiti = await asyncio.gather(*[api.risolvi_atto("legge", "241", "1990") for _ in range(3)])
        assert {r.data for r in esiti} == {"1990-08-07"}
        assert len(chieste) == 1
        assert all(r.fonti is not None for r in esiti)  # each call lists the page it rests on

    async def test_a_miss_is_not_kept_on_disk(self):
        await _risolvi({}, "legge", "99999", "1990")
        assert act_dates.leggi(act_dates.chiave("legge", "1990", "99999")) is None


class TestNonTrovato:
    async def test_the_error_page_is_not_found(self):
        r, _ = await _risolvi({}, "legge", "99999", "1990")
        assert r.esito == "atto_non_trovato" and r.data is None and r.urn is None and r.precisione is None
        assert r.errore == "nessun atto «legge n. 99999 del 1990» su Normattiva"
        assert r.fonti is not None

    async def test_the_page_of_another_act_is_not_this_act(self):
        # Normattiva's resolver does not check what it is asked: here it serves L. 241/1990.
        r, _ = await _risolvi({"legge:1990-01-01;242": L241}, "legge", "242", "1990")
        assert r.esito == "atto_non_trovato" and r.data is None
        assert "«LEGGE 7 agosto 1990, n. 241»" in r.errore

    async def test_an_eli_date_of_another_year_is_not_this_act(self):
        r, _ = await _risolvi({"decreto.ministeriale:2015-01-01;55": DM55}, "decreto ministeriale", "55", "2015")
        assert r.esito == "atto_non_trovato" and r.data is None

    async def test_a_404_is_not_found(self):
        r, _ = await _risolvi({"legge:1990-01-01;241": httpx.Response(404)}, "legge", "241", "1990")
        assert r.esito == "atto_non_trovato"


class TestAmbiguo:
    async def test_a_day_that_is_not_the_acts_is_ambiguous(self):
        r, _ = await _risolvi({"legge:1990-01-01;241": L241}, "legge", "241", "1990-08-08")
        assert r.esito == "ambiguo"
        # The act Normattiva has with that type, year and number, said as such.
        assert r.data == "1990-08-07" and r.urn == "urn:nir:stato:legge:1990-08-07;241"
        assert r.errore == ("«legge n. 241 del 1990» su Normattiva è del 1990-08-07, non del 1990-08-08: "
                            "sbagliato il giorno o il numero")


class TestFonte:
    @pytest.mark.parametrize("risposta", [
        httpx.Response(503), httpx.Response(429), httpx.ConnectTimeout("lenta"), httpx.ConnectError("giù"),
    ])
    async def test_a_source_down_is_unreachable(self, risposta):
        r, _ = await _risolvi({"legge:1990-01-01;241": risposta}, "legge", "241", "1990")
        assert r.esito == "fonte_non_raggiungibile" and r.data is None
        assert r.errore.startswith("Normattiva non raggiungibile")

    async def test_another_http_error_is_an_error_of_the_source(self):
        r, _ = await _risolvi({"legge:1990-01-01;241": httpx.Response(403)}, "legge", "241", "1990")
        assert r.esito == "errore_fonte"

    async def test_a_failure_is_not_kept(self):
        await _risolvi({"legge:1990-01-01;241": httpx.Response(503)}, "legge", "241", "1990")
        r, chieste = await _risolvi({"legge:1990-01-01;241": L241}, "legge", "241", "1990")
        assert r.esito == "trovato" and len(chieste) == 1


class TestSenzaRete:
    @pytest.mark.parametrize("args, esito", [
        (("regolamento ue", "679", "2016"), "non_supportata"),
        (("direttiva ue", "2555", "2022"), "non_supportata"),
        (("codice civile", "262", "1942"), "non_supportata"),
        (("costituzione", "1", "1947"), "non_supportata"),
        (("gdpr", "679", "2016"), "atto_non_riconosciuto"),
        (("pippo", "1", "2000"), "atto_non_riconosciuto"),
        (("", "1", "2000"), "riferimento_non_valido"),
        (("legge", "", "2000"), "riferimento_non_valido"),
        (("legge", "abc", "2000"), "riferimento_non_valido"),
        (("legge", "0", "2000"), "riferimento_non_valido"),
        (("legge", "241", ""), "riferimento_non_valido"),
        (("legge", "241", "90"), "riferimento_non_valido"),
        (("legge", "241", "1990-02-30"), "riferimento_non_valido"),
        (("legge", "241", "agosto 1990"), "riferimento_non_valido"),
    ])
    async def test_refused_before_any_request(self, args, esito):
        r, chieste = await _risolvi({}, *args)
        assert r.esito == esito and r.errore and r.data is None
        assert chieste == [] and r.fonti is None

    async def test_a_non_string_is_a_programming_error(self):
        with pytest.raises(TypeError):
            await api.risolvi_atto("legge", 241, "1990")
        with pytest.raises(TypeError):
            await api.risolvi_atto("legge", "241", 1990)


class TestWithFullDate:
    async def test_with_full_date_still_swallows_the_source_failure(self):
        from mcp_legal_it.lib.visualex.models import Norma

        chieste: list = []
        with api.configurazione(client_factory=_normattiva({"legge:1990-01-01;241": httpx.Response(503)}, chieste)):
            norma = Norma(tipo_atto="legge", data="1990", numero_atto="241")
            assert await scraper.with_full_date(norma) is norma
        assert len(chieste) == 1


def test_come_dict_gives_plain_data():
    r = api.AttoRisolto(esito="trovato", tipo_atto="legge", numero_atto="241", data="1990-08-07",
                        urn="urn:nir:stato:legge:1990-08-07;241", url=N2LS + "legge:1990-08-07;241",
                        precisione="ESATTO")
    assert api.come_dict(r) == {
        "esito": "trovato", "tipo_atto": "legge", "numero_atto": "241", "data": "1990-08-07",
        "urn": "urn:nir:stato:legge:1990-08-07;241", "url": N2LS + "legge:1990-08-07;241",
        "precisione": "ESATTO", "errore": None, "fonti": None,
    }
