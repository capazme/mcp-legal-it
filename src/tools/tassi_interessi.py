"""Sezione 2 — Tassi e Interessi: interessi legali, mora, ammortamento, usura."""

import json
from datetime import date, timedelta
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "tassi_legali.json") as f:
    _TASSI_LEGALI = json.load(f)["tassi"]

with open(_DATA / "tassi_mora.json") as f:
    _TASSI_MORA = json.load(f)["tassi"]


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _get_tasso_legale(d: date) -> float:
    """Return the legal interest rate applicable on a given date."""
    for t in _TASSI_LEGALI:
        if _parse_date(t["dal"]) <= d <= _parse_date(t["al"]):
            return t["tasso"]
    return _TASSI_LEGALI[-1]["tasso"]


def _get_tasso_mora(d: date) -> dict:
    """Return mora rate info for a given date."""
    for t in _TASSI_MORA:
        if _parse_date(t["dal"]) <= d <= _parse_date(t["al"]):
            return t
    return _TASSI_MORA[-1]


def _days_in_year(year: int) -> int:
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


@mcp.tool()
def interessi_legali(
    capitale: float,
    data_inizio: str,
    data_fine: str,
    tipo: str = "semplici",
) -> dict:
    """Calcola interessi legali art. 1284 c.c. tra due date.

    Args:
        capitale: Importo del capitale in euro
        data_inizio: Data inizio decorrenza (YYYY-MM-DD)
        data_fine: Data fine decorrenza (YYYY-MM-DD)
        tipo: 'semplici' o 'composti'
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    periodi = []
    current = dt_inizio
    montante = capitale
    totale_interessi = 0.0

    while current < dt_fine:
        tasso = _get_tasso_legale(current)
        # Find end of current rate period
        next_change = dt_fine
        for t in _TASSI_LEGALI:
            al = _parse_date(t["al"])
            if al >= current and al < next_change:
                dal = _parse_date(t["dal"])
                if dal <= current <= al and al < dt_fine:
                    next_change = al + timedelta(days=1)

        periodo_fine = min(next_change, dt_fine)
        giorni = (periodo_fine - current).days
        anno = _days_in_year(current.year)

        if tipo == "composti":
            interessi_periodo = montante * (tasso / 100) * giorni / anno
            montante += interessi_periodo
        else:
            interessi_periodo = capitale * (tasso / 100) * giorni / anno

        totale_interessi += interessi_periodo
        periodi.append({
            "dal": current.isoformat(),
            "al": (periodo_fine - timedelta(days=1) if periodo_fine != dt_fine else dt_fine).isoformat(),
            "giorni": giorni,
            "tasso_pct": tasso,
            "interessi": round(interessi_periodo, 2),
        })
        current = periodo_fine

    return {
        "capitale": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "tipo": tipo,
        "totale_interessi": round(totale_interessi, 2),
        "montante": round(capitale + totale_interessi, 2),
        "periodi": periodi,
    }


@mcp.tool()
def interessi_mora(
    capitale: float,
    data_inizio: str,
    data_fine: str,
) -> dict:
    """Calcola interessi di mora D.Lgs. 231/2002 per transazioni commerciali.

    Args:
        capitale: Importo del credito in euro
        data_inizio: Data decorrenza mora (YYYY-MM-DD)
        data_fine: Data calcolo (YYYY-MM-DD)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    periodi = []
    current = dt_inizio
    totale_interessi = 0.0

    while current < dt_fine:
        info = _get_tasso_mora(current)
        periodo_fine = min(_parse_date(info["al"]) + timedelta(days=1), dt_fine)
        giorni = (periodo_fine - current).days
        anno = _days_in_year(current.year)
        interessi_periodo = capitale * (info["mora"] / 100) * giorni / anno

        totale_interessi += interessi_periodo
        periodi.append({
            "dal": current.isoformat(),
            "al": (periodo_fine - timedelta(days=1)).isoformat(),
            "giorni": giorni,
            "tasso_bce_pct": info["bce"],
            "tasso_mora_pct": info["mora"],
            "interessi": round(interessi_periodo, 2),
        })
        current = periodo_fine

    return {
        "capitale": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "totale_interessi": round(totale_interessi, 2),
        "totale_dovuto": round(capitale + totale_interessi, 2),
        "riferimento_normativo": "D.Lgs. 231/2002 — tasso BCE + 8 punti percentuali",
        "periodi": periodi,
    }


