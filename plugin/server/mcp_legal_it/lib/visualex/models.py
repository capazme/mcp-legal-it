"""Simplified Norma / NormaVisitata dataclasses for URN generation."""

import re
from dataclasses import dataclass, field

from .article_suffixes import ARTICLE_SUFFIX_ALTERNATION
from .map import EURLEX, articolato_in_allegato, codice_urn, normalize_act_type


_NORMATTIVA_BASE = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_EURLEX_BASE = "https://eur-lex.europa.eu/eli"


def _parse_date(date: str) -> str:
    """Convert year-only date to YYYY-01-01; pass through full dates."""
    if not date:
        return ""
    if re.match(r"^\d{4}$", date):
        return f"{date}-01-01"
    return date


#: The ":k" that ends a code's URN in NORMATTIVA_URN_CODICI (";262:2" is the codice civile).
_URN_ALLEGATO = re.compile(r"^(.+;[^;:~]+):(\w+)$")


@dataclass
class Norma:
    tipo_atto: str
    data: str = ""
    numero_atto: str = ""
    # Normattiva's number for a part of the act, the ":k" of its URN (";104:2" is the
    # codice del processo amministrativo, the second part of d.lgs. 104/2010's export).
    # It is VisuaLex's ``allegato``: a position, not the name the act gives the annex
    # ("Allegato 1"). Empty: the act's body, or a code's own default part.
    allegato: str = ""

    def __post_init__(self):
        self.tipo_atto_normalized = normalize_act_type(self.tipo_atto)

    def _is_eurlex(self) -> bool:
        return self.tipo_atto_normalized.lower() in EURLEX

    def url(self, article: str = "") -> str:
        """Generate URL for this act (Normattiva or EUR-Lex)."""
        norm = self.tipo_atto_normalized.lower()

        # EUR-Lex routing
        if norm in EURLEX:
            val = EURLEX[norm]
            if val.startswith("https"):
                return val
            year = self.data.split("-")[0] if self.data and "-" in self.data else self.data
            return f"{_EURLEX_BASE}/{val}/{year}/{self.numero_atto}/oj/ita"

        # Normattiva: check codici first
        urn = codice_urn(norm)
        if urn:
            # Keep allegato suffix (e.g. :2 for codice civile) — it must precede ~artNNN —
            # unless another part of the act is asked for.
            if self.allegato:
                m = _URN_ALLEGATO.match(urn)
                urn = f"{m.group(1) if m else urn}:{self.allegato}"
            if article:
                urn = _append_article(urn, article)
            return _NORMATTIVA_BASE + urn

        # Normattiva: regular act
        act_urn = norm.replace(" ", ".")
        formatted_date = _parse_date(self.data)
        if not formatted_date:
            return ""
        urn = f"{act_urn}:{formatted_date};{self.numero_atto}"
        if self.allegato:
            # The part asked for by position wins over the act's default one, never both.
            urn += f":{self.allegato}"
        if article:
            allegato = articolato_in_allegato(act_urn, formatted_date, self.numero_atto)
            if allegato and not self.allegato and not names_an_annex(article):
                urn += f":{allegato}"
            urn = _append_article(urn, article)
        return _NORMATTIVA_BASE + urn

    def __str__(self):
        parts = [self.tipo_atto_normalized]
        if self.data:
            parts.append(f"{self.data},")
        if self.numero_atto:
            parts.append(f"n. {self.numero_atto}")
        return " ".join(parts)


@dataclass
class NormaVisitata:
    norma: Norma
    numero_articolo: str = ""
    _urn: str = field(default="", repr=False)

    def url(self) -> str:
        # An annex article has no ~artN of its own in the act URN: the act's URL is
        # the honest one (~artN would point at the body article with that number).
        if self.norma._is_eurlex() or split_annex(self.numero_articolo):
            return self.norma.url()
        return self.norma.url(article=self.numero_articolo)

    def __str__(self):
        base = str(self.norma)
        if split_annex(self.numero_articolo):
            base += f" {self.numero_articolo}"
        elif self.numero_articolo:
            base += f" art. {self.numero_articolo}"
        return base


# Annex identifiers as acts number them: "I.7", "II.14", "III", "1", "A".
ANNEX_ID = r"(?:[IVXLCDM]+|\d+|[A-Z])(?:\.\d+)*"

_ANNEX_RE = re.compile(
    rf"^\s*allegato\s+(?P<id>{ANNEX_ID})"
    # The article forms of the reference parser: "30", "2-bis", "2 bis", "2bis", "30.1",
    # "3-quater.1". Each repetition starts with a separator that \w cannot match: with
    # the separator optional ("[-/.\s]?\w+") a run of digits split in exponentially
    # many ways and a failing match took 0.44 s at 20 characters, x4 every 2 more.
    r"(?:[\s,]*(?:art(?:icolo)?\.?)\s*(?P<art>\d+[a-z]*(?:[-/.\s]\w+)*))?\s*$",
    re.IGNORECASE,
)


