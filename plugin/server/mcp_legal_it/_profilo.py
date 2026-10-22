"""LEGAL_PROFILE, read once when the server is built: an unknown name refuses to start (#76).

A reduced profile is asked for to get FEWER tools (often: no tool that goes online). Falling
back to `full` on a typo did the opposite in silence, so the server fails closed instead.
This module imports nothing from the server, so the console entry point can catch the error
and print it without a traceback.
"""
from __future__ import annotations

import os
from collections.abc import Iterable


class ProfiloSconosciuto(ValueError):
    """LEGAL_PROFILE names no profile."""


def profilo_richiesto(profili: Iterable[str]) -> str:
    """The profile LEGAL_PROFILE asks for ("full" when unset or blank); refuses an unknown one."""
    nome = os.environ.get("LEGAL_PROFILE", "full").strip() or "full"
    validi = sorted(profili)
    if nome != "full" and nome not in validi:
        raise ProfiloSconosciuto(
            f"LEGAL_PROFILE={nome!r} non è un profilo. Valori ammessi: full, {', '.join(validi)}. "
            "Il server non parte: con un profilo sconosciuto esporrebbe tutti gli strumenti, "
            "compresi quelli che vanno in rete."
        )
    return nome
