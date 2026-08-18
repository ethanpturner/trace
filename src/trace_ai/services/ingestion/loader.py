"""The document loader: the first code that reads a file supplied for review.

`current-architecture.md` section 5.4 lists nine ingestion responsibilities. This module performs
the six that do not depend on segmentation — accept the file, validate the format, assign a stable
identifier, preserve the original content, generate the content hash, record ingestion metadata —
and leaves normalization, division into sections, and location preservation to the indexing node
(#55), which is why every document it produces is `registered` rather than `ingested`.

`agent-design.md` sections 3 and 4 classify ingestion as a deterministic node with no model
involvement. Nothing here calls a model, and nothing here reads a document for meaning.

**The loader does not look at content, and that is a security property rather than a limitation.**
It decides the format from the file extension against an allowlist and never sniffs content to
widen it, because content-based format detection is content deciding how it will be handled. It
records line counts and byte lengths and nothing about what a document says. Deciding whether a
passage is security-relevant, or whether it contains an injection attempt, belongs to steps that
know they are reading untrusted text; a loader that formed opinions would be forming them before
anything had established it was allowed to.

**Two rules are decided here rather than inherited.**

*Origin is a channel, not a content shape.* `demo/forgeflow/input/structured-system-input.yaml` is
the structured project definition, which invites `structured_input` — and it is wrong. Section 4.4
defines `SourceOrigin` as where information *originated*, and that file originated the same way the
seven Markdown files did: somebody put it in a directory. `structured_input` is reserved for
information entered through the interface, which is a different channel with a different trust
story. The decisive argument is that the loader could not implement the alternative without reading
the file to decide what it was, which is the one thing it must not do.

*A structured document must be a mapping or a sequence.* DEC-015 addresses JSON and YAML by JSON
Pointer, and defines an addressable node as each top-level mapping key and each element of a
top-level sequence. A document that parses to a bare scalar has no addressable node, so no evidence
could ever cite it — it would ingest successfully and be permanently uncitable. Refusing it at the
boundary is better than discovering it three steps later.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

import yaml

from trace_ai.domain.base import now
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.source_document import (
    IngestionStatus,
    MediaType,
    SourceDocument,
    TrustLevel,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.execution_ledger import ExecutionLedger

__all__ = [
    "MAXIMUM_DOCUMENT_BYTES",
    "SUFFIXES",
    "DocumentLoadError",
    "DocumentLoader",
    "MalformedDocumentError",
    "NoTextLayerError",
    "NotUnicodeError",
    "TooLargeError",
    "UnaddressableDocumentError",
    "UnsupportedFormatError",
]

# What this node is called in the execution ledger. The version is the node implementation's, not
# the workflow's: `data-model.md` section 27 records both so a record says which code produced it.
NODE_NAME: Final = "document_ingestion"
NODE_VERSION: Final = "0.1"

# Extension to format. Section 5.4's five inputs, spelled the ways they are spelled on disk.
# Extension only: content sniffing would let a document choose how it is parsed. `.tf` ingests as
# plain text (DEC-121): HCL is a text format and the IaC parser recognizes the suffix downstream —
# the same shape as `.tf.json` arriving through `.json`, and `.mmd` follows it (#599): Mermaid
# source is plain text and the DFD parser recognizes the suffix. `.pdf` is the one binary format
# (DEC-123): its addressable text is the deterministic extraction of the stored bytes.
SUFFIXES: Final[dict[str, MediaType]] = {
    ".md": MediaType.MARKDOWN,
    ".markdown": MediaType.MARKDOWN,
    ".txt": MediaType.PLAIN_TEXT,
    ".tf": MediaType.PLAIN_TEXT,
    ".mmd": MediaType.PLAIN_TEXT,
    ".json": MediaType.JSON,
    ".yaml": MediaType.YAML,
    ".yml": MediaType.YAML,
    ".pdf": MediaType.PDF,
}

# A guard against obvious mistakes -- a video, a database dump, a log archive -- rather than a
# security control. The real constraint on document size is the model context window and the cost
# it implies, and that limit belongs to the steps that send content to a model. The largest file in
# the demo corpus is a few tens of kilobytes.
MAXIMUM_DOCUMENT_BYTES: Final = 10 * 1024 * 1024

# Formats whose parse must yield something DEC-015 can address.
_STRUCTURED: Final = frozenset({MediaType.JSON, MediaType.YAML})


class DocumentLoadError(RuntimeError):
    """A file that cannot become a `SourceDocument`."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"cannot load {path.name!r}: {reason}")
        self.filename = path.name


class UnsupportedFormatError(DocumentLoadError):
    def __init__(self, path: Path) -> None:
        supported = ", ".join(sorted(SUFFIXES))
        formats = ", ".join(sorted(member.value for member in MediaType))
        super().__init__(
            path,
            f"its extension is not one this build ingests. Supported extensions: {supported} "
            f"({formats}). Office, repository, and web-page ingestion are deferred "
            f"(current-architecture.md section 5.4)",
        )


