"""Calcoli per risarcimento danni: danno biologico micropermanenti (art. 139 CdA) e macropermanenti
(art. 138 CdA), danno non patrimoniale con tutte le componenti, danno parentale (tabelle Milano/Roma),
menomazioni plurime (Balthazard), indennizzo INAIL, equo indennizzo causa di servizio."""

import json
from pathlib import Path

from src.server import mcp
from src.lib._regime import previgente
from src.lib._data import sourced

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


@mcp.tool(tags={"danni"})
@sourced("tabella_danno_bio")
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
    Vigenza: tabelle aggiornate al DM 20/07/2026 (importi dal mese di aprile 2026).
    Precisione: ESATTO (formula di legge applicata ai valori tabellari vigenti: il coefficiente
    del grado di invalidità accertato si applica a ciascun punto — art. 139 co. 2 lett. a) e co. 6 —
    e il risultato si riduce dello 0,5% per ogni anno di età a partire dall'undicesimo).

    Usa questo quando: sinistro stradale o sanitario con invalidità permanente tra 1% e 9%.
    NON usare per: invalidità ≥10% → usa danno_biologico_macro().
    NON usare per: danno non patrimoniale con tutte le componenti → usa danno_non_patrimoniale().
    Chaining: → danno_non_patrimoniale() → rivalutazione_monetaria() → interessi_legali()

    Args:
        percentuale_invalidita: Percentuale di invalidità permanente (1-9)
        eta_vittima: Età della vittima al momento del sinistro (0-120)
        giorni_itt: Giorni di invalidità temporanea totale al 100%
        giorni_itp75: Giorni di invalidità temporanea parziale al 75%
        giorni_itp50: Giorni di invalidità temporanea parziale al 50%
        giorni_itp25: Giorni di invalidità temporanea parziale al 25%
        personalizzazione_pct: Percentuale di personalizzazione per danno morale (0-20)
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

    # Art. 139 co. 2 lett. a) e co. 6 Cod. Ass.: il coefficiente moltiplicatore corrisponde al
    # grado di invalidità accertato e si applica a ciascun punto percentuale; il valore del
    # punto (base x coefficiente, ridotto per età) va quindi moltiplicato per i punti, come
    # nelle tabelle allegate ai decreti annuali. Sommare i valori dei gradi inferiori (1+1,1+...)
    # sottostimava il danno fino a un terzo al 9%.
    coeff = coefficienti[str(percentuale_invalidita)]
    valore_punto = punto_base * coeff * riduzione
    danno_permanente = valore_punto * percentuale_invalidita
    dettaglio_punti = [
        {
            "percentuale": percentuale_invalidita,
            "coefficiente": coeff,
            "valore_punto": round(valore_punto, 2),
            "punti": percentuale_invalidita,
            "formula": "valore punto (base x coefficiente x riduzione età) x punti",
        }
    ]

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
        "coefficiente_grado": coeff,
        "valore_punto": round(valore_punto, 2),
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
        "riferimento_normativo": "Art. 139 Cod. Assicurazioni (D.Lgs. 209/2005) — DM 20/07/2026",
    }


