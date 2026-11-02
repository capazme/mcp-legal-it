"""A decree cited by its year is never read as the law Normattiva serves in its place (#136).

Normattiva's resolver does not check an act's type: asked a DPCM n. 158 of 2014 by its year
it serves L. 17 ottobre 2014, n. 158, and a D.M. n. 241 of 1990 gets L. 7 agosto 1990, n. 241.
The types dated by their ELI date (D.M., DPCM, d.lgs.lgt.) are taken only when the page's
heading names them (``scraper._INTESTAZIONI_ELI``). Network mocked; every page is a trimmed
copy of what Normattiva served (``tests/fixtures/normattiva``, 2 Nov 2026).
"""

from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import act_dates, scraper
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
NORMATTIVA = FIXTURES / "normattiva"


def _pagina(nome: str) -> str:
    return (NORMATTIVA / nome).read_text(encoding="utf-8")


DPCM158_SERVE_LEGGE = _pagina("landing_dpcm_158_2014_serve_legge.html")
DM241_SERVE_LEGGE = _pagina("landing_dm_241_1990_serve_legge.html")
DPCM159 = _pagina("landing_dpcm_159_2013.html")
DM37 = _pagina("landing_dm_37_2008.html")
DM55 = _pagina("landing_dm_55_2014.html")
DLLGT98 = _pagina("landing_dllgt_98_1946.html")
DLLGT151 = _pagina("landing_dllgt_151_1944.html")
DPCM_SENZA_NUMERO = _pagina("landing_dpcm_2020_03_08_senza_numero.html")
L241 = (FIXTURES / "akn" / "landing_legge_241_1990.html").read_text(encoding="utf-8")
# The article page of L. 241/1990: what the decree's year-only URN of an article would serve.
L241_ART3 = _pagina("l241_n2ls_art3.html")
ERRORE = _pagina("landing_atto_inesistente.html")

N2LS = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
DM241 = "decreto.ministeriale:1990-01-01;241"
DPCM158 = "decreto.del.presidente.del.consiglio.dei.ministri:2014-01-01;158"
CONTROLLO = "legge:1990-01-01;241"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    monkeypatch.setattr(scraper, "_controllo_valido_fino", 0.0)
    monkeypatch.setattr(scraper, "_controllo_ok", False)
    monkeypatch.setattr(scraper, "_controllo_in_corso", {})
    act_dates.svuota_memoria()
    api.configura()
    yield
    api.configura()
    act_dates.svuota_memoria()


def _normattiva(routes: dict, chieste: list, altrimenti: str = ERRORE):
    """A client factory answering each URL from *routes* (URL suffix -> page), else *altrimenti*."""

    async def handler(request):
        url = str(request.url)
        chieste.append(url)
        for suffisso, risposta in routes.items():
            if url.endswith(suffisso):
                return httpx.Response(200, text=risposta)
        return httpx.Response(200, text=altrimenti)

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


async def _risolvi(routes, *args):
    chieste: list = []
    with api.configurazione(client_factory=_normattiva(routes, chieste)):
        return await api.risolvi_atto(*args), chieste


class TestLaLeggeServitaAlPostoDelDecreto:
    @pytest.mark.parametrize("pagina, url, args, legge", [
        (DPCM158_SERVE_LEGGE, DPCM158, ("decreto del presidente del consiglio dei ministri", "158", "2014"),
         "LEGGE 17 ottobre 2014, n. 158"),
        (DM241_SERVE_LEGGE, DM241, ("decreto ministeriale", "241", "1990"), "LEGGE 7 agosto 1990, n. 241"),
    ], ids=["dpcm-158-2014", "dm-241-1990"])
    async def test_the_law_served_for_a_decree_is_not_found(self, pagina, url, args, legge):
        r, chieste = await _risolvi({url: pagina}, *args)
        assert r.esito == "atto_non_trovato" and r.data is None and r.urn is None
        assert f"la pagina restituita è «{legge}»" in r.errore
        assert chieste == [N2LS + url]  # positive evidence: no check of a known act

    async def test_a_decree_without_a_number_is_not_the_numbered_one(self):
        # The D.P.C.M. 8 marzo 2020 has no number: served for a DPCM n. 1 of 2020, it is
        # another act's page, never a transient failure.
        url = "decreto.del.presidente.del.consiglio.dei.ministri:2020-01-01;1"
        r, _ = await _risolvi({url: DPCM_SENZA_NUMERO},
                              "decreto del presidente del consiglio dei ministri", "1", "2020")
        assert r.esito == "atto_non_trovato"
        assert "«DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI 8 marzo 2020»" in r.errore

    def test_a_heading_without_a_number_is_an_act_page(self):
        meta = scraper.act_page_metadata(DPCM_SENZA_NUMERO)
        assert scraper.normattiva_page_problem(DPCM_SENZA_NUMERO, meta) is None


