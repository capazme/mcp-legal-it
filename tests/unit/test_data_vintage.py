"""Every hand-maintained table has to say how current it is, and say it out loud.

A reader of this project put the risk plainly: the calculations rest on tables
typed by hand, and one of them will eventually be out of date. These tests hold
the two halves of the answer in place — the declaration on the table, and the
line the tool prints next to the number it derived from it.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from src.lib._data import (
    AUTOMATIC,
    MANUAL,
    UNVERIFIED,
    DATA_DIR,
    all_datasets,
    footer,
    sourced,
    vintage,
)

VERIFICHE = {AUTOMATIC, MANUAL, UNVERIFIED}


@pytest.mark.parametrize("dataset", all_datasets())
def test_every_table_declares_a_vintage(dataset):
    payload = json.loads((DATA_DIR / f"{dataset}.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict), (
        f"{dataset}.json is a bare list and cannot carry `_vintage`; "
        "wrap it in an object as codici_ateco/codici_ruolo are"
    )
    assert "_vintage" in payload, f"{dataset}.json non dichiara `_vintage`"


@pytest.mark.parametrize("dataset", all_datasets())
def test_vintage_fields_are_well_formed(dataset):
    v = vintage(dataset)
    assert v.verifica in VERIFICHE, f"{dataset}: verifica '{v.verifica}' non riconosciuta"
    assert v.fonte and v.fonte != "fonte non dichiarata", f"{dataset}: fonte mancante"
    for campo in (v.aggiornato_al, v.copre_fino_a):
        assert campo is None or isinstance(campo, date)
    assert v.tolleranza_giorni >= 0


@pytest.mark.parametrize("dataset", all_datasets())
def test_declared_coverage_has_not_elapsed(dataset):
    """Mirrors the CI gate: a stated period must still be running.

    A table marked `da_verificare` is a known gap, tracked as a warning by
    `scripts/update-data.py`; it is not this test's business. A table that
    claims a period and has outlived it is a wrong answer waiting to happen.
    """
    v = vintage(dataset)
    if v.verifica == UNVERIFIED:
        pytest.skip("gap noto, sorvegliato da update-data.py come warning")
    assert not v.scaduto(), (
        f"{dataset}: copre fino al {v.copre_fino_a} (tolleranza {v.tolleranza_giorni}gg) "
        "— riconciliare con la fonte"
    )


def test_unverified_table_says_so_instead_of_staying_silent():
    v = vintage("violazioni_patente")
    assert v.verifica == UNVERIFIED
    assert "non verificate" in v.to_line()
    assert "prima dell'uso in un atto" in v.to_line()


def test_footer_renders_one_line_per_table():
    out = footer("tassi_legali", "tegm")
    assert out.startswith("\n\n> **Dati applicati**")
    assert out.count("\n> - ") == 2


def test_sourced_appends_to_a_string_return():
    @sourced("tassi_legali")
    def tool() -> str:
        return "Totale: 1.234,56 EUR"

    out = tool()
    assert out.startswith("Totale: 1.234,56 EUR")
    assert "Dati applicati" in out


def test_sourced_adds_a_key_to_a_dict_return_without_disturbing_it():
    @sourced("tegm")
    def tool() -> dict:
        return {"soglia": 12.5}

    out = tool()
    assert out["soglia"] == 12.5
    assert out["dati_applicati"] == [vintage("tegm").to_line()]


def test_sourced_keeps_the_signature_fastmcp_builds_its_schema_from():
    import inspect

    @sourced("tegm")
    def tool(capitale: float, tasso: float = 1.0) -> dict:
        """Docstring che l'LLM deve continuare a vedere."""
        return {}

    sig = inspect.signature(tool)
    assert list(sig.parameters) == ["capitale", "tasso"]
    assert tool.__doc__.startswith("Docstring")
    assert tool.__sourced_datasets__ == ("tegm",)


def test_a_real_tool_carries_its_table_vintage():
    from src.tools.tassi_interessi import interessi_legali

    out = interessi_legali(
        capitale=1000.0, data_inizio="2024-01-01", data_fine="2024-06-30"
    )
    assert "dati_applicati" in out, "il tool non espone la provenienza della tabella"
    assert any("tassi legali" in r for r in out["dati_applicati"])
