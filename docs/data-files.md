# Data Files — mcp-legal-it

> Documentazione dei file JSON statici in `src/data/`: descrizione, fonte normativa, moduli che li usano.

## Indice

- [Panoramica](#panoramica)
- [Tabella riepilogativa](#tabella-riepilogativa)
- [Dettaglio per file](#dettaglio-per-file)
  - [Calcoli monetari e tassi](#calcoli-monetari-e-tassi)
  - [Imposte e fisco](#imposte-e-fisco)
  - [Atti giudiziari e procedure](#atti-giudiziari-e-procedure)
  - [Risarcimento danni](#risarcimento-danni)
  - [Proprietà e successioni](#proprietà-e-successioni)
  - [Utilità e codifiche](#utilità-e-codifiche)
  - [Privacy e GDPR](#privacy-e-gdpr)

---

## Panoramica

I file JSON in `src/data/` contengono le tabelle normative e i dati di riferimento usati dai tool di calcolo. Sono caricati a runtime dai moduli tool e aggiornati manualmente a ogni variazione normativa.

**Struttura tipo**: ogni file inizia con chiavi descrittive (`_description`, `_source`, `_note`) seguite dai dati operativi. Questo pattern permette l'auto-documentazione e la tracciabilità della fonte.

---

## Tabella riepilogativa

| File | Moduli tool | Contenuto | Fonte normativa |
|------|------------|-----------|----------------|
| `indici_foi.json` | `rivalutazioni_istat`, `tassi_interessi` | Indici FOI (rivalutazione monetaria) per anno/mese | ISTAT, serie storica |
| `tassi_legali.json` | `tassi_interessi`, `rivalutazioni_istat`, `dichiarazione_redditi` | Tassi interesse legale per anno (art. 1284 c.c.) | D.M. MEF annuali 1999-2025 |
| `tassi_mora.json` | `tassi_interessi`, `atti_giudiziari` | Tassi di mora (BCE + 8pp) per semestre | D.Lgs. 231/2002, BCE |
| `tegm.json` | `tassi_interessi` | TEGM (Tasso Effettivo Globale Medio) per categoria | Banca d'Italia, D.L. 394/2000 |
| `festivita.json` | `scadenze_termini`, `varie` | Festività nazionali fisse e variabili per anno | L. 260/1949 e successive |
| `contributo_unificato.json` | `atti_giudiziari`, `fatturazione_avvocati` | Scaglioni CU per tipo procedimento e valore | D.P.R. 115/2002 |
| `parametri_forensi.json` | `fatturazione_avvocati` | Parametri D.M. 55/2014 per scaglione e fase | D.M. 55/2014, agg. D.M. 147/2022 |
| `tribunali_competenti.json` | `atti_giudiziari` | Circoscrizioni tribunali per comune | Ord. giudiziario, D.Lgs. 155/2012 |
| `codici_ruolo.json` | `atti_giudiziari` | Codici ruolo ministeriali per tipo procedimento | Ministero della Giustizia |
| `irpef_scaglioni.json` | `dichiarazione_redditi` | Scaglioni IRPEF, aliquote e detrazioni per anno | D.Lgs. 216/2023, L. 207/2024 |
| `imposte_successione.json` | `proprieta_successioni` | Aliquote e franchigie imposta di successione | D.Lgs. 346/1990, L. 383/2001 |
| `usufrutto_coefficienti.json` | `proprieta_successioni` | Coefficienti usufrutto per età (tabella ministeriale) | D.M. MEF (agg. periodica) |
| `tabella_danno_bio.json` | `risarcimento_danni` | Tabelle art. 139 CdA (micro-permanente ≤9%) | D.Lgs. 209/2005, art. 139 CdA |
| `tabella_milano_roma.json` | `risarcimento_danni` | Tabelle Milano e Roma per danno biologico macro (>9%) | Tribunale di Milano (agg. annuale) |
| `codici_ateco.json` | `varie` | Codici ATECO con descrizione attività | ISTAT, classificazione ATECO 2007 |
| `violazioni_patente.json` | `varie` | Violazioni CdS con punti, sanzioni e decurtazione | D.Lgs. 285/1992 (CdS) |
| `comuni.json` | `atti_giudiziari`, `rivalutazioni_istat`, `varie`, `proprieta_successioni`, `privacy_gdpr` | Comuni italiani con codice catastale, regione, provincia | ISTAT, Agenzia delle Entrate |
| `gdpr_sanzioni.json` | `privacy_gdpr` | Parametri sanzioni GDPR per tipo violazione | Reg. UE 2016/679, art. 83 |
| `gdpr_basi_giuridiche.json` | `privacy_gdpr` | Basi giuridiche GDPR con condizioni e casistica | Reg. UE 2016/679, art. 6 + art. 9 |
| `gdpr_dpia_criteri.json` | `privacy_gdpr` | 9 criteri WP248 per valutazione necessità DPIA | WP248 rev.01, EDPB |

---

## Dettaglio per file

### Calcoli monetari e tassi

#### `indici_foi.json`

Serie storica degli indici FOI (Famiglie Operai Impiegati) usati per la rivalutazione monetaria. Struttura:

```json
{
  "_description": "Indici FOI ISTAT per rivalutazione monetaria",
  "_note": "...",
  "base": 100,
  "2000": {"01": 87.5, "02": 87.7, ..., "12": 89.0},
  "2025": {"01": 125.3, ...}
}
```

Aggiornamento: mensile, rilascio ISTAT circa il 15 del mese successivo.

---

#### `tassi_legali.json`

Tassi di interesse legale (art. 1284 c.c.) per anno, dal 2000 al 2026. Struttura:

```json
{
  "_description": "Tassi interesse legale ex art. 1284 c.c.",
  "tassi": {
    "2000": 2.5,
    "2023": 5.0,
    "2026": 1.6
  }
}
```

Fonte: D.M. MEF emesso ogni dicembre per l'anno successivo. Ultimo aggiornamento: D.M. 10/12/2025 (tasso 2026: 1,60%).

---

#### `tassi_mora.json`

Tassi di mora per transazioni commerciali (D.Lgs. 231/2002): BCE + 8 punti percentuali, aggiornati semestralmente. Struttura per semestre (`"YYYY-S1"` / `"YYYY-S2"`).

---

#### `tegm.json`

TEGM per categoria di operazione (prestiti personali, mutui, leasing, ecc.). Usato per il calcolo della soglia usura (TEGM × 1,25 + 4pp). Fonte: Banca d'Italia, aggiornamento trimestrale.

---

#### `festivita.json`

Festività nazionali per il calcolo dei termini processuali:

```json
{
  "_description": "Festività nazionali italiane",
  "fisse": ["01-01", "06-01", "04-25", "05-01", "06-02", "08-15", "11-01", "12-08", "12-25", "12-26"],
  "variabili": {
    "2024": {"pasqua": "2024-03-31", "lunedi_angeli": "2024-04-01"},
    "2025": {"pasqua": "2025-04-20", "lunedi_angeli": "2025-04-21"}
  }
}
```

Fonte: L. 260/1949 e successive modifiche.

---

### Imposte e fisco

#### `irpef_scaglioni.json`

Scaglioni IRPEF, aliquote e detrazioni per anno fiscale. Struttura per anno, con sotto-chiavi per scaglioni, detrazioni lavoro dipendente, detrazioni pensione, no tax area. Riflette la riforma fiscale D.Lgs. 216/2023 (3 aliquote dal 2024: 23%, 35%, 43%).

---

#### `imposte_successione.json`

Aliquote e franchigie per imposta di successione e donazione:

| Grado parentela | Aliquota | Franchigia |
|----------------|---------|-----------|
| Coniuge / Figli | 4% | € 1.000.000 |
| Fratelli / Sorelle | 6% | € 100.000 |
| Altri parenti fino 4° grado | 6% | Nessuna |
| Altri soggetti | 8% | Nessuna |
| Portatori di handicap grave | 4%/6%/8% | € 1.500.000 |

Fonte: D.Lgs. 346/1990, mod. L. 383/2001. Imposte ipotecaria (2%) e catastale (1%) per immobili.

---

#### `usufrutto_coefficienti.json`

Coefficienti per la determinazione del valore fiscale dell'usufrutto per età dell'usufruttuario. Aggiornati periodicamente dal MEF. Usati per il calcolo delle imposte su atti con usufrutto (registro, successione, donazione).

---

### Atti giudiziari e procedure

#### `contributo_unificato.json`

Tabella scaglioni del contributo unificato (D.P.R. 115/2002):

```json
{
  "_description": "Contributo unificato per valore causa e tipo procedimento",
  "civile": [
    {"da": 0, "a": 1100, "importo": 43},
    {"da": 1100.01, "a": 5200, "importo": 98},
    ...
  ],
  "appello": {"moltiplicatore": 1.5},
  "cassazione": {"moltiplicatore": 2},
  "decreto_ingiuntivo": {"moltiplicatore": 0.5},
  "speciali": {
    "cautelare": 98,
    "volontaria_giurisdizione": 98,
    "esecuzione_immobiliare": 278
  }
}
```

---

#### `parametri_forensi.json`

Parametri per il calcolo del compenso degli avvocati (D.M. 55/2014, aggiornato D.M. 147/2022). Struttura per scaglione di valore della causa e per fase processuale (studio, introduttiva, istruttoria/trattazione, decisoria). Ogni voce ha `minimo`, `medio`, `massimo`.

---

#### `tribunali_competenti.json`

Mappa comune → circoscrizione giudiziaria competente. Struttura: `"tribunale_name": ["comune1", "comune2", ...]`. Riflette la riforma delle circoscrizioni giudiziarie (D.Lgs. 155/2012).

---

#### `codici_ruolo.json`

Lista codici ruolo ministeriali per la registrazione dei procedimenti. Struttura: array di oggetti `{"codice": "...", "descrizione": "...", "tipo": "civile|penale|lavoro"}`.

---

### Risarcimento danni

#### `tabella_danno_bio.json`

Tabelle per il danno biologico da micro-permanente (IP ≤ 9%):

- Valori tabellari art. 139 CdA (D.Lgs. 209/2005) per percentuale di invalidità e età
- Valori ITT (Inabilità Temporanea Totale) per giorno
- Valori ITP (Inabilità Temporanea Parziale) per percentuale ridotta (75%, 50%, 25%)

Aggiornamento: annuale con rivalutazione ISTAT (art. 139, co. 14 CdA).

---

#### `tabella_milano_roma.json`

Tabelle per il danno biologico da macro-permanente (IP > 9%):

- **Tabelle di Milano** (Tribunale di Milano, aggiornamento annuale): valore punto per IP e età, coefficienti di personalizzazione
- **Tabelle di Roma** (Tribunale di Roma): struttura analoga

Le tabelle di Milano sono quelle più frequentemente applicate dalla Cassazione come riferimento nazionale.

---

### Proprietà e successioni

#### `comuni.json`

Database comuni italiani con:
- Codice catastale (4 caratteri: lettera + 3 cifre)
- Regione, provincia
- Coordinate geografiche (opzionale)

Usato per identificare il foro competente, il Comune di residenza nelle dichiarazioni fiscali, le coordinate per il calcolo dell'aliquota IMU.

---

### Utilità e codifiche

#### `codici_ateco.json`

Codici ATECO 2007 con descrizione attività economica. Array di oggetti:
```json
[{"codice": "A01.11", "descrizione": "Coltivazione di cereali (escluso il riso)"}]
```

73 macro-categorie con codici relativi. Usato per la verifica del codice attività in regime forfettario.

---

#### `violazioni_patente.json`

Infrazioni al Codice della Strada con:
- Articolo CdS violato
- Importo minimo e massimo della sanzione pecuniaria
- Punti decurtati dalla patente
- Eventuale sospensione/ritiro patente

Fonte: D.Lgs. 285/1992 (Codice della Strada), tabella sanzionatoria.

---

### Privacy e GDPR

#### `gdpr_sanzioni.json`

Parametri per il calcolo delle sanzioni GDPR (art. 83):

```json
{
  "tier1": {
    "massimale_assoluto": 10000000,
    "massimale_percentuale": 0.02,
    "violazioni": ["obblighi titolare/responsabile", "certificazione", "monitoraggio"]
  },
  "tier2": {
    "massimale_assoluto": 20000000,
    "massimale_percentuale": 0.04,
    "violazioni": ["principi base", "diritti interessati", "trasferimenti"]
  }
}
```

Fattori mitiganti/aggravanti: gravità, durata, numero interessati, cooperazione con autorità, misure adottate, categorie di dati.

---

#### `gdpr_basi_giuridiche.json`

Basi giuridiche GDPR per trattamento (art. 6) e per dati particolari (art. 9):

```json
{
  "art6": {
    "consenso": {"lettera": "a", "condizioni": [...], "contesti": [...]},
    "contratto": {"lettera": "b", ...},
    ...
  },
  "art9": {
    "consenso_esplicito": {"lettera": "a", ...},
    ...
  }
}
```

Usato da `analisi_base_giuridica()` per raccomandare la base corretta.

---

#### `gdpr_dpia_criteri.json`

9 criteri WP248 rev.01 (EDPB) per la valutazione della necessità di DPIA:

```json
{
  "soglia_obbligatoria": 2,
  "criteri": [
    {"id": 1, "nome": "valutazione_scoring", "descrizione": "..."},
    {"id": 2, "nome": "decisione_automatizzata", "descrizione": "..."},
    ...
  ]
}
```

Se ≥ 2 criteri sono soddisfatti → DPIA obbligatoria (art. 35 GDPR).

---

## Aggiornamento dei dati

I file statici devono essere aggiornati manualmente a ogni variazione normativa. Checklist per l'aggiornamento annuale (tipicamente dicembre/gennaio):

- [ ] `tassi_legali.json` — nuovo D.M. MEF (tasso anno successivo)
- [ ] `tassi_mora.json` — tasso BCE semestrale (gennaio e luglio)
- [ ] `irpef_scaglioni.json` — Legge di Bilancio
- [ ] `tabella_danno_bio.json` — rivalutazione ISTAT art. 139 CdA
- [ ] `tabella_milano_roma.json` — aggiornamento Tribunale di Milano (solitamente marzo)
- [ ] `usufrutto_coefficienti.json` — aggiornamento D.M. MEF (se variato)
- [ ] `parametri_forensi.json` — eventuali aggiornamenti D.M. 55/2014
- [ ] `indici_foi.json` — nuovi indici mensili ISTAT
- [ ] `festivita.json` — aggiungere anno corrente con data Pasqua
