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
# The other provisions art. 27 amends (scan of 16 November 2026, #177).
ART765 = _pagina("cpc_art765_vig_2026-11-16_note_ferme_al_2026_trimmed.html")
ART765_V3 = _pagina("cpc_art765_vig_2021-10-30_versione_3_trimmed.html")
ART73BIS = _pagina("dispattcc_art73bis_vig_2026-11-16_rinvio_2027_trimmed.html")
ART73BIS_V2 = _pagina("dispattcc_art73bis_vig_2021-10-30_versione_2_trimmed.html")
ART32_116 = _pagina("dlgs116_2017_art32_vig_2026-11-16_trimmed.html")
TABELLE_ART27 = json.loads((NORMATTIVA / "rinvio_art27_aggiornamenti.json").read_text(encoding="utf-8"))
DISP_ATT_CC = "regio.decreto:1942-03-30;318:1~art"
DLGS_116 = "decreto.legislativo:2017-07-13;116~art"

pytestmark = pytest.mark.finestra_reale  # the pages carry their own «Testo in vigore dal» block


def _tabella(articolo: str, tabelle: "dict | None" = None) -> dict:
    """The recorded table of updates, in the shape leggi_aggiornamenti returns (int keys, tuples)."""
    t = copy.deepcopy((tabelle or TABELLE)[articolo])
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
        if "esito" in tabella:
            return tabella
        # One table per article: {"765": ..., "32": ...}.
        if articolo not in tabella:
            raise AssertionError(f"the table of art. {articolo} must not be read here")
        return tabella[articolo]

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
        assert "vi ha applicato modifiche successive" in t.avvisi[0] and "le contiene già" not in t.avvisi[0]
        assert not any("2025-10-30" in r for r in richieste)

    async def test_a_previous_page_that_is_not_the_article_is_case_b(self, monkeypatch):
        _serve(monkeypatch, {CPC + "7": ART7, CPC + "7!vig=2025-10-30": ART543}, _tabella("7"))
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert "3-ter)" in t.article_text and "la versione precedente non è stata letta" in t.avvisi[0]
        assert "le contiene già" not in t.avvisi[0]

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
        # #177: never «the text already contains them»; d.lgs. 164/2024 may have rewritten them.
        assert "vi ha applicato modifiche successive" in t.avvisi[0] and "le contiene già" not in t.avvisi[0]
        assert "non è verificato che sia il testo in vigore" in t.avvisi[0]
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
        """The day after, the notes' date has passed: art. 32, comma 3 is read once to confirm
        it was not moved again (#177), and the text is served as it is."""
        monkeypatch.setenv("LEGAL_TODAY", "2027-11-01")
        richieste, tabelle = _serve(monkeypatch, {CPC + "7": ART7, DLGS_116 + "32": ART32_116}, None)
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert t.esito == "trovato" and t.precisione == "ESATTO" and "3-ter)" in t.article_text
        assert tabelle == [] and not any("2027-10-31" in a for a in t.avvisi)
        assert richieste[-1] == DLGS_116 + "32!vig=2027-11-01"

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
        assert "la versione precedente non è stata letta" in t.avvisi[0]

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
        assert "le dà come vigenti dal 2021-10-31" in m.avvisi[0]
        assert "non è verificato quale sia il testo in vigore" in m.avvisi[0]
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
        _serve(monkeypatch, {CPC + "7": ART7, DLGS_116 + "32": ART32_116}, _tabella("7"))
        m = await api.modifiche_articolo("art. 7 c.p.c.")
        assert m.esito == "trovato" and not any("rinvia al" in a for a in m.avvisi)


# --- The other provisions art. 27 amends (scan of 16 November 2026, #177) ----------------------


def _tabelle_art27(*articoli: str) -> dict:
    return {a: _tabella(a, TABELLE_ART27) for a in articoli}


def _note(articolo: str) -> list:
    return TABELLE_ART27[articolo]["note_pagina"]


