"""Draw the seed decisions for the gold set.

Sampling is by ENUMERATION, never by relevance. The Solr query is `*:*`
sorted by deposit date; the draw is a fixed-seed random pick over the
enumerated candidates. This is the mitigation for the contamination risk in
spec 2.1: if we selected decisions by searching for them, we would pick the
ones Italgiure surfaces well and hand the MCP arm a rigged win.

Never add a query string to this module.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import date, datetime

from src.lib.italgiure.client import get_kind_filter

WINDOW_START = date(2025, 1, 7)
WINDOW_END = date(2025, 5, 30)

DOMAIN_QUOTAS: dict[str, int] = {"civil": 13, "labour": 8, "tax": 9}

# Discovered live on 2026-07-27 against the 2025 civil corpus (35,009 docs).
# `materia` is NOT usable here: its values are stemmed keyword tokens
# (accertament, tribut, irpef, responsabilit) that overlap and do not
# partition the corpus. `szdec` is the section code and does:
#   5 (13,212) -> tax, L (6,395) -> labour, {1,2,3} (14,902) -> civil.
# `U` (Sezioni Unite, 500) is excluded on purpose: those decisions resolve
# conflicts between sections, so they are precisely the revirement /
# active_conflict material, and sampling them into one domain would skew
# that domain's issue-status mix toward the hardest cases.
DOMAIN_FILTERS: dict[str, list[str]] = {
    "civil": ["1", "2", "3"],
    "labour": ["L"],
    "tax": ["5"],
}

_ARCHIVIO = "civile"

_DATE_PATTERNS = (
    ("%Y%m%d", re.compile(r"^\d{8}$")),
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{2}-\d{2}")),
    ("%d/%m/%Y", re.compile(r"^\d{2}/\d{2}/\d{4}$")),
)


@dataclass(frozen=True)
class SeedDecision:
    doc_id: str
    number: int
    year: int
    deposited: date
    section: str
    materia: str
    dispositivo: str


def _scalar(value: object) -> str:
    """Normalise a Solr field to a plain string.

    Some fields come back multi-valued (observed live: `datdep=['20251231']`)
    while others come back as plain scalars (observed live: `numdec='34933'`,
    `anno='2025'`) — the shape is not uniform across fields, so every field
    read from a raw Solr document must go through this helper rather than
    assuming either shape.

    When a field is a list, only the first element is used. This is a
    deliberate choice, not an arbitrary one: a Cassazione decision has
    exactly one deposit date, one number, and one section, so a
    multi-valued field here is a Solr storage artefact, not a real
    multiplicity — there is no second value to reconcile.
    """
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value) if value is not None else ""


def decision_from_doc(doc: dict) -> SeedDecision | None:
    """Build a `SeedDecision` from a raw Solr document.

    Returns None when the deposit date does not parse, or when a numeric
    field (`numdec`, `anno`) is missing or non-numeric — a malformed
    document must be dropped, not allowed to abort the whole enumeration.
    """
    deposited = parse_datdep(doc.get("datdep"))
    if deposited is None:
        return None
    try:
        return SeedDecision(
            doc_id=_scalar(doc.get("id")),
            number=int(_scalar(doc.get("numdec"))),
            year=int(_scalar(doc.get("anno"))),
            deposited=deposited,
            section=_scalar(doc.get("szdec")),
            materia=_scalar(doc.get("materia")),
            dispositivo=_scalar(doc.get("ocrdis")),
        )
    except (TypeError, ValueError):
        return None


def parse_datdep(raw: object) -> date | None:
    """Parse the deposit-date field, whatever shape Solr hands back.

    Normalises internally via `_scalar`, so it is safe to call directly
    with either a scalar string or a multi-valued list — the interface
    the brief exposes publicly must not depend on the caller respecting an
    unenforced contract.
    """
    text = _scalar(raw).strip()
    if not text:
        return None
    for fmt, pattern in _DATE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(0), fmt).date()
        except ValueError:
            continue
    return None


def in_window(d: date) -> bool:
    """True when the decision falls in the paper's temporal window.

    Redundant against the `datdep` range filter already applied in
    `build_enumeration_params` — kept anyway as the assertion that catches
    the day the field shape or the index's range-filter behaviour changes
    under us. Do not remove this as dead code.
    """
    return WINDOW_START <= d <= WINDOW_END


def build_enumeration_params(
    sezioni: list[str],
    rows: int,
    start: int,
) -> dict:
    """Solr params that enumerate, rather than rank.

    `datdep` is a zero-padded `YYYYMMDD` string, so the window is filtered
    directly in Solr via a lexical range query — enumerating from the far
    end of ~15,000 documents per domain (the default `pd desc` sort puts
    31 December first) would take dozens of requests against a slow
    government endpoint for data Solr can filter server-side. Sort is
    `pd asc` so the enumeration starts at the window's beginning. The
    range bounds are derived from `WINDOW_START`/`WINDOW_END` so the two
    can never drift apart. `in_window` remains as a client-side check —
    see its docstring.

    The sort carries `id asc` as a tie-breaker: `pd` is day-granular and
    hundreds of decisions share any given day across ~15,000 documents per
    domain, and Solr does not guarantee stable relative ordering among
    equal sort keys across separate paginated requests. Without a unique
    tie-breaker, pagination via `start`/`rows` could silently duplicate or
    skip documents between pages.
    """
    kinds = " OR ".join(f'kind:"{k}"' for k in get_kind_filter(_ARCHIVIO))
    window_clause = (
        f"datdep:[{WINDOW_START:%Y%m%d} TO {WINDOW_END:%Y%m%d}]"
    )
    fq = [f"({kinds})", "anno:[2025 TO 2025]", window_clause]
    if sezioni:
        # One OR clause. Three separate fq clauses would AND together and
        # match nothing, since a decision has exactly one section.
        fq.append("szdec:(" + " OR ".join(sezioni) + ")")
    return {
        "q": "*:*",
        "fq": fq,
        "sort": "pd asc, id asc",
        "rows": rows,
        "start": start,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocrdis,kind",
    }


def select_sample(
    candidates: dict[str, list[SeedDecision]],
    quotas: dict[str, int],
    seed: int = 20250107,
) -> dict[str, list[SeedDecision]]:
    """Draw the quota per domain with a reproducible seed.

    `rng.sample` picks by index, so reproducibility for a fixed seed also
    requires the pool to arrive in the same order every time — which
    Solr pagination does not guarantee on its own (see the tie-breaker
    note on `build_enumeration_params`). The pool is therefore canonicalised
    by `doc_id` before drawing, so the sample depends only on the seed and
    the *set* of candidates, never on the order they were fetched in.

    Returned in decision-number order — a distinct, later sort, kept
    purely so the gold set diffs cleanly in git.
    """
    picked: dict[str, list[SeedDecision]] = {}
    for domain, quota in quotas.items():
        pool = sorted(candidates.get(domain, []), key=lambda d: d.doc_id)
        rng = random.Random(f"{seed}:{domain}")
        chosen = pool[:] if len(pool) <= quota else rng.sample(pool, quota)
        picked[domain] = sorted(chosen, key=lambda d: d.number)
    return picked
