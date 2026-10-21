"""Benchmark fase 1: regime_forfettario vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-imposta-regime-forfettario.php

Modulo ``Forfettario`` (POST verso ``#Res``). Campi: select ``Settore`` (1-9, nove
settori dell'allegato 4 alla L. 190/2014 ridotti a sei coefficienti: 40, 54, 62,
67, 78, 86), testo ``Reddito`` (ricavi lordi, formato italiano con la virgola),
testo ``Contributi`` (contributi previdenziali obbligatori, co. 64), checkbox
``NuovaAttivita`` (aliquota 5% del co. 65). Pulsante ``#button1`` (name ``Op``,
value ``Calcola``). Risultato in ``#R-Output`` (``table.result``): coefficiente e
limite ("Limite di reddito: € 85.000, coefficiente di redditività: 78%"),
"Imponibile calcolato al N%", "Imponibile al netto dei contributi" (solo con
contributi valorizzati), "Imposta sostitutiva al N%". Oltre il limite il sito non
calcola e mostra l'errore di campo "Ricavi massimi per questo settore: € 85.000,00".

Driver: il banner CMP (qc-cmp2) viene rimosso via JS senza prestare consenso;
la spunta si imposta con ``checked = true`` e l'invio usa
``form.requestSubmit(#button1)`` perche' il click forzato puo' colpire l'overlay.

Tool: ``regime_forfettario(ricavi, coefficiente_redditivita, anni_attivita,
contributi_inps)`` (src/tools/dichiarazione_redditi.py, tabella irpef_scaglioni.json
blocco ``forfettario``: limite 85.000, aliquota 15%, startup 5%).
Corrispondenze: coefficiente -> settore del sito (40 -> 2 o 7, 54 -> 4, 62 -> 6,
67 -> 9, 78 -> 8, 86 -> 5); ``anni_attivita`` 1-5 -> spunta "Nuova attivita'",
oltre 5 -> nessuna spunta (il sito non conosce gli anni: chiede all'utente se
ricorrono le condizioni del co. 65, che il tool invece presume).

Norme (testo letto con cite_law, art. 1 L. 190/2014 vigente):
- co. 54 lett. a): ricavi/compensi dell'anno precedente non superiori a 85.000 euro;
- co. 64: reddito = ricavi x coefficiente (allegato 4); imposta sostitutiva 15%;
  contributi previdenziali dedotti dal reddito cosi' determinato, "l'eventuale
  eccedenza e' deducibile dal reddito complessivo" (art. 10 TUIR);
- co. 65: 5% per il periodo d'imposta di inizio e i quattro successivi, alle
  condizioni delle lettere a)-c);
- co. 71: cessazione dall'anno successivo, o dallo stesso anno oltre 100.000 euro.

Confronto (tool == sito, tolleranza 0,01 euro sugli importi, coefficiente e
aliquota esatti): reddito lordo (``reddito_lordo`` / "Imponibile calcolato"),
reddito imponibile (``reddito_imponibile`` / "Imponibile al netto dei contributi",
o l'imponibile calcolato se i contributi sono zero), imposta sostitutiva.
Non confrontati perche' il sito non li espone: ``reddito_netto`` e
``confronto_ordinario`` del tool (il sito mostra invece l'incidenza percentuale
dell'imposta sui ricavi, che il tool non espone). Il sito e' un benchmark, non una
fonte: un KO resta un KO e lo giudica la fase 2.
"""

import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest  # noqa: E402

from tests.comparison.conftest import parse_euro  # noqa: E402

URL = "https://www.avvocatoandreani.it/servizi/calcolo-imposta-regime-forfettario.php"
TOL_EUR = 0.01

# coefficiente di redditivita' -> value del select "Settore" del sito
SETTORE = {40: "2", 54: "4", 62: "6", 67: "9", 78: "8", 86: "5"}

_SITE_CACHE: dict[tuple, dict] = {}


