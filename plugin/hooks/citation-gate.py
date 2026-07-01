#!/usr/bin/env python3
"""legal-it — Stop hook: gate citazioni deterministico con DEDUP di sessione.

Sostituisce il precedente hook di tipo 'prompt' (LLM) che over-firava, segnalando
falsi positivi (acronimi/tecniche, concetti, contenuto di file) e ri-naggando norme
gia' verificate. Questa versione:
- estrae le citazioni a livello di ARTICOLO dall'ULTIMO messaggio assistant;
- le considera coperte se il numero d'articolo compare in QUALSIASI cite_law()
  gia' presente nel transcript (dedup di sessione);
- segnala SOLO le citazioni nuove e non coperte; altrimenti resta in silenzio.
Conservativo (bias anti-nag). L'enforcement forte del merito resta sul gate pre-export
e sul giudizio umano dell'avvocato.
"""
import sys, json, re


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("stop_hook_active"):
        return 0
    tp = data.get("transcript_path")
    if not tp:
        return 0
    try:
        lines = open(tp, encoding="utf-8").read().splitlines()
    except Exception:
        return 0

    last_text = ""
    cite_refs = []
    for ln in lines:
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if o.get("type") != "assistant":
            continue
        content = (o.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        texts = []
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text":
                texts.append(c.get("text") or "")
            elif c.get("type") == "tool_use" and "cite_law" in (c.get("name") or ""):
                ref = (c.get("input") or {}).get("reference")
                if ref:
                    cite_refs.append(ref)
        joined = "\n".join(t for t in texts if t)
        if joined.strip():
            last_text = joined

    if not last_text:
        return 0

    verified_nums = set()
    for r in cite_refs:
        for m in re.finditer(r"art\.?\s*(\d+)", r, re.I):
            verified_nums.add(m.group(1))

    lawtoken = re.compile(
        r"c\.p\.c\.|c\.p\.p\.|c\.p\.|c\.c\.|cost|codice civile|codice penale|"
        r"codice di procedura|g\.?d\.?p\.?r|gdpr|\bcdf\b|deontolog|"
        r"\bl\.\s*\d|legge\s*\d|d\.?\s*lgs|reg(?:olamento)?\.?\s*(?:ue)?\s*\d|"
        r"2024/1689|ai act|direttiva\s*\d",
        re.I,
    )
    art = re.compile(
        r"art\.?\s*(\d+)(?:[\s-]*(?:bis|ter|quater|quinquies|sexies|septies|octies))?",
        re.I,
    )

    uncovered = []
    seen = set()
    for m in art.finditer(last_text):
        num = m.group(1)
        window = last_text[max(0, m.start() - 6): m.end() + 28]
        if not lawtoken.search(window):
            continue
        if num in verified_nums:
            continue
        snippet = re.sub(r"\s+", " ", last_text[m.start(): m.end() + 20]).strip()
        key = (num, snippet[:24])
        if key in seen:
            continue
        seen.add(key)
        uncovered.append(snippet)

    if not uncovered:
        return 0

    elenco = "; ".join(uncovered[:12])
    sys.stderr.write(
        "ATTENZIONE — gate citazioni: le seguenti norme risultano citate nel messaggio "
        "SENZA una cite_law() corrispondente nel transcript: [" + elenco + "]. "
        "Richiama cite_law() per ciascuna (o segnala esplicitamente che sono fuori "
        "copertura, es. CDF/allegati UE) prima di finalizzare.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
