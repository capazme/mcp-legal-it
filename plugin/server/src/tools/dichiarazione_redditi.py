"""Calcoli fiscali per la dichiarazione dei redditi: IRPEF 2026 (L. 199/2025), regime forfettario
(L. 190/2014), TFR, ravvedimento operoso (D.Lgs. 87/2024), Assegno Unico Universale 2026,
detrazioni familiari, lavoro dipendente, pensione, locazione e rateizzazione imposte."""

import json
from datetime import date
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "irpef_scaglioni.json") as f:
    _IRPEF = json.load(f)

with open(_DATA / "codici_tributo.json") as f:
    _CODICI_TRIBUTO: list[dict] = json.load(f)["codici"]


def _get_scaglioni(anno: int | None = None) -> list[dict]:
    """Return IRPEF brackets for the given fiscal year (default: current year)."""
    if anno is None:
        anno = date.today().year
    per_anno = _IRPEF.get("scaglioni_per_anno", {})
    return per_anno.get(str(anno), _IRPEF["scaglioni"])


def _calcola_imposta_lorda(imponibile: float, anno: int | None = None) -> tuple[float, list[dict]]:
    """Calculate gross IRPEF tax across brackets, returning total and breakdown."""
    scaglioni = _get_scaglioni(anno)
    imposta = 0.0
    dettaglio = []
    residuo = imponibile

    prev_limit = 0
    for s in scaglioni:
        aliquota = s["aliquota"]
        limite = s.get("fino_a", float("inf"))
        base = min(residuo, limite - prev_limit)
        if base <= 0:
            break
        tassa = base * aliquota / 100
        imposta += tassa
        dettaglio.append({
            "scaglione": f"{prev_limit}-{limite if limite != float('inf') else 'oltre'}",
            "aliquota_pct": aliquota,
            "base_imponibile": round(base, 2),
            "imposta": round(tassa, 2),
        })
        residuo -= base
        prev_limit = limite

    return round(imposta, 2), dettaglio


def _detrazione_lavoro_dipendente(reddito: float) -> float:
    """Calculate employment income deduction based on income brackets."""
    fasce = _IRPEF["detrazioni_lavoro_dipendente"]
    if reddito <= 15000:
        return fasce[0]["detrazione"]
    elif reddito <= 28000:
        return 1910 + 1190 * (28000 - reddito) / (28000 - 15000)
    elif reddito <= 50000:
        return 1910 * (50000 - reddito) / (50000 - 28000)
    return 0


def _detrazione_pensione(reddito: float) -> float:
    """Calculate pension income deduction based on income brackets."""
    if reddito <= 8500:
        return 1955
    elif reddito <= 28000:
        return 700 + 1255 * (28000 - reddito) / (28000 - 8500)
    elif reddito <= 50000:
        return 700 * (50000 - reddito) / (50000 - 28000)
    return 0


@mcp.tool(tags={"fiscale"})
def calcolo_irpef(
    reddito_complessivo: float,
    tipo_reddito: str = "dipendente",
    deduzioni: float = 0,
    detrazioni_extra: float = 0,
    anno_fiscale: int = 0,
) -> dict:
    """Calcola l'IRPEF con scaglioni, detrazioni da lavoro e addizionali regionali e comunali.
    Vigenza: scaglioni IRPEF storicizzati per anno (2024: 23-35-43%, 2026+: 23-33-43%).
    Precisione: INDICATIVO (le addizionali regionali e comunali variano per ente impositore;
    i valori usati sono medie nazionali — per il calcolo esatto serve l'aliquota del comune/regione).

    Args:
        reddito_complessivo: Reddito complessivo annuo lordo in euro (€)
        tipo_reddito: Tipo di reddito prevalente: 'dipendente', 'pensionato' o 'autonomo'
        deduzioni: Oneri deducibili in euro (€) — riducono il reddito imponibile prima del calcolo
        detrazioni_extra: Detrazioni aggiuntive in euro (€) — riducono l'imposta lorda calcolata
        anno_fiscale: Anno fiscale di riferimento (default: anno corrente). 2024-2025: aliquota 35%; 2026+: aliquota 33%.
    """
    if reddito_complessivo <= 0:
        return {"errore": "Il reddito complessivo deve essere positivo"}

    anno = anno_fiscale if anno_fiscale > 0 else None
    imponibile = max(reddito_complessivo - deduzioni, 0)
    imposta_lorda, dettaglio_scaglioni = _calcola_imposta_lorda(imponibile, anno=anno)

    # Detrazioni lavoro
    if tipo_reddito == "dipendente":
        detrazione_lavoro = _detrazione_lavoro_dipendente(imponibile)
    elif tipo_reddito == "pensionato":
        detrazione_lavoro = _detrazione_pensione(imponibile)
    else:
        detrazione_lavoro = 0

    detrazioni_totali = round(detrazione_lavoro + detrazioni_extra, 2)
    imposta_netta = round(max(imposta_lorda - detrazioni_totali, 0), 2)

    # Addizionali
    add_regionale_pct = _IRPEF["addizionale_regionale_media"]
    add_comunale_pct = _IRPEF["addizionale_comunale_media"]
    add_regionale = round(imponibile * add_regionale_pct / 100, 2)
    add_comunale = round(imponibile * add_comunale_pct / 100, 2)
    addizionali = round(add_regionale + add_comunale, 2)

    totale_imposte = round(imposta_netta + addizionali, 2)
    reddito_netto = round(reddito_complessivo - totale_imposte, 2)

    return {
        "reddito_complessivo": reddito_complessivo,
        "deduzioni": deduzioni,
        "reddito_imponibile": round(imponibile, 2),
        "tipo_reddito": tipo_reddito,
        "imposta_lorda": imposta_lorda,
        "dettaglio_scaglioni": dettaglio_scaglioni,
        "detrazioni": {
            "lavoro": round(detrazione_lavoro, 2),
            "extra": detrazioni_extra,
            "totale": detrazioni_totali,
        },
        "imposta_netta": imposta_netta,
        "addizionali": {
            "regionale": add_regionale,
            "regionale_pct": add_regionale_pct,
            "comunale": add_comunale,
            "comunale_pct": add_comunale_pct,
            "totale": addizionali,
        },
        "totale_imposte": totale_imposte,
        "reddito_netto": reddito_netto,
        "aliquota_effettiva_pct": round(totale_imposte / reddito_complessivo * 100, 2),
        "anno_fiscale": anno or date.today().year,
        "riferimento_normativo": "TUIR — D.P.R. 917/1986, art. 11-13",
    }


