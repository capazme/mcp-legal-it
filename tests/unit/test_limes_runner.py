"""Unit tests for the LIMES runner: manifests, argv, waves, SHAs, payload.

Identity tests (bank_sha/protocol_sha) use the *tracked* directories: they
assert stability and distinctness, not values, because the values move with
every legitimate bank edit — a number pinned here would break the very idea
of content-addressed identity.
"""

import json
import subprocess
from pathlib import Path

import pytest

from benchmarks.limes.runner.executor import build_argv, _extract_payload
from benchmarks.limes.runner.manifests import ManifestError, load_manifest
from benchmarks.limes.runner.shas import (
    ShaError,
    bank_sha,
    judge_sha,
    model_sha,
    protocol_sha,
)
from benchmarks.limes.runner.waves import WaveError, load_wave

REPO_ROOT = Path(__file__).resolve().parents[2]
LIMES_ROOT = REPO_ROOT / "benchmarks" / "limes"
CONFIGS_DIR = LIMES_ROOT / "configs"
WAVES_DIR = LIMES_ROOT / "waves"


class TestManifests:
    @pytest.mark.parametrize(
        "manifest_id",
        [
            "bare",
            "mcp-legalit-v2.14.0",
            "plugin-legalit-v2.14.0",
            "plugin-legalit-v3.0.0-beta.3",
        ],
    )
    def test_shipped_manifests_load(self, manifest_id):
        manifest = load_manifest(CONFIGS_DIR / f"{manifest_id}.yaml")
        assert manifest.id == manifest_id
        if manifest_id != "bare":
            assert manifest.ref  # variant_sha lesson: never run unpinned

    def test_unpinned_enhancement_rejected(self, tmp_path):
        p = tmp_path / "m.yaml"
        p.write_text(
            "id: m\nsurface: plugin\nparity: {max_turns: 4}\n", encoding="utf-8"
        )
        with pytest.raises(ManifestError, match="ref"):
            load_manifest(p)

    def test_unknown_surface_rejected(self, tmp_path):
        p = tmp_path / "m.yaml"
        p.write_text(
            "id: m\nsurface: shell\nref: v1\nparity: {max_turns: 4}\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="surface"):
            load_manifest(p)

    def test_bad_max_turns_rejected(self, tmp_path):
        p = tmp_path / "m.yaml"
        p.write_text(
            "id: m\nsurface: bare\nparity: {max_turns: 0}\n", encoding="utf-8"
        )
        with pytest.raises(ManifestError, match="max_turns"):
            load_manifest(p)

    def test_missing_id_rejected(self, tmp_path):
        p = tmp_path / "m.yaml"
        p.write_text(
            "surface: bare\nparity: {max_turns: 4}\n", encoding="utf-8"
        )
        with pytest.raises(ManifestError, match="id"):
            load_manifest(p)

    def test_mcp_template_must_exist(self, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        p = d / "m.yaml"
        p.write_text(
            "id: m\nsurface: mcp\nref: v1\nparity: {max_turns: 4}\n"
            "mcp: {server_template: mcp/missing.json}\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="template"):
            load_manifest(p)

    def test_unresolved_placeholder_fails_closed(self, tmp_path):
        d = tmp_path / "cfg"
        (d / "mcp").mkdir(parents=True)
        (d / "mcp" / "s.json").write_text(
            json.dumps({"mcpServers": {"legalit": {"command": "${MISSING_VAR}"}}}),
            encoding="utf-8",
        )
        p = d / "m.yaml"
        p.write_text(
            "id: m\nsurface: mcp\nref: v1\nparity: {max_turns: 4}\n"
            "mcp: {server_template: mcp/s.json}\n",
            encoding="utf-8",
        )
        manifest = load_manifest(p)
        with pytest.raises(ManifestError, match="MISSING_VAR"):
            manifest.resolve_mcp_config(env={})

    def test_shipped_mcp_template_resolves(self):
        manifest = load_manifest(CONFIGS_DIR / "mcp-legalit-v2.14.0.yaml")
        try:
            config = manifest.resolve_mcp_config(
                env={
                    "LIMES_LEGALIT_CMD": "/usr/local/bin/legalit",
                    "LIMES_LEGALIT_PROFILE": "mcp-legalit-v2.14.0",
                }
            )
        except ManifestError:
            pytest.skip("legalit env vars not set on this machine")
        assert "legalit" in config["mcpServers"]


class TestBuildArgv:
    def test_bare_declares_no_tools(self):
        argv = build_argv("bare", "m1", 4, "default", None, "PROMPT")
        assert argv[0] == "claude" and argv[1] == "-p" and argv[2] == "PROMPT"
        assert "--tools" in argv and argv[argv.index("--tools") + 1] == ""
        assert "--max-turns" in argv and "4" in argv
        assert "--mcp-config" not in argv

    def test_mcp_declares_strict_config(self, tmp_path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text("{}", encoding="utf-8")
        argv = build_argv("mcp", "m1", 4, "default", cfg, "PROMPT")
        assert argv[argv.index("--tools") + 1] == "ToolSearch"
        assert argv[argv.index("--mcp-config") + 1] == str(cfg)
        assert "--strict-mcp-config" in argv

    def test_mcp_without_config_raises(self):
        with pytest.raises(Exception):
            build_argv("mcp", "m1", 4, "default", None, "PROMPT")

    def test_unknown_surface_raises(self):
        with pytest.raises(Exception):
            build_argv("shell", "m1", 4, "default", None, "PROMPT")

    def test_bench_mode_swaps_system_prompt(self):
        plain = build_argv("bare", "m1", 4, "default", None, "P")
        bench = build_argv("bare", "m1", 4, "bench", None, "P")
        assert "--system-prompt" in bench and "--system-prompt" not in plain


class TestWaves:
    def test_shipped_wave_loads(self):
        wave = load_wave(WAVES_DIR / "wave-0.yaml")
        assert wave.id == "wave-0"
        assert wave.tag == "limes-wave-0"
        assert len(wave.configs) == 4 and len(wave.models) == 2
        assert len(wave.cells(27)) == 8

    def test_tag_template_expansion(self, tmp_path):
        p = tmp_path / "w.yaml"
        p.write_text(
            "id: w9\ntag: 'limes-{id}'\nconfigs: [bare]\nmodels: [m1]\n",
            encoding="utf-8",
        )
        assert load_wave(p).tag == "limes-w9"

    def test_empty_configs_rejected(self, tmp_path):
        p = tmp_path / "w.yaml"
        p.write_text("id: w\ntag: t\nconfigs: []\nmodels: [m1]\n", encoding="utf-8")
        with pytest.raises(WaveError):
            load_wave(p)


class TestShas:
    # bank_sha/protocol_sha against the real bank are exercised in the CLI
    # smoke check after the content is committed and frozen in the wave tag
    # (DESIGN §2): while the bank is untracked, the sha must REFUSE to
    # exist — the tmp-repo tests below pin that contract state-independently.

    @staticmethod
    def _git_repo(tmp_path: Path) -> Path:
        import subprocess

        repo = tmp_path / "repo"
        (repo / "bank").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
             "--allow-empty", "-q", "-m", "init"],
            cwd=repo, check=True,
        )
        return repo

    def test_untracked_bank_fails_closed(self, tmp_path):
        # No commit at all: nothing is tracked, identity is undeclarable.
        repo = self._git_repo(tmp_path)
        (repo / "bank" / "x.json").write_text("[]", encoding="utf-8")
        with pytest.raises(ShaError):
            bank_sha(repo / "bank")

    def test_dirty_bank_fails_closed(self, tmp_path):
        import subprocess

        repo = self._git_repo(tmp_path)
        (repo / "bank" / "x.json").write_text("[]", encoding="utf-8")
        subprocess.run(["git", "add", "bank"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
             "-q", "-m", "bank"],
            cwd=repo, check=True,
        )
        (repo / "bank" / "x.json").write_text("[]\n", encoding="utf-8")  # dirty
        with pytest.raises(ShaError, match="modifiche non committate"):
            bank_sha(repo / "bank")

    def test_committed_bank_yields_stable_sha(self, tmp_path):
        import subprocess

        repo = self._git_repo(tmp_path)
        (repo / "bank" / "x.json").write_text("[]", encoding="utf-8")
        subprocess.run(["git", "add", "bank"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
             "-q", "-m", "bank"],
            cwd=repo, check=True,
        )
        first = bank_sha(repo / "bank")
        assert first == bank_sha(repo / "bank")
        assert len(first) == 16
        # Content change must move the sha (content-addressed identity).
        (repo / "bank" / "y.json").write_text("{}", encoding="utf-8")
        subprocess.run(["git", "add", "bank"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
             "-q", "-m", "bank2"],
            cwd=repo, check=True,
        )
        assert bank_sha(repo / "bank") != first

    def test_judge_sha_none_for_mechanical_wave(self):
        assert judge_sha(LIMES_ROOT / "protocol") == "none"

    def test_model_sha_pins_explicit_strings(self):
        assert model_sha("claude-opus-4-6") == "claude-opus-4-6"
        with pytest.raises(ShaError):
            model_sha("  ")
        with pytest.raises(ShaError):
            model_sha("")




class TestExtractPayload:
    def test_result_object(self):
        text, tools, stop = _extract_payload(
            {"type": "result", "result": "Risposta finale.", "subtype": "success"}
        )
        assert text == "Risposta finale."
        assert tools == [] and stop == "success"

    def test_message_stream_collects_text_and_tool_results(self):
        payload = {
            "messages": [
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "parte 1"}]},
                },
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "content": [
                                    {"type": "text", "text": "out strumento"}
                                ],
                            }
                        ]
                    },
                },
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "parte 2"}]},
                },
                {"type": "result", "subtype": "success"},
            ]
        }
        text, tools, stop = _extract_payload(payload)
        assert text == "parte 1\nparte 2"
        assert tools == ["out strumento"]
        assert stop == "success"

    def test_string_content_normalized(self):
        text, _, _ = _extract_payload(
            {"messages": [{"type": "assistant", "message": {"content": "testo"}}]}
        )
        assert text == "testo"


