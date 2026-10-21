"""Comparison tests: calcolo_notula_penale vs avvocatoandreani.it (parametri penali).

Site page: calcolo-compenso-avvocati-parametri-penali-2014.php, "Tabelle: 2022"
(DM 55/2014 as amended by DM 147/2022), with "Includi accessori" (IVA 22% + CPA 4%)
switched on and "Spese generali" 15% on or off as the case requires.

Norms: DM 55/2014 art. 2 co. 2 (spese generali 15%), art. 12 and Tabella penale
(values per phase and per competent court, as updated by DM 147/2022);
CPA 4% (art. 11 L. 576/1980); IVA 22% (DPR 633/1972).

The tool always adds CPA and IVA and never applies the ritenuta d'acconto, so the
site is driven with IVA + CPA ticked and "Rit. acc." left unticked.
Tolerance: 0.01 EUR on every amount (brief); the two half-cent rounding probes compare
to the exact cent (see _TOL_ROUNDING).
"""

import json
import re

import pytest

from tests.comparison.conftest import assert_close

_URL = "https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-penali-2014.php"
_TOL = 0.01
# The two rounding probes below sit on an exact half cent of IVA: with the 0.01 brief
# tolerance a one-cent rounding difference would pass unnoticed, so those tests compare
# at half a cent (i.e. to the cent, exactly). This is stricter, never wider, than the brief.
_TOL_ROUNDING = 0.005

# Tool competenza -> site "Competenza" select value.
_COMP_MAP = {
    "giudice_pace": "500",
    "tribunale_monocratico": "570",
    "tribunale_collegiale": "580",
    "corte_assise": "590",
    "corte_appello": "600",
    "cassazione": "630",
}

# Tool livello -> site "VselAll" radio value (applies the level to every phase).
_LIVELLO_MAP = {"min": "1", "medio": "2", "max": "3"}

# Site phase row label prefix -> tool phase name.
_FASE_LABELS = {
    "studio": "studio",
    "introduttiva": "introduttiva",
    "istruttoria": "istruttoria",
    "decisionale": "decisionale",
}

_AMOUNT_RE = re.compile(r"€\s*([\d.]+,\d{2})\s*$")


def _tool(**kwargs) -> dict:
    from src.tools.fatturazione_avvocati import calcolo_notula_penale

    fn = getattr(calcolo_notula_penale, "fn", calcolo_notula_penale)
    return fn(**kwargs)


