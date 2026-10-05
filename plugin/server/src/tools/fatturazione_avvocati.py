"""Calcolo parcelle avvocati: compensi DM 55/2014 (agg. DM 147/2022), nota proforma,
fattura elettronica, contributo unificato, spese trasferta."""

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from src.server import mcp
from src.lib._data import sourced

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "parametri_forensi.json", encoding="utf-8") as f:
    _PARAMETRI = json.load(f)

#: Contributo unificato di cognizione, read from the shared table rather than
#: copied here: a hand-kept copy does not age with the table, diverges from the
#: answer of `contributo_unificato` without anything failing, and cannot report
#: its own vintage to the reader.
with open(_DATA / "contributo_unificato.json", encoding="utf-8") as f:
    _CU_CIVILE: list[dict] = json.load(f)["civile"]["cognizione"]

def _q(x) -> float:
    """Round to the cent, half-up, on the decimal value of ``x``.

    ``round(x, 2)`` works on the binary float: 1040.25 * 0.22 is exactly 228.855 but the float
    is 228.85499..., so a tie falls down for some amounts and up for others. Ties go up, as art. 5
    Reg. (CE) 1103/97 does for the euro rounding, and the same amount always gives the same cent.
    """
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _pct(base, pct: str) -> float:
    """``pct`` percent of ``base``, rounded to the cent half-up on exact decimals."""
    return _q(Decimal(str(base)) * Decimal(pct) / Decimal(100))


_FASI_CIVILE = ["studio", "introduttiva", "istruttoria", "decisionale"]
_FASI_PENALE = ["studio", "introduttiva", "istruttoria", "decisionale"]
_FASI_VOLONTARIA = ["studio", "trattazione"]
_COMPETENZE_PENALE = [c["tipo"] for c in _PARAMETRI["penale"]["competenze"]]


def _scaglione_label(scaglione: dict, scaglioni: list[dict]) -> str:
    if not scaglione.get("oltre"):
        return f"fino a {scaglione['fino_a']}€"
    finite = [s["fino_a"] for s in scaglioni if not s.get("oltre")]
    return f"oltre {finite[-1]}€" if finite else "oltre"


def _scaglione_civile_oltre_32_milioni(valore_causa: float, ultimo: dict, limite: float) -> dict:
    """Bands above 32 million: art. 6 co. 1 DM 55/2014, last sentence.

    "tale ultimo criterio puo' essere utilizzato per ogni successivo raddoppio del
    valore della controversia": +30% on the parameters of the previous band for each
    doubling (32-64 million +30%, 64-128 million +30% on the result, ...). Same
    convention as the bands the table already carries up to 32 million (verified
    against all of them): the medium is the previous rounded medium x 1,3 rounded to
    the euro half up, minimum and maximum are that medium -/+ 50%, rounded.
    """
    fasi = {f: int(ultimo[f]["medio"]) for f in _FASI_CIVILE}
    while valore_causa > limite:
        limite *= 2
        fasi = {f: int(_round_euro(Decimal(m) * Decimal("1.3"))) for f, m in fasi.items()}
    return {
        "oltre": True,
        **{
            f: {
                "min": int(_round_euro(Decimal(m) * Decimal("0.5"))),
                "medio": m,
                "max": int(_round_euro(Decimal(m) * Decimal("1.5"))),
            }
            for f, m in fasi.items()
        },
    }


def _find_scaglione_civile(valore_causa: float) -> dict:
    scaglioni = _PARAMETRI["civile"]["scaglioni"]
    for s in scaglioni:
        if s.get("oltre"):
            chiusi = [x for x in scaglioni if not x.get("oltre")]
            return _scaglione_civile_oltre_32_milioni(valore_causa, chiusi[-1], chiusi[-1]["fino_a"])
        if valore_causa <= s["fino_a"]:
            return s
    return scaglioni[-1]


def _find_scaglione_stragiudiziale(valore_pratica: float) -> dict:
    """Band of Tab. 25; above 520.000 euro art. 22 DM 55/2014 applies instead.

    Art. 22: "il compenso e' liquidato sulla base di una percentuale progressivamente
    decrescente del valore dell'affare, secondo quanto previsto dalla allegata tabella
    n. 25". The percentage of the bracket the value falls in (3% up to 2 million, ...,
    0,25% above 22 million) is applied to the WHOLE value: the medium, whole euro half
    up; minimum and maximum are that medium -/+ 50% (art. 19 co. 1).
    """
    scaglioni = _PARAMETRI["stragiudiziale"]["scaglioni"]
    for s in scaglioni:
        if s.get("oltre"):
            break
        if valore_pratica <= s["fino_a"]:
            return s
    for fascia in _PARAMETRI["stragiudiziale"]["percentuali_oltre_520000"]["fasce"]:
        if fascia.get("oltre") or valore_pratica <= fascia["fino_a"]:
            pct = Decimal(str(fascia["pct"]))
            break
    medio = int(_round_euro(Decimal(str(valore_pratica)) * pct / Decimal(100)))
    return {
        "oltre": True,
        "pct": float(pct),
        "min": int(_round_euro(Decimal(medio) * Decimal("0.5"))),
        "medio": medio,
        "max": int(_round_euro(Decimal(medio) * Decimal("1.5"))),
    }


def _label_stragiudiziale(scaglione: dict) -> str:
    return _scaglione_label(scaglione, _PARAMETRI["stragiudiziale"]["scaglioni"])


