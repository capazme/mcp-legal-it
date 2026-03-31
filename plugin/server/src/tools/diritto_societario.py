"""Calcoli di diritto societario: quorum assembleari (artt. 2368-2369, 2479 c.c.),
soglie organo di controllo SRL (art. 2477 c.c.), scadenze societarie,
costi di costituzione."""

from datetime import date, timedelta

from src.server import mcp


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _add_days(d: date, days: int) -> date:
    return d + timedelta(days=days)


@mcp.tool(tags={"societario"})
def quorum_assembleari(
    tipo_societa: str,
    tipo_delibera: str,
    capitale_totale: float,
    capitale_presente: float = 0,
    voti_favorevoli: float = 0,
) -> dict:
    """Verifica i quorum costitutivi e deliberativi per assemblee societarie.

    Calcola i quorum richiesti dalla legge per SPA (artt. 2368-2369 c.c.),
    SRL (art. 2479 c.c.) e cooperative (art. 2538 c.c.) in prima e seconda
    convocazione, verificando se i valori forniti li soddisfano.
    Precisione: INDICATIVO — lo statuto può prevedere quorum più elevati o,
    nei limiti di legge, più bassi.

    Args:
        tipo_societa: Tipo di società: 'spa', 'srl', 'cooperativa'
        tipo_delibera: Tipo di delibera: 'ordinaria', 'straordinaria', 'modifica_statuto', 'scioglimento'
        capitale_totale: Capitale sociale totale (o numero totale soci per cooperativa)
        capitale_presente: Capitale rappresentato in assemblea (o soci presenti per cooperativa); 0 se non calcolato
        voti_favorevoli: Capitale votante a favore (o soci favorevoli per cooperativa); 0 se non calcolato
    """
    if capitale_totale <= 0:
        raise ValueError("capitale_totale deve essere > 0")
    if capitale_presente < 0 or voti_favorevoli < 0:
        raise ValueError("capitale_presente e voti_favorevoli non possono essere negativi")
    if capitale_presente > capitale_totale:
        raise ValueError("capitale_presente non può superare capitale_totale")
    # voti_favorevoli vs capitale_presente: check only when capitale_presente > 0
    # (SRL uses voti_favorevoli on total capital, not on present)
    if capitale_presente > 0 and voti_favorevoli > capitale_presente:
        raise ValueError("voti_favorevoli non possono superare capitale_presente")
    if capitale_presente == 0 and voti_favorevoli > capitale_totale:
        raise ValueError("voti_favorevoli non possono superare capitale_totale")

    tipo_societa = tipo_societa.lower()
    tipo_delibera = tipo_delibera.lower()

    if tipo_societa not in ("spa", "srl", "cooperativa"):
        raise ValueError("tipo_societa deve essere 'spa', 'srl' o 'cooperativa'")
    if tipo_delibera not in ("ordinaria", "straordinaria", "modifica_statuto", "scioglimento"):
        raise ValueError("tipo_delibera deve essere 'ordinaria', 'straordinaria', 'modifica_statuto' o 'scioglimento'")

    pct_presente = (capitale_presente / capitale_totale * 100) if capitale_presente else None
    pct_favorevoli_su_totale = (voti_favorevoli / capitale_totale * 100) if voti_favorevoli else None
    pct_favorevoli_su_presenti = (voti_favorevoli / capitale_presente * 100) if voti_favorevoli and capitale_presente else None

    # ---- SPA ----------------------------------------------------------------
    if tipo_societa == "spa":
        if tipo_delibera == "ordinaria":
            quorum_cost_1a = "50%+1 del capitale (art. 2368 c.c.)"
            quorum_cost_2a = "Nessun quorum costitutivo (art. 2369 c.c.)"
            quorum_delib = "Maggioranza assoluta dei voti sui presenti (art. 2368 c.c.)"

            cost_raggiunto = (pct_presente is not None and pct_presente > 50)
            delib_raggiunto = (pct_favorevoli_su_presenti is not None and pct_favorevoli_su_presenti > 50)
            nota = "In seconda convocazione non è richiesto il quorum costitutivo; deliberativo rimane invariato."
            rif = "Artt. 2368-2369 c.c."
        elif tipo_delibera in ("straordinaria", "modifica_statuto"):
            quorum_cost_1a = "50%+1 del capitale (art. 2368 c.c.)"
            quorum_cost_2a = "Più di 1/3 del capitale (art. 2369 c.c.)"
            quorum_delib = "2/3 del capitale rappresentato in assemblea (art. 2368 c.c.)"

            cost_raggiunto = (pct_presente is not None and pct_presente > 50)
            delib_raggiunto = (pct_favorevoli_su_presenti is not None and pct_favorevoli_su_presenti >= 66.67)
            nota = "In seconda convocazione: costitutivo > 1/3 del capitale; deliberativo invariato (2/3 presenti)."
            rif = "Artt. 2368-2369 c.c."
        else:  # scioglimento
            quorum_cost_1a = "50%+1 del capitale (art. 2368 c.c.)"
            quorum_cost_2a = "50%+1 del capitale (nessuna deroga per scioglimento)"
            quorum_delib = "Maggioranza assoluta del capitale (art. 2484 c.c.)"
            cost_raggiunto = (pct_presente is not None and pct_presente > 50)
            delib_raggiunto = (pct_favorevoli_su_totale is not None and pct_favorevoli_su_totale > 50)
            nota = "Per lo scioglimento anticipato il quorum deliberativo è sulla maggioranza del capitale, non solo dei presenti."
            rif = "Artt. 2368-2369, 2484 c.c."

    # ---- SRL ----------------------------------------------------------------
    elif tipo_societa == "srl":
        quorum_cost_1a = "Nessun quorum costitutivo (art. 2479 c.c.)"
        quorum_cost_2a = "N/A — la SRL non ha seconda convocazione per legge"
        cost_raggiunto = True  # No costitutivo required
        if tipo_delibera == "ordinaria":
            quorum_delib = "Maggioranza del capitale (>50%) (art. 2479 c.c.)"
            delib_raggiunto = (pct_favorevoli_su_totale is not None and pct_favorevoli_su_totale > 50)
        elif tipo_delibera in ("straordinaria", "modifica_statuto"):
            quorum_delib = "Maggioranza del capitale (>50%) (art. 2479 c.c.)"
            delib_raggiunto = (pct_favorevoli_su_totale is not None and pct_favorevoli_su_totale > 50)
        else:  # scioglimento
            quorum_delib = "Almeno 2/3 del capitale (art. 2484 c.c.)"
            delib_raggiunto = (pct_favorevoli_su_totale is not None and pct_favorevoli_su_totale >= 66.67)
        nota = "Lo statuto SRL può prevedere quorum diversi (maggiori o minori nei limiti di legge). Non vi è seconda convocazione automatica."
        rif = "Artt. 2479, 2479-bis, 2484 c.c."

    # ---- COOPERATIVA --------------------------------------------------------
    else:
        quorum_cost_1a = "Metà più uno dei soci (art. 2538 c.c.) — voto per teste"
        quorum_cost_2a = "Nessun quorum costitutivo in seconda convocazione"
        quorum_delib = "Maggioranza dei soci presenti (art. 2538 c.c.) — voto per teste"
        cost_raggiunto = (pct_presente is not None and pct_presente > 50)
        delib_raggiunto = (pct_favorevoli_su_presenti is not None and pct_favorevoli_su_presenti > 50)
        nota = "Nelle cooperative il voto è per teste (ciascun socio = 1 voto), indipendentemente dalla quota di capitale."
        rif = "Art. 2538 c.c."

    result = {
        "tipo_societa": tipo_societa,
        "tipo_delibera": tipo_delibera,
        "capitale_totale": capitale_totale,
        "capitale_presente": capitale_presente if capitale_presente else "non fornito",
        "voti_favorevoli": voti_favorevoli if voti_favorevoli else "non fornito",
        "percentuale_presente": f"{round(pct_presente, 2)}%" if pct_presente is not None else "n/a",
        "percentuale_favorevoli_su_presenti": f"{round(pct_favorevoli_su_presenti, 2)}%" if pct_favorevoli_su_presenti is not None else "n/a",
        "percentuale_favorevoli_su_totale": f"{round(pct_favorevoli_su_totale, 2)}%" if pct_favorevoli_su_totale is not None else "n/a",
        "quorum_costitutivo_prima_conv": quorum_cost_1a,
        "quorum_costitutivo_seconda_conv": quorum_cost_2a,
        "quorum_deliberativo": quorum_delib,
        "raggiunto_costitutivo": cost_raggiunto,
        "raggiunto_deliberativo": delib_raggiunto if delib_raggiunto is not None else "dati insufficienti",
        "delibera_valida": (cost_raggiunto and bool(delib_raggiunto)) if delib_raggiunto is not None else False,
        "note": nota,
        "riferimento_normativo": rif,
    }
    return result


