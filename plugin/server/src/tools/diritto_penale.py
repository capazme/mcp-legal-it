"""Calcolo pena con aggravanti/attenuanti (art. 63-69 c.p.), prescrizione del reato
(art. 157 ss. c.p., post L. 251/2005), patteggiamento (art. 444 c.p.p.), fine pena."""

from datetime import date, timedelta
from math import ceil

from src.lib import _clock
from src.server import mcp


def _parse_date(d: str) -> date:
    try:
        return date.fromisoformat(d)
    except ValueError:
        raise ValueError(f"data non valida: '{d}', usare il formato YYYY-MM-DD")


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping day to month end."""
    total_months = d.month - 1 + months
    year = d.year + total_months // 12
    month = total_months % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


@mcp.tool(tags={"penale"})
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
    Chaining: → pena_concordata() per simulare un patteggiamento

    Args:
        pena_base_mesi: Pena base in mesi (es. 24 per 2 anni; range tipico: 1-240)
        aggravanti: Lista di aggravanti, ciascuna con {'tipo': str, 'aumento_pct': float} (es. aumento_pct: 33.33 per +1/3)
        attenuanti: Lista di attenuanti, ciascuna con {'tipo': str, 'riduzione_pct': float} (es. riduzione_pct: 33.33 per -1/3)
        recidiva: True per applicare recidiva semplice art. 99 c.p. (+1/3 sulla pena base)
    """
    if pena_base_mesi < 0:
        raise ValueError("pena_base_mesi non può essere negativa")

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
            pct = agg.get("aumento_pct")
            if pct is None:
                raise ValueError("ogni aggravante deve avere il campo 'aumento_pct'")
            tipo = agg.get("tipo", "aggravante")
            aumento = pena * pct / 100
            pena += aumento
            dettaglio.append({
                "step": f"Aggravante: {tipo} (+{pct}%)",
                "aumento_mesi": round(aumento, 2),
                "mesi": round(pena, 2),
            })

    if attenuanti:
        for att in attenuanti:
            pct = att.get("riduzione_pct")
            if pct is None:
                raise ValueError("ogni attenuante deve avere il campo 'riduzione_pct'")
            tipo = att.get("tipo", "attenuante")
            riduzione = pena * pct / 100
            pena -= riduzione
            dettaglio.append({
                "step": f"Attenuante: {tipo} (-{pct}%)",
                "riduzione_mesi": round(riduzione, 2),
                "mesi": round(pena, 2),
            })

    pena = max(0.0, pena)
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


@mcp.tool(tags={"penale"})
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
    if direzione not in {"detentiva_a_pecuniaria", "pecuniaria_a_detentiva"}:
        raise ValueError(
            "direzione non valida: usare 'detentiva_a_pecuniaria' o 'pecuniaria_a_detentiva'"
        )
    if importo < 0:
        raise ValueError("importo non può essere negativo")

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


@mcp.tool(tags={"penale"})
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
    if pena_totale_mesi < 0:
        raise ValueError("pena_totale_mesi non può essere negativa")
    if giorni_presofferto < 0:
        raise ValueError("giorni_presofferto non può essere negativo")

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


#: Confini dei regimi di prescrizione per data del fatto.
_ORLANDO_DAL = date(2017, 8, 3)      # L. 103/2017, art. 1 co. 11: art. 159 co. 2 c.p. (sospensioni post condanna)
_BLOCCO_DAL = date(2020, 1, 1)       # L. 3/2019, art. 1 co. 1 lett. e): la prescrizione cessa dopo il primo grado
_TRANSITORIO_FINO_AL = date(2024, 12, 31)  # L. 134/2021, art. 2 co. 5: termini di improcedibilita' allungati

#: Art. 161 co. 2 c.p.: aumento massimo per interruzioni, per stato di recidiva.
_AUMENTO_INTERRUZIONE = {
    "nessuna": (0.25, "un quarto (art. 161 co. 2 c.p.)"),
    "aggravata": (0.5, "la meta' (art. 161 co. 2 c.p. — recidiva ex art. 99 co. 2)"),
    "reiterata": (2 / 3, "due terzi (art. 161 co. 2 c.p. — recidiva ex art. 99 co. 4)"),
    "abituale": (1.0, "il doppio (art. 161 co. 2 c.p. — artt. 102, 103 e 105 c.p.)"),
}


