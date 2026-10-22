"""Which text of an EU regulation or directive is the text in force: the latest consolidation.

``cite_law("art. 111 Regolamento UE 2024/1689")`` served the Official Journal text of
12.7.2024, while Reg. (UE) 2026/1744 had amended art. 111 and EUR-Lex published the
consolidation 02024R1689-20260727 (issue #50). A request without a date asks for the
text in force, as it does for an Italian act, so an amended EU act is read from its
latest consolidation.

CELLAR says it in one SPARQL query per act: every consolidation of the act
(``cdm:act_consolidated_based_on_resource_legal``), its date
(``cdm:act_consolidated_date``) and the acts it consolidates
(``cdm:act_consolidated_consolidates_resource_legal``: the base act, the amending acts
and their corrigenda). A consolidation that consolidates nothing but the base act is the
Official Journal text again (Dir. 2019/790 has only 02019L0790-20190517), so the
Official Journal text is served then, authentic.

The answer is kept for a day in memory, keyed by the base act's CELEX; a failed query is
never kept. The query goes through the ``eur_lex`` source's network rules.

A consolidated text is EUR-Lex's documentation, not the authentic text: only the text
published in the Official Journal is. Every answer from a consolidation says so, and is
INDICATIVO (decision LI-031 keeps ESATTO for the authentic text).
"""

from __future__ import annotations

import re
import threading
import time

import httpx

from ...core._http import async_client
from .._http import retry_request

_SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
#: Short, and no retry: a hanging SPARQL endpoint must not hold every EU citation. The OJ
#: text is served anyway (fail open), and the failure is remembered for NEGATIVO_SECONDI.
_TIMEOUT = httpx.Timeout(12.0, connect=5.0)
_HEADERS = {"Accept": "application/sparql-results+json"}
TTL_SECONDI = 86400
NEGATIVO_SECONDI = 300

#: An OJ act's CELEX, the only thing interpolated into the query: sector 3, year, R or L, number.
_CELEX_BASE = re.compile(r"3\d{4}[RL]\d{4}", re.ASCII)
#: "32026R1744", "32026R1744R(01)" (a corrigendum): kind, year, number, corrigendum.
_CELEX_ATTO = re.compile(r"3(\d{4})([RLD])(\d{4})(R\(\d+\))?", re.ASCII)
_TIPI = {"R": "regolamento", "L": "direttiva", "D": "decisione"}

_cache: dict[str, tuple[float, "dict | None"]] = {}
_lock = threading.Lock()


