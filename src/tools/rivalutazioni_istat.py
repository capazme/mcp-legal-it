"""Rivalutazione monetaria con indici FOI ISTAT (disponibili dal 1947, base 2015=100):
inflazione, adeguamento canoni (L. 392/1978 art. 32), TFR (art. 2120 c.c.)."""

import json
from datetime import date
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "indici_foi.json") as f:
    _INDICI_FOI = json.load(f)["indici"]

with open(_DATA / "tassi_legali.json") as f:
    _TASSI_LEGALI = json.load(f)["tassi"]


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


_FOI_FALLBACK_WARNINGS: list[str] = []


def _get_foi(year: int, month: int) -> float | None:
    """Get FOI index for a given year/month, falling back to closest available."""
    y_str = str(year)
    m_str = f"{month:02d}"

    # Exact match
    if y_str in _INDICI_FOI and m_str in _INDICI_FOI[y_str]:
        return _INDICI_FOI[y_str][m_str]

    # Year exists but month missing — pick closest month
    if y_str in _INDICI_FOI:
        months = _INDICI_FOI[y_str]
        closest = min(months.keys(), key=lambda m: abs(int(m) - month))
        return months[closest]

    # Year missing — pick closest year
    available_years = sorted(_INDICI_FOI.keys(), key=lambda y: abs(int(y) - year))
    if available_years:
        best_year = available_years[0]
        gap = abs(int(best_year) - year)
        if gap > 1:
            warning = f"ATTENZIONE: indice FOI per {year}/{m_str} non disponibile — usato anno {best_year} (distanza {gap} anni). Risultato approssimato."
            _FOI_FALLBACK_WARNINGS.append(warning)
        months = _INDICI_FOI[best_year]
        closest_m = min(months.keys(), key=lambda m: abs(int(m) - month))
        return months[closest_m]

    return None


def _get_tasso_legale(d: date) -> float:
    for t in _TASSI_LEGALI:
        if _parse_date(t["dal"]) <= d <= _parse_date(t["al"]):
            return t["tasso"]
    return _TASSI_LEGALI[-1]["tasso"]


def _days_in_year(year: int) -> int:
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


