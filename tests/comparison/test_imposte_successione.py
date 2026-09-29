"""Comparison tests: imposte_successione vs avvocatoandreani.it.

Page: /servizi/calcolo-imposte-di-successione.php (one heir; fields Grado,
Handicap, ImpImmobiliPc, ImpImmobiliAltri, ImpLiquidita; button #btn-calc).

Norms: D.Lgs. 346/1990 (TUS) art. 7 as amended by art. 2, co. 48-49 D.L.
262/2006 (aliquote 4/6/6/8 %, franchigie 1.000.000 / 100.000 / 1.500.000 for
L. 104/1992 heirs); D.Lgs. 347/1990 artt. 10 and 13 + tariffa (ipotecaria 2 %,
catastale 1 %, minimum 200 euro each; prima casa 200 + 200 fixed).

The tool applies the franchigia to `valore_beni` (the single heir's share) and
computes ipotecaria/catastale on the whole `valore_beni` when immobili=True, so
the site is always fed a single heir and either all-movable (immobili=False)
or all-real-estate (immobili=True) values.

Tolerance: 0,01 euro on amounts (brief default).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

PAGE = "calcolo-imposte-di-successione.php"
URL = f"https://www.avvocatoandreani.it/servizi/{PAGE}"

# Site "Grado" option values
CONIUGE, DISCENDENTE, ASCENDENTE, FRATELLO, PARENTE_4, AFFINE_3, ALTRO = "1234567"


def _call(**kwargs):
    import src.server  # noqa: F401  (registers modules)
    from src.tools.proprieta_successioni import imposte_successione

    fn = getattr(imposte_successione, "fn", imposte_successione)
    return fn(**kwargs)


def _fmt(v: float) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _site(page, grado, *, liquidita=0.0, immobili_altri=0.0, immobili_pc=0.0, handicap=False):
    """Fill the form, submit, return {label: amount} from the result tables."""
    goto(page, PAGE, wait_ms=1500)
    accept_cookies(page)
    if handicap:
        # In headless Chromium, ticking the "Si" radio of Handicap leaves the
        # #btn-calc click without a submission (no POST reaches the site). The
        # server itself handles Handicap=1 correctly, so the same form fields
        # (FormData captured from the page, incl. hidden Anno/PrimaChiamata) are
        # posted directly and the returned page is rendered for parsing.
        form = {
            "Grado": grado,
            "Handicap": "1",
            "ImpImmobiliPc": _fmt(immobili_pc),
            "ImpImmobiliAltri": _fmt(immobili_altri),
            "ImpLiquidita": _fmt(liquidita),
            "Anno": "2006",
            "PrimaChiamata": "N",
            "Op": "Calcola Imposte",
        }
        resp = page.context.request.post(URL, form=form)
        assert resp.status == 200, f"site POST failed: {resp.status}"
        page.set_content(resp.text(), wait_until="domcontentloaded")
    else:
        page.select_option("#Grado", grado)
        page.fill("#ImpImmobiliPc", _fmt(immobili_pc))
        page.fill("#ImpImmobiliAltri", _fmt(immobili_altri))
        page.fill("#ImpLiquidita", _fmt(liquidita))
        page.click("#btn-calc", force=True)
        page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    start = text.find("IMPOSTA di SUCCESSIONE\n")
    assert start >= 0, "result block not found on site"
    block = text[start:text.find("IMPOSTE TOTALI DOVUTE", start) + 60]
    out = {}
    # A label may wrap onto a second line, e.g.
    # "Imposta catastale ... (1%):\n(applicato il minimo di € 200,00)\t€ 200,00".
    for label, amount in re.findall(r"([^\n\t:]+):[^\t]*?\t€\s*([\d.,]+)", block):
        out[label.strip()] = parse_euro(amount)
    return out


def _pick(values: dict, prefix: str, default: float | None = None) -> float:
    """Sum every site line whose label starts with prefix (e.g. 'Imposta ipotecaria')."""
    hits = [v for k, v in values.items() if k.lower().startswith(prefix.lower())]
    if not hits and default is not None:
        return default
    assert hits, f"label '{prefix}' not in site result: {values}"
    return round(sum(hits), 2)


def _compare(tool, site, *, immobili):
    # The site omits the "Imposta di successione" line when the franchigia covers the
    # whole estate (no "Patrimonio Imponibile" line either): that is an imposta of 0.
    no_taxable = "Patrimonio Imponibile" not in site
    site_imposta = _pick(site, "Imposta di successione", default=0.0 if no_taxable else None)
    assert_close(tool["imposta_successione"], site_imposta, 0.01, "imposta")
    if immobili:
        assert_close(tool["imposta_ipotecaria"], _pick(site, "Imposta ipotecaria"), 0.01, "ipotecaria")
        assert_close(tool["imposta_catastale"], _pick(site, "Imposta catastale"), 0.01, "catastale")
    assert_close(tool["totale_imposte"], _pick(site, "IMPOSTE TOTALI DOVUTE"), 0.01, "totale")


# ---- Plan cases ---------------------------------------------------------------


def test_coniuge_oltre_franchigia(page):
    # Plan: (1.500.000 - 1.000.000) x 4% = 20.000,00 (art. 7 co. 1 lett. a TUS).
    tool = _call(valore_beni=1_500_000, parentela="coniuge_linea_retta")
    site = _site(page, CONIUGE, liquidita=1_500_000)
    _compare(tool, site, immobili=False)


def test_fratello_con_immobili(page):
    # Plan: (250.000 - 100.000) x 6% = 9.000; ipotecaria 2% = 5.000; catastale 1% =
    # 2.500; totale 16.500,00 (art. 7 co. 1 lett. b TUS; D.Lgs. 347/1990 artt. 10, 13).
    tool = _call(valore_beni=250_000, parentela="fratelli_sorelle", immobili=True)
    site = _site(page, FRATELLO, immobili_altri=250_000)
    _compare(tool, site, immobili=True)


def test_parente_quarto_grado_minimi(page):
    # Plan: imposta 300 (6%, no franchigia); ipotecaria e catastale al minimo di 200;
    # totale 700,00 (art. 7 co. 1 lett. c TUS; minimi D.Lgs. 347/1990).
    tool = _call(valore_beni=5_000, parentela="parenti_fino_4_grado_affini_fino_3", immobili=True)
    site = _site(page, PARENTE_4, immobili_altri=5_000)
    _compare(tool, site, immobili=True)


def test_estraneo_prima_casa(page):
    # Plan: 8% = 8.000; ipotecaria e catastale fisse 200 + 200; totale 8.400,00
    # (art. 7 co. 1 lett. d TUS; art. 69 co. 3 L. 342/2000).
    tool = _call(valore_beni=100_000, parentela="altri", immobili=True, prima_casa=True)
    site = _site(page, ALTRO, immobili_pc=100_000)
    _compare(tool, site, immobili=True)


def test_handicap_grave_override(page):
    # Plan: (2.000.000 - 1.500.000) x 4% = 20.000,00 (art. 7 co. 2-bis TUS,
    # L. 104/1992). Tool reaches 1,5M only through aliquote_franchigie.
    tool = _call(
        valore_beni=2_000_000,
        parentela="coniuge_linea_retta",
        aliquote_franchigie=[{"parentela": "coniuge_linea_retta", "aliquota": 4, "franchigia": 1_500_000}],
    )
    site = _site(page, CONIUGE, liquidita=2_000_000, handicap=True)
    _compare(tool, site, immobili=False)


# ---- Edge cases -----------------------------------------------------------------


def test_limite_franchigia_coniuge_esatta(page):
    # Edge: value equal to the 1.000.000 franchigia -> imposta 0 (art. 7 co. 1 lett. a TUS).
    tool = _call(valore_beni=1_000_000, parentela="coniuge_linea_retta")
    site = _site(page, DISCENDENTE, liquidita=1_000_000)
    _compare(tool, site, immobili=False)


def test_limite_fratello_un_euro_oltre_franchigia(page):
    # Edge: 100.001 -> (1) x 6% = 0,06 (art. 7 co. 1 lett. b TUS).
    tool = _call(valore_beni=100_001, parentela="fratelli_sorelle")
    site = _site(page, FRATELLO, liquidita=100_001)
    _compare(tool, site, immobili=False)


def test_limite_minimo_ipotecaria_esatto(page):
    # Edge: immobili 10.000 -> ipotecaria 2% = 200 (= minimum), catastale 1% = 100
    # raised to 200; imposta 8% = 800; totale 1.200 (D.Lgs. 347/1990).
    tool = _call(valore_beni=10_000, parentela="altri", immobili=True)
    site = _site(page, ALTRO, immobili_altri=10_000)
    _compare(tool, site, immobili=True)


def test_enum_affine_terzo_grado(page):
    # Enum: the tool merges 'parente fino al 4 grado' and 'affine fino al 3 grado'
    # in one key; site option 6 (affine). 50.000 x 6% = 3.000 (art. 7 co. 1 lett. c TUS).
    tool = _call(valore_beni=50_000, parentela="parenti_fino_4_grado_affini_fino_3")
    site = _site(page, AFFINE_3, liquidita=50_000)
    _compare(tool, site, immobili=False)


def test_enum_ascendente_linea_retta_con_immobili(page):
    # Enum: ascendente -> coniuge_linea_retta. 1.200.000 immobili:
    # (200.000) x 4% = 8.000; ipotecaria 24.000; catastale 12.000; totale 44.000.
    tool = _call(valore_beni=1_200_000, parentela="coniuge_linea_retta", immobili=True)
    site = _site(page, ASCENDENTE, immobili_altri=1_200_000)
    _compare(tool, site, immobili=True)


def test_immobili_misti_non_confrontabile(page):
    # The tool cannot model an estate that is partly real estate: ipotecaria and
    # catastale go on the whole valore_beni. Not comparable with the site.
    pytest.skip("tool computes ipocatastali on the whole valore_beni; mixed estates not modelled")
