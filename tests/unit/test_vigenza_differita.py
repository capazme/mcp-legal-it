"""A version Normattiva dates by an entry into force that a later act deferred (#172).

Art. 27 of d.lgs. 13 luglio 2017, n. 116 rewrites, among others, artt. 7, 15-bis and 543
c.p.c. (the giudice di pace reform). Its art. 32, comma 3, deferred its entry into force again
and again: 31/10/2021, 31/10/2025, 31/10/2026 and, by d.l. 12 giugno 2026, n. 100, 31/10/2027.
Normattiva dates the version that carries those amendments by an earlier date of that chain and
serves it as the text in force; only the article's update notes say otherwise:

- art. 7 (case A): version 10, «in vigore dal 31-10-2025», carries only the deferred act and
  the acts that deferred it; the text in force is version 9 (01/01/2023-30/10/2025);
- art. 543 (case B): the deferred «giudice competente» entered version 7 (31-10-2021); versions
  8 and 9 (l. 206/2021, d.lgs. 164/2024) were laid on top of it, so no version is in force;
- art. 15-bis: inserted by the deferred act, so nothing of it is in force yet.

Pages and the table of updates: what Normattiva served on 16 November 2026, trimmed
(``tests/fixtures/normattiva``). In every case the answer is never ESATTO and says why.
"""

import copy
import json
from pathlib import Path

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import aggiornamenti, akn_fetch, pagine_normattiva, scraper
from mcp_legal_it.lib.visualex import vigenza_differita as vd

NORMATTIVA = Path(__file__).resolve().parents[1] / "fixtures" / "normattiva"
OGGI = "2026-11-16"


def _pagina(nome: str) -> str:
    return (NORMATTIVA / nome).read_text(encoding="utf-8")


ART7 = _pagina("cpc_art7_vig_2026-11-16_rinvio_2027_trimmed.html")
ART7_V9 = _pagina("cpc_art7_vig_2025-10-30_versione_9_trimmed.html")
ART543 = _pagina("cpc_art543_vig_2026-11-16_rinvio_2027_trimmed.html")
ART15BIS = _pagina("cpc_art15bis_vig_2026-11-16_rinvio_2027_trimmed.html")
TABELLE = json.loads((NORMATTIVA / "cpc_aggiornamenti_rinvio_2027.json").read_text(encoding="utf-8"))
CPC = "regio.decreto:1940-10-28;1443:1~art"

pytestmark = pytest.mark.finestra_reale  # the pages carry their own «Testo in vigore dal» block


def _tabella(articolo: str) -> dict:
    """The recorded table of updates, in the shape leggi_aggiornamenti returns (int keys, tuples)."""
    t = copy.deepcopy(TABELLE[articolo])
    return {**t, "versioni": {int(k): tuple(v) if v else None for k, v in t["versioni"].items()},
            "righe": {int(k): v for k, v in t["righe"].items()}}