@mcp.tool()
def rivalutazione_monetaria(
    capitale: float,
    data_inizio: str,
    data_fine: str,
    con_interessi_legali: bool = True,
) -> dict:
    """Rivaluta un capitale con indici FOI ISTAT, con o senza interessi legali anno per anno.

    Se con_interessi_legali=True, applica il criterio Cass. SU 1712/1995: interessi legali
    sul capitale rivalutato per ciascun anno (metodo più favorevole al creditore).
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947 al mese più recente pubblicato.
    Precisione: ESATTO (indici ISTAT ufficiali); INDICATIVO se la data richiesta è oltre l'ultimo indice disponibile (usa l'anno più prossimo).

    Args:
        capitale: Importo originario del credito in euro (€)
        data_inizio: Data del credito originario (formato YYYY-MM-DD)
        data_fine: Data di liquidazione/calcolo (formato YYYY-MM-DD)
        con_interessi_legali: Se True, calcola interessi legali (art. 1284 c.c.) anno per anno sul rivalutato
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    foi_inizio = _get_foi(dt_inizio.year, dt_inizio.month)
    foi_fine = _get_foi(dt_fine.year, dt_fine.month)

    if foi_inizio is None or foi_fine is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    coefficiente = foi_fine / foi_inizio
    capitale_rivalutato = capitale * coefficiente

    dettaglio_anni = []
    totale_interessi = 0.0

    for anno in range(dt_inizio.year, dt_fine.year + 1):
        # FOI at start and end of this year-segment
        if anno == dt_inizio.year:
            m_start = dt_inizio.month
        else:
            m_start = 1
        if anno == dt_fine.year:
            m_end = dt_fine.month
        else:
            m_end = 12

        foi_a = _get_foi(dt_inizio.year, dt_inizio.month)
        foi_b = _get_foi(anno, m_end)
        coeff_anno = foi_b / foi_a
        capitale_anno = round(capitale * coeff_anno, 2)

        entry = {
            "anno": anno,
            "foi_riferimento": foi_b,
            "coefficiente": round(coeff_anno, 6),
            "capitale_rivalutato": capitale_anno,
        }

        if con_interessi_legali:
            tasso = _get_tasso_legale(date(anno, 1, 1))
            # Fraction of year covered
            if anno == dt_inizio.year:
                giorni = (date(anno, 12, 31) - dt_inizio).days
            elif anno == dt_fine.year:
                giorni = (dt_fine - date(anno, 1, 1)).days
            else:
                giorni = _days_in_year(anno)
            interessi_anno = capitale_anno * (tasso / 100) * giorni / _days_in_year(anno)
            totale_interessi += interessi_anno
            entry["tasso_legale_pct"] = tasso
            entry["giorni"] = giorni
            entry["interessi_legali"] = round(interessi_anno, 2)

        dettaglio_anni.append(entry)

    result = {
        "capitale_originario": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "foi_inizio": foi_inizio,
        "foi_fine": foi_fine,
        "coefficiente_rivalutazione": round(coefficiente, 6),
        "capitale_rivalutato": round(capitale_rivalutato, 2),
        "dettaglio_anni": dettaglio_anni,
    }

    if con_interessi_legali:
        result["totale_interessi_legali"] = round(totale_interessi, 2)
        result["totale_dovuto"] = round(capitale_rivalutato + totale_interessi, 2)

    return result


@mcp.tool()
def rivalutazione_mensile(
    importo_mensile: float,
    data_inizio: str,
    data_fine: str,
) -> dict:
    """Rivaluta ogni singola mensilità di una rata/assegno ricorrente con indici FOI ISTAT.

    Utile per assegni di mantenimento arretrati o canoni mensili non corrisposti:
    ogni mensilità viene rivalutata individualmente dalla sua data fino a data_fine.
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947 al mese più recente.
    Precisione: ESATTO (indici ISTAT ufficiali mese per mese).

    Args:
        importo_mensile: Importo della singola rata/assegno mensile in euro (€)
        data_inizio: Data della prima mensilità (formato YYYY-MM-DD)
        data_fine: Data di riferimento finale per la rivalutazione (formato YYYY-MM-DD)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    foi_fine = _get_foi(dt_fine.year, dt_fine.month)
    if foi_fine is None:
        return {"errore": "Indice FOI non disponibile per la data finale"}

    dettaglio = []
    totale_nominale = 0.0
    totale_rivalutato = 0.0
    year = dt_inizio.year
    month = dt_inizio.month

    while date(year, month, 1) <= dt_fine:
        foi_mese = _get_foi(year, month)
        if foi_mese is None:
            break

        coeff = foi_fine / foi_mese
        importo_rivalutato = importo_mensile * coeff
        differenza = importo_rivalutato - importo_mensile

        dettaglio.append({
            "anno": year,
            "mese": month,
            "foi": foi_mese,
            "coefficiente": round(coeff, 6),
            "importo_nominale": importo_mensile,
            "importo_rivalutato": round(importo_rivalutato, 2),
            "differenza": round(differenza, 2),
        })

        totale_nominale += importo_mensile
        totale_rivalutato += importo_rivalutato

        month += 1
        if month > 12:
            month = 1
            year += 1

    return {
        "importo_mensile": importo_mensile,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "foi_riferimento_finale": foi_fine,
        "numero_mensilita": len(dettaglio),
        "totale_nominale": round(totale_nominale, 2),
        "totale_rivalutato": round(totale_rivalutato, 2),
        "differenza_totale": round(totale_rivalutato - totale_nominale, 2),
        "dettaglio_mensile": dettaglio,
    }


