"""Benchmark fase 1: calcolo_imu vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-imu-nuova-ici.php
(/utility/calcolo-ici.php e' un duplicato interno della stessa pagina).

Modulo ``CalcoloImu`` (POST su ``./calcolo-imu-nuova-ici.php#Res``, campo nascosto
``anno=2026``). Campi usati: ``CategoriaCatastale`` (select: ``A`` = A/2-A/7,
``AL`` = A/1, A/8, A/9, ``A10``, ``B``, ``C1``..``C7``, ``D`` = gruppo D esclusi
D/5 e D/10, ``D5``, ``R1`` = D/10 rurale strumentale, ``R2``, ``AF``, ``T1``),
``AbitazionePrincipale`` (checkbox, abilitata solo per abitazioni e pertinenze),
``RenditaCatastale`` (rendita non rivalutata, virgola decimale), ``Aliquota``
(PER MILLE, campo vuoto = "aliquota base" del sito). Restano ai valori di default:
pertinenze vuote, quota di possesso 100% per 12 mesi, niente comodato ne' canone
concordato, detrazione 200,00 con un titolare. Pulsante ``#Calcola``.

Risultato: ``table.Boxed.result`` con le righe "Rendita catastale rivalutata al 5%",
"Imponibile complessivo immobile|prima casa", "Imposta lorda complessiva
( N per mille )", per la prima casa "Detrazione spettante" e "Imposta dovuta
( al netto della detrazione )" oppure il messaggio "Nessuna imposta dovuta";
infine "Imposta arrotondata all'euro" (arrotondamento del versamento F24, che il
tool non fa). Il sito non espone la rata semestrale (acconto): ``imu_semestrale``
del tool non e' confrontabile.

Driver: il banner CMP (qc-cmp2) viene rimosso via JS senza prestare consenso; la
spunta "prima casa" si imposta con ``checked`` + ``OnClickAbitazionePrincipale()``
(la funzione della pagina che abilita detrazione e pertinenze); l'invio usa
``form.requestSubmit(#Calcola)``. Pausa di 1,5 s prima di ogni richiesta.

Tool: ``calcolo_imu(rendita_catastale, categoria, aliquota_comunale=0.86,
prima_casa=False)`` (src/tools/proprieta_successioni.py): base = rendita x 1,05 x
moltiplicatore (L. 160/2019 art. 1 co. 745: 160 gruppo A e C/2, C/6, C/7; 140
gruppo B e C/3, C/4, C/5; 80 A/10 e D/5; 65 gruppo D; 55 C/1); imposta = base x
aliquota; abitazione principale esente salvo A/1, A/8, A/9 (co. 740), che hanno
la detrazione di 200 euro (co. 749).

Confronto (tool == sito, tolleranza 0,01 euro sugli importi e 0,0001 sull'aliquota
per mille, come da brief). Per ogni caso si confrontano rendita rivalutata, base
imponibile, aliquota applicata, detrazione (prima casa di lusso) e imposta dovuta;
il messaggio di errore elenca tutte le voci, OK e KO, cosi' la fase 2 vede quale
componente produce lo scostamento. Il sito e' un benchmark, non una fonte: un KO
resta un KO anche quando e' il sito a discostarsi dalla norma (vedi il caso
dell'aliquota base dell'abitazione principale di lusso).
"""

import json
import os
import re

import pytest

URL = "https://www.avvocatoandreani.it/servizi/calcolo-imu-nuova-ici.php"
TOL_EUR = 0.01
TOL_PM = 0.0001
# Rumore della rappresentazione binaria dei float: una differenza di esattamente
# 0,01 euro puo' valere 0,010000000000218 in virgola mobile. Non allarga la
# tolleranza del brief (0,01), evita solo falsi KO sul confine.
_EPS = 1e-9


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  (registra i moduli, evita import circolari)
    from src.tools.proprieta_successioni import calcolo_imu

    fn = getattr(calcolo_imu, "fn", calcolo_imu)
    return fn(**kwargs)