class TooLargeError(DocumentLoadError):
    def __init__(self, path: Path, size: int, limit: int) -> None:
        super().__init__(path, f"it is {size} bytes, over the {limit}-byte limit. Nothing was read")


class NotUnicodeError(DocumentLoadError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            "it is not valid UTF-8. Text source documents are text; a binary file reaching this "
            "point is a supplied file that is not what its extension claims",
        )


class NoTextLayerError(DocumentLoadError):
    def __init__(self, path: Path, page_count: int) -> None:
        super().__init__(
            path,
            f"none of its {page_count} page(s) carries extractable text. Extraction is text-layer "
            f"only — OCR and diagram interpretation are out of scope (DEC-123) — and an image-only "
            f"PDF ingested as an empty document would be silence presented as content (DEC-009). "
            f"Supply a text export of the document instead",
        )


class MalformedDocumentError(DocumentLoadError):
    def __init__(self, path: Path, media_type: MediaType, detail: str) -> None:
        super().__init__(path, f"it does not parse as {media_type}: {detail}")


class UnaddressableDocumentError(DocumentLoadError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            "it parses to a bare scalar. DEC-015 addresses structured documents by JSON Pointer, "
            "where an addressable node is a top-level mapping key or sequence element, so nothing "
            "in this document could ever be cited as evidence",
        )


