# v3 — Harness-agnostic content layer — Design

- **Date**: 2026-08-24
- **Branch**: `feature/harness-agnostic-layer` (from `develop`)
- **Status**: Design approved by the user (2026-08-24), pending implementation plan
- **Target version**: `3.0.0`
- **Scope**: introduces a capability manifest (`targets.yaml`) and a single
  builder (`scripts/build_targets.py`) that projects one content corpus onto
  several agent harnesses. Consolidates the existing corpus (skills, MCP
  prompts, MCP resources, agents, slash commands), relocates the citation gate
  into the MCP server, and adds an OpenAI target (Codex CLI + ChatGPT).
  The 218 tools and their signatures are **unchanged**.

## Problem

Every non-tool asset in this project is written in a Claude-specific format,
and several of them are written twice. The project has never had a content
model separate from its packaging. Four consequences, all measured on
2026-08-24:

1. **16 workflows exist twice.** `analisi_sinistro`, `recupero_credito`,
   `causa_civile`, `pianificazione_successione`, `parere_legale`,
   `quantificazione_danni`, `calcolo_parcella`, `verifica_prescrizione`,
   `ricerca_normativa`, `analisi_articolo`, `confronto_norme`,
   `mappatura_normativa`, `analisi_giurisprudenziale`,
   `analisi_delibere_consob`, `novita_consob` and `compliance_privacy` are each
   written once in `src/prompts.py` and once in `plugin/skills/<name>/SKILL.md`.
   Diffed on `analisi_sinistro`: the two bodies carry the same doctrine, the
   same SS.UU. warnings and the same output table, differing only in tool
   naming (`danno_non_patrimoniale` vs `legal-it:danno_non_patrimoniale`) and
   in the prompt's typed parameters. A correction applied to one leaves the
   other stale, and nothing detects the divergence.

2. **7 workflows are trapped in `prompts.py`.** `analisi_tributaria`,
   `analisi_giurisprudenza_amministrativa`, `analisi_giurisprudenza_europea`,
   `analisi_costituzionale`, `ricerca_gazzetta`,
   `orientamento_giurisprudenziale` and `attuazione_direttiva` exist only as
   MCP prompts. MCP prompts must be invoked by hand, so in practice these are
   unreachable — the model never selects them the way it selects a skill.

3. **15 `legal://` resources are read-only for Claude.** They are never reused
   by the skills that would need them, and no other harness can see them at all.

4. **Tool names are hardcoded across 37 markdown files.** `legal-it:cite_law`
   is repeated verbatim in every skill, agent and command. Renaming the server,
   or supporting a harness that namespaces tools differently, is a corpus-wide
   find-and-replace with no verification.

Separately, five build paths (`scripts/build-all.sh`, `build-plugin.sh`,
`build-dxt.sh`, `plugin/build-web-skills.py`, `install.py`) each package a
subset of the same corpus with their own rules, orchestrated by `release.py`.

## Goals

1. One source of truth per workflow. Every packaged artifact is a projection.
2. Adding a harness is a manifest entry, not a code branch.
3. The citation gate works on every harness, not only where hooks exist.
4. Codex CLI and ChatGPT get a first-class, documented bundle.
5. No capability regression on Claude — including the MCP prompt surface.

## Non-goals

- Rewriting the 218 tools or changing any tool signature.
- Inventing a new content format. `SKILL.md` already **is** the neutral format
  (OpenAI documents it as the open agent skills standard); we adopt it rather
  than layer another abstraction on top.
- Running a public multi-tenant MCP endpoint (see Distribution).
- Supporting harnesses beyond Claude and OpenAI in this version. The manifest
  makes them cheap later; it does not deliver them now.

## Decisions taken with the user (2026-08-24)

