# FASE 3 (verdetto: sito_errato). The site prints 12 x the periodic rate (a nominal rate) under the
# label TAEG. Art. 121 c. 1 lett. m) TUB defines the TAEG as the total cost of credit "in percentuale
# annua" and Dir. 2008/48/CE Annex I defines it through the annual EFFECTIVE rate X ((1+X)^t with t in
# years), so the tool's taeg_pct (effective) is the legal figure. Hand check (bisection on the monthly IRR):
# 30.000 / 120 x 269,3707 / 270 upfront -> monthly i = 0,14034%, 12 x i = 1,6841% (site 1,68, tool tan_pct),
# (1+i)^12 - 1 = 1,6972% (tool taeg_pct 1,6975 with rounded rata). The taeg_pct failures below are that
# convention gap, not a tool error; tan_pct coincides with the site.
"""Comparison tests: calcolo_taeg vs avvocatoandreani.it/servizi/calcolo-taeg.php.

Norma: art. 121 TUB co. 1 lett. m; Dir. 2008/48/CE all. I (il sito cita il D.M. 8/7/1992, superato).

Convenzione osservata: il sito non riceve la rata ma il TAN; calcola la rata, poi
il TAEG come 12 x (tasso periodico interno), cioe' un tasso NOMINALE annuo, e lo
mostra con due decimali. Il tool restituisce due valori:
  - taeg_pct: tasso EFFETTIVO annuo ((1+r)^12 - 1), formula dell'all. I Dir. 2008/48/CE;
  - tan_pct : 12 x r (stessa convenzione del sito).
Per ogni scenario ci sono quindi due test: il confronto di taeg_pct con il sito
(scostamento genuino di convenzione, resta fallito) e quello di tan_pct (deve coincidere).

Tolleranza: il sito arrotonda a 2 decimali, quindi 0,005 punti percentuali (mezzo
centesimo di punto) e' il minimo confronto possibile; le quattro decimali del brief
non sono applicabili al valore del sito. La rata passata al tool e' quella mostrata
dal sito: rata francese esatta C*i/(1-(1+i)^-n), i = TAN/12 (il sito la usa non arrotondata
nel calcolo del TAEG; con la rata arrotondata a 2 decimali il caso a 2 rate sposta il
risultato di 0,0008 punti, oltre il mezzo centesimo). Il test verifica che la rata
mostrata dal sito sia quella esatta arrotondata al centesimo.

Il sito conserva in sessione i valori dei campi: ogni chiamata riempie TUTTI i campi
(vuoti compresi). Il pulsante non risponde al click sintetico: si usa requestSubmit.
"""
import re
import time

import pytest

from tests.comparison.conftest import accept_cookies, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo-taeg.php"
TOL_PP = 0.005  # mezzo centesimo di punto: il sito mostra due decimali

_CAMPI = {
    "istr": "SpeseIstruttoria",
    "med": "CostoMediazione",
    "notarili": "SpeseNotarili",
    "alt": "SpeseIniziali",
    "inc": "SpeseIncassoRata",
    "ass": "SpeseAssicurazione",
    "gest": "SpeseGestioneAnnuale",
}
_cache: dict = {}


def _it(x):
    return str(x).replace(".", ",")


def _site(page, cap, tasso, rate, **spese):
    """Ritorna dict con rata e taeg letti dal sito, oppure None se non calcola."""
    key = (cap, tasso, rate, tuple(sorted(spese.items())))
    if key in _cache:
        return _cache[key]
    time.sleep(2)
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("#Capitale", _it(cap))
    page.fill("#Tasso", _it(tasso))
    page.select_option("#Periodicita", "12")
    page.check("#TipoDurata-2")
    page.select_option("#NumeroRate", str(rate))
    for k, fid in _CAMPI.items():
        page.fill("#" + fid, _it(spese.get(k, "")))
    try:
        with page.expect_navigation(timeout=20000):
            page.evaluate(
                "document.getElementById('CalcoloTaeg').requestSubmit("
                "document.getElementById('btn-calc'))"
            )
    except Exception:
        _cache[key] = None
        return None
    page.wait_for_timeout(1500)
    text = page.inner_text("body")
    m_t = re.search(r"TAEG su base annua:\s*([\d.]+,\d+)\s*%", text)
    m_r = re.search(r"Importo della Rata:\s*€\s*([\d.]+,\d{2})", text)
    if not (m_t and m_r):
        _cache[key] = None
        return None
    out = {"taeg": parse_euro(m_t.group(1)), "rata": parse_euro(m_r.group(1))}
    _cache[key] = out
    return out


def _tool(capitale, rate, importi_rate, spese_iniziali=0, spese_periodiche=0):
    import src.server  # noqa: F401
    from src.tools.tassi_interessi import calcolo_taeg

    fn = getattr(calcolo_taeg, "fn", calcolo_taeg)
    return fn(capitale=capitale, rate=rate, importi_rate=importi_rate,
              spese_iniziali=spese_iniziali, spese_periodiche=spese_periodiche)


