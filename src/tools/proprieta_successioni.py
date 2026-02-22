"""Calcolo quote ereditarie, imposte di successione (D.Lgs. 346/1990), IMU (L. 160/2019),
compravendita immobiliare (DPR 131/1986), usufrutto, cedolare secca, spese condominiali."""

import json
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "imposte_successione.json") as f:
    _SUCCESSIONE = json.load(f)

with open(_DATA / "usufrutto_coefficienti.json") as f:
    _USUFRUTTO = json.load(f)


@mcp.tool()
def calcolo_eredita(
    massa_ereditaria: float,
    eredi: dict,
) -> dict:
    """Calcola le quote di legittima e la quota disponibile secondo le norme di successione necessaria.
    Vigenza: Art. 536 ss. c.c. — Successione necessaria (quote immutabili per legge).
    Precisione: ESATTO (quote frazioni legali: 1/2, 1/3, 1/4 ecc. secondo c.c.).

    Args:
        massa_ereditaria: Valore totale della massa ereditaria in euro (€)
        eredi: Composizione del nucleo familiare: {'coniuge': bool, 'figli': int, 'ascendenti': bool, 'fratelli': int}
    """
    coniuge = eredi.get("coniuge", False)
    figli = eredi.get("figli", 0)
    ascendenti = eredi.get("ascendenti", False)
    fratelli = eredi.get("fratelli", 0)

    quote = []

    if coniuge and figli == 0 and not ascendenti:
        # Coniuge solo: 1/2 legittima, 1/2 disponibile
        quote.append({"erede": "coniuge", "quota_legittima": "1/2", "valore": round(massa_ereditaria / 2, 2)})
        disponibile = 1 / 2

    elif coniuge and figli == 1:
        # Coniuge + 1 figlio: 1/3 ciascuno, 1/3 disponibile
        quote.append({"erede": "coniuge", "quota_legittima": "1/3", "valore": round(massa_ereditaria / 3, 2)})
        quote.append({"erede": "figlio", "quota_legittima": "1/3", "valore": round(massa_ereditaria / 3, 2)})
        disponibile = 1 / 3

    elif coniuge and figli >= 2:
        # Coniuge + 2+ figli: 1/4 coniuge, 1/2 figli (divisa), 1/4 disponibile
        quota_coniuge = massa_ereditaria / 4
        quota_figli_totale = massa_ereditaria / 2
        quota_per_figlio = quota_figli_totale / figli
        quote.append({"erede": "coniuge", "quota_legittima": "1/4", "valore": round(quota_coniuge, 2)})
        for i in range(1, figli + 1):
            quote.append({
                "erede": f"figlio_{i}",
                "quota_legittima": f"1/{2 * figli}",
                "valore": round(quota_per_figlio, 2),
            })
        disponibile = 1 / 4

    elif not coniuge and figli == 1:
        # Solo 1 figlio: 1/2 legittima, 1/2 disponibile
        quote.append({"erede": "figlio", "quota_legittima": "1/2", "valore": round(massa_ereditaria / 2, 2)})
        disponibile = 1 / 2

    elif not coniuge and figli >= 2:
        # Solo 2+ figli: 2/3 legittima (divisa), 1/3 disponibile
        quota_figli_totale = massa_ereditaria * 2 / 3
        quota_per_figlio = quota_figli_totale / figli
        for i in range(1, figli + 1):
            quote.append({
                "erede": f"figlio_{i}",
                "quota_legittima": f"2/{3 * figli}",
                "valore": round(quota_per_figlio, 2),
            })
        disponibile = 1 / 3

    elif coniuge and figli == 0 and ascendenti:
        # Coniuge + ascendenti: 1/2 coniuge, 1/4 ascendenti, 1/4 disponibile
        quote.append({"erede": "coniuge", "quota_legittima": "1/2", "valore": round(massa_ereditaria / 2, 2)})
        quote.append({"erede": "ascendenti", "quota_legittima": "1/4", "valore": round(massa_ereditaria / 4, 2)})
        disponibile = 1 / 4

    elif not coniuge and figli == 0 and ascendenti:
        # Solo ascendenti: 1/3 legittima, 2/3 disponibile
        quote.append({"erede": "ascendenti", "quota_legittima": "1/3", "valore": round(massa_ereditaria / 3, 2)})
        disponibile = 2 / 3

    else:
        # Nessun legittimario (fratelli o altri): tutta disponibile
        disponibile = 1.0

    # Fratelli concorrono solo nella successione legittima (senza testamento), non nella legittima
    if fratelli > 0 and not coniuge and figli == 0 and not ascendenti:
        quota_per_fratello = massa_ereditaria / fratelli
        for i in range(1, fratelli + 1):
            quote.append({
                "erede": f"fratello_{i}",
                "quota_successione_legittima": f"1/{fratelli}",
                "valore": round(quota_per_fratello, 2),
                "nota": "Quota per successione legittima (senza testamento). I fratelli non sono legittimari.",
            })
        disponibile = 0.0

    return {
        "massa_ereditaria": massa_ereditaria,
        "eredi": eredi,
        "quote": quote,
        "quota_disponibile": round(massa_ereditaria * disponibile, 2),
        "percentuale_disponibile": f"{round(disponibile * 100, 1)}%",
        "riferimento_normativo": "Art. 536 ss. c.c. — Successione necessaria (legittima)",
    }


