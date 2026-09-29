"""Benchmark fase 1: rateizzazione_imposte vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-rateizzazione-imposte-irpef.php
Modulo ``RateazioneImposte`` (POST, ricarica su ``#Res``): campo ``Imposta``
(importo da rateizzare), select ``IdPiano`` (``1-0`` = prima rata 30 giugno 2026
senza maggiorazione, ``1-1`` = prima rata 30 luglio 2026 con maggiorazione dello
0,40%), select ``NumeroRate`` (ricostruita via JavaScript: 1..7 per ``1-0``,
1..6 per ``1-1``, con la nota ``( max N rate )``), pulsante ``#btn-calc``.
Il sito calcola solo i versamenti 2026 (non c'e' scelta dell'anno).

Campo nascosto ``PartitaIva`` (valore fisso ``1`` nell'interfaccia): il sito
mostra quindi il piano dei TITOLARI di partita IVA (rate successive il 16 di
ogni mese, 20 agosto per la proroga di Ferragosto; interessi 0,18%, 0,51%,
0,84%...). Il server gestisce anche ``PartitaIva=0`` (non titolari: rate a fine
mese, interessi 0,33% al mese), che l'interfaccia non offre piu': i casi marcati
"non titolare" impostano il campo nascosto prima dell'invio. Sono l'unico modo
di confrontare l'atteso del piano (redatto per i non titolari), ma sono
un'opzione nascosta del sito e vanno letti come tali.

Risultato: tabella riepilogo (``Imposta da rateizzare``, ``Maggiorazione
( 0,40% )``, ``Imposta totale dovuta``, ``Numero rate``, ``Importo della singola
rata``) e tabella ``DETTAGLIO RATE e INTERESSI`` con una riga per rata
(n., scadenza in lettere, giorno della settimana, % interessi, capitale,
interessi euro, marcatore ``(*)`` per gli interessi inferiori a 1,03 euro "da non
versare", esclusi dal totale), poi ``TOTALE VERSAMENTI`` e ``Capitale +
Interessi``. Il resto dell'arrotondamento del capitale va sull'ULTIMA rata.

Norma: art. 20 D.Lgs. 241/1997 (vigente, letto su Normattiva): rate mensili di
uguale importo, interessi dal mese di scadenza, pagamento "completato entro il
16 dicembre"; co. 4: rate "entro il giorno 16 di ciascun mese" (titolari di
partita IVA); tasso 4% annuo (DM 21/05/2009), calcolato dall'AdE ad anno
commerciale sulla singola rata (0,33% al mese). Maggiorazione dello 0,40% per il
versamento nei 30 giorni successivi (art. 17, co. 2, DPR 435/2001).

Il tool non distingue titolari e non titolari, non applica la maggiorazione,
sposta ogni rata (anche la prima) al giorno 28 del mese e calcola gli interessi
sul debito residuo per il numero di mesi. I test restano tool == sito con la
tolleranza del brief (0,01 euro; date esatte): gli scostamenti li giudica la
fase 2. Il tool non dipende dalla data corrente (nessun LEGAL_TODAY necessario).
"""

import re
from datetime import date

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.comparison.conftest import accept_cookies, goto, parse_euro

PAGE = "calcolo-rateizzazione-imposte-irpef.php"
TOL = 0.01
GIUGNO = "1-0"   # 30 giugno 2026, senza maggiorazione
LUGLIO = "1-1"   # 30 luglio 2026, con maggiorazione 0,40%

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11,
    "dicembre": 12,
}


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool_raw(**kwargs) -> dict:
    import importlib

    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)

    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod.rateizzazione_imposte, "fn", mod.rateizzazione_imposte)
    return fn(**kwargs)


def _tool(**kwargs) -> dict:
    r = _tool_raw(**kwargs)
    assert "errore" not in r, f"errore_tool: {r}"
    rate = [
        {
            "n": x["rata"],
            "data": x["data_scadenza"],
            "capitale": float(x["importo_capitale"]),
            "interessi": float(x["interessi"]),
        }
        for x in r["piano_rate"]
    ]
    return {
        "rate": rate,
        "maggiorazione": 0.0,  # il tool non la calcola
        "imposta_totale": float(r["importo_totale"]),
        "totale_capitale": round(sum(x["capitale"] for x in rate), 2),
        "totale_interessi": float(r["totale_interessi"]),
        "totale_versato": float(r["totale_versato"]),
        "raw": r,
    }


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

