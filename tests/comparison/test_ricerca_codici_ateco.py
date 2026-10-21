"""Comparison: ricerca_codici_ateco vs avvocatoandreani.it/servizi/ricerca-codici-ateco.php

The site uses ATECO 2025, the tool uses ATECO 2007 (codici_ateco.json, vintage
da_verificare). Only the coefficient di redditivita' (percentage, exact) is compared,
and only for codes that both sides know and for which the site shows a coefficient.
The site does not offer a coefficient for every code (e.g. 79.11.00, 88.91.00): those
cases are skipped as not comparable.

The site search is a jQuery autocomplete (svc-mod/jdecode.php) and the detail is a POST
of the hidden form with SelCod set, so the driver replays exactly that.
"""

import os
import re

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-29")

import src.server  # noqa: E402,F401
from src.tools.varie import ricerca_codici_ateco  # noqa: E402
from tests.comparison.conftest import accept_cookies  # noqa: E402

_fn = getattr(ricerca_codici_ateco, "fn", ricerca_codici_ateco)
URL = "https://www.avvocatoandreani.it/servizi/ricerca-codici-ateco.php"


def _open(page):
    page.goto(URL, wait_until="domcontentloaded")
    accept_cookies(page)


def site_coefficiente(page, codice):
    """Return (denominazione, coefficiente|None) shown by the site for a code, or None."""
    _open(page)
    with page.expect_navigation():
        page.evaluate(
            "code => {document.querySelector('#Cerca').value = code;"
            "document.querySelector('#SelCod').value = code;"
            "document.forms['RicercaAteco'].requestSubmit(document.querySelector('#btn-search'));}",
            codice,
        )
    body = page.inner_text("body")
    i = body.find("CODICE ATECO\n")
    if i < 0:
        return None
    seg = body[i : body.find("Pubblicità", i)]
    lines = [ln for ln in seg.split("\n") if ln.strip()]
    if len(lines) < 3 or lines[2].strip() != codice:
        return None
    m = re.search(r"Coefficiente di redditività:\s*([\d,]+)%", seg)
    return lines[1], (float(m.group(1).replace(",", ".")) if m else None)


def site_codici(page, keyword):
    _open(page)
    rows = page.evaluate(
        "kw => fetch('/svc-mod/jdecode.php?t=ateco&cr=1&or=&mc=4&m=100&s='"
        "+encodeURIComponent(kw)+'&term='+encodeURIComponent(kw)).then(r => r.json())",
        keyword,
    )
    return {r["value"] for r in rows}


def tool_voce(codice):
    r = _fn(keyword=codice)
    for v in r.get("risultati", []):
        if v["codice"] == codice:
            return v
    raise AssertionError(f"codice {codice} assente dal tool")


def _confronta(page, codice):
    v = tool_voce(codice)
    s = site_coefficiente(page, codice)
    if s is None:
        pytest.skip(f"non_confrontabile: {codice} non esiste in ATECO 2025 sul sito")
    if s[1] is None:
        pytest.skip(f"non_confrontabile: il sito non mostra il coefficiente per {codice}")
    assert v["coefficiente"] == s[1], (
        f"{codice}: tool {v['coefficiente']}% vs sito {s[1]}% ({s[0]})"
    )


def test_avvocati_69_10_10(page):
    _confronta(page, "69.10.10")


def test_impianti_elettrici_43_21_01(page):
    # 86% group "Costruzioni e attivita' immobiliari" (divisione 43)
    _confronta(page, "43.21.01")


def test_limite_strutture_metalliche_25_11_00(page):
    # boundary between groups: divisione 25 (manifattura) must not take the 86% of costruzioni
    _confronta(page, "25.11.00")


def test_limite_pane_10_71_10(page):
    # boundary: divisione 10 (industrie alimentari) vs generic manufacturing
    _confronta(page, "10.71.10")


def test_commercio_dettaglio_47_71_10(page):
    _confronta(page, "47.71.10")


def test_agenzie_viaggio_79_11_00(page):
    _confronta(page, "79.11.00")


def test_asili_nido_88_91_00(page):
    _confronta(page, "88.91.00")


def test_keyword_affitto_codice_presente_sul_sito(page):
    codici_tool = {v["codice"] for v in _fn(keyword="affitto")["risultati"]}
    assert codici_tool, "il tool non trova nulla per 'affitto'"
    assert codici_tool <= site_codici(page, "affitto")


def test_keyword_viaggi_codice_presente_sul_sito(page):
    codici_tool = {v["codice"] for v in _fn(keyword="viaggi")["risultati"]}
    assert codici_tool, "il tool non trova nulla per 'viaggi'"
    assert codici_tool <= site_codici(page, "viaggi")