@mcp.tool(tags={"danni"})
@sourced("tabella_danno_bio")
def danno_biologico_macro(
    percentuale_invalidita: int,
    eta_vittima: int,
    personalizzazione_pct: float = 0,
) -> dict:
    """Calcola il danno biologico per MACROPERMANENTI (≥10% di invalidità).
    Applica art. 138 Codice delle Assicurazioni (D.Lgs. 209/2005).
    Vigenza: art. 138 Cod. Ass.; la tabella unica nazionale per le lesioni dal 10 al 100% è stata
    adottata con DPR 13 gennaio 2025 n. 12 (in vigore dal 2025) e NON è trascritta in questo
    server: i valori inclusi sono medie indicative non riconducibili alla TUN né alle tabelle di
    Milano, e per gradi elevati producono importi non attendibili.
    Precisione: STIMATO (ordine di grandezza; per la liquidazione usare la tabella unica nazionale
    DPR 12/2025 o le tabelle del tribunale competente, per età e grado). Il tetto di
    personalizzazione è il 30% (art. 138 co. 3).

    Usa questo quando: sinistro stradale o sanitario con invalidità permanente tra 10% e 100%.
    NON usare per: invalidità <10% → usa danno_biologico_micro().
    NON usare per: danno non patrimoniale con tutte le componenti → usa danno_non_patrimoniale().
    Chaining: → danno_non_patrimoniale() → rivalutazione_monetaria() → interessi_legali()

    Args:
        percentuale_invalidita: Percentuale di invalidità permanente (10-100)
        eta_vittima: Età della vittima al momento del sinistro (0-120)
        personalizzazione_pct: Percentuale di personalizzazione (0-30, art. 138 co. 3 Cod. Ass.)
    """
    if not 10 <= percentuale_invalidita <= 100:
        return {"errore": "Macropermanenti: percentuale deve essere tra 10 e 100"}

    if not 0 <= eta_vittima <= 120:
        return {"errore": "Età non valida"}

    if personalizzazione_pct < 0 or personalizzazione_pct > 30:
        return {"errore": "Personalizzazione macropermanenti deve essere tra 0 e 30% (art. 138 co. 3 Cod. Ass.)"}

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
        "avvertenza": (
            "STIMA di ordine di grandezza: i valori punto inclusi non sono la tabella unica "
            "nazionale (DPR 13/01/2025 n. 12) né una tabella di tribunale, e per gradi elevati "
            "risultano sovrastimati. Per la liquidazione usare la TUN o la tabella del tribunale "
            "competente per età e grado."
        ),
        "riferimento_normativo": "Art. 138 Cod. Assicurazioni (D.Lgs. 209/2005) — tabella unica nazionale DPR 12/2025 (da trascrivere)",
    }


