"""Run one task through one arm via `claude -p`.

The arms differ in tool availability and in NOTHING else: same model,
same system prompt, same turn cap, same empty settings, same clean working
directory. `--system-prompt` replaces Claude Code's default rather than
appending to it, which is what makes the bare arm genuinely bare.

The variant arms (`plugin-v2`, `plugin-v3`) extend the same principle one
level up: each loads ONE pinned version of the whole legal-it deliverable
via `--plugin-dir` — the MCP server, the skills, the agents, the slash
commands and the citation-gate hook travel together, exactly as a real
user receives them from the marketplace. The directory comes from a git
worktree pinned to a ref (benchmarks/legalita/run/variants.py), and the
commit it was pinned to is recorded per-run in RunRecord.variant_sha.
Because skills and prompt bodies are part of what these arms load, they
are the arms that can measure content-layer changes between versions —
which the plain `mcp` arm (server only, via --mcp-config) cannot see.

Two common flags are therefore NOT common to the plugin arms, both settled
by live probing on CLI 2.1.278 rather than by reading help text:
`--disable-slash-commands` also strips the `Skill` built-in (skills and
commands are the content layer under test, so the flag is dropped for
these arms only), and `--strict-mcp-config` also suppresses the plugin's
OWN `.mcp.json` server, so the pinned plugin's declaration is re-mounted
explicitly on the same strict footing (see
`materialise_variant_mcp_config`).

Live-probed against `claude -p` on 2026-07-27 (see task-5-brief.md and
task-5-report.md for the full trail — several rounds of probing were needed
beyond what the brief anticipated):

- `--output-format json` prints a JSON *array* of messages
  (`system`, `assistant`, ..., `result`), not a single object. The answer
  lives in the last message, the one with `type == "result"`.
- `--allowedTools` / `--disallowedTools` are permission-prompt allow/deny
  lists layered on top of the FULL tool catalog — under
  `--permission-mode bypassPermissions` they do not restrict which tools
  the model can actually call (verified: `--allowedTools WebSearch WebFetch`
  still let the model invoke `Skill` and `Bash`). `--tools` is the real
  hard allowlist ("available tools from the built-in set"; `""` disables
  all of them) and is what actually produces `tools: []` / `tools: [X, Y]`
  in the init message and blocks execution of anything else.
- This operator's Claude Code install has `ENABLE_TOOL_SEARCH=true` set
  globally, which defers MCP-server tools behind the `ToolSearch` meta-tool
  instead of listing them eagerly — `--tools ""` for the mcp arm silently
  starves it of any way to discover `mcp__legal-it__*`, so the arm produces
  an answer from the model's own memory while looking like a real MCP run.
  The mcp arm therefore uses `--tools "ToolSearch"`, not `--tools ""`.
- `--disable-slash-commands` is applied to every arm uniformly: this
  operator's personal Claude Code install has ~140 slash commands/skills
  from unrelated plugins (superpowers, bmad-method, personal skills) loaded
  into every session regardless of `--settings {}`. Their mere presence in
  context (not just being callable) measurably changes model behaviour —
  observed once as the model narrating a "routing-lavoro" skill check
  instead of answering. Disabling them is a uniform no-op for arms that
  never used skills anyway (bare, web) and removes a real confound for mcp.
- `--setting-sources project` is applied to every arm uniformly, for a
  deeper version of the same problem: the "routing-lavoro"/"verifica-lavoro"
  skill-narration still appeared even with slash commands disabled and
  `slash_commands_count: 0`, which meant it wasn't coming from the skill
  registry at all but from the operator's global `~/.claude/CLAUDE.md` and
  `~/.claude/settings.json` — a "user"-level source that `--settings {}`
  does not touch (it *adds* settings, it does not change which sources are
  read). `--bare` and `--safe-mode` both strip this too, but `--bare`
  forces API-key auth (breaks this OAuth-subscription session) and
  `--safe-mode` also disables MCP servers with no override, breaking the
  mcp arm. `--setting-sources project` excludes the "user" source while
  leaving `--mcp-config` and MCP connectivity untouched, and the run's
  workdir has no project-level `.claude/` to load either — verified over
  repeated trials to eliminate the contamination while the mcp arm still
  reaches `mcp__legal-it__*` tools normally.
- The prompt is passed on stdin, never as an argv element, so the argv is
  otherwise identical across arms except for the tool-related flags.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from benchmarks.legalita.schema import ARMS, VARIANT_ARMS, RunRecord, Task

SYSTEM_PROMPT = (
    "Sei un giurista italiano esperto. Rispondi al quesito professionale che ti "
    "viene posto in modo completo e tecnicamente accurato, citando le fonti "
    "normative e giurisprudenziali rilevanti. Indica gli estremi identificativi "
    "delle pronunce che citi (corte, sezione, numero, anno). Non inventare mai "
    "estremi di sentenze o contenuti normativi."
)

ARM_TOOLS: dict[str, list[str]] = {
    "bare": [],
    "web": ["WebSearch", "WebFetch"],
    "mcp": ["mcp__legal-it__*"],
    # A plugin arm gets the same MCP capability as `mcp` PLUS the Skill
    # built-in: the plugin's skills/agents/commands are half of what this
    # arm exists to measure, and Skill is the built-in that surfaces them.
    "plugin-v2": ["mcp__legal-it__*", "Skill"],
    "plugin-v3": ["mcp__legal-it__*", "Skill"],
}

# The CLI's `--tools` value that actually produces the capability declared
# in ARM_TOOLS above. Not a 1:1 rendering of ARM_TOOLS: `--tools` only
# accepts names "from the built-in set" (per `claude -p --help`), so
# `mcp__legal-it__*` is never a legal value there. MCP-server tools are
# granted instead via `--mcp-config`, and in this environment they must be
# *discovered* through the built-in `ToolSearch` meta-tool (see module
# docstring) — so the mcp arm's `--tools` value is `ToolSearch`, and the
# actual restriction to legal-it-only tools comes from `--strict-mcp-config`
# (no other MCP server is declared) plus `--disable-slash-commands` (no
# skills to search for instead).
_CLI_TOOLS_FLAG: dict[str, str] = {
    "bare": "",
    "web": ",".join(ARM_TOOLS["web"]),
    "mcp": "ToolSearch",
    # Same ToolSearch discovery path as the mcp arm, plus Skill for the
    # plugin's own skills/commands surface.
    "plugin-v2": "Skill,ToolSearch",
    "plugin-v3": "Skill,ToolSearch",
}

_MCP_CONFIG_TEMPLATE = Path(__file__).with_name("mcp-config.json")


def build_argv(
    arm: str,
    model: str,
    max_turns: int,
    mcp_config: str | None,
    plugin_dir: str | None = None,
) -> list[str]:
    """The exact command line for one arm. Pure — safe to assert on."""
    if arm not in ARMS:
        raise ValueError(f"arm: expected one of {ARMS}, got {arm!r}")

    argv = [
        "claude",
        "-p",
        "--model", model,
        "--system-prompt", SYSTEM_PROMPT,
        "--settings", "{}",
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--permission-mode", "bypassPermissions",
        "--tools", _CLI_TOOLS_FLAG[arm],
    ]

    if arm not in VARIANT_ARMS:
        # Keeps the plain arms out of the operator's global slash commands.
        # NEVER pass this to a plugin arm: on CLI 2.1.278 it also strips the
        # Skill built-in, and with it every skill and command the pinned
        # plugin ships — i.e. exactly the content layer those arms exist to
        # measure. Probed, not inferred.
        argv += ["--disable-slash-commands"]

    if arm in VARIANT_ARMS and not plugin_dir:
        raise ValueError(
            f"{arm} requires a plugin_dir (the variant worktree's "
            "plugin/ directory) — without it the arm would silently "
            "run bare"
        )

    if arm in ("mcp", *VARIANT_ARMS):
        # Every MCP-bearing arm mounts its server explicitly, on the strict
        # footing --strict-mcp-config sets. For a plugin arm that config is
        # built from the pinned plugin's OWN declaration: strict mode would
        # otherwise drop the plugin's .mcp.json server and leave the arm
        # holding skills with no tools behind them.
        if not mcp_config:
            raise ValueError(
                f"{arm} requires an mcp_config path (the server it must "
                "mount under --strict-mcp-config)"
            )
        argv += ["--mcp-config", mcp_config]

    if arm in VARIANT_ARMS:
        argv += ["--plugin-dir", plugin_dir]
    return argv


def arm_env(arm: str) -> dict[str, str]:
    """Environment overlay for one arm.

    Both MCP-bearing arms run the reduced `normativa` profile: serving
    every tool schema costs tens of thousands of tokens before the model
    reads the query (declared Limitation #24), and the profile is a
    property of the SERVER under test — identical for the plain `mcp`
    arm and for the plugin arms, so it never confounds the comparison
    between variants.
    """
    return {"LEGAL_PROFILE": "normativa"} if arm in ("mcp", *VARIANT_ARMS) else {}


def _extract_tool_calls(messages: list[dict]) -> list[str]:
    """Tool names invoked across all assistant messages, in call order."""
    calls: list[str] = []
    for message in messages:
        if message.get("type") != "assistant":
            continue
        content = message.get("message", {}).get("content", [])
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                calls.append(str(block.get("name", "")))
    return calls


def _hook_feedback(messages: list[dict]) -> str | None:
    """Detect a Stop-hook-injected synthetic user turn in the transcript.

    Claude Code marks these `type == "user"`, `isSynthetic: true`, text
    starting with `"Stop hook feedback:"`. This operator's personal Claude
    Code install has the `legal-it` plugin's own citation-gate Stop hook
    registered globally (this repo also ships as a Claude Code plugin for
    daily legal work) — it fires identically as a registered hook in every
    arm, but its EFFECT is not uniform: only arms that can reach the
    plugin's tools can satisfy it by calling `cite_law()`, so bare/web get
    a forced extra turn and a garbled answer whenever they attempt a
    citation. `isolation_env()` sets `LEGAL_IT_GATE_SKIP_PATHS` for the
    known case, but no released gate honours that variable (see
    `isolation_env()`), so this detector is the actual guard, and the
    backstop for an unrelated hook on someone else's machine.

    For a plugin arm the same signal means something different: the
    citation gate is part of the product under test (it ships in the
    plugin's hooks/), so the detector's result is recorded as a
    `hook_interventions` event on the run, NOT as an error — an arm whose
    gate fires is behaving exactly like the deliverable being measured,
    and dropping those runs would bias the comparison against the very
    behaviour the arm exists to observe.
    """
    for message in messages:
        if message.get("type") != "user" or not message.get("isSynthetic"):
            continue
        content = message.get("message", {}).get("content", [])
        text = "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
        if text.startswith("Stop hook feedback:"):
            return text.strip()[:300]
    return None


def _legal_it_server_issue(
    arm_label: str,
    tools_reported: list[str],
    mcp_servers_reported: list[dict],
) -> str | None:
    """Shared server-side shape check for arms that mount the legal-it MCP
    server (the plain `mcp` arm and both plugin arms). Returns a
    human-readable mismatch description, or None if the server side of the
    shape is healthy."""
    tools_set = set(tools_reported)
    legal_it_entry = next(
        (
            s for s in mcp_servers_reported
            if isinstance(s, dict) and s.get("name") == "legal-it"
        ),
        None,
    )
    if legal_it_entry is None:
        return (
            f"{arm_label}: expected an mcp_servers entry named 'legal-it', "
            f"init reported mcp_servers={mcp_servers_reported!r}"
        )

    # A positive status ("connected") is never required — "pending" is
    # what a healthy run typically shows in the init snapshot (the
    # connection settles a moment later, well before the model's first
    # turn — see task-5-report.md). But an EXPLICIT failure status must
    # not be waved through just because ToolSearch happens to be listed:
    # ToolSearch is a built-in offered regardless of whether any
    # particular MCP server connected, so its presence proves nothing
    # about legal-it specifically and must never override a failed
    # server entry.
    status = str(legal_it_entry.get("status") or "").lower()
    if any(marker in status for marker in ("fail", "error")):
        return (
            f"{arm_label}: legal-it mcp server reported an explicit failure "
            f"status ({legal_it_entry.get('status')!r}) — ToolSearch or "
            "direct mcp__legal-it__* tool names being present does not "
            f"override this, init reported mcp_servers={mcp_servers_reported!r}"
        )

    # Tool Search is this environment's discovery path (see module
    # docstring); a future machine without ENABLE_TOOL_SEARCH would
    # instead list mcp__legal-it__* tools directly. Either is healthy —
    # what's unhealthy is neither being present despite the server
    # not reporting an explicit failure.
    has_tool_search = "ToolSearch" in tools_set
    has_direct_tools = any(t.startswith("mcp__legal-it__") for t in tools_set)
    if not (has_tool_search or has_direct_tools):
        return (
            f"{arm_label}: legal-it server reported but no way to reach its "
            "tools (no ToolSearch, no mcp__legal-it__* entries), init "
            f"reported tools={sorted(tools_set)}"
        )
    return None


def _validate_tool_shape(
    arm: str,
    tools_reported: list[str],
    mcp_servers_reported: list[dict],
    plugin_root: Path | None = None,
) -> str | None:
    """Check the init message's reported tools/mcp_servers against what this
    arm actually asked for. Returns a human-readable mismatch description, or
    None if the shape is healthy.

    This is the check that catches the failure mode that matters most: an
    arm silently getting fewer or different tools than it was granted — the
    MCP server failing to start, tool search being unavailable on some future
    machine, a flag regression reintroducing the wrong `--tools` value — and
    still producing `is_error: false`, `tool_calls: []`, and a plausible
    answer drawn from the model's own memory. Without this check that run is
    indistinguishable from a legitimate "the model didn't need a tool for
    this question" result, and a whole degraded batch would quietly drag the
    mcp arm's grounding numbers toward the bare arm's — the single worst
    outcome this benchmark could produce, since that is exactly the
    direction of the question it exists to answer.
    """
    tools_set = set(tools_reported)
    server_names = {s.get("name") for s in mcp_servers_reported if isinstance(s, dict)}

    if arm == "bare":
        if tools_set:
            return f"bare arm: expected no tools, init reported tools={sorted(tools_set)}"
        if server_names:
            return (
                f"bare arm: expected no mcp servers, init reported "
                f"mcp_servers={sorted(server_names)}"
            )
        return None

    if arm == "web":
        expected = set(ARM_TOOLS["web"])
        if tools_set != expected:
            return (
                f"web arm: expected tools=={sorted(expected)}, "
                f"init reported tools={sorted(tools_set)}"
            )
        if server_names:
            return (
                f"web arm: expected no mcp servers, init reported "
                f"mcp_servers={sorted(server_names)}"
            )
        return None

    if arm == "mcp":
        return _legal_it_server_issue("mcp arm", tools_reported, mcp_servers_reported)

    if arm in VARIANT_ARMS:
        # A plugin arm mounts the FULL product via --plugin-dir. The
        # declared root must at least be a plugin root, and its MCP server
        # must have come up exactly as for the plain mcp arm; the extra
        # requirement is the Skill built-in, because skills/agents/
        # commands are the other half of what this arm exists to measure.
        label = f"{arm} arm"
        if plugin_root is None:
            return (
                f"{label}: no plugin root provided — the variant worktree "
                "was not provisioned for this run"
            )
        if not plugin_root.is_dir() or not (plugin_root / ".mcp.json").is_file():
            return (
                f"{label}: plugin root {plugin_root} is not a plugin "
                "directory (no .mcp.json) — wrong or missing variant "
                "worktree, and the run must not look healthy"
            )
        server_issue = _legal_it_server_issue(label, tools_reported, mcp_servers_reported)
        if server_issue is not None:
            return server_issue
        if "Skill" not in set(tools_reported):
            return (
                f"{label}: expected the Skill built-in to be reported — a "
                "plugin arm measures the plugin's skills/agents/commands "
                "too, not only its MCP server — init reported "
                f"tools={sorted(set(tools_reported))}"
            )
        return None

    return None


def isolation_env(workdir: Path) -> dict[str, str]:
    """Environment overlay applied identically to every arm.

    This is independent of tool availability — it exists only because this
    operator's Claude Code install has the `legal-it` plugin's Stop hook
    registered globally, and it must be neutralised the same way regardless
    of which arm is running, or the "arms differ only in tools" invariant
    breaks. `LEGAL_IT_GATE_SKIP_PATHS` is the gate's switch for exactly this
    domain-separation case, but no released gate honours it (as of
    2026-09-25): the support written for it in July 2026 never reached
    develop. Until the installed plugin carries it, this overlay is inert
    and `_hook_feedback()` is the only guard. LIMES avoids the problem with
    a scratch CLAUDE_CONFIG_DIR, where the global plugin never loads.
    Scoping the variable to the run's own workdir keeps the effect local to
    the benchmark without silencing the gate for the operator's real legal
    work elsewhere.
    """
    return {"LEGAL_IT_GATE_SKIP_PATHS": str(workdir.resolve())}


def parse_cli_json(
    payload: list[dict],
    task_id: str,
    arm: str,
    duration_ms: int,
    plugin_root: Path | None = None,
) -> RunRecord:
    """Turn `claude -p --output-format json` output into a RunRecord.

    `payload` is the JSON array of stream messages the CLI prints, not a
    single object. The answer, turn count and usage all live on the last
    message, identified by `type == "result"` — never by array position.
    Raises if that message is absent: an empty answer must never be
    confused with a model that genuinely produced nothing.

    Also verifies the init message's reported `tools`/`mcp_servers` against
    what this arm asked for (see `_validate_tool_shape`) and records what was
    actually reported either way, so a mismatched run is data about the
    environment rather than silently lost or silently trusted.
    """
    if not isinstance(payload, list):
        raise ValueError(
            f"parse_cli_json: expected a list of CLI messages, got {type(payload).__name__}"
        )

    result_message = next((m for m in payload if m.get("type") == "result"), None)
    if result_message is None:
        raise ValueError(
            f"parse_cli_json: no message with type == 'result' in CLI output "
            f"for task {task_id!r} arm {arm!r}"
        )

    system_message = next((m for m in payload if m.get("type") == "system"), None)

    is_error = bool(result_message.get("is_error"))
    # NOTE for whoever writes the Task 11 report generator: `usage` is named
    # for the CLI's token-accounting block, but this function also rides
    # four extra keys in it — tools_reported, mcp_servers_reported,
    # stop_reason, permission_denials — since RunRecord has no dedicated
    # fields for them. Look here, not just at `result_message["usage"]`.
    usage = dict(result_message.get("usage", {}))

    # tools_reported/mcp_servers_reported drive the shape check below even
    # when there is no system message (defaults to empty); they are only
    # persisted into usage when a system message actually supplied them, so
    # an incomplete payload doesn't fabricate a false "reported nothing".
    # `or []` guards against the key being present with an explicit JSON
    # null, which `.get(key, [])` alone does not catch (`list(None)` raises
    # TypeError, and a raise here would abort the whole run instead of
    # producing a RunRecord — the one thing this harness must never do).
    tools_reported: list[str] = []
    mcp_servers_reported: list[dict] = []
    if system_message is not None:
        tools_reported = list(system_message.get("tools") or [])
        mcp_servers_reported = list(system_message.get("mcp_servers") or [])
        usage["tools_reported"] = tools_reported
        usage["mcp_servers_reported"] = mcp_servers_reported

        slash_commands = system_message.get("slash_commands")
        if slash_commands is not None:
            # Recorded so the artifact shows this count was constant across
            # arms — Claude Code's own commands/skills load regardless of
            # the tool filter and are not part of the experiment's variable.
            usage["slash_commands_count"] = len(slash_commands)

    if "stop_reason" in result_message:
        usage["stop_reason"] = result_message["stop_reason"]
    if "permission_denials" in result_message:
        usage["permission_denials"] = list(result_message["permission_denials"] or [])

    model_usage = result_message.get("modelUsage") or {}
    model = next(iter(model_usage), result_message.get("model", "unknown"))

    issues: list[str] = []
    shape_issue = _validate_tool_shape(arm, tools_reported, mcp_servers_reported, plugin_root)
    if shape_issue is not None:
        issues.append(shape_issue)
    hook_feedback = _hook_feedback(payload)
    if hook_feedback is not None:
        if arm in VARIANT_ARMS:
            # The plugin's own Stop hook (the citation gate) firing is
            # PRODUCT BEHAVIOUR for a plugin arm, not contamination: the
            # gate ships inside the plugin under test. Recorded as an
            # event on the run, never an error — the arm whose gate fires
            # is exactly the arm being measured.
            usage["hook_interventions"] = {
                "source": "plugin-under-test",
                "excerpt": hook_feedback,
            }
        else:
            # The run still completed, so the answer is kept — but a hook
            # intervened mid-run, which is exactly the kind of arm-specific
            # side effect the experiment cannot tolerate. Flag it rather
            # than silently mixing a contaminated run into clean ones.
            issues.append(
                f"stop hook fired mid-run, isolation may have failed: {hook_feedback}"
            )

    if is_error:
        error = "cli reported is_error"
    elif issues:
        error = " | ".join(issues)
    else:
        error = result_message.get("error")

    return RunRecord(
        task_id=task_id,
        arm=arm,
        model=model,
        answer="" if is_error else str(result_message.get("result", "")),
        tool_calls=_extract_tool_calls(payload),
        num_turns=int(result_message.get("num_turns", 0)),
        duration_ms=duration_ms,
        usage=usage,
        error=error,
    )


def materialise_mcp_config(workdir: Path, plugin_root: Path) -> Path:
    """Write the plain `mcp` arm's MCP config into the run's working directory.

    Server only. The plugin arms mount their own pinned server through
    `materialise_variant_mcp_config` instead — same strict footing, but the
    launch command is whatever the plugin under test declares.
    """
    text = _MCP_CONFIG_TEMPLATE.read_text(encoding="utf-8")
    target = workdir / "mcp-config.json"
    target.write_text(text.replace("PLUGIN_ROOT", str(plugin_root)), encoding="utf-8")
    return target


def materialise_variant_mcp_config(workdir: Path, plugin_dir: Path) -> Path:
    """Mount a variant plugin's OWN declared MCP server, explicitly.

    A plugin arm passes `--strict-mcp-config` for the same reason every
    other arm does: to keep whatever servers the operator happens to have
    configured out of the run. Live probing on CLI 2.1.278 shows that flag
    ALSO suppresses the plugin's own `.mcp.json` server, which would leave
    the arm holding skills but no tools at all — so the pinned plugin's
    declaration is re-mounted here on the same strict footing, with
    `${CLAUDE_PLUGIN_ROOT}` expanded to the provisioned worktree. The
    server then reports as `legal-it` / connected, which is what the shape
    check expects.

    Read, not templated: the launch command stays whatever the version
    under test declares, so a future release that changes its launcher is
    measured as it ships rather than as this harness remembers it.
    """
    declaration = plugin_dir / ".mcp.json"
    try:
        config = json.loads(declaration.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{plugin_dir}: unreadable plugin .mcp.json ({exc})") from exc
    text = json.dumps(config, ensure_ascii=False).replace(
        "${CLAUDE_PLUGIN_ROOT}", str(plugin_dir)
    )
    target = workdir / "mcp-config-variant.json"
    target.write_text(text, encoding="utf-8")
    return target


def run_arm(
    task: Task,
    arm: str,
    workdir: Path,
    plugin_root: Path,
    model: str = "opus",
    # One constant for EVERY arm: the cap is part of the parity controls, so
    # it can never be raised for the tool-bearing arms alone without turning
    # "answered" into an arm-specific outcome. 30 rather than the previous
    # 12 after live probing on CLI 2.1.278: with ~227 tools behind tool
    # search, a 12-turn budget was consumed entirely by discovery and ended
    # `stop_reason=tool_use` with an empty answer — an arm that cannot reach
    # the point of answering is not a measurement of anything.
    max_turns: int = 30,
    timeout_s: int = 900,
    plugin_dir: Path | None = None,
    variant_sha: str | None = None,
) -> RunRecord:
    """Execute one task in one arm. `workdir` MUST be empty of CLAUDE.md.

    `plugin_dir`/`variant_sha` are required for a variant arm
    (`plugin-v2`, `plugin-v3`): the directory loaded via --plugin-dir and
    the commit the variant worktree was pinned to, both recorded on the
    run so the comparison is reproducible from the artifact alone.
    """
    if arm in VARIANT_ARMS and (plugin_dir is None or variant_sha is None):
        raise ValueError(
            f"{arm} requires plugin_dir and variant_sha (provision the "
            "variant worktrees first: legalita variants)"
        )

    workdir.mkdir(parents=True, exist_ok=True)
    if arm == "mcp":
        mcp_config = str(materialise_mcp_config(workdir, plugin_root))
    elif arm in VARIANT_ARMS:
        mcp_config = str(materialise_variant_mcp_config(workdir, Path(plugin_dir)))
    else:
        mcp_config = None
    # The root the shape check must inspect is the one that was LOADED. For a
    # variant arm that is the pinned worktree's plugin/ directory — never the
    # benchmark's own plugin/server, which is not a plugin directory at all
    # and used to flag every plugin run as broken.
    shape_root = Path(plugin_dir) if arm in VARIANT_ARMS else plugin_root
    argv = build_argv(
        arm, model=model, max_turns=max_turns, mcp_config=mcp_config,
        plugin_dir=str(plugin_dir) if plugin_dir else None,
    )

    # isolation_env is identical for every arm; arm_env is the only overlay
    # that may legitimately vary by arm (currently just LEGAL_PROFILE).
    env = {**os.environ, **isolation_env(workdir), **arm_env(arm)}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            input=task.query,
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed = int((time.monotonic() - started) * 1000)
        return RunRecord(
            task_id=task.id, arm=arm, model=model, answer="", tool_calls=[],
            num_turns=0, duration_ms=elapsed, usage={}, error=f"timeout after {timeout_s}s",
            variant_sha=variant_sha,
        )

    elapsed = int((time.monotonic() - started) * 1000)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        # stderr usually holds the actual reason (auth failure, crash) when
        # stdout never became valid JSON — the returncode alone doesn't say
        # why, and dropping stderr here would discard the one clue available.
        return RunRecord(
            task_id=task.id, arm=arm, model=model, answer="", tool_calls=[],
            num_turns=0, duration_ms=elapsed, usage={},
            error=(
                f"unparseable CLI output (returncode={completed.returncode}): "
                f"stdout={completed.stdout[:200]!r} stderr={completed.stderr[:200]!r}"
            ),
            variant_sha=variant_sha,
        )

    try:
        record = parse_cli_json(
            payload, task_id=task.id, arm=arm, duration_ms=elapsed,
            plugin_root=shape_root,
        )
        record.variant_sha = variant_sha
    except ValueError as exc:
        return RunRecord(
            task_id=task.id, arm=arm, model=model, answer="", tool_calls=[],
            num_turns=0, duration_ms=elapsed, usage={},
            error=f"{exc} (returncode={completed.returncode}, stderr={completed.stderr[:200]!r})",
            variant_sha=variant_sha,
        )

    if completed.returncode != 0:
        # A non-zero exit alongside a well-formed `result` message is still
        # worth surfacing — a process that emits valid JSON before crashing
        # is a real, previously-unflagged failure mode.
        rc_note = f"cli exited with returncode={completed.returncode} despite well-formed output"
        record.error = f"{record.error} | {rc_note}" if record.error else rc_note
    return record
