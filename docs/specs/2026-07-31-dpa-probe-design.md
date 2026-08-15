# DPA probe — live determination of `dpa_proprio` — Design

- **Date**: 2026-07-31
- **Branch**: `feature/dpa-probe` (from `develop`)
- **Status**: Approved (design), pending implementation plan
- **Scope**: new lib `src/lib/dpa_probe/` + 1 new MCP tool
  `verifica_dpa_fornitore` in `src/tools/analisi_fornitori.py`. Rewrites step 4
  of the `analisi-fornitori` skill and deletes
  `plugin/skills/analisi-fornitori/references/dpa-whitelist.md`.

> **Amendment 2026-07-31** — a second defect surfaced from the same real run and
> is folded into this spec: see [Class-consistency check](#class-consistency-check).
> It adds one required field to the canonical record, so the original claim that
> the record contract is untouched no longer holds. Everything about the DPA
> probe below is unaffected.

## Problem

`dpa_proprio` is currently decided by a hand-maintained markdown table of ~20
vendors (`references/dpa-whitelist.md`), injected verbatim into the model's
context. The table has three structural defects:

1. **It never expires.** Nothing in the pipeline re-checks it, so a wrong entry
   stays authoritative indefinitely.
2. **It can assert something false without any signal.** Verified on
   2026-07-31: the Zucchetti entry pointed at Zucchetti's *own website privacy
   notice*, and the TeamSystem entry at a hub that redirected to a **product
   page**. Both claimed "this vendor publishes a DPA". An analyst following the
   list would set `dpa_proprio: "si"` and **skip a required art. 28
   appointment**. Two further entries were dead (Aruba 404, PayPal 404) and two
   permanently redirected (Salesforce, Zoom).
3. **It does not scale past the listed vendors.** Every supplier outside the
   table already falls through to an expensive targeted web search. In the real
   Stand out run (296 suppliers, 68 processors) the session's web-search budget
   was exhausted at 200/200 *with* the whitelist covering the large vendors.

A live check also matches an existing precedent in this codebase: VAT numbers
are not kept in a table, they are verified against VIES at analysis time.

## Goals

- Decide `dpa_proprio` from evidence fetched at analysis time, not from curated
  data.
- Keep the cost below the web-search budget that the current design already
  exceeds.
- Make a confirmation **earned**: a page that merely discusses GDPR must not
  produce `si`.
- Make every stored determination carry a date and expire on its own.

## Non-goals

- Deciding whether a published DPA is actually incorporated into *this client's*
  contract. That is a contractual question the mastrino cannot answer; it stays
  a caveat in the report's Avvertenze sheet.
- Changing the Excel layout.
- Re-qualifying suppliers already analysed. Existing checkpoints keep their
  qualifications; they need only the backfill described under the
  class-consistency check.

## Class-consistency check

*Added 2026-07-31, from the same Stand out run.*

### Problem

Parallel mode splits suppliers into blocks of ~15, each analysed by an
independent subagent that cannot see the others. Suppliers of the **same kind**
therefore get qualified by different agents with no reconciliation. Observed:
16 INPGI journalists came back 11 `fuori_perimetro` and 5 `titolare_autonomo` —
and the split tracked *which block processed them*, not any difference in the
suppliers. It took a manual audit of the merged set to notice.

The existing merge guardrails do not catch this: they check confidence
calibration and contract shape, both of which every one of those records passed.
An incoherent set can be perfectly well-formed.

### Design

Each record declares `classe_attivita`: a short lowercase label for the kind of
supplier it is (`giornalista`, `social media manager`, `ristorazione`,
`hosting/cloud`, …). `genera_report_fornitori` groups records by that label and
**refuses to write the file** when one class carries more than one
`qualificazione`, listing the class, the conflicting values and the suppliers on
each side.

This lands in the tool, not in the skill's prose, for the same reason the DPA
whitelist was replaced: a rule the model is asked to remember is a rule that
eventually goes unremembered. The tool already does collect-all validation and
rejects the whole batch on error — this is one more rule in that pass, and it
fails at the loudest available moment: no report until the incoherence is
resolved.

The field is **required**. An optional field the model forgets to populate makes
the check silently vacuous, which is the failure mode being removed. The
resolution when it fires is to **align the qualifications** across the class;
splitting the class is allowed only when those suppliers really do render
different services, never to make the validation pass. The error message ranks
the two accordingly — offering them as equals invites a model under pressure to
produce the file to take the cheaper one.

#### Synonym labels *(amended 2026-07-31 after whole-branch review)*

Classes collide on **exact string equality** (lowercased, whitespace collapsed).
The review reproduced the original incident straight through the check: with
labels `giornalista` and `giornalista freelance` the incoherent set is two
classes, each internally consistent, and the report is written.

This is not fixed in Python. A controlled vocabulary would have to enumerate
every kind of supplier an Italian ledger can contain, and fuzzy matching would
merge classes that are genuinely distinct — both trade a visible failure for a
silent one. It is fixed in the skill's process, at the two points where the
labels are produced and merged:

- the parallel-mode subagent prompt carries the list of `classe_attivita`
  labels already emitted by earlier blocks and binds each block to reuse them
  verbatim, coining a new label only for a kind no existing label covers.
  Blocks are dispatched in waves so the list can propagate;
- the merge guardrail requires synonym labels to be reconciled onto a single
  label **before** `genera_report_fornitori` is called — the merge is the only
  point at which the divergence is visible at all.

The tool keeps exact-string comparison and says so in its argument
documentation: it is the last line of defence, not the first.

### Consequence

Records produced before this change lack the field and will fail validation. The
Stand out checkpoint (296 records) needs a one-off backfill before its report can
be regenerated. This is deliberate: the alternative is a check that reports
"0 conflicts" on data it never actually examined.

## Architecture

The supplier's domain is **already a by-product of work the skill performs**:
Fase 3 step 2 requires the model to find the official website and cite it in
`fonti`. Today that domain is used for identification and discarded. It becomes
the probe's input at no additional cost.

```
Fase 3 step 2  →  official site (already searched, already cited in `fonti`)
                        │
                        ▼
        verifica_dpa_fornitore(dominio)          ← new tool, HTTP only
                        │
      ┌─────────────────┼──────────────────┬───────────────┐
      ▼                 ▼                  ▼               ▼
 dpa_dedicato   clausola_in_condizioni  non_trovato   bloccato /
      │                 │                  │        dominio_irraggiungibile
      │                 │                  └───────┬───────┘
      │                 │                          ▼
      │                 │              model's targeted search  ← cost paid only here
      ▼                 ▼                          ▼
                  mapping → dpa_proprio
```

### Components

| Component | Responsibility |
|---|---|
| `src/lib/dpa_probe/client.py` | Probe conventional paths, fetch, judge content. Knows URL conventions, **no vendor names**. |
| `src/lib/dpa_probe/cache.py` | On-disk cache of determinations, TTL-bounded. |
| `verifica_dpa_fornitore(dominio, nome_fornitore="")` | MCP tool wrapper, sibling of `verifica_partita_iva_vies`. |
| skill Fase 3 step 4 | Maps the verdict onto `dpa_proprio`, falls back to search. |

Probed paths (ordered, stop at first confirmation): `/legal/dpa`, `/dpa`,
`/legal/data-processing-addendum`, `/legal/data-processing`, `/privacy/dpa`,
`/legal/terms/dataprocessing`, `/trust/gdpr`, `/gdpr`. This is a list of
*conventions*, which ages far more slowly than a list of individual links.

## Verdicts and mapping

The probe returns a verdict, not a boolean:

| Verdict | Meaning | → `dpa_proprio` |
|---|---|---|
| `dpa_dedicato` | Standalone DPA document found | `si` |
| `clausola_in_condizioni` | Art. 28 designation lives **inside** general service conditions | `si` + **mandatory** note that coverage depends on the service actually purchased |
| `non_trovato` | Nothing on conventional paths | hand off to search; if search also fails, apply the fallback rule below |
| `bloccato` | Anti-bot block (non-browser client refused) | hand off to search; if unresolved → `da_verificare` |
| `dominio_irraggiungibile` | Network failure / DNS / timeout | hand off to search; if unresolved → `da_verificare` |

`clausola_in_condizioni` exists because of a real case: Aruba publishes **no
standalone DPA at all** — the appointment is art. 21 of Section I of the Aruba
Cloud general conditions. Collapsing that into a plain `si` is what produced the
misleading whitelist note.

The tool response also carries `url_evidenza`, `marcatori` (which markers
matched), `evidenza` (`"contenuto"` or `"url"`) and `verificato_il`.

## Judging rules

A confirmation requires markers of **processor designation**, not of privacy as
a topic.

**Strong markers** (at least one required):
- explicit reference to art. 28 (or to 2016/679 in combination with
  `responsabile` / `processor`);
- `data processing agreement`, `data processing addendum`,
  `data protection addendum`, `designazione a responsabile`,
  `nomina a responsabile` — in `<title>` or a heading element.

**Supporting markers**: the art. 28(3) obligations — documented instructions,
sub-processor authorisation, assistance with data-subject rights,
audit/inspection, deletion or return of data at end of service.

A page scoring only "GDPR" or "trattamento dei dati" does **not** confirm. This
is the rule the Zucchetti privacy notice fails.

**Proximity and anchoring** *(amended 2026-07-31 after review)*. Counting one
strong plus one supporting marker anywhere in the page is too weak: review
demonstrated that a generic "about us" page reading *"non ricorre mai a un
sub-processor … vedi anche l'art. 28 del nostro regolamento interno aziendale"*
would confirm as a dedicated DPA. Two constraints close it:

1. **`art. 28` counts as strong only in GDPR context** — within 60 characters of
   `GDPR`, `2016/679`, or `regolamento` qualified as `(UE)` / `europeo` /
   `generale`. An article 28 of some other instrument is not evidence.
2. **The strong and supporting markers must co-occur**, either in the same
   two-sentence window of the body, or with the strong marker in the page's
   title/heading and the support anywhere in the body. A designation states its
   obligations next to its designation; scattered keywords do not.

**Direction of the designation** *(amended 2026-07-31 after whole-branch
review)*. The markers above establish that *a designation sentence exists*, not
*who designates whom*. A privacy notice says "I appoint my suppliers"; a DPA
says "the client appoints me". Same vocabulary, opposite direction, and the
direction is the only thing that matters legally — the review reproduced
`dpa_dedicato` on an idiomatic art. 13 informativa, on a cookie policy and on a
blog post. Two rules close it:

1. **Negative gate: is this an art. 13/14 notice?** Decided from the **body**,
   *(amended again 2026-07-31 after re-review)*. The first version enumerated
   headings, and failed the way every enumeration fails: of 17 realistic
   own-notice titles, 12 were not on the list — `Trattamento dei dati
   personali`, `Tutela della privacy`, `Protezione dei dati personali`,
   `Data Protection Policy`, `Dati personali`, a page with no `<title>` at all —
   and each confirmed as `dpa_dedicato` when served from a conventional DPA
   path, then cached for 90 days. A longer denylist is the whitelist mistake at
   a larger size.

   The gate now matches what an art. 13/14 notice **is**, by its content
   obligations, which a DPA has no reason to carry:

   - a reference to `art. 13` / `art. 14` (`art.`, `artt.`, `articolo`,
     `articoli`; both numbers);
   - the right to lodge a complaint — `reclamo al Garante`,
     `reclamo all'Autorità`, `diritto di proporre/presentare reclamo`;
   - `base giuridica` or `legittimo interesse`.

   **Two of the three** are required. One alone is not proof: a DPA annex may
   legitimately state the lawful basis of the processing it governs, and a DPA
   may cross-reference the controller's art. 13 duty. Measured on the fixtures:
   3/3 on the real informativa, **0/3** on each of HubSpot, Atlassian, Aruba,
   TeamSystem and Zucchetti — a full point of margin.

   The heading list is retained as a **second, independent route into the same
   gate** (a union, not a conjunction): it still catches a short notice whose
   body carries only one signal. The body signature carries the rule.

   **The body signature is absolute; only the heading backstop is exemptable**
   *(corrected 2026-07-31 — the first attempt at this exemption was a
   regression)*. The heading branch reads the first eight h1/h2 elements, which
   on a real vendor page are mega-menu and footer items: without an exemption, a
   document titled `Data Processing Agreement` was refused because
   `Privacy Policy` appeared in its navigation. So **that branch, and only that
   branch, yields to a strong marker in the `<title>`.**

   Extending the exemption to the whole gate — as the first attempt did —
   reopens the module's core failure in its more probable direction, because a
   title is not just unreliable, it is **chosen**. An own notice can put a
   strong marker in its own title and thereby exempt itself from the body
   signature:

   | `<title>` (body = a real art. 13 notice, 3/3 on the signature) | with whole-gate exemption |
   |---|---|
   | `Atto di nomina a responsabile del trattamento` | `dpa_dedicato` |
   | `Informativa privacy e nomina a responsabile dei fornitori` | `dpa_dedicato` |
   | `Informativa sul trattamento dei dati ex art. 28 GDPR` | `dpa_dedicato` |

   The first is the ordinary designation letter a controller publishes **toward
   its own suppliers** — routine on Italian public-sector and healthcare sites,
   and exactly the inverted direction this gate exists to refuse. Worse, the
   strong marker in the title also satisfies the anchoring rule, so these
   confirm with **no URL at all**, from any of the eight probed paths.

   The invariant to preserve: *what a document does* (body) cannot be overridden
   by *what it calls itself* (title). The regression test is written as that
   property over titles chosen to defeat the exemption — deliberately not as a
   list of titles known to be safe, which would be the denylist mistake moved up
   one level.
2. **Anchoring.** `dpa_dedicato` requires the document to be *about* the
   designation, not merely to contain one: a strong marker in the
   title/h1/h2, **or** a final URL matching the conventional DPA forms
   (`/dpa` as a whole path segment, `data-processing-agreement|addendum`,
   `data-protection-addendum`). Body-only co-occurrence under a generic
   heading yields `non_trovato`.

The gate outranks the anchor: a CMS that answers an unknown `/privacy/dpa` with
its own privacy notice passes the host check, `_PATH_LEGALE` and the soft-404
fingerprint, so the URL alone must never be allowed to confirm — the cache
would then freeze the false positive for 90 days, which is exactly the
whitelist's fatal property rebuilt.

A false confirmation is the error to avoid: it makes an analyst skip a required
appointment. `non_trovato` costs one targeted search, and the fallback rule
below still applies.

**Dedicated vs clause**: if the document's dominant subject is the DPA (title or
H1 matches a strong marker) → `dpa_dedicato`. If art. 28 markers appear inside a
document whose title indicates general terms (`condizioni generali`,
`termini e condizioni`, `terms and conditions`, `general conditions`) →
`clausola_in_condizioni`. The **title** decides which of the two wins: a
`Nomina a responsabile` section heading inside a terms page does not promote the
whole document to a standalone DPA, since collapsing the two loses the caveat
that coverage depends on the service actually purchased (the Aruba case).