@mcp.tool()
def imposte_successione(
    valore_beni: float,
    parentela: str,
    immobili: bool = False,
    prima_casa: bool = False,
) -> dict:
    """Calcola imposta di successione con franchigie, aliquote e imposte ipocatastali.
    Vigenza: D.Lgs. 346/1990 (TU successioni e donazioni); aliquote: 4% (linea retta), 6% (fratelli/altri parenti), 8% (estranei).
    Franchigie: €1.000.000 (coniuge/figli), €100.000 (fratelli), €0 (altri).
    Precisione: ESATTO (aliquote e franchigie di legge vigenti).

    Args:
        valore_beni: Valore complessivo dei beni ereditati in euro (€)
        parentela: Grado di parentela: 'coniuge_linea_retta', 'fratelli_sorelle', 'parenti_fino_4_grado_affini_fino_3', 'altri'
        immobili: True se l'eredità comprende beni immobili (aggiunge imposte ipotecaria e catastale)
        prima_casa: True se almeno un erede beneficia dell'agevolazione prima casa (imposte fisse ridotte)
    """
    aliquota_info = None
    for a in _SUCCESSIONE["aliquote"]:
        if a["parentela"] == parentela:
            aliquota_info = a
            break

    if not aliquota_info:
        return {"errore": f"Parentela '{parentela}' non riconosciuta. Valori: coniuge_linea_retta, fratelli_sorelle, parenti_fino_4_grado_affini_fino_3, altri"}

    franchigia = aliquota_info["franchigia"]
    aliquota = aliquota_info["aliquota"]
    base_imponibile = max(valore_beni - franchigia, 0)
    imposta = round(base_imponibile * aliquota / 100, 2)

    result = {
        "valore_beni": valore_beni,
        "parentela": parentela,
        "franchigia": franchigia,
        "base_imponibile": base_imponibile,
        "aliquota_pct": aliquota,
        "imposta_successione": imposta,
    }

    if immobili:
        ipo = _SUCCESSIONE["imposte_ipocatastali"]
        if prima_casa:
            ipotecaria = ipo["prima_casa"]["ipotecaria"]
            catastale = ipo["prima_casa"]["catastale"]
            result["nota_prima_casa"] = ipo["prima_casa"]["nota"]
        else:
            ipotecaria = max(valore_beni * ipo["ipotecaria"] / 100, ipo["minimo_ipotecaria"])
            catastale = max(valore_beni * ipo["catastale"] / 100, ipo["minimo_catastale"])
            ipotecaria = round(ipotecaria, 2)
            catastale = round(catastale, 2)

        result["imposta_ipotecaria"] = ipotecaria
        result["imposta_catastale"] = catastale
        result["totale_imposte"] = round(imposta + ipotecaria + catastale, 2)
    else:
        result["totale_imposte"] = imposta

    result["riferimento_normativo"] = "TU 346/1990 — Imposta sulle successioni e donazioni"
    return result


@mcp.tool()
def calcolo_usufrutto(
    valore_piena_proprieta: float,
    eta_usufruttuario: int,
) -> dict:
    """Calcola valore dell'usufrutto e della nuda proprietà in base all'età dell'usufruttuario.
    Vigenza: DPR 131/1986 — Prospetto coefficienti usufrutto (aggiornato periodicamente).
    Precisione: ESATTO (coefficienti tabellari ufficiali dell'Agenzia delle Entrate).

    Args:
        valore_piena_proprieta: Valore della piena proprietà in euro (€)
        eta_usufruttuario: Età dell'usufruttuario in anni compiuti (0-120)
    """
    tasso_legale = _USUFRUTTO["tasso_legale"]
    coefficiente = None

    for fascia in _USUFRUTTO["coefficienti"]:
        if fascia["eta_min"] <= eta_usufruttuario <= fascia["eta_max"]:
            coefficiente = fascia["coefficiente"]
            break

    if coefficiente is None:
        return {"errore": f"Età {eta_usufruttuario} fuori range (0-120)"}

    rendita_annua = valore_piena_proprieta * tasso_legale / 100
    valore_usufrutto = round(rendita_annua * coefficiente, 2)
    valore_nuda_proprieta = round(valore_piena_proprieta - valore_usufrutto, 2)

    return {
        "valore_piena_proprieta": valore_piena_proprieta,
        "eta_usufruttuario": eta_usufruttuario,
        "tasso_legale_pct": tasso_legale,
        "coefficiente": coefficiente,
        "rendita_annua": round(rendita_annua, 2),
        "valore_usufrutto": valore_usufrutto,
        "valore_nuda_proprieta": valore_nuda_proprieta,
        "percentuale_usufrutto": round(valore_usufrutto / valore_piena_proprieta * 100, 2),
        "percentuale_nuda_proprieta": round(valore_nuda_proprieta / valore_piena_proprieta * 100, 2),
        "riferimento_normativo": "DPR 131/1986 — Prospetto coefficienti usufrutto",
    }


