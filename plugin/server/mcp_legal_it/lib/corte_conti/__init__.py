"""Corte dei conti: deliberazioni of the control sections (banca dati, public service)."""

from .client import (
    MAX_DOCUMENTI,
    CorteContiAccessoNegato,
    CorteContiErrore,
    CorteContiNonRaggiungibile,
    CorteContiNonTrovato,
    CorteContiPaginaInattesa,
    Deliberazione,
    fetch_deliberazione,
    format_deliberazione,
    format_result,
    scrub_body,
    search_deliberazioni,
)

__all__ = [
    "MAX_DOCUMENTI",
    "CorteContiAccessoNegato",
    "CorteContiErrore",
    "CorteContiNonRaggiungibile",
    "CorteContiNonTrovato",
    "CorteContiPaginaInattesa",
    "Deliberazione",
    "fetch_deliberazione",
    "format_deliberazione",
    "format_result",
    "scrub_body",
    "search_deliberazioni",
]