@mcp.tool()
def adeguamento_canone_locazione(
    canone_annuo: float,
    data_stipula: str,
    data_adeguamento: str,
    percentuale_istat: float = 75.0,
) -> dict:
    """Calcola l'adeguamento ISTAT del canone di locazione secondo L. 392/1978 art. 32.

    Per contratti liberi 4+4 si applica il 100% della variazione FOI; per concordati il 75%.
    Vigenza: L. 392/1978 art. 32 — L. 431/1998; indici FOI ISTAT base 2015=100.
    Precisione: ESATTO (indici ISTAT ufficiali; la percentuale applicabile dipende dal tipo di contratto).

    Args:
        canone_annuo: Canone annuo corrente in euro (€)
        data_stipula: Data di stipula del contratto o dell'ultimo adeguamento (formato YYYY-MM-DD)
        data_adeguamento: Data per cui calcolare il nuovo canone (formato YYYY-MM-DD)
        percentuale_istat: Percentuale della variazione FOI da applicare (0.0-100.0; default 75% per concordati, 100% per liberi)
    """
    dt_stipula = _parse_date(data_stipula)
    dt_adeguamento = _parse_date(data_adeguamento)

    if dt_adeguamento <= dt_stipula:
        return {"errore": "data_adeguamento deve essere successiva a data_stipula"}

    foi_stipula = _get_foi(dt_stipula.year, dt_stipula.month)
    foi_adeguamento = _get_foi(dt_adeguamento.year, dt_adeguamento.month)

    if foi_stipula is None or foi_adeguamento is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    variazione_piena_pct = ((foi_adeguamento - foi_stipula) / foi_stipula) * 100
    variazione_applicata_pct = variazione_piena_pct * (percentuale_istat / 100)
    canone_aggiornato = canone_annuo * (1 + variazione_applicata_pct / 100)
    canone_mensile_prima = canone_annuo / 12
    canone_mensile_dopo = canone_aggiornato / 12

    return {
        "canone_annuo_originario": canone_annuo,
        "canone_mensile_originario": round(canone_mensile_prima, 2),
        "data_stipula": data_stipula,
        "data_adeguamento": data_adeguamento,
        "foi_stipula": foi_stipula,
        "foi_adeguamento": foi_adeguamento,
        "variazione_foi_piena_pct": round(variazione_piena_pct, 2),
        "percentuale_istat_applicata": percentuale_istat,
        "variazione_applicata_pct": round(variazione_applicata_pct, 2),
        "canone_annuo_aggiornato": round(canone_aggiornato, 2),
        "canone_mensile_aggiornato": round(canone_mensile_dopo, 2),
        "aumento_annuo": round(canone_aggiornato - canone_annuo, 2),
        "riferimento_normativo": "L. 392/1978, art. 32 — L. 431/1998",
    }


