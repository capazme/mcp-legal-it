"""An EU regulation or directive without a date is the text in force: its latest consolidation (issue #50).

``cite_law("art. 111 Regolamento UE 2024/1689")`` served the Official Journal text of 12.7.2024
while Reg. (UE) 2026/1744 had amended art. 111: par. 2 now reads «prima della data di
applicazione del capo III di cui all'articolo 113» and par. 4 was added. The pages are CELLAR's
(trimmed to art. 111, tests/fixtures/visualex/eurlex/README.md); CELLAR's consolidation lookup is
faked with what it answered on 22/10/2026.
"""

import json
from pathlib import Path

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import eurlex_consolidate as ec
from mcp_legal_it.lib.visualex import scraper

pytestmark = pytest.mark.consolidazioni_reali

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "eurlex"
CELLAR = "https://publications.europa.eu/resource/celex/"
OJ = (FIXTURES / "ai_act_oj_art111_trimmed.html").read_text(encoding="utf-8")
CONS = (FIXTURES / "ai_act_consolidated_20260727_art111_trimmed.html").read_text(encoding="utf-8")

#: What CELLAR answered for 32024R1689 on 22/10/2026 (``consolidazioni``).
AI_ACT = {
    "data_gu": "2024-07-12", "in_vigore_dal": "2024-08-01",
    "versioni": [
        {"celex": "02024R1689-20260727", "data": "2026-07-27",
         "modifiche": [{"celex": "32026R1744", "atto": "regolamento 2026/1744"},
                       {"celex": "32026R1744R(01)", "atto": "rettifica del regolamento 2026/1744"}]},
        {"celex": "02024R1689-20240712", "data": "2024-07-12",
         "modifiche": [{"celex": "32024R1689R(01)", "atto": "rettifica del regolamento 2024/1689"}]},
    ],
}


class _Cellar:
    """CELLAR's pages by URL, every request counted."""

    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def __call__(self, fonte, **kwargs):
        pages, asked = self.pages, self.asked

        class _Resp:
            def __init__(self, url, text):
                self.url, self.text, self.status_code = url, text, 200

            def raise_for_status(self):
                return None

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url):
                asked.append(url)
                if url not in pages:
                    raise AssertionError(f"unexpected request: {url}")
                return _Resp(url, pages[url])

        return _Client()


@pytest.fixture
def cellar(monkeypatch):
    pages = _Cellar({CELLAR + "32024R1689": OJ, CELLAR + "02024R1689-20260727": CONS,
                     CELLAR + "02024R1689-20240712": OJ})
    monkeypatch.setattr(scraper, "async_client", pages)
    return pages


@pytest.fixture
def lookup(monkeypatch):
    """The consolidation lookup, answering *risposta* and counting its calls."""
    state = {"risposta": AI_ACT, "chiamate": []}

    async def consolidazioni(celex_base):
        state["chiamate"].append(celex_base)
        return state["risposta"]

    monkeypatch.setattr(ec, "consolidazioni", consolidazioni)
    return state


def _sp(text):
    """The OJ text writes «2\xa0agosto»: compared with plain spaces here, served as it is."""
    return text.replace("\xa0", " ")


def _ai_act(**kw):
    return api.riferimento_da_parametri("regolamento ue", "111", data="2024", numero_atto="1689", **kw).norma_data[0]


