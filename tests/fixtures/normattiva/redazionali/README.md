# Normattiva article pages with the Gazzetta's editorial notes (`div.note-akn`)

Captured on 2026-11-02 from `https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:<urn>`
(HTTP 200), polite and serial (one request at a time, 2 s apart), during the survey for
issue #119. Each file keeps the page's `<div class="bodyTesto">` as BeautifulSoup reads it,
inside a minimal HTML shell; the rest of the page is dropped.

| File | URN (after `urn:nir:stato:`) | What it shows |
|------|------------------------------|---------------|
| `l24_2017_art7.html` | `legge:2017-03-08;24~art7` | The current text of an article never amended keeps its notes: one section «Note all'art. 7», transcribing artt. 1218, 1228 and 2043 c.c. |
| `l132_2025_art1.html` | `legge:2025-09-23;132~art1` | Art. 1 of an act: the «N O T E» banner, the «Avvertenza» (art. 10 d.P.R. 1092/1985) on two lines, then «Note all'art. 1» |
| `dlgs58_1998_art1_originale.html` | `decreto.legislativo:1998-02-24;58~art1@originale` | The original text: «Avvertenza», «Note alle premesse» (about the preamble, 12,600 characters), «Nota all'art. 1» |
| `dlgs231_2001_art4.html` | `decreto.legislativo:2001-06-08;231~art4` | One section «Nota all'art. 4», the same words as the `authorialNote` of art. 4 in `../../akn/dlgs_231_2001.xml` |

`../aggiornamenti/dlgs196_art13_v1.html` (version 1 of art. 13 d.lgs. 196/2003) is the
issue's own example: «Nota all'art. 13: - Per la legge 7 dicembre 2000, n. 397, vedi in
nota all'art. 8.»

Survey (59 article pages): the block sat directly under `div.bodyTesto`, always in the
comma-div shape; 12 of 21 original texts and 3 of 38 current texts had it; from 83 to
62,000 characters, median about 8,000.

Only the «Note all'art. N» sections are kept (decision LI-058); the tests split the whole
block too, to check the headings left out.

Used by `tests/unit/test_note_redazionali.py`.