@mcp.tool()
def calcolo_imu(
    rendita_catastale: float,
    categoria: str,
    aliquota_comunale: float = 0.86,
    prima_casa: bool = False,
) -> dict:
    """Calcola IMU annua e semestrale per immobile in base a rendita catastale e categoria.
    L'abitazione principale è esente IMU salvo categorie di lusso (A/1, A/8, A/9).
    Vigenza: L. 160/2019 art. 1 co. 738-783 — IMU (anno fiscale corrente).
    Precisione: ESATTO per moltiplicatori catastali e rivalutazione 5%; INDICATIVO per aliquota (varia per comune).

    Args:
        rendita_catastale: Rendita catastale non rivalutata dell'immobile in euro (€)
        categoria: Categoria catastale dell'immobile (es. 'A/2', 'A/10', 'C/1', 'D/1')
        aliquota_comunale: Aliquota IMU comunale in percentuale (default 0.86 = 8,6‰; range tipico: 0.46-1.06)
        prima_casa: True se l'immobile è abitazione principale (esente salvo A/1, A/8, A/9)
    """
    cat_upper = categoria.upper().strip()

    moltiplicatori = {
        "A/10": 80,
        "B": 140,
        "C/1": 55,
        "D/5": 80,
    }

    if cat_upper == "A/10":
        molt = 80
    elif cat_upper.startswith("A/"):
        molt = 160
    elif cat_upper.startswith("B"):
        molt = 140
    elif cat_upper == "C/1":
        molt = 55
    elif cat_upper in ("C/3", "C/4", "C/5"):
        molt = 140
    elif cat_upper.startswith("C/"):
        molt = 160
    elif cat_upper == "D/5":
        molt = 80
    elif cat_upper.startswith("D"):
        molt = 65
    else:
        return {"errore": f"Categoria catastale '{categoria}' non riconosciuta"}

    rendita_rivalutata = rendita_catastale * 1.05
    base_imponibile = round(rendita_rivalutata * molt, 2)
    imu_annua = round(base_imponibile * aliquota_comunale / 100, 2)

    detrazione = 0.0
    if prima_casa and cat_upper in ("A/1", "A/8", "A/9"):
        detrazione = 200.0
        imu_annua = round(max(imu_annua - detrazione, 0), 2)

    imu_semestrale = round(imu_annua / 2, 2)

    result = {
        "rendita_catastale": rendita_catastale,
        "categoria": cat_upper,
        "moltiplicatore": molt,
        "rendita_rivalutata": round(rendita_rivalutata, 2),
        "base_imponibile": base_imponibile,
        "aliquota_comunale_pct": aliquota_comunale,
        "imu_annua": imu_annua,
        "imu_semestrale": imu_semestrale,
    }

    if prima_casa:
        if cat_upper in ("A/1", "A/8", "A/9"):
            result["detrazione_prima_casa"] = detrazione
            result["nota"] = "IMU dovuta solo per abitazioni di lusso (A/1, A/8, A/9)"
        else:
            result["imu_annua"] = 0.0
            result["imu_semestrale"] = 0.0
            result["nota"] = "Abitazione principale esente IMU (escluse A/1, A/8, A/9)"

    result["riferimento_normativo"] = "L. 160/2019 art. 1 co. 738-783 — IMU"
    return result


