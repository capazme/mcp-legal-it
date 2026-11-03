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
- **Fuori dall'ambito diretto della TUN** (altri illeciti, sinistri verificatisi fino al 5/3/2025
  compreso): la
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
  sulla capacità lavorativa specifica, ma SOLO per il suo aspetto non reddituale: maggiore usura,
  fatica e difficoltà nello svolgere il lavoro (c.d. cenestesi lavorativa), che è danno alla
  salute e si liquida nel danno biologico (Cass. civ., sez. III, ord. n. 16844/2023, che riferisce
  questo orientamento a postumi contenuti, orientativamente entro il 25%). La perdita
  di reddito non entra qui: è danno patrimoniale (sezione 2-bis).

### 2-bis. Danno patrimoniale da ridotta capacità di guadagno (voce separata)

La riduzione della capacità di produrre reddito (lucro cessante, presente e futuro) è una posta
PATRIMONIALE autonoma, da provare e liquidare a parte, fuori dal valore tabellare e dalla
personalizzazione. La percentuale di invalidità, o di «incapacità lavorativa specifica» stimata
dal CTU, non prova da sola la perdita di reddito: il danneggiato deve allegare e provare il lavoro
svolto (oppure una qualificazione professionale acquisita e non ancora esercitata), le mansioni e
l'impegno che richiedono, e la riduzione di reddito in atto o probabile; da questi fatti il
giudice può risalire anche per presunzioni, non per automatismo dai postumi (Cass. civ., sez. III,
ord. n. 25467/2025). Con invalidità molto elevate, che escludono qualunque attività lavorativa, la
perdita di guadagno va comunque liquidata come danno patrimoniale (Cass. n. 16844/2023). Senza
questi dati, segnala la voce come da istruire e non quantificarla.

Nell'infortunio sul lavoro, verso il datore di lavoro spetta solo il danno patrimoniale
differenziale, per poste omogenee: si liquida il lucro cessante civilistico, se ne detrae il valore
capitale della quota di rendita INAIL che indennizza le conseguenze patrimoniali (art. 13, co. 2,
lett. b, D.Lgs. 38/2000: menomazioni dal 16%) e si riconosce solo l'eccedenza; il danno emergente
provato non è coperto dalla rendita e non si riduce (Cass. civ., sez. lav., n. 21196/2025).

### 3. Devalutazione (debito di valore)

Il valore tabellare (nella versione vigente al momento della decisione) è già espresso in moneta
attuale: NON rivalutarlo di nuovo. Per calcolare gli interessi, riconducilo alla data del sinistro
con `legal-it:calcolo_devalutazione` (`importo_attuale` = valore tabellare comprensivo dell'eventuale
personalizzazione, `data_attuale` = oggi,
`data_passata` = data del sinistro). La somma devalutata è solo la base di calcolo: non si somma.

### 4. Interessi compensativi (Cass. SS.UU. 1712/1995)

NON calcolare gli interessi sul capitale INTERAMENTE rivalutato all'attualità: sarebbe la
sovra-compensazione censurata dalle SS.UU. Calcolali sulla somma devalutata e poi rivalutata anno
per anno (così Cass. civ., sez. III, n. 11614/2025: interessi compensativi «previa devalutazione
fino alla data del fatto illecito e rivalutazione di anno in anno»): chiama
`legal-it:interessi_vari_capitale_rivalutato` con `capitale` = somma devalutata, dalla data del sinistro a
oggi, e prendi solo `totale_interessi`. In via semplificata (è una semplificazione di prassi, non
una formula delle SS.UU.): `legal-it:interessi_legali` sulla base `(somma_devalutata + valore_tabellare) / 2` (valore tabellare
comprensivo dell'eventuale personalizzazione) dalla data del sinistro a oggi.

Gli interessi compensativi coprono il periodo dall'evento alla liquidazione. Il saggio maggiorato
dell'art. 1284, co. 4, c.c. non si applica all'obbligazione risarcitoria da fatto illecito, che è
un debito di valore (Cass. civ., sez. III, n. 6698/2026).

## Output atteso

| Voce | Importo |
|------|---------|
| Danno non patrimoniale (valore complessivo, morale incluso) | ... |
| Personalizzazione (se ricorrente, entro i tetti) | ... |
| Interessi compensativi (su somma devalutata e rivalutata anno per anno, o base media) | ... |
| Subtotale danno non patrimoniale (interessi inclusi) | ... |
| Danno patrimoniale da ridotta capacità di guadagno (voce separata, solo se provato) | ... |
| **TOTALE RISARCIMENTO** | **...** |

## Avvertenze da includere

- Danno non patrimoniale UNITARIO: una sola voce comprensiva del morale (SS.UU. 26972/2008) — non sommare biologico e morale come poste distinte.
- Interessi compensativi, previa devalutazione alla data del fatto, sulla somma progressivamente rivalutata / valore medio, MAI sul capitale già interamente rivalutato (SS.UU. 1712/1995).
- Valori INDICATIVI: micro ≤9% art. 139 CdA; macro >9% TUN per circolazione e sanità (sinistri dopo il 5/3/2025), altrimenti la tabella scelta e motivata. Per le macro il valore del tool è una stima da sostituire con quello tabellare. Non sostituiscono la valutazione medico-legale.
- Capacità lavorativa specifica: nella personalizzazione solo l'incidenza non reddituale (usura, maggiore fatica); la perdita di reddito è danno patrimoniale separato, da provare.
- Per ITT/ITP, danno emergente e lucro cessante servono dati aggiuntivi.
- Citare sempre la fonte tabellare e normativa.
