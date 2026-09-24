# Literature survey — LegalITA replica benchmark methodology review

> Compiled 2026-08-16 from five parallel research strands (web search, sources
> verified where stated). Purpose: evidence base for the pre-release
> methodological review requested by the owner. Honest gaps are marked
> **[not found]** — a separate analysis pass maps these findings onto our
> design; this file collects evidence only.

## Strand A — Legal LLM benchmarks and evals

- **LegalBench** — Guha et al., NeurIPS 2023 D&B. 162 tasks across 6 legal
  reasoning types, hand-authored by legal professionals. Heterogeneous
  per-task grading (multiple-choice, binary classification, exact-match)
  against human-authored gold answers. Closest precedent for per-task
  binary criteria. arXiv:2308.11462.
- **LexGLUE** — Chalkidis et al., ACL 2022. 7 legal datasets (SCOTUS, ECHR,
  EU), mostly text classification + CaseHOLD multiple-choice QA.
  Jurisdiction stratification precedent. aclanthology.org/2022.acl-long.297.
- **LEXTREME** — Niklaus et al., Findings EMNLP 2023. Multilingual (24
  languages incl. Italian), 11 datasets; best baseline 61.3/100. No
  Cassazione/Normattiva coverage. arXiv:2301.13126.
- **LawBench** — Fei et al., EMNLP 2024. Chinese; 20 tasks over a 3-level
  cognitive taxonomy (memorization / understanding / application), 51 LLMs.
  Precedent for cognitive-level stratification. arXiv:2309.16289.
- **LexEval** — NeurIPS 2024 D&B. Largest Chinese legal benchmark: 23 tasks,
  14,150 questions, 6-dimension "LexAbility" taxonomy, 38 LLMs.
  arXiv:2409.20288.
- **CLERC** — Findings NAACL 2025 (arXiv:2406.17186). US case-law retrieval +
  RAG generation with citations over 1.84M federal decisions. Grades text
  quality (ROUGE) SEPARATELY from an explicit hallucination measure —
  GPT-4o best ROUGE and worst hallucination rate. Closest precedent for
  decoupling citation reliability from answer quality.
- **Katz, Bommarito, Gao, Arredondo 2023** — GPT-4 passes the UBE (Phil.
  Trans. R. Soc. A). Mixed multiple-choice + open-ended professional-exam
  grading precedent. No IT/EU bar-exam follow-ups found **[not found]**.
- **Italian legal NLP**: no Italian analogue of LegalBench exists.
  - ITALIAN-LEGAL-BERT (Computer Law & Security Review) — pretraining
    resource on Italian civil judgments, not a benchmark.
  - ITA-Bench (SapienzaNLP) — generalist Italian suite, no legal component.
  - Cassazione topic-modeling dataset (Univ. Firenze 2025, arXiv:2505.08439)
    — corpus processing, not an eval.
  - **"From Judgments to Issues"** (Piccioli, Fidelangeli, Santin, Vivo,
    July 2026, arXiv:2607.03325) — HIGHLY RELEVANT: decomposes ~330k Italian
    tax judgments into per-issue IRAC XML with an explicit citation
    hallucination filter (checks model-produced references against those in
    the source judgment; residual hallucination 11.7% → 0.9%). Human
    validation: 4/78 issues flagged missing. Closest Italian precedent to
    our isolation invariant + fail-closed citation checking.
  - EVALITA: no legal reasoning/QA task, only historical legal-text parsing
    (2011-2014). CIRSFID/ITTIG: nothing verifiable found **[not found]**.
- **LegalCiteBench** (arXiv:2605.10186, AI4Law @ ICML 2026) — closed-book
  citation recovery/verification over 1,000 US opinions (~24k instances).
  Introduces **Misleading Answer Rate (MAR)**: concrete-but-wrong
  authorities; MAR >94% for 20/21 models closed-book. Quantifies how hard
  correct citation "from memory" is without tools.