The judge therefore takes the final URL as an optional second argument —
`giudica_html(html: str, url: str = "") -> Giudizio`. It stays optional so that
every existing call site remains valid; without it, a heading marker is the only
route to `dpa_dedicato`.

### Traps to neutralise

All three were observed on 2026-07-31 while auditing the existing whitelist.

- **Soft-404** — TeamSystem's `/legal` returned HTTP 200 while landing on a
  product page. Before probing, request a deliberately absent path
  (`/__dpa_probe_404__`) and fingerprint the domain's error page; any probe
  whose body matches that fingerprint is a disguised 404. Costs one request per
  domain.
- **Redirect away** — if the final URL changes host, or the final path no longer
  resembles a legal path, downgrade instead of accepting.
- **Anti-bot block** — Meta returns 400 to non-browser clients although the page
  is valid. This must yield `bloccato`, never a negative: the probe **did not
  see the page**, and must not assert an absence it never verified. `bloccato`
  says "unknown, go and look"; `non_trovato` says "I looked and there was
  nothing", which here would be a claim the tool has no basis for.

  *This is not a ranking of the two error types.* An earlier draft justified the
  rule by calling a false negative "the worse of the two errors", which
  contradicts §Problem and §Judging rules and could be read as licence to
  reorder the judging gates. The ranking is settled in §Judging rules and is the
  other way round: **a false confirmation is the error to avoid**, because it
  suppresses a legally required appointment, whereas a false negative costs one
  targeted web search.

