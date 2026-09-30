"""Benchmark fase 1: calcolo_irpef vs avvocatoandreani.it.

Pagina principale: https://www.avvocatoandreani.it/servizi/calcolo-irpef.php
Modulo ``CalcoloIrpef`` (POST): ``RedditoComplessivoIrpef`` (rigo RN1 col. 5),
``DeduzioneAbitazionePrincipale`` (RN2), ``OneriDeducibili`` (RN3),
``DetrazioniImposta`` (RN22), ``CreditiImposta`` (RN25), checkbox ``AltreAliquote``
("Simula con le nuove aliquote 2026"), pulsante ``#btn-calc``. Senza spunta la
pagina applica gli scaglioni dell'anno d'imposta 2025 (dichiarazione 2026:
23-35-43%); con la spunta quelli del 2026 (23-33-43%, L. 199/2025) e mostra
l'avviso "Imposta calcolata con le nuove aliquote in vigore dal 2026". Risultati:
``RN4 Reddito imponibile``, ``RN5 IRPEF LORDA``, ``RN26 IRPEF NETTA`` (solo se
RN22/RN25 sono valorizzati e diversi da zero) e la tabella "Sviluppo del calcolo".

Pagine di riscontro per la detrazione da lavoro (il modulo IRPEF non conosce il
tipo di reddito: prende il totale delle detrazioni come dato, rigo RN22):
- calcolo-detrazione-redditi-lavoro-dipendente.php -> RN7 col. 1 (art. 13 co. 1 e
  1.1 TUIR), 365 giorni, tempo indeterminato (valori di default);
- calcolo-detrazione-redditi-pensione.php -> RN7 col. 2 (art. 13 co. 3 e 3-bis);
- calcolo-detrazione-altri-redditi-assimilati.php -> RN7 col. 4 (art. 13 co. 5 e
  5-ter: redditi di lavoro autonomo art. 53 e assimilati).
Le tre pagine dichiarano "Periodo di imposta 2025". L'art. 13 TUIR vigente (letto
con cite_law il 2026-09-25) non e' stato toccato dalla L. 199/2025, che ha
modificato solo l'aliquota del secondo scaglione (art. 11): le detrazioni 2025 e
2026 coincidono, quindi le pagine valgono anche per i casi 2026.

Il sito calcola la netta cosi': RN26 = RN5 - RN22 - RN25. Il test passa in RN22
la detrazione calcolata dal sito stesso, quindi la netta del sito e' "imposta
lorda meno detrazione art. 13". Non comprende l'ulteriore detrazione di 1.000
euro dell'art. 1, co. 6, L. 207/2024 (dipendenti tra 20.000 e 40.000 euro) che il
sito non calcola in nessuna pagina e il tool non applica: quella componente non
e' confrontabile e resta nelle note del piano.

Convenzioni osservate sul sito:
- importi inseriti e imposte arrotondati all'unita' di euro (istruzioni REDDITI
  PF: importi in euro interi). La detrazione 1.736,19 e' mostrata come 1.736,00;
  454,50 come 455,00 (half-up). Il tool lavora al centesimo.
- coefficienti delle detrazioni troncati alla quarta cifra decimale (art. 13,
  co. 6, TUIR): 0,9090 e 0,0512. Il tool non tronca.
- con RN22 = 0 il sito non stampa RN26: in quel caso la netta del sito e', per
  la sua stessa formula, uguale a RN5.

Tolleranze: 0,01 euro sulla lorda e sull'imponibile (i redditi scelti danno
imposte in euro interi, quindi l'arrotondamento del sito e' neutro). 0,50 euro
sulla detrazione e sulla netta: il sito arrotonda la detrazione all'euro (RN7
e RN22 sono righi in euro interi), per cui un tool esatto al centesimo differisce
fino a 0,50 per sola convenzione. Il caso con i centesimi nel reddito usa 1,00
euro (motivazione nel test). Nessuna tolleranza assorbe uno scostamento di
sostanza: le differenze attese (65 euro, 50 euro, 455 euro, 109 euro) restano
fallimenti, che giudichera' la fase 2.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

PAGE = "calcolo-irpef.php"
TOL = 0.01
# Il sito arrotonda la detrazione all'unita' di euro (RN7/RN22 in euro interi).
TOL_EURO = 0.50

DETR_PAGE = {
    "dipendente": ("calcolo-detrazione-redditi-lavoro-dipendente.php", "RN7 Col.1"),
    "pensionato": ("calcolo-detrazione-redditi-pensione.php", "RN7 Col.2"),
    "autonomo": ("calcolo-detrazione-altri-redditi-assimilati.php", "RN7 Col.4"),
}


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(**kwargs) -> dict:
    import importlib

    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)

    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod.calcolo_irpef, "fn", mod.calcolo_irpef)
    r = fn(**kwargs)
    assert "errore" not in r, r
    return r


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _fmt(value: float) -> str:
    """Importo nel formato del sito: virgola per i decimali, niente migliaia."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".replace(".", ",")


