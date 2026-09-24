"""Calcoli di diritto del lavoro: indennità licenziamento (D.Lgs. 23/2015 tutele crescenti),
preavviso per CCNL, NASpI (D.Lgs. 22/2015), scadenze impugnazione licenziamento,
costo del lavoro, offerta conciliativa."""

import json
from datetime import date, timedelta
from pathlib import Path

from src.lib import _clock
from src.server import mcp
from src.lib._data import sourced

_DATA = Path(__file__).parent.parent / "data"

with open(_DATA / "preavviso_ccnl.json") as _f:
    _PREAVVISO: dict = json.load(_f)

with open(_DATA / "irpef_scaglioni.json") as _f:
    _IRPEF: dict = json.load(_f)


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _add_days(d: date, giorni: int) -> date:
    return d + timedelta(days=giorni)


def _calcola_irpef_semplificata(imponibile: float) -> float:
    """Stima IRPEF lorda su imponibile annuo usando scaglioni vigenti."""
    scaglioni = _IRPEF.get("scaglioni_per_anno", {}).get(str(_clock.today().year), _IRPEF["scaglioni"])
    imposta = 0.0
    residuo = imponibile
    prev_limit = 0
    for s in scaglioni:
        aliquota = s["aliquota"] / 100
        limite = s.get("fino_a", float("inf"))
        base = min(residuo, limite - prev_limit)
        if base <= 0:
            break
        imposta += base * aliquota
        residuo -= base
        prev_limit = limite
    return round(imposta, 2)


@mcp.tool(tags={"lavoro"})
def indennita_licenziamento(
    anni_servizio: float,
    retribuzione_mensile: float,
    dimensione_azienda: str = "grande",
    tipo: str = "indennitario",
) -> dict:
    """Calcola l'indennità di licenziamento per tutele crescenti (D.Lgs. 23/2015).

    Applica le formule post C.Cost. 194/2018 (no più moltiplicatore fisso per anni)
    e C.Cost. 128/2024 / 118/2025 per le piccole imprese.
    Vigenza: D.Lgs. 23/2015 artt. 3, 9 — C.Cost. 194/2018, 128/2024, 118/2025.
    Precisione: INDICATIVO (dopo Corte cost. 194/2018 l'indennità non è commisurata automaticamente
        a due mensilità per anno: il giudice la determina tra il minimo e il massimo tenendo conto
        di anzianità, dimensioni dell'impresa e comportamento delle parti; il moltiplicatore per
        anzianità è solo un punto di partenza)
    Chaining: → offerta_conciliativa() per la formula agevolata art. 6 D.Lgs. 23/2015.

    Args:
        anni_servizio: Anni di servizio maturati (es. 3.5; valore > 0)
        retribuzione_mensile: Retribuzione mensile lorda in euro (es. 2000.00; valore > 0)
        dimensione_azienda: 'grande' (>15 dipendenti) o 'piccola' (≤15 dipendenti)
        tipo: 'indennitario' (art. 3 co. 1) o 'reintegra' (art. 3 co. 2 — calcola max risarcimento)
    """
    if anni_servizio <= 0:
        raise ValueError("anni_servizio deve essere > 0")
    if retribuzione_mensile <= 0:
        raise ValueError("retribuzione_mensile deve essere > 0")
    if dimensione_azienda not in ("grande", "piccola"):
        raise ValueError("dimensione_azienda deve essere 'grande' o 'piccola'")
    if tipo not in ("indennitario", "reintegra"):
        raise ValueError("tipo deve essere 'indennitario' o 'reintegra'")

    if tipo == "reintegra":
        mensilita = min(anni_servizio * 2, 12)
        floor_val = 0
        cap_val = 12
        formula = "min(anni_servizio × 2, 12) — risarcimento max in caso di reintegra"
        nota = "La reintegra è disposta dal giudice; questa è la stima del risarcimento massimo (retribuzioni perse)"
    elif dimensione_azienda == "grande":
        mensilita_raw = anni_servizio * 2
        floor_val = 6
        cap_val = 36
        mensilita = max(floor_val, min(mensilita_raw, cap_val))
        formula = f"anni_servizio ({anni_servizio}) × 2 = {round(mensilita_raw, 2)} → clamp [{floor_val}, {cap_val}]"
        nota = "Azienda con >15 dipendenti: regime ordinario D.Lgs. 23/2015 art. 3"
    else:
        mensilita_raw = anni_servizio * 1
        floor_val = 3
        cap_val = 18
        mensilita = max(floor_val, min(mensilita_raw, cap_val))
        formula = f"anni_servizio ({anni_servizio}) × 1 = {round(mensilita_raw, 2)} → clamp [{floor_val}, {cap_val}]"
        nota = "Azienda con ≤15 dipendenti: regime ridotto post C.Cost. 118/2025"

    importo = round(mensilita * retribuzione_mensile, 2)

    return {
        "anni_servizio": anni_servizio,
        "retribuzione_mensile": retribuzione_mensile,
        "tipo": tipo,
        "dimensione_azienda": dimensione_azienda,
        "mensilita": round(mensilita, 2),
        "importo": importo,
        "minimo_mensilita": floor_val,
        "massimo_mensilita": cap_val,
        "dettaglio_formula": formula,
        "nota": nota,
        "riferimento_normativo": "D.Lgs. 23/2015 artt. 3, 9 — C.Cost. 194/2018, 128/2024, 118/2025",
    }


