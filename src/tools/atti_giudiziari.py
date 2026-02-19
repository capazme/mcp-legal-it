"""Sezione 4 — Atti Giudiziari: CU, diritti copia, pignoramento, solleciti, decreti ingiuntivi, hash PCT, tassazione."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "contributo_unificato.json") as f:
    _CU = json.load(f)

with open(_DATA / "tassi_mora.json") as f:
    _TASSI_MORA = json.load(f)["tassi"]


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _days_in_year(year: int) -> int:
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


def _get_tasso_mora(d: date) -> dict:
    for t in _TASSI_MORA:
        if _parse_date(t["dal"]) <= d <= _parse_date(t["al"]):
            return t
    return _TASSI_MORA[-1]


def _lookup_scaglione(scaglioni: list, valore: float) -> float:
    for s in scaglioni:
        if "fino_a" in s and valore <= s["fino_a"]:
            return s["importo"]
        if "oltre" in s:
            return s["importo"]
    return scaglioni[-1]["importo"]


def _calcola_cu_base(valore_causa: float, tipo_procedimento: str) -> float:
    """Calcola CU base primo grado."""
    civile = _CU["civile"]

    # Procedimenti a importo fisso
    fissi = {
        "esecuzione_immobiliare": civile["esecuzione_immobiliare"],
        "esecuzione_mobiliare": civile["esecuzione_mobiliare"],
        "volontaria_giurisdizione": civile["volontaria_giurisdizione"],
        "separazione_consensuale": civile["separazione_consensuale"],
        "separazione_giudiziale": civile["separazione_giudiziale"],
        "divorzio_congiunto": civile["divorzio_congiunto"],
        "divorzio_giudiziale": civile["divorzio_giudiziale"],
        "cautelari": civile["cautelari"],
    }
    if tipo_procedimento in fissi:
        return fissi[tipo_procedimento]

    # Cognizione (scaglioni per valore)
    if tipo_procedimento == "cognizione":
        return _lookup_scaglione(civile["cognizione"], valore_causa)

    # Monitorio (scaglioni dimezzati)
    if tipo_procedimento == "monitorio":
        return _lookup_scaglione(civile["procedimento_monitorio"]["scaglioni"], valore_causa)

    # Lavoro — primo grado esente
    if tipo_procedimento == "lavoro":
        return 0.0

    # Tributario
    if tipo_procedimento == "tributario":
        return _lookup_scaglione(_CU["tributario"]["scaglioni"], valore_causa)

    # TAR
    if tipo_procedimento == "tar":
        return _CU["amministrativo"]["tar_ordinario"]

    return _lookup_scaglione(civile["cognizione"], valore_causa)


@mcp.tool()
def contributo_unificato(
    valore_causa: float,
    tipo_procedimento: str = "cognizione",
    grado: str = "primo",
) -> dict:
    """Calcola il Contributo Unificato (DPR 115/2002) per valore causa, tipo e grado.

    Args:
        valore_causa: Valore della causa in euro
        tipo_procedimento: cognizione, esecuzione_immobiliare, esecuzione_mobiliare, monitorio, volontaria_giurisdizione, separazione_consensuale, separazione_giudiziale, divorzio_congiunto, divorzio_giudiziale, cautelari, lavoro, tributario, tar
        grado: primo, appello, cassazione
    """
    cu_base = _calcola_cu_base(valore_causa, tipo_procedimento)

    moltiplicatore = 1.0
    if grado == "appello":
        if tipo_procedimento == "lavoro":
            lavoro_appello = _CU["lavoro"]["appello"]
            if valore_causa <= lavoro_appello["fino_a"]:
                cu_base = lavoro_appello["importo"]
            elif valore_causa <= 50000:
                cu_base = lavoro_appello["fino_a_50000"]
            else:
                cu_base = lavoro_appello["oltre"]
            moltiplicatore = 1.0
        else:
            moltiplicatore = _CU["appello"]["moltiplicatore"]
    elif grado == "cassazione":
        moltiplicatore = _CU["cassazione"]["moltiplicatore"]

    importo = round(cu_base * moltiplicatore, 2)

    return {
        "valore_causa": valore_causa,
        "tipo_procedimento": tipo_procedimento,
        "grado": grado,
        "cu_base": cu_base,
        "moltiplicatore": moltiplicatore,
        "importo_dovuto": importo,
        "riferimento_normativo": "DPR 115/2002 — Testo Unico Spese di Giustizia",
    }


@mcp.tool()
def diritti_copia(
    n_pagine: int,
    tipo: str = "semplice",
    urgente: bool = False,
) -> dict:
    """Calcola diritti di copia atti giudiziari.

    Args:
        n_pagine: Numero di pagine dell'atto
        tipo: semplice, autentica, esecutiva
        urgente: True per urgenza (+50%)
    """
    tariffe = {
        "semplice": 0.30,
        "autentica": 0.70,
        "esecutiva": 0.70,
    }
    tariffa_pagina = tariffe.get(tipo, 0.30)
    subtotale = round(n_pagine * tariffa_pagina, 2)
    maggiorazione_urgenza = round(subtotale * 0.5, 2) if urgente else 0.0
    totale = round(subtotale + maggiorazione_urgenza, 2)

    result = {
        "n_pagine": n_pagine,
        "tipo": tipo,
        "tariffa_pagina": tariffa_pagina,
        "subtotale": subtotale,
        "urgente": urgente,
        "totale": totale,
        "riferimento_normativo": "DPR 115/2002, artt. 267-270",
    }
    if urgente:
        result["maggiorazione_urgenza"] = maggiorazione_urgenza
    return result


@mcp.tool()
def pignoramento_stipendio(
    stipendio_netto_mensile: float,
    tipo_credito: str = "ordinario",
) -> dict:
    """Calcola quote pignorabili dello stipendio/pensione ex art. 545 c.p.c.

    Args:
        stipendio_netto_mensile: Stipendio netto mensile in euro
        tipo_credito: ordinario, alimentare, fiscale, concorso_crediti
    """
    # Assegno sociale 2024 come minimo vitale per pensioni
    minimo_vitale = 534.41

    if tipo_credito == "ordinario":
        quota = 1 / 5
        pignorabile = round(stipendio_netto_mensile * quota, 2)
        descrizione = "1/5 dello stipendio netto (art. 545 co. 4 c.p.c.)"
    elif tipo_credito == "alimentare":
        quota = 1 / 3
        pignorabile = round(stipendio_netto_mensile * quota, 2)
        descrizione = "Fino a 1/3 dello stipendio netto (art. 545 co. 3 c.p.c.) — misura fissata dal giudice"
    elif tipo_credito == "fiscale":
        quota_base = 1 / 5
        quota_aggiuntiva = 1 / 10
        pignorabile = round(stipendio_netto_mensile * (quota_base + quota_aggiuntiva), 2)
        quota = quota_base + quota_aggiuntiva
        descrizione = "1/5 + 1/10 per crediti fiscali/cartelle esattoriali (DPR 602/73)"
    elif tipo_credito == "concorso_crediti":
        quota = 1 / 2
        pignorabile = round(stipendio_netto_mensile * quota, 2)
        descrizione = "Fino a 1/2 in caso di concorso di crediti (art. 545 co. 5 c.p.c.)"
    else:
        return {"errore": f"tipo_credito non riconosciuto: {tipo_credito}"}

    non_pignorabile = round(stipendio_netto_mensile - pignorabile, 2)

    return {
        "stipendio_netto_mensile": stipendio_netto_mensile,
        "tipo_credito": tipo_credito,
        "quota_pignorabile": round(quota, 4),
        "importo_pignorabile": pignorabile,
        "importo_non_pignorabile": non_pignorabile,
        "minimo_vitale_pensioni": minimo_vitale,
        "nota_pensioni": f"Per le pensioni, è impignorabile l'importo pari al doppio dell'assegno sociale (€{minimo_vitale * 2:.2f})",
        "descrizione": descrizione,
        "riferimento_normativo": "Art. 545 c.p.c. — DL 83/2015",
    }


@mcp.tool()
def sollecito_pagamento(
    creditore: str,
    debitore: str,
    importo: float,
    data_scadenza: str,
    data_sollecito: str,
    tasso_mora: float | None = None,
) -> dict:
    """Genera lettera di sollecito pagamento con calcolo interessi mora.

    Args:
        creditore: Nome/ragione sociale del creditore
        debitore: Nome/ragione sociale del debitore
        importo: Importo del credito in euro
        data_scadenza: Data scadenza originale (YYYY-MM-DD)
        data_sollecito: Data del sollecito (YYYY-MM-DD)
        tasso_mora: Tasso mora annuo % personalizzato (se None, usa D.Lgs. 231/2002)
    """
    dt_scadenza = _parse_date(data_scadenza)
    dt_sollecito = _parse_date(data_sollecito)
    giorni_ritardo = (dt_sollecito - dt_scadenza).days

    if giorni_ritardo <= 0:
        return {"errore": "La data del sollecito deve essere successiva alla scadenza"}

    # Calcolo interessi mora
    if tasso_mora is not None:
        interessi = round(importo * (tasso_mora / 100) * giorni_ritardo / _days_in_year(dt_scadenza.year), 2)
        tasso_applicato = tasso_mora
        base_giuridica_tasso = f"Tasso convenzionale {tasso_mora}%"
    else:
        info_mora = _get_tasso_mora(dt_scadenza)
        tasso_applicato = info_mora["mora"]
        interessi = round(importo * (tasso_applicato / 100) * giorni_ritardo / _days_in_year(dt_scadenza.year), 2)
        base_giuridica_tasso = f"D.Lgs. 231/2002 — tasso BCE ({info_mora['bce']}%) + 8 pp = {tasso_applicato}%"

    totale_dovuto = round(importo + interessi, 2)

    testo = f"""Egr. {debitore},

