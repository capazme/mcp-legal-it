"""Symmetric tool-name prefix rewriting between corpus (bare) and targets."""
from __future__ import annotations

import re

_STRIP_RE = re.compile(r"legal-it:([a-z0-9_]+)")


def strip_prefixes(text: str) -> tuple[str, list[str]]:
    """Remove every 'legal-it:' prefix; return (new_text, sorted unique tool names found)."""
    found: set[str] = set()

    def repl(m: re.Match[str]) -> str:
        found.add(m.group(1))
        return m.group(1)

    return _STRIP_RE.sub(repl, text), sorted(found)


def find_bare_tools(text: str, vocabulary: list[str]) -> list[str]:
    """Vocabulary tool names that appear unprefixed in the text (word-bounded).

    The (?!\\w|\\.\\w) lookahead excludes file-path/extension contexts like
    `data/contributo_unificato.json` (tool name followed by .word).
    """
    hits = []
    for tool in vocabulary:
        if re.search(rf"(?<![\w:]){re.escape(tool)}(?!\w|\.\w)", text):
            hits.append(tool)
    return sorted(hits)


def add_prefixes(text: str, tools: list[str], template: str = "legal-it:{}") -> str:
    """Prefix every word-bounded occurrence of each tool name.

    The lookbehind excludes '_' and ':' so mcp__legal-it__X and legal-it:X are
    never touched — add_prefixes(strip_prefixes(t)) is byte-identical.
    """
    for tool in sorted(set(tools), key=len, reverse=True):
        text = re.sub(
            rf"(?<![\w:]){re.escape(tool)}(?!\w|\.\w)", template.format(tool), text
        )
    return text
