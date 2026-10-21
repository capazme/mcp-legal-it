"""Reference parsing and act resolution: the stdlib-only half of ``norme``.

Kept apart from ``norme`` (which fetches over httpx) so that the plugin's
citation gate can parse and resolve citations with the server's own code
without importing an HTTP stack on every turn. Nothing here may import
httpx, bs4, lxml or FastMCP: ``tests/unit/test_citation_gate.py`` checks it.
"""

import difflib
import re

from mcp_legal_it.lib.visualex import resolve_atto, strip_leading_particles, known_act_names
from mcp_legal_it.lib.visualex.models import ANNEX_ID, annex_reference

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Strips paragraph/point/comma indicators from the start of the act name
# so that "art. 4 n. 11 GDPR" → article="4", act="GDPR".
_PARAGRAPH_PATTERN = re.compile(
    r"^[,;\s]*(?:n\.?\s*\d+|co(?:mma)?\.?\s*\d+|par\.?\s*\d+|punto\s*\d+|lett\.?\s*\w\)?)\s*[,;]?\s*",
    re.IGNORECASE,
)


# Connectives between an annex and its act: "allegato I.7 al D.Lgs. 36/2023".
_ANNEX_LINK = r"(?:(?:al|del|della|dello|alla|all['’]|dell['’])\s*)?"

# "allegato I.7 [art. 30] <atto>", "Allegato III, punto 4, lett. a) <atto>"
_ANNEX_FIRST_PATTERN = re.compile(
    rf"^allegato\s+(?P<id>{ANNEX_ID})(?=[\s,;]|$)"
    r"(?:\s*,?\s*(?:articol[oi]|art)\.?\s*(?P<art>\d+(?:[-/.]\w+)*))?"
    r"\s*[,;]?\s*(?P<rest>.+)$",
    re.IGNORECASE,
)

# What follows "art. 30" when the article belongs to an annex: "dell'allegato I.7 al ..."
_ANNEX_AFTER_ARTICLE = re.compile(
    rf"^{_ANNEX_LINK}allegato\s+(?P<id>{ANNEX_ID})(?=[\s,;]|$)\s*[,;]?\s*(?P<rest>.+)$",
    re.IGNORECASE,
)


# Act first, then the article or annex: "D.Lgs. 196/2003 art. 13", "GDPR, art. 6
# par. 1 lett. f)", "D.Lgs. 36/2023 allegato I.1 art. 1". Only an article, its
# paragraph/letter indicators and an annex may follow the act: any other trailing
# text ("... convertito dalla L. 27/2020") would end up inside the act name.
_ART = r"(?:articol[oi]|art)\.?\s*\d+(?:[-/.]\w+)*"
# One separator class per repetition: "\s*[,;]?\s*" splits a run of spaces two ways and,
# repeated, made a failing match exponential in the number of indicators.
_PARAGRAPHS = (
    r"(?:[\s,;]*(?:n\.?\s*\d+|co(?:mma)?\.?\s*\d+\w*|par\.?\s*\d+|punto\s*\d+|lett\.?\s*\w\)?))*"
)
# The act may not end on a separator and every separator run is one [\s,;]+: a lazy
# ".+?" followed by "\s*[,;]?\s+" could split the same run of spaces many ways, which
# made a failing match cubic in its length (5000 spaces: 92 s, synchronously).
_ACT_FIRST_PATTERN = re.compile(
    rf"^(?P<act>.*?[^\s,;])[\s,;]+(?P<ref>"
    rf"{_ART}{_PARAGRAPHS}(?:[\s,;]*{_ANNEX_LINK}allegato\s+{ANNEX_ID})?"
    rf"|allegato\s+{ANNEX_ID}(?:[\s,]*{_ART})?{_PARAGRAPHS}"
    r")\s*$",
    re.IGNORECASE,
)


# The annex written after the act: "D.Lgs. 36/2023, allegato I.7".
_ANNEX_LAST = re.compile(
    rf"^(?P<act>.*?[^\s,;])[\s,;]+{_ANNEX_LINK}allegato\s+(?P<id>{ANNEX_ID})\s*$",
    re.IGNORECASE,
)


