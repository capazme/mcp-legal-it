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

The answers are not all values: a tool whose declared grade an unsourced table
cannot support refuses, and the refusal is part of what is frozen here (see
`test_the_reference_stores_results_not_failures`).

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

from src.lib import _data

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


def test_the_reference_stores_results_not_failures(surface, monkeypatch):
    """A frozen error is not a value: it means the arguments need fixing.

    The harness generates arguments from the schema, and the schema does not
    declare every closed vocabulary (company types, CCNL levels, catastrophic
    categories are validated inside the tools). When one of those drifts, the
    tool answers with an error -- and an error is not something to freeze as
    the expected answer.

    One error *is* an answer: `dati_non_affidabili`, the refusal a tool gives
    when the tables it rests on cannot support the grade it declares in its
    docstring (`src/lib/_precision.py`). It is checked rather than merely
    allowed, because "the reference may contain errors" would otherwise be a
    licence for any argument drift: a refusal is only legitimate for a tool
    whose tables are actually flagged, it must say the grade is `nessuna`, and
    its record must still name the tables it refused on.
    """
    recorded = {
        tool: entry["expected"]
        for entries in _load_groups(_load_manifest()).values()
        for tool, entry in entries.items()
    }
    refusals = {
        name: text
        for name, text in recorded.items()
        if '"dati_non_affidabili"' in text
    }
    markers = ('"errore"', "Error calling tool", "validation error", '"valido": false')
    broken = {
        name: next(m for m in markers if m in text)
        for name, text in recorded.items()
        if name not in refusals and any(m in text for m in markers)
    }
    assert not broken, "recorded answers are failures, not results: %s" % broken

    assert refusals, (
        "no refusal in the reference: either the policy stopped acting on the "
        "tables that are still unsourced, or the recorded answers were taken "
        "from a run that never reached it"
    )
    # The same date the reference was taken at: whether a table is flagged is a
    # property of the clock, and this check has to ask the same clock.
    monkeypatch.setenv("LEGAL_TODAY", PINNED_TODAY)
    tables = _datasets_by_tool()
    for name, text in refusals.items():
        assert '"effettiva":"nessuna"' in text, (
            "%s refuses without declaring that it claims no precision" % name
        )
        assert '"dati_applicati"' in text, (
            "%s refuses without naming the tables it refused on" % name
        )
        flagged = [
            dataset
            for dataset in tables.get(name, [])
            if _data.warnings([dataset])
        ]
        assert flagged, (
            "%s refused, but none of the tables it declares is flagged: %s"
            % (name, tables.get(name, []))
        )
    # Every tool the shipped tables take out of service has to be in the
    # reference, or a refusal could sit in the code without a frozen answer.
    # (Five before the TUS 346/1990 and CdS 126-bis reconciliations; three
    # remain -- codice_fiscale, decodifica_codice_fiscale, indennita_preavviso.)
    assert len(refusals) >= 3, (
        "only %d refusals recorded: a refusal that no longer happens is a change "
        "to inspect, and one that happens without being frozen is invisible"
        % len(refusals)
    )


def _opened_tables(reply: dict) -> set[str]:
    """Tables a call declared it opened, from the result `_meta`."""
    meta = ((reply or {}).get("result") or {}).get("_meta") or {}
    return set(meta.get("mcp-legal-it/opened_tables") or ())


def test_the_server_declares_the_tables_each_call_opened(surface):
    """The runtime oracle: what the process read, not what the walk thinks.

    `@sourced(...)` and the audit are both static -- they say which tables a
    tool's code *can* read. Every call now also reports, in its result `_meta`,
    which tables it *did* read, observed by the ledger that wraps the table
    constants (`src/lib/_ledger.py`). Comparing the two is the only check here
    that a reader the walk cannot follow fails: a table seen at runtime and not
    attributed to the tool by the audit means the audit is missing a path, which
    is exactly how three preloaded tables stayed invisible while six tools
    answered with no provenance at all.
    """
    _, _, replies = surface
    known = _datasets_by_tool()
    stamps = _audit().available_datasets
    undeclared: dict[str, list[str]] = {}
    opened_anywhere: set[str] = set()
    for tool, reply in replies.items():
        seen = _opened_tables(reply)
        if not seen:
            continue
        opened_anywhere |= seen
        unattributed = sorted(seen - set(known.get(tool, [])))
        if unattributed:
            undeclared[tool] = unattributed
        # What the call used has to be in the footer it handed the reader, or the
        # vintage the reader checks does not cover the numbers they were given.
        named = _datasets_in_answer(answer_text(reply), stamps)
        if seen - named:
            undeclared.setdefault(tool, []).extend(
                "%s (footer names %s)" % (t, ",".join(sorted(named)) or "nothing")
                for t in sorted(seen - named)
            )
    assert not undeclared, (
        "the audit and the running server disagree about which tables were read: %s"
        % undeclared
    )
    assert len(opened_anywhere) >= 15, (
        "only %d tables were observed at runtime; the ledger is not observing "
        "anything" % len(opened_anywhere)
    )


def test_answers_declare_the_tables_they_read(surface):
    """An answer's `dati_applicati` footer is the provenance a reader checks.

    The tables it names are the ones this call read, observed by the ledger, not
    every table the tool's code could read: a tool that branches between two
    tables must not attach the vintage of the branch it did not take. Where the
    ledger saw nothing -- a table reached through a value computed at import,
    which cannot be wrapped -- the declaration is what the footer falls back to,
    and `test_the_server_declares_the_tables_each_call_opened` is what keeps that
    fallback from hiding a read the walk missed.

    Two failures are possible in either direction: naming one table fewer than
    the call used hides a vintage the reader needed, naming one more claims a
    table this answer does not rest on.
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
        opened = _opened_tables(reply)
        # What the footer must name: the observation when there is one, the
        # declaration when the ledger could not see the read at all.
        expected = opened or set(datasets.get(tool, []))
        if declared != expected:
            disagreements[tool] = {
                "declared": sorted(declared),
                "opened": sorted(opened),
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
        "answers and the tables they applied disagree: %s" % disagreements
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
