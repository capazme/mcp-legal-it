"""Sezione 12 — Applicazioni Varie: codice fiscale, IBAN, conteggio giorni, scorporo IVA."""

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


@mcp.tool()
def codice_fiscale(
    cognome: str,
    nome: str,
    data_nascita: str,
    sesso: str,
    comune_nascita: str,
) -> dict:
    """Genera codice fiscale italiano.

    Args:
        cognome: Cognome della persona
        nome: Nome della persona
        data_nascita: Data di nascita (YYYY-MM-DD)
        sesso: 'M' o 'F'
        comune_nascita: Nome del comune (o stato estero) di nascita
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


@mcp.tool()
def decodifica_codice_fiscale(codice_fiscale: str) -> dict:
    """Decodifica un codice fiscale italiano nei dati anagrafici.

    Args:
        codice_fiscale: Codice fiscale di 16 caratteri
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


@mcp.tool()
def verifica_iban(iban: str) -> dict:
    """Validazione IBAN italiano con estrazione componenti.

    Args:
        iban: Codice IBAN da verificare
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
        holidays[date(year, f["mese"], f["giorno"])] = f["nome"]
    pasqua = _easter(year)
    holidays[pasqua] = "Pasqua"
    holidays[pasqua + timedelta(days=1)] = "Lunedì dell'Angelo"
    return holidays


@mcp.tool()
def conta_giorni(
    data_inizio: str,
    data_fine: str,
    tipo: str = "calendario",
) -> dict:
    """Conta giorni tra due date (calendario, lavorativi o festivi).

    Args:
        data_inizio: Data inizio (YYYY-MM-DD)
        data_fine: Data fine (YYYY-MM-DD)
        tipo: 'calendario' (tutti), 'lavorativi' (esclusi weekend e festivi), 'festivi' (solo festivi nel periodo)
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

    giorni_totali = (dt_fine - dt_inizio).days + 1  # inclusive
    festivita_nel_periodo = []
    count = 0
    current = dt_inizio

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


