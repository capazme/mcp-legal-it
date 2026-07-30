"""MCP tools for supplier-ledger privacy screening (analisi mastrino fornitori).

TRIGGER: usare quando l'utente deve analizzare il mastrino fornitori di un cliente
ai fini GDPR (individuare i responsabili ex art. 28 da nominare), verificare una
P.IVA sul VIES, o produrre il report Excel standard dell'analisi fornitori.
"""

from src.lib.vies import check_vat, checksum_partita_iva
from src.server import mcp


QUALIFICAZIONI = {"responsabile", "titolare_autonomo", "fuori_perimetro"}
CONFIDENZE = {"alto", "medio", "basso"}
PROBABILITA = {"alta", "media", "bassa"}
DPA_VALORI = {"si", "no", "da_verificare"}

_CAMPI_OBBLIGATORI = ("denominazione_mastrino", "qualificazione", "motivazione", "confidenza")


def _valida_fornitori(fornitori) -> list[str]:
    """Collect-all validation of canonical supplier records (1-based row indexes)."""
    if not isinstance(fornitori, list):
        return ["'fornitori' deve essere una lista di oggetti"]
    if not fornitori:
        return ["'fornitori' è una lista vuota: nessun fornitore da riportare"]

    errori: list[str] = []
    for i, riga in enumerate(fornitori, start=1):
        if not isinstance(riga, dict):
            errori.append(f"riga {i}: non è un oggetto")
            continue
        for campo in _CAMPI_OBBLIGATORI:
            valore = riga.get(campo)
            if not isinstance(valore, str) or not valore.strip():
                errori.append(f"riga {i}: campo obbligatorio '{campo}' mancante o vuoto")
        qualificazione = riga.get("qualificazione")
        if isinstance(qualificazione, str) and qualificazione and qualificazione not in QUALIFICAZIONI:
            errori.append(
                f"riga {i}: 'qualificazione' non valida ({qualificazione!r}); ammessi: {sorted(QUALIFICAZIONI)}"
            )
        confidenza = riga.get("confidenza")
        if isinstance(confidenza, str) and confidenza and confidenza not in CONFIDENZE:
            errori.append(f"riga {i}: 'confidenza' non valida ({confidenza!r}); ammessi: {sorted(CONFIDENZE)}")

        probabilita = riga.get("probabilita_responsabile")
        dpa = riga.get("dpa_proprio")
        if qualificazione == "responsabile":
            if probabilita not in PROBABILITA:
                errori.append(
                    f"riga {i}: 'probabilita_responsabile' obbligatoria per i responsabili; ammessi: {sorted(PROBABILITA)}"
                )
            if dpa not in DPA_VALORI:
                errori.append(
                    f"riga {i}: 'dpa_proprio' obbligatorio per i responsabili; ammessi: {sorted(DPA_VALORI)}"
                )
        elif qualificazione in QUALIFICAZIONI:
            if probabilita is not None:
                errori.append(
                    f"riga {i}: 'probabilita_responsabile' presente ma la qualificazione non è 'responsabile'"
                )
            if dpa is not None:
                errori.append(f"riga {i}: 'dpa_proprio' presente ma la qualificazione non è 'responsabile'")

        fonti = riga.get("fonti", [])
        if fonti is not None and not isinstance(fonti, list):
            errori.append(f"riga {i}: 'fonti' deve essere una lista di URL")
    return errori


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
