"""Calcoli e generazione di atti giudiziari: Contributo Unificato (DPR 115/2002), diritti di copia
(cartacei e PCT), pignoramento stipendio (art. 545 c.p.c.), imposta di registro su atti giudiziari.
Generazione bozze: sollecito pagamento, decreto ingiuntivo, precetto, sfratto per morosità,
procura alle liti, attestazione conformità PCT, relata PEC, note trattazione scritta e altri atti."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from src.server import mcp
from src.lib._data import sourced

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "contributo_unificato.json") as f:
    _CU = json.load(f)

with open(_DATA / "tassi_mora.json") as f:
    _TASSI_MORA = json.load(f)["tassi"]

with open(_DATA / "tribunali_competenti.json") as f:
    _TRIBUNALI_COMPETENTI = {
        k: v for k, v in json.load(f).items() if not k.startswith("_")
    }  # `_`-prefixed keys are metadata (see src/lib/_data.py), not records

with open(_DATA / "codici_ruolo.json") as f:
    _CODICI_RUOLO = json.load(f)["codici"]


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _days_in_year(year: int) -> int:
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


def _get_tasso_mora(d: date) -> dict:
    for t in _TASSI_MORA:
        if _parse_date(t["dal"]) <= d <= _parse_date(t["al"]):
            return t
    if d > _parse_date(_TASSI_MORA[-1]["al"]):
        return _TASSI_MORA[-1]
    return None


def _lookup_scaglione(scaglioni: list, valore: float) -> float:
    for s in scaglioni:
        if "fino_a" in s and valore <= s["fino_a"]:
            return s["importo"]
        if "oltre" in s:
            return s["importo"]
    return scaglioni[-1]["importo"]


#: I tipi di procedimento che `_calcola_cu_base` conosce (docstring del tool e validazione).
_TIPI_CU = (
    "cognizione", "valore_indeterminabile", "valore_indeterminabile_gdp", "monitorio",
    "opposizione_decreto_ingiuntivo", "opposizione_atti_esecutivi", "esecuzione_immobiliare",
    "esecuzione_mobiliare", "cautelari", "volontaria_giurisdizione", "separazione_consensuale",
    "separazione_giudiziale", "divorzio_congiunto", "divorzio_giudiziale", "lavoro", "previdenza",
    "tributario", "tar",
)


def _calcola_cu_base(
    valore_causa: float,
    tipo_procedimento: str,
    tabella: dict | None = None,
    reddito_oltre_soglia: bool = False,
) -> float:
    """Calcola CU base primo grado.

    `tabella` is a replacement table supplied by the caller (the `alternativa`
    parameter of the `contributo_unificato` tool): when given, nothing is read
    from the shipped file, so the answer rests entirely on the caller's data.
    `reddito_oltre_soglia` is the art. 9 co. 1-bis condition for labour and
    welfare cases: the contribution is due only above three times the art. 76
    income threshold.
    """
    if tipo_procedimento not in _TIPI_CU:
        raise ValueError(
            f"tipo_procedimento non valido: {tipo_procedimento!r}; valori ammessi: {', '.join(_TIPI_CU)}"
        )
    cu = tabella if tabella is not None else _CU
    civile = cu["civile"]

    # Procedimenti a importo fisso
    fissi = {
        "esecuzione_immobiliare": civile["esecuzione_immobiliare"],
        "volontaria_giurisdizione": civile["volontaria_giurisdizione"],
        "separazione_consensuale": civile["separazione_consensuale"],
        "separazione_giudiziale": civile["separazione_giudiziale"],
        "divorzio_congiunto": civile["divorzio_congiunto"],
        "divorzio_giudiziale": civile["divorzio_giudiziale"],
    }
    if tipo_procedimento in fissi:
        return fissi[tipo_procedimento]

    # Esecuzione mobiliare: fisso 43 fino a 2.500 euro, 139 oltre (art. 13, c. 2)
    if tipo_procedimento == "esecuzione_mobiliare":
        return _lookup_scaglione(civile["esecuzione_mobiliare"]["scaglioni"], valore_causa)

    # Cautelari: ridotti del 50% della tabella ordinaria per valore
    if tipo_procedimento == "cautelari":
        return _lookup_scaglione(civile["cognizione"], valore_causa) * civile["cautelari"][
            "riduzione"
        ]

    # Cognizione (scaglioni per valore)
    if tipo_procedimento == "cognizione":
        return _lookup_scaglione(civile["cognizione"], valore_causa)

    # Valore indeterminabile: 518 in tribunale (lett. d), 237 davanti al giudice di pace (lett. c)
    if tipo_procedimento == "valore_indeterminabile":
        return civile["valore_indeterminabile"]
    if tipo_procedimento == "valore_indeterminabile_gdp":
        return civile["cognizione"][2]["importo"]

    # Monitorio e opposizione a decreto ingiuntivo (scaglioni dimezzati, art. 13 co. 3)
    if tipo_procedimento == "monitorio":
        return _lookup_scaglione(civile["procedimento_monitorio"]["scaglioni"], valore_causa)
    if tipo_procedimento == "opposizione_decreto_ingiuntivo":
        return _lookup_scaglione(civile["opposizione_decreto_ingiuntivo"]["scaglioni"], valore_causa)

    # Opposizione agli atti esecutivi: importo fisso (art. 13 co. 2, ultimo periodo)
    if tipo_procedimento == "opposizione_atti_esecutivi":
        return civile["opposizione_atti_esecutivi"]["importo"]

    # Lavoro e previdenza (art. 9 co. 1-bis): esenti fino a tre volte la soglia dell'art. 76;
    # oltre, previdenza alla lett. a) (43 euro) e lavoro alla meta' dello scaglione (co. 3)
    if tipo_procedimento == "previdenza":
        return civile["cognizione"][0]["importo"] if reddito_oltre_soglia else 0.0
    if tipo_procedimento == "lavoro":
        if not reddito_oltre_soglia:
            return 0.0
        return round(_lookup_scaglione(civile["cognizione"], valore_causa) / 2, 2)

    # Tributario (art. 13 co. 6-quater: stessi importi in primo e secondo grado)
    if tipo_procedimento == "tributario":
        return _lookup_scaglione(cu["tributario"]["scaglioni"], valore_causa)

    # TAR
    if tipo_procedimento == "tar":
        return cu["amministrativo"]["tar_ordinario"]

    return _lookup_scaglione(civile["cognizione"], valore_causa)


@mcp.tool(tags={"giudiziario", "credito", "sinistro"})
@sourced("contributo_unificato", alternativa="tabella_contributo_unificato")
def contributo_unificato(
    valore_causa: float,
    tipo_procedimento: str = "cognizione",
    grado: str = "primo",
    tabella_contributo_unificato: dict | None = None,
    reddito_oltre_soglia_lavoro: bool = False,
) -> dict:
    """Calcola il Contributo Unificato per valore della causa, tipo di procedimento e grado.
    Vigenza: DPR 115/2002, art. 13 (importi del testo vigente riscontrati su Normattiva il
    20/09/2026), art. 9 co. 1-bis (lavoro e previdenza), art. 13 co. 6-quater (tributario).
    Precisione: ESATTO (scaglioni per valore; +50% in appello e raddoppio in Cassazione ex art. 13
    co. 1-bis; per lavoro/previdenza e tributario in Cassazione verificare con cite_law).
    Spesso chiamato insieme a decreto_ingiuntivo() o prima di avviare una causa civile.

    Args:
        valore_causa: Valore della causa in euro (€)
        tipo_procedimento: Tipo di rito: 'cognizione', 'valore_indeterminabile' (518 in tribunale),
                           'valore_indeterminabile_gdp' (237 davanti al giudice di pace),
                           'monitorio' e 'opposizione_decreto_ingiuntivo' (metà, art. 13 co. 3),
                           'opposizione_atti_esecutivi' (168 fisso), 'esecuzione_immobiliare' (278),
                           'esecuzione_mobiliare' (43 sotto 2.500, 139 oltre), 'cautelari' (metà),
                           'volontaria_giurisdizione', 'separazione_consensuale',
                           'separazione_giudiziale', 'divorzio_congiunto', 'divorzio_giudiziale',
                           'lavoro' e 'previdenza' (esenti salvo reddito oltre tre volte la soglia
                           dell'art. 76: allora previdenza 43 euro e lavoro metà scaglione),
                           'tributario' (art. 13 co. 6-quater, stessi importi in appello), 'tar'
        grado: Grado del giudizio: 'primo', 'appello', 'cassazione'
        reddito_oltre_soglia_lavoro: Solo per 'lavoro' e 'previdenza': True se la parte ha un reddito
                           imponibile superiore a tre volte la soglia dell'art. 76 DPR 115/2002
                           (art. 9 co. 1-bis); False (default) = esente
        tabella_contributo_unificato: Tabella sostitutiva fornita dal chiamante, con la
                          stessa struttura di src/data/contributo_unificato.json (almeno
                          'civile', 'tributario', 'appello', 'cassazione'). Se la fornisci,
                          il calcolo non legge la tabella inclusa: utile se vuoi garantire
                          tu la vigenza degli importi o applicare una tabella aggiornata di
                          cui disponi
    """
    if valore_causa < 0:
        return {"errore": "valore_causa non può essere negativo"}
    if grado not in ("primo", "appello", "cassazione"):
        return {"errore": f"grado non valido: {grado}", "valori_ammessi": ["primo", "appello", "cassazione"]}

    tabella = tabella_contributo_unificato or _CU
    try:
        cu_base = _calcola_cu_base(
            valore_causa, tipo_procedimento, tabella_contributo_unificato, reddito_oltre_soglia_lavoro
        )
    except ValueError as exc:
        return {"errore": str(exc), "valori_ammessi": list(_TIPI_CU)}

    note = []
    moltiplicatore = 1.0
    if grado == "appello":
        if tipo_procedimento == "tributario":
            # Art. 13 co. 6-quater: gli importi valgono per i ricorsi in primo e in secondo grado
            note.append("Tributario in appello: stessi importi del primo grado (art. 13 co. 6-quater)")
        elif tipo_procedimento in ("lavoro", "previdenza") and not reddito_oltre_soglia_lavoro:
            note.append("Lavoro/previdenza: esente anche in appello sotto la soglia di reddito (art. 9 co. 1-bis)")
        else:
            moltiplicatore = tabella["appello"]["moltiplicatore"]
    elif grado == "cassazione":
        if tipo_procedimento in ("lavoro", "previdenza"):
            if reddito_oltre_soglia_lavoro:
                # Art. 9 co. 1-bis: in Cassazione il contributo e' dovuto nella misura dell'art. 13 co. 1
                cu_base = _lookup_scaglione(tabella["civile"]["cognizione"], valore_causa)
                moltiplicatore = tabella["cassazione"]["moltiplicatore"]
                note.append("Lavoro/previdenza in Cassazione oltre soglia: importo pieno dell'art. 13 co. 1, raddoppiato ex co. 1-bis")
            else:
                note.append("Lavoro/previdenza: esente anche in Cassazione sotto la soglia di reddito (art. 9 co. 1-bis)")
        elif tipo_procedimento == "tributario":
            # Il co. 6-quater copre solo i gradi di merito: in Cassazione si applica la scala civile
            cu_base = _lookup_scaglione(tabella["civile"]["cognizione"], valore_causa)
            moltiplicatore = tabella["cassazione"]["moltiplicatore"]
            note.append("Tributario in Cassazione: scala civile dell'art. 13 co. 1, raddoppiata ex co. 1-bis (verificare)")
        else:
            moltiplicatore = tabella["cassazione"]["moltiplicatore"]

    importo = round(cu_base * moltiplicatore, 2)

    result = {
        "valore_causa": valore_causa,
        "tipo_procedimento": tipo_procedimento,
        "grado": grado,
        "cu_base": cu_base,
        "moltiplicatore": moltiplicatore,
        "importo_dovuto": importo,
        "riferimento_normativo": "DPR 115/2002, art. 13 — Testo Unico Spese di Giustizia",
    }
    if tipo_procedimento in ("lavoro", "previdenza"):
        result["reddito_oltre_soglia_lavoro"] = reddito_oltre_soglia_lavoro
        result["riferimento_normativo"] += "; art. 9 co. 1-bis (esenzione fino a tre volte la soglia dell'art. 76)"
    if note:
        result["note"] = note
    return result


@mcp.tool(tags={"giudiziario"})
def diritti_copia(
    n_pagine: int,
    tipo: str = "semplice",
    formato: str = "digitale",
    urgente: bool = False,
) -> dict:
    """Calcola i diritti di copia per atti giudiziari in formato cartaceo e digitale PCT.
    Vigenza: DPR 115/2002, artt. 267-270, Tabella 8; DL 90/2014 conv. L. 114/2014
    (copie semplici digitali gratuite).
    Precisione: INDICATIVO (gli importi degli allegati 6, 7 e 8 al DPR 115/2002 sono adeguati
        periodicamente ex art. 274 e la maggiorazione per urgenza ex art. 270 va verificata sul
        testo vigente: i valori inclusi sono indicativi; resta esatta la gratuità della copia
        semplice digitale)

    Args:
        n_pagine: Numero di pagine dell'atto (intero positivo)
        tipo: Tipo di copia: 'semplice', 'autentica', 'esecutiva'
        formato: Formato di rilascio: 'digitale' (PCT — gratuito se semplice) o 'cartaceo'
        urgente: True per maggiorazione urgenza +50% (solo per formato cartaceo)
    """
    if formato not in ("digitale", "cartaceo"):
        return {"errore": "formato deve essere 'digitale' o 'cartaceo'"}
    if tipo not in ("semplice", "autentica", "esecutiva"):
        return {"errore": "tipo deve essere 'semplice', 'autentica' o 'esecutiva'"}
    if n_pagine <= 0:
        return {"errore": "n_pagine deve essere un intero positivo"}

    if formato == "digitale":
        if tipo == "semplice":
            # Copie semplici digitali gratuite (art. 40 DPR 115/2002 mod. DL 90/2014)
            totale = 0.0
            nota = "Copia semplice digitale gratuita (art. 40 DPR 115/2002 mod. DL 90/2014)"
        else:
            # Copie autentiche/esecutive digitali: tariffa forfettaria
            if n_pagine <= 4:
                totale = 1.62
            elif n_pagine <= 10:
                totale = 4.05
            elif n_pagine <= 20:
                totale = 6.48
            elif n_pagine <= 50:
                totale = 8.11
            else:
                totale = 10.13 + (n_pagine - 50) // 50 * 1.62
                totale = round(totale, 2)
            nota = f"Copia {tipo} digitale — tariffa forfettaria DPR 115/2002 Tabella 8"

        return {
            "n_pagine": n_pagine,
            "tipo": tipo,
            "formato": formato,
            "totale": round(totale, 2),
            "nota": nota,
            "riferimento_normativo": "DPR 115/2002, art. 267-270, Tabella 8 — DL 90/2014 conv. L. 114/2014",
        }

    # Cartaceo (original logic)
    tariffe = {
        "semplice": 0.30,
        "autentica": 0.70,
        "esecutiva": 0.70,
    }
    tariffa_pagina = tariffe[tipo]
    subtotale = round(n_pagine * tariffa_pagina, 2)
    maggiorazione_urgenza = round(subtotale * 0.5, 2) if urgente else 0.0
    totale = round(subtotale + maggiorazione_urgenza, 2)

    result = {
        "n_pagine": n_pagine,
        "tipo": tipo,
        "formato": formato,
        "tariffa_pagina": tariffa_pagina,
        "subtotale": subtotale,
        "urgente": urgente,
        "totale": totale,
        "riferimento_normativo": "DPR 115/2002, artt. 267-270",
    }
    if urgente:
        result["maggiorazione_urgenza"] = maggiorazione_urgenza
    return result


#: Assegno sociale mensile usato per il minimo impignorabile delle pensioni (art. 545 co. 7
#: c.p.c.: il doppio dell'assegno sociale, con un minimo di 1.000 euro). L'importo e' quello
#: del 2024 (534,41 euro) e va aggiornato ogni anno sulla circolare INPS: il chiamante puo'
#: passare il valore corrente con `assegno_sociale_mensile`.
_ASSEGNO_SOCIALE_MENSILE = 534.41
_ASSEGNO_SOCIALE_ANNO = 2024
_MINIMO_IMPIGNORABILE_PENSIONI = 1000.0


@mcp.tool(tags={"giudiziario", "credito"})
def pignoramento_stipendio(
    stipendio_netto_mensile: float,
    tipo_credito: str = "ordinario",
    pensione: bool = False,
    assegno_sociale_mensile: float | None = None,
) -> dict:
    """Calcola le quote pignorabili dello stipendio o della pensione ex art. 545 c.p.c.
    Vigenza: art. 545 c.p.c. (co. 3-5 per stipendi; co. 7 per le pensioni nel testo dell'art.
    21-bis DL 115/2022 conv. L. 142/2022: impignorabile il doppio dell'assegno sociale con un
    minimo di 1.000 euro; co. 8 per le somme accreditate su conto); art. 72-ter DPR 602/1973 per
    i crediti fiscali dell'agente della riscossione.
    Precisione: ESATTO per le quote di legge (1/5 ordinario, fino a 1/3 alimentare, scaglioni
    fiscali); INDICATIVO per le pensioni, perché il minimo impignorabile dipende dall'assegno
    sociale dell'anno (incluso: 2024) — passare `assegno_sociale_mensile` aggiornato.

    Args:
        stipendio_netto_mensile: Stipendio o pensione netta mensile in euro (€)
        tipo_credito: Tipo di credito per cui si procede: 'ordinario' (1/5),
                      'alimentare' (fino a 1/3 — misura fissata dal giudice),
                      'fiscale' (scaglioni dell'agente della riscossione: 1/10, 1/7, 1/5),
                      'concorso_crediti' (fino a 1/2 in caso di concorso)
        pensione: True se la somma è una pensione: la quota si calcola solo sulla parte che
                  eccede il minimo impignorabile (doppio dell'assegno sociale, minimo 1.000 euro)
        assegno_sociale_mensile: Importo mensile dell'assegno sociale dell'anno corrente (facoltativo;
                  default il valore 2024 incluso nel server)
    """
    if stipendio_netto_mensile < 0:
        return {"errore": "stipendio_netto_mensile non può essere negativo"}
    if assegno_sociale_mensile is not None and assegno_sociale_mensile <= 0:
        return {"errore": "assegno_sociale_mensile deve essere positivo"}

    minimo_vitale = assegno_sociale_mensile if assegno_sociale_mensile is not None else _ASSEGNO_SOCIALE_MENSILE
    impignorabile_pensioni = max(2 * minimo_vitale, _MINIMO_IMPIGNORABILE_PENSIONI)
    # Art. 545 co. 7: la quota si applica alla sola parte eccedente il minimo impignorabile
    base = stipendio_netto_mensile
    if pensione:
        base = max(stipendio_netto_mensile - impignorabile_pensioni, 0.0)

    if tipo_credito == "ordinario":
        quota = 1 / 5
        descrizione = "1/5 dello stipendio netto (art. 545 co. 4 c.p.c.)"
    elif tipo_credito == "alimentare":
        quota = 1 / 3
        descrizione = "Fino a 1/3 dello stipendio netto (art. 545 co. 3 c.p.c.) — misura fissata dal giudice"
    elif tipo_credito == "fiscale":
        # Scaglioni art. 72-ter DPR 602/1973 (introdotto dal DL 16/2012, conv. L. 44/2012)
        if stipendio_netto_mensile <= 2500:
            quota = 1 / 10
            descrizione = "1/10 — stipendio netto ≤ €2.500 (art. 72-ter DPR 602/73)"
        elif stipendio_netto_mensile <= 5000:
            quota = 1 / 7
            descrizione = "1/7 — stipendio netto €2.500-5.000 (art. 72-ter DPR 602/73)"
        else:
            quota = 1 / 5
            descrizione = "1/5 — stipendio netto > €5.000 (art. 72-ter DPR 602/73)"
    elif tipo_credito == "concorso_crediti":
        quota = 1 / 2
        descrizione = "Fino a 1/2 in caso di concorso di crediti (art. 545 co. 5 c.p.c.)"
    else:
        return {"errore": f"tipo_credito non riconosciuto: {tipo_credito}"}

    pignorabile = round(base * quota, 2)
    non_pignorabile = round(stipendio_netto_mensile - pignorabile, 2)

    result = {
        "stipendio_netto_mensile": stipendio_netto_mensile,
        "pensione": pensione,
        "tipo_credito": tipo_credito,
        "quota_pignorabile": round(quota, 4),
        "base_di_calcolo": round(base, 2),
        "importo_pignorabile": pignorabile,
        "importo_non_pignorabile": non_pignorabile,
        "assegno_sociale_mensile": minimo_vitale,
        "minimo_impignorabile_pensioni": round(impignorabile_pensioni, 2),
        "nota_pensioni": (
            f"Per le pensioni è impignorabile la parte fino al doppio dell'assegno sociale, con un "
            f"minimo di 1.000 euro (€{impignorabile_pensioni:.2f} con l'assegno sociale indicato); la "
            f"quota si applica solo all'eccedenza (art. 545 co. 7 c.p.c.). Assegno sociale incluso: "
            f"anno {_ASSEGNO_SOCIALE_ANNO} — aggiornarlo con `assegno_sociale_mensile`."
        ),
        "nota_conto_corrente": (
            "Somme accreditate su conto prima del pignoramento: pignorabili solo oltre il triplo "
            "dell'assegno sociale (art. 545 co. 8 c.p.c.)"
        ),
        "descrizione": descrizione,
        "riferimento_normativo": "Art. 545 c.p.c. (co. 7 nel testo dell'art. 21-bis DL 115/2022 conv. L. 142/2022); art. 72-ter DPR 602/1973",
    }
    if pensione and assegno_sociale_mensile is None:
        result["avvertenza"] = (
            f"Minimo impignorabile calcolato sull'assegno sociale {_ASSEGNO_SOCIALE_ANNO}: "
            "per l'anno in corso passare `assegno_sociale_mensile` dalla circolare INPS."
        )
    return result


@mcp.tool(tags={"giudiziario", "credito"})
@sourced("tassi_mora")
def sollecito_pagamento(
    creditore: str,
    debitore: str,
    importo: float,
    data_scadenza: str,
    data_sollecito: str,
    tasso_mora: float | None = None,
) -> dict:
    """Genera bozza di lettera di sollecito pagamento con calcolo degli interessi di mora.
    Vigenza: D.Lgs. 231/2002 (tasso BCE + 8 pp per crediti commerciali, aggiornato semestralmente);
    per tasso convenzionale indicare manualmente tasso_mora.
    Precisione: ESATTO per gli interessi (calcolo pro rata sul periodo di ritardo).

    Args:
        creditore: Nome o ragione sociale del creditore
        debitore: Nome o ragione sociale del debitore
        importo: Importo del credito in euro (€)
        data_scadenza: Data di scadenza originale del pagamento (YYYY-MM-DD)
        data_sollecito: Data odierna o di emissione del sollecito (YYYY-MM-DD)
        tasso_mora: Tasso di mora annuo personalizzato in percentuale (es. 8.5);
                    se None usa il tasso D.Lgs. 231/2002 (BCE + 8 pp) aggiornato
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
        # Reject scadenze before the mora rate table starts (no fallback rate applicable)
        primo_dal = _parse_date(_TASSI_MORA[0]["dal"])
        if dt_scadenza < primo_dal:
            return {
                "errore": f"Tasso di mora D.Lgs. 231/2002 non disponibile per scadenze anteriori al {primo_dal.strftime('%d/%m/%Y')}; indicare manualmente tasso_mora"
            }
        # Split by mora rate periods like interessi_mora()
        interessi_totali = 0.0
        current = dt_scadenza + timedelta(days=1)
        dt_sollecito_end = dt_sollecito
        while current <= dt_sollecito_end:
            info_mora = _get_tasso_mora(current)
            if info_mora is None:
                break
            period_end_raw = _parse_date(info_mora["al"])
            periodo_end = min(period_end_raw, dt_sollecito_end)
            giorni_periodo = (periodo_end - current).days + 1
            interessi_totali += importo * (info_mora["mora"] / 100) * giorni_periodo / _days_in_year(current.year)
            if periodo_end < current:
                break
            current = periodo_end + timedelta(days=1)
        interessi = round(interessi_totali, 2)
        info_mora = _get_tasso_mora(dt_scadenza)
        tasso_applicato = info_mora["mora"]
        base_giuridica_tasso = f"D.Lgs. 231/2002 — tasso BCE variabile per semestre (tasso iniziale {info_mora['bce']}% + 8 pp = {tasso_applicato}%)"

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


@mcp.tool(tags={"giudiziario", "credito"})
@sourced("contributo_unificato")
def decreto_ingiuntivo(
    creditore: str,
    debitore: str,
    importo: float,
    tipo_credito: str = "ordinario",
    provvisoria_esecuzione: bool = False,
) -> dict:
    """Genera bozza di ricorso per decreto ingiuntivo con calcolo della competenza per valore e CU.
    Vigenza: artt. 633-656 c.p.c.; art. 7 c.p.c. nel testo del D.Lgs. 149/2022 (giudice di pace fino
    a €10.000 dal 28/02/2023; l'innalzamento a €30.000 del D.Lgs. 116/2017 è stato più volte
    differito e non è in vigore); art. 413 c.p.c. per i crediti di lavoro (sempre tribunale);
    DPR 115/2002 (CU monitorio, metà ex art. 13 co. 3).
    Precisione: INDICATIVO per la bozza (richiede completamento con dati specifici del caso).
    Chaining: → contributo_unificato() per calcolare le spese di giustizia → parcella_avvocato_civile()

    Args:
        creditore: Nome o ragione sociale del creditore
        debitore: Nome o ragione sociale del debitore
        importo: Importo del credito in euro (€)
        tipo_credito: Natura del credito: 'ordinario', 'professionale' (parcella vidimata),
                      'condominiale' (delibera assembleare), 'cambiale', 'retribuzioni' (crediti di
                      lavoro: competenza del tribunale in funzione di giudice del lavoro)
        provvisoria_esecuzione: True per richiedere la clausola ex art. 642 c.p.c.
    """
    # Giudice competente: crediti di lavoro sempre al tribunale (art. 413 c.p.c.); per gli altri
    # per valore (art. 7 co. 1 c.p.c. post-Cartabia: giudice di pace fino a €10.000)
    if tipo_credito == "retribuzioni":
        giudice = "Tribunale — Sezione Lavoro"
    elif importo <= 10000:
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
        "termini": {
            "opposizione": "40 giorni dalla notifica del decreto (50 se l'ingiunto risiede in altro Stato UE, 60 fuori UE) — art. 641 c.p.c.",
            "notifica_decreto": "entro 60 giorni dalla pronuncia (90 se all'estero), altrimenti il decreto perde efficacia — art. 644 c.p.c.",
        },
        "riferimento_normativo": "Artt. 633-656 c.p.c.; art. 7 c.p.c. (competenza per valore); art. 413 c.p.c. (crediti di lavoro)",
    }


@mcp.tool(tags={"giudiziario"})
def calcolo_hash(testo: str) -> dict:
    """Calcola l'impronta hash SHA-256 di un testo per il deposito telematico PCT.
    Vigenza: DM 44/2011 — Specifiche tecniche PCT (algoritmo SHA-256 obbligatorio).
    Precisione: ESATTO (hash deterministico su testo UTF-8).

    Args:
        testo: Testo o contenuto del documento di cui calcolare l'impronta digitale
    """
    digest = hashlib.sha256(testo.encode("utf-8")).hexdigest()

    return {
        "algoritmo": "SHA-256",
        "hash": digest,
        "lunghezza_input": len(testo),
        "nota": "Impronta digitale conforme alle specifiche tecniche PCT (DM 44/2011)",
    }


@mcp.tool(tags={"giudiziario"})
def tassazione_atti(
    tipo_atto: str,
    valore: float,
    prima_casa: bool = False,
) -> dict:
    """Calcola l'imposta di registro dovuta su atti giudiziari.
    Vigenza: DPR 131/1986 — TU Imposta di Registro, Tariffa Parte I (tabelle vigenti).
    Precisione: ESATTO (imposta proporzionale 3% con minimo €200; 2% per prima casa su verbale).

    Args:
        tipo_atto: Tipo di atto giudiziario: 'sentenza_condanna' (3% proporzionale o €200 fisso),
                   'decreto_ingiuntivo' (3%), 'verbale_conciliazione' (3% o 2% prima casa),
                   'ordinanza' (€200 fisso)
        valore: Valore dell'atto o importo oggetto del provvedimento in euro (€)
        prima_casa: True se il verbale di conciliazione riguarda un trasferimento prima casa
                    (aliquota agevolata 2%, minimo €1.000)
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
# 18 nuovi tool — Calcolatori e generatori documenti
# ---------------------------------------------------------------------------


@mcp.tool(tags={"giudiziario"})
def copie_processo_tributario(
    n_pagine: int,
    tipo: str = "semplice",
    urgente: bool = False,
) -> dict:
    """Calcola i diritti di copia specifici per il processo tributario.
    Vigenza: DPR 115/2002 — tariffe processo tributario (€0,25/pagina semplice, €0,50 autentica).
    Precisione: INDICATIVO (tariffe per pagina non riscontrate sul testo vigente del DPR 115/2002:
        verificare prima dell'uso)

    Args:
        n_pagine: Numero di pagine dell'atto (intero positivo)
        tipo: Tipo di copia: 'semplice' (€0,25/pag) o 'autentica' (€0,50/pag)
        urgente: True per maggiorazione urgenza +50%
    """
    if n_pagine <= 0:
        return {"errore": "n_pagine deve essere un intero positivo"}

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


@mcp.tool(tags={"giudiziario"})
@sourced("codici_ruolo", "contributo_unificato")
def note_iscrizione_ruolo(
    tipo_procedimento: str,
    valore_causa: float | None = None,
) -> dict:
    """Genera note per l'iscrizione a ruolo con codici oggetto suggeriti e CU calcolato.
    Vigenza: DPR 115/2002 (CU); provvedimenti DGSIA per codici oggetto iscrizione a ruolo.
    Precisione: INDICATIVO per i codici oggetto (suggeriti in base alla materia; verificare
    sempre il codice esatto nel software di deposito telematico PCT).

    Args:
        tipo_procedimento: Tipo di rito: 'cognizione_ordinaria', 'lavoro', 'locazione',
                           'condominio', 'esecuzione_mobiliare', 'esecuzione_immobiliare',
                           'monitorio', 'volontaria_giurisdizione'
        valore_causa: Valore della causa in euro (€) — necessario per calcolare il CU
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
    cu_value_based = cu_tipo in ("cognizione", "monitorio")

    materia = mapping_materia.get(tipo_procedimento)
    codici_suggeriti = []
    if materia:
        codici_suggeriti = [c for c in _CODICI_RUOLO if c["materia"] == materia]

    if valore_causa is None and cu_value_based:
        return {
            "tipo_procedimento": tipo_procedimento,
            "valore_causa": valore_causa,
            "contributo_unificato": None,
            "codici_oggetto_suggeriti": codici_suggeriti,
            "note": f"Iscrivere a ruolo come '{tipo_procedimento}'. valore_causa richiesto per il calcolo del CU.",
            "riferimento_normativo": "DPR 115/2002 — Provvedimenti DGSIA per codici oggetto",
        }

    cu_importo = _calcola_cu_base(valore_causa or 0, cu_tipo)

    return {
        "tipo_procedimento": tipo_procedimento,
        "valore_causa": valore_causa,
        "contributo_unificato": cu_importo,
        "codici_oggetto_suggeriti": codici_suggeriti,
        "note": f"Iscrivere a ruolo come '{tipo_procedimento}'. CU calcolato: EUR {cu_importo:.2f}.",
        "riferimento_normativo": "DPR 115/2002 — Provvedimenti DGSIA per codici oggetto",
    }


@mcp.tool(tags={"giudiziario"})
@sourced("codici_ruolo")
def codici_iscrizione_ruolo(materia: str) -> dict:
    """Ricerca il codice oggetto per l'iscrizione a ruolo di cause civili.
    Vigenza: provvedimenti DGSIA — Codici oggetto iscrizione a ruolo (tabella aggiornata).
    Precisione: INDICATIVO (ricerca per keyword nella materia e descrizione).

    Args:
        materia: Keyword di ricerca per la materia della causa, es. 'contratto', 'locazione',
                 'responsabilita', 'famiglia', 'lavoro', 'condominio', 'successione',
                 'societario', 'proprieta', 'possesso', 'consumatore', 'bancario'
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


@mcp.tool(tags={"giudiziario"})
def fascicolo_di_parte(
    avvocato: str,
    parte: str,
    controparte: str,
    tribunale: str,
    rg_numero: str | None = None,
) -> dict:
    """Genera bozza di frontespizio per il fascicolo di parte.
    Vigenza: art. 165 c.p.c. — Costituzione dell'attore; specifiche PCT DM 44/2011.

    Args:
        avvocato: Nome dell'avvocato difensore
        parte: Nome della parte assistita (attrice/ricorrente)
        controparte: Nome della controparte (convenuta/resistente)
        tribunale: Denominazione completa del tribunale competente
        rg_numero: Numero di Ruolo Generale, es. "1234/2025" (se già assegnato, altrimenti omettere)
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


@mcp.tool(tags={"giudiziario"})
def procura_alle_liti(
    parte: str,
    avvocato: str,
    cf_avvocato: str,
    foro: str,
    oggetto_causa: str,
    tipo: str = "generale",
) -> dict:
    """Genera bozza di procura alle liti ex art. 83 c.p.c.
    Vigenza: art. 83 c.p.c. (testo vigente); include clausola GDPR e antiriciclaggio.

    Args:
        parte: Nome della parte che conferisce la procura
        avvocato: Nome e cognome dell'avvocato incaricato
        cf_avvocato: Codice fiscale dell'avvocato
        foro: Foro di appartenenza dell'avvocato (es. "Milano", "Roma")
        oggetto_causa: Descrizione sintetica dell'oggetto della causa
        tipo: Tipo di procura: 'generale' (ogni stato e grado), 'speciale' (solo questo giudizio),
              'appello' (solo per il giudizio di appello avverso sentenza specifica)
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


@mcp.tool(tags={"giudiziario"})
def attestazione_conformita(
    avvocato: str,
    tipo_documento: str,
    estremi_originale: str,
    modalita: str = "estratto",
) -> dict:
    """Genera bozza di attestazione di conformità per il deposito telematico PCT.
    Vigenza: artt. 196-octies, 196-novies, 196-decies e 196-undecies disp. att. c.p.c., introdotti
    dal D.Lgs. 149/2022 (Riforma Cartabia) in luogo degli artt. 16-bis co. 9-bis e 16-undecies
    DL 179/2012 conv. L. 221/2012, che restano applicabili ai soli procedimenti pendenti al
    28/02/2023; DM 44/2011 e specifiche tecniche DGSIA per le modalità.

    Args:
        avvocato: Nome e cognome dell'avvocato attestante
        tipo_documento: Descrizione del tipo di documento attestato (es. "verbale di causa")
        estremi_originale: Estremi identificativi dell'originale (es. "R.G. 1234/2024, pag. 1-3")
        modalita: Modalità di attestazione: 'estratto' (copia dal fascicolo informatico),
                  'copia_informatica' (copia da originale analogico), 'duplicato' (duplicato informatico)
    """
    if modalita == "copia_informatica":
        tipo_attestazione = "copia informatica di documento analogico"
        norma_specifica = "art. 196-decies disp. att. c.p.c. (copia informatica di atto analogico)"
    elif modalita == "duplicato":
        tipo_attestazione = "duplicato informatico"
        norma_specifica = "art. 196-octies disp. att. c.p.c. (duplicato informatico)"
    else:
        tipo_attestazione = "copia informatica estratta dal fascicolo informatico"
        norma_specifica = "art. 196-octies disp. att. c.p.c. (copia estratta dal fascicolo informatico)"

    testo = f"""ATTESTAZIONE DI CONFORMITA'
(Artt. 196-octies, 196-decies e 196-undecies disp. att. c.p.c.)

Il sottoscritto Avv. {avvocato}, in qualità di difensore di parte nel procedimento indicato in atti,

ATTESTA

ai sensi dell'{norma_specifica}, che la {tipo_attestazione} del seguente documento:

{tipo_documento}

Estremi: {estremi_originale}

è conforme all'originale {("analogico" if modalita == "copia_informatica" else "contenuto nel fascicolo informatico")}.

La presente attestazione è resa ai sensi dell'art. 196-undecies delle disposizioni di attuazione del codice di procedura civile (D.Lgs. 10 ottobre 2022, n. 149).

Luogo e data _______________

Avv. {avvocato}
(firmato digitalmente)"""

    return {
        "testo": testo,
        "tipo_atto": "attestazione_conformita",
        "modalita": modalita,
        "riferimento_normativo": "Art. 16-bis co. 9-bis DL 179/2012 — Art. 16-undecies DL 179/2012",
    }


@mcp.tool(tags={"giudiziario"})
def relata_notifica_pec(
    avvocato: str,
    destinatario: str,
    pec_destinatario: str,
    atto_notificato: str,
    data_invio: str,
) -> dict:
    """Genera bozza di relata di notificazione a mezzo PEC ex L. 53/1994.
    Vigenza: art. 3-bis L. 53/1994 (mod. L. 228/2012); la notifica si perfeziona con
    la ricevuta di avvenuta consegna (RdAC).

    Args:
        avvocato: Nome e cognome dell'avvocato notificante (iscritto a INI-PEC)
        destinatario: Nome del destinatario della notifica
        pec_destinatario: Indirizzo PEC del destinatario (estratto da INI-PEC/ReGIndE/Registro Imprese)
        atto_notificato: Descrizione dell'atto notificato (es. "ricorso per decreto ingiuntivo")
        data_invio: Data di invio del messaggio PEC (YYYY-MM-DD)
    """
    dt = _parse_date(data_invio)
    data_fmt = dt.strftime("%d/%m/%Y")

    testo = f"""RELATA DI NOTIFICAZIONE A MEZZO PEC
(L. 21 gennaio 1994, n. 53, come modificata dalla L. 228/2012)

Il sottoscritto Avv. {avvocato}, ai sensi degli artt. 1 e 3-bis della L. 53/1994 (per la notificazione a mezzo PEC non occorre l'autorizzazione del Consiglio dell'Ordine, richiesta solo per la notifica a mezzo posta),

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

Ai sensi dell'art. 3-bis co. 3 della L. 53/1994 e dell'art. 147 co. 3 c.p.c., la notifica si intende perfezionata, per il notificante, nel momento in cui è generata la ricevuta di accettazione e, per il destinatario, nel momento in cui è generata la ricevuta di avvenuta consegna; se quest'ultima è generata tra le ore 21 e le ore 7 del mattino del giorno successivo, la notificazione si intende perfezionata per il destinatario alle ore 7.

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


@mcp.tool(tags={"giudiziario"})
def indice_documenti(documenti: list[dict]) -> dict:
    """Genera bozza di indice numerato dei documenti per deposito telematico PCT.
    Vigenza: specifiche tecniche PCT DM 44/2011 — elenco allegati al deposito.

    Args:
        documenti: Lista di documenti, ciascuno con le chiavi:
                   - numero (int): numero progressivo del documento
                   - descrizione (str): descrizione dell'allegato
                   - pagine (int): numero di pagine del documento
    """
    righe = []
    totale_pagine = 0
    for doc in documenti:
        num = doc.get("numero", 0)
        desc = doc.get("descrizione", "")
        pag = int(doc.get("pagine", 0) or 0)
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


@mcp.tool(tags={"giudiziario"})
def note_trattazione_scritta(
    avvocato: str,
    parte: str,
    tribunale: str,
    rg_numero: str,
    giudice: str,
    conclusioni: str,
) -> dict:
    """Genera bozza di note di trattazione scritta in sostituzione dell'udienza.
    Vigenza: art. 127-ter c.p.c. introdotto dalla Riforma Cartabia (D.Lgs. 149/2022; applicabile
    dal 01/01/2023 anche ai procedimenti pendenti, art. 35 co. 2 come modificato dalla L. 197/2022)
    — sostituzione dell'udienza con deposito di note scritte contenenti le sole istanze e
    conclusioni; il correttivo D.Lgs. 164/2024 esclude la sostituzione quando è richiesta la
    presenza personale delle parti e consente alle parti di opporsi.

    Args:
        avvocato: Nome e cognome dell'avvocato depositante
        parte: Nome della parte assistita
        tribunale: Denominazione del tribunale (es. "Tribunale di Milano")
        rg_numero: Numero di Ruolo Generale del procedimento (es. "1234/2025")
        giudice: Nome del giudice istruttore o del collegio
        conclusioni: Testo delle conclusioni e istanze da includere nelle note
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


@mcp.tool(tags={"giudiziario", "credito"})
def sfratto_morosita(
    locatore: str,
    conduttore: str,
    immobile: str,
    canone_mensile: float,
    mensilita_insolute: int,
    data_contratto: str,
) -> dict:
    """Genera bozza di intimazione di sfratto per morosità con citazione per convalida.
    Vigenza: artt. 658-669 c.p.c.; art. 55 L. 392/1978 (termine di grazia fino a 90gg).

    Args:
        locatore: Nome o ragione sociale del locatore
        conduttore: Nome o ragione sociale del conduttore moroso
        immobile: Descrizione dell'immobile (indirizzo e, se disponibili, dati catastali)
        canone_mensile: Canone mensile pattuito in euro (€)
        mensilita_insolute: Numero di mensilità non pagate (interi positivi)
        data_contratto: Data di stipula del contratto di locazione (YYYY-MM-DD)
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


@mcp.tool(tags={"giudiziario", "credito"})
def atto_di_precetto(
    creditore: str,
    debitore: str,
    titolo_esecutivo: str,
    importo_capitale: float,
    interessi: float = 0,
    spese: float = 0,
) -> dict:
    """Genera bozza di atto di precetto con avvertimento ex art. 480 c.p.c.
    Vigenza: art. 480 c.p.c. — precetto; il debitore ha 10gg per pagare, poi si può pignorare.

    Args:
        creditore: Nome o ragione sociale del creditore
        debitore: Nome o ragione sociale del debitore
        titolo_esecutivo: Descrizione del titolo esecutivo (es. "sentenza Tribunale di Milano
                          n. 1234/2024 del 15/01/2024, passata in giudicato")
        importo_capitale: Importo del capitale in euro (€)
        interessi: Interessi maturati fino alla data del precetto in euro (€)
        spese: Spese legali e di procedimento in euro (€)
    """
    totale = round(importo_capitale + interessi + spese, 2)

    testo = f"""ATTO DI PRECETTO
(Art. 480 c.p.c.)

Il/La sottoscritto/a {creditore}, C.F. ___, residente/con sede in ___, rappresentato/a e difeso/a dall'Avv. ___, giusta procura in calce/a margine,

PREMESSO

— che è in possesso del seguente titolo esecutivo: {titolo_esecutivo};
— che il predetto titolo è stato ritualmente notificato (art. 479 c.p.c.);
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

il debitore che, in mancanza di pagamento nel termine suindicato, si procederà ad esecuzione forzata; che l'opposizione agli atti esecutivi per vizi del titolo o del precetto va proposta nel termine perentorio di venti giorni dalla notificazione del presente atto (art. 617 c.p.c.), mentre l'opposizione all'esecuzione ex art. 615 c.p.c. non è soggetta a termine; e che, ai sensi dell'art. 480 co. 2 c.p.c., può porre rimedio alla situazione di sovraindebitamento concludendo con i creditori un accordo di composizione della crisi o proponendo un piano del consumatore (D.Lgs. 14/2019).

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


@mcp.tool(tags={"giudiziario", "credito"})
def nota_precisazione_credito(
    creditore: str,
    debitore: str,
    procedura_esecutiva: str,
    capitale: float,
    interessi: float,
    spese_legali: float,
    spese_esecuzione: float,
) -> dict:
    """Genera bozza di nota di precisazione del credito per procedure esecutive.
    Vigenza: atto di prassi, non tipizzato dal codice: precisa il credito ai fini dell'assegnazione
    o della distribuzione (artt. 510, 543 e 596 c.p.c.); l'art. 547 c.p.c. riguarda invece la
    dichiarazione del terzo pignorato.

    Args:
        creditore: Nome o ragione sociale del creditore procedente
        debitore: Nome o ragione sociale del debitore esecutato
        procedura_esecutiva: Estremi della procedura (es. "R.G.E. 123/2024")
        capitale: Importo del capitale in euro (€)
        interessi: Interessi maturati fino alla data della precisazione in euro (€)
        spese_legali: Spese legali in euro (€)
        spese_esecuzione: Spese di esecuzione (ufficiale giudiziario, notifica, etc.) in euro (€)
    """
    totale = round(capitale + interessi + spese_legali + spese_esecuzione, 2)

    testo = f"""NOTA DI PRECISAZIONE DEL CREDITO
(Artt. 510, 543 e 596 c.p.c.)

TRIBUNALE DI _______________

Procedura esecutiva n. {procedura_esecutiva}

Promossa da: {creditore}
Contro: {debitore}

***

Il/La sottoscritto/a Avv. ___, quale difensore di {creditore}, ai fini dell'assegnazione o della distribuzione delle somme (artt. 510, 543 e 596 c.p.c.),

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
        "riferimento_normativo": "Artt. 510, 543 e 596 c.p.c. — precisazione del credito ai fini dell'assegnazione o distribuzione (atto di prassi)",
    }


@mcp.tool(tags={"giudiziario"})
def dichiarazione_553_cpc(
    terzo_pignorato: str,
    debitore: str,
    procedura: str,
    tipo_rapporto: str = "conto_corrente",
) -> dict:
    """Genera bozza di dichiarazione del terzo pignorato ex art. 547 c.p.c.
    Vigenza: art. 547 c.p.c. (dichiarazione a mezzo PEC o raccomandata entro dieci giorni dalla
    notifica del pignoramento, art. 543 co. 2 n. 3) e art. 548 c.p.c. (mancata dichiarazione:
    credito non contestato). Il nome del tool richiama l'art. 553 c.p.c. sull'assegnazione,
    che è l'esito della fase; il modello è la dichiarazione del terzo.

    Args:
        terzo_pignorato: Nome o ragione sociale del terzo pignorato (banca, datore di lavoro, etc.)
        debitore: Nome o ragione sociale del debitore esecutato
        procedura: Estremi della procedura esecutiva (es. "R.G.E. 456/2024")
        tipo_rapporto: Tipo di rapporto tra terzo e debitore: 'conto_corrente' (banca),
                       'stipendio' (datore di lavoro), 'altro' (credito generico)
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

Ai sensi dell'art. 548 c.p.c., in caso di mancata dichiarazione e di mancata comparizione all'udienza fissata dal giudice, il credito pignorato si considera non contestato nei termini indicati dal creditore procedente.

[Luogo], [Data]

{terzo_pignorato}
(Firma e timbro)"""

    return {
        "testo": testo,
        "tipo_atto": "dichiarazione_terzo_pignorato",
        "tipo_rapporto": tipo_rapporto,
        "riferimento_normativo": "Artt. 543, 547 e 548 c.p.c. — Dichiarazione del terzo",
    }


@mcp.tool(tags={"giudiziario"})
def testimonianza_scritta(
    teste: str,
    capitoli_prova: list[str],
) -> dict:
    """Genera bozza del modulo per testimonianza scritta con capitoli e ammonizione.
    Vigenza: art. 257-bis c.p.c. — testimonianza scritta su autorizzazione del giudice.

    Args:
        teste: Nome e cognome del testimone
        capitoli_prova: Lista dei capitoli di prova su cui il teste deve rispondere
                        (es. ["È vero che il 10/01/2024 lei era presente in..."])
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

Il/La teste è ammonito/a dal Giudice sull'importanza morale del giuramento (art. 251 co. 2 c.p.c., nel testo risultante da Corte cost. n. 149/1995) e sulle conseguenze penali delle dichiarazioni false o reticenti, e presta il seguente

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


@mcp.tool(tags={"giudiziario"})
def istanza_visibilita_fascicolo(
    avvocato: str,
    parte: str,
    tribunale: str,
    rg_numero: str,
    motivo: str = "costituzione",
) -> dict:
    """Genera bozza di istanza di visibilità del fascicolo telematico per avvocato non costituito.
    Vigenza: art. 196-quater disp. att. c.p.c. (deposito telematico e fascicolo informatico,
    D.Lgs. 149/2022, già art. 16-bis DL 179/2012) — DM 44/2011 e specifiche tecniche DGSIA.

    Args:
        avvocato: Nome e cognome dell'avvocato richiedente (con PEC e foro di appartenenza)
        parte: Nome della parte assistita
        tribunale: Denominazione del tribunale (es. "Tribunale di Milano, Sezione Prima Civile")
        rg_numero: Numero di Ruolo Generale del procedimento (es. "1234/2025")
        motivo: Motivo della richiesta: 'costituzione' (per predisporre la difesa),
                'consultazione' (per interessi della parte), 'intervento' (ex art. 105 c.p.c.)
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


@mcp.tool(tags={"giudiziario"})
@sourced("tribunali_competenti")
def cerca_ufficio_giudiziario(
    comune: str,
    tipo: str = "tribunale",
) -> dict:
    """Cerca l'ufficio giudiziario territorialmente competente per un dato comune.
    Vigenza: R.D. 30 gennaio 1941 n. 12 — Ordinamento giudiziario; circondari vigenti.
    Precisione: INDICATIVO (copertura sui principali circondari italiani — per comuni minori
    verificare sempre sul sito del Ministero della Giustizia).

    Args:
        comune: Nome del comune (es. "Milano", "Roma", "Brescia")
        tipo: Tipo di ufficio: 'tribunale' (sede principale) o 'giudice_pace'
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
