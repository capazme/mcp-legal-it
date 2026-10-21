"""Benchmark verifica_iban vs avvocatoandreani.it (verifica-codice-iban-nazionale-estero.php).

Norma: ISO 13616 (formato IBAN IT a 27 caratteri), ISO 7064 mod 97-10.
Il sito e' un benchmark, non una fonte. Confronto su: validita' formale,
componenti (checksum, CIN, ABI, CAB, conto) quando il sito le espone.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from conftest import accept_cookies, goto, submit_form  # noqa: E402

import src.server  # noqa: E402,F401
from src.tools.varie import verifica_iban  # noqa: E402

fn = getattr(verifica_iban, "fn", verifica_iban)
PAGE = "verifica-codice-iban-nazionale-estero.php"


def _site(page, iban):
    """Drive the site; return dict(valido, componenti) or None when the site does not submit."""
    goto(page, PAGE, wait_ms=2500)
    accept_cookies(page)  # the CMP overlay may appear late and swallow the click
    page.fill("#Iban", iban)
    submit_form(page)
    accept_cookies(page)
    try:
        page.wait_for_function(
            "document.body.innerText.includes('Il codice IBAN è formalmente corretto')"
            " || document.body.innerText.includes('Il codice IBAN non è corretto')",
            timeout=8000,
        )
    except Exception:
        return None
    t = page.inner_text("body")
    if "Il codice IBAN è formalmente corretto" in t:
        valido = True
    elif "Il codice IBAN non è corretto" in t:
        valido = False
    else:
        return None
    comp = {}
    for label, key in (("Checksum IBAN", "check_digits"), ("CIN", "cin"), ("ABI", "abi"),
                       ("CAB", "cab"), ("Conto corrente", "conto_corrente")):
        m = re.search(rf"^{label}:\t(\S+)", t, re.M)
        if m:
            comp[key] = m.group(1)
    return {"valido": valido, "componenti": comp}


def _check_components(tool, site):
    for k, v in site["componenti"].items():
        assert tool["componenti"][k] == v, f"{k}: tool={tool['componenti'][k]} sito={v}"


def test_iban_valido(page):
    # Piano: valido; checksum 60; CIN X; ABI 05428; CAB 11101; conto 000000123456 (ISO 13616 / mod 97).
    iban = "IT60X0542811101000000123456"
    s = _site(page, iban)
    t = fn(iban=iban)
    assert s is not None
    assert t["valido"] is True and s["valido"] is True
    _check_components(t, s)


def test_iban_con_spazi(page):
    # Piano: identico al caso valido (spazi ignorati dal tool). Il sito con spazi non invia il modulo.
    s = _site(page, "IT60 X054 2811 1010 0000 0123 456")
    t = fn(iban="IT60 X054 2811 1010 0000 0123 456")
    assert t["valido"] is True
    if s is None:
        pytest.skip("il sito non elabora IBAN con spazi (nessun risultato)")
    assert s["valido"] == t["valido"]


def test_cifre_controllo_alterate(page):
    # Piano: non valido (checksum corretto 60). Limite: solo il checksum cambia.
    iban = "IT61X0542811101000000123456"
    s = _site(page, iban)
    t = fn(iban=iban)
    assert s is not None
    assert t["valido"] == s["valido"] is False


def test_cin_alterato(page):
    # Piano: non valido; il sito indica anche il CIN atteso X, il tool no (solo mod 97). Limite: CIN.
    iban = "IT60Y0542811101000000123456"
    s = _site(page, iban)
    t = fn(iban=iban)
    assert s is not None
    assert t["valido"] == s["valido"] is False


def test_lunghezza_errata(page):
    # Limite: 26 caratteri. Norma: formato IT a 27 caratteri (ISO 13616).
    iban = "IT60X054281110100000012345"
    s = _site(page, iban)
    t = fn(iban=iban)
    assert s is not None
    assert t["valido"] == s["valido"] is False


def test_minuscolo(page):
    # Limite: input minuscolo, entrambi normalizzano in maiuscolo.
    iban = "it60x0542811101000000123456"
    s = _site(page, iban)
    t = fn(iban=iban)
    assert s is not None
    assert t["valido"] == s["valido"] is True


def test_san_marino(page):
    # Piano: il tool respinge IBAN non IT per scelta; il mod 97 e' 1 e il sito lo dichiara corretto.
    iban = "SM86U0322509800000000270100"
    s = _site(page, iban)
    t = fn(iban=iban)
    assert s is not None
    assert t["valido"] == s["valido"], f"tool={t['valido']} sito={s['valido']} (scelta di ambito IT)"


def test_trattini(page):
    # Limite: il tool ignora i trattini (doc), il sito conta 28 caratteri e respinge.
    iban = "IT60-X054-2811-1101-0000-0012-3456"
    s = _site(page, iban)
    t = fn(iban=iban)
    assert s is not None
    assert t["valido"] == s["valido"], f"tool={t['valido']} sito={s['valido']}"
