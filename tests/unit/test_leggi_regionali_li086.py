"""Regional laws: a minimal guard (LI-086). Real coverage is the regions branch's (LI-076).

- A regional citation answers «fonte non coperta», like ``FONTI_NON_COPERTE``, and is never
  read as a State law: «l.r. 65/2014» or «legge 10 novembre 2014, n. 65 della Regione Toscana»
  served as the legge 65/2014 would be the wrong act in silence.
- No code path builds or fetches a Normattiva URN for a regional act: Normattiva's resolver
  answers a regional URN with the State's act of the same year and number (act_dates.py).
- The citation gate warns on every regional law the answer cites (no tool result can back one),
  lets a line marked «fuori copertura» through, and respects ``LEGAL_CITATION_GATE=off``.
"""

import pathlib
import re

import httpx
import pytest

from mcp_legal_it.core.citazioni import leggi_regionali_nel_testo, norme_nel_testo
from mcp_legal_it.core.riferimenti import _parse_reference, _resolve_act, _unresolved_act_error
from mcp_legal_it.lib.visualex import Norma, NormaVisitata
from mcp_legal_it.lib.visualex import scraper
from mcp_legal_it.lib.visualex.map import legge_regionale, resolve_atto
from mcp_legal_it.tools import legal_citations as lc
from tests.unit.test_citation_gate import HOOK, NAGS, SILENT, isolated_hook, run, session  # noqa: F401

SERVER = pathlib.Path(__file__).resolve().parents[2] / "plugin" / "server" / "mcp_legal_it"

REGIONALI = [
    "l.r. Toscana 65/2014",
    "l.r. 65/2014",
    "L.R. n. 3/2015",
    "l. r. 65/2014",
    "LR 65/2014",
    "L.R.T. 65/2014",
    "legge regionale 12 marzo 2015, n. 3",
    "legge regionale n. 3/2015",
    "legge reg. Lazio 3/2015",
    "legge regionale Lombardia 12 marzo 2015, n. 3",
    "legge della Regione Toscana 10 novembre 2014, n. 65",
    "legge Regione Toscana 65/2014",
    "legge 10 novembre 2014, n. 65 della Regione Toscana",
    "legge 65/2014 della Regione Toscana",
    "legge 65/2014 (Regione Toscana)",
    "legge 10 novembre 2014, n. 65 (Toscana)",
    "legge 65/2014 della Toscana",
    "legge 3/2015 della Regione autonoma della Sardegna",
    "L.R. Toscana n. 65 del 10 novembre 2014",
    "della l.r. Toscana 65/2014",
    # «l.» / «L» / «Reg.» / «R.»: every spelling of «legge» the State patterns read (review of #191).
    "L. 65/2014 della Regione Toscana",
    "L. 65/2014 (Regione Toscana)",
    "l. n. 65/2014 Regione Toscana",
    "L. 65/2014 Toscana",
    "l. 10 novembre 2014, n. 65 Regione Toscana",
    "legge 65/2014 Reg. Toscana",
    "legge 65/2014 R. Toscana",
    "L 65/2014 Regione Toscana",
    "L.65/2014 Regione Toscana",
    "legge n. 65 del 2014 della Regione Toscana",
    "l. Regione Toscana 65/2014",
]


class TestResolver:
    @pytest.mark.parametrize("nome", REGIONALI)
    def test_a_regional_law_is_never_resolved(self, nome):
        assert legge_regionale(nome)
        assert resolve_atto(nome) is None
        assert _resolve_act(nome) is None
        assert _resolve_act(nome, data="2026-11-18") is None

    @pytest.mark.parametrize("nome", REGIONALI)
    def test_it_is_a_source_not_covered(self, nome):
        out = _unresolved_act_error(nome)
        assert out == ("**Errore**: fonte non coperta — le leggi regionali non sono coperte dai tool di "
                       "questo server: verifica il testo sul Bollettino ufficiale o sulla banca dati della Regione")

    @pytest.mark.parametrize("riferimento", [f"art. 3 {nome}" for nome in REGIONALI])
    def test_an_article_of_it_is_parsed_but_not_resolved(self, riferimento):
        articolo, atto = _parse_reference(riferimento)
        assert articolo == "3" and _resolve_act(atto) is None

    @pytest.mark.parametrize("nome", ["legge 65/2014", "L. 65/2014", "legge 10 novembre 2014, n. 65",
                                      "legge 241/1990", "l. 3/2015", "L 241/1990", "L.241/1990",
                                      "legge 241/1990, che si applica alle regioni"])
    def test_the_state_laws_still_resolve(self, nome):
        assert not legge_regionale(nome)
        assert _resolve_act(nome)["tipo_atto"] == "legge"

    @pytest.mark.parametrize("nome", ["legge costituzionale 3/2001", "legge fallimentare", "LRT", "lrt",
                                      "regolamento (UE) 2016/679"])
    def test_names_that_only_look_alike_are_not_regional(self, nome):
        assert not legge_regionale(nome)


