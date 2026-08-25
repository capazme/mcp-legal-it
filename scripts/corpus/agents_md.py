"""Generate the openai bundle's AGENTS.md from a hand-written header/footer
plus the REGOLE/OUTPUT/WORKFLOW block extracted verbatim from
plugin/server/src/server.py's FastMCP `instructions` string.

Single source of truth: the REGOLE/OUTPUT/WORKFLOW text is never copied into
this module — it is read out of server.py at build time so the two can never
drift. Everything else (scope header, Legal Grounding Protocol summary, tool
naming footer) is hand-written here, in Italian, matching the rest of the
corpus.
"""
from __future__ import annotations

from pathlib import Path

_SERVER_PY_REL = Path("plugin") / "server" / "src" / "server.py"

_START_MARKER = "REGOLE:"
_WORKFLOW_MARKER = "WORKFLOW:"
_END_MARKER = '"""'

_HEADER = """\
# AGENTS.md — Legal IT

Strumenti di diritto italiano esposti dal server MCP `legal_it`: calcoli \
(interessi, rivalutazione, parcelle, danni, scadenze), consultazione \
normativa (Normattiva, EUR-Lex, Brocardi), giurisprudenza (Cassazione, \
Corte Costituzionale, CeRDEF, TAR/CdS, CGUE), CONSOB, Gazzetta Ufficiale, \
recepimento UE→IT, compliance GDPR/privacy e redazione atti. Le skill in \
`.agents/skills/` guidano l'agente su quando e come usare questi tool; il \
server MCP fornisce gli strumenti esecutivi.

## Legal Grounding Protocol

- **Norme**: usare sempre `cite_law()` prima di citare un articolo — mai a \
memoria.
- **Sentenze con numero noto**: `leggi_sentenza(numero, anno)` diretto — mai \
web search.
- **Ricerca per tema**: prima un tool `cerca_*` (`cerca_giurisprudenza`, \
`cerca_giurisprudenza_tributaria`, `cerca_giurisprudenza_amministrativa`, \
`cerca_giurisprudenza_cgue`, ...) per trovare la fonte, poi il `leggi_*`/\
`fetch_*` corrispondente per leggerla per intero.
- **Calcoli**: i tool numerici applicano le norme internamente e non \
richiedono `cite_law()`.

---
"""

_FOOTER = """
---

## Nomi dei tool

A seconda della modalità del client MCP, i tool di questo server compaiono \
come `legal_it__<nome>` oppure `mcp__legal_it__<nome>`. Nei testi delle \
skill sono citati col nome bare (es. `cite_law`, `leggi_sentenza`): \
antepponi tu il prefisso corretto per la tua configurazione quando li \
invochi.
"""


def _extract_regole_block(root: Path) -> str:
    server_path = root / _SERVER_PY_REL
    text = server_path.read_text(encoding="utf-8")

    if text.count(_START_MARKER) != 1:
        raise SystemExit(
            f"{server_path}: expected exactly one {_START_MARKER!r} marker, "
            f"found {text.count(_START_MARKER)}"
        )
    if text.count(_WORKFLOW_MARKER) != 1:
        raise SystemExit(
            f"{server_path}: expected exactly one {_WORKFLOW_MARKER!r} marker, "
            f"found {text.count(_WORKFLOW_MARKER)}"
        )

    start = text.find(_START_MARKER)
    end = text.find(_END_MARKER, start)
    if end == -1:
        raise SystemExit(
            f"{server_path}: no closing {_END_MARKER!r} found after {_START_MARKER!r}"
        )

    block = text[start:end]
    if _WORKFLOW_MARKER not in block:
        raise SystemExit(
            f"{server_path}: {_WORKFLOW_MARKER!r} not found between "
            f"{_START_MARKER!r} and the closing {_END_MARKER!r}"
        )
    return block.rstrip("\n")


def generate(root: Path) -> str:
    """Assemble AGENTS.md: hand-written header + REGOLE/OUTPUT/WORKFLOW
    (extracted verbatim from server.py) + hand-written footer."""
    regole_block = _extract_regole_block(root)
    return _HEADER + regole_block + "\n" + _FOOTER
