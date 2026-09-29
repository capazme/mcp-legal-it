"""Calcolo interessi legali (art. 1284 c.c., tasso legale variabile per anno, letto dalla tabella
ministeriale aggiornata), interessi di mora (D.Lgs. 231/2002, BCE+8pp), ammortamento mutui,
TAEG (Dir. 2008/48/CE), verifica usura."""

import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from src.lib import _clock, _data
from src.server import mcp
from src.lib._data import sourced

# Shared FOI index access (single load, same fallback and warning semantics).
from src.tools import rivalutazioni_istat as _rivalutazioni

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "tassi_legali.json") as f:
    _TASSI_LEGALI = json.load(f)["tassi"]

with open(_DATA / "tassi_mora.json") as f:
    _TASSI_MORA = json.load(f)["tassi"]


_MORA_REGIME_7_FINE = date(2012, 12, 31)  # art. 3 c.1 D.Lgs. 192/2012: +8 for transactions from 1/1/2013


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _get_tasso_legale(d: date) -> float:
    """Return the legal interest rate applicable on a given date."""
    for t in _TASSI_LEGALI:
        if _parse_date(t["dal"]) <= d <= _parse_date(t["al"]):
            return t["tasso"]
    return _TASSI_LEGALI[-1]["tasso"]


def _get_rate_period(d: date) -> tuple[float, date]:
    """Return (rate, last_day) for the rate period containing date d."""
    for t in _TASSI_LEGALI:
        dal = _parse_date(t["dal"])
        al = _parse_date(t["al"])
        if dal <= d <= al:
            return t["tasso"], al
    last = _TASSI_LEGALI[-1]
    return last["tasso"], _parse_date(last["al"])


def _calc_interessi_periodo(capitale: float, dt_inizio: date, dt_fine: date) -> float:
    """Compute total legal interest between two dates (dies a quo, 365-day year).

    Shared helper used by interessi_acconti, calcolo_maggior_danno, interessi_corso_causa.
    """
    if dt_fine <= dt_inizio:
        return 0.0

    totale = 0.0
    current = dt_inizio + timedelta(days=1)  # dies a quo non computatur

    while current <= dt_fine:
        tasso, al = _get_rate_period(current)
        year_end = date(current.year, 12, 31)
        periodo_end = min(al, year_end, dt_fine)
        if periodo_end < current:
            break
        giorni = (periodo_end - current).days + 1
        totale += capitale * (tasso / 100) * giorni / 365
        current = periodo_end + timedelta(days=1)

    return totale


def _get_tasso_mora(d: date) -> dict:
    """Return mora rate info for a given date."""
    for t in _TASSI_MORA:
        if _parse_date(t["dal"]) <= d <= _parse_date(t["al"]):
            return t
    return _TASSI_MORA[-1]


def _get_mora_period(d: date) -> tuple[dict, date]:
    """Return (mora_info, last_day) for the mora rate period containing date d."""
    for t in _TASSI_MORA:
        dal = _parse_date(t["dal"])
        al = _parse_date(t["al"])
        if dal <= d <= al:
            return t, al
    last = _TASSI_MORA[-1]
    return last, _parse_date(last["al"])


def _calc_interessi_mora_periodo(capitale: float, dt_inizio: date, dt_fine: date) -> tuple[float, list[dict]]:
    """Compute total mora interest (D.Lgs. 231/2002) between two dates.

    Returns (totale, periodi_detail) where each entry in periodi_detail has
    dal, al, bce, mora keys from the mora rate table.
    """
    if dt_fine <= dt_inizio:
        return 0.0, []

    totale = 0.0
    periodi_detail: list[dict] = []
    current = dt_inizio + timedelta(days=1)  # dies a quo non computatur

    while current <= dt_fine:
        info, al = _get_mora_period(current)
        year_end = date(current.year, 12, 31)
        periodo_end = min(al, year_end, dt_fine)
        if periodo_end < current:
            break
        giorni = (periodo_end - current).days + 1
        mora_rate = info["mora"]
        totale += capitale * (mora_rate / 100) * giorni / 365
        periodi_detail.append({
            "dal": current.isoformat(),
            "al": periodo_end.isoformat(),
            "bce": info.get("bce"),
            "mora": mora_rate,
            "giorni": giorni,
        })
        current = periodo_end + timedelta(days=1)

    return totale, periodi_detail


