"""Read-only repository ingestion at a pinned commit (#597).

Every test runs against a local fixture repository built with `git init` in tmp_path and fetched
over `file://` — the identical code path the https integration takes, with no network and no
key, which is what keeps CI keyless. The properties under test are the DEC's: the pin is the
identity, the selection rule is decided, provenance survives flattening, and a token never
surfaces.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.source_document import TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.ingestion.repository import (
    RepositoryIngestionError,
    _fetch_url,
    _redact,
    ingest_repository,
    select_paths,
)


def _git(repo: Path, *arguments: str) -> str:
    command = ["git", "-C", str(repo), *arguments]
    completed = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        text=True,
        check=True,
        env={
            "PATH": os.environ["PATH"],
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        },
    )
    return completed.stdout.strip()


@pytest.fixture
def fixture_repo(tmp_path: Path) -> tuple[str, str]:
    """A local repository with readable, unreadable, hidden, and workflow files; returns (url, sha)."""
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Fixture\n\nAn overview.\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "auth.md").write_text("## Auth\n\nSSO everywhere.\n", encoding="utf-8")
    (repo / "docs" / "README.md").write_text("# Docs index\n", encoding="utf-8")
    (repo / "main.tf").write_text('resource "aws_db_instance" "db" {}\n', encoding="utf-8")
    (repo / "app.py").write_text("print('not review material')\n", encoding="utf-8")
    (repo / ".hidden").mkdir()
    (repo / ".hidden" / "notes.md").write_text("skipped\n", encoding="utf-8")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("jobs: {}\n", encoding="utf-8")
    _git(repo, "init", "--quiet")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "fixture")
    sha = _git(repo, "rev-parse", "HEAD")
    return f"file://{repo}", sha


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    with AssessmentStore.at_root(tmp_path / "store") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "store")
        created = service.create(
            "Repo", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def test_ingestion_registers_the_selection_rule_with_provenance(
    fixture_repo: tuple[str, str], handle: AssessmentHandle
) -> None:
    url, sha = fixture_repo
    documents = ingest_repository(handle, url, sha)

    by_path = {document.metadata["repository_path"]: document for document in documents}
    assert set(by_path) == {
        ".github/workflows/ci.yml",
        "README.md",
        "docs/README.md",
        "docs/auth.md",
        "main.tf",
    }
    nested = by_path["docs/auth.md"]
    assert nested.filename == "docs__auth.md"
    assert nested.metadata["repository"] == url
    assert nested.metadata["commit"] == sha
    assert nested.origin is SourceOrigin.UPLOADED_DOCUMENT
    assert nested.trust_level is TrustLevel.UNTRUSTED
    # Two README.md files flatten to distinct names rather than colliding in the store.
    assert by_path["README.md"].filename != by_path["docs/README.md"].filename


def test_a_branch_tag_or_short_sha_is_refused(
    fixture_repo: tuple[str, str], handle: AssessmentHandle
) -> None:
    url, sha = fixture_repo
    for reference in ("main", "v1.0", sha[:12]):
        with pytest.raises(RepositoryIngestionError, match="moving or ambiguous"):
            ingest_repository(handle, url, reference)


def test_the_pin_is_the_tree_that_registers_not_the_tip(
    fixture_repo: tuple[str, str], handle: AssessmentHandle, tmp_path: Path
) -> None:
    url, sha = fixture_repo
    repo = Path(url.removeprefix("file://"))
    (repo / "README.md").write_text("# Moved on\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "later")

    documents = ingest_repository(handle, url, sha)
    readme = next(d for d in documents if d.metadata["repository_path"] == "README.md")
    stored = handle.artifacts.area("sources") / readme.filename
    assert "An overview." in stored.read_text(encoding="utf-8")


def test_reingesting_the_same_commit_is_idempotent(
    fixture_repo: tuple[str, str], handle: AssessmentHandle
) -> None:
    url, sha = fixture_repo
    first = {d.id for d in ingest_repository(handle, url, sha)}
    second = {d.id for d in ingest_repository(handle, url, sha)}
    assert first == second


def test_an_unreachable_sha_fails_with_nothing_registered(
    fixture_repo: tuple[str, str], handle: AssessmentHandle
) -> None:
    from trace_ai.domain.source_document import SourceDocument

    url, _ = fixture_repo
    with pytest.raises(RepositoryIngestionError):
        ingest_repository(handle, url, "0" * 40)
    assert handle.objects.list(SourceDocument) == []


def test_a_credentialed_url_is_refused_and_a_token_never_surfaces() -> None:
    with pytest.raises(RepositoryIngestionError, match="must not embed credentials"):
        ingest_repository(None, "https://user:pass@example.com/r.git", "0" * 40)  # type: ignore[arg-type]
    fetch = _fetch_url("https://example.com/org/repo.git", "tok-123")
    assert "tok-123" in fetch
    assert _redact(f"fatal: {fetch}", "tok-123").count("tok-123") == 0


def test_the_selection_rule_is_sorted_and_decided(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    (root / "b").mkdir(parents=True)
    (root / "a.md").write_text("x", encoding="utf-8")
    (root / "b" / "c.yaml").write_text("k: v", encoding="utf-8")
    (root / "b" / "ignored.rs").write_text("fn main() {}", encoding="utf-8")
    (root / ".ci").mkdir()
    (root / ".ci" / "d.md").write_text("hidden", encoding="utf-8")
    selected = [p.relative_to(root).as_posix() for p in select_paths(root)]
    assert selected == ["a.md", "b/c.yaml"]


def test_a_repository_with_nothing_readable_is_stated(
    tmp_path: Path, handle: AssessmentHandle
) -> None:
    repo = tmp_path / "empty-repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('code only')\n", encoding="utf-8")
    _git(repo, "init", "--quiet")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "code only")
    sha = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(RepositoryIngestionError, match="no file the loader reads"):
        ingest_repository(handle, f"file://{repo}", sha)


def test_github_token_is_a_secret_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    from trace_ai.config import Settings

    settings = Settings(github_token=SecretStr("tok-abc"))
    assert "tok-abc" not in repr(settings)