| # | Decision | Chosen |
|---|----------|--------|
| 1 | Target harnesses | Codex CLI **and** ChatGPT |
| 2 | Audience | Public distribution |
| 3 | Approach | Adapter over the existing corpus, not a rewrite |
| 4 | Framing | This is `v3.0.0`, the agnostic version |
| 5 | Sequencing | Debt first, then the OpenAI target |
| 6 | Citation gate | In the MCP server **and** the Claude hook (defence in depth) |
| 7 | ChatGPT exposure | Documented self-hosting only — no public endpoint operated by us |

Decision 5 was taken against the recommendation on record: it is the sequence
that delays the Codex release the most, and the user's stated context was
"release a working Codex version now, I'm gaining traction". The user chose it
knowingly. The design compensates by requiring Phase 1 to be shaped by the
agnostic target rather than by Claude's convenience, so no work is done twice.

## Current inventory (measured 2026-08-24, v2.12.1)

| Asset | Count | Location |
|---|---|---|
| MCP tools | 218 | `src/tools/` (32 modules) |
| Skills | 23 | `plugin/skills/*/SKILL.md` |
| Skills with bundled files | 4 | `cookie-audit`, `esporta-documento`, `analisi-fornitori`, `procure-quotazioni` |
| MCP prompts | 23 | `src/prompts.py` |
| MCP resources | 15 | `src/resources.py` (`legal://riferimenti/*`) |
| Agents | 6 | `plugin/agents/*.md` |
| Slash commands | 8 | `plugin/commands/*.md` |
| Hooks | 1 | `plugin/hooks/citation-gate.py` (Stop) |

Overlap: 16 prompts have a same-named skill, 7 prompts do not, 7 skills have no
prompt. Note: `.claude-plugin/marketplace.json` advertises "22 skill" against
23 on disk — an existing drift to fix in Phase 1.

## Architecture

```
SOURCE (single corpus)
  content/skills/<name>/SKILL.md      workflow body + frontmatter
                        references/   shared reference material
                        scripts/      executable helpers
                        assets/       templates
                    │
                    ▼
  targets.yaml        capability manifest: per harness, what it supports
                      and how it names things
                    │
                    ▼
  scripts/build_targets.py
                    │
    ├──▶ dist/claude/    plugin/ tree: skills, agents, commands, hooks
    ├──▶ dist/openai/    .agents/skills/, AGENTS.md, config.toml, openai.yaml
    ├──▶ src/prompts.py  GENERATED MCP prompts (clients that support them)
    └──▶ dist/mcpb/      desktop extension (existing dxt path)
```

### The source format

`SKILL.md` stays as-is: YAML frontmatter plus a markdown body. Two additions,
both optional and both ignored by harnesses that do not care:

- **`tools:`** — the workflow declares the tool names it uses in *bare* form
  (`cite_law`, not `legal-it:cite_law`). The builder rewrites them per target.
  This removes the hardcoded namespace from all 37 files.
- **`prompt:`** — when present, declares typed parameters (name, type,
  description). Its presence is what makes the builder also emit an MCP prompt
  for that workflow. Workflows without it (interactive ones like `cookie-audit`)
  simply produce no prompt.

The deduplication is therefore achieved by **generation, not deletion**: the
MCP prompt surface keeps its current names and parameters, so plain MCP clients
lose nothing, and Codex ignores prompts harmlessly.

### `targets.yaml` — the capability manifest

This is the abstract layer the project is being restructured around. It
declares, per harness: which capabilities exist (MCP prompts, MCP resources,
hooks, subagents, slash commands), how tools are namespaced, which frontmatter
fields survive, output directories, and per-artifact size limits.

```yaml
targets:
  claude-code:
    tool_namespace: "legal-it:{tool}"
    supports: [skills, mcp_prompts, mcp_resources, hooks, subagents, commands]
    frontmatter: [name, description, argument-hint, model, allowed-tools]
    out: dist/claude/
  codex-cli:
    tool_namespace: "{server}:{tool}"     # TO VERIFY — see Open questions
    supports: [skills]
    frontmatter: [name, description]
    skills_dir: .agents/skills
    out: dist/openai/
  chatgpt:
    tool_namespace: "{tool}"
    supports: [skills]
    frontmatter: [name, description]
    out: dist/openai/
```

