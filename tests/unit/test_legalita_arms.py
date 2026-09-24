"""Arm harness: argv construction and CLI output parsing.

Actually invoking `claude -p` is a live operation and is not unit-tested.
What IS tested is the part that decides what the three arms are allowed to
do, because that is the experiment's only independent variable.
"""

import json
import subprocess
from pathlib import Path

import pytest

from benchmarks.legalita.run.arms import (
    ARM_TOOLS,
    SYSTEM_PROMPT,
    _extract_tool_calls,
    _hook_feedback,
    arm_env,
    build_argv,
    isolation_env,
    materialise_variant_mcp_config,
    parse_cli_json,
    run_arm,
)
from benchmarks.legalita.schema import ARMS, VARIANT_ARMS, Task


def _argv(arm: str) -> list[str]:
    return build_argv(
        arm, model="claude-opus-5", max_turns=12, mcp_config="cfg.json",
        plugin_dir="/tmp/variant/plugin" if arm in VARIANT_ARMS else None,
    )


def _flag_value(argv: list[str], flag: str) -> list[str]:
    start = argv.index(flag) + 1
    values = []
    for token in argv[start:]:
        if token.startswith("--"):
            break
        values.append(token)
    return values


def test_every_arm_uses_the_same_system_prompt():
    for arm in ARMS:
        assert _flag_value(_argv(arm), "--system-prompt") == [SYSTEM_PROMPT]


def test_every_arm_uses_the_same_model_and_turn_cap():
    for arm in ARMS:
        argv = _argv(arm)
        assert _flag_value(argv, "--model") == ["claude-opus-5"]
        assert _flag_value(argv, "--max-turns") == ["12"]


def test_every_arm_neutralises_inherited_settings():
    for arm in ARMS:
        argv = _argv(arm)
        assert _flag_value(argv, "--settings") == ["{}"]
        assert _flag_value(argv, "--setting-sources") == ["project"]
        assert "--strict-mcp-config" in argv
        assert _flag_value(argv, "--output-format") == ["json"]
        if arm in VARIANT_ARMS:
            # Dropping this flag is what keeps the pinned plugin's own skills
            # and commands reachable: on CLI 2.1.278 it also strips `Skill`,
            # which is half of what a plugin arm is meant to measure.
            assert "--disable-slash-commands" not in argv
        else:
            assert "--disable-slash-commands" in argv


def test_bare_arm_gets_no_tools_and_no_mcp_config():
    # --allowedTools/--disallowedTools are permission-prompt allow/deny
    # lists layered on the full catalog and do not restrict it under
    # --permission-mode bypassPermissions (live-verified: an allowedTools
    # list still let the model call Skill and Bash). --tools "" is the
    # actual hard restriction to zero tools.
    argv = _argv("bare")
    assert "--mcp-config" not in argv
    assert "--allowedTools" not in argv
    assert "--disallowedTools" not in argv
    assert _flag_value(argv, "--tools") == [""]


def test_web_arm_gets_only_search_tools():
    assert ARM_TOOLS["web"] == ["WebSearch", "WebFetch"]
    assert _flag_value(_argv("web"), "--tools") == ["WebSearch,WebFetch"]
    assert "--mcp-config" not in _argv("web")


def test_mcp_arm_gets_only_legal_it_tools():
    # ARM_TOOLS documents the granted capability (mcp__legal-it__* only);
    # --tools cannot name MCP tools directly (it only accepts built-ins), so
    # the mcp arm allows the built-in ToolSearch meta-tool, which is how
    # this environment (ENABLE_TOOL_SEARCH=true) discovers MCP-server
    # tools. --strict-mcp-config + --disable-slash-commands ensure the
    # legal-it server is the only thing ToolSearch can find.
    argv = _argv("mcp")
    assert ARM_TOOLS["mcp"] == ["mcp__legal-it__*"]
    assert _flag_value(argv, "--tools") == ["ToolSearch"]
    assert _flag_value(argv, "--mcp-config") == ["cfg.json"]


def test_mcp_arm_runs_the_reduced_profile():
    assert arm_env("mcp")["LEGAL_PROFILE"] == "normativa"


