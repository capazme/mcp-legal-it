"""Calcolo parcelle e fatture per professionisti non avvocati: CTU/periti (DPR 115/2002),
mediazione civile (DM 150/2023), Enasarco, curatore fallimentare (DM 30/2012)."""

import math

from src.server import mcp

# Rivalsa INPS per tipo professionista
_RIVALSA_INPS = {
    "ingegnere": 4.0,
    "architetto": 4.0,
    "geometra": 4.0,
    "commercialista": 4.0,
    "consulente_lavoro": 4.0,
    "psicologo": 5.0,
    "medico": 4.0,
}

# Scaglioni indennità mediazione DM 150/2023 (per ciascuna parte)
_SCAGLIONI_MEDIAZIONE = [
    (1_000, 60, 120),
    (5_000, 100, 200),
    (10_000, 170, 340),
    (25_000, 240, 480),
    (50_000, 360, 720),
    (250_000, 530, 1_060),
    (500_000, 880, 1_760),
    (2_500_000, 1_250, 2_500),
    (5_000_000, 2_000, 4_000),
    (float("inf"), 2_800, 5_600),
]

# Compensi CTU indicativi (min, max) per tipo incarico
_COMPENSI_CTU = {
    "perizia_immobiliare": {
        "pct_valore": (0.5, 2.0),
        "orario": (80, 150),
        "descrizione": "Perizia estimativa immobiliare",
    },
    "perizia_contabile": {
        "pct_valore": (1.0, 3.0),
        "orario": (70, 130),
        "descrizione": "Perizia contabile / societaria",
    },
    "perizia_medica": {
        "pct_valore": (0.5, 2.5),
        "orario": (100, 200),
        "descrizione": "Consulenza tecnica medico-legale",
    },
    "stima_danni": {
        "pct_valore": (1.0, 3.0),
        "orario": (80, 150),
        "descrizione": "Stima e quantificazione danni",
    },
    "accertamenti_tecnici": {
        "pct_valore": (1.0, 2.5),
        "orario": (80, 140),
        "descrizione": "Accertamenti tecnici preventivi ex art. 696 c.p.c.",
    },
}


@mcp.tool()
def fattura_professionista(
    imponibile: float,
    tipo: str = "ingegnere",
    regime: str = "ordinario",
) -> dict:
    """Calcola fattura per professionista (non avvocato) con rivalsa INPS, IVA e ritenuta d'acconto.
    Vigenza: DPR 633/1972 (IVA); DPR 600/1973 art. 25 (ritenuta); L. 190/2014 (forfettario).
    Precisione: ESATTO (aliquote di legge: rivalsa INPS 4-5%, IVA 22%, ritenuta 20%).

    Args:
        imponibile: Compenso professionale in euro (€, imponibile)
        tipo: Tipo professionista: 'ingegnere', 'architetto', 'geometra', 'commercialista', 'consulente_lavoro', 'psicologo', 'medico'
        regime: Regime fiscale: 'ordinario' (IVA 22% + ritenuta 20%) o 'forfettario' (no IVA, no ritenuta, bollo se >77.47€)
    """
    if tipo not in _RIVALSA_INPS:
        return {"errore": f"Tipo professionista non valido. Valori: {list(_RIVALSA_INPS.keys())}"}
    if regime not in ("ordinario", "forfettario"):
        return {"errore": "Regime deve essere 'ordinario' o 'forfettario'"}

    aliquota_rivalsa = _RIVALSA_INPS[tipo]
    rivalsa = round(imponibile * aliquota_rivalsa / 100, 2)
    base_imponibile_iva = round(imponibile + rivalsa, 2)

    voci = [
        {"voce": "Compenso professionale", "importo": imponibile},
        {"voce": f"Rivalsa INPS {aliquota_rivalsa}%", "importo": rivalsa},
    ]

    if regime == "ordinario":
        iva = round(base_imponibile_iva * 22 / 100, 2)
        ritenuta = round(imponibile * 20 / 100, 2)
        totale = round(base_imponibile_iva + iva - ritenuta, 2)

        voci.append({"voce": "IVA 22%", "importo": iva})
        voci.append({"voce": "Ritenuta d'acconto 20% (-)", "importo": -ritenuta})

        return {
            "tipo_professionista": tipo,
            "regime": regime,
            "imponibile": imponibile,
            "rivalsa_inps": rivalsa,
            "base_imponibile_iva": base_imponibile_iva,
            "iva": iva,
            "ritenuta_acconto": ritenuta,
            "totale_fattura": round(base_imponibile_iva + iva, 2),
            "netto_a_pagare": totale,
            "voci": voci,
            "nota": "Il committente versa la ritenuta d'acconto con F24 (codice tributo 1040)",
        }
    else:
        # Forfettario: no IVA, no ritenuta, bollo €2 se importo > 77.47
        bollo = 2.0 if base_imponibile_iva > 77.47 else 0.0
        totale = round(base_imponibile_iva + bollo, 2)

        if bollo > 0:
            voci.append({"voce": "Imposta di bollo", "importo": bollo})

        return {
            "tipo_professionista": tipo,
            "regime": regime,
            "imponibile": imponibile,
            "rivalsa_inps": rivalsa,
            "base_imponibile": base_imponibile_iva,
            "iva": 0.0,
            "ritenuta_acconto": 0.0,
            "bollo": bollo,
            "totale_fattura": totale,
            "netto_a_pagare": totale,
            "voci": voci,
            "nota": "Regime forfettario: operazione senza IVA ex art. 1 co. 54-89 L. 190/2014, non soggetta a ritenuta",
        }


