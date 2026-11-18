"""Sigle that follow the date (LI-086): the fiscal testi unici and the codice dei contratti pubblici.

Until a new testo unico applies, its sigla names the old act with a one-line notice («dal
1° gennaio 2027 si applica il d.lgs. …»); from that day it names the new testo unico, the
annex of its decree. The date is the caller's (``resolve_atto(name, data=…)``) or today,
pinned here with ``LEGAL_TODAY`` on both sides of the switch. Every date was read on
Normattiva (see the comments in ``map.SIGLE_DATATE``). No network here.
"""

import json

import pytest

from mcp_legal_it.core import norme
from mcp_legal_it.core.riferimenti import _resolve_act, _unresolved_act_error
from mcp_legal_it.lib.visualex.map import SIGLE_DATATE, nome_ambiguo, resolve_atto
from mcp_legal_it.tools import italgiure as ig
from mcp_legal_it.tools import legal_citations as lc

DPR = "decreto del presidente della repubblica"
DLGS = "decreto legislativo"

PRIMA, DAL = "2026-12-31", "2027-01-01"

_TUIR_VECCHIO = {"tipo_atto": DPR, "data": "1986-12-22", "numero_atto": "917"}
_TUIR_NUOVO = {"tipo_atto": DLGS, "data": "2026-06-19", "numero_atto": "117", "allegato": "1"}
_REGISTRO_VECCHIO = {"tipo_atto": DPR, "data": "1986-04-26", "numero_atto": "131"}
_REGISTRO_NUOVO = {"tipo_atto": DLGS, "data": "2025-08-01", "numero_atto": "123", "allegato": "1"}
_IVA_VECCHIO = {"tipo_atto": DPR, "data": "1972-10-26", "numero_atto": "633"}
_IVA_NUOVO = {"tipo_atto": DLGS, "data": "2026-01-19", "numero_atto": "10", "allegato": "1"}
_SUCCESSIONI = {"tipo_atto": DLGS, "data": "1990-10-31", "numero_atto": "346"}
_TUGT = {"tipo_atto": DLGS, "data": "2024-11-14", "numero_atto": "175", "allegato": "1"}

_AVVISO_TUIR = "dal 1° gennaio 2027 si applica il d.lgs. 19 giugno 2026, n. 117 (testo unico delle imposte sui redditi)"
_AVVISO_REGISTRO = ("dal 1° gennaio 2027 si applica il d.lgs. 1° agosto 2025, n. 123 (testo unico dell'imposta "
                    "di registro e degli altri tributi indiretti)")
_AVVISO_IVA = ("dal 1° gennaio 2027 si applica il d.lgs. 19 gennaio 2026, n. 10 (testo unico dell'imposta sul "
               "valore aggiunto)")

# (names, act before the switch, act from it, the notice before it)
_PASSAGGI = [
    (("TUIR", "t.u.i.r.", "testo unico delle imposte sui redditi", "tu imposte redditi"),
     _TUIR_VECCHIO, _TUIR_NUOVO, _AVVISO_TUIR),
    (("TUR", "T.U. registro", "testo unico registro", "testo unico dell'imposta di registro"),
     _REGISTRO_VECCHIO, _REGISTRO_NUOVO, _AVVISO_REGISTRO),
    (("TUIVA", "TU IVA", "t.u. IVA", "T.U.I.V.A.", "testo unico iva"), _IVA_VECCHIO, _IVA_NUOVO, _AVVISO_IVA),
]
_CASI = [(nome, prima, dopo, avviso) for nomi, prima, dopo, avviso in _PASSAGGI for nome in nomi]


def _senza_avviso(atto: dict) -> dict:
    return {k: v for k, v in atto.items() if k != "avviso"}


