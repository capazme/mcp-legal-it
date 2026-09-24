# LegalITA replica benchmark — pre-release methodological review

- **Date**: 2026-08-16
- **Reviews**: [`docs/specs/2026-07-27-legalita-benchmark-design.md`](2026-07-27-legalita-benchmark-design.md)
  as built (see `benchmarks/legalita/`)
- **Evidence base**: [`docs/specs/2026-08-16-legalita-literature-survey.md`](2026-08-16-legalita-literature-survey.md)
- **Status**: decided and implemented — kept as the audit record. See the
  addendum below for the owner's decisions and the resulting amendments.

## Addendum — post-review outcome (2026-08-16)

The owner reviewed this document and decided, on its three highest-stakes
questions: (1) **accents restored** in every benchmark-facing Italian string
before any run existed; (2) **repeats**: the targeted stability subset
(10 tasks x bare+mcp x 3 repeats, resolution-stability only); (3) **judges
stay Claude-only** with the strengthened, arm-stratified human audit in
exchange. The low-risk rigor package was approved in full.

The AMEND-BEFORE-RELEASE items below were then implemented on this branch as
amendments A1-A5 plus the final-review fix wave: accent restoration and
accent-tolerant narrative markers (A1), arm-stratified 30-item audit
agreement sampling with per-kind error rates (A4), exact paired McNemar
comparisons and a grounding-pass kappa with fail-closed n/d rendering (A2),
the stability repeat subset (A3), the human leakage spot-check round trip
(A5), and the never-measured-renders-as-null guarantees (audit error rate,
zero-survivor CIs) with per-arm N columns. The remaining declarations were
folded into `benchmarks/legalita/README.md`'s limitations list. The verdicts
in the body below are therefore the PRE-amendment state, preserved as the
audit trail.

## How to read this document

This is a pre-release audit, not a literature essay. For each of ten
methodological dimensions it states four things in the same order:

1. **What we do** — the design as actually implemented.
2. **What the literature says** — the relevant published finding, cited by
   short name and arXiv id.
3. **Verdict** — one of four:
   - **SOUND** — no change needed.
   - **SOUND-WITH-DECLARATION** — the design is defensible, but the README
     must say so out loud. These feed the Task 13 checklist at the end.
   - **AMEND-BEFORE-RELEASE** — I would not ship without changing something.
   - **OPEN-QUESTION** — the literature has no answer; we must say that
     rather than pretend otherwise.
4. **Options** — where an amendment is on the table, with effort and
   trade-off, so you can choose.

A short glossary, because several of these terms are ML jargon:

