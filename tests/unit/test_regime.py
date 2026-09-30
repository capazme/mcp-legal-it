"""The superseded-regime flag: declared once in the docstring, enforced in three places.

A tool that computes under a rule that no longer governs new cases (the memorie
ex art. 183 co. 6 c.p.c. before the Riforma Cartabia, the equo indennizzo of DPR
834/1981) is right for the residual cases it names and wrong for everything
else. `src/lib/_regime.py` reads the `Regime: PREVIGENTE` line, the wrapper puts
a `regime_normativo` block in every answer, the policy in `tool_annotations.py`
carries the group so `tools/list` and every result `_meta` name it, and
`LEGAL_PREVIGENTE=off` hides the group. This file checks each of those, and that
the audit refuses a flag declared in one place only.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest
from fastmcp import Client

from src.lib import _regime
from src.lib._ledger import REGIME_KEY
from src.tool_annotations import PREVIGENTE

REPO = pathlib.Path(__file__).resolve().parents[2]
SNIPPET = """
import asyncio, json, sys
sys.path.insert(0, "plugin/server")
from fastmcp import Client
from src.server import mcp
async def main():
    async with Client(mcp) as c:
        return sorted(t.name for t in await c.list_tools())
print(json.dumps(asyncio.run(main())))
"""


def _surface(home: pathlib.Path, **extra: str) -> list[str]:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "LEGAL_CACHE": "off", **extra}
    out = subprocess.run(
        [sys.executable, "-c", SNIPPET], cwd=REPO, env=env, capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

def test_parse_reads_state_scope_and_successors_across_lines():
    doc = """Calcola qualcosa.
    Regime: PREVIGENTE — cause iscritte a ruolo prima del 28/02/2023 (artt. 183 co. 6
    e 190 c.p.c. nel testo anteriore); tool vigenti: termini_memorie_repliche,
    termini_processuali_civili
    Vigenza: testo previgente
    Precisione: ESATTO
    """
    info = _regime.parse(doc)
    assert info is not None and info.previgente
    assert info.stato == "PREVIGENTE"
    assert info.ambito.startswith("cause iscritte a ruolo prima del 28/02/2023")
    assert "190 c.p.c. nel testo anteriore" in info.ambito
    assert info.tool_vigenti == ("termini_memorie_repliche", "termini_processuali_civili")
    assert info.to_dict()["stato"] == "previgente"
    assert "avvertenza" in info.to_dict()


def test_parse_stops_at_the_next_field_and_accepts_no_successor():
    info = _regime.parse("Regime: PREVIGENTE — fatti anteriori al 06/12/2011\n    Args:\n        x: y")
    assert info.ambito == "fatti anteriori al 06/12/2011"
    assert info.tool_vigenti == ()
    assert _regime.parse("Regime: VIGENTE") is not None and not _regime.parse("Regime: VIGENTE").previgente
    assert _regime.parse("Nessuna riga") is None


def test_the_wrapper_refuses_a_tool_that_declares_nothing():
    def anonymous():
        """Precisione: ESATTO"""
        return {}

    with pytest.raises(ValueError, match="Regime: PREVIGENTE"):
        _regime.previgente(anonymous)


def test_the_wrapper_marks_dicts_strings_and_coroutines():
    @_regime.previgente
    def as_dict():
        """Regime: PREVIGENTE — solo casi vecchi; tool vigenti: nuovo_tool"""
        return {"valore": 1}

    @_regime.previgente
    def as_text():
        """Regime: PREVIGENTE — solo casi vecchi"""
        return "risposta"

    @_regime.previgente
    async def as_coroutine():
        """Regime: PREVIGENTE — solo casi vecchi"""
        return {"valore": 2}

    out = as_dict()
    assert out["valore"] == 1
    assert out[_regime.CAMPO]["stato"] == "previgente"
    assert out[_regime.CAMPO]["tool_vigenti"] == ["nuovo_tool"]
    text = as_text()
    assert text.startswith("risposta") and "Regime normativo previgente" in text
    assert asyncio.run(as_coroutine())[_regime.CAMPO]["applicabile_a"] == "solo casi vecchi"
    assert as_dict.__doc__.startswith("Regime: PREVIGENTE")


def test_hidden_by_environment_reads_the_switch():
    assert _regime.hidden_by_environment("off")
    assert _regime.hidden_by_environment("0") and _regime.hidden_by_environment("FALSE")
    assert not _regime.hidden_by_environment(None)
    assert not _regime.hidden_by_environment("on")


# ---------------------------------------------------------------------------
# The policy and the wire
# ---------------------------------------------------------------------------

def test_the_policy_names_the_two_superseded_tools_with_their_successors():
    assert set(PREVIGENTE) == {"termini_183_190_cpc", "equo_indennizzo"}
    assert PREVIGENTE["termini_183_190_cpc"]["tool_vigenti"] == (
        "termini_memorie_repliche", "termini_processuali_civili",
    )
    assert "28/02/2023" in PREVIGENTE["termini_183_190_cpc"]["applicabile_a"]
    assert "06/12/2011" in PREVIGENTE["equo_indennizzo"]["applicabile_a"]


def test_tools_list_and_results_carry_the_regime_over_the_wire():
    from src.server import mcp

    async def run():
        async with Client(mcp) as client:
            tools = {t.name: t for t in await client.list_tools()}
            old = await client.call_tool("termini_183_190_cpc", {"data_udienza": "2025-05-01"})
            new = await client.call_tool("termini_memorie_repliche", {"data_udienza": "2025-10-01"})
            equo = await client.call_tool(
                "equo_indennizzo",
                {"categoria_tabella": "5", "percentuale_invalidita": 35.0, "stipendio_annuo": 28000.0},
            )
            return tools, old, new, equo

    tools, old, new, equo = asyncio.run(run())

    listed = tools["termini_183_190_cpc"].meta[REGIME_KEY]
    assert listed["stato"] == "previgente"
    assert "termini_memorie_repliche" in listed["tool_vigenti"]
    assert "previgente" in tools["termini_183_190_cpc"].meta["fastmcp"]["tags"]
    assert REGIME_KEY not in (tools["termini_memorie_repliche"].meta or {})
    assert tools["termini_183_190_cpc"].description.splitlines()[1].strip().startswith("Regime: PREVIGENTE")

    assert old.meta[REGIME_KEY]["stato"] == "previgente"
    body = old.structured_content or json.loads(old.content[0].text)
    assert body[_regime.CAMPO]["stato"] == "previgente"
    assert body["dati_applicati"], "the @sourced footer still travels under the wrapper"
    assert REGIME_KEY not in (new.meta or {})
    assert _regime.CAMPO not in (new.structured_content or json.loads(new.content[0].text))
    assert equo.meta[REGIME_KEY]["stato"] == "previgente"
    assert (equo.structured_content or json.loads(equo.content[0].text))[_regime.CAMPO]["stato"] == "previgente"


def test_the_switch_hides_the_group_and_only_the_group(tmp_path):
    full = _surface(tmp_path)
    hidden = _surface(tmp_path, LEGAL_PREVIGENTE="off")
    assert set(full) - set(hidden) == set(PREVIGENTE)
    assert len(hidden) == len(full) - len(PREVIGENTE)
    narrowed = _surface(tmp_path, LEGAL_PROFILE="studio", LEGAL_PREVIGENTE="off")
    assert "termini_183_190_cpc" not in narrowed and "termini_memorie_repliche" in narrowed


# ---------------------------------------------------------------------------
# The audit refuses a flag declared in one place only
# ---------------------------------------------------------------------------

def _audit_module():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from audit_tool_annotations import Audit, verify_regime  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    return Audit, verify_regime


def _copy_src(tmp_path: pathlib.Path) -> pathlib.Path:
    src = tmp_path / "src"
    shutil.copytree(REPO / "plugin/server/src", src, ignore=shutil.ignore_patterns("__pycache__"))
    return src


def test_the_committed_source_passes_the_regime_audit():
    Audit, verify_regime = _audit_module()
    assert verify_regime(Audit(REPO / "plugin/server/src")) == []


def test_a_dropped_tag_or_wrapper_fails_the_audit(tmp_path):
    Audit, verify_regime = _audit_module()
    src = _copy_src(tmp_path)
    scadenze = src / "tools" / "scadenze_termini.py"
    text = scadenze.read_text(encoding="utf-8")
    sabotaged, n = re.subn(r'tags=\{"scadenze", "previgente"\}', 'tags={"scadenze"}', text, count=1)
    assert n == 1
    scadenze.write_text(sabotaged, encoding="utf-8")
    problems = verify_regime(Audit(src))
    assert any("termini_183_190_cpc" in p and "tag" in p for p in problems), problems

    src2 = _copy_src(tmp_path / "second")
    danni = src2 / "tools" / "risarcimento_danni.py"
    text = danni.read_text(encoding="utf-8")
    sabotaged, n = re.subn(r"@previgente\ndef equo_indennizzo\(", "def equo_indennizzo(", text, count=1)
    assert n == 1
    danni.write_text(sabotaged, encoding="utf-8")
    problems = verify_regime(Audit(src2))
    assert any("equo_indennizzo" in p and "@previgente" in p for p in problems), problems


def test_a_tag_without_a_declaration_and_an_unknown_successor_fail_the_audit(tmp_path):
    Audit, verify_regime = _audit_module()
    src = _copy_src(tmp_path)
    varie = src / "tools" / "varie.py"
    text = varie.read_text(encoding="utf-8")
    sabotaged, n = re.subn(r'@mcp\.tool\(tags=\{"utility"\}\)\n@sourced\("festivita"\)\ndef conta_giorni\(',
                           '@mcp.tool(tags={"utility", "previgente"})\n@sourced("festivita")\ndef conta_giorni(',
                           text, count=1)
    assert n == 1
    varie.write_text(sabotaged, encoding="utf-8")
    problems = verify_regime(Audit(src))
    assert any("conta_giorni" in p and "declares no" in p for p in problems), problems

    src2 = _copy_src(tmp_path / "second")
    scadenze = src2 / "tools" / "scadenze_termini.py"
    text = scadenze.read_text(encoding="utf-8")
    assert "tool vigenti: termini_memorie_repliche," in text
    scadenze.write_text(text.replace("tool vigenti: termini_memorie_repliche,", "tool vigenti: tool_fantasma,", 1),
                        encoding="utf-8")
    problems = verify_regime(Audit(src2))
    assert any("tool_fantasma" in p for p in problems), problems
