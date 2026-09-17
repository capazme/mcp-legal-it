"""Freeze what the local calculation tools answer, grouped by the table they read.

`test_read_only_contract.py` proves these tools write nothing;
`test_tool_annotations.py` proves they are advertised as read-only. Neither says
anything about whether they still compute the same thing. A table gets refreshed
(`indici_foi.json`, `tassi_legali.json`, `parametri_forensi.json`,
`tabella_danno_bio.json`), a bracket is mistyped, a band boundary moves by one
euro -- and every test still passes while the advice changes.

The reference lives in `tests/fixtures/golden/calcoli_locali/`, **one file per
set of tables** the tools in it read: `indici_foi.json` for the 10 tools that
read FOI alone, `indici_foi+tassi_legali.json` for the 2 that read both,
`nessuna_tabella.json` for the 104 pure algorithms (date arithmetic, codice
fiscale, IVA, capital gains formulas) that no table affects. A refreshed FOI
series therefore shows up as a diff in exactly the files whose tools read FOI,
and the failure message names the dataset before it names the tools.

The grouping is derived, not hand-kept: `scripts/audit_tool_annotations.py`
reads each tool's `@sourced(...)` declaration and the module-level tables its
reachable code references. If a tool starts reading a new table, the mapping in
the manifest no longer matches the code and the test says so instead of quietly
comparing against the wrong group.

Two things make the comparison reproducible:

* the run is hermetic (its own `HOME`, `TMPDIR`, `MCP_CACHE_DIR`, caching off)
  and offline -- these tools reach no service, so the answer is a pure function
  of the arguments;
* the clock is pinned (`LEGAL_TODAY`/`LEGAL_NOW`), because tools like
  `prescrizione_diritti`, `scadenze_*` and `calcolo_eta_anagrafica` are "as of
  today" by design. Without the pin they would drift with the calendar and the
  test would have to give up on the most interesting half of the surface.

Regenerate the reference deliberately, after reading the diff:

    GOLDEN_UPDATE=1 pytest tests/unit/test_golden_calcoli.py -q

Run just this file with:

    pytest tests/unit/test_golden_calcoli.py -q
"""

from __future__ import annotations

import difflib
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile

import pytest

from .mcp_harness import (
    REPO,
    answer_text,
    arguments_for,
    call_tools,
    local_read_only,
    server_env,
    tools,
)

GOLDEN_DIR = REPO / "tests/fixtures/golden/calcoli_locali"
MANIFEST = GOLDEN_DIR / "_manifest.json"
PINNED_TODAY = "2026-09-15"
PINNED_NOW = "2026-09-15T12:00:00"
# Answers are stored truncated: a few tools return whole documents, and a
# reference file nobody can read in review is a reference file nobody checks.
TRUNCATED_AT = 4000
#: Tools with no table at all land in this group.
NO_TABLE_GROUP = "nessuna_tabella"


def _normalize(text: str) -> str:
    """Trailing whitespace is formatting; the rest is the value."""
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _group_name(datasets: list[str]) -> str:
    return "+".join(datasets) if datasets else NO_TABLE_GROUP


def _audit():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from audit_tool_annotations import Audit  # type: ignore[import-not-found]

        return Audit(pathlib.Path(REPO / "plugin/server/src"))
    finally:
        sys.path.pop(0)


def _datasets_by_tool() -> dict[str, list[str]]:
    """The mapping the manifest must agree with, straight from the code."""
    audit = _audit()
    return {name: audit.datasets(fq) for fq, name in audit.tools.items()}


