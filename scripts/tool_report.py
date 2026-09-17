#!/usr/bin/env python3
"""Render the 221-tool surface as a self-contained HTML page.

The page groups every tool by what a host needs to know before running it:

  * read-only, local      -- pure calculations over the bundled tables
  * read-only, external   -- looks things up on Normattiva/EUR-Lex/Italgiure/...
  * writes to disk        -- 12 cache refreshers and 5 document generators
  * (within the last two) which cache directory each one can touch

Everything is derived from the same audit that produces the annotations, so the
report cannot disagree with the policy the server advertises.

Usage:

    python scripts/tool_report.py                  # -> docs/tool-report.html
    python scripts/tool_report.py --out /tmp/x.html
    python scripts/tool_report.py --json           # the raw grouping
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from audit_tool_annotations import REPO, Audit, cache_inventory, verify_caches  # noqa: E402

DEFAULT_OUT = REPO / "docs/tool-report.html"

# What each external client actually is, for the reader who has never seen the
# inside of this repo. Names come from src/lib/<client>.
CLIENT_SOURCES = {
    "brocardi": "Brocardi.it (article commentary)",
    "cerdef": "Corte di Cassazione, sezione tributaria",
    "cgue": "Corte di giustizia UE (CELLAR SPARQL)",
    "consob": "CONSOB delibere",
    "corte_cost": "Corte costituzionale (open data)",
    "gazzetta": "Gazzetta Ufficiale (ELI)",
    "giustizia_amm": "Giustizia amministrativa (TAR/CdS)",
    "gpdp": "Garante privacy",
    "italgiure": "Italgiure (Cassazione)",
    "eu_implementation": "EUR-Lex recepimento direttive",
    "parlamento": "dati.senato.it / dati.camera.it (SPARQL)",
    "visualex": "Normattiva / EUR-Lex (Visualex)",
    "vies": "VIES (partite IVA UE)",
}

GROUPS = (
    ("local", "Read-only, local", "No network, no disk: arithmetic over the bundled JSON tables."),
    ("external", "Read-only, external", "Reads only, but the answer comes from a service outside the process."),
    ("cache", "Writes to disk: cache refresh", "Only reachable write is the local cache; annotated readOnlyHint: false."),
    ("document", "Writes to disk: documents", "Produces a file the user asked for (PDF/DOCX/XLSX)."),
)

STYLE = """
:root {
  --bg: #0f1115; --panel: #171a21; --line: #262b36; --ink: #e8eaf0;
  --dim: #9aa3b2; --accent: #7aa2f7; --warn: #e0af68; --ok: #9ece6a;
}
@media (prefers-color-scheme: light) {
  :root { --bg: #f7f8fa; --panel: #fff; --line: #e2e6ee; --ink: #1a1d24;
          --dim: #5c6575; --accent: #3b5bdb; --warn: #b8860b; --ok: #2f7a2f; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem clamp(1rem, 4vw, 3rem) 4rem; background: var(--bg);
       color: var(--ink); font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
h1 { font-size: 1.6rem; margin: 0 0 .3rem; }
h2 { font-size: 1.1rem; margin: 2.4rem 0 .2rem; }
.sub { color: var(--dim); margin: 0 0 1.6rem; }
.cards { display: flex; flex-wrap: wrap; gap: .75rem; margin: 1.2rem 0 0; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
        padding: .7rem .9rem; min-width: 9.5rem; }
.card b { display: block; font-size: 1.5rem; font-variant-numeric: tabular-nums; }
.card span { color: var(--dim); font-size: .82rem; }
table { width: 100%; border-collapse: collapse; background: var(--panel);
        table-layout: fixed; border: 1px solid var(--line); border-radius: 10px;
        overflow: hidden; margin-top: .6rem; }
td, th { overflow-wrap: anywhere; }
th:nth-child(1), td:nth-child(1) { width: 21%; }
th:nth-child(2), td:nth-child(2) { width: 17%; }
th:nth-child(3), td:nth-child(3) { width: 13%; }
th, td { text-align: left; padding: .45rem .7rem; border-bottom: 1px solid var(--line);
         vertical-align: top; font-size: .88rem; }
th { color: var(--dim); font-weight: 600; font-size: .78rem; text-transform: uppercase;
     letter-spacing: .04em; }
tr:last-child td { border-bottom: 0; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85em; }
.tag { display: inline-block; padding: .05rem .4rem; border-radius: 999px;
       border: 1px solid var(--line); color: var(--dim); font-size: .74rem; margin-right: .25rem; }
.tag.net { color: var(--warn); border-color: var(--warn); }
.tag.disk { color: var(--accent); border-color: var(--accent); }
.tag.ro { color: var(--ok); border-color: var(--ok); }
.tool { font-weight: 600; }
.why { color: var(--dim); }
details { margin-top: .8rem; }
summary { cursor: pointer; color: var(--accent); }
footer { margin-top: 3rem; color: var(--dim); font-size: .8rem; }
"""


def vintage_lines(src: pathlib.Path) -> dict[str, str]:
    """One line per shipped table, read from its own `_vintage` block.

    Read from the JSON rather than through `src.lib._data`, so the report needs
    no running server and shows exactly what an answer would append.
    """
    lines: dict[str, str] = {}
    for path in sorted((src / "data").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        block = payload.get("_vintage") if isinstance(payload, dict) else None
        block = block or {}
        fonte = block.get("fonte", "fonte non dichiarata")
        if block.get("verifica", "da_verificare") == "da_verificare":
            lines[path.stem] = "%s — PROVENIENZA E DATA NON VERIFICATE" % fonte
        elif block.get("copre_fino_a"):
            lines[path.stem] = "%s — copre fino al %s" % (fonte, block["copre_fino_a"])
        elif block.get("aggiornato_al"):
            lines[path.stem] = "%s — aggiornati al %s" % (fonte, block["aggiornato_al"])
        else:
            lines[path.stem] = "%s — periodo di validità non dichiarato" % fonte
    return lines


def group_tools(audit: Audit) -> dict[str, list[dict]]:
    """Split the surface into the four groups the report renders."""
    vintages = vintage_lines(audit.src)
    grouped: dict[str, list[dict]] = {key: [] for key, _, _ in GROUPS}
    for fq, tool in sorted(audit.tools.items(), key=lambda item: item[1]):
        evidence = audit.writes_for(fq)
        clients = audit.upstream_clients(fq)
        entry = {
            "tool": tool,
            "module": fq.rsplit(".", 1)[0].replace("src.tools.", "").replace("src.", ""),
            "clients": clients,
            "caches": audit.cache_locations(fq),
            "evidence": evidence,
            "tables": [
                (name, vintages.get(name, "vintage non dichiarato"))
                for name in audit.reads(fq)
            ],
        }
        if evidence:
            # Same rule the annotations use: a cache refresh is a write, but not
            # a destructive one, and everything else that writes is producing a
            # file for the user.
            entry["group"] = "cache" if audit.is_cache_only(fq) else "document"
        else:
            entry["group"] = "external" if clients else "local"
        grouped[entry["group"]].append(entry)
    return grouped


def _cells(entry: dict) -> str:
    tags = []
    if entry["clients"]:
        tags.append('<span class="tag net">external</span>')
    if entry["caches"]:
        tags.append('<span class="tag disk">cache</span>')
    if entry["group"] == "local":
        tags.append('<span class="tag ro">read-only</span>')
    detail = ""
    if entry["clients"]:
        detail = "; ".join(
            "%s &mdash; %s" % (html.escape(c), html.escape(CLIENT_SOURCES.get(c, "external service")))
            for c in entry["clients"]
        )
    elif entry["group"] in ("cache", "document"):
        detail = ", ".join("`%s`" % html.escape(item) for item in entry["evidence"])
    cache = "<br>".join("<code>%s</code>" % html.escape(c) for c in entry["caches"]) or "&mdash;"
    tables = "<br>".join(
        '<code>%s</code> <span class="dim">%s</span>' % (html.escape(name), html.escape(fonte))
        for name, fonte in entry["tables"]
    )
    why = "<br>".join(part for part in (detail, tables) if part) or "&mdash;"
    return (
        '<td class="tool"><code>%s</code>%s</td><td><code>%s</code></td>'
        "<td>%s</td><td class=\"why\">%s</td>"
        % (
            html.escape(entry["tool"]),
            (" " + "".join(tags)) if tags else "",
            html.escape(entry["module"]),
            cache,
            why,
        )
    )


def render_html(audit: Audit, grouped: dict[str, list[dict]]) -> str:
    total = sum(len(rows) for rows in grouped.values())
    problems = verify_caches(audit)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>mcp-legal-it tool surface</title>",
        "<style>%s</style></head><body>" % STYLE,
        "<h1>mcp-legal-it &mdash; tool surface</h1>",
        '<p class="sub">%d tools, grouped by what they do before a host runs them. '
        "Generated %s by <code>scripts/tool_report.py</code> from the same audit that "
        "stamps the MCP annotations, so this page and the policy cannot disagree.</p>"
        % (total, now),
        '<div class="cards">',
    ]
    for key, title, _ in GROUPS:
        out.append(
            '<div class="card"><b>%d</b><span>%s</span></div>'
            % (len(grouped[key]), title)
        )
    out.append(
        '<div class="card"><b>%d</b><span>open-world tools</span></div>'
        % len({e["tool"] for rows in grouped.values() for e in rows if e["clients"]})
    )
    out.append(
        '<div class="card"><b>%d</b><span>tools with provenance</span></div>'
        % sum(1 for rows in grouped.values() for entry in rows if entry["tables"])
    )
    out.append(
        '<div class="card"><b>%s</b><span>cache audit</span></div>'
        % ("clean" if not problems else "%d issues" % len(problems))
    )
    out.append("</div>")

    for key, title, blurb in GROUPS:
        rows = grouped[key]
        out.append("<h2>%s &mdash; %d tools</h2>" % (html.escape(title), len(rows)))
        out.append('<p class="sub">%s</p>' % blurb)
        if not rows:
            out.append('<p class="sub">None.</p>')
            continue
        out.append(
            "<table><thead><tr><th>Tool</th><th>Module</th><th>Cache</th>"
            "<th>Reaches / evidence</th></tr></thead><tbody>"
        )
        for entry in rows:
            out.append("<tr>%s</tr>" % _cells(entry))
        out.append("</tbody></table>")

    out.append("<h2>How the hints are derived</h2>")
    out.append(
        '<p class="sub">An AST walk over every <code>@mcp.tool()</code> call graph, '
        "not a hand-kept list: a tool is read-only when nothing reachable opens a file "
        "for writing or mutates an HTTP request, and open-world when its chain reaches "
        "one of the <code>src/lib</code> clients. "
        "<code>scripts/audit_tool_annotations.py --check</code> fails the suite when the "
        "committed policy drifts from the source, and "
        "<code>tests/unit/test_read_only_contract.py</code> calls all 168 local ones and "
        "asserts the filesystem did not change, and "
        "<code>tests/unit/test_golden_calcoli.py</code> pins what they answer "
        "(<code>tests/fixtures/golden/calcoli_locali/</code>, one file per data table) "
        "with the clock frozen "
        "via <code>LEGAL_TODAY</code>/<code>LEGAL_NOW</code>, so a refreshed rate or a "
        "corrected parameter fails the suite instead of silently changing the advice. "
        "<code>LEGAL_CACHE=off</code> keeps the cache writers off the disk entirely. "
        "The tables listed for a tool are the provenance a host sees in the answer: "
        "every tool that opens a hand-maintained table carries the table and its "
        "vintage in <code>dati_applicati</code>, and the audit fails when a tool reads "
        "a table without declaring it, declares one its code never reads, or leaves a "
        "shipped table that no tool applies.</p>"
    )
    if problems:
        out.append("<details open><summary>Cache audit problems</summary><ul>")
        for problem in problems:
            out.append("<li>%s</li>" % html.escape(problem))
        out.append("</ul></details>")

    rows = cache_inventory(audit)
    out.append("<h2>Declared caches</h2>")
    out.append(
        "<table><thead><tr><th>Location</th><th>Files</th><th>Retention</th>"
        "<th>Written by</th><th>Tools</th></tr></thead><tbody>"
    )
    for row in rows:
        out.append(
            "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td><code>%s</code></td>"
            "<td>%d</td></tr>"
            % (
                html.escape(row["dir"]),
                "<br>".join("<code>%s</code>" % html.escape(f) for f in row["files"]),
                html.escape(row["retention"]),
                html.escape(row["module"]),
                len(row["tools"]),
            )
        )
    out.append("</tbody></table>")
    out.append(
        "<footer>Regenerate with <code>python scripts/tool_report.py</code>. "
        "Annotation policy: <code>plugin/server/src/tool_annotations.py</code>. "
        "Cache inventory: <code>docs/cache-inventory.md</code>.</footer>"
    )
    out.append("</body></html>")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", default=str(REPO / "plugin/server/src"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json", action="store_true", help="print the grouping instead")
    args = parser.parse_args()

    audit = Audit(pathlib.Path(args.src))
    grouped = group_tools(audit)

    if args.json:
        print(
            json.dumps(
                {
                    "counts": {key: len(rows) for key, rows in grouped.items()},
                    "groups": grouped,
                    "problems": verify_caches(audit),
                },
                indent=1,
            )
        )
        return 0

    out = pathlib.Path(args.out)
    out.write_text(render_html(audit, grouped), encoding="utf-8")
    counts = {key: len(rows) for key, rows in grouped.items()}
    print(
        "wrote %s | local %d, external %d, cache %d, documents %d"
        % (out, counts["local"], counts["external"], counts["cache"], counts["document"])
    )
    for problem in verify_caches(audit):
        print("cache audit: %s" % problem, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
