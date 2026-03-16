---
name: analisi-sinistro
description: Analizza sinistri stradali, sanitari e lavorativi con quantificazione completa del danno biologico, morale/esistenziale, rivalutazione ISTAT e interessi legali. Usa quando l'utente descrive un incidente, un sinistro, chiede risarcimento danni per invalidita o quantificazione danni da lesioni personali.
argument-hint: "[descrizione sinistro, percentuale invalidità, data]"
allowed-tools: mcp__legal-it__danno_biologico_micro, mcp__legal-it__danno_biologico_macro, mcp__legal-it__danno_non_patrimoniale, mcp__legal-it__rivalutazione_monetaria, mcp__legal-it__interessi_legali
---

# Analisi Sinistro

Quantificazione completa del danno da sinistro stradale, sanitario o lavorativo.

## Workflow

### 1. Danno biologico

Determina lo strumento in base alla percentuale di invalidita:

- **<= 9%**: chiama `legal-it:danno_biologico_micro` (tabelle art. 139 CdA)
- **> 9%**: chiama `legal-it:danno_biologico_macro` (tabelle Milano)

Parametri: `percentuale`, `eta`.

### 2. Danno non patrimoniale

Chiama `legal-it:danno_non_patrimoniale` per la componente morale/esistenziale.

Personalizza in base al tipo di sinistro:
- **Stradale**: incidenza su mobilita, lavoro, sport
- **Sanitario**: sofferenza da errore medico (componente iatrogena)
- **Lavoro**: incidenza sulla capacita lavorativa specifica

### 3. Rivalutazione monetaria

Chiama `legal-it:rivalutazione_monetaria` sugli importi dalla data del sinistro a oggi.

### 4. Interessi legali

Chiama `legal-it:interessi_legali` sul capitale rivalutato, dalla data del sinistro a oggi.

## Output atteso

Tabella riepilogativa:

| Voce | Importo |
|------|---------|
| Danno biologico (base tabellare) | ... |
| Personalizzazione (morale/esistenziale) | ... |
| Totale danno non patrimoniale | ... |
| Rivalutazione monetaria | ... |
| Interessi legali | ... |
| **TOTALE RISARCIMENTO** | **...** |

## Avvertenze da includere

- Valori su tabelle Milano (macro) o art. 139 CdA (micro <= 9%) — INDICATIVI
- Non sostituisce la valutazione medico-legale
- Per ITT/ITP, danno emergente e lucro cessante servono dati aggiuntivi
- Citare sempre la fonte tabellare e normativa