**Strand A practices relevant to us**: human-authored gold criteria
(LegalBench); cognitive-level stratification as an alternative axis to
domain (LawBench/LexEval); decoupling citation reliability from text
quality (CLERC); the Italian tax-judgment pipeline's fail-closed citation
filter as the nearest domestic precedent; NO existing benchmark uses a GOG
ratio identical to ours — nearest concepts are CLERC's hallucination rate
and LegalCiteBench's MAR (cite both as related work).

## Strand B — Legal hallucination & citation grounding

- **Dahl, Magesh, Suzgun, Ho — "Large Legal Fictions"** (J. Legal Analysis
  16(1), 2024; arXiv:2401.01301; code: reglab/legal_hallucinations).
  Taxonomy: closed-domain vs open-domain (training-corpus contradiction vs
  factual infidelity to the controlling legal landscape). Verification both
  reference-based (metadata vs authoritative DBs) and reference-free
  (self-consistency at high temperature). Hallucination on verifiable
  case-law queries: 58% (ChatGPT-4) to 88% (Llama 2); worse for lower
  courts and less prominent cases.
- **Magesh, Surani, Dahl, Suzgun, Manning, Ho — "Hallucination-Free?"**
  (arXiv:2405.20362; J. Empirical Legal Studies 2025). Pre-registered eval
  of commercial legal RAG tools (Lexis+ AI, Westlaw AIRC, Ask Practical
  Law): 17-33% hallucination — RAG reduces but does not eliminate. Formal
  correct/misgrounded/hallucinated definitions are behind the paywall
  **[not found in detail]**. NOTE: shares authors with Dahl et al. — not
  independent corroboration.
- **LegalCiteBench** (see Strand A) — MAR as a false-positive-grounding
  analogue. **SG-LegalCite** (arXiv:2605.21057) — Singapore case-principle
  retrieval, methodological reference for case-principle matching.
  **LegalCiteTrust** (arXiv:2607.20872, Chinese) — surfaced only, not
  verified **[not found in detail]**.
- **AbstentionBench** — Meta/FAIR 2025 (arXiv:2506.09038). 20 datasets, 6
  abstention scenarios (incl. **False Premise**, **Answer Unknown**,
  Underspecified Context). Key finding: reasoning fine-tuning WORSENS
  abstention by 24% on average. Not legal, but the canonical framework for
  our MDD track. No legal/civil-law-specific abstention work found
  **[not found]**.

**Strand B practices relevant to us**: three-way taxonomy maps onto our
narrative-citation counting (unidentifiable ⇒ ungrounded) and
resolved-but-off-issue (no credit, not fabricated); commercial RAG's 17-33%
hallucination empirically justifies fail-closed post-hoc validation; our
three-state design (grounded / no-credit-ambiguous / confirmed-fabrication)
has NO direct published precedent — a potentially original methodological
contribution to state explicitly, with MAR and Magesh et al. cited as
nearest concepts; frame MDD as selective prediction under
false-premise/missing-evidence (AbstentionBench vocabulary).

## Strand C — LLM-as-judge methodology

- **Zheng et al. 2023** (NeurIPS 2023 D&B, arXiv:2306.05685) — MT-Bench /
  Chatbot Arena. Documents position, verbosity, self-enhancement bias;
  GPT-4-judge >80% agreement with humans (≈ human-human). Mitigations now
  standard: position swapping, reference-guided grading.
- **Panickssery, Bowman, Feng** (NeurIPS 2024, arXiv:2404.13076) — judges
  recognize and favor their own generations; self-preference scales with
  self-recognition ability.
- **Family-enhancement bias** — same-family (not just same-model) favoring;
  magnitude large and dataset-dependent (arXiv:2604.22891 and follow-ups).
- **PoLL — "Replacing Judges with Juries"** (Cohere, arXiv:2404.18796) — a
  panel of smaller judges from DISJOINT families beats a single large
  judge on 3 settings/6 datasets, reduces intra-model bias, 7× cheaper.
  The benefit comes specifically from family diversity.