@mcp.tool()
def imposte_compravendita(
    prezzo: float,
    tipo_immobile: str = "abitazione",
    prima_casa: bool = False,
    da_costruttore: bool = False,
    rendita_catastale: float | None = None,
) -> dict:
    """Calcola imposte per acquisto immobile: registro, ipotecaria, catastale e IVA.
    Se da_costruttore=True si applica IVA (4%, 10% o 22%); altrimenti imposta di registro (2% o 9%).
    Vigenza: DPR 131/1986 — TU Imposta di registro; DPR 633/1972 (IVA).
    Precisione: ESATTO per aliquote e importi fissi vigenti; INDICATIVO per base prezzo-valore (dipende da rendita).

    Args:
        prezzo: Prezzo di acquisto in euro (€)
        tipo_immobile: Tipo di immobile: 'abitazione', 'lusso', 'terreno_agricolo', 'commerciale'
        prima_casa: True se si beneficia dell'agevolazione prima casa (riduce le aliquote)
        da_costruttore: True se acquisto da impresa costruttrice soggetta IVA
        rendita_catastale: Rendita catastale dell'immobile in euro (€, opzionale — abilita calcolo prezzo-valore)
    """
    reg = _SUCCESSIONE["imposta_registro_compravendita"]
    imposte = {}

    if da_costruttore:
        iva_data = reg["da_costruttore_iva"]
        if tipo_immobile == "lusso":
            rates = iva_data["lusso"]
        elif prima_casa:
            rates = iva_data["prima_casa"]
        else:
            rates = iva_data["seconda_casa"]

        iva = round(prezzo * rates["iva"] / 100, 2)
        imposte = {
            "iva_aliquota_pct": rates["iva"],
            "iva": iva,
            "imposta_registro": rates["registro"],
            "imposta_ipotecaria": rates["ipotecaria"],
            "imposta_catastale": rates["catastale"],
            "totale_imposte": round(iva + rates["registro"] + rates["ipotecaria"] + rates["catastale"], 2),
        }

    elif tipo_immobile == "terreno_agricolo":
        rates = reg["terreno_agricolo"]
        registro = max(round(prezzo * rates["registro"] / 100, 2), 1000)
        imposte = {
            "imposta_registro_aliquota_pct": rates["registro"],
            "imposta_registro": registro,
            "imposta_ipotecaria": rates["ipotecaria"],
            "imposta_catastale": rates["catastale"],
            "totale_imposte": round(registro + rates["ipotecaria"] + rates["catastale"], 2),
        }

    else:
        if prima_casa:
            rates = reg["prima_casa"]
        else:
            rates = reg["seconda_casa"]

        # Prezzo-valore: per abitazioni (no lusso) da privato, base = rendita * 115.5 (prima casa) o * 126 (seconda)
        base = prezzo
        if rendita_catastale and tipo_immobile == "abitazione":
            moltiplicatore = 115.5 if prima_casa else 126.0
            base = round(rendita_catastale * moltiplicatore, 2)
            imposte["base_prezzo_valore"] = base
            imposte["nota_prezzo_valore"] = f"Rendita {rendita_catastale} x {moltiplicatore}"

        registro = max(round(base * rates["registro"] / 100, 2), rates["minimo_registro"])
        imposte.update({
            "imposta_registro_aliquota_pct": rates["registro"],
            "imposta_registro": registro,
            "imposta_ipotecaria": rates["ipotecaria"],
            "imposta_catastale": rates["catastale"],
            "totale_imposte": round(registro + rates["ipotecaria"] + rates["catastale"], 2),
        })

    return {
        "prezzo": prezzo,
        "tipo_immobile": tipo_immobile,
        "prima_casa": prima_casa,
        "da_costruttore": da_costruttore,
        **imposte,
        "riferimento_normativo": "DPR 131/1986 — TU Imposta di registro",
    }


@mcp.tool()
def pensione_reversibilita(
    pensione_de_cuius: float,
    beneficiari: dict,
    reddito_beneficiario: float = 0,
) -> dict:
    """Calcola pensione di reversibilità INPS con quote per tipologia di beneficiari e riduzione per cumulo redditi.

    Quote: coniuge solo 60%, coniuge+1 figlio 80%, coniuge+2+ figli 100%,
    solo 1 figlio 70%, 2 figli 80%, 3+ figli 100%, genitori 15% ciascuno.
    Riduzione se reddito supera soglie (3x, 4x, 5x trattamento minimo).
    Vigenza: L. 335/1995 art. 1 co. 41; Tabella F (trattamento minimo aggiornato annualmente).
    Precisione: INDICATIVO (il trattamento minimo di riferimento viene aggiornato ogni anno dall'INPS).

    Args:
        pensione_de_cuius: Importo annuo lordo della pensione del defunto in euro (€)
        beneficiari: Composizione dei beneficiari: {'coniuge': bool, 'figli': int, 'figli_minori': int, 'genitori': int}
        reddito_beneficiario: Reddito annuo lordo del beneficiario principale in euro (€, per verifica tetto cumulo)
    """
    coniuge = beneficiari.get("coniuge", False)
    figli = beneficiari.get("figli", 0)
    genitori = beneficiari.get("genitori", 0)

    # Determine quota
    if coniuge and figli == 0:
        quota_pct = 60
        descrizione = "Coniuge solo"
    elif coniuge and figli == 1:
        quota_pct = 80
        descrizione = "Coniuge + 1 figlio"
    elif coniuge and figli >= 2:
        quota_pct = 100
        descrizione = f"Coniuge + {figli} figli"
    elif not coniuge and figli == 1:
        quota_pct = 70
        descrizione = "1 figlio solo"
    elif not coniuge and figli == 2:
        quota_pct = 80
        descrizione = "2 figli soli"
    elif not coniuge and figli >= 3:
        quota_pct = 100
        descrizione = f"{figli} figli soli"
    elif genitori > 0 and not coniuge and figli == 0:
        quota_pct = 15 * genitori
        descrizione = f"{genitori} genitore/i"
    else:
        return {"errore": "Nessun beneficiario valido individuato"}

    pensione_lorda = round(pensione_de_cuius * quota_pct / 100, 2)

    # Riduzione per cumulo redditi (trattamento minimo 2024 ~ €7.781,93)
    trattamento_minimo = 7781.93
    riduzione_pct = 0
    if reddito_beneficiario > 0:
        rapporto = reddito_beneficiario / trattamento_minimo
        if rapporto > 5:
            riduzione_pct = 50
        elif rapporto > 4:
            riduzione_pct = 40
        elif rapporto > 3:
            riduzione_pct = 25

    pensione_netta = round(pensione_lorda * (1 - riduzione_pct / 100), 2)

    return {
        "pensione_de_cuius": pensione_de_cuius,
        "beneficiari": beneficiari,
        "descrizione_quota": descrizione,
        "quota_pct": quota_pct,
        "pensione_lorda_annua": pensione_lorda,
        "pensione_lorda_mensile": round(pensione_lorda / 13, 2),
        "riduzione_cumulo": {
            "reddito_beneficiario": reddito_beneficiario,
            "trattamento_minimo": trattamento_minimo,
            "riduzione_pct": riduzione_pct,
        },
        "pensione_netta_annua": pensione_netta,
        "pensione_netta_mensile": round(pensione_netta / 13, 2),
        "riferimento_normativo": "L. 335/1995 art. 1 co. 41; L. 335/1995 Tabella F",
    }


