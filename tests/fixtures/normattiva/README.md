# Normattiva N2Ls pages (article lookup)

Captured on 2026-10-04 from `https://www.normattiva.it/uri-res/N2Ls?<urn>` (HTTP 200
for every one of them). Each file keeps the page's `<div class="bodyTesto">` verbatim
inside a minimal HTML shell; the rest of the page (navigation, the act's whole tree,
~2.5 MB for the codice civile) is dropped.

| File | URN (after `urn:nir:stato:`) | What Normattiva served |
|------|------------------------------|------------------------|
| `cc_n2ls_art99999.html` | `regio.decreto:1942-03-16;262:2~art99999` | art. 1 of the R.D. 262/1942 (the approving decree), with its preamble — the article does not exist |
| `cc_n2ls_art2043.html` | `regio.decreto:1942-03-16;262:2~art2043` | art. 2043 c.c., as an attachment ("Art. 2043." head, no numbered heading) |
| `cc_n2ls_art2059.html` | `regio.decreto:1942-03-16;262:2~art2059` | art. 2059 c.c. |
| `cc_n2ls_art1.html` | `regio.decreto:1942-03-16;262:2~art1` | art. 1 c.c. (not the decree's art. 1) |
| `l241_n2ls_art999.html` | `legge:1990-08-07;241~art999` | art. 1 of the L. 241/1990 — the article does not exist |
| `l241_n2ls_art3.html` | `legge:1990-08-07;241~art3` | art. 3 of the L. 241/1990 (`<h2 class="article-num-akn" id="art_3">`) |
| `dlgs36_n2ls_art999.html` | `decreto.legislativo:2023-03-31;36~art999` | art. 1 of the D.Lgs. 36/2023 (an act with annexes) — the article does not exist |
| `dlgs196_n2ls_art2sexiesdecies.html` | `decreto.legislativo:2003-06-30;196~art2sexiesdecies` | the article, labelled "Art. 2-sex-decies" (`id="art_2-sex-decies"`) |
| `dlgs196_n2ls_art2quinquiesdecies.html` | `decreto.legislativo:2003-06-30;196~art2quinquiesdecies` | the (abrogated) article, labelled "Art. 2-quindecies" |
| `cp_n2ls_art609undecies.html` | `regio.decreto:1930-10-19;1398:1~art609undecies` | art. 609-undecies c.p. ("Art. 609-undecies." head) |
| `cp_n2ls_art416bis1.html` | `regio.decreto:1930-10-19;1398:1~art416bis.1` | art. 416-bis.1 c.p. ("Art. 416-bis.1" head) |
| `dlgs23_n2ls_art3.html` | `decreto.legislativo:2015-03-04;23~art3` | art. 3 d.lgs. 23/2015, captured 2026-10-29: 3 comma divs and 4 «AGGIORNAMENTO» notes (1, 2, 3, 10), notes 2 and 10 the C. cost. 194/2018 and 128/2024 declarations; the body calls them «(1)» «(2)» «(3)» «((10))» |
| `cc_n2ls_art2327.html` | `regio.decreto:1942-03-16;262:2~art2327` | art. 2327 c.c., captured 2026-10-29: a code's attachment whose text already carries its note «AGGIORNAMENTO (113)» |
| `tub_n2ls_art117.html` | `decreto.legislativo:1993-09-01;385~art117` | art. 117 TUB, captured 2026-10-29: commi renumbered by amendments written «((6)).», «((7)).», «((8)).» at the start of their line (not note calls), one real call «((38))» and its note |

Used by `tests/unit/test_articolo_inesistente.py` and `tests/unit/test_note_aggiornamento.py`. To refresh, fetch the same URLs
(a few seconds apart) and keep only the `bodyTesto` element.

## Act pages (identity only)

Captured on 2026-10-29 from the act's year-only URN, without an article. Each keeps only
the `<title>` and the `eli:` metadata of the page's head, verbatim.

| File | URN (after `urn:nir:stato:`) | What Normattiva served |
|------|------------------------------|------------------------|
| `landing_dm_55_2014.html` | `decreto.ministeriale:2014;55` | the page of D.M. 10 marzo 2014, n. 55 (title «DECRETO 10 marzo 2014, n. 55», ELI date 2014-03-10) |
| `landing_atto_inesistente.html` | `legge:1990;99999` | HTTP 200, the error page «Normattiva - Errore», no `eli:` metadata («Errore nel caricamento delle informazioni»). The update table of d.lgs. 196/2003 art. 2-ter asked without the session cookie served the same page, byte for byte but for the session id |

Captured on 2026-11-02 the same way (the type check of #136). The first two are the pages
Normattiva's resolver serves for a decree it does not have: the law with the same year and
number, since it does not check the type. Each keeps the four `eli:` properties the library
reads (`id_local`, `type_document`, `date_document`, `title`) and the `<title>`, verbatim.

| File | Asked as (after `urn:nir:stato:`) | What Normattiva served |
|------|-----------------------------------|------------------------|
| `landing_dpcm_158_2014_serve_legge.html` | `decreto.del.presidente.del.consiglio.dei.ministri:2014;158` | the page of L. 17 ottobre 2014, n. 158 (title «LEGGE 17 ottobre 2014, n. 158», `type_document` LEGGE) |
| `landing_dm_241_1990_serve_legge.html` | `decreto.ministeriale:1990;241` | the page of L. 7 agosto 1990, n. 241 |
| `landing_dpcm_159_2013.html` | `decreto.del.presidente.del.consiglio.dei.ministri:2013;159` | the page of D.P.C.M. 5 dicembre 2013, n. 159 (title «DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI 5 dicembre 2013, n. 159») |
| `landing_dm_37_2008.html` | `decreto.ministeriale:2008;37` | the page of D.M. 22 gennaio 2008, n. 37 (title «DECRETO 22 gennaio 2008, n. 37») |
| `landing_dllgt_98_1946.html` | `decreto.legislativo.luogotenenziale:1946;98` | the page of D.Lgs.Lgt. 16 marzo 1946, n. 98 (title «DECRETO LEGISLATIVO LUOGOTENENZIALE 16 marzo 1946, n. 98») |
| `landing_dllgt_151_1944.html` | `decreto.legislativo.luogotenenziale:1944;151` | the act headed «DECRETO-LEGGE LUOGOTENENZIALE 25 giugno 1944, n. 151» (`type_document` DECRETO-LEGGE_LUOGOTENENZIALE) |
| `landing_dpcm_2020_03_08_senza_numero.html` | by ELI, `/eli/id/2020/03/08/20A01522/CONSOLIDATED` (a URN without a number answers the error page) | the D.P.C.M. 8 marzo 2020, an act without a number (title «DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI 8 marzo 2020») |

Used by `tests/unit/test_api_risolvi_atto.py` and `tests/unit/test_atto_per_anno_tipo.py`,
together with `../akn/landing_legge_241_1990.html`.

## Articles split into parts (`parti/`)

Captured on 2026-10-29. Art. 1 L. 296/2006 is split by Normattiva into 14 parts, «1 (commi
1-100)» to «1 (commi 1301-1364)», each opened from the act's tree with
`/atto/caricaArticolo?…&art.progressivo=k` (with the article page's session cookie).

| File | Page | What it keeps |
|------|------|---------------|
| `parti/l296_art1.html` | `legge:2006-12-27;296~art1!vig=2026-10-29` | the act tree's 14 entries of art. 1, the visible line «art. 1 (commi 1-100)» and `bodyTesto` (part 1) |
| `parti/l296_art1_parte8.html` | part 8, `art.progressivo=8` | the visible line «art. 1 (commi 701-800)» and `bodyTesto`: comma 773 («complessivamente rideterminata nel 10 per cento») |
| `parti/l296_art1_parte2.html` | part 2, `art.progressivo=2` | «art. 1 (commi 101-200)» and `bodyTesto`: a call «((168))» with no note block on the page |

Each trim was checked to give the same text, served article, notes, parts and served part as
the whole page. Used by `tests/unit/test_parti_articolo.py`.


## A whole act read article by article (`atto_intero/`)

Captured on 2026-11-02 from L. 30 dicembre 2023, n. 213 (bilancio 2024), one request at a
time, with the session cookie the act page sets. Art. 1 is split by Normattiva into six parts,
«1 (commi 1-100)» to «1 (commi 501-561)»; some annexes are published as images only («Parte di
provvedimento in formato grafico», a `vediPdf` link).

| File | Page | What it keeps |
|------|------|---------------|
| `atto_intero/l213_atto.html` | `legge:2023-12-30;213` | the `<title>`, the `eli:` title/id/type metadata and 15 entries of the act's tree, verbatim: the six current parts of art. 1 (`art.versione=39`), the six parts of its previous version («agg.37», `art.imUpdate=true`), art. 2, «Allegato I», «Allegato II» |
| `atto_intero/l213_art1_parteK.html` (K = 1…6) | part K, `art.progressivo=K` | the visible line «art. 1 (commi a-b)» and `bodyTesto` with its first two commi and its last |
| `atto_intero/l213_art2.html` | art. 2 | `bodyTesto` verbatim |
| `atto_intero/l213_allegato_I.html` | «Allegato I» | `bodyTesto` verbatim: an annex with a table as text |
| `atto_intero/l213_allegato_II.html` | «Allegato II» | `bodyTesto` verbatim: an annex in graphic form, a heading and the `vediPdf` link only |
| `atto_intero/dlgs196_albero.html` | `decreto.legislativo:2003-06-30;196` | the `<title>` and ten tree entries, verbatim and in order: arts. 2, 2-bis, 2-ter (one `art.idArticolo=2`, `art.idSottoArticolo` 1, 2, 3) with their older versions, arts. 2-quaterdecies and 2-quaterdecies.1 (`art.idSottoArticolo1` 10 and 20), art. 3 today (`art.idGruppo=4`) and its original text («orig.», `art.idGruppo=1`, `art.imUpdate=true`) |

Each trimmed part was checked to give the same served part (`parte_servita`) and the same
served article as the whole page, and the trimmed tree the same parts of art. 1 as the whole
tree. Used by `tests/unit/test_atto_intero_parti.py`.
