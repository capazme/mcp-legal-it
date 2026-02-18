"""Sezione 6 — Parcelle Professionisti: fatture, CTU, mediazione, compensi orari, ritenuta."""

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
    """Calcola fattura generica professionista con rivalsa INPS, IVA e ritenuta.

    Args:
        imponibile: Compenso professionale in euro (imponibile)
        tipo: Tipo professionista (ingegnere, architetto, geometra, commercialista, consulente_lavoro, psicologo, medico)
        regime: 'ordinario' (IVA 22% + ritenuta 20%) o 'forfettario' (no IVA, no ritenuta, bollo se >77.47€)
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
        # Ritenuta d'acconto 20% su compenso + rivalsa
        ritenuta = round(base_imponibile_iva * 20 / 100, 2)
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
    """Calcola compenso indicativo del consulente tecnico d'ufficio (CTU).

    Args:
        tipo_incarico: Tipo incarico (perizia_immobiliare, perizia_contabile, perizia_medica, stima_danni, accertamenti_tecnici)
        valore_causa: Valore della causa in euro (per calcolo a percentuale)
        ore_lavoro: Ore di lavoro effettive (per calcolo orario)
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
    """Calcola indennità di mediazione civile/commerciale DM 150/2023.

    Args:
        valore_controversia: Valore della controversia in euro
        esito: 'positivo' (accordo raggiunto) o 'negativo' (mancato accordo)
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
    """Calcola compenso professionale a ore con arrotondamento.

    Args:
        tariffa_oraria: Tariffa oraria in euro
        ore: Numero di ore lavorate
        minuti: Minuti aggiuntivi (0-59)
        arrotondamento: Tipo arrotondamento: 'quarto_ora' (15 min), 'mezz_ora' (30 min), 'ora' (60 min)
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
    """Calcola ritenuta d'acconto su compensi professionali.

    Args:
        compenso_lordo: Compenso lordo in euro (base imponibile per la ritenuta)
        aliquota: Aliquota ritenuta in percentuale (default 20%)
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
