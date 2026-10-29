# Normattiva article versions and update tables

Captured on 2026-10-29 for `api.modifiche_articolo`, polite and serial (one request at a
time, 2 s apart). Each article page was fetched first, with the same client as its
version pages and tables: without its session cookie, Normattiva answers those with its
generic error page.

Per article `<name>`:

- `<name>.html`: the article page (`N2Ls?urn:nir:stato:<urn>`), trimmed. It keeps the
  title, the `eli:` metadata, the validity block (`div.vigore`), the act's and the
  article's update links, the act tree's entries for this article (its
  `caricaArticolo?art.versione=k` links) and `div.bodyTesto`, as BeautifulSoup reads them. The rest of the page (the whole act tree,
  2.6 MB for the codice civile) is dropped. The trim was checked to give the same update
  link, current version, version links, window, article number and act date as the
  whole page.
- `<name>_v<k>.html`: version *k*'s page (`/atto/caricaArticolo?art.versione=k&…`), whole.
- `<name>_agg_v<k>.html`: version *k*'s update table
  (`/do/atto/vediAggiornamentiAllArticolo?…&art.versione=k`), whole. Version 1's table
  (`_agg_v1`) is the article's whole history, not the amendments that produced version 1:
  for `dlgs196_art2ter` it opens with d.lgs. 101/2018 introducing the article and has the
  decree-law converted «con modificazioni» as a row without a number of its own.

| Name | Article (URN after `urn:nir:stato:`) | What it shows |
|------|--------------------------------------|---------------|
| `dlgs196_art2ter` | `decreto.legislativo:2003-06-30;196~art2ter` | 3 versions. The d.l. 139/2021 as published (v2: «l'introduzione del comma 1-bis … e la modifica … commi 2 e 3»), then as converted «con modificazioni» together with the conversion law 205/2021 (v3) |
| `dlgs196_art13` | `decreto.legislativo:2003-06-30;196~art13` | 5 versions, 2004 to 2018. An indirect amendment («ha conseguentemente disposto», d.l. 135/2009); the abrogation by d.lgs. 101/2018 (G.U. 4 Sept, in force 19 Sept 2018) |
| `dpr131_art1` | `decreto.del.presidente.della.repubblica:1986-04-26;131~art1` | The undated page serves version 2, abrogated from 2027-01-01 (d.lgs. 123/2025, in a Supplemento ordinario): a version not in force yet |
| `cc_art2` | `regio.decreto:1942-03-16;262:2~art2` | A code's article, in the code's annex: the L. 39/1975 amendment |
| `ccii_art64bis` | `decreto.legislativo:2019-01-12;14~art64bis` | Five provisions of d.lgs. 136/2024 in one row (v2), then d.lgs. 147/2026 (v3) |
| `cc_art2740` | `regio.decreto:1942-03-16;262:2~art2740` | Never amended: no update link |

Used by `tests/unit/test_api_modifiche_articolo.py`.
