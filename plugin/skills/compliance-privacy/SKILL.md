---
name: compliance-privacy
description: Assessment completo di compliance GDPR con analisi base giuridica, verifica DPIA, registro trattamenti, informativa privacy e DPA. Usa quando l'utente chiede compliance privacy, adeguamento GDPR, informativa privacy, registro trattamenti, DPIA, valutazione impatto, data breach o contratto con responsabile del trattamento.
---

# Compliance Privacy GDPR

Assessment completo: base giuridica, DPIA, registro, informativa, DPA.

## Workflow

### 1. Analisi base giuridica

Chiama `legal-it:analisi_base_giuridica` con tipo_trattamento e contesto.
Identifica la base ex art. 6 GDPR. Se dati particolari (art. 9), attiva flag.

### 2. Verifica necessita DPIA

Chiama `legal-it:verifica_necessita_dpia` con i criteri applicabili.
Valuta: profilazione, dati sensibili, monitoraggio sistematico, larga scala, soggetti vulnerabili, nuove tecnologie, scoring, incrocio dataset.

Se >= 2 criteri soddisfatti (WP248): DPIA obbligatoria.

### 2b. DPIA (se necessaria)

Chiama `legal-it:genera_dpia` con rischi e misure di mitigazione.

### 3. Registro trattamenti

Chiama `legal-it:genera_registro_trattamenti` per scheda art. 30 GDPR.

### 4. Informativa privacy

Chiama `legal-it:genera_informativa_privacy` per informativa art. 13 GDPR.

Varianti disponibili:
- `legal-it:genera_informativa_cookie` (cookie policy)
- `legal-it:genera_informativa_dipendenti` (dipendenti)
- `legal-it:genera_informativa_videosorveglianza` (videosorveglianza)

### 5. DPA (se responsabili esterni)

Chiama `legal-it:genera_dpa` per contratto art. 28 GDPR.

## Output atteso

### Checklist compliance
- [ ] Base giuridica identificata e documentata
- [ ] DPIA eseguita (se necessaria)
- [ ] Registro trattamenti aggiornato
- [ ] Informativa privacy redatta
- [ ] DPA stipulati con responsabili
- [ ] Misure di sicurezza (art. 32)
- [ ] Procedura data breach (artt. 33-34)

## Tool aggiuntivi per incident

- `legal-it:valutazione_data_breach` — valutazione rischio e obblighi notifica
- `legal-it:genera_notifica_data_breach` — modulo notifica Garante (72h)
- `legal-it:calcolo_sanzione_gdpr` — stima range sanzioni art. 83

## Tool utilizzati

- `legal-it:analisi_base_giuridica`
- `legal-it:verifica_necessita_dpia`
- `legal-it:genera_dpia`
- `legal-it:genera_registro_trattamenti`
- `legal-it:genera_informativa_privacy` (+ varianti cookie, dipendenti, videosorveglianza)
- `legal-it:genera_dpa`
- `legal-it:valutazione_data_breach`
- `legal-it:genera_notifica_data_breach`
- `legal-it:calcolo_sanzione_gdpr`
