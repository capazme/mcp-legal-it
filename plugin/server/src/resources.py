"""MCP Resources — 15 legal reference documents.

Resources whose figures live in src/data (contributo unificato, interessi
legali, scaglioni IRPEF) are rendered from those JSON files at read time,
so they stay aligned with the datasets watched by scripts/update-data.py.
"""

import json
from pathlib import Path

from src.server import mcp

_DATA = Path(__file__).parent / "data"


def _load(name: str) -> dict:
    return json.loads((_DATA / name).read_text())


def _eur(value: float) -> str:
    """1214 -> '1.214,00' (Italian amount formatting)."""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _soglia(value: float) -> str:
    """Threshold formatting: integers without decimals (1.100), floats with (2.582,28)."""
    if float(value) == int(value):
        return f"{int(value):,}".replace(",", ".")
    return _eur(value)


def _pct(value: float) -> str:
    """2.5 -> '2,50'."""
    return f"{value:.2f}".replace(".", ",")


def _scaglioni_rows(scaglioni: list) -> list:
    """Markdown rows for a list of {fino_a|oltre, importo} brackets."""
    rows = []
    prev = None
    for s in scaglioni:
        if s.get("oltre"):
            label = f"Oltre € {_soglia(prev)}"
        elif prev is None:
            label = f"Fino a € {_soglia(s['fino_a'])}"
        else:
            label = f"Da € {_soglia(prev + 0.01)} a € {_soglia(s['fino_a'])}"
        rows.append(f"| {label} | € {_eur(s['importo'])} |")
        prev = s.get("fino_a", prev)
    return rows


