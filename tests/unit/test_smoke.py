"""Smoke test proving the toolchain is wired up end to end."""

import pytest

from trace_ai.cli import run


def test_main_runs(capsys: pytest.CaptureFixture[str]) -> None:
    """`run([])` rather than `main()`: the entry point now reads `sys.argv`, which under pytest is
    pytest's own arguments. The behaviour asserted is unchanged."""
    assert run([]) == 0
    assert "context-aware security architecture analysis" in capsys.readouterr().out
