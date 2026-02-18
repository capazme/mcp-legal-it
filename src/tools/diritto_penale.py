"""Sezione 8 — Diritto Penale: calcolo pena, conversione, prescrizione, patteggiamento."""

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
    """Calcolo pena con aggravanti e attenuanti art. 63-69 c.p.

    Args:
        pena_base_mesi: Pena base in mesi
        aggravanti: Lista di aggravanti, ciascuna con {tipo: str, aumento_pct: float}
        attenuanti: Lista di attenuanti, ciascuna con {tipo: str, riduzione_pct: float}
        recidiva: Se applicare recidiva semplice art. 99 c.p. (+1/3)
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
    """Conversione pena detentiva ↔ pecuniaria art. 135 c.p.

    Args:
        importo: Giorni di pena detentiva (se detentiva_a_pecuniaria) o euro (se pecuniaria_a_detentiva)
        direzione: 'detentiva_a_pecuniaria' o 'pecuniaria_a_detentiva'
        tipo_pena: 'reclusione' o 'arresto'
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
    """Calcolo data fine pena con liberazione anticipata art. 54 L. 354/1975.

    Args:
        data_inizio_pena: Data inizio esecuzione pena (YYYY-MM-DD)
        pena_totale_mesi: Pena totale in mesi
        liberazione_anticipata: Se calcolare la liberazione anticipata (45gg ogni semestre)
        giorni_presofferto: Giorni di custodia cautelare da sottrarre
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
    """Calcolo termine prescrizione reato art. 157 c.p.

    Args:
        pena_massima_anni: Pena massima edittale in anni
        data_commissione: Data di commissione del reato (YYYY-MM-DD)
        interruzioni_giorni: Giorni di interruzione (estendono il termine di 1/4)
        sospensioni_giorni: Giorni di sospensione della prescrizione
        tipo_reato: 'delitto' o 'contravvenzione'
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
    """Simulazione patteggiamento art. 444 c.p.p.

    Args:
        pena_base_mesi: Pena base in mesi
        attenuanti_generiche: Se applicare attenuanti generiche art. 62-bis c.p. (-1/3)
        diminuente_rito: Se applicare la diminuente per rito abbreviato/patteggiamento (-1/3)
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
