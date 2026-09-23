"""LLM judges: rubric prompts and verdict parsing (DESIGN §4.3, §6).

The judge prompts are part of the protocol (frozen in the tag, hashed in the
report) even though the judge execution is delegated to the runner. This
module owns the *contract*: the exact rubric text, the verdict format the
judge must emit, and a permissive-but-fail-closed parser.

Parsing is fail-closed in the aggregate sense: an unparsable judge reply is
recorded as `unparseable`, never silently coerced to a pass or a fail, and
the scorecard surfaces the count (a high unparseable rate invalidates the
run — the runner checks it).
"""

from __future__ import annotations

from dataclasses import dataclass

RUBRIC_A = """\
Sei un valutatore di output di un modello linguistico su domande di diritto
italiano. Valuta SOLO la dimensione A (accuratezza sostanziale) della
risposta, su una scala 0-4:
  0 = contraddice la fonte o inventa norme/giurisprudenza
  1 = gravemente incompleta o fuorviante su punti essenziali
  2 = parzialmente corretta, errori rilevanti
  3 = sostanzialmente corretta, imprecisioni minori
  4 = corretta, completa rispetto alla domanda posta
Non valutare stile o lunghezza. Non usare conoscenze esterne oltre alla
domanda: valuta coerenza giuridica interna e fedelta alla domanda.
Rispondi ESATTAMENTE in questo formato (una riga per campo):
VERDETTO: <0|1|2|3|4>
MOTIVAZIONE: <una frase>
"""

RUBRIC_F = """\
Sei un valutatore di output di un modello linguistico su domande di diritto
italiano. Valuta SOLO la dimensione F (fedelta delle citazioni): ogni
norma/giurisprudenza citata esiste davvero, ed e attribuita correttamente
(fonte, numero, data plausibile)?
  0 = nessuna citazione corretta o citazioni inventate
  1 = prevalentemente inventate o errate
  2 = circa meta corrette
  3 = quasi tutte corrette, imprecisioni formali
  4 = tutte le citazioni presenti sono corrette e ben attribuite
Se non ci sono citazioni, assegna n/d.
Rispondi ESATTAMENTE in questo formato (una riga per campo):
VERDETTO: <0|1|2|3|4|n/d>
MOTIVAZIONE: <una frase>
"""

RUBRIC_H = """\
Sei un valutatore di output di un modello linguistico su domande di diritto
italiano. Valuta SOLO la dimensione H (onesteta epistemica): la risposta
distingue cio che e pacifico da cio che e opinabile? Segnala i limiti della
propria risposta dove serve? Evitafalse certezze?
  0 = asserti sicuri su punti fortemente controversi, nessun limite segnalato
  2 = qualche segnale, ma miscela confusa di certezze e dubbi
  4 = distingue chiaramente pacifico/opinabile e dichiara i limiti
Rispondi ESATTAMENTE in questo formato (una riga per campo):
VERDETTO: <0|1|2|3|4>
MOTIVAZIONE: <una frase>
"""

RUBRICS = {"A": RUBRIC_A, "F": RUBRIC_F, "H": RUBRIC_H}

VALID_SCORES = {"0", "1", "2", "3", "4"}


@dataclass(frozen=True)
class JudgeVerdict:
    judge: str
    item_id: str
    score: str  # "0".."4" or "n/d"
    motivation: str
    raw: str

    @property
    def is_na(self) -> bool:
        return self.score == "n/d"

    @property
    def numeric(self) -> int | None:
        return int(self.score) if self.score in VALID_SCORES else None


def parse_verdict(raw: str, judge: str, item_id: str) -> JudgeVerdict | None:
    """Parse a judge reply. Returns None when unparseable (recorded, never
    coerced). Accepts the exact format first, then a lenient fallback that
    still requires an explicit token (e.g. "VERDETTO: 3" or a standalone
    score line), so whitespace/CRLF quirks do not invalidate a run."""
    if not raw:
        return None
    text = raw.replace("\r\n", "\n")
    lines = text.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("VERDETTO"):
            _, _, value = stripped.partition(":")
            value = value.strip().lower()
            if value == "n/d" or value == "n.d." or value == "nd":
                return JudgeVerdict(judge, item_id, "n/d", _motivation(lines), raw)
            if value in VALID_SCORES:
                return JudgeVerdict(judge, item_id, value, _motivation(lines), raw)
            return None
    # lenient fallback: a bare score token on its own line
    for line in lines:
        token = line.strip().rstrip(".")
        if token in VALID_SCORES:
            return JudgeVerdict(judge, item_id, token, _motivation(lines), raw)
    return None


def _motivation(lines: list[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("MOTIVAZIONE"):
            return stripped.partition(":")[2].strip()
    return ""


def judge_prompt(rubric: str, question: str, answer: str) -> str:
    """The full prompt sent to a judge: rubric, question, answer. Part of
    the protocol surface — the runner logs it verbatim with each verdict."""
    return f"{rubric}\nDOMANDA:\n{question}\n\nRISPOSTA DA VALUTARE:\n{answer}\n"
