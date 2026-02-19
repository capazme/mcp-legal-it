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


# --- Spese vive stimate per tipo procedimento civile ---
_SPESE_VIVE_STIMATE = {
    "contributo_unificato": [
        (1_100, 43),
        (5_200, 98),
        (26_000, 237),
        (52_000, 237),
        (260_000, 518),
        (520_000, 759),
        (float("inf"), 1_686),
    ],
    "marca_da_bollo": 27.0,
    "notifica_pec": 3.54,
    "notifica_ufficiale_giudiziario": 27.0,
    "diritti_copia": 15.0,
}


def _contributo_unificato(valore_causa: float) -> float:
    for soglia, importo in _SPESE_VIVE_STIMATE["contributo_unificato"]:
        if valore_causa <= soglia:
            return importo
    return _SPESE_VIVE_STIMATE["contributo_unificato"][-1][1]


@mcp.tool()
def preventivo_civile(
    valore_causa: float,
    fasi: list[str] | None = None,
    livello: str = "medio",
    spese_generali: bool = True,
    cpa: bool = True,
    iva: bool = True,
) -> dict:
    """Genera preventivo completo per causa civile con compensi, spese generali, CPA, IVA e spese vive stimate.

    Args:
        valore_causa: Valore della causa in euro
        fasi: Fasi processuali (default: tutte). Valori: "studio", "introduttiva", "istruttoria", "decisionale"
        livello: Livello compenso: "min", "medio", "max"
        spese_generali: Se aggiungere 15% spese generali (default: True)
        cpa: Se aggiungere CPA 4% (default: True)
        iva: Se aggiungere IVA 22% (default: True)
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

    dettaglio_fasi = []
    totale_compensi = 0.0
    for fase in fasi:
        importo = scaglione[fase][livello]
        totale_compensi += importo
        dettaglio_fasi.append({"fase": fase, "importo": importo})

    sg_importo = round(totale_compensi * 0.15, 2) if spese_generali else 0.0
    subtotale = round(totale_compensi + sg_importo, 2)
    cpa_importo = round(subtotale * 0.04, 2) if cpa else 0.0
    imponibile_iva = round(subtotale + cpa_importo, 2)
    iva_importo = round(imponibile_iva * 0.22, 2) if iva else 0.0
    totale_onorari = round(imponibile_iva + iva_importo, 2)

    # Spese vive stimate
    cu = _contributo_unificato(valore_causa)
    spese_vive = {
        "contributo_unificato": cu,
        "marca_da_bollo_iscrizione": _SPESE_VIVE_STIMATE["marca_da_bollo"],
        "notifica_pec": _SPESE_VIVE_STIMATE["notifica_pec"],
        "notifica_ufficiale_giudiziario": _SPESE_VIVE_STIMATE["notifica_ufficiale_giudiziario"],
        "diritti_copia": _SPESE_VIVE_STIMATE["diritti_copia"],
    }
    totale_spese_vive = round(sum(spese_vive.values()), 2)
    totale_preventivo = round(totale_onorari + totale_spese_vive, 2)

    linee = [
        f"PREVENTIVO CAUSA CIVILE — Valore causa: €{valore_causa:,.2f}",
        f"Scaglione: {scaglione_label} | Livello: {livello}",
        "",
        "COMPENSI PROFESSIONALI:",
    ]
    for d in dettaglio_fasi:
        linee.append(f"  - Fase {d['fase']}: €{d['importo']:,.2f}")
    linee.append(f"  Totale compensi: €{totale_compensi:,.2f}")
    if spese_generali:
        linee.append(f"  Spese generali 15%: €{sg_importo:,.2f}")
    linee.append(f"  Subtotale: €{subtotale:,.2f}")
    if cpa:
        linee.append(f"  CPA 4%: €{cpa_importo:,.2f}")
    if iva:
        linee.append(f"  IVA 22%: €{iva_importo:,.2f}")
    linee.append(f"  TOTALE ONORARI: €{totale_onorari:,.2f}")
    linee.append("")
    linee.append("SPESE VIVE STIMATE:")
    for k, v in spese_vive.items():
        linee.append(f"  - {k.replace('_', ' ').title()}: €{v:,.2f}")
    linee.append(f"  TOTALE SPESE VIVE: €{totale_spese_vive:,.2f}")
    linee.append("")
    linee.append(f"TOTALE PREVENTIVO: €{totale_preventivo:,.2f}")

    return {
        "testo_preventivo": "\n".join(linee),
        "dettaglio_calcoli": {
            "valore_causa": valore_causa,
            "scaglione": scaglione_label,
            "livello": livello,
            "fasi": dettaglio_fasi,
            "totale_compensi": round(totale_compensi, 2),
            "spese_generali_15pct": sg_importo,
            "subtotale": subtotale,
            "cpa_4pct": cpa_importo,
            "imponibile_iva": imponibile_iva,
            "iva_22pct": iva_importo,
            "totale_onorari": totale_onorari,
            "spese_vive": spese_vive,
            "totale_spese_vive": totale_spese_vive,
            "totale_preventivo": totale_preventivo,
        },
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi contenzioso civile",
    }


@mcp.tool()
def preventivo_stragiudiziale(
    valore_pratica: float,
    livello: str = "medio",
    spese_generali: bool = True,
    cpa: bool = True,
    iva: bool = True,
) -> dict:
    """Genera preventivo per attività stragiudiziale (diffida, trattativa, mediazione) con spese generali, CPA e IVA.

    Args:
        valore_pratica: Valore della pratica in euro
        livello: Livello compenso: "min", "medio", "max"
        spese_generali: Se aggiungere 15% spese generali (default: True)
        cpa: Se aggiungere CPA 4% (default: True)
        iva: Se aggiungere IVA 22% (default: True)
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    scaglione = _find_scaglione_stragiudiziale(valore_pratica)
    scaglione_label = f"fino a {scaglione['fino_a']}€" if not scaglione.get("oltre") else "oltre 520.000€"
    compenso = scaglione[livello]

    sg_importo = round(compenso * 0.15, 2) if spese_generali else 0.0
    subtotale = round(compenso + sg_importo, 2)
    cpa_importo = round(subtotale * 0.04, 2) if cpa else 0.0
    imponibile_iva = round(subtotale + cpa_importo, 2)
    iva_importo = round(imponibile_iva * 0.22, 2) if iva else 0.0
    totale = round(imponibile_iva + iva_importo, 2)

    linee = [
        f"PREVENTIVO ATTIVITÀ STRAGIUDIZIALE — Valore pratica: €{valore_pratica:,.2f}",
        f"Scaglione: {scaglione_label} | Livello: {livello}",
        "",
        f"  Compenso base: €{compenso:,.2f}",
    ]
    if spese_generali:
        linee.append(f"  Spese generali 15%: €{sg_importo:,.2f}")
    linee.append(f"  Subtotale: €{subtotale:,.2f}")
    if cpa:
        linee.append(f"  CPA 4%: €{cpa_importo:,.2f}")
    if iva:
        linee.append(f"  IVA 22%: €{iva_importo:,.2f}")
    linee.append(f"  TOTALE: €{totale:,.2f}")

    return {
        "testo_preventivo": "\n".join(linee),
        "dettaglio_calcoli": {
            "valore_pratica": valore_pratica,
            "scaglione": scaglione_label,
            "livello": livello,
            "compenso_base": compenso,
            "spese_generali_15pct": sg_importo,
            "subtotale": subtotale,
            "cpa_4pct": cpa_importo,
            "imponibile_iva": imponibile_iva,
            "iva_22pct": iva_importo,
            "totale": totale,
        },
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi attività stragiudiziale",
    }


