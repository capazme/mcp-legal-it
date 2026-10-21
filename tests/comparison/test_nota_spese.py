"""Comparison tests: nota_spese vs avvocatoandreani.it (calcolo fattura studio legale).

Site page: calcolo_fattura_studio_legale.php ("Calcolo Fattura per Avvocati e Studi
Legali"). The site has no per-item interface, so the tool's items are folded into
the site's three amounts:

- ``compenso`` items            -> "Onorari €" (field ``Importo``)
- ``spese_vive`` / ``spese_documentate`` items -> "Spese Esenti €" (``SpeseEsenti``,
  art. 15 DPR 633/1972: outside CPA and IVA)
- a ``spese_generali_15pct`` item whose base equals the compensi total -> the
  "Spese Generali" checkbox ticked at 15% (the site always computes them on the
  onorari); no such item -> checkbox unticked.

"Spese Imponibili" (``SpeseNonEsenti``) stays at zero: the tool has no item type for
taxable expenses. "Ritenuta d'Acconto" is unticked because the tool does not compute
it; the comparison is on the "Totale documento", i.e. before the ritenuta.

Norms: DM 55/2014 art. 2 co. 2 (spese generali 15% of the compenso); CPA 4%
(art. 11 L. 576/1980); IVA 22% (art. 16 DPR 633/1972) on compensi + spese generali
+ CPA; spese anticipate in nome e per conto del cliente excluded from the IVA base
(art. 15 co. 1 n. 3 DPR 633/1972).

Tolerance: 0.01 EUR on every amount (brief). No year-dependent table is involved:
the percentages are fixed by law, the site offers no year selector.
"""

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

_PAGE = "calcolo_fattura_studio_legale.php"
_TOL = 0.01
# Half-cent rounding cases are compared to the cent (tolerance 0): with a 1-cent
# tolerance they would hide exactly the rounding they are there to probe. This is
# narrower than the brief's tolerance, never wider.
_TOL_ROUNDING = 0.0
# Float noise only: 115.23 - 115.22 == 0.010000000000005116 in binary floating point,
# which would turn a difference of exactly one cent into a failure at _TOL = 0.01.
_EPS = 1e-9

# Site result row label (prefix) -> key used by the comparison.
_SITE_ROWS = {
    "Onorari": "onorari",
    "Spese generali": "spese_generali",
    "Spese imponibili": "spese_imponibili",
    "Cassa Avvocati": "cpa",
    "Totale imponibile": "imponibile",
    "IVA": "iva",
    "Spese esenti": "spese_esenti",
    "Totale documento": "totale",
}


def _tool(voci: list[dict]) -> dict:
    from src.tools.fatturazione_avvocati import nota_spese

    fn = getattr(nota_spese, "fn", nota_spese)
    return fn(voci=voci)


def _it(amount: float) -> str:
    """1000.1 -> '1000,10' (the site's text fields take the Italian decimal comma)."""
    return f"{amount:.2f}".replace(".", ",")


def _site_inputs(voci: list[dict]) -> tuple[float, float, bool]:
    """Fold the tool items into (onorari, spese esenti, spese generali on/off)."""
    onorari = round(sum(v["importo"] for v in voci if v["tipo"] == "compenso"), 2)
    esenti = round(
        sum(v["importo"] for v in voci if v["tipo"] in ("spese_vive", "spese_documentate")), 2
    )
    basi_sg = [v["importo"] for v in voci if v["tipo"] == "spese_generali_15pct"]
    if basi_sg and round(sum(basi_sg), 2) != onorari:
        pytest.skip(
            "Non confrontabile: il sito calcola le spese generali solo sul totale degli "
            "onorari, la voce spese_generali_15pct del tool ha una base diversa"
        )
    return onorari, esenti, bool(basi_sg)


def _set_checkbox(page, name: str, checked: bool) -> None:
    """Set a checkbox through its ``checked`` property, then run its onclick handler.

    Clicks do not work reliably on this page: a document-level capture listener
    (third-party script) swallows synthetic clicks and a coordinate click can land on
    an ad overlay. The form is posted to the server, which reads only the submitted
    state, so the property is set directly; the page's own handler (e.g.
    ``OnClickDoSpeseGen``, which enables or disables the percentage field) still runs.
    """
    page.evaluate(
        """([n, v]) => {
            const e = document.getElementsByName(n)[0];
            e.checked = v;
            if (typeof e.onclick === 'function') e.onclick.call(e);
        }""",
        [name, checked],
    )
    assert page.is_checked(f"input[name='{name}']") == checked, f"checkbox {name} non impostata"


_CMP = "#qc-cmp2-container, .qc-cmp2-container, .qc-cmp-cleanslate"


def _remove_cmp(page, wait_ms: int = 0) -> None:
    """Remove the Quantcast consent dialog without answering it.

    The dialog is injected asynchronously, often after ``goto`` has already removed
    it, and then sits over the "Calcola" button: wait for it (up to ``wait_ms``) and
    drop it from the DOM. No consent choice is recorded.
    """
    if wait_ms:
        try:
            page.wait_for_selector(_CMP, state="attached", timeout=wait_ms)
        except Exception:
            pass
    page.evaluate(f'document.querySelectorAll("{_CMP}").forEach(el => el.remove())')


