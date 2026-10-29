"""``api.modifiche_articolo``: an article's versions and amendments. Network mocked.

The pages are copies of what Normattiva served on 29 Oct 2026 (``tests/fixtures/normattiva/
aggiornamenti``, see its README): per article, the article page (trimmed), each version's
page and each version's update table.
"""

import dataclasses
import re
from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import act_dates, aggiornamenti, scraper

DIR = Path(__file__).resolve().parents[1] / "fixtures" / "normattiva" / "aggiornamenti"
ERRORE = (Path(__file__).resolve().parents[1] / "fixtures" / "normattiva" / "landing_atto_inesistente.html"
          ).read_text(encoding="utf-8")
ART_99999 = (Path(__file__).resolve().parents[1] / "fixtures" / "normattiva" / "cc_n2ls_art99999.html"
             ).read_text(encoding="utf-8")

N2LS = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LEGAL_TODAY", "2026-10-29")
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    act_dates.svuota_memoria()
    api.configura()
    yield
    api.configura()


def _pagina(nome: str) -> str:
    return (DIR / f"{nome}.html").read_text(encoding="utf-8")


def _normattiva(insieme: str, chieste: list, eccezioni: dict | None = None):
    """A client factory serving *insieme*'s pages: the article page, ``_v{k}`` and ``_agg_v{k}``.

    *eccezioni* maps ``"pagina"``, ``"v{k}"`` or ``"agg{k}"`` to another answer.
    """
    eccezioni = eccezioni or {}

    def handler(request):
        url = str(request.url)
        chieste.append(url)
        versione = re.search(r"art\.versione=(\d+)", url)
        if "uri-res/N2Ls" in url:
            chiave, nome = "pagina", insieme
        elif "caricaArticolo" in url:
            chiave, nome = f"v{versione.group(1)}", f"{insieme}_v{versione.group(1)}"
        elif "vediAggiornamentiAllArticolo" in url:
            chiave, nome = f"agg{versione.group(1)}", f"{insieme}_agg_v{versione.group(1)}"
        else:
            return httpx.Response(404)
        risposta = eccezioni.get(chiave)
        if isinstance(risposta, Exception):
            raise risposta
        if isinstance(risposta, httpx.Response):
            return risposta
        if isinstance(risposta, str):
            return httpx.Response(200, text=risposta)
        if not (DIR / f"{nome}.html").exists():
            return httpx.Response(404)
        return httpx.Response(200, text=_pagina(nome))

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


async def _modifiche(insieme, riferimento, eccezioni=None, **kwargs):
    chieste: list = []
    with api.configurazione(client_factory=_normattiva(insieme, chieste, eccezioni)):
        return await api.modifiche_articolo(riferimento, **kwargs), chieste


def _rif(tipo, articolo, data, numero):
    return api.riferimento_da_parametri(tipo, articolo, data, numero).norma_data[0]


ART_2TER = "art. 2-ter d.lgs. 196/2003"
ART_13 = "art. 13 d.lgs. 196/2003"
DPR131_ART1 = ("decreto del presidente della repubblica", "1", "1986-04-26", "131")
CCII_64BIS = ("decreto legislativo", "64-bis", "2019-01-12", "14")


def _versioni(r):
    return [(v.version_number, v.valid_from, v.valid_to) for v in r.versioni]


def _righe(r):
    return [(m.versione, m.in_vigore_dal, m.tipo, m.atto.tipo_atto, m.atto.numero_atto, m.disposizione, m.parti)
            for m in r.modifiche]


