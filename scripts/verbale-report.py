#!/usr/bin/env python3
"""The refusal ledger's monthly report, on a schedule.

`verbale_mensile` answers "how did this month go" inside a conversation; this
script is the recurring habit around the same ledger: a cron line, a
pre-release check, or the first thing you run when a caller says "the tool
refused again". It reads the same file the middleware writes
(`<MCP_CACHE_DIR>/refusals.jsonl`) with the same aggregation the tool uses
(`src/lib/_refusals.py`), renders it, and exits non-zero when the current month
is *worse* than the last one -- so the same line that generates the report can
gate a release.

    python3 scripts/verbale-report.py                     # terminal report
    python3 scripts/verbale-report.py --out report.md     # markdown file
    python3 scripts/verbale-report.py --json              # machine-readable
    python3 scripts/verbale-report.py --mesi 12 --strict  # fail on regression

`--strict` exits 1 when the current month's total is greater than the previous
month's (`delta_mese_precedente > 0`) or when the ledger is off: a silent
monitor is not a monitor. Without `--strict` the exit code only reports real
failures (unreadable ledger).

Keeping the ledger on (`LEGAL_REFUSAL_LEDGER=on` in the host env) is what makes
this report worth anything; the script prints the reminder instead of
pretending an empty file is an empty month.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin" / "server"))

from src.lib import _refusals  # noqa: E402


def _render_markdown(report: dict) -> str:
    righe = report.get("serie") or []
    out = ["# Verbale dei rifiuti — serie mensile", ""]
    grafico = report.get("grafico") or []
    if grafico:
        out.append("```")
        out.extend(grafico)
        out.append("```")
        out.append("")
    out.append("| mese | rifiuti | accettazioni | Δ | top tool | top tabella |")
    out.append("|------|---------|--------------|---|----------|-------------|")
    for riga in righe:
        delta = riga.get("delta_mese_precedente")
        delta_s = "—" if delta is None else ("%+d" % delta)
        out.append(
            "| %s | %d | %d | %s | %s | %s |"
            % (
                riga["mese"],
                sum(riga.get("rifiuti", {}).values()),
                sum(riga.get("accettazioni", {}).values()),
                delta_s,
                riga.get("top_tool") or "—",
                riga.get("top_tabella") or "—",
            )
        )
    out.append("")
    current = righe[-1] if righe else None
    if current:
        out.append("## Mese corrente (%s)" % current["mese"])
        out.append("")
        for label, key in (("Tool", "rifiuti"), ("Tabelle", "tabelle")):
            conteggi = current.get(key) or {}
            if conteggi:
                out.append(
                    "- **%s**: %s"
                    % (
                        label,
                        ", ".join("%s ×%d" % (k, v) for k, v in conteggi.items()),
                    )
                )
        if not any((current.get(k) for k in ("rifiuti", "tabelle", "accettazioni"))):
            out.append("- Nessun evento registrato: o il verbale è spento, o il mese è andato davvero liscio.")
    out.append("")
    out.append("> Il verbale registra solo rifiuti e accettazioni di precisione — mai dati di causa.")
    return "\n".join(out)


def _render_terminal(report: dict) -> str:
    righe = report.get("serie") or []
    out = ["Verbale dei rifiuti — serie mensile (%d mesi)" % len(righe)]
    for riga in report.get("grafico") or []:
        out.append("  " + riga)
    out.append("")
    for riga in righe:
        delta = riga.get("delta_mese_precedente")
        delta_s = "·" if delta is None else ("%+d" % delta)
        out.append(
            "  %s  rifiuti=%-3d accett=%-3d Δ=%-4s top=%s"
            % (
                riga["mese"],
                sum(riga.get("rifiuti", {}).values()),
                sum(riga.get("accettazioni", {}).values()),
                delta_s,
                riga.get("top_tool") or "—",
            )
        )
    out.append("(registra solo rifiuti/accettazioni: mai dati di causa)")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mesi", type=int, default=6, help="finestra in mesi (default 6)")
    parser.add_argument("--json", action="store_true", help="output JSON invece di testo")
    parser.add_argument("--out", type=Path, default=None, help="scrivi il report su file")
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 se il mese corrente e' peggiorato o il verbale e' spento",
    )
    args = parser.parse_args()

    os.environ.setdefault("LEGAL_REFUSAL_LEDGER", "on")
    report = _refusals.monthly(args.mesi)

    if not report.get("disponibile"):
        print(report.get("motivo", "verbale non disponibile"), file=sys.stderr)
        return 1 if args.strict else 0
    if not report.get("serie"):
        print("nessun dato nel verbale: LEGAL_REFUSAL_LEDGER era acceso?", file=sys.stderr)
        return 1 if args.strict else 0

    if args.json:
        body = json.dumps(report, ensure_ascii=False, indent=2)
    else:
        body = _render_markdown(report) if args.out else _render_terminal(report)
    if args.out:
        args.out.write_text(body + "\n", encoding="utf-8")
        print("report scritto: %s" % args.out)
    else:
        print(body)

    if args.strict:
        righe = report["serie"]
        corrente, precedente = righe[-1], (righe[-2] if len(righe) > 1 else None)
        rifiuti_ora = sum(corrente.get("rifiuti", {}).values())
        rifiuti_prima = sum(precedente.get("rifiuti", {}).values()) if precedente else 0
        if precedente is not None and rifiuti_ora > rifiuti_prima:
            print(
                "REGRESSIONE: %d rifiuti questo mese contro %d il mese scorso"
                % (rifiuti_ora, rifiuti_prima),
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
