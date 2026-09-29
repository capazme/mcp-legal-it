"""Comparison: termini_deposito_atti_appello vs avvocatoandreani.it.

The site page named after the tool (calcolo-termini-deposito-atti-appello.php) computes the
art. 352 c.p.c. terms (note 60, conclusionale 30, replica 15 days before the hearing), which
the tool does not compute. The tool's four terms are therefore matched on two other pages:

- termine breve / lungo (artt. 325, 327 c.p.c.): termini-impugnazioni-civile-amministrativo-
  tributario.php, form ``Impugnazioni`` (Processo=Civile, Impugnazione=1 Appello,
  Decorrenza 1 notifica / 2 pubblicazione, three date selects, SospensioneFeriale checkbox,
  submit #button1). Result: "Termine ultimo: <Giorno> <dd> <Mese> <yyyy>".
- costituzione dell'appellante (10 days forward, art. 165 via art. 347 c.p.c.) and comparsa
  dell'appellato (70 days backward, art. 166 via art. 347 c.p.c., text of D.Lgs. 149/2022):
  calcolo_scadenze_termini_udienze.php, form ``Scadenze`` (GiornoInizio1/MeseInizio1/
  AnnoInizio1, NumeroGiorni, PrimaDopo radio, SospensioneFeriale checkbox, submit #btn_calc).
  Result: "La data di scadenza calcolata è: ..." and, when the raw day is a holiday, a second
  line "Primo giorno precedente|successivo non festivo: dd/mm/yyyy". The adjusted date (second
  line when present) is what is compared with the tool, which returns the adjusted deadline.

Norms: artt. 155, 165, 166, 325, 327, 343, 347 c.p.c.; art. 1 L. 742/1969 (sospensione
feriale 1-31 agosto); L. 260/1949 as amended by L. 151/2025 (4 ottobre festivo dal 2026).
Tolerance: dates must match exactly.
"""

import os
import re
from datetime import date

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

from tests.comparison.conftest import accept_cookies, goto  # noqa: E402

URL_IMPUGNAZIONI = (
    "https://www.avvocatoandreani.it/servizi/"
    "termini-impugnazioni-civile-amministrativo-tributario.php"
)
PAGE_SCADENZE = "calcolo_scadenze_termini_udienze.php"
PAGE_352 = "calcolo-termini-deposito-atti-appello.php"

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11,
    "dicembre": 12,
}


def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  (registers every module, avoids circular imports)
    from src.tools.scadenze_termini import termini_deposito_atti_appello

    fn = getattr(termini_deposito_atti_appello, "fn", termini_deposito_atti_appello)
    r = fn(**kwargs)
    assert "errore" not in r, r
    return {t["termine"]: t.get("scadenza") for t in r["termini"]}


def _site_impugnazione(page, data: str, notificata: bool, feriale: bool = True) -> str:
    """Appeal deadline (civil, Ricorso in Appello) from the impugnazioni page, YYYY-MM-DD."""
    y, m, d = data.split("-")
    page.goto(URL_IMPUGNAZIONI, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1000)
    page.check("#Civile", force=True)
    page.select_option("#Impugnazione", "1")
    page.select_option("#Decorrenza", "1" if notificata else "2")
    page.select_option("#GiornoInizio", d)
    page.select_option("#MeseInizio", m)
    page.select_option("#AnnoInizio", y)
    # Checkbox and submit are set/fired via the DOM: a forced click on #button1 produced
    # no navigation (60 s timeout), requestSubmit with the submitter works.
    page.evaluate(
        "v => { document.querySelector('#SospensioneFeriale').checked = v; }", feriale
    )
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "document.querySelector('form[name=Impugnazioni]')"
            ".requestSubmit(document.querySelector('#button1'))"
        )
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    mt = re.search(r"Termine ultimo:\s*\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})", body)
    assert mt, "site returned no 'Termine ultimo'"
    got = date(int(mt.group(3)), _MESI[mt.group(2).lower()], int(mt.group(1))).isoformat()
    print(f"SITE impugnazione {data} notificata={notificata} feriale={feriale}: {got}")
    return got


def _site_scadenza(page, data: str, giorni: int, verso: str, feriale: bool) -> tuple[str, str]:
    """Generic deadline page. Return (adjusted date YYYY-MM-DD, result text)."""
    y, m, d = data.split("-")
    goto(page, PAGE_SCADENZE)
    page.select_option("#GiornoInizio1", d)
    page.select_option("#MeseInizio1", m)
    page.select_option("#AnnoInizio1", y)
    page.fill("form#Scadenze input[name='NumeroGiorni']", str(giorni))
    # Radio and checkbox do not react to forced clicks (overlay): set them via the DOM.
    page.evaluate(
        "v => { document.querySelector(`form#Scadenze input[name='PrimaDopo'][value='${v}']`)"
        ".checked = true; }",
        verso,
    )
    page.evaluate(
        "v => { document.querySelector(\"form#Scadenze input[name='SospensioneFeriale']\")"
        ".checked = v; }",
        feriale,
    )
    # requestSubmit with the submitter keeps "Calcola" in the POST; a plain click on the
    # button sometimes produced no navigation at all.
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "document.querySelector('form#Scadenze')"
            ".requestSubmit(document.querySelector('#btn_calc'))"
        )
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    i = body.find("La data di scadenza calcolata")
    assert i >= 0, "site returned no computed deadline"
    j = body.find("GIORNI INTERCORRENTI", i)
    block = body[i: j if j > 0 else i + 300]
    adj = re.search(r"non festivo:\s*(\d{2})/(\d{2})/(\d{4})", block)
    raw = re.search(r"(\d{2})/(\d{2})/(\d{4})", block)
    mt = adj or raw
    assert mt, f"no date in site result: {block!r}"
    got = f"{mt.group(3)}-{mt.group(2)}-{mt.group(1)}"
    text = " | ".join(x.strip() for x in block.splitlines() if x.strip())
    print(f"SITE {data} {verso} {giorni} feriale={feriale}: {got} [{text}]")
    return got, text


