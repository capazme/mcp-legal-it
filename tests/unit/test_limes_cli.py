"""CLI smoke tests: the entry points must work on the real files (plan,
check) and fail closed where the DESIGN demands it."""

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from benchmarks.limes.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
LIMES_ROOT = REPO_ROOT / "benchmarks" / "limes"


def _run(argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(argv)
    return code, buffer.getvalue()


class TestCli:
    def test_plan_on_real_files(self):
        code, out = _run(["plan", "--root", str(LIMES_ROOT)])
        assert code == 0
        # The plan prints the matrix the wave declares: 2 models x 4 configs.
        assert "matrice: 8 celle" in out
        # Default wave = the newest declared (wave-1), loaded on its slice.
        assert "bank:" in out and "289 item" in out
        assert "giudici: dichiarati" in out  # declared, run only on request
        assert "potenza OK" in out  # B1: the bank meets the declared power
        # Freeze status is diagnostic, never an error while uncommitted.
        assert "freeze" in out

    def test_check_on_real_files(self):
        code, out = _run(["check", "--root", str(LIMES_ROOT)])
        assert code == 0
        assert "bank OK" in out
        # The whole bank (every wave's slices) validates; each wave that
        # names its slice is validated under its own rules too.
        assert "wave-1 slice OK" in out
        assert "twin_families=34" in out

    def test_run_requires_wave(self):
        with pytest.raises(SystemExit):
            main(["run", "--root", str(LIMES_ROOT)])

    def test_dry_run_works_before_freeze(self):
        # The documented first step: a planning dry-run must not crash on
        # the freeze guard or on surfaces (mcp) that need a rendered config.
        code, out = _run(
            ["run", "--root", str(LIMES_ROOT), "--wave", "wave-0", "--dry-run"]
        )
        assert code == 0
        assert out.count("[dry]") == 8  # 2 models x 4 configs
        assert "<mcp-config>" in out  # shape preview, no secrets resolved
        assert "<plugin-dir>" in out  # plugin cells load the plugin at its ref
        assert "--output-format stream-json" in out

    def test_score_requires_verdicts(self, tmp_path):
        empty = tmp_path / "wave-0" / "m" / "bare"
        empty.mkdir(parents=True)
        with pytest.raises(SystemExit):
            main(["score", "--root", str(LIMES_ROOT), "--cell", str(empty)])

    def test_unknown_command_exits(self):
        with pytest.raises(SystemExit):
            main(["nope"])