@mcp.tool(tags={"lavoro"})
@sourced("preavviso_ccnl", alternativa="giorni_preavviso")
def indennita_preavviso(
    ccnl: str,
    livello: str,
    anzianita_anni: float,
    retribuzione_mensile: float,
    tipo: str = "licenziamento",
    giorni_preavviso: float | None = None,
) -> dict:
    """Calcola l'indennità sostitutiva del preavviso per CCNL principali.

    Supported CCNL: 'commercio', 'metalmeccanici', 'studi_professionali'.
    Il preavviso è dovuto in caso di recesso senza giusta causa; in mancanza si corrisponde
    l'indennità sostitutiva pari alla retribuzione del periodo.
    Vigenza: artt. 2118-2119 c.c. — CCNL di riferimento per il settore.
    Precisione: ESATTO per i periodi tabellari del CCNL indicato; verificare il CCNL aziendale applicato.

    Args:
        ccnl: Codice CCNL: 'commercio', 'metalmeccanici', 'studi_professionali'
        livello: Livello contrattuale (es. '2_3', 'quadri_1', 'A1_B2_B3', '3S_3')
        anzianita_anni: Anni di anzianità aziendale (es. 7.0; valore >= 0)
        retribuzione_mensile: Retribuzione mensile lorda in euro (es. 2000.00; valore > 0)
        tipo: Tipo di recesso: 'licenziamento' o 'dimissioni'
        giorni_preavviso: Giorni di preavviso che il CCNL applicabile prevede, se li conosci: al posto
                          della tabella inclusa, che i contratti rinnovano. Il calcolo dell'indennità
                          non dipende allora dalla tabella
    """
    if retribuzione_mensile <= 0:
        raise ValueError("retribuzione_mensile deve essere > 0")
    if anzianita_anni < 0:
        raise ValueError("anzianita_anni deve essere >= 0")
    if tipo not in ("licenziamento", "dimissioni"):
        raise ValueError("tipo deve essere 'licenziamento' o 'dimissioni'")

    if anzianita_anni <= 5:
        fascia = "fino_5"
    elif anzianita_anni <= 10:
        fascia = "5_10"
    else:
        fascia = "oltre_10"

    # The notice period is what the CCNL table provides, and it is the part that
    # goes stale: a caller who has the applicable contract in hand can supply it
    # and the calculation no longer rests on the bundled table at all (which is
    # why it is then never read, and its vintage never enters the answer).
    dal_chiamante = giorni_preavviso is not None
    if dal_chiamante:
        ccnl_data = {"nome": ccnl, "fonte": "giorni di preavviso forniti dal chiamante"}
    else:
        ccnl_data = _PREAVVISO["ccnl"].get(ccnl)
        if ccnl_data is None:
            ccnl_disponibili = list(_PREAVVISO["ccnl"].keys())
            raise ValueError(f"CCNL '{ccnl}' non trovato. Disponibili: {ccnl_disponibili}")

        tabella_tipo = ccnl_data[tipo]
        livello_data = tabella_tipo.get(livello)
        if livello_data is None:
            livelli_disponibili = list(tabella_tipo.keys())
            raise ValueError(f"Livello '{livello}' non trovato nel CCNL '{ccnl}' per '{tipo}'. Disponibili: {livelli_disponibili}")
        giorni_preavviso = livello_data[fascia]

    if giorni_preavviso < 0:
        raise ValueError("giorni_preavviso deve essere >= 0")
    retribuzione_giornaliera = round(retribuzione_mensile / 30, 4)
    importo = round(retribuzione_giornaliera * giorni_preavviso, 2)

    return {
        "ccnl": ccnl,
        "ccnl_nome": ccnl_data["nome"],
        "livello": livello,
        "anzianita_anni": anzianita_anni,
        "fascia_anzianita": fascia,
        "tipo": tipo,
        "giorni_preavviso": giorni_preavviso,
        "giorni_preavviso_fonte": "forniti dal chiamante" if dal_chiamante else "tabella CCNL inclusa",
        "retribuzione_giornaliera": retribuzione_giornaliera,
        "importo": importo,
        "riferimento_normativo": f"Artt. 2118-2119 c.c. — {ccnl_data['fonte']}",
    }


