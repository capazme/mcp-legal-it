"""Benchmark fase 1: detrazione_figli vs avvocatoandreani.it.

Pagina principale: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-figli-21-anni.php
Modulo ``CalcoloDetrazioneFigli`` (POST): ``RedditoComplessivoDetrazione`` (rigo RN1
col. 1), ``DeduzioneAbitazionePrincipale`` (rigo RN2), ``NumeroFigliCarico`` (select
1-10) e, per ciascun figlio, ``MesiCarico{i}`` (1-12, default 12) e ``PctFiglio{i}``
(0/50/100, default **50**: il driver forza 12 mesi e 100%, l'unico scenario che il
tool modella). Nessun campo per la disabilita'. Il pulsante ``input[name=Op]`` non
risponde al click (overlay pubblicitari): il modulo si invia con ``requestSubmit``.

Pagina secondaria (solo per la maggiorazione disabili): calcolo-detrazione-figli-a-carico.php,
stesso nome di modulo, con ``Mesi3Anni{i}``, ``Disabile{i}`` (checkbox) e
``PctUlterioreDetrazione``. Il sito stesso la dichiara "valida solo fino alla
dichiarazione 2022": modella il regime previgente al D.Lgs. 230/2021.

Risultato (entrambe le pagine): blocco "SVILUPPO del CALCOLO -- Periodo di imposta
2025 - Dichiarazione dei redditi 2026" con Reddito per detrazioni, Numero figli a
carico, Detrazione teorica complessiva, Quoziente di riduzione, "Detrazione figli
effettiva" (in centesimi) e "RN6 Col.2 Detrazione figli spettante" (arrotondata
all'euro, come nel modello).

Confronto: ``detrazione_totale`` del tool (centesimi, nessun arrotondamento all'euro)
contro "Detrazione figli effettiva" del sito, cioe' la stessa grandezza prima
dell'arrotondamento dichiarativo; il rigo RN6 e' riportato solo nei commenti.

Norma (art. 12 TUIR vigente, letto su Normattiva con cite_law il 2026-09-25):
- co. 1, lett. c): 950 euro per ciascun figlio di eta' pari o superiore a 21 anni ma
  inferiore a 30 (o di 30 anni e oltre se disabile ex art. 3 L. 104/1992; limite
  introdotto dalla L. 207/2024), "per la parte corrispondente al rapporto tra
  l'importo di 95.000 euro, diminuito del reddito complessivo, e 95.000 euro"; con piu'
  figli "l'importo di 95.000 euro e' aumentato per tutti di 15.000 euro per ogni
  figlio successivo al primo". I periodi sulla maggiorazione di 400 euro per il figlio
  disabile risultano "SOPPRESSI DAL D.LGS. 21 DICEMBRE 2021, N. 230".
- co. 4: se i rapporti di cui alle lett. c) e d) sono "pari a zero, minori di zero o
  uguali a uno, le detrazioni non competono. Negli altri casi, il risultato dei predetti
  rapporti si assume nelle prime quattro cifre decimali".
Il sito tronca il quoziente alla quarta cifra (co. 4) e poi tronca anche i centesimi
del prodotto (1.900 x 0,7272 = 1.381,68 esposto come 1.381,67); il tool usa il
coefficiente a precisione piena, arrotonda per figlio e riconosce la detrazione piena
con reddito zero (rapporto = 1).

Anno: il sito calcola per il periodo d'imposta 2025 (nessuna scelta dell'anno); il tool
non ha tabelle annuali e non legge l'orologio (nessun LEGAL_TODAY necessario).

Tolleranza: 0,01 euro (brief di benchmark), confrontata in centesimi interi per non
far fallire per rappresentazione binaria un caso che dista esattamente un centesimo.
"""

import re
import time

import pytest

from tests.comparison.conftest import extract_amount, goto, parse_euro

PAGE = "calcolo-detrazione-figli-21-anni.php"
PAGE_PREVIGENTE = "calcolo-detrazione-figli-a-carico.php"
FORM = "CalcoloDetrazioneFigli"
TOL_CENT = 1  # 0,01 euro

