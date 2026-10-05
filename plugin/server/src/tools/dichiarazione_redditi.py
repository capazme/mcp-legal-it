"""Calcoli fiscali per la dichiarazione dei redditi: IRPEF 2026 (L. 199/2025), regime forfettario
(L. 190/2014), TFR, ravvedimento operoso (D.Lgs. 87/2024), Assegno Unico Universale 2026,
detrazioni familiari, lavoro dipendente, pensione, locazione e rateizzazione imposte."""

import json
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

from src.lib import _clock
from src.server import mcp
from src.lib._data import sourced

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "irpef_scaglioni.json", encoding="utf-8") as f:
    _IRPEF = json.load(f)

with open(_DATA / "codici_tributo.json", encoding="utf-8") as f:
    _CODICI_TRIBUTO: list[dict] = json.load(f)["codici"]

with open(_DATA / "tassi_legali.json", encoding="utf-8") as f:
    _TASSI_LEGALI: list[dict] = json.load(f)["tassi"]


def _quoziente4(numeratore: float, denominatore: float) -> float:
    """Rapporto assunto nelle prime quattro cifre decimali (troncamento, non arrotondamento):
    art. 12 co. 4 e art. 13 co. 6 TUIR."""
    q = Decimal(str(numeratore)) / Decimal(str(denominatore))
    return float(q.quantize(Decimal("0.0001"), rounding=ROUND_DOWN))


def _get_scaglioni(anno: int | None = None) -> list[dict]:
    """Return IRPEF brackets for the given fiscal year (default: current year)."""
    if anno is None:
        anno = _clock.today().year
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
@sourced("irpef_scaglioni")
def calcolo_irpef(
    reddito_complessivo: float,
    tipo_reddito: str = "dipendente",
    deduzioni: float = 0,
    detrazioni_extra: float = 0,
    anno_fiscale: int = 0,
) -> dict:
    """Calcola l'IRPEF con scaglioni, detrazioni da lavoro e addizionali regionali e comunali.
    Vigenza: scaglioni IRPEF storicizzati per anno (art. 11 TUIR: 2024-2025: 23-35-43%,
    2026+: 23-33-43%, L. 199/2025); detrazioni dell'art. 13 TUIR nel testo vigente al 2026-09-29
    (commi 1, 1.1, 3, 3-bis, 5, 5-ter, 6, 6-bis), calcolate sul reddito complessivo con i rapporti
    troncati alla quarta cifra decimale; anni anteriori al 2024 non supportati.
    Precisione: INDICATIVO (le addizionali regionali e comunali variano per ente impositore;
    i valori usati sono medie nazionali — per il calcolo esatto serve l'aliquota del comune/regione;
    non applica la somma esente e l'ulteriore detrazione di 1.000 € per i dipendenti dell'art. 1
    co. 4-6 L. 207/2024, né il rapporto della detrazione al periodo di lavoro: reddito e
    detrazioni sono per l'anno intero).

    Args:
        reddito_complessivo: Reddito complessivo annuo lordo in euro (€)
        tipo_reddito: Tipo di reddito prevalente: 'dipendente', 'pensionato' o 'autonomo'
        deduzioni: Oneri deducibili in euro (€) — riducono il reddito imponibile prima del calcolo
        detrazioni_extra: Detrazioni aggiuntive in euro (€) — riducono l'imposta lorda calcolata
        anno_fiscale: Anno fiscale di riferimento (default: anno corrente). 2024-2025: aliquota 35%; 2026+: aliquota 33%.
    """
    if reddito_complessivo <= 0:
        return {"errore": "Il reddito complessivo deve essere positivo"}
    if 0 < anno_fiscale < 2024:
        return {"errore": (
            f"anno_fiscale {anno_fiscale} non in tabella: gli scaglioni disponibili partono dal 2024 "
            "(per gli anni precedenti l'art. 11 TUIR prevedeva quattro scaglioni 23-25-35-43%)"
        )}

    anno = anno_fiscale if anno_fiscale > 0 else None
    imponibile = max(reddito_complessivo - deduzioni, 0)
    imposta_lorda, dettaglio_scaglioni = _calcola_imposta_lorda(imponibile, anno=anno)

    # Detrazioni art. 13 TUIR: calcolate sul reddito complessivo (co. 1, 3, 5 e 6-bis), non
    # sull'imponibile al netto degli oneri deducibili.
    detrazione_lavoro = _detrazione_art13(reddito_complessivo, tipo_reddito)

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
        "anno_fiscale": anno or _clock.today().year,
        "riferimento_normativo": "TUIR — D.P.R. 917/1986, art. 11-13",
    }


@mcp.tool(tags={"fiscale"})
@sourced("irpef_scaglioni")
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

    if ricavi <= 0:
        return {"errore": "I ricavi devono essere positivi"}
    if not 0 < coefficiente_redditivita <= 100:
        return {"errore": "Il coefficiente di redditività deve essere tra 0 e 100"}
    if anni_attivita < 1:
        return {"errore": "Gli anni di attività devono essere almeno 1"}

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


# Imposta sostitutiva sulle rivalutazioni del fondo TFR: art. 11 c. 3 D.Lgs. 47/2000, 11% fino alle
# rivalutazioni 2014, 17% da quelle decorrenti dal 1 gennaio 2015 (art. 1 c. 623-625 L. 190/2014).
_TFR_SOSTITUTIVA_FINO_2014 = 0.11
_TFR_SOSTITUTIVA_DAL_2015 = 0.17
# Contributo aggiuntivo 0,30% + 0,20% della retribuzione imponibile, detratto dalla quota TFR
# (art. 3 L. 297/1982, ultimi due commi: "Agli oneri ..." e "I datori di lavoro detraggono").
_TFR_CONTRIBUTO_IVS = 0.005
# Detrazione art. 19 c. 1-ter TUIR: lire 120.000 per anno = 61,97 euro (tempo determinato <= 2 anni).
_TFR_DETRAZIONE_TD_ANNO = 61.97