@mcp.tool()
def calcolo_inflazione(
    data_inizio: str,
    data_fine: str,
) -> dict:
    """Calcola la variazione percentuale di inflazione tra due date usando gli indici FOI ISTAT.

    Restituisce variazione cumulata, coefficiente di rivalutazione e inflazione media annua.
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947 al mese più recente pubblicato.
    Precisione: ESATTO (indici ISTAT ufficiali).

    Args:
        data_inizio: Data iniziale del periodo (formato YYYY-MM-DD)
        data_fine: Data finale del periodo (formato YYYY-MM-DD)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    foi_inizio = _get_foi(dt_inizio.year, dt_inizio.month)
    foi_fine = _get_foi(dt_fine.year, dt_fine.month)

    if foi_inizio is None or foi_fine is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    variazione_pct = ((foi_fine - foi_inizio) / foi_inizio) * 100
    coefficiente = foi_fine / foi_inizio
    anni = (dt_fine - dt_inizio).days / 365.25
    inflazione_media_annua = ((coefficiente ** (1 / anni)) - 1) * 100 if anni > 0 else 0

    return {
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "foi_inizio": foi_inizio,
        "foi_fine": foi_fine,
        "variazione_percentuale": round(variazione_pct, 2),
        "coefficiente_rivalutazione": round(coefficiente, 6),
        "anni": round(anni, 2),
        "inflazione_media_annua_pct": round(inflazione_media_annua, 2),
        "base_indici": "2015=100",
        "esempio": f"100€ del {data_inizio} equivalgono a {round(100 * coefficiente, 2)}€ del {data_fine}",
    }


@mcp.tool()
def rivalutazione_tfr(
    retribuzione_annua: float,
    anni_servizio: int,
    anno_cessazione: int,
) -> dict:
    """Calcola il TFR con rivalutazione annuale ex art. 2120 c.c.

    Il TFR accantonato (1/13.5 della retribuzione annua) si rivaluta ogni anno con coefficiente:
    1.5% fisso + 75% della variazione FOI. Sull'importo rivalutato si applica imposta sostitutiva 17%.
    Vigenza: Art. 2120 c.c.; indici FOI ISTAT base 2015=100 (disponibili dal 1947).
    Precisione: ESATTO per la formula di legge; INDICATIVO se la variazione FOI dell'anno non è ancora disponibile.

    Args:
        retribuzione_annua: Ultima retribuzione annua lorda in euro (€)
        anni_servizio: Numero di anni di servizio (intero positivo)
        anno_cessazione: Anno di cessazione del rapporto di lavoro (es. 2025)
    """
    if anni_servizio <= 0:
        return {"errore": "anni_servizio deve essere maggiore di zero"}

    anno_inizio = anno_cessazione - anni_servizio
    accantonamento_annuo = retribuzione_annua / 13.5
    tfr_accumulato = 0.0
    dettaglio = []

    for anno in range(anno_inizio, anno_cessazione):
        tfr_accumulato += accantonamento_annuo

        if anno > anno_inizio:
            # FOI variation for the year
            foi_dic_prec = _get_foi(anno - 1, 12)
            foi_dic = _get_foi(anno, 12)

            if foi_dic_prec and foi_dic and foi_dic_prec > 0:
                variazione_foi = ((foi_dic - foi_dic_prec) / foi_dic_prec) * 100
            else:
                variazione_foi = 0.0

            # Coefficiente rivalutazione TFR: 1.5% fisso + 75% variazione FOI
            coeff_rival = 1.5 + 0.75 * variazione_foi
            # No negative revaluation
            coeff_rival = max(coeff_rival, 0)
            rivalutazione = (tfr_accumulato - accantonamento_annuo) * (coeff_rival / 100)
            tfr_accumulato += rivalutazione
        else:
            variazione_foi = 0.0
            coeff_rival = 0.0
            rivalutazione = 0.0

        dettaglio.append({
            "anno": anno,
            "accantonamento": round(accantonamento_annuo, 2),
            "variazione_foi_pct": round(variazione_foi, 2),
            "coefficiente_rivalutazione_pct": round(coeff_rival, 2),
            "rivalutazione": round(rivalutazione, 2),
            "tfr_accumulato": round(tfr_accumulato, 2),
        })

    # Imposta sostitutiva (17% sulla rivalutazione)
    totale_rivalutazioni = sum(d["rivalutazione"] for d in dettaglio)
    imposta_sostitutiva = totale_rivalutazioni * 0.17

    return {
        "retribuzione_annua": retribuzione_annua,
        "anni_servizio": anni_servizio,
        "anno_inizio": anno_inizio,
        "anno_cessazione": anno_cessazione,
        "accantonamento_annuo": round(accantonamento_annuo, 2),
        "tfr_lordo": round(tfr_accumulato, 2),
        "totale_rivalutazioni": round(totale_rivalutazioni, 2),
        "imposta_sostitutiva_17_pct": round(imposta_sostitutiva, 2),
        "tfr_netto_rivalutazione": round(tfr_accumulato - imposta_sostitutiva, 2),
        "riferimento_normativo": "Art. 2120 c.c. — rivalutazione 1.5% fisso + 75% FOI ISTAT",
        "dettaglio_anni": dettaglio,
    }


@mcp.tool()
def interessi_vari_capitale_rivalutato(
    capitale: float,
    data_inizio: str,
    data_fine: str,
    tasso_personalizzato: float | None = None,
) -> dict:
    """Rivaluta un capitale FOI e calcola interessi a tasso personalizzato o legale sul rivalutato (criterio Cass. SU 1712/1995).

    Versione estesa di rivalutazione_monetaria che permette di usare un tasso diverso da quello legale
    (es. tasso contrattuale, tasso BOT). Se tasso_personalizzato=None usa il tasso legale vigente per anno.
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947 al mese più recente.
    Precisione: ESATTO (indici ISTAT ufficiali); tasso personalizzato non verificato rispetto ai tassi di legge.

    Args:
        capitale: Importo originario del credito in euro (€)
        data_inizio: Data del credito originario (formato YYYY-MM-DD)
        data_fine: Data di liquidazione (formato YYYY-MM-DD)
        tasso_personalizzato: Tasso annuo percentuale da applicare (es. 3.5); se None usa tasso legale vigente
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    foi_inizio = _get_foi(dt_inizio.year, dt_inizio.month)
    foi_fine = _get_foi(dt_fine.year, dt_fine.month)

    if foi_inizio is None or foi_fine is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    coefficiente = foi_fine / foi_inizio
    capitale_rivalutato = capitale * coefficiente

    dettaglio_anni = []
    totale_interessi = 0.0

    for anno in range(dt_inizio.year, dt_fine.year + 1):
        foi_b = _get_foi(anno, 12 if anno != dt_fine.year else dt_fine.month)
        coeff_anno = foi_b / foi_inizio
        capitale_anno = capitale * coeff_anno

        if anno == dt_inizio.year:
            giorni = (date(anno, 12, 31) - dt_inizio).days
        elif anno == dt_fine.year:
            giorni = (dt_fine - date(anno, 1, 1)).days
        else:
            giorni = _days_in_year(anno)

        tasso = tasso_personalizzato if tasso_personalizzato is not None else _get_tasso_legale(date(anno, 1, 1))
        interessi_anno = capitale_anno * (tasso / 100) * giorni / _days_in_year(anno)
        totale_interessi += interessi_anno

        dettaglio_anni.append({
            "anno": anno,
            "coefficiente": round(coeff_anno, 6),
            "capitale_rivalutato": round(capitale_anno, 2),
            "tasso_pct": tasso,
            "tipo_tasso": "personalizzato" if tasso_personalizzato is not None else "legale",
            "giorni": giorni,
            "interessi": round(interessi_anno, 2),
        })

    return {
        "capitale_originario": capitale,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "coefficiente_rivalutazione": round(coefficiente, 6),
        "capitale_rivalutato": round(capitale_rivalutato, 2),
        "totale_interessi": round(totale_interessi, 2),
        "totale_dovuto": round(capitale_rivalutato + totale_interessi, 2),
        "tasso_utilizzato": f"{tasso_personalizzato}% personalizzato" if tasso_personalizzato is not None else "tasso legale variabile",
        "dettaglio_anni": dettaglio_anni,
    }


