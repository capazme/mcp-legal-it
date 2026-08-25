---
name: compliance-privacy
description: Assessment completo di compliance GDPR con analisi base giuridica, verifica DPIA, registro trattamenti, informativa privacy e DPA. Usa quando l'utente chiede compliance privacy, adeguamento GDPR, informativa privacy, registro trattamenti, DPIA, valutazione impatto, data breach o contratto con responsabile del trattamento.
tools: [analisi_base_giuridica, genera_dpa, genera_dpia, genera_informativa_cookie, genera_informativa_dipendenti, genera_informativa_privacy, genera_informativa_videosorveglianza, genera_registro_trattamenti, verifica_necessita_dpia]
prompt: {"name": "compliance_privacy", "description": "Workflow completo compliance privacy GDPR: analisi base giuridica, DPIA, registro, informativa e DPA", "args": [{"name": "titolare", "type": "str"}, {"name": "tipo_trattamento", "type": "str"}, {"name": "contesto", "type": "str"}]}
---

# Compliance Privacy GDPR

Assessment completo: base giuridica, DPIA, registro, informativa, DPA.

## Workflow

### 1. Analisi base giuridica

Chiama `analisi_base_giuridica` con tipo_trattamento e contesto.
Valori ammessi per `contesto`: B2C / B2B / dipendenti / pubblica_amministrazione / sanita / profilazione.
Identifica la base ex art. 6 GDPR. Se dati particolari (art. 9), attiva flag.
Annota la base consigliata per i passi successivi.

### 2. Verifica necessita DPIA

Chiama `verifica_necessita_dpia` con i criteri applicabili.
Valuta: profilazione, dati sensibili, monitoraggio sistematico, larga scala, soggetti vulnerabili, nuove tecnologie, scoring, incrocio dataset.

Se >= 2 criteri soddisfatti (WP248): DPIA obbligatoria.

### 2b. DPIA (se necessaria)

Chiama `genera_dpia` con rischi e misure di mitigazione.
Documenta la matrice dei rischi e il rischio residuo.

### 3. Registro trattamenti

Chiama `genera_registro_trattamenti` per scheda art. 30 GDPR.
Usa la base giuridica identificata al passo 1.

### 4. Informativa privacy

Chiama `genera_informativa_privacy` per informativa art. 13 GDPR.
Includi tutte le finalità, basi giuridiche, categorie di dati e destinatari.

Varianti disponibili:
- `genera_informativa_cookie` (cookie policy)
- `genera_informativa_dipendenti` (dipendenti)
- `genera_informativa_videosorveglianza` (videosorveglianza)

### 5. DPA (se responsabili esterni)

Se il trattamento coinvolge responsabili esterni (fornitori IT, cloud, commercialista, ecc.),
chiama `genera_dpa` per contratto art. 28 GDPR.

## Output atteso

Report intestato «Assessment Compliance GDPR — `titolare`», con le sezioni seguenti.

### 1. Base Giuridica
| Elemento | Dettaglio |
|----------|----------|
| Base consigliata | ... |
| Articolo | ... |
| Motivazione | ... |

### 2. DPIA
| Criterio | Soddisfatto | Descrizione |
|----------|-------------|-------------|
| ... | Sì/No | ... |
| **DPIA necessaria** | **Sì/No** | ... |

### 3. Registro Trattamenti
Scheda art. 30 con tutti i campi obbligatori.

### 4. Informativa Privacy
Testo completo dell'informativa art. 13 GDPR pronto per l'uso.

### 5. DPA
Contratto art. 28 GDPR (se applicabile).

### Checklist compliance
- [ ] Base giuridica identificata e documentata
- [ ] DPIA eseguita (se necessaria)
- [ ] Registro trattamenti aggiornato
- [ ] Informativa privacy redatta e pubblicata
- [ ] DPA stipulati con responsabili
- [ ] Misure di sicurezza (art. 32)
- [ ] Procedura data breach (artt. 33-34)

## Avvertenze

- Il presente assessment è uno strumento di supporto e non sostituisce la consulenza legale specializzata.
- Verificare sempre la normativa nazionale integrativa (D.Lgs. 196/2003 come modificato dal D.Lgs. 101/2018).
- Per trattamenti su larga scala o ad alto rischio, consultare il DPO e valutare una consultazione preventiva (art. 36 GDPR).