@mcp.tool()
def spese_trasferta_avvocati(
    km_distanza: float,
    ore_assenza: float,
    pernottamento: bool = False,
    mezzo: str = "auto",
) -> dict:
    """Calcolo indennità e rimborso spese di trasferta per avvocati.

    Args:
        km_distanza: Distanza andata/ritorno in km
        ore_assenza: Ore di assenza dallo studio
        pernottamento: Se è necessario il pernottamento
        mezzo: Mezzo di trasporto: "auto" (€0.30/km ACI), "treno", "aereo"
    """
    if mezzo not in ("auto", "treno", "aereo"):
        return {"errore": f"Mezzo non valido: {mezzo}. Usare: auto, treno, aereo"}

    # Rimborso chilometrico (solo auto)
    rimborso_km = round(km_distanza * 0.30, 2) if mezzo == "auto" else 0.0

    # Indennità di trasferta basata su ore assenza
    # Riferimento: onorario medio fase studio scaglione 26.000€ = 540€
    onorario_riferimento = 540.0
    if ore_assenza <= 4:
        pct_indennita = 10
    elif ore_assenza <= 8:
        pct_indennita = 20
    else:
        pct_indennita = 40
    indennita = round(onorario_riferimento * pct_indennita / 100, 2)

    voci = [
        {"voce": f"Indennità trasferta ({pct_indennita}% su €{onorario_riferimento})", "importo": indennita},
    ]
    if mezzo == "auto":
        voci.append({"voce": f"Rimborso km ({km_distanza} km × €0.30)", "importo": rimborso_km})
    else:
        voci.append({"voce": f"Rimborso {mezzo}: a piè di lista", "importo": 0.0})

    nota_pernottamento = None
    if pernottamento:
        nota_pernottamento = "Pernottamento: rimborso a piè di lista su presentazione di ricevuta/fattura"
        voci.append({"voce": "Pernottamento", "importo": 0.0, "nota": "a piè di lista"})

    totale_stimato = round(indennita + rimborso_km, 2)

    return {
        "km_distanza": km_distanza,
        "ore_assenza": ore_assenza,
        "mezzo": mezzo,
        "pernottamento": pernottamento,
        "indennita_trasferta": indennita,
        "percentuale_indennita": pct_indennita,
        "rimborso_km": rimborso_km,
        "totale_stimato": totale_stimato,
        "voci": voci,
        "nota_pernottamento": nota_pernottamento,
        "note": [
            "L'indennità è calcolata come percentuale dell'onorario medio (scaglione €26.000, fase studio)",
            "Per treno/aereo il rimborso è a piè di lista su documentazione",
            "Il pernottamento è sempre rimborsato a piè di lista",
        ],
        "riferimento_normativo": "DM 55/2014 art. 27 — Spese di trasferta avvocati",
    }