def _submit(page):
    # Il banner CMP (Quantcast) puo' comparire dopo la rimozione fatta da goto():
    # lo si toglie di nuovo e si preme il pulsante via DOM, cosi' il clic non
    # finisce sull'overlay (il pulsante porta name/value nel POST come un clic).
    accept_cookies(page)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate("document.getElementById('btn-calc').click()")
    page.wait_for_timeout(2500)


def _site_detrazione(page, tipo: str, reddito_per_detrazioni: float) -> float:
    """Detrazione art. 13 TUIR dalla pagina di riscontro (365 giorni, default)."""
    path, rigo = DETR_PAGE[tipo]
    goto(page, path)
    page.fill("input[name='RedditoComplessivoDetrazione']", _fmt(reddito_per_detrazioni))
    _submit(page)
    body = page.inner_text("body")
    assert "Periodo di imposta 2025" in body, body[:1500]
    m = re.search(rf"{re.escape(rigo)}\s+[^\n€]*€\s*([\d.]+,\d{{2}})", body)
    assert m, f"rigo {rigo} non trovato: {body[:1500]}"
    return parse_euro(m.group(1))


def _site_irpef(page, reddito: float, oneri: float = 0, detrazioni: float = 0,
                aliquote_2026: bool = False) -> dict:
    goto(page, PAGE)
    page.fill("input[name='RedditoComplessivoIrpef']", _fmt(reddito))
    if oneri:
        page.fill("input[name='OneriDeducibili']", _fmt(oneri))
    if detrazioni:
        page.fill("input[name='DetrazioniImposta']", _fmt(detrazioni))
    if aliquote_2026:
        page.check("input[name='AltreAliquote']", force=True)
    _submit(page)
    body = page.inner_text("body")

    def _rigo(label):
        m = re.search(rf"{label}\s+€\s*([\d.]+,\d{{2}})", body, re.IGNORECASE)
        return parse_euro(m.group(1)) if m else None

    out = {
        "imponibile": _rigo(r"RN4\s+Reddito imponibile"),
        "lorda": _rigo(r"RN5\s+IRPEF LORDA"),
        "netta": _rigo(r"RN26\s+IRPEF NETTA"),
        "avviso_2026": "nuove aliquote in vigore dal 2026" in body,
        "aliquote": [
            int(a) for a in re.findall(
                r"€\s*[\d.]+,\d{2}\s+€\s*[\d.]+,\d{2}\s+(\d+)%\s+€\s*[\d.]+,\d{2}", body
            )
        ],
    }
    assert out["lorda"] is not None, f"IRPEF LORDA non trovata: {body[:2000]}"
    # Con RN22 = 0 il sito non stampa RN26: per la sua formula (RN5 - RN22 - RN25)
    # la netta coincide con la lorda.
    if out["netta"] is None and not detrazioni:
        out["netta"] = out["lorda"]
    assert out["avviso_2026"] == aliquote_2026, "anno degli scaglioni non selezionato"
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _report(case: str, voci: list[tuple[str, float, float, float]]):
    for label, ours, site, _tol in voci:
        print(f"BENCH|{case}|{label}|tool={ours}|sito={site}|diff={round(ours - site, 2)}")


def _confronta(case: str, voci: list[tuple[str, float, float, float]]):
    """Asserisce tutte le voci e fallisce elencando ogni scostamento."""
    _report(case, voci)
    errori = []
    for label, ours, site, tol in voci:
        try:
            assert_close(ours, site, tolerance=tol, label=f"{case}.{label}")
        except AssertionError as exc:
            errori.append(str(exc))
    assert not errori, "\n".join(errori)