_HIDE_CMP = (
    ".qc-cmp2-container,#qc-cmp2-container"
    "{display:none !important;pointer-events:none !important}"
)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(reddito: float, n: int, disabili: int = 0) -> dict:
    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)
    from src.tools.dichiarazione_redditi import detrazione_figli

    fn = getattr(detrazione_figli, "fn", detrazione_figli)
    r = fn(reddito_complessivo=reddito, n_figli_over21=n, n_figli_disabili=disabili)
    assert "errore" not in r, r
    return r


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _submit_and_read(page) -> dict:
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "(()=>{const f=document.forms['" + FORM + "'];"
            "f.requestSubmit(f.querySelector('input[type=submit]'))})()"
        )
    page.wait_for_timeout(1500)
    body = page.inner_text("body")

    start = body.find("SVILUPPO del CALCOLO")
    if start < 0:
        return {"calcolato": False, "body": body}
    end = body.find("Pubblicit", start)
    block = body[start:end if end > 0 else start + 1500]

    q = re.search(r"Quoziente di riduzione\s+(-?[\d.,]+)", block)
    rn6 = re.search(r"Detrazione figli spettante\s+€\s*([\d.,]+)", block)
    return {
        "calcolato": True,
        "block": block,
        "anno": re.search(r"Periodo di imposta (\d{4})", block).group(1),
        "reddito": extract_amount(block, "Reddito per detrazioni"),
        "n": int(extract_amount(block, "Numero figli a carico")),
        "teorica": extract_amount(block, "Detrazione teorica complessiva"),
        "quoziente": float(q.group(1).replace(".", "").replace(",", ".")),
        "effettiva": extract_amount(block, "Detrazione figli effettiva"),
        "spettante_rn6": parse_euro(rn6.group(1)),
    }


def _open(page, path: str) -> None:
    time.sleep(1.5)  # cortesia verso il sito tra una richiesta e l'altra
    goto(page, path)
    page.add_style_tag(content=_HIDE_CMP)
    page.wait_for_timeout(500)


def _site(page, rn1: str, n: int) -> dict:
    """Pagina figli >= 21 anni: tutti i figli 12 mesi al 100%."""
    _open(page, PAGE)
    page.fill("input[name='RedditoComplessivoDetrazione']", rn1)
    page.fill("input[name='DeduzioneAbitazionePrincipale']", "")
    page.select_option("select[name='NumeroFigliCarico']", str(n))
    for i in range(1, n + 1):
        page.select_option(f"select[name='MesiCarico{i}']", "12")
        page.select_option(f"select[name='PctFiglio{i}']", "100")
    return _submit_and_read(page)


def _site_previgente(page, rn1: str, n: int, disabili: int) -> dict:
    """Pagina figli a carico (regime fino alla dichiarazione 2022), con disabilita'."""
    _open(page, PAGE_PREVIGENTE)
    page.fill("input[name='RedditoComplessivoDetrazione']", rn1)
    page.fill("input[name='DeduzioneAbitazionePrincipale']", "")
    page.select_option("select[name='NumeroFigliCarico']", str(n))
    for i in range(1, n + 1):
        page.select_option(f"select[name='MesiCarico{i}']", "12")
        page.select_option(f"select[name='Mesi3Anni{i}']", "0")
        page.select_option(f"select[name='PctFiglio{i}']", "100")
        # il click (anche forzato) puo' finire sugli overlay pubblicitari: si imposta
        # lo stato della checkbox direttamente, poi lo si rilegge
        checked = i > n - disabili
        box = f"input[name='Disabile{i}']"
        page.eval_on_selector(box, f"el => {{ el.checked = {str(checked).lower()}; }}")
        assert page.is_checked(box) is checked
    return _submit_and_read(page)


def _cent(x: float) -> int:
    return int(round(x * 100))


