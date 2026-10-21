"""Calcoli di diritto del lavoro: indennità licenziamento (D.Lgs. 23/2015 tutele crescenti),
preavviso per CCNL, NASpI (D.Lgs. 22/2015), scadenze impugnazione licenziamento,
costo del lavoro, offerta conciliativa."""

import json
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

from src.lib import _clock, _data
from src.server import mcp
from src.lib._data import sourced

_DATA = Path(__file__).parent.parent / "data"

with open(_DATA / "preavviso_ccnl.json", encoding="utf-8") as _f:
    _PREAVVISO: dict = json.load(_f)

with open(_DATA / "irpef_scaglioni.json", encoding="utf-8") as _f:
    _IRPEF: dict = json.load(_f)


#: The Quadri row is 'quadri_1' in the commercio table and 'quadri' in the studi professionali one.
_ALIAS_LIVELLO = {"quadri_1": "quadri", "quadri": "quadri_1"}


def _it(valore: float) -> str:
    """Italian number format: 122295.0 -> '122.295,00'."""
    return f"{valore:,.2f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _add_days(d: date, giorni: int) -> date:
    return d + timedelta(days=giorni)


def _dec(valore) -> Decimal:
    """A float as the decimal the caller typed (`Decimal(str(x))`, not the binary expansion)."""
    return Decimal(str(valore))


def _cent(valore: Decimal) -> Decimal:
    """Round half up to the cent, as a payroll does (Python's `round()` is binary)."""
    return valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quattro_decimali(rapporto: Decimal) -> Decimal:
    """Art. 13 co. 6 TUIR: a positive ratio 'si assume nelle prime quattro cifre decimali'."""
    return rapporto.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


def _parametri_inps() -> tuple[int, dict]:
    """INPS yearly parameters of the running year (the latest year listed when it is missing).

    Read through `_data.load` so the call is observed by the table ledger. When the running
    year is not in the table the latest one is used and the expired vintage tells the caller
    (and, for a figure about today, the precision policy refuses): a stale value is never
    applied without a signal.
    """
    anni = _data.load("inps_parametri")["anni"]
    anno = str(_clock.today().year)
    chiave = anno if anno in anni else max(anni, key=int)
    return int(chiave), anni[chiave]


def _calcola_irpef_semplificata(imponibile: float) -> float:
    """Stima IRPEF lorda su imponibile annuo usando scaglioni vigenti (art. 11 TUIR)."""
    scaglioni = _IRPEF.get("scaglioni_per_anno", {}).get(str(_clock.today().year), _IRPEF["scaglioni"])
    imposta = Decimal(0)
    residuo = _dec(imponibile)
    prev_limit = Decimal(0)
    for s in scaglioni:
        aliquota = _dec(s["aliquota"]) / 100
        limite = _dec(s["fino_a"]) if "fino_a" in s else None
        base = residuo if limite is None else min(residuo, limite - prev_limit)
        if base <= 0:
            break
        imposta += base * aliquota
        residuo -= base
        if limite is None:
            break
        prev_limit = limite
    return float(_cent(imposta))