- **"Nine Judges, Two Effective Votes"** (Kohli, arXiv:2605.29800, 2026) —
  9 LLM judges from 7 families ≈ only ~2.2-2.5 effective independent votes
  (Kish n_eff); correlated errors put panels 8-22pp below the independent
  Condorcet bound; the single best judge matches or beats the panel.
  Direct evidence that observed agreement (κ) OVERSTATES reliability for
  correlated judges.
- **Human adjudication**: two-annotator + human tiebreak is standard
  annotation practice; auditing a sample of AGREEMENTS (not only
  disagreements) appears only in practitioner sources (Arize, Braintrust)
  — **weak precedent, no canonical peer-reviewed source [not found]**.
- **Grouped-criteria judging (halo effect)**: no direct study found of
  grouped vs per-criterion judging **[not found]** — our mitigation
  (criterion-order shuffling + separate written justification) is
  consistent with Zheng et al.'s principles but not validated by a
  dedicated study.
- Surveys: Gu et al. arXiv:2411.15594 (verified, detail not extracted);
  arXiv:2604.23178, arXiv:2606.13685 (existence only).

**Strand C practices relevant to us**: same-provider two-judge panel
(Sonnet+Opus) reduces but does NOT remove correlated error — the
literature's remedy is cross-family panels; correlated-judge κ inflation
makes the human audit of the agreement stratum load-bearing, and our
20-agreements audit matches emerging practitioner practice but has no
strong citable precedent; declare the grouped-judging halo mitigation as
unvalidated-by-literature.

## Strand D — Benchmark design methodology & statistics

- **BetterBench** — Reuel et al., NeurIPS 2024 spotlight (arXiv:2411.12990;
  betterbench.stanford.edu). 46-criterion lifecycle checklist; assessed 24
  benchmarks; "most benchmarks do not report statistical significance of
  their results nor allow for their results to be easily replicated."
  Exact lifecycle-stage labels not extracted **[not found]**.
- **HELM** — Liang et al., TMLR 2023 (arXiv:2211.09110). Multi-metric per
  scenario (7 metrics × 42 scenarios, 30 models); explicit anti-compositing
  rationale (paraphrase-level, not verbatim-quotable).
- **Raji, Denton, Bender, Hanna, Paullada** (NeurIPS 2021 D&B) — "Everything
  in the Whole Wide World" critique of composite/general benchmarks.
- **Bowman & Dahl** (NAACL 2021) — four criteria: validity, reliable
  annotation, statistical power, freedom from bias artifacts.
- **"Measuring what Matters: Construct Validity in LLM Benchmarks"**
  (NeurIPS 2025 D&B, arXiv:2511.04703) — review of 445 articles; most have
  construct-validity weaknesses; 27% used convenience sampling.
- **Contamination**: temporal-split evaluation is the standard mitigation
  but "Test of Time" (arXiv:2509.00072) shows the temporal signal is highly
  sensitive to how questions are constructed (LLM-generated vs cloze);
  detection is inherently probabilistic with undisclosed corpora
  (arXiv:2409.09927); SCOTUS memorization study (arXiv:2512.13654) is the
  closest legal analogue; nothing Cassazione-specific **[not found]**.
- **Small-N statistics**: bootstrap CIs (10k resamples, percentile) are
  standard; **McNemar's test** is the standard paired test for same-items
  binary outcomes across systems; paired/clustered bootstrap over per-item
  differences for the rest (no single canonical NLP citation
  **[not found]**).
- **Card, Henderson, Khandelwal, Jia, Mahowald, Jurafsky** (EMNLP 2020,
  "With Little Power Comes Great Responsibility") — NLP experiments are
  chronically underpowered; 20-30 item tracks detect only large effects.
  **NLPStatTest** (AACL 2020) — operational three-stage procedure
  (significance → effect size → power).
- **Pre-registration** (arXiv:2302.10086) — emerging, not yet standard;
  defends against HARKing/selective reporting.