# Parametri forfettari per notule su procedimenti tipici
_NOTULA_PROCEDIMENTI = {
    "decreto_ingiuntivo": {
        "fasi_default": ["studio", "introduttiva"],
        "descrizione": "Ricorso per decreto ingiuntivo",
        "spese_vive_stimate": {"contributo_unificato_dimezzato": True, "marca_da_bollo": 27.0},
    },
    "precetto": {
        "fasi_default": ["studio", "introduttiva"],
        "descrizione": "Atto di precetto",
        "spese_vive_stimate": {"marca_da_bollo": 27.0, "notifica": 27.0},
    },
    "esecuzione_mobiliare": {
        "fasi_default": ["studio", "introduttiva", "istruttoria"],
        "descrizione": "Esecuzione mobiliare presso terzi",
        "spese_vive_stimate": {"contributo_unificato": True, "marca_da_bollo": 27.0},
    },
    "esecuzione_immobiliare": {
        "fasi_default": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "descrizione": "Esecuzione immobiliare",
        "spese_vive_stimate": {"contributo_unificato": True, "marca_da_bollo": 27.0, "trascrizione": 300.0},
    },
}


@mcp.tool()
def modello_notula(
    tipo_procedimento: str,
    avvocato: str,
    cliente: str,
    valore_causa: float,
    fasi: list[str] | None = None,
    livello: str = "medio",
) -> dict:
    """Genera notula (nota spese) completa formattata per decreto ingiuntivo, precetto o esecuzioni.

    Args:
        tipo_procedimento: Tipo: "decreto_ingiuntivo", "precetto", "esecuzione_mobiliare", "esecuzione_immobiliare"
        avvocato: Nome e cognome dell'avvocato
        cliente: Nome e cognome / ragione sociale del cliente
        valore_causa: Valore della causa in euro
        fasi: Fasi da includere (default: fasi tipiche del procedimento)
        livello: Livello compenso: "min", "medio", "max"
    """
    if tipo_procedimento not in _NOTULA_PROCEDIMENTI:
        return {"errore": f"Tipo non valido: {tipo_procedimento}. Ammessi: {list(_NOTULA_PROCEDIMENTI.keys())}"}
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    proc = _NOTULA_PROCEDIMENTI[tipo_procedimento]
    if fasi is None:
        fasi = proc["fasi_default"]
    else:
        invalid = [f for f in fasi if f not in _FASI_CIVILE]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_CIVILE}"}

    scaglione = _find_scaglione_civile(valore_causa)

    dettaglio_fasi = []
    totale_compensi = 0.0
    for fase in fasi:
        importo = scaglione[fase][livello]
        totale_compensi += importo
        dettaglio_fasi.append({"fase": fase, "importo": importo})

    sg = round(totale_compensi * 0.15, 2)
    subtotale = round(totale_compensi + sg, 2)
    cpa_importo = round(subtotale * 0.04, 2)
    imponibile_iva = round(subtotale + cpa_importo, 2)
    iva_importo = round(imponibile_iva * 0.22, 2)
    totale_onorari = round(imponibile_iva + iva_importo, 2)

    # Spese vive
    spese_vive_det = {}
    sv = proc["spese_vive_stimate"]
    if sv.get("contributo_unificato"):
        spese_vive_det["contributo_unificato"] = _contributo_unificato(valore_causa)
    if sv.get("contributo_unificato_dimezzato"):
        spese_vive_det["contributo_unificato_dimezzato"] = round(_contributo_unificato(valore_causa) / 2, 2)
    if sv.get("marca_da_bollo"):
        spese_vive_det["marca_da_bollo"] = sv["marca_da_bollo"]
    if sv.get("notifica"):
        spese_vive_det["notifica"] = sv["notifica"]
    if sv.get("trascrizione"):
        spese_vive_det["trascrizione"] = sv["trascrizione"]
    totale_spese_vive = round(sum(spese_vive_det.values()), 2)
    totale_notula = round(totale_onorari + totale_spese_vive, 2)

    linee = [
        "NOTULA — NOTA SPESE",
        f"Avv. {avvocato}",
        f"Cliente: {cliente}",
        f"Procedimento: {proc['descrizione']}",
        f"Valore causa: €{valore_causa:,.2f}",
        "",
        "COMPENSI PROFESSIONALI (DM 55/2014 agg. DM 147/2022):",
    ]
    for d in dettaglio_fasi:
        linee.append(f"  Fase {d['fase']}: €{d['importo']:,.2f}")
    linee.append(f"  Totale compensi: €{totale_compensi:,.2f}")
    linee.append(f"  Spese generali 15%: €{sg:,.2f}")
    linee.append(f"  Subtotale: €{subtotale:,.2f}")
    linee.append(f"  CPA 4%: €{cpa_importo:,.2f}")
    linee.append(f"  IVA 22%: €{iva_importo:,.2f}")
    linee.append(f"  TOTALE ONORARI: €{totale_onorari:,.2f}")
    linee.append("")
    linee.append("SPESE VIVE:")
    for k, v in spese_vive_det.items():
        linee.append(f"  {k.replace('_', ' ').title()}: €{v:,.2f}")
    linee.append(f"  TOTALE SPESE VIVE: €{totale_spese_vive:,.2f}")
    linee.append("")
    linee.append(f"TOTALE NOTULA: €{totale_notula:,.2f}")

    return {
        "testo_notula": "\n".join(linee),
        "dettaglio_calcoli": {
            "tipo_procedimento": tipo_procedimento,
            "avvocato": avvocato,
            "cliente": cliente,
            "valore_causa": valore_causa,
            "livello": livello,
            "fasi": dettaglio_fasi,
            "totale_compensi": round(totale_compensi, 2),
            "spese_generali_15pct": sg,
            "subtotale": subtotale,
            "cpa_4pct": cpa_importo,
            "iva_22pct": iva_importo,
            "totale_onorari": totale_onorari,
            "spese_vive": spese_vive_det,
            "totale_spese_vive": totale_spese_vive,
            "totale_notula": totale_notula,
        },
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022",
    }


