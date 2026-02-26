---
name: verifica-prescrizione
description: Verifica prescrizione di un diritto civile o di un reato penale con analisi temporale.
  Usa quando l'utente chiede se un diritto è prescritto o quando scade un termine di prescrizione.
argument-hint: "[tipo: civile|penale] [descrizione fatto] [data fatto GG/MM/AAAA]"
---

# Workflow Verifica Prescrizione

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Classificazione
Identifica dall'input dell'utente:
- **Tipo**: civile o penale
- **Descrizione del fatto/diritto**
- **Data del fatto** o della nascita del diritto

Se mancano dati essenziali, chiedi all'utente.

## Step 2 — Calcolo prescrizione

**Se civile**: chiama `prescrizione_diritti` con i dati forniti.
- Identifica il tipo di diritto (contrattuale, extracontrattuale, reale, etc.)
- Termine ordinario: 10 anni (art. 2946 c.c.)
- Termini brevi: 5 anni (risarcimento danni, art. 2947 c.c.), 2 anni (assicurazione, art. 2952 c.c.), 1 anno (trasporti)
- Verifica cause di sospensione (artt. 2941-2942 c.c.)
- Verifica cause di interruzione (art. 2943 c.c.): messa in mora, ricorso, riconoscimento del debito

**Se penale**: chiama `prescrizione_reato` con i dati forniti.
- Identifica il reato (titolo e articolo c.p.)
- Termine base = massimo edittale della pena (min. 6 anni delitto, 4 anni contravvenzione)
- Verifica cause di sospensione (art. 159 c.p.) e interruzione (art. 160 c.p.)
- Regime applicabile: ordinario / Bonafede (L. 3/2019) / Cartabia (D.Lgs. 150/2022) in base alla data del fatto

## Step 3 — Analisi temporale
- Data decorrenza
- Data odierna: calcola il tempo trascorso
- Data prescrizione: indica la scadenza esatta
- Stato: PRESCRITTA / NON PRESCRITTA / IN SCADENZA (ultimi 6 mesi)

## Step 4 — Tabella riepilogativa

| Elemento | Dettaglio |
|----------|----------|
| Fatto | ... |
| Data fatto | GG/MM/AAAA |
| Tipo diritto/reato | ... |
| Norma applicabile | art. ... |
| Termine prescrizione | ... anni |
| Data decorrenza | GG/MM/AAAA |
| Data scadenza prescrizione | GG/MM/AAAA |
| Tempo trascorso | ... anni, ... mesi, ... giorni |
| Tempo residuo | ... anni, ... mesi, ... giorni |
| **STATO** | **PRESCRITTA / NON PRESCRITTA / IN SCADENZA** |

### Cause di Sospensione/Interruzione
Elenca eventuali cause note che potrebbero aver modificato il decorso.

### Avvertenze
- La prescrizione può essere interrotta o sospesa da atti non noti al momento dell'analisi.
- Per la prescrizione penale, la riforma Bonafede e Cartabia hanno modificato il regime — il tool applica automaticamente la disciplina corretta.
- In ambito civile, il decorso può essere interrotto con atto stragiudiziale (raccomandata/PEC di messa in mora).
