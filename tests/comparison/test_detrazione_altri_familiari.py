"""Benchmark fase 1: detrazione_altri_familiari vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-altri-familiari-a-carico.php
Modulo ``CalcoloDetrazioneFamiliari`` (POST): ``RedditoComplessivoDetrazione`` (rigo
RN1 col. 1), ``DeduzioneAbitazionePrincipale`` (rigo RN2), ``NumeroFamiliariCarico``
(select 1-6) e, per ciascun familiare, ``MesiCaricoFam{i}`` (1-12, default 12) e
``PctSpettFam{i}`` (100/50/33.33/25/20/0, default **50**: il driver forza 100 e 12
mesi, l'unico scenario che il tool modella). Pulsante ``#btn-calc``: il click non
parte (overlay pubblicitari), il modulo si invia con ``requestSubmit``.

Risultato: blocco "SVILUPPO del CALCOLO -- Periodo di imposta 2025 - Dichiarazione
dei redditi 2026" con le righe Reddito netto (RN1 - RN2), Numero altri familiari a
carico, Detrazione teorica complessiva, Quoziente di riduzione, Detrazione in base al
reddito (in centesimi) e "RN6 Col.4 Detrazione altri familiari spettante"
(arrotondata all'unita' di euro, half-up, come nel modello).

Confronto: ``detrazione_totale`` del tool (in centesimi, nessun arrotondamento
all'euro) contro "Detrazione in base al reddito" del sito, cioe' la stessa grandezza
prima dell'arrotondamento dichiarativo. Il valore del rigo RN6 e' riportato solo nei
commenti: la differenza e' di convenzione di presentazione, non di calcolo.

Norma: art. 12, co. 1, lett. d), TUIR (D.P.R. 917/1986) -- 750 euro per ciascun
ascendente convivente, "per la parte corrispondente al rapporto tra l'importo di
80.000 euro, diminuito del reddito complessivo, e 80.000 euro"; co. 4: se il rapporto
e' pari a zero, minore di zero o uguale a uno la detrazione non compete, "negli altri
casi, il risultato dei predetti rapporti si assume nelle prime quattro cifre
decimali"; co. 4-bis: reddito complessivo al netto dell'abitazione principale.
Il sito tronca il quoziente alla quarta cifra decimale (co. 4); il tool usa il
coefficiente a precisione piena: da qui gli scostamenti attesi nei casi 79.999,
26.811 e 1 euro.

Anno: il sito calcola per il periodo d'imposta 2025 (nessuna scelta dell'anno); il
tool non ha tabelle annuali (750 euro e soglia 80.000 costanti dal 2022; la L.
207/2024 ha ristretto dal 2025 i beneficiari agli ascendenti conviventi senza toccare
importo e soglia). Il tool non dipende dalla data corrente (nessun LEGAL_TODAY).

Tolleranza: 0,01 euro (brief di benchmark).
"""

import re
import time

import pytest

from tests.comparison.conftest import assert_close, extract_amount, goto, parse_euro

PAGE = "calcolo-detrazione-altri-familiari-a-carico.php"
FORM = "CalcoloDetrazioneFamiliari"
TOL = 0.01

_HIDE_CMP = (
    ".qc-cmp2-container,#qc-cmp2-container"
    "{display:none !important;pointer-events:none !important}"
)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(reddito: float, n: int) -> dict:
    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)
    from src.tools.dichiarazione_redditi import detrazione_altri_familiari

    fn = getattr(detrazione_altri_familiari, "fn", detrazione_altri_familiari)
    r = fn(reddito_complessivo=reddito, n_familiari=n)
    assert "errore" not in r, r
    return r


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _site(page, rn1: str, n: int, rn2: str = "") -> dict:
    """Compila il modulo (tutti i familiari 12 mesi al 100%) e legge lo sviluppo."""
    time.sleep(1.5)  # cortesia verso il sito tra una richiesta e l'altra
    goto(page, PAGE)
    page.add_style_tag(content=_HIDE_CMP)
    page.wait_for_timeout(500)
    page.fill("input[name='RedditoComplessivoDetrazione']", rn1)
    page.fill("input[name='DeduzioneAbitazionePrincipale']", rn2)
    page.select_option("select[name='NumeroFamiliariCarico']", str(n))
    for i in range(1, n + 1):
        page.select_option(f"select[name='MesiCaricoFam{i}']", "12")
        page.select_option(f"select[name='PctSpettFam{i}']", "100")
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

    q = re.search(r"Quoziente di riduzione\s+(-?[\d.,]+)", block)
    spett = re.search(r"Detrazione altri familiari spettante\s+€\s*([\d.,]+)", block)
    return {
        "calcolato": True,
        "block": block,
        "anno": re.search(r"Periodo di imposta (\d{4})", block).group(1),
        "reddito_netto": extract_amount(block, "Reddito netto"),
        "n": int(extract_amount(block, "Numero altri familiari a carico")),
        "teorica": extract_amount(block, "Detrazione teorica complessiva"),
        "quoziente": float(q.group(1).replace(",", ".")),
        "in_base_al_reddito": extract_amount(block, "Detrazione in base al reddito"),
        "spettante_rn6": parse_euro(spett.group(1)),
    }


