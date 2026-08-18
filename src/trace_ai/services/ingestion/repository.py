"""Read-only repository ingestion at a pinned commit (future-features 3.1, #597).

Future-features 3.1 deferred repository ingestion "until local document ingestion and evidence
traceability are reliable"; the parser family, PDF ingestion, and the lineage walk met that
condition, and this module is the discharge — scoped the way the deferral asked: read-only,
pinned, allowlisted.

**The commit is the identity.** Ingestion names `(repository, commit)` and refuses anything that
is not a full forty-hex SHA: a branch or tag is a moving reference, and a source set that can
change under an assessment breaks the reproducibility every `EvidenceReference` hash depends on.
After checkout the working tree's HEAD is re-resolved and compared to the requested SHA, so a
server that silently substituted a different tree is caught before a byte is registered.

**The fetch is the application's, at ingestion time.** Agents get no internet (agent-design
section 22) and nothing behind the model seam touches the network; this module runs the system
`git` client in a subprocess — a deliberate dependency decision over a Python git library: the
client is already the operator's trust decision for this repository host, it receives no
repository-controlled arguments beyond the URL and SHA the operator typed, and a clone executes
no repository-provided code (hooks are not cloned; no filter drivers are configured).

**Fetched content is source-document content.** Every selected file enters through
`DocumentLoader` exactly as an uploaded document does — untrusted, format from the extension,
content never read here. The selection rule is decided, not everything: every file in the tree
whose suffix the loader supports, excluding dot-directories except `.github/workflows` (workflow
definitions are review material; a repository's other dot-trees are tooling). Skipping the rest
differs from `load_directory`'s refuse-unsupported rule on purpose: a curated input directory
containing an Office file is a reviewer expecting it to be assessed, while a repository is a
whole codebase, and "what the loader reads" *is* the curated rule.

**Nested paths flatten with their provenance kept.** The artifact store treats filenames as
untrusted and stores flat, so `docs/auth/overview.md` registers as `docs__auth__overview.md`
while `repository_path` in the document's metadata records the true in-repo path, beside
`repository` (the credential-free URL) and `commit`.

**A token never surfaces.** A configured `github_token` (`Settings`, `SecretStr`) is injected
into the clone URL for the subprocess only; the URL recorded in metadata is the clean one, and
any error text this module raises has the token replaced before it can reach a message or a log.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.source_document import TrustLevel
from trace_ai.services.ingestion.loader import SUFFIXES, DocumentLoader

if TYPE_CHECKING:
    from pydantic import SecretStr

    from trace_ai.domain.source_document import SourceDocument
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.execution_ledger import ExecutionLedger

__all__ = [
    "RepositoryIngestionError",
    "ingest_repository",
    "select_paths",
]

_FULL_SHA: Final = re.compile(r"^[0-9a-f]{40}$")

# URL schemes the fetch will speak. `https` is the integration; `file` exists so the test suite
# exercises the identical code path against local fixture repositories with no network and no
# key, which is what keeps CI keyless (evaluation-plan section 3's repeatability posture).
_SCHEMES: Final = ("https://", "file://")

_WORKFLOWS: Final = (".github", "workflows")


class RepositoryIngestionError(RuntimeError):
    """A repository that cannot become a source set, with the reason stated."""


def _require_clean_url(url: str) -> str:
    if not url.startswith(_SCHEMES):
        raise RepositoryIngestionError(
            f"unsupported repository URL scheme for {url!r}: repository ingestion speaks "
            "https:// (and file:// for local fixtures)"
        )
    if "@" in url.split("://", 1)[1].split("/", 1)[0]:
        raise RepositoryIngestionError(
            "the repository URL must not embed credentials; configure github_token in the "
            "environment instead, so the secret stays out of metadata and logs"
        )
    return url


def _require_full_sha(commit: str) -> str:
    if not _FULL_SHA.match(commit):
        raise RepositoryIngestionError(
            f"{commit!r} is not a full forty-character commit SHA. A branch, tag, or "
            "abbreviated SHA is a moving or ambiguous reference, and a moving reference is "
            "not an ingestible identity: the pinned commit is what makes the source set "
            "reproducible."
        )
    return commit


def _redact(text: str, token: str | None) -> str:
    return text.replace(token, "***") if token else text


def _git_env() -> dict[str, str]:
    return {"GIT_TERMINAL_PROMPT": "0", "PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def _run_git(arguments: list[str], *, token: str | None) -> subprocess.CompletedProcess[str]:
    # Arguments are operator-supplied (the URL and SHA the operator typed), never repository
    # content, and the environment is minimal with prompting off. The client resolves from PATH
    # deliberately: the operator's git is the trust decision (module docstring).
    command = ["git", *arguments]
    completed = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=False,
    )
    if completed.returncode != 0:
        raise RepositoryIngestionError(
            f"git {arguments[0]} failed: {_redact(completed.stderr.strip(), token)[:500]}"
        )
    return completed


def _fetch_url(url: str, token: str | None) -> str:
    if token is None or not url.startswith("https://"):
        return url
    scheme, rest = url.split("://", 1)
    return f"{scheme}://x-access-token:{token}@{rest}"


def _clone_pinned(url: str, commit: str, destination: Path, *, token: str | None) -> None:
    _run_git(["clone", "--quiet", _fetch_url(url, token), str(destination)], token=token)
    _run_git(["-C", str(destination), "checkout", "--quiet", "--detach", commit], token=token)
    resolved = _run_git(["-C", str(destination), "rev-parse", "HEAD"], token=token)
    if resolved.stdout.strip() != commit:
        raise RepositoryIngestionError(
            f"the checked-out HEAD is {resolved.stdout.strip()!r}, not the requested "
            f"{commit!r}; the pin did not hold and nothing was registered"
        )


def select_paths(root: Path) -> list[Path]:
    """The decided selection rule: loader-readable suffixes, dot-trees excluded, workflows kept.

    Sorted by in-repo path so two ingestions of the same commit register the same sequence and
    therefore the same identifiers (the repeatability rule `load_directory` states).
    """
    selected: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        hidden = [part for part in relative.parts if part.startswith(".")]
        if hidden and relative.parts[:2] != _WORKFLOWS:
            continue
        if path.suffix.casefold() not in SUFFIXES:
            continue
        selected.append(path)
    return sorted(selected, key=lambda p: p.relative_to(root).as_posix())


def _flattened(relative: Path) -> str:
    return "__".join(relative.parts)


def ingest_repository(
    handle: AssessmentHandle,
    url: str,
    commit: str,
    *,
    ledger: ExecutionLedger | None = None,
    github_token: SecretStr | None = None,
    workdir: Path | None = None,
) -> list[SourceDocument]:
    """Register the selected files of `url` at `commit`, read-only, and report what registered.

    Every document carries `repository`, `commit`, and `repository_path` in its metadata; the
    stored filename is the flattened in-repo path. Registration is the loader's and inherits
    its idempotency, so re-ingesting the same commit returns the documents it already made.
    """
    clean = _require_clean_url(url)
    pinned = _require_full_sha(commit)
    token = github_token.get_secret_value() if github_token is not None else None

    loader = DocumentLoader(handle, ledger=ledger)
    documents: list[SourceDocument] = []
    with tempfile.TemporaryDirectory(prefix="trace-repo-ingest-") as scratch:
        checkout = Path(workdir) if workdir is not None else Path(scratch) / "checkout"
        _clone_pinned(clean, pinned, checkout, token=token)
        staging = Path(scratch) / "flat"
        staging.mkdir(parents=True, exist_ok=True)
        for path in select_paths(checkout):
            relative = path.relative_to(checkout)
            flat = staging / _flattened(relative)
            shutil.copyfile(path, flat)
            documents.append(
                loader.load_document(
                    flat,
                    origin=SourceOrigin.UPLOADED_DOCUMENT,
                    trust_level=TrustLevel.UNTRUSTED,
                    extra_metadata={
                        "repository": clean,
                        "commit": pinned,
                        "repository_path": relative.as_posix(),
                    },
                )
            )
    if not documents:
        raise RepositoryIngestionError(
            f"{clean} at {pinned} contains no file the loader reads; an empty source set is "
            "an assessment of nothing, stated rather than silently created"
        )
    return documents
