"""Behaviour of ``mcp_legal_it.api``: outcomes as data, shapes, injection. Network mocked."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.core import _config
from mcp_legal_it.lib import _cache, _sources
from mcp_legal_it.lib.visualex.scraper import ARTICLE_NOT_FOUND

CC_URL = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043"


@pytest.fixture(autouse=True)
def _clean_config(monkeypatch):
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    monkeypatch.delenv("LEGAL_BROCARDI", raising=False)
    api.configura()
    yield
    api.configura()


def _fetch(result=None, exc=None, note=None):
    async def fake(nv, **kw):
        if note:
            _sources.note(*note)
        if exc:
            raise exc
        return dict(result, url=result.get("url") or nv.url())
    return fake


# ---------------------------------------------------------------------------
# Norms
# ---------------------------------------------------------------------------


class TestTestoArticolo:
    async def test_canale_is_required_and_checked(self):
        with pytest.raises(TypeError):
            await api.testo_articolo("art. 2043 c.c.")  # type: ignore[call-arg]
        with pytest.raises(ValueError):
            await api.testo_articolo("art. 2043 c.c.", canale="pdf")  # type: ignore[arg-type]

    async def test_html_channel_reads_the_page_with_visualex_s_extractor(self):
        from pathlib import Path

        from mcp_legal_it.lib.visualex.normattiva_html import estrai_da_html

        pagina = (Path(__file__).resolve().parents[1] / "fixtures" / "normattiva" / "cc_n2ls_art2043.html").read_text(
            encoding="utf-8")
        chieste = []

        def handler(request):
            chieste.append(str(request.url))
            return httpx.Response(200, text=pagina)

        def factory(fonte, **kwargs):
            kwargs.pop("verify", None)
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        with api.configurazione(client_factory=factory):
            t = await api.testo_articolo("art. 2043 c.c.", canale="html")
            di_nuovo = await api.testo_articolo("art. 2043 c.c.", canale="html")
        assert t.esito == "trovato" and t.canale == "html" and t.fonte == "normattiva"
        assert t.article_text == estrai_da_html(pagina)  # VisuaLex's text, byte for byte
        assert t.url == CC_URL and t.urn == CC_URL.split("?", 1)[1]
        assert chieste == [CC_URL]  # the second read comes from the page cache
        assert di_nuovo.article_text == t.article_text

    async def test_found_keeps_visualex_keys_and_both_url_and_urn(self):
        fake = _fetch({"text": "Qualunque fatto doloso...", "source": "normattiva-akn", "data_atto": ""},
                      note=("normattiva", CC_URL))
        with patch("mcp_legal_it.core.norme.fetch_article", side_effect=fake):
            t = await api.testo_articolo("art. 2043 c.c.", canale="akn")
        assert t.esito == "trovato" and t.errore is None
        assert t.article_text == "Qualunque fatto doloso..."
        assert t.url == CC_URL and t.urn == CC_URL.split("?", 1)[1]
        assert t.validity is None and t.fonte == "normattiva-akn"
        d = api.come_dict(t)
        assert {"article_text", "norma_data", "url", "validity"} <= set(d)
        assert d["norma_data"]["numero_articolo"] == "2043"
        assert t.fonti and t.fonti.fonti[0].fonte == "normattiva"

    async def test_year_only_act_keeps_its_urn_and_says_the_date_is_a_placeholder(self):
        fake = _fetch({"text": "testo", "source": "normattiva", "data_atto": "2023"})
        with patch("mcp_legal_it.core.norme.fetch_article", side_effect=fake):
            t = await api.testo_articolo("art. 3 L. 12/2023", canale="akn")
            # The MCP JSON face is unchanged: it still withholds a placeholder URN.
            from mcp_legal_it.core.norme import _cite_law_struct
            mcp_json = await _cite_law_struct("art. 3 L. 12/2023")
        assert t.urn == "urn:nir:stato:legge:2023-01-01;12~art3"
        assert t.norma_data.data_risolta is False and t.norma_data.data == "2023"
        assert mcp_json["urn"] is None

    async def test_resolved_year_only_act_has_its_real_date(self):
        fake = _fetch({"text": "testo", "source": "normattiva", "data_atto": "2023-02-17",
                       "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2023-02-17;12~art3"})
        with patch("mcp_legal_it.core.norme.fetch_article", side_effect=fake):
            t = await api.testo_articolo("art. 3 L. 12/2023", canale="akn")
        assert t.norma_data.data == "2023-02-17" and t.norma_data.data_risolta is True
        assert t.urn == "urn:nir:stato:legge:2023-02-17;12~art3"

    @pytest.mark.parametrize("result,exc,esito", [
        ({"text": "", "source": "normattiva", "esito": ARTICLE_NOT_FOUND, "error": "non esiste"}, None,
         "articolo_non_trovato"),
        (None, httpx.ConnectError("down"), "verifica_non_disponibile"),
        ({"text": "", "source": "normattiva"}, None, "testo_assente"),
        ({"text": "", "source": "eurlex", "error": "Could not fetch EUR-Lex document"}, None, "errore_fonte"),
    ])
    async def test_outcomes_are_data(self, result, exc, esito):
        with patch("mcp_legal_it.core.norme.fetch_article", side_effect=_fetch(result, exc)):
            t = await api.testo_articolo("art. 2043 c.c.", canale="akn")
        assert t.esito == esito and t.errore

    async def test_unreadable_and_unknown_references(self):
        t = await api.testo_articolo("qualcosa", canale="akn")
        assert t.esito == "atto_non_riconosciuto"
        assert "fetch_law_article" not in t.errore and "riferimento_da_parametri" in t.errore
        assert (await api.testo_articolo("", canale="akn")).esito == "riferimento_non_valido"

    async def test_normadati_input(self):
        nd = api.riferimento_da_parametri("codice civile", "2043").norma_data[0]
        with patch("mcp_legal_it.core.norme.fetch_article",
                   side_effect=_fetch({"text": "x", "source": "normattiva-akn"})):
            t = await api.testo_articolo(nd, canale="akn")
        assert t.esito == "trovato" and t.url == CC_URL

    async def test_many_articles_keep_order_and_respect_the_cap(self):
        running, peak = 0, 0

        async def fake(nv, **kw):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1
            return {"text": nv.numero_articolo, "url": nv.url(), "source": "normattiva"}

        refs = [f"art. {n} c.c." for n in range(1, 9)]
        with patch("mcp_legal_it.core.norme.fetch_article", side_effect=fake):
            out = await api.testi_articoli(refs, canale="akn", concorrenza=3)
        assert [t.article_text for t in out] == [str(n) for n in range(1, 9)]
        assert peak <= 3

    async def test_sources_reach_an_enclosing_mcp_call(self):
        fake = _fetch({"text": "x", "source": "normattiva"}, note=("normattiva", CC_URL))
        with _sources.recording() as outer, patch("mcp_legal_it.core.norme.fetch_article", side_effect=fake):
            await api.testo_articolo("art. 2043 c.c.", canale="akn")
        assert ("normattiva", "https://www.normattiva.it/uri-res/N2Ls") in outer


class TestRiferimenti:
    def test_read_without_network(self):
        r = api.leggi_riferimento("allegato I.7 art. 30 D.Lgs. 36/2023")
        assert r.esito == "trovato"
        nd = r.norma_data[0]
        assert (nd.allegato, nd.numero_articolo, nd.tipo_atto) == ("I.7", "30", "decreto legislativo")

    def test_a_year_only_act_is_never_resolved_over_the_network(self):
        boom = AssertionError("leggi_riferimento must stay offline")
        with patch("mcp_legal_it.lib.visualex.scraper.with_full_date", side_effect=boom), \
             patch("mcp_legal_it.lib.visualex.scraper._act_metadata", side_effect=boom), \
             patch("httpx.AsyncClient", side_effect=boom):
            r = api.leggi_riferimento("art. 3 L. 12/2023")
            p = api.riferimento_da_parametri("legge", "3", "2023", "12")
        for nd in (r.norma_data[0], p.norma_data[0]):
            assert nd.data == "2023" and nd.data_risolta is False

    @pytest.mark.parametrize("testo, urn", [
        ("art. 1 TUIR", "decreto.del.presidente.della.repubblica:1986-12-22;917~art1"),
        ("art. 1 TUB", "decreto.legislativo:1993-09-01;385~art1"),
        ("art. 1 TUF", "decreto.legislativo:1998-02-24;58~art1"),
        ("art. 1 testo unico sicurezza", "decreto.legislativo:2008-04-09;81~art1"),
    ])
    def test_a_known_italian_act_carries_its_full_date(self, testo, urn):
        nd = api.leggi_riferimento(testo).norma_data[0]
        assert nd.data_risolta is True
        assert nd.urn == f"urn:nir:stato:{urn}"

    def test_eu_act_has_no_urn(self):
        nd = api.leggi_riferimento("art. 6 GDPR").norma_data[0]
        assert nd.urn is None and nd.data_risolta is True and nd.url.startswith("https://eur-lex")

    def test_unknown_act_types_and_incomplete_eu_acts_are_refused(self):
        assert api.riferimento_da_parametri("pippo", "1", "2020-01-01", "5").esito == "atto_non_riconosciuto"
        assert api.riferimento_da_parametri("regolamento ue", "6").esito == "riferimento_non_valido"
        assert api.riferimento_da_parametri("regolamento ue", "6", "2016", "679").esito == "trovato"
        assert api.riferimento_da_parametri("d.lgs.", "1", "2001-06-08", "231").esito == "trovato"
        assert api.riferimento_da_parametri("costituzione", "3").esito == "trovato"

    def test_versions(self):
        orig = api.riferimento_da_parametri("codice civile", "2043", versione="originale")
        assert orig.esito == "trovato" and orig.norma_data[0].url.endswith("~art2043@originale")
        assert api.riferimento_da_parametri("codice civile", "2043", versione="storica").esito == "riferimento_non_valido"
        assert api.riferimento_da_parametri("", "1").esito == "riferimento_non_valido"
        assert api.riferimento_da_parametri("legge", "1").esito == "riferimento_non_valido"  # no date: no URL

    def test_alias_catalog_shape(self):
        c = api.catalogo_alias()
        assert c.presets["ai act"] == {"act_type": "regolamento ue", "act_number": "1689", "date": "2024"}
        assert "codice civile" in c.known_acts and list(c.known_acts) == sorted(c.known_acts)


class TestIndiceAtto:
    async def test_rubriche_from_index_lines(self):
        result = {"index": ["Articoli", "1-  Soggetti", "2-bis- Rubrica bis", "Capo I"],
                  "codice_redazionale": "001G0293", "data_gu": "2001-06-19", "url": "u"}
        with patch("mcp_legal_it.api._norme.fetch_act_index", AsyncMock(return_value=result)):
            i = await api.indice_atto("D.Lgs. 231/2001")
        assert i.esito == "trovato"
        assert i.rubriche == {"1": "Soggetti", "2-bis": "Rubrica bis"} and i.count == 2
        assert i.voci[0] == "Articoli" and i.abrogati == () and i.parts == ()

    async def test_an_eu_act_has_an_index(self, monkeypatch):
        # Since the 3.0 migration: VisuaLex's EU tree on the act's page (test_eurlex_indice.py).
        from mcp_legal_it.lib.visualex import scraper

        async def pagina(norma):
            return ('<html><body><p class="oj-ti-art">Articolo 1</p><p class="oj-sti-art">Oggetto</p>'
                    '</body></html>'), "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679"

        monkeypatch.setattr(scraper, "_fetch_eurlex_html", pagina)
        i = await api.indice_atto("GDPR")
        assert i.esito == "trovato" and i.rubriche == {"1": "Oggetto"}

    async def test_source_down(self):
        with patch("mcp_legal_it.api._norme.fetch_act_index", AsyncMock(side_effect=httpx.ConnectTimeout("t"))):
            assert (await api.indice_atto("D.Lgs. 231/2001")).esito == "verifica_non_disponibile"


class TestBrocardi:
    async def test_switched_off_makes_no_request(self):
        with patch("mcp_legal_it.lib.brocardi.client.fetch_brocardi", side_effect=AssertionError("no request")):
            with api.configurazione(brocardi=False):
                a = await api.annotazioni_brocardi("art. 2043 c.c.")
        assert a.esito == "brocardi_disattivato"

    def test_an_inherited_value_does_not_switch_a_context_off_back_on(self):
        from mcp_legal_it.lib import _brocardi_switch

        api.configura(brocardi=True)
        with _brocardi_switch.disabled():
            with api.configurazione(cache=False):
                assert _brocardi_switch.enabled() is False
            with pytest.raises(ValueError):
                with api.configurazione(brocardi=True):
                    pass
            assert _brocardi_switch.enabled() is False

    async def test_found_with_structured_abstracts(self):
        from mcp_legal_it.lib.brocardi.client import BrocardiResult, Massima

        r = BrocardiResult(url="https://www.brocardi.it/x", ratio="r", spiegazione="s", brocardi=["b"],
                           massime=[Massima(autorita="Cass. civ.", numero="100", anno="2024", testo="m")])
        with patch("mcp_legal_it.lib.brocardi.client.fetch_brocardi", AsyncMock(return_value=r)):
            a = await api.annotazioni_brocardi("art. 2043 c.c.")
        assert a.esito == "trovato" and a.brocardi == ("b",)
        assert a.massime == (api.MassimaBrocardi(autorita="Cass. civ.", numero="100", anno="2024", testo="m"),)
        assert (await api.annotazioni_brocardi("art. 2043 c.c.".replace("art. 2043 ", ""))).esito == \
            "riferimento_non_valido"

    async def test_env_off_cannot_be_switched_back_on(self, monkeypatch):
        monkeypatch.setenv("LEGAL_BROCARDI", "off")
        with pytest.raises(ValueError):
            with api.configurazione(brocardi=True):
                pass
        with pytest.raises(ValueError):
            api.configura(brocardi=True)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfigurazione:
    def test_cache_settings(self, tmp_path, monkeypatch):
        with api.configurazione(cache_dir=tmp_path):
            assert _cache.cache_root() == tmp_path
        assert _cache.cache_root() != tmp_path
        with api.configurazione(cache=False):
            assert _cache.cache_enabled() is False
        monkeypatch.setenv("LEGAL_CACHE", "off")
        with api.configurazione(cache=True):
            assert _cache.cache_enabled() is False  # the environment's off wins

    def test_process_default_and_reset(self, tmp_path):
        api.configura(cache_dir=tmp_path)
        assert _cache.cache_root() == tmp_path
        api.configura()
        assert _config.attuale() == api.Configurazione()

    async def test_client_factory_sees_every_client_with_its_settings(self):
        seen = []
        doc = {"id": "x", "numdec": "00001", "anno": "2024", "kind": "snciv", "szdec": "U", "ocr": "testo"}

        def handler(request):
            if request.method == "POST":
                return httpx.Response(200, json={"response": {"docs": [doc], "numFound": 1}})
            return httpx.Response(200, text="ok")

        def factory(fonte, **kwargs):
            seen.append((fonte, kwargs.get("verify", True)))
            kwargs.pop("verify", None)
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        with api.configurazione(client_factory=factory):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=1, anno=2024))
        assert d.esito == "trovata" and d.testo_grezzo.testo == "testo"
        # Italgiure's TLS is verified with the bundled intermediate (lib/italgiure).
        from mcp_legal_it.lib.italgiure.client import tls_context
        assert seen and all(s == ("italgiure", tls_context()) for s in seen)

    async def test_concurrent_contexts_do_not_leak(self, tmp_path):
        async def dentro(path):
            with api.configurazione(cache_dir=path):
                await asyncio.sleep(0.01)
                return _cache.cache_root()

        a, b = await asyncio.gather(dentro(tmp_path / "a"), dentro(tmp_path / "b"))
        assert (a, b) == (tmp_path / "a", tmp_path / "b")


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

def _doc(id_, kind="snciv", szdec="3", numdec="12345", anno="2023", **extra):
    return {"id": id_, "kind": kind, "szdec": szdec, "numdec": numdec, "anno": anno, "datdep": "20230509",
            "tipoprov": "Ordinanza", "materia": "LEASING", "ocr": "motivi", "ocrdis": "P.Q.M. rigetta", **extra}


class TestLeggiDecisione:
    async def test_invalid_request(self):
        d = await api.leggi_decisione(api.RiferimentoDecisione(corte="luna", numero=0, anno=3000))
        assert d.esito == "richiesta_non_valida" and set(d.errori) == {"corte", "numero", "anno"}
        with pytest.raises(TypeError):
            await api.leggi_decisione({"corte": "cassazione"})  # type: ignore[arg-type]
        d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=1, anno=2024, sezione="Z"))
        assert d.esito == "richiesta_non_valida" and "sezione" in d.errori

    async def test_found(self):
        with patch("mcp_legal_it.core.cassazione.lookup_decisione", AsyncMock(return_value=([_doc("a")], True))):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=12345, anno=2023))
        assert d.esito == "trovata" and d.testo is None
        assert (d.identita.corte, d.identita.numero, d.identita.anno, d.identita.archivio) == \
            ("cassazione", 12345, 2023, "civile")
        assert d.attributi.data_deposito == "2023-05-09" and d.attributi.sezione == "3"
        assert d.testo_grezzo == api.TestoGrezzo(testo="motivi", dispositivo="P.Q.M. rigetta")
        attributi = api.come_dict(d)["attributi"]
        assert "relatore" not in attributi  # only the filled ones, as in VisuaLex

    async def test_same_number_in_two_archives_is_ambiguous(self):
        docs = [_doc("a"), _doc("b", kind="snpen")]
        with patch("mcp_legal_it.core.cassazione.lookup_decisione", AsyncMock(return_value=(docs, True))):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=12345, anno=2023))
        assert d.esito == "ambigua"
        assert [c.identita.archivio for c in d.candidati] == ["civile", "penale"]

    async def test_full_text_step_is_never_ambiguous(self):
        with patch("mcp_legal_it.core.cassazione.lookup_decisione", AsyncMock(return_value=([_doc("a")], False))):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=12345, anno=2023))
        assert d.esito == "trovata"

    @pytest.mark.parametrize("anno,motivo", [(2015, "fuori_archivio"), (2021, "anno_parziale"),
                                             (2023, "inesistente"), (2026, "anno_parziale")])
    async def test_not_found_reasons(self, anno, motivo, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", "2026-10-21")
        with patch("mcp_legal_it.core.cassazione.lookup_decisione", AsyncMock(return_value=([], False))), \
             patch("mcp_legal_it.core.cassazione._italgiure_archive_start",
                   AsyncMock(return_value=(2021, "2021-01-27"))):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=1, anno=anno))
        assert d.esito == "non_trovata" and d.motivo == motivo and d.archivio_dal == "2021-01-27"

    async def test_source_down(self):
        with patch("mcp_legal_it.core.cassazione.lookup_decisione", AsyncMock(side_effect=httpx.ConnectError("x"))):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=1, anno=2024))
        assert d.esito == "fonte_non_raggiungibile" and d.errore

    async def test_corte_costituzionale(self):
        from mcp_legal_it.lib.corte_cost.client import PronunciaCost

        p = PronunciaCost(numero_pronuncia="242", anno_pronuncia="2019", tipologia_pronuncia="S",
                          data_deposito="22/11/2019", ecli="ECLI:IT:COST:2019:242", testo="t", dispositivo="d")
        with patch("mcp_legal_it.lib.corte_cost.client.fetch_pronuncia", AsyncMock(return_value=p)):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="corte_costituzionale", numero=242, anno=2019))
        assert d.esito == "trovata" and d.attributi.tipo == "sentenza" and d.attributi.data_deposito == "2019-11-22"
        with patch("mcp_legal_it.lib.corte_cost.client.fetch_pronuncia", AsyncMock(return_value=None)):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="corte_costituzionale", numero=9, anno=2019))
        assert d.esito == "non_trovata"

    async def test_other_courts_are_planned(self):
        d = await api.leggi_decisione(api.RiferimentoDecisione(corte="tar", numero=1, anno=2024))
        assert d.esito == "non_supportata"


class TestRicercaCassazione:
    async def test_needs_a_theme_or_a_norm(self):
        r = await api.cerca_decisioni_cassazione()
        assert r.esito == "richiesta_non_valida" and "tema" in r.errori

    async def test_hits_fragments_years_and_paging(self):
        data = {
            "response": {"numFound": 42, "docs": [_doc("a")]},
            "highlighting": {"a": {"ocrdis": ["la <em>perdita</em> di <em>chance</em>"]}},
            "facet_counts": {"facet_fields": {"anno": ["2023", 30, "2024", 12]}},
        }
        solr = AsyncMock(return_value=data)
        with patch("mcp_legal_it.core.cassazione.solr_query", solr), \
             patch("mcp_legal_it.core.cassazione._italgiure_archive_start",
                   AsyncMock(return_value=(2021, "2021-01-27"))):
            r = await api.cerca_decisioni_cassazione("perdita di chance", pagina=3, per_pagina=10)
        assert solr.await_args.args[0]["start"] == 20 and solr.await_args.args[0]["rows"] == 10
        assert r.esito == "risultati" and r.totale == 42 and r.pagina == 3 and r.archivio_dal == "2021-01-27"
        f = r.decisioni[0].frammento
        assert f.testo == "la perdita di chance"
        assert [f.testo[a:b] for a, b in f.evidenziati] == ["perdita", "chance"]
        assert r.anni == ({"anno": 2024, "n": 12}, {"anno": 2023, "n": 30})

    async def test_no_hit_is_results_with_zero(self):
        with patch("mcp_legal_it.core.cassazione.solr_query",
                   AsyncMock(return_value={"response": {"numFound": 0, "docs": []}})), \
             patch("mcp_legal_it.core.cassazione._italgiure_archive_start", AsyncMock(return_value=(2021, ""))):
            r = await api.giurisprudenza_su_articolo("art. 2051 c.c.", sezione="3")
        assert r.esito == "risultati" and r.totale == 0 and r.decisioni == ()


class TestUnificata:
    async def test_one_source_down_does_not_fail_the_call(self):
        ok = api.RicercaDecisioni(esito="risultati", fonte="italgiure", totale=1)
        with patch("mcp_legal_it.api._decisioni.cerca_decisioni_cassazione", AsyncMock(return_value=ok)), \
             patch("mcp_legal_it.api._decisioni.cerca_decisioni_ue", AsyncMock(side_effect=RuntimeError("boom"))):
            out = await api.cerca_giurisprudenza_unificata("tema", fonti=("cassazione", "ue"))
        assert out["cassazione"] is ok and out["ue"].esito == "errore_fonte"
        with pytest.raises(ValueError):
            await api.cerca_giurisprudenza_unificata("tema", fonti=("luna",))


def test_come_dict_is_json_ready():
    d = api.EsitoDecisione(esito="trovata", avvisi=(api.Avviso("sezione_diversa", {"citata": "3", "effettiva": "2"}),),
                           attributi=api.Attributi(sezione="2"))
    out = api.come_dict(d)
    json.dumps(out)
    assert out["avvisi"] == [{"tipo": "sezione_diversa", "citata": "3", "effettiva": "2"}]
    assert out["attributi"] == {"sezione": "2"}


@pytest.mark.parametrize("uri", [
    "http://169.254.169.254/latest/meta-data/",
    "http://localhost:8000/resource/cellar/x",
    "https://publications.europa.eu.evil.example/resource/cellar/x",
    "http://user@publications.europa.eu/resource/cellar/x",
    "http://publications.europa.eu:8080/resource/cellar/x",
    "http://publications.europa.eu/resource/cellar/x?redirect=http://evil",
    "http://publications.europa.eu/other/x",
    "https://publications.europa.eu:abc/resource/cellar/x",
    "https://publications.europa.eu:99999/resource/cellar/x",
    "http://[::1/resource/cellar/x",
    "file:///etc/passwd",
    "",
])
async def test_cgue_reader_refuses_any_uri_but_cellar_before_any_request(uri):
    with patch("mcp_legal_it.lib.cgue.client.fetch_sentenza_text", side_effect=AssertionError("no request")):
        d = await api.leggi_sentenza_cgue(uri)
    assert d.esito == "richiesta_non_valida"


async def test_cgue_reader_accepts_cellar_and_celex_uris():
    text = "Sentenza " * 40
    for uri in ("http://publications.europa.eu/resource/cellar/4e4876f7-237a-11f1-8c3a-01aa75ed71a1.0006",
                "http://publications.europa.eu/resource/celex/62019CJ0311"):
        with patch("mcp_legal_it.lib.cgue.client.fetch_sentenza_text", AsyncMock(return_value=text)), \
             patch("mcp_legal_it.lib.cgue.client.fetch_case_metadata",
                   AsyncMock(return_value={"case_ref": "C-311/19", "ecli": "ECLI:EU:C:2020:981", "date": "2020-12-03"})):
            d = await api.leggi_sentenza_cgue(uri)
        assert d.esito == "trovata" and d.identita.chiave_fonte == uri
        if "/celex/" in uri:  # a CELLAR id without a CELEX in the text has no metadata to read
            assert (d.identita.numero, d.identita.anno) == (311, 2019)
            assert d.attributi.ecli == "ECLI:EU:C:2020:981"



class TestTestoAtto:
    async def test_found_short_and_eu(self):
        full = {"text": "x" * 80, "title": "LEGGE 20 maggio 1970, n. 300", "url": "u"}
        with patch("mcp_legal_it.api._norme.fetch_normattiva_full_text", AsyncMock(return_value=full)):
            t = await api.testo_atto("legge 20 maggio 1970, n. 300")
        assert t.esito == "trovato" and t.titolo.startswith("LEGGE")
        with patch("mcp_legal_it.api._norme.fetch_normattiva_full_text", AsyncMock(return_value={"text": "x"})):
            assert (await api.testo_atto("legge 20 maggio 1970, n. 300")).esito == "testo_assente"
        assert (await api.testo_atto("GDPR")).esito == "non_supportata"


class TestLettoriPerChiave:
    async def test_cerdef(self):
        from mcp_legal_it.lib.cerdef.client import CerdefNonTrovato, ProvvedimentoDetail

        d = ProvvedimentoDetail(guid="g-1", estremi="Sentenza del 12/03/2024 n. 1234", massima="M",
                                testo_integrale="T")
        with patch("mcp_legal_it.lib.cerdef.client.fetch_provvedimento", AsyncMock(return_value=d)):
            r = await api.leggi_provvedimento_tributario("g-1")
        assert r.esito == "trovata" and r.identita.chiave_fonte == "g-1"
        assert (r.identita.numero, r.identita.anno) == (1234, 2024)
        assert r.testo_grezzo == api.TestoGrezzo(testo="T", massima="M")
        with patch("mcp_legal_it.lib.cerdef.client.fetch_provvedimento",
                   AsyncMock(side_effect=CerdefNonTrovato("guid sconosciuto"))):
            assert (await api.leggi_provvedimento_tributario("g-2")).esito == "non_trovata"
        assert (await api.leggi_provvedimento_tributario("")).esito == "richiesta_non_valida"

    async def test_giustizia_amministrativa(self):
        from mcp_legal_it.lib.giustizia_amm.client import ProvvedimentoDocument

        doc = ProvvedimentoDocument(title="Sentenza", text="testo", url="https://mdp/x", pdf_only=False,
                                    meta={"tipologia": "Sentenza", "numero": "202614035",
                                          "data_pubblicazione": "2026-07-01"})
        with patch("mcp_legal_it.lib.giustizia_amm.client.fetch_provvedimento_document",
                   AsyncMock(return_value=doc)):
            r = await api.leggi_provvedimento_amministrativo("tar_rm", "202500001", "f.xml")
        assert r.esito == "trovata" and r.identita.corte == "tar" and r.identita.sede == "tar_rm"
        assert (r.identita.numero, r.identita.anno) == (14035, 2026)
        assert r.identita.chiave_fonte == {"sede": "tar_rm", "nrg": "202500001", "nome_file": "f.xml"}
        pdf = ProvvedimentoDocument(title="", text="", url="https://mdp/x.pdf", pdf_only=True, meta={})
        with patch("mcp_legal_it.lib.giustizia_amm.client.fetch_provvedimento_document",
                   AsyncMock(return_value=pdf)):
            r = await api.leggi_provvedimento_amministrativo("cds", "1", "f.pdf")
        assert r.esito == "trovata" and r.testo_grezzo is None and r.avvisi[0].tipo == "testo_non_disponibile"
        assert r.identita.corte == "consiglio_di_stato"
        assert (await api.leggi_provvedimento_amministrativo("", "", "")).esito == "richiesta_non_valida"


    @pytest.mark.parametrize("fixture,attesa", [
        ("parere_1918_2026.html", (1918, 2026, "Parere", None)),
        ("ap17_2021.html", (17, 2021, "Sentenza", "2021-11-09")),
    ])
    async def test_giustizia_amministrativa_numero_n_anno(self, fixture, attesa):
        """The reader gives «N/AAAA» («1918/2026»): number 1918 of 2026, never year 1918."""
        from pathlib import Path

        from mcp_legal_it.lib.giustizia_amm.client import ProvvedimentoDocument, _parse_html_document

        page = (Path(__file__).resolve().parents[1] / "fixtures" / "giustizia_amm" / fixture).read_bytes()
        title, text, meta = _parse_html_document(page)
        doc = ProvvedimentoDocument(title=title, text=text, meta=meta, pdf_only=False, url="https://mdp/x")
        with patch("mcp_legal_it.lib.giustizia_amm.client.fetch_provvedimento_document",
                   AsyncMock(return_value=doc)):
            r = await api.leggi_provvedimento_amministrativo("cds", "201303041", fixture)
        assert (r.identita.numero, r.identita.anno, r.attributi.tipo, r.attributi.data_deposito) == attesa

    @pytest.mark.parametrize("numero,attesa", [
        ("1918/2026", (1918, 2026)), ("17/2021", (17, 2021)), ("202614035", (14035, 2026)),
        ("", (None, None)), ("abc", ("abc", None)),
    ])
    def test_numero_ga_forms(self, numero, attesa):
        from mcp_legal_it.api._decisioni import _numero_anno_ga

        assert _numero_anno_ga(numero) == attesa


class TestAltreRicerche:
    async def test_costituzionale(self):
        from mcp_legal_it.lib.corte_cost.client import MassimaCost, PronunciaCost

        p = PronunciaCost(numero_pronuncia="242", anno_pronuncia="2019", tipologia_pronuncia="S")
        with patch("mcp_legal_it.lib.corte_cost.client.search_pronunce", AsyncMock(return_value=[p])):
            r = await api.cerca_decisioni_costituzionali("fine vita", anno_dal=2019, anno_al=2019)
        assert r.esito == "risultati" and r.decisioni[0].identita.numero == 242
        hit = ("242", "2019", MassimaCost(titolo="Aiuto al suicidio", testo="massima"))
        with patch("mcp_legal_it.lib.corte_cost.client.pronunce_su_norma", AsyncMock(return_value=[hit])):
            r = await api.pronunce_costituzionali_su_norma("art. 580 c.p.")
        assert r.decisioni[0].frammento.testo == "massima" and r.decisioni[0].attributi.titolo == "Aiuto al suicidio"
        assert (await api.cerca_decisioni_costituzionali("x", max_risultati=0)).esito == "richiesta_non_valida"

    async def test_tributaria(self):
        from mcp_legal_it.lib.cerdef.client import CerdefError, EsitoRicerca, ProvvedimentoResult

        e = EsitoRicerca(risultati=[ProvvedimentoResult(guid="g", estremi="Sent. n. 5/2024", titoli="IVA",
                                                        ente="CGT II grado", data="12/03/2024")],
                         totale=7, esaminati=1, troncato=True)
        with patch("mcp_legal_it.lib.cerdef.client.search_giurisprudenza", AsyncMock(return_value=e)):
            r = await api.cerca_decisioni_tributarie("IVA")
        assert r.esito == "risultati" and r.totale == 7 and r.troncato is True
        assert r.decisioni[0].identita.chiave_fonte == "g" and r.decisioni[0].attributi.data_deposito == "2024-03-12"
        with patch("mcp_legal_it.lib.cerdef.client.search_giurisprudenza", AsyncMock(side_effect=ValueError("ente?"))):
            assert (await api.cerca_decisioni_tributarie("IVA", ente="x")).esito == "richiesta_non_valida"
        with patch("mcp_legal_it.lib.cerdef.client.search_giurisprudenza", AsyncMock(side_effect=CerdefError("x"))):
            assert (await api.cerca_decisioni_tributarie("IVA")).esito == "errore_fonte"

    async def test_amministrativa_year_filter_is_flagged(self):
        from mcp_legal_it.lib.giustizia_amm.client import ProvvedimentoResult

        docs = [ProvvedimentoResult(sede="cds", sede_label="Consiglio di Stato", nrg="1", tipo="SENTENZA", anno=a,
                                    nome_file="f", data_deposito="", oggetto="o", numero=f"{a}00001")
                for a in ("2025", "2026")]
        with patch("mcp_legal_it.lib.giustizia_amm.client.search_provvedimenti_page",
                   AsyncMock(return_value=(docs, 99))):
            r = await api.cerca_decisioni_amministrative("appalto", anno="2026")
        assert [d.identita.anno for d in r.decisioni] == [2026]
        assert r.totale is None and r.troncato is True

    async def test_ue(self):
        from mcp_legal_it.lib.cgue.client import CaseResult

        c = CaseResult(celex="62019CJ0311", ecli="ECLI:EU:C:2020:981", case_number="C-311/19", date="2020-12-03",
                       title="t", court="CJ", doc_type="JUDG", cellar_uri="http://publications.europa.eu/resource/cellar/x")
        with patch("mcp_legal_it.lib.cgue.client.search_giurisprudenza", AsyncMock(return_value=[c])):
            r = await api.cerca_decisioni_ue("dati")
            r2 = await api.giurisprudenza_ue_su_articolo("art. 82 GDPR")
        for res in (r, r2):
            i = res.decisioni[0].identita
            assert (i.corte, i.numero, i.anno, i.chiave_fonte) == ("corte_giustizia_ue", 311, 2019, c.cellar_uri)
        assert (await api.giurisprudenza_ue_su_articolo("")).esito == "richiesta_non_valida"



class TestRisposteVisuaLex:
    """Alfred's answers on PR #59: the shapes VisuaLex's shell and saved records depend on."""

    @pytest.mark.parametrize("citazione,allegato,urn", [
        ("art. 2043 c.c.", "2", "urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043"),
        ("art. 575 c.p.", "1", "urn:nir:stato:regio.decreto:1930-10-19;1398:1~art575"),
        ("art. 700 c.p.c.", "1", "urn:nir:stato:regio.decreto:1940-10-28;1443:1~art700"),
        ("art. 13 D.Lgs. 196/2003", None, "urn:nir:stato:decreto.legislativo:2003-06-30;196~art13"),
    ])
    def test_codes_carry_their_default_annex_in_allegato_and_urn(self, citazione, allegato, urn):
        nd = api.leggi_riferimento(citazione).norma_data[0]
        assert (nd.allegato, nd.urn) == (allegato, urn)

    async def test_the_default_annex_round_trips_as_the_article_not_as_an_annex(self):
        nd = api.riferimento_da_parametri("codice civile", "2043", allegato="2").norma_data[0]
        assert nd.url == CC_URL and nd.allegato == "2" and nd.numero_articolo == "2043"
        seen = []

        async def fake(nv, **kw):
            seen.append(nv.numero_articolo)
            return {"text": "x", "url": nv.url(), "source": "normattiva-akn"}

        with patch("mcp_legal_it.core.norme.fetch_article", side_effect=fake):
            t = await api.testo_articolo(nd, canale="akn")
        assert seen == ["2043"] and t.url == CC_URL

    async def test_sezione_is_the_italgiure_code_in_upper_case(self):
        with patch("mcp_legal_it.core.cassazione.lookup_decisione",
                   AsyncMock(return_value=([_doc("a", szdec="u")], True))):
            d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=1, anno=2024))
        assert d.attributi.sezione == "U"

    @pytest.mark.parametrize("chiamata,patch_target,codice", [
        (lambda: api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=1, anno=2024)),
         "mcp_legal_it.core.cassazione.lookup_decisione", "cassazione"),
        (lambda: api.leggi_decisione(api.RiferimentoDecisione(corte="corte_costituzionale", numero=1, anno=2024)),
         "mcp_legal_it.lib.corte_cost.client.fetch_pronuncia", "corte_costituzionale"),
        (lambda: api.leggi_sentenza_cgue("http://publications.europa.eu/resource/celex/62019CJ0311"),
         "mcp_legal_it.lib.cgue.client.fetch_sentenza_text", "curia"),
        (lambda: api.leggi_provvedimento_amministrativo("cds", "1", "f.xml"),
         "mcp_legal_it.lib.giustizia_amm.client.fetch_provvedimento_document", "giustizia_amministrativa"),
    ])
    async def test_source_down_names_the_source_as_visualex_does(self, chiamata, patch_target, codice):
        with patch(patch_target, AsyncMock(side_effect=httpx.ConnectError("down"))):
            d = await chiamata()
        assert d.esito == "fonte_non_raggiungibile"
        assert d.fonte.codice == codice

    @pytest.mark.parametrize("chiamata,patch_target,codice", [
        (lambda: api.cerca_decisioni_cassazione("x"), "mcp_legal_it.core.cassazione.solr_query", "cassazione"),
        (lambda: api.cerca_decisioni_costituzionali("x"), "mcp_legal_it.lib.corte_cost.client.search_pronunce",
         "corte_costituzionale"),
        (lambda: api.cerca_decisioni_ue("x"), "mcp_legal_it.lib.cgue.client.search_giurisprudenza", "curia"),
        (lambda: api.cerca_decisioni_amministrative("x"),
         "mcp_legal_it.lib.giustizia_amm.client.search_provvedimenti_page", "giustizia_amministrativa"),
    ])
    async def test_searches_use_the_same_source_codes(self, chiamata, patch_target, codice):
        with patch(patch_target, AsyncMock(side_effect=httpx.ConnectError("down"))):
            r = await chiamata()
        assert (r.esito, r.fonte) == ("fonte_non_raggiungibile", codice)


def test_every_source_maps_to_allowed_hosts_and_every_call_site_to_a_source():
    import re
    from pathlib import Path

    from mcp_legal_it.core._http import HOST_PER_FONTE
    from mcp_legal_it.lib._egress import ALLOWED_HOSTS

    for fonte, hosts in HOST_PER_FONTE.items():
        if hosts is not None:
            assert hosts <= set(ALLOWED_HOSTS), (fonte, hosts - set(ALLOWED_HOSTS))
    lib = Path(api.__file__).resolve().parents[1] / "lib"
    used = {m for py in lib.rglob("*.py") for m in re.findall(r'async_client\(\s*"([a-z_]+)"', py.read_text())}
    assert used and used <= set(HOST_PER_FONTE), used - set(HOST_PER_FONTE)



class TestGuardieDellaFactory:
    """A client factory cannot remove the library's request guards (SSRF)."""

    @staticmethod
    def _ignora_tutto(chiamate):
        def handler(request):
            chiamate.append(str(request.url))
            return httpx.Response(200, text="ok")

        # Ignores every kwarg it receives, event_hooks included.
        return lambda fonte, **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                                         follow_redirects=True)

    async def test_dpa_probe_guard_survives_a_factory_that_drops_the_kwargs(self):
        from mcp_legal_it.lib.dpa_probe.client import DestinazioneNonPubblica, _guardia_destinazioni

        chiamate: list = []
        with api.configurazione(client_factory=self._ignora_tutto(chiamate)):
            from mcp_legal_it.core._http import async_client

            async with async_client("dpa_probe", event_hooks={"request": [_guardia_destinazioni({})]}) as client:
                with pytest.raises(DestinazioneNonPubblica):
                    await client.get("http://127.0.0.1/admin")
                with pytest.raises(DestinazioneNonPubblica):
                    await client.get("http://169.254.169.254/latest/meta-data/")
        assert chiamate == []  # nothing reached the transport

    async def test_a_process_wide_factory_does_not_disarm_the_mcp_tool(self):
        from mcp_legal_it.lib.dpa_probe.client import sonda_dominio

        chiamate: list = []
        api.configura(client_factory=self._ignora_tutto(chiamate))
        with patch("mcp_legal_it.lib.dpa_probe.client._verifica_destinazione",
                   AsyncMock(side_effect=[None, "indirizzo privato"] * 20)):
            esito = await sonda_dominio("example.com")
        assert esito.errore and chiamate == []

    async def test_follow_redirects_false_is_kept_and_factory_hooks_run_after(self):
        from mcp_legal_it.core._http import async_client

        ordine = []

        async def guardia(request):
            ordine.append("guardia")

        async def della_factory(request):
            ordine.append("factory")

        def factory(fonte, **kwargs):
            return httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)),
                                     follow_redirects=True, event_hooks={"request": [della_factory]})

        with api.configurazione(client_factory=factory):
            async with async_client("normattiva", follow_redirects=False,
                                    event_hooks={"request": [guardia]}) as client:
                assert client.follow_redirects is False
                await client.get("https://www.normattiva.it/")
        assert ordine == ["guardia", "factory"]
