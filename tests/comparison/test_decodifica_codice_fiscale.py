"""Comparison tests: decodifica_codice_fiscale vs
avvocatoandreani.it/servizi/decodifica_codice_fiscale.php (codice fiscale inverso).

Norma: DM 12/03/1974 (Agenzia delle Entrate); DM 23/12/1976 per il carattere di
controllo e la tabella di omocodia (L-V al posto delle cifre 0-9).
Tolleranza: sesso, data (esatta), comune e carattere di controllo devono coincidere.

Il sito ha un limite di frequenza ("Troppe richieste consecutive"): il driver
distanzia le richieste e riprova. Il sito NON sa leggere l'anno "00" (mostra "?"),
e interpreta sempre l'anno a due cifre come 19xx.
"""

import os
import re
import time

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

from tests.comparison.conftest import accept_cookies

URL = "https://www.avvocatoandreani.it/servizi/decodifica_codice_fiscale.php"


def _tool(cf):
    import src.server  # noqa: F401
    from src.tools.varie import decodifica_codice_fiscale

    fn = getattr(decodifica_codice_fiscale, "fn", decodifica_codice_fiscale)
    return fn(codice_fiscale=cf)


def _check(base):
    import src.server  # noqa: F401
    from src.tools.varie import _cf_check_char

    return base + _cf_check_char(base)


def _site(page, cf):
    """Drive the site; return dict(sesso, data_iso|None, comune, omocodia, atteso_controllo)."""
    body = ""
    for _attempt in range(4):
        time.sleep(7)
        page.goto(URL, wait_until="domcontentloaded")
        accept_cookies(page)
        page.fill("input[name='CodiceFiscale']", cf)
        page.click("#btn-calc", force=True)
        page.wait_for_timeout(2500)
        body = page.inner_text("body")
        if "Troppe richieste" not in body:
            break
    if "Dati anagrafici ricavati da" not in body:
        pytest.skip(f"sito non produce il risultato: {body[-400:]!r}")
    k = body.find("Dati anagrafici ricavati da")
    blk = body[k : body.find("Pubblicità", k)]

    def f(label):
        m = re.search(label + r":\s*([^\n\t]+)", blk)
        return m.group(1).strip() if m else None

    d = re.search(r"Data di Nascita:\s*(\d{2})/(\d{2})/(\d{4})", blk)
    m = re.search(r"Mi aspetto la lettera (\w)", blk)
    return {
        "sesso": {"Maschio": "M", "Femmina": "F"}.get(f("Sesso")),
        "data": f"{d.group(3)}-{d.group(2)}-{d.group(1)}" if d else None,
        "comune": f("Comune di Nascita") or f("Stato Estero di Nascita"),
        "omocodia": "omocodia" in blk,
        "atteso_controllo": m.group(1) if m else None,
    }


def _compare(page, cf, compare_date=True):
    ours = _tool(cf)
    assert "errore" not in ours, f"tool: {ours}"
    site = _site(page, cf)
    d = ours["dati"]
    assert d["sesso"] == site["sesso"], f"sesso tool={d['sesso']} sito={site['sesso']}"
    tool_comune = d["comune_nascita"].replace(" (stato estero)", "").upper()
    assert tool_comune == (site["comune"] or "").upper(), f"comune tool={tool_comune} sito={site['comune']}"
    assert ours["carattere_controllo_valido"] == (site["atteso_controllo"] is None), (
        f"controllo tool={ours['carattere_controllo_valido']} sito_atteso={site['atteso_controllo']}"
    )
    if compare_date:
        assert d["data_nascita"] == site["data"], f"data tool={d['data_nascita']} sito={site['data']}"
    return ours, site


class TestDecodificaCodiceFiscale:
    def test_ordinario_roma(self, page):
        # Piano: RSSMRA85H15H501D valido; M; 1985-06-15; ROMA (H501). DM 12/03/1974.
        ours, _ = _compare(page, "RSSMRA85H15H501D")
        assert ours["carattere_controllo_valido"] is True

    def test_omocodico(self, page):
        # Piano: RSSMRA85H15H50MV (cifra 1 -> M). Limite: omocodia, DM 23/12/1976.
        # Il sito segnala anche "codice fiscale modificato per omocodia"; il tool non ha un flag dedicato.
        ours, site = _compare(page, "RSSMRA85H15H50MV")
        assert site["omocodia"] is True
        assert ours["dati"]["codice_catastale"] == "H501"

    def test_anno_29_ambiguo(self, page):
        # Piano: RSSMRA29A01H501P atteso 1929-01-01 (2029 sarebbe futuro rispetto al 25/09/2026).
        # Limite: euristica del secolo.
        _compare(page, "RSSMRA29A01H501P")

    def test_comune_ercolano_h243(self, page):
        # Piano: RSSMRA80A01H243X valido; ERCOLANO (H243), codice corretto nella 2.14.
        ours, _ = _compare(page, "RSSMRA80A01H243X")
        assert ours["dati"]["codice_catastale"] == "H243"

    def test_anno_26_secolo(self, page):
        # Limite: anno 26 = anno corrente al 25/09/2026. 01/01/2026 e' nel passato, ma il sito legge 1926.
        _compare(page, _check("RSSMRA26A01H501"))

    def test_anno_30_confine_euristica(self, page):
        # Limite: primo anno 19xx per l'euristica del tool (30 -> 1930).
        _compare(page, _check("RSSMRA30A01H501"))

    def test_femmina_giorno_41_milano(self, page):
        # Limite: giorno +40 => F; BNCMRA90A41F205J, MILANO (F205).
        _compare(page, "BNCMRA90A41F205J")

    def test_anno_00_non_confrontabile(self, page):
        # Il sito mostra "Data di Nascita: ?" per l'anno 00: nessun confronto sulla data possibile;
        # si confrontano comunque sesso, comune e controllo.
        cf = _check("RSSMRA00A01H501")
        ours, site = _compare(page, cf, compare_date=False)
        assert site["data"] is None
        pytest.skip(f"sito non decodifica l'anno 00 (data='?'); tool={ours['dati']['data_nascita']}")

    def test_stato_estero_germania(self, page):
        # Limite: codice catastale di stato estero Z112. Sito: "Stato Estero di Nascita: GERMANIA", anno 00 -> '?'.
        cf = _check("FOXGUO00B29Z112")
        ours, site = _compare(page, cf, compare_date=False)
        pytest.skip(f"anno 00 non decodificato dal sito; comune tool={ours['dati']['comune_nascita']}")

    def test_carattere_controllo_errato(self, page):
        # Limite: ultimo carattere errato (A invece di D); il sito indica la lettera attesa D.
        ours, site = _compare(page, "RSSMRA85H15H501A")
        assert ours["carattere_controllo_valido"] is False
        assert site["atteso_controllo"] == "D"
