"""Sezione 5 — Fatturazione Avvocati: parcelle, fatture e note spese forensi."""

import json
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "parametri_forensi.json") as f:
    _PARAMETRI = json.load(f)

_FASI_CIVILE = ["studio", "introduttiva", "istruttoria", "decisionale"]
_FASI_PENALE = ["studio", "introduttiva", "istruttoria", "decisionale"]
_TIPI_REATO = ["contravvenzioni", "delitti_fino_4_anni", "delitti_4_8_anni", "delitti_oltre_8_anni"]


def _find_scaglione_civile(valore_causa: float) -> dict:
    for s in _PARAMETRI["civile"]["scaglioni"]:
        if s.get("oltre"):
            return s
        if valore_causa <= s["fino_a"]:
            return s
    return _PARAMETRI["civile"]["scaglioni"][-1]


def _find_scaglione_stragiudiziale(valore_pratica: float) -> dict:
    for s in _PARAMETRI["stragiudiziale"]["scaglioni"]:
        if s.get("oltre"):
            return s
        if valore_pratica <= s["fino_a"]:
            return s
    return _PARAMETRI["stragiudiziale"]["scaglioni"][-1]


@mcp.tool()
def parcella_avvocato_civile(
    valore_causa: float,
    fasi: list[str] | None = None,
    livello: str = "medio",
) -> dict:
    """Calcolo compenso avvocato per contenzioso civile (DM 55/2014 agg. DM 147/2022).

    Args:
        valore_causa: Valore della causa in euro
        fasi: Fasi processuali da includere (default: tutte). Valori: "studio", "introduttiva", "istruttoria", "decisionale"
        livello: Livello compenso: "min", "medio", "max"
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if fasi is None:
        fasi = list(_FASI_CIVILE)
    else:
        invalid = [f for f in fasi if f not in _FASI_CIVILE]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_CIVILE}"}

    scaglione = _find_scaglione_civile(valore_causa)
    scaglione_label = f"fino a {scaglione['fino_a']}€" if not scaglione.get("oltre") else "oltre 520.000€"

    dettaglio = []
    totale = 0.0
    for fase in fasi:
        importo = scaglione[fase][livello]
        totale += importo
        dettaglio.append({"fase": fase, "importo": importo})

    return {
        "valore_causa": valore_causa,
        "scaglione": scaglione_label,
        "livello": livello,
        "fasi": dettaglio,
        "totale_compenso": round(totale, 2),
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi contenzioso civile",
    }


@mcp.tool()
def parcella_avvocato_penale(
    tipo_reato: str,
    fasi: list[str] | None = None,
    livello: str = "medio",
) -> dict:
    """Calcolo compenso avvocato per procedimento penale (DM 55/2014 agg. DM 147/2022).

    Args:
        tipo_reato: Tipo di reato: "contravvenzioni", "delitti_fino_4_anni", "delitti_4_8_anni", "delitti_oltre_8_anni"
        fasi: Fasi processuali da includere (default: tutte). Valori: "studio", "introduttiva", "istruttoria", "decisionale"
        livello: Livello compenso: "min", "medio", "max"
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if tipo_reato not in _TIPI_REATO:
        return {"errore": f"Tipo reato non valido: {tipo_reato}. Ammessi: {_TIPI_REATO}"}

    if fasi is None:
        fasi = list(_FASI_PENALE)
    else:
        invalid = [f for f in fasi if f not in _FASI_PENALE]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_PENALE}"}

    scaglione = next(s for s in _PARAMETRI["penale"]["scaglioni"] if s["tipo"] == tipo_reato)

    dettaglio = []
    totale = 0.0
    for fase in fasi:
        importo = scaglione[fase][livello]
        totale += importo
        dettaglio.append({"fase": fase, "importo": importo})

    return {
        "tipo_reato": tipo_reato,
        "livello": livello,
        "fasi": dettaglio,
        "totale_compenso": round(totale, 2),
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi penale",
    }


