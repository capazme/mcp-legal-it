"""The Stop/SubagentStop citation gate: every bypass the 3.0 audit found is closed.

The gate stops an answer that cites a norm or a decision the session has not
read with a tool (Legal Grounding Protocol). It is advisory and fails open, so
it must also stay silent where the citation was read, where the "citation" is
not law (a contract's article, "atto di costituzione") and where code quotes
a norm instead of asserting it.

All transcripts here are synthetic: they reproduce the shape of Claude Code's
JSONL records (prompt, assistant text and tool_use, tool_result), never the
content of a real session.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "plugin" / "hooks" / "citation-gate.py"
HOOKS_JSON = HOOK.with_name("hooks.json")

SILENT = 0
NAGS = 2

_FONTE_CC = "**Fonte**: Normattiva — https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262:2~art"


class Transcript:
    """A synthetic session transcript, written as Claude Code writes its JSONL."""

    def __init__(self, path: Path):
        self.path = path
        self.lines: list[dict] = []
        self._n = 0

    def prompt(self, text: str = "Domanda dell'utente.") -> "Transcript":
        self.lines.append({"type": "user", "message": {"role": "user", "content": text}})
        return self

    def say(self, *texts: str) -> "Transcript":
        """One assistant record per text block, as the API streams them."""
        for text in texts:
            self.lines.append({"type": "assistant",
                               "message": {"content": [{"type": "text", "text": text}]}})
        return self

    def call(self, name: str, tool_input: dict, result=None, *, is_error: bool = False,
             prefix: str = "mcp__plugin_legal-it_legal-it__") -> "Transcript":
        self._n += 1
        call_id = f"toolu_{self._n:04d}"
        self.lines.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": call_id, "name": prefix + name, "input": tool_input}]}})
        if result is not None:
            block = {"type": "tool_result", "tool_use_id": call_id, "content": result}
            if is_error:
                block["is_error"] = True
            self.lines.append({"type": "user", "message": {"content": [block]},
                               "toolUseResult": {"stdout": "duplicate of the content"}})
        return self

    def cite_law(self, reference: str, result) -> "Transcript":
        return self.call("cite_law", {"reference": reference}, result)

    def write(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in self.lines),
                             encoding="utf-8")
        return self.path


def session(tmp_path: Path, name: str = "sessione") -> Transcript:
    return Transcript(tmp_path / f"{name}.jsonl")


def run(payload: dict, *, python_args: tuple[str, ...] = (), hook: Path = HOOK) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *python_args, str(hook)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60)


def gate(t: Transcript, **extra) -> int:
    return run({"transcript_path": str(t.write()), "hook_event_name": "Stop", **extra}).returncode


def article(n: str, body: str = "Testo dell'articolo.") -> str:
    return f"{_FONTE_CC}{n}\n\nArt. {n}.\n\n{body}"


def json_result(tipo: str, articolo: str, testo: str | None = None, *, data: str = "",
                numero: str = "", errore=None) -> str:
    return json.dumps({
        "formato": "json", "riferimento": "x", "articolo": articolo,
        "atto": {"tipo_atto": tipo, "data": data, "numero_atto": numero, "descrizione": ""},
        "url": "", "urn": None, "fonte": "normattiva", "allegato": None,
        "testo": f"Art. {articolo}.\n\nTesto." if testo is None else testo, "errore": errore,
    })


def _wrapped(markdown: str) -> str:
    """The FastMCP structured wrapper Claude Code hands the hook for a str result."""
    return json.dumps({"result": markdown})


# ---------------------------------------------------------------------------
# Bypasses found by the audit: each one is now caught
# ---------------------------------------------------------------------------

def test_a_bare_article_number_no_longer_covers_another_act(tmp_path):
    """cite_law("art. 2 Cost.") used to cover "art. 2 c.p.": only the number was compared."""
    t = session(tmp_path).prompt().cite_law("art. 2 Cost.", article("2")).say(
        "L'art. 2 c.p. disciplina la successione di leggi penali.")
    assert gate(t) == NAGS


def test_one_cite_law_of_two_articles_does_not_cover_both(tmp_path):
    """One call with two references used to credit both numbers. The server answers it
    with an error (the second reference is no act), so it credits neither."""
    t = session(tmp_path).prompt().cite_law(
        "art. 1218, art. 2043 c.c.", "**Errore**: atto 'art. 2043 c.c.' non riconosciuto.").say(
        "Rilevano l'art. 1218 c.c. e l'art. 2043 c.c.")
    assert gate(t) == NAGS


def test_a_list_of_articles_needs_each_one_read(tmp_path):
    t = session(tmp_path).prompt().cite_law("art. 1218 c.c.", article("1218")).say(
        "Si applicano gli artt. 1218 e 1223 c.c.")
    assert gate(t) == NAGS
    t.cite_law("art. 1223 c.c.", article("1223")).say("Si applicano gli artt. 1218 e 1223 c.c.")
    assert gate(t) == SILENT


def test_a_closing_text_block_does_not_hide_the_answer(tmp_path):
    """Only the last text block was read: a closing "Fatto." hid the whole answer."""
    t = session(tmp_path).prompt().say(
        "Ai sensi dell'art. 2043 c.c. il fatto illecito obbliga al risarcimento.", "Fatto.")
    assert gate(t) == NAGS


def test_text_written_to_a_prose_file_is_read(tmp_path):
    t = session(tmp_path).prompt().call(
        "Write", {"file_path": "/tmp/parere.md", "content": "# Parere\n\nL'art. 2043 c.c. impone..."},
        "File created", prefix="").say("Ho scritto il parere nel file.")
    assert gate(t) == NAGS


def test_text_written_with_edit_and_multiedit_is_read(tmp_path):
    t = session(tmp_path).prompt().call(
        "Edit", {"file_path": "/tmp/nota.txt", "old_string": "x", "new_string": "v. art. 640 c.p."},
        "ok", prefix="").say("Aggiornato.")
    assert gate(t) == NAGS
    t = session(tmp_path, "s2").prompt().call(
        "MultiEdit", {"file_path": "/tmp/nota.md", "edits": [{"old_string": "a", "new_string": "art. 41 Cost."}]},
        "ok", prefix="").say("Aggiornato.")
    assert gate(t) == NAGS


def test_text_sent_to_a_document_tool_is_read(tmp_path):
    t = session(tmp_path).prompt().call(
        "esporta_atto_docx", {"testo": "Visto l'art. 633 c.p.c., si chiede...", "titolo": "Ricorso"},
        "Salvato in /tmp/ricorso.docx").say("Ecco il documento.")
    assert gate(t) == NAGS
    t = session(tmp_path, "s2").prompt().call(
        "genera_dpa", {"titolare": "Alfa S.r.l.", "clausole_extra": ["Si richiama l'art. 82 GDPR."]},
        "DPA generato").say("Fatto.")
    assert gate(t) == NAGS


@pytest.mark.parametrize("text", [
    "Il D.Lgs. 196/2003, art. 13, regolava l'informativa.",
    "Si veda l'art. 6, par. 1, lett. f), del Regolamento (UE) 2016/679.",
    "L'art. 117 TUB disciplina i contratti bancari.",
    "Il TUF all'art. 21 fissa i criteri generali.",
    "Gli artt. 1218 e 1223 c.c. regolano l'inadempimento.",
    "L'art. 4, comma 1, lett. a), del d.lgs. n. 81 del 2008 definisce il lavoratore.",
    "L'art. 2051, primo comma, c.c. disciplina il danno da cosa in custodia.",
])
def test_acts_far_from_the_article_are_found(tmp_path, text):
    """The act had to sit within 6 characters of "art.": these all walked through."""
    assert gate(session(tmp_path).prompt().say(text)) == NAGS, text


def test_a_decision_must_be_read(tmp_path):
    t = session(tmp_path).prompt().say("Cass. civ., sez. III, n. 12345/2024 ha affermato il principio.")
    assert gate(t) == NAGS


@pytest.mark.parametrize("text", [
    "Corte cost., sent. n. 242/2019, sul fine vita.",
    "La sentenza n. 242 del 2019 della Corte costituzionale.",
    "Cons. Stato, sez. V, 3 marzo 2023, n. 2100, sull'esclusione.",
    "TAR Lazio, sez. I, n. 123/2024.",
    "La CGUE, causa C-311/18 (Schrems II), ha invalidato il Privacy Shield.",
])
def test_decisions_of_every_court_must_be_read(tmp_path, text):
    assert gate(session(tmp_path).prompt().say(text)) == NAGS, text


# ---------------------------------------------------------------------------
# Credit comes from what the tool returned
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("result", [
    article("2043", "(Risarcimento per fatto illecito).\n\nQualunque fatto doloso..."),
    "**Fonte**: Normattiva-Akn — https://x\n\n### Art. 2043\n\nArt. 2043.\n\n(Risarcimento per fatto illecito).",
    [{"type": "text", "text": "**Fonte**: Normattiva-Akn — https://x\n\n### Art. 2043\n\nQualunque fatto..."}],
    _wrapped(article("2043")),
    json_result("codice civile", "2043"),
    _wrapped(json_result("codice civile", "2043", data="1942-03-16")),
])
def test_a_cite_law_that_returned_the_article_covers_it(tmp_path, result):
    t = session(tmp_path).prompt().cite_law("art. 2043 c.c.", result).say(
        "Ai sensi dell'art. 2043 c.c. il fatto illecito obbliga al risarcimento.")
    assert gate(t) == SILENT


@pytest.mark.parametrize("result", [
    # The answer before the cite_law fix: art. 1 of the approving decree under the URL of art. 99999.
    article("99999").replace("Art. 99999.", "Art. 1"),
    "**Errore**: articolo 99999 non trovato in codice civile: per questo numero Normattiva restituisce l'art. 1",
    "**Errore**: verifica non disponibile per l'art. 99999 di codice civile",
    "**Nessun testo trovato** — URL: https://x",
    json_result("codice civile", "99999", testo="", errore="articolo 99999 non trovato in codice civile"),
    _wrapped(json_result("codice civile", "99999", testo="Art. 1.\nÈ approvato il testo...")),
    json.dumps({"qualcosa": "altro"}),
])
def test_a_cite_law_that_did_not_return_the_article_covers_nothing(tmp_path, result):
    t = session(tmp_path).prompt().cite_law("art. 99999 c.c.", result).say(
        "Ai sensi dell'art. 99999 c.c. il contratto e' nullo.")
    assert gate(t) == NAGS


def test_an_error_flag_covers_nothing(tmp_path):
    t = session(tmp_path).prompt().call("cite_law", {"reference": "art. 2043 c.c."},
                                        "connection reset", is_error=True).say("Vale l'art. 2043 c.c.")
    assert gate(t) == NAGS


def test_a_call_without_a_result_covers_nothing(tmp_path):
    t = session(tmp_path).prompt().call("cite_law", {"reference": "art. 2043 c.c."}).say(
        "Vale l'art. 2043 c.c.")
    assert gate(t) == NAGS


def test_a_failed_call_does_not_hide_a_later_successful_one(tmp_path):
    t = (session(tmp_path).prompt()
         .cite_law("art. 2043 c.c.", "**Errore**: verifica non disponibile per l'art. 2043 di codice civile")
         .cite_law("art. 2043 c.c.", article("2043"))
         .say("Ai sensi dell'art. 2043 c.c. il fatto illecito obbliga al risarcimento."))
    assert gate(t) == SILENT


def test_aliases_of_one_act_are_one_act(tmp_path):
    """The key is the act the server would fetch, not the words used for it."""
    t = session(tmp_path).prompt().cite_law("articolo 2043 codice civile", article("2043")).say(
        "Ai sensi dell'articolo 2043 del codice civile si risponde del danno.")
    assert gate(t) == SILENT
    t = session(tmp_path, "s2").prompt().cite_law("art. 13 codice privacy", "Art. 13.\n\nTesto.").say(
        "L'art. 13 del D.Lgs. 196/2003 regolava l'informativa.")
    assert gate(t) == SILENT


def test_suffixes_are_part_of_the_article(tmp_path):
    t = session(tmp_path).prompt().cite_law("art. 2 D.Lgs. 196/2003", "Art. 2.\n\nTesto.").say(
        "L'art. 2-bis D.Lgs. 196/2003 non e' l'art. 2.")
    assert gate(t) == NAGS
    t.cite_law("art. 2-bis D.Lgs. 196/2003", "Art. 2-bis.\n\nTesto.").say(
        "L'art. 2-bis D.Lgs. 196/2003 non e' l'art. 2.")
    assert gate(t) == SILENT


def test_fetch_law_article_counts(tmp_path):
    t = session(tmp_path).prompt().call(
        "fetch_law_article", {"act_type": "codice civile", "article": "2043"}, article("2043")).say(
        "L'art. 2043 c.c. fonda la responsabilita' aquiliana.")
    assert gate(t) == SILENT


def test_fetch_full_act_counts_for_the_articles_it_returned(tmp_path):
    full = "# Decreto legislativo 8 giugno 2001, n. 231\n**Fonte**: Normattiva — x\n\nArt. 5\nResponsabilita'...\n\nArt. 6\nSoggetti..."
    t = session(tmp_path).prompt().call("fetch_full_act", {"reference": "D.Lgs. 231/2001"}, full).say(
        "Gli artt. 5 e 6 del D.Lgs. 231/2001 definiscono l'imputazione.")
    assert gate(t) == SILENT
    t.say("E l'art. 25 D.Lgs. 231/2001 elenca i reati.")
    assert gate(t) == NAGS


_WINDOW_CUT_IN_A_HEADING = (
    "# Decreto legislativo 8 giugno 2001, n. 231\n**Fonte**: Normattiva — x\n**Dimensione**: 90,000 caratteri\n\n"
    "Art. 5\nResponsabilita'...\n\nArt. 6\nSoggetti...\n\nArt. 4"
    "\n\n*[Caratteri 1-30000 su 90000 totali: per leggere il seguito ripetere la chiamata con da_carattere=30001]*"
)


def test_fetch_full_act_window_does_not_credit_a_heading_it_cut(tmp_path):
    # The window stops after «Art. 4» of «Art. 41»: art. 41 was not read, nor art. 4.
    t = session(tmp_path).prompt().call(
        "fetch_full_act", {"reference": "D.Lgs. 231/2001"}, _WINDOW_CUT_IN_A_HEADING).say(
        "Gli artt. 5 e 6 del D.Lgs. 231/2001 definiscono l'imputazione.")
    assert gate(t) == SILENT
    t.say("L'art. 4 D.Lgs. 231/2001 regola i reati commessi all'estero.")
    assert gate(t) == NAGS


def test_fetch_full_act_last_window_credits_its_last_heading(tmp_path):
    last = _WINDOW_CUT_IN_A_HEADING.replace(
        "per leggere il seguito ripetere la chiamata con da_carattere=30001", "fine del testo")
    t = session(tmp_path).prompt().call("fetch_full_act", {"reference": "D.Lgs. 231/2001"}, last).say(
        "L'art. 4 D.Lgs. 231/2001 regola i reati commessi all'estero.")
    assert gate(t) == SILENT


def test_the_fallback_reader_does_not_credit_a_cut_heading(tmp_path, isolated_hook):
    args = {"python_args": ("-I", "-S"), "hook": isolated_hook}
    t = session(tmp_path).prompt().call(
        "fetch_full_act", {"reference": "D.Lgs. 231/2001"}, _WINDOW_CUT_IN_A_HEADING).say(
        "L'art. 4 D.Lgs. 231/2001 regola i reati commessi all'estero.")
    assert run({"transcript_path": str(t.write())}, **args).returncode == NAGS


def test_verification_anywhere_in_the_session_counts(tmp_path):
    t = (session(tmp_path).prompt("prima domanda").cite_law("art. 2043 c.c.", article("2043"))
         .say("Risposta.").prompt("seconda domanda").say("Resta fermo l'art. 2043 c.c."))
    assert gate(t) == SILENT


def test_only_the_last_turn_is_judged(tmp_path):
    t = session(tmp_path).prompt("prima").say("Vale l'art. 2043 c.c.").prompt("seconda").say("Ok.")
    assert gate(t) == SILENT


@pytest.mark.parametrize("tool, result", [
    ("leggi_sentenza", "# Cass. civ., sez. III, n. 12345/2024, dep. 22/04/2024\n\nTesto..."),
    ("cerca_giurisprudenza", "**Distribuzione risultati** (2 totali):\n\n### Cass. civ., sez. III, n. 12345/2024\n\nmassima..."),
])
def test_a_decision_read_with_its_court_tool_is_covered(tmp_path, tool, result):
    t = session(tmp_path).prompt().call(tool, {"numero": 12345, "anno": 2024}, result).say(
        "Cass. civ., sez. III, n. 12345/2024 ha affermato il principio.")
    assert gate(t) == SILENT


_READ_DECISION = ("# Cass. civ., sez. III, n. 1234/2020, dep. 03/03/2020\n**Materia**: privacy\n\n"
                  "## Testo della decisione\nRichiamata Cass. n. 5678/2015 e il D.Lgs. 196/2003, "
                  "nonche' la sentenza n. 99/2018 della Corte costituzionale, la Corte rigetta.")


@pytest.mark.parametrize("text", [
    "Secondo Cass. n. 5678/2015 il trattamento e' lecito.",   # a precedent cited inside the decision
    "Vedi Cass. n. 196/2003.",                               # a decree number, never a decision
    "Corte cost. n. 99/2018.",                               # another court's decision in the body
])
def test_a_read_decision_credits_itself_and_nothing_it_cites(tmp_path, text):
    t = session(tmp_path).prompt().call("leggi_sentenza", {"numero": 1234, "anno": 2020}, _READ_DECISION)
    t.say("Cass. civ., sez. III, n. 1234/2020 ha rigettato.")
    assert gate(t) == SILENT
    t.say(text)
    assert gate(t) == NAGS, text


def test_a_search_credits_its_hits_not_their_abstracts(tmp_path):
    result = ("### Cass. civ., sez. I, n. 1111/2021\n\nmassima: conforme a Cass. n. 2222/2019.\n\n"
              "### Cass. civ., sez. II, n. 3333/2022\n\nmassima.")
    t = session(tmp_path).prompt().call("cerca_giurisprudenza", {"query": "x"}, result).say(
        "Cass. n. 1111/2021 e Cass. n. 3333/2022.")
    assert gate(t) == SILENT
    t.say("Cass. n. 2222/2019.")
    assert gate(t) == NAGS


def test_a_decree_number_in_a_heading_is_not_a_decision(tmp_path):
    t = session(tmp_path).prompt().call(
        "cerca_giurisprudenza", {"query": "x"}, "### Applicazione del D.Lgs. 196/2003\n\ntesto").say(
        "Cass. n. 196/2003.")
    assert gate(t) == NAGS


def test_a_decision_not_found_covers_nothing(tmp_path):
    t = session(tmp_path).prompt().call(
        "leggi_sentenza", {"numero": 12345, "anno": 2024},
        "Decisione n. 12345/2024 non trovata negli archivi della Cassazione.").say(
        "Cass. n. 12345/2024 ha affermato il principio.")
    assert gate(t) == NAGS


def test_another_courts_tool_does_not_cover_a_decision(tmp_path):
    t = session(tmp_path).prompt().call(
        "leggi_pronuncia_costituzionale", {"numero": 242, "anno": 2019},
        "# Sentenza Corte Costituzionale n. 242/2019\n\nTesto...").say(
        "Cass. n. 242/2019 ha affermato il principio.")
    assert gate(t) == NAGS


def test_constitutional_laws_are_acts_never_decisions(tmp_path):
    """"art. 1 l. cost. 3/2001" is an article of a resolved act; "3/2001" next to the
    Cassazione is that act's number, not a decision."""
    from mcp_legal_it.core.citazioni import decisioni_nel_testo, norme_nel_testo
    found = norme_nel_testo("L'art. 1 l. cost. 3/2001 ha riscritto il Titolo V.")
    assert [(n.articolo, "legge.costituzionale:2001;3" in (n.atto or "")) for n in found] == [("1", True)]
    assert decisioni_nel_testo("La Cassazione ha applicato la l. cost. 3/2001.") == []
    t = session(tmp_path).prompt().cite_law("art. 1 l. cost. 3/2001", "Art. 1.\n\nTesto.").say(
        "L'art. 1 l. cost. 3/2001 ha riscritto il Titolo V.")
    assert gate(t) == SILENT