def test_non_mcp_arms_set_no_profile():
    assert "LEGAL_PROFILE" not in arm_env("bare")
    assert "LEGAL_PROFILE" not in arm_env("web")
    # The plugin arms share the mcp arm's server-side profile: it is a
    # property of the server under test, identical across every MCP-bearing
    # arm, so it cannot confound the variant comparison.
    for arm in VARIANT_ARMS:
        assert arm_env(arm)["LEGAL_PROFILE"] == "normativa"


def test_unknown_arm_is_rejected():
    with pytest.raises(ValueError, match="arm"):
        build_argv("tools", model="m", max_turns=1, mcp_config=None)


def test_variant_arm_requires_a_plugin_dir():
    # Without a provisioned worktree a variant arm would silently run bare —
    # the one failure mode that must never look like data.
    for arm in VARIANT_ARMS:
        with pytest.raises(ValueError, match="plugin_dir"):
            build_argv(arm, model="m", max_turns=1, mcp_config=None, plugin_dir=None)
        argv = build_argv(
            arm, model="m", max_turns=1, mcp_config="variant-mcp.json",
            plugin_dir="/tmp/variant/plugin",
        )
        assert _flag_value(argv, "--plugin-dir") == ["/tmp/variant/plugin"]
        # The pinned server is mounted explicitly as well: --strict-mcp-config
        # is on for every arm and would otherwise suppress the plugin's own
        # .mcp.json server, leaving skills with no tools behind them.
        assert _flag_value(argv, "--mcp-config") == ["variant-mcp.json"]


def test_variant_arm_refuses_to_mount_no_server_at_all():
    # A plugin arm that loads skills but no MCP server is not the product
    # under test, and must not be reachable by forgetting an argument.
    for arm in VARIANT_ARMS:
        with pytest.raises(ValueError, match="mcp_config"):
            build_argv(
                arm, model="m", max_turns=1, mcp_config=None,
                plugin_dir="/tmp/variant/plugin",
            )


def test_variant_arm_gets_skill_alongside_the_mcp_surface():
    for arm in VARIANT_ARMS:
        assert ARM_TOOLS[arm] == ["mcp__legal-it__*", "Skill"]
        # One comma-joined argv token, same rendering the web arm uses.
        assert _flag_value(_argv(arm), "--tools") == ["Skill,ToolSearch"]


def test_parse_cli_json_extracts_answer_and_tool_calls():
    # A healthy mcp-arm shape: the legal-it server connected and its tools
    # are reachable via ToolSearch (this environment's discovery path).
    messages = [
        {
            "type": "system",
            "subtype": "init",
            "tools": ["ToolSearch"],
            "mcp_servers": [{"name": "legal-it", "status": "pending"}],
        },
        {"type": "assistant", "message": {"content": []}},
        {
            "type": "result",
            "result": "La responsabilita e del committente.",
            "num_turns": 4,
            "usage": {"input_tokens": 100, "output_tokens": 20},
            "modelUsage": {"claude-opus-5": {}},
            "is_error": False,
        },
    ]
    record = parse_cli_json(messages, task_id="T1", arm="mcp", duration_ms=900)
    assert record.answer.startswith("La responsabilita")
    assert record.num_turns == 4
    assert record.duration_ms == 900
    assert record.error is None


def test_parse_cli_json_marks_errors():
    messages = [
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": []},
        {"type": "result", "result": "", "is_error": True, "num_turns": 1, "usage": {}},
    ]
    record = parse_cli_json(messages, task_id="T1", arm="bare", duration_ms=10)
    assert record.error is not None
    assert record.answer == ""


def test_parse_cli_json_survives_a_missing_usage_block():
    messages = [{"type": "result", "result": "x"}]
    record = parse_cli_json(messages, task_id="T1", arm="bare", duration_ms=1)
    assert record.usage == {}
    assert record.num_turns == 0


def test_parse_cli_json_raises_when_result_message_is_absent():
    messages = [{"type": "system", "subtype": "init", "tools": [], "mcp_servers": []}]
    with pytest.raises(ValueError, match="result"):
        parse_cli_json(messages, task_id="T1", arm="bare", duration_ms=1)


