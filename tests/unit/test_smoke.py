"""Smoke test proving the toolchain is wired up end to end."""

import pytest

from trace_ai import main


def test_main_runs(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    assert "Hello from trace!" in capsys.readouterr().out
