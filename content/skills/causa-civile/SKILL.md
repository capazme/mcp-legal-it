---
name: causa-civile
description: Usa quando l'utente chiede di avviare una causa, calcolare costi giudiziali, verificare termini processuali o un preventivo — contributo unificato, scadenze post-Cartabia, impugnazioni e costi.
tools: [contributo_unificato, preventivo_civile, scadenza_processuale, scadenze_impugnazioni]
prompt: {"name": "causa_civile", "description": "Pianificazione causa civile: contributo unificato, scadenze, impugnazioni e preventivo", "args": [{"name": "valore_causa", "type": "float"}, {"name": "rito", "type": "str"}, {"name": "grado", "type": "str"}]}
---

# Causa Civile

Pianificazione completa: costi, scadenze, preventivo.

## Workflow

### 1. Contributo unificato

Chiama `contributo_unificato` con valore_causa, tipo_procedimento (es. cognizione, lavoro, monitorio) e grado (primo/appello/cassazione).

Verifica eventuali esenzioni (es. cause di lavoro sotto soglia, procedimenti di volontaria giurisdizione).

### 2. Scadenze processuali

Chiama `scadenza_processuale` per i termini in base al rito:
- **Ordinario**: comparsa risposta (70gg), memorie art. 171-ter c.p.c.
- **Sommario**: costituzione resistente, mutamento rito
- **Lavoro**: ricorso, memoria difensiva, note autorizzate

Sospensione feriale (1-31 agosto): indicala solo se il rito o la materia vi è soggetto — non opera, tra l'altro, in materia di lavoro, procedimenti cautelari e alimenti.

### 3. Impugnazioni

Chiama `scadenze_impugnazioni`:
- Primo -> appello: 30gg (breve) / 6 mesi (lungo)
- Appello -> cassazione: 60gg (breve) / 6 mesi (lungo)
- Revocazione, opposizione di terzo se pertinenti

### 4. Preventivo

Chiama `preventivo_civile` con range compenso per fase.

## Formato output

```markdown
## Quadro Economico
| Voce | Importo |
|------|---------|
| Contributo unificato | € ... |
| Marca da bollo (iscrizione a ruolo) | € 27,00 |
| Compenso avvocato (range min-max) | € ... — € ... |
| Spese generali (15%) | € ... |
| CPA (4%) + IVA (22%) | € ... |
| **Budget stimato (medio)** | **€ ...** |

## Scadenze Chiave
| Termine | Scadenza | Norma |
|---------|----------|-------|
| ... | ... | ... |
```

## Note
- Indicare i rischi di soccombenza e regime spese (art. 91 c.p.c.)
- Valutare la mediazione obbligatoria se applicabile (D.Lgs. 28/2010, materie estese dalla riforma Cartabia)
- Segnalare se il rito è soggetto a negoziazione assistita (D.L. 132/2014)
