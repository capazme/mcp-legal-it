"""Comparison: scadenze_multe vs avvocatoandreani.it (ricorso-pagamento-multa.php).

Site form (#Ricorso, POST): Stato=2 ("Mi e' stata notificata una multa"), notification
date as GiornoRif/MeseRif/AnnoRif, Azione (1 = ricorso al Prefetto, 2 = ricorso al
Giudice di Pace, 4 = pagare la multa). The result is rendered in #R-Output as a
weekday + long Italian date ("Giovedi 31 Luglio 2025").

Site behaviour worth knowing:
- it reasons on the REAL current date: once the 5-day discount window has expired it
  only shows the 60-day payment term, and a notification date in the future returns an
  empty output. The 5-day term can only be read while it is still open.
- years offered: 2021-2026.

Norms: D.Lgs. 285/1992 artt. 202 (pagamento in misura ridotta, 60 gg; sconto 30% entro
5 gg per art. 20 DL 69/2013 conv. L. 98/2013), 203 (ricorso al prefetto, 60 gg),
204-bis + art. 7 D.Lgs. 150/2011 (ricorso al giudice di pace, 30 gg).
Tolerance: dates must match exactly.
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import re
import sys
from datetime import date, timedelta

import pytest

from tests.comparison.conftest import goto

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import src.server  # noqa: E402,F401  (registers every tool module)
from src.tools.scadenze_termini import scadenze_multe  # noqa: E402

_fn = getattr(scadenze_multe, "fn", scadenze_multe)

PAGE = "ricorso-pagamento-multa.php"
AZIONE = {"prefetto": "1", "giudice_pace": "2", "pagamento": "4"}
_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_DATE_RE = re.compile(r"(\d{1,2}) (" + "|".join(m.capitalize() for m in _MESI) + r") (\d{4})")


def _tool(data_notifica: str, tipo: str) -> dict:
    r = _fn(data_notifica=data_notifica, tipo_ricorso=tipo)
    assert "errore" not in r, r
    return r


def _parse_it_date(match) -> str:
    g, m, y = match.groups()
    return date(int(y), _MESI[m.lower()], int(g)).isoformat()


def _site_output(page, notifica: str, azione: str) -> str:
    y, m, d = notifica.split("-")
    goto(page, PAGE, wait_ms=1500)
    page.select_option("#Stato", "2")
    page.wait_for_timeout(400)
    page.select_option("#GiornoRif", d)
    page.select_option("#MeseRif", m)
    page.select_option("#AnnoRif", y)
    page.select_option("#Azione", AZIONE[azione])
    page.wait_for_timeout(400)
    with page.expect_navigation(timeout=60000):
        # A plain click on #button1 does not submit in headless Chromium; requestSubmit does.
        page.evaluate(
            'document.getElementById("Ricorso").requestSubmit(document.getElementById("button1"))'
        )
    page.wait_for_timeout(1500)
    return page.inner_text("#R-Output")


def _site_first_date(page, notifica: str, azione: str) -> str:
    text = _site_output(page, notifica, azione)
    m = _DATE_RE.search(text)
    assert m, f"no date in site output: {text!r}"
    return _parse_it_date(m)


# --- casi del piano -------------------------------------------------------------

def test_prefetto_60gg(page):
    """Piano: 2025-06-01 prefetto -> 2025-07-31 (art. 203 co. 1 CdS). Site: 31/07/2025."""
    t = _tool("2025-06-01", "prefetto")
    s = _site_first_date(page, "2025-06-01", "prefetto")
    assert t["scadenza"] == s == "2025-07-31"


def test_riepilogo_giudice_pace_30gg(page):
    """Piano: riepilogo giudice_pace 2025-07-01 (art. 204-bis CdS; art. 7 D.Lgs. 150/2011)."""
    t = _tool("2025-06-01", "prefetto")["riepilogo_opzioni"]["giudice_pace"]["scadenza"]
    s = _site_first_date(page, "2025-06-01", "giudice_pace")
    assert t == s == "2025-07-01"


def test_giudice_pace_attraversa_agosto_2025(page):
    """Piano: 2025-07-20 giudice_pace -> 2025-09-19 con sospensione feriale L. 742/1969
    (Cassazione: applicabile all'opposizione a verbale); il tool non sospende e da'
    2025-08-19. LIMITE: agosto."""
    t = _tool("2025-07-20", "giudice_pace")["scadenza"]
    s = _site_first_date(page, "2025-07-20", "giudice_pace")
    assert t == s, f"tool {t} vs sito {s} (sospensione feriale)"


def test_pagamento_5gg_natale_non_confrontabile(page):
    """Piano: 2025-12-20 pagamento_ridotto_5gg -> sabato 2025-12-27 (art. 2963 c.c.), tool
    2025-12-29. Il sito calcola sulla data reale: a termine scaduto mostra solo i 60 giorni."""
    text = _site_output(page, "2025-12-20", "pagamento")
    if "sconto del 30%" not in text or "se paghi entro" not in text:
        pytest.skip("il sito non mostra il termine di 5 giorni quando e' gia' scaduto rispetto a oggi")
    m = _DATE_RE.search(text[text.find("se paghi entro"):])
    assert _tool("2025-12-20", "pagamento_ridotto_5gg")["scadenza"] == _parse_it_date(m)


def test_pagamento_60gg_primo_maggio(page):
    """Piano: 2026-03-02 pagamento_ridotto -> 60o giorno ven 1/5/2026 festivo, proroga a
    sabato 2026-05-02 (art. 2963 c.c.); il tool da' lunedi' 2026-05-04. LIMITE: festivo+sabato."""
    t = _tool("2026-03-02", "pagamento_ridotto")["scadenza"]
    s = _site_first_date(page, "2026-03-02", "pagamento")
    assert t == s, f"tool {t} vs sito {s} (proroga del sabato)"


# --- casi aggiunti --------------------------------------------------------------

def test_pagamento_60gg_a_cavallo_anno(page):
    """2025-12-20 pagamento_ridotto (60 gg, art. 202 co. 1 CdS) -> 2026-02-18 (mercoledi').
    LIMITE: anno diverso."""
    t = _tool("2025-12-20", "pagamento_ridotto")["scadenza"]
    s = _site_first_date(page, "2025-12-20", "pagamento")
    assert t == s == "2026-02-18"


def test_prefetto_scade_sabato(page):
    """2025-06-03 prefetto: il 60o giorno e' sabato 2025-08-02 (art. 203 CdS, termine
    amministrativo: nessuna sospensione feriale; il sabato non e' festivo ex art. 2963 c.c.).
    Il tool proroga a lunedi' 2025-08-04 (art. 155 co. 5 c.p.c.). LIMITE: sabato."""
    t = _tool("2025-06-03", "prefetto")["scadenza"]
    s = _site_first_date(page, "2025-06-03", "prefetto")
    assert t == s, f"tool {t} vs sito {s} (proroga del sabato)"


def test_giudice_pace_scade_sabato(page):
    """2025-09-18 giudice_pace: il 30o giorno e' sabato 2025-10-18. Termine processuale:
    art. 155 co. 5 c.p.c. proroga al lunedi' 2025-10-20 (tool). LIMITE: sabato."""
    t = _tool("2025-09-18", "giudice_pace")["scadenza"]
    s = _site_first_date(page, "2025-09-18", "giudice_pace")
    assert t == s, f"tool {t} vs sito {s} (sabato, art. 155 co. 5 c.p.c.)"


def test_giudice_pace_attraversa_agosto_2026(page):
    """2026-07-10 giudice_pace: senza sospensione 2026-08-09 (domenica) -> 2026-08-10 (tool);
    con sospensione feriale (21 gg luglio + 9 settembre) 2026-09-09. LIMITE: agosto, anno 2026."""
    t = _tool("2026-07-10", "giudice_pace")["scadenza"]
    s = _site_first_date(page, "2026-07-10", "giudice_pace")
    assert t == s, f"tool {t} vs sito {s} (sospensione feriale)"


def test_pagamento_5gg_finestra_aperta(page):
    """Sconto del 30% entro 5 gg (art. 202 co. 1 CdS, art. 20 DL 69/2013). Il sito mostra il
    termine solo se non ancora scaduto rispetto alla data REALE: la notifica e' presa due
    giorni prima di oggi. Confronta sia il termine di 5 gg sia quello di 60 gg."""
    notifica = date.today() - timedelta(days=2)
    if notifica.year > 2026:
        pytest.skip("il sito offre solo gli anni 2021-2026")
    n = notifica.isoformat()
    text = _site_output(page, n, "pagamento")
    assert "se paghi entro" in text, text
    s60 = _parse_it_date(_DATE_RE.search(text))
    s5 = _parse_it_date(_DATE_RE.search(text[text.find("se paghi entro"):]))
    r = _tool(n, "pagamento_ridotto_5gg")
    assert r["scadenza"] == s5, f"5gg: tool {r['scadenza']} vs sito {s5}"
    assert r["riepilogo_opzioni"]["pagamento_ridotto"]["scadenza"] == s60


# Benchmark phase 3 verdict (2026-09-29): tool_errato fixed. The giudice_pace cases needed the feriale
# suspension (art. 1 L. 742/1969; Cass. 11478/2017, 30427/2022) and now match the site. The remaining
# Saturday cases for prefetto/payment (non-procedural terms) now also match: Saturday is a working day.
# The 5-day payment case is not comparable (site uses the real current date).
# Remaining failure test_giudice_pace_scade_sabato: site wrong. The ricorso to the giudice di pace is a
# procedural act outside the hearing, so art. 155 co. 5 c.p.c. prorogues a Saturday expiry to Monday.
