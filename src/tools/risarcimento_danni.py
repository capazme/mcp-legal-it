"""Calcoli per risarcimento danni: danno biologico micropermanenti (art. 139 CdA) e macropermanenti
(art. 138 CdA), danno non patrimoniale con tutte le componenti, danno parentale (tabelle Milano/Roma),
menomazioni plurime (Balthazard), indennizzo INAIL, equo indennizzo causa di servizio."""

import json
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "tabella_danno_bio.json") as f:
    _DANNO_BIO = json.load(f)

with open(_DATA / "tabella_milano_roma.json") as f:
    _PARENTALE = json.load(f)

_MICRO = _DANNO_BIO["micropermanenti"]
_MACRO = _DANNO_BIO["macropermanenti"]


def _coefficiente_eta(eta: int) -> float:
    """Return age coefficient for macropermanenti from range keys."""
    for chiave, coeff in _MACRO["coefficiente_eta"].items():
        if chiave.startswith("_"):
            continue
        low, high = map(int, chiave.split("-"))
        if low <= eta <= high:
            return coeff
    return 0.40


def _interpola_punto_base(percentuale: int) -> float:
    """Interpolate punto_base from macropermanenti table."""
    punti = {int(k): v for k, v in _MACRO["punto_base"].items()}
    soglie = sorted(punti.keys())

    if percentuale in punti:
        return punti[percentuale]

    for i in range(len(soglie) - 1):
        if soglie[i] < percentuale < soglie[i + 1]:
            low, high = soglie[i], soglie[i + 1]
            ratio = (percentuale - low) / (high - low)
            return punti[low] + ratio * (punti[high] - punti[low])

    if percentuale < soglie[0]:
        return punti[soglie[0]]
    return punti[soglie[-1]]


