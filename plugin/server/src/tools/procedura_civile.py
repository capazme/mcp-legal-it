"""Strumenti di procedura civile: competenza del giudice (artt. 7-17 c.p.c.), verifica mediazione obbligatoria (art. 5 D.Lgs. 28/2010), ammissione al gratuito patrocinio (DPR 115/2002)."""

import re
import unicodedata

from src.server import mcp
from src.lib import _data
from src.lib._data import sourced


def _load_mediazione() -> dict:
    """The mediation matters table, read lazily and observed by the ledger."""
    return _data.load("mediazione_obbligatoria")


def _normalizza_materia(materia: str) -> str:
    """Lowercase, accents stripped, every run of non-alphanumerics turned into one underscore."""
    nfkd = unicodedata.normalize("NFKD", materia.lower())
    senza_accenti = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", senza_accenti).strip("_")


@mcp.tool(tags={"giudiziario"})
def competenza_giudice(
    valore_causa: float,
    materia: str = "civile",
) -> dict:
    """Determina il giudice competente per valore e materia (artt. 7-17 c.p.c.).

    Individua la competenza tra Giudice di Pace e Tribunale in base al valore della
    causa e alla materia. Le materie di competenza esclusiva del Tribunale (art. 9 co. 2:
    imposte e tasse, stato e capacità, querela di falso, esecuzione forzata, valore
    indeterminabile) sono assegnate indipendentemente dal valore; le materie non riconosciute
    sono rifiutate. Le soglie di 30.000 e 50.000 euro del D.Lgs. 116/2017 si applicano dal
    31/10/2027 (art. 32 co. 3): fino ad allora restano 10.000 e 25.000.
    Vigenza: Artt. 7-17 c.p.c. — soglie aggiornate post-Cartabia (D.Lgs. 149/2022), testo letto su Normattiva al 2026-09-29.
    Precisione: INDICATIVO per materie di confine; verificare con giurisprudenza di merito.
    Chaining: → verifica_mediazione_obbligatoria() per verificare se serve il tentativo di mediazione

    Args:
        valore_causa: Valore della causa in euro (es. 3000.0). Deve essere >= 0.
        materia: Materia della controversia. Valori: 'civile' (default), 'circolazione_stradale',
                 'mobili', 'locazione', 'condominio', 'lavoro', 'famiglia', 'fallimento', 'crisi_impresa',
                 'usucapione', 'immobili', 'querela_di_falso', 'imposte_tasse', 'stato_capacita',
                 'esecuzione_forzata', 'intelligenza_artificiale', 'valore_indeterminabile',
                 'apposizione_termini', 'immissioni', 'servitu'
    """
    if valore_causa < 0:
        raise ValueError("valore_causa non può essere negativo")

    materia_norm = materia.lower().strip().replace(" ", "_")

    def _risposta(giudice, articolo, note, riservata, soglia=None):
        return {
            "giudice_competente": giudice,
            "articolo": articolo,
            "valore_causa": valore_causa,
            "materia": materia,
            "materia_riservata": riservata,
            "note": note,
            "soglia_gdp_euro": soglia,
        }

    # Materie di competenza del Tribunale a prescindere dal valore.
    # Art. 9 co. 2 c.p.c. (competenza esclusiva): imposte e tasse, stato e capacità delle
    # persone, diritti onorifici, querela di falso, esecuzione forzata, sistemi di
    # intelligenza artificiale, valore indeterminabile. Altre materie: residuale art. 9 co. 1
    # (l'art. 7 co. 1 copre solo i beni mobili).
    _art9_co2 = "Art. 9 co. 2 c.p.c."
    _riservate_tribunale = {
        "locazione": ("Tribunale", "Artt. 9 co. 1 e 447-bis c.p.c.", "Locazione di immobili: non è causa su beni mobili (art. 7 co. 1), competenza residuale del Tribunale indipendentemente dal valore; rito speciale art. 447-bis c.p.c."),
        "lavoro": ("Tribunale — Sezione Lavoro", "Art. 413 co. 1 c.p.c.", "Controversie di lavoro subordinato, para-subordinato e previdenziali (art. 409 c.p.c.): il Tribunale in funzione di giudice del lavoro"),
        "famiglia": ("Tribunale", _art9_co2 + " — rito artt. 473-bis ss. c.p.c.", "Stato e capacità delle persone, separazione, divorzio, filiazione (gli artt. 706 ss. c.p.c. sono abrogati dal D.Lgs. 149/2022)"),
        "stato_capacita": ("Tribunale", _art9_co2, "Cause relative allo stato e alla capacità delle persone e ai diritti onorifici: competenza esclusiva del Tribunale"),
        "imposte_tasse": ("Tribunale", _art9_co2, "Cause in materia di imposte e tasse: competenza esclusiva del Tribunale"),
        "querela_di_falso": ("Tribunale", _art9_co2, "Querela di falso: competenza esclusiva del Tribunale, qualunque sia il valore"),
        "esecuzione_forzata": ("Tribunale", _art9_co2, "Esecuzione forzata: competenza esclusiva del Tribunale"),
        "intelligenza_artificiale": ("Tribunale", _art9_co2, "Cause sul funzionamento di un sistema di intelligenza artificiale: competenza esclusiva del Tribunale"),
        "valore_indeterminabile": ("Tribunale", _art9_co2, "Cause di valore indeterminabile: competenza esclusiva del Tribunale"),
        "usucapione": ("Tribunale", "Artt. 7 co. 1 e 9 co. 1 c.p.c.", "Usucapione e cause su immobili o diritti reali immobiliari: non sono cause su beni mobili, competenza residuale del Tribunale. Dal 31/10/2027 (art. 32 co. 3 D.Lgs. 116/2017) il Giudice di Pace è competente per l'usucapione fino a 30.000 euro (art. 7 co. 4)"),
        "immobili": ("Tribunale", "Artt. 7 co. 1 e 9 co. 1 c.p.c.", "Cause su immobili: non sono cause su beni mobili (art. 7 co. 1), competenza residuale del Tribunale"),
        "crisi_impresa": ("Tribunale del circondario in cui il debitore ha il centro degli interessi principali (COMI)", "Art. 27 co. 2 D.Lgs. 14/2019 (CCII)", "Liquidazione giudiziale e crisi d'impresa: tribunale del COMI; il tribunale sede della sezione specializzata in materia di imprese solo per imprese assoggettabili ad amministrazione straordinaria e gruppi di imprese di rilevante dimensione (art. 27 co. 1 CCII)"),
    }
    _riservate_tribunale["fallimento"] = _riservate_tribunale["crisi_impresa"]

    # Materie del Giudice di Pace qualunque ne sia il valore (art. 7 co. 3 c.p.c.)
    _gdp_qualunque_valore = {
        "apposizione_termini": "Cause relative ad apposizione di termini (n. 1)",
        "immissioni": "Immissioni di fumo, calore, rumori tra proprietari o detentori di immobili ad uso abitativo (n. 3)",
        "servitu": "Cause in materia di esercizio delle servitù prediali (n. 3-novies)",
    }

    if materia_norm in _riservate_tribunale:
        giudice, articolo, note = _riservate_tribunale[materia_norm]
        return _risposta(giudice, articolo, note, True)

    if materia_norm in _gdp_qualunque_valore:
        return _risposta("Giudice di Pace", "Art. 7 co. 3 c.p.c.", _gdp_qualunque_valore[materia_norm] + ": competenza GdP qualunque ne sia il valore", True)

    if materia_norm == "condominio":
        # Servizi condominiali: GdP qualunque valore (art. 7 co. 3 n. 2); crediti: art. 7 co. 1.
        if valore_causa <= 10_000.0:
            return _risposta("Giudice di Pace", "Art. 7 co. 1 e co. 3 n. 2 c.p.c.",
                             "Cause condominiali: GdP per i crediti fino a 10.000 euro (art. 7 co. 1) e, qualunque ne sia il valore, per le cause sui servizi condominiali (art. 7 co. 3 n. 2)",
                             False, 10_000.0)
        return _risposta("Tribunale", "Art. 9 co. 1 c.p.c.",
                         "Oltre 10.000 euro: Tribunale, salvo le cause in materia di condominio negli edifici che l'art. 7 co. 3 n. 2 c.p.c. assegna al GdP qualunque ne sia il valore (verificare l'oggetto)",
                         False, 10_000.0)

    _note_valide = {"civile", "mobili", "circolazione_stradale"}
    if materia_norm not in _note_valide:
        elenco = sorted(_note_valide | set(_riservate_tribunale) | set(_gdp_qualunque_valore) | {"condominio"})
        raise ValueError(f"materia non riconosciuta: '{materia}'. Valori ammessi: {', '.join(elenco)}")

    # Materia circolazione stradale: GdP ≤ 25.000 (art. 7 co. 2 c.p.c., post-Cartabia).
    # La soglia di €50.000 (D.Lgs. 116/2017) ha decorrenza 31/10/2027 (art. 32 co. 3 D.Lgs. 116/2017, mod. art. 5 co. 1 lett. b) D.L. 100/2026).
    if materia_norm == "circolazione_stradale":
        soglia = 25_000.0
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

    # Beni mobili o default civile: GdP ≤ 10.000 (art. 7 co. 1 c.p.c., post-Cartabia).
    # La soglia di €30.000 (D.Lgs. 116/2017) ha decorrenza 31/10/2027 (art. 32 co. 3 D.Lgs. 116/2017, mod. art. 5 co. 1 lett. b) D.L. 100/2026).
    soglia = 10_000.0
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
@sourced("mediazione_obbligatoria")
def verifica_mediazione_obbligatoria(materia: str) -> dict:
    """Verifica se una materia è soggetta a mediazione obbligatoria (art. 5 D.Lgs. 28/2010).

    Controlla l'elenco delle materie per cui il tentativo di mediazione è condizione
    di procedibilità della domanda giudiziale, sia quelle originarie del 2010 sia
    quelle aggiunte dalla riforma Cartabia (D.Lgs. 149/2022).
    Vigenza: Art. 5 co. 1, 5 e 6 D.Lgs. 28/2010 come modificato da D.Lgs. 149/2022 e D.Lgs. 28/2023 (testo letto su Normattiva al 2026-09-29).
    Il confronto e' per identita' (nome o alias, senza accenti): un input vuoto o sotto i 3 caratteri e' 'non determinabile',
    un input generico come 'contratti' e' 'non determinabile' (obbligatoria=None).
    Precisione: ESATTO per le materie elencate; per materie di confine verificare con cite_law.
    Chaining: → competenza_giudice() per determinare il giudice davanti al quale instaurare il giudizio

    Args:
        materia: Materia della controversia (es. 'condominio', 'locazione', 'franchising',
                 'contratti_bancari', 'responsabilita_medica'). Case-insensitive.
    """
    data = _load_mediazione()
    materie = data["materie"]
    esclusioni = data["esclusioni"]

    materia_norm = _normalizza_materia(materia)
    def _risposta(**extra):
        base = {
            "materia_input": materia,
            "esclusioni_applicabili": esclusioni,
            "nota_provvedimenti_urgenti": data.get("nota_provvedimenti_urgenti"),
            "riferimento_normativo": "Art. 5 co. 1 D.Lgs. 28/2010 (mod. D.Lgs. 149/2022)",
        }
        base.update(extra)
        return base

    # Confronto per identita' (nome o alias esatto dopo la normalizzazione), non per sottostringa:
    # 'contratti' o una stringa vuota non devono agganciare la prima voce che li contiene.
    trovata = None
    for m in materie:
        if materia_norm == m["nome"] or materia_norm in m.get("alias", []):
            trovata = m
            break

    if trovata:
        return _risposta(
            obbligatoria=True,
            materia_trovata=trovata["nome"],
            fonte=trovata["fonte"],
            note=trovata["note"],
        )

    if len(materia_norm) < 3:
        return _risposta(
            obbligatoria=None,
            materia_trovata=None,
            fonte=None,
            note="Non determinabile: materia vuota o troppo breve (meno di 3 caratteri). Indicare la materia della controversia.",
        )

    if materia_norm in ("contratto", "contratti"):
        return _risposta(
            obbligatoria=None,
            materia_trovata=None,
            fonte=None,
            note="Non determinabile: l'art. 5 co. 1 D.Lgs. 28/2010 non elenca i contratti in genere, ma solo i contratti assicurativi, bancari e finanziari, l'associazione in partecipazione, il consorzio, il franchising, l'opera, la rete, la somministrazione, la subfornitura, la locazione, il comodato e l'affitto di aziende. Indicare il tipo di contratto.",
        )

    if materia_norm in ("circolazione_stradale", "circolazione", "sinistro_stradale"):
        return _risposta(
            obbligatoria=False,
            materia_trovata=None,
            fonte=None,
            note="Materia non inclusa nell'elenco ex art. 5 co. 1 D.Lgs. 28/2010. Il risarcimento del danno da circolazione di veicoli e natanti (e le domande di pagamento fino a 50.000 euro) richiede la negoziazione assistita obbligatoria (art. 3 D.L. 132/2014).",
        )

    return _risposta(
        obbligatoria=False,
        materia_trovata=None,
        fonte=None,
        note="Materia non inclusa nell'elenco ex art. 5 co. 1 D.Lgs. 28/2010. La mediazione può essere tentata su base volontaria ma non è condizione di procedibilità.",
    )


