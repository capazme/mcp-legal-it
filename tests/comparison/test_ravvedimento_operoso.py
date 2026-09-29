"""Benchmark fase 1: ravvedimento_operoso vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-ravvedimento-operoso.php
(duplicato interno sotto /utility/, stesso modulo). Il calcolatore NON richiede
piu' il login (il vecchio tests/comparison/test_ravvedimento.py e' saltato per
questo motivo, ma dal 2026-09-25 il modulo risponde a una sessione anonima).

Modulo "RavvedimentoOperoso" (POST): ``IdTributo`` (qui sempre ``1_2`` = 4001
IRPEF Saldo: il codice tributo cambia solo i codici F24 esposti, non il calcolo),
``Importo``, data di scadenza in tre select (``GiornoScad``/``MeseScad``/
``AnnoScad``), data del ravvedimento in tre select (``GiornoRavv``/``MeseRavv``/
``AnnoRavv``), pulsante ``#create``. Risultato: una tabella di riepilogo con
"Giorni di ritardo", "Norma applicata: '...' (1/N del minimo)", la riga
"Cod. trib. 8901 - SANZIONE (formula = x,xx%): EUR" e la riga "Cod. trib. 1989 -
INTERESSI: EUR"; una tabella degli interessi per anno (tasso legale di ciascun
anno); il prospetto F24 con il TOTALE.

Il tool lavora sui giorni di ritardo, il sito sulle date: il test ricava i giorni
dalle due date (dies a quo escluso, come il sito) e li passa al tool; il numero
di giorni mostrato dal sito e' verificato uguale.

Norme: art. 13, co. 1, D.Lgs. 471/1997 (sanzione 25% per le violazioni dal
01/09/2024, D.Lgs. 87/2024; dimezzata entro 90 giorni; entro 15 giorni ulteriore
riduzione a 1/15 per giorno); art. 13, co. 1, lett. a), a-bis), b), b-bis),
b-ter) D.Lgs. 472/1997 nel testo vigente (letto con cite_law il 2026-09-25):
b) 1/8 entro il termine della dichiarazione relativa all'anno della violazione;
b-bis) 1/7 OLTRE quel termine, senza limite superiore; b-ter) 1/6 solo dopo la
comunicazione dello schema d'atto (art. 6-bis L. 212/2000). Art. 13, co. 2:
interessi moratori al tasso legale con maturazione giorno per giorno.

Convenzioni osservate sul sito (2026-09-25):
- percentuale della sanzione arrotondata a due decimali PRIMA di applicarla
  all'imposta (1/9 x 12,5% = 1,39% -> 13,90 su 1.000; il tool calcola 13,89);
- interessi: tasso legale di ciascun anno solare (2,5% 2024, 2% 2025, 1,6%
  2026), divisore 365 anche nel 2024 bisestile, ogni tratto arrotondato al
  centesimo e poi sommato; il tool applica l'ultimo tasso (1,6%) a tutto il
  periodo;
- soglia della lett. b): 31 ottobre dell'anno successivo a quello della
  violazione (termine della dichiarazione), non 365 giorni fissi;
- oltre il termine della dichiarazione dell'anno successivo il sito applica 1/6
  (lett. b-ter nel testo previgente al D.Lgs. 87/2024);
- regime previgente (base 30%) per le scadenze anteriori al 01/09/2024;
- nel TOTALE F24 non entrano gli importi inferiori a 1,03 euro (nota (2) del
  sito): il test confronta quindi il totale del tool con imposta + sanzione +
  interessi esposti dal sito, e riporta il TOTALE F24 solo nei messaggi.

Tolleranza: 0,01 euro (brief di benchmark); giorni e frazione di riduzione
esatti. I test confrontano tool == sito e raccolgono tutte le differenze del
caso in un'unica asserzione: uno scostamento genuino resta un fallimento (lo
giudica la fase 2). Il tool non dipende dalla data corrente.
"""

import re
from datetime import date

import pytest

from tests.comparison.conftest import accept_cookies, goto, parse_euro, submit_form

PAGE = "calcolo-ravvedimento-operoso.php"
TOL = 0.01
TRIBUTO_IRPEF_SALDO = "1_2"  # 4001 - IRPEF Saldo


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

_FRAZIONE_TOOL = {
    "sprint": 10,
    "breve": 10,
    "intermedio": 9,
    "lungo": 8,
    "biennale": 7,
    "ultrannuale": 6,
}


