"""Comparison: assegno_unico vs avvocatoandreani.it (calcolo-assegno-unico-universale.php).

Norm: D.Lgs. 29 dicembre 2021, n. 230, art. 4 (text read from Normattiva on
2026-09-25): c. 1 importo per figlio minorenne (175 -> 50 euro between ISEE
15.000 and 40.000, "secondo gli importi indicati nella tabella 1"), +50% for a
child under one year and, in households with three or more children, for each
child aged one to three "per livelli di ISEE fino a 40.000 euro"; c. 2 figlio
maggiorenne fino a 21 anni (85 -> 25 euro); c. 3 maggiorazione per ciascun
figlio successivo al secondo (85 -> 15 euro); c. 8 entrambi i genitori
lavoratori (extended to the widowed working parent); c. 9 without ISEE the
MINIMUM amounts apply; c. 11 amounts and ISEE thresholds are revalued every
year to the cost-of-living index.

Year of the tables. The tool carries the 2026 table (soglie 17.468,51 /
46.582,71; importi 203,80 / 58,30). The site has no year selector and, on
2026-09-25, still computes with the 2024 table (soglie 17.090,61 / 45.574,96;
importi 199,40 / 57,00 - read at runtime from the explanatory table of the
page). The brief asks to select on the site the same year as the tool's
table: since that is impossible, each case is compared at the SAME POSITION
of the revalued table (art. 4, c. 11):

* the ISEE given to the site is the tool's ISEE mapped linearly between the
  two tables' thresholds (so 17.468,51 -> 17.090,61, 46.582,71 -> 45.574,96);
* where the site's answer is a tier of the table (maximum or minimum amount),
  or a percentage of the base amount (the +50% of c. 1), the tool's expected
  value is exact in the tool's own table and is compared at 0,01;
* where the site's answer is an intermediate amount of a table the tool does
  not carry, it is carried to 2026 with the ratio of the two tables' maxima
  (203,80 / 199,40). TOLL_TRASPOSTO = 0,11 euro: the INPS tables are rounded
  to the tenth of a euro every year (2025 and 2026: up to 0,05 each) plus the
  final rounding to the cent. It is the only tolerance wider than 0,01 and it
  is due to the transposition, not to the comparison.
"""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

import src.server  # noqa: F401  (registers every tool module)
from src.tools.dichiarazione_redditi import assegno_unico as _tool

PAGE = "calcolo-assegno-unico-universale.php"

# 2026 thresholds carried by the tool (src/tools/dichiarazione_redditi.py,
# ISEE_MIN / ISEE_MAX; they are not exposed in the tool output).
TOOL_SOGLIA_MIN = 17468.51
TOOL_SOGLIA_MAX = 46582.71

# Brief tolerance 0,01 euro; the 1e-9 only absorbs binary float noise in the
# difference, it does not widen the tolerance.
TOLL = 0.01 + 1e-9
TOLL_TRASPOSTO = 0.11 + 1e-9  # see module docstring

R_MINORI = "Figli minorenni e/o disabili senza limiti di età"
R_MAGGIORENNI = "Figli maggiorenni di età inferiore a 21 anni"
R_SUCCESSIVI = "Figli successivi al secondo"
R_SOTTO_UNO = "Figli di età inferiore a 1 anno"
R_UNO_TRE = "Figli da 1 a tre anni"


def _fn():
    return getattr(_tool, "fn", _tool)


def _tool_call(**kw) -> dict:
    return _fn()(**kw)


def _tool_tabella() -> dict:
    """Maximum and minimum base amount of the tool's own table."""
    return {
        "max": _tool_call(isee=1.0, n_figli=1, eta_figli=[5])["importo_base_per_figlio"],
        "min": _tool_call(isee=10_000_000.0, n_figli=1, eta_figli=[5])["importo_base_per_figlio"],
        "soglia_min": TOOL_SOGLIA_MIN,
        "soglia_max": TOOL_SOGLIA_MAX,
    }


# --------------------------------------------------------------------------
# Site driver
# --------------------------------------------------------------------------


def _parametri_sito(page) -> dict:
    """Read the site's table (year) from the explanatory table of the form page."""
    txt = ""
    for t in page.query_selector_all("table"):
        s = t.inner_text()
        if "Assegno per ogni figlio minorenne" in s:
            txt = s.replace("\xa0", " ")
            break
    m = re.search(
        r"Assegno per ogni figlio minorenne.*?maggiori di ([\d.,]+) euro.*?"
        r"fino a € ([\d.,]+) e resta costante oltre i ([\d.,]+) euro\.\s*€ ([\d.,]+)",
        txt,
        re.S,
    )
    assert m, "tabella degli importi del sito non trovata"
    return {
        "soglia_min": parse_euro(m.group(1)),
        "min": parse_euro(m.group(2)),
        "soglia_max": parse_euro(m.group(3)),
        "max": parse_euro(m.group(4)),
    }