def _caso_completo(page, case: str, *, reddito: float, tipo: str, anno: int,
                   deduzioni: float = 0):
    """Lorda, imponibile, detrazione art. 13 e netta: tool contro sito."""
    kwargs = dict(reddito_complessivo=reddito, tipo_reddito=tipo, deduzioni=deduzioni,
                  detrazioni_extra=0, anno_fiscale=anno)
    r = _tool(**kwargs)
    anno_effettivo = r["anno_fiscale"]
    assert anno_effettivo in (2025, 2026), anno_effettivo

    # La detrazione dell'art. 13 si calcola sul reddito complessivo (co. 6-bis:
    # al netto della sola abitazione principale), non sull'imponibile.
    detr_sito = _site_detrazione(page, tipo, reddito)
    page.wait_for_timeout(1500)
    sito = _site_irpef(page, reddito, oneri=deduzioni, detrazioni=detr_sito,
                       aliquote_2026=(anno_effettivo == 2026))

    aliquote_tool = [s["aliquota_pct"] for s in r["dettaglio_scaglioni"]]
    print(f"BENCH|{case}|aliquote|tool={aliquote_tool}|sito={sito['aliquote']}")
    assert aliquote_tool == sito["aliquote"], (aliquote_tool, sito["aliquote"])

    _confronta(case, [
        ("imponibile", r["reddito_imponibile"], sito["imponibile"], TOL),
        ("lorda", r["imposta_lorda"], sito["lorda"], TOL),
        ("detrazione_lavoro", r["detrazioni"]["lavoro"], detr_sito, TOL_EURO),
        ("netta", r["imposta_netta"], sito["netta"], TOL_EURO),
    ])


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_dipendente_30000_anno_2026(page):
    """Piano 1. Atteso: lorda 7.100,00 (28.000 x 23% + 2.000 x 33%, art. 11 TUIR
    come modificato dalla L. 199/2025); detrazione art. 13 co. 1 lett. c) con
    coefficiente troncato 0,9090 = 1.736,19 + 65 (co. 1.1) = 1.801,19; netta
    (senza l'ulteriore detrazione L. 207/2024, non calcolata dal sito) 5.298,81.
    Il tool restituisce detrazione 1.736,36 e netta 5.363,64."""
    _caso_completo(page, "dip30k_2026", reddito=30000, tipo="dipendente", anno=2026)


def test_autonomo_50000_anno_2025_confine_secondo_scaglione(page):
    """Piano 2 (caso al limite: confine superiore del secondo scaglione).
    Atteso: lorda 14.140,00 (6.440 + 22.000 x 35%, art. 11 TUIR nel testo 2025);
    detrazione art. 13 co. 5 lett. b-bis) nulla a 50.000 euro; netta = lorda."""
    _caso_completo(page, "aut50k_2025", reddito=50000, tipo="autonomo", anno=2025)


def test_autonomo_50000_anno_2026_confine_secondo_scaglione(page):
    """Piano 2, variante 2026 (caso al limite, opzione "nuove aliquote 2026").
    Atteso: lorda 13.700,00 (6.440 + 22.000 x 33%, L. 199/2025); netta = lorda."""
    _caso_completo(page, "aut50k_2026", reddito=50000, tipo="autonomo", anno=2026)


def test_autonomo_30000_anno_2026_detrazione_comma_5(page):
    """Piano 3. Atteso: lorda 7.100,00; detrazione art. 13 co. 5 lett. b-bis)
    TUIR 500 x 0,9090 = 454,50 (sito: 455 all'euro); netta 6.645,50. Il tool non
    riconosce alcuna detrazione per 'autonomo' (netta 7.100,00)."""
    _caso_completo(page, "aut30k_2026", reddito=30000, tipo="autonomo", anno=2026)


def test_dipendente_30000_oneri_deducibili_2000_anno_2026(page):
    """Piano 4. Atteso: imponibile 28.000 (RN3 = 2.000), lorda 6.440,00;
    detrazione sul reddito complessivo di 30.000 (art. 13 co. 1 e 6-bis TUIR):
    1.801,19; netta 4.638,81 (4.638,81 - 1.000 con l'ulteriore detrazione L.
    207/2024 = 3.638,81, come nel piano). Il tool calcola la detrazione
    sull'imponibile di 28.000 (1.910,00) e restituisce 4.530,00."""
    _caso_completo(page, "dip30k_ded2k_2026", reddito=30000, tipo="dipendente",
                   anno=2026, deduzioni=2000)


def test_pensionato_27000_anno_2026(page):
    """Piano 5. Atteso: lorda 6.210,00; detrazione art. 13 co. 3 lett. b)
    700 + 1.255 x 0,0512 = 764,26, piu' 50 euro (co. 3-bis, tra 25.000 e 29.000)
    = 814,26; netta 5.395,74. Il tool: detrazione 764,36, netta 5.445,64."""
    _caso_completo(page, "pens27k_2026", reddito=27000, tipo="pensionato", anno=2026)