def test_parse_cli_json_flags_stop_hook_contamination_but_keeps_the_answer():
    messages = [
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": []},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "art. 2043 c.c."}]}},
        {
            "type": "user",
            "isSynthetic": True,
            "message": {
                "content": [
                    {
                        "type": "text",
                        "text": "Stop hook feedback:\n[...]: ATTENZIONE — gate citazioni: ...",
                    }
                ]
            },
        },
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "final answer"}]}},
        {
            "type": "result",
            "result": "final answer",
            "num_turns": 2,
            "usage": {},
            "is_error": False,
        },
    ]
    record = parse_cli_json(messages, task_id="T1", arm="bare", duration_ms=5)
    assert record.answer == "final answer"
    assert record.error is not None
    assert "stop hook" in record.error.lower()


def test_parse_cli_json_records_plugin_hook_feedback_as_an_event_not_an_error(plugin_root):
    # For a plugin arm the citation gate ships INSIDE the plugin under
    # test: its firing is product behaviour to record, never a reason to
    # flag the run — dropping these runs would bias the comparison against
    # the gate-bearing deliverable.
    messages = [
        {
            "type": "system",
            "subtype": "init",
            "tools": ["Skill", "ToolSearch"],
            "mcp_servers": [{"name": "legal-it", "status": "connected"}],
        },
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "art. 2043 c.c."}]}},
        {
            "type": "user",
            "isSynthetic": True,
            "message": {
                "content": [
                    {"type": "text", "text": "Stop hook feedback:\nATTENZIONE — gate citazioni: ..."}
                ]
            },
        },
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "final answer"}]}},
        {
            "type": "result",
            "result": "final answer",
            "num_turns": 2,
            "usage": {},
            "is_error": False,
        },
    ]
    record = parse_cli_json(
        messages, task_id="T1", arm="plugin-v3", duration_ms=5,
        plugin_root=plugin_root,
    )
    assert record.error is None
    assert record.answer == "final answer"
    assert record.usage["hook_interventions"] == {
        "source": "plugin-under-test",
        "excerpt": "Stop hook feedback:\nATTENZIONE — gate citazioni: ...",
    }


def test_isolation_env_is_scoped_to_the_run_workdir(tmp_path):
    env = isolation_env(tmp_path)
    assert env["LEGAL_IT_GATE_SKIP_PATHS"] == str(tmp_path.resolve())


# --- Tool-shape verification: the guard against a silent MCP degrade -------
#
# An arm that requested tools but didn't get them (server never started,
# tool search unavailable, a flag regression) must never look identical to a
# clean run. `is_error: false` + `tool_calls: []` alone cannot tell "the
# model didn't need a tool" apart from "the model had no tool to reach" —
# these tests are that distinction.


# --- Variant arms (plugin-v2 / plugin-v3): the full product under test ----


def _variant_messages(tools: list[str], servers: list[dict]) -> list[dict]:
    return [
        {"type": "system", "subtype": "init", "tools": tools, "mcp_servers": servers},
        {"type": "result", "result": "risposta", "num_turns": 1, "usage": {}, "is_error": False},
    ]


@pytest.fixture()
def plugin_root(tmp_path):
    root = tmp_path / "variant" / "plugin"
    root.mkdir(parents=True)
    (root / ".mcp.json").write_text("{}", encoding="utf-8")
    return root


def test_parse_cli_json_accepts_healthy_plugin_shape(plugin_root):
    record = parse_cli_json(
        _variant_messages(["Skill", "ToolSearch"], [{"name": "legal-it", "status": "pending"}]),
        task_id="T1", arm="plugin-v2", duration_ms=5, plugin_root=plugin_root,
    )
    assert record.error is None


def test_parse_cli_json_accepts_direct_mcp_tools_for_plugin_arm(plugin_root):
    # Same ENABLE_TOOL_SEARCH fallback as the plain mcp arm: on a machine
    # without tool search the MCP tools are listed directly. Also healthy.
    record = parse_cli_json(
        _variant_messages(
            ["Skill", "mcp__legal-it__cite_law"],
            [{"name": "legal-it", "status": "connected"}],
        ),
        task_id="T1", arm="plugin-v3", duration_ms=5, plugin_root=plugin_root,
    )
    assert record.error is None