Adding Gemini CLI, Cursor or Manus later is a block in this file. The builder
never learns a harness's name.

### `scripts/build_targets.py`

Absorbs `build-web-skills.py`, `build-plugin.sh`, `build-dxt.sh` and
`build-all.sh` into one entry point with a target argument. `release.py` calls
it instead of orchestrating five scripts. The transformations it performs:
frontmatter filtering, description truncation (already implemented for Claude
web), tool-name rewriting, reference resolution, and prompt generation.

## Phase 1 — Corpus consolidation

Outcome: one corpus, every workflow with exactly one home.

1. Move `plugin/skills/` to `content/skills/`. `plugin/` becomes build
   output — but **stays committed**: `.claude-plugin/marketplace.json`
   declares `source: "./plugin"`, so the marketplace installs from the
   tree in git, not from a build artifact. Generated-and-committed, with
   `release.py` responsible for regenerating it before every tag.
2. For the 16 duplicated workflows: keep the skill body, add a `prompt:` block
   carrying the prompt's current parameter list, delete the hand-written prompt
   function. Verify the generated prompt is semantically equivalent to the one
   it replaces.
3. For the 7 orphan prompts: write a `SKILL.md` for each, deriving the body
   from the existing prompt text and adding a trigger `description`. These
   become invocable on Claude too — closing an existing gap, not only serving
   OpenAI.
4. Extract the 15 `legal://` resources into `content/references/`. `resources.py`
   reads them from there; skills that need them reference them by path.
   One text, two consumers.
5. Replace hardcoded `legal-it:` prefixes with bare tool names plus a `tools:`
   declaration, across all 37 markdown files.
6. Fix the 22-vs-23 skill count in `marketplace.json` and every other place the
   counts are asserted (`README.md`, `CLAUDE.md`, plugin description).

## Phase 2 — Agnostic layer

Outcome: Claude is a generated target, not the native format.

1. Write `targets.yaml` with the `claude-code` target only.
2. Write `build_targets.py`.
3. **Regression gate**: regenerating the `claude-code` target must reproduce
   the current `plugin/` tree. An empty diff proves Phase 1 lost nothing. This
   gate is free and stronger than any hand-written test; it is the acceptance
   criterion for the whole phase.
4. Add an `mcpb` target for the desktop extension, absorbing
   `build-dxt.sh`. It is a repackaging of the `claude-code` output, so it
   declares no capabilities of its own.
5. Point `release.py` at the single builder; retire the four legacy scripts.

## Phase 3 — OpenAI target

Outcome: a downloadable bundle for Codex CLI and ChatGPT.

1. Add the `codex-cli` and `chatgpt` blocks to `targets.yaml`.
2. Emit `dist/openai/.agents/skills/<name>/` for all workflows.
3. Emit `AGENTS.md` carrying the operating rules that Claude gets from
   `CLAUDE.md` plus the hook: legal grounding protocol, output formats,
   the citation rule.
4. Emit a `config.toml` snippet:
   ```toml
   [mcp_servers.legal_it]
   command = "uv"
   args = ["run", "--python", "3.12", "...", "run_server.py"]
   ```
5. Map the 6 agents to role-skills (invocable as `$civilista`), with an
   optional `~/.agents/` variant for users who enable `multi_agent`.
6. Map the 8 slash commands to skills — Codex deprecated custom prompts in
   favour of skills, so this is the forward-compatible target.
7. Emit `agents/openai.yaml` per skill for ChatGPT display metadata.
8. Write the install documentation for both surfaces.

## Citation gate relocation

Today `citation-gate.py` runs as a Claude `Stop` hook. It lives there because
that was the only place available, not because it is the right place. In an
agnostic project the right place is the MCP server, where it applies to every
client by construction.

- **New floor (all harnesses)**: tools that emit legal prose —
  `genera_modello_atto`, the `genera_*` privacy family, `esporta_atto_docx` —
  run their citations through `verifica_citazioni` and append the outcome to
  their own output. The check becomes part of the data, not of client behaviour.