def test_anno_2023_assente_dalla_tabella():
    """Piano 6 (caso al limite: anno fuori tabella). Atteso: lorda 7.400,00
    (15.000 x 23% + 13.000 x 25% + 2.000 x 35%, art. 11 TUIR nel testo vigente
    per il 2023). Il sito offre solo gli scaglioni 2025 e la simulazione 2026:
    non confrontabile. Si registra comunque cosa fa il tool."""
    import src.server  # noqa: F401
    from src.tools import dichiarazione_redditi as mod

    fn = getattr(mod.calcolo_irpef, "fn", mod.calcolo_irpef)
    r = fn(reddito_complessivo=30000, tipo_reddito="autonomo", anno_fiscale=2023)
    # The tool used to fall back silently on the 2026 brackets; it now refuses years
    # before 2024 (art. 11 TUIR had four brackets 23-25-35-43%).
    assert "errore" in r, r
    pytest.skip(
        "sito: solo anno d'imposta 2025 e simulazione 2026, niente 2023. "
        "Il tool rifiuta gli anni anteriori al 2024 (atteso dal piano 7.400,00 a quattro scaglioni)"
    )


# ---------------------------------------------------------------------------
# Casi al limite aggiunti
# ---------------------------------------------------------------------------

def test_dipendente_28000_anno_2025_confine_primo_scaglione(page):
    """Caso al limite: 28.000 euro, confine del primo scaglione (art. 11 TUIR) e
    punto di raccordo tra le lettere b) e c) dell'art. 13 co. 1. Atteso: lorda
    6.440,00; detrazione 1.910 + 65 (co. 1.1, reddito tra 25.000 e 35.000) =
    1.975,00; netta 4.465,00. Il tool omette i 65 euro (detrazione 1.910)."""
    _caso_completo(page, "dip28k_2025", reddito=28000, tipo="dipendente", anno=2025)


def test_dipendente_80000_anno_default_terzo_scaglione(page, monkeypatch):
    """Caso al limite: anno_fiscale=0 (default "anno corrente") con la data
    pinnata al 2026-09-25, quindi scaglioni 2026; reddito nel terzo scaglione.
    Atteso: lorda 26.600,00 (6.440 + 22.000 x 33% + 30.000 x 43%); detrazione
    art. 13 co. 1 nulla oltre 50.000 euro; netta = lorda."""
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-25")
    _caso_completo(page, "dip80k_default", reddito=80000, tipo="dipendente", anno=0)


def test_autonomo_80000_anno_2024_scaglioni_uguali_al_2025(page):
    """Caso al limite: anno diverso della tabella. Il sito non offre il 2024, ma
    gli scaglioni 2024 (D.Lgs. 216/2023, art. 1 co. 2) e 2025 (L. 207/2024, che li
    ha resi strutturali) sono identici: 23-35-43% con soglie 28.000/50.000.
    Atteso: lorda 27.040,00 (6.440 + 7.700 + 30.000 x 43%). Si confronta solo la
    lorda con la pagina senza spunta (2025)."""
    r = _tool(reddito_complessivo=80000, tipo_reddito="autonomo", anno_fiscale=2024)
    sito = _site_irpef(page, 80000)
    aliquote_tool = [s["aliquota_pct"] for s in r["dettaglio_scaglioni"]]
    print(f"BENCH|aut80k_2024|aliquote|tool={aliquote_tool}|sito={sito['aliquote']}")
    assert aliquote_tool == sito["aliquote"], (aliquote_tool, sito["aliquote"])
    _confronta("aut80k_2024", [
        ("imponibile", r["reddito_imponibile"], sito["imponibile"], TOL),
        ("lorda", r["imposta_lorda"], sito["lorda"], TOL),
    ])


def test_reddito_con_centesimi_arrotondamento_all_euro(page):
    """Caso al limite (convenzione di arrotondamento). Reddito 35.123,45, anno
    2025. Tool: 6.440 + 7.123,45 x 35% = 8.933,21. Il sito arrotonda all'euro sia
    il reddito inserito (35.123) sia l'imposta (8.933,05 -> 8.933,00), come
    chiedono le istruzioni del modello REDDITI (importi in euro interi).
    Tolleranza 1,00 euro: l'arrotondamento del reddito sposta l'imposta di al
    massimo 0,50 x 43% = 0,215 e quello dell'imposta di 0,50; oltre questo sarebbe
    un errore di calcolo, non di convenzione."""
    r = _tool(reddito_complessivo=35123.45, tipo_reddito="autonomo", anno_fiscale=2025)
    sito = _site_irpef(page, 35123.45)
    _confronta("aut35123_45_2025", [
        ("imponibile", r["reddito_imponibile"], sito["imponibile"], 1.00),
        ("lorda", r["imposta_lorda"], sito["lorda"], 1.00),
    ])
