---
name: causa-civile
description: Pianificazione causa civile con contributo unificato, scadenze, impugnazioni e preventivo.
  Usa quando l'utente deve avviare una causa o vuole stimare costi e tempi di un giudizio civile.
argument-hint: "[valore causa] [rito: ordinario|sommario|lavoro] [grado: primo|appello|cassazione]"
---

# Workflow Causa Civile

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Raccolta dati
Identifica dall'input dell'utente:
- **Valore della causa** (in euro)
- **Rito**: ordinario, sommario (semplificato), lavoro
- **Grado**: primo grado, appello, cassazione

Se mancano dati essenziali, chiedi all'utente.

## Step 2 — Contributo unificato
Chiama `contributo_unificato(valore, rito, grado)`.
Verifica eventuali esenzioni:
- Cause di lavoro sotto soglia
- Procedimenti di volontaria giurisdizione
- Controversie previdenziali

## Step 3 — Scadenze processuali
Chiama `scadenza_processuale` per calcolare i termini chiave in base al rito:
- **Ordinario**: comparsa di risposta (70gg), memorie art. 171-ter c.p.c.
- **Sommario/Semplificato**: costituzione resistente, eventuale mutamento rito
- **Lavoro**: ricorso, memoria difensiva, note autorizzate

Indica la sospensione feriale (1-31 agosto) se applicabile.

## Step 4 — Scadenze impugnazioni
Chiama `scadenze_impugnazioni` per i termini del grado attuale:
- Primo grado → appello: 30gg (breve) / 6 mesi (lungo)
- Appello → cassazione: 60gg (breve) / 6 mesi (lungo)
- Revocazione, opposizione di terzo se pertinenti

## Step 5 — Preventivo costi
Chiama `preventivo_civile(valore, rito, grado)`.
Mostra il range di compenso per ogni fase processuale.

## Step 6 — Tabella riepilogativa

### Quadro Economico
| Voce | Importo |
|------|---------|
| Contributo unificato | € ... |
| Marca da bollo | € 27,00 |
| Compenso avvocato (range min-max) | € ... — € ... |
| Spese generali (15%) | € ... |
| CPA (4%) + IVA (22%) | € ... |
| **Budget stimato (medio)** | **€ ...** |

### Scadenze Chiave
| Termine | Scadenza | Norma |
|---------|----------|-------|
| ... | ... | ... |

### Note
- Indicare i rischi di soccombenza e regime spese (art. 91 c.p.c.)
- Valutare la mediazione obbligatoria se applicabile (D.Lgs. 28/2010)
- Segnalare se il rito è soggetto a negoziazione assistita (D.L. 132/2014)