class TestDecretiVeri:
    @pytest.mark.parametrize("pagina, url, args, data", [
        (DPCM159, "decreto.del.presidente.del.consiglio.dei.ministri:2013-01-01;159",
         ("decreto del presidente del consiglio dei ministri", "159", "2013"), "2013-12-05"),
        (DM37, "decreto.ministeriale:2008-01-01;37", ("decreto ministeriale", "37", "2008"), "2008-01-22"),
        (DM55, "decreto.ministeriale:2014-01-01;55", ("decreto ministeriale", "55", "2014"), "2014-03-10"),
        (DLLGT98, "decreto.legislativo.luogotenenziale:1946-01-01;98",
         ("decreto legislativo luogotenenziale", "98", "1946"), "1946-03-16"),
        # Cited as a d.lgs.lgt., headed «DECRETO-LEGGE LUOGOTENENZIALE»: the act under its other name.
        (DLLGT151, "decreto.legislativo.luogotenenziale:1944-01-01;151",
         ("decreto legislativo luogotenenziale", "151", "1944"), "1944-06-25"),
    ], ids=["dpcm-159-2013", "dm-37-2008", "dm-55-2014", "dllgt-98-1946", "dllgt-151-1944"])
    async def test_a_decree_headed_by_its_type_is_found(self, pagina, url, args, data):
        r, _ = await _risolvi({url: pagina}, *args)
        assert r.esito == "trovato" and r.data == data and r.precisione == "INDICATIVO"

    async def test_the_number_with_leading_zeros_is_the_same_act(self):
        r, _ = await _risolvi({"decreto.ministeriale:2008-01-01;37": DM37}, "decreto ministeriale", "037", "2008")
        assert r.esito == "trovato" and r.data == "2008-01-22"


class TestIntestazioneNonVerificabile:
    # Derived from the real D.M. 55/2014 page: its heading's type replaced by one no measured
    # page carries. Never taken for the act, never for another act: transient, not kept.
    ALTRO_TIPO = DM55.replace("<title>DECRETO 10 marzo 2014, n. 55 - Normattiva</title>",
                              "<title>DELIBERAZIONE 10 marzo 2014, n. 55 - Normattiva</title>")
    URL = "decreto.ministeriale:2014-01-01;55"

    async def test_a_heading_of_an_unknown_type_is_transient_and_asked_again(self):
        r, chieste = await _risolvi({self.URL: self.ALTRO_TIPO}, "decreto ministeriale", "55", "2014")
        assert r.esito == "fonte_non_raggiungibile" and r.data is None
        assert "«DELIBERAZIONE 10 marzo 2014, n. 55»" in r.errore and "data completa" in r.errore
        assert chieste == [N2LS + self.URL]
        r, chieste = await _risolvi({self.URL: DM55}, "decreto ministeriale", "55", "2014")
        assert r.esito == "trovato" and chieste == [N2LS + self.URL]

    async def test_a_page_without_heading_is_not_dated_by_its_eli_date(self):
        # Derived: the real page with the site's bare name as title. Its ELI date is in the
        # cited year, but nothing says whose it is.
        senza = DM55.replace("<title>DECRETO 10 marzo 2014, n. 55 - Normattiva</title>", "<title>Normattiva</title>")
        r, chieste = await _risolvi({self.URL: senza}, "decreto ministeriale", "55", "2014")
        assert r.esito == "fonte_non_raggiungibile" and r.data is None
        r, chieste = await _risolvi({self.URL: DM55}, "decreto ministeriale", "55", "2014")
        assert r.esito == "trovato" and chieste == [N2LS + self.URL]

    def test_the_tables_name_only_measured_headings(self):
        assert scraper._INTESTAZIONI_ELI == {
            "decreto.ministeriale": {"DECRETO"},
            "decreto.del.presidente.del.consiglio.dei.ministri": {"DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI"},
            "decreto.legislativo.luogotenenziale": {"DECRETO LEGISLATIVO LUOGOTENENZIALE",
                                                    "DECRETO-LEGGE LUOGOTENENZIALE"},
        }
        # Every type on the ELI path of risolvi_atto has its measured headings.
        from mcp_legal_it.api import _norme
        from mcp_legal_it.lib.visualex.map import codice_urn

        eli = {t for t in _norme._TIPI_NOTI
               if scraper._tipo_urn(Norma(tipo_atto=t)) not in act_dates._TITLES
               and not codice_urn(t) and t != "costituzione"}
        assert {scraper._tipo_urn(Norma(tipo_atto=t)) for t in eli} <= set(scraper._INTESTAZIONI_ELI)


