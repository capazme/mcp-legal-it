# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/visualex_api/services/akn_parser.py at eca698dc.
# VisuaLex's file is itself a port of this project's parser; this is the merge of the two.
# From VisuaLex, unchanged: the hardened XML parser, rubriche, abrogati, the accents of a
# rubrica, ``presentable_title``, the per-article FRBRWork dates, the Dispositivo part.
# From mcp-legal-it: which text serves the default lookup (issue #47, plus the approving-decree
# rule below), the looser component names of some annexes, the annex API, ``article_keys``.
# New in the merge: ``<table>`` rendered as a Markdown table (both parsers lost the cells),
# the Normattiva position of each part, and structlog replaced by a line on stderr. And one
# documented change to VisuaLex's ``normalize_article_key``: a suffix written in two words
# ("135 sex decies", as Normattiva's tree prints it) is joined when the joined form is a
# suffix of the table ("135-sexdecies"); VisuaLex's version keeps "135-sex-decies", which no
# request spells, so the existence check declared the article missing (sent upstream).

"""Pure parser for Akoma Ntoso 3.0 XML exported by Normattiva (caricaAKN).

No network access — XML string in, structured ``ParsedAct`` out. Handles both
AKN structures emitted by Normattiva:

- **flat**: ``<article eId="art_N">`` directly under the body (laws, decrees,
  Costituzione);
- **component**: each article is a ``<doc name="PART-art. N">`` inside
  ``<attachments>/<attachment>`` (codici: c.c., c.p.; the annexes of an act).

The AKN namespace (``http://docs.oasis-open.org/legaldocml/ns/akn/3.0``) is the
default namespace; all element lookups use ``local-name()`` so the namespace can
be ignored.

The export transliterates every accent ("attivita'", "e'"): its article text is
never VisuaLex's ``article_text`` (that is the page's, ``normattiva_html``).
"""

import re
import sys
from dataclasses import dataclass, field

from lxml import etree

from .article_suffixes import ARTICLE_SUFFIX_ALTERNATION


_AGGIORNAMENTO_MARKER = "-----------"


# ---------------------------------------------------------------------------
# Rubriche (article headings)
# ---------------------------------------------------------------------------
#
# Normattiva's article TREE carries no rubriche — every <li> holds a bare
# number — so an index built from it can only show numbers. The AKN export does
# carry them, in two different shapes depending on the act's structure:
#
#   flat acts (leggi, decreti)  the rubrica is the <heading>, which the renderer
#                               emits on the "### Art. N." line;
#   component acts (codici)     there is no <heading>; the rubrica is a
#                               parenthesised block of its own, right after the
#                               repeated "Art. N." line.
#
# Measured over the committed fixtures: 3248/3249 for the codice civile,
# 995/995 for the codice penale, 50/51 for L. 241/1990, 104/109 for
# D.Lgs. 231/2001. The Costituzione yields 0, which is correct — its articles
# have no rubriche.

# Everything after "Art." on the heading line. What of it belongs to the article
# id and what is the rubrica cannot be decided by pattern: "Art. 2409 bis" is an
# id with a space in it, while "Art. 3 Motivazione" is an id plus a rubrica. The
# caller knows the key, so the id is consumed by normalising against it.
_RUBRICA_FROM_HEADING = re.compile(r"^#+\s*Art\.?\s*(.+)$")
# A third shape: the rubrica opens the body block instead of standing alone —
# "(Potere discrezionale del giudice nell'applicazione della pena: limiti) Nei
# limiti stabiliti dalla legge…" (art. 132 c.p.).
_RUBRICA_LEADING_PAREN = re.compile(r"^\((.{3,200}?)\)", re.S)

# An abrogated article carries no rubrica because it carries no content. Saying
# so is more useful than leaving the row blank — the reader cannot otherwise
# tell "repealed" from "we could not find the title".
_ABROGATO = re.compile(
    r"^\(*\s*(?:articolo\s+)?(?:abrogat|soppress)|^\(*\s*articolo\s+da\s+ritenersi\s+soppress",
    re.IGNORECASE,
)


def is_abrogato(article_text: str | None) -> bool:
    """Whether the rendered article says it has been repealed."""
    if not article_text:
        return False
    blocks = [b.strip() for b in article_text.strip().split("\n") if b.strip()]
    # blocks[0] is the "### Art. N" heading; a component act repeats "Art. N."
    # on the next line. The statement, when there is one, follows.
    body = " ".join(blocks[1:]).strip()
    body = re.sub(r"^Art\.?\s*[\w.-]+\.?\s*", "", body).strip()
    return bool(_ABROGATO.match(body))

# Words whose final apostrophe is a genuine troncamento, not a stand-in for an
# accent. Without this list "un po'" would become "un pò".
_TRONCAMENTI = frozenset({
    "po", "da", "fa", "sta", "va", "di", "be", "ca", "mo", "to", "de", "su", "fu",
})

_ACCENTED = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù"}

