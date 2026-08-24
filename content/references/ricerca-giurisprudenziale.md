RICERCA GIURISPRUDENZIALE — GUIDA ALL'USO DI ITALGIURE
(Archivio Cassazione, sentenze dal 2020 in poi)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI
═══════════════════════════════════════════════════════════

| Tool | Uso | Parametri chiave |
|------|-----|------------------|
| `cerca_giurisprudenza` | Ricerca full-text | query, modalita, campo, materia, sezione, tipo_provvedimento, archivio, max_risultati |
| `giurisprudenza_su_norma` | Sentenze su un articolo | riferimento, solo_sezioni_unite, anno_da, anno_a, archivio |
| `leggi_sentenza` | Testo completo | numero, anno, sezione, archivio |
| `ultime_pronunce` | Ultime depositate | materia, sezione, archivio |

═══════════════════════════════════════════════════════════
STRATEGIA: ESPLORA → FILTRA → LEGGI
═══════════════════════════════════════════════════════════

### Passo 1 — Esplora la distribuzione
```
cerca_giurisprudenza(query=""tema"", modalita="esplora")
```
Restituisce solo i facets (materia, sezione, anno, tipo provvedimento) SENZA documenti.
Serve per capire dove si concentrano i risultati prima di cercare.

### Passo 2 — Filtra con i facets
In base alla distribuzione, scegli i filtri:
- **Materia** dominante (>40%) → filtra per materia
- **Sezione** dominante (es. III per resp. civile) → filtra per sezione
- **Sezioni Unite** presenti → cercale separatamente (le più autorevoli)
- `tipo_provvedimento="sentenza"` → esclude ordinanze (meno motivate)

```
cerca_giurisprudenza(
    query=""tema"",
    materia="...",
    sezione="...",
    tipo_provvedimento="sentenza",
    max_risultati=10
)
```

### Passo 3 — Leggi le decisioni chiave
Per le 2-4 decisioni più rilevanti:
```
leggi_sentenza(numero=XXXXX, anno=2024)
```
Privilegia: Sezioni Unite > sentenze recenti > sentenze (non ordinanze).

═══════════════════════════════════════════════════════════
SINTASSI QUERY SOLR
═══════════════════════════════════════════════════════════

Il motore è Solr eDisMax. Sintassi supportata nel campo `query`:

| Sintassi | Effetto | Esempio |
|----------|---------|---------|
| `"frase esatta"` | Match testuale esatto | `"responsabilità medica"` |
| `AND` / `OR` | Operatori booleani (default: OR) | `"art. 2043" AND "danno"` |
| `-termine` | Esclude termine | `"onere prova" -lavoro` |
| `"frase"~3` | Prossimità (entro N parole) | `"nesso causale"~5` |
| `termin*` | Wildcard (prefisso) | `risarcim*` |

REGOLA: usare SEMPRE virgolette per frasi di 2+ parole correlate.

═══════════════════════════════════════════════════════════
PARAMETRO `campo`
═══════════════════════════════════════════════════════════

| Valore | Cerca in | Quando usare |
|--------|----------|--------------|
| (default) | Testo completo (OCR) | Ricerca ampia |
| `"dispositivo"` | Solo dispositivo | Più preciso, meno recall |

═══════════════════════════════════════════════════════════
FACETS DISPONIBILI
═══════════════════════════════════════════════════════════

| Facet | Descrizione | Esempio valori |
|-------|-------------|----------------|
| Materia | Area giuridica | Obbligazioni, Lavoro, Famiglia |
| Sezione | Sezione della Corte | I, II, III, lav., SU |
| Anno | Anno di deposito | 2020, 2021, ..., 2026 |
| Tipo provvedimento | Tipo decisione | sentenza, ordinanza |

═══════════════════════════════════════════════════════════
ARCHIVI
═══════════════════════════════════════════════════════════

| Archivio | Collezione Solr | Documenti |
|----------|----------------|-----------|
| `civile` | snciv | ~186K |
| `penale` | snpen | ~238K |
| `tutti` (default) | entrambi | ~424K |

═══════════════════════════════════════════════════════════
WORKFLOW TIPO
═══════════════════════════════════════════════════════════

Ricerca su tema:
1. cerca_giurisprudenza(query=""tema"", modalita="esplora")
2. Analizza facets → scegli filtri
3. cerca_giurisprudenza(query=""tema"", materia="...", sezione="...", max_risultati=10)
4. leggi_sentenza(numero, anno) per le 2-3 decisioni chiave
5. cite_law("art. ...") per le norme citate

Ricerca su norma specifica:
1. giurisprudenza_su_norma(riferimento="art. 2043 c.c.")
2. leggi_sentenza(numero, anno) per le decisioni chiave
3. cerca_brocardi("art. 2043 c.c.") per massime e dottrina

═══════════════════════════════════════════════════════════
NOTE TECNICHE
═══════════════════════════════════════════════════════════

- API: Solr REST su italgiure.giustizia.it (pubblica, nessuna autenticazione)
- OCR troncato a 30000 caratteri per evitare saturazione contesto
- Certificato SSL non valido → verify=False (necessario)
- Campi chiave: numdec (numero), anno, datdep (data deposito), szdec (sezione), ocr (testo)
