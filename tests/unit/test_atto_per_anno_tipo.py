"""A decree cited by its year is never read as the law Normattiva serves in its place.

Normattiva's resolver does not check an act's type: asked a DPCM n. 158 of 2014 by its year
it serves L. 17 ottobre 2014, n. 158, and a D.M. (or a d.lgs.) n. 241 of 1990 gets L. 7 agosto
1990, n. 241. A page whose heading names another act is refused for every type; the types
dated by their page alone (D.M., DPCM, d.lgs.lgt.) are taken only when the heading names
them (``scraper._INTESTAZIONI``). Network mocked; every page is a trimmed copy of what
Normattiva served (``tests/fixtures/normattiva``, 2 Nov 2026).
"""

from pathlib import Path

import httpx
import pytest

from src.lib.visualex import akn_fetch, scraper
from src.lib.visualex.models import Norma, NormaVisitata
from src.lib.visualex.scraper import AttoNonVerificato, with_full_date

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
ERRORE = _pagina("landing_atto_inesistente.html")
L241 = (FIXTURES / "akn" / "landing_legge_241_1990.html").read_text(encoding="utf-8")
L742 = (FIXTURES / "akn" / "landing_legge_742_1969.html").read_text(encoding="utf-8")
# The article page of L. 241/1990: what a decree's year-only URN of an article would serve.
L241_ART3 = _pagina("l241_n2ls_art3.html")

N2LS = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
DM241 = "decreto.ministeriale:1990-01-01;241"
DLGS241 = "decreto.legislativo:1990-01-01;241"
_CLIENT_REALE = httpx.AsyncClient  # taken once: a second _normattiva must not wrap the first


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    akn_fetch.clear_akn_cache(disk=True)
    yield
    akn_fetch.clear_akn_cache(disk=True)


def _normattiva(monkeypatch, routes: dict, altrimenti=ERRORE) -> list:
    """Every httpx client of the scraper and of the AKN export answers from *routes*
    (URL suffix -> page or response), else *altrimenti*; returns the URLs asked."""
    chieste: list = []

    async def handler(request):
        url = str(request.url)
        chieste.append(url)
        for suffisso, risposta in routes.items():
            if url.endswith(suffisso):
                return risposta if isinstance(risposta, httpx.Response) else httpx.Response(200, text=risposta)
        return altrimenti if isinstance(altrimenti, httpx.Response) else httpx.Response(200, text=altrimenti)

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _CLIENT_REALE(*args, **kwargs)

    monkeypatch.setattr(scraper.httpx, "AsyncClient", factory)
    monkeypatch.setattr(akn_fetch.httpx, "AsyncClient", factory)
    return chieste


class TestUnAltroAtto:
    @pytest.mark.parametrize("pagina, url, norma, legge", [
        (DPCM158_SERVE_LEGGE, "decreto.del.presidente.del.consiglio.dei.ministri:2014-01-01;158",
         Norma("decreto del presidente del consiglio dei ministri", "2014", "158"), "LEGGE 17 ottobre 2014, n. 158"),
        (DM241_SERVE_LEGGE, DM241, Norma("decreto ministeriale", "1990", "241"), "LEGGE 7 agosto 1990, n. 241"),
        # A titled type too: the d.lgs. n. 241 of 1990 asked by its year gets the law's page.
        (L241, DLGS241, Norma("decreto legislativo", "1990", "241"), "LEGGE 7 agosto 1990, n. 241"),
    ], ids=["dpcm-158-2014", "dm-241-1990", "dlgs-241-1990"])
    async def test_the_law_served_for_a_decree_is_refused(self, monkeypatch, pagina, url, norma, legge):
        _normattiva(monkeypatch, {url: pagina})
        with pytest.raises(AttoNonVerificato, match=f"la pagina restituita è «{legge}»"):
            await with_full_date(norma)

    async def test_a_decree_without_a_number_is_not_the_numbered_one(self, monkeypatch):
        _normattiva(monkeypatch, {"decreto.del.presidente.del.consiglio.dei.ministri:2020-01-01;1": DPCM_SENZA_NUMERO})
        with pytest.raises(AttoNonVerificato, match="8 marzo 2020»"):
            await with_full_date(Norma("decreto del presidente del consiglio dei ministri", "2020", "1"))


class TestDecretiVeri:
    @pytest.mark.parametrize("pagina, url, norma, data", [
        (DPCM159, "decreto.del.presidente.del.consiglio.dei.ministri:2013-01-01;159",
         Norma("decreto del presidente del consiglio dei ministri", "2013", "159"), "2013-12-05"),
        (DM37, "decreto.ministeriale:2008-01-01;37", Norma("decreto ministeriale", "2008", "37"), "2008-01-22"),
        (DM55, "decreto.ministeriale:2014-01-01;55", Norma("decreto ministeriale", "2014", "55"), "2014-03-10"),
        (DLLGT98, "decreto.legislativo.luogotenenziale:1946-01-01;98",
         Norma("decreto legislativo luogotenenziale", "1946", "98"), "1946-03-16"),
        (DLLGT151, "decreto.legislativo.luogotenenziale:1944-01-01;151",
         Norma("decreto legislativo luogotenenziale", "1944", "151"), "1944-06-25"),
        (L742, "legge:1969-01-01;742", Norma("legge", "1969", "742"), "1969-10-07"),
    ], ids=["dpcm-159-2013", "dm-37-2008", "dm-55-2014", "dllgt-98-1946", "dllgt-151-1944", "legge-742-1969"])
    async def test_an_act_headed_by_its_type_is_dated(self, monkeypatch, pagina, url, norma, data):
        _normattiva(monkeypatch, {url: pagina})
        assert (await with_full_date(norma)).data == data