@mcp.tool(tags={"lavoro"})
def indennita_licenziamento(
    anni_servizio: float,
    retribuzione_mensile: float,
    dimensione_azienda: str = "grande",
    tipo: str = "indennitario",
) -> dict:
    """Calcola l'indennità di licenziamento per tutele crescenti (D.Lgs. 23/2015).

    Indennità dell'art. 3 co. 1 nella forma post C.Cost. 194/2018 (caduto il moltiplicatore
    fisso di due mensilità per anno: resta l'intervallo 6-36, o 3-18 per i datori sotto la
    soglia dell'art. 18 St. lav. dopo C.Cost. 118/2025, che ha eliminato il tetto di sei
    mensilità dell'art. 9 co. 1). Con tipo='reintegra' restituisce il tetto di 12 mensilità
    dell'indennità risarcitoria dell'art. 3 co. 2 (esteso da C.Cost. 128/2024 al licenziamento
    per giustificato motivo oggettivo con fatto materiale insussistente), che non dipende
    dall'anzianità: il valore effettivo è il periodo tra licenziamento e reintegra, dedotto
    l'aliunde percepito o percepibile, più i contributi senza sanzioni.
    Vigenza: D.Lgs. 23/2015 artt. 3, 9 nel testo vigente al 2026-09-29 — C.Cost. 194/2018, 128/2024, 118/2025.
    Precisione: INDICATIVO (il giudice può discostarsi nei limiti floor/cap in base a criteri art. 8 L. 604/1966).
    Chaining: → offerta_conciliativa() per la formula agevolata art. 6 D.Lgs. 23/2015.

    Args:
        anni_servizio: Anni di servizio maturati (es. 3.5; valore > 0)
        retribuzione_mensile: Ultima retribuzione di riferimento per il calcolo del TFR, mensile, in euro (es. 2000.00; valore > 0)
        dimensione_azienda: 'grande' (>15 dipendenti) o 'piccola' (≤15 dipendenti)
        tipo: 'indennitario' (art. 3 co. 1) o 'reintegra' (art. 3 co. 2: calcola il tetto dell'indennità risarcitoria; solo con dimensione_azienda='grande', l'art. 9 co. 1 esclude la reintegra sotto soglia)
    """
    if anni_servizio <= 0:
        raise ValueError("anni_servizio deve essere > 0")
    if retribuzione_mensile <= 0:
        raise ValueError("retribuzione_mensile deve essere > 0")
    if dimensione_azienda not in ("grande", "piccola"):
        raise ValueError("dimensione_azienda deve essere 'grande' o 'piccola'")
    if tipo not in ("indennitario", "reintegra"):
        raise ValueError("tipo deve essere 'indennitario' o 'reintegra'")
    if tipo == "reintegra" and dimensione_azienda == "piccola":
        raise ValueError(
            "art. 9 co. 1 D.Lgs. 23/2015: sotto i requisiti dimensionali dell'art. 18 St. lav. "
            "'non si applica l'articolo 3, comma 2': la reintegra non spetta. Usa tipo='indennitario' "
            "(indennità dimezzata, da 3 a 18 mensilità)"
        )

    if tipo == "reintegra":
        # Art. 3 co. 2: the damages run from the dismissal to the actual reinstatement (less
        # the aliunde perceptum et percipiendum), and for the period before the ruling they
        # cannot exceed twelve mensilita. Nothing ties them to seniority, so the only figure
        # the inputs support is the ceiling.
        mensilita = 12
        floor_val = 0
        cap_val = 12
        formula = (
            "tetto di 12 mensilità (art. 3 co. 2 D.Lgs. 23/2015), indipendente dall'anzianità: "
            "l'importo effettivo è il periodo dal licenziamento all'effettiva reintegra, dedotto l'aliunde "
            "percepito o percepibile, entro 12 mensilità per il periodo anteriore alla pronuncia"
        )
        nota = (
            "La reintegra è disposta dal giudice solo per il licenziamento per giustificato motivo soggettivo o "
            "giusta causa con fatto materiale insussistente (art. 3 co. 2) e, dopo C.Cost. 128/2024, per il "
            "giustificato motivo oggettivo con fatto materiale insussistente. 'importo' è il tetto massimo "
            "dell'indennità risarcitoria; si aggiungono i contributi previdenziali e assistenziali dal "
            "licenziamento alla reintegra, senza sanzioni. Il lavoratore può chiedere in luogo della reintegra "
            "l'indennità sostitutiva di 15 mensilità (art. 3 co. 2, che richiama l'art. 2 co. 3)"
        )
    elif dimensione_azienda == "grande":
        mensilita_raw = anni_servizio * 2
        floor_val = 6
        cap_val = 36
        mensilita = max(floor_val, min(mensilita_raw, cap_val))
        formula = f"anni_servizio ({anni_servizio}) × 2 = {round(mensilita_raw, 2)} → clamp [{floor_val}, {cap_val}]"
        nota = "Azienda con >15 dipendenti: regime ordinario D.Lgs. 23/2015 art. 3"
    else:
        mensilita_raw = anni_servizio * 1
        floor_val = 3
        cap_val = 18
        mensilita = max(floor_val, min(mensilita_raw, cap_val))
        formula = f"anni_servizio ({anni_servizio}) × 1 = {round(mensilita_raw, 2)} → clamp [{floor_val}, {cap_val}]"
        nota = "Azienda con ≤15 dipendenti: regime ridotto post C.Cost. 118/2025"

    importo = round(mensilita * retribuzione_mensile, 2)

    return {
        "anni_servizio": anni_servizio,
        "retribuzione_mensile": retribuzione_mensile,
        "tipo": tipo,
        "dimensione_azienda": dimensione_azienda,
        "mensilita": round(mensilita, 2),
        "importo": importo,
        "minimo_mensilita": floor_val,
        "massimo_mensilita": cap_val,
        "dettaglio_formula": formula,
        "nota": nota,
        "riferimento_normativo": "D.Lgs. 23/2015 artt. 3, 9 — C.Cost. 194/2018, 128/2024, 118/2025",
    }