@mcp.tool(tags={"lavoro"})
def calcolo_naspi(
    retribuzione_media_mensile: float,
    settimane_contributive: int,
    eta_anni: int,
) -> dict:
    """Calcola l'importo e la durata della NASpI (indennità di disoccupazione).

    Applica la formula 2026 con soglia, massimale, durata proporzionale alle settimane
    contributive degli ultimi 4 anni e decalage mensile dal 6° mese (o 8° se età ≥ 55).
    Vigenza: D.Lgs. 22/2015 artt. 4-8 — Circ. INPS n. 4/2026.
    Precisione: INDICATIVO (il calcolo INPS considera le retribuzioni imponibili effettive dei 4 anni precedenti).
    Chaining: → scadenze_licenziamento() per le scadenze di impugnazione collegate al licenziamento.

    Args:
        retribuzione_media_mensile: Retribuzione media mensile imponibile previdenziale in euro (es. 2500.00; valore > 0)
        settimane_contributive: Settimane di contribuzione accreditate negli ultimi 4 anni (es. 104; valore > 0)
        eta_anni: Età del lavoratore in anni interi (influenza la soglia decalage)
    """
    if retribuzione_media_mensile <= 0:
        raise ValueError("retribuzione_media_mensile deve essere > 0")
    if settimane_contributive <= 0:
        raise ValueError("settimane_contributive deve essere > 0")

    # 2026 reference values
    soglia = 1456.72
    massimale = 1584.70

    if retribuzione_media_mensile <= soglia:
        naspi_base = 0.75 * retribuzione_media_mensile
    else:
        naspi_base = 0.75 * soglia + 0.25 * (retribuzione_media_mensile - soglia)

    naspi_base = min(naspi_base, massimale)
    naspi_base = round(naspi_base, 2)

    # Duration: weeks / 2, converted to months, capped at 24
    durata_mesi_raw = settimane_contributive / 2 / 4.33
    durata_mesi = min(round(durata_mesi_raw, 1), 24.0)
    durata_mesi_interi = int(durata_mesi) if durata_mesi == int(durata_mesi) else durata_mesi

    # Decalage starts from month 6 (or 8 if age >= 55)
    decalage_da_mese = 8 if eta_anni >= 55 else 6
    decalage_pct = 0.03  # 3% per month

    piano_mensile = []
    totale = 0.0
    importo_corrente = naspi_base
    n_mesi = int(durata_mesi) + (1 if durata_mesi > int(durata_mesi) else 0)

    for mese in range(1, n_mesi + 1):
        # Art. 4 co. 3 D.Lgs. 22/2015 (L. 234/2021): riduzione del 3% ogni mese a decorrere dal
        # primo giorno del sesto mese di fruizione (ottavo per chi ha compiuto 55 anni)
        if mese >= decalage_da_mese:
            importo_corrente = round(naspi_base * (1 - decalage_pct) ** (mese - decalage_da_mese + 1), 2)
            importo_corrente = max(importo_corrente, 0.0)

        # Last month may be partial
        if mese == n_mesi and durata_mesi != int(durata_mesi):
            frazione = durata_mesi - int(durata_mesi)
            contributo = round(importo_corrente * frazione, 2)
        else:
            contributo = importo_corrente

        totale += contributo
        piano_mensile.append({"mese": mese, "importo": contributo})

    totale = round(totale, 2)

    # Return first 6 + last entry for brevity
    piano_ridotto = piano_mensile[:6]
    if len(piano_mensile) > 6:
        piano_ridotto.append({"mese": piano_mensile[-1]["mese"], "importo": piano_mensile[-1]["importo"], "nota": "ultimo mese"})

    return {
        "retribuzione_media_mensile": retribuzione_media_mensile,
        "settimane_contributive": settimane_contributive,
        "eta_anni": eta_anni,
        "importo_mensile_iniziale": naspi_base,
        "soglia_2026": soglia,
        "massimale_2026": massimale,
        "durata_mesi": durata_mesi_interi,
        "decalage_da_mese": decalage_da_mese,
        "totale_stimato": totale,
        "piano_mensile": piano_ridotto,
        "riferimento_normativo": "D.Lgs. 22/2015 artt. 4-8 — Circ. INPS n. 4/2026",
    }


