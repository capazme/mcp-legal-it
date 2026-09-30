"""Comparison tests: parcella_avvocato_penale vs avvocatoandreani.it (parametri penali).

Site page: calcolo-compenso-avvocati-parametri-penali-2014.php, "Tabelle: 2022 (vigenti)",
i.e. DM 55/2014 as amended by DM 147/2022 (GU n. 236 of 8/10/2022) - the only table the
tool carries (src/data/parametri_forensi.json, block "penale").

Norms: DM 55/2014 art. 12 co. 1 and the Tabella for criminal proceedings (values per
phase and per competent court, as updated by DM 147/2022); art. 4 co. 1 / art. 12 co. 1
(the medium value may be increased or reduced by up to 50%: the site's "Min"/"Max").

Driver: the site's Competenza select reloads the phase table by AJAX; the "VselAll"
radio (Min/Med/Max) applies the level to every phase; unticking "Fsel<i>" drops a
phase. The comparison reads the result table after "Calcola il Compenso" (per-phase
lines and "Compenso tabellare (...)", with cents) plus the live "Totale" field.

Secondary source: the published penal tables I-III linked from
tabelle-parametri-forensi.php (medium value, Min, Max per phase and per court).

Tolerance: 0.01 EUR on every amount (brief). The tool carries no spese generali /
CPA / IVA, so only "Compenso tabellare" is compared (not the "PROSPETTO FINALE").
"""

import re

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.comparison.conftest import accept_cookies, assert_close

_PAGE = "calcolo-compenso-avvocati-parametri-penali-2014.php"
_BASE = "https://www.avvocatoandreani.it/servizi/"
_TOL = 0.01

# Tool competenza -> site "Competenza" select value.
_COMP_MAP = {
    "giudice_pace": "500",
    "tribunale_monocratico": "570",
    "tribunale_collegiale": "580",
    "corte_assise": "590",
    "corte_appello": "600",
    "cassazione": "630",
}

# Tool livello -> site "VselAll" radio value.
_LIVELLO_MAP = {"min": "1", "medio": "2", "max": "3"}

_FASI = ("studio", "introduttiva", "istruttoria", "decisionale")

_AMOUNT_RE = re.compile(r"€\s*([\d.]+(?:,\d{2})?)")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _tool(**kwargs) -> dict:
    from src.tools.fatturazione_avvocati import parcella_avvocato_penale

    fn = getattr(parcella_avvocato_penale, "fn", parcella_avvocato_penale)
    return fn(**kwargs)