# Plan case 1 (limit: August). Art. 325 co. 1 c.p.c. + art. 1 L. 742/1969.
# Expected 2025-09-19: 11 days in July, August skipped, 19 in September.
def test_termine_breve_attraverso_agosto(page):
    tool = _tool(data_notifica_sentenza="2025-07-20")["appello_termine_breve"]
    site = _site_impugnazione(page, "2025-07-20", notificata=True)
    assert tool == site, f"tool {tool} != site {site}"


# Plan case 1 (limit: New Year's Day). Art. 327 c.p.c. + L. 742/1969 + art. 155 co. 4.
# Expected 2026-01-02: six months to 2025-12-01, +31 days = 2026-01-01 (holiday) -> Jan 2.
def test_termine_lungo_capodanno(page):
    tool = _tool(data_pubblicazione="2025-06-01")["appello_termine_lungo"]
    site = _site_impugnazione(page, "2025-06-01", notificata=False)
    assert tool == site, f"tool {tool} != site {site}"


# Plan case 2 (limit: August). Art. 165 via art. 347 c.p.c. (10 days) + L. 742/1969.
# Expected 2025-09-04: 6 days in July, 4 in September.
def test_costituzione_appellante_agosto(page):
    tool = _tool(data_notifica_citazione="2025-07-25")["costituzione_appellante"]
    site, _ = _site_scadenza(page, "2025-07-25", 10, "dopo", True)
    assert tool == site, f"tool {tool} != site {site}"


# Plan case 2 (limit: August + Sunday, backward). Art. 166 via art. 347 c.p.c. (70 days
# before the hearing, D.Lgs. 149/2022) + L. 742/1969 + art. 155 c.p.c.
# Expected 2025-07-04: 44 days Oct-Sep, 26 in July down to Sunday 6, anticipated to Friday 4
# (the tool also skips Saturday, art. 155 co. 5 applied to a backward term). The site
# declares Saturday a working day, so it anticipates only to Saturday 5: convention gap.
def test_comparsa_appellato_agosto_domenica(page):
    tool = _tool(data_udienza="2025-10-15")["comparsa_risposta_appellato"]
    site, _ = _site_scadenza(page, "2025-10-15", 70, "prima", True)
    assert tool == site, f"tool {tool} != site {site}"


# Plan case 3 (limit: suspension off, art. 3 L. 742/1969 excluded matters).
# Expected costituzione 2025-08-04 (art. 165 via 347).
def test_costituzione_appellante_senza_sospensione(page):
    tool = _tool(
        data_notifica_citazione="2025-07-25", sospensione_feriale=False
    )["costituzione_appellante"]
    site, _ = _site_scadenza(page, "2025-07-25", 10, "dopo", False)
    assert tool == site, f"tool {tool} != site {site}"


# Plan case 3 (limit: suspension off). Expected comparsa 2025-08-06 (art. 166 via 347).
def test_comparsa_appellato_senza_sospensione(page):
    tool = _tool(data_udienza="2025-10-15", sospensione_feriale=False)[
        "comparsa_risposta_appellato"
    ]
    site, _ = _site_scadenza(page, "2025-10-15", 70, "prima", False)
    assert tool == site, f"tool {tool} != site {site}"


# Plan case 4. Art. 166 via art. 347 c.p.c. (D.Lgs. 149/2022): 70 days before 2025-12-15
# -> 2025-10-06 (Monday). The pre-2023 20-day term (2025-11-25) is not computed by the tool.
def test_comparsa_appellato_ordinaria(page):
    tool = _tool(data_udienza="2025-12-15")["comparsa_risposta_appellato"]
    site, _ = _site_scadenza(page, "2025-12-15", 70, "prima", True)
    assert tool == site, f"tool {tool} != site {site}"


# Extra (limit: 4 October holiday from 2026, L. 151/2025). 2026-09-24 + 10 = Sunday 4
# October 2026 -> Monday 2026-10-05 (art. 155 co. 4 c.p.c.).
def test_costituzione_appellante_4_ottobre_2026(page):
    tool = _tool(data_notifica_citazione="2026-09-24")["costituzione_appellante"]
    site, _ = _site_scadenza(page, "2026-09-24", 10, "dopo", True)
    assert tool == site, f"tool {tool} != site {site}"


# Extra (limit: Saturday, forward). 2025-10-01 + 10 = Saturday 11 October 2025 ->
# Monday 2025-10-13 (art. 155 co. 5 c.p.c., L. 263/2005). The site does not list Saturday
# among holidays: expected convention gap, recorded as found.
def test_costituzione_appellante_sabato(page):
    tool = _tool(data_notifica_citazione="2025-10-01")["costituzione_appellante"]
    site, _ = _site_scadenza(page, "2025-10-01", 10, "dopo", True)
    assert tool == site, f"tool {tool} != site {site}"


# Not comparable: the page named after the tool computes the art. 352 c.p.c. terms
# (note 60, conclusionale 30, replica 15 days before the hearing), which no tool computes.
def test_pagina_art_352_non_confrontabile(page):
    goto(page, PAGE_352)
    assert "352" in page.title() or "352" in page.inner_text("body")
    pytest.skip(
        "sito: la pagina omonima calcola i termini ex art. 352 c.p.c. (60/30/15 giorni "
        "prima dell'udienza), non calcolati dal tool"
    )