@mcp.tool()
def danno_biologico_micro(
    percentuale_invalidita: int,
    eta_vittima: int,
    giorni_itt: int = 0,
    giorni_itp75: int = 0,
    giorni_itp50: int = 0,
    giorni_itp25: int = 0,
    personalizzazione_pct: float = 0,
) -> dict:
    """Calcola il danno biologico per MICROPERMANENTI (≤9% di invalidità).
    Applica art. 139 Codice delle Assicurazioni (D.Lgs. 209/2005).
    Vigenza: tabelle aggiornate al DM 18/07/2025.
    Precisione: ESATTO (formula di legge applicata ai valori tabellari vigenti).

    Usa questo quando: sinistro stradale o sanitario con invalidità permanente tra 1% e 9%.
    NON usare per: invalidità ≥10% → usa danno_biologico_macro().
    NON usare per: danno non patrimoniale con tutte le componenti → usa danno_non_patrimoniale().

    Args:
        percentuale_invalidita: Percentuale di invalidità permanente (1-9)
        eta_vittima: Età della vittima al momento del sinistro (0-120)
        giorni_itt: Giorni di invalidità temporanea totale al 100%
        giorni_itp75: Giorni di invalidità temporanea parziale al 75%
        giorni_itp50: Giorni di invalidità temporanea parziale al 50%
        giorni_itp25: Giorni di invalidità temporanea parziale al 25%
        personalizzazione_pct: Percentuale di personalizzazione per danno morale (0-33.33)
    """
    if not 1 <= percentuale_invalidita <= 9:
        return {"errore": "Micropermanenti: percentuale deve essere tra 1 e 9"}

    if not 0 <= eta_vittima <= 120:
        return {"errore": "Età non valida"}

    if personalizzazione_pct < 0 or personalizzazione_pct > _MICRO["maggiorazione_morale_max_pct"]:
        return {"errore": f"Personalizzazione deve essere tra 0 e {_MICRO['maggiorazione_morale_max_pct']}%"}

    punto_base = _MICRO["punto_base"]
    coefficienti = _MICRO["coefficienti_punto"]
    eta_inizio_decremento = _MICRO["eta_decremento_da"]
    decremento_pct = _MICRO["decremento_eta_pct_per_anno"]

    # Age adjustment: 0.5% reduction per year from age 11 onward (art. 139 c. 1)
    if eta_vittima >= eta_inizio_decremento:
        anni_sopra = eta_vittima - eta_inizio_decremento
        riduzione = 1 - (decremento_pct / 100) * anni_sopra
        riduzione = max(riduzione, 0)
    else:
        riduzione = 1.0

    danno_permanente = 0.0
    dettaglio_punti = []
    for p in range(1, percentuale_invalidita + 1):
        coeff = coefficienti[str(p)]
        valore_punto = punto_base * coeff * riduzione
        danno_permanente += valore_punto
        dettaglio_punti.append({"percentuale": p, "coefficiente": coeff, "valore": round(valore_punto, 2)})

    # Invalidità temporanea
    itt = giorni_itt * _MICRO["invalidita_temporanea_totale_giornaliera"]
    itp75 = giorni_itp75 * _MICRO["invalidita_temporanea_parziale_75_pct"]
    itp50 = giorni_itp50 * _MICRO["invalidita_temporanea_parziale_50_pct"]
    itp25 = giorni_itp25 * _MICRO["invalidita_temporanea_parziale_25_pct"]
    danno_temporaneo = itt + itp75 + itp50 + itp25

    danno_base = danno_permanente + danno_temporaneo

    # Personalizzazione (danno morale)
    maggiorazione_morale = danno_base * (personalizzazione_pct / 100)

    totale = danno_base + maggiorazione_morale

    return {
        "percentuale_invalidita": percentuale_invalidita,
        "eta_vittima": eta_vittima,
        "punto_base": punto_base,
        "riduzione_eta": round(riduzione, 4),
        "danno_permanente": round(danno_permanente, 2),
        "danno_temporaneo": {
            "itt": {"giorni": giorni_itt, "importo": round(itt, 2)},
            "itp_75": {"giorni": giorni_itp75, "importo": round(itp75, 2)},
            "itp_50": {"giorni": giorni_itp50, "importo": round(itp50, 2)},
            "itp_25": {"giorni": giorni_itp25, "importo": round(itp25, 2)},
            "totale": round(danno_temporaneo, 2),
        },
        "danno_base": round(danno_base, 2),
        "personalizzazione_pct": personalizzazione_pct,
        "maggiorazione_morale": round(maggiorazione_morale, 2),
        "totale_risarcimento": round(totale, 2),
        "dettaglio_punti": dettaglio_punti,
        "riferimento_normativo": "Art. 139 Cod. Assicurazioni (D.Lgs. 209/2005) — DM 18/07/2025",
    }