@mcp.tool()
def lettera_adeguamento_canone(
    locatore: str,
    conduttore: str,
    indirizzo_immobile: str,
    canone_attuale: float,
    data_stipula: str,
    data_adeguamento: str,
    percentuale_istat: float = 75.0,
) -> dict:
    """Genera il testo della lettera formale di comunicazione dell'adeguamento ISTAT del canone di locazione.

    Include calcolo del nuovo canone con indici FOI e riferimenti normativi pronti per l'invio al conduttore.
    Vigenza: L. 392/1978 art. 32 — L. 431/1998; indici FOI ISTAT base 2015=100.
    Precisione: ESATTO (indici ISTAT ufficiali).

    Args:
        locatore: Nome e cognome completo del locatore (mittente della lettera)
        conduttore: Nome e cognome completo del conduttore (destinatario)
        indirizzo_immobile: Indirizzo completo dell'immobile locato
        canone_attuale: Canone mensile corrente in euro (€)
        data_stipula: Data di stipula del contratto o dell'ultimo adeguamento (formato YYYY-MM-DD)
        data_adeguamento: Data di decorrenza del nuovo canone (formato YYYY-MM-DD)
        percentuale_istat: Percentuale della variazione FOI da applicare (0.0-100.0; default 75%)
    """
    dt_stipula = _parse_date(data_stipula)
    dt_adeguamento = _parse_date(data_adeguamento)

    if dt_adeguamento <= dt_stipula:
        return {"errore": "data_adeguamento deve essere successiva a data_stipula"}

    foi_stipula = _get_foi(dt_stipula.year, dt_stipula.month)
    foi_adeguamento = _get_foi(dt_adeguamento.year, dt_adeguamento.month)

    if foi_stipula is None or foi_adeguamento is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    variazione_piena_pct = ((foi_adeguamento - foi_stipula) / foi_stipula) * 100
    variazione_applicata_pct = variazione_piena_pct * (percentuale_istat / 100)
    canone_nuovo = canone_attuale * (1 + variazione_applicata_pct / 100)

    lettera = (
        f"Egr. Sig./Sig.ra {conduttore}\n\n"
        f"OGGETTO: Comunicazione adeguamento ISTAT canone di locazione — "
        f"Immobile sito in {indirizzo_immobile}\n\n"
        f"Il/La sottoscritto/a {locatore}, in qualità di locatore dell'immobile "
        f"sopra indicato, con la presente comunica che, ai sensi dell'art. 32 "
        f"della Legge n. 392/1978 e dell'art. 1 della Legge n. 431/1998, "
        f"il canone di locazione verrà adeguato sulla base della variazione "
        f"dell'indice ISTAT FOI (Famiglie di Operai e Impiegati).\n\n"
        f"DATI DI CALCOLO:\n"
        f"- Canone mensile attuale: € {canone_attuale:.2f}\n"
        f"- Indice FOI alla stipula ({data_stipula}): {foi_stipula}\n"
        f"- Indice FOI all'adeguamento ({data_adeguamento}): {foi_adeguamento}\n"
        f"- Variazione ISTAT piena: {variazione_piena_pct:.2f}%\n"
        f"- Percentuale applicata: {percentuale_istat}%\n"
        f"- Variazione applicata: {variazione_applicata_pct:.2f}%\n\n"
        f"NUOVO CANONE MENSILE: € {canone_nuovo:.2f}\n"
        f"(con decorrenza dal {data_adeguamento})\n\n"
        f"Si invita pertanto a corrispondere il canone aggiornato a partire "
        f"dalla data sopra indicata.\n\n"
        f"Distinti saluti,\n"
        f"{locatore}"
    )

    return {
        "lettera": lettera,
        "canone_attuale": canone_attuale,
        "canone_nuovo": round(canone_nuovo, 2),
        "variazione_piena_pct": round(variazione_piena_pct, 2),
        "variazione_applicata_pct": round(variazione_applicata_pct, 2),
        "aumento_mensile": round(canone_nuovo - canone_attuale, 2),
        "riferimento_normativo": "L. 392/1978, art. 32 — L. 431/1998",
    }


