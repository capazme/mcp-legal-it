# VisuaLex → mcp-legal-it: inventory of the readers

Status: **inventory, for review before any code moves.** Nothing here is implemented.

- **VisuaLex (VX)**: `capazme/VisuaLexAPI`, `develop` at `eca698dc` (includes PR #252 one download
  per tree page, #255 Retry-After «not before» per source, #257 Normattiva index in the shared
  client). Paths are relative to `services/visualex/visualex_api/` unless they start with `tests/`
  (`services/visualex/tests/`).
- **mcp-legal-it (MLI)**: `feature/robustness-fixes` at `5fb615f` (stacks the rename, the tags and
  Brocardi switch, the `api`/`core` module and the robustness audit). Paths are relative to
  `plugin/server/mcp_legal_it/`; tests are in `tests/unit/`.
- Method: every row was read on both sides; the claims marked *measured* were run offline on the
  same fixtures through both implementations (no request to any source). VX timings are PR #252's
  cold run on a development Mac; MLI was not timed live, its request counts are read from the code.

## The rule that is not a choice

VisuaLex's `article_text` and its decision texts are a data contract: highlights and notes are
anchored by character offset in a projection of the text, and the renderer drops an anchor in
silence when one character moves. So for **article text** (Normattiva HTML channel, EUR-Lex) and
**decision text** (Cassazione, Corte costituzionale, CGUE, administrative courts) VisuaLex's
output wins **byte for byte**, as a rule. Where a row below says «VisuaLex (frozen)», that is why.
MLI's own presentation (truncation, `da_carattere` paging, Markdown) is rebuilt on top of the
frozen text as an MCP layer, never by changing the text.

## Summary of choices

| Area | Choice |
|---|---|
| Network: client, retries, limits | merge (VX rules on MLI's httpx `core/_http`) |
| Retry-After «not before» | VisuaLex |
| Per-source timeouts and concurrency | merge |
| Circuit breaker | VisuaLex, opt-in and fixed |
| Egress allowlist | merge (runtime hook on every request, redirects included) |
| Italgiure TLS | merge (MLI file and tests + VX runtime pin) |
| SSRF guards on caller URLs | mcp-legal-it |
| Cache injection | mcp-legal-it contract, VX pruning and atomic writes |
| User-Agent | VisuaLex (one honest UA), after live checks |
| Playwright | mcp-legal-it (no browser in the engine) — **open question Q1** |
| Normattiva HTML article text | VisuaLex (frozen) |
| Article fetch order / channel | merge: `canale="html"` = VX, `canale="akn"` = MLI |
| AKN fetch and cache | merge |
| AKN parser | merge (VX base + MLI annex fixes; tables missing on both) |
| Article keys and suffixes | merge (VX table + MLI spelling equivalence) |
| Act index, tree, rubriche | VisuaLex |
| Missing-article guard | merge (VX pre-check + MLI post-check) |
| Annexes | merge |
| Full act text | mcp-legal-it |
| Law PDF | mcp-legal-it |
| Page and disk caches | merge |
| Act dates (year-only acts) | VisuaLex + MLI «no placeholder as identity» |
| Validity (vigenza) | VisuaLex |
| URN and norm model | merge (VX `generate_urn`/`sources.py`, MLI annex syntax and wire shape) |
| Act names and aliases | merge (VX tables, MLI live gates and treaty CELEX) |
| `normalize_act_type` | VisuaLex |
| NL query parser | merge, VX as base |
| EU act year/number | VisuaLex |
| Article lists and ranges | VisuaLex |
| Citation linker (prose) | VisuaLex after a regex fix; MLI list splitter stays |
| Decision citation parser | VisuaLex + MLI «N del AAAA» |
| EUR-Lex article text | VisuaLex (frozen), fetch channel per Q1 |
| Treaties | merge (CELLAR) |
| Recitals | VisuaLex |
| Consolidated EU texts | VisuaLex (frozen) |
| EU rubriche, tree, title | VisuaLex |
| EU annexes and PDF | mcp-legal-it |
| CGUE decision text | VisuaLex (frozen), MLI `cellar_uri` entry kept |
| EU case law citing an article | merge (VX axioms primary, MLI title search as declared fallback) |
| EU → IT implementation | mcp-legal-it (VX has none) |
| Cassazione lookup | merge |
| Cassazione text | VisuaLex (frozen) |
| Cassazione original PDF | VisuaLex (library part; route stays in VX) |
| Cassazione search | merge (VX query modes, MLI agent features) |
| Corte costituzionale | merge (VX reader, MLI search and massime) |
| Giustizia amministrativa | merge (VX read by number, MLI search) |
| CeRDEF | mcp-legal-it (VX has none) |
| Decision model and identity | VisuaLex |

Four defects found during the inventory are **in correction on PR #58** (robustness audit, with
2.17.1 patches) and are not redone by the migration: the exponential `_ANNEX_RE`, «art. 3-5» read
as art. 35, the court classification in `verifica_citazioni`, the disp. att. c.p.c. date. They are
marked in their rows.

---

## 1. Network and safety layer

