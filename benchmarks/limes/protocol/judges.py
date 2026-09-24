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


# --------------------------------------------------------------------------
# Wave 1: residual-rubric judging with bias countermeasures (B2).
#
# Judges only see rubrics NOT covered by the mechanical layer
# (`Rubric.mechanical == False`); the mechanical dimensions never change
# because of a judge. Countermeasures (Wataoka et al. 2024 on self-preference;
# position/verbosity bias):
#   (i)   judge family must differ from every evaluated model's family;
#   (ii)  explicit per-item rubrics, binary per criterion (no holistic score);
#   (iii) criterion order shuffled with a seed derived from the protocol
#         seed, reproducible, and judged twice in two different orders;
#   (iv)  no inferential use until calibration against a human gold set
#         passes the pre-registered thresholds (kappa, Equal Opportunity).
# --------------------------------------------------------------------------

import hashlib
import json as _json
import os
import random
import re
import urllib.error
import urllib.request

RUBRIC_RESIDUAL = """\
Sei un valutatore di risposte a quesiti di diritto italiano. Per ciascun
criterio elencato stabilisci se la RISPOSTA lo soddisfa. Valuta solo il
contenuto richiesto dal criterio: ignora lunghezza, stile e tono; una
risposta più lunga non è per questo migliore. Non premiare citazioni che
non puoi riscontrare: se un criterio richiede una fonte e la risposta ne
cita una inesistente o sbagliata, il criterio NON è soddisfatto.
Rispondi con una riga per criterio, nell'ordine dato, esattamente così:
<ID>: SI
<ID>: NO
Nessun altro testo.
"""

_FAMILY_PREFIXES = {
    "claude": "anthropic",
    "anthropic/": "anthropic",
    "openai/": "openai",
    "gpt-": "openai",
    "google/": "google",
    "gemini": "google",
    "meta-llama/": "meta",
    "mistralai/": "mistral",
    "x-ai/": "xai",
    "deepseek/": "deepseek",
    "qwen/": "qwen",
}


class JudgeError(RuntimeError):
    """Raised when the judge panel violates the protocol (fail-closed)."""


def model_family(model_id: str) -> str:
    """Vendor family of a model id; unknown ids are their own family
    (fail-closed in the heterogeneity check only when they collide)."""
    lowered = model_id.lower()
    for prefix, family in _FAMILY_PREFIXES.items():
        if lowered.startswith(prefix):
            return family
    return lowered.split("/", 1)[0]


def enforce_heterogeneous(judges: list[str], evaluated: list[str]) -> None:
    """(i) A judge never shares a family with an evaluated model: judges
    prefer their own family's outputs (self-preference bias)."""
    evaluated_families = {model_family(m) for m in evaluated}
    clash = [j for j in judges if model_family(j) in evaluated_families]
    if clash:
        raise JudgeError(
            f"giudici della stessa famiglia dei modelli valutati: {clash} "
            f"(famiglie valutate: {sorted(evaluated_families)})"
        )
    if len({model_family(j) for j in judges}) < len(judges):
        raise JudgeError("il pannello deve avere giudici di famiglie diverse tra loro")


def criterion_order(rubric_ids: list[str], seed: int, item_id: str, judge: str, replica: int) -> list[str]:
    """(iii) Reproducible shuffled order of the criteria for one judgement.

    The RNG is keyed by a hash of (protocol seed, item, judge, replica), so
    the same protocol always produces the same orders, and the two replicas
    see different orders whenever there are at least two criteria.
    """
    key = f"{seed}|{item_id}|{judge}|{replica}".encode("utf-8")
    rng = random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))
    order = list(rubric_ids)
    rng.shuffle(order)
    if replica > 0 and len(order) > 1 and order == criterion_order(rubric_ids, seed, item_id, judge, 0):
        order = order[1:] + order[:1]  # guarantee a different order across replicas
    return order


def residual_prompt(question: str, answer: str, rubrics: dict[str, str], order: list[str]) -> str:
    criteria = "\n".join(f"{rid}: {rubrics[rid]}" for rid in order)
    return (
        f"{RUBRIC_RESIDUAL}\nCRITERI:\n{criteria}\n\nDOMANDA:\n{question}\n\n"
        f"RISPOSTA DA VALUTARE:\n{answer}\n"
    )


_CRITERION_LINE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(SI|SÌ|NO)\b", re.IGNORECASE)


def parse_residual(raw: str, expected_ids: list[str]) -> dict[str, bool] | None:
    """Parse per-criterion verdicts. None (unparseable, recorded as such)
    unless EVERY expected criterion has exactly one verdict — a partial
    reply is never completed by guessing."""
    if not raw:
        return None
    found: dict[str, bool] = {}
    for line in raw.replace("\r\n", "\n").split("\n"):
        match = _CRITERION_LINE.match(line)
        if not match:
            continue
        rid, verdict = match.group(1), match.group(2).upper()
        if rid in found:
            return None  # contradictory duplicate
        found[rid] = verdict in ("SI", "SÌ")
    if set(found) != set(expected_ids):
        return None
    return found