@mcp.tool()
def scorporo_iva(
    importo_ivato: float,
    aliquota: float = 22,
) -> dict:
    """Scorporo IVA da importo ivato.

    Args:
        importo_ivato: Importo comprensivo di IVA in euro
        aliquota: Aliquota IVA percentuale (4, 5, 10 o 22)
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


@mcp.tool()
def decurtazione_punti_patente(violazione: str) -> dict:
    """Punti decurtati dalla patente per violazione del Codice della Strada.

    Args:
        violazione: Keyword della violazione (es. 'cellulare', 'cintura', 'semaforo_rosso', 'eccesso_velocita_10', 'guida_ebbra', ecc.)
    """
    _VIOLAZIONI = {
        "cellulare": {"punti": 5, "articolo": "Art. 173 CdS", "descrizione": "Uso del telefono alla guida", "sanzione_accessoria": "Sospensione patente in caso di recidiva"},
        "cintura": {"punti": 5, "articolo": "Art. 172 CdS", "descrizione": "Mancato uso della cintura di sicurezza"},
        "semaforo_rosso": {"punti": 6, "articolo": "Art. 146 CdS", "descrizione": "Passaggio con semaforo rosso", "sanzione_accessoria": "Sospensione patente 1-3 mesi"},
        "eccesso_velocita_10": {"punti": 0, "articolo": "Art. 142 CdS", "descrizione": "Eccesso di velocita fino a 10 km/h"},
        "eccesso_velocita_40": {"punti": 6, "articolo": "Art. 142 CdS", "descrizione": "Eccesso di velocita tra 10 e 40 km/h"},
        "eccesso_velocita_60": {"punti": 10, "articolo": "Art. 142 CdS", "descrizione": "Eccesso di velocita oltre 60 km/h", "sanzione_accessoria": "Sospensione patente 6-12 mesi"},
        "guida_ebbra": {"punti": 10, "articolo": "Art. 186 CdS", "descrizione": "Guida in stato di ebbrezza (tasso > 0.5 g/l)", "sanzione_accessoria": "Sospensione/revoca patente"},
        "sorpasso": {"punti": 4, "articolo": "Art. 148 CdS", "descrizione": "Sorpasso vietato o pericoloso"},
        "precedenza": {"punti": 8, "articolo": "Art. 145 CdS", "descrizione": "Mancata precedenza", "sanzione_accessoria": "Sospensione patente in caso di incidente"},
        "stop": {"punti": 6, "articolo": "Art. 145 CdS", "descrizione": "Mancato arresto al segnale di stop"},
        "contromano": {"punti": 10, "articolo": "Art. 143 CdS", "descrizione": "Circolazione contromano", "sanzione_accessoria": "Sospensione patente 1-3 mesi"},
        "strisce_pedonali": {"punti": 8, "articolo": "Art. 191 CdS", "descrizione": "Mancata precedenza ai pedoni sulle strisce"},
        "distanza_sicurezza": {"punti": 5, "articolo": "Art. 149 CdS", "descrizione": "Mancato rispetto della distanza di sicurezza"},
        "casco": {"punti": 5, "articolo": "Art. 171 CdS", "descrizione": "Mancato uso del casco"},
        "fuga_incidente": {"punti": 10, "articolo": "Art. 189 CdS", "descrizione": "Fuga dopo incidente con danni", "sanzione_accessoria": "Sospensione/revoca patente"},
        "patente_scaduta": {"punti": 0, "articolo": "Art. 126 CdS", "descrizione": "Guida con patente scaduta"},
        "revisione_scaduta": {"punti": 0, "articolo": "Art. 80 CdS", "descrizione": "Circolazione con revisione scaduta"},
        "assicurazione": {"punti": 0, "articolo": "Art. 193 CdS", "descrizione": "Circolazione senza assicurazione", "sanzione_accessoria": "Sequestro del veicolo"},
    }

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


@mcp.tool()
def tasso_alcolemico(
    sesso: str,
    peso_kg: float,
    unita_alcoliche: float,
    ore_trascorse: float,
    stomaco_pieno: bool = False,
) -> dict:
    """Calcolo tasso alcolemico teorico con formula di Widmark e fascia sanzionatoria CdS.

    Args:
        sesso: 'M' o 'F'
        peso_kg: Peso corporeo in kg
        unita_alcoliche: Numero di unita alcoliche consumate (1 UA = 12g di alcol puro = 1 birra 33cl, 1 bicchiere vino 12cl)
        ore_trascorse: Ore trascorse dall'assunzione
        stomaco_pieno: True se consumo durante pasto completo (riduzione assorbimento ~30%)
    """
    sesso = sesso.upper().strip()
    if sesso not in ("M", "F"):
        return {"errore": "sesso deve essere 'M' o 'F'"}
    if peso_kg <= 0 or unita_alcoliche < 0:
        return {"errore": "peso_kg e unita_alcoliche devono essere positivi"}

    GRAMMI_PER_UA = 12
    COEFF_WIDMARK = 0.73 if sesso == "M" else 0.66
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


@mcp.tool()
def prescrizione_diritti(
    tipo_diritto: str,
    data_evento: str,
) -> dict:
    """Calcolo prescrizione diritti civili: verifica se un diritto e prescritto e data di prescrizione.

    Args:
        tipo_diritto: Tipo di diritto — 'ordinaria' (10 anni), 'risarcimento_danni' (5), 'risarcimento_rca' (2), 'diritti_lavoro' (5), 'crediti_professionisti' (3), 'canoni_locazione' (5), 'contributi_previdenziali' (5), 'vizi_vendita' (1), 'garanzia_appalto' (2)
        data_evento: Data del fatto generatore del diritto (YYYY-MM-DD)
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
    data_prescrizione = date(dt_evento.year + anni, dt_evento.month, dt_evento.day)
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


@mcp.tool()
def calcolo_tempo_trascorso(
    data_inizio: str,
    data_fine: str | None = None,
) -> dict:
    """Calcolo tempo trascorso tra due date in anni, mesi e giorni. Utile per anzianita, durata contratti, etc.

    Args:
        data_inizio: Data inizio (YYYY-MM-DD)
        data_fine: Data fine (YYYY-MM-DD). Se omessa usa la data odierna.
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


@mcp.tool()
def verifica_partita_iva(partita_iva: str) -> dict:
    """Validazione formale partita IVA italiana (11 cifre, algoritmo di controllo).

    Args:
        partita_iva: Numero di partita IVA (11 cifre)
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


