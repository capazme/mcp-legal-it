# Beta Release Channel — Implementation Plan (2026-08-26)

## Context

v3.0.0 will ship as a **beta line** before GA. Convention (user-approved):

- Tags `vX.Y.Z-beta.N` (strict: only `beta`, N ≥ 1), published as **GitHub
  Pre-releases** so `releases/latest` keeps serving the 2.x stable line.
- Long-lived branch `release/X.Y.Z` created from `develop`; beta tags are cut
  **on that branch**; `main` stays untouched on 2.x for the whole beta period.
- GA path (manual, documented): merge `release/X.Y.Z` back into `develop`,
  delete the branch, run the standard `--from-develop` flow with `X.Y.Z`.
- Beta testers install from the Pre-release artifacts (`.mcpb`, plugin zip,
  openai zip — CI already stamps the beta version into them) or
  `git checkout vX.Y.Z-beta.N`. No marketplace beta channel (marketplace
  tracks `main` → stays 2.x).

Recon findings this plan is built on (file:line refs verified 2026-08-26):

- `release.py:44` `SEMVER_RE = ^\d+\.\d+\.\d+$` rejects prereleases in all
  modes (`check_semver` at :560-564; called at :1079, :1264, :1410, and the
  interactive prompts :886-888, :949-951).
- `bump_part` (:206-215) and `check_version_gt` (:567-574, duplicated inline
  at :1413-1414) do `int(x) for x in v.split('.')` → uncaught ValueError on
  `-beta` components.
- No mode tags without touching `main`: `--from-develop` requires branch
  `develop` (:1077) and merges/tags on main (:1164-1185); `--tag-only`
  requires `main` (:1262); `--plugin-only` never tags.
- `_push_release` (:1023-1048) runs `git push origin --tags` (:1039) — pushes
  ALL local tags (cross-contamination risk with mixed 2.x/3.x tags).
- `print_summary` (:1565) prints wrong repo owner `github.com/gpuzio/...`.
- `.github/workflows/release.yml:3-6` fires on any `v*` tag; the
  `softprops/action-gh-release@v2` step (:40-46) sets **no `prerelease:` and
  no `make_latest:`** → a beta tag would hijack `releases/latest`.
- `ci.yml:3-10` and `security-audit.yml:9-16` never run on `release/**`
  branches.
- All 6 version manifests + artifact name templates accept a `-beta.N`
  string verbatim (no numeric parsing downstream); `verify_all_versions`
  compares byte-wise → safe.

## Non-goals

- No `--finalize` GA mode (GA uses the existing `--from-develop` after the
  manual merge-back; documented instead).
- No marketplace beta channel, no changes on `main`, no interactive-mode
  wiring for beta (CLI flag only).
- No fix for the pre-existing rollback gaps of stable flows (out of scope).

## Tasks

### T1 — Prerelease-aware version helpers (release.py)

1. Next to `SEMVER_RE` add:
   `BETA_RE = re.compile(r"^\d+\.\d+\.\d+-beta\.[1-9]\d*$")`.
2. Add pure helper `version_key(version: str) -> tuple[int, int, int, int, int]`:
   parses `X.Y.Z` or `X.Y.Z-beta.N` → `(X, Y, Z, is_final, beta_n)` with
   `is_final=1, beta_n=0` for stable, `is_final=0, beta_n=N` for beta.
   Raises `ValueError` with a clear message on any other shape. This is the
   single ordering authority: stable > its own betas; betas ordered by N.
3. Rewrite `check_version_gt` to compare `version_key(new) > version_key(current)`;
   keep the existing fatal message style. Replace the duplicated inline
   int-tuple compare in `run_plugin_only` (:1413-1414) with the same helper.
4. Make `bump_part` prerelease-tolerant: strip a `-beta.N` suffix before
   parsing (bumping from a beta base bumps the underlying `X.Y.Z`); one
   comment line documenting the semantics.
5. `check_semver` stays strict (stable flows must keep rejecting betas) but
   its fatal message gains the hint: `per una beta: release.py X.Y.Z-beta.N --beta`.

### T2 — Single-tag push in ALL flows (release.py)

1. `_push_release`: replace `git push origin --tags` (:1039) with
   `git push origin <tag>` — thread the tag name through (it is known at both
   call sites). Same replacement in `run_tag_only`'s push path.
2. Update the manual-push hint strings in `print_summary` (`--tags` →
   the specific `v{version}`).
3. Fix `github.com/gpuzio/` → `github.com/capazme/` (:1565).

### T3 — `run_beta` flow (release.py)