@pytest.fixture(autouse=True)
def _oggi(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", OGGI)


def _serve(monkeypatch, pagine: dict, tabella: "dict | None" = None):
    """Normattiva pages by the URN after «urn:nir:stato:» (exact, else without «!vig=»), and the
    table of updates *tabella* (None: reading it is an error of the test)."""
    richieste: list[str] = []
    tabelle_lette: list[str] = []

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
            urn = url.split("urn:nir:stato:", 1)[-1]
            richieste.append(urn)
            pagina = pagine.get(urn, pagine.get(urn.split("!vig=")[0]))
            if pagina is None:
                raise AssertionError(f"unexpected request: {url}")
            return _Risposta(url, pagina)

    async def nessun_export(norma, data_vigenza=None):
        return None

    async def tabella_registrata(url, articolo, **kw):
        tabelle_lette.append(articolo)
        if tabella is None:
            raise AssertionError("the table of updates must not be read here")
        return tabella

    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(scraper.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", nessun_export)
    monkeypatch.setattr(aggiornamenti, "leggi_aggiornamenti", tabella_registrata)
    pagine_normattiva.svuota_memoria()
    return richieste, tabelle_lette


def _cpc(articolo: str):
    return api.leggi_riferimento(f"art. {articolo} c.p.c.").norma_data[0]


class TestLaNota:
    @pytest.mark.parametrize("articolo, pagina", [("7", ART7), ("543", ART543)], ids=["art7", "art543"])
    async def test_the_fixture_is_the_bug(self, monkeypatch, articolo, pagina):
        """What Normattiva serves: a window holding today, and a note deferring to 31/10/2027."""
        _serve(monkeypatch, {CPC + articolo: pagina}, _tabella(articolo))
        t = await api.testo_articolo(_cpc(articolo), canale="html")
        assert t.esito == "trovato"
        assert any("31 ottobre 2027" in n.testo for n in t.note_aggiornamento)

    def test_the_latest_note_of_a_provision_wins(self):
        note = [
            {"numero": "179", "testo": "Il D.Lgs. 13 luglio 2017, n. 116, come modificato dal D.L. 8 agosto 2025, "
                                       "n. 117, convertito con modificazioni dalla L. 3 ottobre 2025, n. 148, ha "
                                       "disposto (con l'art. 32, comma 3) che \"Le disposizioni dell'articolo 27 "
                                       "entrano in vigore il 31 ottobre 2026\"."},
            {"numero": "183", "testo": "Il D.Lgs. 13 luglio 2017, n. 116, come modificato dal D.L. 12 giugno 2026, "
                                       "n. 100, ha disposto (con l'art. 32, comma 3) che \"Le disposizioni "
                                       "dell'articolo 27 entrano in vigore il 31 ottobre 2027\"."},
        ]
        r = vd.rinvio(note, OGGI)
        assert r["data"] == "2027-10-31" and r["nota"] == "183" and r["articolo"] == "27"
        assert r["superate"] == ["2026-10-31"]
        assert r["catena"] == {("decreto legislativo", "2017-07-13", "116"), ("decreto legge", "2025-08-08", "117"),
                               ("legge", "2025-10-03", "148"), ("decreto legge", "2026-06-12", "100")}
        # The day after, nothing is deferred any more.
        assert vd.rinvio(note, "2027-10-31") is None
        # Note (179) alone puts the date at 31/10/2026, already past: nothing is deferred.
        assert vd.rinvio(note[:1], OGGI) is None

    def test_only_dated_clauses_are_read(self):
        assert vd.clausola({"numero": "1", "testo": "Il D.L. 8 agosto 2025, n. 117 ha disposto (con l'art. 6, "
                                                    "comma 1) che le modifiche si applicano ai procedimenti "
                                                    "introdotti dopo l'entrata in vigore."}) is None
        assert vd.clausola({"numero": "2", "testo": "Il D.Lgs. 10 ottobre 2022, n. 149 ha disposto (con l'art. 35, "
                                                    "comma 1) che \"Le disposizioni del presente decreto hanno "
                                                    "effetto a decorrere dal 30 giugno 2023\"."})["data"] == "2023-06-30"


class TestCasoA:
    async def test_the_previous_version_is_served_as_the_text_in_force(self, monkeypatch):
        richieste, tabelle = _serve(monkeypatch, {CPC + "7": ART7, CPC + "7!vig=2025-10-30": ART7_V9}, _tabella("7"))
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert t.esito == "trovato" and t.precisione == "INDICATIVO" and not t.not_in_force
        testo = " ".join(t.article_text.split())
        assert "non superiore a diecimila euro" in testo and "3-ter)" not in testo  # version 9, not 10
        assert t.url.endswith("~art7!vig=2025-10-30")
        assert t.upcoming == {"change": "amended", "valid_from": "2027-10-31", "version_number": None}
        assert "versione precedente, in vigore dal 2023-01-01" in t.avvisi[0] and "2027-10-31" in t.avvisi[0]
        assert tabelle == ["7"] and richieste[-1] == CPC + "7!vig=2025-10-30"

    async def test_a_latest_version_with_another_act_is_case_b(self, monkeypatch):
        """Bartolo's guard: one act outside the chain in the latest version, and the previous
        version is never presented as in force."""
        tabella = _tabella("7")
        tabella["righe"][10].append({"progressivo": 9, "data_gu": "2024-11-11", "atti": [
            {"atto": {"tipo_atto": "decreto legislativo", "data": "2024-10-31", "numero_atto": "164"}}]})
        richieste, _ = _serve(monkeypatch, {CPC + "7": ART7}, tabella)
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert t.precisione == "INDICATIVO" and "3-ter)" in t.article_text  # today's page, version 10
        assert "nessuna versione di Normattiva corrisponde" in t.avvisi[0]
        assert not any("2025-10-30" in r for r in richieste)

    async def test_a_previous_page_that_is_not_the_article_is_case_b(self, monkeypatch):
        _serve(monkeypatch, {CPC + "7": ART7, CPC + "7!vig=2025-10-30": ART543}, _tabella("7"))
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert "3-ter)" in t.article_text and "nessuna versione di Normattiva corrisponde" in t.avvisi[0]

    async def test_cite_law_says_it_before_the_text(self, monkeypatch):
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {CPC + "7": ART7, CPC + "7!vig=2025-10-30": ART7_V9}, _tabella("7"))
        out = await lc._cite_law_impl("art. 7 c.p.c.")
        prima = out.split("Art. 7.")[0]
        assert "**Attenzione**: la nota (183)" in prima and "versione precedente" in prima

    async def test_cite_law_json_carries_it(self, monkeypatch):
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {CPC + "7": ART7, CPC + "7!vig=2025-10-30": ART7_V9}, _tabella("7"))
        body = json.loads(await lc._cite_law_impl("art. 7 c.p.c.", formato="json"))
        assert body["rinvio"] == {"data": "2027-10-31", "nota": "183", "atto": "D.Lgs. 13 luglio 2017, n. 116",
                                  "articolo": "27", "caso": "A"}
        assert body["avvisi"][0].startswith("la nota (183) di Normattiva rinvia al 2027-10-31")