class TestStoria:
    async def test_a_decree_law_and_its_conversion_are_distinct_amendments(self):
        r, chieste = await _modifiche("dlgs196_art2ter", ART_2TER)
        assert r.esito == "trovato" and r.completa and r.precisione == "ESATTO" and r.errore is None
        assert _versioni(r) == [(1, "2018-09-19", "2021-10-08"), (2, "2021-10-09", "2021-12-07"), (3, "2021-12-08", None)]
        assert _righe(r) == [
            # Version 2: the decree-law as it was published.
            (2, "2021-10-09", "inserimento", "decreto legge", "139", "art. 9, comma 1, lettera a)", "comma 1-bis"),
            (2, "2021-10-09", "modifica", "decreto legge", "139", "art. 9, comma 1, lettera a)", "commi 2 e 3"),
            # Version 3: the decree-law as converted «con modificazioni», and the conversion law.
            (3, "2021-12-08", "modifica", "decreto legge", "139", "art. 9, comma 1, lettera a)", "commi 1, 1-bis, 2 e 3"),
            (3, "2021-12-08", "modifica", "decreto legge", "139", "art. 9, comma 5", "comma 1"),
            (3, "2021-12-08", "conversione", "legge", "205", "art. 1, comma 1", None),
        ]
        dl = r.modifiche[0].atto
        assert dl.urn == "urn:nir:stato:decreto.legge:2021-10-08;139" and dl.gazzetta == "G.U. 08/10/2021, n.241"
        assert r.modifiche[0].data_gu == "2021-10-08"  # published the day before it came into force
        assert "convertito con modificazioni dalla L. 3 dicembre 2021, n. 205" in r.modifiche[2].atto.descrizione
        assert r.modifiche[3].testo == "ha disposto (con l'art. 9, comma 5) la modifica dell'art. 2-ter, comma 1"
        assert r.url == N2LS + "decreto.legislativo:2003-06-30;196~art2ter"
        assert r.norma_data.urn == "urn:nir:stato:decreto.legislativo:2003-06-30;196~art2ter"
        assert r.avvisi == (
            "la versione 1 è il testo con cui l'articolo è entrato nell'atto: l'atto che lo ha introdotto non "
            "compare nella tabella degli aggiornamenti",)
        assert len(chieste) == 5  # 2V-1: the article page, versions 2 and 1, tables 3 and 2
        assert r.fonti is not None and r.versioni_non_lette == 0

    async def test_an_abrogated_article_ends_with_its_abrogation(self):
        r, chieste = await _modifiche("dlgs196_art13", ART_13)
        assert r.completa and r.precisione == "ESATTO"
        assert _versioni(r) == [(1, "2004-01-01", "2009-02-28"), (2, "2009-03-01", "2009-11-24"),
                                (3, "2009-11-25", "2011-07-12"), (4, "2011-07-13", "2018-09-18"),
                                (5, "2018-09-19", None)]
        assert [(m.versione, m.tipo, m.atto.numero_atto) for m in r.modifiche] == [
            (2, "modifica", "207"), (3, "modifica", "135"), (4, "inserimento", "70"), (5, "abrogazione", "101")]
        # An act that amends the article by amending the act that amended it.
        assert r.modifiche[1].testo.startswith("ha conseguentemente disposto (con l'art. 20-bis, comma 3)")
        assert len(chieste) == 9

    async def test_a_change_published_and_not_yet_in_force(self):
        # Without a date, Normattiva serves version 2, in force from 1 January 2027, as the article.
        r, _ = await _modifiche("dpr131_art1", _rif(*DPR131_ART1))
        assert _versioni(r) == [(1, "1986-07-01", "2026-12-31"), (2, "2027-01-01", None)]
        assert _righe(r) == [(2, "2027-01-01", "abrogazione", "decreto legislativo", "123",
                              "art. 204, comma 1, lettera f)", None)]
        assert r.modifiche[0].atto.gazzetta == "SO n.29, relativo alla G.U. 12/08/2025, n.186"
        assert any(a.startswith("la versione 2 entra in vigore il 2027-01-01: non è ancora in vigore")
                   for a in r.avvisi)

    async def test_a_code_article_is_read_in_the_code(self):
        r, chieste = await _modifiche("cc_art2", "art. 2 c.c.")
        assert chieste[0] == N2LS + "regio.decreto:1942-03-16;262:2~art2"  # the code, not its decree
        assert _versioni(r) == [(1, "1942-04-19", "1975-03-09"), (2, "1975-03-10", None)]
        assert _righe(r) == [(2, "1975-03-10", "modifica", "legge", "39", "art. 1, comma 1", None)]

    async def test_one_provision_with_several_actions(self):
        r, _ = await _modifiche("ccii_art64bis", _rif(*CCII_64BIS))
        assert [(m.versione, m.tipo, m.parti) for m in r.modifiche] == [
            (2, "inserimento", "comma 1-bis"), (2, "modifica", "comma 4, lettera a)"), (2, "modifica", "comma 8"),
            (2, "modifica", "comma 9"), (2, "inserimento", "comma 9-bis"), (3, "modifica", "comma 1-bis")]

    async def test_an_article_never_amended(self):
        r, chieste = await _modifiche("cc_art2740", "art. 2740 c.c.")
        assert r.esito == "trovato" and r.completa and r.precisione == "ESATTO"
        assert _versioni(r) == [(1, "1942-04-19", None)] and r.modifiche == () and r.avvisi == ()
        assert len(chieste) == 1

    async def test_identical_rows_are_kept_once(self):
        # The same table served for versions 2 and 3: its rows are kept at version 2 only.
        tabella = _pagina("dlgs196_art2ter_agg_v3")
        r, _ = await _modifiche("dlgs196_art2ter", ART_2TER, {"agg2": tabella})
        assert [m.versione for m in r.modifiche] == [2, 2, 2]