@pytest.fixture(scope="module")
def surface():
    """The local read-only surface, called once, pinned and offline."""
    local = local_read_only(tools())
    arguments = {tool["name"]: arguments_for(tool) for tool in local}
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="golden-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="golden-tmp-"))
    env = server_env(
        sandbox,
        scratch,
        extra={
            "LEGAL_TODAY": PINNED_TODAY,
            "LEGAL_NOW": PINNED_NOW,
            "LEGAL_CACHE": "off",
            "TZ": "UTC",
        },
    )
    replies = call_tools(env, list(arguments), arguments, timeout=900)
    yield local, arguments, replies
    shutil.rmtree(sandbox, ignore_errors=True)
    shutil.rmtree(scratch, ignore_errors=True)


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _load_groups(manifest: dict) -> dict[str, dict]:
    """{group file: {tool: {"arguments": ..., "expected": ...}}}."""
    out = {}
    for name in manifest["groups"]:
        path = GOLDEN_DIR / name
        assert path.exists(), "manifest names a missing group file: %s" % name
        out[name] = json.loads(path.read_text(encoding="utf-8"))["tools"]
    return out


def _current(arguments: dict, replies: dict) -> dict:
    return {
        name: _normalize(answer_text(replies.get(name, {})))[:TRUNCATED_AT]
        for name in arguments
    }


