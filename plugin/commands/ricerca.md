---
name: ricerca
description: Ricerca giurisprudenza o normativa su un tema
---

In base alla richiesta dell'utente, scegli il tipo di ricerca:

**Giurisprudenza** (archivio Cassazione 2020+):
1. Prima esplora la distribuzione: `cerca_giurisprudenza(query="...", modalita="esplora")`
2. In base ai facets (materia, sezione, anno, tipo), cerca con filtri mirati
3. Usa virgolette per frasi esatte: `"responsabilità medica"` non `responsabilità medica`
4. Per match precisi: `campo="dispositivo"`
5. Per leggere una sentenza: `leggi_sentenza`

**Normativa**: Usa `cite_law` per le norme individuate. Integra con `cerca_brocardi` per annotazioni e massime.

**Garante Privacy**: Usa `cerca_provvedimenti_garante` per provvedimenti del GPDP.

**CONSOB**: Usa `cerca_delibere_consob` per delibere e provvedimenti.

Se la richiesta e generica, chiedi se vuole cercare giurisprudenza, normativa, provvedimenti Garante o delibere CONSOB.