_TRANSLITTERATED_WORD = re.compile(r"\b([A-Za-zÀ-ÿ]+)([aeiou])'(?![A-Za-zÀ-ÿ])")


def _restore_accents(text: str) -> str:
    """Undo the AKN export's accent transliteration, for rubriche only.

    Normattiva's AKN writes every accented final vowel as vowel+apostrophe
    ("responsabilita'", "e'"). In the article TEXT this is left alone — that
    text is a data contract and must not be rewritten. In a rubrica it is a
    title shown in an index, short and nominal, where the transliteration reads
    as a defect.

    Conservative by construction: only a word-final vowel+apostrophe is touched,
    and never for the handful of words where the apostrophe is a real
    troncamento. Words ending in -che' take the acute accent (perché), the rest
    take the grave.
    """
    def replace(match: re.Match) -> str:
        stem, vowel = match.group(1), match.group(2)
        if (stem + vowel).lower() in _TRONCAMENTI:
            return match.group(0)
        if vowel == "e" and stem.lower().endswith("ch"):
            return stem + "é"
        return stem + _ACCENTED[vowel]

    # A bare "e'" is the verb è, and carries no stem for the pattern above.
    text = re.sub(r"(?<![A-Za-zÀ-ÿ])e'(?![A-Za-zÀ-ÿ])", "è", text)
    return _TRANSLITTERATED_WORD.sub(replace, text)


# "… professione forense. (13G00018)", and the older acts' "(030U1398)": the
# Gazzetta's code for the act, which a heading does not need.
_GAZZETTA_CODE = re.compile(r"\s*\.?\s*\((?:\d{2}[A-Z]\d{5}|\d{3}[A-Z]\d{4})\)\s*$")
# A final full stop, unless it closes an abbreviation ("c.p.c.", "S.p.A.").
_FINAL_STOP = re.compile(r"(?<!\.[A-Za-z])\.$")


def presentable_title(raw: str | None) -> str:
    """An act's AKN title as a heading (the dossier names each act once, with it).

    Three repairs, each measured on Normattiva's export: the Gazzetta code at the
    end goes (both of its shapes); the amendment brackets "((…))" are unwrapped
    and the space they leave before a comma or a closing parenthesis closed up;
    transliterated accents are restored as in a rubrica ("nonche'" -> "nonché").
    One final full stop goes too, never one that closes an abbreviation. Only for
    the title: never used on article text (root rule 23).
    """
    if not raw:
        return ""
    text = " ".join(raw.split())
    text = _GAZZETTA_CODE.sub("", text)
    text = text.replace("((", " ").replace("))", " ")
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = _FINAL_STOP.sub("", " ".join(text.split())).strip()
    return _restore_accents(text)


def extract_rubrica(article_text: str | None, key: str | None = None) -> str | None:
    """The rubrica of a rendered article, or None when it has none.

    `key` is the article's canonical key. It is what separates the id from the
    title on the heading line: an ordinal suffix is part of the id ("Art. 2409
    bis"), and without the key the suffix itself gets read as the rubrica.
    """
    if not article_text:
        return None
    blocks = [b.strip() for b in article_text.strip().split("\n") if b.strip()]
    if not blocks:
        return None

    match = _RUBRICA_FROM_HEADING.match(blocks[0])
    if match and key:
        tokens = match.group(1).split()
        # Consume the LONGEST token prefix that still normalises to this
        # article's key; whatever follows is the rubrica.
        consumed = 0
        for i in range(1, len(tokens) + 1):
            # rstrip the trailing dot: flat acts write "Art. 3." where the
            # key is "3", and without this the id is never consumed and the
            # rubrica on the same line is lost.
            if normalize_article_key(" ".join(tokens[:i]).rstrip(".")) == key:
                consumed = i
        if consumed:
            candidate = " ".join(tokens[consumed:]).strip().strip("().").strip()
            if candidate:
                return _restore_accents(" ".join(candidate.split()))

    # Component acts carry no <heading>: the rubrica is a parenthesised span
    # right after the article number. It appears in three shapes — a block of
    # its own, the opening of the body block, or split across lines mid-phrase
    # ("(Potere discrezionale del giudice nell'applicazione della pena:" /
    # "limiti)", art. 132 c.p.) — so the lines are joined before matching
    # rather than examined one by one.
    # Two kinds of preamble sit between the heading and the rubrica and have to
    # be stepped over first: the article number repeated ("Art. 1."), and — on
    # the FIRST article of a component part — the part's own title in capitals
    # ("CODICE CIVILE"). Everything from the first parenthesised block onwards
    # is then joined, because the span itself can be split across lines.
    tail = []
    for block in blocks[1:6]:
        if not tail:
            if block.startswith("("):
                tail.append(block)
                continue
            stripped = re.sub(r"^Art\.?\s*", "", block).rstrip(".")
            if key and normalize_article_key(stripped) == key:
                continue          # the repeated article number
            if block == block.upper() and len(block) < 90:
                continue          # the part title
            break                 # real body text: there is no rubrica here
        else:
            tail.append(block)

    match = _RUBRICA_LEADING_PAREN.match(" ".join(tail)) if tail else None
    if match:
        return _restore_accents(" ".join(match.group(1).split()))
    return None