class TestCasoB:
    async def test_no_version_is_in_force_and_it_is_said(self, monkeypatch):
        richieste, _ = _serve(monkeypatch, {CPC + "543": ART543}, _tabella("543"))
        t = await api.testo_articolo(_cpc("543"), canale="html")
        assert t.esito == "trovato" and t.precisione == "INDICATIVO"
        assert "giudice competente" in t.article_text  # what Normattiva serves, with the notice
        assert "le dà come vigenti dal 2021-10-31" in t.avvisi[0]
        assert "nessuna versione di Normattiva corrisponde" in t.avvisi[0]
        assert t.upcoming == {"change": "amended", "valid_from": "2027-10-31", "version_number": None}
        assert not any("!vig=" in r for r in richieste)


class TestNonInVigore:
    async def test_an_article_the_deferred_act_inserted_is_not_in_force(self, monkeypatch):
        _serve(monkeypatch, {CPC + "15bis": ART15BIS}, _tabella("15-bis"))
        t = await api.testo_articolo(_cpc("15-bis"), canale="html")
        assert t.not_in_force and t.precisione == "INDICATIVO"
        assert t.upcoming == {"change": "inserted", "valid_from": "2027-10-31", "version_number": None}
        assert any("testo non ancora in vigore: entra in vigore il 2027-10-31" in a for a in t.avvisi)


class TestSenzaRinvio:
    async def test_the_table_not_readable_still_gives_the_notice(self, monkeypatch):
        _serve(monkeypatch, {CPC + "7": ART7}, {"esito": "verifica_non_disponibile"})
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert t.precisione == "INDICATIVO" and "3-ter)" in t.article_text
        assert "non è stato possibile verificare se il testo riportato le contiene già" in t.avvisi[0]

    async def test_a_date_already_reached_is_no_deferral(self, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", "2027-11-01")
        _, tabelle = _serve(monkeypatch, {CPC + "7": ART7}, None)
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert tabelle == [] and not any("2027-10-31" in a for a in t.avvisi)

    async def test_a_text_at_a_date_is_left_alone(self, monkeypatch):
        _, tabelle = _serve(monkeypatch, {CPC + "7": ART7_V9}, None)
        rif = api.riferimento_da_parametri("codice di procedura civile", "7", data_versione="2024-01-01")
        await api.testo_articolo(rif.norma_data[0], canale="html")
        assert tabelle == []

    def test_a_table_without_the_deferred_act_says_nothing(self):
        r = vd.rinvio([{"numero": "183", "testo": "Il D.Lgs. 13 luglio 2017, n. 116, come modificato dal D.L. 12 "
                                                  "giugno 2026, n. 100, ha disposto (con l'art. 32, comma 3) che "
                                                  "\"Le disposizioni dell'articolo 27 entrano in vigore il 31 "
                                                  "ottobre 2027\"."}], OGGI)
        tabella = _tabella("543")
        righe = {k: [riga for riga in v if all(x["atto"]["numero_atto"] != "116" for x in riga["atti"])]
                 for k, v in tabella["righe"].items()}
        assert vd.caso(r, tabella["versioni"], righe) == (None, {})


class TestTabellaParziale:
    """Review of #173: a walk that stopped (``mancanti``) is a table not readable, never a case."""

    @pytest.mark.parametrize("manca", [10, 9], ids=["without-v10", "without-v9"])
    async def test_a_truncated_table_is_not_readable(self, monkeypatch, manca):
        tabella = _tabella("7")
        tabella["righe"].pop(manca, None)
        tabella["mancanti"] = [manca]
        richieste, _ = _serve(monkeypatch, {CPC + "7": ART7}, tabella)
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert t.precisione == "INDICATIVO" and "3-ter)" in t.article_text  # today's page, never a guess
        assert "non è stato possibile verificare se il testo riportato le contiene già" in t.avvisi[0]
        assert not any("!vig=" in r for r in richieste)  # no case A, no false case B

    async def test_a_previous_page_of_another_act_is_case_b(self, monkeypatch):
        _serve(monkeypatch, {CPC + "7": ART7, CPC + "7!vig=2025-10-30": ART7_V9}, _tabella("7"))
        originale = scraper._normattiva_page

        async def altro_atto(url, articolo=None):
            if "!vig=2025-10-30" in url:
                raise scraper.AttoNonVerificato("la pagina restituita è un altro atto", altro_atto=True)
            return await originale(url, articolo)

        monkeypatch.setattr(scraper, "_normattiva_page", altro_atto)
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert t.esito == "trovato" and "3-ter)" in t.article_text
        assert "nessuna versione di Normattiva corrisponde" in t.avvisi[0]

    async def test_verifica_citazioni_says_a_deferral_it_could_not_verify(self, monkeypatch):
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {CPC + "7": ART7}, {"esito": "verifica_non_disponibile"})
        verdetto, nota = await lc._verifica_norma("art. 7 c.p.c.")
        assert verdetto == "verificata"
        assert "rinvia al 2027-10-31" in nota and "non è stato possibile verificare se il testo le contiene già" in nota


