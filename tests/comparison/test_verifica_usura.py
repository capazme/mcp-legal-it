"""Benchmark verifica_usura vs avvocatoandreani.it/servizi/calcolo_tasso_usura.php.

Norma: art. 644 c.p.; L. 108/1996 art. 2 co. 4 come modificato dal DL 70/2011
art. 8 co. 5 lett. d): soglia = min(TEGM x 1,25 + 4; TEGM + 8).
Il TEGM e' quello del trimestre (decreti MEF trimestrali); il sito legge lo
stesso dato da mese e anno di riferimento.

Convenzioni del sito osservate:
- il modulo va inviato con form.submit() (il click sul pulsante e' intercettato
  dall'overlay CMP in headless);
- il tasso inserito viene arrotondato a 2 decimali ("9,263" diventa "9,26%");
- la soglia e' mostrata a 2 decimali; la colonna "Supera" e' un Si/No;
- la fascia per importo (apertura di credito 5.000, cessione del quinto 15.000,
  leasing strumentale/autoveicoli 25.000, factoring 50.000, scoperti 1.500) dipende
  dal campo Importo.
"""

import json
import os
import re

# Pin della data "ad oggi" PRIMA dell'import del tool (trimestre = None).
os.environ["LEGAL_TODAY"] = "2026-09-25"

import pytest  # noqa: E402

import src.server  # noqa: E402,F401  (registra i moduli, evita import circolari)
from src.tools.tassi_interessi import verifica_usura  # noqa: E402
from tests.comparison.conftest import accept_cookies, assert_close  # noqa: E402

_FN = getattr(verifica_usura, "fn", verifica_usura)
_URL = "https://www.avvocatoandreani.it/servizi/calcolo_tasso_usura.php"
_PERIODI = {"Gennaio - Marzo": 1, "Aprile - Giugno": 2, "Luglio - Settembre": 3, "Ottobre - Dicembre": 4}

# tipo_operazione del tool -> (valore del campo Operazione sul sito, importo che seleziona
# la stessa fascia della tabella del tool)
_MAPPA = {
    "mutuo_prima_casa": ("9", 10000),
    "mutuo_tasso_variabile": ("10", 10000),
    "credito_personale": ("13", 10000),
    "apertura_credito": ("1", 3000),
    "apertura_credito_oltre_5000": ("1", 10000),
    "leasing": ("16", 10000),
    "factoring": ("3", 10000),
    "carte_revolving": ("20", 10000),
    "cessione_quinto": ("6", 10000),
    "cessione_quinto_oltre_15000": ("6", 20000),
    "credito_finalizzato": ("19", 10000),
    "leasing_immobiliare_fisso": ("23", 10000),
    "leasing_immobiliare_variabile": ("24", 10000),
    "leasing_auto": ("18", 10000),
    "scoperti_senza_affidamento": ("11", 1000),
}


def _log(caso, tool, sito, esito):
    """Traccia opzionale dei valori (solo se USURA_LOG e' impostata)."""
    path = os.environ.get("USURA_LOG")
    if path:
        with open(path, "a") as fh:
            fh.write(json.dumps({"caso": caso, "tool": tool, "sito": sito, "esito": esito}, ensure_ascii=False) + "\n")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _sito(page, operazione, importo, tasso, mese1, anno1, mese2="", anno2=""):
    """Guida il modulo e restituisce {(anno, trimestre): (tegm, soglia, supera_bool)}."""
    page.goto(_URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1000)
    page.fill("input[name='Importo']", str(importo))
    page.fill("input[name='Tasso']", tasso)
    page.select_option("select[name='Operazione']", operazione)
    page.select_option("select[name='Mese1']", mese1)
    page.select_option("select[name='Anno1']", anno1)
    if mese2:
        page.select_option("select[name='Mese2']", mese2)
        page.select_option("select[name='Anno2']", anno2)
    with page.expect_navigation(timeout=30000):
        page.evaluate("document.querySelector('form[name=CalcoloTassoUsura]').submit()")
    page.wait_for_timeout(1500)
    testo = page.inner_text("body")
    k = testo.find("Anno\tPeriodo")
    assert k >= 0, "tabella dei risultati assente sul sito"
    righe, anno = {}, None
    for line in testo[k:k + 4000].split("\n"):
        m = re.match(r"(?:(\d{4})\t)?([A-Za-z]+ - [A-Za-z]+)\t([\d,]+)%\t([\d,]+)%\t(\w+)", line.strip())
        if m:
            anno = m.group(1) or anno
            righe[(int(anno), _PERIODI[m.group(2)])] = (_num(m.group(3)), _num(m.group(4)), m.group(5).lower().startswith("s"))
    assert righe, "nessuna riga letta dal sito"
    page.wait_for_timeout(1500)  # cortesia verso il sito
    return righe


