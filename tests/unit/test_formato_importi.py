"""Amounts in prose are written the Italian way, never «25,000.00».

Python's ``{x:,.2f}`` writes the English separators, and in a deed, a quote or
a fee note «€1,234.00» reads wrong. Every tool formats amounts through
``lib/_numeri.numero_it``; this test renders a few tools of each family as a
client receives them and scans the text. Each call is chosen so that at least
one amount has a thousands separator, so the scan cannot pass vacuously.
"""

import asyncio
import json
import re

import pytest
from fastmcp import Client
from mcp_legal_it.lib._numeri import numero_it
from mcp_legal_it.server import mcp

ENGLISH = re.compile(r"\d,\d{3}\.\d{2}")
ITALIAN = re.compile(r"\d\.\d{3}(?![\d.])")  # a thousands dot, with or without decimals

CALLS = [
    # deeds
    ("decreto_ingiuntivo", {"creditore": "A", "debitore": "B", "importo": 25000}),
    ("sfratto_morosita", {"locatore": "A", "conduttore": "B", "immobile": "Via Roma 1", "canone_mensile": 1250,
                          "mensilita_insolute": 8, "data_contratto": "2020-01-01"}),
    ("atto_di_precetto", {"creditore": "A", "debitore": "B", "titolo_esecutivo": "sentenza n. 1/2025",
                          "importo_capitale": 25000}),
    # quotes and fee notes
    ("preventivo_civile", {"valore_causa": 30000}),
    ("preventivo_stragiudiziale", {"valore_pratica": 30000}),
    ("preventivo_volontaria_giurisdizione", {"valore_causa": 30000}),
    ("modello_notula", {"tipo_procedimento": "decreto_ingiuntivo", "avvocato": "Avv. A", "cliente": "B", "valore_causa": 30000}),
    # other professionals
    ("compenso_curatore_fallimentare", {"attivo_realizzato": 500000, "passivo_accertato": 800000}),
    ("compenso_delegati_vendite", {"prezzo_aggiudicazione": 250000}),
    # civil procedure
    ("competenza_giudice", {"valore_causa": 30000}),
    ("gratuito_patrocinio", {"reddito_richiedente": 12000}),
    # GDPR
    ("calcolo_sanzione_gdpr", {"tipo_violazione": "art83_5", "fatturato_annuo": 50000000}),
    # Enasarco: amounts that used to be interpolated raw («€1234.5»)
    ("fattura_enasarco", {"provvigioni": 40000}),
    # ISTAT revaluation
    ("lettera_adeguamento_canone", {"locatore": "A", "conduttore": "B", "indirizzo_immobile": "Via Roma 1",
                                    "canone_attuale": 1200, "data_stipula": "2021-09-01",
                                    "data_adeguamento": "2025-09-01"}),
]


def _text(name: str, args: dict) -> str:
    async def run():
        async with Client(mcp) as client:
            r = await client.call_tool_mcp(name, args)
            return r.model_dump(by_alias=True, exclude_none=True, mode="json")

    wire = _run(run())
    assert not wire.get("isError"), wire
    # Only strings: JSON numbers (10000.0) are numbers, not prose.
    return "\n".join(_strings(wire.get("structuredContent") or {})
                     + [b.get("text", "") for b in wire.get("content", []) if b.get("type") == "text"
                        and not b.get("text", "").lstrip().startswith(("{", "["))])


def _strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v)]
    return []


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("name,args", CALLS, ids=[c[0] for c in CALLS])
def test_amounts_have_italian_separators(name, args):
    text = _text(name, args)
    assert not ENGLISH.findall(text), (name, ENGLISH.findall(text)[:5])
    assert ITALIAN.search(text), f"{name}: no amount over 1.000 in the text, the scan would be vacuous"


def test_numero_it():
    assert numero_it(25000) == "25.000,00"
    assert numero_it(1234567.891) == "1.234.567,89"
    assert numero_it(0.35, 4) == "0,3500"
    assert numero_it(20000000, 0) == "20.000.000"
    assert json.dumps(numero_it(-1500.5)) == '"-1.500,50"'
