"""Benchmark rendimento_bot vs avvocatoandreani.it (calcolo-rendimento-bot.php).

Norma: D.Lgs. 239/1996 (imposta sostitutiva 12,5% sullo scarto di emissione,
trattenuta alla sottoscrizione - art. 3 co. 2 DL 66/2014); commissioni massime
DM 15/01/2015.

Site conventions (read from the page, 2026-09-28):
- price is entered per 100 of nominal, capital is the nominal subscribed;
- commission is a percentage of the nominal (same as the tool);
- the "annuale" yield uses the commercial year (360 days), while the tool
  annualises on 365 days. To compare like with like the test compares the
  PERIOD yield ("Rendimento % lordo/netto N giorni"), obtained from the tool
  as annual_pct * giorni / 365. The site prints yields with 3 decimals, so the
  percentage tolerance is 0.0005 (half a unit of the last displayed digit),
  not the 4-decimal default of the brief: a tighter tolerance cannot be met by
  a value the site never shows.
- the site's net yield divides by (price + withholding + commission), i.e. the
  cash actually paid at subscription; the tool divides by the price only.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, goto, parse_euro

EUR_TOL = 0.01
PCT_TOL = 0.0005  # site displays 3 decimals (see module docstring)


def _tool(**kw):
    import src.server  # noqa: F401  (registers modules)
    from src.tools.investimenti import rendimento_bot

    fn = getattr(rendimento_bot, "fn", rendimento_bot)
    return fn(**kw)


def _site(page, tipo, giorni, prezzo100, capitale, commissione):
    goto(page, "calcolo-rendimento-bot.php", wait_ms=1500)
    accept_cookies(page)
    page.select_option("select[name='TipoBot']", tipo)
    page.wait_for_timeout(500)
    if giorni is not None:
        page.fill("input[name='DurataGiorni']", str(giorni))
        page.dispatch_event("input[name='DurataGiorni']", "change")
    page.fill("input[name='PrezzoAcquisto']", f"{prezzo100:.3f}".replace(".", ","))
    page.fill("input[name='Capitale']", str(capitale))
    page.fill("input[name='Commissione']", f"{commissione:.2f}".replace(".", ","))
    page.evaluate("document.RendimentoBOT.requestSubmit(document.getElementById('btn-calc'))")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)
    text = page.inner_text("body")
    if "Un campo risulta errato" in text:
        return None
    out = {}
    for label, key in [
        (r"Guadagno lordo \(capital gain\)", "lordo_eur"),
        (r"Ritenuta fiscale \([^)]*\)", "ritenuta_eur"),
        (r"Commissione \([^)]*\)", "commissione_eur"),
        (r"Guadagno netto", "netto_eur"),
    ]:
        m = re.search(label + r"\s*€\s*([\d.,-]+)", text)
        out[key] = parse_euro(m.group(1)) if m else 0.0
    for kind in ("lordo", "netto"):
        m = re.search(rf"Rendimento % {kind} (?!annuale)[^\t\n]*\t\s*([-\d,]+)%", text)
        out[f"{kind}_periodo_pct"] = float(m.group(1).replace(",", "."))
        m = re.search(rf"Rendimento % {kind} annuale\s*([-\d,]+)%", text)
        out[f"{kind}_annuale360_pct"] = float(m.group(1).replace(",", "."))
    return out


def _compare(r, s, giorni):
    lordo_periodo = r["rendimento_lordo_annuo_pct"] * giorni / 365
    netto_periodo = r["rendimento_netto_annuo_pct"] * giorni / 365
    diffs = {
        "plusvalenza": (r["plusvalenza_lorda"], s["lordo_eur"], EUR_TOL),
        "imposta": (r["imposta"], s["ritenuta_eur"], EUR_TOL),
        "commissione": (r["commissione"], s["commissione_eur"], EUR_TOL),
        "guadagno_netto": (r["guadagno_netto"], s["netto_eur"], EUR_TOL),
        "rend_lordo_periodo": (lordo_periodo, s["lordo_periodo_pct"], PCT_TOL),
        "rend_netto_periodo": (netto_periodo, s["netto_periodo_pct"], PCT_TOL),
    }
    bad = {k: (a, b) for k, (a, b, t) in diffs.items() if abs(a - b) > t}
    assert not bad, f"tool vs sito: {bad}"


def test_bot_12_mesi_senza_commissione(page):
    """Piano: scarto 300, imposta 37,50, netto 262,50; lordo 3,0928% e netto
    2,7062% su base 365. Norma: D.Lgs. 239/1996."""
    r = _tool(valore_nominale=10000, prezzo_acquisto=9700, giorni_scadenza=365, commissione_pct=0)
    s = _site(page, "In Giorni", 365, 97.0, 10000, 0.0)
    _compare(r, s, 365)


def test_bot_6_mesi_commissione_010(page):
    """Piano: commissione 0,10% = 10,00; netto 150 - 18,75 - 10 = 121,25;
    rendimento netto 2,4687%. Norma: D.Lgs. 239/1996; DM 15/01/2015."""
    r = _tool(valore_nominale=10000, prezzo_acquisto=9850, giorni_scadenza=182, commissione_pct=0.10)
    s = _site(page, "In Giorni", 182, 98.5, 10000, 0.10)
    _compare(r, s, 182)


def test_bot_sopra_la_pari(page):
    """Piano: prezzo 100,20 a 91 giorni; imposta 0 e commissione azzerata
    (DM 15/01/2015): netto -20,00 (-0,8006%); il tool addebita 5,00 (-1,0007%).
    Limite: il sito rifiuta un prezzo >= 100."""
    r = _tool(valore_nominale=10000, prezzo_acquisto=10020, giorni_scadenza=91, commissione_pct=0.05)
    assert "errore" not in r
    s = _site(page, "In Giorni", 91, 100.2, 10000, 0.05)
    if s is None:
        pytest.skip("il sito rifiuta prezzi sopra la pari ('Un campo risulta errato')")
    _compare(r, s, 91)


def test_bot_semestrale_opzione_enumerata(page):
    """Limite (opzione enumerata 'Semestrale' = 6 mesi commerciali = 180 gg),
    commissione massima proposta dal sito 0,20%. Atteso: scarto 200, imposta
    25, commissione 20, netto 155. Norma: D.Lgs. 239/1996."""
    r = _tool(valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=180, commissione_pct=0.20)
    s = _site(page, "Semestrale", None, 98.0, 10000, 0.20)
    _compare(r, s, 180)


def test_bot_trimestrale_91_giorni(page):
    """Limite: BOT a 91 giorni sotto la pari con commissione 0,05% (massimo
    DM 15/01/2015 a 3 mesi). Atteso: scarto 50, imposta 6,25, commissione 5,
    netto 38,75. Norma: D.Lgs. 239/1996."""
    r = _tool(valore_nominale=10000, prezzo_acquisto=9950, giorni_scadenza=91, commissione_pct=0.05)
    s = _site(page, "In Giorni", 91, 99.5, 10000, 0.05)
    _compare(r, s, 91)
