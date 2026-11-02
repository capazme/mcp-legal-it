"""MCP tools on the validity in time of Italian norms (tag ``vigenza``).

TRIGGER: usare quando l'utente chiede quando un articolo è cambiato, quali versioni
ha avuto, quale atto lo ha modificato o da quando è in vigore il testo attuale.

A thin wrapper (ADR-001) over ``api.modifiche_articolo``: the reading, the dates and
the grade are the library's; this module only renders them. Vigenza is not
applicability, and the answer says so.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from mcp_legal_it import api
from mcp_legal_it.lib import _clock
from mcp_legal_it.server import mcp

_NOTA_VIGENZA = ("Vigenza non è applicabilità: un testo in vigore può non applicarsi a un fatto anteriore "
                 "(regime transitorio).")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _gg(iso: str | None) -> str:
    """An ISO day as GG/MM/AAAA; anything else unchanged."""
    return _ISO.sub(lambda m: f"{m[3]}/{m[2]}/{m[1]}", iso) if iso else ""


def _cella(testo: str) -> str:
    """Text safe inside a markdown table cell."""
    return " ".join(testo.split()).replace("|", "\\|")


def _atto(m: api.Modifica) -> str:
    """The amending act as Normattiva words it, without the row's leading article."""
    d = re.sub(r"^(?:Il|La|Lo|L')\s*", "", m.atto.descrizione.strip())
    return d or " ".join(p for p in (m.atto.tipo_atto, _gg(m.atto.data), m.atto.numero_atto) if p) or "atto non letto"


def _voce(m: api.Modifica) -> str:
    """One amendment: «art. 9, comma 1, lettera a): inserimento comma 1-bis»."""
    cosa = f"{m.tipo} {m.parti}" if m.parti else m.tipo
    voce = f"{m.disposizione}: {cosa}" if m.disposizione else cosa
    return voce + (" (INDICATIVO)" if m.precisione != "ESATTO" else "")


def _modifiche_della_versione(modifiche: list[api.Modifica]) -> str:
    """A version's amendments, grouped by amending act in the order read."""
    gruppi: dict[str, list[str]] = {}
    for m in modifiche:
        gruppi.setdefault(_atto(m), []).append(_voce(m))
    return " · ".join(f"{atto}: {'; '.join(voci)}" for atto, voci in gruppi.items())


def _finestra(v: api.VersioneArticolo, oggi: str) -> str:
    if not v.valid_from:
        return "finestra non letta"
    if v.valid_to:
        return f"{_gg(v.valid_from)} – {_gg(v.valid_to)}"
    futura = " (non ancora in vigore)" if v.valid_from > oggi else ""
    return f"dal {_gg(v.valid_from)}{futura}"


def _intestazione(r: api.ModificheArticolo) -> str:
    nd = r.norma_data
    articolo = f"Art. {nd.numero_articolo} {_gg(nd.descrizione)}" if nd else "Articolo"
    n = len(r.versioni)
    storia = "storia completa" if r.completa else "storia incompleta"
    return f"**{articolo}** — {n} {'versione' if n == 1 else 'versioni'}, {storia} ({r.precisione})"


def _testo(r: api.ModificheArticolo, dal: str | None, al: str | None, oggi: str) -> str:
    per_versione: dict[int | None, list[api.Modifica]] = {}  # the API always sets versione
    for m in r.modifiche:
        per_versione.setdefault(m.versione, []).append(m)

    def nel_periodo(v: api.VersioneArticolo) -> bool:
        if v.version_number in per_versione:
            return True
        if not v.valid_from:
            return False  # unread (ceiling or failure): the avvisi name it
        return (dal is None or v.valid_from >= dal) and (al is None or v.valid_from <= al)

    righe = [f"| {v.version_number} | {_finestra(v, oggi)} | "
             f"{_cella(_modifiche_della_versione(per_versione.get(v.version_number, []))) or '—'} |"
             for v in r.versioni if nel_periodo(v)]

    out = [_intestazione(r)]
    if dal or al:
        periodo = " ".join(p for p in (f"dal {_gg(dal)}" if dal else "", f"al {_gg(al)}" if al else "") if p)
        out.append(f"Periodo (entrata in vigore): {periodo}.")
    out += [f"- ⚠ {_gg(a)}" for a in r.avvisi]
    out.append("")
    if righe:
        out += ["| Versione | In vigore | Modifiche che l'hanno prodotta |", "|---|---|---|", *righe]
    else:
        out.append("Nessuna versione nel periodo indicato.")
    out += ["", f"*Fonte: Normattiva, tabelle degli aggiornamenti per versione — {r.url}. {_NOTA_VIGENZA}*"]
    return "\n".join(out)


def _errore(r: api.ModificheArticolo) -> str:
    # The resolver points a library caller to riferimento_da_parametri(): no tool equivalent here.
    errore = (r.errore or r.esito).replace(" o usa riferimento_da_parametri()", "")
    return f"**Errore** ({r.esito}): {errore}"


async def _storia_norma_impl(riferimento: str, dal: str | None = None, al: str | None = None,
                             max_versioni: int = 20, formato: str = "testo") -> str:
    """Implementation of storia_norma (testable without the MCP wrapper)."""
    if formato not in ("testo", "json"):
        return f"**Errore**: formato '{formato}' non valido: attesi 'testo' o 'json'"
    try:
        r = await api.modifiche_articolo(riferimento, dal=dal, al=al, max_versioni=max_versioni)
    except ValueError as e:  # max_versioni below 1
        if formato == "json":
            rifiuto = api.ModificheArticolo(esito="riferimento_non_valido", errore=str(e))
            return json.dumps(api.come_dict(rifiuto), ensure_ascii=False)
        return f"**Errore**: {e}"
    if formato == "json":
        return json.dumps(api.come_dict(r), ensure_ascii=False)
    if r.esito != "trovato":
        return _errore(r)
    return _testo(r, dal and dal.strip(), al and al.strip(), _clock.today().isoformat())


@mcp.tool(tags={"normativa", "vigenza"}, output_schema=None)
async def storia_norma(
    riferimento: str,
    dal: str | None = None,
    al: str | None = None,
    max_versioni: int = 20,
    formato: Literal["testo", "json"] = "testo",
) -> str:
    """Storia di un articolo di legge italiano: versioni, date di entrata in vigore e atti che le hanno prodotte (Normattiva).

    Per «quando è cambiato», «chi l'ha modificato»; il testo di una versione: cite_law.
    Vigenza non è applicabilità: un testo in vigore può non applicarsi a un fatto anteriore.
    Un atto non riconosciuto dà errore, mai un atto indovinato.

    Precisione: ESATTO con la storia completa, altrimenti INDICATIVO (con gli avvisi).

    Args:
        riferimento: come per cite_law, es. "art. 2-ter d.lgs. 196/2003"
        dal: "AAAA-MM-GG", incluso, sull'entrata in vigore
        al: "AAAA-MM-GG", incluso
        max_versioni: versioni lette al massimo, dalle più recenti
        formato: "testo" (tabella) o "json"
    """
    return await _storia_norma_impl(riferimento, dal, al, max_versioni, formato)