con la presente siamo a ricordarVi che alla data odierna risulta ancora insoluto il pagamento di Euro {importo:,.2f} (diconsi euro {importo:,.2f}), scaduto in data {dt_scadenza.strftime('%d/%m/%Y')}.

Ad oggi il ritardo ammonta a {giorni_ritardo} giorni.

Vi invitiamo pertanto a provvedere al pagamento dell'importo complessivo di Euro {totale_dovuto:,.2f}, così composto:
- Capitale: Euro {importo:,.2f}
- Interessi di mora ({tasso_applicato}% annuo, {giorni_ritardo} gg): Euro {interessi:,.2f}

Il pagamento dovrà pervenire entro e non oltre 15 giorni dal ricevimento della presente.

In difetto, ci vedremo costretti ad adire le vie legali per il recupero del credito, con aggravio di spese a Vostro carico.

Distinti saluti,
{creditore}"""

    return {
        "testo_lettera": testo,
        "calcoli": {
            "importo_originale": importo,
            "data_scadenza": data_scadenza,
            "data_sollecito": data_sollecito,
            "giorni_ritardo": giorni_ritardo,
            "tasso_mora_pct": tasso_applicato,
            "interessi_mora": interessi,
            "totale_dovuto": totale_dovuto,
            "base_giuridica": base_giuridica_tasso,
        },
    }


@mcp.tool()
def decreto_ingiuntivo(
    creditore: str,
    debitore: str,
    importo: float,
    tipo_credito: str = "ordinario",
    provvisoria_esecuzione: bool = False,
) -> dict:
    """Genera bozza ricorso per decreto ingiuntivo con calcolo competenza e CU.

    Args:
        creditore: Nome/ragione sociale del creditore
        debitore: Nome/ragione sociale del debitore
        importo: Importo del credito in euro
        tipo_credito: ordinario, professionale, condominiale, cambiale
        provvisoria_esecuzione: True per richiedere provvisoria esecuzione ex art. 642 c.p.c.
    """
    # Giudice competente per valore
    if importo <= 5000:
        giudice = "Giudice di Pace"
    else:
        giudice = "Tribunale"

    # CU monitorio
    cu = _calcola_cu_base(importo, "monitorio")

    # Motivi provvisoria esecuzione
    motivi_pe = []
    if provvisoria_esecuzione:
        if tipo_credito == "professionale":
            motivi_pe.append("credito fondato su parcella professionale vidimata dall'Ordine (art. 642 co. 1 c.p.c.)")
        elif tipo_credito == "condominiale":
            motivi_pe.append("credito fondato su delibera assembleare di approvazione spese (art. 63 disp. att. c.c.)")
        elif tipo_credito == "cambiale":
            motivi_pe.append("credito fondato su cambiale (art. 642 co. 1 c.p.c.)")
        else:
            motivi_pe.append("pericolo di grave pregiudizio nel ritardo (art. 642 co. 2 c.p.c.)")

    bozza = f"""RICORSO PER DECRETO INGIUNTIVO
(Artt. 633 e ss. c.p.c.)

ILL.MO SIG. {giudice.upper()} DI [SEDE]

RICORSO

Il/La sottoscritto/a Avv. [LEGALE], C.F. [...], con studio in [...], quale procuratore/trice di:

{creditore}, C.F./P.IVA [...], con sede in [...]

ESPONE

Che il/la ricorrente vanta un credito di Euro {importo:,.2f} nei confronti di:

{debitore}, C.F./P.IVA [...], con sede in [...]

per le causali risultanti dalla documentazione allegata.

Che il credito è certo, liquido ed esigibile, come risulta dalla prova scritta allegata.

CHIEDE

che l'Ill.mo {giudice} voglia emettere decreto con il quale si ingiunge a {debitore} di pagare la somma di Euro {importo:,.2f}, oltre interessi legali dalla messa in mora al saldo, oltre spese e competenze del procedimento."""

    if provvisoria_esecuzione:
        bozza += f"""

Si chiede altresì che il decreto sia munito di clausola di provvisoria esecuzione ex art. 642 c.p.c., in quanto:
- {'; '.join(motivi_pe)}"""

    bozza += """

Si allegano:
1. Procura alle liti
2. Documentazione comprovante il credito
3. [Ulteriori allegati]

[Luogo], [Data]
Avv. [LEGALE]"""

    return {
        "bozza_ricorso": bozza,
        "riepilogo": {
            "creditore": creditore,
            "debitore": debitore,
            "importo": importo,
            "tipo_credito": tipo_credito,
            "giudice_competente": giudice,
            "contributo_unificato": cu,
            "provvisoria_esecuzione": provvisoria_esecuzione,
            "motivi_pe": motivi_pe if provvisoria_esecuzione else None,
        },
        "riferimento_normativo": "Artt. 633-656 c.p.c.",
    }


@mcp.tool()
def calcolo_hash(testo: str) -> dict:
    """Calcola impronta hash SHA-256 per deposito telematico PCT.

    Args:
        testo: Testo o contenuto del documento di cui calcolare l'hash
    """
    digest = hashlib.sha256(testo.encode("utf-8")).hexdigest()

    return {
        "algoritmo": "SHA-256",
        "hash": digest,
        "lunghezza_input": len(testo),
        "nota": "Impronta digitale conforme alle specifiche tecniche PCT (DM 44/2011)",
    }


@mcp.tool()
def tassazione_atti(
    tipo_atto: str,
    valore: float,
    prima_casa: bool = False,
) -> dict:
    """Calcola imposta di registro su atti giudiziari.

    Args:
        tipo_atto: sentenza_condanna, decreto_ingiuntivo, verbale_conciliazione, ordinanza
        valore: Valore dell'atto/importo oggetto del provvedimento in euro
        prima_casa: True se relativo a trasferimento prima casa (aliquota agevolata)
    """
    # Imposte fisse e proporzionali per atti giudiziari
    imposta_fissa = 200.0

    if tipo_atto == "sentenza_condanna":
        if valore > 0:
            aliquota = 0.03  # 3% per condanne al pagamento di somme
            imposta = max(round(valore * aliquota, 2), imposta_fissa)
            descrizione = "Imposta proporzionale 3% su sentenze di condanna al pagamento"
        else:
            imposta = imposta_fissa
            aliquota = 0
            descrizione = "Imposta fissa per sentenze senza condanna al pagamento"
    elif tipo_atto == "decreto_ingiuntivo":
        aliquota = 0.03
        imposta = max(round(valore * aliquota, 2), imposta_fissa)
        descrizione = "Imposta proporzionale 3% su decreto ingiuntivo"
    elif tipo_atto == "verbale_conciliazione":
        if prima_casa:
            aliquota = 0.02  # 2% agevolata
            imposta = max(round(valore * aliquota, 2), 1000.0)
            descrizione = "Imposta 2% su verbale conciliazione (agevolazione prima casa)"
        else:
            aliquota = 0.03
            imposta = max(round(valore * aliquota, 2), imposta_fissa)
            descrizione = "Imposta proporzionale 3% su verbale di conciliazione"
    elif tipo_atto == "ordinanza":
        imposta = imposta_fissa
        aliquota = 0
        descrizione = "Imposta fissa per ordinanze"
    else:
        return {"errore": f"tipo_atto non riconosciuto: {tipo_atto}. Valori ammessi: sentenza_condanna, decreto_ingiuntivo, verbale_conciliazione, ordinanza"}

    return {
        "tipo_atto": tipo_atto,
        "valore": valore,
        "prima_casa": prima_casa,
        "aliquota_pct": round(aliquota * 100, 2) if aliquota else 0,
        "imposta_registro": imposta,
        "descrizione": descrizione,
        "riferimento_normativo": "DPR 131/1986 — TU Imposta di Registro, Tariffa Parte I",
    }