@mcp.tool()
def grado_parentela(
    relazione: str,
) -> dict:
    """Calcola il grado di parentela tra due persone, con rilevanza successoria e fiscale.

    Accetta input descrittivo (es. 'cugino', 'zio') oppure catena di passi separati da virgola
    (es. 'genitore,figlio' = fratello, grado 2; 'genitore,genitore,figlio' = zio, grado 3).
    Vigenza: Art. 74-77 c.c. — Parentela e affinità.
    Precisione: ESATTO (calcolo sul numero di passi).

    Args:
        relazione: Relazione familiare ('figlio', 'nonno', 'fratello', 'zio', 'cugino', 'prozio', 'cugino_secondo') o catena di passi separati da virgola (es. 'genitore,figlio,figlio')
    """
    # Relazioni note
    relazioni_note = {
        "figlio": {"grado": 1, "linea": "retta", "passi": ["figlio"]},
        "genitore": {"grado": 1, "linea": "retta", "passi": ["genitore"]},
        "nipote_figlio": {"grado": 2, "linea": "retta", "passi": ["figlio", "figlio"]},
        "nonno": {"grado": 2, "linea": "retta", "passi": ["genitore", "genitore"]},
        "fratello": {"grado": 2, "linea": "collaterale", "passi": ["genitore", "figlio"]},
        "sorella": {"grado": 2, "linea": "collaterale", "passi": ["genitore", "figlio"]},
        "zio": {"grado": 3, "linea": "collaterale", "passi": ["genitore", "genitore", "figlio"]},
        "nipote_zio": {"grado": 3, "linea": "collaterale", "passi": ["genitore", "figlio", "figlio"]},
        "bisnonno": {"grado": 3, "linea": "retta", "passi": ["genitore", "genitore", "genitore"]},
        "pronipote": {"grado": 3, "linea": "retta", "passi": ["figlio", "figlio", "figlio"]},
        "cugino": {"grado": 4, "linea": "collaterale", "passi": ["genitore", "genitore", "figlio", "figlio"]},
        "prozio": {"grado": 4, "linea": "collaterale", "passi": ["genitore", "genitore", "genitore", "figlio"]},
        "cugino_secondo": {"grado": 6, "linea": "collaterale", "passi": ["genitore"] * 3 + ["figlio"] * 3},
    }

    rel = relazione.lower().strip()

    if rel in relazioni_note:
        info = relazioni_note[rel]
        grado = info["grado"]
        linea = info["linea"]
        passi = info["passi"]
    elif "," in rel:
        passi = [p.strip() for p in rel.split(",")]
        grado = len(passi)
        # Determine linea: retta if all same direction, collaterale otherwise
        has_up = any(p in ("genitore", "padre", "madre") for p in passi)
        has_down = any(p in ("figlio", "figlia") for p in passi)
        linea = "collaterale" if (has_up and has_down) else "retta"
    else:
        return {
            "errore": f"Relazione '{relazione}' non riconosciuta",
            "relazioni_disponibili": sorted(relazioni_note.keys()),
            "suggerimento": "Oppure usa catena di passi separati da virgola: 'genitore,figlio' = fratello (grado 2)",
        }

    # Limite parentela rilevante per legge
    rilevanza = "Parentela rilevante per successione" if grado <= 6 else "Oltre il 6° grado: nessun effetto successorio"

    return {
        "relazione": relazione,
        "grado": grado,
        "linea": linea,
        "passi": passi,
        "rilevanza_successoria": rilevanza,
        "imposta_successione": (
            "Franchigia €1.000.000 + aliquota 4%"
            if grado == 1 or rel in ("coniuge", "figlio", "genitore")
            else "Franchigia €100.000 + aliquota 6%"
            if grado == 2 and rel in ("fratello", "sorella")
            else "Aliquota 6% (fino al 4° grado)"
            if grado <= 4
            else "Aliquota 8% (oltre il 4° grado o estranei)"
        ),
        "riferimento_normativo": "Art. 74-77 c.c. — Parentela e affinità",
    }