@mcp.tool()
def danno_biologico_macro(
    percentuale_invalidita: int,
    eta_vittima: int,
    personalizzazione_pct: float = 0,
) -> dict:
    """Calcola il danno biologico per MACROPERMANENTI (≥10% di invalidità).
    Applica art. 138 Codice delle Assicurazioni (D.Lgs. 209/2005) con tabella unica nazionale.
    Vigenza: Tabella unica nazionale DM 2024 — valori Milano per interpolazione.
    Precisione: INDICATIVO (interpolazione lineare sui punti tabellari; il valore esatto
    dipende dalla tabella unica nazionale definitiva ex art. 138 CdA, ancora in via di adozione).

    Usa questo quando: sinistro stradale o sanitario con invalidità permanente tra 10% e 100%.
    NON usare per: invalidità <10% → usa danno_biologico_micro().
    NON usare per: danno non patrimoniale con tutte le componenti → usa danno_non_patrimoniale().

    Args:
        percentuale_invalidita: Percentuale di invalidità permanente (10-100)
        eta_vittima: Età della vittima al momento del sinistro (0-120)
        personalizzazione_pct: Percentuale di personalizzazione per danno morale (0-50)
    """
    if not 10 <= percentuale_invalidita <= 100:
        return {"errore": "Macropermanenti: percentuale deve essere tra 10 e 100"}

    if not 0 <= eta_vittima <= 120:
        return {"errore": "Età non valida"}

    if personalizzazione_pct < 0 or personalizzazione_pct > 50:
        return {"errore": "Personalizzazione macropermanenti deve essere tra 0 e 50%"}

    punto_base = _interpola_punto_base(percentuale_invalidita)
    coeff_eta = _coefficiente_eta(eta_vittima)

    danno_base = punto_base * percentuale_invalidita * coeff_eta

    maggiorazione_morale = danno_base * (personalizzazione_pct / 100)
    totale = danno_base + maggiorazione_morale

    return {
        "percentuale_invalidita": percentuale_invalidita,
        "eta_vittima": eta_vittima,
        "punto_base_interpolato": round(punto_base, 2),
        "coefficiente_eta": coeff_eta,
        "danno_base": round(danno_base, 2),
        "personalizzazione_pct": personalizzazione_pct,
        "maggiorazione_morale": round(maggiorazione_morale, 2),
        "totale_risarcimento": round(totale, 2),
        "riferimento_normativo": "Art. 138 Cod. Assicurazioni (D.Lgs. 209/2005) — Tabella unica nazionale DM 2024",
    }


@mcp.tool()
def danno_parentale(
    vittima: str,
    superstite: str,
    tabella: str = "milano",
    personalizzazione_pct: float = 50,
) -> dict:
    """Calcola il danno da perdita del rapporto parentale (danno morale da morte del congiunto).
    Vigenza: Tabelle di Milano 2024 e Roma 2024 (aggiornate con Cass. SU 26972/2008 e successive).
    Precisione: INDICATIVO (forchetta min-max; il valore finale dipende dalla personalizzazione
    giudiziale sulle concrete circostanze del rapporto e del lutto).

    Usa questo quando: richiesta risarcimento per morte del congiunto in sinistro o illecito.
    NON usare per: danno biologico del superstite (es. disturbo dell'adattamento) → usa danno_biologico_micro/macro().

    Args:
        vittima: Ruolo della vittima deceduta (figlio, genitore, coniuge, fratello, nipote, nonno)
        superstite: Ruolo del superstite richiedente il risarcimento (figlio, genitore, coniuge, fratello, nipote, nonno)
        tabella: Tabella di riferimento: 'milano' o 'roma'
        personalizzazione_pct: Posizione nel range min-max (0=minimo, 50=mediano, 100=massimo)
    """
    tabella = tabella.lower()
    vittima = vittima.lower()
    superstite = superstite.lower()

    if tabella not in _PARENTALE:
        return {"errore": f"Tabella non valida. Valori ammessi: milano, roma"}

    if personalizzazione_pct < 0 or personalizzazione_pct > 100:
        return {"errore": "personalizzazione_pct deve essere tra 0 e 100"}

    rapporti = _PARENTALE[tabella]["rapporti"]
    match = None
    for r in rapporti:
        if r["vittima"] == vittima and r["superstite"] == superstite:
            match = r
            break

    if not match:
        coppie = [f"{r['vittima']}/{r['superstite']}" for r in rapporti]
        return {
            "errore": f"Rapporto vittima={vittima}/superstite={superstite} non trovato",
            "rapporti_disponibili": coppie,
        }

    importo_min = match["min"]
    importo_max = match["max"]
    importo = importo_min + (importo_max - importo_min) * (personalizzazione_pct / 100)

    return {
        "vittima": vittima,
        "superstite": superstite,
        "tabella": tabella,
        "importo_minimo": importo_min,
        "importo_massimo": importo_max,
        "personalizzazione_pct": personalizzazione_pct,
        "importo_liquidato": round(importo, 2),
        "riferimento": _PARENTALE[tabella]["_note"],
    }


