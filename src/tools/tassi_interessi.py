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


@mcp.tool()
def interessi_acconti(
    capitale: float,
    data_inizio: str,
    acconti: list[dict],
    data_fine: str,
) -> dict:
    """Calcolo interessi legali con acconti intermedi.

    Sottrae ogni acconto dal capitale residuo e ricalcola gli interessi
    sul residuo per ciascun sotto-periodo.

    Args:
        capitale: Importo del capitale iniziale in euro
        data_inizio: Data inizio decorrenza (YYYY-MM-DD)
        acconti: Lista di acconti, ciascuno con 'data' (YYYY-MM-DD) e 'importo' (float)
        data_fine: Data fine decorrenza (YYYY-MM-DD)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    # Sort acconti by date
    acconti_sorted = sorted(acconti, key=lambda a: a["data"])

    periodi = []
    capitale_residuo = capitale
    totale_interessi = 0.0
    current = dt_inizio

    # Build period boundaries: start, each acconto date, end
    boundaries = []
    for acc in acconti_sorted:
        dt_acc = _parse_date(acc["data"])
        if dt_inizio < dt_acc < dt_fine:
            boundaries.append((dt_acc, acc["importo"]))

    boundaries.append((dt_fine, 0))

    for dt_boundary, importo_acconto in boundaries:
        if current >= dt_boundary:
            if importo_acconto > 0:
                capitale_residuo -= importo_acconto
            continue

        # Calculate interests for this sub-period
        sub_current = current
        interessi_periodo = 0.0

        while sub_current < dt_boundary:
            tasso = _get_tasso_legale(sub_current)
            # Find end of current rate period
            next_change = dt_boundary
            for t in _TASSI_LEGALI:
                al = _parse_date(t["al"])
                dal = _parse_date(t["dal"])
                if dal <= sub_current <= al and al + timedelta(days=1) < next_change:
                    next_change = al + timedelta(days=1)

            periodo_fine = min(next_change, dt_boundary)
            giorni = (periodo_fine - sub_current).days
            anno = _days_in_year(sub_current.year)
            interessi = capitale_residuo * (tasso / 100) * giorni / anno
            interessi_periodo += interessi
            sub_current = periodo_fine

        totale_interessi += interessi_periodo

        periodi.append({
            "dal": current.isoformat(),
            "al": (dt_boundary - timedelta(days=1)).isoformat() if dt_boundary != dt_fine else dt_fine.isoformat(),
            "capitale_residuo": round(capitale_residuo, 2),
            "interessi": round(interessi_periodo, 2),
            "acconto_successivo": importo_acconto if importo_acconto > 0 else None,
        })

        if importo_acconto > 0:
            capitale_residuo -= importo_acconto
            capitale_residuo = max(capitale_residuo, 0)
        current = dt_boundary

    return {
        "capitale_iniziale": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "numero_acconti": len(acconti),
        "totale_acconti": round(sum(a["importo"] for a in acconti), 2),
        "capitale_residuo_finale": round(capitale_residuo, 2),
        "totale_interessi": round(totale_interessi, 2),
        "totale_dovuto": round(capitale_residuo + totale_interessi, 2),
        "periodi": periodi,
    }


@mcp.tool()
def calcolo_maggior_danno(
    capitale: float,
    data_inizio: str,
    data_fine: str,
) -> dict:
    """Calcolo maggior danno ex art. 1224 c.c. per obbligazioni pecuniarie.

    Confronta rivalutazione ISTAT vs interessi legali e prende il maggiore,
    come previsto dalla giurisprudenza per il risarcimento del maggior danno.

    Args:
        capitale: Importo del credito in euro
        data_inizio: Data del credito/inadempimento (YYYY-MM-DD)
        data_fine: Data di liquidazione (YYYY-MM-DD)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    # Load FOI data for rivalutazione
    _foi_data_path = _DATA / "indici_foi.json"
    with open(_foi_data_path) as f:
        indici_foi = json.load(f)["indici"]

    def _get_foi_local(year: int, month: int) -> float | None:
        y_str = str(year)
        m_str = f"{month:02d}"
        if y_str in indici_foi and m_str in indici_foi[y_str]:
            return indici_foi[y_str][m_str]
        if y_str in indici_foi:
            months = indici_foi[y_str]
            closest = min(months.keys(), key=lambda m: abs(int(m) - month))
            return months[closest]
        return None

    # 1. Rivalutazione ISTAT
    foi_inizio = _get_foi_local(dt_inizio.year, dt_inizio.month)
    foi_fine = _get_foi_local(dt_fine.year, dt_fine.month)

    if foi_inizio is None or foi_fine is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    coefficiente = foi_fine / foi_inizio
    capitale_rivalutato = capitale * coefficiente
    danno_rivalutazione = capitale_rivalutato - capitale

    # 2. Interessi legali
    totale_interessi = 0.0
    current = dt_inizio
    while current < dt_fine:
        tasso = _get_tasso_legale(current)
        next_change = dt_fine
        for t in _TASSI_LEGALI:
            al = _parse_date(t["al"])
            dal = _parse_date(t["dal"])
            if dal <= current <= al and al + timedelta(days=1) < next_change:
                next_change = al + timedelta(days=1)
        periodo_fine = min(next_change, dt_fine)
        giorni = (periodo_fine - current).days
        anno = _days_in_year(current.year)
        totale_interessi += capitale * (tasso / 100) * giorni / anno
        current = periodo_fine

    # Il maggior danno è la differenza tra rivalutazione e interessi legali, se positiva
    maggior_danno = max(danno_rivalutazione - totale_interessi, 0)
    criterio_applicato = "rivalutazione" if danno_rivalutazione > totale_interessi else "interessi_legali"
    importo_spettante = max(danno_rivalutazione, totale_interessi)

    return {
        "capitale": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "rivalutazione_istat": round(danno_rivalutazione, 2),
        "capitale_rivalutato": round(capitale_rivalutato, 2),
        "interessi_legali": round(totale_interessi, 2),
        "maggior_danno": round(maggior_danno, 2),
        "criterio_applicato": criterio_applicato,
        "importo_spettante": round(importo_spettante, 2),
        "totale_dovuto": round(capitale + importo_spettante, 2),
        "riferimento_normativo": "Art. 1224, co. 2 c.c. — Cass. SU 19499/2008",
    }


