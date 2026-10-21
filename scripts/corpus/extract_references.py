"""ONE-SHOT: extract the 12 inline-literal resources to content/references/*.md.

Non ri-eseguibile dopo il Task 9: le 12 funzioni statiche non esistono più come attributi di modulo — conservato come audit record.
Rieseguito oggi lo dice ed esce con codice 2 senza scrivere nulla; non sovrascrive mai un file esistente.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugin" / "server"))

STATIC = [
    "procedura_civile", "termini_processuali", "checklist_decreto_ingiuntivo",
    "fonti_diritto_italiano", "codici_e_leggi_principali", "gdpr_checklist",
    "consob_delibere", "ricerca_giurisprudenziale", "cerdef_giurisprudenza",
    "modelli_atti_catalogo", "giustizia_amministrativa", "cgue_giurisprudenza",
]

def main() -> int:
    from mcp_legal_it import resources as res
    out_dir = ROOT / "content" / "references"
    missing = [name for name in STATIC if not hasattr(res, name)]
    if missing:
        # The migration ran once (corpus consolidation, Task 9): content/references/*.md is
        # now the source and resources.py loads it. Nothing left to extract.
        print("extract_references: migration already done -- content/references/*.md is the "
              f"source of truth and resources.py no longer defines {', '.join(missing[:3])}...; "
              "edit the .md files and run scripts/build_targets.py claude-code.", file=sys.stderr)
        return 2
    targets = [out_dir / (name.replace("_", "-") + ".md") for name in STATIC]
    existing = [t.name for t in targets if t.exists()]
    if existing:
        print(f"extract_references: refusing to overwrite {', '.join(existing)}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    for func_name, target in zip(STATIC, targets):
        fn = getattr(res, func_name)
        fn = getattr(fn, "fn", fn)  # unwrap FastMCP resource wrapper if present
        text = fn()
        target.write_text(text, encoding="utf-8")
        print(f"{func_name} -> {target.name} ({len(text)} chars)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
