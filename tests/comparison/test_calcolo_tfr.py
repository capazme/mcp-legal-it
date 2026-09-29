"""Benchmark fase 1: calcolo_tfr vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-tfr.php
Riscontro secondario: https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php

Modulo ``CalcoloTfr`` (POST). Campi: date di inizio e cessazione del rapporto
(select ``GiornoInizio/MeseInizio/AnnoInizio`` e ``GiornoFine/MeseFine/AnnoFine``);
alla scelta delle date il JS della pagina crea una riga per anno solare
(``AnnoRetr-i``, ``ValutaRetr-i``, ``ImpRetr-i`` = retribuzione utile per il TFR,
``ImpPrev-i`` = imponibile previdenziale, sbloccato solo con la spunta
``ContributoIVS``; contatore ``NumRetribuzioni``). Pulsante ``#btn-calc``.
Risultati: ``table.tfr`` (ricostruzione del fondo anno per anno: TFR base, quota
IVS, TFR al netto di IVS, coefficiente, rivalutazione, imposta sostitutiva, fondo,
riga TOT.) e ``table.riepilogo`` (mesi utili, reddito di riferimento, aliquota
media, imponibile, imposta lorda, detrazioni, imposta netta, TFR netto).

Driver: il banner CMP (qc-cmp2) compare in ritardo e intercetta i click, per cui
viene rimosso via JS prima di ogni interazione (nessun consenso prestato); l'invio
usa ``form.requestSubmit(#btn-calc)``, perche' il click forzato colpiva l'overlay;
la spunta IVS si imposta con ``checked = true`` + ``App.OnClickContributoIVS()``
(la funzione della pagina che sblocca ``ImpPrev``), perche' il click nativo sulla
checkbox non ne cambia lo stato.

Tool: ``calcolo_tfr(retribuzione_annua_lorda, anni_servizio, rivalutazione_media_pct)``
(src/tools/dichiarazione_redditi.py). Quota annua = retribuzione / 13,5 (art. 2120
co. 1 c.c.); rivalutazione composta al tasso costante 1,5% + 75% del FOI medio
(art. 2120 co. 4 c.c.); reddito di riferimento = TFR lordo x 12 / anni; imposta =
TFR lordo x aliquota media IRPEF calcolata con gli scaglioni dell'anno corrente
(LEGAL_TODAY pinnato al 2026-09-25 -> scaglioni 2026: 23% / 33% / 43%).

Il sito (art. 2120 c.c., art. 3 L. 297/1982, art. 11 D.Lgs. 47/2000, art. 19 TUIR):
- sottrae, se richiesto, il contributo IVS 0,50% dell'imponibile previdenziale
  (art. 3 co. 15-16 L. 297/1982);
- rivaluta con i coefficienti ISTAT reali mese per mese, con la parte variabile
  azzerata se l'indice FOI scende (dicembre 2020: coefficiente 1,5%);
- trattiene l'imposta sostitutiva sulle rivalutazioni (17% dal 2015, art. 11 co. 3
  D.Lgs. 47/2000) dal fondo;
- calcola il reddito di riferimento come (fondo - rivalutazioni lorde) x 144 / mesi
  utili (art. 19 co. 1 TUIR: TFR "al netto delle rivalutazioni gia' assoggettate ad
  imposta sostitutiva"); per rapporti inferiori all'anno usa fondo x 12;
- dichiara di usare gli scaglioni dell'anno di cessazione (art. 19 co. 1 TUIR:
  "anno in cui e' maturato il diritto alla percezione") con la clausola di
  salvaguardia delle aliquote vigenti al 31/12/2006 se piu' favorevoli (finanziaria
  2007, come descritta dal sito). Osservato il 2026-09-25: per cessazioni nel 2026
  applica ancora gli scaglioni 2025 (23% / 35% / 43%: aliquota 25,67% su RR 36.000,
  36,87% su RR 120.000) e su RR 120.000 non applica la clausola 2006 (35,83%);
- arrotonda l'aliquota media a due decimali prima di applicarla (3.000 x 25,67% =
  770,10), mentre il tool applica l'aliquota non arrotondata;
- applica detrazioni: 61,97 euro annui rapportati ai mesi per rapporti inferiori a
  due anni (art. 19 co. 1-ter TUIR, che pero' la norma riserva ai rapporti a tempo
  determinato) piu' una detrazione decrescente col reddito di riferimento che il
  sito attribuisce alla finanziaria 2008.

Confronto (tool == sito, tolleranza 0,01 euro; aliquota media alla precisione
esposta da entrambi, due decimali, tolleranza 0,0001 come da brief). Per ogni caso
si confrontano: fondo TFR (tool ``tfr_lordo``), TFR lordo ante imposta sostitutiva
(solo se il sito calcola rivalutazioni), reddito di riferimento, aliquota media,
imposta ante detrazioni, imposta dovuta dopo le detrazioni (il tool espone una
sola ``imposta``), TFR netto. Il messaggio di errore elenca tutte le voci, OK e KO,
cosi' la fase 2 vede quale componente produce lo scostamento. Il sito e' un
benchmark, non una fonte: i test restano tool == sito e un KO resta un KO.

Casi non confrontabili (pytest.skip con i valori letti): rapporti pluriennali con
FOI medio costante (casi 2 e 3 del piano), perche' il sito usa gli indici ISTAT reali
anno per anno e non accetta un FOI medio. Per rendere confrontabile la rivalutazione
si usano rapporti di due anni con il FOI reale dell'unico anno rivalutato (indici
FOI letti il 2026-09-25 sulla pagina dei coefficienti).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo-tfr.php"
TOL_EUR = 0.01
TOL_PCT = 0.0001

# Indici FOI ISTAT (base 2015=100) mostrati da coefficienti-rivalutazione-tfr.php
# il 2026-09-25: dicembre 2024 = 120,2, dicembre 2025 = 121,5 (coefficiente TFR
# dicembre 2025 = 2,311148%); dicembre 2019 = 102,5, dicembre 2020 = 102,3
# (variazione negativa, coefficiente dicembre 2020 = 1,5%).
FOI_DIC_2025 = (121.5 / 120.2 - 1) * 100  # +1,081531%
FOI_DIC_2020 = (102.3 / 102.5 - 1) * 100  # -0,195122%

_RM_CMP = (
    'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container")'
    ".forEach(el => el.remove())"
)

_SITE_CACHE: dict = {}


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    # Il tool legge gli scaglioni IRPEF dell'anno corrente: pinnati al 2026.
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-25")


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(**kwargs) -> dict:
    import importlib

    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)

    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod.calcolo_tfr, "fn", mod.calcolo_tfr)
    return fn(**kwargs)


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _fmt(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _num(cell: str) -> float:
    cell = cell.strip()
    if cell in ("", "-"):
        return 0.0
    return parse_euro(cell)


def _pct(cell: str) -> float:
    cell = cell.strip().replace("%", "").strip()
    if cell in ("", "-"):
        return 0.0
    return float(cell.replace(".", "").replace(",", "."))


def _open(page):
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    page.evaluate(_RM_CMP)


def _set_dates(page, inizio: str, fine: str):
    gi, mi, ai = inizio.split("/")
    gf, mf, af = fine.split("/")
    for name, val in (("GiornoInizio", gi), ("MeseInizio", mi), ("AnnoInizio", ai),
                      ("GiornoFine", gf), ("MeseFine", mf), ("AnnoFine", af)):
        page.select_option(f"#{name}", val)
        page.wait_for_timeout(150)
    page.wait_for_timeout(800)


def _site(page, inizio: str, fine: str, retribuzioni: list[float],
          imponibili: list[float] | None = None) -> dict:
    """Guida calcolo-tfr.php e restituisce ricostruzione del fondo e riepilogo."""
    key = (inizio, fine, tuple(retribuzioni), tuple(imponibili) if imponibili else None)
    if key in _SITE_CACHE:
        return _SITE_CACHE[key]

    _open(page)
    if imponibili is not None:
        page.evaluate("document.getElementById('ContributoIVS').checked = true")
    _set_dates(page, inizio, fine)
    if imponibili is not None:
        page.evaluate("App.OnClickContributoIVS()")

    n = int(page.input_value("#NumRetribuzioni"))
    anni = [page.input_value(f"#AnnoRetr-{i}") for i in range(n)]
    assert n == len(retribuzioni), f"righe retribuzione attese {len(retribuzioni)}, sito {n} ({anni})"
    for i in range(n):
        page.fill(f"#ImpRetr-{i}", _fmt(retribuzioni[i]))
        if imponibili is not None:
            page.fill(f"#ImpPrev-{i}", _fmt(imponibili[i]))

    page.evaluate(_RM_CMP)
    page.evaluate(
        "document.getElementById('CalcoloTfr')"
        ".requestSubmit(document.getElementById('btn-calc'))"
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector("table.riepilogo", timeout=30000)

    sviluppo = page.inner_text("table.tfr").strip()
    riepilogo = page.inner_text("table.riepilogo").strip()

    out: dict = {"anni": anni, "coeff": {}}
    for row in sviluppo.split("\n"):
        cols = row.split("\t")
        head = cols[0].strip()
        if re.fullmatch(r"\d{4}", head):
            out["coeff"][int(head)] = _pct(cols[4])
        elif head.startswith("TOT"):
            out["tfr_base"] = _num(cols[1])
            out["quota_ivs"] = _num(cols[2])
            out["tfr_netto_ivs"] = _num(cols[3])
            out["rivalutazioni"] = _num(cols[5])
            out["imposta_sostitutiva"] = _num(cols[6])
            out["fondo"] = _num(cols[7])

    for row in riepilogo.split("\n"):
        if "\t" not in row:
            continue
        label, val = (x.strip() for x in row.split("\t", 1))
        label = label.rstrip(":")
        if label.startswith("Mesi utili"):
            out["mesi"] = int(val)
        elif label.startswith("Reddito di riferimento"):
            out["reddito_riferimento"] = parse_euro(val)
        elif label.startswith("Aliquota media"):
            out["aliquota"] = _pct(val)
        elif label.startswith("Imponibile fiscale"):
            out["imponibile"] = parse_euro(val)
        elif label.startswith(("Imposta lorda calcolata", "Imposta calcolata")):
            # senza detrazioni il sito stampa solo "Imposta calcolata (x% ...)"
            out["imposta_lorda"] = parse_euro(val)
        elif label.startswith("Totale detrazioni"):
            out["detrazioni"] = parse_euro(val)
        elif label.startswith("Imposta al netto"):
            out["imposta_netta"] = parse_euro(val)
        elif label.startswith("TFR Netto"):
            out["tfr_netto"] = parse_euro(val)
    out.setdefault("detrazioni", 0.0)
    if "imposta_lorda" in out:
        out.setdefault("imposta_netta", out["imposta_lorda"])
    for k in ("fondo", "reddito_riferimento", "aliquota", "imposta_lorda",
              "imposta_netta", "tfr_netto"):
        assert k in out, f"voce '{k}' non trovata nel risultato del sito:\n{sviluppo}\n{riepilogo}"

    page.wait_for_timeout(1500)  # cortesia verso il sito tra una richiesta e l'altra
    _SITE_CACHE[key] = out
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _righe(t: dict, s: dict) -> list[tuple[str, float, float, float]]:
    ts = t["tassazione_separata"]
    righe = [("fondo TFR (tool tfr_lordo)", t["tfr_lordo"], s["fondo"], TOL_EUR)]
    if s["rivalutazioni"] > 0:
        righe.append(("TFR ante imposta sostitutiva (accantonamenti + rivalutazioni lorde)",
                      t["tfr_lordo"], s["tfr_netto_ivs"] + s["rivalutazioni"], TOL_EUR))
    righe += [
        ("reddito di riferimento", ts["reddito_riferimento"], s["reddito_riferimento"], TOL_EUR),
        ("aliquota media %", ts["aliquota_media_pct"], s["aliquota"], TOL_PCT),
        ("imposta ante detrazioni", ts["imposta"], s["imposta_lorda"], TOL_EUR),
        ("imposta dovuta (dopo detrazioni)", ts["imposta"], s["imposta_netta"], TOL_EUR),
        ("TFR netto", t["tfr_netto"], s["tfr_netto"], TOL_EUR),
    ]
    return righe


def _confronta(caso: str, t: dict, s: dict):
    assert "errore" not in t, t
    righe = _righe(t, s)
    report = []
    ko = []
    for label, vt, vs, tol in righe:
        ok = abs(vt - vs) <= tol + 1e-9
        report.append(f"  {'OK' if ok else 'KO'} {label}: tool={vt:.4f} sito={vs:.4f} diff={vt - vs:+.4f}")
        if not ok:
            ko.append(label)
    extra = (f"  (sito: rivalutazioni {s['rivalutazioni']:.2f}, imposta sostitutiva "
             f"{s['imposta_sostitutiva']:.2f}, quota IVS {s['quota_ivs']:.2f}, "
             f"detrazioni {s.get('detrazioni', 0):.2f}, mesi utili {s.get('mesi')})")
    testo = f"[{caso}]\n" + "\n".join(report) + "\n" + extra
    print(testo)
    assert not ko, f"scostamenti tool vs sito su {ko}\n{testo}"


def _riassunto(t: dict, s: dict) -> str:
    ts = t["tassazione_separata"]
    return (f"tool: lordo {t['tfr_lordo']:.2f}, RR {ts['reddito_riferimento']:.2f}, "
            f"aliquota {ts['aliquota_media_pct']}%, imposta {ts['imposta']:.2f}, "
            f"netto {t['tfr_netto']:.2f} | sito: fondo {s['fondo']:.2f} (base "
            f"{s['tfr_base']:.2f} + rivalutazioni {s['rivalutazioni']:.2f} - imposta "
            f"sostitutiva {s['imposta_sostitutiva']:.2f}), RR {s['reddito_riferimento']:.2f}, "
            f"aliquota {s['aliquota']}%, imposta lorda {s['imposta_lorda']:.2f}, "
            f"detrazioni {s.get('detrazioni', 0):.2f}, imposta {s['imposta_netta']:.2f}, "
            f"netto {s['tfr_netto']:.2f}")


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_piano_27000_un_anno_2025(page):
    """Piano, caso 1: 27.000 euro, un anno (01/01-31/12/2025), senza IVS.
    Atteso (piano): quota 27.000 / 13,5 = 2.000,00 (art. 2120 co. 1 c.c.); reddito di
    riferimento 24.000, aliquota 23%, imposta 460,00 (art. 19 TUIR). Il piano indica
    anche il contributo 0,50% (art. 3 L. 297/1982): qui il sito e' senza spunta IVS,
    il caso con IVS e' il test successivo. Il sito aggiunge detrazioni d'imposta."""
    t = _tool(retribuzione_annua_lorda=27000, anni_servizio=1)
    s = _site(page, "01/01/2025", "31/12/2025", [27000])
    _confronta("27000 x 1 anno 2025", t, s)


def test_piano_27000_un_anno_2025_con_contributo_ivs(page):
    """Piano, caso 1 con l'opzione enumerata ContributoIVS (caso al limite):
    imponibile previdenziale 27.000. Atteso (piano): 2.000 - 0,50% x 27.000 = 1.865,00
    (art. 3 co. 15-16 L. 297/1982); reddito di riferimento 22.380, aliquota 23%, imposta
    428,95. Il tool non ha l'opzione e resta a 2.000 / 460."""
    t = _tool(retribuzione_annua_lorda=27000, anni_servizio=1)
    s = _site(page, "01/01/2025", "31/12/2025", [27000], imponibili=[27000])
    _confronta("27000 x 1 anno 2025 con IVS", t, s)