@mcp.tool(tags={"fiscale"})
def regime_forfettario(
    ricavi: float,
    coefficiente_redditivita: float = 78,
    anni_attivita: int = 1,
    contributi_inps: float = 0,
) -> dict:
    """Simula il regime forfettario: imposta sostitutiva e confronto con l'IRPEF ordinaria.
    Vigenza: art. 1, commi 54-89, L. 190/2014 (mod. L. 208/2015 e L. 145/2018);
    limite ricavi 85.000€; aliquota ordinaria 15%, startup 5% (primi 5 anni).
    Precisione: ESATTO per l'imposta sostitutiva; INDICATIVO per il confronto con l'IRPEF ordinaria
    (usa medie addizionali e non considera detrazioni da lavoro autonomo).

    Args:
        ricavi: Ricavi o compensi annui lordi in euro (€) — deve essere ≤85.000€
        coefficiente_redditivita: Coefficiente di redditivita in percentuale per categoria
                                  ATECO (es. 78 per professionisti, 67 per commercio)
        anni_attivita: Anni di attività dall'inizio — 1-5 = aliquota startup 5%, oltre 5 = 15%
        contributi_inps: Contributi INPS versati nell'anno in euro (€), deducibili dal reddito imponibile
    """
    forfettario = _IRPEF["forfettario"]
    limite = forfettario["limite_ricavi"]

    if ricavi > limite:
        return {
            "errore": f"Ricavi {ricavi}€ superano il limite di {limite}€ per il regime forfettario",
            "limite_ricavi": limite,
        }

    reddito_lordo = round(ricavi * coefficiente_redditivita / 100, 2)
    imponibile = round(max(reddito_lordo - contributi_inps, 0), 2)

    aliquota = forfettario["aliquota_startup"] if anni_attivita <= 5 else forfettario["aliquota_ordinaria"]
    imposta = round(imponibile * aliquota / 100, 2)
    reddito_netto = round(ricavi - contributi_inps - imposta, 2)

    # Confronto con ordinario (stima IRPEF)
    irpef_lorda, _ = _calcola_imposta_lorda(imponibile)
    add_pct = _IRPEF["addizionale_regionale_media"] + _IRPEF["addizionale_comunale_media"]
    stima_ordinario = round(irpef_lorda + imponibile * add_pct / 100, 2)
    risparmio = round(stima_ordinario - imposta, 2)

    return {
        "ricavi": ricavi,
        "coefficiente_redditivita_pct": coefficiente_redditivita,
        "reddito_lordo": reddito_lordo,
        "contributi_inps_dedotti": contributi_inps,
        "reddito_imponibile": imponibile,
        "aliquota_pct": aliquota,
        "tipo_aliquota": "startup (primi 5 anni)" if anni_attivita <= 5 else "ordinaria",
        "imposta_sostitutiva": imposta,
        "reddito_netto": reddito_netto,
        "confronto_ordinario": {
            "stima_irpef_addizionali": stima_ordinario,
            "risparmio_forfettario": risparmio,
        },
        "riferimento_normativo": "Art. 1, commi 54-89, L. 190/2014 (mod. L. 208/2015, L. 145/2018)",
    }


