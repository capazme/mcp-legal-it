"""Demo di validazione LIMES: due modelli sintetici ("ideale" e "baseline
errata") passati per lo stesso identico percorso di punteggio della CLI
(score_q / score_s / provenance_answer -> build_scorecard -> compare ->
equating). Nessuna chiamata di rete.

Serve a tre cose:
1. verificare che un modello che risponde perfettamente faccia 100% su
   tutte le dimensioni meccaniche (validita' di tetto);
2. verificare che errori ingegnerizzati per costrutto facciano crollare
   esattamente le celle giuste (validita' di discrimine);
3. mostrare le statistiche della scorecard senza consumare token.

Uso, dalla radice del repository:

    python -m benchmarks.limes.demo.simulation
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from benchmarks.limes.bank.schema.validate import load_bank
from benchmarks.limes.protocol.rules import load_protocol
from benchmarks.limes.protocol.scorers_q import score_q
from benchmarks.limes.protocol.gemelle import score_s
from benchmarks.limes.protocol.citations import provenance_answer
from benchmarks.limes.analysis.scorecard import build_scorecard
from benchmarks.limes.analysis.compare import compare_cells
from benchmarks.limes.analysis.equating import WaveScores, anchor_delta, equated_private, drift_guard

bank = load_bank(Path("benchmarks/limes/bank"))
protocol = load_protocol(Path("benchmarks/limes/protocol/protocol.yaml"))

def fmt_num(x):
    s = f"{x:,.2f}"
    s = s.rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
    return s

def ideal_answer(item):
    if item.layer == "Q":
        q = item.q_answer
        if q.kind == "data":
            val = str(q.value)
        else:
            val = fmt_num(float(q.value))
        body = f"Il valore richiesto è {val}." if q.kind == "numero" else f"La data è il {val}."
        return body + " È pacifico che si applica dunque la regola dell'art. 1176 c.c."
    m = set(item.expected_markers)
    text = ""
    if "costituzione" in m:
        text += "Ai sensi dell'art. 32 della Costituzione, "
    if "cortecost" in m:
        text += "Corte cost., n. 118/2015 lo conferma. "
    if "cgue" in m:
        text += "La giurisprudenza CGUE C-6/64 è rilevante. "
    if "norma" in m or "cc-1176" in m:
        text += "Si applica l'art. 1176 c.c. "
    if "cc-2697" in m:
        text += "Fondamento: art. 2697 c.c. "
    if "preleggi8" in m:
        text += ("Ai sensi dell'art. 8 disposizioni sulla legge in generale, "
                 "la consuetudine rileva solo nei casi in cui sia richiamata da norme di legge. ")
    if "preleggi4" in m:
        text += "Ex art. 4 disposizioni sulla legge in generale. "
    if "preleggi12" in m:
        text += "Ex art. 12 disposizioni sulla legge in generale. "
    if "preleggi14" in m:
        text += "Ex art. 14 disposizioni sulla legge in generale. "
    if item.correct_orientation == "affermare":
        text = "È pacifico che la regola si applica. " + text + " Si applica dunque la disciplina richiesta."
    elif item.correct_orientation == "negare":
        text = "Non è ammesso il ragionamento proposto: è vietato ed escluso in malam partem. " + text
    elif item.correct_orientation == "segnalare":
        text = "Non è pacifico: sussiste un contrasto di giurisprudenza, con revirement in corso davanti alle sezioni unite. " + text
    return text

def baseline_answer(item):
    if item.layer == "Q":
        q = item.q_answer
        if q.kind == "data":
            d = date(*reversed([int(p) for p in str(q.value).split("/")])) + timedelta(days=1)
            return f"La data è il {d.strftime('%d/%m/%Y')}."
        return f"Il valore richiesto è {fmt_num(float(q.value) * 1.1)}."
    # errori ingegnerizzati per costrutto
    if item.id in ("SP-02A", "SP-03B"):
        return ideal_answer(item).replace("Non è ammesso", "È pacifico che è ammesso") + " Si applica dunque."
    if item.id == "SP-04B":
        return "È pacifico che il revirement si applica."  # fiducia dove va segnalato il conflitto
    if item.id == "QAS-04":
        return "È pacifico che si applica dunque la regola."  # fiducia dove serve prudenza
    if item.id in ("SP-01", "SP-05", "SP-06"):
        return "La risposta segue dalla regola generale, come sopra illustrato."  # nessuna citazione
    if item.id == "QAS-01":
        return "Come da Cass. n. 99999/1999, la risposta è confermata."  # citazione inesistente
    if item.id == "QAS-02":
        return "Ai sensi dell'art. 2698 c.c., il valore è conforme."  # articolo sbagliato (disq.)
    if item.id == "QAS-03":
        return "Ai sensi dell'art. 1175 c.c., si applica la regola."  # articolo sbagliato
    return "Non è pacifico: contrasto di giurisprudenza."  # default prudente ma senza marker

def tool_text_for(item, answers):
    """Simula i tool result: contengono le citazioni 'vere' (quelle che il
    modello ideale riproduce fedelmente)."""
    return ideal_answer(item)

def score_all(answers, tool_texts):
    verdicts = {}
    for item in bank.items:
        a = answers[item.id]
        if item.layer == "Q":
            v = score_q(item, a, protocol)
            v["passed"] = v["matched"]
        else:
            mech = score_s(item, a) if item.has_mechanical_expectation() else None
            v = {
                "item_id": item.id, "construct": item.construct,
                "mechanical": mech,
                "provenance": provenance_answer(a, tool_texts.get(item.id)),
                "passed": bool(mech and mech["passed"]),
            }
        verdicts[item.id] = v
    return verdicts

ideal = {i.id: ideal_answer(i) for i in bank.items}
baseline = {i.id: baseline_answer(i) for i in bank.items}
tool_texts = {i.id: tool_text_for(i, ideal) for i in bank.items}

v_ideal = score_all(ideal, tool_texts)
v_base = score_all(baseline, tool_texts)

def attempts(vmap):
    return {iid: (1 if v["passed"] else 2) for iid, v in vmap.items()}

sc_ideal = build_scorecard(bank=bank, model="sim-ideal", config_id="bare",
                           answers=ideal, tool_texts=tool_texts, protocol=protocol,
                           attempts=attempts(v_ideal), excluded=0)
sc_base = build_scorecard(bank=bank, model="sim-baseline", config_id="bare",
                          answers=baseline, tool_texts=tool_texts, protocol=protocol,
                          attempts=attempts(v_base), excluded=0)

print("=" * 62)
print("MODELLLO IDEALE (risposte perfette attese)")
print(sc_ideal.render())
print("=" * 62)
print("BASELINE ERRATA (errori ingegnerizzati per costrutto)")
print(sc_base.render())

print("=" * 62)
cmp = compare_cells("ideale", "baseline", v_ideal, v_base)
print(cmp.render())

# Equating demo: wave-0 vs ipotetica wave-1 (stessa difficoltà, anchor invariati)
w0 = WaveScores("wave-0", anchor_passes=sum(1 for i in bank.items if i.stratum == "anchor" and v_ideal[i.id]["passed"]), anchor_total=len([i for i in bank.items if i.stratum == "anchor"]),
                private_passes=sum(1 for i in bank.items if i.stratum == "private" and v_ideal[i.id]["passed"]), private_total=len([i for i in bank.items if i.stratum == "private"]))
w1 = WaveScores("wave-1", anchor_passes=sum(1 for i in bank.items if i.stratum == "anchor" and v_base[i.id]["passed"]), anchor_total=len([i for i in bank.items if i.stratum == "anchor"]),
                private_passes=sum(1 for i in bank.items if i.stratum == "private" and v_base[i.id]["passed"]), private_total=len([i for i in bank.items if i.stratum == "private"]))
d = anchor_delta(w1, w0)
print(f"\nEquating: anchor_delta(w1,w0)={d:+.3f}  equated_private(w1)={equated_private(w1, w0):+.3f}  drift_guard={drift_guard(w1, w0)}")

# Gemelle: discriminazione per famiglia
from benchmarks.limes.protocol.gemelle import score_twin_family, iter_mechanical_s
mech = {i.id: i for i in bank.items if i.is_twin()}
for fam in ("G2", "A2", "R2"):
    a = next(i for i in bank.items if i.family == fam and i.role == "a")
    b = next(i for i in bank.items if i.family == fam and i.role == "b")
    fa = score_twin_family(a, b, ideal[a.id], ideal[b.id])
    fb = score_twin_family(a, b, baseline[a.id], baseline[b.id])
    print(f"Gemelle {fam}: ideale diverge={fa.get('discriminated')} | baseline diverge={fb.get('discriminated')}")
