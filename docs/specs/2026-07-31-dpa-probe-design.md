# DPA probe — live determination of `dpa_proprio` — Design

- **Date**: 2026-07-31
- **Branch**: `feature/dpa-probe` (from `develop`)
- **Status**: Approved (design), pending implementation plan
- **Scope**: new lib `src/lib/dpa_probe/` + 1 new MCP tool
  `verifica_dpa_fornitore` in `src/tools/analisi_fornitori.py`. Rewrites step 4
  of the `analisi-fornitori` skill and deletes
  `plugin/skills/analisi-fornitori/references/dpa-whitelist.md`. The canonical
  supplier record contract and `genera_report_fornitori` are **unchanged**.

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
- Changing the canonical record contract or the Excel layout.
- Re-qualifying suppliers already analysed. Existing checkpoints stay valid.

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

**Supporting markers** (at least one required, distinct from the strong one):
any two of the art. 28(3) obligations — documented instructions, sub-processor
authorisation, assistance with data-subject rights, audit/inspection, deletion
or return of data at end of service.

A page scoring only "GDPR" or "trattamento dei dati" does **not** confirm. This
is the rule the Zucchetti privacy notice fails.

**Dedicated vs clause**: if the document's dominant subject is the DPA (title or
H1 matches a strong marker) → `dpa_dedicato`. If art. 28 markers appear inside a
document whose title indicates general terms (`condizioni generali`,
`termini e condizioni`, `terms and conditions`, `general conditions`) →
`clausola_in_condizioni`.

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
  is valid. This must yield `bloccato`, never a negative: a false negative would
  generate an unnecessary appointment, the worse of the two errors.

### PDFs

`pypdf` is **not** a declared dependency, and adding it would touch
`pyproject.toml`, `.mcp.json`, the Dockerfile and the `uv --with` command lines
documented across four setup paths. A PDF served on a conventional path and
named e.g. `data-processing-addendum.pdf` is already strong evidence. Decision:
accept PDFs on the basis of URL and `content-type`, flag the result as
`evidenza: "url"` rather than `"contenuto"`, and do not parse the file. No new
dependency.

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

The canonical record contract in `references/metodologia.md` does not change:
`dpa_proprio` keeps its three values, the evidence URL goes in the existing
`fonti`, the basis of the verdict in the existing `note`. Consequently
`genera_report_fornitori`, the Excel layout and all existing checkpoints remain
valid.

## Testing

Existing harness applies: `tests/unit/` with mocked HTTP, `@pytest.mark.live`
for real-server tests, already excluded by `addopts = "-m 'not live'"`.

**Fixtures must be trimmed copies of real pages, not synthetic HTML.**
Hand-written fixtures encode the author's assumption of what those pages look
like — precisely the assumption that failed. The value of the Zucchetti case is
that it is an *observed* failure.

| Fixture | Expected verdict | Why it is there |
|---|---|---|
| Zucchetti website privacy notice | no confirmation | The incident that motivated this design |
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
