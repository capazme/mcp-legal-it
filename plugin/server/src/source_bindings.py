"""The online-source bindings: which dataset each tool may consult.

`scripts/audit_tool_annotations.py` derives this from the call graph: every
`note_source("dataset", ...)` or `retry_request(..., dataset="dataset")` a
tool can reach at runtime is a dataset its `fonti_consultate` block may name.
The runtime record stays dynamic (`src/lib/_sources.py` notes per call); this
file is the committed surface a reviewer reads and the audit re-derives on
every run, so a client that starts fetching a new dataset fails the suite
until the policy is regenerated -- the same discipline as the table bindings
and the egress allowlist.

Regenerate with `python scripts/audit_tool_annotations.py --write`.
"""

TOOL_SOURCES: dict[str, tuple[str, ...]] = {
    "cerca_brocardi": ("brocardi",),
    "cerca_ddl": ("parlamento_senato",),
    "cerca_delibere_consob": ("consob",),
    "cerca_gazzetta_ufficiale": ("gazzetta",),
    "cerca_giurisprudenza": ("italgiure",),
    "cerca_giurisprudenza_amministrativa": ("giustizia_amm",),
    "cerca_giurisprudenza_cgue": ("cgue",),
    "cerca_giurisprudenza_tributaria": ("cerdef",),
    "cerca_giurisprudenza_unificata": ("cerdef", "cgue", "giustizia_amm", "italgiure"),
    "cerca_pronuncia_costituzionale": ("corte_cost",),
    "cerca_provvedimenti_garante": ("gpdp",),
    "cerdef_leggi_provvedimento": ("cerdef",),
    "cite_law": ("brocardi", "eur_lex", "normattiva"),
    "ddl_su_norma": ("parlamento_senato",),
    "download_law_pdf": ("eur_lex", "normattiva"),
    "elenco_misure_nazionali": ("eur_lex",),
    "fetch_act_index": ("normattiva",),
    "fetch_full_act": ("normattiva",),
    "fetch_law_annotations": ("brocardi",),
    "fetch_law_article": ("eur_lex", "normattiva"),
    "get_eu_basis": ("eur_lex",),
    "get_italian_implementation": ("eur_lex",),
    "giurisprudenza_amm_su_norma": ("giustizia_amm",),
    "giurisprudenza_articolo": ("brocardi", "italgiure"),
    "giurisprudenza_cgue_su_norma": ("cgue",),
    "giurisprudenza_su_norma": ("italgiure",),
    "iter_ddl": ("parlamento_camera", "parlamento_senato"),
    "leggi_atto_gazzetta": ("gazzetta",),
    "leggi_delibera_consob": ("consob",),
    "leggi_pronuncia_costituzionale": ("corte_cost",),
    "leggi_provvedimento_amm": ("giustizia_amm",),
    "leggi_provvedimento_garante": ("gpdp",),
    "leggi_sentenza": ("italgiure",),
    "leggi_sentenza_cgue": ("cgue",),
    "mappa_orientamento": ("brocardi", "italgiure"),
    "orientamento_su_norma": ("italgiure",),
    "orientamento_su_principio": ("italgiure",),
    "pronunce_cost_su_norma": ("corte_cost",),
    "scarica_pdf_gazzetta": ("gazzetta",),
    "sommario_gazzetta": ("gazzetta",),
    "ultime_delibere_consob": ("consob",),
    "ultime_gazzette": ("gazzetta",),
    "ultime_pronunce": ("italgiure",),
    "ultime_pronunce_cost": ("corte_cost",),
    "ultime_sentenze_cgue": ("cgue",),
    "ultime_sentenze_tributarie": ("cerdef",),
    "ultimi_provvedimenti_amm": ("giustizia_amm",),
    "ultimi_provvedimenti_garante": ("gpdp",),
    "verifica_citazioni": ("brocardi", "eur_lex", "italgiure", "normattiva"),
    "verifica_partita_iva_vies": ("vies",),
}