def _render_contributo_unificato() -> str:
    cu = _load("contributo_unificato.json")
    civ = cu["civile"]

    cognizione = _scaglioni_rows(civ["cognizione"])
    cognizione.append(
        f"| Valore indeterminabile (bassa complessità) | € {_eur(civ['valore_indeterminabile'])} |"
    )
    cognizione.append(
        f"| Valore indeterminabile (alta complessità) | € {_eur(civ['cognizione'][-1]['importo'])} |"
    )

    monitorio = _scaglioni_rows(civ["procedimento_monitorio"]["scaglioni"])

    speciali = [
        f"| Opposizione a decreto ingiuntivo | CU pieno per valore |",
        f"| Procedimenti cautelari | € {_eur(civ['cautelari'])} |",
        f"| Volontaria giurisdizione | € {_eur(civ['volontaria_giurisdizione'])} |",
        f"| Procedimenti esecutivi immobiliari | € {_eur(civ['esecuzione_immobiliare'])} |",
        f"| Procedimenti esecutivi mobiliari | € {_eur(civ['esecuzione_mobiliare'])} |",
        f"| Separazione consensuale / divorzio congiunto | € {_eur(civ['separazione_consensuale'])} |",
        f"| Separazione giudiziale / divorzio giudiziale | € {_eur(civ['separazione_giudiziale'])} |",
    ]

    lav = cu["lavoro"]["appello"]
    tributario = _scaglioni_rows(cu["tributario"]["scaglioni"])

    amm_labels = {
        "tar_ordinario": "TAR — rito ordinario",
        "tar_appalti": "TAR — appalti",
        "tar_appalti_sopra_soglia": "TAR — appalti sopra soglia",
        "consiglio_stato": "Consiglio di Stato — ordinario",
        "consiglio_stato_appalti": "Consiglio di Stato — appalti",
        "decreto_ingiuntivo_tar": "Decreto ingiuntivo TAR",
        "silenzio_inadempimento": "Silenzio-inadempimento",
        "accesso_atti": "Accesso agli atti",
        "ottemperanza": "Giudizio di ottemperanza",
    }
    amministrativo = [
        f"| {label} | € {_eur(cu['amministrativo'][key])} |"
        for key, label in amm_labels.items()
        if key in cu["amministrativo"]
    ]

    nl = "\n"
    return f"""CONTRIBUTO UNIFICATO — TABELLA SCAGLIONI
(D.P.R. 115/2002 e successive modifiche — importi generati da src/data/contributo_unificato.json)

═══════════════════════════════════════════════════════════
PROCESSI CIVILI ORDINARI (art. 13, co. 1)
═══════════════════════════════════════════════════════════

| Valore causa | CU |
|--------------|-----|
{nl.join(cognizione)}

═══════════════════════════════════════════════════════════
PROCEDIMENTO MONITORIO — decreto ingiuntivo (dimezzato)
═══════════════════════════════════════════════════════════

| Valore causa | CU |
|--------------|-----|
{nl.join(monitorio)}

═══════════════════════════════════════════════════════════
IMPUGNAZIONI (art. 13, co. 1-bis)
═══════════════════════════════════════════════════════════

| Grado | Maggiorazione |
|-------|---------------|
| Appello | CU × {_pct(cu["appello"]["moltiplicatore"]).rstrip("0").rstrip(",")} ({cu["appello"]["_note"]}) |
| Cassazione | CU × {_pct(cu["cassazione"]["moltiplicatore"]).rstrip("0").rstrip(",")} ({cu["cassazione"]["_note"]}) |
| Riassunzione dopo cassazione con rinvio | come primo grado |

═══════════════════════════════════════════════════════════
PROCEDIMENTI SPECIALI (art. 13, co. 1 e 3)
═══════════════════════════════════════════════════════════

| Procedimento | CU |
|--------------|-----|
{nl.join(speciali)}

═══════════════════════════════════════════════════════════
LAVORO E TRIBUTARIO
═══════════════════════════════════════════════════════════

| Fattispecie | CU |
|-------------|-----|
| Lavoro e previdenza — primo grado | Esente |
| Lavoro — appello (fino a € {_soglia(lav["fino_a"])}) | € {_eur(lav["importo"])} |
| Lavoro — appello (fino a € 50.000) | € {_eur(lav["fino_a_50000"])} |
| Lavoro — appello (oltre € 50.000) | € {_eur(lav["oltre"])} |

Processo tributario (per valore della lite):

| Valore lite | CU |
|-------------|-----|
{nl.join(tributario)}

═══════════════════════════════════════════════════════════
PROCESSO AMMINISTRATIVO
═══════════════════════════════════════════════════════════

| Ricorso | CU |
|---------|-----|
{nl.join(amministrativo)}

═══════════════════════════════════════════════════════════
NOTE
═══════════════════════════════════════════════════════════
- Marca da bollo per iscrizione a ruolo: € 27,00 (sempre dovuta)
- Diritti di copia: variano per tipo e numero di pagine
- In caso di dichiarazione di valore mancante: CU come valore indeterminabile
- Sanzione per omesso/insufficiente pagamento: recupero con ingiunzione del funzionario
"""


@mcp.resource(
    "legal://riferimenti/contributo-unificato",
    name="Contributo Unificato — Tabella Scaglioni",
    description="Scaglioni del contributo unificato per valore causa e tipo procedimento (generati dal dataset corrente)",
)
def contributo_unificato() -> str:
    return _render_contributo_unificato()