def _tool(imposta: float, giorni: int, tipo: str = "omesso_versamento") -> dict:
    import importlib

    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)

    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod.ravvedimento_operoso, "fn", mod.ravvedimento_operoso)
    r = fn(imposta_dovuta=imposta, giorni_ritardo=giorni, tipo=tipo)
    assert "errore" not in r, r
    etichetta = r["tipo_ravvedimento"].split()[0]
    return {
        "sanzione": float(r["sanzione"]),
        "interessi": float(r["interessi_legali"]["importo"]),
        "totale": float(r["totale_dovuto"]),
        "frazione": _FRAZIONE_TOOL[etichetta],
        "etichetta": r["tipo_ravvedimento"],
        "pct": r["sanzione_ridotta_pct"],
        "raw": r,
    }


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _select_date(page, prefix: str, d: date) -> None:
    page.select_option(f"#Giorno{prefix}", f"{d.day:02d}")
    page.select_option(f"#Mese{prefix}", f"{d.month:02d}")
    page.select_option(f"#Anno{prefix}", str(d.year))


def _site(page, importo: float, scadenza: date, ravvedimento: date) -> dict:
    page.wait_for_timeout(1500)  # cortesia verso il sito tra un caso e l'altro
    goto(page, PAGE)
    page.select_option("#IdTributo", TRIBUTO_IRPEF_SALDO)
    page.fill("#Importo", f"{importo:.2f}".replace(".", ","))
    _select_date(page, "Scad", scadenza)
    _select_date(page, "Ravv", ravvedimento)
    # Il banner Quantcast (qc-cmp2) si carica dopo goto() e copre il pulsante:
    # lo si rimuove di nuovo subito prima dell'invio.
    accept_cookies(page)
    submit_form(page, btn_selector="#create")

    tables = [t.inner_text().strip() for t in page.query_selector_all("table")]
    riepilogo = next((t for t in tables if "Omesso o insufficiente versamento" in t), None)
    assert riepilogo, "il sito non ha prodotto la tabella di riepilogo del ravvedimento"

    giorni = int(re.search(r"Giorni di ritardo[^:]*:\s*(\d+)", riepilogo).group(1))
    norma = re.search(r"Norma applicata:\s*(.+?)\t\s*(.+)", riepilogo)
    frazione = int(re.search(r"\(1/(\d+) del minimo\)", riepilogo).group(1))
    m_sanz = re.search(r"SANZIONE \(([^)]*)\):\s*€\s*([\d.,]+)", riepilogo)
    m_int = re.search(r"INTERESSI:\s*€\s*([\d.,]+)", riepilogo)

    righe_interessi = []
    tab_int = next((t for t in tables if t.startswith("Dal:")), "")
    for riga in tab_int.splitlines()[1:]:
        celle = [c.strip() for c in riga.split("\t")]
        if len(celle) >= 6:
            righe_interessi.append(
                f"{celle[0]}-{celle[1]} {celle[3]} {celle[4]}gg {celle[5]}"
            )

    tab_f24 = next((t for t in tables if "TOTALE:" in t), "")
    m_tot = re.search(r"TOTALE:\s*([\d.,]+)", tab_f24)

    return {
        "giorni": giorni,
        "norma": f"{norma.group(1).strip()} | {norma.group(2).strip()}" if norma else "",
        "frazione": frazione,
        "formula_sanzione": m_sanz.group(1),
        "sanzione": parse_euro(m_sanz.group(2)),
        "interessi": parse_euro(m_int.group(1)),
        "righe_interessi": righe_interessi,
        "totale_f24": parse_euro(m_tot.group(1)) if m_tot else None,
    }


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _confronta(importo: float, scadenza: date, ravvedimento: date, page) -> None:
    giorni = (ravvedimento - scadenza).days
    t = _tool(importo, giorni)
    s = _site(page, importo, scadenza, ravvedimento)

    diff = []
    if s["giorni"] != giorni:
        diff.append(f"giorni: test={giorni} sito={s['giorni']}")
    if t["frazione"] != s["frazione"]:
        diff.append(
            f"riduzione: tool 1/{t['frazione']} ({t['etichetta']}) "
            f"vs sito 1/{s['frazione']} ({s['norma']})"
        )
    for voce in ("sanzione", "interessi"):
        if abs(t[voce] - s[voce]) > TOL:
            diff.append(
                f"{voce}: tool={t[voce]:.2f} sito={s[voce]:.2f} "
                f"diff={t[voce] - s[voce]:+.2f}"
            )
    totale_sito = round(importo + s["sanzione"] + s["interessi"], 2)
    if abs(t["totale"] - totale_sito) > TOL:
        diff.append(
            f"totale (imposta+sanzione+interessi): tool={t['totale']:.2f} "
            f"sito={totale_sito:.2f} diff={t['totale'] - totale_sito:+.2f}"
        )
    assert not diff, (
        f"{scadenza:%d/%m/%Y} -> {ravvedimento:%d/%m/%Y} ({giorni} gg), imposta {importo:.2f}: "
        + "; ".join(diff)
        + f" || sito: sanzione '{s['formula_sanzione']}', interessi {s['righe_interessi']}, "
        f"TOTALE F24 {s['totale_f24']} | tool: pct {t['pct']}%, "
        f"tasso {t['raw']['interessi_legali']['tasso_pct']}%"
    )


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_sprint_5_giorni(page):
    """Piano: 16/03/2026 -> 21/03/2026, 5 giorni, imposta 1.000.

    Atteso: 12,5% x 5/15 (art. 13 co. 1 D.Lgs. 471/1997 mod. D.Lgs. 87/2024)
    ridotta a 1/10 (lett. a art. 13 D.Lgs. 472/1997) = 0,4167% -> 4,17;
    interessi 1,6% x 5/365 = 0,22; totale 1.004,39.
    """
    _confronta(1000, date(2026, 3, 16), date(2026, 3, 21), page)