def test_parse_cli_json_flags_plugin_arm_without_skill(plugin_root):
    # The MCP half alone is not the plugin arm's declared surface: without
    # the Skill built-in the content layer is not loaded and the run must
    # not look healthy — this is exactly the silent-degrade shape the
    # guard exists to catch.
    record = parse_cli_json(
        _variant_messages(["ToolSearch"], [{"name": "legal-it", "status": "connected"}]),
        task_id="T1", arm="plugin-v2", duration_ms=5, plugin_root=plugin_root,
    )
    assert record.error is not None
    assert "skill" in record.error.lower()


def test_parse_cli_json_flags_plugin_arm_with_missing_plugin_root():
    # No plugin root supplied at all — the variant worktree was never
    # provisioned — must not look healthy.
    record = parse_cli_json(
        _variant_messages(["Skill", "ToolSearch"], [{"name": "legal-it", "status": "connected"}]),
        task_id="T1", arm="plugin-v2", duration_ms=5, plugin_root=None,
    )
    assert record.error is not None
    assert "plugin root" in record.error.lower()


def test_parse_cli_json_flags_plugin_arm_with_foreign_plugin_dir(tmp_path):
    wrong = tmp_path / "not-a-plugin"
    wrong.mkdir()
    record = parse_cli_json(
        _variant_messages(["Skill", "ToolSearch"], [{"name": "legal-it", "status": "connected"}]),
        task_id="T1", arm="plugin-v3", duration_ms=5, plugin_root=wrong,
    )
    assert record.error is not None
    assert "not a plugin directory" in record.error.lower()


def test_parse_cli_json_flags_plugin_arm_when_legal_it_server_missing(plugin_root):
    record = parse_cli_json(
        _variant_messages(["Skill", "ToolSearch"], []),
        task_id="T1", arm="plugin-v2", duration_ms=5, plugin_root=plugin_root,
    )
    assert record.error is not None
    assert "legal-it" in record.error.lower()


def test_parse_cli_json_flags_plugin_arm_on_explicit_server_failure(plugin_root):
    record = parse_cli_json(
        _variant_messages(["Skill", "ToolSearch"], [{"name": "legal-it", "status": "failed"}]),
        task_id="T1", arm="plugin-v2", duration_ms=5, plugin_root=plugin_root,
    )
    assert record.error is not None
    assert "failed" in record.error.lower()


def test_hook_feedback_detector_feeds_both_classifications():
    # One detector, two policies: an error for the bare/web/mcp arms, a
    # recorded event for the plugin arms. The excerpt must survive into the
    # usage block so the audit can see what the gate actually said.
    messages = [
        {
            "type": "user",
            "isSynthetic": True,
            "message": {"content": [{"type": "text", "text": "Stop hook feedback: gate citazioni"}]},
        },
    ]
    assert _hook_feedback(messages) == "Stop hook feedback: gate citazioni"


def test_parse_cli_json_flags_missing_mcp_server_for_mcp_arm():
    # The exact scenario that must never pass silently: the mcp arm's MCP
    # server never shows up in the init message, yet the run still "looks"
    # fine (is_error: false, a plausible-looking answer from memory).
    messages = [
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": []},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "answer from memory"}]}},
        {
            "type": "result",
            "result": "answer from memory",
            "num_turns": 1,
            "usage": {},
            "is_error": False,
        },
    ]
    record = parse_cli_json(messages, task_id="T1", arm="mcp", duration_ms=50)
    assert record.error is not None
    assert "mcp arm" in record.error.lower()
    assert "legal-it" in record.error.lower()
    # The answer survives — a mismatched run is flagged data, not discarded.
    assert record.answer == "answer from memory"
    # And the actual reported shape is preserved for later audit.
    assert record.usage["tools_reported"] == []
    assert record.usage["mcp_servers_reported"] == []


