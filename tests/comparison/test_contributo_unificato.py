"""Comparison tests: contributo_unificato vs avvocatoandreani.it.

Primary page: /servizi/calcolo_contributo_unificato.php. The calculator has
  - Processo: 1 Civile, 2 Tributario, 3 Amministrativo
  - Giudizio: 1 Primo grado, 2 Impugnazione, 3 Cassazione
  - TipoValore: 0 valore determinato (ValoreCausa, decimal comma), 2 non indicato,
    1 indeterminabile (answers with a small table instead of a single amount)
  - Riduzione: "riduzione del 50%" checkbox (art. 13 co. 3 DPR 115/2002)
  - a second button "Procedimenti con Contributo Fisso" listing the flat amounts.
The calculator has no "monitorio", "lavoro", "cautelari" or "opposizione a decreto
ingiuntivo" option: the site models all of them as the civil scale with the 50%
reduction ticked (its own notes list them as the reduced cases), so the driver
does the same. Execution, family and voluntary-jurisdiction flat amounts come
from the "Procedimenti con Contributo Fisso" list of the same calculator.

Secondary page: /servizi/tabella-contributo-unificato.php (published 2026 table),
used for the full sweep of the civil and tax scales and for the site's note on
labour cases in Cassazione.

Norms: DPR 115/2002, art. 13 co. 1 (civil scale), co. 1-bis (+50% on appeal,
x2 in Cassazione), co. 2 (executions, opposition to enforcement acts), co. 3
(half for summary procedures, opposition to injunction, labour), co. 6-bis
(administrative), co. 6-quater (tax); art. 9 co. 1-bis (labour and welfare:
exempt up to three times the art. 76 income threshold).

Tolerance: 0,01 euro on every amount (brief). No wider tolerance is used.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

TOL = 0.01
CALC = "calcolo_contributo_unificato.php"
TABELLA_URL = "https://www.avvocatoandreani.it/servizi/tabella-contributo-unificato.php"

PROCESSO = {"civile": "1", "tributario": "2", "amministrativo": "3"}
GIUDIZIO = {"primo": "1", "appello": "2", "cassazione": "3"}
# TipoValore radio values on the site
DETERMINATO, INDETERMINABILE = "0", "1"


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    # The tool is not "as of today", but the table vintage check reads the clock:
    # pin it so the run is reproducible (brief: today is 2026-09-25).
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-25")


# --------------------------------------------------------------------------- tool

def _tool(**kwargs) -> float:
    import src.server  # noqa: F401  (registers every module, avoids circular imports)
    from src.tools.atti_giudiziari import contributo_unificato

    fn = getattr(contributo_unificato, "fn", contributo_unificato)
    out = fn(**kwargs)
    assert "errore" not in out, f"tool error for {kwargs}: {out.get('errore')}"
    return out["importo_dovuto"]


# --------------------------------------------------------------------------- site

def _euro_it(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def _press(page, selector: str):
    """Submit the calculator form with `selector` as the submitter and wait for the result.

    A pointer click on the button (even with force=True, or element.click() from JS) is
    intermittently swallowed on this page -- the ad/consent scripts attach click handlers
    at load time -- and the form is then never posted. form.requestSubmit(button) fires
    the form's own submit with the button's name/value pair, without a click event.
    """
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.eval_on_selector(selector, "b => b.form.requestSubmit(b)")
    page.wait_for_timeout(2000)


def _submit(page, processo: str, giudizio: str, tipo_valore: str, valore=None, riduzione=False):
    """Set every field of the form explicitly and submit it.

    The fields are set on the form object itself (a click on a radio or a checkbox can be
    cancelled by the same handlers that swallow the button click); OnClickTipoValore() is
    the page's own handler that enables ValoreCausa only for a determined value.
    """
    goto(page, CALC)
    page.evaluate(
        """([proc, giud, tipo, val, rid]) => {
            const f = document.ContributoUnificato;
            f.Processo.value = proc;
            f.Giudizio.value = giud;
            for (const r of f.TipoValore) r.checked = (r.value === tipo);
            OnClickTipoValore();
            if (tipo === "0") f.ValoreCausa.value = val;
            f.Riduzione.checked = rid;
        }""",
        [PROCESSO[processo], GIUDIZIO[giudizio], tipo_valore,
         _euro_it(valore) if valore is not None else "", riduzione],
    )
    _press(page, "#btn-calc")
    # the result page re-renders the form with the posted values: check the site read ours
    echo = page.evaluate(
        """() => { const f = document.ContributoUnificato;
            return [f.Processo.value, f.Giudizio.value,
                    [...f.TipoValore].filter(r => r.checked).map(r => r.value)[0] || "",
                    f.Riduzione.checked, f.ValoreCausa.value]; }"""
    )
    assert echo[:4] == [PROCESSO[processo], GIUDIZIO[giudizio], tipo_valore, riduzione], (
        f"site echoed {echo} for {processo=} {giudizio=} {tipo_valore=} {riduzione=}"
    )
    if tipo_valore == DETERMINATO:
        assert abs(parse_euro(echo[4]) - valore) < 0.005, f"site read {echo[4]!r} for {valore}"


def _site_calc(page, valore: float, processo="civile", giudizio="primo", riduzione=False) -> float:
    """Amount of the calculator with a determined value ('Il contributo è € 43,00')."""
    _submit(page, processo, giudizio, DETERMINATO, valore, riduzione)
    texts = [e.inner_text() for e in page.query_selector_all(".result")]
    for t in texts:
        m = re.search(r"contributo\s+è\s+€\s*([\d.]+,\d{2})", t, re.IGNORECASE)
        if m:
            return parse_euro(m.group(1))
    raise AssertionError(f"no amount in site result for {valore=} {processo=} {giudizio=}: {texts}")


def _rows(text: str) -> dict:
    """'label<TAB>€ 1.234,56' (or 'esente') lines -> {label: amount}; first amount per row."""
    out = {}
    for line in text.splitlines():
        if "\t" not in line:
            continue
        label, _, rest = line.strip().partition("\t")
        first = rest.split("\t")[0].strip()
        if first.lower() == "esente":
            out[label.strip()] = 0.0
        elif re.fullmatch(r"€\s*[\d.]+,\d{2}", first):
            out[label.strip()] = parse_euro(first)
        else:
            out[label.strip()] = first
    return out


def _site_indeterminabile(page, processo: str, giudizio: str) -> dict:
    """The calculator answers 'valore indeterminabile' with a table of flat amounts."""
    _submit(page, processo, giudizio, INDETERMINABILE)
    body = page.inner_text("body")
    i = body.find("Consulta anche la tabella completa")
    j = body.find("Il contributo unificato è ridotto del 50%", i)
    assert i >= 0 and j > i, "indeterminable-value table not found on the site"
    return _rows(body[i:j])


def _lookup(rows: dict, prefix: str):
    hits = [v for k, v in rows.items() if k.startswith(prefix)]
    assert hits, f"row starting with {prefix!r} not found on the site; rows: {list(rows)}"
    return hits[0]


@pytest.fixture(scope="module")
def site_fissi(browser):
    """'Procedimenti con Contributo Fisso' list of the calculator (one request per module)."""
    ctx = browser.new_context()
    pg = ctx.new_page()
    try:
        goto(pg, CALC)
        _press(pg, "input[name='Button'][value='Procedimenti con Contributo Fisso']")
        body = pg.inner_text("body")
    finally:
        pg.close()
        ctx.close()
    i = body.find("Consulta anche la tabella completa")
    j = body.find("Il contributo unificato è ridotto del 50%", i)
    assert i >= 0 and j > i, "flat-amount list not found on the site"
    return _rows(body[i:j])


@pytest.fixture(scope="module")
def site_tabella(browser):
    """Body text of the published 2026 table (one request per module)."""
    ctx = browser.new_context()
    pg = ctx.new_page()
    try:
        pg.goto(TABELLA_URL, timeout=60000, wait_until="domcontentloaded")
        accept_cookies(pg)
        pg.wait_for_timeout(1500)
        body = pg.inner_text("body")
    finally:
        pg.close()
        ctx.close()
    assert "TABELLA del CONTRIBUTO UNIFICATO" in body
    return body


_ROW = re.compile(
    r"^Valore (?:fino a € (?P<u1>[\d.]+,\d{2})"
    r"|superiore a € (?P<l>[\d.]+,\d{2})(?: e fino a € (?P<u2>[\d.]+,\d{2}))?)"
    r"\s+€ (?P<imp>[\d.]+,\d{2})$"
)


def _scaglioni(body: str, heading: str) -> list[tuple[float | None, float | None, float]]:
    """(lower, upper, amount) rows of the scale printed under `heading`."""
    lines = [ln.strip() for ln in body.splitlines()]
    for idx, ln in enumerate(lines):
        if ln != heading:
            continue
        nxt = [x for x in lines[idx + 1: idx + 4] if x]
        if not nxt or not nxt[0].startswith("Valore della Causa"):
            continue  # table of contents entry, not the table
        rows = []
        for x in lines[idx + 2:]:
            if not x:
                if rows:
                    break
                continue
            m = _ROW.match(x)
            if not m:
                break
            low = parse_euro(m["l"]) if m["l"] else None
            up = m["u1"] or m["u2"]
            rows.append((low, parse_euro(up) if up else None, parse_euro(m["imp"])))
        return rows
    raise AssertionError(f"scale {heading!r} not found on the published table")


# =========================================================================== tests
# --- 1. Civil scale, first grade, on the calculator (art. 13 co. 1) -------------

@pytest.mark.parametrize(
    "valore, atteso",
    [
        # plan: confine del primo scaglione -> 43,00 (lett. a: fino a 1.100)
        pytest.param(1100.00, 43.0, id="1100-confine-lett-a"),
        # plan: appena sopra il primo confine -> 98,00 (lett. b); the site accepts decimals
        pytest.param(1100.01, 98.0, id="1100.01-lett-b"),
        # added: exact upper bound of lett. b -> 98,00 (the "fino a" bound is inclusive)
        pytest.param(5200.00, 98.0, id="5200-confine-lett-b"),
        # plan: appena sopra 26.000 -> 518,00 (lett. d: oltre 26.000 e fino a 52.000)
        pytest.param(26000.01, 518.0, id="26000.01-lett-d"),
        # previous file: interior values of lett. d and lett. e
        pytest.param(50000.00, 518.0, id="50000-lett-d"),
        pytest.param(200000.00, 759.0, id="200000-lett-e"),
        # added: exact upper bound of lett. f -> 1.214,00
        pytest.param(520000.00, 1214.0, id="520000-confine-lett-f"),
        # plan: ultimo scaglione -> 1.686,00 (lett. g)
        pytest.param(520000.01, 1686.0, id="520000.01-lett-g"),
    ],
)
def test_cognizione_primo_grado(page, valore, atteso):
    ours = _tool(valore_causa=valore, tipo_procedimento="cognizione", grado="primo")
    site = _site_calc(page, valore, "civile", "primo")
    assert_close(ours, site, TOL, f"cognizione primo {valore}")


# --- 2. Appeal and Cassazione multipliers (art. 13 co. 1-bis) -------------------

@pytest.mark.parametrize(
    "valore, grado, atteso",
    [
        # plan: appello, scaglione 26.000-52.000 -> 777,00 (518 aumentato della metà, co. 1-bis)
        pytest.param(30000.00, "appello", 777.0, id="appello-30000"),
        # added: appello just above the first bound -> 147,00 (98 x 1,5)
        pytest.param(1100.01, "appello", 147.0, id="appello-1100.01"),
        # plan: Cassazione, ultimo scaglione -> 3.372,00 (1.686 raddoppiato, co. 1-bis)
        pytest.param(600000.00, "cassazione", 3372.0, id="cassazione-600000"),
        # added: Cassazione at the 26.000 bound -> 474,00 (237 x 2)
        pytest.param(26000.00, "cassazione", 474.0, id="cassazione-26000-confine"),
    ],
)
def test_cognizione_impugnazioni(page, valore, grado, atteso):
    ours = _tool(valore_causa=valore, tipo_procedimento="cognizione", grado=grado)
    site = _site_calc(page, valore, "civile", grado)
    assert_close(ours, site, TOL, f"cognizione {grado} {valore}")


# --- 3. Reduced to half (art. 13 co. 3): site = civil scale + "riduzione del 50%" ----

@pytest.mark.parametrize(
    "tipo, valore, atteso",
    [
        # plan: monitorio al confine di 5.200 -> 49,00 (98 ridotto alla metà, co. 3)
        pytest.param("monitorio", 5200.00, 49.0, id="monitorio-5200-confine"),
        # added: opposizione a decreto ingiuntivo in primo grado -> 259,00 (518/2, co. 3)
        pytest.param("opposizione_decreto_ingiuntivo", 30000.00, 259.0, id="opposizione-di-30000"),
        # added: cautelari in the last scale -> 843,00 (1.686/2, co. 3: libro IV titolo I c.p.c.)
        pytest.param("cautelari", 520000.01, 843.0, id="cautelari-520000.01"),
    ],
)
def test_procedimenti_ridotti(page, tipo, valore, atteso):
    ours = _tool(valore_causa=valore, tipo_procedimento=tipo, grado="primo")
    site = _site_calc(page, valore, "civile", "primo", riduzione=True)
    assert_close(ours, site, TOL, f"{tipo} {valore}")


# --- 4. Labour and welfare (art. 9 co. 1-bis) -----------------------------------

def test_lavoro_primo_oltre_soglia(page):
    # plan: lavoro, primo grado, reddito oltre tre volte la soglia dell'art. 76 -> 259,00
    # (art. 9 co. 1-bis and art. 13 co. 3: half of 518). The site has no labour option:
    # its notes list labour cases among the 50% reductions, so civil scale + riduzione.
    ours = _tool(valore_causa=30000, tipo_procedimento="lavoro", grado="primo",
                 reddito_oltre_soglia_lavoro=True)
    site = _site_calc(page, 30000.00, "civile", "primo", riduzione=True)
    assert_close(ours, site, TOL, "lavoro primo oltre soglia")


def test_lavoro_appello_oltre_soglia(page):
    # added (opzione enumerata grado): labour appeal above the threshold -> 388,50
    # (518/2 = 259, +50% on appeal ex co. 1-bis). Site: Impugnazione + riduzione.
    ours = _tool(valore_causa=30000, tipo_procedimento="lavoro", grado="appello",
                 reddito_oltre_soglia_lavoro=True)
    site = _site_calc(page, 30000.00, "civile", "appello", riduzione=True)
    assert_close(ours, site, TOL, "lavoro appello oltre soglia")


def test_lavoro_cassazione_oltre_soglia(page, site_tabella):
    # plan: "da leggere dal sito" -- art. 9 co. 1-bis: in Cassazione the contribution is due
    # "nella misura di cui all'art. 13, comma 1"; the tool doubles it ex co. 1-bis -> 1.036,00.
    # The site's table (note 3 on labour) says: in Cassazione the ordinary table applies
    # without reductions, so the driver uses Civile / Cassazione without the 50% box.
    assert "si applica la tabella ordinaria senza riduzioni" in site_tabella
    ours = _tool(valore_causa=30000, tipo_procedimento="lavoro", grado="cassazione",
                 reddito_oltre_soglia_lavoro=True)
    site = _site_calc(page, 30000.00, "civile", "cassazione", riduzione=False)
    assert_close(ours, site, TOL, "lavoro cassazione oltre soglia")


# --- 5. Tax process (art. 13 co. 6-quater) --------------------------------------

@pytest.mark.parametrize(
    "valore, grado, atteso",
    [
        # added: exact upper bound of the first tax bracket -> 30,00 (lett. a: fino a 2.582,28)
        pytest.param(2582.28, "primo", 30.0, id="2582.28-confine-lett-a"),
        # plan: tributario appena sopra 2.582,28 -> 60,00 (co. 6-quater lett. b)
        pytest.param(2582.29, "primo", 60.0, id="2582.29-lett-b"),
        # added: last tax bracket -> 1.500,00 (oltre 200.000)
        pytest.param(200000.01, "primo", 1500.0, id="200000.01-ultimo"),
        # plan: tributario in appello -> 250,00 (same amounts before the second-degree court)
        pytest.param(50000.00, "appello", 250.0, id="appello-50000"),
        # plan: tributario in Cassazione (voce aperta par. 7) -> tool 1.036,00 (civil scale x2);
        # the site's table: "per i ricorsi in cassazione in materia tributaria il contributo
        # unificato si applica nella misura prevista per il processo civile"
        pytest.param(50000.00, "cassazione", 1036.0, id="cassazione-50000"),
    ],
)
def test_tributario(page, valore, grado, atteso):
    ours = _tool(valore_causa=valore, tipo_procedimento="tributario", grado=grado)
    site = _site_calc(page, valore, "tributario", grado)
    assert_close(ours, site, TOL, f"tributario {grado} {valore}")


# --- 6. Indeterminable value (art. 13 co. 1 lett. c/d and co. 6-bis) ------------

@pytest.mark.parametrize("grado", ["primo", "appello", "cassazione"])
def test_valore_indeterminabile_civile(page, grado):
    # added (opzione enumerata): tribunale 518 / 777 / 1.036 (lett. d, co. 1-bis);
    # giudice di pace 237 / 355,50 / 474 (lett. c). The site answers with both rows.
    rows = _site_indeterminabile(page, "civile", grado)
    tribunale = _lookup(rows, "Processi civili di valore indeterminabile")
    gdp = _lookup(rows, "Processi contenziosi di competenza esclusiva del Giudice di Pace")
    ours_trib = _tool(valore_causa=0, tipo_procedimento="valore_indeterminabile", grado=grado)
    ours_gdp = _tool(valore_causa=0, tipo_procedimento="valore_indeterminabile_gdp", grado=grado)
    assert_close(ours_trib, tribunale, TOL, f"indeterminabile tribunale {grado}")
    assert_close(ours_gdp, gdp, TOL, f"indeterminabile giudice di pace {grado}")


@pytest.mark.parametrize(
    "grado, atteso",
    [
        # added: TAR, first grade -> 650,00 (co. 6-bis lett. e)
        pytest.param("primo", 650.0, id="tar-primo"),
        # added: Consiglio di Stato -> 975,00 (+50%, art. 1 co. 27 L. 228/2012)
        pytest.param("appello", 975.0, id="tar-appello"),
        # plan: TAR in Cassazione -> "errore atteso: la combinazione non corrisponde a nessuna
        # voce dell'art. 13 (art. 111 co. 8 Cost.); il tool restituisce 1.300,00".
        # The site answers 1.300,00 too (650 x 2): recorded as is, the legal point is for phase 2.
        pytest.param("cassazione", 1300.0, id="tar-cassazione"),
    ],
)
def test_tar_valore_indeterminabile(page, grado, atteso):
    rows = _site_indeterminabile(page, "amministrativo", grado)
    site = _lookup(rows, "Processi amministrativi di valore indeterminabile")
    ours = _tool(valore_causa=0, tipo_procedimento="tar", grado=grado)
    assert_close(ours, site, TOL, f"tar {grado}")


# --- 7. Flat amounts and exemptions ("Procedimenti con Contributo Fisso") --------

@pytest.mark.parametrize(
    "prefix, kwargs",
    [
        # plan: esecuzione mobiliare appena sotto 2.500 -> 43,00 (art. 13 co. 2)
        pytest.param("Procedimenti esecutivi mobiliari di valore inferiore ad Euro 2.500,00",
                     dict(valore_causa=2499.99, tipo_procedimento="esecuzione_mobiliare"),
                     id="esec-mobiliare-2499.99"),
        # plan: esecuzione mobiliare a 2.500 -> 139,00 (co. 2: valore "pari o superiore")
        pytest.param("Procedimenti esecutivi mobiliari di valore superiore o uguale a Euro 2.500,00",
                     dict(valore_causa=2500, tipo_procedimento="esecuzione_mobiliare"),
                     id="esec-mobiliare-2500-confine"),
        # added: esecuzione immobiliare -> 278,00 (co. 2)
        pytest.param("Procedimenti di esecuzione immobiliare",
                     dict(valore_causa=100000, tipo_procedimento="esecuzione_immobiliare"),
                     id="esec-immobiliare"),
        # added: opposizione agli atti esecutivi -> 168,00 (co. 2, ultimo periodo)
        pytest.param("Procedimenti di opposizione agli atti esecutivi",
                     dict(valore_causa=0, tipo_procedimento="opposizione_atti_esecutivi"),
                     id="opposizione-atti-esecutivi"),
        # added: volontaria giurisdizione -> 98,00 (co. 1 lett. b)
        pytest.param("Procedimenti di volontaria giurisdizione",
                     dict(valore_causa=0, tipo_procedimento="volontaria_giurisdizione"),
                     id="volontaria-giurisdizione"),
        # added: separazione giudiziale -> 98,00
        pytest.param("Procedimenti di cui al titolo II, capo I e capo VI libro IV c.p.c: "
                     "della separazione personale dei coniugi",
                     dict(valore_causa=0, tipo_procedimento="separazione_giudiziale"),
                     id="separazione-giudiziale"),
        # added: divorzio giudiziale -> 98,00
        pytest.param("Procedimenti di cui all'art. 4 della L. 898/1970",
                     dict(valore_causa=0, tipo_procedimento="divorzio_giudiziale"),
                     id="divorzio-giudiziale"),
        # added: separazione consensuale and divorzio congiunto -> 43,00 (co. 1 lett. a)
        pytest.param("Procedimenti di cui all'art. 711 c.p.c. e art. 4 comma 16 L. 898/1970",
                     dict(valore_causa=0, tipo_procedimento="separazione_consensuale"),
                     id="separazione-consensuale"),
        pytest.param("Procedimenti di cui all'art. 711 c.p.c. e art. 4 comma 16 L. 898/1970",
                     dict(valore_causa=0, tipo_procedimento="divorzio_congiunto"),
                     id="divorzio-congiunto"),
        # plan (variant): lavoro with reddito_oltre_soglia_lavoro false -> 0,00 (esente, art. 9 co. 1-bis)
        pytest.param("Procedimenti in materia di lavoro, rapporti di pubblico impiego nonché "
                     "previdenza e assistenza obbligatorie quando il reddito della parte e' "
                     "inferiore o uguale",
                     dict(valore_causa=30000, tipo_procedimento="lavoro",
                          reddito_oltre_soglia_lavoro=False),
                     id="lavoro-sotto-soglia-esente"),
        # added: previdenza sotto soglia -> esente
        pytest.param("Procedimenti in materia di lavoro, rapporti di pubblico impiego nonché "
                     "previdenza e assistenza obbligatorie quando il reddito della parte e' "
                     "inferiore o uguale",
                     dict(valore_causa=30000, tipo_procedimento="previdenza",
                          reddito_oltre_soglia_lavoro=False),
                     id="previdenza-sotto-soglia-esente"),
        # added: previdenza oltre soglia -> 43,00 (art. 9 co. 1-bis: art. 13 co. 1 lett. a)
        pytest.param("Procedimenti in materia di previdenza e assistenza obbligatorie quando il "
                     "reddito della parte supera",
                     dict(valore_causa=30000, tipo_procedimento="previdenza",
                          reddito_oltre_soglia_lavoro=True),
                     id="previdenza-oltre-soglia"),
        # added: ricorsi avanti ai TAR -> 650,00 (co. 6-bis lett. e)
        pytest.param("Ricorsi avanti ai Tribunali amministrativi regionali",
                     dict(valore_causa=0, tipo_procedimento="tar"),
                     id="tar-fisso"),
    ],
)
def test_contributo_fisso(site_fissi, prefix, kwargs):
    site = _lookup(site_fissi, prefix)
    assert isinstance(site, float), f"site row {prefix!r} is not an amount: {site!r}"
    ours = _tool(grado="primo", **kwargs)
    assert_close(ours, site, TOL, prefix)


# --- 8. Whole published scales (secondary page), both sides of every bound -------

@pytest.mark.parametrize(
    "heading, tipo, grado, n_righe",
    [
        pytest.param("Processo Civile - 1° Grado", "cognizione", "primo", 7, id="civile-primo"),
        pytest.param("Processo Civile - Impugnazione", "cognizione", "appello", 7, id="civile-appello"),
        pytest.param("Processo Civile - Cassazione", "cognizione", "cassazione", 7, id="civile-cassazione"),
        pytest.param("Processo Tributario - Commissione tributaria provinciale e regionale",
                     "tributario", "primo", 6, id="tributario-primo"),
        pytest.param("Processo Tributario - Commissione tributaria provinciale e regionale",
                     "tributario", "appello", 6, id="tributario-appello"),
    ],
)
def test_tabella_pubblicata_scaglioni(site_tabella, heading, tipo, grado, n_righe):
    # Every row of the published table checked at its upper bound ("fino a", inclusive)
    # and one cent above its lower bound ("superiore a").
    rows = _scaglioni(site_tabella, heading)
    assert len(rows) == n_righe, f"{heading}: parsed {len(rows)} rows, expected {n_righe}"
    diffs = []
    for low, up, imp in rows:
        for v in [x for x in (up, (low + 0.01) if low is not None else None) if x is not None]:
            ours = _tool(valore_causa=round(v, 2), tipo_procedimento=tipo, grado=grado)
            if abs(ours - imp) > TOL:
                diffs.append(f"{v:.2f}: nostro={ours:.2f} sito={imp:.2f}")
    assert not diffs, f"{heading} ({tipo}/{grado}): " + "; ".join(diffs)


# --- 9. Options the site offers but the tool does not (not comparable) ----------

def test_valore_non_indicato_non_confrontabile():
    # Art. 13 co. 6: when the value is not declared the highest bracket is presumed
    # (site: "Valore non indicato" -> civile 1.686,00, tributario 1.500,00, amministrativo
    # 6.000,00). The tool has no such option: valore_causa is required.
    pytest.skip("non confrontabile: il tool non gestisce il valore non dichiarato (art. 13 co. 6)")


def test_tar_appalti_per_scaglioni_non_confrontabile():
    # Art. 13 co. 6-bis lett. d: public-procurement cases by value (2.000 / 4.000 / 6.000).
    # The site computes them with Processo = Amministrativo and a determined value; the tool's
    # 'tar' type is always the flat 650 (the table carries tar_appalti_scaglioni, unused).
    pytest.skip("non confrontabile: il tool non espone il rito appalti per scaglioni (co. 6-bis lett. d)")


def test_tributario_valore_indeterminabile_non_confrontabile():
    # Art. 13 co. 6-quater: indeterminable tax cases 120,00 (site: 120 / 120 / 1.036 in Cassazione).
    # The tool has no indeterminable-value option for the tax process.
    pytest.skip("non confrontabile: il tool non ha il tributario di valore indeterminabile")


def test_opposizione_atti_esecutivi_appello_non_confrontabile():
    # The tool returns 252,00 (168 x 1,5) for an appeal against an art. 617 c.p.c. decision,
    # although that decision is not appealable (art. 618 c.p.c.); the site has no such option.
    pytest.skip("non confrontabile: il sito non offre l'opposizione agli atti esecutivi in appello")