def _site_category(categoria: str) -> str:
    """Categoria catastale del tool -> valore della select ``CategoriaCatastale``."""
    c = categoria.upper().strip()
    if c in ("A/1", "A/8", "A/9"):
        return "AL"
    if c == "A/10":
        return "A10"
    if c.startswith("A/"):
        return "A"
    if c.startswith("B"):
        return "B"
    if c.startswith("C/"):
        return "C" + c[2:]
    if c == "D/5":
        return "D5"
    if c == "D/10":
        return "R1"
    if c.startswith("D"):
        return "D"
    raise ValueError(f"categoria non mappata sul sito: {categoria}")


def _per_mille(aliquota_pct: float | None) -> str:
    """Aliquota del tool (percentuale) -> campo ``Aliquota`` del sito (per mille)."""
    if aliquota_pct is None:
        return ""  # campo vuoto = aliquota base del sito
    s = f"{round(aliquota_pct * 10, 4):.4f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _eur(text: str) -> float:
    return float(text.replace("€", "").strip().replace(".", "").replace(",", "."))


def _remove_cmp(page):
    page.evaluate(
        'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container")'
        ".forEach(el => el.remove())"
    )


def _site(page, categoria: str, rendita: float, aliquota_pct: float | None,
          prima_casa: bool = False) -> dict:
    """Compila il modulo, invia e legge la tabella dei risultati."""
    page.wait_for_timeout(1500)  # cura del sito: pausa tra le richieste
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    _remove_cmp(page)
    page.select_option("#CategoriaCatastale", _site_category(categoria))
    page.evaluate(
        "(v) => { const e = document.getElementById('AbitazionePrincipale');"
        " if (!e.disabled) { e.checked = v; } OnClickAbitazionePrincipale(); }",
        prima_casa,
    )
    page.fill("#RenditaCatastale", f"{rendita:.2f}".replace(".", ","))
    page.fill("#Aliquota", _per_mille(aliquota_pct))
    # La pagina abilita la spunta solo per abitazioni (A, AL) e pertinenze (C2,
    # C6, C7): per le altre categorie resta disabilitata e il sito calcola
    # l'imposta ordinaria.
    enabled = page.evaluate("!document.getElementById('AbitazionePrincipale').disabled")
    checked = page.evaluate("document.getElementById('AbitazionePrincipale').checked")
    if enabled:
        assert checked == prima_casa, "spunta 'prima casa' non impostata sul sito"
    page.evaluate(
        "document.getElementById('CalcoloImu')"
        ".requestSubmit(document.getElementById('Calcola'))"
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    _remove_cmp(page)

    table = page.query_selector("table.Boxed.result")
    assert table is not None, "il sito non ha prodotto la tabella dei risultati"
    rows = page.evaluate(
        """(t) => Array.from(t.querySelectorAll('tr')).map(tr =>
               Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()))
           .filter(cells => cells.some(c => c.startsWith('€')))
           .map(cells => [cells.filter(c => c && !c.startsWith('€')).join(' '),
                          cells.find(c => c.startsWith('€'))])""",
        table,
    )
    text = table.inner_text()
    out = {"righe": rows, "testo": " ".join(text.split()),
           "prima_casa_abilitata": enabled, "prima_casa_spuntata": checked}
    for label, value in rows:
        lab = " ".join(label.split())
        amount = _eur(value)
        if lab.startswith("Rendita catastale rivalutata"):
            out["rendita_rivalutata"] = amount
        elif lab.startswith("Imponibile complessivo"):
            out["base_imponibile"] = amount
        elif lab.startswith("Imposta lorda complessiva"):
            out["imposta_lorda"] = amount
            m = re.search(r"\(\s*([\d.,]+)\s*per mille\s*\)", lab)
            if m:
                out["aliquota_per_mille"] = float(m.group(1).replace(",", "."))
        elif lab.startswith("Detrazione spettante"):
            out["detrazione"] = amount
        elif lab.startswith("Detrazione residua"):
            out["detrazione_residua"] = amount
        elif lab.startswith("Imposta dovuta"):
            out["imposta_dovuta"] = amount
        elif lab.startswith("Imposta teorica"):
            out["imposta_teorica"] = amount
        elif lab.startswith("Imposta arrotondata"):
            out["imposta_arrotondata_euro"] = amount
    if "imposta_dovuta" not in out:
        if "Nessuna imposta dovuta" in text:
            out["imposta_dovuta"] = 0.0
        else:
            out["imposta_dovuta"] = out.get("imposta_lorda")
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _dump(case: str, kwargs: dict, tool: dict, site: dict):
    """Registra i valori letti se BENCH_DUMP punta a un file (solo per il report)."""
    path = os.environ.get("BENCH_DUMP")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"caso": case, "input": kwargs, "tool": tool,
                             "sito": site}, ensure_ascii=False) + "\n")