@mcp.tool(tags={"fiscale"})
@sourced("irpef_scaglioni")
def calcolo_tfr(
    retribuzione_annua_lorda: float,
    anni_servizio: int,
    rivalutazione_media_pct: float = 2.0,
    anno_cessazione: int | None = None,
    imponibile_previdenziale: float | None = None,
    tempo_determinato: bool = False,
) -> dict:
    """Calcola il TFR (Trattamento di Fine Rapporto) lordo e netto con tassazione separata.
    Vigenza: art. 2120 c.c. (quota 1/13,5, rivalutazione 1,5% + 75% dell'aumento dell'indice, mai negativa);
    art. 3 L. 297/1982 (contributo aggiuntivo 0,50% detratto dalla quota); art. 11 c. 3 D.Lgs. 47/2000
    (imposta sostitutiva 11% fino al 2014, 17% dal 2015 sulle rivalutazioni); artt. 17 e 19 TUIR
    (tassazione separata con aliquota dell'anno di cessazione, rivalutazioni già tassate escluse
    dall'imponibile e dal reddito di riferimento; detrazione del c. 1-ter solo per i rapporti a tempo
    determinato fino a due anni). Aggiornata al 2026-09-29.
    Precisione: INDICATIVO (anni interi allineati all'anno solare; la riliquidazione degli uffici
    sull'aliquota media dei cinque anni precedenti (art. 19 c. 1) dipende dalla storia reddituale e non
    è calcolata; non sono modellate le detrazioni ulteriori applicate dal sito di confronto né la clausola di
    salvaguardia delle aliquote 2006; rivalutazioni anteriori al 2001 trattate all'11%)

    Args:
        retribuzione_annua_lorda: Retribuzione annua utile ai fini TFR (art. 2120 c. 2 c.c.) in euro (€)
        anni_servizio: Anni di servizio presso il datore di lavoro (interi positivi, con cessazione a fine anno)
        rivalutazione_media_pct: Aumento medio annuo dell'indice FOI in percentuale (default 2.0%); un valore
                                 negativo non riduce la rivalutazione (resta l'1,5% fisso, art. 2120 c. 4 c.c.)
        anno_cessazione: Anno di cessazione del rapporto (default: anno corrente); determina gli scaglioni
                         IRPEF dell'aliquota (art. 19 c. 1 TUIR) e l'aliquota dell'imposta sostitutiva
        imponibile_previdenziale: Retribuzione imponibile annua ai fini previdenziali su cui si calcola il
                                  contributo dello 0,50% (default: uguale alla retribuzione annua; 0 per non applicarlo)
        tempo_determinato: True per un rapporto a termine di durata effettiva non superiore a due anni
                           (detrazione di 61,97 euro per anno, art. 19 c. 1-ter TUIR)
    """
    if anni_servizio <= 0:
        return {"errore": "Gli anni di servizio devono essere almeno 1"}

    anno_fine = anno_cessazione if anno_cessazione is not None else _clock.today().year
    if imponibile_previdenziale is None:
        imponibile_previdenziale = retribuzione_annua_lorda

    accantonamento_annuo = retribuzione_annua_lorda / 13.5
    contributo_ivs_annuo = imponibile_previdenziale * _TFR_CONTRIBUTO_IVS
    quota_annua = accantonamento_annuo - contributo_ivs_annuo
    # Rivalutazione: 1.5% fisso + 75% dell'AUMENTO dell'indice FOI (art. 2120 c. 4 c.c.):
    # con indice in calo la parte variabile e' zero.
    tasso_rivalutazione = 1.5 + 0.75 * max(rivalutazione_media_pct, 0.0)

    # Fondo al netto dell'imposta sostitutiva, rivalutato al 31/12 di ogni anno escluso l'ultimo
    # (la quota dell'anno non si rivaluta) con trattenuta sulle rivalutazioni.
    fondo_netto = 0.0
    rivalutazioni_lorde = 0.0
    imposta_sostitutiva = 0.0
    for j in range(anni_servizio):
        anno = anno_fine - (anni_servizio - 1) + j
        if j > 0:
            riv = fondo_netto * tasso_rivalutazione / 100
            aliq = _TFR_SOSTITUTIVA_FINO_2014 if anno <= 2014 else _TFR_SOSTITUTIVA_DAL_2015
            rivalutazioni_lorde += riv
            imposta_sostitutiva += riv * aliq
            fondo_netto += riv * (1 - aliq)
        fondo_netto += quota_annua

    tfr_lordo = round(quota_annua * anni_servizio + rivalutazioni_lorde, 2)
    fondo_netto = round(fondo_netto, 2)

    # Art. 19 c. 1 TUIR: imponibile = ammontare ridotto delle rivalutazioni gia' assoggettate a imposta
    # sostitutiva; reddito di riferimento = imponibile / anni x 12; aliquota media dell'anno di cessazione.
    imponibile = round(fondo_netto - rivalutazioni_lorde, 2)
    reddito_riferimento = imponibile * 12 / anni_servizio
    imposta_riferimento, _ = _calcola_imposta_lorda(reddito_riferimento, anno_fine)
    aliquota_media = imposta_riferimento / reddito_riferimento * 100 if reddito_riferimento > 0 else 23

    imposta_lorda = round(imponibile * aliquota_media / 100, 2)
    detrazione = 0.0
    if tempo_determinato and anni_servizio <= 2:
        detrazione = min(round(_TFR_DETRAZIONE_TD_ANNO * anni_servizio, 2), imposta_lorda)
    imposta = round(imposta_lorda - detrazione, 2)
    tfr_netto = round(fondo_netto - imposta, 2)

    return {
        "retribuzione_annua_lorda": retribuzione_annua_lorda,
        "anni_servizio": anni_servizio,
        "anno_cessazione": anno_fine,
        "accantonamento_annuo": round(accantonamento_annuo, 2),
        "contributo_aggiuntivo_annuo": round(contributo_ivs_annuo, 2),
        "tasso_rivalutazione_pct": round(tasso_rivalutazione, 2),
        "tfr_lordo": tfr_lordo,
        "rivalutazioni_lorde": round(rivalutazioni_lorde, 2),
        "imposta_sostitutiva_rivalutazioni": round(imposta_sostitutiva, 2),
        "tfr_al_netto_imposta_sostitutiva": fondo_netto,
        "imponibile": imponibile,
        "tassazione_separata": {
            "reddito_riferimento": round(reddito_riferimento, 2),
            "aliquota_media_pct": round(aliquota_media, 2),
            "imposta_lorda": imposta_lorda,
            "detrazione_tempo_determinato": detrazione,
            "imposta": imposta,
        },
        "tfr_netto": tfr_netto,
        "riferimento_normativo": (
            "Art. 2120 c.c.; art. 3 L. 297/1982; art. 11 c. 3 D.Lgs. 47/2000; artt. 17 e 19 TUIR"
        ),
    }


def _round_cent(x) -> float:
    """Round a Fraction/Decimal-like amount half-up to the cent (single final rounding)."""
    from decimal import Decimal, ROUND_HALF_UP
    from fractions import Fraction

    f = Fraction(x)
    d = Decimal(f.numerator) / Decimal(f.denominator)
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _interessi_legali_giorno_per_giorno(imposta, dal, al) -> tuple:
    """Interest at the legal rate of each period, day by day (art. 13, c. 2, D.Lgs. 472/1997).

    Days run from the day after ``dal`` up to ``al`` included; each year uses its own rate
    (art. 1284 c.c.), divisor 365. Returns (Fraction amount, list of segments).
    """
    from datetime import date as _date, timedelta
    from fractions import Fraction

    totale = Fraction(0)
    segmenti = []
    inizio = dal + timedelta(days=1)
    for riga in _TASSI_LEGALI:
        r_dal = _date.fromisoformat(riga["dal"])
        r_al = _date.fromisoformat(riga["al"]) if riga.get("al") else _date.max
        da, a = max(inizio, r_dal), min(al, r_al)
        if a < da:
            continue
        giorni = (a - da).days + 1
        totale += Fraction(str(imposta)) * Fraction(str(riga["tasso"])) / 100 * giorni / 365
        segmenti.append({"dal": da.isoformat(), "al": a.isoformat(), "giorni": giorni, "tasso_pct": riga["tasso"]})
    ultimo = _date.fromisoformat(_TASSI_LEGALI[-1]["al"])
    if al > ultimo:  # beyond the table: last known rate
        da = max(inizio, ultimo + timedelta(days=1))
        giorni = (al - da).days + 1
        tasso = _TASSI_LEGALI[-1]["tasso"]
        totale += Fraction(str(imposta)) * Fraction(str(tasso)) / 100 * giorni / 365
        segmenti.append({"dal": da.isoformat(), "al": al.isoformat(), "giorni": giorni, "tasso_pct": tasso})
    return totale, segmenti


