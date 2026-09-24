"""Deterministic generator of parametric Q items (A3).

Every item is a draw from a legal-computation FAMILY with parameters
derived from the protocol seed and the wave id, so the same protocol
produces the same items and a later wave (different id) produces fresh
items of the same families — no cross-wave contamination through reused
numbers. The true answer is computed HERE, from the primary sources cited
in each family (never from the tools under test: calibrating the meter
with the meter's tasks is circular, DESIGN §4.1), and the derivation is
written into the item.

Conventions are those of protocol v0, unchanged (DESIGN: waves compare
only at constant conventions): dies a quo excluded, actual/365 even in
leap years, exact sum then half-up rounding to the cent. To keep them
unchanged, a draw whose deadline falls on a Saturday, Sunday or national
holiday is rejected and redrawn — so the holiday extension of art. 2963
c.c. comma 3 / art. 155 c.p.c. never decides an answer.

    python -m benchmarks.limes.bank.generate_q --wave wave-1 [--check]

`--check` regenerates and fails if the committed slice differs (the
committed JSON is the frozen artifact; this script is its provenance).
"""

from __future__ import annotations

import argparse
import calendar
import json
import random
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Legal interest rate, art. 1284 c.c., fixed yearly by decree of the Ministry
# of Economy (in force from 1 January of each year). Source: the annual DM
# MEF published in the Gazzetta Ufficiale (last: DM 10 dicembre 2025, GU n.
# 289 del 13/12/2025 -> 1,6% for 2026).
LEGAL_RATES = {
    2019: Decimal("0.8"), 2020: Decimal("0.05"), 2021: Decimal("0.01"),
    2022: Decimal("1.25"), 2023: Decimal("5"), 2024: Decimal("2.5"),
    2025: Decimal("2"), 2026: Decimal("1.6"),
}

# Extinctive prescription terms (codice civile, text verified on Normattiva).
# (label for the prompt, article, years, months)
PRESCRIPTIONS = [
    ("il diritto al risarcimento del danno da fatto illecito (non costituente reato), dal giorno del fatto", "art. 2947, comma 1, c.c.", 5, 0),
    ("il diritto al risarcimento del danno prodotto dalla circolazione di un veicolo (fatto non costituente reato), dal giorno del sinistro", "art. 2947, comma 2, c.c.", 2, 0),
    ("il diritto al pagamento di un canone di locazione di un immobile, dalla sua scadenza", "art. 2948, n. 3, c.c.", 5, 0),
    ("il diritto agli interessi maturati su un capitale, dalla scadenza della singola rata di interessi", "art. 2948, n. 4, c.c.", 5, 0),
    ("il diritto del lavoratore all'indennità di cessazione del rapporto (TFR), dalla cessazione del rapporto", "art. 2948, n. 5, c.c.", 5, 0),
    ("il diritto del mediatore al pagamento della provvigione, dalla conclusione dell'affare", "art. 2950 c.c.", 1, 0),
    ("un diritto derivante da un contratto di trasporto di merci interamente entro l'Italia, dalla riconsegna della merce", "art. 2951, comma 1, c.c.", 1, 0),
    ("un diritto derivante da un contratto di trasporto di merci con destinazione in Brasile, dalla riconsegna della merce a destinazione", "art. 2951, comma 2, c.c.", 0, 18),
    ("il diritto dell'assicuratore al pagamento di una rata di premio, dalla scadenza della rata", "art. 2952, comma 1, c.c.", 1, 0),
    ("il diritto dell'assicurato all'indennizzo in un'assicurazione contro i danni (non sulla vita), dal giorno del sinistro", "art. 2952, comma 2, c.c.", 2, 0),
    ("il diritto alla restituzione di una somma data a mutuo, dalla scadenza pattuita (termine ordinario)", "art. 2946 c.c.", 10, 0),
]

# Latest date for events that the prompts present as already happened.
LATEST_ACT = date(2026, 6, 30)

_MONTHS_IT = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
              "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def is_non_working(day: date) -> bool:
    """Saturday, Sunday or Italian national holiday (l. 260/1949 as amended)."""
    if day.weekday() >= 5:
        return True
    fixed = {(1, 1), (1, 6), (4, 25), (5, 1), (6, 2), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)}
    if (day.month, day.day) in fixed:
        return True
    return day == _easter(day.year) + timedelta(days=1)


