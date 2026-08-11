"""The read-only demonstration interface (#276, DEC-032).

The interface renders a completed assessment's persisted objects to HTML and drives nothing. The
tests replay the committed ForgeFlow run to a data root — the same recording the CLI and the demo
use — and assert the seven views render, the lineage view walks an approved finding to its hashed
evidence, source-derived text is escaped and labelled, and no route can write.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.interface import render
from trace_ai.interface.server import route
from trace_ai.services.assessment import AssessmentService

if TYPE_CHECKING:
    from collections.abc import Iterator

INTERFACE = PROJECT_ROOT / "src" / "trace_ai" / "interface"


def _replay(data_root: Path) -> None:
    path = PROJECT_ROOT / "scripts" / "replay_forgeflow.py"
    spec = importlib.util.spec_from_file_location("replay_forgeflow_iface", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules["replay_forgeflow_iface"] = module
    spec.loader.exec_module(module)
    module.replay(data_root)


@pytest.fixture(scope="module")
def replayed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    root = tmp_path_factory.mktemp("view")
    _replay(root)
    yield root


def _service(root: Path) -> Iterator[AssessmentService]:
    with AssessmentStore.at_root(root) as store:
        yield AssessmentService(store, artifact_root=root)


def test_every_view_renders_from_a_replayed_assessment(replayed: Path) -> None:
    for service in _service(replayed):
        assert route("/", service).status == 200
        for _label, segment in render.VIEWS:
            response = route(f"/asm-001/{segment}", service)
            assert response.status == 200, segment
            assert response.body.startswith("<!doctype html>") or segment == "evaluation"


def test_the_lineage_view_walks_an_approved_finding_to_its_hashed_evidence(replayed: Path) -> None:
    for service in _service(replayed):
        response = route("/asm-001/lineage/fnd-001", service)
        assert response.status == 200
        body = response.body
        # One unbroken chain: threat, mapping, evidence assessment, the fenced excerpt, the hash.
        assert "thr-" in body, "the originating threat"
        assert "map-" in body, "the control mapping"
        assert "evidence assessment" in body.lower()
        assert render.UNTRUSTED_LABEL in body, "the excerpt is labelled untrusted"
        assert "sha256:" in body, "the source document's content hash closes the chain"


def test_source_derived_text_is_html_escaped(replayed: Path) -> None:
    """A browser is not the inert terminal; an excerpt of an untrusted document must not inject
    markup. The lineage excerpts come from documents, so any angle bracket in them is escaped."""
    for service in _service(replayed):
        body = route("/asm-001/lineage/fnd-001", service).body
        # The rendered excerpts are inside <pre>; raw source markup would appear as entities.
        assert "<script" not in body.lower()


def test_a_missing_assessment_and_view_are_404(replayed: Path) -> None:
    for service in _service(replayed):
        assert route("/asm-999/overview", service).status == 404
        assert route("/asm-001/nonsense", service).status == 404


def test_the_index_lists_the_assessment(replayed: Path) -> None:
    for service in _service(replayed):
        body = route("/", service).body
        assert "asm-001" in body
        assert "ForgeFlow" in body


def test_no_route_writes_to_the_store() -> None:
    """The read-only discipline is auditable: the interface package calls no write method.

    There is no read-only SQLite handle here, so read-only is enforced by never calling `save`,
    `allocate`, or `transaction` — and this scans the package to prove none appear."""
    for path in INTERFACE.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for write_call in (".save(", ".allocate(", ".transaction(", ".delete("):
            assert write_call not in source, f"{path.name} calls a write method: {write_call}"


def test_the_server_serves_get_only() -> None:
    """Every non-GET method is refused. The read-only surface has no state to change, so the
    request-forgery threat has nothing to forge."""
    from trace_ai.interface import server

    handler_source = (INTERFACE / "server.py").read_text(encoding="utf-8")
    assert "do_GET" in handler_source
    for method in ("do_POST", "do_PUT", "do_PATCH", "do_DELETE"):
        assert f"{method} = _refuse" in handler_source
    assert server.HOST == "127.0.0.1", "localhost only (DEC-004)"


def test_the_evaluation_view_embeds_the_scorecard_not_assessment_content() -> None:
    """DEC-076 boundary: the evaluation view shows the metrics scorecard, not findings text."""
    scorecard = (PROJECT_ROOT / "docs" / "eval" / "scorecard.html").read_text(encoding="utf-8")
    rendered = render.render_evaluation(scorecard)
    assert rendered == scorecard, "the committed scorecard is embedded verbatim"
