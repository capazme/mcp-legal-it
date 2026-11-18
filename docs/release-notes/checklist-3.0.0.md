# Pre-release checklist: 3.0.0

Tick each box with the evidence (a command output, a link, a date). A box
that cannot be ticked stops the release; it is not skipped.

State last checked on 17 November 2026, on `develop` at `353325a`. Sections 1
and 5 updated on 18 November 2026 with decision LI-086, on `develop` at
`e109b44`.

## 1. Decisions to close first

These need the project owner. Each one either changes code before the GA or
is shipped as it is today, stated as such in the release notes. None may be
«completed» by whoever runs the release.

- [x] Merge order and approval of the 3.0 chain (§2): merged in order on
      2026-10-21 (#55-#62), then the migration PRs (§2).
- [x] The last 2.x release: decided (G-493), 2.17.2 is the last 2.x release
      and the next one is 3.0. Published on 2026-11-18 (§5).
- [ ] An upgrade notice for 2.x users. LI-045 planned one last 2.x release,
      right after the GA, telling users to move to 3.0; 2.17.2 carries no such
      notice, and LI-086 keeps 2.17.2 as the last release. Plugin users with
      auto-update move to 3.0 anyway; `.mcpb` users would not be told. Asked
      on 2026-11-18: a 2.17.3 on `support/2.x` with the notice, or none.
- [x] Start of the art. 482 c.p.c. window: decided (G-329, G-407), first day
      = notice + 11, no extension, no August suspension.
- [x] A «substantive» mode of `scadenza_processuale` without the Saturday
      extension: decided (LI-086), not in 3.0, planned for 3.1 and stated in
      the release notes. The drafted code stays on
      `feature/termini-decisioni-pendenti`.
- [x] Art. 617 c.p.c. and the August suspension: decided (LI-060), excluded;
      `termini_esecuzioni` states the reading and the case law in a note.
- [x] Registration tax: whether the text of D.P.R. 131/1986 is still
      applicable or D.Lgs. 123/2025 replaces it (decided, LI-061: D.P.R.
      131/1986 until 31/12/2026).
- [x] `rendimento_btp` on the 50-year BTP (simple yield above the MEF gross):
      decided (LI-059), yield to maturity gross and net as the MEF; live gate green.
- [x] How long the 2.x line keeps receiving fixes after 3.0: decided
      (LI-086), security fixes only, for three months after the GA, then the
      line closes. 2.17.2 stays the last planned release.
- [x] Review of twelve content items: non-pecuniary damage tables (Milan vs
      TUN), art. 139 Codice delle assicurazioni in work accidents, order of the
      briefs under art. 171-ter c.p.c., 2012 text of art. 348-bis c.p.c.,
      mediation duration, naming of the «sommario» procedure, abrogated abuse
      of office, some CONSOB identifiers, the labour consultant as independent
      controller, Cass. SS.UU. 19499/2008, Cass. SS.UU. 1712/1995, Italgiure
      archive coverage if listed. Decided (LI-086): they ship as they are and
      the release notes list them «in revisione».
- [x] Where the 2.x line lives after the GA: decided (LI-086), on
      `support/2.x`, created from `v2.17.2` before the GA merges 3.0 into
      `main` (§6).
- [x] `main → develop`: until #55 the 2.x and 3.x lines were kept divergent
      on purpose and `main` was never merged into `develop`. Since #55 develop
      descends from `v2.17.0`, and that PR's stated intent is that 2.x hotfixes
      merge forward. 2.17.1 (released, tag `v2.17.1` on `main`) is not an
      ancestor of `develop`: its fixes reached the 3.0 line as separate
      commits. Decided (LI-086): `main` is never merged into `develop`; a fix
      on `support/2.x` reaches the 3.x line as its own commit.
- [x] Relicensing: written consent to MPL-2.0 obtained from every past
      contributor. `NOTICE` still says that the 2.x releases remain available
      under Apache-2.0.
- [x] Sigle of the fiscal testi unici (G-440 follow-up). Since the fiscal reform's
      new testi unici, «TUS», «TUIVA» and «T.U. registro» name more than one act
      and are refused as ambiguous («nome ambiguo»); which act each sigla
      resolves to, if any, is not decided. Decided (LI-086) and merged in #191:
      the sigla follows the date. Before the new testo unico applies
      (1/1/2027 for TUIR, TU IVA and TU registro, checked on Normattiva) it
      gives the old act with a warning naming the new one; from that date,
      the new act. «TUA» is refused as ambiguous (codice dell'ambiente or
      testo unico accise).
- [x] Regional laws (G-444, LI-076): decided (LI-086) and merged in #191, a
      declared limit. A regional law answers «fonte non coperta» and is never
      read as a State law; the citation gate warns on every regional law
      cited; no regional Normattiva URN is built. Real coverage comes later,
      on the regions branch. The laws of the autonomous provinces get the
      same guard in a follow-up PR.
- [x] Codice deontologico forense (CNF): decided (LI-086), 7 April 2026, the
      date on the CNF's page, which the parser already reads (the PDF's notes
      to art. 25-bis say 6 April).