@mcp.tool()
def compenso_ctu(
    tipo_incarico: str,
    valore_causa: float | None = None,
    ore_lavoro: float | None = None,
) -> dict:
    """Calcola compenso indicativo del consulente tecnico d'ufficio (CTU) nominato dal giudice.
    Vigenza: DPR 115/2002 — DM 30/05/2002 — il giudice liquida il compenso definitivo.
    Precisione: INDICATIVO (range min-max orientativo; il giudice può discostarsene).

    Args:
        tipo_incarico: Tipo incarico: 'perizia_immobiliare', 'perizia_contabile', 'perizia_medica', 'stima_danni', 'accertamenti_tecnici'
        valore_causa: Valore della causa in euro (€, opzionale — per calcolo a percentuale)
        ore_lavoro: Ore di lavoro effettive (opzionale — per calcolo a tariffa oraria)
    """
    if tipo_incarico not in _COMPENSI_CTU:
        return {"errore": f"Tipo incarico non valido. Valori: {list(_COMPENSI_CTU.keys())}"}
    if valore_causa is None and ore_lavoro is None:
        return {"errore": "Specificare almeno valore_causa o ore_lavoro"}

    info = _COMPENSI_CTU[tipo_incarico]
    risultato = {
        "tipo_incarico": tipo_incarico,
        "descrizione": info["descrizione"],
    }

    if valore_causa is not None:
        pct_min, pct_max = info["pct_valore"]
        comp_min = round(valore_causa * pct_min / 100, 2)
        comp_max = round(valore_causa * pct_max / 100, 2)
        risultato["calcolo_a_percentuale"] = {
            "valore_causa": valore_causa,
            "percentuale_min": pct_min,
            "percentuale_max": pct_max,
            "compenso_min": comp_min,
            "compenso_max": comp_max,
        }

    if ore_lavoro is not None:
        orario_min, orario_max = info["orario"]
        comp_min = round(ore_lavoro * orario_min, 2)
        comp_max = round(ore_lavoro * orario_max, 2)
        risultato["calcolo_orario"] = {
            "ore_lavoro": ore_lavoro,
            "tariffa_oraria_min": orario_min,
            "tariffa_oraria_max": orario_max,
            "compenso_min": comp_min,
            "compenso_max": comp_max,
        }

    risultato["note"] = [
        "Compensi indicativi — il giudice liquida secondo DPR 115/2002 e DM 30/05/2002",
        "Al compenso si aggiungono spese vive, IVA e CPA 4%",
        "Il CTU può chiedere anticipo spese ex art. 146 DPR 115/2002",
    ]
    risultato["riferimento_normativo"] = "DPR 115/2002 — DM 30/05/2002"
    return risultato


