---
name: quantificazione-danni
description: Quantificazione danni biologico, patrimoniale o morale con personalizzazione e attualizzazione.
  Usa quando l'utente chiede di quantificare un danno specifico (non un sinistro completo).
argument-hint: "[tipo: biologico|patrimoniale|morale] [valore o % invalidità] [età vittima]"
---

# Workflow Quantificazione Danni

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Classificazione danno
Identifica dall'input dell'utente:
- **Tipo danno**: biologico, patrimoniale, morale/esistenziale
- **Valore/percentuale**: importo (patrimoniale) o % invalidità (biologico)
- **Età della vittima**

Se mancano dati essenziali, chiedi all'utente.

## Step 2 — Calcolo base
In base al tipo di danno:

**Biologico** (percentuale invalidità):
- Se ≤ 9%: chiama `danno_biologico_micro(percentuale, eta)` — tabelle art. 139 CdA
- Se ≥ 10%: chiama `danno_biologico_macro(percentuale, eta)` — tabelle Milano

**Patrimoniale** (importo):
- Danno emergente: il valore indicato
- Lucro cessante: calcola in base alla durata della privazione
- Chiama `interessi_legali` sulla somma dalla data dell'evento

**Morale/esistenziale**:
- Chiama `danno_non_patrimoniale` come punto di partenza
- Applica la personalizzazione per gravità e impatto sulla vita di relazione

## Step 3 — Personalizzazione
Valuta i criteri di personalizzazione (Cass. SS.UU. 26972/2008):
- Entità della sofferenza soggettiva
- Incidenza sulla vita di relazione
- Specificità del caso concreto

Indica una percentuale di personalizzazione motivata.

## Step 4 — Attualizzazione
Chiama `rivalutazione_monetaria` dalla data dell'evento a oggi.
Chiama `interessi_legali` sulla somma rivalutata.

## Step 5 — Tabella riepilogativa

| Componente | Importo |
|------------|---------|
| Danno base (tabellare/documentale) | € ... |
| Personalizzazione (±...%) | € ... |
| Subtotale | € ... |
| Rivalutazione ISTAT | € ... |
| Interessi legali | € ... |
| **TOTALE** | **€ ...** |

### Motivazione
Spiega i criteri di personalizzazione adottati e la giurisprudenza di riferimento.

### Avvertenze
- Quantificazione indicativa basata sulle tabelle vigenti.
- La prova del danno patrimoniale richiede documentazione specifica.
- Per il danno biologico è necessaria perizia medico-legale.
