"""Comparison tests: calcolo_irpef vs avvocatoandreani.it/servizi/calcolo-irpef.php."""

import re
import pytest
from tests.comparison.conftest import assert_close, goto, parse_euro

# Our tool uses 2026 IRPEF rates (L. 199/2025: 2nd bracket 33%) while
# avvocatoandreani.it still applies 2025 rates (35%).  Skip until the
# site is updated.  Arithmetic correctness is verified in test_detrazioni.py.
_SKIP_REASON = "Site uses 2025 IRPEF rates (35%); our tool correctly applies 2026 rates (33%, L. 199/2025)"


def _fill_and_calc(page, reddito):
    goto(page, "calcolo-irpef.php")

    # Use JS form.submit() — field name is RedditoComplessivoIrpef
    page.evaluate(f"""() => {{
        const f = document.getElementById('CalcoloIrpef');
        f.RedditoComplessivoIrpef.value = '{int(reddito)}';
        f.submit();
    }}""")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)
    return _parse_result(page)


def _parse_result(page) -> dict:
    body = page.inner_text("body")
    result = {}

    # "IRPEF LORDA € 14.140,00"
    m = re.search(r"IRPEF\s+LORDA\s+€\s*([\d.]+,\d{2})", body, re.IGNORECASE)
    if m:
        result["irpef_lorda"] = parse_euro(m.group(1))

    # Parse scaglioni table: "€ 0,00 € 28.000,00 23% € 6.440,00"
    scaglioni = []
    for m in re.finditer(
        r"€\s*([\d.]+,\d{2})\s+€\s*([\d.]+,\d{2})\s+(\d+)%\s+€\s*([\d.]+,\d{2})",
        body,
    ):
        scaglioni.append({
            "da": parse_euro(m.group(1)),
            "a": parse_euro(m.group(2)),
            "aliquota": int(m.group(3)),
            "imposta": parse_euro(m.group(4)),
        })
    if scaglioni:
        result["scaglioni"] = scaglioni

    if not result:
        raise ValueError(f"Could not parse IRPEF results. Body excerpt: {body[:800]}")

    return result


def _our_irpef(reddito):
    from src.tools.dichiarazione_redditi import calcolo_irpef
    fn = getattr(calcolo_irpef, "fn", calcolo_irpef)
    return fn(reddito_complessivo=reddito, tipo_reddito="autonomo", deduzioni=0, detrazioni_extra=0)


@pytest.mark.skip(reason=_SKIP_REASON)
class TestIrpefComparison:

    def test_reddito_30000(self, page):
        site = _fill_and_calc(page, 30000)
        ours = _our_irpef(30000)
        assert_close(ours["imposta_lorda"], site["irpef_lorda"], tolerance=1, label="irpef_30k")

    def test_reddito_50000(self, page):
        site = _fill_and_calc(page, 50000)
        ours = _our_irpef(50000)
        assert_close(ours["imposta_lorda"], site["irpef_lorda"], tolerance=1, label="irpef_50k")

    def test_reddito_80000(self, page):
        site = _fill_and_calc(page, 80000)
        ours = _our_irpef(80000)
        assert_close(ours["imposta_lorda"], site["irpef_lorda"], tolerance=1, label="irpef_80k")