@mcp.tool(tags={"lavoro"})
def scadenze_licenziamento(
    data_licenziamento: str,
    data_impugnazione: str | None = None,
    data_rifiuto_conciliazione: str | None = None,
) -> dict:
    """Calcola le scadenze perentorie per l'impugnazione del licenziamento.

    I termini di impugnazione sono perentori e si calcolano in giorni di calendario.
    Il mancato rispetto del termine di 60 giorni per l'impugnazione stragiudiziale
    determina la decadenza dall'azione, non sanabile.
    Vigenza: art. 6 L. 604/1966 nel testo dell'art. 32 L. 183/2010 e dell'art. 1 co. 38 L. 92/2012
    (60 giorni per l'impugnazione stragiudiziale; 180 giorni dall'impugnazione per il deposito del
    ricorso o per la richiesta di conciliazione/arbitrato; 60 giorni dal rifiuto o dal mancato
    accordo). Il rito speciale "Fornero" (art. 1 co. 47 ss. L. 92/2012) è stato abrogato dal
    D.Lgs. 149/2022 per i giudizi introdotti dal 28/02/2023.
    Precisione: ESATTO per il computo dei termini di calendario (senza sospensione feriale, che non
    si applica alle cause di lavoro ex art. 3 L. 742/1969); il termine di 180 giorni decorre
    dall'impugnazione effettiva, passare `data_impugnazione` per il calcolo esatto.

    Args:
        data_licenziamento: Data di ricezione della comunicazione di licenziamento (formato YYYY-MM-DD)
        data_impugnazione: Data in cui l'impugnazione stragiudiziale è stata inviata (YYYY-MM-DD);
                           se assente il deposito è calcolato dall'ultimo giorno utile (60° giorno)
        data_rifiuto_conciliazione: Data del rifiuto o del mancato accordo sulla conciliazione o
                           arbitrato richiesti (YYYY-MM-DD), per il termine residuo di 60 giorni
    """
    try:
        dt_lic = _parse_date(data_licenziamento)
    except ValueError:
        raise ValueError("data_licenziamento deve essere in formato YYYY-MM-DD")
    for nome, valore in (("data_impugnazione", data_impugnazione), ("data_rifiuto_conciliazione", data_rifiuto_conciliazione)):
        if valore is not None:
            try:
                _parse_date(valore)
            except ValueError:
                raise ValueError(f"{nome} deve essere in formato YYYY-MM-DD")

    dt_impugnazione = _add_days(dt_lic, 60)
    dt_impugnazione_effettiva = _parse_date(data_impugnazione) if data_impugnazione else dt_impugnazione
    dt_deposito = _add_days(dt_impugnazione_effettiva, 180)

    oggi = _clock.today()

    def _stato(dt: date) -> str:
        delta = (dt - oggi).days
        if delta < 0:
            return f"SCADUTA ({abs(delta)} giorni fa)"
        if delta == 0:
            return "SCADE OGGI"
        if delta <= 7:
            return f"URGENTE — scade tra {delta} giorni"
        return f"scade tra {delta} giorni"

    avvertimenti = []
    if (dt_impugnazione - oggi).days <= 14 and oggi <= dt_impugnazione:
        avvertimenti.append("URGENTE: termine impugnazione stragiudiziale in scadenza imminente")
    if oggi > dt_deposito:
        avvertimenti.append("ATTENZIONE: termine per il deposito del ricorso già scaduto")
    if data_impugnazione and dt_impugnazione_effettiva > dt_impugnazione:
        avvertimenti.append("ATTENZIONE: l'impugnazione risulta inviata oltre i 60 giorni dalla comunicazione del licenziamento (decadenza)")

    scadenze = {
        "impugnazione_stragiudiziale": {
            "data": dt_impugnazione.isoformat(),
            "termine_giorni": 60,
            "stato": _stato(dt_impugnazione),
            "descrizione": "Comunicazione scritta di impugnazione (raccomandata/PEC) entro 60 giorni dalla ricezione del licenziamento — art. 6 co. 1 L. 604/1966",
        },
        "deposito_ricorso": {
            "data": dt_deposito.isoformat(),
            "termine_giorni": 180,
            "decorre_da": data_impugnazione or f"ultimo giorno utile per l'impugnazione ({dt_impugnazione.isoformat()})",
            "stato": _stato(dt_deposito),
            "descrizione": "Deposito del ricorso al giudice del lavoro, o comunicazione della richiesta di conciliazione/arbitrato, entro 180 giorni dall'impugnazione — art. 6 co. 2 L. 604/1966",
        },
    }
    if data_rifiuto_conciliazione:
        dt_post = _add_days(_parse_date(data_rifiuto_conciliazione), 60)
        scadenze["post_conciliazione"] = {
            "data": dt_post.isoformat(),
            "termine_giorni": 60,
            "decorre_da": data_rifiuto_conciliazione,
            "stato": _stato(dt_post),
            "descrizione": "Deposito del ricorso entro 60 giorni dal rifiuto o dal mancato accordo sulla conciliazione o arbitrato — art. 6 co. 2 L. 604/1966",
        }
    else:
        scadenze["post_conciliazione"] = {
            "data": None,
            "termine_giorni": 60,
            "decorre_da": "rifiuto o mancato accordo sulla conciliazione o arbitrato (passare data_rifiuto_conciliazione)",
            "descrizione": "Se la conciliazione o l'arbitrato richiesti sono rifiutati o non si raggiunge l'accordo, il ricorso va depositato entro 60 giorni — art. 6 co. 2 L. 604/1966",
        }

    return {
        "data_licenziamento": data_licenziamento,
        "scadenze": scadenze,
        "avvertimenti": avvertimenti,
        "nota": (
            "I termini sono perentori e di calendario; la sospensione feriale non si applica alle "
            "controversie di lavoro (art. 3 L. 742/1969). I 180 giorni decorrono dalla data in cui "
            "l'impugnazione è stata inviata: senza `data_impugnazione` il calcolo assume l'ultimo giorno utile."
        ),
        "riferimento_normativo": "Art. 6 L. 604/1966 (testo ex art. 32 L. 183/2010 e art. 1 co. 38 L. 92/2012)",
    }


