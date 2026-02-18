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
