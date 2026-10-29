"""Articles Normattiva splits into parts («1 (commi 1-100)» …), read part by part. Network mocked.

Art. 1 L. 296/2006 is 14 parts of up to 100 commi; the article's page serves the first.
Pages: real copies (``tests/fixtures/normattiva/parti``, see the README one level up): the
article page with its tree, parts 8 (commi 701-800) and 2 (101-200).
"""

import json
import re
from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.core import citazioni, norme
from mcp_legal_it.lib.visualex import normattiva_html as nh
from mcp_legal_it.lib.visualex import pagine_normattiva, parti_normattiva, scraper
from mcp_legal_it.tools import legal_citations as lc

DIR = Path(__file__).resolve().parents[1] / "fixtures" / "normattiva"
ART1 = (DIR / "parti" / "l296_art1.html").read_text(encoding="utf-8")
PARTE8 = (DIR / "parti" / "l296_art1_parte8.html").read_text(encoding="utf-8")
PARTE2 = (DIR / "parti" / "l296_art1_parte2.html").read_text(encoding="utf-8")
ART3_DLGS23 = (DIR / "dlgs23_n2ls_art3.html").read_text(encoding="utf-8")

L296 = ("legge", "1", "2006-12-27", "296")
FRASE_773 = "complessivamente rideterminata nel 10 per cento"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AKN_DISABLED", "1")
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    monkeypatch.setattr(scraper, "_sessioni", {})
    pagine_normattiva.svuota_memoria()
    api.configura()
    yield
    api.configura()
    pagine_normattiva.svuota_memoria()


def _normattiva(chieste: list, *, pagina: str = ART1, parti: dict | None = None):
    """The article page (with a session cookie) and the parts' pages by progressivo."""
    parti = {8: PARTE8, 2: PARTE2} if parti is None else parti

    def handler(request):
        url = str(request.url)
        chieste.append((url, request.headers.get("cookie", "")))
        if "uri-res/N2Ls" in url:
            return httpx.Response(200, text=pagina, headers={"set-cookie": "JSESSIONID=sessione-1; Path=/"})
        k = re.search(r"art\.progressivo=(\d+)", url)
        risposta = parti.get(int(k.group(1))) if k else None
        if isinstance(risposta, httpx.Response):
            return risposta
        return httpx.Response(200, text=risposta) if risposta else httpx.Response(404)

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


def _rif():
    return api.riferimento_da_parametri(*L296).norma_data[0]


class TestLettura:
    def _stesso(self, etichetta):
        return scraper._article_identity(scraper.normalize_article_key(etichetta)) == ("1", "")

    def test_the_parts_of_the_tree(self):
        parti = parti_normattiva.parti_articolo(ART1, self._stesso)
        assert len(parti) == 14
        assert [(p["progressivo"], p["commi_dal"], p["commi_al"]) for p in (parti[0], parti[7], parti[-1])] == [
            (1, "1", "100"), (8, "701", "800"), (14, "1301", "1364")]
        assert parti_normattiva.parte_servita(ART1, parti)["progressivo"] == 1
        assert parti_normattiva.parte_servita(PARTE8, parti)["progressivo"] == 8

    def test_an_article_not_split_has_no_parts(self):
        assert parti_normattiva.parti_articolo(ART3_DLGS23, self._stesso) == []

    @pytest.mark.parametrize("comma, progressivo", [
        ("773", 8), ("773-bis", 8), ("701", 8), ("800", 8), ("100-bis", 1), ("1", 1), ("1364", 14), ("1365", None),
    ])
    def test_the_part_of_a_comma(self, comma, progressivo):
        parte = parti_normattiva.parte_del_comma(parti_normattiva.parti_articolo(ART1, self._stesso), comma)
        assert (parte["progressivo"] if parte else None) == progressivo

    @pytest.mark.parametrize("riferimento, comma", [
        ("art. 1, comma 773, L. 296/2006", "773"),
        ("art. 1 co. 773 L. 296/2006", "773"),
        ("art. 1, c. 773, L. 296/2006", "773"),
        ("art. 1, 773° comma, L. 296/2006", "773"),
        ("art. 1, comma 773-bis, L. 296/2006", "773-bis"),
        ("art. 1, co. 12 ter, L. 296/2006", "12-ter"),
        ("art. 1, commi 773 e 774, L. 296/2006", "773"),
        ("art. 1, commi 773-775, L. 296/2006", "773"),
        ("commi 773 e 774 dell'art. 1 L. 296/2006", "773"),
        ("art. 1 L. 296/2006", None),
        ("art. 2043 c.c.", None),
        ("art. 3 l.c. 3/2001", None),  # the «c.» of «l.c.» is no comma
        ("art. 1 c.c. 1942", None),  # nor the year after «c.c.»
        ("art. 18 St. lav. come mod. da art. 1, comma 42, l. 92/2012", None),  # another article's comma
        ("art. 1 L. 296/2006, comma 773", "773"),  # after the act
        ("art. 1 legge 27 dicembre 2006, n. 296, c. 773-bis", "773-bis"),
        ("art. 2 L. 92/2012, come mod. da art. 1 L. 296/2006, comma 5", None),  # two articles: whose?
    ])
    def test_the_comma_of_a_reference(self, riferimento, comma):
        assert parti_normattiva.comma_richiesto(riferimento) == comma

    @pytest.mark.parametrize("riferimento", [
        "art. 1 " + " " * 20000 + "comma 1 x",
        "art. 1" + " ," * 20000 + "x",
        "art. 1 " + "c. " * 10000,
        "comma 1 , " * 5000 + "art. 1",
    ])
    def test_the_comma_reader_is_linear(self, riferimento):
        import time
        start = time.perf_counter()
        parti_normattiva.comma_richiesto(riferimento)
        assert time.perf_counter() - start < 0.1