def test_sprint_15_giorni_ultimo_giorno(page):
    """Piano (caso al limite): 16/03/2026 -> 31/03/2026, 15 giorni.

    Atteso: 12,5% x 15/15 / 10 = 1,25% -> 12,50 (stesso importo del breve);
    interessi 0,66. Il tool lo etichetta 'breve', il sito 'sprint': la frazione
    di riduzione (1/10) e l'importo coincidono.
    """
    _confronta(1000, date(2026, 3, 16), date(2026, 3, 31), page)


def test_intermedio_60_giorni(page):
    """Piano: 16/03/2026 -> 15/05/2026, 60 giorni.

    Atteso: 1/9 di 12,5% = 1,3889% -> 13,89 (lett. a-bis); interessi 2,63;
    totale 1.016,52.
    """
    _confronta(1000, date(2026, 3, 16), date(2026, 5, 15), page)


def test_lungo_180_giorni(page):
    """Piano: 16/03/2026 -> 12/09/2026, 180 giorni.

    Atteso: 1/8 di 25% = 3,125% -> 31,25 (lett. b, entro il termine della
    dichiarazione relativa al 2026); interessi 7,89; totale 1.039,14.
    """
    _confronta(1000, date(2026, 3, 16), date(2026, 9, 12), page)


def test_800_giorni_regime_previgente(page):
    """Piano (caso al limite, tre anni di tabella): 17/06/2024 -> 26/08/2026.

    Atteso dal piano: 1/7 e non 1/6 (tool 41,67); interessi con i tassi di
    ciascun anno (2,5% 2024, 2% 2025, 1,6% 2026: circa 43,95) contro 35,07.
    Nota: la scadenza 17/06/2024 e' ANTERIORE al 01/09/2024, quindi la base e'
    il 30% previgente (art. 13 D.Lgs. 471/1997 ante D.Lgs. 87/2024), regime che
    il tool dichiara di non calcolare ma per cui restituisce comunque un valore
    sulla base del 25%. Il ravvedimento avviene entro il termine della
    dichiarazione relativa al 2025 (31/10/2026): lett. b-bis, 1/7.
    """
    _confronta(1000, date(2024, 6, 17), date(2026, 8, 26), page)


def test_dichiarazione_tardiva_30_giorni(page):
    """Piano: dichiarazione presentata con 30 giorni di ritardo, imposta 1.000.

    Atteso: sanzione fissa per la dichiarazione tardiva entro 90 giorni
    (art. 1 D.Lgs. 471/1997, lett. c art. 13 D.Lgs. 472/1997: 1/10 del minimo)
    oltre alla sanzione sui versamenti; il tool applica il 6% dell'imposta
    (60,00). Il sito non gestisce la dichiarazione tardiva.
    """
    pytest.skip(
        "non confrontabile: il calcolatore del sito gestisce solo l'omesso o "
        "insufficiente versamento ('l'applicazione gestisce il ravvedimento per "
        "omesso versamento ... ma non la regolarizzazione degli errori commessi "
        "in dichiarazione')"
    )