# ---------------------------------------------------------------------------
# Mapping tribunali competenti per i principali comuni italiani
# ---------------------------------------------------------------------------
_TRIBUNALI_COMPETENTI: dict[str, dict[str, str]] = {
    "roma": {"tribunale": "Tribunale di Roma", "giudice_pace": "Giudice di Pace di Roma"},
    "milano": {"tribunale": "Tribunale di Milano", "giudice_pace": "Giudice di Pace di Milano"},
    "napoli": {"tribunale": "Tribunale di Napoli", "giudice_pace": "Giudice di Pace di Napoli"},
    "torino": {"tribunale": "Tribunale di Torino", "giudice_pace": "Giudice di Pace di Torino"},
    "palermo": {"tribunale": "Tribunale di Palermo", "giudice_pace": "Giudice di Pace di Palermo"},
    "genova": {"tribunale": "Tribunale di Genova", "giudice_pace": "Giudice di Pace di Genova"},
    "bologna": {"tribunale": "Tribunale di Bologna", "giudice_pace": "Giudice di Pace di Bologna"},
    "firenze": {"tribunale": "Tribunale di Firenze", "giudice_pace": "Giudice di Pace di Firenze"},
    "bari": {"tribunale": "Tribunale di Bari", "giudice_pace": "Giudice di Pace di Bari"},
    "catania": {"tribunale": "Tribunale di Catania", "giudice_pace": "Giudice di Pace di Catania"},
    "venezia": {"tribunale": "Tribunale di Venezia", "giudice_pace": "Giudice di Pace di Venezia"},
    "verona": {"tribunale": "Tribunale di Verona", "giudice_pace": "Giudice di Pace di Verona"},
    "messina": {"tribunale": "Tribunale di Messina", "giudice_pace": "Giudice di Pace di Messina"},
    "padova": {"tribunale": "Tribunale di Padova", "giudice_pace": "Giudice di Pace di Padova"},
    "trieste": {"tribunale": "Tribunale di Trieste", "giudice_pace": "Giudice di Pace di Trieste"},
    "taranto": {"tribunale": "Tribunale di Taranto", "giudice_pace": "Giudice di Pace di Taranto"},
    "brescia": {"tribunale": "Tribunale di Brescia", "giudice_pace": "Giudice di Pace di Brescia"},
    "reggio calabria": {"tribunale": "Tribunale di Reggio Calabria", "giudice_pace": "Giudice di Pace di Reggio Calabria"},
    "modena": {"tribunale": "Tribunale di Modena", "giudice_pace": "Giudice di Pace di Modena"},
    "prato": {"tribunale": "Tribunale di Prato", "giudice_pace": "Giudice di Pace di Prato"},
    "parma": {"tribunale": "Tribunale di Parma", "giudice_pace": "Giudice di Pace di Parma"},
    "cagliari": {"tribunale": "Tribunale di Cagliari", "giudice_pace": "Giudice di Pace di Cagliari"},
    "livorno": {"tribunale": "Tribunale di Livorno", "giudice_pace": "Giudice di Pace di Livorno"},
    "perugia": {"tribunale": "Tribunale di Perugia", "giudice_pace": "Giudice di Pace di Perugia"},
    "foggia": {"tribunale": "Tribunale di Foggia", "giudice_pace": "Giudice di Pace di Foggia"},
    "reggio emilia": {"tribunale": "Tribunale di Reggio Emilia", "giudice_pace": "Giudice di Pace di Reggio Emilia"},
    "salerno": {"tribunale": "Tribunale di Salerno", "giudice_pace": "Giudice di Pace di Salerno"},
    "ravenna": {"tribunale": "Tribunale di Ravenna", "giudice_pace": "Giudice di Pace di Ravenna"},
    "ferrara": {"tribunale": "Tribunale di Ferrara", "giudice_pace": "Giudice di Pace di Ferrara"},
    "rimini": {"tribunale": "Tribunale di Rimini", "giudice_pace": "Giudice di Pace di Rimini"},
    "sassari": {"tribunale": "Tribunale di Sassari", "giudice_pace": "Giudice di Pace di Sassari"},
    "siracusa": {"tribunale": "Tribunale di Siracusa", "giudice_pace": "Giudice di Pace di Siracusa"},
    "pescara": {"tribunale": "Tribunale di Pescara", "giudice_pace": "Giudice di Pace di Pescara"},
    "monza": {"tribunale": "Tribunale di Monza", "giudice_pace": "Giudice di Pace di Monza"},
    "bergamo": {"tribunale": "Tribunale di Bergamo", "giudice_pace": "Giudice di Pace di Bergamo"},
    "trento": {"tribunale": "Tribunale di Trento", "giudice_pace": "Giudice di Pace di Trento"},
    "bolzano": {"tribunale": "Tribunale di Bolzano", "giudice_pace": "Giudice di Pace di Bolzano"},
    "forlì": {"tribunale": "Tribunale di Forlì", "giudice_pace": "Giudice di Pace di Forlì"},
    "vicenza": {"tribunale": "Tribunale di Vicenza", "giudice_pace": "Giudice di Pace di Vicenza"},
    "terni": {"tribunale": "Tribunale di Terni", "giudice_pace": "Giudice di Pace di Terni"},
    "novara": {"tribunale": "Tribunale di Novara", "giudice_pace": "Giudice di Pace di Novara"},
    "ancona": {"tribunale": "Tribunale di Ancona", "giudice_pace": "Giudice di Pace di Ancona"},
    "piacenza": {"tribunale": "Tribunale di Piacenza", "giudice_pace": "Giudice di Pace di Piacenza"},
    "lecce": {"tribunale": "Tribunale di Lecce", "giudice_pace": "Giudice di Pace di Lecce"},
    "pesaro": {"tribunale": "Tribunale di Pesaro", "giudice_pace": "Giudice di Pace di Pesaro"},
    "catanzaro": {"tribunale": "Tribunale di Catanzaro", "giudice_pace": "Giudice di Pace di Catanzaro"},
    "cosenza": {"tribunale": "Tribunale di Cosenza", "giudice_pace": "Giudice di Pace di Cosenza"},
    "latina": {"tribunale": "Tribunale di Latina", "giudice_pace": "Giudice di Pace di Latina"},
    "udine": {"tribunale": "Tribunale di Udine", "giudice_pace": "Giudice di Pace di Udine"},
    "arezzo": {"tribunale": "Tribunale di Arezzo", "giudice_pace": "Giudice di Pace di Arezzo"},
    "caserta": {"tribunale": "Tribunale di Santa Maria Capua Vetere", "giudice_pace": "Giudice di Pace di Caserta"},
    "la spezia": {"tribunale": "Tribunale di La Spezia", "giudice_pace": "Giudice di Pace di La Spezia"},
    "pistoia": {"tribunale": "Tribunale di Pistoia", "giudice_pace": "Giudice di Pace di Pistoia"},
    "lucca": {"tribunale": "Tribunale di Lucca", "giudice_pace": "Giudice di Pace di Lucca"},
    "como": {"tribunale": "Tribunale di Como", "giudice_pace": "Giudice di Pace di Como"},
    "varese": {"tribunale": "Tribunale di Varese", "giudice_pace": "Giudice di Pace di Varese"},
    "treviso": {"tribunale": "Tribunale di Treviso", "giudice_pace": "Giudice di Pace di Treviso"},
    "pisa": {"tribunale": "Tribunale di Pisa", "giudice_pace": "Giudice di Pace di Pisa"},
    "lecco": {"tribunale": "Tribunale di Lecco", "giudice_pace": "Giudice di Pace di Lecco"},
    "l'aquila": {"tribunale": "Tribunale di L'Aquila", "giudice_pace": "Giudice di Pace di L'Aquila"},
    "potenza": {"tribunale": "Tribunale di Potenza", "giudice_pace": "Giudice di Pace di Potenza"},
    "campobasso": {"tribunale": "Tribunale di Campobasso", "giudice_pace": "Giudice di Pace di Campobasso"},
    "aosta": {"tribunale": "Tribunale di Aosta", "giudice_pace": "Giudice di Pace di Aosta"},
    "alessandria": {"tribunale": "Tribunale di Alessandria", "giudice_pace": "Giudice di Pace di Alessandria"},
    "asti": {"tribunale": "Tribunale di Asti", "giudice_pace": "Giudice di Pace di Asti"},
    "cuneo": {"tribunale": "Tribunale di Cuneo", "giudice_pace": "Giudice di Pace di Cuneo"},
    "savona": {"tribunale": "Tribunale di Savona", "giudice_pace": "Giudice di Pace di Savona"},
    "imperia": {"tribunale": "Tribunale di Imperia", "giudice_pace": "Giudice di Pace di Imperia"},
    "belluno": {"tribunale": "Tribunale di Belluno", "giudice_pace": "Giudice di Pace di Belluno"},
    "rovigo": {"tribunale": "Tribunale di Rovigo", "giudice_pace": "Giudice di Pace di Rovigo"},
    "pordenone": {"tribunale": "Tribunale di Pordenone", "giudice_pace": "Giudice di Pace di Pordenone"},
    "gorizia": {"tribunale": "Tribunale di Gorizia", "giudice_pace": "Giudice di Pace di Gorizia"},
    "mantova": {"tribunale": "Tribunale di Mantova", "giudice_pace": "Giudice di Pace di Mantova"},
    "cremona": {"tribunale": "Tribunale di Cremona", "giudice_pace": "Giudice di Pace di Cremona"},
    "lodi": {"tribunale": "Tribunale di Lodi", "giudice_pace": "Giudice di Pace di Lodi"},
    "pavia": {"tribunale": "Tribunale di Pavia", "giudice_pace": "Giudice di Pace di Pavia"},
    "sondrio": {"tribunale": "Tribunale di Sondrio", "giudice_pace": "Giudice di Pace di Sondrio"},
    "massa": {"tribunale": "Tribunale di Massa", "giudice_pace": "Giudice di Pace di Massa"},
    "grosseto": {"tribunale": "Tribunale di Grosseto", "giudice_pace": "Giudice di Pace di Grosseto"},
    "siena": {"tribunale": "Tribunale di Siena", "giudice_pace": "Giudice di Pace di Siena"},
    "viterbo": {"tribunale": "Tribunale di Viterbo", "giudice_pace": "Giudice di Pace di Viterbo"},
    "rieti": {"tribunale": "Tribunale di Rieti", "giudice_pace": "Giudice di Pace di Rieti"},
    "frosinone": {"tribunale": "Tribunale di Frosinone", "giudice_pace": "Giudice di Pace di Frosinone"},
    "teramo": {"tribunale": "Tribunale di Teramo", "giudice_pace": "Giudice di Pace di Teramo"},
    "chieti": {"tribunale": "Tribunale di Chieti", "giudice_pace": "Giudice di Pace di Chieti"},
    "isernia": {"tribunale": "Tribunale di Isernia", "giudice_pace": "Giudice di Pace di Isernia"},
    "avellino": {"tribunale": "Tribunale di Avellino", "giudice_pace": "Giudice di Pace di Avellino"},
    "benevento": {"tribunale": "Tribunale di Benevento", "giudice_pace": "Giudice di Pace di Benevento"},
    "brindisi": {"tribunale": "Tribunale di Brindisi", "giudice_pace": "Giudice di Pace di Brindisi"},
    "matera": {"tribunale": "Tribunale di Matera", "giudice_pace": "Giudice di Pace di Matera"},
    "crotone": {"tribunale": "Tribunale di Crotone", "giudice_pace": "Giudice di Pace di Crotone"},
    "vibo valentia": {"tribunale": "Tribunale di Vibo Valentia", "giudice_pace": "Giudice di Pace di Vibo Valentia"},
    "agrigento": {"tribunale": "Tribunale di Agrigento", "giudice_pace": "Giudice di Pace di Agrigento"},
    "caltanissetta": {"tribunale": "Tribunale di Caltanissetta", "giudice_pace": "Giudice di Pace di Caltanissetta"},
    "enna": {"tribunale": "Tribunale di Enna", "giudice_pace": "Giudice di Pace di Enna"},
    "ragusa": {"tribunale": "Tribunale di Ragusa", "giudice_pace": "Giudice di Pace di Ragusa"},
    "trapani": {"tribunale": "Tribunale di Trapani", "giudice_pace": "Giudice di Pace di Trapani"},
    "nuoro": {"tribunale": "Tribunale di Nuoro", "giudice_pace": "Giudice di Pace di Nuoro"},
    "oristano": {"tribunale": "Tribunale di Oristano", "giudice_pace": "Giudice di Pace di Oristano"},
    "verbania": {"tribunale": "Tribunale di Verbania", "giudice_pace": "Giudice di Pace di Verbania"},
    "biella": {"tribunale": "Tribunale di Biella", "giudice_pace": "Giudice di Pace di Biella"},
    "vercelli": {"tribunale": "Tribunale di Vercelli", "giudice_pace": "Giudice di Pace di Vercelli"},
}