@mcp.tool(tags={"lavoro"})
@sourced("irpef_scaglioni")
def costo_lavoro(
    retribuzione_lorda_annua: float,
    tipo_contratto: str = "dipendente",
) -> dict:
    """Stima il costo totale del lavoro per l'azienda e il netto per il dipendente.

    Calcolo semplificato con aliquote medie di riferimento. Le aliquote variano per
    settore INAIL, dimensione aziendale, regione (IRAP), anzianità e agevolazioni.
    Vigenza: D.P.R. 917/1986 (IRPEF) — L. 153/1969 (contributi) — D.Lgs. 446/1997 (IRAP).
    Precisione: INDICATIVO (aliquote contributive medie; l'IRAP sul costo del personale a tempo
        indeterminato è deducibile dal 2015, art. 11 co. 4-octies D.Lgs. 446/1997; verificare le
        aliquote del CCNL e dell'INPS applicabili)
    Chaining: → calcolo_naspi() per la stima NASpI in caso di licenziamento.

    Args:
        retribuzione_lorda_annua: Retribuzione lorda annua in euro (es. 30000.0; valore > 0)
        tipo_contratto: 'dipendente' (standard), 'apprendista' (contributi ridotti), 'dirigente' (INPDAI)
    """
    if retribuzione_lorda_annua <= 0:
        raise ValueError("retribuzione_lorda_annua deve essere > 0")
    if tipo_contratto not in ("dipendente", "apprendista", "dirigente"):
        raise ValueError("tipo_contratto deve essere 'dipendente', 'apprendista' o 'dirigente'")

    lordo = retribuzione_lorda_annua

    # Employee INPS contributions
    if tipo_contratto == "dirigente":
        aliq_dip = 0.0919  # INPDAI base (aliquota simile IVS)
        aliq_datore = 0.2390  # INPSDAI + INAIL dirigenti
        nota_contrib = "Aliquote dirigenti INPDAI — verificare con consulente"
    elif tipo_contratto == "apprendista":
        aliq_dip = 0.0519  # ridotta per apprendisti
        aliq_datore = 0.1161  # ridotta per aziende < 9 dip (media indicativa)
        nota_contrib = "Aliquote apprendisti ridotte — variano per dimensione aziendale e anno di apprendistato"
    else:
        aliq_dip = 0.0919
        aliq_datore = 0.3000  # IVS + CIGS + malattia + maternità + INAIL medio
        nota_contrib = "Aliquote medie dipendente ordinario — variano per settore e dimensione"

    contributi_dip = round(lordo * aliq_dip, 2)
    imponibile_irpef = lordo - contributi_dip

    irpef_lorda = _calcola_irpef_semplificata(imponibile_irpef)
    # Detrazioni da lavoro dipendente stimate (semplificazione)
    if imponibile_irpef <= 15000:
        detrazione_lavoro = 1955.0
    elif imponibile_irpef <= 28000:
        detrazione_lavoro = round(1910 + 1190 * (28000 - imponibile_irpef) / 13000, 2)
    elif imponibile_irpef <= 50000:
        detrazione_lavoro = round(1910 * (50000 - imponibile_irpef) / 22000, 2)
    else:
        detrazione_lavoro = 0.0
    irpef_netta = max(0.0, round(irpef_lorda - detrazione_lavoro, 2))

    netto = round(lordo - contributi_dip - irpef_netta, 2)

    # Employer cost
    contributi_datore = round(lordo * aliq_datore, 2)
    tfr = round(lordo * 0.0691, 2)  # 6.91% TFR (art. 2120 c.c.)
    irap = round(lordo * 0.039, 2)  # IRAP media 3.9% su costo lavoro
    costo_totale = round(lordo + contributi_datore + tfr + irap, 2)

    cuneo_fiscale = round((costo_totale - netto) / costo_totale * 100, 1) if costo_totale > 0 else 0.0

    return {
        "tipo_contratto": tipo_contratto,
        "lordo_annuo": lordo,
        "contributi_dipendente": contributi_dip,
        "aliquota_contributi_dipendente_pct": round(aliq_dip * 100, 2),
        "imponibile_irpef": round(imponibile_irpef, 2),
        "irpef_stimata": irpef_netta,
        "netto_stimato": netto,
        "contributi_datore": contributi_datore,
        "aliquota_contributi_datore_pct": round(aliq_datore * 100, 2),
        "tfr_annuo": tfr,
        "irap_stimata": irap,
        "costo_azienda_totale": costo_totale,
        "cuneo_fiscale_pct": cuneo_fiscale,
        "nota": nota_contrib,
        "avvertimento": "INDICATIVO — le aliquote variano per settore INAIL, dimensione, regione e agevolazioni. Verificare con consulente del lavoro.",
        "riferimento_normativo": "D.P.R. 917/1986 (IRPEF) — L. 153/1969 (contributi) — D.Lgs. 446/1997 (IRAP) — Art. 2120 c.c. (TFR)",
    }