@mcp.tool(tags={"lavoro"})
@sourced("preavviso_ccnl", alternativa="giorni_preavviso")
def indennita_preavviso(
    ccnl: str,
    livello: str,
    anzianita_anni: float,
    retribuzione_mensile: float,
    tipo: str = "licenziamento",
    giorni_preavviso: float | None = None,
) -> dict:
    """Calcola l'indennità sostitutiva del preavviso per CCNL principali.

    Supported CCNL: 'commercio', 'metalmeccanici', 'studi_professionali'.
    Il preavviso è dovuto in caso di recesso senza giusta causa; in mancanza si corrisponde
    l'indennità sostitutiva pari alla retribuzione del periodo (art. 2118 co. 2 c.c.), calcolata
    senza arrotondamenti intermedi come retribuzione mensile x giorni / 30. Per i metalmeccanici
    l'importo segue la tabella dell'indennità in mensilità del CCNL (per i livelli D1, D2 e C1 lo
    stesso contratto scrive 0,33 e 0,67 mensilità al posto di 10/30 e 20/30).
    Vigenza: artt. 2118-2119 e 2121 c.c.; TU CCNL Terziario 3/2/2026 artt. 251-252 e 256; CCNL industria
    metalmeccanica 5/2/2021 Sez. IV Tit. VIII art. 1; CCNL studi professionali 16/2/2024 artt. 146-147
    (testi depositati al CNEL, letti il 2026-09-25).
    Precisione: ESATTO per i periodi tabellari del CCNL indicato; verificare il CCNL aziendale applicato.

    Args:
        ccnl: Codice CCNL: 'commercio', 'metalmeccanici', 'studi_professionali'
        livello: Livello contrattuale (es. '2_3', 'quadri_1', 'A1_B2_B3', '3S_3'; per gli studi professionali 'quadri' vale come il livello '1')
        anzianita_anni: Anni di anzianità aziendale (es. 7.0; valore >= 0)
        retribuzione_mensile: Retribuzione mensile lorda in euro (es. 2000.00; valore > 0), comprensiva dei ratei di 13a e 14a mensilità e di ogni compenso continuativo (art. 2121 c.c.; art. 252 TU Terziario; art. 147 CCNL studi professionali)
        tipo: Tipo di recesso: 'licenziamento' o 'dimissioni'
        giorni_preavviso: Giorni di preavviso che il CCNL applicabile prevede, se li conosci: al posto
                          della tabella inclusa, che i contratti rinnovano. Il calcolo dell'indennità
                          non dipende allora dalla tabella
    """
    if retribuzione_mensile <= 0:
        raise ValueError("retribuzione_mensile deve essere > 0")
    if anzianita_anni < 0:
        raise ValueError("anzianita_anni deve essere >= 0")
    if tipo not in ("licenziamento", "dimissioni"):
        raise ValueError("tipo deve essere 'licenziamento' o 'dimissioni'")

    if anzianita_anni <= 5:
        fascia = "fino_5"
    elif anzianita_anni <= 10:
        fascia = "5_10"
    else:
        fascia = "oltre_10"

    # The notice period is what the CCNL table provides, and it is the part that
    # goes stale: a caller who has the applicable contract in hand can supply it
    # and the calculation no longer rests on the bundled table at all (which is
    # why it is then never read, and its vintage never enters the answer).
    dal_chiamante = giorni_preavviso is not None
    mensilita_ccnl = None
    if dal_chiamante:
        ccnl_data = {"nome": ccnl, "fonte": "giorni di preavviso forniti dal chiamante"}
    else:
        ccnl_data = _PREAVVISO["ccnl"].get(ccnl)
        if ccnl_data is None:
            ccnl_disponibili = list(_PREAVVISO["ccnl"].keys())
            raise ValueError(f"CCNL '{ccnl}' non trovato. Disponibili: {ccnl_disponibili}")

        tabella_tipo = ccnl_data[tipo]
        # 'quadri_1' (the commercio key) and 'quadri' (studi professionali) name the same row.
        livello = next(
            (k for k in (livello, _ALIAS_LIVELLO.get(livello)) if k in tabella_tipo), livello
        )
        livello_data = tabella_tipo.get(livello)
        if livello_data is None:
            livelli_disponibili = list(tabella_tipo.keys())
            raise ValueError(f"Livello '{livello}' non trovato nel CCNL '{ccnl}' per '{tipo}'. Disponibili: {livelli_disponibili}")
        giorni_preavviso = livello_data[fascia]
        # Some CCNL fix the indemnity in mensilita' with a table of their own (metalmeccanici,
        # art. 1 second table): that is the amount the contract states, not the term converted.
        mensilita_ccnl = ccnl_data.get("indennita_mensilita", {}).get(livello, {}).get(fascia)

    if giorni_preavviso < 0:
        raise ValueError("giorni_preavviso deve essere >= 0")
    retribuzione_giornaliera = round(retribuzione_mensile / 30, 4)  # shown, never multiplied
    if mensilita_ccnl is not None:
        importo = float(_cent(_dec(mensilita_ccnl) * _dec(retribuzione_mensile)))
        base_importo = f"{mensilita_ccnl} mensilità della retribuzione (tabella dell'indennità del CCNL)"
    else:
        # Art. 2118 co. 2 c.c.: the pay of the period, one month being 30 days; no rounding
        # of the daily rate before the multiplication (150 days on 1.000 euro are 5.000,00).
        importo = float(_cent(_dec(retribuzione_mensile) * _dec(giorni_preavviso) / 30))
        base_importo = f"retribuzione mensile x {giorni_preavviso} giorni / 30 (art. 2118 co. 2 c.c.)"

    return {
        "ccnl": ccnl,
        "ccnl_nome": ccnl_data["nome"],
        "livello": livello,
        "anzianita_anni": anzianita_anni,
        "fascia_anzianita": fascia,
        "tipo": tipo,
        "giorni_preavviso": giorni_preavviso,
        "giorni_preavviso_fonte": "forniti dal chiamante" if dal_chiamante else "tabella CCNL inclusa",
        "retribuzione_giornaliera": retribuzione_giornaliera,
        "importo": importo,
        "base_importo": base_importo,
        "riferimento_normativo": f"Artt. 2118-2119 c.c. — {ccnl_data['fonte']}",
    }


