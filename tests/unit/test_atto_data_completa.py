"""An act cited with its full date is never read as another act Normattiva serves in its place.

The resolver does not check what it is asked, with a full date either: the URN of a
D.M. 7 agosto 1990, n. 241 serves L. 7 agosto 1990, n. 241. Every page a reader downloads
is checked against the URN asked (``scraper.controlla_intestazione``): another type,
number or day is refused (``atto_non_trovato``), naming the page. Network mocked; the pages
are trimmed copies of what Normattiva served (``tests/fixtures/normattiva``).
"""

import json
from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import act_dates, akn_fetch, pagine_normattiva, scraper
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
L241 = (FIXTURES / "akn" / "landing_legge_241_1990.html").read_text(encoding="utf-8")
ART3_SERVE_LEGGE = (FIXTURES / "normattiva" / "dm_241_1990_art3_serve_legge.html").read_text(encoding="utf-8")
DM241_SERVE_LEGGE = (FIXTURES / "normattiva" / "landing_dm_241_1990_serve_legge.html").read_text(encoding="utf-8")

N2LS = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
DM = Norma(tipo_atto="decreto ministeriale", data="1990-08-07", numero_atto="241")
RIFIUTO = ("nessun atto «decreto ministeriale n. 241 del 1990-08-07» su Normattiva: la pagina restituita è "
           "«LEGGE 7 agosto 1990, n. 241» (controlla tipo, numero e data)")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    monkeypatch.setattr(akn_fetch, "_url_params", {})
    monkeypatch.setattr(akn_fetch, "_url_params_loaded", False)
    pagine_normattiva.svuota_memoria()
    akn_fetch.clear_akn_cache()
    act_dates.svuota_memoria()
    api.configura()
    yield
    api.configura()
    pagine_normattiva.svuota_memoria()
    akn_fetch.clear_akn_cache()


def _normattiva(routes: dict, chieste: list):
    """Every URL answered from *routes* (URL suffix -> page); anything else is the law's page."""

    async def handler(request):
        url = str(request.url)
        chieste.append(url)
        for suffisso, pagina in routes.items():
            if url.endswith(suffisso):
                return httpx.Response(200, text=pagina)
        return httpx.Response(200, text=L241)

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


async def _con(chiamata, routes=None):
    chieste: list = []
    rotte = routes if routes is not None else {
        "decreto.ministeriale:1990-08-07;241~art3": ART3_SERVE_LEGGE,
        "decreto.ministeriale:1990-08-07;241": DM241_SERVE_LEGGE,
    }
    with api.configurazione(client_factory=_normattiva(rotte, chieste), brocardi=False):
        return await chiamata(), chieste


class TestControllaIntestazione:
    @pytest.mark.parametrize("url, pagina", [
        (N2LS + "decreto.ministeriale:1990-08-07;241~art3", ART3_SERVE_LEGGE),       # another type
        (N2LS + "legge:1990-08-08;241", L241),                                       # another day
        (N2LS + "legge:1990-08-07;242", L241),                                       # another number
        (N2LS + "decreto.legislativo:1990-01-01;241", L241),                         # year-only, another type
    ], ids=["tipo", "giorno", "numero", "anno-tipo"])
    def test_another_act_is_refused(self, url, pagina):
        with pytest.raises(scraper.AttoNonVerificato) as exc:
            scraper.controlla_intestazione(url, pagina)
        assert exc.value.altro_atto and "«LEGGE 7 agosto 1990, n. 241»" in str(exc.value)

    @pytest.mark.parametrize("url, pagina", [
        (N2LS + "legge:1990-08-07;241~art3", L241),        # the act itself
        (N2LS + "legge:1990-01-01;241", L241),             # its year-only URN
        (N2LS + "legge:1990-08-07;0241", L241),            # leading zeros
        (N2LS + "costituzione:1947-12-27~art1", L241),     # no number: nothing to compare
        ("https://www.normattiva.it/do/atto/caricaArticolo?x=1", L241),  # not an act URN
        (N2LS + "decreto.ministeriale:1990-08-07;241", "<html><title>Normattiva</title></html>"),  # no heading
    ], ids=["stesso-atto", "solo-anno", "zeri", "senza-numero", "frammento", "senza-intestazione"])
    def test_nothing_is_refused_without_positive_evidence(self, url, pagina):
        scraper.controlla_intestazione(url, pagina)

    def test_the_message_says_data_or_anno(self):
        with pytest.raises(scraper.AttoNonVerificato, match=r"\(controlla tipo, numero e data\)$"):
            scraper.controlla_intestazione(N2LS + "decreto.ministeriale:1990-08-07;241", L241)