def fmt(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def add_months(start: date, months: int) -> date:
    """Art. 2963 c.c. commi 4-5: same day of the final month, or its last
    day when that day does not exist."""
    total = start.month - 1 + months
    year, month = start.year + total // 12, total % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(start.day, last))


def money(value: Decimal) -> str:
    q = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, cents = f"{q:.2f}".split(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return ".".join(groups) + "," + cents


def _rand_date(rng: random.Random, lo: date, hi: date) -> date:
    return lo + timedelta(days=rng.randrange((hi - lo).days + 1))


# --- families ---------------------------------------------------------------


def fam_termine_giorni(rng: random.Random, n: int) -> list[dict]:
    out = []
    contexts = [
        ("Una clausola contrattuale attribuisce a una parte la facoltà di recesso da esercitare entro {n} giorni dalla consegna del bene, avvenuta il {d}.", "recesso"),
        ("Un regolamento condominiale concede {n} giorni dalla comunicazione del verbale, ricevuta il {d}, per contestare la ripartizione delle spese.", "contestazione"),
        ("Un bando assegna ai partecipanti {n} giorni dalla pubblicazione della graduatoria, avvenuta il {d}, per presentare osservazioni.", "osservazioni"),
        ("Una diffida ad adempiere ricevuta il {d} assegna al debitore un termine di {n} giorni per adempiere.", "diffida"),
    ]
    while len(out) < n:
        days = rng.choice([10, 15, 20, 30, 40, 45, 50, 60, 75, 90, 120])
        start = _rand_date(rng, date(2025, 1, 2), date(2026, 8, 31))
        end = start + timedelta(days=days)
        if is_non_working(end):
            continue
        template, tag = rng.choice(contexts)
        out.append({
            "prompt": template.format(n=days, d=fmt(start))
            + " Indica la data in cui scade il termine (formato gg/mm/aaaa), applicando il computo "
              "convenzionale (giorno iniziale escluso, giorno finale compreso).",
            "q_answer": {"kind": "data", "value": fmt(end), "unit": "data"},
            "derivation": f"Dies a quo ({fmt(start)}) escluso: {fmt(start)} + {days} giorni = {fmt(end)} "
                          f"(giorno lavorativo, nessuna proroga in gioco).",
            "params": {"start": start.isoformat(), "days": days, "context": tag},
            "construct_def": "C.termine",
            "reasoning_type": "rule_application",
            "source": "art. 155, commi 1-2, c.p.c. (computo a giorni); art. 2963, comma 2, c.c.",
        })
    return out


def fam_termine_ritroso(rng: random.Random, n: int) -> list[dict]:
    out = []
    while len(out) < n:
        days = rng.choice([10, 14, 20, 30, 40, 60, 90])
        hearing = _rand_date(rng, date(2025, 3, 1), date(2026, 12, 15))
        if is_non_working(hearing):
            continue
        limit = hearing - timedelta(days=days)
        if is_non_working(limit):
            continue
        out.append({
            "prompt": f"Un'udienza è fissata per il {fmt(hearing)}; la parte deve depositare una memoria almeno "
                      f"{days} giorni prima dell'udienza. Indica l'ultimo giorno utile per il deposito "
                      f"(formato gg/mm/aaaa), computando a ritroso con il giorno dell'udienza escluso.",
            "q_answer": {"kind": "data", "value": fmt(limit), "unit": "data"},
            "derivation": f"Termine a ritroso: dal {fmt(hearing)} (escluso) si contano {days} giorni liberi "
                          f"all'indietro; tra il {fmt(limit)} (escluso) e il {fmt(hearing)} (compreso) "
                          f"intercorrono {days} giorni. Ultimo giorno utile {fmt(limit)}.",
            "params": {"hearing": hearing.isoformat(), "days": days},
            "construct_def": "C.termine",
            "reasoning_type": "rule_application",
            "source": "art. 155 c.p.c. (computo dei termini); convenzione v0 identica a QP-04",
        })
    return out


def fam_prescrizione(rng: random.Random, n: int) -> list[dict]:
    out = []
    order = list(range(len(PRESCRIPTIONS)))
    rng.shuffle(order)
    i = 0
    while len(out) < n:
        label, article, years, months = PRESCRIPTIONS[order[i % len(order)]]
        start = _rand_date(rng, date(2019, 1, 1), date(2025, 12, 31))
        # Favour month-end starts sometimes: they exercise art. 2963 c. 5.
        if rng.random() < 0.25:
            start = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
        end = add_months(start, years * 12 + months)
        if is_non_working(end):
            continue
        i += 1
        term = (f"{years} anni" if years > 1 else "1 anno") if years else f"{months} mesi"
        note = ""
        if end.day != start.day:
            note = f" Nel mese di scadenza manca il giorno {start.day}: il termine si compie l'ultimo giorno del mese (art. 2963, comma 5, c.c.)."
        out.append({
            "prompt": f"Considera {label}. Il termine decorre dal {fmt(start)}. In assenza di atti "
                      f"interruttivi e di cause di sospensione, indica il giorno in cui si compie la "
                      f"prescrizione (formato gg/mm/aaaa).",
            "q_answer": {"kind": "data", "value": fmt(end), "unit": "data"},
            "derivation": f"Prescrizione di {term} ({article}); computo a calendario comune, giorno "
                          f"corrispondente del mese finale (art. 2963 c.c.): {fmt(start)} + {term} = "
                          f"{fmt(end)}.{note} Il giorno finale non è festivo.",
            "params": {"start": start.isoformat(), "article": article, "years": years, "months": months},
            "construct_def": "C.termine",
            "reasoning_type": "rule_recall",
            "source": f"{article}; art. 2963 c.c. (testo vigente, Normattiva)",
        })
    return out


def fam_interessi_semplici(rng: random.Random, n: int) -> list[dict]:
    out = []
    parties = [
        "un fornitore vanta un credito", "una società deve restituire un finanziamento",
        "un condomino è debitore verso il condominio", "un conduttore deve un conguaglio",
        "un committente deve a un appaltatore un saldo",
    ]
    while len(out) < n:
        capital = Decimal(rng.randrange(1500, 95000, 50))
        rate = Decimal(rng.choice(["2", "3", "3.5", "4", "4.5", "5", "6", "7", "8", "9"]))
        days = rng.randrange(20, 700)
        exact = capital * rate / Decimal(100) * Decimal(days) / Decimal(365)
        value = exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rate_s = f"{rate}".replace(".", ",")
        out.append({
            "prompt": f"{rng.choice(parties).capitalize()} di euro {money(capital)}; le parti hanno pattuito "
                      f"interessi al {rate_s}% annuo, maturati per un ritardo di {days} giorni. Indica "
                      f"l'importo degli interessi in euro, arrotondato al centesimo (interessi semplici, "
                      f"anno di 365 giorni).",
            "q_answer": {"kind": "numero", "value": float(value), "unit": "EUR",
                         "tolerance": {"absolute": 0.02}},
            "derivation": f"{capital} x {rate}% x {days}/365 = {exact:.6f} -> {money(value)}.",
            "params": {"capital": str(capital), "rate": str(rate), "days": days},
            "construct_def": "C.importo",
            "reasoning_type": "rule_application",
            "source": "art. 1284, comma 3, c.c. (interessi convenzionali pattuiti per iscritto); convenzione actual/365 del protocollo",
        })
    return out


def _legal_interest(capital: Decimal, start: date, end: date) -> tuple[Decimal, list[str]]:
    """Legal interest from start (excluded) to end (included), year by year
    at the rate in force on each accrued day, actual/365 regardless of
    leap years. Each segment covers the accrued days of one calendar year."""
    total = Decimal(0)
    steps: list[str] = []
    cursor = start  # last day NOT yet accrued-over (dies a quo excluded)
    while cursor < end:
        first_day = cursor + timedelta(days=1)
        segment_end = min(end, date(first_day.year, 12, 31))
        days = (segment_end - cursor).days
        rate = LEGAL_RATES[first_day.year]
        part = capital * rate / Decimal(100) * Decimal(days) / Decimal(365)
        total += part
        steps.append(f"{fmt(first_day)}-{fmt(segment_end)} {days} gg al {rate}% = {part:.6f}")
        cursor = segment_end
    return total, steps


def fam_interessi_legali(rng: random.Random, n: int) -> list[dict]:
    out = []
    while len(out) < n:
        capital = Decimal(rng.randrange(2000, 150000, 100))
        start = _rand_date(rng, date(2019, 3, 1), date(2025, 6, 30))
        end = _rand_date(rng, start + timedelta(days=200), min(start + timedelta(days=1800), date(2026, 8, 31)))
        if end.year == start.year:
            continue  # the family exists to cross rate changes
        exact, steps = _legal_interest(capital, start, end)
        value = exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if value <= 0:
            continue
        out.append({
            "prompt": f"Calcola gli interessi legali ex art. 1284 c.c. su un capitale di euro {money(capital)} "
                      f"dal {fmt(start)} al {fmt(end)}, applicando per ciascun periodo il saggio legale in "
                      f"vigore (giorno iniziale escluso, giorno finale compreso; anno di 365 giorni anche se "
                      f"bisestile; interessi semplici; somma esatta dei periodi arrotondata al centesimo). "
                      f"Indica l'importo in euro.",
            "q_answer": {"kind": "numero", "value": float(value), "unit": "EUR",
                         "tolerance": {"absolute": 0.05}},
            "derivation": "Saggi annuali DM MEF (2019 0,8%; 2020 0,05%; 2021 0,01%; 2022 1,25%; 2023 5%; "
                          "2024 2,5%; 2025 2%; 2026 1,6%). Periodi: " + "; ".join(steps)
                          + f". Totale {exact:.6f} -> {money(value)}.",
            "params": {"capital": str(capital), "start": start.isoformat(), "end": end.isoformat()},
            "construct_def": "C.importo",
            "reasoning_type": "rule_application",
            "source": "art. 1284, comma 1, c.c.; decreti annuali MEF sul saggio legale (GU)",
        })
    return out


def feriale_deadline(start: date, days: int) -> date:
    """Art. 1 l. 742/1969: the running of procedural terms is suspended
    from 1 to 31 August and resumes afterwards; a term that would start in
    August starts after the 31st. Counted day by day, dies a quo excluded."""
    current, remaining = start, days
    while remaining:
        current += timedelta(days=1)
        if current.month == 8:
            continue
        remaining -= 1
    return current


def fam_sospensione_feriale(rng: random.Random, n: int) -> list[dict]:
    out = []
    kinds = [("appello (termine breve)", 30, "art. 325, comma 1, c.p.c."),
             ("ricorso per cassazione (termine breve)", 60, "art. 325, comma 2, c.p.c.")]
    while len(out) < n:
        label, days, article = rng.choice(kinds)
        year = rng.choice([2024, 2025])
        start = _rand_date(rng, date(year, 6, 15) if days == 30 else date(year, 5, 20), date(year, 8, 25))
        if is_non_working(start):
            continue
        end = feriale_deadline(start, days)
        naive = start + timedelta(days=days)
        if is_non_working(end) or end == naive:
            continue  # the family exists to cross the August suspension
        in_august = start.month == 8
        how = ("la notifica cade nel periodo feriale: il decorso inizia dopo il 31 agosto"
               if in_august else "il periodo 1-31 agosto non si computa")
        out.append({
            "prompt": f"In una controversia civile ordinaria (non di lavoro, né rientrante tra i procedimenti "
                      f"esclusi dalla sospensione feriale), la sentenza di primo grado è notificata alla parte "
                      f"soccombente il {fmt(start)}. Indica l'ultimo giorno utile per il {label} "
                      f"(formato gg/mm/aaaa).",
            "q_answer": {"kind": "data", "value": fmt(end), "unit": "data"},
            "derivation": f"Termine di {days} giorni ({article}) dalla notifica del {fmt(start)}, dies a quo "
                          f"escluso; sospensione feriale (art. 1 l. 742/1969): {how}. Scadenza {fmt(end)} "
                          f"(senza sospensione sarebbe stata {fmt(naive)}). Giorno lavorativo.",
            "params": {"start": start.isoformat(), "days": days},
            "construct_def": "C.termine",
            "reasoning_type": "rule_application",
            "source": f"{article}; art. 1 l. 7 ottobre 1969, n. 742; art. 155 c.p.c.",
        })
    return out


def fam_prescrizione_interrotta(rng: random.Random, n: int) -> list[dict]:
    out = []
    terms = [p for p in PRESCRIPTIONS if p[3] == 0 and p[2] in (1, 2, 5, 10)]
    while len(out) < n:
        label, article, years, _months = rng.choice(terms)
        start = _rand_date(rng, date(2016, 1, 1), date(2023, 12, 31))
        original = add_months(start, years * 12)
        late = rng.random() < 0.3  # letter received AFTER the term expired
        if late:
            letter = original + timedelta(days=rng.randrange(10, 200))
            end = original
        else:
            letter = _rand_date(rng, start + timedelta(days=30), original - timedelta(days=5))
            end = add_months(letter, years * 12)
        # Acts lie in the past: a letter "received" after today would be a
        # hypothetical no reviewer accepts (and makes the question odd).
        if letter > LATEST_ACT or letter <= start:
            continue
        if is_non_working(end) or is_non_working(letter):
            continue
        term = f"{years} anni" if years > 1 else "1 anno"
        if late:
            derivation = (f"Prescrizione di {term} ({article}) dal {fmt(start)}: si compie il {fmt(original)}. "
                          f"La lettera ricevuta il {fmt(letter)} è successiva: un atto interruttivo non può "
                          f"interrompere una prescrizione già compiuta. Risposta {fmt(end)}.")
        else:
            derivation = (f"Prescrizione di {term} ({article}) dal {fmt(start)}; la costituzione in mora "
                          f"ricevuta il {fmt(letter)} la interrompe (art. 2943, comma 4, c.c.) e fa iniziare "
                          f"un nuovo periodo (art. 2945, comma 1, c.c.): {fmt(letter)} + {term} = {fmt(end)}.")
        out.append({
            "prompt": f"Considera {label}. Il termine decorre dal {fmt(start)}. Il creditore invia al debitore "
                      f"una lettera di costituzione in mora, ricevuta il {fmt(letter)}; non vi sono altri atti "
                      f"interruttivi né cause di sospensione. Indica il giorno in cui si compie (o si è compiuta) "
                      f"la prescrizione (formato gg/mm/aaaa).",
            "q_answer": {"kind": "data", "value": fmt(end), "unit": "data"},
            "derivation": derivation + " Il giorno finale non è festivo.",
            "params": {"start": start.isoformat(), "letter": letter.isoformat(), "article": article,
                       "years": years, "late": late},
            "construct_def": "C.termine",
            "reasoning_type": "rule_application",
            "source": f"{article}; artt. 2943, comma 4, 2945, comma 1, e 2963 c.c.",
        })
    return out


FAMILIES = [
    ("TG", fam_termine_giorni, 16),
    ("TR", fam_termine_ritroso, 10),
    ("PR", fam_prescrizione, 22),
    ("PI", fam_prescrizione_interrotta, 14),
    ("SF", fam_sospensione_feriale, 16),
    ("IS", fam_interessi_semplici, 14),
    ("IL", fam_interessi_legali, 18),
]

# Rotating anchors (A3): these generated items are scored in this wave and
# become publishable anchor candidates only AFTER the wave closes — never
# public and scored at the same time.
ROTATING_PER_FAMILY = 1

_OBSERVABLE = {
    "C.termine": "La data finale dichiarata nella risposta (formato gg/mm/aaaa o per esteso).",
    "C.importo": "L'importo in euro dichiarato nella risposta, entro la tolleranza pre-registrata.",
}
_WHY = {
    "C.termine": "Risposta esatta e unica: una data di calendario confrontata per uguaglianza.",
    "C.importo": "Risposta numerica unica, calcolata qui dalle fonti con le convenzioni del protocollo; la tolleranza assorbe solo l'arrotondamento.",
}


def generate(wave: str, seed: int) -> list[dict]:
    items: list[dict] = []
    for code, family, count in FAMILIES:
        rng = random.Random(f"{seed}:{wave}:{code}")
        for k, draw in enumerate(family(rng, count), start=1):
            params = dict(draw["params"])
            if k <= ROTATING_PER_FAMILY:
                params["publish_after"] = wave
            items.append({
                "id": f"W1-Q{code}-{k:02d}",
                "layer": "Q",
                "construct": "calcolo",
                "prompt": draw["prompt"],
                "q_answer": draw["q_answer"],
                "derivation": draw["derivation"],
                "reasoning_type": draw["reasoning_type"],
                "validity": {
                    "construct_def": draw["construct_def"],
                    "observable": _OBSERVABLE[draw["construct_def"]],
                    "why_mechanical": _WHY[draw["construct_def"]],
                    "source": draw["source"],
                },
                "generator": {"family": code, "seed": f"{seed}:{wave}:{code}", "params": params},
            })
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="generate LIMES parametric Q items")
    parser.add_argument("--wave", required=True)
    parser.add_argument("--seed", type=int, default=None, help="default: protocol seed")
    parser.add_argument("--out", default=None)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    seed = args.seed
    if seed is None:
        from benchmarks.limes.protocol.rules import load_protocol

        seed = load_protocol(ROOT / "protocol" / "protocol.yaml").seed
    out = Path(args.out) if args.out else ROOT / "bank" / "private" / f"q-{args.wave}.json"
    payload = {
        "$comment": f"GENERATED by benchmarks/limes/bank/generate_q.py --wave {args.wave} "
                    f"(seed {seed}). Do not edit by hand: regenerate.",
        "items": generate(args.wave, seed),
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not out.is_file() or out.read_text(encoding="utf-8") != text:
            print(f"{out}: differs from the generator output", file=sys.stderr)
            return 1
        print(f"{out}: in sync ({len(payload['items'])} items)")
        return 0
    out.write_text(text, encoding="utf-8")
    print(f"{len(payload['items'])} items -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
