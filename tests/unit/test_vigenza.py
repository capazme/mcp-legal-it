"""The text's validity, the text at a date, and how sure the answer is (LI-031, B-42). No network.

The pages are VisuaLex's captures (tests/fixtures/visualex/normattiva, README there); the
validity reader itself is tested by test_normattiva_validity.py (VisuaLex's tests).
"""

from pathlib import Path

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import akn_fetch, pagine_normattiva, scraper
from mcp_legal_it.lib.visualex.akn_parser import ParsedAct

from .validity_pages import page, synthetic

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _serve(monkeypatch, pagine: dict[str, str], act=None):
    """Normattiva pages by URL suffix; the AKN export is *act* (None: unavailable)."""
    richieste: list[str] = []

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
            for suffisso, testo in pagine.items():
                if url.endswith(suffisso):
                    return _Risposta(url, testo)
            raise AssertionError(f"unexpected request: {url}")

    kept: dict = {}

    async def fake_akn_kept(norma, data_vigenza=None):
        if act is not None:
            kept["act"] = act  # what the real fetch leaves in its cache
        return act

    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(scraper.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", fake_akn_kept)
    monkeypatch.setattr(akn_fetch, "cached_act", lambda norma, data_vigenza=None: kept.get("act"))
    pagine_normattiva.svuota_memoria()
    return richieste


def _l241(article: str, **kw):
    return api.riferimento_da_parametri("legge", article, data="1990-08-07", numero_atto="241", **kw).norma_data[0]


class TestTheTextAtADate:
    def test_a_date_is_the_text_in_force_that_day_with_or_without_versione(self):
        # VisuaLex's generate_urn reads the date only with versione="vigente": a date sent
        # without it got today's text (art. 1284 c.c. «at 2010» with the commi of 2014).
        for versione in ("vigente", None):
            nd = api.riferimento_da_parametri("codice civile", "1284", versione=versione,
                                              data_versione="2010-01-01").norma_data[0]
            assert nd.url.endswith(";262:2~art1284!vig=2010-01-01")
            assert (nd.versione, nd.data_versione) == ("vigente", "2010-01-01")

    def test_the_italian_long_form_is_read(self):
        nd = api.riferimento_da_parametri("codice civile", "1284", data_versione="1 gennaio 2010").norma_data[0]
        assert nd.data_versione == "2010-01-01"

    @pytest.mark.parametrize("kw,esito", [
        ({"data_versione": "2999-01-01"}, "riferimento_non_valido"),   # Normattiva would serve today's
        ({"data_versione": "ieri"}, "riferimento_non_valido"),
        ({"versione": "originale", "data_versione": "2010-01-01"}, "riferimento_non_valido"),
        ({"versione": "storica"}, "riferimento_non_valido"),
    ])
    def test_what_cannot_be_a_version_is_refused(self, kw, esito):
        assert api.riferimento_da_parametri("codice civile", "1284", **kw).esito == esito

    def test_eu_acts_have_versions_treaties_and_annexes_do_not(self):
        # Since issue #50 an EU regulation or directive has a text at a date (its consolidation)
        # and an original (the OJ text): test_eurlex_vigente.py.
        assert api.riferimento_da_parametri("regolamento ue", "5", data="2016", numero_atto="679",
                                            data_versione="2020-01-01").esito == "trovato"
        assert api.riferimento_da_parametri("tfue", "101", data_versione="2020-01-01").esito == "non_supportata"
        assert api.riferimento_da_parametri("decreto legislativo", "allegato I.7 art. 30", data="2023-03-31",
                                            numero_atto="36", data_versione="2024-01-01").esito == "non_supportata"

    def test_the_original_text(self):
        nd = api.riferimento_da_parametri("codice civile", "1284", versione="originale").norma_data[0]
        assert nd.url.endswith("~art1284@originale") and nd.versione == "originale"

    async def test_the_page_at_the_date_is_read_and_its_window_holds_the_date(self, monkeypatch):
        richieste = _serve(monkeypatch, {"~art1284!vig=2007-12-29": page("art1284_cc_at_2007-12-29_trimmed.html")})
        nd = api.riferimento_da_parametri("codice civile", "1284", data_versione="2007-12-29").norma_data[0]
        t = await api.testo_articolo(nd, canale="html")
        assert t.esito == "trovato" and t.fonte == "normattiva"
        assert len(richieste) == 1  # the validity comes from the same page
        assert t.validity is not None and t.validity.state == "historical"
        assert t.validity.request_in_window is True
        assert t.precisione == "ESATTO" and t.avvisi == ()


class TestPrecision:
    async def test_a_page_whose_validity_is_read_is_exact(self, monkeypatch):
        _serve(monkeypatch, {"241~art7": synthetic(dal="25-12-2003", version=3, updated="11/08/2026")})
        t = await api.testo_articolo(_l241("7"), canale="html")
        assert t.validity.state == "current" and t.validity.valid_from == "2003-12-25"
        assert t.validity.version_number == 3 and t.validity.act_updated == "2026-08-11"
        assert t.precisione == "ESATTO"

    @pytest.mark.finestra_reale
    async def test_a_page_that_does_not_say_is_indicative(self, monkeypatch):
        # Without a date such a page is never served (test_testo_di_oggi.py); at a date it
        # is the page asked for, and says nothing of its window.
        senza = synthetic(dal="25-12-2003").replace('<div class="vigore my-5">', '<div class="altro">')
        _serve(monkeypatch, {"~art7!vig=2010-01-01": senza})
        t = await api.testo_articolo(_l241("7", data_versione="2010-01-01"), canale="html")
        assert t.validity is None and t.precisione == "INDICATIVO"
        assert "non indica la vigenza" in t.avvisi[0]

    async def test_a_window_that_misses_the_date_is_said(self, monkeypatch):
        # The page served for the date is the text in force from 2003: not the one of 2002.
        _serve(monkeypatch, {"~art7!vig=2002-01-01": synthetic(dal="25-12-2003")})
        t = await api.testo_articolo(_l241("7", data_versione="2002-01-01"), canale="html")
        assert t.validity.request_in_window is False and t.precisione == "INDICATIVO"
        assert "non comprende il 2002-01-01" in t.avvisi[0]

    async def test_the_export_s_text_is_indicative_and_says_why(self, monkeypatch):
        act = ParsedAct(title="L. 241/1990", articles={"7": "### Art. 7.\n\n1. Testo."}, order=["7"],
                        consolidato="2026-06-04")
        _serve(monkeypatch, {}, act=act)
        t = await api.testo_articolo(_l241("7"), canale="akn")
        assert t.fonte == "normattiva-akn" and t.precisione == "INDICATIVO"
        assert t.validity is None
        assert "export Akoma Ntoso" in t.avvisi[0] and "consolidato al 2026-06-04" in t.avvisi[0]


class TestTheTwoChannels:
    """B-42: d.P.R. 131/1986, whose page says «ARTICOLO ABROGATO» while the export serves the text."""

    _ABROGATA = synthetic(dal="01-01-2026", label="Art. 7",
                          content='<div class="ins-akn art_abrogato-akn">((ARTICOLO ABROGATO DAL D.LGS. '
                                  '1 AGOSTO 2025, N. 123, COME MODIFICATO DAL D.L. 31 DICEMBRE 2025, N. 200))</div>',
                          updated="15/10/2026")

    async def test_the_page_repeals_the_export_does_not(self, monkeypatch):
        act = ParsedAct(title="atto", articles={"7": "### Art. 7.\n\n1. L'imposta si applica."}, order=["7"],
                        consolidato="2026-06-04")
        _serve(monkeypatch, {"241~art7": self._ABROGATA}, act=act)
        await api.testo_articolo(_l241("7"), canale="akn")  # the export in the cache
        t = await api.testo_articolo(_l241("7"), canale="html")
        assert t.validity.state == "abrogated" and t.precisione == "ESATTO"
        assert any("non concordano sull'abrogazione" in a and "la pagina dà l'articolo come abrogato" in a
                   for a in t.avvisi)

    async def test_the_export_answer_is_checked_against_the_page_kept(self, monkeypatch):
        act = ParsedAct(title="atto", articles={"7": "### Art. 7.\n\n1. L'imposta si applica."}, order=["7"],
                        consolidato="2026-06-04")
        _serve(monkeypatch, {"241~art7": self._ABROGATA}, act=act)
        await api.testo_articolo(_l241("7"), canale="html")  # the page kept for a day
        t = await api.testo_articolo(_l241("7"), canale="akn")
        assert t.fonte == "normattiva-akn" and t.precisione == "INDICATIVO"
        assert any("consolidato al 2026-06-04, la pagina dell'atto è aggiornata al 2026-10-15" in a for a in t.avvisi)
        assert any("non concordano sull'abrogazione" in a for a in t.avvisi)

    async def test_the_successor_named_by_the_notice_is_derived_and_indicative(self, monkeypatch):
        _serve(monkeypatch, {"241~art7": self._ABROGATA})
        t = await api.testo_articolo(_l241("7"), canale="html")
        assert t.successione == {
            "abrogato_da": "D.LGS. 1 AGOSTO 2025, N. 123, COME MODIFICATO DAL D.L. 31 DICEMBRE 2025, N. 200",
            "precisione": "INDICATIVO", "fonte": "avviso di abrogazione nel testo"}

    async def test_a_whole_act_repealed(self, monkeypatch):
        _serve(monkeypatch, {"241~art1": page("dlgs163_2006_art1_provvedimento_abrogato_trimmed.html")
               .replace("Art. 1 ", "Art. 1 ")})
        t = await api.testo_articolo(_l241("1"), canale="html")
        assert t.successione and t.successione["abrogato_da"].startswith("D.LGS. 18 APRILE 2016, N. 50")


class TestWhatIsNotServedAtADate:
    async def test_an_annex_given_as_normadati_at_a_date(self):
        from dataclasses import replace

        nd = api.riferimento_da_parametri("decreto legislativo", "allegato I.7 art. 30", data="2023-03-31",
                                          numero_atto="36").norma_data[0]
        t = await api.testo_articolo(replace(nd, data_versione="2024-01-01"), canale="html")
        assert t.esito == "non_supportata" and t.article_text == ""

    async def test_the_whole_act_at_a_date(self):
        nd = _l241("", data_versione="2010-01-01")
        assert (await api.indice_atto(nd)).esito == "non_supportata"

    async def test_a_bad_version_given_as_normadati(self):
        from dataclasses import replace

        t = await api.testo_articolo(replace(_l241("7"), versione="storica"), canale="html")
        assert t.esito == "riferimento_non_valido"


def _c_p_c(article: str, data_versione: str):
    return api.riferimento_da_parametri("codice di procedura civile", article, data_versione=data_versione).norma_data[0]


class TestReviewOf72:
    @pytest.mark.finestra_reale
    async def test_an_article_that_did_not_exist_on_the_day_is_not_found(self, monkeypatch):
        # «CODICE DI PROCEDURA CIVILE-art. 183 bis NON ANCORA ESISTENTE O VIGENTE», «al: 12-09-2014».
        _serve(monkeypatch, {"~art183bis!vig=2010-01-01": page("art183bis_cpc_at_2010-01-01_not_yet_trimmed.html")})
        t = await api.testo_articolo(_c_p_c("183-bis", "2010-01-01"), canale="html")
        assert t.esito == "articolo_non_trovato" and t.article_text == ""
        assert t.errore == "l'articolo non esisteva il 2010-01-01: entra in vigore dopo il 2014-09-12"
        assert t.validity.state == "not_yet"

    @pytest.mark.finestra_reale
    async def test_the_last_day_before_the_article_existed_and_the_first_day_it_did(self, monkeypatch):
        prima = page("art183bis_cpc_at_2010-01-01_not_yet_trimmed.html")
        dopo = synthetic(dal="13-09-2014", label="Art. 183 bis",
                         content='<span class="art-just-text-akn">Il testo del 2014.</span>')
        _serve(monkeypatch, {"~art183bis!vig=2014-09-12": prima, "~art183bis!vig=2014-09-13": dopo})
        t = await api.testo_articolo(_c_p_c("183-bis", "2014-09-12"), canale="html")
        assert t.esito == "articolo_non_trovato"
        t = await api.testo_articolo(_c_p_c("183-bis", "2014-09-13"), canale="html")
        assert t.esito == "trovato" and "Il testo del 2014" in t.article_text
        assert t.validity.request_in_window is True and t.precisione == "ESATTO"

    def test_the_core_says_it_too(self, monkeypatch):
        from mcp_legal_it.core import norme

        assert norme.non_ancora_vigente({"valid_to": "2014-09-12"}, None) == (
            "l'articolo non esisteva alla data richiesta: entra in vigore dopo il 2014-09-12")

    @pytest.mark.parametrize("canale", ["akn", "html"])
    @pytest.mark.parametrize("kw", [{"versione": "originale"}, {"data_versione": "2010-01-01"}])
    async def test_a_version_of_an_act_whose_full_date_is_unknown_is_refused(self, monkeypatch, canale, kw):
        # Cited with the year only and its date not read: the export would be asked at today's date.
        export = []

        async def nessuna_data(norma):
            return {}

        async def akn(norma, data_vigenza=None):
            export.append(data_vigenza)
            return ParsedAct(title="L. 241/1990", articles={"7": "### Art. 7.\n\n1. Testo di oggi."}, order=["7"])

        richieste = _serve(monkeypatch, {})
        monkeypatch.setattr(scraper, "_act_metadata", nessuna_data)
        monkeypatch.setattr(akn_fetch, "fetch_act_akn", akn)
        nd = api.riferimento_da_parametri("legge", "7", data="1990", numero_atto="241", **kw).norma_data[0]
        t = await api.testo_articolo(nd, canale=canale)
        assert t.esito == "verifica_non_disponibile" and t.article_text == ""
        assert "data completa dell'atto" in t.errore
        assert export == [] and richieste == []


async def test_a_date_read_from_the_eli_alone_is_not_kept(monkeypatch):
    # A kind outside the titles' nine: its ELI date serves this call, and is never written to disk.
    from mcp_legal_it.lib.visualex import act_dates
    from mcp_legal_it.lib.visualex.models import Norma

    async def meta(norma):
        return {"date": "2020-03-04"}

    monkeypatch.setattr(scraper, "_act_metadata", meta)
    norma = Norma("decreto del presidente del consiglio dei ministri", "2020", "5")
    piena = await scraper.with_full_date(norma)
    assert piena.data == "2020-03-04"
    assert act_dates.leggi(act_dates.chiave(scraper._tipo_urn(norma), "2020", "5")) is None


async def test_a_date_read_from_the_title_is_kept(monkeypatch):
    from mcp_legal_it.lib.visualex import act_dates
    from mcp_legal_it.lib.visualex.models import Norma

    async def meta(norma):
        return {"date": "1990-08-07", "data_titolo": "1990-08-07"}

    monkeypatch.setattr(scraper, "_act_metadata", meta)
    norma = Norma("legge", "1990", "241")
    assert (await scraper.with_full_date(norma)).data == "1990-08-07"
    assert act_dates.leggi(act_dates.chiave("legge", "1990", "241")) == "1990-08-07"


@pytest.mark.parametrize("canale", ["akn", "html"])
async def test_the_original_text_never_comes_from_the_export(monkeypatch, canale):
    # A code has no date in its NormaVisitata: the export would be asked at today's date.
    export = []

    async def akn(norma, data_vigenza=None):
        export.append(data_vigenza)
        return ParsedAct(title="c.c.", articles={"2043": "### Art. 2043.\n\nTesto di oggi."}, order=["2043"])

    originale = synthetic(dal="21-04-1942", label="Art. 2043",
                          content='<span class="art-just-text-akn">Il testo del 1942.</span>')
    richieste = _serve(monkeypatch, {"~art2043@originale": originale})
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", akn)
    nd = api.riferimento_da_parametri("codice civile", "2043", versione="originale").norma_data[0]
    t = await api.testo_articolo(nd, canale=canale)
    assert t.esito == "trovato" and "Il testo del 1942" in t.article_text and t.fonte == "normattiva"
    assert export == [] and len(richieste) == 1


async def test_the_original_text_without_its_page_is_not_today_s(monkeypatch):
    async def akn(norma, data_vigenza=None):
        raise AssertionError("the export was asked for the original text")

    _serve(monkeypatch, {})  # the @originale page cannot be read
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", akn)
    nd = api.riferimento_da_parametri("codice civile", "2043", versione="originale").norma_data[0]
    t = await api.testo_articolo(nd, canale="html")
    assert t.article_text == "" and t.esito != "trovato"