# ---------------------------------------------------------------------------
# Article key normalization
# ---------------------------------------------------------------------------


def normalize_article_key(numero_articolo: str) -> str:
    """Normalize an article reference to the canonical key form.

    Examples: ``"art. 2 bis"`` -> ``"2-bis"``, ``"2043"`` -> ``"2043"``,
    ``"art_2-bis"`` -> ``"2-bis"``, ``"2 BIS"`` -> ``"2-bis"``.
    """
    if not numero_articolo:
        return ""

    key = numero_articolo.strip().lower()
    # Drop leading "art_" (eId form) or "art."/"articolo"/"art" word.
    key = re.sub(r"^art_", "", key)
    key = re.sub(r"^\s*articol[oi]\b\.?\s*", "", key)
    key = re.sub(r"^\s*art\b\.?\s*", "", key)
    key = key.strip()

    # Unify separators between the number and an ordinal suffix: a space, a dash
    # or nothing all collapse to a single dash. e.g. "2 bis" / "2bis" -> "2-bis".
    # The table is the shared one: numbering goes far past "decies"
    # ("2409 octiesdecies" c.c., "25 undevicies" d.lgs. 231/2001), and the short
    # list this used to carry left "25terdecies" to the fallback below, which
    # cannot tell a suffix from a rubrica.
    suffix_alt = ARTICLE_SUFFIX_ALTERNATION
    m = re.match(rf"^(\d+)\s*[-\s]?\s*({suffix_alt})$", key)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Plain number (possibly with trailing punctuation/spaces).
    m = re.match(r"^(\d+)\b", key)
    if m and re.fullmatch(rf"\d+(?:\s*[-\s]\s*(?:{suffix_alt}))?", key):
        return key.replace(" ", "-")

    # A suffix the tree writes in two words ("135 sex decies", l. 633/1941) is the
    # suffix it spells ("135-sexdecies"): joined only when the joined form is one.
    # One separator between the parts (a dash with blanks around it, or blanks): never
    # several optional blank runs side by side, which split a long run of blanks many ways.
    m = re.match(r"^(\d+)(?:\s*-\s*|\s+)([a-z]+)(?:\s*-\s*|\s+)([a-z]+)$", key)
    if m and re.fullmatch(suffix_alt, m.group(2) + m.group(3)):
        return f"{m.group(1)}-{m.group(2)}{m.group(3)}"

    # Fallback: collapse internal whitespace to dashes, strip stray chars.
    # This is where the shapes the table cannot spell land — "270 bis.1" ->
    # "270-bis.1", "314/2" — and they
    # need nothing more. A bare digit after an ordinal is a dotted sub-number
    # ("171 octies 1" in the tree of l. 633/1941 is ~art171octies.1 on
    # Normattiva), so it joins with a dot: the tree's spelling, the archive's
    # "171-octies-1" and the request's "171-octies.1" share one key.
    key = re.sub(r"\s+", "-", key)
    key = re.sub(r"-{2,}", "-", key).strip("-")
    key = re.sub(r"(?<=[a-z])-(\d+)$", r".\1", key)
    return key


# ---------------------------------------------------------------------------
# Component parts
# ---------------------------------------------------------------------------

# A component act can bundle more than one PART (see ``_parse_component``). The
# default lookup targets the dominant part (the code body); a caller may request
# another part by name. ``_PART_ALIASES`` maps a caller-facing hint to a
# substring of the real AKN PART name.
#: Name given to the flat <article> elements of a component act. They are the
#: enacting provisions, which Normattiva exposes as the "Dispositivo" annex.
_DISPOSITIVO_PART = "Dispositivo"

_PART_ALIASES = {
    # The codice civile AKN export bundles the preleggi as a separate part named
    # "Disposizioni sulla legge in generale".
    "preleggi": "disposizioni sulla legge in generale",
}

#: A part hint that names the part by its Normattiva position, the ":k" of an URN
#: (";104:2" is the codice del processo amministrativo, the export's second part).
_POSITION_HINT = re.compile(r"^:(\d+)$")


def position_hint(position: "str | int") -> str:
    """The part hint for the part at Normattiva position *position* (the URN's ``:k``)."""
    return f":{position}"


@dataclass
class ParsedPart:
    """One PART of a component act (e.g. the code body, or the preleggi)."""

    name: str
    articles: dict[str, str] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    # Article key -> ISO date of the text in force for that article, read from
    # the article's own FRBRWork/FRBRdate. Component acts only.
    dates: dict[str, str] = field(default_factory=dict)
    # Normattiva's number for the part, the ":k" of its URN: see ``_part_positions``.
    # 0 for the Dispositivo, which is the act's own body and has no ":k".
    position: int = 0

    @property
    def article_count(self) -> int:
        return len(self.order)


# ---------------------------------------------------------------------------
# ParsedAct
# ---------------------------------------------------------------------------

