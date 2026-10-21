"""Shared fixtures for the unit tests."""

import copy
import importlib

import pytest

# Last (year, month) of the frozen FOI series served by `foi_serie_fissa`.
#
# The live table in mcp_legal_it/data/indici_foi.json gains one month at every data
# refresh (scripts/refresh_data.py, or the monthly PR opened by
# .github/workflows/data-freshness.yml). Tests that exercise the "index not yet
# published" fallback need to know which month is the last published one and
# which is the first missing one, so pinning them to the live table made every
# refresh PR red by construction. They run on this frozen copy instead: the
# real GU-published values up to 06/2026, nothing after it.
#
# The tests that use the fixture hardcode 06/2026 as the last published month
# and 07/2026 as the first missing one, together with the numbers that follow
# from them. Moving this constant means recomputing those numbers by hand —
# which is the point: they must never move with the live table.
FOI_ULTIMO_MESE_FISSO = (2026, 6)


def _tronca(tabella: dict, anno_max: int, mese_max: int) -> dict:
    """Deep copy of a ``{"YYYY": {"MM": ...}}`` table without anything after (anno_max, mese_max).

    Non-year keys (e.g. ``_descrizione`` in ``variazioni_ufficiali``) are kept as they are.
    The copy is deep so that a test mutating the frozen table in place can never
    touch the live one.
    """
    fissa: dict = {}
    for anno, mesi in copy.deepcopy(tabella).items():
        if not anno.isdigit():
            fissa[anno] = mesi
            continue
        tenuti = {
            mese: valore
            for mese, valore in mesi.items()
            if (int(anno), int(mese)) <= (anno_max, mese_max)
        }
        if tenuti:
            fissa[anno] = tenuti
    return fissa


@pytest.fixture
def foi_serie_fissa(monkeypatch) -> tuple[int, int]:
    """Freeze the FOI series and the official variations at FOI_ULTIMO_MESE_FISSO.

    Patches ``_INDICI_FOI`` and ``_VARIAZIONI_UFFICIALI`` on
    ``mcp_legal_it.tools.rivalutazioni_istat`` for the duration of the test; every tool
    reading the series (including ``calcolo_maggior_danno`` in
    ``tassi_interessi``, which shares the same lookup) sees the frozen copy.
    Returns the frozen (year, month).
    """
    mod = importlib.import_module("mcp_legal_it.tools.rivalutazioni_istat")
    anno, mese = FOI_ULTIMO_MESE_FISSO
    assert f"{mese:02d}" in mod._INDICI_FOI.get(str(anno), {}), (
        f"indici_foi.json non contiene più {mese:02d}/{anno}: "
        "la serie congelata dei test non può essere ricostruita dalla tabella reale"
    )
    monkeypatch.setattr(mod, "_INDICI_FOI", _tronca(mod._INDICI_FOI, anno, mese))
    monkeypatch.setattr(
        mod, "_VARIAZIONI_UFFICIALI", _tronca(mod._VARIAZIONI_UFFICIALI, anno, mese)
    )
    return FOI_ULTIMO_MESE_FISSO


@pytest.fixture(autouse=True)
def _regole_di_rete_neutre(monkeypatch):
    """Every test starts with no pause, no failure count and no interval between requests.

    The per-source limits of ``core/_http`` are process-wide: without this a 429 or a
    breaker opened in one test would hold the next one, and the 0.5 s interval would
    slow every test that sends several requests. ``tests/unit/test_http_rules.py``
    restores the real interval where it checks it.
    """
    from mcp_legal_it.core import _http

    _http._azzera_stato()
    monkeypatch.setattr(_http, "POLITICA", _http.Politica(intervallo=0.0))
    monkeypatch.delenv("LEGAL_CIRCUIT_BREAKER", raising=False)
    yield
    _http._azzera_stato()
