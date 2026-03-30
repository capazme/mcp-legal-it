"""Strumenti di procedura civile: competenza del giudice (artt. 7-17 c.p.c.), verifica mediazione obbligatoria (art. 5 D.Lgs. 28/2010), ammissione al gratuito patrocinio (DPR 115/2002)."""

import json
from pathlib import Path

from src.server import mcp

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_mediazione() -> dict:
    with open(_DATA_DIR / "mediazione_obbligatoria.json", encoding="utf-8") as f:
        return json.load(f)


@mcp.tool(tags={"giudiziario"})
def competenza_giudice(
    valore_causa: float,
    materia: str = "civile",
) -> dict:
    """Determina il giudice competente per valore e materia (artt. 7-17 c.p.c.).

    Individua la competenza tra Giudice di Pace e Tribunale in base al valore della
    causa e alla materia. Le materie riservate al Tribunale sono assegnate
    indipendentemente dal valore (art. 9 c.p.c.).
    Vigenza: Artt. 7-17 c.p.c. — soglie aggiornate post-Cartabia (D.Lgs. 149/2022).
    Precisione: INDICATIVO per materie di confine; verificare con giurisprudenza di merito.
    Chaining: → verifica_mediazione_obbligatoria() per verificare se serve il tentativo di mediazione

    Args:
        valore_causa: Valore della causa in euro (es. 3000.0). Deve essere >= 0.
        materia: Materia della controversia. Valori: 'civile' (default), 'circolazione_stradale',
                 'mobili', 'locazione', 'condominio', 'lavoro', 'famiglia', 'fallimento', 'crisi_impresa'
    """
    if valore_causa < 0:
        raise ValueError("valore_causa non può essere negativo")

    materia_norm = materia.lower().strip().replace(" ", "_")

    # Materie riservate al Tribunale ex art. 9 c.p.c. (valore irrilevante)
    _riservate_tribunale = {
        "locazione": ("Tribunale", "Art. 9 c.p.c. — materia riservata al Tribunale", "Controversie di locazione indipendentemente dal valore"),
        "condominio": ("Tribunale", "Art. 9 c.p.c. — materia riservata al Tribunale", "Controversie condominiali indipendentemente dal valore"),
        "lavoro": ("Tribunale — Sezione Lavoro", "Art. 409 c.p.c.", "Controversie di lavoro subordinato, para-subordinato e previdenziali"),
        "famiglia": ("Tribunale", "Art. 9 c.p.c. — artt. 706 ss. c.p.c.", "Stato e capacità delle persone, separazione, divorzio, filiazione"),
        "fallimento": ("Tribunale — Sezione Specializzata Imprese", "Art. 9 c.p.c. — D.Lgs. 14/2019 (CCII)", "Procedure concorsuali e crisi d'impresa"),
        "crisi_impresa": ("Tribunale — Sezione Specializzata Imprese", "Art. 9 c.p.c. — D.Lgs. 14/2019 (CCII)", "Procedure concorsuali e crisi d'impresa"),
    }

    if materia_norm in _riservate_tribunale:
        giudice, articolo, note = _riservate_tribunale[materia_norm]
        return {
            "giudice_competente": giudice,
            "articolo": articolo,
            "valore_causa": valore_causa,
            "materia": materia,
            "materia_riservata": True,
            "note": note,
            "soglia_gdp_euro": None,
        }

    # Materia circolazione stradale: GdP ≤ 20.000 (art. 7 co. 2 c.p.c.)
    if materia_norm == "circolazione_stradale":
        soglia = 20_000.0
        if valore_causa <= soglia:
            return {
                "giudice_competente": "Giudice di Pace",
                "articolo": "Art. 7 co. 2 c.p.c.",
                "valore_causa": valore_causa,
                "materia": materia,
                "materia_riservata": False,
                "note": f"Risarcimento da circolazione veicoli ≤ €{soglia:,.2f}: competenza GdP",
                "soglia_gdp_euro": soglia,
            }
        else:
            return {
                "giudice_competente": "Tribunale",
                "articolo": "Art. 9 c.p.c.",
                "valore_causa": valore_causa,
                "materia": materia,
                "materia_riservata": False,
                "note": f"Risarcimento da circolazione veicoli > €{soglia:,.2f}: competenza Tribunale",
                "soglia_gdp_euro": soglia,
            }

    # Beni mobili o default civile: GdP ≤ 5.000 (art. 7 co. 1 c.p.c.)
    soglia = 5_000.0
    if valore_causa <= soglia:
        return {
            "giudice_competente": "Giudice di Pace",
            "articolo": "Art. 7 co. 1 c.p.c.",
            "valore_causa": valore_causa,
            "materia": materia,
            "materia_riservata": False,
            "note": f"Cause relative a beni mobili di valore ≤ €{soglia:,.2f}: competenza GdP",
            "soglia_gdp_euro": soglia,
        }
    else:
        return {
            "giudice_competente": "Tribunale",
            "articolo": "Art. 9 c.p.c.",
            "valore_causa": valore_causa,
            "materia": materia,
            "materia_riservata": False,
            "note": f"Causa di valore > €{soglia:,.2f}: competenza Tribunale",
            "soglia_gdp_euro": soglia,
        }


