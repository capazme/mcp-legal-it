"""Benchmark fase 1: rivalutazione_tfr vs avvocatoandreani.it.

Pagina principale: https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php
  Modulo ``CoeffTfr`` (POST): select ``MeseRif`` (01-12) e ``AnnoRif`` (1982-2026),
  pulsante ``#btn-calc``. Risultato: indici FOI di dicembre dell'anno precedente e
  del mese scelto, variazione al 100% e al 75%, tasso fisso (rapportato ai mesi),
  "Coefficiente di rivalutazione TFR" (6 decimali).
Pagina secondaria: https://www.avvocatoandreani.it/servizi/calcolo-tfr.php
  Modulo ``CalcoloTfr``: date di inizio/cessazione (select Giorno/Mese/Anno), una
  riga per anno (``ImpRetr-i`` = retribuzione utile), spunta ``ContributoIVS``
  (lasciata SPENTA: il tool ignora la riduzione 0,50% dell'art. 3 L. 297/1982),
  invio con ``form.requestSubmit(#btn-calc)`` (il banner CMP arriva in ritardo e
  intercetta i click). Risultato: ``table.tfr`` con, anno per anno, TFR base,
  coefficiente, rivalutazione, imposta sostitutiva e fondo, piu' la riga TOT.

Tool: ``rivalutazione_tfr(retribuzione_annua, anni_servizio, anno_cessazione)``
(src/tools/rivalutazioni_istat.py). Anni di servizio = anno_cessazione - anni ...
anno_cessazione - 1, quota annua = retribuzione / 13,5 (art. 2120 co. 1 c.c.),
rivalutazione del fondo al 31/12 dell'anno precedente con 1,5% + 75% della
variazione FOI dicembre su dicembre (art. 2120 co. 4 c.c.), imposta sostitutiva
17% sul totale delle rivalutazioni (art. 11 co. 3 D.Lgs. 47/2000, 17% dal 2015 per
art. 1 co. 623 L. 190/2014; prima 11%). Sul sito lo stesso rapporto e' 01/01 del
primo anno - 31/12 dell'ultimo anno, con retribuzione costante.

Ogni caso confronta tre cose, raccolte in un'unica lista di scostamenti:
  1. coefficiente annuo: rivalutazione del tool per l'anno vs fondo del tool
     all'inizio dell'anno x coefficiente del sito (isola il coefficiente dalla base);
  2. rivalutazioni totali, imposta sostitutiva totale;
  3. fondo finale: ``tfr_netto_rivalutazione`` del tool vs "Fondo TFR" del sito
     (il sito trattiene l'imposta dal fondo anno per anno).
Tolleranza 0,01 euro (brief).
"""

import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

from tests.comparison.conftest import parse_euro

URL_COEFF = "https://www.avvocatoandreani.it/servizi/coefficienti-rivalutazione-tfr.php"
URL_TFR = "https://www.avvocatoandreani.it/servizi/calcolo-tfr.php"
TOL = 0.01


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-25")


def _tool(**kwargs) -> dict:
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import src.server  # noqa: F401  (registers all tool modules)
    from src.tools.rivalutazioni_istat import rivalutazione_tfr

    fn = getattr(rivalutazione_tfr, "fn", rivalutazione_tfr)
    return fn(**kwargs)


def _strip_cmp(page):
    page.evaluate(
        'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container").forEach(el => el.remove())'
    )


def _num(cell: str) -> float:
    cell = cell.strip()
    if cell in ("", "-"):
        return 0.0
    return parse_euro(cell)