@mcp.tool(tags={"danni"})
@sourced("tabella_milano_roma")
def danno_parentale(
    vittima: str,
    superstite: str,
    tabella: str = "milano",
    personalizzazione_pct: float = 50,
) -> dict:
    """Calcola il danno da perdita del rapporto parentale (danno morale da morte del congiunto).
    Vigenza: Tabelle di Milano, edizione 2024 (Osservatorio, valori all'1.1.2024, rivalutazione
    1,162268): il massimo del range coincide con il "cap" della tabella integrata a punti
    (391.103,18 genitori/figli/coniuge; 169.830,60 fratelli/nonni/nipoti). Il minimo è il
    pavimento della vecchia forbice, NON un limite della liquidazione: la tabella a punti parte
    da 0 (valore punto 3.911,00 / 1.698,00) e tiene conto di età, convivenza, altri familiari e
    intensità della relazione, dati che questo tool non riceve. Roma: NON esiste un'edizione 2024
    ufficiale; i valori inclusi sono una stima scalata da Milano, non i criteri del Tribunale di Roma.
    Precisione: INDICATIVO (range minimo-massimo derivati dalle edizioni precedenti delle tabelle;
        dal 2022 la tabella di Milano liquida il danno da perdita del rapporto parentale a punti, in
        linea con Cass. 10579/2021, e i valori di Roma inclusi sono una stima)

    Usa questo quando: richiesta risarcimento per morte del congiunto in sinistro o illecito.
    NON usare per: danno biologico del superstite (es. disturbo dell'adattamento) → usa danno_biologico_micro/macro().
    Chaining: → rivalutazione_monetaria() per attualizzare l'importo

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

    if tabella == "milano":
        avvertenza = (
            "Milano 2024: il minimo e il massimo sono la vecchia forbice rivalutata; il massimo coincide "
            "con il cap della tabella a punti, il minimo non e' un pavimento (la tabella a punti parte da "
            "0 e dipende da eta' di vittima e superstite, convivenza, altri familiari, intensita' della "
            "relazione). L'importo liquidato qui e' solo una posizione nel range, non il risultato della tabella."
        )
    else:
        avvertenza = (
            "Roma: stima scalata da Milano, non esiste un'edizione 2024 ufficiale dei criteri del Tribunale "
            "di Roma (sistema a punti con valore punto e aumenti diversi, es. +1/3 fino a 1/2 senza altri "
            "familiari): il range puo' non coprire la liquidazione effettiva."
        )

    return {
        "vittima": vittima,
        "superstite": superstite,
        "tabella": tabella,
        "avvertenza": avvertenza,
        "importo_minimo": importo_min,
        "importo_massimo": importo_max,
        "personalizzazione_pct": personalizzazione_pct,
        "importo_liquidato": round(importo, 2),
        "riferimento": _PARENTALE[tabella]["_note"],
    }


@mcp.tool(tags={"danni"})
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


@mcp.tool(tags={"danni"})
def risarcimento_inail(
    retribuzione_annua: float,
    percentuale_invalidita: float,
    tipo: str = "permanente",
) -> dict:
    """Calcola l'indennizzo INAIL per infortunio sul lavoro o malattia professionale.
    Vigenza: D.Lgs. 38/2000 art. 13 (quota patrimoniale: retribuzione x coefficiente della Tabella dei
    coefficienti, D.M. 12/07/2000 x grado); D.P.R. 1124/1965 artt. 68 e 73 (inabilità temporanea).
    Verificato il 29/09/2026.
    Precisione: STIMATO (la quota di danno biologico, in capitale 6-15% e in rendita dal 16%, NON è letta
    dalla "Tabella indennizzo danno biologico" per grado ed età rivalutata da INAIL ma è una
    semplificazione lineare sulla retribuzione: gli importi divergono in modo rilevante, fino a
    qualche migliaio di euro; la retribuzione non è riportata a minimale e massimale dell'art. 116
    D.P.R. 1124/1965; il valore esatto richiede le tabelle INAIL in vigore, aggiornate ogni 1 luglio).
    La quota patrimoniale della rendita e l'indennità temporanea seguono invece la norma.

    Usa questo quando: lavoratore infortunato o con malattia professionale riconosciuta dall'INAIL,
    per un ordine di grandezza (non per una quantificazione da produrre in giudizio).
    NON usare per: danno biologico civilistico da illecito di terzi → usa danno_biologico_micro/macro().

    Args:
        retribuzione_annua: Retribuzione annua lorda del lavoratore in euro (€)
        percentuale_invalidita: Percentuale di invalidità accertata dall'INAIL (0-100)
        tipo: Tipo di indennizzo: 'permanente' (in capitale se <16%, rendita dal 16%)
              o 'temporanea' (indennità giornaliera per i giorni di assenza)
    """
    tipo = tipo.lower()
    if tipo not in ("permanente", "temporanea"):
        return {"errore": "tipo deve essere 'permanente' o 'temporanea'"}

    if percentuale_invalidita < 0 or percentuale_invalidita > 100:
        return {"errore": "percentuale_invalidita deve essere tra 0 e 100"}

    if retribuzione_annua < 0:
        return {"errore": "retribuzione_annua non puo essere negativa"}

    if tipo == "temporanea":
        retribuzione_giornaliera = retribuzione_annua / 365
        # Giorno dell'infortunio: intera retribuzione a carico del datore (art. 73 co. 1 DPR 1124/1965)
        # Tre giorni successivi (carenza): 60% a carico del datore, salvo migliori condizioni (art. 73)
        # Dal 4° giorno successivo al 90° giorno: INAIL paga 60% (art. 68 co. 1)
        # Dal 91° giorno in poi: INAIL paga 75% (art. 68 co. 2)
        indennita_60 = retribuzione_giornaliera * 0.60
        indennita_75 = retribuzione_giornaliera * 0.75

        return {
            "tipo": "temporanea",
            "retribuzione_annua": retribuzione_annua,
            "retribuzione_giornaliera": round(retribuzione_giornaliera, 2),
            "giorno_infortunio": "A carico del datore di lavoro (intera retribuzione, art. 73 DPR 1124/1965)",
            "primi_3_giorni": "Carenza a carico del datore di lavoro: 60% della retribuzione, salvo migliori condizioni (art. 73 DPR 1124/1965)",
            "dal_4_al_90_giorno": {
                "percentuale": "60%",
                "indennita_giornaliera": round(indennita_60, 2),
            },
            "dal_91_giorno": {
                "percentuale": "75%",
                "indennita_giornaliera": round(indennita_75, 2),
            },
            "riferimento_normativo": "D.P.R. 1124/1965 artt. 68 e 73 — TU INAIL",
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

    if percentuale_invalidita < 16:
        # Indennizzo in capitale (art. 13 co. 2 lett. a D.Lgs. 38/2000: da 6% a meno di 16%) (una tantum)
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
            "nota": (
                "Invalidità 6-15%: indennizzo in capitale (una tantum). Importo STIMATO con formula "
                "semplificata sulla retribuzione: l'INAIL lo liquida dalla tabella per grado ed età."
            ),
            "riferimento_normativo": "D.Lgs. 38/2000 art. 13 — Tabella indennizzo danno biologico",
        }

    # Da 16%: rendita = quota danno biologico + quota patrimoniale (art. 13 co. 2 lett. a e b D.Lgs. 38/2000)
    # Quota biologica: semplificazione (l'INAIL usa la tabella per grado, indipendente dalla retribuzione).
    quota_biologica = retribuzione_annua * (percentuale_invalidita / 100) * 0.40
    # Quota patrimoniale: retribuzione x coefficiente della Tabella dei coefficienti (D.M. 12/07/2000)
    # x grado percentuale (art. 13 co. 2 lett. b). Coefficiente per fascia di grado.
    grado = int(percentuale_invalidita)
    coefficiente = 1.0
    for limite, valore in ((20, 0.4), (25, 0.5), (35, 0.6), (50, 0.7), (70, 0.8), (85, 0.9)):
        if grado <= limite:
            coefficiente = valore
            break
    quota_patrimoniale = retribuzione_annua * coefficiente * (percentuale_invalidita / 100)
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
        "coefficiente_patrimoniale": coefficiente,
        "nota": (
            "Invalidità dal 16%: rendita diretta = quota biologica + quota patrimoniale. La quota "
            "patrimoniale segue l'art. 13 co. 2 lett. b (retribuzione x coefficiente x grado, senza "
            "minimale e massimale); la quota biologica è STIMATA con formula semplificata."
        ),
        "riferimento_normativo": "D.Lgs. 38/2000 art. 13 — Rendita per danno biologico e patrimoniale",
    }


@mcp.tool(tags={"danni"})
@sourced("tabella_danno_bio")
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
    (personalizzazione), danno esistenziale e patrimoniale emergente (spese mediche); l'ITT è
    esposta come danno biologico temporaneo (art. 139 co. 1 lett. b).
    Vigenza: art. 138-139 Cod. Assicurazioni (D.Lgs. 209/2005); per le micropermanenti importi del
    DM 20/07/2026 (art. 139 co. 1 e 6); per le macropermanenti valori NON riconducibili alla
    tabella unica nazionale DPR 12/2025 né a Milano (vedi danno_biologico_macro). L'ITT è liquidata
    a 57,64 euro/giorno anche sopra il 9% (DPR 12/2025 art. 3 co. 1 rinvia all'art. 139 co. 1 lett. b).
    Precisione: STIMATO (micropermanenti: valori di legge, ma la componente macro è solo un ordine di
    grandezza; la personalizzazione è soggetta a valutazione giudiziale discrezionale e per le
    micropermanenti non può superare il 20% complessivo, art. 139 co. 3)

    Usa questo quando: vuoi un prospetto completo di tutte le componenti del danno non patrimoniale.
    NON usare per: solo danno biologico micro → usa danno_biologico_micro() (più dettagliato).
    NON usare per: solo danno biologico macro → usa danno_biologico_macro().
    NON usare per: danno da perdita del rapporto parentale → usa danno_parentale().
    Chaining: → rivalutazione_monetaria() per attualizzare → interessi_legali() per gli interessi compensativi

    Args:
        percentuale_invalidita: Percentuale di invalidità permanente (1-100)
        eta_vittima: Età della vittima al momento del sinistro (0-120)
        tipo_danno: Voce principale richiesta: 'biologico', 'morale', 'esistenziale', 'patrimoniale_emergente'
        giorni_itt: Giorni di invalidità temporanea totale al 100%
        spese_mediche: Spese mediche documentate in euro (€)
        danno_morale_pct: Percentuale di personalizzazione per danno morale (0-50; micro: morale + esistenziale ≤ 20)
        danno_esistenziale_pct: Percentuale di personalizzazione per danno esistenziale (0-50; micro: morale + esistenziale ≤ 20)
    """
    if not 1 <= percentuale_invalidita <= 100:
        return {"errore": "Percentuale invalidità deve essere tra 1 e 100"}

    if danno_morale_pct < 0 or danno_morale_pct > 50:
        return {"errore": "danno_morale_pct deve essere tra 0 e 50"}

    if danno_esistenziale_pct < 0 or danno_esistenziale_pct > 50:
        return {"errore": "danno_esistenziale_pct deve essere tra 0 e 50"}

    if giorni_itt < 0:
        return {"errore": "giorni_itt non puo essere negativo"}

    # Art. 139 co. 3 Cod. Ass.: per le lesioni fino al 9% l'aumento per le condizioni soggettive
    # (morale e dinamico-relazionale) e' "fino al 20 per cento" e l'importo complessivo e'
    # esaustivo del danno non patrimoniale: le due percentuali non possono cumularsi oltre il 20.
    if percentuale_invalidita <= 9 and danno_morale_pct + danno_esistenziale_pct > _MICRO["maggiorazione_morale_max_pct"]:
        return {
            "errore": (
                f"Micropermanenti: danno morale + esistenziale non possono superare "
                f"{_MICRO['maggiorazione_morale_max_pct']:g}% (art. 139 co. 3 Cod. Ass.)"
            )
        }

    if spese_mediche < 0:
        return {"errore": "spese_mediche non puo essere negativo"}

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

        # Art. 139 co. 1 lett. a) e co. 6: il coefficiente del grado accertato si applica a ciascun
        # punto percentuale (valore punto = base x coeff x riduzione eta', poi x punti), non alla
        # somma dei valori dei gradi inferiori.
        danno_biologico = punto_base * coefficienti[str(percentuale_invalidita)] * riduzione * percentuale_invalidita

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

    # Patrimoniale emergente: solo le spese; l'ITT e' danno biologico temporaneo (art. 139 co. 1
    # lett. b; per le macro DPR 12/2025 art. 3 co. 1), non danno patrimoniale.
    danno_patrimoniale = spese_mediche

    totale = danno_biologico + danno_itt + danno_morale + danno_esistenziale + danno_patrimoniale

    return {
        "percentuale_invalidita": percentuale_invalidita,
        "eta_vittima": eta_vittima,
        "voce_principale_richiesta": tipo_danno,
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
            "danno_biologico_temporaneo": {
                "itt": {"giorni": giorni_itt, "importo": round(danno_itt, 2)},
                "totale": round(danno_itt, 2),
            },
            "danno_patrimoniale_emergente": {
                "spese_mediche": round(spese_mediche, 2),
                "totale": round(danno_patrimoniale, 2),
            },
        },
        "totale_risarcimento": round(totale, 2),
        "riferimento_normativo": "Art. 138-139 Cod. Assicurazioni (D.Lgs. 209/2005); DPR 12/2025 art. 3; DM 20/07/2026 (micropermanenti)",
    }


