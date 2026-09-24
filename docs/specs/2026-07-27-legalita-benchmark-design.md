# LegalITA replica benchmark — mcp-legal-it vs bare Claude — Design

- **Date**: 2026-07-27
- **Branch**: `feature/legalita-benchmark` (from `develop`)
- **Status**: Draft (design), pending user approval
- **Scope**: A methodological replica of the LegalITA v2 benchmark
  (Aptus.AI Research, July 2026) run on our own task set. Measures the effect of
  exposing `mcp-legal-it` to Claude. Does **not** reproduce Aptus numbers and
  does not evaluate any third-party system.

## Problem

The LegalITA white paper (Aptus.AI, July 2026) evaluates eleven systems on
Italian law across three deliberately separate capabilities. Its published
results contain a striking dissociation for general-purpose models:

| Track | Claude Opus 4.8 (direct API) | Next-OS (Aptus legal-tech) |
|---|---:|---:|
| Legal reasoning (all-pass) | 79.1% — 2nd of 11, ahead of every legal-tech competitor | 85.1% |
| Grounding (GOG / Coverage) | **1.2% / 3.0%** | **30.2% / 80.6%** |
| Missing Document Detection | 50.0% | 85.0% |

A frontier model reasons about Italian law better than three commercial
legal-tech products, yet produces an issue-covering citation in 3% of tasks.
GPT-5.5 scores 0.0% grounding: in 62 of 67 answers it refers to Cassazione case
law narratively ("consolidated case law", "the Court has repeatedly held")
without court, branch, number or year, so nothing is verifiable.

The entire gap between a frontier model and a specialised legal product is
**grounding**, not substantive legal reasoning. That is precisely the gap
`mcp-legal-it` exists to close: `cerca_giurisprudenza`, `leggi_sentenza`,
`giurisprudenza_su_norma` and `cite_law` query the real Italgiure and Normattiva
corpora. The paper's source corpus is 17,076 Cassazione decisions deposited
between 7 January and 30 May 2025; our Italgiure archive covers 2020 onward, so
the relevant authorities are reachable.

**The benchmark cannot be run as published.** Aptus does not release the 107
tasks: no HuggingFace repository, no GitHub, no download link, no licence. The
methodology, however, is specified in enough detail to rebuild.

## Goal & success criteria

Answer one falsifiable question: **does exposing `mcp-legal-it` move Claude's
jurisprudential grounding, and at what cost to the other two capabilities?**

The design commits in advance to the expected shape of the result, so that
failure is recognisable:

1. **Grounding rises sharply in the MCP arm.** This is the central hypothesis.
   If GOG and Coverage do not rise, the experiment has failed and the README
   will say so.
2. **Reasoning stays roughly flat across arms.** Bare Claude already scores
   ~79% all-pass in the published table; tools are not expected to add much.
   A large rise would be suspicious and would warrant checking for leakage.
3. **MDD is directionally uncertain.** Search tools could make the model more
   cautious (it can verify the document is absent) or more reckless (it finds
   something adjacent and answers anyway). Either outcome is informative; we
   do not predict one.

## Non-goals

- Reproducing or contesting Aptus's published numbers.
- Evaluating Next-OS or any competitor. We cannot run them.
- Producing a single composite score. The paper's §4.1 argues against it and we
  agree: the three capabilities dissociate, and averaging hides the profiles.

## 1. Metrics

Implemented with the paper's exact formulas (eq. 1-9), reported separately.

| Track | Definition | Tasks |
|---|---|---:|
| **Legal reasoning** | `Rᵢ = Πⱼ∈Qᵢ pᵢⱼ` — a task passes only if every required criterion passes. `AllPass = (1/N)ΣRᵢ`; `CriterionRate = ΣΣpᵢⱼ / Σ|Qᵢ|`. Bonus criteria reported separately as `BonusRate`, never affecting pass/fail. | 30 |
| **Grounding** | `GOGᵢ = |Gᵢ|/|Cᵢ|` if `|Cᵢ|>0` else 0, where `Cᵢ` are extracted citations and `Gᵢ ⊆ Cᵢ` those covering the task's legal issue. `GOG = (1/N)ΣGOGᵢ` (unweighted task mean). `Coverageᵢ = 1[|Gᵢ|>0]`. | 30 |
| **MDD** | Single criterion C-001 with three conjunctive requirements. `Global MDD = (1/M)Σxₖ`. | 20 |

Domain split proportional to the paper (29/18/20 of 67): **13 civil, 8 labour,
9 tax**.

Task-level averaging in GOG is deliberate: it prevents a system that emits many
citations in a few answers from dominating the global score.

## 2. Gold set construction

Five steps, following the paper's §3.2.

1. **Sampling.** Italgiure Solr, `anno:[2025 TO 2025]`, client-side filter on
   `datdep` to the 7 Jan – 30 May 2025 window (the field is year-granular in
   `build_search_params`, so the day window is applied after retrieval).
   Enumeration ordered by deposit date, then **fixed-seed random draw**,
   stratified by `materia`.