def _euro(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _site_phases(page) -> dict[str, int]:
    """Return {tool_phase_name: site_row_index} for the current competenza."""
    rows = page.evaluate(
        """() => {
            const n = parseInt(document.getElementsByName('NumFasi')[0].value, 10);
            const out = [];
            for (let i = 1; i <= n; i++) {
                const f = document.getElementsByName('Fsel' + i)[0];
                if (!f) continue;
                out.push([i, f.closest('tr').innerText.trim().toLowerCase()]);
            }
            return out;
        }"""
    )
    phases = {}
    for idx, label in rows:
        for prefix, name in _FASE_LABELS.items():
            if label.startswith(prefix):
                phases[name] = idx
    return phases


def _decline_consent(page):
    """Dismiss the Quantcast consent dialog with "continua senza accettare".

    Until the dialog is dismissed the page cancels every click on the form (the
    checkbox and button handlers never run), and the dialog appears a moment after
    DOMContentLoaded, so it has to be waited for. Declining is the privacy-preserving
    choice and is enough to unblock the calculator.
    """
    try:
        page.wait_for_selector("#qc-cmp2-ui .qc-cmp2-close-icon", state="visible", timeout=10000)
        page.click("#qc-cmp2-ui .qc-cmp2-close-icon")
        page.wait_for_timeout(800)
    except Exception:
        pass  # no dialog shown: nothing to dismiss


def _open_form(page, competenza: str) -> dict[str, int]:
    """Open the page, pick Tabelle 2022 and the competenza; return the phase map."""
    page.wait_for_timeout(1500)  # be gentle with the site between cases
    page.goto(_URL, timeout=60000, wait_until="domcontentloaded")
    _decline_consent(page)
    if page.eval_on_selector("select[name='Anno']", "e => e.value") != "2022":
        page.select_option("select[name='Anno']", "2022")
        page.wait_for_timeout(800)
    page.select_option("select[name='Competenza']", _COMP_MAP[competenza])
    page.wait_for_timeout(800)
    assert page.eval_on_selector("select[name='Anno']", "e => e.value") == "2022"
    return _site_phases(page)


def _js_click(page, selector: str):
    """Click through the element's own DOM click() (works also for the controls of
    the collapsed "Spese" tab, and is immune to sticky banners over the form)."""
    page.eval_on_selector(selector, "e => e.click()")
    page.wait_for_timeout(250)


def _site_notula(page, competenza, fasi, livello, spese_generali) -> dict:
    """Drive the site calculator and parse the result (phases + PROSPETTO FINALE)."""
    phases = _open_form(page, competenza)

    _js_click(page, f"input[name='VselAll'][value='{_LIVELLO_MAP[livello]}']")

    if fasi is not None:
        for name, idx in phases.items():
            if name not in fasi:
                _js_click(page, f"input[name='Fsel{idx}']")
                assert not page.is_checked(f"input[name='Fsel{idx}']")

    if not spese_generali:
        _js_click(page, "#B-Spese")
        if page.is_checked("input[name='DoSpeseGen']"):
            _js_click(page, "input[name='DoSpeseGen']")
        assert not page.is_checked("input[name='DoSpeseGen']")
    else:
        assert page.is_checked("input[name='DoSpeseGen']")
        assert page.eval_on_selector("input[name='PctSpeseGen']", "e => e.value") == "15"

    # "Includi accessori" ticks IVA and CPA together.
    _js_click(page, "#Btn-Accessori")
    assert page.is_checked("input[name='Iva']") and page.is_checked("input[name='Cpa']")
    assert not page.is_checked("input[name='DoRacc']")

    _js_click(page, "#Btn-Calcola")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)

    body = page.inner_text("body")
    assert "Tabelle: 2022" in body, "il sito non ha usato le tabelle 2022"

    res: dict = {
        "fasi": {},
        "compensi": None,
        "spese_generali": None,
        "cpa": None,
        "imponibile": None,
        "iva": None,
        "totale": None,
    }
    for line in body.splitlines():
        line = line.strip()
        m = _AMOUNT_RE.search(line)
        if not m:
            continue
        val = _euro(m.group(1))
        low = line.lower()
        if low.startswith("fase "):
            for prefix, name in _FASE_LABELS.items():
                if low.startswith(f"fase {prefix}") or low.startswith(f"fase di {prefix}"):
                    res["fasi"][name] = val
        elif low.startswith("compenso tabellare\t") or low.startswith("compenso tabellare €"):
            res["compensi"] = val
        elif low.startswith("spese generali"):
            res["spese_generali"] = val
        elif low.startswith("cassa avvocati"):
            res["cpa"] = val
        elif low.startswith("totale imponibile"):
            res["imponibile"] = val
        elif low.startswith("iva 22%"):
            res["iva"] = val
        elif low.startswith("ipotesi di compenso liquidabile"):
            res["totale"] = val
    return res


def _compare(tool: dict, site: dict, label: str, tol: float = _TOL):
    assert "errore" not in tool, tool
    tool_fasi = {f["fase"]: float(f["importo"]) for f in tool["fasi"]}
    pairs = [
        ("compensi", tool["totale_compensi"]),
        ("spese_generali", tool["spese_generali_15pct"]),
        ("cpa", tool["cpa_4pct"]),
        ("imponibile", tool["imponibile_iva"]),
        ("iva", tool["iva_22pct"]),
        ("totale", tool["totale"]),
    ]
    print(f"\n[{label}] tool={json.dumps({'fasi': tool_fasi, **dict(pairs)})} site={json.dumps(site)}")
    assert set(site["fasi"]) == set(tool_fasi), f"{label}: fasi sito {site['fasi']} vs tool {tool_fasi}"
    for fase, ours in tool_fasi.items():
        assert_close(ours, site["fasi"][fase], tolerance=tol, label=f"{label}_fase_{fase}")
    for key, ours in pairs:
        theirs = site[key]
        if theirs is None and key == "spese_generali":
            theirs = 0.0
        assert theirs is not None, f"{label}: voce '{key}' non trovata nel prospetto del sito"
        assert_close(ours, theirs, tolerance=tol, label=f"{label}_{key}")


