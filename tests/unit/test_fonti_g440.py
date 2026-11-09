"""Sources from the blind corpus (G-440): CCD2, the Corte costituzionale's norme integrative,
and the citation gate's identity of an act named through its annex.

- «CCD2» is dir. (UE) 2023/2225 (CELLAR title checked 9 November 2026). «Direttiva credito ai
  consumatori» stays unresolved: it also names dir. 2008/48/CE.
- The «Norme integrative per i giudizi davanti alla Corte costituzionale» are a deliberation
  of the Court that Normattiva does not publish: an explicit «fonte non coperta», never a
  nearby act, and a citation the gate flags as out of coverage.
- An annex the resolver names is part of the act's identity: «art. 1 testo unico della
  giustizia tributaria» is not «art. 1 d.lgs. 175/2024», «art. 1 disp. att. c.p.a.» is not
  «art. 1 c.p.a.».
"""

import pytest

import mcp_legal_it.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from mcp_legal_it.core.citazioni import norme_nel_testo, riferimento_in_identita
from mcp_legal_it.core.riferimenti import _resolve_act, _unresolved_act_error
from mcp_legal_it.lib.visualex.map import fonte_non_coperta, resolve_atto
from mcp_legal_it.tools import legal_citations as lc

CCD2 = {"tipo_atto": "direttiva ue", "data": "2023", "numero_atto": "2225"}


class TestCcd2:
    @pytest.mark.parametrize("nome", ["ccd2", "CCD2", "ccd 2", "CCD II", "direttiva CCD2", "direttiva ccd 2"])
    def test_aliases(self, nome):
        assert resolve_atto(nome) == CCD2

    def test_the_bare_name_is_ambiguous_and_stays_unresolved(self):
        # 2008/48/CE is repealed by 2023/2225 only from 20 November 2026.
        assert _resolve_act("direttiva credito ai consumatori") is None
        assert _resolve_act("ccd") is None

    def test_the_url_is_the_directives(self):
        from mcp_legal_it.lib.visualex.models import Norma

        assert Norma(**CCD2).url().endswith("/eli/dir/2023/2225/oj/ita")


class TestNormeIntegrative:
    @pytest.mark.parametrize("nome", [
        "norme integrative per i giudizi davanti alla Corte costituzionale",
        "Norme integrative per i giudizi dinanzi alla Corte costituzionale",
        "delle norme integrative per i giudizi davanti alla Corte costituzionale",
        "norme integrative della Corte costituzionale",
        "norme integrative per i giudizi innanzi alla Corte costituzionale",
        "N.I. Corte cost.",
        "N.I. Corte cost",
        "n.i. Corte costituzionale",
        "norme integrative corte cost.",
    ])
    def test_known_as_uncovered(self, nome):
        assert _resolve_act(nome) is None
        assert fonte_non_coperta(nome)

    def test_cite_law_says_out_of_coverage_and_suggests_nothing(self):
        out = _unresolved_act_error("norme integrative per i giudizi davanti alla Corte costituzionale")
        assert out.startswith("**Errore**: fonte non coperta")
        assert "Normattiva non le pubblica" in out and "21A06516" in out
        assert "Forse intendevi" not in out

    @pytest.mark.asyncio
    async def test_cite_law_never_fetches(self, monkeypatch):
        async def boom(*a, **k):
            raise AssertionError("an uncovered source is never fetched")

        from mcp_legal_it.core import norme

        monkeypatch.setattr(norme, "fetch_article", boom)
        out = await lc._cite_law_impl("art. 10 norme integrative per i giudizi davanti alla Corte costituzionale")
        assert "fonte non coperta" in out

    def test_a_bare_name_is_not_the_courts(self):
        # «Norme integrative» alone may be a CCNL's or a regolamento's: no identity given.
        assert fonte_non_coperta("norme integrative") is None
        assert "fonte non coperta" not in _unresolved_act_error("norme integrative")

    @pytest.mark.parametrize("testo", [
        "L'art. 3 delle norme integrative del CCNL commercio prevede il preavviso.",
        "Ai sensi dell'art. 2 delle norme integrative del regolamento condominiale.",
    ])
    def test_the_gate_ignores_other_norme_integrative(self, testo):
        assert norme_nel_testo(testo) == []

    @pytest.mark.parametrize("testo", [
        "Si veda l'art. 24 delle norme integrative della Corte costituzionale.",
        "Si veda l'art. 24 delle norme integrative per i giudizi dinanzi alla Corte costituzionale.",
        "Si veda l'art. 24 delle Norme integrative Corte cost.",
        "Si veda l'art. 24 delle norme integrative per i giudizi innanzi alla Corte costituzionale.",
        "Si veda l'art. 24 N.I. Corte cost.",
        "Si veda l'art. 24 delle N.I. della Corte costituzionale.",
    ])
    def test_the_gate_flags_the_courts_other_spellings(self, testo):
        assert [(n.atto, n.articolo) for n in norme_nel_testo(testo)] == [(None, "24")]

    @pytest.mark.parametrize("riferimento", [
        "art. 24 norme integrative per i giudizi innanzi alla Corte costituzionale",
        "art. 24 N.I. Corte cost.",
    ])
    @pytest.mark.asyncio
    async def test_cite_law_on_the_other_spellings(self, riferimento):
        assert "fonte non coperta" in await lc._cite_law_impl(riferimento)

    def test_a_bare_sigla_is_not_the_courts(self):
        # «N.I.» alone names nothing: only with the Court.
        assert fonte_non_coperta("N.I.") is None
        assert norme_nel_testo("Si veda l'art. 24 delle N.I. del contratto.") == []

    def test_other_unknown_acts_keep_their_message(self):
        assert "non riconosciuto" in _unresolved_act_error("legge immaginaria")

    def test_the_gate_flags_a_citation_as_out_of_coverage(self):
        testo = ("Il termine decorre ai sensi dell'art. 24 delle norme integrative per i giudizi "
                 "davanti alla Corte costituzionale.")
        trovate = norme_nel_testo(testo)
        assert [(n.atto, n.articolo) for n in trovate] == [(None, "24")]


class TestAnnexInTheGatesIdentity:
    def test_the_testo_unico_is_not_the_decree(self):
        tu = riferimento_in_identita("art. 1 testo unico della giustizia tributaria")
        decreto = riferimento_in_identita("art. 1 d.lgs. 175/2024")
        assert tu and decreto and tu != decreto
        assert tu[0].endswith(";175:1")

    def test_disp_att_cpa_is_not_the_cpa(self):
        assert riferimento_in_identita("art. 1 disp. att. c.p.a.") != riferimento_in_identita("art. 1 c.p.a.")

    def test_aliases_of_one_act_still_share_it(self):
        assert (riferimento_in_identita("art. 5 testo unico giustizia tributaria")
                == riferimento_in_identita("art. 5 TUGT"))
        assert riferimento_in_identita("art. 2043 c.c.") == riferimento_in_identita("art. 2043 codice civile")