def _run(page, case: str, kwargs: dict, *, site_aliquota="same",
         check_detrazione: bool = False):
    """Esegue tool e sito sullo stesso caso e confronta voce per voce.

    ``site_aliquota="same"`` passa al sito l'aliquota del tool convertita in per
    mille; ``None`` lascia il campo vuoto (aliquota base del sito) e si usa quando
    il tool gira con il suo default.
    """
    tool = _tool(**kwargs)
    assert "errore" not in tool, tool
    aliquota = kwargs.get("aliquota_comunale") if site_aliquota == "same" else site_aliquota
    site = _site(page, kwargs["categoria"], kwargs["rendita_catastale"], aliquota,
                 kwargs.get("prima_casa", False))
    _dump(case, kwargs, tool, site)

    checks = [
        ("rendita rivalutata", tool["rendita_rivalutata"], site.get("rendita_rivalutata"), TOL_EUR),
        ("base imponibile", tool["base_imponibile"], site.get("base_imponibile"), TOL_EUR),
        ("aliquota per mille", round(tool["aliquota_comunale_pct"] * 10, 6),
         site.get("aliquota_per_mille"), TOL_PM),
        ("imposta dovuta", tool["imu_annua"], site.get("imposta_dovuta"), TOL_EUR),
    ]
    if check_detrazione:
        checks.append(("detrazione", tool.get("detrazione_prima_casa", 0.0),
                       site.get("detrazione"), TOL_EUR))

    report, ko = [], False
    if kwargs.get("prima_casa"):
        report.append("spunta prima casa sul sito: "
                      + ("spuntata" if site["prima_casa_spuntata"] else
                         "disabilitata per questa categoria"))
    for label, t, s, tol in checks:
        if s is None:
            report.append(f"{label}: tool={t} sito=ASSENTE KO")
            ko = True
            continue
        ok = abs(t - s) <= tol + _EPS
        ko |= not ok
        report.append(f"{label}: tool={t} sito={s} diff={abs(t - s):.4f} {'OK' if ok else 'KO'}")
    assert not ko, f"{case}: " + " | ".join(report) + f" || sito: {site['testo']}"
    return tool, site


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_caso1_a2_non_principale_aliquota_massima(page):
    """Piano: base 1.000 x 1,05 x 160 = 168.000 (co. 745); IMU 1.780,80; acconto 890,40.

    L. 160/2019 art. 1 co. 745 (moltiplicatore 160, rivalutazione 5%), co. 755
    (aliquota massima 1,06%). L'acconto non e' esposto dal sito.
    """
    _run(page, "A/2 non principale 10,6 per mille",
         {"rendita_catastale": 1000, "categoria": "A/2", "aliquota_comunale": 1.06,
          "prima_casa": False})


def test_caso2_a1_principale_di_lusso(page):
    """Piano: base 252.000; 0,6% = 1.512 meno detrazione 200 (co. 749) = 1.312,00.

    L. 160/2019 art. 1 co. 740 (A/1, A/8, A/9 non esenti), co. 748 (aliquota),
    co. 749 (detrazione 200 euro).
    """
    _run(page, "A/1 prima casa 6 per mille",
         {"rendita_catastale": 1500, "categoria": "A/1", "aliquota_comunale": 0.6,
          "prima_casa": True}, check_detrazione=True)


def test_caso3_c1_negozio(page):
    """Piano: base 840 x 55 = 46.200; IMU 397,32. L. 160/2019 art. 1 co. 745 (C/1: 55)."""
    _run(page, "C/1 negozio 8,6 per mille",
         {"rendita_catastale": 800, "categoria": "C/1", "aliquota_comunale": 0.86,
          "prima_casa": False})


