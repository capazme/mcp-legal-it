# Testing — mcp-legal-it

> Struttura dei test, strategia di mocking, configurazione pytest e guide per aggiungere nuovi test.

## Indice

- [Struttura directory](#struttura-directory)
- [Configurazione pytest](#configurazione-pytest)
- [Unit test — `tests/unit/`](#unit-test--testsunit)
  - [test_calculations.py](#test_calculationspy)
  - [test_legal_citations.py](#test_legal_citationspy)
  - [test_brocardi.py](#test_brocardipy)
  - [test_italgiure.py](#test_italgiurepy)
  - [test_gpdp.py](#test_gpdppy)
  - [test_privacy_gdpr.py](#test_privacy_gdprpy)
- [Comparison test — `tests/comparison/`](#comparison-test--testscomparison)
- [Comandi di esecuzione](#comandi-di-esecuzione)
- [Come aggiungere un nuovo test](#come-aggiungere-un-nuovo-test)

---

## Struttura directory

```
tests/
├── __init__.py
├── test-queries.md             # Query manuali di riferimento (non eseguiti da pytest)
├── unit/                       # Test senza connessione di rete
│   ├── __init__.py
│   ├── test_calculations.py    # Calcoli numerici: interessi, IRPEF, danni, parcelle
│   ├── test_legal_citations.py # cite_law: parse, resolve, build_nv, fetch (mock HTTP)
│   ├── test_brocardi.py        # Scraper Brocardi e tool cerca_brocardi (mock HTTP)
│   ├── test_italgiure.py       # Client Solr Italgiure e tool (mock HTTP)
│   ├── test_gpdp.py            # Client GPDP Garante e tool (mock HTTP)
│   └── test_privacy_gdpr.py    # 12 tool GDPR/Privacy: output, struttura, obbligatorietà
└── comparison/                 # Test contro valori attesi / servizi reali
    ├── __init__.py
    ├── conftest.py             # Fixture browser Playwright + marcatura @live
    ├── test_privacy_docs.py    # Verifica parametri normativi documenti GDPR (no live)
    └── test_*.py               # Test live contro avvocatoandreani.it e altri (skip default)
```

---

## Configurazione pytest

**File**: `pyproject.toml`

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"           # tutti i test async/await senza @pytest.mark.asyncio
testpaths = ["tests"]
addopts = "-m 'not live'"       # esclude test live per default
markers = [
    "live: live integration tests hitting real APIs"
]
```

**Comportamento default**: esegue solo i test senza marcatura `live` (unit test + comparison unit).

**Framework async**: `pytest-asyncio` in modalità `auto` — tutti i test `async def` sono eseguiti automaticamente senza decoratori aggiuntivi.

---

## Unit test — `tests/unit/`

### Strategia di mocking comune

I test di unit che invocano HTTP usano `unittest.mock`:

- `patch("httpx.AsyncClient")` — mock del client HTTP, sostituito con `AsyncMock`
- `AsyncMock` per `client.get()` e `client.post()` con risposta configurata
- `MagicMock(text=html_fixture)` per le risposte HTML con fixture inline

Per i tool MCP, le funzioni pubbliche sono decoratori `@mcp.tool()`. I test chiamano la funzione interna `fn` direttamente:

```python
def _call(module_path, fn_name, **kwargs):
    import importlib
    mod = importlib.import_module(module_path)
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)  # unwrap @mcp.tool() decorator
    return fn(**kwargs)
```

Per i tool async:
```python
result = await _call_async("src.tools.italgiure", "leggi_sentenza", numero=12345, anno=2024)
```

---

### test_calculations.py

**Cosa testa**: calcoli numerici puri, senza mock HTTP.

**Classi di test**:

| Classe | Modulo testato | Aspetti verificati |
|--------|----------------|-------------------|
| `TestInteressiLegali` | `tassi_interessi` | Calcolo semplici/composti, errore date invertite, struttura `periodi` |
| `TestCalcoloIrpef` | `dichiarazione_redditi` | Primo scaglione, reddito negativo, detrazioni lavoro dipendente |
| `TestDannoBiologico` | `risarcimento_danni` | Micro (≤9%), macro (>9%), ITT, ITP, age-bracket |
| `TestParcellaCivile` | `fatturazione_avvocati` | Scaglioni D.M. 55/2014, fase studio/introduttiva/istruttoria/decisoria |
| `TestContributoUnificato` | `atti_giudiziari` | Scaglioni CU, dimezzamento decreto ingiuntivo, raddoppio cassazione |
| `TestRivalutazione` | `rivalutazioni_istat` | Indici FOI, periodo multi-anno, edge case |
| `TestPrescrizione` | `varie` | Termini civili (5/10 anni), regime penale per data fatto |

---

### test_legal_citations.py

**Cosa testa**: parsing, risoluzione e fetch di citazioni normative. HTTP mockato.

**Fixtures HTML**: snippet HTML Normattiva e EUR-Lex inline nelle classi di test.

**Classi di test**:

| Classe | Cosa verifica |
|--------|---------------|
| `TestParseReference` | `_parse_reference()`: formato standard, senza punto, maiuscolo, estensioni bis/ter |
| `TestResolveAct` | `_resolve_act()`: alias comuni (GDPR, c.c., TUIR), resolve chain completa |
| `TestNormaUrl` | `Norma.url()`: Normattiva con articolo, EUR-Lex con CELEX, articoli bis/ter |
| `TestFetchArticle` | `fetch_article()` con mock HTTP: Normattiva AKN detailed/simple, EUR-Lex subdivision |
| `TestCiteLaw` | `_cite_law_impl()`: integrazione parse → resolve → fetch → format |
| `TestDownloadPdf` | `_download_law_pdf_impl()`: EUR-Lex PDF, Normattiva generato, safe_filename |

---

### test_brocardi.py

**Cosa testa**: scraper Brocardi e tool `cerca_brocardi`. HTTP mockato con HTML fixtures.

**Classi di test**:

| Classe | Cosa verifica |
|--------|---------------|
| `TestMassima` | Dataclass: `estremi`, `is_cassazione`, campi incompleti |
| `TestBrocardiResult` | `to_markdown()`, `cassazione_references`, error state |
| `TestParseSingleMassima` | `_parse_single_massima()`: autorità strutturata, fallback regex, Cass./Trib./CGUE |
| `TestExtractSections` | `_extract_all_sections()`: ratio, spiegazione, massime, adagi, glossario, footnotes |
| `TestFindArticleUrl` | `find_article_url()`: match diretto, sub-page search, cache persistente |
| `TestFetchBrocardi` | `fetch_brocardi()`: integration mock, errore tipo atto sconosciuto |
| `TestParseMassimeReferences` | `parse_massime_references()`: estrazione refs Cassazione, deduplicazione |
| `TestCercaBrocardiTool` | `_cerca_brocardi_impl()`: formato output markdown, chiamata interna |

---

### test_italgiure.py

**Cosa testa**: client Solr Italgiure e tool corrispondenti. HTTP mockato.

**Classi di test**:

| Classe | Cosa verifica |
|--------|---------------|
| `TestGetKindFilter` | Filtro collezione per archivio (civile/penale/tutti) |
| `TestBuildSearchParams` | Costruzione query Solr: `defType`, `fq`, highlight, range anni |
| `TestBuildLookupParams` | Lookup per numero+anno, zero-padding `numdec` |
| `TestBuildNormaVariants` | Varianti `"art. 2043 c.c."` → query Solr OR |
| `TestFormatDate` | Parsing date Solr `"YYYYMMDD"` → `"DD/MM/YYYY"` |
| `TestFormatEstremi` | Costruzione stringa estremi Cass. civ./pen. con sezione |
| `TestFormatSummary` | Formato compatto con highlight e senza |
| `TestFormatFullText` | Formato completo con troncamento OCR a 30.000 caratteri |
| `TestSolrQuery` | `solr_query()` con mock POST: session cookie, form encoding, doseq |
| `TestLeggiSentenzaImpl` | `_leggi_sentenza_impl()`: documento trovato, non trovato, multi-match |
| `TestCercaGiurisprudenzaImpl` | `_cerca_giurisprudenza_impl()`: risultati, paginazione, filtri |

---

### test_gpdp.py

**Cosa testa**: client GPDP (Garante Privacy) e tool. HTTP mockato con HTML Liferay.

**HTML fixtures**: struttura Bootstrap card layout Liferay (`div.card-risultato`, `a.titolo-risultato`, `div.data-risultato`).

**Classi di test**:

| Classe | Cosa verifica |
|--------|---------------|
| `TestBuildSearchParams` | Costruzione parametri Liferay portlet |
| `TestParseResults` | `_parse_results()`: titolo, date, tipologia, argomenti, abstract |
| `TestParseDoc` | `_parse_doc()`: rimozione script/nav/toolbar, estrazione titolo e body |
| `TestFormatResult` | `format_result()`: markdown con link DocWeb, troncamento abstract |
| `TestFormatFull` | `format_full()`: markdown completo, nota troncamento |
| `TestSearchDocs` | `search_docs()` con mock: paginazione automatica, limite 50 |
| `TestCercaProvvedimentiImpl` | `_cerca_provvedimenti_garante_impl()`: output formato, errore rete |
| `TestLeggiProvvedimentoImpl` | `_leggi_provvedimento_garante_impl()`: fetch print URL |

---

### test_privacy_gdpr.py

**Cosa testa**: i 12 tool GDPR/Privacy compliance (output testuale, struttura, elementi obbligatori).

**Approccio**: test dei tool senza mock HTTP — i tool GDPR generano documenti da template interno + file JSON, non richiedono fetch.

**Classi di test** (una per tool):

| Classe | Tool testato | Aspetti verificati |
|--------|--------------|-------------------|
| `TestGeneraInformativaPrivacy` | `genera_informativa_privacy` | Presenza titolare, finalità, base giuridica, diritti, contact Garante |
| `TestGeneraInformativaCookie` | `genera_informativa_cookie` | Tabella cookie tecnici, banner text, classificazione cookie |
| `TestGeneraInformativaDipendenti` | `genera_informativa_dipendenti` | Artt. 13 GDPR + Statuto Lavoratori, categorie dati dipendenti |
| `TestGeneraInformativaVideosorveglianza` | `genera_informativa_videosorveglianza` | Cartello EDPB, finalità sicurezza, retention |
| `TestGeneraDpa` | `genera_dpa` | 8 clausole obbligatorie art. 28(3), parti titolare/responsabile |
| `TestGeneraRegistroTrattamenti` | `genera_registro_trattamenti` | Campi art. 30, base giuridica, termine conservazione |
| `TestGeneraDpia` | `genera_dpia` | Matrice rischi, misure mitigazione, rischio residuo |
| `TestAnalisiBaseGiuridica` | `analisi_base_giuridica` | Raccomandazione motivata, riferimento art. 6/9 GDPR |
| `TestVerificaNecessitaDpia` | `verifica_necessita_dpia` | 9 criteri WP248, soglia ≥2, flag `dpia_necessaria` |
| `TestValutazioneDataBreach` | `valutazione_data_breach` | Livello rischio, obblighi notifica (72h Garante, comunicazione interessati) |
| `TestCalcoloSanzioneGdpr` | `calcolo_sanzione_gdpr` | Range tier1/tier2, calcolo su fatturato, fattori aggravanti/mitiganti |
| `TestGeneraNotificaDataBreach` | `genera_notifica_data_breach` | Modulo art. 33, scadenza 72h, campi obbligatori |

---

## Comparison test — `tests/comparison/`

**Scopo**: test di regressione numerica contro valori attesi calcolati manualmente o da fonti esterne.

**Marcatura**: i comparison test sono automaticamente marcati `@pytest.mark.live` dal `conftest.py` (tramite `pytest_collection_modifyitems`), **eccetto** i file in `_NO_LIVE_MARK` (attualmente solo `test_privacy_docs.py`).

**Eccezione — `test_privacy_docs.py`**: test unit-style che verifica che i documenti GDPR generati contengano i riferimenti normativi corretti (articoli, considerando, Reg. UE 2016/679). Non richiede connessione di rete.

**Altri test comparison**: richiedono Playwright e connessione a `avvocatoandreani.it` (calcolatore online di riferimento). Eseguiti solo in CI con flag `--run-live` o `-m live`.

---

## Comandi di esecuzione

```bash
# Attiva l'ambiente virtuale
source .venv/bin/activate   # macOS/Linux
# oppure: .venv\Scripts\activate  # Windows

# Tutti i test (esclude live) — esecuzione standard
pytest tests/ -m "not live"

# Solo unit test (esplicito)
pytest tests/unit/ -v

# Solo un file di test
pytest tests/unit/test_calculations.py -v

# Solo una classe
pytest tests/unit/test_brocardi.py::TestMassima -v

# Solo un test specifico
pytest tests/unit/test_calculations.py::TestInteressiLegali::test_basic_semplici -v

# Test live (richiedono connessione)
pytest tests/ -m "live" -v

# Test con output dettagliato (inclusi print e log)
pytest tests/unit/ -v -s

# Test con coverage
pytest tests/unit/ --cov=src --cov-report=html

# Test comparison senza live
pytest tests/comparison/test_privacy_docs.py -v
```

---

## Come aggiungere un nuovo test

### Per un nuovo tool di calcolo

```python
# tests/unit/test_nuovo_modulo.py

import pytest


def _call(module_path, fn_name, **kwargs):
    import importlib
    mod = importlib.import_module(module_path)
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestNuovoTool:

    def test_caso_base(self):
        r = _call("src.tools.nuovo_modulo", "nome_tool",
                  param1="valore1", param2=100)
        assert r["campo_atteso"] == pytest.approx(valore_atteso, abs=0.01)

    def test_input_invalido(self):
        r = _call("src.tools.nuovo_modulo", "nome_tool",
                  param1="")
        assert "errore" in r   # tutti i tool restituiscono {"errore": "..."} per input invalidi
```

### Per un tool con chiamate HTTP (mock)

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# HTML fixture
MOCK_HTML = """<html><body><div class="bodyTesto">...</div></body></html>"""


class TestNuovoToolHTTP:

    async def test_fetch_ok(self):
        mock_response = MagicMock()
        mock_response.text = MOCK_HTML
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from src.tools.nuovo_modulo import _nuova_funzione_impl
            result = await _nuova_funzione_impl(param="valore")

        assert result["campo"] == "valore atteso"
```

### Per un tool di libreria interna

```python
from src.lib.nuova_lib.client import NuovaFunzione, NuovoDataclass

class TestNuovaLib:

    def test_dataclass_fields(self):
        obj = NuovoDataclass(campo1="val", campo2=42)
        assert obj.campo1 == "val"
        assert obj.property_calcolata == "risultato atteso"
```

### Convenzioni da seguire

1. Un file di test per modulo/lib — nome `test_{modulo}.py`
2. Una classe di test per funzionalità — nome `Test{NomeFunzionalità}`
3. Ogni test verifica **una cosa sola** — nome esplicito `test_{scenario}_{risultato_atteso}`
4. I tool numerici usano `pytest.approx(valore, abs=0.01)` per tolleranza floating point
5. Per errori: verificare `"errore" in r` (pattern uniforme di tutti i tool)
6. I test HTTP **non** fanno chiamate reali — sempre mockare `httpx.AsyncClient`
7. Aggiungere `@pytest.mark.live` solo se il test richiede connessione di rete
