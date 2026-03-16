"""Utilità generali: codice fiscale (DM 12/03/1974), IBAN, conteggio giorni lavorativi,
prescrizione diritti civili, tasso alcolemico (art. 186 CdS), ATECO, scorporo IVA."""

import json
from datetime import date, timedelta
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "comuni.json") as f:
    _COMUNI_DATA = json.load(f)
    _COMUNI = _COMUNI_DATA["comuni"]
    _STATI_ESTERI = _COMUNI_DATA["stati_esteri"]

with open(_DATA / "festivita.json") as f:
    _FESTIVITA = json.load(f)["fisse"]

with open(_DATA / "codici_ateco.json") as f:
    _ATECO = json.load(f)

with open(_DATA / "violazioni_patente.json") as f:
    _VIOLAZIONI = json.load(f)


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


# --- Codice Fiscale helpers ---

_MESE_CF = {
    1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "H",
    7: "L", 8: "M", 9: "P", 10: "R", 11: "S", 12: "T",
}

_MESE_CF_INV = {v: k for k, v in _MESE_CF.items()}

_ODD_MAP = {
    "0": 1, "1": 0, "2": 5, "3": 7, "4": 9, "5": 13, "6": 15, "7": 17, "8": 19, "9": 21,
    "A": 1, "B": 0, "C": 5, "D": 7, "E": 9, "F": 13, "G": 15, "H": 17, "I": 19, "J": 21,
    "K": 2, "L": 4, "M": 18, "N": 20, "O": 11, "P": 3, "Q": 6, "R": 8, "S": 12, "T": 14,
    "U": 16, "V": 10, "W": 22, "X": 25, "Y": 24, "Z": 23,
}

_EVEN_MAP = {
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7, "I": 8, "J": 9,
    "K": 10, "L": 11, "M": 12, "N": 13, "O": 14, "P": 15, "Q": 16, "R": 17, "S": 18, "T": 19,
    "U": 20, "V": 21, "W": 22, "X": 23, "Y": 24, "Z": 25,
}


def _extract_consonants(s: str) -> str:
    return "".join(c for c in s.upper() if c.isalpha() and c not in "AEIOU")


def _extract_vowels(s: str) -> str:
    return "".join(c for c in s.upper() if c in "AEIOU")


def _cf_cognome(cognome: str) -> str:
    cons = _extract_consonants(cognome)
    vow = _extract_vowels(cognome)
    code = (cons + vow + "XXX")[:3]
    return code


def _cf_nome(nome: str) -> str:
    cons = _extract_consonants(nome)
    if len(cons) >= 4:
        code = cons[0] + cons[2] + cons[3]
    else:
        vow = _extract_vowels(nome)
        code = (cons + vow + "XXX")[:3]
    return code


def _cf_check_char(cf15: str) -> str:
    total = 0
    for i, ch in enumerate(cf15):
        if (i + 1) % 2 == 1:  # odd position (1-indexed)
            total += _ODD_MAP[ch]
        else:
            total += _EVEN_MAP[ch]
    return chr(ord("A") + (total % 26))


def _lookup_codice_catastale(comune: str) -> str | None:
    comune_up = comune.upper().strip()
    code = _COMUNI.get(comune_up)
    if code:
        return code
    return _STATI_ESTERI.get(comune_up)