def _tool(tasso, tipo, trimestre):
    return _FN(tasso_applicato=tasso, tipo_operazione=tipo, trimestre=trimestre)


def _confronta(caso, page, tipo, tasso_num, tasso_txt, mese, anno, trimestre_tool, importo=None):
    op, imp = _MAPPA[tipo]
    riga = _sito(page, op, importo or imp, tasso_txt, mese, str(anno))
    (tegm_s, soglia_s, supera_s), = riga.values()
    r = _tool(tasso_num, tipo, trimestre_tool)
    _log(caso, {"tegm": r.get("tegm_pct"), "soglia": r.get("tasso_soglia_pct"), "usurario": r.get("usurario"),
                "trimestre": r.get("trimestre")}, {"tegm": tegm_s, "soglia": soglia_s, "supera": supera_s},
         "n/d")
    assert_close(r["tegm_pct"], tegm_s, 0.0001, f"{caso} TEGM")
    assert_close(r["tasso_soglia_pct"], soglia_s, 0.0001, f"{caso} soglia")
    assert r["usurario"] == supera_s, f"{caso}: usurario tool={r['usurario']} sito={supera_s}"


# ---------------------------------------------------------------- casi del piano

def test_mutuo_fisso_appena_sotto_soglia(page):
    # Piano: TEGM 4,21%; soglia min(4,21x1,25+4; 4,21+8)=9,2625%; 9,26 non usurario.
    # Art. 2 co. 4 L. 108/1996 (DL 70/2011). Caso al limite (confine al millesimo).
    _confronta("mutuo 9,26 Q3-2026", page, "mutuo_prima_casa", 9.26, "9,26", "09", 2026, "2026-Q3")


def test_mutuo_fisso_appena_sopra_soglia_mese_agosto(page):
    # Piano: 9,27 > 9,2625 usurario. Mese di riferimento agosto = III trimestre 2026
    # (mese diverso da settembre dentro lo stesso trimestre). Caso al limite.
    _confronta("mutuo 9,27 agosto 2026", page, "mutuo_prima_casa", 9.27, "9,27", "08", 2026, "2026-Q3")


def test_revolving_tetto_otto_punti_sotto(page):
    # Piano: TEGM 16,21%; soglia min(24,2625; 24,21)=24,21 (prevale il tetto); 24,21 non usurario.
    # Limite: TEGM > 16% -> tetto TEGM+8 (DL 70/2011 art. 8 co. 5 lett. d).
    _confronta("revolving 24,21 Q3-2026", page, "carte_revolving", 24.21, "24,21", "09", 2026, "2026-Q3")


def test_revolving_tetto_otto_punti_sopra(page):
    # Piano: 24,22 usurario (soglia 24,21, prevale il tetto). Caso al limite.
    _confronta("revolving 24,22 Q3-2026", page, "carte_revolving", 24.22, "24,22", "09", 2026, "2026-Q3")


