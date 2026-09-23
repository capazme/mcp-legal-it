"""Executors: data-driven argv construction for `claude -p` (DESIGN §3: a
new tool or model is a YAML file, never an `if arm == ...` branch) and the
run loop with pre-registered retry budget.

Isolation is uniform (DESIGN §6): clean `CLAUDE_CONFIG_DIR`, restricted
setting sources, no foreign plugins, `--strict-mcp-config` so only the
declared server exists. The transcript is persisted whole — tool *results*,
not just names: provenance fidelity is computed from them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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
        }


def build_argv(
    surface: str,
    model: str,
    max_turns: int,
    system_prompt: str,
    mcp_config: Path | None,
    prompt: str,
) -> list[str]:
    """The exact command line for one cell. Pure — safe to assert on.

    The surface only decides *which capabilities are declared*; there is no
    per-tool branching beyond the data table below (DESIGN §3).
    """
    argv = [
        "claude",
        "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--permission-mode", "bypassPermissions",
        "--settings", "{}",
        "--setting-sources", "user,project",
        "--strict-mcp-config",
        "--disable-slash-commands",
    ]
    if system_prompt == "bench":
        argv += ["--system-prompt", BENCH_SYSTEM_PROMPT]
    if surface == "bare":
        argv += ["--tools", ""]
    elif surface == "mcp":
        if mcp_config is None:
            raise ExecutorError("mcp surface requires a rendered mcp config")
        argv += ["--tools", "ToolSearch", "--mcp-config", str(mcp_config)]
    elif surface == "plugin":
        # The enhancement declares its own tools/skills; no extra flags
        # beyond strict isolation, mirroring the historical harness.
        pass
    else:
        raise ExecutorError(
            f"surface {surface!r}: executor not implemented in wave 0 "
            f"(supported: bare, mcp, plugin)"
        )
    return argv


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
        creds = scratch / ".credentials.json"
        creds.write_bytes(proc.stdout)
        creds.chmod(0o600)
        return
    home_config = Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
    home_config = home_config.expanduser()
    if home_config.resolve() != scratch.resolve():
        candidate = home_config / ".credentials.json"
        if candidate.is_file():
            shutil.copy(candidate, scratch / ".credentials.json")
            return
    raise ExecutorError(
        "nessuna credenziale live trovata (file o keychain): eseguire `claude /login`"
    )


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
    )
    env = build_env(manifest, scratch)

    last_error: str | None = None
    failure_kind = "errore_init_tool_shape"
    for attempt in range(1, protocol.retry_budget + 2):
        started = time.monotonic()
        transcript_path = out_dir / f"attempt-{attempt}.json"
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=protocol.timeout_s,
                env=env,
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
        if payload is None:
            last_error = "output non JSON (crash o stderr)"
            failure_kind = "errore_init_tool_shape"
            continue

        answer, tool_results, stop_reason = _extract_payload(payload)
        if stop_reason == "error" or (answer == "" and not tool_results):
            last_error = f"risposta vuota (attempt {attempt})"
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
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_payload(payload: dict) -> tuple[str, list[str], str | None]:
    """Extract (final_text, tool_result_texts, stop_reason) from the CLI JSON.

    The CLI emits either a single result object or a message stream; both
    shapes are handled here so the executor stays data-driven.
    """
    if payload.get("type") == "result":
        text = payload.get("result") or ""
        return str(text), [], payload.get("subtype")

    messages = payload.get("messages") or (
        [payload] if payload.get("type") in ("assistant", "user", "system") else []
    )
    answer_parts: list[str] = []
    tool_results: list[str] = []
    stop_reason: str | None = None
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("type") == "result":
            stop_reason = message.get("subtype")
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
    return "\n".join(answer_parts).strip(), tool_results, stop_reason
