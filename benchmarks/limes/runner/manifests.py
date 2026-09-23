"""Config manifests (DESIGN §3): YAML declarations, interpreted — never
branched on — by the runner.

Fail-closed: a manifest that does not satisfy the schema raises at load
time. Placeholders (`${VAR}`) in the MCP template or in env-declared paths
are resolved from the environment at run preparation time; an unresolved
placeholder aborts the run before any model call.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - dev dependency guard
    raise ModuleNotFoundError(
        "pyyaml is required to load LIMES manifests "
        "(install the project dev extras: uv sync --extra dev)"
    ) from exc

SURFACES = ("bare", "system-prompt", "mcp", "plugin", "rag", "agent")
SYSTEM_PROMPT_MODES = ("default", "bench")
_PLACEHOLDER = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


class ManifestError(ValueError):
    """Raised when a config manifest does not satisfy the schema."""


@dataclass(frozen=True)
class Manifest:
    id: str
    surface: str
    model: str
    max_turns: int
    system_prompt: str            # "default" | "bench" (parity knob)
    scratch_config_dir: bool
    profile: str | None
    ref: str | None               # pinned ref of the enhancement, if any
    mcp_template: Path | None
    source: Path

    def resolve_mcp_config(self, env: dict[str, str] | None = None) -> dict:
        """Render the MCP template, resolving `${VAR}` from `env`.

        Fail-closed: a missing variable, or a template with no
        `mcpServers` mapping, raises before any model call.
        """
        if self.mcp_template is None:
            raise ManifestError(f"{self.id}: not an mcp surface")
        environ = dict(env) if env is not None else dict(__import__("os").environ)
        raw = self.mcp_template.read_text(encoding="utf-8")

        def _sub(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in environ:
                raise ManifestError(
                    f"{self.mcp_template.name}: placeholder ${{{name}}} is not "
                    f"set in the environment (fail-closed)"
                )
            return environ[name]

        rendered = _PLACEHOLDER.sub(_sub, raw)
        data = json.loads(rendered)
        servers = data.get("mcpServers")
        if not isinstance(servers, dict) or not servers:
            raise ManifestError(
                f"{self.mcp_template.name}: missing 'mcpServers' mapping"
            )
        return data


def _git(*args: str) -> str | None:
    """Run a git query; None outside a repository (callers decide)."""
    try:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip()


def _manifest_sha(source: Path) -> str:
    """Identity of the manifest file: git blob sha when committed, else a
    content hash prefixed `content:` (untracked manifests are usable, but
    their identity must not pretend to be a commit)."""
    blob = _git("rev-parse", f"HEAD:{source.as_posix()}")
    if blob:
        return blob
    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    return f"content:{digest}"


def load_manifest(path: Path) -> Manifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ManifestError(f"{path}: expected a mapping")

    manifest_id = str(raw.get("id") or "").strip()
    if not manifest_id:
        raise ManifestError(f"{path}: missing 'id'")
    surface = str(raw.get("surface") or "")
    if surface not in SURFACES:
        raise ManifestError(
            f"{path}: surface must be one of {SURFACES}, got {surface!r}"
        )
    ref = raw.get("ref")
    if surface not in ("bare",) and not ref:
        raise ManifestError(
            f"{path}: surface {surface!r} requires a pinned 'ref' "
            f"(the variant_sha lesson: never run an unpinned enhancement)"
        )

    isolation = raw.get("isolation") or {}
    if not isinstance(isolation, dict):
        raise ManifestError(f"{path}: 'isolation' must be a mapping")
    parity = raw.get("parity") or {}
    if not isinstance(parity, dict):
        raise ManifestError(f"{path}: 'parity' must be a mapping")
    max_turns = parity.get("max_turns")
    if not isinstance(max_turns, int) or max_turns <= 0:
        raise ManifestError(f"{path}: parity.max_turns must be a positive integer")
    system_prompt = str(parity.get("system_prompt", "default"))
    if system_prompt not in SYSTEM_PROMPT_MODES:
        raise ManifestError(
            f"{path}: parity.system_prompt must be one of {SYSTEM_PROMPT_MODES}"
        )

    mcp_template: Path | None = None
    mcp = raw.get("mcp") or {}
    if surface == "mcp":
        template = mcp.get("server_template") if isinstance(mcp, dict) else None
        if not template:
            raise ManifestError(f"{path}: mcp surface requires mcp.server_template")
        # Resolve against the manifest's own directory, whatever directory
        # the manifest is loaded from (shipped configs or a tmp copy).
        mcp_template = (path.parent / template).resolve()
        if not mcp_template.is_file():
            raise ManifestError(f"{path}: mcp template not found: {template}")

    return Manifest(
        id=manifest_id,
        surface=surface,
        model=str(raw.get("model", "any")),
        max_turns=max_turns,
        system_prompt=system_prompt,
        scratch_config_dir=bool(isolation.get("scratch_config_dir", True)),
        profile=str(isolation["profile"]) if isolation.get("profile") else None,
        ref=str(ref) if ref else None,
        mcp_template=mcp_template,
        source=path.resolve(),
    )


def config_sha(manifest: Manifest) -> str:
    """`config_sha` (DESIGN §2): the manifest's content identity."""
    return _manifest_sha(manifest.source)