@mcp.tool(tags={"societario"})
def soglie_organo_controllo_srl(
    ricavi: float,
    attivo: float,
    dipendenti: int,
) -> dict:
    """Verifica se una SRL supera le soglie che obbligano alla nomina di organo di controllo o revisore.

    Applica i limiti dell'art. 2477 c.c. come modificato dal D.Lgs. 14/2019 (Codice della Crisi).
    L'obbligo scatta se almeno uno dei tre limiti è superato per DUE esercizi consecutivi.
    Usare per capire se è necessario nominare sindaco unico, collegio sindacale o revisore legale.
    Precisione: ESATTO sui limiti di legge vigenti; la verifica sul biennio richiede i dati dei due esercizi.

    Args:
        ricavi: Ricavi delle vendite e delle prestazioni dell'ultimo esercizio (€)
        attivo: Totale attivo dello stato patrimoniale dell'ultimo esercizio (€)
        dipendenti: Numero medio di dipendenti occupati nell'ultimo esercizio
    """
    if ricavi < 0 or attivo < 0 or dipendenti < 0:
        raise ValueError("ricavi, attivo e dipendenti non possono essere negativi")

    SOGLIA_RICAVI = 4_000_000.0
    SOGLIA_ATTIVO = 4_000_000.0
    SOGLIA_DIPENDENTI = 20

    limiti_superati = []
    dettaglio = []

    if ricavi > SOGLIA_RICAVI:
        limiti_superati.append("ricavi")
    dettaglio.append({
        "parametro": "ricavi",
        "valore": ricavi,
        "soglia": SOGLIA_RICAVI,
        "superato": ricavi > SOGLIA_RICAVI,
    })

    if attivo > SOGLIA_ATTIVO:
        limiti_superati.append("attivo")
    dettaglio.append({
        "parametro": "attivo",
        "valore": attivo,
        "soglia": SOGLIA_ATTIVO,
        "superato": attivo > SOGLIA_ATTIVO,
    })

    if dipendenti > SOGLIA_DIPENDENTI:
        limiti_superati.append("dipendenti")
    dettaglio.append({
        "parametro": "dipendenti",
        "valore": dipendenti,
        "soglia": SOGLIA_DIPENDENTI,
        "superato": dipendenti > SOGLIA_DIPENDENTI,
    })

    obbligo_condizionato = len(limiti_superati) >= 1

    return {
        "obbligo_nomina": obbligo_condizionato,
        "limiti_superati": limiti_superati,
        "numero_limiti_superati": len(limiti_superati),
        "dettaglio": dettaglio,
        "soglie": {
            "ricavi_euro": SOGLIA_RICAVI,
            "attivo_euro": SOGLIA_ATTIVO,
            "dipendenti": SOGLIA_DIPENDENTI,
        },
        "note": (
            "ATTENZIONE: l'obbligo di nomina scatta solo se almeno uno dei limiti è superato per DUE ESERCIZI CONSECUTIVI "
            "(art. 2477 c.c. come modificato da D.Lgs. 14/2019). "
            "Il calcolo verifica i valori dell'esercizio fornito: confrontare con l'esercizio precedente."
            if obbligo_condizionato else
            "Nessun limite superato nell'esercizio fornito: non sussiste obbligo di nomina (salvo previsione statutaria)."
        ),
        "riferimento_normativo": "Art. 2477 c.c. — D.Lgs. 14/2019 (Codice della Crisi d'Impresa)",
    }


