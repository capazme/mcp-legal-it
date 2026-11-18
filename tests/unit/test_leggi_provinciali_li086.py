"""Laws of the Province autonome di Trento e di Bolzano: the regional laws' guard (LI-086).

«legge 13/1997 della Provincia autonoma di Trento» read through the State patterns was the
State's legge 13/1997: the wrong act, in silence. Like a regional law, a provincial law is
«fonte non coperta», never resolved, has no Normattiva address, and the citation gate warns on
each one cited. «l.p.a.», «LPA» and «l. proc. amm.», keys of the tables, keep their meaning.
"""

import httpx
import pytest

from mcp_legal_it.core.citazioni import leggi_provinciali_nel_testo, leggi_regionali_nel_testo, norme_nel_testo
from mcp_legal_it.core.riferimenti import _parse_reference, _resolve_act, _unresolved_act_error
from mcp_legal_it.lib.visualex import Norma, NormaVisitata, scraper
from mcp_legal_it.lib.visualex.map import legge_provinciale, legge_regionale, resolve_atto
from mcp_legal_it.tools import legal_citations as lc
from tests.unit.test_citation_gate import HOOK, NAGS, SILENT, isolated_hook, run, session  # noqa: F401

NON_COPERTA = ("**Errore**: fonte non coperta — le leggi provinciali delle Province autonome di Trento e di "
               "Bolzano non sono coperte dai tool di questo server: verifica il testo sul Bollettino ufficiale "
               "della Regione Trentino-Alto Adige/Südtirol o sulla banca dati della Provincia")

PROVINCIALI = [
    "l.p. 13/1997", "L.P. 13/1997", "l. p. 13/1997", "LP 13/1997", "L.P. Bolzano 13/1997",
    "L.P. 13/1997 Südtirol", "legge provinciale 13/1997", "legge prov. 13/1997", "l. prov. 13/1997",
    "legge provinciale Trento 13/1997", "legge provinciale 10 maggio 1997, n. 13",
    "legge della Provincia autonoma di Trento 13/1997",
    # Every spelling of «legge» the State patterns read, with the province after the extremes.
    "legge 13/1997 della Provincia autonoma di Trento", "L. 13/1997 Prov. Trento", "l. 13/1997 Prov. Bolzano",
    "legge 10 maggio 1997, n. 13 della Provincia autonoma di Bolzano", "legge 13/1997 (Provincia di Trento)",
    "legge 13/1997 della Provincia autonoma di Bolzano/Alto Adige", "legge 13/1997 P.A. Trento",
    "legge 13/1997 PAT", "L. 13/1997 PAB", "legge 13/1997 (Trento)", "legge 13/1997 della Provincia autonoma",
    "legge 13/1997 Prov. Aut. Bolzano", "L 13/1997 Provincia di Trento", "L.13/1997 Prov. Trento",
]


class TestResolver:
    @pytest.mark.parametrize("nome", PROVINCIALI)
    def test_a_provincial_law_is_never_resolved(self, nome):
        assert legge_provinciale(nome) and not legge_regionale(nome)
        assert resolve_atto(nome) is None and _resolve_act(nome) is None

    @pytest.mark.parametrize("nome", PROVINCIALI)
    def test_it_is_a_source_not_covered(self, nome):
        assert _unresolved_act_error(nome) == NON_COPERTA

    @pytest.mark.parametrize("riferimento", [f"art. 3 {nome}" for nome in PROVINCIALI])
    def test_an_article_of_it_is_parsed_but_not_resolved(self, riferimento):
        articolo, atto = _parse_reference(riferimento)
        assert articolo == "3" and _resolve_act(atto) is None

    @pytest.mark.parametrize("nome", ["L. 13/1997", "legge 13/1997", "legge 241/1990 della provincia di Roma",
                                      "legge 56/2014 sulle province", "l. 3/2015"])
    def test_the_state_laws_still_resolve(self, nome):
        assert not legge_provinciale(nome)
        assert _resolve_act(nome)["tipo_atto"] == "legge"

    def test_the_table_keys_keep_their_meaning(self):
        assert not legge_provinciale("l.p.a.") and not legge_provinciale("LPA")
        assert _unresolved_act_error("l.p.a.").startswith("**Errore**: nome ambiguo")
        assert _resolve_act("l. proc. amm.")["numero_atto"] == "241"