@mcp.tool()
def menomazioni_plurime(
    percentuali: list[float],
) -> dict:
    """Calcola l'invalidità complessiva per menomazioni plurime con la formula Balthazard.
    Vigenza: formula medico-legale standard, recepita dalla prassi giurisprudenziale italiana.
    Precisione: ESATTO (formula matematica deterministica).

    Usa questo quando: il danneggiato presenta più menomazioni distinte da cumulare correttamente.
    NON usare per: una singola menomazione (non serve la formula di riduzione).

    Args:
        percentuali: Lista delle percentuali di invalidità per ciascuna menomazione in ordine decrescente,
                     es. [15, 10, 5]. Ogni valore deve essere compreso tra 0 e 100. Minimo 2 valori.
    """
    if not percentuali or len(percentuali) < 2:
        return {"errore": "Servono almeno 2 percentuali di invalidità"}

    for p in percentuali:
        if p < 0 or p > 100:
            return {"errore": f"Ogni percentuale deve essere tra 0 e 100 (trovato: {p})"}

    # Formula Balthazard: IT = 1 - prodotto(1 - pi/100)
    prodotto = 1.0
    passi = []
    for i, p in enumerate(percentuali):
        fattore = 1 - p / 100
        prodotto *= fattore
        passi.append({
            "menomazione": i + 1,
            "percentuale": p,
            "fattore_residuo": round(fattore, 4),
            "prodotto_parziale": round(prodotto, 6),
        })

    invalidita_complessiva = (1 - prodotto) * 100

    # Somma aritmetica per confronto
    somma_aritmetica = sum(percentuali)

    return {
        "percentuali_input": percentuali,
        "invalidita_complessiva_pct": round(invalidita_complessiva, 2),
        "somma_aritmetica_pct": round(somma_aritmetica, 2),
        "riduzione_pct": round(somma_aritmetica - invalidita_complessiva, 2),
        "formula": "IT = 1 - Π(1 - pi/100) × 100",
        "passi_calcolo": passi,
        "riferimento_normativo": "Formula Balthazard — riduzione proporzionale per invalidità concorrenti",
    }


