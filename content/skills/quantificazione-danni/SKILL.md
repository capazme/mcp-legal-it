---
name: quantificazione-danni
description: Quantifica danni biologici, patrimoniali o morali con personalizzazione e attualizzazione monetaria. Usa quando l'utente chiede di calcolare un risarcimento, quantificare danni da invalidita, danno emergente, lucro cessante o danno morale/esistenziale.
tools: [danno_biologico_macro, danno_biologico_micro, danno_non_patrimoniale, interessi_legali, rivalutazione_monetaria]
prompt: {"name": "quantificazione_danni", "description": "Quantificazione danni: biologico, patrimoniale o morale con personalizzazione e attualizzazione", "args": [{"name": "tipo_danno", "type": "str"}, {"name": "importo_o_percentuale", "type": "float"}, {"name": "eta_vittima", "type": "int"}]}
---

# Quantificazione Danni

Calcolo base, personalizzazione e attualizzazione.

## Workflow

### 1. Calcolo base

**Biologico** (percentuale invalidita):
- <= 9%: `danno_biologico_micro` (tabelle art. 139 CdA)
- > 9%: `danno_biologico_macro` (tabelle Milano)

**Patrimoniale** (importo):
- Danno emergente + lucro cessante
- `interessi_legali` dalla data evento

**Morale/esistenziale**:
- `danno_non_patrimoniale` come base

### 2. Personalizzazione

Criteri Cass. SS.UU. 26972/2008: sofferenza soggettiva, vita di relazione, specificita del caso.

### 3. Attualizzazione

1. `rivalutazione_monetaria` dalla data evento
2. `interessi_legali` sulla somma rivalutata
