"""Turn a seed decision into a standalone task with evaluation criteria.

The builder model sees the decision. The system under test sees only
`task.query`. `parse_builder_output` enforces that separation by rejecting a
query that leaks the decision number — the single most likely way for the
generator to hand the answer to the subject.
"""

from __future__ import annotations

import json
import re

from benchmarks.legalita.corpus.sample import SeedDecision
from benchmarks.legalita.schema import Criterion, Task, ValidationError

BUILDER_PROMPT = """Sei un giurista che costruisce task di valutazione per un benchmark di diritto italiano.

Ti fornisco una pronuncia della Corte di cassazione. Devi produrre:

1. `query` — un quesito professionale AUTONOMO (standalone), come lo porrebbe un
   avvocato che NON conosce questa pronuncia. Non deve mai citare gli estremi
   della pronuncia, né alludere alla sua esistenza. Deve essere risolvibile da
   chi conosce il diritto italiano.
2. `issue_summary` — una frase che descrive la questione giuridica.
3. `issue_status` — uno tra:
   - `settled`: un orientamento consolidato risolve la questione;
   - `revirement`: un orientamento precedente è stato superato, e va
     identificato quello successivo al mutamento;
   - `active_conflict`: permangono orientamenti incompatibili.
4. `criteria` — da 1 a 4 criteri di valutazione binari e verificabili. Ciascuno
   con `text` e `required` (true = necessario per superare il task, false =
   bonus). Almeno uno deve essere `required`.
5. `builder_confidence` — `high` o `low`. Usa `low` quando non sei sicuro
   dell'issue_status o quando i criteri sono opinabili: quei task andranno in
   revisione umana.

Rispondi SOLO con un oggetto JSON con queste cinque chiavi.

PRONUNCIA
Numero: {number}/{year}
Sezione: {section}
Deposito: {deposited}
Materia: {materia}
Massima e dispositivo:
{dispositivo}
"""

_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>\{.*\})\s*```", re.DOTALL)


class BuilderError(ValueError):
    """The builder model produced something unusable."""


def build_prompt(decision: SeedDecision, domain: str) -> str:
    return BUILDER_PROMPT.format(
        number=decision.number,
        year=decision.year,
        section=decision.section,
        deposited=decision.deposited.isoformat(),
        materia=decision.materia,
        dispositivo=decision.dispositivo,
    )


def _extract_json(text: str) -> dict:
    fenced = _FENCE_RE.search(text)
    candidate = fenced.group("body") if fenced else text.strip()
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1:
            raise BuilderError(f"builder output is not JSON: {text[:120]!r}")
        candidate = candidate[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise BuilderError(f"builder output is not JSON: {exc}") from exc


def parse_builder_output(
    text: str,
    task_id: str,
    domain: str,
    decision: SeedDecision,
) -> Task:
    payload = _extract_json(text)

    query = str(payload.get("query", "")).strip()
    if not query:
        raise BuilderError(f"{task_id}: empty query")
    if str(decision.number) in query:
        raise BuilderError(
            f"{task_id}: query leaks the seed decision number {decision.number}"
        )

    raw_criteria = payload.get("criteria") or []
    criteria = [
        Criterion(
            id=f"C-{index:03d}",
            text=str(item.get("text", "")).strip(),
            required=bool(item.get("required", True)),
        )
        for index, item in enumerate(raw_criteria, start=1)
    ]

    try:
        return Task.from_dict(
            {
                "id": task_id,
                "track": "jurisprudential",
                "domain": domain,
                "query": query,
                "criteria": [c.to_dict() for c in criteria],
                "issue_status": payload.get("issue_status"),
                "issue_summary": str(payload.get("issue_summary", "")),
                "seed_citation": {
                    "court": "Cass. civ.",
                    "section": decision.section,
                    "number": decision.number,
                    "year": decision.year,
                },
                "builder_confidence": payload.get("builder_confidence", "low"),
                "curated": False,
            }
        )
    except ValidationError as exc:
        raise BuilderError(f"{task_id}: {exc}") from exc
