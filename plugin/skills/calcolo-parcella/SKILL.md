---
name: calcolo-parcella
description: Calcola la parcella dell'avvocato per attivita civile, penale o stragiudiziale secondo il D.M. 55/2014 con nota spese completa. Usa quando l'utente chiede compenso avvocato, notula, preventivo legale, parcella professionale o fattura per prestazione legale.
argument-hint: "[tipo: civile/penale/stragiudiziale] [valore causa]"
allowed-tools: mcp__legal-it__parcella_avvocato_civile, mcp__legal-it__parcella_avvocato_penale, mcp__legal-it__parcella_stragiudiziale, mcp__legal-it__parcella_volontaria_giurisdizione, mcp__legal-it__nota_spese, mcp__legal-it__fattura_avvocato
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

### 2. Nota spese

Chiama `legal-it:nota_spese` per il prospetto: compenso per fase, spese generali (15%), CPA (4%), IVA (22%).

## Output atteso

| Fase | Minimo | Medio | Massimo |
|------|--------|-------|---------|
| Studio | ... | ... | ... |
| Introduttiva | ... | ... | ... |
| Istruttoria | ... | ... | ... |
| Decisoria | ... | ... | ... |
| **Totale** | **...** | **...** | **...** |
