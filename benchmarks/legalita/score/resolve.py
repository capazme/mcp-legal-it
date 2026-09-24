"""Resolve extracted citations against the live sources.

Reuses the shipped `verifica_citazioni` tool rather than reimplementing
lookup, so the benchmark measures the same resolution logic a user gets.
Resolution is fail-closed: anything the report does not positively confirm
is `resolved = False`.

Marker vocabulary is taken verbatim from `verifica_citazioni`'s own
docstring in `src/tools/legal_citations.py` (not guessed):

  - "verificata"           — source exists and metadata match. The ONLY
    verdict that may set resolved=True.
  - "inesistente"          — decision not in the archives, or a different
    decision was returned.
  - "non trovata"          — act/article not found.
  - "metadati discordanti" — source exists but section/comma/lettera does
    not match what was cited. Identity is not confirmed, so this is
    resolved=False even though the source itself is real.
  - "non verificabile"     — pre-2020 decision, outside the Italgiure
    archive.
  - "non verificata"       — source temporarily unreachable.
  - "Non interpretabile"   — reference format not recognised.

CRITICAL substring trap: "non verificata" (negative) CONTAINS "verificata"
(positive) as a substring. `_MISSING_MARKERS` MUST be checked before
`_FOUND_MARKERS`, or every "source unreachable" verdict silently reads as a
positive confirmation — the single worst bug this module could have.
`test_non_verificata_does_not_falsely_match_the_verificata_marker` pins it.
"""

from __future__ import annotations

from benchmarks.legalita.schema import Citation

_FOUND_MARKERS = ("verificata",)
_MISSING_MARKERS = (
    "inesistente",
    "non trovata",
    "metadati discordanti",
    "non verificabile",
    "non verificata",
    "non interpretabile",
)


def format_for_verification(citations: list[Citation]) -> str:
    """One identifiable citation per line, as verifica_citazioni expects.

    The literal "sez." token is required, not decorative: `_USER_SEZIONE` in
    `src/tools/legal_citations.py` only recognises a section when it is
    preceded by "sez"/"sezione"/"sez." — omitting it (as an earlier draft of
    this f-string did, matching the tool's own docstring example "Cass. sez.
    III n. ...") silently drops the section from the request, which skips
    the metadata cross-check entirely rather than failing loudly. Confirmed
    against the live tool: "Cass. civ. sez. II n. 12345/2024" resolved with
    "Sezione citata (2) diversa dalla sezione effettiva (L)" — the section
    was correctly parsed and compared.
    """
    lines = [
        f"Cass. sez. {c.parsed['section']} n. {c.parsed['number']}/{c.parsed['year']}"
        for c in citations
        if c.identifiable and c.parsed
    ]
    return "\n".join(lines)


def apply_resolution(citations: list[Citation], report: str) -> list[Citation]:
    """Read the verification report back onto the citations."""
    lowered = report.lower()
    for citation in citations:
        if not citation.identifiable or not citation.parsed:
            citation.resolved = False
            citation.resolution_note = "unidentifiable: no court/number/year"
            continue

        needle = f"{citation.parsed['number']}/{citation.parsed['year']}"
        line = next(
            (ln for ln in report.splitlines() if needle in ln),
            "",
        )
        line_lower = line.lower()
        if any(marker in line_lower for marker in _MISSING_MARKERS):
            citation.resolved = False
            citation.resolution_note = line.strip()
        elif any(marker in line_lower for marker in _FOUND_MARKERS):
            citation.resolved = True
            citation.resolution_note = line.strip()
        else:
            citation.resolved = False
            citation.resolution_note = (
                f"no verdict for {needle} in verification report"
                if needle not in lowered
                else line.strip() or f"ambiguous verdict for {needle}"
            )
    return citations


async def resolve_citations(citations: list[Citation]) -> list[Citation]:
    """Live: send the identifiable citations to verifica_citazioni."""
    from src.tools.legal_citations import verifica_citazioni

    payload = format_for_verification(citations)
    if not payload:
        return apply_resolution(citations, report="")

    fn = getattr(verifica_citazioni, "fn", verifica_citazioni)
    report = await fn(citazioni=payload, archivio="tutti")
    return apply_resolution(citations, report=report)