class TestOgniLettura:
    @pytest.mark.parametrize("akn", ["1", ""], ids=["solo-pagina", "export-prima"])
    async def test_fetch_article(self, monkeypatch, akn):
        if akn:
            monkeypatch.setenv("AKN_DISABLED", akn)
        r, _ = await _con(lambda: scraper.fetch_article(NormaVisitata(norma=DM, numero_articolo="3")))
        assert r == {"text": "", "url": "", "source": "normattiva", "esito": scraper.ACT_NOT_FOUND, "error": RIFIUTO}

    async def test_cite_law(self):
        from mcp_legal_it.tools.legal_citations import _cite_law_impl

        testo, _ = await _con(lambda: _cite_law_impl("art. 3 D.M. 7 agosto 1990, n. 241"))
        assert "«LEGGE 7 agosto 1990, n. 241»" in testo and "motivazione" not in testo.lower()

    async def test_cite_law_json_has_no_link(self):
        from mcp_legal_it.tools.legal_citations import _cite_law_impl

        testo, _ = await _con(lambda: _cite_law_impl("art. 3 D.M. 7 agosto 1990, n. 241", formato="json"))
        payload = json.loads(testo)
        assert payload["url"] == "" and payload["urn"] is None and not payload["testo"]

    @pytest.mark.parametrize("chiamata", [
        lambda: api.albero_atto(api.riferimento_da_parametri("decreto ministeriale", "", data="1990-08-07",
                                                             numero_atto="241").norma_data[0]),
        lambda: api.testo_atto(api.riferimento_da_parametri("decreto ministeriale", "", data="1990-08-07",
                                                            numero_atto="241").norma_data[0]),
        lambda: api.indice_atto(api.riferimento_da_parametri("decreto ministeriale", "", data="1990-08-07",
                                                             numero_atto="241").norma_data[0]),
        lambda: api.modifiche_articolo(api.riferimento_da_parametri("decreto ministeriale", "3", data="1990-08-07",
                                                                    numero_atto="241").norma_data[0]),
    ], ids=["albero", "testo_atto", "indice", "modifiche"])
    async def test_the_api_readers(self, chiamata):
        r, _ = await _con(chiamata)
        assert r.esito == "atto_non_trovato" and "«LEGGE 7 agosto 1990, n. 241»" in r.errore

    async def test_the_index_without_the_export(self, monkeypatch):
        monkeypatch.setenv("AKN_DISABLED", "1")
        from mcp_legal_it.tools.legal_citations import _fetch_act_index_impl

        testo, _ = await _con(lambda: _fetch_act_index_impl("D.M. 7 agosto 1990, n. 241"))
        assert "«LEGGE 7 agosto 1990, n. 241»" in testo

    async def test_the_law_with_its_full_date_is_read(self):
        legge = Norma(tipo_atto="legge", data="1990-08-07", numero_atto="241")
        r, _ = await _con(lambda: scraper.fetch_act_tree(legge), routes={"legge:1990-08-07;241": L241})
        assert not r.get("error") and r["count"] > 0


class TestCache:
    async def test_an_export_url_entry_kept_before_the_check_is_not_read(self, tmp_path):
        # Written by a version without the heading check: two elements. Never trusted.
        url = N2LS + "decreto.ministeriale:1990-08-07;241"
        (tmp_path / "cache" / "akn_acts").mkdir(parents=True)
        (tmp_path / "cache" / "akn_acts" / "akn_url_params.json").write_text(
            json.dumps({url: ["090G0294", "1990-08-18"]}), encoding="utf-8")
        assert akn_fetch._get_url_params(url) is None

    async def test_a_checked_entry_is_kept_with_its_mark(self, tmp_path):
        url = N2LS + "legge:1990-08-07;241"
        akn_fetch._set_url_params(url, "090G0294", "1990-08-18")
        akn_fetch._url_params.clear()
        akn_fetch._url_params_loaded = False
        assert akn_fetch._get_url_params(url) == ("090G0294", "1990-08-18")
        raw = json.loads((tmp_path / "cache" / "akn_acts" / "akn_url_params.json").read_text(encoding="utf-8"))
        assert raw[url] == ["090G0294", "1990-08-18", "intestazione"]

    def test_the_page_cache_schema_was_raised(self):
        assert pagine_normattiva.SCHEMA == 5


class TestExport:
    async def test_concurrent_downloads_of_another_act_each_refuse(self):
        import asyncio

        chieste: list = []

        async def handler(request):
            await asyncio.sleep(0.05)  # the leader is still downloading when the others ask
            chieste.append(str(request.url))
            return httpx.Response(200, text=DM241_SERVE_LEGGE)

        def factory(fonte, **kwargs):
            kwargs.pop("verify", None)
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        with api.configurazione(client_factory=factory):
            esiti = await asyncio.gather(*(akn_fetch.fetch_act_akn(DM, "20261102") for _ in range(3)),
                                         return_exceptions=True)
        assert all(isinstance(e, scraper.AttoNonVerificato) and e.altro_atto for e in esiti), esiti
        assert len(chieste) == 1  # one landing page, shared

    async def test_the_export_fallback_keeps_the_refusal(self):
        # The article page fails (503): the export, the fallback, reads the landing page and
        # finds the law. The answer is atto_non_trovato, not the page's transient error.
        chieste: list = []

        async def handler(request):
            url = str(request.url)
            chieste.append(url)
            if url.endswith("~art3"):
                return httpx.Response(503)
            return httpx.Response(200, text=DM241_SERVE_LEGGE)

        def factory(fonte, **kwargs):
            kwargs.pop("verify", None)
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        with api.configurazione(client_factory=factory, brocardi=False):
            r = await scraper.fetch_article(NormaVisitata(norma=DM, numero_articolo="3"))
        assert r["esito"] == scraper.ACT_NOT_FOUND and r["error"] == RIFIUTO
