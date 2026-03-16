---
name: privacy
description: Genera documenti GDPR (informativa, DPA, DPIA, registro trattamenti)
allowed-tools: mcp__legal-it__genera_informativa_privacy, mcp__legal-it__genera_informativa_cookie, mcp__legal-it__genera_informativa_dipendenti, mcp__legal-it__genera_informativa_videosorveglianza, mcp__legal-it__genera_dpa, mcp__legal-it__genera_registro_trattamenti, mcp__legal-it__genera_dpia, mcp__legal-it__verifica_necessita_dpia, mcp__legal-it__analisi_base_giuridica, mcp__legal-it__cite_law
---

In base alla richiesta:

- **Informativa privacy**: Usa `legal-it:genera_informativa_privacy` (art. 13/14 GDPR).
- **Cookie policy**: Usa `legal-it:genera_informativa_cookie`.
- **Informativa dipendenti**: Usa `legal-it:genera_informativa_dipendenti`.
- **Informativa videosorveglianza**: Usa `legal-it:genera_informativa_videosorveglianza`.
- **DPA (responsabile trattamento)**: Usa `legal-it:genera_dpa` (art. 28 GDPR).
- **Registro trattamenti**: Usa `legal-it:genera_registro_trattamenti` (art. 30 GDPR).
- **DPIA**: Usa `legal-it:genera_dpia` (art. 35 GDPR). Prima verifica necessita con `legal-it:verifica_necessita_dpia`.
- **Base giuridica**: Usa `legal-it:analisi_base_giuridica`.

Se la richiesta e generica, chiedi quale documento serve. Verifica sempre le norme con `legal-it:cite_law`.
