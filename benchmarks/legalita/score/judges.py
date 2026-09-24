"""Two-judge panel with a human tiebreak.

Both judges are Claude — a real weakness, declared in the spec — so the
tiebreak is deliberately NOT a third model. Disagreements go to a human
queue, and the same queue doubles as the measured judge-error estimate.

Criteria are judged grouped by answer rather than one call per criterion.
That deviates from the paper and is declared; the halo effect it introduces
is mitigated by shuffling criterion order and demanding a separate written
justification for each.
"""

from __future__ import annotations

import json
import random
import re

from benchmarks.legalita.schema import Citation, Criterion, RunRecord, Task, Verdict

JUDGE_MODELS: dict[str, str] = {"A": "sonnet", "B": "opus"}

_MAX_DISAGREEMENTS = 40
_AGREEMENT_SAMPLE = 30

# Amendment A4: the agreement stratum is itself stratified by "arm" so one
# arm can't dominate the human-audit sample. Every non-empty arm gets at
# least this many slots (or all of it, if it has fewer items than this).
_MIN_PER_STRATUM = 5

# Fallback stratum key for agreement items that carry no "arm" (older
# call shapes, or a caller that genuinely has no per-arm breakdown).
_NO_ARM_STRATUM = "_all"

_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>\{.*\})\s*```", re.DOTALL)

_JUDGE_TEMPLATE = """Sei un giurista italiano che valuta una risposta professionale.

Ti do un quesito, una risposta e un elenco di criteri. Per OGNI criterio esprimi
un verdetto binario: soddisfatto (true) o non soddisfatto (false). Valuta ogni
criterio in modo indipendente dagli altri e scrivi per ciascuno una motivazione
separata. Non sapere quale sistema abbia prodotto la risposta fa parte del
protocollo: valuta solo il testo.

QUESITO
{query}

RISPOSTA DA VALUTARE
{answer}

CRITERI
{criteria}

Rispondi SOLO con un oggetto JSON:
{{"verdicts": [{{"criterion_id": "...", "verdict": true, "reasoning": "..."}}]}}
"""


class JudgeError(ValueError):
    """A judge produced output the panel cannot use."""


def build_judge_prompt(
    task: Task,
    record: RunRecord,
    criteria: list[Criterion],
    seed: int = 20250107,
) -> str:
    """Blind prompt: the arm that produced the answer is never mentioned."""
    shuffled = list(criteria)
    random.Random(f"{seed}:{task.id}").shuffle(shuffled)
    rendered = "\n".join(f"- {c.id}: {c.text}" for c in shuffled)
    return _JUDGE_TEMPLATE.format(
        query=task.query, answer=record.answer, criteria=rendered
    )


def parse_judge_output(
    text: str,
    task_id: str,
    arm: str,
    judge: str,
    criterion_ids: list[str],
) -> list[Verdict]:
    fenced = _FENCE_RE.search(text)
    candidate = fenced.group("body") if fenced else text.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"{task_id}/{judge}: judge output is not JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise JudgeError(f"{task_id}/{judge}: judge output has wrong shape: expected dict, got {type(payload).__name__}")

    verdicts_list = payload.get("verdicts")
    if not isinstance(verdicts_list, list):
        raise JudgeError(f"{task_id}/{judge}: judge output has wrong shape: 'verdicts' must be a list, got {type(verdicts_list).__name__ if verdicts_list is not None else 'null'}")

    seen = {}
    for item in verdicts_list:
        if not isinstance(item, dict):
            raise JudgeError(f"{task_id}/{judge}: judge output has wrong shape: each verdict must be a dict, got {type(item).__name__}")
        cid = item.get("criterion_id")
        if cid is None:
            raise JudgeError(f"{task_id}/{judge}: judge output has wrong shape: verdict is missing 'criterion_id'")
        if not isinstance(cid, str):
            raise JudgeError(f"{task_id}/{judge}: judge output has wrong shape: 'criterion_id' must be a string, got {type(cid).__name__}")
        seen[cid] = item

    seen_ids = set(seen.keys())
    expected_ids = set(criterion_ids)
    unexpected = seen_ids - expected_ids
    if unexpected:
        raise JudgeError(f"{task_id}/{judge}: unexpected criteria {sorted(unexpected)}")
    missing = expected_ids - seen_ids
    if missing:
        raise JudgeError(f"{task_id}/{judge}: missing criteria {sorted(missing)}")

    return [
        Verdict(
            task_id=task_id, arm=arm, criterion_id=cid, judge=judge,
            verdict=bool(seen[cid].get("verdict")),
            reasoning=str(seen[cid].get("reasoning", "")),
        )
        for cid in criterion_ids
    ]


def reconcile(
    verdicts_a: list[Verdict],
    verdicts_b: list[Verdict],
) -> tuple[dict[tuple[str, str, str], bool], list[dict]]:
    """Agreed verdicts plus the queue for the human tiebreak.

    Disagreement entries deliberately carry NO verdict field: nothing in this
    pipeline may guess an answer the two judges could not agree on.
    """
    def key(v: Verdict) -> tuple[str, str, str]:
        return (v.task_id, v.arm, v.criterion_id)

    index_a = {key(v): v for v in verdicts_a}
    index_b = {key(v): v for v in verdicts_b}
    if set(index_a) != set(index_b):
        symmetric = set(index_a) ^ set(index_b)
        raise JudgeError(f"unpaired judge verdicts: {sorted(symmetric)}")

    agreed: dict[tuple[str, str, str], bool] = {}
    disagreements: list[dict] = []
    for k in sorted(index_a):
        a, b = index_a[k], index_b[k]
        if a.verdict == b.verdict:
            agreed[k] = a.verdict
        else:
            disagreements.append(
                {
                    "task_id": a.task_id,
                    "arm": a.arm,
                    "criterion_id": a.criterion_id,
                    "reasoning_a": a.reasoning,
                    "reasoning_b": b.reasoning,
                }
            )
    return agreed, disagreements


def _largest_remainder_allocate(
    weights: dict[str, int],
    total: int,
    cap: dict[str, int],
) -> dict[str, int]:
    """Round `weights` proportionally so the allocation sums to `total`
    (or less, if capacity runs out), using the largest-remainder method.

    Deterministic: ties in the fractional remainder are broken by key name
    (ascending), never by dict/insertion order. Never allocates more than
    `cap[key]` to any key, and never allocates more than `total` overall —
    if every key hits its cap before `total` is exhausted, the shortfall is
    simply left unallocated rather than exceeding a cap.
    """
    keys = sorted(weights)
    weight_sum = sum(weights.values())
    if weight_sum <= 0 or total <= 0:
        return {k: 0 for k in keys}

    raw = {k: total * weights[k] / weight_sum for k in keys}
    alloc = {k: min(int(raw[k]), cap[k]) for k in keys}

    leftover = total - sum(alloc.values())
    if leftover > 0:
        by_remainder = sorted(keys, key=lambda k: (-(raw[k] - int(raw[k])), k))
        for k in by_remainder:
            if leftover <= 0:
                break
            if alloc[k] >= cap[k]:
                continue
            alloc[k] += 1
            leftover -= 1
    return alloc


def _allocate_agreement_budget(sizes: dict[str, int], budget: int) -> dict[str, int]:
    """How many agreement items to draw from each arm stratum.

    Proportional to stratum size, with a floor of `min(_MIN_PER_STRATUM,
    size)` per non-empty stratum, rounded with the largest-remainder method
    so the total never exceeds `budget`.
    """
    arms = sorted(sizes)
    total_size = sum(sizes.values())
    if total_size <= budget:
        return dict(sizes)  # every stratum taken in full

    floors = {arm: min(_MIN_PER_STRATUM, sizes[arm]) for arm in arms}
    floor_total = sum(floors.values())
    if floor_total >= budget:
        # The floors alone don't fit the budget: fall back to a plain
        # proportional split (no guaranteed minimum), still capped per
        # stratum and never exceeding the budget.
        return _largest_remainder_allocate(sizes, budget, cap=sizes)

    capacity = {arm: sizes[arm] - floors[arm] for arm in arms}
    remaining_budget = budget - floor_total
    weights = {arm: sizes[arm] for arm in arms if capacity[arm] > 0}
    extra = _largest_remainder_allocate(
        weights, remaining_budget, cap={arm: capacity[arm] for arm in weights}
    )

    allocation = dict(floors)
    for arm, n in extra.items():
        allocation[arm] += n
    return allocation


def _stratified_agreement_sample(agreed: list[dict], seed: int, budget: int) -> list[dict]:
    """Sample the agreement stratum, grouped by `item["arm"]` (missing arm
    falls into a single `_all` stratum). Ordering is deterministic: strata
    are visited sorted by arm name, and within a stratum either every item
    is kept (stable input order) or `random.Random(f"{seed}:agreements:{arm}")`
    draws the subset — a generator independent of every other stratum and
    of the disagreement draw.
    """
    if not agreed:
        return []

    strata: dict[str, list[dict]] = {}
    for item in agreed:
        strata.setdefault(item.get("arm") or _NO_ARM_STRATUM, []).append(item)

    arm_names = sorted(strata)
    sizes = {arm: len(strata[arm]) for arm in arm_names}
    allocation = _allocate_agreement_budget(sizes, budget)

    picked: list[dict] = []
    for arm in arm_names:
        stratum_items = strata[arm]
        n = allocation.get(arm, 0)
        if n >= len(stratum_items):
            picked.extend(stratum_items)
        else:
            rng = random.Random(f"{seed}:agreements:{arm}")
            picked.extend(rng.sample(stratum_items, n))
    return picked


def audit_sample(
    agreed: list[dict],
    disagreements: list[dict],
    seed: int = 20250107,
    agreement_sample: int = _AGREEMENT_SAMPLE,
) -> list[dict]:
    """The human audit queue: every disagreement, plus sampled agreements.

    Sampling the AGREED set is what makes the error estimate meaningful. Two
    same-provider judges can agree and both be wrong; without this stratum the
    audit would only ever measure the cases the panel already flagged.

    Amendment A4: the agreement draw is stratified by `item["arm"]` so one
    arm can't dominate the sample — see `_stratified_agreement_sample`. The
    disagreement draw is untouched: its own independent RNG
    (`f"{seed}:disagreements"`), its own fixed cap, so neither stratum's
    sampling perturbs the other.
    """
    rng_disagreements = random.Random(f"{seed}:disagreements")

    picked_disagreements = (
        list(disagreements)
        if len(disagreements) <= _MAX_DISAGREEMENTS
        else rng_disagreements.sample(disagreements, _MAX_DISAGREEMENTS)
    )
    picked_agreements = _stratified_agreement_sample(agreed, seed, agreement_sample)

    return [
        *[{**item, "stratum": "disagreement"} for item in picked_disagreements],
        *[{**item, "stratum": "agreement"} for item in picked_agreements],
    ]


# --- Citation-grounding validation --------------------------------------
#
# A second, independent judgment pass, blind like the criteria one above:
# does the *authority* a resolved citation points to actually cover the
# legal issue in the role the task asks about? A citation can be real
# (`resolved is True`) and still be grounding nothing — e.g. a genuine
# Cassazione decision about a different question entirely. `covers_issue`
# is what `Citation.counts_as_grounded()` requires alongside `resolved`.
#
# No Judge C: the agreement rule below is the whole tiebreak mechanism —
# both true, both false, or the pair goes to the human audit queue exactly
# like a criteria disagreement, never guessed.

GROUNDING_TEMPLATE = """Sei un giurista italiano che verifica se una citazione giurisprudenziale è pertinente.

Ti do il quesito professionale, la questione giuridica in esso sottesa, il testo
della citazione prodotta da un sistema e la nota di verifica dell'esistenza
della fonte. Il tuo compito NON è verificare se la fonte esiste (già fatto):
devi valutare se quella autorità copre la questione giuridica del quesito nel
ruolo in cui viene invocata (es. a sostegno della tesi, come precedente
applicabile), non un tema solo genericamente affine.

QUESITO
{query}

QUESTIONE GIURIDICA
{issue_summary}

CITAZIONE PRODOTTA
{raw}

NOTA DI VERIFICA DELLA FONTE
{resolution_note}

Rispondi SOLO con un oggetto JSON:
{{"covers": true, "reasoning": "..."}}
"""


def build_grounding_prompt(task: Task, citation: Citation) -> str:
    """Blind prompt: the arm that produced the citation is never mentioned."""
    return GROUNDING_TEMPLATE.format(
        query=task.query,
        issue_summary=task.issue_summary,
        raw=citation.raw,
        resolution_note=citation.resolution_note or "(nessuna nota)",
    )


def parse_grounding_output(text: str) -> tuple[bool, str]:
    """Fail-closed parse of a grounding verdict: `(covers, reasoning)`.

    Mirrors `parse_judge_output`'s tolerance for a fenced code block, and
    raises `JudgeError` rather than guessing on anything else — an
    unparseable grounding verdict must never be silently read as
    `covers=False` (which would look identical to a genuine negative
    verdict) nor as `covers=True` (which would fabricate grounding).
    """
    fenced = _FENCE_RE.search(text)
    candidate = fenced.group("body") if fenced else text.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"grounding output is not JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise JudgeError(
            f"grounding output has wrong shape: expected dict, got {type(payload).__name__}"
        )
    if "covers" not in payload:
        raise JudgeError("grounding output has wrong shape: missing 'covers'")
    if not isinstance(payload["covers"], bool):
        raise JudgeError(
            f"grounding output has wrong shape: 'covers' must be a bool, got {type(payload['covers']).__name__}"
        )
    return bool(payload["covers"]), str(payload.get("reasoning", ""))