def _find_scaglione_volontaria(valore_causa: float) -> dict:
    for s in _PARAMETRI["volontaria_giurisdizione"]["scaglioni"]:
        if s.get("oltre"):
            return s
        if valore_causa <= s["fino_a"]:
            return s
    return _PARAMETRI["volontaria_giurisdizione"]["scaglioni"][-1]


@mcp.tool(tags={"parcelle_avv", "sinistro", "credito"})
@sourced("parametri_forensi")
def parcella_avvocato_civile(
    valore_causa: float,
    fasi: list[str] | None = None,
    livello: str = "medio",
) -> dict:
    """Calcola compenso tabellare avvocato per contenzioso civile.
    Vigenza: DM 55/2014 aggiornato DM 147/2022 — Parametri forensi (tabella del tribunale). Oltre 520.000 euro
    applica per intero l'aumento del 30% dell'art. 6 co. 1 a ogni scaglione, compresi i raddoppi successivi
    a 32 milioni (32-64 milioni +30%, 64-128 milioni +30% sul precedente, ecc.).
    Precisione: INDICATIVO (valori medi tabellari; il giudice può variare ±50% ex art. 4 DM 55/2014; l'aumento
    dell'art. 6 è solo "fino al 30 per cento", qui applicato per intero).
    Spesso chiamato come ultimo step nel workflow recupero crediti dopo decreto_ingiuntivo().

    Args:
        valore_causa: Valore della causa in euro (€)
        fasi: Fasi processuali da includere (default: tutte). Valori: 'studio', 'introduttiva', 'istruttoria', 'decisionale'
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if valore_causa < 0:
        return {"errore": "valore_causa non può essere negativo"}

    if fasi is None:
        fasi = list(_FASI_CIVILE)
    else:
        invalid = [f for f in fasi if f not in _FASI_CIVILE]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_CIVILE}"}

    scaglione = _find_scaglione_civile(valore_causa)
    scaglione_label = _scaglione_label(scaglione, _PARAMETRI["civile"]["scaglioni"])

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


@mcp.tool(tags={"parcelle_avv"})
@sourced("parametri_forensi")
def parcella_avvocato_penale(
    competenza: str,
    fasi: list[str] | None = None,
    livello: str = "medio",
) -> dict:
    """Calcola compenso tabellare avvocato per procedimento penale.
    Vigenza: DM 55/2014 aggiornato DM 147/2022 — Parametri forensi penale.
    Precisione: INDICATIVO (valori medi tabellari; il giudice può variare ±50% ex art. 4 DM 55/2014).

    Args:
        competenza: Organo giudicante: 'giudice_pace', 'tribunale_monocratico', 'tribunale_collegiale', 'corte_assise', 'corte_appello', 'cassazione'
        fasi: Fasi processuali da includere (default: tutte applicabili). Valori: 'studio', 'introduttiva', 'istruttoria', 'decisionale'
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if competenza not in _COMPETENZE_PENALE:
        return {"errore": f"Competenza non valida: {competenza}. Ammesse: {_COMPETENZE_PENALE}"}

    comp_data = next(c for c in _PARAMETRI["penale"]["competenze"] if c["tipo"] == competenza)

    if fasi is None:
        fasi = [f for f in _FASI_PENALE if comp_data[f] is not None]
    else:
        invalid = [f for f in fasi if f not in _FASI_PENALE]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_PENALE}"}
        unavailable = [f for f in fasi if comp_data[f] is None]
        if unavailable:
            return {"errore": f"Fasi non disponibili per {competenza}: {unavailable}"}

    dettaglio = []
    totale = 0.0
    for fase in fasi:
        importo = comp_data[fase][livello]
        totale += importo
        dettaglio.append({"fase": fase, "importo": importo})

    return {
        "competenza": competenza,
        "label": comp_data["label"],
        "livello": livello,
        "fasi": dettaglio,
        "totale_compenso": round(totale, 2),
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi penale",
    }