def _days_in_year(year: int) -> int:
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


@mcp.tool(tags={"interessi"})
@sourced("tassi_legali")
def interessi_legali(
    capitale: float,
    data_inizio: str,
    data_fine: str,
    tipo: str = "semplici",
) -> dict:
    """Calcola interessi legali art. 1284 c.c. tra due date, con cambio automatico di tasso per periodo.

    Applica la regola "dies a quo non computatur": il giorno iniziale non matura interessi.
    Tasso legale variabile per anno, letto dalla tabella ministeriale aggiornata — per interessi in corso di causa usare interessi_corso_causa.
    Vigenza: Art. 1284 c.c.; tassi aggiornati annualmente con DM MEF (dal 1° gennaio di ogni anno).
    Precisione: ESATTO per tassi legali storici (dati tabellari ministeriali).
    Spesso chiamato come ultimo step nel workflow sinistro dopo rivalutazione_monetaria().

    Args:
        capitale: Importo del capitale in euro (€)
        data_inizio: Data inizio decorrenza interessi (formato YYYY-MM-DD)
        data_fine: Data fine decorrenza interessi (formato YYYY-MM-DD)
        tipo: Tipo di capitalizzazione: 'semplici' (default) o 'composti'
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    periodi = []
    montante = capitale
    totale_interessi = 0.0

    # "dies a quo non computatur": first accruing day is dt_inizio + 1
    current = dt_inizio + timedelta(days=1)
    dal_display = dt_inizio

    while current <= dt_fine:
        tasso, al = _get_rate_period(current)

        # Split at rate boundary and year boundary
        year_end = date(current.year, 12, 31)
        periodo_end = min(al, year_end, dt_fine)
        if periodo_end < current:
            break

        giorni = (periodo_end - current).days + 1  # inclusive of both ends
        anno = 365  # site uses 365 always (anno civile)

        if tipo == "composti":
            interessi_periodo = montante * (tasso / 100) * giorni / anno
            montante += interessi_periodo
        else:
            interessi_periodo = capitale * (tasso / 100) * giorni / anno

        totale_interessi += interessi_periodo
        periodi.append({
            "dal": dal_display.isoformat(),
            "al": periodo_end.isoformat(),
            "giorni": giorni,
            "tasso_pct": tasso,
            "interessi": round(interessi_periodo, 2),
        })
        current = periodo_end + timedelta(days=1)
        dal_display = current

    return {
        "capitale": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "tipo": tipo,
        "totale_interessi": round(totale_interessi, 2),
        "montante": round(capitale + totale_interessi, 2),
        "periodi": periodi,
    }


@mcp.tool(tags={"interessi"})
@sourced("tassi_mora")
def interessi_mora(
    capitale: float,
    data_inizio: str,
    data_fine: str,
    contratto_ante_2013: bool | None = None,
) -> dict:
    """Calcola interessi di mora per transazioni commerciali (tasso BCE + 8 punti percentuali; + 7 per contratti anteriori al 2013).

    Si applica esclusivamente a transazioni commerciali tra imprese o tra imprese e PA.
    Per crediti tra privati usare interessi_legali. Per interessi in corso di causa: interessi_corso_causa.
    Vigenza: D.Lgs. 231/2002 art. 2 c.1 lett. e) e art. 5 (tasso di riferimento BCE semestrale, 1 gen e 1 lug), maggiorazione di otto punti
        dopo il D.Lgs. 192/2012; le transazioni concluse fino al 31/12/2012 restano soggette al testo originario (art. 5 c.1: sette punti),
        art. 3 c.1 D.Lgs. 192/2012. Parametro contratto_ante_2013: se omesso, la maggiorazione di sette punti si applica quando
        data_inizio e' anteriore o uguale al 31/12/2012 (la scadenza precede il 2013, quindi il contratto e' anteriore); per un contratto
        anteriore al 2013 con scadenza successiva passare contratto_ante_2013=true. Maggiorazione agroalimentare (art. 4 c.2 D.Lgs. 198/2021) non applicata.
    Precisione: ESATTO per tassi storici pubblicati dalla BCE; INDICATIVO per periodi futuri (oltre il 31/12/2026 il tasso non e' ancora noto: nessun interesse calcolato e avvertenza).
    Chaining: → rivalutazione_monetaria() → decreto_ingiuntivo() → parcella_avvocato_civile()

    Args:
        capitale: Importo del credito commerciale in euro (€)
        data_inizio: Data di decorrenza della mora (formato YYYY-MM-DD)
        data_fine: Data di calcolo degli interessi (formato YYYY-MM-DD)
        contratto_ante_2013: True se la transazione e' stata conclusa entro il 31/12/2012 (maggiorazione 7 punti); False per 8 punti;
            omesso: dedotto da data_inizio
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    if contratto_ante_2013 is None:
        contratto_ante_2013 = dt_inizio <= _MORA_REGIME_7_FINE
    maggiorazione = 7 if contratto_ante_2013 else 8

    periodi = []
    totale_interessi = 0.0

    # "dies a quo non computatur": first accruing day is dt_inizio + 1
    current = dt_inizio + timedelta(days=1)
    dal_display = dt_inizio
    ultimo_coperto = _parse_date(_TASSI_MORA[-1]["al"])

    while current <= dt_fine:
        info, al = _get_mora_period(current)
        periodo_end = min(al, dt_fine)
        if periodo_end < current:
            break

        giorni = (periodo_end - current).days + 1  # inclusive
        # rate = BCE reference rate + the spread of the regime (art. 2 lett. e / art. 5 c.1 D.Lgs. 231/2002)
        tasso_mora = round(info["bce"] + maggiorazione, 4)
        interessi_periodo = capitale * (tasso_mora / 100) * giorni / 365

        totale_interessi += interessi_periodo
        periodi.append({
            "dal": dal_display.isoformat(),
            "al": periodo_end.isoformat(),
            "giorni": giorni,
            "tasso_bce_pct": info["bce"],
            "tasso_mora_pct": tasso_mora,
            "interessi": round(interessi_periodo, 2),
        })
        current = periodo_end + timedelta(days=1)
        dal_display = current

    risultato = {
        "capitale": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "totale_interessi": round(totale_interessi, 2),
        "totale_dovuto": round(capitale + totale_interessi, 2),
        "maggiorazione_punti": maggiorazione,
        "riferimento_normativo": (
            f"D.Lgs. 231/2002 — tasso BCE + {maggiorazione} punti percentuali"
            + (" (testo anteriore al D.Lgs. 192/2012, art. 3 c.1)" if maggiorazione == 7 else "")
        ),
        "periodi": periodi,
    }
    if dt_fine > ultimo_coperto:
        risultato["avvertenza"] = (
            f"Il tasso BCE successivo al {ultimo_coperto.strftime('%d/%m/%Y')} non e' ancora in tabella: "
            "gli interessi oltre tale data non sono calcolati."
        )
    return risultato


@mcp.tool(tags={"interessi"})
def interessi_tasso_fisso(
    capitale: float,
    tasso_annuo: float,
    data_inizio: str,
    data_fine: str,
    tipo: str = "semplici",
) -> dict:
    """Calcola interessi a tasso fisso personalizzato (contrattuale, convenzionale o ipotetico).

    Utile per interessi contrattuali o per proiezioni con tasso fisso ipotetico.
    Per tassi legali variabili nel tempo usare interessi_legali; per mora commerciale usare interessi_mora.
    Precisione: ESATTO (calcolo matematico sul tasso fornito); INDICATIVO se il tasso è stimato.

    Args:
        capitale: Importo del capitale in euro (€)
        tasso_annuo: Tasso annuo percentuale (es. 3.5 per 3,5%)
        data_inizio: Data inizio maturazione interessi (formato YYYY-MM-DD)
        data_fine: Data fine maturazione interessi (formato YYYY-MM-DD)
        tipo: Tipo di capitalizzazione: 'semplici' (default) o 'composti'
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


@mcp.tool(tags={"interessi"})
def calcolo_ammortamento(
    capitale: float,
    tasso_annuo: float,
    durata_mesi: int,
    tipo: str = "francese",
) -> dict:
    """Calcola il piano di ammortamento completo per un mutuo o finanziamento.

    Metodo francese: rata costante (quota interessi decrescente, quota capitale crescente).
    Metodo italiano: quota capitale costante (rata decrescente nel tempo).
    Precisione: ESATTO (calcolo matematico su tasso e durata forniti); INDICATIVO se il tasso è variabile nel tempo.

    Args:
        capitale: Importo del mutuo/finanziamento in euro (€)
        tasso_annuo: Tasso annuo percentuale nominale (es. 3.5 per 3,5%)
        durata_mesi: Durata del mutuo in mesi (es. 240 per 20 anni)
        tipo: Metodo di ammortamento: 'francese' (rata costante) o 'italiano' (quota capitale costante)
    """
    if durata_mesi <= 0:
        return {"errore": "durata_mesi deve essere maggiore di zero"}

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


@mcp.tool(tags={"interessi"})
@sourced("tegm")
def verifica_usura(
    tasso_applicato: float,
    tipo_operazione: str = "mutuo_prima_casa",
    trimestre: str | None = None,
) -> dict:
    """Verifica se un tasso supera la soglia di usura ex art. 644 c.p.

    Calcola il tasso soglia con la formula: min(TEGM×1.25+4, TEGM+8) — DL 70/2011.
    Il TEGM è pubblicato trimestralmente dal MEF. Usare per verifica di contratti esistenti.
    Vigenza: Art. 644 c.p. — art. 2 co. 4 L. 108/1996 — DL 70/2011 conv. L. 106/2011; TEGM dei decreti MEF trimestrali (Allegato A), verificati al 2026-09-29; soglia con i quattro decimali del decreto (es. 8,4750).
    Precisione: ESATTO per TEGM del trimestre indicato; INDICATIVO se il trimestre non è ancora disponibile. Un trimestre o una categoria non in tabella danno errore (nessuna sostituzione silenziosa).

    Args:
        tasso_applicato: TAEG effettivo applicato dal finanziatore in percentuale (es. 15.5)
        tipo_operazione: Categoria di finanziamento (una soglia per categoria e classe di importo, art. 2 co. 1 L. 108/1996): 'mutuo_prima_casa' (tasso fisso), 'mutuo_tasso_variabile', 'credito_personale', 'credito_finalizzato', 'apertura_credito' (fino a 5.000), 'apertura_credito_oltre_5000', 'leasing' (strumentale fino a 25.000), 'leasing_auto', 'leasing_immobiliare_fisso', 'leasing_immobiliare_variabile', 'factoring' (fino a 50.000), 'carte_revolving', 'cessione_quinto' (fino a 15.000), 'cessione_quinto_oltre_15000', 'scoperti_senza_affidamento'
        trimestre: Trimestre di riferimento MEF (es. '2024-Q1'); se None usa l'ultimo disponibile
    """
    # Load TEGM from data file (updated quarterly). Through `_data.load` so the
    # ledger sees the read and the answer can declare its vintage.
    tegm_data = _data.load("tegm")

    avvertenza = None
    # Support both old flat format and new multi-quarter format
    if "trimestri" in tegm_data:
        trimestri = tegm_data["trimestri"]
        if trimestre:
            if trimestre not in trimestri:
                # Art. 2 c. 4 L. 108/1996: the limit is the one of the quarter in which the
                # rate was agreed. Answering with another quarter would be silently wrong.
                return {
                    "errore": f"trimestre '{trimestre}' non presente in tabella",
                    "trimestri_disponibili": sorted(trimestri),
                }
            quarter = trimestri[trimestre]
        else:
            # Auto-detect quarter from today's date; fallback to last available
            today = _clock.today()
            quarter = None
            for q_key in sorted(trimestri):
                q = trimestri[q_key]
                if _parse_date(q["dal"]) <= today <= _parse_date(q["al"]):
                    trimestre = q_key
                    quarter = q
                    break
            if quarter is None:
                # Use last available quarter
                last_key = sorted(trimestri)[-1]
                trimestre = last_key
                quarter = trimestri[last_key]
                avvertenza = (
                    f"nessun trimestre in tabella copre la data odierna: usato l'ultimo disponibile ({last_key})"
                )
        categorie = quarter["categorie"]
    else:
        # Legacy flat format
        trimestre = trimestre or tegm_data["trimestre"]
        categorie = tegm_data["categorie"]

    if tipo_operazione not in categorie:
        # Art. 2 c. 1 L. 108/1996: one limit per category of operation. Falling back to
        # another category would apply the wrong limit without telling the caller.
        return {
            "errore": f"tipo_operazione '{tipo_operazione}' non gestito",
            "tipi_operazione_disponibili": sorted(categorie),
        }
    info = categorie[tipo_operazione]
    tegm = info["tegm"]

    # Formula tasso soglia usura (L. 108/1996 come modificata dal DL 70/2011).
    # Decimal: the MEF decree prints the limit with four decimals (8,4750), so the
    # exact value is representable; round() on binary floats turned 8,475 into 8,47.
    d_tegm = Decimal(str(tegm))
    d_formula = d_tegm * Decimal("1.25") + 4
    d_tetto = d_tegm + 8
    d_soglia = min(d_formula, d_tetto)
    d_applicato = Decimal(str(tasso_applicato))
    cent = Decimal("0.01")

    usurario = d_applicato > d_soglia
    prossimo_a_usura = d_applicato > d_soglia * Decimal("0.9")

    risultato = {
        "tasso_applicato_pct": tasso_applicato,
        "tipo_operazione": tipo_operazione,
        "descrizione": info["descrizione"],
        "trimestre": trimestre,
        "tegm_pct": tegm,
        # two decimals half-up (as the MEF/bank tables are displayed); the exact
        # four-decimal figure of the decree is in tasso_soglia_decreto_pct
        "tasso_soglia_pct": float(d_soglia.quantize(cent, rounding=ROUND_HALF_UP)),
        "tasso_soglia_decreto_pct": float(d_soglia),
        "formula": f"min(TEGM×1.25+4, TEGM+8) = min({float(d_formula)}, {float(d_tetto)})",
        "usurario": usurario,
        "prossimo_a_usura": prossimo_a_usura,
        "margine": float((d_soglia - d_applicato).quantize(cent, rounding=ROUND_HALF_UP)),
        "riferimento_normativo": "Art. 644 c.p. — L. 108/1996 — DL 70/2011 conv. L. 106/2011",
    }
    if avvertenza:
        risultato["avvertenza"] = avvertenza
    return risultato


@mcp.tool(tags={"interessi"})
@sourced("tassi_legali")
def interessi_acconti(
    capitale: float,
    data_inizio: str,
    acconti: list[dict],
    data_fine: str,
    imputazione: str = "interessi",
) -> dict:
    """Calcola interessi legali art. 1284 c.c. con acconti intermedi imputati secondo l'art. 1194 c.c.

    Per default (imputazione="interessi") ogni acconto e' imputato prima agli interessi maturati e non ancora pagati e
    solo per l'eccedenza al capitale (art. 1194 c.c.); gli interessi non pagati restano dovuti ma non producono interessi
    (art. 1283 c.c.). Con imputazione="capitale" l'acconto riduce direttamente il capitale: ammesso solo con il consenso
    del creditore (art. 1194 co. 1 c.c.). L'acconto alla data finale e' computato (dies ad quem incluso); un acconto
    anteriore alla decorrenza, successivo alla data finale o superiore al credito residuo e' rifiutato.
    Vigenza: Art. 1194 e 1284 c.c.; tassi legali vigenti per ciascun anno del periodo.
    Precisione: ESATTO per tassi legali storici; INDICATIVO per tassi futuri.

    Args:
        capitale: Importo del capitale iniziale in euro (€)
        data_inizio: Data inizio decorrenza interessi (formato YYYY-MM-DD)
        acconti: Lista di acconti intermedi, ciascuno con 'data' (YYYY-MM-DD) e 'importo' (float in €)
        data_fine: Data fine decorrenza interessi (formato YYYY-MM-DD)
        imputazione: 'interessi' (default, art. 1194: prima gli interessi) oppure 'capitale' (solo con consenso del creditore)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}
    if imputazione not in ("interessi", "capitale"):
        return {"errore": "imputazione deve essere 'interessi' (art. 1194 c.c.) o 'capitale' (con consenso del creditore)"}

    movimenti = []
    for acc in acconti:
        dt_acc = _parse_date(acc["data"])
        if dt_acc < dt_inizio:
            return {"errore": f"acconto del {acc['data']} anteriore alla decorrenza degli interessi: ridurre il capitale iniziale"}
        if dt_acc > dt_fine:
            return {"errore": f"acconto del {acc['data']} successivo a data_fine"}
        movimenti.append((dt_acc, float(acc["importo"])))
    movimenti.sort(key=lambda m: m[0])
    movimenti.append((dt_fine, 0.0))

    periodi = []
    capitale_residuo = float(capitale)
    interessi_residui = 0.0  # accrued and still unpaid (art. 1194)
    totale_interessi = 0.0
    interessi_imputati = 0.0
    current = dt_inizio

    for dt_mov, importo in movimenti:
        if dt_mov > current:
            interessi_periodo = _calc_interessi_periodo(capitale_residuo, current, dt_mov)
            totale_interessi += interessi_periodo
            interessi_residui += interessi_periodo
            periodi.append({
                "dal": current.isoformat(),
                "al": dt_mov.isoformat(),
                "capitale_residuo": round(capitale_residuo, 2),
                "interessi": round(interessi_periodo, 2),
                "acconto_successivo": importo if importo > 0 else None,
            })
            current = dt_mov

        if importo <= 0:
            continue
        if imputazione == "interessi":
            if importo > capitale_residuo + interessi_residui + 0.005:
                return {"errore": (
                    f"acconto di {importo:.2f} del {dt_mov.isoformat()} superiore al credito residuo "
                    f"({capitale_residuo + interessi_residui:.2f})"
                )}
            agli_interessi = min(importo, interessi_residui)
            interessi_residui -= agli_interessi
            interessi_imputati += agli_interessi
            capitale_residuo = max(capitale_residuo - (importo - agli_interessi), 0.0)
        else:
            if importo > capitale_residuo + 0.005:
                return {"errore": (
                    f"acconto di {importo:.2f} del {dt_mov.isoformat()} superiore al capitale residuo "
                    f"({capitale_residuo:.2f})"
                )}
            capitale_residuo = max(capitale_residuo - importo, 0.0)

    if imputazione == "capitale":
        interessi_residui = totale_interessi

    return {
        "capitale_iniziale": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "imputazione": imputazione,
        "numero_acconti": len(acconti),
        "totale_acconti": round(sum(float(a["importo"]) for a in acconti), 2),
        "capitale_residuo_finale": round(capitale_residuo, 2),
        "totale_interessi": round(totale_interessi, 2),
        "interessi_imputati_da_acconti": round(interessi_imputati, 2),
        "interessi_residui": round(interessi_residui, 2),
        "totale_dovuto": round(capitale_residuo + interessi_residui, 2),
        "periodi": periodi,
    }