@mcp.tool()
def parcella_stragiudiziale(
    valore_pratica: float,
    livello: str = "medio",
) -> dict:
    """Calcolo compenso avvocato per attività stragiudiziale (DM 55/2014 agg. DM 147/2022).

    Args:
        valore_pratica: Valore della pratica in euro
        livello: Livello compenso: "min", "medio", "max"
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    scaglione = _find_scaglione_stragiudiziale(valore_pratica)
    scaglione_label = f"fino a {scaglione['fino_a']}€" if not scaglione.get("oltre") else "oltre 520.000€"
    compenso = scaglione[livello]

    return {
        "valore_pratica": valore_pratica,
        "scaglione": scaglione_label,
        "livello": livello,
        "compenso": compenso,
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi attività stragiudiziale",
    }


@mcp.tool()
def fattura_avvocato(
    imponibile: float,
    regime: str = "ordinario",
    cpa: bool = True,
) -> dict:
    """Genera fattura avvocato con CPA, IVA e ritenuta d'acconto.

    Args:
        imponibile: Compenso professionale (imponibile) in euro
        regime: Regime fiscale: "ordinario" o "forfettario"
        cpa: Se applicare Cassa Previdenza Avvocati 4% (default: True)
    """
    if regime not in ("ordinario", "forfettario"):
        return {"errore": f"Regime non valido: {regime}. Usare: ordinario, forfettario"}

    voci = [{"descrizione": "Compenso professionale", "importo": round(imponibile, 2)}]

    cpa_importo = 0.0
    if cpa:
        cpa_importo = round(imponibile * 0.04, 2)
        voci.append({"descrizione": "CPA 4% (Cassa Previdenza Avvocati)", "importo": cpa_importo})

    imponibile_iva = round(imponibile + cpa_importo, 2)

    iva_importo = 0.0
    ritenuta_importo = 0.0

    if regime == "ordinario":
        iva_importo = round(imponibile_iva * 0.22, 2)
        ritenuta_importo = round(imponibile * 0.20, 2)
        voci.append({"descrizione": "IVA 22%", "importo": iva_importo})
        voci.append({"descrizione": "Ritenuta d'acconto 20% (su compenso)", "importo": -ritenuta_importo})
        totale = round(imponibile_iva + iva_importo - ritenuta_importo, 2)
    else:
        totale = imponibile_iva
        voci.append({"descrizione": "IVA: esente (regime forfettario art. 1 c. 54-89 L. 190/2014)", "importo": 0.0})

    return {
        "regime": regime,
        "imponibile": round(imponibile, 2),
        "cpa_4pct": cpa_importo,
        "imponibile_iva": imponibile_iva,
        "iva_22pct": iva_importo,
        "ritenuta_acconto_20pct": ritenuta_importo,
        "totale_fattura": totale,
        "netto_a_pagare": totale,
        "voci": voci,
    }


@mcp.tool()
def nota_spese(
    voci: list[dict],
) -> dict:
    """Calcolo nota spese avvocato con voci di tariffa, spese generali, CPA e IVA.

    Args:
        voci: Lista di voci, ognuna con: descrizione (str), importo (float), tipo ("compenso", "spese_generali_15pct", "spese_vive", "spese_documentate")
    """
    tipi_validi = {"compenso", "spese_generali_15pct", "spese_vive", "spese_documentate"}
    for v in voci:
        if v.get("tipo") not in tipi_validi:
            return {"errore": f"Tipo voce non valido: {v.get('tipo')}. Ammessi: {sorted(tipi_validi)}"}

    dettaglio = []
    totale_compensi = 0.0
    totale_spese_generali = 0.0
    totale_spese_vive = 0.0

    for v in voci:
        importo = round(v["importo"], 2)
        tipo = v["tipo"]

        if tipo == "compenso":
            totale_compensi += importo
            dettaglio.append({"descrizione": v["descrizione"], "tipo": tipo, "importo": importo})
        elif tipo == "spese_generali_15pct":
            sg = round(v["importo"] * 0.15, 2)
            totale_spese_generali += sg
            dettaglio.append({"descrizione": v["descrizione"] + " (15% spese generali)", "tipo": tipo, "importo": sg})
        elif tipo in ("spese_vive", "spese_documentate"):
            totale_spese_vive += importo
            dettaglio.append({"descrizione": v["descrizione"], "tipo": tipo, "importo": importo})

    subtotale = round(totale_compensi + totale_spese_generali, 2)
    cpa = round(subtotale * 0.04, 2)
    imponibile_iva = round(subtotale + cpa, 2)
    iva = round(imponibile_iva * 0.22, 2)
    totale = round(imponibile_iva + iva + totale_spese_vive, 2)

    return {
        "dettaglio_voci": dettaglio,
        "totale_compensi": totale_compensi,
        "totale_spese_generali_15pct": totale_spese_generali,
        "subtotale_compensi": subtotale,
        "cpa_4pct": cpa,
        "imponibile_iva": imponibile_iva,
        "iva_22pct": iva,
        "totale_spese_vive": totale_spese_vive,
        "totale_nota_spese": totale,
        "riferimento_normativo": "DM 55/2014 — Art. 2 c. 2 spese generali 15%",
    }
