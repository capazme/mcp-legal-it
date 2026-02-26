---
name: compliance-privacy
description: Assessment completo compliance GDPR con analisi base giuridica, DPIA, registro trattamenti, informativa e DPA.
  Usa quando l'utente chiede un assessment privacy, deve adeguarsi al GDPR o vuole generare documentazione privacy.
argument-hint: "[titolare] [tipo trattamento] [contesto: B2C|B2B|dipendenti|PA|sanità|profilazione]"
---

# Workflow Compliance Privacy

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Raccolta dati
Identifica dall'input dell'utente:
- **Titolare del trattamento** (denominazione)
- **Tipo di trattamento** (raccolta dati clienti, marketing, videosorveglianza, etc.)
- **Contesto** (B2C, B2B, dipendenti, pubblica amministrazione, sanità, profilazione)

Se mancano dati essenziali, chiedi all'utente.

## Step 2 — Analisi base giuridica
Chiama `analisi_base_giuridica(tipo_trattamento, contesto, finalita)`.
Identifica la base giuridica appropriata ex art. 6 GDPR.
Se il trattamento coinvolge dati particolari (art. 9), attiva il flag `dati_particolari=true`.

## Step 3 — Verifica necessità DPIA
Chiama `verifica_necessita_dpia` con i criteri applicabili.
Valuta: profilazione, dati sensibili, monitoraggio sistematico, larga scala, soggetti vulnerabili, nuove tecnologie, scoring, incrocio dataset.

Se DPIA necessaria: chiama `genera_dpia` con i rischi identificati e le misure di mitigazione.

## Step 4 — Registro trattamenti
Chiama `genera_registro_trattamenti` per creare la scheda del trattamento ai sensi dell'art. 30.
Usa la base giuridica identificata al passo 2.

## Step 5 — Informativa privacy
Chiama `genera_informativa_privacy` per generare l'informativa ai sensi dell'art. 13 GDPR.
Includi tutte le finalità, basi giuridiche, categorie di dati e destinatari.

## Step 6 — DPA (se presenti responsabili del trattamento)
Se il trattamento coinvolge responsabili esterni (fornitori IT, cloud, commercialista, ecc.), chiama `genera_dpa` per generare il contratto ex art. 28 GDPR.

## Step 7 — Riepilogo

### Base Giuridica
| Elemento | Dettaglio |
|----------|----------|
| Base consigliata | ... |
| Articolo | ... |
| Motivazione | ... |

### DPIA
| Criterio | Soddisfatto | Descrizione |
|----------|-------------|-------------|
| ... | Sì/No | ... |
| **DPIA necessaria** | **Sì/No** | ... |

### Documentazione Generata
1. Registro trattamenti (art. 30)
2. Informativa privacy (art. 13)
3. DPIA (art. 35) — se necessaria
4. DPA (art. 28) — se applicabile

### Checklist Compliance
- [ ] Base giuridica identificata e documentata
- [ ] DPIA eseguita (se necessaria)
- [ ] Registro trattamenti aggiornato
- [ ] Informativa privacy redatta e pubblicata
- [ ] DPA stipulati con tutti i responsabili
- [ ] Misure di sicurezza adeguate (art. 32 GDPR)
- [ ] Procedura data breach predisposta (artt. 33-34 GDPR)

### Avvertenze
- Il presente assessment è uno strumento di supporto e non sostituisce la consulenza legale specializzata.
- Verificare sempre la normativa nazionale integrativa (D.Lgs. 196/2003 come modificato dal D.Lgs. 101/2018).
- Per trattamenti su larga scala o ad alto rischio, consultare il DPO.
