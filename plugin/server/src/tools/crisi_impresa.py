"""Strumenti per la crisi d'impresa e l'insolvenza: indicatori di crisi (art. 3 CCII D.Lgs. 14/2019),
composizione negoziata (artt. 12-25-undecies CCII), concordato preventivo (artt. 84-120 CCII),
compenso OCC (D.M. 202/2014)."""

from src.server import mcp


@mcp.tool(tags={"crisi_impresa"})
def test_crisi_impresa(
    dscr: float,
    giorni_ritardo_inps: int = 0,
    giorni_ritardo_ade: int = 0,
    esposizioni_scadute_pct: float = 0.0,
    debiti_vs_attivo_pct: float = 0.0,
) -> dict:
    """Verifica la presenza di indicatori di crisi d'impresa ai sensi dell'art. 3 CCII (D.Lgs. 14/2019).

    Valuta cinque indicatori di allerta per rilevare precocemente lo stato di crisi:
    DSCR prospettico a 6 mesi, ritardo pagamenti INPS/AdE, esposizioni bancarie scadute,
    incidenza debiti sull'attivo. Qualsiasi indicatore attivato comporta l'obbligo di adottare
    misure idonee al superamento della crisi o all'accesso a strumenti di regolazione.
    Vigenza: Art. 3 D.Lgs. 14/2019 (CCII) come modificato dal D.Lgs. 83/2022.
    Precisione: INDICATIVO — il DSCR va calcolato su budget di cassa certificato da advisor.
    Chaining: → composizione_negoziata() per verificare l'accesso allo strumento di risanamento

    Args:
        dscr: Debt Service Coverage Ratio prospettico a 6 mesi (es. 0.8 = copertura insufficiente; < 1.0 = allerta)
        giorni_ritardo_inps: Giorni di ritardo nei pagamenti INPS rispetto alle scadenze (> 90 = allerta)
        giorni_ritardo_ade: Giorni di ritardo nei pagamenti Agenzia delle Entrate (> 90 = allerta)
        esposizioni_scadute_pct: Percentuale di esposizioni bancarie scadute sul totale (> 5.0% = allerta)
        debiti_vs_attivo_pct: Rapporto debiti totali / attivo totale in percentuale (> 80% = allerta)
    """
    if dscr < 0:
        raise ValueError("dscr non può essere negativo")

    indicatori_attivati = []

    if dscr < 1.0:
        indicatori_attivati.append(
            f"DSCR {dscr:.2f} < 1.0 — flusso di cassa insufficiente a coprire il servizio del debito nei 6 mesi"
        )
    if giorni_ritardo_inps > 90:
        indicatori_attivati.append(
            f"Ritardo INPS {giorni_ritardo_inps} giorni > 90 — esposizione previdenziale scaduta"
        )
    if giorni_ritardo_ade > 90:
        indicatori_attivati.append(
            f"Ritardo AdE {giorni_ritardo_ade} giorni > 90 — esposizione fiscale scaduta"
        )
    if esposizioni_scadute_pct > 5.0:
        indicatori_attivati.append(
            f"Esposizioni bancarie scadute {esposizioni_scadute_pct:.1f}% > 5% — deterioramento credito bancario"
        )
    if debiti_vs_attivo_pct > 80.0:
        indicatori_attivati.append(
            f"Debiti/Attivo {debiti_vs_attivo_pct:.1f}% > 80% — eccessivo indebitamento rispetto al patrimonio"
        )

    n = len(indicatori_attivati)
    alert = n > 0

    if n >= 3:
        severita = "critico"
        raccomandazione = (
            "Situazione critica: attivare immediatamente la composizione negoziata (art. 12 CCII) "
            "o valutare il concordato preventivo (art. 84 CCII). Convocare organo amministrativo "
            "e coinvolgere advisor entro 30 giorni."
        )
    elif n == 2:
        severita = "significativo"
        raccomandazione = (
            "Situazione significativa: predisporre piano di risanamento, valutare la composizione "
            "negoziata (art. 12 CCII) e monitorare mensilmente gli indicatori."
        )
    elif n == 1:
        severita = "moderato"
        raccomandazione = (
            "Situazione moderata: adottare misure correttive interne, aggiornare il budget di cassa "
            "e verificare nuovamente gli indicatori entro 90 giorni."
        )
    else:
        severita = "nessuno"
        raccomandazione = (
            "Nessun indicatore di crisi rilevato. Continuare il monitoraggio periodico "
            "ai sensi dell'art. 3 co. 3 CCII."
        )

    return {
        "alert": alert,
        "severita": severita,
        "indicatori_attivati": indicatori_attivati,
        "numero_indicatori": n,
        "dscr": dscr,
        "raccomandazione": raccomandazione,
        "riferimento_normativo": "Art. 3 D.Lgs. 14/2019 (CCII) — Indicatori della crisi",
    }


