"""Comparison tests: calcolo_usufrutto vs avvocatoandreani.it.

Main page:  /servizi/calcolo_usufrutto_nuda_proprieta.php (usufrutto vitalizio,
            tasso di riferimento 2,50%, coefficienti 2026 - D.M. 22 dicembre 2025).
Secondary:  /servizi/tab_coefficienti_usufrutto.php (published table, year 2026).

Norm: DPR 131/1986 (TUR), art. 46 and prospetto dei coefficienti allegato;
coefficients confirmed yearly by MEF decree (2026: tasso legale 1,6%, but the
computation uses the 2,5% floor, so the per-band percentages are unchanged).
Tolerance: 0,01 euro on amounts (brief default).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

PAGE = "calcolo_usufrutto_nuda_proprieta.php"
TABLE_URL = "https://www.avvocatoandreani.it/servizi/tab_coefficienti_usufrutto.php"


def _tool(valore, eta):
    import src.server  # noqa: F401  (registers modules, avoids circular imports)
    from src.tools.proprieta_successioni import calcolo_usufrutto

    fn = getattr(calcolo_usufrutto, "fn", calcolo_usufrutto)
    return fn(valore_piena_proprieta=valore, eta_usufruttuario=eta)


def _site(page, valore, eta) -> dict:
    """Drive the vitalizio form.

    The Valore field has a JS input mask that mangles decimals typed with
    fill() (e.g. "123456,78" -> "123456,7") and the Calcola click does not
    submit non-integer values; so both fields are set via the DOM and the form
    is submitted natively. The server parses the Italian format "123.456,78".
    """
    goto(page, PAGE)
    euro = f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    page.evaluate(f'document.querySelector("input[name=Valore]").value="{euro}"')
    page.check("input[name='TipoCalcolo'][value='1']", force=True)  # vitalizio
    page.evaluate(f'document.querySelector("input[name=Eta]").value="{eta}"')
    with page.expect_navigation():
        page.evaluate('HTMLFormElement.prototype.submit.call(document.forms["CalcoloUsufrutto"])')
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    out = {}
    m = re.search(r"Età dell'usufruttuario\s+(\d+)\s+anni", body)
    out["eta"] = int(m.group(1)) if m else None
    m = re.search(r"Coefficiente moltiplicatore\s+([\d.,]+)", body)
    out["coefficiente"] = float(m.group(1).replace(".", "").replace(",", ".")) if m else None
    m = re.search(r"Valore dell'usufrutto\s+€\s*([\d.]+,\d{2})", body)
    out["usufrutto"] = parse_euro(m.group(1)) if m else None
    m = re.search(r"Valore della nuda proprietà\s+€\s*([\d.]+,\d{2})", body)
    out["nuda"] = parse_euro(m.group(1)) if m else None
    return out


def _compare(page, valore, eta):
    ours = _tool(valore, eta)
    site = _site(page, valore, eta)
    assert site["usufrutto"] is not None, "result not found on site"
    print(f"eta={eta} valore={valore} tool={ours['valore_usufrutto']}/{ours['valore_nuda_proprieta']}"
          f" coeff={ours['coefficiente']} | site={site}")
    assert site["eta"] == eta, f"site read age {site['eta']} instead of {eta}"
    assert_close(ours["coefficiente"], site["coefficiente"], 0.0001, f"coefficiente_{eta}")
    assert_close(ours["valore_usufrutto"], site["usufrutto"], 0.01, f"usufrutto_{eta}")
    assert_close(ours["valore_nuda_proprieta"], site["nuda"], 0.01, f"nuda_{eta}")


# Plan: upper bound of the first band (0-20, coeff. 38) -> usufrutto 95.000 (95%),
# nuda proprietà 5.000. DPR 131/1986, prospetto.
def test_eta_20_confine_prima_fascia(page):
    _compare(page, 100000, 20)


# Plan: first year of the second band (21-30, coeff. 36) -> usufrutto 90.000 (90%),
# nuda proprietà 10.000.
def test_eta_21_inizio_seconda_fascia(page):
    _compare(page, 100000, 21)


# Plan: band 70-72 (coeff. 16) on 150.000 -> usufrutto 60.000 (40%), nuda 90.000.
def test_eta_70_fascia_70_72(page):
    _compare(page, 150000, 70)


# Plan: last band of the prospetto (93-99, coeff. 4) -> usufrutto 10.000 (10%), nuda 90.000.
def test_eta_99_ultima_fascia(page):
    _compare(page, 100000, 99)


# Added boundary: 92 is the last year of band 87-92 (coeff. 6, 15%), 93 the first
# of band 93-99 (coeff. 4, 10%). Non-round value to exercise cent rounding.
def test_eta_92_confine_87_92(page):
    _compare(page, 123456.78, 92)


def test_eta_93_inizio_93_99(page):
    _compare(page, 123456.78, 93)


# Added boundary: 40/41 (band 31-40 coeff. 34 -> 85%; 41-45 coeff. 32 -> 80%).
def test_eta_41_inizio_41_45(page):
    _compare(page, 250000, 41)


# Plan: beyond the prospetto (age 100). The official prospetto stops at 93-99;
# the tool adds a 100-120 band (coeff. 2 -> 5%, 5.000). The site's age field has
# maxlength=2, so 100 cannot be typed in the UI; the value is posted via the DOM
# to see what the server does. If it refuses, the case is not comparable.
def test_eta_100_oltre_prospetto(page):
    ours = _tool(100000, 100)
    site = _site(page, 100000, 100)
    print(f"eta=100 tool={ours.get('valore_usufrutto')} coeff={ours.get('coefficiente')} | site={site}")
    if site["usufrutto"] is None or site["eta"] != 100:
        pytest.skip(
            "Site does not compute age 100 (UI maxlength=2). "
            f"Tool gives usufrutto {ours.get('valore_usufrutto')} (coeff. {ours.get('coefficiente')})."
        )
    assert_close(ours["coefficiente"], site["coefficiente"], 0.0001, "coefficiente_100")
    assert_close(ours["valore_usufrutto"], site["usufrutto"], 0.01, "usufrutto_100")
    assert_close(ours["valore_nuda_proprieta"], site["nuda"], 0.01, "nuda_100")


# Secondary page: the tool's coefficient table vs the published 2026 table
# (bands, coefficients, percentages). Band 100-120 of the tool has no counterpart.
def test_tabella_coefficienti_2026(page):
    import json
    from pathlib import Path

    page.goto(TABLE_URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    text = "\n".join(t.inner_text() for t in page.query_selector_all("table"))
    rows = re.findall(r"da (\d+) a (\d+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", text)
    assert rows, "published table not parsed"
    site = {(int(a), int(b)): float(c.replace(",", ".")) for a, b, c, _, _ in rows}
    data = json.loads(
        (Path(__file__).resolve().parents[2] / "src/data/usufrutto_coefficienti.json").read_text()
    )
    tool = {(f["eta_min"], f["eta_max"]): f["coefficiente"] for f in data["coefficienti"]}
    tool_in_prospetto = {k: v for k, v in tool.items() if k[1] <= 99}
    assert tool_in_prospetto == site
    for (a, b), c in site.items():
        pct = _tool(100000, a)["percentuale_usufrutto"]
        assert_close(pct, c * 2.5, 0.0001, f"pct_{a}_{b}")
