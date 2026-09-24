"""Extract citations from a model answer.

Two kinds are recognised and both are recorded:

* identifiable  — court, number and year can be read off the text, so the
  citation can be resolved against Italgiure. Both the slash convention
  ("n. 12345/2025") and the date convention ("sentenza del 3 marzo 2025,
  n. 12345") are matched.
* narrative     — a bare appeal to case law with no identifying elements
  ("giurisprudenza consolidata"). Unresolvable by construction, but it is a
  produced citation and belongs in the GOG denominator. Narrative citations
  are never deduplicated: two separate hand-waves supporting two different
  claims are two produced citations, not one — collapsing them would shrink
  the denominator and inflate the score, rewarding the exact failure mode
  this metric exists to detect.

A narrative marker immediately followed by an identifiable citation is one
claim, not two: the marker is introducing the decision that follows. That
absorption is decided structurally: absorb only when none of the delimiters
in `_SENTENCE_BOUNDARY_RE` — sentence-terminal punctuation (`.` `;` `:` `!`
`?`), an em/en dash or a whitespace-bounded hyphen used as a clause break, an
ellipsis, a numbered-list marker (`1)`, `2)`, ...), or a newline — appears
between the end of the marker and the start of the citation (plus a
~200-character backstop against pathological input). It is not decided by a
character count and it is not decided by masking abbreviation dots.

## Why there is no abbreviation allow-list, and why one must not be re-added

Three earlier rounds tried to special-case the sentence-boundary rule with a
list of Italian legal abbreviations ("ad es.", "cfr.", "art.", "c.p.c.", ...)
so that an abbreviation's period would not be misread as a sentence end.
Each round closed its case and the next review found another token with the
same flaw: one round removed nine ambiguous tokens, and the next review then
found "ecc." still in the surviving list ("contratti, appalti, forniture,
ecc. Cass. civ. n. 5/2025 affronta un tema diverso" wrongly merged into one
citation). A pass over the rest of that list found the identical problem in
"c.c.", "cost.", "Un." and "op. cit." — "la responsabilita ex art. 2043 c.c."
ends sentences constantly in Italian pleadings.

The list was never the bug. The approach is: nearly every Italian legal
abbreviation can legitimately end a sentence, so no allow-list of them can be
made safe. The fix is to delete the abbreviation-masking machinery entirely
and keep only the plain structural rule. With no masking, a period between a
narrative marker and a following citation always separates them, so two
independent claims can never be merged into one over that delimiter.

That guarantee is bounded by the delimiter set in `_SENTENCE_BOUNDARY_RE`,
not absolute — say so plainly rather than claim more than was verified. The
parser cannot merge two independent claims separated by sentence-terminal
punctuation, an em dash (`—`), an en dash (`–`), a hyphen used as a clause
break with whitespace on both sides (` - `), an ellipsis (`…`), a
numbered-list marker (`1)`, `2)`, ...), or a newline — each of these was
checked by execution against a concrete counter-example (see the tests) and
closed. Unlike legal abbreviations, none of these characters ever occurs
inside an Italian abbreviation, so admitting them into the boundary set
carries none of the ambiguity that sank the allow-list.

That boundary set is bounded, not exhaustive, and the gap outside it is
OVER-absorption — the dangerous direction, not the accepted one. Any
separator the regex does not recognise (a bare bullet character glued
directly to the following word with no surrounding whitespace, a spaced
bullet character such as "•", a guillemet "»", a bare carriage return `\r`
with no `\n`, or any other clause break not in the list above) can still
cause two independent claims to merge into one. This is the same failure
mode the abbreviation allow-list produced — merging claims shrinks the GOG
denominator and inflates the score — narrowed by the delimiters above but
not eliminated. It is NOT the same trade-off as the under-absorption cost
described below: under-absorption is the safe direction we accept on
purpose; this residual is the dangerous direction we have not (yet) closed,
smaller than before this round but still open. Do not invent a heuristic
for a bare hyphen without surrounding whitespace to try to close it: a
hyphen between two words is far more often a compound than a clause break,
and guessing there would reopen exactly the ambiguity class that took four
rounds to remove from the abbreviation list.

This makes the parser under-absorb in return: "si veda, ad es. Cass. civ.
n. 1/2025" now counts as two citations rather than one, even though it is a
single grounded claim. That cost is real and it is not evenly distributed —
the `mcp` arm holds real decisions read off Italgiure, so it is the arm most
likely to write a narrative marker next to a genuine citation, and it takes
most of the penalty.

That cost is accepted for one reason: over-absorption merges two independent
claims into one, shrinking the GOG denominator and INFLATING the score — it
flatters the hypothesis this benchmark exists to test, and an artifact that
flatters its own hypothesis makes the result impossible for anyone to trust
without independently reproducing it against the original dataset.
Under-absorption splits one claim into two, enlarging the denominator and
DEFLATING the score — it only costs sensitivity, never credibility: it can
make the measured effect smaller than the truth, but it can never make it
look larger than the truth. Given a choice between a benchmark that might
overstate its conclusion and one that might understate it, a benchmark that
cannot be independently reproduced must take the second. Do not reintroduce
abbreviation masking, an allow-list, or any per-token exception to the
sentence-boundary check — the same review cycle that killed three previous
attempts will find the next surviving ambiguous token too.

## Known limitation (under-absorption / safe direction) — parked, not fixed

The dash and numbered-list delimiters above are one-directional: they treat
every occurrence as a clause break, but Italian legal prose also uses them
as a PAIRED aside inside a single sentence, e.g. "Secondo la giurisprudenza
costante — come pacificamente riconosciuto — Cass. civ. n. 1/2025 conferma"
(the two em dashes bracket a parenthetical, not two separate clauses), and
"Cass. civ. n. 1/2025, par. 2) del considerato in diritto" (the numbered
marker here indexes a paragraph of the cited decision, not a new list
item). Both are currently misread as boundaries and wrongly split one
grounded claim into two. This is under-absorption — the safe, accepted
direction, costing sensitivity rather than credibility — so it is recorded
here as a known limitation rather than fixed. The obvious future fix, not
yet implemented: an even number of dash occurrences inside the gap signals
a bracketed aside rather than a boundary (a single dash starts a clause
break; a matched pair closes it again before the citation), and a
numbered-list marker immediately followed by a lowercase word ("par.",
"considerato", ...) rather than a capitalised sentence start is more likely
a paragraph reference than a list item.
"""