class TestTheTextInForce:
    async def test_the_latest_consolidation_is_served(self, cellar, lookup):
        t = await api.testo_articolo(_ai_act(), canale="html")
        assert t.esito == "trovato"
        assert "prima della data di applicazione del capo III di cui all'articolo 113" in t.article_text
        assert "\n4. I fornitori di sistemi di IA" in t.article_text
        assert "prima del 2 agosto 2026, solo se" not in _sp(t.article_text)
        assert t.consolidato["celex"] == "02024R1689-20260727" and t.consolidato["data"] == "2026-07-27"
        assert [m["celex"] for m in t.consolidato["modificato_da"]] == ["32026R1744", "32026R1744R(01)"]
        assert t.consolidato_verificato is True and t.precisione == "INDICATIVO"
        assert "non fa fede" in t.avvisi[0] and "GUUE" in t.avvisi[0]
        assert t.url == "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:02024R1689-20260727"
        assert cellar.asked == [CELLAR + "02024R1689-20260727"] and lookup["chiamate"] == ["32024R1689"]

    async def test_the_text_is_visualex_s_reader_on_the_consolidated_page(self, cellar, lookup):
        from bs4 import BeautifulSoup

        from mcp_legal_it.lib.visualex.eurlex_text import extract_article_text

        t = await api.testo_articolo(_ai_act(), canale="html")
        assert t.article_text == extract_article_text(BeautifulSoup(CONS, "html.parser"), "111")

    async def test_a_consolidation_that_amends_nothing_is_the_oj_text(self, cellar, lookup):
        # Dir. 2019/790 has only 02019L0790-20190517: the base act again.
        lookup["risposta"] = {"data_gu": "2024-07-12", "in_vigore_dal": "2024-08-01",
                              "versioni": [{"celex": "02024R1689-20240712", "data": "2024-07-12", "modifiche": []}]}
        t = await api.testo_articolo(_ai_act(), canale="html")
        assert "prima del 2 agosto 2026, solo se" in _sp(t.article_text)
        assert t.consolidato is None and t.consolidato_verificato is True
        assert t.precisione == "ESATTO" and t.avvisi == ()
        assert cellar.asked == [CELLAR + "32024R1689"]

    async def test_no_consolidation_at_all_is_the_oj_text(self, cellar, lookup):
        lookup["risposta"] = {"data_gu": "2024-07-12", "in_vigore_dal": "2024-08-01", "versioni": []}
        t = await api.testo_articolo(_ai_act(), canale="html")
        assert t.consolidato is None and t.consolidato_verificato is True and t.precisione == "ESATTO"

    async def test_when_cellar_cannot_say_the_oj_text_comes_with_a_notice_first(self, cellar, lookup):
        lookup["risposta"] = None
        t = await api.testo_articolo(_ai_act(), canale="html")
        assert t.esito == "trovato" and "prima del 2 agosto 2026, solo se" in _sp(t.article_text)
        assert t.consolidato is None and t.consolidato_verificato is False
        assert t.precisione == "INDICATIVO"
        assert t.avvisi[0].startswith("non è stato possibile verificare su EUR-Lex se esiste una versione consolidata")


class TestTheOriginal:
    async def test_the_oj_text_on_request(self, cellar, lookup):
        t = await api.testo_articolo(_ai_act(versione="originale"), canale="html")
        assert "prima del 2 agosto 2026, solo se" in _sp(t.article_text)
        assert t.consolidato is None and t.consolidato_verificato is None
        assert t.precisione == "ESATTO" and t.avvisi == ()
        assert lookup["chiamate"] == [] and cellar.asked == [CELLAR + "32024R1689"]

    async def test_cite_law_asks_for_it_by_versione(self, cellar, lookup):
        from mcp_legal_it.tools import legal_citations as lc

        out = json.loads(await lc._cite_law_impl("art. 111 Regolamento UE 2024/1689", formato="json",
                                                 versione="originale"))
        assert "prima del 2 agosto 2026, solo se" in _sp(out["testo"])
        assert out["consolidato"] is None and out["consolidato_verificato"] is None and lookup["chiamate"] == []

    async def test_cite_law_refuses_another_versione(self):
        from mcp_legal_it.tools import legal_citations as lc

        out = await lc._cite_law_impl("art. 111 Regolamento UE 2024/1689", versione="storica")
        assert out.startswith("**Errore**: versione 'storica' non valida")

    async def test_cite_law_s_original_of_an_italian_act_is_normattiva_s(self, monkeypatch):
        from mcp_legal_it.core import norme
        from mcp_legal_it.tools import legal_citations as lc

        visti = []

        async def fetch(nv, canale="html"):
            visti.append(nv.url())
            return {"text": "Art. 2043. Testo del 1942.", "url": nv.url(), "source": "normattiva"}

        monkeypatch.setattr(lc, "fetch_norma", fetch)
        monkeypatch.setattr(norme, "fetch_norma", fetch)
        await lc._cite_law_impl("art. 2043 c.c.", versione="originale")
        await lc._cite_law_impl("art. 2043 c.c.", formato="json", versione="originale")
        assert visti and all(u.endswith("~art2043@originale") for u in visti)


