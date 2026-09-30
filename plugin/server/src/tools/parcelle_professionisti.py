"""Calcolo parcelle e fatture per professionisti non avvocati: CTU/periti (DPR 115/2002),
mediazione civile (DM 150/2023), Enasarco, curatore fallimentare (DM 30/2012)."""

import math
from decimal import ROUND_HALF_UP, Decimal

from src.server import mcp


def _d(valore) -> Decimal:
    """Exact Decimal from a float or string (via repr, so 1234.75 stays 1234.75)."""
    return valore if isinstance(valore, Decimal) else Decimal(repr(valore))


def _q2(valore) -> float:
    """Commercial rounding to the cent: a half cent goes up.

    Python's round() works on the binary float and sends 228.855 or 271.645 down, so the same
    half cent could round either way depending on its binary representation.
    """
    return float(_d(valore).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# Contributo previdenziale addebitato in fattura per tipo di professionista.
# Due regimi diversi: la rivalsa INPS 4% della gestione separata (professionisti senza cassa,
# art. 1 co. 212 L. 662/1996) e' parte del compenso e quindi soggetta a ritenuta d'acconto;
# il contributo integrativo delle casse di categoria (Inarcassa, CIPAG, CNPADC, ENPACL,
# ENPAP, ENPAM) e' soggetto a IVA ma NON a ritenuta d'acconto. Le aliquote delle casse sono
# quelle piu' diffuse e vanno verificate sul regolamento della cassa.
_CONTRIBUTO_PREVIDENZIALE = {
    "gestione_separata": {"cassa": "INPS Gestione separata (rivalsa)", "aliquota": 4.0, "ritenuta": True},
    "ingegnere": {"cassa": "Inarcassa (contributo integrativo)", "aliquota": 4.0, "ritenuta": False},
    "architetto": {"cassa": "Inarcassa (contributo integrativo)", "aliquota": 4.0, "ritenuta": False},
    "geometra": {"cassa": "CIPAG (contributo integrativo)", "aliquota": 4.0, "ritenuta": False},
    "commercialista": {"cassa": "CNPADC (contributo integrativo)", "aliquota": 4.0, "ritenuta": False},
    "consulente_lavoro": {"cassa": "ENPACL (contributo integrativo)", "aliquota": 4.0, "ritenuta": False},
    "psicologo": {"cassa": "ENPAP (contributo integrativo)", "aliquota": 5.0, "ritenuta": False},
    "medico": {"cassa": "ENPAM (contributo integrativo)", "aliquota": 4.0, "ritenuta": False},
}
#: Compatibilita' con i lettori esterni della vecchia mappa.
_RIVALSA_INPS = {k: v["aliquota"] for k, v in _CONTRIBUTO_PREVIDENZIALE.items()}

# Mediazione civile e commerciale, DM 24 ottobre 2023 n. 150 (in vigore dal 15 novembre 2023, abroga il
# DM 180/2010). Tabella A (art. 31 co. 1), organismi pubblici: (limite superiore dello scaglione,
# spese di mediazione minime, massime). Oltre 5.000.000: coefficienti 0,2% (minimo) e 0,3% (massimo)
# del valore della lite; valore indeterminabile: scaglione 50.000,01-150.000 (note in calce alla tabella).
_TABELLA_A_DM150 = [
    (1_000, 80, 160),
    (5_000, 160, 290),
    (10_000, 290, 440),
    (25_000, 440, 720),
    (50_000, 720, 1_200),
    (150_000, 1_200, 1_500),
    (250_000, 1_500, 2_500),
    (500_000, 2_500, 3_900),
    (1_500_000, 3_900, 4_600),
    (2_500_000, 4_600, 6_500),
    (5_000_000, 6_500, 10_000),
]
_TABELLA_A_OLTRE_MIN_PCT = Decimal("0.2")
_TABELLA_A_OLTRE_MAX_PCT = Decimal("0.3")
_IVA_MEDIAZIONE = Decimal(22)


def _mediazione_voci_fisse(valore: float) -> tuple[Decimal, Decimal]:
    """Spese di avvio (art. 28 co. 4) e spese di mediazione del primo incontro (art. 28 co. 5)."""
    if valore <= 1_000:
        return Decimal(40), Decimal(60)
    if valore <= 50_000:
        return Decimal(75), Decimal(120)
    return Decimal(110), Decimal(170)


def _mediazione_tabella_a(valore: float) -> tuple[Decimal, Decimal, str]:
    """(minimo, massimo, etichetta scaglione) della Tabella A per il valore della lite."""
    precedente = 0
    for limite, minimo, massimo in _TABELLA_A_DM150:
        if valore <= limite:
            if precedente == 0:
                etichetta = f"fino a €{limite:,.0f}".replace(",", ".")
            else:
                etichetta = f"da €{precedente + 1:,.0f} a €{limite:,.0f}".replace(",", ".")
            return Decimal(minimo), Decimal(massimo), etichetta
        precedente = limite
    v = _d(valore)
    return v * _TABELLA_A_OLTRE_MIN_PCT / 100, v * _TABELLA_A_OLTRE_MAX_PCT / 100, "oltre €5.000.000"


def _mediazione_calcolo(
    valore: float,
    esito: str,
    momento: str,
    obbligatoria: bool,
    importo_tabella: str,
) -> dict:
    """Costo per parte secondo gli artt. 28 e 30 DM 150/2023 (organismi pubblici, Tabella A)."""
    avvio, primo = _mediazione_voci_fisse(valore)
    minimo, massimo, etichetta = _mediazione_tabella_a(valore)
    tab = {"minimo": minimo, "medio": (minimo + massimo) / 2, "massimo": massimo}[importo_tabella]

    integrazione = Decimal(0)
    maggiorazione_pct = Decimal(0)
    if esito == "positivo" or momento == "incontri_successivi":
        # Art. 28 co. 7 e art. 30: Tabella A meno gli importi dell'art. 28 co. 5 (primo incontro);
        # maggiorazione 10% se l'accordo e' al primo incontro (co. 1), 25% se dopo (co. 2);
        # nessuna maggiorazione se le parti proseguono e non si accordano (co. 3).
        integrazione = tab - primo
        if esito == "positivo":
            maggiorazione_pct = Decimal(10) if momento == "primo_incontro" else Decimal(25)
    maggiorazione = integrazione * maggiorazione_pct / 100

    riduzione = Decimal(4) / 5 if obbligatoria else Decimal(1)  # art. 28 co. 8, art. 30 co. 4: meno un quinto
    v_avvio = avvio * riduzione
    v_primo = primo * riduzione
    v_integrazione = (integrazione + maggiorazione) * riduzione
    imponibile = v_avvio + v_primo + v_integrazione
    iva = imponibile * _IVA_MEDIAZIONE / 100
    imponibile_q = _q2(imponibile)
    iva_q = _q2(iva)
    return {
        "scaglione": etichetta,
        "tabella_a": {
            "minimo": _q2(minimo), "medio": _q2((minimo + massimo) / 2), "massimo": _q2(massimo),
            "usato": importo_tabella,
        },
        "voci": {
            "spese_avvio": _q2(v_avvio),
            "spese_mediazione_primo_incontro": _q2(v_primo),
            "spese_mediazione_ulteriori": _q2(v_integrazione),
            "di_cui_maggiorazione": _q2(maggiorazione * riduzione),
        },
        "maggiorazione_pct": float(maggiorazione_pct),
        "indennita_per_parte": imponibile_q,
        "iva_22_per_parte": iva_q,
        "totale_per_parte": _q2(_d(imponibile_q) + _d(iva_q)),
    }


def _mediazione_valida(valore_controversia, importo_tabella, momento, esito=None):
    if esito is not None and esito not in ("positivo", "negativo"):
        return "Esito deve essere 'positivo' o 'negativo'"
    if valore_controversia <= 0:
        return "Valore controversia deve essere positivo"
    if importo_tabella not in ("minimo", "medio", "massimo"):
        return "importo_tabella deve essere 'minimo', 'medio' o 'massimo'"
    if momento not in ("primo_incontro", "incontri_successivi"):
        return "momento deve essere 'primo_incontro' o 'incontri_successivi'"
    return None


# Compensi CTU: DM 30 maggio 2002 (GU 5/8/2002 n. 182), tabelle allegate. Ogni riga e'
# (limite superiore dello scaglione, percentuale minima, percentuale massima); le percentuali si
# applicano per scaglioni alla sola parte di valore compresa nello scaglione.
_CTU_MINIMO = 145.12  # "in ogni caso dovuto un compenso non inferiore a 145,12" (artt. 2, 3, 11, 13)
_CTU_VACAZIONE = 14.68  # art. 1 DM 30/5/2002; Corte cost. 16/2025: uguale per tutte le vacazioni
_CTU_TETTO_VACAZIONI_GIORNO = 4  # art. 4 c. 5 L. 319/1980
_CTU_ART2 = [  # tabella art. 2: materia amministrativa, contabile e fiscale
    (5_164.57, 4.6896, 9.3951),
    (10_329.14, 3.7580, 7.5160),
    (25_822.84, 2.8106, 5.6370),
    (51_645.69, 2.3527, 4.6896),
    (103_291.38, 1.8790, 3.7580),
    (258_228.45, 0.9316, 1.8790),
    (516_456.90, 0.4737, 0.9474),
]
_CTU_ART11 = [  # tabella art. 11: costruzioni edilizie, impianti, opere e simili
    (5_164.57, 6.5686, 13.1531),
    (10_329.14, 4.6896, 9.3951),
    (25_822.84, 3.7580, 7.5160),
    (51_645.69, 2.8106, 5.6370),
    (103_291.38, 1.8790, 3.7580),
    (258_228.45, 0.9316, 1.8790),
    (516_456.90, 0.2353, 0.4705),
]
_CTU_ART13 = [  # tabella art. 13: estimo
    (5_164.57, 1.0264, 2.0685),
    (10_329.14, 0.9316, 1.8790),
    (25_822.84, 0.8369, 1.6895),
    (51_645.69, 0.5684, 1.1211),
    (103_291.38, 0.3790, 0.7579),
    (258_228.45, 0.2842, 0.5684),
    (516_456.90, 0.0474, 0.0947),
]
# tipo_incarico -> (articolo del DM, tabella, fattore di riduzione, minimo, descrizione).
# L'abbinamento tra tipo di incarico e articolo e' una convenzione del tool: il decreto e' per
# materie, non per tipo di causa (l'ATP non ha un articolo proprio: si applica l'art. 11).
_COMPENSI_CTU = {
    "perizia_immobiliare": {"art": 13, "tabella": _CTU_ART13, "fattore": 1.0, "descrizione": "Perizia estimativa immobiliare (art. 13, estimo)"},
    "perizia_contabile": {"art": 2, "tabella": _CTU_ART2, "fattore": 1.0, "descrizione": "Perizia contabile, amministrativa e fiscale (art. 2)"},
    "perizia_medica": {"art": 21, "tabella": None, "fisso": (48.03, 290.77), "descrizione": "Consulenza tecnica medico-legale, accertamenti medici sulla persona (art. 21: onorario da 48,03 a 290,77 euro)"},
    "stima_danni": {"art": 3, "tabella": _CTU_ART2, "fattore": 0.5, "descrizione": "Valutazione di aziende e diritti al risarcimento di danni (art. 3: art. 2 ridotto alla meta')"},
    "accertamenti_tecnici": {"art": 11, "tabella": _CTU_ART11, "fattore": 1.0, "descrizione": "Accertamenti tecnici, costruzioni e impianti (art. 11; ATP ex art. 696 c.p.c.)"},
}


def _ctu_scaglioni(valore: float, tabella: list) -> tuple[float, float, bool]:
    """Somma per scaglioni (minimo, massimo); il terzo elemento dice se il valore supera l'ultimo scaglione."""
    totale_min = totale_max = 0.0
    precedente = 0.0
    for soglia, pct_min, pct_max in tabella:
        fascia = min(valore, soglia) - precedente
        if fascia <= 0:
            break
        totale_min += round(fascia * pct_min / 100, 2)
        totale_max += round(fascia * pct_max / 100, 2)
        precedente = soglia
    return round(totale_min, 2), round(totale_max, 2), valore > tabella[-1][0]


def _ctu_vacazioni(ore: float) -> float:
    """Vacazioni (2 ore) per il tempo impiegato: art. 4 c. 4 L. 319/1980, la vacazione non si divide che per meta'."""
    intere = int(ore // 2)
    resto = round(ore - 2 * intere, 6)
    if resto <= 0:
        return float(intere)
    # resto fino a 1 ora e un quarto: mezza vacazione; oltre, e' dovuta interamente
    return intere + (0.5 if resto <= 1.25 else 1.0)


@mcp.tool(tags={"parcelle_prof"})
def fattura_professionista(
    imponibile: float,
    tipo: str = "ingegnere",
    regime: str = "ordinario",
) -> dict:
    """Calcola fattura per professionista (non avvocato) con contributo previdenziale, IVA e ritenuta.
    Vigenza: DPR 633/1972 (IVA); DPR 600/1973 art. 25 (ritenuta d'acconto 20%); L. 190/2014
    (forfettario); art. 1 co. 212 L. 662/1996 (rivalsa INPS 4% della gestione separata, soggetta
    a ritenuta); leggi istitutive delle casse per il contributo integrativo (non soggetto a ritenuta).
    Precisione: ESATTO per IVA 22%, ritenuta 20% e rivalsa INPS 4%, con arrotondamento commerciale al
    centesimo (mezzo centesimo per eccesso); INDICATIVO per le aliquote del contributo integrativo delle
    casse di categoria (4-5%), da verificare sul regolamento della cassa, e per il forfettario, dove il
    bollo di 2 euro riaddebitato non entra nella base del contributo (la prassi lo include: da chiarire).

    Args:
        imponibile: Compenso professionale in euro (€, imponibile)
        tipo: Tipo professionista: 'gestione_separata' (senza cassa: rivalsa INPS 4%, soggetta a
              ritenuta), 'ingegnere', 'architetto', 'geometra', 'commercialista', 'consulente_lavoro',
              'psicologo', 'medico' (contributo integrativo della cassa, non soggetto a ritenuta)
        regime: Regime fiscale: 'ordinario' (IVA 22% + ritenuta 20%) o 'forfettario' (no IVA, no ritenuta, bollo se >77.47€)
    """
    if imponibile < 0:
        return {"errore": "Imponibile deve essere positivo"}
    if tipo not in _CONTRIBUTO_PREVIDENZIALE:
        return {"errore": f"Tipo professionista non valido. Valori: {list(_CONTRIBUTO_PREVIDENZIALE.keys())}"}
    if regime not in ("ordinario", "forfettario"):
        return {"errore": "Regime deve essere 'ordinario' o 'forfettario'"}

    previdenza = _CONTRIBUTO_PREVIDENZIALE[tipo]
    aliquota_rivalsa = previdenza["aliquota"]
    rivalsa = _q2(_d(imponibile) * _d(aliquota_rivalsa) / 100)
    base_imponibile_iva = _q2(_d(imponibile) + _d(rivalsa))
    # La rivalsa INPS e' compenso e sconta la ritenuta; il contributo integrativo di cassa no
    base_ritenuta = base_imponibile_iva if previdenza["ritenuta"] else imponibile

    voci = [
        {"voce": "Compenso professionale", "importo": imponibile},
        {"voce": f"{previdenza['cassa']} {aliquota_rivalsa}%", "importo": rivalsa},
    ]

    if regime == "ordinario":
        iva = _q2(_d(base_imponibile_iva) * 22 / 100)
        ritenuta = _q2(_d(base_ritenuta) * 20 / 100)
        totale = _q2(_d(base_imponibile_iva) + _d(iva) - _d(ritenuta))

        voci.append({"voce": "IVA 22%", "importo": iva})
        voci.append({"voce": "Ritenuta d'acconto 20% (-)", "importo": -ritenuta})

        return {
            "tipo_professionista": tipo,
            "cassa": previdenza["cassa"],
            "regime": regime,
            "imponibile": imponibile,
            "contributo_previdenziale": rivalsa,
            "rivalsa_inps": rivalsa,
            "base_imponibile_iva": base_imponibile_iva,
            "iva": iva,
            "base_ritenuta": base_ritenuta,
            "ritenuta_acconto": ritenuta,
            "totale_fattura": _q2(_d(base_imponibile_iva) + _d(iva)),
            "netto_a_pagare": totale,
            "voci": voci,
            "nota": (
                "Il committente versa la ritenuta d'acconto con F24 (codice tributo 1040). "
                + ("La rivalsa INPS concorre alla base della ritenuta." if previdenza["ritenuta"]
                   else "Il contributo integrativo di cassa e' escluso dalla base della ritenuta.")
            ),
        }
    else:
        # Forfettario: no IVA, no ritenuta, bollo €2 se importo > 77.47
        bollo = 2.0 if base_imponibile_iva > 77.47 else 0.0
        totale = _q2(_d(base_imponibile_iva) + _d(bollo))

        if bollo > 0:
            voci.append({"voce": "Imposta di bollo", "importo": bollo})

        return {
            "tipo_professionista": tipo,
            "cassa": previdenza["cassa"],
            "regime": regime,
            "imponibile": imponibile,
            "contributo_previdenziale": rivalsa,
            "rivalsa_inps": rivalsa,
            "base_imponibile": base_imponibile_iva,
            "iva": 0.0,
            "ritenuta_acconto": 0.0,
            "bollo": bollo,
            "totale_fattura": totale,
            "netto_a_pagare": totale,
            "voci": voci,
            "nota": "Regime forfettario: operazione senza IVA ex art. 1 co. 54-89 L. 190/2014, non soggetta a ritenuta",
        }

@mcp.tool(tags={"parcelle_prof"})
def compenso_ctu(
    tipo_incarico: str,
    valore_causa: float | None = None,
    ore_lavoro: float | None = None,
    giorni_lavorativi: int | None = None,
) -> dict:
    """Calcola il compenso del consulente tecnico d'ufficio (CTU) secondo il DM 30 maggio 2002.
    Vigenza: DPR 115/2002 artt. 49-52 — DM 30 maggio 2002 (GU 182/2002), tabelle allegate: art. 2
        (contabile), art. 3 (aziende e danni, meta' dell'art. 2), art. 11 (costruzioni), art. 13
        (estimo), art. 21 (accertamenti medici), minimo 145,12 euro; vacazioni: art. 4 L. 319/1980 e
        art. 1 DM 30/5/2002, 14,68 euro per ogni vacazione di due ore dopo Corte cost. 16/2025
        (le successive alla prima non possono essere inferiori alla prima). Il giudice liquida.
    Precisione: ESATTO sugli importi tabellari dell'articolo applicato (minimo e massimo del decreto)
        e sulle vacazioni; l'abbinamento tra tipo_incarico e articolo e' una convenzione (il decreto
        e' per materie), il giudice sceglie il valore tra minimo e massimo e puo' aumentare fino al
        doppio (art. 52 DPR 115/2002). Oltre 516.456,90 euro le tabelle non prevedono scaglioni: il
        calcolo si ferma a quel valore.

    Args:
        tipo_incarico: Tipo incarico: 'perizia_immobiliare' (art. 13), 'perizia_contabile' (art. 2), 'perizia_medica' (art. 21), 'stima_danni' (art. 3), 'accertamenti_tecnici' (art. 11)
        valore_causa: Valore del bene o della controversia in euro (€, opzionale, per l'onorario a percentuale; non rileva per la perizia medica, onorario fisso)
        ore_lavoro: Ore di lavoro effettive (opzionale, per l'onorario a vacazioni: 1 vacazione = 2 ore, frazione per meta')
        giorni_lavorativi: Giorni di lavoro dell'incarico (opzionale): applica il tetto di 4 vacazioni al giorno (art. 4 c. 5 L. 319/1980)
    """
    if tipo_incarico not in _COMPENSI_CTU:
        return {"errore": f"Tipo incarico non valido. Valori: {list(_COMPENSI_CTU.keys())}"}
    if valore_causa is None and ore_lavoro is None:
        return {"errore": "Specificare almeno valore_causa o ore_lavoro"}
    if (valore_causa is not None and valore_causa < 0) or (ore_lavoro is not None and ore_lavoro < 0):
        return {"errore": "Valore e ore non possono essere negativi"}
    if giorni_lavorativi is not None and giorni_lavorativi < 1:
        return {"errore": "giorni_lavorativi deve essere almeno 1"}

    info = _COMPENSI_CTU[tipo_incarico]
    risultato = {
        "tipo_incarico": tipo_incarico,
        "descrizione": info["descrizione"],
        "articolo_dm_30_5_2002": info["art"],
    }
    note = [
        "Il giudice liquida tra il minimo e il massimo del decreto (DPR 115/2002 artt. 49 e 52)",
        "Al compenso si aggiungono spese vive, IVA e cassa previdenziale se dovute",
        "L'abbinamento tra tipo di incarico e articolo del decreto e' una scelta del tool: verificare la materia",
    ]

    if info["tabella"] is None:
        # art. 21: onorario da 48,03 a 290,77 euro, non legato al valore
        c_min, c_max = info["fisso"]
        if valore_causa is not None:
            risultato["calcolo_a_percentuale"] = {
                "valore_causa": valore_causa,
                "compenso_min": c_min,
                "compenso_max": c_max,
                "nota": "Art. 21 DM 30/5/2002: onorario a forbice fissa, non dipende dal valore",
            }
    elif valore_causa is not None:
        s_min, s_max, oltre = _ctu_scaglioni(valore_causa, info["tabella"])
        f = info["fattore"]
        c_min = max(round(s_min * f, 2), _CTU_MINIMO)
        c_max = max(round(s_max * f, 2), _CTU_MINIMO)
        risultato["calcolo_a_percentuale"] = {
            "valore_causa": valore_causa,
            "compenso_min": c_min,
            "compenso_max": c_max,
            "minimo_di_legge": _CTU_MINIMO,
        }
        if oltre:
            risultato["calcolo_a_percentuale"]["oltre_ultimo_scaglione"] = True
            note.append("Valore oltre 516.456,90 euro: le tabelle non prevedono scaglioni ulteriori, calcolo fermato a quel valore")

    if ore_lavoro is not None:
        vacazioni = _ctu_vacazioni(ore_lavoro)
        tetto = None
        if giorni_lavorativi is not None:
            tetto = _CTU_TETTO_VACAZIONI_GIORNO * giorni_lavorativi
            vacazioni = min(vacazioni, float(tetto))
        importo = round(vacazioni * _CTU_VACAZIONE, 2)
        risultato["calcolo_orario"] = {
            "ore_lavoro": ore_lavoro,
            "vacazioni": vacazioni,
            "importo_per_vacazione": _CTU_VACAZIONE,
            "tetto_vacazioni": tetto,
            "compenso_min": importo,
            "compenso_max": importo,
        }
        note.append(
            "Vacazioni: 14,68 euro ciascuna (art. 4 L. 319/1980, art. 1 DM 30/5/2002; Corte cost. 16/2025 ha "
            "equiparato le successive alla prima; con la regola previgente le successive erano 8,15). "
            "Il termine breve dell'incarico puo' raddoppiare o aumentare la vacazione (art. 4 c. 3)"
        )

    risultato["note"] = note
    risultato["riferimento_normativo"] = "DPR 115/2002 — DM 30/05/2002 — L. 319/1980 art. 4"
    return risultato


@mcp.tool(tags={"parcelle_prof"})
def spese_mediazione(
    valore_controversia: float,
    esito: str = "positivo",
    momento: str = "primo_incontro",
    mediazione_obbligatoria: bool = False,
    importo_tabella: str = "medio",
) -> dict:
    """Calcola l'indennità di mediazione civile e commerciale per parte (organismi pubblici, Tabella A).
    Vigenza: DM 24 ottobre 2023 n. 150, artt. 28 (spese di avvio, spese di mediazione del primo incontro,
        riduzione di un quinto), 30 (ulteriori spese con maggiorazione 10% o 25%) e 31 con Tabella A;
        D.Lgs. 28/2010 (Riforma Cartabia). In vigore dal 15 novembre 2023, abroga il DM 180/2010.
    Precisione: INDICATIVO (la Tabella A fissa un minimo e un massimo per scaglione e l'organismo
        sceglie l'importo: il default 'medio' e' una convenzione; l'IVA 22% e' applicata a tutta l'indennita'
        come organismo soggetto a IVA; oltre 5.000.000 euro i coefficienti 0,2% e 0,3% sono letti sul valore
        della lite; restano fuori le maggiorazioni discrezionali dell'art. 31 co. 3 e 5 e le spese vive)

    Args:
        valore_controversia: Valore della controversia in euro (€); per il valore indeterminabile usare
            un valore dello scaglione 50.000,01-150.000 (Tabella A, nota)
        esito: 'positivo' (accordo raggiunto) o 'negativo' (mancato accordo)
        momento: 'primo_incontro' (accordo al primo incontro, oppure procedimento chiuso al primo incontro
            senza accordo) o 'incontri_successivi' (accordo dopo il primo incontro, oppure procedimento
            proseguito e chiuso senza accordo)
        mediazione_obbligatoria: True se la mediazione e' condizione di procedibilita' (art. 5 co. 1
            D.Lgs. 28/2010) o demandata dal giudice: importi ridotti di un quinto
        importo_tabella: Importo della Tabella A da usare: 'minimo', 'medio' (default) o 'massimo'
    """
    errore = _mediazione_valida(valore_controversia, importo_tabella, momento, esito)
    if errore:
        return {"errore": errore}

    c = _mediazione_calcolo(valore_controversia, esito, momento, mediazione_obbligatoria, importo_tabella)
    totale_per_parte = c["totale_per_parte"]

    if esito == "negativo" and momento == "primo_incontro":
        descrizione = "Mancato accordo al primo incontro: sono dovute solo spese di avvio e di mediazione del primo incontro (art. 28 co. 6)"
    elif esito == "negativo":
        descrizione = "Procedimento proseguito oltre il primo incontro e chiuso senza accordo: Tabella A senza maggiorazione (art. 30 co. 3)"
    elif momento == "primo_incontro":
        descrizione = "Accordo al primo incontro: Tabella A meno primo incontro, con maggiorazione del 10% (art. 30 co. 1)"
    else:
        descrizione = "Accordo dopo il primo incontro: Tabella A meno primo incontro, con maggiorazione del 25% (art. 30 co. 2)"

    risultato = {
        "valore_controversia": valore_controversia,
        "esito": esito,
        "momento": momento,
        "mediazione_obbligatoria": mediazione_obbligatoria,
        "scaglione": c["scaglione"],
        "descrizione_caso": descrizione,
        "tabella_a": c["tabella_a"],
        "dettaglio_per_parte": c["voci"],
        "maggiorazione_pct": c["maggiorazione_pct"],
        "indennita_per_parte": c["indennita_per_parte"],
        "iva_22_per_parte": c["iva_22_per_parte"],
        "totale_per_parte": totale_per_parte,
        "totale_organismo_2_parti": round(totale_per_parte * 2, 2),
    }
    risultato["note"] = [
        "L'indennita' (art. 1 lett. o) comprende spese di avvio e spese di mediazione; le spese vive documentate sono dovute a parte (art. 28 co. 3)",
        "Importi per ciascuna parte che partecipa al procedimento, a ciascun organismo",
    ]
    risultato["agevolazioni"] = [
        "Credito d'imposta fino a €600 per ciascuna parte in caso di accordo (art. 20 D.Lgs. 28/2010)",
        "Esenzione imposta di registro fino a €100.000 per accordi di mediazione",
        "Gratuito patrocinio: le parti ammesse non pagano indennità",
    ]
    risultato["riferimento_normativo"] = "DM 150/2023 artt. 28, 30, 31 e Tabella A — D.Lgs. 28/2010 (Riforma Cartabia)"
    return risultato


@mcp.tool(tags={"parcelle_prof"})
def compenso_orario(
    tariffa_oraria: float,
    ore: int,
    minuti: int = 0,
    arrotondamento: str = "mezz_ora",
) -> dict:
    """Calcola compenso professionale a ore con arrotondamento per eccesso all'unità scelta.
    Precisione: ESATTO (dato un importo orario e un tempo, il calcolo è matematicamente preciso).

    Args:
        tariffa_oraria: Tariffa oraria in euro (€/ora)
        ore: Numero di ore lavorate (intero non negativo)
        minuti: Minuti aggiuntivi (0-59)
        arrotondamento: Tipo arrotondamento per eccesso: 'quarto_ora' (15 min), 'mezz_ora' (30 min), 'ora' (60 min)
    """
    if arrotondamento not in ("quarto_ora", "mezz_ora", "ora"):
        return {"errore": "Arrotondamento deve essere 'quarto_ora', 'mezz_ora' o 'ora'"}
    if not 0 <= minuti <= 59:
        return {"errore": "Minuti deve essere tra 0 e 59"}
    if ore < 0:
        return {"errore": "Ore deve essere un intero non negativo"}

    totale_minuti = ore * 60 + minuti

    unita = {"quarto_ora": 15, "mezz_ora": 30, "ora": 60}[arrotondamento]
    # Round up to next unit
    minuti_arrotondati = math.ceil(totale_minuti / unita) * unita
    ore_arrotondate = minuti_arrotondati / 60

    compenso = round(tariffa_oraria * ore_arrotondate, 2)

    return {
        "tariffa_oraria": tariffa_oraria,
        "tempo_effettivo": f"{ore}h {minuti}min",
        "tempo_effettivo_minuti": totale_minuti,
        "arrotondamento": arrotondamento,
        "tempo_arrotondato": f"{int(minuti_arrotondati // 60)}h {int(minuti_arrotondati % 60)}min",
        "tempo_arrotondato_ore": ore_arrotondate,
        "compenso": compenso,
        "nota": f"Arrotondamento per eccesso a {unita} minuti",
    }


@mcp.tool(tags={"parcelle_prof"})
def ritenuta_acconto(
    compenso_lordo: float,
    aliquota: float = 20.0,
) -> dict:
    """Calcola ritenuta d'acconto su compensi professionali e mostra i campi per la Certificazione Unica.
    Vigenza: Art. 25 DPR 600/1973.
    Precisione: ESATTO (calcolo matematico su aliquota fornita).

    Args:
        compenso_lordo: Compenso lordo in euro (€, base imponibile per la ritenuta)
        aliquota: Aliquota ritenuta in percentuale (default 20%; range tipico: 20.0-30.0)
    """
    if compenso_lordo < 0:
        return {"errore": "Compenso lordo deve essere positivo"}

    ritenuta = round(compenso_lordo * aliquota / 100, 2)
    netto = round(compenso_lordo - ritenuta, 2)

    return {
        "compenso_lordo": compenso_lordo,
        "aliquota_ritenuta_pct": aliquota,
        "ritenuta": ritenuta,
        "netto_percepito": netto,
        "certificazione_unica": {
            "punto_4_compensi": compenso_lordo,
            "punto_8_ritenute": ritenuta,
            "punto_9_netto": netto,
            "codice_tributo_f24": "1040",
            "periodo_versamento": "Entro il 16 del mese successivo al pagamento",
        },
        "nota": (
            "Il committente (sostituto d'imposta) trattiene la ritenuta e la versa con F24. "
            "Rilascia la CU entro il 16/03 dell'anno successivo."
        ),
        "riferimento_normativo": "Art. 25 DPR 600/1973",
    }


# Compenso curatore fallimentare, DM 25 gennaio 2012 n. 30, art. 1 (testo vigente):
# (limite superiore dello scaglione, percentuale minima, percentuale massima) sull'attivo
# realizzato; ogni aliquota si applica alla sola parte eccedente il limite precedente.
_SCAGLIONI_CURATORE_ATTIVO = [
    (16_227.08, 12.0, 14.0),      # c. 1 lett. a
    (24_340.62, 10.0, 12.0),      # lett. b
    (40_567.68, 8.5, 9.5),        # lett. c
    (81_135.38, 7.0, 8.0),        # lett. d
    (405_676.89, 5.5, 6.5),       # lett. e
    (811_353.79, 4.0, 5.0),       # lett. f
    (2_434_061.37, 0.90, 1.80),   # lett. g
    (float("inf"), 0.45, 0.90),   # lett. h
]
# art. 1 c. 2: compenso supplementare sul passivo accertato
_SCAGLIONI_CURATORE_PASSIVO = [
    (81_131.38, 0.19, 0.94),
    (float("inf"), 0.06, 0.46),
]
_CURATORE_MIN = 811.35  # art. 4 c. 1: compenso complessivo non inferiore a 811,35 euro


def _curatore_scaglioni(importo: float, scaglioni: list) -> list:
    dettaglio = []
    precedente = 0.0
    for soglia, pct_min, pct_max in scaglioni:
        fascia = min(importo, soglia) - precedente
        if fascia <= 0:
            break
        c_min = round(fascia * pct_min / 100, 2)
        c_max = round(fascia * pct_max / 100, 2)
        dettaglio.append({
            "fascia": f"€{precedente:,.2f} - €{min(soglia, importo):,.2f}",
            "percentuale_min": pct_min,
            "percentuale_max": pct_max,
            "percentuale": round((pct_min + pct_max) / 2, 4),
            "base": round(fascia, 2),
            "compenso_min": c_min,
            # midpoint of the rounded bracket extremes, half-up to the cent
            "compenso": float(
                ((Decimal(str(c_min)) + Decimal(str(c_max))) / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            ),
            "compenso_max": c_max,
        })
        precedente = soglia
    return dettaglio


@mcp.tool(tags={"parcelle_prof"})
def compenso_curatore_fallimentare(
    attivo_realizzato: float,
    passivo_accertato: float,
) -> dict:
    """Calcola compenso del curatore fallimentare (forbice minimo-massimo e valore medio).
    Vigenza: DM 25 gennaio 2012 n. 30, art. 1 (percentuali sull'attivo realizzato, da 12-14% fino a
        16.227,08 euro a 0,45-0,90% oltre 2.434.061,37 euro; compenso supplementare sul passivo
        accertato 0,19-0,94% sui primi 81.131,38 euro e 0,06-0,46% oltre) e art. 4 (compenso non
        inferiore a 811,35 euro; spese generali 5%), testo vigente al 2026-09-29. Restano esclusi il
        compenso per l'esercizio provvisorio (art. 3) e le spese vive. L'art. 137 CCII rinvia a un
        nuovo decreto per le liquidazioni delle procedure di liquidazione giudiziale.
    Precisione: ESATTO sui limiti minimo e massimo del decreto; il tribunale liquida in concreto
        dentro la forbice (art. 39 l. fall.), quindi il totale medio (`totale_compenso`, media
        aritmetica di ogni scaglione) e' una convenzione di lavoro, non una liquidazione.

    Args:
        attivo_realizzato: Attivo realizzato dalla procedura in euro (€)
        passivo_accertato: Passivo accertato in euro (€, compenso supplementare art. 1 c. 2)
    """
    if attivo_realizzato < 0 or passivo_accertato < 0:
        return {"errore": "Attivo e passivo non possono essere negativi"}

    det_attivo = _curatore_scaglioni(attivo_realizzato, _SCAGLIONI_CURATORE_ATTIVO)
    det_passivo = _curatore_scaglioni(passivo_accertato, _SCAGLIONI_CURATORE_PASSIVO)

    def somma(chiave: str) -> tuple[float, float]:
        a = round(sum(d[chiave] for d in det_attivo), 2)
        p = round(sum(d[chiave] for d in det_passivo), 2)
        return a, p

    att_min, pas_min = somma("compenso_min")
    att_med, pas_med = somma("compenso")
    att_max, pas_max = somma("compenso_max")

    prima_min = round(att_min + pas_min, 2)
    prima_med = round(att_med + pas_med, 2)
    prima_max = round(att_max + pas_max, 2)
    tot_min = max(prima_min, _CURATORE_MIN)
    tot_med = max(prima_med, _CURATORE_MIN)
    tot_max = max(prima_max, _CURATORE_MIN)

    note = [
        "Compenso sull'attivo: percentuali per scaglione, DM 30/2012 art. 1 c. 1",
        "Compenso supplementare sul passivo: DM 30/2012 art. 1 c. 2",
        f"Minimo complessivo: €{_CURATORE_MIN:,.2f} (art. 4 c. 1); nessun massimo complessivo nel decreto",
        "Spese generali del 5% sul compenso (art. 4 c. 2), spese vive documentate, IVA e CPA se dovute",
    ]
    if tot_med != prima_med:
        note.append(
            f"Totale portato al minimo di legge: somma dei parziali €{prima_med:,.2f}, "
            f"differenza dai parziali €{round(tot_med - prima_med, 2):,.2f}"
        )

    return {
        "attivo_realizzato": attivo_realizzato,
        "passivo_accertato": passivo_accertato,
        "compenso_su_attivo": att_med,
        "dettaglio_attivo": det_attivo,
        "compenso_su_passivo": pas_med,
        "dettaglio_passivo": det_passivo,
        "totale_prima_dei_limiti": prima_med,
        "totale_compenso": tot_med,
        "totale_compenso_min": tot_min,
        "totale_compenso_max": tot_max,
        "spese_generali_5pct": round(tot_med * 5 / 100, 2),
        "minimo": _CURATORE_MIN,
        "note": note,
        "riferimento_normativo": "DM 25 gennaio 2012 n. 30, artt. 1 e 4 — Compensi curatore fallimentare",
    }


@mcp.tool(tags={"parcelle_prof"})
def compenso_delegati_vendite(
    prezzo_aggiudicazione: float,
    tipo_vendita: str = "immobili",
) -> dict:
    """Calcola compenso del professionista delegato alle vendite giudiziarie (DM 227/2015).
    Vigenza: DM 15 ottobre 2015 n. 227, art. 2 (espropriazione immobiliare: 1.000 / 1.500 / 2.000
        euro per ciascuna delle 4 fasi secondo lo scaglione di prezzo; spese generali 10% c. 4;
        tetto del 40% c. 5; meta' della fase di trasferimento a carico dell'aggiudicatario c. 7) e
        art. 3 (beni mobili iscritti nei pubblici registri: 200/250/200/250 euro per fase,
        raddoppiati tra 25.000 e 40.000 euro, oltre 40.000 euro si applica l'art. 2 c. 1 lett. a;
        tetto del 30%), testo vigente al 2026-09-29.
    Precisione: ESATTO sull'importo tabellare, sulle spese generali e sul tetto (riduzione
        proporzionale di compenso e spese, convenzione); l'aumento fino al 60% o la riduzione fino
        al 25% per complessita' (art. 2 c. 3), la liquidazione per piu' lotti o debitori (c. 2) e
        le spese documentate sono discrezionali del giudice dell'esecuzione e non sono calcolati.

    Args:
        prezzo_aggiudicazione: Prezzo di aggiudicazione o valore di assegnazione in euro (€)
        tipo_vendita: 'immobili' (art. 2, default) o 'mobili_registrati' (art. 3, beni mobili iscritti in pubblici registri)
    """
    if tipo_vendita not in ("immobili", "mobili_registrati"):
        return {"errore": "tipo_vendita deve essere 'immobili' o 'mobili_registrati'"}
    if prezzo_aggiudicazione <= 0:
        return {"errore": "Prezzo aggiudicazione deve essere positivo"}

    P = prezzo_aggiudicazione
    if tipo_vendita == "mobili_registrati" and P <= 40_000:
        # art. 3 c. 1: 200 + 250 + 200 + 250; c. 2: doppio se 25.000 < P < 40.000.
        # P = 40.000 esatto: ne' "inferiore a 40.000" (c. 2) ne' "eccede 40.000" (c. 4);
        # si applica la misura base del c. 1 (convenzione documentata).
        fasi = [200.0, 250.0, 200.0, 250.0]
        if 25_000 < P < 40_000:
            fasi = [2 * f for f in fasi]
        articolo = "art. 3 DM 227/2015"
        tetto_pct = 30
    else:
        if P <= 100_000:
            per_fase = 1_000.0
        elif P <= 500_000:
            per_fase = 1_500.0
        else:
            per_fase = 2_000.0
        fasi = [per_fase] * 4
        articolo = (
            "art. 3 c. 4 + art. 2 c. 1 lett. a DM 227/2015"
            if tipo_vendita == "mobili_registrati"
            else "art. 2 c. 1 DM 227/2015"
        )
        tetto_pct = 40

    compenso_tabellare = round(sum(fasi), 2)
    spese_generali_tab = round(compenso_tabellare * 10 / 100, 2)
    tetto = round(P * tetto_pct / 100, 2)
    fattore = 1.0
    limite_applicato = False
    compenso = compenso_tabellare
    spese_generali = spese_generali_tab
    if compenso_tabellare + spese_generali_tab > tetto:
        # riduzione proporzionale: compenso + 10% di compenso = tetto
        limite_applicato = True
        compenso = round(tetto / 1.10, 2)
        spese_generali = round(tetto - compenso, 2)
        fattore = compenso / compenso_tabellare

    quota_aggiudicatario = round(fasi[2] * fattore / 2 * 1.10, 2)
    nomi_fasi = [
        "conferimento incarico e avviso di vendita",
        "vendita fino all'aggiudicazione",
        "trasferimento della proprieta'",
        "distribuzione",
    ]
    note = [
        f"Compenso tabellare per le 4 fasi: {compenso_tabellare:,.2f} euro ({articolo})",
        "Spese generali: 10% del compenso (art. 2 c. 4), oltre alle spese documentate",
        "Il giudice dell'esecuzione puo' aumentare il compenso fino al 60% o ridurlo fino al 25% (art. 2 c. 3, non applicato)",
        "Meta' del compenso della fase di trasferimento, con le relative spese generali, e' a carico dell'aggiudicatario (art. 2 c. 7)",
        "Al compenso si aggiungono IVA e CPA se dovute",
    ]
    if limite_applicato:
        note.append(
            f"Tetto del {tetto_pct}% del prezzo ({tetto:,.2f} euro) applicato a compenso e spese generali insieme, "
            "con riduzione proporzionale di entrambi"
        )

    return {
        "prezzo_aggiudicazione": prezzo_aggiudicazione,
        "tipo_vendita": tipo_vendita,
        "compenso": compenso,
        "compenso_tabellare": compenso_tabellare,
        "spese_generali_10pct": spese_generali,
        "totale_compenso_e_spese_generali": round(compenso + spese_generali, 2),
        "limite_applicato": limite_applicato,
        "tetto_pct": tetto_pct,
        "tetto_importo": tetto,
        "quota_a_carico_aggiudicatario": quota_aggiudicatario,
        "percentuale_effettiva": round(compenso / P * 100, 2),
        "fasi": [{"fase": n, "compenso_tabellare": f} for n, f in zip(nomi_fasi, fasi)],
        "note": note,
        "riferimento_normativo": f"DM 227/2015 — {articolo}",
    }


_MEDIAZIONE_FAM_BASE = 40.0  # art. 8 c. 4 DM 151/2023: euro per incontro, a carico di ciascun mediando
_MEDIAZIONE_FAM_COEFF = {"bassa": 1.0, "media": 1.5, "alta": 2.0}  # art. 8 c. 5 lett. a, b, c


@mcp.tool(tags={"parcelle_prof"})
def compenso_mediatore_familiare(
    n_incontri: int,
    tariffa_incontro: float | None = None,
    complessita: str = "media",
    n_mediandi: int = 2,
) -> dict:
    """Calcola compenso del mediatore familiare per percorso di mediazione.
    In pendenza di procedura giudiziaria l'informativa preliminare e' gratuita (art. 6 c. 10 lett. a
    DM 151/2023); ogni incontro successivo e' a pagamento secondo i parametri del decreto.
    Vigenza: DM 27 ottobre 2023 n. 151, art. 8 (c. 4: 40 euro per incontro a carico di ciascun
        mediando; c. 5: moltiplicatore 1 / 1,5 / 2 per complessita' bassa / media / alta; c. 6:
        spese forfettarie 21% sul compenso, che il compenso `compenso_totale` non comprende, c. 1),
        testo vigente al 2026-09-29. Esclusi IVA, cassa e spese documentate.
    Precisione: ESATTO con i parametri del decreto (`tariffa_incontro` omessa); INDICATIVO se si
        indica una `tariffa_incontro` libera, che sostituisce il parametro del decreto. La
        complessita' del caso e' scelta dal professionista (non desumibile dai dati).

    Args:
        n_incontri: Numero totale di incontri comprensivo del primo informativo gratuito (minimo 1)
        tariffa_incontro: Tariffa libera per incontro a pagamento riferita a tutti i mediandi (€). Se omessa
            si applica il decreto: 40 euro x coefficiente di complessita' x numero di mediandi
        complessita: 'bassa' (x1), 'media' (x1,5, default) o 'alta' (x2), art. 8 c. 5 DM 151/2023
        n_mediandi: Numero di mediandi che pagano il compenso (default 2)
    """
    if n_incontri < 1:
        return {"errore": "Numero incontri deve essere almeno 1"}
    if complessita not in _MEDIAZIONE_FAM_COEFF:
        return {"errore": f"Complessita non valida. Valori: {list(_MEDIAZIONE_FAM_COEFF.keys())}"}
    if n_mediandi < 1:
        return {"errore": "Numero mediandi deve essere almeno 1"}
    if tariffa_incontro is not None and tariffa_incontro < 0:
        return {"errore": "Tariffa per incontro non puo' essere negativa"}

    coeff = _MEDIAZIONE_FAM_COEFF[complessita]
    per_mediando = round(_MEDIAZIONE_FAM_BASE * coeff, 2)
    if tariffa_incontro is None:
        tariffa_applicata = round(per_mediando * n_mediandi, 2)
        fonte_tariffa = "DM 151/2023 art. 8 c. 4-5"
    else:
        tariffa_applicata = tariffa_incontro
        fonte_tariffa = "tariffa libera indicata dall'utente"

    incontri_a_pagamento = max(0, n_incontri - 1)
    compenso = round(incontri_a_pagamento * tariffa_applicata, 2)
    spese_forfettarie = round(compenso * 21 / 100, 2)

    return {
        "n_incontri_totali": n_incontri,
        "primo_incontro": "gratuito (informativo)",
        "incontri_a_pagamento": incontri_a_pagamento,
        "complessita": complessita,
        "n_mediandi": n_mediandi,
        "importo_per_incontro_e_per_mediando": per_mediando,
        "tariffa_incontro": tariffa_applicata,
        "fonte_tariffa": fonte_tariffa,
        "compenso_totale": compenso,
        "compenso_per_mediando": round(compenso / n_mediandi, 2),
        "spese_forfettarie_21pct": spese_forfettarie,
        "totale_imponibile": round(compenso + spese_forfettarie, 2),
        "note": [
            "Il primo incontro informativo e' gratuito in pendenza di procedura giudiziaria (art. 6 c. 10 lett. a DM 151/2023)",
            "Compenso: 40 euro per incontro e per mediando x 1 / 1,5 / 2 secondo la complessita' (art. 8 c. 4-5)",
            "Le spese forfettarie del 21% sono dovute in aggiunta al compenso (art. 8 c. 6); il compenso non le comprende (c. 1)",
            "Oneri e contributi (IVA, cassa) restano esclusi; percorso tipico 8-12 incontri",
        ],
        "riferimento_normativo": "DM 27 ottobre 2023 n. 151, art. 8",
    }


# Enasarco: Regolamento delle attivita' istituzionali (RAI), art. 4 (aliquota) e art. 5 (massimali).
# Aliquota contributiva complessiva per anno di decorrenza (art. 4 co. 2 RAI, delibera CdA 73/2012);
# dal 2020 il 17%, meta' a carico dell'agente e meta' del preponente (art. 4 co. 1).
_ENASARCO_ALIQUOTE = {
    2012: 13.50, 2013: 13.75, 2014: 14.20, 2015: 14.65, 2016: 15.10,
    2017: 15.55, 2018: 16.00, 2019: 16.50, 2020: 17.00,
}
_ENASARCO_ALIQUOTA_A_REGIME = 17.0
_ENASARCO_ANNO_MIN = 2012
# Massimale provvigionale annuo e minimale contributivo annuo, per rapporto di agenzia (art. 5 RAI,
# rivalutati ogni anno dalla Fondazione con l'indice ISTAT). Fonte: enasarco.it, "Minimali e
# massimali 2026" (effetto dal 1 gennaio 2026). Gli altri anni non sono tabulati.
_ENASARCO_LIMITI = {
    2026: {
        "monocommittente": {"massimale": 45_717.0, "minimale": 1_026.0},
        "pluricommittente": {"massimale": 30_478.0, "minimale": 515.0},
    },
}


@mcp.tool(tags={"parcelle_prof"})
def fattura_enasarco(
    provvigioni: float,
    tipo_agente: str = "monocommittente",
    anno: int = 2026,
    provvigioni_gia_fatturate_anno: float = 0.0,
    agente_con_collaboratori: bool = False,
) -> dict:
    """Calcola struttura fattura agente di commercio con contributo Enasarco, IVA e ritenuta.
    Vigenza: art. 1742 c.c. (contratto di agenzia); Regolamento delle attivita' istituzionali Enasarco,
        art. 4 (aliquota 17% dal 2020, 8,5% agente + 8,5% preponente; anni 2012-2019 con la scala
        graduale del co. 2) e art. 5 (massimale provvigionale per rapporto di agenzia); art. 25-bis
        DPR 600/1973 (ritenuta IRPEF del primo scaglione, 23%, sul 50% delle provvigioni, sul 20% se
        l'agente dichiara di avvalersi in via continuativa di dipendenti o terzi). Massimali e
        minimali tabulati per il 2026.
    Precisione: ESATTO per aliquota, massimale 2026 e ritenuta; INDICATIVO per gli anni senza
        massimale tabulato (contributo calcolato su tutte le provvigioni) e per l'aliquota della
        ritenuta, che segue il primo scaglione IRPEF (23% dal 2007, art. 11 TUIR). Il minimale
        contributivo annuo e' esposto nella risposta ma non e' applicato al calcolo della fattura.

    Args:
        provvigioni: Importo provvigioni in euro (€, imponibile) della fattura
        tipo_agente: Tipo mandato: 'monocommittente' o 'pluricommittente' (cambia massimale e minimale)
        anno: Anno di competenza delle provvigioni (dal 2012; determina l'aliquota Enasarco)
        provvigioni_gia_fatturate_anno: Provvigioni gia' fatturate nell'anno per lo stesso rapporto di
            agenzia (€): il massimale e' annuo e non frazionabile, quindi il contributo e' dovuto solo
            sulla parte che entra nel massimale residuo
        agente_con_collaboratori: True se l'agente ha dichiarato al preponente di avvalersi in via
            continuativa di dipendenti o terzi (ritenuta sul 20% invece che sul 50%)
    """
    if tipo_agente not in ("monocommittente", "pluricommittente"):
        return {"errore": f"Tipo agente non valido: {tipo_agente}. Usare: monocommittente, pluricommittente"}
    if provvigioni < 0:
        return {"errore": "Provvigioni deve essere positivo"}
    if provvigioni_gia_fatturate_anno < 0:
        return {"errore": "Provvigioni gia' fatturate nell'anno non puo' essere negativo"}
    if anno < _ENASARCO_ANNO_MIN:
        return {"errore": f"Anno non supportato: le aliquote tabulate partono dal {_ENASARCO_ANNO_MIN}"}

    aliquota = _ENASARCO_ALIQUOTE.get(anno, _ENASARCO_ALIQUOTA_A_REGIME)
    limiti = _ENASARCO_LIMITI.get(anno, {}).get(tipo_agente)

    prov = _d(provvigioni)
    if limiti is not None:
        residuo = max(_d(limiti["massimale"]) - _d(provvigioni_gia_fatturate_anno), Decimal(0))
        soggette = min(prov, residuo)
    else:
        soggette = prov
    oltre_massimale = prov - soggette

    contributo_totale = _q2(soggette * _d(aliquota) / 100)
    # Quota agente = meta' dell'aliquota (8,5% nel 2026) sull'imponibile contributivo
    quota_agente = _q2(soggette * _d(aliquota) / 200)
    quota_preponente = _q2(_d(contributo_totale) - _d(quota_agente))

    iva = _q2(prov * 22 / 100)
    pct_base = 20 if agente_con_collaboratori else 50
    base_ritenuta = prov * pct_base / 100
    ritenuta = _q2(base_ritenuta * 23 / 100)

    totale_fattura = _q2(prov + _d(iva))
    netto = _q2(_d(totale_fattura) - _d(ritenuta) - _d(quota_agente))

    contributo = {
        "aliquota_totale": aliquota,
        "aliquota_agente": aliquota / 2,
        "contributo_totale": contributo_totale,
        "quota_agente": quota_agente,
        "quota_preponente": quota_preponente,
        "provvigioni_soggette_a_contributo": _q2(soggette),
        "provvigioni_oltre_massimale": _q2(oltre_massimale),
    }
    if limiti is not None:
        contributo["minimale_annuo"] = limiti["minimale"]
        contributo["massimale_annuo"] = limiti["massimale"]
    else:
        contributo["nota_massimale"] = (
            f"Massimale e minimale non tabulati per il {anno}: contributo calcolato su tutte le provvigioni; "
            "verificare i limiti dell'anno sul sito Enasarco"
        )

    return {
        "provvigioni": provvigioni,
        "tipo_agente": tipo_agente,
        "anno": anno,
        "contributo_enasarco": contributo,
        "iva_22pct": iva,
        "ritenuta_acconto": {
            "base": _q2(base_ritenuta),
            "aliquota": 23.0,
            "importo": ritenuta,
            "nota": (
                f"23% sul {pct_base}% delle provvigioni (art. 25-bis DPR 600/1973"
                + (", co. 2: agente con dipendenti o terzi in via continuativa)" if agente_con_collaboratori else ")")
            ),
        },
        "totale_fattura": totale_fattura,
        "netto_a_pagare": netto,
        "nota": (
            f"Il preponente versa la propria quota Enasarco (€{quota_preponente}) "
            f"e trattiene dalla fattura la quota agente (€{quota_agente}) + ritenuta (€{ritenuta})"
        ),
        "riferimento_normativo": "Art. 1742 c.c. — Regolamento Enasarco (attivita' istituzionali) artt. 4-5 — Art. 25-bis DPR 600/1973",
    }


# Gestione separata INPS, lavoratori autonomi occasionali (art. 44 co. 2 DL 269/2003, conv. L. 326/2003).
# Circolare INPS n. 8 del 3 febbraio 2026, tipo rapporto 09 "Rapporti occasionali autonomi": 33,72%
# (33% IVS + 0,50% + 0,22%, senza la quota DIS-COLL dei collaboratori) per chi non ha altra copertura
# obbligatoria; 24% per pensionati o assicurati presso altra forma obbligatoria (art. 1 co. 79 L. 247/2007).
# La contribuzione e' dovuta solo sull'eccedenza dei compensi annui oltre 5.000 euro (art. 44 co. 2) ed
# e' a carico del prestatore per un terzo e del committente per due terzi (circolare 8/2026, par. 4.1).
_INPS_OCCASIONALI_ANNO = 2026
_INPS_OCCASIONALI_ALIQUOTA = 33.72
_INPS_OCCASIONALI_ALIQUOTA_ALTRA_COPERTURA = 24.0
_INPS_OCCASIONALI_FRANCHIGIA = 5_000.0
_INPS_QUOTA_PRESTATORE = Decimal(1) / Decimal(3)


def _eur_it(valore: float) -> str:
    """Italian money format: 1.234,56."""
    return f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@mcp.tool(tags={"parcelle_prof"})
def ricevuta_prestazione_occasionale(
    compenso_lordo: float,
    committente: str,
    prestatore: str,
    descrizione: str,
    compensi_occasionali_gia_percepiti_anno: float = 0.0,
    altra_previdenza_o_pensionato: bool = False,
    committente_sostituto_imposta: bool = True,
    anno: int = 2026,
) -> dict:
    """Genera testo ricevuta per prestazione occasionale con ritenuta d'acconto (20%), bollo se >€77,47 e quota INPS del prestatore oltre €5.000 annui.
    Vigenza: Art. 2222 c.c. — Art. 67 co. 1 lett. l) TUIR — Art. 25 DPR 600/1973 (ritenuta 20%);
        art. 44 co. 2 DL 269/2003 conv. L. 326/2003 (Gestione separata INPS oltre 5.000 euro annui, 1/3 a
        carico del prestatore) e circolare INPS 8/2026 (aliquota 2026: 33,72%, 24% con altra copertura).
    Precisione: ESATTO per ritenuta 20% e soglia del bollo (77,47 euro); ESATTO per la quota INPS solo per
        l'anno 2026 (aliquote tabulate) e senza il massimale annuo di 122.295 euro; per altri anni la quota
        INPS non e' calcolata.

    Args:
        compenso_lordo: Compenso lordo pattuito in euro (€)
        committente: Nome / ragione sociale del committente (sostituto d'imposta)
        prestatore: Nome e cognome del prestatore della prestazione
        descrizione: Descrizione sintetica della prestazione svolta
        compensi_occasionali_gia_percepiti_anno: Compensi da lavoro autonomo occasionale gia' percepiti
            nell'anno da tutti i committenti (€): la franchigia di 5.000 euro e' annua e cumulativa
        altra_previdenza_o_pensionato: True se il prestatore e' pensionato o assicurato presso altra forma
            obbligatoria (aliquota INPS 24% invece di 33,72%)
        committente_sostituto_imposta: False se il committente non e' sostituto d'imposta (nessuna ritenuta)
        anno: Anno dei compensi (la quota INPS e' calcolata per il 2026)
    """
    if compenso_lordo < 0:
        return {"errore": "Compenso lordo deve essere positivo"}
    if compensi_occasionali_gia_percepiti_anno < 0:
        return {"errore": "Compensi gia' percepiti nell'anno non puo' essere negativo"}

    lordo = _d(compenso_lordo)
    ritenuta = _q2(lordo * 20 / 100) if committente_sostituto_imposta else 0.0
    bollo = 2.0 if compenso_lordo > 77.47 else 0.0

    # Quota INPS del prestatore: solo sulla parte di compenso di questa ricevuta che supera i 5.000 euro
    # annui cumulati (art. 44 co. 2 DL 269/2003), un terzo dell'aliquota.
    inps = None
    if anno == _INPS_OCCASIONALI_ANNO:
        aliquota_inps = (
            _INPS_OCCASIONALI_ALIQUOTA_ALTRA_COPERTURA if altra_previdenza_o_pensionato else _INPS_OCCASIONALI_ALIQUOTA
        )
        franchigia = _d(_INPS_OCCASIONALI_FRANCHIGIA)
        prima = _d(compensi_occasionali_gia_percepiti_anno)
        eccedenza = max(prima + lordo - franchigia, Decimal(0)) - max(prima - franchigia, Decimal(0))
        contributo_totale = eccedenza * _d(aliquota_inps) / 100
        quota_prestatore = _q2(contributo_totale * _INPS_QUOTA_PRESTATORE)
        inps = {
            "aliquota": aliquota_inps,
            "franchigia_annua": _INPS_OCCASIONALI_FRANCHIGIA,
            "base_contributiva": _q2(eccedenza),
            "contributo_totale": _q2(contributo_totale),
            "quota_prestatore_1_3": quota_prestatore,
            "quota_committente_2_3": _q2(contributo_totale - _d(quota_prestatore)),
        }
    quota_inps = inps["quota_prestatore_1_3"] if inps else 0.0

    netto = _q2(lordo - _d(ritenuta) - _d(quota_inps))

    linee = [
        "RICEVUTA PER PRESTAZIONE OCCASIONALE",
        "Art. 2222 c.c. — Art. 67, comma 1, lett. l) TUIR",
        "",
        f"Prestatore: {prestatore}",
        f"Committente: {committente}",
        "",
        f"Descrizione: {descrizione}",
        "",
        f"  Compenso lordo: €{_eur_it(compenso_lordo)}",
    ]
    if committente_sostituto_imposta:
        linee.append(f"  Ritenuta d'acconto 20%: -€{_eur_it(ritenuta)}")
    if quota_inps:
        linee.append(f"  Contributo INPS Gestione separata a carico del prestatore (1/3): -€{_eur_it(quota_inps)}")
    linee.append(f"  Netto a pagare: €{_eur_it(netto)}")
    if bollo > 0:
        linee.append(f"  Imposta di bollo: €{_eur_it(bollo)} (importo > €77,47)")
    linee.append("")
    linee.append("Operazione fuori campo IVA ex art. 5 DPR 633/1972")

    note = [
        "Il committente versa la ritenuta con F24 (codice tributo 1040) entro il 16 del mese successivo",
        "Il prestatore dichiara il reddito nella dichiarazione dei redditi (quadro RL)",
        "Franchigia INPS: fino a €5.000 annui di compensi occasionali (somma di tutti i committenti) non c'e' "
        "obbligo contributivo; oltre, il contributo e' dovuto sulla sola eccedenza (art. 44 co. 2 DL 269/2003), "
        "1/3 a carico del prestatore e 2/3 del committente, che versa entro il 16 del mese successivo",
    ]
    if inps is None:
        note.append(
            f"Quota INPS non calcolata: le aliquote tabulate sono quelle del {_INPS_OCCASIONALI_ANNO}; "
            "verificare l'aliquota dell'anno sulla circolare INPS di inizio anno"
        )
    if not committente_sostituto_imposta:
        note.append("Committente non sostituto d'imposta: nessuna ritenuta, il prestatore assolve l'IRPEF in dichiarazione")

    calcoli = {
        "compenso_lordo": compenso_lordo,
        "ritenuta_acconto_20pct": ritenuta,
        "netto_a_pagare": netto,
        "bollo": bollo,
    }
    if inps is not None:
        calcoli["inps_gestione_separata"] = inps

    return {
        "testo_ricevuta": "\n".join(linee),
        "calcoli": calcoli,
        "committente": committente,
        "prestatore": prestatore,
        "descrizione": descrizione,
        "note": note,
        "riferimento_normativo": "Art. 2222 c.c. — Art. 67 co. 1 lett. l) TUIR — Art. 25 DPR 600/1973 — Art. 44 co. 2 DL 269/2003",
    }


@mcp.tool(tags={"parcelle_prof"})
def tariffe_mediazione(
    valore_controversia: float,
    mediazione_obbligatoria: bool = False,
    importo_tabella: str = "medio",
) -> dict:
    """Restituisce la Tabella A del DM 150/2023 e i costi per parte in tutti gli scenari di esito.
    A differenza di spese_mediazione, mostra insieme spese di avvio, spese del primo incontro, minimo/massimo
    della Tabella A e i quattro scenari (accordo o mancato accordo, al primo incontro o dopo).
    Vigenza: DM 24 ottobre 2023 n. 150, artt. 28, 30 e 31 con Tabella A; D.Lgs. 28/2010 (Riforma Cartabia).
    Precisione: INDICATIVO (la Tabella A fissa un minimo e un massimo per scaglione e l'organismo sceglie
        l'importo: il default 'medio' e' una convenzione; l'IVA 22% e' applicata a tutta l'indennita';
        oltre 5.000.000 euro i coefficienti 0,2% e 0,3% sono letti sul valore della lite; restano fuori le
        maggiorazioni discrezionali dell'art. 31 co. 3 e 5 e le spese vive)

    Args:
        valore_controversia: Valore della controversia in euro (€)
        mediazione_obbligatoria: True se condizione di procedibilita' o demandata dal giudice (meno un quinto)
        importo_tabella: Importo della Tabella A da usare: 'minimo', 'medio' (default) o 'massimo'
    """
    errore = _mediazione_valida(valore_controversia, importo_tabella, "primo_incontro")
    if errore:
        return {"errore": errore}

    def scenario(esito: str, momento: str) -> dict:
        c = _mediazione_calcolo(valore_controversia, esito, momento, mediazione_obbligatoria, importo_tabella)
        return {
            "indennita_per_parte": c["indennita_per_parte"],
            "iva_22pct": c["iva_22_per_parte"],
            "totale_per_parte": c["totale_per_parte"],
            "totale_2_parti": round(c["totale_per_parte"] * 2, 2),
            "dettaglio": c["voci"],
            "maggiorazione_pct": c["maggiorazione_pct"],
        }

    base = _mediazione_calcolo(valore_controversia, "negativo", "primo_incontro", mediazione_obbligatoria, importo_tabella)
    riduzione = Decimal(4) / 5 if mediazione_obbligatoria else Decimal(1)

    tabella = []
    precedente = 0
    for limite, minimo, massimo in _TABELLA_A_DM150:
        avvio, primo = _mediazione_voci_fisse(limite)
        tabella.append({
            "scaglione": (f"fino a €{limite:,.0f}" if precedente == 0 else f"da €{precedente + 1:,.0f} a €{limite:,.0f}").replace(",", "."),
            "spese_avvio": avvio, "spese_primo_incontro": primo,
            "tabella_a_minimo": minimo, "tabella_a_massimo": massimo, "tabella_a_medio": (minimo + massimo) / 2,
        })
        precedente = limite
    tabella.append({
        "scaglione": "oltre €5.000.000", "spese_avvio": 110, "spese_primo_incontro": 170,
        "tabella_a_minimo": "0,2% del valore", "tabella_a_massimo": "0,3% del valore",
    })

    return {
        "valore_controversia": valore_controversia,
        "scaglione": base["scaglione"],
        "mediazione_obbligatoria": mediazione_obbligatoria,
        "spese_avvio_per_parte": _q2(_mediazione_voci_fisse(valore_controversia)[0] * riduzione),
        "spese_primo_incontro_per_parte": _q2(_mediazione_voci_fisse(valore_controversia)[1] * riduzione),
        "tabella_a": base["tabella_a"],
        "esito_negativo": scenario("negativo", "primo_incontro"),
        "esito_negativo_incontri_successivi": scenario("negativo", "incontri_successivi"),
        "esito_positivo": scenario("positivo", "primo_incontro"),
        "esito_positivo_incontri_successivi": scenario("positivo", "incontri_successivi"),
        "tabella_completa": tabella,
        "note": [
            "Spese di avvio (art. 28 co. 4 DM 150/2023) per ciascuna parte: €40 fino a €1.000, €75 da €1.000,01 a €50.000, €110 oltre €50.000 e valore indeterminato",
            "Spese di mediazione del primo incontro (art. 28 co. 5): €60 fino a €1.000, €120 da €1.000,01 a €50.000, €170 oltre; sono comprese nella Tabella A",
            "Mancato accordo al primo incontro: solo avvio e primo incontro (art. 28 co. 6); accordo al primo incontro: Tabella A meno primo incontro, +10% (art. 30 co. 1); accordo dopo: +25% (art. 30 co. 2); prosecuzione senza accordo: Tabella A senza maggiorazione (art. 30 co. 3)",
            "Mediazione condizione di procedibilita' o demandata dal giudice: importi ridotti di un quinto (art. 28 co. 8 e art. 30 co. 4)",
            "Valore indeterminabile: si applica lo scaglione €50.000,01-€150.000 della Tabella A",
            "La Tabella A indica un minimo e un massimo: l'organismo sceglie l'importo, qui usato il valore '" + importo_tabella + "'",
            "Indennita' dovuta per ciascuna parte a ciascun organismo; IVA 22% applicata a tutta l'indennita'",
        ],
        "agevolazioni": [
            "Credito d'imposta fino a €600 per parte in caso di accordo (art. 20 D.Lgs. 28/2010)",
            "Esenzione imposta di registro fino a €100.000",
            "Gratuito patrocinio: parti ammesse non pagano indennità",
        ],
        "riferimento_normativo": "DM 150/2023 artt. 28, 30, 31 e Tabella A — D.Lgs. 28/2010 (Riforma Cartabia)",
    }