def _site(page, onorari: float, esenti: float, spese_generali: bool) -> dict:
    """Drive the site form and return the 'DETTAGLIO FATTURA' rows as floats."""
    page.wait_for_timeout(1500)  # space the requests to the site
    goto(page, _PAGE)
    _remove_cmp(page, wait_ms=4000)
    page.fill("input[name='Importo']", _it(onorari))
    page.fill("input[name='SpeseEsenti']", _it(esenti))
    page.fill("input[name='SpeseNonEsenti']", "0,00")
    _set_checkbox(page, "DoSpeseGen", spese_generali)
    if spese_generali:
        page.fill("input[name='PctSpeseGen']", "15")
    _set_checkbox(page, "DoRacc", False)
    _remove_cmp(page)
    # A third-party capture listener swallows even trusted clicks on "Calcola" (no POST
    # leaves the page), so the form is submitted with the button as submitter: the
    # server receives exactly what a click would send (Op=Calcola + the fields).
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "() => document.forms['Fattura'].requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_timeout(2000)

    tables = [
        t.inner_text() for t in page.query_selector_all("table")
        if "DETTAGLIO FATTURA" in t.inner_text()
    ]
    assert tables, "Il sito non ha restituito il DETTAGLIO FATTURA"
    rows = {key: 0.0 for key in _SITE_ROWS.values()}
    for line in tables[-1].splitlines():
        if "\t" not in line or "€" not in line:
            continue
        label, amount = line.rsplit("\t", 1)
        for prefix, key in _SITE_ROWS.items():
            if label.strip().startswith(prefix):
                rows[key] = parse_euro(amount)
                break
    return rows


def _compare(tool: dict, site: dict, tol: float = _TOL) -> None:
    """Assert every amount, collecting all the differences before failing."""
    pairs = [
        ("compensi / onorari", tool["totale_compensi"], site["onorari"]),
        ("spese generali 15%", tool["totale_spese_generali_15pct"], site["spese_generali"]),
        ("CPA 4%", tool["cpa_4pct"], site["cpa"]),
        ("imponibile IVA", tool["imponibile_iva"], site["imponibile"]),
        ("IVA 22%", tool["iva_22pct"], site["iva"]),
        ("spese esenti", tool["totale_spese_vive"], site["spese_esenti"]),
        ("totale", tool["totale_nota_spese"], site["totale"]),
    ]
    errors = []
    for label, ours, theirs in pairs:
        try:
            assert_close(ours, theirs, tolerance=tol + _EPS, label=label)
        except AssertionError as exc:
            errors.append(str(exc))
    assert not errors, "; ".join(errors)


def _run(page, voci: list[dict], tol: float = _TOL) -> None:
    tool = _tool(voci)
    assert "errore" not in tool, tool
    onorari, esenti, sg = _site_inputs(voci)
    site = _site(page, onorari, esenti, sg)
    print(f"tool={tool}\nsito={site}")
    _compare(tool, site, tol)


# --- Cases from the plan -------------------------------------------------------


def test_piano_compensi_spese_generali_contributo_unificato(page):
    """Piano: compensi 1.696; spese generali 254,40; subtotale 1.950,40; CPA 78,02;
    imponibile IVA 2.028,42; IVA 446,25; spese esenti 237,00; totale 2.711,67.
    Norma: DM 55/2014 art. 2 co. 2; art. 15 DPR 633/1972 per il contributo unificato."""
    _run(page, [
        {"descrizione": "Fase di studio", "importo": 919, "tipo": "compenso"},
        {"descrizione": "Fase introduttiva", "importo": 777, "tipo": "compenso"},
        {"descrizione": "Base spese generali", "importo": 1696, "tipo": "spese_generali_15pct"},
        {"descrizione": "Contributo unificato", "importo": 237, "tipo": "spese_vive"},
    ])


def test_piano_solo_spese_esenti(page):
    """Piano: totale 125,00; CPA e IVA a zero (onorari zero, caso degenere).
    Norma: art. 15 DPR 633/1972 (anticipazioni escluse dalla base IVA); art. 30
    DPR 115/2002 (anticipazioni forfettarie 27 euro)."""
    _run(page, [
        {"descrizione": "Contributo unificato", "importo": 98, "tipo": "spese_vive"},
        {"descrizione": "Anticipazioni forfettarie art. 30 DPR 115/2002", "importo": 27,
         "tipo": "spese_documentate"},
    ])


def test_piano_compenso_e_spese_generali_stessa_base(page):
    """Piano: spese generali 150,00; subtotale 1.150,00; CPA 46,00; IVA 263,12;
    totale 1.459,12. Norma: DM 55/2014 art. 2 co. 2."""
    _run(page, [
        {"descrizione": "Compenso", "importo": 1000, "tipo": "compenso"},
        {"descrizione": "Base spese generali", "importo": 1000, "tipo": "spese_generali_15pct"},
    ])


