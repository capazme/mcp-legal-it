"""MCP tools for supplier-ledger privacy screening (analisi mastrino fornitori).

TRIGGER: usare quando l'utente deve analizzare il mastrino fornitori di un cliente
ai fini GDPR (individuare i responsabili ex art. 28 da nominare), verificare una
P.IVA sul VIES, o produrre il report Excel standard dell'analisi fornitori.
"""

from src.lib.vies import check_vat, checksum_partita_iva
from src.server import mcp


@mcp.tool(tags={"privacy", "utility"})
async def verifica_partita_iva_vies(partita_iva: str, codice_paese: str = "IT") -> dict:
    """Verifica una partita IVA sul VIES (servizio UE gratuito): validità e, se disponibili, denominazione e indirizzo registrati.

    Per le P.IVA italiane esegue prima il checksum locale: se fallisce, il VIES non
    viene interrogato. Usare per agganciare con certezza l'identità di un fornitore
    (es. durante l'analisi del mastrino fornitori). `disponibile: false` significa
    VIES/stato membro momentaneamente non raggiungibile: procedere con la sola
    ricerca web e annotarlo.

    Vigenza: Regolamento (UE) 904/2010 (cooperazione amministrativa IVA); DPR 633/1972 art. 35 per il checksum.
    Precisione: ESATTO per validità; denominazione/indirizzo dipendono dai dati forniti dallo stato membro.

    Args:
        partita_iva: Numero IVA senza prefisso paese (per l'Italia: 11 cifre)
        codice_paese: Codice ISO dello stato membro (default "IT")
    """
    piva = partita_iva.strip().replace(" ", "")
    paese = codice_paese.strip().upper() or "IT"
    checksum: bool | None = checksum_partita_iva(piva) if paese == "IT" else None

    if checksum is False:
        return {
            "partita_iva": piva,
            "codice_paese": paese,
            "checksum_valido": False,
            "disponibile": None,
            "valido": False,
            "denominazione": None,
            "indirizzo": None,
            "errore": "checksum non valido — VIES non interrogato",
        }

    esito = await check_vat(piva, paese)
    return {
        "partita_iva": piva,
        "codice_paese": paese,
        "checksum_valido": checksum,
        **esito,
    }