@mcp.tool()
def risarcimento_inail(
    retribuzione_annua: float,
    percentuale_invalidita: float,
    tipo: str = "permanente",
) -> dict:
    """Calcola l'indennizzo INAIL per infortunio sul lavoro o malattia professionale.
    Vigenza: D.Lgs. 38/2000 art. 13 — D.P.R. 1124/1965 TU INAIL — tabelle INAIL vigenti.
    Precisione: INDICATIVO (i coefficienti per la forma capitale sono una semplificazione;
    il valore esatto richiede la tabella INAIL ufficiale per anno e grado di invalidità).

    Usa questo quando: lavoratore infortunato o con malattia professionale riconosciuta dall'INAIL.
    NON usare per: danno biologico civilistico da illecito di terzi → usa danno_biologico_micro/macro().

    Args:
        retribuzione_annua: Retribuzione annua lorda del lavoratore in euro (€)
        percentuale_invalidita: Percentuale di invalidità accertata dall'INAIL (0-100)
        tipo: Tipo di indennizzo: 'permanente' (in capitale se ≤15%, rendita se >15%)
              o 'temporanea' (indennità giornaliera per i giorni di assenza)
    """
    tipo = tipo.lower()
    if tipo not in ("permanente", "temporanea"):
        return {"errore": "tipo deve essere 'permanente' o 'temporanea'"}

    if percentuale_invalidita < 0 or percentuale_invalidita > 100:
        return {"errore": "percentuale_invalidita deve essere tra 0 e 100"}

    if tipo == "temporanea":
        retribuzione_giornaliera = retribuzione_annua / 365
        # Primi 3 giorni: a carico del datore (100%)
        # Dal 4° al 90° giorno: INAIL paga 60%
        # Dal 91° giorno in poi: INAIL paga 75%
        indennita_60 = retribuzione_giornaliera * 0.60
        indennita_75 = retribuzione_giornaliera * 0.75

        return {
            "tipo": "temporanea",
            "retribuzione_annua": retribuzione_annua,
            "retribuzione_giornaliera": round(retribuzione_giornaliera, 2),
            "primi_3_giorni": "A carico del datore di lavoro (100%)",
            "dal_4_al_90_giorno": {
                "percentuale": "60%",
                "indennita_giornaliera": round(indennita_60, 2),
            },
            "dal_91_giorno": {
                "percentuale": "75%",
                "indennita_giornaliera": round(indennita_75, 2),
            },
            "riferimento_normativo": "D.P.R. 1124/1965 — TU INAIL",
        }

    # Permanente
    if percentuale_invalidita < 6:
        return {
            "tipo": "permanente",
            "percentuale_invalidita": percentuale_invalidita,
            "esito": "Nessun indennizzo",
            "nota": "Invalidità inferiore al 6%: nessun indennizzo INAIL erogabile",
            "riferimento_normativo": "D.Lgs. 38/2000 art. 13",
        }

    if percentuale_invalidita <= 15:
        # Indennizzo in capitale (una tantum)
        # Coefficienti indicativi tabelle INAIL
        coefficiente_capitale = 7.0 * percentuale_invalidita  # semplificazione
        indennizzo = retribuzione_annua * (coefficiente_capitale / 100)

        return {
            "tipo": "permanente",
            "forma": "capitale",
            "percentuale_invalidita": percentuale_invalidita,
            "retribuzione_annua": retribuzione_annua,
            "coefficiente_pct": round(coefficiente_capitale, 2),
            "indennizzo_capitale": round(indennizzo, 2),
            "nota": "Invalidità 6-15%: indennizzo in capitale (una tantum). Importo indicativo basato su tabelle INAIL.",
            "riferimento_normativo": "D.Lgs. 38/2000 art. 13 — Tabella indennizzo danno biologico",
        }

    # > 16%: rendita
    quota_biologica = retribuzione_annua * (percentuale_invalidita / 100) * 0.40
    quota_patrimoniale = 0.0
    if percentuale_invalidita > 16:
        quota_patrimoniale = retribuzione_annua * ((percentuale_invalidita - 16) / 100) * 0.60
    rendita_annua = quota_biologica + quota_patrimoniale
    rendita_mensile = rendita_annua / 12

    return {
        "tipo": "permanente",
        "forma": "rendita",
        "percentuale_invalidita": percentuale_invalidita,
        "retribuzione_annua": retribuzione_annua,
        "quota_danno_biologico": round(quota_biologica, 2),
        "quota_danno_patrimoniale": round(quota_patrimoniale, 2),
        "rendita_annua": round(rendita_annua, 2),
        "rendita_mensile": round(rendita_mensile, 2),
        "nota": "Invalidità >16%: rendita diretta. Composta da quota biologica + quota patrimoniale.",
        "riferimento_normativo": "D.Lgs. 38/2000 art. 13 — Rendita per danno biologico e patrimoniale",
    }