@mcp.tool()
def calcolo_valore_catastale(
    rendita_catastale: float,
    categoria: str,
    tipo: str = "successione",
) -> dict:
    """Calcola valore catastale rivalutato dell'immobile per successione, compravendita o IMU.
    Il coefficiente applicato varia per categoria e finalità (successione/compravendita/IMU).
    Vigenza: DPR 131/1986; L. 160/2019 — Coefficienti valore catastale.
    Precisione: ESATTO (rivalutazione 5% + coefficiente tabellare per categoria).

    Args:
        rendita_catastale: Rendita catastale non rivalutata dell'immobile in euro (€)
        categoria: Categoria catastale (es. 'A/2', 'A/10', 'B/1', 'C/1', 'D/1', 'D/8')
        tipo: Finalità del calcolo: 'successione', 'compravendita', 'imu'
    """
    tipo = tipo.lower()
    cat = categoria.upper().strip()

    rendita_rivalutata = rendita_catastale * 1.05

    # Coefficienti per successione/compravendita
    if cat == "A/10":
        coeff_succ = 63.0
        coeff_comp = 63.0
    elif cat.startswith("A/"):
        coeff_succ = 120.0
        coeff_comp = 126.0
    elif cat.startswith("B"):
        coeff_succ = 140.0
        coeff_comp = 140.0
    elif cat == "C/1":
        coeff_succ = 42.84
        coeff_comp = 42.84
    elif cat.startswith("C/"):
        coeff_succ = 120.0
        coeff_comp = 126.0
    elif cat == "D/5":
        coeff_succ = 63.0
        coeff_comp = 63.0
    elif cat.startswith("D"):
        coeff_succ = 63.0
        coeff_comp = 63.0
    else:
        return {"errore": f"Categoria catastale '{categoria}' non riconosciuta"}

    if tipo == "successione":
        coeff = coeff_succ
    elif tipo == "compravendita":
        coeff = coeff_comp
    elif tipo == "imu":
        # IMU uses different multipliers (handled by calcolo_imu tool)
        if cat == "A/10":
            coeff = 80.0
        elif cat.startswith("A/"):
            coeff = 160.0
        elif cat.startswith("B"):
            coeff = 140.0
        elif cat == "C/1":
            coeff = 55.0
        elif cat in ("C/3", "C/4", "C/5"):
            coeff = 140.0
        elif cat.startswith("C/"):
            coeff = 160.0
        elif cat == "D/5":
            coeff = 80.0
        elif cat.startswith("D"):
            coeff = 65.0
        else:
            coeff = 120.0
    else:
        return {"errore": f"Tipo '{tipo}' non valido. Valori ammessi: successione, compravendita, imu"}

    valore_catastale = round(rendita_rivalutata * coeff, 2)

    return {
        "rendita_catastale": rendita_catastale,
        "rendita_rivalutata": round(rendita_rivalutata, 2),
        "categoria": cat,
        "tipo": tipo,
        "coefficiente": coeff,
        "valore_catastale": valore_catastale,
        "riferimento_normativo": "DPR 131/1986; L. 160/2019 — Coefficienti valore catastale",
    }


@mcp.tool()
def calcolo_superficie_commerciale(
    superficie_calpestabile: float,
    balconi: float = 0,
    terrazzi: float = 0,
    giardino: float = 0,
    cantina: float = 0,
    garage: float = 0,
) -> dict:
    """Calcola la superficie commerciale dell'immobile applicando i coefficienti DPR 138/1998.
    Utile per la valutazione catastale e per i contratti di locazione/compravendita.
    Vigenza: DPR 138/1998 — Standard dimensionali catastali.
    Precisione: ESATTO (coefficienti fissi: calpestabile 1.00, balconi 0.33, terrazzi 0.25, giardino 0.10, cantina 0.25, garage 0.50).

    Args:
        superficie_calpestabile: Superficie interna calpestabile in mq
        balconi: Superficie balconi in mq (default 0)
        terrazzi: Superficie terrazzi scoperti in mq (default 0)
        giardino: Superficie giardino/area esterna in mq (default 0)
        cantina: Superficie cantina in mq (default 0)
        garage: Superficie garage/box in mq (default 0)
    """
    coefficienti = {
        "calpestabile": 1.00,
        "balconi": 0.33,
        "terrazzi": 0.25,
        "giardino": 0.10,
        "cantina": 0.25,
        "garage": 0.50,
    }

    dettaglio = {}
    totale = 0.0

    superfici = {
        "calpestabile": superficie_calpestabile,
        "balconi": balconi,
        "terrazzi": terrazzi,
        "giardino": giardino,
        "cantina": cantina,
        "garage": garage,
    }

    for nome, mq in superfici.items():
        coeff = coefficienti[nome]
        contributo = round(mq * coeff, 2)
        if mq > 0:
            dettaglio[nome] = {
                "mq_reali": mq,
                "coefficiente": coeff,
                "mq_commerciali": contributo,
            }
        totale += contributo

    return {
        "superficie_commerciale": round(totale, 2),
        "dettaglio": dettaglio,
        "coefficienti_applicati": coefficienti,
        "riferimento_normativo": "DPR 138/1998 — Standard dimensionali catastali",
    }


