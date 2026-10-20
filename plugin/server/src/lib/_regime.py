"""The normative regime a tool implements, and how a superseded one is flagged.

Some tools deliberately compute under a regime that no longer governs new cases:
the memorie ex art. 183 co. 6 c.p.c. in the text before the Riforma Cartabia
(still right for a case enrolled before 28/02/2023), the equo indennizzo of DPR
834/1981 (abolished for events after 06/12/2011). They are not stale tables --
the numbers are exactly what that regime says -- and they are not wrong: they
are *residual*, useful only in the edge cases the old rule still governs. What
goes wrong is a model picking one of them for a case the current rule governs,
because nothing in the answer said which rule it applied.

The flag lives in the one place the calling model reads before choosing, the
docstring, on a line shaped like the `Precisione:` line `_precision.py` parses::

    Regime: PREVIGENTE — cause iscritte a ruolo prima del 28/02/2023;
    tool vigenti: termini_memorie_repliche, termini_processuali_civili

and it is enforced in three places so that it cannot be declared and forgotten:

* the tool carries the tag ``previgente`` in its ``@mcp.tool(tags=...)``, so a
  host can filter on it and ``LEGAL_PREVIGENTE=off`` can hide the whole group;
* the tool is wrapped by ``@previgente``, so every answer -- dict or string --
  carries a ``regime_normativo`` block naming the regime, the cases it still
  governs and the tool to use for a current case;
* the audit (``scripts/audit_tool_annotations.py``) fails the suite when the
  three disagree, renders the group into ``src/tool_annotations.py`` and the
  middleware stamps ``mcp-legal-it/regime`` in ``_meta`` on ``tools/list`` and
  on every result, so a client that never reads a body still sees it.

A tool with no ``Regime:`` line is current (``VIGENTE``): the default is the
common case, and the flag marks only the exception.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from functools import wraps

#: The tool computes under the rule that governs new cases today.
VIGENTE = "VIGENTE"
#: The tool computes under a rule that has been replaced, and says for which
#: residual cases it still applies.
PREVIGENTE = "PREVIGENTE"

STATI = (VIGENTE, PREVIGENTE)

#: The tag a superseded tool carries in ``@mcp.tool(tags=...)``.
TAG = "previgente"
#: Key under which a call, and a ``tools/list`` entry, declare the regime in ``_meta``.
META_KEY = "mcp-legal-it/regime"
#: The field a superseded tool's answer carries in its body.
CAMPO = "regime_normativo"
#: The environment switch that hides the superseded tools altogether.
ENV_SWITCH = "LEGAL_PREVIGENTE"

#: The line a tool's docstring carries, e.g.
#: ``Regime: PREVIGENTE — cause iscritte a ruolo prima del 28/02/2023; tool vigenti: x, y``.
#: The declaration may continue on the indented lines that follow, up to a blank
#: line or the next ``Campo:`` field (``Vigenza:``, ``Precisione:``, ``Args:``).
_RIGA = re.compile(r"^[ \t]*Regime:[ \t]*([A-Za-zÀ-ÿ]+)[ \t]*(.*)$", re.MULTILINE)
#: A line that opens another docstring field, which ends the declaration.
_CAMPO = re.compile(r"^[ \t]*[A-ZÀ-Ý][A-Za-zÀ-ÿ ]*:")
#: The successors named after ``tool vigente:``/``tool vigenti:`` in the declaration.
_VIGENTI = re.compile(r"tool vigent[ei]\s*:\s*([A-Za-z0-9_,\s]+)", re.IGNORECASE)
#: The separators a docstring uses after the state word (leading) and before the
#: next field (trailing); a closing parenthesis stays, it closes an aside in the text.
_SEPARATORI_INIZIO = " \t—–-:(,;."
_SEPARATORI_FINE = " \t—–-:,;."


@dataclass(frozen=True)
class Dichiarato:
    """What a tool's docstring says about the rule it applies."""

    stato: str
    #: The cases the superseded rule still governs, in the tool's own words.
    ambito: str = ""
    #: The tools that compute the same thing under the current rule.
    tool_vigenti: tuple[str, ...] = ()
    riga: str = ""

    @property
    def previgente(self) -> bool:
        return self.stato == PREVIGENTE

    def to_dict(self) -> dict:
        out: dict = {"stato": self.stato.lower()}
        if self.ambito:
            out["applicabile_a"] = self.ambito
        if self.tool_vigenti:
            out["tool_vigenti"] = list(self.tool_vigenti)
        if self.previgente:
            out["avvertenza"] = (
                "Regime normativo superato: il risultato vale solo per i casi residuali "
                "indicati in `applicabile_a`. Per un caso soggetto alla disciplina vigente "
                "usare i tool in `tool_vigenti`."
            )
        return out


