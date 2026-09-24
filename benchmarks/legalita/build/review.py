"""Targeted human curation of the gold set.

Markdown in, markdown out: the reviewer is a lawyer with a text editor, not
an API client. The parser reads only the canonical checkboxes, so free-text notes
the reviewer adds anywhere in the file are harmless.

A canonical checkbox must be exactly `- [<mark>] approva` or `- [<mark>] scarta`
with nothing else on the line. A ticked box with trailing text (e.g.,
`- [x] approva (con riserva)`) is treated as untouched/deferred — it errs safe
by not silently making a decision based on an ambiguous line. The task simply
re-enters the next export for the reviewer to clarify.
"""

from __future__ import annotations

import re

from benchmarks.legalita.schema import Task

_BLOCK_RE = re.compile(
    r"^##\s+(?P<id>[A-Z0-9\-]+)\s*$(?P<body>.*?)(?=^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_APPROVE_RE = re.compile(r"^-\s*\[(?P<mark>[ xX])\]\s*approva\s*$", re.MULTILINE)
_REJECT_RE = re.compile(r"^-\s*\[(?P<mark>[ xX])\]\s*scarta\s*$", re.MULTILINE)


def needs_review(tasks: list[Task]) -> list[Task]:
    """Tasks the builder was unsure about and that nobody has signed off yet."""
    return [t for t in tasks if t.builder_confidence == "low" and not t.curated]


def export_review_markdown(tasks: list[Task]) -> str:
    lines = [
        "# Curatela mirata — LegalITA benchmark",
        "",
        "Per ogni task: spunta `approva` se query, criteri e issue status sono",
        "corretti; spunta `scarta` se il task va eliminato. Lascia entrambe le",
        "caselle vuote per rimandare la decisione. Le note libere sono ignorate",
        "dal parser: scrivile pure dove vuoi.",
        "",
    ]
    for task in tasks:
        seed = task.seed_citation or {}
        lines += [
            f"## {task.id}",
            "",
            f"**Dominio**: {task.domain} · **Issue status**: {task.issue_status}",
            f"**Pronuncia seme**: {seed.get('court', '')} sez. {seed.get('section', '')} "
            f"n. {seed.get('number', '')}/{seed.get('year', '')}",
            "",
            f"**Quesito**: {task.query}",
            "",
            f"**Questione**: {task.issue_summary}",
            "",
            "**Criteri**:",
        ]
        for criterion in task.criteria:
            kind = "richiesto" if criterion.required else "bonus"
            lines.append(f"- `{criterion.id}` ({kind}) — {criterion.text}")
        lines += ["", "- [ ] approva", "- [ ] scarta", ""]
    return "\n".join(lines) + "\n"


def parse_review_markdown(text: str) -> dict[str, dict]:
    """Read the ticked boxes. Untouched blocks are absent from the result."""
    decisions: dict[str, dict] = {}
    for block in _BLOCK_RE.finditer(text):
        task_id = block.group("id")
        body = block.group("body")
        approve = _APPROVE_RE.search(body)
        reject = _REJECT_RE.search(body)
        approved = bool(approve and approve.group("mark").lower() == "x")
        rejected = bool(reject and reject.group("mark").lower() == "x")
        if approved and rejected:
            raise ValueError(f"{task_id}: both approva and scarta are ticked")
        if approved:
            decisions[task_id] = {"action": "approve"}
        elif rejected:
            decisions[task_id] = {"action": "reject"}
    return decisions


def apply_review(tasks: list[Task], decisions: dict[str, dict]) -> list[Task]:
    """Apply the reviewer's decisions. Unknown task ids are a hard error."""
    known = {t.id for t in tasks}
    unknown = set(decisions) - known
    if unknown:
        raise KeyError(f"decisions for unknown tasks: {sorted(unknown)}")

    result: list[Task] = []
    for task in tasks:
        decision = decisions.get(task.id)
        if decision is None:
            result.append(task)
        elif decision["action"] == "approve":
            task.curated = True
            result.append(task)
        # reject: drop
    return result
