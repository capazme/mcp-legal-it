"""Spellings of acts that an external citation corpus cites and the tables did not know (G-440).

Each alias points to an act checked live on 11 November 2026: CELLAR titles for the EU
regulations, Normattiva titles for the Italian laws and laws of ratification, consob.it for
Consob's delibere. What Normattiva and EUR-Lex do not serve (Consob's regulations, the CEDU
and its protocols, treaties) is a declared «fonte non coperta» with its identity, never a
nearby act, and the citation gate flags it. Ambiguous names stay unresolved.
"""

import pytest

import mcp_legal_it.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from mcp_legal_it.core.citazioni import identita_atto, norme_nel_testo
from mcp_legal_it.core.riferimenti import _resolve_act, _unresolved_act_error
from mcp_legal_it.lib.visualex.map import fonte_non_coperta
from mcp_legal_it.lib.visualex.models import Norma


def _ue(anno, numero):
    return {"tipo_atto": "regolamento ue", "data": anno, "numero_atto": numero}


class TestRegolamentiUe:
    @pytest.mark.parametrize("nome,atto", [
        ("MAR", _ue("2014", "596")),
        ("Regolamento MAR", _ue("2014", "596")),
        ("Regolamento Europeo sugli Abusi di Mercato", _ue("2014", "596")),
        ("Market Abuse Regulation", _ue("2014", "596")),
        ("MiCAR", _ue("2023", "1114")),
        ("MiFIR", _ue("2014", "600")),
        ("Regolamento Prospetto", _ue("2017", "1129")),
        ("Regolamento DLT", _ue("2022", "858")),
        ("Regolamento CSDR", _ue("2014", "909")),
        ("Regolamento SAFE", _ue("2025", "1106")),
        ("Regolamento eIDAS", _ue("2014", "910")),
        ("Regolamento DORA", _ue("2022", "2554")),
        ("regolamento (UE) DORA", _ue("2022", "2554")),
        ("Regolamento sull'IA", _ue("2024", "1689")),
        ("Regolamento europeo sull'intelligenza artificiale", _ue("2024", "1689")),
    ])
    def test_aliases(self, nome, atto):
        assert _resolve_act(nome) == atto

    @pytest.mark.parametrize("nome", [
        "Regolamento condominiale", "regolamento emittenti", "Regolamento Mercati", "regolamento",
        "Regolamento NIS2",  # NIS2 is a directive: «Regolamento <nickname>» only takes regulations
        "Regolamento interno", "regolamento di condominio",
    ])
    def test_regolamento_before_a_word_is_no_eu_act(self, nome):
        info = _resolve_act(nome)
        assert info is None or info.get("tipo_atto") != "regolamento ue"

    @pytest.mark.parametrize("nome", ["prospetto", "dlt", "safe", "Decreto FinTech", "CSE",
                                      "Convenzione di Ginevra", "Decreto RENT"])
    def test_ambiguous_names_stay_unresolved(self, nome):
        assert _resolve_act(nome) is None
        assert fonte_non_coperta(nome) is None


class TestMarIsNotMarch:
    @pytest.mark.parametrize("nome", ["mar.", "Mar.", "marzo"])
    def test_a_month_is_no_act(self, nome):
        assert _resolve_act(nome) is None

    def test_mar_after_the_article_is_the_regulation(self):
        trovate = norme_nel_testo("Si applica l'art. 17 MAR agli emittenti.")
        assert [(n.atto, n.articolo) for n in trovate] == [(identita_atto(_ue("2014", "596")), "17")]

    @pytest.mark.parametrize("testo", [
        "Ai sensi dell'art. 103 del d.l. 17 mar. 2020, n. 18, i termini sono sospesi.",
        "Il termine scade il 17 mar art. 2 del contratto.",
        "Entro il 10 marzo, l'art. 5 del regolamento interno si applica.",
        "Dal 17 mar. l'art. 3 dello statuto sociale prevede la convocazione.",
        "Per l'art. 17 mar. 2020 la comunicazione è tardiva.",
        "Si applica l'art. 17 mar 2020, n. 18.",
    ])
    def test_a_date_never_gives_the_mar(self, testo):
        mar = identita_atto(_ue("2014", "596"))
        assert all(n.atto != mar for n in norme_nel_testo(testo)), norme_nel_testo(testo)


