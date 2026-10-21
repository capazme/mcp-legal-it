"""Simplified Norma / NormaVisitata dataclasses for URN generation."""

import re
from dataclasses import dataclass, field

from .map import EURLEX, codice_urn, normalize_act_type


_NORMATTIVA_BASE = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_EURLEX_BASE = "https://eur-lex.europa.eu/eli"


def _parse_date(date: str) -> str:
    """Convert year-only date to YYYY-01-01; pass through full dates."""
    if not date:
        return ""
    if re.match(r"^\d{4}$", date):
        return f"{date}-01-01"
    return date


@dataclass
class Norma:
    tipo_atto: str
    data: str = ""
    numero_atto: str = ""

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
            # Keep allegato suffix (e.g. :2 for codice civile) — it must precede ~artNNN
            if article:
                urn = _append_article(urn, article)
            return _NORMATTIVA_BASE + urn

        # Normattiva: regular act
        act_urn = norm.replace(" ", ".")
        formatted_date = _parse_date(self.data)
        if not formatted_date:
            return ""
        urn = f"{act_urn}:{formatted_date};{self.numero_atto}"
        if article:
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
    # The article forms of the reference parser: "30", "2-bis", "2 bis", "30.1", "3-quater.1".
    r"(?:\s*,?\s*(?:art(?:icolo)?\.?)\s*(?P<art>\d+(?:[-/.\s]?\w+)*))?\s*$",
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


def _append_article(urn: str, article: str) -> str:
    """Append ~artXXX to URN, handling extensions like '13-bis' or '2 bis'."""
    article = re.sub(r"\b[Aa]rticoli?\b|\b[Aa]rt\.?\b", "", article).strip()
    extension = ""
    space_match = re.match(r"^(\d+)\s+(bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)$", article, re.IGNORECASE)
    if space_match:
        article = space_match.group(1)
        extension = space_match.group(2)
    elif "-" in article:
        parts = article.split("-", 1)
        article = parts[0]
        extension = parts[1].replace("-", "")
    urn += f"~art{article}"
    if extension:
        urn += extension
    return urn