def test_piano_30000_dieci_anni_foi_2(page):
    """Piano, caso 2: 30.000 euro x 10 anni, FOI medio 2% (tasso 3%).
    Atteso (piano): da leggere dal sito con dieci anni di retribuzione costante
    (01/01/2016-31/12/2025); tool 25.475,29 senza contributo IVS ne' imposta
    sostitutiva 17% (art. 11 co. 3 D.Lgs. 47/2000), quindi sito inferiore.
    Non confrontabile: il sito rivaluta con i coefficienti ISTAT reali 2017-2025, il
    tool con un FOI medio costante che il sito non accetta."""
    t = _tool(retribuzione_annua_lorda=30000, anni_servizio=10, rivalutazione_media_pct=2.0)
    s = _site(page, "01/01/2016", "31/12/2025", [30000] * 10)
    assert "errore" not in t, t
    pytest.skip("non confrontabile (FOI medio 2% vs indici ISTAT reali): " + _riassunto(t, s))


def test_piano_60000_venti_anni_foi_0(page):
    """Piano, caso 3: 60.000 euro x 20 anni, FOI nullo (solo 1,5% fisso, art. 2120
    co. 4 c.c.). Atteso (piano): da leggere dal sito; tool lordo 102.771,85 e imposta
    31.191,90 calcolata anche sulle rivalutazioni (art. 19 co. 1 TUIR le esclude).
    Non confrontabile: nel periodo 2006-2025 il FOI non e' mai nullo per vent'anni; la
    variante confrontabile (anno con FOI in calo) e' test_limite_foi_nullo_2019_2020."""
    t = _tool(retribuzione_annua_lorda=60000, anni_servizio=20, rivalutazione_media_pct=0)
    s = _site(page, "01/01/2006", "31/12/2025", [60000] * 20)
    assert "errore" not in t, t
    pytest.skip("non confrontabile (FOI 0 costante vs indici ISTAT reali): " + _riassunto(t, s))