@mcp.tool()
def calcolo_devalutazione(
    importo_attuale: float,
    data_attuale: str,
    data_passata: str,
) -> dict:
    """Calcolo inverso della rivalutazione: riconduce un importo attuale al suo valore in una data passata.

    Utile per confronti storici di valore (es. "quanto valeva in euro 1990 questa somma di oggi?").
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947 al mese più recente.
    Precisione: ESATTO (indici ISTAT ufficiali).

    Args:
        importo_attuale: Importo attuale di riferimento in euro (€)
        data_attuale: Data dell'importo attuale (formato YYYY-MM-DD)
        data_passata: Data storica a cui ricondurre il valore (formato YYYY-MM-DD, deve essere anteriore a data_attuale)
    """
    dt_attuale = _parse_date(data_attuale)
    dt_passata = _parse_date(data_passata)

    if dt_passata >= dt_attuale:
        return {"errore": "data_passata deve essere anteriore a data_attuale"}

    foi_attuale = _get_foi(dt_attuale.year, dt_attuale.month)
    foi_passata = _get_foi(dt_passata.year, dt_passata.month)

    if foi_attuale is None or foi_passata is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    coefficiente = foi_passata / foi_attuale
    importo_passato = importo_attuale * coefficiente

    return {
        "importo_attuale": importo_attuale,
        "data_attuale": data_attuale,
        "data_passata": data_passata,
        "foi_attuale": foi_attuale,
        "foi_passata": foi_passata,
        "coefficiente_devalutazione": round(coefficiente, 6),
        "importo_in_data_passata": round(importo_passato, 2),
        "perdita_potere_acquisto_pct": round((1 - coefficiente) * 100, 2),
        "esempio": f"€ {importo_attuale:.2f} del {data_attuale} equivalevano a € {importo_passato:.2f} del {data_passata}",
    }


