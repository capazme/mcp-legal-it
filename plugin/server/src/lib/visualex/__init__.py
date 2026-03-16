"""VisualEx — simplified legal scraping library for MCP Legal IT."""

from .models import Norma, NormaVisitata
from .map import resolve_atto, normalize_act_type, find_brocardi_url

__all__ = ["Norma", "NormaVisitata", "resolve_atto", "normalize_act_type", "find_brocardi_url"]