def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  registra i moduli ed evita import circolari
    from src.tools.dichiarazione_redditi import regime_forfettario

    fn = getattr(regime_forfettario, "fn", regime_forfettario)
    return fn(**kwargs)


def _fmt_it(value: float) -> str:
    """50000.5 -> '50000,50' (formato accettato dal campo del sito)."""
    return f"{value:.2f}".replace(".", ",")


def _remove_cmp(page) -> None:
    page.evaluate(
        'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container").forEach(el => el.remove())'
    )


def _num(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    return parse_euro(m.group(1)) if m else None


def _site(page, settore: str, ricavi: float, contributi: float, nuova: bool) -> dict:
    """Compila e invia il modulo; restituisce i valori letti (con cache per input)."""
    key = (settore, ricavi, contributi, nuova)
    if key in _SITE_CACHE:
        return _SITE_CACHE[key]
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    _remove_cmp(page)
    page.select_option("#Settore", settore)
    page.fill("#Reddito", _fmt_it(ricavi))
    if contributi:
        page.fill("#Contributi", _fmt_it(contributi))
    if nuova:
        page.evaluate("document.getElementById('NuovaAttivita').checked = true")
    _remove_cmp(page)
    with page.expect_navigation(timeout=60000, wait_until="domcontentloaded"):
        page.evaluate(
            "document.getElementById('Forfettario').requestSubmit(document.getElementById('button1'))"
        )
    page.wait_for_timeout(2000)
    out = page.inner_text("#R-Output") if page.locator("#R-Output").count() else ""
    err_el = page.locator(".ferror")
    errore = err_el.first.inner_text().strip() if err_el.count() else ""
    coeff = re.search(r"coefficiente di redditivit\S*:\s*(\d+(?:,\d+)?)%", out)
    aliq = re.search(r"Imposta sostitutiva al (\d+)%", out)
    lordo = _num(r"Imponibile calcolato al [\d,]+%[^:]*:\s*€\s*(-?[\d.,]+)", out)
    netto = _num(r"Imponibile al netto dei contributi[^:]*:\s*€\s*(-?[\d.,]+)", out)
    res = {
        "testo": out.strip(),
        "errore": errore,
        "limite_errore": _num(r"Ricavi massimi per questo settore:\s*€\s*([\d.,]+)", errore),
        "coefficiente": float(coeff.group(1).replace(",", ".")) if coeff else None,
        "aliquota": int(aliq.group(1)) if aliq else None,
        "reddito_lordo": lordo,
        "reddito_imponibile": netto if netto is not None else lordo,
        "imposta": _num(r"Imposta sostitutiva al \d+%[^:]*:\s*€\s*(-?[\d.,]+)", out),
    }
    _SITE_CACHE[key] = res
    return res


def _confronta(tool: dict, site: dict) -> list[str]:
    """Confronta tutte le voci e restituisce l'elenco completo OK/KO."""
    righe, ko = [], False

    def voce(label, t, s, tol=None):
        nonlocal ko
        if s is None or t is None:
            ok = False
        elif tol is None:
            ok = t == s
        else:
            ok = abs(t - s) <= tol
        ko |= not ok
        righe.append(f"{'OK' if ok else 'KO'} {label}: tool={t} sito={s}")

    voce("coefficiente %", float(tool["coefficiente_redditivita_pct"]), site["coefficiente"])
    voce("aliquota %", tool["aliquota_pct"], site["aliquota"])
    voce("reddito lordo", tool["reddito_lordo"], site["reddito_lordo"], TOL_EUR)
    voce("reddito imponibile", tool["reddito_imponibile"], site["reddito_imponibile"], TOL_EUR)
    voce("imposta sostitutiva", tool["imposta_sostitutiva"], site["imposta"], TOL_EUR)
    return righe if ko else []


CASI = [
    # Piano 1 - professionista al primo anno (co. 64-65): reddito 39.000 (78%),
    # imposta 5% = 1.950,00.
    pytest.param(dict(ricavi=50000, coefficiente_redditivita=78, anni_attivita=1, contributi_inps=0),
                 id="piano1-professionista-startup"),
    # Piano 2 - LIMITE: ricavi esattamente 85.000 (co. 54 lett. a, limite incluso),
    # aliquota 15%, contributi 8.000 dedotti (co. 64): reddito 66.300, imponibile
    # 58.300, imposta 8.745,00.
    pytest.param(dict(ricavi=85000, coefficiente_redditivita=78, anni_attivita=6, contributi_inps=8000),
                 id="piano2-limite-85000-ordinaria"),
    # Piano 4 - commercio 40% (allegato 4), terzo anno (co. 65): reddito 24.000,
    # imponibile 20.000, imposta 5% = 1.000,00.
    pytest.param(dict(ricavi=60000, coefficiente_redditivita=40, anni_attivita=3, contributi_inps=4000),
                 id="piano4-commercio-40-terzo-anno"),
    # Piano 5 - LIMITE: quinto anno ancora agevolato (co. 65: anno di inizio + quattro
    # successivi), altre attivita' 67%: reddito 26.800, imponibile 23.800, imposta
    # 5% = 1.190,00.
    pytest.param(dict(ricavi=40000, coefficiente_redditivita=67, anni_attivita=5, contributi_inps=3000),
                 id="piano5-quinto-anno-5pct"),
    # Piano 5 bis - LIMITE: sesto anno, aliquota 15% (co. 64): imposta 3.570,00.
    pytest.param(dict(ricavi=40000, coefficiente_redditivita=67, anni_attivita=6, contributi_inps=3000),
                 id="piano5bis-sesto-anno-15pct"),
    # Extra - opzione enumerata: costruzioni e attivita' immobiliari 86% (allegato 4),
    # ottavo anno: reddito 25.800, imponibile 23.300, imposta 15% = 3.495,00.
    pytest.param(dict(ricavi=30000, coefficiente_redditivita=86, anni_attivita=8, contributi_inps=2500),
                 id="extra-costruzioni-86"),
    # Extra - opzione enumerata: commercio ambulante altri prodotti 54%, importi con
    # centesimi: reddito 10.800,27, imponibile 9.565,71, imposta 5% = 478,29
    # (478,2855 arrotondato al centesimo).
    pytest.param(dict(ricavi=20000.50, coefficiente_redditivita=54, anni_attivita=2, contributi_inps=1234.56),
                 id="extra-ambulante-54-centesimi"),
    # Extra - opzione enumerata: intermediari del commercio 62%, senza contributi:
    # reddito = imponibile 28.320,92, imposta 15% = 4.248,14.
    pytest.param(dict(ricavi=45678.91, coefficiente_redditivita=62, anni_attivita=7, contributi_inps=0),
                 id="extra-intermediari-62"),
    # Extra - LIMITE di arrotondamento: imponibile 37.765,10, imposta 5% esatta
    # 1.888,255 (mezzo centesimo): arrotondamento commerciale -> 1.888,26.
    pytest.param(dict(ricavi=50000, coefficiente_redditivita=78, anni_attivita=1, contributi_inps=1234.90),
                 id="extra-mezzo-centesimo-5pct"),
    # Extra - LIMITE di arrotondamento: stesso imponibile, imposta 15% esatta
    # 5.664,765 (mezzo centesimo) -> 5.664,77.
    pytest.param(dict(ricavi=50000, coefficiente_redditivita=78, anni_attivita=6, contributi_inps=1234.90),
                 id="extra-mezzo-centesimo-15pct"),
]


@pytest.mark.parametrize("args", CASI)
def test_regime_forfettario_vs_sito(page, args):
    tool = _tool(**args)
    assert "errore" not in tool, tool
    site = _site(
        page,
        SETTORE[int(args["coefficiente_redditivita"])],
        args["ricavi"],
        args["contributi_inps"],
        args["anni_attivita"] <= 5,
    )
    assert site["testo"], f"il sito non ha calcolato: {site['errore']!r}"
    ko = _confronta(tool, site)
    assert not ko, "\n".join(ko)


def test_oltre_limite_85000_01(page):
    """Piano 3 - LIMITE: ricavi 85.000,01 (un centesimo oltre il co. 54 lett. a).

    Atteso del piano: errore, oltre 85.000 euro. Il co. 54 riguarda i ricavi
    dell'anno precedente e il co. 71 fa cessare il regime dall'anno successivo
    (dallo stesso anno solo oltre 100.000): il tool non distingue, il sito nemmeno.
    Confronto: entrambi rifiutano il calcolo e indicano lo stesso limite.
    """
    tool = _tool(ricavi=85000.01, coefficiente_redditivita=78, anni_attivita=6)
    site = _site(page, SETTORE[78], 85000.01, 0, False)
    assert "errore" in tool, tool
    assert not site["testo"], f"il sito ha calcolato oltre il limite: {site['testo']!r}"
    assert site["limite_errore"] is not None, f"errore del sito non riconosciuto: {site['errore']!r}"
    assert tool["limite_ricavi"] == site["limite_errore"], (
        f"limite: tool={tool['limite_ricavi']} sito={site['limite_errore']}"
    )


# Extra - LIMITE: contributi (5.000) superiori al reddito forfettario (40% di
# 10.000 = 4.000), settore alloggio e ristorazione (40%), decimo anno. Co. 64:
# i contributi si deducono dal reddito forfettario e "l'eventuale eccedenza e'
# deducibile dal reddito complessivo" (art. 10 TUIR). Atteso: imposta 0,00.
_ECCEDENZA = dict(ricavi=10000, coefficiente_redditivita=40, anni_attivita=10, contributi_inps=5000)


def test_contributi_eccedenti_imposta(page):
    tool = _tool(**_ECCEDENZA)
    site = _site(page, "7", 10000, 5000, False)
    assert site["testo"], f"il sito non ha calcolato: {site['errore']!r}"
    assert site["aliquota"] == tool["aliquota_pct"], (tool["aliquota_pct"], site["aliquota"])
    assert abs(tool["imposta_sostitutiva"] - site["imposta"]) <= TOL_EUR, (
        f"imposta: tool={tool['imposta_sostitutiva']} sito={site['imposta']}"
    )


def test_contributi_eccedenti_imponibile(page):
    """Imponibile con contributi eccedenti: il tool lo porta a zero (max(...,0)),
    il sito espone il valore negativo (l'eccedenza).
    CONVENZIONE (fase 3): art. 1 c. 64 L. 190/2014 deduce i contributi dal reddito forfettario e
    rende "l'eventuale eccedenza" deducibile dal reddito complessivo (art. 10 TUIR). La base
    dell'imposta sostitutiva non puo' essere negativa: il tool la azzera, il sito mostra l'eccedenza
    (-1.000) come imponibile negativo. Le due rappresentazioni sono equivalenti, l'imposta e' 0,00
    in entrambi; si confronta quindi il tool con max(sito, 0).
    """
    tool = _tool(**_ECCEDENZA)
    site = _site(page, "7", 10000, 5000, False)
    assert site["testo"], f"il sito non ha calcolato: {site['errore']!r}"
    assert abs(tool["reddito_lordo"] - site["reddito_lordo"]) <= TOL_EUR, (
        f"reddito lordo: tool={tool['reddito_lordo']} sito={site['reddito_lordo']}"
    )
    assert abs(tool["reddito_imponibile"] - max(site["reddito_imponibile"], 0)) <= TOL_EUR, (
        f"reddito imponibile: tool={tool['reddito_imponibile']} sito={site['reddito_imponibile']}"
    )
