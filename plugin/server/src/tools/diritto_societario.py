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
    convocazione: str = "prima",
    ricorso_mercato_capitale_rischio: bool = False,
) -> dict:
    """Verifica i quorum costitutivi e deliberativi per assemblee societarie.

    Applica i quorum legali supplettivi (lo statuto o l'atto costitutivo possono derogare):
    s.p.a. (artt. 2368-2369 c.c.), s.r.l. (art. 2479-bis co. 3 c.c.; per lo scioglimento
    art. 2487 co. 1 c.c.) e cooperative (art. 2538 co. 5 c.c., che rinvia all'atto costitutivo;
    in mancanza, per il rinvio dell'art. 2519 c.c., regole della s.p.a. chiusa).
    S.p.a. chiusa, prima convocazione: ordinaria con almeno la metà del capitale e maggioranza
    assoluta; straordinaria con il voto favorevole di più della metà del capitale sociale
    (art. 2368 co. 2, primo periodo). Seconda convocazione: ordinaria qualunque sia il capitale
    rappresentato; straordinaria con oltre un terzo del capitale e i 2/3 del rappresentato
    (art. 2369 co. 3), e per scioglimento anticipato, cambio di oggetto, trasformazione e
    proroga anche più di un terzo del capitale sociale favorevole (art. 2369 co. 5). I 2/3 del
    rappresentato in prima convocazione valgono solo per le società che fanno ricorso al mercato
    del capitale di rischio (art. 2368 co. 2, secondo periodo; ricorso_mercato_capitale_rischio=True),
    che di regola si riuniscono in unica convocazione (art. 2369 co. 1 e 7).
    S.r.l.: assemblea costituita con almeno la metà del capitale, maggioranza assoluta dei
    presenti; per le modifiche dell'atto costitutivo (art. 2479 co. 2 nn. 4 e 5) e per lo
    scioglimento anticipato (per rinvio, art. 2487 co. 1) voto favorevole di almeno la metà del
    capitale sociale. La s.r.l. non ha una seconda convocazione legale.
    Vigenza: codice civile (R.D. 262/1942) testo vigente al 2026-09-29, artt. 2368, 2369, 2479,
    2479-bis, 2484, 2487, 2519, 2538.
    Precisione: INDICATIVO (lo statuto può prevedere quorum diversi; per lo scioglimento della
        s.r.l. la maggioranza delle modifiche dell'atto costitutivo discende dal rinvio dell'art.
        2487 co. 1 e dalla dottrina, non da una norma sullo scioglimento; per le cooperative i
        quorum sono rimessi all'atto costitutivo)

    Args:
        tipo_societa: Tipo di società: 'spa', 'srl', 'cooperativa'
        tipo_delibera: Tipo di delibera: 'ordinaria', 'straordinaria', 'modifica_statuto', 'scioglimento'
        capitale_totale: Capitale sociale totale (o numero totale soci per cooperativa)
        capitale_presente: Capitale rappresentato in assemblea (o soci presenti per cooperativa); 0 se non calcolato
        voti_favorevoli: Capitale votante a favore (o soci favorevoli per cooperativa); 0 se non calcolato
        convocazione: 'prima', 'seconda' o 'unica' (solo s.p.a. con ricorso al mercato del capitale di rischio, art. 2369 co. 1)
        ricorso_mercato_capitale_rischio: True per la s.p.a. che fa ricorso al mercato del capitale di rischio (art. 2368 co. 2, secondo periodo); ignorato per s.r.l. e cooperative
    """
    if capitale_totale <= 0:
        raise ValueError("capitale_totale deve essere > 0")
    if capitale_presente < 0 or voti_favorevoli < 0:
        raise ValueError("capitale_presente e voti_favorevoli non possono essere negativi")
    if capitale_presente > capitale_totale:
        raise ValueError("capitale_presente non può superare capitale_totale")
    # voti_favorevoli vs capitale_presente: check only when capitale_presente > 0
    # (deliberations counted on the total capital can be evaluated without capitale_presente)
    if capitale_presente > 0 and voti_favorevoli > capitale_presente:
        raise ValueError("voti_favorevoli non possono superare capitale_presente")
    if capitale_presente == 0 and voti_favorevoli > capitale_totale:
        raise ValueError("voti_favorevoli non possono superare capitale_totale")

    tipo_societa = tipo_societa.lower()
    tipo_delibera = tipo_delibera.lower()
    convocazione = convocazione.lower()

    if tipo_societa not in ("spa", "srl", "cooperativa"):
        raise ValueError("tipo_societa deve essere 'spa', 'srl' o 'cooperativa'")
    if tipo_delibera not in ("ordinaria", "straordinaria", "modifica_statuto", "scioglimento"):
        raise ValueError("tipo_delibera deve essere 'ordinaria', 'straordinaria', 'modifica_statuto' o 'scioglimento'")
    if convocazione not in ("prima", "seconda", "unica"):
        raise ValueError("convocazione deve essere 'prima', 'seconda' o 'unica'")
    mercato = bool(ricorso_mercato_capitale_rischio) and tipo_societa == "spa"
    if convocazione == "unica" and not mercato:
        raise ValueError(
            "l'unica convocazione è prevista dall'art. 2369 co. 1 c.c. solo per le s.p.a. che fanno "
            "ricorso al mercato del capitale di rischio (ricorso_mercato_capitale_rischio=True)"
        )

    pct_presente = (capitale_presente / capitale_totale * 100) if capitale_presente else None
    pct_favorevoli_su_totale = (voti_favorevoli / capitale_totale * 100) if voti_favorevoli else None
    pct_favorevoli_su_presenti = (voti_favorevoli / capitale_presente * 100) if voti_favorevoli and capitale_presente else None

    has_presente = pct_presente is not None
    has_favorevoli = voti_favorevoli > 0
    has_fav_presenti = pct_favorevoli_su_presenti is not None

    # Elementary predicates (None = input missing)
    def _presente_almeno_meta():  # art. 2368 co. 1, 2479-bis co. 3: "almeno la metà"
        return None if not has_presente else capitale_presente * 2 >= capitale_totale

    def _presente_oltre_terzo():  # art. 2369 co. 3: "oltre un terzo"
        return None if not has_presente else capitale_presente * 3 > capitale_totale

    def _presente_almeno_quinto():  # art. 2369 co. 7: "almeno un quinto"
        return None if not has_presente else capitale_presente * 5 >= capitale_totale

    def _fav_maggioranza_assoluta_presenti():  # voti > metà del capitale rappresentato
        return None if not has_fav_presenti else voti_favorevoli * 2 > capitale_presente

    def _fav_due_terzi_presenti():  # "almeno i due terzi del capitale rappresentato"
        return None if not has_fav_presenti else voti_favorevoli * 3 >= capitale_presente * 2

    def _fav_piu_meta_totale():  # art. 2368 co. 2: "più della metà del capitale sociale"
        return None if not has_favorevoli else voti_favorevoli * 2 > capitale_totale

    def _fav_almeno_meta_totale():  # art. 2479-bis co. 3: "almeno la metà del capitale sociale"
        return None if not has_favorevoli else voti_favorevoli * 2 >= capitale_totale

    def _fav_oltre_terzo_totale():  # art. 2369 co. 5: "più di un terzo del capitale sociale"
        return None if not has_favorevoli else voti_favorevoli * 3 > capitale_totale

    def _and(*vals):
        if any(v is False for v in vals):
            return False
        if any(v is None for v in vals):
            return None
        return True

    # ---- SPA (and cooperative by art. 2519 rinvio, closed-company rules) ----
    if tipo_societa in ("spa", "cooperativa"):
        ordinaria = tipo_delibera == "ordinaria"
        art5 = tipo_delibera == "scioglimento"  # matters of art. 2369 co. 5 (scioglimento anticipato)
        if ordinaria:
            q1 = "Almeno la metà del capitale (art. 2368 co. 1 c.c.)"
            q2 = "Nessun quorum costitutivo: qualunque sia il capitale rappresentato (art. 2369 co. 3 c.c.)"
            qu = "Nessun quorum costitutivo: qualunque sia il capitale rappresentato (art. 2369 co. 1 e 3 c.c.)"
            d_txt = "Maggioranza assoluta del capitale rappresentato (art. 2368 co. 1 c.c.)"
            if convocazione == "prima":
                cost, delib = _presente_almeno_meta(), _fav_maggioranza_assoluta_presenti()
            else:
                cost, delib = True, _fav_maggioranza_assoluta_presenti()
            nota = ("Ordinaria: prima convocazione con almeno la metà del capitale; in seconda (o unica) "
                    "convocazione qualunque sia il capitale rappresentato; sempre maggioranza assoluta dei presenti.")
        elif mercato:
            q1 = "Almeno la metà del capitale (art. 2368 co. 2, secondo periodo c.c.)"
            q2 = "Oltre un terzo del capitale (art. 2369 co. 3 c.c.)"
            qu = "Almeno un quinto del capitale (art. 2369 co. 1 e 7 c.c.)"
            d_txt = "Almeno i 2/3 del capitale rappresentato in assemblea (art. 2368 co. 2, art. 2369 co. 3 e 7 c.c.)"
            if convocazione == "prima":
                cost = _presente_almeno_meta()
            elif convocazione == "seconda":
                cost = _presente_oltre_terzo()
            else:
                cost = _presente_almeno_quinto()
            delib = _fav_due_terzi_presenti()
            nota = ("S.p.a. con ricorso al mercato del capitale di rischio: 2/3 del capitale rappresentato in ogni "
                    "convocazione; costitutivo metà (prima), oltre un terzo (seconda), un quinto (unica o successive).")
        else:
            q1 = ("Nessun quorum costitutivo autonomo: il voto favorevole di più della metà del capitale sociale "
                  "ne presuppone la rappresentanza (art. 2368 co. 2, primo periodo c.c.)")
            q2 = "Oltre un terzo del capitale (art. 2369 co. 3 c.c.)"
            qu = "Non prevista per le società senza ricorso al mercato del capitale di rischio (art. 2369 co. 1 c.c.)"
            if convocazione == "prima":
                cost = _fav_piu_meta_totale()
                delib = _fav_piu_meta_totale()
                d_txt = "Voto favorevole di più della metà del capitale sociale (art. 2368 co. 2, primo periodo c.c.)"
            else:
                cost = _presente_oltre_terzo()
                if art5:
                    delib = _and(_fav_due_terzi_presenti(), _fav_oltre_terzo_totale())
                    d_txt = ("Almeno i 2/3 del capitale rappresentato e comunque più di un terzo del capitale "
                             "sociale (art. 2369 co. 3 e 5 c.c.)")
                else:
                    delib = _fav_due_terzi_presenti()
                    d_txt = "Almeno i 2/3 del capitale rappresentato in assemblea (art. 2369 co. 3 c.c.)"
            nota = ("S.p.a. senza ricorso al mercato del capitale di rischio: prima convocazione con più della metà del "
                    "capitale sociale favorevole; seconda convocazione con oltre un terzo del capitale presente e "
                    "2/3 del rappresentato" + (", e per lo scioglimento anticipato anche più di un terzo del capitale "
                    "sociale favorevole (art. 2369 co. 5)." if art5 else "."))
        rif = "Artt. 2368-2369 c.c." + (" (scioglimento anticipato: art. 2369 co. 5)" if art5 and not ordinaria else "")
        if tipo_societa == "cooperativa":
            q1 = ("Fissato dall'atto costitutivo (art. 2538 co. 5 c.c.); in mancanza, regole della s.p.a. per il "
                  "rinvio dell'art. 2519 c.c.: " + q1)
            nota = ("Cooperativa: le maggioranze sono determinate dall'atto costitutivo e calcolate sui voti spettanti ai soci "
                    "(art. 2538 co. 5 c.c.); ciascun socio cooperatore ha un voto. Il tool applica in via supplettiva le "
                    "regole della s.p.a. chiusa (art. 2519 co. 1 c.c.). " + nota)
            rif = "Artt. 2538, 2519, 2368-2369 c.c."

    # ---- SRL ----------------------------------------------------------------
    else:
        q1 = "Almeno la metà del capitale sociale (art. 2479-bis co. 3 c.c.)"
        q2 = "N/A: la s.r.l. non ha seconda convocazione per legge (l'atto costitutivo può prevederla)"
        qu = q2
        cost = _presente_almeno_meta()
        if tipo_delibera == "ordinaria":
            d_txt = "Maggioranza assoluta del capitale rappresentato (art. 2479-bis co. 3 c.c.)"
            delib = _fav_maggioranza_assoluta_presenti()
        elif tipo_delibera in ("straordinaria", "modifica_statuto"):
            d_txt = ("Voto favorevole dei soci che rappresentano almeno la metà del capitale sociale "
                     "(art. 2479-bis co. 3 e art. 2479 co. 2 nn. 4 e 5 c.c.)")
            delib = _fav_almeno_meta_totale()
        else:  # scioglimento
            d_txt = ("Almeno la metà del capitale sociale: maggioranza delle modifiche dell'atto costitutivo "
                     "(art. 2487 co. 1 e art. 2479-bis co. 3 c.c.); l'art. 2484 c.c. non fissa maggioranze")
            delib = _fav_almeno_meta_totale()
        nota = ("L'atto costitutivo della s.r.l. può derogare ai quorum di legge. Per lo scioglimento la maggioranza "
                "delle modifiche discende dal rinvio dell'art. 2487 co. 1 c.c. Non vi è seconda convocazione legale.")
        rif = "Artt. 2479, 2479-bis, 2484, 2487 c.c."

    result = {
        "tipo_societa": tipo_societa,
        "tipo_delibera": tipo_delibera,
        "convocazione": convocazione,
        "ricorso_mercato_capitale_rischio": mercato,
        "capitale_totale": capitale_totale,
        "capitale_presente": capitale_presente if capitale_presente else "non fornito",
        "voti_favorevoli": voti_favorevoli if voti_favorevoli else "non fornito",
        "percentuale_presente": f"{round(pct_presente, 2)}%" if pct_presente is not None else "n/a",
        "percentuale_favorevoli_su_presenti": f"{round(pct_favorevoli_su_presenti, 2)}%" if pct_favorevoli_su_presenti is not None else "n/a",
        "percentuale_favorevoli_su_totale": f"{round(pct_favorevoli_su_totale, 2)}%" if pct_favorevoli_su_totale is not None else "n/a",
        "quorum_costitutivo_prima_conv": q1,
        "quorum_costitutivo_seconda_conv": q2,
        "quorum_costitutivo_unica_conv": qu,
        "quorum_deliberativo": d_txt,
        "raggiunto_costitutivo": bool(cost),
        "raggiunto_deliberativo": bool(delib),
        "delibera_valida": bool(cost) and bool(delib),
        "note": nota,
        "riferimento_normativo": rif,
    }
    return result