def test_piano_anni_servizio_zero(page):
    """Piano, caso 4: anni di servizio nulli. Atteso (piano): errore di validazione.
    Sul sito l'equivalente e' una data di inizio uguale alla cessazione: il JS rifiuta
    con 'La data iniziale deve essere anteriore alla data di cessazione del rapporto'
    e non crea righe di retribuzione (nessun invio)."""
    t = _tool(retribuzione_annua_lorda=30000, anni_servizio=0)
    _open(page)
    _set_dates(page, "31/12/2025", "31/12/2025")
    err = page.inner_text("#Err_GiornoInizio") if page.query_selector("#Err_GiornoInizio") else ""
    righe = int(page.input_value("#NumRetribuzioni"))
    page.wait_for_timeout(1000)
    assert "errore" in t, f"il tool non rifiuta anni_servizio=0: {t}"
    assert "anteriore" in err and righe == 0, f"il sito non rifiuta: err={err!r}, righe={righe}"


# ---------------------------------------------------------------------------
# Casi al limite
# ---------------------------------------------------------------------------

def test_limite_foi_nullo_2019_2020(page):
    """Caso al limite (variante confrontabile del caso 3): rapporto 01/01/2019-
    31/12/2020, 13.500 euro l'anno (quota 1.000). Il FOI scende (102,5 -> 102,3), la
    parte variabile si azzera e il coefficiente di dicembre 2020 e' 1,5% (art. 2120
    co. 4 c.c.: 75% "dell'aumento" dell'indice): tool con rivalutazione_media_pct=0.
    Atteso per legge: rivalutazione 15,00, imposta sostitutiva 17% = 2,55 (art. 11
    co. 3 D.Lgs. 47/2000), fondo 2.012,45; reddito di riferimento (2.012,45 - 15,00)
    x 12 = 11.984,70 (art. 19 co. 1 TUIR); aliquota 23% (scaglioni 2020 e 2026
    coincidono sotto 15.000). Tool: lordo 2.015,00, RR 12.090, imposta 463,45."""
    t = _tool(retribuzione_annua_lorda=13500, anni_servizio=2, rivalutazione_media_pct=0)
    s = _site(page, "01/01/2019", "31/12/2020", [13500, 13500])
    assert s["coeff"].get(2020) == pytest.approx(1.5, abs=1e-6), f"precondizione: coefficiente 2020 {s['coeff']}"
    _confronta("13500 x 2 anni 2019-2020, FOI 0", t, s)


