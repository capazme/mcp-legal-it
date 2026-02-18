"""MCP Legal IT — 60+ Italian legal calculation tools."""

from fastmcp import FastMCP

mcp = FastMCP(
    "Legal IT",
    instructions="Strumenti di calcolo legale italiano: rivalutazioni, interessi, scadenze, parcelle, risarcimenti e altro.",
)

# Import all tool modules — each registers its tools via @mcp.tool()
from src.tools import (  # noqa: E402, F401
    rivalutazioni_istat,
    tassi_interessi,
    scadenze_termini,
    atti_giudiziari,
    fatturazione_avvocati,
    parcelle_professionisti,
    risarcimento_danni,
    diritto_penale,
    proprieta_successioni,
    investimenti,
    dichiarazione_redditi,
    varie,
)

if __name__ == "__main__":
    mcp.run(transport="stdio")