@mcp.tool()
def spese_mediazione(
    valore_controversia: float,
    esito: str = "positivo",
) -> dict:
    """Calcola indennità di mediazione civile e commerciale per scaglione di valore.
    Vigenza: DM 150/2023 — D.Lgs. 28/2010 (Riforma Cartabia).
    Precisione: ESATTO (importi tabellari ministeriali).

    Args:
        valore_controversia: Valore della controversia in euro (€)
        esito: Esito della mediazione: 'positivo' (accordo raggiunto) o 'negativo' (mancato accordo)
    """
    if esito not in ("positivo", "negativo"):
        return {"errore": "Esito deve essere 'positivo' o 'negativo'"}

    # Find scaglione
    for soglia, ind_negativo, ind_positivo in _SCAGLIONI_MEDIAZIONE:
        if valore_controversia <= soglia:
            indennita_base = ind_positivo if esito == "positivo" else ind_negativo
            break

    # Con esito negativo: riduzione di un terzo dopo primo incontro
    indennita_per_parte = indennita_base
    riduzione = None
    if esito == "negativo":
        riduzione = round(indennita_base / 3, 2)
        indennita_ridotta = round(indennita_base - riduzione, 2)

    iva_per_parte = round(indennita_per_parte * 22 / 100, 2)
    totale_per_parte = round(indennita_per_parte + iva_per_parte, 2)
    totale_organismo = round(totale_per_parte * 2, 2)

    risultato = {
        "valore_controversia": valore_controversia,
        "esito": esito,
        "indennita_per_parte": indennita_per_parte,
        "iva_22_per_parte": iva_per_parte,
        "totale_per_parte": totale_per_parte,
        "totale_organismo_2_parti": totale_organismo,
    }

    if esito == "negativo":
        risultato["nota_riduzione"] = (
            f"Dopo il primo incontro informativo senza accordo, l'indennità può ridursi di 1/3 "
            f"(riduzione: €{riduzione}, indennità ridotta: €{indennita_ridotta})"
        )

    risultato["agevolazioni"] = [
        "Credito d'imposta fino a €600 per ciascuna parte in caso di accordo (art. 20 D.Lgs. 28/2010)",
        "Esenzione imposta di registro fino a €100.000 per accordi di mediazione",
        "Gratuito patrocinio: le parti ammesse non pagano indennità",
    ]
    risultato["riferimento_normativo"] = "DM 150/2023 — D.Lgs. 28/2010 (Riforma Cartabia)"
    return risultato


@mcp.tool()
def compenso_orario(
    tariffa_oraria: float,
    ore: int,
    minuti: int = 0,
    arrotondamento: str = "mezz_ora",
) -> dict:
    """Calcola compenso professionale a ore con arrotondamento per eccesso all'unità scelta.
    Precisione: ESATTO (dato un importo orario e un tempo, il calcolo è matematicamente preciso).

    Args:
        tariffa_oraria: Tariffa oraria in euro (€/ora)
        ore: Numero di ore lavorate (intero non negativo)
        minuti: Minuti aggiuntivi (0-59)
        arrotondamento: Tipo arrotondamento per eccesso: 'quarto_ora' (15 min), 'mezz_ora' (30 min), 'ora' (60 min)
    """
    if arrotondamento not in ("quarto_ora", "mezz_ora", "ora"):
        return {"errore": "Arrotondamento deve essere 'quarto_ora', 'mezz_ora' o 'ora'"}
    if not 0 <= minuti <= 59:
        return {"errore": "Minuti deve essere tra 0 e 59"}

    totale_minuti = ore * 60 + minuti

    unita = {"quarto_ora": 15, "mezz_ora": 30, "ora": 60}[arrotondamento]
    # Round up to next unit
    minuti_arrotondati = math.ceil(totale_minuti / unita) * unita
    ore_arrotondate = minuti_arrotondati / 60

    compenso = round(tariffa_oraria * ore_arrotondate, 2)

    return {
        "tariffa_oraria": tariffa_oraria,
        "tempo_effettivo": f"{ore}h {minuti}min",
        "tempo_effettivo_minuti": totale_minuti,
        "arrotondamento": arrotondamento,
        "tempo_arrotondato": f"{int(minuti_arrotondati // 60)}h {int(minuti_arrotondati % 60)}min",
        "tempo_arrotondato_ore": ore_arrotondate,
        "compenso": compenso,
        "nota": f"Arrotondamento per eccesso a {unita} minuti",
    }