### PDFs

`pypdf` is **not** a declared dependency, and adding it would touch
`pyproject.toml`, `.mcp.json`, the Dockerfile and the `uv --with` command lines
documented across four setup paths. A PDF served on a conventional path and
named e.g. `data-processing-addendum.pdf` is already strong evidence. Decision:
accept PDFs on the basis of URL and `content-type`, flag the result as
`evidenza: "url"` rather than `"contenuto"`, and do not parse the file. No new
dependency.

**The PDF branch keeps the narrow URL rule** *(amended 2026-07-31 after
re-review)*. The HTML anchor was widened to recognise `/dpa` as a whole path
segment; applying the same pattern here made `/legal/dpa`, `/dpa` and
`/privacy/dpa` confirm a PDF on the path alone. That is not what this rule was
justified by: the argument above rests on the file being **named** after a DPA,
and a bare `/privacy/dpa` names nothing — it is the exact path of the C1 CMS
trap. The two branches are not symmetric: on the HTML side the URL only breaks a
tie between markers that have already passed four content gates, while here it
*is* the whole verdict, with no direction gate and no content check, because the
document is never read. `giudica_pdf` therefore matches
`data-processing-agreement|addendum`, `data-protection-addendum`, and `dpa` only
when followed by `-`, `_` or `.` (`/dpa.pdf`, `/dpa-en.pdf`).

