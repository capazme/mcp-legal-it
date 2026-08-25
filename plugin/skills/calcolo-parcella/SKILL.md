---
name: calcolo-parcella
description: Calcola la parcella dell'avvocato per attivita civile, penale o stragiudiziale secondo il D.M. 55/2014 con nota spese completa. Usa quando l'utente chiede compenso avvocato, notula, preventivo legale, parcella professionale o fattura per prestazione legale.
---

# Calcolo Parcella

Compenso avvocato D.M. 55/2014 con nota spese.

## Workflow

### 1. Calcolo compenso

| Tipo | Tool |
|------|------|
| Civile | `legal-it:parcella_avvocato_civile` |
| Penale | `legal-it:parcella_avvocato_penale` |
| Stragiudiziale | `legal-it:parcella_stragiudiziale` |
| Vol. giurisdizione | `legal-it:parcella_volontaria_giurisdizione` |

Le fasi compensate variano con il tipo di attività — la tabella di output va adeguata di conseguenza.

Per attività **penale** (D.M. 55/2014):
- Fase di studio
- Fase introduttiva
- Fase istruttoria
- Fase dibattimentale
- Fase decisoria

Per attività **stragiudiziale**:
- Assistenza/consulenza
- Redazione atti e diffide
- Negoziazione

### 2. Nota spese

Chiama `legal-it:nota_spese` per il prospetto: compenso per fase, spese generali (15%), CPA (4%), IVA (22%), contributo unificato e bolli (se giudiziale).

## Output atteso

| Fase | Minimo | Medio | Massimo |
|------|--------|-------|---------|
| Studio | ... | ... | ... |
| Introduttiva | ... | ... | ... |
| Istruttoria | ... | ... | ... |
| Decisionale | ... | ... | ... |
| **Totale** | **...** | **...** | **...** |

### Nota Spese (su compenso medio)

| Voce | Importo |
|------|---------|
| Compenso | € ... |
| Spese generali (15%) | € ... |
| CPA (4%) | € ... |
| Imponibile IVA | € ... |
| IVA (22%) | € ... |
| **Totale parcella** | **€ ...** |

## Note

- I compensi si riferiscono al D.M. 55/2014 come da ultimo aggiornato dal D.M. 147/2022.
- Indicare sempre lo scaglione di valore applicato.
- In sede di liquidazione giudiziale i massimi sono derogabili in casi di particolare complessità, ma i minimi sono inderogabili (D.M. 55/2014 come modificato dal D.M. 147/2022).