def test_revolving_formula_prevalente_sotto(page):
    # Piano: TEGM 15,77%; soglia min(23,7125; 23,77)=23,7125 -> pubblicata 23,71.
    # 23,71 <= 23,7125: non usurario. Limite (TEGM sotto 16%: prevale TEGM x 1,25 + 4).
    _confronta("revolving 23,71 Q1-2026", page, "carte_revolving", 23.71, "23,71", "03", 2026, "2026-Q1")


def test_revolving_formula_prevalente_sopra(page):
    # Piano: 23,72 usurario (soglia 23,7125). Limite.
    _confronta("revolving 23,72 Q1-2026", page, "carte_revolving", 23.72, "23,72", "03", 2026, "2026-Q1")


def test_categoria_non_gestita_anticipi_sconti(page):
    # Piano: "Atteso errore per categoria non gestita; il tool usa in silenzio Prestiti personali
    # (soglia 18,60%)". Il sito offre la categoria 3 "Anticipi su crediti e sconti": Q3-2026
    # TEGM 8,12%, soglia 14,15%. Il tool deve dare la stessa soglia o un errore, non un'altra categoria.
    riga = _sito(page, "21", 10000, "10", "09", "2026")
    (tegm_s, soglia_s, supera_s), = riga.values()
    r = _tool(10, "anticipi_sconti", "2026-Q3")
    _log("anticipi_sconti Q3-2026", r, {"tegm": tegm_s, "soglia": soglia_s, "supera": supera_s}, "n/d")
    if "errore" in r:
        return  # rifiuto esplicito: accettabile
    assert_close(r["tegm_pct"], tegm_s, 0.0001, "anticipi TEGM")
    assert_close(r["tasso_soglia_pct"], soglia_s, 0.0001, "anticipi soglia")


def test_trimestre_non_in_tabella_2024_q1(page):
    # Piano: TEGM del I trim. 2024 da leggere dalla fonte (credito personale, DM MEF dic. 2023).
    # Sito: 12,02% / soglia 19,03%. L'usura si valuta al momento della pattuizione (art. 1 DL 394/2000).
    riga = _sito(page, "13", 10000, "10", "01", "2024")
    (tegm_s, soglia_s, supera_s), = riga.values()
    r = _tool(10, "credito_personale", "2024-Q1")
    _log("credito_personale 2024-Q1", r, {"tegm": tegm_s, "soglia": soglia_s, "supera": supera_s}, "n/d")
    if "errore" in r:
        return
    assert r["trimestre"] == "2024-Q1", f"il tool ha sostituito il trimestre 2024-Q1 con {r['trimestre']}"
    assert_close(r["tegm_pct"], tegm_s, 0.0001, "2024-Q1 TEGM")
    assert_close(r["tasso_soglia_pct"], soglia_s, 0.0001, "2024-Q1 soglia")


# ---------------------------------------------------------------- casi al limite aggiuntivi

def test_arrotondamento_soglia_2025_q4_mezzo_centesimo(page):
    # 2025-Q4 mutuo a tasso fisso: TEGM 3,58 -> 3,58x1,25+4 = 8,475. Il sito pubblica 8,48
    # (arrotondamento commerciale); il tool mostra round(8,475, 2) = 8,47 (binario) e con 8,48
    # dichiara usurario. Caso al limite: mezzo centesimo sulla soglia.
    _confronta("mutuo 8,48 Q4-2025", page, "mutuo_prima_casa", 8.48, "8,48", "12", 2025, "2025-Q4")


