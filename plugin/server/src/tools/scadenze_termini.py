"""Calcolo scadenze processuali civili: termini ex art. 155 c.p.c., memorie ex art. 171-ter c.p.c.
e termini per la decisione ex art. 189 c.p.c. (rito post-Cartabia D.Lgs. 149/2022), procedimento
semplificato (artt. 281-decies ss.), impugnazioni, appello, esecuzioni, famiglia, contravvenzioni
stradali. La sospensione feriale (1-31 agosto, L. 742/1969) è calcolata giorno per giorno.
Per procedimenti iscritti a ruolo prima del 28/02/2023 usare termini_183_190_cpc() (regime previgente)."""

import calendar
import json
from datetime import date, timedelta
from pathlib import Path

from src.server import mcp
from src.lib._data import sourced
from src.lib._regime import previgente

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "festivita.json") as f:
    _FESTIVITA_FISSE = json.load(f)["fisse"]

#: Riferimento unico alla sospensione feriale, ripetuto nelle risposte.
_RIF_FERIALE = "L. 742/1969, art. 1 (sospensione dal 1° al 31 agosto, come modificato dall'art. 16 DL 132/2014)"
#: Le materie sottratte alla sospensione (art. 3 L. 742/1969, che rinvia all'art. 92 R.D. 12/1941).
_NOTA_ESCLUSIONI_FERIALE = (
    "La sospensione feriale non si applica alle cause di lavoro e previdenza, alimenti, "
    "sfratti, opposizioni esecutive, procedimenti cautelari e alle altre materie dell'art. 3 "
    "L. 742/1969: in quei casi impostare sospensione_feriale=False."
)


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _validate_date(d: str) -> dict | None:
    """Return a structured error dict if d is not a valid YYYY-MM-DD date, else None."""
    try:
        date.fromisoformat(d)
        return None
    except (ValueError, TypeError):
        return {"errore": f"data non valida: {d!r} (formato atteso YYYY-MM-DD)"}


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
        if f.get("dal_anno") and d.year < f["dal_anno"]:
            continue
        if d.day == f["giorno"] and d.month == f["mese"]:
            return True
    pasqua = _easter(d.year)
    if d == pasqua or d == pasqua + timedelta(days=1):  # Lunedì dell'Angelo
        return True
    return False


def _slide_forward(d: date) -> tuple[date, bool]:
    """Art. 155 co. 4-5 c.p.c.: slide to next business day if holiday or Saturday."""
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


def _slide_backward(d: date) -> tuple[date, bool]:
    """Termini a ritroso: se il giorno finale è festivo (o sabato) la scadenza anticipa
    al giorno non festivo precedente, perché una proroga in avanti ridurrebbe il termine
    minimo garantito alla controparte."""
    original = d
    while _is_holiday(d):
        d -= timedelta(days=1)
    return d, d != original


def _in_sospensione(d: date) -> bool:
    """1-31 agosto: i giorni che non si contano (art. 1 L. 742/1969)."""
    return d.month == 8


def _conta_avanti(dies_a_quo: date, giorni: int, feriale: bool) -> tuple[date, bool]:
    """Conta `giorni` in avanti dal dies a quo (escluso, art. 155 co. 1 c.p.c.).

    Con la sospensione feriale i giorni dal 1° al 31 agosto non si contano; se il
    dies a quo cade in agosto il decorso è differito al 1° settembre, che vale come
    primo giorno (art. 1 co. 2 L. 742/1969). Restituisce anche se la sospensione ha
    inciso sul conteggio.
    """
    d = dies_a_quo
    contati = 0
    incisa = False
    while contati < giorni:
        d += timedelta(days=1)
        if feriale and _in_sospensione(d):
            incisa = True
            continue
        contati += 1
    return d, incisa


def _conta_ritroso(dies_ad_quem: date, giorni: int, feriale: bool) -> tuple[date, bool]:
    """Conta `giorni` a ritroso dal dies ad quem (l'udienza, esclusa dal computo).

    Con la sospensione feriale i giorni dal 1° al 31 agosto non si contano: un
    termine "a ritroso" che li attraversa anticipa di conseguenza. Restituisce anche
    se la sospensione ha inciso sul conteggio.
    """
    d = dies_ad_quem
    contati = 0
    incisa = False
    while contati < giorni:
        d -= timedelta(days=1)
        if feriale and _in_sospensione(d):
            incisa = True
            continue
        contati += 1
    return d, incisa


def _add_months(d: date, months: int) -> date:
    """Add N months to a date (art. 155 co. 2 c.p.c.: calendario comune), clamping to
    the last day of the month when the corresponding day does not exist."""
    year = d.year + (d.month + months - 1) // 12
    month = (d.month + months - 1) % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(d.day, max_day)
    return date(year, month, day)


def _mesi_avanti(dies_a_quo: date, mesi: int, feriale: bool) -> tuple[date, bool]:
    """Termine a mesi (art. 155 co. 2 c.p.c.) con sospensione feriale.

    Ogni periodo 1-31 agosto compreso nel termine non si conta e sposta la scadenza
    di 31 giorni. Se il dies a quo cade in agosto il decorso è differito alla fine
    della sospensione (art. 1 co. 2 L. 742/1969): il termine si computa dal 31
    agosto, lettura prudenziale rispetto a chi lo fa decorrere dal 1° settembre.
    """
    incisa = False
    if feriale and _in_sospensione(dies_a_quo):
        dies_a_quo = date(dies_a_quo.year, 8, 31)
        incisa = True
    fine = _add_months(dies_a_quo, mesi)
    if feriale:
        anno = dies_a_quo.year
        while True:
            primo_agosto = date(anno, 8, 1)
            if primo_agosto > fine:
                break
            if primo_agosto > dies_a_quo:
                fine += timedelta(days=31)
                incisa = True
            anno += 1
    return fine, incisa


def _voce_scadenza(scadenza: date, prorogata: bool) -> dict:
    """Le tre chiavi che ogni scadenza espone, sempre con lo stesso nome."""
    return {
        "scadenza": scadenza.isoformat(),
        "prorogata_art_155": prorogata,
        "giorno_settimana": scadenza.strftime("%A"),
    }


