---
name: verifica-prescrizione
description: Usa quando l'utente chiede se un diritto è prescritto, i termini di prescrizione o la decadenza di un'azione — calcolo del termine civile o penale con cause di sospensione/interruzione e stato attuale.
tools: [prescrizione_diritti, prescrizione_reato]
prompt: {"name": "verifica_prescrizione", "description": "Verifica prescrizione di un diritto civile o di un reato penale", "args": [{"name": "tipo", "type": "str"}, {"name": "descrizione_fatto", "type": "str"}, {"name": "data_fatto", "type": "str"}]}
---

# Verifica Prescrizione

Calcolo termine prescrizione civile o penale.

## Workflow

### Civile

Identifica anzitutto il tipo di diritto (contrattuale, extracontrattuale, reale, etc.): è la classificazione che determina quale termine si applica.

Chiama `prescrizione_diritti`:
- **10 anni**: ordinaria (tipo_diritto='ordinaria', art. 2946 c.c.)
- **5 anni**: risarcimento danni (tipo_diritto='risarcimento_danni', art. 2947 c.c.)
- **2 anni**: danno da circolazione veicoli / RCA (tipo_diritto='risarcimento_rca', art. 2947 c.2 c.c.)
- **2 anni**: diritti derivanti dal contratto di assicurazione (art. 2952 c.c.)
- **1 anno**: trasporti e spedizioni

Verifica sospensione (artt. 2941-2942) e interruzione (art. 2943 c.c.): messa in mora, ricorso, riconoscimento del debito.

### Penale

Identifica anzitutto il reato (titolo e articolo c.p.): è il presupposto per calcolare il massimo edittale.

Chiama `prescrizione_reato`:
- Termine = massimo edittale (min 6 anni delitto, 4 contravvenzione)
- Sospensione (art. 159 c.p.), interruzione (art. 160 c.p.) e termine massimo con interruzioni (art. 161 c.p.)
- Riforma Cartabia: improcedibilita in appello/cassazione — per il regime applicabile in base alla data del fatto, vedi «Avvertenze»

### Analisi temporale

- Data decorrenza: la data del fatto indicata
- Data odierna: calcola il tempo trascorso
- Data prescrizione: indica la scadenza esatta
- Stato: PRESCRITTA / NON PRESCRITTA / IN SCADENZA (ultimi 6 mesi)

## Formato output

Stato PRESCRITTA / NON PRESCRITTA / IN SCADENZA con data esatta, presentato in tabella:

### Verifica Prescrizione — civile o penale

| Elemento | Dettaglio |
|----------|----------|
| Fatto | descrizione del fatto |
| Data fatto | data indicata |
| Tipo diritto/reato | ... |
| Norma applicabile | art. ... |
| Termine prescrizione | ... anni |
| Data decorrenza | data del fatto |
| Data scadenza prescrizione | GG/MM/AAAA |
| Tempo trascorso | ... anni, ... mesi, ... giorni |
| Tempo residuo | ... anni, ... mesi, ... giorni |
| **STATO** | **PRESCRITTA / NON PRESCRITTA / IN SCADENZA** |

### Cause di Sospensione/Interruzione

Elenca eventuali cause note che potrebbero aver modificato il decorso.

## Avvertenze

- La prescrizione può essere interrotta o sospesa da atti non noti al momento dell'analisi: ogni verdetto PRESCRITTA è provvisorio rispetto alla completezza dei fatti forniti.
- Prescrizione penale — regime intertemporale, da individuare in base alla data del fatto:
  - **Fatti fino al 2.8.2017**: regime pre-Orlando — la prescrizione corre in ogni grado e stato, senza le sospensioni della L. 103/2017 (norme sostanziali sfavorevoli, irretroattive ex art. 2 c.p.); rilevano solo gli aumenti da interruzione ex art. 161 c.p.
  - **Fatti dal 3.8.2017 al 31.12.2019**: riforma Orlando — la prescrizione corre anche in appello, con le sospensioni fino a 18 mesi dopo la condanna di primo grado e altri 18 dopo quella d'appello (art. 159, co. 2 c.p. come modificato dalla L. 103/2017).
  - **Fatti dal 1.1.2020**: blocco Bonafede (L. 3/2019) — il corso della prescrizione cessa dopo la sentenza di primo grado; per i giudizi di impugnazione opera l'improcedibilità Cartabia ex art. 344-bis c.p.p. (introdotto dalla L. 134/2021, con attuazione nel D.Lgs. 150/2022).
- In ambito civile, il decorso della prescrizione può essere interrotto con atto stragiudiziale (raccomandata/PEC di messa in mora) — rimedio economico da suggerire quando lo stato è IN SCADENZA.
