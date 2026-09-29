"""Calcolo del rendimento netto di strumenti finanziari italiani: BOT (zero-coupon), BTP (cedola fissa),
pronti contro termine (PCT), buoni fruttiferi postali e confronto tra più strumenti.
Tassazione agevolata 12,5% per titoli di Stato (D.Lgs. 239/1996); 26% per altri strumenti."""

from bisect import bisect_right
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.lib import _clock, _data
from src.lib._data import sourced
from src.server import mcp


# Italian tax rates on financial instruments
_ALIQUOTA_TITOLI_STATO = 12.5  # BOT, BTP, buoni postali, PCT su titoli di stato
_ALIQUOTA_ALTRO = 26.0  # azioni, obbligazioni corporate, fondi, etc.


def _aliquota(tipo_tassazione: str) -> float:
    return _ALIQUOTA_TITOLI_STATO if tipo_tassazione == "titoli_stato" else _ALIQUOTA_ALTRO


def _normalizza_tipo_tassazione(valore: object) -> str | None:
    """Canonical 'titoli_stato' / 'altro', tolerating case, stray spaces and '-' for '_'.

    Anything else is None: an unknown regime must not fall back silently to 26%, a titolo di
    Stato would pay double (art. 2 co. 1 D.Lgs. 239/1996: 12,50%).
    """
    canonico = str(valore).strip().lower().replace("-", "_").replace(" ", "_")
    return canonico if canonico in ("titoli_stato", "altro") else None


