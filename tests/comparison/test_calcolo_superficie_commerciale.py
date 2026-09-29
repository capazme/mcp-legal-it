"""Comparison: calcolo_superficie_commerciale vs avvocatoandreani.it.

Page: https://www.avvocatoandreani.it/servizi/calcolo-superficie-commerciale.php
("Indicazioni OMI e D.P.R. 138/98").

Driving notes
- The page posts through an AJAX helper (``JQAjax``) that never loads in a
  headless browser, so clicking "Calcola" does nothing. The form also has a
  plain POST fallback (action ``./calcolo-superficie-commerciale.php#Res``):
  the driver fills the fields and calls ``HTMLFormElement.prototype.submit``
  with ``Op=Calcola``; the server then renders the result in ``#R-Output``.
- The site works on the gross surface (DPR 138/1998 all. C: walls up to
  50 cm); the tool starts from ``superficie_calpestabile``. The same number is
  entered on the site as "Complessiva", so both sides weigh the same base.
- Pertinenze: Balcone is always "comunicante"; Terrazza defaults to
  comunicante (checkbox pre-checked); Cantina/Box default non comunicante;
  Giardino has no comunicante flag.

Site rounding: the headline total is rounded to the whole mq; the driver sums
the breakdown rows instead (see ``_site``).

Tolerance: 0,01 mq (same as the brief's 0,01 euro on amounts).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close

URL = "https://www.avvocatoandreani.it/servizi/calcolo-superficie-commerciale.php"

# tool keyword -> site pertinenza code
_PCOD = {
    "balconi": "v24",
    "terrazzi": "v43",
    "giardino": "v30",
    "cantina": "v27",
    "garage": "v25",  # "Box" (the site also has v26 "Garage": same flags)
}


def _call_tool(**kwargs):
    import src.server  # noqa: F401  (registers every module)
    from src.tools.proprieta_successioni import calcolo_superficie_commerciale

    fn = getattr(calcolo_superficie_commerciale, "fn", calcolo_superficie_commerciale)
    return fn(**kwargs)


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _site(page, superficie: float, pertinenze: dict, cod_gruppo: str = "1") -> tuple[float, str]:
    """Drive the site; return (superficie commerciale, full output text)."""
    page.goto(URL, timeout=60000, wait_until="load")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    page.select_option("#CodGruppo", cod_gruppo)
    page.fill("#Superficie", f"{superficie:g}".replace(".", ","))
    idx = 0
    for key, mq in pertinenze.items():
        if not mq:
            continue
        if idx > 0:
            # The "Aggiungi pertinenza" div ignores a synthetic click in
            # headless Chromium; the page's own handler is App.AddPertinenze().
            page.evaluate("App.AddPertinenze()")
            page.wait_for_selector(f"#PCod-{idx}", state="attached", timeout=10000)
            page.wait_for_timeout(500)
        page.select_option(f"#PCod-{idx}", _PCOD[key])
        page.wait_for_timeout(200)
        page.fill(f"#PSup-{idx}", f"{mq:g}".replace(".", ","))
        idx += 1
    with page.expect_navigation(timeout=60000):
        page.evaluate(
            "var f=document.SuperficieCommerciale;"
            "var i=document.createElement('input');i.type='hidden';i.name='Op';i.value='Calcola';"
            "f.appendChild(i);HTMLFormElement.prototype.submit.call(f)"
        )
    page.wait_for_timeout(2000)
    out = page.inner_text("#R-Output")
    m = re.search(r"Superficie commerciale calcolata:\s*([\d.,]+)\s*Mq", out)
    assert m, f"risultato non trovato nell'output del sito:\n{out}"
    # The headline ("Superficie commerciale calcolata") and the "Totale
    # immobile" row are rounded to the whole square metre (87,5 -> 88,
    # 90,4 -> 90). The breakdown rows keep the decimals, so the compared value
    # is the sum of the "Commerciale" column of the breakdown rows: this is a
    # parsing choice, not a wider tolerance.
    rows = re.findall(r"^(Vani principali[^\t]*|Pertinenze[^\t]*):\t([\d.,]+) Mq\t([\d.,]+) Mq", out, re.M)
    if not rows:  # no pertinenze: the site prints only the headline
        return _num(m.group(1)), out
    return round(sum(_num(r[2]) for r in rows), 2), out


def _compare(page, label, **kwargs):
    tool = _call_tool(**kwargs)["superficie_commerciale"]
    pert = {k: v for k, v in kwargs.items() if k != "superficie_calpestabile"}
    site, out = _site(page, kwargs["superficie_calpestabile"], pert)
    print(f"\n[{label}] tool={tool} sito={site}\n{out}")
    assert_close(tool, site, tolerance=0.01, label=label)


def test_solo_vani_principali(page):
    # Piano: 100,00 mq se sul sito si inseriscono 100 mq lordi.
    # Norma: DPR 138/1998 all. C, vani principali e accessori diretti al 100%.
    _compare(page, "solo_vani", superficie_calpestabile=100)


def test_balcone_30mq(page):
    # Piano: 80 + 25 x 30% + 5 x 10% = 88,00 mq (DPR 138/1998 all. C,
    # balconi comunicanti 30% fino a 25 mq, 10% oltre); il tool da' 89,90.
    _compare(page, "balcone_30", superficie_calpestabile=80, balconi=30)


def test_balcone_25mq_confine_scaglione(page):
    # Limite: esattamente 25 mq, confine della soglia 30%/10% dell'all. C.
    # Atteso DPR: 80 + 25 x 30% = 87,50 mq; tool (33% fisso) 88,25.
    _compare(page, "balcone_25", superficie_calpestabile=80, balconi=25)


def test_giardino_200mq(page):
    # Piano: 80 + 80 x 10% + 120 x 2% = 90,40 mq (DPR 138/1998 all. C,
    # aree scoperte 10% fino alla superficie dei vani, 2% oltre); tool 100,00.
    _compare(page, "giardino_200", superficie_calpestabile=80, giardino=200)


def test_giardino_80mq_confine_superficie_vani(page):
    # Limite: area scoperta pari alla superficie dei vani (80 mq) -> tutta al
    # 10%: atteso 88,00 mq sia per il DPR sia per il tool (10% fisso).
    _compare(page, "giardino_80", superficie_calpestabile=80, giardino=80)


def test_terrazzo_20mq(page):
    # Piano: 80 + 20 x 30% = 86,00 mq se comunicante (DPR 138/1998 all. C);
    # il tool (25% fisso) da' 85,00. Sito: Terrazza comunicante di default.
    _compare(page, "terrazzo_20", superficie_calpestabile=80, terrazzi=20)


def test_cantina_e_box(page):
    # Piano: cantina non comunicante 25% = 2,5 (50% se comunicante); box da
    # leggere dal sito; il tool (cantina 25%, garage 50%) da' 92,50.
    # Norma: DPR 138/1998 all. C, pertinenze accessorie a servizio indiretto.
    _compare(page, "cantina_box", superficie_calpestabile=80, cantina=10, garage=20)