@mcp.tool(tags={"interessi"})
@sourced("indici_foi", "tassi_legali")
def calcolo_maggior_danno(
    capitale: float,
    data_inizio: str,
    data_fine: str,
) -> dict:
    """Calcola il maggior danno ex art. 1224 co. 2 c.c. per obbligazioni pecuniarie inadempiute.

    Confronta rivalutazione ISTAT (indici FOI) e interessi legali, applicando il criterio
    del maggiore tra i due (Cass. SU 19499/2008). Se la rivalutazione supera gli interessi,
    il creditore ha diritto al maggior danno pari alla differenza.
    Vigenza: Art. 1224 co. 2 c.c. — Cass. SU 19499/2008; indici FOI ISTAT base 2015=100
    raccordata (dal 2026 base 2025=100, coefficiente ufficiale 1,214), serie dal 1990.
    Precisione: INDICATIVO (Cass. SS.UU. 19499/2008 presume il maggior danno ex art. 1224 co. 2 c.c.
        nella differenza tra il rendimento medio annuo netto dei titoli di Stato di durata non
        superiore a dodici mesi e il tasso legale; il confronto con l'indice FOI qui adottato è un
        criterio diverso, da usare solo come stima)

    Args:
        capitale: Importo del credito originario in euro (€)
        data_inizio: Data dell'inadempimento/credito originario (formato YYYY-MM-DD)
        data_fine: Data di liquidazione (formato YYYY-MM-DD)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    # 1. Rivalutazione ISTAT (shared FOI series from rivalutazioni_istat)
    sostituzioni: list = []
    foi_inizio = _rivalutazioni._foi_tracciato(
        sostituzioni, dt_inizio.year, dt_inizio.month
    )
    foi_fine = _rivalutazioni._foi_tracciato(sostituzioni, dt_fine.year, dt_fine.month)

    if foi_inizio is None or foi_fine is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    coefficiente = foi_fine / foi_inizio
    capitale_rivalutato = capitale * coefficiente
    danno_rivalutazione = capitale_rivalutato - capitale

    # 2. Interessi legali
    totale_interessi = _calc_interessi_periodo(capitale, dt_inizio, dt_fine)

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
        "avvertenza": _rivalutazioni._formatta_avvertenza(sostituzioni),
        "riferimento_normativo": "Art. 1224, co. 2 c.c. — Cass. SU 19499/2008",
    }


@mcp.tool(tags={"interessi"})
@sourced("tassi_mora")
def interessi_corso_causa(
    capitale: float,
    data_citazione: str,
    data_sentenza: str,
    data_pagamento: str | None = None,
) -> dict:
    """Calcola interessi in corso di causa art. 1284 co. 4 c.c. (tasso mora D.Lgs. 231/2002 dalla citazione).

    Dal giorno della domanda giudiziale (citazione) si applica il tasso di mora D.Lgs. 231/2002
    (BCE+8pp) invece del tasso legale ordinario, sia in corso di causa sia post-sentenza.
    Per interessi ante-causa (prima della citazione) usare interessi_legali.
    Vigenza: Art. 1284 co. 4 c.c. (introdotto da L. 162/2014); D.Lgs. 231/2002.
    Precisione: ESATTO per tassi BCE storici; INDICATIVO per periodi futuri.

    Args:
        capitale: Importo del credito in euro (€)
        data_citazione: Data della domanda giudiziale/citazione (formato YYYY-MM-DD)
        data_sentenza: Data di deposito della sentenza (formato YYYY-MM-DD)
        data_pagamento: Data di effettivo pagamento (formato YYYY-MM-DD; se None usa data_sentenza)
    """
    dt_citazione = _parse_date(data_citazione)
    dt_sentenza = _parse_date(data_sentenza)
    dt_pagamento = _parse_date(data_pagamento) if data_pagamento else dt_sentenza

    if dt_sentenza <= dt_citazione:
        return {"errore": "data_sentenza deve essere successiva a data_citazione"}

    # In corso di causa (data_citazione -> data_sentenza): mora rate per art. 1284 co. 4 c.c.
    interessi_causa, _ = _calc_interessi_mora_periodo(capitale, dt_citazione, dt_sentenza)
    totale_interessi = interessi_causa

    periodi = [{
        "tipo": "in_corso_causa",
        "dal": data_citazione,
        "al": data_sentenza,
        "tasso_tipo": "mora D.Lgs. 231/2002",
        "interessi": round(interessi_causa, 2),
    }]

    # Post-sentenza (data_sentenza -> data_pagamento): mora rate continues
    interessi_post = 0.0
    if dt_pagamento > dt_sentenza:
        interessi_post, _ = _calc_interessi_mora_periodo(capitale, dt_sentenza, dt_pagamento)
        totale_interessi += interessi_post
        periodi.append({
            "tipo": "post_sentenza",
            "dal": data_sentenza,
            "al": dt_pagamento.isoformat(),
            "tasso_tipo": "mora D.Lgs. 231/2002",
            "interessi": round(interessi_post, 2),
        })

    return {
        "capitale": capitale,
        "data_citazione": data_citazione,
        "data_sentenza": data_sentenza,
        "data_pagamento": data_pagamento or data_sentenza,
        "totale_interessi": round(totale_interessi, 2),
        "totale_dovuto": round(capitale + totale_interessi, 2),
        "tasso_applicato": "mora D.Lgs. 231/2002 (art. 1284 co. 4 c.c.)",
        "riferimento_normativo": "Art. 1284, co. 4 c.c. (L. 162/2014) — tasso mora D.Lgs. 231/2002 BCE+8pp",
        "periodi": periodi,
    }


@mcp.tool(tags={"interessi"})
def calcolo_surroga_mutuo(
    debito_residuo: float,
    rata_attuale: float,
    tasso_attuale: float,
    tasso_nuovo: float,
    mesi_residui: int,
) -> dict:
    """Confronta il mutuo attuale con un mutuo surrogato per valutare la convenienza della portabilità.

    La surroga è gratuita per legge (art. 120-quater TUB, Legge Bersani). Calcola risparmio
    totale interessi e confronto rata mensile tra mutuo attuale e mutuo surrogato.
    Vigenza: Art. 120-quater TUB — D.L. 7/2007 conv. L. 40/2007 (Legge Bersani).
    Precisione: ESATTO per calcolo ammortamento francese; INDICATIVO se il tasso futuro è variabile.

    Args:
        debito_residuo: Capitale residuo del mutuo attuale in euro (€)
        rata_attuale: Rata mensile attuale in euro (€)
        tasso_attuale: Tasso annuo del mutuo attuale in percentuale (es. 4.5 per 4,5%)
        tasso_nuovo: Tasso annuo proposto dalla nuova banca in percentuale (es. 3.0)
        mesi_residui: Numero di mesi residui del mutuo attuale (es. 180 per 15 anni)
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


