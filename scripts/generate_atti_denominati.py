#!/usr/bin/env python3
"""Generate (and drift-check) the ATTI_DENOMINATI base rows from BROCARDI_CODICI.

The Brocardi keys embed each act's extremes — "Legge fallimentare(R.D. 16 marzo
1942, n. 267)". This script turns them into `_ATTI_DENOMINATI_SPEC` rows to be
pasted into src/lib/visualex/map.py. It is deliberately one-shot: the checked-in
table is the source of truth, so an act can be corrected without touching a
display label, and every row stays reviewable in a diff.

    python scripts/generate_atti_denominati.py          # emit rows
    python scripts/generate_atti_denominati.py --check   # report Brocardi acts missing from the table
"""

import json
import sys

sys.path.insert(0, ".")

from src.lib.visualex.map import BROCARDI_CODICI, parse_brocardi_estremi  # noqa: E402


def parse(key: str) -> dict | None:
    """One spec row from a Brocardi label; None for labels without extremes."""
    estremi = parse_brocardi_estremi(key)
    if not estremi or estremi["tipo_atto"] == "regolamento ue":
        return None  # EU acts live in ATTI_NOTI, not here
    label = key.split("(")[0].strip().replace('"', "").replace("[ABROGATO]", "").strip()
    return {
        "tipo_atto": estremi["tipo_atto"],
        "data": estremi["data"],
        "numero": estremi["numero_atto"],
        "alias": label.lower(),
    }


def main() -> int:
    rows, skipped = [], []
    for key in BROCARDI_CODICI:
        parsed = parse(key)
        (rows.append(parsed) if parsed else skipped.append(key))

    if "--check" in sys.argv:
        # The question is whether the resolver handles the act at all — an act
        # covered by ATTI_NOTI or NORMATTIVA_URN_CODICI needs no row here.
        from src.lib.visualex.map import resolve_atto

        missing = [r for r in rows if not resolve_atto(r["alias"])]
        for r in missing:
            print(f"MANCANTE: {r['alias']} -> {r['tipo_atto']} {r['data']} n. {r['numero']}")
        print(f"\n{len(rows) - len(missing)}/{len(rows)} atti Brocardi risolvibili")
        return 1 if missing else 0

    for r in rows:
        alias = json.dumps(r["alias"], ensure_ascii=False)
        print(f'    ("{r["tipo_atto"]}", "{r["data"]}", "{r["numero"]}", [{alias}]),')
    print(f"\n# {len(rows)} righe generate; {len(skipped)} chiavi senza estremi utilizzabili:", file=sys.stderr)
    for s in skipped:
        print(f"#   {s[:80]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
