"""Load and validate content/targets.yaml — the capability manifest."""
from __future__ import annotations

from pathlib import Path

import yaml

_REQUIRED_PROJECTION_KEYS = {"tool_namespace", "strip_frontmatter_keys", "out"}

# Filesystem kinds a projection can emit natively — each one present in
# `supports` demands a matching key in `out`. `mcp_resources` additionally
# demands `references` (the resource copy is keyed differently from the
# supports vocabulary). `mcp_prompts` and `hooks` are not filesystem
# projections done by this module (prompts.py generation / static hooks
# tree) and demand no `out` key at all.
_FS_KINDS = {"skills", "agents", "commands"}


def load_targets(root: Path) -> dict:
    data = yaml.safe_load((root / "content" / "targets.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("targets.yaml: unsupported or missing version")
    for name, cfg in (data.get("projections") or {}).items():
        missing = _REQUIRED_PROJECTION_KEYS - set(cfg)
        if missing:
            raise ValueError(f"targets.yaml projection {name!r}: missing {sorted(missing)} (tool_namespace, strip_frontmatter_keys, out are required)")
        supports = cfg.get("supports")
        if supports is None:
            continue  # absent supports = full claude behavior (backward compatible)
        needed = _FS_KINDS & set(supports)
        if "mcp_resources" in supports:
            needed = needed | {"references"}
        out_keys = set(cfg.get("out") or {})
        missing_out = sorted(needed - out_keys)
        if missing_out:
            raise ValueError(
                f"targets.yaml projection {name!r}: supports {sorted(supports)} "
                f"requires an 'out' key for {missing_out} — missing"
            )
    return data


def get_target(root: Path, name: str) -> dict:
    data = load_targets(root)
    for section in ("projections", "packaging"):
        if name in (data.get(section) or {}):
            return data[section][name]
    raise KeyError(name)