@mcp.tool()
def calcolo_notula_penale(
    tipo_reato: str,
    fasi: list[str] | None = None,
    livello: str = "medio",
    spese_generali: bool = True,
) -> dict:
    """Calcolo parcella penale completa con spese generali 15%, CPA 4% e IVA 22%.

    Args:
        tipo_reato: Tipo di reato: "contravvenzioni", "delitti_fino_4_anni", "delitti_4_8_anni", "delitti_oltre_8_anni"
        fasi: Fasi processuali (default: tutte). Valori: "studio", "introduttiva", "istruttoria", "decisionale"
        livello: Livello compenso: "min", "medio", "max"
        spese_generali: Se aggiungere 15% spese generali (default: True)
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

    dettaglio_fasi = []
    totale_compensi = 0.0
    for fase in fasi:
        importo = scaglione[fase][livello]
        totale_compensi += importo
        dettaglio_fasi.append({"fase": fase, "importo": importo})

    sg_importo = round(totale_compensi * 0.15, 2) if spese_generali else 0.0
    subtotale = round(totale_compensi + sg_importo, 2)
    cpa_importo = round(subtotale * 0.04, 2)
    imponibile_iva = round(subtotale + cpa_importo, 2)
    iva_importo = round(imponibile_iva * 0.22, 2)
    totale = round(imponibile_iva + iva_importo, 2)

    return {
        "tipo_reato": tipo_reato,
        "livello": livello,
        "fasi": dettaglio_fasi,
        "totale_compensi": round(totale_compensi, 2),
        "spese_generali_15pct": sg_importo,
        "subtotale": subtotale,
        "cpa_4pct": cpa_importo,
        "imponibile_iva": imponibile_iva,
        "iva_22pct": iva_importo,
        "totale": totale,
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi penale",
    }