class TestOgniLettura:
    """Every reader of a year-only act refuses the law's page: no request after the landing page."""

    DM = Norma(tipo_atto="decreto ministeriale", data="1990", numero_atto="241")

    async def _con_normattiva(self, chiamata):
        chieste: list = []
        # The landing page is the law's; any other URL (an article, the AKN export, the tree)
        # would serve the law's article page.
        fabbrica = _normattiva({DM241: DM241_SERVE_LEGGE}, chieste, altrimenti=L241_ART3)
        with api.configurazione(client_factory=fabbrica, brocardi=False):
            risultato = await chiamata()
        assert chieste == [N2LS + DM241], chieste
        return risultato

    @staticmethod
    def _rifiuto(errore: str) -> None:
        assert "nessun atto «decreto ministeriale n. 241 del 1990» su Normattiva" in errore
        assert "«LEGGE 7 agosto 1990, n. 241»" in errore

    async def test_fetch_article(self):
        r = await self._con_normattiva(lambda: scraper.fetch_article(NormaVisitata(norma=self.DM, numero_articolo="3")))
        assert r["text"] == "" and r["url"] == "" and r["esito"] == scraper.CHECK_UNAVAILABLE
        self._rifiuto(r["error"])

    async def test_fetch_article_of_an_annex(self):
        r = await self._con_normattiva(
            lambda: scraper.fetch_article(NormaVisitata(norma=self.DM, numero_articolo="allegato A")))
        assert r["text"] == "" and r["esito"] == scraper.CHECK_UNAVAILABLE
        self._rifiuto(r["error"])

    async def test_fetch_article_futura(self):
        r = await self._con_normattiva(
            lambda: scraper.fetch_article_futura(NormaVisitata(norma=self.DM, numero_articolo="3")))
        assert r["text"] == "" and r["esito"] == scraper.CHECK_UNAVAILABLE
        self._rifiuto(r["error"])

    async def test_testo_articolo(self):
        r = await self._con_normattiva(lambda: api.testo_articolo("art. 3 d.m. 241/1990", canale="html"))
        assert r.esito == "verifica_non_disponibile" and not r.article_text
        self._rifiuto(r.errore)

    async def test_albero_atto(self):
        r = await self._con_normattiva(lambda: api.albero_atto("d.m. 241/1990"))
        assert r.esito == "verifica_non_disponibile" and not r.articles
        self._rifiuto(r.errore)

    async def test_testo_atto(self):
        r = await self._con_normattiva(lambda: api.testo_atto("d.m. 241/1990"))
        assert r.esito == "verifica_non_disponibile" and not r.testo
        self._rifiuto(r.errore)

    async def test_indice_atto_and_the_akn_export(self):
        r = await self._con_normattiva(lambda: api.indice_atto("d.m. 241/1990"))
        assert r.esito == "verifica_non_disponibile" and not r.rubriche
        self._rifiuto(r.errore)

    async def test_indice_atto_without_the_akn_export(self, monkeypatch):
        monkeypatch.setenv("AKN_DISABLED", "1")
        r = await self._con_normattiva(lambda: api.indice_atto("d.m. 241/1990"))
        assert r.esito == "verifica_non_disponibile" and not r.rubriche and not r.codice_redazionale
        self._rifiuto(r.errore)

    async def test_the_fetch_act_index_tool(self):
        from mcp_legal_it.tools.legal_citations import _fetch_act_index_impl

        testo = await self._con_normattiva(lambda: _fetch_act_index_impl("d.m. 241/1990"))
        self._rifiuto(testo)
        assert "motivazione" not in testo.lower()

    async def test_modifiche_articolo(self):
        r = await self._con_normattiva(lambda: api.modifiche_articolo("art. 3 d.m. 241/1990"))
        assert r.esito == "verifica_non_disponibile" and not r.versioni
        self._rifiuto(r.errore)

    async def test_cite_law(self):
        from mcp_legal_it.tools.legal_citations import _cite_law_impl

        testo = await self._con_normattiva(lambda: _cite_law_impl("art. 3 d.m. 241/1990"))
        assert "LEGGE 7 agosto 1990, n. 241" in testo
        # Nothing of the law's art. 3 (its «motivazione») is presented as the decree's text.
        assert "motivazione" not in testo.lower()


