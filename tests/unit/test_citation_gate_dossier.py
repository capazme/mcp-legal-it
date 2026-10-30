"""The citation gate and VisuaLex's dossier (D8): what the dossier verified is read.

VisuaLex's ``omnilex_crea_dossier`` takes up to 50 references and 10 decisions in plain
words, verifies each once against the sources, and answers ``{dossier, entrate: {norme,
sentenze, note}, non_entrate: [{riga, motivo}]}`` (optional ``note_non_entrate``,
``errore``, and from 1.10.7 ``in_sospeso`` with every ``errore``). The answer carries no
norm text and does not echo the lines entered: the gate credits the lines given less
``non_entrate[].riga`` (byte-identical to the input line), less every reference when
«norme» is in ``in_sospeso`` and every decision when «sentenze» is; an ``errore`` without
``in_sospeso`` (a VisuaLex before 1.10.7) credits nothing. Every case runs with both
readers (the server's and the hook's stdlib fallback): they must give the same verdict.
"""

from __future__ import annotations

import json

import pytest

from tests.unit.test_citation_gate import NAGS, SILENT, isolated_hook, run, session  # noqa: F401
from tests.unit.test_citation_gate_commi import parte

NORMA = "art. 2043 c.c."
COMMA = "art. 1, comma 773, L. 296/2006"
SENTENZA = "Cass. civ., sez. III, n. 12345/2024"
ALTRA_SENTENZA = "Cass. civ., sez. lav., n. 6789/2023"

FRASE_NORMA = "L'art. 2043 c.c. regola il fatto illecito."
FRASE_COMMA = "L'art. 1, comma 773, L. 296/2006 ridetermina l'aliquota."
FRASE_SENTENZA = "Lo conferma Cass. civ., sez. III, n. 12345/2024."
FRASE_ALTRA_SENTENZA = "Lo conferma anche Cass. civ., sez. lav., n. 6789/2023."

INGRESSO = {"titolo": "Responsabilità civile", "riferimenti": [NORMA, COMMA], "sentenze": [SENTENZA, ALTRA_SENTENZA]}


def risposta(non_entrate=(), **altro) -> str:
    """A dossier answer in VisuaLex's shape (no norm text, no echo of the lines entered)."""
    entrate = {"norme": 2 - sum(1 for e in non_entrate if e["riga"] in INGRESSO["riferimenti"]),
               "sentenze": 2 - sum(1 for e in non_entrate if e["riga"] in INGRESSO["sentenze"]),
               "note": 0}
    body = {"dossier": {"id": "d-7f3a", "titolo": INGRESSO["titolo"]}, "entrate": entrate,
            "non_entrate": list(non_entrate), **altro}
    return json.dumps(body, ensure_ascii=False)


def _gate(t, fallback, hook):
    payload = {"transcript_path": str(t.write()), "hook_event_name": "Stop"}
    if fallback:
        return run(payload, python_args=("-I", "-S"), hook=hook)
    return run(payload)


@pytest.fixture(params=[False, True], ids=["server", "fallback"])
def lettore(request, isolated_hook):  # noqa: F811
    return request.param, isolated_hook


def dossier(tmp_path, result, *, nome="dossier", tool_input=None, prefix="mcp__visualex__", **kw):
    return session(tmp_path, nome).prompt().call("omnilex_crea_dossier", tool_input or INGRESSO, result,
                                                 prefix=prefix, **kw)


def verdetto(tmp_path, lettore, result, frase, **kw) -> int:
    nome = f"d{abs(hash((result, frase, str(kw)))) % 10**8}"
    return _gate(dossier(tmp_path, result, nome=nome, **kw).say(frase), *lettore).returncode


@pytest.mark.parametrize("frase", [FRASE_NORMA, FRASE_COMMA, FRASE_SENTENZA, FRASE_ALTRA_SENTENZA])
def test_a_full_dossier_credits_every_line(tmp_path, lettore, frase):
    assert verdetto(tmp_path, lettore, risposta(), frase) == SILENT


def test_a_dossier_credits_only_its_lines(tmp_path, lettore):
    assert verdetto(tmp_path, lettore, risposta(), "L'art. 2051 c.c. regola la custodia.") == NAGS
    assert verdetto(tmp_path, lettore, risposta(), "Lo dice Cass. civ. n. 1/2020.") == NAGS


def test_a_line_not_entered_is_not_credited(tmp_path, lettore):
    fuori = risposta([{"riga": NORMA, "motivo": "non verificabile"},
                      {"riga": SENTENZA, "motivo": "sentenza non trovata"}])
    assert verdetto(tmp_path, lettore, fuori, FRASE_NORMA) == NAGS
    assert verdetto(tmp_path, lettore, fuori, FRASE_SENTENZA) == NAGS
    assert verdetto(tmp_path, lettore, fuori, FRASE_COMMA) == SILENT
    assert verdetto(tmp_path, lettore, fuori, FRASE_ALTRA_SENTENZA) == SILENT