def _confronta(page, reddito: float, n: int, rn1: str | None = None, rn2: str = "",
               label: str = "") -> tuple[dict, dict]:
    t = _tool(reddito, n)
    s = _site(page, rn1 if rn1 is not None else str(int(reddito)), n, rn2)
    assert s["calcolato"], f"{label}: il sito non ha prodotto lo sviluppo del calcolo"
    # il driver ha davvero passato i dati al sito
    assert s["n"] == n, f"{label}: familiari letti dal sito {s['n']} != {n}"
    assert_close(reddito, s["reddito_netto"], 0.01, f"{label} reddito netto")
    assert s["anno"] == "2025", f"{label}: periodo d'imposta del sito {s['anno']}"
    assert_close(
        float(t["detrazione_totale"]),
        s["in_base_al_reddito"],
        TOL,
        f"{label} detrazione (quoziente sito {s['quoziente']}, RN6 sito {s['spettante_rn6']})",
    )
    return t, s


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_piano_due_familiari_reddito_40000(page):
    """Piano: 750 x 0,5 = 375,00 ciascuno, totale 750,00.

    Art. 12, co. 1, lett. d), TUIR: (80.000 - 40.000) / 80.000 = 0,5.
    Sito: teorica 1.500,00, quoziente 0,5, in base al reddito 750,00, RN6 750,00.
    """
    _confronta(page, 40000, 2, label="40.000 / 2 familiari")


def test_piano_un_familiare_reddito_20000(page):
    """Piano: 750 x 0,75 = 562,50.

    Art. 12, co. 1, lett. d), TUIR: quoziente 0,75. Sito: in base al reddito 562,50;
    RN6 563,00 (arrotondamento all'euro del modello, non applicato dal tool).
    """
    _confronta(page, 20000, 1, label="20.000 / 1 familiare")


def test_piano_reddito_pari_alla_soglia(page):
    """Piano: 0,00 (caso al limite: reddito = 80.000).

    Art. 12, co. 4, TUIR: rapporto pari a zero, la detrazione non compete.
    """
    _confronta(page, 80000, 1, label="80.000 / 1 familiare")


def test_piano_un_euro_sotto_soglia_tre_familiari(page):
    """Piano: coefficiente 0,0000 alla quarta cifra decimale: 0,00 (tool 0,03).

    Caso al limite. Art. 12, co. 4, TUIR: il rapporto (1/80.000 = 0,0000125) "si
    assume nelle prime quattro cifre decimali" -> 0,0000 -> detrazione 0,00. Il tool
    usa il coefficiente pieno: 750 x 0,0000125 = 0,009375 -> 0,01 per familiare,
    0,03 in totale. Scostamento atteso.
    """
    _confronta(page, 79999, 3, label="79.999 / 3 familiari")


# ---------------------------------------------------------------------------
# Casi aggiunti
# ---------------------------------------------------------------------------

def test_troncamento_quarta_cifra_decimale(page):
    """Reddito 26.811, tre familiari (convenzione del quoziente).

    Art. 12, co. 4, TUIR: (80.000 - 26.811) / 80.000 = 0,6648625 -> 0,6648.
    Atteso secondo norma: 2.250 x 0,6648 = 1.495,80 (RN6 1.496). Il tool:
    750 x 0,6648625 = 498,646875 -> 498,65 per familiare, x 3 = 1.495,95.
    Scostamento atteso (quoziente non troncato).
    """
    _confronta(page, 26811, 3, label="26.811 / 3 familiari")


