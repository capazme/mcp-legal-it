"""Executors: data-driven argv construction for `claude -p` (DESIGN §3: a
new tool or model is a YAML file, never an `if arm == ...` branch) and the
run loop with pre-registered retry budget.

Isolation is uniform (DESIGN §6): clean `CLAUDE_CONFIG_DIR`, restricted
setting sources, no foreign plugins, `--strict-mcp-config` so only the
declared server exists. The transcript is persisted whole — tool *results*,
not just names: provenance fidelity is computed from them.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from benchmarks.limes.protocol.rules import Protocol
from benchmarks.limes.runner.manifests import Manifest

# Parity: one neutral bench prompt shared by every surface; "default" means
# the platform default (declared, not hidden — the choice is in the record).
BENCH_SYSTEM_PROMPT = (
    "Sei un giurista italiano esperto. Rispondi al quesito professionale che "
    "ti viene posto in modo completo e tecnicamente accurato, citando le "
    "fonti normative e giurisprudenziali rilevanti. Indica gli estremi "
    "identificativi delle pronunce che citi (corte, sezione, numero, anno). "
    "Non inventare mai estremi di sentenze o contenuti normativi."
)


_WORKDIRS: list[Path] = []


@atexit.register
def _cleanup_workdirs() -> None:
    for workdir in _WORKDIRS:
        shutil.rmtree(workdir, ignore_errors=True)


class ExecutorError(RuntimeError):
    """Raised when a run cannot even be attempted (config, not model)."""


@dataclass
class RunOutcome:
    item_id: str
    model: str
    config_id: str
    ok: bool
    answer: str
    transcript_path: str | None
    attempts: int
    duration_s: float
    error: str | None = None
    excluded: bool = False
    exclusion: str | None = None
    tool_results: list[str] = field(default_factory=list)
    # R-dimension observables from the CLI's own result record (DESIGN §5:
    # token, latency, cost are metrics, not debug output).
    stop: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    num_turns: int | None = None
    cost_usd: float | None = None
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "model": self.model,
            "config_id": self.config_id,
            "ok": self.ok,
            "attempts": self.attempts,
            "duration_s": round(self.duration_s, 3),
            "error": self.error,
            "excluded": self.excluded,
            "exclusion": self.exclusion,
            "transcript_path": self.transcript_path,
            "stop": self.stop,
            "tool_calls": list(self.tool_calls),
            "num_turns": self.num_turns,
            "cost_usd": self.cost_usd,
            "usage": dict(self.usage),
        }


# Built-in tools per surface (parity, DESIGN §3/§6): the only thing that
# varies between cells is the enhancement. No surface gets web access or a
# shell — a plugin cell that could WebSearch would measure the web, not the
# plugin. ToolSearch is the deferred-tool loader MCP tools arrive through;
# Skill is how a plugin's skills are invoked. A manifest may override the
# list (`parity.tools`), and the override is part of config_sha.
SURFACE_TOOLS: dict[str, tuple[str, ...]] = {
    "bare": (),
    "mcp": ("ToolSearch",),
    "plugin": ("ToolSearch", "Skill"),
}


def build_argv(
    surface: str,
    model: str,
    max_turns: int,
    system_prompt: str,
    mcp_config: Path | None,
    prompt: str,
    plugin_dir: Path | None = None,
    tools: tuple[str, ...] | list[str] | None = None,
) -> list[str]:
    """The exact command line for one cell. Pure — safe to assert on.

    The surface only decides *which capabilities are declared*; there is no
    per-tool branching beyond the data table above (DESIGN §3).

    Output is `stream-json` (with `--verbose`, which the CLI requires for
    it): the single-object `json` format carries only the final text, so
    tool RESULTS never reached the record and provenance fidelity could not
    be computed from the transcript (DESIGN §4.1).
    """
    if surface not in SURFACE_TOOLS:
        raise ExecutorError(
            f"surface {surface!r}: executor not implemented "
            f"(supported: {', '.join(SURFACE_TOOLS)})"
        )
    argv = [
        "claude",
        "-p", prompt,
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        "--max-turns", str(max_turns),
        "--permission-mode", "bypassPermissions",
        "--settings", "{}",
        "--setting-sources", "user,project",
        "--strict-mcp-config",
    ]
    if surface != "plugin":
        # Skills are part of a plugin enhancement; everywhere else they are
        # off (the flag disables ALL skills, the plugin's included).
        argv.append("--disable-slash-commands")
    if system_prompt == "bench":
        argv += ["--system-prompt", BENCH_SYSTEM_PROMPT]
    declared = SURFACE_TOOLS[surface] if tools is None else tuple(tools)
    argv += ["--tools", ",".join(declared)]
    if surface == "mcp":
        if mcp_config is None:
            raise ExecutorError("mcp surface requires a rendered mcp config")
        argv += ["--mcp-config", str(mcp_config)]
    elif surface == "plugin":
        # The enhancement brings its own MCP server, skills and agents from
        # the materialized ref; without --plugin-dir the cell ran bare
        # (verified empirically: one turn, zero tool calls).
        if plugin_dir is None:
            raise ExecutorError("plugin surface requires a materialized plugin dir")
        argv += ["--plugin-dir", str(plugin_dir)]
        # --strict-mcp-config (kept: it also keeps the account's claude.ai
        # connectors out of the cell) drops the plugin's own .mcp.json, so
        # the plugin's server is passed explicitly (plugin_mcp_config).
        if mcp_config is not None:
            argv += ["--mcp-config", str(mcp_config)]
    return argv


def plugin_mcp_config(plugin_dir: Path, profile: str | None) -> dict | None:
    """The plugin's own `.mcp.json`, with ${CLAUDE_PLUGIN_ROOT} resolved and
    the manifest profile injected into each server's env."""
    source = plugin_dir / ".mcp.json"
    if not source.is_file():
        return None
    raw = source.read_text(encoding="utf-8").replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_dir))
    data = json.loads(raw)
    for server in (data.get("mcpServers") or {}).values():
        if profile:
            server.setdefault("env", {})["LEGAL_PROFILE"] = profile
    return data


