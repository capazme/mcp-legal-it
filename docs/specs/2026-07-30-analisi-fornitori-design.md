# Analisi Fornitori — Supplier ledger privacy screening — Design

- **Date**: 2026-07-30
- **Branch**: `feature/analisi-fornitori` (from `develop`)
- **Status**: Approved (design), pending implementation plan
- **Scope**: new plugin skill `analisi-fornitori` + 2 new MCP tools in
  `src/tools/analisi_fornitori.py` + VIES client lib. Reuses `genera_dpa`
  unchanged. No SAPG platform code.

## Problem

Clients send the firm their **mastrino fornitori** (supplier ledger: every
received invoice with the counterparty). For GDPR compliance the firm must
screen each supplier and decide whether it acts as a **data processor
(responsabile ex art. 28 GDPR)** — and therefore needs a nomina — or as an
independent controller / outside the privacy perimeter.

Today this is done manually: a hand-written prompt (a `.docx` kept in Dropbox)
is pasted into Claude together with the ledger, and the output Excel is
reconciled against a hand-made template
(`Modello_analisi_privacy_fornitori.xlsx`, 11 columns + an "Avvertenze" sheet).
The method is sound but nothing guarantees it is applied identically each
time: the taxonomy lives in a loose prompt, the Excel layout is rebuilt by the
LLM on every run, identification of suppliers is best-effort web search, and a
long run cannot be interrupted and resumed.

## Decisions taken with the user (2026-07-30)

1. **Where**: skill in the `legal-it` plugin (this repo), not a SAPG platform
   feature. Optional SAPG integration is explicitly out of scope.
2. **Input**: unpredictable formats (Excel/CSV, native PDF, scanned PDF,
   e-mail bodies). Extraction is LLM-driven, not a deterministic parser.
3. **Identification sources**: free only — web search + VIES. No Openapi.it.
4. **Output**: standard Excel report (deterministic tool) **plus**, on user
   confirmation, art. 28 nomina drafts via the existing `genera_dpa` tool.
   No SAPG/ROPA push, no supplier questionnaire letter.
5. **Approach**: LLM does what is irregular (reading messy inputs, web
   research, legal judgement guided by written rules); deterministic tools do
   what must be identical every time (VIES lookup, Excel rendering).
   Parallel subagent mode as an optional scale path for large ledgers.

## Architecture

```
mcp-legal-it/
├── src/lib/vies/
│   ├── __init__.py                     # re-export check_vat
│   └── client.py                       # VIES REST client (httpx + shared retry)
├── src/tools/analisi_fornitori.py      # NEW module, tags {"privacy", "utility"}
│   ├── verifica_partita_iva_vies()     # VAT → validity + registered name/address
│   └── genera_report_fornitori()       # canonical JSON rows → standard .xlsx
├── plugin/skills/analisi-fornitori/
│   ├── SKILL.md                        # orchestrating workflow (Italian)
│   └── references/
│       ├── metodologia.md              # extraction, dedup, confidence rules
│       ├── classificazione.md          # 3-category taxonomy + controversial cases
│       └── dpa-whitelist.md            # vendors with their own standard DPA
└── tests/unit/
    ├── test_analisi_fornitori.py       # xlsx tool: structure + validation
    └── test_vies.py                    # VIES client + tool (mocked, + live marker)
```

The lib does not depend on `src.server` (repo convention). Both tools are
registered in `src/server.py` imports and in the `instructions` string.

## Canonical supplier record (data contract)

Every phase of the workflow produces/consumes this JSON object per supplier.
`genera_report_fornitori` validates it; the subagent mode returns it; the
checkpoint file stores it.

```json
{
  "denominazione_mastrino": "ACME CLOUD SRL",
  "piva_cf": "01234567890",
  "fonte_piva": "mastrino | vies | web | null",
  "attivita": "Hosting e SaaS gestionale",
  "categorie_dati": "Dati di clienti/utenti trattati per conto del titolare",
  "qualificazione": "responsabile | titolare_autonomo | fuori_perimetro",
  "motivazione": "SaaS che tratta dati per conto del titolare su sue istruzioni",
  "probabilita_responsabile": "alta | media | bassa",
  "dpa_proprio": "si | no | da_verificare",
  "confidenza": "alto | medio | basso",
  "fonti": ["https://..."],
  "note": "flag controverso / omonimia / ..."
}
```