class TestADate:
    async def test_the_latest_consolidation_not_after_the_day(self, cellar, lookup):
        t = await api.testo_articolo(_ai_act(data_versione="2025-01-01"), canale="html")
        assert t.consolidato["celex"] == "02024R1689-20240712" and t.precisione == "INDICATIVO"
        assert any("la più recente non successiva al 2025-01-01" in a and "ritardo" in a for a in t.avvisi)
        assert cellar.asked == [CELLAR + "02024R1689-20240712"]

    async def test_after_the_act_and_before_its_first_consolidation_is_the_oj_text(self, cellar, lookup):
        # Published on 12.7.2024, in force from 1.8.2024: on 20.7 it was the OJ text, not in force yet.
        lookup["risposta"] = {**AI_ACT, "versioni": [{**AI_ACT["versioni"][1], "data": "2024-07-25"},
                                                     AI_ACT["versioni"][0]]}
        t = await api.testo_articolo(_ai_act(data_versione="2024-07-20"), canale="html")
        assert t.esito == "trovato" and t.consolidato is None and "prima del 2 agosto 2026" in _sp(t.article_text)
        assert any("non ancora in vigore (in vigore dal 2024-08-01)" in a for a in t.avvisi)

    async def test_a_day_before_the_act_s_publication_is_not_valid(self, cellar, lookup):
        # Adopted on 13.6.2024, published on 12.7.2024: on 20.6 there was no act to read.
        t = await api.testo_articolo(_ai_act(data_versione="2024-06-20"), canale="html")
        assert t.esito == "riferimento_non_valido" and t.article_text == "" and cellar.asked == []
        assert "2024-07-12" in t.errore

    def test_a_consolidation_and_a_version_do_not_go_together(self):
        for kw in ({"versione": "originale"}, {"data_versione": "2025-01-01"}):
            r = api.riferimento_da_parametri("regolamento ue", "111", data="2024", numero_atto="1689",
                                             celex_consolidated="02024R1689-20260727", **kw)
            assert r.esito == "riferimento_non_valido"


class TestWhatIsNotLookedUp:
    async def test_a_treaty_is_unchanged(self, monkeypatch, lookup):
        from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

        async def pagina(norma):
            return "<html><body><p class=\"oj-ti-art\">Articolo 101</p><p>Testo.</p></body></html>", "u"

        monkeypatch.setattr(scraper, "_fetch_eurlex_html", pagina)
        r = await scraper.fetch_article(NormaVisitata(Norma("tfue"), "101"))
        assert r["consolidato"] is None and r["consolidato_verificato"] is None and lookup["chiamate"] == []

    async def test_a_recital_is_the_oj_one(self, monkeypatch, lookup):
        from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

        async def pagina(norma):
            assert not norma.celex_consolidated
            return "<html><body><p>(42) Il considerando.</p></body></html>", "u"

        monkeypatch.setattr(scraper, "_fetch_eurlex_html", pagina)
        r = await scraper.fetch_article(NormaVisitata(Norma("regolamento ue", "2024", "1689"), "rec_42"))
        assert r["consolidato"] is None and lookup["chiamate"] == []

    async def test_an_annex_is_the_oj_one_and_says_it_may_be_outdated(self, monkeypatch, lookup):
        from mcp_legal_it.core import norme

        async def pagina(norma):
            return ('<html><body><div id="anx_III"><p>ALLEGATO III</p><p>Sistemi ad alto rischio.</p></div>'
                    '</body></html>'), "u"

        monkeypatch.setattr(scraper, "_fetch_eurlex_html", pagina)
        base, _ = await norme._cite_law_lookup("Allegato III AI Act")
        assert lookup["chiamate"] == [] and base["consolidato"] is None
        q = norme.qualita_testo(base, {}, "allegato III")
        assert q["precisione"] == "INDICATIVO" and "allegato letto dal testo pubblicato in GUUE" in q["avvisi"][0]