def test_sei_familiari_opzione_massima_del_sito(page):
    """Sei familiari (ultima opzione del select del sito), reddito 30.000.

    Caso al limite (opzione enumerata). Art. 12, co. 1, lett. d), TUIR: quoziente
    0,625; 6 x 750 x 0,625 = 2.812,50 (RN6 2.813, parte decimale di 50 centesimi
    arrotondata all'euro superiore).
    """
    _confronta(page, 30000, 6, label="30.000 / 6 familiari")


def test_reddito_un_euro_sopra_soglia(page):
    """Reddito 80.001: rapporto negativo.

    Caso al limite. Art. 12, co. 4, TUIR: rapporto minore di zero, la detrazione non
    compete -> 0,00 (il sito mostra il quoziente come "-0").
    """
    _confronta(page, 80001, 1, label="80.001 / 1 familiare")


def test_quoziente_minimo_rappresentabile(page):
    """Reddito 79.992: rapporto 8/80.000 = 0,0001 esatto.

    Caso al limite: il piu' piccolo quoziente che sopravvive al troncamento alla
    quarta cifra (art. 12, co. 4, TUIR). 750 x 0,0001 = 0,075 -> 0,07 in virgola
    mobile (sia tool sia sito); RN6 0,00.
    """
    _confronta(page, 79992, 1, label="79.992 / 1 familiare")


def test_reddito_un_euro_quoziente_quasi_uno(page):
    """Reddito 1 euro: rapporto 79.999/80.000 = 0,9999875.

    Caso al limite (quoziente vicino a uno). Art. 12, co. 4, TUIR: si assume 0,9999
    -> 750 x 0,9999 = 749,925 (il sito mostra 749,92; RN6 750). Il tool: 750 x
    0,9999875 = 749,99. Scostamento atteso (quoziente non troncato).
    """
    _confronta(page, 1, 1, label="1 euro / 1 familiare")


def test_deduzione_abitazione_principale(page):
    """RN1 45.000 e RN2 5.000: il sito calcola sul reddito netto 40.000.

    Art. 12, co. 4-bis, TUIR: il reddito complessivo si assume al netto
    dell'abitazione principale. Il tool non ha il campo RN2: riceve direttamente il
    reddito gia' al netto (40.000). Atteso: 750 x 0,5 = 375,00.
    """
    _confronta(page, 40000, 1, rn1="45000", rn2="5000", label="45.000 - 5.000 / 1 familiare")


def test_reddito_zero_quoziente_uno(page):
    """Reddito 0: rapporto uguale a uno.

    Caso al limite. Art. 12, co. 4, TUIR: se il rapporto di cui alla lett. d) e'
    "uguale a uno" la detrazione non compete -> 0,00. Il tool restituisce 750,00
    (coefficiente limitato a 1, nessuna esclusione). Il sito non accetta 0 nel
    campo RN1 ("Specifica un valore") e non calcola: caso non confrontabile.
    """
    t = _tool(0, 1)
    s = _site(page, "0", 1)
    if not s["calcolato"]:
        assert "Specifica un valore" in s["body"]
        pytest.skip(
            "sito_non_calcola: RN1 = 0 rifiutato ('Specifica un valore'); "
            f"tool {t['detrazione_totale']}, norma (art. 12 co. 4 TUIR) 0,00"
        )
    assert_close(float(t["detrazione_totale"]), s["in_base_al_reddito"], TOL, "reddito 0")


def test_mesi_e_percentuale_non_confrontabile():
    """Familiare a carico 8 mesi al 50% (esempio della pagina del sito).

    Art. 12, co. 3 e lett. d), TUIR: la detrazione si rapporta ai mesi a carico e si
    ripartisce pro quota tra gli aventi diritto. Il sito offre mesi (1-12) e
    percentuale (100/50/33/25/20/0); il tool non ha ne' mesi ne' percentuale e
    calcola sempre 12 mesi al 100%: caso non confrontabile.
    """
    pytest.skip(
        "non_confrontabile: il tool non ha i parametri mesi a carico e % di spettanza "
        "(il sito, a 40.000 euro, 8 mesi al 50%: teorica 250,00, detrazione 125,00)"
    )
