"""Comparison: spese_condominiali vs avvocatoandreani.it.

Main page: calcolo-ripartizione-spese-utenze.php, a generic splitter of an
amount over a ripartition scheme (Millesimi, Parti, Mq, ...). It covers the
art. 1123 c.c. share by millesimi and, fed with a declared height scheme, the
art. 1124 c.c. half of a lift expense ripartita "per altezza". The site does
not split landlord/tenant: that is checked on the secondary page (tabella
Confedilizia Sunia-Sicet-Uniat 2014 degli oneri accessori, art. 9 L. 392/1978).

Site conventions observed (Phase 1, 2026-09-28):
- each share is rounded half-up to the cent (10,01 x 500/1000 = 5,005 -> 5,01)
  and the TOTALE row is the sum of the rounded shares;
- the sum of millesimi is validated: above 1000 the site refuses to compute;
- the form keeps state across submissions in the same browser context, so
  every submission uses a fresh page (the `page` fixture gives one per test).
"""

import re
import sys

import pytest

sys.path.insert(0, "/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it")

import src.server  # noqa: E402,F401  (registers all tool modules)
from src.tools.proprieta_successioni import spese_condominiali as _tool  # noqa: E402

from .conftest import accept_cookies, assert_close, parse_euro  # noqa: E402

TOOL = getattr(_tool, "fn", _tool)
URL = "https://www.avvocatoandreani.it/servizi/calcolo-ripartizione-spese-utenze.php"
URL_PI = "https://www.avvocatoandreani.it/servizi/ripartizione_spese_proprietario_inquilino.php"

UNIT_MILLESIMI = "5"
UNIT_PARTI = "10"


def _it(x: float) -> str:
    """Format a number with the Italian decimal comma (no thousands sep)."""
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _site_split(page, importo: float, unit: str, rows: list[tuple[str, str]]) -> dict:
    """Submit one ripartition on the site; return {nominativo: quota} + errors."""
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1200)
    page.fill("input[name='DesImp(0)']", "Spesa")
    page.fill("input[name='ValImp(0)']", _it(importo))
    page.select_option("select[name='CodUnitaMisura']", unit)
    extra = len(rows) - 6
    if extra > 0:
        page.evaluate(f"() => {{ for (let i = 0; i < {extra}; i++) AddNewRow('Criteri'); }}")
    for i, (name, value) in enumerate(rows):
        page.fill(f"input[name='DesRip({i})']", name)
        page.fill(f"input[name='ValRip({i})']", value)
    with page.expect_navigation(timeout=30000, wait_until="domcontentloaded"):
        page.evaluate(
            """() => { const f = document.forms['CalcoloRipartizione'];
            const b = [...f.querySelectorAll('input[type=submit]')]
                .find(e => e.value == 'Calcola Ripartizione');
            f.requestSubmit(b); }"""
        )
    page.wait_for_timeout(2000)
    out: dict = {}
    tables = [t.inner_text() for t in page.query_selector_all("table") if "Quota Parte" in t.inner_text()]
    if not tables:
        body = page.inner_text("body")
        m = re.search(r"Attenzione\s+(.*?)\n\s*VOCI di SPESA", body, re.S)
        out["_errore"] = " ".join(m.group(1).split()) if m else "nessun risultato"
        return out
    for line in tables[0].splitlines():
        cells = [c.strip() for c in line.split("\t")]
        if len(cells) == 3 and cells[2].startswith("€"):
            out[cells[0]] = parse_euro(cells[2])
    return out


# ---------------------------------------------------------------------------
# Art. 1123 c.c. - ripartizione per millesimi
# ---------------------------------------------------------------------------

def test_ordinaria_millesimi(page):
    """Plan case 1. Atteso: 855,00 (art. 1123 co. 1 c.c.)."""
    tool = TOOL(importo_totale=10000, millesimi_proprietario=85.5, tipo_spesa="ordinaria")
    site = _site_split(page, 10000, UNIT_MILLESIMI, [("Unita", "85,5"), ("Altri", "914,5")])
    assert_close(site["TOTALE"], 10000, 0.01, "controllo importo acquisito dal sito")
    assert_close(tool["quota_unita"], site["Unita"], 0.01, "quota ordinaria per millesimi")