class DocumentLoader:
    """Registers files as `SourceDocument` objects for one assessment.

    Bound to an `AssessmentHandle`, so the assessment-data boundary is the object rather than an
    argument -- the same shape both stores use.
    """

    def __init__(
        self,
        handle: AssessmentHandle,
        *,
        maximum_bytes: int = MAXIMUM_DOCUMENT_BYTES,
        ledger: ExecutionLedger | None = None,
    ) -> None:
        self.handle = handle
        self._maximum_bytes = maximum_bytes
        self._ledger = ledger

    def load_document(
        self,
        path: Path,
        *,
        origin: SourceOrigin,
        trust_level: TrustLevel,
        extra_metadata: Mapping[str, object] | None = None,
    ) -> SourceDocument:
        """Register one file. `origin` and `trust_level` are required, never inferred.

        Inferring either would mean deciding from the file what to believe about the file.

        Registration is idempotent: a file whose name and bytes are already registered returns
        the existing `SourceDocument` unchanged (#320).

        `extra_metadata` is caller-supplied provenance — repository ingestion records the
        repository, commit, and in-repo path here. It is merged over the size-derived
        metadata and is provenance about *where the file came from*, never a reading of what
        the file says: the loader's content-indifference holds because the caller computed
        these values without opening the document.
        """
        if self._ledger is None:
            return self._load(
                path, origin=origin, trust_level=trust_level, extra_metadata=extra_metadata
            )
        with self._ledger.record(NODE_NAME, node_version=NODE_VERSION) as execution:
            document = self._load(
                path, origin=origin, trust_level=trust_level, extra_metadata=extra_metadata
            )
            execution.produced(document.id)
            return document

    def _load(
        self,
        path: Path,
        *,
        origin: SourceOrigin,
        trust_level: TrustLevel,
        extra_metadata: Mapping[str, object] | None = None,
    ) -> SourceDocument:
        media_type = self._media_type(path)
        content = self._read(path, text=media_type is not MediaType.PDF)
        if media_type is MediaType.PDF:
            metadata = self._validate_pdf(path, content)
        else:
            self._parse(path, media_type, content)
            metadata = describe(content, media_type)
        if extra_metadata:
            metadata = {**metadata, **extra_metadata}

        # Registration is idempotent per (filename, content): `source add` run twice must return
        # the document it already made, not mint a second one — every count downstream (documents,
        # evidence references, the report's source table) would silently double otherwise. The
        # same filename with different bytes still falls through to the artifact store, which
        # refuses the overwrite by name.
        digest = content_hash(content)
        existing = next(
            (
                document
                for document in self.handle.objects.list(SourceDocument)
                if document.filename == path.name and document.content_hash == digest
            ),
            None,
        )
        if existing is not None:
            return existing

        already_stored = (self.handle.artifacts.area("sources") / path.name).exists()
        stored = self.handle.artifacts.store_source(path.name, content)

        repository = self.handle.objects
        try:
            with repository.transaction():
                document = SourceDocument(
                    id=repository.allocate("src"),
                    assessment_id=self.handle.assessment_id,
                    filename=path.name,
                    media_type=media_type,
                    origin=origin,
                    original_path=str(stored),
                    content_hash=self.handle.artifacts.hash_of("sources", path.name),
                    created_at=now(),
                    ingestion_status=IngestionStatus.REGISTERED,
                    trust_level=trust_level,
                    metadata=metadata,
                )
                repository.save(document)
        except BaseException:
            # Only remove what this call created. Another document may legitimately share the
            # filename with identical bytes -- the store is idempotent for that case -- and
            # deleting then would take a file a successfully registered document points at.
            if not already_stored:
                stored.unlink(missing_ok=True)
            raise

        return document

    def load_directory(
        self,
        path: Path,
        *,
        origin: SourceOrigin = SourceOrigin.UPLOADED_DOCUMENT,
        trust_level: TrustLevel = TrustLevel.UNTRUSTED,
    ) -> list[SourceDocument]:
        """Register every supported file in a directory, in filename order.

        Ordering is sorted rather than whatever the filesystem returns, so two runs over the same
        directory produce the same sequence -- and therefore the same identifiers, which
        `evaluation-plan.md` section 3's repeatability requirement depends on.

        Unsupported files are refused rather than skipped. A directory containing an Office
        document is a reviewer expecting that document to be assessed, and silently ignoring it
        would produce an assessment missing a document nobody was told about.
        """
        if not path.is_dir():
            raise DocumentLoadError(path, "it is not a directory")
        return [
            self.load_document(child, origin=origin, trust_level=trust_level)
            for child in sorted(path.iterdir())
            if child.is_file()
        ]

    def _media_type(self, path: Path) -> MediaType:
        media_type = SUFFIXES.get(path.suffix.casefold())
        if media_type is None:
            raise UnsupportedFormatError(path)
        return media_type

    def _read(self, path: Path, *, text: bool = True) -> bytes:
        """Read the file, refusing an oversized one before opening it.

        `text` is False only for the PDF branch (DEC-123): a PDF is the one format whose original
        is legitimately binary, and its readable content is established by `_validate_pdf` rather
        than by a decode.
        """
        if not path.is_file():
            raise DocumentLoadError(path, "it is not a file")
        size = path.stat().st_size
        if size > self._maximum_bytes:
            raise TooLargeError(path, size, self._maximum_bytes)

        content = path.read_bytes()
        if text:
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise NotUnicodeError(path) from error
        return content

    def _validate_pdf(self, path: Path, content: bytes) -> dict[str, object]:
        """Validate a PDF and derive its format facts. The extraction itself is not kept.

        The same posture as `_parse`: this is format validation plus the DEC-123 refusal
        decision, not extraction-for-keeps. The indexing node re-extracts when it needs the
        addressable text — the extraction is a pure function of the stored bytes, so computing
        it twice yields the same answer and stores nothing derived.
        """
        from trace_ai.services.ingestion.pdf import PdfExtractionError, extract_pdf

        try:
            extraction = extract_pdf(content)
        except PdfExtractionError as error:
            raise DocumentLoadError(path, str(error)) from error
        if not extraction.has_text:
            raise NoTextLayerError(path, extraction.page_count)

        facts: dict[str, object] = {
            "byte_length": len(content),
            "line_count": len(extraction.text.splitlines()),
            "page_count": extraction.page_count,
        }
        if extraction.pages_without_text:
            facts["pages_without_text"] = list(extraction.pages_without_text)
        return facts

    def _parse(self, path: Path, media_type: MediaType, content: bytes) -> None:
        """Confirm a structured document parses and can be addressed. Nothing is kept.

        The parse result is discarded deliberately: this is format validation, which section 5.4
        lists as a responsibility, and not extraction, which belongs to a step that knows it is
        reading untrusted text.
        """
        if media_type not in _STRUCTURED:
            return

        text = content.decode("utf-8")
        try:
            # `yaml.safe_load_all` rather than `yaml.load`: the safe loader constructs no
            # arbitrary Python objects from document content, which the default loader would —
            # code execution chosen by an untrusted input file. The `_all` form admits a
            # multi-document stream (DEC-128): a Kubernetes manifest is conventionally several
            # documents separated by `---`, that is valid YAML with the same safety properties,
            # and each document is held to the same addressability bar a single one is. JSON has
            # no equivalent hazard and needs no equivalent care.
            if media_type is MediaType.JSON:
                documents: list[object] = [json.loads(text)]
            else:
                documents = [parsed for parsed in yaml.safe_load_all(text) if parsed is not None]
        except (json.JSONDecodeError, yaml.YAMLError) as error:
            raise MalformedDocumentError(path, media_type, str(error).split("\n")[0]) from error

        if not documents or not all(isinstance(parsed, dict | list) for parsed in documents):
            raise UnaddressableDocumentError(path)


def describe(content: bytes, media_type: MediaType) -> dict[str, object]:
    """Format-derived facts about a document, and nothing about what it says.

    Everything here is countable from the bytes without reading them for meaning. `heading_count`
    is the number of ATX heading lines, which is a property of Markdown syntax rather than an
    opinion about structure -- the indexing node decides which of them segment the document
    (DEC-015), and that is a different question.
    """
    text = content.decode("utf-8")
    lines = text.splitlines()
    facts: dict[str, object] = {"byte_length": len(content), "line_count": len(lines)}
    if media_type in {MediaType.MARKDOWN, MediaType.PLAIN_TEXT}:
        facts["heading_count"] = sum(1 for line in lines if line.lstrip().startswith("#"))
    return facts