@mcp.tool(tags={"giudiziario"})
def gratuito_patrocinio(
    reddito_richiedente: float,
    n_familiari_conviventi: int = 0,
    redditi_familiari: list[float] | None = None,
    ambito: str = "civile",
    vittima_violenza: bool = False,
    diritti_personalita: bool = False,
    interessi_in_conflitto: bool = False,
) -> dict:
    """Verifica l'ammissibilità al patrocinio a spese dello Stato (DPR 115/2002).

    Calcola se il nucleo familiare rientra nei limiti di reddito per l'ammissione al
    gratuito patrocinio. Per le vittime di violenza domestica/di genere l'ammissione
    è automatica indipendentemente dal reddito. In ambito penale la soglia è maggiorata
    di €1.032,91 per ogni familiare convivente. Quando la causa ha per oggetto diritti
    della personalità o gli interessi del richiedente sono in conflitto con quelli dei
    conviventi si conta il solo reddito personale (art. 76 co. 4).
    Vigenza: DPR 115/2002 artt. 76, 92 — D.M. 22 aprile 2025 (soglia €13.659,64), verificato al 2026-09-29.
    Precisione: INDICATIVO — la verifica definitiva compete al Consiglio dell'Ordine.
    Chaining: → competenza_giudice() per individuare il giudice, → calcolo_parcella() per stimare il compenso

    Args:
        reddito_richiedente: Reddito imponibile annuo del richiedente in euro (ultimo anno d'imposta).
        n_familiari_conviventi: Numero di familiari conviventi (escluso il richiedente). Default 0.
        redditi_familiari: Lista dei redditi imponibili annui dei familiari conviventi in euro. Default [].
        ambito: Ambito processuale: 'civile' (default) o 'penale'. In penale la soglia è maggiorata per familiari.
        vittima_violenza: True se vittima di violenza domestica/di genere/stalking (art. 76 co. 4-ter DPR 115/2002). Ammissione automatica.
        diritti_personalita: True se la causa ha per oggetto diritti della personalità (art. 76 co. 4): conta il solo reddito del richiedente.
        interessi_in_conflitto: True se gli interessi del richiedente sono in conflitto con quelli dei familiari conviventi (art. 76 co. 4): conta il solo reddito del richiedente.

    Nota: il reddito da indicare comprende anche i redditi esenti IRPEF e quelli soggetti a ritenuta a titolo d'imposta o a imposta sostitutiva (art. 76 co. 3).
    """
    if reddito_richiedente < 0:
        raise ValueError("reddito_richiedente non può essere negativo")

    if redditi_familiari is None:
        redditi_familiari = []

    ambito = ambito.lower().strip()

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

    # Art. 76 co. 4: solo reddito personale per diritti della personalità o conflitto di interessi
    solo_personale = diritti_personalita or interessi_in_conflitto
    if solo_personale:
        reddito_totale = reddito_richiedente
    else:
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

    etichetta_reddito = (
        "Reddito personale (art. 76 co. 4 DPR 115/2002)" if solo_personale else "Reddito nucleo familiare"
    )
    note_calc = (
        f"{etichetta_reddito}: €{reddito_totale:,.2f} — {nota_soglia} — "
        f"{'AMMESSO' if ammesso else 'NON AMMESSO'} (margine: {'+' if margine >= 0 else ''}{margine:,.2f} €)"
    )

    return {
        "ammesso": ammesso,
        "vittima_violenza": False,
        "reddito_richiedente": round(reddito_richiedente, 2),
        "redditi_familiari": [round(r, 2) for r in redditi_familiari],
        "n_familiari_conviventi": n_familiari_conviventi,
        "solo_reddito_personale": solo_personale,
        "reddito_totale_nucleo": round(reddito_totale, 2),
        "soglia_applicata": round(soglia, 2),
        "margine": margine,
        "ambito": ambito,
        "note": note_calc,
        "riferimento_normativo": "DPR 115/2002 artt. 76, 92 — D.M. 22 aprile 2025 (soglia €13.659,64)",
    }