class TestNessunUrnProvinciale:
    @pytest.mark.parametrize("tipo", ["legge provinciale", "l.p.", "provincia.trento:legge",
                                      "urn:nir:provincia.bolzano:legge"])
    def test_the_urn_builder_gives_no_address(self, tipo):
        norma = Norma(tipo_atto=tipo, data="1997-05-10", numero_atto="13")
        assert norma.url() == "" and NormaVisitata(norma=norma, numero_articolo="3").url() == ""

    @pytest.mark.asyncio
    async def test_no_request_and_the_provincial_message(self, monkeypatch):
        def no_network(*a, **k):
            raise AssertionError("no request for a provincial act")

        monkeypatch.setattr(httpx, "AsyncClient", no_network)
        nv = NormaVisitata(norma=Norma(tipo_atto="legge provinciale", data="1997", numero_atto="13"),
                           numero_articolo="3")
        assert (await scraper.fetch_article(nv))["error"].startswith("fonte non coperta — le leggi provinciali")
        out = await lc._cite_law_impl("art. 3 legge 13/1997 della Provincia autonoma di Trento")
        assert out == NON_COPERTA


class TestLettori:
    TESTO = ("Si applica l'art. 3 della legge 13/1997 della Provincia autonoma di Trento, e l'art. 2 della "
             "l.p. Bolzano 4/2005.")

    def test_no_article_is_read_as_a_state_act(self):
        assert norme_nel_testo(self.TESTO) == []

    def test_every_provincial_law_is_found_once(self):
        assert leggi_provinciali_nel_testo(self.TESTO + " La l.p. Bolzano 4/2005 resta.") == [
            "legge 13/1997 della Provincia autonoma di Trento", "l.p. Bolzano 4/2005"]
        assert leggi_regionali_nel_testo(self.TESTO) == []

    @pytest.mark.parametrize("testo", ["la legge provinciale prevede 3 casi", "la l.p.a. 3/2020",
                                       "l'art. 3 l. 241/1990", "le province autonome"])
    def test_prose_without_a_provincial_citation(self, testo):
        assert leggi_provinciali_nel_testo(testo) == []


class TestGate:
    def test_a_provincial_law_is_warned_on_and_not_asked_as_a_state_law(self, tmp_path):
        t = session(tmp_path).prompt().say("Si applica l'art. 3 della legge 13/1997 della Provincia autonoma di Trento.")
        r = run({"transcript_path": str(t.write())})
        assert r.returncode == NAGS
        assert "legge provinciale: le leggi provinciali non sono coperte" in r.stderr and "(cite_law)" not in r.stderr

    def test_fuori_copertura_lets_it_through(self, tmp_path):
        t = session(tmp_path).prompt().say("Si applica la l.p. 13/1997 (fuori copertura).")
        assert run({"transcript_path": str(t.write())}).returncode == SILENT

    def test_the_opt_out_is_respected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LEGAL_CITATION_GATE", "off")
        t = session(tmp_path).prompt().say("Si applica la l.p. 13/1997.")
        assert run({"transcript_path": str(t.write())}).returncode == SILENT

    @pytest.mark.parametrize("testo, avvisa", [("Si applica la L.P. Bolzano 13/1997.", True),
                                                ("La legge provinciale prevede 3 casi.", False),
                                                ("Vedi la l.p.a. 3/2020 (fuori copertura).", False)])
    def test_the_fallback_reader(self, tmp_path, isolated_hook, testo, avvisa):
        t = session(tmp_path).prompt().say(testo)
        r = run({"transcript_path": str(t.write())}, python_args=("-I", "-S"), hook=isolated_hook)
        assert ("legge provinciale:" in r.stderr) is avvisa