# ---------------------------------------------------------------------------
# Codici oggetto iscrizione a ruolo — principali cause civili
# ---------------------------------------------------------------------------
_CODICI_RUOLO: list[dict[str, str]] = [
    {"codice": "1.01.001", "materia": "contratto", "descrizione": "Inadempimento contrattuale"},
    {"codice": "1.01.002", "materia": "contratto", "descrizione": "Risoluzione contrattuale"},
    {"codice": "1.01.003", "materia": "contratto", "descrizione": "Annullamento contratto"},
    {"codice": "1.01.010", "materia": "compravendita", "descrizione": "Compravendita immobiliare"},
    {"codice": "1.01.011", "materia": "compravendita", "descrizione": "Compravendita mobiliare"},
    {"codice": "1.02.001", "materia": "locazione", "descrizione": "Locazione — sfratto per morosità"},
    {"codice": "1.02.002", "materia": "locazione", "descrizione": "Locazione — sfratto per finita locazione"},
    {"codice": "1.02.003", "materia": "locazione", "descrizione": "Locazione — determinazione canone"},
    {"codice": "1.02.010", "materia": "locazione", "descrizione": "Locazione — altro"},
    {"codice": "1.03.001", "materia": "responsabilità", "descrizione": "Responsabilità extracontrattuale — risarcimento danni"},
    {"codice": "1.03.002", "materia": "responsabilità", "descrizione": "Responsabilità professionale — medica"},
    {"codice": "1.03.003", "materia": "responsabilità", "descrizione": "Responsabilità professionale — avvocato"},
    {"codice": "1.03.010", "materia": "responsabilità", "descrizione": "Responsabilità da circolazione stradale"},
    {"codice": "1.04.001", "materia": "condominio", "descrizione": "Impugnazione delibera condominiale"},
    {"codice": "1.04.002", "materia": "condominio", "descrizione": "Ripartizione spese condominiali"},
    {"codice": "1.05.001", "materia": "famiglia", "descrizione": "Separazione giudiziale"},
    {"codice": "1.05.002", "materia": "famiglia", "descrizione": "Separazione consensuale"},
    {"codice": "1.05.003", "materia": "famiglia", "descrizione": "Divorzio giudiziale"},
    {"codice": "1.05.004", "materia": "famiglia", "descrizione": "Divorzio congiunto"},
    {"codice": "1.05.010", "materia": "famiglia", "descrizione": "Modifica condizioni separazione/divorzio"},
    {"codice": "1.05.020", "materia": "famiglia", "descrizione": "Affidamento e mantenimento figli"},
    {"codice": "1.06.001", "materia": "successione", "descrizione": "Petizione di eredità"},
    {"codice": "1.06.002", "materia": "successione", "descrizione": "Divisione ereditaria"},
    {"codice": "1.06.003", "materia": "successione", "descrizione": "Impugnazione testamento"},
    {"codice": "1.07.001", "materia": "lavoro", "descrizione": "Lavoro subordinato — impugnazione licenziamento"},
    {"codice": "1.07.002", "materia": "lavoro", "descrizione": "Lavoro subordinato — differenze retributive"},
    {"codice": "1.07.003", "materia": "lavoro", "descrizione": "Lavoro subordinato — mobbing"},
    {"codice": "1.07.010", "materia": "lavoro", "descrizione": "Previdenza e assistenza obbligatoria"},
    {"codice": "1.08.001", "materia": "societario", "descrizione": "Impugnazione delibera assembleare"},
    {"codice": "1.08.002", "materia": "societario", "descrizione": "Azione di responsabilità vs amministratori"},
    {"codice": "1.09.001", "materia": "proprietà", "descrizione": "Rivendicazione proprietà"},
    {"codice": "1.09.002", "materia": "proprietà", "descrizione": "Azione negatoria servitù"},
    {"codice": "1.09.003", "materia": "proprietà", "descrizione": "Regolamento confini"},
    {"codice": "1.09.010", "materia": "proprietà", "descrizione": "Usucapione"},
    {"codice": "1.10.001", "materia": "possesso", "descrizione": "Azione di reintegrazione (spoglio)"},
    {"codice": "1.10.002", "materia": "proprietà", "descrizione": "Azione di manutenzione"},
    {"codice": "1.11.001", "materia": "consumatore", "descrizione": "Tutela del consumatore — clausole vessatorie"},
    {"codice": "1.11.002", "materia": "consumatore", "descrizione": "Tutela del consumatore — prodotto difettoso"},
    {"codice": "1.12.001", "materia": "bancario", "descrizione": "Contratti bancari — anatocismo"},
    {"codice": "1.12.002", "materia": "bancario", "descrizione": "Contratti bancari — usura"},
    {"codice": "1.12.003", "materia": "bancario", "descrizione": "Contratti bancari — fideiussione"},
]