@mcp.tool(tags={"crisi_impresa"})
def composizione_negoziata(
    fatturato: float,
    attivo: float,
    dipendenti: int,
    debito_totale: float,
    tipo_impresa: str = "commerciale",
) -> dict:
    """Verifica l'ammissibilità alla composizione negoziata della crisi e valuta gli indicatori finanziari.

    La composizione negoziata (artt. 12-25-undecies CCII) è uno strumento stragiudiziale che consente
    all'imprenditore in stato di crisi o insolvenza reversibile di negoziare con i creditori
    con l'assistenza di un esperto indipendente nominato dalla CCIAA competente.
    Vigenza: Artt. 12-25-undecies D.Lgs. 14/2019 (CCII) come modificato dal D.Lgs. 83/2022.
    Precisione: INDICATIVO — l'ammissibilità definitiva è valutata dall'esperto nominato dalla CCIAA.
    Chaining: → concordato_preventivo() se la composizione negoziata fallisce

    Args:
        fatturato: Fatturato annuo in euro (es. 500000.0)
        attivo: Totale attivo patrimoniale in euro (es. 800000.0)
        dipendenti: Numero di dipendenti (es. 10)
        debito_totale: Debito totale in euro (es. 300000.0)
        tipo_impresa: Tipo di impresa: 'commerciale' (default), 'agricola' (art. 25-quater), 'sotto_soglia' (art. 2 co. 1 lett. d CCII)
    """
    if any(v < 0 for v in [fatturato, attivo, debito_totale]):
        raise ValueError("I valori finanziari non possono essere negativi")
    if dipendenti < 0:
        raise ValueError("Il numero di dipendenti non può essere negativo")

    # Verifica requisiti di accesso per tipo impresa
    requisiti_soddisfatti = []
    ammissibile = False

    if tipo_impresa == "commerciale":
        ammissibile = True
        requisiti_soddisfatti.append("Impresa commerciale: accesso diretto (art. 12 co. 1 CCII)")
    elif tipo_impresa == "agricola":
        ammissibile = True
        requisiti_soddisfatti.append("Impresa agricola: accesso ex art. 25-quater CCII")
    elif tipo_impresa == "sotto_soglia":
        # Art. 2 co. 1 lett. d: almeno uno dei tre parametri sotto soglia
        sotto_attivo = attivo <= 300_000
        sotto_ricavi = fatturato <= 200_000
        sotto_debiti = debito_totale <= 500_000
        if sotto_attivo or sotto_ricavi or sotto_debiti:
            ammissibile = True
            if sotto_attivo:
                requisiti_soddisfatti.append(f"Attivo ≤ €300.000 (attuale: €{attivo:,.2f})")
            if sotto_ricavi:
                requisiti_soddisfatti.append(f"Ricavi ≤ €200.000 (attuale: €{fatturato:,.2f})")
            if sotto_debiti:
                requisiti_soddisfatti.append(f"Debiti ≤ €500.000 (attuale: €{debito_totale:,.2f})")
            requisiti_soddisfatti.append("Impresa sotto soglia: ammessa ex art. 2 co. 1 lett. d CCII")
        else:
            ammissibile = False
            requisiti_soddisfatti.append(
                "Impresa sotto soglia: nessuna soglia rispettata — non ammissibile come sotto_soglia"
            )
    else:
        raise ValueError(f"tipo_impresa non valido: '{tipo_impresa}'. Usare 'commerciale', 'agricola' o 'sotto_soglia'")

    # Indicatori finanziari
    rapporto_debito_fatturato = round(debito_totale / fatturato, 2) if fatturato > 0 else None
    rapporto_debito_attivo = round(debito_totale / attivo * 100, 1) if attivo > 0 else None
    risanamento_ragionevole = debito_totale < 2 * fatturato if fatturato > 0 else False

    indicatori = {
        "rapporto_debito_fatturato": rapporto_debito_fatturato,
        "rapporto_debito_attivo_pct": rapporto_debito_attivo,
        "risanamento_ragionevole": risanamento_ragionevole,
        "nota_risanamento": (
            "Rapporto debito/fatturato < 2: risanamento potenzialmente ragionevole"
            if risanamento_ragionevole
            else "Rapporto debito/fatturato ≥ 2: risanamento difficile — valutare procedure concorsuali"
        ),
    }

    misure_protettive = [
        "Sospensione azioni esecutive e cautelari (art. 18 CCII)",
        "Sospensione obbligo di scioglimento per perdita capitale (art. 20 CCII)",
        "Prededuzione dei finanziamenti interinali (art. 22 CCII)",
        "Sospensione revocatoria per atti in esecuzione del piano (art. 24 CCII)",
    ]

    return {
        "ammissibile": ammissibile,
        "tipo_impresa": tipo_impresa,
        "requisiti_soddisfatti": requisiti_soddisfatti,
        "indicatori": indicatori,
        "durata_max": "180 giorni + proroga di ulteriori 180 giorni (art. 13 CCII)",
        "misure_protettive": misure_protettive,
        "riferimento_normativo": "Artt. 12-25-undecies D.Lgs. 14/2019 (CCII) — Composizione negoziata",
    }


