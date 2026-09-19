"""What the server does with a vintage: flag it, structurally, per call.

`tests/unit/test_data_vintage.py` covers how a table declares its own currency.
This file covers the other half -- what a *call* is told about it:

* which tables the warnings are about is the observed set (`src/lib/_ledger.py`),
  not the declaration, so a call that branches between two tables is flagged for
  the one it used;
* an expired covered period and an unverified provenance are different states,
  reported apart from each other, next to the answer instead of only at the end
  of it;
* a table that is neither raises nothing -- the field has to mean something when
  it is there, or nobody can act on it.

The states are pinned to real shipped tables on purpose. A hand-made fixture
imitating them would keep passing after the tables themselves were fixed, which
is the one thing this file is meant to prevent.
"""

from __future__ import annotations

import pathlib
import re
import sys
import tempfile

import pytest

from src.lib import _data, _tables_open
from src.lib._data import warnings

from .mcp_harness import (
    REPO,
    answer_text,
    arguments_for,
    call_tools,
    local_read_only,
    server_env,
    tools,
)

#: A table whose source is known and whose covered period is still running.
IN_FORCE = "tassi_legali"
#: A table whose source and period nobody has established.
#: (`contributo_unificato` used to be the pin; it was reconciled with the DPR
#: 115/2002 on 2026-09-18, and the gap this file watches moved to the next
#: table still unverified.)
UNVERIFIED_TABLE = "imposte_successione"
#: A table with a source and no recurring update: not stale, and not flagged.
STABLE = "festivita"

PRESENT = {"LEGAL_TODAY": "2026-09-15", "LEGAL_NOW": "2026-09-15T12:00:00", "TZ": "UTC"}
FUTURE = {"LEGAL_TODAY": "2027-06-01", "LEGAL_NOW": "2027-06-01T12:00:00", "TZ": "UTC"}
#: Tools that answer from one of the three tables above, plus `codice_fiscale`,
#: which reads an unverified table (`comuni`) that is easy to mistake for a
#: stable dictionary of catastal codes.
WATCHED = (
    "interessi_legali",
    "imposte_successione",
    "conta_giorni",
    "codice_fiscale",
    "danno_biologico_micro",
    "parcella_avvocato_civile",
)
DATA_WARNINGS_KEY = "mcp-legal-it/data_warnings"
OPENER_TABLES_KEY = "mcp-legal-it/opened_tables"


def _audit():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from audit_tool_annotations import Audit  # type: ignore[import-not-found]

        return Audit(pathlib.Path(REPO / "plugin/server/src"))
    finally:
        sys.path.pop(0)


def _payload(reply: dict) -> dict:
    structured = ((reply or {}).get("result") or {}).get("structuredContent")
    return structured if isinstance(structured, dict) else {}


def _meta(reply: dict) -> dict:
    return (((reply or {}).get("result") or {}).get("_meta")) or {}


def _states(entries) -> list[tuple[str, str]]:
    return [(entry["tabella"], entry["stato"]) for entry in entries or ()]


def _footer_tables(reply: dict) -> set[str]:
    """Table names in an answer's provenance footer, from either rendering."""
    known = _audit().available_datasets
    text = answer_text(reply)
    names: set[str] = set()

    def label(line: str) -> str:
        return line.split(":")[0].strip().replace(" ", "_")

    for block in re.findall(r'"dati_applicati":\s*\[(.*?)\]', text, re.S):
        names.update(label(item) for item in re.findall(r'"([^"]+)"', block))
    marker = "**Dati applicati**"
    if marker in text:
        names.update(
            label(line[4:])
            for line in text.split(marker, 1)[1].splitlines()
            if line.startswith("> - ")
        )
    return {name for name in names if name in known}


@pytest.fixture(scope="module")
def sessions():
    """The watched tools, called once at the pinned present and once in the future.

    Two runs are the point: `tassi_legali` covers 2026, so at the first date it
    must be silent and at the second it must be flagged. If the flag were a
    property of the table rather than of the clock, one of the two would be wrong.
    """
    manifest = {tool["name"]: tool for tool in tools()}
    names = [name for name in WATCHED if name in manifest]
    assert len(names) == len(WATCHED), "the watched tools moved: %s" % (
        sorted(set(WATCHED) - set(manifest)),
    )
    arguments = {name: arguments_for(manifest[name]) for name in names}
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="vintage-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="vintage-tmp-"))
    out = {}
    for label, clock in (("present", PRESENT), ("future", FUTURE)):
        env = server_env(
            sandbox / label, scratch, extra={**clock, "LEGAL_CACHE": "off"}
        )
        out[label] = call_tools(env, names, arguments, timeout=300)
    return names, out


