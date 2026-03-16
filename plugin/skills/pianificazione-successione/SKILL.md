---
name: pianificazione-successione
description: Pianifica una successione ereditaria con calcolo quote legittime, imposte di successione, franchigie e adempimenti. Usa quando l'utente chiede di calcolare quote ereditarie, imposte successione, eredita, testamento, franchigia o donazione.
argument-hint: "[valore asse] [eredi] [grado parentela]"
allowed-tools: mcp__legal-it__calcolo_eredita, mcp__legal-it__imposte_successione, mcp__legal-it__imposte_compravendita, mcp__legal-it__grado_parentela
---

# Pianificazione Successione

Quote ereditarie, imposte e adempimenti.

## Workflow

### 1. Quote ereditarie

Chiama `calcolo_eredita` con valore_asse, grado_parentela, numero_eredi.

### 2. Imposte di successione

Chiama `imposte_successione`:
- Aliquota per grado di parentela
- Franchigia (1M coniuge/figli, 100K fratelli)
- Imposte ipotecaria (2%) e catastale (1%) se immobili

### 3. Imposte compravendita (se immobili da vendere)

Chiama `imposte_compravendita`.

## Adempimenti da indicare

- Dichiarazione successione: entro 12 mesi
- Voltura catastale: entro 30 giorni
- Accettazione eredita: con beneficio d'inventario se opportuno