def test_the_line_not_entered_is_compared_byte_for_byte(tmp_path, lettore):
    # «art. 2043 c.c. » is not the line given: «art. 2043 c.c.» went in.
    altra = risposta([{"riga": NORMA + " ", "motivo": "non verificabile"}])
    assert verdetto(tmp_path, lettore, altra, FRASE_NORMA) == SILENT


def test_an_error_with_norms_pending_credits_the_decisions_only(tmp_path, lettore):
    errore = risposta([{"riga": ALTRA_SENTENZA, "motivo": "passo rifiutato"}],
                      errore="timeout sul passo delle norme", in_sospeso=["norme"])
    assert verdetto(tmp_path, lettore, errore, FRASE_NORMA) == NAGS
    assert verdetto(tmp_path, lettore, errore, FRASE_COMMA) == NAGS
    assert verdetto(tmp_path, lettore, errore, FRASE_SENTENZA) == SILENT
    assert verdetto(tmp_path, lettore, errore, FRASE_ALTRA_SENTENZA) == NAGS  # listed in non_entrate


def test_an_error_with_decisions_pending_credits_the_norms_only(tmp_path, lettore):
    errore = risposta(errore="timeout sul passo delle sentenze", in_sospeso=["sentenze"])
    assert verdetto(tmp_path, lettore, errore, FRASE_NORMA) == SILENT
    assert verdetto(tmp_path, lettore, errore, FRASE_SENTENZA) == NAGS


def test_an_error_with_nothing_pending_credits_the_lines_entered(tmp_path, lettore):
    errore = risposta([{"riga": NORMA, "motivo": "passo rifiutato"}], errore="nota non salvata", in_sospeso=[])
    assert verdetto(tmp_path, lettore, errore, FRASE_NORMA) == NAGS
    assert verdetto(tmp_path, lettore, errore, FRASE_COMMA) == SILENT
    assert verdetto(tmp_path, lettore, errore, FRASE_SENTENZA) == SILENT


@pytest.mark.parametrize("frase", [FRASE_NORMA, FRASE_COMMA, FRASE_SENTENZA])
def test_an_error_without_in_sospeso_credits_nothing(tmp_path, lettore, frase):
    # A VisuaLex before 1.10.7: a step that timed out does not list its rows.
    assert verdetto(tmp_path, lettore, risposta(errore="timeout"), frase) == NAGS


@pytest.mark.parametrize("prefix", ["mcp__visualex__", "mcp__claude_ai_VisuaLex__", ""],
                         ids=["visualex", "other-connector", "bare"])
def test_the_dossier_tool_is_known_by_any_connector_prefix(tmp_path, lettore, prefix):
    assert verdetto(tmp_path, lettore, risposta(), FRASE_NORMA, prefix=prefix) == SILENT


@pytest.mark.parametrize("nome, prefix", [
    ("omnilex_aggiungi_nota_dossier", "mcp__visualex__"),  # a note is no verified reference
    ("omnilex_crea_dossier", "altro__"),  # not an MCP tool
])
def test_other_tools_credit_nothing(tmp_path, lettore, nome, prefix):
    t = session(tmp_path).prompt().call(nome, INGRESSO, risposta(), prefix=prefix).say(FRASE_NORMA)
    assert _gate(t, *lettore).returncode == NAGS


@pytest.mark.parametrize("result, is_error", [
    (risposta(), True),
    ("Errore: VisuaLex non raggiungibile", False),
    (json.dumps({"dossier": {"id": "d-1"}}), False),  # no non_entrate: not the dossier's answer
])
def test_a_failed_or_unknown_answer_credits_nothing(tmp_path, lettore, result, is_error):
    assert verdetto(tmp_path, lettore, result, FRASE_NORMA, is_error=is_error) == NAGS


def test_a_single_string_of_lines_is_read_line_by_line(tmp_path, lettore):
    ingresso = {"riferimenti": f"{NORMA}\n{COMMA}", "sentenze": SENTENZA}
    assert verdetto(tmp_path, lettore, risposta(), FRASE_NORMA, tool_input=ingresso) == SILENT
    assert verdetto(tmp_path, lettore, risposta(), FRASE_SENTENZA, tool_input=ingresso) == SILENT


def test_a_dossier_never_reads_an_article_whole(tmp_path, lettore):
    # VisuaLex verifies the reference, and says nothing of the commi of an article Normattiva
    # splits: after a part read, a comma outside it is still asked for.
    t = (session(tmp_path).prompt()
         .cite_law("art. 1 L. 296/2006", parte("1", "100", "1", comma=False))
         .call("omnilex_crea_dossier", INGRESSO, risposta(), prefix="mcp__visualex__")
         .say(FRASE_COMMA))
    done = _gate(t, *lettore)
    assert done.returncode == NAGS and "cite_law con il comma 773" in done.stderr


def test_the_server_says_not_to_verify_the_references_of_a_dossier_first():
    from mcp_legal_it.server import _STOCK_INSTRUCTIONS

    riga = "Se crei un dossier con VisuaLex, non verificare prima i riferimenti con questi strumenti."
    assert riga in _STOCK_INSTRUCTIONS.splitlines()