# "Allegato I.7", and the annexes that carry their title after the identifier:
# "Allegato 1 Codice del processo amministrativo" (d.lgs. 104/2010).
_ANNEX_NAME_RE = re.compile(r"^allegato\s+(?P<id>\S+?)\.?(?:\s.*)?$", re.IGNORECASE | re.S)


def annex_id_of(part_name: str) -> str | None:
    """The annex identifier of a part name (``"Allegato I.7"`` -> ``"i.7"``), else None.

    The identifier is the act's own ("Allegato 1" of d.lgs. 104/2010), not the
    part's Normattiva position (that annex is ``:2``): see ``ParsedPart.position``.
    """
    m = _ANNEX_NAME_RE.match((part_name or "").strip())
    return m.group("id").lower() if m else None


@dataclass
class ParsedAct:
    title: str
    articles: dict[str, str] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    # Mirrors the dominant part's ``dates``; empty for flat acts, whose
    # lifecycle is recorded at act level only.
    dates: dict[str, str] = field(default_factory=dict)
    structure: str = "flat"
    # All component parts keyed by their AKN PART name (the code body of a
    # codice, the preleggi, the annexes of an act; the Dispositivo of a codice).
    # ``articles``/``order`` hold the default lookup: the body of the act, or the
    # dominant part when the act is a decree approving the code it annexes.
    parts: dict[str, ParsedPart] = field(default_factory=dict)
    # Name of the part that serves the default lookup; "" when it is the body.
    main_part: str = ""

    def article(self, numero_articolo: str, part: str | None = None) -> str | None:
        """Return the markdown text of an article, or ``None`` if absent.

        Accepts ``"2043"``, ``"art. 2043"``, ``"2-bis"``, ``"2 bis"``. When
        ``part`` is given (e.g. ``"preleggi"``, or ``":2"`` for the part at that
        Normattiva position), the lookup targets that component part instead of
        the dominant one, and ``None`` is returned if the part is unknown.
        """
        key = normalize_article_key(numero_articolo)
        if part:
            matched = self._resolve_part(part)
            return matched.articles.get(key) if matched is not None else None
        return self.articles.get(key)

    def article_keys(self, part: str | None = None) -> list[str]:
        """Keys of the articles of a component part (the default lookup when ``part`` is None)."""
        if part:
            matched = self._resolve_part(part)
            return list(matched.order) if matched is not None else []
        return list(self.order)

    def full_text(self, part: str | None = None) -> str:
        """Return all articles joined as markdown, prefixed by the act title.

        When ``part`` is given, only that component part is rendered (headed by
        the part's own name); an empty string is returned if the part is unknown.
        """
        if part:
            matched = self._resolve_part(part)
            if matched is None:
                return ""
            title = matched.name
            source_order, source_articles = matched.order, matched.articles
        else:
            title = self.title
            source_order, source_articles = self.order, self.articles
        out: list[str] = []
        if title:
            out.append(f"# {title}")
        for key in source_order:
            out.append(source_articles[key])
        return "\n\n".join(out).strip()

    def _resolve_part(self, query: str) -> "ParsedPart | None":
        """Resolve a part hint to a :class:`ParsedPart`: ``":k"`` by position, else exact then substring."""
        q = (query or "").strip().lower()
        if not q:
            return None
        m = _POSITION_HINT.match(q)
        if m:
            return self.part_at(int(m.group(1)))
        q = _PART_ALIASES.get(q, q)
        for name, part in self.parts.items():
            if name.lower() == q:
                return part
        for name, part in self.parts.items():
            if q in name.lower():
                return part
        return None

    def part_at(self, position: int) -> "ParsedPart | None":
        """The part at Normattiva position *position* (the URN's ``:k``), else None."""
        if position < 1:
            return None
        for part in self.parts.values():
            if part.position == position:
                return part
        return None

    def part_position(self, name: str | None = None) -> int:
        """Normattiva position of a part (the default lookup's when *name* is None).

        0 for the body, and 0 when the position is shared by more than one part
        ("Allegato I.4" and "Allegato I.4-Tabella A" are one entry of the tree):
        the URN's ``:k`` would not say which of them is meant.
        """
        part = self.parts.get(self.main_part if name is None else name)
        return self._unique(part.position) if part is not None else 0

    def _unique(self, position: int) -> int:
        if position < 1:
            return 0
        same = [p for p in self.parts.values() if p.position == position]
        return position if len(same) == 1 else 0

    def part_article_count(self, part: str | None = None) -> int:
        """Article count of a component part (dominant part when ``part`` is None)."""
        if part:
            matched = self._resolve_part(part)
            return matched.article_count if matched is not None else 0
        return len(self.order)

    def part_title(self, part: str | None = None) -> str:
        """Display title: the selected part's name (falling back to the act
        title if the part is unknown), or the act title when ``part`` is None."""
        if part:
            matched = self._resolve_part(part)
            if matched is not None:
                return matched.name
        return self.title

    def rubriche(self, part: str | None = None) -> dict[str, str]:
        """Article key -> rubrica, for every article that has one.

        Built for the index: Normattiva's article tree carries only numbers, so
        this is where the titles come from. Articles without a rubrica are
        absent from the map rather than present with an empty value.
        """
        matched = self._resolve_part(part) if part else None
        articles = matched.articles if matched else self.articles
        out: dict[str, str] = {}
        for key, text in articles.items():
            rubrica = extract_rubrica(text, key)
            if rubrica:
                out[key] = rubrica
        return out

    def abrogati(self, part: str | None = None) -> list[str]:
        """Keys of the articles this act declares repealed."""
        matched = self._resolve_part(part) if part else None
        articles = matched.articles if matched else self.articles
        return [key for key, text in articles.items() if is_abrogato(text)]

    @property
    def article_count(self) -> int:
        return len(self.order)

    # --- annexes -----------------------------------------------------------

    def annex_names(self) -> list[str]:
        """Names of the annex parts ("Allegato I.7", ...), in document order."""
        return [name for name in self.parts if annex_id_of(name)]

    def _resolve_annex(self, annex_id: str) -> "ParsedPart | None":
        # Exact identifier match: "I.1" must never resolve to "I.11".
        wanted = (annex_id or "").strip().lower()
        for name, part in self.parts.items():
            if annex_id_of(name) == wanted:
                return part
        return None

    def annex_article(self, annex_id: str, numero_articolo: str) -> str | None:
        """Text of an article of an annex, or None if the annex or article is absent."""
        part = self._resolve_annex(annex_id)
        if part is None:
            return None
        return part.articles.get(normalize_article_key(numero_articolo))

    def annex_text(self, annex_id: str) -> str | None:
        """Every article of an annex, headed by its name; None if the annex is absent."""
        part = self._resolve_annex(annex_id)
        if part is None:
            return None
        return self.full_text(part=part.name)

    def annex_name(self, annex_id: str) -> str | None:
        part = self._resolve_annex(annex_id)
        return part.name if part is not None else None

    def annex_position(self, annex_id: str) -> int:
        """Normattiva position of the annex the act calls *annex_id*, 0 if it has none or shares it."""
        part = self._resolve_annex(annex_id)
        return self._unique(part.position) if part is not None else 0


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def _strip_modification_markers(text: str) -> str:
    """Remove the literal ``(( ))`` Normattiva modification markers."""
    text = text.replace("((", "").replace("))", "")
    return text