@mcp.tool()
def ritenuta_acconto(
    compenso_lordo: float,
    aliquota: float = 20.0,
) -> dict:
    """Calcola ritenuta d'acconto su compensi professionali e mostra i campi per la Certificazione Unica.
    Vigenza: Art. 25 DPR 600/1973.
    Precisione: ESATTO (calcolo matematico su aliquota fornita).

    Args:
        compenso_lordo: Compenso lordo in euro (€, base imponibile per la ritenuta)
        aliquota: Aliquota ritenuta in percentuale (default 20%; range tipico: 20.0-30.0)
    """
    ritenuta = round(compenso_lordo * aliquota / 100, 2)
    netto = round(compenso_lordo - ritenuta, 2)

    return {
        "compenso_lordo": compenso_lordo,
        "aliquota_ritenuta_pct": aliquota,
        "ritenuta": ritenuta,
        "netto_percepito": netto,
        "certificazione_unica": {
            "punto_4_compensi": compenso_lordo,
            "punto_8_ritenute": ritenuta,
            "punto_9_netto": netto,
            "codice_tributo_f24": "1040",
            "periodo_versamento": "Entro il 16 del mese successivo al pagamento",
        },
        "nota": (
            "Il committente (sostituto d'imposta) trattiene la ritenuta e la versa con F24. "
            "Rilascia la CU entro il 16/03 dell'anno successivo."
        ),
        "riferimento_normativo": "Art. 25 DPR 600/1973",
    }


# Scaglioni compenso curatore fallimentare DM 30/2012
_SCAGLIONI_CURATORE = [
    (16_227.08, 14.0),
    (24_340.62, 10.5),
    (40_567.68, 7.0),
    (81_131.36, 4.75),
    (162_262.72, 2.8),
    (float("inf"), 1.5),
]
_CURATORE_MIN = 811.31
_CURATORE_MAX = 405_656.80