def _isee_per_sito(isee_tool: float, tt: dict, ts: dict) -> float:
    """Map the tool's ISEE to the same position of the site's table (art. 4 c. 11)."""
    if isee_tool <= tt["soglia_min"]:
        return round(isee_tool * ts["soglia_min"] / tt["soglia_min"], 2)
    if isee_tool >= tt["soglia_max"]:
        return round(isee_tool * ts["soglia_max"] / tt["soglia_max"], 2)
    q = (isee_tool - tt["soglia_min"]) / (tt["soglia_max"] - tt["soglia_min"])
    return round(ts["soglia_min"] + q * (ts["soglia_max"] - ts["soglia_min"]), 2)


def _set_checkbox(page, sel: str, want: bool):
    # A click listener of the page (consent layer) swallows real clicks after a
    # few seconds: set the property and call the page's own handler instead.
    page.eval_on_selector(
        sel,
        "(e, w) => { e.checked = w; if (e.id === 'Isee') App.OnClickIsee(e); }",
        want,
    )
    page.wait_for_timeout(150)
    assert page.is_checked(sel) == want, sel


def _sito(page, isee_tool: float | None, figli: list) -> dict:
    """Fill the form and return {parametri, isee_sito, righe, mensile}.

    isee_tool: the ISEE given to the tool (None = ISEE non presentato); it is
    mapped to the same position of the site's table before filling the form.
    figli: list of ages, or (age, requisito_art2) tuples for adult children.
    """
    page.on("dialog", lambda d: d.accept())  # RemoveFigli asks confirm()
    goto(page, PAGE)
    page.wait_for_function("typeof App !== 'undefined' && App && App.Figli", timeout=30000)
    parametri = _parametri_sito(page)
    isee = None if isee_tool is None else _isee_per_sito(isee_tool, _tool_tabella(), parametri)

    _set_checkbox(page, "#Isee", isee is not None)
    if isee is not None:
        page.fill("#ImportoIsee", f"{isee:.2f}".replace(".", ","))
    _set_checkbox(page, "#EtaMadre", False)
    _set_checkbox(page, "#MaggReddito", False)

    n = len(figli)
    for _ in range(12):
        cur = int(page.input_value("#NumFigli"))
        if cur == n:
            break
        if cur < n:
            page.evaluate("App.AddFigli()")
        else:
            page.evaluate(f"App.RemoveFigli({cur - 1})")
        page.wait_for_timeout(400)
    assert int(page.input_value("#NumFigli")) == n

    for i, f in enumerate(figli):
        eta, req = (f, False) if isinstance(f, int) else f
        page.fill(f"#Eta-{i}", str(eta))
        page.evaluate(f"App.GestMaggTran({i})")  # enables 'Requisiti art. 2' for 18-20
        if not page.is_disabled(f"#ReqMagg-{i}"):
            _set_checkbox(page, f"#ReqMagg-{i}", req)

    page.wait_for_timeout(1000)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "() => document.AssegnoUnico.requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_selector("table.importi", timeout=30000)

    righe = {}
    for tr in page.query_selector_all("table.importi tr"):
        tds = [c.inner_text().strip() for c in tr.query_selector_all("td")]
        if len(tds) == 4 and "€" in tds[2]:
            righe[tds[0]] = {
                "num": int(tds[1]),
                "pro_capite": parse_euro(tds[2]),
                "totale": parse_euro(tds[3]),
            }
    res = [s.inner_text().strip() for s in page.query_selector_all("span.result")]
    mensile = None
    for i, s in enumerate(res):
        if s.startswith("Importo mensile") and i + 1 < len(res):
            mensile = parse_euro(res[i + 1])
    assert mensile is not None, f"importo mensile non letto: {res}"
    return {"parametri": parametri, "isee_sito": isee, "righe": righe, "mensile": mensile}


def _livello(importo_sito: float, ts: dict, tt: dict) -> float:
    """Site tier (max / min of its table) -> same tier of the tool's table."""
    if abs(importo_sito - ts["max"]) < 0.005:
        return tt["max"]
    if abs(importo_sito - ts["min"]) < 0.005:
        return tt["min"]
    pytest.fail(f"il sito ha restituito un importo intermedio ({importo_sito}): livello non trasponibile")