@mcp.tool(tags={"fiscale"})
def calcolo_tfr(
    retribuzione_annua_lorda: float,
    anni_servizio: int,
    rivalutazione_media_pct: float = 2.0,
) -> dict:
    """Calcola il TFR (Trattamento di Fine Rapporto) lordo e netto con tassazione separata.
    Vigenza: art. 2120 c.c. (accantonamento e rivalutazione); artt. 17 e 19 TUIR (tassazione separata).
    Precisione: INDICATIVO (la tassazione separata usa un'approssimazione dell'aliquota media IRPEF
    degli ultimi 5 anni; il calcolo esatto dipende dalla storia reddituale individuale).

    Args:
        retribuzione_annua_lorda: Retribuzione annua lorda (RAL) in euro (€)
        anni_servizio: Anni di servizio presso il datore di lavoro (interi positivi)
        rivalutazione_media_pct: Indice FOI medio annuo in percentuale per la rivalutazione TFR
                                 (default 2.0%, componente inflattiva ISTAT)
    """
    if anni_servizio <= 0:
        return {"errore": "Gli anni di servizio devono essere almeno 1"}

    accantonamento_annuo = retribuzione_annua_lorda / 13.5
    # Rivalutazione: 1.5% fisso + 75% dell'indice FOI
    tasso_rivalutazione = 1.5 + 0.75 * rivalutazione_media_pct

    # TFR lordo: somma accantonamenti rivalutati
    tfr_lordo = 0.0
    for anno in range(anni_servizio):
        anni_residui = anni_servizio - anno - 1
        accantonamento_rivalutato = accantonamento_annuo * ((1 + tasso_rivalutazione / 100) ** anni_residui)
        tfr_lordo += accantonamento_rivalutato

    tfr_lordo = round(tfr_lordo, 2)

    # Tassazione separata: aliquota media IRPEF ultimi 5 anni
    # Approssimazione: reddito di riferimento = TFR * 12 / anni_servizio
    reddito_riferimento = tfr_lordo * 12 / anni_servizio
    imposta_riferimento, _ = _calcola_imposta_lorda(reddito_riferimento)
    aliquota_media = imposta_riferimento / reddito_riferimento * 100 if reddito_riferimento > 0 else 23

    imposta = round(tfr_lordo * aliquota_media / 100, 2)
    tfr_netto = round(tfr_lordo - imposta, 2)

    return {
        "retribuzione_annua_lorda": retribuzione_annua_lorda,
        "anni_servizio": anni_servizio,
        "accantonamento_annuo": round(accantonamento_annuo, 2),
        "tasso_rivalutazione_pct": round(tasso_rivalutazione, 2),
        "tfr_lordo": tfr_lordo,
        "tassazione_separata": {
            "reddito_riferimento": round(reddito_riferimento, 2),
            "aliquota_media_pct": round(aliquota_media, 2),
            "imposta": imposta,
        },
        "tfr_netto": tfr_netto,
        "riferimento_normativo": "Art. 2120 c.c. — Tassazione separata ex art. 17, 19 TUIR",
    }


@mcp.tool(tags={"fiscale"})
def ravvedimento_operoso(
    imposta_dovuta: float,
    giorni_ritardo: int,
    tipo: str = "omesso_versamento",
) -> dict:
    """Calcola sanzioni ridotte e interessi legali per il ravvedimento operoso.
    Vigenza: art. 13 D.Lgs. 472/1997 (mod. D.Lgs. 87/2024 — nuova sanzione base 25%);
    tasso di interesse legale aggiornato all'ultimo dato disponibile nei tassi_legali.json.
    Precisione: ESATTO (formule di legge; sanzione base 25% per omesso versamento, 120%
    per dichiarazione tardiva; riduzioni sprint/breve/intermedio/lungo/biennale/ultrannuale).

    Args:
        imposta_dovuta: Importo dell'imposta originariamente dovuta in euro (€)
        giorni_ritardo: Giorni di ritardo rispetto alla scadenza ordinaria (interi positivi)
        tipo: Tipo di violazione: 'omesso_versamento' (sanzione base 25%) o
              'dichiarazione_tardiva' (sanzione base 120%)
    """
    if giorni_ritardo <= 0:
        return {"errore": "I giorni di ritardo devono essere almeno 1"}

    # Sanzione base: 25% per omesso versamento (D.Lgs. 87/2024), 120% per dichiarazione
    if tipo == "omesso_versamento":
        sanzione_base_pct = 25
        sanzione_dimezzata = 12.5  # ≤90 gg: metà della sanzione base
    else:
        sanzione_base_pct = 120
        sanzione_dimezzata = 60

    # Riduzione sanzioni per ravvedimento (art. 13 D.Lgs. 472/1997 mod. D.Lgs. 87/2024)
    if giorni_ritardo <= 14:
        # Sprint: 1/10 di (sanzione_dimezzata * giorni/15)
        sanzione_pct = round(sanzione_dimezzata / 15 * giorni_ritardo / 10, 4)
        tipo_ravvedimento = "sprint (entro 14 giorni)"
    elif giorni_ritardo <= 30:
        # Breve: 1/10 della sanzione dimezzata
        sanzione_pct = round(sanzione_dimezzata / 10, 4)
        tipo_ravvedimento = "breve (15-30 giorni)"
    elif giorni_ritardo <= 90:
        # Intermedio: 1/9 della sanzione dimezzata
        sanzione_pct = round(sanzione_dimezzata / 9, 4)
        tipo_ravvedimento = "intermedio (31-90 giorni)"
    elif giorni_ritardo <= 365:
        # Lungo: 1/8 della sanzione piena
        sanzione_pct = round(sanzione_base_pct / 8, 4)
        tipo_ravvedimento = "lungo (91 giorni - 1 anno)"
    elif giorni_ritardo <= 730:
        # Biennale: 1/7 della sanzione piena
        sanzione_pct = round(sanzione_base_pct / 7, 4)
        tipo_ravvedimento = "biennale (1-2 anni)"
    else:
        # Ultrannuale: 1/6 della sanzione piena
        sanzione_pct = round(sanzione_base_pct / 6, 4)
        tipo_ravvedimento = "ultrannuale (oltre 2 anni)"

    sanzione = round(imposta_dovuta * sanzione_pct / 100, 2)

    # Interessi legali pro rata (caricato da tassi_legali.json)
    with open(_DATA / "tassi_legali.json") as f:
        tassi = json.load(f)["tassi"]
    tasso_legale = tassi[-1]["tasso"]  # ultimo tasso vigente
    interessi = round(imposta_dovuta * tasso_legale / 100 * giorni_ritardo / 365, 2)

    totale_dovuto = round(imposta_dovuta + sanzione + interessi, 2)

    return {
        "imposta_dovuta": imposta_dovuta,
        "giorni_ritardo": giorni_ritardo,
        "tipo": tipo,
        "tipo_ravvedimento": tipo_ravvedimento,
        "sanzione_base_pct": sanzione_base_pct,
        "sanzione_ridotta_pct": sanzione_pct,
        "sanzione": sanzione,
        "interessi_legali": {
            "tasso_pct": tasso_legale,
            "importo": interessi,
        },
        "totale_dovuto": totale_dovuto,
        "riferimento_normativo": "Art. 13 D.Lgs. 472/1997 (mod. D.Lgs. 87/2024)",
    }


