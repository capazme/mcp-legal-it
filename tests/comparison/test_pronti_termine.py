# FASE 3 (verdetto: sito_errato). Amounts coincide. The site's net annual yield divides by capital PLUS
# the withholding tax; on a full year 222/10.000 must be 2,22% (site 2,203%). For a PCT the ritenuta is
# taken on the proventi when they are paid at maturity (art. 26 c. 3-bis DPR 600/1973; art. 2 D.Lgs.
# 239/1996 for titoli di Stato at 12,5%, DL 66/2014 26% otherwise), so it is not part of the capital laid
# out. The tool divides by the capital: correct, nothing changed.
"""Comparison: pronti_termine vs avvocatoandreani.it (calcolo-rendimento-pronti-contro-termine.php).

Norma: art. 3 D.L. 66/2014 (26% in generale; 12,5% sui proventi di PCT su titoli
pubblici, via D.Lgs. 239/1996 e circ. AdE 19/E/2014).

Driving the site:
- the form (#RendimentoPCT) does not submit through a click on #btn-calc in
  headless Chromium (a JS handler swallows it, no POST reaches the server), so
  the form is submitted with HTMLFormElement.prototype.submit.
- the tool has no expenses: SpeseOperazione / SpeseGestione are left empty.
- the tool takes the tax rate from tipo_sottostante: the site field
  AliquotaFiscale is filled with the same rate (12,50 or 26,00).
- the site declares 365-day year and simple interest (notes 2 and 3), same as the tool.

Tolerances: 0,01 EUR on amounts. The site prints percentages with only three
decimals, so the annual net yield is compared with a 0.0005 tolerance (half a
unit of the last printed digit) instead of the brief's four decimals: a finer
comparison is impossible with what the site prints.
"""

import re
import sys

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, parse_euro

sys.path.insert(0, "/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it")

URL = "https://www.avvocatoandreani.it/servizi/calcolo-rendimento-pronti-contro-termine.php"


def _tool(**kw):
    import src.server  # noqa: F401  (registers modules, avoids circular imports)
    from src.tools.investimenti import pronti_termine

    fn = getattr(pronti_termine, "fn", pronti_termine)
    return fn(**kw)


def _site(page, capitale, tasso, giorni, aliquota):
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1000)
    f = "form#RendimentoPCT "
    page.fill(f + "input[name='Durata']", str(giorni))
    page.check(f + "input[name='TipoDurata'][value='1']", force=True)  # giorni
    page.fill(f + "input[name='CapitaleAPronti']", f"{capitale:.2f}".replace(".", ","))
    page.fill(f + "input[name='RendimentoLordo']", f"{tasso}".replace(".", ","))
    page.check(f + "input[name='TipoRend'][value='1']", force=True)  # annuale
    # A page script blanks AliquotaFiscale when it is typed into with fill() (the
    # POST then carries an empty rate and the site applies no tax): set the value
    # directly, after the other fields, and check it before submitting.
    rate = f"{aliquota:.2f}".replace(".", ",")
    page.evaluate(
        "v => { document.querySelector('#RendimentoPCT [name=AliquotaFiscale]').value = v }", rate
    )
    assert page.eval_on_selector(f + "input[name='AliquotaFiscale']", "e => e.value") == rate
    page.evaluate(
        "HTMLFormElement.prototype.submit.call(document.getElementById('RendimentoPCT'))"
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    body = page.inner_text("body")

    def euro(label):
        m = re.search(re.escape(label) + r"[^€]{0,80}€\s*([\d.,]+)", body)
        assert m, f"etichetta non trovata sul sito: {label} -- {body[body.find('Guadagno lordo'):][:300]!r}"
        return parse_euro(m.group(1))

    def pct(label):
        m = re.search(re.escape(label) + r"[^\n]*?\t\s*(-?[\d.,]+)%", body)
        assert m, f"etichetta non trovata sul sito: {label} -- {body[body.find('Guadagno lordo'):][:300]!r}"
        return float(m.group(1).replace(".", "").replace(",", "."))

    return {
        "lordo": euro("Guadagno lordo (capital gain)"),
        "ritenuta": euro("Ritenuta fiscale ("),
        "netto": euro("Guadagno netto"),
        "rend_netto_annuo": pct("Rendimento % netto annuale"),
    }


def _compare(page, capitale, tasso, giorni, tipo, aliquota):
    r = _tool(capitale=capitale, tasso_lordo_pct=tasso, giorni=giorni, tipo_sottostante=tipo)
    assert "errore" not in r, r
    assert r["aliquota_pct"] == aliquota
    s = _site(page, capitale, tasso, giorni, aliquota)
    print("TOOL", r)
    print("SITE", s)
    assert_close(r["interessi_lordi"], s["lordo"], 0.01, "interessi lordi")
    assert_close(r["imposta"], s["ritenuta"], 0.01, "ritenuta")
    assert_close(r["interessi_netti"], s["netto"], 0.01, "interessi netti")
    assert_close(r["rendimento_netto_annuo_pct"], s["rend_netto_annuo"], 0.0005,
                 "rendimento netto annuo %")


def test_titoli_stato_90_giorni(page):
    # Piano: lordi 863,01 (base 365), imposta 12,5% = 107,88, netti 755,14,
    # rendimento netto 3,0625%. Norma: art. 3 co. 2 D.L. 66/2014 (12,5%).
    _compare(page, 100000, 3.5, 90, "titoli_stato", 12.5)


def test_altro_180_giorni(page):
    # Piano: lordi 986,30, imposta 26% = 256,44, netti 729,86, rendimento netto 2,96%.
    # Norma: art. 3 co. 1 D.L. 66/2014 (26%).
    _compare(page, 50000, 4.0, 180, "altro", 26.0)


def test_limite_anno_intero_365_giorni(page):
    # Caso al limite: durata pari all'anno solare (365 gg) -> lordi = capitale x tasso.
    # Atteso: lordi 300,00, imposta 26% = 78,00, netti 222,00, netto annuo 2,22%.
    _compare(page, 10000, 3.0, 365, "altro", 26.0)


def test_limite_un_giorno(page):
    # Caso al limite: durata minima (1 giorno), titoli di Stato 12,5%.
    # Atteso: lordi 1.000.000 x 2% / 365 = 54,79; imposta 6,85; netti 47,95.
    _compare(page, 1000000, 2.0, 1, "titoli_stato", 12.5)


def test_sottostante_non_ammesso():
    # Piano: tipo_sottostante 'misto' -> errore del tool. Il sito non ha il concetto
    # di sottostante (chiede l'aliquota libera): non confrontabile.
    r = _tool(capitale=50000, tasso_lordo_pct=4.0, giorni=180, tipo_sottostante="misto")
    assert "errore" in r
    pytest.skip("non confrontabile: il sito non distingue il sottostante, chiede l'aliquota "
                "(il tool rifiuta 'misto' come atteso)")
