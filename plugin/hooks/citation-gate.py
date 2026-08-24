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


_INLINE_CODE = re.compile(r"`[^`\n]*`")

# One pattern for both the prose scan and the cite_law() dedup: when they
# disagreed, a `cite_law("articolo 2043 c.c.")` failed to cover the very
# citation it had verified. Covers art. / art / artt. / articolo / articoli,
# because Italian legal writing uses all of them interchangeably.
_ARTICOLO = r"\bart(?:icol[oi]|t)?\.?\s*(\d+)"


def strip_code(text: str) -> str:
    """Drop fenced blocks and inline spans before looking for citations.

    Code quotes things; it does not assert them. A sample tool payload, a
    fixture value or a snippet of documentation that happens to contain
    "art. 1284 c.c." is not the assistant claiming what that article says, and
    nagging about it is what got this gate called too eager in public.

    Splitting on the fence rather than matching pairs also discards a block
    left unterminated at the end of a message.
    """
    prosa = "\n".join(text.split("```")[::2])
    return _INLINE_CODE.sub(" ", prosa)


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

    last_text = strip_code(last_text)
    if not last_text.strip():
        return 0

    verified_nums = set()
    for r in cite_refs:
        for m in re.finditer(_ARTICOLO, r, re.I):
            verified_nums.add(m.group(1))

    lawtoken = re.compile(
        # `cost` has to stay anchored: as a bare substring it matched "costi",
        # "costo" and "costante", so any nearby `art. N` tripped the gate.
        r"c\.p\.c\.|c\.p\.p\.|c\.p\.|c\.c\.|\bcost\b\.?|\bcostituzion|"
        # Named codes are enumerated rather than matched as a bare "codice":
        # this project handles codice fiscale, codice tributo and codice ATECO
        # as data, and none of them is a source of law.
        r"codice\s+(?:civile|penale|di\s+procedura|del\s+consumo|della\s+strada|"
        r"della\s+crisi|dell'?\s?ambiente|della\s+navigazione|della\s+privacy|"
        r"delle\s+assicurazioni|dei\s+contratti)|"
        r"\bc\.d\.s\.|\bccii\b|\btuir\b|\bt\.u\.f\.|\bcod\.?\s*ass\.|"
        r"g\.?d\.?p\.?r|gdpr|\bcdf\b|deontolog|"
        r"\bl\.\s*\d|legge\s*\d|d\.?\s*lgs|reg(?:olamento)?\.?\s*(?:ue)?\s*\d|"
        r"2024/1689|ai act|direttiva\s*\d",
        re.I,
    )
    art = re.compile(
        _ARTICOLO + r"(?:[\s-]*(?:bis|ter|quater|quinquies|sexies|septies|octies))?",
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
