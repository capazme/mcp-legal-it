"""Benchmark pensione_reversibilita vs avvocatoandreani.it (Fase 1).

Page: https://www.avvocatoandreani.it/servizi/calcolo-pensione-reversibilita-inps.php
Norm: L. 335/1995, art. 1 co. 41 and Tabella F (cumulo with the beneficiary's
income, thresholds at 3x/4x/5x the INPS minimum, salvaguardia clause).

The tool hardcodes the 2024 INPS minimum (7,781.93 per year), so the site is
driven with Anno=2024 unless the case is explicitly about a different year.
The site computes the reduction only on the spouse's share and prints one
sentence per beneficiary class; the total compared here is the sum of the
shares, with the spouse's share replaced by the net amount after cumulo.
Tolerance: 0.01 euro (brief).
"""

import re

import pytest

from tests.comparison.conftest import assert_close, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo-pensione-reversibilita-inps.php"

_SET_JS = """([c, r]) => {
  const q = n => document.querySelector(n);
  q("input[name='TipoImportoPensione'][value='a']").checked = true;
  q("input[name='TipoImportoPensione'][value='m']").checked = false;
  q("input[name='Coniuge']").checked = c; ChkConiuge();
  q("input[name='ConiugePercepisceReddito']").checked = r;
  ChkConiugePercepisceReddito(true); ChkConiuge();
}"""

_AMOUNT = r"€\s*([\d.]+,\d{2})"


def _call(**kwargs):
    import src.server  # noqa: F401  registers every tool module
    from src.tools.proprieta_successioni import pensione_reversibilita

    fn = getattr(pensione_reversibilita, "fn", pensione_reversibilita)
    return fn(**kwargs)


def _site(page, anno, pensione_annua, coniuge=False, reddito=None, figli=0, genitori=0):
    """Drive the form (annual amount, 13 months) and return (total, text)."""
    page.goto(URL, timeout=60000, wait_until="load")
    page.wait_for_timeout(1500)
    page.evaluate('document.querySelectorAll("#qc-cmp2-container").forEach(e => e.remove())')
    page.select_option("select[name='Anno']", str(anno))
    page.fill("input[name='Pensione']", f"{pensione_annua}".replace(".", ","))
    # The checkboxes are toggled through the page's own handlers: real clicks
    # are intercepted by an overlay and do not change their state.
    page.evaluate(_SET_JS, [coniuge, reddito is not None])
    if reddito is not None:
        page.fill("input[name='RedditoConiuge']", f"{reddito}".replace(".", ","))
    if figli:
        page.select_option("select[name='NumeroFigli']", str(figli))
    if genitori:
        page.select_option("select[name='NumeroGenitori']", str(genitori))
    with page.expect_navigation(wait_until="load"):
        page.evaluate(
            "document.PensioneReversibilita.requestSubmit("
            "document.querySelector('form#PensioneReversibilita input[type=submit]'))"
        )
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    start = body.find("(senza coniuge, figli e genitori)")
    end = body.find("Avvertenza")
    text = body[start:end]

    total = 0.0
    m = re.search(r"Al coniuge spetta .*?" + _AMOUNT, text)
    if m:
        coniuge_amt = parse_euro(m.group(1))
        net = re.search(r"ammonta a " + _AMOUNT, text)
        total += parse_euro(net.group(1)) if net else coniuge_amt
    for pat in (r"Al figlio spetta .*?" + _AMOUNT,
                r"Ai \d+ figli va .*?" + _AMOUNT,
                r"Ai \d+ genitori spetta .*?" + _AMOUNT):
        m = re.search(pat, text)
        if m:
            total += parse_euro(m.group(1))
    assert total > 0, f"site result not parsed: {text!r}"
    return round(total, 2), text


def _compare(page, anno, tool_kwargs, site_kwargs, label):
    # The tool takes the reference year explicitly (trattamento minimo of Tabella F): pass the same
    # year selected on the site, otherwise the tool would use the current one.
    r = _call(anno=anno, **tool_kwargs)
    assert "errore" not in r, r
    site_total, text = _site(page, anno, **site_kwargs)
    print(f"{label}: tool={r['pensione_netta_annua']} site={site_total} | {text.strip()}")
    assert_close(r["pensione_netta_annua"], site_total, tolerance=0.01, label=label)


def test_coniuge_solo_senza_redditi(page):
    # Plan: 60% = 12,000.00 per year, 923.08 per month (13). Art. 1 co. 41 L. 335/1995 (Tabella F).
    _compare(page, 2024,
             dict(pensione_de_cuius=20000, beneficiari={"coniuge": True, "figli": 0, "genitori": 0},
                  reddito_beneficiario=0),
             dict(pensione_annua=20000, coniuge=True), "coniuge_solo")