def _trasposto(importo_sito: float, ts: dict, tt: dict) -> float:
    """Intermediate site amount carried to the tool's year (ratio of the maxima)."""
    return round(importo_sito * tt["max"] / ts["max"], 2)


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------


def test_isee_assente_importo_minimo(page):
    """ISEE non presentato, un figlio di 5 anni (piano, caso 1; opzione enumerata).

    Atteso del piano: importo minimo 58,30 mensili 2026 - art. 4, c. 9, D.Lgs.
    230/2021 ("nel caso di assenza di ISEE ... spettano gli importi
    corrispondenti a quelli minimi"); il tool restituisce il massimo 203,80.
    Sito: ISEE non spuntato -> importo minimo della sua tabella.
    """
    tt = _tool_tabella()
    r = _tool_call(isee=0, n_figli=1, eta_figli=[5], genitore_solo=False)
    s = _sito(page, None, [5])
    ts = s["parametri"]
    sito = s["righe"][R_MINORI]["pro_capite"]
    atteso = _livello(sito, ts, tt)
    print(f"sito={sito} (tabella {ts}) -> atteso tool {atteso}; tool={r['totale_mensile']}")
    assert_close(r["totale_mensile"], atteso, TOLL, "ISEE assente: importo mensile")


def test_isee_soglia_inferiore(page):
    """ISEE pari alla soglia inferiore 2026 (17.468,51), un figlio di 5 anni (piano, caso 2; limite).

    Atteso del piano: importo massimo 203,80 mensili - art. 4, c. 1 (importo
    pieno per ISEE pari o inferiore alla soglia) e c. 11 (soglia rivalutata).
    Il sito e' interrogato alla sua soglia inferiore (17.090,61).
    """
    tt = _tool_tabella()
    r = _tool_call(isee=17468.51, n_figli=1, eta_figli=[5])
    s = _sito(page, 17468.51, [5])
    ts = s["parametri"]
    assert s["isee_sito"] == ts["soglia_min"]
    sito = s["righe"][R_MINORI]["pro_capite"]
    atteso = _livello(sito, ts, tt)
    print(f"ISEE sito={s['isee_sito']} sito={sito} -> atteso tool {atteso}; tool={r['totale_mensile']}")
    assert_close(r["totale_mensile"], atteso, TOLL, "ISEE alla soglia inferiore")


def test_isee_soglia_superiore(page):
    """ISEE pari alla soglia superiore 2026 (46.582,71), un figlio di 5 anni (piano, caso 3; limite).

    Atteso del piano: importo minimo 58,30 mensili - art. 4, c. 1 (importo
    costante oltre la soglia superiore) e c. 11. Sito interrogato alla sua
    soglia superiore (45.574,96).
    """
    tt = _tool_tabella()
    r = _tool_call(isee=46582.71, n_figli=1, eta_figli=[5])
    s = _sito(page, 46582.71, [5])
    ts = s["parametri"]
    assert s["isee_sito"] == ts["soglia_max"]
    sito = s["righe"][R_MINORI]["pro_capite"]
    atteso = _livello(sito, ts, tt)
    print(f"ISEE sito={s['isee_sito']} sito={sito} -> atteso tool {atteso}; tool={r['totale_mensile']}")
    assert_close(r["totale_mensile"], atteso, TOLL, "ISEE alla soglia superiore")


def _maggiorazione(r: dict, figlio: int, tipo: str) -> float:
    """Tool maggiorazione of type *tipo* for the 0-based child index (0 if absent)."""
    return sum(
        m["importo"]
        for m in r["dettaglio_figli"][figlio]["maggiorazioni"]
        if tipo in m["tipo"]
    )


def _successivi_tool(r: dict) -> float:
    """Tool maggiorazione for children after the second (art. 4, c. 3), if any."""
    return sum(
        m["importo"]
        for f in r["dettaglio_figli"]
        for m in f["maggiorazioni"]
        if "successiv" in m["tipo"] or "terzo" in m["tipo"]
    )


def _confronta(scarti: list, label: str, tool: float, atteso: float, toll: float):
    diff = abs(tool - atteso)
    esito = "ok" if diff <= toll else "SCOSTAMENTO"
    print(f"  {label}: tool={tool:.2f} atteso={atteso:.2f} diff={diff:.2f} (toll {toll:.2f}) {esito}")
    if diff > toll:
        scarti.append(f"{label}: tool={tool:.2f}, atteso dal sito={atteso:.2f}, diff={diff:.2f}")