@mcp.tool(tags={"utility"})
def codice_fiscale(
    cognome: str,
    nome: str,
    data_nascita: str,
    sesso: str,
    comune_nascita: str,
) -> dict:
    """Genera il codice fiscale italiano a 16 caratteri secondo l'algoritmo ufficiale.

    Vigenza: DM 12/03/1974 — Agenzia delle Entrate; database comuni e stati esteri aggiornato.
    Precisione: ESATTO (algoritmo ufficiale con carattere di controllo); possibile omonimia non gestita (codice jolly).

    Args:
        cognome: Cognome della persona (anche composto)
        nome: Nome della persona (anche composto)
        data_nascita: Data di nascita (formato YYYY-MM-DD)
        sesso: Sesso della persona: 'M' o 'F'
        comune_nascita: Nome del comune italiano o dello stato estero di nascita (es. 'ROMA', 'GERMANIA')
    """
    sesso = sesso.upper().strip()
    if sesso not in ("M", "F"):
        return {"errore": "sesso deve essere 'M' o 'F'"}

    try:
        dt = _parse_date(data_nascita)
    except ValueError:
        return {"errore": "data_nascita non valida, usare formato YYYY-MM-DD"}

    catastale = _lookup_codice_catastale(comune_nascita)
    if not catastale:
        return {"errore": f"Comune o stato estero '{comune_nascita}' non trovato nel database"}

    part_cognome = _cf_cognome(cognome)
    part_nome = _cf_nome(nome)
    part_anno = f"{dt.year % 100:02d}"
    part_mese = _MESE_CF[dt.month]
    giorno = dt.day if sesso == "M" else dt.day + 40
    part_giorno = f"{giorno:02d}"

    cf15 = part_cognome + part_nome + part_anno + part_mese + part_giorno + catastale
    check = _cf_check_char(cf15)

    return {
        "codice_fiscale": cf15 + check,
        "dettaglio": {
            "cognome": part_cognome,
            "nome": part_nome,
            "anno": part_anno,
            "mese": part_mese,
            "giorno": part_giorno,
            "codice_catastale": catastale,
            "carattere_controllo": check,
        },
    }


@mcp.tool(tags={"utility"})
def decodifica_codice_fiscale(codice_fiscale: str) -> dict:
    """Decodifica un codice fiscale italiano a 16 caratteri estraendo i dati anagrafici.

    Nota: l'anno di nascita è stimato (ambiguità di secolo); i caratteri cognome/nome non sono reversibili.
    Vigenza: DM 12/03/1974 — Agenzia delle Entrate.
    Precisione: ESATTO per validità formale (carattere controllo); INDICATIVO per anno di nascita (stima 1900/2000).

    Args:
        codice_fiscale: Codice fiscale di 16 caratteri (lettere e cifre, spazi ignorati)
    """
    cf = codice_fiscale.upper().strip()
    if len(cf) != 16:
        return {"errore": "Il codice fiscale deve essere di 16 caratteri"}

    # Validate check character
    expected_check = _cf_check_char(cf[:15])
    check_valido = cf[15] == expected_check

    # Extract year
    anno_part = cf[6:8]
    anno = int(anno_part)
    # Heuristic: 00-29 -> 2000s, 30-99 -> 1900s
    anno_completo = 2000 + anno if anno <= 29 else 1900 + anno

    # Month
    mese_char = cf[8]
    mese = _MESE_CF_INV.get(mese_char)
    if not mese:
        return {"errore": f"Carattere mese '{mese_char}' non valido"}

    # Day and sex
    giorno_raw = int(cf[9:11])
    if giorno_raw > 40:
        sesso = "F"
        giorno = giorno_raw - 40
    else:
        sesso = "M"
        giorno = giorno_raw

    # Date
    try:
        data_nascita = date(anno_completo, mese, giorno)
    except ValueError:
        return {"errore": "Data di nascita non valida nel codice fiscale"}

    # Comune lookup (reverse)
    codice_catastale = cf[11:15]
    comune = None
    for nome, cod in _COMUNI.items():
        if cod == codice_catastale:
            comune = nome
            break
    if not comune:
        for nome, cod in _STATI_ESTERI.items():
            if cod == codice_catastale:
                comune = nome + " (stato estero)"
                break

    return {
        "codice_fiscale": cf,
        "carattere_controllo_valido": check_valido,
        "dati": {
            "sesso": sesso,
            "data_nascita": data_nascita.isoformat(),
            "anno_nascita_stimato": anno_completo,
            "comune_nascita": comune or f"Codice catastale {codice_catastale} (non trovato nel database)",
            "codice_catastale": codice_catastale,
        },
        "nota": "L'anno di nascita è stimato (ambiguità secolo). I caratteri cognome/nome non sono reversibili.",
    }