from __future__ import annotations

import re

from benchmarks.legalita.schema import Citation

_SECTION = r"(?:Sez(?:ione)?\.?\s*)?(?P<section>Un\.?|[IVX]{1,4}|lav\.?|trib\.?|[1-7])\.?"

_MONTHS = (
    r"gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
    r"settembre|ottobre|novembre|dicembre"
)

# Two mutually exclusive forms of an identifiable citation:
#   1. date form:  "sentenza/ordinanza del <day> <month> <year>, n. <number>"
#   2. slash form: "n. <number>/<year>"
# Distinct group names per branch (Python's `re` forbids reusing a group
# name within one pattern) — `parse_citation` picks whichever pair matched.
CITATION_RE = re.compile(
    "".join(
        [
            r"Cass(?:azione|\.)?\s*",
            r"(?P<branch>civ(?:ile)?|pen(?:ale)?)?\.?\s*,?\s*",
            r"(?:",
            _SECTION,
            r"\s*,?\s*)?",
            r"(?:",
            r"(?:sent(?:enza)?|ord(?:inanza)?)\.?\s+del\s+",
            r"(?P<day>\d{1,2})\s+(?P<month>",
            _MONTHS,
            r")\s+(?P<date_year>(?:19|20)\d{2})\s*,?\s*",
            r"n\.?\s*(?P<date_number>\d{1,6})",
            r"|",
            r"(?:(?:sent(?:enza)?|ord(?:inanza)?)\.?\s*)?",
            r"n\.?\s*(?P<number>\d{1,6})\s*/\s*(?P<year>(?:19|20)\d{2})",
            r")",
        ]
    ),
    re.IGNORECASE,
)

NARRATIVE_MARKERS: tuple[str, ...] = (
    r"giurisprudenza\s+(?:consolidata|costante|pacifica|maggioritaria)",
    r"orientamento\s+(?:consolidato|costante|pacifico|maggioritario)",
    r"la\s+(?:Suprema\s+)?Corte\s+ha\s+(?:pi[uù]\s+volte|costantemente|ripetutamente)",
    r"secondo\s+la\s+(?:costante\s+)?giurisprudenza",
    r"[eè]\s+principio\s+(?:consolidato|pacifico)",
)

NARRATIVE_RE = re.compile("|".join(NARRATIVE_MARKERS), re.IGNORECASE)

# A narrative marker is absorbed into the identifiable citation that follows
# it when the two live in the same clause: none of the delimiters below
# between the end of the marker and the start of the citation. The character
# ceiling is only a backstop against pathological input (a citation
# appearing hundreds of characters later can never be "the same clause"
# regardless of punctuation); it is not what decides absorption.
_ABSORB_CEILING = 200