class TestTestiUniciEcodici:
    @pytest.mark.parametrize("nome,numero", [
        ("t.u. edilizia", "380"), ("t.u.ed.", "380"), ("t.u. stupefacenti", "309"),
        ("t.u. immigrazione", "286"), ("t.u. enti locali", "267"), ("T.U. bancario", "385"),
        ("t.u. pubblico impiego", "165"), ("t.u. imposte redditi", "917"), ("t. u. edilizia", "380"),
    ])
    def test_dotted_tu(self, nome, numero):
        assert _resolve_act(nome)["numero_atto"] == numero

    def test_dotted_acronyms_keep_their_meaning(self):
        assert _resolve_act("T.U.E.")["tipo_atto"] == "TUE"  # the treaty, not the testo unico edilizia
        assert _resolve_act("t.u.b.")["numero_atto"] == "385"

    @pytest.mark.parametrize("nome,numero", [
        ("codice della crisi e dell'insolvenza", "14"), ("Codice della Crisi d'Impresa", "14"),
        ("C. Crisi Impresa", "14"), ("cod. contratti pubblici", "36"), ("codice dei beni culturali", "42"),
        ("codice della proprieta' industriale", "30"), ("norme att. cod. proc. pen.", "271"),
        ("preleggi al codice civile", "262"),
    ])
    def test_codes(self, nome, numero):
        assert _resolve_act(nome)["numero_atto"] == numero

    def test_costituzione_italiana(self):
        assert _resolve_act("Costituzione italiana")["tipo_atto"] == "costituzione"

    @pytest.mark.parametrize("nome,data,numero", [
        ("Codice Rosso", "2019-07-19", "69"), ("Legge Capitali", "2024-03-05", "21"),
    ])
    def test_nicknames(self, nome, data, numero):
        assert _resolve_act(nome) == {"tipo_atto": "legge", "data": data, "numero_atto": numero}


def test_the_legge_sulle_locazioni_abitative_is_a_legge():
    from mcp_legal_it.lib.visualex.map import resolve_atto

    assert resolve_atto("legge sulle locazioni abitative") == {
        "tipo_atto": "legge", "data": "1998-12-09", "numero_atto": "431"}


class TestRegioDecretoLegislativo:
    @pytest.mark.parametrize("nome,data", [
        ("regio decreto legislativo 31 maggio 1946, n. 511", "1946-05-31"),
        ("r.d.lgs. 511/1946", "1946"), ("R.D.Lgs. 511/1946", "1946"), ("R.D.Lgs. n. 511 del 1946", "1946"),
    ])
    def test_the_type(self, nome, data):
        assert _resolve_act(nome) == {"tipo_atto": "regio decreto legislativo", "data": data, "numero_atto": "511"}

    def test_its_urn(self):
        norma = Norma(tipo_atto="regio decreto legislativo", data="1946-05-31", numero_atto="511")
        assert norma.url().endswith("urn:nir:stato:regio.decreto.legislativo:1946-05-31;511")

    def test_the_neighbouring_types_are_unchanged(self):
        assert _resolve_act("R.D.L. 1578/1933")["tipo_atto"] == "regio decreto legge"
        assert _resolve_act("r.d. 262/1942")["tipo_atto"] == "regio decreto"


