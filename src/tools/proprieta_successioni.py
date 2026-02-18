"""Sezione 9 — Proprietà e Successioni: eredità, imposte successione, usufrutto, IMU, compravendita."""

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
    """Calcola quote ereditarie legittime secondo il codice civile italiano (art. 536 ss. c.c.).

    Args:
        massa_ereditaria: Valore totale della massa ereditaria in euro
        eredi: Composizione nucleo familiare: {coniuge: bool, figli: int, ascendenti: bool, fratelli: int}
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
    """Calcola imposte di successione con franchigie e ipocatastali.

    Args:
        valore_beni: Valore complessivo dei beni ereditati in euro
        parentela: Grado di parentela: 'coniuge_linea_retta', 'fratelli_sorelle', 'parenti_fino_4_grado_affini_fino_3', 'altri'
        immobili: True se l'eredità comprende beni immobili
        prima_casa: True se almeno un erede usufruisce dell'agevolazione prima casa
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

    Args:
        valore_piena_proprieta: Valore della piena proprietà in euro
        eta_usufruttuario: Età dell'usufruttuario in anni compiuti
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
    """Calcola IMU per immobile in base a rendita catastale e categoria.

    Args:
        rendita_catastale: Rendita catastale non rivalutata in euro
        categoria: Categoria catastale (es. 'A/2', 'C/1', 'D/1', 'A/10')
        aliquota_comunale: Aliquota comunale in percentuale (default 0.86 = 8,6 per mille)
        prima_casa: True se abitazione principale di lusso (A/1, A/8, A/9)
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
    """Calcola imposte per acquisto immobile (registro, ipotecaria, catastale, IVA).

    Args:
        prezzo: Prezzo di acquisto in euro
        tipo_immobile: 'abitazione', 'lusso', 'terreno_agricolo', 'commerciale'
        prima_casa: True se si usufruisce dell'agevolazione prima casa
        da_costruttore: True se acquisto da impresa costruttrice (soggetto IVA)
        rendita_catastale: Rendita catastale (opzionale, per calcolo prezzo-valore prima casa)
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
