"""Calcolo pena con aggravanti/attenuanti (art. 63-69 c.p.), prescrizione del reato
(art. 157 ss. c.p., post L. 251/2005), patteggiamento (art. 444 c.p.p.), fine pena."""

from datetime import date, timedelta
from math import ceil

from src.server import mcp


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping day to month end."""
    total_months = d.month - 1 + months
    year = d.year + total_months // 12
    month = total_months % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


@mcp.tool()
def aumenti_riduzioni_pena(
    pena_base_mesi: float,
    aggravanti: list[dict] | None = None,
    attenuanti: list[dict] | None = None,
    recidiva: bool = False,
) -> dict:
    """Calcola la pena risultante applicando aggravanti, attenuanti e recidiva sulla pena base.

    Calcola la pena finale partendo dalla pena base edittale, applicando in sequenza
    recidiva (+1/3), aggravanti (aumenti percentuali) e attenuanti (riduzioni percentuali).
    Per simulare il patteggiamento usare pena_concordata; per la data fine pena usare fine_pena.
    Vigenza: Artt. 63-69 c.p. (aumenti/riduzioni); art. 99 c.p. (recidiva).
    Precisione: INDICATIVO (il giudice applica le variazioni discrezionalmente nei limiti di legge).

    Args:
        pena_base_mesi: Pena base in mesi (es. 24 per 2 anni; range tipico: 1-240)
        aggravanti: Lista di aggravanti, ciascuna con {'tipo': str, 'aumento_pct': float} (es. aumento_pct: 33.33 per +1/3)
        attenuanti: Lista di attenuanti, ciascuna con {'tipo': str, 'riduzione_pct': float} (es. riduzione_pct: 33.33 per -1/3)
        recidiva: True per applicare recidiva semplice art. 99 c.p. (+1/3 sulla pena base)
    """
    pena = pena_base_mesi
    dettaglio = [{"step": "Pena base", "mesi": round(pena, 2)}]

    if recidiva:
        aumento = pena / 3
        pena += aumento
        dettaglio.append({
            "step": "Recidiva semplice art. 99 c.p. (+1/3)",
            "aumento_mesi": round(aumento, 2),
            "mesi": round(pena, 2),
        })

    if aggravanti:
        for agg in aggravanti:
            aumento = pena * agg["aumento_pct"] / 100
            pena += aumento
            dettaglio.append({
                "step": f"Aggravante: {agg['tipo']} (+{agg['aumento_pct']}%)",
                "aumento_mesi": round(aumento, 2),
                "mesi": round(pena, 2),
            })

    if attenuanti:
        for att in attenuanti:
            riduzione = pena * att["riduzione_pct"] / 100
            pena -= riduzione
            dettaglio.append({
                "step": f"Attenuante: {att['tipo']} (-{att['riduzione_pct']}%)",
                "riduzione_mesi": round(riduzione, 2),
                "mesi": round(pena, 2),
            })

    anni = int(pena // 12)
    mesi_residui = round(pena % 12, 2)

    return {
        "pena_base_mesi": pena_base_mesi,
        "pena_risultante_mesi": round(pena, 2),
        "pena_risultante_formato": f"{anni} anni e {mesi_residui} mesi" if anni else f"{mesi_residui} mesi",
        "recidiva_applicata": recidiva,
        "dettaglio": dettaglio,
        "riferimento_normativo": "Artt. 63-69, 99 c.p.",
    }


@mcp.tool()
def conversione_pena(
    importo: float,
    direzione: str = "detentiva_a_pecuniaria",
    tipo_pena: str = "reclusione",
) -> dict:
    """Converte pena detentiva in pecuniaria (o viceversa) al tasso legale di €250/giorno.

    Vigenza: Art. 135 c.p. — tasso di conversione €250 per giorno (aggiornato periodicamente).
    Precisione: ESATTO per il tasso di legge vigente; verificare aggiornamenti al tasso ex art. 135 c.p.

    Args:
        importo: Giorni di pena detentiva (se direzione='detentiva_a_pecuniaria') oppure importo in euro (€) (se direzione='pecuniaria_a_detentiva')
        direzione: Direzione della conversione: 'detentiva_a_pecuniaria' o 'pecuniaria_a_detentiva'
        tipo_pena: Tipo di pena detentiva: 'reclusione' (delitti) o 'arresto' (contravvenzioni)
    """
    tasso_giornaliero = 250  # €250 per giorno (art. 135 c.p.)

    if direzione == "detentiva_a_pecuniaria":
        giorni = importo
        euro = giorni * tasso_giornaliero
        return {
            "direzione": direzione,
            "tipo_pena": tipo_pena,
            "giorni_detentivi": giorni,
            "importo_pecuniario_euro": round(euro, 2),
            "tasso_conversione": f"€{tasso_giornaliero}/giorno",
            "riferimento_normativo": "Art. 135 c.p.",
        }
    else:
        euro = importo
        giorni = ceil(euro / tasso_giornaliero)
        return {
            "direzione": direzione,
            "tipo_pena": tipo_pena,
            "importo_pecuniario_euro": euro,
            "giorni_detentivi": giorni,
            "tasso_conversione": f"€{tasso_giornaliero}/giorno",
            "riferimento_normativo": "Art. 135 c.p.",
        }


@mcp.tool()
def fine_pena(
    data_inizio_pena: str,
    pena_totale_mesi: float,
    liberazione_anticipata: bool = True,
    giorni_presofferto: int = 0,
) -> dict:
    """Calcola la data di fine pena con eventuale liberazione anticipata (45 giorni per semestre).

    Sottrae i giorni di presofferto (custodia cautelare) e calcola il beneficio della
    liberazione anticipata ex art. 54 L. 354/1975 (ordinamento penitenziario).
    Per calcolare la pena da scontare (con aggravanti/attenuanti) usare aumenti_riduzioni_pena.
    Vigenza: Art. 54 L. 354/1975 (ordinamento penitenziario).
    Precisione: INDICATIVO (la liberazione anticipata è concessa discrezionalmente dal magistrato di sorveglianza).

    Args:
        data_inizio_pena: Data di inizio esecuzione della pena (formato YYYY-MM-DD)
        pena_totale_mesi: Durata totale della pena da scontare in mesi (es. 36 per 3 anni)
        liberazione_anticipata: True per calcolare lo sconto di 45 giorni ogni semestre (default: True)
        giorni_presofferto: Giorni di custodia cautelare già scontati da sottrarre (default 0)
    """
    dt_inizio = _parse_date(data_inizio_pena)

    # Subtract presofferto
    dt_inizio_effettivo = dt_inizio - timedelta(days=giorni_presofferto)

    # Calculate end date
    mesi_interi = int(pena_totale_mesi)
    giorni_frazionari = round((pena_totale_mesi - mesi_interi) * 30)
    dt_fine = _add_months(dt_inizio_effettivo, mesi_interi) + timedelta(days=giorni_frazionari)

    result = {
        "data_inizio_pena": data_inizio_pena,
        "pena_totale_mesi": pena_totale_mesi,
        "giorni_presofferto": giorni_presofferto,
        "data_inizio_effettiva": dt_inizio_effettivo.isoformat(),
        "data_fine_pena": dt_fine.isoformat(),
    }

    if liberazione_anticipata:
        # 45 days reduction per semester served (art. 54 L. 354/1975)
        giorni_totali = (dt_fine - dt_inizio_effettivo).days
        semestri = giorni_totali // 180
        sconto_giorni = semestri * 45
        dt_fine_anticipata = dt_fine - timedelta(days=sconto_giorni)
        result.update({
            "liberazione_anticipata": {
                "semestri_scontati": semestri,
                "sconto_giorni": sconto_giorni,
                "data_fine_con_liberazione": dt_fine_anticipata.isoformat(),
            },
        })

    result["riferimento_normativo"] = "Art. 54 L. 354/1975 (Ordinamento penitenziario)"
    return result


@mcp.tool()
def prescrizione_reato(
    pena_massima_anni: float,
    data_commissione: str,
    interruzioni_giorni: int = 0,
    sospensioni_giorni: int = 0,
    tipo_reato: str = "delitto",
) -> dict:
    """Calcola il termine di prescrizione del reato e la data di prescrizione.

    Termine base: massimo edittale (min. 6 anni per delitti, 4 per contravvenzioni).
    Le interruzioni estendono il termine di 1/4; le sospensioni lo spostano in avanti.
    Attenzione: per reati con pena perpetua o con regimi speciali (es. mafia, corruzione post L. 3/2019)
    il calcolo standard non è applicabile.
    Vigenza: Art. 157-161 c.p. (post riforma L. 251/2005 — ex Cirielli; e L. 134/2021 — Riforma Cartabia).
    Precisione: INDICATIVO (il calcolo esatto dipende da interruzioni e sospensioni specifiche del processo).

    Args:
        pena_massima_anni: Pena massima edittale del reato in anni (es. 5.0; range tipico: 0.25-30)
        data_commissione: Data di commissione del reato (formato YYYY-MM-DD)
        interruzioni_giorni: Giorni totali di atti interruttivi (estendono il termine di 1/4)
        sospensioni_giorni: Giorni totali di sospensione della prescrizione (spostano la data in avanti)
        tipo_reato: Tipo di reato: 'delitto' (minimo 6 anni) o 'contravvenzione' (minimo 4 anni)
    """
    dt_commissione = _parse_date(data_commissione)

    # Base term: max sentence, with minimums (art. 157 c.p.)
    if tipo_reato == "delitto":
        termine_base_anni = max(pena_massima_anni, 6)
    else:
        termine_base_anni = max(pena_massima_anni, 4)

    # With interruption: +1/4 of base term
    termine_con_interruzione_anni = termine_base_anni
    aumento_interruzione_anni = 0.0
    if interruzioni_giorni > 0:
        aumento_interruzione_anni = termine_base_anni / 4
        termine_con_interruzione_anni = termine_base_anni + aumento_interruzione_anni

    # Calculate prescription date
    mesi_totali = int(termine_con_interruzione_anni * 12)
    dt_prescrizione = _add_months(dt_commissione, mesi_totali)

    # Add suspension days
    if sospensioni_giorni > 0:
        dt_prescrizione += timedelta(days=sospensioni_giorni)

    oggi = date.today()
    prescritto = oggi >= dt_prescrizione

    return {
        "tipo_reato": tipo_reato,
        "pena_massima_anni": pena_massima_anni,
        "data_commissione": data_commissione,
        "termine_base_anni": termine_base_anni,
        "aumento_interruzione_anni": round(aumento_interruzione_anni, 2),
        "termine_totale_anni": round(termine_con_interruzione_anni, 2),
        "sospensioni_giorni": sospensioni_giorni,
        "data_prescrizione": dt_prescrizione.isoformat(),
        "prescritto": prescritto,
        "giorni_alla_prescrizione": (dt_prescrizione - oggi).days if not prescritto else 0,
        "riferimento_normativo": "Art. 157-161 c.p.",
    }


@mcp.tool()
def pena_concordata(
    pena_base_mesi: float,
    attenuanti_generiche: bool = True,
    diminuente_rito: bool = True,
) -> dict:
    """Simula la pena patteggiata (art. 444 c.p.p.) con attenuanti generiche e diminuente di rito.

    Calcola la pena finale applicando -1/3 per attenuanti generiche (art. 62-bis c.p.) e
    -1/3 per la diminuente di rito del patteggiamento (art. 444 c.p.p.).
    Il patteggiamento è ammissibile se la pena finale è ≤ 5 anni (60 mesi).
    Per calcolare la pena base con aggravanti/attenuanti specifiche usare aumenti_riduzioni_pena.
    Vigenza: Art. 444 c.p.p. — Art. 62-bis c.p.
    Precisione: INDICATIVO (le riduzioni sono soggette a valutazione discrezionale del giudice).

    Args:
        pena_base_mesi: Pena base in mesi da cui partire (es. 36 per 3 anni; range tipico: 1-240)
        attenuanti_generiche: True per applicare attenuanti generiche art. 62-bis c.p. (-1/3 sulla pena base)
        diminuente_rito: True per applicare diminuente di rito art. 444 c.p.p. (-1/3 sulla pena dopo attenuanti)
    """
    pena = pena_base_mesi
    dettaglio = [{"step": "Pena base", "mesi": round(pena, 2)}]

    if attenuanti_generiche:
        riduzione = pena / 3
        pena -= riduzione
        dettaglio.append({
            "step": "Attenuanti generiche art. 62-bis c.p. (-1/3)",
            "riduzione_mesi": round(riduzione, 2),
            "mesi": round(pena, 2),
        })

    if diminuente_rito:
        riduzione = pena / 3
        pena -= riduzione
        dettaglio.append({
            "step": "Diminuente rito art. 444 c.p.p. (-1/3)",
            "riduzione_mesi": round(riduzione, 2),
            "mesi": round(pena, 2),
        })

    pena = round(pena, 2)
    anni = int(pena // 12)
    mesi_residui = round(pena % 12, 2)

    # Patteggiamento limits
    patteggiamento_possibile = pena <= 60  # 5 years max
    sospendibile = pena <= 24  # 2 years for conditional suspension

    return {
        "pena_base_mesi": pena_base_mesi,
        "pena_finale_mesi": pena,
        "pena_finale_formato": f"{anni} anni e {mesi_residui} mesi" if anni else f"{mesi_residui} mesi",
        "attenuanti_generiche": attenuanti_generiche,
        "diminuente_rito": diminuente_rito,
        "patteggiamento_possibile": patteggiamento_possibile,
        "sospendibile": sospendibile,
        "nota_sospensione": "Pena ≤ 2 anni: sospensione condizionale possibile" if sospendibile else "Pena > 2 anni: sospensione condizionale non applicabile",
        "dettaglio": dettaglio,
        "riferimento_normativo": "Art. 444 c.p.p. — Art. 62-bis c.p.",
    }
