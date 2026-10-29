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

Used by `tests/unit/test_articolo_inesistente.py`. To refresh, fetch the same URLs
(a few seconds apart) and keep only the `bodyTesto` element.

## Act pages (identity only)

Captured on 2026-10-29 from the act's year-only URN, without an article. Each keeps only
the `<title>` and the `eli:` metadata of the page's head, verbatim.

| File | URN (after `urn:nir:stato:`) | What Normattiva served |
|------|------------------------------|------------------------|
| `landing_dm_55_2014.html` | `decreto.ministeriale:2014;55` | the page of D.M. 10 marzo 2014, n. 55 (title «DECRETO 10 marzo 2014, n. 55», ELI date 2014-03-10) |
| `landing_atto_inesistente.html` | `legge:1990;99999` | HTTP 200, the error page «Normattiva - Errore», no `eli:` metadata («Errore nel caricamento delle informazioni»). The update table of d.lgs. 196/2003 art. 2-ter asked without the session cookie served the same page, byte for byte but for the session id |

Used by `tests/unit/test_api_risolvi_atto.py`, together with `../akn/landing_legge_241_1990.html`.
