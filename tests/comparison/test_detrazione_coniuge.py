"""Benchmark fase 1: detrazione_coniuge vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-coniuge-a-carico.php
Modulo ``CalcoloDetrazioneConiuge`` (POST): ``RedditoComplessivoDetrazione`` (rigo RN1
col. 1), ``DeduzioneAbitazionePrincipale`` (rigo RN2) e ``MesiConiugeCarico`` (select
1-12, default 12: il driver lo forza a 12, l'unico scenario che il tool modella).
Pulsante ``#btn-calc``: il click e' coperto dagli overlay pubblicitari, il modulo si
invia con ``requestSubmit``.

Risultato: blocco "SVILUPPO del CALCOLO -- Periodo di imposta 2025 - Dichiarazione dei
redditi 2026" con le righe Reddito netto (RN1 - RN2), Mesi a Carico, Detrazione base,
Quoziente (troncato alla quarta cifra decimale) oppure Maggiorazione per fascia di
reddito, la "Formula applicata" e "RN6 Col.1 Detrazione per coniuge a carico
spettante", arrotondata all'unita' di euro come nel modello dichiarativo.

Confronto: il sito espone solo l'importo del rigo RN6 arrotondato all'euro. Il valore
in centesimi del sito viene quindi ricostruito dai suoi stessi addendi (detrazione
base, quoziente, maggiorazione, mesi) secondo la formula che il sito dichiara, e il
driver verifica che quel valore, arrotondato all'euro (half-up), coincida con RN6: se
non coincide il test fallisce per errore del driver, non per scostamento del tool.
``detrazione`` del tool (in centesimi) e' poi confrontata con il valore ricostruito
alla tolleranza di 0,01 euro; RN6 e' riportato nei messaggi.

Norma: art. 12, co. 1, lett. a), TUIR (D.P.R. 917/1986): 1) 800 euro meno 110 x
(reddito / 15.000) fino a 15.000; 2) 690 euro oltre 15.000 e fino a 40.000; 3) 690 x
(80.000 - reddito) / 40.000 oltre 40.000 e fino a 80.000. Lett. b): la detrazione della
lettera a) e' aumentata di 10 euro (29.000-29.200], 20 (29.200-34.700], 30
(34.700-35.000], 20 (35.000-35.100], 10 (35.100-35.200] -- il tool NON applica la lett.
b): scostamenti attesi nella fascia 29.000,01-35.200. Co. 3: detrazioni rapportate a
mese. Co. 4: rapporto di lett. a) n. 1 uguale a uno -> 690; rapporti di n. 1 e n. 3
uguali a zero -> la detrazione non compete; negli altri casi il rapporto "si assume
nelle prime quattro cifre decimali" (il sito tronca, il tool usa la precisione piena:
scostamenti attesi di pochi centesimi nella terza fascia). Co. 4-bis: reddito al netto
dell'abitazione principale (il sito sottrae RN2; il tool riceve il reddito gia' netto).

Anno: il sito calcola per il periodo d'imposta 2025 senza scelta dell'anno; il tool non
ha tabelle annuali (importi fissi di legge) e non dipende dalla data corrente.

Importi: il sito porta il reddito inserito all'unita' di euro (RN1 "29000,40" -> Reddito
netto 29.000,00, quindi nessuna maggiorazione), come gli importi del modello; il tool
accetta i centesimi. Per questo tutti i casi usano redditi interi.

Tolleranza: 0,01 euro (brief di benchmark); ``_EPS`` assorbe solo la rappresentazione
binaria dei float (una differenza di esattamente 0,01 non deve fallire per 1e-14).
"""

import re
import time
from decimal import ROUND_HALF_UP, Decimal

import pytest

from tests.comparison.conftest import assert_close, extract_amount, goto, parse_euro

PAGE = "calcolo-detrazione-coniuge-a-carico.php"
FORM = "CalcoloDetrazioneConiuge"
TOL = 0.01
_EPS = 1e-9

_HIDE_CMP = (
    ".qc-cmp2-container,#qc-cmp2-container"
    "{display:none !important;pointer-events:none !important}"
)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool_raw(reddito: float) -> dict:
    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)
    from src.tools.dichiarazione_redditi import detrazione_coniuge

    fn = getattr(detrazione_coniuge, "fn", detrazione_coniuge)
    return fn(reddito_complessivo=reddito)


