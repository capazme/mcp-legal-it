"""Comparison: imposta_registro_locazioni vs avvocatoandreani.it.

Page: /servizi/calcolo-imposta-registro-contratto-locazione.php
Norms: DPR 131/1986 (TUR), Tariffa parte I art. 5 (2% on the annual rent,
minimum EUR 67 for the first registration); art. 17 co. 3 TUR (payment for
the whole duration: discount equal to half the legal interest rate times the
number of years); art. 8 L. 431/1998 (agreed-rent contracts in high-tension
municipalities: taxable base reduced to 70%, so 2% x 70% = 1.4%).

Tolerance: EUR 0.01 on amounts (brief). The site rounds the lump-sum
"Imposta da versare" to whole euros; that case is compared as-is.
"""

import os
import re
import time

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

from tests.comparison.conftest import assert_close, parse_euro  # noqa: E402

URL = "https://www.avvocatoandreani.it/servizi/calcolo-imposta-registro-contratto-locazione.php"


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers modules)
    from src.tools.proprieta_successioni import imposta_registro_locazioni

    fn = getattr(imposta_registro_locazioni, "fn", imposta_registro_locazioni)
    return fn(**kwargs)


def _site(page, canone_annuo, durata, concordato=False, pagamento="r"):
    """Drive the site form; return the result table as {label: amount}."""
    # conftest.goto() removes the Quantcast CMP node via JS; on this page that
    # leaves the form unsubmittable (verified: no result table). Accept the CMP
    # through its own button instead, then submit with a forced click.
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    try:
        page.click("#qc-cmp2-container button[mode='primary']", timeout=4000)
    except Exception:
        pass
    page.select_option("select[name='TipoImmobile']", "Fabbricato ad uso abitativo")
    page.select_option("select[name='DurataContratto']", str(durata))
    page.fill("input[name='ImportoCanone']", str(canone_annuo).replace(".", ","))
    page.evaluate(
        """([conc, pag]) => {
            document.querySelector("input[name='TipoDurata'][value='a']").checked = true;
            document.querySelector("input[name='TipoImportoCanone'][value='a']").checked = true;
            document.querySelector("input[name='CanoneConcordato']").checked = conc;
            document.querySelector("input[name='SoggettoIva']").checked = false;
            document.querySelector(`input[name='TipoPagamento'][value='${pag}']`).checked = true;
        }""",
        [concordato, pagamento],
    )
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    out = {}
    for tb in page.query_selector_all("table"):
        txt = tb.inner_text()
        if "Imposta di registro per la locazione" not in txt:
            continue
        for line in txt.splitlines():
            m = re.match(r"\s*(.+?)\s*\t\s*€\s*([\d.,]+)", line)
            if m:
                out[m.group(1).strip()] = parse_euro(m.group(2))
            m2 = re.match(r"\s*Tipologia del canone\s*\t\s*(\S+)", line)
            if m2:
                out["_tipologia"] = m2.group(1)
    time.sleep(1)
    assert out, "site returned no result table"
    print("SITE", canone_annuo, durata, concordato, pagamento, out)
    return out


def _get(d, prefix):
    # With a two-year contract the site labels the second instalment
    # "Rata successiva" instead of "Ciascuna delle successive N rate".
    prefixes = (prefix, "Rata successiva") if prefix.startswith("Ciascuna delle successive") else (prefix,)
    for k, v in d.items():
        if k.startswith(prefixes):
            return v
    raise KeyError(f"{prefix!r} not in {list(d)}")


def test_libero_4_anni_rateale(page):
    # Piano case 1 (annual payment): 12,000 x 2% = 240.00 per year, 960 in total.
    # Norm: Tariffa parte I art. 5 TUR.
    r = _tool(canone_annuo=12000, durata_anni=4, tipo_contratto="libero", prima_registrazione=True)
    s = _site(page, 12000, 4, pagamento="r")
    print("TOOL", r)
    assert_close(r["imposta_prima_annualita"], _get(s, "Prima rata"), 0.01, "prima annualita")
    assert_close(r["imposta_annualita_successive"], _get(s, "Ciascuna delle successive"), 0.01, "successive")
    assert_close(r["totale_durata_contratto"], _get(s, "Imposta complessiva"), 0.01, "totale")


def test_libero_4_anni_unica_soluzione(page):
    # Piano case 1 (whole duration): 960 less 3.2% (1.6%/2 x 4, art. 17 co. 3 TUR)
    # = 929.28; the tool returns 960.00 (no discount). Expected: genuine deviation.
    r = _tool(canone_annuo=12000, durata_anni=4, tipo_contratto="libero", prima_registrazione=True)
    s = _site(page, 12000, 4, pagamento="u")
    print("TOOL", r)
    # The site rounds the amount due to whole euros (929.00); compared as-is.
    assert_close(r["opzione_intera_durata"], _get(s, "Imposta da versare"), 0.01, "intera durata")


