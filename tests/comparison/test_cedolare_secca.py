"""Live comparison: cedolare_secca vs avvocatoandreani.it.

Page: https://www.avvocatoandreani.it/servizi/calcolo-convenienza-cedolare-secca-affitti.php

How the site's figures are mapped onto the tool's
-------------------------------------------------
The site does not print the IRPEF on the rent: it prints the yearly
"Convenienza fiscale" of the cedolare, i.e.

    IRPEF(reddito + base canone) - IRPEF(reddito)      (real 2025 brackets 23/35/43)
  + addizionali on the rent share                      (rate = addizionale / reddito)
  + landlord's half of the registration tax avoided    (2% of rent, 50% landlord)
  + (first year only) half of the stamp duty
  - cedolare

So, from the SECOND year (no stamp duty):

    IRPEF + addizionali  =  convenienza_anno_2 + cedolare - quota_registro_locatore

with quota_registro_locatore = 1% of the rent (libero) and 0.7% (concordato:
registration base reduced by 30%, art. 8 L. 431/1998). The mapping was checked on
four independent inputs (e.g. reddito 1.000 + canone 12.000 -> 2.622 - 2.520 + 120 = 222).

To match the tool's flat marginal rate the income is chosen so that the whole rent
falls in one bracket, and the site's addizionale comunale is set to 2% of the
income, which the site turns into a 2% rate on the rent share - the tool's estimate.

The site rounds its results to the euro; every case below lands on whole euros,
so the brief's 0.01 tolerance is kept.
"""

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo-convenienza-cedolare-secca-affitti.php"


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers every module)
    from src.tools.proprieta_successioni import cedolare_secca

    fn = getattr(cedolare_secca, "fn", cedolare_secca)
    return fn(**kwargs)


def _site(page, *, concordato, canone, reddito, add_comunale, mensile=False):
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.check(f"input[name='CanoneConcordato'][value='{1 if concordato else 0}']", force=True)
    page.fill("input[name='ImportoCanone']", str(canone))
    page.check(f"input[name='TipoImportoCanone'][value='{'m' if mensile else 'a'}']", force=True)
    page.uncheck("input[name='AdeguamentoIstatPrevisto']", force=True)
    page.fill("input[name='RedditoComplessivoIrpef']", str(reddito))
    page.select_option("select[name='CanoneInclusoNelReddito']", "0")  # escluso il canone
    page.fill("input[name='AddizionaleComunale']", str(add_comunale))
    page.select_option("select[name='RiduzioneRedditoLocazioni']", "5")
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.evaluate(
            "document.getElementById('CedolareSecca')"
            ".requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_timeout(1500)
    text = page.inner_text("body")
    start = text.find("Contratto a canone")
    assert start >= 0, "risultato non trovato sulla pagina"
    block = text[start:]

    def _row(label):
        for line in block.splitlines():
            if line.strip().startswith(label):
                cells = [c.strip() for c in line.split("\t") if c.strip()]
                return cells
        raise AssertionError(f"riga '{label}' non trovata")

    canone_annuo = parse_euro(_row("Importo annuale canone")[1])
    cedolare = parse_euro(_row("Cedolare secca calcolata")[1])
    conv_2 = parse_euro(_row("Secondo anno")[1])
    quota_registro = canone_annuo * (0.7 if concordato else 1.0) / 100
    irpef_tot = conv_2 + cedolare - quota_registro
    return {
        "canone_annuo": canone_annuo,
        "cedolare": cedolare,
        "convenienza_anno_2": conv_2,
        "irpef_piu_addizionali": round(irpef_tot, 2),
        "risparmio_netto_registro": round(conv_2 - quota_registro, 2),
    }


def _compare(r, s):
    assert_close(r["cedolare_secca"]["imposta"], s["cedolare"], tolerance=0.01, label="cedolare")
    assert_close(r["irpef_ordinaria"]["totale"], s["irpef_piu_addizionali"], tolerance=0.01,
                 label="irpef+addizionali")
    assert_close(r["risparmio_cedolare"], s["risparmio_netto_registro"], tolerance=0.01,
                 label="risparmio")


def test_libero_marginale_35(page):
    """Piano: cedolare 21% = 2.520,00 (art. 3 co. 2 D.Lgs. 23/2011); IRPEF sul 95% = 3.990,00
    + addizionali. Reddito 35.000 + 11.400 = 46.400: tutto nello scaglione 35% del sito
    (scaglioni 2025; dal 2026 lo scaglione 28-50k e' al 33%, L. 199/2025)."""
    r = _tool(canone_annuo=12000, tipo_contratto="libero", irpef_marginale=35)
    s = _site(page, concordato=False, canone=12000, reddito=35000, add_comunale=700)
    _compare(r, s)


def test_concordato_marginale_23(page):
    """Piano: cedolare 10% = 1.200,00; IRPEF su 12.000 x 95% x 70% = 7.980 -> 1.835,40
    (art. 8 L. 431/1998). Il tool usa il 95% (11.400 -> 2.622,00). Atteso scostamento."""
    r = _tool(canone_annuo=12000, tipo_contratto="concordato", irpef_marginale=23)
    s = _site(page, concordato=True, canone=12000, reddito=1000, add_comunale=20)
    _compare(r, s)


def test_brevi_non_confrontabile(page):
    """Piano: locazione breve, 21% sull'unita' indicata (art. 4 co. 2 DL 50/2017 mod.
    art. 1 co. 63 L. 213/2023); il tool applica 26%. Il sito offre solo libero/concordato."""
    pytest.skip("il sito non offre l'opzione locazioni brevi (solo libero / concordato)")


def test_libero_marginale_43_confine_50000(page):
    """Piano: cedolare 4.200,00; IRPEF sul 95% = 8.170,00 + addizionali.
    Caso al limite: reddito esattamente 50.000 (confine 35/43): tutto il canone
    cade sopra la soglia e si tassa al 43% (art. 11 TUIR)."""
    r = _tool(canone_annuo=20000, tipo_contratto="libero", irpef_marginale=43)
    s = _site(page, concordato=False, canone=20000, reddito=50000, add_comunale=1000)
    _compare(r, s)


def test_libero_marginale_23_confine_28000(page):
    """Caso al limite: reddito 16.600 + 11.400 = 28.000 esatti, tetto del primo scaglione
    (23%, art. 11 TUIR). Atteso: cedolare 2.520,00; IRPEF 2.622,00 + addizionali 228,00."""
    r = _tool(canone_annuo=12000, tipo_contratto="libero", irpef_marginale=23)
    s = _site(page, concordato=False, canone=12000, reddito=16600, add_comunale=332)
    _compare(r, s)


def test_canone_mensile_opzione(page):
    """Opzione enumerata del sito: canone mensile 1.000 (= 12.000 annui), reddito 60.000
    (scaglione 43%). Atteso: cedolare 2.520,00; IRPEF 4.902,00 + addizionali 228,00."""
    r = _tool(canone_annuo=12000, tipo_contratto="libero", irpef_marginale=43)
    s = _site(page, concordato=False, canone=1000, reddito=60000, add_comunale=1200, mensile=True)
    assert_close(s["canone_annuo"], 12000, tolerance=0.01, label="canone annualizzato")
    _compare(r, s)