# ---------------------------------------------------------------------------
# 18 nuovi tool — Calcolatori e generatori documenti
# ---------------------------------------------------------------------------


@mcp.tool()
def copie_processo_tributario(
    n_pagine: int,
    tipo: str = "semplice",
    urgente: bool = False,
) -> dict:
    """Calcola diritti di copia specifici per il processo tributario.

    Args:
        n_pagine: Numero di pagine
        tipo: semplice, autentica
        urgente: True per urgenza (+50%)
    """
    tariffe = {"semplice": 0.25, "autentica": 0.50}
    tariffa = tariffe.get(tipo, 0.25)
    subtotale = round(n_pagine * tariffa, 2)
    maggiorazione = round(subtotale * 0.5, 2) if urgente else 0.0
    totale = round(subtotale + maggiorazione, 2)

    result = {
        "n_pagine": n_pagine,
        "tipo": tipo,
        "tariffa_pagina": tariffa,
        "subtotale": subtotale,
        "urgente": urgente,
        "totale": totale,
        "riferimento_normativo": "DPR 115/2002 — Tariffe processo tributario",
    }
    if urgente:
        result["maggiorazione_urgenza"] = maggiorazione
    return result


@mcp.tool()
def note_iscrizione_ruolo(
    tipo_procedimento: str,
    valore_causa: float | None = None,
) -> dict:
    """Genera note per iscrizione a ruolo con codici oggetto e CU calcolato.

    Args:
        tipo_procedimento: cognizione_ordinaria, lavoro, locazione, condominio, esecuzione_mobiliare, esecuzione_immobiliare, monitorio, volontaria_giurisdizione
        valore_causa: Valore della causa in euro (se applicabile)
    """
    mapping_cu = {
        "cognizione_ordinaria": "cognizione",
        "lavoro": "lavoro",
        "locazione": "cognizione",
        "condominio": "cognizione",
        "esecuzione_mobiliare": "esecuzione_mobiliare",
        "esecuzione_immobiliare": "esecuzione_immobiliare",
        "monitorio": "monitorio",
        "volontaria_giurisdizione": "volontaria_giurisdizione",
    }

    mapping_materia = {
        "cognizione_ordinaria": "contratto",
        "lavoro": "lavoro",
        "locazione": "locazione",
        "condominio": "condominio",
        "monitorio": "contratto",
    }

    cu_tipo = mapping_cu.get(tipo_procedimento, "cognizione")
    cu_importo = _calcola_cu_base(valore_causa or 0, cu_tipo)

    materia = mapping_materia.get(tipo_procedimento)
    codici_suggeriti = []
    if materia:
        codici_suggeriti = [c for c in _CODICI_RUOLO if c["materia"] == materia]

    return {
        "tipo_procedimento": tipo_procedimento,
        "valore_causa": valore_causa,
        "contributo_unificato": cu_importo,
        "codici_oggetto_suggeriti": codici_suggeriti,
        "note": f"Iscrivere a ruolo come '{tipo_procedimento}'. CU calcolato: EUR {cu_importo:.2f}.",
        "riferimento_normativo": "DPR 115/2002 — Provvedimenti DGSIA per codici oggetto",
    }


@mcp.tool()
def codici_iscrizione_ruolo(materia: str) -> dict:
    """Ricerca codice oggetto per iscrizione a ruolo cause civili.

    Args:
        materia: Keyword di ricerca (contratto, locazione, responsabilità, famiglia, lavoro, condominio, successione, societario, proprietà, possesso, consumatore, bancario)
    """
    keyword = materia.lower().strip()
    risultati = [
        c for c in _CODICI_RUOLO
        if keyword in c["materia"] or keyword in c["descrizione"].lower()
    ]

    return {
        "ricerca": materia,
        "risultati": risultati,
        "totale": len(risultati),
        "riferimento_normativo": "Provvedimenti DGSIA — Codici oggetto iscrizione a ruolo",
    }


@mcp.tool()
def fascicolo_di_parte(
    avvocato: str,
    parte: str,
    controparte: str,
    tribunale: str,
    rg_numero: str | None = None,
) -> dict:
    """Genera frontespizio fascicolo di parte.

    Args:
        avvocato: Nome dell'avvocato difensore
        parte: Nome della parte assistita
        controparte: Nome della controparte
        tribunale: Denominazione del tribunale
        rg_numero: Numero di Ruolo Generale (se già assegnato)
    """
    rg_line = f"R.G. n. {rg_numero}" if rg_numero else "R.G. n. ___/____"

    testo = f"""{tribunale.upper()}

FASCICOLO DI PARTE

{rg_line}

{parte.upper()}
(parte attrice/ricorrente)

rappresentata e difesa dall'Avv. {avvocato}

CONTRO

{controparte.upper()}
(parte convenuta/resistente)

OGGETTO: _______________________________________________

GIUDICE: _______________________________________________

UDIENZA: _______________________________________________

INDICE DOCUMENTI:
1. Procura alle liti
2. Atto introduttivo
3. _______________________________________________
"""

    return {
        "testo": testo,
        "tipo_atto": "fascicolo_di_parte",
        "riferimento_normativo": "Art. 165 c.p.c. — Costituzione dell'attore",
    }


@mcp.tool()
def procura_alle_liti(
    parte: str,
    avvocato: str,
    cf_avvocato: str,
    foro: str,
    oggetto_causa: str,
    tipo: str = "generale",
) -> dict:
    """Genera procura alle liti ex art. 83 c.p.c.

    Args:
        parte: Nome della parte che conferisce la procura
        avvocato: Nome dell'avvocato
        cf_avvocato: Codice fiscale dell'avvocato
        foro: Foro di appartenenza dell'avvocato
        oggetto_causa: Oggetto della causa
        tipo: generale, speciale, appello
    """
    if tipo == "speciale":
        intestazione = "PROCURA SPECIALE ALLE LITI"
        clausola_tipo = "con ogni più ampio potere per il presente giudizio, ivi compreso il potere di conciliare, transigere, incassare, rinunciare agli atti e accettare la rinuncia, chiamare in causa terzi, proporre domande riconvenzionali"
    elif tipo == "appello":
        intestazione = "PROCURA SPECIALE ALLE LITI PER L'APPELLO"
        clausola_tipo = "con ogni più ampio potere per il giudizio di appello avverso la sentenza n. ___ del ___, ivi compreso il potere di conciliare, transigere, incassare, rinunciare agli atti e accettare la rinuncia"
    else:
        intestazione = "PROCURA ALLE LITI"
        clausola_tipo = "con ogni più ampio potere in ogni stato e grado del giudizio, ivi compreso il potere di conciliare, transigere, incassare, rinunciare agli atti e accettare la rinuncia, chiamare in causa terzi, proporre domande riconvenzionali e impugnare"

    testo = f"""{intestazione}

Il/La sottoscritto/a {parte}, nato/a a ___ il ___, C.F. ___, residente in ___,

DELEGA

l'Avv. {avvocato}, C.F. {cf_avvocato}, del Foro di {foro}, con studio in ___, PEC: ___, a rappresentarlo/a e difenderlo/a nel giudizio avente ad oggetto: {oggetto_causa},

{clausola_tipo}.

Elegge domicilio presso lo studio del predetto difensore e, ai fini delle comunicazioni e notificazioni, all'indirizzo PEC dello stesso risultante da pubblici elenchi.

Dichiara di essere stato/a informato/a, ai sensi dell'art. 4 co. 3 del D.Lgs. 231/2007, che il difensore è tenuto ad effettuare la verifica dell'identità del cliente e all'adeguata verifica ai fini antiriciclaggio.

Presta il consenso al trattamento dei dati personali ai sensi del Reg. UE 2016/679 (GDPR) per le finalità connesse al conferimento dell'incarico professionale.

Dichiara di aver ricevuto l'informativa ai sensi dell'art. 13 del Reg. UE 2016/679.

Luogo e data _______________

Firma _______________
({parte})

È vera la firma apposta in mia presenza.
Avv. {avvocato}"""

    return {
        "testo": testo,
        "tipo_atto": "procura_alle_liti",
        "tipo_procura": tipo,
        "riferimento_normativo": "Art. 83 c.p.c. — Procura alle liti",
    }


