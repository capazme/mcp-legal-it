"""Unit tests for release.py prompt/rollback safety.

Regression tests for the v2.11.0 release incident (2026-07-30): with piped
stdin, an EOF on the post-release prompt raised SystemExit(0) inside the
RollbackContext, which rolled back LOCAL state (tag, manifests) after the
push had already succeeded — leaving local and remote diverged.

All tests are offline and side-effect free: they exercise ask()/ask_yes_no()
with a patched input() and the RollbackContext in isolation.
"""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "release_script", Path(__file__).parents[2] / "release.py"
)
rel = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rel)


def _raise(exc):
    def _inner(*args, **kwargs):
        raise exc
    return _inner


@pytest.fixture(autouse=True)
def _reset_non_interactive():
    yield
    setter = getattr(rel, "set_non_interactive", None)
    if setter is not None:
        setter(False)


# ---------------------------------------------------------------------------
# ask() / ask_yes_no() — EOF must degrade to the default, never exit
# ---------------------------------------------------------------------------

class TestAskEof:
    def test_ask_eof_returns_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", _raise(EOFError()))
        try:
            result = rel.ask("Domanda", "valore-default")
        except SystemExit:
            pytest.fail("ask() must not exit on EOF; it must return the default")
        assert result == "valore-default"

    def test_ask_eof_without_default_returns_empty(self, monkeypatch):
        monkeypatch.setattr("builtins.input", _raise(EOFError()))
        try:
            result = rel.ask("Domanda")
        except SystemExit:
            pytest.fail("ask() must not exit on EOF")
        assert result == ""

    def test_ask_yes_no_eof_keeps_true_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", _raise(EOFError()))
        try:
            assert rel.ask_yes_no("Procedere?", default=True) is True
        except SystemExit:
            pytest.fail("ask_yes_no() must not exit on EOF")

    def test_ask_yes_no_eof_keeps_false_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", _raise(EOFError()))
        try:
            assert rel.ask_yes_no("Procedere?", default=False) is False
        except SystemExit:
            pytest.fail("ask_yes_no() must not exit on EOF")

    def test_ask_yes_no_unattended_override_on_eof(self, monkeypatch):
        # The push confirmation defaults to yes for humans, but an unattended
        # run (EOF) must never push implicitly: unattended=False wins on EOF.
        import inspect
        assert "unattended" in inspect.signature(rel.ask_yes_no).parameters, (
            "ask_yes_no() must accept unattended= for EOF/non-interactive runs"
        )
        monkeypatch.setattr("builtins.input", _raise(EOFError()))
        assert rel.ask_yes_no("Pushare?", default=True, unattended=False) is False

    def test_ask_yes_no_unattended_override_non_interactive(self, monkeypatch):
        monkeypatch.setattr(
            "builtins.input",
            _raise(AssertionError("input() must not be called in non-interactive mode")),
        )
        rel.set_non_interactive(True)
        assert rel.ask_yes_no("Pushare?", default=True, unattended=False) is False

    def test_ask_yes_no_interactive_answer_beats_unattended(self, monkeypatch):
        # unattended= only applies when stdin is unavailable; a real answer wins.
        monkeypatch.setattr("builtins.input", lambda *a: "s")
        assert rel.ask_yes_no("Pushare?", default=True, unattended=False) is True

    def test_ask_keyboard_interrupt_still_exits(self, monkeypatch):
        # Ctrl-C is an intentional abort: exiting is correct (with the
        # conventional 130 code). Rollback protection for the post-push
        # phase comes from RollbackContext.disarm(), not from swallowing
        # the interrupt.
        monkeypatch.setattr("builtins.input", _raise(KeyboardInterrupt()))
        with pytest.raises(SystemExit) as excinfo:
            rel.ask("Domanda", "default")
        assert excinfo.value.code == 130


# ---------------------------------------------------------------------------
# Non-interactive mode — prompts never touch stdin
# ---------------------------------------------------------------------------