def test_parse_cli_json_accepts_healthy_mcp_shape_via_direct_tools():
    # On a machine without ENABLE_TOOL_SEARCH, mcp__legal-it__* tools would
    # be listed directly instead of behind ToolSearch — also healthy.
    messages = [
        {
            "type": "system",
            "subtype": "init",
            "tools": ["mcp__legal-it__cite_law", "mcp__legal-it__cerca_brocardi"],
            "mcp_servers": [{"name": "legal-it", "status": "connected"}],
        },
        {
            "type": "result",
            "result": "art. 2043 c.c.",
            "num_turns": 2,
            "usage": {},
            "is_error": False,
        },
    ]
    record = parse_cli_json(messages, task_id="T1", arm="mcp", duration_ms=50)
    assert record.error is None


def test_parse_cli_json_flags_explicit_mcp_server_failure_even_with_tool_search():
    # The scenario the guard exists to catch: the legal-it server explicitly
    # failed to start, but ToolSearch (a built-in offered regardless of any
    # particular server's connection state) is still listed. ToolSearch's
    # presence must NOT be allowed to override an explicit failure status.
    messages = [
        {
            "type": "system",
            "subtype": "init",
            "tools": ["ToolSearch"],
            "mcp_servers": [{"name": "legal-it", "status": "failed"}],
        },
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "answer from memory"}]}},
        {
            "type": "result",
            "result": "answer from memory",
            "num_turns": 1,
            "usage": {},
            "is_error": False,
        },
    ]
    record = parse_cli_json(messages, task_id="T1", arm="mcp", duration_ms=50)
    assert record.error is not None
    assert "mcp arm" in record.error.lower()
    assert "failed" in record.error.lower()
    # Data preserved, not discarded, same as every other mismatch.
    assert record.answer == "answer from memory"
    assert record.usage["mcp_servers_reported"] == [{"name": "legal-it", "status": "failed"}]


def test_parse_cli_json_accepts_mcp_shape_with_no_status_key():
    # A missing status key (never observed live, but not a positive claim
    # either) must not be treated as a failure — only an explicit failure
    # marker should flag.
    messages = [
        {
            "type": "system",
            "subtype": "init",
            "tools": ["ToolSearch"],
            "mcp_servers": [{"name": "legal-it"}],
        },
        {"type": "result", "result": "x", "num_turns": 1, "usage": {}, "is_error": False},
    ]
    record = parse_cli_json(messages, task_id="T1", arm="mcp", duration_ms=1)
    assert record.error is None


def test_parse_cli_json_survives_explicit_json_null_for_tools_and_mcp_servers():
    # `{"tools": null}` (an explicit JSON null, not a missing key) must not
    # crash parse_cli_json — a bad payload is data, never an abort.
    messages = [
        {"type": "system", "subtype": "init", "tools": None, "mcp_servers": None},
        {"type": "result", "result": "x", "num_turns": 1, "usage": {}, "is_error": False},
    ]
    record = parse_cli_json(messages, task_id="T1", arm="bare", duration_ms=1)
    assert record.usage["tools_reported"] == []
    assert record.usage["mcp_servers_reported"] == []
    assert record.error is None


def test_parse_cli_json_survives_explicit_json_null_for_permission_denials():
    messages = [
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": []},
        {
            "type": "result",
            "result": "x",
            "num_turns": 1,
            "usage": {},
            "is_error": False,
            "permission_denials": None,
        },
    ]
    record = parse_cli_json(messages, task_id="T1", arm="bare", duration_ms=1)
    assert record.usage["permission_denials"] == []


def test_parse_cli_json_flags_tool_leak_for_bare_arm():
    messages = [
        {"type": "system", "subtype": "init", "tools": ["Bash"], "mcp_servers": []},
        {"type": "result", "result": "x", "num_turns": 1, "usage": {}, "is_error": False},
    ]
    record = parse_cli_json(messages, task_id="T1", arm="bare", duration_ms=1)
    assert record.error is not None
    assert "bare arm" in record.error.lower()
    assert record.usage["tools_reported"] == ["Bash"]


