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

_CASS_CITATION = (
    r"Cass\.(?:\s*(?:civ|pen)\.)?,?"
    r"(?:\s*(?:sez\.?\s*(?:un\.?|[\wIVX]+)|SS\.?\s*UU\.?|sezioni\s+unite)\s*,?)?"
    r"(?:\s*(?:ord|sent)\.\s*,?)?"
    r"(?:\s*\d{1,2}[./]\d{1,2}[./]\d{4}\s*,?)?"
    r"\s*nn?\.\s*(\d{1,6})\s*[/\\]\s*(\d{4})"
)

# Declared markers. Ids are referenced by bank items (`expected_markers`,
# `disqualifiers`) and cross-checked by the bank validator.
MARKERS: dict[str, Pattern[str]] = {
    # Cassazione with full identifying elements (sezione optional, number+year
    # required — a bare "Cass." mention is not an identifiable citation).
    # v1: also "Cass. civ., SS.UU., 30/12/2021, n. 41994/2021", "Cass.,
    # sez. un., ord. n. ...", "Cass. civ., sez. III, n. ..." (the v0 pattern
    # only knew "Cass. sez. X, n. N/YYYY" and missed every SS.UU. citation).
    "cass": re.compile(_CASS_CITATION, re.IGNORECASE),
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

# --- Parametric coded-article markers (protocol v1) -------------------------
#
# Ids of the form `<code>-<article>` (e.g. `cp-25`, `cost-25`, `cpc-645`,
# `cc-2947`, `l689-1`) resolve to "article N followed, within a short
# window, by the code's label". The code label is REQUIRED: an identifiable
# citation is norm + article + source (DESIGN §4.1), and `art. 25` alone
# is ambiguous between the Constitution and the criminal code. Lists are
# recognised ("artt. 2043 e 2059 c.c." hits both cc-2043 and cc-2059).
# Resolution is lazy but deterministic: the id grammar and the label table
# below are the declaration (both pinned by protocol_sha).
_CODE_LABELS: dict[str, str] = {
    "cc": r"(?:c\.\s?c\.|cod\.\s?civ\.|codice\s+civile)",
    "cp": r"(?:c\.\s?p\.(?!\s?[cp]\.)|cod\.\s?pen\.|codice\s+penale)",
    "cpc": r"(?:c\.\s?p\.\s?c\.|cod\.\s?proc\.\s?civ\.|codice\s+di\s+procedura\s+civile)",
    "cpp": r"(?:c\.\s?p\.\s?p\.|cod\.\s?proc\.\s?pen\.|codice\s+di\s+procedura\s+penale)",
    "cost": r"(?:cost\.|costituzione)",
    "prel": r"(?:disp(?:osizioni)?\.?\s*(?:sulla\s+legge\s+in\s+generale|prel(?:iminari)?\.?)|preleggi)",
    "tfue": r"(?:tfue|trattato\s+sul\s+funzionamento)",
    "tue": r"(?:\btue\b|trattato\s+sull'?\s*unione)",
    "gdpr": r"(?:gdpr|rgpd|regolamento\s+(?:\(ue\)\s*)?(?:n\.\s*)?2016/679)",
    "l689": r"(?:(?:l\.|legge)\s*(?:n\.\s*)?689(?:/|\s+del\s+)(?:19)?81)",
    "dlgs28": r"(?:d\.\s?lgs\.?\s*(?:n\.\s*)?28(?:/|\s+del\s+)(?:20)?10)",
    "cds": r"(?:c\.\s?d\.\s?s\.|codice\s+della\s+strada)",
    "tub": r"(?:\btub\b|testo\s+unico\s+bancario|d\.\s?lgs\.?\s*(?:n\.\s*)?385(?:/|\s+del\s+)(?:19)?93)",
    "l300": r"(?:statuto\s+dei\s+lavoratori|(?:l\.|legge)\s*(?:n\.\s*)?300(?:/|\s+del\s+)(?:19)?70)",
    "l400": r"(?:(?:l\.|legge)\s*(?:n\.\s*)?400(?:/|\s+del\s+)(?:19)?88)",
    "cdc": r"(?:codice\s+del\s+consumo|cod\.\s?cons\.|c\.\s?cons\.|d\.\s?lgs\.?\s*(?:n\.\s*)?206(?:/|\s+del\s+)(?:20)?05)",
    "l431": r"(?:(?:l\.|legge)\s*(?:n\.\s*)?431(?:/|\s+del\s+)(?:19)?98)",
    "l87": r"(?:(?:l\.|legge)\s*(?:n\.\s*)?87(?:/|\s+del\s+)(?:19)?53)",
    "l2248": r"(?:(?:l\.|legge)\s*(?:n\.\s*)?2248(?:/|\s+del\s+)(?:18)?65|allegato\s+e|all\.\s*e\b|legge\s+abolitiva\s+del\s+contenzioso)",
}
# Any source label: the article-to-label gap may never CROSS another label,
# or "art. 1176 c.c. e di Corte cost." would attach 1176 to the Constitution.
_ANY_LABEL = "(?:" + "|".join(_CODE_LABELS.values()) + ")"
_GAP_CHAR = (
    rf"(?:(?!{_ANY_LABEL})"
    r"(?:[^.;]|(?:(?<=\b[a-z])|(?<=\b[a-z]{2})|(?<=\b[a-z]{3})|(?<=\b[a-z]{4}))\.))"
)
_CODED_ID = re.compile(r"^(" + "|".join(_CODE_LABELS) + r")-(\d{1,4})(bis|ter|quater)?$")


def _coded_pattern(code: str, number: str, suffix: str | None) -> Pattern[str]:
    article = number + (rf"[\s-]*{suffix}" if suffix else r"(?![\s-]*(?:bis|ter|quater)\b)")
    return re.compile(
        rf"\bartt?(?:icol[oi])?\.?\s*(?:\d{{1,4}}(?:[\s-]*(?:bis|ter|quater))?\s*(?:,|e|ed)\s*)*"
        rf"{article}\b"
        # Gap between article and code label: any text but a sentence end;
        # a dot is allowed only inside abbreviations ("n. 4", "co. 2",
        # "d.lgs.") — so a label in the NEXT sentence never attaches.
        rf"{_GAP_CHAR}{{0,60}}?"
        rf"{_CODE_LABELS[code]}",
        re.IGNORECASE,
    )


# `cass-<number>-<year>`: ONE specific decision. The generic `cass` marker
# only checks the citation FORMAT, so a fabricated number passes it; an item
# that asks for a specific pronouncement expects this marker instead. The
# number must be followed, within a short window, by the year ("n. 41994/2021",
# "41994 del 30/12/2021", "nn. 12564-12567 del 2018").
_CASS_ID = re.compile(r"^cass-(\d{1,6})-(\d{4})$")


def _cass_pattern(number: str, year: str) -> Pattern[str]:
    # Number then year ("n. 41994/2021", "41994 del 30/12/2021") or the
    # date-first form ("SS.UU., 30/12/2021, n. 41994").
    return re.compile(
        rf"(?<!\d){number}(?!\d)[^.;]{{0,40}}?(?:\d{{1,2}}[./-]\d{{1,2}}[./-])?{year}\b"
        rf"|\b(?:\d{{1,2}}[./-]\d{{1,2}}[./-])?{year}\b[^;]{{0,12}}?\bnn?\.\s*{number}(?!\d)",
        re.IGNORECASE,
    )


def marker_pattern(marker: str) -> Pattern[str] | None:
    """The pattern of a declared marker: a static registry entry, a
    well-formed coded-article id or a specific-decision id; None for
    unknown ids (fail-closed at the bank validator)."""
    if marker in MARKERS:
        return MARKERS[marker]
    cass = _CASS_ID.match(marker)
    if cass is not None:
        return _cass_pattern(cass.group(1), cass.group(2))
    match = _CODED_ID.match(marker)
    if match is None:
        return None
    return _coded_pattern(match.group(1), match.group(2), match.group(3))


def is_known_marker(marker: str) -> bool:
    return marker_pattern(marker) is not None




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
    "cass": re.compile(_CASS_CITATION, re.IGNORECASE),
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


# Generic extractors, one per coded source (`art-<code>`): they make every
# "art. N <source>" citation of the label table an IDENTIFIABLE citation
# (fidelity key = article number + source label) for the P dimension, not
# only the handful of sources the wave-0 registry knew. Extraction only —
# bank items reference the specific `<code>-<article>` ids above.
_GAP = _GAP_CHAR + "{0,60}?"
for _code, _label in _CODE_LABELS.items():
    _generic = (
        rf"\bartt?(?:icol[oi])?\.?\s*(\d{{1,4}}(?:[\s-]*(?:bis|ter|quater))?)\b"
        rf"{_GAP}({_label})"
    )
    MARKERS[f"art-{_code}"] = re.compile(_generic, re.IGNORECASE)
    _FIDELITY_KEYS[f"art-{_code}"] = re.compile(_generic, re.IGNORECASE)


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
    pattern = marker_pattern(marker)
    if pattern is None:
        raise KeyError(marker)
    return pattern.search(normalize(answer)) is not None


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
