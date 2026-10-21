"""Normattiva's article tree (VisuaLex's treextractor, Normattiva half) and the existence check.

The tree variants test and the existence/where-else cases are VisuaLex's
(tests/test_tree_variants.py and tests/test_article_existence.py at eca698dc), on the pure
functions this package exposes instead of VisuaLex's Quart controller. No network.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from mcp_legal_it import api
from mcp_legal_it.api.tipi import AlberoAtto
from mcp_legal_it.lib.visualex import albero_normattiva as albero
from mcp_legal_it.lib.visualex import pagine_normattiva, scraper
from mcp_legal_it.lib.visualex.akn_parser import parse_akn
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "akn"
LANDING = (FIXTURES / "landing_legge_241_1990.html").read_text(encoding="utf-8")
L241 = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241"
VARIANTS = [(link, details, metadata)
            for link in (False, True) for details in (False, True) for metadata in (False, True)]


# ---------------------------------------------------------------------------
# VisuaLex's test_tree_variants: every variant is the narrowed widest tree
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("link,details,metadata", VARIANTS)
def test_every_variant_is_the_narrowed_widest_tree(link, details, metadata):
    direct = albero._parse_normattiva_tree(BeautifulSoup(LANDING, "html.parser"), L241, link,
                                           details, return_metadata=metadata)
    full = albero._parse_normattiva_tree(BeautifulSoup(LANDING, "html.parser"), L241, link,
                                         True, return_metadata=True)
    assert full[1] > 0 and any(isinstance(entry, str) for entry in full[0])
    assert albero._narrow(*full, details, metadata) == direct


def test_the_tree_of_l_241_1990():
    articles, count, metadata = albero._parse_normattiva_tree(
        BeautifulSoup(LANDING, "html.parser"), L241, True, False, return_metadata=True)
    assert count == 51
    assert articles[0] == {"numero": "1", "allegato": None, "url": f"{L241}~art1"}
    # The tree spells a suffix with a space; the URL joins it (VisuaLex's _generate_article_url).
    assert {"numero": "2 bis", "allegato": None, "url": f"{L241}~art2bis"} in articles
    assert [(a["number"], a["label"], a["article_count"]) for a in metadata["annexes"]] == [(None, "Dispositivo", 51)]


# ---------------------------------------------------------------------------
# VisuaLex's test_article_existence, on the pure functions
# ---------------------------------------------------------------------------

TREE = [{"numero": "1", "allegato": None}, {"numero": "2", "allegato": None},
        {"numero": "2-bis", "allegato": None}, {"numero": "3", "allegato": None}]

# Captured from live Normattiva by VisuaLex on 2026-08-26: the tree spells every suffix
# with a space and goes far past "decies".
REAL_SUFFIX_TREE = [{"numero": n, "allegato": None} for n in (
    "281 undecies", "669 terdecies", "452 quaterdecies", "518 duodevicies", "2409 octiesdecies",
    "2409 noviesdecies", "25 undecies", "25 quinquiesdecies", "25 septiesdecies", "25 undevicies",
    "25 bis.1", "2409 duodecies.1")]

# D.lgs. 104/2010 as Normattiva's tree gives it: the c.p.a. is its annex 2 (the act calls it
# «Allegato 1»), the decree's own text has five articles.
CPA_TREE = ([{"numero": str(n), "allegato": None} for n in range(1, 6)]
            + [{"numero": str(n), "allegato": 2} for n in range(1, 41)])


class TestExistence:
    @pytest.mark.parametrize("article", ["1", "2-bis", "3"])
    def test_existing_articles_pass(self, article):
        assert albero.articolo_nell_albero(TREE, article) is True

    @pytest.mark.parametrize("article", ["99999", "7000", "4"])
    def test_missing_articles_are_reported(self, article):
        assert albero.articolo_nell_albero(TREE, article) is False

    def test_bis_spelling_variants_match(self):
        assert albero.articolo_nell_albero([{"numero": "2 bis", "allegato": None}], "2-bis") is True

    @pytest.mark.parametrize("article", [
        "281-undecies", "669-terdecies", "452-quaterdecies", "518-duodevicies", "2409-octiesdecies",
        "2409-noviesdecies", "25-undecies", "25-quinquiesdecies", "25-septiesdecies", "25-undevicies",
        "25 undecies", "669 terdecies", "25-bis.1", "2409-duodecies.1",
    ])
    def test_suffixes_beyond_decies_match_in_any_spelling(self, article):
        assert albero.articolo_nell_albero(REAL_SUFFIX_TREE, article) is True

    def test_a_genuinely_absent_suffixed_article_is_still_reported(self):
        assert albero.articolo_nell_albero(REAL_SUFFIX_TREE, "25-vicies") is False
        assert albero.articolo_nell_albero(REAL_SUFFIX_TREE, "670-terdecies") is False

    @pytest.mark.parametrize("tree", ["Failed to retrieve the page: boom", "Empty response from server", []])
    def test_an_unreadable_tree_cannot_tell(self, tree):
        assert albero.articolo_nell_albero(tree, "1") is None

    def test_the_article_is_matched_within_the_requested_part(self):
        assert albero.articolo_nell_albero(CPA_TREE, "29", "2") is True
        assert albero.articolo_nell_albero(CPA_TREE, "29", "") is False
        assert albero.articolo_nell_albero(CPA_TREE, "3", "") is True


class TestWhereElse:
    @pytest.mark.parametrize("article,annex,hint", [
        ("29", "1", ": su Normattiva l'art. 29 si trova nell'allegato 2"),
        ("3", "2", ": su Normattiva l'art. 3 si trova nel testo dell'atto"),
        ("3", "1", ": su Normattiva l'art. 3 si trova nel testo dell'atto e nell'allegato 2"),
        ("99", "1", ""),
    ])
    def test_the_hint_names_the_other_parts(self, article, annex, hint):
        assert albero.dove_altrove(CPA_TREE, article, annex) == hint

    def test_string_and_integer_annexes_read_alike(self):
        tree = [{"numero": "1", "allegato": None}, {"numero": "29", "allegato": "2"}]
        assert albero.dove_altrove(tree, "29", 1) == ": su Normattiva l'art. 29 si trova nell'allegato 2"

    @pytest.mark.parametrize("tree", ["Errore di rete", []])
    def test_an_unreadable_tree_gives_no_hint(self, tree):
        assert albero.dove_altrove(tree, "29", "1") == ""


# ---------------------------------------------------------------------------
# The API: albero_atto, articolo_nell_albero, dove_altrove
# ---------------------------------------------------------------------------

def _serve_landing(monkeypatch, page=LANDING):
    richieste = []

    class _Risposta:
        def __init__(self, url, text):
            self.url, self.text, self.status_code = url, text, 200

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            richieste.append(url)
            return _Risposta(url, page)

    monkeypatch.setattr(scraper.httpx, "AsyncClient", _Client)
    pagine_normattiva.svuota_memoria()
    return richieste


class TestAlberoAtto:
    async def test_one_page_serves_every_variant_and_is_kept(self, monkeypatch):
        richieste = _serve_landing(monkeypatch)
        l241 = api.riferimento_da_parametri("legge", "", data="1990-08-07", numero_atto="241").norma_data[0]
        a = await api.albero_atto(l241)
        b = await api.albero_atto(l241, link=True, dettagli=True)
        assert richieste == [L241]
        assert a.esito == "trovato" and a.count == 51
        assert all(isinstance(e, dict) and "url" not in e for e in a.articles)
        assert any(isinstance(e, str) for e in b.articles) and b.articles[1]["url"] == f"{L241}~art1"
        assert a.metadata["annexes"][0]["label"] == "Dispositivo"

    async def test_a_code_is_read_from_its_act_not_its_default_part(self, monkeypatch):
        richieste = _serve_landing(monkeypatch)
        await api.albero_atto("c.c.")
        assert richieste == ["https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262"]

    async def test_a_page_without_a_tree_is_an_error_and_is_not_kept(self, monkeypatch):
        richieste = _serve_landing(monkeypatch, page="<html><body>" + "x" * 600 + "</body></html>")
        l241 = api.riferimento_da_parametri("legge", "", data="1990-08-07", numero_atto="241").norma_data[0]
        t = await api.albero_atto(l241)
        assert t.esito == "errore_fonte"
        await api.albero_atto(l241)
        assert len(richieste) == 2
        assert api.articolo_nell_albero(t, "1") is None and api.dove_altrove(t, "1", "") == ""

    async def test_eu_acts_have_no_tree(self):
        assert (await api.albero_atto("GDPR")).esito == "non_supportata"

    def test_existence_on_the_api_type(self):
        t = AlberoAtto(esito="trovato", articles=tuple(CPA_TREE), count=len(CPA_TREE))
        assert api.articolo_nell_albero(t, "29", "2") is True
        assert api.dove_altrove(t, "29", "1") == ": su Normattiva l'art. 29 si trova nell'allegato 2"


# ---------------------------------------------------------------------------
# testo_articolo: the hint, from the export, on an article the act does not have there
# ---------------------------------------------------------------------------

class TestHintOnRefusal:
    def _result(self, act, nv):
        result = {"text": "x", "url": nv.url(), "source": "normattiva", "data_atto": nv.norma.data}
        return scraper._checked_html_article(result, nv, "1", act, None)

    def test_an_annex_article_asked_in_the_body_is_pointed_to_its_part(self):
        act = parse_akn((FIXTURES / "dlgs_36_2023_positions.xml").read_text(encoding="utf-8"))
        # Art. 32-ter is only in Allegato I.7, Normattiva's part 8.
        nv = NormaVisitata(Norma("decreto legislativo", "2023-03-31", "36"), "32-ter")
        out = self._result(act, nv)
        assert out["esito"] == "articolo_non_trovato"
        assert out["error"].endswith(": su Normattiva l'art. 32-ter si trova nell'allegato 8")

    def test_a_codes_default_part_gets_no_hint(self):
        # Art. 40 of the preleggi is not art. 40 of the codice civile.
        act = parse_akn((FIXTURES / "codice_civile.xml").read_text(encoding="utf-8"))
        nv = NormaVisitata(Norma("preleggi"), "40")
        out = scraper._checked_html_article({"text": "x", "url": nv.url(), "source": "normattiva"},
                                            nv, "1", act, "preleggi")
        assert out["esito"] == "articolo_non_trovato" and "si trova" not in out["error"]


# ---------------------------------------------------------------------------
# indice_atto from the export: VisuaLex's /fetch_rubriche
# ---------------------------------------------------------------------------

def _serve_export(monkeypatch, act):
    from mcp_legal_it.lib.visualex import akn_fetch

    async def fake(norma, data_vigenza=None):
        return act

    async def same(norma):
        return norma

    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", fake)
    monkeypatch.setattr(scraper, "with_full_date", same)


class TestIndiceDaExport:
    async def test_title_rubriche_abrogati_and_parts(self, monkeypatch):
        _serve_export(monkeypatch, parse_akn((FIXTURES / "legge_654_1975.xml").read_text(encoding="utf-8")))
        i = await api.indice_atto("l. 654/1975")
        assert i.esito == "trovato" and i.voci == ()
        assert i.abrogati == ("3",)
        assert i.title and "(" not in i.title[-12:]  # the Gazzetta code is gone
        convenzione = next(p for p in i.parts if p["name"] == "Convenzione")
        assert convenzione["allegato"] == "2" and convenzione["keys"][:3] == ["1", "2", "3"]
        assert set(convenzione) == {"name", "keys", "rubriche", "abrogati", "allegato"}

    async def test_a_code_with_its_preleggi_and_dispositivo(self, monkeypatch):
        _serve_export(monkeypatch, parse_akn((FIXTURES / "codice_civile.xml").read_text(encoding="utf-8")))
        i = await api.indice_atto("c.c.")
        assert i.rubriche["2043"] == "Risarcimento per fatto illecito" and i.count == len(i.rubriche)
        by_name = {p["name"]: p for p in i.parts}
        assert by_name["Disposizioni sulla legge in generale"]["allegato"] == "1"
        assert by_name["CODICE CIVILE"]["allegato"] == "2"
        # The Dispositivo has its own art. 1, with no rubrica: never the code's "Capacità giuridica".
        assert by_name["Dispositivo"]["allegato"] is None
        assert "1" not in by_name["Dispositivo"]["rubriche"]

    async def test_without_the_export_vedirubriche_answers(self, monkeypatch):
        from unittest.mock import AsyncMock

        _serve_export(monkeypatch, None)
        result = {"index": ["1-  Soggetti"], "codice_redazionale": "C", "data_gu": "2001-06-19", "url": "u"}
        monkeypatch.setattr("mcp_legal_it.api._norme.fetch_act_index", AsyncMock(return_value=result))
        i = await api.indice_atto("D.Lgs. 231/2001")
        assert i.rubriche == {"1": "Soggetti"} and i.voci == ("1-  Soggetti",) and i.parts == ()