def test_parse_cli_json_flags_wrong_tools_for_web_arm():
    messages = [
        {"type": "system", "subtype": "init", "tools": ["WebSearch"], "mcp_servers": []},
        {"type": "result", "result": "x", "num_turns": 1, "usage": {}, "is_error": False},
    ]
    record = parse_cli_json(messages, task_id="T1", arm="web", duration_ms=1)
    assert record.error is not None
    assert "web arm" in record.error.lower()


def test_parse_cli_json_retains_stop_reason_and_permission_denials():
    messages = [
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": []},
        {
            "type": "result",
            "result": "x",
            "num_turns": 12,
            "usage": {},
            "is_error": False,
            "stop_reason": "max_turns",
            "permission_denials": [{"tool": "Bash"}],
        },
    ]
    record = parse_cli_json(messages, task_id="T1", arm="bare", duration_ms=1)
    assert record.usage["stop_reason"] == "max_turns"
    assert record.usage["permission_denials"] == [{"tool": "Bash"}]


def test_extract_tool_calls_finds_real_tool_use_blocks():
    messages = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "ToolSearch", "input": {"query": "cite_law"}},
                    {"type": "tool_use", "name": "mcp__legal-it__cite_law", "input": {}},
                ]
            },
        },
    ]
    assert _extract_tool_calls(messages) == ["ToolSearch", "mcp__legal-it__cite_law"]


# --- Variant arms: the wiring that the unit seams above cannot see ---------


def test_materialise_variant_mcp_config_expands_the_plugin_root(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (plugin / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "legal-it": {
                        "command": "bash",
                        "args": ["${CLAUDE_PLUGIN_ROOT}/start_server.sh"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    target = materialise_variant_mcp_config(tmp_path, plugin)
    config = json.loads(target.read_text(encoding="utf-8"))
    assert config["mcpServers"]["legal-it"] == {
        "command": "bash",
        "args": [f"{plugin}/start_server.sh"],
    }


def test_materialise_variant_mcp_config_rejects_an_unreadable_declaration(tmp_path):
    with pytest.raises(ValueError, match="unreadable"):
        materialise_variant_mcp_config(tmp_path, tmp_path / "missing")


def test_run_arm_validates_the_loaded_plugin_root_not_the_repo_server(tmp_path, monkeypatch):
    """Regression: `run_arm` handed the shape check the benchmark's OWN
    plugin/server path — a repo directory that is never a plugin root — so
    every plugin-arm run was recorded as an error even when the pinned
    plugin loaded perfectly. The root that must be checked is the one that
    was actually LOADED, i.e. the variant worktree's plugin/ directory."""
    from benchmarks.legalita.run import arms as arms_mod

    plugin = tmp_path / "variant" / "plugin"
    plugin.mkdir(parents=True)
    (plugin / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "legal-it": {
                        "command": "bash",
                        "args": ["${CLAUDE_PLUGIN_ROOT}/start_server.sh"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    repo_server = tmp_path / "repo" / "plugin" / "server"  # what cli.py passes as plugin_root
    repo_server.mkdir(parents=True)

    payload = [
        {
            "type": "system",
            "subtype": "init",
            "tools": ["Skill", "ToolSearch", "mcp__legal-it__cite_law"],
            "mcp_servers": [{"name": "legal-it", "status": "connected"}],
        },
        {"type": "result", "result": "risposta", "num_turns": 1, "usage": {}, "is_error": False},
    ]
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(arms_mod.subprocess, "run", fake_run)

    task = Task(
        id="T1", track="jurisprudential", domain="civil", query="quesito",
        criteria=[], issue_status="settled", issue_summary="",
        seed_citation=None, builder_confidence="high", curated=False,
    )
    record = run_arm(
        task, "plugin-v2", tmp_path / "workdir", repo_server,
        plugin_dir=plugin, variant_sha="b" * 40,
    )

    assert record.error is None
    assert record.variant_sha == "b" * 40
    argv = captured["argv"]
    assert _flag_value(argv, "--plugin-dir") == [str(plugin)]
    assert "--disable-slash-commands" not in argv
    mounted = json.loads(Path(_flag_value(argv, "--mcp-config")[0]).read_text(encoding="utf-8"))
    assert mounted["mcpServers"]["legal-it"]["args"] == [f"{plugin}/start_server.sh"]