def _euro(valore: float) -> float:
    """Amount rounded to the cent, half up (the fogli CDP round 8-decimal coefficients, then the cent)."""
    return float(Decimal(repr(round(valore, 8))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _aggiungi_anni(giorno: date, anni: int) -> date:
    """`giorno` shifted by whole years (29 February falls back to 28 February)."""
    try:
        return giorno.replace(year=giorno.year + anni)
    except ValueError:
        return giorno.replace(year=giorno.year + anni, day=28)


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
    if valore_nominale <= 0:
        return {"errore": "valore_nominale deve essere positivo"}

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
    if valore_nominale <= 0:
        return {"errore": "valore_nominale deve essere positivo"}
    if frequenza_cedola <= 0:
        return {"errore": "frequenza_cedola deve essere positiva (es. 1 annuale, 2 semestrale)"}

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
    if tipo_sottostante not in ("titoli_stato", "altro"):
        return {"errore": "tipo_sottostante deve essere 'titoli_stato' (12,5%) o 'altro' (26%)"}

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
@sourced("buoni_postali")
def rendimento_buoni_postali(
    importo: float,
    tipo: str = "ordinario",
    anni: int = 10,
    serie: str | None = None,
    eta_minore: int = 0,
    valore_portafoglio_buoni: float | None = None,
) -> dict:
    """Calcola montante e rendimento netto di un buono fruttifero postale con i coefficienti della serie CDP.
    Vigenza: art. 2 co. 1 e 3 D.Lgs. 239/1996 (imposta sostitutiva 12,50%, applicata da Poste) e art. 3
    co. 2 lett. a) D.L. 66/2014; condizioni economiche = coefficienti dei fogli informativi CDP delle serie
    TF120A250624 (ordinario), TF012A260724 (3x4 con premio), TF118A260922 (minori), consultati il 2026-09-29;
    bollo: art. 13 co. 2-ter e nota 3-ter Tariffa parte I D.P.R. 642/1972, art. 19 D.L. 201/2011.
    Precisione: INDICATIVO (il montante coincide con il foglio informativo della serie indicata, ma il tool non sa
    quale serie ha sottoscritto il cliente: per un buono di altra serie usare i coefficienti del suo foglio;
    per dedicato_minori il bimestre del 18 compleanno è stimato dall'età in anni; l'imposta di bollo è una
    stima esposta a parte, non inclusa nel montante netto, perché dipende dall'intero portafoglio buoni).

    Args:
        importo: Importo sottoscritto in euro (€)
        tipo: Tipologia: 'ordinario' (20 anni), '3x4_con_premio' (12 anni, con premio a scadenza), 'dedicato_minori'
              (fino ai 18 anni del minore); serie non più in emissione: '3x4' (12 anni), '4x4' (16 anni)
        anni: Anni di possesso al rimborso (interi); oltre la durata del tipo il buono è infruttifero e il calcolo
              si ferma alla scadenza. Per i 3x4 e 4x4 valgono gli interessi dell'ultimo triennio o quadriennio compiuto
        serie: Serie CDP (es. 'TF120A250624'); se omessa, la serie del tipo più recente presente in tabella
        eta_minore: Solo per dedicato_minori: età in anni compiuti del minore alla sottoscrizione (0-16, default 0)
        valore_portafoglio_buoni: Valore di rimborso complessivo dei buoni del titolare in euro (€), per la soglia di
                                  esenzione del bollo (5.000 €); se omesso si assume il montante lordo di questo buono
    """
    if importo <= 0:
        return {"errore": "importo deve essere positivo"}
    if anni <= 0:
        return {"errore": "anni deve essere positivo"}

    dati = _data.load("buoni_postali")
    tipi = dati["tipi"]
    tipo_norm = str(tipo).strip().lower()
    cfg_tipo = tipi.get(tipo_norm)
    if cfg_tipo is None:
        return {"errore": f"tipo non valido: {tipo}. Valori ammessi: {list(tipi.keys())}"}
    tipo = tipo_norm

    codice_serie = serie or cfg_tipo["serie_corrente"]
    cfg_serie = cfg_tipo["serie"].get(codice_serie)
    if cfg_serie is None:
        return {"errore": f"serie non disponibile per '{tipo}': {codice_serie}. "
                          f"Serie in tabella: {list(cfg_tipo['serie'].keys())}"}
    if valore_portafoglio_buoni is not None and valore_portafoglio_buoni <= 0:
        return {"errore": "valore_portafoglio_buoni deve essere positivo"}
    if tipo != "dedicato_minori" and eta_minore:
        return {"errore": "eta_minore vale solo per il tipo dedicato_minori"}

    avvertenze: list[str] = []
    if not cfg_serie["in_emissione"]:
        avvertenze.append(
            f"serie {codice_serie} non più in emissione (collocata fino al {cfg_serie['collocato_fino_al']}): "
            "condizioni valide per chi l'ha sottoscritta"
        )

    durata_max = cfg_tipo["durata_max_anni"]
    anni_effettivi = min(anni, durata_max)
    scadenza_minori = False
    data_18_anni = None

    if tipo == "dedicato_minori":
        if not 0 <= eta_minore <= 16:
            return {"errore": "eta_minore deve essere compresa tra 0 e 16 anni compiuti"}
        anni_al_18 = 18 - eta_minore
        anni_effettivi = min(anni, anni_al_18)
        scadenza_minori = anni >= anni_al_18
        if scadenza_minori:
            # Tabella A: the maturity coefficient depends on the bimester of the 18th birthday; the
            # last row applies to every later birthday (nota 4 of the foglio informativo).
            data_18_anni = _aggiungi_anni(_clock.today(), anni_al_18)
            righe = cfg_serie["maturita"]
            inizi = [r[0] for r in righe]
            idx = bisect_right(inizi, data_18_anni.isoformat()) - 1
            if idx < 0:
                return {"errore": f"il 18 compleanno stimato ({data_18_anni.isoformat()}) cade prima della "
                                  f"prima riga della Tabella A della serie {codice_serie} ({inizi[0]})"}
            coefficienti = {str(anno): cfg_serie["rimborso_anticipato"][str(anno)] for anno in range(0, anni_al_18)}
            coefficienti[str(anni_al_18)] = righe[idx][1:]
            avvertenze.append(
                f"scadenza al 18 compleanno stimato il {data_18_anni.isoformat()} (oggi + {anni_al_18} anni): "
                f"coefficiente della Tabella A per il bimestre che inizia il {righe[idx][0]}"
            )
        else:
            coefficienti = cfg_serie["rimborso_anticipato"]
            avvertenze.append(
                "rimborso anticipato (Tabella C, tasso nominale 0,50%, nessun interesse entro 18 mesi): "
                "con il minore ancora minorenne serve il provvedimento del giudice tutelare (art. 320 co. 4 c.c.)"
            )
    else:
        coefficienti = cfg_serie["coefficienti"]

    if anni > anni_effettivi:
        avvertenze.append(f"oltre {anni_effettivi} anni il buono è infruttifero: calcolo fermato alla scadenza")
    if tipo == "3x4_con_premio" and anni_effettivi == durata_max:
        avvertenze.append("il montante a 12 anni comprende il premio a scadenza dell'8% lordo (7% netto) del valore nominale")
    if tipo in ("3x4", "3x4_con_premio", "4x4"):
        periodo = 4 if tipo == "4x4" else 3
        compiuti = anni_effettivi // periodo * periodo
        if compiuti < anni_effettivi:
            avvertenze.append(
                f"interessi del {'quadriennio' if tipo == '4x4' else 'triennio'} in corso non corrisposti: "
                f"il montante è quello dei {compiuti} anni compiuti"
                if compiuti else
                f"nessun interesse se rimborsato prima di {periodo} anni: si restituisce il solo capitale"
            )

    lordo, netto = coefficienti[str(anni_effettivi)]
    # Rounded to the cent first: the amounts of the answer then add up to the cent
    # (montante_lordo - imposta = montante_netto), as the foglio informativo does.
    montante = _euro(importo * lordo)
    montante_netto = _euro(importo * netto)
    interessi_lordi = montante - importo
    imposta = montante - montante_netto
    interessi_netti = montante_netto - importo

    dettaglio = []
    for anno in range(1, anni_effettivi + 1):
        l_anno = coefficienti[str(anno)][0]
        riga = {"anno": anno, "coefficiente_lordo": l_anno, "montante_lordo": _euro(importo * l_anno)}
        if scadenza_minori and anno == anni_effettivi:
            riga["scadenza"] = True
        dettaglio.append(riga)

    rendimento_netto_annuo = ((montante_netto / importo) ** (1 / anni_effettivi) - 1) * 100

    # Imposta di bollo: shown apart from the montante (it depends on the whole portfolio and is
    # charged by Poste on the rendiconto). Schede di sintesi CDP: 0,20% annuo sul capitale investito
    # when the portfolio exceeds 5.000 euro; art. 19 co. 3 lett. b) D.L. 201/2011: esenti i buoni
    # postali fruttiferi di valore di rimborso complessivamente non superiore a 5.000 euro.
    bollo_cfg = dati["bollo"]
    base_portafoglio = valore_portafoglio_buoni if valore_portafoglio_buoni is not None else montante
    bollo_dovuto = base_portafoglio > bollo_cfg["soglia_esenzione_eur"]
    bollo_stimato = importo * bollo_cfg["aliquota_annua_pct"] / 100 * anni_effettivi if bollo_dovuto else 0.0

    return {
        "importo": importo,
        "tipo": tipo,
        "serie": codice_serie,
        "in_emissione": cfg_serie["in_emissione"],
        "anni": anni_effettivi,
        "montante_lordo": _euro(montante),
        "interessi_lordi": _euro(interessi_lordi),
        "imposta_sostitutiva_pct": _ALIQUOTA_TITOLI_STATO,
        "imposta": _euro(imposta),
        "montante_netto": _euro(montante_netto),
        "interessi_netti": _euro(interessi_netti),
        "rendimento_netto_annuo_pct": round(rendimento_netto_annuo, 4),
        "imposta_bollo": {
            "aliquota_annua_pct": bollo_cfg["aliquota_annua_pct"],
            "soglia_esenzione_eur": bollo_cfg["soglia_esenzione_eur"],
            "valore_portafoglio_considerato": _euro(base_portafoglio),
            "dovuta": bollo_dovuto,
            "stima_totale": _euro(bollo_stimato),
            "avvertenza": (
                "Stima non inclusa nel montante netto: il bollo (0,20% annuo sul capitale investito) è dovuto "
                "sull'intero portafoglio buoni se il suo valore di rimborso supera 5.000 euro, altrimenti "
                "i buoni sono esenti; la soglia riguarda tutti i buoni del titolare, non solo questo."
            ),
        },
        "montante_netto_dopo_bollo": _euro(montante_netto - bollo_stimato),
        "dettaglio_annuale": dettaglio,
        "avvertenze": avvertenze,
        "nota": (
            f"Coefficienti del foglio informativo CDP, serie {codice_serie} (condizioni dal "
            f"{cfg_serie['condizioni_dal']}): il buono sottoscritto in altra serie ha condizioni diverse."
        ),
        "riferimento_normativo": "D.Lgs. 239/1996 art. 2 — imposta sostitutiva 12,5% (equiparati a titoli di Stato)",
    }


@mcp.tool(tags={"investimenti"})
def confronto_investimenti(
    importo: float,
    investimenti: list[dict],
) -> dict:
    """Confronta il rendimento netto tra diversi strumenti finanziari con tassazione corretta.
    Vigenza: art. 3 co. 1 D.L. 66/2014 (26% su interessi e altri proventi); art. 2 co. 1 D.Lgs. 239/1996
    e art. 3 co. 2 lett. a)-b) D.L. 66/2014 (12,50% sui titoli dell'art. 31 D.P.R. 601/1973 ed equiparati
    e sui titoli degli Stati white list); imposta solo sui proventi percepiti (art. 45 co. 1 TUIR): con
    rendimento negativo l'imposta è zero, mai un rimborso. Testi riletti su Normattiva il 2026-09-29.
    Precisione: INDICATIVO (interessi capitalizzati al lordo e imposta prelevata una volta sola a scadenza:
    corretto per strumenti a capitalizzazione o zero coupon, per i titoli a cedola l'imposta è prelevata a
    ogni cedola e il montante è sovrastimato; rendimento lordo annuo costante; la classifica e 'migliore'
    usano il rendimento netto annuo e ignorano la durata: a parità di durata è il criterio corretto, con
    durate diverse confrontare 'montante_netto' o 'rendimento_netto_annualizzato_pct'; non considera
    rischio, inflazione, costi di gestione o variazioni di tasso nel tempo).

    Args:
        importo: Importo da investire in euro (€), uguale per tutti gli strumenti nel confronto
        investimenti: Lista di dict, ciascuno con le chiavi:
                      - nome (str): nome identificativo dello strumento
                      - rendimento_lordo_pct (float): tasso lordo annuo in percentuale (anche negativo)
                      - tipo_tassazione (str): 'titoli_stato' (12,5%) o 'altro' (26%, default se assente);
                        qualunque altro valore è rifiutato con un errore
                      - durata_anni (int): orizzonte temporale in anni interi, almeno 1
    """
    if importo <= 0:
        return {"errore": "importo deve essere positivo"}
    if not investimenti:
        return {"errore": "fornire almeno un investimento"}

    risultati = []
    for inv in investimenti:
        nome = inv.get("nome", "N/D")
        tipo_tax = _normalizza_tipo_tassazione(inv.get("tipo_tassazione", "altro"))
        if tipo_tax is None:
            return {
                "errore": (
                    f"tipo_tassazione '{inv.get('tipo_tassazione')}' non riconosciuto per '{nome}': "
                    "usare 'titoli_stato' (12,5%) o 'altro' (26%)"
                ),
            }
        try:
            rend_lordo = float(inv.get("rendimento_lordo_pct", 0.0))
            durata_raw = float(inv.get("durata_anni", 1))
        except (TypeError, ValueError):
            return {"errore": f"valori numerici non validi per investimento '{nome}'"}
        if not durata_raw.is_integer() or durata_raw < 1:
            return {"errore": f"durata_anni deve essere un intero >= 1 per investimento '{nome}'"}
        if rend_lordo <= -100:
            return {"errore": f"rendimento_lordo_pct deve essere maggiore di -100 per investimento '{nome}'"}
        durata = int(durata_raw)

        aliquota = _aliquota(tipo_tax)

        montante_lordo = importo * (1 + rend_lordo / 100) ** durata
        interessi_lordi = montante_lordo - importo
        # Art. 45 co. 1 TUIR: taxable income is the interest "percepiti"; art. 3 co. 1 D.L. 66/2014
        # and art. 2 co. 1 D.Lgs. 239/1996 tax it. No income, no tax and no refund.
        imposta = max(interessi_lordi, 0.0) * aliquota / 100
        montante_netto = montante_lordo - imposta
        rend_netto = rend_lordo * (1 - aliquota / 100) if rend_lordo > 0 else rend_lordo
        rend_netto_annualizzato = ((montante_netto / importo) ** (1 / durata) - 1) * 100

        risultati.append({
            "nome": nome,
            "rendimento_lordo_pct": rend_lordo,
            "aliquota_pct": aliquota,
            "rendimento_netto_pct": round(rend_netto, 4),
            "rendimento_netto_annualizzato_pct": round(rend_netto_annualizzato, 4),
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
        "nota": (
            "Confronto indicativo — imposta prelevata una volta a scadenza sugli interessi composti "
            "(per i titoli a cedola il montante è sovrastimato); classifica per rendimento netto annuo, "
            "che ignora la durata; non considera costi di gestione, inflazione o rischio"
        ),
    }
