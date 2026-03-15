"""Regression tests for prompt keyword presence.

Ensures that prompts referencing giurisprudenza include the esplora/filtra
strategy terms introduced in the Italgiure alignment.
"""

import pytest

from src.prompts import (
    analisi_giurisprudenziale,
    ricerca_normativa,
    analisi_delibere_consob,
    parere_legale,
)


def _get_prompt_text(fn, **kwargs):
    """Call a prompt function and return the generated text."""
    inner = getattr(fn, "fn", fn)
    return inner(**kwargs)


@pytest.mark.parametrize(
    "prompt_fn,kwargs,expected_terms",
    [
        pytest.param(
            analisi_giurisprudenziale,
            {"tema": "test", "archivio": "tutti"},
            ["esplora", "modalita", "filtri"],
            id="analisi_giurisprudenziale",
        ),
        pytest.param(
            ricerca_normativa,
            {"tema": "test", "area_diritto": "civile"},
            ["esplora"],
            id="ricerca_normativa",
        ),
        pytest.param(
            analisi_delibere_consob,
            {"tema": "test"},
            ["esplora"],
            id="analisi_delibere_consob",
        ),
        pytest.param(
            parere_legale,
            {"area_diritto": "civile", "quesito": "test"},
            ["cerca_giurisprudenza"],
            id="parere_legale",
        ),
    ],
)
def test_prompt_contains_keywords(prompt_fn, kwargs, expected_terms):
    text = _get_prompt_text(prompt_fn, **kwargs)
    for term in expected_terms:
        assert term in text, (
            f"Prompt '{prompt_fn.__name__}' missing keyword '{term}'"
        )
