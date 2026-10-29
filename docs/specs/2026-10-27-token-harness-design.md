# Token harness: measuring what mcp-legal-it costs the model

Date: 27 October 2026. Status: the two offline measures are built
(`scripts/token_report.py`); the tool-choice run is designed only and has
never been run.

## Why

The token-reduction work cuts what the model reads from this server. Every cut
has to show two things: how many tokens it saves, and that the model still
picks the right tool and still gets the facts right. This harness is the
instrument for both. It changes no shipped behaviour and calls no LLM API.

## The three measures

| Measure | What it reads | Network | Cost |
|---|---|---|---|
| `tools` | `initialize` + `tools/list`, as a client receives them | none | free, ~2 s |
| `outputs` | the answers of 12 fixed calls, replayed from a tape | only when recording | free, ~20 s |
| tool choice | 20 tasks run by a model against the server | LLM API + sources | paid; not run |

Each offline measure writes JSON; `compare` diffs two reports of the same measure.

```bash
python scripts/token_report.py tools [--profile P | --include-tags a,b --exclude-tags c] [--json F] [--top N]
python scripts/token_report.py outputs [--tape T.json.gz] [--record] [--json F]
python scripts/token_report.py compare base.json head.json
```

### Workflow for a cut

1. On the base ref, before the cut:
   - `tools --json base-tools.json`
   - `outputs --record --tape <tape>`: once, with network
   - `outputs --tape <tape> --json base-out.json`
2. On the branch with the cut:
   - `tools --json head-tools.json`
   - `outputs --tape <tape> --json head-out.json`: offline, same tape
3. Run `compare` on each pair, and paste the tables into the PR.

The tape defaults to `.replay-tapes/token-calls.json.gz`, which git ignores; when
the base and the head are two worktrees, pass the same `--tape` to both. A path
inside the repo that git does not ignore is refused. Record the tape on the base
ref, never on the branch. Never commit a tape: it holds third-party content.
The rules of `scripts/replay_mcp_outputs.py` apply.

A cut that changes which HTTP requests a tool makes misses the tape. The
replayer counts the missed requests per call. `outputs` marks those calls and
exits 1, and `compare` lists them and exits 1. A failed replay answers in about
140 characters, and without that check it would pass for a 98% saving.

`compare` also warns when the two runs differ in setup instead of code:

