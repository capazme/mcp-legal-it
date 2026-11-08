"""The codice deontologico forense, read from the Consiglio nazionale forense's site."""

from .client import (
    AVVISO_FONTE,
    PAGINA_CODICE,
    CnfNonDisponibile,
    Edizione,
    edizione,
    fetch_articolo,
)
from .parser import Articolo, Codice, FormatoNonRiconosciuto, analizza, chiave_articolo

__all__ = [
    "AVVISO_FONTE",
    "PAGINA_CODICE",
    "Articolo",
    "CnfNonDisponibile",
    "Codice",
    "Edizione",
    "FormatoNonRiconosciuto",
    "analizza",
    "chiave_articolo",
    "edizione",
    "fetch_articolo",
]