@pytest.mark.parametrize("text, court", [
    ("Corte cost. n. 238/2014 ha escluso l'immunita'.", "cost"),
    ("Cons. St. n. 1/2020 ha chiarito il punto.", "amm"),
    ("La CGUE, causa C-311/18, ha deciso.", "cgue"),
])
def test_the_court_of_a_decision_is_the_one_named(tmp_path, text, court):
    """The same citations verifica_citazioni routes away from Italgiure: never read as Cassazione.

    A Cassazione result carrying the same number does not cover them; their own court's does."""
    numero = {"cost": "238/2014", "amm": "1/2020", "cgue": "C-311/18"}[court]
    t = session(tmp_path).prompt().call(
        "leggi_sentenza", {}, f"# Cass. civ., sez. I, n. {numero}\n\nTesto").say(text)
    assert gate(t) == NAGS, text
    own = {"cost": ("leggi_pronuncia_costituzionale", f"# Sentenza Corte Costituzionale n. {numero}"),
           "amm": ("leggi_provvedimento_amm", f"# Consiglio di Stato\n**Estremi**: Sentenza n. {numero}, pubblicata il 01/01/2020"),
           "cgue": ("leggi_sentenza_cgue", f"# {numero}")}[court]
    t.call(own[0], {}, own[1]).say(text)
    assert gate(t) == SILENT, text