def test_straordinaria_millesimi_decimali(page):
    """Extra case, enum option 'straordinaria' with fractional millesimi.

    Atteso: 1.234,57 x 333,33/1000 = 411,5172 -> 411,52 (art. 1123 co. 1 c.c.).
    """
    tool = TOOL(importo_totale=1234.57, millesimi_proprietario=333.33, tipo_spesa="straordinaria")
    site = _site_split(page, 1234.57, UNIT_MILLESIMI, [("Unita", "333,33"), ("Altri", "666,67")])
    assert_close(site["TOTALE"], 1234.57, 0.01, "controllo importo acquisito dal sito")
    assert_close(tool["quota_unita"], site["Unita"], 0.01, "quota straordinaria per millesimi")


def test_riscaldamento_mille_millesimi(page):
    """Limit case: millesimi = 1000 (upper bound), enum option 'riscaldamento'.

    Atteso: l'intera spesa, 5.000,00 (art. 1123 c.c.).
    """
    tool = TOOL(importo_totale=5000, millesimi_proprietario=1000, tipo_spesa="riscaldamento")
    site = _site_split(page, 5000, UNIT_MILLESIMI, [("Unita", "1000")])
    assert_close(tool["quota_unita"], site["Unita"], 0.01, "quota con 1000 millesimi")


def test_arrotondamento_mezzo_centesimo(page):
    """Limit case: the share falls exactly on half a cent (10,01 x 500/1000 = 5,005).

    The site rounds half-up (5,01); the tool uses Python round() on a binary
    float (5.00499... -> 5,00). The 1-cent gap is within the brief's 0,01
    tolerance; the convention difference is reported in the phase-1 notes.
    Norm: art. 1123 c.c. (no rounding rule in the norm).
    """
    tool = TOOL(importo_totale=10.01, millesimi_proprietario=500, tipo_spesa="ordinaria")
    site = _site_split(page, 10.01, UNIT_MILLESIMI, [("A", "500"), ("B", "500")])
    assert_close(tool["quota_unita"], site["A"], 0.01, "quota su mezzo centesimo")


def test_millesimi_oltre_mille(page):
    """Plan case 4. Atteso: errore di validazione; il tool restituisce 12.000,00.

    The site refuses: "La somma dei millesimi e' superiore a 1000". The tool
    should refuse too (a share above the whole expense is impossible under
    art. 1123 c.c.).
    """
    tool = TOOL(importo_totale=10000, millesimi_proprietario=1200)
    site = _site_split(page, 10000, UNIT_MILLESIMI, [("Unita", "1200")])
    assert "_errore" in site and "1000" in site["_errore"], f"il sito ha calcolato: {site}"
    assert "errore" in tool, (
        f"il sito rifiuta ({site['_errore']}), il tool restituisce quota_unita={tool.get('quota_unita')}"
    )


# ---------------------------------------------------------------------------
# Art. 1124 c.c. - ascensore: meta' per millesimi, meta' per altezza
# ---------------------------------------------------------------------------

def _tool_lift_parts(tool: dict) -> tuple[float, float]:
    m = re.search(r"millesimi \(([\d.]+)€\) \+ 50% piano \d+ \(([\d.]+)€\)", tool["metodo_ripartizione"])
    assert m, tool["metodo_ripartizione"]
    return float(m.group(1)), float(m.group(2))


def test_ascensore_meta_millesimi(page):
    """Plan case 2, first half. Atteso: meta' per millesimi = 300,00 (art. 1124 c.c.)."""
    tool = TOOL(importo_totale=6000, millesimi_proprietario=100, tipo_spesa="ascensore", piano=3)
    q_mill, _ = _tool_lift_parts(tool)
    site = _site_split(page, 3000, UNIT_MILLESIMI, [("Unita", "100"), ("Altri", "900")])
    assert_close(q_mill, site["Unita"], 0.01, "meta' ascensore per millesimi")