@mcp.tool(tags={"fiscale"})
def assegno_unico(
    isee: float,
    n_figli: int,
    eta_figli: list[int] | None = None,
    genitore_solo: bool = False,
) -> dict:
    """Simula l'Assegno Unico Universale (AUU) per figli a carico.
    Vigenza: D.Lgs. 230/2021; importi 2026 (DPCM 16/02/2023 con rivalutazione annuale ISTAT).
    Precisione: INDICATIVO (gli importi base 2026 sono aggiornati; le maggiorazioni dipendono
    dalla composizione familiare; verificare sempre gli importi aggiornati su INPS).

    Args:
        isee: Valore ISEE familiare in euro (€) — inserire 0 se non si ha l'ISEE
        n_figli: Numero totale di figli a carico (interi positivi, minimo 1)
        eta_figli: Lista delle età dei figli in anni — opzionale, necessaria per calcolare
                   maggiorazioni (es. [0, 2, 5] per figlio neonato, bimbo e bambino)
        genitore_solo: True se nucleo monogenitoriale — aggiunge maggiorazione del 30%
    """
    if n_figli <= 0:
        return {"errore": "Il numero di figli deve essere almeno 1"}

    # Importi base 2026
    ISEE_MIN = 17468.51
    ISEE_MAX = 46582.71
    IMPORTO_MIN = 58.30
    IMPORTO_MAX = 203.80

    # Importo base per figlio (scala lineare tra min e max)
    if isee <= 0 or isee <= ISEE_MIN:
        importo_base = IMPORTO_MAX
    elif isee >= ISEE_MAX:
        importo_base = IMPORTO_MIN
    else:
        importo_base = IMPORTO_MAX - (IMPORTO_MAX - IMPORTO_MIN) * (isee - ISEE_MIN) / (ISEE_MAX - ISEE_MIN)

    importo_base = round(importo_base, 2)

    # Maggiorazioni per figlio
    dettaglio_figli = []
    if eta_figli is None:
        eta_figli = [10] * n_figli  # Default: eta media senza maggiorazioni speciali

    for i, eta in enumerate(eta_figli[:n_figli]):
        maggiorazioni = []
        importo_figlio = importo_base

        if eta < 1:
            magg = 96.9
            maggiorazioni.append({"tipo": "figlio < 1 anno", "importo": magg})
            importo_figlio += magg

        if 1 <= eta <= 3 and n_figli >= 3:
            magg = 34.1
            maggiorazioni.append({"tipo": "figlio 1-3 anni (3+ figli)", "importo": magg})
            importo_figlio += magg

        dettaglio_figli.append({
            "figlio": i + 1,
            "eta": eta,
            "importo_base": importo_base,
            "maggiorazioni": maggiorazioni,
            "importo_mensile": round(importo_figlio, 2),
        })

    # Fill remaining children without eta info
    for i in range(len(eta_figli), n_figli):
        dettaglio_figli.append({
            "figlio": i + 1,
            "eta": None,
            "importo_base": importo_base,
            "maggiorazioni": [],
            "importo_mensile": importo_base,
        })

    totale_mensile = sum(f["importo_mensile"] for f in dettaglio_figli)

    # Maggiorazione genitore solo
    maggiorazione_genitore = 0
    if genitore_solo:
        maggiorazione_genitore = round(totale_mensile * 0.30, 2)
        totale_mensile += maggiorazione_genitore

    totale_mensile = round(totale_mensile, 2)
    totale_annuo = round(totale_mensile * 12, 2)

    return {
        "isee": isee,
        "n_figli": n_figli,
        "importo_base_per_figlio": importo_base,
        "dettaglio_figli": dettaglio_figli,
        "genitore_solo": genitore_solo,
        "maggiorazione_genitore_solo": maggiorazione_genitore,
        "totale_mensile": totale_mensile,
        "totale_annuo": totale_annuo,
        "riferimento_normativo": "D.Lgs. 230/2021 — Importi 2024 (DPCM 16/02/2023)",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_figli(
    reddito_complessivo: float,
    n_figli_over21: int,
    n_figli_disabili: int = 0,
) -> dict:
    """Calcola la detrazione IRPEF per figli a carico con età ≥21 anni (art. 12 TUIR).
    I figli under 21 rientrano nell'Assegno Unico Universale — non generano detrazione IRPEF.
    Vigenza: art. 12 TUIR — D.P.R. 917/1986 (mod. D.Lgs. 230/2021 che ha spostato i figli
    under 21 all'AUU); soglia reddito 95.000€.
    Precisione: ESATTO (formula di legge; detrazione proporzionale al reddito).

    Args:
        reddito_complessivo: Reddito complessivo annuo del contribuente in euro (€)
        n_figli_over21: Numero di figli a carico con età ≥21 anni (interi positivi)
        n_figli_disabili: Numero di figli disabili tra quelli over21 (detrazione maggiorata a 1.350€)
    """
    if n_figli_over21 <= 0:
        return {"errore": "Il numero di figli over 21 deve essere almeno 1"}

    n_figli_normali = n_figli_over21 - n_figli_disabili
    if n_figli_normali < 0:
        return {"errore": "I figli disabili non possono superare il totale figli over 21"}

    soglia = 95000
    dettaglio = []
    totale = 0.0

    for i in range(n_figli_normali):
        detrazione_base = 950
        coefficiente = max((soglia - reddito_complessivo) / soglia, 0)
        importo = round(detrazione_base * coefficiente, 2)
        dettaglio.append({"figlio": i + 1, "tipo": "ordinario", "detrazione_teorica": detrazione_base, "importo": importo})
        totale += importo

    for i in range(n_figli_disabili):
        detrazione_base = 1350
        coefficiente = max((soglia - reddito_complessivo) / soglia, 0)
        importo = round(detrazione_base * coefficiente, 2)
        dettaglio.append({"figlio": n_figli_normali + i + 1, "tipo": "disabile", "detrazione_teorica": detrazione_base, "importo": importo})
        totale += importo

    return {
        "reddito_complessivo": reddito_complessivo,
        "n_figli_over21": n_figli_over21,
        "n_figli_disabili": n_figli_disabili,
        "soglia_reddito": soglia,
        "dettaglio": dettaglio,
        "detrazione_totale": round(totale, 2),
        "riferimento_normativo": "Art. 12 TUIR — D.P.R. 917/1986 (mod. D.Lgs. 230/2021)",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_coniuge(reddito_complessivo: float) -> dict:
    """Calcola la detrazione IRPEF per coniuge a carico (art. 12 TUIR).
    Il coniuge è a carico se il suo reddito non supera €2.840,51 (o €4.000 se under 24).
    Vigenza: art. 12, comma 1, lett. a) TUIR — D.P.R. 917/1986 (testo vigente).
    Precisione: ESATTO (scaglioni di legge: fino a 15.000€, 15.001-40.000€, 40.001-80.000€).

    Args:
        reddito_complessivo: Reddito complessivo annuo del contribuente in euro (€)
    """
    if reddito_complessivo <= 0:
        return {"errore": "Il reddito complessivo deve essere positivo"}

    if reddito_complessivo <= 15000:
        detrazione = max(800 - (110 * reddito_complessivo / 15000), 0)
        fascia = "fino a 15.000€"
    elif reddito_complessivo <= 40000:
        detrazione = 690
        fascia = "15.001-40.000€"
    elif reddito_complessivo <= 80000:
        detrazione = 690 * (80000 - reddito_complessivo) / 40000
        fascia = "40.001-80.000€"
    else:
        detrazione = 0
        fascia = "oltre 80.000€"

    return {
        "reddito_complessivo": reddito_complessivo,
        "fascia": fascia,
        "detrazione": round(detrazione, 2),
        "limite_reddito_coniuge": 2840.51,
        "limite_reddito_coniuge_under24": 4000,
        "riferimento_normativo": "Art. 12, comma 1, lett. a) TUIR — D.P.R. 917/1986",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_altri_familiari(
    reddito_complessivo: float,
    n_familiari: int,
) -> dict:
    """Calcola la detrazione IRPEF per altri familiari a carico (art. 12 TUIR).
    Comprende: genitori, fratelli, sorelle, nonni, nipoti e altri soggetti ex art. 433 c.c.
    il cui reddito non supera €2.840,51.
    Vigenza: art. 12, comma 1, lett. d) TUIR — D.P.R. 917/1986; soglia 80.000€.
    Precisione: ESATTO (detrazione unitaria teorica €750, proporzionata al reddito).

    Args:
        reddito_complessivo: Reddito complessivo annuo del contribuente in euro (€)
        n_familiari: Numero di altri familiari a carico (interi positivi)
    """
    if n_familiari <= 0:
        return {"errore": "Il numero di familiari deve essere almeno 1"}

    soglia = 80000
    detrazione_unitaria = 750
    coefficiente = max((soglia - reddito_complessivo) / soglia, 0)
    importo_per_familiare = round(detrazione_unitaria * coefficiente, 2)
    totale = round(importo_per_familiare * n_familiari, 2)

    return {
        "reddito_complessivo": reddito_complessivo,
        "n_familiari": n_familiari,
        "soglia_reddito": soglia,
        "detrazione_unitaria_teorica": detrazione_unitaria,
        "detrazione_per_familiare": importo_per_familiare,
        "detrazione_totale": totale,
        "riferimento_normativo": "Art. 12, comma 1, lett. d) TUIR — D.P.R. 917/1986",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_lavoro_dipendente(
    reddito_complessivo: float,
    giorni_lavoro: int = 365,
) -> dict:
    """Calcola la detrazione IRPEF per redditi di lavoro dipendente (art. 13 TUIR), proporzionata
    ai giorni lavorati nell'anno.
    Vigenza: art. 13, comma 1, TUIR — scaglioni 2026 ex L. 199/2025 (Legge di Bilancio 2026).
    Precisione: ESATTO (detrazione calcolata per scaglioni e poi proporzionata ai giorni lavorati).

    Args:
        reddito_complessivo: Reddito complessivo annuo in euro (€)
        giorni_lavoro: Giorni lavorati nell'anno (1-365; default 365 per anno intero)
    """
    giorni_lavoro = min(max(giorni_lavoro, 1), 365)

    if reddito_complessivo <= 15000:
        detrazione_annua = _IRPEF["detrazioni_lavoro_dipendente"][0]["detrazione"]
        fascia = "fino a 15.000€"
    elif reddito_complessivo <= 28000:
        detrazione_annua = 1910 + 1190 * (28000 - reddito_complessivo) / (28000 - 15000)
        fascia = "15.001-28.000€"
    elif reddito_complessivo <= 50000:
        detrazione_annua = 1910 * (50000 - reddito_complessivo) / (50000 - 28000)
        fascia = "28.001-50.000€"
    else:
        detrazione_annua = 0
        fascia = "oltre 50.000€"

    detrazione = round(detrazione_annua * giorni_lavoro / 365, 2)

    return {
        "reddito_complessivo": reddito_complessivo,
        "giorni_lavoro": giorni_lavoro,
        "fascia": fascia,
        "detrazione_annua_piena": round(detrazione_annua, 2),
        "detrazione_rapportata": detrazione,
        "riferimento_normativo": "Art. 13, comma 1, TUIR — D.P.R. 917/1986 (scaglioni 2026 ex L. 199/2025)",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_pensione(
    reddito_complessivo: float,
    giorni: int = 365,
) -> dict:
    """Calcola la detrazione IRPEF per redditi da pensione (art. 13 TUIR), proporzionata ai giorni.
    Vigenza: art. 13, comma 3, TUIR — D.P.R. 917/1986 (scaglioni invariati rispetto al 2024).
    Precisione: ESATTO (scaglioni: fino a 8.500€, 8.501-28.000€, 28.001-50.000€, oltre 50.000€).

    Args:
        reddito_complessivo: Reddito complessivo annuo in euro (€)
        giorni: Giorni di godimento della pensione nell'anno (1-365; default 365 per anno intero)
    """
    giorni = min(max(giorni, 1), 365)

    if reddito_complessivo <= 8500:
        detrazione_annua = 1955
        fascia = "fino a 8.500€"
    elif reddito_complessivo <= 28000:
        detrazione_annua = 700 + 1255 * (28000 - reddito_complessivo) / (28000 - 8500)
        fascia = "8.501-28.000€"
    elif reddito_complessivo <= 50000:
        detrazione_annua = 700 * (50000 - reddito_complessivo) / (50000 - 28000)
        fascia = "28.001-50.000€"
    else:
        detrazione_annua = 0
        fascia = "oltre 50.000€"

    detrazione = round(detrazione_annua * giorni / 365, 2)

    return {
        "reddito_complessivo": reddito_complessivo,
        "giorni": giorni,
        "fascia": fascia,
        "detrazione_annua_piena": round(detrazione_annua, 2),
        "detrazione_rapportata": detrazione,
        "riferimento_normativo": "Art. 13, comma 3, TUIR — D.P.R. 917/1986",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_assegno_coniuge(reddito_complessivo: float) -> dict:
    """Calcola la detrazione per assegno periodico percepito dal coniuge separato o divorziato.
    L'assegno periodico è reddito assimilato al lavoro dipendente per il percipiente
    e onere deducibile ex art. 10 TUIR per chi lo corrisponde.
    Vigenza: art. 13, comma 5-bis, TUIR; art. 10, comma 1, lett. c) TUIR — D.P.R. 917/1986.
    Precisione: ESATTO (scaglioni: fino a 5.500€, 5.501-28.000€, 28.001-50.000€, oltre 50.000€).

    Args:
        reddito_complessivo: Reddito complessivo annuo del percipiente l'assegno in euro (€)
    """
    if reddito_complessivo <= 0:
        return {"errore": "Il reddito complessivo deve essere positivo"}

    if reddito_complessivo <= 5500:
        detrazione = 1265
        fascia = "fino a 5.500€"
    elif reddito_complessivo <= 28000:
        detrazione = 500 + 765 * (28000 - reddito_complessivo) / (28000 - 5500)
        fascia = "5.501-28.000€"
    elif reddito_complessivo <= 50000:
        detrazione = 500 * (50000 - reddito_complessivo) / (50000 - 28000)
        fascia = "28.001-50.000€"
    else:
        detrazione = 0
        fascia = "oltre 50.000€"

    return {
        "reddito_complessivo": reddito_complessivo,
        "fascia": fascia,
        "detrazione": round(detrazione, 2),
        "nota": "L'assegno periodico al coniuge e reddito assimilato al lavoro dipendente per il percipiente e onere deducibile per chi lo versa.",
        "riferimento_normativo": "Art. 13, comma 5-bis, TUIR — Art. 10, comma 1, lett. c) TUIR",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_canone_locazione(
    reddito_complessivo: float,
    tipo_contratto: str = "libero",
) -> dict:
    """Calcola la detrazione IRPEF per inquilini con contratto di locazione come abitazione principale.
    Vigenza: art. 16 TUIR — D.P.R. 917/1986 (importi rivalutati; soglie reddito non aggiornate dal 1997).
    Precisione: ESATTO (importi fissi per scaglione di reddito come da legge).

    Args:
        reddito_complessivo: Reddito complessivo annuo in euro (€)
        tipo_contratto: Tipologia contrattuale: 'libero' (art. 16 co. 1, max €300/150),
                        'concordato' (co. 2, max €495,80/247,90),
                        'giovani_under31' (co. 1-ter, 20% del canone max €2.000, solo reddito ≤€15.493,71)
    """
    tipi_validi = ("libero", "concordato", "giovani_under31")
    if tipo_contratto not in tipi_validi:
        return {"errore": f"tipo_contratto deve essere uno tra {tipi_validi}"}

    if tipo_contratto == "libero":
        if reddito_complessivo <= 15493.71:
            detrazione = 300
        elif reddito_complessivo <= 30987.41:
            detrazione = 150
        else:
            detrazione = 0
    elif tipo_contratto == "concordato":
        if reddito_complessivo <= 15493.71:
            detrazione = 495.80
        elif reddito_complessivo <= 30987.41:
            detrazione = 247.90
        else:
            detrazione = 0
    else:  # giovani_under31
        if reddito_complessivo <= 15493.71:
            detrazione = 2000
        else:
            detrazione = 0

    return {
        "reddito_complessivo": reddito_complessivo,
        "tipo_contratto": tipo_contratto,
        "detrazione": round(detrazione, 2),
        "nota_giovani": "Per giovani under 31: detrazione pari al 20% del canone, max 2.000€, reddito <= 15.493,71€" if tipo_contratto == "giovani_under31" else None,
        "riferimento_normativo": "Art. 16 TUIR — D.P.R. 917/1986",
    }


@mcp.tool(tags={"fiscale"})
def acconto_irpef(
    imposta_anno_precedente: float,
    metodo: str = "storico",
) -> dict:
    """Calcola l'acconto IRPEF (primo e secondo acconto) con importi e scadenze.
    Vigenza: art. 17 D.P.R. 435/2001; art. 4 D.L. 69/1989; acconto totale = 100% dell'imposta
    dell'anno precedente (con metodo storico).
    Precisione: ESATTO (40% primo acconto, 60% secondo; soglia esenzione €51,65).

    Args:
        imposta_anno_precedente: Imposta netta IRPEF risultante dalla dichiarazione dell'anno
                                 precedente in euro (€) — da rigo RN34 del modello Redditi PF
        metodo: Metodo di calcolo: 'storico' (100% dell'imposta precedente) o 'previsionale'
                (su stima dell'imposta per l'anno corrente — calcolare manualmente l'importo)
    """
    if metodo not in ("storico", "previsionale"):
        return {"errore": "metodo deve essere 'storico' o 'previsionale'"}

    if imposta_anno_precedente <= 51.65:
        return {
            "imposta_anno_precedente": imposta_anno_precedente,
            "metodo": metodo,
            "acconto_dovuto": False,
            "motivo": "Nessun acconto dovuto: imposta anno precedente <= 51.65€",
        }

    acconto_totale = round(imposta_anno_precedente, 2)
    primo_acconto = round(acconto_totale * 0.40, 2)
    secondo_acconto = round(acconto_totale - primo_acconto, 2)

    return {
        "imposta_anno_precedente": imposta_anno_precedente,
        "metodo": metodo,
        "acconto_dovuto": True,
        "acconto_totale": acconto_totale,
        "primo_acconto": {
            "importo": primo_acconto,
            "percentuale": 40,
            "scadenza": "30 giugno (o 30 luglio con maggiorazione 0.40%)",
        },
        "secondo_acconto": {
            "importo": secondo_acconto,
            "percentuale": 60,
            "scadenza": "30 novembre",
        },
        "nota_previsionale": "Con metodo previsionale, gli importi vanno calcolati sull'imposta stimata per l'anno corrente" if metodo == "previsionale" else None,
        "riferimento_normativo": "Art. 17 D.P.R. 435/2001 — Art. 4 D.L. 69/1989",
    }


@mcp.tool(tags={"fiscale"})
def acconto_cedolare_secca(imposta_anno_precedente: float) -> dict:
    """Calcola l'acconto cedolare secca (primo e secondo acconto) con importi e scadenze.
    Vigenza: art. 3, comma 4, D.Lgs. 23/2011; acconto totale = 100% della cedolare secca
    dell'anno precedente; stesse scadenze dell'IRPEF (giugno/luglio e novembre).
    Precisione: ESATTO (40% primo acconto, 60% secondo; soglia esenzione €51,65).

    Args:
        imposta_anno_precedente: Imposta da cedolare secca risultante dalla dichiarazione
                                 dell'anno precedente in euro (€)
    """
    if imposta_anno_precedente <= 51.65:
        return {
            "imposta_anno_precedente": imposta_anno_precedente,
            "acconto_dovuto": False,
            "motivo": "Nessun acconto dovuto: imposta anno precedente <= 51.65€",
        }

    acconto_totale = round(imposta_anno_precedente, 2)
    primo_acconto = round(acconto_totale * 0.40, 2)
    secondo_acconto = round(acconto_totale - primo_acconto, 2)

    return {
        "imposta_anno_precedente": imposta_anno_precedente,
        "acconto_dovuto": True,
        "acconto_totale": acconto_totale,
        "primo_acconto": {
            "importo": primo_acconto,
            "percentuale": 40,
            "scadenza": "30 giugno (o 30 luglio con maggiorazione 0.40%)",
        },
        "secondo_acconto": {
            "importo": secondo_acconto,
            "percentuale": 60,
            "scadenza": "30 novembre",
        },
        "riferimento_normativo": "Art. 3, comma 4, D.Lgs. 23/2011",
    }


@mcp.tool(tags={"fiscale"})
def rateizzazione_imposte(
    importo_totale: float,
    n_rate: int,
    data_prima_rata: str,
    tasso_interesse_annuo: float = 2.0,
) -> dict:
    """Calcola il piano di rateizzazione delle imposte IRPEF e addizionali da dichiarazione.
    Vigenza: art. 20 D.Lgs. 241/1997; la rateizzazione è consentita da 2 a 7 rate mensili
    a partire dal mese di giugno (o luglio con maggiorazione 0,40%).
    Precisione: ESATTO (rata base + interessi mensili calcolati sulla quota residua).

    Args:
        importo_totale: Importo totale da rateizzare in euro (€)
        n_rate: Numero di rate mensili (2-7; oltre luglio si aggiunge maggiorazione 0,40%)
        data_prima_rata: Data della prima rata — di norma 30 giugno (YYYY-MM-DD)
        tasso_interesse_annuo: Tasso di interesse annuo in percentuale (default 2,0%)
    """
    from datetime import date as _date

    if n_rate < 2 or n_rate > 7:
        return {"errore": "Il numero di rate deve essere tra 2 e 7"}
    if importo_totale <= 0:
        return {"errore": "L'importo totale deve essere positivo"}

    try:
        dt_prima = _date.fromisoformat(data_prima_rata)
    except ValueError:
        return {"errore": "data_prima_rata non valida, usare formato YYYY-MM-DD"}

    importo_rata_base = round(importo_totale / n_rate, 2)
    tasso_mensile = tasso_interesse_annuo / 100 / 12
    piano = []

    for i in range(n_rate):
        mesi_dalla_prima = i
        interessi = round((importo_totale - i * importo_rata_base) * tasso_mensile * mesi_dalla_prima, 2) if i > 0 else 0
        # Date approssimate: una rata al mese
        data_rata = _date(dt_prima.year, dt_prima.month + i, min(dt_prima.day, 28)) if dt_prima.month + i <= 12 else _date(dt_prima.year + 1, (dt_prima.month + i) - 12, min(dt_prima.day, 28))

        rata_totale = round(importo_rata_base + interessi, 2)
        piano.append({
            "rata": i + 1,
            "data_scadenza": data_rata.isoformat(),
            "importo_capitale": importo_rata_base,
            "interessi": interessi,
            "rata_totale": rata_totale,
        })

    totale_interessi = sum(r["interessi"] for r in piano)
    totale_versato = round(importo_totale + totale_interessi, 2)

    return {
        "importo_totale": importo_totale,
        "n_rate": n_rate,
        "tasso_interesse_annuo_pct": tasso_interesse_annuo,
        "piano_rate": piano,
        "totale_interessi": round(totale_interessi, 2),
        "totale_versato": totale_versato,
        "riferimento_normativo": "Art. 20 D.Lgs. 241/1997",
    }


@mcp.tool(tags={"fiscale"})
def cerca_codice_tributo(query: str) -> str:
    """Cerca un codice tributo F24 per codice o descrizione.

    Usare quando serve il codice tributo per compilare un modello F24.
    Restituisce: codice, descrizione, sezione e categoria per ogni risultato trovato.

    Args:
        query: Codice tributo (es. '4001') o testo da cercare (es. 'IRPEF saldo', 'IMU', 'IVA mensile')
    """
    q = query.strip()

    # Exact code match (case-insensitive for robustness)
    exact = [c for c in _CODICI_TRIBUTO if c["codice"].lower() == q.lower()]
    if exact:
        results = exact
    else:
        q_lower = q.lower()
        results = [
            c for c in _CODICI_TRIBUTO
            if q_lower in c["descrizione"].lower() or q_lower in c["categoria"].lower()
        ]

    if not results:
        return f"Nessun codice tributo trovato per: {query}"

    lines = [
        "| Codice | Descrizione | Sezione | Categoria |",
        "|--------|-------------|---------|-----------|",
    ]
    for c in results:
        lines.append(
            f"| {c['codice']} | {c['descrizione']} | {c['sezione']} | {c['categoria']} |"
        )
    return "\n".join(lines)