def test_only_the_two_states_that_carry_weight_are_flagged(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-15")
    assert warnings([]) == [], "nothing applied, nothing to flag"
    assert warnings([STABLE]) == [], "a source with no recurring update is not stale"
    assert warnings(["tabella_danno_bio"]) == [], "a source and no period is not an expiry"
    assert warnings([IN_FORCE]) == [], "the period is still running at this date"

    unverified = warnings([UNVERIFIED_TABLE])
    assert _states(unverified) == [(UNVERIFIED_TABLE, "non_verificata")]
    assert unverified[0]["verificata"] is False
    assert unverified[0]["copre_fino_a"] is None, (
        "an unverified table declares no period: reporting one would be an invention"
    )


def test_an_elapsed_period_is_a_different_state_from_an_unverified_one(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2027-01-01")
    expired = warnings([IN_FORCE])
    assert _states(expired) == [(IN_FORCE, "scaduta")]
    assert expired[0]["verificata"] is True, "the source is known; the period is what ended"
    assert expired[0]["copre_fino_a"] == "2026-12-31"

    both = warnings([IN_FORCE, UNVERIFIED_TABLE])
    assert _states(both) == [
        (IN_FORCE, "scaduta"),
        (UNVERIFIED_TABLE, "non_verificata"),
    ], "the two failures have to stay distinguishable in the same answer"
    assert [entry["messaggio"] for entry in both] == [
        _data.vintage(IN_FORCE).to_line(),
        _data.vintage(UNVERIFIED_TABLE).to_line(),
    ], "the structured message and the footer line must be the same sentence"


def test_effective_prefers_what_the_call_touched_and_falls_back_when_blind():
    declared = ("indici_foi", "tassi_legali")
    assert _data.effective(declared) == declared, "outside a call there is nothing to narrow"

    with _tables_open.recording():
        _tables_open.note("indici_foi")
        assert _data.effective(declared) == ("indici_foi",), (
            "the call used one table; naming both claims a vintage it never applied"
        )

    with _tables_open.recording():
        _tables_open.note("festivita")
        assert _data.effective(declared) == declared, (
            "nothing observed belongs to the declaration: the declaration is still "
            "the best statement of what the answer rests on, not an empty footer"
        )


def test_reading_a_table_by_name_is_observed_and_rendering_it_is_not():
    """The accessor is the choke point, and the footer must not feed itself.

    `_data.load` is how a tool reads a table inside a call, so it records the
    read. Rendering a vintage goes to the cached `_read` underneath instead:
    otherwise every footer would note the tables it describes, the observation
    would always equal the declaration, and no answer could ever narrow.
    """
    assert _data.load("festivita") is _data.load("festivita"), "the read is cached"
    assert _tables_open.opened() == [], "outside a call even the accessor stays quiet"

    with _tables_open.recording():
        _data.load(STABLE)
        assert _tables_open.opened() == [STABLE]
        _data.footer(IN_FORCE, UNVERIFIED_TABLE)
        _data.warnings([IN_FORCE, UNVERIFIED_TABLE])
        assert _tables_open.opened() == [STABLE], (
            "describing a table's vintage counted as applying it"
        )


def test_an_answer_from_an_expired_table_says_so_structurally(sessions):
    names, runs = sessions
    assert "interessi_legali" in names
    expired = runs["future"]["interessi_legali"]
    payload, meta = _payload(expired), _meta(expired)

    assert _states(payload.get("avvisi_dati")) == [(IN_FORCE, "scaduta")]
    assert _states(meta.get(DATA_WARNINGS_KEY)) == [(IN_FORCE, "scaduta")], (
        "the same fact has to reach a host that reads only the meta"
    )
    assert "PERIODO SCADUTO" in answer_text(expired), (
        "the reader of the prose is told too, and told in the footer they already read"
    )

    # The same tool, the same table, the same arguments -- a clock that has not
    # passed the covered period yet. Silence here is what makes the flag mean
    # something: it is the date that is wrong, not the presence of the table.
    at_present = runs["present"]["interessi_legali"]
    assert "avvisi_dati" not in _payload(at_present)
    assert DATA_WARNINGS_KEY not in _meta(at_present)
    assert "PERIODO SCADUTO" not in answer_text(at_present)


def test_an_unverified_provenance_is_flagged_whenever_it_is_asked(sessions):
    """Not clock-dependent: this table is a gap in the data, not a stale number."""
    _, runs = sessions
    for label in ("present", "future"):
        reply = runs[label]["imposte_successione"]
        entry = _payload(reply).get("avvisi_dati") or []
        assert _states(entry) == [(UNVERIFIED_TABLE, "non_verificata")], label
        assert entry[0]["verificata"] is False
        assert "SCADUTO" not in answer_text(reply), (
            "an unverified source is not an expired one: the two say different things "
            "to whoever has to decide whether to use the number"
        )


def test_a_table_with_a_stable_source_raises_nothing(sessions):
    """Silence is the report for a table that is neither expired nor undeclared.

    Three shapes of "nothing to say": a statute with no recurring update
    (`festivita`), a table with a source and no declared period (`tabella_danno_bio`),
    and one reconciled to a date with no end in sight (`parametri_forensi`).
    """
    _, runs = sessions
    for name in ("conta_giorni", "danno_biologico_micro", "parcella_avvocato_civile"):
        reply = runs["present"][name]
        tables = _footer_tables(reply) | _footer_tables(runs["future"][name])
        assert tables, "%s stopped declaring its tables" % name
        assert tables.isdisjoint({IN_FORCE}), "the fixture picked the wrong tools"
        assert "avvisi_dati" not in _payload(reply), name
        assert DATA_WARNINGS_KEY not in _meta(reply), name

    # The counterpart, in the same run: a table whose source nobody has
    # established is flagged even though nothing about it looks stale.
    flagged = runs["present"]["codice_fiscale"]
    assert _states(_payload(flagged).get("avvisi_dati")) == [("comuni", "non_verificata")]


def test_the_structured_warning_is_the_footer_line_of_the_table_it_names(sessions):
    """Two channels for one fact: if they can disagree, one of them is noise."""
    _, runs = sessions
    checked = 0
    for label, replies in runs.items():
        for name, reply in replies.items():
            entries = _payload(reply).get("avvisi_dati") or []
            if not entries:
                continue
            checked += 1
            text = answer_text(reply)
            for entry in entries:
                assert entry["tabella"] in _footer_tables(reply), (
                    "%s/%s: avvisi_dati names %s, the footer does not"
                    % (label, name, entry["tabella"])
                )
                assert entry["messaggio"] in text, (
                    "%s/%s: the structured message is not the line the reader sees"
                    % (label, name)
                )
            assert _states(entries) == _states(_meta(reply).get(DATA_WARNINGS_KEY)), (
                "%s/%s: the payload and the meta disagree" % (label, name)
            )
    assert checked >= 4, "only %d warned answers were inspected" % checked


def test_the_warnings_follow_the_call_and_not_the_declaration():
    """The narrowing case, where both halves of the change are visible at once.

    `note_iscrizione_ruolo` declares two tables and computes the contributo
    unificato only when a value in controversy is given. Called with the required
    parameters alone it reads one table, so its footer must name one and its
    warnings must be about that one: claiming the other's vintage would be a
    statement about a table the call never opened.
    """
    manifest = {tool["name"]: tool for tool in local_read_only(tools())}
    audit = _audit()
    declared = {name: audit.datasets(fq) for fq, name in audit.tools.items()}
    multi = sorted(name for name in declared if len(declared[name]) > 1 and name in manifest)
    assert len(multi) > 1, "no tool reads more than one table: nothing to narrow"

    arguments = {}
    for name in multi:
        schema = manifest[name].get("inputSchema") or {}
        required = set(schema.get("required") or ())
        arguments[name] = {
            key: value
            for key, value in arguments_for(manifest[name]).items()
            if key in required
        }

    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="narrow-sandbox-"))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="narrow-tmp-"))
    env = server_env(sandbox, scratch, extra={**PRESENT, "LEGAL_CACHE": "off"})
    replies = call_tools(env, multi, arguments, timeout=300)

    narrowed = {}
    for name in multi:
        reply = replies.get(name) or {}
        opened = set(_meta(reply).get(OPENER_TABLES_KEY) or ())
        footer = _footer_tables(reply)
        assert footer, "%s answered without any provenance" % name
        assert opened, "%s read a table the ledger did not observe" % name
        assert footer == opened, (
            "%s names %s in its footer but opened %s"
            % (name, sorted(footer), sorted(opened))
        )
        assert opened <= set(declared[name]), (
            "%s opened %s, which its declaration does not cover"
            % (name, sorted(opened - set(declared[name])))
        )
        warned = {entry["tabella"] for entry in _payload(reply).get("avvisi_dati") or ()}
        assert warned <= opened, "%s warns about a table the call never opened" % name
        if opened != set(declared[name]):
            narrowed[name] = (sorted(declared[name]), sorted(opened))

    assert narrowed, (
        "no call narrowed: either the footer is still written from the declaration, "
        "or the required-only arguments no longer close any branch"
    )
    assert "note_iscrizione_ruolo" in narrowed, (
        "the tool this check is built around no longer branches: %s" % sorted(narrowed)
    )
    assert narrowed["note_iscrizione_ruolo"] == (["codici_ruolo", "contributo_unificato"], ["codici_ruolo"])
