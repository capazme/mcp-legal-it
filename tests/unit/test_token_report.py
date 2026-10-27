"""scripts/token_report.py: the token measuring instrument (offline parts only).

The ``outputs`` measure needs a recorded tape, which is never committed, so only
its helpers are tested here; ``tools`` runs for real in a subprocess, because it
reads tools/list from a freshly imported server.
"""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from mcp_legal_it.tool_annotations import READ_ONLY, WRITES_FILES

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("token_report", REPO / "scripts" / "token_report.py")
token_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(token_report)


def test_schema_prose_counts_descriptions_at_any_depth_only():
    schema = {"description": "abc", "properties": {
        "description": {"type": "string", "description": "de"},  # a parameter named "description"
        "x": {"anyOf": [{"type": "string", "description": "f"}, {"type": "null"}]},
    }}
    assert token_report.schema_prose(schema) == 6


def test_anyof_null_overhead_measures_the_wrapper_and_the_null_default():
    param = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None, "description": "d"}
    count, chars = token_report.anyof_null_overhead({"properties": {"p": param, "q": {"type": "integer"}}})
    plain = {"type": "string", "description": "d"}
    assert count == 1
    assert chars == token_report.compact(param) - token_report.compact(plain)


def test_block_chars_follows_continuation_lines_until_the_next_label():
    desc = "Intro.\nVigenza: tabella 2026\ncontinua qui\nPrecisione: ESATTO\n\nAltro."
    assert token_report.block_chars(desc, ("Vigenza",)) == len("Vigenza: tabella 2026\n") + len("continua qui\n")
    assert token_report.block_chars(desc, ("Precisione",)) == len("Precisione: ESATTO\n")


def test_tokens_estimate_uses_the_documented_ratios():
    assert token_report.tokens(35, 0) == 10
    assert token_report.tokens(0, 30) == 10


def test_tools_report_covers_every_listed_tool(tmp_path):
    out = tmp_path / "tools.json"
    subprocess.run([sys.executable, str(REPO / "scripts" / "token_report.py"), "tools", "--json", str(out)],
                   check=True, capture_output=True, text=True, cwd=REPO,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "LEGAL_CACHE": "off"})
    report = json.loads(out.read_text(encoding="utf-8"))
    names = {r["name"] for r in report["tools"]}
    assert names == set(READ_ONLY | WRITES_FILES)
    t = report["totals"]
    assert t["tools"] == len(names)
    assert t["model_chars"] == sum(r["model_chars"] for r in report["tools"])
    assert t["total_tokens"] == t["tokens"] + t["instructions_tokens"]
    assert sum(g["tools"] for g in report["by_kind"].values()) == t["tools"]
    assert "?" not in report["by_kind"], "a tool without a kind tag"
    assert report["blocks"]["additional_properties_false"]["count"] >= 1


def test_profile_narrows_the_surface(tmp_path):
    out = tmp_path / "calcoli.json"
    subprocess.run([sys.executable, str(REPO / "scripts" / "token_report.py"), "tools", "--profile", "calcoli",
                    "--json", str(out)],
                   check=True, capture_output=True, text=True, cwd=REPO,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "LEGAL_CACHE": "off"})
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["meta"]["profile"] == "calcoli"
    assert set(report["by_kind"]) <= {"calcolo", "diagnostica"}


def test_tool_choice_tasks_name_only_listed_tools():
    """docs/benchmark/token-tasks.json: a renamed tool must not leave the task set pointing at nothing."""
    spec = json.loads((REPO / "docs" / "benchmark" / "token-tasks.json").read_text(encoding="utf-8"))
    tasks = spec["tasks"]
    assert 15 <= len(tasks) <= 20
    assert len({t["id"] for t in tasks}) == len(tasks)
    listed = set(READ_ONLY | WRITES_FILES)
    for t in tasks:
        e = t["expected"]
        assert e.get("required") or e.get("required_any"), t["id"]
        named = e.get("required", []) + e.get("required_any", []) + e.get("acceptable", []) + e.get("forbidden", [])
        assert set(named) <= listed, (t["id"], set(named) - listed)
        assert set(e.get("order", [])) <= set(e.get("required", [])), t["id"]
        for f in t["facts"]:
            re.compile(f["pattern"])
            assert f["verified_by"] in spec["verified_by_values"], (t["id"], f)


def test_subset_server_keeps_module_attribution_and_ignores_an_inherited_profile(tmp_path):
    """crea_server mounts the stock server (mounted tools have no fn); LEGAL_PROFILE in the shell is not measured."""
    out = tmp_path / "fonti.json"
    subprocess.run([sys.executable, str(REPO / "scripts" / "token_report.py"), "tools",
                    "--include-tags", "normativa,giurisprudenza", "--json", str(out)],
                   check=True, capture_output=True, text=True, cwd=REPO,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "LEGAL_CACHE": "off",
                        "LEGAL_PROFILE": "calcoli"})
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["meta"]["profile"] == "full"
    assert "?" not in report["by_module"]
    assert set(report["by_kind"]) <= {"normativa", "giurisprudenza"}
    assert report["totals"]["tools"] > 0