class TestNessunUrnRegionale:
    @pytest.mark.parametrize("tipo", ["legge regionale", "l.r.", "L.R.", "regione.toscana:legge",
                                      "urn:nir:regione.toscana:legge", "legge della regione toscana"])
    def test_the_urn_builder_gives_no_address(self, tipo):
        norma = Norma(tipo_atto=tipo, data="2014-11-10", numero_atto="65")
        assert norma.url() == "" and norma.url(article="3") == ""
        assert NormaVisitata(norma=norma, numero_articolo="3").url() == ""

    @pytest.mark.asyncio
    async def test_fetch_article_refuses_without_a_request(self, monkeypatch):
        def no_network(*a, **k):
            raise AssertionError("no request for a regional act")

        monkeypatch.setattr(httpx, "AsyncClient", no_network)
        nv = NormaVisitata(norma=Norma(tipo_atto="legge regionale", data="2014", numero_atto="65"),
                           numero_articolo="3")
        result = await scraper.fetch_article(nv)
        assert result["text"] == "" and result["url"] == ""
        assert result["error"].startswith("fonte non coperta — le leggi regionali")

    @pytest.mark.asyncio
    async def test_fetch_law_article_and_cite_law_refuse_without_a_request(self, monkeypatch):
        def no_network(*a, **k):
            raise AssertionError("no request for a regional act")

        monkeypatch.setattr(httpx, "AsyncClient", no_network)
        out = await lc._fetch_law_article_impl("legge regionale", "3", "2014", "65")
        assert "fonte non coperta" in out and "normattiva.it" not in out
        for riferimento in ("art. 3 l.r. Toscana 65/2014", "art. 3 legge 65/2014 della Regione Toscana"):
            out = await lc._cite_law_impl(riferimento)
            assert out.startswith("**Errore**: fonte non coperta"), out

    def test_no_source_file_builds_a_regional_normattiva_urn(self):
        # A builder of «urn:nir:regione.…» would reach the State's act on Normattiva.
        trovati = [str(p.relative_to(SERVER)) for p in SERVER.rglob("*.py")
                   if re.search(r"urn:nir:regione|nir:regione\.", p.read_text(encoding="utf-8"))]
        assert not trovati, trovati


class TestLettoreDelleCitazioni:
    TESTO = ("Ai sensi dell'art. 3 della l.r. Toscana 65/2014 e dell'art. 2 della legge regionale 12 marzo "
             "2015, n. 3. Vedi anche l'art. 4 della legge 10 novembre 2014, n. 65 della Regione Toscana.")

    def test_no_article_of_a_regional_law_is_read_as_a_state_act(self):
        assert norme_nel_testo(self.TESTO) == []

    def test_every_regional_law_is_found_once(self):
        assert leggi_regionali_nel_testo(self.TESTO + " La l.r. Toscana 65/2014 resta.") == [
            "l.r. Toscana 65/2014", "legge regionale 12 marzo 2015, n. 3",
            "legge 10 novembre 2014, n. 65 della Regione Toscana"]

    @pytest.mark.parametrize("testo, letta", [
        ("Si veda la L.R. Toscana n. 65 del 10 novembre 2014.", "L.R. Toscana n. 65 del 10 novembre 2014"),
        ("Ai sensi dell'art. 5 della legge regionale n. 3, si provvede.", "legge regionale n. 3"),
        ("Lo prevede la l.r. n. 3.", "l.r. n. 3"),
        ("Art. 3 della legge 3/2015 della Regione autonoma della Sardegna.",
         "legge 3/2015 della Regione autonoma della Sardegna"),
        ("Art. 4 della legge 10 novembre 2014, n. 65 (Toscana).", "legge 10 novembre 2014, n. 65 (Toscana"),
    ])
    def test_the_forms_the_review_found(self, testo, letta):
        assert leggi_regionali_nel_testo(testo) == [letta]
        assert norme_nel_testo(testo) == []

    def test_an_article_of_a_regional_law_is_never_silent(self):
        # A form the pattern does not read: the start of what follows the article is listed.
        testo = "Si applica l'art. 5 della legge regionale Toscana numero tre del 2015, e altro."
        assert norme_nel_testo(testo) == []
        assert leggi_regionali_nel_testo(testo) == ["della legge regionale Toscana numero tre del 2015"]

    @pytest.mark.parametrize("testo", ["la legge regionale prevede 3 casi", "la s.r.l. 3/2020",
                                       "l'art. 3 l. 65/2014", "le leggi regionali in materia",
                                       "la l. recante norme n. 15/2005"])
    def test_prose_without_a_regional_citation(self, testo):
        assert leggi_regionali_nel_testo(testo) == []

    def test_the_state_law_next_to_it_is_still_read(self):
        trovate = norme_nel_testo("L'art. 3 l. 65/2014 e l'art. 3 l.r. 65/2014.")
        assert [(n.atto.rsplit("stato:", 1)[1], n.articolo) for n in trovate] == [("legge:2014;65", "3")]

    @pytest.mark.asyncio
    async def test_verifica_citazioni_says_not_covered(self):
        verdetto, nota = await lc._verifica_norma("art. 3 l.r. Toscana 65/2014")
        assert verdetto == "non trovata"
        data, _ = await lc._cite_law_lookup("art. 3 l.r. Toscana 65/2014")
        assert data["errore"].startswith("fonte non coperta — le leggi regionali")


