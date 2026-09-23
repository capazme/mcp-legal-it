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
        assert "bank:" in out and "27 item" in out
        assert "meccanico-only" in out  # wave 0: no judges
        # Freeze status is diagnostic, never an error while uncommitted.
        assert "freeze" in out

    def test_check_on_real_files(self):
        code, out = _run(["check", "--root", str(LIMES_ROOT)])
        assert code == 0
        assert "bank OK" in out
        assert "twin_families=3" in out
        assert "items=27" in out

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
        assert "freeze PENDING" in out  # diagnostic, non-blocking here

    def test_score_requires_verdicts(self, tmp_path):
        empty = tmp_path / "wave-0" / "m" / "bare"
        empty.mkdir(parents=True)
        with pytest.raises(SystemExit):
            main(["score", "--root", str(LIMES_ROOT), "--cell", str(empty)])

    def test_unknown_command_exits(self):
        with pytest.raises(SystemExit):
            main(["nope"])