def _site_tfr(page, anno_inizio: int, anno_fine: int, retribuzione: float) -> dict:
    """Drive calcolo-tfr.php for 01/01/anno_inizio - 31/12/anno_fine, IVS off."""
    page.goto(URL_TFR, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)  # the CMP banner shows up late
    _strip_cmp(page)
    for name, val in [
        ("GiornoInizio", "01"), ("MeseInizio", "01"), ("AnnoInizio", str(anno_inizio)),
        ("GiornoFine", "31"), ("MeseFine", "12"), ("AnnoFine", str(anno_fine)),
    ]:
        page.select_option(f"select[name='{name}']", val)
        page.wait_for_timeout(300)
    page.wait_for_timeout(1000)
    n = anno_fine - anno_inizio + 1
    imp = f"{retribuzione:.2f}".replace(".", ",")
    for i in range(n):
        page.fill(f"#ImpRetr-{i}", imp)
    page.evaluate("document.CalcoloTfr.requestSubmit(document.getElementById('btn-calc'))")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector("table.tfr", timeout=30000)
    page.wait_for_timeout(1000)
    righe = {}
    tot = None
    for tr in page.query_selector_all("table.tfr tr"):
        celle = [c.inner_text().strip() for c in tr.query_selector_all("td")]
        if len(celle) < 8 or not (celle[0].startswith("TOT") or re.fullmatch(r"\d{4}", celle[0])):
            continue  # header row
        coeff = celle[4].strip()
        riga = {
            "tfr_base": _num(celle[1]),
            "coeff": None if coeff in ("", "-") else float(coeff.replace(",", ".")),
            "rivalutazione": _num(celle[5]),
            "imposta": _num(celle[6]),
            "fondo": _num(celle[7]),
        }
        if celle[0].startswith("TOT"):
            tot = riga
        elif re.fullmatch(r"\d{4}", celle[0]):
            righe[int(celle[0])] = riga
    assert tot is not None and len(righe) == n, f"tabella del sito incompleta: {righe}"
    page.wait_for_timeout(1500)  # courtesy pause between requests
    return {"righe": righe, "tot": tot}