- [x] Art. 645 co. 3 c.p.c. in the `opposizione_decreto_ingiuntivo` model
      (G-493): the provision refers to «l'anticipazione di cui all'articolo
      163-bis, secondo comma», and Normattiva gives that comma as repealed by
      D.Lgs. 149/2022. Decided (LI-086) and merged in #191: the quote stays
      verbatim, followed by a sentence saying that comma is shown as
      repealed.
- [x] Act models: renames, merged keys and a filter: decided (LI-086), in
      3.1, with aliases for the old keys. 3.0 ships the catalogue as it is,
      with the content fixes already made.

## 2. The 3.0 chain is merged

- [x] In order: #55 → #56 → #57 → #59 → #58 → #60 → #61 → #62, all merged on
      2026-10-21; the release material #63 (2026-10-21); the VisuaLex
      migration: Normattiva text channel #64, AKN #65, act tree and index #67,
      vigenza #72 and #88, EUR-Lex #74, #87, #94, #95, citations/URN #93; the
      decisions are in the library API of #59 (`api._decisioni`).
- [x] The integration conflicts (`CHANGELOG.md` / `plugin/CHANGELOG.md`) were
      resolved when the chain was merged; nothing is left to integrate.
- [ ] `docs/migration/2.x-to-3.0.md` and `docs/release-notes/3.0.0.md` updated
      with what the migration PRs and the later fixes changed (§8), and with the
      outcome of every decision in §1 (or left «in attesa di decisione»).
- [x] Counts are true everywhere: 233 tools by default, with Brocardi off
      (LI-079), and 235 with `LEGAL_BROCARDI=on`; 30 skills, 9 slash commands,
      6 agents, 23 prompts, 15 resources. Checked on 2026-11-17 after LI-079:
      `release.py` `count_tools()` 233 (the default surface, so the manifests
      keep it); the server's `list_tools` 233 by default and 235 with
      `LEGAL_BROCARDI=on`; `content/tool-vocabulary.json` 235 (every registered
      tool); `content/` 30 skills,
      9 commands, 6 agents; `plugin.json`, `marketplace.json`, README and the
      pages agree (`plugin/README.md` said 23 skills in English: fixed). The
      OpenAI bundle's 42 skills (28 + 6 agents + 8 commands) and the 2.x
      count of 228 tools in the migration guide are right.

## 3. Gates

Run long jobs under `caffeinate -dims`: a sleeping Mac stalls the live suites.

- [ ] Full non-live suite: `pytest tests/ -m "not live"`, green in CI on
      Python 3.11 and 3.12 × FastMCP 3 and 4.
- [x] `python scripts/audit_tool_annotations.py --check`: up to date
      (2026-11-17, `353325a`).
- [x] `python scripts/check_deps_sync.py`: OK, the three launchers match
      `pyproject.toml` (2026-11-17).
- [x] `python scripts/check_directory_readiness.py`: OK, only the two accepted
      holds (`uv-run-frozen`, `subfolder-program`), 257 files (2026-11-17).
- [ ] `python scripts/build_targets.py all` twice: no diff the second time.
- [x] `pip-audit` on the root environment and on `plugin/server/uv.lock`:
      clean. The lock exported with `uv export --frozen` and audited on
      2026-11-17: no known vulnerabilities; both CI jobs green on #182.
- [ ] Replay: `scripts/replay_mcp_outputs.py compare --base <previous tip>`:
      only the differences each PR declared.
- [ ] **Live gate, act numbers**:
      `pytest tests/unit/test_atti_denominati_live.py -m live -q` green
      (Normattiva date and number for every named act, CELLAR for every CELEX).
- [ ] **Live gate, Brocardi**:
      `pytest tests/unit/test_brocardi_codici_live.py -m live -q` green (every
      table URL answers; every source of brocardi.it/fonti.html is mapped).