def test_limite_foi_negativo_reale_2019_2020(page):
    """Caso al limite: stesso rapporto, ma al tool si passa il FOI reale del 2020
    (-0,195122%, indici 102,5 -> 102,3). Per legge (art. 2120 co. 4 c.c.) la parte
    variabile e' il 75% dell'aumento, quindi zero se l'indice cala: tasso 1,5%,
    rivalutazione 15,00 come nel caso precedente. Il tool non azzera la parte
    negativa: tasso 1,5 - 0,75 x 0,195122 = 1,353659%, lordo 2.013,54."""
    t = _tool(retribuzione_annua_lorda=13500, anni_servizio=2, rivalutazione_media_pct=FOI_DIC_2020)
    s = _site(page, "01/01/2019", "31/12/2020", [13500, 13500])
    assert s["coeff"].get(2020) == pytest.approx(1.5, abs=1e-6), f"precondizione: coefficiente 2020 {s['coeff']}"
    _confronta("13500 x 2 anni 2019-2020, FOI reale negativo", t, s)


def test_limite_coefficiente_reale_2024_2025(page):
    """Caso al limite (variante confrontabile del caso 2): rapporto 01/01/2024-
    31/12/2025, 30.000 euro l'anno; al tool il FOI reale di dicembre 2025 (+1,081531%,
    indici 120,2 -> 121,5), cosi' tasso tool = coefficiente sito 2,311148%.
    Atteso per legge: quote 2 x 2.222,22; rivalutazione 51,36; imposta sostitutiva 17%
    8,73 (art. 11 co. 3 D.Lgs. 47/2000); fondo 4.487,07; reddito di riferimento
    (4.487,07 - 51,36) x 144 / 24 = 26.614,26 (art. 19 co. 1 TUIR). Tool: lordo
    4.495,80 (coincide con accantonamenti + rivalutazione lorda), RR 26.974,80."""
    t = _tool(retribuzione_annua_lorda=30000, anni_servizio=2, rivalutazione_media_pct=FOI_DIC_2025)
    s = _site(page, "01/01/2024", "31/12/2025", [30000, 30000])
    assert s["coeff"].get(2025) == pytest.approx(1.5 + 0.75 * FOI_DIC_2025, abs=5e-7), (
        f"precondizione: coefficiente 2025 {s['coeff']}")
    _confronta("30000 x 2 anni 2024-2025, FOI reale", t, s)