class TestApi:
    async def test_the_article_is_its_first_part_and_says_so(self):
        chieste: list = []
        with api.configurazione(client_factory=_normattiva(chieste)):
            t = await api.testo_articolo(_rif(), canale="html")
        assert t.esito == "trovato" and t.article_text == nh.estrai_da_html(ART1)  # VisuaLex's, byte for byte
        assert t.testo_parziale is True and len(t.parti) == 14
        assert t.parti[7] == api.ParteArticolo(
            progressivo=8, commi_dal="701", commi_al="800",
            url=t.parti[7].url) and t.parti[7].url.startswith("https://www.normattiva.it/atto/caricaArticolo?")
        assert any(a.startswith("testo parziale: commi 1-100 di 1364 (l'articolo è diviso in 14 parti") for a in t.avvisi)
        assert len(chieste) == 1

    async def test_a_part_is_one_request_more_with_the_pages_session(self):
        chieste: list = []
        with api.configurazione(client_factory=_normattiva(chieste)):
            t = await api.parte_articolo(_rif(), 8, canale="html")
        assert t.esito == "trovato" and FRASE_773 in t.article_text and "773." in t.article_text
        assert t.testo_parziale is True and len(t.parti) == 14
        assert any(a.startswith("testo parziale: commi 701-800 di 1364") for a in t.avvisi)
        assert len(chieste) == 2 and "JSESSIONID=sessione-1" in chieste[1][1]

    async def test_without_a_session_the_page_is_asked_again(self, monkeypatch):
        chieste: list = []
        with api.configurazione(client_factory=_normattiva(chieste)):
            await api.testo_articolo(_rif(), canale="html")
            scraper._sessioni.clear()
            t = await api.parte_articolo(_rif(), 8, canale="html")
        assert FRASE_773 in t.article_text
        assert [u for u, _ in chieste][1:] == [chieste[0][0], chieste[2][0]] and "progressivo=8" in chieste[2][0]

    async def test_a_part_read_is_kept_under_its_commi(self):
        chieste: list = []
        with api.configurazione(client_factory=_normattiva(chieste)):
            await api.parte_articolo(_rif(), 8, canale="html")
            n = len(chieste)
            t = await api.parte_articolo(_rif(), 8, canale="html")
        assert len(chieste) == n and FRASE_773 in t.article_text

    @pytest.mark.parametrize("progressivo", [0, 15])
    async def test_a_progressivo_the_tree_lacks_is_refused(self, progressivo):
        with api.configurazione(client_factory=_normattiva([])):
            t = await api.parte_articolo(_rif(), progressivo, canale="html")
        assert t.esito == "riferimento_non_valido" and t.article_text == "" and "non la" in t.errore
        assert len(t.parti) == 14

    async def test_an_article_not_split_has_no_parts(self):
        with api.configurazione(client_factory=_normattiva([], pagina=ART3_DLGS23)):
            nd = api.riferimento_da_parametri("decreto legislativo", "3", "2015-03-04", "23").norma_data[0]
            intero = await api.testo_articolo(nd, canale="html")
            parte = await api.parte_articolo(nd, 1, canale="html")
        assert intero.parti == () and intero.testo_parziale is False
        assert parte.esito == "riferimento_non_valido" and "non è diviso in parti" in parte.errore

    @pytest.mark.parametrize("guasto", [httpx.Response(503), PARTE2])
    async def test_a_part_that_cannot_be_read_is_never_another(self, guasto):
        # A 503, or the page of another part (commi 101-200 served when 701-800 was asked).
        with api.configurazione(client_factory=_normattiva([], parti={8: guasto})):
            t = await api.parte_articolo(_rif(), 8, canale="html")
        assert t.esito == "verifica_non_disponibile" and t.article_text == ""
        assert "commi 701-800" in t.errore

    def test_the_part_of_a_comma_in_the_library(self):
        parti = tuple(api.ParteArticolo(p, d, a, "") for p, d, a in [(1, "1", "100"), (2, "101", "200")])
        assert api.parte_del_comma(parti, "150").progressivo == 2
        assert api.parte_del_comma(parti, "100 bis").progressivo == 1
        assert api.parte_del_comma(parti, "201") is None
        assert api.parte_del_comma((), "1") is None

    async def test_a_parts_notes_are_its_own(self):
        # Part 2 calls «((168))» and holds no note: said, never silent.
        with api.configurazione(client_factory=_normattiva([])):
            t = await api.parte_articolo(_rif(), 2, canale="html")
        assert t.note_aggiornamento == () and t.note_non_lette is True
        assert norme.AVVISO_NOTE_NON_LETTE in t.avvisi