@mcp.tool(tags={"danni", "previgente"})
@previgente
def equo_indennizzo(
    categoria_tabella: str,
    percentuale_invalidita: float,
    stipendio_annuo: float,
    eta_evento: int | None = None,
    pensione_privilegiata: bool = False,
) -> dict:
    """Calcola l'equo indennizzo per causa di servizio per dipendenti pubblici (istituto abrogato).
    Regime: PREVIGENTE — infermità da causa di servizio di dipendenti pubblici per fatti anteriori
    al 06/12/2011 (istituto abrogato dall'art. 6 DL 201/2011 conv. L. 214/2011; nessun tool
    vigente equivalente: per gli infortuni dei lavoratori privati → risarcimento_inail)

    ATTENZIONE: Istituto ABROGATO per eventi successivi al 06/12/2011
    (art. 6 DL 201/2011 conv. L. 214/2011 — Riforma Fornero). Il calcolo resta valido
    per pratiche relative a fatti anteriori a tale data. L'abrogazione NON si applica al personale
    del comparto sicurezza, difesa, vigili del fuoco e soccorso pubblico (art. 6 co. 1, secondo
    periodo): per quel personale l'istituto è tuttora vigente e il calcolo è applicabile.

    Vigenza: art. 1 co. 119 L. 662/1996 (Tabella 1: 2 x stipendio tabellare x percentuale della
    categoria), art. 1 co. 210-211 L. 266/2005 (stipendio tabellare in godimento alla domanda, per
    domande dal 01/01/2006), art. 49 DPR 686/1957 (riduzione per età all'evento), art. 50 DPR 686/1957
    (riduzione alla metà con pensione privilegiata). Verificato il 29/09/2026.
    Precisione: INDICATIVO (le percentuali della Tabella 1 sono lette dall'allegato alla L. 662/1996;
    la categoria di menomazione è assegnata dalla CMO e non è calcolata; per le domande anteriori al
    01/01/2006 lo stipendio da usare è quello tabellare iniziale; non si detrae quanto già percepito
    per assicurazione a carico dello Stato, art. 50 co. 2 DPR 686/1957).

    Usa questo quando: dipendente pubblico con infermità da causa di servizio anteriore al 06/12/2011,
    o appartenente al comparto sicurezza, difesa, vigili del fuoco e soccorso pubblico.
    NON usare per: altro personale con eventi successivi al 06/12/2011 (istituto abrogato).
    NON usare per: lavoratori privati infortunati → usa risarcimento_inail().

    Args:
        categoria_tabella: Categoria di menomazione da '1' a '8' (Tabella A DPR 834/1981) oppure '9'
                           (o 'B', 'una_tantum') per l'indennità una tantum della Tabella B, pari al 3%
        percentuale_invalidita: Percentuale di invalidità accertata dalla CMO (0-100). Non entra nel
                           calcolo: l'importo dipende solo dalla categoria
        stipendio_annuo: Stipendio annuo TABELLARE in euro (€), senza altre voci retributive
        eta_evento: Età dell'interessato al momento dell'evento dannoso (art. 49 co. 3 DPR 686/1957).
                    Oltre 50 anni l'indennizzo è ridotto del 25%, oltre 60 del 50%. Se omessa,
                    nessuna riduzione
        pensione_privilegiata: True se l'interessato consegue anche la pensione privilegiata:
                    l'indennizzo è ridotto della metà (art. 50 co. 1 DPR 686/1957)
    """
    # Tabella 1 allegata alla L. 662/1996: percentuale dell'importo di 1ª categoria (2 x stipendio)
    percentuali = {
        "1": 100, "2": 92, "3": 75, "4": 61, "5": 44, "6": 27, "7": 12, "8": 6,
        "9": 3,  # indennità una tantum (Tabella B): 3% dell'importo di 1ª categoria
    }

    cat = str(categoria_tabella).strip().lower()
    if cat in ("b", "una_tantum", "una tantum"):
        cat = "9"
    if cat not in percentuali:
        return {"errore": f"Categoria non valida. Valori ammessi: 1-8, 9 (una tantum) (trovato: {categoria_tabella})"}

    if percentuale_invalidita < 0 or percentuale_invalidita > 100:
        return {"errore": "percentuale_invalidita deve essere tra 0 e 100"}

    if stipendio_annuo < 0:
        return {"errore": "stipendio_annuo non puo essere negativo"}

    if eta_evento is not None and (eta_evento < 0 or eta_evento > 120):
        return {"errore": "eta_evento deve essere tra 0 e 120"}

    pct = percentuali[cat]
    base = 2 * stipendio_annuo * pct / 100

    # art. 49 co. 2 DPR 686/1957: -25% se ha superato i 50 anni, -50% se ha superato i 60
    riduzione_eta = 0
    if eta_evento is not None:
        if eta_evento > 60:
            riduzione_eta = 50
        elif eta_evento > 50:
            riduzione_eta = 25
    importo = base * (100 - riduzione_eta) / 100

    # art. 50 co. 1 DPR 686/1957: ridotto della metà se consegue anche la pensione privilegiata
    if pensione_privilegiata:
        importo = importo / 2

    indennizzo = round(importo, 2)

    result = {
        "categoria_tabella": cat,
        "percentuale_categoria": pct,
        "percentuale_invalidita": percentuale_invalidita,
        "stipendio_annuo": stipendio_annuo,
        "importo_prima_categoria": round(2 * stipendio_annuo, 2),
        "riduzione_eta_pct": riduzione_eta,
        "pensione_privilegiata": pensione_privilegiata,
        "equo_indennizzo": indennizzo,
    }
    if cat == "9":
        result["nota_categoria"] = "Indennità una tantum (Tabella B): 3% dell'importo di 1ª categoria"
    if eta_evento is None:
        result["nota_eta"] = (
            "eta_evento non indicata: nessuna riduzione per età applicata "
            "(art. 49 DPR 686/1957: -25% oltre 50 anni, -50% oltre 60)"
        )

    result["attenzione"] = (
        "Istituto ABROGATO per eventi successivi al 06/12/2011 "
        "(art. 6 DL 201/2011 conv. L. 214/2011 — Riforma Fornero), salvo il personale del comparto "
        "sicurezza, difesa, vigili del fuoco e soccorso pubblico. "
        "Il calcolo è valido per pratiche relative a fatti anteriori a tale data o per tale personale."
    )
    result["riferimento_normativo"] = (
        "L. 662/1996 art. 1 co. 119 (Tabella 1); L. 266/2005 art. 1 co. 210-211; "
        "DPR 686/1957 artt. 49-50; DPR 834/1981 (Tabelle A e B). "
        "Abrogato per nuovi eventi da art. 6 DL 201/2011 (L. 214/2011)"
    )
    return result