def _render_irpef_scaglioni() -> str:
    per_anno = _load("irpef_scaglioni.json")["scaglioni_per_anno"]
    anno = max(per_anno.keys(), key=int)
    scaglioni = per_anno[anno]

    rows = []
    quote = []
    prev = 0
    for s in scaglioni:
        if s.get("oltre"):
            rows.append(f"| Oltre € {_soglia(prev)} | {s['aliquota']}% | — |")
        else:
            label = (
                f"Fino a € {_soglia(s['fino_a'])}"
                if prev == 0
                else f"Da € {_soglia(prev + 1)} a € {_soglia(s['fino_a'])}"
            )
            quota = (s["fino_a"] - prev) * s["aliquota"] / 100
            quote.append(quota)
            rows.append(f"| {label} | {s['aliquota']}% | max € {_eur(quota)} |")
            prev = s["fino_a"]

    aliquota_top = scaglioni[-1]["aliquota"]
    esempio_reddito = 60000
    eccedenza = esempio_reddito - prev
    quota_top = eccedenza * aliquota_top / 100
    totale = sum(quote) + quota_top
    somma = " + ".join(f"€ {_eur(q)}" for q in quote)

    nl = "\n"
    return f"""IRPEF {anno} — SCAGLIONI, ALIQUOTE E DETRAZIONI PRINCIPALI
(D.Lgs. 216/2023 — Riforma fiscale; scaglioni {anno} generati da src/data/irpef_scaglioni.json)

═══════════════════════════════════════════════════════════
SCAGLIONI E ALIQUOTE ({anno})
═══════════════════════════════════════════════════════════

| Scaglione di reddito | Aliquota | Imposta su scaglione |
|----------------------|----------|---------------------|
{nl.join(rows)}

Esempio: reddito € {_soglia(esempio_reddito)}
→ {somma} + {aliquota_top}% × € {_soglia(eccedenza)} = € {_eur(totale)}
"""


@mcp.resource(
    "legal://riferimenti/irpef-detrazioni",
    name="IRPEF — Scaglioni e Detrazioni",
    description="Schema IRPEF vigente: scaglioni (generati dal dataset corrente), aliquote e principali detrazioni",
)
def irpef_detrazioni() -> str:
    return _render_irpef_scaglioni() + """
Nota: nel 2024-2025 l'aliquota del secondo scaglione era il 35% (max € 7.700).
La riduzione al 33% dal 2026 (L. 199/2025, art. 1, c. 3) è neutralizzata per i
redditi complessivi oltre € 200.000 tramite una corrispondente riduzione delle detrazioni.

═══════════════════════════════════════════════════════════
DETRAZIONI PER LAVORO DIPENDENTE (art. 13 TUIR)
═══════════════════════════════════════════════════════════

| Reddito complessivo | Detrazione |
|---------------------|-----------|
| Fino a € 15.000 | € 1.955 (min. € 690 / € 1.380 tempo det.) |
| Da € 15.001 a € 28.000 | € 1.910 + € 1.190 × (€ 28.000 - reddito) / € 13.000 |
| Da € 28.001 a € 50.000 | € 1.910 × (€ 50.000 - reddito) / € 22.000 |
| Oltre € 50.000 | Nessuna |

+ € 65 aggiuntivi se reddito tra € 25.001 e € 35.000

═══════════════════════════════════════════════════════════
DETRAZIONI PER PENSIONE (art. 13 TUIR)
═══════════════════════════════════════════════════════════

| Reddito complessivo | Detrazione |
|---------------------|-----------|
| Fino a € 8.500 | € 1.955 (min. € 713) |
| Da € 8.501 a € 28.000 | € 700 + € 1.255 × (€ 28.000 - reddito) / € 19.500 |
| Da € 28.001 a € 50.000 | € 700 × (€ 50.000 - reddito) / € 22.000 |
| Oltre € 50.000 | Nessuna |

═══════════════════════════════════════════════════════════
DETRAZIONI PER CARICHI DI FAMIGLIA (art. 12 TUIR)
═══════════════════════════════════════════════════════════

| Familiare | Detrazione | Note |
|-----------|-----------|------|
| Coniuge (no separato) | € 800 (variabile per reddito) | Decresce sopra € 15.000 |
| Figli < 21 anni | Assegno Unico (non più detrazione) | ISEE-based |
| Figli ≥ 21 anni a carico | € 950 × (€ 95.000 - reddito) / € 95.000 | Reddito figlio < € 2.840,51 |
| Figli disabili ≥ 21 | € 1.350 × formula | Idem |
| Altri familiari a carico | € 750 × (€ 80.000 - reddito) / € 80.000 | Reddito < € 2.840,51 |

Limite reddito "a carico": € 2.840,51 (€ 4.000 per figli fino a 24 anni)

═══════════════════════════════════════════════════════════
NO TAX AREA
═══════════════════════════════════════════════════════════

| Categoria | Soglia esenzione |
|-----------|-----------------|
| Lavoro dipendente | € 8.500 |
| Pensione | € 8.500 |
| Lavoro autonomo | € 5.500 (circa) |

═══════════════════════════════════════════════════════════
ADDIZIONALI
═══════════════════════════════════════════════════════════

| Tipo | Aliquota |
|------|----------|
| Addizionale regionale | 1,23% — 3,33% (variabile per regione) |
| Addizionale comunale | 0% — 0,8% (delibera comunale) |
"""