@pytest.mark.parametrize("text", [
    "La Cassazione, richiamando la Corte EDU, ric. n. 123/2020, ha deciso.",
    "Cass., richiamando Corte dei conti n. 123/2020, ha deciso.",
    "Cass. civ. che richiama il giudice di pace di Roma n. 123/2020.",
])
def test_a_court_named_after_the_cassazione_owns_the_number(text):
    """verifica_citazioni's court names: a number of the ECtHR, the Corte dei conti or a
    merits court is never a Cassazione decision, so no Cassazione reader can cover it."""
    from mcp_legal_it.core.citazioni import decisioni_nel_testo
    assert all(d.corte != "cass" for d in decisioni_nel_testo(text)), text


def test_a_cassazione_section_is_not_another_court():
    from mcp_legal_it.core.citazioni import decisioni_nel_testo
    for text in ("Cass., sez. trib., n. 1/2024.", "Cass. sez. trib. ord. n. 1/2024."):
        assert [(d.corte, d.numero) for d in decisioni_nel_testo(text)] == [("cass", "1")], text


def test_a_cassazione_reader_does_not_cover_the_council_of_state_it_cites(tmp_path):
    text = "La Cassazione, che richiama Cons. St. n. 1/2020, ha deciso."
    t = session(tmp_path).prompt().call("leggi_sentenza", {}, "# Cass. civ., sez. I, n. 1/2020\n\nTesto").say(text)
    assert gate(t) == NAGS
    t.call("leggi_provvedimento_amm", {}, "# Consiglio di Stato\n**Estremi**: Sentenza n. 1/2020, pubblicata il 01/01/2020").say(text)
    assert gate(t) == SILENT