class TestStrumentiMcp:
    async def test_a_comma_reads_its_part(self):
        chieste: list = []
        with api.configurazione(client_factory=_normattiva(chieste)):
            out = await lc._cite_law_impl("art. 1, comma 773, legge 27 dicembre 2006, n. 296")
        assert FRASE_773 in out and len(chieste) == 2
        assert "**Attenzione**: testo parziale: commi 701-800 di 1364 (l'articolo è diviso in 14 parti su Normattiva)." in out
        assert "**Commi 701-800** (parte 8 di 14 dell'articolo su Normattiva)" in out
        assert "citarlo nel riferimento" not in out
        # The citation gate reads the article the text is about: art. 1, the article read.
        assert citazioni.articolo_servito(out) == "1"

    async def test_without_a_comma_the_first_part_the_notice_and_the_parts(self):
        with api.configurazione(client_factory=_normattiva([])):
            out = await lc._cite_law_impl("art. 1 legge 27 dicembre 2006, n. 296")
        assert FRASE_773 not in out
        assert ("**Attenzione**: testo parziale: commi 1-100 di 1364 (l'articolo è diviso in 14 parti su Normattiva); "
                "per un comma, citarlo nel riferimento (es. «art. 1, comma 773, L. 296/2006»).") in out
        assert out.rstrip().endswith("commi 1201-1300; commi 1301-1364.")
        assert "**Parti dell'articolo su Normattiva**: commi 1-100; commi 101-200;" in out

    async def test_fetch_law_article_serves_the_first_part_and_says_so(self):
        with api.configurazione(client_factory=_normattiva([])):
            out = await lc._fetch_law_article_impl("legge", "1", "2006-12-27", "296")
        assert "testo parziale: commi 1-100 di 1364" in out

    async def test_a_comma_in_no_part_is_said(self):
        with api.configurazione(client_factory=_normattiva([])):
            out = await lc._cite_law_impl("art. 1, comma 1400, legge 27 dicembre 2006, n. 296")
        assert "il comma 1400 non è in nessuna parte dell'art. 1 su Normattiva (commi 1-1364)" in out

    async def test_a_part_not_read_is_said_and_the_text_is_the_first(self):
        with api.configurazione(client_factory=_normattiva([], parti={8: httpx.Response(503)})):
            out = await lc._cite_law_impl("art. 1, comma 773, legge 27 dicembre 2006, n. 296")
        assert "commi 701-800 non letti (HTTPStatusError): il testo è un'altra parte dell'articolo" in out
        assert "testo parziale: commi 1-100 di 1364" in out and FRASE_773 not in out

    async def test_cite_law_json_with_a_comma(self):
        with api.configurazione(client_factory=_normattiva([])):
            j = json.loads(await lc._cite_law_impl("art. 1, comma 773, legge 27 dicembre 2006, n. 296", formato="json"))
        assert FRASE_773 in j["testo"] and j["testo_parziale"] is True
        assert (j["parte"]["progressivo"], j["parte"]["commi_dal"], j["parte"]["commi_al"]) == (8, "701", "800")
        assert len(j["parti"]) == 14 and j["parti"][13]["commi_al"] == "1364"
        assert "chiave_pagina" not in j