@mcp.tool(tags={"interessi"})
def calcolo_taeg(
    capitale: float,
    rate: int,
    importi_rate: float,
    spese_iniziali: float = 0,
    spese_periodiche: float = 0,
) -> dict:
    """Calcola il TAEG (Tasso Annuo Effettivo Globale) con metodo iterativo Newton-Raphson.

    Il TAEG include tutte le spese accessorie (istruttoria, incasso rata ecc.) come previsto dalla
    normativa europea sulla trasparenza bancaria. Utile per confronto tra prodotti finanziari diversi.
    Vigenza: Art. 121 TUB — Direttiva 2008/48/CE (Consumer Credit Directive).
    Precisione: INDICATIVO (calcolo iterativo convergente con 200 iterazioni; può divergere per parametri estremi).

    Args:
        capitale: Importo del finanziamento erogato in euro (€)
        rate: Numero totale di rate mensili (intero positivo)
        importi_rate: Importo nominale di ciascuna rata mensile in euro (€, escluse spese periodiche)
        spese_iniziali: Spese di istruttoria/apertura una tantum in euro (€, default 0)
        spese_periodiche: Spese di incasso rata o simili per ogni rata in euro (€, default 0)
    """
    if rate <= 0:
        return {"errore": "rate deve essere maggiore di zero"}

    # Net amount received by borrower
    netto_erogato = capitale - spese_iniziali

    if netto_erogato <= 0:
        return {"errore": "netto_erogato deve essere maggiore di zero (capitale > spese_iniziali)"}

    # Total cost
    rata_effettiva = importi_rate + spese_periodiche
    totale_pagato = rata_effettiva * rate
    costo_totale = totale_pagato - netto_erogato

    # Newton-Raphson to find monthly IRR
    # NPV(r) = -netto_erogato + sum(rata_effettiva / (1+r)^k) = 0
    import math
    r = 0.01  # initial guess (monthly rate)

    converged = False
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
            converged = True
            break
        r = r_new

    if not converged or not math.isfinite(r) or r <= -1:
        return {"errore": "Impossibile calcolare il TAEG: parametri non convergenti o non validi"}

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
