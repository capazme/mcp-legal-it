---
name: privacy
description: Genera documenti GDPR (informativa privacy/cookie/dipendenti/videosorveglianza, DPA, registro trattamenti, DPIA, analisi base giuridica). Usa quando l'utente chiede di generare un documento privacy, un'informativa, un DPA, una DPIA o un registro dei trattamenti.
argument-hint: "[tipo documento] [titolare] [dettagli]"
tools: genera_informativa_privacy, genera_informativa_cookie, genera_informativa_dipendenti, genera_informativa_videosorveglianza, genera_dpa, genera_registro_trattamenti, genera_dpia, verifica_necessita_dpia, analisi_base_giuridica, cite_law
---

In base alla richiesta:

- **Informativa privacy**: Usa `genera_informativa_privacy` (art. 13/14 GDPR).
- **Cookie policy**: Usa `genera_informativa_cookie`.
- **Informativa dipendenti**: Usa `genera_informativa_dipendenti`.
- **Informativa videosorveglianza**: Usa `genera_informativa_videosorveglianza`.
- **DPA (responsabile trattamento)**: Usa `genera_dpa` (art. 28 GDPR).
- **Registro trattamenti**: Usa `genera_registro_trattamenti` (art. 30 GDPR).
- **DPIA**: Usa `genera_dpia` (art. 35 GDPR). Prima verifica necessita con `verifica_necessita_dpia`.
- **Base giuridica**: Usa `analisi_base_giuridica`.

Se la richiesta e generica, chiedi quale documento serve. Verifica sempre le norme con `cite_law`.
