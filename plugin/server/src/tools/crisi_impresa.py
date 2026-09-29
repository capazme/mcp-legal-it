"""Strumenti per la crisi d'impresa e l'insolvenza: indicatori di crisi (art. 3 CCII D.Lgs. 14/2019),
composizione negoziata (artt. 12-25-undecies CCII), concordato preventivo (artt. 84-120 CCII),
compenso OCC (D.M. 202/2014)."""

from src.server import mcp

def _it(valore: float, decimali: int = 2) -> str:
    """Italian number format (thousands with a dot, decimals with a comma): 15000.5 -> '15.000,50'."""
    testo = f"{valore:,.{decimali}f}"
    return testo.replace(",", "\0").replace(".", ",").replace("\0", ".")


# Art. 25-novies co. 1 lett. d) CCII: AdER threshold by legal form of the debtor (euro, "superiori a").
_SOGLIE_ADER = {
    "impresa_individuale": 100_000,
    "societa_di_persone": 200_000,
    "altra_societa": 500_000,
}


@mcp.tool(tags={"crisi_impresa"})
def test_crisi_impresa(
    dscr: float | None = None,
    giorni_ritardo_inps: int = 0,
    giorni_ritardo_ade: int = 0,
    esposizioni_scadute_pct: float = 0.0,
    debiti_vs_attivo_pct: float = 0.0,
    retribuzioni_scadute_30gg: float | None = None,
    monte_retribuzioni_mensile: float | None = None,
    debiti_fornitori_scaduti_90gg: float | None = None,
    debiti_fornitori_non_scaduti: float | None = None,
    debito_inps: float | None = None,
    contributi_inps_anno_precedente: float | None = None,
    impresa_con_lavoratori: bool = True,
    giorni_ritardo_inail: int = 0,
    debito_inail: float | None = None,
    debito_iva_ade: float | None = None,
    volume_affari_anno_precedente: float | None = None,
    debito_ader: float | None = None,
    giorni_ritardo_ader: int = 0,
    forma_giuridica: str | None = None,
) -> dict:
    """Rileva i segnali di crisi dell'art. 3 co. 4 CCII (D.Lgs. 14/2019) e alcuni indici di prassi.

    I segnali normativi sono quattro: (a) debiti per retribuzioni scaduti da almeno 30 giorni per oltre
    la metà del monte retribuzioni mensile; (b) debiti verso fornitori scaduti da almeno 90 giorni
    superiori ai debiti non scaduti; (c) esposizioni bancarie scadute (o sconfinate) da oltre 60 giorni
    pari ad ALMENO il 5% del totale; (d) le esposizioni verso i creditori pubblici qualificati
    dell'art. 25-novies co. 1: INPS (oltre 90 giorni e oltre il 30% dei contributi dell'anno precedente
    e 15.000 euro, oppure 5.000 euro per le imprese senza lavoratori), INAIL (oltre 90 giorni e oltre
    5.000 euro), Agenzia delle entrate (debito IVA oltre 5.000 euro e non inferiore al 10% del volume
    d'affari, comunque oltre 20.000 euro; nessuna soglia a giorni), Agenzia delle entrate-Riscossione
    (carichi scaduti da oltre 90 giorni oltre 100.000 euro per le imprese individuali, 200.000 per le
    società di persone, 500.000 per le altre società). Per i creditori pubblici contano gli importi, non i
    soli giorni: se un dato necessario manca il segnale non viene attivato ma è elencato tra i
    `segnali_non_determinabili`. I segnali "agevolano la previsione" della crisi (art. 3 co. 3): non ne
    provano l'esistenza. Il DSCR a 12 mesi (art. 3 co. 3 lett. b: sostenibilità dei debiti almeno per i
    dodici mesi successivi), il rapporto debiti/attivo > 80% e i livelli di severità sono criteri di
    PRASSI, non previsti dal testo vigente, e sono etichettati come tali.
    Vigenza: Art. 3 co. 3-4 e art. 25-novies co. 1 D.Lgs. 14/2019 (CCII) come sostituiti dal D.Lgs. 83/2022; testo vigente al 2026-09-29.
    Precisione: INDICATIVO — i segnali normativi sono applicati alla lettera, ma dati e orizzonte dipendono dalle scritture; DSCR, debiti/attivo e severità sono prassi.
    Chaining: → composizione_negoziata() per verificare l'accesso allo strumento di risanamento

    Args:
        dscr: (prassi) Debt Service Coverage Ratio prospettico a 12 mesi (< 1.0 = flussi insufficienti); facoltativo
        giorni_ritardo_inps: Giorni di ritardo nel versamento dei contributi INPS (segnale solo se > 90 E con gli importi di debito_inps)
        giorni_ritardo_ade: DEPRECATO e ignorato: l'art. 25-novies co. 1 lett. c) non prevede soglie a giorni per l'Agenzia delle entrate (usare debito_iva_ade)
        esposizioni_scadute_pct: Percentuale (0-100) delle esposizioni verso banche e intermediari SCADUTE DA PIÙ DI 60 GIORNI (o sconfinate da almeno 60) sul totale delle esposizioni (segnale se >= 5.0)
        debiti_vs_attivo_pct: (prassi) Rapporto debiti totali / attivo totale in percentuale (> 80% = indice di prassi)
        retribuzioni_scadute_30gg: Euro di debiti per retribuzioni scaduti da almeno 30 giorni (lett. a)
        monte_retribuzioni_mensile: Euro dell'ammontare complessivo mensile delle retribuzioni (lett. a)
        debiti_fornitori_scaduti_90gg: Euro di debiti verso fornitori scaduti da almeno 90 giorni (lett. b)
        debiti_fornitori_non_scaduti: Euro di debiti verso fornitori non scaduti (lett. b)
        debito_inps: Euro di contributi previdenziali scaduti e non versati (art. 25-novies co. 1 lett. a)
        contributi_inps_anno_precedente: Euro di contributi dovuti all'INPS nell'anno precedente (per il 30%, imprese con lavoratori)
        impresa_con_lavoratori: True se l'impresa ha lavoratori subordinati o parasubordinati (soglia 15.000 e 30%); False (soglia 5.000)
        giorni_ritardo_inail: Giorni di ritardo nel pagamento dei premi INAIL (segnale solo se > 90 E debito_inail > 5.000)
        debito_inail: Euro di premi INAIL scaduti e non versati (lett. b)
        debito_iva_ade: Euro di debito IVA scaduto e non versato risultante dalle liquidazioni periodiche (lett. c)
        volume_affari_anno_precedente: Euro di volume d'affari della dichiarazione dell'anno d'imposta precedente (per il 10%)
        debito_ader: Euro di crediti affidati all'Agenzia delle entrate-Riscossione, autodichiarati o definitivamente accertati (lett. d)
        giorni_ritardo_ader: Giorni di scaduto dei carichi affidati all'AdER (segnale solo se > 90)
        forma_giuridica: 'impresa_individuale' (soglia 100.000), 'societa_di_persone' (200.000) o 'altra_societa' (500.000), per l'AdER
    """
    if dscr is not None and dscr < 0:
        raise ValueError("dscr non può essere negativo")
    for nome, valore in (
        ("giorni_ritardo_inps", giorni_ritardo_inps),
        ("giorni_ritardo_ade", giorni_ritardo_ade),
        ("giorni_ritardo_inail", giorni_ritardo_inail),
        ("giorni_ritardo_ader", giorni_ritardo_ader),
    ):
        if valore < 0:
            raise ValueError(f"{nome} non può essere negativo")
    if not (0 <= esposizioni_scadute_pct <= 100):
        raise ValueError("esposizioni_scadute_pct deve essere compresa tra 0 e 100")
    if debiti_vs_attivo_pct < 0:
        raise ValueError("debiti_vs_attivo_pct non può essere negativo")
    for nome, valore in (
        ("retribuzioni_scadute_30gg", retribuzioni_scadute_30gg),
        ("monte_retribuzioni_mensile", monte_retribuzioni_mensile),
        ("debiti_fornitori_scaduti_90gg", debiti_fornitori_scaduti_90gg),
        ("debiti_fornitori_non_scaduti", debiti_fornitori_non_scaduti),
        ("debito_inps", debito_inps),
        ("contributi_inps_anno_precedente", contributi_inps_anno_precedente),
        ("debito_inail", debito_inail),
        ("debito_iva_ade", debito_iva_ade),
        ("volume_affari_anno_precedente", volume_affari_anno_precedente),
        ("debito_ader", debito_ader),
    ):
        if valore is not None and valore < 0:
            raise ValueError(f"{nome} non può essere negativo")
    if forma_giuridica is not None and forma_giuridica not in _SOGLIE_ADER:
        raise ValueError(
            f"forma_giuridica non valida: '{forma_giuridica}'. Usare 'impresa_individuale', "
            "'societa_di_persone' o 'altra_societa'"
        )

    segnali: list[str] = []  # art. 3 co. 4 CCII, verified on the figures given
    non_determinabili: list[str] = []  # the norm needs a figure that was not supplied
    avvertenze: list[str] = []

    # Art. 3 co. 4 lett. a): retribuzioni scadute da almeno 30 giorni, oltre la metà del monte mensile.
    if retribuzioni_scadute_30gg:
        if not monte_retribuzioni_mensile:
            non_determinabili.append(
                "Art. 3 co. 4 lett. a) CCII: retribuzioni scadute da almeno 30 giorni indicate, ma manca "
                "monte_retribuzioni_mensile (il segnale richiede l'importo oltre la metà del monte mensile)"
            )
        elif retribuzioni_scadute_30gg > monte_retribuzioni_mensile / 2:
            segnali.append(
                f"Art. 3 co. 4 lett. a) CCII: retribuzioni scadute da almeno 30 giorni "
                f"{_it(retribuzioni_scadute_30gg)} euro > metà del monte mensile "
                f"({_it(monte_retribuzioni_mensile / 2)} euro)"
            )

    # Art. 3 co. 4 lett. b): fornitori scaduti da almeno 90 giorni, superiori ai debiti non scaduti.
    if debiti_fornitori_scaduti_90gg:
        if debiti_fornitori_non_scaduti is None:
            non_determinabili.append(
                "Art. 3 co. 4 lett. b) CCII: debiti verso fornitori scaduti da almeno 90 giorni indicati, ma "
                "manca debiti_fornitori_non_scaduti (il segnale richiede il confronto con i debiti non scaduti)"
            )
        elif debiti_fornitori_scaduti_90gg > debiti_fornitori_non_scaduti:
            segnali.append(
                f"Art. 3 co. 4 lett. b) CCII: debiti verso fornitori scaduti da almeno 90 giorni "
                f"{_it(debiti_fornitori_scaduti_90gg)} euro > debiti non scaduti "
                f"{_it(debiti_fornitori_non_scaduti)} euro"
            )

    # Art. 3 co. 4 lett. c): esposizioni bancarie scadute da oltre 60 giorni, ALMENO il 5% del totale.
    if esposizioni_scadute_pct >= 5.0:
        segnali.append(
            f"Art. 3 co. 4 lett. c) CCII: esposizioni bancarie scadute da oltre 60 giorni "
            f"{esposizioni_scadute_pct:.2f}% >= 5% del totale delle esposizioni"
        )

    # Art. 3 co. 4 lett. d) with art. 25-novies co. 1: public creditors, days AND amounts.
    # INPS (lett. a): oltre 90 giorni e importo > 30% dei contributi dell'anno precedente e 15.000 euro
    # (imprese con lavoratori), oppure > 5.000 euro (imprese senza lavoratori).
    if giorni_ritardo_inps > 90:
        if debito_inps is None:
            non_determinabili.append(
                f"Art. 25-novies co. 1 lett. a) CCII: ritardo INPS di {giorni_ritardo_inps} giorni (> 90), ma "
                "il segnale richiede anche l'importo: indicare debito_inps"
            )
        elif impresa_con_lavoratori:
            if debito_inps <= 15_000:
                pass  # cannot exceed 15.000 euro: no signal
            elif contributi_inps_anno_precedente is None:
                non_determinabili.append(
                    f"Art. 25-novies co. 1 lett. a) n. 1) CCII: ritardo INPS di {giorni_ritardo_inps} giorni "
                    f"e debito di {_it(debito_inps)} euro (> 15.000), ma manca contributi_inps_anno_precedente "
                    "per il confronto con il 30% dei contributi dovuti nell'anno precedente"
                )
            elif debito_inps > 0.30 * contributi_inps_anno_precedente:
                segnali.append(
                    f"Art. 25-novies co. 1 lett. a) n. 1) CCII: ritardo INPS {giorni_ritardo_inps} giorni > 90, "
                    f"debito {_it(debito_inps)} euro > 30% dei contributi dell'anno precedente "
                    f"({_it(0.30 * contributi_inps_anno_precedente)} euro) e > 15.000 euro"
                )
        elif debito_inps > 5_000:
            segnali.append(
                f"Art. 25-novies co. 1 lett. a) n. 2) CCII: ritardo INPS {giorni_ritardo_inps} giorni > 90, "
                f"debito {_it(debito_inps)} euro > 5.000 euro (impresa senza lavoratori)"
            )

    # INAIL (lett. b): premi scaduti da oltre 90 giorni e non versati, superiori a 5.000 euro.
    if giorni_ritardo_inail > 90:
        if debito_inail is None:
            non_determinabili.append(
                f"Art. 25-novies co. 1 lett. b) CCII: ritardo INAIL di {giorni_ritardo_inail} giorni (> 90), ma "
                "il segnale richiede anche l'importo: indicare debito_inail"
            )
        elif debito_inail > 5_000:
            segnali.append(
                f"Art. 25-novies co. 1 lett. b) CCII: premi INAIL scaduti da oltre 90 giorni, "
                f"debito {_it(debito_inail)} euro > 5.000 euro"
            )

    # Agenzia delle entrate (lett. c): debito IVA > 5.000 e non inferiore al 10% del volume d'affari,
    # in ogni caso se > 20.000. Nessuna soglia a giorni.
    if giorni_ritardo_ade:
        avvertenze.append(
            "giorni_ritardo_ade ignorato: l'art. 25-novies co. 1 lett. c) CCII fissa per l'Agenzia delle "
            "entrate soglie d'importo (debito IVA), non di giorni; usare debito_iva_ade e "
            "volume_affari_anno_precedente"
        )
    if debito_iva_ade is not None:
        if debito_iva_ade > 20_000:
            segnali.append(
                f"Art. 25-novies co. 1 lett. c) CCII: debito IVA scaduto e non versato "
                f"{_it(debito_iva_ade)} euro > 20.000 euro (segnalazione in ogni caso)"
            )
        elif debito_iva_ade > 5_000:
            if volume_affari_anno_precedente is None:
                non_determinabili.append(
                    f"Art. 25-novies co. 1 lett. c) CCII: debito IVA di {_it(debito_iva_ade)} euro (> 5.000) "
                    "ma manca volume_affari_anno_precedente per il confronto con il 10% del volume d'affari"
                )
            elif debito_iva_ade >= 0.10 * volume_affari_anno_precedente:
                segnali.append(
                    f"Art. 25-novies co. 1 lett. c) CCII: debito IVA {_it(debito_iva_ade)} euro > 5.000 euro "
                    f"e >= 10% del volume d'affari ({_it(0.10 * volume_affari_anno_precedente)} euro)"
                )

    # Agenzia delle entrate-Riscossione (lett. d): carichi scaduti da oltre 90 giorni sopra soglia per forma.
    if debito_ader is not None and giorni_ritardo_ader > 90:
        if forma_giuridica is not None:
            soglia_ader = _SOGLIE_ADER[forma_giuridica]
            if debito_ader > soglia_ader:
                segnali.append(
                    f"Art. 25-novies co. 1 lett. d) CCII: carichi AdER scaduti da oltre 90 giorni, "
                    f"{_it(debito_ader)} euro > {_it(soglia_ader, 0)} euro ({forma_giuridica})"
                )
        elif debito_ader > min(_SOGLIE_ADER.values()):
            non_determinabili.append(
                f"Art. 25-novies co. 1 lett. d) CCII: carichi AdER di {_it(debito_ader)} euro scaduti da oltre "
                "90 giorni; la soglia dipende dalla forma giuridica (100.000 impresa individuale, 200.000 "
                "società di persone, 500.000 altre società): indicare forma_giuridica"
            )
    elif debito_ader is not None and giorni_ritardo_ader == 0 and debito_ader > min(_SOGLIE_ADER.values()):
        non_determinabili.append(
            "Art. 25-novies co. 1 lett. d) CCII: debito AdER indicato senza giorni di scaduto; il segnale "
            "richiede carichi scaduti da oltre 90 giorni (indicare giorni_ritardo_ader)"
        )

    # Criteri di PRASSI (not in the vigente text of art. 3 CCII).
    prassi: list[str] = []
    if dscr is not None and dscr < 1.0:
        prassi.append(
            f"[prassi] DSCR {dscr:.2f} < 1.0: flussi di cassa prospettici insufficienti a coprire il servizio "
            "del debito nei 12 mesi successivi (art. 3 co. 3 lett. b) CCII: orizzonte di dodici mesi)"
        )
    if debiti_vs_attivo_pct > 80.0:
        prassi.append(
            f"[prassi] Debiti/Attivo {debiti_vs_attivo_pct:.1f}% > 80%: eccessivo indebitamento rispetto al "
            "patrimonio (indice non previsto dal testo vigente dell'art. 3 CCII)"
        )

    indicatori_attivati = segnali + prassi
    n = len(indicatori_attivati)
    alert = n > 0

    # The severity ladder is a convention of this tool, not a rule of the CCII.
    if n >= 3:
        severita = "critico"
        raccomandazione = (
            "Situazione critica: valutare senza indugio la composizione negoziata (art. 12 CCII) o il "
            "concordato preventivo (art. 84 CCII); convocare l'organo amministrativo e coinvolgere advisor."
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
            "e verificare nuovamente gli indicatori a breve."
        )
    else:
        severita = "nessuno"
        raccomandazione = (
            "Nessun segnale di crisi rilevato sui dati forniti. Continuare il monitoraggio periodico "
            "ai sensi dell'art. 3 co. 3 CCII."
        )
        if non_determinabili:
            raccomandazione += " Alcuni segnali non sono determinabili per dati mancanti (vedi segnali_non_determinabili)."

    return {
        "alert": alert,
        "severita": severita,
        "severita_criterio": "prassi: la scala dei livelli non è prevista dal CCII",
        "indicatori_attivati": indicatori_attivati,
        "numero_indicatori": n,
        "segnali_art_3_co_4": segnali,
        "numero_segnali_normativi": len(segnali),
        "indicatori_di_prassi": prassi,
        "segnali_non_determinabili": non_determinabili,
        "avvertenze": avvertenze,
        "dscr": dscr,
        "raccomandazione": raccomandazione,
        "riferimento_normativo": (
            "Art. 3 D.Lgs. 14/2019 (CCII) — Adeguatezza delle misure e degli assetti (co. 3 lett. b, co. 4); "
            "art. 25-novies co. 1 (segnalazioni dei creditori pubblici qualificati)"
        ),
    }