def bootstrap_credentials(scratch: Path) -> None:
    """Seed the scratch CLAUDE_CONFIG_DIR with live credentials.

    The isolation contract gives every run a *clean* config dir, which also
    means an unauthenticated one: without seeding, every cell dies with
    "Not logged in" before touching a single item (verified empirically).
    Sources, in order: the macOS keychain item the host CLI uses (the live
    session — on this host the credentials file can be stale), then the
    ambient CLAUDE_CONFIG_DIR's own file. Fail-closed: no live
    credential source, no run.
    """
    proc = subprocess.run(
        ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        minimal = minimal_credentials(proc.stdout)
        if minimal is not None:
            _write_secret(scratch / ".credentials.json", minimal)
            return
    home_config = Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
    home_config = home_config.expanduser()
    if home_config.resolve() != scratch.resolve():
        candidate = home_config / ".credentials.json"
        if candidate.is_file():
            minimal = minimal_credentials(candidate.read_bytes())
            if minimal is not None:
                _write_secret(scratch / ".credentials.json", minimal)
                return
    raise ExecutorError(
        "nessuna credenziale live trovata (file o keychain): eseguire `claude /login`"
    )


def minimal_credentials(raw: bytes) -> bytes | None:
    """Only the Claude login, never the rest of the keychain item.

    The host item also carries OAuth tokens of every MCP connector the
    user authorised (Slack, Notion, MS365, ...): copying it whole left one
    copy of all of them per executed item under results/. A cell needs
    exactly `claudeAiOauth`; anything else is dropped. None when absent
    (the caller falls through to the next source, then fails closed)."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("claudeAiOauth"), dict):
        return None
    return json.dumps({"claudeAiOauth": data["claudeAiOauth"]}).encode("utf-8")


def _write_secret(path: Path, content: bytes) -> None:
    path.touch(mode=0o600)
    path.chmod(0o600)
    path.write_bytes(content)


# --- usage / rate limits -----------------------------------------------------
#
# A plan quota is a property of the ACCOUNT, not of the configuration under
# test: a rate-limited call must never become an excluded (or failed) item,
# or a cell's denominators would depend on when the quota ran out. The
# executor waits for the reset and retries without spending the retry
# budget; past `max_wait` it aborts the whole run (resume with --resume).
_RATE_LIMIT_RE = re.compile(
    r"usage limit|limit reached|hit your (?:\w+ )?limit|session limit|rate[ _-]?limit|too many requests|\b429\b|overloaded",
    re.IGNORECASE,
)
_RESET_EPOCH_RE = re.compile(r"\|(\d{10})\b")


class RateLimited(RuntimeError):
    """The account's usage limit did not reset within the allowed wait."""


def _is_error_result(message: dict) -> bool:
    return bool(message.get("is_error")) or str(message.get("subtype", "")).startswith("error")


def _reset_wait(text: str, now: float | None = None) -> float | None:
    """Seconds until the reset the CLI announces: `…|<epoch>` or
    `resets 1:30pm (Europe/Rome)`. None when no reset time is stated."""
    now = time.time() if now is None else now
    epoch = _RESET_EPOCH_RE.search(text)
    if epoch:
        return max(60.0, float(epoch.group(1)) - now + 60.0)
    clock = _RESET_CLOCK_RE.search(text)
    if not clock:
        return None
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    hour = int(clock.group(1)) % 12 + (12 if clock.group(3).lower() == "pm" else 0)
    minute = int(clock.group(2) or 0)
    try:
        zone = ZoneInfo(clock.group(4)) if clock.group(4) else None
    except (ZoneInfoNotFoundError, ValueError):
        zone = None
    current = datetime.fromtimestamp(now, zone)
    target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return (target - current).total_seconds() + 60.0


_RESET_CLOCK_RE = re.compile(r"resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?:\s*\(([\w/+-]+)\))?", re.IGNORECASE)


def rate_limit_reset(stdout: str, stderr: str, payload: dict | None, now: float | None = None) -> float | None:
    """Seconds to wait when the reply is a usage/rate-limit refusal, else None.

    Structured signals first — the CLI marks the refusal with
    `api_error_status: 429` on the result and `error: rate_limit` on a
    synthetic assistant message, while `subtype` still says "success" and
    `result` carries the refusal TEXT (verified on a real Pro-plan refusal,
    which the first MVP run scored as an answer). Text patterns are only a
    fallback. Wait = the announced reset time, else a 15-minute backoff."""
    texts = [stderr or ""]
    structured = False
    if payload is not None:
        results = [m for m in _messages(payload) if m.get("type") == "result"]
        failed = [m for m in results if _is_error_result(m)]
        if results and not failed:
            return None  # a real answer: stderr noise never turns it into a refusal
        for message in _messages(payload):
            if message.get("error") == "rate_limit":
                structured = True
        for message in failed:
            if str(message.get("api_error_status")) in ("429", "529"):
                structured = True
            texts.append(str(message.get("result") or ""))
            texts.append(str(message.get("error") or ""))
    elif stdout and len(stdout) < 2000:
        texts.append(stdout)
    blob = "\n".join(texts)
    if not structured and not _RATE_LIMIT_RE.search(blob):
        return None
    wait = _reset_wait(blob, now)
    return wait if wait is not None else 15 * 60.0


def build_env(manifest: Manifest, scratch_config_dir: Path) -> dict[str, str]:
    """Isolation env for one run: clean config dir, profile passthrough."""
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(scratch_config_dir)
    if manifest.profile:
        env["LEGAL_PROFILE"] = manifest.profile
    return env


def run_cell(
    manifest: Manifest,
    model: str,
    item_id: str,
    prompt: str,
    protocol: Protocol,
    out_dir: Path,
    mcp_config: dict | None = None,
    plugin_dir: Path | None = None,
    max_rate_limit_wait_s: float = 6 * 3600,
    sleep=time.sleep,
) -> RunOutcome:
    """Execute one cell of the matrix with retry + exclusion semantics.

    Retry budget is pre-registered in the protocol; every attempt is
    persisted; an exhausted budget is an EXCLUDED run (error rate is a
    published metric, not noise to clean — DESIGN §6).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    # State ownership: this call owns the per-item directory. A repeated run
    # must not leave stale artifacts — a transcript of a previous attempt
    # would masquerade as attempt-1, and a verdict of a previously-ok run
    # would survive next to an excluded outcome and leak into `compare`
    # (which reads verdict.json only).
    for stale in out_dir.glob("attempt-*.json"):
        stale.unlink()
    stale_verdict = out_dir / "verdict.json"
    if stale_verdict.exists():
        stale_verdict.unlink()
    scratch = out_dir / "config-dir"
    if scratch.exists():
        shutil.rmtree(scratch)  # isolation: never inherit a previous run's config state
    scratch.mkdir()
    bootstrap_credentials(scratch)
    # Neutral working directory OUTSIDE any git repository: the CLI loads
    # CLAUDE.md from the project root (the enclosing git toplevel) and its
    # parents, so running from the repository — or from a results dir inside
    # it — fed every cell (bare included) ~40k tokens describing the very
    # tools under test (verified empirically on the MVP run).
    workdir = Path(tempfile.mkdtemp(prefix="limes-work-"))
    _WORKDIRS.append(workdir)
    mcp_path: Path | None = None
    if mcp_config is not None:
        mcp_path = out_dir / "mcp-config.json"
        mcp_path.write_text(json.dumps(mcp_config), encoding="utf-8")

    argv = build_argv(
        surface=manifest.surface,
        model=model,
        max_turns=manifest.max_turns,
        system_prompt=manifest.system_prompt,
        mcp_config=mcp_path,
        prompt=prompt,
        plugin_dir=plugin_dir,
        tools=manifest.tools,
    )
    env = build_env(manifest, scratch)

    try:
        return _attempts(manifest, model, item_id, protocol, out_dir, argv, env, workdir,
                         max_rate_limit_wait_s, sleep)
    finally:
        # The scratch dir holds a live login token: it never outlives the call.
        shutil.rmtree(scratch, ignore_errors=True)


def _attempts(manifest, model, item_id, protocol, out_dir, argv, env, workdir,
              max_rate_limit_wait_s, sleep) -> RunOutcome:
    last_error: str | None = None
    failure_kind = "errore_init_tool_shape"
    waited = 0.0
    attempt = 0
    while attempt < protocol.retry_budget + 1:
        attempt += 1
        started = time.monotonic()
        transcript_path = out_dir / f"attempt-{attempt}.json"
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=protocol.timeout_s,
                env=env,
                cwd=workdir,
                check=False,
            )
        except subprocess.TimeoutExpired:
            last_error = f"timeout after {protocol.timeout_s}s"
            failure_kind = "errore_init_tool_shape"
            continue
        except FileNotFoundError:
            raise ExecutorError(
                "runner 'claude' non trovato nel PATH"
            ) from None

        transcript_path.write_text(proc.stdout, encoding="utf-8")
        duration = time.monotonic() - started
        payload = _parse_json_output(proc.stdout)
        wait = rate_limit_reset(proc.stdout, proc.stderr, payload)
        if wait is not None:
            if waited + wait > max_rate_limit_wait_s:
                raise RateLimited(
                    f"{item_id}: limite d'uso dell'account non rientrato entro "
                    f"{max_rate_limit_wait_s / 3600:.1f} h — riprendere con --resume"
                )
            print(f"    limite d'uso: attendo {wait / 60:.0f} min e riprovo {item_id}", flush=True)
            sleep(wait)
            waited += wait
            attempt -= 1  # a quota refusal never spends the retry budget
            transcript_path.unlink(missing_ok=True)
            continue
        if payload is None:
            last_error = "output non JSON (crash o stderr)"
            failure_kind = "errore_init_tool_shape"
            continue

        answer, tool_results, stop_reason = _extract_payload(payload)
        meta = _result_meta(payload)
        if stop_reason == "error_max_turns":
            # The configuration ran out of turns without answering: that is
            # the configuration's own failure, scored as a fail (empty
            # answer), never excluded — excluding it would reward a surface
            # that loops (DESIGN §6: error rate is a metric).
            return RunOutcome(
                item_id=item_id, model=model, config_id=manifest.id, ok=True,
                answer=answer, transcript_path=str(transcript_path),
                attempts=attempt, duration_s=duration, tool_results=tool_results,
                stop="max_turns", **meta,
            )
        errored = any(_is_error_result(m) for m in _messages(payload) if m.get("type") == "result")
        if errored or (stop_reason or "").startswith("error") or (answer == "" and not tool_results):
            last_error = f"risposta vuota (attempt {attempt}, stop={stop_reason})"
            failure_kind = "risposta_vuota"
            continue

        return RunOutcome(
            item_id=item_id,
            model=model,
            config_id=manifest.id,
            ok=True,
            answer=answer,
            transcript_path=str(transcript_path),
            attempts=attempt,
            duration_s=duration,
            tool_results=tool_results,
            stop=stop_reason,
            **meta,
        )

    # Budget exhausted: excluded run, recorded, never silent. The exclusion
    # id is tracked when it happens (both are pre-registered in the
    # protocol), never re-derived from the error string.
    return RunOutcome(
        item_id=item_id,
        model=model,
        config_id=manifest.id,
        ok=False,
        answer="",
        transcript_path=None,
        attempts=protocol.retry_budget + 1,
        duration_s=0.0,
        error=last_error,
        excluded=True,
        exclusion=failure_kind,
    )


def _parse_json_output(stdout: str) -> dict | None:
    """Parse the CLI output: a single JSON object (`json` format) or a JSONL
    message stream (`stream-json`), normalized to `{"messages": [...]}`."""
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        messages = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue  # stray non-JSON line (e.g. a warning): skip, not fatal
            if isinstance(message, dict):
                messages.append(message)
        return {"messages": messages} if messages else None
    return payload if isinstance(payload, dict) else None


def _messages(payload: dict) -> list[dict]:
    if payload.get("type") == "result":
        return [payload]
    messages = payload.get("messages") or (
        [payload] if payload.get("type") in ("assistant", "user", "system") else []
    )
    return [m for m in messages if isinstance(m, dict)]


def _extract_payload(payload: dict) -> tuple[str, list[str], str | None]:
    """Extract (final_text, tool_result_texts, stop_reason) from the CLI JSON.

    The answer is the final `result` text when the stream carries one: the
    intermediate assistant turns ("cerco la norma…") are process, not the
    answer, and scoring them would let tool-call chatter hit the markers.
    Without a result text the assistant text blocks are joined.
    """
    answer_parts: list[str] = []
    tool_results: list[str] = []
    stop_reason: str | None = None
    final_text: str | None = None
    for message in _messages(payload):
        if message.get("type") == "result":
            stop_reason = message.get("subtype")
            if message.get("result"):
                final_text = str(message["result"])
            continue
        content = message.get("message", {}).get("content") or []
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                answer_parts.append(str(block.get("text", "")))
            elif block.get("type") == "tool_result":
                inner = block.get("content")
                if isinstance(inner, list):
                    for piece in inner:
                        if isinstance(piece, dict) and piece.get("type") == "text":
                            tool_results.append(str(piece.get("text", "")))
                elif isinstance(inner, str):
                    tool_results.append(inner)
    answer = final_text if final_text is not None else "\n".join(answer_parts)
    return answer.strip(), tool_results, stop_reason


def _result_meta(payload: dict) -> dict:
    """R-dimension observables: tool calls made, turns, cost, token usage."""
    tool_calls: list[str] = []
    meta: dict = {"tool_calls": tool_calls, "num_turns": None, "cost_usd": None, "usage": {}}
    for message in _messages(payload):
        if message.get("type") == "result":
            meta["num_turns"] = message.get("num_turns")
            meta["cost_usd"] = message.get("total_cost_usd")
            usage = message.get("usage") or {}
            meta["usage"] = {
                k: usage[k]
                for k in ("input_tokens", "output_tokens",
                          "cache_creation_input_tokens", "cache_read_input_tokens")
                if k in usage
            }
            continue
        content = message.get("message", {}).get("content") or []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls.append(str(block.get("name", "")))
    return meta