@mcp.tool()
def attestazione_conformita(
    avvocato: str,
    tipo_documento: str,
    estremi_originale: str,
    modalita: str = "estratto",
) -> dict:
    """Attestazione di conformità ex art. 16-bis DL 179/2012 per PCT.

    Args:
        avvocato: Nome dell'avvocato
        tipo_documento: Descrizione del tipo di documento attestato
        estremi_originale: Estremi identificativi dell'originale
        modalita: estratto, copia_informatica, duplicato
    """
    if modalita == "copia_informatica":
        tipo_attestazione = "copia informatica di documento analogico"
        norma_specifica = "art. 16-bis co. 9-bis DL 179/2012, conv. L. 221/2012"
    elif modalita == "duplicato":
        tipo_attestazione = "duplicato informatico"
        norma_specifica = "art. 16-bis co. 9-bis DL 179/2012, conv. L. 221/2012"
    else:
        tipo_attestazione = "copia informatica estratta dal fascicolo informatico"
        norma_specifica = "art. 16-bis co. 9-bis DL 179/2012, conv. L. 221/2012"

    testo = f"""ATTESTAZIONE DI CONFORMITA'
(Art. 16-bis co. 9-bis DL 179/2012 — Art. 16-undecies DL 179/2012)

Il sottoscritto Avv. {avvocato}, in qualità di difensore di parte nel procedimento indicato in atti,

ATTESTA

ai sensi dell'{norma_specifica}, che la {tipo_attestazione} del seguente documento:

{tipo_documento}

Estremi: {estremi_originale}

è conforme all'originale {("analogico" if modalita == "copia_informatica" else "contenuto nel fascicolo informatico")}.

La presente attestazione è resa ai sensi dell'art. 16-undecies del DL 18 ottobre 2012, n. 179, convertito con modificazioni dalla L. 17 dicembre 2012, n. 221.

Luogo e data _______________

Avv. {avvocato}
(firmato digitalmente)"""

    return {
        "testo": testo,
        "tipo_atto": "attestazione_conformita",
        "modalita": modalita,
        "riferimento_normativo": "Art. 16-bis co. 9-bis DL 179/2012 — Art. 16-undecies DL 179/2012",
    }


@mcp.tool()
def relata_notifica_pec(
    avvocato: str,
    destinatario: str,
    pec_destinatario: str,
    atto_notificato: str,
    data_invio: str,
) -> dict:
    """Relata di notifica a mezzo PEC ex L. 53/1994.

    Args:
        avvocato: Nome dell'avvocato notificante
        destinatario: Nome del destinatario della notifica
        pec_destinatario: Indirizzo PEC del destinatario
        atto_notificato: Descrizione dell'atto notificato
        data_invio: Data di invio PEC (YYYY-MM-DD)
    """
    dt = _parse_date(data_invio)
    data_fmt = dt.strftime("%d/%m/%Y")

    testo = f"""RELATA DI NOTIFICAZIONE A MEZZO PEC
(L. 21 gennaio 1994, n. 53, come modificata dalla L. 228/2012)

Il sottoscritto Avv. {avvocato}, autorizzato dal Consiglio dell'Ordine ai sensi dell'art. 1 della L. 53/1994,

CERTIFICA

di aver notificato in data {data_fmt} a mezzo posta elettronica certificata il seguente atto:

{atto_notificato}

al seguente destinatario:

{destinatario}
Indirizzo PEC: {pec_destinatario}

L'indirizzo PEC del destinatario è stato estratto da pubblici elenchi (INI-PEC / ReGIndE / Registro Imprese), come previsto dall'art. 3-bis co. 1 della L. 53/1994.

DICHIARA

1. Che il messaggio di posta elettronica certificata è stato inviato dall'indirizzo PEC del sottoscritto risultante da pubblici elenchi;
2. Che l'atto notificato è stato trasmesso in formato PDF conforme all'originale;
3. Che si è provveduto a inserire nella busta di trasporto la relazione di notificazione sottoscritta digitalmente;
4. Che la ricevuta di accettazione e la ricevuta di avvenuta consegna sono state conservate agli atti.

Ai sensi dell'art. 3-bis co. 3 della L. 53/1994, la notifica si intende perfezionata nel momento in cui è generata la ricevuta di avvenuta consegna (RdAC).

Luogo e data _______________

Avv. {avvocato}
(firmato digitalmente)"""

    return {
        "testo": testo,
        "tipo_atto": "relata_notifica_pec",
        "data_invio": data_invio,
        "destinatario": destinatario,
        "pec_destinatario": pec_destinatario,
        "riferimento_normativo": "L. 53/1994 — Art. 3-bis, Notificazioni a mezzo PEC",
    }


@mcp.tool()
def indice_documenti(documenti: list[dict]) -> dict:
    """Genera indice numerato documenti per deposito telematico PCT.

    Args:
        documenti: Lista di documenti, ciascuno con chiavi: numero (int), descrizione (str), pagine (int)
    """
    righe = []
    totale_pagine = 0
    for doc in documenti:
        num = doc.get("numero", 0)
        desc = doc.get("descrizione", "")
        pag = doc.get("pagine", 0)
        totale_pagine += pag
        righe.append(f"Doc. {num:>3}  —  {desc:<60s}  (pagg. {pag})")

    intestazione = "INDICE DEI DOCUMENTI ALLEGATI\n" + "=" * 80
    footer = f"\n{'=' * 80}\nTotale documenti: {len(documenti)} — Totale pagine: {totale_pagine}"

    testo = intestazione + "\n\n" + "\n".join(righe) + footer

    return {
        "testo": testo,
        "tipo_atto": "indice_documenti",
        "totale_documenti": len(documenti),
        "totale_pagine": totale_pagine,
        "riferimento_normativo": "Specifiche tecniche PCT — DM 44/2011",
    }


@mcp.tool()
def note_trattazione_scritta(
    avvocato: str,
    parte: str,
    tribunale: str,
    rg_numero: str,
    giudice: str,
    conclusioni: str,
) -> dict:
    """Note di trattazione scritta ex art. 127-ter c.p.c. (sostituzione udienza).

    Args:
        avvocato: Nome dell'avvocato
        parte: Nome della parte
        tribunale: Denominazione del tribunale
        rg_numero: Numero di Ruolo Generale
        giudice: Nome del giudice
        conclusioni: Testo delle conclusioni e istanze
    """
    testo = f"""{tribunale.upper()}
Sezione ___

R.G. n. {rg_numero}
Giudice: {giudice}

NOTE DI TRATTAZIONE SCRITTA
(Art. 127-ter c.p.c.)

Nell'interesse di: {parte}
Difeso da: Avv. {avvocato}

***

Il sottoscritto difensore, ai sensi dell'art. 127-ter c.p.c., in sostituzione dell'udienza fissata per il giorno ___, deposita le seguenti

NOTE SCRITTE

Premesso che la causa verte su _______________,

si osserva quanto segue:

_______________________________________________
_______________________________________________

CONCLUSIONI

{conclusioni}

***

Si chiede che il Giudice voglia provvedere come in conclusioni.

Si producono i seguenti documenti:
_______________________________________________

Con osservanza.

Luogo e data _______________

Avv. {avvocato}"""

    return {
        "testo": testo,
        "tipo_atto": "note_trattazione_scritta",
        "rg_numero": rg_numero,
        "riferimento_normativo": "Art. 127-ter c.p.c. — Deposito di note scritte in sostituzione dell'udienza",
    }


