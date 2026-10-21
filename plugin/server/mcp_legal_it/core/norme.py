"""Norm lookup logic shared by the MCP tools and the library API.

Pure logic per ADR-001: reference parsing, act resolution and the structured
article lookup. Nothing here imports FastMCP or ``mcp_legal_it.server``; the
tools in ``mcp_legal_it.tools.legal_citations`` add the Markdown on top.
"""

import asyncio
import difflib
import re

import httpx

from mcp_legal_it.lib import _clock
from mcp_legal_it.lib.visualex import (
    Norma,
    NormaVisitata,
    resolve_atto,
    strip_leading_particles,
    known_act_names,
)
from mcp_legal_it.lib.visualex.models import ANNEX_ID, annex_reference
from mcp_legal_it.lib.visualex.scraper import CHECK_UNAVAILABLE, fetch_article

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
    reference = reference.strip()

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
        return article, rest

    # No "art." prefix — try to parse as just act name (no article)
    return "", reference


# Act types as they appear in citations, spelled-out forms first so the
# alternation never settles for the "L." inside "legge".
_TIPO_ALT = (
    r"decreto\s+del\s+presidente\s+della\s+repubblica"
    r"|decreto\s+del\s+presidente\s+del\s+consiglio(?:\s+dei\s+ministri)?"
    r"|decreto\s+legislativo|decreto[-\s]legge|decreto\s+ministeriale"
    r"|regio\s+decreto|legge"
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


def _build_nv(act_info: dict, article: str) -> NormaVisitata:
    """Build a NormaVisitata from resolved act info + article number."""
    norma = Norma(
        tipo_atto=act_info["tipo_atto"],
        data=act_info.get("data", ""),
        numero_atto=act_info.get("numero_atto", ""),
    )
    return NormaVisitata(norma=norma, numero_articolo=article)


def _urn_from_url(url: str) -> str | None:
    """Extract the URN from a Normattiva ``uri-res`` URL, else None.

    Normattiva citable URLs look like
    ``https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:...`` — the URN is
    the substring after the ``?``. Any other URL (EUR-Lex, etc.) has no URN.
    """
    if "normattiva.it/uri-res/N2Ls?" not in url:
        return None
    return url.split("?", 1)[1] or None


def _source_failure(exc: Exception) -> bool:
    """Whether an exception says the source is down, slow or limiting us (not that the norm is absent)."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        return status == 429 or status >= 500
    return isinstance(exc, (httpx.TransportError, asyncio.TimeoutError))


def _failed_fetch(nv: NormaVisitata, exc: Exception) -> dict:
    result = {"text": "", "url": nv.url(), "source": "", "error": str(exc)}
    if _source_failure(exc):
        result["esito"] = CHECK_UNAVAILABLE
    return result


async def fetch_norma(nv: NormaVisitata) -> dict:
    """``fetch_article`` with a failure turned into the scraper's error shape, never raised."""
    try:
        return await fetch_article(nv)
    except Exception as e:
        return _failed_fetch(nv, e)


async def _cite_law_struct(reference: str) -> dict:
    """Structured article lookup (no Brocardi): the JSON face of cite_law."""
    return (await _cite_law_lookup(reference))[0]


async def _cite_law_lookup(reference: str) -> tuple[dict, str | None]:
    """The JSON face of cite_law, plus the outcome of the existence check.

    The outcome is ``ARTICLE_NOT_FOUND`` (the article is not in the act),
    ``CHECK_UNAVAILABLE`` (the source could not tell) or None.
    """
    today = _clock.today().isoformat()
    base = {
        "formato": "json", "riferimento": reference, "articolo": "",
        "atto": {"tipo_atto": "", "data": "", "numero_atto": "", "descrizione": ""},
        "url": "", "urn": None, "fonte": "", "allegato": None, "testo": "", "errore": None,
        "data_consultazione": today,
    }
    article, act_name = _parse_reference(reference)
    if not act_name:
        base["errore"] = (f"impossibile interpretare il riferimento '{reference}'. "
                          "Formato atteso: 'art. <numero> <atto>'")
        return base, None
    act_info = _resolve_act(act_name)
    if not act_info:
        base["errore"] = _unresolved_act_error(act_name).replace("**Errore**: ", "")
        return base, None

    nv = _build_nv(act_info, article)
    base["articolo"] = article or ""
    base["atto"] = {
        "tipo_atto": nv.norma.tipo_atto_normalized,
        "data": act_info.get("data", ""),
        "numero_atto": act_info.get("numero_atto", ""),
        "descrizione": str(nv.norma),
    }
    result = await fetch_norma(nv)
    base["url"] = result.get("url", "") or nv.url()
    base["urn"] = _urn_from_url(base["url"])
    # Cited with the year only, the act is queried as YYYY-01-01. The scraper replaces that
    # with the act's real date (from the Normattiva page); when it could not, the URL still
    # works but its date is a placeholder, so no URN is presented as the act's own.
    full_date = result.get("data_atto") or ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", full_date):
        base["atto"]["data"] = full_date
        base["atto"]["descrizione"] = str(Norma(tipo_atto=nv.norma.tipo_atto, data=full_date,
                                                numero_atto=nv.norma.numero_atto))
    elif base["urn"] and re.fullmatch(r"\d{4}", act_info.get("data", "") or ""):
        base["urn"] = None
    base["fonte"] = result.get("source", "") or ""
    base["allegato"] = result.get("allegato") or None
    base["testo"] = result.get("text", "") or ""
    if result.get("error"):
        base["errore"] = result["error"]
    elif not base["testo"]:
        base["errore"] = "nessun testo trovato"
    return base, result.get("esito")
