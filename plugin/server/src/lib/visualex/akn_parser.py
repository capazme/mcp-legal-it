"""Pure parser for Akoma Ntoso 3.0 XML exported by Normattiva (caricaAKN).

No network access — XML string in, structured ``ParsedAct`` out. Handles both
AKN structures emitted by Normattiva:

- **flat**: ``<article eId="art_N">`` directly under the body (laws, decrees,
  Costituzione);
- **component**: each article is a ``<doc name="PART-art. N">`` inside
  ``<attachments>/<attachment>`` (codici: c.c., c.p.).

The AKN namespace (``http://docs.oasis-open.org/legaldocml/ns/akn/3.0``) is the
default namespace; all element lookups use ``local-name()`` so the namespace can
be ignored.
"""

import re
from dataclasses import dataclass, field

from lxml import etree


_AGGIORNAMENTO_MARKER = "-----------"


# ---------------------------------------------------------------------------
# Article key normalization
# ---------------------------------------------------------------------------

_ORDINAL_SUFFIXES = (
    "bis", "ter", "quater", "quinquies", "sexies", "septies",
    "octies", "novies", "decies",
)


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
    suffix_alt = "|".join(_ORDINAL_SUFFIXES)
    m = re.match(rf"^(\d+)\s*[-\s]?\s*({suffix_alt})$", key)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Plain number (possibly with trailing punctuation/spaces).
    m = re.match(r"^(\d+)\b", key)
    if m and re.fullmatch(rf"\d+(?:\s*[-\s]\s*(?:{suffix_alt}))?", key):
        return key.replace(" ", "-")

    # Fallback: collapse internal whitespace to dashes, strip stray chars.
    key = re.sub(r"\s+", "-", key)
    key = re.sub(r"-{2,}", "-", key).strip("-")
    return key


# ---------------------------------------------------------------------------
# Component parts
# ---------------------------------------------------------------------------

# A component act can bundle more than one PART (see ``_parse_component``). The
# default lookup targets the dominant part (the code body); a caller may request
# another part by name. ``_PART_ALIASES`` maps a caller-facing hint to a
# substring of the real AKN PART name.
_PART_ALIASES = {
    # The codice civile AKN export bundles the preleggi as a separate part named
    # "Disposizioni sulla legge in generale".
    "preleggi": "disposizioni sulla legge in generale",
}


@dataclass
class ParsedPart:
    """One PART of a component act (e.g. the code body, or the preleggi)."""

    name: str
    articles: dict[str, str] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)

    @property
    def article_count(self) -> int:
        return len(self.order)


# ---------------------------------------------------------------------------
# ParsedAct
# ---------------------------------------------------------------------------

_ANNEX_NAME_RE = re.compile(r"^allegato\s+(?P<id>\S+)$", re.IGNORECASE)


def annex_id_of(part_name: str) -> str | None:
    """The annex identifier of a part name (``"Allegato I.7"`` -> ``"i.7"``), else None."""
    m = _ANNEX_NAME_RE.match((part_name or "").strip())
    return m.group("id").lower() if m else None