def _clean_text(text: str) -> str:
    """Collapse whitespace runs and trim, preserving paragraph breaks."""
    text = _strip_modification_markers(text)
    # Normalize spaces/tabs (not newlines) within lines.
    text = re.sub(r"[ \t]+", " ", text)
    # Trim trailing spaces on each line.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    # Collapse 3+ blank lines to a single blank line.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _collect(node, parts: list[str]) -> None:
    """Recursively collect text, dropping ``<del>`` subtrees, keeping ``<ins>``."""
    local = etree.QName(node).localname if isinstance(node.tag, str) else ""
    if local == "del":
        return  # drop deleted text entirely
    if node.text:
        parts.append(node.text)
    for child in node:
        _collect(child, parts)
        if child.tail:
            parts.append(child.tail)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
#
# The Tariffa of d.P.R. 131/1986 is a <table> inside a <content>, next to its
# <p>: "1. Atti traslativi a titolo oneroso … | 9 per cento". Reading only
# content/p lost every cell — the rates of the imposta di registro — in both
# parsers. A table is rendered as a Markdown table: one line per row, the first
# row as the header (the export has no other way to say which row heads the
# table), every cell kept, "|" escaped, a cell's lines joined by spaces. A cell
# spanning rows keeps its column (empty in the rows below), a cell spanning
# columns leaves empty cells after it, a table nested in a cell is read into that
# cell once (its rows are not the outer table's).

def _cell_text(cell) -> str:
    """A cell's text on one line: its paragraphs (and any table inside it) one space apart."""
    blocks = [child for child in cell if isinstance(child.tag, str) and etree.QName(child).localname in ("p", "table")]
    if blocks:
        pieces = []
        if cell.text and cell.text.strip():
            pieces.append(cell.text)
        for child in blocks:
            if etree.QName(child).localname == "table":
                pieces.extend(_flatten(c) for c in _own_cells(child))
            else:
                pieces.append(_flatten(child))
        text = " ".join(pieces)
    else:
        text = _flatten(cell)
    return " ".join(text.split()).replace("|", "\\|")


def _own_rows(table) -> list:
    """The table's own rows, never those of a table nested in one of its cells."""
    return [tr for tr in table.iter("{*}tr") if next(tr.iterancestors("{*}table"), None) is table]


def _own_cells(table) -> list:
    return [cell for tr in _own_rows(table) for cell in tr.xpath(f"{_local('th')}|{_local('td')}")]


def _span(cell, attr: str) -> int:
    try:
        return max(1, min(int(cell.get(attr) or 1), 50))
    except ValueError:
        return 1