@mcp.tool(tags={"crisi_impresa"})
def concordato_preventivo(
    creditori_privilegiati: float,
    creditori_chirografari: float,
    proposta_pct_chirografari: float,
    proposta_pct_privilegiati: float = 100.0,
    tipo: str = "continuita",
) -> dict:
    """Verifica l'ammissibilità e calcola i parametri del concordato preventivo (artt. 84-120 CCII).

    Il concordato preventivo consente all'imprenditore insolvente di proporre ai creditori
    un piano di soddisfazione parziale. In continuità (art. 84 co. 2) non esiste una soglia
    minima di soddisfazione; in liquidazione (art. 84 co. 4) i chirografari devono ricevere almeno il 20%.
    I creditori privilegiati devono essere soddisfatti integralmente salvo degradazione consensuale.
    Vigenza: Artt. 84-120 D.Lgs. 14/2019 (CCII).
    Precisione: INDICATIVO — l'ammissibilità è soggetta a verifica del Tribunale.
    Chaining: → compenso_occ() per stimare i costi della procedura

    Args:
        creditori_privilegiati: Totale crediti privilegiati in euro (es. 200000.0)
        creditori_chirografari: Totale crediti chirografari in euro (es. 500000.0)
        proposta_pct_chirografari: Percentuale di soddisfazione proposta per i chirografari (0-100)
        proposta_pct_privilegiati: Percentuale di soddisfazione proposta per i privilegiati (0-100; default 100)
        tipo: Tipo di concordato: 'continuita' (art. 84 co. 2, no soglia minima) o 'liquidatorio' (art. 84 co. 4, min 20%)
    """
    if not (0 <= proposta_pct_chirografari <= 100):
        raise ValueError("proposta_pct_chirografari deve essere compresa tra 0 e 100")
    if not (0 <= proposta_pct_privilegiati <= 100):
        raise ValueError("proposta_pct_privilegiati deve essere compresa tra 0 e 100")

    totale_debito = creditori_privilegiati + creditori_chirografari

    proposta_privilegiati = round(creditori_privilegiati * proposta_pct_privilegiati / 100, 2)
    proposta_chirografari_importo = round(creditori_chirografari * proposta_pct_chirografari / 100, 2)
    proposta_totale = round(proposta_privilegiati + proposta_chirografari_importo, 2)

    if tipo == "liquidatorio":
        soglia_minima = 20.0
        ammissibile = proposta_pct_chirografari >= soglia_minima
        nota_soglia = (
            f"Concordato liquidatorio: soddisfazione chirografari {proposta_pct_chirografari:.1f}% "
            f"{'≥' if ammissibile else '<'} soglia minima {soglia_minima}% (art. 84 co. 4 CCII)"
        )
    elif tipo == "continuita":
        soglia_minima = 0.0
        ammissibile = True
        nota_soglia = (
            "Concordato in continuità: nessuna soglia minima ex lege (art. 84 co. 2 CCII) — "
            "il piano deve tuttavia essere migliorativo rispetto alla liquidazione"
        )
    else:
        raise ValueError(f"tipo non valido: '{tipo}'. Usare 'continuita' o 'liquidatorio'")

    # Privilegiati: devono ricevere 100% salvo degradazione consensuale
    privilegiati_integrali = proposta_pct_privilegiati >= 100.0
    nota_privilegiati = (
        "Privilegiati: soddisfatti integralmente (conforme all'art. 84 CCII)"
        if privilegiati_integrali
        else f"Privilegiati: soddisfatti al {proposta_pct_privilegiati:.1f}% — necessaria degradazione consensuale ex art. 109 CCII"
    )

    return {
        "ammissibile": ammissibile,
        "tipo": tipo,
        "totale_debito": round(totale_debito, 2),
        "creditori_privilegiati": creditori_privilegiati,
        "creditori_chirografari": creditori_chirografari,
        "proposta_privilegiati_euro": proposta_privilegiati,
        "proposta_chirografari_euro": proposta_chirografari_importo,
        "proposta_totale": proposta_totale,
        "percentuale_chirografari": proposta_pct_chirografari,
        "percentuale_privilegiati": proposta_pct_privilegiati,
        "soglia_minima_pct": soglia_minima,
        "nota_soglia": nota_soglia,
        "nota_privilegiati": nota_privilegiati,
        "voto_requisito": (
            "Maggioranza dei crediti ammessi per ciascuna classe (art. 109 CCII). "
            "In mancanza di classi: maggioranza dei crediti chirografari."
        ),
        "riferimento_normativo": "Artt. 84-120 D.Lgs. 14/2019 (CCII) — Concordato preventivo",
    }