class TestPassaggioAllaData:
    @pytest.mark.parametrize("nome, vecchio, nuovo, avviso", _CASI)
    def test_the_day_before_the_old_act_with_the_notice(self, nome, vecchio, nuovo, avviso, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", PRIMA)
        atto = _resolve_act(nome)
        assert _senza_avviso(atto) == vecchio
        assert atto["avviso"] == avviso

    @pytest.mark.parametrize("nome, vecchio, nuovo, avviso", _CASI)
    def test_the_day_of_the_switch_the_new_testo_unico(self, nome, vecchio, nuovo, avviso, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", DAL)
        assert _resolve_act(nome) == nuovo

    @pytest.mark.parametrize("nome, vecchio, nuovo, avviso", _CASI)
    def test_an_explicit_date_wins_over_today(self, nome, vecchio, nuovo, avviso, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", DAL)
        assert _senza_avviso(resolve_atto(nome, data=PRIMA)) == vecchio
        assert _resolve_act(nome, data="2030-05-05") == nuovo
        monkeypatch.setenv("LEGAL_TODAY", PRIMA)
        assert resolve_atto(nome, data=DAL) == nuovo

    def test_the_new_testo_unico_is_read_in_its_annex(self, monkeypatch):
        from mcp_legal_it.core.citazioni import identita_atto

        monkeypatch.setenv("LEGAL_TODAY", DAL)
        assert identita_atto(_resolve_act("TUIR")).endswith("decreto.legislativo:2026;117:1")

    def test_the_former_ambiguous_sigle_are_not_ambiguous_any_more(self, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", PRIMA)
        for nome in ("TUIVA", "TU IVA", "T.U. registro", "testo unico registro"):
            assert nome_ambiguo(nome) is None

    def test_every_dated_sigla_is_a_known_name(self):
        from mcp_legal_it.lib.visualex.map import known_act_names

        assert set(SIGLE_DATATE) <= set(known_act_names())


class TestSuccessioniEGiustiziaTributaria:
    def test_tu_successioni_carries_the_registro_notice_then_stays_on_its_act(self, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", PRIMA)
        atto = _resolve_act("TU successioni")
        assert _senza_avviso(atto) == _SUCCESSIONI and atto["avviso"] == _AVVISO_REGISTRO
        # From 2027 the sigla still names d.lgs. 346/1990, which cite_law shows as repealed: it is
        # not the new testo unico's sigla, and the article numbers differ.
        monkeypatch.setenv("LEGAL_TODAY", DAL)
        assert _resolve_act("testo unico sulle successioni e donazioni") == _SUCCESSIONI

    @pytest.mark.parametrize("nome", ["tugt", "T.U.G.T.", "testo unico della giustizia tributaria"])
    def test_tugt_keeps_its_act_and_says_when_it_applies(self, nome, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", PRIMA)
        atto = _resolve_act(nome)
        assert _senza_avviso(atto) == _TUGT
        assert atto["avviso"] == (
            "il testo unico della giustizia tributaria si applica dal 1° gennaio 2027 (art. 131, comma 1, "
            "come modificato dall'art. 4, comma 3, d.l. 200/2025); fino ad allora valgono le disposizioni "
            "previgenti")
        monkeypatch.setenv("LEGAL_TODAY", DAL)
        assert _resolve_act(nome) == _TUGT


class TestTua:
    @pytest.mark.parametrize("nome", ["TUA", "tua", "T.U.A."])
    def test_tua_stays_refused_and_names_both_acts(self, nome):
        assert _resolve_act(nome) is None
        out = _unresolved_act_error(nome)
        assert out.startswith("**Errore**: nome ambiguo")
        assert "d.lgs. 3 aprile 2006, n. 152" in out and "d.lgs. 26 ottobre 1995, n. 504" in out

    @pytest.mark.parametrize("nome", ["codice dell'ambiente", "testo unico ambientale", "d.lgs. 152/2006",
                                      "TU ambiente"])
    def test_the_codice_dell_ambiente_still_resolves(self, nome):
        atto = _resolve_act(nome)
        assert atto["tipo_atto"] == DLGS and atto["numero_atto"] == "152"

    def test_the_testo_unico_accise_still_resolves(self):
        assert _resolve_act("testo unico accise")["numero_atto"] == "504"


_CODICE_2023 = {"tipo_atto": "codice dei contratti pubblici", "data": "2023-03-31", "numero_atto": "36"}
_DLGS_163 = {"tipo_atto": DLGS, "data": "2006-04-12", "numero_atto": "163"}
_DLGS_50 = {"tipo_atto": DLGS, "data": "2016-04-18", "numero_atto": "50"}


class TestCodiceDeiContrattiPubblici:
    @pytest.mark.parametrize("nome", ["cod. app.", "codice dei contratti pubblici", "codice degli appalti",
                                      "CCP", "codice appalti"])
    @pytest.mark.parametrize("data, atto", [
        ("2006-07-01", _DLGS_163), ("2016-04-18", _DLGS_163),
        ("2016-04-19", _DLGS_50), ("2023-06-30", _DLGS_50),
        ("2023-07-01", _CODICE_2023), ("2026-11-18", _CODICE_2023),
    ])
    def test_with_a_date_the_code_in_force_that_day(self, nome, data, atto):
        assert _resolve_act(nome, data=data) == atto

    def test_without_a_date_nothing_changes(self, monkeypatch):
        # The switch lies in the past: «today» would silently move older citations (LI-086).
        monkeypatch.setenv("LEGAL_TODAY", "2026-11-18")
        assert _resolve_act("codice degli appalti") == _DLGS_163
        assert _resolve_act("codice dei contratti pubblici") == _CODICE_2023
        assert _resolve_act("cod. app.") is None
        assert _unresolved_act_error("cod. app.").startswith("**Errore**: nome ambiguo")

    def test_before_the_first_code_no_act(self):
        assert _resolve_act("codice degli appalti", data="2006-06-30") is None
        out = _unresolved_act_error("codice degli appalti", data="2006-06-30")
        assert out == ("**Errore**: il 30/06/2006 nessun atto rispondeva a «codice degli appalti»: il primo, "
                       "d.lgs. 12 aprile 2006, n. 163, si applica dal 1° luglio 2006.")

    def test_the_explicit_names_of_one_code_are_not_dated(self):
        assert _resolve_act("nuovo codice appalti", data="2010-01-01")["numero_atto"] == "36"
        assert _resolve_act("codice appalti 2006", data="2024-01-01")["numero_atto"] == "163"


# ---------------------------------------------------------------------------
# The notice travels with the act to every tool that shares the resolver
# ---------------------------------------------------------------------------

_TESTO = {"text": "Art. 1.\n\nTesto dell'articolo.", "url": "https://example.invalid/art1", "source": ""}


@pytest.fixture
def senza_rete(monkeypatch):
    """Every fetch answers with a stub article: the tests read what the tools add around it."""
    async def fetch(nv, **_):
        return dict(_TESTO)

    monkeypatch.setattr(lc, "fetch_norma", fetch)
    monkeypatch.setattr(norme, "fetch_norma", fetch)
    monkeypatch.setenv("LEGAL_TODAY", PRIMA)


class TestAvvisoNeiTool:
    @pytest.mark.asyncio
    async def test_cite_law_markdown_says_it_first(self, senza_rete):
        out = await lc._cite_law_impl("art. 1 TUIR")
        assert out.startswith(f"**Attenzione**: {_AVVISO_TUIR}.")
        assert "Testo dell'articolo." in out

    @pytest.mark.asyncio
    async def test_cite_law_json_has_it_first_in_avvisi(self, senza_rete):
        data = json.loads(await lc._cite_law_impl("art. 1 TUIVA", formato="json"))
        assert data["avvisi"][0] == _AVVISO_IVA
        assert data["atto"]["numero_atto"] == "633"

    @pytest.mark.asyncio
    async def test_no_notice_from_the_day_of_the_switch(self, senza_rete, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", DAL)
        out = await lc._cite_law_impl("art. 1 TUIR")
        assert "si applica il d.lgs." not in out

    @pytest.mark.asyncio
    async def test_an_act_cited_by_number_carries_no_notice(self, senza_rete):
        out = await lc._cite_law_impl("art. 1 d.P.R. 917/1986")
        assert "**Attenzione**: dal 1° gennaio 2027" not in out

    @pytest.mark.asyncio
    async def test_verifica_citazioni_adds_it_to_the_note(self, senza_rete):
        verdetto, nota = await lc._verifica_norma("art. 1 T.U. registro")
        assert verdetto == "verificata"
        assert nota.endswith(f"Attenzione: {_AVVISO_REGISTRO}.")

    @pytest.mark.asyncio
    async def test_fetch_full_act_says_it_as_an_avviso(self, senza_rete, monkeypatch):
        async def full(norma, da):
            return {"text": "Art. 1.\n\n" + "testo " * 30, "title": "TUIR", "url": "https://example.invalid"}

        monkeypatch.setattr(lc, "_full_act_text", full)
        out = await lc._fetch_full_act_impl("TUIR")
        # «**Avviso**:», which the citation gate skips when it reads a window.
        assert f"**Avviso**: {_AVVISO_TUIR}" in out

    @pytest.mark.asyncio
    async def test_the_library_api_has_it_in_avvisi(self, senza_rete):
        from mcp_legal_it import api

        r = await api.testo_articolo("art. 1 TUIR", canale="html")
        assert r.avvisi and r.avvisi[0] == _AVVISO_TUIR

    def test_giurisprudenza_su_norma_reads_it(self, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", PRIMA)
        assert ig._avviso_sigla("art. 2 TUIR") == _AVVISO_TUIR
        assert ig._avviso_sigla("art. 2043 c.c.") is None

    def test_the_alias_catalogue_gives_the_act_of_today(self, monkeypatch):
        from mcp_legal_it import api

        monkeypatch.setenv("LEGAL_TODAY", PRIMA)
        assert api.catalogo_alias().presets["tuir"] == {"act_type": DPR, "act_number": "917", "date": "1986-12-22"}
        monkeypatch.setenv("LEGAL_TODAY", DAL)
        assert api.catalogo_alias().presets["tuir"] == {"act_type": DLGS, "act_number": "117", "date": "2026-06-19"}