@mcp.tool(tags={"lavoro"})
@sourced("inps_parametri")
def calcolo_naspi(
    retribuzione_media_mensile: float,
    settimane_contributive: int,
    eta_anni: int,
) -> dict:
    """Calcola l'importo e la durata della NASpI (indennità di disoccupazione).

    Applica la formula dell'anno con soglia, massimale, durata pari a metà delle settimane
    contributive degli ultimi 4 anni e riduzione del 3% al mese dal 6° mese di fruizione
    (dall'8° se l'età alla domanda è ≥ 55). Con meno di 13 settimane di contribuzione nei
    quattro anni la NASpI non spetta (art. 3 co. 1 lett. b): l'esito è 'non_spettante',
    senza importo. Non verifica lo stato di disoccupazione involontaria (lett. a) né, per
    gli eventi dal 2025, le 13 settimane successive a dimissioni volontarie (lett. c-bis).
    Vigenza: D.Lgs. 22/2015 artt. 3-5 nel testo vigente al 2026-09-29 — Circ. INPS n. 4 del 28-01-2026 par. 6
    (soglia 1.456,72 e massimale 1.584,70 euro per il 2026).
    Precisione: INDICATIVO (il calcolo INPS considera le retribuzioni imponibili effettive dei 4 anni precedenti).
    Chaining: → scadenze_licenziamento() per le scadenze di impugnazione collegate al licenziamento.

    Args:
        retribuzione_media_mensile: Retribuzione media mensile imponibile previdenziale in euro (es. 2500.00; valore > 0)
        settimane_contributive: Settimane di contribuzione accreditate negli ultimi 4 anni (es. 104; valore > 0; sotto 13 la prestazione non spetta)
        eta_anni: Età in anni interi alla data di presentazione della domanda (da 55 anni la riduzione parte dall'8° mese)
    """
    if retribuzione_media_mensile <= 0:
        raise ValueError("retribuzione_media_mensile deve essere > 0")
    if settimane_contributive <= 0:
        raise ValueError("settimane_contributive deve essere > 0")

    anno, parametri = _parametri_inps()
    soglia = parametri["naspi"]["retribuzione_riferimento_mensile"]
    massimale = parametri["naspi"]["importo_massimo_mensile"]
    base_output = {
        "retribuzione_media_mensile": retribuzione_media_mensile,
        "settimane_contributive": settimane_contributive,
        "eta_anni": eta_anni,
        "anno_parametri": anno,
        f"soglia_{anno}": soglia,
        f"massimale_{anno}": massimale,
    }
    # Not checked by the tool: it has no input for them (art. 3 co. 1 lett. a and c-bis).
    requisiti_non_verificati = [
        "stato di disoccupazione involontaria (art. 3 co. 1 lett. a D.Lgs. 22/2015): dimissioni volontarie non danno diritto "
        "salvo giusta causa o risoluzione consensuale ex art. 7 L. 604/1966",
        "per gli eventi dal 1° gennaio 2025, se il rapporto a tempo indeterminato precedente è cessato per dimissioni "
        "volontarie nei 12 mesi prima, servono 13 settimane di contribuzione dopo quella cessazione (art. 3 co. 1 lett. c-bis)",
    ]

    # Art. 3 co. 1 lett. b: at least thirteen weeks of contribution in the four years before
    # the start of unemployment, together with the other requirements. Below that there is no NASpI.
    if settimane_contributive < 13:
        return {
            **base_output,
            "esito": "non_spettante",
            "importo_mensile_iniziale": 0.0,
            "durata_mesi": 0,
            "decalage_da_mese": 8 if eta_anni >= 55 else 6,
            "totale_stimato": 0.0,
            "piano_mensile": [],
            "motivo": (
                f"{settimane_contributive} settimane di contribuzione nei quattro anni sono meno di 13: "
                "requisito dell'art. 3 co. 1 lett. b D.Lgs. 22/2015 non soddisfatto, la NASpI non spetta"
            ),
            "requisiti_non_verificati": requisiti_non_verificati,
            "riferimento_normativo": "D.Lgs. 22/2015 art. 3 co. 1 lett. b",
        }

    d_retribuzione = _dec(retribuzione_media_mensile)
    d_soglia = _dec(soglia)
    if d_retribuzione <= d_soglia:
        naspi_base = Decimal("0.75") * d_retribuzione
    else:
        naspi_base = Decimal("0.75") * d_soglia + Decimal("0.25") * (d_retribuzione - d_soglia)
    naspi_base = _cent(min(naspi_base, _dec(massimale)))

    # Duration: weeks / 2, converted to months, capped at 24
    durata_mesi_raw = settimane_contributive / 2 / 4.33
    durata_mesi = min(round(durata_mesi_raw, 1), 24.0)
    durata_mesi_interi = int(durata_mesi) if durata_mesi == int(durata_mesi) else durata_mesi

    # Art. 4 co. 3: -3% every month from the first day of the sixth month of use (eighth from
    # age 55 at the application), so that month 6 is the first reduced one, each step on the
    # amount of the month before (compound).
    decalage_da_mese = 8 if eta_anni >= 55 else 6
    fattore = Decimal("0.97")

    piano_mensile = []
    totale = Decimal(0)
    n_mesi = int(durata_mesi) + (1 if durata_mesi > int(durata_mesi) else 0)

    for mese in range(1, n_mesi + 1):
        if mese >= decalage_da_mese:
            importo_corrente = _cent(naspi_base * fattore ** (mese - decalage_da_mese + 1))
        else:
            importo_corrente = naspi_base

        # Last month may be partial
        if mese == n_mesi and durata_mesi != int(durata_mesi):
            frazione = _dec(durata_mesi - int(durata_mesi))
            contributo = _cent(importo_corrente * frazione)
        else:
            contributo = importo_corrente

        totale += contributo
        piano_mensile.append({"mese": mese, "importo": float(contributo)})

    # Return first 6 + last entry for brevity
    piano_ridotto = piano_mensile[:6]
    if len(piano_mensile) > 6:
        piano_ridotto.append({"mese": piano_mensile[-1]["mese"], "importo": piano_mensile[-1]["importo"], "nota": "ultimo mese"})

    return {
        **base_output,
        "esito": "calcolato",
        "importo_mensile_iniziale": float(naspi_base),
        "durata_mesi": durata_mesi_interi,
        "decalage_da_mese": decalage_da_mese,
        "totale_stimato": float(_cent(totale)),
        "piano_mensile": piano_ridotto,
        "requisiti_non_verificati": requisiti_non_verificati,
        "riferimento_normativo": "D.Lgs. 22/2015 artt. 3-5 — Circ. INPS n. 4/2026",
    }