class TestCiteLaw:
    async def test_the_markdown_names_the_consolidation_and_what_is_authentic(self, cellar, lookup):
        from mcp_legal_it.tools import legal_citations as lc

        out = await lc._cite_law_impl("art. 111 Regolamento UE 2024/1689")
        assert "**Testo consolidato** EUR-Lex al 2026-07-27 (CELEX 02024R1689-20260727)" in out
        assert "regolamento 2026/1744 (CELEX 32026R1744)" in out
        assert "fa fede solo il testo pubblicato in GUUE" in out
        assert "prima della data di applicazione del capo III" in out

    async def test_the_markdown_s_first_line_says_cellar_could_not_say(self, cellar, lookup):
        from mcp_legal_it.tools import legal_citations as lc

        lookup["risposta"] = None
        out = await lc._cite_law_impl("art. 111 Regolamento UE 2024/1689")
        assert out.startswith("**Attenzione**: non è stato possibile verificare su EUR-Lex")

    async def test_the_json_keys_are_always_there(self, cellar, lookup):
        from mcp_legal_it.tools import legal_citations as lc

        out = json.loads(await lc._cite_law_impl("art. 111 Regolamento UE 2024/1689", formato="json"))
        assert out["consolidato"]["celex"] == "02024R1689-20260727" and out["consolidato_verificato"] is True
        lookup["risposta"] = None
        ec._cache.clear()
        out = json.loads(await lc._cite_law_impl("art. 111 Regolamento UE 2024/1689", formato="json"))
        assert out["consolidato"] is None and out["consolidato_verificato"] is False
        assert out["avvisi"][0].startswith("non è stato possibile verificare")