def test_caso4_d1_capannone(page):
    """Piano: base 341.250 (moltiplicatore 65); IMU 2.934,75, di cui 2.593,50 allo
    Stato (0,76%, co. 753): il tool non separa la quota.

    L. 160/2019 art. 1 co. 745 (gruppo D: 65), co. 753 (quota statale 0,76%). Anche
    il sito espone solo l'imposta complessiva: la quota statale non e' confrontabile.
    """
    _run(page, "D/1 capannone 8,6 per mille",
         {"rendita_catastale": 5000, "categoria": "D/1", "aliquota_comunale": 0.86})


def test_caso5_a2_principale_esente(page):
    """Piano: 0,00 (esenzione, co. 740).

    Tool con aliquota di default, sito con il campo aliquota vuoto: per le
    abitazioni principali A/2-A/7 il sito calcola un'imposta "teorica" al 4 per
    mille meno la detrazione e poi dichiara "Nessuna imposta dovuta"; l'aliquota
    esposta (4 per mille) non si confronta perche' l'immobile e' esente e il tool
    riporta l'aliquota di default non applicata. Si confrontano rendita
    rivalutata, base imponibile e imposta dovuta (zero).
    """
    kwargs = {"rendita_catastale": 700, "categoria": "A/2", "prima_casa": True}
    tool = _tool(**kwargs)
    site = _site(page, "A/2", 700, None, prima_casa=True)
    _dump("A/2 prima casa esente", kwargs, tool, site)
    report, ko = [], False
    for label, t, s in [
        ("rendita rivalutata", tool["rendita_rivalutata"], site.get("rendita_rivalutata")),
        ("base imponibile", tool["base_imponibile"], site.get("base_imponibile")),
        ("imposta dovuta", tool["imu_annua"], site.get("imposta_dovuta")),
    ]:
        ok = s is not None and abs(t - s) <= TOL_EUR + _EPS
        ko |= not ok
        report.append(f"{label}: tool={t} sito={s} {'OK' if ok else 'KO'}")
    assert not ko, " | ".join(report) + f" || sito: {site['testo']}"


def test_caso6_c6_pertinenza_non_principale(page):
    """Piano: base 200 x 1,05 x 160 = 33.600; IMU 356,16. L. 160/2019 art. 1 co. 745."""
    _run(page, "C/6 non principale 10,6 per mille",
         {"rendita_catastale": 200, "categoria": "C/6", "aliquota_comunale": 1.06})


# ---------------------------------------------------------------------------
# Casi al limite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "categoria, moltiplicatore",
    [
        ("A/10", 80),   # co. 745 lett. d)
        ("B/1", 140),   # co. 745 lett. b)
        ("C/2", 160),   # co. 745 lett. a)
        ("C/3", 140),   # co. 745 lett. b)
        ("C/4", 140),   # co. 745 lett. b)
        ("C/5", 140),   # co. 745 lett. b)
        ("C/7", 160),   # co. 745 lett. a)
        ("D/5", 80),    # co. 745 lett. c)
    ],
)
def test_limite_moltiplicatori_enumerati(page, categoria, moltiplicatore):
    """Opzione enumerata: ogni moltiplicatore del co. 745 L. 160/2019 (80/140/160)
    sulle categorie che il tool mappa per eccezione. Rendita 1.000, 8,6 per mille:
    atteso base 1.050 x moltiplicatore e imposta = base x 0,86%."""
    tool, _ = _run(page, f"{categoria} moltiplicatore {moltiplicatore}",
                   {"rendita_catastale": 1000, "categoria": categoria,
                    "aliquota_comunale": 0.86})
    assert tool["moltiplicatore"] == moltiplicatore


def test_limite_d10_rurale_strumentale(page):
    """Opzione enumerata: D/10 fabbricato rurale strumentale (voce R1 del sito).
    L. 160/2019 art. 1 co. 745 (gruppo D: 65) e co. 750 (aliquota base 0,1%).
    Atteso: base 5.000 x 1,05 x 65 = 341.250; IMU 341,25.

    Il sito, con aliquota 1 per mille sulla voce R1, non produce alcun risultato
    (accetta 2 per mille, che e' anche la sua aliquota base: D.L. 201/2011 art. 13
    co. 8, non piu' vigente; il co. 750 L. 160/2019 fissa il massimo allo 0,1%).
    In quel caso il test si salta come "sito non calcola"."""
    try:
        _run(page, "D/10 rurale strumentale 1 per mille",
             {"rendita_catastale": 5000, "categoria": "D/10", "aliquota_comunale": 0.1})
    except AssertionError as exc:
        if "non ha prodotto la tabella" in str(exc):
            pytest.skip("sito non calcola: nessun risultato per D/10 (R1) con "
                        "aliquota 1 per mille (co. 750 L. 160/2019); accetta solo 2 per mille")
        raise


