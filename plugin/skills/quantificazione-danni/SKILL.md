---
name: quantificazione-danni
description: Quantifica danni biologici, patrimoniali o morali con personalizzazione e attualizzazione monetaria. Usa quando l'utente chiede di calcolare un risarcimento, quantificare danni da invalidita, danno emergente, lucro cessante o danno morale/esistenziale.
---

# Quantificazione Danni

Calcolo base, personalizzazione e attualizzazione.

## Workflow

### 1. Calcolo base

**Biologico** (percentuale invalidita):
- <= 9%: `legal-it:danno_biologico_micro` (tabelle art. 139 CdA)
- > 9%: `legal-it:danno_biologico_macro` (tabelle Milano)
- Parametri richiesti: percentuale di invalidita ed eta della vittima (l'eta incide sul demoltiplicatore tabellare)

**Patrimoniale** (importo):
- Danno emergente + lucro cessante
- Lucro cessante: calcola in base alla durata della privazione
- `legal-it:interessi_legali` dalla data evento

**Morale/esistenziale**:
- `legal-it:danno_non_patrimoniale` come base

### 2. Personalizzazione

Criteri Cass. SS.UU. 26972/2008: sofferenza soggettiva, vita di relazione, specificita del caso.

Indica una percentuale di personalizzazione motivata.

### 3. Attualizzazione

1. `legal-it:rivalutazione_monetaria` dalla data evento
2. `legal-it:interessi_legali` sulla somma rivalutata

## Formato output

Intestazione `## Quantificazione Danno` con il tipo di danno tra parentesi, poi la tabella a componenti:

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

## Avvertenze

- Quantificazione indicativa basata sulle tabelle vigenti. Per le macropermanenti (> 9%) in ambito RC auto e responsabilita sanitaria la liquidazione segue la Tabella Unica Nazionale ex art. 138 CdA (vincolante); le tabelle Milano restano il riferimento per i danni fuori dal perimetro del Codice delle Assicurazioni.
- La prova del danno patrimoniale richiede documentazione specifica.
- Per il danno biologico serve una perizia medico-legale.
