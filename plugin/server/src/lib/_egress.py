"""The complete list of hosts this server may contact, and who owns each one.

A lawyer evaluating this project has to answer one question before running it
on client matters: where does my data go. Answering it by reading the code is
days of work, and answering it with a promise in a README is worth nothing. So
the answer lives here, as data, and `tests/unit/test_egress_allowlist.py`
fails the build if a URL literal appears in `src/` for a host not listed —
which is what makes it an assertion rather than a claim.

The server sends no telemetry and has no analytics endpoint. Every host below
is a public institutional source consulted to answer a specific question.
"""

from __future__ import annotations

from urllib.parse import urlparse

#: Hosts the running server may contact, mapped to who operates them.
ALLOWED_HOSTS: dict[str, str] = {
    # --- Italian State: legislation ---
    "www.normattiva.it": "Normattiva — Istituto Poligrafico e Zecca dello Stato",
    "www.gazzettaufficiale.it": "Gazzetta Ufficiale — IPZS",
    # --- Italian State: case law ---
    "www.italgiure.giustizia.it": "Corte di cassazione — Ministero della giustizia",
    "www.giustizia-amministrativa.it": "Giustizia amministrativa (TAR/CdS)",
    "mdp.giustizia-amministrativa.it": "Giustizia amministrativa — testi integrali",
    "dati.cortecostituzionale.it": "Corte costituzionale — open data",
    "def.finanze.it": "CeRDEF — Ministero dell'economia e delle finanze",
    # --- Italian State: parliament ---
    "dati.senato.it": "Senato della Repubblica — open data (SPARQL)",
    "dati.camera.it": "Camera dei deputati — open data (SPARQL)",
    # --- Italian State: authorities ---
    "www.garanteprivacy.it": "Garante per la protezione dei dati personali",
    "servizi.gpdp.it": "Garante privacy — servizi",
    "www.consob.it": "CONSOB",
    # --- European Union ---
    "eur-lex.europa.eu": "EUR-Lex — Ufficio delle pubblicazioni UE",
    "publications.europa.eu": "CELLAR/SPARQL — Ufficio delle pubblicazioni UE",
    "ec.europa.eu": "VIES — Commissione europea (validazione partite IVA)",
    # --- Private ---
    # The only non-institutional source. Brocardi supplies doctrinal notes and
    # case-law abstracts, never the text of a norm: that always comes from
    # Normattiva or EUR-Lex. Named explicitly because an auditor should see
    # that this project's single private dependency was a deliberate choice.
    "www.brocardi.it": "Brocardi.it — annotazioni dottrinali (fonte privata)",
}

#: Hosts contacted only by maintenance scripts under `scripts/`, never by the
#: running server. They refresh the shipped data tables from official sources.
CI_ONLY_HOSTS: dict[str, str] = {
    "data-api.ecb.europa.eu": "BCE Data Portal — serie MRO per i tassi di mora",
    "www.istat.it": "ISTAT — indici FOI per le rivalutazioni",
    "www.bancaditalia.it": "Banca d'Italia — TEGM (indicato come fonte, non scaricato)",
    "www.mef.gov.it": "MEF — decreti tassi legali (indicato come fonte)",
    "www.finanze.gov.it": "MEF — decreto coefficienti usufrutto (indicato come fonte)",
    "www.mimit.gov.it": "MIMIT — DM danno biologico (indicato come fonte)",
}

#: URIs that look like hosts but are never fetched: XML/RDF namespace
#: identifiers and placeholder domains inside docstrings.
NON_NETWORK_HOSTS: dict[str, str] = {
    "www.w3.org": "namespace XMLSchema nei PREFIX SPARQL",
    "purl.org": "namespace Dublin Core nei PREFIX SPARQL (dati.camera.it)",
    "www.senato.it": "link scheda DDL emesso per l'utente — mai richiesto dal server (il sito risponde 202/WAF alle richieste automatiche)",
    "www.camera.it": "link scheda atto (resolver URN) emesso per l'utente — mai richiesto dal server",
    "docs.oasis-open.org": "namespace Akoma Ntoso citato in un docstring",
    "www.esempio.it": "dominio segnaposto negli esempi dei docstring",
    "github.com": "link doc nel README generato del bundle openai (scripts/build_targets.py) — mai richiesto dallo script",
}


def is_allowed(url: str) -> bool:
    """True when `url`'s host is one the running server may contact."""
    return (urlparse(url).hostname or "") in ALLOWED_HOSTS