def test_tre_figli_0_2_10_isee_30000(page):
    """Tre figli di 0, 2 e 10 anni, ISEE 30.000 (piano, caso 4).

    Atteso del piano: +50% dell'importo base per il figlio sotto un anno e +50%
    per il figlio tra 1 e 3 anni nei nuclei con tre o piu' figli (art. 4, c. 1,
    come modificato dalla L. 197/2022: circa 70,59 sull'importo base 2026 di
    141,17), piu' la maggiorazione per il figlio successivo al secondo (art. 4,
    c. 3); il tool aggiunge 96,90 e 34,10 fissi e nessuna maggiorazione per il
    terzo figlio (totale 554,51).
    Confronto per componenti: le maggiorazioni del 50% come quota dell'importo
    base (esatte, 0,01); importo base e maggiorazione c. 3 trasposti al 2026
    (TOLL_TRASPOSTO).
    """
    tt = _tool_tabella()
    r = _tool_call(isee=30000, n_figli=3, eta_figli=[0, 2, 10])
    s = _sito(page, 30000, [0, 2, 10])
    ts, righe = s["parametri"], s["righe"]
    print(f"ISEE sito={s['isee_sito']} righe={righe} mensile sito={s['mensile']}; tool totale={r['totale_mensile']}")
    base_t = r["importo_base_per_figlio"]
    base_s = righe[R_MINORI]["pro_capite"]
    scarti: list[str] = []
    _confronta(scarti, "importo base per figlio", base_t, _trasposto(base_s, ts, tt), TOLL_TRASPOSTO)
    q1 = righe.get(R_SOTTO_UNO, {"pro_capite": 0.0})["pro_capite"] / base_s
    _confronta(scarti, "maggiorazione figlio < 1 anno", _maggiorazione(r, 0, "< 1"), round(q1 * base_t, 2), TOLL)
    q13 = righe.get(R_UNO_TRE, {"pro_capite": 0.0})["pro_capite"] / base_s
    _confronta(scarti, "maggiorazione figlio 1-3 anni", _maggiorazione(r, 1, "1-3"), round(q13 * base_t, 2), TOLL)
    succ_s = righe.get(R_SUCCESSIVI, {"totale": 0.0})["totale"]
    _confronta(scarti, "maggiorazione figli successivi al secondo", _successivi_tool(r), _trasposto(succ_s, ts, tt), TOLL_TRASPOSTO)
    assert not scarti, "\n".join(scarti)


def test_tre_figli_eta_3_isee_sotto_soglia(page):
    """Tre figli di 3, 5 e 8 anni, ISEE 15.000 (caso aggiunto; limite di eta' 3 anni).

    Norma: art. 4, c. 1 ("per ciascun figlio di eta' compresa tra uno e tre
    anni" nei nuclei con tre o piu' figli, +50%) e c. 3 (figlio successivo al
    secondo). ISEE sotto la soglia: importo base al massimo su entrambi i lati,
    quindi base e +50% sono esatti nella tabella del tool; la maggiorazione c. 3
    al massimo (96,90 nel 2024) e' trasposta al 2026. Il tool applica 34,10 fissi
    per il figlio di 3 anni e nessuna maggiorazione c. 3 (totale 645,50).
    """
    tt = _tool_tabella()
    r = _tool_call(isee=15000, n_figli=3, eta_figli=[3, 5, 8])
    s = _sito(page, 15000, [3, 5, 8])
    ts, righe = s["parametri"], s["righe"]
    print(f"ISEE sito={s['isee_sito']} righe={righe} mensile sito={s['mensile']}; tool totale={r['totale_mensile']}")
    base_t = r["importo_base_per_figlio"]
    base_s = righe[R_MINORI]["pro_capite"]
    scarti: list[str] = []
    _confronta(scarti, "importo base per figlio (livello massimo)", base_t, _livello(base_s, ts, tt), TOLL)
    q13 = righe.get(R_UNO_TRE, {"pro_capite": 0.0})["pro_capite"] / base_s
    _confronta(scarti, "maggiorazione figlio di 3 anni", _maggiorazione(r, 0, "1-3"), round(q13 * base_t, 2), TOLL)
    succ_s = righe.get(R_SUCCESSIVI, {"totale": 0.0})["totale"]
    _confronta(scarti, "maggiorazione figli successivi al secondo", _successivi_tool(r), _trasposto(succ_s, ts, tt), TOLL_TRASPOSTO)
    assert not scarti, "\n".join(scarti)