@mcp.tool()
def interessi_corso_causa(
    capitale: float,
    data_citazione: str,
    data_sentenza: str,
    data_pagamento: str | None = None,
) -> dict:
    """Interessi in corso di causa art. 1284 co. 4 c.c.

    Dal giorno della domanda giudiziale il tasso legale è maggiorato.
    Calcola il dettaglio per periodi: ante-causa (tasso legale),
    in corso di causa (tasso maggiorato), post-sentenza.

    Args:
        capitale: Importo del credito in euro
        data_citazione: Data della domanda giudiziale (YYYY-MM-DD)
        data_sentenza: Data della sentenza (YYYY-MM-DD)
        data_pagamento: Data effettivo pagamento, se disponibile (YYYY-MM-DD)
    """
    dt_citazione = _parse_date(data_citazione)
    dt_sentenza = _parse_date(data_sentenza)
    dt_pagamento = _parse_date(data_pagamento) if data_pagamento else dt_sentenza

    if dt_sentenza <= dt_citazione:
        return {"errore": "data_sentenza deve essere successiva a data_citazione"}

    periodi = []
    totale_interessi = 0.0

    # Period: in corso di causa (data_citazione -> data_sentenza)
    # Art. 1284 co. 4: tasso legale maggiorato (legale + spread, typically legale itself if > soglia)
    current = dt_citazione
    while current < dt_sentenza:
        tasso_legale = _get_tasso_legale(current)
        # Art. 1284 co. 4: if legal rate is lower than threshold, apply legal rate itself
        # In practice the rate "in corso di causa" equals the legal rate (which already reflects the increase)
        tasso_corso_causa = tasso_legale

        next_change = dt_sentenza
        for t in _TASSI_LEGALI:
            al = _parse_date(t["al"])
            dal = _parse_date(t["dal"])
            if dal <= current <= al and al + timedelta(days=1) < next_change:
                next_change = al + timedelta(days=1)

        periodo_fine = min(next_change, dt_sentenza)
        giorni = (periodo_fine - current).days
        anno = _days_in_year(current.year)
        interessi = capitale * (tasso_corso_causa / 100) * giorni / anno
        totale_interessi += interessi

        periodi.append({
            "tipo": "in_corso_causa",
            "dal": current.isoformat(),
            "al": (periodo_fine - timedelta(days=1)).isoformat(),
            "giorni": giorni,
            "tasso_pct": tasso_corso_causa,
            "interessi": round(interessi, 2),
        })
        current = periodo_fine

    # Period: post-sentenza (data_sentenza -> data_pagamento) if applicable
    interessi_post = 0.0
    if dt_pagamento > dt_sentenza:
        current = dt_sentenza
        while current < dt_pagamento:
            tasso = _get_tasso_legale(current)
            next_change = dt_pagamento
            for t in _TASSI_LEGALI:
                al = _parse_date(t["al"])
                dal = _parse_date(t["dal"])
                if dal <= current <= al and al + timedelta(days=1) < next_change:
                    next_change = al + timedelta(days=1)

            periodo_fine = min(next_change, dt_pagamento)
            giorni = (periodo_fine - current).days
            anno = _days_in_year(current.year)
            interessi = capitale * (tasso / 100) * giorni / anno
            interessi_post += interessi
            totale_interessi += interessi

            periodi.append({
                "tipo": "post_sentenza",
                "dal": current.isoformat(),
                "al": (periodo_fine - timedelta(days=1)).isoformat(),
                "giorni": giorni,
                "tasso_pct": tasso,
                "interessi": round(interessi, 2),
            })
            current = periodo_fine

    return {
        "capitale": capitale,
        "data_citazione": data_citazione,
        "data_sentenza": data_sentenza,
        "data_pagamento": data_pagamento or data_sentenza,
        "totale_interessi": round(totale_interessi, 2),
        "totale_dovuto": round(capitale + totale_interessi, 2),
        "riferimento_normativo": "Art. 1284, co. 4 c.c. (L. 162/2014)",
        "periodi": periodi,
    }


