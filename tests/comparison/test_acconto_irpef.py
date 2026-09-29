"""Benchmark fase 1: acconto_irpef vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-acconto-irpef.php
Modulo "Irpef" (POST): campo ``IrpefNetta`` (rigo RN34 del modello REDDITI 2026,
anno d'imposta 2025), campo ``PrimaRata`` (prima rata gia' versata, senza
maggiorazione), pulsante ``#button1``. Il risultato (``#R-Output``) e' una tabella
"Codice tributo acconto | Importo | Scadenza" con le righe ``4033 Prima rata`` e
``4034 Seconda rata`` (piu' TOTALE e la prima rata maggiorata dello 0,4%) oppure
``4034 Unico versamento``; sotto soglia il testo "L'acconto Irpef non e' dovuto".

Norma: art. 17, co. 3, D.P.R. 435/2001 -- acconto in due rate "salvo che il
versamento da effettuare alla scadenza della prima rata non superi euro 103";
40% alla scadenza del saldo (30 giugno; co. 2: entro i 30 giorni successivi con
la maggiorazione dello 0,40%), residuo nel mese di novembre. Misura del 100%:
art. 11, co. 18, D.L. 76/2013 ("A decorrere dal periodo d'imposta in corso al
31 dicembre 2013"). Esonero se l'imposta dell'anno precedente non supera 51,65
euro (100.000 lire): regola applicata da tool e sito; la sua base va ricontrollata
in fase 2 (l'art. 4 D.L. 69/1989 vigente non la contiene: co. 1 abrogato dal
D.P.R. 435/2001, co. 2 riguarda le sanzioni sugli acconti insufficienti; l'art. 1
L. 97/1977 risulta abrogato dal D.Lgs. 33/2025, TU versamenti e riscossione, che
si applica dal 1 gennaio 2027 e all'art. 72 ripete 100%, 51,65 per i coniugi e
50%+50% per i soggetti ISA). Confine tra unica soluzione e due rate: a 257,52 euro
il 40% e' gia' 103,01 (> 103), quindi due rate; il tool usa invece ``<= 257.52``
-> unica soluzione (testi letti con cite_law il 25/9/2026).

Convenzione osservata sul sito: l'importo inserito viene arrotondato all'unita'
di euro con half-up (51,49 -> 51 non dovuto; 51,50 e 51,65 -> 52; 257,49 -> 257
unica; 257,50 e 257,52 -> 258 due rate), perche' il rigo RN34 e' espresso in euro
interi (istruzioni REDDITI PF: importi arrotondati all'unita' di euro). Il tool
applica le soglie all'importo esatto passato. Sugli importi interi (gli unici che
possono comparire nel rigo) i due coincidono; sui quattro casi del piano con i
centesimi divergono. I test restano tool == sito: lo scostamento lo giudica la
fase 2.

Tolleranza: 0,01 euro sugli importi (brief di benchmark). Scadenze confrontate su
giorno e mese: il tool non indica l'anno, il sito indica il 2026 (30 giugno 2026
martedi', 30 novembre 2026 lunedi': nessuna proroga per sabato o festivo).
Il tool non dipende dalla data corrente (nessun LEGAL_TODAY necessario).
"""

import re

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

PAGE = "calcolo-acconto-irpef.php"
TOL = 0.01


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(imposta: float, metodo: str = "storico") -> dict:
    import importlib

    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)

    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod.acconto_irpef, "fn", mod.acconto_irpef)
    r = fn(imposta_anno_precedente=imposta, metodo=metodo)
    assert "errore" not in r, r
    out = {"dovuto": r["acconto_dovuto"], "unica": None, "prima": None, "seconda": None,
           "totale": None, "scad_unica": None, "scad_prima": None, "scad_seconda": None,
           "raw": r}
    if not r["acconto_dovuto"]:
        return out
    out["totale"] = float(r["acconto_totale"])
    if "unica_soluzione" in r:
        out["unica"] = float(r["unica_soluzione"]["importo"])
        out["scad_unica"] = r["unica_soluzione"]["scadenza"]
    else:
        out["prima"] = float(r["primo_acconto"]["importo"])
        out["seconda"] = float(r["secondo_acconto"]["importo"])
        out["scad_prima"] = r["primo_acconto"]["scadenza"]
        out["scad_seconda"] = r["secondo_acconto"]["scadenza"]
    return out


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