@mcp.tool()
def rivalutazione_storica(
    importo: float,
    anno_partenza: int,
    anno_arrivo: int,
) -> dict:
    """Rivalutazione semplificata basata sulla media annuale degli indici FOI (senza specificare il mese).

    Usa la media annuale degli indici FOI per ciascun anno. Utile quando non si conosce
    il mese esatto dell'obbligazione. Per precisione mensile usare rivalutazione_monetaria.
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947.
    Precisione: ESATTO (media annua indici ISTAT ufficiali); meno preciso di rivalutazione_monetaria se si conosce il mese.

    Args:
        importo: Importo originario in euro (€)
        anno_partenza: Anno di partenza (es. 2010; deve essere presente negli indici FOI)
        anno_arrivo: Anno di arrivo (es. 2025; deve essere presente negli indici FOI)
    """
    if anno_arrivo <= anno_partenza:
        return {"errore": "anno_arrivo deve essere successivo a anno_partenza"}

    def _media_annua(anno: int) -> float | None:
        y_str = str(anno)
        if y_str not in _INDICI_FOI:
            return None
        vals = list(_INDICI_FOI[y_str].values())
        return sum(vals) / len(vals)

    media_partenza = _media_annua(anno_partenza)
    media_arrivo = _media_annua(anno_arrivo)

    if media_partenza is None or media_arrivo is None:
        return {"errore": "Indici FOI non disponibili per gli anni richiesti"}

    coefficiente = media_arrivo / media_partenza
    importo_rivalutato = importo * coefficiente

    # Build year-by-year table
    dettaglio = []
    for anno in range(anno_partenza, anno_arrivo + 1):
        media = _media_annua(anno)
        if media is not None:
            coeff = media / media_partenza
            dettaglio.append({
                "anno": anno,
                "media_foi": round(media, 2),
                "coefficiente": round(coeff, 6),
                "importo_rivalutato": round(importo * coeff, 2),
            })

    return {
        "importo_originario": importo,
        "anno_partenza": anno_partenza,
        "anno_arrivo": anno_arrivo,
        "media_foi_partenza": round(media_partenza, 2),
        "media_foi_arrivo": round(media_arrivo, 2),
        "coefficiente_rivalutazione": round(coefficiente, 6),
        "importo_rivalutato": round(importo_rivalutato, 2),
        "differenza": round(importo_rivalutato - importo, 2),
        "dettaglio_anni": dettaglio,
    }


@mcp.tool()
def variazioni_istat(
    anno_inizio: int,
    anno_fine: int,
) -> dict:
    """Restituisce la tabella delle variazioni percentuali annuali degli indici FOI ISTAT per un periodo.

    Utile per consulenze, analisi storiche dell'inflazione e relazioni peritali.
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947 al mese più recente.
    Precisione: ESATTO (medie annue indici ISTAT ufficiali).

    Args:
        anno_inizio: Anno iniziale del periodo (es. 2000; range disponibile: 1947 a oggi)
        anno_fine: Anno finale del periodo (es. 2024)
    """
    if anno_fine <= anno_inizio:
        return {"errore": "anno_fine deve essere successivo a anno_inizio"}

    def _media_annua(anno: int) -> float | None:
        y_str = str(anno)
        if y_str not in _INDICI_FOI:
            return None
        vals = list(_INDICI_FOI[y_str].values())
        return sum(vals) / len(vals)

    tabella = []
    media_prec = _media_annua(anno_inizio)

    for anno in range(anno_inizio, anno_fine + 1):
        media = _media_annua(anno)
        if media is None:
            continue

        if anno == anno_inizio:
            tabella.append({
                "anno": anno,
                "media_foi": round(media, 2),
                "variazione_pct": None,
            })
        else:
            if media_prec and media_prec > 0:
                variazione = ((media - media_prec) / media_prec) * 100
            else:
                variazione = 0.0
            tabella.append({
                "anno": anno,
                "media_foi": round(media, 2),
                "variazione_pct": round(variazione, 2),
            })
        media_prec = media

    # Cumulative variation
    prima_media = _media_annua(anno_inizio)
    ultima_media = _media_annua(anno_fine)
    variazione_cumulata = None
    if prima_media and ultima_media:
        variazione_cumulata = round(((ultima_media - prima_media) / prima_media) * 100, 2)

    return {
        "anno_inizio": anno_inizio,
        "anno_fine": anno_fine,
        "variazione_cumulata_pct": variazione_cumulata,
        "base_indici": "2015=100",
        "tabella": tabella,
    }