CLI: add `--beta` to the existing mutually-exclusive mode group; add an
epilog example `python3 release.py 3.0.0-beta.1 --beta --dry-run`. If
`--plugin-version` or `--no-plugin-bump` is combined with `--beta`, fatal
("non supportati in --beta: il plugin segue la versione server in lockstep").

`run_beta(version, ...)` mirrors the structure/style of `run_from_develop`
(step/success/fatal helpers, section banners, RollbackContext):

1. `check_clean_tree()`.
2. Version must match `BETA_RE`, else fatal showing the expected format.
3. `base = version.split("-")[0]`; `release_branch = f"release/{base}"`.
4. Branch logic: current branch == `release_branch` → proceed; current ==
   `develop` → create `release_branch` from develop (first beta; register
   rollback: checkout develop + delete branch); anything else → fatal
   ("una beta si taglia da develop o da release/X.Y.Z").
5. Remote sync, tolerant: new helper `check_remote_sync_if_exists(branch)` —
   if `git rev-parse --verify origin/<branch>` fails, `warn(...)` and skip
   (origin/develop may not exist yet); otherwise same semantics as
   `check_remote_sync`.
6. `check_version_gt(version, <pyproject current>)`.
7. `check_tag_not_exists(f"v{version}")`.
8. Tests (same gate as from-develop) unless `--skip-tests`.
9. Bumps: `write_pyproject_version(version)`; `write_plugin_version(version)`
   (lockstep); `bump_extra_manifests(version, count_tools())`. Register the
   pyproject/plugin restores on the rollback stack as from-develop does.
10. CHANGELOG: `generate_changelog_entry(version, git_latest_tag())` + same
    write prompt as the stable flow (nearest tag is the previous beta — or
    v2.12.x for beta.1 — which is exactly the right changelog base).
11. `verify_all_versions(version)`.
12. Commit on `release_branch`: `chore(release): v{version}`.
13. `git tag -a v{version}` on the release branch (register tag delete).
14. Push (via `ask_yes_no`, honoring `--push` / `--non-interactive` defaults):
    `git push -u origin {release_branch}` then `git push origin v{version}`.
    Disarm rollback after the branch push (same rationale as `_push_release`).
    **Never** touches main/develop, **no** marketplace update, **no** remote
    branch deletion.
15. `print_summary` with mode `beta`; the not-pushed hint prints the two
    exact push commands above.

### T4 — Pre-release flag in CI (.github/workflows/release.yml)

In the `softprops/action-gh-release@v2` step add:

```yaml
          prerelease: ${{ contains(github.ref_name, '-') }}
          make_latest: ${{ contains(github.ref_name, '-') && 'false' || 'true' }}
```

(`make_latest` explicit so a prerelease can never take `releases/latest`.)

### T5 — CI coverage for release branches

- `ci.yml`: add `"release/**"` to both `push.branches` and
  `pull_request.branches`.
- `security-audit.yml`: add `"release/**"` to `push.branches` and
  `pull_request.branches`.

### T6 — Unit tests (new file `tests/unit/test_release_versioning.py`)

Import `release.py` from the repo root via `importlib.util.spec_from_file_location`
(root is not a package; verify import is side-effect-free — the module must
only define things until `if __name__ == "__main__"`). Cover at minimum:

- `BETA_RE`: accepts `3.0.0-beta.1`, `3.0.0-beta.12`; rejects `3.0.0-beta.0`,
  `3.0.0-rc.1`, `3.0.0beta1`, `3.0.0-beta`, `3.0.0`.
- `version_key` ordering: `2.12.1 < 3.0.0-beta.1 < 3.0.0-beta.2 < 3.0.0`;
  equality on identical strings; ValueError on garbage.
- `bump_part` on a beta base: `bump_part("3.0.0-beta.5", "patch") == "3.0.1"`
  (and stable bases unchanged behavior).
- `SEMVER_RE` still rejects prerelease strings.

### T7 — Docs

- `README.md`: new short subsection «Canale beta» near the install section:
  the convention table (stable = `releases/latest` e marketplace, beta = tag
  `vX.Y.Z-beta.N` marcati Pre-release), how to try a beta (download the
  pre-release artifacts by exact version / `git checkout vX.Y.Z-beta.N`),
  explicit note that marketplace and `releases/latest` keep serving the
  stable line.
- `CLAUDE.md` (repo): in the Git Flow / Versioning section: beta lifecycle
  (long-lived `release/X.Y.Z` from develop; beta tags cut there via
  `release.py X.Y.Z-beta.N --beta`; main untouched; GA = merge-back into
  develop → delete branch → standard `--from-develop X.Y.Z`), and the
  single-tag push change.

## Constraints

