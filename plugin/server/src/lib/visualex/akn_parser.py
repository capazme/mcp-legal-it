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
# ParsedAct
# ---------------------------------------------------------------------------

@dataclass
class ParsedAct:
    title: str
    articles: dict[str, str] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    structure: str = "flat"

    def article(self, numero_articolo: str) -> str | None:
        """Return the markdown text of an article, or ``None`` if absent.

        Accepts ``"2043"``, ``"art. 2043"``, ``"2-bis"``, ``"2 bis"``.
        """
        key = normalize_article_key(numero_articolo)
        return self.articles.get(key)

    def full_text(self) -> str:
        """Return all articles joined as markdown, prefixed by the act title."""
        parts: list[str] = []
        if self.title:
            parts.append(f"# {self.title}")
        for key in self.order:
            parts.append(self.articles[key])
        return "\n\n".join(parts).strip()

    @property
    def article_count(self) -> int:
        return len(self.order)


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

_DOC_NAME_RE = re.compile(r"^(?P<part>.+?)-art\.\s*(?P<num>.+)$", re.IGNORECASE)


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


def _parse_component(root) -> tuple[dict[str, str], list[str], str]:
    """Parse component ``<doc name="PART-art. N">`` elements.

    For codici with multiple parts (e.g. preleggi + main code), prefer the part
    with the most articles (the main code).
    """
    docs = root.xpath(f"//{_local('attachments')}//{_local('doc')}")

    # Group docs by PART prefix.
    by_part: dict[str, list[tuple[str, object]]] = {}
    for doc in docs:
        name = (doc.get("name") or "").strip()
        m = _DOC_NAME_RE.match(name)
        if not m:
            continue
        part = m.group("part").strip()
        num_raw = m.group("num").strip()
        by_part.setdefault(part, []).append((num_raw, doc))

    if not by_part:
        return {}, [], ""

    # Choose the dominant part (largest), which is the main code.
    main_part = max(by_part, key=lambda p: len(by_part[p]))

    articles: dict[str, str] = {}
    order: list[str] = []
    for num_raw, doc in by_part[main_part]:
        key = normalize_article_key(num_raw)
        if not key or key in articles:
            continue
        rendered = _render_component_doc(doc, num_raw)
        if rendered:
            articles[key] = rendered
            order.append(key)

    return articles, order, main_part


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

    Auto-detects flat vs component structure: if the act has component
    ``<doc name="...-art. N">`` elements, those win (they carry the full set for
    codici); otherwise the flat ``<article>`` elements are used.
    """
    if isinstance(xml, str):
        xml_bytes = xml.encode("utf-8")
    else:
        xml_bytes = xml
    # Recover from minor encoding declaration mismatches.
    parser = etree.XMLParser(recover=True, huge_tree=True)
    root = etree.fromstring(xml_bytes, parser=parser)

    title = _extract_title(root)

    comp_articles, comp_order, _ = _parse_component(root)
    if comp_articles:
        return ParsedAct(
            title=title,
            articles=comp_articles,
            order=comp_order,
            structure="component",
        )

    flat_articles, flat_order = _parse_flat(root)
    return ParsedAct(
        title=title,
        articles=flat_articles,
        order=flat_order,
        structure="flat",
    )
