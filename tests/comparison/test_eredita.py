"""Comparison tests: calcolo_eredita vs avvocatoandreani.it/servizi/calcolo_quote_ereditarie.php."""

import re
from tests.comparison.conftest import assert_close, goto, parse_euro


def _fill_and_calc(page, patrimonio, coniuge=False, figli=0, ascendenti=0, fratelli=0):
    goto(page, "calcolo_quote_ereditarie.php")

    # Use JS form.submit() — page.click on #btn-calc doesn't work because
    # multiple inputs share name='Operazione' (tab buttons + submit)
    js = f"""() => {{
        const form = document.getElementById('QuoteEreditarie');
        form.Patrimonio.value = '{int(patrimonio)}';
        form.Testamento.value = '1';
        form.PrimaChiamata.value = 'N';
        {'form.Coniuge.checked = true;' if coniuge else ''}
        if (form.NumeroFigli) form.NumeroFigli.value = '{figli}';
        if (form.NumeroAscendenti) form.NumeroAscendenti.value = '{ascendenti}';
        if (form.NumeroFratelli) form.NumeroFratelli.value = '{fratelli}';
        // Remove button-type Operazione inputs to avoid ambiguity
        form.querySelectorAll('input[name=Operazione][type=button]').forEach(e => e.remove());
        form.querySelector('input[name=Operazione][type=submit]').value = 'Calcola';
        form.submit();
    }}"""
    page.evaluate(js)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)
    return _parse_result(page)


def _parse_result(page) -> dict:
    body = page.inner_text("body")
    result = {}

    # Site format: "€ 50.000" (no decimals) or "€ 50.000,00"
    # Match "quota disponibile" with euro amount
    m = re.search(
        r"quota\s+disponibil[ei].*?pari\s+a\s+€\s*([\d.]+(?:,\d{2})?)",
        body, re.IGNORECASE
    )
    if m:
        result["disponibile"] = parse_euro(m.group(1))

    # Match coniuge amount
    m = re.search(
        r"[Cc]oniuge.*?€\s*([\d.]+(?:,\d{2})?)",
        body
    )
    if m:
        result["coniuge"] = parse_euro(m.group(1))

    if not result:
        raise ValueError(f"Could not parse eredita results. Body excerpt: {body[:800]}")

    return result


def _our_eredita(patrimonio, coniuge=False, figli=0, ascendenti=False, fratelli=0):
    from src.tools.proprieta_successioni import calcolo_eredita
    fn = getattr(calcolo_eredita, "fn", calcolo_eredita)
    return fn(massa_ereditaria=patrimonio, eredi={
        "coniuge": coniuge, "figli": figli, "ascendenti": ascendenti, "fratelli": fratelli
    })


class TestEreditaComparison:

    def test_coniuge_solo(self, page):
        site = _fill_and_calc(page, 100000, coniuge=True)
        ours = _our_eredita(100000, coniuge=True)
        if "disponibile" in site:
            assert_close(ours["quota_disponibile"], site["disponibile"], tolerance=1, label="disp_coniuge")

    def test_coniuge_un_figlio(self, page):
        site = _fill_and_calc(page, 300000, coniuge=True, figli=1)
        ours = _our_eredita(300000, coniuge=True, figli=1)
        if "disponibile" in site:
            assert_close(ours["quota_disponibile"], site["disponibile"], tolerance=1, label="disp_c1f")

    def test_coniuge_due_figli(self, page):
        site = _fill_and_calc(page, 500000, coniuge=True, figli=2)
        ours = _our_eredita(500000, coniuge=True, figli=2)
        if "disponibile" in site:
            assert_close(ours["quota_disponibile"], site["disponibile"], tolerance=1, label="disp_c2f")