class TestPaginaNonVerificabile:
    """A decree's page that cannot be read or verified now: no reader falls back on the
    year-only URN, which would serve the law with that year and number."""

    DM = Norma(tipo_atto="decreto ministeriale", data="2014", numero_atto="55")
    URL = "decreto.ministeriale:2014-01-01;55"

    @pytest.mark.parametrize("risposta", [
        # Derived from the real page: the site's bare name as title.
        DM55.replace("<title>DECRETO 10 marzo 2014, n. 55 - Normattiva</title>", "<title>Normattiva</title>"),
        httpx.Response(503),
        ERRORE,
    ], ids=["senza-intestazione", "503", "pagina-di-errore"])
    async def test_fetch_article_refuses_without_asking_the_year_only_urn(self, risposta):
        chieste: list = []

        async def handler(request):
            chieste.append(str(request.url))
            if str(request.url).endswith(self.URL):
                return risposta if isinstance(risposta, httpx.Response) else httpx.Response(200, text=risposta)
            return httpx.Response(200, text=L241_ART3)

        def factory(fonte, **kwargs):
            kwargs.pop("verify", None)
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        with api.configurazione(client_factory=factory, brocardi=False):
            r = await scraper.fetch_article(NormaVisitata(norma=self.DM, numero_articolo="3"))
        assert r["text"] == "" and r["esito"] == scraper.CHECK_UNAVAILABLE
        assert "la data completa dell'atto non è stata verificata su Normattiva" in r["error"]
        assert all(u.endswith(self.URL) for u in chieste), chieste  # never ~art3 on the year-only URN


class TestDataDallIntestazione:
    URL = "decreto.ministeriale:2014-01-01;55"

    async def test_without_an_eli_date_the_headings_day_is_taken(self):
        # Derived from the real page: its eli:date_document removed.
        senza_eli = DM55.replace('property="eli:date_document"', 'property="x"')
        r, _ = await _risolvi({self.URL: senza_eli}, "decreto ministeriale", "55", "2014")
        assert r.esito == "trovato" and r.data == "2014-03-10" and r.precisione == "INDICATIVO"

    async def test_a_heading_and_an_eli_date_that_disagree_are_transient(self):
        # Derived from the real page: its ELI date moved to another day of the same year.
        discorde = DM55.replace('content="2014-03-10"', 'content="2014-03-11"')
        r, chieste = await _risolvi({self.URL: discorde}, "decreto ministeriale", "55", "2014")
        assert r.esito == "fonte_non_raggiungibile" and r.data is None
        assert "non coincidono" in r.errore
        r, chieste = await _risolvi({self.URL: DM55}, "decreto ministeriale", "55", "2014")
        assert r.esito == "trovato" and chieste == [N2LS + self.URL]

    async def test_a_reader_says_why_when_heading_and_eli_date_disagree(self):
        discorde = DM55.replace('content="2014-03-10"', 'content="2014-03-11"')
        chieste: list = []
        with api.configurazione(client_factory=_normattiva({self.URL: discorde}, chieste, altrimenti=L241_ART3),
                                brocardi=False):
            r = await scraper.fetch_article(NormaVisitata(
                norma=Norma(tipo_atto="decreto ministeriale", data="2014", numero_atto="55"), numero_articolo="3"))
        assert r["text"] == "" and r["esito"] == scraper.CHECK_UNAVAILABLE and "non coincidono" in r["error"]
        assert chieste == [N2LS + self.URL]