def _euro(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _fase_key(label: str) -> str | None:
    low = label.lower()
    for fase in _FASI:
        if fase in low:
            return fase
    return None


def _decline_consent(page) -> None:
    """Dismiss the consent dialog with its close icon ("continua senza accettare").

    Until the dialog is dismissed the page cancels the form's clicks (the submit never
    fires); it appears a moment after DOMContentLoaded, so it is waited for. Declining
    is the privacy-preserving choice and is enough to unblock the calculator."""
    try:
        page.wait_for_selector("#qc-cmp2-ui .qc-cmp2-close-icon", state="visible", timeout=10000)
        page.click("#qc-cmp2-ui .qc-cmp2-close-icon")
        page.wait_for_timeout(800)
    except PlaywrightTimeoutError:
        pass  # no dialog shown: nothing to dismiss


def _open_form(page) -> None:
    page.wait_for_timeout(1500)  # be gentle with the site between cases
    page.goto(_BASE + _PAGE, timeout=60000, wait_until="domcontentloaded")
    _decline_consent(page)


def _js_click(page, selector: str) -> None:
    """Click through the element's own DOM click() (immune to sticky banners)."""
    page.eval_on_selector(selector, "e => e.click()")
    page.wait_for_timeout(300)


def _select_and_wait(page, name: str, value: str, op: int) -> None:
    """Pick an option and wait for the AJAX reload of the phase table (op=2 Competenza,
    op=3 Anno); fall back to a fixed wait if the response is not observed."""
    try:
        with page.expect_response(lambda r: f"op={op}&" in r.url, timeout=15000):
            page.select_option(f"select[name='{name}']", value)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(1500)


def _form_rows(page) -> list[dict]:
    return page.evaluate(
        """() => { const out = [];
        for (let i = 1; document.getElementById('rfase-' + i); i++) {
          const v = document.forms.Parametri['Val' + i];
          out.push({i, label: (document.getElementById('fase-' + i) || {}).innerText || '',
                    checked: document.forms.Parametri['Fsel' + i].checked,
                    val: v ? v.value : ''});
        }
        return out; }"""
    )


def _site_calcola(page, competenza: str, livello: str, escludi: tuple[str, ...] = ()) -> dict:
    """Drive the calculator with Tabelle 2022 and return form rows, live total and the
    result table after 'Calcola il Compenso'."""
    _open_form(page)
    if page.eval_on_selector("#Anno", "e => e.value") != "2022":
        _select_and_wait(page, "Anno", "2022", 3)
    if page.eval_on_selector("#Competenza", "e => e.value") != _COMP_MAP[competenza]:
        _select_and_wait(page, "Competenza", _COMP_MAP[competenza], 2)
    assert page.eval_on_selector("#Anno", "e => e.value") == "2022"
    assert page.eval_on_selector("#Competenza", "e => e.value") == _COMP_MAP[competenza]

    _js_click(page, f'input[name="VselAll"][value="{_LIVELLO_MAP[livello]}"]')

    for row in _form_rows(page):
        if _fase_key(row["label"]) in escludi and row["checked"]:
            _js_click(page, f'input[name="Fsel{row["i"]}"]')
    rows = _form_rows(page)
    for row in rows:
        assert row["checked"] == (_fase_key(row["label"]) not in escludi), rows
    live_tot = page.eval_on_selector("#val-tot", "e => e.value")

    with page.expect_navigation(timeout=30000, wait_until="domcontentloaded"):
        _js_click(page, "#Btn-Calcola")
    page.wait_for_timeout(2500)
    assert "Tabelle: 2022" in page.inner_text("body"), "il sito non ha usato le tabelle 2022"

    tables = page.evaluate(
        """() => Array.from(document.querySelectorAll('table')).map(t => t.innerText.trim())
                 .filter(t => /Compenso tabellare \\(/.test(t))"""
    )
    assert tables, "result table with 'Compenso tabellare (...)' not found"
    fasi: dict[str, float] = {}
    totale = None
    for line in tables[0].splitlines():
        m = _AMOUNT_RE.search(line)
        if not m:
            continue
        if line.startswith("Compenso tabellare"):
            totale = _euro(m.group(1))
        elif line.startswith("Fase"):
            key = _fase_key(line.split(",")[0])
            if key:
                fasi[key] = _euro(m.group(1))
    assert totale is not None, f"total not parsed from: {tables[0]!r}"
    return {
        "rows": rows,
        "fasi_form": [_fase_key(r["label"]) for r in rows],
        "live_tot": _euro(live_tot) if live_tot else None,
        "fasi": fasi,
        "totale": totale,
        "testo": tables[0],
    }


def _compare(ours: dict, site: dict, label: str) -> None:
    assert "errore" not in ours, ours
    ours_fasi = {f["fase"]: f["importo"] for f in ours["fasi"]}
    assert set(ours_fasi) == set(site["fasi"]), (
        f"{label}: fasi tool={sorted(ours_fasi)} sito={sorted(site['fasi'])}"
    )
    for fase, importo in ours_fasi.items():
        assert_close(importo, site["fasi"][fase], _TOL, f"{label}_{fase}")
    assert_close(ours["totale_compenso"], site["totale"], _TOL, f"{label}_totale")
    assert_close(ours["totale_compenso"], site["live_tot"], _TOL, f"{label}_totale_live")


# ---------------------------------------------------------------------------
# cases from the plan
# ---------------------------------------------------------------------------


def test_tribunale_monocratico_medio_tutte_fasi(page):
    """Plan case 1. Atteso: 473 + 567 + 1.134 + 1.418 = 3.592 EUR (Competenza 570).
    Norma: DM 55/2014 Tab. penale (DM 147/2022), valori medi."""
    ours = _tool(competenza="tribunale_monocratico", fasi=None, livello="medio")
    site = _site_calcola(page, "tribunale_monocratico", "medio")
    _compare(ours, site, "trib_mono_medio")


def test_cassazione_max_senza_istruttoria(page):
    """Plan case 2 (limit: court without the istruttoria phase). Atteso: tre fasi,
    1.418 + 3.969 + 4.112 = 9.499 EUR, massimi = medi (945, 2.646, 2.741) +50%
    (Competenza 630). Norma: DM 55/2014 Tab. penale (DM 147/2022), art. 12 co. 1."""
    ours = _tool(competenza="cassazione", fasi=None, livello="max")
    site = _site_calcola(page, "cassazione", "max")
    assert "istruttoria" not in site["fasi_form"], site["fasi_form"]
    _compare(ours, site, "cass_max")


def test_giudice_pace_min(page):
    """Plan case 3 (limit: -50% on an odd medium value, 473 -> 236,5 -> 237).
    Atteso: 189 + 237 + 378 + 331 = 1.135 EUR (Competenza 500).
    Norma: DM 55/2014 Tab. penale (DM 147/2022), art. 12 co. 1 (riduzione fino al 50%)."""
    ours = _tool(competenza="giudice_pace", fasi=None, livello="min")
    site = _site_calcola(page, "giudice_pace", "min")
    _compare(ours, site, "gdp_min")


def test_cassazione_fase_istruttoria_non_prevista(page):
    """Plan case 4 (limit). Atteso: tool -> errore 'Fasi non disponibili per cassazione';
    sul sito la fase istruttoria per la Cassazione non esiste (nessuna riga / campo).
    Norma: DM 55/2014 Tab. penale, Corte di Cassazione: fasi studio, introduttiva,
    decisionale."""
    ours = _tool(competenza="cassazione", fasi=["istruttoria"], livello="medio")
    assert "errore" in ours and "Fasi non disponibili per cassazione" in ours["errore"], ours
    _open_form(page)
    _select_and_wait(page, "Competenza", _COMP_MAP["cassazione"], 2)
    assert page.eval_on_selector("#Competenza", "e => e.value") == "630"
    fasi_sito = [_fase_key(r["label"]) for r in _form_rows(page)]
    assert fasi_sito == ["studio", "introduttiva", "decisionale"], fasi_sito
    assert page.query_selector("#val-60") is None


# ---------------------------------------------------------------------------
# additional limit cases
# ---------------------------------------------------------------------------


def test_tribunale_collegiale_max(page):
    """Limit: enumerated court not in the plan, max level.
    Atteso tool: 710 + 1.134 + 2.127 + 2.127 = 6.098 EUR (Competenza 580).
    Norma: DM 55/2014 Tab. penale (DM 147/2022), art. 12 co. 1 (aumento fino al 50%)."""
    ours = _tool(competenza="tribunale_collegiale", fasi=None, livello="max")
    site = _site_calcola(page, "tribunale_collegiale", "max")
    _compare(ours, site, "trib_coll_max")


def test_corte_appello_min(page):
    """Limit: enumerated court not in the plan, min level (-50% on 945 -> 472,5 -> 473).
    Atteso tool: 237 + 473 + 709 + 709 = 2.128 EUR (Competenza 600).
    Norma: DM 55/2014 Tab. penale (DM 147/2022), art. 12 co. 1."""
    ours = _tool(competenza="corte_appello", fasi=None, livello="min")
    site = _site_calcola(page, "corte_appello", "min")
    _compare(ours, site, "app_min")


def test_corte_assise_max_arrotondamenti(page):
    """Limit: +50% on odd medium values (2.363 -> 3.544,5 -> 3.545; 2.835 -> 4.252,5 -> 4.253).
    Atteso tool: 1.134 + 2.127 + 3.545 + 4.253 = 11.059 EUR (Competenza 590).
    Norma: DM 55/2014 Tab. penale (DM 147/2022), art. 12 co. 1."""
    ours = _tool(competenza="corte_assise", fasi=None, livello="max")
    site = _site_calcola(page, "corte_assise", "max")
    _compare(ours, site, "assise_max")


def test_corte_assise_medio_fasi_parziali(page):
    """Limit: phase subset (introduttiva and istruttoria dropped on both sides).
    Atteso tool: studio 756 + decisionale 2.835 = 3.591 EUR (Competenza 590).
    Norma: DM 55/2014 art. 12 co. 3 (compenso per le sole fasi svolte), Tab. penale."""
    ours = _tool(competenza="corte_assise", fasi=["studio", "decisionale"], livello="medio")
    site = _site_calcola(page, "corte_assise", "medio", escludi=("introduttiva", "istruttoria"))
    _compare(ours, site, "assise_medio_parziale")


def test_tabelle_pubblicate_penale(page):
    """Secondary source: published penal tables I-III (tabelle-parametri-forensi.php).
    Every value (medio, Min, Max) for the six courts the tool covers must equal the tool's
    per-phase amount; a '-' cell must correspond to a phase the tool rejects.
    Norma: DM 55/2014 Tab. penale (DM 147/2022)."""
    pages = [
        "tabella-parametri-forensi-giudice-di-pace-penale-indagini-preliminari-difensive-"
        "cautelari-personali-reali.html",
        "tabella-parametri-forensi-gip-gup-tribunale-monocratico-collegiale-corte-assise.html",
        "tabella-parametri-forensi-corte-appello-penale-tribunale-sorveglianza-corte-assise-"
        "appello-cassazione-penale-magistrature-superiori.html",
    ]
    colonne = {
        "Giudice di pace": "giudice_pace",
        "Tribunale monocratico": "tribunale_monocratico",
        "Tribunale collegiale": "tribunale_collegiale",
        "Corte d'Assise": "corte_assise",
        "Corte d'Appello": "corte_appello",
        "Corte di Cassazione": "cassazione",
    }
    visti: set[tuple[str, str, str]] = set()
    for url in pages:
        page.goto(_BASE + url, timeout=60000, wait_until="domcontentloaded")
        accept_cookies(page)
        page.wait_for_timeout(1500)
        testo = page.evaluate(
            """() => Array.from(document.querySelectorAll('table')).map(t => t.innerText.trim())
                     .filter(t => /Fase di studio/.test(t))[0] || ''"""
        )
        lines = [ln for ln in testo.splitlines() if ln.strip()]
        header = [c.strip() for c in lines[0].split("\t") if c.strip()]
        for idx, line in enumerate(lines):
            if not line.startswith("Fase"):
                continue
            cells = line.split("\t")
            fase = _fase_key(cells[0])
            medi = [c.strip() for c in cells[1:]]
            mins = [c.strip() for c in lines[idx + 2].split("\t")]
            maxs = [c.strip() for c in lines[idx + 3].split("\t")]
            for col, nome in enumerate(header):
                comp = colonne.get(nome)
                if comp is None:
                    continue
                for livello, cella in (("medio", medi[col]), ("min", mins[col]), ("max", maxs[col])):
                    ours = _tool(competenza=comp, fasi=[fase], livello=livello)
                    if cella == "-":
                        assert "errore" in ours, f"{comp}/{fase}/{livello}: sito '-', tool {ours}"
                    else:
                        m = _AMOUNT_RE.search(cella)
                        assert m, f"{comp}/{fase}/{livello}: cella {cella!r}"
                        assert "errore" not in ours, f"{comp}/{fase}/{livello}: {ours}"
                        assert_close(ours["totale_compenso"], _euro(m.group(1)), _TOL,
                                     f"tab_{comp}_{fase}_{livello}")
                    visti.add((comp, fase, livello))
        page.wait_for_timeout(1500)
    # 5 courts x 4 phases + Cassazione x 4 (istruttoria '-') = 24 cells x 3 levels
    assert len(visti) == 72, len(visti)


# ---------------------------------------------------------------------------
# not comparable
# ---------------------------------------------------------------------------


def test_tabelle_2014_non_confrontabile():
    """Limit (table year): the site also offers 'Tabelle 2014-2018 (precedenti)'
    (e.g. Tribunale monocratico medio 450 + 540 + 1.080 + 1.350 = 3.420 EUR), the tool
    has no year parameter and carries only the DM 147/2022 values."""
    pytest.skip("non confrontabile: il tool non ha le tabelle 2014-2018 (solo DM 147/2022)")


def test_organi_non_coperti():
    """Coverage gap: the site computes GIP, GUP, indagini preliminari/difensive,
    convalida dell'arresto, cautelari personali/reali, tribunale e magistrato di
    sorveglianza, Corte d'Assise d'Appello, magistrature superiori (e.g. Corte d'Assise
    d'Appello medio 756 + 1.985 + 2.268 + 2.336 = 7.345 EUR); the tool rejects them."""
    ours = _tool(competenza="corte_assise_appello", fasi=None, livello="medio")
    assert "errore" in ours, ours
    pytest.skip("non confrontabile: il tool copre 6 organi su 17 del sito (Competenza non valida)")