# Delimiters that end a clause and therefore block absorption:
#   [.;:!?]   sentence-terminal punctuation
#   \n        newline
#   —  –      em dash / en dash used as a clause break ("... — tuttavia ...")
#   …         ellipsis
#   \s-\s     a hyphen used as a dash, with whitespace on both sides (not a
#             hyphen glued inside a compound word, which has no surrounding
#             whitespace)
#   \d+\)     a numbered-list marker ("1)", "2)", ...)
# Unlike legal abbreviations, none of these characters ever occurs inside an
# Italian abbreviation, so admitting them here carries none of the ambiguity
# that sank the abbreviation allow-list (see the module docstring). This set
# is not exhaustive: a bare bullet glued directly to the next word (no
# surrounding whitespace) or no delimiter at all can still be absorbed
# wrongly — that residual gap is documented in the module docstring as an
# accepted, known limit, not hidden behind an "impossible by construction"
# claim. Do not add a bare-hyphen (no whitespace) rule to close it: a hyphen
# between two words is far more often a compound than a clause break.
_SENTENCE_BOUNDARY_RE = re.compile(r"[.;:!?…—–]|\n|\s-\s|\d+\)")


def parse_citation(raw: str) -> dict | None:
    """Return the structured form of a citation, or None if unidentifiable."""
    match = CITATION_RE.search(raw)
    if not match:
        return None
    branch = (match.group("branch") or "").lower()
    if branch.startswith("pen"):
        court = "Cass. pen."
    elif branch.startswith("civ"):
        court = "Cass. civ."
    else:
        court = "Cass."
    section = match.group("section")
    if section:
        section = section.strip().rstrip(".")
        if section.lower().startswith("un"):
            section = "Un."
        elif section.lower().startswith("lav"):
            section = "lav."
        elif section.lower().startswith("trib"):
            section = "trib."
    if match.group("number") is not None:
        number = int(match.group("number"))
        year = int(match.group("year"))
    else:
        number = int(match.group("date_number"))
        year = int(match.group("date_year"))
    return {
        "court": court,
        "section": section,
        "number": number,
        "year": year,
    }


def _is_absorbed(text: str, marker_end: int, named_start: int) -> bool:
    """Whether a named citation at `named_start` absorbs the marker ending at `marker_end`."""
    if not (0 <= named_start - marker_end <= _ABSORB_CEILING):
        return False
    gap = text[marker_end:named_start]
    return not _SENTENCE_BOUNDARY_RE.search(gap)


def extract_citations(text: str, task_id: str, arm: str) -> list[Citation]:
    """Return every citation the answer produces, in order of appearance."""
    if not text:
        return []

    named = [
        (m.start(), m.group(0), parse_citation(m.group(0)))
        for m in CITATION_RE.finditer(text)
    ]
    narrative_spans = [
        (m.start(), m.end(), m.group(0)) for m in NARRATIVE_RE.finditer(text)
    ]

    named_starts = [start for start, _, _ in named]
    kept_narrative = [
        (start, raw)
        for start, end, raw in narrative_spans
        if not any(_is_absorbed(text, end, ns) for ns in named_starts)
    ]

    entries: list[tuple[int, str, dict | None]] = [
        *named,
        *[(start, raw, None) for start, raw in kept_narrative],
    ]
    entries.sort(key=lambda item: item[0])

    citations: list[Citation] = []
    seen: set[str] = set()
    for _, raw, parsed in entries:
        if parsed is None:
            # Narrative citations are never deduplicated: GOG divides
            # issue-covering citations by citations produced, so collapsing
            # repeated hand-waves would shrink the denominator and inflate
            # the score -- rewarding exactly the ungrounded, unidentifiable
            # hand-waving this metric exists to punish. Each matched span is
            # its own citation regardless of whether an identical one was
            # already produced elsewhere in the answer.
            citations.append(
                Citation(
                    task_id=task_id,
                    arm=arm,
                    index=len(citations),
                    raw=raw.strip(),
                    parsed=None,
                    identifiable=False,
                )
            )
            continue
        key = f"{parsed['court']}|{parsed['section']}|{parsed['number']}|{parsed['year']}"
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                task_id=task_id,
                arm=arm,
                index=len(citations),
                raw=raw.strip(),
                parsed=parsed,
                identifiable=True,
            )
        )
    return citations
