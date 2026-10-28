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

#: Any of these is an amount that slipped back to Python's default format:
#: «25,000.00» and «52,000€» (English thousands), «€1092.48», «900.9€» or «€850.0»
#: (a raw float), «52000€» (a bare integer: four digits or more with no separator).
#: The English-thousands patterns without decimals are tied to the euro sign, so a
#: legitimate Italian three-decimal value («1,789 euro/litro», «2,500%») never trips
#: them. Spaces are matched as ' ?', never \s: the scanned text joins its strings with
#: newlines, and «€» at the end of one must not pair with a number opening the next.
ENGLISH = [
    re.compile(r"\d,\d{3}\.\d{2}"),
    re.compile(r"\d,\d{3}(?![\d,]) ?€"),
    re.compile(r"€ ?\d{1,3},\d{3}(?!\d)"),
    re.compile(r"€ ?\d{4,}\.\d"),
    re.compile(r"\d{4,}\.\d+ ?€"),
    re.compile(r"(?<![\d,.])\d+\.\d{1,2} ?€"),
    re.compile(r"€ ?\d+\.\d{1,2}(?![\d])"),
    re.compile(r"(?<![\d,.])\d{4,} ?€"),
    re.compile(r"€ ?\d{4,}(?![\d.,])"),
]
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
    ("preventivo_stragiudiziale", {"valore_pratica": 1000000}),  # the «oltre 520.000€» bracket
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
    # amounts that used to be raw floats or bare integers in prose
    ("spese_condominiali", {"importo_totale": 25000, "millesimi_proprietario": 120, "tipo_spesa": "ascensore",
                            "piano": 4}),
    ("indennita_licenziamento", {"anni_servizio": 8, "retribuzione_mensile": 2500.5}),
    ("regime_forfettario", {"ricavi": 90000.5}),
    ("parcella_avvocato_civile", {"valore_causa": 30000}),
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


def _english(text: str) -> list[str]:
    return [m for pattern in ENGLISH for m in pattern.findall(text)]


@pytest.mark.parametrize("text", [
    "Euro 25,000.00", "fino a 52,000€", "€ 52,000", "€1092.48", "900.9€", "€850.0", "fino a 52000€", "€ 52000",
    "oltre 520000€",
])
def test_the_scan_catches_every_english_shape(text):
    assert _english(text), text


@pytest.mark.parametrize("text", [
    "Euro 25.000,00", "fino a 52.000€", "€ 1.092,48", "900,90€", "€850,00", "1,789 euro/litro", "2,500%",
    "0,3500 €/km", "soglia €\n2026-10-21", "anno 2026\n€ 1.000,00", "coefficiente 1,193707",
])
def test_the_scan_leaves_italian_numbers_alone(text):
    assert not _english(text), (text, _english(text))


@pytest.mark.parametrize("name,args", CALLS, ids=[c[0] for c in CALLS])
def test_amounts_have_italian_separators(name, args):
    text = _text(name, args)
    assert not _english(text), (name, _english(text)[:5])
    assert ITALIAN.search(text), f"{name}: no amount over 1.000 in the text, the scan would be vacuous"


def test_inflation_example_has_an_italian_decimal_comma():
    # 100€ grows to a three-digit amount: no thousands separator to scan for, only the comma.
    text = _text("calcolo_inflazione", {"data_inizio": "2015-01-01", "data_fine": "2025-12-31"})
    assert not _english(text)
    assert re.search(r"equivalgono a \d{3},\d{2}€", text), text


def test_fuel_price_keeps_its_three_decimals_with_a_comma():
    # «1.789 euro/litro» reads as one thousand seven hundred: the price is «1,789».
    text = _text("spese_trasferta_avvocati", {"km_distanza": 100, "ore_assenza": 6,
                                              "prezzo_carburante_litro": 1.789})
    assert "un quinto di 1,789 euro/litro" in text
    assert "1.789 euro/litro" not in text


def test_a_margin_that_rounds_to_zero_has_no_minus_sign():
    # An income 0,004 € over the threshold: the margin rounds to -0.0, which printed "+-0,00 €".
    async def run():
        async with Client(mcp) as client:
            first = await client.call_tool_mcp("gratuito_patrocinio", {"reddito_richiedente": 1000})
            soglia = first.structuredContent["soglia_applicata"]
            r = await client.call_tool_mcp("gratuito_patrocinio", {"reddito_richiedente": soglia + 0.004})
            return r.structuredContent

    out = _run(run())
    assert out["margine"] == 0.0 and str(out["margine"]) == "0.0"
    assert "(margine: +0,00 €)" in out["note"], out["note"]


def test_numero_it():
    assert numero_it(25000) == "25.000,00"
    assert numero_it(1234567.891) == "1.234.567,89"
    assert numero_it(0.35, 4) == "0,3500"
    assert numero_it(20000000, 0) == "20.000.000"
    assert json.dumps(numero_it(-1500.5)) == '"-1.500,50"'
