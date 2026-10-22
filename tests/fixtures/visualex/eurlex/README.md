<!-- Imported from VisuaLex (MPL-2.0), services/visualex/tests/fixtures/eurlex/README.md at 493a8dd1, with the four pages it describes, byte for byte. -->

# EUR-Lex fixtures

Captured 2026-09-19 with a browser User-Agent from the `legal-content/IT/TXT/HTML`
URLs (the `/eli/` URLs answer 202 to non-browsers). Three markups live here:

- `gdpr_oj_trimmed.html` — modern OJ format (`oj-ti-art`, `oj-sti-art`,
  `div#rct_N` recitals, `oj-ti-section-1/2` headings). Recitals 1-3 and 173,
  Capo I (art. 1-4), art. 17.
- `eprivacy_oj_legacy.html` — legacy OJ format, whole page: class-less `<p>`,
  recitals as `<p>(N) …</p>` after "considerando quanto segue:", articles as
  `<p>Articolo N</p>`.
- `eprivacy_consolidated_20091219.html` — consolidated format, whole page:
  `title-article-norm` / `stitle-article-norm`, `modref` markers, no recitals,
  "Articolo 14 <span class="norm">bis</span>".
- `eidas_consolidated_20241018_trimmed.html` — consolidated format with
  `eli-subdivision` wrappers and `title-division-1/2` headings. Capo I,
  art. 12 and art. 24 (`modref` markers nested inside `div.norm` and the
  `grid-list` point grids, one of them the "▼M2 —————" deleted-point
  placeholder), art. 50.

Trimming: `str()` of the elements with the listed ids, assembled inside
`<html><body>`. The capture and trim commands are in
`docs/superpowers/plans/2026-09-19-archivio-visualex-extensions.md`, Task 1.

Used by `tests/unit/test_eurlex_fixtures.py` and `tests/unit/test_eurlex_consolidated.py` (VisuaLex's tests, adapted).

mcp-legal-it's own, captured 2026-10-22 from CELLAR (`publications.europa.eu/resource/celex/<CELEX>`),
trimmed as above to `div#art_111` and checked to give the same article text as the whole page:

- `ai_act_oj_art111_trimmed.html`: Reg. (UE) 2024/1689, Official Journal text (32024R1689).
- `ai_act_consolidated_20260727_art111_trimmed.html`: the consolidation 02024R1689-20260727
  (Reg. (UE) 2026/1744): par. 2 rewritten, par. 4 added. Used by `tests/unit/test_eurlex_vigente.py`.
