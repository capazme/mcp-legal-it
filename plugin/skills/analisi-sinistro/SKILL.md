---
name: analisi-sinistro
description: Usa quando l'utente descrive un incidente o sinistro, chiede risarcimento per invalidità o danni da lesioni — danno non patrimoniale ex art. 2059 c.c., rivalutazione ISTAT e interessi compensativi.
---

# Analisi Sinistro

Quantificazione del danno NON PATRIMONIALE da sinistro stradale, sanitario o lavorativo.

**Principio (Cass. SS.UU. 26972/2008, «San Martino»)**: il danno non patrimoniale è UNITARIO
(art. 2059 c.c.). Biologico, morale ed esistenziale sono aspetti di un unico pregiudizio, NON
poste autonome da sommare. Le tabelle (tabella unica nazionale e tabelle di Milano) liquidano un
valore COMPLESSIVO che comprende la componente morale (per la TUN: art. 138, co. 2, lett. e), CdA).

## Workflow

### 1. Danno non patrimoniale (valore complessivo, unitario)

Chiama UNA SOLA VOLTA `legal-it:danno_non_patrimoniale` con `percentuale_invalidita` (intero) e
`eta_vittima` (intero).

Quale tabella:
- **Circolazione di veicoli a motore e natanti, responsabilità sanitaria — macropermanenti (>9%)**:
  tabella unica nazionale (TUN, D.P.R. 13 gennaio 2025, n. 12, art. 138 CdA; per la sanità
  art. 7, co. 4, L. 24/2017). Il D.P.R. è in vigore dal 5 marzo 2025 (pubblicato in G.U. il
  18/2/2025) e si applica ai sinistri verificatisi dopo quella data (art. 5). I valori sono
  aggiornati ogni anno con decreto del Ministro delle imprese e del made in Italy (art. 138, co. 5,
  CdA): DM 10/12/2025 (G.U. 27/12/2025) e DM 28/9/2026 (G.U. 9/10/2026).
- **Stessi ambiti — micropermanenti (≤9%)**: art. 139 CdA (per la sanità, art. 7, co. 4, L. 24/2017).
- **Fuori dall'ambito diretto della TUN** (altri illeciti, sinistri anteriori al 5/3/2025): la
  liquidazione è equitativa (artt. 1226 e 2056 c.c.). Prima di scegliere tra TUN e tabelle di
  Milano, verifica l'orientamento di legittimità più recente con `legal-it:cerca_giurisprudenza` e motiva
  la scelta della tabella.
- Qualunque tabella usi, applica la versione vigente al momento della decisione (Cass. civ.,
  sez. III, n. 13539/2026).

Attenzione: per le macropermanenti `legal-it:danno_non_patrimoniale` restituisce una STIMA di ordine di
grandezza, che non è né la TUN né le tabelle di Milano: sostituiscila con il valore tabellare del
caso. Il valore tabellare comprende già il danno morale.

NON chiamare in aggiunta un tool di "danno morale" da sommare: duplicherebbe la componente già
inclusa (unitarietà del danno non patrimoniale).

### 1-bis. Infortunio sul lavoro

L'art. 139 CdA vale per le lesioni da circolazione di veicoli a motore e natanti (e per la sanità,
art. 7, co. 4, L. 24/2017), non per l'infortunio sul lavoro in quanto tale:
- L'INAIL indennizza il danno biologico con le proprie tabelle (art. 13 D.Lgs. 38/2000): usa
  `legal-it:risarcimento_inail`.
- Verso il datore di lavoro responsabile spetta solo il danno differenziale, cioè la parte che
  eccede le indennità INAIL (art. 10 D.P.R. 1124/1965), calcolata per poste omogenee: dal danno
  biologico civilistico si detrae solo la quota della rendita INAIL che ristora il danno biologico,
  non l'intera rendita (Cass. civ., sez. lav., n. 21196/2025). Il danno civilistico si liquida con
  i criteri della sezione 1 per gli illeciti fuori dall'ambito della TUN, non con l'art. 139.
- Se l'infortunio è anche un sinistro stradale (tipico l'infortunio in itinere, art. 2, co. 3,
  D.P.R. 1124/1965), verso il terzo responsabile si applicano gli artt. 138 e 139 CdA; l'INAIL che
  ha pagato è surrogato nei diritti dell'infortunato (art. 1916 c.c., ultimo comma; art. 142 CdA).

### 2. Personalizzazione (solo se motivata da circostanze eccezionali)

Solo in presenza di circostanze peculiari documentate, applica una personalizzazione ENTRO i tetti
massimi della tabella (calcolata sulla componente biologica), tramite `personalizzazione_pct`. NON
è una seconda voce cumulata: è un incremento del valore tabellare entro i limiti. In base al tipo:
- **Stradale**: dinamica relazionale (mobilità, lavoro, sport)
- **Sanitario**: sofferenza iatrogena da errore medico
- **Lavoro**: prima il passaggio INAIL e il danno differenziale (sezione 1-bis), poi l'incidenza
  sulla capacità lavorativa specifica

### 3. Rivalutazione monetaria (debito di valore)

Chiama `legal-it:rivalutazione_monetaria` dalla data del sinistro a oggi.

### 4. Interessi compensativi (Cass. SS.UU. 1712/1995)

NON calcolare gli interessi sul capitale INTERAMENTE rivalutato all'attualità: sarebbe la
sovra-compensazione censurata dalle SS.UU. Le tabelle danno valori attuali: prima DEVALUTA la somma
liquidata alla data del fatto, poi calcola gli interessi sulla somma PROGRESSIVAMENTE rivalutata
anno per anno o, in via semplificata (è una semplificazione di prassi, non una formula delle
SS.UU.), sul VALORE MEDIO tra somma devalutata e somma rivalutata: chiama `legal-it:interessi_legali` sulla
base `(somma_devalutata + somma_rivalutata) / 2`.

Gli interessi compensativi coprono il periodo dall'evento alla liquidazione. Il saggio maggiorato
dell'art. 1284, co. 4, c.c. non si applica all'obbligazione risarcitoria da fatto illecito, che è
un debito di valore (Cass. civ., sez. III, n. 6698/2026).

## Output atteso

| Voce | Importo |
|------|---------|
| Danno non patrimoniale (valore complessivo, morale incluso) | ... |
| Personalizzazione (se ricorrente, entro i tetti) | ... |
| Rivalutazione monetaria | ... |
| Interessi compensativi (su base media/progressiva) | ... |
| **TOTALE RISARCIMENTO** | **...** |

## Avvertenze da includere

- Danno non patrimoniale UNITARIO: una sola voce comprensiva del morale (SS.UU. 26972/2008) — non sommare biologico e morale come poste distinte.
- Interessi compensativi, previa devalutazione alla data del fatto, sulla somma progressivamente rivalutata / valore medio, MAI sul capitale già interamente rivalutato (SS.UU. 1712/1995).
- Valori INDICATIVI: micro ≤9% art. 139 CdA; macro >9% TUN per circolazione e sanità (sinistri dopo il 5/3/2025), altrimenti la tabella scelta e motivata. Per le macro il valore del tool è una stima da sostituire con quello tabellare. Non sostituiscono la valutazione medico-legale.
- Per ITT/ITP, danno emergente e lucro cessante servono dati aggiuntivi.
- Citare sempre la fonte tabellare e normativa.