@mcp.tool(tags={"societario"})
def soglie_organo_controllo_srl(
    ricavi: float,
    attivo: float,
    dipendenti: int,
    ricavi_precedente: float | None = None,
    attivo_precedente: float | None = None,
    dipendenti_precedente: int | None = None,
    bilancio_consolidato: bool = False,
    controlla_societa_revisione: bool = False,
) -> dict:
    """Verifica se una SRL è obbligata a nominare un organo di controllo o un revisore (art. 2477 c.c.).

    Applica l'art. 2477 co. 2 c.c.: la nomina è obbligatoria se la società a) è tenuta alla redazione
    del bilancio consolidato; b) controlla una società obbligata alla revisione legale; c) ha superato
    per DUE esercizi consecutivi almeno uno dei limiti: attivo 4 milioni, ricavi 4 milioni, 20 dipendenti
    medi (superamento stretto). Con i dati di un solo esercizio l'obbligo ex lett. c) non può essere
    accertato: `obbligo_nomina` è None e `limite_superato_ultimo_esercizio` segnala il superamento. Per
    l'accertamento passare anche i dati dell'esercizio precedente. L'obbligo ex lett. c) cessa solo quando
    per tre esercizi consecutivi non è superato alcun limite (co. 3); l'assemblea che approva il bilancio
    con i limiti superati nomina entro trenta giorni (co. 5).
    Usare per capire se è necessario nominare sindaco unico, collegio sindacale o revisore legale.
    Vigenza: art. 2477 co. 2-3 e 5 c.c., limiti 4 milioni / 4 milioni / 20 unità come sostituiti dall'art.
    2-bis co. 2 D.L. 32/2019 conv. L. 55/2019 (l'art. 379 D.Lgs. 14/2019 fissava 2 milioni / 2 milioni / 10
    unità), testo vigente al 2026-09-29.
    Precisione: ESATTO sui limiti di legge vigenti; la lett. c) richiede i dati di due esercizi consecutivi
        (con limiti diversi superati nei due esercizi l'esito è non determinabile, questione interpretativa).

    Args:
        ricavi: Ricavi delle vendite e delle prestazioni dell'ultimo esercizio (€)
        attivo: Totale attivo dello stato patrimoniale dell'ultimo esercizio (€)
        dipendenti: Numero medio di dipendenti occupati nell'ultimo esercizio
        ricavi_precedente: Ricavi dell'esercizio precedente (€); da passare insieme ad attivo_precedente e dipendenti_precedente
        attivo_precedente: Totale attivo dell'esercizio precedente (€)
        dipendenti_precedente: Numero medio di dipendenti dell'esercizio precedente
        bilancio_consolidato: True se la società è tenuta alla redazione del bilancio consolidato (art. 2477 co. 2 lett. a)
        controlla_societa_revisione: True se controlla una società obbligata alla revisione legale dei conti (lett. b)
    """
    if ricavi < 0 or attivo < 0 or dipendenti < 0:
        raise ValueError("ricavi, attivo e dipendenti non possono essere negativi")
    precedenti = (ricavi_precedente, attivo_precedente, dipendenti_precedente)
    if any(v is not None for v in precedenti) and any(v is None for v in precedenti):
        raise ValueError(
            "ricavi_precedente, attivo_precedente e dipendenti_precedente vanno indicati tutti insieme"
        )
    if any(v is not None and v < 0 for v in precedenti):
        raise ValueError("i dati dell'esercizio precedente non possono essere negativi")

    SOGLIA_RICAVI = 4_000_000.0
    SOGLIA_ATTIVO = 4_000_000.0
    SOGLIA_DIPENDENTI = 20

    def _superati(r: float, a: float, d: float) -> list[str]:
        out = []
        if r > SOGLIA_RICAVI:
            out.append("ricavi")
        if a > SOGLIA_ATTIVO:
            out.append("attivo")
        if d > SOGLIA_DIPENDENTI:
            out.append("dipendenti")
        return out

    limiti_superati = _superati(ricavi, attivo, dipendenti)
    dettaglio = [
        {"parametro": "ricavi", "valore": ricavi, "soglia": SOGLIA_RICAVI, "superato": ricavi > SOGLIA_RICAVI},
        {"parametro": "attivo", "valore": attivo, "soglia": SOGLIA_ATTIVO, "superato": attivo > SOGLIA_ATTIVO},
        {"parametro": "dipendenti", "valore": dipendenti, "soglia": SOGLIA_DIPENDENTI,
         "superato": dipendenti > SOGLIA_DIPENDENTI},
    ]

    obbligo_a_b = bool(bilancio_consolidato) or bool(controlla_societa_revisione)
    biennio = all(v is not None for v in precedenti)
    limiti_precedente: list[str] | None = None
    lett_c: bool | None
    nota_c: str
    if biennio:
        limiti_precedente = _superati(*precedenti)  # type: ignore[arg-type]
        stessi = [x for x in limiti_superati if x in limiti_precedente]
        if stessi:
            lett_c = True
            nota_c = ("Lett. c): almeno un limite (" + ", ".join(stessi) + ") superato per due esercizi consecutivi.")
        elif limiti_superati and limiti_precedente:
            lett_c = None
            nota_c = ("Lett. c): nei due esercizi sono superati limiti diversi; se la lett. c) richieda il superamento "
                      "dello stesso limite è questione interpretativa: verificare.")
        else:
            lett_c = False
            nota_c = "Lett. c): nei due esercizi non c'è alcun limite superato per due esercizi consecutivi."
    elif limiti_superati:
        lett_c = None
        nota_c = ("Lett. c): limite superato nell'ultimo esercizio; l'obbligo sorge solo se il superamento si ripete "
                  "per due esercizi consecutivi: indicare i dati dell'esercizio precedente.")
    else:
        lett_c = False
        nota_c = "Lett. c): nessun limite superato nell'esercizio fornito."

    if obbligo_a_b or lett_c is True:
        obbligo: bool | None = True
    elif lett_c is None:
        obbligo = None
    else:
        obbligo = False

    note = nota_c
    if obbligo_a_b:
        note += " Lett. a) o b): la nomina è obbligatoria a prescindere dai limiti."
    else:
        note += (" Restano da escludere le lett. a) (bilancio consolidato) e b) (controllo di società soggetta a "
                 "revisione legale), che impongono la nomina a prescindere dai limiti.")
    note += (" Un obbligo già sorto ex lett. c) cessa solo quando per tre esercizi consecutivi non è superato alcun "
             "limite (co. 3); l'assemblea che approva il bilancio con i limiti superati nomina entro trenta giorni "
             "(co. 5), altrimenti provvede il tribunale.")

    return {
        "obbligo_nomina": obbligo,
        "obbligo_lettere_a_b": obbligo_a_b,
        "limite_superato_ultimo_esercizio": bool(limiti_superati),
        "limiti_superati": limiti_superati,
        "numero_limiti_superati": len(limiti_superati),
        "limiti_superati_esercizio_precedente": limiti_precedente,
        "dettaglio": dettaglio,
        "soglie": {
            "ricavi_euro": SOGLIA_RICAVI,
            "attivo_euro": SOGLIA_ATTIVO,
            "dipendenti": SOGLIA_DIPENDENTI,
        },
        "note": note,
        "riferimento_normativo": (
            "Art. 2477 co. 2 lett. a), b), c), co. 3 e 5 c.c.; limiti 4 mln / 4 mln / 20 unità: art. 2-bis co. 2 "
            "D.L. 32/2019 conv. L. 55/2019 (art. 379 D.Lgs. 14/2019: 2 mln / 2 mln / 10 unità, sostituiti)"
        ),
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
    Il verbale di approvazione non ha un termine proprio: si deposita insieme al bilancio entro 30 giorni
    dall'approvazione (art. 2435 co. 1 c.c.; per le s.r.l. art. 2478-bis co. 2). Il bilancio va comunicato
    a sindaci e revisore almeno 30 giorni prima dell'assemblea (art. 2429 co. 1). Le date sono termini
    di calendario, senza sospensione feriale; il tool segnala se cadono di sabato o domenica.
    Vigenza: artt. 2364 co. 2, 2366, 2429, 2435 co. 1, 2478-bis co. 2, 2479-bis co. 1 c.c., testo vigente
    al 2026-09-29.
    Precisione: ESATTO sui termini di legge; verificare eventuali proroghe emergenziali.

    Args:
        data_chiusura_esercizio: Data di chiusura dell'esercizio (formato YYYY-MM-DD, es. '2024-12-31')
        bilancio_differito: True se lo statuto prevede il maggior termine e ricorrono le condizioni dell'art. 2364 co. 2 c.c. (società tenute al bilancio consolidato o particolari esigenze relative alla struttura e all'oggetto; gli amministratori motivano la dilazione nella relazione sulla gestione): termine da 120 a 180 giorni
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

    # Comunicazione del bilancio a sindaci e revisore: almeno 30 giorni prima dell'assemblea (art. 2429 co. 1)
    dt_comunicazione_controllo = _add_days(dt_approvazione, -30)

    scadenze = {
            "termine_approvazione_bilancio": {
                "data": dt_approvazione.isoformat(),
                "giorni_dalla_chiusura": giorni_approvazione,
                "nota": f"{'180 giorni — bilancio differito' if bilancio_differito else '120 giorni — termine ordinario'} (art. 2364 c.c.)",
            },
            "convocazione_assemblea_spa": {
                "data": dt_convocazione_spa.isoformat(),
                "nota": "Data ultima utile per inviare la convocazione ai soci SPA assumendo l'assemblea all'ultimo giorno utile di approvazione — 15 giorni prima (art. 2366 c.c.). Se l'assemblea è anticipata, ricalcolare 15 giorni prima della data effettiva.",
            },
            "convocazione_assemblea_srl": {
                "data": dt_convocazione_srl.isoformat(),
                "nota": "Data ultima utile per inviare la convocazione ai soci SRL assumendo l'assemblea all'ultimo giorno utile di approvazione — 8 giorni prima (art. 2479-bis c.c.). Se l'assemblea è anticipata, ricalcolare 8 giorni prima della data effettiva.",
            },
            "deposito_bilancio_sede_sociale": {
                "data": dt_deposito_sede.isoformat(),
                "nota": "Data ultima utile per il deposito di bilancio e relazioni in sede assumendo l'assemblea all'ultimo giorno utile di approvazione — 15 giorni prima (art. 2429 c.c.). Se l'assemblea è anticipata, ricalcolare 15 giorni prima della data effettiva.",
            },
            "deposito_cciaa": {
                "data": dt_deposito_cciaa.isoformat(),
                "giorni_dall_approvazione": 30,
                "nota": "Deposito bilancio approvato al Registro Imprese — 30 giorni dall'approvazione (art. 2435 c.c.)",
            },
            "comunicazione_bilancio_organo_controllo": {
                "data": dt_comunicazione_controllo.isoformat(),
                "nota": "Data ultima utile per comunicare il bilancio, con la relazione, al collegio sindacale e al revisore legale, assumendo l'assemblea all'ultimo giorno utile — almeno 30 giorni prima dell'assemblea (art. 2429 co. 1 c.c.); se l'assemblea è anticipata, ricalcolare 30 giorni prima della data effettiva.",
            },
            "iscrizione_verbale_assemblea": {
                "data": dt_iscrizione_verbale.isoformat(),
                "nota": "Il verbale di approvazione non ha un termine autonomo: si deposita al Registro Imprese insieme al bilancio, a cura degli amministratori, entro 30 giorni dall'approvazione (art. 2435 co. 1 c.c.; per le s.r.l. art. 2478-bis co. 2). Stessa data del deposito del bilancio.",
            },
    }
    giorni = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
    for v in scadenze.values():
        v["giorno_settimana"] = giorni[date.fromisoformat(v["data"]).weekday()]

    return {
        "data_chiusura_esercizio": data_chiusura_esercizio,
        "bilancio_differito": bilancio_differito,
        "scadenze": scadenze,
        "avvertenze": [
            "Le s.p.a. non quotate depositano entro gli stessi 30 giorni anche l'elenco soci (art. 2435 co. 2 c.c.).",
            "Termini di calendario senza sospensione feriale; il dies a quo (chiusura dell'esercizio o approvazione) non si conta.",
        ] + [
            f"{voce}: {v['data']} cade di {v['giorno_settimana']}; il tool non sposta il termine."
            for voce, v in scadenze.items() if v["giorno_settimana"] in ("sabato", "domenica")
        ],
        "riferimento_normativo": "Artt. 2364, 2366, 2429, 2435, 2478-bis, 2479-bis c.c.",
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
            {"voce": "Diritti di segreteria", "min": 0.0, "max": 0.0, "note": "ESENTI per SRLS (art. 3 c. 3 D.L. 1/2012: iscrizione esente da bollo e diritti di segreteria)"},
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
        note_extra = "Capitale minimo €50.000 (art. 2327 c.c.); almeno il 25% dei conferimenti in denaro va versato all'atto della costituzione (art. 2342 co. 2 c.c.)."

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
        "totale_stimato_formato": f"€{f'{totale_min:,.2f}'.replace(',', ' ').replace('.', ',').replace(' ', '.')} – €{f'{totale_max:,.2f}'.replace(',', ' ').replace('.', ',').replace(' ', '.')}",
        "capitale_minimo": capitale_minimo,
        "capitale_consigliato": capitale_consigliato,
        "note": note_extra,
        "avvertenza": "INDICATIVO — i costi notarili variano per zona geografica e complessità dell'operazione. Richiedere preventivo al notaio.",
        "riferimento_normativo": rif,
    }
    return result
