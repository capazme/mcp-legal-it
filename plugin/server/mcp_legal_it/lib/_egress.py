"""The complete list of hosts this server may contact, and who owns each one.

A lawyer evaluating this project has to answer one question before running it
on client matters: where does my data go. Answering it by reading the code is
days of work, and answering it with a promise in a README is worth nothing. So
the answer lives here, as data, and `tests/unit/test_egress_allowlist.py`
fails the build if a URL literal appears in `mcp_legal_it/` for a host not listed —
which is what makes it an assertion rather than a claim.

The server sends no telemetry and has no analytics endpoint. Every host below
is a public institutional source consulted to answer a specific question.
"""

from __future__ import annotations

from urllib.parse import urlparse

from . import _brocardi_switch

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
    "www.tmdn.org": "TMview — EUIPO / EU Intellectual Property Network (banca dati marchi)",
    # --- Private ---
    # The only non-institutional source. Brocardi supplies doctrinal notes and
    # case-law abstracts, never the text of a norm: that always comes from
    # Normattiva or EUR-Lex. Named explicitly because an auditor should see
    # that this project's single private dependency was a deliberate choice.
    # LEGAL_BROCARDI=off (or crea_server(brocardi=False)) removes it at runtime:
    # `is_allowed` refuses it and the scrapers never build a request for it
    # (lib/_brocardi_switch.py).
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
    "mozilla.org": "testo della licenza MPL-2.0 citato nell'intestazione dei file importati da VisuaLex",
}

#: Like NON_NETWORK_HOSTS, but scoped to `scripts/` only. Kept separate so the
#: server-side tripwire stays armed: a URL for one of these hosts appearing in
#: `mcp_legal_it/` must still fail the build.
SCRIPT_ONLY_NON_NETWORK_HOSTS: dict[str, str] = {
    "github.com": "link doc nel README generato del bundle openai (scripts/build_targets.py) — mai richiesto dallo script",
}


def is_allowed(url: str) -> bool:
    """True when `url`'s host is one the running server may contact right now.

    Brocardi is on the list but switchable: with Brocardi off its host is refused.

    The host must be the one every client reads, Python's `urlparse` as a browser
    would (ported from VisuaLex's `tools/egress.py`): a backslash, a control
    character, credentials before the host or a scheme other than http(s) is
    refused, because Chromium reads `\\` as `/` and drops tabs and newlines, so
    such a URL can name one host to `urlparse` and another to a browser. Every
    request the libraries send is also checked at runtime, per source, by the
    guard in `core/_http`.
    """
    if not isinstance(url, str) or "\\" in url or any(ord(c) < 0x20 or ord(c) == 0x7F for c in url):
        return False
    if _brocardi_switch.is_brocardi_url(url) and not _brocardi_switch.enabled():
        return False
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ("http", "https")
            and "@" not in parsed.netloc
            and (parsed.hostname or "") in ALLOWED_HOSTS
        )
    except ValueError:
        return False