@mcp.tool()
def cedolare_secca(
    canone_annuo: float,
    tipo_contratto: str = "libero",
    irpef_marginale: float = 38,
) -> dict:
    """Confronta la convenienza tra cedolare secca e IRPEF ordinaria per redditi da locazione.
    Vigenza: D.Lgs. 23/2011 art. 3 — aliquote: 21% (libero), 10% (concordato), 26% (brevi periodi).
    Precisione: INDICATIVO per IRPEF (le addizionali regionali/comunali stimate al 2% variano per comune).

    Args:
        canone_annuo: Canone annuo di locazione in euro (€)
        tipo_contratto: Tipo di contratto: 'libero' (cedolare 21%), 'concordato' (cedolare 10%), 'brevi' (cedolare 26%)
        irpef_marginale: Aliquota IRPEF marginale del locatore in percentuale (es. 23, 35, 43)
    """
    tipo = tipo_contratto.lower()
    if tipo not in ("libero", "concordato", "brevi"):
        return {"errore": "tipo_contratto deve essere 'libero', 'concordato' o 'brevi'"}

    if tipo == "libero":
        aliquota_cedolare = 21.0
    elif tipo == "concordato":
        aliquota_cedolare = 10.0
    else:  # brevi
        aliquota_cedolare = 26.0
    imposta_cedolare = round(canone_annuo * aliquota_cedolare / 100, 2)

    # IRPEF ordinaria: base imponibile = 95% del canone (abbattimento forfettario 5%)
    base_irpef = canone_annuo * 0.95
    imposta_irpef = round(base_irpef * irpef_marginale / 100, 2)

    # Addizionali comunali/regionali stimate (~2%)
    addizionali = round(base_irpef * 0.02, 2)
    totale_irpef = round(imposta_irpef + addizionali, 2)

    risparmio = round(totale_irpef - imposta_cedolare, 2)
    conveniente = "cedolare_secca" if risparmio > 0 else "irpef_ordinaria"

    return {
        "canone_annuo": canone_annuo,
        "tipo_contratto": tipo,
        "cedolare_secca": {
            "aliquota_pct": aliquota_cedolare,
            "imposta": imposta_cedolare,
        },
        "irpef_ordinaria": {
            "base_imponibile_95_pct": round(base_irpef, 2),
            "aliquota_marginale_pct": irpef_marginale,
            "imposta_irpef": imposta_irpef,
            "addizionali_stimate": addizionali,
            "totale": totale_irpef,
        },
        "risparmio_cedolare": risparmio,
        "opzione_conveniente": conveniente,
        "nota": "Con cedolare secca: nessun adeguamento ISTAT, no addizionali, no imposta registro",
        "riferimento_normativo": "D.Lgs. 23/2011 art. 3 — Cedolare secca sugli affitti",
    }


@mcp.tool()
def imposta_registro_locazioni(
    canone_annuo: float,
    durata_anni: int = 4,
    tipo_contratto: str = "libero",
    prima_registrazione: bool = True,
) -> dict:
    """Calcola imposta di registro per contratto di locazione abitativa.
    Aliquota: 2% del canone annuo (libero) o 1% (concordato in comuni ad alta densità); minimo €67 per prima registrazione.
    Vigenza: DPR 131/1986 art. 5 Tariffa Parte I.
    Precisione: ESATTO (aliquote e minimo di legge).

    Args:
        canone_annuo: Canone annuo di locazione in euro (€)
        durata_anni: Durata contrattuale in anni (default 4; tipico: 4+4 libero, 3+2 concordato)
        tipo_contratto: Tipo di contratto: 'libero' (aliquota 2%) o 'concordato' (aliquota 1%)
        prima_registrazione: True per prima registrazione (minimo €67), False per annualità successive
    """
    tipo = tipo_contratto.lower()
    if tipo not in ("libero", "concordato"):
        return {"errore": "tipo_contratto deve essere 'libero' o 'concordato'"}

    aliquota = 2.0 if tipo == "libero" else 1.0
    imposta_annua = round(canone_annuo * aliquota / 100, 2)

    minimo = 67.0 if prima_registrazione else 0.0
    imposta_annua_effettiva = max(imposta_annua, minimo)

    imposta_totale = round(imposta_annua_effettiva + imposta_annua * (durata_anni - 1), 2)

    # Opzione pagamento intero periodo (sconto 50% delle annualità successive)
    # In realtà: si può pagare per l'intera durata con sconto del canone costante
    prima_annualita_intera = max(canone_annuo * aliquota / 100, minimo)
    imposta_intera_durata = round(prima_annualita_intera + canone_annuo * aliquota / 100 * (durata_anni - 1), 2)

    return {
        "canone_annuo": canone_annuo,
        "durata_anni": durata_anni,
        "tipo_contratto": tipo,
        "aliquota_pct": aliquota,
        "imposta_prima_annualita": round(imposta_annua_effettiva, 2),
        "imposta_annualita_successive": round(imposta_annua, 2),
        "totale_durata_contratto": imposta_totale,
        "opzione_intera_durata": imposta_intera_durata,
        "minimo_applicato": prima_registrazione and imposta_annua < minimo,
        "nota": "Imposta a carico 50% locatore e 50% conduttore (salvo patto contrario)" if tipo == "libero" else "Aliquota ridotta 1% per comuni ad alta densità abitativa (concordato)",
        "riferimento_normativo": "DPR 131/1986 art. 5 Tariffa Parte I — Imposta registro locazioni",
    }