@mcp.tool(tags={"giudiziario"})
def verifica_mediazione_obbligatoria(materia: str) -> dict:
    """Verifica se una materia è soggetta a mediazione obbligatoria (art. 5 D.Lgs. 28/2010).

    Controlla l'elenco delle materie per cui il tentativo di mediazione è condizione
    di procedibilità della domanda giudiziale, sia quelle originarie del 2010 sia
    quelle aggiunte dalla riforma Cartabia (D.Lgs. 149/2022).
    Vigenza: Art. 5 co. 1 D.Lgs. 28/2010 come modificato da D.Lgs. 149/2022.
    Precisione: ESATTO per le materie elencate; per materie di confine verificare con cite_law.
    Chaining: → competenza_giudice() per determinare il giudice davanti al quale instaurare il giudizio

    Args:
        materia: Materia della controversia (es. 'condominio', 'locazione', 'franchising',
                 'contratti_bancari', 'responsabilita_medica'). Case-insensitive.
    """
    data = _load_mediazione()
    materie = data["materie"]
    esclusioni = data["esclusioni"]

    materia_norm = materia.lower().strip().replace(" ", "_")

    trovata = None
    for m in materie:
        if m["nome"] == materia_norm or materia_norm in m["nome"] or m["nome"] in materia_norm:
            trovata = m
            break

    if trovata:
        return {
            "obbligatoria": True,
            "materia_input": materia,
            "materia_trovata": trovata["nome"],
            "fonte": trovata["fonte"],
            "note": trovata["note"],
            "esclusioni_applicabili": esclusioni,
            "riferimento_normativo": "Art. 5 co. 1 D.Lgs. 28/2010 (mod. D.Lgs. 149/2022)",
        }

    return {
        "obbligatoria": False,
        "materia_input": materia,
        "materia_trovata": None,
        "fonte": None,
        "note": "Materia non inclusa nell'elenco ex art. 5 co. 1 D.Lgs. 28/2010. La mediazione può essere tentata su base volontaria ma non è condizione di procedibilità.",
        "esclusioni_applicabili": esclusioni,
        "riferimento_normativo": "Art. 5 co. 1 D.Lgs. 28/2010 (mod. D.Lgs. 149/2022)",
    }