def _write_reference(arguments: dict, current: dict, datasets: dict[str, list[str]]) -> None:
    groups: dict[str, dict] = {}
    for tool, datasets_ in datasets.items():
        groups.setdefault(_group_name(datasets_), {})[tool] = {
            "arguments": arguments[tool],
            "expected": current[tool],
        }
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for stale in GOLDEN_DIR.glob("*.json"):
        if stale.name != MANIFEST.name and stale.stem not in groups:
            stale.unlink()
    manifest = {
        "note": (
            "Expected answers of the local read-only tools, split by the data "
            "tables they read, pinned to LEGAL_TODAY/LEGAL_NOW and truncated at "
            "%d characters. One file per set of tables: a refreshed table shows "
            "up as a diff in the groups whose name lists it. Regenerate with: "
            "GOLDEN_UPDATE=1 pytest tests/unit/test_golden_calcoli.py" % TRUNCATED_AT
        ),
        "pinned_today": PINNED_TODAY,
        "pinned_now": PINNED_NOW,
        "truncated_at": TRUNCATED_AT,
        "groups": {
            name: {
                "datasets": [] if name == NO_TABLE_GROUP else name.split("+"),
                "tools": sorted(entries),
            }
            for name, entries in sorted(groups.items())
        },
        "tool_datasets": {tool: datasets_ for tool, datasets_ in sorted(datasets.items())},
    }
    for name, entries in groups.items():
        (GOLDEN_DIR / name).write_text(
            json.dumps(
                {
                    "datasets": [] if name == NO_TABLE_GROUP else name.split("+"),
                    "tools": entries,
                },
                indent=1,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    MANIFEST.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _datasets_in_answer(text: str, known: set[str]) -> set[str]:
    """Tables an answer declares, read from its own footer.

    Two renderings reach a host and both count: a dict answer carries the lines
    under a `dati_applicati` key, a string answer carries the markdown block. A
    reader that understood only the first would call the string-returning tools
    silent while they do declare their tables.
    """

    def label(line: str) -> str:
        return line.split(":")[0].strip().replace(" ", "_")

    declared: set[str] = set()
    for footer in re.findall(r'"dati_applicati":\s*\[(.*?)\]', text, re.S):
        declared.update(label(item) for item in re.findall(r'"([^"]+)"', footer))
    marker = "**Dati applicati**"
    if marker in text:
        declared.update(
            label(line[4:])
            for line in text.split(marker, 1)[1].splitlines()
            if line.startswith("> - ")
        )
    return {name for name in declared if name in known}


def test_local_calculation_tools_answer_the_recorded_values(surface):
    local, arguments, replies = surface
    current = _current(arguments, replies)

    answered = sorted(name for name, text in current.items() if text)
    assert len(answered) >= 0.9 * len(local), (
        "only %d/%d tools answered; the arguments or the server are broken: %s"
        % (len(answered), len(local), sorted(set(arguments) - set(answered))[:8])
    )

    datasets = _datasets_by_tool()
    if os.environ.get("GOLDEN_UPDATE") == "1":
        _write_reference(arguments, current, {name: datasets[name] for name in arguments})
        pytest.skip("reference regenerated in %s" % GOLDEN_DIR.relative_to(REPO))

    manifest = _load_manifest()
    groups = _load_groups(manifest)
    recorded = {tool: entry for entries in groups.values() for tool, entry in entries.items()}

    missing = sorted(set(recorded) - set(current))
    assert not missing, (
        "the reference records tools that no longer exist: %s -- regenerate with "
        "GOLDEN_UPDATE=1" % missing[:8]
    )
    added = sorted(set(current) - set(recorded))
    assert not added, (
        "tools with no recorded value: %s -- regenerate with GOLDEN_UPDATE=1" % added[:8]
    )

    # The grouping is derived from the code, so a tool that starts reading
    # another table has to be re-recorded rather than compared against the
    # wrong group.
    mapping_changed = sorted(
        tool
        for tool in current
        if manifest["tool_datasets"].get(tool) != datasets[tool]
    )
    assert not mapping_changed, (
        "these tools now read a different set of tables than the manifest says: "
        "%s -- regenerate with GOLDEN_UPDATE=1"
        % [(tool, manifest["tool_datasets"].get(tool), datasets[tool]) for tool in mapping_changed[:6]]
    )

    arguments_changed = sorted(
        tool
        for tool, entry in recorded.items()
        if arguments[tool] != entry["arguments"]
    )
    assert not arguments_changed, (
        "the harness now generates different arguments for: %s -- if that is "
        "intentional, regenerate the reference with GOLDEN_UPDATE=1"
        % arguments_changed[:8]
    )

    changed = {
        tool: (entry["expected"], current[tool])
        for tool, entry in recorded.items()
        if entry["expected"] != current[tool]
    }
    if not changed:
        return

    # Which table explains the change? The one read by every changed tool is
    # the prime suspect; the others are listed with how many they cover.
    counts = {
        dataset: sum(1 for tool in changed if dataset in datasets[tool])
        for dataset in sorted({d for tool in changed for d in datasets[tool]})
    }
    prime = [dataset for dataset, hits in counts.items() if hits == len(changed)]
    report = [
        "%d of %d recorded answers changed." % (len(changed), len(current)),
        "",
        "tables involved: %s"
        % ", ".join("%s (%d/%d tools)" % (d, n, len(changed)) for d, n in counts.items()),
        "likely trigger: %s" % (", ".join(prime) if prime else "none alone -- see the diffs"),
        "affected groups: %s" % ", ".join(
            name for name, entries in groups.items() if set(entries) & set(changed)
        ),
        "",
    ]
    for tool in sorted(changed):
        expected, actual = changed[tool]
        diff = [
            line.rstrip()
            for line in difflib.unified_diff(
                expected.splitlines(), actual.splitlines(), "recorded", "now", lineterm="", n=0
            )
            if not line.startswith(("---", "+++", "@@"))
        ]
        report.append("%s [%s]\n  %s" % (tool, "+".join(datasets[tool]) or "-", "\n  ".join(diff[:10])))

    assert not changed, (
        "%s\n\nIf the change is intended (a new rate, a corrected parameter, a "
        "fixed bracket), regenerate the reference with: GOLDEN_UPDATE=1 pytest "
        "tests/unit/test_golden_calcoli.py" % "\n".join(report)
    )


def test_the_reference_partitions_the_surface_by_table(surface):
    """One file per table set: no tool twice, no tool missing, names honest."""
    local, _, _ = surface
    manifest = _load_manifest()
    groups = _load_groups(manifest)
    datasets = _datasets_by_tool()

    seen: list[str] = []
    for name, entries in groups.items():
        for tool in entries:
            seen.append(tool)
            assert name == _group_name(datasets[tool]), (
                "%s is filed under %s but reads %s"
                % (tool, name, "+".join(datasets[tool]) or "-")
            )
        declared = manifest["groups"][name]["datasets"]
        assert declared == (name.split("+") if name != NO_TABLE_GROUP else []), (
            "group %s declares %s" % (name, declared)
        )
    assert len(seen) == len(set(seen)), (
        "a tool appears in more than one group: %s"
        % sorted({t for t in seen if seen.count(t) > 1})[:8]
    )
    assert set(seen) == {tool["name"] for tool in local}, (
        "the groups and the local read-only surface disagree: %s"
        % sorted(set(seen) ^ {tool["name"] for tool in local})[:8]
    )


def test_the_reference_stores_results_not_failures(surface):
    """A frozen error is not a value: it means the arguments need fixing.

    The harness generates arguments from the schema, and the schema does not
    declare every closed vocabulary (company types, CCNL levels, catastrophic
    categories are validated inside the tools). When one of those drifts, the
    tool answers with an error -- and an error is not something to freeze as
    the expected answer.
    """
    recorded = {
        tool: entry["expected"]
        for entries in _load_groups(_load_manifest()).values()
        for tool, entry in entries.items()
    }
    markers = ('"errore"', "Error calling tool", "validation error", '"valido": false')
    broken = {
        name: next(m for m in markers if m in text)
        for name, text in recorded.items()
        if any(m in text for m in markers)
    }
    assert not broken, "recorded answers are failures, not results: %s" % broken


def test_answers_declare_the_tables_they_read(surface):
    """An answer's `dati_applicati` footer is the provenance a reader checks.

    For every tool whose answer carries a footer, the tables it names must be
    exactly the tables the code reads: a missing one hides a table's vintage
    (the tool gives advice whose currency is invisible), an extra one claims a
    table the tool never opened.
    """
    _, _, replies = surface
    datasets = _datasets_by_tool()
    audit_stems = _audit().available_datasets
    disagreements = {}
    declaring, silent = [], sorted(
        tool
        for tool, tables in datasets.items()
        if tables and tool in replies and not _datasets_in_answer(answer_text(replies[tool]), audit_stems)
    )
    for tool, reply in replies.items():
        declared = _datasets_in_answer(answer_text(reply), audit_stems)
        if not declared:
            continue
        declaring.append(tool)
        if declared != set(datasets.get(tool, [])):
            disagreements[tool] = {
                "declared": sorted(declared),
                "reads": sorted(datasets.get(tool, [])),
            }
    assert len(declaring) > 50, (
        "only %d answers carry a provenance footer; they are what makes the "
        "tables' vintage visible" % len(declaring)
    )
    assert not silent, (
        "these tools answer from a hand-maintained table and say nothing about "
        "its vintage: %s" % silent
    )
    assert not disagreements, (
        "answers and code disagree about which tables were used: %s" % disagreements
    )


def test_the_reference_is_pinned_complete_and_readable(surface):
    """The fixture itself: pinned, complete, reviewable, machine-independent."""
    local, _, _ = surface
    manifest = _load_manifest()
    assert manifest["pinned_today"] == PINNED_TODAY
    assert manifest["pinned_now"] == PINNED_NOW

    recorded = {
        tool: entry["expected"]
        for entries in _load_groups(manifest).values()
        for tool, entry in entries.items()
    }
    assert len(recorded) > 100, "the reference covers only %d tools" % len(recorded)
    assert len(recorded) == len(local_read_only(tools()))

    too_long = {name: len(text) for name, text in recorded.items() if len(text) > TRUNCATED_AT}
    assert not too_long, "answers stored beyond the truncation limit: %s" % too_long
    empty = sorted(name for name, text in recorded.items() if not text)
    assert not empty, "tools recorded with an empty answer: %s" % empty[:8]

    # A recorded answer must not carry the machine it was recorded on.
    leakage = {
        name: [needle for needle in (str(pathlib.Path.home()), "golden-sandbox-") if needle in text]
        for name, text in recorded.items()
    }
    leaked = {name: hits for name, hits in leakage.items() if hits}
    assert not leaked, "the reference leaks local paths: %s" % list(leaked)[:5]
