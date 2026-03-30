"""Calcoli di diritto del lavoro: indennità licenziamento (D.Lgs. 23/2015 tutele crescenti),
preavviso per CCNL, NASpI (D.Lgs. 22/2015), scadenze impugnazione licenziamento,
costo del lavoro, offerta conciliativa."""

import json
from datetime import date, timedelta
from pathlib import Path

from src.server import mcp

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
    scaglioni = _IRPEF.get("scaglioni_per_anno", {}).get("2026", _IRPEF["scaglioni"])
    imposta = 0.0
    for s in scaglioni:
        limite_inf = s.get("da", 0)
        limite_sup = s.get("a")
        aliquota = s["aliquota"] / 100
        if imponibile <= limite_inf:
            break
        tetto = min(imponibile, limite_sup) if limite_sup else imponibile
        imposta += (tetto - limite_inf) * aliquota
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
    Precisione: INDICATIVO (il giudice può discostarsi nei limiti floor/cap in base a criteri art. 8 L. 604/1966).
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
        mensilita_raw = anni_servizio * 2
        floor_val = 3
        cap_val = 18
        mensilita = max(floor_val, min(mensilita_raw, cap_val))
        formula = f"anni_servizio ({anni_servizio}) × 2 = {round(mensilita_raw, 2)} → clamp [{floor_val}, {cap_val}]"
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
def indennita_preavviso(
    ccnl: str,
    livello: str,
    anzianita_anni: float,
    retribuzione_mensile: float,
    tipo: str = "licenziamento",
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
    """
    if retribuzione_mensile <= 0:
        raise ValueError("retribuzione_mensile deve essere > 0")
    if anzianita_anni < 0:
        raise ValueError("anzianita_anni deve essere >= 0")
    if tipo not in ("licenziamento", "dimissioni"):
        raise ValueError("tipo deve essere 'licenziamento' o 'dimissioni'")

    ccnl_data = _PREAVVISO["ccnl"].get(ccnl)
    if ccnl_data is None:
        ccnl_disponibili = list(_PREAVVISO["ccnl"].keys())
        raise ValueError(f"CCNL '{ccnl}' non trovato. Disponibili: {ccnl_disponibili}")

    tabella_tipo = ccnl_data[tipo]
    livello_data = tabella_tipo.get(livello)
    if livello_data is None:
        livelli_disponibili = list(tabella_tipo.keys())
        raise ValueError(f"Livello '{livello}' non trovato nel CCNL '{ccnl}' per '{tipo}'. Disponibili: {livelli_disponibili}")

    if anzianita_anni <= 5:
        fascia = "fino_5"
    elif anzianita_anni <= 10:
        fascia = "5_10"
    else:
        fascia = "oltre_10"

    giorni_preavviso = livello_data[fascia]
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
    Vigenza: D.Lgs. 22/2015 artt. 4-8 — Circ. INPS 16/2026.
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
        if mese > decalage_da_mese:
            riduzioni = mese - decalage_da_mese
            importo_corrente = round(naspi_base * (1 - decalage_pct * riduzioni), 2)
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
        "riferimento_normativo": "D.Lgs. 22/2015 artt. 4-8 — Circ. INPS 16/2026",
    }


@mcp.tool(tags={"lavoro"})
def scadenze_licenziamento(
    data_licenziamento: str,
) -> dict:
    """Calcola le scadenze perentorie per l'impugnazione del licenziamento.

    I termini di impugnazione sono perentori e si calcolano in giorni di calendario.
    Il mancato rispetto del termine di 60 giorni per l'impugnazione stragiudiziale
    determina la decadenza dall'azione, non sanabile.
    Vigenza: L. 604/1966 art. 6 (60 gg impugnazione) — L. 183/2010 art. 32 (180 gg deposito ricorso).
    Precisione: ESATTO per il computo dei termini di calendario; verificare festività e sospensioni feriali.

    Args:
        data_licenziamento: Data di efficacia del licenziamento (formato YYYY-MM-DD)
    """
    dt_lic = _parse_date(data_licenziamento)

    dt_impugnazione = _add_days(dt_lic, 60)
    dt_deposito = _add_days(dt_impugnazione, 180)
    dt_post_conciliazione = _add_days(dt_deposito, 60)

    oggi = date.today()

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

    return {
        "data_licenziamento": data_licenziamento,
        "scadenze": {
            "impugnazione_stragiudiziale": {
                "data": dt_impugnazione.isoformat(),
                "termine_giorni": 60,
                "stato": _stato(dt_impugnazione),
                "descrizione": "Comunicazione scritta di impugnazione (raccomandata/PEC) — art. 6 co. 1 L. 604/1966",
            },
            "deposito_ricorso": {
                "data": dt_deposito.isoformat(),
                "termine_giorni": 180,
                "decorre_da": "impugnazione stragiudiziale",
                "stato": _stato(dt_deposito),
                "descrizione": "Deposito ricorso in Tribunale (rito Fornero) — art. 6 co. 2 L. 604/1966",
            },
            "post_conciliazione": {
                "data": dt_post_conciliazione.isoformat(),
                "termine_giorni": 60,
                "decorre_da": "deposito ricorso",
                "stato": _stato(dt_post_conciliazione),
                "descrizione": "Termine residuo in caso di tentativo di conciliazione — art. 32 L. 183/2010",
            },
        },
        "avvertimenti": avvertimenti,
        "nota": "I termini sono perentori e di calendario. La sospensione feriale (1-31 agosto) non si applica ai procedimenti con rito urgente Fornero.",
        "riferimento_normativo": "L. 604/1966 art. 6 — L. 183/2010 art. 32",
    }


@mcp.tool(tags={"lavoro"})
def costo_lavoro(
    retribuzione_lorda_annua: float,
    tipo_contratto: str = "dipendente",
) -> dict:
    """Stima il costo totale del lavoro per l'azienda e il netto per il dipendente.

    Calcolo semplificato con aliquote medie di riferimento. Le aliquote variano per
    settore INAIL, dimensione aziendale, regione (IRAP), anzianità e agevolazioni.
    Vigenza: D.P.R. 917/1986 (IRPEF) — L. 153/1969 (contributi) — D.Lgs. 446/1997 (IRAP).
    Precisione: INDICATIVO — usare per stime preliminari; il calcolo esatto richiede verifica con consulente del lavoro.
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
    Precisione: ESATTO per la formula legale (1 mensilità/anno nei limiti floor/cap).
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
    else:
        floor_val = 1.5
        cap_val = 13.5

    mensilita = max(floor_val, min(anni_servizio, cap_val))
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
        "nota": "Importo esente da IRPEF e da contributi previdenziali se accettato in sede conciliativa (art. 6 D.Lgs. 23/2015)",
        "confronto_giudiziale": "Indennità giudiziale standard: 2 mensilità/anno (floor 6, cap 36 per aziende grandi) — usare indennita_licenziamento() per il confronto",
        "riferimento_normativo": "D.Lgs. 23/2015 art. 6",
    }