def parse(doc: str | None) -> Dichiarato | None:
    """The regime a docstring declares, or None when it declares none."""
    text = doc or ""
    found = _RIGA.search(text)
    if found is None:
        return None
    stato = found.group(1).upper()
    parti = [found.group(2).strip()]
    for line in text[found.end():].split("\n")[1:]:
        if not line.strip() or _CAMPO.match(line):
            break
        parti.append(line.strip())
    resto = " ".join(p for p in parti if p)
    vigenti: tuple[str, ...] = ()
    match = _VIGENTI.search(resto)
    if match:
        vigenti = tuple(n.strip() for n in match.group(1).split(",") if n.strip())
        resto = (resto[: match.start()] + resto[match.end():]).strip()
    ambito = resto.lstrip(_SEPARATORI_INIZIO).rstrip(_SEPARATORI_FINE)
    return Dichiarato(stato=stato, ambito=ambito, tool_vigenti=vigenti, riga=found.group(0).strip())


def declared(fn: object) -> Dichiarato | None:
    """The regime a tool declares in its docstring, or None when it declares none."""
    return parse(getattr(fn, "__doc__", None) or "")


def _blocco_markdown(info: Dichiarato) -> str:
    righe = [f"> **Regime normativo {info.stato.lower()}**"]
    if info.ambito:
        righe.append(f"> - applicabile a: {info.ambito}")
    if info.tool_vigenti:
        righe.append("> - tool vigenti: " + ", ".join(f"`{n}`" for n in info.tool_vigenti))
    if info.previgente:
        righe.append(
            "> - il risultato vale solo per i casi residuali indicati; per un caso soggetto "
            "alla disciplina vigente usare i tool vigenti"
        )
    return "\n\n" + "\n".join(righe)


def attach(result: object, info: Dichiarato) -> object:
    """Carry the regime alongside whatever shape a tool returns."""
    if isinstance(result, dict):
        return {**result, CAMPO: info.to_dict()}
    if isinstance(result, str):
        return result + _blocco_markdown(info)
    return result  # a bare scalar has nowhere to put it; left untouched


def previgente(fn):
    """Mark a tool as computing under a superseded rule.

    Applied under ``@mcp.tool(...)`` (and outside ``@sourced``, when both are
    present) so FastMCP registers the wrapper; ``wraps`` keeps the signature the
    schema is built from, including the ``accetta_precisione`` parameter that
    ``@sourced`` adds. The regime itself is read from the docstring, which has to
    declare ``Regime: PREVIGENTE``: a decorator on a tool that declares nothing
    is refused at import, so the flag cannot be half-applied.

        @mcp.tool(tags={"scadenze", "previgente"})
        @previgente
        @sourced("festivita")
        def termini_183_190_cpc(...):
            \"\"\"...
            Regime: PREVIGENTE — cause iscritte a ruolo prima del 28/02/2023;
            tool vigenti: termini_memorie_repliche
            \"\"\"
    """
    info = declared(fn)
    if info is None or not info.previgente:
        raise ValueError(
            f"{getattr(fn, '__name__', fn)!s}: @previgente requires a docstring line "
            f"`Regime: {PREVIGENTE} — <casi residuali>; tool vigenti: <nomi>`"
        )

    if inspect.iscoroutinefunction(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            return attach(await fn(*args, **kwargs), info)
    else:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return attach(fn(*args, **kwargs), info)

    # `wraps` copies `__dict__`, so `__signature__`, `__sourced_datasets__` and the
    # other markers `@sourced` set travel with the wrapper; the annotations it
    # extended are copied too. Nothing here changes the schema.
    wrapper.__regime_dichiarato__ = info
    return wrapper


def hidden_by_environment(value: str | None) -> bool:
    """Whether ``LEGAL_PREVIGENTE`` asks the server to hide the superseded tools.

    Default is to keep them registered and flagged: they are right for the
    residual cases, and a flagged tool is safer than a missing one. ``off``
    (or ``0``, ``false``, ``no``) hides the whole group for hosts that would
    rather not expose it at all.
    """
    return (value or "").strip().lower() in {"off", "0", "false", "no"}