@pytest.mark.parametrize("tool, result, text", [
    ("leggi_pronuncia_costituzionale", "# Sentenza Corte Costituzionale n. 242/2019\n\nTesto...",
     "Corte cost., sent. n. 242/2019, sul fine vita."),
    ("cerca_giurisprudenza_amministrativa",
     "### TAR Lazio — Sentenza n. 202400123 (2024)\n**Estremi**: TAR Lazio, sentenza n. 123/2024",
     "TAR Lazio, sez. I, n. 123/2024."),
    ("leggi_sentenza_cgue", "# C-311/18\n\nTesto della sentenza...",
     "La CGUE, causa C-311/18 (Schrems II), ha invalidato il Privacy Shield."),
])
def test_decisions_of_other_courts_are_covered_by_their_tools(tmp_path, tool, result, text):
    t = session(tmp_path).prompt().call(tool, {}, result).say(text)
    assert gate(t) == SILENT


@pytest.mark.parametrize("text, uncovered", [
    ("Cass. n. 500/1999; n. 600/2000.", "600/2000"),
    ("Cass. nn. 500/1999, 600/2000 e 700/2001.", "700/2001"),
    ("Corte cost. sentenze n. 242/2019 e n. 135/2024.", "135/2024"),
])
def test_every_number_of_a_list_keeps_its_court(tmp_path, text, uncovered):
    """A court named once covers the whole list: reading the first number is not enough."""
    first = text.split("n")[0]
    results = {"Cass": ("leggi_sentenza", "# Cass. civ., sez. III, n. 500/1999\n\nTesto"),
               "Corte cost": ("leggi_pronuncia_costituzionale", "# Sentenza Corte Costituzionale n. 242/2019")}
    tool, result = results["Corte cost" if first.startswith("Corte") else "Cass"]
    t = session(tmp_path).prompt().call(tool, {}, result).say(text)
    done = run({"transcript_path": str(t.write())})
    assert done.returncode == NAGS
    assert uncovered.split("/")[0] in done.stderr


