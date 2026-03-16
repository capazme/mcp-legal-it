---
name: causa-civile
description: Pianifica una causa civile con calcolo contributo unificato, scadenze processuali post-Cartabia, termini impugnazione e preventivo costi. Usa quando l'utente chiede di avviare una causa, calcolare costi giudiziali, verificare termini processuali o preparare un preventivo per il cliente.
argument-hint: "[valore causa] [rito: ordinario/sommario/lavoro]"
allowed-tools: mcp__legal-it__contributo_unificato, mcp__legal-it__scadenza_processuale, mcp__legal-it__scadenze_impugnazioni, mcp__legal-it__preventivo_civile
---

# Causa Civile

Pianificazione completa: costi, scadenze, preventivo.

## Workflow

### 1. Contributo unificato

Chiama `legal-it:contributo_unificato` con valore, rito e grado.

### 2. Scadenze processuali

Chiama `legal-it:scadenza_processuale` per i termini in base al rito:
- **Ordinario**: comparsa risposta (70gg), memorie art. 171-ter c.p.c.
- **Sommario**: costituzione resistente, mutamento rito
- **Lavoro**: ricorso, memoria difensiva

Sospensione feriale: 1-31 agosto.

### 3. Impugnazioni

Chiama `legal-it:scadenze_impugnazioni`:
- Primo -> appello: 30gg (breve) / 6 mesi (lungo)
- Appello -> cassazione: 60gg (breve) / 6 mesi (lungo)

### 4. Preventivo

Chiama `legal-it:preventivo_civile` con range compenso per fase.

## Note
- Mediazione obbligatoria (D.Lgs. 28/2010)
- Negoziazione assistita (D.L. 132/2014)