def _query(celex: str) -> str:
    return f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?data_gu (MIN(?eif) AS ?in_vigore) ?celex ?data (GROUP_CONCAT(DISTINCT ?mc; separator="|") AS ?atti) WHERE {{
  ?atto cdm:resource_legal_id_celex "{celex}"^^xsd:string .
  OPTIONAL {{ ?atto cdm:official-journal-act_date_publication ?data_gu }}
  OPTIONAL {{ ?atto cdm:resource_legal_date_entry-into-force ?eif }}
  OPTIONAL {{
    ?c cdm:act_consolidated_based_on_resource_legal ?atto ;
       cdm:resource_legal_id_celex ?celex ;
       cdm:act_consolidated_date ?data .
    OPTIONAL {{ ?c cdm:act_consolidated_consolidates_resource_legal ?m . ?m cdm:resource_legal_id_celex ?mc . }}
  }}
}} GROUP BY ?data_gu ?celex ?data"""


def etichetta(celex: str) -> str:
    """«regolamento 2026/1744», «rettifica del regolamento 2026/1744»; the CELEX itself otherwise."""
    m = _CELEX_ATTO.fullmatch(celex or "")
    if not m:
        return celex
    nome = f"{_TIPI[m.group(2)]} {m.group(1)}/{int(m.group(3))}"
    return f"rettifica {'del' if m.group(2) == 'R' else 'della'} {nome}" if m.group(4) else nome


def leggi_risposta(celex_base: str, bindings: list[dict]) -> dict:
    """``{"data_gu", "in_vigore_dal", "versioni"}`` from the query's rows, newest consolidation first.

    ``data_gu`` is the act's publication in the Official Journal, ``in_vigore_dal`` its first
    entry into force. Each version is ``{"celex", "data", "modifiche": [{"celex", "atto"}]}``;
    the base act is not among its ``modifiche``. A consolidation whose CELEX is not this act's
    («0» + the base's year, type and number + «-YYYYMMDD») is dropped: it never reaches a URL.
    """
    data_gu, in_vigore, versioni = None, None, []
    propria = re.compile("0" + re.escape(celex_base[1:]) + r"-\d{8}", re.ASCII)
    for row in bindings:
        data_gu = data_gu or (row.get("data_gu") or {}).get("value")
        in_vigore = in_vigore or (row.get("in_vigore") or {}).get("value")
        celex = (row.get("celex") or {}).get("value")
        data = (row.get("data") or {}).get("value")
        if not celex or not data or not propria.fullmatch(celex):
            continue
        atti = sorted({a for a in ((row.get("atti") or {}).get("value") or "").split("|") if a and a != celex_base})
        versioni.append({"celex": celex, "data": data[:10],
                         "modifiche": [{"celex": a, "atto": etichetta(a)} for a in atti]})
    versioni.sort(key=lambda v: v["data"], reverse=True)
    return {"data_gu": data_gu[:10] if data_gu else None, "in_vigore_dal": in_vigore[:10] if in_vigore else None,
            "versioni": versioni}


async def consolidazioni(celex_base: str) -> "dict | None":
    """The act's consolidations (``leggi_risposta``), or None when CELLAR could not say."""
    if not _CELEX_BASE.fullmatch(celex_base or ""):
        return None
    adesso = time.time()
    with _lock:
        kept = _cache.get(celex_base)
        if kept is not None and adesso - kept[0] < (TTL_SECONDI if kept[1] is not None else NEGATIVO_SECONDI):
            return kept[1]
    try:
        async with async_client("eur_lex", timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await retry_request(client, "POST", _SPARQL_URL, dataset="eur_lex", max_retries=0,
                                       data={"query": _query(celex_base)})
            resp.raise_for_status()
            bindings = resp.json()["results"]["bindings"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        bindings = None
    if not bindings:
        # CELLAR could not say, or does not know the act: remembered a few minutes only, so a
        # down endpoint costs one wait per act, not one per citation.
        with _lock:
            _cache[celex_base] = (adesso, None)
        return None
    info = leggi_risposta(celex_base, bindings)
    with _lock:
        _cache[celex_base] = (adesso, info)
    return info


def scegli(info: dict, giorno: "str | None", oggi: "str | None" = None) -> tuple[str, "dict | None"]:
    """``("consolidato", version)``, ``("oj", None)`` or ``("prima", None)`` for the text asked for.

    The latest consolidation dated on or before *giorno* ("YYYY-MM-DD"), or before *oggi*
    without a date: a consolidation dated after today is a text not applicable yet
    (``futura``). A consolidation that amends nothing is the Official Journal text (``"oj"``),
    and so is a day before the first consolidation. A day before the act's publication in
    the Official Journal is ``"prima"``: the act did not exist.
    """
    if giorno and info.get("data_gu") and giorno < info["data_gu"]:
        return "prima", None
    limite = giorno or oggi
    candidate = [v for v in info.get("versioni", []) if not limite or v["data"] <= limite]
    if not candidate or not candidate[0]["modifiche"]:
        return "oj", None
    return "consolidato", candidate[0]


def futura(info: dict, oggi: str) -> "dict | None":
    """The earliest consolidation dated after *oggi* that amends the act, or None: VisuaLex's
    ``upcoming`` shape, ``{"change", "valid_from", "version_number", "celex"}``."""
    dopo = [v for v in info.get("versioni", []) if v["data"] > oggi and v["modifiche"]]
    if not dopo:
        return None
    v = min(dopo, key=lambda v: v["data"])
    return {"change": "amended", "valid_from": v["data"], "version_number": None, "celex": v["celex"]}


def avviso_futura(prossima: dict) -> str:
    return (f"EUR-Lex pubblica già una versione consolidata applicabile dal {prossima['valid_from']} "
            f"(CELEX {prossima['celex']}): il testo riportato è quello in vigore oggi")


def avviso_non_ancora_in_vigore(giorno: str, in_vigore_dal: str) -> str:
    return f"il {giorno} l'atto era pubblicato in GUUE ma non ancora in vigore (in vigore dal {in_vigore_dal})"


def avvisi(consolidato: "dict | None", verificato: "bool | None", giorno: "str | None",
           allegato_oj: bool = False) -> list[str]:
    """What the reader must know about an EU text: where it comes from, and what is authentic."""
    if allegato_oj:
        return ["allegato letto dal testo pubblicato in GUUE: le versioni consolidate degli allegati non sono "
                "ancora lette, quindi le modifiche successive non sono considerate e il testo potrebbe non "
                "essere quello vigente"]
    if verificato is False:
        return ["non è stato possibile verificare su EUR-Lex se esiste una versione consolidata: il testo "
                "riportato è quello pubblicato in GUUE e potrebbe non essere quello vigente"]
    if consolidato is None:
        return []
    modifiche = consolidato.get("modificato_da") or []
    # A lawyer reads «rettifica» and «modifica» differently: a consolidation that only
    # folds corrigenda in says so.
    solo_rettifiche = bool(modifiche) and all(_CELEX_ATTO.fullmatch(m["celex"] or "") and
                                              _CELEX_ATTO.fullmatch(m["celex"]).group(4) for m in modifiche)
    quale = ("testo consolidato EUR-Lex che incorpora le rettifiche pubblicate in GUUE" if solo_rettifiche
             else "testo consolidato EUR-Lex")
    righe = [f"{quale}, al {consolidato['data']} (CELEX {consolidato['celex']}): è "
             "documentazione, non fa fede; fa fede solo il testo pubblicato in GUUE"]
    if giorno:
        righe.append(f"versione consolidata al {consolidato['data']}, la più recente non successiva al {giorno}: "
                     "le consolidazioni di EUR-Lex possono seguire le modifiche con ritardo, verificare in GUUE "
                     "gli atti modificativi pubblicati dopo quella data")
    return righe