@pytest.mark.parametrize("text", [
    "Cassazione, sentenza 26972 del 2008, sul danno non patrimoniale.",
    "Corte cost., sent. 242 del 2019, sul fine vita.",
    "La CGUE, causa C\u2011311/18, ha deciso.",
])
def test_decisions_written_without_n_or_with_other_dashes_are_read(tmp_path, text):
    assert gate(session(tmp_path).prompt().say(text)) == NAGS, text


def test_a_docket_number_is_not_a_decision(tmp_path):
    t = session(tmp_path).prompt().say("Il ricorso per cassazione e' iscritto al n. 1234/2023 R.G.")
    assert gate(t) == SILENT


def test_a_brocardi_abstract_does_not_cover_the_decision(tmp_path):
    t = session(tmp_path).prompt().call(
        "cerca_brocardi", {"reference": "art. 2043 c.c."},
        "Massime: Cass. civ. n. 12345/2024 — il danno...").say("Cass. civ. n. 12345/2024 lo afferma.")
    assert gate(t) == NAGS


def test_the_unified_search_credits_each_number_to_its_own_court(tmp_path):
    result = ("# Ricerca giurisprudenziale unificata: danno\n\n"
              "## Cassazione (Italgiure)\n\n### Cass. civ., sez. III, n. 12345/2024\n\nmassima...\n\n"
              "## Amministrativa (TAR/CdS)\n\n### TAR Lazio — Sentenza n. 202400123 (2024)\n"
              "**Estremi**: TAR Lazio, sentenza n. 123/2024\n\n---\n**Fonti consultate**: ...")
    t = session(tmp_path).prompt().call("cerca_giurisprudenza_unificata", {"query": "danno"}, result).say(
        "Cass. civ. n. 12345/2024 e TAR Lazio n. 123/2024.")
    assert gate(t) == SILENT
    t.say("Anche Cons. Stato n. 12345/2024.")
    assert gate(t) == NAGS