- **Extra layer (Claude only)**: the existing Stop hook stays. It catches
  citations written without going through any tool, which the server-side floor
  structurally cannot see.

Per decision 6, both are kept. The README must state plainly that OpenAI
harnesses get the floor and not the second layer.

## Harness capability matrix

Verified 2026-08-24 from OpenAI documentation; the Claude Desktop column is
partly inferred and must be confirmed before Phase 3 ships.

| Capability | Claude Code | Claude Desktop | Codex CLI | ChatGPT |
|---|---|---|---|---|
| MCP tools | yes | yes | yes | yes |
| MCP prompts | yes | yes | **no** | **no** |
| MCP resources | yes | yes | **no** | **no** |
| Skills | yes | yes | yes | yes (via plugin) |
| Slash commands | yes | no | deprecated | no |
| Subagents | yes | no | behind `multi_agent` | no |
| Hooks | yes | no | **no** | **no** |

Two notes with operational consequences:

- Codex has been reported to use `resources/list` when deciding whether a
  server is available, so a tools-only server can be shown as unavailable while
  connected. Our server exposes resources, so this works in our favour — but it
  means we must **not** stop serving resources as an optimisation.
- The skills list is budgeted at most 2% of the context window, or 8000
  characters when unknown. With 30 workflows the `description` fields must stay
  short; the builder should fail the build when the projected list exceeds the
  budget rather than silently truncating.

## Distribution

Per decision 7, we operate no public MCP endpoint.

- **Codex CLI**: users install the skills bundle into `.agents/skills` (repo)
  or `$HOME/.agents/skills` (user) and add the stdio server to
  `~/.codex/config.toml`. Same local-process model as Claude Code today,
  no hosting, no auth.
- **ChatGPT**: documented self-hosting. The user deploys the server behind
  their own HTTPS endpoint (the existing Docker path) and registers it as a
  custom connector in Developer Mode. We publish the procedure and the caveats;
  we do not run the endpoint.

This removes the abuse question entirely: nobody can burn our IP against
Normattiva, Italgiure or CeRDEF, because there is no shared address to burn. It
raises the barrier for non-technical ChatGPT users, which is the accepted
trade-off.

## Testing

| Gate | What it proves | Phase |
|---|---|---|
| Empty diff on `claude-code` regeneration | Consolidation lost nothing | 2 |
| Generated prompt equivalence (16 workflows) | Prompt surface preserved | 1 |
| Skills-list budget check in the builder | No silent truncation | 2 |
| Empirical tool-naming probe on real Codex | Skill bodies name tools correctly | 3 |
| `test_atti_denominati_live.py` (marker `live`) | Act resolution unbroken | pre-release |
| Existing unit suite, `-m "not live"` | No tool regression | every phase |

## Open questions — to verify empirically, not from memory

1. **Codex tool naming.** Documentation and issue tracker indicate `<server>:<tool>`
   since v0.121 with `-` normalised to `_` in qualified names, which would make
   ours `legal_it:cite_law`. This must be measured against a running Codex
   before the skill bodies are written — a wrong prefix silently breaks every
   workflow. First task of Phase 3.
2. **Claude Desktop capability column.** Confirm skills and prompt support in
   the current Desktop build before publishing the matrix.
3. **`agents/openai.yaml` schema.** Confirm the exact fields before emitting.

## Implementation planning

The three phases are sequential and each is large enough to stand alone.
They get **one implementation plan each**, written when the previous phase
has passed its gate — not one plan for the whole of v3. Phase 2's empty-diff
gate in particular is a hard stop: Phase 3 does not start until
regeneration reproduces the current plugin tree.

## Out of scope (explicit)

- Any change to the 218 tool signatures or output formats.
- OAuth for a hosted endpoint.
- Gemini CLI, Cursor, Manus targets.
- The `benchmarks/` work, which remains blocked on its own pending decisions.
