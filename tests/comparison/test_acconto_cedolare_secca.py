"""Benchmark fase 1: acconto_cedolare_secca vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-acconto-cedolare-secca.php
Modulo "Cedolare" (POST): campo ``CedolareSecca`` (RB11 col. 3), campo
``PrimaRata`` (prima rata gia' versata, senza maggiorazione), pulsante ``#button1``.
Il risultato e' una tabella "Codice tributo acconto | Importo | Scadenza" con le
righe ``1840 Prima rata``, ``1841 Seconda rata`` oppure ``1841 Unico versamento``,
e il testo "L'acconto sulla Cedolare Secca non e' dovuto" sotto soglia.

Norma: art. 3, comma 4, D.Lgs. 23/2011 -- acconto pari al 100% della cedolare
dell'anno precedente, con le regole e le scadenze dell'acconto IRPEF (soglie di
51,65 e 257,52 euro della disciplina dell'acconto IRPEF; termini dell'art. 17
D.P.R. 435/2001):
non dovuto fino a 51,65; unica soluzione entro il 30 novembre fino a 257,52;
oltre, 40% entro il 30 giugno e 60% entro il 30 novembre.

Convenzione osservata sul sito: l'importo inserito viene arrotondato all'unita'
di euro (half-up: 51,65 -> 52; 257,49 -> 257; 257,50 -> 258), perche' il campo
e' il rigo RB11 col. 3 del modello REDDITI, espresso in euro interi. Il tool
invece applica le soglie all'importo esatto passato. Sugli importi interi (gli
unici che possono comparire nel rigo) i due coincidono; sugli importi con i
centesimi dei casi del piano divergono. I test restano tool == sito: lo
scostamento lo giudica la fase 2.

Tolleranza: 0,01 euro sugli importi (brief di benchmark); scadenze confrontate
su giorno e mese (il tool non indica l'anno, il sito indica il 2026: 30 giugno
2026 e' martedi', 30 novembre 2026 e' lunedi', nessuna proroga per festivo).

Verdetto fase 2-3 (2026-09-29): convenzione. Il rigo di dichiarazione e' in euro
interi e il sito arrotonda half-up all'unita' prima di applicare le soglie; il
tool applica le soglie all'importo esatto (i centesimi non possono comparire nel
rigo). Nessuna norma impone un arrotondamento diverso: gli scostamenti sui casi
con i centesimi (51,65; 51,66; 257,53) restano documentati e non vanno corretti.
Il solo errore del tool era il confine dei centesimi: a 257,52 il 40% e' 103,01 e
supera euro 103 (art. 17, c. 3, D.P.R. 435/2001), quindi due rate; corretto con
test unitari in tests/unit/test_dichiarazione_redditi.py. Sugli interi il tool
coincide con il sito.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

PAGE = "calcolo-acconto-cedolare-secca.php"
TOL = 0.01


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(imposta: float) -> dict:
    import importlib

    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)

    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod.acconto_cedolare_secca, "fn", mod.acconto_cedolare_secca)
    r = fn(imposta_anno_precedente=imposta)
    assert "errore" not in r, r
    out = {"dovuto": r["acconto_dovuto"], "unica": None, "prima": None, "seconda": None,
           "scad_unica": None, "scad_prima": None, "scad_seconda": None, "raw": r}
    if not r["acconto_dovuto"]:
        return out
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
    return f"{v:.2f}".replace(".", ",")


def _site(page, imposta: float, prima_rata: str = "") -> dict:
    goto(page, PAGE, wait_ms=1500)
    # Il banner dei cookie (#accept-btn) compare dopo il domcontentloaded: se
    # resta aperto intercetta il click forzato su #button1 e il modulo non parte.
    accept_cookies(page)
    page.fill("#CedolareSecca", _fmt_it(imposta))
    page.fill("#PrimaRata", prima_rata)
    page.click("#button1", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)

    body = page.inner_text("body")
    i = body.find("CALCOLO ACCONTO CEDOLARE SECCA")
    j = body.find("Pubblicit", i)
    assert i >= 0, "modulo del sito non trovato"
    res = body[i:j if j > i else None]

    out = {"dovuto": None, "unica": None, "prima": None, "seconda": None,
           "scad_unica": None, "scad_prima": None, "scad_seconda": None,
           "codici": {}, "maggiorata": None, "text": res}
    if "non è dovuto" in res:
        out["dovuto"] = False
        return out

    for key, label in (("unica", "Unico versamento"), ("prima", "Prima rata"),
                       ("seconda", "Seconda rata")):
        m = re.search(rf"(\d{{4}})\s+{label}:\s*€\s*([\d.,]+)\s+{_DATE}", res)
        if m:
            out["codici"][key] = m.group(1)
            out[key] = parse_euro(m.group(2))
            out[f"scad_{key}"] = m.group(3)
    m = re.search(r"maggiorazione è pari a\s*€\s*([\d.,]+)", res)
    if m:
        out["maggiorata"] = parse_euro(m.group(1))
    assert out["unica"] is not None or out["prima"] is not None, (
        f"risultato del sito non riconosciuto:\n{res}")
    out["dovuto"] = True
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _giorno_mese(s: str) -> str:
    """'30 giugno (o 30 luglio ...)' / '30 giugno 2026' -> '30 giugno'."""
    return " ".join(s.split("(")[0].split()[:2])


def _confronta(page, imposta: float, label: str) -> tuple[dict, dict]:
    t = _tool(imposta)
    s = _site(page, imposta)
    summary = (f"{label}: tool={ {k: t[k] for k in ('dovuto', 'unica', 'prima', 'seconda')} } "
               f"sito={ {k: s[k] for k in ('dovuto', 'unica', 'prima', 'seconda')} }")
    assert t["dovuto"] == s["dovuto"], f"acconto dovuto diverso -- {summary}"
    if not t["dovuto"]:
        return t, s
    # Stessa modalita' di versamento (unica soluzione vs due rate)
    assert (t["unica"] is None) == (s["unica"] is None), f"modalita' diversa -- {summary}"
    if t["unica"] is not None:
        assert_close(t["unica"], s["unica"], TOL, f"{label} unica soluzione")
        assert _giorno_mese(t["scad_unica"]) == _giorno_mese(s["scad_unica"]), summary
        assert s["codici"]["unica"] == "1841"
    else:
        assert_close(t["prima"], s["prima"], TOL, f"{label} primo acconto")
        assert_close(t["seconda"], s["seconda"], TOL, f"{label} secondo acconto")
        assert _giorno_mese(t["scad_prima"]) == _giorno_mese(s["scad_prima"]), summary
        assert _giorno_mese(t["scad_seconda"]) == _giorno_mese(s["scad_seconda"]), summary
        assert (s["codici"]["prima"], s["codici"]["seconda"]) == ("1840", "1841")
    return t, s


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_piano_soglia_esenzione_51_65(page):
    """Caso al limite (piano): imposta pari alla soglia di esenzione.

    Atteso del piano: nessun acconto dovuto (art. 3, co. 4, D.Lgs. 23/2011 +
    soglia IRPEF 51,65: dovuto solo se l'imposta e' *superiore* a 51,65).
    Il sito arrotonda 51,65 -> 52 (RB11 col. 3 in euro interi) e chiede un
    unico versamento di 52,00 entro il 30 novembre: scostamento di convenzione.
    Riscontro per la fase 2: le istruzioni Redditi 2026 PF, fasc. 1, rigo LC2
    (citate dal portale infoprecompilata dell'Agenzia) esprimono la soglia in
    euro interi: "inferiore ad euro 52" non dovuto, "maggiore o uguale ad euro
    52" dovuto al 100%.
    """
    _confronta(page, 51.65, "51,65")


def test_piano_limite_versamento_unico_257_52(page):
    """Caso al limite (piano): limite del versamento unico.

    Atteso del piano: unica soluzione di 257,52 entro il 30 novembre (soglia
    IRPEF di 257,52 applicata alla cedolare dall'art. 3, co. 4, D.Lgs. 23/2011).
    Il sito arrotonda 257,52 -> 258 e divide in due rate (103,20 + 154,80).
    Riscontro per la fase 2: le istruzioni Redditi 2026 PF, fasc. 1, rigo LC2
    (portale infoprecompilata dell'Agenzia) prevedono l'unica soluzione se
    l'importo e' "inferiore ad euro 257,52" e le due rate se e' "pari o
    superiore ad euro 257,52": su 257,52 esatti il tool (<= 257,52 -> unica) e
    l'atteso del piano non seguono quella formulazione.
    """
    _confronta(page, 257.52, "257,52")


def test_piano_centesimo_oltre_limite_257_53(page):
    """Caso al limite (piano): un centesimo oltre il limite.

    Atteso del piano: 103,01 entro il 30 giugno e 154,52 entro il 30 novembre
    (40% / 60%, art. 3, co. 4, D.Lgs. 23/2011). Il sito calcola su 258
    (arrotondamento all'euro): 103,20 + 154,80.
    """
    _confronta(page, 257.53, "257,53")


def test_piano_caso_ordinario_2000(page):
    """Caso ordinario (piano): 2.000 euro di cedolare dell'anno precedente.

    Atteso del piano: 800,00 (40%, 30 giugno) e 1.200,00 (60%, 30 novembre),
    art. 3, co. 4, D.Lgs. 23/2011. Controlla anche la maggiorazione dello
    0,40% per il versamento entro il 30 luglio (art. 17, co. 2, D.P.R.
    435/2001): il tool la cita solo nel testo della scadenza, il sito ne
    calcola l'importo (803,20).
    """
    t, s = _confronta(page, 2000, "2000")
    assert "0.40%" in t["scad_prima"] and "30 luglio" in t["scad_prima"]
    assert "0,4 %" in s["text"] and "30 luglio" in s["text"]
    assert_close(s["maggiorata"], round(t["prima"] * 1.004, 2), TOL, "prima rata maggiorata")


# ---------------------------------------------------------------------------
# Casi al limite aggiunti (importi interi, come nel rigo RB11 col. 3)
# ---------------------------------------------------------------------------

def test_limite_intero_sotto_soglia_51(page):
    """Caso al limite: 51 euro, ultimo intero sotto la soglia di 51,65.

    Atteso: nessun acconto dovuto (soglia 51,65; art. 3, co. 4, D.Lgs. 23/2011).
    """
    _confronta(page, 51, "51")


def test_limite_intero_primo_dovuto_52(page):
    """Caso al limite: 52 euro, primo intero sopra la soglia di esenzione.

    Atteso: unica soluzione di 52,00 entro il 30 novembre (acconto <= 257,52).
    """
    _confronta(page, 52, "52")


def test_limite_intero_unica_257(page):
    """Caso al limite: 257 euro, ultimo intero entro il limite di 257,52.

    Atteso: unica soluzione di 257,00 entro il 30 novembre.
    """
    _confronta(page, 257, "257")


def test_limite_intero_due_rate_258(page):
    """Caso al limite: 258 euro, primo intero oltre 257,52.

    Atteso: 103,20 (40%) entro il 30 giugno e 154,80 (60%) entro il 30 novembre.
    """
    _confronta(page, 258, "258")


def test_ordinario_dispari_1001(page):
    """Caso ordinario con ripartizione non tonda: 1.001 euro.

    Atteso: 400,40 (40%) e 600,60 (60%), art. 3, co. 4, D.Lgs. 23/2011.
    """
    _confronta(page, 1001, "1001")


def test_prima_rata_gia_versata_non_confrontabile(page):
    """Opzione del sito "Prima rata gia' versata" (seconda rata = acconto - versato).

    Il tool non ha un parametro equivalente: caso non confrontabile.
    (Riscontro manuale sul sito: 2.000 con prima rata versata 800 -> seconda 1.200,00.)
    """
    pytest.skip("il tool non accetta la prima rata gia' versata (campo PrimaRata del sito)")