class TestStoria:
    """storia_norma and api.modifiche_articolo: the version carrying the deferred act is said."""

    async def test_case_a_names_the_version_and_the_one_in_force(self, monkeypatch):
        _serve(monkeypatch, {CPC + "7": ART7}, _tabella("7"))
        m = await api.modifiche_articolo("art. 7 c.p.c.")
        assert m.esito == "trovato" and m.precisione == "INDICATIVO"
        assert ("Normattiva dà la versione 10 come vigente dal 2025-10-31, ma non è in vigore; il testo in vigore "
                "è la versione 9, dal 2023-01-01") in m.avvisi[0]
        catena = {"116", "117", "148", "100"}
        assert all(x.precisione == "INDICATIVO" for x in m.modifiche if x.atto.numero_atto in catena)
        assert any(x.precisione == "ESATTO" for x in m.modifiche if x.atto.numero_atto not in catena)

    async def test_case_b_and_the_inserted_article(self, monkeypatch):
        _serve(monkeypatch, {CPC + "543": ART543}, _tabella("543"))
        m = await api.modifiche_articolo("art. 543 c.p.c.")
        assert "le dà come vigenti dal 2021-10-31" in m.avvisi[0] and "nessuna versione è il testo in vigore" in m.avvisi[0]
        _serve(monkeypatch, {CPC + "15bis": ART15BIS}, _tabella("15-bis"))
        m = await api.modifiche_articolo("art. 15-bis c.p.c.")
        assert m.precisione == "INDICATIVO" and "non è ancora in vigore" in m.avvisi[0]

    async def test_a_truncated_walk_is_said_as_not_verifiable(self, monkeypatch):
        tabella = _tabella("7")
        tabella["righe"].pop(10)
        tabella["mancanti"], tabella["errore"] = [10], "errore di rete"
        _serve(monkeypatch, {CPC + "7": ART7}, tabella)
        m = await api.modifiche_articolo("art. 7 c.p.c.")
        assert "non è stato possibile verificare quali versioni le contengono" in m.avvisi[0]
        assert m.precisione == "INDICATIVO"

    async def test_storia_norma_prints_it(self, monkeypatch):
        from mcp_legal_it.tools import vigenza

        _serve(monkeypatch, {CPC + "7": ART7}, _tabella("7"))
        out = await vigenza._storia_norma_impl("art. 7 c.p.c.")
        assert "(INDICATIVO)" in out.splitlines()[0]
        assert "⚠ la nota (183) di Normattiva rinvia al 31/10/2027" in out

    async def test_no_deferral_no_notice(self, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", "2027-11-01")
        _serve(monkeypatch, {CPC + "7": ART7}, _tabella("7"))
        m = await api.modifiche_articolo("art. 7 c.p.c.")
        assert not any("rinvia al" in a for a in m.avvisi)