@mcp.tool(tags={"scadenze", "sinistro"})
@sourced("festivita")
def scadenza_processuale(
    data_evento: str,
    giorni: int,
    tipo: str = "calendario",
    sospensione_feriale: bool = False,
) -> dict:
    """Calcola una scadenza processuale generica con proroga festiva ex art. 155 c.p.c.
    Vigenza: art. 155 c.p.c. (testo vigente — non modificato dalla Riforma Cartabia); L. 742/1969
    per la sospensione feriale (1-31 agosto).
    Precisione: ESATTO (dies a quo escluso; proroga automatica al primo giorno feriale successivo;
    sospensione feriale contata giorno per giorno se richiesta).

    Usa questo quando: devi calcolare un termine di legge generico (non coperto dagli altri tool).
    Per memorie ex art. 171-ter → usa termini_processuali_civili() o termini_memorie_repliche().

    Args:
        data_evento: Data da cui decorre il termine — dies a quo ESCLUSO (YYYY-MM-DD)
        giorni: Numero di giorni del termine (interi positivi)
        tipo: Tipo di conteggio: 'calendario' (dies a quo escluso, art. 155 c.p.c.) o 'lavorativi'
        sospensione_feriale: True per non contare i giorni 1-31 agosto (L. 742/1969) — solo per
                             termini processuali di cause non escluse dall'art. 3 L. 742/1969.
                             Default False perché il tool serve anche per termini sostanziali.
    """
    err = _validate_date(data_evento)
    if err:
        return err
    if not isinstance(giorni, int) or giorni < 1:
        return {"errore": "giorni deve essere un intero positivo"}
    if tipo not in ("calendario", "lavorativi"):
        return {
            "errore": f"tipo non valido: {tipo}",
            "valori_ammessi": ["calendario", "lavorativi"],
        }
    dt_evento = _parse_date(data_evento)

    incisa = False
    if tipo == "lavorativi":
        scadenza = _add_business_days(dt_evento, giorni)
        adjusted = False
    else:
        scadenza_raw, incisa = _conta_avanti(dt_evento, giorni, sospensione_feriale)
        scadenza, adjusted = _slide_forward(scadenza_raw)

    result = {
        "data_evento": data_evento,
        "giorni": giorni,
        "tipo": tipo,
        **_voce_scadenza(scadenza, adjusted),
        "sospensione_feriale_applicata": sospensione_feriale,
        "sospensione_feriale_incidente": incisa,
        "riferimento_normativo": "Art. 155 c.p.c. — se il termine scade in giorno festivo, è prorogato al primo giorno seguente non festivo",
    }
    if sospensione_feriale:
        result["riferimento_normativo"] += f"; {_RIF_FERIALE}"
    return result


@mcp.tool(tags={"scadenze"})
@sourced("festivita")
def termini_processuali_civili(
    data_udienza: str,
    tipo_termine: str,
    sospensione_feriale: bool = True,
    giorni: int | None = None,
) -> dict:
    """Calcola un termine del rito ordinario post-Cartabia: memorie ex art. 171-ter c.p.c. (a ritroso
    dall'udienza ex art. 183) o atti per la decisione ex art. 189 c.p.c. (a ritroso dall'udienza di
    rimessione della causa in decisione).
    Vigenza: artt. 171-ter e 189 c.p.c. nel testo del D.Lgs. 149/2022 (in vigore dal 28/02/2023);
    l'art. 190 c.p.c. (conclusionali e repliche dopo l'udienza di precisazione delle conclusioni) è
    stato abrogato dalla stessa riforma e vale solo per le cause iscritte prima del 28/02/2023.
    Precisione: ESATTO (termini di legge a ritroso; sospensione feriale L. 742/1969 contata giorno
    per giorno; scadenza in giorno festivo anticipata al giorno non festivo precedente).
    Nota: per procedimenti iscritti a ruolo PRIMA del 28/02/2023 → usa termini_183_190_cpc().

    Args:
        data_udienza: Per le memorie: data dell'udienza di comparizione e trattazione ex art. 183.
                      Per note, conclusionale e replica: data dell'udienza di rimessione della causa
                      in decisione fissata dal giudice ex art. 189 (YYYY-MM-DD)
        tipo_termine: 'memoria_I' (40gg prima, art. 171-ter n. 1), 'memoria_II' (20gg prima, n. 2),
                      'memoria_III' (10gg prima, n. 3), 'note_conclusioni' (fino a 60gg prima,
                      art. 189 n. 1), 'comparsa_conclusionale' (fino a 30gg prima, art. 189 n. 2),
                      'replica' (fino a 15gg prima, art. 189 n. 3)
        sospensione_feriale: Applica la sospensione feriale 1-31 agosto ex L. 742/1969 (default True;
                             False per le materie escluse dall'art. 3 L. 742/1969, es. lavoro)
        giorni: Termine diverso assegnato dal giudice, in giorni prima dell'udienza (facoltativo:
                l'art. 189 fissa solo i massimi di 60/30/15 giorni)
    """
    err = _validate_date(data_udienza)
    if err:
        return err
    dt_udienza = _parse_date(data_udienza)

    termini_config = {
        "memoria_I": {
            "giorni": 40,
            "gruppo": "memorie",
            "descrizione": "Memoria art. 171-ter, co. 1, n. 1 — precisazione/modificazione domande, eccezioni, conclusioni",
        },
        "memoria_II": {
            "giorni": 20,
            "gruppo": "memorie",
            "descrizione": "Memoria art. 171-ter, co. 1, n. 2 — replica ed eccezioni nuove",
        },
        "memoria_III": {
            "giorni": 10,
            "gruppo": "memorie",
            "descrizione": "Memoria art. 171-ter, co. 1, n. 3 — indicazione prova contraria",
        },
        "note_conclusioni": {
            "giorni": 60,
            "gruppo": "decisione",
            "descrizione": "Note scritte di precisazione delle conclusioni art. 189, co. 1, n. 1 (termine non superiore a 60gg prima dell'udienza di rimessione in decisione)",
        },
        "comparsa_conclusionale": {
            "giorni": 30,
            "gruppo": "decisione",
            "descrizione": "Comparsa conclusionale art. 189, co. 1, n. 2 (termine non superiore a 30gg prima dell'udienza di rimessione in decisione)",
        },
        "replica": {
            "giorni": 15,
            "gruppo": "decisione",
            "descrizione": "Memoria di replica art. 189, co. 1, n. 3 (termine non superiore a 15gg prima dell'udienza di rimessione in decisione)",
        },
    }

    if tipo_termine not in termini_config:
        return {
            "errore": f"tipo_termine non valido: {tipo_termine}",
            "valori_ammessi": list(termini_config.keys()),
        }
    if giorni is not None and (not isinstance(giorni, int) or giorni < 1):
        return {"errore": "giorni deve essere un intero positivo"}

    config = termini_config[tipo_termine]
    giorni_applicati = giorni if giorni is not None else config["giorni"]

    scadenza_raw, incisa = _conta_ritroso(dt_udienza, giorni_applicati, sospensione_feriale)
    scadenza, adjusted = _slide_backward(scadenza_raw)

    # Riepilogo dei termini dello stesso gruppo (massimi di legge)
    riepilogo = {}
    for nome, cfg in termini_config.items():
        if cfg["gruppo"] != config["gruppo"]:
            continue
        d_raw, _ = _conta_ritroso(dt_udienza, cfg["giorni"], sospensione_feriale)
        d, _ = _slide_backward(d_raw)
        riepilogo[nome] = d.isoformat()

    if config["gruppo"] == "memorie":
        riferimento = "Art. 171-ter c.p.c. (D.Lgs. 149/2022 — Riforma Cartabia)"
        udienza_riferimento = "udienza di comparizione e trattazione ex art. 183 c.p.c."
    else:
        riferimento = "Art. 189 c.p.c. (D.Lgs. 149/2022 — Riforma Cartabia; art. 190 c.p.c. abrogato)"
        udienza_riferimento = "udienza di rimessione della causa in decisione ex art. 189 c.p.c."
    if sospensione_feriale:
        riferimento += f"; {_RIF_FERIALE}"

    result = {
        "data_udienza": data_udienza,
        "udienza_di_riferimento": udienza_riferimento,
        "tipo_termine": tipo_termine,
        "descrizione": config["descrizione"],
        "giorni_prima_udienza": giorni_applicati,
        "giorni_assegnati_dal_giudice": giorni is not None,
        **_voce_scadenza(scadenza, adjusted),
        "sospensione_feriale_applicata": sospensione_feriale,
        "sospensione_feriale_incidente": incisa,
        "riferimento_normativo": riferimento,
    }
    if config["gruppo"] == "memorie":
        result["riepilogo_termini_memorie"] = riepilogo
    else:
        result["riepilogo_termini_decisione"] = riepilogo
        result["nota"] = (
            "L'art. 189 fissa i termini massimi (60/30/15 giorni prima dell'udienza): il giudice "
            "può assegnarne di più brevi — in tal caso passare `giorni`."
        )
    return result


