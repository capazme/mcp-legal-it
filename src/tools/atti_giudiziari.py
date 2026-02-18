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
