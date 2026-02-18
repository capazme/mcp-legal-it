"""Sezione 10 — Investimenti: rendimento BOT, BTP, pronti termine, buoni postali, confronto."""

from src.server import mcp


# Italian tax rates on financial instruments
_ALIQUOTA_TITOLI_STATO = 12.5  # BOT, BTP, buoni postali, PCT su titoli di stato
_ALIQUOTA_ALTRO = 26.0  # azioni, obbligazioni corporate, fondi, etc.


def _aliquota(tipo_tassazione: str) -> float:
    return _ALIQUOTA_TITOLI_STATO if tipo_tassazione == "titoli_stato" else _ALIQUOTA_ALTRO


# Indicative rates for buoni fruttiferi postali (gross annual %, by year bracket)
_TASSI_BUONI = {
    "ordinario": [
        (1, 0.50), (2, 0.50), (3, 0.75), (4, 0.75),
        (5, 1.00), (6, 1.00), (7, 1.25), (8, 1.25),
        (9, 1.50), (10, 1.50), (11, 1.75), (12, 1.75),
        (13, 2.00), (14, 2.00), (15, 2.00), (16, 2.00),
        (17, 2.25), (18, 2.25), (19, 2.25), (20, 2.25),
    ],
    "3x4": [
        (3, 0.75), (6, 1.00), (9, 1.50), (12, 2.00),
    ],
    "4x4": [
        (4, 1.00), (8, 1.50), (12, 2.00), (16, 2.50),
    ],
    "dedicato_minori": [
        (4, 1.50), (8, 2.00), (12, 2.50), (16, 3.00), (18, 3.50),
    ],
}


@mcp.tool()
def rendimento_bot(
    valore_nominale: float,
    prezzo_acquisto: float,
    giorni_scadenza: int,
    commissione_pct: float = 0.0,
) -> dict:
    """Calcola rendimento netto di un BOT (zero-coupon, imposta sostitutiva 12.5%).

    Args:
        valore_nominale: Valore nominale del BOT in euro (rimborso a scadenza)
        prezzo_acquisto: Prezzo di acquisto in euro
        giorni_scadenza: Giorni residui alla scadenza
        commissione_pct: Commissione bancaria percentuale sul nominale (es. 0.15)
    """
    if giorni_scadenza <= 0:
        return {"errore": "giorni_scadenza deve essere positivo"}
    if prezzo_acquisto <= 0:
        return {"errore": "prezzo_acquisto deve essere positivo"}

    plusvalenza = valore_nominale - prezzo_acquisto
    commissione = valore_nominale * commissione_pct / 100
    imposta = plusvalenza * _ALIQUOTA_TITOLI_STATO / 100 if plusvalenza > 0 else 0.0
    guadagno_netto = plusvalenza - imposta - commissione

    rendimento_lordo_annuo = (plusvalenza / prezzo_acquisto) * (365 / giorni_scadenza) * 100
    rendimento_netto_annuo = (guadagno_netto / prezzo_acquisto) * (365 / giorni_scadenza) * 100

    return {
        "valore_nominale": valore_nominale,
        "prezzo_acquisto": prezzo_acquisto,
        "giorni_scadenza": giorni_scadenza,
        "plusvalenza_lorda": round(plusvalenza, 2),
        "imposta_sostitutiva_pct": _ALIQUOTA_TITOLI_STATO,
        "imposta": round(imposta, 2),
        "commissione": round(commissione, 2),
        "guadagno_netto": round(guadagno_netto, 2),
        "rendimento_lordo_annuo_pct": round(rendimento_lordo_annuo, 4),
        "rendimento_netto_annuo_pct": round(rendimento_netto_annuo, 4),
        "riferimento_normativo": "D.Lgs. 239/1996 — imposta sostitutiva 12,5% su titoli di Stato",
    }