class TestNonInteractive:
    def test_setter_exists(self):
        assert hasattr(rel, "set_non_interactive"), (
            "release.py must expose set_non_interactive() for --non-interactive"
        )

    def test_ask_skips_input_entirely(self, monkeypatch):
        monkeypatch.setattr(
            "builtins.input",
            _raise(AssertionError("input() must not be called in non-interactive mode")),
        )
        rel.set_non_interactive(True)
        assert rel.ask("Domanda", "default") == "default"
        assert rel.ask_yes_no("Procedere?", default=False) is False


# ---------------------------------------------------------------------------
# interactive_setup() — zero-args mode must refuse a non-TTY stdin
# ---------------------------------------------------------------------------

class TestInteractiveSetupGuard:
    def test_refuses_non_tty_stdin(self, monkeypatch):
        # With EOF degrading to defaults, a no-args run with closed stdin would
        # otherwise walk the whole menu on defaults and return a real release
        # Namespace. Non-TTY stdin must abort before any prompt.
        monkeypatch.setattr(rel.sys.stdin, "isatty", lambda: False)
        monkeypatch.setattr("builtins.input", _raise(EOFError()))
        with pytest.raises(SystemExit) as excinfo:
            rel.interactive_setup()
        assert excinfo.value.code == 1


# ---------------------------------------------------------------------------
# _push_release — the point of no return is the FIRST successful push
# ---------------------------------------------------------------------------

class TestPushRelease:
    def test_helper_exists(self):
        assert hasattr(rel, "_push_release"), (
            "release.py must expose _push_release(rb, ...) so both flows share "
            "the push sequence and its disarm point"
        )

    def test_tag_push_failure_does_not_roll_back(self, monkeypatch):
        # Branch push succeeds, tag push fails: origin already has the release
        # commits, so the armed rollback must NOT fire.
        calls = []

        def fake_run_git(*args, dry_run=False):
            calls.append(args)
            if "--tags" in args:
                raise RuntimeError("network error")

        monkeypatch.setattr(rel, "run_git", fake_run_git)
        executed = []
        with pytest.raises(RuntimeError, match="network error"):
            with rel.RollbackContext(dry_run=False) as rb:
                rb.register("canary", lambda: executed.append("rolled-back"))
                rel._push_release(
                    rb, dry=False, branches=("main", "develop"),
                    tag="v9.9.9", release_branch="release/9.9.9",
                )
        assert calls[0] == ("push", "origin", "main", "develop")
        assert executed == [], "rollback must not run once branches are pushed"

    def test_full_push_sequence_order(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            rel, "run_git", lambda *args, dry_run=False: calls.append(args)
        )
        with rel.RollbackContext(dry_run=False) as rb:
            rel._push_release(
                rb, dry=False, branches=("main",), tag="v9.9.9", release_branch=None,
            )
        assert calls == [
            ("push", "origin", "main"),
            ("push", "origin", "--tags"),
        ]


# ---------------------------------------------------------------------------
# RollbackContext — disarm() after a successful push
# ---------------------------------------------------------------------------

class TestRollbackDisarm:
    def test_disarm_exists(self):
        ctx = rel.RollbackContext(dry_run=False)
        assert hasattr(ctx, "disarm"), (
            "RollbackContext must expose disarm() to call after a successful push"
        )

    def test_disarmed_context_skips_rollback_actions(self):
        executed = []
        with pytest.raises(RuntimeError):
            with rel.RollbackContext(dry_run=False) as ctx:
                ctx.register("azione", lambda: executed.append("rolled-back"))
                ctx.disarm()
                raise RuntimeError("failure after push")
        assert executed == [], "disarmed context must not run rollback actions"

    def test_armed_context_still_rolls_back(self):
        # Characterization guard: without disarm(), rollback keeps working.
        executed = []
        with pytest.raises(RuntimeError):
            with rel.RollbackContext(dry_run=False) as ctx:
                ctx.register("azione", lambda: executed.append("rolled-back"))
                raise RuntimeError("failure before push")
        assert executed == ["rolled-back"]

    def test_disarmed_context_still_propagates_exception(self):
        with pytest.raises(RuntimeError, match="failure after push"):
            with rel.RollbackContext(dry_run=False) as ctx:
                ctx.disarm()
                raise RuntimeError("failure after push")