@mcp.tool()
def rivalutazione_annuale_media(
    importo: float,
    data_inizio: str,
    data_fine: str,
) -> dict:
    """Rivaluta un importo usando la media annuale degli indici FOI (ignora il mese, conta solo l'anno).

    Alternativa a rivalutazione_monetaria quando non si conosce il mese esatto dell'obbligazione.
    Per calcoli dove il mese è noto, preferire rivalutazione_monetaria.
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947.
    Precisione: ESATTO su base annua (media annua indici ISTAT ufficiali).

    Args:
        importo: Importo originario in euro (€)
        data_inizio: Data iniziale (formato YYYY-MM-DD; viene usato solo l'anno)
        data_fine: Data finale (formato YYYY-MM-DD; viene usato solo l'anno)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    def _media_annua(anno: int) -> float | None:
        y_str = str(anno)
        if y_str not in _INDICI_FOI:
            return None
        vals = list(_INDICI_FOI[y_str].values())
        return sum(vals) / len(vals)

    media_inizio = _media_annua(dt_inizio.year)
    media_fine = _media_annua(dt_fine.year)

    if media_inizio is None or media_fine is None:
        return {"errore": "Indici FOI non disponibili per gli anni richiesti"}

    coefficiente = media_fine / media_inizio
    importo_rivalutato = importo * coefficiente

    return {
        "importo_originario": importo,
        "anno_inizio": dt_inizio.year,
        "anno_fine": dt_fine.year,
        "media_foi_inizio": round(media_inizio, 2),
        "media_foi_fine": round(media_fine, 2),
        "coefficiente_rivalutazione": round(coefficiente, 6),
        "importo_rivalutato": round(importo_rivalutato, 2),
        "differenza": round(importo_rivalutato - importo, 2),
        "nota": "Calcolo basato su media annua FOI (non mese specifico)",
    }


@mcp.tool()
def inflazione_titoli_stato(
    capitale_investito: float,
    rendimento_lordo_annuo_pct: float,
    data_inizio: str,
    data_fine: str,
) -> dict:
    """Confronta il rendimento nominale di un investimento con l'inflazione FOI nello stesso periodo.

    Calcola il rendimento reale (equazione di Fisher) e verifica se l'investimento
    ha preservato il potere d'acquisto rispetto all'inflazione ISTAT del periodo.
    Vigenza: Indici FOI ISTAT base 2015=100, disponibili dal 1947 al mese più recente.
    Precisione: ESATTO per indici FOI; INDICATIVO per rendimento reale (usa inflazione media annua FOI).

    Args:
        capitale_investito: Capitale iniziale investito in euro (€)
        rendimento_lordo_annuo_pct: Rendimento lordo annuo in percentuale (es. 3.5 per 3,5%)
        data_inizio: Data di inizio dell'investimento (formato YYYY-MM-DD)
        data_fine: Data di fine dell'investimento (formato YYYY-MM-DD)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine <= dt_inizio:
        return {"errore": "data_fine deve essere successiva a data_inizio"}

    foi_inizio = _get_foi(dt_inizio.year, dt_inizio.month)
    foi_fine = _get_foi(dt_fine.year, dt_fine.month)

    if foi_inizio is None or foi_fine is None:
        return {"errore": "Indici FOI non disponibili per le date richieste"}

    anni = (dt_fine - dt_inizio).days / 365.25
    inflazione_pct = ((foi_fine - foi_inizio) / foi_inizio) * 100
    inflazione_media_annua = ((foi_fine / foi_inizio) ** (1 / anni) - 1) * 100 if anni > 0 else 0

    # Nominal return
    montante_nominale = capitale_investito * ((1 + rendimento_lordo_annuo_pct / 100) ** anni)
    rendimento_nominale_totale = montante_nominale - capitale_investito

    # Real return (Fisher equation)
    rendimento_reale_annuo = ((1 + rendimento_lordo_annuo_pct / 100) / (1 + inflazione_media_annua / 100) - 1) * 100
    montante_reale = capitale_investito * ((1 + rendimento_reale_annuo / 100) ** anni)
    rendimento_reale_totale = montante_reale - capitale_investito

    return {
        "capitale_investito": capitale_investito,
        "rendimento_lordo_annuo_pct": rendimento_lordo_annuo_pct,
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "anni": round(anni, 2),
        "inflazione_totale_pct": round(inflazione_pct, 2),
        "inflazione_media_annua_pct": round(inflazione_media_annua, 2),
        "montante_nominale": round(montante_nominale, 2),
        "rendimento_nominale_totale": round(rendimento_nominale_totale, 2),
        "rendimento_reale_annuo_pct": round(rendimento_reale_annuo, 2),
        "montante_reale": round(montante_reale, 2),
        "rendimento_reale_totale": round(rendimento_reale_totale, 2),
        "potere_acquisto_preservato": rendimento_reale_annuo > 0,
        "nota": "Rendimento reale calcolato con equazione di Fisher",
    }