@mcp.tool(tags={"parcelle_avv"})
@sourced("parametri_forensi")
def parcella_stragiudiziale(
    valore_pratica: float,
    livello: str = "medio",
) -> dict:
    """Calcola compenso tabellare avvocato per attività stragiudiziale (diffida, trattativa, negoziazione).
    Vigenza: DM 55/2014 aggiornato DM 147/2022, Tab. 25 (art. 20 e 22); oltre 520.000 euro art. 22: percentuale
    decrescente del valore (3% fino a 2 milioni, 2,75% fino a 4, ... 0,25% oltre 22 milioni, applicata all'intero
    valore), verificata il 2026-09-29. Non copre mediazione e negoziazione assistita (Tab. 25-bis, per fasi).
    Precisione: INDICATIVO (valori medi tabellari arrotondati all'euro; il giudice può variare ±50% ex art. 19 DM 55/2014).

    Args:
        valore_pratica: Valore della pratica in euro (€)
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if valore_pratica < 0:
        return {"errore": "valore_pratica non può essere negativo"}

    scaglione = _find_scaglione_stragiudiziale(valore_pratica)
    scaglione_label = _label_stragiudiziale(scaglione)
    compenso = scaglione[livello]

    return {
        "valore_pratica": valore_pratica,
        "scaglione": scaglione_label,
        "livello": livello,
        "compenso": compenso,
        # only above 520.000: art. 22 DM 55/2014, Tab. 25, percent of the whole value
        **({"percentuale_tab_25": scaglione["pct"]} if scaglione.get("pct") is not None else {}),
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi attività stragiudiziale",
    }


@mcp.tool(tags={"parcelle_avv"})
@sourced("parametri_forensi")
def parcella_volontaria_giurisdizione(
    valore_causa: float,
    fasi: list[str] | None = None,
    livello: str = "medio",
) -> dict:
    """Calcola compenso tabellare per procedimento di volontaria giurisdizione (Tab. 7 DM 55/2014).

    Si applica esclusivamente a procedimenti non contenziosi: interdizioni, inabilitazioni,
    amministrazioni di sostegno, tutele, curatele, DAT, autorizzazioni giudiziali.
    Per procedimenti contenziosi usare parcella_avvocato_civile.
    Vigenza: DM 55/2014 aggiornato DM 147/2022, Tabella 7 (verificata il 2026-09-29: 425, 1.418, 2.336, 3.329, 4.536 medi).
    Precisione: INDICATIVO (valori medi tabellari arrotondati all'euro, la tabella riporta i centesimi, es. 212,50;
    il giudice può variare ±50%). Compenso unico per scaglione: la ripartizione studio/trattazione (50%) è
    convenzionale, non prevista dalla tabella. Oltre 520.000 euro la tabella non ha riga e si usa l'ultimo
    scaglione: l'aumento dell'art. 6 DM 55/2014 è solo "fino al 30 per cento" e non viene applicato
    (parcella_avvocato_civile applica invece il 30% pieno).

    Args:
        valore_causa: Valore della causa in euro (€)
        fasi: Fasi da includere (default: tutte). Valori: 'studio', 'trattazione'
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if valore_causa < 0:
        return {"errore": "valore_causa non può essere negativo"}

    if fasi is None:
        fasi = list(_FASI_VOLONTARIA)
    else:
        invalid = [f for f in fasi if f not in _FASI_VOLONTARIA]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_VOLONTARIA}"}

    scaglione = _find_scaglione_volontaria(valore_causa)
    scaglione_label = _scaglione_label(scaglione, _PARAMETRI["volontaria_giurisdizione"]["scaglioni"])

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
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Tab. 7 Volontaria giurisdizione",
    }