def _render_table(table) -> str:
    rows: list[list[str]] = []
    # Column -> (text, rows still to cover) of a cell spanning down from a row above: it
    # holds its column in the rows it covers, so the cells after it do not slide left.
    carried: dict[int, list] = {}
    for tr in _own_rows(table):
        row: list[str] = []
        col = 0

        def fill_carried():
            nonlocal col
            while col in carried:
                text, left = carried[col]
                row.append("")  # the spanning cell's text stays in its first row
                carried[col][1] = left - 1
                if carried[col][1] == 0:
                    del carried[col]
                col += 1

        for cell in tr.xpath(f"{_local('th')}|{_local('td')}"):
            fill_carried()
            text = _cell_text(cell)
            down = _span(cell, "rowspan")
            for i in range(_span(cell, "colspan")):
                row.append(text if i == 0 else "")
                if down > 1:
                    carried[col] = [text, down - 1]
                col += 1
        fill_carried()
        if row:
            rows.append(row)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    lines = []
    for i, row in enumerate(rows):
        cells = row + [""] * (width - len(row))
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("|" + "|".join([" --- "] * width) + "|")
    return "\n".join(lines)


def _content_text(container) -> str:
    """The text of the ``<content>`` blocks under *container*: its paragraphs and its tables, in order.

    Without a table this is exactly the ``content/p`` reading the parser always had.
    """
    blocks: list[str] = []
    for content in container.xpath(f".//{_local('content')}"):
        for child in content.xpath(f"{_local('p')}|{_local('table')}"):
            if etree.QName(child).localname == "table":
                # A blank line on each side: a Markdown table must open its own block.
                blocks.append(f"\n{_render_table(child)}\n")
            else:
                blocks.append(_flatten(child))
    return "\n".join(blocks).strip()


# ---------------------------------------------------------------------------
# Flat structure
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    return f"*[local-name()='{tag}']"


def _child_text(elem, tag: str) -> str:
    children = elem.xpath(_local(tag))
    if not children:
        return ""
    return _flatten(children[0])


def _flatten(elem) -> str:
    """Flatten an element to plain text, ins-aware."""
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        _collect(child, parts)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def _render_flat_article(article) -> str:
    """Render a flat ``<article>`` element to markdown."""
    num = _child_text(article, "num").strip()
    heading = ""
    headings = article.xpath(_local("heading"))
    if headings:
        heading = _flatten(headings[0]).strip()

    header = f"### {num}".rstrip() if num else "###"
    if heading:
        header = f"{header} {heading}".strip()

    lines: list[str] = [header]

    paragraphs = article.xpath(_local("paragraph"))
    if paragraphs:
        for para in paragraphs:
            lines.append(_render_flat_paragraph(para))
    else:
        # No commi: dump any content directly.
        body = _content_text(article)
        if body:
            lines.append(body)

    return _clean_text("\n\n".join(part for part in lines if part.strip()))


def _render_flat_paragraph(para) -> str:
    """Render a ``<paragraph>`` (comma), including any ``<point>`` (lettere)."""
    num = _child_text(para, "num").strip()
    chunks: list[str] = []

    points = para.xpath(f".//{_local('point')}")
    if points:
        intro = para.xpath(f".//{_local('intro')}")
        intro_text = _flatten(intro[0]).strip() if intro else ""
        head = f"{num} {intro_text}".strip() if num else intro_text
        if head:
            chunks.append(head)
        for point in points:
            p_num = _child_text(point, "num").strip()
            p_body = _content_text(point)
            if not p_body:
                p_body = _flatten(point).strip()
            chunks.append(f"  {p_num} {p_body}".rstrip())
    else:
        body = _content_text(para)
        if not body:
            body = _flatten(para).strip()
        chunks.append(f"{num} {body}".strip() if num else body)

    return "\n".join(chunk for chunk in chunks if chunk.strip())


def _parse_flat(root) -> tuple[dict[str, str], list[str]]:
    """Parse flat ``<article eId="art_N">`` elements under the body."""
    articles: dict[str, str] = {}
    order: list[str] = []
    for article in root.xpath(f"//{_local('body')}//{_local('article')}"):
        eid = article.get("eId", "")
        if not eid:
            continue
        key = normalize_article_key(eid)
        if not key or key in articles:
            continue
        rendered = _render_flat_article(article)
        if rendered:
            articles[key] = rendered
            order.append(key)
    return articles, order


# ---------------------------------------------------------------------------
# Component structure
# ---------------------------------------------------------------------------