- the FastMCP version (FastMCP 4 adds `serverInfo` to every result's `_meta`);
- the profile, the tag filters or the switches (`tools`);
- the clock or the server environment (`outputs`).

The `outputs` worker drops every `LEGAL_*` and `AKN_*` variable of the shell. It
passes only the pinned ones, and the report records them.

## What `tools` counts

The server is built in-process from `plugin/server`. The script refuses an
installed copy of the package. `initialize` and `tools/list` are read through
the FastMCP in-memory client.

`--profile` sets `LEGAL_PROFILE` before the import. `--include-tags` and
`--exclude-tags` go through `crea_server`.

- **Model-visible** means name + description + `inputSchema` as compact JSON:
  what a client hands the model for each tool.
- **Wire** is the whole tool object, with `outputSchema`, `annotations` and
  `_meta` too. It is reported, but kept apart from the model-visible count.
- **Breakdowns** are by kind tag (`tool_taxonomy.KINDS`), by module and by tool.
- **Repeated blocks** are those from the 27 Oct analysis:
  - `Vigenza:` and `Precisione:` blocks: the label line and its continuation
    lines, up to a blank line or the next `Label:` line. An unlabelled sentence
    right after the block (for example «Spesso chiamato dopo…») is counted in,
    so the figure is an upper bound. The rule is the analysis's own, kept so
    the numbers stay comparable;
  - the usage lines (`Restituisce`, `Usa questo`, `Chaining`, `NON usare`…);
  - the `accetta_precisione` parameter;
  - the `anyOf [{X}, {null}]` + `default: null` overhead over a plain `{X}`;
  - `additionalProperties: false`;
  - collapsible whitespace.

## What `outputs` counts

Each call goes through `call_tool_mcp`, so the report sees the raw
`CallToolResult`. For each call it reports:

- the text content and its token estimate;
- `structuredContent` (compact JSON), and whether it only repeats the text:
  either `{"result": text}` or the JSON the text already serializes;
- `_meta`;
- the whole result on the wire.

The replay pins the clock (`LEGAL_NOW=2026-10-21T12:00:00`), turns the caches
off and fixes the hash seed. Two replays of one checkout give identical
reports. That was checked.

The fixed calls are:

- `cite_law` on art. 1284 c.c. and on art. 6 GDPR;
- `fetch_full_act` on the Statuto dei lavoratori (no cap);
- `cerca_giurisprudenza`, then `leggi_sentenza` on Cass. 21332/2024;
- `leggi_sentenza_cgue` on C-311/19;
- `cerdef_leggi_provvedimento` on SS.UU. 24823/2015;
- `leggi_atto_gazzetta` on D.Lgs. 101/2018;
- four calculators.

## Token estimate

No tokenizer for Claude models runs offline, and none is installed. The
script uses the rule of the 27 Oct analysis:

- prose (descriptions, result strings) counts at characters / 3.5;
- JSON structure counts at characters / 3.

The numbers are for comparing runs with each other. They are not a bill. When
the tool-choice run happens, its API `usage` gives exact counts. That run can
also calibrate the estimate: count one `tools/list` with the token-counting
endpoint and record the ratio here.

## Cross-check with the 27 Oct analysis

The measures were run on `develop` 2631ea1 with fastmcp 3.4.2.

| Quantity | 27 Oct analysis | This harness |
|---|---|---|
| tools | 231 | 231 |
| model-visible chars | ~390k | 390,052 |
| tokens | ~116k | 116,080 |
| tool descriptions | ~177k | 177,049 |
| parameter descriptions | ~116k | 115,662 |
| calcolo / redazione / giurisprudenza / normativa | 248k / 58k / 39k / 23k | 247,725 / 58,018 / 38,871 / 23,185 |
| Vigenza + Precisione | 77k (175 / 173) | 77,121 (175 / 173) |
| `accetta_precisione` | 74 tools, 33k, ~9.8k tok | 74 tools, 33,078, 9,800 tok |
| `anyOf`-null / `additionalProperties:false` | 164 → 7k / 231 → 6.7k | 164 → 7,052 / 231 → 6,699 |
| server instructions | 6k | 6,013 |
| normativa + giurisprudenza + autorità | 52 tools, ~22.6k tok | 52 tools, 22,187 tok (`crea_server`) |
| outputs: `cite_law` 1284, `leggi_sentenza` 21332/2024, `cerca_giurisprudenza` | 8,259 / 22,093 / 3,334 | 8,259 / 22,093 / 3,334 |

Every number matches. One method differs without changing a number today:
this harness reads parameter descriptions at any depth of the schema, while
the analysis read only the first level. On `develop` both give 115,662
characters, because no tool nests a described schema yet.

## Tool-choice run (design only)

The task set is `docs/benchmark/token-tasks.json`: 20 tasks.

### Families covered

| Family | Tasks |
|---|---|
| normativa | 4 |
| giurisprudenza (Cassazione, CeRDEF, CGUE, Consulta) | 6 |
| autorità | 1 |
| calcolo | 7 |
| redazione | 1 |
| workflow (two tools) | 1 |

### Sources

The tasks are drawn from `tests/test-queries.md` and from the calls of the
output measure. No private benchmark content is used.

### Format of a task

| Field | Content |
|---|---|
| `prompt` | the user's request, in Italian |
| `expected.required` | tools that must all be called |
| `expected.required_any` | the alternative: one of these must be called |
| `expected.order` | optional order for `required` |
| `expected.acceptable` | tools that cost nothing in the score |
| `expected.forbidden` | tools that cost points |
| `max_calls` | the call budget |
| `facts` | case-insensitive regexes searched in the final answer, each with `verified_by` |

`verified_by` takes three values:

- `tool@clock`: the expected tool gave the fact under the pinned clock;
- `tape`: the fact is in the recorded source text;
- `to_verify`: drafted from legal knowledge. Confirm it against the source on
  the first run before it counts.

A unit test keeps every tool name in the file in step with the registered tools.

Two tasks are traps on purpose:

- **T04** asks for one article of the Statuto dei lavoratori.
  `fetch_full_act` is forbidden: it costs about 15k tokens for one article.
- **T17** asks for an appeal deadline. `scadenze_impugnazioni` is the right
  tool; the generic `scadenza_processuale` is a worse choice.

### Running it

1. Start the server with `LEGAL_PROFILE=full`, `LEGAL_NOW` pinned as in the
   file, and `LEGAL_CACHE=off`.
2. Give each task to a model in a fresh conversation, with this server as its
   only tool source.
3. Run every task 3 times on the base and 3 times on the head, with the same
   model and default sampling.
4. Source tasks need the network. Record a tape during the base run and replay
   it on the head. Where the head asks for something not on the tape, go live
   and flag the task.

### Scores per run

| Score | How it is computed |
|---|---|
| tool choice | 1 if every `required` tool was called (or one of `required_any`), 0 otherwise. Then 0.5 is subtracted if a `forbidden` tool was called, and 0.25 if `order` was broken. Also log whether the **first** call was a required tool. |
| correctness | facts matched / facts scored. `to_verify` facts are left out until they are confirmed. |
| tokens | from the API `usage`: input split into session start (system + tools), tool results and the model's own turns; cache reads and writes separately; output tokens. |
| calls | number of tool calls; going over `max_calls` is flagged, not penalised twice. |

### Acceptance rule for a cut

A cut passes when all three hold:

1. Median input tokens per task go down.
2. No task goes from pass to fail on the majority of its 3 runs, for tool
   choice or for correctness.
3. Aggregate correctness does not drop.

A cut that saves tokens but fails rule 2 on any task is not merged as is.

**Never cut, whatever the saving.** The «AGGIORNAMENTO (n)» notes of a Normattiva
article and the Corte costituzionale declarations of illegitimacy they carry are part
of the text a lawyer reads (art. 3 d.lgs. 23/2015 still prints the words C. cost.
194/2018 struck down). A «notes on request» switch, if one comes, must leave them in
by default and out of its scope (decided on 29 Oct 2026, with VisuaLex).

### Cost order of magnitude

- 20 tasks × 3 runs × 2 configurations = 120 conversations.
- With the full profile, each conversation starts with about 118k
  tool-definition and instruction tokens, plus tool results: up to about 15k
  for T04 done wrong, otherwise mostly 1–8k.
- That is about 15–18M input tokens before prompt caching. Caching the tool
  block cuts most of the session-start share.
- Multiply by the current price list on the day of the run. The decision to
  run it belongs to the owners.

## Findings while building (not fixed here: shipped code is out of scope)

1. **`LEGAL_PROFILE` does not narrow the server instructions.** A profiled
   server still sends all 6,013 characters, which name tools the profile hid.
   `crea_server` and `LEGAL_BROCARDI=off` do narrow them (4,296 characters for
   normativa + giurisprudenza + autorità). See `server.py`, around the
   `_instructions_for` call.
2. **Under any profile, the first `tools/list` prints a wrong warning on
   stderr**: "tool_annotations: policy names no longer registered: …".
   `ToolAnnotationMiddleware._warn_on_drift` compares the policy with the
   *visible* tools, not the registered ones.
3. **Every text result is sent twice.** Calculators send their JSON as text
   and again as `structuredContent`; text tools send `{"result": text}`. The
   wire is about 2× the text on all 12 calls.
4. **`fetch_full_act` has no cap.** It returns 52.6k characters (about 15k
   tokens) for the Statuto dei lavoratori.
5. **`cerca_giurisprudenza` snippets carry `<em>` tags**, and the
   `leggi_sentenza` text repeats the Italgiure page header.
6. **The CGUE call reads a different case from the one it was taken for.**
   `scripts/replay_mcp_outputs.py` uses CELEX `62019CJ0311` for its CGUE call.
   That is C-311/19 *Bonver Win*, not Schrems II (C-311/18, which is
   `62018CJ0311`). The call works; only a reader expecting Schrems II would be
   misled.
7. **`decreto_ingiuntivo` writes amounts in English format**: «Euro 25,000.00»
   in an Italian deed.
