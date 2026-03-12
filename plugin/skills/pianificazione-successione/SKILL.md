---
name: pianificazione-successione
description: Pianifica una successione ereditaria con calcolo quote legittime, imposte di successione, franchigie e adempimenti. Usa quando l'utente chiede di calcolare quote ereditarie, imposte successione, eredita, testamento, franchigia o donazione.
---

# Pianificazione Successione

Quote ereditarie, imposte e adempimenti.

## Workflow

### 1. Quote ereditarie

Chiama `legal-it:calcolo_eredita` con valore_asse, grado_parentela, numero_eredi.

### 2. Imposte di successione

Chiama `legal-it:imposte_successione`:
- Aliquota per grado di parentela
- Franchigia (1M coniuge/figli, 100K fratelli)
- Imposte ipotecaria (2%) e catastale (1%) se immobili

### 3. Imposte compravendita (se immobili da vendere)

Chiama `legal-it:imposte_compravendita`.

## Adempimenti da indicare

- Dichiarazione successione: entro 12 mesi
- Voltura catastale: entro 30 giorni
- Accettazione eredita: con beneficio d'inventario se opportuno

## Tool utilizzati

- `legal-it:calcolo_eredita`
- `legal-it:imposte_successione`
- `legal-it:imposte_compravendita`
- `legal-it:grado_parentela`
