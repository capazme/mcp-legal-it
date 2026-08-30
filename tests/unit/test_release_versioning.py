"""Unit tests for release.py prerelease-aware version helpers (beta channel).

Covers BETA_RE, version_key() and the prerelease-tolerant bump_part(), plus a
guard that SEMVER_RE keeps rejecting prerelease strings (stable flows must
stay strict). See docs/specs/2026-08-26-beta-release-channel-plan.md (T6).
"""

import importlib.util
import inspect
import re
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "release_versioning", Path(__file__).parents[2] / "release.py"
)
rel = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rel)


# ---------------------------------------------------------------------------
# BETA_RE
# ---------------------------------------------------------------------------

class TestBetaRe:
    @pytest.mark.parametrize("version", ["3.0.0-beta.1", "3.0.0-beta.12"])
    def test_accepts_valid_beta(self, version):
        assert rel.BETA_RE.match(version), f"BETA_RE should accept '{version}'"

    @pytest.mark.parametrize(
        "version",
        [
            "3.0.0-beta.0",
            "3.0.0-rc.1",
            "3.0.0beta1",
            "3.0.0-beta",
            "3.0.0",
        ],
    )
    def test_rejects_invalid_beta(self, version):
        assert not rel.BETA_RE.match(version), f"BETA_RE should reject '{version}'"


# ---------------------------------------------------------------------------
# version_key — single ordering authority
# ---------------------------------------------------------------------------

class TestVersionKey:
    def test_ordering_stable_and_betas(self):
        versions = ["2.12.1", "3.0.0-beta.1", "3.0.0-beta.2", "3.0.0"]
        keys = [rel.version_key(v) for v in versions]
        assert keys == sorted(keys), (
            "2.12.1 < 3.0.0-beta.1 < 3.0.0-beta.2 < 3.0.0 must hold via version_key()"
        )
        # Strict, pairwise — sorted() alone would not catch a stable dupe key.
        assert keys[0] < keys[1] < keys[2] < keys[3]

    def test_stable_key_shape(self):
        assert rel.version_key("2.12.1") == (2, 12, 1, 1, 0)

    def test_beta_key_shape(self):
        assert rel.version_key("3.0.0-beta.5") == (3, 0, 0, 0, 5)

    def test_equality_on_identical_strings(self):
        assert rel.version_key("3.0.0-beta.1") == rel.version_key("3.0.0-beta.1")
        assert rel.version_key("2.12.1") == rel.version_key("2.12.1")

    @pytest.mark.parametrize(
        "garbage",
        ["not-a-version", "3.0", "3.0.0-alpha.1", "3.0.0-beta.0", "", "3.0.0.0"],
    )
    def test_raises_value_error_on_garbage(self, garbage):
        with pytest.raises(ValueError):
            rel.version_key(garbage)


# ---------------------------------------------------------------------------
# bump_part — prerelease-tolerant
# ---------------------------------------------------------------------------

class TestBumpPart:
    def test_bump_patch_from_beta_base(self):
        assert rel.bump_part("3.0.0-beta.5", "patch") == "3.0.1"

    def test_bump_minor_from_beta_base(self):
        assert rel.bump_part("3.0.0-beta.5", "minor") == "3.1.0"

    def test_bump_major_from_beta_base(self):
        assert rel.bump_part("3.0.0-beta.5", "major") == "4.0.0"

    def test_bump_never_reintroduces_beta_suffix(self):
        bumped = rel.bump_part("3.0.0-beta.5", "patch")
        assert "-beta" not in bumped

    def test_stable_base_unchanged_behavior(self):
        assert rel.bump_part("2.12.1", "patch") == "2.12.2"
        assert rel.bump_part("2.12.1", "minor") == "2.13.0"
        assert rel.bump_part("2.12.1", "major") == "3.0.0"


# ---------------------------------------------------------------------------
# SEMVER_RE — stable flows must keep rejecting prereleases
# ---------------------------------------------------------------------------

class TestSemverStillStrict:
    @pytest.mark.parametrize(
        "version", ["3.0.0-beta.1", "3.0.0-rc.1", "3.0.0+build.1"]
    )
    def test_rejects_prerelease_strings(self, version):
        assert not rel.SEMVER_RE.match(version), (
            f"SEMVER_RE must keep rejecting prerelease strings, got a match for '{version}'"
        )

    def test_accepts_plain_semver(self):
        assert rel.SEMVER_RE.match("3.0.0")


# ---------------------------------------------------------------------------
# run_beta safety invariant
# ---------------------------------------------------------------------------

class TestRunBetaSafetyInvariant:
    """The one property of the beta channel that must never regress: a beta
    cut cannot touch main, merge anything, delete remote refs or run the
    local marketplace update. Driving the full flow would need the
    interactive harness, so the invariant is guarded on the source of
    run_beta itself (see the beta-channel plan review, finding #6)."""

    def test_git_subcommands_are_allowlisted(self):
        src = inspect.getsource(rel.run_beta)
        used = set(re.findall(r'run_git\(\s*"([a-z-]+)"', src))
        allowed = {"checkout", "branch", "add", "commit", "tag", "push", "rev-parse", "reset"}
        assert used <= allowed, (
            f"run_beta usa subcomandi git fuori allowlist: {sorted(used - allowed)}"
        )

    def test_never_names_forbidden_operations(self):
        src = inspect.getsource(rel.run_beta)
        assert '"merge"' not in src, "run_beta non deve mai fare merge"
        assert '"--delete"' not in src, "run_beta non deve mai cancellare ref remoti"
        assert '"main"' not in src, "run_beta non deve mai passare 'main' a git"
        assert "update_marketplace" not in src, "run_beta non deve toccare il marketplace locale"
        assert "verify_marketplace" not in src, "run_beta non deve toccare il marketplace locale"
