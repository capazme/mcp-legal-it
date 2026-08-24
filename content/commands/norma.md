---
name: norma
description: Cerca il testo vigente di un articolo di legge. Usa quando l'utente chiede di consultare, leggere o citare una norma (codice, legge, GDPR, ecc.).
argument-hint: "[riferimento normativo, es. 'art. 2043 c.c.' | 'art. 6 GDPR']"
tools: cite_law, cerca_brocardi, giurisprudenza_su_norma
---

Usa `cite_law` per cercare il testo vigente della norma richiesta dall'utente.

Se l'utente ha specificato un riferimento (es. "art. 2043 c.c.", "art. 6 GDPR"), chiamalo direttamente.
Se non ha specificato, chiedi quale norma vuole consultare.

Dopo il testo, chiedi se vuole anche le annotazioni Brocardi (`cerca_brocardi`) o la giurisprudenza collegata (`giurisprudenza_su_norma`).