@mcp.tool(tags={"crisi_impresa"})
def compenso_occ(
    passivo: float,
    tipo: str = "ristrutturazione",
) -> dict:
    """Calcola il compenso dell'Organismo di Composizione della Crisi (OCC) ex D.M. 202/2014.

    Il compenso è calcolato a fasce progressive sul passivo dell'impresa, con importo
    minimo garantito. L'OCC assiste l'imprenditore nelle procedure di composizione
    negoziata e di ristrutturazione dei debiti ai sensi del D.Lgs. 14/2019.
    Vigenza: D.M. 202/2014 — Compensi OCC ex art. 15 co. 9 D.Lgs. 14/2019.
    Precisione: STIMATO — il compenso definitivo è determinato dal giudice delegato.
    Chaining: → concordato_preventivo() per la stima complessiva dei costi della procedura

    Args:
        passivo: Passivo totale dell'impresa in euro (es. 300000.0)
        tipo: Tipo di procedura: 'ristrutturazione' (aliquote ridotte, min €1.500) o 'liquidazione' (aliquote maggiori, min €2.000)
    """
    if passivo < 0:
        raise ValueError("Il passivo non può essere negativo")
    if tipo not in ("ristrutturazione", "liquidazione"):
        raise ValueError(f"tipo non valido: '{tipo}'. Usare 'ristrutturazione' o 'liquidazione'")

    # Progressive bracket rates by type
    fasce_config = {
        "ristrutturazione": [
            (100_000, 0.05),
            (400_000, 0.03),   # 100.001 - 500.000
            (float("inf"), 0.01),
        ],
        "liquidazione": [
            (100_000, 0.07),
            (400_000, 0.04),   # 100.001 - 500.000
            (float("inf"), 0.02),
        ],
    }
    minimi = {"ristrutturazione": 1_500.0, "liquidazione": 2_000.0}

    fasce = fasce_config[tipo]
    minimo = minimi[tipo]

    dettaglio_fasce = []
    compenso_calcolato = 0.0
    residuo = passivo

    soglie = [100_000, 500_000]
    precedente = 0

    for i, (ampiezza, aliquota) in enumerate(fasce):
        limite = soglie[i] if i < len(soglie) else float("inf")
        quota = min(residuo, limite - precedente) if limite != float("inf") else residuo
        if quota <= 0:
            break
        importo_fascia = round(quota * aliquota, 2)
        compenso_calcolato += importo_fascia
        dettaglio_fasce.append({
            "fascia": (
                f"fino a €{precedente + ampiezza:,.0f}" if i == 0
                else f"€{precedente + 1:,.0f} – €{limite:,.0f}" if limite != float("inf")
                else f"oltre €{precedente:,.0f}"
            ),
            "imponibile": round(quota, 2),
            "aliquota_pct": aliquota * 100,
            "importo": importo_fascia,
        })
        residuo -= quota
        precedente = limite
        if residuo <= 0:
            break

    compenso_calcolato = round(compenso_calcolato, 2)
    minimo_applicato = compenso_calcolato < minimo
    compenso_finale = minimo if minimo_applicato else compenso_calcolato

    return {
        "compenso": compenso_finale,
        "passivo": passivo,
        "tipo": tipo,
        "compenso_calcolato": compenso_calcolato,
        "minimo_applicato": minimo_applicato,
        "minimo_di_legge": minimo,
        "dettaglio_fasce": dettaglio_fasce,
        "riferimento_normativo": "D.M. 202/2014 — Compensi OCC ex art. 15 co. 9 D.Lgs. 14/2019",
    }
