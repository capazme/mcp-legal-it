GDPR COMPLIANCE — CHECKLIST OPERATIVA
(Reg. UE 2016/679, D.Lgs. 196/2003 come mod. D.Lgs. 101/2018)

═══════════════════════════════════════════════════════════
1. MAPPATURA TRATTAMENTI (Art. 30)
═══════════════════════════════════════════════════════════

☐ Censimento di tutti i trattamenti di dati personali
☐ Per ogni trattamento, registrare:
  ☐ Finalità del trattamento
  ☐ Base giuridica (art. 6) → usa `analisi_base_giuridica()`
  ☐ Categorie di interessati
  ☐ Categorie di dati personali
  ☐ Destinatari (interni ed esterni)
  ☐ Termine di cancellazione
  ☐ Misure di sicurezza (art. 32)
☐ Compilare il registro trattamenti → usa `genera_registro_trattamenti()`
☐ Aggiornare il registro ad ogni variazione significativa

═══════════════════════════════════════════════════════════
2. BASI GIURIDICHE (Art. 6)
═══════════════════════════════════════════════════════════

| Base | Lettera | Contesto tipico | Tool |
|------|---------|-----------------|------|
| Consenso | art. 6(1)(a) | Marketing, profilazione, cookie | `analisi_base_giuridica()` |
| Contratto | art. 6(1)(b) | E-commerce, clienti, dipendenti | `analisi_base_giuridica()` |
| Obbligo legale | art. 6(1)(c) | Adempimenti fiscali, AML | `analisi_base_giuridica()` |
| Interesse vitale | art. 6(1)(d) | Emergenze sanitarie | `analisi_base_giuridica()` |
| Interesse pubblico | art. 6(1)(e) | PA, sanità pubblica | `analisi_base_giuridica()` |
| Legittimo interesse | art. 6(1)(f) | Sicurezza, antifrode, CRM | `analisi_base_giuridica()` |

Per dati particolari (art. 9): serve condizione aggiuntiva ex art. 9(2)

═══════════════════════════════════════════════════════════
3. INFORMATIVE (Artt. 13-14)
═══════════════════════════════════════════════════════════

☐ Informativa generale (sito web / clienti) → `genera_informativa_privacy(tipo="art13")`
☐ Informativa per dati da terzi → `genera_informativa_privacy(tipo="art14")`
☐ Informativa cookie → `genera_informativa_cookie()`
☐ Informativa dipendenti → `genera_informativa_dipendenti()`
☐ Informativa videosorveglianza (cartello + estesa) → `genera_informativa_videosorveglianza()`

Elementi obbligatori art. 13:
- Identità titolare e contatti
- Contatti DPO (se nominato)
- Finalità e base giuridica
- Destinatari
- Trasferimento extra-UE (se presente)
- Periodo di conservazione
- Diritti dell'interessato
- Diritto di reclamo al Garante

═══════════════════════════════════════════════════════════
4. RESPONSABILI DEL TRATTAMENTO (Art. 28)
═══════════════════════════════════════════════════════════

☐ Censire tutti i fornitori che trattano dati personali per conto del titolare
☐ Per ciascun responsabile, stipulare DPA → usa `genera_dpa()`
☐ Le 8 clausole obbligatorie (art. 28(3)):
  1. Trattamento solo su istruzioni documentate del titolare
  2. Riservatezza delle persone autorizzate
  3. Misure di sicurezza (art. 32)
  4. Condizioni per sub-responsabili
  5. Assistenza per diritti degli interessati
  6. Assistenza per sicurezza, breach, DPIA
  7. Cancellazione o restituzione alla cessazione
  8. Diritto di audit

═══════════════════════════════════════════════════════════
5. VALUTAZIONE D'IMPATTO — DPIA (Art. 35)
═══════════════════════════════════════════════════════════

☐ Verificare la necessità → usa `verifica_necessita_dpia()`
☐ Criteri WP248: se ≥2 su 9 → DPIA obbligatoria
☐ Se necessaria → usa `genera_dpia()` per documentarla

I 9 criteri WP248 rev.01:
1. Valutazione/scoring/profilazione
2. Decisione automatizzata con effetti giuridici
3. Monitoraggio sistematico
4. Dati sensibili o altamente personali
5. Trattamento su larga scala
6. Incrocio/combinazione di dataset
7. Soggetti vulnerabili
8. Nuove tecnologie
9. Impedimento all'esercizio di diritti

═══════════════════════════════════════════════════════════
6. DATA BREACH (Artt. 33-34)
═══════════════════════════════════════════════════════════

☐ Predisporre procedura interna per la gestione dei data breach
☐ In caso di violazione:
  ☐ Valutare il rischio → usa `valutazione_data_breach()`
  ☐ Se rischio per diritti e libertà → notifica al Garante entro 72 ore
  ☐ Se rischio elevato → comunicare agli interessati
  ☐ Generare il modulo di notifica → usa `genera_notifica_data_breach()`
☐ Registrare ogni violazione nel registro dei data breach (art. 33(5))

═══════════════════════════════════════════════════════════
7. SANZIONI (Art. 83)
═══════════════════════════════════════════════════════════

| Tipo violazione | Massimale |
|-----------------|-----------|
| Art. 83(4) — obblighi titolare/responsabile | € 10M o 2% fatturato |
| Art. 83(5) — principi, diritti, trasferimenti | € 20M o 4% fatturato |
| Art. 83(6) — inosservanza ordini autorità | € 20M o 4% fatturato |

Stima sanzioni → usa `calcolo_sanzione_gdpr()`

═══════════════════════════════════════════════════════════
8. SCADENZE E TERMINI
═══════════════════════════════════════════════════════════

| Adempimento | Termine | Norma |
|-------------|---------|-------|
| Notifica data breach al Garante | 72 ore dalla scoperta | Art. 33(1) |
| Risposta a richieste degli interessati | 30 giorni (prorogabili a 90) | Art. 12(3) |
| DPIA prima dell'avvio del trattamento | Preventiva | Art. 35(1) |
| Consultazione preventiva (se rischio residuo alto) | Prima del trattamento | Art. 36 |
| Aggiornamento registro trattamenti | Continuativo | Art. 30 |
| Revisione DPIA | Se cambiano rischi | Art. 35(11) |