@mcp.tool(tags={"lavoro"})
def scadenze_licenziamento(
    data_licenziamento: str,
    data_impugnazione: str | None = None,
    data_rifiuto_conciliazione: str | None = None,
) -> dict:
    """Calcola le scadenze perentorie per l'impugnazione del licenziamento.

    I termini di impugnazione sono perentori e si calcolano in giorni di calendario.
    Il mancato rispetto del termine di 60 giorni per l'impugnazione stragiudiziale
    determina la decadenza dall'azione, non sanabile.
    Vigenza: art. 6 L. 604/1966 nel testo dell'art. 32 L. 183/2010 e dell'art. 1 co. 38 L. 92/2012
    (60 giorni per l'impugnazione stragiudiziale; 180 giorni dall'impugnazione per il deposito del
    ricorso o per la richiesta di conciliazione/arbitrato; 60 giorni dal rifiuto o dal mancato
    accordo). Il rito speciale "Fornero" (art. 1 co. 47 ss. L. 92/2012) è stato abrogato dal
    D.Lgs. 149/2022 per i giudizi introdotti dal 28/02/2023.
    Precisione: ESATTO per il computo dei termini di calendario (senza sospensione feriale, che non
    si applica alle cause di lavoro ex art. 3 L. 742/1969); il termine di 180 giorni decorre
    dall'impugnazione effettiva, passare `data_impugnazione` per il calcolo esatto.

    Args:
        data_licenziamento: Data di ricezione della comunicazione di licenziamento (formato YYYY-MM-DD)
        data_impugnazione: Data in cui l'impugnazione stragiudiziale è stata inviata (YYYY-MM-DD);
                           se assente il deposito è calcolato dall'ultimo giorno utile (60° giorno)
        data_rifiuto_conciliazione: Data del rifiuto o del mancato accordo sulla conciliazione o
                           arbitrato richiesti (YYYY-MM-DD), per il termine residuo di 60 giorni
    """
    try:
        dt_lic = _parse_date(data_licenziamento)
    except ValueError:
        raise ValueError("data_licenziamento deve essere in formato YYYY-MM-DD")
    for nome, valore in (("data_impugnazione", data_impugnazione), ("data_rifiuto_conciliazione", data_rifiuto_conciliazione)):
        if valore is not None:
            try:
                _parse_date(valore)
            except ValueError:
                raise ValueError(f"{nome} deve essere in formato YYYY-MM-DD")

    dt_impugnazione = _add_days(dt_lic, 60)
    dt_impugnazione_effettiva = _parse_date(data_impugnazione) if data_impugnazione else dt_impugnazione
    dt_deposito = _add_days(dt_impugnazione_effettiva, 180)

    oggi = _clock.today()

    def _stato(dt: date) -> str:
        delta = (dt - oggi).days
        if delta < 0:
            return f"SCADUTA ({abs(delta)} giorni fa)"
        if delta == 0:
            return "SCADE OGGI"
        if delta <= 7:
            return f"URGENTE — scade tra {delta} giorni"
        return f"scade tra {delta} giorni"

    avvertimenti = []
    if (dt_impugnazione - oggi).days <= 14 and oggi <= dt_impugnazione:
        avvertimenti.append("URGENTE: termine impugnazione stragiudiziale in scadenza imminente")
    if oggi > dt_deposito:
        avvertimenti.append("ATTENZIONE: termine per il deposito del ricorso già scaduto")
    if data_impugnazione and dt_impugnazione_effettiva > dt_impugnazione:
        avvertimenti.append("ATTENZIONE: l'impugnazione risulta inviata oltre i 60 giorni dalla comunicazione del licenziamento (decadenza)")

    scadenze = {
        "impugnazione_stragiudiziale": {
            "data": dt_impugnazione.isoformat(),
            "termine_giorni": 60,
            "stato": _stato(dt_impugnazione),
            "descrizione": "Comunicazione scritta di impugnazione (raccomandata/PEC) entro 60 giorni dalla ricezione del licenziamento — art. 6 co. 1 L. 604/1966",
        },
        "deposito_ricorso": {
            "data": dt_deposito.isoformat(),
            "termine_giorni": 180,
            "decorre_da": data_impugnazione or f"ultimo giorno utile per l'impugnazione ({dt_impugnazione.isoformat()})",
            "stato": _stato(dt_deposito),
            "descrizione": "Deposito del ricorso al giudice del lavoro, o comunicazione della richiesta di conciliazione/arbitrato, entro 180 giorni dall'impugnazione — art. 6 co. 2 L. 604/1966",
        },
    }
    if data_rifiuto_conciliazione:
        dt_post = _add_days(_parse_date(data_rifiuto_conciliazione), 60)
        scadenze["post_conciliazione"] = {
            "data": dt_post.isoformat(),
            "termine_giorni": 60,
            "decorre_da": data_rifiuto_conciliazione,
            "stato": _stato(dt_post),
            "descrizione": "Deposito del ricorso entro 60 giorni dal rifiuto o dal mancato accordo sulla conciliazione o arbitrato — art. 6 co. 2 L. 604/1966",
        }
    else:
        scadenze["post_conciliazione"] = {
            "data": None,
            "termine_giorni": 60,
            "decorre_da": "rifiuto o mancato accordo sulla conciliazione o arbitrato (passare data_rifiuto_conciliazione)",
            "descrizione": "Se la conciliazione o l'arbitrato richiesti sono rifiutati o non si raggiunge l'accordo, il ricorso va depositato entro 60 giorni — art. 6 co. 2 L. 604/1966",
        }

    return {
        "data_licenziamento": data_licenziamento,
        "scadenze": scadenze,
        "avvertimenti": avvertimenti,
        "nota": (
            "I termini sono perentori e di calendario; la sospensione feriale non si applica alle "
            "controversie di lavoro (art. 3 L. 742/1969). I 180 giorni decorrono dalla data in cui "
            "l'impugnazione è stata inviata: senza `data_impugnazione` il calcolo assume l'ultimo giorno utile."
        ),
        "riferimento_normativo": "Art. 6 L. 604/1966 (testo ex art. 32 L. 183/2010 e art. 1 co. 38 L. 92/2012)",
    }