# "CODICE CIVILE-art. 2043", and the looser forms of some annexes in the same
# exports: "Allegato I.4-art 1", "Allegati - Allegato I.01 art. 1".
_DOC_NAME_RE = re.compile(r"^(?P<part>.+?)(?:\s*-\s*|\s+)art\.?\s*(?P<num>\d.*)$", re.IGNORECASE)
# Index-wide prefix of some annex names ("Allegati - Allegato I.01").
_PART_PREFIX_RE = re.compile(r"^allegati\s*-\s*", re.IGNORECASE)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Normattiva numbers the entries of its tree, the ":k" of an URN, and an export's part
# names are those entries, sometimes with a sub-part after a dash: "Allegato I.4-Tabella
# A" belongs to entry "Allegato I.4", "Allegati - Allegato I.01" to entry "Allegati".
# Entries without articles count too ("Indice generale", "Convention", "Prospetto").
# Measured live on 21/10/2026: c.c. preleggi :1, codice :2; c.p. :1; d.lgs. 104/2010
# "Indice generale" :1, codice del processo amministrativo :2; l. 654/1975 Convenzione :2;
# d.lgs. 36/2023 Allegato I.11 :12 (the dash rule makes it 12; counting every part name
# would make it 16).
_TREE_ENTRY_RE = re.compile(r"\s*-\s*")


def _doc_work_date(doc) -> str | None:
    """The FRBRWork date of a component <doc>, or None.

    Expression and Manifestation dates sit beside it and are the act's, not
    the article's — the Work date is the one that moves when the article's
    text is replaced.
    """
    dates = doc.xpath(
        f".//{_local('meta')}//{_local('FRBRWork')}/{_local('FRBRdate')}/@date"
    )
    for value in dates:
        value = (value or "").strip()
        if _ISO_DATE.match(value):
            return value
    return None


def _render_component_doc(doc, num_label: str) -> str:
    """Render a component ``<doc>`` element to markdown."""
    paragraphs = doc.xpath(f".//{_local('mainBody')}//{_local('paragraph')}")
    body_chunks: list[str] = []
    update_chunks: list[str] = []

    for para in paragraphs:
        para_text = _content_text(para)
        if not para_text:
            para_text = "\n".join(_flatten(p) for p in para.xpath(f".//{_local('p')}")).strip()
        if not para_text:
            continue
        # Modification-history blocks start with a separator line / AGGIORNAMENTO.
        if para_text.startswith(_AGGIORNAMENTO_MARKER) or "AGGIORNAMENTO" in para_text.split("\n")[0]:
            update_chunks.append(para_text)
        else:
            body_chunks.append(para_text)

    body = "\n\n".join(body_chunks).strip()
    # The body already embeds "Art. N." + rubrica inline; add a markdown header
    # for consistency with the flat renderer.
    header = f"### Art. {num_label}".rstrip()
    parts = [header]
    if body:
        parts.append(body)
    if update_chunks:
        parts.append("\n\n".join(update_chunks))
    return _clean_text("\n\n".join(parts))


def _parse_component(root) -> tuple[dict[str, ParsedPart], str]:
    """Parse component ``<doc name="PART-art. N">`` elements into parts.

    Returns ``(parts, main_part_name)`` where ``parts`` maps each PART name to a
    :class:`ParsedPart`. For codici with multiple parts (e.g. the preleggi plus
    the main code), every part is kept and the dominant one (most articles) is
    reported as ``main_part_name``.

    Each part's ``position`` is Normattiva's number for it (``_part_positions``).
    """
    docs = root.xpath(f"//{_local('attachments')}//{_local('doc')}")

    # Group docs by PART prefix; number the entries of Normattiva's tree as they appear.
    by_part: dict[str, list[tuple[str, object]]] = {}
    positions: dict[str, int] = {}
    tree_entries: dict[str, int] = {}
    for doc in docs:
        name = (doc.get("name") or "").strip()
        m = _DOC_NAME_RE.match(name)
        raw_part = (m.group("part") if m else name).strip()
        entry = _TREE_ENTRY_RE.split(raw_part, maxsplit=1)[0].strip()
        if entry and entry not in tree_entries:
            tree_entries[entry] = len(tree_entries) + 1
        part = _PART_PREFIX_RE.sub("", raw_part)
        if part and part not in positions:
            positions[part] = tree_entries.get(entry, 0)
        if not m:
            continue
        num_raw = m.group("num").strip()
        by_part.setdefault(part, []).append((num_raw, doc))

    if not by_part:
        return {}, ""

    parts: dict[str, ParsedPart] = {}
    for part_name, entries in by_part.items():
        articles: dict[str, str] = {}
        order: list[str] = []
        dates: dict[str, str] = {}
        for num_raw, doc in entries:
            key = normalize_article_key(num_raw)
            if not key or key in articles:
                continue
            rendered = _render_component_doc(doc, num_raw)
            if rendered:
                articles[key] = rendered
                order.append(key)
                work_date = _doc_work_date(doc)
                if work_date:
                    dates[key] = work_date
        if articles:
            parts[part_name] = ParsedPart(name=part_name, articles=articles, order=order, dates=dates,
                                          position=positions.get(part_name, 0))

    if not parts:
        return {}, ""

    # The dominant part (largest) is the main code; it is the default lookup.
    main_part = max(parts, key=lambda p: parts[p].article_count)
    return parts, main_part