@mcp.tool()
def danno_non_patrimoniale(
    percentuale_invalidita: int,
    eta_vittima: int,
    tipo_danno: str = "biologico",
    giorni_itt: int = 0,
    spese_mediche: float = 0,
    danno_morale_pct: float = 0,
    danno_esistenziale_pct: float = 0,
) -> dict:
    """Calcola il danno non patrimoniale complessivo con tutte le componenti in un unico prospetto.

    Combina automaticamente danno biologico (micro se ≤9%, macro se ≥10%), danno morale
    (personalizzazione), danno esistenziale e patrimoniale emergente (spese mediche + ITT).
    Vigenza: art. 138-139 Cod. Assicurazioni; Tabelle Milano 2024; Cass. SU 26972/2008.
    Precisione: INDICATIVO (il danno biologico macro è interpolato; la personalizzazione
    morale ed esistenziale è soggetta a valutazione giudiziale discrezionale).

    Usa questo quando: vuoi un prospetto completo di tutte le componenti del danno non patrimoniale.
    NON usare per: solo danno biologico micro → usa danno_biologico_micro() (più dettagliato).
    NON usare per: solo danno biologico macro → usa danno_biologico_macro().
    NON usare per: danno da perdita del rapporto parentale → usa danno_parentale().

    Args:
        percentuale_invalidita: Percentuale di invalidità permanente (1-100)
        eta_vittima: Età della vittima al momento del sinistro (0-120)
        tipo_danno: Voce principale richiesta: 'biologico', 'morale', 'esistenziale', 'patrimoniale_emergente'
        giorni_itt: Giorni di invalidità temporanea totale al 100%
        spese_mediche: Spese mediche documentate in euro (€)
        danno_morale_pct: Percentuale di personalizzazione per danno morale (0-50)
        danno_esistenziale_pct: Percentuale di personalizzazione per danno esistenziale (0-50)
    """
    if not 1 <= percentuale_invalidita <= 100:
        return {"errore": "Percentuale invalidità deve essere tra 1 e 100"}

    if danno_morale_pct < 0 or danno_morale_pct > 50:
        return {"errore": "danno_morale_pct deve essere tra 0 e 50"}

    if danno_esistenziale_pct < 0 or danno_esistenziale_pct > 50:
        return {"errore": "danno_esistenziale_pct deve essere tra 0 e 50"}

    # Calcolo componente biologica (micro o macro)
    if percentuale_invalidita <= 9:
        punto_base = _MICRO["punto_base"]
        coefficienti = _MICRO["coefficienti_punto"]
        eta_inizio_decremento = _MICRO["eta_decremento_da"]
        decremento_pct = _MICRO["decremento_eta_pct_per_anno"]

        if eta_vittima >= eta_inizio_decremento:
            anni_sopra = eta_vittima - eta_inizio_decremento
            riduzione = max(1 - (decremento_pct / 100) * anni_sopra, 0)
        else:
            riduzione = 1.0

        danno_biologico = 0.0
        for p in range(1, percentuale_invalidita + 1):
            danno_biologico += punto_base * coefficienti[str(p)] * riduzione

        tipo_calcolo = "micropermanenti (art. 139)"
    else:
        punto_base = _interpola_punto_base(percentuale_invalidita)
        coeff_eta = _coefficiente_eta(eta_vittima)
        danno_biologico = punto_base * percentuale_invalidita * coeff_eta
        tipo_calcolo = "macropermanenti (art. 138)"

    # ITT
    itt_giornaliero = _MICRO["invalidita_temporanea_totale_giornaliera"]
    danno_itt = giorni_itt * itt_giornaliero

    # Componente morale
    danno_morale = danno_biologico * (danno_morale_pct / 100)

    # Componente esistenziale
    danno_esistenziale = danno_biologico * (danno_esistenziale_pct / 100)

    # Patrimoniale emergente
    danno_patrimoniale = spese_mediche + danno_itt

    totale = danno_biologico + danno_morale + danno_esistenziale + danno_patrimoniale

    return {
        "percentuale_invalidita": percentuale_invalidita,
        "eta_vittima": eta_vittima,
        "tipo_calcolo": tipo_calcolo,
        "componenti": {
            "danno_biologico": round(danno_biologico, 2),
            "danno_morale": {
                "personalizzazione_pct": danno_morale_pct,
                "importo": round(danno_morale, 2),
            },
            "danno_esistenziale": {
                "personalizzazione_pct": danno_esistenziale_pct,
                "importo": round(danno_esistenziale, 2),
            },
            "danno_patrimoniale_emergente": {
                "spese_mediche": round(spese_mediche, 2),
                "itt": {"giorni": giorni_itt, "importo": round(danno_itt, 2)},
                "totale": round(danno_patrimoniale, 2),
            },
        },
        "totale_risarcimento": round(totale, 2),
        "riferimento_normativo": "Art. 138-139 Cod. Assicurazioni; Tabelle Milano 2024; Cass. SU 26972/2008",
    }