# ---------------------------------------------------------------------------
# Not citations of law: silent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "L'art. 12 riduce i costi di gestione del servizio.",
    "Vedi art. 3 del file di configurazione costruito a mano.",
    "L'art. 7 definisce la costante di normalizzazione applicata.",
    "Il punto 4 dell'art. 9 incide sul costo complessivo dell'opera.",
    "L'art. 5 del contratto di locazione prevede il rinnovo tacito.",
    "Come da art. 12 dello statuto condominiale approvato in assemblea.",
    "Vedi l'art. 3 delle condizioni generali allegate alla polizza.",
    "L'art. 7 del disciplinare di gara richiede la cauzione.",
    "Ho generato il codice fiscale del cliente, vedi art. 3 del mandato.",
    "Il codice tributo indicato nell'art. 4 del modello F24 allegato.",
    "Cerca il codice ATECO all'art. 2 della visura camerale.",
    # "costituzion" used to read as the Costituzione.
    "L'art. 1 dell'atto di costituzione della societa' fissa la sede.",
    "Nell'atto di costituzione, art. 4, e' indicato il capitale.",
    "Vedi il D.Lgs. 196/2003 in generale.",
    "Il file tar 123/2024 e' pronto.",
])
def test_things_that_are_not_citations_of_law_stay_silent(tmp_path, text):
    assert gate(session(tmp_path).prompt().say(text)) == SILENT, text


@pytest.mark.parametrize("text", [
    "Ecco l'output del tool:\n\n```\ninteressi_legali(1000, ...)\n  -> \"tassi legali: "
    "copre fino al 31/12/2026 (DM MEF, art. 1284 c.c.)\"\n```\n\nCome vedi funziona.",
    "Il campo vale `art. 2043 c.c.` nella fixture di test.",
    "```python\nRIFERIMENTO = \"art. 640 c.p.\"  # stringa di esempio\n```",
])
def test_norms_quoted_inside_code_are_not_assertions(tmp_path, text):
    assert gate(session(tmp_path).prompt().say(text)) == SILENT


def test_a_norm_outside_the_block_is_still_caught(tmp_path):
    text = "```\nesempio = 1\n```\n\nNel merito si applica l'art. 2043 c.c."
    assert gate(session(tmp_path).prompt().say(text)) == NAGS


def test_source_code_files_are_not_read(tmp_path):
    t = session(tmp_path).prompt().call(
        "Write", {"file_path": "/tmp/test_x.py", "content": 'REF = "art. 2043 c.c."'}, "ok", prefix="").say(
        "Test aggiunto.")
    assert gate(t) == SILENT


# ---------------------------------------------------------------------------
# Escape, one block per turn, fail-open
# ---------------------------------------------------------------------------

def test_the_explicit_escape_lets_an_uncovered_source_through(tmp_path):
    t = session(tmp_path).prompt().say(
        "L'art. 7 CEDU sancisce il principio di legalita' (fuori copertura: nessun tool la legge).")
    assert gate(t) == SILENT


def test_an_unresolved_source_of_law_is_flagged_until_escaped(tmp_path):
    t = session(tmp_path).prompt().say("L'art. 9 del codice deontologico forense impone la probita'.")
    assert gate(t) == NAGS


def test_the_escape_covers_only_its_own_line(tmp_path):
    t = session(tmp_path).prompt().say("Art. 7 CEDU (fuori copertura).\nVale poi l'art. 2043 c.c.")
    assert gate(t) == NAGS


def test_at_most_one_block_per_turn(tmp_path):
    t = session(tmp_path).prompt().say("Vale l'art. 2043 c.c.")
    assert gate(t, stop_hook_active=True) == SILENT


# ---------------------------------------------------------------------------
# Opt-out: LEGAL_CITATION_GATE=off switches the gate off for development sessions
# ---------------------------------------------------------------------------

_BLOCKING_TEXT = "Nel merito si applica l'art. 2043 c.c."


@pytest.mark.parametrize("value", ["off", "OFF", "Off", "0", "false", "False", "no", "NO", " off "])
def test_the_opt_out_values_skip_the_gate(tmp_path, monkeypatch, value):
    t = session(tmp_path).prompt().say(_BLOCKING_TEXT)
    monkeypatch.delenv("LEGAL_CITATION_GATE", raising=False)
    assert gate(t) == NAGS  # the same transcript blocks without the opt-out
    monkeypatch.setenv("LEGAL_CITATION_GATE", value)
    done = run({"transcript_path": str(t.path), "hook_event_name": "Stop"})
    assert done.returncode == SILENT
    assert done.stdout == "" and done.stderr == ""


def test_the_opt_out_applies_to_subagents_too(tmp_path, monkeypatch):
    monkeypatch.setenv("LEGAL_CITATION_GATE", "off")
    t = session(tmp_path).prompt().say(_BLOCKING_TEXT)
    assert gate(t, hook_event_name="SubagentStop") == SILENT


def test_the_opt_out_does_not_read_stdin_or_transcript():
    done = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True,
                          text=True, env={**os.environ, "LEGAL_CITATION_GATE": "off"}, timeout=60)
    assert (done.returncode, done.stdout, done.stderr) == (SILENT, "", "")


@pytest.mark.parametrize("value", ["", "on", "1", "true", "yes", "offf", "disabled"])
def test_any_other_value_keeps_the_gate_on(tmp_path, monkeypatch, value):
    monkeypatch.setenv("LEGAL_CITATION_GATE", value)
    assert gate(session(tmp_path).prompt().say(_BLOCKING_TEXT)) == NAGS


def test_with_the_variable_unset_the_gate_is_on(tmp_path, monkeypatch):
    monkeypatch.delenv("LEGAL_CITATION_GATE", raising=False)
    assert gate(session(tmp_path).prompt().say(_BLOCKING_TEXT)) == NAGS


@pytest.mark.parametrize("payload", [
    "not json", "{}", json.dumps({"transcript_path": "/nonexistent/x.jsonl"}), json.dumps([1, 2]),
])
def test_it_fails_open(payload):
    done = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True)
    assert done.returncode == SILENT