def test_limite_confine_scaglione_28000_tabella_2026(page):
    """Caso al limite: confine del primo scaglione (28.000) con la tabella 2026, la
    stessa del tool. Sul sito il 2026 si puo' chiudere solo prima di oggi: rapporto
    01/01/2026-31/08/2026 (8 mesi) con retribuzione utile 31.500 -> quota 2.333,33;
    per i rapporti inferiori all'anno il sito usa RR = fondo x 12 = 27.999,96, come il
    tool con anni_servizio=1. Atteso: aliquota 23% (art. 11 TUIR, 2026: 23% fino a
    28.000), imposta 536,67. Il sito applica le detrazioni (anche pro rata 8/12)."""
    t = _tool(retribuzione_annua_lorda=31500, anni_servizio=1)
    s = _site(page, "01/01/2026", "31/08/2026", [31500])
    _confronta("31500, 8 mesi 2026 (RR al confine 28.000)", t, s)


def test_secondo_scaglione_tabella_2026(page):
    """Tabella 2026 nel secondo scaglione: rapporto 01/01/2026-31/08/2026, retribuzione
    utile 40.500 -> quota 3.000, RR 36.000. Atteso (art. 19 co. 1 TUIR con art. 11
    TUIR 2026, L. 199/2025: 23% fino a 28.000, 33% fino a 50.000): imposta su RR
    6.440 + 2.640 = 9.080, aliquota media 25,22%, imposta sul TFR 756,67 (756,60 se
    l'aliquota e' arrotondata a due decimali prima dell'applicazione), come il tool.
    Osservato: il sito applica gli scaglioni 2025 (35%): aliquota 25,67%, imposta
    770,10 -- probabile mancato aggiornamento del sito alla L. 199/2025."""
    t = _tool(retribuzione_annua_lorda=40500, anni_servizio=1)
    s = _site(page, "01/01/2026", "31/08/2026", [40500])
    _confronta("40500, 8 mesi 2026 (RR 36.000)", t, s)


