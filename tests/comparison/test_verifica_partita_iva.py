"""Benchmark verifica_partita_iva vs avvocatoandreani.it/servizi/verifica-partita-iva.php.

Norma: art. 35 DPR 633/1972 (11 cifre: 7 matricola, 3 codice ufficio, 1 controllo).
Il sito legge l'esito dalla riga "La Partita IVA e' formalmente corretta / errata"
e mostra matricola, ufficio (con provincia) e cifra di controllo.

Phase 3: the tool's codice_ufficio now reads digits 8-10 (fixed). The site also rejects
office codes it does not know (000, 101, 890); the list of assigned codes has no primary
source that could be read (art. 35 DPR 633/1972 does not define it), so the tool keeps
validating the check digit only: open point (da_chiarire), the related cases stay red.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import src.server  # noqa: F401,E402
from src.tools.varie import verifica_partita_iva  # noqa: E402

from tests.comparison.conftest import accept_cookies  # noqa: E402

_fn = getattr(verifica_partita_iva, "fn", verifica_partita_iva)
URL = "https://www.avvocatoandreani.it/servizi/verifica-partita-iva.php"


def _with_check(base10: str) -> str:
    """Append the correct check digit (art. 35 algorithm) to 10 digits."""
    s = 0
    for i, c in enumerate(base10):
        d = int(c)
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        s += d
    return base10 + str((10 - s % 10) % 10)


def _sito(page, piva: str) -> dict:
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("#PartitaIva", piva)
    page.click("#btn-calc", force=True)
    page.wait_for_timeout(2500)
    t = page.inner_text("body")
    out = {"testo": t}
    m = re.search(r"Ufficio\s*=\s*(\d{3})\s*:\s*([^\n]*)", t)
    out["ufficio"] = m.group(1) if m else None
    out["ufficio_desc"] = m.group(2).strip() if m else None
    out["valida"] = "formalmente corretta" in t
    out["errata"] = "Partita IVA è errata" in t
    return out


def _confronta(page, piva: str, check_ufficio: bool = True):
    tool = _fn(partita_iva=piva)
    s = _sito(page, piva)
    assert s["valida"] or s["errata"], "esito non leggibile sul sito"
    assert tool["valido"] == s["valida"], f"tool valido={tool['valido']} sito valida={s['valida']} ({s['ufficio_desc']})"
    if check_ufficio and s["ufficio"]:
        assert tool["codice_ufficio"] == s["ufficio"], (
            f"codice_ufficio tool={tool['codice_ufficio']} sito={s['ufficio']} (cifre 8-10)"
        )


def test_piva_valida(page):
    # Piano: valida (controllo 7); codice ufficio = cifre 8-10 = 015. Art. 35 DPR 633/1972.
    _confronta(page, "00743110157")


def test_piva_valida_solo_esito(page):
    # Stesso caso, solo esito di validita' (il codice ufficio e' testato a parte).
    _confronta(page, "00743110157", check_ufficio=False)


def test_cifra_controllo_errata(page):
    # Piano: non valida, attesa 7 presente 8. Al limite: differisce dalla valida per la sola ultima cifra.
    tool = _fn(partita_iva="00743110158")
    s = _sito(page, "00743110158")
    assert tool["valido"] is False and s["errata"]
    assert tool["cifra_controllo_attesa"] == 7
    assert "mi aspetto 7" in s["testo"]


def test_ufficio_non_attribuito_890(page):
    # Piano: 12345678903 con checksum corretto ma ufficio 890 non attribuito -> non valida (LIMITE).
    _confronta(page, "12345678903", check_ufficio=False)


def test_tutti_zeri(page):
    # Piano: 00000000000 non valida (matricola nulla, ufficio 000) (LIMITE).
    _confronta(page, "00000000000", check_ufficio=False)


def test_ufficio_100_limite_alto_ordinario(page):
    # LIMITE: 100 e' l'ultimo codice ufficio ordinario (001-100); checksum corretto.
    _confronta(page, _with_check("0074311100"), check_ufficio=False)


def test_ufficio_101_primo_non_attribuito(page):
    # LIMITE: 101 subito oltre 100, checksum corretto.
    _confronta(page, _with_check("0074311101"), check_ufficio=False)


def test_ufficio_121_speciale(page):
    # LIMITE: 120/121 sono codici speciali secondo python-stdnum; checksum corretto.
    _confronta(page, _with_check("0074311121"), check_ufficio=False)


def test_ufficio_999(page):
    # LIMITE: 999 (codice speciale per stdnum); checksum corretto.
    _confronta(page, _with_check("0074311999"), check_ufficio=False)


def test_lunghezza_errata(page):
    # Input non valido: 4 cifre. Il sito segnala "Il codice deve essere lungo 11", il tool errore.
    tool = _fn(partita_iva="1234")
    s = _sito(page, "1234")
    assert tool["valido"] is False and "errore" in tool
    assert "lungo 11" in s["testo"]
