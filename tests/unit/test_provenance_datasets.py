"""Demonstrate the table → tool mapping the provenance footer is built from.

A tool that reads a hand-maintained table appends `Dati applicati` to its
answer, naming the table and its vintage. That line is only worth something if
the mapping behind it is true, and the mapping is *derived* from the source by
`scripts/audit_tool_annotations.py`, so a derivation error would print a
reassuring line next to numbers that came from somewhere else.

So this test does not re-derive anything: it perturbs a table in a throwaway
copy of the server and watches which answers move, comparing that against what
the tools themselves say. Both directions are failures:

  * an answer that moves with a table whose footer does not name it is a silent
    reader — the case that hid `codici_tributo`, `modelli_atti` and
    `preavviso_ccnl`, whose loaders bind through a subscript, a comprehension
    and an annotated assignment rather than a bare `X = json.load(f)`;
  * an answer that names a table and does not move with it is a decorative
    footer.

The caller set comes from the tools' own footers, not from the audit, so the
two are independent: the audit decides what the policy should say, the server
says what it does, and this test makes them meet.

The tables are perturbed in a copy of `plugin/server` under `tmp_path`, never in
the working tree, and the run gets a sandboxed `HOME` with `LEGAL_CACHE=off`.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import tempfile

from . import mcp_harness as H

REPO = pathlib.Path(__file__).resolve().parents[2]
SERVER = REPO / "plugin/server"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".venv")

MARKER = "**Dati applicati**"

#: The error a tool answers with when the tables it rests on cannot support the
#: grade it declares (`src/lib/_data.py`). Such an answer is about the table's
#: *state*, so perturbing the table's values leaves it identical -- which is why
#: the mapping for those tables is demonstrated the other way round, by giving the
#: table a source and watching the refusal turn into a computation.
REFUSAL = "dati_non_affidabili"

#: Tables whose mapping is demonstrated. The whole table is perturbed, not one
#: field: readers use different halves of it — `imposte_successione` answers from
#: the aliquote, `imposte_compravendita` from the registro ones — so a
#: single-field mutation would look like a decorative footer in the other half.
PERTURBATIONS = (
    "imposte_successione",
    "modelli_atti",
    "preavviso_ccnl",
    "codici_tributo",
)

#: Keys whose values are provenance metadata, not data: perturbing them would
#: change the footer text and let a decorative footer look like a live one.
METADATA = "_"

#: Controls: tools that read other tables, plus a couple that read none. They
#: must not move with a table they do not name, which is what exposes a reader
#: no footer mentions.
CONTROLS = (
    "calcolo_irpef",
    "conta_giorni",
    "codice_fiscale",
    "interessi_legali",
    "danno_biologico_micro",
    "scorporo_iva",
    "verifica_iban",
)


def checkout(where: pathlib.Path) -> pathlib.Path:
    """A full copy of the server tree, as the launcher needs it."""
    shutil.copytree(SERVER, where / "plugin/server", ignore=IGNORE)
    return where


def content_text(reply: dict | None) -> str:
    """What a tool computed, with the provenance footer taken out.

    Comparing answers *without* their footer is what keeps the test honest: a
    footer that merely echoes a perturbed vintage string would otherwise count
    as an answer that moved, and a decorative footer would pass.
    """
    result = (reply or {}).get("result") or {}
    text = "\n".join(
        item.get("text", "")
        for item in result.get("content") or []
        if item.get("type") == "text"
    )
    if MARKER in text:
        text = text.split(MARKER)[0]
    text = re.sub(r'"dati_applicati":\s*\[.*?\]', "", text, flags=re.S)
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        text += "\n" + json.dumps(
            {k: v for k, v in structured.items() if k != "dati_applicati"},
            sort_keys=True,
            ensure_ascii=False,
        )
    return text


def _label(line: str) -> str:
    """The dataset a vintage line starts with: "tassi legali: copre fino al..."."""
    return line.split(":")[0].strip().replace(" ", "_").lower()


def footer_tables(reply: dict | None) -> set[str]:
    """Datasets an answer declares, read from its own footer.

    Three shapes reach a host: a dict answer keeps the lines in
    `structuredContent.dati_applicati`, the same dict rendered as text keeps them
    under a `"dati_applicati": [...]` key, and a string answer carries the
    markdown block. A test that read only one of them would call two thirds of
    the surface silent.
    """
    result = (reply or {}).get("result") or {}
    text = "\n".join(
        item.get("text", "")
        for item in result.get("content") or []
        if item.get("type") == "text"
    )
    labels: set[str] = set()
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        labels.update(_label(line) for line in structured.get("dati_applicati") or [])
    for footer in re.findall(r'"dati_applicati":\s*\[(.*?)\]', text, re.S):
        labels.update(_label(item) for item in re.findall(r'"([^"]+)"', footer))
    if MARKER in text:
        for line in text.split(MARKER, 1)[1].splitlines():
            if line.startswith("> - "):
                labels.add(_label(line[4:]))
    return {label for label in labels if label}


def shake(node):
    """Perturb every value of a table, keeping its keys and metadata intact."""
    if isinstance(node, dict):
        return {
            key: node[key] if key.startswith(METADATA) else shake(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [shake(value) for value in node]
    if isinstance(node, bool) or node is None:
        return node
    if isinstance(node, int):
        return node + 7
    if isinstance(node, float):
        return node + 7.0
    if isinstance(node, str):
        return node + " ZZZ"
    return node


def perturb(root: pathlib.Path, table: str) -> None:
    """Perturb a whole table inside a copy of the tree."""
    path = root / "plugin/server/src/data" / f"{table}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(
        json.dumps(shake(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def give_source(root: pathlib.Path, table: str) -> None:
    """Give a table a declared source, so tools may stop refusing it."""
    path = root / "plugin/server/src/data" / f"{table}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    block = payload.setdefault("_vintage", {})
    block["verifica"] = "manuale"
    block["fonte"] = "fonte di prova (perturbazione del test)"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def call(root: pathlib.Path, names: list[str], arguments: dict) -> dict:
    """Answers of `names`, read from the server in `root`."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    env = H.server_env(
        tmp / "home", tmp,
        {"LEGAL_CACHE": "off", "LEGAL_TODAY": "2026-09-15", "LEGAL_NOW": "2026-09-15T12:00:00"},
    )
    return H.call_tools(
        env, names, {name: arguments[name] for name in names}, timeout=300, repo=root
    )


