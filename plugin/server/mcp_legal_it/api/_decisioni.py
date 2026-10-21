"""Decision functions of ``mcp_legal_it.api`` (see ``docs/api.md``).

One result shape for every court: ``EsitoDecisione`` for a decision read,
``RicercaDecisioni`` for a search (VisuaLex ``/fetch_decision`` and
``/search_decisions``). The text is given as the source serves it
(``testo_grezzo``); VisuaLex's block form (``testo``) is planned.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from urllib.parse import urlsplit
from typing import Iterable

from mcp_legal_it.api._comune import fonte_giu, registra
from mcp_legal_it.api.tipi import (
    Attributi,
    Avviso,
    Candidato,
    DecisioneTrovata,
    EsitoDecisione,
    FonteDecisione,
    Frammento,
    Identita,
    RicercaDecisioni,
    RiferimentoDecisione,
    TestoGrezzo,
)
from mcp_legal_it.core import cassazione
from mcp_legal_it.lib import _clock
from mcp_legal_it.lib.italgiure.client import (
    TIPO_PROV,
    build_norma_variants,
    build_search_params,
    format_estremi,
    quote_fq_value,
    resolve_sezione,
)

_CORTI = ("cassazione", "corte_costituzionale", "corte_giustizia_ue", "tribunale_ue",
          "consiglio_di_stato", "cgars", "tar")
_FONTE_CASSAZIONE = FonteDecisione(nome="Corte suprema di cassazione — Italgiure (SentenzeWeb)")
_FONTE_CONSULTA = FonteDecisione(nome="Corte costituzionale — open data")
_FONTE_CERDEF = FonteDecisione(nome="CeRDEF — Dipartimento delle Finanze")
_FONTE_GA = FonteDecisione(nome="Giustizia amministrativa")
_FONTE_CGUE = FonteDecisione(nome="CURIA — CELLAR (Ufficio delle pubblicazioni dell'UE)")


def _non_raggiungibile(fonte: FonteDecisione, exc: BaseException) -> EsitoDecisione:
    esito = "fonte_non_raggiungibile" if fonte_giu(exc) else "errore_fonte"
    return EsitoDecisione(esito=esito, fonte=fonte, errore=str(exc) or type(exc).__name__)


# ---------------------------------------------------------------------------
# Cassazione: Solr documents -> identita / attributi
# ---------------------------------------------------------------------------


def _v(doc: dict, key: str) -> str:
    val = doc.get(key)
    if isinstance(val, list):
        val = val[0] if val else ""
    return str(val).strip() if val is not None else ""


def _iso(raw: str) -> str | None:
    raw = (raw or "").strip()
    if len(raw) >= 8 and raw[:8].isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return "-".join(m.groups())
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _int(raw: str) -> int | str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    return int(raw) if raw.isdigit() else raw


def _identita_cass(doc: dict) -> Identita:
    kind = _v(doc, "kind")
    return Identita(
        corte="cassazione",
        numero=_int(_v(doc, "numdec")),
        anno=_int(_v(doc, "anno")) if _v(doc, "anno").isdigit() else None,
        archivio={"snciv": "civile", "snpen": "penale"}.get(kind),
    )


def _attributi_cass(doc: dict) -> Attributi:
    return Attributi(
        sezione=_v(doc, "szdec") or None,
        tipo=_v(doc, "tipoprov") or None,
        data_deposito=_iso(_v(doc, "datdep")),
        relatore=_v(doc, "relatore") or None,
        presidente=_v(doc, "presidente") or None,
        materia=_v(doc, "materia") or None,
        estremi=format_estremi(doc, con_tipo=True),
    )


_EM = re.compile(r"</?em>")


def _frammento(snippets: list[str] | None) -> Frammento | None:
    """A Solr highlight as text plus the [start, end) offsets of the highlighted words."""
    if not snippets:
        return None
    raw = snippets[0]
    testo, evidenziati, pos, start = [], [], 0, None
    for parte in re.split(r"(</?em>)", raw):
        if parte == "<em>":
            start = pos
        elif parte == "</em>":
            if start is not None:
                evidenziati.append((start, pos))
            start = None
        else:
            testo.append(parte)
            pos += len(parte)
    return Frammento(testo="".join(testo), evidenziati=tuple(evidenziati))


def _valida_numero_anno(numero, anno) -> dict[str, str]:
    errori: dict[str, str] = {}
    if not isinstance(numero, int) or isinstance(numero, bool) or not 1 <= numero <= 999_999:
        errori["numero"] = "atteso un intero tra 1 e 999999"
    if not isinstance(anno, int) or isinstance(anno, bool) or not 1800 <= anno <= _clock.today().year + 1:
        errori["anno"] = "atteso un anno intero plausibile"
    return errori


async def _leggi_cassazione(rif: RiferimentoDecisione) -> EsitoDecisione:
    archivio = rif.archivio or "tutti"
    if archivio not in ("tutti", "civile", "penale"):
        return EsitoDecisione(esito="richiesta_non_valida", errori={"archivio": "atteso 'civile' o 'penale'"})
    try:
        sezione, archivio = resolve_sezione(rif.sezione or "", archivio)
    except ValueError as exc:
        return EsitoDecisione(esito="richiesta_non_valida", errori={"sezione": str(exc)})
    with registra() as registro:
        try:
            docs, omonimi = await cassazione.lookup_decisione(rif.numero, rif.anno, sezione, archivio)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_non_raggiungibile(_FONTE_CASSAZIONE, exc), fonti=registro.fonti())
        if not docs:
            primo_anno, primo_giorno = await cassazione._italgiure_archive_start(archivio)
            if rif.anno < primo_anno:
                motivo = "fuori_archivio"
            elif rif.anno == primo_anno or rif.anno >= _clock.today().year:
                # The first year is only partly indexed, the current one lags behind:
                # a miss there proves nothing.
                motivo = "anno_parziale"
            else:
                motivo = "inesistente"
            return EsitoDecisione(esito="non_trovata", motivo=motivo, archivio_dal=primo_giorno or str(primo_anno),
                                  fonte=_FONTE_CASSAZIONE, fonti=registro.fonti())
        distinti = list({_v(d, "id"): d for d in docs}.values()) if omonimi else docs[:1]
        if len(distinti) > 1:
            return EsitoDecisione(
                esito="ambigua", fonte=_FONTE_CASSAZIONE, fonti=registro.fonti(),
                candidati=tuple(Candidato(identita=_identita_cass(d), attributi=_attributi_cass(d)) for d in distinti),
            )
        doc = distinti[0]
        avvisi: list[Avviso] = []
        effettiva = _v(doc, "szdec")
        if sezione and effettiva and effettiva != sezione:
            avvisi.append(Avviso("sezione_diversa", {"citata": rif.sezione, "effettiva": effettiva}))
        testo = _v(doc, "ocr")
        if not testo:
            avvisi.append(Avviso("testo_non_disponibile"))
        return EsitoDecisione(
            esito="trovata",
            identita=_identita_cass(doc),
            attributi=_attributi_cass(doc),
            fonte=_FONTE_CASSAZIONE,
            avvisi=tuple(avvisi),
            testo_grezzo=TestoGrezzo(testo=testo, dispositivo=_v(doc, "ocrdis") or None),
            fonti=registro.fonti(),
        )


# ---------------------------------------------------------------------------
# Corte costituzionale
# ---------------------------------------------------------------------------


def _identita_cost(numero, anno) -> Identita:
    return Identita(corte="corte_costituzionale", numero=_int(str(numero)), anno=_int(str(anno)) or None)


def _attributi_cost(p) -> Attributi:
    tipo = {"S": "sentenza", "O": "ordinanza"}.get((p.tipologia_pronuncia or "").upper(), p.tipologia_pronuncia or None)
    return Attributi(
        tipo=tipo,
        data_deposito=_iso(p.data_deposito),
        data_decisione=_iso(p.data_decisione),
        ecli=p.ecli or None,
        relatore=p.relatore_pronuncia or None,
        presidente=p.presidente or None,
    )


async def _leggi_consulta(rif: RiferimentoDecisione) -> EsitoDecisione:
    from mcp_legal_it.lib.corte_cost.client import fetch_pronuncia

    with registra() as registro:
        try:
            p = await fetch_pronuncia(rif.numero, rif.anno)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_non_raggiungibile(_FONTE_CONSULTA, exc), fonti=registro.fonti())
        if p is None:
            return EsitoDecisione(esito="non_trovata", motivo="inesistente", fonte=_FONTE_CONSULTA,
                                  fonti=registro.fonti())
        return EsitoDecisione(
            esito="trovata",
            identita=_identita_cost(p.numero_pronuncia, p.anno_pronuncia),
            attributi=_attributi_cost(p),
            fonte=_FONTE_CONSULTA,
            testo_grezzo=TestoGrezzo(testo=p.testo, epigrafe=p.epigrafe or None, dispositivo=p.dispositivo or None),
            avvisi=() if p.testo else (Avviso("testo_non_disponibile"),),
            fonti=registro.fonti(),
        )


async def leggi_decisione(riferimento: RiferimentoDecisione) -> EsitoDecisione:
    """One decision by court, number and year (VisuaLex ``/fetch_decision``).

    Served: ``cassazione`` (``archivio`` civile/penale, optional ``sezione``) and
    ``corte_costituzionale``. The other courts answer ``non_supportata``
    (planned): read them with their source key (``leggi_provvedimento_*``,
    ``leggi_sentenza_cgue``) from a search result.

    Esiti: ``trovata``; ``ambigua`` (``candidati``: same number and year in more
    than one archive or section); ``non_trovata`` with ``motivo``
    (``inesistente`` | ``fuori_archivio`` | ``anno_parziale``) and ``archivio_dal``;
    ``richiesta_non_valida`` (``errori``); ``fonte_non_raggiungibile``;
    ``errore_fonte``; ``non_supportata``.
    """
    if not isinstance(riferimento, RiferimentoDecisione):
        raise TypeError("atteso un RiferimentoDecisione")
    errori = _valida_numero_anno(riferimento.numero, riferimento.anno)
    if riferimento.corte not in _CORTI:
        errori["corte"] = "attesa una tra: " + ", ".join(_CORTI)
    if errori:
        return EsitoDecisione(esito="richiesta_non_valida", errori=errori)
    if riferimento.corte == "cassazione":
        return await _leggi_cassazione(riferimento)
    if riferimento.corte == "corte_costituzionale":
        return await _leggi_consulta(riferimento)
    return EsitoDecisione(
        esito="non_supportata",
        errore=f"lettura per numero e anno di '{riferimento.corte}': prevista dalla fase di migrazione",
    )


# ---------------------------------------------------------------------------
# Readers by source key
# ---------------------------------------------------------------------------

_NUM_ANNO = re.compile(r"n\.?\s*(\d+)(?:\s*/\s*(\d{4}))?", re.IGNORECASE)
_ANNO = re.compile(r"\b(19\d{2}|20\d{2})\b")


async def leggi_provvedimento_tributario(guid: str) -> EsitoDecisione:
    """A CeRDEF decision by the ``guid`` a tax-law search returned (massima + full text)."""
    from mcp_legal_it.lib.cerdef.client import CerdefNonTrovato, fetch_provvedimento

    if not guid or not str(guid).strip():
        return EsitoDecisione(esito="richiesta_non_valida", errori={"guid": "obbligatorio"})
    with registra() as registro:
        try:
            d = await fetch_provvedimento(guid)
        except CerdefNonTrovato as exc:
            return EsitoDecisione(esito="non_trovata", motivo="inesistente", fonte=_FONTE_CERDEF,
                                  errore=str(exc), fonti=registro.fonti())
        except ValueError as exc:
            return EsitoDecisione(esito="richiesta_non_valida", errori={"guid": str(exc)}, fonti=registro.fonti())
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_non_raggiungibile(_FONTE_CERDEF, exc), fonti=registro.fonti())
        m = _NUM_ANNO.search(d.estremi or "")
        a = _ANNO.search(d.estremi or "")
        anno = (m.group(2) if m and m.group(2) else None) or (a.group(1) if a else None)
        return EsitoDecisione(
            esito="trovata",
            identita=Identita(corte="giustizia_tributaria", numero=_int(m.group(1)) if m else None,
                              anno=int(anno) if anno else None, chiave_fonte=d.guid),
            attributi=Attributi(estremi=d.estremi or None),
            fonte=_FONTE_CERDEF,
            testo_grezzo=TestoGrezzo(testo=d.testo_integrale, massima=d.massima or None),
            avvisi=() if d.testo_integrale else (Avviso("testo_non_disponibile"),),
            fonti=registro.fonti(),
        )


def _corte_ga(sede: str) -> str:
    s = (sede or "").lower()
    if s in ("cds", "consiglio di stato", "consiglio_di_stato"):
        return "consiglio_di_stato"
    if s.startswith("cga") or s == "cgars":
        return "cgars"
    return "tar"


async def leggi_provvedimento_amministrativo(sede: str, nrg: str, nome_file: str) -> EsitoDecisione:
    """A TAR / Consiglio di Stato decision by the ``sede``, ``nrg``, ``nome_file`` a search returned."""
    from mcp_legal_it.lib.giustizia_amm.client import fetch_provvedimento_document

    errori = {k: "obbligatorio" for k, v in (("sede", sede), ("nrg", nrg), ("nome_file", nome_file)) if not v}
    if errori:
        return EsitoDecisione(esito="richiesta_non_valida", errori=errori)
    chiave = {"sede": sede, "nrg": nrg, "nome_file": nome_file}
    with registra() as registro:
        try:
            doc = await fetch_provvedimento_document(sede, nrg, nome_file)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_non_raggiungibile(_FONTE_GA, exc), fonti=registro.fonti())
        fonte = FonteDecisione(nome=_FONTE_GA.nome, url=doc.url or None)
        numero = (doc.meta or {}).get("numero", "")
        corte = _corte_ga(sede)
        identita = Identita(
            corte=corte,
            numero=_int(numero[4:]) if len(numero) > 4 and numero[:4].isdigit() else _int(numero),
            anno=int(numero[:4]) if len(numero) > 4 and numero[:4].isdigit() else None,
            sede=sede if corte == "tar" else None,
            provvedimento=((doc.meta or {}).get("tipologia") or "").lower() or None,
            chiave_fonte=chiave,
        )
        attributi = Attributi(tipo=(doc.meta or {}).get("tipologia") or None,
                              data_deposito=_iso((doc.meta or {}).get("data_pubblicazione", "")),
                              titolo=doc.title or None)
        if doc.pdf_only:
            return EsitoDecisione(esito="trovata", identita=identita, attributi=attributi, fonte=fonte,
                                  avvisi=(Avviso("testo_non_disponibile", {"motivo": "solo_pdf", "url": doc.url}),),
                                  testo_grezzo=None, fonti=registro.fonti())
        if not (doc.text or "").strip():
            return EsitoDecisione(esito="non_trovata", motivo="inesistente", fonte=fonte,
                                  errore="il portale ha risposto con una pagina di errore (riferimento non più valido?)",
                                  fonti=registro.fonti())
        return EsitoDecisione(esito="trovata", identita=identita, attributi=attributi, fonte=fonte,
                              testo_grezzo=TestoGrezzo(testo=doc.text), fonti=registro.fonti())


def _uri_cellar(uri) -> bool:
    """Only CELLAR resources are fetched: the URI comes from the caller, so any other
    host (an internal address, a metadata endpoint) is refused before any request."""
    if not isinstance(uri, str):
        return False
    try:
        parsed = urlsplit(uri.strip())
    except ValueError:
        return False
    return (
        parsed.scheme in ("http", "https")
        and parsed.hostname == "publications.europa.eu"
        and parsed.port in (None, 80, 443)
        and not parsed.username and not parsed.password
        and re.match(r"^/resource/(?:cellar|celex)/[\w.\-]+$", parsed.path or "") is not None
        and not parsed.query and not parsed.fragment
    )


_CAUSA = re.compile(r"^([CT])-(\d+)/(\d{2,4})")


async def leggi_sentenza_cgue(cellar_uri: str) -> EsitoDecisione:
    """A CJEU / General Court decision by the CELLAR URI a search returned (Italian text)."""
    from mcp_legal_it.lib.cgue.client import celex_of, fetch_case_metadata, fetch_sentenza_text

    if not _uri_cellar(cellar_uri):
        return EsitoDecisione(
            esito="richiesta_non_valida",
            errori={"cellar_uri": "atteso un URI di publications.europa.eu/resource/ (cellar/… o celex/…)"},
        )
    with registra() as registro:
        try:
            text = await fetch_sentenza_text(cellar_uri)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_non_raggiungibile(_FONTE_CGUE, exc), fonti=registro.fonti())
        stripped = (text or "").strip()
        if len(stripped) < 200:
            return EsitoDecisione(esito="non_trovata", motivo="inesistente", fonte=_FONTE_CGUE,
                                  errore="testo non disponibile da CELLAR (risposta vuota o pagina non valida)",
                                  fonti=registro.fonti())
        celex = celex_of(cellar_uri, stripped)
        try:
            meta = await fetch_case_metadata(celex) if celex else {}
        except Exception:  # noqa: BLE001 - metadata are best effort, as in the MCP tool
            meta = {}
        causa = meta.get("case_ref", "") or ""
        m = _CAUSA.match(causa)
        corte = "tribunale_ue" if (celex[5:7] if len(celex) > 7 else "").startswith("T") else "corte_giustizia_ue"
        anno = None
        if m:
            y = m.group(3)
            anno = int(y) if len(y) == 4 else int(("19" if int(y) > 50 else "20") + y)
        return EsitoDecisione(
            esito="trovata",
            identita=Identita(corte=corte, numero=_int(m.group(2)) if m else None, anno=anno,
                              chiave_fonte=cellar_uri),
            attributi=Attributi(ecli=meta.get("ecli") or None, data_decisione=_iso(meta.get("date", "")),
                                estremi=causa or celex or None),
            fonte=FonteDecisione(nome=_FONTE_CGUE.nome, url=cellar_uri),
            testo_grezzo=TestoGrezzo(testo=text),
            fonti=registro.fonti(),
        )


# ---------------------------------------------------------------------------
# Searches
# ---------------------------------------------------------------------------


def _anni(facet_counts: dict) -> tuple[dict[str, int], ...]:
    raw = (facet_counts or {}).get("facet_fields", {}).get("anno", []) or []
    coppie = [(raw[i], raw[i + 1]) for i in range(0, len(raw) - 1, 2)]
    return tuple({"anno": int(a), "n": int(n)} for a, n in sorted(coppie, key=lambda p: str(p[0]), reverse=True)
                 if str(a).isdigit())


async def cerca_decisioni_cassazione(
    tema: str | None = None,
    norma: str | None = None,
    *,
    archivio: str | None = None,
    pagina: int = 1,
    per_pagina: int = 20,
    anno_dal: int | None = None,
    anno_al: int | None = None,
    materia: str | None = None,
    sezione: str | None = None,
    solo_sezioni_unite: bool = False,
    tipo_provvedimento: str | None = None,
) -> RicercaDecisioni:
    """Search the Cassazione archive (VisuaLex ``/search_decisions``, ``modo="testo"``).

    *tema* is a full-text query; *norma* ("art. 2043 c.c.") restricts to decisions
    citing that article (alone: every decision that cites it). At least one is
    required. *pagina* starts at 1. No automatic relaxing or narrowing of the query
    (that is the MCP tool's agent aid): the answer is what the archive returns.
    ``modo="indice"`` (VisuaLex's index search) is planned.
    """
    errori: dict[str, str] = {}
    if not (tema and tema.strip()) and not (norma and norma.strip()):
        errori["tema"] = "indicare almeno uno tra tema e norma"
    if archivio not in (None, "civile", "penale"):
        errori["archivio"] = "atteso 'civile' o 'penale'"
    if not isinstance(pagina, int) or pagina < 1:
        errori["pagina"] = "atteso un intero da 1"
    if not isinstance(per_pagina, int) or not 1 <= per_pagina <= 50:
        errori["per_pagina"] = "atteso un intero tra 1 e 50"
    if tipo_provvedimento and tipo_provvedimento not in TIPO_PROV:
        errori["tipo_provvedimento"] = "attesi: " + ", ".join(sorted(TIPO_PROV))
    arch = archivio or "tutti"
    if not errori:
        try:
            sezione, arch = resolve_sezione(sezione or "", arch)
        except ValueError as exc:
            errori["sezione"] = str(exc)
    if errori:
        return RicercaDecisioni(esito="richiesta_non_valida", fonte="italgiure", errori=errori)
    start = (pagina - 1) * per_pagina
    if tema and tema.strip():
        params = build_search_params(
            cassazione._normalize_query(tema), archivio=arch, materia=materia or None, sezione=sezione or None,
            anno_da=anno_dal or None, anno_a=anno_al or None, tipo_provvedimento=tipo_provvedimento or None,
            solo_sezioni_unite=solo_sezioni_unite, rows=per_pagina, start=start, include_facets=True,
            fq_extra=[build_norma_variants(norma, strict=True)] if norma else None,
        )
    else:
        params = cassazione.params_su_norma(
            norma, archivio=arch, solo_sezioni_unite=solo_sezioni_unite, anno_da=anno_dal or 0,
            anno_a=anno_al or 0, max_risultati=per_pagina, pagina=pagina - 1,
        )
        extra = []
        if materia:
            extra.append(f"materia:{quote_fq_value(materia)}")
        if sezione:
            extra.append(f"szdec:{sezione}")
        if tipo_provvedimento:
            extra.append(f"tipoprov:{TIPO_PROV[tipo_provvedimento]}")
        if extra:
            params["fq"] = list(params.get("fq", [])) + extra
    with registra() as registro:
        try:
            data = await cassazione.query_con_ripiego(params)
            primo_anno, primo_giorno = await cassazione._italgiure_archive_start(arch)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return RicercaDecisioni(esito="fonte_non_raggiungibile" if fonte_giu(exc) else "errore_fonte",
                                    fonte="italgiure", errore=str(exc), fonti=registro.fonti())
        response = data.get("response", {})
        highlighting = data.get("highlighting", {}) or {}
        decisioni = []
        for doc in response.get("docs", []):
            hl = highlighting.get(_v(doc, "id")) or {}
            decisioni.append(DecisioneTrovata(
                identita=_identita_cass(doc), attributi=_attributi_cass(doc), trovata="testo",
                frammento=_frammento(hl.get("ocrdis") or hl.get("ocr")),
            ))
        return RicercaDecisioni(
            esito="risultati", fonte="italgiure", totale=response.get("numFound", 0), pagina=pagina,
            modo="testo", archivio=archivio, archivio_dal=primo_giorno or str(primo_anno),
            decisioni=tuple(decisioni), anni=_anni(data.get("facet_counts", {})), fonti=registro.fonti(),
        )


async def giurisprudenza_su_articolo(
    riferimento: str,
    *,
    archivio: str | None = None,
    pagina: int = 1,
    per_pagina: int = 20,
    anno_dal: int | None = None,
    anno_al: int | None = None,
    sezione: str | None = None,
    solo_sezioni_unite: bool = False,
) -> RicercaDecisioni:
    """Cassazione decisions citing an article ("art. 2043 c.c."): ``cerca_decisioni_cassazione(norma=...)``.

    An article without its act ("art. 13") matches any act's article 13: name the act.
    """
    return await cerca_decisioni_cassazione(
        norma=riferimento, archivio=archivio, pagina=pagina, per_pagina=per_pagina, anno_dal=anno_dal,
        anno_al=anno_al, sezione=sezione, solo_sezioni_unite=solo_sezioni_unite,
    )


def _ricerca_errore(fonte: str, exc: BaseException) -> RicercaDecisioni:
    if isinstance(exc, ValueError):
        return RicercaDecisioni(esito="richiesta_non_valida", fonte=fonte, errori={"parametri": str(exc)})
    return RicercaDecisioni(esito="fonte_non_raggiungibile" if fonte_giu(exc) else "errore_fonte",
                            fonte=fonte, errore=str(exc) or type(exc).__name__)


def _limite(n: int, massimo: int) -> int:
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("max_risultati deve essere un intero positivo")
    return min(n, massimo)


async def cerca_decisioni_costituzionali(
    tema: str, *, tipo: str | None = None, anno_dal: int | None = None, anno_al: int | None = None,
    max_risultati: int = 10,
) -> RicercaDecisioni:
    """Search Corte costituzionale decisions (open data). Without years only the current year is read.

    *tema*: terms, comma-separated alternatives. *tipo*: ``"sentenza"`` | ``"ordinanza"``.
    """
    from mcp_legal_it.lib.corte_cost.client import TIPOLOGIE, search_pronunce

    try:
        limite = _limite(max_risultati, 50)
    except ValueError as exc:
        return _ricerca_errore("corte_cost", exc)
    terms = [t.strip().lower() for t in (tema or "").split(",") if t.strip()]
    with registra() as registro:
        try:
            docs = await search_pronunce(terms=terms, tipo_code=TIPOLOGIE.get(tipo or "", ""),
                                         year_from=anno_dal or 0, year_to=anno_al or 0, limit=limite,
                                         current_year=_clock.today().year)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_ricerca_errore("corte_cost", exc), fonti=registro.fonti())
        return RicercaDecisioni(
            esito="risultati", fonte="corte_cost", totale=None, troncato=len(docs) >= limite,
            decisioni=tuple(DecisioneTrovata(identita=_identita_cost(p.numero_pronuncia, p.anno_pronuncia),
                                             attributi=_attributi_cost(p)) for p in docs),
            fonti=registro.fonti(),
        )


async def pronunce_costituzionali_su_norma(
    riferimento: str, *, anno_dal: int | None = None, anno_al: int | None = None, max_risultati: int = 10,
) -> RicercaDecisioni:
    """Corte costituzionale decisions whose massime invoke *riferimento* as a parameter.

    ``frammento`` is the massima's text; ``attributi.titolo`` its title.
    """
    from mcp_legal_it.lib.corte_cost.client import pronunce_su_norma

    try:
        limite = _limite(max_risultati, 50)
    except ValueError as exc:
        return _ricerca_errore("corte_cost", exc)
    with registra() as registro:
        try:
            hits = await pronunce_su_norma(riferimento=riferimento, year_from=anno_dal or 0, year_to=anno_al or 0,
                                           limit=limite, current_year=_clock.today().year)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_ricerca_errore("corte_cost", exc), fonti=registro.fonti())
        return RicercaDecisioni(
            esito="risultati", fonte="corte_cost", totale=None, troncato=len(hits) >= limite,
            decisioni=tuple(
                DecisioneTrovata(identita=_identita_cost(numero, anno),
                                 attributi=Attributi(titolo=massima.titolo or None),
                                 frammento=Frammento(testo=massima.testo) if massima.testo else None)
                for numero, anno, massima in hits
            ),
            fonti=registro.fonti(),
        )


async def cerca_decisioni_tributarie(
    tema: str, *, ente: str = "", tipo_provvedimento: str = "", data_da: str = "", data_a: str = "",
    numero: str = "", criterio: str = "tutti", ordinamento: str = "rilevanza", max_risultati: int = 10,
) -> RicercaDecisioni:
    """Search CeRDEF tax case law. Dates ``GG/MM/AAAA``. ``troncato``: the first-instance
    filter stopped at its scan limit, so fewer hits than asked is not "no more".
    ``identita.chiave_fonte`` is the guid for ``leggi_provvedimento_tributario``."""
    from mcp_legal_it.lib.cerdef.client import search_giurisprudenza

    try:
        limite = _limite(max_risultati, 250)
    except ValueError as exc:
        return _ricerca_errore("cerdef", exc)
    with registra() as registro:
        try:
            esito = await search_giurisprudenza(parole=tema, tipo_criterio=criterio, tipo_estremi=tipo_provvedimento,
                                                numero=numero, data_da=data_da, data_a=data_a, ente=ente,
                                                ordinamento=ordinamento, rows=limite)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_ricerca_errore("cerdef", exc), fonti=registro.fonti())
        decisioni = []
        for r in esito.risultati:
            m = _NUM_ANNO.search(r.estremi or "")
            a = _ANNO.search(r.data or "") or _ANNO.search(r.estremi or "")
            decisioni.append(DecisioneTrovata(
                identita=Identita(corte="giustizia_tributaria", numero=_int(m.group(1)) if m else None,
                                  anno=int(a.group(1)) if a else None, chiave_fonte=r.guid),
                attributi=Attributi(estremi=r.estremi or None, data_deposito=_iso(r.data), titolo=r.titoli or None,
                                    sezione=r.ente or None),
            ))
        return RicercaDecisioni(esito="risultati", fonte="cerdef", totale=esito.totale, troncato=esito.troncato,
                                decisioni=tuple(decisioni), fonti=registro.fonti())


async def cerca_decisioni_amministrative(
    tema: str, *, sede: str = "", tipo: str = "", anno: str = "", numero: str = "", max_risultati: int = 10,
) -> RicercaDecisioni:
    """Search TAR / Consiglio di Stato decisions. A year without a number is applied on the
    page the portal returned (the portal cannot filter by year alone): ``troncato`` then says
    the count may be partial. ``identita.chiave_fonte`` feeds ``leggi_provvedimento_amministrativo``."""
    from mcp_legal_it.lib.giustizia_amm.client import search_provvedimenti_page

    try:
        limite = _limite(max_risultati, 50)
    except ValueError as exc:
        return _ricerca_errore("giustizia_amm", exc)
    with registra() as registro:
        try:
            docs, totale = await search_provvedimenti_page(query=tema, tipo=tipo, sede=sede, anno=anno,
                                                           numero=numero, rows=limite)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_ricerca_errore("giustizia_amm", exc), fonti=registro.fonti())
        per_anno = bool(anno and anno.strip().isdigit()) and not numero
        if per_anno:
            docs = [d for d in docs if d.anno == anno.strip()]
        decisioni = []
        for d in docs:
            corte = _corte_ga(d.sede)
            num = d.numero or ""
            decisioni.append(DecisioneTrovata(
                identita=Identita(
                    corte=corte,
                    numero=_int(num[4:]) if len(num) > 4 and num[:4].isdigit() else _int(num),
                    anno=int(d.anno) if (d.anno or "").isdigit() else None,
                    sede=d.sede if corte == "tar" else None,
                    provvedimento=(d.tipo or "").lower() or None,
                    chiave_fonte={"sede": d.sede, "nrg": d.nrg, "nome_file": d.nome_file},
                ),
                attributi=Attributi(sezione=d.sezione or None, tipo=d.tipo or None, ecli=d.ecli or None,
                                    titolo=d.sede_label or None),
                frammento=Frammento(testo=d.oggetto) if d.oggetto else None,
            ))
        return RicercaDecisioni(esito="risultati", fonte="giustizia_amm", totale=None if per_anno else totale,
                                troncato=per_anno, decisioni=tuple(decisioni), fonti=registro.fonti())


def _decisione_cgue(c) -> DecisioneTrovata:
    m = _CAUSA.match(c.case_number or "")
    anno = None
    if m:
        y = m.group(3)
        anno = int(y) if len(y) == 4 else int(("19" if int(y) > 50 else "20") + y)
    return DecisioneTrovata(
        identita=Identita(corte="tribunale_ue" if c.court == "TJ" else "corte_giustizia_ue",
                          numero=_int(m.group(2)) if m else None, anno=anno, chiave_fonte=c.cellar_uri),
        attributi=Attributi(ecli=c.ecli or None, data_decisione=_iso(c.date), tipo=c.doc_type or None,
                            estremi=c.case_number or c.celex or None, titolo=c.title or None),
    )


async def cerca_decisioni_ue(
    tema: str, *, corte: str = "", tipo: str = "", anno_dal: str = "", anno_al: str = "", materia: str = "",
    max_risultati: int = 10,
) -> RicercaDecisioni:
    """Search CJEU / General Court decisions by title (CELLAR). *tema*: comma-separated alternatives.

    *corte*: ``"CJ"`` | ``"TJ"``; *tipo*: ``"JUDG"`` | ``"ORDER"`` | ``"OPIN_AG"``.
    ``identita.chiave_fonte`` is the CELLAR URI for ``leggi_sentenza_cgue``."""
    from mcp_legal_it.lib.cgue.client import search_giurisprudenza

    try:
        limite = _limite(max_risultati, 50)
    except ValueError as exc:
        return _ricerca_errore("cgue", exc)
    keywords = [k.strip() for k in (tema or "").split(",") if k.strip()]
    with registra() as registro:
        try:
            docs = await search_giurisprudenza(keywords=keywords, court=corte, doc_type=tipo, year_from=anno_dal,
                                               year_to=anno_al, materia=materia, limit=limite)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_ricerca_errore("cgue", exc), fonti=registro.fonti())
        return RicercaDecisioni(esito="risultati", fonte="cgue", totale=None, troncato=len(docs) >= limite,
                                decisioni=tuple(_decisione_cgue(c) for c in docs), fonti=registro.fonti())


async def giurisprudenza_ue_su_articolo(
    riferimento: str, *, corte: str = "", anno_dal: str = "", max_risultati: int = 10,
) -> RicercaDecisioni:
    """CJEU / General Court decisions whose title cites an EU provision ("art. 82 GDPR").

    Title search, not CELLAR citations: VisuaLex's ``/search_eu_case_law`` (by CELEX
    and article, over citations) is a different, planned query.
    """
    from mcp_legal_it.lib.cgue.client import normalize_riferimento, search_giurisprudenza

    terms = normalize_riferimento(riferimento or "")
    if not terms:
        return RicercaDecisioni(esito="richiesta_non_valida", fonte="cgue",
                                errori={"riferimento": 'indicare una norma UE (es. "art. 101 TFUE")'})
    try:
        limite = _limite(max_risultati, 50)
    except ValueError as exc:
        return _ricerca_errore("cgue", exc)
    with registra() as registro:
        try:
            docs = await search_giurisprudenza(keywords=[], required_terms=terms, court=corte, year_from=anno_dal,
                                               limit=limite)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return replace(_ricerca_errore("cgue", exc), fonti=registro.fonti())
        return RicercaDecisioni(esito="risultati", fonte="cgue", totale=None, troncato=len(docs) >= limite,
                                decisioni=tuple(_decisione_cgue(c) for c in docs), fonti=registro.fonti())


_FONTI_UNIFICATA = ("cassazione", "tributaria", "amministrativa", "ue")


async def cerca_giurisprudenza_unificata(
    tema: str, *, fonti: Iterable[str] = _FONTI_UNIFICATA, anno_dal: int | None = None,
    anno_al: int | None = None, max_risultati: int = 5,
) -> dict[str, RicercaDecisioni]:
    """The same query on several sources at once: ``{fonte: RicercaDecisioni}``.

    *fonti*: any of ``cassazione``, ``tributaria``, ``amministrativa``, ``ue``,
    ``costituzionale``. One source down is that entry's ``esito``, never a failure
    of the whole call. Each source is searched as its own function does.
    """
    scelte = [f for f in dict.fromkeys(fonti)]
    ignote = [f for f in scelte if f not in (*_FONTI_UNIFICATA, "costituzionale")]
    if ignote:
        raise ValueError(f"fonti sconosciute: {ignote}")
    n = max(1, min(max_risultati, 20))

    def coro(fonte: str):
        if fonte == "cassazione":
            return cerca_decisioni_cassazione(tema, anno_dal=anno_dal, anno_al=anno_al, per_pagina=n)
        if fonte == "tributaria":
            return cerca_decisioni_tributarie(tema, data_da=f"01/01/{anno_dal}" if anno_dal else "",
                                              data_a=f"31/12/{anno_al}" if anno_al else "", max_risultati=n)
        if fonte == "amministrativa":
            return cerca_decisioni_amministrative(tema, anno=str(anno_dal) if anno_dal and anno_dal == anno_al else "",
                                                  max_risultati=n)
        if fonte == "ue":
            return cerca_decisioni_ue(tema, anno_dal=str(anno_dal or ""), anno_al=str(anno_al or ""), max_risultati=n)
        return cerca_decisioni_costituzionali(tema, anno_dal=anno_dal, anno_al=anno_al, max_risultati=n)

    risultati = await asyncio.gather(*(coro(f) for f in scelte), return_exceptions=True)
    out: dict[str, RicercaDecisioni] = {}
    for fonte, r in zip(scelte, risultati):
        out[fonte] = r if isinstance(r, RicercaDecisioni) else RicercaDecisioni(
            esito="errore_fonte", fonte=fonte, errore=str(r) or type(r).__name__)
    return out


__all__ = [
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
]
