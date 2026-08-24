CONSOB — GUIDA ALLA RICERCA DELIBERE E PROVVEDIMENTI
(Commissione Nazionale per le Società e la Borsa)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI
═══════════════════════════════════════════════════════════

| Tool | Uso | Parametri chiave |
|------|-----|------------------|
| `cerca_delibere_consob` | Ricerca nel bollettino | query, tipologia, argomento, data_da, data_a |
| `leggi_delibera_consob` | Testo completo delibera | numero (es. "23257") |
| `ultime_delibere_consob` | Ultime pubblicate | tipologia, argomento, max_risultati |

═══════════════════════════════════════════════════════════
TIPOLOGIE (filtro per tipo di provvedimento)
═══════════════════════════════════════════════════════════

| Chiave | Descrizione |
|--------|-------------|
| `delibere` | Delibere della Commissione |
| `comunicazioni` | Comunicazioni ufficiali |
| `provvedimenti_urgenti` | Provvedimenti d'urgenza |
| `opa` | Provvedimenti OPA |
| `regolamenti` | Regolamenti CONSOB |
| `interpelli` | Risposte a interpelli |
| `pareri` | Pareri resi dalla Commissione |

═══════════════════════════════════════════════════════════
ARGOMENTI (filtro per materia — ID Liferay)
═══════════════════════════════════════════════════════════

| Chiave | Descrizione | ID |
|--------|-------------|----|
| `abusi_di_mercato` | Market abuse, insider trading, manipolazione | 4989535 |
| `intermediari` | SIM, SGR, banche, consulenti | 4989527 |
| `emittenti` | Obblighi informativi società quotate | 4989652 |
| `mercati` | Struttura e regolamentazione mercati | 4989533 |
| `offerte_acquisto` | OPA, OPS, offerte pubbliche | 4989651 |
| `gestione_collettiva` | OICR, fondi, SICAV | 4989529 |
| `servizi_investimento` | MiFID II, adeguatezza, best execution | 4989531 |
| `cripto_attivita` | MiCA, crypto-asset, token | 4989653 |
| `crowdfunding` | Piattaforme, Reg. UE 2020/1503 | 4989654 |
| `vigilanza` | Attività di vigilanza generale | 4989534 |

═══════════════════════════════════════════════════════════
WORKFLOW CONSIGLIATI
═══════════════════════════════════════════════════════════

Ricerca tematica:
1. cerca_delibere_consob(query="tema") → lista delibere
2. leggi_delibera_consob(numero) → testo completo
3. cite_law("art. N TUF") → norma di riferimento

Monitoraggio novità:
1. ultime_delibere_consob() → ultime pubblicate
2. ultime_delibere_consob(argomento="intermediari") → per materia
3. leggi_delibera_consob(numero) → approfondimento

═══════════════════════════════════════════════════════════
NORMATIVA DI RIFERIMENTO MERCATI FINANZIARI
═══════════════════════════════════════════════════════════

| Fonte | Riferimento | Citazione | Materia |
|-------|-------------|-----------|---------|
| TUF | D.Lgs. 58/1998 | art. N TUF | Testo unico finanza |
| Reg. Emittenti | Reg. CONSOB 11971/1999 | — | Obblighi emittenti |
| Reg. Intermediari | Reg. CONSOB 20307/2018 | — | Servizi investimento |
| Reg. Mercati | Reg. CONSOB 20249/2017 | — | Struttura mercati |
| MAR | Reg. UE 596/2014 | art. N MAR | Abusi di mercato |
| MiFID II | Dir. 2014/65/UE | art. N MiFID II | Mercati strumenti fin. |
| MiFIR | Reg. UE 600/2014 | art. N MiFIR | Trasparenza mercati |
| MiCA | Reg. UE 2023/1114 | art. N MiCA | Cripto-attività |
| Crowdfunding | Reg. UE 2020/1503 | art. N Reg. 2020/1503 | Piattaforme crowdfunding |
| DORA | Reg. UE 2022/2554 | art. N DORA | Resilienza digitale |

Per il testo di queste norme: usare cite_law("art. N [fonte]").

═══════════════════════════════════════════════════════════
CROSS-REFERENCE GIURISPRUDENZA
═══════════════════════════════════════════════════════════

Per sentenze della Cassazione correlate a temi CONSOB:
1. cerca_giurisprudenza(query=""tema"", modalita="esplora") → distribuzione
2. Filtra con materia/sezione dai facets
3. leggi_sentenza(numero, anno) → testo integrale

Vedi risorsa: legal://riferimenti/ricerca-giurisprudenziale

═══════════════════════════════════════════════════════════
NOTE TECNICHE
═══════════════════════════════════════════════════════════

- Il numero delibera è nel formato numerico (es. "23257") o con suffisso (es. "23256-1")
- Le date nei filtri usano formato YYYY-MM-DD (es. "2024-01-01")
- Il testo delle delibere è troncato a 8000 caratteri per evitare saturazione del contesto
- La ricerca interroga il Bollettino CONSOB (Liferay Portal) — dati pubblici, nessuna autenticazione