@dataclass
class ParsedAct:
    title: str
    articles: dict[str, str] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    structure: str = "flat"
    # All component parts keyed by their AKN PART name (the code body of a
    # codice, the preleggi, the annexes of an act). ``articles``/``order`` hold
    # the default lookup: the body of the act, or the dominant part when the act
    # is a short decree whose real text is a component (the codici).
    parts: dict[str, ParsedPart] = field(default_factory=dict)
    # Name of the part that serves the default lookup; "" when it is the body.
    main_part: str = ""

    def article(self, numero_articolo: str, part: str | None = None) -> str | None:
        """Return the markdown text of an article, or ``None`` if absent.

        Accepts ``"2043"``, ``"art. 2043"``, ``"2-bis"``, ``"2 bis"``. When
        ``part`` is given (e.g. ``"preleggi"``), the lookup targets that
        component part instead of the dominant one, and ``None`` is returned if
        the part is unknown.
        """
        key = normalize_article_key(numero_articolo)
        if part:
            matched = self._resolve_part(part)
            return matched.articles.get(key) if matched is not None else None
        return self.articles.get(key)

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
        """Resolve a part hint to a :class:`ParsedPart` (exact then substring)."""
        q = (query or "").strip().lower()
        if not q:
            return None
        q = _PART_ALIASES.get(q, q)
        for name, part in self.parts.items():
            if name.lower() == q:
                return part
        for name, part in self.parts.items():
            if q in name.lower():
                return part
        return None

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
        # No commi: dump any content/p directly.
        body = "\n".join(
            _flatten(p) for p in article.xpath(f".//{_local('content')}/{_local('p')}")
        ).strip()
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
            p_body = "\n".join(
                _flatten(p) for p in point.xpath(f".//{_local('content')}/{_local('p')}")
            ).strip()
            if not p_body:
                p_body = _flatten(point).strip()
            chunks.append(f"  {p_num} {p_body}".rstrip())
    else:
        body = "\n".join(
            _flatten(p) for p in para.xpath(f".//{_local('content')}/{_local('p')}")
        ).strip()
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


def _render_component_doc(doc, num_label: str) -> str:
    """Render a component ``<doc>`` element to markdown."""
    paragraphs = doc.xpath(f".//{_local('mainBody')}//{_local('paragraph')}")
    body_chunks: list[str] = []
    update_chunks: list[str] = []

    for para in paragraphs:
        ps = para.xpath(f".//{_local('content')}/{_local('p')}")
        if not ps:
            ps = para.xpath(f".//{_local('p')}")
        para_text = "\n".join(_flatten(p) for p in ps).strip()
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
    reported as ``main_part_name`` — it becomes the act's default lookup.
    """
    docs = root.xpath(f"//{_local('attachments')}//{_local('doc')}")

    # Group docs by PART prefix.
    by_part: dict[str, list[tuple[str, object]]] = {}
    for doc in docs:
        name = (doc.get("name") or "").strip()
        m = _DOC_NAME_RE.match(name)
        if not m:
            continue
        part = _PART_PREFIX_RE.sub("", m.group("part").strip())
        num_raw = m.group("num").strip()
        by_part.setdefault(part, []).append((num_raw, doc))

    if not by_part:
        return {}, ""

    parts: dict[str, ParsedPart] = {}
    for part_name, entries in by_part.items():
        articles: dict[str, str] = {}
        order: list[str] = []
        for num_raw, doc in entries:
            key = normalize_article_key(num_raw)
            if not key or key in articles:
                continue
            rendered = _render_component_doc(doc, num_raw)
            if rendered:
                articles[key] = rendered
                order.append(key)
        if articles:
            parts[part_name] = ParsedPart(name=part_name, articles=articles, order=order)

    if not parts:
        return {}, ""

    # The dominant part (largest) is the main code; it is the default lookup.
    main_part = max(parts, key=lambda p: parts[p].article_count)
    return parts, main_part


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

    - a codice (c.c., c.p.) is a short approving decree (2-3 body articles) whose
      code is a component part: the dominant part wins, as before;
    - an act with annexes (D.Lgs. 36/2023: 233 body articles, Allegato I.7 with
      50) keeps its body. Letting the largest annex win served "art. 30" from
      Allegato I.7 under the URN of the Code's own art. 30 (issue #47).

    Every component part stays reachable (``parts``, ``annex_article``).
    """
    if isinstance(xml, str):
        xml_bytes = xml.encode("utf-8")
    else:
        xml_bytes = xml
    # Recover from minor encoding declaration mismatches.
    parser = etree.XMLParser(recover=True, huge_tree=True)
    root = etree.fromstring(xml_bytes, parser=parser)

    title = _extract_title(root)

    parts, main_part = _parse_component(root)
    flat_articles, flat_order = _parse_flat(root)
    if parts and parts[main_part].article_count > len(flat_order):
        main = parts[main_part]
        return ParsedAct(
            title=title,
            articles=main.articles,
            order=main.order,
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