class TestSessione:
    """A kept session is reused only while it serves the part; a dead one is dropped."""

    @staticmethod
    def _sessioni_in_successione(chieste: list):
        """The page gives the session «morta» first, then «viva»; «morta» answers another part."""
        sessioni = iter(["morta", "viva", "viva", "viva"])

        def handler(request):
            url, cookie = str(request.url), request.headers.get("cookie", "")
            chieste.append((url, cookie))
            if "uri-res/N2Ls" in url:
                return httpx.Response(200, text=ART1, headers={"set-cookie": f"JSESSIONID={next(sessioni)}; Path=/"})
            return httpx.Response(200, text=PARTE2 if "morta" in cookie else PARTE8)

        def factory(fonte, **kwargs):
            kwargs.pop("verify", None)
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        return factory

    async def test_a_dead_session_is_dropped_and_the_part_read_with_a_new_one(self):
        chieste: list = []
        with api.configurazione(client_factory=self._sessioni_in_successione(chieste)):
            await api.testo_articolo(_rif(), canale="html")
            t = await api.parte_articolo(_rif(), 8, canale="html")
        assert t.esito == "trovato" and FRASE_773 in t.article_text
        # page («morta»), part with «morta» (another part), page again («viva»), part with «viva».
        assert [("N2Ls" in u, c.split("=")[-1] if c else "") for u, c in chieste] == [
            (True, ""), (False, "morta"), (True, ""), (False, "viva")]
        (cookie,) = [v for _, v in scraper._sessioni.values()]
        assert cookie == {"JSESSIONID": "viva"}

    async def test_a_session_is_never_kept_for_a_part_not_served(self):
        def handler(request):
            if "uri-res/N2Ls" in str(request.url):
                return httpx.Response(200, text=ART1, headers={"set-cookie": "JSESSIONID=x; Path=/"})
            return httpx.Response(200, text=PARTE2)  # always another part

        def factory(fonte, **kwargs):
            kwargs.pop("verify", None)
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        with api.configurazione(client_factory=factory):
            await api.testo_articolo(_rif(), canale="html")
            scraper._sessioni.clear()
            t = await api.parte_articolo(_rif(), 8, canale="html")
        assert t.esito == "verifica_non_disponibile" and scraper._sessioni == {}

    async def test_without_a_session_the_part_path_comes_from_the_fresh_page(self):
        chieste: list = []
        with api.configurazione(client_factory=_normattiva(chieste)):
            await api.testo_articolo(_rif(), canale="html")  # tree kept with art.versione=150
        scraper._sessioni.clear()
        nuova = ART1.replace("art.versione=150", "art.versione=151")
        chieste.clear()
        with api.configurazione(client_factory=_normattiva(chieste, pagina=nuova)):
            t = await api.parte_articolo(_rif(), 8, canale="html")
        assert FRASE_773 in t.article_text
        assert "art.versione=151" in chieste[-1][0] and "progressivo=8" in chieste[-1][0]

    async def test_the_part_reading_is_kept_under_the_trees_version(self):
        with api.configurazione(client_factory=_normattiva([])):
            await api.parte_articolo(_rif(), 8, canale="html")
        chiavi = [k for k in pagine_normattiva._memoria if "|parte|" in k]
        assert chiavi and all("|parte|v150|701-800" in k for k in chiavi)


class TestCorrezioni:
    @pytest.mark.parametrize("testo", ["\n" * 40000, " \n" * 20000 + "(" * 20000, ("1. a\n" * 20000)])
    def test_the_comma_line_search_is_linear(self, testo):
        # «^\s*» under (?m) crossed every blank line after each line start: 40k empty lines took 5 s.
        import time
        start = time.perf_counter()
        assert parti_normattiva.contiene_comma(testo, "773-bis") is False
        assert time.perf_counter() - start < 0.1

    async def test_a_part_not_read_makes_the_verifier_say_non_verificata(self):
        with api.configurazione(client_factory=_normattiva([], parti={8: httpx.Response(503)})):
            verdetto, nota = await lc._verifica_norma("art. 1, comma 773, legge 27 dicembre 2006, n. 296")
        assert verdetto == "non verificata" and "non è stato possibile" in nota

    async def test_the_akn_channel_has_no_parts(self):
        t = await api.parte_articolo(_rif(), 8, canale="akn")
        assert t.esito == "non_supportata" and t.article_text == ""

    async def test_the_library_reads_the_comma_of_a_reference_string(self):
        with api.configurazione(client_factory=_normattiva([])):
            t = await api.testo_articolo("art. 1, comma 773, legge 27 dicembre 2006, n. 296", canale="html")
        assert FRASE_773 in t.article_text and t.testo_parziale is True

    async def test_the_library_notice_names_its_own_functions(self):
        with api.configurazione(client_factory=_normattiva([])):
            t = await api.testo_articolo(_rif(), canale="html")
        (avviso,) = [a for a in t.avvisi if a.startswith("testo parziale")]
        assert "parte_del_comma(parti, comma) e parte_articolo(riferimento, progressivo)" in avviso

    async def test_a_part_without_the_commas_line_is_said(self):
        senza_773 = re.sub(r"(?m)^(\s*(?:<[^>]+>\s*)*)773\.", r"\1773bis.", PARTE8, count=1)
        assert senza_773 != PARTE8
        with api.configurazione(client_factory=_normattiva([], parti={8: senza_773})):
            out = await lc._cite_law_impl("art. 1, comma 773, legge 27 dicembre 2006, n. 296")
        assert "il comma 773 non compare nella parte letta (commi 701-800): verificare su Normattiva" in out

