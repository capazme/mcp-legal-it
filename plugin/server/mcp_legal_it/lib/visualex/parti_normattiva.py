"""The parts Normattiva splits a very long article into («1 (commi 1-100)», «1 (commi 101-200)» …).

Normattiva serves a very long article in parts: art. 1 L. 296/2006 is 14 pages, «1 (commi
1-100)» to «1 (commi 1301-1364)», each opened from the act's tree with
``/atto/caricaArticolo?…&art.progressivo=k``. The article's own page (``N2Ls?…~art1``) is
one of them, the first, and says so in a visible line «art. 1 (commi 1-100)». A part's page
needs the session cookie the article page sets, as the update tables do.

The progressivo is Normattiva's index in the tree as it is today: an amendment can split the
article again, so nothing here is keyed by the progressivo alone (the commi range travels
with it). Pure parsing; the request is ``scraper.leggi_parte``.
"""

from __future__ import annotations

import html as _html
import re
from typing import Any, Callable, Optional

from .article_suffixes import ARTICLE_SUFFIX_ALTERNATION as _SUFFISSI

# A comma number as the tree writes it: «773», «1-bis», «12 ter».
_COMMA = rf"\d+(?:[\s-]*(?:{_SUFFISSI})\b)?"
# A tree entry of a part: showArticle('/atto/caricaArticolo?…') … >1 (commi 701-800)</a>
_VOCE = re.compile(
    r"showArticle\('(/atto/caricaArticolo\?[^']+)'[^>]*>\s*([^<(]*?)\s*\(commi\s+(" + _COMMA + r")\s*-\s*("
    + _COMMA + r")\)\s*</a>",
    re.IGNORECASE,
)
_PROGRESSIVO = re.compile(r"art\.progressivo=(\d+)")
# The page's visible line naming the part it serves: «art. 1 (commi 701-800)».
_SERVITA = re.compile(r"art\.\s*[\w.\- ]+?\s*\(commi\s+(" + _COMMA + r")\s*-\s*(" + _COMMA + r")\)", re.IGNORECASE)
_COMMENTO = re.compile(r"<!--.*?-->", re.S)


def _canonico(comma: str) -> str:
    """«1 bis», «1-bis», «1bis» -> «1-bis»; «773» stays."""
    m = re.match(rf"(\d+)[\s-]*({_SUFFISSI})?$", comma.strip(), re.IGNORECASE)
    if not m:
        return comma.strip()
    return m.group(1) + (f"-{m.group(2).lower()}" if m.group(2) else "")


def parti_articolo(html: str, stesso_articolo: Callable[[str], bool]) -> list[dict[str, Any]]:
    """The parts of the article in the page's tree, in order: ``[{progressivo, commi_dal, commi_al, path}]``.

    *stesso_articolo(label)* says whether a tree label («1», «1-bis») is the article asked
    for. ``[]`` when the article is not split (its tree entry has no «(commi a-b)»).
    """
    parti: dict[int, dict[str, Any]] = {}
    for m in _VOCE.finditer(html):
        path, etichetta, dal, al = _html.unescape(m.group(1)), m.group(2), m.group(3), m.group(4)
        progressivo = _PROGRESSIVO.search(path)
        if progressivo is None or not stesso_articolo(etichetta):
            continue
        k = int(progressivo.group(1))
        parti.setdefault(k, {"progressivo": k, "commi_dal": _canonico(dal), "commi_al": _canonico(al), "path": path})
    return [parti[k] for k in sorted(parti)]


def parte_servita(html: str, parti: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """The part a page serves, from its visible «art. N (commi a-b)» line; None when it does not say."""
    m = _SERVITA.search(_COMMENTO.sub("", html))
    if m is None:
        return None
    dal, al = _canonico(m.group(1)), _canonico(m.group(2))
    return next((p for p in parti if p["commi_dal"] == dal and p["commi_al"] == al), None)


def _numero(comma: str) -> Optional[int]:
    m = re.match(r"\s*(\d+)", comma or "")
    return int(m.group(1)) if m else None


def parte_del_comma(parti: list[dict[str, Any]], comma: str) -> Optional[dict[str, Any]]:
    """The part whose commi hold *comma* («773», «773-bis»), or None.

    A comma with a suffix sits after its number («773-bis» after 773), so it is placed by its
    number: a part ending at «100» holds «100-bis». None when no part's range holds it.
    """
    numero = _numero(comma)
    if numero is None:
        return None
    for p in parti:
        dal, al = _numero(p["commi_dal"]), _numero(p["commi_al"])
        if dal is not None and al is not None and dal <= numero <= al:
            return p
    return None


# --- the comma a reference asks for -----------------------------------------------------

_ARTICOLO = re.compile(rf"\b(?:art|articolo)\.?\s*\d+(?:[\s-]*(?:{_SUFFISSI})\b)?", re.IGNORECASE)
# Right after the article: «, comma 773», «co. 773», «c. 773» (never the «c.» of «l.c.» or «c.c.»),
# «commi 773 e 774», «773° comma».
_DOPO = re.compile(
    rf"[\s,]*(?:(?:commi|comma|co\.|(?<![a-z]\.)c\.)\s*({_COMMA})|({_COMMA})\s*[°º]\s*comma\b)",
    re.IGNORECASE,
)
# Right before the article: «comma 773 dell'art. 1», «commi 773 e 774 dell'art. 1».
_PRIMA = re.compile(
    rf"\b(?:comma|commi)\s+({_COMMA})(?:\s*(?:,|e|-|–)\s*{_COMMA})*\s*,?\s*(?:dell['’]|del|dello)?\s*$",
    re.IGNORECASE,
)


def comma_richiesto(riferimento: str) -> Optional[str]:
    """The comma a citation names for its article («art. 1, comma 773, L. 296/2006» -> «773»).

    Only a comma attached to the first article cited: right after it («, comma 773», «co.
    773», «c. 773», «773° comma», «commi 773 e 774»: the first) or right before it («comma
    773 dell'art. 1»). A comma of another article later in the reference («come mod. da art.
    1, comma 5, l. 92/2012») and the «c.» of «l.c.» or «c.c.» are not it. Canonical
    («773-bis»); None when none.
    """
    testo = riferimento or ""
    articolo = _ARTICOLO.search(testo)
    if articolo is None:
        return None
    dopo = _DOPO.match(testo, articolo.end())
    if dopo is not None:
        return _canonico(dopo.group(1) or dopo.group(2))
    prima = _PRIMA.search(testo[max(0, articolo.start() - 60):articolo.start()])
    return _canonico(prima.group(1)) if prima else None


def contiene_comma(testo: str, comma: str) -> bool:
    """Whether a part's text has the comma's own line («773. …», «773-bis. …»)."""
    m = re.match(rf"(\d+)(?:-({_SUFFISSI}))?$", comma or "", re.IGNORECASE)
    if not m:
        return False
    suffisso = rf"[ \t-]*{m.group(2)}" if m.group(2) else ""
    # [ \t], never \s: under (?m) a \s* from every line start crossed the blank lines after
    # it, quadratic in a text of many empty lines.
    return re.search(rf"(?mi)^[ \t]*\(*{m.group(1)}{suffisso}[ \t]*\)*[ \t]*\.", testo or "") is not None