class TestNoteFerme:
    """Art. 765 c.p.c.: Normattiva's notes stop at 31/10/2026 (notes 160 and 179); the 2027 note
    was never added. Art. 32, comma 3 of d.lgs. 116/2017, read live, says 31 ottobre 2027, and
    versions 4 (2021-10-31) and 5 (2025-10-31) both belong to the deferred chain: version 3 is
    the text in force."""

    def test_the_notes_alone_say_nothing_is_deferred(self):
        assert vd.rinvio(_note("765"), OGGI) is None
        s = vd.rinvio_scaduto(_note("765"), OGGI)
        assert s["data"] == "2026-10-31" and s["nota"] == "179" and s["superate"] == ["2025-10-31"]
        assert s["atto"] == ("decreto legislativo", "2017-07-13", "116") and s["disposizione"] == "32, comma 3"

    def test_a_date_moved_earlier_is_no_stale_deferral(self):
        """Art. 7 c.p.c.'s Cartabia notes (171, 173): 30/06/2023 brought forward to 28/02/2023."""
        cartabia = [n for n in TABELLE["7"]["note_pagina"] if n["numero"] in ("171", "173")]
        assert vd.rinvio_scaduto(cartabia, OGGI) is None

    def test_the_date_is_read_in_the_provision_comma(self):
        testo = ("Art. 32\nDisposizioni transitorie e abrogazioni\n\n1. COMMA ABROGATO.\n\n"
                 "3. Le disposizioni dell'articolo 27 entrano in vigore il ((31 ottobre 2027)).\n\n"
                 "4. Le disposizioni dell'articolo 28 entrano in vigore il 1° gennaio 2019.")
        assert vd.stato_disposizione(testo, "3", OGGI) == ("rinvio", "2027-10-31")
        assert vd.stato_disposizione(testo, "4", OGGI) == ("in_vigore", None)  # its only date has passed
        assert vd.stato_disposizione(testo, "1", OGGI) == ("in_vigore", None)  # repealed: nothing deferred
        assert vd.stato_disposizione(testo, "2", OGGI) == ("ignoto", None)  # not found
        assert vd.stato_disposizione(testo, None, OGGI) == ("rinvio", "2027-10-31")  # one future date
        # Review of #179 (M1): a comma read whose dates have all passed defers nothing, for ever.
        assert vd.stato_disposizione(testo, "3", "2027-11-01") == ("in_vigore", None)
        due = "3. Le disposizioni dell'articolo 27 entrano in vigore il 31 ottobre 2027 e quelle dell'articolo 28 " \
              "entrano in vigore il 1° gennaio 2028."
        assert vd.stato_disposizione(due, "3", OGGI) == ("ignoto", None)  # two future dates: never a guess
        assert vd.stato_disposizione(due, "3", "2028-02-01") == ("in_vigore", None)
        assert vd.stato_disposizione("3. Le disposizioni dell'articolo 27 si applicano.", "3", OGGI) == ("ignoto", None)

    async def test_version_3_is_served_with_the_provision_date(self, monkeypatch):
        richieste, tabelle = _serve(monkeypatch, {CPC + "765": ART765, CPC + "765!vig=2021-10-30": ART765_V3,
                                                  DLGS_116 + "32": ART32_116}, _tabelle_art27("765", "32"))
        t = await api.testo_articolo(_cpc("765"), canale="html")
        assert t.esito == "trovato" and t.precisione == "INDICATIVO" and not t.not_in_force
        testo = " ".join(t.article_text.split())
        assert "dal cancelliere del tribunale" in testo and "cancelliere del conciliatore" in testo
        assert "giudice di pace" not in testo
        assert t.url.endswith("~art765!vig=2021-10-30")
        assert t.validity is None or t.validity.state != "current"
        assert t.upcoming == {"change": "amended", "valid_from": "2027-10-31", "version_number": None}
        avviso = t.avvisi[0]
        assert "art. 32, comma 3" in avviso and "2027-10-31" in avviso
        assert "(179)" in avviso and "2026-10-31" in avviso
        assert "versione 3, in vigore dal 1998-07-04" in avviso
        assert DLGS_116 + "32!vig=2026-11-16" in richieste and set(tabelle) == {"32", "765"}

    async def test_cite_law_json_says_where_the_date_comes_from(self, monkeypatch):
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {CPC + "765": ART765, CPC + "765!vig=2021-10-30": ART765_V3,
                             DLGS_116 + "32": ART32_116}, _tabelle_art27("765", "32"))
        body = json.loads(await lc._cite_law_impl("art. 765 c.p.c.", formato="json"))
        assert body["rinvio"]["data"] == "2027-10-31" and body["rinvio"]["caso"] == "A"
        assert body["rinvio"]["data_nota"] == "2026-10-31" and body["rinvio"]["disposizione"] == "art. 32, comma 3"

    async def test_the_provision_not_readable_gives_a_notice_without_a_date(self, monkeypatch):
        richieste, _ = _serve(monkeypatch, {CPC + "765": ART765}, _tabelle_art27("765"))
        originale = scraper._normattiva_page

        async def art32_giu(url, articolo=None):
            if "~art32" in url:
                raise scraper.httpx.ConnectError("rete")
            return await originale(url, articolo)

        monkeypatch.setattr(scraper, "_normattiva_page", art32_giu)
        t = await api.testo_articolo(_cpc("765"), canale="html")
        assert t.precisione == "INDICATIVO" and "giudice di pace" in t.article_text  # today's page, never a guess
        assert "non è stato possibile leggere" in t.avvisi[0] and "art. 32, comma 3" in t.avvisi[0]
        assert not any("!vig=2021-10-30" in r for r in richieste)

    async def test_the_provision_table_not_readable_is_never_case_a(self, monkeypatch):
        """Without art. 32's own table, d.l. 100/2026 is outside the chain: version 4 is not
        chain-only, and the previous version is never presented as in force."""
        richieste, _ = _serve(monkeypatch, {CPC + "765": ART765, DLGS_116 + "32": ART32_116},
                              {"765": _tabella("765", TABELLE_ART27), "32": {"esito": "verifica_non_disponibile"}})
        t = await api.testo_articolo(_cpc("765"), canale="html")
        assert t.precisione == "INDICATIVO" and "giudice di pace" in t.article_text
        assert "2027-10-31" in t.avvisi[0] and not any("!vig=2021-10-30" in r for r in richieste)

    async def test_a_provision_date_already_reached_says_nothing(self, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", "2027-11-01")
        _, tabelle = _serve(monkeypatch, {CPC + "765": ART765, DLGS_116 + "32": ART32_116}, None)
        t = await api.testo_articolo(_cpc("765"), canale="html")
        assert tabelle == [] and not any("2027-10-31" in a for a in t.avvisi)

    async def test_the_history_says_versions_4_and_5_are_not_in_force(self, monkeypatch):
        _serve(monkeypatch, {CPC + "765": ART765, DLGS_116 + "32": ART32_116}, _tabelle_art27("765", "32"))
        m = await api.modifiche_articolo("art. 765 c.p.c.")
        assert m.esito == "trovato" and m.precisione == "INDICATIVO"
        assert "art. 32, comma 3" in m.avvisi[0] and "2027-10-31" in m.avvisi[0]
        assert "il testo in vigore è la versione 3, dal 1998-07-04" in m.avvisi[0]
        assert all(x.precisione == "INDICATIVO" for x in m.modifiche if x.atto.numero_atto == "100")


class TestAbrogazioneRinviata:
    """Art. 73-bis disp. att. c.c.: repealed by art. 27, comma 3, lett. f), a repeal deferred with
    the rest of art. 27. Notes (37), (55) and (58) word it «la proroga al … dell'entrata in vigore
    della presente abrogazione», (58) with «che». Version 2 is in force."""

    def test_the_proroga_wording_is_read(self):
        note = {n["numero"]: n for n in _note("73-bis")}
        senza_che, con_che = vd.clausola(note["37"]), vd.clausola(note["58"])
        assert senza_che["data"] == "2025-10-31" and senza_che["abrogazione"]
        assert con_che["data"] == "2027-10-31" and con_che["disposizione"] == "32, comma 3"
        r = vd.rinvio(_note("73-bis"), OGGI)
        assert r["data"] == "2027-10-31" and r["nota"] == "58" and r["abrogazione"]
        assert ("decreto legge", "2026-06-12", "100") in r["catena"]

    async def test_version_2_is_served_never_a_repeal(self, monkeypatch):
        richieste, _ = _serve(monkeypatch, {DISP_ATT_CC + "73bis": ART73BIS,
                                            DISP_ATT_CC + "73bis!vig=2021-10-30": ART73BIS_V2},
                              _tabelle_art27("73-bis"))
        rif = api.leggi_riferimento("art. 73-bis disp. att. c.c.").norma_data[0]
        t = await api.testo_articolo(rif, canale="html")
        assert t.esito == "trovato" and t.precisione == "INDICATIVO"
        testo = " ".join(t.article_text.split())
        assert "sono adottati dal tribunale in composizione monocratica" in testo and "ABROGATO" not in testo
        assert t.validity is not None and t.validity.state != "abrogated"
        assert t.upcoming == {"change": "abrogated", "valid_from": "2027-10-31", "version_number": None}
        assert t.successione == {"abrogato_da": "D.LGS. 13 LUGLIO 2017, N. 116", "dal": "2027-10-31",
                                 "precisione": "INDICATIVO", "fonte": "abrogazione rinviata (note di Normattiva)"}
        assert "abrogazione" in t.avvisi[0] and "2027-10-31" in t.avvisi[0]
        assert "versione precedente, in vigore dal 1998-07-04" in t.avvisi[0]
        assert richieste[-1] == DISP_ATT_CC + "73bis!vig=2021-10-30"

    async def test_verifica_citazioni_says_the_repeal_is_deferred(self, monkeypatch):
        from mcp_legal_it.tools import legal_citations as lc

        _serve(monkeypatch, {DISP_ATT_CC + "73bis": ART73BIS, DISP_ATT_CC + "73bis!vig=2021-10-30": ART73BIS_V2},
               _tabelle_art27("73-bis"))
        verdetto, nota = await lc._verifica_norma("art. 73-bis disp. att. c.c.")
        assert verdetto == "verificata" and "abrogazione" in nota and "2027-10-31" in nota

    async def test_the_history_says_the_repeal_is_not_in_force(self, monkeypatch):
        _serve(monkeypatch, {DISP_ATT_CC + "73bis": ART73BIS}, _tabelle_art27("73-bis"))
        m = await api.modifiche_articolo("art. 73-bis disp. att. c.c.")
        assert m.precisione == "INDICATIVO"
        assert "abrogato" in m.avvisi[0] and "il testo in vigore è la versione 2, dal 1998-07-04" in m.avvisi[0]


class TestRevisione:
    """Review of this fix: the edges that must stay conservative."""

    def test_a_comma_is_read_only_in_the_list_of_commi(self):
        def riga(parti):
            return [{"atti": [{"atto": {"tipo_atto": "decreto legge", "data": "2026-06-12", "numero_atto": "100"},
                               "disposizioni": [{"parti": parti}]}]}]

        assert vd.atti_del_comma(riga("comma 3"), "3") == {("decreto legge", "2026-06-12", "100")}
        assert vd.atti_del_comma(riga("commi 1, 2 e 3"), "3")
        assert vd.atti_del_comma(riga(None), "3")  # a row naming no part touches the whole article
        assert not vd.atti_del_comma(riga("comma 1, lettera b), numero 3)"), "3")
        assert not vd.atti_del_comma(riga("comma 30"), "3") and not vd.atti_del_comma(riga("comma 3-bis"), "3")

    def test_a_comma_number_alone_on_its_line(self):
        assert vd.stato_disposizione("2.\nAltro.\n3.\nLe disposizioni dell'articolo 27 entrano in vigore il 31 "
                                     "ottobre 2027.\n4.\nLe disposizioni entrano in vigore il 1° gennaio 2019.", "3",
                                     OGGI) == ("rinvio", "2027-10-31")

    @staticmethod
    def _art32_giu(monkeypatch):
        originale = scraper._normattiva_page

        async def art32_giu(url, articolo=None):
            if "~art32" in url:
                raise scraper.httpx.ConnectError("rete")
            return await originale(url, articolo)

        monkeypatch.setattr(scraper, "_normattiva_page", art32_giu)

    @staticmethod
    def _sopra_la_v4():
        """Art. 765's table with version 5 made by an act outside the chain (d.lgs. 164/2024)
        over version 4, which carries the deferred act."""
        tabella = _tabella("765", TABELLE_ART27)
        tabella["righe"][5] = [{"progressivo": 1, "data_gu": "2024-11-11", "atti": [
            {"atto": {"tipo_atto": "decreto legislativo", "data": "2024-10-31", "numero_atto": "164",
                      "gazzetta": "G.U. 11/11/2024, n.264", "data_gu": "2024-11-11",
                      "descrizione": "Il DECRETO LEGISLATIVO 31 ottobre 2024, n. 164"},
             "disposizioni": [{"disposizione": "art. 3, comma 1", "tipo": "modifica", "parti": "comma 2",
                               "testo": "ha disposto (con l'art. 3, comma 1) la modifica dell'art. 765, comma 2"}]}]}]
        return tabella

    async def test_a_date_not_read_over_a_later_act_is_still_said(self, monkeypatch):
        """Review of #179 (B1): provision not readable, version 5 by another act over the deferred
        version 4. With the date read this is a case B; without it, never ESATTO either."""
        _serve(monkeypatch, {CPC + "765": ART765}, {"765": self._sopra_la_v4()})
        self._art32_giu(monkeypatch)
        t = await api.testo_articolo(_cpc("765"), canale="html")
        assert t.precisione == "INDICATIVO"
        assert "non è stato possibile leggere sull'art. 32, comma 3" in t.avvisi[0]

    async def test_a_date_not_read_over_a_later_act_in_the_history(self, monkeypatch):
        _serve(monkeypatch, {CPC + "765": ART765}, {"765": self._sopra_la_v4()})
        self._art32_giu(monkeypatch)
        m = await api.modifiche_articolo("art. 765 c.p.c.")
        assert m.precisione == "INDICATIVO" and "art. 32, comma 3" in m.avvisi[0]

    async def test_a_stale_chain_with_no_version_of_the_deferred_act_says_nothing(self, monkeypatch):
        """No version read carries the deferred act: the text holds none of it, nothing is said."""
        tabella = _tabella("765", TABELLE_ART27)
        tabella["righe"] = {k: [r for r in v if all(a["atto"]["numero_atto"] != "116" for a in r["atti"])]
                            for k, v in tabella["righe"].items()}
        _serve(monkeypatch, {CPC + "765": ART765}, {"765": tabella})
        self._art32_giu(monkeypatch)
        t = await api.testo_articolo(_cpc("765"), canale="html")
        assert t.esito == "trovato" and t.precisione == "ESATTO" and not any("2026-10-31" in a for a in t.avvisi)

    @pytest.mark.parametrize("comma3", [
        "COMMA ABROGATO DAL D.L. 1 FEBBRAIO 2027, N. 1.",
        "Le disposizioni dell'articolo 27 entrano in vigore il 31 ottobre 2027 e quelle dell'articolo 28 entrano "
        "in vigore il 1° gennaio 2027.",
    ], ids=["comma-abrogato", "due-date-passate"])
    async def test_a_provision_read_with_no_future_date_defers_nothing(self, monkeypatch, comma3):
        """Review of #179 (M1): after 31/10/2027, a comma repealed (spent) or stating only dates
        already past is no deferral: art. 7 stays ESATTO, never INDICATIVO for ever."""
        monkeypatch.setenv("LEGAL_TODAY", "2027-11-01")
        art32 = ART32_116.replace(
            "Le disposizioni dell'articolo 27 entrano in vigore il <div class=\"ins-akn\" eid=\"ins_1\">((31 ottobre "
            "2027))</div>.", comma3)
        assert art32 != ART32_116
        _, tabelle = _serve(monkeypatch, {CPC + "7": ART7, DLGS_116 + "32": art32}, None)
        t = await api.testo_articolo(_cpc("7"), canale="html")
        assert t.esito == "trovato" and t.precisione == "ESATTO" and tabelle == []
        assert not any("2027-10-31" in a or "2026-10-31" in a for a in t.avvisi)

    async def test_a_deferred_repeal_with_the_table_unread_never_says_amendments(self, monkeypatch):
        _serve(monkeypatch, {DISP_ATT_CC + "73bis": ART73BIS}, {"esito": "verifica_non_disponibile"})
        rif = api.leggi_riferimento("art. 73-bis disp. att. c.c.").norma_data[0]
        t = await api.testo_articolo(rif, canale="html")
        assert t.precisione == "INDICATIVO" and "ABROGATO" in t.article_text  # the page, never a guess
        assert "Normattiva dà l'articolo come abrogato: non è stato possibile leggere il testo in vigore" in t.avvisi[0]
        assert "le contiene" not in t.avvisi[0]