_SITE_CACHE: dict = {}


def _fmt_it(v: float) -> str:
    """3000 -> '3000'; 1000.5 -> '1000,50' (formato del campo del sito)."""
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.2f}".replace(".", ",")


def _data_it(s: str) -> str:
    """'30 giugno 2026' -> '2026-06-30'."""
    m = re.match(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", s.strip().lower())
    assert m, f"data non riconosciuta: {s!r}"
    return date(int(m.group(3)), _MESI[m.group(2)], int(m.group(1))).isoformat()


def _apri(page, piano: str) -> tuple[int, str]:
    """Apre la pagina, sceglie il piano e legge il numero massimo di rate offerto."""
    goto(page, PAGE, wait_ms=1500)
    page.select_option("#IdPiano", piano)
    page.wait_for_timeout(300)
    opts = page.eval_on_selector_all("#NumeroRate option", "els => els.map(e => e.value)")
    max_rate = max(int(v) for v in opts if v.strip())
    nota = page.inner_text("#NotaMaxRate").strip()
    return max_rate, nota


def _invia(page) -> None:
    """Invia il modulo con un click reale su ``#btn-calc`` (POST, ricarica su ``#Res``).

    Il banner del consenso (``#accept-btn`` / Quantcast) blocca l'invio finche'
    non e' chiuso: lo si chiude subito prima del click e, se la pagina non
    ricarica, si riprova.
    """
    for _ in range(3):
        accept_cookies(page)
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                page.click("#btn-calc", force=True)
            return
        except PlaywrightTimeoutError:
            continue
    pytest.fail("errore_sito: il modulo non e' stato inviato (banner sopra il pulsante?)")


def _site(page, imposta: float, piano: str, n: int, partita_iva: str = "1") -> dict:
    """Piano di rateazione del sito. ``partita_iva='0'`` usa il campo nascosto."""
    key = (imposta, piano, n, partita_iva)
    if key in _SITE_CACHE:
        return _SITE_CACHE[key]

    max_rate, nota = _apri(page, piano)
    page.fill("#Imposta", _fmt_it(imposta))
    page.select_option("#NumeroRate", str(n))
    if partita_iva != "1":
        # Campo nascosto, non offerto dall'interfaccia (vedi docstring del modulo).
        page.evaluate(f'document.getElementById("PartitaIva").value = "{partita_iva}"')
    _invia(page)
    page.wait_for_timeout(2000)

    out = {"max_rate_ui": max_rate, "nota": nota, "errore": None, "rate": [],
           "non_dovuti": [], "maggiorazione": 0.0, "imposta_totale": None,
           "totale_capitale": None, "totale_interessi": None, "totale_versato": None}

    dettaglio = None
    riepilogo = None
    for t in page.query_selector_all("table"):
        txt = t.inner_text()
        if "DETTAGLIO RATE" in txt:
            dettaglio = t
        elif "Imposta da rateizzare" in txt:
            riepilogo = t

    if dettaglio is None:
        form = page.inner_text("#RateazioneImposte")
        msg = [ln.strip() for ln in form.splitlines()
               if ln.strip() and not re.fullmatch(r"\d+", ln.strip())
               and "Giugno 2026" not in ln and "Luglio 2026" not in ln
               and "max" not in ln and not ln.strip().endswith(":")
               and "CALCOLO RATEAZIONE" not in ln and "Imposta" not in ln]
        out["errore"] = " ".join(msg) or "nessun risultato"
        _SITE_CACHE[key] = out
        return out

    # Riepilogo: imposta, maggiorazione, imposta totale dovuta.
    rt = riepilogo.inner_text() if riepilogo else ""
    m = re.search(r"Imposta da rateizzare\s*€\s*([\d.,]+)", rt)
    base = parse_euro(m.group(1)) if m else None
    m = re.search(r"Maggiorazione[^€]*€\s*([\d.,]+)", rt)
    out["maggiorazione"] = parse_euro(m.group(1)) if m else 0.0
    m = re.search(r"Imposta totale dovuta\s*€\s*([\d.,]+)", rt)
    out["imposta_totale"] = parse_euro(m.group(1)) if m else base

    # Righe del dettaglio: 7 celle, la prima e' il numero di rata.
    for tr in dettaglio.query_selector_all("tr"):
        cells = [c.inner_text().strip() for c in tr.query_selector_all("td")]
        if len(cells) == 7 and re.fullmatch(r"\d+", cells[0]):
            out["rate"].append({
                "n": int(cells[0]),
                "data": _data_it(cells[1]),
                "pct": cells[3],
                "capitale": parse_euro(cells[4]),
                "interessi": parse_euro(cells[5]),
            })
            if "(*)" in cells[6]:
                out["non_dovuti"].append(int(cells[0]))

    dt = dettaglio.inner_text()
    m = re.search(r"TOTALE VERSAMENTI:\s*€\s*([\d.,]+)\s*€\s*([\d.,]+)", dt)
    assert m, f"errore_sito: totali non trovati\n{dt}"
    out["totale_capitale"] = parse_euro(m.group(1))
    out["totale_interessi"] = parse_euro(m.group(2))
    m = re.search(r"Capitale \+ Interessi:\s*€\s*([\d.,]+)", dt)
    out["totale_versato"] = parse_euro(m.group(1)) if m else None
    assert out["rate"], f"errore_sito: nessuna rata letta\n{dt}"

    _SITE_CACHE[key] = out
    page.wait_for_timeout(1000)
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _confronta(t: dict, s: dict) -> list[str]:
    """Elenca TUTTE le differenze tool/sito (rata per rata e totali)."""
    diffs = []
    if len(t["rate"]) != len(s["rate"]):
        diffs.append(f"numero rate: tool={len(t['rate'])} sito={len(s['rate'])}")
    for rt, rs in zip(t["rate"], s["rate"]):
        n = rt["n"]
        if rt["data"] != rs["data"]:
            diffs.append(f"rata {n} scadenza: tool={rt['data']} sito={rs['data']}")
        if abs(rt["capitale"] - rs["capitale"]) > TOL:
            diffs.append(f"rata {n} capitale: tool={rt['capitale']:.2f} sito={rs['capitale']:.2f}")
        if abs(rt["interessi"] - rs["interessi"]) > TOL:
            nd = " (sito: '(*)' da non versare, < 1,03)" if n in s["non_dovuti"] else ""
            diffs.append(f"rata {n} interessi: tool={rt['interessi']:.2f} "
                         f"sito={rs['interessi']:.2f} ({rs['pct']}){nd}")
    for k in ("maggiorazione", "imposta_totale", "totale_capitale", "totale_interessi",
              "totale_versato"):
        if s[k] is None:
            continue
        if abs(t[k] - s[k]) > TOL:
            diffs.append(f"{k}: tool={t[k]:.2f} sito={s[k]:.2f} diff={t[k] - s[k]:+.2f}")
    return diffs


def _assert_uguali(t: dict, s: dict, caso: str) -> None:
    diffs = _confronta(t, s)
    assert not diffs, f"{caso}: {len(diffs)} scostamenti tool/sito\n  " + "\n  ".join(diffs)


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_tre_rate_giugno_titolare_piva(page):
    """Piano caso 1 sul sito come offerto (titolare di partita IVA).

    Atteso del piano (non titolare): rate da 1.000 al 30/06, 31/07, 31/08;
    interessi 0; 3,30; 6,60 = 9,90; il tool da' 13,34 e scadenze al 28.
    Il sito (titolare): 30/06, 16/07, 20/08 (Ferragosto); 0%, 0,18%, 0,51%
    -> 0; 1,80; 5,10 = 6,90. Norma: art. 20, co. 1 e 4, D.Lgs. 241/1997.
    """
    t = _tool(importo_totale=3000, n_rate=3, data_prima_rata="2026-06-30",
              tasso_interesse_annuo=4.0)
    s = _site(page, 3000, GIUGNO, 3)
    _assert_uguali(t, s, "3.000 in 3 rate da giugno (titolare P.IVA)")


def test_tre_rate_giugno_non_titolare_piva(page):
    """Piano caso 1 sul piano dei NON titolari (campo nascosto PartitaIva=0).

    Atteso del piano: 30/06, 31/07, 31/08; interessi 0; 3,30 (0,33%); 6,60
    (0,66%) = 9,90 (art. 20 D.Lgs. 241/1997, tabella AdE). Il tool: 13,34 e
    scadenze 28/06, 28/07, 28/08.
    """
    t = _tool(importo_totale=3000, n_rate=3, data_prima_rata="2026-06-30",
              tasso_interesse_annuo=4.0)
    s = _site(page, 3000, GIUGNO, 3, partita_iva="0")
    _assert_uguali(t, s, "3.000 in 3 rate da giugno (non titolare, campo nascosto)")


def test_sette_rate_massimo_titolare_piva(page):
    """Piano caso 2 (limite: numero massimo di rate), titolare di partita IVA.

    Atteso del piano (non titolare): 0; 3,30; 6,60; 9,90; 13,20; 16,50; 19,80
    = 69,30, ultima rata a dicembre; il tool da' 186,66. Sul sito (titolare):
    ultima rata 16/12/2026, interessi 0,18%..1,83% -> totale 60,30. Art. 20,
    co. 1, D.Lgs. 241/1997: pagamento completato entro il 16 dicembre (il tool
    fissa la settima rata al 28/12/2026).
    """
    t = _tool(importo_totale=7000, n_rate=7, data_prima_rata="2026-06-30")
    s = _site(page, 7000, GIUGNO, 7)
    _assert_uguali(t, s, "7.000 in 7 rate da giugno (titolare P.IVA)")


def test_sette_rate_non_titolare_piva(page):
    """Piano caso 2 sul piano dei non titolari (campo nascosto PartitaIva=0).

    Atteso del piano: interessi 0..19,80 = 69,30. Il sito, per i non titolari,
    rifiuta la settima rata ("Il piano di rateazione prevede al massimo 6
    rate": tabella nascosta ``nrnoiva`` = 6, limite anteriore al D.Lgs. 1/2024
    oppure lettura del termine del 16 dicembre dell'art. 20, co. 1). Il tool
    accetta 7 rate e da' 186,66.
    """
    t = _tool(importo_totale=7000, n_rate=7, data_prima_rata="2026-06-30")
    s = _site(page, 7000, GIUGNO, 7, partita_iva="0")
    if s["errore"]:
        pytest.skip(
            f"sito_non_calcola: il sito (non titolare, campo nascosto) risponde "
            f"{s['errore']!r}; tool: 7 rate, totale interessi {t['totale_interessi']:.2f}, "
            f"ultima rata {t['rate'][-1]['data']}"
        )
    _assert_uguali(t, s, "7.000 in 7 rate da giugno (non titolare, campo nascosto)")


def test_otto_rate_oltre_il_massimo(page):
    """Piano caso 3 (limite): 8 rate -> errore del tool.

    Il sito, per la prima rata al 30 giugno, offre al massimo 7 rate
    ("( max 7 rate )"): 30/06 + sei rate mensili fino al 16/12 (art. 20, co. 1,
    D.Lgs. 241/1997, come modificato dal D.Lgs. 1/2024). Il tool deve
    accettare 7 e rifiutare 8.
    """
    max_sito, nota = _apri(page, GIUGNO)
    r8 = _tool_raw(importo_totale=7000, n_rate=8, data_prima_rata="2026-06-30")
    r7 = _tool_raw(importo_totale=7000, n_rate=7, data_prima_rata="2026-06-30")
    max_tool = 7 if ("errore" in r8 and "errore" not in r7) else None
    assert max_tool == max_sito, (
        f"massimo rate da giugno: tool={max_tool} (8 -> {r8.get('errore')!r}, "
        f"7 -> {'errore' if 'errore' in r7 else 'ok'}) sito={max_sito} ({nota})"
    )


def test_luglio_con_maggiorazione_sei_rate(page):
    """Piano caso 4: prima rata al 30 luglio (con maggiorazione), 6 rate.

    Atteso del piano: maggiorazione 0,40% (art. 17, co. 2, DPR 435/2001) e
    interessi dello 0,33% al mese (non titolari); il tool non applica la
    maggiorazione e sposta le date al 28. Sul sito (titolare): imposta 6.000 +
    24,00 = 6.024, rate da 1.004 al 30/07, 20/08, 16/09, 16/10, 16/11, 16/12;
    interessi 0; 0,18%; 0,51%; 0,84%; 1,17%; 1,50% = 42,17.
    """
    t = _tool(importo_totale=6000, n_rate=6, data_prima_rata="2026-07-30")
    s = _site(page, 6000, LUGLIO, 6)
    _assert_uguali(t, s, "6.000 in 6 rate da luglio con maggiorazione (titolare P.IVA)")


# ---------------------------------------------------------------------------
# Casi al limite aggiunti
# ---------------------------------------------------------------------------

def test_luglio_sette_rate_oltre_dicembre(page):
    """Limite: 7 rate con prima rata al 30 luglio.

    Il sito offre al massimo 6 rate per il piano di luglio ("( max 6 rate )":
    30/07 + cinque rate fino al 16/12). Art. 20, co. 1, D.Lgs. 241/1997: il
    pagamento va completato entro il 16 dicembre. Il tool accetta 7 rate e
    colloca l'ultima al 28/01/2027. Atteso: il tool rifiuta come il sito.
    """
    max_sito, nota = _apri(page, LUGLIO)
    r7 = _tool_raw(importo_totale=6000, n_rate=7, data_prima_rata="2026-07-30")
    ultima = r7["piano_rate"][-1]["data_scadenza"] if "piano_rate" in r7 else None
    tool_accetta = "errore" not in r7
    sito_accetta = 7 <= max_sito
    assert tool_accetta == sito_accetta, (
        f"7 rate da luglio: tool {'accetta (ultima rata ' + str(ultima) + ')' if tool_accetta else 'rifiuta'}, "
        f"sito {'accetta' if sito_accetta else 'rifiuta'} (max {max_sito}, {nota})"
    )


def test_arrotondamento_rata_non_divisibile(page):
    """Limite: importo non divisibile (1.000 in 3 rate), titolare di partita IVA.

    Art. 20 D.Lgs. 241/1997: rate di uguale importo; il resto dell'arrotondamento
    va su una rata. Sito: 333,33 + 333,33 + 333,34 (resto sull'ultima), interessi
    0; 0,60 (*); 1,70; il (*) segna interessi sotto 1,03 euro "da non versare",
    esclusi dal totale (1,70). Il tool: 333,33 x 3 = 999,99 (manca un centesimo).
    Il centesimo mancante (rata 3 e totale capitale) sta dentro la tolleranza
    di 0,01 del brief e non compare tra gli scostamenti: resta segnalato qui e
    nel resoconto; falliscono comunque scadenze e interessi.
    """
    t = _tool(importo_totale=1000, n_rate=3, data_prima_rata="2026-06-30")
    s = _site(page, 1000, GIUGNO, 3)
    _assert_uguali(t, s, "1.000 in 3 rate da giugno (titolare P.IVA)")


def test_due_rate_minimo(page):
    """Limite: numero minimo di rate del tool (2), titolare di partita IVA.

    Sito: 30/06 e 16/07; interessi 0 e 0,18% -> 2,70 su 1.500. Il tool:
    28/06 e 28/07; 5,00 (un mese di interessi sul residuo di 1.500).
    Norma: art. 20, co. 1 e 4, D.Lgs. 241/1997.
    """
    t = _tool(importo_totale=3000, n_rate=2, data_prima_rata="2026-06-30")
    s = _site(page, 3000, GIUGNO, 2)
    _assert_uguali(t, s, "3.000 in 2 rate da giugno (titolare P.IVA)")


def test_una_rata_opzione_del_sito(page):
    """Opzione enumerata del sito: "1" rata (versamento unico).

    Il sito accetta 1 rata e restituisce il versamento unico senza interessi; il
    tool rifiuta n_rate < 2 per costruzione (una sola rata non e' una
    rateazione ai sensi dell'art. 20 D.Lgs. 241/1997). Non confrontabile.
    """
    r = _tool_raw(importo_totale=3000, n_rate=1, data_prima_rata="2026-06-30")
    s = _site(page, 3000, GIUGNO, 1)
    sito = (f"{len(s['rate'])} rata, capitale {s['totale_capitale']}, interessi "
            f"{s['totale_interessi']}" if not s["errore"] else s["errore"])
    pytest.skip(f"non_confrontabile: sito -> {sito}; tool -> {r.get('errore', r)!r}")