_DATE = r"(\d{1,2}\s+[a-z]+\s+\d{4})"


def _fmt_it(v: float) -> str:
    """1000 -> '1000'; 51.65 -> '51,65' (formato del campo del sito)."""
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.2f}".replace(".", ",")


def _invia(page) -> None:
    """Invia il modulo con un click reale su ``#button1`` (POST, ricarica su ``#Res``).

    Il banner Quantcast (qc-cmp2) compare dopo il domcontentloaded e si disegna
    sopra il pulsante: un click, anche forzato, finisce sul banner e il modulo
    non parte (il click DOM via JavaScript non invia il modulo). Si rimuove il
    banner subito prima del click e, se la pagina non ricarica, si riprova.
    """
    for _ in range(3):
        accept_cookies(page)
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                page.click("#button1", force=True)
            return
        except PlaywrightTimeoutError:
            continue
    pytest.fail("errore_sito: il modulo non e' stato inviato (banner sopra il pulsante?)")


def _site(page, imposta: float, prima_rata: str = "") -> dict:
    goto(page, PAGE, wait_ms=1500)
    page.fill("#IrpefNetta", _fmt_it(imposta))
    page.fill("#PrimaRata", prima_rata)
    _invia(page)
    page.wait_for_timeout(2000)

    res = page.inner_text("#R-Output").strip()
    eco = page.input_value("#IrpefNetta")
    assert res, f"il sito non ha restituito un risultato (campo IrpefNetta={eco!r})"

    out = {"dovuto": None, "unica": None, "prima": None, "seconda": None, "totale": None,
           "scad_unica": None, "scad_prima": None, "scad_seconda": None,
           "codici": {}, "maggiorata": None, "text": res, "eco": eco}
    if "non è dovuto" in res:
        out["dovuto"] = False
        return out

    for key, label in (("unica", "Unico versamento"), ("prima", "Prima rata"),
                       ("seconda", "Seconda rata")):
        m = re.search(rf"(\d{{4}})\s+{label}\s*:\s*€\s*([\d.,]+)\s+{_DATE}", res)
        if m:
            out["codici"][key] = m.group(1)
            out[key] = parse_euro(m.group(2))
            out[f"scad_{key}"] = m.group(3)
    m = re.search(r"TOTALE\s*:\s*€\s*([\d.,]+)", res)
    if m:
        out["totale"] = parse_euro(m.group(1))
    m = re.search(r"maggiorazione è pari a\s*€\s*([\d.,]+)", res)
    if m:
        out["maggiorata"] = parse_euro(m.group(1))
    assert out["unica"] is not None or out["prima"] is not None, (
        f"risultato del sito non riconosciuto:\n{res}")
    if out["totale"] is None:
        out["totale"] = out["unica"]
    out["dovuto"] = True
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _giorno_mese(s: str) -> str:
    """'30 giugno (o 30 luglio ...)' / '30 giugno 2026' -> '30 giugno'."""
    return " ".join(s.split("(")[0].split()[:2])