class TestCalcoloNotulaPenaleComparison:

    def test_tribunale_monocratico_medio_con_spese_generali(self, page):
        """Plan case 1. Expected: compensi 3.592; SG 538,80; subtotale 4.130,80;
        CPA 165,23; imponibile 4.296,03; IVA 945,13; totale 5.241,16.
        DM 55/2014 art. 2 co. 2 + Tabella penale (DM 147/2022)."""
        args = dict(competenza="tribunale_monocratico", fasi=None, livello="medio",
                    spese_generali=True)
        _compare(_tool(**args), _site_notula(page, **args), "trib_mono_medio_sg")

    def test_cassazione_minimo_senza_spese_generali(self, page):
        """Plan case 2. Expected: compensi 473 + 1.323 + 1.371 = 3.167; CPA 126,68;
        IVA 724,61; totale 4.018,29. Tabella penale, Cassazione (3 phases, no istruttoria).
        Norms: DM 55/2014 art. 12 and Tabella penale (values as updated by DM 147/2022),
        SG omitted (art. 2 co. 2 is a flat refund the tool lets the user leave out);
        CPA 4% art. 11 L. 576/1980; IVA 22% DPR 633/1972."""
        args = dict(competenza="cassazione", fasi=None, livello="min", spese_generali=False)
        _compare(_tool(**args), _site_notula(page, **args), "cass_min_no_sg")

    def test_corte_assise_studio_decisionale_massimo(self, page):
        """Plan case 3. Expected: compensi 1.134 + 4.253 = 5.387; SG 808,05; CPA 247,80;
        IVA 1.417,43; totale 7.860,28. Phase subset (studio + decisionale) at the maximum.
        Norms: DM 55/2014 art. 12 and Tabella penale (values as updated by DM 147/2022);
        art. 2 co. 2 DM 55/2014 (SG 15%); CPA 4% art. 11 L. 576/1980; IVA 22% DPR 633/1972."""
        args = dict(competenza="corte_assise", fasi=["studio", "decisionale"], livello="max",
                    spese_generali=True)
        _compare(_tool(**args), _site_notula(page, **args), "assise_max_2fasi")

    def test_cassazione_fase_istruttoria_non_disponibile(self, page):
        """Plan case 4 (enumerated option at the limit). Expected: error, the istruttoria
        phase does not exist for the Cassazione in the Tabella penale. The site offers
        only studio / introduttiva / decisionale for Cassazione: both must refuse it.
        Norms: DM 55/2014 art. 12 and Tabella penale (DM 147/2022), Corte di Cassazione row:
        fase di studio, introduttiva and decisionale only."""
        res = _tool(competenza="cassazione", fasi=["istruttoria"], livello="medio",
                    spese_generali=True)
        assert "errore" in res and "istruttoria" in res["errore"], res
        phases = _open_form(page, "cassazione")
        assert set(phases) == {"studio", "introduttiva", "decisionale"}, phases

    def test_limite_arrotondamento_iva_mezzo_centesimo(self, page):
        """Limit case (rounding). Tribunale monocratico, studio + introduttiva + istruttoria
        at the minimum with SG: compensi 237 + 284 + 567 = 1.088; SG 163,20; CPA 50,05;
        imponibile 1.301,25; IVA 22% = 286,275 exactly -> 286,28 (half-up and half-even
        agree), totale 1.587,53. Probes the IVA rounding on an exact half cent: the tool
        rounds the binary float 286.27499999... and returns 286,27 / 1.587,52.
        Norms: DM 55/2014 art. 12 and Tabella penale (values as updated by DM 147/2022);
        art. 2 co. 2 DM 55/2014 (SG 15%); CPA 4% art. 11 L. 576/1980; IVA 22% DPR 633/1972."""
        args = dict(competenza="tribunale_monocratico",
                    fasi=["studio", "introduttiva", "istruttoria"], livello="min",
                    spese_generali=True)
        _compare(_tool(**args), _site_notula(page, **args), "trib_mono_min_3fasi_halfcent",
                 tol=_TOL_ROUNDING)

    def test_limite_giudice_pace_decisionale_mezzo_centesimo(self, page):
        """Limit case (rounding). Giudice di pace, only decisionale at the medium with SG:
        compensi 662; SG 99,30; CPA 30,45; imponibile 791,75; IVA = 174,185 exactly
        -> 174,19 half-up; totale 965,94.
        Norms: DM 55/2014 art. 12 and Tabella penale (values as updated by DM 147/2022);
        art. 2 co. 2 DM 55/2014 (SG 15%); CPA 4% art. 11 L. 576/1980; IVA 22% DPR 633/1972."""
        args = dict(competenza="giudice_pace", fasi=["decisionale"], livello="medio",
                    spese_generali=True)
        _compare(_tool(**args), _site_notula(page, **args), "gdp_medio_decisionale_halfcent",
                 tol=_TOL_ROUNDING)

    def test_giudice_pace_massimo_tutte_le_fasi(self, page):
        """Enumerated option (lowest court, top level). Giudice di pace, 4 phases at the
        maximum with SG: compensi 567 + 710 + 1.134 + 993 = 3.404; SG 510,60;
        subtotale 3.914,60; CPA 156,58; imponibile 4.071,18; IVA 895,66; totale 4.966,84.
        Norms: DM 55/2014 art. 12 and Tabella penale (values as updated by DM 147/2022);
        art. 2 co. 2 DM 55/2014 (SG 15%); CPA 4% art. 11 L. 576/1980; IVA 22% DPR 633/1972."""
        args = dict(competenza="giudice_pace", fasi=None, livello="max", spese_generali=True)
        _compare(_tool(**args), _site_notula(page, **args), "gdp_max_sg")

    def test_tribunale_collegiale_minimo_senza_spese_generali(self, page):
        """Enumerated option. Tribunale collegiale, 4 phases at the minimum without SG:
        compensi 237 + 378 + 709 + 709 = 2.033; CPA 81,32; imponibile 2.114,32;
        IVA 465,15; totale 2.579,47.
        Norms: DM 55/2014 art. 12 and Tabella penale (values as updated by DM 147/2022),
        SG omitted (art. 2 co. 2 is a flat refund the tool lets the user leave out);
        CPA 4% art. 11 L. 576/1980; IVA 22% DPR 633/1972."""
        args = dict(competenza="tribunale_collegiale", fasi=None, livello="min",
                    spese_generali=False)
        _compare(_tool(**args), _site_notula(page, **args), "trib_coll_min_no_sg")

    def test_corte_appello_medio_con_spese_generali(self, page):
        """Enumerated option. Corte d'appello (site value 600, not "Corte d'Assise
        d'Appello"), 4 phases at the medium with SG: compensi 473 + 945 + 1.418 + 1.418
        = 4.254; SG 638,10; subtotale 4.892,10; CPA 195,68; imponibile 5.087,78;
        IVA 1.119,31; totale 6.207,09.
        Norms: DM 55/2014 art. 12 and Tabella penale (values as updated by DM 147/2022);
        art. 2 co. 2 DM 55/2014 (SG 15%); CPA 4% art. 11 L. 576/1980; IVA 22% DPR 633/1972."""
        args = dict(competenza="corte_appello", fasi=None, livello="medio",
                    spese_generali=True)
        _compare(_tool(**args), _site_notula(page, **args), "app_medio_sg")

    def test_tabelle_2014_non_supportate(self, page):
        """Different table year. The site also offers the 2014-2018 tables (pre DM 147/2022);
        the tool has no year parameter and applies only the DM 147/2022 values.
        Norms: tables before DM 147/2022 (DM 55/2014 and its 2018 amendment, labelled
        "2014-2018" on the site) vs the DM 147/2022 values the tool applies."""
        pytest.skip("non confrontabile: il tool non offre le tabelle 2014-2018 (solo DM 147/2022)")
