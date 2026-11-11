"""Sigle and nicknames of testi unici and laws: the second alias pass (G-440).

Each identity was checked on Normattiva on 11 November 2026 (the page's heading for type, date
and number; the act's title for its subject; the act calling itself «testo unico» where the
alias says so). Names more than one act answers are refused on purpose (``NOMI_AMBIGUI``):
the fiscal reform's new testi unici (IVA, d.lgs. 10/2026; registro, d.lgs. 123/2025) make
«TUIVA» and «T.U. registro» mean two acts each.
"""

import pytest

import mcp_legal_it.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from mcp_legal_it.core.citazioni import identita_atto, norme_nel_testo
from mcp_legal_it.core.riferimenti import _parse_reference, _resolve_act, _unresolved_act_error
from mcp_legal_it.lib.visualex.models import Norma

DPR = "decreto del presidente della repubblica"
DLGS = "decreto legislativo"


@pytest.mark.parametrize("nome, tipo, data, numero", [
    ("TUED", DPR, "2001-06-06", "380"), ("T.U.E.D.", DPR, "2001-06-06", "380"), ("TUEd", DPR, "2001-06-06", "380"),
    ("TUEs", DPR, "2001-06-08", "327"), ("T.U.Es.", DPR, "2001-06-08", "327"), ("TUEspr", DPR, "2001-06-08", "327"),
    ("TUSG", DPR, "2002-05-30", "115"), ("T.U.S.G.", DPR, "2002-05-30", "115"),
    ("T.U. spese di giustizia", DPR, "2002-05-30", "115"), ("TU spese di giustizia", DPR, "2002-05-30", "115"),
    ("testo unico delle spese di giustizia", DPR, "2002-05-30", "115"),
    ("TUDA", DPR, "2000-12-28", "445"), ("T.U.D.A.", DPR, "2000-12-28", "445"),
    ("T.U. documentazione amministrativa", DPR, "2000-12-28", "445"),
    ("T.U. accise", DLGS, "1995-10-26", "504"),
    ("TULD", DPR, "1973-01-23", "43"), ("T.U.L.D.", DPR, "1973-01-23", "43"),
    ("TUSMA", DLGS, "2021-11-08", "208"), ("TUSMAR", DLGS, "2005-07-31", "177"),
    ("TUOM", DPR, "2010-03-15", "90"), ("T.U.O.M.", DPR, "2010-03-15", "90"),
    ("TUIMM", DLGS, "1998-07-25", "286"), ("TUStup", DPR, "1990-10-09", "309"),
    ("T.U. ambiente", DLGS, "2006-04-03", "152"), ("TU ambiente", DLGS, "2006-04-03", "152"),
    ("TUAmb", DLGS, "2006-04-03", "152"),
    ("St. lav.", "legge", "1970-05-20", "300"), ("L.F.", "regio decreto", "1942-03-16", "267"),
    ("l. proc. amm.", "legge", "1990-08-07", "241"),
    ("legge Madia", "legge", "2015-08-07", "124"),
    ("legge Balduzzi", "decreto legge", "2012-09-13", "158"),
    ("decreto whistleblowing", DLGS, "2023-03-10", "24"),
    ("decreto dignità", "decreto legge", "2018-07-12", "87"),
    ("decreto Salva Casa", "decreto legge", "2024-05-29", "69"),
    ("decreto salva-casa", "decreto legge", "2024-05-29", "69"),
])
def test_the_aliases(nome, tipo, data, numero):
    assert _resolve_act(nome) == {"tipo_atto": tipo, "data": data, "numero_atto": numero}


@pytest.mark.parametrize("nome, tipo, numero", [
    ("cod. ass.", "codice delle assicurazioni private", "209"),
    ("codice Urbani", "codice dei beni culturali e del paesaggio", "42"),
    ("CBCP", "codice dei beni culturali e del paesaggio", "42"),
    ("cod. app.", "codice dei contratti pubblici", "36"),
])
def test_the_codes(nome, tipo, numero):
    info = _resolve_act(nome)
    assert info["tipo_atto"] == tipo and info["numero_atto"] == numero


@pytest.mark.parametrize("nome", ["cod. priv.", "c.priv.", "c. priv."])
def test_the_codice_privacy(nome):
    assert _resolve_act(nome) == _resolve_act("codice privacy")


class TestArt36BisTued:
    def test_cite_law_reads_the_reference(self):
        articolo, atto = _parse_reference("art. 36-bis TUED")
        info = _resolve_act(atto)
        url = Norma(tipo_atto=info["tipo_atto"], data=info["data"], numero_atto=info["numero_atto"]).url(
            article=articolo)
        assert url.endswith("decreto.del.presidente.della.repubblica:2001-06-06;380~art36bis")

    def test_the_gate_reads_it(self):
        trovate = norme_nel_testo("La sanatoria segue l'art. 36-bis TUED, introdotto nel 2024.")
        assert [(n.atto, n.articolo) for n in trovate] == [
            (identita_atto({"tipo_atto": DPR, "data": "2001-06-06", "numero_atto": "380"}), "36bis")]


def test_tue_stays_the_treaty():
    assert _resolve_act("TUE")["tipo_atto"] == "TUE"
    assert _resolve_act("T.U.E.")["tipo_atto"] == "TUE"


@pytest.mark.parametrize("nome", [
    "TUS", "T.U.S.", "decreto trasparenza", "decreto Semplificazioni", "riforma Cartabia",
    "TUIVA", "TU IVA", "T.U. registro", "testo unico registro", "T.U. rinnovabili", "testo unico rinnovabili",
    "TUFER", "decreto FER", "decreto CER", "S.L.", "TUI", "CGC", "L.P.A.",
])
def test_ambiguous_names_are_refused_on_purpose(nome):
    assert _resolve_act(nome) is None
    out = _unresolved_act_error(nome)
    assert out.startswith("**Errore**: nome ambiguo") and f"«{nome}»" in out, out
    assert "Forse intendevi" not in out


def test_the_ambiguous_fiscal_names_say_which_acts():
    assert "d.lgs. 19 gennaio 2026, n. 10" in _unresolved_act_error("TUIVA")
    assert "d.lgs. 1 agosto 2025, n. 123" in _unresolved_act_error("T.U. registro")


def test_an_unknown_sigla_stays_unresolved():
    # «TUOG» names no testo unico that could be checked: unresolved, not guessed.
    assert _resolve_act("TUOG") is None