@mcp.tool(tags={"fiscale"})
@sourced("tassi_legali")
def ravvedimento_operoso(
    imposta_dovuta: float,
    giorni_ritardo: int,
    tipo: str = "omesso_versamento",
    data_scadenza: str = "",
) -> dict:
    """Calcola sanzioni ridotte e interessi legali per il ravvedimento operoso.
    Vigenza: art. 13 D.Lgs. 472/1997 e art. 13, c. 1, D.Lgs. 471/1997 (mod. D.Lgs. 87/2024:
    sanzione base 25% per le violazioni commesse dal 01/09/2024, art. 5 D.Lgs. 87/2024;
    lett. b-bis) 1/7 oltre il termine della dichiarazione, senza limite superiore); interessi
    al tasso legale di ciascun anno, giorno per giorno (art. 13, c. 2), riletti il 2026-09-29.
    Precisione: INDICATIVO. Con `data_scadenza` (data della violazione, YYYY-MM-DD) la soglia
    della lett. b) e' il termine della dichiarazione dell'anno della violazione (31 ottobre
    dell'anno successivo, art. 2 D.P.R. 322/1998, persone fisiche e societa' di persone) e gli
    interessi seguono il tasso di ogni anno; senza data la soglia e' approssimata a 365 giorni
    e gli interessi usano l'ultimo tasso. Le violazioni anteriori al 01/09/2024 (base 30%,
    riduzioni previgenti) non sono calcolate: con `data_scadenza` anteriore il tool rifiuta.
    Non calcola le riduzioni b-ter) e seguenti (dopo lo schema d'atto o la constatazione).

    Args:
        imposta_dovuta: Importo dell'imposta originariamente dovuta in euro (€)
        giorni_ritardo: Giorni di ritardo rispetto alla scadenza ordinaria (interi positivi);
                        il giorno della scadenza non si conta
        tipo: Tipo di violazione: 'omesso_versamento' (sanzione base 25%) o
              'dichiarazione_tardiva' (sanzione base 120%, calcolo semplificato)
        data_scadenza: Data della scadenza violata, YYYY-MM-DD (opzionale, consigliata):
                       la data di pagamento e' data_scadenza + giorni_ritardo
    """
    from datetime import date as _date, timedelta
    from fractions import Fraction

    if giorni_ritardo <= 0:
        return {"errore": "I giorni di ritardo devono essere almeno 1"}

    scadenza = None
    if data_scadenza:
        try:
            scadenza = _date.fromisoformat(data_scadenza)
        except ValueError:
            return {"errore": "data_scadenza non valida, usare formato YYYY-MM-DD"}
        if scadenza < _date(2024, 9, 1):
            return {
                "errore": "Violazione anteriore al 01/09/2024: si applica la disciplina previgente "
                "(sanzione base 30%, riduzioni previgenti, art. 5 D.Lgs. 87/2024), che il tool non calcola",
            }

    # Base sanction: 25% late payment (art. 13 D.Lgs. 471/1997), 120% late return
    if tipo == "omesso_versamento":
        sanzione_base_pct = 25
        meta = Fraction(25, 2)  # <= 90 days: half of the base sanction
    else:
        sanzione_base_pct = 120
        meta = Fraction(60)
    base = Fraction(sanzione_base_pct)

    avvertenze = []
    if scadenza is not None:
        pagamento = scadenza + timedelta(days=giorni_ritardo)
        termine_dich = _date(scadenza.year + 1, 10, 31)
        oltre_termine = pagamento > termine_dich
    else:
        pagamento = None
        oltre_termine = giorni_ritardo > 365
        avvertenze.append(
            "Senza data_scadenza la soglia della lett. b) e' approssimata a 365 giorni e gli "
            "interessi usano l'ultimo tasso legale: indicare data_scadenza per il calcolo esatto"
        )

    # Reduced sanction (art. 13 D.Lgs. 472/1997), kept as an exact fraction of the tax
    if giorni_ritardo <= 15:
        # art. 13, c. 1, D.Lgs. 471/1997: 1/15 per day of the halved sanction, then lett. a) 1/10
        frazione = meta / 15 * giorni_ritardo / 10
        tipo_ravvedimento = "sprint (entro 15 giorni)"
    elif giorni_ritardo <= 30:
        frazione = meta / 10  # lett. a)
        tipo_ravvedimento = "breve (16-30 giorni)"
    elif giorni_ritardo <= 90:
        frazione = meta / 9  # lett. a-bis)
        tipo_ravvedimento = "intermedio (31-90 giorni)"
    elif not oltre_termine:
        frazione = base / 8  # lett. b)
        tipo_ravvedimento = (
            "lungo (91 giorni - termine dichiarazione)" if scadenza is not None
            else "lungo (91 giorni - 1 anno)"
        )
    else:
        frazione = base / 7  # lett. b-bis), no upper limit
        tipo_ravvedimento = "oltre il termine della dichiarazione (lett. b-bis, 1/7)"

    sanzione = _round_cent(Fraction(str(imposta_dovuta)) * frazione / 100)
    sanzione_pct = round(float(frazione), 4)

    # Legal interest, day by day (art. 13, c. 2, D.Lgs. 472/1997)
    if scadenza is not None:
        tot_int, segmenti = _interessi_legali_giorno_per_giorno(imposta_dovuta, scadenza, pagamento)
        interessi = _round_cent(tot_int)
        tasso_legale = segmenti[-1]["tasso_pct"] if segmenti else _TASSI_LEGALI[-1]["tasso"]
    else:
        segmenti = None
        tasso_legale = _TASSI_LEGALI[-1]["tasso"]  # last known rate
        interessi = _round_cent(
            Fraction(str(imposta_dovuta)) * Fraction(str(tasso_legale)) / 100 * giorni_ritardo / 365
        )

    totale_dovuto = round(imposta_dovuta + sanzione + interessi, 2)

    out = {
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
    if segmenti is not None:
        out["interessi_legali"]["periodi"] = segmenti
        out["data_pagamento"] = pagamento.isoformat()
    if avvertenze:
        out["avvertenze"] = avvertenze
    return out


@mcp.tool(tags={"fiscale"})
def assegno_unico(
    isee: float,
    n_figli: int,
    eta_figli: list[int] | None = None,
    genitore_solo: bool = False,
) -> dict:
    """Simula l'Assegno Unico Universale (AUU) per figli a carico.
    Vigenza: art. 4 D.Lgs. 230/2021 (importi rivalutati ex c. 11; importi 2026 da INPS circ. 7/2026,
    +1,4%); senza ISEE spettano gli importi minimi (c. 9); +50% per il figlio sotto un anno e per i
    figli di 1-3 anni nei nuclei con tre o più figli (c. 1, solo fino alla soglia ISEE superiore);
    maggiorazione per ciascun figlio successivo al secondo (c. 3); maggiorenni fino a 21 anni (c. 2).
    Aggiornata al 2026-09-29.
    Precisione: INDICATIVO (importo interpolato in modo lineare tra i valori pieno e minimo, mentre la
    tabella 1 INPS procede a fasce arrotondate al decimo, scarto di circa 0,2-0,4 euro per figlio;
    non modellate le maggiorazioni per disabilità (c. 4), madre under 21 (c. 7), genitori entrambi
    lavoratori (c. 8) e il forfait per quattro o più figli (c. 10); il figlio di 18-20 anni è
    considerato in possesso dei requisiti dell'art. 2; età 3 anni compresa nella fascia 1-3, da riscontrare)

    Args:
        isee: Valore ISEE familiare in euro (€), 0 se l'ISEE non è stato presentato (importi minimi, c. 9)
        n_figli: Numero totale di figli a carico (interi positivi, minimo 1)
        eta_figli: Lista delle età dei figli in anni — opzionale, necessaria per calcolare
                   maggiorazioni (es. [0, 2, 5] per figlio neonato, bimbo e bambino)
        genitore_solo: Nessun effetto: il D.Lgs. 230/2021 non prevede una maggiorazione del 30% per il
                       genitore solo (parametro mantenuto per compatibilità)
    """
    if n_figli <= 0:
        return {"errore": "Il numero di figli deve essere almeno 1"}

    # Importi 2026 (INPS circ. 7/2026, rivalutazione +1,4% ex art. 4 c. 11 D.Lgs. 230/2021)
    ISEE_MIN = 17468.51  # fino a questa soglia importo pieno (175 euro nominali, 15.000 ISEE)
    ISEE_MAX = 46582.71  # oltre importo minimo (50 euro nominali, 40.000 ISEE)
    # (importo pieno, importo minimo): c. 1 minorenni, c. 2 maggiorenni fino a 21 anni,
    # c. 3 maggiorazione per ciascun figlio successivo al secondo
    MINORENNE = (203.80, 58.30)
    MAGGIORENNE = (99.10, 29.10)
    SUCCESSIVO_AL_SECONDO = (99.10, 17.40)

    # Art. 4 c. 9: senza ISEE spettano gli importi minimi (0 = ISEE non presentato)
    senza_isee = isee <= 0

    def _scala(pieno_minimo: tuple[float, float]) -> float:
        pieno, minimo = pieno_minimo
        if senza_isee or isee >= ISEE_MAX:
            return minimo
        if isee <= ISEE_MIN:
            return pieno
        return pieno - (pieno - minimo) * (isee - ISEE_MIN) / (ISEE_MAX - ISEE_MIN)

    importo_base = round(_scala(MINORENNE), 2)
    importo_maggiorenne = round(_scala(MAGGIORENNE), 2)
    magg_terzo_figlio = round(_scala(SUCCESSIVO_AL_SECONDO), 2)
    # Art. 4 c. 1: +50% per il figlio sotto un anno (qualunque ISEE) e per i figli di 1-3 anni nei
    # nuclei con almeno tre figli solo fino alla soglia ISEE superiore (40.000 euro rivalutati)
    entro_soglia_isee = senza_isee or isee <= ISEE_MAX

    dettaglio_figli = []
    if eta_figli is None:
        eta_figli = [10] * n_figli  # Default: eta media senza maggiorazioni speciali
    eta_figli = list(eta_figli[:n_figli]) + [None] * (n_figli - len(eta_figli[:n_figli]))

    aventi_diritto = 0
    for i, eta in enumerate(eta_figli):
        maggiorazioni = []
        base_figlio = importo_base
        if eta is not None and eta >= 21:
            # Art. 4 c. 2: maggiorenni solo fino al compimento del ventunesimo anno
            dettaglio_figli.append({
                "figlio": i + 1, "eta": eta, "importo_base": 0.0, "maggiorazioni": [],
                "importo_mensile": 0.0,
                "nota": "Oltre il ventunesimo anno l'assegno non spetta (art. 4 c. 2 D.Lgs. 230/2021), salvo disabilita non modellata",
            })
            continue
        if eta is not None and eta >= 18:
            base_figlio = importo_maggiorenne
        importo_figlio = base_figlio
        aventi_diritto += 1

        if eta is not None and eta < 1:
            magg = round(base_figlio * 0.5, 2)
            maggiorazioni.append({"tipo": "figlio < 1 anno", "importo": magg})
            importo_figlio += magg

        if eta is not None and 1 <= eta <= 3 and n_figli >= 3 and entro_soglia_isee:
            magg = round(base_figlio * 0.5, 2)
            maggiorazioni.append({"tipo": "figlio 1-3 anni (3+ figli, +50%)", "importo": magg})
            importo_figlio += magg

        # Art. 4 c. 3: maggiorazione per ciascun figlio successivo al secondo
        if aventi_diritto > 2:
            maggiorazioni.append({"tipo": "figlio successivo al secondo", "importo": magg_terzo_figlio})
            importo_figlio += magg_terzo_figlio

        dettaglio_figli.append({
            "figlio": i + 1,
            "eta": eta,
            "importo_base": base_figlio,
            "maggiorazioni": maggiorazioni,
            "importo_mensile": round(importo_figlio, 2),
        })

    totale_mensile = round(sum(f["importo_mensile"] for f in dettaglio_figli), 2)
    totale_annuo = round(totale_mensile * 12, 2)

    return {
        "isee": isee,
        "isee_presentato": not senza_isee,
        "n_figli": n_figli,
        "importo_base_per_figlio": importo_base,
        "dettaglio_figli": dettaglio_figli,
        "genitore_solo": genitore_solo,
        "maggiorazione_genitore_solo": 0,
        "nota_genitore_solo": "Il D.Lgs. 230/2021 non prevede una maggiorazione per il genitore solo: il parametro non ha effetto",
        "totale_mensile": totale_mensile,
        "totale_annuo": totale_annuo,
        "riferimento_normativo": "D.Lgs. 230/2021 art. 4 - importi 2026 (INPS circ. 7/2026)",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_figli(
    reddito_complessivo: float,
    n_figli_over21: int,
    n_figli_disabili: int = 0,
) -> dict:
    """Calcola la detrazione IRPEF per figli a carico con età ≥21 anni (art. 12 TUIR).
    I figli under 21 rientrano nell'Assegno Unico Universale — non generano detrazione IRPEF.
    Vigenza: art. 12, comma 1, lett. c) TUIR — D.P.R. 917/1986 nel testo vigente al 2026-09-29
    (D.Lgs. 230/2021, dal 1° marzo 2022): 950 € per ciascun figlio di età pari o superiore a 21
    anni e inferiore a 30, e per ciascun figlio di 30 anni o più con disabilità accertata (art. 3
    L. 104/1992); la maggiorazione di 400 € per il figlio disabile è stata soppressa. Detrazione
    per la parte corrispondente al rapporto (95.000 € - reddito) / 95.000 €; la soglia sale di
    15.000 € per ogni figlio dopo il primo, per tutti. Comma 4: il rapporto si assume nelle prime
    quattro cifre decimali (troncamento) e la detrazione non compete se è pari a zero o a uno.
    Il tool calcola l'anno intero per l'intero importo: nessuna ripartizione tra i genitori (50%
    o accordo, lett. c) né rapporto a mesi (comma 3); il reddito va indicato già al netto
    dell'abitazione principale (comma 4-bis); l'età dei figli non è un input (chi ha 30 anni o
    più senza disabilità non genera detrazione: va escluso dal conteggio).
    Precisione: ESATTO (formula di legge con il troncamento del comma 4, per l'intero anno e senza
    ripartizione tra i genitori).

    Args:
        reddito_complessivo: Reddito complessivo annuo del contribuente in euro (€)
        n_figli_over21: Numero di figli a carico di età 21-29 anni, più quelli di 30 anni o più con disabilità (interi positivi)
        n_figli_disabili: Numero di figli disabili tra quelli indicati (informativo: dal 2022 non cambia l'importo, 950 € per tutti)
    """
    if n_figli_over21 <= 0:
        return {"errore": "Il numero di figli over 21 deve essere almeno 1"}

    n_figli_normali = n_figli_over21 - n_figli_disabili
    if n_figli_normali < 0:
        return {"errore": "I figli disabili non possono superare il totale figli over 21"}

    soglia = 95000 + 15000 * (n_figli_over21 - 1)
    detrazione_base = 950
    # Comma 4: rapporto troncato alla quarta cifra; pari a zero, negativo o uguale a uno
    # (reddito nullo) la detrazione non compete.
    rapporto = _rapporto_quattro_cifre(soglia - reddito_complessivo, soglia)
    compete = Decimal(0) < rapporto < Decimal(1) and reddito_complessivo > 0
    per_figlio = Decimal(detrazione_base) * rapporto if compete else Decimal(0)

    dettaglio = []
    for i in range(n_figli_over21):
        tipo = "ordinario" if i < n_figli_normali else "disabile"
        dettaglio.append({
            "figlio": i + 1,
            "tipo": tipo,
            "detrazione_teorica": detrazione_base,
            "importo": float(per_figlio),
        })
    totale = per_figlio * n_figli_over21

    return {
        "reddito_complessivo": reddito_complessivo,
        "n_figli_over21": n_figli_over21,
        "n_figli_disabili": n_figli_disabili,
        "soglia_reddito": soglia,
        "rapporto": float(rapporto) if compete else 0.0,
        "dettaglio": dettaglio,
        "detrazione_totale": _centesimi(totale),
        "riferimento_normativo": "Art. 12, comma 1, lett. c) e comma 4 TUIR — D.P.R. 917/1986 (mod. D.Lgs. 230/2021)",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_coniuge(reddito_complessivo: float) -> dict:
    """Calcola la detrazione IRPEF annua (12 mesi) per coniuge a carico (art. 12 TUIR).
    Il coniuge è a carico se il suo reddito non supera €2.840,51 (art. 12 co. 2; il limite di
    €4.000 riguarda solo i figli fino a 24 anni). Passare il reddito già al netto della rendita
    dell'abitazione principale (co. 4-bis). Il tool non rapporta a mese (co. 3): per meno di 12
    mesi il risultato va rapportato a mano.
    Vigenza: art. 12, comma 1, lett. a) e b) TUIR — D.P.R. 917/1986 (testo vigente al 2026-09-29):
    base 800/690 euro, maggiorazioni di 10-30 euro per redditi tra 29.000 e 35.200 euro, rapporti
    troncati alla quarta cifra decimale (co. 4).
    Precisione: ESATTO (formula di legge, importo annuo intero; mesi a carico non gestiti).

    Args:
        reddito_complessivo: Reddito complessivo annuo del contribuente in euro (€)
    """
    if reddito_complessivo <= 0:
        return {"errore": "Il reddito complessivo deve essere positivo"}

    if reddito_complessivo <= 15000:
        # art. 12 co. 1 lett. a) n. 1; con rapporto uguale a 1 spettano 690 euro (co. 4), stesso valore
        detrazione = 800 - 110 * _quoziente4(reddito_complessivo, 15000)
        fascia = "fino a 15.000€"
    elif reddito_complessivo <= 40000:
        detrazione = 690
        fascia = "15.001-40.000€"
    elif reddito_complessivo <= 80000:
        # lett. a) n. 3; rapporto zero: la detrazione non compete (co. 4)
        detrazione = 690 * _quoziente4(80000 - reddito_complessivo, 40000)
        fascia = "40.001-80.000€"
    else:
        detrazione = 0
        fascia = "oltre 80.000€"

    # art. 12 co. 1 lett. b): maggiorazioni sommate alla detrazione di lett. a)
    maggiorazione = 0
    for da, a_, importo in (
        (29000, 29200, 10),
        (29200, 34700, 20),
        (34700, 35000, 30),
        (35000, 35100, 20),
        (35100, 35200, 10),
    ):
        if da < reddito_complessivo <= a_:
            maggiorazione = importo
    detrazione += maggiorazione

    return {
        "reddito_complessivo": reddito_complessivo,
        "fascia": fascia,
        "maggiorazione": maggiorazione,
        "detrazione": round(detrazione, 2),
        "limite_reddito_coniuge": 2840.51,
        "riferimento_normativo": "Art. 12, comma 1, lett. a) e b), commi 2 e 4 TUIR — D.P.R. 917/1986",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_altri_familiari(
    reddito_complessivo: float,
    n_familiari: int,
) -> dict:
    """Calcola la detrazione IRPEF per gli ascendenti conviventi a carico (art. 12, comma 1, lett. d) TUIR).
    Vigenza: art. 12, comma 1, lett. d) TUIR — D.P.R. 917/1986 nel testo vigente al 2026-09-29:
    750 € per ciascun ascendente che conviva con il contribuente (i fratelli, le sorelle, i nipoti
    e gli altri soggetti dell'art. 433 c.c. non danno più diritto alla detrazione), da ripartire pro
    quota tra coloro che hanno diritto; spetta per il rapporto (80.000 € - reddito) / 80.000 €.
    Comma 4: il rapporto si assume nelle prime quattro cifre decimali (troncamento) e la
    detrazione non compete se è pari a zero o a uno (reddito nullo). Il familiare deve avere un
    reddito non superiore a 2.840,51 € (comma 2). Il tool calcola l'anno intero per l'intero
    importo: nessuna ripartizione pro quota né rapporto a mesi (comma 3); il reddito va indicato
    già al netto dell'abitazione principale (comma 4-bis).
    Precisione: ESATTO (750 € x rapporto troncato alla quarta cifra, per l'intero anno e senza
    ripartizione pro quota).

    Args:
        reddito_complessivo: Reddito complessivo annuo del contribuente in euro (€), al netto dell'abitazione principale
        n_familiari: Numero di ascendenti conviventi a carico (interi positivi)
    """
    if n_familiari <= 0:
        return {"errore": "Il numero di familiari deve essere almeno 1"}

    soglia = 80000
    detrazione_unitaria = 750
    rapporto = _rapporto_quattro_cifre(soglia - reddito_complessivo, soglia)
    compete = Decimal(0) < rapporto < Decimal(1) and reddito_complessivo > 0
    per_familiare = Decimal(detrazione_unitaria) * rapporto if compete else Decimal(0)

    return {
        "reddito_complessivo": reddito_complessivo,
        "n_familiari": n_familiari,
        "soglia_reddito": soglia,
        "rapporto": float(rapporto) if compete else 0.0,
        "detrazione_unitaria_teorica": detrazione_unitaria,
        "detrazione_per_familiare": _centesimi(per_familiare),
        "detrazione_totale": _centesimi(per_familiare * n_familiari),
        "riferimento_normativo": "Art. 12, comma 1, lett. d) e comma 4 TUIR — D.P.R. 917/1986",
    }


@mcp.tool(tags={"fiscale"})
@sourced("irpef_scaglioni")
def detrazione_lavoro_dipendente(
    reddito_complessivo: float,
    giorni_lavoro: int = 365,
    tempo_determinato: bool = False,
) -> dict:
    """Calcola la detrazione IRPEF per redditi di lavoro dipendente (art. 13 TUIR), rapportata
    ai giorni lavorati nell'anno, con l'aumento di 65 euro (co. 1.1) e i minimi (co. 1 lett. a).
    Vigenza: art. 13, commi 1, 1.1 e 6 TUIR (testo vigente al 2026-09-29): 1.955 euro fino a
    15.000 (art. 13 co. 1 lett. a), minimo 690 euro (1.380 per i rapporti a tempo determinato)
    sulla detrazione rapportata ai giorni, +65 euro tra 25.000 e 35.000 euro (sommati per intero),
    rapporti troncati alla quarta cifra decimale.
    Precisione: ESATTO (formula di legge; il +65 e' sommato per intero alla detrazione rapportata).

    Args:
        reddito_complessivo: Reddito complessivo annuo in euro (€), al netto della rendita
                             dell'abitazione principale (art. 13 co. 6-bis)
        giorni_lavoro: Giorni lavorati nell'anno (1-365; default 365 per anno intero)
        tempo_determinato: True per rapporti a tempo determinato (minimo 1.380 euro invece di 690)
    """
    giorni_lavoro = min(max(giorni_lavoro, 1), 365)

    if reddito_complessivo <= 15000:
        detrazione_annua = _IRPEF["detrazioni_lavoro_dipendente"][0]["detrazione"]
        fascia = "fino a 15.000€"
    elif reddito_complessivo <= 28000:
        detrazione_annua = 1910 + 1190 * _quoziente4(28000 - reddito_complessivo, 28000 - 15000)
        fascia = "15.001-28.000€"
    elif reddito_complessivo <= 50000:
        detrazione_annua = 1910 * _quoziente4(50000 - reddito_complessivo, 50000 - 28000)
        fascia = "28.001-50.000€"
    else:
        detrazione_annua = 0
        fascia = "oltre 50.000€"

    detrazione = detrazione_annua * giorni_lavoro / 365
    minimo = 0
    if reddito_complessivo <= 15000:
        # art. 13 co. 1 lett. a): minimo sulla detrazione effettivamente spettante
        minimo = 1380 if tempo_determinato else 690
        detrazione = max(detrazione, minimo)
    aumento = 65 if 25000 < reddito_complessivo <= 35000 else 0  # art. 13 co. 1.1
    detrazione = round(detrazione + aumento, 2)

    return {
        "reddito_complessivo": reddito_complessivo,
        "giorni_lavoro": giorni_lavoro,
        "tempo_determinato": tempo_determinato,
        "fascia": fascia,
        "detrazione_annua_piena": round(detrazione_annua, 2),
        "minimo_applicabile": minimo,
        "aumento_comma_1_1": aumento,
        "detrazione_rapportata": detrazione,
        "riferimento_normativo": "Art. 13, commi 1, 1.1 e 6 TUIR — D.P.R. 917/1986",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_pensione(
    reddito_complessivo: float,
    giorni: int = 365,
) -> dict:
    """Calcola la detrazione IRPEF per redditi da pensione (art. 13 TUIR), rapportata ai giorni,
    con il minimo di 713 euro e l'aumento di 50 euro. Passare il reddito già al netto della
    rendita dell'abitazione principale (co. 6-bis).
    Vigenza: art. 13, commi 3, 3-bis e 6 TUIR — D.P.R. 917/1986 (testo vigente al 2026-09-29):
    1.955 euro fino a 8.500 (minimo 713 euro sulla detrazione rapportata), +50 euro tra 25.000 e
    29.000 euro (sommati per intero alla detrazione rapportata), rapporti troncati alla quarta
    cifra decimale.
    Precisione: ESATTO (formula di legge).

    Args:
        reddito_complessivo: Reddito complessivo annuo in euro (€)
        giorni: Giorni di godimento della pensione nell'anno (1-365; default 365 per anno intero)
    """
    giorni = min(max(giorni, 1), 365)

    if reddito_complessivo <= 8500:
        detrazione_annua = 1955
        fascia = "fino a 8.500€"
    elif reddito_complessivo <= 28000:
        detrazione_annua = 700 + 1255 * _quoziente4(28000 - reddito_complessivo, 28000 - 8500)
        fascia = "8.501-28.000€"
    elif reddito_complessivo <= 50000:
        detrazione_annua = 700 * _quoziente4(50000 - reddito_complessivo, 50000 - 28000)
        fascia = "28.001-50.000€"
    else:
        detrazione_annua = 0
        fascia = "oltre 50.000€"

    detrazione = detrazione_annua * giorni / 365
    minimo = 0
    if reddito_complessivo <= 8500:
        minimo = 713  # art. 13 co. 3 lett. a)
        detrazione = max(detrazione, minimo)
    aumento = 50 if 25000 < reddito_complessivo <= 29000 else 0  # art. 13 co. 3-bis
    detrazione = round(detrazione + aumento, 2)

    return {
        "reddito_complessivo": reddito_complessivo,
        "giorni": giorni,
        "fascia": fascia,
        "detrazione_annua_piena": round(detrazione_annua, 2),
        "minimo_applicabile": minimo,
        "aumento_comma_3_bis": aumento,
        "detrazione_rapportata": detrazione,
        "riferimento_normativo": "Art. 13, commi 3, 3-bis e 6 TUIR — D.P.R. 917/1986",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_assegno_coniuge(reddito_complessivo: float) -> dict:
    """Calcola la detrazione per assegno periodico percepito dal coniuge separato o divorziato.
    L'assegno periodico è reddito assimilato al lavoro dipendente per il percipiente
    e onere deducibile ex art. 10 TUIR per chi lo corrisponde.
    Vigenza: art. 13, comma 5-bis, TUIR (testo vigente al 2026-09-29): misura pari a quella del
    comma 3 (1.955 euro fino a 8.500; 700 + 1.255 x rapporto fino a 28.000; 700 x rapporto fino a
    50.000), non rapportata ad alcun periodo, rapporti troncati alla quarta cifra decimale (co. 6).
    La maggiorazione di 50 euro del co. 3-bis non e' applicata (rinvio non chiaro, punto aperto).
    Precisione: ESATTO (formula di legge, esclusa la maggiorazione del co. 3-bis).

    Args:
        reddito_complessivo: Reddito complessivo annuo del percipiente l'assegno in euro (€)
    """
    if reddito_complessivo <= 0:
        return {"errore": "Il reddito complessivo deve essere positivo"}

    if reddito_complessivo <= 8500:
        detrazione = 1955
        fascia = "fino a 8.500€"
    elif reddito_complessivo <= 28000:
        detrazione = 700 + 1255 * _quoziente4(28000 - reddito_complessivo, 28000 - 8500)
        fascia = "8.501-28.000€"
    elif reddito_complessivo <= 50000:
        detrazione = 700 * _quoziente4(50000 - reddito_complessivo, 50000 - 28000)
        fascia = "28.001-50.000€"
    else:
        detrazione = 0
        fascia = "oltre 50.000€"

    return {
        "reddito_complessivo": reddito_complessivo,
        "fascia": fascia,
        "detrazione": round(detrazione, 2),
        "nota": "L'assegno periodico al coniuge e reddito assimilato al lavoro dipendente per il percipiente e onere deducibile per chi lo versa.",
        "riferimento_normativo": "Art. 13, commi 5-bis e 6 TUIR (misura del comma 3) — Art. 10, comma 1, lett. c) TUIR",
    }


@mcp.tool(tags={"fiscale"})
def detrazione_canone_locazione(
    reddito_complessivo: float,
    tipo_contratto: str = "libero",
    canone_annuo: float = 0,
) -> dict:
    """Calcola la detrazione IRPEF per inquilini con contratto di locazione come abitazione principale.
    Vigenza: art. 16 TUIR — D.P.R. 917/1986 nel testo vigente al 2026-09-29 (co. 01 contratti
    liberi L. 431/1998: 300/150 €; co. 1 concordati: lire 960.000/480.000 = 495,80/247,90 €;
    co. 1-ter giovani 20-31 anni non compiuti: 991,60 € oppure, se superiore, il 20% del canone
    entro 2.000 €, per i primi quattro anni). Soglie di reddito non aggiornate dal 1997.
    Il tool restituisce l'importo annuo intero, non rapportato al periodo di abitazione principale
    (co. 1-quinquies) né ripartito tra gli aventi diritto (co. 1-quater); non tratta il co. 1-bis
    (lavoratori dipendenti trasferiti).
    Precisione: ESATTO (importi fissi per scaglione di reddito come da legge; per i giovani serve
    il canone annuo, senza il quale l'importo restituito è il minimo di legge di 991,60 €).

    Args:
        reddito_complessivo: Reddito complessivo annuo in euro (€)
        tipo_contratto: Tipologia contrattuale: 'libero' (art. 16 co. 01, max €300/150),
                        'concordato' (co. 1, max €495,80/247,90),
                        'giovani_under31' (co. 1-ter, €991,60 o, se superiore, 20% del canone max €2.000, solo reddito ≤€15.493,71)
        canone_annuo: Canone annuo di locazione in euro (€), usato solo per 'giovani_under31'; se omesso (0) si applica il minimo di €991,60
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
            # Art. 16 co. 1-ter: 991,60 euro, ovvero, se superiore, il 20% del canone
            # entro il limite massimo di 2.000 euro.
            venti_per_cento = min(canone_annuo * 0.20, 2000) if canone_annuo > 0 else 0
            detrazione = max(991.60, venti_per_cento)
        else:
            detrazione = 0

    return {
        "reddito_complessivo": reddito_complessivo,
        "tipo_contratto": tipo_contratto,
        "detrazione": round(detrazione, 2),
        "nota_giovani": (
            "Per giovani 20-31 anni non compiuti (art. 16 co. 1-ter): 991,60€ oppure, se superiore, "
            "20% del canone entro 2.000€; reddito <= 15.493,71€; primi quattro anni di contratto"
            + ("" if canone_annuo > 0 else ". Canone non indicato: applicato il minimo di legge, "
               "passare canone_annuo per il calcolo del 20%")
        ) if tipo_contratto == "giovani_under31" else None,
        "riferimento_normativo": "Art. 16 TUIR — D.P.R. 917/1986",
    }


def _acconto_due_rate(acconto_totale: float) -> bool:
    """True se l'acconto va versato in due rate (art. 17, c. 3, D.P.R. 435/2001).

    Le rate sono due "salvo che il versamento da effettuare alla scadenza della prima
    rata non superi euro 103": la prima rata e' il 40% dell'acconto, arrotondato al
    centesimo. 257,51 -> 103,00 (unica soluzione); 257,52 -> 103,01 (due rate).
    """
    from decimal import Decimal, ROUND_HALF_UP

    prima = (Decimal(str(acconto_totale)) * Decimal("0.40")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return prima > Decimal("103")


@mcp.tool(tags={"fiscale"})
def acconto_irpef(
    imposta_anno_precedente: float,
    metodo: str = "storico",
) -> dict:
    """Calcola l'acconto IRPEF (primo e secondo acconto) con importi e scadenze.
    Vigenza: art. 17, c. 3, D.P.R. 435/2001 (due rate, 40% e 60%, salvo che la prima rata
    non superi euro 103, quindi unica soluzione fino a 257,51); art. 4, c. 2, lett. a), D.L.
    69/1989 (soglia di esenzione 100.000 lire = €51,65); art. 11, c. 18, D.L. 76/2013 (misura
    dell'acconto al 100% dal periodo d'imposta 2013), verificati sul testo vigente al 2026-09-29.
    Non applica la ripartizione 50% + 50% dei soggetti ISA (art. 58 D.L. 124/2019).
    Precisione: ESATTO per i soggetti non ISA (soglia esenzione €51,65; oltre, unica soluzione
    entro il 30 novembre se il 40% non supera €103; altrimenti due rate: 40% primo acconto,
    60% secondo). Il rigo RN34 del modello e' in euro interi: passare l'importo del rigo.

    Args:
        imposta_anno_precedente: Imposta netta IRPEF risultante dalla dichiarazione dell'anno
                                 precedente in euro (€) — da rigo RN34 del modello Redditi PF
                                 (in euro interi: con i centesimi le soglie si applicano
                                 all'importo esatto, mentre il modello arrotonda all'unita')
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

    if not _acconto_due_rate(acconto_totale):
        return {
            "imposta_anno_precedente": imposta_anno_precedente,
            "metodo": metodo,
            "acconto_dovuto": True,
            "acconto_totale": acconto_totale,
            "unica_soluzione": {
                "importo": acconto_totale,
                "percentuale": 100,
                "scadenza": "30 novembre",
            },
            "motivo": "Prima rata (40%) non superiore a 103€: versamento in unica soluzione entro il 30 novembre",
            "nota_previsionale": "Con metodo previsionale, gli importi vanno calcolati sull'imposta stimata per l'anno corrente" if metodo == "previsionale" else None,
            "riferimento_normativo": "Art. 17 D.P.R. 435/2001 — Art. 4 D.L. 69/1989",
        }

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
    Vigenza: art. 3, comma 4, D.Lgs. 23/2011 (versamento nei termini IRPEF); art. 17, c. 3,
    D.P.R. 435/2001 (due rate, 40% e 60%, salvo che la prima rata non superi euro 103, quindi
    unica soluzione fino a 257,51); soglia di esenzione €51,65 (art. 4, c. 2, lett. a), D.L.
    69/1989); acconto totale = 100% della cedolare secca dell'anno precedente.
    Precisione: ESATTO (soglia esenzione €51,65; oltre, unica soluzione entro il 30 novembre
    se il 40% non supera €103; altrimenti due rate: 40% primo acconto, 60% secondo).
    Il rigo RB11 del modello e' in euro interi: passare l'importo del rigo.

    Args:
        imposta_anno_precedente: Imposta da cedolare secca risultante dalla dichiarazione
                                 dell'anno precedente in euro (€), da rigo RB11 (in euro
                                 interi: con i centesimi le soglie si applicano all'importo
                                 esatto, mentre il modello arrotonda all'unita')
    """
    if imposta_anno_precedente <= 51.65:
        return {
            "imposta_anno_precedente": imposta_anno_precedente,
            "acconto_dovuto": False,
            "motivo": "Nessun acconto dovuto: imposta anno precedente <= 51.65€",
        }

    acconto_totale = round(imposta_anno_precedente, 2)

    if not _acconto_due_rate(acconto_totale):
        return {
            "imposta_anno_precedente": imposta_anno_precedente,
            "acconto_dovuto": True,
            "acconto_totale": acconto_totale,
            "unica_soluzione": {
                "importo": acconto_totale,
                "percentuale": 100,
                "scadenza": "30 novembre",
            },
            "motivo": "Prima rata (40%) non superiore a 103€: versamento in unica soluzione entro il 30 novembre",
            "riferimento_normativo": "Art. 3, comma 4, D.Lgs. 23/2011",
        }

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
    tasso_interesse_annuo: float = 4.0,
) -> dict:
    """Calcola il piano di rateizzazione delle imposte IRPEF e addizionali da dichiarazione.
    Vigenza: art. 20 D.Lgs. 241/1997 (rate mensili di uguale importo, ultima entro il 16
    dicembre, c. 1; versamenti entro il giorno 16 di ciascun mese, c. 4); art. 17, c. 2,
    D.P.R. 435/2001 (prima rata entro il 30 luglio con maggiorazione dello 0,40% sull'importo),
    testi riletti su Normattiva il 2026-09-29. Da 2 a 7 rate se la prima e' a giugno, 6 se a luglio.
    Precisione: INDICATIVO (la prima rata e' alla data indicata, le altre il 16 dei mesi
    successivi senza slittamenti per festivi o proroga di agosto; gli interessi seguono la
    tabella AdE per titolari di partita IVA: 0,18% sulla seconda rata, poi +0,33% al mese
    con il tasso del 4%, applicati al capitale di ciascuna rata).

    Args:
        importo_totale: Importo totale da rateizzare in euro (€)
        n_rate: Numero di rate mensili (2-7; con prima rata a luglio al massimo 6, perche' il
                pagamento deve essere completato entro il 16 dicembre)
        data_prima_rata: Data della prima rata, 30 giugno oppure 30 luglio con maggiorazione
                         0,40% (YYYY-MM-DD)
        tasso_interesse_annuo: Tasso di interesse annuo in percentuale (default 4,0%, quello
                               applicato dall'AdE alla rateizzazione delle imposte da
                               dichiarazione, art. 20, c. 2, D.Lgs. 241/1997; pari allo 0,33%
                               mensile)
    """
    from datetime import date as _date
    from decimal import Decimal, ROUND_HALF_UP

    if n_rate < 2 or n_rate > 7:
        return {"errore": "Il numero di rate deve essere tra 2 e 7"}
    if importo_totale <= 0:
        return {"errore": "L'importo totale deve essere positivo"}

    try:
        dt_prima = _date.fromisoformat(data_prima_rata)
    except ValueError:
        return {"errore": "data_prima_rata non valida, usare formato YYYY-MM-DD"}

    def _q(x) -> float:
        return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    # Scadenze: prima rata alla data indicata, poi il 16 di ciascun mese (art. 20, c. 4)
    date_rate = [dt_prima]
    for i in range(1, n_rate):
        mese = dt_prima.month + i
        anno = dt_prima.year + (mese - 1) // 12
        date_rate.append(_date(anno, (mese - 1) % 12 + 1, 16))

    # Il pagamento deve essere completato entro il 16 dicembre (art. 20, c. 1)
    if date_rate[-1] > _date(dt_prima.year, 12, 16):
        return {
            "errore": f"Con {n_rate} rate l'ultima scade il {date_rate[-1].isoformat()}, oltre il "
            "16 dicembre: il pagamento deve essere completato entro il 16 dicembre dello stesso "
            "anno (art. 20, c. 1, D.Lgs. 241/1997)",
        }

    # Prima rata dal 1 al 30 luglio: maggiorazione 0,40% sulle somme da versare (art. 17, c. 2)
    maggiorazione = 0.0
    importo_da_rateizzare = importo_totale
    if dt_prima.month == 7:
        importo_da_rateizzare = _q(Decimal(str(importo_totale)) * Decimal("1.004"))
        maggiorazione = _q(Decimal(str(importo_da_rateizzare)) - Decimal(str(importo_totale)))

    capitale_base = _q(Decimal(str(importo_da_rateizzare)) / n_rate)
    # Percentuali di interesse per rata (tabella AdE): 16 giorni sulla seconda, poi un mese
    # (tasso/12 arrotondato a due decimali) per ciascuna rata successiva
    t = Decimal(str(tasso_interesse_annuo))
    primo_passo = Decimal(str(_q(t * 16 / 360)))
    passo_mensile = Decimal(str(_q(t / 12)))

    piano = []
    for i in range(n_rate):
        # l'eventuale resto dell'arrotondamento e' assegnato all'ultima rata
        if i == n_rate - 1:
            capitale = _q(Decimal(str(importo_da_rateizzare)) - Decimal(str(capitale_base)) * (n_rate - 1))
        else:
            capitale = capitale_base
        pct = Decimal(0) if i == 0 else primo_passo + passo_mensile * (i - 1)
        interessi = _q(Decimal(str(capitale)) * pct / 100)
        piano.append({
            "rata": i + 1,
            "data_scadenza": date_rate[i].isoformat(),
            "importo_capitale": capitale,
            "percentuale_interessi": float(pct),
            "interessi": interessi,
            "rata_totale": _q(Decimal(str(capitale)) + Decimal(str(interessi))),
        })

    totale_interessi = _q(sum(Decimal(str(r["interessi"])) for r in piano))
    totale_versato = _q(sum(Decimal(str(r["rata_totale"])) for r in piano))

    out = {
        "importo_totale": importo_totale,
        "n_rate": n_rate,
        "tasso_interesse_annuo_pct": tasso_interesse_annuo,
        "piano_rate": piano,
        "totale_interessi": totale_interessi,
        "totale_versato": totale_versato,
        "riferimento_normativo": "Art. 20 D.Lgs. 241/1997",
    }
    if maggiorazione:
        out["maggiorazione_0_40"] = maggiorazione
        out["importo_da_rateizzare"] = importo_da_rateizzare
        out["riferimento_normativo"] += "; art. 17, c. 2, D.P.R. 435/2001"
    return out


@mcp.tool(tags={"fiscale"})
@sourced("codici_tributo")
def cerca_codice_tributo(query: str) -> str:
    """Cerca un codice tributo F24 per codice o descrizione.

    Usare quando serve il codice tributo per compilare un modello F24.
    Restituisce: codice, descrizione, sezione e categoria per ogni risultato trovato.
    Vigenza: sottoinsieme dei codici piu' usati, riletto il 2026-09-29 sulle tabelle
    dell'Agenzia delle Entrate (erariali e regionali 23/09/2026; F24 ELIDE 27/07/2026;
    tributi locali 27/03/2026). I codici 1500-1504 (registro locazioni) e GA01-GA05
    (contributo unificato TAR/Consiglio di Stato) si versano con il modello F24 ELIDE;
    il contributo unificato civile non ha codice F24. Il codice 1038 e' soppresso dal
    1.1.2017 (ris. AdE 13/E del 17/3/2016): le ritenute su provvigioni usano il 1040.
    Precisione: INDICATIVO (ricerca per codice o descrizione su un sottoinsieme delle
    tabelle AdE, non sull'elenco completo; verificare il codice sulla tabella o sulla
    risoluzione prima del versamento).

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


def _rapporto_quattro_cifre(numeratore: float, denominatore: float) -> Decimal:
    """Ratio truncated to the first four decimal digits (art. 12 co. 4 and art. 13 co. 6 TUIR)."""
    q = Decimal(str(numeratore)) / Decimal(str(denominatore))
    return q.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


def _centesimi(valore: Decimal) -> float:
    """Round a Decimal amount to the cent (half up) and return a float."""
    return float(valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _detrazione_art13(reddito: float, tipo_reddito: str) -> float:
    """Detrazione dell'art. 13 TUIR per l'anno intero, sul reddito complessivo.

    dipendente (co. 1 + 1.1), pensionato (co. 3 + 3-bis), autonomo (co. 5 + 5-ter); i rapporti
    sono assunti nelle prime quattro cifre decimali (co. 6). Altri tipi: nessuna detrazione.
    """
    r = Decimal(str(reddito))
    if tipo_reddito == "dipendente":
        if r <= 15000:
            d = Decimal(1955)
        elif r <= 28000:
            d = Decimal(1910) + Decimal(1190) * _rapporto_quattro_cifre(28000 - reddito, 13000)
        elif r <= 50000:
            d = Decimal(1910) * _rapporto_quattro_cifre(50000 - reddito, 22000)
        else:
            d = Decimal(0)
        if d > 0 and 25000 < r <= 35000:  # co. 1.1
            d += 65
    elif tipo_reddito == "pensionato":
        if r <= 8500:
            d = Decimal(1955)
        elif r <= 28000:
            d = Decimal(700) + Decimal(1255) * _rapporto_quattro_cifre(28000 - reddito, 19500)
        elif r <= 50000:
            d = Decimal(700) * _rapporto_quattro_cifre(50000 - reddito, 22000)
        else:
            d = Decimal(0)
        if d > 0 and 25000 < r <= 29000:  # co. 3-bis
            d += 50
    elif tipo_reddito == "autonomo":
        if r <= 5500:
            d = Decimal(1265)
        elif r <= 28000:
            d = Decimal(500) + Decimal(765) * _rapporto_quattro_cifre(28000 - reddito, 22500)
        elif r <= 50000:
            d = Decimal(500) * _rapporto_quattro_cifre(50000 - reddito, 22000)
        else:
            d = Decimal(0)
        if d > 0 and 11000 < r <= 17000:  # co. 5-ter
            d += 50
    else:
        d = Decimal(0)
    return _centesimi(d)
