"""Calcolo del rendimento netto di strumenti finanziari italiani: BOT (zero-coupon), BTP (cedola fissa),
pronti contro termine (PCT), buoni fruttiferi postali e confronto tra più strumenti.
Tassazione agevolata 12,5% per titoli di Stato (D.Lgs. 239/1996); 26% per altri strumenti."""

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


@mcp.tool(tags={"investimenti"})
def rendimento_bot(
    valore_nominale: float,
    prezzo_acquisto: float,
    giorni_scadenza: int,
    commissione_pct: float = 0.0,
) -> dict:
    """Calcola il rendimento netto di un BOT (Buono Ordinario del Tesoro, zero-coupon).
    Vigenza: D.Lgs. 239/1996 — imposta sostitutiva 12,5% sulla plusvalenza (scarto di emissione).
    Precisione: ESATTO (formula rendimento annualizzato su base 365gg; imposta sulla plusvalenza).

    Args:
        valore_nominale: Valore nominale del BOT in euro — importo rimborsato a scadenza (€)
        prezzo_acquisto: Prezzo di acquisto in euro (€), normalmente inferiore al nominale
        giorni_scadenza: Giorni residui alla scadenza (interi positivi)
        commissione_pct: Commissione bancaria percentuale sul nominale (es. 0.15 per 0,15%)
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


@mcp.tool(tags={"investimenti"})
def rendimento_btp(
    valore_nominale: float,
    prezzo_acquisto: float,
    cedola_annua_pct: float,
    anni_scadenza: int,
    frequenza_cedola: int = 2,
) -> dict:
    """Calcola il rendimento netto di un BTP (Buono del Tesoro Poliennale) a cedola fissa.
    Vigenza: D.Lgs. 239/1996 — imposta sostitutiva 12,5% su cedole e plusvalenza da capital gain.
    Precisione: INDICATIVO (rendimento semplificato: non considera il reinvestimento delle cedole
    né il rateo cedolare al momento dell'acquisto; per il rendimento esatto usare il TIR).

    Args:
        valore_nominale: Valore nominale del BTP in euro (€), solitamente 1.000€ per titolo
        prezzo_acquisto: Prezzo di acquisto in euro (€), può essere sopra o sotto il nominale
        cedola_annua_pct: Tasso cedolare annuo lordo in percentuale (es. 3.5 per 3,5%)
        anni_scadenza: Anni residui alla scadenza (interi positivi)
        frequenza_cedola: Numero di cedole per anno (default 2 = semestrale; 1 = annuale)
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


@mcp.tool(tags={"investimenti"})
def pronti_termine(
    capitale: float,
    tasso_lordo_pct: float,
    giorni: int,
    tipo_sottostante: str = "titoli_stato",
) -> dict:
    """Calcola il rendimento netto di un pronti contro termine (PCT).
    Vigenza: D.Lgs. 239/1996 (titoli di Stato, aliquota 12,5%); D.L. 66/2014 (altri strumenti, 26%).
    Precisione: ESATTO (formula interessi su base 365gg con aliquota corretta per il sottostante).

    Args:
        capitale: Capitale investito in euro (€)
        tasso_lordo_pct: Tasso di interesse lordo annuo in percentuale (es. 3.5 per 3,5%)
        giorni: Durata dell'operazione in giorni (interi positivi)
        tipo_sottostante: Tipo di sottostante: 'titoli_stato' (aliquota 12,5%) o 'altro' (aliquota 26%)
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


@mcp.tool(tags={"investimenti"})
def rendimento_buoni_postali(
    importo: float,
    tipo: str = "ordinario",
    anni: int = 10,
) -> dict:
    """Calcola il rendimento netto di buoni fruttiferi postali con capitalizzazione a scaglioni.
    Vigenza: D.Lgs. 239/1996 — imposta sostitutiva 12,5% (equiparati ai titoli di Stato).
    Precisione: INDICATIVO (i tassi sono indicativi aggiornati al momento dell'implementazione;
    le condizioni effettive variano — verificare sempre le condizioni aggiornate su poste.it).

    Args:
        importo: Importo sottoscritto in euro (€)
        tipo: Tipologia di buono: 'ordinario' (durata max 20 anni), '3x4' (max 12 anni),
              '4x4' (max 16 anni), 'dedicato_minori' (max 18 anni)
        anni: Durata in anni desiderata — viene limitata al massimo del tipo selezionato
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


@mcp.tool(tags={"investimenti"})
def confronto_investimenti(
    importo: float,
    investimenti: list[dict],
) -> dict:
    """Confronta il rendimento netto tra diversi strumenti finanziari con tassazione corretta.
    Precisione: INDICATIVO (confronto basato su rendimento lordo annuo costante; non considera
    rischio, inflazione, costi di gestione o variazioni di tasso nel tempo).

    Args:
        importo: Importo da investire in euro (€), uguale per tutti gli strumenti nel confronto
        investimenti: Lista di dict, ciascuno con le chiavi:
                      - nome (str): nome identificativo dello strumento
                      - rendimento_lordo_pct (float): tasso lordo annuo in percentuale
                      - tipo_tassazione (str): 'titoli_stato' (12,5%) o 'altro' (26%)
                      - durata_anni (int): orizzonte temporale in anni
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