def test_coniuge_reddito_oltre_5x(page):
    # Plan: Tabella F, reduction 50% -> 6,000.00 (income 50,000 > 5x minimum;
    # salvaguardia not binding because 7,200 + 5x minimum < 50,000).
    _compare(page, 2024,
             dict(pensione_de_cuius=20000, beneficiari={"coniuge": True, "figli": 0},
                  reddito_beneficiario=50000),
             dict(pensione_annua=20000, coniuge=True, reddito=50000), "coniuge_5x")


def test_coniuge_figlio_minore_reddito_alto(page):
    # Plan: no reduction when the household includes a minor child (art. 1 co. 41
    # L. 335/1995): 80% = 16,000.00; the tool halves the whole 80% (8,000.00).
    # The site reduces only the spouse's 60% share (6,000) and leaves the child's
    # 20% (4,000) untouched: 10,000.00. Phase 3 verdict: the tool is now right (16,000.00,
    # art. 1 co. 41 L. 335/1995: limits do not apply with minor children in the household);
    # the site is wrong, so this case stays failing by design.
    _compare(page, 2024,
             dict(pensione_de_cuius=20000, beneficiari={"coniuge": True, "figli": 1, "figli_minori": 1},
                  reddito_beneficiario=50000),
             dict(pensione_annua=20000, coniuge=True, reddito=50000, figli=1), "coniuge_figlio_minore")


def test_reddito_appena_oltre_3x_minimo_2024(page):
    # Plan (limit): 2024 threshold 23,345.79; reduction 25% capped by the
    # Tabella F salvaguardia at 11,845.79; the tool returns 9,000.00.
    _compare(page, 2024,
             dict(pensione_de_cuius=20000, beneficiari={"coniuge": True}, reddito_beneficiario=23500),
             dict(pensione_annua=20000, coniuge=True, reddito=23500), "3x_2024_salvaguardia")


def test_reddito_23500_anno_2026(page):
    # Plan (limit, different table year): with the 2026 minimum (7,954.05 on the
    # site) 23,500 is below 3x -> no reduction, 12,000.00. The tool is pinned to
    # the 2024 minimum and returns 9,000.00.
    _compare(page, 2026,
             dict(pensione_de_cuius=20000, beneficiari={"coniuge": True}, reddito_beneficiario=23500),
             dict(pensione_annua=20000, coniuge=True, reddito=23500), "3x_2026")


def test_reddito_esattamente_3x_minimo_2024(page):
    # Limit: income equal to 3x the 2024 minimum (23,345.79): no reduction
    # ("superiore a 3 volte" in Tabella F) -> 12,000.00.
    _compare(page, 2024,
             dict(pensione_de_cuius=20000, beneficiari={"coniuge": True}, reddito_beneficiario=23345.79),
             dict(pensione_annua=20000, coniuge=True, reddito=23345.79), "3x_esatto_2024")


def test_reddito_appena_oltre_5x_minimo_2024(page):
    # Limit: 40,000 > 5x 2024 minimum (38,909.65): theoretical 50% reduction
    # (6,000), salvaguardia raises it to 7,200 + 38,909.65 - 40,000 = 6,109.65.
    _compare(page, 2024,
             dict(pensione_de_cuius=20000, beneficiari={"coniuge": True}, reddito_beneficiario=40000),
             dict(pensione_annua=20000, coniuge=True, reddito=40000), "5x_2024_salvaguardia")


def test_tre_figli_soli(page):
    # Plan: 100% = 24,000.00 (Tabella F quote).
    _compare(page, 2024,
             dict(pensione_de_cuius=24000, beneficiari={"figli": 3}),
             dict(pensione_annua=24000, figli=3), "tre_figli")


def test_due_genitori(page):
    # Plan: 15% each = 9,000.00 in total.
    _compare(page, 2024,
             dict(pensione_de_cuius=30000, beneficiari={"genitori": 2}),
             dict(pensione_annua=30000, genitori=2), "due_genitori")


@pytest.mark.parametrize(
    "beneficiari,site_kwargs,label",
    [
        ({"figli": 1}, dict(figli=1), "un_figlio_70"),
        ({"figli": 2}, dict(figli=2), "due_figli_80"),
        ({"coniuge": True, "figli": 2}, dict(coniuge=True, figli=2), "coniuge_due_figli_100"),
    ],
)
def test_quote_enumerate(page, beneficiari, site_kwargs, label):
    # Enumerated options of Tabella F: 1 child 70%, 2 children 80%, spouse + 2 children 100%.
    _compare(page, 2024,
             dict(pensione_de_cuius=20000, beneficiari=beneficiari),
             dict(pensione_annua=20000, **site_kwargs), label)