def test_footer_mapping_is_demonstrated_and_not_just_derived(tmp_path):
    manifest = {tool["name"]: tool for tool in H.tools()}
    arguments = {name: H.arguments_for(tool) for name, tool in manifest.items()}
    names = [
        tool["name"]
        for tool in H.local_read_only(list(manifest.values()))
        if tool["name"] not in CONTROLS
    ]

    baseline = call(checkout(tmp_path / "clean"), list(CONTROLS) + names, arguments)
    answers = {name: content_text(reply) for name, reply in baseline.items()}

    declares = {
        table: sorted(name for name in names if table in footer_tables(baseline[name]))
        for table in PERTURBATIONS
    }
    assert all(declares.values()), "no tool names these tables: %s" % {
        table: len(declares[table]) for table in declares
    }
    noisy = sorted(
        name
        for table in PERTURBATIONS
        for name in CONTROLS
        if table in footer_tables(baseline[name])
    )
    assert not noisy, "a control names a table under perturbation: %s" % sorted(set(noisy))

    failures: list[str] = []
    for table in PERTURBATIONS:
        root = checkout(tmp_path / ("mutated-" + table))
        perturb(root, table)
        watchers = declares[table] + list(CONTROLS)
        current = call(root, watchers, arguments)

        moved = {
            name for name in watchers if content_text(current[name]) != answers[name]
        }
        refused = {
            name for name in declares[table] if REFUSAL in answers[name]
        }
        for name in sorted(moved - set(declares[table])):
            failures.append(
                "%s moved with %s but its answer does not name it" % (name, table)
            )
        for name in sorted((set(declares[table]) - moved) - refused):
            failures.append(
                "%s names %s but its answer did not move with it" % (name, table)
            )
        # The other direction, for the tools whose answer is a refusal: their
        # text cannot move when the values do, because it is about the table's
        # state. Two copies, both with the table given a source -- one with its
        # values shaken -- settle both halves: the refusal has to become a
        # computation (so it really depended on this table), and that computation
        # has to move with the values (so the table's content reaches the answer
        # for these tools too).
        if refused:
            intact = checkout(tmp_path / ("sourced-" + table))
            give_source(intact, table)
            shaken = checkout(tmp_path / ("sourced-mutated-" + table))
            give_source(shaken, table)
            perturb(shaken, table)
            answered = call(intact, sorted(refused), arguments)
            with_values = call(shaken, sorted(refused), arguments)
            for name in sorted(refused):
                if REFUSAL in content_text(answered.get(name)):
                    failures.append(
                        "%s kept refusing %s after the table declared a source: the "
                        "refusal does not depend on the state it names" % (name, table)
                    )
                elif content_text(with_values.get(name)) == content_text(answered.get(name)):
                    failures.append(
                        "%s answers the same thing with %s's values shaken: it "
                        "refuses on the table but never reads it" % (name, table)
                    )
    assert not failures, "\n".join(failures)