**Strand D practices relevant to us**: paired tests across arms (same
tasks!) rather than independent per-arm CIs; report significance AND
enable replication (differentiator per BetterBench); declare the temporal
boundary AND its limits (cutoff alone does not settle recall-vs-reasoning
in the bare arm); run/report a power analysis or explicitly acknowledge
small-N limits; consider pre-registration of the hypotheses (the design
doc's committed expectations are already close — formalize); document that
task-generation style affects contamination-signal interpretability.

**Distilled checklist (BetterBench/HELM-class, 17 items)**:
1. Task selection reproducible, not convenience sampling. 2. Temporal/
contamination boundary declared vs model cutoffs. 3. Sensitivity of
contamination signal to task-generation style acknowledged. 4. CIs per
metric/track. 5. Paired tests for same-item multi-arm comparisons.
6. Power analysis or explicit small-N acknowledgment. 7. Replicability
(data, prompts, rubric published). 8. No composite when constructs
dissociate. 9. Constructs explicitly operationalized. 10. Scoring
reliability reported (κ + its caveats). 11. Statistical power addressed.
12. Bias in task/label construction checked. 13. Versioned benchmark
lifecycle. 14. Claims scoped to construct validity. 15. Analysis plan
fixed before results (or deviations disclosed). 16. Effect sizes beside
significance. 17. Enumerable, non-cherry-picked sampling frame.

## Strand E — Tool-augmented vs bare comparisons

- **τ-bench** (Yao et al., arXiv:2406.12045) — outcome-based agent grading;
  **pass^k** reliability metric: GPT-4o pass^8 <25% in retail — single-run
  arm comparisons are weak evidence. No bare-vs-tool ablation inside
  τ-bench itself.
- **SWE-bench critique line**: "The SWE-Bench Illusion" (arXiv:2506.12286)
  — 32.67% of successes had solution leakage in the task text; file-path
  memorization up to 76% for in-training repos. OpenAI's audit of
  SWE-bench Verified: 59.4% of examined "failures" were harness flaws.
  "Position: Coding Benchmarks Are Misaligned with Agentic SE"
  (arXiv:2606.17799) — end-to-end scores conflate model, harness,
  tool-scaffold, environment; harness choice is a confound co-equal with
  the model. Remediation: decontamination-by-freshness (SWE-bench Live,
  SWE-rebench arXiv:2505.20411).
- **ToolBench/ToolLLM, API-Bank** — absolute tool-use accuracy, no
  controlled tool-present/absent ablation with parity controls found in
  primary sources **[not found in primary]**.
- **RAG-fairness line** (MDPI 2078-2489/16/9/766; arXiv:2409.19804) —
  must-control list: same prompt template, temperature, decoding across
  arms; separate retrieval quality from generation quality; change one
  axis at a time.
- **Tool-count effects**: "Scaling Enterprise Agent Routing"
  (arXiv:2606.17519, weakly sourced numbers) — accuracy drops 7-85% as
  tool count grows (~50 tools: 84-95%; ~740: 0-20%). "Retrieval Models
  Aren't Tool-Savvy" (arXiv:2503.01763) — curated tool subsets are
  themselves unreliable (can miss relevant tools).
- **OPEN GAP**: no source addresses whether comparing two DIFFERENT tools
  (generic web search vs a specialized legal MCP) is a clean ablation or
  its own confound — genuinely open in the literature **[not found]**;
  state as such, do not cite around it.

**Strand E practices relevant to us**: consider pass^k / repeated runs per
arm (non-determinism is benchmark-verified); check task text for solution
leakage (builder + subject + judges are all Claude — SWE-bench's 32.67%
leakage mode transfers); prefer post-cutoff material where possible;
log failure modes at component level (tool-schema vs retrieval vs
reasoning), not only end-to-end pass/fail; state prompt/turn-cap/cwd
parity across arms explicitly (we already hold them constant — say so);
present the curated `normativa` profile as a documented trade-off, not a
neutral choice; declare the web-vs-MCP heterogeneous-tool confound as an
open methodological point.
