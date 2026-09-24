"""Human review of a wave's items (DESIGN §8.2): export review packets,
ingest verdicts, apply the pre-registered inclusion rule.

    python -m benchmarks.limes.bank.review export --wave wave-1 \
        --reviewers "Anna,Bruno,Carla" [--out DIR] [--q-sample 20]
    python -m benchmarks.limes.bank.review ingest --wave wave-1 [--dir DIR] [--apply]

`export` writes one .xlsx per reviewer. Every S item goes to exactly
`reviewers_per_item` reviewers (the wave file's `review` block), balanced;
the two members of a twin family always go to the SAME reviewers, who must
judge them together (the pair is only as good as its contrast). A seeded
stratified sample of generated Q items is added as a spot check of the
generator (an error found there invalidates its whole family).

`ingest` reads the filled workbooks and applies the inclusion rule: an item
enters only if every assigned reviewer marks it OK. Twin partners and
paraphrases follow their item. It reports inter-reviewer agreement (Cohen's
kappa on OK vs not-OK) and, with --apply, writes the exclusion list into the
wave file — before the freeze tag, never after seeing model answers.

Packets contain the PRIVATE items: they are written under results/ (not
versioned) and must not be published.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from benchmarks.limes.bank.schema.item import Bank, Item, load_bank
from benchmarks.limes.runner.waves import load_wave

ROOT = Path(__file__).resolve().parents[1]
VERDICTS = ("OK", "DA RIVEDERE", "ERRORE")
_ESITO = {"affermare": "SÌ / PACIFICO", "negare": "NO", "segnalare": "CONTROVERSO"}
_HEADERS = ["id", "costrutto", "gemella", "domanda", "risposta attesa", "marker attesi",
            "marker vietati", "fonte dichiarata", "segnale atteso", "VERDETTO", "COMMENTO"]
_INSTRUCTIONS = """\
LIMES — revisione giuridica degli item (MATERIALE RISERVATO: non diffondere)

Per ogni riga valuta SOLO la domanda e la risposta attesa, come faresti con
una domanda d'esame:
  OK           la domanda è chiara, univoca, e la risposta attesa è corretta
               secondo il diritto vigente (o alla data indicata nella domanda);
  DA RIVEDERE  la domanda è ambigua, ammette più risposte difendibili, oppure
               la fonte indicata non è la più pertinente: spiega nel commento;
  ERRORE       la risposta attesa è giuridicamente sbagliata: spiega nel
               commento e, se puoi, indica la fonte corretta.

Coppie gemelle (colonna «gemella»): le due domande sono volutamente quasi
identiche e devono avere risposte OPPOSTE per un solo elemento (data, profilo
o fonte). Valutale insieme: se l'elemento che le distingue non basta a
giustificare esiti opposti, segna DA RIVEDERE su entrambe.

«Marker attesi»: le disposizioni che una risposta corretta deve citare
(es. cc-2043 = art. 2043 c.c.; prel-14 = art. 14 disp. prel.; cost-25 =
art. 25 Cost.; cass-41994-2021 = Cass. n. 41994/2021). «Marker vietati»: la
disposizione contigua con cui la norma si confonde.

Righe Q (calcoli): verifica il risultato con la derivazione riportata nella
colonna «fonte dichiarata»; un errore in una riga Q rimette in discussione
tutta la famiglia generata.

