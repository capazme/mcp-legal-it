---
name: privacy
description: Genera documenti GDPR (informativa, DPA, DPIA, registro trattamenti)
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