| # | Area | VX | MLI | Cases only one side covers | Tests | Recent fixes | Performance | Choice |
|---|---|---|---|---|---|---|---|---|
| 1.1 | HTTP client, retries, rate limits | `services/http_client.py:ThrottledHttpClient.request` (aiohttp). Defaults (`tools/config.py:26-32`): concurrency 3, spacing 0.5 s, 4 retries, backoff 0.5×2^n + 0–0.3 s jitter, 30 s total. 404 → `DocumentNotFoundError`, no retry; network errors, timeouts and 5xx retried; `max_retries=n` per call (tree 0, act dates 1, GA/curia/eu_case_law 1); no sleep after the last attempt. Spacing and concurrency are **per client object** (two: shared + `decisions/http.py`). | `lib/_http.py:retry_request` (httpx), ~30 call sites. 2 retries, 1 s then 2 s, no jitter; network errors and 5xx retried, any 4xx (429 included) raised at once. No concurrency cap or spacing except tmview (1 s), `verifica_citazioni`'s semaphore, `api/_norme.py:281`. `core/_http.py:async_client(fonte, …)` is the single construction point (32 sites) and already names the source. | VX: spacing, cap, jitter, per-call budget. MLI: one factory naming the source, `fonti_consultate` provenance. | VX `test_http_client_retries.py` (12). MLI `test_http_retry.py` (7), `test_api*.py`. | VX 3baf1a12, 502f5a23 (#255), a1d40115, 6edf02a8. MLI 6133ebe, 066d596. | VX cold run (19 requests) = 27 HTTP + 1 Playwright visit; ≤ ~2 req/s per client. MLI uncapped. | **merge**: keep httpx and `async_client`; port VX semantics into `core/_http` keyed **by source** (cap, spacing, budget, per-call `max_retries`, jitter, no final sleep). No aiohttp. |
| 1.2 | Retry-After «not before» | `_pause_source` / `_respect_source_pause` / `_stated_retry_after` (`http_client.py:163-201`): a stated Retry-After on 429/503 pauses that source for every caller; waited before taking a slot; > 30 s left (`MAX_PAUSE_WAIT`) → refused at once. Own backoff never pauses. Numeric form only. | None: the header is never read. | VX only. | VX `test_http_client_retries.py:127-185`. MLI none. | VX 502f5a23 (#255), a1d40115. | — | **VisuaLex**, as a per-source table in `core/_http`; add the HTTP-date form. |
| 1.3 | Timeouts, concurrency per source | One 30 s total timeout with per-call overrides (GA/curia 20 s, corte_cost download 180 s, resolver budgets 25 s / 240 s). | Per client, separate connect limit: 30/10 s (Italgiure, GA, CONSOB, Normattiva HTML…), 45/15 s (CeRDEF, CGUE, eu_implementation), 60 s (AKN, corte_cost, CELLAR), 120/15 s (full act), 20/8 s (dpa_probe). | — | — | — | — | **merge**: MLI's per-source timeouts; VX cap/spacing (3, 0.5 s) as per-source defaults. |
| 1.4 | Circuit breaker | `tools/circuit_breaker.py`: 3 failures → open 300 s, one half-open trial, in memory; wraps only `get_document` in the article routes. **Flaw**: counts every exception, and a 404 arrives as `NetworkError` (`sys_op.py:83-86`), so three requests for missing articles close Normattiva for 5 minutes. | None. | VX only. | VX `test_circuit_breaker.py` (16). | none recent. | — | **VisuaLex, opt-in and fixed**: per source in `core/_http`, counting only network errors, 5xx and 429. Useful for the HTTP deployment (one process, many users); little for stdio. |
| 1.5 | Egress allowlist | `tools/egress.py:ALLOWED_HOSTS` (8) + `is_allowed`, checked **at request time** in `ThrottledHttpClient.request` and before a tree visit; refuses backslash, control characters, credentials, non-http(s) schemes. Gaps it documents: Playwright `page.goto`, redirect targets. | `lib/_egress.py` (17 hosts + CI/script lists). `is_allowed` handles the Brocardi switch and a host lookup only, and is **not called at runtime**: enforcement is the static URL-literal scan plus `HOST_PER_FONTE` (`core/_http.py:35`). Redirect re-checks only in cgue and dpa_probe hooks. | VX: runtime check, string hardening. MLI: wider host inventory, CI scan. | VX `test_egress_allowlist.py`. MLI `test_egress_allowlist.py` (6), `test_api.py`. | VX c0c2f206, 3baf1a12. MLI 8b6400c, 5cc21bb. | — | **merge**: an httpx `request` event hook in `async_client` checking host and scheme against `HOST_PER_FONTE[fonte]`, in `GUARDIE` so an injected factory cannot drop it; it runs on redirects too, closing both sides' gap. Port VX's string hardening into `is_allowed`. |
| 1.6 | Italgiure TLS | `tools/tls.py:italgiure_ssl_context`: shipped intermediate, **SHA-256 pin checked at runtime**, mismatch raises. | `lib/italgiure/client.py:53-58 tls_context()`: same certificate (same SHA-256, expires 2029-07-29); pin and a 180-day expiry alarm enforced **by tests**, plus an AST scan for `verify=False` and a live handshake. | VX: runtime pin. MLI: stronger tests. | VX `test_tls_italgiure.py`. MLI `test_italgiure_tls.py` (5). | VX 6501c38d. MLI b1db6e7, b367c06. | — | **merge**: MLI file and tests + VX runtime hash check. One file, one pin after the move. |
| 1.7 | SSRF on caller-supplied URLs | `pdfextractor.py:is_allowed_pdf_urn` (exact host, http(s)), path through `pdf_cache_path`; tree checks `is_allowed`. | cgue `cellar_uri_error` + `_only_cellar` hook (redirects); dpa_probe public-address check on every hop. | MLI: guards on every request and redirect. | VX `test_pdf_url_guard.py` (3), `test_pdf_cache_path.py` (3). MLI `test_cgue.py`, `test_dpa_probe.py` (79). | MLI bb35fcc, 0fdcb5a. | — | **mcp-legal-it**. Noted for the VX side, not ported: `/export_pdf` calls `setup_driver`/`close_drivers`, which `PlaywrightManager` does not have (`app.py:833,841`). |
| 1.8 | Cache injection | Scrapers call `get_cache_manager().get_persistent(ns)` directly (`normattiva_scraper.py:25`, `akn_fetch.py:228`, `act_dates.py:102`, `eu_case_law.py:155`, `treextractor.py:79,222`) and `aiocache @cached`; Redis optional. | `lib/_cache.py` sole reader of `MCP_CACHE_DIR`/`LEGAL_CACHE`; `core/_config.Configurazione(client_factory, cache_dir, cache, brocardi)` per task or process; `LEGAL_CACHE=off` wins. In-flight key includes the event loop. | VX: pruning, atomic writes (row 3.11). MLI: single reader, switch, injectable. | MLI `test_cache_switch.py` (8). | MLI 6133ebe, 6eaf78a, 381d42b. | — | **mcp-legal-it** contract: migrated readers lose their `get_cache_manager()` calls; VX plugs its cache in through the injection point. Keep in-flight dedupe and the AKN cap (agree one default: VX 40, MLI 50). |
| 1.9 | User-Agent | Court readers send an honest UA with a contact (`decisions/http.py:27`), accepted by Italgiure; Playwright paths spoof Chrome. | Mostly spoofed browser UAs; SPARQL clients send stale `mcp-legal-it/2.1`/`2.12`. | — | — | — | — | **VisuaLex**: one honest UA in `core/_http`, overridable per source only where a firewall is shown to need it; verify each source live first. |
| 1.10 | Playwright | EUR-Lex scraper (WAF), EUR-Lex tree, Normattiva PDF export. `sys_op.PlaywrightManager` is not actually used by any of the three. | No runtime browser (dev dependency only). EUR-Lex text and treaties via CELLAR. | — | — | — | — | **mcp-legal-it**: no browser in the engine. Depends on **Q1**. |

## 2. Normattiva: text and structure

| # | Area | VX | MLI | Cases only one side covers | Tests | Recent fixes | Performance | Choice |
|---|---|---|---|---|---|---|---|---|
| 2.1 | HTML article text | `services/normattiva_scraper.py:75-300` `estrai_da_html` + 4 `_estrai_testo_*`, `html.parser`; raises `ParsingError`; `[ \t]+` → one space. | `lib/visualex/scraper.py:425-525` `_normattiva_*`, `lxml`; keeps line-start indentation; no `bodyTesto` → whole page text. | VX: repealed-article notice outside the span (c.p. 523-555). MLI: `_served_article_key` (the number of the article actually served). *Measured* on 29 fixtures: 25 identical; c.p. art. 524 differs by one trailing space (lxml vs html.parser on malformed markup); 3 title pages differ (VX error, MLI whole page). | VX `test_normattiva_extraction.py` (9), `test_normattiva_validity.py` fixtures. MLI `test_legal_citations.py`, `test_articolo_inesistente.py` (34). | VX fb0dfd26. MLI none since 9ee8840. | 1 GET per article page; VX caches the raw page. | **VisuaLex (frozen)**, `html.parser` unchanged. Keep MLI's `_served_article_key` as a separate read. *Done in PR 3a: 11/11 texts identical to a live VisuaLex run.* |
| 2.2 | Fetch order, channel | `get_document`: HTML first; AKN only as last resort (re-downloads the whole export, uncached). | `fetch_article`: AKN first, then HTML, then the existence guard; year-only acts resolved first. | MLI: suffix spelling identity, preleggi part hint. | as above | MLI 5f6c4ad (#48). | VX cold cc_2043 7.05 s, 2 requests. MLI cold 2 (landing + caricaAKN), +1 year-only; warm 0. | **merge**: `canale="html"` = the VX path unchanged (stops answering `non_supportata`); `canale="akn"` = MLI. |
| 2.3 | AKN fetch and cache | `services/akn_fetch.py`: caches only the **index** (keys, structure, rubriche, abrogati, parts, fingerprints), memory + persistent; single-flight with `asyncio.shield`; parsing in `asyncio.to_thread`; cap 40; accepts an export only above 40 000 characters. | `lib/visualex/akn_fetch.py`: caches the **whole parsed act** (LRU 50 + JSON on disk, schema 2); URL→params index (warm call = 0 requests); loop-aware in-flight dedupe; structural acceptance check. | VX: per-article sha256 fingerprints + FRBRWork dates. MLI: `LEGAL_CACHE=off`; short acts (VX's floor rejects l. 742/1969, 24 555 bytes). | VX `test_akn_fetch.py` (18), `test_akn_integration.py` (6), `test_fetch_act_fingerprints.py` (8). MLI `test_akn_fetch.py` (23). | VX 83e62932, 85a4d278. MLI 6133ebe, fab1f6b. | VX rubriche_cc cold 4.75 s. MLI parses on the event loop (~250 ms for c.c.) and rewrites `akn_hits.json` on every hit. | **merge**: VX index-only cache policy, `to_thread`, fingerprints; MLI warm path, structural check, schema version, switch. Drop the per-hit write and the 40 000 floor. |
| 2.4 | AKN parser | `services/akn_parser.py` (749 lines): `XMLParser(recover, resolve_entities=False, no_network=True)`; `ParsedPart.dates`; Dispositivo part; rubriche, abrogati, `_restore_accents` (titles only), `presentable_title`; largest part always wins. | `lib/visualex/akn_parser.py` (530 lines): `XMLParser(recover, huge_tree=True)` **without entity/network hardening**; body kept when it has more articles than the largest annex (#47); wider annex-name regex; annex API. | *Measured* on 7 MLI fixtures: identical article texts on 6 acts; on d.lgs. 36/2023 VX's `article('30')` returns Allegato I.7 (the #47 bug MLI fixed). **Neither renders `<table>`**: commi read via `content/p` lose table cells (Tariffa of DPR 131/1986); no fixture with a table on either side. | VX `test_akn_parser.py` (40). MLI `test_akn_parser.py` (39), `test_allegati.py` (30). | VX 3b9530ce, 5f35beb5, 6910a49a, bd82c41d. MLI fab1f6b (#47). | same | **merge**: VX base (hardened parser, dates, Dispositivo, rubriche/abrogati/accents) + MLI #47 dominance rule, annex regex and API. Add `<table>` handling and a DPR 131/1986 fixture. |
| 2.5 | Article keys | `akn_parser.normalize_article_key` + `tools/article_suffixes.py` (bis … vicies, longest first). | Suffix list stops at `decies` in several copies; `scraper._article_identity` unifies spellings (quindecies = quinquiesdecies, nonies = novies, unico = 1). | complementary | VX `test_article_suffixes.py` (8). MLI `test_articolo_inesistente.py:413-424`. | VX b30a0679, 2b2d3e6f. | — | **merge**: VX normaliser and table + MLI spelling identity. See 4.5. |
| 2.6 | Index, tree, rubriche | `tools/treextractor.py` `get_tree` / `_narrow` (one download serves every variant) / `_parse_normattiva_tree`; `/fetch_rubriche` from the AKN index with abrogati, parts and the presentable title. | `fetch_act_index` (`vediRubriche`): flat list, regex-parsed rubriche, no annexes, no abrogati, no cache; `api.indice_atto` says abrogati/parts are planned. | VX only (per-annex index, EUR-Lex tree). | VX `test_tree_variants.py` (12), `test_fetch_rubriche.py` (5). | VX e7f7bc04 (#252), c0c2f206, 33706a78. | VX tree_cc 0.04 s after #252, rubriche_cc 4.75 s. MLI 2 uncached GETs per call. | **VisuaLex**, with the EUR-Lex/Playwright half split out of the module. |
| 2.7 | Missing article | `app.py:406-620 create_norma_visitata_from_data` (Quart methods): checks **before** fetching against the tree, scoped to dispositivo or annex, AKN fallback, `None` on outage, partial ranges, «where else» hint (`_where_else_in_tree`). | `scraper.py:219-351 _checked_html_article` (#48): checks **after** fetching (served number vs requested, then AKN numbers); `esito` `articolo_non_trovato` / `verifica_non_disponibile`; also EUR-Lex. | VX: scope and hint. MLI: needs no tree, machine-readable outcomes. VX's AKN fallback uses the dominant part (the annex for d.lgs. 36/2023). | VX `test_article_existence.py` (26). MLI `test_articolo_inesistente.py` (34), `test_legal_citations_fixes.py`. | VX 8735718f. MLI 5f6c4ad, 548a7c4 (#48). | VX +1 tree request (cached). MLI 0. | **merge**: extract VX's check from the Quart controller into pure functions; keep MLI's post-check and outcomes. |
| 2.8 | Annexes | Positional annex numbers read from the tree (c.p.a. = annex 2); default annex of a codice; redirect to the annex holding the article. | Annex ids as the act writes them (`I.7`) from AKN; never the body article on a malformed annex reference. | complementary | MLI `test_allegati.py` (30). | VX 8735718f. MLI fab1f6b (#47). | — | **merge**. |
| 2.9 | Full act text | None in the library (raw HTML from `get_document`). | `fetch_normattiva_full_text`, `api.testo_atto`, `fetch_full_act`: AKN `full_text(part)`; fallback walks `caricaArticolo` article by article. | MLI only | MLI `test_legal_citations*`. | MLI fab1f6b. | MLI 2 cold / 0 warm; fallback N+1 sequential requests (thousands for c.c.). | **mcp-legal-it**; cap or drop the per-article fallback. |
| 2.10 | Law PDF | `services/pdfextractor.py` (Playwright) + `/export_pdf`. | EU: official PDF from CELLAR; Italian: fpdf2 from the full text. | — | VX `test_pdf_cache_path.py`, `test_pdf_url_guard.py`. | VX f0fa8dc3, cc17480a. | VX browser, 60-240 s. | **mcp-legal-it** for the library; the Playwright export stays a VX feature. |
| 2.11 | Page and disk caches | `tools/cache.py PersistentCache` (atomic write, `sweep_expired`, `prune`); `prune_normattiva_cache` (30 days unread / 2 GB); raw pages 24 h. | No raw-page cache; `akn_acts/*.json` one file per act per vigenza day, **never pruned** (c.c. ≈ 2 MB a day). | VX pruning; MLI switch and declared locations. | VX `test_normattiva_cache_prune.py` (17). MLI `test_cache_switch.py`. | VX 0e6154ba, 2681afdc, 118c5656. | — | **merge**: MLI contract + VX atomic write and pruning applied to MLI's caches. No Redis. |

## 3. EU sources

| # | Area | VX | MLI | Cases only one side covers | Tests | Recent fixes | Performance | Choice |
|---|---|---|---|---|---|---|---|---|
| 3.1 | EUR-Lex article text (OJ) | `services/eurlex_scraper.py`: Playwright visit to the ELI page (passes the WAF), page cached per URL (one visit per act since #252), `html.parser`, 4 strategies. | `scraper.py:_build_celex`, `_eurlex_urls`, `_fetch_eurlex_html`, `_extract_eurlex_article`: one httpx GET to CELLAR by CELEX, **no page cache**, `lxml`, `div#art_N` first, title must end the number (`(?!\d)`). | *Measured*: on the same OJ fixtures the two extractors give byte-identical text (6 GDPR articles, 3 of directive 2002/58, AI Act art. 6). The difference is the **fetch channel**. VX bug: a missing article is served as another (`startswith` without the digit guard, `eurlex_scraper.py:421-425`; GDPR without art. 1 serves art. 17). | VX `test_eurlex_fixtures.py` (5), `test_eurlex_consolidated.py`. MLI `test_legal_citations_fixes.py`, `test_articolo_inesistente.py`, `test_allegati.py`. | VX e7f7bc04 (#252). MLI 5f6c4ad, cf01414. | VX cold gdpr_art6 4.50 s (1 visit; was 8.61 s / 2), warm ~0.2 s. MLI 1 GET + CELLAR redirects, never cached. | **VisuaLex (frozen)** extractor; fetched from CELLAR with a VX-style page cache **if Q1's A/B test confirms identical bytes**. Port MLI's `(?!\d)` guard (touches only the «not found» path). |
| 3.2 | Treaties TUE/TFUE/CDFUE | EUR-Lex HTML via Playwright. | `EURLEX_TREATY_CELEX` → CELLAR; the citable URL stays EUR-Lex. | — | MLI `test_resolver_coverage.py`. | MLI cf01414. | as 3.1 | **merge** (CELLAR), per Q1. |
| 3.3 | Recitals | `extract_recitals` + `/fetch_recitals`: all at once as `{number, text}`, modern `div#rct_N` and legacy `<p>(N)` in sequence between «considerando quanto segue» and «HA ADOTTATO», footnote calls removed; consolidated → `[]`. | `_extract_eurlex_article("rec_N")`: one at a time, text keeps «(N)», footnote calls kept, legacy fallback can take a footnote. | VX: bulk, sequence check. | VX `test_eurlex_recitals.py` (9), `test_fetch_recitals.py` (14). | VX ce594d9b, 26682f52. MLI 5ff0e9e. | cached page | **VisuaLex**. Open: whether recitals fall under the frozen-text rule (then VX's form binds). |
| 3.4 | Consolidated versions | `celex_consolidated` (sector-0 CELEX), `extract_article_consolidated`, `strip_amendment_markers` (▼M markers, one line per point). | None; on consolidated fixtures MLI's extractor leaves «▼M2» and double spaces. | VX only | VX `test_eurlex_consolidated.py` (52). | VX 93c02ae6, 9908a907, 18366776, 45dd59ec. | Playwright | **VisuaLex (frozen)**. Q1(b): does CELLAR serve the sector-0 page with the same markup? |
| 3.5 | EU rubriche, tree, title | `treextractor._parse_eurlex_tree`, `_extract_eurlex_title` (`eli-main-title` → `title-doc-last` → `DC.description`), failed trees never cached. | None for EU acts. | VX only | VX `test_eurlex_rubriche.py` (6), `test_tree_variants.py`. | VX 76bc7396, 33706a78. | rubriche_gdpr 0.22 s | **VisuaLex**. |
| 3.6 | EU annexes and PDF | No EU annexes; no EU PDF. | `_extract_eurlex_annex` (`div#anx_N`); `download_eurlex_pdf` (CELLAR content negotiation, PDF/A then PDF, EUR-Lex last). | MLI only | MLI `test_allegati.py`, `test_legal_citations_fixes.py`. | MLI fab1f6b, 0b71c60. | up to 4+1 requests | **mcp-legal-it**. |
| 3.7 | CGUE decision text | `services/decisions/curia.py`: found **by case** (C-634/21) via SPARQL (with year, then without for joined cases → `causa_riunita`, then by CELEX); exact case token; Italian XHTML or pre-2009 HTML from CELLAR; blocks; footnote calls and procedure-language note removed (→ `lingua_processuale`); frozen projections `curia_synthetic_*`. | `lib/cgue/client.py:fetch_sentenza_text(cellar_uri)`: whole document `get_text("\n")`, no blocks, footnote calls kept; `leggi_decisione` answers `non_supportata` for EU courts. Strong SSRF guard on `cellar_uri`. | *Measured* on VX's synthetic fixture: MLI's projection ≠ VX's (643 vs 576 characters). | VX `test_decisions_curia.py` (33), frozen test. MLI `test_cgue.py` (131). | VX 003afbf5, 06d5276a, 216718dc. MLI e9690d6, bb35fcc, 0fdcb5a. | VX cgue_634_2021 0.91 s, 2 requests. | **VisuaLex (frozen)** text and lookup by case; keep MLI's `cellar_uri` entry and its guard. No browser on either side. |
| 3.8 | EU case law citing an article | `services/decisions/eu_case_law.py`: CELLAR `owl:Axiom` citations, fragment `^A0?<n>($|[PL])`; sector-3 R/L/D only (treaty → `non_supportata`); JUDG/ORDER/OPIN_AG; 500-row cap → `troncato`; cached 3 days; partial answer = 503, never an empty list. | `giurisprudenza_cgue_su_norma` / `api.giurisprudenza_ue_su_articolo`: SPARQL `CONTAINS` on **titles**; works for treaties and free text; recall depends on titles; no cache. | VX: precise citation graph. MLI: treaties, free text. | VX `test_eu_case_law.py` (45). MLI `test_cgue.py`. | VX e7b3717c, 5bb9c8cd. MLI 0b71c60, 83e5e6f. | VX 0.06-0.8 s, 1 request. | **merge**: VX axioms primary; MLI title search as a **declared** fallback (the output says which method produced the list). |
| 3.9 | EU → IT implementation | none | `lib/eu_implementation`: national measures, EU basis of an Italian act. | MLI only | MLI `test_eu_implementation.py` (90). | MLI 203d69a, 0b71c60, 6133ebe. | 1-3 SPARQL | **mcp-legal-it**. |

## 4. Identity of a norm

| # | Area | VX | MLI | Cases only one side covers | Tests | Recent fixes | Performance | Choice |
|---|---|---|---|---|---|---|---|---|
| 4.1 | Act dates (year-only citations) | `services/act_dates.py` (`date_from_title`, `resolve_many`, `complete_year`): Normattiva resolver, date accepted only when type, year **and number** match the page title; nine State kinds; 15 s budget; found dates cached a year on disk. `complete_date_or_parse` still writes `YYYY-01-01` into the URN on a miss. | `scraper.py:with_full_date` / `act_page_metadata`: landing page via the `YYYY-01-01` URL, accepts `eli:date_document` when it **starts with the year** (no number or type check); memory cache only. `cite_law` hides the URN when unresolved; `api.NormaDati` keeps the placeholder URN with `data_risolta=False` (`tests/unit/test_api.py:76`). | VX: title verification, more act kinds, disk cache. | VX `test_act_dates.py` (50). MLI ~6 in `test_legal_citations_fixes.py`, 2-3 in `test_api.py`. | VX c2a53f5d, 530519e2, d1c287fa, 91574aad. MLI 0b71c60. | VX 1 GET cold, 0 warm (dlgs231_year_only 1.13 s, 3 requests in all). MLI also 3 cold, and the landing GET again after every restart. | **VisuaLex** + MLI's rule «never present a placeholder URN as identity», applied to both `generate_urn` and `NormaDati` — **open question Q3**. |
| 4.2 | Validity (vigenza) | `services/normattiva_validity.py`: window «Testo in vigore dal … al …», version number, act's last update, state `current`/`historical`/`not_yet`/`abrogated`, `request_in_window`, `reject_future_version_date` (Europe/Rome); read from the raw page already cached, **no extra request**; linear-time patterns; unreadable page → no key, never a guess. | None. `api.tipi.Vigenza` always `None`; `versione` ≠ vigente → `non_supportata`. `akn_fetch.fetch_act_akn(norma, data_vigenza)` already fetches AKN at a date (unused). | VX only | VX `test_normattiva_validity.py` (81), `test_validity_wire.py` (8), live. | VX d84a2eac, c08a3bb1, 2bb4b071, b41fe8cb, bfa93c0d, 3b0b3052. | 0 extra requests | **VisuaLex**, ported as is: it reads the window from the page, never from the request, which is what an ESATTO label at a date needs. The window comes from the HTML page: an AKN-channel answer needs the HTML page too (+1 request) or a window read from AKN (not built). Successions between versions are not computed by either side. |
| 4.3 | URN and norm model | `tools/urngenerator.py` (`generate_urn`, `append_article_info`, `append_version_info`), `tools/norma.py`, `tools/sources.py` (`normalize_norm_urn`, `eu_identity`, `cite_article`/`cite_act`) pinned to `conventions/sources/golden.json`. | `lib/visualex/models.py` (`Norma.url`, `_append_article`, `split_annex`), `core/norme._urn_from_url`, `api.tipi.NormaDati` (VX keys + `descrizione`, `data_risolta`). | VX: `@originale`/`!vig=`, annex override, consolidated CELEX, URN normaliser, citation style. MLI: annex syntax in the article string. *Measured* MLI defects: `Norma('d.l.', …)` → `urn:nir:stato:d.l.:…`, `l. cost.` → `l..cost.`; `_append_article("25 terdecies")` → a space in the URN. VX: `normalize_norm_urn` treats `YYYY-01-01` as an identity. | VX `test_sources_golden.py` (16), `test_urngenerator_version.py` (6). MLI `test_allegati.py`, `test_api.py`. | VX d2f96cfe, 50f2edbd. MLI fab1f6b, cf01414. | — | **merge**: VX `generate_urn` and `sources.py` as the identity layer, MLI annex syntax in front, `NormaDati` wire shape kept. The `d.l.`/`l. cost.` URNs are fixed by taking VX's search keys (4.4). |
| 4.4 | Act names and aliases | `tools/map.py`, `tools/act_resolver.py`, `tools/alias_resolver.py` + `preset_aliases.yaml` (~90 presets, before the NL parser). | `lib/visualex/map.py` (+ `normalize_act_type`), `core/norme._resolve_act` (EU and Italian long/short patterns), `_suggest_acts`. | *Measured*: `ATTI_NOTI` (64), `ATTI_DENOMINATI` (202/81) and `BROCARDI_CODICI` (103) identical; candidate-key logic identical. VX extra: 2 code URNs (c.p.i. implementing regulation, c.p.p. execution regulation), 18 `NORMATTIVA_SEARCH` keys (`d.l.`, `decreto-legge`, `l. cost.`, `legge costituzionale`, `r.d.l.`, `d.lgs.lgt.`, `c.p.a.`, capitalised codes), the dotted `NORMATTIVA` table (111). MLI extra: `EURLEX_TREATY_CELEX`; **live gates** over every table row (`test_atti_denominati_live.py`, `test_brocardi_codici_live.py`) that VX lacks. Disp. att. c.p.c. dated 1941-08-25 in MLI's code table (correct: 18 December 1941) — **in correction on PR #58**. | VX `test_act_resolver.py` (13), `test_act_tables.py` (11), `test_alias_resolver.py` (51), `test_alias_catalog.py` (6). MLI `test_resolver_coverage.py` (28), `test_brocardi_identity.py` (42), live gates. | VX 4f555c92, 76dfdbb8, 36d1daae, 4700b72d. MLI cf01414, a81db4f, f131154, 823c383, 5fb615f. | — | **merge**: VX tables (superset) + MLI treaty CELEX and live gates (extended to VX's extra rows); MLI `_resolve_act` patterns and `_suggest_acts` next to VX's presets. |
| 4.5 | Article suffixes | `tools/article_suffixes.py`: 26 spellings bis … vicies (variants, semel), longest first, leaf module read by every article regex; mirrored by `apps/web/src/utils/articleSuffixes.ts` and `apps/server/src/utils/articleSuffixes.ts`. | Three private copies: `api/_norme.py:43-54` (stops at sexiesdecies, adds `tredecies`), `models.py:136` (stops at decies), `akn_parser.py:29`; `scraper._ORDINAL_SPELLINGS` spelling equivalence. *Measured*: `_VOCE_ARTICOLO` reads «25-septiesdecies- Delitti» as article 25 (live today in `indice_atto`). | VX: full table and TS parity. MLI: spelling equivalence. | VX `test_article_suffixes.py` (8), `test_article_numbers.py` (20), `test_article_existence.py` (26) + TS test. MLI `test_articolo_inesistente.py`, `test_api_surface.py`. | VX 2b2d3e6f, 4700b72d, 0ebe8822. MLI 5f6c4ad. | — | **merge**: VX table as the single source, imported byte for byte; MLI's copies removed; MLI's spelling equivalence kept for the served-article check (`scraper._ORDINAL_SPELLINGS`, extended to VX's variants). `tredecies` (MLI's API only, no source prints it) dropped. *Done in PR 2.* A change to the table must change the two TS mirrors in VX in the same step (TS parity constraint). |
| 4.6 | `normalize_act_type` | `text_op.normalize_act_type`: literal key, then case-insensitive index, then without spaces; every key reachable. | Literal lookup only: capitalised keys unreachable. | VX | VX `test_normalize_act_type.py` (5). MLI none. | VX 2b2d3e6f. | — | **VisuaLex**. Parity with VX's `actTypes.ts` through the golden file. |

## 5. Parsing text into references

| # | Area | VX | MLI | Cases only one side covers | Tests | Recent fixes | Performance | Choice |
|---|---|---|---|---|---|---|---|---|
| 5.1 | NL query parser (one citation) | `tools/nl_parser.py:parse_nl_query`. | `core/norme.py:_parse_reference`, `_resolve_act`; `api.leggi_riferimento`. | *Measured*. Only VX: lists and ranges (`artt. 1, 2`, `3-5`), joined/spaced suffixes (`615bis`), the convention labels (`l. cost.`, `r.d.l.`, `d.lgs.lgt.`), «1° settembre», `(Allegato A)`, refusal of «cost. 1/2003». Only MLI: recitals (`considerando 42 GDPR`), dotted annexes (`I.7`; VX reads «I» — wrong annex, silently), act-before-article, refusal with near names. MLI «art. 3-5 c.c.» → art. 35 — **in correction on PR #58**. | VX `test_nl_parser.py` (96), `test_nl_parser_convention.py` (10), `test_alias_resolver.py` (51). MLI `test_legal_citations.py` (127), `test_resolver_coverage.py`, `test_allegati.py`, `test_api.py`. | VX 4f555c92, 76dfdbb8, 3ab81870, 4700b72d. MLI 5fb615f, 823c383, f131154, 5f6c4ad. | VX ≤ 4 ms on hostile input (500-char cap); compiles a regex per search key per call. MLI linear since 5fb615f. | **merge, VX as base** + MLI recitals, dotted annexes, act-first, «refuse with suggestions». |
| 5.2 | EU act year/number | `resolve_eu_year_and_number`, `eu_act_from_groups`: directive marker, year-first numbering from 2015, `(CE)`/`(CEE)` number first, year ≤ current + 1. | `_EU_PATTERN`, `_split_eu_year_number`. *Measured* wrong: `regolamento (CE) n. 2006/2004` → year 2006; `reg. 2913/92` → year 2913. | VX | in `test_nl_parser`, `test_citation_linker`. | — | — | **VisuaLex**. |
| 5.3 | Annex in a citation | `_extract_annex`: letter, roman, digit; keeps case; «allegato a d.lgs.» trap. | `_ANNEX_*` patterns + `models.split_annex`: dotted ids, any position. `models._ANNEX_RE` exponential — **in correction on PR #58**. | complementary | MLI `test_allegati.py` (30). | VX 76dfdbb8, d75b2c89. MLI 823c383, fab1f6b. | — | **merge**. |
| 5.4 | Article lists and ranges | `text_op.parse_article_input`: `1, 2-bis, 4-6`, ranges expanded through the act's index, `615bis`, `135 sex decies`, `171 octies 1`, `314/2`, dedupe, typed errors (503/404/400). | None (one article per reference). | VX | VX `test_article_numbers.py` (20), `test_article_range_index.py` (13). | VX 4700b72d, 90bb5e99, 6a11e86b. | linear | **VisuaLex** (fills the «planned» multi-article API). |
| 5.5 | Citation linker (prose) | `tools/citation_linker.py:extract_citations`: five passes, spans `{start, end, display_text, …}`, EU marker mandatory for regulations, lists, comma clauses, bare «art. 7» inherits the last act. Limit: context is not reset at a sentence end (documented). **Quadratic regex** in the shared EU head (`nl_parser.py:90-98`, adjacent `\s*`): «regolamento» + 16 K spaces = 7.6 s (*measured*); runs in a thread. | `_split_citazioni`: splits a list, does not read prose. | VX only for prose. | VX `test_citation_linker.py` (82). MLI in `test_legal_citations.py`. | VX 4700b72d, fc12b8a7, c7c213c8. | see left | **VisuaLex after fixing the EU head** (possessive or collapsed whitespace, plus a timing test); MLI's list splitter stays for `verifica_citazioni`. |
| 5.6 | Decision citation parser | `services/decisions/citation.py:read_decision_citation`: Cassazione (archive, section, S.U., dates), Corte cost., CdS, CGARS, TAR by seat or region, CGUE `C-`/`T-` and pre-1989 cases, two-digit years, recognised-but-unsupported courts; pinned to the golden `decision_citations`. | `_classify_citazione`, `_sentenza_num_anno` (+ Brocardi `parse_massime_references`). Corte cost. and CdS checked on Italgiure — **in correction on PR #58**. MLI reads «Cass. 999 del 2021» (VX does not). | — | VX `test_decision_citation.py` (16). MLI `test_legal_citations.py`, `test_brocardi.py`. | VX 4539b61d, 4daf4e27, 98a5d8ef, fbc773b3, 72896791. MLI 5fb615f, c7e558c. | VX scans ≤ 600 chars. | **VisuaLex** + MLI «N del AAAA». |
| 5.7 | `text_op` helpers | `parse_date`, `nospazi`, `get_annex_from_urn`, … | `models._parse_date` (year → `YYYY-01-01`), inline. | — | VX `test_sources_golden.py`. | VX d1c287fa. | — | **VisuaLex** where it replaces a weaker copy; the rest are interchangeable. |
| 5.8 | Duplicates inside MLI | — | `tools/italgiure.py:_parse_articolo_riferimento` and `tools/orientamento.py:_parse_articolo_riferimento`: the same regex twice, no act-first, annexes or suffixes. | — | — | — | — | Replace with the unified parser of 5.1. |

## 6. Italian court decisions

| # | Area | VX | MLI | Cases only one side covers | Tests | Recent fixes | Performance | Choice |
|---|---|---|---|---|---|---|---|---|
| 6.1 | Cassazione lookup | `decisions/resolver.py` + `decisions/italgiure.py`: one Solr query per archive, number zero-padded; `trovata`/`ambigua` (`archivio_dedotto` when the section decides)/`non_trovata` + `motivo` + `archivio_dal`; `suggerimento` (penal, next year); section notices; **oscuramento** recognised (≤ 300 chars mentioning it → `testo={}` + `testo_assente`); caches 30 d / 1 h / 24 h with versioned keys, swept every 6 h; no homepage GET. | `core/cassazione.py:lookup_decisione` (4 steps), `tools/italgiure.py:_leggi_sentenza_impl` (omonimi note), `api._leggi_cassazione`; one query for both archives with «tutti». **No oscuramento detection**: the source's notice comes out as the text. `anno_parziale` also for the current year (VX: `inesistente`). No cache. | VX: oscuramento, motivi, suggestion, caches. MLI: one query for both archives, omonimi rendering. | VX `test_decisions_italgiure.py` (41), `test_decisions_resolver.py` (35), `test_fetch_decision.py` (11), `test_decisions_model.py` (12). MLI `test_italgiure.py` (283), `test_italgiure_tls.py`. | VX 99a27d66, 666e752a, 24d4b3fc, cd01d5f6. MLI b1db6e7, b502cbf, d1da27d. | VX cass_civ_12449_2024 0.96 s, 2 requests. MLI: homepage GET always (`client.py:212`) → found 2, missing up to 5, + 2 archive-start probes in the API. | **merge**: VX semantics and caches; MLI single query for both archives and omonimi rendering in the MCP tool. |
| 6.2 | Cassazione text | `italgiure.py` (`paragraphs`, `split_dispositivo`, `pdf_url`, `_plausible`, `lookup_with_pdf`) + `pdf_text.py`: text from the court's **PDF** (the field is cut at the source in about a third of cases), refused when it names another decision, < 70% of the field, or shares < 10 of the first 20 words; else the field with `testo_da_archivio`; dispositivo once; never truncated; budgets 8 / 6 / 15 s. | `lib/italgiure/client.py:format_full_text`: raw `ocr`, truncated at 30 K (12 K + 18 K), `da_carattere` paging, `ocrdis` repeated (dispositivo **twice**). | VX | VX `test_decisions_pdf_text.py` (31, synthetic PDFs), `test_decisions_text_frozen.py` (31 hashes). `*_local` tests use real decisions kept out of the repo: **not moved**. MLI truncation/paging in `test_italgiure.py`. | VX e42ad740, 4238619a, ae03c305, 39bb1e7d. MLI 83e5e6f. | VX +1 GET for the PDF, ≤ 15 s. | **VisuaLex (frozen)**. Truncation and `da_carattere` rebuilt on the projection as MCP presentation. New dependency `pdfminer.six` (Q4). |
| 6.3 | Cassazione original PDF | `resolver.original_pdf`, `italgiure.original_pdf`, `pdf_url` guard, `%PDF-`, ≤ 5 MB; route `pdf_route.py` stays in VX. | none | VX | VX `test_fetch_decision_pdf.py` (8). | VX a8efaf3d, ae03c305. | cached 0, cold 2 | **VisuaLex** (library part). |
| 6.4 | Cassazione search | `decisions/search.py` + `italgiure.search`: modes `indice` (codes and Constitution) and `testo`; phrases never a bare «art. N» (measured by VX: 1588 vs 939 hits); proximity ~6; topic as one sanitised quoted phrase; sort by deposit; year facet in the same request; `non_supportata`. Route `search_route.py` stays in VX. | `build_search_params` (edismax, boosts, facets), `build_norma_variants`, `core/cassazione.query_con_ripiego`, `_auto_relax`, `_auto_refine`, `_smart_suggestions`, orientamento. Non-strict variants OR a bare «art. N» (lower precision); proximity ~15. | VX: index mode, year facet, sanitised topic. MLI: relevance ranking, filters, relax/refine, orientamento. | VX `test_decisions_search_query.py` (26), `test_decisions_italgiure_search.py` (19), `test_search_decisions.py` (26). MLI `test_italgiure.py`, `test_orientamento.py` (52), `test_giurisprudenza_unificata.py` (23). | VX dd5349af, 2b17a544, c33dfeec. MLI b502cbf, e31af90, 346e24d. | VX search_2043_cc 0.66 s, 2 requests. MLI 2 per query, up to +6 on relax, +4 on refine, no cache. | **merge**: VX modes and phrases behind `modo`; MLI's agent features kept for the MCP tools. |
| 6.5 | Corte costituzionale | `decisions/corte_cost.py`: open-data bundles on disk (closed 30 d, open 24 h), year read on demand, 2-year LRU; an expired copy confirms, never denies (→ 503); `clean` (HTML entities, C1/cp1252, NFC), `split_epigrafe`, `line_paragraphs`; never truncated; no search. | `lib/corte_cost/client.py`: same bundles (VX took them from MLI 2.15), JSON cache per year 7 days for every year; `_clean` without entity/C1/NFC fixes; search, massime, `pronunce_su_norma`, `ultime_pronunce`; 25 K cap. | VX: text rules. MLI: search, massime, «on a norm». | VX `test_decisions_corte_cost.py` (29). MLI `test_corte_cost.py` (92). | VX 00a46301, ce564ea3, de389d18. MLI 90d6fe7, 7ba2032. | VX corte_cost_242_2019 0.03 s, 0 requests. MLI cold download ~56 MB. | **merge**: VX reader and `clean` (frozen), TTLs, expired-copy rule; MLI search, massime and «on a norm» moved onto VX's bundle cache. |
| 6.6 | Giustizia amministrativa | `decisions/giustizia_amministrativa.py` + `tar_seats.py`: read **by number and year** (kind in the identity, families, TAR by region → seats + `sede_dedotta`, `ambigua`); portlet and `p_auth` read at runtime; XML read with lxml, no network, no DTD, no entities; each `h:div` a line; `…Ted` twins left out. | `lib/giustizia_amm/client.py`: **topic search** by seat, kind, year; «on a norm»; «latest»; read by `(sede, nrg, nome_file)`; stdlib ET, `itertext` joined by spaces; on `ParseError` the tag-stripped HTML becomes the text. TLS already verified (a20a763). | VX: read by number. MLI: search. | VX `test_decisions_giustizia_amministrativa.py` (20), `test_decisions_admin_resolver.py` (12), `test_decisions_admin_model.py` (7). MLI `test_giustizia_amm.py` (106). | VX 7bb0f54e, 83b3611a, 72896791. MLI 20d48e4 (#32), a20a763. | VX 3 per seat. MLI 2. | **merge**: VX reading, XML parser (frozen lines, safe XML) and seats; MLI search, «on a norm», «latest», read by source key. |
| 6.7 | CeRDEF | none | `lib/cerdef/client.py`, `tools/cerdef.py`, `api.leggi_provvedimento_tributario`, `cerca_decisioni_tributarie`. | MLI only | MLI `test_cerdef.py` (121). | MLI ec90c88 (#46), 0b71c60. | 1 POST (+ paginator), detail 1 GET | **mcp-legal-it**, mapped onto `EsitoDecisione`. |
| 6.8 | Model and identity | `decisions/model.py`: `Identity` and its `key()` (shared by the web page, dossiers, MERL-T), `Reference`, `Decision` (block text, `testo_assente`, `testo_origine`), `parse_reference`, `FAMIGLIE`; `resolver.Outcome.to_dict`. | `api.tipi` + `api/_decisioni.py`: `EsitoDecisione` in VX's shape with raw text; no `testo_assente`, `testo_origine`, `suggerimento`, `archivio_dedotto`/`testo_da_archivio`/`sede_dedotta`. | VX | VX `test_decisions_model.py`, `test_decision_citation.py`. MLI `test_api.py`, `test_api_surface.py`. | MLI 6eaf78a, 381d42b, 066d596. | — | **VisuaLex**: the identity and its `key()` are a shared contract; `test_api_surface.py` is updated with the move. |

---

## Tests that move

Only synthetic fixtures or fixtures already public in VisuaLex's repository move; the `_local`
tests (real decisions kept out of the repository) stay local, and the frozen projections move as
hashes only.

- Network: `test_http_client_retries`, `test_circuit_breaker`, `test_egress_allowlist` (merged with
  ours), `test_tls_italgiure` (merged with ours), `test_pdf_url_guard`, `test_pdf_cache_path`.
- Normattiva/AKN: `test_normattiva_extraction`, `test_akn_fetch`, `test_akn_integration`,
  `test_akn_parser`, `test_article_existence`, `test_article_numbers`, `test_article_range_index`,
  `test_article_suffixes`, `test_act_dates`, `test_act_resolver`, `test_act_tables`,
  `test_normalize_act_type`, `test_urngenerator_version`, `test_fetch_act_fingerprints`,
  `test_fetch_rubriche`, `test_tree_variants`, `test_normattiva_validity` (+ `_live`, by hand),
  `test_validity_wire`, `validity_pages.py`, `test_normattiva_cache_prune` (adapted).
- EUR-Lex: `test_eurlex_fixtures`, `test_eurlex_consolidated`, `test_eurlex_recitals`,
  `test_eurlex_rubriche`, `test_fetch_recitals`.
- Decisions: `test_decisions_text_frozen` (+ `frozen_projections.json`), `test_decisions_pdf_text`,
  `decisions_pdf_synth.py`, `test_decision_citation`, `test_decisions_corte_cost`,
  `test_decisions_curia`, `test_decisions_giustizia_amministrativa`, `test_decisions_italgiure`,
  `test_decisions_italgiure_search`, `test_decisions_model`, `test_decisions_resolver`,
  `test_decisions_search_query`, `test_decisions_admin_model`, `test_decisions_admin_resolver`,
  `test_eu_case_law`, `test_fetch_decision`, `test_fetch_decision_pdf`, `test_search_decisions`;
  `*_live` by hand only.
- Citations: `test_alias_catalog`, `test_alias_resolver`, `test_nl_parser`,
  `test_nl_parser_convention`, `test_citation_linker`, `test_sources_golden` (needs the golden file,
  see Q6).
- Route tests (`test_fetch_*`, `test_search_decisions`, `test_validity_wire`) are rewritten against
  the library functions; the Quart routes stay in VisuaLex.

## Risks

1. **Byte identity.** One known difference already (c.p. art. 524, `lxml` vs `html.parser`): the
   HTML channel must run VisuaLex's extractor unchanged. Every migration PR runs VisuaLex's
   `collector_timing.py --compare` and the frozen-text tests.
2. **MCP outputs change where VisuaLex's text wins.** `leggi_sentenza` (PDF text, dispositivo
   once), the Corte costituzionale (`clean`, epigrafe split), the administrative courts (lines
   instead of space-joined text), CGUE (blocks, no footnote calls), recitals. `replay_mcp_outputs.py
   compare` will show them; each is declared as intended, and `da_carattere` offsets move.
3. **Decision texts with personal data on disk.** VisuaLex caches whole texts 30 days and sweeps
   them; MLI caches none today. A text cache must come with the sweep **and** the oscuramento rule,
   or a source's anonymisation notice is cached as the court's reasons.
4. **Dependencies.** Must not enter the distributed package: aiohttp, aiocache, structlog, Quart,
   Redis, Playwright. New: `pdfminer.six` (Q4).
5. **Import-time side effects in VisuaLex modules** that MLI's gates refuse: `treextractor` imports
   Playwright and creates a cache directory at import; a log file handler is opened in the working
   directory; `akn_fetch` reads `date.today()` (MLI reads the clock only through `_clock`). Every
   imported module goes through MLI's gates (clock, declared caches, egress).
6. **Two VisuaLex controllers.** The existence check and the date completion live as Quart methods
   in `services/visualex/app.py`; they are extracted into pure functions.
7. **TypeScript parity.** `article_suffixes`, act types and citation forms are mirrored in
   VisuaLex's TypeScript and pinned by the golden file; any behaviour change there is shown against
   `articleSuffixes.ts`, `actTypes.ts` and the golden tests.
8. **Overlap with the citation-gate work**, which moves MLI's reference parser into
   `core/riferimenti.py` / `core/citazioni.py` and adds prose readers for norms and decisions:
   rows 5.1–5.6 should land after it, inside those modules (VisuaLex's parser modules use only the
   standard library, which fits the gate's constraint).
9. **Python floor.** Possessive quantifiers need Python ≥ 3.11; the published package must declare
   a floor that matches.
10. **XML hardening in MLI's AKN parser** (`huge_tree=True` without `resolve_entities=False` /
    `no_network=True`): VisuaLex's parser settings are taken with the merge (row 2.4). The input
    comes from Normattiva, so the exposure is low, but it is a known misconfiguration.
11. **Load on the sources.** Changing retry budgets moves the load; PR #252's cold baseline (19
    requests → 27 HTTP + 1 browser visit) is re-measured after the network PR, with no row
    allowed more requests.

## Open questions

- **Q1 — Playwright.** VisuaLex needs a browser only for EUR-Lex pages (OJ, treaties,
  consolidated). Shipping Chromium (~150 MB, `playwright install`) in every uv/.mcpb install is a
  heavy cost. Proposed: one serial, polite live A/B on the texts PR #252 already compared, plus one
  or two consolidated texts and one pre-2014 act: VisuaLex's extractor on the Playwright page vs
  on CELLAR's XHTML, byte for byte. (a) same bytes on OJ pages? (b) does CELLAR serve sector-0
  consolidated texts with the same markup? (c) same title fields for legacy acts and treaties? If
  yes, no browser in the engine; if not, the EUR-Lex text stays behind an optional extra.
- **Q2 — `article_text` channel default.** The MCP tools serve AKN first today; VisuaLex must get
  `canale="html"`. Does the MCP default stay AKN (faster warm, accent-transliterated) or move to
  HTML (the frozen text)?
- **Q3 — placeholder dates.** One rule for a year-only act: a year-only URN, or no URN, never
  `YYYY-01-01` as an identity. VisuaLex keys stored notes on the date, so changing dates already
  stored is a data migration on VisuaLex's side, not part of this move.
- **Q4 — `pdfminer.six`** as a runtime dependency (Cassazione text from the PDF), pinned as
  VisuaLex pins it, in the package, the `.mcpb` launcher and the OpenAI config.
- **Q5 — circuit breaker** on by default only for the HTTP transport, or off everywhere unless
  configured.
- **Q6 — the golden file** `conventions/sources/golden.json`: copied into mcp-legal-it as a fixture
  (with a check that it matches VisuaLex's) or shared another way.
- **Q7 — Corte costituzionale bundles** (~56 MB download for 2001–today): kept on disk under
  `MCP_CACHE_DIR` with VisuaLex's TTLs; what happens with `LEGAL_CACHE=off` (memory only, one
  download per process).

## Proposed PR order

Stacked, each small and reviewable, each with VisuaLex's tests and fixtures, the byte-identity
checks, `replay_mcp_outputs.py compare`, the full non-live suite on FastMCP 3 and 4 and the gates.

1. **Network**: per-source limits, spacing, retry budget, Retry-After «not before», optional
   breaker, runtime egress hook, honest UA, TLS runtime pin — all in `core/_http`.
2. **Article keys, suffixes, act types, tables** (4.4–4.6, 2.5): small, unblocks everything else.
3. **Normattiva HTML channel, index, existence check, AKN parser merge** (2.1–2.8, 2.11).
4. **Act dates and validity** (4.1, 4.2), filling `validity` from the same fetch.
5. **EUR-Lex** (3.1–3.6), after Q1.
6. **Decisions**: model, Cassazione with PDF text and oscuramento, Corte costituzionale, GA, CGUE,
   EU case law (6.x, 3.7–3.8).
7. **Citations and URN** (5.x, 4.3), after the citation-gate work lands.

## Code from VisuaLex: licence

VisuaLex is MPL-2.0 as a whole; its source files carry no per-file header. Each imported file gets
the MPL-2.0 notice and a line «Imported from VisuaLex (MPL-2.0), `<path>` at `<commit>`»; the README
gets a short «Code from VisuaLex» section. mcp-legal-it is MPL-2.0 from 3.0, so no relicensing is
involved. Some VisuaLex files themselves derive from mcp-legal-it (act tables, AKN parser, Corte
costituzionale reader); the header records the path and commit they were imported from.