def _heights(top_floor: int) -> list[tuple[str, str]]:
    # One unit per floor, from the ground floor (coefficient 0,5 - the tool's own
    # convention) to `top_floor`: an ASSUMED building, since art. 1124 c.c.
    # needs the heights of all units and the tool asks only for one floor.
    return [(f"P{k}", "0,5" if k == 0 else str(k)) for k in range(top_floor + 1)]


def test_ascensore_meta_altezza_terzo_piano(page):
    """Plan case 2, second half. Atteso: quota per altezza non determinabile
    senza le altezze di tutte le unita'; il tool restituisce 900 (totale 1.200).

    Benchmark on an assumed 10-floor building, one unit per floor (0..10):
    the site splits the 3.000 height half in proportion to the floors
    (3/55,5 -> 162,16). The tool normalises on a fixed 10 (3/10 -> 900).
    """
    tool = TOOL(importo_totale=6000, millesimi_proprietario=100, tipo_spesa="ascensore", piano=3)
    _, q_alt = _tool_lift_parts(tool)
    site = _site_split(page, 3000, UNIT_PARTI, _heights(10))
    assert_close(q_alt, site["P3"], 0.01, "meta' ascensore per altezza, piano 3 (edificio 0-10)")


def test_ascensore_dodicesimo_piano(page):
    """Plan case 3 (limit: above the 10-floor normalisation).

    Atteso: la quota per altezza non puo' superare 3.000,00 (meta' della
    spesa); il tool attribuisce 3.600,00 per l'altezza e 3.900,00 in totale.
    Benchmark on an assumed building 0..12, one unit per floor: the site
    gives 12/78,5 x 3.000 = 458,60 (art. 1124 c.c.).
    """
    tool = TOOL(importo_totale=6000, millesimi_proprietario=100, tipo_spesa="ascensore", piano=12)
    _, q_alt = _tool_lift_parts(tool)
    site = _site_split(page, 3000, UNIT_PARTI, _heights(12))
    assert sum(v for k, v in site.items() if k.startswith("P")) == pytest.approx(3000, abs=0.05)
    assert q_alt <= 3000, f"quota per altezza {q_alt} oltre la meta' della spesa (3.000)"
    assert_close(q_alt, site["P12"], 0.01, "meta' ascensore per altezza, piano 12 (edificio 0-12)")


# ---------------------------------------------------------------------------
# Art. 9 L. 392/1978 - ripartizione locatore / conduttore
# ---------------------------------------------------------------------------

def test_locato_ordinaria_portierato(page):
    """Plan case 5. Atteso: non tutte le voci ordinarie sono a carico del
    conduttore (art. 9 L. 392/1978; tabella oneri accessori); il tool
    attribuisce 855,00 al conduttore.

    The splitter page has no landlord/tenant option; the secondary page (tabella
    Confedilizia Sunia-Sicet-Uniat 2014, voce Portierato) puts "Manutenzione
    ordinaria della guardiola" at P 10% / I 90%. For an ordinary expense of
    that kind the tenant share is 855,00 x 90% = 769,50.
    """
    # Phase 3: the portineria is now its own expense type (art. 9 co. 2 L. 392/1978, 90% tenant);
    # the generic 'ordinaria' type stays 100% tenant, so this case uses 'portineria'.
    tool = TOOL(importo_totale=10000, millesimi_proprietario=85.5, tipo_spesa="portineria", immobile_locato=True)
    page.goto(f"{URL_PI}?tabella=2&menu=210", timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    m = re.search(r"Manutenzione ordinaria della guardiola\s+P\s*(\d+)%\s+I\s*(\d+)%", body)
    assert m, "riga 'Manutenzione ordinaria della guardiola' non trovata"
    perc_i = int(m.group(2)) / 100
    site_inquilino = round(tool["quota_unita"] * perc_i, 2)
    assert_close(
        tool["ripartizione_locazione"]["quota_inquilino"], site_inquilino, 0.01,
        "quota conduttore, spesa ordinaria di portierato",
    )