`data-protection-addendum` was missing from the restored pattern and has been
**added** rather than struck from this paragraph: it is a *named* form — the
same phrase is already a `titolo_dpa` strong marker — so it fits the
justification above exactly and cannot match a bare path. Omitting it was a
plain false negative. Each accepted and each refused form is pinned by a
parametrised test.

## Cache

- Location: `~/.cache/mcp-legal-it/dpa_probe.json`, honouring `MCP_CACHE_DIR`
  (same convention as the existing Brocardi URL cache).
- Key: normalised domain (lowercased, `www.` stripped).
- Value: `{verdetto, url_evidenza, marcatori, evidenza, verificato_il}`.
- TTL: 90 days. Expired entries are re-probed.

**Failures are never cached.** Only determinations (`dpa_dedicato`,
`clausola_in_condizioni`, `non_trovato`) are written. `bloccato` and
`dominio_irraggiungibile` are transient and must not be frozen — caching them
would recreate the whitelist's defect through the back door.

## Error handling and cost

The probe stops at the first confirmation and tries at most the listed paths,
reusing `retry_request` from `src/lib/_http`. Worst case is roughly ten HTTP
requests per domain — orders of magnitude cheaper than one web search, which is
why the hybrid stays within budget. The tool never returns a bare boolean:
always verdict plus evidence plus date.