@mcp.tool(tags={"utility"})
def verifica_iban(iban: str) -> dict:
    """Valida un IBAN italiano (27 caratteri) ed estrae le componenti ABI, CAB e conto.

    Esegue la verifica formale tramite algoritmo ISO 7064 mod 97. Non verifica l'esistenza del conto.
    Vigenza: ISO 13616 — standard IBAN; formato IT: 27 caratteri.
    Precisione: ESATTO per validità formale algoritmica; non verifica esistenza del conto in banca.

    Args:
        iban: Codice IBAN italiano da verificare (27 caratteri; spazi e trattini ignorati)
    """
    iban_clean = iban.upper().replace(" ", "").replace("-", "")

    errori = []
    if len(iban_clean) != 27:
        errori.append(f"Lunghezza {len(iban_clean)} invece di 27")
    if not iban_clean[:2] == "IT":
        errori.append("Non inizia con 'IT'")

    if errori:
        return {"valido": False, "errori": errori}

    # Extract components
    paese = iban_clean[0:2]
    check_digits = iban_clean[2:4]
    cin = iban_clean[4]
    abi = iban_clean[5:10]
    cab = iban_clean[10:15]
    conto = iban_clean[15:27]

    # ISO 7064 mod 97 validation
    rearranged = iban_clean[4:] + iban_clean[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        else:
            numeric += str(ord(ch) - ord("A") + 10)
    valido = int(numeric) % 97 == 1

    return {
        "iban": iban_clean,
        "valido": valido,
        "componenti": {
            "paese": paese,
            "check_digits": check_digits,
            "cin": cin,
            "abi": abi,
            "cab": cab,
            "conto_corrente": conto,
        },
    }


# --- Giorni helpers ---

def _easter(year: int) -> date:
    """Computus algorithm for Easter Sunday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _get_holidays(year: int) -> dict[date, str]:
    """Return all Italian holidays for a given year."""
    holidays = {}
    for f in _FESTIVITA:
        if f.get("dal_anno") and year < f["dal_anno"]:
            continue
        holidays[date(year, f["mese"], f["giorno"])] = f["nome"]
    pasqua = _easter(year)
    holidays[pasqua] = "Pasqua"
    holidays[pasqua + timedelta(days=1)] = "Lunedì dell'Angelo"
    return holidays


@mcp.tool(tags={"utility"})
def conta_giorni(
    data_inizio: str,
    data_fine: str,
    tipo: str = "calendario",
) -> dict:
    """Conta i giorni tra due date per tipo: calendario, lavorativi (escl. weekend e festivi italiani) o festivi.

    Include tutte le festività nazionali italiane fisse e mobili (Pasqua). Applica
    la regola "dies a quo non computatur" (il giorno iniziale non è conteggiato).
    Vigenza: Festività nazionali italiane vigenti (L. 260/1949 e ss.).
    Precisione: ESATTO (calcolo matematico su calendario italiano ufficiale).

    Args:
        data_inizio: Data di inizio del periodo (formato YYYY-MM-DD)
        data_fine: Data di fine del periodo (formato YYYY-MM-DD)
        tipo: Tipo di conteggio: 'calendario' (tutti i giorni), 'lavorativi' (esclusi weekend e festivi), 'festivi' (solo giorni festivi nel periodo)
    """
    dt_inizio = _parse_date(data_inizio)
    dt_fine = _parse_date(data_fine)

    if dt_fine < dt_inizio:
        return {"errore": "data_fine deve essere uguale o successiva a data_inizio"}

    if tipo not in ("calendario", "lavorativi", "festivi"):
        return {"errore": "tipo deve essere 'calendario', 'lavorativi' o 'festivi'"}

    # Collect holidays for all years in range
    holidays = {}
    for year in range(dt_inizio.year, dt_fine.year + 1):
        holidays.update(_get_holidays(year))

    giorni_totali = (dt_fine - dt_inizio).days
    festivita_nel_periodo = []
    count = 0
    current = dt_inizio + timedelta(days=1)  # dies a quo non computatur

    while current <= dt_fine:
        is_weekend = current.weekday() >= 5
        is_holiday = current in holidays

        if is_holiday:
            festivita_nel_periodo.append({
                "data": current.isoformat(),
                "nome": holidays[current],
                "giorno_settimana": ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"][current.weekday()],
            })

        if tipo == "calendario":
            count += 1
        elif tipo == "lavorativi":
            if not is_weekend and not is_holiday:
                count += 1
        elif tipo == "festivi":
            if is_holiday:
                count += 1

        current += timedelta(days=1)

    return {
        "data_inizio": data_inizio,
        "data_fine": data_fine,
        "tipo": tipo,
        "giorni": count,
        "giorni_calendario_totali": giorni_totali,
        "festivita_nel_periodo": festivita_nel_periodo,
    }


@mcp.tool(tags={"utility"})
def scorporo_iva(
    importo_ivato: float,
    aliquota: float = 22,
) -> dict:
    """Scorporo dell'IVA da un importo ivato: ricava imponibile e IVA separati.

    Vigenza: DPR 633/1972 — aliquote IVA vigenti: 4% (beni prima necessità), 5% (alcuni servizi), 10% (ridotta), 22% (ordinaria).
    Precisione: ESATTO (formula matematica: imponibile = importo_ivato / (1 + aliquota/100)).

    Args:
        importo_ivato: Importo comprensivo di IVA in euro (€)
        aliquota: Aliquota IVA in percentuale: 4, 5, 10 o 22
    """
    aliquote_valide = (4, 5, 10, 22)
    if aliquota not in aliquote_valide:
        return {"errore": f"Aliquota deve essere una tra {aliquote_valide}"}

    imponibile = importo_ivato / (1 + aliquota / 100)
    iva = importo_ivato - imponibile

    return {
        "importo_ivato": importo_ivato,
        "aliquota_pct": aliquota,
        "imponibile": round(imponibile, 2),
        "iva": round(iva, 2),
        "verifica": round(imponibile + iva, 2),
    }


@mcp.tool(tags={"utility"})
def decurtazione_punti_patente(violazione: str) -> dict:
    """Restituisce punti decurtati, sanzione pecuniaria e sospensione patente per violazione CdS.

    Accetta parola chiave e restituisce tutte le violazioni corrispondenti con i relativi punti decurtati.
    Vigenza: D.Lgs. 285/1992 (Codice della Strada) — aggiornato al D.Lgs. 36/2023 (Riforma CdS 2023).
    Precisione: ESATTO per violazioni presenti nel database; verificare aggiornamenti per riforme recenti.

    Args:
        violazione: Parola chiave della violazione (es. 'cellulare', 'cintura', 'semaforo_rosso', 'eccesso_velocita_10', 'guida_ebbra', 'sorpasso_divieto')
    """
    violazione_lower = violazione.lower().strip()

    # Exact match
    if violazione_lower in _VIOLAZIONI:
        v = _VIOLAZIONI[violazione_lower]
        return {"violazione": violazione_lower, **v}

    # Keyword search
    risultati = []
    for key, v in _VIOLAZIONI.items():
        if violazione_lower in key or violazione_lower in v["descrizione"].lower():
            risultati.append({"violazione": key, **v})

    if risultati:
        return {"ricerca": violazione, "risultati": risultati}

    return {
        "errore": f"Violazione '{violazione}' non trovata",
        "violazioni_disponibili": sorted(_VIOLAZIONI.keys()),
    }


@mcp.tool(tags={"utility"})
def tasso_alcolemico(
    sesso: str,
    peso_kg: float,
    unita_alcoliche: float,
    ore_trascorse: float,
    stomaco_pieno: bool = False,
) -> dict:
    """Calcola il tasso alcolemico teorico con la formula di Widmark e indica la fascia sanzionatoria CdS.

    Calcolo puramente indicativo: il tasso reale varia per metabolismo, farmaci e condizioni fisiche.
    Per la guida: lecito sotto 0,5 g/l (0,0 g/l per neopatentati e guidatori professionali).
    Vigenza: Art. 186 D.Lgs. 285/1992 (Codice della Strada) — soglie vigenti: 0.5 g/l (lett. a), 0.8 g/l (lett. b), 1.5 g/l (lett. c).
    Precisione: INDICATIVO (formula di Widmark è una stima teorica; il tasso reale misurato può differire significativamente).

    Args:
        sesso: Sesso della persona: 'M' o 'F' (influenza il coefficiente di Widmark: 0.70 M, 0.60 F)
        peso_kg: Peso corporeo in kg (es. 70; range realistico: 40-200)
        unita_alcoliche: Numero di unità alcoliche consumate (1 UA = 12g alcol = 1 birra 33cl o 1 bicchiere vino 12cl)
        ore_trascorse: Ore trascorse dall'inizio dell'assunzione (es. 2.5)
        stomaco_pieno: True se il consumo è avvenuto durante un pasto completo (riduce assorbimento del ~30%)
    """
    sesso = sesso.upper().strip()
    if sesso not in ("M", "F"):
        return {"errore": "sesso deve essere 'M' o 'F'"}
    if peso_kg <= 0 or unita_alcoliche < 0:
        return {"errore": "peso_kg e unita_alcoliche devono essere positivi"}

    GRAMMI_PER_UA = 12
    COEFF_WIDMARK = 0.70 if sesso == "M" else 0.60
    METABOLIZZAZIONE = 0.15  # g/l per ora

    alcol_grammi = unita_alcoliche * GRAMMI_PER_UA
    if stomaco_pieno:
        alcol_grammi *= 0.70  # riduzione 30%

    tasso_picco = alcol_grammi / (peso_kg * COEFF_WIDMARK)
    tasso_attuale = max(tasso_picco - (METABOLIZZAZIONE * ore_trascorse), 0)
    tasso_attuale = round(tasso_attuale, 2)

    # Tempo per smaltimento completo
    ore_smaltimento = round(tasso_picco / METABOLIZZAZIONE, 1) if tasso_picco > 0 else 0
    ore_residue = round(max(ore_smaltimento - ore_trascorse, 0), 1)

    # Fascia sanzionatoria
    if tasso_attuale == 0:
        fascia = "nessuna (tasso 0)"
        sanzione = None
    elif tasso_attuale < 0.5:
        fascia = "nessuna (< 0.5 g/l)"
        sanzione = None
    elif tasso_attuale < 0.8:
        fascia = "art. 186 co. 2 lett. a)"
        sanzione = "Ammenda 500-2000€, sospensione patente 3-6 mesi"
    elif tasso_attuale < 1.5:
        fascia = "art. 186 co. 2 lett. b)"
        sanzione = "Ammenda 800-3200€, arresto fino a 6 mesi, sospensione patente 6-12 mesi"
    else:
        fascia = "art. 186 co. 2 lett. c)"
        sanzione = "Ammenda 1500-6000€, arresto 6-12 mesi, sospensione patente 1-2 anni, confisca veicolo"

    return {
        "sesso": sesso,
        "peso_kg": peso_kg,
        "unita_alcoliche": unita_alcoliche,
        "ore_trascorse": ore_trascorse,
        "stomaco_pieno": stomaco_pieno,
        "alcol_assorbito_grammi": round(alcol_grammi, 1),
        "tasso_picco_g_l": round(tasso_picco, 2),
        "tasso_attuale_g_l": tasso_attuale,
        "ore_smaltimento_totale": ore_smaltimento,
        "ore_residue_smaltimento": ore_residue,
        "fascia_sanzione_cds": fascia,
        "sanzione": sanzione,
        "avvertenza": "Calcolo puramente indicativo basato su formula di Widmark. Il tasso reale dipende da metabolismo individuale, farmaci, condizioni fisiche.",
        "riferimento_normativo": "Art. 186 D.Lgs. 285/1992 (Codice della Strada)",
    }


@mcp.tool(tags={"utility"})
def prescrizione_diritti(
    tipo_diritto: str,
    data_evento: str,
) -> dict:
    """Calcola la data di prescrizione di un diritto civile e verifica se è già prescritto.

    Non applicabile a diritti imprescrittibili (es. stato di famiglia, diritti della personalità).
    I termini possono essere sospesi o interrotti da atti specifici (diffida, citazione, riconoscimento debito).
    Vigenza: Termini ex c.c.: art. 2946 (ordinaria 10a), 2947 (danni 5a/RCA 2a), 2948 (lavoro 5a),
    2956 (professionisti 3a), 1495 (vizi vendita 1a), 1667 (appalto 2a); L. 335/1995 (previdenza 5a).
    Precisione: INDICATIVO (sospensioni e interruzioni non sono calcolate automaticamente).

    Args:
        tipo_diritto: Tipo di diritto: 'ordinaria' (10a), 'risarcimento_danni' (5a), 'risarcimento_rca' (2a), 'diritti_lavoro' (5a), 'crediti_professionisti' (3a), 'canoni_locazione' (5a), 'contributi_previdenziali' (5a), 'vizi_vendita' (1a), 'garanzia_appalto' (2a)
        data_evento: Data del fatto generatore del diritto (formato YYYY-MM-DD)
    """
    _TERMINI = {
        "ordinaria": {"anni": 10, "norma": "Art. 2946 c.c."},
        "risarcimento_danni": {"anni": 5, "norma": "Art. 2947 c.c."},
        "risarcimento_rca": {"anni": 2, "norma": "Art. 2947, comma 2, c.c."},
        "diritti_lavoro": {"anni": 5, "norma": "Art. 2948 c.c."},
        "crediti_professionisti": {"anni": 3, "norma": "Art. 2956 c.c."},
        "canoni_locazione": {"anni": 5, "norma": "Art. 2948, n. 3, c.c."},
        "contributi_previdenziali": {"anni": 5, "norma": "Art. 3, comma 9, L. 335/1995"},
        "vizi_vendita": {"anni": 1, "norma": "Art. 1495 c.c."},
        "garanzia_appalto": {"anni": 2, "norma": "Art. 1667 c.c."},
    }

    if tipo_diritto not in _TERMINI:
        return {"errore": f"tipo_diritto deve essere uno tra: {', '.join(sorted(_TERMINI.keys()))}"}

    try:
        dt_evento = _parse_date(data_evento)
    except ValueError:
        return {"errore": "data_evento non valida, usare formato YYYY-MM-DD"}

    termine = _TERMINI[tipo_diritto]
    anni = termine["anni"]
    try:
        data_prescrizione = date(dt_evento.year + anni, dt_evento.month, dt_evento.day)
    except ValueError:
        data_prescrizione = date(dt_evento.year + anni, dt_evento.month, 28)
    oggi = date.today()
    prescritto = oggi > data_prescrizione
    giorni_mancanti = (data_prescrizione - oggi).days if not prescritto else 0

    return {
        "tipo_diritto": tipo_diritto,
        "data_evento": data_evento,
        "termine_anni": anni,
        "data_prescrizione": data_prescrizione.isoformat(),
        "prescritto": prescritto,
        "giorni_mancanti": giorni_mancanti,
        "nota": "I termini possono essere sospesi o interrotti da atti specifici (diffida, citazione, riconoscimento del debito).",
        "riferimento_normativo": termine["norma"],
    }


@mcp.tool(tags={"utility"})
def calcolo_tempo_trascorso(
    data_inizio: str,
    data_fine: str | None = None,
) -> dict:
    """Calcola il tempo trascorso tra due date espresso in anni, mesi e giorni.

    Utile per calcolare anzianità lavorativa, durata contratti, età al fatto, termini processuali.
    Precisione: ESATTO (calcolo calendario esatto con gestione anni bisestili).

    Args:
        data_inizio: Data di inizio del periodo (formato YYYY-MM-DD)
        data_fine: Data di fine del periodo (formato YYYY-MM-DD); se omessa usa la data odierna
    """
    try:
        dt_inizio = _parse_date(data_inizio)
    except ValueError:
        return {"errore": "data_inizio non valida, usare formato YYYY-MM-DD"}

    if data_fine:
        try:
            dt_fine = _parse_date(data_fine)
        except ValueError:
            return {"errore": "data_fine non valida, usare formato YYYY-MM-DD"}
    else:
        dt_fine = date.today()

    if dt_fine < dt_inizio:
        return {"errore": "data_fine deve essere uguale o successiva a data_inizio"}

    # Calculate years, months, days
    anni = dt_fine.year - dt_inizio.year
    mesi = dt_fine.month - dt_inizio.month
    giorni = dt_fine.day - dt_inizio.day

    if giorni < 0:
        mesi -= 1
        # Days in previous month
        prev_month = dt_fine.month - 1 if dt_fine.month > 1 else 12
        prev_year = dt_fine.year if dt_fine.month > 1 else dt_fine.year - 1
        if prev_month in (1, 3, 5, 7, 8, 10, 12):
            days_prev = 31
        elif prev_month in (4, 6, 9, 11):
            days_prev = 30
        else:
            days_prev = 29 if (prev_year % 4 == 0 and (prev_year % 100 != 0 or prev_year % 400 == 0)) else 28
        giorni += days_prev

    if mesi < 0:
        anni -= 1
        mesi += 12

    giorni_totali = (dt_fine - dt_inizio).days

    return {
        "data_inizio": data_inizio,
        "data_fine": dt_fine.isoformat(),
        "anni": anni,
        "mesi": mesi,
        "giorni": giorni,
        "giorni_totali": giorni_totali,
        "descrizione": f"{anni} anni, {mesi} mesi, {giorni} giorni",
    }


@mcp.tool(tags={"utility"})
def verifica_partita_iva(partita_iva: str) -> dict:
    """Valida formalmente una partita IVA italiana tramite algoritmo di controllo (11 cifre).

    Vigenza: DPR 633/1972 art. 35 — struttura P.IVA italiana; algoritmo di controllo invariato.
    Precisione: ESATTO per validità formale algoritmica; non verifica attivazione effettiva presso Agenzia Entrate.

    Args:
        partita_iva: Numero di partita IVA italiano (11 cifre numeriche)
    """
    piva = partita_iva.strip().replace(" ", "")

    if not piva.isdigit():
        return {"valido": False, "errore": "La partita IVA deve contenere solo cifre"}
    if len(piva) != 11:
        return {"valido": False, "errore": f"La partita IVA deve essere di 11 cifre, trovate {len(piva)}"}

    # Codice provincia (prime 2 cifre per persone fisiche, 3 per soggetti diversi)
    codice_ufficio = piva[:2]

    # Luhn-like algorithm for Italian VAT numbers
    somma = 0
    for i, c in enumerate(piva[:10]):
        digit = int(c)
        if i % 2 == 0:
            # Odd position (1-indexed): add as-is
            somma += digit
        else:
            # Even position: double, subtract 9 if >= 10
            doubled = digit * 2
            somma += doubled if doubled < 10 else doubled - 9

    check_digit = (10 - (somma % 10)) % 10
    valido = check_digit == int(piva[10])

    return {
        "partita_iva": piva,
        "valido": valido,
        "codice_ufficio": codice_ufficio,
        "cifra_controllo_attesa": check_digit,
        "cifra_controllo_presente": int(piva[10]),
    }


@mcp.tool(tags={"utility"})
def calcolo_eta_anagrafica(
    data_nascita: str,
    data_riferimento: str | None = None,
) -> dict:
    """Calcola l'età anagrafica esatta in anni, mesi e giorni con data del prossimo compleanno.

    Utile per verificare maggiore età, capacità d'agire, accesso a prestazioni per fascia d'età.
    Precisione: ESATTO (calcolo calendario esatto con gestione anni bisestili).

    Args:
        data_nascita: Data di nascita della persona (formato YYYY-MM-DD)
        data_riferimento: Data di riferimento per il calcolo (formato YYYY-MM-DD); se omessa usa la data odierna
    """
    try:
        dt_nascita = _parse_date(data_nascita)
    except ValueError:
        return {"errore": "data_nascita non valida, usare formato YYYY-MM-DD"}

    if data_riferimento:
        try:
            dt_rif = _parse_date(data_riferimento)
        except ValueError:
            return {"errore": "data_riferimento non valida, usare formato YYYY-MM-DD"}
    else:
        dt_rif = date.today()

    if dt_rif < dt_nascita:
        return {"errore": "La data di riferimento deve essere successiva alla data di nascita"}

    # Age calculation
    anni = dt_rif.year - dt_nascita.year
    mesi = dt_rif.month - dt_nascita.month
    giorni = dt_rif.day - dt_nascita.day

    if giorni < 0:
        mesi -= 1
        prev_month = dt_rif.month - 1 if dt_rif.month > 1 else 12
        prev_year = dt_rif.year if dt_rif.month > 1 else dt_rif.year - 1
        if prev_month in (1, 3, 5, 7, 8, 10, 12):
            days_prev = 31
        elif prev_month in (4, 6, 9, 11):
            days_prev = 30
        else:
            days_prev = 29 if (prev_year % 4 == 0 and (prev_year % 100 != 0 or prev_year % 400 == 0)) else 28
        giorni += days_prev

    if mesi < 0:
        anni -= 1
        mesi += 12

    # Next birthday
    try:
        prossimo = date(dt_rif.year, dt_nascita.month, dt_nascita.day)
    except ValueError:
        prossimo = date(dt_rif.year, dt_nascita.month, 28)
    if prossimo <= dt_rif:
        try:
            prossimo = date(dt_rif.year + 1, dt_nascita.month, dt_nascita.day)
        except ValueError:
            prossimo = date(dt_rif.year + 1, dt_nascita.month, 28)

    giorni_al_compleanno = (prossimo - dt_rif).days

    return {
        "data_nascita": data_nascita,
        "data_riferimento": dt_rif.isoformat(),
        "eta_anni": anni,
        "eta_mesi": mesi,
        "eta_giorni": giorni,
        "descrizione": f"{anni} anni, {mesi} mesi, {giorni} giorni",
        "prossimo_compleanno": prossimo.isoformat(),
        "giorni_al_compleanno": giorni_al_compleanno,
    }


@mcp.tool(tags={"utility"})
def ricerca_codici_ateco(keyword: str) -> dict:
    """Ricerca codici ATECO per parola chiave, con coefficiente di redditività per il regime forfettario.

    Utile per identificare il codice ATECO corretto e il coefficiente di redditività applicabile
    nel regime forfettario (L. 190/2014) per il calcolo del reddito imponibile.
    Vigenza: Classificazione ATECO 2007 (aggiornata 2022) — Allegato alla L. 190/2014 per coefficienti forfettario.
    Precisione: INDICATIVO (la categoria ATECO corretta va verificata con il proprio consulente fiscale).

    Args:
        keyword: Parola chiave da cercare nell'archivio ATECO (es. 'ristorante', 'avvocato', 'sviluppatore', 'commercio')
    """
    keyword_lower = keyword.lower().strip()
    risultati = []

    for voce in _ATECO:
        if keyword_lower in voce["descrizione"].lower() or keyword_lower in voce["codice"]:
            risultati.append(voce)

    if not risultati:
        return {
            "keyword": keyword,
            "risultati": [],
            "suggerimento": "Prova con termini piu generici (es. 'commercio', 'medic', 'informatica', 'bar', 'ingegn')",
        }

    return {
        "keyword": keyword,
        "n_risultati": len(risultati),
        "risultati": risultati,
        "nota": "Il coefficiente di redditivita e usato nel regime forfettario per determinare il reddito imponibile (ricavi * coefficiente / 100)",
    }
