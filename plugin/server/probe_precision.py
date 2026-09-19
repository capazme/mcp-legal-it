"""A wire probe for the precision policy, not a tool of the server.

Every shipped tool now reads a verified table or declares INDICATIVO, so no
real surface refuses any more -- which is the data work succeeding, not the
policy rotting. The refusal and the acceptance that lowers it are exercised
here on a probe wrapped by the same `sourced` the real tools use, registered on
its own FastMCP app and launched by `call_tools` with the repository checkout
as its working directory: the probe imports the server's libraries exactly the
way `server.py` does, and the middleware, the ledger and the refusal recording
run on its answers as they would on a shipped one.

The test files (`test_precision_policy`, `test_refusal_ledger`) launch this
module through the harness with it as the script argument, so nothing in the
server ever imports it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import src.server  # noqa: E402,F401  (installs the ledger and the middleware)

from fastmcp import FastMCP  # noqa: E402

from src.lib import _data  # noqa: E402
from src.lib._ledger import TableLedgerMiddleware  # noqa: E402

mcp = FastMCP("precision-probe")
mcp.add_middleware(
    TableLedgerMiddleware(
        tool_tables={"sonda_rifiuto": ("codici_ateco",)},
        tool_alternatives={"sonda_rifiuto": "codice_ateco"},
    )
)


@mcp.tool()
@_data.sourced("codici_ateco", alternativa="codice_ateco")
def sonda_rifiuto(keyword: str, codice_ateco: str | None = None) -> dict:
    """Cerca un codice ATECO per parola chiave.

    Precisione: ESATTO (tabella codici ATECO).

    Args:
        keyword: parola chiave da cercare nella descrizione dell'attivita
        codice_ateco: codice noto dal chiamante, al posto della tabella
    """
    if codice_ateco is not None:
        return {
            "codice": codice_ateco,
            "descrizione": "codice fornito dal chiamante",
            "dettaglio": {"ateco_dal_chiamante": True},
        }
    for voce in _data.load("codici_ateco")["voci"]:
        if keyword.lower() in voce["descrizione"].lower():
            return {"codice": voce["codice"], "descrizione": voce["descrizione"]}
    return {"codice": None, "descrizione": "nessuna corrispondenza", "voci": 0}


if __name__ == "__main__":
    mcp.run(transport="stdio")
