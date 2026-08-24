"""ONE-SHOT: extract the 12 inline-literal resources to content/references/*.md."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STATIC = [
    "procedura_civile", "termini_processuali", "checklist_decreto_ingiuntivo",
    "fonti_diritto_italiano", "codici_e_leggi_principali", "gdpr_checklist",
    "consob_delibere", "ricerca_giurisprudenziale", "cerdef_giurisprudenza",
    "modelli_atti_catalogo", "giustizia_amministrativa", "cgue_giurisprudenza",
]

def main() -> None:
    from src import resources as res
    out_dir = ROOT / "content" / "references"
    out_dir.mkdir(parents=True, exist_ok=True)
    for func_name in STATIC:
        fn = getattr(res, func_name)
        fn = getattr(fn, "fn", fn)  # unwrap FastMCP resource wrapper if present
        text = fn()
        (out_dir / (func_name.replace("_", "-") + ".md")).write_text(text, encoding="utf-8")
        print(f"{func_name} -> {func_name.replace('_', '-')}.md ({len(text)} chars)")

if __name__ == "__main__":
    main()
