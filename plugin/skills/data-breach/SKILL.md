---
name: data-breach
description: Gestione data breach con valutazione rischio, notifica al Garante e stima sanzioni.
  Usa quando l'utente segnala una violazione di dati personali o chiede come gestire un data breach.
argument-hint: "[tipo violazione: confidenzialità|integrità|disponibilità] [numero interessati] [dati coinvolti]"
---

# Workflow Data Breach

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Raccolta dati sull'incidente
Identifica dall'input dell'utente:
- **Tipo di violazione**: confidenzialità (accesso non autorizzato), integrità (alterazione), disponibilità (perdita/distruzione)
- **Numero di interessati** coinvolti
- **Categorie di dati** violati (anagrafici, sanitari, finanziari, biometrici, etc.)
- **Causa della violazione** (attacco informatico, errore umano, guasto tecnico, etc.)
- **Data/ora della scoperta**
- **Misure di contenimento** già adottate

Se mancano dati essenziali, chiedi all'utente.

## Step 2 — Valutazione rischio
Chiama `valutazione_data_breach(tipo_violazione, numero_interessati, categorie_dati, ...)`.
Il tool valuta:
- Livello di rischio per gli interessati (basso, medio, alto, molto alto)
- Obbligo di notifica al Garante (art. 33 GDPR) — sì se rischio non improbabile
- Obbligo di comunicazione agli interessati (art. 34 GDPR) — sì se rischio elevato

## Step 3 — Notifica al Garante
Se la notifica è necessaria, chiama `genera_notifica_data_breach(titolare, tipo_violazione, ...)`.
Il tool genera il modulo con tutte le informazioni richieste dall'art. 33 GDPR.

**SCADENZA**: 72 ore dalla scoperta della violazione.

## Step 4 — Stima sanzioni
Chiama `calcolo_sanzione_gdpr(tipo_violazione, ...)` per stimare il range di sanzioni applicabili.
Analizza i criteri dell'art. 83(2) GDPR:
- Natura, gravità e durata della violazione
- Carattere doloso o colposo
- Misure adottate per attenuare il danno
- Precedenti violazioni
- Categorie di dati coinvolti

## Step 5 — Piano d'azione

### Valutazione Rischio
| Elemento | Dettaglio |
|----------|----------|
| Tipo violazione | ... |
| Interessati coinvolti | ... |
| Categorie dati | ... |
| **Livello di rischio** | **...** |
| Notifica Garante | Sì/No |
| Comunicazione interessati | Sì/No |

### Scadenze
| Adempimento | Scadenza | Stato |
|-------------|----------|-------|
| Notifica al Garante | 72h dalla scoperta | ... |
| Comunicazione agli interessati | Senza ingiustificato ritardo | ... |
| Annotazione nel registro violazioni | Immediata | ... |

### Range Sanzioni
| Scenario | Importo stimato |
|----------|----------------|
| Minimo | € ... |
| Medio | € ... |
| Massimo | € ... |

### Azioni Immediate
1. Contenere la violazione
2. Documentare l'incidente nel registro violazioni (art. 33(5) GDPR)
3. Notificare al Garante (se rischio non improbabile)
4. Comunicare agli interessati (se rischio elevato)
5. Adottare misure correttive per prevenire recidive

### Avvertenze
- La scadenza di 72h è tassativa — il ritardo va motivato.
- La mancata notifica è essa stessa una violazione sanzionabile.
- Documentare SEMPRE l'incidente, anche se non si notifica al Garante.
