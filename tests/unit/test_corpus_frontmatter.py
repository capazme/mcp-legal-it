"""Tests for scripts/corpus/frontmatter.py (loaded via importlib like test_release_script.py)."""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "corpus_frontmatter", Path(__file__).parents[2] / "scripts" / "corpus" / "frontmatter.py"
)
fm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fm)

DOC = "---\nname: analisi-sinistro\ndescription: Analizza sinistri stradali,\n  sanitari e lavorativi.\n---\n\n# Corpo\n\nTesto.\n"

def test_split_join_roundtrip_is_byte_identical():
    lines, body = fm.split(DOC)
    assert lines[0] == "name: analisi-sinistro"
    assert body.startswith("\n# Corpo")
    assert fm.join(lines, body) == DOC

def test_split_rejects_missing_frontmatter():
    import pytest
    with pytest.raises(ValueError):
        fm.split("# no frontmatter\n")

def test_block_range_covers_continuation_lines():
    lines, _ = fm.split(DOC)
    start, end = fm.block_range(lines, "description")
    assert (start, end) == (1, 3)  # 'description:' + one indented continuation line
    assert fm.block_range(lines, "tools") is None

def test_strip_keys_removes_whole_blocks():
    lines, body = fm.split(DOC)
    lines2 = fm.append_lines(lines, ["tools: [cite_law]", 'prompt: {"name": "x", "args": []}'])
    stripped = fm.strip_keys(lines2, ["tools", "prompt"])
    assert stripped == lines
    assert fm.join(stripped, body) == DOC

def test_replace_line_swaps_in_place():
    lines = ["name: norma", "tools: cite_law, cerca_brocardi"]
    out = fm.replace_line(lines, "tools", "allowed-tools: mcp__legal-it__cite_law, mcp__legal-it__cerca_brocardi")
    assert out[1].startswith("allowed-tools:")
    assert out[0] == "name: norma"