def test_limite_detrazione_maggiore_imposta(page):
    """Confine della detrazione: A/1 abitazione principale con imposta lorda (84,00)
    inferiore alla detrazione di 200 euro (co. 749): imposta dovuta zero, mai
    negativa. Rendita 100 al 5 per mille (aliquota base co. 748)."""
    _run(page, "A/1 prima casa detrazione > imposta",
         {"rendita_catastale": 100, "categoria": "A/1", "aliquota_comunale": 0.5,
          "prima_casa": True}, check_detrazione=True)


def test_limite_rendita_con_decimali(page):
    """Arrotondamento della rendita rivalutata: 987,65 x 1,05 = 1.037,0325.
    Se si arrotonda la rendita rivalutata al centesimo prima del moltiplicatore la
    base e' 165.924,80, altrimenti 165.925,20 (co. 745 non prescrive arrotondamenti
    intermedi). Atteso del tool: base 165.925,20, IMU 1.758,81 al 10,6 per mille."""
    _run(page, "A/2 rendita con decimali",
         {"rendita_catastale": 987.65, "categoria": "A/2", "aliquota_comunale": 1.06})


def test_limite_terzo_decimale_cinque(page):
    """Arrotondamento al centesimo con terzo decimale 5: C/1 rendita 500, base
    28.875, imposta esatta 248,325 al 8,6 per mille. Il sito dichiara
    l'arrotondamento commerciale (per eccesso da 5 a 9: 248,33); il tool usa
    round() di Python sul float (248,32). Differenza attesa 0,01 = tolleranza."""
    _run(page, "C/1 terzo decimale 5",
         {"rendita_catastale": 500, "categoria": "C/1", "aliquota_comunale": 0.86})


def test_limite_aliquota_default_non_principale(page):
    """Opzione di default: tool senza aliquota (0,86%) contro campo vuoto del sito
    (aliquota base). L. 160/2019 art. 1 co. 754: aliquota base 0,86% per gli
    immobili diversi dall'abitazione principale. Atteso 168.000 x 0,86% = 1.444,80."""
    _run(page, "A/2 aliquota di default",
         {"rendita_catastale": 1000, "categoria": "A/2"}, site_aliquota=None)


def test_limite_aliquota_default_principale_di_lusso(page):
    """Opzione di default: A/1 abitazione principale senza aliquota.

    Norma: L. 160/2019 art. 1 co. 748, aliquota base 0,5% per l'abitazione
    principale A/1, A/8, A/9 -> 252.000 x 0,5% = 1.260 - 200 = 1.060,00.
    Il tool applica il suo default 0,86% (1.967,20; la nota del piano: "passare
    sempre l'aliquota"); il sito applica il 4 per mille (808,00), che e' l'aliquota
    base della vecchia IMU (D.L. 201/2011 art. 13 co. 7), non quella vigente.
    Nessuno dei due coincide con la norma: il test resta tool == sito."""
    _run(page, "A/1 prima casa aliquota di default",
         {"rendita_catastale": 1500, "categoria": "A/1", "prima_casa": True},
         site_aliquota=None, check_detrazione=True)


def test_non_confrontabile_canone_concordato(page):
    """Riduzione al 75% per le abitazioni locate a canone concordato (L. 160/2019
    art. 1 co. 760): il sito la offre (campo ImmobileCanoneConcordato), il tool no.
    Lo stesso vale per comodato ai parenti in linea retta (co. 747 lett. c),
    quota e mesi di possesso e pertinenze della prima casa."""
    pytest.skip(
        "non confrontabile: il tool non gestisce la riduzione del 25% per canone "
        "concordato (co. 760), il comodato (co. 747), quota/mesi di possesso e "
        "pertinenze, che il sito offre"
    )