@mcp.tool()
def calcolo_eta_anagrafica(
    data_nascita: str,
    data_riferimento: str | None = None,
) -> dict:
    """Calcolo eta anagrafica esatta in anni, mesi, giorni con prossimo compleanno.

    Args:
        data_nascita: Data di nascita (YYYY-MM-DD)
        data_riferimento: Data di riferimento (YYYY-MM-DD). Se omessa usa la data odierna.
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


@mcp.tool()
def ricerca_codici_ateco(keyword: str) -> dict:
    """Ricerca codice ATECO per keyword. Utile per regime forfettario (coefficiente di redditivita).

    Args:
        keyword: Parola chiave da cercare (es. 'ristorante', 'avvocato', 'sviluppatore', 'commercio')
    """
    _ATECO = [
        {"codice": "01.11.10", "descrizione": "Coltivazione di cereali", "coefficiente": 40},
        {"codice": "10.71.10", "descrizione": "Produzione di pane e prodotti di panetteria freschi", "coefficiente": 40},
        {"codice": "25.11.00", "descrizione": "Fabbricazione di strutture metalliche", "coefficiente": 86},
        {"codice": "41.20.00", "descrizione": "Costruzione di edifici residenziali e non", "coefficiente": 86},
        {"codice": "43.21.01", "descrizione": "Installazione di impianti elettrici", "coefficiente": 86},
        {"codice": "43.22.01", "descrizione": "Installazione di impianti idraulici", "coefficiente": 86},
        {"codice": "45.11.01", "descrizione": "Commercio ingrosso/dettaglio di autovetture", "coefficiente": 40},
        {"codice": "45.20.10", "descrizione": "Riparazione meccanica di autoveicoli", "coefficiente": 67},
        {"codice": "46.11.00", "descrizione": "Intermediari del commercio (agenti)", "coefficiente": 62},
        {"codice": "46.19.02", "descrizione": "Procacciatori d'affari", "coefficiente": 62},
        {"codice": "47.11.40", "descrizione": "Minimercati e altri esercizi non specializzati", "coefficiente": 40},
        {"codice": "47.19.10", "descrizione": "Grandi magazzini", "coefficiente": 40},
        {"codice": "47.24.10", "descrizione": "Commercio al dettaglio di pane", "coefficiente": 40},
        {"codice": "47.71.10", "descrizione": "Commercio al dettaglio di abbigliamento", "coefficiente": 40},
        {"codice": "47.91.10", "descrizione": "Commercio al dettaglio via internet (e-commerce)", "coefficiente": 40},
        {"codice": "49.32.10", "descrizione": "Trasporto con taxi", "coefficiente": 67},
        {"codice": "49.41.00", "descrizione": "Trasporto merci su strada", "coefficiente": 67},
        {"codice": "55.10.00", "descrizione": "Alberghi", "coefficiente": 40},
        {"codice": "55.20.51", "descrizione": "Affittacamere, B&B, case vacanze", "coefficiente": 40},
        {"codice": "56.10.11", "descrizione": "Ristorazione con somministrazione", "coefficiente": 40},
        {"codice": "56.10.30", "descrizione": "Gelaterie e pasticcerie", "coefficiente": 40},
        {"codice": "56.21.00", "descrizione": "Catering per eventi", "coefficiente": 40},
        {"codice": "56.30.00", "descrizione": "Bar e altri esercizi simili", "coefficiente": 40},
        {"codice": "62.01.00", "descrizione": "Produzione di software, consulenza informatica", "coefficiente": 67},
        {"codice": "62.02.00", "descrizione": "Consulenza informatica", "coefficiente": 67},
        {"codice": "62.09.09", "descrizione": "Altre attivita dei servizi IT", "coefficiente": 67},
        {"codice": "63.11.19", "descrizione": "Elaborazione dati, hosting, web", "coefficiente": 67},
        {"codice": "63.91.00", "descrizione": "Attivita delle agenzie di stampa", "coefficiente": 67},
        {"codice": "68.20.02", "descrizione": "Affitto di immobili propri", "coefficiente": 40},
        {"codice": "69.10.10", "descrizione": "Attivita degli studi legali — avvocati", "coefficiente": 78},
        {"codice": "69.10.20", "descrizione": "Attivita degli studi notarili", "coefficiente": 78},
        {"codice": "69.20.11", "descrizione": "Servizi forniti da dottori commercialisti", "coefficiente": 78},
        {"codice": "69.20.12", "descrizione": "Servizi forniti da ragionieri e periti commerciali", "coefficiente": 78},
        {"codice": "69.20.13", "descrizione": "Servizi forniti da consulenti del lavoro", "coefficiente": 78},
        {"codice": "69.20.30", "descrizione": "Attivita dei CAF", "coefficiente": 78},
        {"codice": "70.22.09", "descrizione": "Consulenza aziendale e gestionale", "coefficiente": 78},
        {"codice": "71.11.00", "descrizione": "Attivita degli studi di architettura", "coefficiente": 78},
        {"codice": "71.12.10", "descrizione": "Attivita degli studi di ingegneria", "coefficiente": 78},
        {"codice": "71.12.20", "descrizione": "Servizi di progettazione di ingegneria integrata", "coefficiente": 78},
        {"codice": "71.12.40", "descrizione": "Attivita di studio geologico e di prospezione", "coefficiente": 78},
        {"codice": "71.20.10", "descrizione": "Collaudi e analisi tecniche", "coefficiente": 78},
        {"codice": "72.19.09", "descrizione": "Ricerca e sviluppo sperimentale", "coefficiente": 78},
        {"codice": "73.11.02", "descrizione": "Agenzie pubblicitarie", "coefficiente": 78},
        {"codice": "74.10.21", "descrizione": "Attivita dei designer industriali", "coefficiente": 78},
        {"codice": "74.10.29", "descrizione": "Altre attivita di design", "coefficiente": 78},
        {"codice": "74.10.10", "descrizione": "Attivita di design di moda", "coefficiente": 78},
        {"codice": "74.20.19", "descrizione": "Altre attivita di riprese fotografiche", "coefficiente": 78},
        {"codice": "74.30.00", "descrizione": "Traduzione e interpretariato", "coefficiente": 78},
        {"codice": "74.90.99", "descrizione": "Altre attivita professionali NCA", "coefficiente": 78},
        {"codice": "75.00.00", "descrizione": "Servizi veterinari", "coefficiente": 78},
        {"codice": "77.11.00", "descrizione": "Noleggio autovetture e autoveicoli leggeri", "coefficiente": 40},
        {"codice": "79.11.00", "descrizione": "Attivita delle agenzie di viaggio", "coefficiente": 40},
        {"codice": "82.11.01", "descrizione": "Servizi di segreteria e supporto amministrativo", "coefficiente": 67},
        {"codice": "85.59.20", "descrizione": "Corsi di formazione e aggiornamento professionale", "coefficiente": 78},
        {"codice": "85.59.30", "descrizione": "Scuole e corsi di lingua", "coefficiente": 78},
        {"codice": "85.51.00", "descrizione": "Corsi sportivi e ricreativi", "coefficiente": 78},
        {"codice": "86.10.10", "descrizione": "Ospedali e case di cura generici", "coefficiente": 78},
        {"codice": "86.21.00", "descrizione": "Servizi degli studi medici di medicina generale", "coefficiente": 78},
        {"codice": "86.22.09", "descrizione": "Studi medici specialistici", "coefficiente": 78},
        {"codice": "86.23.00", "descrizione": "Attivita degli studi odontoiatrici", "coefficiente": 78},
        {"codice": "86.90.21", "descrizione": "Fisioterapia", "coefficiente": 78},
        {"codice": "86.90.29", "descrizione": "Altre attivita paramediche (es. logopedista, psicologo)", "coefficiente": 78},
        {"codice": "88.91.00", "descrizione": "Servizi di asili nido", "coefficiente": 67},
        {"codice": "90.01.01", "descrizione": "Attivita nel campo della recitazione", "coefficiente": 67},
        {"codice": "90.03.09", "descrizione": "Altre creazioni artistiche e letterarie", "coefficiente": 67},
        {"codice": "93.11.10", "descrizione": "Gestione di impianti sportivi", "coefficiente": 67},
        {"codice": "93.13.00", "descrizione": "Gestione di palestre", "coefficiente": 67},
        {"codice": "93.19.10", "descrizione": "Enti e organizzazioni sportive, personal trainer", "coefficiente": 67},
        {"codice": "95.11.00", "descrizione": "Riparazione di computer", "coefficiente": 67},
        {"codice": "96.02.01", "descrizione": "Servizi dei saloni di barbiere e parrucchiere", "coefficiente": 67},
        {"codice": "96.02.02", "descrizione": "Servizi degli istituti di bellezza", "coefficiente": 67},
        {"codice": "96.04.10", "descrizione": "Servizi di centri per il benessere fisico (esclusi gli stabilimenti termali)", "coefficiente": 67},
        {"codice": "96.09.09", "descrizione": "Altre attivita di servizi per la persona NCA", "coefficiente": 67},
    ]

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