@mcp.tool()
def sfratto_morosita(
    locatore: str,
    conduttore: str,
    immobile: str,
    canone_mensile: float,
    mensilita_insolute: int,
    data_contratto: str,
) -> dict:
    """Genera intimazione di sfratto per morosità ex art. 658 c.p.c. con citazione per convalida.

    Args:
        locatore: Nome del locatore
        conduttore: Nome del conduttore
        immobile: Descrizione dell'immobile (indirizzo, dati catastali)
        canone_mensile: Canone mensile in euro
        mensilita_insolute: Numero di mensilità non pagate
        data_contratto: Data del contratto di locazione (YYYY-MM-DD)
    """
    totale_dovuto = round(canone_mensile * mensilita_insolute, 2)
    dt_contratto = _parse_date(data_contratto)

    testo = f"""ATTO DI INTIMAZIONE DI SFRATTO PER MOROSITA'
CON CONTESTUALE CITAZIONE PER LA CONVALIDA
(Artt. 658 e ss. c.p.c.)

TRIBUNALE DI _______________

Il/La sottoscritto/a {locatore}, C.F. ___, residente in ___, rappresentato/a e difeso/a dall'Avv. ___, giusta procura in calce/a margine,

PREMESSO

— che in data {dt_contratto.strftime('%d/%m/%Y')} è stato stipulato un contratto di locazione avente ad oggetto l'immobile sito in {immobile};
— che il canone mensile pattuito ammonta ad Euro {canone_mensile:,.2f};
— che il/la conduttore/trice {conduttore} si è reso/a moroso/a nel pagamento di n. {mensilita_insolute} mensilità, per un importo complessivo di Euro {totale_dovuto:,.2f};
— che, nonostante i solleciti, il/la conduttore/trice non ha provveduto al pagamento;

INTIMA

a {conduttore}, C.F. ___, residente in ___,

lo sfratto dall'immobile sopra descritto per morosità nel pagamento del canone, e contestualmente

CITA

il/la medesimo/a {conduttore} a comparire avanti al Tribunale di ___, all'udienza del ___ ore ___, per ivi sentir convalidare lo sfratto ai sensi dell'art. 663 c.p.c.

Con espresso avvertimento che:
1. Se il/la convenuto/a non comparirà o comparendo non si opporrà, il Giudice convaliderà lo sfratto (art. 663 co. 1 c.p.c.);
2. Il/La convenuto/a potrà evitare la convalida pagando, prima dell'udienza, tutti i canoni scaduti e le spese del procedimento;
3. Il Giudice potrà concedere al conduttore un termine non superiore a 90 giorni (cd. "termine di grazia") per il pagamento dei canoni scaduti (art. 55 L. 392/1978).

Si chiede inoltre la condanna del/la convenuto/a al pagamento di:
— Euro {totale_dovuto:,.2f} per canoni scaduti e non pagati;
— canoni a scadere fino all'effettivo rilascio;
— spese e competenze del procedimento.

Si allegano:
1. Contratto di locazione
2. Diffida al pagamento
3. Procura alle liti

[Luogo], [Data]
Avv. _______________"""

    return {
        "testo": testo,
        "tipo_atto": "sfratto_morosita",
        "canone_mensile": canone_mensile,
        "mensilita_insolute": mensilita_insolute,
        "totale_dovuto": totale_dovuto,
        "riferimento_normativo": "Artt. 658-669 c.p.c. — Art. 55 L. 392/1978",
    }


@mcp.tool()
def atto_di_precetto(
    creditore: str,
    debitore: str,
    titolo_esecutivo: str,
    importo_capitale: float,
    interessi: float = 0,
    spese: float = 0,
) -> dict:
    """Genera atto di precetto ex art. 480 c.p.c.

    Args:
        creditore: Nome del creditore
        debitore: Nome del debitore
        titolo_esecutivo: Descrizione del titolo esecutivo (sentenza, decreto ingiuntivo, etc.)
        importo_capitale: Importo del capitale in euro
        interessi: Interessi maturati in euro
        spese: Spese legali e di procedimento in euro
    """
    totale = round(importo_capitale + interessi + spese, 2)

    testo = f"""ATTO DI PRECETTO
(Art. 480 c.p.c.)

Il/La sottoscritto/a {creditore}, C.F. ___, residente/con sede in ___, rappresentato/a e difeso/a dall'Avv. ___, giusta procura in calce/a margine,

PREMESSO

— che è in possesso del seguente titolo esecutivo: {titolo_esecutivo};
— che il predetto titolo è stato ritualmente notificato in forma esecutiva;
— che il/la debitore/trice non ha ancora provveduto al pagamento delle somme dovute;

INTIMA

a {debitore}, C.F. ___, residente/con sede in ___,

di pagare, entro il termine di dieci giorni dalla notificazione del presente atto, la complessiva somma di Euro {totale:,.2f}, così composta:

— Capitale:                Euro {importo_capitale:>12,.2f}
— Interessi:               Euro {interessi:>12,.2f}
— Spese legali:            Euro {spese:>12,.2f}
— TOTALE:                  Euro {totale:>12,.2f}

oltre interessi dalla data odierna al saldo effettivo, oltre spese del presente atto di precetto e successive occorrende.

AVVERTE

il debitore che, ai sensi dell'art. 480 co. 2 c.p.c., può proporre opposizione al precetto ai sensi dell'art. 615 c.p.c. nel termine perentorio di venti giorni dalla notificazione del presente atto, e che, in mancanza di pagamento nel termine suindicato, si procederà ad esecuzione forzata.

Con riserva di ogni ulteriore diritto e azione.

[Luogo], [Data]

Avv. _______________
(per {creditore})"""

    return {
        "testo": testo,
        "tipo_atto": "atto_di_precetto",
        "importo_capitale": importo_capitale,
        "interessi": interessi,
        "spese": spese,
        "totale_intimato": totale,
        "riferimento_normativo": "Art. 480 c.p.c. — Forma del precetto",
    }


@mcp.tool()
def nota_precisazione_credito(
    creditore: str,
    debitore: str,
    procedura_esecutiva: str,
    capitale: float,
    interessi: float,
    spese_legali: float,
    spese_esecuzione: float,
) -> dict:
    """Nota di precisazione del credito ex art. 547 c.p.c. per procedure esecutive.

    Args:
        creditore: Nome del creditore
        debitore: Nome del debitore
        procedura_esecutiva: Estremi della procedura (es. R.G.E. 123/2024)
        capitale: Importo capitale in euro
        interessi: Interessi maturati in euro
        spese_legali: Spese legali in euro
        spese_esecuzione: Spese di esecuzione in euro
    """
    totale = round(capitale + interessi + spese_legali + spese_esecuzione, 2)

    testo = f"""NOTA DI PRECISAZIONE DEL CREDITO
(Art. 547 c.p.c.)

TRIBUNALE DI _______________

Procedura esecutiva n. {procedura_esecutiva}

Promossa da: {creditore}
Contro: {debitore}

***

Il/La sottoscritto/a Avv. ___, quale difensore di {creditore}, ai sensi dell'art. 547 c.p.c.,

PRECISA

il proprio credito come segue, aggiornato alla data odierna:

1. Capitale:                  Euro {capitale:>12,.2f}
2. Interessi maturati:        Euro {interessi:>12,.2f}
3. Spese legali:              Euro {spese_legali:>12,.2f}
4. Spese di esecuzione:       Euro {spese_esecuzione:>12,.2f}
   ——————————————————————————————————————
   TOTALE:                    Euro {totale:>12,.2f}

Oltre ulteriori interessi dalla data odierna al saldo effettivo al tasso legale vigente.

Si allegano:
1. Conteggio analitico degli interessi
2. Nota spese
3. Titolo esecutivo e precetto

Con osservanza.

[Luogo], [Data]

Avv. _______________"""

    return {
        "testo": testo,
        "tipo_atto": "nota_precisazione_credito",
        "capitale": capitale,
        "interessi": interessi,
        "spese_legali": spese_legali,
        "spese_esecuzione": spese_esecuzione,
        "totale_credito": totale,
        "riferimento_normativo": "Art. 547 c.p.c. — Dichiarazione del terzo e precisazione credito",
    }


@mcp.tool()
def dichiarazione_553_cpc(
    terzo_pignorato: str,
    debitore: str,
    procedura: str,
    tipo_rapporto: str = "conto_corrente",
) -> dict:
    """Modello di dichiarazione del terzo pignorato ex art. 547 c.p.c.

    Args:
        terzo_pignorato: Nome del terzo pignorato (banca, datore di lavoro, etc.)
        debitore: Nome del debitore esecutato
        procedura: Estremi della procedura esecutiva
        tipo_rapporto: conto_corrente, stipendio, altro
    """
    if tipo_rapporto == "conto_corrente":
        sezione_rapporto = f"""DICHIARA

1. Che alla data di notifica del pignoramento, il/la Sig./Sig.ra {debitore} risulta titolare dei seguenti rapporti:

   [ ] Conto corrente n. ___________ — Saldo alla data del pignoramento: Euro ___________
   [ ] Conto deposito n. ___________ — Saldo: Euro ___________
   [ ] Deposito titoli n. ___________ — Controvalore: Euro ___________
   [ ] Cassetta di sicurezza n. ___________
   [ ] Altro: ___________

2. Che il saldo disponibile, al netto delle somme impignorabili, è pari a Euro ___________.

3. Che le somme sono state vincolate ai sensi dell'art. 546 c.p.c.

4. [ ] Che non risultano sequestri, pignoramenti precedenti o cessioni su detti rapporti.
   [ ] Che risultano i seguenti vincoli preesistenti: ___________"""
    elif tipo_rapporto == "stipendio":
        sezione_rapporto = f"""DICHIARA

1. Che il/la Sig./Sig.ra {debitore} risulta dipendente con qualifica di ___________, assunto/a in data ___________.

2. Che la retribuzione netta mensile ammonta a Euro ___________.

3. Che la quota pignorabile ai sensi dell'art. 545 c.p.c. è pari a Euro ___________ (1/5 dello stipendio netto).

4. Che il TFR maturato alla data del pignoramento ammonta a Euro ___________.

5. [ ] Che non risultano cessioni del quinto, delegazioni di pagamento o pignoramenti precedenti.
   [ ] Che risultano i seguenti vincoli preesistenti: ___________"""
    else:
        sezione_rapporto = f"""DICHIARA

1. Che alla data di notifica del pignoramento risultano i seguenti rapporti con il/la Sig./Sig.ra {debitore}:
   ___________________________________________

2. Che le somme/beni dovuti ammontano a Euro ___________.

3. [ ] Che non risultano vincoli preesistenti.
   [ ] Che risultano i seguenti vincoli: ___________"""

    testo = f"""DICHIARAZIONE DEL TERZO PIGNORATO
(Art. 547 c.p.c.)

TRIBUNALE DI _______________

Procedura esecutiva n. {procedura}

***

Il/La sottoscritto/a, in qualità di legale rappresentante / responsabile dell'ufficio competente di:

{terzo_pignorato}

in relazione all'atto di pignoramento presso terzi notificato in data ___________, su istanza di ___________ nei confronti di {debitore},

{sezione_rapporto}

Ai sensi dell'art. 547 co. 3 c.p.c., in caso di mancata comparizione all'udienza o mancato invio della presente dichiarazione, il credito pignorato si considera non contestato nei termini indicati dal creditore procedente.

[Luogo], [Data]

{terzo_pignorato}
(Firma e timbro)"""

    return {
        "testo": testo,
        "tipo_atto": "dichiarazione_terzo_pignorato",
        "tipo_rapporto": tipo_rapporto,
        "riferimento_normativo": "Art. 547 c.p.c. — Dichiarazione del terzo",
    }