@mcp.tool()
def interessi_tasso_fisso(
    capitale: float,
    tasso_annuo: float,
    data_inizio: str,
    data_fine: str,
    tipo: str = "semplici",
) -> dict:
    """Calcola interessi a tasso fisso personalizzato.

    Args:
        capitale: Importo del capitale in euro
        tasso_annuo: Tasso annuo percentuale (es. 3.5 per 3,5%)
        data_inizio: Data inizio (YYYY-MM-DD)
        data_fine: Data fine (YYYY-MM-DD)
        tipo: 'semplici' o 'composti'
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)
    giorni = (dt_fine - dt_inizio).days

    if giorni <= 0:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    if tipo == "composti":
        anni = giorni / 365.0
        montante = capitale * ((1 + tasso_annuo / 100) ** anni)
        interessi = montante - capitale
    else:
        anno = _days_in_year(dt_inizio.year)
        interessi = capitale * (tasso_annuo / 100) * giorni / anno
        montante = capitale + interessi

    return {
        "capitale": capitale,
        "tasso_annuo_pct": tasso_annuo,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "giorni": giorni,
        "tipo": tipo,
        "interessi": round(interessi, 2),
        "montante": round(montante, 2),
    }


@mcp.tool()
def calcolo_ammortamento(
    capitale: float,
    tasso_annuo: float,
    durata_mesi: int,
    tipo: str = "francese",
) -> dict:
    """Calcola piano di ammortamento mutuo.

    Args:
        capitale: Importo del mutuo in euro
        tasso_annuo: Tasso annuo percentuale (es. 3.5)
        durata_mesi: Durata in mesi
        tipo: 'francese' (rata costante) o 'italiano' (quota capitale costante)
    """
    tasso_mensile = tasso_annuo / 100 / 12
    rate = []

    if tipo == "francese":
        if tasso_mensile > 0:
            rata = capitale * tasso_mensile / (1 - (1 + tasso_mensile) ** (-durata_mesi))
        else:
            rata = capitale / durata_mesi

        debito_residuo = capitale
        totale_interessi = 0.0

        for i in range(1, durata_mesi + 1):
            interessi = debito_residuo * tasso_mensile
            quota_capitale = rata - interessi
            debito_residuo -= quota_capitale
            totale_interessi += interessi
            rate.append({
                "rata_n": i,
                "rata": round(rata, 2),
                "quota_capitale": round(quota_capitale, 2),
                "quota_interessi": round(interessi, 2),
                "debito_residuo": round(max(debito_residuo, 0), 2),
            })

    else:  # italiano
        quota_capitale_fissa = capitale / durata_mesi
        debito_residuo = capitale
        totale_interessi = 0.0

        for i in range(1, durata_mesi + 1):
            interessi = debito_residuo * tasso_mensile
            rata = quota_capitale_fissa + interessi
            debito_residuo -= quota_capitale_fissa
            totale_interessi += interessi
            rate.append({
                "rata_n": i,
                "rata": round(rata, 2),
                "quota_capitale": round(quota_capitale_fissa, 2),
                "quota_interessi": round(interessi, 2),
                "debito_residuo": round(max(debito_residuo, 0), 2),
            })

    return {
        "capitale": capitale,
        "tasso_annuo_pct": tasso_annuo,
        "durata_mesi": durata_mesi,
        "tipo": tipo,
        "rata_iniziale": rate[0]["rata"] if rate else 0,
        "totale_interessi": round(totale_interessi, 2),
        "totale_pagato": round(capitale + totale_interessi, 2),
        "piano": rate,
    }


@mcp.tool()
def verifica_usura(
    tasso_applicato: float,
    tipo_operazione: str = "mutuo_prima_casa",
    trimestre: str = "2024-Q4",
) -> dict:
    """Verifica superamento tasso soglia usura ex art. 644 c.p.

    Args:
        tasso_applicato: TAEG applicato dal finanziatore (percentuale)
        tipo_operazione: Tipo di finanziamento (mutuo_prima_casa, credito_personale, apertura_credito, leasing, factoring, carte_revolving)
        trimestre: Trimestre di riferimento (es. 2024-Q4)
    """
    # Tassi soglia indicativi (da aggiornare trimestralmente da Banca d'Italia)
    # Formula soglia: TEGM * 1.25 + 4 (con tetto: TEGM + 8)
    tegm_indicativi = {
        "mutuo_prima_casa": {"tegm": 4.41, "descrizione": "Mutui a tasso fisso"},
        "mutuo_tasso_variabile": {"tegm": 4.87, "descrizione": "Mutui a tasso variabile"},
        "credito_personale": {"tegm": 10.78, "descrizione": "Prestiti personali"},
        "apertura_credito": {"tegm": 11.82, "descrizione": "Aperture di credito in c/c"},
        "leasing": {"tegm": 7.35, "descrizione": "Leasing"},
        "factoring": {"tegm": 6.12, "descrizione": "Factoring"},
        "carte_revolving": {"tegm": 16.53, "descrizione": "Carte di credito revolving"},
        "cessione_quinto": {"tegm": 10.02, "descrizione": "Cessione del quinto"},
    }

    info = tegm_indicativi.get(tipo_operazione, tegm_indicativi["credito_personale"])
    tegm = info["tegm"]

    # Formula tasso soglia usura (L. 108/1996 come modificata dal DL 70/2011)
    soglia_formula = tegm * 1.25 + 4
    soglia_tetto = tegm + 8
    tasso_soglia = min(soglia_formula, soglia_tetto)

    usurario = tasso_applicato > tasso_soglia
    prossimo_a_usura = tasso_applicato > (tasso_soglia * 0.9)

    return {
        "tasso_applicato_pct": tasso_applicato,
        "tipo_operazione": tipo_operazione,
        "descrizione": info["descrizione"],
        "trimestre": trimestre,
        "tegm_pct": tegm,
        "tasso_soglia_pct": round(tasso_soglia, 2),
        "formula": f"min(TEGM×1.25+4, TEGM+8) = min({round(soglia_formula, 2)}, {round(soglia_tetto, 2)})",
        "usurario": usurario,
        "prossimo_a_usura": prossimo_a_usura,
        "margine": round(tasso_soglia - tasso_applicato, 2),
        "riferimento_normativo": "Art. 644 c.p. — L. 108/1996 — DL 70/2011 conv. L. 106/2011",
    }
