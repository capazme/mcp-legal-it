#!/usr/bin/env python3
"""Count the requests each reader sends to the sources, cold then warm.

The load baseline of the VisuaLex migration: the 19 requests VisuaLex's timing
harness sends (VisuaLexAPI ``services/visualex/scripts/collector_timing.py``, PR
#252), asked through ``mcp_legal_it.api``. Every request that reaches httpx's
network transport is counted, per row and per host, so two checkouts can be
compared: a migration step may not make any row send more requests.

    # the checkout this script sits in
    python scripts/measure_requests.py --out /tmp/after.json
    # another checkout (its package directory first on the path)
    python scripts/measure_requests.py --package /tmp/base/plugin/server --out /tmp/before.json
    python scripts/measure_requests.py --compare /tmp/before.json /tmp/after.json

It talks to the real sources, one request at a time: run it a few times, never
in a loop. Rows VisuaLex answers and mcp-legal-it does not yet (a past version,
a whole-act tree, an EU index, a decision PDF, a CGUE judgment by case) are
listed with the answer mcp-legal-it gives today, usually without a request.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: (row, call): the rows of VisuaLex's harness, in its order.
ROWS: list[tuple[str, str]] = [
    ("cc_2043", "testo_articolo('art. 2043 c.c.')"),
    ("cc_2043_2044", "testi_articoli(['art. 2043 c.c.', 'art. 2044 c.c.'])"),
    ("cpc_183", "testo_articolo('art. 183 c.p.c.')"),
    ("cp_612bis", "testo_articolo('art. 612-bis c.p.')"),
    ("l241_1990_art1_3", "testi_articoli(['art. 1 l. 241/1990', 'art. 2 l. 241/1990', 'art. 3 l. 241/1990'])"),
    ("dlgs231_year_only", "testo_articolo('art. 5 d.lgs. 231/2001')"),
    ("cc_1284_historical", "riferimento_da_parametri('codice civile', '1284', data_versione='2010-01-01')"),
    ("tree_l241_1990", "albero_atto('l. 241/1990')"),
    ("rubriche_l241_1990", "indice_atto('l. 241/1990')"),
    ("tree_cc", "albero_atto('c.c.')"),
    ("rubriche_cc", "indice_atto('c.c.')"),
    ("gdpr_art6", "testo_articolo('art. 6 GDPR')"),
    ("gdpr_art17", "testo_articolo('art. 17 GDPR')"),
    ("rubriche_gdpr", "(no EU act index in mcp-legal-it yet)"),
    ("cass_civ_12449_2024", "leggi_decisione(cassazione, 12449, 2024, civile)"),
    ("cass_pdf_12449_2024", "(no decision PDF in mcp-legal-it yet)"),
    ("corte_cost_242_2019", "leggi_decisione(corte_costituzionale, 242, 2019)"),
    ("cgue_634_2021", "leggi_decisione(corte_giustizia_ue, 634, 2021)"),
    ("search_2043_cc", "giurisprudenza_su_articolo('art. 2043 c.c.', archivio='civile')"),
]


async def _call(api, row: str, canale: str):
    if row in ("cc_2043", "cpc_183", "cp_612bis", "dlgs231_year_only", "gdpr_art6", "gdpr_art17"):
        ref = {"cc_2043": "art. 2043 c.c.", "cpc_183": "art. 183 c.p.c.", "cp_612bis": "art. 612-bis c.p.",
               "dlgs231_year_only": "art. 5 d.lgs. 231/2001", "gdpr_art6": "art. 6 GDPR",
               "gdpr_art17": "art. 17 GDPR"}[row]
        t = await api.testo_articolo(ref, canale=canale)
        return t.esito, len(t.article_text or "")
    if row == "cc_2043_2044":
        ts = await api.testi_articoli(["art. 2043 c.c.", "art. 2044 c.c."], canale=canale)
        return ",".join(t.esito for t in ts), sum(len(t.article_text or "") for t in ts)
    if row == "l241_1990_art1_3":
        ts = await api.testi_articoli([f"art. {n} l. 241/1990" for n in (1, 2, 3)], canale=canale)
        return ",".join(t.esito for t in ts), sum(len(t.article_text or "") for t in ts)
    if row == "cc_1284_historical":
        r = api.riferimento_da_parametri("codice civile", "1284", data_versione="2010-01-01")
        return r.esito, 0
    if row in ("tree_l241_1990", "tree_cc"):
        a = await api.albero_atto("l. 241/1990" if "l241" in row else "c.c.")
        return a.esito, a.count
    if row in ("rubriche_l241_1990", "rubriche_cc"):
        i = await api.indice_atto("l. 241/1990" if "l241" in row else "c.c.")
        return i.esito, i.count
    if row in ("rubriche_gdpr", "cass_pdf_12449_2024"):
        return "non_disponibile", 0
    if row == "cass_civ_12449_2024":
        d = await api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=12449, anno=2024,
                                                               archivio="civile"))
        return d.esito, len(getattr(d.testo_grezzo, "testo", "") or "") if d.testo_grezzo else 0
    if row == "corte_cost_242_2019":
        d = await api.leggi_decisione(api.RiferimentoDecisione(corte="corte_costituzionale", numero=242, anno=2019))
        return d.esito, len(getattr(d.testo_grezzo, "testo", "") or "") if d.testo_grezzo else 0
    if row == "cgue_634_2021":
        d = await api.leggi_decisione(api.RiferimentoDecisione(corte="corte_giustizia_ue", numero=634, anno=2021))
        return d.esito, 0
    if row == "search_2043_cc":
        r = await api.giurisprudenza_su_articolo("art. 2043 c.c.", archivio="civile")
        return r.esito, len(r.decisioni)
    raise KeyError(row)


async def _measure(package: Path | None, canale: str) -> dict:
    if package:
        sys.path.insert(0, str(package))
    else:
        sys.path.insert(0, str(REPO / "plugin" / "server"))
    import httpx

    from mcp_legal_it import api

    sent: Counter = Counter()
    original = httpx.AsyncHTTPTransport.handle_async_request

    async def counting(self, request):
        sent[request.url.host] += 1
        return await original(self, request)

    httpx.AsyncHTTPTransport.handle_async_request = counting
    out: dict = {"package": str(package or "this checkout"), "canale": canale, "rows": {}}
    with tempfile.TemporaryDirectory() as cache:
        api.configura(cache_dir=cache)
        for passata in ("cold", "warm"):
            for row, _ in ROWS:
                sent.clear()
                t0 = time.monotonic()
                try:
                    esito, size = await _call(api, row, canale)
                except Exception as exc:  # a row that crashes is a row to read, not a stop
                    esito, size = f"crash: {type(exc).__name__}: {exc}"[:160], 0
                out["rows"].setdefault(row, {})[passata] = {
                    "requests": sum(sent.values()), "hosts": dict(sent), "s": round(time.monotonic() - t0, 2),
                    "esito": esito, "size": size,
                }
                print(f"{passata:4} {row:22} {sum(sent.values()):3} req {time.monotonic() - t0:6.2f} s  {esito}",
                      file=sys.stderr)
        api.configura()
    return out


def _compare(before: Path, after: Path) -> int:
    a, b = json.loads(before.read_text()), json.loads(after.read_text())
    print(f"Normattiva channel: before `{a.get('canale', 'akn')}`, after `{b.get('canale', 'akn')}`.\n")
    print("| row | call | cold before | cold after | warm before | warm after | s cold before → after | outcome after |")
    print("|---|---|---|---|---|---|---|---|")
    calls = dict(ROWS)
    more = []
    tot = Counter()
    for row, _ in ROWS:
        x, y = a["rows"][row], b["rows"][row]
        for p in ("cold", "warm"):
            tot[f"{p}_before"] += x[p]["requests"]
            tot[f"{p}_after"] += y[p]["requests"]
            if y[p]["requests"] > x[p]["requests"]:
                more.append(f"{row} ({p}): {x[p]['requests']} → {y[p]['requests']}")
        print(f"| {row} | `{calls[row]}` | {x['cold']['requests']} | {y['cold']['requests']} | "
              f"{x['warm']['requests']} | {y['warm']['requests']} | {x['cold']['s']} → {y['cold']['s']} | "
              f"{y['cold']['esito']} |")
    print(f"| **total** | | {tot['cold_before']} | {tot['cold_after']} | {tot['warm_before']} | "
          f"{tot['warm_after']} | | |")
    if more:
        print("\nRows with MORE requests:\n" + "\n".join(f"- {m}" for m in more))
        return 1
    print("\nNo row sends more requests.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, help="where to write the measures (JSON)")
    parser.add_argument("--package", type=Path, help="directory holding the mcp_legal_it package to measure")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--canale", choices=("akn", "html"), default="html",
                        help="the Normattiva channel the article rows read (a checkout before the "
                             "HTML channel supports only akn)")
    args = parser.parse_args()
    if args.compare:
        return _compare(*args.compare)
    if not args.out:
        parser.error("--out or --compare")
    result = asyncio.run(_measure(args.package, args.canale))
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
