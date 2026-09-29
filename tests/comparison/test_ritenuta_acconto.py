"""Comparison: ritenuta_acconto vs avvocatoandreani.it (calcolo-ritenuta-d-acconto.php).

Norma: art. 25 DPR 600/1973 (ritenuta a titolo d'acconto del 20% sui compensi di
lavoro autonomo; 30% per i percipienti non residenti, co. 2); art. 25-ter DPR
600/1973 (ritenuta del 4% del condominio sostituto d'imposta).

The site's "Dal Lordo al Netto" block posts the whole page (no AJAX) and renders
the result in #R-OutputNetto ("Importo Ritenuta" / "Importo Netto").
Tolerance: 0.01 euro (brief).
"""

import re
import sys

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

sys.path.insert(0, "/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it")
import src.server  # noqa: E402,F401  (registers every tool module)
from src.tools.parcelle_professionisti import ritenuta_acconto  # noqa: E402

_fn = getattr(ritenuta_acconto, "fn", ritenuta_acconto)
TOL = 0.01


def _it(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _site(page, lordo: float, aliquota: float) -> tuple[float, float]:
    """Drive the "Dal Lordo al Netto" block and read ritenuta/netto.

    Two driver pitfalls observed on 2026-09-28:
    - AJAX is disabled (Data.Cfg.AJEnable=0) and a force-click on #btn-calc-netto
      does not post the form headless: submit with form.requestSubmit(button).
    - The fields carry a keystroke input mask: page.fill("20,00") leaves "2" in
      PctRitenutaLordo (the site then computes at 2%). Values are therefore
      assigned via JS, and the values echoed back by the server are checked.
    """
    goto(page, "calcolo-ritenuta-d-acconto.php", wait_ms=1500)
    try:
        page.wait_for_load_state("load", timeout=30000)
    except Exception:
        pass
    page.evaluate(
        "([l, a]) => { document.getElementById('ImportoLordo').value = l;"
        " document.getElementById('PctRitenutaLordo').value = a; }",
        [_it(lordo), _it(aliquota)],
    )
    with page.expect_navigation(timeout=30000):
        page.evaluate(
            "document.Ritenuta.requestSubmit(document.getElementById('btn-calc-netto'))"
        )
    page.wait_for_timeout(1500)
    echo_l = parse_euro(page.input_value("#ImportoLordo"))
    echo_a = parse_euro(page.input_value("#PctRitenutaLordo"))
    assert abs(echo_l - lordo) < 0.005 and abs(echo_a - aliquota) < 0.00005, (
        f"il sito ha ricevuto input diversi: lordo={echo_l} aliquota={echo_a}"
    )
    out = page.inner_text("#R-OutputNetto")
    rit = re.search(r"Importo Ritenuta:\s*€\s*([\d.,]+)", out)
    net = re.search(r"Importo Netto:\s*€\s*([\d.,]+)", out)
    assert rit and net, f"risultato del sito non leggibile: {out!r}"
    return parse_euro(rit.group(1)), parse_euro(net.group(1))


def _compare(page, lordo, aliquota):
    r = _fn(compenso_lordo=lordo, aliquota=aliquota)
    assert "errore" not in r, r
    s_rit, s_net = _site(page, lordo, aliquota)
    print(f"lordo={lordo} aliq={aliquota}: tool rit={r['ritenuta']} net={r['netto_percepito']} "
          f"| sito rit={s_rit} net={s_net}")
    assert_close(r["ritenuta"], s_rit, TOL, "ritenuta")
    assert_close(r["netto_percepito"], s_net, TOL, "netto")


def test_aliquota_ordinaria(page):
    # Piano: ritenuta 200,00; netto 800,00 (art. 25 co. 1 DPR 600/1973, 20%).
    _compare(page, 1000.0, 20.0)


def test_non_residente_30(page):
    # Piano: ritenuta 300,00; netto 700,00 (art. 25 co. 2 DPR 600/1973, 30%).
    _compare(page, 1000.0, 30.0)


def test_arrotondamento_centesimo(page):
    # Piano: ritenuta 15,49 (15,494 arrotondato); netto 61,98. Art. 25 DPR 600/1973.
    _compare(page, 77.47, 20.0)


def test_importo_minimo(page):
    # Piano (limite): ritenuta 0,01; netto 0,04 su lordo 0,05 al 20%.
    _compare(page, 0.05, 20.0)


def test_mezzo_centesimo_30(page):
    # Limite: 100,05 x 30% = 30,015 (mezzo centesimo esatto sulla carta).
    # Atteso con arrotondamento commerciale: ritenuta 30,02; netto 70,03.
    # Art. 25 co. 2 DPR 600/1973.
    _compare(page, 100.05, 30.0)


def test_condominio_4(page):
    # Opzione: aliquota 4% del condominio sostituto d'imposta (art. 25-ter DPR 600/1973).
    # 1.234,56 x 4% = 49,3824 -> ritenuta 49,38; netto 1.185,18.
    _compare(page, 1234.56, 4.0)


def test_campi_certificazione_unica(page):
    # Piano: nella CU (quadro lavoro autonomo) punto 4 = lordo, punto 8 = imponibile,
    # punto 9 = ritenute a titolo d'acconto. Il sito non espone la CU.
    pytest.skip("Il sito non mostra i campi della Certificazione Unica: non confrontabile")