@mcp.tool()
def compenso_curatore_fallimentare(
    attivo_realizzato: float,
    passivo_accertato: float,
) -> dict:
    """Calcola compenso del curatore fallimentare su scaglioni progressivi.
    Vigenza: DM 30/2012 — compenso minimo €811,31 e massimo €405.656,80.
    Precisione: ESATTO (scaglioni percentuali tabellari DM 30/2012).

    Args:
        attivo_realizzato: Attivo realizzato dalla procedura in euro (€)
        passivo_accertato: Passivo accertato in euro (€, usato a metà aliquota)
    """
    # Calcolo su attivo realizzato (scaglioni progressivi)
    def _calcola_scaglioni(importo: float, scaglioni: list, moltiplicatore: float = 1.0) -> list:
        dettaglio = []
        residuo = importo
        precedente = 0.0
        for soglia, pct in scaglioni:
            fascia = min(residuo, soglia - precedente)
            if fascia <= 0:
                break
            compenso = round(fascia * pct * moltiplicatore / 100, 2)
            dettaglio.append({
                "fascia": f"€{precedente:,.2f} - €{min(soglia, precedente + fascia):,.2f}",
                "percentuale": pct * moltiplicatore,
                "base": round(fascia, 2),
                "compenso": compenso,
            })
            residuo -= fascia
            precedente = soglia
        return dettaglio

    det_attivo = _calcola_scaglioni(attivo_realizzato, _SCAGLIONI_CURATORE)
    comp_attivo = sum(d["compenso"] for d in det_attivo)

    # Maggiorazione su passivo: metà degli scaglioni
    det_passivo = _calcola_scaglioni(passivo_accertato, _SCAGLIONI_CURATORE, 0.5)
    comp_passivo = sum(d["compenso"] for d in det_passivo)

    totale = round(comp_attivo + comp_passivo, 2)
    totale = max(totale, _CURATORE_MIN)
    totale = min(totale, _CURATORE_MAX)

    return {
        "attivo_realizzato": attivo_realizzato,
        "passivo_accertato": passivo_accertato,
        "compenso_su_attivo": round(comp_attivo, 2),
        "dettaglio_attivo": det_attivo,
        "compenso_su_passivo": round(comp_passivo, 2),
        "dettaglio_passivo": det_passivo,
        "totale_compenso": totale,
        "minimo": _CURATORE_MIN,
        "massimo": _CURATORE_MAX,
        "note": [
            "Compenso su attivo: scaglioni progressivi DM 30/2012",
            "Compenso su passivo: metà delle percentuali su attivo",
            f"Limiti: minimo €{_CURATORE_MIN:,.2f}, massimo €{_CURATORE_MAX:,.2f}",
            "Al compenso si aggiungono IVA e CPA se dovute",
        ],
        "riferimento_normativo": "DM 30/2012 — Compensi curatore fallimentare",
    }


@mcp.tool()
def compenso_delegati_vendite(
    prezzo_aggiudicazione: float,
) -> dict:
    """Calcola compenso del professionista delegato alle vendite giudiziarie immobiliari.
    Vigenza: DM 227/2015 — compenso minimo €1.100 per aggiudicazioni fino a €100.000.
    Precisione: ESATTO (scaglioni percentuali tabellari DM 227/2015).

    Args:
        prezzo_aggiudicazione: Prezzo di aggiudicazione dell'immobile in euro (€)
    """
    if prezzo_aggiudicazione <= 100_000:
        pct = 2.6
        compenso = round(prezzo_aggiudicazione * pct / 100, 2)
        compenso = max(compenso, 1_100.0)
    elif prezzo_aggiudicazione <= 500_000:
        compenso_prima_fascia = round(100_000 * 2.6 / 100, 2)
        compenso_seconda_fascia = round((prezzo_aggiudicazione - 100_000) * 1.5 / 100, 2)
        compenso = round(compenso_prima_fascia + compenso_seconda_fascia, 2)
        pct = round(compenso / prezzo_aggiudicazione * 100, 2)
    else:
        compenso_prima_fascia = round(100_000 * 2.6 / 100, 2)
        compenso_seconda_fascia = round(400_000 * 1.5 / 100, 2)
        compenso_terza_fascia = round((prezzo_aggiudicazione - 500_000) * 0.75 / 100, 2)
        compenso = round(compenso_prima_fascia + compenso_seconda_fascia + compenso_terza_fascia, 2)
        pct = round(compenso / prezzo_aggiudicazione * 100, 2)

    return {
        "prezzo_aggiudicazione": prezzo_aggiudicazione,
        "compenso": compenso,
        "percentuale_effettiva": pct,
        "scaglioni": [
            {"fascia": "fino a €100.000", "percentuale": 2.6, "minimo": 1_100},
            {"fascia": "€100.001 - €500.000", "percentuale": 1.5},
            {"fascia": "oltre €500.000", "percentuale": 0.75},
        ],
        "note": [
            "Compenso minimo: €1.100 (per aggiudicazioni fino a €100.000)",
            "Al compenso si aggiungono IVA e CPA/rivalsa se dovute",
            "Rimborso spese forfettario: 10% del compenso",
        ],
        "riferimento_normativo": "DM 227/2015 — Compensi professionisti delegati vendite giudiziarie",
    }


