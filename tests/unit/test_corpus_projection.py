import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]

def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / "corpus" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

SKILL = (
    "---\n"
    "name: demo\n"
    "description: Demo skill.\n"
    "tools: [cite_law, leggi_sentenza]\n"
    'prompt: {"name": "demo", "description": "d", "args": []}\n'
    "---\n\nUsa `cite_law`, poi leggi_sentenza(n, a).\n"
)
COMMAND = (
    "---\n"
    "name: norma\n"
    "description: Cerca una norma.\n"
    "tools: cite_law, cerca_brocardi, Bash\n"
    "---\n\nUsa `cite_law`; poi proponi `cerca_brocardi`. Se serve, usa Bash.\n"
)
AGENT = "---\nname: civilista\ndescription: Civilista.\nmodel: sonnet\ntools: [cite_law]\n---\n\nUsa `cite_law`.\n"
REF = "Riferimento condiviso senza frontmatter.\n"

TARGETS_YAML = (
    "version: 1\n"
    "projections:\n"
    "  claude-code:\n"
    '    tool_namespace: "legal-it:{tool}"\n'
    '    command_tool_namespace: "mcp__legal-it__{tool}"\n'
    "    strip_frontmatter_keys: [tools, prompt]\n"
    "    supports: [skills, agents, commands, mcp_prompts, mcp_resources, hooks]\n"
    "    out:\n"
    "      skills: plugin/skills\n"
    "      agents: plugin/agents\n"
    "      commands: plugin/commands\n"
    "      references: plugin/server/src/data/references\n"
)

# Same shape, but WITHOUT command_tool_namespace — exercises the lazy read.
TARGETS_YAML_NO_COMMAND_NS = (
    "version: 1\n"
    "projections:\n"
    "  claude-code:\n"
    '    tool_namespace: "legal-it:{tool}"\n'
    "    strip_frontmatter_keys: [tools, prompt]\n"
    "    supports: [skills, agents, commands, mcp_prompts, mcp_resources, hooks]\n"
    "    out:\n"
    "      skills: plugin/skills\n"
    "      agents: plugin/agents\n"
    "      commands: plugin/commands\n"
    "      references: plugin/server/src/data/references\n"
)

def _make_content(root: Path):
    (root / "content/skills/demo/references").mkdir(parents=True)
    (root / "content/tool-vocabulary.json").write_text(
        '["cerca_brocardi", "cite_law", "leggi_sentenza"]', encoding="utf-8"
    )
    (root / "content/targets.yaml").write_text(TARGETS_YAML, encoding="utf-8")
    (root / "content/skills/demo/SKILL.md").write_text(SKILL, encoding="utf-8")
    (root / "content/skills/demo/references/nota.md").write_text("Vedi `cite_law`.\n", encoding="utf-8")
    (root / "content/agents").mkdir(parents=True)
    (root / "content/agents/civilista.md").write_text(AGENT, encoding="utf-8")
    (root / "content/commands").mkdir(parents=True)
    (root / "content/commands/norma.md").write_text(COMMAND, encoding="utf-8")
    (root / "content/references").mkdir(parents=True)
    (root / "content/references/fonti.md").write_text(REF, encoding="utf-8")

