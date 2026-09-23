"""Citation markers, extraction and provenance fidelity (the P dimension).

A marker is a *declared* observable: a named regular expression, fixed in the
protocol (it is versioned under `protocol/`, so `protocol_sha` pins it).
Scorers never cite sources by ad-hoc regexes — a marker id on an item refers
to an entry of this registry, and the bank validator refuses unknown ids.

Fidelity (DESIGN §4.1, "Provenienza"): a citation is *faithful* when the
tool actually received what the answer claims to cite — checked against the
full transcript the runner persisted, not against the world. A citation is
*identifiable* when its canonical elements (court, section, number, year; or
norm + article + code) are present. Identifiable-but-unfaithful citations
are exactly the hallucination mode that survives "I saw it somewhere".

Fail-closed semantics:
- no citations in the answer  -> nothing to be faithful about; fidelity is
  defined (0.0), identifiability 0.0 — refusing to cite is a failure;
- tools present but no tool results in the transcript -> fidelity is
  *undefined* (None): the run is broken (a tool config that produces no
  results must never be scored as "everything unfaithful");
- tools absent (bare)         -> fidelity None (n/d), never 0.0.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Pattern


def _article_marker(number: int) -> Pattern[str]:
    """A marker for one specific article of a codice (code suffix optional)."""
    return re.compile(
        rf"art(?:icolo)?\.?\s*{number}\b", re.IGNORECASE
    )

# Declared markers. Ids are referenced by bank items (`expected_markers`,
# `disqualifiers`) and cross-checked by the bank validator.
MARKERS: dict[str, Pattern[str]] = {
    # Cassazione with full identifying elements (sezione optional, number+year
    # required — a bare "Cass." mention is not an identifiable citation).
    "cass": re.compile(
        r"Cass\.\s*(?:sez\.?\s*[\wIVX]+)?,?\s*n\.\s*\d{1,6}\s*[/\\]\s*\d{4}",
        re.IGNORECASE,
    ),
    "cortecost": re.compile(
        r"Corte\s+cost\.,?\s*(?:n\.\s*)?\d{1,3}\s*[/\\]\s*\d{4}", re.IGNORECASE
    ),
    "cgue": re.compile(
        r"CGUE(?:\s+C-\d{1,4}/\d{2,4})?"
        r"|Corte\s+di\s+giustizia(?:\s+dell'?Unione\s+europea)?(?:\s+C-\d{1,4}/\d{2,4})?"
        r"|C-\d{1,4}/\d{2,4}",
        re.IGNORECASE,
    ),
    # NOTA (pre-registrata): "Sezioni Unite" / "SS.UU." resta un marker
    # ATTESO valido (QAS-04 chiede di indicare l'organo competente) ma NON
    # è una CITAZIONE: il riferimento all'organo ("le Sezioni Unite hanno
    # affermato") non identifica un provvedimento, e sui revirement
    # l'hedge è il comportamento corretto che la dimensione U già premia —
    # trattarlo come citazione opaca punirebbe due volte la stessa
    # risposta. L'evento specifico ("Cass., SS.UU., n. .../...") è coperto
    # dal marker `cass`.
    "ssuu": re.compile(r"Sezioni\s+Unite|SS\.?\s*UU\.?", re.IGNORECASE),
    # Disposizioni sulla legge in generale, whole set or specific articles.
    "preleggi": re.compile(
        r"(?:art(?:icolo)?\.?\s*\d{1,2}\b[^.;]{0,60}?"
        r"(?:disposizioni\s+sulla\s+legge\s+in\s+generale|disp\.?\s*prel\.?|preleggi)"
        r"|disposizioni\s+sulla\s+legge\s+in\s+generale)",
        re.IGNORECASE,
    ),
    "preleggi4": re.compile(
        r"art(?:icolo)?\.?\s*4\b[^.;]{0,60}?"
        r"(?:disposizioni\s+sulla\s+legge\s+in\s+generale|disp\.?\s*prel\.?|preleggi)",
        re.IGNORECASE,
    ),
    "preleggi12": re.compile(
        r"art(?:icolo)?\.?\s*12(?:-bis)?\b[^.;]{0,60}?"
        r"(?:disposizioni\s+sulla\s+legge\s+in\s+generale|disp\.?\s*prel\.?|preleggi)",
        re.IGNORECASE,
    ),
    "preleggi14": re.compile(
        r"art(?:icolo)?\.?\s*14\b[^.;]{0,60}?"
        r"(?:disposizioni\s+sulla\s+legge\s+in\s+generale|disp\.?\s*prel\.?|preleggi)",
        re.IGNORECASE,
    ),
    "costituzione": re.compile(
        r"art(?:icolo)?\.?\s*\d{1,3}\s+(?:della\s+)?(?:Costituzione|Cost\.)",
        re.IGNORECASE,
    ),
    # Codici and primary norms in general.
    "norma": re.compile(
        r"art(?:icolo)?\.?\s*\d{1,4}(?:-bis|-ter)?\s+(?:c\.c\.|c\.p\.c\.|c\.p\.|c\.p\.p\.)",
        re.IGNORECASE,
    ),
    # Article-specific markers referenced by the bank: the expected citation
    # of a `provenienza` item, or the near-miss a disqualifier forbids.
    # Optional code suffix: "art. 1176 c.c." and "art. 1176" both hit.
    "cc-1176": _article_marker(1176),
    "cc-1175": _article_marker(1175),
    "cc-2697": _article_marker(2697),
    "cc-2698": _article_marker(2698),
    "cc-2943": _article_marker(2943),
    "preleggi8": re.compile(
        r"art(?:icolo)?\.?\s*8\b[^.;]{0,60}?"
        r"(?:disposizioni\s+sulla\s+legge\s+in\s+generale|disp\.?\s*prel\.?|preleggi)",
        re.IGNORECASE,
    ),
}

# Markers that name an ORGAN or a procedural state, not a source claim.
# They are legitimate mechanical expectations (`has_marker`) but are never
# scored as citations (see the NOTA above the registry).
_ORGAN_MENTIONS = {"ssuu"}

# Citation types for which *fidelity keys* are extractable: the tokens that
# must appear in the tool results for the citation to count as faithful.
# Article-specific markers are identifiable citations (norm + article [+ code]
# — DESIGN §4.1): their key is the article number, so "art. 1176 c.c." counts
# as identifiable and its fidelity is checkable in the transcript.
_FIDELITY_KEYS: dict[str, Pattern[str]] = {
    "cass": re.compile(r"Cass\.\s*(?:sez\.?\s*[\wIVX]+)?,?\s*n\.\s*(\d{1,6})\s*[/\\]\s*(\d{4})", re.IGNORECASE),
    "cortecost": re.compile(r"Corte\s+cost\.,?\s*(?:n\.\s*)?(\d{1,3})\s*[/\\]\s*(\d{4})", re.IGNORECASE),
    "cgue": re.compile(r"(C-\d{1,4}/\d{2,4})", re.IGNORECASE),
    "norma": re.compile(r"art(?:icolo)?\.?\s*(\d{1,4}(?:-bis|-ter)?)\s+(c\.[cp]\.|c\.p\.p\.)", re.IGNORECASE),
    "costituzione": re.compile(r"art(?:icolo)?\.?\s*(\d{1,3})\s+(?:della\s+)?(?:Costituzione|Cost\.)", re.IGNORECASE),
    "cc-1176": re.compile(r"art(?:icolo)?\.?\s*(1176)", re.IGNORECASE),
    "cc-1175": re.compile(r"art(?:icolo)?\.?\s*(1175)", re.IGNORECASE),
    "cc-2697": re.compile(r"art(?:icolo)?\.?\s*(2697)", re.IGNORECASE),
    "cc-2698": re.compile(r"art(?:icolo)?\.?\s*(2698)", re.IGNORECASE),
    "cc-2943": re.compile(r"art(?:icolo)?\.?\s*(2943)", re.IGNORECASE),
    "preleggi4": re.compile(r"art(?:icolo)?\.?\s*(4)\b", re.IGNORECASE),
    "preleggi8": re.compile(r"art(?:icolo)?\.?\s*(8)\b", re.IGNORECASE),
    "preleggi12": re.compile(r"art(?:icolo)?\.?\s*(12)\b", re.IGNORECASE),
    "preleggi14": re.compile(r"art(?:icolo)?\.?\s*(14)\b", re.IGNORECASE),
}


def normalize(text: str) -> str:
    """Lowercase, strip diacritics and collapse whitespace (house style:
    accent-tolerant matching — `n. 12345` and `n. 12345/2022` must not miss
    because of a stray accent or double space)."""
    decomposed = unicodedata.normalize("NFKD", text)
    without = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without.lower())


@dataclass(frozen=True)
class Citation:
    marker: str
    raw: str


def extract_citations(answer: str) -> list[Citation]:
    """Extract declared-marker citations from an answer, in order of appearance.

    Overlapping spans are deduplicated longest-first: generic markers
    (`norma`, `costituzione`) also match text covered by article-specific
    ones (`cc-1176`), and counting the same citation twice would overstate
    both the citation list and the identifiability denominator.

    Organ mentions (`ssuu`) are excluded from the citation set (see the
    NOTA above the registry): they remain valid as mechanical EXPECTATIONS
    (`has_marker`) but are not claims about a source, so they never enter
    the identifiability or fidelity observables.
    """
    candidates: list[tuple[int, int, str, str]] = []
    for marker, pattern in MARKERS.items():
        if marker in _ORGAN_MENTIONS:
            continue
        for match in pattern.finditer(answer):
            candidates.append((*match.span(), marker, match.group(0)))

    def _has_keys(marker: str, raw: str) -> bool:
        key_pattern = _FIDELITY_KEYS.get(marker)
        return key_pattern is not None and key_pattern.search(raw) is not None

    # Longest span first within the same start; at equal span the marker
    # whose identifying keys extract (the specific one) wins over the
    # generic alias — `preleggi4` must not be shadowed by `preleggi`.
    candidates.sort(
        key=lambda c: (c[0], -(c[1] - c[0]), 0 if _has_keys(c[2], c[3]) else 1)
    )
    accepted: list[tuple[int, int, Citation]] = []
    for start, end, marker, raw in candidates:
        if any(start < a_end and a_start < end for a_start, a_end, _ in accepted):
            continue
        accepted.append((start, end, Citation(marker=marker, raw=raw)))
    accepted.sort(key=lambda a: a[0])
    return [citation for _, _, citation in accepted]


def has_marker(answer: str, marker: str) -> bool:
    """Whether the answer contains the declared marker (accent-tolerant)."""
    return MARKERS[marker].search(normalize(answer)) is not None


def fidelity_keys(citation: Citation) -> list[str]:
    """The identifying tokens of a citation, for transcript matching."""
    pattern = _FIDELITY_KEYS.get(citation.marker)
    if pattern is None:
        return []
    match = pattern.search(citation.raw)
    if match is None:
        return []
    return [group for group in match.groups() if group]


def citation_fidelity(cited: list[Citation], tool_text: str | None) -> float | None:
    """Share of cited citations whose identifying keys appear in the tool text.

    None (n/d) when there is no tool text at all — that includes the bare
    surface (nothing to be faithful to) and broken tool runs (nothing
    received, which must not read as "everything unfaithful"). Zero
    citations means nothing cited: fidelity is defined at 0.0 because an
    uncited answer fails provenance outright (house GOG semantics).
    """
    if tool_text is None:
        return None
    if not cited:
        return 0.0
    haystack = normalize(tool_text)
    faithful = 0
    for citation in cited:
        keys = fidelity_keys(citation)
        if keys and all(normalize(key) in haystack for key in keys):
            faithful += 1
    return faithful / len(cited)


def provenance_answer(answer: str, tool_text: str | None) -> dict:
    """The P-dimension observables for one answer."""
    cited = extract_citations(answer)
    identifiable = [c for c in cited if fidelity_keys(c)]
    return {
        "citations": [c.raw for c in cited],
        "identifiable": len(identifiable),
        "identifiability": (len(identifiable) / len(cited)) if cited else 0.0,
        "fidelity": citation_fidelity(cited, tool_text),
    }
