<!-- Imported from VisuaLex (MPL-2.0), services/visualex/tests/fixtures/eurlex/README.md at b2f7a30f (first at 493a8dd1), with the nine pages it describes, byte for byte. -->
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

Added 2026-10-22:

- `eprivacy_eli_legacy_trimmed.html` — the `/eli/dir/2002/58/oj/ita` page as the scraper's
  browser receives it: a legacy act with no `DC.description`, no `oj-doc-ti`, no
  `title-doc-last`, only the ELI metadata naming the act in 23 languages
  (`<meta property="eli:title" lang="…">`). Trimmed to `<title>`, those metas and `#TexteOnly`.
- `synthetic_oj_article_15_bis.html` — **synthetic**, written for the test: an OJ-style act
  whose only article 15 is «Articolo 15 bis». No real page with that shape is known.
- `amending_dir_2009_136_trimmed.html` — the OJ page of dir. 2009/136 (`/eli/dir/2009/136/oj/ita`,
  captured 2026-10-22), an amending act: its six articles, and inside art. 1 and 2, in table
  cells, the articles it replaces or inserts in dir. 2002/22 and 2002/58 («Articolo 21», «Articolo
  23 bis», «Articolo 15 bis» …). Trimmed to `#tit_1` and `#art_1` … `#art_6`.
- `synthetic_classless_glued_15_bis.html` — **synthetic**: a class-less page whose heading and text
  share an element, so the element reads «Articolo 15 bisTesto…»; its only article 15 is 15 bis.
- `gdpr_consolidated_20160504_title_trimmed.html` — the consolidated GDPR
  (`CELEX:02016R0679-20160504`, captured 2026-10-22), trimmed to its `title-doc-first` and
  `title-doc-last` paragraphs: the last holds only the EEA note, the subject is in the first.

Used by `tests/unit/test_eurlex_fixtures.py`, `test_eurlex_consolidated.py`, `test_eurlex_tree.py`,
`test_eurlex_rubriche.py` and `test_eurlex_recitals.py` (VisuaLex's tests, generated), and by
`test_eurlex_indice.py`.

mcp-legal-it's own, captured 2026-10-22 from CELLAR (`publications.europa.eu/resource/celex/<CELEX>`),
trimmed as above and checked to give the same article text as the whole page:

- `ai_act_oj_art111_trimmed.html` (`div#art_111`): Reg. (UE) 2024/1689, Official Journal text (32024R1689).
- `ai_act_consolidated_20260727_art111_trimmed.html`: the consolidation 02024R1689-20260727
  (Reg. (UE) 2026/1744): par. 2 rewritten, par. 4 added. Used by `tests/unit/test_eurlex_vigente.py`.
- `dir2009_136_oj_art1_2_trimmed.html` (32009L0136): `div#art_1` and `div#art_2` of dir.
  2009/136/CE. Art. 1 quotes, in table cells, the articles of dir. 2002/22/CE it rewrites (21, 22,
  23, 27, …). Used by `tests/unit/test_eurlex_quoted_articles.py`.
- `dir2009_136_consolidated_20201221.html` (02009L0136-20201221), the whole page: the consolidation
  of dir. 2009/136/CE has arts 2-6 only; art. 1 is gone. Used by `tests/unit/test_eurlex_vigente.py`.