def _strip_paragraphs(rest: str) -> str:
    """Drop leading paragraph/point/letter indicators, repeatedly ("comma 1 lett. a) GDPR" → "GDPR")."""
    while True:
        stripped = _PARAGRAPH_PATTERN.sub("", rest).strip()
        if stripped == rest:
            return rest
        rest = stripped


def _strip_annex_link(rest: str) -> str:
    """Drop the connective before the act name ("al D.Lgs. 36/2023" → "D.Lgs. 36/2023")."""
    return re.sub(rf"^{_ANNEX_LINK}", "", rest, flags=re.IGNORECASE).strip()


def _parse_reference(reference: str) -> tuple[str, str]:
    """Parse a legal reference like 'art. 13 GDPR' into (article, act_name).

    Supports:
    - "art. 13 GDPR"
    - "art. 2-ter D.Lgs. 196/2003"
    - "ART 117 Costituzione"
    - "art. 2043 c.c."
    - "art. 6 D.Lgs. 231/2001"
    - "art. 4 n. 11 GDPR"  → paragraph stripped → ("4", "GDPR")
    - "considerando 42 GDPR" → ("rec_42", "GDPR")
    - "recital 47 GDPR"     → ("rec_47", "GDPR")
    - "allegato I.7 art. 30 D.Lgs. 36/2023", "art. 30 dell'allegato I.7 al D.Lgs. 36/2023"
                             → ("allegato I.7 art. 30", "D.Lgs. 36/2023")
    - "Allegato III AI Act"  → ("allegato III", "AI Act")
    """
    # One space for any run of whitespace (tabs, NBSP, newlines included): every
    # pattern below then sees separators of bounded length.
    reference = re.sub(r"\s+", " ", reference).strip()
    # A range written with spaces, an en/em dash or "artt." is still a range: one form,
    # "art. 3-5", so the entry points refuse it with the same message.
    reference = re.sub(r"(\d) ?[-\u2013\u2014] ?(\d)", r"\1-\2", reference)
    reference = re.sub(r"\bartt\.? ?(?=\d+-\d)", "art. ", reference, flags=re.IGNORECASE)

    annex_match = _ANNEX_FIRST_PATTERN.match(reference)
    if annex_match:
        rest = _strip_annex_link(_strip_paragraphs(annex_match.group("rest").strip()))
        return annex_reference(annex_match.group("id"), annex_match.group("art") or ""), rest

    # Considerando / recital — must be checked before "art." pattern
    rec_match = re.match(
        r"(?:considerando|recital)\s+(\d+)\s+(.+)",
        reference,
        re.IGNORECASE,
    )
    if rec_match:
        return f"rec_{rec_match.group(1)}", rec_match.group(2).strip()

    # Pattern: art[.] <number[-ext]> <act_name>
    match = re.match(
        r"(?:articol[oi]|art)\.?\s*(\d+(?:[-/.]\w+)*)\s*[,;]?\s+(.+)",
        reference,
        re.IGNORECASE,
    )
    if match:
        article = match.group(1).strip()
        # Strip leading paragraph/point/comma indicators, applied repeatedly
        # to handle chains like "comma 1 lett. a) GDPR" → "GDPR".
        rest = _strip_paragraphs(match.group(2).strip())
        annex_match = _ANNEX_AFTER_ARTICLE.match(rest)
        if annex_match:
            rest = _strip_annex_link(annex_match.group("rest").strip())
            return annex_reference(annex_match.group("id"), article), rest
        # "art. 30 D.Lgs. 36/2023, allegato I.7": the annex closes the reference.
        annex_last = _ANNEX_LAST.match(rest)
        if annex_last:
            return annex_reference(annex_last.group("id"), article), annex_last.group("act").strip()
        return article, rest

    # Act written first: put the article (or annex) in front and parse that.
    # Read as an act name, "D.Lgs. 196/2003 art. 13" resolves to the decree and
    # the article is lost: the caller got the start of the act instead of art. 13.
    act_first = _ACT_FIRST_PATTERN.match(reference)
    if act_first:
        return _parse_reference(f"{act_first.group('ref')} {act_first.group('act')}")

    # An article is named but cannot be told apart from the act: refuse (the
    # caller reports the expected format) rather than resolve the act alone.
    if re.search(rf"\b{_ART}", reference, re.IGNORECASE):
        return "", ""

    # No "art." prefix — try to parse as just act name (no article)
    return "", reference