2. **Generation.** A builder model reads the massima and the principle of law
   and emits: a standalone professional query, required criteria, issue status,
   and the seed citation.
3. **Issue-status annotation** (paper §3.3), which governs how citations are
   validated later: `settled` (a consolidated orientation resolves the issue),
   `revirement` (an earlier orientation was replaced; the current post-change
   orientation must be identified), `active_conflict` (incompatible orientations
   remain live; a citation must support one of them).
4. **Targeted human curation.** Tasks where the builder self-reports low
   confidence on issue status, where criteria are ambiguous, or where the two
   judges later disagree, are exported for review by the user. Estimated 8-12
   tasks of 30.
5. **Isolation.** The system under test receives **only** the final standalone
   query — never the source decision, the principle, the criteria, the issue
   status or the seed citation.

MDD tasks (20) are authored directly: prompts asking for analysis of contracts,
notices, judgments, pleadings or administrative acts described as attached and
never supplied.

### 2.1 Contamination risk and mitigation

The seed decisions are drawn from Italgiure and the MCP arm queries Italgiure.
If decisions were selected *by relevance search*, we would implicitly pick the
ones Italgiure surfaces well, and the MCP arm would win by selection artefact.

Two defences:

- **Sampling is by enumeration, never by relevance.** No semantic query
  participates in selection. A fixed seed makes the draw reproducible.
- **Grounding is open-set**, as in the paper's §4.6: the seed citation is a
  *seed*, not a whitelist. Any authentic authority that covers the issue earns
  credit. The MCP arm gets no points merely for recovering the seed.

This is mitigated, not eliminated, and is declared in §7.

## 3. Execution: three arms

All arms run through `claude -p` (Claude Code headless, subscription-backed),
because the alternative — a custom agent loop over a paid API — was ruled out on
cost. The confound this normally introduces (Claude Code's own system prompt) is
removed by `--system-prompt`, which **replaces** rather than appends to the
default.

| Arm | Tool access |
|---|---|
| `bare` | none |
| `web` | `WebSearch`, `WebFetch` |
| `mcp` | `mcp__legal-it__*` only |

Identical across all three arms: model, system prompt, task query, turn cap,
working directory. Tool availability is the only variable.

**System under test**: Claude Opus 5, pinned via `--model` and recorded with its
resolved model id in every result record. **Task builder**: Claude Opus 5 as
well, via `claude -p` (the paper used Claude Sonnet 4.6 for the same role).
Builder and subject sharing a model is a real concern — the builder may phrase
queries in ways the subject finds congenial — and is declared in §7.

Isolation harness per invocation:

- `--system-prompt` with one shared legal-expert prompt (no arm-specific wording)
- `--strict-mcp-config`, plus `--mcp-config` only for the `mcp` arm
- `--settings '{}'` to neutralise inherited project settings
- clean temporary working directory containing no `CLAUDE.md`
- `--allowedTools` per the table, `--disallowedTools` for everything else
- `--output-format json` to capture answer, tool calls and usage
- `--max-turns` cap, recorded per run

The `mcp` arm runs with **`LEGAL_PROFILE=normativa`**, not `full`. Serving 216
tool schemas on every call costs tens of thousands of tokens of schemas alone,
and the fee calculators are irrelevant to a jurisprudential query. The
`normativa` profile exposes exactly the relevant surface: normativa,
giurisprudenza ordinaria/amministrativa/UE, CONSOB, privacy. This is also the
configuration a real user would choose. Declared in §7.

Residual limitations of this approach, accepted: no temperature control, and no
straightforward path to a non-Claude arm later.

## 4. Judge panel

Adaptive majority, adapted to the subscription constraint.

- **Judge A** — Claude Sonnet, via `claude -p`
- **Judge B** — Claude Opus, via `claude -p`, with a distinct evaluation prompt
- **Tiebreak** — **human**, not a third model

Both judges emit binary verdicts with mandatory per-criterion reasoning. Where
they agree, the verdict is final. Where they disagree, the criterion goes to the
user's audit queue. Criteria that remain unresolvable after human review are
reported as `unresolved` — explicitly, never silently converted to failures.

Judges are **blind to the arm**: answers are presented unlabelled and in
randomised order, so a judge cannot favour the citation-dense arm on form.

### 4.1 Grouped judging

Criteria are judged **grouped by response** — one call returns a verdict for
every criterion of one answer — rather than one call per criterion as in the
paper. This is a deliberate deviation, taken to cut the panel from ~1,500 calls
to ~480 and remove the risk of exhausting subscription limits mid-run.

Volume, recomputed from the paper's own manifest (137 criteria over 67 tasks,
mean 2.0 per task — an earlier estimate of 4 was wrong):

| Stage | Calls per judge |
|---|---:|
| Reasoning (30 responses × 3 arms) | 90 |
| MDD (20 tasks × 3 arms, 1 criterion each) | 60 |
| Grounding validation (30 responses × 3 arms) | 90 |
| **Per judge** | **240** |
| **Both judges** | **480** |

Plus ~150 generation runs. Total ≈ 630 `claude -p` invocations.

