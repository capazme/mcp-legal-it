---
name: quantificazione-danni
description: Usa quando l'utente chiede di calcolare un risarcimento o quantificare danni da invalidità, danno emergente, lucro cessante o danno morale — quantificazione con personalizzazione e attualizzazione.
---

# Quantificazione Danni

Calcolo base, personalizzazione e attualizzazione.

## Workflow

### 1. Calcolo base

**Biologico** (percentuale invalidita):
- <= 9%: `legal-it:danno_biologico_micro` (tabelle art. 139 CdA)
- > 9%: `legal-it:danno_biologico_macro` — restituisce una STIMA di ordine di grandezza, non la TUN né le tabelle di Milano: sostituiscila con il valore tabellare (vedi Avvertenze)
- Parametri richiesti: percentuale di invalidita ed eta della vittima (l'eta incide sul demoltiplicatore tabellare)

**Patrimoniale** (importo):
- Danno emergente + lucro cessante
- Lucro cessante: calcola in base alla durata della privazione
- Rivalutazione e interessi: vedi Attualizzazione (voci storiche)

**Morale/esistenziale**:
- `legal-it:danno_non_patrimoniale` come base

### 2. Personalizzazione

Criteri Cass. SS.UU. 26972/2008: sofferenza soggettiva, vita di relazione, specificita del caso.

Indica una percentuale di personalizzazione motivata.

### 3. Attualizzazione

Interessi compensativi (Cass. SS.UU. 1712/1995) mai sul capitale interamente rivalutato, che sarebbe una sovra-compensazione:
1. **Voci storiche** (danno patrimoniale espresso in moneta dell'epoca): `legal-it:rivalutazione_monetaria` dalla data evento con `con_interessi_legali=True`, che rivaluta e calcola gli interessi anno per anno sul capitale rivalutato. Non aggiungere altri interessi.
2. **Voci a valore attuale** (danno non patrimoniale da tabella): non rivalutarle di nuovo. Riconducile alla data del fatto con `legal-it:calcolo_devalutazione`, poi `legal-it:interessi_vari_capitale_rivalutato` sulla somma devalutata dalla data evento (solo `totale_interessi`); così Cass. civ., sez. III, n. 11614/2025 («previa devalutazione fino alla data del fatto illecito e rivalutazione di anno in anno»). In via semplificata (semplificazione di prassi, non formula delle SS.UU.): `legal-it:interessi_legali` sulla base `(somma_devalutata + valore_tabellare) / 2`.
3. Il saggio dell'art. 1284, co. 4, c.c. non si applica all'obbligazione risarcitoria da fatto illecito, debito di valore (Cass. civ., sez. III, n. 6698/2026)

## Formato output

Intestazione `## Quantificazione Danno` con il tipo di danno tra parentesi, poi la tabella a componenti:

| Componente | Importo |
|------------|---------|
| Danno base (tabellare/documentale) | € ... |
| Personalizzazione (±...%) | € ... |
| Subtotale | € ... |
| Rivalutazione ISTAT (solo voci storiche) | € ... |
| Interessi compensativi | € ... |
| **TOTALE** | **€ ...** |

### Motivazione

Spiega i criteri di personalizzazione adottati e la giurisprudenza di riferimento.

## Avvertenze

- Quantificazione indicativa. Per le macropermanenti (> 9%) da circolazione di veicoli e natanti o da responsabilità sanitaria si applica la tabella unica nazionale (D.P.R. 12/2025, art. 138 CdA; art. 7, co. 4, L. 24/2017) ai sinistri verificatisi dopo il 5/3/2025, data della sua entrata in vigore; i valori sono aggiornati ogni anno con decreto ministeriale (art. 138, co. 5, CdA; da ultimo DM 28/9/2026). Fuori da quell'ambito la liquidazione è equitativa (artt. 1226 e 2056 c.c.): verifica l'orientamento di legittimità più recente e motiva la scelta della tabella. Qualunque tabella si usi, va applicata la versione vigente al momento della decisione (Cass. civ., sez. III, n. 13539/2026).
- La prova del danno patrimoniale richiede documentazione specifica.
- Per il danno biologico serve una perizia medico-legale.