def _regime_prescrizione(dt_commissione: date) -> dict:
    """Il regime della prescrizione applicabile ai fatti commessi in una data."""
    if dt_commissione < _ORLANDO_DAL:
        return {
            "nome": "ordinario (ex Cirielli)",
            "fatti": "commessi fino al 02/08/2017",
            "fonte": "artt. 157-161 c.p. nel testo della L. 251/2005",
            "descrizione": "La prescrizione decorre in ogni grado del giudizio; le interruzioni prolungano il termine entro il massimo dell'art. 161 co. 2.",
        }
    if dt_commissione < _BLOCCO_DAL:
        return {
            "nome": "riforma Orlando",
            "fatti": "commessi dal 03/08/2017 al 31/12/2019",
            "fonte": "artt. 157-161 c.p.; art. 159 co. 2 c.p. nel testo della L. 103/2017",
            "descrizione": "Come il regime ordinario, ma dopo la sentenza di condanna di primo grado il corso e' sospeso fino al deposito della sentenza di appello per non oltre 1 anno e 6 mesi, e dopo la condanna in appello fino alla sentenza definitiva per non oltre altri 1 anno e 6 mesi (art. 159 co. 2 nn. 1-2); la sospensione viene meno se il grado successivo assolve.",
        }
    return {
        "nome": "blocco dopo il primo grado e improcedibilità (L. 3/2019 e L. 134/2021)",
        "fatti": "commessi dal 01/01/2020",
        "fonte": "art. 161-bis c.p. (L. 134/2021, gia' art. 159 co. 2 nel testo della L. 3/2019); art. 344-bis c.p.p.",
        "descrizione": "La prescrizione decorre solo fino alla sentenza di primo grado (o al decreto penale di condanna), poi cessa definitivamente; nei gradi di impugnazione opera l'improcedibilita' per superamento dei termini di durata (2 anni in appello, 1 anno in Cassazione; 3 anni e 1 anno e 6 mesi per le impugnazioni proposte entro il 31/12/2024), prorogabili dal giudice nei casi dell'art. 344-bis co. 4 c.p.p.",
    }