@mcp.tool()
def calcolo_surroga_mutuo(
    debito_residuo: float,
    rata_attuale: float,
    tasso_attuale: float,
    tasso_nuovo: float,
    mesi_residui: int,
) -> dict:
    """Confronto mutuo attuale vs surrogato (portabilità ex art. 120-quater TUB).

    Calcola risparmio totale interessi, nuova rata e break-even point.

    Args:
        debito_residuo: Debito residuo del mutuo attuale in euro
        rata_attuale: Rata mensile attuale in euro
        tasso_attuale: Tasso annuo attuale percentuale (es. 4.5)
        tasso_nuovo: Tasso annuo proposto dalla nuova banca (es. 3.0)
        mesi_residui: Numero di mesi residui del mutuo
    """
    if mesi_residui <= 0:
        return {"errore": "mesi_residui deve essere maggiore di zero"}

    tasso_m_attuale = tasso_attuale / 100 / 12
    tasso_m_nuovo = tasso_nuovo / 100 / 12

    # Current total cost
    totale_attuale = rata_attuale * mesi_residui
    interessi_attuali = totale_attuale - debito_residuo

    # New rate (French amortization)
    if tasso_m_nuovo > 0:
        rata_nuova = debito_residuo * tasso_m_nuovo / (1 - (1 + tasso_m_nuovo) ** (-mesi_residui))
    else:
        rata_nuova = debito_residuo / mesi_residui

    totale_nuovo = rata_nuova * mesi_residui
    interessi_nuovi = totale_nuovo - debito_residuo

    risparmio_rata = rata_attuale - rata_nuova
    risparmio_totale = totale_attuale - totale_nuovo

    # Break-even: months to recover any notarial/admin costs (estimated ~0 for surroga gratuita)
    break_even_mesi = 0  # Surroga is free by law (art. 120-quater TUB)

    return {
        "debito_residuo": debito_residuo,
        "mesi_residui": mesi_residui,
        "mutuo_attuale": {
            "tasso_annuo_pct": tasso_attuale,
            "rata_mensile": rata_attuale,
            "totale_restituito": round(totale_attuale, 2),
            "interessi_residui": round(interessi_attuali, 2),
        },
        "mutuo_surrogato": {
            "tasso_annuo_pct": tasso_nuovo,
            "rata_mensile": round(rata_nuova, 2),
            "totale_restituito": round(totale_nuovo, 2),
            "interessi_residui": round(interessi_nuovi, 2),
        },
        "risparmio_rata_mensile": round(risparmio_rata, 2),
        "risparmio_totale_interessi": round(risparmio_totale, 2),
        "break_even_mesi": break_even_mesi,
        "conviene": risparmio_totale > 0,
        "riferimento_normativo": "Art. 120-quater TUB — D.L. 7/2007 (Legge Bersani)",
    }