- **Never execute release.py flows** — not even `--dry-run`. Only
  `uv run --python 3.12 --extra dev python release.py --help` to verify
  argparse wiring. Behavior is verified through the unit tests of the pure
  helpers only.
- Match existing release.py style: Italian user-facing strings, `step`/
  `success`/`warn`/`fatal` helpers, section banner comments.
- Full suite must stay green:
  `uv run --python 3.12 --extra dev pytest tests/ -m "not live" -q`.
- Do NOT commit; report a diff summary and test counts.
- Work only inside the worktree
  `/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it/.claude/worktrees/mcp-legal-it-freebuff-53b316`
  on branch `feature/beta-release-channel`. Do not touch the main checkout.

## Deviations

(recorded during implementation)

- **T2 scope widened slightly to inline dry-run/decline-push hint strings.**
  The plan's T2.2 only mentions updating `print_summary`'s manual-push hints,
  but `run_from_develop`/`run_tag_only` also print `git push origin --tags`
  in their own dry-run branch and in the "push declined" branch (separate
  from `print_summary`). Leaving those as `--tags` after T2's `_push_release`
  change would have shipped a functional inconsistency — the very
  cross-contamination bug T2 exists to close — inside the same PR. Updated
  those four `info(...)` strings to the specific tag too. Low-impact, same
  intent as T2, no new behavior.
- **`run_beta` does not reuse `_push_release`.** The shared helper always
  does a plain `git push origin <branches>` (no `-u`) and unconditionally
  tries `git push origin --delete <release_branch>` when a release_branch is
  passed — both wrong for beta (needs `-u` for a possibly-new branch, must
  never delete the long-lived release branch). Push logic for `--beta` is
  inlined in `run_beta`, following the same disarm-after-first-push
  rationale documented on `_push_release`, rather than extending the shared
  helper's signature for a one-off case.
- **`run_beta` does not call `build_web_skills()`.** T3 step 9 ("Bumps")
  lists only `write_pyproject_version`, `write_plugin_version`,
  `bump_extra_manifests` — unlike `run_from_develop`'s plugin-bump branch,
  which also rebuilds the Claude Web skills ZIP. The plan's own context notes
  CI already builds the `.mcpb`/plugin-zip/openai bundles from the tag; the
  Web-skills ZIP is a separate manual-upload artifact not mentioned as part
  of the beta artifact set, so it was left out to match the literal task
  list.
- **`check_version_gt`/`run_plugin_only`'s inline compare wrap `version_key`
  ValueError in `fatal()`.** Not explicitly specified by T1.3, but both
  values passed in are always pre-validated by `check_semver`/`BETA_RE`
  upstream in every real call path, so the `fatal()` branch is a defensive
  fallback, not a new user-facing behavior change.

## Review outcome (2026-08-26)

Independent review verdict: FIX FIRST — 2 blockers, both fixed:

1. **run_beta rollback deadlock (MAJOR)**: the file restores ran before the
   `checkout develop` in LIFO order, so after the release commit the dirty
   tree aborted the checkout and the branch delete never ran (reviewer
   reproduced empirically). Fixed with `checkout -f develop` in the
   branch-delete rollback plus a `reset --hard <head_before>` registered
   right after the release commit, which also covers the beta.N>1 case
   (where no branch delete exists and the restores alone would leave a
   dirty tree blocking the next run's `check_clean_tree`).
2. **GA path aborted mid-flow (MAJOR, docs)**: the documented
   `release.py X.Y.Z --from-develop` auto-bumps the plugin patch from the
   beta base (→ X.Y.(Z+1) ≠ X.Y.Z) and `verify_all_versions` fatals AFTER
   the local merge on main. CLAUDE.md now mandates
   `--plugin-version X.Y.Z` and deleting the beta branch locally AND
   remotely before the GA run (same-name recreation clash).

Also addressed from the review: module docstring/usage + positional help
updated for `--beta` (#3); run_beta docstring no longer claims
marketplace.json is untouched (#4); `check_remote_sync`/`_if_exists`
deduplicated via `_compare_with_remote` (#5); run_beta safety invariant now
guarded by source-level tests (git subcommand allowlist + forbidden-ops
scan) in `test_release_versioning.py` (#6); `run_plugin_only` fatals when
`plugin.json` holds a beta version — the plugin follows the server in
lockstep during a beta line (#7); CLAUDE.md branch table notes the
long-lived semantics of `release/X.Y.Z` during a beta (#8).

Waived as cosmetic/low-risk: `print_summary` column overflow past
`-beta.9` (#9); the three version regexes encode the same grammar — drift
between `BETA_RE` and `_VERSION_KEY_RE` is already caught by the paired
accept/reject unit tests (#10).
