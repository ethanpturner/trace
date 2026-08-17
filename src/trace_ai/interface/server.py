"""The read-only server: stdlib `http.server`, localhost only, GET only, no state change.

The interface exists at all because DEC-032 permits a read-only local view for the Stage 5
demonstration. Shipping it re-creates the browser-to-application boundary DEC-032 removed — a
listening port, a server process holding assessment data — so the boundary is bounded rather than
denied:

- It binds to `127.0.0.1` only (DEC-004, single-user local), so it is not reachable off the machine.
- It serves `GET` only; every other method is `405`. There is no state-changing endpoint, so the
  request-forgery threat the threat model names has nothing to forge — the read-only discipline is
  the mitigation, not a token check bolted onto a mutable surface.
- It renders through `render.py`, which HTML-escapes every source-derived value, so an excerpt of
  an untrusted document cannot inject markup into the reviewer's browser.

The store opens read-write because SQLite has no read-only handle here; read-only is a discipline,
and this module calls only the repository's read methods. One connection, one thread
(`http.server.HTTPServer`, not the threading variant), because a single reviewer needs no
concurrency and a shared SQLite connection across threads is a bug waiting to happen.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

from trace_ai.config import PROJECT_ROOT
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.interface import render
from trace_ai.services.assessment import AssessmentService, AssessmentServiceError

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.domain.assessment import Assessment

__all__ = ["Response", "route", "serve"]

HOST = "127.0.0.1"
SCORECARD = PROJECT_ROOT / "docs" / "eval" / "scorecard.html"


class Response:
    """A rendered response: a status, a content type, and a body. Pure data, no socket."""

    __slots__ = ("body", "content_type", "status")

    def __init__(self, status: int, body: str, *, content_type: str = "text/html; charset=utf-8"):
        self.status = status
        self.body = body
        self.content_type = content_type


def route(path: str, service: AssessmentService) -> Response:
    """Resolve one GET path to a response, reading only. The whole interface's logic lives here.

    Kept separate from the socket so it is a pure function of the path and the store — a test drives
    it directly, the way the CLI's `run` is driven, without binding a port.
    """
    segments = [segment for segment in path.split("/") if segment]

    if not segments:
        return Response(200, render.render_index(_assessments(service)))

    if segments == ["evaluation"] or (len(segments) == 2 and segments[1] == "evaluation"):
        scorecard = SCORECARD.read_text(encoding="utf-8") if SCORECARD.is_file() else None
        return Response(200, render.render_evaluation(scorecard))

    if segments[:1] == ["diff"]:
        # /diff/<before>/<after> compares two assessments' approved models (DEC-097, #508).
        # Two scoped reads, never a cross-assessment query -- the diff service opens each handle
        # in turn, which is why this lives beside the per-assessment routes rather than inside one.
        if len(segments) != 3:
            return Response(
                404,
                render.render_page(
                    "Not found", None, "", "<p>Diff is /diff/&lt;before&gt;/&lt;after&gt;.</p>"
                ),
            )
        before, after = segments[1], segments[2]
        if _find_assessment(service, before) is None or _find_assessment(service, after) is None:
            return Response(
                404, render.render_page("Not found", None, "", "<p>No such assessment.</p>")
            )
        from trace_ai.services.diff import diff_assessments
        from trace_ai.services.export import ExportError

        try:
            diff = diff_assessments(service.handle(before), service.handle(after))
        except ExportError as refused:
            return Response(
                200,
                render.render_page("Assessment diff", None, "", f"<p>Cannot diff: {refused}</p>"),
            )
        return Response(200, render.render_diff(before, after, diff))

    assessment_id = segments[0]
    assessment = _find_assessment(service, assessment_id)
    if assessment is None:
        return Response(
            404, render.render_page("Not found", None, "", "<p>No such assessment.</p>")
        )
    handle = service.handle(assessment_id)
    view = segments[1] if len(segments) > 1 else "overview"

    if view == "overview":
        return Response(200, render.render_overview(handle, assessment))
    if view == "context":
        return Response(200, render.render_context(handle, assessment))
    if view == "threats":
        return Response(200, render.render_threats(handle, assessment))
    if view == "workflow":
        return Response(200, render.render_workflow(handle, assessment))
    if view == "ledger":
        return Response(200, render.render_ledger(handle, assessment))
    if view == "questions":
        return Response(200, render.render_questions(handle, assessment))
    if view == "findings":
        return Response(200, render.render_findings(handle, assessment))
    if view == "lineage" and len(segments) > 2:
        return Response(200, render.render_lineage(handle, assessment, segments[2]))
    if view == "lineage":
        return Response(200, render.render_lineage_index(handle, assessment))
    return Response(404, render.render_page("Not found", None, "", "<p>No such view.</p>"))


def _assessments(service: AssessmentService) -> list[Assessment]:
    return sorted(service.list(), key=lambda assessment: assessment.id)


def _find_assessment(service: AssessmentService, assessment_id: str) -> Assessment | None:
    try:
        return service.get(assessment_id)
    except AssessmentServiceError:
        return None


def _make_handler(service: AssessmentService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "trace-view"

        def do_GET(self) -> None:
            response = route(self.path, service)
            payload = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(payload)))
            # No caching and no framing by another origin: this holds assessment data.
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(payload)

        def _refuse(self) -> None:
            self.send_error(405, "the view is read-only; it serves GET only (DEC-032)")

        do_POST = _refuse  # noqa: N815
        do_PUT = _refuse  # noqa: N815
        do_PATCH = _refuse  # noqa: N815
        do_DELETE = _refuse  # noqa: N815

        def log_message(self, *args: object) -> None:
            # Silence the default request logging: a request path could carry a finding identifier,
            # and stderr is not where the interface reports.
            return

    return Handler


def serve(data_root: Path, *, port: int = 8765) -> None:
    """Serve the read-only interface over one data root until interrupted (localhost only)."""
    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        httpd = HTTPServer((HOST, port), _make_handler(service))
        base = f"http://{HOST}:{httpd.server_address[1]}"
        print(f"read-only view on {base}  (Ctrl-C to stop)")
        for assessment in _assessments(service):
            print(f"  {base}/{assessment.id}/overview")
            print(f"  {base}/{assessment.id}/lineage")
        print(f"  {base}/evaluation")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
        finally:
            httpd.server_close()
