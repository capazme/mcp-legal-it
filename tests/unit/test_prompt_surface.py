"""The MCP prompt surface is frozen: 23 names with exact signatures.

Passes against the hand-written prompts.py AND against the generated one —
this is the no-regression contract for the corpus consolidation.
"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from src import prompts  # noqa: E402

E = inspect.Parameter.empty
EXPECTED = {
    "analisi_articolo": [("riferimento_norma", str, E)],
    "analisi_costituzionale": [("tema", str, E), ("tipo", str, "")],
    "analisi_delibere_consob": [("tema", str, E), ("tipologia", str, ""), ("argomento", str, "")],
    "analisi_giurisprudenza_amministrativa": [("tema", str, E), ("sede", str, "")],
    "analisi_giurisprudenza_europea": [("tema", str, E), ("corte", str, "tutte")],
    "analisi_giurisprudenziale": [("tema", str, E), ("archivio", str, "tutti")],
    "analisi_sinistro": [("tipo_sinistro", str, E), ("percentuale_invalidita", float, E), ("eta_vittima", int, E)],
    "analisi_tributaria": [("tema", str, E), ("ente", str, "")],
    "attuazione_direttiva": [("direttiva", str, E)],
    "calcolo_parcella": [("tipo_attivita", str, E), ("valore_causa", float, E)],
    "causa_civile": [("valore_causa", float, E), ("rito", str, E), ("grado", str, E)],
    "compliance_privacy": [("titolare", str, E), ("tipo_trattamento", str, E), ("contesto", str, E)],
    "confronto_norme": [("norma_1", str, E), ("norma_2", str, E), ("contesto", str, "")],
    "mappatura_normativa": [("settore", str, E), ("attivita_specifica", str, "")],
    "novita_consob": [("tipologia", str, ""), ("argomento", str, "")],
    "orientamento_giurisprudenziale": [("riferimento", str, E), ("archivio", str, "tutti")],
    "parere_legale": [("area_diritto", str, E), ("quesito", str, E)],
    "pianificazione_successione": [("valore_asse", float, E), ("grado_parentela", str, E), ("numero_eredi", int, E)],
    "quantificazione_danni": [("tipo_danno", str, E), ("importo_o_percentuale", float, E), ("eta_vittima", int, E)],
    "recupero_credito": [("importo", float, E), ("tipo_credito", str, E), ("data_scadenza", str, E)],
    "ricerca_gazzetta": [("tema", str, E), ("serie", str, "serie_generale")],
    "ricerca_normativa": [("tema", str, E), ("area_diritto", str, E)],
    "verifica_prescrizione": [("tipo", str, E), ("descrizione_fatto", str, E), ("data_fatto", str, E)],
}


def _underlying(obj):
    return getattr(obj, "fn", obj)  # FastMCP may wrap the function


def test_all_23_prompts_exist_with_frozen_signatures():
    for name, expected in EXPECTED.items():
        fn = _underlying(getattr(prompts, name))
        params = list(inspect.signature(fn).parameters.values())
        got = [(p.name, p.annotation, p.default) for p in params]
        assert got == [(n, a, d) for n, a, d in expected], f"{name}: {got}"


def test_rendered_prompt_carries_data_and_doctrine():
    fn = _underlying(prompts.analisi_sinistro)
    text = fn("stradale", 25.0, 40)
    assert "stradale" in text  # arg value flows into the render (old and generated formats differ)
    assert "26972/2008" in text  # San Martino — present in both old prompt and skill body
