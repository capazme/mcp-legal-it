"""Freeze what the local calculation tools answer, so a changed number shows up.

`test_read_only_contract.py` proves these tools write nothing;
`test_tool_annotations.py` proves they are advertised as read-only. Neither says
anything about whether they still compute the same thing. A table gets refreshed
(`indici_foi.json`, `tassi_legali.json`, `parametri_forensi.json`,
`tabella_danno_bio.json`), a bracket is mistyped, a band boundary moves by one
euro -- and every test still passes while the advice changes.

This test pins the numbers: each local read-only tool is called with the
arguments from the shared harness, and the answer is compared with
`tests/fixtures/golden/calcoli_locali.json`. A difference fails with the tool
name and the lines that moved.

Two things make that possible:

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
import shutil
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

GOLDEN = REPO / "tests/fixtures/golden/calcoli_locali.json"
PINNED_TODAY = "2026-09-15"
PINNED_NOW = "2026-09-15T12:00:00"
# Answers are stored truncated: a few tools return whole documents, and a
# reference file nobody can read in review is a reference file nobody checks.
TRUNCATED_AT = 4000


def _normalize(text: str) -> str:
    """Trailing whitespace is formatting; the rest is the value."""
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


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


def _reference() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _current(arguments: dict, replies: dict) -> dict:
    return {
        name: _normalize(answer_text(replies.get(name, {})))[:TRUNCATED_AT]
        for name in arguments
    }


def _describe(name: str, expected: str, actual: str) -> str:
    diff = [
        line.rstrip()
        for line in difflib.unified_diff(
            expected.splitlines(), actual.splitlines(), "recorded", "now", lineterm="", n=0
        )
        if not line.startswith(("---", "+++", "@@"))
    ]
    return "%s\n  %s" % (name, "\n  ".join(diff[:12]))


def _write_reference(arguments: dict, current: dict) -> None:
    payload = {
        "note": (
            "Expected answers of the local read-only tools, pinned to "
            "LEGAL_TODAY/LEGAL_NOW and truncated at %d characters. Regenerate "
            "with: GOLDEN_UPDATE=1 pytest "
            "tests/unit/test_golden_calcoli.py" % TRUNCATED_AT
        ),
        "pinned_today": PINNED_TODAY,
        "pinned_now": PINNED_NOW,
        "arguments": arguments,
        "tools": current,
    }
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_local_calculation_tools_answer_the_recorded_values(surface):
    local, arguments, replies = surface
    current = _current(arguments, replies)

    answered = sorted(name for name, text in current.items() if text)
    assert len(answered) >= 0.9 * len(local), (
        "only %d/%d tools answered; the arguments or the server are broken: %s"
        % (len(answered), len(local), sorted(set(arguments) - set(answered))[:8])
    )

    if os.environ.get("GOLDEN_UPDATE") == "1":
        _write_reference(arguments, current)
        pytest.skip("reference regenerated: %s" % GOLDEN.relative_to(REPO))

    reference = _reference()
    recorded = reference["tools"]

    missing = sorted(set(recorded) - set(current))
    assert not missing, (
        "the reference records tools that no longer exist: %s -- regenerate with "
        "GOLDEN_UPDATE=1" % missing[:8]
    )
    added = sorted(set(current) - set(recorded))
    assert not added, (
        "tools with no recorded value: %s -- regenerate with GOLDEN_UPDATE=1" % added[:8]
    )

    # The inputs are part of the fixture too: an answer recorded for different
    # arguments is not comparable with today's run.
    arguments_changed = sorted(
        name for name, args in arguments.items() if args != reference["arguments"].get(name)
    )
    assert not arguments_changed, (
        "the harness now generates different arguments for: %s -- if that is "
        "intentional, regenerate the reference with GOLDEN_UPDATE=1"
        % arguments_changed[:8]
    )

    changed = [
        _describe(name, recorded[name], current[name])
        for name in sorted(current)
        if recorded[name] != current[name]
    ]
    assert not changed, (
        "%d of %d recorded answers changed:\n\n%s\n\nIf the change is intended "
        "(a new rate, a corrected parameter, a fixed bracket), regenerate the "
        "reference with: GOLDEN_UPDATE=1 pytest tests/unit/test_golden_calcoli.py"
        % (len(changed), len(current), "\n\n".join(changed[:6]))
    )


def test_the_reference_stores_results_not_failures():
    """A frozen error is not a value: it means the arguments need fixing.

    The harness generates arguments from the schema, and the schema does not
    declare every closed vocabulary (company types, CCNL levels, catastrophic
    categories are validated inside the tools). When one of those drifts, the
    tool answers with an error -- and an error is not something to freeze as
    the expected answer.
    """
    recorded = _reference()["tools"]
    markers = ('"errore"', "Error calling tool", "validation error", '"valido": false')
    broken = {
        name: next(m for m in markers if m in text)
        for name, text in recorded.items()
        if any(m in text for m in markers)
    }
    assert not broken, "recorded answers are failures, not results: %s" % broken


def test_the_reference_is_pinned_complete_and_readable():
    """The fixture itself: pinned, aligned with the surface, reviewable."""
    reference = _reference()
    assert reference["pinned_today"] == PINNED_TODAY
    assert reference["pinned_now"] == PINNED_NOW

    recorded = reference["tools"]
    local_names = {tool["name"] for tool in local_read_only(tools())}
    assert set(recorded) == local_names, (
        "the reference and the local read-only surface disagree: %s"
        % sorted(set(recorded) ^ local_names)[:8]
    )
    assert len(recorded) > 100, "the reference covers only %d tools" % len(recorded)
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