# Act types as they appear in citations, spelled-out forms first so the
# alternation never settles for the "L." inside "legge".
_TIPO_ALT = (
    r"decreto\s+del\s+presidente\s+della\s+repubblica"
    r"|decreto\s+del\s+presidente\s+del\s+consiglio(?:\s+dei\s+ministri)?"
    r"|decreto\s+legislativo\s+luogotenenziale"
    r"|decreto\s+legislativo|decreto[-\s]legge|decreto\s+ministeriale"
    r"|regio\s+decreto[-\s]legge|regio\s+decreto"
    r"|legge\s+cost(?:ituzionale|\.)|legge"
    # Constitutional laws, royal decree-laws and lieutenancy decrees before the
    # forms they start with ("l.", "r.d.", "d.lgs."/"d.l.").
    r"|L\.?\s?cost(?:ituzionale|\.)?|R\.?\s?D\.?\s?L\.?|D\.?\s?(?:Lgs|L)\.?\s?Lgt\.?"
    r"|D\.?\s?Lgs\.?|D\.?P\.?C\.?M\.?|D\.?P\.?R\.?|DPR|R\.?D\.?"
    r"|D\.?\s?M\.?|D\.?\s?L\.?|L\.?"
)

# Canonical name per act type, keyed on the citation stripped of dots, spaces
# and hyphens ("D. Lgs." and "decreto legislativo" both land on one entry).
_TIPO_CANONICO = {
    "dlgs": "decreto legislativo",
    "decretolegislativo": "decreto legislativo",
    "dl": "decreto legge",
    "decretolegge": "decreto legge",
    "dm": "decreto ministeriale",
    "decretoministeriale": "decreto ministeriale",
    "dpcm": "decreto del presidente del consiglio dei ministri",
    "decretodelpresidentedelconsiglio": "decreto del presidente del consiglio dei ministri",
    "decretodelpresidentedelconsigliodeiministri": "decreto del presidente del consiglio dei ministri",
    "dpr": "decreto del presidente della repubblica",
    "decretodelpresidentedellarepubblica": "decreto del presidente della repubblica",
    "rd": "regio decreto",
    "regiodecreto": "regio decreto",
    "l": "legge",
    "legge": "legge",
    # The names the URN builder knows: legge.costituzionale, regio.decreto.legge,
    # decreto.legislativo.luogotenenziale.
    "lcost": "legge costituzionale",
    "lcostituzionale": "legge costituzionale",
    "leggecost": "legge costituzionale",
    "leggecostituzionale": "legge costituzionale",
    "rdl": "regio decreto legge",
    "regiodecretolegge": "regio decreto legge",
    "dllgt": "decreto legislativo luogotenenziale",
    "dlgslgt": "decreto legislativo luogotenenziale",
    "decretolegislativoluogotenenziale": "decreto legislativo luogotenenziale",
}

_MESI_IT = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
    "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
    "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
}

# "regolamento (UE) 2016/679", "reg. UE n. 679/2016", "direttiva 95/46/CE"
_EU_PATTERN = re.compile(
    r"^(reg(?:olamento)?|dir(?:ettiva)?)\.?\s*"
    r"(?:\(?\s*(?:UE|EU|CE|CEE)\s*\)?)?\s*"
    r"(?:n\.?\s*)?(\d{1,4})\s*/\s*(\d{1,4})"
    r"(?:\s*/\s*(?:UE|EU|CE|CEE))?",
    re.IGNORECASE,
)