- [ ] Every other live module, one at a time (`ls tests/unit/*_live.py`),
      including the CeRDEF canary and `test_italgiure_live.py` with TLS
      verification on. Red gates are either fixed or listed in §1 (the BTP
      50-year yield, LI-059, was fixed in #147; the D.M. 55/2014 gate is no
      longer red).
- [ ] The citation gate on a real session: a reply citing an article not read
      is stopped once with «ATTENZIONE — gate citazioni»; after `cite_law` it
      passes; «fuori copertura» passes; a subagent's read counts.

## 4. Fresh installs

On a clean user account (no `~/.cache/uv`, no `~/.claude/plugins`), with the
release candidate:

| | Mac (Apple silicon) | Mac (Intel) | Windows 11 |
|---|---|---|---|
| Plugin from the marketplace, following the published guide step by step | [ ] | [ ] | [ ] |
| `/mcp` connected on a fresh install, nothing set; 233 tools; `stato_server` says 3.0.0 and `brocardi.stato` `spento_per_default` | [ ] | [ ] | [ ] |
| `LEGAL_BROCARDI=on claude` (Windows: `$env:LEGAL_BROCARDI="on"; claude`): 235 tools, `cerca_brocardi` answers, `stato_server` says `acceso` | [ ] | [ ] | [ ] |
| `LEGAL_BROCARDI=off claude`: 233 tools, `stato_server` says `spento_esplicito` | [ ] | [ ] | [ ] |
| `"LEGAL_BROCARDI": "on"` in the `env` block of `~/.claude/settings.json`, app's Code tab (not started from a terminal): `stato_server` says `acceso`. The mechanism was verified on 2026-10-21 (Mac, Claude Code CLI, temporary HOME: a plugin MCP server received `off` with the block and an empty value without it); this row checks it end to end in the app | [ ] | [ ] | [ ] |
| `.mcpb` in Claude Desktop: installs, tools answer, first start rebuilds once | [ ] | [ ] | [ ] |
| `uvx --from git+https://github.com/capazme/mcp-legal-it@v3.0.0 mcp-legal-it --version` | [ ] | [ ] | [ ] |
| Docker (`docker build .`, `docker run -p 8000:8000`), 233 tools on `/mcp` (235 with `-e LEGAL_BROCARDI=on`) | [ ] | — | — |
| A generated DOCX lands in the private temp folder (0700 on Mac) | [ ] | [ ] | [ ] |
| Time to `initialize`, cold / warm (2.x reference: plugin 1.8 s / 0.6 s) | | | |

The Mac Intel column checks the `cryptography` platform split of the lock.

## 5. Update path from 2.x

The marketplace is git-sourced from `main` on GitHub: when `main` moves to 3.0,
every 2.x plugin user with auto-update receives it.

- [x] 2.17.2, the last 2.x release (G-493), is published before the GA, so
      the update path starts from it: tag `v2.17.2` on `main` (`55025e3`),
      released on 2026-11-18 with the `.mcpb`, the plugin zip and the skills
      zip.
- [x] #176 (cookie-audit, a 2.x fix open against `main`): closed on
      2026-11-18 with the reason (LI-086: 2.x takes security fixes only); the
      same fix is in 3.0 through #175.
- [ ] On a machine with 2.17.2 installed from the marketplace:
      `claude plugin marketplace update mcp-legal-it`, then
      `claude plugin update legal-it@mcp-legal-it`, restart. The first start
      syncs the new lock in the background (two-phase start) and the tools
      appear; `stato_server` says 3.0.0.
- [ ] The same with auto-update on, without typing anything.
- [ ] The hooks are the new ones: `Stop` and `SubagentStop` in the installed
      `hooks/hooks.json`.
- [ ] A 2.17.2 `.mcpb` replaced by the 3.0.0 one keeps working after the
      one-time uv rebuild.
- [ ] A 3.0.0-beta user (pre-release artifacts) moves to the GA the same way.
- [ ] `marketplace.json` and `plugin.json` on `main` say 3.0.0 after the
      release.

## 6. Cutting the GA with `release.py`

The beta channel's GA procedure, checked against what the script does today.

