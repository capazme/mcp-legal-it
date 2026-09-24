"""Demo di validazione LIMES: modelli sintetici passati per lo stesso
identico percorso di punteggio della CLI (score_q / score_s /
provenance_answer -> build_scorecard -> compare). Nessuna chiamata di rete.

Serve a tre cose (gate di uscita della wave, DESIGN §8):
1. validità di tetto — un modello che risponde come l'item prescrive fa
   100% su ogni dimensione meccanica;
2. validità di discrimine — un errore ingegnerizzato per costrutto fa
   crollare la dimensione che attacca e SOLO quella;
3. discriminazione delle gemelle — il modello ideale diverge in ogni
   famiglia, il modello che «afferma sempre» in nessuna.

Le risposte sono costruite dai marker e dagli esiti dichiarati negli item,
non scritte a mano: la demo vale per qualunque wave.

Uso, dalla radice del repository:

    python -m benchmarks.limes.demo.simulation [--wave wave-1]
"""

from __future__ import annotations

import argparse
import re
from datetime import date, timedelta
from pathlib import Path

from benchmarks.limes.analysis.compare import compare_cells
from benchmarks.limes.analysis.scorecard import build_scorecard, discrimination_report
from benchmarks.limes.bank.schema.item import Bank, Item, load_bank
from benchmarks.limes.protocol.citations import provenance_answer
from benchmarks.limes.protocol.gemelle import score_s
from benchmarks.limes.protocol.rules import load_protocol
from benchmarks.limes.protocol.scorers_q import score_q
from benchmarks.limes.runner.waves import load_wave

ROOT = Path(__file__).resolve().parents[1]

_CODE_TEXT = {
    "cc": "c.c.", "cp": "c.p.", "cpc": "c.p.c.", "cpp": "c.p.p.", "cost": "Cost.",
    "prel": "disp. prel.", "tfue": "TFUE", "tue": "TUE", "gdpr": "GDPR",
    "l689": "l. n. 689/1981", "dlgs28": "d.lgs. n. 28/2010", "cds": "c.d.s.",
    "tub": "TUB", "l300": "l. n. 300/1970", "l400": "l. n. 400/1988",
    "l2248": "l. n. 2248/1865, all. E",
    "cdc": "d.lgs. n. 206/2005", "l431": "l. n. 431/1998", "l87": "l. n. 87/1953",
}
_STATIC_TEXT = {
    "costituzione": "art. 134 della Costituzione",
    "cortecost": "Corte cost., n. 118/2015",
    "cgue": "CGUE C-6/64",
    "ssuu": "le Sezioni Unite",
    "norma": "art. 645 c.p.c.",
    "preleggi": "art. 12 disposizioni sulla legge in generale",
    "preleggi4": "art. 4 disposizioni sulla legge in generale",
    "preleggi8": "art. 8 disposizioni sulla legge in generale",
    "preleggi12": "art. 12 disposizioni sulla legge in generale",
    "preleggi14": "art. 14 disposizioni sulla legge in generale",
    "cc-1176": "art. 1176 c.c.", "cc-1175": "art. 1175 c.c.",
    "cc-2697": "art. 2697 c.c.", "cc-2698": "art. 2698 c.c.", "cc-2943": "art. 2943 c.c.",
}
_ESITO = {"affermare": "SÌ", "negare": "NO"}
_ESITO_U = {"affermare": "PACIFICO", "segnalare": "CONTROVERSO"}


def cite(marker: str) -> str:
    """Canonical citation text that hits exactly one declared marker."""
    if marker in _STATIC_TEXT:
        return _STATIC_TEXT[marker]
    cass = re.fullmatch(r"cass-(\d+)-(\d{4})", marker)
    if cass:
        return f"Cass., SS.UU., n. {cass.group(1)}/{cass.group(2)}"
    code, number = re.fullmatch(r"([a-z0-9]+)-(\d+(?:bis|ter|quater)?)", marker).groups()
    number = re.sub(r"(\d+)(bis|ter|quater)", r"\1-\2", number)
    return f"art. {number} {_CODE_TEXT[code]}"


def _fmt_num(x: float) -> str:
    s = f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _asks_esito(item: Item) -> bool:
    return "ESITO" in item.prompt


def _orientation_text(item: Item, orientation: str | None) -> str:
    if orientation is None:
        return ""
    if _asks_esito(item):
        table = _ESITO_U if item.construct == "revirement" else _ESITO
        return f"\nESITO: {table.get(orientation, 'SÌ')}"
    return {
        "affermare": "È pacifico che la regola si applica.",
        "negare": "Non è ammesso: è vietato ed escluso.",
        "segnalare": "Non è pacifico: sussiste un contrasto di giurisprudenza.",
    }[orientation]