# "D.Lgs. 30 giugno 2003, n. 196"
_IT_LONG_PATTERN = re.compile(
    rf"^({_TIPO_ALT})\s+(\d{{1,2}})\s+"
    r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    r"\s+(\d{4})[,]?\s*n\.?\s*(\d+)",
    re.IGNORECASE,
)

# "D.Lgs. 196/2003", "legge n. 241 del 1990", "legge n. 241/1990"
_IT_SHORT_PATTERN = re.compile(
    rf"^({_TIPO_ALT})\s*(?:n\.?\s*)?(\d+)\s*(?:/|\s+del\s+)\s*(\d{{4}})",
    re.IGNORECASE,
)


def _canonical_tipo(raw: str) -> str:
    """Map a cited act type to its canonical Normattiva name."""
    key = re.sub(r"[.\s-]", "", raw.lower())
    return _TIPO_CANONICO.get(key, raw.lower().strip())


def _split_eu_year_number(first: str, second: str) -> tuple[str, str]:
    """Decide which half of an EU act's "NNNN/NNNN" is the year.

    Directives switched notation in 2015: "95/46/CE" is year/number with a
    two-digit year, "2019/1937" is year/number with a four-digit one, and some
    citations still invert it as "679/2016". The four-digit plausible year wins;
    a leading two-digit group is a 20th-century year.
    """
    def is_year(v: str) -> bool:
        return len(v) == 4 and 1950 <= int(v) <= 2099

    if is_year(first):
        return first, second
    if is_year(second):
        return second, first
    if len(first) == 2:
        return f"19{first}", second
    return first, second


def _resolve_act(act_name: str) -> dict | None:
    """Resolve an act name to scraper parameters {tipo_atto, data, numero_atto}.

    Resolution chain:
    1. resolve_atto() — hand-verified tables (ATTI_NOTI, codici, ATTI_DENOMINATI)
    2. citation patterns — EU acts, then Italian acts in long and short form

    Returns None rather than guessing: a caller that cannot resolve an act must
    say so, never cite a different one.
    """
    result = resolve_atto(act_name)
    if result:
        return result

    # Patterns run against the name stripped of any leading preposition
    # ("del D.Lgs. 231/2001"), which resolve_atto has already normalized away.
    candidate = strip_leading_particles(act_name)

    eu_match = _EU_PATTERN.match(candidate)
    if eu_match:
        tipo_raw, first, second = eu_match.groups()
        anno, numero = _split_eu_year_number(first, second)
        tipo = "regolamento ue" if tipo_raw.lower().startswith("reg") else "direttiva ue"
        return {"tipo_atto": tipo, "data": anno, "numero_atto": numero}

    long_match = _IT_LONG_PATTERN.match(candidate)
    if long_match:
        tipo_raw, giorno, mese_it, anno, numero = long_match.groups()
        data = f"{anno}-{_MESI_IT[mese_it.lower()]}-{giorno.zfill(2)}"
        return {"tipo_atto": _canonical_tipo(tipo_raw), "data": data, "numero_atto": numero}

    short_match = _IT_SHORT_PATTERN.match(candidate)
    if short_match:
        tipo_raw, numero, anno = short_match.groups()
        return {"tipo_atto": _canonical_tipo(tipo_raw), "data": anno, "numero_atto": numero}

    return None


def _suggest_acts(act_name: str, limit: int = 3) -> list[str]:
    """Names close to an unrecognised one, so the caller can retry knowingly."""
    return difflib.get_close_matches(
        strip_leading_particles(act_name), known_act_names(), n=limit, cutoff=0.7
    )


def _unresolved_act_error(act_name: str) -> str:
    """Error text for an act the resolver could not identify, with near misses."""
    message = f"**Errore**: atto '{act_name}' non riconosciuto."
    suggestions = _suggest_acts(act_name)
    if suggestions:
        message += " Forse intendevi: " + ", ".join(f"'{s}'" for s in suggestions) + "."
    message += (
        " Prova con il nome completo (es. 'D.Lgs. 196/2003')"
        " o usa fetch_law_article() con parametri espliciti."
    )
    return message
