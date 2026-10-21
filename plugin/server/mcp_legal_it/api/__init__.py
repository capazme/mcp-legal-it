"""mcp-legal-it as a library: the only stable surface (semver).

Italian norms and case law as plain functions with structured returns::

    import asyncio
    from mcp_legal_it import api

    t = asyncio.run(api.testo_articolo("art. 2043 c.c.", canale="html"))
    t.esito, t.article_text, t.norma_data.urn

Every network function is ``async`` and never raises for an expected outcome:
the result carries ``esito`` and ``errore`` (see ``docs/api.md``). Importing this
module does not import FastMCP or the MCP server, registers no tool and opens
no connection. Everything outside ``mcp_legal_it.api`` is internal and may
change in any release.

Infrastructure is injectable: ``configurazione(client_factory=..., cache_dir=...,
cache=False, brocardi=False)`` for a block, ``configura(...)`` for the process.
"""

from mcp_legal_it.api._decisioni import (
    cerca_decisioni_amministrative,
    cerca_decisioni_cassazione,
    cerca_decisioni_costituzionali,
    cerca_decisioni_tributarie,
    cerca_decisioni_ue,
    cerca_giurisprudenza_unificata,
    giurisprudenza_su_articolo,
    giurisprudenza_ue_su_articolo,
    leggi_decisione,
    leggi_provvedimento_amministrativo,
    leggi_provvedimento_tributario,
    leggi_sentenza_cgue,
    pronunce_costituzionali_su_norma,
)
from mcp_legal_it.api._norme import (
    ARTICLE_SUFFIX_ALTERNATION,
    SUFFISSI_ARTICOLO,
    albero_atto,
    annotazioni_brocardi,
    articolo_nell_albero,
    catalogo_alias,
    dove_altrove,
    indice_atto,
    leggi_riferimento,
    riferimento_da_parametri,
    testi_articoli,
    testo_articolo,
    testo_atto,
)
from mcp_legal_it.api.tipi import (
    AlberoAtto,
    AnnotazioniBrocardi,
    Attributi,
    Avviso,
    Candidato,
    Canale,
    CatalogoAlias,
    CodiceFonte,
    DecisioneTrovata,
    EsitoDecisione,
    EsitoLettura,
    EsitoNorma,
    EsitoRicerca,
    EsitoRiferimento,
    FonteConsultata,
    FonteDecisione,
    FontiConsultate,
    Frammento,
    Identita,
    IndiceAtto,
    MassimaBrocardi,
    NormaDati,
    RicercaDecisioni,
    RiferimentoDecisione,
    TestoArticolo,
    TestoAtto,
    TestoDecisione,
    TestoGrezzo,
    Vigenza,
    come_dict,
)
from mcp_legal_it.core._config import ClientFactory, Configurazione, configura, configurazione
from mcp_legal_it.core._http import con_regole

__all__ = [
    # configuration
    "ClientFactory",
    "Configurazione",
    "configura",
    "configurazione",
    "con_regole",
    # constants
    "ARTICLE_SUFFIX_ALTERNATION",
    "SUFFISSI_ARTICOLO",
    # norms
    "albero_atto",
    "annotazioni_brocardi",
    "articolo_nell_albero",
    "catalogo_alias",
    "dove_altrove",
    "indice_atto",
    "leggi_riferimento",
    "riferimento_da_parametri",
    "testi_articoli",
    "testo_articolo",
    "testo_atto",
    # decisions
    "cerca_decisioni_amministrative",
    "cerca_decisioni_cassazione",
    "cerca_decisioni_costituzionali",
    "cerca_decisioni_tributarie",
    "cerca_decisioni_ue",
    "cerca_giurisprudenza_unificata",
    "giurisprudenza_su_articolo",
    "giurisprudenza_ue_su_articolo",
    "leggi_decisione",
    "leggi_provvedimento_amministrativo",
    "leggi_provvedimento_tributario",
    "leggi_sentenza_cgue",
    "pronunce_costituzionali_su_norma",
    # types
    "AlberoAtto",
    "AnnotazioniBrocardi",
    "Attributi",
    "Avviso",
    "Candidato",
    "Canale",
    "CatalogoAlias",
    "CodiceFonte",
    "DecisioneTrovata",
    "EsitoDecisione",
    "EsitoLettura",
    "EsitoNorma",
    "EsitoRicerca",
    "EsitoRiferimento",
    "FonteConsultata",
    "FonteDecisione",
    "FontiConsultate",
    "Frammento",
    "Identita",
    "IndiceAtto",
    "MassimaBrocardi",
    "NormaDati",
    "RicercaDecisioni",
    "RiferimentoDecisione",
    "TestoArticolo",
    "TestoAtto",
    "TestoDecisione",
    "TestoGrezzo",
    "Vigenza",
    "come_dict",
]