def ideal_answer(item: Item) -> str:
    if item.layer == "Q":
        q = item.q_answer
        value = str(q.value) if q.kind == "data" else _fmt_num(float(q.value))
        return f"Il risultato è {value}."
    body = "; ".join(cite(m) for m in item.expected_markers)
    text = f"Si fonda su {body}." if body else "La risposta segue dal quadro normativo."
    return text + " " + _orientation_text(item, item.correct_orientation)


# --- engineered failures, one construct each ---------------------------------


def always_affirm(item: Item) -> str:
    """Right sources, but always the same verdict: fails one branch of every
    twin family (discrimination = 0)."""
    if item.layer == "Q":
        return ideal_answer(item)
    body = "; ".join(cite(m) for m in item.expected_markers)
    return f"Si fonda su {body}. " + _orientation_text(item, "affermare" if item.correct_orientation else None)


def no_sources(item: Item) -> str:
    """Right verdicts, no citations: P, H, A, M collapse; C and the
    marker-free U branch survive."""
    if item.layer == "Q":
        return ideal_answer(item)
    return "La risposta segue dal quadro normativo. " + _orientation_text(item, item.correct_orientation)


def wrong_article(item: Item) -> str:
    """Cites the contiguous distractor on provenance items: P floors."""
    if item.construct == "provenienza" and item.disqualifiers:
        return f"Si fonda su {cite(item.disqualifiers[0])}."
    return ideal_answer(item)


def off_by_one(item: Item) -> str:
    """Q answers off by one day / one per cent: C collapses."""
    if item.layer != "Q":
        return ideal_answer(item)
    q = item.q_answer
    if q.kind == "data":
        d, m, y = (int(p) for p in str(q.value).split("/"))
        return f"Il risultato è {(date(y, m, d) + timedelta(days=1)).strftime('%d/%m/%Y')}."
    return f"Il risultato è {_fmt_num(float(q.value) * 1.01 + 0.5)}."


MODELS = {
    "ideale": ideal_answer,
    "afferma-sempre": always_affirm,
    "senza-fonti": no_sources,
    "articolo-contiguo": wrong_article,
    "calcolo-sbagliato": off_by_one,
}


def score_all(bank: Bank, protocol, answers: dict[str, str], tool_texts) -> dict[str, dict]:
    verdicts = {}
    for item in bank.items:
        answer = answers[item.id]
        if item.layer == "Q":
            verdict = score_q(item, answer, protocol)
            verdict["passed"] = verdict["matched"]
        else:
            mech = score_s(item, answer) if item.has_mechanical_expectation() else None
            verdict = {"item_id": item.id, "construct": item.construct, "mechanical": mech,
                       "provenance": provenance_answer(answer, tool_texts.get(item.id)),
                       "passed": bool(mech and mech["passed"])}
        verdicts[item.id] = verdict
    return verdicts


def simulate(wave_id: str | None = "wave-1") -> dict:
    protocol = load_protocol(ROOT / "protocol" / "protocol.yaml")
    if wave_id:
        wave = load_wave(ROOT / "waves" / f"{wave_id}.yaml")
        bank = load_bank(ROOT / "bank", wave.bank_slices, wave.require_validity, wave.excluded)
    else:
        bank = load_bank(ROOT / "bank")
    scored = {i.id for i in bank.items if not i.paraphrase_of}
    ideal = {i.id: ideal_answer(i) for i in bank.items}
    out: dict = {"bank": bank, "models": {}}
    for name, answer_fn in MODELS.items():
        answers = {i.id: answer_fn(i) for i in bank.items}
        tool_texts = dict(ideal)  # the tools returned the true citations
        card = build_scorecard(bank=bank, model=f"sim-{name}", config_id="sim",
                               answers=answers, tool_texts=tool_texts, protocol=protocol,
                               scored=scored)
        out["models"][name] = {
            "answers": answers,
            "scorecard": card,
            "verdicts": score_all(bank, protocol, answers, tool_texts),
            "discrimination": discrimination_report(bank, answers),
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LIMES validity demo (no network)")
    parser.add_argument("--wave", default="wave-1", help="wave id (default wave-1); 'all' = whole bank")
    args = parser.parse_args(argv)
    result = simulate(None if args.wave == "all" else args.wave)
    for name, row in result["models"].items():
        print("=" * 62)
        print(f"MODELLO SINTETICO: {name}")
        print(row["scorecard"].render())
        disc = row["discrimination"]
        rate = disc["rate"]
        print(f"  gemelle: discriminazione={'n/d' if rate is None else f'{rate:.0%}'} "
              f"su {disc['families_scored']} famiglie")
    print("=" * 62)
    ideal = result["models"]["ideale"]["verdicts"]
    for name in ("afferma-sempre", "senza-fonti"):
        print(compare_cells("ideale", name, ideal, result["models"][name]["verdicts"]).render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