@mcp.tool()
def compenso_mediatore_familiare(
    n_incontri: int,
    tariffa_incontro: float = 120.0,
) -> dict:
    """Calcola compenso del mediatore familiare per percorso di mediazione.
    Il primo incontro informativo è gratuito; la mediazione familiare non è regolata da tariffe ministeriali.
    Vigenza: nessuna tariffa ministeriale — importi di prassi professionale.
    Precisione: INDICATIVO (tariffa varia per professionista e territorio; percorso tipico: 8-12 incontri).

    Args:
        n_incontri: Numero totale di incontri comprensivo del primo informativo gratuito (minimo 1)
        tariffa_incontro: Tariffa per singolo incontro a pagamento in euro (€, default: €120)
    """
    if n_incontri < 1:
        return {"errore": "Numero incontri deve essere almeno 1"}

    incontri_a_pagamento = max(0, n_incontri - 1)
    compenso = round(incontri_a_pagamento * tariffa_incontro, 2)

    return {
        "n_incontri_totali": n_incontri,
        "primo_incontro": "gratuito (informativo)",
        "incontri_a_pagamento": incontri_a_pagamento,
        "tariffa_incontro": tariffa_incontro,
        "compenso_totale": compenso,
        "note": [
            "Il primo incontro informativo è gratuito",
            "Percorso tipico: 8-12 incontri",
            "Tariffa indicativa — varia per professionista e territorio",
            "La mediazione familiare non è regolata da tariffe ministeriali",
        ],
    }


# Enasarco 2026
_ENASARCO_ALIQUOTA = 17.0  # 50% agente + 50% preponente
_ENASARCO_MINIMALE_TRIMESTRALE = 443.0
_ENASARCO_MASSIMALE_ANNUO = 27_000.0


@mcp.tool()
def fattura_enasarco(
    provvigioni: float,
    tipo_agente: str = "monocommittente",
    anno: int = 2026,
) -> dict:
    """Calcola struttura fattura agente di commercio con contributo Enasarco, IVA e ritenuta.
    Vigenza: D.Lgs. 303/1996 — Regolamento Enasarco; aliquota 2026: 17% totale (50% agente + 50% preponente).
    Precisione: ESATTO per aliquote vigenti nell'anno indicato; verificare aggiornamenti annuali Enasarco.

    Args:
        provvigioni: Importo provvigioni in euro (€, imponibile)
        tipo_agente: Tipo mandato: 'monocommittente' o 'pluricommittente'
        anno: Anno di riferimento per le aliquote Enasarco (es. 2026)
    """
    if tipo_agente not in ("monocommittente", "pluricommittente"):
        return {"errore": f"Tipo agente non valido: {tipo_agente}. Usare: monocommittente, pluricommittente"}

    contributo_totale = round(provvigioni * _ENASARCO_ALIQUOTA / 100, 2)
    quota_agente = round(contributo_totale / 2, 2)
    quota_preponente = round(contributo_totale - quota_agente, 2)

    iva = round(provvigioni * 22 / 100, 2)
    ritenuta = round(provvigioni * 50 / 100 * 23 / 100, 2)  # 23% sul 50% delle provvigioni

    totale_fattura = round(provvigioni + iva, 2)
    netto = round(totale_fattura - ritenuta - quota_agente, 2)

    return {
        "provvigioni": provvigioni,
        "tipo_agente": tipo_agente,
        "anno": anno,
        "contributo_enasarco": {
            "aliquota_totale": _ENASARCO_ALIQUOTA,
            "contributo_totale": contributo_totale,
            "quota_agente": quota_agente,
            "quota_preponente": quota_preponente,
            "minimale_trimestrale": _ENASARCO_MINIMALE_TRIMESTRALE,
            "massimale_annuo": _ENASARCO_MASSIMALE_ANNUO,
        },
        "iva_22pct": iva,
        "ritenuta_acconto": {
            "base": round(provvigioni * 50 / 100, 2),
            "aliquota": 23.0,
            "importo": ritenuta,
            "nota": "23% sul 50% delle provvigioni (art. 25-bis DPR 600/1973)",
        },
        "totale_fattura": totale_fattura,
        "netto_a_pagare": netto,
        "nota": (
            f"Il preponente versa la propria quota Enasarco (€{quota_preponente}) "
            f"e trattiene dalla fattura la quota agente (€{quota_agente}) + ritenuta (€{ritenuta})"
        ),
        "riferimento_normativo": "D.Lgs. 303/1996 — Regolamento Enasarco",
    }