def test_tre_figli_eta_2_isee_sopra_soglia(page):
    """Tre figli di 2, 5 e 8 anni, ISEE 50.000 (caso aggiunto; limite: ISEE oltre la soglia superiore).

    Norma: art. 4, c. 1 - il +50% per i figli tra uno e tre anni spetta "per
    livelli di ISEE fino a 40.000 euro" (rivalutati ex c. 11: 46.582,71 nel
    2026); c. 3 - maggiorazione per il figlio successivo al secondo al suo
    minimo (15 euro, 17,10 nel 2024). Importo base al minimo (esatto nella
    tabella del tool). Il tool aggiunge comunque 34,10 per il figlio di 2 anni
    e nessuna maggiorazione c. 3 (totale 209,00).
    """
    tt = _tool_tabella()
    r = _tool_call(isee=50000, n_figli=3, eta_figli=[2, 5, 8])
    s = _sito(page, 50000, [2, 5, 8])
    ts, righe = s["parametri"], s["righe"]
    print(f"ISEE sito={s['isee_sito']} righe={righe} mensile sito={s['mensile']}; tool totale={r['totale_mensile']}")
    base_t = r["importo_base_per_figlio"]
    base_s = righe[R_MINORI]["pro_capite"]
    scarti: list[str] = []
    _confronta(scarti, "importo base per figlio (livello minimo)", base_t, _livello(base_s, ts, tt), TOLL)
    q13 = righe.get(R_UNO_TRE, {"pro_capite": 0.0})["pro_capite"] / base_s
    _confronta(scarti, "maggiorazione figlio di 2 anni", _maggiorazione(r, 0, "1-3"), round(q13 * base_t, 2), TOLL)
    succ_s = righe.get(R_SUCCESSIVI, {"totale": 0.0})["totale"]
    _confronta(scarti, "maggiorazione figli successivi al secondo", _successivi_tool(r), _trasposto(succ_s, ts, tt), TOLL_TRASPOSTO)
    assert not scarti, "\n".join(scarti)


def test_figlio_19_anni_isee_25000(page):
    """Figlio di 19 anni, ISEE 25.000 (piano, caso 5).

    Atteso del piano: importo per figlio maggiorenne fino a 21 anni, inferiore a
    quello dei minori - art. 4, c. 2 (85 euro al massimo, 25 al minimo, rivalutati
    ex c. 11); il tool applica l'importo dei minori (166,16). Sul sito il figlio
    18-20enne conta solo con uno dei requisiti dell'art. 2, c. 1 (spuntato).
    L'importo del sito (tabella c. 2, 2024) e' trasposto al 2026 (TOLL_TRASPOSTO).
    """
    tt = _tool_tabella()
    r = _tool_call(isee=25000, n_figli=1, eta_figli=[19])
    s = _sito(page, 25000, [(19, True)])
    ts, righe = s["parametri"], s["righe"]
    print(f"ISEE sito={s['isee_sito']} righe={righe} mensile sito={s['mensile']}; tool totale={r['totale_mensile']}")
    assert R_MAGGIORENNI in righe, righe
    atteso = _trasposto(righe[R_MAGGIORENNI]["pro_capite"], ts, tt)
    assert_close(r["totale_mensile"], atteso, TOLL_TRASPOSTO, "figlio maggiorenne di 19 anni")


def test_genitore_solo_due_figli(page):
    """Due figli di 4 e 8 anni, genitore solo, ISEE 25.000 (piano, caso 6).

    Atteso del piano: la maggiorazione del 30% per genitore solo non risulta nel
    D.Lgs. 230/2021 (l'art. 4, c. 8 prevede la maggiorazione per entrambi i
    genitori lavoratori, estesa al genitore lavoratore vedovo per 5 anni); il
    tool aggiunge 99,70. Il sito non offre un'opzione "genitore solo" (solo
    "madre < 21 anni" e "genitori entrambi lavoratori"): caso non confrontabile.
    """
    r = _tool_call(isee=25000, n_figli=2, eta_figli=[4, 8], genitore_solo=True)
    pytest.skip(
        "il sito non offre l'opzione 'genitore solo' (art. 4 D.Lgs. 230/2021 non la prevede); "
        f"tool: totale {r['totale_mensile']} di cui maggiorazione genitore solo {r['maggiorazione_genitore_solo']}"
    )