class TestTheLookup:
    def test_the_answer_is_read(self):
        rows = [
            {"data_gu": {"value": "2024-07-12"}, "in_vigore": {"value": "2024-08-01"}, "celex": {"value": "02024R1689-20240712"},
             "data": {"value": "2024-07-12"}, "atti": {"value": "32024R1689|32024R1689R(01)"}},
            {"data_gu": {"value": "2024-07-12"}, "in_vigore": {"value": "2024-08-01"}, "celex": {"value": "02024R1689-20260727"},
             "data": {"value": "2026-07-27"}, "atti": {"value": "32024R1689|32026R1744|32026R1744R(01)"}},
        ]
        info = ec.leggi_risposta("32024R1689", rows)
        assert info["data_gu"] == "2024-07-12" and info["in_vigore_dal"] == "2024-08-01"
        assert [v["celex"] for v in info["versioni"]] == [
            "02024R1689-20260727", "02024R1689-20240712"]
        assert info["versioni"][0]["modifiche"][0] == {"celex": "32026R1744", "atto": "regolamento 2026/1744"}
        assert ec.leggi_risposta("32019L0790", [{"data_gu": {"value": "2019-05-17"}}]) == {
            "data_gu": "2019-05-17", "in_vigore_dal": None, "versioni": []}

    def test_a_consolidation_that_is_not_the_act_s_is_dropped(self):
        rows = [{"celex": {"value": c}, "data": {"value": "2026-07-27"}, "atti": {"value": "32026R1744"}}
                for c in ("02024R1689-20260727", "02016R0679-20260727", "02024R1689-2026072", "02024R1689-20260727/x")]
        assert [v["celex"] for v in ec.leggi_risposta("32024R1689", rows)["versioni"]] == ["02024R1689-20260727"]

    def test_labels(self):
        assert ec.etichetta("32026R1744") == "regolamento 2026/1744"
        assert ec.etichetta("32002L0058") == "direttiva 2002/58"
        assert ec.etichetta("32026R1744R(01)") == "rettifica del regolamento 2026/1744"
        assert ec.etichetta("32002L0058R(01)") == "rettifica della direttiva 2002/58"
        assert ec.etichetta("altro") == "altro"

    def test_the_choice(self):
        assert ec.scegli(AI_ACT, None, "2026-10-22")[1]["celex"] == "02024R1689-20260727"
        assert ec.scegli(AI_ACT, "2026-07-27")[1]["celex"] == "02024R1689-20260727"
        assert ec.scegli(AI_ACT, "2026-07-26")[1]["celex"] == "02024R1689-20240712"
        assert ec.scegli(AI_ACT, "2024-07-12")[1]["celex"] == "02024R1689-20240712"
        assert ec.scegli(AI_ACT, "2024-07-11") == ("prima", None)

    def test_a_consolidation_dated_after_today_is_not_the_text_in_force(self):
        # The review's case: -20271202 must not be served as in force on 22.10.2026.
        con_futura = {**AI_ACT, "versioni": [{"celex": "02024R1689-20271202", "data": "2027-12-02",
                                              "modifiche": [{"celex": "32027R0001", "atto": "regolamento 2027/1"}]},
                                             *AI_ACT["versioni"]]}
        assert ec.scegli(con_futura, None, "2026-10-22")[1]["celex"] == "02024R1689-20260727"
        assert ec.futura(con_futura, "2026-10-22") == {"change": "amended", "valid_from": "2027-12-02",
                                                        "version_number": None, "celex": "02024R1689-20271202"}
        assert ec.futura(AI_ACT, "2026-10-22") is None

    async def test_one_query_per_act_a_day_and_a_failure_kept_a_few_minutes(self, monkeypatch):
        import httpx

        ec._cache.clear()
        chieste, risposte = [], []

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        async def retry(client, method, url, *, dataset="", data=None, max_retries=2, **kw):
            assert max_retries == 0  # a hanging endpoint is not asked again within the call
            chieste.append((dataset, data["query"]))
            r = risposte.pop(0)
            if isinstance(r, Exception):
                raise r
            return httpx.Response(200, json=r, request=httpx.Request("POST", url))

        monkeypatch.setattr(ec, "async_client", lambda fonte, **kw: _Client())
        monkeypatch.setattr(ec, "retry_request", retry)
        risposte.extend([httpx.ConnectError("down"), {"results": {"bindings": [
            {"data_gu": {"value": "2024-07-12"}}]}}])
        assert await ec.consolidazioni("32024R1689") is None
        assert await ec.consolidazioni("32024R1689") is None  # the failure is remembered: no second wait
        assert len(chieste) == 1
        with ec._lock:  # five minutes later
            ec._cache["32024R1689"] = (ec._cache["32024R1689"][0] - ec.NEGATIVO_SECONDI - 1, None)
        assert (await ec.consolidazioni("32024R1689"))["data_gu"] == "2024-07-12"
        assert (await ec.consolidazioni("32024R1689"))["data_gu"] == "2024-07-12"
        assert len(chieste) == 2 and chieste[0][0] == "eur_lex" and '"32024R1689"' in chieste[0][1]
        assert ec._TIMEOUT.read <= 15
        ec._cache.clear()

    async def test_only_an_oj_celex_reaches_the_query(self):
        for bad in ('32024R1689" } ; DROP', "02024R1689-20260727", "", None):
            assert await ec.consolidazioni(bad) is None


def test_a_consolidation_of_corrigenda_only_says_so():
    # The GDPR's only consolidation (02016R0679-20160504) folds in the Italian corrigenda.
    gdpr = {"celex": "02016R0679-20160504", "data": "2016-05-04",
            "modificato_da": [{"celex": "32016R0679R(01)", "atto": "rettifica del regolamento 2016/679"},
                              {"celex": "32016R0679R(02)", "atto": "rettifica del regolamento 2016/679"}]}
    assert ec.avvisi(gdpr, True, None)[0].startswith(
        "testo consolidato EUR-Lex che incorpora le rettifiche pubblicate in GUUE, al 2016-05-04")
    amended = AI_ACT["versioni"][0]
    first = ec.avvisi({**amended, "modificato_da": amended["modifiche"]}, True, None)[0]
    assert first.startswith("testo consolidato EUR-Lex, al 2026-07-27") and "rettifiche" not in first



