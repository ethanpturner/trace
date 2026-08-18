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


def test_the_lineage_walk_is_navigable_and_re_verified(replayed: Path) -> None:
    """#533: every hop carries an anchor, the page opens with a contents line, and each excerpt
    is re-verified against its source as the page renders — the verdict at the leaf."""
    for service in _service(replayed):
        body = route("/asm-001/lineage/fnd-001", service).body
        # Contents line: fragment links to the hops.
        assert 'href="#threats"' in body
        assert 'href="#evidence"' in body
        # Anchors: the hop sections and the objects inside them.
        assert '<a id="mappings"></a>' in body
        assert '<a id="thr-001"></a>' in body
        assert '<a id="evd-' in body
        # The leaf verdict: a fresh replay verifies everything it quotes.
        assert '<span class="ok">verifies</span>' in body
        assert "re-verified" in body


def test_a_drifted_excerpt_shows_its_verdict_at_the_leaf(replayed: Path, tmp_path: Path) -> None:
    """Tamper with a stored source, and the walk says so instead of quoting it as verified."""
    import shutil

    root = tmp_path / "drifted"
    shutil.copytree(replayed, root)
    sources = root / "assessments" / "asm-001" / "sources"
    for victim in sources.iterdir():
        if victim.is_file():
            victim.write_text("# Replaced\n", encoding="utf-8")
    for service in _service(root):
        body = route("/asm-001/lineage/fnd-001", service).body
        assert 'class="drift"' in body
        assert '<span class="ok">verifies</span>' not in body


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
    """DEC-076 boundary: the evaluation view shows the metrics scorecard, not findings text.

    One navigation line is injected after `<body>` so the view is not a dead end (#431); every
    other byte is the committed page, so the embed-don't-absorb boundary holds.
    """
    scorecard = (PROJECT_ROOT / "docs" / "eval" / "scorecard.html").read_text(encoding="utf-8")
    rendered = render.render_evaluation(scorecard)
    assert "&larr; assessments" in rendered
    without_backlink = "\n".join(
        line for line in rendered.splitlines() if "&larr; assessments" not in line
    )
    assert without_backlink == scorecard.rstrip("\n"), (
        "apart from the injected navigation line, the committed scorecard embeds verbatim"
    )


def test_the_lineage_index_is_one_click_from_the_navigation() -> None:
    """#431: the differentiator view was reachable only by hand-typed deep link."""
    assert ("Lineage", "lineage") in render.VIEWS


def test_the_threats_and_ledger_views_render(replayed: Path) -> None:
    """Both were absent from the pre-#508 view; the VIEWS iteration covers them, and this names
    them so a regression that drops one is legible."""
    for service in _service(replayed):
        threats = route("/asm-001/threats", service)
        ledger = route("/asm-001/ledger", service)
        assert threats.status == 200 and "Threats" in threats.body
        assert ledger.status == 200 and "Ledger" in ledger.body


def test_the_diff_route_compares_two_assessments(replayed: Path) -> None:
    """DEC-097's diff, reachable read-only (#508): the route resolves, reads both scopes, and
    renders. Diffing the replay's one assessment against itself exercises the whole path; the
    context families match self-to-self and read unchanged."""
    for service in _service(replayed):
        response = route("/diff/asm-001/asm-001", service)
        assert response.status == 200
        assert "asm-001" in response.body
        assert "components: " in response.body and "unchanged" in response.body


def test_the_diff_route_shapes_are_guarded(replayed: Path) -> None:
    for service in _service(replayed):
        assert route("/diff/asm-001", service).status == 404
        assert route("/diff/asm-001/asm-999", service).status == 404


def test_no_route_writes_to_the_store_including_the_new_ones() -> None:
    """The read-only guarantee extends to threats, ledger, diff, and source: DEC-078."""
    import ast

    source = (INTERFACE / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"save", "transaction", "allocate"}:
            raise AssertionError(f"server.py calls a write method: {node.attr}")


def test_the_lineage_excerpts_link_into_the_source(replayed: Path) -> None:
    """#572: the excerpt is not the end of the chain — it links to the stored document itself,
    at the span the citation names, so the walk is clickable from the finding to the source."""
    for service in _service(replayed):
        body = route("/asm-001/lineage/fnd-001", service).body
        assert 'href="/asm-001/source/evd-' in body
        assert "open the source at this span" in body


def test_the_source_view_marks_the_cited_span(replayed: Path) -> None:
    """The source view renders the whole original document, escaped and labelled untrusted,
    with an anchor per line and the cited lines highlighted."""
    import re

    for service in _service(replayed):
        lineage = route("/asm-001/lineage/fnd-001", service).body
        links = re.findall(r'href="(/asm-001/source/evd-[^"#]+)#L(\d+)"', lineage)
        assert links, "at least one excerpt cites a line span"
        path, start = links[0]
        body = route(path, service).body
        assert render.UNTRUSTED_LABEL in body
        assert f'id="L{start}" class="src-line hit"' in body
        assert 'id="L1" class="src-line' in body, "the whole document renders, not the excerpt"
        assert "verifies" in body or "drift" in body


def test_the_lineage_hops_cross_link_by_anchor(replayed: Path) -> None:
    """#572: an identifier that names another object in the walk is a link to its anchor —
    the assessment's subject, the mapping's threat and evidence — not bare text."""
    import re

    for service in _service(replayed):
        body = route("/asm-001/lineage/fnd-001", service).body
        assert re.search(r'<a href="#(thr|map)-\d+"><code>', body), "the assessment's subject"
        assert re.search(r'<a href="#evd-[^"]+"><code>', body), "the mapping's evidence"


def test_hostile_source_content_is_escaped_in_the_source_view(replayed: Path) -> None:
    """The injection fixture renders as text: the whole document passes through the escaper,
    so instruction-shaped content is visible to the reviewer and inert to the browser."""
    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.domain.source_document import SourceDocument

    for service in _service(replayed):
        handle = service.handle("asm-001")
        documents = {doc.id: doc.filename for doc in handle.objects.list(SourceDocument)}
        hostile = next(
            reference
            for reference in handle.objects.list(EvidenceReference)
            if documents[reference.source_document_id] == "sample-repository-notes.md"
        )
        body = route(f"/asm-001/source/{hostile.id}", service).body
        assert "<script" not in body.lower()
        raw = handle.artifacts.read("sources", "sample-repository-notes.md").decode("utf-8")
        for line in raw.splitlines():
            if "<" in line:
                assert line not in body, "raw markup from the document reached the page"


def test_an_unknown_evidence_reference_renders_a_refusal(replayed: Path) -> None:
    for service in _service(replayed):
        body = route("/asm-001/source/evd-999", service).body
        assert "No such evidence reference" in body