def test_a_corrupt_line_is_skipped(tmp_path):
    path = session(tmp_path).prompt().say("Vale l'art. 2043 c.c.").write()
    path.write_text("{broken\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    assert run({"transcript_path": str(path)}).returncode == NAGS


def test_the_message_names_the_tool_to_use(tmp_path):
    t = session(tmp_path).prompt().say("Vale l'art. 2043 c.c.; v. Cass. n. 100/2024.")
    done = run({"transcript_path": str(t.write())})
    assert done.returncode == NAGS
    assert "cite_law" in done.stderr and "leggi_sentenza" in done.stderr
    assert "fuori copertura" in done.stderr


# ---------------------------------------------------------------------------
# Subagents
# ---------------------------------------------------------------------------

def subagent(tmp_path: Path, main: str = "sessione", agent: str = "agent-a1") -> Transcript:
    return Transcript(tmp_path / main / "subagents" / f"{agent}.jsonl")


def test_subagent_stop_reads_the_subagents_own_transcript(tmp_path):
    main = session(tmp_path).prompt().call("Agent", {"prompt": "ricerca"}, prefix="")
    sub = subagent(tmp_path).prompt("Trova la norma.").say("La norma e' l'art. 2043 c.c.")
    payload = {"transcript_path": str(main.write()), "hook_event_name": "SubagentStop",
               "agent_transcript_path": str(sub.write())}
    assert run(payload).returncode == NAGS
    sub.cite_law("art. 2043 c.c.", article("2043")).say("La norma e' l'art. 2043 c.c.")
    sub.write()
    assert run(payload).returncode == SILENT


def test_a_subagents_reading_counts_for_the_main_answer(tmp_path):
    subagent(tmp_path).prompt("Trova la norma.").cite_law("art. 2043 c.c.", article("2043")).say("Ok").write()
    t = session(tmp_path).prompt().say("Secondo la ricerca, vale l'art. 2043 c.c.")
    assert gate(t) == SILENT


def test_another_sessions_subagents_never_count(tmp_path):
    subagent(tmp_path, main="altra-sessione").prompt().cite_law("art. 2043 c.c.", article("2043")).write()
    (tmp_path / "altra-sessione.jsonl").write_text("", encoding="utf-8")
    Transcript(tmp_path / "sessione" / "agent-a1.jsonl").prompt().cite_law(
        "art. 2043 c.c.", article("2043")).write()  # outside subagents/: not a subagent
    t = session(tmp_path).prompt().say("Vale l'art. 2043 c.c.")
    assert gate(t) == NAGS


def test_a_subagent_transcript_outside_the_session_is_ignored(tmp_path):
    main = session(tmp_path).prompt().write()
    stray = Transcript(tmp_path / "altrove" / "agent-x.jsonl").prompt().say("Vale l'art. 2043 c.c.").write()
    payload = {"transcript_path": str(main), "hook_event_name": "SubagentStop",
               "agent_transcript_path": str(stray)}
    assert run(payload).returncode == SILENT


def test_a_symlink_into_another_session_is_not_followed(tmp_path):
    other = subagent(tmp_path, main="altra").prompt().cite_law("art. 2043 c.c.", article("2043")).write()
    link_dir = tmp_path / "sessione" / "subagents"
    link_dir.mkdir(parents=True)
    (link_dir / "agent-link.jsonl").symlink_to(other)
    t = session(tmp_path).prompt().say("Vale l'art. 2043 c.c.")
    assert gate(t) == NAGS


def test_a_linked_subagents_folder_is_not_followed(tmp_path):
    other = subagent(tmp_path, main="altra").prompt().cite_law("art. 2043 c.c.", article("2043")).write()
    (tmp_path / "sessione").mkdir()
    (tmp_path / "sessione" / "subagents").symlink_to(other.parent, target_is_directory=True)
    t = session(tmp_path).prompt().say("Vale l'art. 2043 c.c.")
    assert gate(t) == NAGS
    payload = {"transcript_path": str(t.write()), "hook_event_name": "SubagentStop",
               "agent_transcript_path": str(tmp_path / "sessione" / "subagents" / other.name)}
    assert run(payload).returncode == SILENT  # not ours: not judged, fail-open


def test_a_linked_session_folder_is_not_followed(tmp_path):
    other = subagent(tmp_path, main="altra").prompt().cite_law("art. 2043 c.c.", article("2043")).write()
    (tmp_path / "sessione").symlink_to(other.parent.parent, target_is_directory=True)
    t = session(tmp_path).prompt().say("Vale l'art. 2043 c.c.")
    assert gate(t) == NAGS


def test_a_broken_link_does_not_drop_the_other_subagents(tmp_path):
    folder = tmp_path / "sessione" / "subagents"
    folder.mkdir(parents=True)
    (folder / "agent-a0.jsonl").symlink_to(tmp_path / "missing.jsonl")
    subagent(tmp_path, agent="agent-b1").prompt().cite_law("art. 2043 c.c.", article("2043")).write()
    t = session(tmp_path).prompt().say("Vale l'art. 2043 c.c.")
    assert gate(t) == SILENT


# ---------------------------------------------------------------------------
# The reader: the server's code, light; a stdlib fallback when it is missing
# ---------------------------------------------------------------------------

def test_the_server_reader_imports_no_http_stack():
    """The hook imports it on every turn: httpx, bs4, lxml or FastMCP would cost each Stop."""
    probe = ("import sys; sys.path.insert(0, %r); import mcp_legal_it.core.citazioni; "
             "print([m for m in ('httpx','bs4','lxml','fastmcp','mcp') if m in sys.modules])")
    server = str(HOOK.parents[1] / "server")
    done = subprocess.run([sys.executable, "-I", "-c", probe % server], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"


@pytest.fixture
def isolated_hook(tmp_path):
    """The hook with no server next to it, run with -I -S: the stdlib fallback reader."""
    hooks = tmp_path / "plugin" / "hooks"
    hooks.mkdir(parents=True)
    copy = hooks / HOOK.name
    shutil.copy(HOOK, copy)
    return copy


def test_the_fallback_reader_still_gates(tmp_path, isolated_hook):
    t = session(tmp_path).prompt().say("Ai sensi dell'art. 2043 c.c. si risponde del danno.")
    payload = {"transcript_path": str(t.write())}
    assert run(payload, python_args=("-I", "-S"), hook=isolated_hook).returncode == NAGS
    t.cite_law("art. 2043 c.c.", article("2043")).say("Ai sensi dell'art. 2043 c.c. si risponde.")
    t.write()
    assert run(payload, python_args=("-I", "-S"), hook=isolated_hook).returncode == SILENT
    t2 = session(tmp_path, "s2").prompt().say("Cass. civ. n. 12345/2024 ha deciso.")
    assert run({"transcript_path": str(t2.write())}, python_args=("-I", "-S"),
               hook=isolated_hook).returncode == NAGS


def test_the_fallback_reader_handles_spelled_out_genitives(tmp_path, isolated_hook):
    t = session(tmp_path).prompt().say("Il principio discende dall'art. 2 della Costituzione.")
    assert run({"transcript_path": str(t.write())}, python_args=("-I", "-S"),
               hook=isolated_hook).returncode == NAGS


@pytest.mark.parametrize("text", [
    "art. 1" + " " * 50000 + "x",
    "\n" * 50000 + "x",
    "x" + " art. 1" * 7000 + " ?",
])
def test_adversarial_text_is_read_quickly_by_both_readers(tmp_path, isolated_hook, text):
    """Bounded separators everywhere: a failing match must stay linear in its length."""
    t = session(tmp_path).prompt().call("fetch_full_act", {"reference": "D.Lgs. 231/2001"}, text).say(text)
    payload = {"transcript_path": str(t.write())}
    for kwargs in ({}, {"python_args": ("-I", "-S"), "hook": isolated_hook}):
        start = time.monotonic()
        run(payload, **kwargs)
        assert time.monotonic() - start < 5, kwargs


def test_the_fallback_reader_credits_only_headings_too(tmp_path, isolated_hook):
    t = session(tmp_path).prompt().call("leggi_sentenza", {"numero": 1234, "anno": 2020}, _READ_DECISION)
    t.say("Cass. civ. n. 1234/2020 ha rigettato.")
    args = {"python_args": ("-I", "-S"), "hook": isolated_hook}
    assert run({"transcript_path": str(t.write())}, **args).returncode == SILENT
    t.say("Secondo Cass. n. 5678/2015 e Cass. n. 196/2003.")
    assert run({"transcript_path": str(t.write())}, **args).returncode == NAGS


def test_a_long_session_is_judged_quickly(tmp_path):
    """Hundreds of turns and megabytes of tool results: well inside the hook's timeout."""
    t = session(tmp_path)
    big = "Art. 1.\n\n" + ("Lorem ipsum dolor sit amet. " * 4000)  # ~110 KB per result
    for i in range(300):
        t.prompt(f"domanda {i}").call("fetch_full_act", {"reference": "D.Lgs. 231/2001"}, big)
        t.call("Read", {"file_path": f"/tmp/f{i}.md"}, "x" * 20000, prefix="")
        t.say(f"Risposta {i} senza citazioni.")
    t.prompt().cite_law("art. 2043 c.c.", article("2043")).say("Vale l'art. 2043 c.c. e nient'altro.")
    path = t.write()
    assert path.stat().st_size > 30_000_000
    start = time.monotonic()
    assert run({"transcript_path": str(path)}).returncode == SILENT
    assert time.monotonic() - start < 10


# --- launcher -----------------------------------------------------------------

_COMMAND = ('uv run --no-project --python 3.12 '
            'python "${CLAUDE_PLUGIN_ROOT}/hooks/citation-gate.py"')


@pytest.mark.parametrize("event", ["Stop", "SubagentStop"])
def test_the_hook_runs_on_uv_python_outside_the_server_environment(event):
    """No bare `python3`: on Windows it is usually the Microsoft Store alias
    (exit 9009), which turned every reply into a "Stop hook error". uv's own
    Python 3.12 is there anyway, since the server needs it.

    --no-project: the gate imports only the standard library and the plugin's
    own stdlib-only modules, so it must never open the server's `.venv`. A
    `uv run --project <plugin>/server` that finds that environment linked to an
    interpreter it cannot reach deletes and recreates it under the running
    server; with --no-sync it is left empty and every tool then fails with
    "No module named ...". The same script serves SubagentStop, so a
    subagent's unread citation is stopped where it was written."""
    hook = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"][event][0]["hooks"][0]
    assert hook["command"] == _COMMAND
    # Seconds. On the first Stop of a session uv may still have to fetch Python 3.12.
    assert 15 <= hook["timeout"] <= 600


def test_no_hook_opens_the_server_project():
    hooks = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    commands = [h["command"] for groups in hooks.values() for g in groups for h in g["hooks"]]
    assert commands
    for command in commands:
        assert "--project" not in command.replace("--no-project", ""), command


def test_the_gate_reader_imports_on_a_bare_interpreter():
    # What --no-project relies on: no site-packages (-S), only the plugin folder.
    probe = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from mcp_legal_it.core import citazioni;"
        "extra = {m.split('.')[0] for m in sys.modules} - set(sys.stdlib_module_names);"
        "print(sorted(extra - {'__main__', 'mcp_legal_it'}))"
    )
    done = subprocess.run([sys.executable, "-I", "-S", "-c", probe, str(HOOK.parents[1] / "server")],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
