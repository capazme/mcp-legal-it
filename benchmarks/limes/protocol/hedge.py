"""Orientation detection: the mechanical core of the U dimension (DESIGN §4.1,
"Open texture / revirement").

On `revirement`/`active_conflict` items the *correct behaviour* is to signal
the conflict, not to choose with confidence; on settled items the correct
behaviour is a confident application. `coppie gemelle` (§4.2) make this
measurable structurally: the pair diverges in the direction the law
requires, and the divergence is observable with declared lexicons rather
than with a judge.

Three orientations, from the same family of observables:

- `affermare`: takes a position, applies the settled rule;
- `segnalare`: flags uncertainty / pending conflict (hedges);
- `negare`: refuses the proposed move (e.g. analogy where art. 14 Preleggi
  forbids it).

The detector counts declared lexicon hits (accent-tolerant, like the
citation markers) and returns the dominant orientation; ties and zero-hit
answers are `ambiguo` and always count as *not matching* the expected
orientation — fail-closed in both directions: silence is never scored as
assertiveness, assertiveness is never scored as prudence.

The lexicons are deliberately small and specific; widening them is a
protocol change (protocol_sha moves) and must be pre-registered, not
patched after seeing answers.
"""

from __future__ import annotations

import re

from benchmarks.limes.protocol.citations import normalize

ORIENTATIONS = ("affermare", "segnalare", "negare")

# Lexicons are matched against `normalize()` output: lowercase and WITHOUT
# diacritics — patterns must be written accent-free ("e pacifico", not
# "è pacifico"), otherwise they can never fire.
_AFFIRM = [
    r"\be\s+pacific[oa]",
    r"orientamento\s+(?:ormai\s+)?(?:costante|consolidato|fermo)",
    r"giurisprudenza\s+(?:costante|consolidata)",
    r"indubbiamente",
    r"senz(?:a|')\s+(?:alcun\s+)?(?:dubbio|incertezza)",
    r"si\s+applica\s+(?:pertanto|dunque)?\s*(?:la|il|l')",
    r"\bva\s+(?:dis)?applicat[oa]",
    r"\bdeve\s+(?:dis)?applicar[ea]",
]

_HEDGE = [
    r"non\s+(?:\be\b|\be\s+piu\b)\s+pacific[oa]",
    r"contrasto(?:\s+di\s+(?:giurisprudenza|orientamenti))?",
    r"contrast(?:ante|atorio)",
    r"sezioni\s+unite",
    r"ss\.?\s*uu\.?",
    r"revirement",
    r"cambiamento\s+di\s+orientamento",
    r"in\s+corso\s+di\s+(?:decisione|riexame)",
    r"pendent[ei]\s+(?:davanti\s+)?(?:alle\s+)?sezioni\s+unite",
    r"non\s+uniform[ei]",
    r"incertezz[ae]",
    # Word boundaries are load-bearing: without them "dubbia" matches
    # inside "indubbiamente" and "prudenza" inside "giurisprudenza",
    # so a confident answer citing "giurisprudenza consolidata" would tie
    # and be scored ambiguo.
    r"\bdubbi[oa]\b",
    r"riserv(?:a|atezza|ato)",
    r"\bprudenz[ae]\b",
]

_DENY = [
    r"non\s+(?:\be\b|\bsono\b)\s+(?:ammess[oa]|consentit[oa]|possibile)",
    r"\bvietat[oa]",
    r"non\s+applicabile",
    r"non\s+(?:si\s+)?puo\s+(?:dis)?applicar[ea]",
    r"non\s+\be\s+possibile\s+(?:dis)?applicare",
    r"espressamente\s+esclus[oa]",
    r"in\s+malam\s+partem",
]

_AFFIRM_RE = [re.compile(p) for p in _AFFIRM]
_HEDGE_RE = [re.compile(p) for p in _HEDGE]
_DENY_RE = [re.compile(p) for p in _DENY]


# Explicit closed verdict (protocol v1). Wave-1 twin items ask the model to
# close with one line `ESITO: <token>`; when present, that line IS the
# observable — a declared conclusion is a far more valid measure of the
# orientation than lexicon counts over free prose. Tokens map onto the
# three orientations. Accent-free (matched after `normalize`).
_ESITO_TOKENS = {
    "si": "affermare",
    "no": "negare",
    "pacifico": "affermare",
    "controverso": "segnalare",
}
# `normalize` collapses newlines, so the verdict is anchored on the word
# `esito`, not on a line start; markdown emphasis around it is tolerated.
_ESITO_RE = re.compile(r"\besito\W{0,6}:\W{0,6}(si|no|pacifico|controverso)\b")


def explicit_verdict(answer: str) -> str | None:
    """The orientation declared by `ESITO:` lines, `ambiguo` when the answer
    declares contradictory verdicts, None when it declares none."""
    found = {_ESITO_TOKENS[m.group(1)] for m in _ESITO_RE.finditer(normalize(answer))}
    if not found:
        return None
    if len(found) > 1:
        return "ambiguo"  # fail-closed: two different verdicts are no verdict
    return found.pop()


def detect_orientation(answer: str) -> str:
    """Dominant orientation of an answer, or `ambiguo` (fail-closed).

    An explicit `ESITO:` verdict (protocol v1) takes precedence over the
    lexicon; the lexicon remains the observable for items that do not ask
    for a closed verdict (wave 0)."""
    declared = explicit_verdict(answer)
    if declared is not None:
        return declared
    text = normalize(answer)
    scores = {
        "affermare": sum(1 for p in _AFFIRM_RE if p.search(text)),
        "segnalare": sum(1 for p in _HEDGE_RE if p.search(text)),
        "negare": sum(1 for p in _DENY_RE if p.search(text)),
    }
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "ambiguo"
    # Tie between families means the answer both asserts and signals (or
    # both refuses and asserts): undecided, never a pass.
    max_count = scores[best]
    if sum(1 for v in scores.values() if v == max_count) > 1:
        return "ambiguo"
    return best


def orientation_matches(answer: str, expected: str) -> bool:
    if expected not in ORIENTATIONS:
        raise ValueError(f"orientation_matches: unknown expected {expected!r}")
    return detect_orientation(answer) == expected
