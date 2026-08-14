"""The public architecture image (#354) stays true to the pipeline it draws.

The image is a committed, hand-authored SVG — source and render in one file. What can rot is
the phase list, so this pins every `Phase` value into the image text, in both directions is
unnecessary: extra prose is fine, a missing or renamed phase is not.
"""

from __future__ import annotations

from trace_ai.config import PROJECT_ROOT
from trace_ai.workflow.phases import Phase

IMAGE = PROJECT_ROOT / "docs" / "assets" / "architecture.svg"


def test_the_image_names_every_phase_exactly() -> None:
    svg = IMAGE.read_text(encoding="utf-8")
    missing = [phase.value for phase in Phase if phase.value not in svg]
    assert not missing, f"the architecture image is missing phases: {missing}"


def test_the_image_marks_the_two_checkpoints_and_the_seam() -> None:
    svg = IMAGE.read_text(encoding="utf-8")
    assert "human checkpoint" in svg
    assert "Model seam" in svg
    assert "Authoritative state" in svg