@mcp.tool(tags={"parcelle_avv"})
@sourced("parametri_forensi")
def preventivo_volontaria_giurisdizione(
    valore_causa: float,
    fasi: list[str] | None = None,
    livello: str = "medio",
    spese_generali: bool = True,
    cpa: bool = True,
    iva: bool = True,
) -> dict:
    """Genera preventivo completo per volontaria giurisdizione con spese generali (15%), CPA (4%) e IVA (22%).

    Si applica a procedimenti non contenziosi: interdizioni, inabilitazioni, amministrazioni di sostegno,
    tutele, curatele, DAT, autorizzazioni giudiziali.
    Vigenza: DM 55/2014 aggiornato DM 147/2022, Tabella 7 (verificata il 2026-09-29).
    Precisione: INDICATIVO per compensi (valori tabellari medi arrotondati all'euro; compenso unico per scaglione,
    la ripartizione studio/trattazione è convenzionale; oltre 520.000 euro si usa l'ultimo scaglione senza
    l'aumento facoltativo "fino al 30 per cento" dell'art. 6); ESATTO per CPA e IVA. Ogni riga è arrotondata al centesimo, con la metà per eccesso (art. 5 Reg. CE 1103/97).

    Args:
        valore_causa: Valore della causa in euro (€)
        fasi: Fasi da includere (default: tutte). Valori: 'studio', 'trattazione'
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
        spese_generali: Se aggiungere 15% spese generali (default: True)
        cpa: Se aggiungere CPA 4% Cassa Previdenza Avvocati (default: True)
        iva: Se aggiungere IVA 22% (default: True)
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if valore_causa < 0:
        return {"errore": "valore_causa non può essere negativo"}

    if fasi is None:
        fasi = list(_FASI_VOLONTARIA)
    else:
        invalid = [f for f in fasi if f not in _FASI_VOLONTARIA]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_VOLONTARIA}"}

    scaglione = _find_scaglione_volontaria(valore_causa)
    scaglione_label = _scaglione_label(scaglione, _PARAMETRI["volontaria_giurisdizione"]["scaglioni"])

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

    linee = [
        f"PREVENTIVO VOLONTARIA GIURISDIZIONE — Valore causa: €{valore_causa:,.2f}",
        f"Scaglione: {scaglione_label} | Livello: {livello}",
        "",
        "COMPENSI PROFESSIONALI (DM 55/2014 agg. DM 147/2022, Tab. 7):",
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
        },
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Tab. 7 Volontaria giurisdizione",
    }


@mcp.tool(tags={"parcelle_avv"})
def fattura_avvocato(
    imponibile: float,
    regime: str = "ordinario",
    cpa: bool = True,
) -> dict:
    """Genera struttura fattura avvocato con CPA, IVA e ritenuta d'acconto.
    Vigenza: L. 190/2014 (regime forfettario); DPR 633/1972 (IVA); DPR 600/1973 (ritenuta);
    DPR 642/1972 (imposta di bollo di 2 euro sulle fatture senza IVA oltre 77,47 euro).
    Precisione: ESATTO (importi di legge: CPA 4%, IVA 22%, ritenuta 20%, bollo 2 euro). Ogni riga è
        arrotondata al centesimo, con la metà per eccesso (art. 5 Reg. CE 1103/97).
    Convenzione: nel forfettario la CPA è calcolata sul solo compenso; il bollo riaddebitato è aggiunto dopo.
        L'AdE (risposta a interpello 428/2022) lo considera parte del compenso ai fini del reddito, ma
        la rivalsa della cassa è facoltativa e la norma di Cassa Forense non è stata verificata: chi la
        applica anche sul bollo aggiunge 0,08 euro (4% di 2 euro).

    Args:
        imponibile: Compenso professionale (imponibile) in euro (€)
        regime: Regime fiscale: 'ordinario' (IVA 22% + ritenuta 20%) o 'forfettario' (no IVA, no
                ritenuta; bollo di 2 euro se l'importo supera 77,47 euro)
        cpa: Se applicare Cassa Previdenza Avvocati 4% sull'imponibile (default: True)
    """
    if regime not in ("ordinario", "forfettario"):
        return {"errore": f"Regime non valido: {regime}. Usare: ordinario, forfettario"}

    if imponibile < 0:
        return {"errore": "imponibile non può essere negativo"}

    voci = [{"descrizione": "Compenso professionale", "importo": _q(imponibile)}]

    cpa_importo = 0.0
    if cpa:
        cpa_importo = _pct(imponibile, "4")
        voci.append({"descrizione": "CPA 4% (Cassa Previdenza Avvocati)", "importo": cpa_importo})

    imponibile_iva = _q(Decimal(str(imponibile)) + Decimal(str(cpa_importo)))

    iva_importo = 0.0
    ritenuta_importo = 0.0
    bollo = 0.0

    if regime == "ordinario":
        iva_importo = _pct(imponibile_iva, "22")
        ritenuta_importo = _pct(imponibile, "20")
        voci.append({"descrizione": "IVA 22%", "importo": iva_importo})
        voci.append({"descrizione": "Ritenuta d'acconto 20% (su compenso)", "importo": -ritenuta_importo})
        totale = _q(Decimal(str(imponibile_iva)) + Decimal(str(iva_importo)) - Decimal(str(ritenuta_importo)))
    else:
        voci.append({"descrizione": "IVA: esente (regime forfettario art. 1 c. 54-89 L. 190/2014)", "importo": 0.0})
        # Fattura senza IVA di importo superiore a 77,47 euro: imposta di bollo di 2 euro
        # (art. 13 Tariffa parte I DPR 642/1972), a carico del cliente se addebitata in fattura
        if imponibile_iva > 77.47:
            bollo = 2.0
            voci.append({"descrizione": "Imposta di bollo (DPR 642/1972)", "importo": bollo})
        totale = _q(Decimal(str(imponibile_iva)) + Decimal(str(bollo)))

    return {
        "regime": regime,
        "imponibile": _q(imponibile),
        "cpa_4pct": cpa_importo,
        "imponibile_iva": imponibile_iva,
        "iva_22pct": iva_importo,
        "ritenuta_acconto_20pct": ritenuta_importo,
        "bollo": bollo,
        "totale_fattura": totale,
        "netto_a_pagare": totale,
        "voci": voci,
    }


@mcp.tool(tags={"parcelle_avv"})
def nota_spese(
    voci: list[dict],
) -> dict:
    """Calcola nota spese avvocato aggregando voci di compenso, spese generali (15%), CPA (4%) e IVA (22%).
    Vigenza: DM 55/2014 art. 2 co. 2 (spese generali 15%).
    Precisione: ESATTO per percentuali di legge; INDICATIVO per voci di compenso inserite manualmente.
        Ogni riga è arrotondata al centesimo, con la metà per eccesso (art. 5 Reg. CE 1103/97).

    Args:
        voci: Lista di voci, ciascuna con: descrizione (str), importo (float in €), tipo ('compenso', 'spese_generali_15pct', 'spese_vive', 'spese_documentate')
    """
    tipi_validi = {"compenso", "spese_generali_15pct", "spese_vive", "spese_documentate"}
    for v in voci:
        if v.get("tipo") not in tipi_validi:
            return {"errore": f"Tipo voce non valido: {v.get('tipo')}. Ammessi: {sorted(tipi_validi)}"}
        if "importo" not in v or "descrizione" not in v:
            return {"errore": f"Voce incompleta: {v}. Richiesti 'descrizione' e 'importo'."}

    dettaglio = []
    totale_compensi = 0.0
    totale_spese_generali = 0.0
    totale_spese_vive = 0.0

    for v in voci:
        importo = _q(v["importo"])
        tipo = v["tipo"]

        if tipo == "compenso":
            totale_compensi += importo
            dettaglio.append({"descrizione": v["descrizione"], "tipo": tipo, "importo": importo})
        elif tipo == "spese_generali_15pct":
            sg = _pct(v["importo"], "15")
            totale_spese_generali += sg
            dettaglio.append({"descrizione": v["descrizione"] + " (15% spese generali)", "tipo": tipo, "importo": sg})
        elif tipo in ("spese_vive", "spese_documentate"):
            totale_spese_vive += importo
            dettaglio.append({"descrizione": v["descrizione"], "tipo": tipo, "importo": importo})

    subtotale = _q(totale_compensi + totale_spese_generali)
    cpa = _pct(subtotale, "4")
    imponibile_iva = _q(subtotale + cpa)
    iva = _pct(imponibile_iva, "22")
    totale = _q(imponibile_iva + iva + totale_spese_vive)

    return {
        "dettaglio_voci": dettaglio,
        "totale_compensi": _q(totale_compensi),
        "totale_spese_generali_15pct": _q(totale_spese_generali),
        "subtotale_compensi": subtotale,
        "cpa_4pct": cpa,
        "imponibile_iva": imponibile_iva,
        "iva_22pct": iva,
        "totale_spese_vive": _q(totale_spese_vive),
        "totale_nota_spese": totale,
        "riferimento_normativo": "DM 55/2014 — Art. 2 c. 2 spese generali 15%",
    }


# --- Spese vive stimate per tipo procedimento civile ---
_SPESE_VIVE_STIMATE = {
    "marca_da_bollo": 27.0,
    "notifica_pec": 3.54,
    "notifica_ufficiale_giudiziario": 27.0,
    "diritti_copia": 15.0,
}


def _contributo_unificato(valore_causa: float) -> float:
    """Contributo unificato di cognizione for a claim of this value.

    The bands come from `contributo_unificato.json` (DPR 115/2002), the same
    table `contributo_unificato` and `decreto_ingiuntivo` answer from, so an
    update to the table moves this estimate too and the vintage line below
    describes the numbers actually applied.
    """
    for scaglione in _CU_CIVILE:
        if scaglione.get("oltre") or valore_causa <= scaglione["fino_a"]:
            return float(scaglione["importo"])
    return float(_CU_CIVILE[-1]["importo"])


@mcp.tool(tags={"parcelle_avv"})
@sourced("contributo_unificato", "parametri_forensi")
def preventivo_civile(
    valore_causa: float,
    fasi: list[str] | None = None,
    livello: str = "medio",
    spese_generali: bool = True,
    cpa: bool = True,
    iva: bool = True,
) -> dict:
    """Genera preventivo completo per causa civile: compensi tabellari, spese generali (15%), CPA (4%), IVA (22%) e spese vive stimate.
    Vigenza: DM 55/2014 aggiornato DM 147/2022; contributo unificato ex DPR 115/2002 (importi di legge).
    Precisione: INDICATIVO per compensi (valori tabellari medi); ESATTO per contributo unificato e CPA/IVA.

    Args:
        valore_causa: Valore della causa in euro (€)
        fasi: Fasi processuali (default: tutte). Valori: 'studio', 'introduttiva', 'istruttoria', 'decisionale'
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
        spese_generali: Se aggiungere 15% spese generali (default: True)
        cpa: Se aggiungere CPA 4% Cassa Previdenza Avvocati (default: True)
        iva: Se aggiungere IVA 22% (default: True)
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if valore_causa < 0:
        return {"errore": "valore_causa non può essere negativo"}

    if fasi is None:
        fasi = list(_FASI_CIVILE)
    else:
        invalid = [f for f in fasi if f not in _FASI_CIVILE]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_CIVILE}"}

    scaglione = _find_scaglione_civile(valore_causa)
    scaglione_label = _scaglione_label(scaglione, _PARAMETRI["civile"]["scaglioni"])

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