## Skill changes

Two edits only:

1. **Fase 3 step 4** of `SKILL.md` — replaces "consult
   `references/dpa-whitelist.md`" with "call `verifica_dpa_fornitore` with the
   domain found at step 2; on `non_trovato` / `bloccato` /
   `dominio_irraggiungibile`, run the targeted search as today".
2. **Parallel-mode prompt** — drops the `WHITELIST DPA: {...}` block, gains the
   tool instruction.

`references/dpa-whitelist.md` is deleted. **Its closing fallback rule must be
preserved**, moved verbatim into step 4 of `SKILL.md`, or deleting the file
silently drops it:

> Local SME / vendor with no published DPA → almost always `dpa_proprio: "no"`
> (the controller's appointment is needed, tool `genera_dpa`). When in doubt:
> `da_verificare`.

The same guard note added to the whitelist on 2026-07-31 also moves to step 4: a
page discussing GDPR is not a DPA — `si` requires a contractual text designating
the vendor as processor under art. 28.

The DPA work alone leaves the canonical record contract in
`references/metodologia.md` untouched: `dpa_proprio` keeps its three values, the
evidence URL goes in the existing `fonti`, the basis of the verdict in the
existing `note`. The class-consistency check is what adds `classe_attivita` to
the contract; the Excel layout stays as it is either way.

## Testing

Existing harness applies: `tests/unit/` with mocked HTTP, `@pytest.mark.live`
for real-server tests, already excluded by `addopts = "-m 'not live'"`.

**Fixtures must be trimmed copies of real pages, not synthetic HTML.**
Hand-written fixtures encode the author's assumption of what those pages look
like — precisely the assumption that failed. The value of the Zucchetti case is
that it is an *observed* failure.

A negative fixture that contains **no markers at all** proves nothing: it would
pass against an arbitrarily permissive judge. At least one negative must carry a
genuine strong marker *and* a supporting duty, and be rejected on direction
rather than on absence.

| Fixture | Expected verdict | Why it is there |
|---|---|---|
| Zucchetti website privacy notice | no confirmation | The incident that motivated this design |
| Italian art. 13 informativa appointing its own suppliers | no confirmation | Real page, real `art. 28` strong marker, inverted direction |
| TeamSystem `/legal` product page | no confirmation | Soft-404 behind HTTP 200 |
| Aruba Cloud general conditions | `clausola_in_condizioni` | Appointment at art. 21, no standalone DPA |
| HubSpot / Atlassian / LinkedIn DPA | `dpa_dedicato` | True positives |
| Meta, HTTP 400 to non-browser client | `bloccato` | Must never be a false negative |

Two invariants carry more weight than the functional cases:

- **failures are not cached** — simulate timeout and anti-bot block, assert the
  cache file is untouched;
- **the TTL expires** — an entry dated 91 days ago must be re-probed.

A few `@pytest.mark.live` tests against two or three real vendors act as a
canary on URL conventions, kept out of the default suite so a vendor's site
redesign does not break CI.

## Known limitations

- No test can prove the *legal* conclusion is right. The tests prove the probe
  behaves as specified. Whether a discovered DPA is actually incorporated into
  the client's contract is outside automation and stays in the Avvertenze
  sheet — see Non-goals.
- Vendors publishing their DPA on a different top-level domain from their main
  site (verified case: Zucchetti's DPA is on `zucchetti.com` while the Italian
  site is `zucchetti.it`) will not be found by domain probing. They fall to the
  search path on first encounter and are then served from cache for 90 days.
- Vendors with no public DPA and no reachable site yield `da_verificare`, which
  is the correct outcome: unknown, not absent.