def test_minimo_67_prima_annualita(page):
    # Piano case 2 (limit: minimum): 3,000 x 2% = 60 -> first year raised to 67.00,
    # following years 60.00, total 247.00. Norm: art. 5 Tariffa parte I, minimum 67.
    r = _tool(canone_annuo=3000, durata_anni=4, tipo_contratto="libero")
    s = _site(page, 3000, 4, pagamento="r")
    print("TOOL", r)
    assert_close(r["imposta_prima_annualita"], _get(s, "Prima rata"), 0.01, "prima (minimo)")
    assert_close(r["imposta_annualita_successive"], _get(s, "Ciascuna delle successive"), 0.01, "successive")
    assert_close(r["totale_durata_contratto"], _get(s, "Imposta complessiva"), 0.01, "totale")


def test_minimo_unica_soluzione(page):
    # Piano case 2 (whole duration): 240 less 3.2% = 232.32 (tool 247.00).
    # Limit case: minimum 67 interacting with the lump-sum discount.
    r = _tool(canone_annuo=3000, durata_anni=4, tipo_contratto="libero")
    s = _site(page, 3000, 4, pagamento="u")
    print("TOOL", r)
    assert_close(r["opzione_intera_durata"], _get(s, "Imposta da versare"), 0.01, "intera durata (minimo)")


def test_soglia_minimo_3350(page):
    # Limit case: 3,350 x 2% = 67.00 exactly (threshold of the minimum);
    # first year 67.00, following 67.00, total over 2 years 134.00.
    r = _tool(canone_annuo=3350, durata_anni=2, tipo_contratto="libero")
    s = _site(page, 3350, 2, pagamento="r")
    print("TOOL", r)
    assert_close(r["imposta_prima_annualita"], _get(s, "Prima rata"), 0.01, "prima (soglia)")
    assert_close(r["totale_durata_contratto"], _get(s, "Imposta complessiva"), 0.01, "totale (soglia)")


def test_concordato_6000_3_anni(page):
    # Piano case 3: 6,000 x 70% x 2% = 84.00 per year (art. 8 L. 431/1998);
    # the tool applies 1% (60, raised to 67). Expected: genuine deviation.
    r = _tool(canone_annuo=6000, durata_anni=3, tipo_contratto="concordato")
    s = _site(page, 6000, 3, concordato=True, pagamento="r")
    print("TOOL", r)
    assert_close(r["imposta_prima_annualita"], _get(s, "Prima rata"), 0.01, "concordato prima")
    assert_close(r["imposta_annualita_successive"], _get(s, "Ciascuna delle successive"), 0.01, "concordato successive")


def test_concordato_12000_4_anni(page):
    # Option case (enumerated 'concordato', above the minimum): 12,000 x 70% x 2%
    # = 168.00 per year (art. 8 L. 431/1998); the tool gives 120.00 (1%).
    r = _tool(canone_annuo=12000, durata_anni=4, tipo_contratto="concordato")
    s = _site(page, 12000, 4, concordato=True, pagamento="r")
    print("TOOL", r)
    assert_close(r["imposta_prima_annualita"], _get(s, "Prima rata"), 0.01, "concordato prima")
    assert_close(r["totale_durata_contratto"], _get(s, "Imposta complessiva"), 0.01, "concordato totale")


def test_annualita_successiva_senza_minimo(page):
    # Piano case 4: following year, no minimum: 12,000 x 2% = 240.00.
    # The site has no "annualita successiva" option; a one-year contract gives the
    # annual tax (240 > 67, so the minimum is irrelevant) and is the closest match.
    r = _tool(canone_annuo=12000, durata_anni=1, tipo_contratto="libero", prima_registrazione=False)
    s = _site(page, 12000, 1, pagamento="r")
    print("TOOL", r)
    site_val = next(v for k, v in s.items() if not k.startswith("Canone") and not k.startswith("_"))
    assert_close(r["imposta_annualita_successive"], site_val, 0.01, "annualita successiva")


def test_annualita_successiva_canone_basso(page):
    # Limit case: following year with low rent (3,000 x 2% = 60): no minimum on
    # following years (tool 60.00). The site shows the following-year rate in the
    # rateale breakdown of a multi-year contract ("Ciascuna delle successive").
    r = _tool(canone_annuo=3000, durata_anni=1, tipo_contratto="libero", prima_registrazione=False)
    s = _site(page, 3000, 2, pagamento="r")
    print("TOOL", r)
    assert_close(r["imposta_annualita_successive"], _get(s, "Ciascuna delle successive"), 0.01, "successiva bassa")