def _assert_eq(tool_val: float, s: dict, label: str) -> None:
    diff = abs(_cent(tool_val) - _cent(s["effettiva"]))
    assert diff <= TOL_CENT, (
        f"{label}: tool={tool_val:.2f}, sito={s['effettiva']:.2f} "
        f"(quoziente sito {s['quoziente']}, RN6 sito {s['spettante_rn6']:.2f}), "
        f"diff={diff / 100:.2f} (max 0,01)"
    )


def _confronta(page, reddito: float, n: int, rn1: str | None = None, label: str = "",
               reddito_sito: float | None = None) -> tuple[dict, dict]:
    t = _tool(reddito, n)
    s = _site(page, rn1 if rn1 is not None else str(int(reddito)), n)
    assert s["calcolato"], f"{label}: il sito non ha prodotto lo sviluppo del calcolo"
    # il driver ha davvero passato i dati al sito
    assert s["n"] == n, f"{label}: figli letti dal sito {s['n']} != {n}"
    atteso_reddito = reddito if reddito_sito is None else reddito_sito
    assert _cent(s["reddito"]) == _cent(atteso_reddito), (
        f"{label}: reddito letto dal sito {s['reddito']} != {atteso_reddito}"
    )
    assert s["anno"] == "2025", f"{label}: periodo d'imposta del sito {s['anno']}"
    assert _cent(s["teorica"]) == 950 * n * 100, f"{label}: teorica sito {s['teorica']}"
    _assert_eq(float(t["detrazione_totale"]), s, label)
    return t, s


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_piano_due_figli_reddito_30000(page):
    """Piano: soglia 110.000 (art. 12, co. 1, lett. c), TUIR: 95.000 + 15.000 per il
    secondo figlio); quoziente 0,7272 (co. 4, quarta cifra); 950 x 0,7272 = 690,84 per
    figlio, totale 1.381,68 (tool 1.381,82 con coefficiente non troncato).

    Sito: teorica 1.900,00, quoziente 0,7272, effettiva 1.381,67 (il sito tronca anche i
    centesimi del prodotto 1.381,68), RN6 1.382,00. Scostamento atteso: 0,15.
    """
    _confronta(page, 30000, 2, label="30.000 / 2 figli")


def test_piano_figlio_disabile_reddito_40000_pagina_previgente(page):
    """Piano: 1.350 (950 + 400) x 0,5789 = 781,51 circa (tool 781,58).

    La pagina principale non ha il campo disabilita'. L'unica pagina del sito che lo
    offre e' quella "valida solo fino alla dichiarazione 2022" (regime anteriore al
    D.Lgs. 230/2021, che ha soppresso i periodi sulla maggiorazione di 400 euro dell'art.
    12, co. 1, lett. c), TUIR). Confronto sul regime che il tool riproduce.
    Sito: teorica 1.350,00, quoziente 0,5789, effettiva 781,51, RN6 782,00.
    Scostamento atteso: 0,07 (troncamento del quoziente, co. 4).
    """
    t = _tool(40000, 1, disabili=1)
    s = _site_previgente(page, "40000", 1, 1)
    assert s["calcolato"], "il sito non ha prodotto lo sviluppo del calcolo"
    assert s["n"] == 1 and _cent(s["reddito"]) == 4000000
    assert _cent(s["teorica"]) == 135000, f"teorica sito {s['teorica']} (disabile non letto?)"
    _assert_eq(float(t["detrazione_totale"]), s, "40.000 / 1 figlio disabile (pagina previgente)")


def test_piano_reddito_pari_alla_soglia_95000(page):
    """Piano: 0,00. Caso al limite: rapporto (95.000 - 95.000)/95.000 = 0, la
    detrazione non compete (art. 12, co. 4, TUIR).

    Sito: quoziente 0, effettiva 0,00, RN6 0,00.
    """
    _confronta(page, 95000, 1, label="95.000 / 1 figlio (soglia)")