@mcp.tool()
def ricevuta_prestazione_occasionale(
    compenso_lordo: float,
    committente: str,
    prestatore: str,
    descrizione: str,
) -> dict:
    """Genera testo ricevuta per prestazione occasionale con ritenuta d'acconto (20%) e bollo se >€77,47.
    Vigenza: Art. 2222 c.c. — Art. 67 co. 1 lett. l) TUIR — Art. 25 DPR 600/1973.
    Precisione: ESATTO (ritenuta 20%, soglia bollo €77,47 fissa per legge).
    Nota: limite annuo €5.000 per evitare obbligo INPS Gestione Separata.

    Args:
        compenso_lordo: Compenso lordo pattuito in euro (€)
        committente: Nome / ragione sociale del committente (sostituto d'imposta)
        prestatore: Nome e cognome del prestatore della prestazione
        descrizione: Descrizione sintetica della prestazione svolta
    """
    ritenuta = round(compenso_lordo * 20 / 100, 2)
    netto = round(compenso_lordo - ritenuta, 2)
    bollo = 2.0 if compenso_lordo > 77.47 else 0.0

    linee = [
        "RICEVUTA PER PRESTAZIONE OCCASIONALE",
        f"Art. 2222 c.c. — Art. 67, comma 1, lett. l) TUIR",
        "",
        f"Prestatore: {prestatore}",
        f"Committente: {committente}",
        "",
        f"Descrizione: {descrizione}",
        "",
        f"  Compenso lordo: €{compenso_lordo:,.2f}",
        f"  Ritenuta d'acconto 20%: -€{ritenuta:,.2f}",
        f"  Netto a pagare: €{netto:,.2f}",
    ]
    if bollo > 0:
        linee.append(f"  Imposta di bollo: €{bollo:,.2f} (importo > €77,47)")
    linee.append("")
    linee.append("Operazione fuori campo IVA ex art. 5 DPR 633/1972")

    return {
        "testo_ricevuta": "\n".join(linee),
        "calcoli": {
            "compenso_lordo": compenso_lordo,
            "ritenuta_acconto_20pct": ritenuta,
            "netto_a_pagare": netto,
            "bollo": bollo,
        },
        "committente": committente,
        "prestatore": prestatore,
        "descrizione": descrizione,
        "note": [
            "Il committente versa la ritenuta con F24 (codice tributo 1040) entro il 16 del mese successivo",
            "Il prestatore dichiara il reddito nella dichiarazione dei redditi (quadro RL)",
            "Limite annuo: €5.000 lordi per non incorrere in obbligo contributivo INPS Gestione Separata",
        ],
        "riferimento_normativo": "Art. 2222 c.c. — Art. 67 co. 1 lett. l) TUIR — Art. 25 DPR 600/1973",
    }


# Tabella indennità mediazione DM 150/2023 completa
_TABELLA_MEDIAZIONE_DM150 = [
    {"fino_a": 1_000, "spese_avvio": 40, "indennita_negativo": 60, "indennita_positivo": 120},
    {"fino_a": 5_000, "spese_avvio": 40, "indennita_negativo": 100, "indennita_positivo": 200},
    {"fino_a": 10_000, "spese_avvio": 40, "indennita_negativo": 170, "indennita_positivo": 340},
    {"fino_a": 25_000, "spese_avvio": 40, "indennita_negativo": 240, "indennita_positivo": 480},
    {"fino_a": 50_000, "spese_avvio": 40, "indennita_negativo": 360, "indennita_positivo": 720},
    {"fino_a": 250_000, "spese_avvio": 40, "indennita_negativo": 530, "indennita_positivo": 1_060},
    {"fino_a": 500_000, "spese_avvio": 40, "indennita_negativo": 880, "indennita_positivo": 1_760},
    {"fino_a": 2_500_000, "spese_avvio": 40, "indennita_negativo": 1_250, "indennita_positivo": 2_500},
    {"fino_a": 5_000_000, "spese_avvio": 40, "indennita_negativo": 2_000, "indennita_positivo": 4_000},
    {"oltre": True, "spese_avvio": 40, "indennita_negativo": 2_800, "indennita_positivo": 5_600},
]