@mcp.tool(tags={"societario"})
def scadenze_societarie(
    data_chiusura_esercizio: str,
    bilancio_differito: bool = False,
) -> dict:
    """Calcola le principali scadenze societarie annuali a partire dalla chiusura dell'esercizio.

    Determina le date limite per: approvazione bilancio, deposito CCIAA, convocazione
    assemblea (SPA e SRL), deposito bilancio presso sede sociale.
    Usare ogni anno dopo la chiusura dell'esercizio per pianificare gli adempimenti societari.
    Precisione: ESATTO sui termini di legge; verificare eventuali proroghe Covid o emergenziali.

    Args:
        data_chiusura_esercizio: Data di chiusura dell'esercizio (formato YYYY-MM-DD, es. '2024-12-31')
        bilancio_differito: True se ricorrono particolari esigenze (es. gruppo, struttura complessa): termine passa da 120 a 180 giorni (art. 2364 c.c.)
    """
    dt_chiusura = _parse_date(data_chiusura_esercizio)

    # Approvazione bilancio: 120 o 180 giorni dalla chiusura (art. 2364 c.c.)
    giorni_approvazione = 180 if bilancio_differito else 120
    dt_approvazione = _add_days(dt_chiusura, giorni_approvazione)

    # Deposito CCIAA: 30 giorni dall'approvazione (art. 2435 c.c.)
    dt_deposito_cciaa = _add_days(dt_approvazione, 30)

    # Convocazione assemblea SPA: 15 giorni prima dell'assemblea (art. 2366 c.c.)
    # → termine per inviare convocazione
    dt_convocazione_spa = _add_days(dt_approvazione, -15)

    # Convocazione assemblea SRL: 8 giorni prima (art. 2479-bis c.c.)
    dt_convocazione_srl = _add_days(dt_approvazione, -8)

    # Deposito bilancio presso sede: 15 giorni prima dell'assemblea (art. 2429 c.c.)
    dt_deposito_sede = _add_days(dt_approvazione, -15)

    # Pubblicazione verbale assemblea nel registro imprese: 30 giorni dall'assemblea
    dt_iscrizione_verbale = _add_days(dt_approvazione, 30)

    return {
        "data_chiusura_esercizio": data_chiusura_esercizio,
        "bilancio_differito": bilancio_differito,
        "scadenze": {
            "termine_approvazione_bilancio": {
                "data": dt_approvazione.isoformat(),
                "giorni_dalla_chiusura": giorni_approvazione,
                "nota": f"{'180 giorni — bilancio differito' if bilancio_differito else '120 giorni — termine ordinario'} (art. 2364 c.c.)",
            },
            "convocazione_assemblea_spa": {
                "data": dt_convocazione_spa.isoformat(),
                "nota": "Termine entro cui inviare la convocazione ai soci SPA — 15 giorni prima (art. 2366 c.c.)",
            },
            "convocazione_assemblea_srl": {
                "data": dt_convocazione_srl.isoformat(),
                "nota": "Termine entro cui inviare la convocazione ai soci SRL — 8 giorni prima (art. 2479-bis c.c.)",
            },
            "deposito_bilancio_sede_sociale": {
                "data": dt_deposito_sede.isoformat(),
                "nota": "Bilancio e relazioni disponibili in sede — 15 giorni prima dell'assemblea (art. 2429 c.c.)",
            },
            "deposito_cciaa": {
                "data": dt_deposito_cciaa.isoformat(),
                "giorni_dall_approvazione": 30,
                "nota": "Deposito bilancio approvato al Registro Imprese — 30 giorni dall'approvazione (art. 2435 c.c.)",
            },
            "iscrizione_verbale_assemblea": {
                "data": dt_iscrizione_verbale.isoformat(),
                "nota": "Iscrizione verbale assemblea al Registro Imprese — 30 giorni dall'assemblea (art. 2436 c.c.)",
            },
        },
        "riferimento_normativo": "Artt. 2364, 2366, 2429, 2435, 2436, 2479-bis c.c.",
    }