class TestEndToEnd:
    async def test_a_consolidation_not_applicable_yet_is_said(self, cellar, lookup):
        lookup["risposta"] = {**AI_ACT, "versioni": [
            {"celex": "02024R1689-20990101", "data": "2099-01-01",
             "modifiche": [{"celex": "32098R0001", "atto": "regolamento 2098/1"}]}, *AI_ACT["versioni"]]}
        t = await api.testo_articolo(_ai_act(), canale="html")
        assert t.consolidato["celex"] == "02024R1689-20260727"
        assert t.upcoming == {"change": "amended", "valid_from": "2099-01-01", "version_number": None,
                              "celex": "02024R1689-20990101"}
        assert any("applicabile dal 2099-01-01" in a for a in t.avvisi)

    async def test_the_gdpr_is_its_corrigenda_consolidation(self, monkeypatch, lookup):
        # 32016R0679 has one consolidation, 02016R0679-20160504, folding in the corrigenda only.
        lookup["risposta"] = {"data_gu": "2016-05-04", "in_vigore_dal": "2016-05-24", "versioni": [
            {"celex": "02016R0679-20160504", "data": "2016-05-04",
             "modifiche": [{"celex": "32016R0679R(02)", "atto": "rettifica del regolamento 2016/679"}]}]}
        cons = ('<html><body><div class="eli-subdivision" id="art_7"><p class="title-article-norm">Articolo 7</p>'
                '<p class="stitle-article-norm">Condizioni per il consenso</p><p class="norm">1. Qualora il '
                'trattamento sia basato sul consenso, il titolare del trattamento deve essere in grado di dimostrare '
                'che l\'interessato ha prestato il proprio consenso al trattamento dei propri dati personali.</p>'
                '</div></body></html>')
        pages = _Cellar({CELLAR + "02016R0679-20160504": cons})
        monkeypatch.setattr(scraper, "async_client", pages)
        nd = api.riferimento_da_parametri("regolamento ue", "7", data="2016", numero_atto="679").norma_data[0]
        t = await api.testo_articolo(nd, canale="html")
        assert "ha prestato il proprio consenso" in t.article_text and t.precisione == "INDICATIVO"
        assert t.avvisi[0].startswith("testo consolidato EUR-Lex che incorpora le rettifiche pubblicate in GUUE")
        assert pages.asked == [CELLAR + "02016R0679-20160504"]

    async def test_a_directive_with_only_its_initial_consolidation_is_the_oj_text(self, monkeypatch, lookup):
        # Dir. 2019/790: 02019L0790-20190517 consolidates nothing but the base act.
        lookup["risposta"] = {"data_gu": "2019-05-17", "in_vigore_dal": "2019-06-06", "versioni": [
            {"celex": "02019L0790-20190517", "data": "2019-05-17", "modifiche": []}]}
        oj = ('<html><body><div class="eli-subdivision" id="art_17"><p class="oj-ti-art">Articolo 17</p>'
              '<p class="oj-sti-art">Utilizzo di contenuti protetti</p><p class="oj-normal">1. Testo.</p>'
              '</div></body></html>')
        pages = _Cellar({CELLAR + "32019L0790": oj})
        monkeypatch.setattr(scraper, "async_client", pages)
        nd = api.riferimento_da_parametri("direttiva ue", "17", data="2019", numero_atto="790").norma_data[0]
        t = await api.testo_articolo(nd, canale="html")
        assert t.consolidato is None and t.consolidato_verificato is True and t.precisione == "ESATTO"
        assert pages.asked == [CELLAR + "32019L0790"]
