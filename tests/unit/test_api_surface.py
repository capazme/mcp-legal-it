"""The public surface of ``mcp_legal_it.api`` is frozen here: names, signatures, fields.

``mcp_legal_it.api`` is the package's semver boundary (docs/api.md). Changing a
name, a parameter, a default or a field of a public type is a contract change:
this test fails until EXPECTED is updated on purpose, in the same change that
updates docs/api.md and the CHANGELOG (an addition is a minor release, a removal
or rename a major one after the deprecation period).

Regenerate EXPECTED with:
    python -c "from tests.unit._api_surface import describe_surface; import pprint; \
pprint.pprint(describe_surface(), width=200)"
"""

from ._api_surface import describe_surface

EXPECTED = {
    'ARTICLE_SUFFIX_ALTERNATION': "str = 'quinquiesdecies|septiesdecies|quaterdecies|sexiesdecies|octiesdecies|noviesdecies|duodevicies|quindecies|undevicies|quinquies|duodecies|terdecies|sexdecies|undecies|septies|quater|sexies|octies|novies|decies|vicies|nonies|vices|semel|bis|ter'",
    'AlberoAtto': 'dataclass(esito: EsitoNorma, articles: tuple[Any, ...] = ..., count: int = ..., metadata: dict[str, Any] = ..., url: str = ..., errore: str | None = ..., fonti: FontiConsultate | None = ..., consolidato: dict[str, Any] | None = ..., consolidato_verificato: bool | None = ...)',
    'AnnotazioniBrocardi': "dataclass(esito: Literal['trovato', 'brocardi_disattivato', 'riferimento_non_valido', 'atto_non_riconosciuto', 'non_supportata', 'errore_fonte', 'testo_assente'], url: str = ..., ratio: str = ..., spiegazione: str = ..., brocardi: tuple[str, ...] = ..., massime: tuple[MassimaBrocardi, ...] = ..., errore: str | None = ..., fonti: FontiConsultate | None = ...)",
    'AttoRisolto': "dataclass(esito: EsitoAtto, tipo_atto: str = ..., numero_atto: str = ..., data: str | None = ..., urn: str | None = ..., url: str | None = ..., precisione: Literal['ESATTO', 'INDICATIVO'] | None = ..., errore: str | None = ..., fonti: FontiConsultate | None = ...)",
    'Attributi': 'dataclass(sezione: str | None = ..., tipo: str | None = ..., data_deposito: str | None = ..., data_decisione: str | None = ..., ecli: str | None = ..., relatore: str | None = ..., presidente: str | None = ..., materia: str | None = ..., estremi: str | None = ..., titolo: str | None = ...)',
    'Avviso': 'dataclass(tipo: str, dettagli: dict[str, Any] = ...)',
    'Canale': "Literal('akn', 'html')",
    'Candidato': 'dataclass(identita: Identita, attributi: Attributi)',
    'CatalogoAlias': 'dataclass(presets: dict[str, dict[str, str]], known_acts: tuple[str, ...])',
    'ClientFactory': 'alias',
    'CodiceFonte': "Literal('cassazione', 'corte_costituzionale', 'curia', 'giustizia_amministrativa', 'cerdef')",
    'Configurazione': 'dataclass(client_factory: ClientFactory | None = ..., cache_dir: str | Path | None = ..., cache: bool | None = ..., brocardi: bool | None = ...)',
    'ConsiderandiAtto': 'dataclass(esito: EsitoNorma, considerando: tuple[dict[str, str], ...] = ..., url: str = ..., errore: str | None = ..., fonti: FontiConsultate | None = ...)',
    'DecisioneTrovata': "dataclass(identita: Identita, attributi: Attributi, trovata: Literal['indice', 'testo'] = ..., frammento: Frammento | None = ...)",
    'EsitoAtto': "Literal('trovato', 'atto_non_trovato', 'ambiguo', 'fonte_non_raggiungibile', 'errore_fonte', 'riferimento_non_valido', 'atto_non_riconosciuto', 'non_supportata')",
    'EsitoDecisione': 'dataclass(esito: EsitoLettura, identita: Identita | None = ..., attributi: Attributi | None = ..., testo: TestoDecisione | None = ..., fonte: FonteDecisione | None = ..., avvisi: tuple[Avviso, ...] = ..., candidati: tuple[Candidato, ...] = ..., motivo: str | None = ..., archivio_dal: str | None = ..., errori: dict[str, str] = ..., testo_grezzo: TestoGrezzo | None = ..., errore: str | None = ..., fonti: FontiConsultate | None = ...)',
    'EsitoLettura': "Literal('trovata', 'ambigua', 'non_trovata', 'richiesta_non_valida', 'fonte_non_raggiungibile', 'errore_fonte', 'non_supportata')",
    'EsitoNorma': "Literal('trovato', 'riferimento_non_valido', 'atto_non_riconosciuto', 'articolo_non_trovato', 'verifica_non_disponibile', 'testo_assente', 'errore_fonte', 'non_supportata')",
    'EsitoRicerca': "Literal('risultati', 'richiesta_non_valida', 'fonte_non_raggiungibile', 'errore_fonte', 'non_supportata')",
    'EsitoRiferimento': 'dataclass(esito: EsitoNorma, norma_data: tuple[NormaDati, ...] = ..., errore: str | None = ...)',
    'FonteConsultata': 'dataclass(fonte: str, url: str)',
    'FonteDecisione': 'dataclass(nome: str, licenza: str | None = ..., url: str | None = ..., codice: CodiceFonte | None = ...)',
    'FontiConsultate': 'dataclass(consultate_al: str, fonti: tuple[FonteConsultata, ...] = ...)',
    'Frammento': 'dataclass(testo: str, evidenziati: tuple[tuple[int, int], ...] = ...)',
    'Identita': 'dataclass(corte: str, numero: int | str | None, anno: int | None, archivio: str | None = ..., sede: str | None = ..., provvedimento: str | None = ..., chiave_fonte: str | dict[str, str] | None = ...)',
    'IndiceAtto': 'dataclass(esito: EsitoNorma, title: str = ..., rubriche: dict[str, str] = ..., abrogati: tuple[str, ...] = ..., parts: tuple[dict[str, Any], ...] = ..., count: int = ..., voci: tuple[str, ...] = ..., codice_redazionale: str = ..., data_gu: str = ..., url: str = ..., errore: str | None = ..., fonti: FontiConsultate | None = ..., consolidato: dict[str, Any] | None = ..., consolidato_verificato: bool | None = ...)',
    'MassimaBrocardi': 'dataclass(autorita: str = ..., numero: str = ..., anno: str = ..., testo: str = ...)',
    'NormaDati': 'dataclass(tipo_atto: str, data: str, numero_atto: str, url: str, allegato: str | None, numero_articolo: str, versione: str = ..., data_versione: str | None = ..., urn: str | None = ..., descrizione: str = ..., data_risolta: bool = ..., celex_consolidated: str | None = ...)',
    'RicercaDecisioni': "dataclass(esito: EsitoRicerca, fonte: str = ..., totale: int | None = ..., pagina: int = ..., modo: Literal['indice', 'testo'] = ..., archivio: str | None = ..., archivio_dal: str | None = ..., decisioni: tuple[DecisioneTrovata, ...] = ..., anni: tuple[dict[str, int], ...] = ..., troncato: bool = ..., errori: dict[str, str] = ..., errore: str | None = ..., fonti: FontiConsultate | None = ...)",
    'RiferimentoDecisione': "dataclass(corte: str, numero: int, anno: int, archivio: Literal['civile', 'penale'] | None = ..., sezione: str | None = ..., sede: str | None = ..., provvedimento: str | None = ..., tipo: Literal['sentenza', 'ordinanza', 'decreto'] | None = ...)",
    'SUFFISSI_ARTICOLO': "tuple = (('bis',), ('ter',), ('quater',), ('quinquies',), ('sexies',), ('septies',), ('octies',), ('novies', 'nonies'), ('decies',), ('undecies',), ('duodecies',), ('terdecies',), ('quaterdecies',), ('quinquiesdecies', 'quindecies'), ('sexiesdecies', 'sexdecies'), ('septiesdecies',), ('octiesdecies', 'duodevicies'), ('noviesdecies', 'undevicies'), ('vicies', 'vices'))",
    'TIPI_ATTO_VERIFICATI': "tuple = ('legge', 'decreto legislativo', 'decreto legge', 'decreto del presidente della repubblica', 'regio decreto', 'regio decreto legge', 'legge costituzionale')",
    'TestoArticolo': "dataclass(esito: EsitoNorma, article_text: str, norma_data: NormaDati | None, url: str, validity: Vigenza | None = ..., urn: str | None = ..., fonte: str = ..., canale: Canale = ..., data_consultazione: str = ..., errore: str | None = ..., fonti: FontiConsultate | None = ..., precisione: Literal['ESATTO', 'INDICATIVO'] | None = ..., avvisi: tuple[str, ...] = ..., successione: dict[str, str] | None = ..., upcoming: dict[str, Any] | None = ..., not_in_force: bool = ..., consolidato: dict[str, Any] | None = ..., consolidato_verificato: bool | None = ...)",
    'TestoAtto': 'dataclass(esito: EsitoNorma, testo: str = ..., titolo: str = ..., url: str = ..., errore: str | None = ..., fonti: FontiConsultate | None = ...)',
    'TestoDecisione': 'dataclass(motivazione: str, epigrafe: str | None = ..., dispositivo: str | None = ...)',
    'TestoGrezzo': 'dataclass(testo: str, epigrafe: str | None = ..., dispositivo: str | None = ..., massima: str | None = ...)',
    'Vigenza': "dataclass(state: Literal['current', 'historical', 'not_yet', 'abrogated'], valid_from: str | None = ..., valid_to: str | None = ..., version_number: int | None = ..., act_updated: str | None = ..., request_in_window: bool | None = ...)",
    'albero_atto': "async def(atto: 'str | NormaDati', *, link: 'bool' = False, dettagli: 'bool' = False) -> 'AlberoAtto'",
    'annotazioni_brocardi': "async def(riferimento: 'str') -> 'AnnotazioniBrocardi'",
    'articolo_nell_albero': "def(albero: 'AlberoAtto', articolo: 'str', allegato: 'str | None' = None) -> 'bool | None'",
    'catalogo_alias': "def() -> 'CatalogoAlias'",
    'cerca_decisioni_amministrative': "async def(tema: 'str', *, sede: 'str' = '', tipo: 'str' = '', anno: 'str' = '', numero: 'str' = '', max_risultati: 'int' = 10) -> 'RicercaDecisioni'",
    'cerca_decisioni_cassazione': "async def(tema: 'str | None' = None, norma: 'str | None' = None, *, archivio: 'str | None' = None, pagina: 'int' = 1, per_pagina: 'int' = 20, anno_dal: 'int | None' = None, anno_al: 'int | None' = None, materia: 'str | None' = None, sezione: 'str | None' = None, solo_sezioni_unite: 'bool' = False, tipo_provvedimento: 'str | None' = None) -> 'RicercaDecisioni'",
    'cerca_decisioni_costituzionali': "async def(tema: 'str', *, tipo: 'str | None' = None, anno_dal: 'int | None' = None, anno_al: 'int | None' = None, max_risultati: 'int' = 10) -> 'RicercaDecisioni'",
    'cerca_decisioni_tributarie': "async def(tema: 'str', *, ente: 'str' = '', tipo_provvedimento: 'str' = '', data_da: 'str' = '', data_a: 'str' = '', numero: 'str' = '', criterio: 'str' = 'tutti', ordinamento: 'str' = 'rilevanza', max_risultati: 'int' = 10) -> 'RicercaDecisioni'",
    'cerca_decisioni_ue': "async def(tema: 'str', *, corte: 'str' = '', tipo: 'str' = '', anno_dal: 'str' = '', anno_al: 'str' = '', materia: 'str' = '', max_risultati: 'int' = 10) -> 'RicercaDecisioni'",
    'cerca_giurisprudenza_unificata': "async def(tema: 'str', *, fonti: 'Iterable[str]' = ('cassazione', 'tributaria', 'amministrativa', 'ue'), anno_dal: 'int | None' = None, anno_al: 'int | None' = None, max_risultati: 'int' = 5) -> 'dict[str, RicercaDecisioni]'",
    'come_dict': "def(valore: 'Any') -> 'Any'",
    'con_regole': "def(fonte: 'str', transport: 'httpx.AsyncBaseTransport') -> 'httpx.AsyncBaseTransport'",
    'configura': "def(*, client_factory: 'ClientFactory | None | _NonIndicato' = NON_INDICATO, cache_dir: 'str | Path | None | _NonIndicato' = NON_INDICATO, cache: 'bool | None | _NonIndicato' = NON_INDICATO, brocardi: 'bool | None | _NonIndicato' = NON_INDICATO) -> 'Configurazione'",
    'configurazione': "def(*, client_factory: 'ClientFactory | None | _NonIndicato' = NON_INDICATO, cache_dir: 'str | Path | None | _NonIndicato' = NON_INDICATO, cache: 'bool | None | _NonIndicato' = NON_INDICATO, brocardi: 'bool | None | _NonIndicato' = NON_INDICATO) -> 'Iterator[Configurazione]'",
    'considerando': "async def(atto: 'str | NormaDati') -> 'ConsiderandiAtto'",
    'dove_altrove': "def(albero: 'AlberoAtto', articolo: 'str', allegato: 'str | None') -> 'str'",
    'giurisprudenza_su_articolo': "async def(riferimento: 'str', *, archivio: 'str | None' = None, pagina: 'int' = 1, per_pagina: 'int' = 20, anno_dal: 'int | None' = None, anno_al: 'int | None' = None, sezione: 'str | None' = None, solo_sezioni_unite: 'bool' = False) -> 'RicercaDecisioni'",
    'giurisprudenza_ue_su_articolo': "async def(riferimento: 'str', *, corte: 'str' = '', anno_dal: 'str' = '', max_risultati: 'int' = 10) -> 'RicercaDecisioni'",
    'indice_atto': "async def(atto: 'str | NormaDati') -> 'IndiceAtto'",
    'leggi_decisione': "async def(riferimento: 'RiferimentoDecisione') -> 'EsitoDecisione'",
    'leggi_provvedimento_amministrativo': "async def(sede: 'str', nrg: 'str', nome_file: 'str') -> 'EsitoDecisione'",
    'leggi_provvedimento_tributario': "async def(guid: 'str') -> 'EsitoDecisione'",
    'leggi_riferimento': "def(testo: 'str') -> 'EsitoRiferimento'",
    'leggi_sentenza_cgue': "async def(cellar_uri: 'str') -> 'EsitoDecisione'",
    'pronunce_costituzionali_su_norma': "async def(riferimento: 'str', *, anno_dal: 'int | None' = None, anno_al: 'int | None' = None, max_risultati: 'int' = 10) -> 'RicercaDecisioni'",
    'riferimento_da_parametri': "def(tipo_atto: 'str', numero_articolo: 'str' = '', data: 'str' = '', numero_atto: 'str' = '', allegato: 'str | None' = None, versione: 'str' = 'vigente', data_versione: 'str | None' = None, celex_consolidated: 'str | None' = None) -> 'EsitoRiferimento'",
    'risolvi_atto': "async def(tipo_atto: 'str', numero_atto: 'str', anno_o_data: 'str') -> 'AttoRisolto'",
    'testi_articoli': "async def(riferimenti: 'Iterable[str | NormaDati]', *, canale: 'Canale', concorrenza: 'int' = 4) -> 'list[TestoArticolo]'",
    'testo_articolo': "async def(riferimento: 'str | NormaDati', *, canale: 'Canale') -> 'TestoArticolo'",
    'testo_atto': "async def(atto: 'str | NormaDati') -> 'TestoAtto'",
}


def test_public_surface_is_frozen():
    actual = describe_surface()
    added = sorted(set(actual) - set(EXPECTED))
    removed = sorted(set(EXPECTED) - set(actual))
    changed = sorted(n for n in set(actual) & set(EXPECTED) if actual[n] != EXPECTED[n])
    assert not (added or removed or changed), (
        f"public API changed: added={added} removed={removed} changed="
        + "; ".join(f"{n}: {EXPECTED[n]} -> {actual[n]}" for n in changed)
    )


def test_every_public_name_is_documented():
    from pathlib import Path

    doc = (Path(__file__).resolve().parents[2] / "docs" / "api.md").read_text(encoding="utf-8")
    missing = [n for n in EXPECTED if f"`{n}" not in doc]
    assert not missing, f"names missing from docs/api.md: {missing}"
