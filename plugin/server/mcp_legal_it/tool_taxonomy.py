"""The tag vocabulary every tool is filed under, and the rules that keep it consistent.

Tags are what a host filters on: ``LEGAL_PROFILE`` narrows the stock server with
them, ``crea_server(include_tags=..., exclude_tags=...)`` builds a server from them,
and ``LEGAL_BROCARDI=off`` hides a group by them. A filter is only as good as the
tags under it, so the vocabulary lives here as data and
``tests/unit/test_tool_taxonomy.py`` fails the suite when a tool breaks a rule
(a new tool without a kind, a calculator tagged ``normativa``, a court decision
without its court). ``docs/tool-tags.md`` is the same table for readers; the test
checks that it names every tag below.

Every tool carries:

* exactly one **kind** (``KINDS``): what sort of answer it gives;
* if its kind is ``giurisprudenza``, at least one **court** (``COURTS``), and a court
  tag never appears on a tool of another kind;
* if its kind is ``autorita``, exactly one **authority** (``AUTHORITIES``), and an
  authority tag never appears on a tool of another kind;
* any number of **areas** (``AREAS``), the subject matters the desktop profiles
  are built from, and of **markers** (``MARKERS``).

This module imports nothing: a library consumer can read the vocabulary without
loading the server.
"""

from __future__ import annotations

#: What sort of answer a tool gives. Exactly one per tool.
KINDS: dict[str, str] = {
    "normativa": "Legislation and what annotates it: text of norms, act index and PDF, "
                 "Gazzetta Ufficiale, parliamentary bills, EU-Italy transposition, "
                 "citation checks, Brocardi annotations.",
    "giurisprudenza": "Court decisions: search, full text, case law on a norm, orientations.",
    "autorita": "Decisions and guidance of an independent authority (Garante privacy, CONSOB, ANAC).",
    "registri": "Facts looked up online in a public register or a third-party site, not law: "
                "trademarks (TMview), VAT numbers (VIES), a supplier's published DPA.",
    "calcolo": "Answered locally from the inputs and the bundled tables: calculations, "
               "deadlines, fees, taxes, checks and look-ups. No online source.",
    "redazione": "Produces a draft document or text to be used as such: deeds, letters, "
                 "privacy notices, DPAs, DOCX and Excel files. Invoices, fee notes, "
                 "receipts and quotes are `calcolo`: their content is the computation.",
    "diagnostica": "Reports on the server itself: version, data freshness, refusal log.",
}

#: The court a ``giurisprudenza`` tool reads. At least one per case-law tool.
COURTS: dict[str, str] = {
    "giurisprudenza_cass": "Corte di cassazione (Italgiure), and the orientations built on it.",
    "giurisprudenza_cost": "Corte costituzionale.",
    "giurisprudenza_trib": "Tax courts and tax Cassazione (CeRDEF).",
    "giurisprudenza_amm": "Administrative courts: TAR and Consiglio di Stato.",
    "giurisprudenza_conti": "Corte dei conti: deliberazioni and pareri of its control sections.",
    "giurisprudenza_ue": "Court of Justice and General Court of the EU (CGUE).",
}

#: The authority an ``autorita`` tool reads. Exactly one per authority tool.
AUTHORITIES: dict[str, str] = {
    "garante": "Garante per la protezione dei dati personali.",
    "consob": "CONSOB (Commissione nazionale per le società e la borsa).",
    "anac": "ANAC (Autorità Nazionale Anticorruzione).",
}

#: Subject matters. A tool may carry several; the desktop profiles select on them.
AREAS: dict[str, str] = {
    "atti": "Judicial and out-of-court deeds composed from the catalogue of models.",
    "credito": "Debt recovery workflow (interest, injunction, enforcement, fees).",
    "crisi_impresa": "Business crisis and insolvency (CCII).",
    "danni": "Personal injury and damages.",
    "fiscale": "Taxes, tax returns and tax case law.",
    "giudiziario": "Court procedure: filing costs, PCT filings, procedural checks.",
    "interessi": "Interest rates, default interest, usury, amortisation.",
    "investimenti": "Government bonds and savings products.",
    "lavoro": "Employment law.",
    "marchi": "Trademarks.",
    "parcelle_avv": "Lawyers' fees (D.M. 55/2014), invoices and quotes.",
    "parcelle_prof": "Fees of other professionals (CTU, mediators, receivers).",
    "parlamento": "Parliamentary bills and their passage.",
    "penale": "Criminal law: sentences, limitation, conversion.",
    "privacy": "Data protection (GDPR, Codice privacy).",
    "proprieta": "Property, inheritance and real-estate taxes.",
    "recepimento_ue": "Transposition of EU acts into Italian law, and the EU basis of Italian acts.",
    "rivalutazione": "Monetary revaluation on ISTAT indices.",
    "scadenze": "Procedural and legal deadlines.",
    "sinistro": "Road and medical accident workflow.",
    "societario": "Company law.",
    "utility": "General-purpose checks and conversions (tax code, IBAN, VAT, dates).",
}

#: Cross-cutting flags. They change how a tool is offered, not what it is about.
MARKERS: dict[str, str] = {
    "brocardi": "The answer can contain Brocardi content (doctrinal notes, case-law "
                "abstracts from brocardi.it, a private source).",
    "solo_brocardi": "The answer is Brocardi content and nothing else: the tool is hidden "
                     "when Brocardi is switched off. Always paired with `brocardi`.",
    "previgente": "Computes under a superseded regime, for the residual cases it still "
                  "governs (see lib/_regime.py); LEGAL_PREVIGENTE=off hides it.",
}

GROUPS: dict[str, dict[str, str]] = {
    "kind": KINDS,
    "court": COURTS,
    "authority": AUTHORITIES,
    "area": AREAS,
    "marker": MARKERS,
}

#: Every tag a tool may carry, with what it means.
VOCABULARY: dict[str, str] = {tag: text for group in GROUPS.values() for tag, text in group.items()}


def problems(tools: dict[str, set[str]]) -> list[str]:
    """Every way the given ``{tool name: tags}`` map breaks the rules above."""
    out: list[str] = []
    for name in sorted(tools):
        tags = set(tools[name])
        unknown = sorted(tags - VOCABULARY.keys())
        if unknown:
            out.append(f"{name}: tags not in the vocabulary: {unknown}")
        kinds = sorted(tags & KINDS.keys())
        if len(kinds) != 1:
            out.append(f"{name}: needs exactly one kind tag of {sorted(KINDS)}, has {kinds}")
            continue
        kind = kinds[0]
        courts = tags & COURTS.keys()
        if kind == "giurisprudenza" and not courts:
            out.append(f"{name}: a case-law tool names its court ({sorted(COURTS)})")
        if kind != "giurisprudenza" and courts:
            out.append(f"{name}: court tags {sorted(courts)} on a `{kind}` tool")
        authorities = tags & AUTHORITIES.keys()
        if kind == "autorita" and len(authorities) != 1:
            out.append(f"{name}: an authority tool names exactly one authority ({sorted(AUTHORITIES)})")
        if kind != "autorita" and authorities:
            out.append(f"{name}: authority tags {sorted(authorities)} on a `{kind}` tool")
        if "solo_brocardi" in tags and "brocardi" not in tags:
            out.append(f"{name}: `solo_brocardi` without `brocardi`")
    return out