@mcp.tool()
def testimonianza_scritta(
    teste: str,
    capitoli_prova: list[str],
) -> dict:
    """Modello per testimonianza scritta ex art. 257-bis c.p.c.

    Args:
        teste: Nome completo del teste
        capitoli_prova: Lista dei capitoli di prova su cui il teste deve deporre
    """
    capitoli_formattati = []
    for i, cap in enumerate(capitoli_prova, 1):
        capitoli_formattati.append(
            f"Capitolo {i}: \"{cap}\"\n"
            f"   Risposta: [ ] Vero  [ ] Non vero  [ ] Non so\n"
            f"   Specificazioni: _______________________________________________"
        )

    testo = f"""MODULO PER TESTIMONIANZA SCRITTA
(Art. 257-bis c.p.c.)

TRIBUNALE DI _______________
R.G. n. _______________
Giudice: _______________

***

DATI DEL TESTE

Nome e Cognome: {teste}
Nato/a a: _______________  il: _______________
Residente in: _______________
C.F.: _______________
Professione: _______________

***

AMMONIZIONE (art. 251 c.p.c.)

Il/La teste è ammonito/a dal Giudice sull'importanza religiosa e morale del giuramento e sulle conseguenze penali delle dichiarazioni false o reticenti, e presta il seguente

GIURAMENTO

"Consapevole della responsabilità morale e giuridica che assumo con la mia deposizione, mi impegno a dire tutta la verità e a non nascondere nulla di quanto è a mia conoscenza."

Firma del teste: _______________

***

RISPOSTE AI CAPITOLI DI PROVA

{chr(10).join(capitoli_formattati)}

***

ISTRUZIONI PER IL TESTE:
1. Rispondere a ciascun capitolo barrando la casella corrispondente.
2. Se si risponde "Vero" o "Non vero", specificare nelle righe sottostanti i fatti a propria conoscenza.
3. Non è possibile deporre su fatti appresi da terzi (testimonianza de relato).
4. Il modulo deve essere restituito compilato e firmato entro il termine assegnato dal Giudice.
5. La mancata restituzione può comportare le sanzioni di cui all'art. 255 c.p.c.

Data compilazione: _______________

Firma del teste: _______________

AUTENTICAZIONE
(a cura del segretario comunale o di altro pubblico ufficiale)

Certifico che la firma è stata apposta in mia presenza da persona della cui identità mi sono accertato.

Timbro e firma: _______________"""

    return {
        "testo": testo,
        "tipo_atto": "testimonianza_scritta",
        "numero_capitoli": len(capitoli_prova),
        "riferimento_normativo": "Art. 257-bis c.p.c. — Testimonianza scritta",
    }


@mcp.tool()
def istanza_visibilita_fascicolo(
    avvocato: str,
    parte: str,
    tribunale: str,
    rg_numero: str,
    motivo: str = "costituzione",
) -> dict:
    """Istanza di visibilità del fascicolo telematico per avvocati non ancora costituiti.

    Args:
        avvocato: Nome dell'avvocato richiedente
        parte: Nome della parte assistita
        tribunale: Denominazione del tribunale
        rg_numero: Numero di Ruolo Generale
        motivo: costituzione, consultazione, intervento
    """
    motivi_testo = {
        "costituzione": "di doversi costituire nel procedimento sopra indicato in qualità di difensore della parte convenuta/resistente e necessitando pertanto di prendere visione degli atti contenuti nel fascicolo telematico per predisporre la propria difesa",
        "consultazione": "di avere interesse alla consultazione del fascicolo telematico del procedimento sopra indicato ai fini della tutela degli interessi della parte assistita",
        "intervento": "di doversi costituire nel procedimento sopra indicato mediante atto di intervento ex art. 105 c.p.c. e necessitando pertanto di prendere visione degli atti del fascicolo telematico",
    }

    motivo_desc = motivi_testo.get(motivo, motivi_testo["costituzione"])

    testo = f"""ISTANZA DI VISIBILITA' DEL FASCICOLO TELEMATICO

Al Sig. {tribunale}
Ufficio _______________

R.G. n. {rg_numero}

***

Il sottoscritto Avv. {avvocato}, C.F. ___, del Foro di ___, con studio in ___, PEC: ___,

nell'interesse di {parte}, C.F. ___,

ESPONE

{motivo_desc};

che allo stato attuale il fascicolo telematico non risulta visibile al sottoscritto difensore, non essendosi ancora costituito in giudizio;

CHIEDE

che venga concessa la visibilità del fascicolo telematico relativo al procedimento R.G. n. {rg_numero}, al fine di consentire al sottoscritto difensore di prendere visione degli atti e documenti in esso contenuti.

Si allega copia del mandato difensivo.

Con osservanza.

[Luogo], [Data]

Avv. {avvocato}
(firmato digitalmente)"""

    return {
        "testo": testo,
        "tipo_atto": "istanza_visibilita_fascicolo",
        "motivo": motivo,
        "rg_numero": rg_numero,
        "riferimento_normativo": "Art. 16-bis DL 179/2012 — Specifiche tecniche PCT (DM 44/2011)",
    }


@mcp.tool()
def cerca_ufficio_giudiziario(
    comune: str,
    tipo: str = "tribunale",
) -> dict:
    """Lookup ufficio giudiziario competente per territorio.

    Args:
        comune: Nome del comune
        tipo: tribunale, giudice_pace
    """
    key = comune.lower().strip()
    entry = _TRIBUNALI_COMPETENTI.get(key)

    if entry:
        ufficio = entry.get(tipo, entry.get("tribunale", "Non trovato"))
        return {
            "comune": comune,
            "tipo": tipo,
            "ufficio_competente": ufficio,
            "trovato": True,
            "nota": "Dato basato sui principali circondari italiani. Verificare su sito Ministero della Giustizia per comuni minori.",
            "riferimento_normativo": "R.D. 30 gennaio 1941 n. 12 — Ordinamento giudiziario",
        }

    # Fuzzy: try to find partial match
    parziali = [
        (k, v) for k, v in _TRIBUNALI_COMPETENTI.items()
        if key in k or k in key
    ]

    if parziali:
        risultati = [
            {"comune": k.title(), "ufficio": v.get(tipo, v.get("tribunale"))}
            for k, v in parziali
        ]
        return {
            "comune": comune,
            "tipo": tipo,
            "trovato": False,
            "suggerimenti": risultati,
            "nota": "Comune non trovato esattamente. Possibili corrispondenze elencate.",
            "riferimento_normativo": "R.D. 30 gennaio 1941 n. 12 — Ordinamento giudiziario",
        }

    return {
        "comune": comune,
        "tipo": tipo,
        "trovato": False,
        "nota": f"Comune '{comune}' non presente nella tabella dei principali circondari. Consultare il sito del Ministero della Giustizia per la competenza territoriale.",
        "riferimento_normativo": "R.D. 30 gennaio 1941 n. 12 — Ordinamento giudiziario",
    }