@mcp.tool()
def equo_indennizzo(
    categoria_tabella: str,
    percentuale_invalidita: float,
    stipendio_annuo: float,
) -> dict:
    """Calcola l'equo indennizzo per causa di servizio per dipendenti pubblici (istituto abrogato).

    ATTENZIONE: Istituto ABROGATO per eventi successivi al 06/12/2011
    (art. 6 DL 201/2011 conv. L. 214/2011 — Riforma Fornero). Il calcolo resta valido
    esclusivamente per pratiche relative a fatti anteriori a tale data.

    Vigenza: DPR 834/1981 Tabella A — applicabile solo a fatti anteriori al 06/12/2011.
    Precisione: INDICATIVO (coefficienti tabellari semplificati; il calcolo esatto
    dipende dalla specifica categoria e dalla delibera della CMO).

    Usa questo quando: dipendente pubblico con infermità da causa di servizio anteriore al 06/12/2011.
    NON usare per: eventi successivi al 06/12/2011 (istituto abrogato).
    NON usare per: lavoratori privati infortunati → usa risarcimento_inail().

    Args:
        categoria_tabella: Categoria dalla Tabella A DPR 834/1981 ('1' = 81-100%, '8' = 1-10%)
        percentuale_invalidita: Percentuale di invalidità accertata dalla CMO (0-100)
        stipendio_annuo: Ultimo stipendio annuo lordo in euro (€)
    """
    coefficienti = {
        "1": {"range": "81-100%", "coefficiente": 8.0, "pensione_privilegiata": True},
        "2": {"range": "61-80%", "coefficiente": 6.5, "pensione_privilegiata": True},
        "3": {"range": "51-60%", "coefficiente": 5.0, "pensione_privilegiata": True},
        "4": {"range": "41-50%", "coefficiente": 4.0, "pensione_privilegiata": True},
        "5": {"range": "31-40%", "coefficiente": 3.0, "pensione_privilegiata": True},
        "6": {"range": "21-30%", "coefficiente": 2.5, "pensione_privilegiata": False},
        "7": {"range": "11-20%", "coefficiente": 1.5, "pensione_privilegiata": False},
        "8": {"range": "1-10%", "coefficiente": 0.7, "pensione_privilegiata": False},
    }

    cat = str(categoria_tabella).strip()
    if cat not in coefficienti:
        return {"errore": f"Categoria non valida. Valori ammessi: 1-8 (trovato: {categoria_tabella})"}

    info = coefficienti[cat]
    base = stipendio_annuo * info["coefficiente"] * (percentuale_invalidita / 100)
    indennizzo = round(base, 2)

    result = {
        "categoria_tabella": cat,
        "range_invalidita": info["range"],
        "percentuale_invalidita": percentuale_invalidita,
        "stipendio_annuo": stipendio_annuo,
        "coefficiente": info["coefficiente"],
        "equo_indennizzo": indennizzo,
        "pensione_privilegiata": info["pensione_privilegiata"],
    }

    if info["pensione_privilegiata"]:
        result["nota_pensione"] = (
            "Categoria 1ª-5ª: diritto a pensione privilegiata se cessazione dal servizio per infermità"
        )

    result["attenzione"] = (
        "Istituto ABROGATO per eventi successivi al 06/12/2011 "
        "(art. 6 DL 201/2011 conv. L. 214/2011 — Riforma Fornero). "
        "Il calcolo è valido solo per pratiche relative a fatti anteriori a tale data."
    )
    result["riferimento_normativo"] = "DPR 461/2001; DPR 834/1981 — Tabella A. Abrogato per nuovi eventi da art. 6 DL 201/2011 (L. 214/2011)"
    return result
