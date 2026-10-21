"""Calcolo quote ereditarie, imposte di successione (D.Lgs. 346/1990), IMU (L. 160/2019),
compravendita immobiliare (DPR 131/1986), usufrutto, cedolare secca, spese condominiali."""

import json
from pathlib import Path

from src.lib import _clock
from src.server import mcp
from src.lib import _clock
from src.lib._data import sourced

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "imposte_successione.json", encoding="utf-8") as f:
    _SUCCESSIONE = json.load(f)

with open(_DATA / "usufrutto_coefficienti.json", encoding="utf-8") as f:
    _USUFRUTTO = json.load(f)

with open(_DATA / "tassi_legali.json", encoding="utf-8") as f:
    _TASSI_LEGALI_REGISTRO: list[dict] = json.load(f)["tassi"]


def _tasso_legale_oggi() -> float:
    """Legal interest rate (%) in force today, from tassi_legali.json (latest row if none matches)."""
    oggi = _clock.today().isoformat()
    for riga in _TASSI_LEGALI_REGISTRO:
        if riga["dal"] <= oggi <= riga["al"]:
            return riga["tasso"]
    return _TASSI_LEGALI_REGISTRO[-1]["tasso"]


@mcp.tool(tags={"proprieta"})
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


@mcp.tool(tags={"proprieta"})
@sourced("imposte_successione", alternativa="aliquote_franchigie")
def imposte_successione(
    valore_beni: float,
    parentela: str,
    immobili: bool = False,
    prima_casa: bool = False,
    aliquote_franchigie: list[dict] | None = None,
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
        aliquote_franchigie: Lista sostitutiva fornita dal chiamante con le stesse voci di
                          src/data/imposte_successione.json → aliquote: [{'parentela':
                          'coniuge_linea_retta', 'aliquota': 4, 'franchigia': 1000000}, ...].
                          Se la fornisci, il calcolo delle aliquote e franchigie non legge la
                          tabella inclusa: utile se vuoi garantire tu i valori applicati
    """
    aliquote = aliquote_franchigie if aliquote_franchigie else _SUCCESSIONE["aliquote"]
    aliquota_info = None
    for a in aliquote:
        # Tolerant of caller-supplied garbage: a malformed entry is skipped and
        # falls through to the not-recognized error below, not to a crash.
        if isinstance(a, dict) and a.get("parentela") == parentela:
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


@mcp.tool(tags={"proprieta"})
@sourced("usufrutto_coefficienti")
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
    if valore_piena_proprieta <= 0:
        return {"errore": "valore_piena_proprieta deve essere positivo"}

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


@mcp.tool(tags={"proprieta"})
def calcolo_imu(
    rendita_catastale: float,
    categoria: str,
    aliquota_comunale: float | None = None,
    prima_casa: bool = False,
) -> dict:
    """Calcola IMU annua e semestrale per immobile in base a rendita catastale e categoria.
    L'abitazione principale è esente IMU salvo categorie di lusso (A/1, A/8, A/9).
    Vigenza: L. 160/2019 art. 1 co. 745 (moltiplicatori), 748 (aliquota di base 0,5% per l'abitazione principale A/1, A/8, A/9), 754 (aliquota di base 0,86% per gli altri immobili) — IMU. Verificata al 2026-09-29.
    Non gestisce: quota statale 0,76% del gruppo D (co. 753), aliquote specifiche di rurali strumentali (co. 750), riduzioni del 50% o del 25% (co. 747, 760), quota e mesi di possesso.
    Precisione: ESATTO per moltiplicatori catastali e rivalutazione 5%; INDICATIVO per aliquota (varia per comune).

    Args:
        rendita_catastale: Rendita catastale non rivalutata dell'immobile in euro (€)
        categoria: Categoria catastale dell'immobile (es. 'A/2', 'A/10', 'C/1', 'D/1')
        aliquota_comunale: Aliquota IMU comunale in percentuale (default se omessa: 0.5 = 5‰ per l'abitazione principale A/1, A/8, A/9, co. 748; 0.86 = 8,6‰ per gli altri immobili, co. 754; range tipico: 0.46-1.06)
        prima_casa: True se l'immobile è abitazione principale (esente salvo A/1, A/8, A/9)
    """
    cat_upper = categoria.upper().strip()

    if aliquota_comunale is None:
        # Co. 748: base rate 0.5% for the principal residence A/1, A/8, A/9; co. 754: 0.86% otherwise.
        aliquota_comunale = 0.5 if (prima_casa and cat_upper in ("A/1", "A/8", "A/9")) else 0.86

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
        imu_annua = round(max(imu_annua - detrazione, 0.0), 2)

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


@mcp.tool(tags={"proprieta"})
@sourced("imposte_successione", alternativa="aliquote_registro")
def imposte_compravendita(
    prezzo: float,
    tipo_immobile: str = "abitazione",
    prima_casa: bool = False,
    da_costruttore: bool = False,
    rendita_catastale: float | None = None,
    aliquote_registro: dict | None = None,
) -> dict:
    """Calcola imposte per acquisto immobile: registro, ipotecaria, catastale e IVA.
    Se da_costruttore=True si applica IVA (4%, 10% o 22%); altrimenti imposta di registro (2% o 9%).
    Vigenza: DPR 131/1986 — TU Imposta di registro (art. 1 Tariffa I e nota II-bis, come modificati dall'art. 10 D.Lgs. 23/2011, dal 1/1/2014); DPR 633/1972 (IVA). Verificata al 2026-09-29.
    Le abitazioni di lusso (A/1, A/8, A/9) non godono mai dell'aliquota prima casa: registro 9% anche con prima_casa=True.
    Non sono inclusi l'imposta di bollo e le tasse ipotecarie/tributi catastali dovuti negli atti soggetti a IVA (nelle vendite tra privati ne e' esente ex art. 10 co. 3 D.Lgs. 23/2011); non gestisce le cessioni di immobili strumentali da impresa (ipotecaria 3%, catastale 1%).
    Precisione: INDICATIVO (totale_imposte esclude bollo e tasse ipotecarie delle vendite con IVA; base prezzo-valore dipende dalla rendita).

    Args:
        prezzo: Prezzo di acquisto in euro (€)
        tipo_immobile: Tipo di immobile: 'abitazione', 'lusso', 'terreno_agricolo', 'commerciale'
        prima_casa: True se si beneficia dell'agevolazione prima casa (riduce le aliquote)
        da_costruttore: True se acquisto da impresa costruttrice soggetta IVA
        rendita_catastale: Rendita catastale dell'immobile in euro (€, opzionale — abilita calcolo prezzo-valore)
        aliquote_registro: Sezione sostitutiva fornita dal chiamante con la struttura di
                          src/data/imposte_successione.json → imposta_registro_compravendita
                          ('prima_casa', 'seconda_casa', 'terreno_agricolo', 'da_costruttore_iva',
                          'lusso'...). Se la fornisci, il calcolo non legge la tabella inclusa
    """
    reg = aliquote_registro if aliquote_registro else _SUCCESSIONE["imposta_registro_compravendita"]
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
        # Nota II-bis art. 1 Tariffa I TUR: the 2% prima-casa rate never applies to
        # luxury dwellings (A/1, A/8, A/9), so 'lusso' is always taxed at 9%.
        if prima_casa and tipo_immobile != "lusso":
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


# Annual INPS trattamento minimo (monthly minimum x 13): 598.61 (2024), 603.40 (2025, circ. INPS
# 23/2025), 611.85 (2026, circ. INPS 153/2025). It is the reference of Tabella F L. 335/1995.
_TRATTAMENTO_MINIMO_ANNUO = {2024: 7781.93, 2025: 7844.20, 2026: 7954.05}


@mcp.tool(tags={"proprieta"})
def pensione_reversibilita(
    pensione_de_cuius: float,
    beneficiari: dict,
    reddito_beneficiario: float = 0,
    anno: int | None = None,
) -> dict:
    """Calcola pensione di reversibilità INPS con quote per tipologia di beneficiari e riduzione per cumulo redditi.

    Quote: coniuge solo 60%, coniuge+1 figlio 80%, coniuge+2+ figli 100%,
    solo 1 figlio 70%, 2 figli 80%, 3+ figli 100%, genitori 15% ciascuno.
    Riduzione se reddito supera soglie (3x, 4x, 5x trattamento minimo: 25%, 40%, 50%), con clausola di
    salvaguardia (il trattamento cumulato non puo' essere inferiore a quello spettante con reddito pari al
    limite della fascia precedente) e senza riduzione se il beneficiario fa parte di un nucleo con figli
    minori, studenti o inabili (art. 1 co. 41 L. 335/1995).
    Vigenza: L. 335/1995 art. 1 co. 41; Tabella F; trattamento minimo INPS annuo (2024: 7.781,93; 2025: 7.844,20; 2026: 7.954,05). Verificata al 2026-09-29.
    Precisione: INDICATIVO (il trattamento minimo di riferimento viene aggiornato ogni anno dall'INPS; la riduzione e' applicata all'intera quota, non per singolo beneficiario).

    Args:
        pensione_de_cuius: Importo annuo lordo della pensione del defunto in euro (€)
        beneficiari: Composizione dei beneficiari: {'coniuge': bool, 'figli': int, 'figli_minori': int, 'genitori': int}; 'figli_minori' = figli minorenni, studenti o inabili nel nucleo (se > 0 non si applica alcuna riduzione per cumulo)
        reddito_beneficiario: Reddito annuo lordo del beneficiario principale in euro (€, per verifica tetto cumulo)
        anno: Anno del trattamento minimo di riferimento (2024, 2025, 2026; default: anno corrente, o l'ultimo disponibile)
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

    # Riduzione per cumulo redditi (Tabella F L. 335/1995)
    if anno is None:
        anno = _clock.today().year
    anno_tm = anno if anno in _TRATTAMENTO_MINIMO_ANNUO else max(_TRATTAMENTO_MINIMO_ANNUO)
    trattamento_minimo = _TRATTAMENTO_MINIMO_ANNUO[anno_tm]
    figli_minori = beneficiari.get("figli_minori", 0) or 0

    def _riduzione(reddito: float) -> int:
        rapporto = reddito / trattamento_minimo
        if rapporto > 5:
            return 50
        if rapporto > 4:
            return 40
        if rapporto > 3:
            return 25
        return 0

    riduzione_pct = 0
    salvaguardia = False
    pensione_netta = pensione_lorda
    if reddito_beneficiario > 0 and figli_minori <= 0:
        riduzione_pct = _riduzione(reddito_beneficiario)
        pensione_netta = round(pensione_lorda * (1 - riduzione_pct / 100), 2)
        if riduzione_pct:
            # Salvaguardia (art. 1 co. 41): the cumulated treatment cannot be lower than the one due
            # with income equal to the upper limit of the band just below the actual one.
            soglia = {25: 3, 40: 4, 50: 5}[riduzione_pct] * trattamento_minimo
            riduzione_prec = _riduzione(soglia)
            pensione_al_limite = pensione_lorda * (1 - riduzione_prec / 100)
            minimo_garantito = round(soglia + pensione_al_limite - reddito_beneficiario, 2)
            if minimo_garantito > pensione_netta:
                pensione_netta = min(minimo_garantito, pensione_lorda)
                salvaguardia = True

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
            "clausola_salvaguardia_applicata": salvaguardia,
            "anno_trattamento_minimo": anno_tm,
            "esclusa_per_figli_minori": bool(figli_minori and figli_minori > 0),
        },
        "pensione_netta_annua": pensione_netta,
        "pensione_netta_mensile": round(pensione_netta / 13, 2),
        "riferimento_normativo": "L. 335/1995 art. 1 co. 41; L. 335/1995 Tabella F",
    }


@mcp.tool(tags={"proprieta"})
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
        passi_validi = {"genitore", "padre", "madre", "figlio", "figlia"}
        if not passi or any(p not in passi_validi for p in passi):
            return {
                "errore": f"Relazione '{relazione}' non riconosciuta",
                "relazioni_disponibili": sorted(relazioni_note.keys()),
                "suggerimento": "Oppure usa catena di passi separati da virgola: 'genitore,figlio' = fratello (grado 2)",
            }
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


@mcp.tool(tags={"proprieta"})
def calcolo_valore_catastale(
    rendita_catastale: float,
    categoria: str,
    tipo: str = "successione",
    prima_casa: bool = False,
) -> dict:
    """Calcola valore catastale rivalutato dell'immobile per successione, compravendita o IMU.
    Formula: rendita × 1,05 × moltiplicatore-base (il moltiplicatore-base si applica alla rendita
    GIÀ rivalutata del 5%). I moltiplicatori di A/10, C/1, D ed E (60, 40,8) incorporano gia' la
    rivalutazione del 20% ex art. 1-bis co. 7 DL 168/2004 e non vanno maggiorati ancora; il gruppo B
    usa 168 (140 x 1,2) sia in successione sia in compravendita (art. 309 co. 6 lett. b D.Lgs. 141/2026). Terreni (categoria 'T'):
    reddito dominicale rivalutato del 25% (art. 3 co. 51 L. 662/1996) x 90 (x 135 per l'IMU, co. 746 L. 160/2019).
    Vigenza: DPR 131/1986 art. 52 co. 4-5; D.Lgs. 346/1990 art. 34; DL 168/2004 art. 1-bis co. 7; DL 262/2006 art. 2 c.45
    (dal 1/1/2027 confluiti negli artt. 299 e 309 del D.Lgs. 141/2026, stessi moltiplicatori). Verificata al 2026-09-29.
    Non accetta una data di riferimento (successioni aperte prima del 2006) e non gestisce l'esenzione IMU del gruppo E.
    Precisione: ESATTO (rivalutazione + moltiplicatore-base per categoria).

    Args:
        rendita_catastale: Rendita catastale non rivalutata dell'immobile in euro (€)
        categoria: Categoria catastale (es. 'A/2', 'A/10', 'B/1', 'C/1', 'D/1', 'E/1') oppure 'T' per un terreno (rendita_catastale = reddito dominicale)
        tipo: Finalità del calcolo: 'successione', 'compravendita', 'imu'
        prima_casa: True se prima casa (moltiplicatore agevolato e nessun +20% di registro)
    """
    tipo = tipo.lower()
    cat = categoria.upper().strip()

    # Terreni: reddito dominicale rivalutato del 25% (art. 3 co. 51 L. 662/1996); fabbricati: 5% (co. 48)
    is_terreno = cat in ("T", "TERRENO")
    rendita_rivalutata = rendita_catastale * (1.25 if is_terreno else 1.05)

    # Moltiplicatore-BASE applicato alla rendita GIÀ rivalutata del 5% (rendita × 1,05 × base).
    # NB: i valori "effettivi" (es. 126 = 120×1,05; 63 = 60×1,05; 42,84 = 40,8×1,05) NON vanno
    # applicati alla rendita rivalutata, pena la doppia rivalutazione (bug corretto qui).
    if is_terreno:
        base = 90.0  # art. 52 co. 4 DPR 131/1986: terreni 90 volte il reddito dominicale rivalutato
    elif cat == "A/10":
        base = 60.0
    elif cat.startswith("B"):
        base = 168.0  # gruppo B: 140 (DL 262/2006) + 20% ex DL 168/2004, oggi art. 309 co. 6 lett. b D.Lgs. 141/2026
    elif cat == "C/1":
        base = 40.8
    elif cat.startswith("E"):
        base = 40.8
    elif cat.startswith("A"):
        base = 110.0 if prima_casa else 120.0
    elif cat.startswith("C"):
        base = 110.0 if prima_casa else 120.0
    elif cat.startswith("D"):
        base = 60.0
    else:
        return {"errore": f"Categoria catastale '{categoria}' non riconosciuta"}

    if tipo == "successione":
        coeff = base  # successioni/donazioni: nessuna maggiorazione +20%
    elif tipo == "compravendita":
        # Same multipliers as the succession: the +20% of art. 1-bis co. 7 DL 168/2004 is already in the
        # bases (60, 40.8, 120 and, for the group B, 168 = 140 x 1.2: art. 309 co. 6 D.Lgs. 141/2026).
        coeff = base
    elif tipo == "imu":
        # IMU uses different multipliers (handled by calcolo_imu tool)
        if is_terreno:
            coeff = 135.0  # co. 746 L. 160/2019
        elif cat == "A/10":
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
        "riferimento_normativo": "DPR 131/1986 art. 52; D.Lgs. 346/1990 art. 34; DL 168/2004 art. 1-bis; DL 262/2006 art. 2 c.45",
    }


@mcp.tool(tags={"proprieta"})
def calcolo_superficie_commerciale(
    superficie_calpestabile: float,
    balconi: float = 0,
    terrazzi: float = 0,
    giardino: float = 0,
    cantina: float = 0,
    garage: float = 0,
    balconi_terrazzi_comunicanti: bool = True,
    cantina_comunicante: bool = False,
    garage_comunicante: bool = False,
) -> dict:
    """Calcola la superficie commerciale dell'immobile applicando i criteri dell'allegato C al DPR 138/1998.
    Utile per la valutazione catastale e per i contratti di locazione/compravendita.
    Criteri (gruppo R, allegato C punti 1 lett. b-d e 3): balconi e terrazze 30% fino a 25 mq e 10% oltre se comunicanti
    con i vani principali (15% e 5% se non comunicanti); cantine, soffitte e simili 50% se comunicanti, 25% se non comunicanti
    (stesso criterio applicato al box); area scoperta 10% fino alla superficie dei vani principali e 2% oltre; le
    pertinenze entrano al massimo per meta' della superficie dei vani principali.
    Vigenza: DPR 138/1998 allegato C (norme tecniche per la superficie catastale, in vigore dal 27/5/1998). Verificata al 2026-09-29.
    Il DPR misura la superficie lorda (muri perimetrali fino a 50 cm, muri in comune al 50%) e arrotonda al metro quadrato: questo tool parte dalla superficie indicata dal chiamante e non arrotonda.
    Precisione: INDICATIVO (base dei vani principali fornita dal chiamante, non calcolata sulla superficie lorda; box e categoria catastale non distinti).

    Args:
        superficie_calpestabile: Superficie dei vani principali e accessori diretti in mq (base a coefficiente 1)
        balconi: Superficie balconi in mq (default 0)
        terrazzi: Superficie terrazzi scoperti in mq (default 0); con i balconi condivide la soglia dei 25 mq
        giardino: Superficie giardino/area esterna in mq (default 0)
        cantina: Superficie cantina in mq (default 0)
        garage: Superficie garage/box in mq (default 0)
        balconi_terrazzi_comunicanti: True se balconi e terrazzi comunicano con i vani principali (default True: 30%/10%; False: 15%/5%)
        cantina_comunicante: True se la cantina comunica con i vani principali (50% invece di 25%)
        garage_comunicante: True se il garage comunica con i vani principali (50% invece di 25%)
    """
    dettaglio = {}

    def _add(nome: str, mq: float, mq_comm: float, coeff) -> float:
        if mq > 0:
            dettaglio[nome] = {"mq_reali": mq, "coefficiente": coeff, "mq_commerciali": round(mq_comm, 2)}
        return mq_comm

    principali = _add("calpestabile", superficie_calpestabile, superficie_calpestabile * 1.0, 1.0)

    # Balconi and terrazze share the 25 mq threshold (allegato C, lett. c: "balconi, terrazze e simili")
    c_pieno, c_ridotto = (0.30, 0.10) if balconi_terrazzi_comunicanti else (0.15, 0.05)

    def _balcone(mq: float, gia_usati: float) -> tuple[float, str]:
        entro = max(min(mq, 25 - gia_usati), 0)
        oltre = mq - entro
        return entro * c_pieno + oltre * c_ridotto, f"{c_pieno:.2f} fino a 25 mq, {c_ridotto:.2f} oltre"

    b_mc, b_lbl = _balcone(balconi, 0)
    t_mc, t_lbl = _balcone(terrazzi, balconi)

    # Area scoperta: 10% up to the surface of the main rooms, 2% beyond (lett. d)
    entro = min(giardino, superficie_calpestabile)
    g_mc = entro * 0.10 + (giardino - entro) * 0.02

    c_coeff = 0.50 if cantina_comunicante else 0.25
    g_coeff = 0.50 if garage_comunicante else 0.25
    cant_mc = cantina * c_coeff
    gar_mc = garage * g_coeff

    pertinenze = b_mc + t_mc + g_mc + cant_mc + gar_mc
    tetto = superficie_calpestabile / 2  # allegato C punto 3: at most half of the main rooms surface
    cap = pertinenze > tetto
    fattore = tetto / pertinenze if cap and pertinenze > 0 else 1.0

    totale = principali
    for nome, mq, mc, coeff in (
        ("balconi", balconi, b_mc, b_lbl),
        ("terrazzi", terrazzi, t_mc, t_lbl),
        ("giardino", giardino, g_mc, "0.10 fino alla superficie dei vani, 0.02 oltre"),
        ("cantina", cantina, cant_mc, c_coeff),
        ("garage", garage, gar_mc, g_coeff),
    ):
        totale += _add(nome, mq, mc * fattore, coeff)

    return {
        "superficie_commerciale": round(totale, 2),
        "dettaglio": dettaglio,
        "tetto_pertinenze_applicato": cap,
        "coefficienti_applicati": {
            "calpestabile": 1.0,
            "balconi_terrazzi": b_lbl,
            "giardino": "0.10 fino alla superficie dei vani, 0.02 oltre",
            "cantina": c_coeff,
            "garage": g_coeff,
        },
        "riferimento_normativo": "DPR 138/1998 allegato C — Norme tecniche per la determinazione della superficie catastale",
    }


@mcp.tool(tags={"proprieta"})
def cedolare_secca(
    canone_annuo: float,
    tipo_contratto: str = "libero",
    irpef_marginale: float = 38,
) -> dict:
    """Confronta la convenienza tra cedolare secca e IRPEF ordinaria per redditi da locazione.
    Vigenza: D.Lgs. 23/2011 art. 3 co. 2 — aliquote: 21% (libero), 10% (concordato), 26% (brevi periodi); IRPEF ordinaria: base 95% del canone, 66,5% per il concordato (art. 8 co. 1 L. 431/1998, riduzione ulteriore del 30%). Verificata al 2026-09-29.
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

    # IRPEF ordinaria: base imponibile = 95% del canone (abbattimento forfettario 5%,
    # art. 37 co. 4-bis TUIR); per i contratti concordati il reddito ex art. 34 TUIR e'
    # "ulteriormente ridotto del 30 per cento" (art. 8 co. 1 L. 431/1998): 95% x 70% = 66,5%.
    base_irpef = canone_annuo * 0.95
    if tipo == "concordato":
        base_irpef *= 0.70
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
            # key name kept for compatibility: 95% of the rent, 66.5% for 'concordato'
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


@mcp.tool(tags={"proprieta"})
@sourced("tassi_legali")
def imposta_registro_locazioni(
    canone_annuo: float,
    durata_anni: int = 4,
    tipo_contratto: str = "libero",
    prima_registrazione: bool = True,
) -> dict:
    """Calcola imposta di registro per contratto di locazione abitativa.
    Aliquota: 2% del canone annuo; per il canone concordato (art. 2 c. 3 L. 431/1998) la base imponibile è il 70%
    del canone (art. 8 c. 1 L. 431/1998), cioè 1,4% effettivo; minimo €67 sulla prima annualità.
    Pagando per l'intera durata l'imposta è ridotta di una percentuale pari alla metà del tasso di interesse
    legale per il numero delle annualità (nota all'art. 5 della Tariffa, parte prima, DPR 131/1986).
    Vigenza: art. 5 Tariffa parte I e art. 17 c. 3 DPR 131/1986 (ora art. 21 c. 3 del testo unico, D.Lgs.
    123/2025); art. 8 c. 1 L. 431/1998. Aggiornata al 2026-09-29.
    Precisione: ESATTO (aliquote, base del 70%, minimo e sconto di legge; importi non arrotondati all'euro,
    l'arrotondamento del versamento in F24 non è applicato)

    Args:
        canone_annuo: Canone annuo di locazione in euro (€)
        durata_anni: Durata contrattuale in anni (default 4; tipico: 4+4 libero, 3+2 concordato)
        tipo_contratto: Tipo di contratto: 'libero' (2% sul canone) o 'concordato' (2% sul 70% del canone)
        prima_registrazione: True per prima registrazione (minimo €67), False per annualità successive
    """
    if durata_anni < 1:
        return {"errore": "durata_anni deve essere >= 1"}

    tipo = tipo_contratto.lower()
    if tipo not in ("libero", "concordato"):
        return {"errore": "tipo_contratto deve essere 'libero' o 'concordato'"}

    aliquota = 2.0
    # Art. 8 c. 1 L. 431/1998: per i contratti concordati il corrispettivo e' assunto nella misura minima del 70%
    base_imponibile_pct = 100.0 if tipo == "libero" else 70.0
    imposta_annua = round(canone_annuo * base_imponibile_pct / 100 * aliquota / 100, 2)

    minimo = 67.0 if prima_registrazione else 0.0
    imposta_annua_effettiva = max(imposta_annua, minimo)

    imposta_totale = round(imposta_annua_effettiva + imposta_annua * (durata_anni - 1), 2)

    # Pagamento per l'intera durata: imposta sul corrispettivo dell'intero periodo, ridotta di una percentuale
    # pari alla meta' del tasso legale per il numero delle annualita' (nota art. 5 Tariffa); minimo 67 sul totale.
    tasso_legale = _tasso_legale_oggi()
    sconto_pct = round(tasso_legale / 2 * durata_anni, 4) if durata_anni > 1 else 0.0
    imposta_nominale = imposta_annua * durata_anni
    sconto = round(imposta_nominale * sconto_pct / 100, 2)
    imposta_intera_durata = round(max(imposta_nominale - sconto, minimo), 2)

    return {
        "canone_annuo": canone_annuo,
        "durata_anni": durata_anni,
        "tipo_contratto": tipo,
        "aliquota_pct": aliquota,
        "base_imponibile_pct": base_imponibile_pct,
        "imposta_prima_annualita": round(imposta_annua_effettiva, 2),
        "imposta_annualita_successive": round(imposta_annua, 2),
        "totale_durata_contratto": imposta_totale,
        "opzione_intera_durata": imposta_intera_durata,
        "sconto_intera_durata_pct": sconto_pct,
        "sconto_intera_durata": sconto,
        "minimo_applicato": prima_registrazione and imposta_annua < minimo,
        "nota": "Imposta a carico 50% locatore e 50% conduttore (salvo patto contrario)" if tipo == "libero" else "Canone concordato: 2% sul 70% del canone (art. 8 c. 1 L. 431/1998), 1,4% effettivo",
        "riferimento_normativo": "DPR 131/1986 art. 5 Tariffa Parte I (D.Lgs. 123/2025); art. 8 L. 431/1998 — Imposta registro locazioni",
    }


@mcp.tool(tags={"proprieta"})
def spese_condominiali(
    importo_totale: float,
    millesimi_proprietario: float,
    tipo_spesa: str = "ordinaria",
    piano: int = 0,
    immobile_locato: bool = False,
    piani_edificio: int | None = None,
    somma_altezze_edificio: float | None = None,
) -> dict:
    """Calcola la quota condominiale spettante all'unità immobiliare per millesimi e tipo di spesa.
    Se l'immobile è in locazione, ripartisce tra proprietario e inquilino (L. 392/1978 art. 9).
    Ascensore (art. 1124 c.c.): meta' della spesa in ragione dei millesimi e meta' in proporzione all'altezza del piano
    rispetto alla somma delle altezze di tutte le unita' servite (piano terra = 0,5).
    Locazione (art. 9 L. 392/1978): pulizia, riscaldamento, acqua, energia, funzionamento e manutenzione ordinaria dell'ascensore e
    altri servizi comuni sono interamente a carico del conduttore; la portineria al 90%; la manutenzione straordinaria
    (compresa quella dell'ascensore) al proprietario.
    Vigenza: Art. 1123-1124 c.c.; L. 392/1978 art. 9. Verificata al 2026-09-29.
    Precisione: ESATTO per millesimi e percentuali legali; INDICATIVO per l'ascensore se non si indicano piani_edificio o somma_altezze_edificio (si ipotizza un'unita' per piano da 0 a max(10, piano)); le voci 'ordinaria' non elencate nell'art. 9 (es. manutenzione ordinaria delle parti comuni) sono trattate come oneri accessori del conduttore.

    Args:
        importo_totale: Importo totale della spesa condominiale in euro (€)
        millesimi_proprietario: Millesimi di proprietà dell'unità immobiliare (es. 85.50 su 1000, tra 0 e 1000)
        tipo_spesa: Tipo di spesa: 'ordinaria', 'straordinaria', 'riscaldamento', 'ascensore' (funzionamento e manutenzione ordinaria), 'ascensore_straordinaria' (manutenzione straordinaria o sostituzione), 'portineria'
        piano: Piano dell'unità immobiliare (rilevante solo per ascensore; 0 = piano terra)
        immobile_locato: True se l'immobile è concesso in locazione (abilita ripartizione proprietario/inquilino)
        piani_edificio: Ascensore: numero di piani dell'edificio (una unita' per piano, dal terra al piano indicato); alternativa a somma_altezze_edificio
        somma_altezze_edificio: Ascensore: somma dei coefficienti di altezza di tutte le unita' servite (piano terra = 0,5); se indicata prevale su piani_edificio
    """
    tipo = tipo_spesa.lower()
    tipi = ("ordinaria", "straordinaria", "riscaldamento", "ascensore", "ascensore_straordinaria", "portineria")
    if tipo not in tipi:
        return {"errore": "tipo_spesa deve essere: " + ", ".join(tipi)}
    # Millesimi are shares of a total of 1000 (art. 1123 c.c.): a share above the whole expense is impossible.
    if millesimi_proprietario < 0 or millesimi_proprietario > 1000:
        return {"errore": "millesimi_proprietario deve essere compreso tra 0 e 1000 (i millesimi sono quote di 1000)"}

    ascensore = tipo in ("ascensore", "ascensore_straordinaria")
    ipotesi = None
    if ascensore:
        # Art. 1124 c.c.: 50% by value (millesimi) + 50% in proportion to the floor height
        quota_millesimi = importo_totale * 0.5 * (millesimi_proprietario / 1000)
        coeff_piano = max(piano, 0.5)  # ground floor = 0.5
        if somma_altezze_edificio is not None:
            if somma_altezze_edificio < coeff_piano:
                return {"errore": "somma_altezze_edificio non puo' essere inferiore all'altezza del piano indicato"}
            totale_altezze = somma_altezze_edificio
        else:
            n = piani_edificio if piani_edificio is not None else max(10, piano)
            if n < piano:
                return {"errore": "piani_edificio non puo' essere inferiore al piano indicato"}
            totale_altezze = 0.5 + n * (n + 1) / 2  # one unit per floor: 0.5 + 1 + ... + n
            if piani_edificio is None:
                ipotesi = f"edificio ipotizzato di {n} piani, un'unita' per piano"
        quota_piano = importo_totale * 0.5 * (coeff_piano / totale_altezze)
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
    if ipotesi:
        result["ipotesi_altezze"] = ipotesi

    if immobile_locato:
        # Art. 9 L. 392/1978
        if tipo in ("ordinaria", "riscaldamento", "ascensore"):
            quota_inquilino = quota_proprietario_tot
            quota_proprietario = 0.0
            nota = "Spesa a carico del conduttore (art. 9 co. 1 L. 392/1978: servizi comuni, riscaldamento, funzionamento e manutenzione ordinaria dell'ascensore)"
        elif tipo == "portineria":
            quota_inquilino = round(quota_proprietario_tot * 0.9, 2)
            quota_proprietario = round(quota_proprietario_tot - quota_inquilino, 2)
            nota = "Portineria: 90% al conduttore, salvo patto per una misura inferiore (art. 9 co. 2 L. 392/1978)"
        else:  # straordinaria, ascensore_straordinaria
            quota_inquilino = 0.0
            quota_proprietario = quota_proprietario_tot
            nota = "Spesa straordinaria: interamente a carico del proprietario"

        result["ripartizione_locazione"] = {
            "quota_proprietario": quota_proprietario,
            "quota_inquilino": quota_inquilino,
            "nota": nota,
        }

    result["riferimento_normativo"] = "Art. 1123-1124 c.c.; L. 392/1978 art. 9 — Ripartizione spese condominiali"
    return result