class TestPaginaNonVerificabile:
    URL = "decreto.ministeriale:2014-01-01;55"
    DM = Norma("decreto ministeriale", "2014", "55")

    @pytest.mark.parametrize("risposta, attesa", [
        # Derived from the real page: the site's bare name as title.
        (DM55.replace("<title>DECRETO 10 marzo 2014, n. 55 - Normattiva</title>", "<title>Normattiva</title>"),
         "pagina senza l'intestazione dell'atto"),
        (httpx.Response(503), "HTTPStatusError"),
        (ERRORE, "pagina senza l'intestazione dell'atto"),
    ], ids=["senza-intestazione", "503", "pagina-di-errore"])
    async def test_a_decree_whose_page_is_not_verified_is_refused_and_asked_again(self, monkeypatch, risposta, attesa):
        chieste = _normattiva(monkeypatch, {self.URL: risposta})
        with pytest.raises(AttoNonVerificato) as exc:
            await with_full_date(self.DM)
        assert str(exc.value) == ("«decreto ministeriale n. 55 del 2014»: Normattiva non ha confermato ora quale "
                                  f"atto è ({attesa}): riprova più tardi, oppure cita l'atto con la data completa "
                                  "(AAAA-MM-GG)")
        _normattiva(monkeypatch, {self.URL: DM55})
        assert (await with_full_date(self.DM)).data == "2014-03-10"  # never kept: asked again

    async def test_a_heading_of_an_unknown_type_is_refused(self, monkeypatch):
        # Derived from the real page: its heading's type replaced by one no measured page carries.
        _normattiva(monkeypatch, {self.URL: DM55.replace("<title>DECRETO 10 marzo", "<title>DELIBERAZIONE 10 marzo")})
        with pytest.raises(AttoNonVerificato, match="«DELIBERAZIONE 10 marzo 2014, n. 55»"):
            await with_full_date(self.DM)

    async def test_a_heading_and_an_eli_date_that_disagree_are_refused(self, monkeypatch):
        # Derived from the real page: its ELI date moved to another day of the same year.
        _normattiva(monkeypatch, {self.URL: DM55.replace('content="2014-03-10"', 'content="2014-03-11"')})
        with pytest.raises(AttoNonVerificato, match="non coincidono"):
            await with_full_date(self.DM)

    async def test_a_titled_type_whose_page_is_not_read_keeps_the_year(self, monkeypatch):
        # Unchanged for the titled types: a page that cannot be read leaves the citation as is.
        _normattiva(monkeypatch, {"legge:1969-01-01;742": httpx.Response(503)})
        norma = Norma("legge", "1969", "742")
        assert await with_full_date(norma) is norma


class TestOgniLettura:
    """Every reader of a year-only act refuses the law's page: nothing after the landing page."""

    @pytest.mark.parametrize("norma, url, pagina, citato", [
        (Norma("decreto ministeriale", "1990", "241"), DM241, DM241_SERVE_LEGGE, "decreto ministeriale"),
        (Norma("decreto legislativo", "1990", "241"), DLGS241, L241, "decreto legislativo"),
    ], ids=["dm", "dlgs"])
    @pytest.mark.parametrize("lettura", ["articolo", "allegato", "testo_atto", "indice"])
    async def test_every_reader_refuses(self, monkeypatch, norma, url, pagina, citato, lettura):
        chieste = _normattiva(monkeypatch, {url: pagina}, altrimenti=L241_ART3)
        if lettura == "articolo":
            r = await scraper.fetch_article(NormaVisitata(norma=norma, numero_articolo="3"))
            assert r["text"] == "" and r["esito"] == scraper.CHECK_UNAVAILABLE
        elif lettura == "allegato":
            r = await scraper.fetch_article(NormaVisitata(norma=norma, numero_articolo="allegato A"))
            assert r["text"] == "" and r["esito"] == scraper.CHECK_UNAVAILABLE
        elif lettura == "testo_atto":
            r = await scraper.fetch_normattiva_full_text(norma)
            assert r["text"] == ""
        else:
            r = await scraper.fetch_act_index(norma)
            assert r["index"] == []
        assert f"nessun atto «{citato} n. 241 del 1990» su Normattiva" in r["error"]
        assert "«LEGGE 7 agosto 1990, n. 241»" in r["error"]
        assert chieste == [N2LS + url], chieste

    async def test_cite_law(self, monkeypatch):
        from src.tools.legal_citations import _cite_law_impl

        chieste = _normattiva(monkeypatch, {DM241: DM241_SERVE_LEGGE}, altrimenti=L241_ART3)
        testo = await _cite_law_impl("art. 3 d.m. 241/1990")
        assert "«LEGGE 7 agosto 1990, n. 241»" in testo
        assert "motivazione" not in testo.lower()  # nothing of the law's art. 3
        assert chieste == [N2LS + DM241]