Field rules:

- `denominazione_mastrino`, `qualificazione`, `motivazione`, `confidenza`:
  required, non-empty.
- `probabilita_responsabile` and `dpa_proprio`: **required when**
  `qualificazione == "responsabile"`, **must be absent/null otherwise**.
- `piva_cf`: 11-digit P.IVA or 16-char CF, or null. `fonte_piva` says where it
  came from (`mastrino` = present in the ledger, `vies`/`web` = recovered).
- `fonti`: list of URLs (may be empty for obvious fuori-perimetro rows).
- Enum values are lowercase snake_case on the wire; the Excel tool maps them to
  display labels (see below).

## Workflow (the skill)

Six phases, with a JSON checkpoint after every mutation so long runs are
interruptible and resumable.

**Fase 0 — Setup.** Identify the titolare (the firm's client) and the ledger
file. Create `analisi_fornitori_checkpoint.json` next to the ledger (fallback:
cwd). If a checkpoint for that ledger already exists, offer to resume from the
first unanalysed supplier.

**Fase 1 — Estrazione.** Read the ledger whatever the format (xlsx/csv via
parsing, native PDF via text extraction, scans via OCR, e-mail bodies as
text). Extract `denominazione` + `piva_cf` when present. Amounts are
irrelevant and ignored. If the file is unreadable, stop and ask for a better
copy — **never invent suppliers**.

**Fase 2 — Dedup.** Deterministic rules written in `metodologia.md`: key on
P.IVA when available, otherwise on normalized name (uppercase, strip corporate
forms and punctuation, merge obvious variants). Then a user gate: *"N fornitori
unici, procedo con la ricerca?"* — the user sees the perimeter and estimated
effort before the long phase starts.

**Fase 3 — Ricerca e classificazione.** In blocks of ~15 suppliers. Per
supplier: (a) if it has a P.IVA → `verifica_partita_iva_vies` for a hard
identity anchor; (b) web search for the supplier's actual business; (c)
classify per `classificazione.md`; (d) DPA check: whitelist first, then a
targeted search; (e) confidence per the written rules ("alto" only with a
confirmed P.IVA match; when in doubt, lower it). Checkpoint updated after
every block.

*Parallel mode (>~40 suppliers):* the skill offers to dispatch blocks to
concurrent general-purpose subagents. The per-block prompt is fixed in
SKILL.md and instructs the subagent to return **only** canonical JSON rows.
The orchestrator merges results into the checkpoint and applies guardrails:

- any row with `confidenza: "alto"` but no confirmed P.IVA is downgraded to
  `"medio"`;
- rows that do not validate against the contract are discarded and their block
  is re-run sequentially.

**Fase 4 — Report.** Call `genera_report_fornitori` with the full analysis
from the checkpoint → standard Excel, delivered to the user.

**Fase 5 — Nomine (on confirmation).** List the responsabili with
`dpa_proprio: "no"`; on a single user confirmation, generate one art. 28
nomina draft per supplier via the existing `genera_dpa` tool (DOCX each).

### Checkpoint file format

```json
{
  "versione": 1,
  "cliente": "Titolare S.r.l.",
  "file_mastrino": "/path/mastrino.xlsx",
  "creato": "2026-07-30T12:00:00",
  "fase": "estrazione | dedup | ricerca | completata",
  "_nota_fase": "completata = ricerca finished; report and nomine are stateless and can be regenerated from `analisi` at any time",
  "fornitori_estratti": [{"denominazione_mastrino": "...", "piva_cf": null}],
  "fornitori_unici":   [{"denominazione_mastrino": "...", "piva_cf": null,
                          "varianti": ["..."]}],
  "analisi":           [ { canonical record, one per completed supplier } ]
}
```

## Tool 1 — `verifica_partita_iva_vies`

```python
@mcp.tool(tags={"privacy", "utility"})
async def verifica_partita_iva_vies(partita_iva: str, codice_paese: str = "IT") -> dict
```

- Pre-check: reuse the checksum logic of the existing `verifica_partita_iva`
  (for `IT` only) — invalid checksum returns immediately without a network
  call.
- Endpoint: VIES REST
  `POST https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number`
  with `{"countryCode": ..., "vatNumber": ...}`. httpx async, standard
  30s/10s timeouts, shared retry helper with backoff.
- Returns (never raises to the caller):

```json
{
  "partita_iva": "01234567890",
  "codice_paese": "IT",
  "checksum_valido": true,
  "disponibile": true,
  "valido": true,
  "denominazione": "ACME CLOUD SRL",
  "indirizzo": "VIA ROMA 1 20100 MILANO MI",
  "errore": null
}
```

- `disponibile: false` + `errore` when VIES or the member state is down
  (`MS_UNAVAILABLE`, timeouts, 5xx). `denominazione`/`indirizzo` are null when
  the member state returns `"---"` or empty (data not provided). The skill
  treats unavailability as "proceed web-only, note it, confidence rules
  unchanged".

## Tool 2 — `genera_report_fornitori`

```python
@mcp.tool(tags={"privacy", "utility"})
def genera_report_fornitori(
    fornitori: list[dict],          # canonical records
    cliente: str,                   # titolare name, shown in Avvertenze
    data_analisi: str = "",         # default: today, dd/mm/yyyy
    file_sorgente: str = "",        # ledger filename, shown in Avvertenze
    nome_file: str = "",            # default: analisi_fornitori_<cliente>_<uuid8>.xlsx
) -> str                            # "File salvato: <path> (<KB> KB)" convention
```

**Validation (collect-all, then fail).** All violations are collected and
returned as one error string (`"Errore di validazione: riga 3: manca
'motivazione'; riga 7: 'dpa_proprio' presente ma qualificazione non è
'responsabile'; ..."`) so the model can fix everything in one pass. No file is
written on error. Checks: required fields, enum membership, the
responsabile-only field rules, `fonti` is a list, `fornitori` non-empty.

**Rendering (openpyxl).** Two sheets, mirroring the existing hand-made model:

1. **`Avvertenze`** — metadata block (cliente, data analisi, file sorgente,
   totale fornitori, counts per category) + the standing disclaimer: automatic
   first-level screening to be validated with the client and the contracts;
   where the P.IVA is missing identifications may be uncertain; manually
   review rows with Confidenza "Basso" and "controverso" flags.
2. **`Analisi fornitori`** — 11 columns, frozen header row, model column
   widths (30/16/34/34/20/40/16/16/14/32/40), wrap text on long columns:

   | # | Header |
   |---|--------|
   | A | Denominazione (da mastrino) |
   | B | P.IVA / CF |
   | C | Attività / servizi |
   | D | Categorie di dati presumibilmente trattate |
   | E | Qualificazione ipotizzata |
   | F | Motivazione sintetica |
   | G | Probabilità che tratti dati come responsabile |
   | H | DPA proprio del fornitore disponibile? |
   | I | Confidenza dell'identificazione |
   | J | Fonte (URL) |
   | K | Note / flag |

   *Deliberate deviation from the model file*: headers get proper Italian
   accents (the hand-made model was ASCII-only). Everything else matches.

**Display mapping**: `responsabile` → "Responsabile del trattamento",
`titolare_autonomo` → "Titolare autonomo", `fuori_perimetro` → "Fuori
perimetro privacy"; `alta/media/bassa` → "Alta/Media/Bassa"; `si/no/
da_verificare` → "Sì/No/Da verificare"; `alto/medio/basso` →
"Alto/Medio/Basso"; `fonti` joined with newlines in column J; non-applicable
G/H cells rendered as "—".

**Sort order** (the report's whole point is surfacing what needs action):

1. responsabili with `dpa_proprio: "no"` (nomina needed),
2. responsabili `"da_verificare"`,
3. responsabili `"si"`,
4. titolari autonomi,
5. fuori perimetro — alphabetical by denominazione within each group.

Output dir: `$TMPDIR/mcp-legal-it/` (same `_salva` convention as the DOCX
tools).

## Skill package

`SKILL.md` (Italian, like every legal-it skill) with frontmatter triggers:
«mastrino fornitori», «analisi fornitori», «screening fornitori privacy»,
«nomine responsabili dai fornitori», «chi devo nominare ex art. 28», and the
generic "il cliente ci ha mandato l'elenco fatture/fornitori". Body: the six
phases above, the gates, the checkpoint handling, the parallel-mode dispatch
prompt, and the golden rules (never invent; amounts irrelevant; always cite
sources; confidence downward bias).

`references/metodologia.md`: per-format extraction guidance (typical ledger
column names, PDF table layouts, OCR caveats), name normalization and dedup
rules, web identification strategy (query patterns, preferred sources:
official site, registroimprese-derived directories), confidence calibration
table (verbatim from the current manual method: "alto" only with unique
confirmed identification; missing P.IVA → "alto" is the exception).

`references/classificazione.md`: the three categories with definitions and
examples, ported from the manual prompt; the controversial-case table with
defaults (consulente del lavoro / studio paghe → titolare autonomo, flag;
corrieri/spedizionieri → titolare autonomo, flag; recupero crediti → depends
on mandate vs purchase, confidenza "basso"); guidance for "categorie di dati
presumibilmente trattate" per category. Method note: the qualification
depends on the concrete service actually rendered, which the ledger does not
reveal — first-level screening to validate with client and contracts.

`references/dpa-whitelist.md`: vendors that publish their own standard DPA
(big tech: Google, Microsoft, AWS, Meta, LinkedIn, Stripe, PayPal, Mailchimp,
HubSpot, Salesforce, Zoom, Dropbox…; Italian hosters/gestionali with standard
DPAs: Aruba, Register.it, TeamSystem, Zucchetti…), each with the URL of the
DPA page and the caveat to verify the current version.

## Error handling

- **VIES down / rate-limited** → tool returns `disponibile: false` + reason;
  skill proceeds web-only and notes it; retries with backoff inside the
  client.
- **Unreadable ledger** → stop and ask for a better copy; never invent.
- **Unidentifiable supplier / homonyms** → never guess: most probable
  category, `confidenza: "basso"`, alternatives in `note`.
- **Malformed rows to the xlsx tool** → collect-all validation error with row
  indexes; no partial file.
- **Session interruption** → resume from checkpoint (first unanalysed
  supplier).
- **Subagent returns off-contract rows** → discard, re-run that block
  sequentially; confidence guardrail applies regardless.

## Testing

- `tests/unit/test_analisi_fornitori.py`: xlsx structure (2 sheets, exact 11
  headers, sort order with no-DPA responsabili first, Avvertenze content,
  display mappings, "—" for non-applicable cells), validation errors (missing
  fields, bad enums, responsabile-only field rules, collect-all with row
  indexes), openpyxl read-back roundtrip.
- `tests/unit/test_vies.py`: mocked httpx for the four cases (valid with
  name, valid without data, invalid, unavailable/timeout), checksum
  short-circuit, plus one `@pytest.mark.live` test excluded by default.
- Taxonomy correctness is not unit-testable (LLM-facing text): mitigated by
  keeping controversial cases and defaults as an explicit reviewable list in
  `classificazione.md`.

## Dependency & release notes

- New dependency **`openpyxl>=3.1`** (pure Python). Wire it in: `pyproject.toml`
  `dependencies`, `plugin/.mcp.json` `--with` list, dxt manifest, CLAUDE.md
  setup snippets (manual config examples), README if it repeats the list.
- Tool count 216 → **218**: update `src/server.py` `instructions`, CLAUDE.md,
  plugin/dxt descriptions (the release skill verifies counts).
- Version: MINOR bump → **2.11.0** via the `legal-it:release` skill, on user
  request at the end.
- Git: this branch `feature/analisi-fornitori` from `develop`, PR back to
  `develop` per Git Flow.

## Out of scope (explicit)

- SAPG platform integration (ROPA push, client linkage) — possible phase 2;
  the canonical JSON contract is designed to make that translation trivial.
- Supplier questionnaire letter.
- Openapi.it company search (paid) — the contract's `fonte_piva` field
  already accommodates it if added later.
- OCR quality improvements: scans are read with the tools available in the
  session; the skill's job is to refuse gracefully, not to ship an OCR stack.
