"""The mechanical Q scorer (DESIGN §4.1, strato Q).

Pure functions: a Q item carries the true value and a pre-registered
tolerance; the scorer parses the answer's numbers or dates with Italian
conventions and reports a pass/fail plus everything needed to audit the
verdict (what was extracted, what was expected, which candidate matched).

Parsing rules, declared here because they are part of protocol_sha:
- numbers use the Italian format (`1.234,56`); thousands dots without a
  decimal comma (`1.234`) are ambiguous with `1.234` meaning 1.234 — treated
  as thousands when the group is exactly three digits, else plain integer;
- a dot followed by 1–2 digits (`493.15`) has no valid Italian reading, so
  it is read as an Anglo decimal: international models in the matrix answer
  in their own convention and the C construct must not grade punctuation;
- dates accept `gg/mm/aaaa`, `gg-mm-aaaa` and `gg mese aaaa` (Italian month
  names, abbreviations included);
- a date answer never matches a bare number and vice versa (different
  `q_answer.kind`).
"""

from __future__ import annotations

import re
from datetime import date

from benchmarks.limes.bank.schema.item import Item, Toleranza
from benchmarks.limes.protocol.rules import Protocol

_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
    "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
    "novembre": 11, "dicembre": 12,
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7,
    "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
}

# Numbers in Italian format. The negative lookbehind/lookahead keep a match
# from starting or ending inside a longer numeric token (e.g. the `56` of
# `1.234,56` or a year inside a date).
_NUMBER_RE = re.compile(
    r"(?<![\d.,])("
    r"\d{1,3}(?:\.\d{3})+,\d{1,2}"   # 24.000,00
    r"|\d+,\d{1,2}"                   # 493,15
    r"|\d+\.\d{1,2}"                  # 493.15 (Anglo decimal: no Italian reading)
    r"|\d{1,3}(?:\.\d{3})+"          # 1.234 (thousands)
    r"|\d+"                            # 42
    r")(?!\d)(?!,\d)"
)
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")
_MONTH_DATE_RE = re.compile(
    r"\b(\d{1,2})(?:°)?\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)


def parse_numbers(text: str) -> list[float]:
    """Extract numeric candidates from Italian-formatted text."""
    out: list[float] = []
    for match in _NUMBER_RE.finditer(text):
        token = match.group(1)
        if "," in token:
            token = token.replace(".", "").replace(",", ".")
            out.append(float(token))
        elif re.fullmatch(r"\d+\.\d{1,2}", token):
            # Anglo decimal — the dot is a decimal point, never thousands.
            out.append(float(token))
        else:
            # `1.234` with exactly-three-digit groups is thousands; a plain
            # `250` or a dotless `12345` is an integer.
            if "." in token and all(
                len(part) == 3 for part in token.split(".")[1:]
            ):
                token = token.replace(".", "")
            out.append(float(token))
    return out


def parse_dates(text: str) -> list[date]:
    """Extract calendar dates (numeric and Italian month-name formats)."""
    out: list[date] = []
    for match in _NUMERIC_DATE_RE.finditer(text):
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            out.append(date(year, month, day))
        except ValueError:
            continue
    for match in _MONTH_DATE_RE.finditer(text):
        day, month, year = (
            int(match.group(1)),
            _MONTHS[match.group(2).lower()],
            int(match.group(3)),
        )
        try:
            out.append(date(year, month, day))
        except ValueError:
            continue
    return out


def parse_expected_date(value: str) -> date:
    day, month, year = value.split("/")
    return date(int(year), int(month), int(day))


def score_q(item: Item, answer: str, protocol: Protocol | None = None) -> dict:
    """Score a Q item mechanically.

    Returns a verdict dict — never raises on content: an unparsable answer
    is a legitimate fail (the model was asked for a number, not for prose).
    Raises only on schema misuse (scoring an S item).

    An item without its own tolerance inherits the protocol's
    pre-registered default (never an ad-hoc one chosen after seeing the
    answer).
    """
    if item.layer != "Q" or item.q_answer is None:
        raise ValueError(f"score_q: {item.id} is not a Q item")
    expected = item.q_answer
    tolerance = expected.tolerance
    if tolerance is None and protocol is not None:
        tolerance = Toleranza(**protocol.default_tolerance())

    if expected.kind == "data":
        want = parse_expected_date(str(expected.value))
        got = parse_dates(answer)
        matched = any(d == want for d in got)
        return {
            "item_id": item.id,
            "construct": item.construct,
            "kind": "data",
            "expected": expected.value,
            "extracted": [d.strftime("%d/%m/%Y") for d in got],
            "matched": matched,
        }

    want = float(expected.value)
    candidates = parse_numbers(answer)
    best = min(candidates, key=lambda c: abs(c - want)) if candidates else None
    if best is None:
        matched = False
    elif tolerance is not None:
        matched = tolerance.allows(want, best)
    else:
        matched = best == want
    return {
        "item_id": item.id,
        "construct": item.construct,
        "kind": "numero",
        "expected": want,
        "extracted": candidates,
        "best": best,
        "matched": matched,
    }