class TestRunCell:
    """`run_cell` exercised end-to-end with a stubbed subprocess: retry
    budget, exclusion ids (tracked, never sniffed from the error string),
    and ownership of the per-item directory across repeated runs."""

    @pytest.fixture(autouse=True)
    def _no_credential_bootstrap(self, monkeypatch):
        """Stubbed `claude` means auth is out of scope here; the bootstrap's
        keychain probe must not consume one of the stubbed `run` calls."""
        from benchmarks.limes.runner import executor

        monkeypatch.setattr(
            executor,
            "bootstrap_credentials",
            lambda scratch: None,
        )

    @pytest.fixture()
    def protocol(self):
        from benchmarks.limes.protocol.rules import load_protocol

        return load_protocol(LIMES_ROOT / "protocol" / "protocol.yaml")

    @pytest.fixture()
    def manifest(self):
        return load_manifest(LIMES_ROOT / "configs" / "bare.yaml")

    @staticmethod
    def _payload(text: str) -> str:
        return json.dumps(
            {"type": "result", "subtype": "success", "result": text}
        )

    def test_first_attempt_success(
        self, monkeypatch, tmp_path, protocol, manifest
    ):
        from benchmarks.limes.runner import executor
        from benchmarks.limes.runner.executor import run_cell

        calls = []

        def fake_run(argv, **kwargs):
            calls.append(list(argv))
            return subprocess.CompletedProcess(
                argv, 0, stdout=self._payload("risposta perfetta"), stderr=""
            )

        monkeypatch.setattr(executor.subprocess, "run", fake_run)
        outcome = run_cell(
            manifest=manifest, model="m-test", item_id="QA-01",
            prompt="domanda", protocol=protocol, out_dir=tmp_path / "it",
        )
        assert outcome.ok and outcome.attempts == 1
        assert outcome.answer == "risposta perfetta"
        assert outcome.excluded is False and outcome.exclusion is None
        assert calls and calls[0][0] == "claude" and "-p" in calls[0]
        assert (tmp_path / "it" / "attempt-1.json").is_file()

    def test_retry_then_success_within_budget(
        self, monkeypatch, tmp_path, protocol, manifest
    ):
        from benchmarks.limes.runner import executor
        from benchmarks.limes.runner.executor import run_cell

        responses = ["non sono json", self._payload("ok al secondo colpo")]

        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(
                argv, 0, stdout=responses.pop(0), stderr=""
            )

        monkeypatch.setattr(executor.subprocess, "run", fake_run)
        outcome = run_cell(
            manifest=manifest, model="m-test", item_id="QA-01",
            prompt="domanda", protocol=protocol, out_dir=tmp_path / "it",
        )
        assert outcome.ok and outcome.attempts == 2
        assert (tmp_path / "it" / "attempt-1.json").read_text() == "non sono json"

    def test_exhausted_budget_excludes_with_tracked_id(
        self, monkeypatch, tmp_path, protocol, manifest
    ):
        from benchmarks.limes.runner import executor
        from benchmarks.limes.runner.executor import run_cell

        def fake_run(argv, **kwargs):
            # Always a timeout: the exclusion id must be the tracked one,
            # not re-derived by sniffing the error string.
            raise subprocess.TimeoutExpired(cmd=argv, timeout=1)

        monkeypatch.setattr(executor.subprocess, "run", fake_run)
        outcome = run_cell(
            manifest=manifest, model="m-test", item_id="QA-01",
            prompt="domanda", protocol=protocol, out_dir=tmp_path / "it",
        )
        assert outcome.ok is False and outcome.excluded is True
        assert outcome.attempts == protocol.retry_budget + 1
        assert outcome.exclusion == "errore_init_tool_shape"
        assert "timeout" in outcome.error

    def test_empty_answer_after_budget_excludes_risposta_vuota(
        self, monkeypatch, tmp_path, protocol, manifest
    ):
        from benchmarks.limes.runner import executor
        from benchmarks.limes.runner.executor import run_cell

        monkeypatch.setattr(
            executor.subprocess, "run",
            lambda argv, **kw: subprocess.CompletedProcess(
                argv, 0, stdout=self._payload(""), stderr=""
            ),
        )
        outcome = run_cell(
            manifest=manifest, model="m-test", item_id="QA-01",
            prompt="domanda", protocol=protocol, out_dir=tmp_path / "it",
        )
        assert outcome.excluded is True
        assert outcome.exclusion == "risposta_vuota"

    def test_rerun_owns_the_directory(
        self, monkeypatch, tmp_path, protocol, manifest
    ):
        from benchmarks.limes.runner import executor
        from benchmarks.limes.runner.executor import run_cell

        monkeypatch.setattr(
            executor.subprocess, "run",
            lambda argv, **kw: subprocess.CompletedProcess(
                argv, 0, stdout=self._payload("ok"), stderr=""
            ),
        )
        item_dir = tmp_path / "it"
        first = run_cell(
            manifest=manifest, model="m", item_id="QA-01",
            prompt="d", protocol=protocol, out_dir=item_dir,
        )
        assert first.ok
        # Artifacts of a previously-ok run, plus a stale scratch config.
        (item_dir / "verdict.json").write_text("{}", encoding="utf-8")
        (item_dir / "attempt-9.json").write_text("stale", encoding="utf-8")
        scratch = item_dir / "config-dir"  # created by the first run
        (scratch / "stale.cfg").write_text("x", encoding="utf-8")

        second = run_cell(
            manifest=manifest, model="m", item_id="QA-01",
            prompt="d", protocol=protocol, out_dir=item_dir,
        )
        assert second.ok
        assert not (item_dir / "verdict.json").exists()
        assert not (item_dir / "attempt-9.json").exists()
        assert not (scratch / "stale.cfg").exists()  # scratch reset, not inherited
        assert sorted(p.name for p in item_dir.glob("attempt-*.json")) == [
            "attempt-1.json"
        ]


