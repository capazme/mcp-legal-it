"""The Stop-hook citation gate must nag only for genuinely unverified norms.

Its predecessor was an LLM prompt hook replaced precisely because it over-fired;
this deterministic version inherited one of the same false positives. `cost` was
matched as a bare substring, so the ordinary Italian words "costi", "costante"
and "costruito" all read as a citation of the Costituzione, and any `art. N`
within the surrounding window tripped the gate. A reviewer running the plugin
reported it firing on plain examples written for something else.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "plugin" / "hooks" / "citation-gate.py"

SILENT = 0
NAGS = 2


def run_gate(tmp_path: Path, assistant_text: str, cite_law_refs: tuple[str, ...] = ()) -> int:
    """Drive the hook over a synthetic transcript, return its exit code."""
    lines = []
    for ref in cite_law_refs:
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "cite_law", "input": {"reference": ref}}
            ]},
        }))
    lines.append(json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": assistant_text}]},
    }))

    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("\n".join(lines), encoding="utf-8")

    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"transcript_path": str(transcript)}),
        capture_output=True,
        text=True,
    ).returncode


@pytest.mark.parametrize("text", [
    "L'art. 12 riduce i costi di gestione del servizio.",
    "Vedi art. 3 del file di configurazione costruito a mano.",
    "L'art. 7 definisce la costante di normalizzazione applicata.",
    "Il punto 4 dell'art. 9 incide sul costo complessivo dell'opera.",
])
def test_ordinary_words_starting_with_cost_do_not_trip_the_gate(tmp_path, text):
    assert run_gate(tmp_path, text) == SILENT, f"falso positivo su: {text!r}"


@pytest.mark.parametrize("text", [
    "L'art. 15 Cost. tutela la liberta' di corrispondenza.",
    "Il principio discende dall'art. 41 della Costituzione.",
    "Ai sensi dell'art. 2043 c.c. il fatto illecito obbliga al risarcimento.",
    "L'art. 640 c.p. punisce la truffa.",
])
def test_real_uncovered_citations_still_trip_the_gate(tmp_path, text):
    assert run_gate(tmp_path, text) == NAGS, f"mancata segnalazione su: {text!r}"


@pytest.mark.parametrize("text", [
    # Reproduces the gate firing on this very project's writeup: the norm was
    # inside a fenced block showing what a tool returns, not asserted as law.
    "Ecco l'output del tool:\n\n```\ninteressi_legali(1000, ...)\n  -> \"tassi legali: "
    "copre fino al 31/12/2026 (DM MEF, art. 1284 c.c.)\"\n```\n\nCome vedi funziona.",
    "Il campo vale `art. 2043 c.c.` nella fixture di test.",
    "```python\nRIFERIMENTO = \"art. 640 c.p.\"  # stringa di esempio\n```",
])
def test_norms_quoted_inside_code_are_not_assertions(tmp_path, text):
    """Fenced blocks and inline code quote things; they do not claim them.

    The gate exists to catch a norm stated from memory. A sample payload, a
    fixture value or a snippet of documentation is neither, and nagging about
    them is what made a reviewer call the whole mechanism too eager.
    """
    assert run_gate(tmp_path, text) == SILENT, f"falso positivo su: {text[:60]!r}"


def test_a_norm_outside_the_block_is_still_caught(tmp_path):
    """Stripping code must not become a way to smuggle an unverified citation."""
    text = "```\nesempio = 1\n```\n\nNel merito si applica l'art. 2043 c.c."
    assert run_gate(tmp_path, text) == NAGS


@pytest.mark.parametrize("text", [
    # `art\.?\s*\d` wanted the literal "art" then a digit, so the spelled-out
    # form — the one lawyers write half the time — walked straight through.
    "Ai sensi dell'articolo 2043 del codice civile il fatto illecito obbliga al risarcimento.",
    "Gli articoli 536 e 544 c.c. fissano le quote di riserva.",
    "Gli artt. 2941 e 2946 c.c. disciplinano la prescrizione.",
    "Il tasso e' quello dell'art 1284 c.c. senza punto abbreviativo.",
    "L'articolo 5 del Codice del consumo impone obblighi informativi.",
    "L'art. 186 del Codice della strada punisce la guida in stato di ebbrezza.",
    "L'art. 3 del Codice della crisi definisce gli assetti adeguati.",
])
def test_spelled_out_and_plural_article_forms_are_caught(tmp_path, text):
    assert run_gate(tmp_path, text) == NAGS, f"citazione mancata: {text[:60]!r}"


@pytest.mark.parametrize("text", [
    # Widening recall must not start firing on articles of things that are not
    # law: a contract, a set of by-laws, a tender notice.
    "L'art. 5 del contratto di locazione prevede il rinnovo tacito.",
    "Come da art. 12 dello statuto condominiale approvato in assemblea.",
    "Vedi l'art. 3 delle condizioni generali allegate alla polizza.",
    "L'art. 7 del disciplinare di gara richiede la cauzione.",
    # "codice" alone would have been tempting and wrong: these are the codes
    # this project handles as data, not as sources of law.
    "Ho generato il codice fiscale del cliente, vedi art. 3 del mandato.",
    "Il codice tributo indicato nell'art. 4 del modello F24 allegato.",
    "Cerca il codice ATECO all'art. 2 della visura camerale.",
])
def test_articles_of_non_legal_documents_stay_silent(tmp_path, text):
    assert run_gate(tmp_path, text) == SILENT, f"falso positivo su: {text[:60]!r}"


def test_dedup_understands_the_spelled_out_form_too(tmp_path):
    """A cite_law() written out in full still covers the citation in the prose."""
    text = "Ai sensi dell'articolo 2043 del codice civile si risponde del danno."
    assert run_gate(tmp_path, text, cite_law_refs=("articolo 2043 codice civile",)) == SILENT


def test_citation_already_verified_in_session_is_not_re_nagged(tmp_path):
    text = "Ai sensi dell'art. 2043 c.c. il fatto illecito obbliga al risarcimento."
    assert run_gate(tmp_path, text, cite_law_refs=("art. 2043 c.c.",)) == SILENT