@mcp.tool(tags={"lavoro"})
def offerta_conciliativa(
    anni_servizio: float,
    retribuzione_mensile: float,
    dimensione_azienda: str = "grande",
) -> dict:
    """Calcola l'offerta conciliativa esente da IRPEF e contributi (art. 6 D.Lgs. 23/2015).

    L'offerta conciliativa è uno strumento deflativo del contenzioso: se accettata dal
    lavoratore estingue il rapporto e l'impugnazione. L'importo è completamente detassato
    (non soggetto a IRPEF né a contributi previdenziali).
    Vigenza: D.Lgs. 23/2015 art. 6.
    Precisione: ESATTO per la formula legale (1 mensilità/anno per le aziende grandi, 0,5 mensilità/anno per le piccole, nei limiti floor/cap).
    Chaining: → indennita_licenziamento() per confronto con indennità giudiziale standard.

    Args:
        anni_servizio: Anni di servizio maturati (es. 5.0; valore > 0)
        retribuzione_mensile: Retribuzione mensile lorda in euro (es. 2000.00; valore > 0)
        dimensione_azienda: 'grande' (>15 dipendenti) o 'piccola' (≤15 dipendenti)
    """
    if anni_servizio <= 0:
        raise ValueError("anni_servizio deve essere > 0")
    if retribuzione_mensile <= 0:
        raise ValueError("retribuzione_mensile deve essere > 0")
    if dimensione_azienda not in ("grande", "piccola"):
        raise ValueError("dimensione_azienda deve essere 'grande' o 'piccola'")

    if dimensione_azienda == "grande":
        floor_val = 3.0
        cap_val = 27.0
        mensilita = max(floor_val, min(anni_servizio, cap_val))
    else:
        floor_val = 1.5
        # Il tetto di 6 mensilità (art. 9 c.1 D.Lgs. 23/2015, richiamato anche per l'art. 6)
        # è stato dichiarato illegittimo da Corte Cost. 118/2025; ricostruito come 27/2.
        # Il dimezzamento (×0,5) NON è stato toccato dalla Corte e resta in vigore.
        cap_val = 13.5
        mensilita = max(floor_val, min(anni_servizio * 0.5, cap_val))
    importo = round(mensilita * retribuzione_mensile, 2)

    return {
        "anni_servizio": anni_servizio,
        "retribuzione_mensile": retribuzione_mensile,
        "dimensione_azienda": dimensione_azienda,
        "mensilita": mensilita,
        "floor_mensilita": floor_val,
        "cap_mensilita": cap_val,
        "importo": importo,
        "detassato": True,
        "nota": "Importo esente da IRPEF e da contributi previdenziali se accettato in sede conciliativa (art. 6 D.Lgs. 23/2015). Piccole imprese: dimezzamento ex art. 9 c.1 ancora vigente; tetto di 6 mensilità abrogato da Corte Cost. 118/2025 (la formula agevolata è ricostruita con cap 13,5; il datore può comunque offrire di più).",
        "confronto_giudiziale": "Indennità giudiziale standard: 2 mensilità/anno (floor 6, cap 36 per aziende grandi) — usare indennita_licenziamento() per il confronto",
        "riferimento_normativo": "D.Lgs. 23/2015 artt. 6, 9 — Corte Cost. 118/2025",
    }