def test_limite_anno_cessazione_2025_tabella_diversa(page):
    """Caso al limite: anno diverso della tabella. Rapporto 01/01/2025-31/12/2025,
    40.500 euro -> quota 3.000, RR 36.000. Art. 19 co. 1 TUIR: aliquota "con
    riferimento all'anno in cui e' maturato il diritto alla percezione" = 2025
    (23% / 35% / 43%): imposta su RR 6.440 + 2.800 = 9.240, aliquota 25,67%. Il tool
    non riceve l'anno di cessazione e usa gli scaglioni dell'anno corrente (2026,
    33%): aliquota 25,22%, imposta 756,67."""
    t = _tool(retribuzione_annua_lorda=40500, anni_servizio=1)
    s = _site(page, "01/01/2025", "31/12/2025", [40500])
    _confronta("40500 x 1 anno 2025 (scaglioni 2025 vs 2026)", t, s)


def test_limite_clausola_salvaguardia_2006(page):
    """Caso al limite: reddito di riferimento alto, dove le aliquote vigenti al
    31/12/2006 (23% fino a 26.000, 33% fino a 33.500, 39% fino a 100.000, 43% oltre)
    sono piu' favorevoli di quelle 2026. Rapporto 01/01/2026-31/08/2026, retribuzione
    utile 135.000 -> quota 10.000, RR 120.000. Scaglioni 2026: 43.800 -> 36,50%;
    scaglioni 2006: 42.990 -> 35,825%. Atteso (clausola di salvaguardia della
    finanziaria 2007, come descritta dal sito): aliquota 35,83%, imposta 3.582,50;
    il tool non ha la clausola e applica 36,50% (3.650,00). Osservato: il sito da'
    36,87% (scaglioni 2025, senza clausola), quindi ne' tool ne' sito danno 35,83%:
    applicabilita' della clausola da verificare in fase 2."""
    t = _tool(retribuzione_annua_lorda=135000, anni_servizio=1)
    s = _site(page, "01/01/2026", "31/08/2026", [135000])
    _confronta("135000, 8 mesi 2026 (clausola aliquote 2006)", t, s)


def test_limite_rapporto_a_cavallo_anno(page):
    """Caso al limite: un anno di servizio a cavallo di due anni solari, 01/07/2024-
    30/06/2025, 15.000 euro per semestre (30.000 annui). Per legge (art. 2120 co. 4-5
    c.c.) la quota accantonata al 31/12/2024 (1.111,11) si rivaluta alla cessazione
    col coefficiente di giugno 2025 (0,75% fisso + 75% del FOI giugno 2025 / dicembre
    2024 = 1,436356%): rivalutazione 15,96, imposta sostitutiva 17%. Il tool, con
    anni_servizio=1, non rivaluta nulla: lordo 2.222,22, RR 26.666,64."""
    t = _tool(retribuzione_annua_lorda=30000, anni_servizio=1)
    s = _site(page, "01/07/2024", "30/06/2025", [15000, 15000])
    _confronta("30000, 12 mesi 07/2024-06/2025", t, s)