def _confronta(page, imposta: float, label: str, metodo: str = "storico") -> tuple[dict, dict]:
    t = _tool(imposta, metodo)
    s = _site(page, imposta)
    keys = ("dovuto", "unica", "prima", "seconda")
    summary = (f"{label}: tool={ {k: t[k] for k in keys} } "
               f"sito={ {k: s[k] for k in keys} } "
               f"(il sito ha letto il campo come {s['eco']!r} e arrotonda all'euro)")
    assert t["dovuto"] == s["dovuto"], f"acconto dovuto diverso -- {summary}"
    if not t["dovuto"]:
        return t, s
    # Stessa modalita' di versamento (unica soluzione vs due rate)
    assert (t["unica"] is None) == (s["unica"] is None), f"modalita' diversa -- {summary}"
    if t["unica"] is not None:
        assert_close(t["unica"], s["unica"], TOL, f"{label} unica soluzione")
        assert _giorno_mese(t["scad_unica"]) == _giorno_mese(s["scad_unica"]), summary
        assert s["codici"]["unica"] == "4034"
    else:
        assert_close(t["prima"], s["prima"], TOL, f"{label} primo acconto")
        assert_close(t["seconda"], s["seconda"], TOL, f"{label} secondo acconto")
        assert_close(t["totale"], s["totale"], TOL, f"{label} acconto totale")
        assert _giorno_mese(t["scad_prima"]) == _giorno_mese(s["scad_prima"]), summary
        assert _giorno_mese(t["scad_seconda"]) == _giorno_mese(s["scad_seconda"]), summary
        assert (s["codici"]["prima"], s["codici"]["seconda"]) == ("4033", "4034")
    return t, s


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_piano_soglia_esenzione_51_65(page):
    """Caso al limite (piano): imposta pari alla soglia di esenzione.

    Atteso del piano: nessun acconto dovuto (L. 97/1977, art. 4 D.L. 69/1989:
    dovuto solo se l'imposta dell'anno precedente e' *superiore* a 51,65).
    Il sito arrotonda 51,65 -> 52 (RN34 in euro interi) e chiede un unico
    versamento di 52,00 entro il 30 novembre: scostamento di convenzione.
    """
    _confronta(page, 51.65, "51,65")


def test_piano_centesimo_oltre_esenzione_51_66(page):
    """Caso al limite (piano): un centesimo oltre la soglia di esenzione.

    Atteso del piano: acconto unico di 51,66 entro il 30 novembre (art. 17,
    co. 3, D.P.R. 435/2001: prima rata <= 103 -> unica soluzione a novembre).
    Il sito calcola su 52 (arrotondamento all'euro): unico versamento 52,00.
    """
    _confronta(page, 51.66, "51,66")


def test_piano_limite_versamento_unico_257_52(page):
    """Caso al limite (piano): limite del versamento unico.

    Atteso del piano: unica soluzione di 257,52 entro il 30 novembre.
    Norma: art. 17, co. 3, D.P.R. 435/2001 -- due rate "salvo che il versamento
    da effettuare alla scadenza della prima rata non superi euro 103"; a 257,52
    la prima rata sarebbe 103,01 (> 103), e anche il testo della pagina del
    sito parla di due rate se l'acconto e' "pari o superiore a 257,52" (il
    testo delle istruzioni AdE non e' stato riletto): l'atteso del piano (e il
    ``<= 257.52`` del tool) e' dubbio proprio sul centesimo di confine.
    Il sito arrotonda 257,52 -> 258 e divide in due rate (103,20 + 154,80).
    """
    _confronta(page, 257.52, "257,52")


def test_piano_centesimo_oltre_limite_257_53(page):
    """Caso al limite (piano): un centesimo oltre il limite, due rate.

    Atteso del piano: 103,01 entro il 30 giugno e 154,52 entro il 30 novembre
    (40% / 60%, art. 17, co. 3, D.P.R. 435/2001). Il sito calcola su 258
    (arrotondamento all'euro): 103,20 + 154,80.
    """
    _confronta(page, 257.53, "257,53")


def test_piano_caso_ordinario_1000(page):
    """Caso ordinario (piano): 1.000 euro di imposta netta (RN34).

    Atteso del piano: 400,00 (40%, 30 giugno) e 600,00 (60%, 30 novembre),
    art. 17, co. 3, D.P.R. 435/2001; per i soggetti ISA sarebbero 500 + 500
    (art. 58 D.L. 124/2019), ma ne' il tool ne' il sito hanno l'opzione.
    Controlla anche la maggiorazione dello 0,40% per il versamento entro il
    30 luglio (art. 17, co. 2, D.P.R. 435/2001): il tool la cita solo nel testo
    della scadenza, il sito ne calcola l'importo (401,60).
    """
    t, s = _confronta(page, 1000, "1000")
    assert "0.40%" in t["scad_prima"] and "30 luglio" in t["scad_prima"]
    assert "0,4 %" in s["text"] and "30 luglio" in s["text"]
    assert_close(s["maggiorata"], round(t["prima"] * 1.004, 2), TOL, "prima rata maggiorata")