The cost of grouping is the halo effect: a judge that has just failed three
criteria tends to fail the fourth. Mitigated by presenting criteria in
randomised order and requiring separate written justification for each.

### 4.2 Human audit

The user reviews roughly 60 verdicts, in two strata:

- **All A/B disagreements**, capped at 40 by random subsample if more arise.
  Expected 6-10% of ~490 criterion-level verdicts per judge (162 reasoning,
  60 MDD, ~270 citation validations), so 30-50 before capping.
- **20 randomly sampled agreements.** Two same-provider judges can agree and
  both be wrong; sampling the agreed set is what makes the error estimate
  meaningful.

Estimated 45 minutes. This audit serves double duty — it resolves ties *and*
yields a measured judge error rate, which is reported. Cohen's κ between A and B
is computed and reported, with the explicit caveat that same-provider judges
have correlated errors and the figure is therefore inflated relative to the
paper's cross-provider 0.836.

This makes the scoring pipeline a **two-phase run with a human gate**: judge,
export the audit queue, wait, then finalise scores.

## 5. Grounding pipeline

Four stages, the most delicate part of the design.

```
answer → citation extraction → resolution → legal validation → Gᵢ
```

- **Extraction.** Deterministic regex for canonical forms
  (`Cass. civ., sez. II, n. 12345/2025`) plus an LLM pass for narrative forms.
  Critically, it must also count citations that carry **no identifying
  elements** — these are produced citations that cannot be resolved, and
  omitting them would flatter exactly the failure mode the paper found in
  GPT-5.5.
- **Resolution.** `verifica_citazioni()`, which already checks existence and
  metadata coherence against the live sources. Applied **identically to all
  three arms**. When the bare arm hallucinates, the resolver detects it — that
  is the point of the measurement, not a bias against the arm.
- **Legal validation.** Does the resolved authority support *this* issue, in the
  role its issue status requires (§2 step 3)? Judged by the panel.
- **Fail-closed aggregation.** A citation enters `Gᵢ` only when both its
  identity and its legal role are confirmed. Ambiguous, `needs_review` and
  unresolved citations do not contribute. Authentic authorities addressing
  adjacent points receive no grounding credit and are **not** recorded as
  fabricated — they are simply outside the task's scoring scope.

## 6. Code structure

In the `mcp-legal-it` repository, following the precedent of
`benchmarks/akn_vs_html.py`.

```
benchmarks/legalita/
├── README.md              # method, how to re-run, declared limits
├── corpus/sample.py       # Cassazione sampling, fixed seed
├── build/tasks.py         # task + criteria generation
├── build/review.py        # export for targeted human curation
├── run/arms.py            # claude -p harness: bare | web | mcp
├── score/reasoning.py     # eq. 1-4
├── score/grounding.py     # eq. 6-9, citation pipeline
├── score/mdd.py           # eq. 5
├── score/judges.py        # A/B panel, human tiebreak queue, κ
├── data/                  # gold tasks, versioned in git
└── results/               # runs + markdown report
```

Runs are checkpointed and resumable: a subscription-backed run of 630
invocations may need to span sessions.

Like `akn_vs_html.py`, this is a **manual benchmark tool, not a test suite**. It
hits live Normattiva and Italgiure and must never run in CI.

## 7. Declared limitations

Written into `benchmarks/legalita/README.md`, not buried:

1. **This is not LegalITA v2.** It is a methodological replica on our own tasks.
   The numbers are **not comparable** to the Aptus table. No claim of the form
   "we beat Next-OS" is admissible.
2. **30 + 20 tasks** against the paper's 67 + 40. The paper concedes its own
   size does not establish statistical significance for small ranking
   differences. We report bootstrap confidence intervals per track.
3. **Home ground.** The corpus is Cassazione and `mcp-legal-it` queries
   Cassazione. The result supports "the MCP helps ground on Court of Cassation
   case law", not "the MCP helps always".
4. **Different model** from any row in the published table — our bare arm is a
   newer model than Opus 4.8, so cross-reading the two is not legitimate.
5. **Targeted curation, not full.** Declared as such.
6. **Same-provider judge panel.** κ is inflated relative to a cross-provider
   panel; the human audit is what backs the verdicts.
6b. **Closed loop on one model family.** Builder, subject and both judges are
   Claude. The paper has the same weakness in part (its Judge A, Sonnet 4.6, is
   also an evaluated system), but ours is total. The human audit is the only
   external check, and the design leans on it accordingly. Note that the
   *comparison* is unaffected — all three arms share the same builder and
   judges, so the bias is a constant, not a differential.
7. **Grouped criterion judging** deviates from the paper's independent
   per-criterion protocol (§4.1).
8. **Reduced MCP profile** (`normativa`, not `full`) — §3.
9. **Temporal scope** inherited from the paper: Cassazione, January–May 2025.

## References

Grandi, J. and Molla, A. (2026). *LegalITA: A Benchmark for Legal Reasoning,
Jurisprudential Grounding, and Safe Abstention in Italian Law*. Aptus.AI
Research, July 2026, V1.