def _confronta(page, campo, cap, tasso, rate, iniziali=0.0, periodiche=0.0, **spese):
    s = _site(page, cap, tasso, rate, **spese)
    assert s is not None, "il sito non restituisce un risultato"
    i = tasso / 1200
    rata = cap * i / (1 - (1 + i) ** -rate)
    assert abs(rata - s["rata"]) <= 0.005 + 1e-9, (rata, s["rata"])
    t = _tool(cap, rate, rata, iniziali, periodiche)
    assert "errore" not in t, t
    diff = abs(t[campo] - s["taeg"])
    assert diff <= TOL_PP, (
        f"{campo}: tool={t[campo]:.4f}, sito={s['taeg']:.2f}, diff={diff:.4f} (max {TOL_PP})"
    )


# --- Caso 1: esempio del sito, sole spese iniziali (limite: valore pubblicato) ---
# Piano: TAEG 1,70% (1,6971) con all. I Dir. 2008/48/CE; la pagina riporta 1,68% (= 12 x r).
def test_esempio_sito_taeg_effettivo(page):
    _confronta(page, "taeg_pct", 30000, 1.5, 120, iniziali=270, istr=270)


def test_esempio_sito_tan12(page):
    _confronta(page, "tan_pct", 30000, 1.5, 120, iniziali=270, istr=270)


# --- Caso 2: esempio con incasso 5 euro a rata e 20 euro annui (approssimati a 1,6667/mese) ---
# Piano: TAEG circa 2,21% (2,2081) con la formula europea; la pagina riporta 2,18%.
def test_esempio_sito_spese_ricorrenti_taeg_effettivo(page):
    _confronta(page, "taeg_pct", 30000, 1.5, 120, iniziali=270, periodiche=5 + 20 / 12,
               istr=270, inc=5, gest=20)


def test_esempio_sito_spese_ricorrenti_tan12(page):
    _confronta(page, "tan_pct", 30000, 1.5, 120, iniziali=270, periodiche=5 + 20 / 12,
               istr=270, inc=5, gest=20)


# --- Caso 2b: sole spese di incasso mensili (nessuna spesa annua): confronto pulito ---
# Nessuna cifra nel piano. Il caso 2 differisce per come le spese annue sono modellate:
# il sito le addebita una volta l'anno (piano: 2,2065 effettivo con le spese alla loro data),
# il tool le puo' solo spalmare in dodicesimi mensili.
def test_solo_incasso_mensile_taeg_effettivo(page):
    _confronta(page, "taeg_pct", 30000, 1.5, 120, iniziali=270, periodiche=5, istr=270, inc=5)


def test_solo_incasso_mensile_tan12(page):
    _confronta(page, "tan_pct", 30000, 1.5, 120, iniziali=270, periodiche=5, istr=270, inc=5)


# --- Caso 3 (limite: spese iniziali su piu' voci, ricorrenti su piu' voci, 60 rate) ---
# 10.000 al 6% per 5 anni, iniziali 300+500, ricorrenti 2+10 a rata, nessuna spesa annua.
# Nessuna cifra nel piano: atteso = stessa convenzione del sito.
def test_spese_multiple_taeg_effettivo(page):
    _confronta(page, "taeg_pct", 10000, 6, 60, iniziali=800, periodiche=12,
               istr=300, notarili=500, ass=10, inc=2)


def test_spese_multiple_tan12(page):
    _confronta(page, "tan_pct", 10000, 6, 60, iniziali=800, periodiche=12,
               istr=300, notarili=500, ass=10, inc=2)


# --- Caso 4 (limite: durata minima, 2 rate, TAEG molto alto) ---
def test_due_rate_taeg_effettivo(page):
    _confronta(page, "taeg_pct", 5000, 8, 2, iniziali=50, alt=50)


def test_due_rate_tan12(page):
    _confronta(page, "tan_pct", 5000, 8, 2, iniziali=50, alt=50)


# --- Caso 5 (limite: tasso zero) ---
# Piano: TAEG 0,00 e costo totale 0. Il sito non calcola con TAN = 0.
def test_tasso_zero(page):
    s = _site(page, 1200, 0, 12)
    t = _tool(1200, 12, 100)
    assert t["taeg_pct"] == 0.0 and t["costo_totale_credito"] == 0.0, t
    if s is None:
        pytest.skip("il sito non restituisce alcun risultato con TAN 0 (tool: taeg 0,00, costo 0)")
    assert abs(t["taeg_pct"] - s["taeg"]) <= TOL_PP


# --- Caso 6 (limite: spese iniziali pari al capitale) ---
# Piano: errore, netto erogato nullo. Il sito produce un TAEG privo di senso (miliardi di %).
def test_spese_pari_al_capitale(page):
    t = _tool(1200, 12, 100, spese_iniziali=1200)
    assert "errore" in t
    pytest.skip("non confrontabile: il sito non segnala errore ma mostra un TAEG assurdo; "
                "il tool rifiuta correttamente (netto erogato nullo)")