def test_piano_un_euro_sotto_la_soglia_di_due_figli(page):
    """Piano: coefficiente 0,0000 alla quarta cifra decimale, detrazione 0,00 (il tool
    restituisce 0,02). Caso al limite: soglia 110.000 (co. 1, lett. c); rapporto
    1/110.000 = 0,0000090 troncato a 0,0000 (co. 4).

    Sito: quoziente 0, effettiva 0,00. Scostamento atteso: 0,02.
    """
    _confronta(page, 109999, 2, label="109.999 / 2 figli")


# ---------------------------------------------------------------------------
# Casi al limite aggiunti
# ---------------------------------------------------------------------------

def test_limite_figlio_disabile_reddito_40000_regime_vigente(page):
    """Opzione n_figli_disabili sul regime vigente. Art. 12, co. 1, lett. c), TUIR
    (testo Normattiva): 950 euro per ciascun figlio >= 21 anni; la disabilita' rileva
    solo per ammettere i figli di 30 anni e oltre; la maggiorazione di 400 euro e'
    soppressa dal D.Lgs. 230/2021 (dal 1 marzo 2022). La pagina principale, che modella
    il periodo d'imposta 2025, non ha quindi un campo disabilita': per un figlio
    disabile la detrazione spettante coincide con quella di un figlio qualsiasi.

    Atteso di legge: 950 x 0,5789 = 549,95 (troncamento co. 4). Tool: 1.350 x
    0,578947... = 781,58. Sito: effettiva 549,95, RN6 550,00.
    """
    t = _tool(40000, 1, disabili=1)
    s = _site(page, "40000", 1)
    assert s["calcolato"], "il sito non ha prodotto lo sviluppo del calcolo"
    assert s["n"] == 1 and _cent(s["reddito"]) == 4000000 and s["anno"] == "2025"
    _assert_eq(float(t["detrazione_totale"]), s, "40.000 / 1 figlio disabile (regime vigente)")


def test_limite_tre_figli_quoziente_esatto(page):
    """Opzione n = 3: soglia 95.000 + 2 x 15.000 = 125.000 (co. 1, lett. c).
    Reddito 50.000: rapporto 75.000/125.000 = 0,6 esatto, nessun effetto del
    troncamento (co. 4). Atteso 2.850 x 0,6 = 1.710,00.
    """
    _confronta(page, 50000, 3, label="50.000 / 3 figli")


def test_limite_dieci_figli_ultima_opzione(page):
    """Ultima opzione del sito (n = 10): soglia 95.000 + 9 x 15.000 = 230.000
    (co. 1, lett. c). Reddito 115.000: rapporto 0,5 esatto. Atteso 9.500 x 0,5 = 4.750,00.
    """
    _confronta(page, 115000, 10, label="115.000 / 10 figli")


def test_limite_reddito_zero_rapporto_uguale_a_uno(page):
    """Reddito complessivo 0: rapporto (95.000 - 0)/95.000 = 1. Art. 12, co. 4, TUIR:
    se il rapporto e' "uguale a uno" la detrazione non compete. Atteso di legge 0,00;
    il tool (coefficiente limitato a 1, non escluso) restituisce 950,00.

    Il sito rifiuta "0" come campo vuoto ("Specifica un valore"): si immette "0,4", che
    il sito arrotonda all'euro (nota della pagina) e mostra come reddito 0,00, quoziente
    1, effettiva 0,00. Il test verifica che il sito abbia davvero usato reddito 0.
    """
    _confronta(page, 0, 1, rn1="0,4", reddito_sito=0.0, label="0 / 1 figlio")


def test_limite_troncamento_entro_un_centesimo(page):
    """Un figlio, reddito 30.000: rapporto 65.000/95.000 = 0,684210... troncato a
    0,6842 (co. 4): 950 x 0,6842 = 649,999 esposto dal sito come 649,99 (troncamento
    dei centesimi); il tool restituisce 650,00. Differenza di un centesimo, entro la
    tolleranza del brief.
    """
    _confronta(page, 30000, 1, label="30.000 / 1 figlio")
