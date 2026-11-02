"""The imposta di registro calculators and the switch to the testo unico (LI-061).

The D.P.R. 131/1986 applies until 31/12/2026; from 1 January 2027 the testo unico
of D.Lgs. 123/2025 applies (art. 205, as amended by art. 4 co. 5 d.l. 200/2025).
Up to that day every calculator that applies the D.P.R. keeps its figures and its
declared grade and adds one fixed notice; from that day it refuses, whatever grade
the caller accepts. The date is the calculation date read through `_clock`, so the
tests move it with `LEGAL_TODAY` on both sides of the boundary.

The tools are called through the registered object (`.fn`), with every wrapper the
server applies, because the guard is one of them.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
from datetime import date

import pytest

from mcp_legal_it.lib import _transizione
from mcp_legal_it.lib._transizione import CAMPO_AVVISO, DPR_131_1986, ERRORE, transitoria

from .mcp_harness import tool_body

AVVISO = (
    "Calcolo secondo il D.P.R. 131/1986, applicabile fino al 31/12/2026. "
    "Dal 1° gennaio 2027 si applica il testo unico di cui al D.Lgs. 123/2025 "
    "(art. 205, come modificato dall'art. 4, comma 5, del d.l. 200/2025): "
    "per atti con effetti da quella data il calcolo va rifatto. "
    "Uno schema di decreto legislativo correttivo dei testi unici, che riguarda anche "
    "l'imposta di registro, è stato approvato in esame preliminare dal Consiglio dei "
    "ministri il 13/10/2026: non ancora in vigore."
)

#: (module, tool, arguments, a key that only a computed answer carries)
TOOLS = [
    ("proprieta_successioni", "imposta_registro_locazioni",
     {"canone_annuo": 10000, "durata_anni": 4, "tipo_contratto": "libero"}, "totale_durata_contratto"),
    ("proprieta_successioni", "imposte_compravendita",
     {"prezzo": 200000, "prima_casa": True}, "imposta_registro"),
    ("proprieta_successioni", "calcolo_usufrutto",
     {"valore_piena_proprieta": 100000, "eta_usufruttuario": 70}, "valore_usufrutto"),
    ("atti_giudiziari", "tassazione_atti",
     {"tipo_atto": "sentenza_condanna", "valore": 50000}, "imposta_registro"),
    ("diritto_societario", "costi_costituzione",
     {"tipo_societa": "srl"}, "voci_costo"),
]

IDS = [t[1] for t in TOOLS]


def _registered(module: str, name: str):
    mod = importlib.import_module(f"mcp_legal_it.tools.{module}")
    tool = getattr(mod, name)
    return getattr(tool, "fn", tool)


def _run(fn, **kwargs):
    result = fn(**kwargs)
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    return result


@pytest.mark.parametrize("module,name,kwargs,computed", TOOLS, ids=IDS)
def test_last_day_of_the_dpr_computes_with_the_notice(monkeypatch, module, name, kwargs, computed):
    monkeypatch.setenv("LEGAL_TODAY", "2026-12-31")
    result = _run(_registered(module, name), **kwargs)
    assert "errore" not in result
    assert computed in result
    assert result[CAMPO_AVVISO] == AVVISO


@pytest.mark.parametrize("module,name,kwargs,computed", TOOLS, ids=IDS)
def test_first_day_of_the_testo_unico_refuses(monkeypatch, module, name, kwargs, computed):
    monkeypatch.setenv("LEGAL_TODAY", "2027-01-01")
    result = _run(_registered(module, name), **kwargs)
    assert result["errore"] == ERRORE
    assert computed not in result
    assert CAMPO_AVVISO not in result
    assert result["data_calcolo"] == "2027-01-01"
    assert result["disciplina"]["applicabile_fino_al"] == "2026-12-31"
    assert result["precisione"]["effettiva"] == "nessuna"
    assert "D.Lgs. 123/2025" in result["messaggio"]


@pytest.mark.parametrize("module,name,kwargs,computed", TOOLS, ids=IDS)
def test_figures_are_the_same_as_without_the_guard(monkeypatch, module, name, kwargs, computed):
    """The guard adds one field and changes no number."""
    monkeypatch.setenv("LEGAL_TODAY", "2026-11-02")
    guarded = _run(_registered(module, name), **kwargs)
    bare = _run(tool_body(_registered(module, name)), **kwargs)
    without_notice = {k: v for k, v in guarded.items() if k != CAMPO_AVVISO}
    for key, value in bare.items():
        assert without_notice[key] == value


def test_acceptance_cannot_buy_the_old_rule(monkeypatch):
    """`accetta_precisione` is about how well a table is known, not which law applies."""
    monkeypatch.setenv("LEGAL_TODAY", "2027-03-15")
    fn = _registered("proprieta_successioni", "imposta_registro_locazioni")
    result = _run(fn, canone_annuo=10000, accetta_precisione="STIMATO")
    assert result["errore"] == ERRORE


def test_the_declared_grade_stays_on_the_refusal(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2027-01-01")
    result = _run(_registered("proprieta_successioni", "imposta_registro_locazioni"), canone_annuo=10000)
    assert result["precisione"]["dichiarata"] == "ESATTO"


def test_an_input_error_carries_no_notice(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2026-11-02")
    fn = _registered("proprieta_successioni", "imposta_registro_locazioni")
    result = _run(fn, canone_annuo=10000, durata_anni=0)
    assert "errore" in result
    assert CAMPO_AVVISO not in result


def test_schema_and_markers_survive_the_wrapper():
    """`accetta_precisione` and the table declaration stay visible to the server and the audit."""
    fn = _registered("proprieta_successioni", "imposta_registro_locazioni")
    assert "accetta_precisione" in inspect.signature(fn).parameters
    assert fn.__sourced_datasets__ == ("tassi_legali",)
    assert fn.__disciplina_transitoria__ is DPR_131_1986


def test_tool_body_reaches_the_arithmetic():
    """Computation tests stay independent of the calendar: they skip the guard."""
    fn = _registered("proprieta_successioni", "imposta_registro_locazioni")
    assert not hasattr(tool_body(fn), "__disciplina_transitoria__")
    assert not hasattr(tool_body(fn), "__sourced_datasets__")


def test_the_valore_catastale_tool_is_not_guarded():
    """Art. 52 D.P.R. 131/1986 is not among those art. 204 D.Lgs. 123/2025 abrogates."""
    fn = _registered("proprieta_successioni", "calcolo_valore_catastale")
    assert not hasattr(fn, "__disciplina_transitoria__")


def test_notice_text_is_built_from_the_dates():
    assert DPR_131_1986.avviso == AVVISO
    assert _transizione._giorno_esteso(date(2027, 1, 1)) == "1° gennaio 2027"
    assert _transizione._giorno_esteso(date(2027, 3, 15)) == "15 marzo 2027"
    bare = _transizione.Disciplina("D.P.R. X", date(2026, 12, 31), "la regola Y")
    assert bare.avviso.endswith("il calcolo va rifatto.")


def test_the_pending_correttivo_is_named_on_the_notice_not_on_the_refusal(monkeypatch):
    """LI-062: named until final, and only on an answer about today's rule."""
    assert "esame preliminare" in DPR_131_1986.avviso
    assert "non ancora in vigore" in DPR_131_1986.avviso
    monkeypatch.setenv("LEGAL_TODAY", "2027-01-01")
    refused = _run(_registered("atti_giudiziari", "tassazione_atti"), tipo_atto="ordinanza", valore=0)
    assert "esame preliminare" not in refused["messaggio"]


def test_string_answers_and_async_tools_are_covered(monkeypatch):
    disciplina = _transizione.Disciplina("D.P.R. X", date(2026, 12, 31), "la regola Y")

    @transitoria(disciplina)
    async def tool_async() -> str:
        """Precisione: INDICATIVO"""
        return "risultato"

    monkeypatch.setenv("LEGAL_TODAY", "2026-06-01")
    assert asyncio.run(tool_async()).endswith(disciplina.avviso)
    monkeypatch.setenv("LEGAL_TODAY", "2027-06-01")
    refused = asyncio.run(tool_async())
    assert refused["errore"] == ERRORE
    assert refused["precisione"]["dichiarata"] == "INDICATIVO"


def test_the_date_is_the_clock_s(monkeypatch):
    """No `date.today()` here: an unpinned run follows the real clock through `_clock`."""
    seen = []
    monkeypatch.setattr(_transizione._clock, "today", lambda: seen.append(1) or date(2026, 1, 1))
    _run(_registered("atti_giudiziari", "tassazione_atti"), tipo_atto="ordinanza", valore=0)
    assert seen
