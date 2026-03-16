---
name: verifica-prescrizione
description: Verifica la prescrizione di un diritto civile o di un reato penale con calcolo termine, analisi cause di sospensione/interruzione e stato attuale. Usa quando l'utente chiede se un diritto e prescritto, i termini di prescrizione, o la decadenza di un'azione.
---

# Verifica Prescrizione

Calcolo termine prescrizione civile o penale.

## Workflow

### Civile

Chiama `prescrizione_diritti`:
- **10 anni**: ordinario (art. 2946 c.c.)
- **5 anni**: risarcimento (art. 2947)
- **2 anni**: assicurazione (art. 2952)

Verifica sospensione (artt. 2941-2942) e interruzione (art. 2943).

### Penale

Chiama `prescrizione_reato`:
- Termine = massimo edittale (min 6 anni delitto, 4 contravvenzione)
- Sospensione (art. 159 c.p.) e interruzione (art. 160 c.p.)
- Riforma Cartabia: improcedibilita in appello/cassazione

## Output: stato PRESCRITTA / NON PRESCRITTA / IN SCADENZA con data esatta.

## Tool utilizzati

- `prescrizione_diritti` (civile)
- `prescrizione_reato` (penale)
- `cite_law` (norme sulla prescrizione)