def openrouter_call(model: str, prompt: str, seed: int, timeout_s: int = 120) -> str:
    """One judge call through OpenRouter (stdlib only). Temperature 0 and a
    fixed seed: the judge is part of the instrument, not a sampler."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise JudgeError("OPENROUTER_API_KEY non impostata: i giudici non possono girare")
    body = _json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "seed": seed,
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = _json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise JudgeError(f"chiamata giudice {model} fallita: {exc}") from exc
    try:
        return str(payload["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError) as exc:
        raise JudgeError(f"risposta giudice {model} senza contenuto: {payload!r:.200}") from exc


def judge_item(
    item_id: str,
    question: str,
    answer: str,
    rubrics: dict[str, str],
    judges: list[str],
    seed: int,
    replicas: int = 2,
    call=openrouter_call,
) -> dict:
    """Judge one answer on its residual rubrics with every judge x replica.

    Returns per-judge, per-replica verdicts (None = unparseable or failed
    call, recorded), the consensus per criterion (all parsed judgements
    agree) and the intra-judge agreement across replicas (DESIGN §6: the
    variance floor published with the scorecard).
    """
    ids = sorted(rubrics)
    judgements: list[dict] = []
    for judge in judges:
        for replica in range(replicas):
            order = criterion_order(ids, seed, item_id, judge, replica)
            prompt = residual_prompt(question, answer, rubrics, order)
            try:
                raw = call(judge, prompt, seed)
                error = None
            except JudgeError as exc:
                raw, error = "", str(exc)
            judgements.append({
                "judge": judge,
                "replica": replica,
                "order": order,
                "verdicts": parse_residual(raw, ids),
                "error": error,
                "raw": raw,
            })
    parsed = [j for j in judgements if j["verdicts"] is not None]
    consensus: dict[str, bool | None] = {}
    for rid in ids:
        values = {j["verdicts"][rid] for j in parsed}
        consensus[rid] = values.pop() if len(values) == 1 else None
    intra: list[float] = []
    for judge in judges:
        mine = [j["verdicts"] for j in parsed if j["judge"] == judge]
        if len(mine) >= 2:
            agree = sum(1 for rid in ids if mine[0][rid] == mine[1][rid])
            intra.append(agree / len(ids))
    return {
        "item_id": item_id,
        "judgements": judgements,
        "unparseable": len(judgements) - len(parsed),
        "consensus": consensus,
        "intra_judge_agreement": sum(intra) / len(intra) if intra else None,
    }


# --- calibration against the human gold set (iv) ---------------------------


def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected == 1.0:
        return 1.0 if observed == 1.0 else None
    return (observed - expected) / (1 - expected)


def calibration(gold: list[dict], judge_verdicts: dict[str, bool], thresholds: dict) -> dict:
    """Judge vs human gold set.

    `gold` rows: {key, human: [label_1, label_2], group}. Only rows where
    the two human labellers AGREE form the reference (disagreements are
    reported, not resolved by the machine). `judge_verdicts` maps key ->
    judge consensus. Equal Opportunity gap (Wataoka et al.): the spread of
    the judge's true-positive rate across `group`s (e.g. which surface or
    model produced the answer) — a judge that recognises a correct answer
    more readily for one group than another is biased toward it.
    """
    min_n = int(thresholds["min_gold"])
    min_kappa = float(thresholds["min_kappa"])
    max_eo = float(thresholds["max_eo_gap"])
    human_pairs = [r for r in gold if len(r.get("human", [])) == 2]
    human_kappa = cohen_kappa([r["human"][0] for r in human_pairs], [r["human"][1] for r in human_pairs])
    reference = [r for r in human_pairs if r["human"][0] == r["human"][1] and r["key"] in judge_verdicts]
    truth = [r["human"][0] for r in reference]
    predicted = [judge_verdicts[r["key"]] for r in reference]
    kappa = cohen_kappa(truth, predicted)
    tpr_by_group: dict[str, float] = {}
    for group in sorted({r.get("group", "") for r in reference}):
        positives = [r for r in reference if r.get("group", "") == group and r["human"][0]]
        if positives:
            tpr_by_group[group] = sum(1 for r in positives if judge_verdicts[r["key"]]) / len(positives)
    eo_gap = (max(tpr_by_group.values()) - min(tpr_by_group.values())) if len(tpr_by_group) >= 2 else None
    passed = (
        len(reference) >= min_n
        and kappa is not None and kappa >= min_kappa
        and (eo_gap is None or eo_gap <= max_eo)
    )
    return {
        "gold_rows": len(gold),
        "human_double_labelled": len(human_pairs),
        "human_kappa": human_kappa,
        "reference_n": len(reference),
        "judge_kappa": kappa,
        "tpr_by_group": tpr_by_group,
        "eo_gap": eo_gap,
        "thresholds": {"min_gold": min_n, "min_kappa": min_kappa, "max_eo_gap": max_eo},
        "calibrated": passed,
    }