def test_piano_tipo_voce_non_ammesso():
    """Piano: errore 'tipo voce non valido'. Il sito non ha tipi di voce: si verifica
    solo l'errore del tool, poi il caso e' dichiarato non confrontabile."""
    r = _tool([{"descrizione": "Compenso", "importo": 1000, "tipo": "altro"}])
    assert "errore" in r and "Tipo voce non valido" in r["errore"], r
    pytest.skip("Non confrontabile: il sito non ha tipi di voce da validare")


# --- Boundary cases ---------------------------------------------------------------


def test_limite_senza_spese_generali(page):
    """Opzione enumerata: nessuna voce spese_generali_15pct -> checkbox 'Spese Generali'
    non spuntata. Atteso: compensi 800; CPA 32,00; imponibile 832,00; IVA 183,04;
    totale 1.015,04. Norma: CPA 4% art. 11 L. 576/1980; IVA 22%."""
    _run(page, [
        {"descrizione": "Compenso fase studio", "importo": 500, "tipo": "compenso"},
        {"descrizione": "Compenso fase introduttiva", "importo": 300, "tipo": "compenso"},
    ])


def test_limite_arrotondamento_spese_generali_mezzo_centesimo(page):
    """Arrotondamento: 15% di 1.000,10 = 150,015 esatti, a meta' centesimo.
    Atteso (arrotondamento commerciale al centesimo): spese generali 150,02;
    CPA 46,00; imponibile 1.196,12; IVA 263,15; totale 1.459,27.
    Norma: DM 55/2014 art. 2 co. 2 (15%)."""
    _run(page, [
        {"descrizione": "Compenso", "importo": 1000.10, "tipo": "compenso"},
        {"descrizione": "Base spese generali", "importo": 1000.10, "tipo": "spese_generali_15pct"},
    ], tol=_TOL_ROUNDING)


def test_limite_arrotondamento_iva_mezzo_centesimo(page):
    """Arrotondamento: compenso 503,61, CPA 20,14, imponibile 523,75; IVA 22% =
    115,225 esatti, a meta' centesimo. Atteso: IVA 115,23; totale 638,98.
    Norma: art. 16 DPR 633/1972 (aliquota 22%)."""
    _run(page, [
        {"descrizione": "Compenso", "importo": 503.61, "tipo": "compenso"},
    ], tol=_TOL_ROUNDING)


def test_limite_arrotondamento_passaggi_intermedi(page):
    """Arrotondamento dei passaggi intermedi: onorari 1.999,90. Arrotondando ogni riga
    (spese generali 299,99; CPA 92,00; imponibile 2.391,89; IVA 526,22) il totale e'
    2.918,11; senza arrotondamenti intermedi sarebbe 2.918,09. Norma: DM 55/2014
    art. 2 co. 2; CPA 4%; IVA 22%."""
    _run(page, [
        {"descrizione": "Compenso", "importo": 1999.90, "tipo": "compenso"},
        {"descrizione": "Base spese generali", "importo": 1999.90, "tipo": "spese_generali_15pct"},
    ], tol=_TOL_ROUNDING)


def test_importi_elevati_con_spese_vive_e_documentate(page):
    """Importi a sei cifre (separatore delle migliaia) e somma di spese vive e documentate.
    Atteso: compensi 123.456,78; spese generali 18.518,52; CPA 5.679,01; imponibile
    147.654,31; IVA 32.483,95; spese esenti 1.234,56; totale 181.372,82.
    Norma: DM 55/2014 art. 2 co. 2; art. 15 DPR 633/1972."""
    _run(page, [
        {"descrizione": "Compenso fasi di merito", "importo": 100000, "tipo": "compenso"},
        {"descrizione": "Compenso fase esecutiva", "importo": 23456.78, "tipo": "compenso"},
        {"descrizione": "Base spese generali", "importo": 123456.78, "tipo": "spese_generali_15pct"},
        {"descrizione": "Contributo unificato", "importo": 1214, "tipo": "spese_vive"},
        {"descrizione": "Notifiche", "importo": 20.56, "tipo": "spese_documentate"},
    ])


def test_spese_generali_su_base_diversa_dai_compensi():
    """La voce spese_generali_15pct con base diversa dai compensi (qui 500 su compensi
    1.000) non ha corrispondente sul sito, che calcola il 15% sempre sugli onorari.
    Norma: DM 55/2014 art. 2 co. 2 (15% 'del compenso totale per la prestazione')."""
    voci = [
        {"descrizione": "Compenso", "importo": 1000, "tipo": "compenso"},
        {"descrizione": "Base spese generali parziale", "importo": 500,
         "tipo": "spese_generali_15pct"},
    ]
    r = _tool(voci)
    assert r["totale_spese_generali_15pct"] == 75.0, r
    _site_inputs(voci)  # skips: not comparable