def test_tasso_con_tre_decimali_sopra_soglia_non_arrotondata(page):
    # Soglia esatta 9,2625. Con 9,263 il tool dice usurario (9,263 > 9,2625); il sito
    # arrotonda l'input a 2 decimali (9,26%) e risponde No. Norma: art. 2 co. 4 L. 108/1996
    # non fissa un numero di decimali. Caso al limite (sub-centesimale).
    # CONVENZIONE (fase 3): il decreto MEF stampa la soglia a quattro decimali (es. 9,2625) e
    # il limite e' superato da qualunque tasso maggiore; il tool confronta il valore esatto
    # (piu' rigoroso), il sito arrotonda l'input. Scostamento accertato e non corretto nel tool.
    riga = _sito(page, "9", 10000, "9,263", "09", "2026")
    (_, _, supera_s), = riga.values()
    r = _tool(9.263, "mutuo_prima_casa", "2026-Q3")
    _log("mutuo 9,263 Q3-2026", {"usurario": r["usurario"], "soglia": r["tasso_soglia_pct"]},
         {"supera": supera_s}, "n/d")
    assert r["usurario"] == supera_s, f"usurario tool={r['usurario']} sito={supera_s}"


def test_trimestre_omesso_usa_trimestre_corrente(page):
    # trimestre=None con LEGAL_TODAY=2026-09-25 -> III trimestre 2026; il sito a settembre 2026
    # da' lo stesso trimestre. Mutuo a tasso fisso, 9,26.
    _confronta("mutuo 9,26 trimestre omesso", page, "mutuo_prima_casa", 9.26, "9,26", "09", 2026, None)


@pytest.mark.parametrize("tipo,importo,tasso_txt", [
    ("cessione_quinto", 15000, "5"),
    ("cessione_quinto_oltre_15000", 15001, "5"),
    ("apertura_credito", 5000, "5"),
    ("apertura_credito_oltre_5000", 5001, "5"),
])
def test_confine_fascia_per_importo(page, tipo, importo, tasso_txt):
    # Limite di fascia: il sito applica la fascia bassa fino a 15.000 (quinto) / 5.000 (apertura
    # di credito) compresi e quella alta da 1 euro oltre. Il tool espone le fasce come tipi distinti.
    _confronta(f"{tipo} importo {importo}", page, tipo, 5.0, tasso_txt, "09", 2026, "2026-Q3", importo=importo)


# ---------------------------------------------------------------- tabella TEGM per categoria

@pytest.mark.parametrize("tipo", list(_MAPPA))
def test_tegm_e_soglia_per_categoria_2025_q1_2026_q3(page, tipo):
    # Una sola richiesta per categoria con intervallo gen 2025 - set 2026 (7 trimestri, due anni
    # diversi). Confronta TEGM e soglia pubblicata (2 decimali) del tool con il sito, con la
    # fascia di importo corrispondente alla tabella del tool. Tolleranza 0,0001 sulle percentuali.
    op, imp = _MAPPA[tipo]
    righe = _sito(page, op, imp, "5", "01", "2025", "09", "2026")
    assert len(righe) == 7
    diff = []
    for (anno, q), (tegm_s, soglia_s, _) in sorted(righe.items()):
        tr = f"{anno}-Q{q}"
        r = _tool(5.0, tipo, tr)
        if r["trimestre"] != tr:
            diff.append(f"{tr}: trimestre sostituito da {r['trimestre']}")
            continue
        if abs(r["tegm_pct"] - tegm_s) > 0.0001:
            diff.append(f"{tr}: TEGM tool={r['tegm_pct']} sito={tegm_s}")
        if abs(r["tasso_soglia_pct"] - soglia_s) > 0.0001:
            diff.append(f"{tr}: soglia tool={r['tasso_soglia_pct']} sito={soglia_s}")
    _log(f"sweep {tipo}", {"n": len(righe)}, {"diff": diff}, "n/d")
    assert not diff, f"{tipo}: " + "; ".join(diff)


def test_categorie_del_sito_assenti_nel_tool():
    # Il sito offre altre fasce/categorie (finanziamenti con carte di credito, altri
    # finanziamenti, factoring oltre 50.000, leasing autoveicoli oltre 25.000, leasing strumentale
    # oltre 25.000): il tool non le espone, quindi non c'e' un valore da confrontare.
    pytest.skip("categorie senza equivalente nel tool: carte di credito, altri finanziamenti, "
                "factoring/leasing strumentale/leasing auto oltre 25-50 mila euro")