def _render_interessi_legali() -> str:
    legali = _load("tassi_legali.json")["tassi"]
    mora = _load("tassi_mora.json")["tassi"]

    def _data_it(iso: str) -> str:
        return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"

    legali_rows = [
        f"| {_data_it(t['dal'])} | {_data_it(t['al'])} | {_pct(t['tasso'])}% |" for t in legali
    ]
    ultimo = max(legali, key=lambda t: t["al"])
    fonte_ultimo = ultimo.get("fonte", "DM MEF di dicembre")

    mora_rows = [
        f"| {'I' if t['dal'][5:7] == '01' else 'II'} sem. {t['dal'][0:4]} "
        f"| {_pct(t['bce'])}% | {_pct(t['mora'])}% |"
        for t in mora[-8:]
    ]

    nl = "\n"
    return f"""INTERESSI LEGALI — STORICO TASSI (art. 1284 c.c.)
Decreto ministeriale annuale del Ministero dell'Economia e delle Finanze
Tasso vigente: {_pct(ultimo["tasso"])}% (dal {_data_it(ultimo["dal"])} — {fonte_ultimo})
Tabelle generate da src/data/tassi_legali.json e tassi_mora.json

═══════════════════════════════════════════════════════════
TASSI PER PERIODO (dal 1942)
═══════════════════════════════════════════════════════════

| Dal | Al | Tasso |
|-----|-----|-------|
{nl.join(legali_rows)}

═══════════════════════════════════════════════════════════
INTERESSI DI MORA (D.Lgs. 231/2002 — transazioni commerciali)
═══════════════════════════════════════════════════════════

Tasso = tasso BCE + 8 punti percentuali (art. 5, D.Lgs. 231/2002)
Ultimi semestri:

| Semestre | Tasso BCE | Tasso mora |
|----------|-----------|------------|
{nl.join(mora_rows)}

═══════════════════════════════════════════════════════════
NOTE APPLICATIVE
═══════════════════════════════════════════════════════════

- Art. 1284, co. 1 c.c.: tasso legale per obbligazioni pecuniarie
- Art. 1284, co. 4 c.c.: dal 2014, se il debitore è inadempiente il tasso
  per le transazioni commerciali si applica anche ai crediti giudiziari
  (salvo diversa pattuizione)
- Interessi composti: vietato l'anatocismo (art. 1283 c.c.)
  salvo usi normativi e domanda giudiziale
- Rivalutazione vs. interessi: non cumulabili sullo stesso importo
  (Cass. SS.UU. 16601/2017) — il creditore sceglie la via più favorevole
"""


@mcp.resource(
    "legal://riferimenti/interessi-legali",
    name="Storico Tassi Interessi Legali e Mora",
    description="Tassi di interesse legale dal 1942 a oggi e saggi di mora (generati dai dataset correnti)",
)
def interessi_legali() -> str:
    return _render_interessi_legali()


# ---------------------------------------------------------------------------
# Static references — GENERATED copies of content/references/*.md live in
# src/data/references/ (projected by scripts/corpus/project_claude.py).
# One text, two consumers: the MCP resource below and any skill that needs it.
# ---------------------------------------------------------------------------
_REFERENCES_DIR = Path(__file__).parent / "data" / "references"