class TestPeriodo:
    async def test_dal_al_are_inclusive_and_on_the_entry_into_force(self):
        r, chieste = await _modifiche("dlgs196_art13", ART_13, dal="2011-07-13", al="2018-09-19")
        assert [m.versione for m in r.modifiche] == [4, 5]
        assert r.completa and len(r.versioni) == 5
        # The article page, table 5, version 4 and table 4, version 3 (before dal: the walk stops).
        assert len(chieste) == 5

    async def test_the_gazzetta_date_is_not_the_filter(self):
        # Abrogation by d.lgs. 101/2018: G.U. 4 Sept 2018, in force 19 Sept 2018.
        r, _ = await _modifiche("dlgs196_art13", ART_13, dal="2018-09-05")
        assert [(m.versione, m.data_gu, m.in_vigore_dal) for m in r.modifiche] == [(5, "2018-09-04", "2018-09-19")]

    async def test_al_before_a_future_change_leaves_it_out_unread(self):
        r, chieste = await _modifiche("dpr131_art1", _rif(*DPR131_ART1), al="2026-12-31")
        assert r.modifiche == () and r.completa
        assert not any("vediAggiornamentiAllArticolo" in u for u in chieste)

    async def test_without_a_window_the_gazzetta_date_filters_and_is_indicative(self):
        # Version 4's page without its validity block: its amendment has no in_vigore_dal.
        senza = re.sub(r'<div class="vigore[\s\S]*?</div>', "", _pagina("dlgs196_art13_v4"), count=1)
        r, _ = await _modifiche("dlgs196_art13", ART_13, {"v4": senza}, dal="2011-01-01", al="2011-12-31")
        assert [(m.versione, m.in_vigore_dal, m.data_gu, m.precisione) for m in r.modifiche] == [
            (4, None, "2011-05-13", "INDICATIVO")]
        assert r.precisione == "INDICATIVO"
        assert any("data di pubblicazione in Gazzetta" in a for a in r.avvisi)

    @pytest.mark.parametrize("kwargs", [{"dal": "13/07/2011"}, {"al": "2011-02-30"}, {"dal": "2012-01-01", "al": "2011-01-01"}])
    async def test_a_bad_period_is_refused_before_any_request(self, kwargs):
        r, chieste = await _modifiche("dlgs196_art13", ART_13, **kwargs)
        assert r.esito == "riferimento_non_valido" and chieste == []


class TestTetto:
    async def test_the_ceiling_reads_the_newest_versions(self):
        r, chieste = await _modifiche("dlgs196_art13", ART_13, max_versioni=2)
        assert [m.versione for m in r.modifiche] == [4, 5]
        assert not r.completa and r.precisione == "INDICATIVO" and r.versioni_non_lette == 3
        assert _versioni(r)[:3] == [(1, None, None), (2, None, None), (3, None, None)]
        assert any(a.startswith("lette le ultime 2 versioni su 5") for a in r.avvisi)
        assert len(chieste) == 4

    @pytest.mark.parametrize("valore", [0, -1, True, "20"])
    async def test_a_ceiling_below_one_is_a_programming_error(self, valore):
        with pytest.raises(ValueError):
            await api.modifiche_articolo(ART_13, max_versioni=valore)


class TestFallimenti:
    @pytest.mark.parametrize("guasto", [httpx.Response(503), httpx.Response(429), httpx.ConnectError("giù"), ERRORE])
    async def test_a_version_that_fails_stops_the_walk_and_says_so(self, guasto):
        r, _ = await _modifiche("dlgs196_art13", ART_13, {"agg3": guasto})
        assert r.esito == "trovato" and not r.completa and r.precisione == "INDICATIVO"
        assert [m.versione for m in r.modifiche] == [4, 5]  # never a gap filled
        assert r.versioni_non_lette == 3
        assert any(a.startswith("versioni non lette per un errore della fonte: 1, 2, 3") and "riprovare" in a
                   for a in r.avvisi)

    async def test_a_version_page_of_another_article_is_a_failure(self):
        r, _ = await _modifiche("dlgs196_art13", ART_13, {"v4": _pagina("dlgs196_art2ter_v2")})
        assert not r.completa and [m.versione for m in r.modifiche] == [5]

    @pytest.mark.parametrize("pagina", [ERRORE, httpx.Response(503), httpx.Response(429), httpx.ConnectError("giù"),
                                        httpx.Response(202, content=b"")])
    async def test_an_unreadable_article_page_is_transient_never_missing(self, pagina):
        r, _ = await _modifiche("dlgs196_art13", ART_13, {"pagina": pagina})
        assert r.esito == "verifica_non_disponibile" and r.modifiche == () and not r.completa
        assert r.errore

    async def test_the_page_of_another_article_means_it_does_not_exist(self):
        r, _ = await _modifiche("cc_art2", "art. 99999 c.c.", {"pagina": ART_99999})
        assert r.esito == "articolo_non_trovato" and "art. 1" in r.errore