@mcp.tool(tags={"parcelle_avv"})
@sourced("parametri_forensi")
def preventivo_stragiudiziale(
    valore_pratica: float,
    livello: str = "medio",
    spese_generali: bool = True,
    cpa: bool = True,
    iva: bool = True,
) -> dict:
    """Genera preventivo per attività stragiudiziale (diffida, trattativa) con spese generali (15%), CPA (4%) e IVA (22%).
    Vigenza: DM 55/2014 aggiornato DM 147/2022, Tab. 25; oltre 520.000 euro art. 22 (percentuale decrescente del
    valore, applicata all'intero valore), verificata il 2026-09-29. Non copre la mediazione e la negoziazione
    assistita (Tab. 25-bis, compensi per fasi): per quelle il compenso è diverso.
    Precisione: INDICATIVO per compensi (valori tabellari medi arrotondati all'euro); ESATTO per CPA e IVA.

    Args:
        valore_pratica: Valore della pratica in euro (€)
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
        spese_generali: Se aggiungere 15% spese generali (default: True)
        cpa: Se aggiungere CPA 4% Cassa Previdenza Avvocati (default: True)
        iva: Se aggiungere IVA 22% (default: True)
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}

    if valore_pratica < 0:
        return {"errore": "valore_pratica non può essere negativo"}

    scaglione = _find_scaglione_stragiudiziale(valore_pratica)
    scaglione_label = _label_stragiudiziale(scaglione)
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
            **({"percentuale_tab_25": scaglione["pct"]} if scaglione.get("pct") is not None else {}),
            "spese_generali_15pct": sg_importo,
            "subtotale": subtotale,
            "cpa_4pct": cpa_importo,
            "imponibile_iva": imponibile_iva,
            "iva_22pct": iva_importo,
            "totale": totale,
        },
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi attività stragiudiziale",
    }


@mcp.tool(tags={"parcelle_avv"})
def spese_trasferta_avvocati(
    km_distanza: float,
    ore_assenza: float,
    pernottamento: bool = False,
    mezzo: str = "auto",
    prezzo_carburante_litro: float | None = None,
    costo_albergo: float = 0.0,
    pedaggi_parcheggi: float = 0.0,
) -> dict:
    """Calcola indennità di trasferta e rimborso chilometrico per avvocati.
    Vigenza: DM 55/2014 art. 27 co. 1 (vigente al 2026-09-29, testo DM 147/2022): indennità chilometrica
        pari a un quinto del costo del carburante al litro, pedaggi e parcheggi documentati, albergo
        documentato (limite quattro stelle) con maggiorazione del 10% per spese accessorie.
    Precisione: INDICATIVO (la norma non fissa l'indennità di trasferta: l'importo base di 540 euro e le
        percentuali orarie sono stime del tool). Il rimborso chilometrico è ESATTO solo se si passa
        prezzo_carburante_litro; senza, applica 0,30 euro/km, cioè un carburante a 1,50 euro/litro.

    Args:
        km_distanza: Distanza andata/ritorno in km (valore positivo)
        ore_assenza: Ore di assenza dallo studio (es. 3.5)
        pernottamento: True se è necessario il pernottamento (rimborso a piè di lista)
        mezzo: Mezzo di trasporto: 'auto' (indennità chilometrica), 'treno' (a piè di lista), 'aereo' (a piè di lista)
        prezzo_carburante_litro: Prezzo del carburante al litro in euro (€): l'indennità chilometrica è un quinto
            di questo prezzo per km (art. 27 DM 55/2014). Se omesso: 0,30 euro/km (carburante a 1,50 euro/litro)
        costo_albergo: Costo documentato del soggiorno in euro (€), da liquidare con maggiorazione del 10%
        pedaggi_parcheggi: Pedaggio autostradale e parcheggio documentati in euro (€), a piè di lista
    """
    if mezzo not in ("auto", "treno", "aereo"):
        return {"errore": f"Mezzo non valido: {mezzo}. Usare: auto, treno, aereo"}

    if km_distanza < 0:
        return {"errore": "km_distanza non può essere negativo"}

    if ore_assenza < 0:
        return {"errore": "ore_assenza non può essere negativo"}

    if prezzo_carburante_litro is not None and prezzo_carburante_litro < 0:
        return {"errore": "prezzo_carburante_litro non può essere negativo"}
    if costo_albergo < 0 or pedaggi_parcheggi < 0:
        return {"errore": "costo_albergo e pedaggi_parcheggi non possono essere negativi"}

    # Rimborso chilometrico (solo auto): un quinto del costo del carburante al litro per km (art. 27)
    if prezzo_carburante_litro is None:
        euro_km = Decimal("0.30")
        carburante_note = "prezzo carburante non indicato: applicati 0,30 euro/km (carburante a 1,50 euro/litro)"
    else:
        euro_km = Decimal(str(prezzo_carburante_litro)) / 5
        carburante_note = f"un quinto di {prezzo_carburante_litro} euro/litro"
    rimborso_km = _q(Decimal(str(km_distanza)) * euro_km) if mezzo == "auto" else 0.0
    albergo_maggiorato = _pct(costo_albergo, "110")
    extra_documentati = _q(Decimal(str(albergo_maggiorato)) + Decimal(str(pedaggi_parcheggi)))

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
        voci.append({"voce": f"Rimborso km ({km_distanza} km × {euro_km:.4f} €/km, {carburante_note})", "importo": rimborso_km})
    else:
        voci.append({"voce": f"Rimborso {mezzo}: a piè di lista", "importo": 0.0})

    nota_pernottamento = None
    if pernottamento:
        nota_pernottamento = "Pernottamento: rimborso a piè di lista su presentazione di ricevuta/fattura"
        voci.append({"voce": "Pernottamento", "importo": 0.0, "nota": "a piè di lista"})

    if costo_albergo:
        voci.append({"voce": "Albergo documentato +10% spese accessorie", "importo": albergo_maggiorato})
    if pedaggi_parcheggi:
        voci.append({"voce": "Pedaggi e parcheggi documentati", "importo": pedaggi_parcheggi})

    totale_stimato = _q(Decimal(str(indennita)) + Decimal(str(rimborso_km)) + Decimal(str(extra_documentati)))

    return {
        "km_distanza": km_distanza,
        "ore_assenza": ore_assenza,
        "mezzo": mezzo,
        "pernottamento": pernottamento,
        "indennita_trasferta": indennita,
        "percentuale_indennita": pct_indennita,
        "rimborso_km": rimborso_km,
        "albergo_maggiorato_10pct": albergo_maggiorato,
        "pedaggi_parcheggi": pedaggi_parcheggi,
        "totale_stimato": totale_stimato,
        "voci": voci,
        "nota_pernottamento": nota_pernottamento,
        "note": [
            "L'indennità è calcolata come percentuale dell'onorario medio (scaglione €26.000, fase studio)",
            "Per treno/aereo il rimborso è a piè di lista su documentazione",
            "Il pernottamento è rimborsato a piè di lista (costo_albergo, limite quattro stelle) con maggiorazione del 10%",
        ],
        "riferimento_normativo": "DM 55/2014 art. 27 — Spese di trasferta avvocati",
    }


# Procedimenti tipici di recupero crediti. Each one is paid on its OWN table of the
# DM 55/2014 (agg. DM 147/2022), not on the phases of the tribunal's cognizione:
# Tab. VIII (monitori, fase unica), Tab. VI (precetto, fase unica), Tab. XVI
# (esecuzioni mobiliari), Tab. XVII (presso terzi, consegna e rilascio), Tab. XVIII
# (immobiliari). The tables live in parametri_forensi.json, "notula_recupero_crediti".
_NOTULA = _PARAMETRI["notula_recupero_crediti"]

#: Art. 30 DPR 115/2002: 27 euro of forfait paid by the party who files the ricorso
#: or, in the espropriazione forzata, asks for the assegnazione or the sale. A
#: precetto is not a proceeding, so no forfait is due for it.
_ANTICIPAZIONE_FORFETTARIA = 27.0

_NOTULA_PROCEDIMENTI = {
    "decreto_ingiuntivo": {
        "tabella": "monitorio",
        "descrizione": "Ricorso per decreto ingiuntivo (Tab. VIII, procedimenti monitori)",
        "spese_vive_stimate": {"contributo_unificato_dimezzato": True, "anticipazione_forfettaria": True},
    },
    "precetto": {
        "tabella": "precetto",
        "descrizione": "Atto di precetto (Tab. VI)",
        "spese_vive_stimate": {"notifica": 27.0},
    },
    "esecuzione_mobiliare": {
        "tabella": "esecuzione_mobiliare",
        "descrizione": "Esecuzione mobiliare presso il debitore (Tab. XVI)",
        "spese_vive_stimate": {"contributo_unificato_esecuzione_mobiliare": True, "anticipazione_forfettaria": True},
    },
    "esecuzione_presso_terzi": {
        "tabella": "esecuzione_presso_terzi",
        "descrizione": "Esecuzione presso terzi, consegna e rilascio (Tab. XVII)",
        "spese_vive_stimate": {"contributo_unificato_esecuzione_mobiliare": True, "anticipazione_forfettaria": True},
    },
    "esecuzione_immobiliare": {
        "tabella": "esecuzione_immobiliare",
        "descrizione": "Esecuzione immobiliare (Tab. XVIII)",
        "spese_vive_stimate": {
            "contributo_unificato_esecuzione_immobiliare": True,
            "anticipazione_forfettaria": True,
            "trascrizione": 300.0,
        },
    },
}

#: Contributo unificato of the executions, art. 13 co. 2 DPR 115/2002 (43 below
#: 2.500 euro, 139 from 2.500; 278 for the immobiliari), from the shared table.
_CU_CIVILE_TUTTO: dict = json.loads((_DATA / "contributo_unificato.json").read_text())["civile"]
_CU_ESEC_MOBILIARE: list[dict] = _CU_CIVILE_TUTTO["esecuzione_mobiliare"]["scaglioni"]
_CU_ESEC_IMMOBILIARE: float = float(_CU_CIVILE_TUTTO["esecuzione_immobiliare"])

_LIVELLO_FATTORE = {"min": Decimal("0.5"), "medio": Decimal("1"), "max": Decimal("1.5")}


def _round_euro(x: Decimal | float) -> float:
    """Whole euro, half up: the convention of the module (the tables print cents)."""
    return float(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _find_notula_scaglione(scaglioni: list[dict], valore: float) -> dict:
    for s in scaglioni:
        if s.get("oltre") or valore <= s["fino_a"]:
            return s
    return scaglioni[-1]


@mcp.tool(tags={"parcelle_avv"})
@sourced("contributo_unificato", "parametri_forensi")
def modello_notula(
    tipo_procedimento: str,
    avvocato: str,
    cliente: str,
    valore_causa: float,
    fasi: list[str] | None = None,
    livello: str = "medio",
) -> dict:
    """Genera notula (nota spese) completa formattata per procedimenti tipici di recupero crediti.
    Ogni procedimento si liquida sulla PROPRIA tabella del DM 55/2014: Tab. VIII (monitorio, fase unica),
    Tab. VI (precetto), Tab. XVI (esecuzione mobiliare), Tab. XVII (presso terzi, consegna e rilascio),
    Tab. XVIII (esecuzione immobiliare). Contributo unificato: art. 13 DPR 115/2002 (monitorio meta' della
    cognizione; esecuzioni importi fissi del comma 2, 43 sotto 2.500 euro e 139 da 2.500 per le mobiliari,
    278 per le immobiliari; nessun contributo per il precetto). Anticipazione forfettaria di 27 euro
    (art. 30 DPR 115/2002) per ricorso monitorio ed esecuzioni, non per il precetto.
    Vigenza: DM 55/2014 aggiornato DM 147/2022 (tabelle allegate); DPR 115/2002 artt. 13 e 30, verificati il 2026-09-29.
    Precisione: INDICATIVO per compensi (valori tabellari medi arrotondati all'euro, le tabelle riportano i
    centesimi; il giudice puo' variare -/+50% ex art. 19 DM 55/2014); oltre 520.000 euro le tabelle non hanno
    riga e si usa l'ultimo scaglione, senza l'aumento facoltativo dell'art. 6. ESATTO per contributo unificato
    e CPA/IVA. Notifica del precetto (27) e trascrizione del pignoramento immobiliare (300) sono STIME senza fonte.

    Args:
        tipo_procedimento: Tipo: 'decreto_ingiuntivo', 'precetto', 'esecuzione_mobiliare', 'esecuzione_presso_terzi', 'esecuzione_immobiliare'
        avvocato: Nome e cognome dell'avvocato
        cliente: Nome e cognome / ragione sociale del cliente
        valore_causa: Valore della causa in euro (€)
        fasi: Fasi della tabella del procedimento (default: tutte). 'unica' per monitorio e precetto; 'studio' e 'trattazione' per l'esecuzione mobiliare; 'introduttiva' e 'trattazione' per presso terzi e immobiliare
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
    """
    if tipo_procedimento not in _NOTULA_PROCEDIMENTI:
        return {"errore": f"Tipo non valido: {tipo_procedimento}. Ammessi: {list(_NOTULA_PROCEDIMENTI.keys())}"}
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}
    if valore_causa < 0:
        return {"errore": "valore_causa non può essere negativo"}

    proc = _NOTULA_PROCEDIMENTI[tipo_procedimento]
    tabella = _NOTULA[proc["tabella"]]
    fasi_ammesse = tabella["fasi"]
    if fasi is None:
        fasi = list(fasi_ammesse)
    else:
        invalid = [f for f in fasi if f not in fasi_ammesse]
        if invalid:
            return {"errore": f"Fasi non valide per {tipo_procedimento}: {invalid}. Ammesse: {fasi_ammesse}"}
        if len(set(fasi)) != len(fasi):
            return {"errore": f"Fasi duplicate: {fasi}"}

    scaglione = _find_notula_scaglione(tabella["scaglioni"], valore_causa)
    fattore = _LIVELLO_FATTORE[livello]

    dettaglio_fasi = []
    totale_compensi = 0.0
    for fase in fasi:
        importo = _round_euro(Decimal(str(scaglione[fase])) * fattore)
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
    if sv.get("contributo_unificato_dimezzato"):
        spese_vive_det["contributo_unificato_dimezzato"] = round(_contributo_unificato(valore_causa) / 2, 2)
    if sv.get("contributo_unificato_esecuzione_mobiliare"):
        # art. 13 co. 2 DPR 115/2002: 43 below 2.500 euro, 139 from 2.500
        spese_vive_det["contributo_unificato"] = float(
            _find_notula_scaglione(_CU_ESEC_MOBILIARE, valore_causa)["importo"]
        )
    if sv.get("contributo_unificato_esecuzione_immobiliare"):
        spese_vive_det["contributo_unificato"] = _CU_ESEC_IMMOBILIARE
    if sv.get("anticipazione_forfettaria"):
        spese_vive_det["anticipazione_forfettaria_art_30"] = _ANTICIPAZIONE_FORFETTARIA
    if sv.get("notifica"):
        spese_vive_det["notifica"] = sv["notifica"]
    if sv.get("trascrizione"):
        spese_vive_det["trascrizione"] = sv["trascrizione"]
    totale_spese_vive = round(sum(spese_vive_det.values()), 2)
    totale_notula = round(totale_onorari + totale_spese_vive, 2)

    avvertenze = []
    if valore_causa > tabella["scaglioni"][-1]["fino_a"]:
        avvertenze.append(
            "Valore oltre 520.000 euro: le tabelle non hanno una riga propria, applicato l'ultimo scaglione "
            "(l'art. 6 DM 55/2014 consente un aumento fino al 30 per cento, non applicato)."
        )

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
            "tabella": tabella["_tabella"],
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
        "avvertenze": avvertenze,
        "riferimento_normativo": f"DM 55/2014 aggiornato DM 147/2022, {tabella['_tabella']}",
    }


@mcp.tool(tags={"parcelle_avv"})
@sourced("parametri_forensi")
def calcolo_notula_penale(
    competenza: str,
    fasi: list[str] | None = None,
    livello: str = "medio",
    spese_generali: bool = True,
) -> dict:
    """Calcola parcella penale completa con spese generali (15%), CPA (4%) e IVA (22%).
    Equivalente a parcella_avvocato_penale ma include già il calcolo del totale con accessori.
    Vigenza: DM 55/2014 aggiornato DM 147/2022 — Parametri forensi penale.
    Precisione: INDICATIVO per compensi (valori tabellari medi); ESATTO per CPA e IVA.

    Args:
        competenza: Organo giudicante: 'giudice_pace', 'tribunale_monocratico', 'tribunale_collegiale', 'corte_assise', 'corte_appello', 'cassazione'
        fasi: Fasi processuali (default: tutte applicabili). Valori: 'studio', 'introduttiva', 'istruttoria', 'decisionale'
        livello: Livello compenso tabellare: 'min', 'medio', 'max'
        spese_generali: Se aggiungere 15% spese generali art. 2 DM 55/2014 (default: True)
    """
    if livello not in ("min", "medio", "max"):
        return {"errore": f"Livello non valido: {livello}. Usare: min, medio, max"}
    if competenza not in _COMPETENZE_PENALE:
        return {"errore": f"Competenza non valida: {competenza}. Ammesse: {_COMPETENZE_PENALE}"}

    comp_data = next(c for c in _PARAMETRI["penale"]["competenze"] if c["tipo"] == competenza)

    if fasi is None:
        fasi = [f for f in _FASI_PENALE if comp_data[f] is not None]
    else:
        invalid = [f for f in fasi if f not in _FASI_PENALE]
        if invalid:
            return {"errore": f"Fasi non valide: {invalid}. Ammesse: {_FASI_PENALE}"}
        unavailable = [f for f in fasi if comp_data[f] is None]
        if unavailable:
            return {"errore": f"Fasi non disponibili per {competenza}: {unavailable}"}

    dettaglio_fasi = []
    totale_compensi = 0.0
    for fase in fasi:
        importo = comp_data[fase][livello]
        totale_compensi += importo
        dettaglio_fasi.append({"fase": fase, "importo": importo})

    sg_importo = _pct(totale_compensi, "15") if spese_generali else 0.0
    subtotale = _q(totale_compensi + sg_importo)
    cpa_importo = _pct(subtotale, "4")
    imponibile_iva = _q(subtotale + cpa_importo)
    iva_importo = _pct(imponibile_iva, "22")
    totale = _q(imponibile_iva + iva_importo)

    return {
        "competenza": competenza,
        "label": comp_data["label"],
        "livello": livello,
        "fasi": dettaglio_fasi,
        "totale_compensi": _q(totale_compensi),
        "spese_generali_15pct": sg_importo,
        "subtotale": subtotale,
        "cpa_4pct": cpa_importo,
        "imponibile_iva": imponibile_iva,
        "iva_22pct": iva_importo,
        "totale": totale,
        "riferimento_normativo": "DM 55/2014 aggiornato DM 147/2022 — Parametri forensi penale",
    }