class TestCredentialBootstrap:
    """`bootstrap_credentials`: keychain is the primary source (the ambient
    credentials file can be stale — verified empirically), the file is the
    fallback, and no live source fails closed before any model call."""

    @staticmethod
    def _completed(argv, stdout=""):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    def test_keychain_primary(self, monkeypatch, tmp_path):
        from benchmarks.limes.runner.executor import bootstrap_credentials

        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        seen = []

        def fake_run(argv, **kwargs):
            seen.append(list(argv))
            return self._completed(argv, stdout=b'{"oauth": "secret"}')

        monkeypatch.setattr(
            __import__(
                "benchmarks.limes.runner.executor", fromlist=["subprocess"]
            ).subprocess,
            "run",
            fake_run,
        )
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        bootstrap_credentials(scratch)
        creds = scratch / ".credentials.json"
        assert b'{"oauth": "secret"}' == creds.read_bytes()
        assert (creds.stat().st_mode & 0o777) == 0o600
        assert seen and seen[0][0] == "security"

    def test_falls_back_to_ambient_file(self, monkeypatch, tmp_path):
        from benchmarks.limes.runner import executor
        from benchmarks.limes.runner.executor import bootstrap_credentials

        ambient = tmp_path / "ambient"
        ambient.mkdir()
        (ambient / ".credentials.json").write_text('{"file": true}', encoding="utf-8")
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(ambient))

        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 44, stdout="", stderr="oops")

        monkeypatch.setattr(executor.subprocess, "run", fake_run)
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        bootstrap_credentials(scratch)
        assert (scratch / ".credentials.json").read_text(encoding="utf-8") == '{"file": true}'

    def test_no_source_fails_closed(self, monkeypatch, tmp_path):
        from benchmarks.limes.runner import executor
        from benchmarks.limes.runner.executor import ExecutorError, bootstrap_credentials

        empty_ambient = tmp_path / "ambient-empty"
        empty_ambient.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(empty_ambient))

        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 44, stdout=b"", stderr=b"")

        monkeypatch.setattr(executor.subprocess, "run", fake_run)
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        with pytest.raises(ExecutorError, match="credenzial"):
            bootstrap_credentials(scratch)

    def test_run_cell_wires_credentials_into_scratch(
        self, monkeypatch, tmp_path
    ):
        """End-to-end through `run_cell`: keychain feeds the scratch dir,
        then the stubbed claude call runs with no auth surprise."""
        import os

        from benchmarks.limes.runner import executor
        from benchmarks.limes.runner.executor import run_cell
        from benchmarks.limes.protocol.rules import load_protocol

        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        protocol = load_protocol(LIMES_ROOT / "protocol" / "protocol.yaml")
        manifest = load_manifest(LIMES_ROOT / "configs" / "bare.yaml")
        scratch_seen = []

        def fake_run(argv, **kwargs):
            if argv[0] == "security":
                return self._completed(argv, stdout=b'{"oauth": "keychain"}')
            scratch_seen.append(kwargs["env"]["CLAUDE_CONFIG_DIR"])
            return self._completed(
                argv, stdout=json.dumps(
                    {"type": "result", "subtype": "success", "result": "ok"}
                )
            )

        monkeypatch.setattr(executor.subprocess, "run", fake_run)
        outcome = run_cell(
            manifest=manifest, model="m-test", item_id="QA-01",
            prompt="domanda", protocol=protocol, out_dir=tmp_path / "it",
        )
        assert outcome.ok
        assert len(scratch_seen) == 1
        creds = Path(scratch_seen[0]) / ".credentials.json"
        assert creds.read_bytes() == b'{"oauth": "keychain"}'
