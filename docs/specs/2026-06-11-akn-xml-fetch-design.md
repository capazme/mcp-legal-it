# AKN XML fetch for Normattiva — Design

- **Date**: 2026-06-11
- **Branch**: `feature/akn-xml-fetch` (from `develop`)
- **Status**: Approved (design), pending implementation plan
- **Scope**: Normattiva only. EUR-Lex and Brocardi paths are untouched.

## Problem

The current Normattiva fetch (`src/lib/visualex/scraper.py`) scrapes rendered HTML
and extracts article text with four cascading heuristics
(`_normattiva_akn_detailed` → `_simple` → `_attachment` → `_fallback`). This is
fragile to layout changes, produces text with modification markers to clean by
regex (`(( ))`), and for full text issues one AJAX request per article.

Normattiva exposes the official **Akoma Ntoso 3.0 XML** export behind the
`caricaAKN` endpoint (the "Esporta XML" button). It returns the whole act in one
request with deterministic structure: every article is `<article eId="art_N">`,
every comma `art_N__para_M`, every letter `__point_a`, modifications marked with
`<ins>`/`<del>`, and native multivigenza via the `dataVigenza` parameter.

## Goal & success criteria (binding)

Merge to `main` only if the benchmark shows **real value**. The user set three
binding criteria:

1. **No latency regression on the single-article hot path.** `cite_law` on a
   single article (e.g. `art. 2043 c.c.`) must be ≤ current HTML latency.
2. **Clear full-text advantage.** Whole-act retrieval must be clearly
   faster/more reliable than today's N AJAX calls.
3. **More structure and better formatting.** Output must preserve articles,
   commi, lettere, headings — not flat text with modification cruft.

Reliability gains (bis articles, allegati, old acts) are a welcome bonus but are
**not** the primary gate.

## Recon findings (2026-06-11, measured against live Normattiva)

The design below is grounded in measurements, not assumptions. Key findings that
**changed the original plan**:

1. **`caricaAKN` requires an act-specific session cookie.** Calling it cold (or
   with a session from the homepage / search page) returns a 32254-byte error
   page. The session must be established by first GETting the act's landing page.
   A generic reusable session does **not** work. → AKN is **always 2 requests
   cold** (landing → caricaAKN).
2. **No per-article XML export exists.** `caricaAKN` returns the *whole act*.
   (`caricaArticolo` returns single-article *HTML*, which is what the current
   full-text walker already uses.)
3. **Two distinct AKN structures.** Flat acts (laws, decrees, Costituzione) put
   articles directly as `<article eId="art_N">` under the body. Large codici
   (c.c., c.p.) use the **multi-component** form: each article is a `<doc>` inside
   an `<attachment>` (3280 components in the c.c.). The parser MUST handle both.
4. **Size.** c.c. = 10.6 MB, c.p. = 4.1 MB, D.Lgs 152/2006 = 6.3 MB of XML.
5. **Latency reality** (cold, 2-request AKN whole-act vs current 1-request HTML
   single-article):

   | Act | HTML 1 art. | AKN whole-act (2 req) | Size |
   |-----|------------:|----------------------:|-----:|
   | c.c. art 2043 | 1964 ms | 1881 ms | 10.6 MB |
   | c.p. art 575 | 1242 ms | 1061 ms | 4.1 MB |
   | L.241 art 3 | 755 ms | 706 ms | 0.3 MB |
   | D.Lgs 152 art 1 | 1215 ms | 1223 ms | 6.3 MB |

   AKN is at **parity or faster even cold**, because the landing-page load is the
   shared bottleneck (~1.5–2 s for codici) and the caricaAKN download adds only
   84–319 ms on top. Warm (cached) it is effectively instant.

## Consequences for the design

- **Precomputed codici params are DROPPED.** Since the session forces a landing-
  page fetch anyway, and that page already contains `codiceRedazionale` +
  `dataGU`, precomputing them saves nothing. Removed from scope.
- **Criterion 1 is met without tricks**: cold parity + warm win.
- **The valuable cache is the parsed-act cache** (in-memory LRU + optional on-disk
  persistence), keyed by `(codiceRedaz, dataGU, dataVigenza)`. On-disk persistence
  matters most for the giant codici (avoid re-downloading 10 MB across restarts);
  keying by `dataVigenza` (defaults to today) gives natural daily expiry.

## Architecture (Approach A — AKN-first hybrid)

### New: `src/lib/visualex/akn_fetch.py` (network layer)
- `async fetch_act_akn(norma) -> dict | None`: the core fetch. Steps:
  1. GET the act landing page (`norma.url()`, no article) → establishes the
     act-specific session **and** yields `codiceRedazionale` + `dataGU` (from the
     `caricaAKN` href / `eli:id_local` meta).
  2. GET `caricaAKN?dataGU=&codiceRedaz=&dataVigenza=` on the **same client**
     (session reused) → whole-act AKN XML.
  3. Validate (`<?xml` prefix + contains `<article`/`<doc>`), parse, return the
     parsed act. Return `None` on any failure → caller falls back to HTML.
- `dataVigenza` defaults to today (`YYYYMMDD`); overridable for historical reads.

