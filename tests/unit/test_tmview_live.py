"""Live smoke gate for the TMview trademark tools (www.tmdn.org/tmview, the JSON API behind the SPA).

Tools under test: `cerca_marchi`, `leggi_marchio`, `verifica_anteriorita_marchio`
(src/tools/tmview.py over src/lib/tmview/client.py). The source is TMview, the EUIPO /
TMDN aggregator of the national registers (UIBM for Italy); no norm fixes the values, the
checks are on the metadata of a known record.

What it checks, one real call per case, spaced (TMview sits behind an F5 WAF that blocks
bursts; the client itself keeps one second between requests):

* the search for "FUORI CORSO" limited to office IT returns only Italian marks (ST13 "IT…",
  office IT) with holder, Nice classes and filing date, and among them FUORICORSO
  IT502013902128590 (MENNUCCI LETIZIA, classes 25 and 43, filed 19/02/2013, registered
  17/09/2013 under n. 0001557431);
* an invalid Nice class (46) is rejected before any network call;
* the status filter "scaduto" reaches TMview as the code "Expired" (EUIPO marks: every result
  is shown as "Scaduto") — the client only claimed "Registered" as verified live; the SPA
  bundle of 2026-09-25 lists exactly Ended / Expired / Filed / Registered as mark statuses;
* the record IT502013902128590 carries name, office "Italy - UIBM", holder with nationality,
  class 25 among goods and services, application and registration numbers and dates;
* the anteriority check puts FUORICORSO (IT502013902128590) among the IDENTICAL marks for
  "FUORI CORSO" in class 25 / office IT (letters and digits only, case-folded), keeps the
  marks that merely contain the term among the similar ones, and always ends with the
  disclaimer — also when nothing is found (a made-up name), which the tool treats as success.

FIXED DEFECT (found on 2026-09-25, two runs; corrected after the audit):

* `leggi_marchio` on a well-formed but nonexistent ST13 (IT500000000000000): TMview answers
  HTTP 500 with the JSON body {"message":"Can't get trademark/design detail from resource
  url:{}"}. `retry_request` used to retry every 5xx twice (three API hits plus the warm-up,
  against a WAF that counts them) and the tool reported "**Errore**: tmview non raggiungibile"
  (source_down). Now the client stops at the first reply (TMviewNotFoundError) and the tool
  answers error_type no_results, "Nessuna scheda restituita ... ST13 inesistente o scheda ...
  momentaneamente non disponibile". The same endpoint also answers transient 500s for existing
  marks (seen once for IT502013902128590, gone 40 s later), so the wording covers both.

If the WAF turns the client away the tool answers with its anti-bot hint: the case is skipped
as "source temporarily unavailable", never passed.

Needs the network, so it is excluded from the default run. Launch it with:

    .venv/bin/pytest tests/unit/test_tmview_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import re
import time
from unittest.mock import patch

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.tools.tmview import cerca_marchi, leggi_marchio, verifica_anteriorita_marchio

pytestmark = pytest.mark.live

_ST13_FUORICORSO = "IT502013902128590"
_ST13_INESISTENTE = "IT500000000000000"
_DATA_RE = r"\d{2}/\d{2}/\d{4}"
_DISCLAIMER = "Non sostituisce una ricerca di anteriorità professionale"


def _fn(tool):
    return getattr(tool, "fn", tool)


def _run(tool, *, riprova: bool = True, **kwargs) -> str:
    """Call the tool once; on "non raggiungibile" wait 30 s and try once more (positive cases only).

    The detail endpoint answered a transient HTTP 500 for the known ST13 in one of two runs on
    2026-09-25 (200 again 40 s later, and on four fresh sessions after that): one retry keeps a
    passing blip from failing the gate, while a lasting outage or a changed API still fails.
    """
    risultato = asyncio.run(_fn(tool)(**kwargs))
    if riprova and "non raggiungibile" in risultato:
        time.sleep(30)
        risultato = asyncio.run(_fn(tool)(**kwargs))
    if "protezione anti-bot" in risultato:
        pytest.skip(f"TMview: gate anti-bot attivo, fonte temporaneamente non disponibile: {risultato[:200]}")
    return risultato


@pytest.fixture(autouse=True)
def _pausa_tra_le_chiamate():
    """Space the requests to tmdn.org: one call at a time, never a burst."""
    yield
    time.sleep(3)


def _blocchi(testo: str) -> list[str]:
    """Split a markdown result list into its '### ' blocks (one per trademark)."""
    return [b for b in re.split(r"^### ", testo, flags=re.M)[1:] if b.strip()]


def _campo(blocco: str, etichetta: str) -> str:
    """Value of '**Etichetta**: value' up to the next ' | ' or end of line."""
    m = re.search(rf"\*\*{re.escape(etichetta)}\*\*: ([^|\n]*)", blocco)
    return m.group(1).strip() if m else ""


def _st13(blocco: str) -> str:
    return _campo(blocco, "ST13").strip("`")


def _classi(blocco: str) -> set[str]:
    return {c.strip() for c in _campo(blocco, "Classi Nizza").split(",") if c.strip()}


def _normalizza(nome: str) -> str:
    return "".join(ch for ch in nome.casefold() if ch.isalnum())


def _sezione(testo: str, titolo: str) -> str:
    """Text of the '## <titolo>…' section up to the next '## ' heading or the disclaimer."""
    m = re.search(rf"^## {re.escape(titolo)}.*?$(.*?)(?=^## |^\*Verifica preliminare|\Z)", testo, flags=re.M | re.S)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# cerca_marchi
# ---------------------------------------------------------------------------

def test_cerca_marchi_fuori_corso_ufficio_it_trova_fuoricorso_classe_25():
    """Plan case 1: only Italian marks, each with holder, classes and filing date; FUORICORSO among them."""
    r = _run(cerca_marchi, query="FUORI CORSO", uffici="IT", max_risultati=20)
    assert "**Errore**" not in r, r[:600]
    m = re.search(r"\*\*Trovati (\d+) marchi su TMview\*\* \(mostrati (\d+)\)", r)
    assert m and int(m.group(1)) >= 1, r[:600]
    blocchi = _blocchi(r)
    assert len(blocchi) == int(m.group(2)), (len(blocchi), m.group(0))
    for b in blocchi:
        assert _st13(b).startswith("IT"), b[:300]
        assert _campo(b, "Ufficio") == "IT", b[:300]
        assert _campo(b, "Titolare") not in ("", "—"), b[:300]
        assert _classi(b), b[:300]
        assert re.fullmatch(_DATA_RE, _campo(b, "Deposito")), b[:300]

    per_st13 = {_st13(b): b for b in blocchi}
    assert _ST13_FUORICORSO in per_st13, sorted(per_st13)
    b = per_st13[_ST13_FUORICORSO]
    assert b.splitlines()[0].strip() == "FUORICORSO", b[:300]
    assert "25" in _classi(b), b[:300]
    assert _campo(b, "Titolare") == "MENNUCCI LETIZIA", b[:300]
    assert _campo(b, "Stato") == "Registrato", b[:300]
    assert _campo(b, "Deposito") == "19/02/2013", b[:300]
    assert "**Registrazione**: 17/09/2013 (n. 0001557431)" in b, b[:300]
    assert "leggi_marchio(st13)" in r


def test_cerca_marchi_classe_nizza_46_rifiutata_senza_chiamata_di_rete():
    """Plan case 2: Nice classes run from 1 to 45; class 46 is refused before touching the network."""
    with patch("httpx.AsyncClient", side_effect=AssertionError("chiamata di rete non attesa")):
        r = asyncio.run(_fn(cerca_marchi)(query="FUORI CORSO", classi_nizza="46"))
    assert "Classe di Nizza non valida: '46'" in r, r
    assert "da 1 a 45" in r, r


def test_cerca_marchi_stato_scaduto_arriva_come_expired():
    """The 'scaduto' filter maps onto TMview's 'Expired' code: every EUIPO result is shown as Scaduto.

    On office IT the same filter returns nothing for BARILLA (UIBM records seldom carry Expired),
    so the check runs on EUIPO, where 84 BARILLA marks were Expired on 2026-09-25.
    """
    r = _run(cerca_marchi, query="BARILLA", uffici="EM", stato="scaduto", max_risultati=10)
    assert "**Errore**" not in r, r[:600]
    blocchi = _blocchi(r)
    assert blocchi, r[:600]
    for b in blocchi:
        assert _st13(b).startswith("EM"), b[:300]
        assert _campo(b, "Stato") == "Scaduto", b[:300]


# ---------------------------------------------------------------------------
# leggi_marchio
# ---------------------------------------------------------------------------

def test_leggi_marchio_fuoricorso_scheda_completa():
    """Plan case 1: the UIBM record of FUORICORSO with holder, class 25, numbers and dates."""
    r = _run(leggi_marchio, st13=_ST13_FUORICORSO)
    assert "**Errore**" not in r, r[:600]
    assert r.splitlines()[0] == "# FUORICORSO", r[:300]
    assert f"**ST13**: `{_ST13_FUORICORSO}` | **Ufficio**: Italy - UIBM" in r, r[:600]
    assert re.search(r"^\*\*Stato\*\*: Registrato \(", r, flags=re.M), r[:600]
    assert "**Domanda**: n. 2013902128590 del 19/02/2013" in r, r[:600]
    assert "**Registrazione**: n. 0001557431 del 17/09/2013" in r, r[:600]
    assert "**Titolare**: MENNUCCI LETIZIA (IT)" in r, r[:600]
    assert "## Prodotti e servizi (classificazione di Nizza)" in r, r
    assert re.search(r"^- \*\*Classe 25\*\*: .*ABBIGLIAMENTO", r, flags=re.M), r
    assert re.search(rf"Dati dell'ufficio aggiornati al {_DATA_RE}", r), r[-300:]


def test_leggi_marchio_st13_inesistente_e_non_trovato_non_fonte_giu():
    """Plan case 2: a nonexistent ST13 is 'no record returned', not 'source unreachable'.

    TMview answers HTTP 500 {"message":"Can't get trademark/design detail…"} for an unknown ST13
    (same reply for a momentary outage of the office record): the tool must not retry it and
    must not call the source unreachable. The wording is "Nessuna scheda restituita ... ST13
    inesistente o scheda ... momentaneamente non disponibile" (the old assertion looked for
    "Nessun marchio trovato", which would claim non-existence: wrong in form, not in substance).
    """
    r = _run(leggi_marchio, riprova=False, st13=_ST13_INESISTENTE)  # deterministic: no retry
    assert "non raggiungibile" not in r, r[:600]
    assert f"Nessuna scheda restituita da TMview per ST13 `{_ST13_INESISTENTE}`" in r, r[:600]
    assert "ST13 inesistente o scheda dell'ufficio d'origine momentaneamente non disponibile" in r, r[:600]


# ---------------------------------------------------------------------------
# verifica_anteriorita_marchio
# ---------------------------------------------------------------------------

def test_verifica_anteriorita_fuori_corso_classe_25_fuoricorso_tra_gli_identici():
    """Plan case 1: FUORICORSO is IDENTICAL to 'FUORI CORSO' (spaces ignored), high risk; disclaimer last."""
    r = _run(verifica_anteriorita_marchio, nome="FUORI CORSO", classi_nizza="25", uffici="IT")
    assert "**Errore**" not in r, r[:600]
    assert re.search(r"\*\*Verifica anteriorità per\*\* _FUORI CORSO_ — \d+ marchi trovati su TMview", r), r[:300]

    identici = _sezione(r, "Marchi identici")
    assert identici, r[:600]
    assert re.search(r"^## Marchi identici \(\d+\) — rischio alto$", r, flags=re.M), r[:600]
    blocchi_identici = _blocchi(identici)
    assert _ST13_FUORICORSO in {_st13(b) for b in blocchi_identici}, identici[:800]
    for b in blocchi_identici:
        assert _normalizza(b.splitlines()[0]) == "fuoricorso", b[:200]
        assert "25" in _classi(b), b[:300]
        assert _campo(b, "Ufficio") == "IT", b[:300]

    for b in _blocchi(_sezione(r, "Marchi simili o contenenti il termine")):
        assert _normalizza(b.splitlines()[0]) != "fuoricorso", b[:200]
        assert "25" in _classi(b), b[:300]
        assert _campo(b, "Ufficio") == "IT", b[:300]

    assert r.rstrip().endswith(_DISCLAIMER + ".*"), r[-400:]


def test_verifica_anteriorita_nome_inventato_nessun_anteriore_con_avvertenza():
    """Plan case 2: no prior mark for a made-up name in class 25, with the disclaimer still present."""
    r = _run(verifica_anteriorita_marchio, nome="ZXQWVJ KRTPLM", classi_nizza="25", uffici="IT")
    assert "**Errore**" not in r, r[:600]
    assert "**Nessun marchio anteriore trovato su TMview per** _ZXQWVJ KRTPLM_ nelle classi 25." in r, r
    assert _DISCLAIMER in r, r
    assert "somiglianza fonetica, concettuale o grafica" in r, r