@mcp.tool(tags={"penale"})
def prescrizione_reato(
    pena_massima_anni: float,
    data_commissione: str,
    interruzioni_giorni: int = 0,
    sospensioni_giorni: int = 0,
    tipo_reato: str = "delitto",
    recidiva: str = "nessuna",
    data_sentenza_primo_grado: str | None = None,
    data_sentenza_appello: str | None = None,
    data_impugnazione: str | None = None,
) -> dict:
    """Calcola il termine e la data di prescrizione del reato applicando il regime che dipende
    dalla data del fatto, e per i fatti dal 2020 i termini di improcedibilità dell'impugnazione.

    Termine base: massimo edittale (min. 6 anni per delitti, 4 per contravvenzioni, art. 157 c.p.).
    Le interruzioni prolungano il termine fino al massimo dell'art. 161 co. 2 (un quarto; la metà,
    due terzi o il doppio in caso di recidiva o abitualità); le sospensioni lo spostano in avanti.
    Attenzione: per reati con pena perpetua, reati ex art. 51 co. 3-bis e 3-quater c.p.p. e ipotesi
    di raddoppio ex art. 157 co. 6 c.p. il calcolo standard non è applicabile.
    Vigenza: artt. 157-161 c.p. (L. 251/2005) per i fatti fino al 02/08/2017; art. 159 co. 2 c.p. nel
    testo della L. 103/2017 per i fatti dal 03/08/2017 al 31/12/2019; art. 161-bis c.p. (L. 3/2019,
    poi L. 134/2021) e art. 344-bis c.p.p. per i fatti dal 01/01/2020. Le riforme del 2019-2021 sono
    di legge ordinaria, non del D.Lgs. 150/2022. Verificare con cite_law() eventuali modifiche
    successive di artt. 159 e 161-bis c.p. e 344-bis c.p.p.
    Precisione: INDICATIVO (il calcolo esatto dipende da interruzioni e sospensioni specifiche del
    processo; la decorrenza dell'improcedibilità è stimata sul termine ordinario di deposito della
    motivazione).
    Chaining: → cite_law() per verificare il testo della norma incriminatrice

    Args:
        pena_massima_anni: Pena massima edittale del reato in anni (es. 5.0; range tipico: 0.25-30)
        data_commissione: Data di commissione del reato (formato YYYY-MM-DD)
        interruzioni_giorni: Giorni totali di atti interruttivi (> 0 fa scattare l'aumento massimo
                             dell'art. 161 co. 2; il termine prolungato è quello massimo)
        sospensioni_giorni: Giorni totali di sospensione della prescrizione (spostano la data in avanti)
        tipo_reato: Tipo di reato: 'delitto' (minimo 6 anni) o 'contravvenzione' (minimo 4 anni)
        recidiva: Stato dell'imputato ai fini dell'art. 161 co. 2: 'nessuna' (+1/4), 'aggravata'
                  (art. 99 co. 2, +1/2), 'reiterata' (art. 99 co. 4, +2/3), 'abituale' (artt. 102,
                  103, 105: doppio)
        data_sentenza_primo_grado: Data della sentenza di primo grado (YYYY-MM-DD), opzionale: per i
                  fatti dal 2020 ferma la prescrizione e fa decorrere l'improcedibilità in appello
        data_sentenza_appello: Data della sentenza di appello (YYYY-MM-DD), opzionale: fa decorrere
                  l'improcedibilità in Cassazione (fatti dal 2020)
        data_impugnazione: Data di proposizione dell'impugnazione (YYYY-MM-DD), opzionale: entro il
                  31/12/2024 valgono i termini transitori di 3 anni (appello) e 1 anno e 6 mesi (Cassazione)
    """
    if pena_massima_anni < 0:
        raise ValueError("pena_massima_anni non può essere negativa")
    if interruzioni_giorni < 0:
        raise ValueError("interruzioni_giorni non può essere negativo")
    if sospensioni_giorni < 0:
        raise ValueError("sospensioni_giorni non può essere negativo")

    tr = tipo_reato.strip().lower()
    if tr not in {"delitto", "contravvenzione"}:
        raise ValueError(
            "tipo_reato non valido: usare 'delitto' o 'contravvenzione'"
        )
    rec = recidiva.strip().lower()
    if rec not in _AUMENTO_INTERRUZIONE:
        raise ValueError("recidiva non valida: usare 'nessuna', 'aggravata', 'reiterata' o 'abituale'")

    dt_commissione = _parse_date(data_commissione)
    dt_primo = _parse_date(data_sentenza_primo_grado) if data_sentenza_primo_grado else None
    dt_appello = _parse_date(data_sentenza_appello) if data_sentenza_appello else None
    dt_impugnazione = _parse_date(data_impugnazione) if data_impugnazione else None
    regime = _regime_prescrizione(dt_commissione)

    # Base term: max sentence, with minimums (art. 157 c.p.)
    if tr == "delitto":
        termine_base_anni = max(pena_massima_anni, 6)
    else:
        termine_base_anni = max(pena_massima_anni, 4)

    # With interruption: up to +1/4 (or more with recidiva) of base term (art. 161 co. 2)
    frazione, frazione_descr = _AUMENTO_INTERRUZIONE[rec]
    termine_con_interruzione_anni = termine_base_anni
    aumento_interruzione_anni = 0.0
    if interruzioni_giorni > 0:
        aumento_interruzione_anni = termine_base_anni * frazione
        termine_con_interruzione_anni = termine_base_anni + aumento_interruzione_anni

    # Calculate prescription date
    mesi_esatti = termine_con_interruzione_anni * 12
    mesi_interi = int(mesi_esatti)
    giorni_frazionari = round((mesi_esatti - mesi_interi) * 30)
    dt_prescrizione = _add_months(dt_commissione, mesi_interi) + timedelta(days=giorni_frazionari)

    # Add suspension days
    if sospensioni_giorni > 0:
        dt_prescrizione += timedelta(days=sospensioni_giorni)

    oggi = _clock.today()
    avvertenze = []
    prescrizione_cessata = False
    improcedibilita = None

    if dt_commissione >= _BLOCCO_DAL:
        # Art. 161-bis c.p.: il corso della prescrizione cessa con la sentenza di primo grado
        if dt_primo is not None:
            if dt_primo <= dt_prescrizione:
                prescrizione_cessata = True
                avvertenze.append(
                    f"Fatto dal 01/01/2020: la sentenza di primo grado del {dt_primo.isoformat()} e' "
                    "intervenuta prima della scadenza, quindi il corso della prescrizione e' cessato "
                    "definitivamente (art. 161-bis c.p.); nei gradi successivi rileva solo "
                    "l'improcedibilita' ex art. 344-bis c.p.p."
                )
            else:
                avvertenze.append(
                    f"La sentenza di primo grado del {dt_primo.isoformat()} e' successiva alla data di "
                    "prescrizione calcolata: il reato risulta prescritto prima del primo grado."
                )
        else:
            avvertenze.append(
                "Fatto dal 01/01/2020: la data calcolata vale solo fino alla sentenza di primo grado; "
                "dopo, la prescrizione non decorre piu' (art. 161-bis c.p.) e si applica "
                "l'improcedibilita' ex art. 344-bis c.p.p. Passare data_sentenza_primo_grado."
            )
        # Improcedibilita' (art. 344-bis c.p.p.): i termini decorrono dal 90° giorno successivo
        # alla scadenza del termine per il deposito della motivazione (art. 544 c.p.p.; qui il
        # termine ordinario di 15 giorni), prorogabili ex co. 4.
        transitorio = dt_impugnazione is not None and dt_impugnazione <= _TRANSITORIO_FINO_AL
        termini = {"appello": (36 if transitorio else 24), "cassazione": (18 if transitorio else 12)}
        improcedibilita = {
            "riferimento": "Art. 344-bis c.p.p. (L. 134/2021)" + ("; termini transitori art. 2 co. 5 L. 134/2021" if transitorio else ""),
            "regime_termini": "transitorio (impugnazione proposta entro il 31/12/2024)" if transitorio else "ordinario (impugnazioni dal 01/01/2025, o data di impugnazione non indicata)",
            "durata_massima_mesi": termini,
            "proroghe": "prorogabili con ordinanza motivata di 1 anno in appello e 6 mesi in Cassazione per giudizi complessi; per i reati ex art. 344-bis co. 4 le proroghe non hanno limite",
            "nota_decorrenza": "decorrenza stimata: 90° giorno dopo la scadenza del termine ordinario di 15 giorni per il deposito della motivazione (art. 544 co. 2 c.p.p.); con termini piu' lunghi o prorogati (art. 154 disp. att.) la decorrenza slitta",
        }
        if dt_primo is not None:
            decorrenza_app = dt_primo + timedelta(days=15 + 90)
            scadenza_app = _add_months(decorrenza_app, termini["appello"])
            improcedibilita["appello"] = {
                "decorrenza_stimata": decorrenza_app.isoformat(),
                "scadenza_stimata": scadenza_app.isoformat(),
                "mesi": termini["appello"],
            }
        if dt_appello is not None:
            decorrenza_cass = dt_appello + timedelta(days=15 + 90)
            scadenza_cass = _add_months(decorrenza_cass, termini["cassazione"])
            improcedibilita["cassazione"] = {
                "decorrenza_stimata": decorrenza_cass.isoformat(),
                "scadenza_stimata": scadenza_cass.isoformat(),
                "mesi": termini["cassazione"],
            }
    elif dt_commissione >= _ORLANDO_DAL and dt_primo is not None:
        sospesa_max = _add_months(dt_prescrizione, 18)
        avvertenze.append(
            "Fatto tra il 03/08/2017 e il 31/12/2019: se la sentenza di primo grado del "
            f"{dt_primo.isoformat()} e' di condanna, il corso e' sospeso fino alla sentenza di appello "
            f"per non oltre 18 mesi (art. 159 co. 2 n. 1): la prescrizione slitta al piu' tardi al "
            f"{sospesa_max.isoformat()}, e di altri 18 mesi al massimo dopo una condanna in appello."
        )

    prescritto = (not prescrizione_cessata) and oggi >= dt_prescrizione

    result = {
        "tipo_reato": tipo_reato,
        "pena_massima_anni": pena_massima_anni,
        "data_commissione": data_commissione,
        "regime": regime,
        "termine_base_anni": termine_base_anni,
        "recidiva": rec,
        "aumento_massimo_interruzioni": frazione_descr,
        "aumento_interruzione_anni": round(aumento_interruzione_anni, 2),
        "termine_totale_anni": round(termine_con_interruzione_anni, 2),
        "sospensioni_giorni": sospensioni_giorni,
        "data_prescrizione": dt_prescrizione.isoformat(),
        "prescrizione_cessata_con_primo_grado": prescrizione_cessata,
        "prescritto": prescritto,
        "giorni_alla_prescrizione": (dt_prescrizione - oggi).days if (not prescritto and not prescrizione_cessata) else 0,
        "riferimento_normativo": "Art. 157-161 c.p." + ("; art. 161-bis c.p. e art. 344-bis c.p.p." if dt_commissione >= _BLOCCO_DAL else ""),
    }
    if improcedibilita:
        result["improcedibilita"] = improcedibilita
    if avvertenze:
        result["avvertenze"] = avvertenze
    return result


@mcp.tool(tags={"penale"})
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
    if pena_base_mesi < 0:
        raise ValueError("pena_base_mesi non può essere negativa")

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

    pena = round(max(0.0, pena), 2)
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