# ---------------------------------------------------------------------------
# Casi al limite aggiunti (importi interi, come nel rigo RN34)
# ---------------------------------------------------------------------------

def test_limite_ultimo_euro_esente_51(page):
    """Caso al limite: 51 euro, ultimo importo intero sotto la soglia di 51,65.

    Atteso: nessun acconto dovuto (L. 97/1977; art. 4 D.L. 69/1989).
    """
    _confronta(page, 51, "51")


def test_limite_primo_euro_dovuto_52(page):
    """Caso al limite: 52 euro, primo importo intero sopra la soglia di 51,65.

    Atteso: unico versamento di 52,00 entro il 30 novembre (art. 17, co. 3,
    D.P.R. 435/2001: prima rata 20,80 <= 103 -> unica soluzione). E' anche la
    soglia che il sito dichiara nel testo ("RN34 maggiore o uguale a 52").
    """
    _confronta(page, 52, "52")


def test_limite_ultimo_euro_unica_257(page):
    """Caso al limite: 257 euro, ultimo importo intero in unica soluzione.

    Atteso: unico versamento di 257,00 entro il 30 novembre (art. 17, co. 3,
    D.P.R. 435/2001: prima rata 102,80 <= 103).
    """
    _confronta(page, 257, "257")


def test_limite_primo_euro_due_rate_258(page):
    """Caso al limite: 258 euro, primo importo intero con due rate.

    Atteso: 103,20 entro il 30 giugno e 154,80 entro il 30 novembre (art. 17,
    co. 3, D.P.R. 435/2001: prima rata 103,20 > 103); maggiorata 103,61.
    """
    t, s = _confronta(page, 258, "258")
    assert_close(s["maggiorata"], round(t["prima"] * 1.004, 2), TOL, "prima rata maggiorata")


def test_opzione_metodo_previsionale_1000(page):
    """Opzione enumerata: metodo='previsionale' con imposta stimata di 1.000.

    Il sito non ha un selettore del metodo: la pagina dice di inserire nello
    stesso campo l'imposta prevista per l'anno in corso. Il tool con
    'previsionale' applica le stesse regole all'importo passato e aggiunge una
    nota. Atteso: 400,00 + 600,00 (art. 17, co. 3, D.P.R. 435/2001; art. 4
    D.L. 69/1989 per la facolta' del previsionale).
    """
    t, _ = _confronta(page, 1000, "1000 previsionale", metodo="previsionale")
    assert t["raw"]["nota_previsionale"]


def test_importo_elevato_12347(page):
    """Caso ordinario aggiunto: 12.347 euro (importo con migliaia).

    Atteso: 4.938,80 (40%, 30 giugno) e 7.408,20 (60%, 30 novembre), art. 17,
    co. 3, D.P.R. 435/2001; verifica anche il parsing del separatore delle
    migliaia nel risultato del sito.
    """
    _confronta(page, 12347, "12347")


def test_opzione_prima_rata_gia_versata(page):
    """Opzione del sito non confrontabile: "Prima rata gia' versata".

    Il sito ricalcola la seconda rata come differenza tra l'acconto dovuto e la
    prima rata gia' versata (utile quando la percentuale cambia tra le due
    scadenze, come nel 2013 con l'art. 11, co. 18, D.L. 76/2013). Il tool non
    ha un parametro equivalente.
    """
    pytest.skip("non_confrontabile: il tool non ha il parametro 'prima rata gia' versata' "
                "offerto dal sito (seconda rata per differenza)")
