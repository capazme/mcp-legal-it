"""Shared helpers for the live gates that read the vigente text of a norm.

Used by `test_cartabia_live.py`, `test_norme_live_*.py`, `test_fonte_*_live.py` and
`test_strutturale_*_live.py`. Every helper needs the network (Normattiva, EUR-Lex)
and is meant for files marked `pytest.mark.live`.

Normattiva's text has quirks a naive substring check trips on: numbers are
sometimes written after the noun ("giorni sessanta"), the ordinal indicator is
U+00BA ("1º agosto") rather than the degree sign, and whitespace is irregular.
`contiene()` normalises both sides before comparing.
"""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata

_ORDINALS = {"º": "°", "ª": "°"}


def normalizza(testo: str) -> str:
    """Lower-case, single spaces, ordinal indicators unified, accents kept."""
    testo = unicodedata.normalize("NFC", testo or "")
    for k, v in _ORDINALS.items():
        testo = testo.replace(k, v)
    return re.sub(r"\s+", " ", testo).strip().lower()


def cite_law_json(reference: str) -> dict:
    """Return the JSON payload of `cite_law(reference, formato="json")`."""
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.tools.legal_citations import cite_law

    fn = getattr(cite_law, "fn", cite_law)
    raw = asyncio.run(fn(reference=reference, formato="json"))
    return json.loads(raw)


def testo_vigente(reference: str) -> str:
    """Normalised vigente text of a norm, asserting the fetch succeeded."""
    payload = cite_law_json(reference)
    assert not payload.get("errore"), payload
    testo = payload.get("testo") or ""
    assert testo, payload
    return normalizza(testo)


def contiene(testo: str, *frasi: str) -> list[str]:
    """Return the phrases (any of the alternatives separated by '|') missing from the text."""
    testo = normalizza(testo)
    missing = []
    for frase in frasi:
        if not any(normalizza(alt) in testo for alt in frase.split("|")):
            missing.append(frase)
    return missing


def assert_parole(reference: str, *frasi: str) -> str:
    """Assert every phrase (alternatives with '|') appears in the vigente text; return the text."""
    testo = testo_vigente(reference)
    missing = contiene(testo, *frasi)
    assert not missing, f"{reference}: il testo vigente non contiene {missing}"
    return testo


def numeri_in_lettere(n: int) -> str:
    """Italian cardinal for small numbers used in procedural terms (0-100), for assertions."""
    unita = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci",
             "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette",
             "diciotto", "diciannove"]
    decine = ["", "", "venti", "trenta", "quaranta", "cinquanta", "sessanta", "settanta", "ottanta", "novanta"]
    if n < 20:
        return unita[n]
    if n == 100:
        return "cento"
    d, u = divmod(n, 10)
    base = decine[d]
    if u in (1, 8):
        base = base[:-1]
    return base + (unita[u] if u else "")