| Term | Plain meaning |
|---|---|
| **arm** | One experimental condition. We have three: `bare`, `web`, `mcp`. |
| **judge** | A model asked to grade another model's answer against a criterion. |
| **κ (Cohen's kappa)** | Agreement between two graders, corrected for the agreement you would get by pure chance. 1.0 = perfect, 0 = chance-level. |
| **paired test** | A statistical test that compares two arms *on the same tasks*, which is far more sensitive than comparing two independent averages. |
| **power** | The probability that a real difference of a given size will show up as statistically significant. Low power = real effects go undetected. |
| **contamination** | The evaluated model having already seen the test material during its training. |
| **construct validity** | Whether the number you compute actually measures the thing you named it after. |
| **GOG** | Grounding On the legal Issue: of the case-law citations an answer produces, the fraction that are both real and actually on point. |
| **MDD** | Missing Document Detection: does the model refuse to analyse a document that was never attached? |

---

## Executive summary

The design is unusually careful for a solo project. The isolation harness in
`run/arms.py`, the fail-closed resolution vocabulary in `score/resolve.py`,
and the refusal to let any automated stage guess a verdict are all stronger
than what most published benchmarks do. The three-state grounding pipeline
(grounded / unresolved-no-credit / off-issue-no-credit-not-fabricated) has no
direct precedent in the literature and is, in my reading, the most publishable
thing here.

The weaknesses are concentrated in three places, and two of them are cheap to
fix:

- **No paired statistical test.** `score/metrics.py` computes per-arm
  bootstrap confidence intervals but nothing that compares arms on the same
  tasks. This is the single largest gap against BetterBench (arXiv:2411.12990)
  and Card et al. (EMNLP 2020), and it is roughly half a day of pure-function
  code.
- **The grounding panel's reliability is never measured.** `cmd_score` computes
  κ over `judgments.jsonl` (the reasoning criteria) only. The `covers_issue`
  panel in `grounding.jsonl` — which single-handedly determines GOG, the
  headline metric — has no reported agreement statistic at all. `judges.py`
  already has `_grounding_verdict_list` to make this a ~20-line change.
- **`audit_error_rate` is computed from 20 items and reported as a bare
  number.** At n=20, an observed 10% error rate has a 95% confidence interval
  of roughly [1%, 32%]. The audit is load-bearing (it is the only non-Claude
  check in the entire loop) and it is currently too small to bear that load
  with a straight face.

Three verdicts are **OPEN-QUESTION** and must be shipped as declared unknowns,
not quietly resolved: the web-vs-MCP heterogeneous-tool comparison, whether the
2025 corpus is inside the evaluated model's training window, and whether
same-provider judges can validate their own family's citations.

One thing I want to flag before it becomes a habit: the accent-free Italian
convention has escaped from source code into the **task queries and the judge
prompts**. "la clausola e nulla" is not a typographic variant of "la clausola è
nulla" — it is a different sentence. I treat that as AMEND-BEFORE-RELEASE.

Verdict tally: 1 SOUND, 3 SOUND-WITH-DECLARATION, 4 AMEND-BEFORE-RELEASE,
2 OPEN-QUESTION (see the gating table at the end for the exact mapping).

---

## 1. Judge panel composition

**What we do.** Two judges, both Claude: Judge A is Sonnet, Judge B is Opus
(`JUDGE_MODELS` in `score/judges.py`). Both are blind to which arm produced
the answer. Agreement is final; disagreement goes to a human queue and is
never guessed by a third model. κ between A and B is computed and reported
with a caveat. A 20-item sample of *agreements* is also audited, producing an
`audit_error_rate`.

**What the literature says.** Three findings converge and they are not
flattering:

- Judges systematically prefer text from their own model, and the preference
  scales with how well the judge can recognise its own output (Panickssery et
  al., arXiv:2404.13076). The effect extends from same-model to same-*family*
  (arXiv:2604.22891).
- The measured benefit of a judge panel comes specifically from **family
  diversity**, not from panel size: PoLL (arXiv:2404.18796) shows small judges
  from disjoint families beating one large judge across three settings and six
  datasets.
- Kohli (arXiv:2605.29800) is the sharpest result for us: nine judges drawn
  from seven families behave like only ~2.2–2.5 statistically independent
  votes, and correlated errors put such panels 8–22 percentage points below
  what independent voting would predict. The direct consequence: **observed
  agreement overstates reliability when judges are correlated.** Our two judges
  share a provider, a training pipeline and probably most of a training corpus.
  Our κ is therefore not comparable to the paper's cross-provider κ=0.836, and
  saying so in a footnote is the minimum, not the fix.

**What our agreement-stratum audit does and does not rescue.** It is the right
instrument: sampling agreements (not only disagreements) is exactly what
detects two correlated judges being confidently wrong together, and the design
deserves credit for including it — even though its only citable support is
practitioner writing, with no peer-reviewed source found. What it does **not**
do at n=20 is produce a usable number. A 2/20 overturn rate is an
`audit_error_rate` of 0.10 with a 95% binomial interval of roughly
[0.012, 0.317]. Reported as "0.100" in `scores.json` it looks like a
measurement; it is an order-of-magnitude sanity check. Worse, the sample is
currently pooled across criteria verdicts and grounding verdicts and across
all three arms, so it is possible to draw 20 agreements and have almost none
of them be grounding verdicts from the `mcp` arm — the exact cell where a
correlated-judge error would most distort the headline result.

**Verdict: AMEND-BEFORE-RELEASE** (the audit design, not the panel
composition; the panel itself is SOUND-WITH-DECLARATION).

**Options.**

| # | Option | Effort | Trade-off |
|---|---|---|---|
| A | Keep the Claude panel, strengthen the audit: raise the agreement stratum to ~50 items, **stratify it by (metric × arm)** so grounding-in-`mcp` is guaranteed representation, and report `audit_error_rate` with its binomial CI. | ~1h coding, ~25 extra minutes of your review time | Still no external model check; but the one external check we have becomes interpretable. |
| B | Add a cross-provider Judge C (e.g. a GPT- or Gemini-class model over a paid API) as a third panel member, keeping the human as tiebreak only when all three split. | ~1 day; a paid API key; ~480 extra API calls (cost, not subscription) | This is the literature's actual remedy (PoLL). Breaks the "subscription-only, no paid API" constraint the design was built around. Gains genuine family diversity for both κ and the covers_issue pass. |
| C | Hybrid: keep the Claude panel for the full run, and add a cross-provider judge on a **fixed 30% sample** used solely to estimate the panel's bias, reported as a calibration figure. | ~half day; ~150 API calls | Cheapest way to get a real external anchor. Does not change any headline number; it quantifies how much to distrust them. |

**My recommendation.** A is the release blocker; C is the strengthening I would
do if you want this to survive scrutiny from an ML reader. B is over-engineering
for a v1.

---

## 2. Statistical power and paired analysis

**What we do.** `metrics.py` computes percentile bootstrap confidence intervals
(10,000 resamples, fixed seed) for `all_pass` and for GOG, per arm. No
confidence interval for `coverage`, `criterion_rate`, `bonus_rate` or MDD. No
test compares two arms.

**What the literature says.** Card et al. (EMNLP 2020, "With Little Power Comes
Great Responsibility") is the canonical finding that NLP experiments are
chronically underpowered and that 20–30 item test sets detect only large
effects. BetterBench (arXiv:2411.12990) found that most benchmarks report
neither statistical significance nor a replication path — reporting both is a
differentiator, not a nicety. The standard paired test for the same items
scored by two systems on a binary outcome is **McNemar's test**; for
non-binary per-item quantities (like GOG_i, which is a ratio in [0,1]) the
standard is a paired bootstrap over the per-item differences. NLPStatTest
(AACL 2020) gives the operational sequence: significance, then effect size,
then power.

Comparing two *independent* per-arm confidence intervals — which is all we can
do today — is both weaker and subtly wrong: our arms answer **the same 30
tasks**, so most of the between-task variance is shared and should be
differenced away. Two overlapping CIs are routinely read as "no significant
difference" when the paired test on the same data is significant.

**What is actually detectable at N=30 and N=20.** Concretely, using the exact
sign test on discordant pairs (McNemar's small-sample form):

- With **N=30** and a perfectly one-directional effect (some tasks flip from
  fail to pass, none flip back), you need **at least 6 flips** to reach
  p<0.05 two-sided. That is a **20 percentage-point** difference under the most
  favourable possible noise conditions.
- Realistically some tasks flip back. With 3 reverse flips you need about 12
  forward flips — a **net 30 pp** difference.
- With **N=20** (the MDD track), the one-directional floor is 6/20 = **30 pp**;
  realistically 40 pp or more.
- A per-arm proportion near 0.5 at N=30 has a 95% CI of roughly **±18 pp**. Our
  headline `all_pass` around 0.79 will land at roughly [0.63, 0.90].

Read against the design's three committed expectations:

- **Hypothesis 1 (grounding rises sharply)** — well powered. The published
  contrast is 3% coverage against 80%; anything in that neighbourhood produces
  ~20 one-directional flips and p < 10⁻⁴. If the effect is real, this design
  will see it.
- **Hypothesis 2 (reasoning stays roughly flat)** — **not testable as
  written.** A 15 pp drop in `all_pass` would be invisible at N=30, and "the
  CIs overlap" is not evidence of equivalence. The README must not claim
  "reasoning was unaffected"; it may only claim "we did not detect a change,
  and our design could not have detected one smaller than ~30 pp."
- **Hypothesis 3 (MDD directionally uncertain)** — honest already, and the
  30–40 pp floor at N=20 means almost any MDD result will be descriptive.

**Verdict: AMEND-BEFORE-RELEASE.**

**Options.**

| # | Option | Effort | Trade-off |
|---|---|---|---|
| A | Add `mcnemar_exact(a, b)` and `paired_bootstrap_diff(a, b)` to `metrics.py`, run every arm pair (bare↔mcp, bare↔web, web↔mcp) per track, and put a minimum-detectable-effect paragraph in the README. Extend bootstrap CIs to `coverage`, `criterion_rate` and MDD. | ~half day, pure functions, no new invocations, fully unit-testable | None. This is the highest value-per-hour change in the document. |
| B | Expand to ~60 jurisprudential + 40 MDD tasks to halve the detectable effect. | Doubles corpus/build/run/judge cost: roughly +900 `claude -p` invocations and +1h of curation | Buys real power, at a cost that probably delays release by weeks. The detectable-effect floor only improves as 1/√N — 60 tasks gets you to ~14 pp one-directional, not to precision. |
| C | Accept N as-is and scope every claim to the grounding hypothesis, stating plainly that reasoning and MDD are reported descriptively. | Zero | Honest, but leaves the "reasoning stays flat" expectation formally unevaluable, which weakens the design's own falsifiability commitment. |

**My recommendation.** A, unconditionally, plus the scoping language from C.
B is a v2 decision, not a release blocker.

---

## 3. Contamination

**What we do.** Seed decisions are Cassazione rulings deposited 7 Jan – 30 May
2025, sampled by fixed-seed enumeration (never by relevance search) and
stratified by domain. The subject model never sees the seed decision, the
principle of law, the criteria or the seed citation — only the standalone
query. The isolation invariant is enforced in code and tested. Grounding is
open-set: recovering the seed earns nothing special.

**What the literature says.** Temporal splitting is the standard mitigation,
but three findings limit what it buys us:

- **Test of Time** (arXiv:2509.00072) shows the temporal signal is highly
  sensitive to *how the questions were constructed* — LLM-generated questions
  behave differently from cloze-style ones. Our tasks are LLM-generated from
  the massima by a Claude builder. That is precisely the sensitive construction
  style, and it is currently not acknowledged anywhere.
- Contamination detection is inherently probabilistic when the training corpus
  is undisclosed (arXiv:2409.09927). We cannot settle this; we can only bound
  it.
- The **SWE-bench Illusion** (arXiv:2506.12286) is the transfer that worries me
  most: 32.67% of that benchmark's apparent successes had the solution leaking
  through the task text itself, and file-path memorization reached 76% for
  in-training repositories. Our builder, subject and both judges are all
  Claude. A builder that has memorised the seed decision can phrase a query in
  a way that hands the subject the answer without ever quoting it — the
  isolation invariant blocks the *document*, not the *phrasing*.
- The nearest legal analogue is the SCOTUS memorization study
  (arXiv:2512.13654); nothing Cassazione-specific exists.

**The core problem.** A corpus window of Jan–May 2025 is very likely inside the
training window of a 2026-generation model. If the bare arm scores non-trivial
GOG, we cannot distinguish "the model reasons about Italian case law" from "the
model remembers these decisions." That ambiguity does not damage the
*comparison* between arms — it is symmetric — but it does damage any absolute
statement about the bare arm, and the design's Hypothesis 2 explicitly invites
absolute reading ("bare Claude already scores ~79%").

**Verdict: OPEN-QUESTION** for the window itself; **AMEND-BEFORE-RELEASE** for
the leakage spot-check, which is cheap and directly warranted by the SWE-bench
transfer.

**Options.**

| # | Option | Effort | Trade-off |
|---|---|---|---|
| A | Declare openly (window vs cutoff unknown; LLM-generated task style noted per Test of Time) **plus** a leakage spot-check: read all 30 task queries against their seed decisions and flag any query that reproduces distinctive phrasing from the massima. Record the count in the README. | ~45 min of your reading time, no code | The minimum I would ship. It also catches builder sloppiness unrelated to contamination. |
| B | Add a post-cutoff subset: 10 additional tasks seeded from decisions deposited after a date you are confident post-dates the model. | ~1 day; +30 generation runs, +60 criteria judge calls, +~120 grounding calls | The only real decontamination move (cf. SWE-rebench, arXiv:2505.20411). Introduces a second, unbalanced stratum that complicates every aggregate. Best framed as a separate reported subset, never merged into the headline. |
| C | Memorization probe: ask the bare model, in a separate off-benchmark call, to state the holding of each seed decision by number. High recall = strong contamination evidence. | ~2h; +30 invocations | Cheap, produces a genuinely informative number, and is itself reportable. Weak as proof (failure to recall does not prove absence of contamination) but strong as a positive signal. |

**My recommendation.** A is a blocker. C is the best cost/insight ratio here and
I would do it. B is future work.

---

## 4. Tool-arm comparability

**What we do.** Three arms differing only in tool availability. Everything else
is held constant and enforced in code: same model, same system prompt, same
turn cap, same `--settings {}`, same `--setting-sources project`, same
`--disable-slash-commands`, same clean working directory, prompt on stdin so
even argv is identical except the tool flags. `_validate_tool_shape` fails a
run whose init message does not report the tools that arm was granted, and
`_hook_feedback_contamination` flags any Stop hook that fired mid-run. Errored
runs are excluded from both judging and scoring, and the exclusion count is
printed per arm. The `mcp` arm runs `LEGAL_PROFILE=normativa`, not `full`.

**What the literature says.** The RAG-fairness line (arXiv:2409.19804 and the
MDPI review) gives the must-control list — same prompt template, same decoding
parameters, one axis changed at a time — and **we satisfy every item on it
except temperature**, which `claude -p` does not expose. That is worth stating
positively; most published tool ablations do not enforce parity at the argv
level, and the "Coding Benchmarks Are Misaligned" position paper
(arXiv:2606.17799) argues the harness is a confound co-equal with the model.
`_validate_tool_shape` is a direct answer to that critique and I would say so.

On tool count: accuracy degrades as the tool catalogue grows
(arXiv:2606.17519, weakly sourced but directionally consistent), and curated
tool subsets are themselves unreliable because they can omit the relevant tool
(arXiv:2503.01763). Choosing `normativa` over `full` is therefore not a neutral
efficiency decision — it is a methodological choice with a known failure mode
in both directions: `full` would penalise the arm with 216 schemas of context
overhead, `normativa` might exclude a tool a task needed.

**The open point.** No source in the survey addresses whether comparing
**generic web search against a specialised legal MCP** is a clean ablation or
its own confound. It is a comparison of two different tools, not of
tool-present against tool-absent, and the literature simply has not settled it.
The `bare`↔`mcp` contrast is clean. The `web`↔`mcp` contrast is not a
controlled ablation and must not be reported as one — the honest framing is
"two tool configurations a real user might choose", not "tools help by X".

**Verdict: SOUND-WITH-DECLARATION** for the parity controls (state them —
they are a strength). **OPEN-QUESTION** for `web`↔`mcp`, to be declared as
genuinely unresolved in the literature rather than argued around.

**Options.** No amendment needed beyond README text. Optionally, log tool-call
failure modes at component level (tool-schema error vs empty retrieval vs
reasoning failure) rather than only end-to-end pass/fail — `RunRecord.tool_calls`
already captures the names, so a per-arm failure taxonomy is a report-side
change of a few hours and would materially improve the write-up.

---

## 5. Grounding pipeline and GOG construct validity

**What we do.** Four stages: extraction (deterministic regex for canonical
forms, plus explicit counting of *narrative* citations that carry no
identifying elements), resolution against live Italgiure via
`verifica_citazioni` with a fail-closed marker vocabulary, legal validation by
a second blind panel pass, and fail-closed aggregation —
`counts_as_grounded()` requires `identifiable AND resolved is True AND
covers_issue is True`.

Three details deserve specific credit:

- **Narrative citations are counted and never deduplicated.** Two separate
  hand-waves supporting two different claims are two produced citations. This
  is the single most important construct decision in the metric: it is what
  makes GOG detect the exact failure mode the paper found in GPT-5.5 (62 of 67
  answers gesturing at "consolidated case law" with nothing verifiable).
  Collapsing them would shrink the denominator and inflate the score.
- **The `verificata` substring trap is handled.** "non verificata" contains
  "verificata"; `_MISSING_MARKERS` is checked first, with a test pinning it.
  Every unresolved state — metadata mismatch, pre-2020, transient failure —
  scores as ungrounded.
- **A transient resolution failure never fabricates `resolved=False`.** The
  citation is left at its unset default and the resolution cache is not
  written. This is the correct fail-closed behaviour and is unusually careful.

**What the literature says.** There is **no published metric identical to
GOG**. The nearest concepts are CLERC's decoupling of text quality from an
explicit hallucination measure (arXiv:2406.17186 — GPT-4o had the best ROUGE
and the worst hallucination rate, which is exactly our dissociation argument),
LegalCiteBench's **Misleading Answer Rate** for concrete-but-wrong authorities
(arXiv:2605.10186, MAR above 94% for 20 of 21 closed-book models), and
Magesh et al. on commercial legal RAG (arXiv:2405.20362, 17–33% hallucination
even with retrieval — which is the empirical justification for validating
post-hoc rather than trusting the tool). Dahl et al.'s closed-domain /
open-domain taxonomy (arXiv:2401.01301) maps onto our states cleanly. The
nearest Italian precedent is "From Judgments to Issues" (arXiv:2607.03325),
whose citation-hallucination filter cut residual hallucination from 11.7% to
0.9% over ~330k tax judgments.

Our **three-state design** — grounded / no-credit-because-unresolvable /
no-credit-but-explicitly-not-recorded-as-fabricated — has no direct precedent.
That third state matters legally: an authentic Cassazione decision on an
adjacent point is a real authority badly deployed, not an invention, and
conflating the two would misstate the risk profile a lawyer cares about. I
would present this as an original methodological contribution, with MAR and
Magesh et al. cited as nearest concepts.

**The covers_issue mechanism, assessed.** This was underspecified in the design
("judged by the panel") and implemented during the build as a second blind
panel pass. Reviewing it against the same-provider concern from dimension 1:

- **Structurally sound.** Both judges must agree; disagreement yields `None`
  and goes to the human queue; `parse_grounding_output` refuses to read an
  unparseable verdict as either `covers=False` (indistinguishable from a real
  negative) or `covers=True` (fabricated grounding). Only `resolved is True`
  citations are judged at all, so the panel can never resurrect an unresolvable
  citation.
- **A genuine and underrated strength**: `build_grounding_prompt` passes the
  query, the issue summary, the citation string and the resolution note —
  **never the full answer**. A verbose, confident, fluently-written answer
  therefore cannot bias its own citations' grounding verdicts. That closes the
  verbosity-bias channel documented in Zheng et al. (arXiv:2306.05685) for this
  pass specifically. Say this in the README; it is a real design property, not
  an accident.
- **The unmitigated risk.** The *same two correlated Claude judges* determine
  both the reasoning verdicts and the grounding verdicts. The benchmark's whole
  thesis is that these two constructs **dissociate** — reasoning high, grounding
  low. If Sonnet and Opus share a bias (for instance, both being generous about
  whether a Cassazione decision on a neighbouring question "covers the issue"),
  that bias inflates GOG in whichever arm produces more real citations, which
  is by construction the `mcp` arm. Kohli's correlated-error result
  (arXiv:2605.29800) says agreement will not reveal this.
- **The measurement gap.** `cmd_score` computes κ from `judgments.jsonl` only.
  There is **no κ over `grounding.jsonl`** — the pass that determines the
  headline metric has no reported reliability statistic at all.
  `_grounding_verdict_list` and `_paired_verdicts` already exist; this is a
  ~20-line addition to `cmd_score` and a field in `scores.json`.

**Verdict: AMEND-BEFORE-RELEASE** (report grounding κ; stratify the audit into
this cell). The pipeline itself is **SOUND** and is the strongest part of the
design.

**Options.**

| # | Option | Effort | Trade-off |
|---|---|---|---|
| A | Compute and report κ over grounding verdicts alongside the criteria κ; add `kappa_grounding` to `scores.json` and the report. | ~1h | None. Do it. |
| B | Guarantee the audit's agreement stratum includes grounding verdicts from the `mcp` arm (stratified sampling, see dimension 1 option A). | folded into 1-A | None. |
| C | Have the human tiebreak *all* `covers_issue` verdicts for one arm's worth of tasks, as a calibration set. | ~2h of your time for ~40 citations | Turns the grounding panel from "unvalidated" into "validated on a known subset". Strongest single improvement to the headline metric's credibility. |

---

## 6. MDD track framing

**What we do.** 20 adversarial tasks asking for analysis of a document
described as attached and never supplied. One criterion, C-001, with three
conjunctive requirements: all three must pass or the task fails. Scored as a
plain rate.

**What the literature says.** AbstentionBench (Meta/FAIR, arXiv:2506.09038) is
the canonical framework and gives us vocabulary we should adopt rather than
invent: our MDD scenario is exactly their **False Premise** category (the
prompt asserts something untrue — that a document is attached), bordering on
**Answer Unknown**. Its headline finding is directly relevant and slightly
alarming for us: **reasoning fine-tuning makes abstention worse, by ~24% on
average.** Our subject is a frontier reasoning model. That makes the design's
"MDD is directionally uncertain" stance well-founded — and gives a specific
prior worth stating: if the `mcp` arm's MDD *drops*, that is consistent with
published behaviour (more capability, more willingness to produce an answer
anyway), not evidence of a harness bug.

No legal or civil-law-specific abstention work was found. Framing our track in
AbstentionBench's terms is therefore how a reader connects it to anything.

**On the conjunctive criterion.** Requiring all three sub-requirements is
strict, and strictness is defensible for a safety metric — a partial refusal
that still analyses a nonexistent document is a failure in practice. But it
compounds with dimension 2's power problem: a conjunctive criterion has a lower
base rate, and at N=20 with a 30–40 pp detectable floor, MDD will be
descriptive. It should be reported as such.

**Verdict: SOUND-WITH-DECLARATION.** Adopt AbstentionBench vocabulary in the
README, cite the reasoning-worsens-abstention finding as context for whatever
direction the result takes, and label the track descriptive.

---

## 7. Single-run non-determinism

**What we do.** One run per (task, arm). No repeats. Temperature is not
controllable through `claude -p`.

**What the literature says.** τ-bench (arXiv:2406.12045) introduced **pass^k**
— the probability that a system succeeds on all k independent attempts — and
found GPT-4o's pass^8 below 25% in the retail domain where pass^1 looked far
healthier. The blunt reading: **single-run arm comparisons are weak evidence
about agent behaviour.** Our `mcp` arm is an agent (it plans tool calls); its
`bare` counterpart is closer to a single forward pass and is plausibly *more*
stable. That asymmetry means run-to-run variance is not symmetric across arms,
so it does not simply cancel in the comparison.

**Verdict: AMEND-BEFORE-RELEASE**, at the smallest available scope. Shipping
N=1 with no variance estimate at all is the weakest defensible position, and
the fix can be genuinely cheap if scoped to the central hypothesis.

**Options.**

| # | Option | Effort (in `claude -p` invocations) | Trade-off |
|---|---|---|---|
| A | 3 repeats on a fixed 10-task subset, all three arms, **full** scoring (criteria + grounding). | +60 generations, +120 criteria judge calls, +~250 grounding calls ≈ **+430 invocations** | Complete variance picture. Roughly +50% on total run cost — see the volume note below. |
| B | 3 repeats on a fixed 10-task subset, **`bare` and `mcp` only**, scored for **grounding only** (the central hypothesis). Report coverage variance and per-task GOG spread. | +40 generations, +~170 grounding calls ≈ **+210 invocations** | Covers the hypothesis that matters at half the cost. Says nothing about reasoning-track stability. |
| C | Accept single-run and declare it, citing τ-bench. | Zero | Defensible only if the effect size turns out to be very large (e.g. coverage 0.05 → 0.70). Indefensible for any close call. |

**Volume note, worth knowing before you budget.** The design's §4.1 table
estimated 90 grounding-validation calls per judge on the assumption of one call
per *response*. The implementation judges one call per *resolved citation* per
judge. If answers average three resolved citations, the grounding pass alone is
~380 calls rather than 180, putting the real total nearer **830** invocations
than the estimated 630. This is not a methodological flaw — per-citation is the
correct granularity — but it changes the arithmetic on every option above.

**My recommendation.** B. It buys the variance estimate on the only hypothesis
the benchmark is really testing, for about a quarter of the run's cost.

---

## 8. Reproducibility and lifecycle — BetterBench self-assessment

Run against the survey's distilled 17-item checklist (BetterBench,
arXiv:2411.12990; HELM, arXiv:2211.09110; Bowman & Dahl, NAACL 2021). One line
each, honest.

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Task selection reproducible, not convenience sampling | **PASS** | Fixed-seed enumeration ordered by deposit date, stratified by domain; never relevance-ranked. |
| 2 | Temporal/contamination boundary declared vs model cutoffs | **PARTIAL** | Window declared; its relation to the subject model's training cutoff is not. Fix in README. |
| 3 | Sensitivity of contamination signal to task-generation style acknowledged | **FAIL** | Tasks are LLM-generated from massime — the style Test of Time (arXiv:2509.00072) flags. Currently unmentioned. |
| 4 | CIs per metric/track | **PARTIAL** | Bootstrap CIs exist for `all_pass` and GOG only; `coverage`, `criterion_rate`, `bonus_rate` and MDD have none. |
| 5 | Paired tests for same-item multi-arm comparisons | **FAIL** | None implemented. See dimension 2. |
| 6 | Power analysis or explicit small-N acknowledgment | **PARTIAL** | §7.2 concedes size; no minimum-detectable-effect statement anywhere. |
| 7 | Replicability (data, prompts, rubric published) | **PASS** | `data/tasks.json` versioned in git; prompts are literals in `arms.py`/`judges.py`; README must point at both. |
| 8 | No composite when constructs dissociate | **PASS** | Explicit non-goal; three tracks reported separately throughout. |
| 9 | Constructs explicitly operationalized | **PARTIAL** | Reasoning and MDD are operationalized in code. `covers_issue` is operationalized **only as a judge prompt** — publish `GROUNDING_TEMPLATE` verbatim in the README or the construct is not inspectable. |
| 10 | Scoring reliability reported (κ + caveats) | **PARTIAL** | κ over criteria only. No κ over grounding — the pass that determines the headline metric. See dimension 5. |
| 11 | Statistical power addressed | **FAIL** | Same as 6. |
| 12 | Bias in task/label construction checked | **PARTIAL** | Builder-model circularity is declared; no leakage spot-check performed. See dimension 3. |
| 13 | Versioned benchmark lifecycle | **PARTIAL** | Data are in git but the task set carries no version string or changelog. Add `benchmark_version` to `tasks.json`. |
| 14 | Claims scoped to construct validity | **PASS** | Non-comparability warning and the "home ground" limitation are both explicit in §7. |
| 15 | Analysis plan fixed before results | **PASS, informally** | The design doc's three committed expectations are a pre-registration in substance. Formalize by git-tagging the design doc before the first scored run. |
| 16 | Effect sizes beside significance | **FAIL** | Follows automatically from item 5. |
| 17 | Enumerable, non-cherry-picked sampling frame | **PASS** | The Solr enumeration over the window is the frame; the draw is seeded. |

Tally: **6 PASS, 7 PARTIAL, 4 FAIL.** Every FAIL and every PARTIAL except #9
is addressed by the amendments in dimensions 1, 2, 3 and 5 plus README text —
there is no item here requiring a redesign.

**On pre-registration.** The survey notes it is emerging rather than standard
(arXiv:2302.10086) and defends against HARKing (hypothesising after results are
known) and selective reporting. Our design doc already commits, in advance, to
three named expectations including "if grounding does not rise, the experiment
has failed and the README will say so." That is a stronger commitment than most
published benchmarks make. **Formalize it cheaply**: git-tag the design doc
(e.g. `benchmark-preregistration-v1`) before the first scored run, add the tag
SHA to the README, and record any post-hoc deviation as an explicit deviation
note. Effort: ten minutes. Credibility gain: disproportionate.

**Verdict: AMEND-BEFORE-RELEASE** (items 3, 5, 11, 16 are the FAILs; 5/11/16
are one change).

---

## 9. Gold-set construction

**What we do.** Builder is Claude Opus 5; subject is Claude Opus 5; both judges
are Claude. Tasks are generated from the massima and principle of law. Targeted
human curation covers tasks where the builder self-reports low confidence,
where criteria are ambiguous, or where judges later disagree — an estimated
8–12 of 30. The isolation invariant is enforced and tested.

**What the literature says.** LegalBench (arXiv:2308.11462) is the gold
standard here and it is human-authored by legal professionals throughout — 162
tasks written by lawyers, not generated. The construct-validity review of 445
articles (arXiv:2511.04703) found most benchmarks weak on exactly this axis,
with 27% relying on convenience sampling. The Italian precedent, "From
Judgments to Issues" (arXiv:2607.03325), is instructive on scale and on
validation practice: ~330k judgments decomposed into per-issue IRAC structure,
with human validation finding 4 of 78 sampled issues flagged as missing — a
roughly 5% construction error rate on a pipeline far more constrained than
free-form task generation.

**The triangular self-reference.** Claude writes the tasks, Claude answers
them, Claude grades them. The design already declares this (§7.6b) and makes
the right argument: because all three arms share the same builder and the same
judges, the bias is a **constant, not a differential**, so the *comparison*
survives. I agree with that reasoning and think it is the strongest defence
available. Two caveats it does not cover:

- The bias is only constant if it is **arm-independent**. A builder that
  phrases queries in a way Claude-with-tools finds especially tractable is not
  a constant across arms. This is the SWE-bench Illusion mechanism
  (arXiv:2506.12286) applied to phrasing rather than to solution text, and it
  is the specific reason the dimension-3 leakage spot-check is worth 45 minutes
  of your time.
- **Absolute levels are uninterpretable.** No absolute number from this
  benchmark — not `all_pass`, not GOG — may be read as an estimate of how the
  model would perform on tasks written by a human lawyer. Only the differences
  between arms are interpretable. The README should say this in one blunt
  sentence.

**On targeted versus full curation.** Targeted curation is the pragmatic choice
and is declared. Its weakness: the trigger conditions (builder low confidence,
ambiguous criteria, judge disagreement) all detect *visible* problems. A task
that is confidently wrong — a criterion that misstates the holding, in
plausible legal Italian — passes every trigger and never reaches you. Given the
~5% construction error rate that a much more constrained Italian pipeline
measured, I would expect 1–3 such tasks in 30.

**Verdict: SOUND-WITH-DECLARATION**, with one recommended strengthening.

**Options.**

| # | Option | Effort | Trade-off |
|---|---|---|---|
| A | Keep targeted curation, declare it, add a **random 5-task spot-read** on top of the triggered set: read the seed decision and confirm the criteria actually reflect its holding. Report the number of corrections. | ~40 min of your time | Turns "we curated the suspicious ones" into "we curated the suspicious ones and measured the error rate in the rest". Directly answers checklist item 12. |
| B | Full curation of all 30 tasks. | ~3h of your time | Removes the concern entirely. Best if you intend this to be cited. |
| C | Accept as designed. | Zero | Leaves the confidently-wrong-task class unmeasured. |

**My recommendation.** A. It is 40 minutes and it converts a declared weakness
into a reported number.

---

## 10. Presentation integrity

**Accent-free Italian.** The repo convention writes Italian without accents
("e" for "è", "gia" for "già", "puo" for "può") and it has propagated into two
places it should not have: the **task queries shown to the evaluated models**
and the **judge prompts** (`_JUDGE_TEMPLATE` and `GROUNDING_TEMPLATE` in
`judges.py` — "Il tuo compito NON e verificare se la fonte esiste (gia fatto)").

Weighing this honestly, because it is easy to over- or under-react:

- *Argument that it is harmless*: it is applied identically to all three arms,
  so any degradation is symmetric and the comparison holds. Modern tokenizers
  handle unaccented Italian; models routinely read informal Italian written
  without accents.
- *Argument that it is not harmless*, which I find stronger: in Italian, `è`
  (is) and `e` (and) are **different words**, distinguished only by the accent.
  "la clausola e nulla" is not a misspelling of "la clausola è nulla" — it is a
  grammatical sentence with a different meaning. Legal Italian is dense with
  copular constructions, so this ambiguity fires constantly in exactly this
  register. Beyond the specific ambiguity, no Italian lawyer writes a
  professional query this way, which is a straightforward **ecological validity**
  problem: the benchmark's claim is about how a system responds to a
  professional query, and these are not professional queries typographically.
  That is a construct-validity concern of the kind arXiv:2511.04703 catalogues,
  not a style nit.
- The judge prompts are the worse case: a degraded instruction to the grader
  affects every measurement downstream, and it is not even the object of study.

The repo convention exists for source code, and it should stay there. Data
files and prompt literals in Italian are content, not code.

**Verdict: AMEND-BEFORE-RELEASE.** Restore accents in (a) `data/tasks.json`
query and criteria text, (b) the judge and grounding prompt templates, (c) the
system prompt in `arms.py`. Leave code identifiers, docstrings, comments and
commit messages under the existing English/accent-free rule. Effort: ~1h,
mostly a careful pass over `tasks.json` before the run (and it must happen
**before** generation, not after — regenerating tasks invalidates any run
already executed). If you decline, the README must declare it as a known
deviation from professional register, which I think reads worse than fixing it.

**Non-comparability warning.** The design's §7.1 already forbids any claim of
the form "we beat Next-OS" and states the numbers are not comparable to the
Aptus table. This mirrors the Aptus paper's own practice and is correct. I
would strengthen the placement: put it as the **first paragraph** of the README,
above the results table, not in a limitations section at the bottom. Anyone
skimming the results will otherwise cross-read them against the published
table, which is precisely what the warning exists to prevent. Same treatment
for the "different model from any published row" point (§7.4).

---

## Release-gating summary

| # | Dimension | Verdict | Recommended action | Owner decision needed |
|---|---|---|---|---|
| 1 | Judge panel composition | AMEND-BEFORE-RELEASE (audit); SOUND-WITH-DECLARATION (panel) | Raise agreement stratum to ~50, stratify by (metric × arm), report `audit_error_rate` with its CI | **Sì** — also whether to add a cross-provider judge (option B/C) |
| 2 | Statistical power & paired analysis | AMEND-BEFORE-RELEASE | Add McNemar + paired bootstrap to `metrics.py`; extend CIs to all metrics; minimum-detectable-effect paragraph in README | **Sì** — only on whether to expand N (option B); the code change is not optional |
| 3 | Contamination | OPEN-QUESTION (window); AMEND (leakage check) | Declare window/cutoff and LLM-generated task style; run the 30-query leakage spot-check | **Sì** — whether to add the memorization probe (option C) |
| 4 | Tool-arm comparability | SOUND-WITH-DECLARATION; OPEN-QUESTION for web↔mcp | State the parity controls we satisfy; declare `normativa` as a documented trade-off; declare web↔mcp as unresolved in the literature | No |
| 5 | Grounding pipeline & GOG | SOUND (pipeline); AMEND (reliability reporting) | Add κ over grounding verdicts; publish `GROUNDING_TEMPLATE`; present the three-state design as an original contribution | **Sì** — whether to do the full calibration set (option C) |
| 6 | MDD framing | SOUND-WITH-DECLARATION | Adopt AbstentionBench False-Premise vocabulary; cite reasoning-worsens-abstention as context; label the track descriptive | No |
| 7 | Single-run non-determinism | AMEND-BEFORE-RELEASE | 3 repeats on a 10-task subset, `bare`+`mcp`, grounding only (~+210 invocations) | **Sì** — scope of repeats (A/B/C) |
| 8 | Reproducibility & lifecycle | AMEND-BEFORE-RELEASE | Close checklist items 3/5/11/16; add `benchmark_version`; git-tag the design doc as pre-registration | No (the tag is free) |
| 9 | Gold-set construction | SOUND-WITH-DECLARATION | Add a random 5-task spot-read on top of targeted curation; declare absolute levels uninterpretable | **Sì** — targeted + spot-read vs full curation |
| 10 | Presentation integrity | AMEND-BEFORE-RELEASE | Restore accents in task queries, criteria and all judge/system prompts; move the non-comparability warning to the top of the README | **Sì** — accents are a convention change; needs your call |

---

## What I would do

Opinionated. You decide.

### (a) Blockers — I would not release without these

1. **Restore accents in the task queries, criteria and every prompt template.**
   Must happen *before* the generation run, since regenerating tasks
   invalidates completed runs. ~1h. (Dimension 10)
2. **Add paired tests to `metrics.py`** — exact McNemar for binary per-task
   outcomes (`all_pass`, `coverage`, MDD), paired bootstrap for GOG_i — and run
   them for all three arm pairs. Extend bootstrap CIs to `coverage`,
   `criterion_rate` and MDD. ~half day, pure functions, no invocations.
   (Dimension 2)
3. **Report κ over the grounding panel.** The metric the whole benchmark exists
   to measure currently has no reliability statistic. ~1h. (Dimension 5)
4. **Fix the audit's statistical footing**: agreement stratum to ~50, stratified
   by (metric × arm), `audit_error_rate` reported with its binomial CI. ~1h
   coding, ~25 extra minutes of your review. (Dimension 1)
5. **Run the leakage spot-check** on all 30 task queries against their seed
   decisions, and record the count. ~45 min of your time. (Dimensions 3, 9)
6. **Git-tag the design doc as a pre-registration** before the first scored run
   and cite the tag in the README. ~10 min. (Dimension 8)

### (b) Declarations the README must carry

The full list, with citations, is the checklist in the next section. It feeds
Task 13 directly.

### (c) Optional strengthenings, with cost

| Strengthening | Cost | Why I would consider it |
|---|---|---|
| 3 repeats on a 10-task subset, `bare`+`mcp`, grounding only | ~+210 `claude -p` invocations | τ-bench (arXiv:2406.12045) makes single-run agent comparisons weak evidence; this covers the central hypothesis. **The one I would actually do.** |
| Memorization probe on the 30 seed decisions | ~+30 invocations, ~2h | Produces a real, reportable contamination signal instead of a shrug. |
| Random 5-task curation spot-read | ~40 min of your time | Converts "targeted curation" from a declared weakness into a measured error rate. |
| Human tiebreak of all `covers_issue` verdicts for one arm | ~2h of your time, ~40 citations | Turns the grounding panel from unvalidated into validated-on-a-known-subset. Biggest single credibility gain for GOG. |
| Cross-provider calibration judge on a 30% sample | ~half day + ~150 paid API calls | The literature's actual remedy for correlated judges (PoLL, arXiv:2404.18796). Breaks the subscription-only constraint. |
| Component-level tool failure taxonomy in the report | ~3h | `RunRecord.tool_calls` already has the data; answers the harness-as-confound critique (arXiv:2606.17799). |

### (d) Future work — say so, do not do it now

- A post-cutoff task subset seeded from decisions after the model's training
  cutoff (decontamination-by-freshness, cf. SWE-rebench arXiv:2505.20411).
- Expanding to ~60 + 40 tasks to halve the detectable effect (dimension 2).
- A non-Claude subject arm — currently impossible under the `claude -p`
  harness, and the design says so.
- Extending beyond Cassazione (the "home ground" limitation), where the MCP's
  advantage is untested.
- Publishing the three-state grounding taxonomy as a standalone methodological
  note; it is the most original piece of this work.

---

## README limitations checklist (input to Task 13)

Every bullet below must appear in `benchmarks/legalita/README.md`. Items marked
**§7** already exist in the design's declared limitations and carry over; the
rest are new from this review. Each carries its supporting citation.

**Framing (put these above the results table, not at the bottom)**

1. **This is not LegalITA v2.** A methodological replica on our own tasks; the
   numbers are not comparable to the Aptus table and no "we beat X" claim is
   admissible. (§7.1 — mirrors the Aptus paper's own non-comparability warning)
2. **Different subject model** from any published row, so cross-reading the two
   tables is not legitimate. (§7.4)
3. **Only differences between arms are interpretable.** Absolute levels are not
   estimates of performance on human-authored tasks, because the tasks were
   generated by the same model family being evaluated. (LegalBench,
   arXiv:2308.11462, as the human-authored contrast; construct-validity review,
   arXiv:2511.04703)

**Judging**

4. **Same-provider two-judge panel** (Sonnet + Opus). κ is inflated relative to
   a cross-provider panel and is not comparable to the paper's 0.836. (PoLL,
   arXiv:2404.18796; Kohli, arXiv:2605.29800; self-preference,
   arXiv:2404.13076) (§7.6)
5. **Correlated judges can agree and both be wrong**, and observed agreement
   does not reveal this — which is why the human audit samples agreements, not
   only disagreements. (Kohli, arXiv:2605.29800)
6. **`audit_error_rate` is an order-of-magnitude check, not a measurement**;
   report it with its binomial confidence interval and state the sample size.
   (no canonical peer-reviewed precedent for agreement-stratum auditing — the
   survey found practitioner sources only; declare it as such)
7. **Closed loop on one model family**: builder, subject and both judges are
   Claude; the human audit is the only external check. The bias is a constant
   across arms and so does not invalidate the comparison, but it does
   invalidate absolute readings. (§7.6b)
8. **Grouped criterion judging** deviates from the paper's per-criterion
   protocol; the halo mitigation (shuffled criterion order + separate written
   justification) is consistent with Zheng et al. (arXiv:2306.05685) but is
   **not validated by any dedicated study** — the survey found none. (§7.7)
9. **Grounding verdicts are produced by the same correlated pair** that produces
   the reasoning verdicts, so the dissociation between the two tracks is not
   fully independent. Mitigated by the grounding judge never seeing the full
   answer, which closes the verbosity-bias channel. (Zheng et al.,
   arXiv:2306.05685)

**Statistics**

10. **30 + 20 tasks** against the paper's 67 + 40. (§7.2)
11. **Minimum detectable effect**: at N=30 the smallest difference this design
    can detect is ~20 pp under the most favourable noise conditions and ~30 pp
    realistically; at N=20 (MDD), ~30–40 pp. "No significant difference" here
    is not evidence of equivalence. (Card et al., EMNLP 2020; NLPStatTest,
    AACL 2020)
12. **Arms are compared with paired tests on the same tasks**, not by comparing
    independent per-arm confidence intervals. (BetterBench, arXiv:2411.12990)
13. **Single run per (task, arm)** — or, if the repeats are added, repeats on a
    named subset only. Agentic arms are non-deterministic and single-run
    comparisons are weak evidence. (τ-bench, arXiv:2406.12045)

**Contamination and task construction**

14. **Temporal window** (Cassazione, 7 Jan – 30 May 2025) is stated together
    with the fact that it **likely falls inside the subject model's training
    window**, and that this is not resolvable with an undisclosed training
    corpus. (arXiv:2409.09927; SCOTUS memorization, arXiv:2512.13654) (§7.9,
    extended)
15. **Tasks are LLM-generated from the massime**, and contamination signals are
    known to be sensitive to task-generation style. (Test of Time,
    arXiv:2509.00072)
16. **Leakage spot-check performed** on all 30 queries against their seed
    decisions, with the number of flagged/corrected queries reported. (SWE-bench
    Illusion, arXiv:2506.12286 — 32.67% solution leakage via task text)
17. **Targeted, not full, curation** — plus the random spot-read result if
    option 9-A is taken. A confidently-wrong task triggers none of the curation
    conditions. (From Judgments to Issues, arXiv:2607.03325 — ~5% construction
    error rate on a more constrained pipeline) (§7.5)
18. **Sampling is by seeded enumeration, never by relevance**, and grounding is
    open-set so recovering the seed citation earns nothing. (§2.1)

**Tools and arms**

19. **Parity controls satisfied** — same model, system prompt, turn cap,
    settings, setting-sources, slash-command state and working directory;
    prompt on stdin; tool shape verified per run against the init message.
    **Temperature is the one control we cannot hold**, because `claude -p` does
    not expose it. (RAG-fairness must-control list, arXiv:2409.19804;
    harness-as-confound, arXiv:2606.17799)
20. **`web` vs `mcp` is not a controlled ablation.** Whether comparing a generic
    web search against a specialised legal tool is a clean comparison or its own
    confound is **genuinely unresolved in the literature** — the survey found no
    source addressing it. `bare` vs `mcp` is the clean contrast.
21. **Reduced MCP profile** (`normativa`, not `full`) — a documented trade-off,
    not a neutral choice: large tool catalogues degrade accuracy
    (arXiv:2606.17519) and curated subsets can omit a needed tool
    (arXiv:2503.01763). (§7.8)
22. **Home ground.** Corpus is Cassazione and the MCP queries Cassazione; the
    result supports "helps ground on Cassation case law", not "helps always".
    (§7.3)

**Grounding metric**

23. **Three-state fail-closed design stated explicitly**: grounded /
    no-credit-because-unresolvable / real-but-off-issue (no credit, and
    explicitly **not** recorded as fabricated). No published metric is identical;
    nearest concepts are CLERC's hallucination rate (arXiv:2406.17186),
    LegalCiteBench's MAR (arXiv:2605.10186) and Magesh et al. on commercial
    legal RAG (arXiv:2405.20362, 17–33% hallucination with retrieval). The
    closed-domain/open-domain taxonomy is Dahl et al. (arXiv:2401.01301).
24. **Narrative citations count in the denominator and are never
    deduplicated** — this is what makes the metric detect the "consolidated case
    law" failure mode rather than reward it.
25. **Resolution is fail-closed against the live Italgiure archive (2020+)**:
    only `verificata` counts; `metadati discordanti`, `non verificabile`
    (pre-2020) and transient `non verificata` all score as ungrounded.
26. **Known residual**: report rows matched by number/year only, so a
    civil/criminal pair sharing a number and year within one answer could be
    misattributed. Symmetric across arms.
27. **`covers_issue` mechanism published verbatim** — the `GROUNDING_TEMPLATE`
    prompt is the operational definition of the construct and must be readable,
    not just described. (construct operationalization, BetterBench
    arXiv:2411.12990)

**MDD**

28. **Framed as False Premise / Answer Unknown abstention** in AbstentionBench
    terms (arXiv:2506.09038). No legal-domain abstention literature exists — the
    survey found none.
29. **Reasoning models abstain worse** (~24% degradation, AbstentionBench): a
    drop in the tool arm's MDD is consistent with published behaviour, not
    automatically a harness bug.
30. **The conjunctive C-001 criterion is strict by design**, and at N=20 the
    track is reported descriptively.

**Lifecycle**

31. **Pre-registration**: the design doc's three committed expectations were
    git-tagged before the first scored run; the tag SHA is cited and any
    deviation is recorded as a deviation. (arXiv:2302.10086)
32. **Benchmark version** recorded in `tasks.json`; the task set is versioned in
    git and re-runnable from the documented commands.
33. **Never run in CI** — the suite hits live Normattiva and Italgiure.

---

## References

Cited by short name and arXiv id throughout; full entries in
[`literature-survey.md`](2026-08-16-legalita-literature-survey.md).
Where the survey recorded **[not found]** — notably the absence of any source
on heterogeneous-tool ablations, of a peer-reviewed precedent for
agreement-stratum auditing, and of any legal-domain abstention literature —
this review treats the gap as a gap and says so, rather than citing around it.