@mcp.tool()
def rendimento_btp(
    valore_nominale: float,
    prezzo_acquisto: float,
    cedola_annua_pct: float,
    anni_scadenza: int,
    frequenza_cedola: int = 2,
) -> dict:
    """Calcola rendimento netto di un BTP a cedola fissa (imposta sostitutiva 12.5%).

    Args:
        valore_nominale: Valore nominale del BTP in euro
        prezzo_acquisto: Prezzo di acquisto in euro
        cedola_annua_pct: Tasso cedolare annuo lordo (es. 3.5 per 3,5%)
        anni_scadenza: Anni residui alla scadenza
        frequenza_cedola: Numero cedole per anno (default 2 = semestrale)
    """
    if anni_scadenza <= 0:
        return {"errore": "anni_scadenza deve essere positivo"}
    if prezzo_acquisto <= 0:
        return {"errore": "prezzo_acquisto deve essere positivo"}

    # Cedole
    cedola_singola_lorda = valore_nominale * (cedola_annua_pct / 100) / frequenza_cedola
    n_cedole = anni_scadenza * frequenza_cedola
    totale_cedole_lordo = cedola_singola_lorda * n_cedole
    imposta_cedole = totale_cedole_lordo * _ALIQUOTA_TITOLI_STATO / 100
    totale_cedole_netto = totale_cedole_lordo - imposta_cedole

    # Plusvalenza in conto capitale
    plusvalenza = valore_nominale - prezzo_acquisto
    imposta_plusvalenza = plusvalenza * _ALIQUOTA_TITOLI_STATO / 100 if plusvalenza > 0 else 0.0
    plusvalenza_netta = plusvalenza - imposta_plusvalenza

    # Rendimento complessivo
    guadagno_netto_totale = totale_cedole_netto + plusvalenza_netta
    rendimento_netto_annuo = (guadagno_netto_totale / prezzo_acquisto / anni_scadenza) * 100

    flusso_cedole = []
    for i in range(1, n_cedole + 1):
        flusso_cedole.append({
            "cedola_n": i,
            "lorda": round(cedola_singola_lorda, 2),
            "netta": round(cedola_singola_lorda * (1 - _ALIQUOTA_TITOLI_STATO / 100), 2),
        })

    return {
        "valore_nominale": valore_nominale,
        "prezzo_acquisto": prezzo_acquisto,
        "cedola_annua_pct": cedola_annua_pct,
        "anni_scadenza": anni_scadenza,
        "frequenza_cedola": frequenza_cedola,
        "totale_cedole_lordo": round(totale_cedole_lordo, 2),
        "imposta_cedole": round(imposta_cedole, 2),
        "totale_cedole_netto": round(totale_cedole_netto, 2),
        "plusvalenza_lorda": round(plusvalenza, 2),
        "imposta_plusvalenza": round(imposta_plusvalenza, 2),
        "plusvalenza_netta": round(plusvalenza_netta, 2),
        "guadagno_netto_totale": round(guadagno_netto_totale, 2),
        "rendimento_netto_annuo_pct": round(rendimento_netto_annuo, 4),
        "flusso_cedole": flusso_cedole,
        "riferimento_normativo": "D.Lgs. 239/1996 — imposta sostitutiva 12,5% su titoli di Stato",
    }


@mcp.tool()
def pronti_termine(
    capitale: float,
    tasso_lordo_pct: float,
    giorni: int,
    tipo_sottostante: str = "titoli_stato",
) -> dict:
    """Calcola rendimento netto di un pronti contro termine (PCT).

    Args:
        capitale: Capitale investito in euro
        tasso_lordo_pct: Tasso lordo annuo percentuale (es. 3.5)
        giorni: Durata dell'operazione in giorni
        tipo_sottostante: 'titoli_stato' (aliquota 12.5%) o 'altro' (aliquota 26%)
    """
    if giorni <= 0:
        return {"errore": "giorni deve essere positivo"}
    if capitale <= 0:
        return {"errore": "capitale deve essere positivo"}

    aliquota = _aliquota(tipo_sottostante)
    interessi_lordi = capitale * (tasso_lordo_pct / 100) * giorni / 365
    imposta = interessi_lordi * aliquota / 100
    interessi_netti = interessi_lordi - imposta
    rendimento_netto_annuo = (interessi_netti / capitale) * (365 / giorni) * 100

    return {
        "capitale": capitale,
        "tasso_lordo_pct": tasso_lordo_pct,
        "giorni": giorni,
        "tipo_sottostante": tipo_sottostante,
        "interessi_lordi": round(interessi_lordi, 2),
        "aliquota_pct": aliquota,
        "imposta": round(imposta, 2),
        "interessi_netti": round(interessi_netti, 2),
        "rendimento_netto_annuo_pct": round(rendimento_netto_annuo, 4),
        "riferimento_normativo": "D.Lgs. 239/1996 (titoli di Stato 12,5%) — D.L. 66/2014 (altri strumenti 26%)",
    }