@mcp.tool()
def tariffe_mediazione(
    valore_controversia: float,
) -> dict:
    """Restituisce la tabella completa delle indennità di mediazione DM 150/2023 per scaglione applicabile.
    A differenza di spese_mediazione, include anche le spese di avvio (€40) e la tabella per tutti gli scaglioni.
    Vigenza: DM 150/2023 — D.Lgs. 28/2010 (Riforma Cartabia).
    Precisione: ESATTO (importi tabellari ministeriali).

    Args:
        valore_controversia: Valore della controversia in euro (€)
    """
    scaglione_applicabile = None
    for s in _TABELLA_MEDIAZIONE_DM150:
        if s.get("oltre") or valore_controversia <= s["fino_a"]:
            scaglione_applicabile = s
            break

    label = f"fino a €{scaglione_applicabile['fino_a']:,.0f}" if not scaglione_applicabile.get("oltre") else "oltre €5.000.000"

    spese_avvio = scaglione_applicabile["spese_avvio"]
    ind_neg = scaglione_applicabile["indennita_negativo"]
    ind_pos = scaglione_applicabile["indennita_positivo"]

    # Costi per parte
    iva_neg = round(ind_neg * 22 / 100, 2)
    iva_pos = round(ind_pos * 22 / 100, 2)
    totale_neg = round(spese_avvio + ind_neg + iva_neg, 2)
    totale_pos = round(spese_avvio + ind_pos + iva_pos, 2)

    return {
        "valore_controversia": valore_controversia,
        "scaglione": label,
        "spese_avvio_per_parte": spese_avvio,
        "esito_negativo": {
            "indennita_per_parte": ind_neg,
            "iva_22pct": iva_neg,
            "totale_per_parte": totale_neg,
            "totale_2_parti": round(totale_neg * 2, 2),
        },
        "esito_positivo": {
            "indennita_per_parte": ind_pos,
            "iva_22pct": iva_pos,
            "totale_per_parte": totale_pos,
            "totale_2_parti": round(totale_pos * 2, 2),
        },
        "tabella_completa": [
            {
                "scaglione": f"fino a €{s['fino_a']:,.0f}" if not s.get("oltre") else "oltre €5.000.000",
                "spese_avvio": s["spese_avvio"],
                "indennita_negativo": s["indennita_negativo"],
                "indennita_positivo": s["indennita_positivo"],
            }
            for s in _TABELLA_MEDIAZIONE_DM150
        ],
        "note": [
            "Spese di avvio: €40 per ciascuna parte, dovute all'atto della presentazione della domanda",
            "Indennità: dovuta per ciascuna parte a ciascun organismo",
            "Esito positivo = accordo raggiunto; esito negativo = mancato accordo",
            "Incontri successivi al primo: maggiorazione fino al 25% dell'indennità",
            "Per più di 2 parti: aumento indennità per ciascuna parte ulteriore",
        ],
        "agevolazioni": [
            "Credito d'imposta fino a €600 per parte in caso di accordo (art. 20 D.Lgs. 28/2010)",
            "Esenzione imposta di registro fino a €100.000",
            "Gratuito patrocinio: parti ammesse non pagano indennità",
        ],
        "riferimento_normativo": "DM 150/2023 — D.Lgs. 28/2010 (Riforma Cartabia)",
    }