class TestRifiuti:
    @pytest.mark.parametrize("riferimento, esito", [
        ("d.lgs. 196/2003", "non_supportata"),  # the whole act: never its art. 1
        ("art. 6 GDPR", "non_supportata"),
        ("allegato I.7 art. 30 D.Lgs. 36/2023", "non_supportata"),
        ("art. 1 pippo", "atto_non_riconosciuto"),
    ])
    async def test_refused_before_any_request(self, riferimento, esito):
        r, chieste = await _modifiche("dlgs196_art13", riferimento)
        assert r.esito == esito and chieste == [] and r.errore

    async def test_an_act_without_an_article_is_never_its_art_1(self):
        nd = api.riferimento_da_parametri("decreto legislativo", "", "2003-06-30", "196").norma_data[0]
        r, chieste = await _modifiche("dlgs196_art13", nd)
        assert r.esito == "non_supportata" and "serve un articolo" in r.errore and chieste == []


class TestCache:
    async def test_past_versions_are_read_from_the_cache_and_the_answer_is_the_same(self, tmp_path):
        prima, chieste = await _modifiche("dlgs196_art2ter", ART_2TER)
        assert len(chieste) == 5
        poi, chieste = await _modifiche("dlgs196_art2ter", ART_2TER)
        # The article page and the current version's table are read every time.
        assert len(chieste) == 2 and all("caricaArticolo" not in u for u in chieste)
        assert dataclasses.replace(poi, fonti=None) == dataclasses.replace(prima, fonti=None)
        assert len(list((tmp_path / "cache" / "normattiva_aggiornamenti").glob("*.json"))) == 2

    async def test_nothing_on_disk_with_the_cache_off(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LEGAL_CACHE", "off")
        await _modifiche("dlgs196_art2ter", ART_2TER)
        _, chieste = await _modifiche("dlgs196_art2ter", ART_2TER)
        assert len(chieste) == 5 and not (tmp_path / "cache").exists()

    async def test_a_failed_version_is_never_kept(self, tmp_path):
        await _modifiche("dlgs196_art13", ART_13, {"agg3": httpx.Response(503)})
        r, chieste = await _modifiche("dlgs196_art13", ART_13)
        assert r.completa and [m.versione for m in r.modifiche] == [2, 3, 4, 5]
        # Version 4, read whole before the failure, comes from the cache; 3, 2 and 1 are read.
        assert not any("art.versione=4" in u for u in chieste)

    async def test_an_expired_record_is_read_again(self, tmp_path, monkeypatch):
        await _modifiche("dlgs196_art2ter", ART_2TER)
        monkeypatch.setattr(aggiornamenti, "TTL_SECONDI", -1)
        _, chieste = await _modifiche("dlgs196_art2ter", ART_2TER)
        assert len(chieste) == 5


class TestParser:
    def test_a_row_with_a_conversion_law(self):
        righe = aggiornamenti.parse_righe(_pagina("dlgs196_art13_agg_v2"))
        atto = righe[0]["atti"][0]["atto"]
        assert (atto["tipo_atto"], atto["data"], atto["numero_atto"], atto["data_gu"]) == (
            "decreto legge", "2008-12-30", "207", "2008-12-31")
        assert "convertito con modificazioni dalla L. 27 febbraio 2009, n. 14" in atto["descrizione"]

    def test_an_error_page_has_no_table(self):
        assert aggiornamenti.parse_righe(ERRORE) is None

    def test_the_version_links_are_the_articles_own(self):
        pagina = _pagina("dlgs196_art13")
        link = aggiornamenti.update_link(pagina)
        assert aggiornamenti.link_version(link) == 5
        assert sorted(aggiornamenti.version_pages(pagina, link)) == [1, 2, 3, 4, 5]