@mcp.tool(tags={"societario"})
def costi_costituzione(
    tipo_societa: str,
) -> dict:
    """Stima i costi di costituzione di una società o impresa individuale (valori 2025-2026).

    Fornisce una stima delle principali voci di costo: onorario notarile, imposte,
    diritti CCIAA, capitale minimo. I costi notarili variano significativamente per
    zona geografica, complessità dello statuto e valore del capitale versato.
    Precisione: INDICATIVO — ottenere preventivo dal notaio scelto.
    Chaining: → cite_law() per verificare il testo aggiornato degli artt. 2463, 2327 c.c.

    Args:
        tipo_societa: Tipo di società: 'srl', 'srls', 'spa', 'sas', 'snc', 'ditta_individuale'
    """
    tipo_societa = tipo_societa.lower()

    TIPI_VALIDI = ("srl", "srls", "spa", "sas", "snc", "ditta_individuale")
    if tipo_societa not in TIPI_VALIDI:
        raise ValueError(f"tipo_societa deve essere uno tra: {', '.join(TIPI_VALIDI)}")

    if tipo_societa == "srl":
        voci = [
            {"voce": "Onorario notarile", "min": 1500.0, "max": 2500.0, "note": "Varia per zona e complessità statuto"},
            {"voce": "Imposta di registro", "min": 200.0, "max": 200.0, "note": "Fissa (DPR 131/1986)"},
            {"voce": "Bolli e diritti", "min": 156.0, "max": 156.0, "note": "Marche da bollo su atto e copia"},
            {"voce": "Diritto CCIAA (annuale)", "min": 120.0, "max": 120.0, "note": "Diritto annuale — varia per provincia"},
            {"voce": "Diritti MiSE (pratiche Registro Imprese)", "min": 90.0, "max": 90.0, "note": "Diritti di segreteria"},
            {"voce": "Tassa di concessione governativa", "min": 309.87, "max": 309.87, "note": "Art. 23 Tariffa TCG"},
        ]
        capitale_minimo = 1.0
        capitale_consigliato = 10000.0
        rif = "Art. 2463 c.c. — D.M. 55/2014 — DPR 131/1986"
        note_extra = "Il capitale minimo legale è €1, ma è consigliato almeno €10.000 per operatività e credibilità."

    elif tipo_societa == "srls":
        voci = [
            {"voce": "Onorario notarile", "min": 0.0, "max": 0.0, "note": "GRATUITO — atto standard tabellare (art. 2463-bis c.c.)"},
            {"voce": "Imposta di registro", "min": 200.0, "max": 200.0, "note": "Fissa (DPR 131/1986)"},
            {"voce": "Bolli e diritti", "min": 0.0, "max": 0.0, "note": "ESENTI per SRLS (art. 3 c. 1 D.L. 1/2012)"},
            {"voce": "Diritto CCIAA (annuale)", "min": 120.0, "max": 120.0, "note": "Diritto annuale — varia per provincia"},
            {"voce": "Diritti MiSE", "min": 90.0, "max": 90.0, "note": "Diritti di segreteria Registro Imprese"},
        ]
        capitale_minimo = 1.0
        capitale_consigliato = 9999.0
        rif = "Art. 2463-bis c.c. — D.L. 1/2012 conv. L. 27/2012"
        note_extra = "La SRLS deve adottare lo statuto standard ministeriale. Capitale: €1–€9.999 (oltre = SRL ordinaria)."

    elif tipo_societa == "spa":
        voci = [
            {"voce": "Onorario notarile", "min": 2500.0, "max": 4000.0, "note": "Varia per zona, complessità e capitale versato"},
            {"voce": "Imposta di registro", "min": 200.0, "max": 200.0, "note": "Fissa (DPR 131/1986)"},
            {"voce": "Bolli e diritti", "min": 156.0, "max": 156.0, "note": "Marche da bollo su atto e copia"},
            {"voce": "Diritto CCIAA (annuale)", "min": 120.0, "max": 120.0, "note": "Diritto annuale — varia per provincia"},
            {"voce": "Diritti MiSE", "min": 90.0, "max": 90.0, "note": "Diritti di segreteria"},
            {"voce": "Tassa di concessione governativa", "min": 309.87, "max": 309.87, "note": "Art. 23 Tariffa TCG"},
        ]
        capitale_minimo = 50000.0
        capitale_consigliato = 50000.0
        rif = "Art. 2327 c.c. — DPR 131/1986"
        note_extra = "Capitale minimo €50.000; almeno 3/10 del conferimento in denaro va versato all'atto della costituzione."

    elif tipo_societa == "sas":
        voci = [
            {"voce": "Onorario notarile", "min": 1000.0, "max": 1500.0, "note": "Varia per zona e complessità"},
            {"voce": "Imposta di registro", "min": 200.0, "max": 200.0, "note": "Fissa (DPR 131/1986)"},
            {"voce": "Bolli e diritti", "min": 156.0, "max": 156.0, "note": "Marche da bollo su atto e copia"},
            {"voce": "Diritto CCIAA (annuale)", "min": 120.0, "max": 120.0, "note": "Diritto annuale — varia per provincia"},
        ]
        capitale_minimo = 0.0
        capitale_consigliato = None
        rif = "Artt. 2313-2324 c.c. — DPR 131/1986"
        note_extra = "Nessun capitale minimo. Il socio accomandatario risponde illimitatamente; l'accomandante è limitato al conferimento."

    elif tipo_societa == "snc":
        voci = [
            {"voce": "Onorario notarile", "min": 800.0, "max": 1200.0, "note": "Varia per zona e complessità (atto pubblico o scrittura privata autenticata)"},
            {"voce": "Imposta di registro", "min": 200.0, "max": 200.0, "note": "Fissa (DPR 131/1986)"},
            {"voce": "Bolli e diritti", "min": 156.0, "max": 156.0, "note": "Marche da bollo su atto e copia"},
            {"voce": "Diritto CCIAA (annuale)", "min": 120.0, "max": 120.0, "note": "Diritto annuale — varia per provincia"},
        ]
        capitale_minimo = 0.0
        capitale_consigliato = None
        rif = "Artt. 2291-2312 c.c. — DPR 131/1986"
        note_extra = "Nessun capitale minimo. Tutti i soci rispondono illimitatamente e solidalmente delle obbligazioni sociali."

    else:  # ditta_individuale
        voci = [
            {"voce": "Diritto CCIAA (iscrizione)", "min": 53.0, "max": 53.0, "note": "Diritto annuale ditta individuale"},
            {"voce": "Diritti MiSE (pratiche RI)", "min": 18.0, "max": 18.0, "note": "Diritti di segreteria Registro Imprese"},
            {"voce": "Bolli", "min": 17.50, "max": 17.50, "note": "Marche da bollo"},
        ]
        capitale_minimo = 0.0
        capitale_consigliato = None
        rif = "Artt. 2082, 2195 c.c. — L. 580/1993"
        note_extra = "Nessun atto notarile richiesto. Il titolare risponde con tutto il patrimonio personale."

    totale_min = round(sum(v["min"] for v in voci), 2)
    totale_max = round(sum(v["max"] for v in voci), 2)

    result = {
        "tipo_societa": tipo_societa,
        "voci_costo": voci,
        "totale_stimato_min": totale_min,
        "totale_stimato_max": totale_max,
        "totale_stimato_formato": f"€{totale_min:,.2f} – €{totale_max:,.2f}".replace(",", "."),
        "capitale_minimo": capitale_minimo,
        "capitale_consigliato": capitale_consigliato,
        "note": note_extra,
        "avvertenza": "INDICATIVO — i costi notarili variano per zona geografica e complessità dell'operazione. Richiedere preventivo al notaio.",
        "riferimento_normativo": rif,
    }
    return result
