# GitHub Pages for 3.0 (drafts)

`index.html` and `privacy.html` are the 3.0 versions of the two pages served
from the orphan branch `gh-pages` (capazme.github.io/mcp-legal-it). They are
here so they can be reviewed with the rest of the release material. **Do not
publish them before the GA**: on release day copy them over the files on
`gh-pages` (see `../checklist-3.0.0.md`).

Both start from `gh-pages` at `da4fba2`. Layout, styles, the Mac/Windows switch
and the tone (written for lawyers, no Python knowledge assumed) are unchanged.

## `index.html` (installation guide)

- Eyebrow says «Versione 3.0»; the lead counts 30 guided procedures, 9
  commands and 6 agents (it said «23 procedure guidate», the MCP prompt count,
  not what the plugin ships).
- A link under the lead sends 2.x users to the new section.
- New section **«Aggiornare dalla versione 2»**: the two update commands,
  restart, the one-time download on the first start, how to check the version
  (`stato_server`), what changes for them, the `.mcpb` update, a link to the
  release notes.
- New section **«Usare Legal IT senza Brocardi»**: `LEGAL_BROCARDI=off` for Mac
  (`LEGAL_BROCARDI=off claude`) and Windows PowerShell
  (`$env:LEGAL_BROCARDI="off"; claude`), and for the app's Code tab the `env`
  block of `~/.claude/settings.json` (to be confirmed on a fresh install, see
  the checklist §4), checked with `stato_server`.
- Troubleshooting table: two rows, the citation gate («gate citazioni» and
  «fuori copertura») and a value no longer accepted after the update
  (`opposizione_atti_esecutivi`).
- Footer: MPL-2.0 from 3.0, Apache-2.0 up to 2.x.

## `privacy.html` (privacy notice)

- Eyebrow: «versione 3.0» and a date placeholder (`GG mese 2026`) to fill in
  on release day.
- Generated files: they go to a private `mcp-legal-it` folder in the system
  temp directory, readable only by the user (it said «nella cartella che
  indichi», which the generators do not do), and the system may empty it.
- Refusal ledger: what one line contains (tool, table, outcome, time; never
  case data).
- Citation gate: what it reads locally in 3.0 (the current session's
  transcript, the text Claude writes into files, tool results, the same
  session's subagent transcripts), and that it reads no other session, saves
  nothing, sends nothing.
- Sources: Brocardi.it can be excluded with `LEGAL_BROCARDI=off`; a new
  paragraph on the network rules (host check on every request and redirect,
  http(s) only, no credentials, at most three requests at a time per source,
  `Retry-After` honoured, verified TLS for Italgiure too).
- The English summary carries the same three additions.