def _site_coeff(page, anno: int, mese: str = "12") -> dict:
    page.goto(URL_COEFF, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    _strip_cmp(page)
    page.select_option("select[name='MeseRif']", mese)
    page.select_option("select[name='AnnoRif']", str(anno))
    page.evaluate("document.CoeffTfr.requestSubmit(document.getElementById('btn-calc'))")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    txt = page.inner_text("body")
    m = re.search(r"Coefficiente di rivalutazione TFR\s+([\d.,]+)\s*%", txt)
    v = re.search(r"Variazione percentuale al 100%\s+(-?[\d.,]+)\s*%", txt)
    assert m, "coefficiente non trovato sulla pagina"
    page.wait_for_timeout(1500)
    return {
        "coeff": float(m.group(1).replace(",", ".")),
        "var100": float(v.group(1).replace(",", ".")) if v else None,
    }


def _confronta(t: dict, s: dict) -> list[str]:
    """Return the list of mismatches (empty = coincide)."""
    diff = []
    det = t["dettaglio_anni"]
    for prev, cur in zip(det, det[1:]):
        anno = cur["anno"]
        sc = s["righe"][anno]["coeff"]
        atteso = prev["tfr_accumulato"] * (sc or 0.0) / 100
        if abs(cur["rivalutazione"] - atteso) > TOL:
            diff.append(
                f"{anno} coefficiente: tool {cur['coefficiente_rivalutazione_pct']}% "
                f"(riv. {cur['rivalutazione']:.2f}) vs sito {sc}% "
                f"(riv. attesa sul fondo del tool {atteso:.2f})"
            )
    for label, tv, sv in [
        ("rivalutazioni totali", t["totale_rivalutazioni"], s["tot"]["rivalutazione"]),
        ("imposta sostitutiva", t["imposta_sostitutiva_17_pct"], s["tot"]["imposta"]),
        ("fondo TFR finale (netto imposta)", t["tfr_netto_rivalutazione"], s["tot"]["fondo"]),
        ("quote accantonate", round(t["accantonamento_annuo"] * t["anni_servizio"], 2), s["tot"]["tfr_base"]),
    ]:
        if abs(tv - sv) > TOL:
            diff.append(f"{label}: tool {tv:.2f} vs sito {sv:.2f} (diff {tv - sv:+.2f})")
    return diff


def _run(page, retribuzione, anni, cessazione):
    t = _tool(retribuzione_annua=retribuzione, anni_servizio=anni, anno_cessazione=cessazione)
    assert "errore" not in t, t
    s = _site_tfr(page, cessazione - anni, cessazione - 1, retribuzione)
    diff = _confronta(t, s)
    assert not diff, "Scostamenti tool/sito:\n" + "\n".join(diff)


def test_piano_tre_anni_2021_2023(page):
    """Piano caso 1: 27.000, 3 anni, cessazione 2024 (rapporto 2021-2023).

    Atteso del piano: quote 2.000 (27.000/13,5, art. 2120 co. 1 c.c.); coefficienti
    ISTAT 2022 9,974576% e 2023 1,944162%; rivalutazioni 199,49 e 81,65; lordo
    6.281,14; imposta 17% = 47,79 (art. 11 co. 3 D.Lgs. 47/2000).
    """
    _run(page, 27000, 3, 2024)


def test_piano_2011_2015_indice_in_calo_e_aliquota_11(page):
    """Piano caso 2 (LIMITE: FOI in calo 2013/2014, aliquota 11% -> 17% nel 2015).

    Atteso del piano: coefficienti ISTAT 2012 3,302885, 2013 1,922535, 2014 1,500000
    (indice in calo: parte variabile zero, art. 2120 co. 4 c.c. "75% dell'aumento"),
    2015 1,500000; rivalutazioni 359,94; lordo 10.359,94; imposta 11% fino al 2014
    (art. 11 co. 3 D.Lgs. 47/2000) e 17% sul 2015 (art. 1 co. 623 L. 190/2014) = 47,01.
    Il tool oggi restituisce 10.288,09 e 48,97.
    """
    _run(page, 27000, 5, 2016)


def test_piano_rapporto_lungo_2004_2015(page):
    """Piano caso 3 (LIMITE: rapporto di 12 anni a cavallo del cambio d'aliquota 2015).

    Atteso del piano: imposta 11% sulle rivalutazioni 2005-2014 e 17% su quella 2015
    (art. 1 co. 623 L. 190/2014); il tool applica il 17% a tutte (555,31).
    Coefficienti annui da leggere dalla fonte ISTAT.
    """
    _run(page, 30000, 12, 2016)


def test_limite_un_solo_anno_senza_rivalutazione(page):
    """LIMITE: un anno di servizio (2025): nessuna rivalutazione, fondo = 30.000/13,5.

    Art. 2120 co. 4 c.c.: la rivalutazione si applica al fondo al 31/12 dell'anno
    precedente, che nel primo anno e' zero. Atteso: 2.222,22.
    """
    _run(page, 30000, 1, 2026)


def test_limite_coefficiente_2025_base_foi_nuova(page):
    """LIMITE: rapporto 2024-2025, coefficiente di dicembre 2025 (ultimo anno intero
    della tabella FOI, a cavallo del cambio di base 2025=100 con coefficiente di
    raccordo 1,214). Art. 2120 co. 4 c.c.; atteso: quote 2.000 + riv. 2.000 x coeff.
    dicembre 2025 del sito.
    """
    _run(page, 27000, 2, 2026)


def test_piano_dicembre_2026_non_pubblicato(page):
    """Piano caso 4: 30.000, 2 anni, cessazione 2027 (rapporto 2025-2026).

    Atteso del piano: dicembre 2026 non pubblicato, il tool usa agosto 2026
    (variazione 3,62%) e deve segnalarlo come INDICATIVO; valore ufficiale ISTAT a
    gennaio 2027. Il calcolatore del sito non accetta il 2027 (anno massimo 2026) e
    la pagina coefficienti per agosto 2026 riporta la parte fissa rapportata a 8 mesi
    (1%), mentre il tool applica 1,5% pieno su una variazione parziale: grandezze non
    omogenee, confronto non possibile. Si verifica solo l'avvertenza INDICATIVO e si
    registrano i due valori.
    """
    t = _tool(retribuzione_annua=30000, anni_servizio=2, anno_cessazione=2027)
    assert t.get("avvertenza") and "INDICATIVO" in t["avvertenza"], t.get("avvertenza")
    s = _site_coeff(page, 2026, "08")
    pytest.skip(
        f"non confrontabile: tool coeff 2026 {t['dettaglio_anni'][1]['coefficiente_rivalutazione_pct']}% "
        f"(12 mesi di parte fissa su FOI dic 2025 -> ago 2026) vs sito agosto 2026 {s['coeff']}% "
        f"(variazione {s['var100']}%, parte fissa 8/12); il sito non calcola cessazioni nel 2027"
    )