@mcp.tool()
def spese_condominiali(
    importo_totale: float,
    millesimi_proprietario: float,
    tipo_spesa: str = "ordinaria",
    piano: int = 0,
    immobile_locato: bool = False,
) -> dict:
    """Calcola la quota condominiale spettante all'unità immobiliare per millesimi e tipo di spesa.
    Se l'immobile è in locazione, ripartisce tra proprietario e inquilino (L. 392/1978 art. 9).
    Vigenza: Art. 1123-1124 c.c.; L. 392/1978 art. 9.
    Precisione: ESATTO per millesimi e percentuali legali; INDICATIVO per ascensore (normalizzazione su 10 piani).

    Args:
        importo_totale: Importo totale della spesa condominiale in euro (€)
        millesimi_proprietario: Millesimi di proprietà dell'unità immobiliare (es. 85.50 su 1000)
        tipo_spesa: Tipo di spesa: 'ordinaria', 'straordinaria', 'riscaldamento', 'ascensore'
        piano: Piano dell'unità immobiliare (rilevante solo per ascensore; 0 = piano terra)
        immobile_locato: True se l'immobile è concesso in locazione (abilita ripartizione proprietario/inquilino)
    """
    tipo = tipo_spesa.lower()
    if tipo not in ("ordinaria", "straordinaria", "riscaldamento", "ascensore"):
        return {"errore": "tipo_spesa deve essere: ordinaria, straordinaria, riscaldamento, ascensore"}

    if tipo == "ascensore":
        # Art. 1124 c.c.: 50% millesimi proprietà + 50% in proporzione all'altezza
        quota_millesimi = importo_totale * 0.5 * (millesimi_proprietario / 1000)
        # Coefficiente piano: semplificazione lineare
        coeff_piano = max(piano, 0.5)  # piano terra = 0.5
        quota_piano = importo_totale * 0.5 * (coeff_piano / 10)  # normalizzato su 10 piani
        quota_proprietario_tot = round(quota_millesimi + quota_piano, 2)
        metodo = f"50% millesimi ({round(quota_millesimi, 2)}€) + 50% piano {piano} ({round(quota_piano, 2)}€)"
    else:
        quota_proprietario_tot = round(importo_totale * millesimi_proprietario / 1000, 2)
        metodo = f"Millesimi: {millesimi_proprietario}/1000"

    result = {
        "importo_totale": importo_totale,
        "millesimi": millesimi_proprietario,
        "tipo_spesa": tipo,
        "metodo_ripartizione": metodo,
        "quota_unita": quota_proprietario_tot,
    }

    if immobile_locato:
        # Art. 9 L. 392/1978: inquilino paga spese ordinarie, proprietario le straordinarie
        if tipo == "ordinaria" or tipo == "riscaldamento":
            quota_inquilino = quota_proprietario_tot
            quota_proprietario = 0.0
            nota = "Spesa ordinaria: interamente a carico del conduttore (art. 9 L. 392/1978)"
        elif tipo == "straordinaria":
            quota_inquilino = 0.0
            quota_proprietario = quota_proprietario_tot
            nota = "Spesa straordinaria: interamente a carico del proprietario"
        else:  # ascensore
            # Manutenzione ordinaria ascensore: conduttore; straordinaria: proprietario
            quota_inquilino = round(quota_proprietario_tot * 0.5, 2)
            quota_proprietario = round(quota_proprietario_tot * 0.5, 2)
            nota = "Ascensore: manutenzione ordinaria al conduttore, straordinaria al proprietario"

        result["ripartizione_locazione"] = {
            "quota_proprietario": quota_proprietario,
            "quota_inquilino": quota_inquilino,
            "nota": nota,
        }

    result["riferimento_normativo"] = "Art. 1123-1124 c.c.; L. 392/1978 art. 9 — Ripartizione spese condominiali"
    return result