- [ ] Working tree clean, on `develop`, in sync with `origin/develop`.
- [ ] `release/3.0.0` carries 3.0.0-beta.4 (cut on 2026-11-03), which is not
      in develop: `git merge-base --is-ancestor origin/release/3.0.0
      origin/develop` fails on 2026-11-17. The two commits that develop lacks
      only bump the versions to `3.0.0-beta.4` (`cea6ae17`) and add its
      changelog heading (`95f2e41f`); develop already carries `3.0.0` and one
      `[Unreleased]` section. Merge `release/3.0.0` into `develop` (`--no-ff`)
      keeping develop's content (`3.0.0` in `pyproject.toml`, `plugin.json`,
      `marketplace.json`, the manifests and the lock; no beta.4 heading), check
      the ancestry again, and push that merge to `origin/develop` before
      running the script (`check_remote_sync`).
- [ ] Delete `release/3.0.0` **locally and on origin**: the standard flow
      creates a branch with the same name.
- [ ] Create `support/2.x` from `v2.17.2` and push it (LI-086), before `main`
      moves to 3.0. It takes security fixes only, for three months after the
      GA.
- [ ] `CHANGELOG.md`: rename `## [Unreleased]` to `## [3.0.0] - <date>`. The
      section is already the release section: the 2.x entries are in their own
      sections, not repeated. `plugin/CHANGELOG.md` is not a copy of the root
      one: replace its `[Unreleased]` with the same section and point the
      migration-guide link at `../docs/migration/2.x-to-3.0.md`. Commit through
      a branch and PR as usual, and answer **n** to `release.py`'s «Scrivere il
      CHANGELOG?»: it would prepend a second section built from commit subjects.
- [ ] Run the suite yourself first. If the worktree has its own `.venv`
      without pytest, `release.py` picks it and the test step fails: then pass
      `--skip-tests` after a green run of your own.
- [ ] Hide the `claude` CLI from `PATH` while the script runs (otherwise
      `update_marketplace` runs `claude plugin marketplace add <checkout>` and
      reinstalls the plugin from the local folder over the GitHub-sourced one).
- [ ] Dry run: `python3 release.py 3.0.0 --from-develop --plugin-version 3.0.0 --dry-run`.
      Expected, and not a reason to stop: «pyproject.toml (3.0.0) non allineato
      con ultimo tag» (`check_version_sync`) and «3.0.0 non è maggiore di
      3.0.0» (`check_version_gt`), because develop already carries 3.0.0. Both
      are warnings: the script proceeds.
- [ ] Real run: `python3 release.py 3.0.0 --from-develop --plugin-version 3.0.0`.
      The explicit `--plugin-version` is required: without it the patch
      auto-bump writes 3.0.1 and `verify_all_versions` fails mid-flow.
- [ ] Answer **n** to «Scrivere il CHANGELOG?».
- [ ] Decline the script's push. `main` is owner-only (GitHub ruleset): the
      owner pushes
      `git push origin main develop` and `git push origin refs/tags/v3.0.0`
      (one tag, never `--tags`).
- [ ] `release.yml` on the tag: green; the release has the `.mcpb`, the plugin
      zip, the OpenAI bundle and the web-skills zip, and is marked *latest*
      (not pre-release).
- [ ] Replace the auto-generated release body with
      `docs/release-notes/3.0.0.md`, without its opening draft note (the
      blockquote); its links are absolute, so they work in the release page.

## 7. Anthropic directory submission

- [ ] `check_directory_readiness.py` OK on the released tag, two accepted holds
      only.
- [ ] Plugin pre-submission checklist re-read
      (claude.com/docs/plugins/pre-submission-checklist) against the tag.
- [ ] `plugin.json`: version 3.0.0, `license: MPL-2.0`, description with true
      counts, homepage and repository URLs.
- [ ] The privacy notice URL submitted is the published 3.0 `privacy.html`
      (§8 done first).
- [ ] Submitted; the expected outcome is a HOLD for a reviewer on the two
      accepted points. Record the submission date and the answer.

## 8. Pages and announcements

- [ ] Copy `docs/release-notes/pages/index.html` and `privacy.html` over the
      files on `gh-pages` (owner), date filled in on the privacy page; check
      both pages on a phone and in dark mode.
- [ ] README links the migration guide and states MPL-2.0 (the «Senza
      Brocardi» section is already there).
- [ ] Open issues touched by 3.0 answered with the release link.
- [ ] Monthly data-freshness cron (`data-freshness.yml`) still opens its PRs
      against the right branch after the GA.
- [ ] `docs/release-notes/3.0.0.md` and the pages updated with the November work:
      deferred entries into force (#173, #179, #180), the legge Basevi cited as
      a d.lgs. (#181), the act-model warnings (#182, G-493), the codice
      deontologico forense from the CNF (#158, #159), the act names and types of
      G-440 (#160-#167).