# ---------------------------------------------------------------------------
# Casi al limite aggiunti
# ---------------------------------------------------------------------------

def test_breve_30_giorni_ultimo_giorno_lett_a(page):
    """Limite: 16/03/2026 -> 15/04/2026, 30 giorni (ultimo giorno della lett. a).

    Atteso: 1/10 di 12,5% = 1,25% -> 12,50; interessi 1,6% x 30/365 = 1,32.
    """
    _confronta(1000, date(2026, 3, 16), date(2026, 4, 15), page)


def test_intermedio_60_giorni_imposta_100000(page):
    """Arrotondamento: 16/03/2026 -> 15/05/2026, 60 giorni, imposta 100.000.

    Atteso: 1/9 di 12,5% di 100.000 = 1.388,89 (lett. a-bis); interessi
    100.000 x 1,6% x 60/365 = 263,01. Il sito arrotonda la percentuale a 1,39%
    prima di applicarla (1.390,00): il caso misura l'effetto su un importo alto.
    """
    _confronta(100000, date(2026, 3, 16), date(2026, 5, 15), page)


def test_lungo_91_giorni_primo_giorno(page):
    """Limite 90/91: 16/03/2026 -> 15/06/2026, 91 giorni.

    Atteso: fine del dimezzamento (art. 13 co. 1 D.Lgs. 471/1997): 1/8 di 25%
    = 3,125% -> 31,25 (lett. b); interessi 1,6% x 91/365 = 3,99.
    """
    _confronta(1000, date(2026, 3, 16), date(2026, 6, 15), page)


def test_breve_30_giorni_a_cavallo_anno(page):
    """Limite tabella annuale: 16/12/2025 -> 15/01/2026, 30 giorni.

    Atteso: sanzione 1/10 di 12,5% = 12,50; interessi al tasso legale di
    ciascun anno (art. 13 co. 2 D.Lgs. 472/1997, maturazione giorno per
    giorno): 15 gg al 2% (0,82) + 15 gg all'1,6% (0,66) = 1,48. Il tool
    applica l'1,6% a tutti i 30 giorni (1,32).
    """
    _confronta(1000, date(2025, 12, 16), date(2026, 1, 15), page)


def test_lungo_ultimo_giorno_termine_dichiarazione(page):
    """Limite lett. b: 16/09/2024 -> 31/10/2025, 410 giorni.

    Atteso: violazione del 2024, regolarizzazione entro il termine della
    dichiarazione relativa al 2024 (31/10/2025): lett. b, 1/8 di 25% = 31,25.
    Il tool usa la soglia fissa di 365 giorni e applica 1/7 (35,71).
    Interessi: 2,5% per il 2024 e 2% per il 2025.
    """
    _confronta(1000, date(2024, 9, 16), date(2025, 10, 31), page)


def test_lunghissimo_731_giorni(page):
    """Limite 730/731: 16/09/2024 -> 17/09/2026, 731 giorni.

    Atteso: regolarizzazione oltre il termine della dichiarazione relativa al
    2024 e prima di quello della dichiarazione relativa al 2025 (31/10/2026):
    lett. b-bis, 1/7 di 25% = 35,71 (nel testo vigente b-bis vale comunque
    per tutto il periodo successivo, senza limite). Il tool passa a 1/6
    (41,67) oltre i 730 giorni. Interessi per anno: 7,26 + 20,00 + 11,40.
    """
    _confronta(1000, date(2024, 9, 16), date(2026, 9, 17), page)


def test_oltre_termine_seconda_dichiarazione_791_giorni(page):
    """Limite b-bis/b-ter: 16/09/2024 -> 16/11/2026, 791 giorni.

    Atteso dalla norma vigente (art. 13 co. 1 lett. b-bis D.Lgs. 472/1997 come
    modificato dal D.Lgs. 87/2024, violazione successiva al 01/09/2024): 1/7
    di 25% = 35,71, perche' la lett. b-ter (1/6) presuppone la comunicazione
    dello schema d'atto. Sia il tool sia il sito applicano 1/6 (41,67 / 41,70):
    il sito segue il testo previgente della lett. b-ter. Il confronto
    tool == sito misura le altre differenze (arrotondamento della percentuale
    e tassi per anno). Data del ravvedimento futura rispetto al 25/09/2026, ma
    entro l'anno coperto dalla tabella dei tassi (1,6% fino al 31/12/2026).
    """
    _confronta(1000, date(2024, 9, 16), date(2026, 11, 16), page)
