"""Text-level frontmatter handling for the content corpus.

Deliberately NOT YAML-based: the corpus round-trip (migrate -> project) must be
byte-identical, so we only ever split on delimiter lines and insert/remove
whole lines. Re-serializing YAML would reorder keys and rewrap strings.
"""
from __future__ import annotations


def split(text: str) -> tuple[list[str], str]:
    """Split a markdown document into (frontmatter lines, body).

    The delimiters are excluded; body starts right after the closing '---\\n'.
    Raises ValueError when the document has no leading frontmatter.
    """
    if not text.startswith("---\n"):
        raise ValueError("document has no leading frontmatter")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise ValueError("frontmatter is not closed")
    return text[4:end].split("\n"), text[end + len("\n---\n"):]


def join(fm_lines: list[str], body: str) -> str:
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


def block_range(fm_lines: list[str], key: str) -> tuple[int, int] | None:
    """Half-open [start, end) index range of `key:` plus its indented continuation."""
    prefix = key + ":"
    for i, line in enumerate(fm_lines):
        if line == key or line.startswith(prefix):
            j = i + 1
            while j < len(fm_lines) and (fm_lines[j].startswith((" ", "\t")) or fm_lines[j] == ""):
                j += 1
            return i, j
    return None


def strip_keys(fm_lines: list[str], keys: list[str]) -> list[str]:
    out = list(fm_lines)
    for key in keys:
        rng = block_range(out, key)
        if rng is not None:
            del out[rng[0]:rng[1]]
    return out


def append_lines(fm_lines: list[str], new_lines: list[str]) -> list[str]:
    return list(fm_lines) + list(new_lines)


def replace_line(fm_lines: list[str], key: str, new_line: str) -> list[str]:
    rng = block_range(fm_lines, key)
    if rng is None:
        raise KeyError(key)
    if rng[1] - rng[0] != 1:
        raise ValueError(f"{key!r} spans multiple lines; replace_line handles single lines only")
    out = list(fm_lines)
    out[rng[0]] = new_line
    return out


def read_field(fm_lines: list[str], key: str) -> str | None:
    """Extract a (possibly multi-line) frontmatter field's raw value.

    Block-aware: uses block_range() so a multi-line value (continuation lines
    indented under `key:`) is read in full and joined with '\\n', instead of
    raising the way replace_line() does. Shared by build_claude_web (claude-web
    packaging) and the corpus projection engine's description_max_chars cap.
    """
    rng = block_range(fm_lines, key)
    if rng is None:
        return None
    first = fm_lines[rng[0]]
    _, _, after = first.partition(":")
    val_lines = [after.lstrip()] + list(fm_lines[rng[0] + 1 : rng[1]])
    return "\n".join(val_lines).strip()


def truncate_description(desc: str, max_chars: int) -> str:
    """Normalize whitespace UNCONDITIONALLY, then truncate at a word boundary.

    Shared by build_claude_web and the corpus projection engine's
    description_max_chars cap — one implementation, so claude-web behavior is
    unaffected by anything the projection engine layers on top (e.g. its
    dangling-connector trim, applied by the caller AFTER this function).
    """
    desc = " ".join(desc.split())
    if len(desc) <= max_chars:
        return desc
    truncated = desc[: max_chars - 3]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."
