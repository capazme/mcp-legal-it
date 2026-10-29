"""scripts/token_report.py: the token measuring instrument (offline parts only).

The ``outputs`` measure needs a recorded tape, which is never committed, so only
its helpers are tested here; ``tools`` runs for real in a subprocess, because it
reads tools/list from a freshly imported server.
"""

import asyncio
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
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
    # The blocks are measured even when the listing no longer carries them
    # (mcp_legal_it/_listing.py drops additionalProperties:false and anyOf-null).
    assert report["blocks"]["additional_properties_false"]["count"] == 0
    assert report["blocks"]["anyof_null"]["count"] == 0
    assert report["blocks"]["accetta_precisione"]["count"] >= 1


def test_profile_narrows_the_surface(tmp_path):
    out = tmp_path / "calcoli.json"
    subprocess.run([sys.executable, str(REPO / "scripts" / "token_report.py"), "tools", "--profile", "calcoli",
                    "--json", str(out)],
                   check=True, capture_output=True, text=True, cwd=REPO,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "LEGAL_CACHE": "off"})
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["meta"]["profile"] == "calcoli"
    assert report["totals"]["tools"] > 0
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


def test_output_row_measures_text_structured_and_meta():
    text = "Art. 1284 c.c. — testo"
    row = token_report.output_row({
        "tool": "cite_law", "args": {"reference": "art. 1284 c.c."}, "missed_requests": 0,
        "wire": {"content": [{"type": "text", "text": text}], "structuredContent": {"result": text},
                 "_meta": {"k": "v"}, "isError": False},
    })
    assert row["call"] == 'cite_law {"reference": "art. 1284 c.c."}'
    assert row["text_chars"] == len(text)
    assert row["structured_chars"] == token_report.compact({"result": text})
    assert row["structured_duplicates_text"] is True
    assert row["meta_chars"] == token_report.compact({"k": "v"})
    # a calculator: the text is the structuredContent serialized, estimated as JSON
    data = {"totale": 1081.68, "nota": "abc"}
    calc = token_report.output_row({"tool": "interessi_legali", "args": {}, "missed_requests": 0,
                                    "wire": {"content": [{"type": "text", "text": json.dumps(data)}],
                                             "structuredContent": data}})
    assert calc["structured_duplicates_text"] is True
    assert calc["text_tokens"] == token_report.value_tokens(data)


def _report(calls, **meta):
    rows = [{"call": c, "text_chars": n, "text_tokens": n // 3, "structured_chars": n,
             "structured_duplicates_text": True, "meta_chars": 0, "wire_chars": 2 * n, "is_error": False,
             "missed_requests": missed} for c, n, missed in calls]
    totals = {k: sum(r[k] for r in rows) for k in ("text_chars", "text_tokens", "structured_chars", "meta_chars",
                                                   "wire_chars")}
    return {"measure": "outputs", "meta": {"sha": "x", "dirty": False, "fastmcp": "3.4.2", "clock": "c",
                                           "env": {}, "estimator": "e", **meta},
            "totals": totals, "calls": rows}


def _compare(tmp_path, base, head, capsys):
    (tmp_path / "a.json").write_text(json.dumps(base), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(head), encoding="utf-8")
    code = token_report.compare(tmp_path / "a.json", tmp_path / "b.json", top=5)
    return code, capsys.readouterr().out


def test_compare_fails_on_a_call_that_missed_the_tape(tmp_path, capsys):
    base = _report([("cite_law x", 8259, 0)])
    head = _report([("cite_law x", 137, 3)])  # an empty tape: a short error, not a saving
    code, out = _compare(tmp_path, base, head, capsys)
    assert code == 1
    assert "FAILED" in out and "head: `cite_law x`: 3 request(s) not on tape" in out


def test_compare_passes_clean_replays_and_warns_on_a_different_setup(tmp_path, capsys):
    base = _report([("cite_law x", 8259, 0)])
    head = _report([("cite_law x", 4000, 0)], fastmcp="4.1.4")
    code, out = _compare(tmp_path, base, head, capsys)
    assert code == 0
    assert "8,259 → 4,000" in out
    assert "Note: fastmcp differs" in out


def test_outputs_worker_env_keeps_only_the_pinned_server_variables(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2031-06-01")
    monkeypatch.setenv("AKN_DISABLED", "1")
    monkeypatch.setenv("UNRELATED", "kept")
    env = token_report._worker_env({"LEGAL_NOW": "2026-10-21T12:00:00"})
    assert env["LEGAL_NOW"] == "2026-10-21T12:00:00"
    assert "LEGAL_TODAY" not in env and "AKN_DISABLED" not in env
    assert env["UNRELATED"] == "kept"


def test_a_tape_on_a_tracked_path_inside_the_repo_is_refused(tmp_path):
    token_report._refuse_a_committable_tape(token_report.DEFAULT_TAPE.resolve())  # ignored: accepted
    token_report._refuse_a_committable_tape(tmp_path / "t.json.gz")  # outside the repo: accepted
    with pytest.raises(SystemExit):
        token_report._refuse_a_committable_tape((REPO / "docs" / "t.json.gz").resolve())


def test_the_replayer_counts_a_request_missing_from_the_tape(tmp_path, monkeypatch):
    import gzip

    import httpx

    sys.path.insert(0, str(REPO / "scripts"))
    from replay_mcp_outputs import install_tape_transport

    # install_tape_transport patches httpx.AsyncClient for the whole process: put it back after.
    monkeypatch.setattr(httpx.AsyncClient, "__init__", httpx.AsyncClient.__init__)
    tape = tmp_path / "empty.json.gz"
    with gzip.open(tape, "wt", encoding="utf-8") as fh:
        fh.write("{}")
    misses: list[str] = []
    install_tape_transport("replay", str(tape), misses)

    async def get():
        async with httpx.AsyncClient() as client:
            await client.get("https://example.invalid/x")

    with pytest.raises(httpx.ConnectError, match="not on tape"):
        asyncio.run(get())
    assert len(misses) == 1 and "https://example.invalid/x" in misses[0]


def test_compare_fails_on_a_call_that_errored(tmp_path, capsys):
    base = _report([("cite_law x", 8259, 0)])
    head = _report([("cite_law x", 300, 0)])
    head["calls"][0]["is_error"] = True
    code, out = _compare(tmp_path, base, head, capsys)
    assert code == 1
    assert "head: `cite_law x`: error" in out


def test_outputs_exits_1_when_a_call_failed(monkeypatch, tmp_path, capsys):
    failed = _report([("cite_law x", 137, 2)])
    monkeypatch.setattr(token_report, "measure_outputs", lambda args: failed)
    monkeypatch.setattr(sys, "argv", ["token_report.py", "outputs", "--tape", str(tmp_path / "t.json.gz")])
    assert token_report.main() == 1
    assert "FAILED" in capsys.readouterr().out
    monkeypatch.setattr(token_report, "measure_outputs", lambda args: _report([("cite_law x", 8259, 0)]))
    assert token_report.main() == 0


def test_a_tape_on_a_tracked_path_of_an_enclosing_repo_is_refused(tmp_path):
    import subprocess as sp

    outer = tmp_path / "outer"
    outer.mkdir()
    sp.run(["git", "init", "-q", str(outer)], check=True)
    (outer / ".gitignore").write_text("tapes/\n", encoding="utf-8")
    token_report._refuse_a_committable_tape(outer / "tapes" / "t.json.gz")  # ignored there: accepted
    with pytest.raises(SystemExit):
        token_report._refuse_a_committable_tape(outer / "docs" / "t.json.gz")  # not yet created, tracked path
