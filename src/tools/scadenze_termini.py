"""Sezione 3 — Scadenze e Termini: calcolo scadenze processuali, impugnazioni, famiglia, multe."""

import json
from datetime import date, timedelta
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "festivita.json") as f:
    _FESTIVITA_FISSE = json.load(f)["fisse"]


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _easter(year: int) -> date:
    """Gauss algorithm for Easter Sunday."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _is_holiday(d: date) -> bool:
    """Check if date is a weekend or Italian public holiday."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return True
    for f in _FESTIVITA_FISSE:
        if d.day == f["giorno"] and d.month == f["mese"]:
            return True
    pasqua = _easter(d.year)
    if d == pasqua or d == pasqua + timedelta(days=1):  # Lunedì dell'Angelo
        return True
    return False


def _slide_forward(d: date) -> tuple[date, bool]:
    """Art. 155 c.p.c.: slide to next business day if holiday."""
    original = d
    while _is_holiday(d):
        d += timedelta(days=1)
    return d, d != original


def _add_business_days(start: date, days: int) -> date:
    """Add N business days (excluding weekends and holidays)."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if not _is_holiday(current):
            added += 1
    return current


def _subtract_calendar_days_with_slide(d: date, days: int) -> tuple[date, bool]:
    """Subtract calendar days and slide forward if result is a holiday."""
    result = d - timedelta(days=days)
    return _slide_forward(result)


def _add_months(d: date, months: int) -> date:
    """Add N months to a date, clamping to end of month if needed."""
    import calendar
    year = d.year + (d.month + months - 1) // 12
    month = (d.month + months - 1) % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(d.day, max_day)
    return date(year, month, day)


@mcp.tool()
def scadenza_processuale(
    data_evento: str,
    giorni: int,
    tipo: str = "calendario",
) -> dict:
    """Calcolo scadenza processuale con proroga art. 155 c.p.c.

    Args:
        data_evento: Data da cui decorre il termine (YYYY-MM-DD) — dies a quo escluso
        giorni: Numero di giorni del termine
        tipo: 'calendario' (dies a quo escluso, art. 155 c.p.c.) o 'lavorativi'
    """
    dt_evento = _parse_date(data_evento)

    if tipo == "lavorativi":
        scadenza = _add_business_days(dt_evento, giorni)
        adjusted = False
    else:
        scadenza_raw = dt_evento + timedelta(days=giorni)
        scadenza, adjusted = _slide_forward(scadenza_raw)

    return {
        "data_evento": data_evento,
        "giorni": giorni,
        "tipo": tipo,
        "scadenza": scadenza.isoformat(),
        "prorogata_art_155": adjusted,
        "giorno_settimana": scadenza.strftime("%A"),
        "riferimento_normativo": "Art. 155 c.p.c. — se il termine scade in giorno festivo, è prorogato al primo giorno seguente non festivo",
    }


@mcp.tool()
def termini_processuali_civili(
    data_udienza: str,
    tipo_termine: str,
) -> dict:
    """Termini memorie ex art. 171-ter c.p.c. (rito post-Cartabia, D.Lgs. 149/2022).

    Args:
        data_udienza: Data dell'udienza di trattazione (YYYY-MM-DD)
        tipo_termine: Tipo di termine: 'memoria_I' (40gg prima), 'memoria_II' (20gg prima), 'memoria_III' (10gg prima), 'comparsa_conclusionale' (60gg dopo), 'replica' (20gg dopo conclusionale)
    """
    dt_udienza = _parse_date(data_udienza)

    termini_config = {
        "memoria_I": {
            "giorni": 40,
            "direzione": "prima",
            "descrizione": "Memoria art. 171-ter, co. 1, n. 1 — precisazione/modificazione domande, eccezioni, conclusioni",
        },
        "memoria_II": {
            "giorni": 20,
            "direzione": "prima",
            "descrizione": "Memoria art. 171-ter, co. 1, n. 2 — replica ed eccezioni nuove",
        },
        "memoria_III": {
            "giorni": 10,
            "direzione": "prima",
            "descrizione": "Memoria art. 171-ter, co. 1, n. 3 — indicazione prova contraria",
        },
        "comparsa_conclusionale": {
            "giorni": 60,
            "direzione": "dopo",
            "descrizione": "Comparsa conclusionale art. 190 c.p.c.",
        },
        "replica": {
            "giorni": 80,  # 60 + 20
            "direzione": "dopo",
            "descrizione": "Memoria di replica art. 190 c.p.c. (20gg dopo comparsa conclusionale)",
        },
    }

    if tipo_termine not in termini_config:
        return {
            "errore": f"tipo_termine non valido: {tipo_termine}",
            "valori_ammessi": list(termini_config.keys()),
        }

    config = termini_config[tipo_termine]

    if config["direzione"] == "prima":
        scadenza, adjusted = _subtract_calendar_days_with_slide(dt_udienza, config["giorni"])
    else:
        scadenza_raw = dt_udienza + timedelta(days=config["giorni"])
        scadenza, adjusted = _slide_forward(scadenza_raw)

    # Calculate all "prima" deadlines for context
    tutte_scadenze = {}
    for nome, cfg in termini_config.items():
        if cfg["direzione"] == "prima":
            d, _ = _subtract_calendar_days_with_slide(dt_udienza, cfg["giorni"])
            tutte_scadenze[nome] = d.isoformat()

    result = {
        "data_udienza": data_udienza,
        "tipo_termine": tipo_termine,
        "descrizione": config["descrizione"],
        "scadenza": scadenza.isoformat(),
        "prorogata_art_155": adjusted,
        "giorno_settimana": scadenza.strftime("%A"),
        "riferimento_normativo": "Art. 171-ter c.p.c. (D.Lgs. 149/2022 — Riforma Cartabia)",
    }

    if config["direzione"] == "prima":
        result["riepilogo_termini_memorie"] = tutte_scadenze

    return result


@mcp.tool()
def termini_separazione_divorzio(
    data_evento: str,
    tipo: str,
) -> dict:
    """Scadenze diritto di famiglia per separazione, divorzio e negoziazione assistita.

    Args:
        data_evento: Data dell'evento rilevante (YYYY-MM-DD) — es. omologa separazione, sentenza passata in giudicato
        tipo: 'separazione_consensuale' (6 mesi per divorzio), 'separazione_giudiziale' (12 mesi), 'negoziazione_assistita' (6 mesi), 'ricorso_modifica' (nessun termine)
    """
    dt_evento = _parse_date(data_evento)

    config = {
        "separazione_consensuale": {
            "mesi": 6,
            "descrizione": "Termine per presentare ricorso di divorzio dopo separazione consensuale",
            "normativa": "Art. 3, co. 2, lett. b), L. 898/1970 (mod. L. 55/2015)",
        },
        "separazione_giudiziale": {
            "mesi": 12,
            "descrizione": "Termine per presentare ricorso di divorzio dopo separazione giudiziale",
            "normativa": "Art. 3, co. 2, lett. b), L. 898/1970 (mod. L. 55/2015)",
        },
        "negoziazione_assistita": {
            "mesi": 6,
            "descrizione": "Termine per presentare ricorso di divorzio dopo negoziazione assistita",
            "normativa": "Art. 6 DL 132/2014 conv. L. 162/2014 — Art. 3 L. 898/1970",
        },
        "ricorso_modifica": {
            "mesi": 0,
            "descrizione": "Ricorso per modifica delle condizioni — nessun termine specifico, proponibile in qualsiasi momento al mutare delle circostanze",
            "normativa": "Art. 710 c.p.c. / Art. 9 L. 898/1970",
        },
    }

    if tipo not in config:
        return {
            "errore": f"tipo non valido: {tipo}",
            "valori_ammessi": list(config.keys()),
        }

    cfg = config[tipo]

    if cfg["mesi"] == 0:
        return {
            "data_evento": data_evento,
            "tipo": tipo,
            "descrizione": cfg["descrizione"],
            "scadenza": None,
            "nota": "Nessun termine: il ricorso è proponibile in qualsiasi momento",
            "riferimento_normativo": cfg["normativa"],
        }

    # Add months
    mesi = cfg["mesi"]
    year = dt_evento.year + (dt_evento.month + mesi - 1) // 12
    month = (dt_evento.month + mesi - 1) % 12 + 1
    # Handle end-of-month edge cases
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    day = min(dt_evento.day, max_day)
    scadenza_raw = date(year, month, day)
    scadenza, adjusted = _slide_forward(scadenza_raw)

    return {
        "data_evento": data_evento,
        "tipo": tipo,
        "descrizione": cfg["descrizione"],
        "mesi_termine": mesi,
        "scadenza": scadenza.isoformat(),
        "prorogata_art_155": adjusted,
        "giorno_settimana": scadenza.strftime("%A"),
        "riferimento_normativo": cfg["normativa"],
    }


@mcp.tool()
def scadenze_impugnazioni(
    data_pubblicazione: str,
    tipo_impugnazione: str,
    notificata: bool = False,
) -> dict:
    """Termini di impugnazione sentenze civili.

    Args:
        data_pubblicazione: Data pubblicazione/notifica sentenza (YYYY-MM-DD)
        tipo_impugnazione: 'appello_sentenza', 'cassazione', 'revocazione', 'opposizione_terzo', 'regolamento_competenza'
        notificata: True se la sentenza è stata notificata (termine breve), False per termine lungo
    """
    dt_pub = _parse_date(data_pubblicazione)

    config = {
        "appello_sentenza": {
            "breve": 30,
            "lungo_mesi": 6,
            "descrizione": "Appello sentenza di primo grado",
            "normativa": "Art. 325-327 c.p.c.",
        },
        "cassazione": {
            "breve": 60,
            "lungo_mesi": 6,
            "descrizione": "Ricorso per cassazione",
            "normativa": "Art. 325, co. 2 — Art. 327 c.p.c.",
        },
        "revocazione": {
            "breve": 30,
            "lungo_mesi": 6,
            "descrizione": "Revocazione ordinaria",
            "normativa": "Art. 325, co. 1 — Art. 327 c.p.c.",
        },
        "opposizione_terzo": {
            "breve": 30,
            "lungo_mesi": None,
            "descrizione": "Opposizione di terzo — nessun termine decadenziale ordinario",
            "normativa": "Art. 404 c.p.c.",
        },
        "regolamento_competenza": {
            "breve": 30,
            "lungo_mesi": 6,
            "descrizione": "Regolamento di competenza",
            "normativa": "Art. 43 c.p.c.",
        },
    }

    if tipo_impugnazione not in config:
        return {
            "errore": f"tipo_impugnazione non valido: {tipo_impugnazione}",
            "valori_ammessi": list(config.keys()),
        }

    cfg = config[tipo_impugnazione]

    if notificata:
        scadenza_raw = dt_pub + timedelta(days=cfg["breve"])
        scadenza, adjusted = _slide_forward(scadenza_raw)
        tipo_termine = "breve (da notifica)"
        giorni_termine = cfg["breve"]
    elif cfg["lungo_mesi"] is not None:
        import calendar
        mesi = cfg["lungo_mesi"]
        year = dt_pub.year + (dt_pub.month + mesi - 1) // 12
        month = (dt_pub.month + mesi - 1) % 12 + 1
        max_day = calendar.monthrange(year, month)[1]
        day = min(dt_pub.day, max_day)
        scadenza_raw = date(year, month, day)
        scadenza, adjusted = _slide_forward(scadenza_raw)
        tipo_termine = f"lungo ({mesi} mesi da pubblicazione)"
        giorni_termine = (scadenza_raw - dt_pub).days
    else:
        return {
            "data_pubblicazione": data_pubblicazione,
            "tipo_impugnazione": tipo_impugnazione,
            "descrizione": cfg["descrizione"],
            "notificata": notificata,
            "scadenza": None,
            "nota": "Nessun termine decadenziale per questo tipo di impugnazione",
            "riferimento_normativo": cfg["normativa"],
        }

    return {
        "data_pubblicazione": data_pubblicazione,
        "tipo_impugnazione": tipo_impugnazione,
        "descrizione": cfg["descrizione"],
        "notificata": notificata,
        "tipo_termine": tipo_termine,
        "giorni_termine": giorni_termine,
        "scadenza": scadenza.isoformat(),
        "prorogata_art_155": adjusted,
        "giorno_settimana": scadenza.strftime("%A"),
        "riferimento_normativo": cfg["normativa"],
    }


@mcp.tool()
def scadenze_multe(
    data_notifica: str,
    tipo_ricorso: str,
) -> dict:
    """Termini per ricorso contro contravvenzioni stradali (CdS).

    Args:
        data_notifica: Data di notifica del verbale (YYYY-MM-DD)
        tipo_ricorso: 'prefetto' (60gg), 'giudice_pace' (30gg), 'pagamento_ridotto' (60gg), 'pagamento_ridotto_5gg' (5gg sconto 30%)
    """
    dt_notifica = _parse_date(data_notifica)

    config = {
        "prefetto": {
            "giorni": 60,
            "descrizione": "Ricorso al Prefetto",
            "normativa": "Art. 203 D.Lgs. 285/1992 (Codice della Strada)",
        },
        "giudice_pace": {
            "giorni": 30,
            "descrizione": "Ricorso al Giudice di Pace",
            "normativa": "Art. 204-bis D.Lgs. 285/1992",
        },
        "pagamento_ridotto": {
            "giorni": 60,
            "descrizione": "Pagamento in misura ridotta (sanzione minima)",
            "normativa": "Art. 202 D.Lgs. 285/1992",
        },
        "pagamento_ridotto_5gg": {
            "giorni": 5,
            "descrizione": "Pagamento entro 5 giorni con sconto del 30%",
            "normativa": "Art. 202, co. 1, D.Lgs. 285/1992 (mod. L. 120/2010)",
        },
    }

    if tipo_ricorso not in config:
        return {
            "errore": f"tipo_ricorso non valido: {tipo_ricorso}",
            "valori_ammessi": list(config.keys()),
        }

    cfg = config[tipo_ricorso]
    scadenza_raw = dt_notifica + timedelta(days=cfg["giorni"])
    scadenza, adjusted = _slide_forward(scadenza_raw)

    result = {
        "data_notifica": data_notifica,
        "tipo_ricorso": tipo_ricorso,
        "descrizione": cfg["descrizione"],
        "giorni_termine": cfg["giorni"],
        "scadenza": scadenza.isoformat(),
        "prorogata_art_155": adjusted,
        "giorno_settimana": scadenza.strftime("%A"),
        "riferimento_normativo": cfg["normativa"],
    }

    if tipo_ricorso == "pagamento_ridotto_5gg":
        result["nota"] = "Lo sconto del 30% si applica solo al pagamento entro 5 giorni dalla notifica"

    # Show all options for context
    riepilogo = {}
    for nome, c in config.items():
        d_raw = dt_notifica + timedelta(days=c["giorni"])
        d, _ = _slide_forward(d_raw)
        riepilogo[nome] = {"scadenza": d.isoformat(), "giorni": c["giorni"]}
    result["riepilogo_opzioni"] = riepilogo

    return result


@mcp.tool()
def termini_memorie_repliche(data_udienza: str) -> dict:
    """Riepilogo completo termini memorie integrative e repliche art. 171-ter c.p.c. (rito Cartabia).

    Calcola tutte le scadenze per memoria integrativa (40gg prima udienza),
    replica (20gg prima) e prova contraria (10gg prima) in un'unica risposta.

    Args:
        data_udienza: Data dell'udienza di trattazione (YYYY-MM-DD)
    """
    dt_udienza = _parse_date(data_udienza)

    termini = [
        ("memoria_integrativa", 40, "Memoria integrativa art. 171-ter, co. 1, n. 1 — precisazione/modificazione domande, eccezioni, conclusioni"),
        ("replica", 20, "Replica art. 171-ter, co. 1, n. 2 — replica ed eccezioni nuove conseguenti"),
        ("prova_contraria", 10, "Prova contraria art. 171-ter, co. 1, n. 3 — indicazione prova contraria"),
    ]

    scadenze = []
    for nome, giorni, descrizione in termini:
        scad, adjusted = _subtract_calendar_days_with_slide(dt_udienza, giorni)
        scadenze.append({
            "termine": nome,
            "giorni_prima_udienza": giorni,
            "descrizione": descrizione,
            "scadenza": scad.isoformat(),
            "prorogata_art_155": adjusted,
            "giorno_settimana": scad.strftime("%A"),
        })

    return {
        "data_udienza": data_udienza,
        "rito": "ordinario post-Cartabia (D.Lgs. 149/2022)",
        "riferimento_normativo": "Art. 171-ter c.p.c.",
        "scadenze": scadenze,
        "nota": "I termini sono a ritroso rispetto alla data di udienza. Se cadono in giorno festivo, slittano al primo giorno non festivo successivo (art. 155 c.p.c.).",
    }


@mcp.tool()
def termini_procedimento_semplificato(data_udienza: str) -> dict:
    """Termini per procedimento semplificato di cognizione art. 281-decies ss. c.p.c. (riforma Cartabia).

    Calcola: comparsa di risposta (70gg prima udienza) e memorie integrative (40/20/10gg prima).

    Args:
        data_udienza: Data dell'udienza fissata (YYYY-MM-DD)
    """
    dt_udienza = _parse_date(data_udienza)

    termini = [
        ("comparsa_risposta", 70, "Comparsa di costituzione e risposta art. 281-undecies, co. 2 c.p.c."),
        ("memoria_integrativa", 40, "Memoria integrativa art. 281-duodecies, co. 3 — precisazione domande, eccezioni, conclusioni"),
        ("replica", 20, "Replica art. 281-duodecies, co. 3 — replica e nuove eccezioni"),
        ("prova_contraria", 10, "Prova contraria art. 281-duodecies, co. 3 — indicazione prova contraria"),
    ]

    scadenze = []
    for nome, giorni, descrizione in termini:
        scad, adjusted = _subtract_calendar_days_with_slide(dt_udienza, giorni)
        scadenze.append({
            "termine": nome,
            "giorni_prima_udienza": giorni,
            "descrizione": descrizione,
            "scadenza": scad.isoformat(),
            "prorogata_art_155": adjusted,
            "giorno_settimana": scad.strftime("%A"),
        })

    return {
        "data_udienza": data_udienza,
        "rito": "semplificato di cognizione (D.Lgs. 149/2022)",
        "riferimento_normativo": "Artt. 281-decies, 281-undecies, 281-duodecies c.p.c.",
        "scadenze": scadenze,
        "nota": "Il procedimento semplificato è applicabile quando i fatti di causa non sono controversi, o la domanda è fondata su prova documentale, o è di pronta soluzione.",
    }


@mcp.tool()
def termini_183_190_cpc(data_udienza: str) -> dict:
    """Termini pre-Cartabia per memorie ex art. 183, co. 6 e comparse ex art. 190 c.p.c.

    Applicabile a cause pendenti ante 28/02/2023.
    Calcola: prima memoria (30gg), seconda (30gg dopo la prima), terza (20gg dopo la seconda),
    conclusionali (60gg dopo udienza di PC), repliche (20gg dopo conclusionali).

    Args:
        data_udienza: Data dell'udienza ex art. 183 c.p.c. o data di precisazione conclusioni (YYYY-MM-DD)
    """
    dt_udienza = _parse_date(data_udienza)

    # Memorie ex art. 183 comma 6 — termini successivi dall'udienza
    mem1_raw = dt_udienza + timedelta(days=30)
    mem1, mem1_adj = _slide_forward(mem1_raw)

    mem2_raw = mem1_raw + timedelta(days=30)
    mem2, mem2_adj = _slide_forward(mem2_raw)

    mem3_raw = mem2_raw + timedelta(days=20)
    mem3, mem3_adj = _slide_forward(mem3_raw)

    # Conclusionali e repliche ex art. 190
    concl_raw = dt_udienza + timedelta(days=60)
    concl, concl_adj = _slide_forward(concl_raw)

    repl_raw = concl_raw + timedelta(days=20)
    repl, repl_adj = _slide_forward(repl_raw)

    scadenze = [
        {
            "termine": "memoria_183_n1",
            "descrizione": "Art. 183, co. 6, n. 1 — precisazione/modificazione domande, eccezioni, conclusioni",
            "scadenza": mem1.isoformat(),
            "giorni_da_udienza": 30,
            "prorogata_art_155": mem1_adj,
            "giorno_settimana": mem1.strftime("%A"),
        },
        {
            "termine": "memoria_183_n2",
            "descrizione": "Art. 183, co. 6, n. 2 — replica e prova diretta",
            "scadenza": mem2.isoformat(),
            "giorni_da_udienza": 60,
            "prorogata_art_155": mem2_adj,
            "giorno_settimana": mem2.strftime("%A"),
        },
        {
            "termine": "memoria_183_n3",
            "descrizione": "Art. 183, co. 6, n. 3 — indicazione prova contraria",
            "scadenza": mem3.isoformat(),
            "giorni_da_udienza": 80,
            "prorogata_art_155": mem3_adj,
            "giorno_settimana": mem3.strftime("%A"),
        },
        {
            "termine": "comparsa_conclusionale",
            "descrizione": "Comparsa conclusionale art. 190 c.p.c.",
            "scadenza": concl.isoformat(),
            "giorni_da_udienza_pc": 60,
            "prorogata_art_155": concl_adj,
            "giorno_settimana": concl.strftime("%A"),
        },
        {
            "termine": "memoria_replica_190",
            "descrizione": "Memoria di replica art. 190 c.p.c.",
            "scadenza": repl.isoformat(),
            "giorni_da_udienza_pc": 80,
            "prorogata_art_155": repl_adj,
            "giorno_settimana": repl.strftime("%A"),
        },
    ]

    return {
        "data_udienza": data_udienza,
        "rito": "ordinario pre-Cartabia (ante 28/02/2023)",
        "riferimento_normativo": "Artt. 183, co. 6 e 190 c.p.c. (testo previgente)",
        "scadenze": scadenze,
        "nota": "Applicabile solo a cause iscritte a ruolo prima del 28/02/2023. Le memorie 183 decorrono dall'udienza di trattazione; conclusionali e repliche dall'udienza di PC.",
    }


@mcp.tool()
def termini_esecuzioni(
    data_notifica_titolo: str,
    tipo: str = "pignoramento_mobiliare",
) -> dict:
    """Termini procedure esecutive (art. 481 ss. c.p.c.).

    Args:
        data_notifica_titolo: Data di notifica del precetto (YYYY-MM-DD)
        tipo: 'pignoramento_mobiliare', 'pignoramento_immobiliare', 'pignoramento_presso_terzi', 'opposizione_esecuzione'
    """
    dt_notifica = _parse_date(data_notifica_titolo)

    config = {
        "pignoramento_mobiliare": {
            "termine_minimo_giorni": 10,
            "efficacia_precetto_giorni": 90,
            "descrizione": "Pignoramento mobiliare — il precetto perde efficacia se non si inizia l'esecuzione entro 90gg",
            "normativa": "Artt. 480, 481, 513 ss. c.p.c.",
        },
        "pignoramento_immobiliare": {
            "termine_minimo_giorni": 10,
            "efficacia_precetto_giorni": 90,
            "descrizione": "Pignoramento immobiliare — il precetto perde efficacia se non si inizia l'esecuzione entro 90gg",
            "normativa": "Artt. 480, 481, 555 ss. c.p.c.",
        },
        "pignoramento_presso_terzi": {
            "termine_minimo_giorni": 10,
            "efficacia_precetto_giorni": 90,
            "descrizione": "Pignoramento presso terzi — il precetto perde efficacia se non si inizia l'esecuzione entro 90gg",
            "normativa": "Artt. 480, 481, 543 ss. c.p.c.",
        },
        "opposizione_esecuzione": {
            "termine_minimo_giorni": None,
            "efficacia_precetto_giorni": None,
            "termine_opposizione_giorni": 20,
            "descrizione": "Opposizione all'esecuzione — termine per proporre opposizione agli atti esecutivi",
            "normativa": "Art. 617 c.p.c.",
        },
    }

    if tipo not in config:
        return {
            "errore": f"tipo non valido: {tipo}",
            "valori_ammessi": list(config.keys()),
        }

    cfg = config[tipo]

    if tipo == "opposizione_esecuzione":
        scad_raw = dt_notifica + timedelta(days=cfg["termine_opposizione_giorni"])
        scad, adjusted = _slide_forward(scad_raw)
        return {
            "data_notifica": data_notifica_titolo,
            "tipo": tipo,
            "descrizione": cfg["descrizione"],
            "termine_opposizione_giorni": cfg["termine_opposizione_giorni"],
            "scadenza_opposizione": scad.isoformat(),
            "prorogata_art_155": adjusted,
            "giorno_settimana": scad.strftime("%A"),
            "riferimento_normativo": cfg["normativa"],
        }

    # Termine dilatorio minimo (10gg) — non si può pignorare prima
    termine_min_raw = dt_notifica + timedelta(days=cfg["termine_minimo_giorni"])
    termine_min, termine_min_adj = _slide_forward(termine_min_raw)

    # Efficacia precetto (90gg)
    efficacia_raw = dt_notifica + timedelta(days=cfg["efficacia_precetto_giorni"])
    efficacia, efficacia_adj = _slide_forward(efficacia_raw)

    return {
        "data_notifica_precetto": data_notifica_titolo,
        "tipo": tipo,
        "descrizione": cfg["descrizione"],
        "termine_minimo_10gg": {
            "data": termine_min.isoformat(),
            "nota": "Il pignoramento non può essere eseguito prima di 10gg dalla notifica del precetto (art. 482 c.p.c.)",
            "prorogata_art_155": termine_min_adj,
        },
        "scadenza_efficacia_precetto": {
            "data": efficacia.isoformat(),
            "nota": "Il precetto perde efficacia se l'esecuzione non è iniziata entro 90gg dalla notifica (art. 481 c.p.c.)",
            "prorogata_art_155": efficacia_adj,
        },
        "finestra_utile": f"dal {termine_min.isoformat()} al {efficacia.isoformat()}",
        "riferimento_normativo": cfg["normativa"],
    }


@mcp.tool()
def termini_deposito_atti_appello(
    data_notifica_sentenza: str | None = None,
    data_pubblicazione: str | None = None,
) -> dict:
    """Termini per appello: termine lungo (6 mesi da pubblicazione) o breve (30gg da notifica).

    Include iscrizione a ruolo (30gg da notifica citazione) e comparsa di risposta (20gg prima udienza).

    Args:
        data_notifica_sentenza: Data notifica sentenza per termine breve (YYYY-MM-DD), opzionale
        data_pubblicazione: Data pubblicazione sentenza per termine lungo (YYYY-MM-DD), opzionale
    """
    if not data_notifica_sentenza and not data_pubblicazione:
        return {
            "errore": "Specificare almeno uno tra data_notifica_sentenza e data_pubblicazione",
        }

    result = {
        "riferimento_normativo": "Artt. 325, 327, 347, 166 c.p.c.",
        "termini": [],
    }

    if data_notifica_sentenza:
        dt_notifica = _parse_date(data_notifica_sentenza)
        scad_breve_raw = dt_notifica + timedelta(days=30)
        scad_breve, adj_breve = _slide_forward(scad_breve_raw)
        result["termini"].append({
            "termine": "appello_termine_breve",
            "descrizione": "Termine breve per proporre appello dalla notifica della sentenza",
            "giorni": 30,
            "decorrenza": data_notifica_sentenza,
            "scadenza": scad_breve.isoformat(),
            "prorogata_art_155": adj_breve,
            "giorno_settimana": scad_breve.strftime("%A"),
            "normativa": "Art. 325, co. 1 c.p.c.",
        })

    if data_pubblicazione:
        dt_pub = _parse_date(data_pubblicazione)
        scad_lungo_raw = _add_months(dt_pub, 6)
        scad_lungo, adj_lungo = _slide_forward(scad_lungo_raw)
        result["termini"].append({
            "termine": "appello_termine_lungo",
            "descrizione": "Termine lungo per proporre appello dalla pubblicazione della sentenza",
            "mesi": 6,
            "decorrenza": data_pubblicazione,
            "scadenza": scad_lungo.isoformat(),
            "prorogata_art_155": adj_lungo,
            "giorno_settimana": scad_lungo.strftime("%A"),
            "normativa": "Art. 327 c.p.c.",
        })

    # Iscrizione a ruolo
    result["termini"].append({
        "termine": "iscrizione_a_ruolo",
        "descrizione": "Iscrizione a ruolo entro 30gg dalla notifica della citazione in appello",
        "giorni": 30,
        "nota": "Decorre dalla notifica della citazione in appello (non dalla sentenza)",
        "normativa": "Art. 347 c.p.c.",
    })

    # Comparsa di risposta
    result["termini"].append({
        "termine": "comparsa_risposta_appellato",
        "descrizione": "Costituzione dell'appellato con comparsa di risposta almeno 20gg prima dell'udienza",
        "giorni_prima_udienza": 20,
        "nota": "Termine a ritroso dall'udienza fissata — specificare data_udienza per il calcolo esatto",
        "normativa": "Art. 166 c.p.c.",
    })

    return result


@mcp.tool()
def termini_deposito_ctu(
    data_conferimento: str,
    giorni_termine: int = 60,
) -> dict:
    """Termini deposito CTU e osservazioni delle parti (art. 195 c.p.c.).

    Default: 60gg per deposito CTU, poi 15gg per osservazioni parti, poi 15gg per replica CTU.
    Tutti soggetti a proroga art. 155 c.p.c.

    Args:
        data_conferimento: Data del conferimento dell'incarico al CTU (YYYY-MM-DD)
        giorni_termine: Giorni concessi per il deposito della relazione CTU (default 60)
    """
    dt_conf = _parse_date(data_conferimento)

    # Deposito CTU
    deposito_raw = dt_conf + timedelta(days=giorni_termine)
    deposito, deposito_adj = _slide_forward(deposito_raw)

    # Osservazioni parti (15gg dal deposito CTU)
    oss_raw = deposito_raw + timedelta(days=15)
    oss, oss_adj = _slide_forward(oss_raw)

    # Replica CTU (15gg dalle osservazioni)
    replica_raw = oss_raw + timedelta(days=15)
    replica, replica_adj = _slide_forward(replica_raw)

    return {
        "data_conferimento": data_conferimento,
        "giorni_termine_ctu": giorni_termine,
        "riferimento_normativo": "Art. 195, co. 3 c.p.c.",
        "scadenze": [
            {
                "termine": "deposito_bozza_ctu",
                "descrizione": "Deposito bozza relazione CTU",
                "giorni_da_conferimento": giorni_termine,
                "scadenza": deposito.isoformat(),
                "prorogata_art_155": deposito_adj,
                "giorno_settimana": deposito.strftime("%A"),
            },
            {
                "termine": "osservazioni_parti",
                "descrizione": "Termine per le osservazioni delle parti alla bozza CTU",
                "giorni_da_deposito_ctu": 15,
                "scadenza": oss.isoformat(),
                "prorogata_art_155": oss_adj,
                "giorno_settimana": oss.strftime("%A"),
            },
            {
                "termine": "replica_ctu",
                "descrizione": "Termine per la replica del CTU alle osservazioni delle parti e deposito relazione definitiva",
                "giorni_da_osservazioni": 15,
                "scadenza": replica.isoformat(),
                "prorogata_art_155": replica_adj,
                "giorno_settimana": replica.strftime("%A"),
            },
        ],
        "nota": "I termini di 15gg per osservazioni e replica sono quelli previsti dall'art. 195, co. 3 c.p.c. Il giudice può disporre termini diversi. Art. 155 c.p.c. si applica a tutti i termini.",
    }
