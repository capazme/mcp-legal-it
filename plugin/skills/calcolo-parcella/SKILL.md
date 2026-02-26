---
name: calcolo-parcella
description: Calcolo parcella avvocato per attività civile, penale o stragiudiziale con nota spese.
  Usa quando l'utente chiede di calcolare il compenso dell'avvocato o generare una nota spese.
argument-hint: "[tipo: civile|penale|stragiudiziale] [valore causa/pratica]"
---

# Workflow Calcolo Parcella

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Raccolta dati
Identifica dall'input dell'utente:
- **Tipo attività**: civile, penale, stragiudiziale
- **Valore della causa/pratica** (in euro)
- **Fasi svolte** (se specificate)

Se mancano dati essenziali, chiedi all'utente.

## Step 2 — Calcolo compenso
In base al tipo di attività:

**Civile** (D.M. 55/2014 e succ. mod.):
Chiama `parcella_avvocato_civile(valore)`.
Fasi: studio, introduttiva, istruttoria/trattazione, decisoria.

**Penale** (D.M. 55/2014):
Chiama `parcella_avvocato_penale(valore)`.
Fasi: studio, introduttiva, istruttoria, dibattimentale, decisoria.

**Stragiudiziale**:
Chiama `parcella_stragiudiziale(valore)`.
Fasi: assistenza/consulenza, redazione atti e diffide, negoziazione.

Ogni fase ha parametri: minimo, medio, massimo.

## Step 3 — Nota spese
Chiama `nota_spese` per generare il prospetto completo con:
- Compenso per ciascuna fase
- Spese generali (15%)
- CPA (4%)
- IVA (22%)
- Contributo unificato e bolli (se giudiziale)

## Step 4 — Tabella riepilogativa

### Compenso (D.M. 55/2014)
| Fase | Minimo | Medio | Massimo |
|------|--------|-------|---------|
| ... | € ... | € ... | € ... |
| **Totale compenso** | **€ ...** | **€ ...** | **€ ...** |

### Nota Spese (su compenso medio)
| Voce | Importo |
|------|---------|
| Compenso | € ... |
| Spese generali (15%) | € ... |
| CPA (4%) | € ... |
| Imponibile IVA | € ... |
| IVA (22%) | € ... |
| **Totale parcella** | **€ ...** |

### Note
- I compensi si riferiscono al D.M. 55/2014 come aggiornato dal D.M. 147/2022.
- Il giudice può liquidare compensi anche oltre i massimi in casi di particolare complessità.
