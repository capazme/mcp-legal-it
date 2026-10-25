"""The text Normattiva has published and not in force yet: an article inserted from a later day,
and the later text asked for (``versione="futura"``; VisuaLex's G-358 and G-357, at 4aa59a9d).

No network: the pages are built in the portal's markup (``validity_pages``), as in
test_testo_di_oggi.py, whose fake client this module shares.
"""

import json

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import akn_fetch, scraper

from .test_testo_di_oggi import DPR131, OGGI, OGGI_PAGINA, _dpr131, _serve
from .validity_pages import synthetic

pytestmark = pytest.mark.finestra_reale

#: The undated page: a text in force from 2027.
DAL_2027 = synthetic(dal="01-01-2027", label="Art. 3",
                     content='<span class="art-just-text-akn">Il testo che verrà.</span>')
#: The page at today's date of an article that does not exist yet.
NON_ANCORA = synthetic(al="31-12-2026", label="Art. 3",
                       content='<span class="art-just-text-akn">ARTICOLO NON ANCORA ESISTENTE O VIGENTE</span>')


@pytest.fixture(autouse=True)
def _oggi(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", OGGI)


def _futura(**kw):
    return api.riferimento_da_parametri("decreto del presidente della repubblica", "3", data="1986-04-26",
                                        numero_atto="131", versione="futura", **kw)


def _no_export(monkeypatch):
    chiesto = []

    async def nessuno(norma, data_vigenza=None):
        chiesto.append(data_vigenza)
        return None

    monkeypatch.setattr(akn_fetch, "fetch_act_akn", nessuno)
    return chiesto


class TestAnArticleInsertedFromALaterDay:
    """Nothing of it is in force today: its later text is served, as VisuaLex does (G-358)."""

    async def test_the_later_text_is_served_and_said_not_in_force(self, monkeypatch):
        richieste = _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": NON_ANCORA})
        chiesto = _no_export(monkeypatch)
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert richieste == [DPR131, f"{DPR131}!vig={OGGI}"] and chiesto == []  # no export asked
        assert t.esito == "trovato" and "Il testo che verrà" in t.article_text and t.not_in_force
        assert t.url.endswith("~art3") and t.precisione == "INDICATIVO"
        assert t.upcoming == {"change": "inserted", "valid_from": "2027-01-01", "version_number": None}
        assert t.avvisi == ("testo non ancora in vigore: entra in vigore il 2027-01-01 (articolo inserito da "
                            "quella data); non è il testo vigente oggi",)
        # The request keeps its key: no date, as VisuaLex's norma_data.
        assert (t.norma_data.versione, t.norma_data.data_versione) == ("vigente", None)
        assert t.validity.valid_from == "2027-01-01" and t.successione is None

    async def test_the_akn_channel_says_the_same(self, monkeypatch):
        _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": NON_ANCORA})
        t = await api.testo_articolo(_dpr131(), canale="akn")
        assert t.esito == "trovato" and t.not_in_force and t.upcoming["change"] == "inserted"

    async def test_cite_law(self, monkeypatch):
        import mcp_legal_it.server  # noqa: F401
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": NON_ANCORA})
        out = await lc._cite_law_impl("art. 3 d.p.r. 26 aprile 1986, n. 131")
        assert "**Attenzione**: testo non ancora in vigore: entra in vigore il 2027-01-01" in out
        assert "Il testo che verrà" in out and "il testo riportato è quello in vigore oggi" not in out
        dati = json.loads(await lc._cite_law_impl("art. 3 d.p.r. 26 aprile 1986, n. 131", formato="json"))
        assert dati["upcoming"]["change"] == "inserted" and dati["not_in_force"] is True
        assert "Il testo che verrà" in dati["testo"]

    async def test_verifica_citazioni_does_not_call_it_verified(self, monkeypatch):
        # Review of #88: a text not in force yet is no verified citation of the law in force.
        import mcp_legal_it.server  # noqa: F401
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": NON_ANCORA})
        dati = json.loads(await lc._verifica_citazioni_impl("art. 3 d.p.r. 26 aprile 1986, n. 131", formato="json"))
        [c] = dati["citazioni"]
        assert c["verdetto"] == "non in vigore"
        assert c["nota"].startswith("L'articolo non è ancora in vigore: entra in vigore il 2027-01-01.")

    async def test_verifica_citazioni_still_verifies_today_s_text(self, monkeypatch):
        import mcp_legal_it.server  # noqa: F401
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        dati = json.loads(await lc._verifica_citazioni_impl("art. 3 d.p.r. 26 aprile 1986, n. 131", formato="json"))
        [c] = dati["citazioni"]
        # In force today, with a later version published: verified, and the note says it.
        assert c["verdetto"] == "verificata"
        assert c["nota"].endswith("Attenzione: modificato con effetto dal 2027-01-01.")


async def test_verifica_citazioni_says_a_coming_repeal(monkeypatch):
    # Art. 3 d.P.R. 131/1986 on 21/10/2026: in force today, repealed from 1/1/2027.
    import mcp_legal_it.server  # noqa: F401
    from mcp_legal_it.tools import legal_citations as lc

    from .test_testo_di_oggi import FUTURA

    _serve(monkeypatch, {DPR131: FUTURA, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
    dati = json.loads(await lc._verifica_citazioni_impl("art. 3 d.p.r. 26 aprile 1986, n. 131", formato="json"))
    [c] = dati["citazioni"]
    assert c["verdetto"] == "verificata"
    assert c["nota"].endswith("Attenzione: abrogato con effetto dal 2027-01-01.")


async def test_verifica_citazioni_adds_no_note_without_a_later_version(monkeypatch):
    # The undated page is today's text: nothing announced, so no «Attenzione» in the note.
    import mcp_legal_it.server  # noqa: F401
    from mcp_legal_it.tools import legal_citations as lc

    _serve(monkeypatch, {DPR131: OGGI_PAGINA})
    dati = json.loads(await lc._verifica_citazioni_impl("art. 3 d.p.r. 26 aprile 1986, n. 131", formato="json"))
    [c] = dati["citazioni"]
    assert c["verdetto"] == "verificata" and "Attenzione" not in c["nota"]


class TestTheLaterTextAskedFor:
    def test_the_reference_keeps_the_version_asked_for(self):
        nd = _futura().norma_data[0]
        assert (nd.versione, nd.data_versione) == ("futura", None) and "!vig=" not in nd.url
        assert _futura(data_versione="2027-06-30").norma_data[0].data_versione == "2027-06-30"

    async def test_a_change_from_a_later_day(self, monkeypatch):
        richieste = _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        t = await api.testo_articolo(_futura().norma_data[0], canale="html")
        assert richieste == [DPR131, f"{DPR131}!vig={OGGI}"]
        assert t.esito == "trovato" and "Il testo che verrà" in t.article_text and t.not_in_force
        assert t.url.endswith("~art3") and t.precisione == "INDICATIVO"
        assert t.upcoming == {"change": "amended", "valid_from": "2027-01-01", "version_number": None}
        assert t.validity.request_in_window is True and t.validity.valid_from == "2027-01-01"
        # Dated to the day it comes into force, as VisuaLex's norma_data: never the text in force.
        assert (t.norma_data.versione, t.norma_data.data_versione) == ("vigente", "2027-01-01")
        assert t.norma_data.urn.endswith("~art3")
        assert t.avvisi[0] == ("testo non ancora in vigore: entra in vigore il 2027-01-01 (articolo modificato "
                               "da quella data); non è il testo vigente oggi")
        assert not any("in vigore oggi" in a and "riportato" in a for a in t.avvisi)

    async def test_an_insertion(self, monkeypatch):
        _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": NON_ANCORA})
        t = await api.testo_articolo(_futura().norma_data[0], canale="html")
        assert t.not_in_force and t.upcoming["change"] == "inserted"

    async def test_today_s_page_unreadable_cannot_tell_a_change_from_an_insertion(self, monkeypatch):
        _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": httpx.ConnectError("down")})
        t = await api.testo_articolo(_futura().norma_data[0], canale="html")
        assert t.not_in_force and t.upcoming["change"] is None

    async def test_none_published(self, monkeypatch):
        richieste = _serve(monkeypatch, {DPR131: OGGI_PAGINA})
        t = await api.testo_articolo(_futura().norma_data[0], canale="html")
        assert richieste == [DPR131] and t.esito == "articolo_non_trovato" and not t.not_in_force
        assert t.errore.startswith("Nessuna versione non ancora in vigore per l'art. 3")

    async def test_none_by_the_day_named(self, monkeypatch):
        _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        t = await api.testo_articolo(_futura(data_versione="2026-12-31").norma_data[0], canale="html")
        assert t.esito == "articolo_non_trovato" and t.errore.endswith("entra in vigore il 2027-01-01")

    async def test_a_day_before_the_latest_of_several_later_versions_cannot_be_told(self, monkeypatch):
        # VisuaLex 02ebc80a: today's text is version 1, the undated page version 3, so version 2
        # comes in between, and Normattiva does not show it on its own.
        later = synthetic(dal="01-01-2027", label="Art. 3", version=3,
                          content='<span class="art-just-text-akn">Il testo che verrà.</span>')
        today = synthetic(dal="30-12-2025", label="Art. 3", version=1,
                          content='<span class="art-just-text-akn">Il testo di oggi.</span>')
        _serve(monkeypatch, {DPR131: later, f"{DPR131}!vig={OGGI}": today})
        t = await api.testo_articolo(_futura(data_versione="2026-12-31").norma_data[0], canale="html")
        assert t.esito == "verifica_non_disponibile"
        assert t.errore.startswith("Non so dire quale versione dell'art. 3") and "ce n'è un'altra" in t.errore
        t = await api.testo_articolo(_futura().norma_data[0], canale="html")
        assert t.upcoming == {"change": "amended", "valid_from": "2027-01-01", "version_number": 3,
                              "versions_between": 1}

    async def test_the_text_of_today_says_the_versions_in_between(self, monkeypatch):
        # Undated request: today's text (version 1) is served, the latest version (3) is announced.
        later = synthetic(dal="01-01-2027", label="Art. 3", version=3,
                          content='<span class="art-just-text-akn">Il testo che verrà.</span>')
        today = synthetic(dal="30-12-2025", label="Art. 3", version=1,
                          content='<span class="art-just-text-akn">Il testo di oggi.</span>')
        _serve(monkeypatch, {DPR131: later, f"{DPR131}!vig={OGGI}": today})
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert "Il testo di oggi" in t.article_text and not t.not_in_force
        assert t.upcoming["versions_between"] == 1

    async def test_a_page_that_does_not_say(self, monkeypatch):
        senza = DAL_2027.replace('<div class="vigore my-5">', '<div class="altro">')
        _serve(monkeypatch, {DPR131: senza})
        t = await api.testo_articolo(_futura().norma_data[0], canale="html")
        assert t.esito == "verifica_non_disponibile" and t.errore.startswith("Non riesco a leggere la vigenza")

    @pytest.mark.parametrize("kw, esito", [
        ({"data_versione": OGGI}, "riferimento_non_valido"),
        ({"data_versione": "2020-01-01"}, "riferimento_non_valido"),
        ({"data_versione": "domani"}, "riferimento_non_valido"),
    ])
    def test_a_day_up_to_today_is_refused(self, kw, esito):
        assert _futura(**kw).esito == esito

    def test_not_for_eu_acts_nor_annexes(self):
        assert api.riferimento_da_parametri("regolamento ue", "6", data="2016", numero_atto="679",
                                            versione="futura").esito == "non_supportata"
        r = api.riferimento_da_parametri("decreto legislativo", "30", data="2023-03-31", numero_atto="36",
                                         allegato="I.7", versione="futura")
        assert r.esito == "non_supportata" and "versione futura" in r.errore

    async def test_cite_law(self, monkeypatch):
        import mcp_legal_it.server  # noqa: F401
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {DPR131: DAL_2027, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        out = await lc._cite_law_impl("art. 3 d.p.r. 26 aprile 1986, n. 131", versione="futura")
        assert "**Attenzione**: testo non ancora in vigore: entra in vigore il 2027-01-01" in out
        assert "Il testo che verrà" in out and "il testo riportato è quello in vigore oggi" not in out
        dati = json.loads(await lc._cite_law_impl("art. 3 d.p.r. 26 aprile 1986, n. 131", formato="json",
                                                  versione="futura"))
        assert dati["not_in_force"] is True and dati["upcoming"]["change"] == "amended"
        assert dati["avvisi"][0].startswith("testo non ancora in vigore")

    async def test_cite_law_refuses_it_for_an_annex_before_any_request(self, monkeypatch):
        # Review of #88: it sent a request, then said «Non riesco a leggere la vigenza».
        import mcp_legal_it.server  # noqa: F401
        from mcp_legal_it.tools import legal_citations as lc

        richieste = _serve(monkeypatch, {})
        out = await lc._cite_law_impl("art. 30 allegato I.7 d.lgs. 36/2023", versione="futura")
        assert out == "**Errore**: la versione futura di un allegato non è ancora disponibile" and richieste == []
        dati = json.loads(await lc._cite_law_impl("art. 30 allegato I.7 d.lgs. 36/2023", formato="json",
                                                  versione="futura"))
        assert dati["errore"] == "la versione futura di un allegato non è ancora disponibile" and richieste == []

    async def test_cite_law_refuses_it_for_an_eu_act(self):
        import mcp_legal_it.server  # noqa: F401
        from mcp_legal_it.tools import legal_citations as lc

        out = await lc._cite_law_impl("art. 6 GDPR", versione="futura")
        assert out == "**Errore**: versione 'futura' disponibile per gli atti su Normattiva"
