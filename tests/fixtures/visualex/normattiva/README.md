# Normattiva fixtures

Whole pages, captured in August 2026 (the page shows "vigente al 26/08/2026"), one
per extractor branch of `NormattivaScraper.estrai_da_html`:

- `akn_comma_div.html` — scenario 1, `div.art-comma-div-akn` per comma.
- `akn_just_text.html` — scenario 2, `span.art-just-text-akn`.
- `abrogato.html` — scenario 2 again, a repealed article whose
  `div.ins-akn.art_abrogato-akn` sits inside the span (cod. privacy art. 3).
- `attachment.html` — scenario 3, `span.attachment-just-text` (an annex).
- `fallback.html` — scenario 4, none of the above.

Trimmed captures (the `div.bodyTesto` block exactly as Normattiva served it,
wrapped in `<html><body>`), taken 2026-09-19 from
`urn:nir:stato:regio.decreto:1930-10-19;1398:1~art524` / `~art544`:

- `cp_524_abrogato_malformed_trimmed.html` — c.p. art. 524, repealed by
  L. 66/1996. The markup is malformed: `<a><span class="attachment-just-text">
  <div>Codice Penale-art. 524</a> <br><br><div class="ins-akn
  art_abrogato-akn">…</div></span>`. After `html.parser` repair the abrogation
  div is a sibling of the `<a>`, outside the span the extractor reads, so the
  article came back as its label only (`'Codice Penale-art. 524'`, HTTP 200).
  The same shape affects c.p. 523-526, 530, 539, 541-543, 545-555.
- `cp_544_abrogato_trimmed.html` — c.p. art. 544, repealed by L. 442/1981,
  the healthy shape for contrast: the abrogation div is inside the span and
  the text reads `Art. 544. \n\n((ARTICOLO ABROGATO DALLA L. 5 AGOSTO 1981,
  N. 442))`.

Trimmed captures of 2026-10-02, for the validity reader
(`normattiva_validity.py`, spec `docs/superpowers/specs/2026-10-01-testo-alla-data-design.md`).
Each keeps the four blocks the reader looks at, as served — `div.vigore` (the window),
the update link, the "Ultimo aggiornamento" line and `div.bodyTesto` — wrapped in
`<html><body>`:

- `art1284_cc_at_2007-12-29_trimmed.html` — art. 1284 c.c. at 2007-12-29: a middle
  version, window 25-12-2003 to 29-12-2007, version 7. Both ends of the window.
- `art183bis_cpc_at_2010-01-01_not_yet_trimmed.html` — art. 183-bis c.p.c. at
  2010-01-01, before the article existed: the window only ends (12-9-2014) and the text is
  "… NON ANCORA ESISTENTE O VIGENTE".
- `art183_cpc_at_2015-01-01_partial_abrogation_trimmed.html` — art. 183 c.p.c. at
  2015-01-01: a closed window and a "COMMA ABROGATO" notice among other commi, to prove
  that a partial notice is not the state "abrogated".
- `art183bis_cpc_in_force_abrogated_with_notes_trimmed.html` — art. 183-bis c.p.c. in
  force on 2026-10-02 (`urn:nir:stato:regio.decreto:1940-10-28;1443:1~art183bis!vig=`):
  repealed by D.Lgs. 164/2024 from 26-11-2024, version 4. Besides the label and the
  "ARTICOLO ABROGATO" notice the body carries a note marker (`((178))`) and the update
  notes (`div.art_aggiornamento-akn`). It exists because the first version of the rule
  counted those as text and read the article as in force. The file keeps the portal's
  CRLF line endings: do not retype it.
- `art155ter_cc_in_force_abrogated_plain_notice_trimmed.html` — art. 155-ter c.c. in force
  on 2026-10-02 (`urn:nir:stato:regio.decreto:1942-03-16;262:2~art155ter`): repealed by
  D.Lgs. 154/2013, window "dal 7-2-2014", version 2. The notice "(( ARTICOLO ABROGATO … ))"
  is a plain `div.ins-akn`, with no `art_abrogato-akn` class: it exists because the rule
  looked at that class only and read the article as in force. CRLF kept.
- `dlgs163_2006_art1_provvedimento_abrogato_trimmed.html` — art. 1 D.Lgs. 163/2006 in force
  on 2026-10-02 (`urn:nir:stato:decreto.legislativo:2006-04-12;163~art1!vig=`): the whole act
  is repealed by D.Lgs. 50/2016, window "dal 19-04-2016", and the notice
  "((PROVVEDIMENTO ABROGATO DAL D.LGS. 18 APRILE 2016, N. 50))" is a plain `div.ins-akn`.
  A whole-act notice, on every article of a repealed act. CRLF kept.
- `tuir_art1_at_2027-01-01_provvedimento_abrogato_trimmed.html` — art. 1 d.P.R. 917/1986
  (TUIR) as the portal serves it for 2027-01-01
  (`urn:nir:stato:decreto.del.presidente.della.repubblica:1986-12-22;917~art1!vig=2027-01-01`):
  a version that starts in the future, version 3, whose notice reads "((PROVVEDIMENTO ABROGATO
  DAL D.LGS. 19 GIUGNO 2026, N. 117))". CRLF kept.
- `tuir_art1_in_force_closing_2026-12-31_trimmed.html` — the same article in force on
  2026-10-02 (`...;917~art1!vig=`): the window announces its closure ("dal 1-1-2004 al:
  31-12-2026"), version 2. The control that a closure announced for the future leaves the
  state `current` and keeps its end. CRLF kept.

Trimmed captures of 2026-10-09, for the date of an act searched by its year
(`services/act_dates.py` `complete_year`): the resolver's page for a year-only URN, kept to
its `<title>` exactly as served (the only part the reader looks at), wrapped in
`<html><head>`. Three requests, 3 s apart, with the honest User-Agent:

- `resolver_dlgs231_2001_title_trimmed.html` — `urn:nir:stato:decreto.legislativo:2001;231`:
  "DECRETO LEGISLATIVO 8 giugno 2001, n. 231". The portal's search, which the date used to
  come from, listed «DECRETO LEGISLATIVO 31 Dicembre 2025, n. 210» first for this act.
- `resolver_dlgs163_2006_title_trimmed.html` — `…:decreto.legislativo:2006;163`:
  "DECRETO LEGISLATIVO 12 aprile 2006, n. 163" (the search listed «DECRETO 28 Giugno 2024,
  n. 127» first).
- `resolver_l241_1990_title_trimmed.html` — `…:legge:1990;241`: "LEGGE 7 agosto 1990, n. 241".

The portal prints the end of the window as `<span class="indent">al: <span id="artFine" class="rosso">29-12-2007</span></span>`
when the window has a start (the start is `<span id="artInizio" class="rosso">`, preceded by `&nbsp;`),
and as the bare text `<span>Testo in vigore al: 12-9-2014</span>`, with no `id` and no `class`, when it has none.

The extractor's output for every file here is frozen (CLAUDE.md gotcha 23:
`article_text` is the offset space of every stored highlight and note).