@mcp.tool(tags={"lavoro"})
@sourced("irpef_scaglioni", "inps_parametri")
def costo_lavoro(
    retribuzione_lorda_annua: float,
    tipo_contratto: str = "dipendente",
) -> dict:
    """Stima il costo totale del lavoro per l'azienda e il netto per il dipendente.

    Calcolo semplificato per un rapporto a tempo indeterminato a tempo pieno per l'intero anno, con
    aliquote medie del datore di lavoro (variano per settore INAIL, dimensione aziendale, anzianità e
    agevolazioni). Quota del lavoratore: IVS 9,19% (5,84% per l'apprendista, circ. INPS n. 128/2012) più
    l'1% sulla retribuzione eccedente la prima fascia pensionabile (art. 3-ter D.L. 384/1992, circ. INPS
    n. 6/2026). IRPEF con le detrazioni dell'art. 13 TUIR (compreso il +65 euro del co. 1.1) e le misure
    della L. 207/2024 (somma non imponibile fino a 20.000 euro di reddito, ulteriore detrazione oltre).
    IRAP sul personale a tempo indeterminato pari a zero (costo interamente deducibile). TFR: quota annua
    al netto dello 0,50% dell'art. 3 L. 297/1982.
    Vigenza: art. 2120 c.c.; artt. 11 e 13 TUIR; art. 1 co. 4-6 L. 207/2024 (dal 2025); art. 11 co. 4-octies D.Lgs. 446/1997; art. 3-ter D.L. 384/1992; art. 1 co. 773 L. 296/2006 (apprendistato); art. 42 L. 289/2002 (dirigenti iscritti al FPLD INPS dal 2003); circ. INPS n. 128/2012 e n. 6/2026; testo vigente al 2026-09-29.
    Precisione: INDICATIVO (aliquota del datore al 30% media non verificabile su fonte ufficiale; nessun massimale contributivo per gli iscritti dal 1996; rapporto a tempo pieno e indeterminato, senza addizionali locali, trattamento integrativo né detrazioni per carichi di famiglia; verificare le aliquote del CCNL e dell'INPS applicabili)
    Chaining: → calcolo_naspi() per la stima NASpI in caso di licenziamento.

    Args:
        retribuzione_lorda_annua: Retribuzione lorda annua in euro (es. 30000.0; valore > 0)
        tipo_contratto: 'dipendente' (standard), 'apprendista' (quota del lavoratore 5,84%) o 'dirigente' (iscritti al FPLD INPS)
    """
    if retribuzione_lorda_annua <= 0:
        raise ValueError("retribuzione_lorda_annua deve essere > 0")
    if tipo_contratto not in ("dipendente", "apprendista", "dirigente"):
        raise ValueError("tipo_contratto deve essere 'dipendente', 'apprendista' o 'dirigente'")

    from src.tools.dichiarazione_redditi import _detrazione_art13

    lordo = retribuzione_lorda_annua
    anno, parametri = _parametri_inps()
    prima_fascia = parametri["contributi"]["prima_fascia_pensionabile"]
    massimale = parametri["contributi"]["massimale_base_contributiva"]

    # Employee INPS contributions
    if tipo_contratto == "dirigente":
        aliq_dip = 0.0919  # IVS FPLD, quota del lavoratore (33% = 23,81% datore + 9,19% lavoratore)
        aliq_datore = 0.2390  # IVS del datore più altri contributi (indicativa)
        nota_contrib = "Aliquote medie dirigente: iscritti al FPLD INPS dal 2003 (art. 42 L. 289/2002) — verificare con consulente"
    elif tipo_contratto == "apprendista":
        aliq_dip = 0.0584  # circ. INPS 128/2012 par. 8: quota del lavoratore per tutta la durata
        aliq_datore = 0.1161  # 10% (art. 1 co. 773 L. 296/2006) + 1,61%: aliquota piena (oltre 9 dipendenti o dal 3° anno)
        nota_contrib = (
            "Aliquote apprendisti: datore 11,61% è l'aliquota piena (per le aziende fino a 9 dipendenti "
            "3,11% nel 1° anno e 4,61% nel 2°, art. 1 co. 773 L. 296/2006)"
        )
    else:
        aliq_dip = 0.0919
        aliq_datore = 0.3000  # IVS + CIGS + malattia + maternità + INAIL medio
        nota_contrib = "Aliquote medie dipendente ordinario — variano per settore e dimensione"

    # Art. 3-ter D.L. 384/1992: 1% on the pay above the first pensionable band (circ. INPS 6/2026 par. 5).
    contributo_aggiuntivo = _cent(max(Decimal(0), _dec(lordo) - _dec(prima_fascia)) * Decimal("0.01"))
    contributi_dip_dec = _cent(_dec(lordo) * _dec(aliq_dip)) + contributo_aggiuntivo
    contributi_dip = float(contributi_dip_dec)
    imponibile_irpef = float(_dec(lordo) - contributi_dip_dec)

    irpef_lorda = _calcola_irpef_semplificata(imponibile_irpef)
    # Art. 13 TUIR co. 1 lett. a-b and co. 1.1 (+65 euro between 25.000 and 35.000), ratios to four decimals.
    detrazione_lavoro = _detrazione_art13(imponibile_irpef, "dipendente")

    somma_esente = Decimal(0)
    detrazione_ulteriore = Decimal(0)
    if anno >= 2025:  # art. 1 co. 4-6 L. 207/2024, from the 2025 tax year
        reddito = _dec(imponibile_irpef)
        if reddito <= 20000:
            # Co. 4: sum that does not form income, percentage on the employment income (co. 5: full year).
            pct = Decimal("0.071") if reddito <= 8500 else Decimal("0.053") if reddito <= 15000 else Decimal("0.048")
            somma_esente = _cent(reddito * pct)
        elif reddito <= 32000:
            detrazione_ulteriore = Decimal(1000)  # co. 6 lett. a
        elif reddito <= 40000:
            # Co. 6 lett. b: 1.000 x (40.000 - reddito) / 8.000 (exact ratio, no truncation stated by the norm).
            detrazione_ulteriore = _cent(Decimal(1000) * (Decimal(40000) - reddito) / Decimal(8000))
    irpef_netta = max(0.0, float(_cent(_dec(irpef_lorda) - _dec(detrazione_lavoro) - detrazione_ulteriore)))

    netto = float(_cent(_dec(lordo) - contributi_dip_dec - _dec(irpef_netta) + somma_esente))

    # Employer cost
    contributi_datore = round(lordo * aliq_datore, 2)
    # Art. 2120 c.c.: quota = retribuzione / 13,5; art. 3 L. 297/1982: minus 0,50% (the tool's 6,9074%).
    tfr = float(_cent(_dec(lordo) / Decimal("13.5") - _dec(lordo) * Decimal("0.005")))
    # Art. 11 co. 4-octies D.Lgs. 446/1997: cost of permanent staff fully deductible from the IRAP base.
    irap = 0.0
    costo_totale = round(lordo + contributi_datore + tfr + irap, 2)

    cuneo_fiscale = round((costo_totale - netto) / costo_totale * 100, 1) if costo_totale > 0 else 0.0

    avvertenze = []
    if lordo > massimale:
        avvertenze.append(
            f"Retribuzione oltre il massimale annuo della base contributiva ({_it(massimale)} euro nel {anno}): "
            "per gli iscritti dal 1996 la contribuzione IVS non è dovuta sull'eccedenza; il tool non conosce "
            "l'anzianità contributiva e applica le aliquote all'intera retribuzione"
        )

    return {
        "tipo_contratto": tipo_contratto,
        "lordo_annuo": lordo,
        "contributi_dipendente": contributi_dip,
        "aliquota_contributi_dipendente_pct": round(aliq_dip * 100, 2),
        "contributo_aggiuntivo_1_pct": float(contributo_aggiuntivo),
        "imponibile_irpef": round(imponibile_irpef, 2),
        "irpef_lorda": irpef_lorda,
        "detrazione_lavoro_dipendente": detrazione_lavoro,
        "detrazione_ulteriore_l_207_2024": float(detrazione_ulteriore),
        "irpef_stimata": irpef_netta,
        "somma_non_imponibile_l_207_2024": float(somma_esente),
        "netto_stimato": netto,
        "contributi_datore": contributi_datore,
        "aliquota_contributi_datore_pct": round(aliq_datore * 100, 2),
        "tfr_annuo": tfr,
        "irap_stimata": irap,
        "costo_azienda_totale": costo_totale,
        "cuneo_fiscale_pct": cuneo_fiscale,
        "nota": nota_contrib,
        "avvertenze": avvertenze,
        "avvertimento": "INDICATIVO — le aliquote variano per settore INAIL, dimensione, regione e agevolazioni. Verificare con consulente del lavoro. IRAP sul personale a tempo indeterminato: costo deducibile (art. 11 co. 4-octies D.Lgs. 446/1997), non sommata.",
        "riferimento_normativo": "D.P.R. 917/1986 artt. 11 e 13 (IRPEF) — L. 207/2024 art. 1 co. 4-6 — D.L. 384/1992 art. 3-ter e circ. INPS 128/2012 e 6/2026 (contributi) — D.Lgs. 446/1997 art. 11 co. 4-octies (IRAP) — Art. 2120 c.c. e art. 3 L. 297/1982 (TFR)",
    }