def test_projection_shapes_all_four_asset_kinds(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    out = tmp_path / "out"
    _make_content(src_root)
    pc.project(src_root, out)

    skill = (out / "plugin/skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "tools:" not in skill and "prompt:" not in skill
    assert "`legal-it:cite_law`" in skill and "legal-it:leggi_sentenza(n, a)" in skill

    ref = (out / "plugin/skills/demo/references/nota.md").read_text(encoding="utf-8")
    assert "`legal-it:cite_law`" in ref

    cmd = (out / "plugin/commands/norma.md").read_text(encoding="utf-8")
    assert "allowed-tools: mcp__legal-it__cite_law, mcp__legal-it__cerca_brocardi, Bash" in cmd
    assert not any(l.startswith("tools:") for l in cmd.splitlines())
    assert "`legal-it:cite_law`" in cmd and "legal-it:Bash" not in cmd

    ag = (out / "plugin/agents/civilista.md").read_text(encoding="utf-8")
    assert "model: sonnet" in ag and "tools:" not in ag and "`legal-it:cite_law`" in ag

    shared = (out / "plugin/server/src/data/references/fonti.md").read_text(encoding="utf-8")
    assert shared == REF

def test_project_runtime_fallback_for_absent_supports(tmp_path):
    """Runtime pin (not just load_targets()) for 'absent supports = full claude
    behavior': a raw cfg dict with NO 'supports' key at all — full claude-shaped
    out map, namespaces, strip keys, no merge/exclude/cap — must still project
    all four asset kinds exactly like the pre-Task-2 unconditional behavior:
    skill with prefixed tools, agent with tools stripped, command WITH the
    allowed-tools line, shared reference copied verbatim."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    out = tmp_path / "out"
    _make_content(src_root)

    cfg = {
        "tool_namespace": "legal-it:{tool}",
        "command_tool_namespace": "mcp__legal-it__{tool}",
        "strip_frontmatter_keys": ["tools", "prompt"],
        "out": {
            "skills": "plugin/skills",
            "agents": "plugin/agents",
            "commands": "plugin/commands",
            "references": "plugin/server/src/data/references",
        },
    }
    assert "supports" not in cfg

    pc.project(src_root, out, cfg=cfg)

    skill = (out / "plugin/skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "tools:" not in skill and "prompt:" not in skill
    assert "`legal-it:cite_law`" in skill and "legal-it:leggi_sentenza(n, a)" in skill

    ref = (out / "plugin/skills/demo/references/nota.md").read_text(encoding="utf-8")
    assert "`legal-it:cite_law`" in ref

    cmd = (out / "plugin/commands/norma.md").read_text(encoding="utf-8")
    assert "allowed-tools: mcp__legal-it__cite_law, mcp__legal-it__cerca_brocardi, Bash" in cmd
    assert not any(l.startswith("tools:") for l in cmd.splitlines())
    assert "`legal-it:cite_law`" in cmd and "legal-it:Bash" not in cmd

    ag = (out / "plugin/agents/civilista.md").read_text(encoding="utf-8")
    assert "model: sonnet" in ag and "tools:" not in ag and "`legal-it:cite_law`" in ag

    shared = (out / "plugin/server/src/data/references/fonti.md").read_text(encoding="utf-8")
    assert shared == REF


def test_projection_fails_on_leftover_prefix_in_content(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    bad = src_root / "content/skills/demo/SKILL.md"
    bad.write_text(SKILL.replace("`cite_law`", "`legal-it:cite_law`"), encoding="utf-8")
    import pytest
    with pytest.raises(SystemExit):
        pc.project(src_root, tmp_path / "out")

def test_cli_runs_against_real_corpus_once_it_exists(tmp_path):
    if not (REPO / "content" / "skills").is_dir():
        import pytest
        pytest.skip("corpus not yet migrated (Task 5)")
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/corpus/project_claude.py"), "--out", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr

def test_multiline_tools_block_is_rejected(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    bad = src_root / "content/skills/demo/SKILL.md"
    bad.write_text(SKILL.replace(
        "tools: [cite_law, leggi_sentenza]",
        "tools:\n  - cite_law\n  - leggi_sentenza",
    ), encoding="utf-8")
    import pytest
    with pytest.raises(SystemExit, match="single-line"):
        pc.project(src_root, tmp_path / "out")


def test_undeclared_vocabulary_name_is_rejected(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    skill = src_root / "content/skills/demo/SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "Usa `cite_law`", "Usa `cite_law` e poi `cerca_brocardi`"
        ),
        encoding="utf-8",
    )  # cerca_brocardi is in the fixture vocabulary but NOT in demo's tools:
    import pytest
    with pytest.raises(SystemExit, match="undeclared"):
        pc.project(src_root, tmp_path / "out")


def test_tool_namespace_placeholder_conversion(tmp_path):
    """The manifest spells the placeholder as NAMED {tool}; toolnames.add_prefixes
    formats POSITIONALLY. project() must convert once when reading cfg, or every
    projected doc raises KeyError on the first str.format() call."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    out = tmp_path / "out"
    pc.project(src_root, out)
    skill = (out / "plugin/skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "`legal-it:cite_law`" in skill


def test_missing_command_tool_namespace_with_command_tools_raises(tmp_path):
    """Without command_tool_namespace, a command declaring vocab tools must
    fail loudly instead of silently emitting an un-namespaced allowed-tools
    line."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    (src_root / "content/targets.yaml").write_text(TARGETS_YAML_NO_COMMAND_NS, encoding="utf-8")
    import pytest
    with pytest.raises(SystemExit, match="command_tool_namespace"):
        pc.project(src_root, tmp_path / "out")


def test_missing_command_tool_namespace_without_commands_succeeds(tmp_path):
    """The same manifest gap is harmless when the corpus has no commands at
    all — command_tool_namespace is never read/formatted."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    (src_root / "content/targets.yaml").write_text(TARGETS_YAML_NO_COMMAND_NS, encoding="utf-8")
    shutil.rmtree(src_root / "content/commands")
    pc.project(src_root, tmp_path / "out")


# ---------------------------------------------------------------------------
# Phase 3 Task 2 — supports:, merge_into_skills, exclude, description cap
# ---------------------------------------------------------------------------
# These pass cfg=dict(...) directly to project() instead of routing through a
# targets.yaml (project() accepts cfg as a parameter — see its signature).
# _make_content() still lays down content/targets.yaml (unused by these tests)
# plus the tool-vocabulary.json / skills / agents / commands / references
# fixtures every test below builds on.

def _openai_like_cfg(out_skills="dist/openai/.agents/skills", **extra):
    cfg = {
        "tool_namespace": "{tool}",  # bare — identity add_prefixes
        "strip_frontmatter_keys": ["tools", "prompt", "standalone-description"],
        "supports": ["skills"],
        "out": {"skills": out_skills},
    }
    cfg.update(extra)
    return cfg


def test_merge_into_skills_projects_agent_with_standalone_description(tmp_path):
    """A merged agent becomes X/SKILL.md; frontmatter is REBUILT as just
    name + description (standalone-description wins over description);
    tools:/model/color are dropped, not merely stripped from a passthrough."""
    import pytest  # noqa: F401 (kept local like the rest of this file's tests)
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    (src_root / "content/agents/penalista.md").write_text(
        "---\n"
        "name: penalista\n"
        "description: Descrizione interna per subagent Claude, non usata sul target merge.\n"
        "model: sonnet\n"
        "color: red\n"
        "tools: [leggi_sentenza]\n"
        "standalone-description: Metodologia penalista sintetica per l'uso standalone.\n"
        "---\n\nUsa `leggi_sentenza(numero, anno)`.\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    cfg = _openai_like_cfg(merge_into_skills=["agents"])

    pc.project(src_root, out, cfg=cfg)

    skill = (out / "dist/openai/.agents/skills/penalista/SKILL.md").read_text(encoding="utf-8")
    assert skill == (
        "---\n"
        "name: penalista\n"
        "description: Metodologia penalista sintetica per l'uso standalone.\n"
        "---\n\nUsa `leggi_sentenza(numero, anno)`.\n"
    )
    assert "model:" not in skill and "color:" not in skill and "tools:" not in skill


def test_merge_into_skills_uses_description_when_no_standalone(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)  # civilista.md agent has no standalone-description
    out = tmp_path / "out"
    cfg = _openai_like_cfg(merge_into_skills=["agents"])

    pc.project(src_root, out, cfg=cfg)

    skill = (out / "dist/openai/.agents/skills/civilista/SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: civilista\ndescription: Civilista.\n---\n\n")


def test_merged_command_bypasses_command_branch_without_command_tool_namespace(tmp_path):
    """Load-bearing: a merged command declaring vocabulary tools, on a cfg
    with NO command_tool_namespace at all, must NOT SystemExit. It is
    processed with skill semantics — no allowed-tools, no command gate."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)  # commands/norma.md tools: cite_law, cerca_brocardi, Bash
    out = tmp_path / "out"
    cfg = _openai_like_cfg(merge_into_skills=["commands"])
    assert "command_tool_namespace" not in cfg

    pc.project(src_root, out, cfg=cfg)  # must NOT raise SystemExit

    skill = (out / "dist/openai/.agents/skills/norma/SKILL.md").read_text(encoding="utf-8")
    assert skill == (
        "---\nname: norma\ndescription: Cerca una norma.\n---\n\n"
        "Usa `cite_law`; poi proponi `cerca_brocardi`. Se serve, usa Bash.\n"
    )
    assert "allowed-tools" not in skill
    assert "argument-hint" not in skill
    assert "tools:" not in skill


def test_exclude_skips_kind_qualified_names(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    out = tmp_path / "out"
    cfg = _openai_like_cfg(
        merge_into_skills=["agents", "commands"],
        exclude=["commands/norma", "agents/civilista", "skills/demo"],
    )

    pc.project(src_root, out, cfg=cfg)

    base = out / "dist/openai/.agents/skills"
    assert not (base / "norma").exists()
    assert not (base / "civilista").exists()
    assert not (base / "demo").exists()


def test_description_max_chars_truncates_at_word_boundary(tmp_path):
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    long_desc = " ".join(f"parola{i}" for i in range(1, 40))
    assert len(long_desc) > 150  # sanity: the fixture must exercise truncation
    skill_dir = src_root / "content/skills/lungo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: lungo\ndescription: {long_desc}\ntools: [cite_law]\n---\n\nUsa `cite_law`.\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    cfg = _openai_like_cfg(description_max_chars=150)

    pc.project(src_root, out, cfg=cfg)

    skill = (out / "dist/openai/.agents/skills/lungo/SKILL.md").read_text(encoding="utf-8")
    desc_line = next(l for l in skill.splitlines() if l.startswith("description:"))
    value = desc_line[len("description: "):]
    assert value.endswith("...")
    assert len(value) <= 150
    prefix = value[:-3]
    assert long_desc.startswith(prefix)
    assert long_desc[len(prefix)] == " "  # cut on a word boundary, not mid-word


def test_multiline_description_is_read_in_full_and_reemitted_as_one_line(tmp_path):
    """Real case: parere-legale's description spans two frontmatter lines.
    frontmatter.replace_line() raises on multi-line keys, so the cap path
    must use the block-aware reader and re-emit a single capped line."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    skill_dir = src_root / "content/skills/multi"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: multi\n"
        "description: Redazione parere legale strutturato con citazioni normative verificate.\n"
        "  Usa quando l'utente chiede un parere o un'analisi giuridica su una questione ampia e complessa.\n"
        "tools: [cite_law]\n"
        "---\n\nUsa `cite_law`.\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    cfg = _openai_like_cfg(description_max_chars=150)

    pc.project(src_root, out, cfg=cfg)

    skill = (out / "dist/openai/.agents/skills/multi/SKILL.md").read_text(encoding="utf-8")
    lines = skill.splitlines()
    desc_lines = [l for l in lines if l.startswith("description:")]
    assert len(desc_lines) == 1  # re-emitted as ONE line, not the original two
    assert not any(l.startswith("  ") for l in lines[: lines.index("---", 1)])  # no leftover continuation
    value = desc_lines[0][len("description: "):]
    assert len(value) <= 150


def _desc_ending_in_connector(base: str, connector: str, junk_len: int = 20) -> tuple[str, int]:
    """Construct (description, max_chars) such that the shared word-boundary
    truncate_description() lands with `connector` as the very last kept word
    before '...' — proves the description cap trims a dangling connector
    left over from naive truncation."""
    prefix_len = len(base) + 1 + len(connector) + 6  # +6: slice extends into junk, not exactly at boundary
    max_chars = prefix_len + 3  # truncate_description reserves 3 chars for '...'
    junk = "Z" * junk_len
    rest = " molte altre parole di riempimento per superare abbondantemente qualunque soglia richiesta"
    desc = f"{base} {connector} {junk}{rest}"
    return desc, max_chars


def test_description_cap_trims_trailing_dangling_connector(tmp_path):
    pc = _load("project_claude")
    for i, connector in enumerate(("Usa", "Usa quando", "con", "per", "es.")):
        desc, max_chars = _desc_ending_in_connector("Analizza il caso concreto", connector)
        src_root = tmp_path / f"repo{i}"
        _make_content(src_root)
        skill_dir = src_root / "content/skills/conn"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: conn\ndescription: {desc}\ntools: [cite_law]\n---\n\nUsa `cite_law`.\n",
            encoding="utf-8",
        )
        out = tmp_path / f"out{i}"
        cfg = _openai_like_cfg(out_skills="dist/skills", description_max_chars=max_chars)

        pc.project(src_root, out, cfg=cfg)

        skill = (out / "dist/skills/conn/SKILL.md").read_text(encoding="utf-8")
        desc_line = next(l for l in skill.splitlines() if l.startswith("description:"))
        value = desc_line[len("description: "):]
        assert value == "Analizza il caso concreto...", (connector, value)


def test_merge_into_skills_applies_description_cap_too(tmp_path):
    """description_max_chars applies to EVERY projected skill description,
    including a merged agent's rebuilt one."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    desc, max_chars = _desc_ending_in_connector("Metodologia legale sintetica", "per")
    (src_root / "content/agents/lungo.md").write_text(
        "---\n"
        "name: lungo\n"
        "description: breve.\n"
        "model: sonnet\n"
        "tools: [cite_law]\n"
        f"standalone-description: {desc}\n"
        "---\n\nUsa `cite_law`.\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    cfg = _openai_like_cfg(merge_into_skills=["agents"], description_max_chars=max_chars)

    pc.project(src_root, out, cfg=cfg)

    skill = (out / "dist/openai/.agents/skills/lungo/SKILL.md").read_text(encoding="utf-8")
    desc_line = next(l for l in skill.splitlines() if l.startswith("description:"))
    value = desc_line[len("description: "):]
    assert value == "Metodologia legale sintetica..."


def test_supports_skills_only_skips_agents_and_commands_entirely(tmp_path):
    """supports: [skills] with no merge_into_skills means agents/commands are
    dropped, not just left in their content/ form — no out dir for them."""
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    out = tmp_path / "out"
    cfg = _openai_like_cfg()  # no merge_into_skills

    pc.project(src_root, out, cfg=cfg)

    assert (out / "dist/openai/.agents/skills/demo/SKILL.md").is_file()
    assert not (out / "plugin/agents").exists()
    assert not (out / "plugin/commands").exists()


def test_guards_apply_symmetrically_to_merged_undeclared_tool(tmp_path):
    """The undeclared-name lint must fire for a merged command too, not just
    for native skills/agents/commands."""
    import pytest
    pc = _load("project_claude")
    src_root = tmp_path / "repo"
    _make_content(src_root)
    cmd = src_root / "content/commands/norma.md"
    cmd.write_text(
        cmd.read_text(encoding="utf-8").replace(
            "Usa `cite_law`", "Usa `cite_law` e poi `leggi_sentenza`"
        ),
        encoding="utf-8",
    )  # leggi_sentenza is in the fixture vocabulary but NOT declared in norma's tools:
    out = tmp_path / "out"
    cfg = _openai_like_cfg(merge_into_skills=["commands"])
    with pytest.raises(SystemExit, match="undeclared"):
        pc.project(src_root, out, cfg=cfg)
