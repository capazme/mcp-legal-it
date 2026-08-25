"""Load and validate content/targets.yaml — the capability manifest."""
from __future__ import annotations

from pathlib import Path

import yaml

_REQUIRED_PROJECTION_KEYS = {"tool_namespace", "strip_frontmatter_keys", "out"}


def load_targets(root: Path) -> dict:
    data = yaml.safe_load((root / "content" / "targets.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("targets.yaml: unsupported or missing version")
    for name, cfg in (data.get("projections") or {}).items():
        missing = _REQUIRED_PROJECTION_KEYS - set(cfg)
        if missing:
            raise ValueError(f"targets.yaml projection {name!r}: missing {sorted(missing)} (tool_namespace, strip_frontmatter_keys, out are required)")
    return data


def get_target(root: Path, name: str) -> dict:
    data = load_targets(root)
    for section in ("projections", "packaging"):
        if name in (data.get(section) or {}):
            return data[section][name]
    raise KeyError(name)