@mcp.tool(tags={"scadenze"})
@sourced("festivita")
def termini_separazione_divorzio(
    data_evento: str,
    tipo: str,
) -> dict:
    """Calcola le scadenze di diritto di famiglia per separazione, divorzio e negoziazione assistita.
    Vigenza: art. 3 n. 2 lett. b) L. 898/1970 (mod. L. 55/2015 — divorzio breve); DL 132/2014 conv.
    L. 162/2014. Dal 28/02/2023 (D.Lgs. 149/2022, art. 473-bis.49 c.p.c.) la domanda di divorzio
    può essere proposta cumulativamente con quella di separazione: in tal caso i termini qui
    calcolati indicano solo quando il giudice può pronunciare sul divorzio.
    Precisione: ESATTO (termini di legge; proroga art. 155 c.p.c. se cadono in giorno festivo).

    Args:
        data_evento: Data da cui decorre il termine (YYYY-MM-DD): per la separazione giudiziale o
                     consensuale la comparizione dei coniugi in udienza (prima udienza; ante
                     28/02/2023 udienza presidenziale), NON l'omologa o il passaggio in giudicato;
                     per la negoziazione assistita la data certificata nell'accordo
        tipo: Tipo di procedimento: 'separazione_consensuale' (6 mesi per il divorzio),
              'separazione_giudiziale' (12 mesi), 'negoziazione_assistita' (6 mesi),
              'ricorso_modifica' (nessun termine — proponibile in qualsiasi momento)
    """
    err = _validate_date(data_evento)
    if err:
        return err
    dt_evento = _parse_date(data_evento)

    config = {
        "separazione_consensuale": {
            "mesi": 6,
            "descrizione": "Termine per presentare ricorso di divorzio dopo separazione consensuale (decorre dalla comparizione dei coniugi in udienza)",
            "normativa": "Art. 3, n. 2, lett. b), L. 898/1970 (mod. L. 55/2015)",
        },
        "separazione_giudiziale": {
            "mesi": 12,
            "descrizione": "Termine per presentare ricorso di divorzio dopo separazione giudiziale (decorre dalla comparizione dei coniugi in udienza)",
            "normativa": "Art. 3, n. 2, lett. b), L. 898/1970 (mod. L. 55/2015)",
        },
        "negoziazione_assistita": {
            "mesi": 6,
            "descrizione": "Termine per presentare ricorso di divorzio dopo negoziazione assistita (decorre dalla data certificata nell'accordo)",
            "normativa": "Art. 6 DL 132/2014 conv. L. 162/2014 — Art. 3 L. 898/1970",
        },
        "ricorso_modifica": {
            "mesi": 0,
            "descrizione": "Ricorso per modifica delle condizioni — nessun termine specifico, proponibile in qualsiasi momento al mutare delle circostanze",
            "normativa": "Art. 473-bis.29 c.p.c. (già art. 710 c.p.c.) / Art. 9 L. 898/1970",
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

    mesi = cfg["mesi"]
    scadenza_raw = _add_months(dt_evento, mesi)
    scadenza, adjusted = _slide_forward(scadenza_raw)

    return {
        "data_evento": data_evento,
        "tipo": tipo,
        "descrizione": cfg["descrizione"],
        "mesi_termine": mesi,
        **_voce_scadenza(scadenza, adjusted),
        "riferimento_normativo": cfg["normativa"],
    }


@mcp.tool(tags={"scadenze", "sinistro"})
@sourced("festivita")
def scadenze_impugnazioni(
    data_pubblicazione: str,
    tipo_impugnazione: str,
    notificata: bool = False,
    sospensione_feriale: bool = True,
) -> dict:
    """Calcola i termini di impugnazione per sentenze civili (termine breve e termine lungo).
    Vigenza: artt. 325-327 c.p.c. (termini non modificati dalla Riforma Cartabia D.Lgs. 149/2022);
    art. 47 c.p.c. per il regolamento di competenza; L. 742/1969 per la sospensione feriale.
    Precisione: ESATTO (termini di legge; sospensione feriale contata giorno per giorno; proroga
    art. 155 c.p.c. se cadono in giorno festivo).

    Args:
        data_pubblicazione: Data di pubblicazione della sentenza (termine lungo) o di notifica
                            (termine breve, con notificata=True) (YYYY-MM-DD)
        tipo_impugnazione: 'appello_sentenza' (30gg breve / 6 mesi lungo), 'cassazione' (60gg /
                           6 mesi), 'revocazione' (30gg / 6 mesi per i motivi nn. 4-5 art. 395),
                           'opposizione_terzo' (30gg dalla scoperta per l'opposizione revocatoria
                           ex art. 404 co. 2; senza termine quella ordinaria ex art. 404 co. 1),
                           'regolamento_competenza' (30gg dalla comunicazione ex art. 47; nessun
                           termine lungo)
        notificata: True = termine breve dalla notifica; False = termine lungo dalla pubblicazione
        sospensione_feriale: Applica la sospensione feriale 1-31 agosto ex L. 742/1969 (default
                             True; False per le materie escluse dall'art. 3 L. 742/1969)
    """
    err = _validate_date(data_pubblicazione)
    if err:
        return err
    dt_pub = _parse_date(data_pubblicazione)

    config = {
        "appello_sentenza": {
            "breve": 30,
            "lungo_mesi": 6,
            "descrizione": "Appello sentenza di primo grado",
            "normativa": "Artt. 325, co. 1, e 327 c.p.c.",
        },
        "cassazione": {
            "breve": 60,
            "lungo_mesi": 6,
            "descrizione": "Ricorso per cassazione",
            "normativa": "Artt. 325, co. 2, e 327 c.p.c.",
        },
        "revocazione": {
            "breve": 30,
            "lungo_mesi": 6,
            "descrizione": "Revocazione (termine lungo solo per i motivi nn. 4 e 5 dell'art. 395)",
            "normativa": "Artt. 325, co. 1, 326 e 327 c.p.c.",
        },
        "opposizione_terzo": {
            "breve": 30,
            "lungo_mesi": None,
            "descrizione": "Opposizione di terzo — revocatoria (art. 404 co. 2): 30gg dalla scoperta del dolo o della collusione; ordinaria (art. 404 co. 1): nessun termine",
            "normativa": "Artt. 325, co. 1, 326 e 404 c.p.c.",
        },
        "regolamento_competenza": {
            "breve": 30,
            "lungo_mesi": None,
            "descrizione": "Regolamento di competenza — 30gg dalla comunicazione dell'ordinanza (o dalla notificazione dell'impugnazione ordinaria); nessun termine lungo",
            "normativa": "Art. 47, co. 2, c.p.c.",
        },
    }

    if tipo_impugnazione not in config:
        return {
            "errore": f"tipo_impugnazione non valido: {tipo_impugnazione}",
            "valori_ammessi": list(config.keys()),
        }

    cfg = config[tipo_impugnazione]
    riferimento = cfg["normativa"] + (f"; {_RIF_FERIALE}" if sospensione_feriale else "")

    if notificata:
        scadenza_raw, incisa = _conta_avanti(dt_pub, cfg["breve"], sospensione_feriale)
        scadenza, adjusted = _slide_forward(scadenza_raw)
        tipo_termine = "breve (da notifica)"
        giorni_termine = cfg["breve"]
    elif cfg["lungo_mesi"] is not None:
        mesi = cfg["lungo_mesi"]
        scadenza_raw, incisa = _mesi_avanti(dt_pub, mesi, sospensione_feriale)
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
            "nota": (
                "Nessun termine lungo per questo tipo di impugnazione: usare notificata=True "
                "per il termine di 30 giorni dalla comunicazione/notifica (o dalla scoperta)"
            ),
            "riferimento_normativo": cfg["normativa"],
        }

    return {
        "data_pubblicazione": data_pubblicazione,
        "tipo_impugnazione": tipo_impugnazione,
        "descrizione": cfg["descrizione"],
        "notificata": notificata,
        "tipo_termine": tipo_termine,
        "giorni_termine": giorni_termine,
        **_voce_scadenza(scadenza, adjusted),
        "sospensione_feriale_applicata": sospensione_feriale,
        "sospensione_feriale_incidente": incisa,
        "riferimento_normativo": riferimento,
    }


@mcp.tool(tags={"scadenze"})
@sourced("festivita")
def scadenze_multe(
    data_notifica: str,
    tipo_ricorso: str,
) -> dict:
    """Calcola i termini per ricorso o pagamento contro contravvenzioni al Codice della Strada.
    Vigenza: D.Lgs. 285/1992 Codice della Strada, artt. 202, 203 e 204-bis; sconto del 30% per il
    pagamento entro 5 giorni introdotto dall'art. 20 DL 69/2013 conv. L. 98/2013.
    Precisione: ESATTO (termini di legge; proroga art. 155 c.p.c. se cadono in giorno festivo; la
    sospensione feriale non viene applicata).

    Args:
        data_notifica: Data di notifica del verbale di accertamento (YYYY-MM-DD)
        tipo_ricorso: Tipo di opzione: 'prefetto' (60gg, ricorso amministrativo),
                      'giudice_pace' (30gg, ricorso giurisdizionale),
                      'pagamento_ridotto' (60gg, sanzione minima prevista),
                      'pagamento_ridotto_5gg' (5gg, sconto 30% sulla sanzione minima)
    """
    err = _validate_date(data_notifica)
    if err:
        return err
    dt_notifica = _parse_date(data_notifica)

    config = {
        "prefetto": {
            "giorni": 60,
            "descrizione": "Ricorso al Prefetto",
            "normativa": "Art. 203 D.Lgs. 285/1992 (Codice della Strada)",
        },
        "giudice_pace": {
            "giorni": 30,
            "descrizione": "Ricorso al Giudice di Pace (60gg se il ricorrente risiede all'estero)",
            "normativa": "Art. 204-bis D.Lgs. 285/1992; art. 7 D.Lgs. 150/2011",
        },
        "pagamento_ridotto": {
            "giorni": 60,
            "descrizione": "Pagamento in misura ridotta (sanzione minima)",
            "normativa": "Art. 202, co. 1, D.Lgs. 285/1992",
        },
        "pagamento_ridotto_5gg": {
            "giorni": 5,
            "descrizione": "Pagamento entro 5 giorni con sconto del 30%",
            "normativa": "Art. 202, co. 1, D.Lgs. 285/1992 (mod. art. 20 DL 69/2013 conv. L. 98/2013)",
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
        **_voce_scadenza(scadenza, adjusted),
        "riferimento_normativo": cfg["normativa"],
    }

    if tipo_ricorso == "pagamento_ridotto_5gg":
        result["nota"] = "Lo sconto del 30% si applica solo al pagamento entro 5 giorni dalla notifica"
    if tipo_ricorso == "giudice_pace":
        result["nota"] = (
            "Il termine non è stato sospeso per il periodo feriale: se il ricorso attraversa "
            "il mese di agosto, verificare l'applicabilità della L. 742/1969"
        )

    # Show all options for context
    riepilogo = {}
    for nome, c in config.items():
        d_raw = dt_notifica + timedelta(days=c["giorni"])
        d, _ = _slide_forward(d_raw)
        riepilogo[nome] = {"scadenza": d.isoformat(), "giorni": c["giorni"]}
    result["riepilogo_opzioni"] = riepilogo

    return result


@mcp.tool(tags={"scadenze"})
@sourced("festivita")
def termini_memorie_repliche(
    data_udienza: str,
    sospensione_feriale: bool = True,
) -> dict:
    """Calcola in un'unica risposta tutte le scadenze per memorie e repliche ex art. 171-ter c.p.c.
    Vigenza: rito ordinario post-Cartabia (D.Lgs. 149/2022, in vigore dal 28/02/2023); L. 742/1969
    per la sospensione feriale.
    Precisione: ESATTO (termini di legge a ritroso dall'udienza; sospensione feriale contata giorno
    per giorno; scadenza in giorno festivo anticipata al giorno non festivo precedente).
    Nota: per procedimenti iscritti a ruolo PRIMA del 28/02/2023 → usa termini_183_190_cpc().

    Calcola: memoria integrativa (40gg prima), replica (20gg prima), prova contraria (10gg prima).

    Args:
        data_udienza: Data dell'udienza di comparizione e trattazione ex art. 183 c.p.c. (YYYY-MM-DD)
        sospensione_feriale: Applica la sospensione feriale 1-31 agosto ex L. 742/1969 (default
                             True; False per le materie escluse dall'art. 3 L. 742/1969)
    """
    err = _validate_date(data_udienza)
    if err:
        return err
    dt_udienza = _parse_date(data_udienza)

    termini = [
        ("memoria_integrativa", 40, "Memoria integrativa art. 171-ter, co. 1, n. 1 — precisazione/modificazione domande, eccezioni, conclusioni"),
        ("replica", 20, "Replica art. 171-ter, co. 1, n. 2 — replica ed eccezioni nuove conseguenti"),
        ("prova_contraria", 10, "Prova contraria art. 171-ter, co. 1, n. 3 — indicazione prova contraria"),
    ]

    scadenze = []
    incisa_totale = False
    for nome, giorni, descrizione in termini:
        scad_raw, incisa = _conta_ritroso(dt_udienza, giorni, sospensione_feriale)
        incisa_totale = incisa_totale or incisa
        scad, adjusted = _slide_backward(scad_raw)
        scadenze.append({
            "termine": nome,
            "giorni_prima_udienza": giorni,
            "descrizione": descrizione,
            **_voce_scadenza(scad, adjusted),
        })

    riferimento = "Art. 171-ter c.p.c." + (f"; {_RIF_FERIALE}" if sospensione_feriale else "")
    return {
        "data_udienza": data_udienza,
        "rito": "ordinario post-Cartabia (D.Lgs. 149/2022)",
        "riferimento_normativo": riferimento,
        "sospensione_feriale_applicata": sospensione_feriale,
        "sospensione_feriale_incidente": incisa_totale,
        "scadenze": scadenze,
        "nota": (
            "I termini sono a ritroso rispetto alla data di udienza. Se cadono in giorno festivo "
            "o di sabato anticipano al giorno non festivo precedente (art. 155 c.p.c.). "
            + _NOTA_ESCLUSIONI_FERIALE
        ),
    }


@mcp.tool(tags={"scadenze"})
@sourced("festivita")
def termini_procedimento_semplificato(
    data_udienza: str,
    giorni_memoria: int = 20,
    giorni_replica: int = 10,
    sospensione_feriale: bool = True,
) -> dict:
    """Calcola i termini del procedimento semplificato di cognizione (artt. 281-decies ss. c.p.c.).
    Vigenza: artt. 281-undecies e 281-duodecies c.p.c. introdotti dal D.Lgs. 149/2022 (in vigore dal
    28/02/2023): costituzione del convenuto non oltre 10 giorni prima dell'udienza (art. 281-undecies
    co. 3); termini liberi non minori di 40 giorni (60 se all'estero) tra notifica del ricorso e
    udienza (co. 2); memorie solo se concesse dal giudice, entro un termine non superiore a 20 giorni
    e un ulteriore termine non superiore a 10 giorni (art. 281-duodecies co. 3).
    Precisione: ESATTO (termini di legge; sospensione feriale contata giorno per giorno; proroga o
    anticipazione art. 155 c.p.c.). I 40/20/10 giorni delle memorie ex art. 171-ter NON si applicano
    al rito semplificato.
    Nota: per procedimenti ante 28/02/2023 → usa termini_183_190_cpc() (rito previgente).

    Calcola: ultimo giorno utile per la notifica del ricorso (41 e 61 giorni prima dell'udienza),
    costituzione del convenuto (10gg prima), memoria integrativa e replica con prova contraria
    (in avanti dall'udienza, se il giudice le concede).

    Args:
        data_udienza: Data della prima udienza fissata con il decreto ex art. 281-undecies (YYYY-MM-DD)
        giorni_memoria: Giorni concessi dal giudice per la memoria integrativa (massimo 20, default 20)
        giorni_replica: Ulteriori giorni concessi per replica e prova contraria (massimo 10, default 10)
        sospensione_feriale: Applica la sospensione feriale 1-31 agosto ex L. 742/1969 (default
                             True; False per le materie escluse dall'art. 3 L. 742/1969)
    """
    err = _validate_date(data_udienza)
    if err:
        return err
    if not isinstance(giorni_memoria, int) or not 1 <= giorni_memoria <= 20:
        return {"errore": "giorni_memoria deve essere un intero tra 1 e 20 (art. 281-duodecies co. 3)"}
    if not isinstance(giorni_replica, int) or not 1 <= giorni_replica <= 10:
        return {"errore": "giorni_replica deve essere un intero tra 1 e 10 (art. 281-duodecies co. 3)"}
    dt_udienza = _parse_date(data_udienza)

    scadenze = []
    incisa_totale = False

    # Termini a ritroso dall'udienza
    for nome, giorni, descrizione, nota in (
        (
            "notifica_ricorso_italia",
            41,
            "Ultimo giorno utile per notificare ricorso e decreto in Italia — art. 281-undecies, co. 2 (termini liberi non minori di 40 giorni)",
            "Termine libero: non si contano né il giorno della notifica né quello dell'udienza",
        ),
        (
            "notifica_ricorso_estero",
            61,
            "Ultimo giorno utile per notificare ricorso e decreto all'estero — art. 281-undecies, co. 2 (termini liberi non minori di 60 giorni)",
            "Termine libero: non si contano né il giorno della notifica né quello dell'udienza",
        ),
        (
            "costituzione_convenuto",
            10,
            "Comparsa di costituzione e risposta del convenuto — art. 281-undecies, co. 3 (non oltre 10 giorni prima dell'udienza)",
            "Domande riconvenzionali, chiamata di terzo ed eccezioni non rilevabili d'ufficio a pena di decadenza",
        ),
    ):
        scad_raw, incisa = _conta_ritroso(dt_udienza, giorni, sospensione_feriale)
        incisa_totale = incisa_totale or incisa
        scad, adjusted = _slide_backward(scad_raw)
        scadenze.append({
            "termine": nome,
            "giorni_prima_udienza": giorni,
            "descrizione": descrizione,
            **_voce_scadenza(scad, adjusted),
            "nota": nota,
        })

    # Termini in avanti dall'udienza, solo se il giudice li concede
    memoria_raw, incisa_m = _conta_avanti(dt_udienza, giorni_memoria, sospensione_feriale)
    memoria, adj_m = _slide_forward(memoria_raw)
    replica_raw, incisa_r = _conta_avanti(memoria_raw, giorni_replica, sospensione_feriale)
    replica, adj_r = _slide_forward(replica_raw)
    incisa_totale = incisa_totale or incisa_m or incisa_r
    scadenze.append({
        "termine": "memoria_integrativa",
        "giorni_da_udienza": giorni_memoria,
        "descrizione": "Memoria per precisare o modificare domande, eccezioni e conclusioni, indicare mezzi di prova e produrre documenti — art. 281-duodecies, co. 3 (termine perentorio non superiore a 20 giorni, solo se concesso dal giudice su richiesta e per giustificato motivo)",
        **_voce_scadenza(memoria, adj_m),
        "nota": "Eventuale: il termine esiste solo se il giudice lo concede; qui è calcolato dall'udienza",
    })
    scadenze.append({
        "termine": "replica_prova_contraria",
        "giorni_da_memoria": giorni_replica,
        "descrizione": "Replica e prova contraria — art. 281-duodecies, co. 3 (ulteriore termine perentorio non superiore a 10 giorni)",
        **_voce_scadenza(replica, adj_r),
        "nota": "Eventuale: decorre dalla scadenza del termine per la memoria integrativa",
    })

    riferimento = "Artt. 281-decies, 281-undecies, 281-duodecies c.p.c." + (
        f"; {_RIF_FERIALE}" if sospensione_feriale else ""
    )
    return {
        "data_udienza": data_udienza,
        "rito": "semplificato di cognizione (D.Lgs. 149/2022)",
        "riferimento_normativo": riferimento,
        "sospensione_feriale_applicata": sospensione_feriale,
        "sospensione_feriale_incidente": incisa_totale,
        "scadenze": scadenze,
        "nota": (
            "Il procedimento semplificato è applicabile quando i fatti di causa non sono controversi, "
            "o la domanda è fondata su prova documentale, o è di pronta soluzione (art. 281-decies). "
            "Se il giudice rileva che mancano i presupposti dispone il mutamento in rito ordinario, con "
            "udienza ex art. 183 e termini ex art. 171-ter (art. 281-duodecies co. 1). "
            + _NOTA_ESCLUSIONI_FERIALE
        ),
    }


@mcp.tool(tags={"scadenze", "previgente"})
@previgente
@sourced("festivita")
def termini_183_190_cpc(
    data_udienza: str,
    sospensione_feriale: bool = True,
) -> dict:
    """Calcola i termini ex art. 183 co. 6 e art. 190 c.p.c. (rito civile ordinario PRE-Cartabia).
    Regime: PREVIGENTE — cause iscritte a ruolo prima del 28/02/2023 (artt. 183 co. 6 e 190 c.p.c.
    nel testo anteriore al D.Lgs. 149/2022); tool vigenti: termini_memorie_repliche,
    termini_processuali_civili
    Vigenza: artt. 183 co. 6 e 190 c.p.c. nel testo previgente — applicabile SOLO a cause
    iscritte a ruolo prima del 28/02/2023 (data di entrata in vigore della Riforma Cartabia
    D.Lgs. 149/2022, art. 35 co. 1). Per le cause successive le memorie sono a ritroso ex art.
    171-ter e gli atti per la decisione ex art. 189; l'art. 190 è abrogato.
    Precisione: ESATTO (termini di legge a decorrere dall'udienza; sospensione feriale contata
    giorno per giorno; proroga art. 155 c.p.c.).
    Nota: per cause post-28/02/2023 → usa termini_memorie_repliche() o termini_processuali_civili().

    Calcola: I memoria (30gg), II memoria (60gg), III memoria (80gg) dall'udienza ex art. 183;
    comparsa conclusionale (60gg) e replica (80gg) dall'udienza di PC.

    Args:
        data_udienza: Data dell'udienza di trattazione ex art. 183 c.p.c. oppure, per le
                      conclusionali e repliche, data dell'udienza di precisazione conclusioni (YYYY-MM-DD)
        sospensione_feriale: Applica la sospensione feriale 1-31 agosto ex L. 742/1969 (default
                             True; False per le materie escluse dall'art. 3 L. 742/1969)
    """
    err = _validate_date(data_udienza)
    if err:
        return err
    dt_udienza = _parse_date(data_udienza)

    def _avanti(giorni: int) -> tuple[date, bool, bool]:
        raw, incisa = _conta_avanti(dt_udienza, giorni, sospensione_feriale)
        scad, adj = _slide_forward(raw)
        return scad, adj, incisa

    voci = (
        ("memoria_183_n1", "Art. 183, co. 6, n. 1 — precisazione/modificazione domande, eccezioni, conclusioni", 30, "giorni_da_udienza"),
        ("memoria_183_n2", "Art. 183, co. 6, n. 2 — replica e prova diretta", 60, "giorni_da_udienza"),
        ("memoria_183_n3", "Art. 183, co. 6, n. 3 — indicazione prova contraria", 80, "giorni_da_udienza"),
        ("comparsa_conclusionale", "Comparsa conclusionale art. 190 c.p.c. (testo previgente)", 60, "giorni_da_udienza_pc"),
        ("memoria_replica_190", "Memoria di replica art. 190 c.p.c. (testo previgente)", 80, "giorni_da_udienza_pc"),
    )
    scadenze = []
    incisa_totale = False
    for nome, descrizione, giorni, chiave in voci:
        scad, adj, incisa = _avanti(giorni)
        incisa_totale = incisa_totale or incisa
        scadenze.append({
            "termine": nome,
            "descrizione": descrizione,
            "scadenza": scad.isoformat(),
            chiave: giorni,
            "prorogata_art_155": adj,
            "giorno_settimana": scad.strftime("%A"),
        })

    riferimento = "Artt. 183, co. 6 e 190 c.p.c. (testo previgente)" + (
        f"; {_RIF_FERIALE}" if sospensione_feriale else ""
    )
    return {
        "data_udienza": data_udienza,
        "rito": "ordinario pre-Cartabia (ante 28/02/2023)",
        "riferimento_normativo": riferimento,
        "sospensione_feriale_applicata": sospensione_feriale,
        "sospensione_feriale_incidente": incisa_totale,
        "scadenze": scadenze,
        "nota": "Applicabile solo a cause iscritte a ruolo prima del 28/02/2023. Le memorie 183 decorrono dall'udienza di trattazione; conclusionali e repliche dall'udienza di PC.",
    }


@mcp.tool(tags={"scadenze"})
@sourced("festivita")
def termini_esecuzioni(
    data_notifica_titolo: str,
    tipo: str = "pignoramento_mobiliare",
) -> dict:
    """Calcola i termini nelle procedure esecutive civili (pignoramento, opposizione).
    Vigenza: artt. 480-482, 543, 555, 617 c.p.c. (testo vigente).
    Precisione: ESATTO (termini di legge; proroga art. 155 c.p.c.). La sospensione feriale non viene
    applicata: le opposizioni esecutive sono escluse dall'art. 3 L. 742/1969.

    Args:
        data_notifica_titolo: Data di notifica del precetto al debitore (YYYY-MM-DD)
        tipo: Tipo di procedura: 'pignoramento_mobiliare', 'pignoramento_immobiliare',
              'pignoramento_presso_terzi' (tutti: minimo 10gg e max 90gg dall'efficacia del precetto),
              'opposizione_esecuzione' (20gg per opposizione agli atti esecutivi ex art. 617 c.p.c.)
    """
    err = _validate_date(data_notifica_titolo)
    if err:
        return err
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
            "descrizione": "Opposizione agli atti esecutivi (art. 617 c.p.c.) — 20 giorni dalla notifica del precetto per i vizi di forma del titolo o del precetto",
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


@mcp.tool(tags={"scadenze"})
@sourced("festivita")
def termini_deposito_atti_appello(
    data_notifica_sentenza: str | None = None,
    data_pubblicazione: str | None = None,
    data_notifica_citazione: str | None = None,
    data_udienza: str | None = None,
    sospensione_feriale: bool = True,
) -> dict:
    """Calcola i termini del giudizio di appello civile: impugnazione (breve e lungo), costituzione
    dell'appellante e comparsa di risposta dell'appellato.
    Vigenza: artt. 325-327 c.p.c. (termini di impugnazione, invariati); artt. 347, 165 e 166 c.p.c.
    nel testo del D.Lgs. 149/2022 (dal 28/02/2023): l'appellante si costituisce entro 10 giorni
    dalla notifica della citazione (art. 165 via art. 347) e l'appellato almeno 70 giorni prima
    dell'udienza (art. 166 via art. 347), proponendo nella comparsa l'appello incidentale a pena di
    decadenza (art. 343). Per le cause ante 28/02/2023 la comparsa dell'appellato era dovuta 20
    giorni prima dell'udienza (art. 166 previgente).
    Precisione: ESATTO (termini di legge; sospensione feriale contata giorno per giorno; proroga o
    anticipazione art. 155 c.p.c.).

    Args:
        data_notifica_sentenza: Data di notifica della sentenza per il termine breve (YYYY-MM-DD), opzionale
        data_pubblicazione: Data di pubblicazione della sentenza per il termine lungo (YYYY-MM-DD), opzionale
        data_notifica_citazione: Data di notifica della citazione in appello, per la costituzione
                                 dell'appellante entro 10 giorni (YYYY-MM-DD), opzionale
        data_udienza: Data dell'udienza di comparizione indicata nella citazione in appello, per la
                      comparsa di risposta dell'appellato 70 giorni prima (YYYY-MM-DD), opzionale
        sospensione_feriale: Applica la sospensione feriale 1-31 agosto ex L. 742/1969 (default
                             True; False per le materie escluse dall'art. 3 L. 742/1969)
    """
    if not any((data_notifica_sentenza, data_pubblicazione, data_notifica_citazione, data_udienza)):
        return {
            "errore": (
                "Specificare almeno una data tra data_notifica_sentenza, data_pubblicazione, "
                "data_notifica_citazione e data_udienza"
            ),
        }
    for valore in (data_notifica_sentenza, data_pubblicazione, data_notifica_citazione, data_udienza):
        if valore:
            err = _validate_date(valore)
            if err:
                return err

    riferimento = "Artt. 325, 327, 347, 165, 166 e 343 c.p.c." + (
        f"; {_RIF_FERIALE}" if sospensione_feriale else ""
    )
    result = {
        "riferimento_normativo": riferimento,
        "sospensione_feriale_applicata": sospensione_feriale,
        "termini": [],
    }
    incisa_totale = False

    if data_notifica_sentenza:
        dt_notifica = _parse_date(data_notifica_sentenza)
        scad_raw, incisa = _conta_avanti(dt_notifica, 30, sospensione_feriale)
        incisa_totale = incisa_totale or incisa
        scad_breve, adj_breve = _slide_forward(scad_raw)
        result["termini"].append({
            "termine": "appello_termine_breve",
            "descrizione": "Termine breve per proporre appello dalla notifica della sentenza",
            "giorni": 30,
            "decorrenza": data_notifica_sentenza,
            **_voce_scadenza(scad_breve, adj_breve),
            "normativa": "Art. 325, co. 1 c.p.c.",
        })

    if data_pubblicazione:
        dt_pub = _parse_date(data_pubblicazione)
        scad_raw, incisa = _mesi_avanti(dt_pub, 6, sospensione_feriale)
        incisa_totale = incisa_totale or incisa
        scad_lungo, adj_lungo = _slide_forward(scad_raw)
        result["termini"].append({
            "termine": "appello_termine_lungo",
            "descrizione": "Termine lungo per proporre appello dalla pubblicazione della sentenza",
            "mesi": 6,
            "decorrenza": data_pubblicazione,
            **_voce_scadenza(scad_lungo, adj_lungo),
            "normativa": "Art. 327 c.p.c.",
        })

    voce_costituzione = {
        "termine": "costituzione_appellante",
        "descrizione": "Costituzione dell'appellante (iscrizione a ruolo) entro 10 giorni dalla notifica della citazione in appello",
        "giorni": 10,
        "normativa": "Art. 165 c.p.c. (via art. 347); improcedibilità ex art. 348 se omessa",
    }
    if data_notifica_citazione:
        dt_cit = _parse_date(data_notifica_citazione)
        scad_raw, incisa = _conta_avanti(dt_cit, 10, sospensione_feriale)
        incisa_totale = incisa_totale or incisa
        scad, adj = _slide_forward(scad_raw)
        voce_costituzione.update({"decorrenza": data_notifica_citazione, **_voce_scadenza(scad, adj)})
    else:
        voce_costituzione["nota"] = "Decorre dalla notifica della citazione in appello: passare data_notifica_citazione per il calcolo"
    result["termini"].append(voce_costituzione)

    voce_appellato = {
        "termine": "comparsa_risposta_appellato",
        "descrizione": "Costituzione dell'appellato con comparsa di risposta almeno 70 giorni prima dell'udienza (appello incidentale a pena di decadenza)",
        "giorni_prima_udienza": 70,
        "normativa": "Artt. 166 e 343 c.p.c. (via art. 347) — testo D.Lgs. 149/2022; 20 giorni per le cause ante 28/02/2023",
    }
    if data_udienza:
        dt_ud = _parse_date(data_udienza)
        scad_raw, incisa = _conta_ritroso(dt_ud, 70, sospensione_feriale)
        incisa_totale = incisa_totale or incisa
        scad, adj = _slide_backward(scad_raw)
        voce_appellato.update({"udienza": data_udienza, **_voce_scadenza(scad, adj)})
    else:
        voce_appellato["nota"] = "Termine a ritroso dall'udienza fissata: passare data_udienza per il calcolo"
    result["termini"].append(voce_appellato)

    result["sospensione_feriale_incidente"] = incisa_totale
    return result


@mcp.tool(tags={"scadenze"})
@sourced("festivita")
def termini_deposito_ctu(
    data_conferimento: str,
    giorni_termine: int = 60,
    giorni_osservazioni: int = 15,
    giorni_replica: int = 15,
    sospensione_feriale: bool = True,
) -> dict:
    """Calcola le scadenze per il deposito della relazione CTU e le osservazioni delle parti.
    Vigenza: art. 195 co. 3 c.p.c. (testo post-Cartabia — D.Lgs. 149/2022): i tre termini (invio
    della bozza alle parti, osservazioni delle parti, deposito della relazione definitiva con la
    valutazione delle osservazioni) sono fissati dal giudice con l'ordinanza ex art. 193, non dalla
    legge; i 60/15/15 giorni di default sono la prassi più diffusa.
    Precisione: ESATTO (aritmetica sui giorni assegnati dal giudice, che vanno passati come
    parametri; sospensione feriale contata giorno per giorno; proroga art. 155 c.p.c.).

    Args:
        data_conferimento: Data del conferimento dell'incarico al CTU da parte del giudice (YYYY-MM-DD)
        giorni_termine: Giorni assegnati al CTU per trasmettere la bozza alle parti (default 60)
        giorni_osservazioni: Giorni assegnati alle parti per le osservazioni (default 15)
        giorni_replica: Giorni assegnati al CTU per il deposito definitivo con la valutazione delle
                        osservazioni (default 15)
        sospensione_feriale: Applica la sospensione feriale 1-31 agosto ex L. 742/1969 (default
                             True; False per le materie escluse dall'art. 3 L. 742/1969)
    """
    err = _validate_date(data_conferimento)
    if err:
        return err
    for nome, valore in (
        ("giorni_termine", giorni_termine),
        ("giorni_osservazioni", giorni_osservazioni),
        ("giorni_replica", giorni_replica),
    ):
        if not isinstance(valore, int) or valore < 1:
            return {"errore": f"{nome} deve essere un intero positivo"}
    dt_conf = _parse_date(data_conferimento)

    deposito_raw, incisa_1 = _conta_avanti(dt_conf, giorni_termine, sospensione_feriale)
    deposito, deposito_adj = _slide_forward(deposito_raw)
    oss_raw, incisa_2 = _conta_avanti(deposito_raw, giorni_osservazioni, sospensione_feriale)
    oss, oss_adj = _slide_forward(oss_raw)
    replica_raw, incisa_3 = _conta_avanti(oss_raw, giorni_replica, sospensione_feriale)
    replica, replica_adj = _slide_forward(replica_raw)

    riferimento = "Art. 195, co. 3 c.p.c." + (f"; {_RIF_FERIALE}" if sospensione_feriale else "")
    return {
        "data_conferimento": data_conferimento,
        "giorni_termine_ctu": giorni_termine,
        "riferimento_normativo": riferimento,
        "sospensione_feriale_applicata": sospensione_feriale,
        "sospensione_feriale_incidente": incisa_1 or incisa_2 or incisa_3,
        "scadenze": [
            {
                "termine": "deposito_bozza_ctu",
                "descrizione": "Trasmissione della bozza di relazione alle parti",
                "giorni_da_conferimento": giorni_termine,
                **_voce_scadenza(deposito, deposito_adj),
            },
            {
                "termine": "osservazioni_parti",
                "descrizione": "Termine per le osservazioni delle parti alla bozza CTU",
                "giorni_da_deposito_ctu": giorni_osservazioni,
                **_voce_scadenza(oss, oss_adj),
            },
            {
                "termine": "replica_ctu",
                "descrizione": "Deposito della relazione definitiva con le osservazioni delle parti e la sintetica valutazione del CTU",
                "giorni_da_osservazioni": giorni_replica,
                **_voce_scadenza(replica, replica_adj),
            },
        ],
        "nota": (
            "I termini sono quelli fissati dal giudice nell'ordinanza ex art. 193 c.p.c.: "
            "passare i giorni effettivamente assegnati. Il deposito definitivo deve comunque "
            "precedere l'udienza successiva (art. 195 co. 3)."
        ),
    }
