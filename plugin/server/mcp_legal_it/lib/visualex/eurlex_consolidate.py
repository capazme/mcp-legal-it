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
_TIMEOUT = httpx.Timeout(45.0, connect=15.0)
_HEADERS = {"Accept": "application/sparql-results+json"}
TTL_SECONDI = 86400

#: An OJ act's CELEX, the only thing interpolated into the query: sector 3, year, R or L, number.
_CELEX_BASE = re.compile(r"3\d{4}[RL]\d{4}", re.ASCII)
#: "32026R1744", "32026R1744R(01)" (a corrigendum): kind, year, number, corrigendum.
_CELEX_ATTO = re.compile(r"3(\d{4})([RLD])(\d{4})(R\(\d+\))?", re.ASCII)
_TIPI = {"R": "regolamento", "L": "direttiva", "D": "decisione"}

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def _query(celex: str) -> str:
    return f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?data_atto ?celex ?data (GROUP_CONCAT(DISTINCT ?mc; separator="|") AS ?atti) WHERE {{
  ?atto cdm:resource_legal_id_celex "{celex}"^^xsd:string .
  OPTIONAL {{ ?atto cdm:work_date_document ?data_atto }}
  OPTIONAL {{
    ?c cdm:act_consolidated_based_on_resource_legal ?atto ;
       cdm:resource_legal_id_celex ?celex ;
       cdm:act_consolidated_date ?data .
    OPTIONAL {{ ?c cdm:act_consolidated_consolidates_resource_legal ?m . ?m cdm:resource_legal_id_celex ?mc . }}
  }}
}} GROUP BY ?data_atto ?celex ?data"""


def etichetta(celex: str) -> str:
    """«regolamento 2026/1744», «rettifica del regolamento 2026/1744»; the CELEX itself otherwise."""
    m = _CELEX_ATTO.fullmatch(celex or "")
    if not m:
        return celex
    nome = f"{_TIPI[m.group(2)]} {m.group(1)}/{int(m.group(3))}"
    return f"rettifica {'del' if m.group(2) == 'R' else 'della'} {nome}" if m.group(4) else nome


def leggi_risposta(celex_base: str, bindings: list[dict]) -> dict:
    """``{"data_atto", "versioni"}`` from the query's rows, newest consolidation first.

    Each version is ``{"celex", "data", "modifiche": [{"celex", "atto"}]}``; the base act
    is not among its ``modifiche``.
    """
    data_atto, versioni = None, []
    for row in bindings:
        data_atto = data_atto or (row.get("data_atto") or {}).get("value")
        celex = (row.get("celex") or {}).get("value")
        data = (row.get("data") or {}).get("value")
        if not celex or not data:
            continue
        atti = sorted({a for a in ((row.get("atti") or {}).get("value") or "").split("|") if a and a != celex_base})
        versioni.append({"celex": celex, "data": data[:10],
                         "modifiche": [{"celex": a, "atto": etichetta(a)} for a in atti]})
    versioni.sort(key=lambda v: v["data"], reverse=True)
    return {"data_atto": data_atto[:10] if data_atto else None, "versioni": versioni}


async def consolidazioni(celex_base: str) -> "dict | None":
    """The act's consolidations (``leggi_risposta``), or None when CELLAR could not say."""
    if not _CELEX_BASE.fullmatch(celex_base or ""):
        return None
    adesso = time.time()
    with _lock:
        kept = _cache.get(celex_base)
        if kept is not None and adesso - kept[0] < TTL_SECONDI:
            return kept[1]
    try:
        async with async_client("eur_lex", timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await retry_request(client, "POST", _SPARQL_URL, dataset="eur_lex",
                                       data={"query": _query(celex_base)})
            resp.raise_for_status()
            bindings = resp.json()["results"]["bindings"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    if not bindings:
        # The act itself is not in CELLAR's answer: nothing is known, so nothing is kept.
        return None
    info = leggi_risposta(celex_base, bindings)
    with _lock:
        _cache[celex_base] = (adesso, info)
    return info


def scegli(info: dict, giorno: "str | None") -> tuple[str, "dict | None"]:
    """``("consolidato", version)``, ``("oj", None)`` or ``("prima", None)`` for the text asked for.

    Without *giorno*, the latest consolidation; on *giorno* ("YYYY-MM-DD"), the latest one
    dated on or before it. A consolidation that amends nothing is the Official Journal text
    (``"oj"``), and so is a day before the first consolidation. A day before the act's own
    date is ``"prima"``: the act did not exist.
    """
    if giorno and info.get("data_atto") and giorno < info["data_atto"]:
        return "prima", None
    candidate = [v for v in info.get("versioni", []) if not giorno or v["data"] <= giorno]
    if not candidate or not candidate[0]["modifiche"]:
        return "oj", None
    return "consolidato", candidate[0]


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