@mcp.tool(tags={"giudiziario"})
def gratuito_patrocinio(
    reddito_richiedente: float,
    n_familiari_conviventi: int = 0,
    redditi_familiari: list[float] | None = None,
    ambito: str = "civile",
    vittima_violenza: bool = False,
) -> dict:
    """Verifica l'ammissibilità al patrocinio a spese dello Stato (DPR 115/2002).

    Calcola se il nucleo familiare rientra nei limiti di reddito per l'ammissione al
    gratuito patrocinio. Per le vittime di violenza domestica/di genere l'ammissione
    è automatica indipendentemente dal reddito. In ambito penale la soglia è maggiorata
    di €1.032,91 per ogni familiare convivente.
    Vigenza: DPR 115/2002 artt. 76, 92 — D.M. 22 aprile 2025 (soglia €13.659,64).
    Precisione: INDICATIVO — la verifica definitiva compete al Consiglio dell'Ordine.
    Chaining: → competenza_giudice() per individuare il giudice, → calcolo_parcella() per stimare il compenso

    Args:
        reddito_richiedente: Reddito imponibile annuo del richiedente in euro (ultimo anno d'imposta).
        n_familiari_conviventi: Numero di familiari conviventi (escluso il richiedente). Default 0.
        redditi_familiari: Lista dei redditi imponibili annui dei familiari conviventi in euro. Default [].
        ambito: Ambito processuale: 'civile' (default) o 'penale'. In penale la soglia è maggiorata per familiari.
        vittima_violenza: True se vittima di violenza domestica/di genere/stalking (art. 76 co. 4-ter DPR 115/2002). Ammissione automatica.
    """
    if reddito_richiedente < 0:
        raise ValueError("reddito_richiedente non può essere negativo")

    if redditi_familiari is None:
        redditi_familiari = []

    SOGLIA_BASE = 13_659.64
    MAGGIORAZIONE_PENALE_PER_FAMILIARE = 1_032.91

    # Vittime di violenza: ammissione automatica indipendentemente dal reddito
    if vittima_violenza:
        reddito_totale = reddito_richiedente + sum(redditi_familiari)
        return {
            "ammesso": True,
            "vittima_violenza": True,
            "reddito_totale_nucleo": round(reddito_totale, 2),
            "soglia_applicata": SOGLIA_BASE,
            "margine": None,
            "ambito": ambito,
            "note": "Ammissione automatica per vittime di violenza domestica/di genere/stalking indipendentemente dal reddito (art. 76 co. 4-ter DPR 115/2002)",
            "riferimento_normativo": "DPR 115/2002 artt. 76, 92 — D.M. 22 aprile 2025 (soglia €13.659,64)",
        }

    reddito_totale = reddito_richiedente + sum(redditi_familiari)

    # Calcolo soglia applicabile
    if ambito == "penale" and n_familiari_conviventi > 0:
        soglia = SOGLIA_BASE + (n_familiari_conviventi * MAGGIORAZIONE_PENALE_PER_FAMILIARE)
        nota_soglia = (
            f"Soglia penale: €{SOGLIA_BASE:,.2f} base "
            f"+ ({n_familiari_conviventi} × €{MAGGIORAZIONE_PENALE_PER_FAMILIARE:,.2f}) = €{soglia:,.2f}"
        )
    else:
        soglia = SOGLIA_BASE
        nota_soglia = f"Soglia civile: €{SOGLIA_BASE:,.2f}"

    ammesso = reddito_totale <= soglia
    margine = round(soglia - reddito_totale, 2)

    note_calc = (
        f"Reddito nucleo familiare: €{reddito_totale:,.2f} — {nota_soglia} — "
        f"{'AMMESSO' if ammesso else 'NON AMMESSO'} (margine: {'+' if margine >= 0 else ''}{margine:,.2f} €)"
    )

    return {
        "ammesso": ammesso,
        "vittima_violenza": False,
        "reddito_richiedente": round(reddito_richiedente, 2),
        "redditi_familiari": [round(r, 2) for r in redditi_familiari],
        "n_familiari_conviventi": n_familiari_conviventi,
        "reddito_totale_nucleo": round(reddito_totale, 2),
        "soglia_applicata": round(soglia, 2),
        "margine": margine,
        "ambito": ambito,
        "note": note_calc,
        "riferimento_normativo": "DPR 115/2002 artt. 76, 92 — D.M. 22 aprile 2025 (soglia €13.659,64)",
    }