### New: `src/lib/visualex/akn_parser.py` (pure, no network)
- `parse_akn(xml: str) -> ParsedAct`: XML → structured act. Pure function,
  fully unit-testable against committed fixtures.
- Handles **both** structures: flat `<article eId="art_N">` under the body, and
  the multi-component form (each article a `<doc>` inside `<attachment>`).
- `ParsedAct.article(eid) -> markdown` and `ParsedAct.full_text() -> markdown`.
- Renders `<num>`/`<heading>`/`<paragraph>`/`<content>`/`<point>` into clean
  markdown; resolves `<ins>`/`<del>` to vigente text; normalizes `art_N-bis`.

### New: parsed-act cache (in `akn_fetch.py`)
- In-memory **LRU** keyed by `(codiceRedaz, dataGU, dataVigenza)` → `ParsedAct`.
  Bounded by `AKN_CACHE_MAX_ACTS` (default 50). After the first fetch, every
  further article and the full text of that act cost **0 requests**.
- **Optional on-disk persistence** of parsed acts under
  `${MCP_CACHE_DIR or ~/.cache/mcp-legal-it}/akn_acts/`, so the 10 MB codici are
  not re-downloaded across process restarts. Keyed by the same tuple →
  `dataVigenza=today` gives natural daily expiry.
- A persisted **hit counter** (`akn_hits.json`) records access frequency; its
  ranking reveals the most-consulted laws (user's discovery-via-cache idea) and
  feeds optional startup pre-warming.

### Changed: `src/lib/visualex/scraper.py`
- `fetch_article(nv)` becomes a thin router for the Normattiva branch: call
  `fetch_act_akn(norma)` (cache-aware), then `ParsedAct.article(eid)`; on
  `None`/exception/missing-article, fall back to the existing
  `_extract_normattiva_article` path. **Signature unchanged.**
- `fetch_normattiva_full_text(norma)` similarly tries the AKN path
  (`fetch_act_akn` → `ParsedAct.full_text()`) first, falls back to the current
  AJAX walker.
- The EUR-Lex branch is untouched. `source` is `"normattiva-akn"` on the AKN path,
  `"normattiva"` on the HTML fallback.

### Fallback triggers (AKN → HTML)
- No `caricaAKN` link / params not resolvable
- HTTP error or non-XML response from `caricaAKN`
- Empty/malformed XML, or requested article eId absent
- Any parser exception

The current HTML path stays fully intact as the safety net. No tool signatures
change; `source` distinguishes `"normattiva"` (HTML) vs `"normattiva-akn"`.

## Benchmark harness: `benchmarks/akn_vs_html.py`

Measures **3 access patterns × {HTML, AKN} × {cold, warm}**:

1. Single article, scattered (cold cache each call)
2. Multiple articles, same act (AKN warm after first)
3. Full text, whole act

Metrics per cell: latency (median, p95), HTTP request count, success rate
(non-empty text), char count, article count, plus a text dump for eyeball review
of formatting fidelity. Output: a markdown table + raw JSON.

### Proposed corpus (user-adjustable)
- Codici: `c.c.` (art. 2043; art. 1; partial full-text), `c.p.` (art. 575),
  `Cost.` (art. 117)
- Leggi: `L. 241/1990` (art. 3; full-text); `art. 2-bis L. 241/1990` (bis stress)
- Decreti: `D.Lgs. 231/2001` (art. 6); `D.Lgs. 196/2003`; `D.Lgs. 152/2006`
  (large, full-text stress)
- Allegati: an act/codice with allegato
- Edge: a pre-1950 act to exercise the HTML fallback (expected AKN miss)

## Testing

- `tests/unit/test_akn_parser.py`: pure XML → markdown conversion against
  committed fixtures — flat (`legge_241_1990.xml`, `costituzione.xml`,
  `dlgs_231_2001.xml`) and component (`codice_civile.xml`, `codice_penale.xml`),
  plus a bis-heavy article (art. 2-bis L.241) and an allegato. Asserts article
  count, presence of specific article text, comma/lettera structure.
- `tests/unit/test_akn_fetch.py`: cache behaviour (LRU eviction, hit counter,
  on-disk round-trip), param extraction from a saved landing-page fixture, and
  fallback routing (mocked AKN failure → HTML path invoked). Network mocked.
- Fixtures already captured from real `caricaAKN` responses live in
  `tests/fixtures/akn/`; no live calls in unit tests.
- `@pytest.mark.live` for a couple of end-to-end fetches.
- The full existing suite (2000 tests) must stay green.

## Environment note

The repo `.venv` points to Python 3.9, but the code requires 3.10+
(`dict | None` syntax). For local benchmarking/testing, recreate the venv with
Homebrew Python 3.12. (Docker already runs 3.10+.) Out of scope to "fix" beyond
recreating the local venv.

## Decision gate

Run the benchmark on `develop`'s current HTML implementation, then on the AKN
branch. Merge to `main` only if criteria 1–3 hold on the numbers. If AKN wins on
full-text + structure but the non-codice cold single-article case regresses, the
fallback path B (AKN for full-text only) is the documented retreat.

## Out of scope

- EUR-Lex and Brocardi (unchanged)
- The OpenData bulk API (`api.normattiva.it/.../bff-opendata`) — wrong tool for
  per-article access
- Regional legislation (`normattiva.it/mfr/`)