@mcp.tool(tags={"crisi_impresa"})
def composizione_negoziata(
    fatturato: float,
    attivo: float,
    dipendenti: int,
    debito_totale: float,
    tipo_impresa: str = "commerciale",
    procedimento_regolazione_pendente: bool = False,
    rinuncia_domanda_ultimi_4_mesi: bool = False,
) -> dict:
    """Verifica la via d'accesso alla composizione negoziata della crisi e riepiloga effetti e limiti.

    La composizione negoziata (artt. 12-25-undecies CCII) è uno strumento stragiudiziale con cui
    l'imprenditore commerciale o agricolo, in crisi o in squilibrio che ne rende probabile la crisi o
    l'insolvenza, negozia con i creditori assistito da un esperto indipendente nominato dal segretario
    generale della CCIAA (art. 12 co. 1). Il tool stabilisce se l'impresa è "minore" (art. 2 co. 1 lett. d:
    attivo, ricavi e debiti non superiori a 300.000, 200.000 e 500.000 euro, congiuntamente): in tal caso
    l'accesso è quello dell'art. 25-quater (imprese sotto soglia), altrimenti l'ordinario art. 12 co. 1.
    Non decide la ragionevole perseguibilità del risanamento né lo squilibrio: sono condizioni dell'art. 12
    co. 1 da verificare con il test pratico e la lista di controllo della piattaforma (art. 13 co. 2).
    Segnala le cause ostative dell'art. 25-quinquies (domanda di accesso a uno strumento di regolazione
    pendente, o rinunciata nei quattro mesi precedenti).
    Vigenza: Artt. 2 co. 1 lett. d), 12, 17 co. 7, 18, 20, 22, 24, 25-quater e 25-quinquies D.Lgs. 14/2019 (CCII) come modificato dal D.Lgs. 83/2022 e dal D.Lgs. 136/2024; soglie dell'impresa minore aggiornabili ogni tre anni con decreto ministeriale (art. 348); testo vigente al 2026-09-29.
    Precisione: INDICATIVO — l'ammissibilità definitiva è valutata dall'esperto; i requisiti dell'impresa minore vanno verificati sui tre esercizi antecedenti.
    Chaining: → concordato_preventivo() se la composizione negoziata fallisce

    Args:
        fatturato: Ricavi annui in euro (requisito dell'impresa minore: non superiori a 200.000; es. 500000.0)
        attivo: Totale attivo patrimoniale in euro (requisito dell'impresa minore: non superiore a 300.000; es. 800000.0)
        dipendenti: Numero di dipendenti (informativo: l'art. 2 co. 1 lett. d) non li considera, non incide sull'accesso)
        debito_totale: Debito totale, anche non scaduto, in euro (requisito dell'impresa minore: non superiore a 500.000; es. 300000.0)
        tipo_impresa: 'commerciale' (default) o 'agricola' (accesso ex art. 12 co. 1, o ex art. 25-quater se impresa minore); 'sotto_soglia' se si vuole verificare l'accesso ex art. 25-quater (art. 2 co. 1 lett. d)
        procedimento_regolazione_pendente: True se pende una domanda di accesso a uno strumento di regolazione della crisi o dell'insolvenza (art. 25-quinquies co. 1: istanza non presentabile)
        rinuncia_domanda_ultimi_4_mesi: True se l'imprenditore ha rinunciato a tale domanda nei quattro mesi precedenti (art. 25-quinquies co. 1)
    """
    if any(v < 0 for v in [fatturato, attivo, debito_totale]):
        raise ValueError("I valori finanziari non possono essere negativi")
    if dipendenti < 0:
        raise ValueError("Il numero di dipendenti non può essere negativo")
    if tipo_impresa not in ("commerciale", "agricola", "sotto_soglia"):
        raise ValueError(f"tipo_impresa non valido: '{tipo_impresa}'. Usare 'commerciale', 'agricola' o 'sotto_soglia'")

    # Art. 2 co. 1 lett. d) CCII: the three requirements are joint, each "non superiore" to its limit.
    sotto_attivo = attivo <= 300_000
    sotto_ricavi = fatturato <= 200_000
    sotto_debiti = debito_totale <= 500_000
    impresa_minore = sotto_attivo and sotto_ricavi and sotto_debiti

    requisiti_soddisfatti: list[str] = []
    requisiti_mancanti: list[str] = []
    for ok, soddisfatto, mancante in (
        (
            sotto_attivo,
            f"Attivo non superiore a € 300.000 (attuale: € {_it(attivo)})",
            f"Attivo superiore a € 300.000 (attuale: € {_it(attivo)})",
        ),
        (
            sotto_ricavi,
            f"Ricavi non superiori a € 200.000 (attuali: € {_it(fatturato)})",
            f"Ricavi superiori a € 200.000 (attuali: € {_it(fatturato)})",
        ),
        (
            sotto_debiti,
            f"Debiti non superiori a € 500.000 (attuali: € {_it(debito_totale)})",
            f"Debiti superiori a € 500.000 (attuali: € {_it(debito_totale)})",
        ),
    ):
        (requisiti_soddisfatti if ok else requisiti_mancanti).append(soddisfatto if ok else mancante)

    # Access route: art. 25-quater for the impresa minore, art. 12 co. 1 otherwise.
    if impresa_minore:
        accesso = "Art. 25-quater co. 1 CCII (imprese sotto soglia)"
        requisiti_soddisfatti.append(
            "Impresa minore (art. 2 co. 1 lett. d CCII): accesso ex art. 25-quater co. 1 CCII; "
            "per quanto non previsto si applicano gli artt. 12 e seguenti (art. 25-quater co. 5)"
        )
    else:
        accesso = "Art. 12 co. 1 CCII (imprenditore commerciale e agricolo)"
        if tipo_impresa == "sotto_soglia":
            requisiti_soddisfatti.append(
                "Non è impresa minore: manca almeno uno dei tre requisiti congiunti dell'art. 2 co. 1 lett. d) "
                "CCII, quindi non si applica l'art. 25-quater; l'accesso resta quello ordinario ex art. 12 co. 1 CCII"
            )
        else:
            requisiti_soddisfatti.append(f"Impresa {tipo_impresa}: accesso ex art. 12 co. 1 CCII")

    # Art. 25-quinquies co. 1 CCII: bars to the request.
    ostacoli: list[str] = []
    if procedimento_regolazione_pendente:
        ostacoli.append(
            "Art. 25-quinquies co. 1 CCII: l'istanza non può essere presentata in pendenza di una domanda di "
            "accesso a uno strumento di regolazione della crisi o dell'insolvenza"
        )
    if rinuncia_domanda_ultimi_4_mesi:
        ostacoli.append(
            "Art. 25-quinquies co. 1 CCII: l'istanza non può essere presentata se l'imprenditore ha rinunciato "
            "a tale domanda nei quattro mesi precedenti"
        )
    ammissibile = not ostacoli

    condizioni_da_verificare = [
        "Art. 12 co. 1 CCII: squilibrio patrimoniale o economico-finanziario che rende probabile la crisi o "
        "l'insolvenza (o crisi/insolvenza ex art. 2 co. 1 lett. a, b) E risanamento ragionevolmente "
        "perseguibile: il tool non le accerta (test pratico e lista di controllo, art. 13 co. 2 CCII)",
        "Art. 2 co. 1 lett. d) CCII: i requisiti dell'impresa minore si misurano sui tre esercizi antecedenti "
        "l'istanza (o dall'inizio dell'attività se di durata inferiore); il tool usa un solo valore annuo",
    ]

    # Informative ratios only: the CCII fixes no debt/turnover threshold.
    rapporto_debito_fatturato = round(debito_totale / fatturato, 2) if fatturato > 0 else None
    rapporto_debito_attivo = round(debito_totale / attivo * 100, 1) if attivo > 0 else None
    euristica_debito_lt_2x = debito_totale < 2 * fatturato if fatturato > 0 else None

    indicatori = {
        "rapporto_debito_fatturato": rapporto_debito_fatturato,
        "rapporto_debito_attivo_pct": rapporto_debito_attivo,
        "euristica_di_prassi_debito_inferiore_a_2x_fatturato": euristica_debito_lt_2x,
        "nota_risanamento": (
            "La ragionevole perseguibilità del risanamento (art. 12 co. 1 CCII) non dipende dal rapporto "
            "debito/fatturato: si verifica con il test pratico e la lista di controllo della piattaforma "
            "telematica nazionale (art. 13 co. 2 CCII, decreto dirigenziale del Ministero della giustizia). "
            "I rapporti sono indicatori informativi; la soglia 2x è una euristica di prassi senza base nel CCII."
        ),
    }

    misure_protettive = [
        "Misure protettive del patrimonio, su richiesta dell'imprenditore: dalla pubblicazione dell'istanza i "
        "creditori interessati non possono acquisire prelazioni non concordate né iniziare o proseguire azioni "
        "esecutive e cautelari; esclusi i crediti dei lavoratori (art. 18 co. 1 e 3 CCII)",
        "Sospensione, su dichiarazione dell'imprenditore, degli obblighi e delle cause di scioglimento per "
        "riduzione o perdita del capitale (artt. 2446, 2447, 2482-bis, 2482-ter, 2484 n. 4 c.c.) fino alla "
        "conclusione delle trattative (art. 20 CCII)",
        "Finanziamenti autorizzati dal tribunale con riconoscimento della prededuzione (art. 22 co. 1 lett. a) CCII)",
    ]
    if impresa_minore:
        misure_protettive.append(
            "Revocatoria (art. 24 CCII): per le imprese sotto soglia l'art. 25-quater co. 5 richiama solo l'art. 24 "
            "co. 3 e 4 (atti soggetti a revocatoria se l'esperto ha iscritto il dissenso o il tribunale ha rigettato "
            "l'autorizzazione); non si applica l'esenzione dell'art. 24 co. 2"
        )
    else:
        misure_protettive.append(
            "Esenzione dalla revocatoria ex art. 166 co. 2 per atti, pagamenti e garanzie successivi "
            "all'accettazione dell'esperto e coerenti con le trattative (art. 24 co. 2 CCII), salvo dissenso "
            "dell'esperto o rigetto dell'autorizzazione (art. 24 co. 3)"
        )

    return {
        "ammissibile": ammissibile,
        "tipo_impresa": tipo_impresa,
        "impresa_minore": impresa_minore,
        "accesso": accesso,
        "requisiti_soddisfatti": requisiti_soddisfatti,
        "requisiti_mancanti": requisiti_mancanti,
        "ostacoli_art_25_quinquies": ostacoli,
        "condizioni_da_verificare": condizioni_da_verificare,
        "indicatori": indicatori,
        "durata_max": "180 giorni dall'accettazione della nomina, prorogabili per non oltre altri 180 giorni (art. 17 co. 7 CCII)",
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
            f"{'≥' if ammissibile else '<'} soglia minima {soglia_minima}% (art. 84 co. 4 CCII). "
            "ATTENZIONE: l'ammissibilità richiede ANCHE l'apporto di risorse esterne che incrementi "
            "di almeno il 10% il soddisfacimento dei chirografari rispetto alla liquidazione giudiziale "
            "(art. 84 co. 4 CCII) — condizione non verificabile da questo tool: l'esito 'ammissibile' "
            "è subordinato alla sussistenza di tale apporto esterno."
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
    Precisione: INDICATIVO (gli scaglioni inclusi sono una semplificazione: l'art. 16 DM 202/2014
        rinvia ai parametri del curatore con riduzioni; verificare sul decreto)
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
                f"fino a €{_it(limite, 0)}" if i == 0
                else f"€{_it(precedente + 1, 0)} – €{_it(limite, 0)}" if limite != float("inf")
                else f"oltre €{_it(precedente, 0)}"
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