Ogni item è rivisto da due persone in modo indipendente: non confrontarti con
gli altri revisori prima di aver consegnato il file.
"""


def _family_key(item: Item) -> str:
    return item.family or item.id


def _row(item: Item) -> list:
    if item.layer == "Q":
        expected = f"{item.q_answer.value} {item.q_answer.unit}".strip()
        source = item.derivation
    else:
        expected = _ESITO.get(item.correct_orientation, "risposta aperta (vedi marker)")
        source = item.validity.source if item.validity else ""
    return [
        item.id, item.construct, f"{item.family} / {item.role}" if item.family else "",
        item.prompt, expected, ", ".join(item.expected_markers), ", ".join(item.disqualifiers),
        source, item.expected_signal, "", "",
    ]


def assign(bank: Bank, reviewers: list[str], per_item: int, q_sample: int, seed: int) -> dict[str, list[Item]]:
    """Balanced assignment: units = twin families or single items; each unit
    to `per_item` distinct reviewers, cycling over reviewer combinations so
    load and pairings stay even."""
    if len(reviewers) < per_item:
        raise SystemExit(f"servono almeno {per_item} revisori (ne hai indicati {len(reviewers)})")
    rng = random.Random(seed)
    units: dict[str, list[Item]] = defaultdict(list)
    for item in bank.items:
        if item.layer == "S" and item.stratum == "private" and not item.paraphrase_of:
            units[_family_key(item)].append(item)
    q_items = [i for i in bank.items if i.layer == "Q" and i.generator]
    by_family: dict[str, list[Item]] = defaultdict(list)
    for item in q_items:
        by_family[item.generator["family"]].append(item)
    per_family = max(1, q_sample // max(1, len(by_family)))
    for family, members in sorted(by_family.items()):
        for item in rng.sample(members, min(per_family, len(members))):
            units[item.id].append(item)
    keys = sorted(units)
    rng.shuffle(keys)
    pairs = list(combinations(reviewers, per_item))
    load = {r: 0 for r in reviewers}
    out: dict[str, list[Item]] = {r: [] for r in reviewers}
    for key in keys:
        # least-loaded combination first; ties broken by the seeded order
        pair = min(pairs, key=lambda p: (sum(load[r] for r in p), pairs.index(p)))
        for reviewer in pair:
            out[reviewer].extend(units[key])
            load[reviewer] += len(units[key])
    return out


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "revisore"


def cmd_export(args: argparse.Namespace) -> int:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation

    wave = load_wave(ROOT / "waves" / f"{args.wave}.yaml")
    bank = load_bank(ROOT / "bank", wave.bank_slices, wave.require_validity)
    reviewers = [r.strip() for r in args.reviewers.split(",") if r.strip()]
    per_item = int(wave.review.get("reviewers_per_item", 2))
    from benchmarks.limes.protocol.rules import load_protocol

    seed = load_protocol(ROOT / "protocol" / "protocol.yaml").seed
    packets = assign(bank, reviewers, per_item, args.q_sample, seed)
    out_dir = Path(args.out) if args.out else ROOT / "results" / "review" / args.wave
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"wave": wave.id, "reviewers": {}, "per_item": per_item}
    for reviewer, items in packets.items():
        wb = Workbook()
        info = wb.active
        info.title = "Istruzioni"
        for line in _INSTRUCTIONS.splitlines():
            info.append([line])
        info.column_dimensions["A"].width = 110
        sheet = wb.create_sheet("Item")
        sheet.append(_HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for item in items:
            sheet.append(_row(item))
        widths = [14, 12, 14, 70, 18, 22, 16, 40, 40, 16, 50]
        for col, width in zip("ABCDEFGHIJK", widths):
            sheet.column_dimensions[col].width = width
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        validation = DataValidation(type="list", formula1='"' + ",".join(VERDICTS) + '"', allow_blank=True)
        sheet.add_data_validation(validation)
        validation.add(f"J2:J{len(items) + 1}")
        sheet.freeze_panes = "B2"
        path = out_dir / f"revisione-{_safe(reviewer)}.xlsx"
        wb.save(path)
        manifest["reviewers"][reviewer] = {"file": path.name, "items": [i.id for i in items]}
        print(f"{reviewer:<20} {len(items):>4} item -> {path}")
    (out_dir / "assegnazioni.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


def read_verdicts(path: Path) -> dict[str, tuple[str, str]]:
    from openpyxl import load_workbook

    sheet = load_workbook(path, read_only=True)["Item"]
    rows = list(sheet.iter_rows(values_only=True))
    header = list(rows[0])
    i_id, i_v, i_c = header.index("id"), header.index("VERDETTO"), header.index("COMMENTO")
    out = {}
    for row in rows[1:]:
        if not row or not row[i_id]:
            continue
        verdict = str(row[i_v] or "").strip().upper()
        out[str(row[i_id])] = (verdict, str(row[i_c] or "").strip())
    return out


def _kappa(a: list[bool], b: list[bool]) -> float | None:
    from benchmarks.limes.protocol.judges import cohen_kappa

    return cohen_kappa(a, b)


def decide(bank: Bank, assignments: dict[str, list[str]], verdicts: dict[str, dict[str, tuple[str, str]]]) -> dict:
    """Apply the inclusion rule. Returns decisions + the closed exclusion
    list (twin partners and paraphrases follow their item)."""
    per_item: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for reviewer, ids in assignments.items():
        for item_id in ids:
            verdict, comment = verdicts.get(reviewer, {}).get(item_id, ("", ""))
            per_item[item_id].append((reviewer, verdict, comment))
    missing = sorted({i for i, rows in per_item.items() for _, v, _ in rows if v not in VERDICTS})
    excluded: set[str] = set()
    decisions = {}
    for item_id, rows in sorted(per_item.items()):
        ok = all(v == "OK" for _, v, _ in rows) and rows
        decisions[item_id] = {"reviews": [{"reviewer": r, "verdict": v, "comment": c} for r, v, c in rows],
                              "included": bool(ok)}
        if not ok:
            excluded.add(item_id)
    by_id = {i.id: i for i in bank.items}
    # A Q spot-check failure condemns its whole generated family.
    bad_q_families = {by_id[i].generator["family"] for i in excluded if i in by_id and by_id[i].generator}
    for item in bank.items:
        if item.generator and item.generator["family"] in bad_q_families:
            excluded.add(item.id)
    for family, (a, b) in bank.twin_families().items():
        if a.id in excluded or b.id in excluded:
            excluded.update({a.id, b.id})
    for item in bank.items:
        if item.paraphrase_of and item.paraphrase_of in excluded:
            excluded.add(item.id)
    agreement = {}
    reviewers = sorted(assignments)
    for r1, r2 in combinations(reviewers, 2):
        shared = sorted(set(assignments[r1]) & set(assignments[r2]))
        a = [verdicts.get(r1, {}).get(i, ("",))[0] == "OK" for i in shared]
        b = [verdicts.get(r2, {}).get(i, ("",))[0] == "OK" for i in shared]
        if shared:
            agreement[f"{r1} / {r2}"] = {"items": len(shared), "kappa": _kappa(a, b),
                                         "raw": sum(x == y for x, y in zip(a, b)) / len(shared)}
    return {"decisions": decisions, "excluded": sorted(excluded), "missing_verdicts": missing,
            "bad_q_families": sorted(bad_q_families), "agreement": agreement}


def cmd_ingest(args: argparse.Namespace) -> int:
    wave_path = ROOT / "waves" / f"{args.wave}.yaml"
    wave = load_wave(wave_path)
    bank = load_bank(ROOT / "bank", wave.bank_slices, wave.require_validity)
    review_dir = Path(args.dir) if args.dir else ROOT / "results" / "review" / args.wave
    manifest = json.loads((review_dir / "assegnazioni.json").read_text(encoding="utf-8"))
    assignments = {r: v["items"] for r, v in manifest["reviewers"].items()}
    verdicts = {r: read_verdicts(review_dir / v["file"]) for r, v in manifest["reviewers"].items()}
    result = decide(bank, assignments, verdicts)
    (review_dir / "decisioni.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    if result["missing_verdicts"]:
        print(f"ATTENZIONE: {len(result['missing_verdicts'])} item senza verdetto valido "
              f"(contano come non approvati): {', '.join(result['missing_verdicts'][:10])}…")
    for pair, row in result["agreement"].items():
        kappa = "n/d" if row["kappa"] is None else f"{row['kappa']:.2f}"
        print(f"accordo {pair}: {row['items']} item in comune, kappa={kappa}, accordo grezzo={row['raw']:.0%}")
    if result["bad_q_families"]:
        print(f"famiglie Q con errori: {', '.join(result['bad_q_families'])} (escluse per intero)")
    from benchmarks.limes.analysis.power import power_check

    remaining = [i for i in bank.items if i.id not in set(result["excluded"]) and not i.paraphrase_of]
    report = power_check(wave.analysis.get("power"), len(remaining))
    print(f"esclusi {len(result['excluded'])} item; restano {len(remaining)} punteggiati; "
          f"potenza {'OK' if report.get('satisfied') else 'INSUFFICIENTE'} "
          f"(richiesti {report.get('required_items')})")
    if args.apply:
        text = wave_path.read_text(encoding="utf-8")
        listed = "[" + ", ".join(result["excluded"]) + "]"
        new, count = re.subn(r"(?m)^(\s*excluded:\s*)\[.*?\]\s*$", lambda m: m.group(1) + listed, text)
        if count != 1:
            print("impossibile aggiornare `excluded:` nel file della wave", file=sys.stderr)
            return 1
        wave_path.write_text(new, encoding="utf-8")
        print(f"esclusioni scritte in {wave_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="limes-review")
    sub = parser.add_subparsers(dest="command", required=True)
    p_exp = sub.add_parser("export")
    p_exp.add_argument("--wave", required=True)
    p_exp.add_argument("--reviewers", required=True, help="nomi separati da virgola")
    p_exp.add_argument("--out", default=None)
    p_exp.add_argument("--q-sample", dest="q_sample", type=int, default=21)
    p_exp.set_defaults(func=cmd_export)
    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("--wave", required=True)
    p_ing.add_argument("--dir", default=None)
    p_ing.add_argument("--apply", action="store_true")
    p_ing.set_defaults(func=cmd_ingest)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