_ANNEX_WORD_RE = re.compile(r"^\s*allegat[oi]\b", re.IGNORECASE)


def names_an_annex(numero_articolo: str) -> bool:
    """Whether the article string speaks of an annex at all, parsable or not."""
    return bool(_ANNEX_WORD_RE.match(numero_articolo or ""))


def split_annex(numero_articolo: str) -> "tuple[str, str] | None":
    """``(annex_id, article)`` when the article designates an annex, else None.

    ``"allegato I.7 art. 30"`` -> ``("I.7", "30")``; ``"Allegato III"`` ->
    ``("III", "")`` (the whole annex). A plain article number returns None.
    """
    m = _ANNEX_RE.match(numero_articolo or "")
    if not m:
        return None
    return m.group("id"), (m.group("art") or "").strip()


def annex_reference(annex_id: str, article: str = "") -> str:
    """Canonical article string for an annex: the inverse of :func:`split_annex`."""
    ref = f"allegato {annex_id}"
    return f"{ref} art. {article}" if article else ref


#: "3-5", "3 - 5", "3/5-bis"... after the number: a second number, i.e. a range.
_ARTICLE_RANGE = re.compile(r"^\d+\s*[-\u2013\u2014]\s*\d")


class IntervalloArticoli(ValueError):
    """An article string that names a range of articles, not one article."""


def intervallo_articoli(article: str) -> "str | None":
    """The error to show when *article* is a range ("3-5"), else None.

    "3-5" is not article 3 with extension "5": as a URN it becomes ~art35 and
    serves art. 35, a real article, without a word. Entry points check this
    before building a reference; ``_append_article`` refuses it as a last resort.
    """
    plain = re.sub(r"^\s*(?:articol[oi]|artt?)\.?\s*", "", article or "", flags=re.IGNORECASE).strip()
    if not _ARTICLE_RANGE.match(plain):
        return None
    first, last = re.split(r"\s*[-\u2013\u2014]\s*", plain, maxsplit=1)
    return (f"«{plain}» indica un intervallo di articoli, non un articolo: "
            f"chiedere un articolo alla volta (es. art. {first}, poi art. {last})")


#: ";104~art120", ";104" at the end of a Normattiva URL: the act number without a ":k".
_URL_SENZA_PARTE = re.compile(r"(;[^;:~!@?]+)(?=~|!|@|$)")


def url_in_part(url: str, position: "int | str") -> str:
    """*url* pointing at the part at Normattiva position *position*, if it names no part yet.

    ``…;104~art120`` -> ``…;104:2~art120``; a URL that already ends its act number
    with ``:k`` (``…;262:2~art2043``) is returned unchanged.
    """
    if not position or "normattiva.it" not in url:
        return url
    return _URL_SENZA_PARTE.sub(lambda m: f"{m.group(1)}:{position}", url, count=1)


def _append_article(urn: str, article: str) -> str:
    """Append ~artXXX to URN, handling extensions like '13-bis' or '2 bis'."""
    if (motivo := intervallo_articoli(article)) is not None:
        raise IntervalloArticoli(motivo)
    article = re.sub(r"\b[Aa]rticoli?\b|\b[Aa]rt\.?\b", "", article).strip()
    extension = ""
    space_match = re.match(rf"^(\d+)\s+({ARTICLE_SUFFIX_ALTERNATION})$", article, re.IGNORECASE)
    if space_match:
        article = space_match.group(1)
        extension = space_match.group(2)
    elif "-" in article:
        # "2-bis", "2 - bis", "135 sex-decies": no space nor dash stays in the URN.
        parts = article.split("-", 1)
        # Every repetition opens with blanks, so a run of letters cannot be split two ways
        # (a nested "(letters blanks*)*" was exponential on "1 aaaa…1").
        head = re.match(r"^(\d+)((?:\s+[A-Za-z]+)*)\s*$", parts[0])
        article = head.group(1) if head else parts[0].strip()
        extension = re.sub(r"[\s-]", "", (head.group(2) if head else "") + parts[1])
    elif (words := re.match(r"^(\d+)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)$", article)):
        # A suffix written in words the table does not list as one ("135 sex decies",
        # "25 vicies semel"): joined, as VisuaLex's controller joins them before the URN
        # ("135 sex decies" -> "135-sex-decies" -> ~art135sexdecies). Never a space in a URN.
        article = words.group(1)
        extension = "".join(words.group(2).split())
    urn += f"~art{article}"
    if extension:
        urn += extension
    return urn
