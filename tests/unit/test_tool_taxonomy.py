"""Every tool is filed under the tag vocabulary of mcp_legal_it/tool_taxonomy.py.

The tags are what LEGAL_PROFILE, crea_server and LEGAL_BROCARDI filter on. A tool
added without a kind, a calculator tagged `normativa`, a TAR decision without the
`giurisprudenza` tag: each one silently moves a tool in or out of a host's
surface, so each one fails here.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from mcp_legal_it.server import _PROFILES, mcp
from mcp_legal_it.tool_taxonomy import AREAS, AUTHORITIES, COURTS, GROUPS, KINDS, MARKERS, VOCABULARY, problems

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "tool-tags.md"


def _tags() -> dict[str, set[str]]:
    return {t.name: set(t.tags) for t in asyncio.run(mcp.list_tools())}


TAGS = _tags()


def _with(tag: str) -> set[str]:
    return {name for name, tags in TAGS.items() if tag in tags}


def test_every_tool_follows_the_taxonomy():
    assert len(TAGS) == 234
    assert problems(TAGS) == []


def test_the_groups_do_not_overlap():
    seen: dict[str, str] = {}
    for group, tags in GROUPS.items():
        for tag in tags:
            assert tag not in seen, f"{tag} is both {seen[tag]} and {group}"
            seen[tag] = group
    assert set(seen) == set(VOCABULARY)


def test_every_tag_in_the_vocabulary_is_used():
    used = set().union(*TAGS.values())
    assert set(VOCABULARY) - used == set()


@pytest.mark.parametrize("tags,expected", [
    ({"utility"}, "exactly one kind"),
    ({"calcolo", "normativa"}, "exactly one kind"),
    ({"calcolo", "fantasia"}, "not in the vocabulary"),
    ({"giurisprudenza"}, "names its court"),
    ({"calcolo", "giurisprudenza_amm"}, "court tags"),
    ({"autorita", "privacy"}, "exactly one authority"),
    ({"normativa", "garante"}, "authority tags"),
    ({"normativa", "solo_brocardi"}, "without `brocardi`"),
])
def test_the_rules_catch_each_mistake(tags, expected):
    found = problems({"nuovo_tool": tags})
    assert any(expected in p for p in found), found


def test_sources_and_calculators_never_share_a_kind():
    sources = _with("normativa") | _with("giurisprudenza") | _with("autorita")
    assert not sources & (_with("calcolo") | _with("redazione") | _with("diagnostica") | _with("registri"))


@pytest.mark.parametrize("module,kind,court", [
    ("italgiure", "giurisprudenza", "giurisprudenza_cass"),
    ("orientamento", "giurisprudenza", "giurisprudenza_cass"),
    ("corte_cost", "giurisprudenza", "giurisprudenza_cost"),
    ("cerdef", "giurisprudenza", "giurisprudenza_trib"),
    ("giustizia_amm", "giurisprudenza", "giurisprudenza_amm"),
    ("cgue", "giurisprudenza", "giurisprudenza_ue"),
    ("gpdp", "autorita", "garante"),
    ("consob", "autorita", "consob"),
    ("anac", "autorita", "anac"),
    ("corte_conti", "giurisprudenza", "giurisprudenza_conti"),
    ("legal_citations", "normativa", None),
    ("gazzetta", "normativa", None),
    ("parlamento", "normativa", None),
    ("eu_implementation", "normativa", None),
    ("tmview", "registri", None),
])
def test_each_source_module_is_filed_under_its_kind(module, kind, court):
    tools = [t for t in asyncio.run(mcp.list_tools()) if t.fn.__module__.endswith("." + module)]
    assert tools
    for tool in tools:
        assert kind in tool.tags, tool.name
        if court:
            assert court in tool.tags, tool.name


def test_diagnostics_and_trademarks_are_not_normativa():
    for name in ("stato_server", "verbale_mensile", "backlog_riconciliazione",
                 "cerca_marchi", "leggi_marchio", "verifica_anteriorita_marchio"):
        assert "normativa" not in TAGS[name], name


def test_the_doc_table_names_every_tag_once():
    text = DOC.read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([a-z_]+)` \|", text, flags=re.MULTILINE)
    assert sorted(rows) == sorted(VOCABULARY), "docs/tool-tags.md and tool_taxonomy.py disagree"


def test_the_doc_counts_match_the_tools():
    text = DOC.read_text(encoding="utf-8")
    for kind in KINDS:
        row = re.search(rf"^\| `{kind}` \| (\d+) \|", text, flags=re.MULTILINE)
        assert row, kind
        assert int(row.group(1)) == len(_with(kind)), f"docs/tool-tags.md: count for {kind}"


# --- LEGAL_PROFILE -----------------------------------------------------------
# A profile is the set of tools whose tags intersect the profile's tags (FastMCP
# `enable(tags=..., only=True)`); test_profiles.py checks that on a real server.

def _profile(name: str) -> set[str]:
    return {tool for tool, tags in TAGS.items() if tags & _PROFILES[name]}


def test_profiles_use_only_vocabulary_tags():
    for name, tags in _PROFILES.items():
        assert tags <= set(VOCABULARY), (name, sorted(tags - set(VOCABULARY)))


def test_every_profile_keeps_the_diagnostics():
    for name in _PROFILES:
        assert _with("diagnostica") <= _profile(name), name


@pytest.mark.parametrize("profile", ["sinistro", "credito", "penale", "normativa", "privacy", "cowork"])
def test_research_profiles_see_every_norm_and_every_court(profile):
    assert _with("normativa") <= _profile(profile)
    assert _with("giurisprudenza") <= _profile(profile)


def test_privacy_profiles_see_the_garante():
    for profile in ("privacy", "normativa", "cowork"):
        assert _with("garante") <= _profile(profile), profile


def test_the_normativa_profile_sees_every_online_source():
    assert _with("autorita") | _with("registri") <= _profile("normativa")


def test_fiscal_profile_sees_tax_case_law_and_consob():
    assert _with("giurisprudenza_trib") | _with("consob") <= _profile("fiscale")


def test_the_drafting_profile_reads_norms_not_case_law():
    # The drafting profile reads norms but not case law: no court decision gets in
    # through a stray `normativa` tag (TAR/CdS and CGUE did before the cleanup).
    assert not _with("giurisprudenza") & _profile("redattore")


def test_areas_and_markers_are_documented_with_a_sentence():
    for group in (KINDS, COURTS, AUTHORITIES, AREAS, MARKERS):
        for tag, text in group.items():
            assert text.strip().endswith("."), tag