@mcp.tool()
def calcolo_taeg(
    capitale: float,
    rate: int,
    importi_rate: float,
    spese_iniziali: float = 0,
    spese_periodiche: float = 0,
) -> dict:
    """Calcolo TAEG (Tasso Annuo Effettivo Globale) con metodo iterativo Newton-Raphson.

    Include tutte le spese accessorie nel calcolo, come richiesto dalla
    normativa sulla trasparenza bancaria (art. 121 TUB).

    Args:
        capitale: Importo finanziato in euro
        rate: Numero totale di rate mensili
        importi_rate: Importo di ciascuna rata mensile in euro
        spese_iniziali: Spese di istruttoria/apertura una tantum in euro (default 0)
        spese_periodiche: Spese periodiche per ogni rata in euro (default 0)
    """
    if rate <= 0:
        return {"errore": "rate deve essere maggiore di zero"}

    # Net amount received by borrower
    netto_erogato = capitale - spese_iniziali

    # Total cost
    rata_effettiva = importi_rate + spese_periodiche
    totale_pagato = rata_effettiva * rate
    costo_totale = totale_pagato - netto_erogato

    # Newton-Raphson to find monthly IRR
    # NPV(r) = -netto_erogato + sum(rata_effettiva / (1+r)^k) = 0
    r = 0.01  # initial guess (monthly rate)

    for _ in range(200):
        npv = -netto_erogato
        dnpv = 0.0
        for k in range(1, rate + 1):
            disc = (1 + r) ** k
            npv += rata_effettiva / disc
            dnpv -= k * rata_effettiva / ((1 + r) ** (k + 1))

        if abs(dnpv) < 1e-15:
            break

        r_new = r - npv / dnpv
        if abs(r_new - r) < 1e-12:
            r = r_new
            break
        r = r_new

    # Convert monthly rate to annual (TAEG)
    taeg = ((1 + r) ** 12 - 1) * 100

    # TAN for comparison
    tan = r * 12 * 100

    return {
        "capitale": capitale,
        "netto_erogato": round(netto_erogato, 2),
        "rate": rate,
        "importo_rata": importi_rate,
        "spese_iniziali": spese_iniziali,
        "spese_periodiche": spese_periodiche,
        "rata_effettiva": round(rata_effettiva, 2),
        "totale_pagato": round(totale_pagato, 2),
        "costo_totale_credito": round(costo_totale, 2),
        "tan_pct": round(tan, 4),
        "taeg_pct": round(taeg, 4),
        "riferimento_normativo": "Art. 121 TUB — Dir. 2008/48/CE (CCD)",
    }