class TestGate:
    def test_a_regional_law_in_the_answer_is_warned_on(self, tmp_path):
        t = session(tmp_path).prompt().say("Si applica l'art. 3 della l.r. Toscana 65/2014.")
        r = run({"transcript_path": str(t.write()), "hook_event_name": "Stop"})
        assert r.returncode == NAGS
        assert "l.r. Toscana 65/2014 (legge regionale: non coperta dai tool del server" in r.stderr
        assert "Bollettino ufficiale o sulla banca dati della Regione" in r.stderr

    @pytest.mark.parametrize("testo", ["Si applica l'art. 1 L. 65/2014 della Regione Toscana.",
                                       "Si applica l'art. 1 legge 65/2014 Reg. Toscana."])
    def test_a_state_like_spelling_is_warned_on_and_not_asked_as_a_state_law(self, tmp_path, testo):
        r = run({"transcript_path": str(session(tmp_path).prompt().say(testo).write())})
        assert r.returncode == NAGS
        assert "legge regionale: non coperta" in r.stderr and "(cite_law)" not in r.stderr
        assert norme_nel_testo(testo) == []

    def test_a_bare_mention_without_an_article_is_warned_on_too(self, tmp_path):
        t = session(tmp_path).prompt().say("La legge regionale 12 marzo 2015, n. 3 disciplina la materia.")
        assert run({"transcript_path": str(t.write())}).returncode == NAGS

    def test_fuori_copertura_lets_it_through(self, tmp_path):
        t = session(tmp_path).prompt().say("Si applica la l.r. Toscana 65/2014 (fuori copertura).")
        assert run({"transcript_path": str(t.write())}).returncode == SILENT

    def test_the_opt_out_is_respected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LEGAL_CITATION_GATE", "off")
        t = session(tmp_path).prompt().say("Si applica la l.r. Toscana 65/2014.")
        assert run({"transcript_path": str(t.write())}).returncode == SILENT

    def test_a_generic_mention_is_not_a_citation(self, tmp_path):
        t = session(tmp_path).prompt().say("La materia è disciplinata dalla legge regionale.")
        assert run({"transcript_path": str(t.write())}).returncode == SILENT

    @pytest.mark.parametrize("testo", ["La legge regionale prevede 3 casi.", "La l. recante norme n. 15/2005."])
    def test_the_fallback_reader_does_not_read_prose_as_a_regional_law(self, tmp_path, isolated_hook, testo):
        t = session(tmp_path).prompt().say(testo)
        r = run({"transcript_path": str(t.write())}, python_args=("-I", "-S"), hook=isolated_hook)
        assert "legge regionale: non coperta" not in r.stderr

    def test_the_fallback_reader_does_not_read_a_word_after_l(self, tmp_path, isolated_hook):
        t = session(tmp_path).prompt().say("La l. recante norme n. 15/2005 si applica (fuori copertura).")
        t.say("Ne parla la l. recante norme n. 15/2005.")
        r = run({"transcript_path": str(t.write())}, python_args=("-I", "-S"), hook=isolated_hook)
        assert "legge regionale" not in r.stderr

    def test_the_fallback_reader_warns_too(self, tmp_path, isolated_hook):
        t = session(tmp_path).prompt().say("Si applica la l.r. Toscana 65/2014.")
        r = run({"transcript_path": str(t.write())}, python_args=("-I", "-S"), hook=isolated_hook)
        assert r.returncode == NAGS and "legge regionale: non coperta" in r.stderr