# The enacting formula of a decree that approves the text it annexes: "E' approvato il testo
# del Codice civile" (r.d. 262/1942), "Il testo definitivo del codice penale … e' approvato"
# (r.d. 1398/1930), "E' approvato il codice del processo amministrativo di cui all'allegato 1"
# (d.lgs. 104/2010), "È approvato l'unito testo unico" (TULPS), "Sono approvate le norme …".
# A law that executes a treaty says something else ("è autorizzato a ratificare", "Piena ed
# intera esecuzione è data", l. 654/1975) and may call the treaty itself "approvata" ("la
# Convenzione …, approvata dall'Assemblea generale"): the formula, not the word, decides.
_OGGETTO = r"(?:testo|codic\w*|regolament\w*|norme|disposizioni|tariff\w*)"
_APPROVA = re.compile(
    r"\b(?:è|e'|sono)\s+approvat[oaie]\b[^.;]{0,60}?\b" + _OGGETTO + r"\b"
    r"|\b(?:testo|codic\w*)\b[^.;]{0,160}?\b(?:è|e')\s+approvat[oaie]\b",
    re.IGNORECASE,
)
def _body_approves_annex(articles: dict[str, str], order: list[str]) -> bool:
    """Whether the act's body opens by approving the text it annexes (see ``_APPROVA``)."""
    return any(_APPROVA.search(articles[key]) for key in order[:2])


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def _extract_title(root) -> str:
    titles = root.xpath(f"//{_local('docTitle')}")
    if titles:
        text = _flatten(titles[0]).strip()
        if text:
            return text
    aliases = root.xpath(f"//{_local('FRBRalias')}")
    if aliases:
        val = aliases[0].get("value")
        if val:
            return val
    return ""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_akn(xml: str) -> ParsedAct:
    """Parse an Akoma Ntoso XML string into a ``ParsedAct``.

    An act has flat ``<article>`` elements in its body and may have component
    ``<doc name="...-art. N">`` elements in its attachments. Which one serves the
    default lookup depends on which is the act's text:

    - a codice (c.c., c.p., c.p.a.) is a short decree (2-3 body articles) that
      approves the code it annexes: the dominant part wins, and the decree's own
      articles stay reachable as the ``Dispositivo`` part;
    - an act with annexes (D.Lgs. 36/2023: 233 body articles, Allegato I.7 with
      50) keeps its body. Letting the largest annex win served "art. 30" from
      Allegato I.7 under the URN of the Code's own art. 30 (issue #47);
    - so does a law that executes a treaty: l. 654/1975 has 4 articles and the
      Convention 25, and its art. 3 (repealed) is the law's, never the Convention's.

    Every component part stays reachable (``parts``, ``part_at``, ``annex_article``).
    """
    if isinstance(xml, str):
        xml_bytes = xml.encode("utf-8")
    else:
        xml_bytes = xml
    # recover=True keeps a malformed export usable. resolve_entities=False and
    # no_network=True close the XXE / billion-laughs surface that lxml leaves
    # open by default; huge_tree is dropped because it lifts libxml2's limits on
    # entity expansion and nesting depth and the fixtures parse without it.
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(xml_bytes, parser=parser)
    except etree.XMLSyntaxError as exc:
        # An empty body or an HTML error page reaches here. The caller treats an
        # article-less act as "AKN had nothing to say" and falls back to the
        # HTML path, so return that shape rather than propagating — but say so.
        print(f"[akn_parser] AKN payload is not parseable XML ({len(xml_bytes)} bytes): {exc}",
              file=sys.stderr)
        return ParsedAct(title="")
    if root is None:
        print(f"[akn_parser] AKN payload parsed to no root element ({len(xml_bytes)} bytes)",
              file=sys.stderr)
        return ParsedAct(title="")

    title = _extract_title(root)

    parts, main_part = _parse_component(root)
    flat_articles, flat_order = _parse_flat(root)
    if (parts and parts[main_part].article_count > len(flat_order)
            and (not flat_order or _body_approves_annex(flat_articles, flat_order))):
        main = parts[main_part]
        # A component act ALSO carries a couple of flat <article> elements at the
        # top. They are not duplicates of the components: they are the enacting
        # provisions — "È approvato il testo del Codice civile…" — which
        # Normattiva serves as the act's *Dispositivo*, its own annex.
        #
        # They stay out of `articles`/`order`, because a text lookup for "art. 1"
        # must keep resolving to art. 1 of the code body. But they are kept as
        # their own part, so the index can label the Dispositivo with its own
        # titles instead of borrowing the code body's — which is what happened
        # while this part was discarded: art. 1 of the Dispositivo was shown as
        # "Capacità giuridica", the rubrica of a different article entirely.
        if flat_articles:
            parts = dict(parts)
            parts[_DISPOSITIVO_PART] = ParsedPart(
                name=_DISPOSITIVO_PART, articles=flat_articles, order=flat_order
            )
        return ParsedAct(
            title=title,
            articles=main.articles,
            order=main.order,
            dates=main.dates,
            structure="component",
            parts=parts,
            main_part=main_part,
        )

    return ParsedAct(
        title=title,
        articles=flat_articles,
        order=flat_order,
        structure="flat",
        parts=parts,
    )