@mcp.tool(tags={"lavoro"})
def offerta_conciliativa(
    anni_servizio: float,
    retribuzione_mensile: float,
    dimensione_azienda: str = "grande",
) -> dict:
    """Calcola l'offerta conciliativa esente da IRPEF e contributi (art. 6 D.Lgs. 23/2015).

    L'offerta conciliativa è uno strumento deflativo del contenzioso: se accettata dal
    lavoratore estingue il rapporto e l'impugnazione. L'importo è completamente detassato
    (non soggetto a IRPEF né a contributi previdenziali).
    Vigenza: D.Lgs. 23/2015 art. 6.
    Precisione: ESATTO per la formula legale (1 mensilità/anno per le aziende grandi, 0,5 mensilità/anno per le piccole, nei limiti floor/cap).
    Chaining: → indennita_licenziamento() per confronto con indennità giudiziale standard.

    Args:
        anni_servizio: Anni di servizio maturati (es. 5.0; valore > 0)
        retribuzione_mensile: Retribuzione mensile lorda in euro (es. 2000.00; valore > 0)
        dimensione_azienda: 'grande' (>15 dipendenti) o 'piccola' (≤15 dipendenti)
    """
    if anni_servizio <= 0:
        raise ValueError("anni_servizio deve essere > 0")
    if retribuzione_mensile <= 0:
        raise ValueError("retribuzione_mensile deve essere > 0")
    if dimensione_azienda not in ("grande", "piccola"):
        raise ValueError("dimensione_azienda deve essere 'grande' o 'piccola'")

    if dimensione_azienda == "grande":
        floor_val = 3.0
        cap_val = 27.0
        mensilita = max(floor_val, min(anni_servizio, cap_val))
    else:
        floor_val = 1.5
        # Il tetto di 6 mensilità (art. 9 c.1 D.Lgs. 23/2015, richiamato anche per l'art. 6)
        # è stato dichiarato illegittimo da Corte Cost. 118/2025; ricostruito come 27/2.
        # Il dimezzamento (×0,5) NON è stato toccato dalla Corte e resta in vigore.
        cap_val = 13.5
        mensilita = max(floor_val, min(anni_servizio * 0.5, cap_val))
    importo = round(mensilita * retribuzione_mensile, 2)

    return {
        "anni_servizio": anni_servizio,
        "retribuzione_mensile": retribuzione_mensile,
        "dimensione_azienda": dimensione_azienda,
        "mensilita": mensilita,
        "floor_mensilita": floor_val,
        "cap_mensilita": cap_val,
        "importo": importo,
        "detassato": True,
        "nota": "Importo esente da IRPEF e da contributi previdenziali se accettato in sede conciliativa (art. 6 D.Lgs. 23/2015). Piccole imprese: dimezzamento ex art. 9 c.1 ancora vigente; tetto di 6 mensilità abrogato da Corte Cost. 118/2025 (la formula agevolata è ricostruita con cap 13,5; il datore può comunque offrire di più).",
        "confronto_giudiziale": "Indennità giudiziale standard: 2 mensilità/anno (floor 6, cap 36 per aziende grandi) — usare indennita_licenziamento() per il confronto",
        "riferimento_normativo": "D.Lgs. 23/2015 artt. 6, 9 — Corte Cost. 118/2025",
    }
