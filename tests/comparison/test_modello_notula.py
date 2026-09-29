"""Comparison tests: modello_notula vs avvocatoandreani.it.

The page the plan names first, modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php,
builds the notula with the 2004 forensic tariff ("diritti" and "onorari"): its figures
cannot be set against a DM 55/2014 notula (see test_pagina_modelli_notula_tariffa_2004).
The comparable figures come from two other pages of the same site:

* calcolo-compenso-avvocati-parametri-civili-2014.php, "Tabelle: 2022" (DM 55/2014 as
  amended by DM 147/2022), with the dedicated competenze the tool's procedures belong to:
  "Procedimenti monitori" (decreto ingiuntivo), "Atto di precetto", "Esecuzioni
  mobiliari", "Esecuzioni presso terzi, per consegna e rilascio", "Esecuzioni
  immobiliari". "Includi accessori" is switched on (IVA 22% + CPA 4%), spese generali
  15% on, ritenuta d'acconto off: the same composition as the tool's totale_onorari.
  The values were cross-checked against the published tables
  tabella-parametri-forensi-{procedimenti-monitori,precetto,esecuzioni-mobiliari,
  esecuzioni-immobiliari}.html (same numbers).
* calcolo_contributo_unificato.php: the proportional calculator (with the 50% reduction
  of art. 13 co. 3 DPR 115/2002 for the decreto ingiuntivo) and the "Procedimenti con
  Contributo Fisso" table (art. 13 co. 2 DPR 115/2002 for the esecuzioni).

Norms: DM 55/2014 art. 2 co. 2 (spese generali 15%), art. 4, Tabella 8 (procedimenti
monitori) and the tables for the atto di precetto and the esecuzioni, as updated by
DM 147/2022;
CPA 4% (art. 11 L. 576/1980); IVA 22% (DPR 633/1972); contributo unificato art. 13
co. 1, 2 and 3 DPR 115/2002; anticipazione forfettaria art. 30 DPR 115/2002.

Tolerance: 0.01 EUR on every amount (brief). A genuine gap stays a failing test.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close

_URL_PARAMETRI = "https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php"
_URL_CU = "https://www.avvocatoandreani.it/servizi/calcolo_contributo_unificato.php"
_URL_MODELLI = (
    "https://www.avvocatoandreani.it/servizi/modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php"
)
_TOL = 0.01

# Site "Competenza" select values (calcolo-compenso-avvocati-parametri-civili-2014.php).
_COMP_TRIBUNALE = "110"
_COMP_PRECETTO = "150"
_COMP_MONITORI = "170"
_COMP_ESEC_MOBILIARI = "270"
_COMP_ESEC_PRESSO_TERZI = "280"
_COMP_ESEC_IMMOBILIARI = "290"

# Tool livello -> value of the per-phase "Vsel<n>" radio (1 = Min, 2 = Med, 3 = Max).
_LIVELLO = {"min": "1", "medio": "2", "max": "3"}

_BASE = {"avvocato": "Mario Rossi", "cliente": "Alfa S.r.l.", "fasi": None}


# --------------------------------------------------------------------------- helpers


def _tool(**kwargs) -> dict:
    from src.tools.fatturazione_avvocati import modello_notula

    fn = getattr(modello_notula, "fn", modello_notula)
    args = dict(_BASE)
    args.update(kwargs)
    r = fn(**args)
    assert "errore" not in r, r
    return r["dettaglio_calcoli"]


def _euro(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _open(page, url: str) -> None:
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    accept_cookies(page)


def _upper_bound(label: str) -> float | None:
    """Upper bound of a site scaglione label ('Fino a € 5.200', 'Da € 5.201 a € 26.000')."""
    nums = re.findall(r"€\s*([\d.]+)", label)
    if label.lower().startswith("oltre") or not nums:
        return None
    return _euro(nums[-1])


def _select_scaglione(page, valore: float) -> str:
    """Select the determinate-value band that contains `valore`; return its label."""
    opts = page.evaluate(
        "() => [...document.querySelectorAll('#Scaglione option')].map(o => [o.value, o.text])"
    )
    for value, text in opts:
        if text.lower().startswith("indeterminabile"):
            continue
        ub = _upper_bound(text)
        if ub is None or valore <= ub:
            page.select_option("#Scaglione", value)
            page.wait_for_timeout(1200)
            return text
    raise AssertionError(f"nessuno scaglione del sito per {valore}: {opts}")


def _site_parametri(page, competenza: str, valore: float, livello: str, keep_phases=None) -> dict:
    """Drive the DM 55/2014 civil calculator and parse the PROSPETTO FINALE.

    keep_phases: indices (1-based) of the phase rows to keep ticked; None keeps all.
    """
    _open(page, _URL_PARAMETRI)
    page.select_option("#Anno", "2022")
    page.wait_for_timeout(800)
    page.select_option("#Competenza", competenza)
    page.wait_for_timeout(1500)
    scaglione = _select_scaglione(page, valore)
    phases = page.evaluate(
        """() => [...document.querySelectorAll('input[name^=Fsel]')]
                 .filter(i => /^Fsel\\d+$/.test(i.name))
                 .map(i => [parseInt(i.name.slice(4), 10),
                            i.closest('tr').innerText.replace(/\\s+/g, ' ').trim()])"""
    )
    for idx, _row in phases:
        page.check(f"input[name='Vsel{idx}'][value='{_LIVELLO[livello]}']", force=True)
        page.wait_for_timeout(200)
        if keep_phases is not None and idx not in keep_phases:
            page.uncheck(f"input[name='Fsel{idx}']", force=True)
            page.wait_for_timeout(200)
    # A coordinate click (even forced) can land on an ad block laid over the button when
    # the phase table is long: dispatch the click on the element itself.
    page.locator("#Btn-Accessori").dispatch_event("click")
    page.wait_for_timeout(500)
    assert page.is_checked("input[name='Iva']") and page.is_checked("input[name='Cpa']")
    assert not page.is_checked("input[name='DoRacc']")
    page.click("#Btn-Calcola", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    assert "Tabelle: 2022" in body, "il sito non ha usato le tabelle DM 147/2022"
    prospetto = body[body.index("PROSPETTO FINALE"):]

    def amount(label: str) -> float:
        m = re.search(re.escape(label) + r"[^\n€]*€\s*([\d.]+,\d{2})", prospetto)
        assert m, f"voce '{label}' non trovata nel prospetto del sito:\n{prospetto[:800]}"
        return _euro(m.group(1))

    return {
        "scaglione": scaglione,
        "fasi": [row for _i, row in phases],
        "compenso": amount("Compenso tabellare"),
        "spese_generali": amount("Spese generali"),
        "cpa": amount("Cassa Avvocati"),
        "iva": amount("IVA 22%"),
        "totale": amount("IPOTESI DI COMPENSO LIQUIDABILE"),
    }


def _site_cu(page, valore: float, riduzione: bool) -> float:
    """Contributo unificato, civil first instance, determinate value."""
    _open(page, _URL_CU)
    page.select_option("select[name='Processo']", "1")
    page.wait_for_timeout(300)
    page.select_option("select[name='Giudizio']", "1")
    page.wait_for_timeout(300)
    page.check("input[name='TipoValore'][value='0']", force=True)
    page.fill("input[name='ValoreCausa']", f"{valore:.2f}".replace(".", ","))
    if riduzione:
        page.check("input[name='Riduzione']", force=True)
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    m = re.search(r"Il contributo è\s*€\s*([\d.]+,\d{2})", page.inner_text("body"))
    assert m, "risultato del contributo unificato non trovato"
    return _euro(m.group(1))


_CU_FISSO: dict[str, float] = {}


def _site_cu_fisso(page) -> dict[str, float]:
    """The 'Procedimenti con Contributo Fisso' table (loaded once per session)."""
    if not _CU_FISSO:
        _open(page, _URL_CU)
        page.click("input[type=submit][value*='Contributo Fisso']", force=True)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2500)
        for line in page.inner_text("body").splitlines():
            m = re.match(r"(.+?)\t\s*€\s*([\d.]+,\d{2})\s*$", line)
            if m:
                _CU_FISSO[m.group(1).strip()] = _euro(m.group(2))
        assert _CU_FISSO, "tabella dei contributi fissi non trovata"
    return _CU_FISSO


def _cu_fisso_voce(page, prefix: str) -> float:
    table = _site_cu_fisso(page)
    hits = [v for k, v in table.items() if k.startswith(prefix)]
    assert len(hits) == 1, f"voce '{prefix}' non univoca nella tabella del sito: {table}"
    return hits[0]


def _assert_notula_vs_site(tool: dict, site: dict, label: str) -> None:
    """Compare compensi and the accessori-inclusive total; report both before failing."""
    diffs = []
    for tk, sk in (("totale_compensi", "compenso"), ("totale_onorari", "totale")):
        if abs(tool[tk] - site[sk]) > _TOL:
            diffs.append(f"{tk}: tool={tool[tk]:.2f} sito={site[sk]:.2f} diff={tool[tk] - site[sk]:+.2f}")
    assert not diffs, (
        f"{label} [sito: {site['scaglione']}, fasi {site['fasi']}; "
        f"tool: fasi {[(f['fase'], f['importo']) for f in tool['fasi']]}]: " + "; ".join(diffs)
    )


# --------------------------------------------------------------------------- the page named by the plan


def test_pagina_modelli_notula_tariffa_2004(page):
    """The plan's page computes with the 2004 tariff: not comparable with DM 55/2014.

    Atteso (piano): 'La pagina modelli-notula-decreto-ingiuntivo-precetto-esecuzioni.php
    usa il tariffario forense del 2004 e non è confrontabile'.
    """
    _open(page, _URL_MODELLI)
    body = page.inner_text("body")
    assert "tariffario forense del 2004" in body
    pytest.skip(
        "modelli-notula-...php compone la notula con il tariffario forense 2004 "
        "(diritti + onorari): non confrontabile con i parametri DM 55/2014 del tool"
    )


# --------------------------------------------------------------------------- decreto ingiuntivo


def test_decreto_ingiuntivo_10000_medio_compenso(page):
    """Plan case 1: decreto ingiuntivo 10.000 EUR, medio.

    Atteso (piano): compenso dalla tabella dei procedimenti monitori, fase unica,
    scaglione 5.200,01-26.000, valore medio 567; il tool usa studio 919 + introduttiva
    777 = 1.696 della cognizione. Norma: DM 55/2014 Tabella 8 (procedimenti monitori)
    agg. DM 147/2022; accessori art. 2 co. 2 DM 55/2014, CPA 4%, IVA 22%.
    """
    tool = _tool(tipo_procedimento="decreto_ingiuntivo", valore_causa=10000, livello="medio")
    site = _site_parametri(page, _COMP_MONITORI, 10000, "medio")
    _assert_notula_vs_site(tool, site, "decreto ingiuntivo 10.000 medio")


def test_decreto_ingiuntivo_10000_contributo_unificato(page):
    """Plan case 1 (spese vive): contributo unificato del decreto ingiuntivo.

    Atteso (piano): 118,50 (237 ridotto alla metà, art. 13 co. 3 DPR 115/2002).
    """
    tool = _tool(tipo_procedimento="decreto_ingiuntivo", valore_causa=10000, livello="medio")
    site = _site_cu(page, 10000, riduzione=True)
    assert_close(tool["spese_vive"]["contributo_unificato_dimezzato"], site, _TOL, "CU decreto ingiuntivo 10.000")


def test_decreto_ingiuntivo_5200_contributo_unificato_limite(page):
    """Limit: 5.200 EUR is the last euro of the 1.100,01-5.200 CU band.

    Atteso: 98 / 2 = 49 (art. 13 co. 1 lett. b e co. 3 DPR 115/2002).
    """
    tool = _tool(tipo_procedimento="decreto_ingiuntivo", valore_causa=5200, livello="medio")
    site = _site_cu(page, 5200, riduzione=True)
    assert_close(tool["spese_vive"]["contributo_unificato_dimezzato"], site, _TOL, "CU decreto ingiuntivo 5.200")


def test_decreto_ingiuntivo_5200_max_compenso_limite(page):
    """Limit + enumerated level: 5.200 EUR (top of the first monitorio band) at 'max'.

    Atteso: DM 55/2014 Tabella 8, fase unica, scaglione fino a 5.200, massimo 710
    (sito); il tool somma studio 638 + introduttiva 638 della cognizione (1.276).
    """
    tool = _tool(tipo_procedimento="decreto_ingiuntivo", valore_causa=5200, livello="max")
    site = _site_parametri(page, _COMP_MONITORI, 5200, "max")
    _assert_notula_vs_site(tool, site, "decreto ingiuntivo 5.200 max")


def test_accessori_con_fasi_cognizione_del_tool(page):
    """Control case: the site's tribunal cognizione table with the tool's own phases.

    Same input as plan case 1, but the site is driven on 'Giudizi di cognizione innanzi
    al tribunale' with only studio + introduttiva ticked (the phases the tool picks for
    a decreto ingiuntivo). Atteso: 919 + 777 = 1.696, spese generali 254,40, CPA 78,02,
    IVA 446,25, totale 2.474,67: isolates the accessori arithmetic (art. 2 co. 2 DM
    55/2014, CPA, IVA) from the choice of table.
    """
    tool = _tool(tipo_procedimento="decreto_ingiuntivo", valore_causa=10000, livello="medio")
    site = _site_parametri(page, _COMP_TRIBUNALE, 10000, "medio", keep_phases={1, 2})
    assert_close(tool["totale_compensi"], site["compenso"], _TOL, "compensi")
    assert_close(tool["spese_generali_15pct"], site["spese_generali"], _TOL, "spese generali")
    assert_close(tool["cpa_4pct"], site["cpa"], _TOL, "CPA")
    assert_close(tool["iva_22pct"], site["iva"], _TOL, "IVA")
    assert_close(tool["totale_onorari"], site["totale"], _TOL, "totale onorari")


# --------------------------------------------------------------------------- precetto


def test_precetto_3000_min_compenso(page):
    """Plan case 5: atto di precetto 3.000 EUR, minimo.

    Atteso (piano): compenso dalla tabella dell'atto di precetto (sito: scaglione fino a
    5.200, minimo 71); il tool usa 213 + 213 = 426 della cognizione. Norma: DM 55/2014,
    tabella dell'atto di precetto, agg. DM 147/2022.
    """
    tool = _tool(tipo_procedimento="precetto", valore_causa=3000, livello="min")
    site = _site_parametri(page, _COMP_PRECETTO, 3000, "min")
    _assert_notula_vs_site(tool, site, "precetto 3.000 min")


def test_precetto_3000_spese_vive():
    """Plan case 5 (spese vive): not comparable on the site.

    Atteso (piano): nessun contributo unificato e nessuna anticipazione forfettaria di
    27 euro (art. 30 DPR 115/2002 si versa all'iscrizione a ruolo), solo notifica; il
    tool aggiunge 27 di marca e 27 di notifica. Nessuna pagina del sito calcola le spese
    vive di un precetto (atto-di-precetto.php le chiede in input).
    """
    tool = _tool(tipo_procedimento="precetto", valore_causa=3000, livello="min")
    pytest.skip(
        "il sito non calcola le spese vive del precetto; tool: "
        f"{tool['spese_vive']} (marca da bollo 27 non dovuta per art. 30 DPR 115/2002)"
    )


# --------------------------------------------------------------------------- esecuzione mobiliare


def test_esecuzione_mobiliare_2000_contributo_unificato(page):
    """Plan case 2: esecuzione mobiliare 2.000 EUR.

    Atteso (piano): contributo unificato 43 euro (art. 13 co. 2 DPR 115/2002, esecuzioni
    mobiliari di valore inferiore a 2.500); il tool indica 98 (tabella di cognizione).
    """
    tool = _tool(tipo_procedimento="esecuzione_mobiliare", valore_causa=2000, livello="medio")
    site = _cu_fisso_voce(page, "Procedimenti esecutivi mobiliari di valore inferiore")
    assert_close(tool["spese_vive"]["contributo_unificato"], site, _TOL, "CU esecuzione mobiliare 2.000")


def test_esecuzione_mobiliare_2500_contributo_unificato_limite(page):
    """Plan case 3 (limit): esecuzione mobiliare esattamente 2.500 EUR.

    Atteso (piano): 139 euro (art. 13 co. 2 DPR 115/2002, da 2.500 in su); il tool 98.
    """
    tool = _tool(tipo_procedimento="esecuzione_mobiliare", valore_causa=2500, livello="medio")
    site = _cu_fisso_voce(page, "Procedimenti esecutivi mobiliari di valore superiore o uguale")
    assert_close(tool["spese_vive"]["contributo_unificato"], site, _TOL, "CU esecuzione mobiliare 2.500")


def test_esecuzione_mobiliare_2000_compenso(page):
    """Plan case 2 (compensi): esecuzione mobiliare 2.000 EUR, medio.

    Atteso (piano): compensi dalla tabella delle esecuzioni mobiliari (sito, scaglione
    1.101-5.200: studio 368 + istruttoria/trattazione 184 = 552); il tool usa studio,
    introduttiva e istruttoria della cognizione (1.701). Norma: DM 55/2014, tabella
    delle esecuzioni mobiliari, agg. DM 147/2022.
    """
    tool = _tool(tipo_procedimento="esecuzione_mobiliare", valore_causa=2000, livello="medio")
    site = _site_parametri(page, _COMP_ESEC_MOBILIARI, 2000, "medio")
    _assert_notula_vs_site(tool, site, "esecuzione mobiliare 2.000 medio")


def test_esecuzione_mobiliare_presso_terzi_2000_compenso(page):
    """Variant: the tool labels 'esecuzione_mobiliare' as 'Esecuzione mobiliare presso terzi'.

    The site has a separate competenza 'Esecuzioni presso terzi, per consegna e rilascio'
    (scaglione 1.101-5.200: introduttiva 331 + trattazione/conclusiva 567 = 898 medio).
    Atteso: in either reading the tool's 1.701 (cognizione) differs.
    """
    tool = _tool(tipo_procedimento="esecuzione_mobiliare", valore_causa=2000, livello="medio")
    site = _site_parametri(page, _COMP_ESEC_PRESSO_TERZI, 2000, "medio")
    _assert_notula_vs_site(tool, site, "esecuzione presso terzi 2.000 medio")


# --------------------------------------------------------------------------- esecuzione immobiliare


def test_esecuzione_immobiliare_100000_contributo_unificato(page):
    """Plan case 4: esecuzione immobiliare 100.000 EUR.

    Atteso (piano): contributo unificato 278 euro (art. 13 co. 2 DPR 115/2002); il tool
    indica 759 (tabella di cognizione) più una trascrizione stimata di 300 (voce che il
    sito non calcola e che resta fuori dal confronto).
    """
    tool = _tool(tipo_procedimento="esecuzione_immobiliare", valore_causa=100000, livello="medio")
    site = _cu_fisso_voce(page, "Procedimenti di esecuzione immobiliare")
    assert_close(tool["spese_vive"]["contributo_unificato"], site, _TOL, "CU esecuzione immobiliare")


def test_esecuzione_immobiliare_100000_compenso(page):
    """Plan case 4 (compensi): esecuzione immobiliare 100.000 EUR, medio.

    Atteso (piano): compensi dalla tabella delle esecuzioni immobiliari (sito, scaglione
    52.001-260.000: introduttiva 1.433 + istruttoria/trattazione 982 = 2.415); il tool
    usa le quattro fasi della cognizione (14.103). Norma: DM 55/2014, tabella delle
    esecuzioni immobiliari, agg. DM 147/2022.
    """
    tool = _tool(tipo_procedimento="esecuzione_immobiliare", valore_causa=100000, livello="medio")
    site = _site_parametri(page, _COMP_ESEC_IMMOBILIARI, 100000, "medio")
    _assert_notula_vs_site(tool, site, "esecuzione immobiliare 100.000 medio")