def _tool(reddito: float) -> dict:
    r = _tool_raw(reddito)
    assert "errore" not in r, r
    return r


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _euro_half_up(x: float) -> float:
    return float(Decimal(repr(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _site(page, rn1: str, rn2: str = "", mesi: int = 12) -> dict:
    """Compila il modulo e legge lo sviluppo del calcolo."""
    time.sleep(1.5)  # cortesia verso il sito tra una richiesta e l'altra
    goto(page, PAGE)
    page.add_style_tag(content=_HIDE_CMP)
    page.wait_for_timeout(500)
    page.fill("input[name='RedditoComplessivoDetrazione']", rn1)
    page.fill("input[name='DeduzioneAbitazionePrincipale']", rn2)
    page.select_option("select[name='MesiConiugeCarico']", str(mesi))
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            f"document.forms['{FORM}'].requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_timeout(1500)
    body = page.inner_text("body")

    start = body.find("SVILUPPO del CALCOLO")
    if start < 0:
        return {"calcolato": False, "body": body}
    end = body.find("Pubblicit", start)
    block = body[start:end if end > 0 else start + 1500]

    q = re.search(r"Quoziente\s+(-?[\d.,]+)", block)
    formula = re.search(r"Formula applicata:\s*(.+)", block)
    # con mesi < 12 il sito inserisce "( rapportata a N mesi )" tra etichetta e importo
    rn6 = re.search(r"Detrazione per coniuge a carico spettante[^€]*€\s*([\d.,]+)", block)
    # con quoziente 0 il sito non stampa la riga "Mesi a Carico": vale quella richiesta
    mesi_letti = extract_amount(block, "Mesi a Carico")
    s = {
        "calcolato": True,
        "block": block,
        "anno": re.search(r"Periodo di imposta (\d{4})", block).group(1),
        "reddito_netto": extract_amount(block, "Reddito netto"),
        "mesi_esposti": mesi_letti is not None,
        "mesi": int(mesi_letti) if mesi_letti is not None else mesi,
        "base": extract_amount(block, "Detrazione base"),
        "quoziente": float(q.group(1).replace(",", ".")) if q else None,
        "maggiorazione": extract_amount(block, "Maggiorazione per fascia di reddito") or 0.0,
        "formula": formula.group(1).strip() if formula else "",
        "rn6": parse_euro(rn6.group(1)),
    }
    s["centesimi"] = _ricostruisci(s)
    return s


def _ricostruisci(s: dict) -> float:
    """Valore del sito prima dell'arrotondamento all'euro, dai suoi addendi."""
    f = s["formula"]
    if s["base"] is None:  # oltre 80.000: il sito mostra solo RN6 (0,00)
        return s["rn6"]
    m = s["mesi"] / 12
    if f.startswith("(800 - (110 x Quoziente))"):
        v = (800 - 110 * s["quoziente"]) * m
    elif f.startswith("(690 x Quoziente)"):
        v = 690 * s["quoziente"] * m
    elif f.startswith("(690 x (Mesi / 12)) + Maggiorazione"):
        v = 690 * m + s["maggiorazione"]
    else:  # formula non prevista: si ripiega sugli addendi esposti
        v = s["base"] * m + s["maggiorazione"]
    return round(v, 2)


def _confronta(page, reddito: float, rn1: str | None = None, rn2: str = "",
               label: str = "") -> tuple[dict, dict]:
    t = _tool(reddito)
    s = _site(page, rn1 if rn1 is not None else str(int(reddito)), rn2)
    assert s["calcolato"], f"{label}: il sito non ha prodotto lo sviluppo del calcolo"
    # il driver ha davvero passato i dati al sito
    assert_close(reddito, s["reddito_netto"], 0.01, f"{label} reddito netto")
    assert s["mesi"] == 12, f"{label}: mesi letti dal sito {s['mesi']}"
    assert s["anno"] == "2025", f"{label}: periodo d'imposta del sito {s['anno']}"
    # la ricostruzione in centesimi e' fedele al rigo RN6 del sito
    assert _euro_half_up(s["centesimi"]) == s["rn6"], (
        f"{label}: ricostruzione {s['centesimi']} non coerente con RN6 {s['rn6']} "
        f"(formula '{s['formula']}')"
    )
    assert_close(
        float(t["detrazione"]),
        s["centesimi"],
        TOL + _EPS,
        f"{label} detrazione (sito: base {s['base']}, quoziente {s['quoziente']}, "
        f"maggiorazione {s['maggiorazione']}, RN6 {s['rn6']})",
    )
    return t, s


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_piano_prima_fascia_reddito_10000(page):
    """Piano: 800 - 110 x 0,6666 = 726,67.

    Art. 12, co. 1, lett. a), n. 1, TUIR; co. 4 (quoziente 10.000/15.000 = 0,6666 alla
    quarta cifra). Sito: quoziente 0,6666, 726,674 -> RN6 727,00. Tool 726,67
    (quoziente pieno: 726,6667 -> 726,67).
    """
    _confronta(page, 10000, label="10.000")


def test_piano_maggiorazione_20_reddito_30000(page):
    """Piano: 690 + 20 = 710,00; il tool restituisce 690.

    Art. 12, co. 1, lett. b), n. 2, TUIR (reddito oltre 29.200 e fino a 34.700).
    Scostamento atteso: il tool non applica la maggiorazione.
    """
    _confronta(page, 30000, label="30.000")


def test_piano_maggiorazione_30_reddito_34800(page):
    """Piano: 690 + 30 = 720,00; tool 690.

    Caso al limite (fascia stretta 34.700-35.000). Art. 12, co. 1, lett. b), n. 3, TUIR.
    Scostamento atteso.
    """
    _confronta(page, 34800, label="34.800")


def test_piano_maggiorazione_10_reddito_35150(page):
    """Piano: 690 + 10 = 700,00; tool 690.

    Caso al limite (fascia 35.100-35.200). Art. 12, co. 1, lett. b), n. 5, TUIR.
    Scostamento atteso.
    """
    _confronta(page, 35150, label="35.150")


def test_piano_terza_fascia_reddito_60000(page):
    """Piano: 690 x 20.000 / 40.000 = 345,00.

    Art. 12, co. 1, lett. a), n. 3, TUIR: quoziente 0,5.
    """
    _confronta(page, 60000, label="60.000")


def test_piano_limite_superiore_reddito_80000(page):
    """Piano: 0,00 (caso al limite: reddito = 80.000).

    Art. 12, co. 4, TUIR: rapporto di lett. a) n. 3 uguale a zero, la detrazione non
    compete.
    """
    _confronta(page, 80000, label="80.000")


# ---------------------------------------------------------------------------
# Casi aggiunti (al limite)
# ---------------------------------------------------------------------------

def test_confine_prima_seconda_fascia_reddito_15000(page):
    """Reddito 15.000: 690,00.

    Caso al limite. Art. 12, co. 1, lett. a), n. 1 e co. 4, TUIR: rapporto uguale a uno,
    la detrazione compete nella misura di 690 euro (800 - 110). Tool: 690,00.
    """
    _confronta(page, 15000, label="15.000")


def test_confine_maggiorazione_esclusa_reddito_29000(page):
    """Reddito 29.000: 690,00 (maggiorazione esclusa).

    Caso al limite. Art. 12, co. 1, lett. b), n. 1, TUIR: 10 euro solo se il reddito e'
    "superiore a 29.000"; a 29.000 nessuna maggiorazione. Tool 690.
    """
    _confronta(page, 29000, label="29.000")


def test_confine_maggiorazione_inclusa_reddito_29001(page):
    """Reddito 29.001: 690 + 10 = 700,00; tool 690.

    Caso al limite (primo euro della fascia). Art. 12, co. 1, lett. b), n. 1, TUIR.
    Scostamento atteso.
    """
    _confronta(page, 29001, label="29.001")


def test_confine_ultima_maggiorazione_reddito_35200(page):
    """Reddito 35.200: 690 + 10 = 700,00; tool 690.

    Caso al limite (ultimo euro della fascia, "non a 35.200" incluso). Art. 12, co. 1,
    lett. b), n. 5, TUIR. Scostamento atteso.
    """
    _confronta(page, 35200, label="35.200")


def test_confine_fine_maggiorazioni_reddito_35201(page):
    """Reddito 35.201: 690,00 (fuori dalle maggiorazioni).

    Caso al limite. Art. 12, co. 1, lett. a), n. 2 e lett. b), TUIR.
    """
    _confronta(page, 35201, label="35.201")


def test_confine_terza_fascia_troncamento_reddito_40001(page):
    """Reddito 40.001: 690 x 0,9999 = 689,93 (norma); tool 689,98.

    Caso al limite (primo euro della terza fascia). Art. 12, co. 1, lett. a), n. 3 e
    co. 4, TUIR: (80.000 - 40.001) / 40.000 = 0,999975 "si assume nelle prime quattro
    cifre decimali" -> 0,9999 -> 689,9310 -> 689,93 (RN6 690). Il tool usa il rapporto
    pieno: 690 x 0,999975 = 689,98275 -> 689,98. Scostamento atteso di 0,05.
    """
    _confronta(page, 40001, label="40.001")


def test_limite_un_euro_sotto_soglia_reddito_79999(page):
    """Reddito 79.999: 0,00 (norma); tool 0,02.

    Caso al limite. Art. 12, co. 4, TUIR: 1 / 40.000 = 0,000025 -> 0,0000 alla quarta
    cifra decimale -> 690 x 0 = 0,00. Il tool: 690 x 0,000025 = 0,01725 -> 0,02.
    Scostamento atteso (quoziente non troncato).
    """
    _confronta(page, 79999, label="79.999")


def test_confine_oltre_soglia_reddito_80001(page):
    """Reddito 80.001: 0,00 (primo euro oltre la terza fascia).

    Caso al limite (quarto ramo del tool, "oltre 80.000"). Art. 12, co. 1, lett. a),
    n. 3, TUIR: la detrazione spetta solo se il reddito "non" supera 80.000; oltre, il
    rapporto (80.000 - 80.001) / 40.000 e' negativo e nulla compete. Sito: espone solo
    Reddito netto 80.001,00 e RN6 0,00 (nessuna detrazione base ne' quoziente).
    """
    _confronta(page, 80001, label="80.001")


def test_deduzione_abitazione_principale_riporta_a_40000(page):
    """RN1 42.000, RN2 2.000: reddito netto 40.000 -> 690,00.

    Caso al limite (confine 40.000 raggiunto via RN2). Art. 12, co. 4-bis, TUIR: il
    reddito complessivo si assume al netto dell'abitazione principale. Il tool non ha
    il parametro: riceve il reddito gia' netto (40.000). Verifica la convenzione.
    """
    _confronta(page, 40000, rn1="42000", rn2="2000", label="42.000 - 2.000")


def test_mesi_a_carico_non_modellati(page):
    """Sei mesi a carico, reddito 30.000: non confrontabile.

    Opzione enumerata del sito (MesiConiugeCarico 1-12). Art. 12, co. 3, TUIR: le
    detrazioni per carichi di famiglia sono rapportate a mese. Il tool non ha un
    parametro per i mesi (calcola sempre 12/12): il valore del sito viene letto e
    registrato, poi il caso si salta.
    """
    t = _tool(30000)
    s = _site(page, "30000", mesi=6)
    assert s["calcolato"], "il sito non ha prodotto lo sviluppo del calcolo"
    assert s["mesi"] == 6, f"mesi letti dal sito {s['mesi']}"
    pytest.skip(
        f"non confrontabile: il tool non rapporta a mese (co. 3); tool {t['detrazione']} "
        f"(12 mesi), sito {s['centesimi']} con 6 mesi, formula '{s['formula']}', "
        f"RN6 {s['rn6']}"
    )


def test_reddito_zero_rifiutato_da_entrambi(page):
    """Reddito 0: il sito non calcola ("Specifica un valore"), il tool restituisce errore.

    Caso al limite. Art. 12, co. 4, TUIR: se il rapporto di lett. a) n. 1 e' uguale a
    zero la detrazione non compete (0,00); entrambi rifiutano l'input invece di
    restituire 0,00. Si verifica che il comportamento coincida.
    """
    t = _tool_raw(0)
    assert "errore" in t, t
    s = _site(page, "0")
    assert not s["calcolato"], f"il sito ha calcolato con reddito 0: {s.get('block')}"
    assert "Specifica un valore" in s["body"]