class TestFontiNonCoperte:
    @pytest.mark.parametrize("nome,estremo", [
        ("Regolamento Emittenti", "11971"), ("Regolamento Emittenti Consob", "11971"),
        ("reg. Consob 11971/1999", "11971"), ("Regolamento OPC", "17221"), ("Regolamento Mercati", "20249"),
        ("CEDU", "848"), ("C.E.D.U.", "848"), ("Convenzione europea dei diritti dell'uomo", "848"),
        ("prot. addiz. CEDU", "848"), ("Primo Protocollo addizionale alla CEDU", "848"),
        ("Protocollo addizionale alla Convenzione europea dei diritti dell'uomo", "848"),
        ("Protocollo n. 1 CEDU", "848"), ("Prot. n. 7 CEDU", "n. 98"), ("Protocollo n. 4 CEDU", "n. 217"),
        ("Carta sociale europea", "n. 30"), ("Convenzione di Aarhus", "n. 108"),
        ("Patto internazionale sui diritti civili e politici", "n. 881"),
        ("Convenzione sui diritti del fanciullo", "n. 176"), ("CEDAW", "n. 132"),
        ("Convenzione MARPOL 73/78", "n. 662"),
    ])
    def test_declared_with_their_identity(self, nome, estremo):
        assert _resolve_act(nome) is None
        out = _unresolved_act_error(nome)
        assert out.startswith("**Errore**: fonte non coperta") and estremo in out, out
        assert "Forse intendevi" not in out

    def test_the_cedu_is_never_served_from_the_1955_law(self):
        out = _unresolved_act_error("CEDU")
        assert "rinumerato" in out and "4 agosto 1955, n. 848" in out

    @pytest.mark.asyncio
    async def test_cite_law_never_fetches_them(self, monkeypatch):
        from mcp_legal_it.core import norme
        from mcp_legal_it.tools import legal_citations as lc

        async def boom(*a, **k):
            raise AssertionError("an uncovered source is never fetched")

        monkeypatch.setattr(norme, "fetch_article", boom)
        for riferimento in ("art. 6 CEDU", "art. 1 Prot. n. 7 CEDU", "art. 65 Regolamento Emittenti"):
            assert "fonte non coperta" in await lc._cite_law_impl(riferimento)


class TestGate:
    @pytest.mark.parametrize("testo,articolo", [
        ("Si veda l'art. 6 della C.E.D.U. sul giusto processo.", "6"),
        ("Si veda l'art. 1 del prot. addiz. CEDU sulla proprietà.", "1"),
        ("Si veda l'art. 1 del Primo Protocollo addizionale alla CEDU.", "1"),
        ("Si veda l'art. 2 del Protocollo n. 7 CEDU.", "2"),
        ("Si veda l'art. 65 del Regolamento Emittenti.", "65"),
        ("Si veda l'art. 65 del reg. Consob emittenti.", "65"),
        ("Si veda l'art. 5 del Regolamento OPC.", "5"),
        ("Si veda l'art. 3 del Regolamento Mercati.", "3"),
        ("Si veda l'art. 3 del Regolamento Mercati Consob sulle sedi.", "3"),
        ("Si veda l'art. 3 del regolamento mercati n. 20249 sulle sedi.", "3"),
        ("Si veda l'art. 24 della Carta sociale europea.", "24"),
        ("Si veda l'art. 9 della Convenzione di Aarhus.", "9"),
        ("Si veda l'art. 14 del Patto internazionale sui diritti civili e politici.", "14"),
        ("Si veda l'art. 3 della Convenzione sui diritti del fanciullo.", "3"),
    ])
    def test_flagged_as_out_of_coverage(self, testo, articolo):
        assert [(n.atto, n.articolo) for n in norme_nel_testo(testo)] == [(None, articolo)]

    @pytest.mark.parametrize("testo", [
        "L'art. 3 del regolamento condominiale vieta gli animali.",
        "L'art. 2 del protocollo d'intesa tra le parti prevede un tavolo tecnico.",
        "L'art. 4 del protocollo n. 3 del verbale di assemblea.",
        "L'art. 7 della carta sociale dell'associazione.",
        "L'art. 1 del regolamento interno del comitato.",
        "L'art. 4 del regolamento mercati rionali del Comune fissa gli orari.",
        "L'art. 2 del regolamento mercati comunali disciplina i posteggi.",
    ])
    def test_not_law_stays_out(self, testo):
        assert norme_nel_testo(testo) == []