@mcp.tool()
def rendimento_buoni_postali(
    importo: float,
    tipo: str = "ordinario",
    anni: int = 10,
) -> dict:
    """Calcola rendimento netto di buoni fruttiferi postali (imposta sostitutiva 12.5%).

    Args:
        importo: Importo sottoscritto in euro
        tipo: Tipo di buono ('ordinario', '3x4', '4x4', 'dedicato_minori')
        anni: Durata in anni (max dipende dal tipo)
    """
    if importo <= 0:
        return {"errore": "importo deve essere positivo"}
    if anni <= 0:
        return {"errore": "anni deve essere positivo"}

    tassi = _TASSI_BUONI.get(tipo)
    if tassi is None:
        return {"errore": f"tipo non valido: {tipo}. Valori ammessi: {list(_TASSI_BUONI.keys())}"}

    durata_max = tassi[-1][0]
    anni_effettivi = min(anni, durata_max)

    # Calculate compound growth using bracket rates
    montante = importo
    dettaglio = []
    tasso_idx = 0

    for anno in range(1, anni_effettivi + 1):
        while tasso_idx < len(tassi) - 1 and anno > tassi[tasso_idx][0]:
            tasso_idx += 1
        tasso = tassi[tasso_idx][1]
        interessi_anno = montante * tasso / 100
        montante += interessi_anno
        dettaglio.append({
            "anno": anno,
            "tasso_lordo_pct": tasso,
            "montante_lordo": round(montante, 2),
        })

    interessi_lordi = montante - importo
    imposta = interessi_lordi * _ALIQUOTA_TITOLI_STATO / 100
    montante_netto = montante - imposta
    interessi_netti = interessi_lordi - imposta

    # Rendimento netto annualizzato
    if anni_effettivi > 0 and importo > 0:
        rendimento_netto_annuo = ((montante_netto / importo) ** (1 / anni_effettivi) - 1) * 100
    else:
        rendimento_netto_annuo = 0.0

    return {
        "importo": importo,
        "tipo": tipo,
        "anni": anni_effettivi,
        "montante_lordo": round(montante, 2),
        "interessi_lordi": round(interessi_lordi, 2),
        "imposta_sostitutiva_pct": _ALIQUOTA_TITOLI_STATO,
        "imposta": round(imposta, 2),
        "montante_netto": round(montante_netto, 2),
        "interessi_netti": round(interessi_netti, 2),
        "rendimento_netto_annuo_pct": round(rendimento_netto_annuo, 4),
        "dettaglio_annuale": dettaglio,
        "nota": "Tassi indicativi — verificare condizioni aggiornate su poste.it",
        "riferimento_normativo": "D.Lgs. 239/1996 — imposta sostitutiva 12,5% (equiparati a titoli di Stato)",
    }


@mcp.tool()
def confronto_investimenti(
    importo: float,
    investimenti: list[dict],
) -> dict:
    """Confronta rendimento netto tra diversi strumenti finanziari.

    Args:
        importo: Importo da investire in euro
        investimenti: Lista di investimenti, ciascuno con {nome, rendimento_lordo_pct, tipo_tassazione, durata_anni}. tipo_tassazione: 'titoli_stato' (12.5%) o 'altro' (26%).
    """
    if importo <= 0:
        return {"errore": "importo deve essere positivo"}
    if not investimenti:
        return {"errore": "fornire almeno un investimento"}

    risultati = []
    for inv in investimenti:
        nome = inv.get("nome", "N/D")
        rend_lordo = inv.get("rendimento_lordo_pct", 0.0)
        tipo_tax = inv.get("tipo_tassazione", "altro")
        durata = inv.get("durata_anni", 1)

        aliquota = _aliquota(tipo_tax)
        rend_netto = rend_lordo * (1 - aliquota / 100)

        montante_lordo = importo * (1 + rend_lordo / 100) ** durata
        interessi_lordi = montante_lordo - importo
        imposta = interessi_lordi * aliquota / 100
        montante_netto = montante_lordo - imposta

        risultati.append({
            "nome": nome,
            "rendimento_lordo_pct": rend_lordo,
            "aliquota_pct": aliquota,
            "rendimento_netto_pct": round(rend_netto, 4),
            "durata_anni": durata,
            "montante_lordo": round(montante_lordo, 2),
            "imposta": round(imposta, 2),
            "montante_netto": round(montante_netto, 2),
            "guadagno_netto": round(montante_netto - importo, 2),
        })

    risultati.sort(key=lambda x: x["rendimento_netto_pct"], reverse=True)

    return {
        "importo": importo,
        "classifica": risultati,
        "migliore": risultati[0]["nome"] if risultati else None,
        "nota": "Confronto indicativo — non considera costi di gestione, inflazione o rischio",
    }