_STATIC_RESOURCES: list[tuple[str, str, str, str]] = [
    ("legal://riferimenti/procedura-civile", "procedura-civile.md",
     "Procedura Civile Ordinaria",
     "Schema fasi e termini della procedura civile post-Cartabia (D.Lgs. 149/2022)"),
    ("legal://riferimenti/termini-processuali", "termini-processuali.md",
     "Termini Processuali Chiave",
     "Tabella dei principali termini processuali civili post-Cartabia"),
    ("legal://riferimenti/checklist-decreto-ingiuntivo", "checklist-decreto-ingiuntivo.md",
     "Checklist Decreto Ingiuntivo",
     "Checklist operativa per il ricorso per decreto ingiuntivo (artt. 633 ss. c.p.c.)"),
    ("legal://riferimenti/fonti-diritto-italiano", "fonti-diritto-italiano.md",
     "Gerarchia Fonti del Diritto Italiano",
     "Sistema delle fonti, gerarchia normativa, criteri di risoluzione antinomie e formato citazione"),
    ("legal://riferimenti/codici-e-leggi-principali", "codici-e-leggi-principali.md",
     "Codici e Leggi Principali — Riferimento Rapido",
     "Indice ragionato dei principali codici, testi unici e leggi italiane ed europee con ambito e citazione"),
    ("legal://riferimenti/gdpr-checklist", "gdpr-checklist.md",
     "GDPR Compliance — Checklist Operativa",
     "Checklist completa per la conformità GDPR: adempimenti, documenti, scadenze e tool disponibili"),
    ("legal://riferimenti/consob-delibere", "consob-delibere.md",
     "CONSOB — Guida Ricerca Delibere",
     "Guida all'uso dei tool CONSOB: tipologie, argomenti, workflow e riferimenti normativi mercati finanziari"),
    ("legal://riferimenti/ricerca-giurisprudenziale", "ricerca-giurisprudenziale.md",
     "Ricerca Giurisprudenziale — Guida Italgiure",
     "Guida alla ricerca su Italgiure: strategia esplora→filtra→leggi, sintassi Solr, facets e workflow tipo"),
    ("legal://riferimenti/cerdef-giurisprudenza", "cerdef-giurisprudenza.md",
     "CeRDEF — Giurisprudenza Tributaria",
     "Guida ai tool CeRDEF: enti, criteri di ricerca, tipi provvedimento e norme fiscali principali"),
    ("legal://riferimenti/modelli-atti-catalogo", "modelli-atti-catalogo.md",
     "Catalogo Modelli Atti — 100 Tipi",
     "Indice di tutti i 100 tipi di atti legali generabili: routing, tool, resource e campi obbligatori per ciascun tipo"),
    ("legal://riferimenti/giustizia-amministrativa", "giustizia-amministrativa.md",
     "Giustizia Amministrativa — Guida Ricerca TAR/CdS",
     "Guida all'uso dei tool per la ricerca di sentenze TAR e Consiglio di Stato: sedi, tipi, workflow e normativa di riferimento"),
    ("legal://riferimenti/cgue-giurisprudenza", "cgue-giurisprudenza.md",
     "CGUE — Guida Giurisprudenza Europea",
     "Guida ai tool CGUE: corti, tipi documento, materie, formato CELEX/ECLI, workflow"),
]


def _make_reader(filename: str, description: str):
    def _read() -> str:
        return (_REFERENCES_DIR / filename).read_text(encoding="utf-8")

    _read.__name__ = filename[:-3].replace("-", "_")
    _read.__doc__ = description
    return _read


for _uri, _fname, _name, _desc in _STATIC_RESOURCES:
    mcp.resource(_uri, name=_name, description=_desc)(_make_reader(_fname, _desc))
