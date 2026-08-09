"""Tests for the document loader, run against the real ForgeFlow corpus.

`demo/forgeflow/input/` is what the loader has to handle: seven Markdown files and one YAML file,
including `sample-repository-notes.md`, which carries a deliberate prompt-injection payload. That
file is loaded here like any other, and nothing in the loader looks at it — which is the point.
Injection detection belongs to a step that knows it is reading untrusted text; the loader's job is
to preserve the bytes and say where they came from.

Most of this file is refusals. A loader is mostly a boundary, and the interesting behaviour is what
it declines: a format with no branch to handle it, a YAML tag that would construct a Python object,
a document that would be permanently uncitable, a file too large to have been meant. Issue #53.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.source_document import (
    IngestionStatus,
    MediaType,
    SourceDocument,
    TrustLevel,
)
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.ingestion.loader import (
    SUFFIXES,
    DocumentLoader,
    DocumentLoadError,
    MalformedDocumentError,
    NotUnicodeError,
    TooLargeError,
    UnaddressableDocumentError,
    UnsupportedFormatError,
)

FORGEFLOW_INPUT = PROJECT_ROOT / "demo" / "forgeflow" / "input"


@pytest.fixture
def loader(tmp_path: Path) -> Iterator[DocumentLoader]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        yield DocumentLoader(service.handle(created.id))


def load(loader: DocumentLoader, path: Path) -> SourceDocument:
    return loader.load_document(
        path, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
    )


# ------------------------------------------------------------------------------------------
# The real corpus
# ------------------------------------------------------------------------------------------


def test_every_forgeflow_input_loads(loader: DocumentLoader) -> None:
    documents = loader.load_directory(FORGEFLOW_INPUT)

    assert len(documents) == 8
    assert len({document.id for document in documents}) == 8
    assert all(document.assessment_id == "asm-001" for document in documents)


def test_the_media_types_are_what_the_extensions_say(loader: DocumentLoader) -> None:
    documents = {d.filename: d.media_type for d in loader.load_directory(FORGEFLOW_INPUT)}

    assert documents["structured-system-input.yaml"] == MediaType.YAML
    markdown = [name for name, media in documents.items() if media == MediaType.MARKDOWN]
    assert len(markdown) == 7


def test_the_injection_fixture_loads_like_any_other_document(loader: DocumentLoader) -> None:
    """The loader does not look at content, so a planted payload is just bytes to it.

    Detecting it is `SourceObservation` work (DEC-021) done by a step that knows it is reading
    untrusted text. A loader that formed the opinion would be forming it before anything had
    established it was allowed to.
    """
    document = load(loader, FORGEFLOW_INPUT / "sample-repository-notes.md")

    assert document.ingestion_status is IngestionStatus.REGISTERED
    assert document.trust_level is TrustLevel.UNTRUSTED
    stored = loader.handle.artifacts.read("sources", "sample-repository-notes.md")
    assert b"AI ANALYSIS OVERRIDE" in stored, "the payload is preserved, not sanitized"


def test_stored_content_is_byte_identical(loader: DocumentLoader) -> None:
    """Section 5.4 preserves the original, and DEC-019 hashes it."""
    source = FORGEFLOW_INPUT / "architecture-overview.md"
    document = load(loader, source)

    stored = loader.handle.artifacts.read("sources", source.name)
    assert stored == source.read_bytes()
    assert document.content_hash == content_hash(source.read_bytes())


def test_a_registered_document_has_no_ingestion_outputs(loader: DocumentLoader) -> None:
    """The indexing node fills these; the loader must not claim work it did not do."""
    document = load(loader, FORGEFLOW_INPUT / "security-overview.md")
    assert document.normalized_path is None
    assert document.ingested_at is None
    assert document.original_path is not None


def test_identifiers_are_allocated_in_directory_order(loader: DocumentLoader) -> None:
    """Sorted rather than filesystem order, so two runs produce the same sequence.

    `evaluation-plan.md` section 3 requires repeatability, and identifiers that depend on
    directory iteration order would make two runs over one corpus incomparable.
    """
    documents = loader.load_directory(FORGEFLOW_INPUT)
    names = [document.filename for document in documents]

    assert names == sorted(names)
    assert [d.id for d in documents] == [f"src-{n:03d}" for n in range(1, 9)]


def test_load_directory_is_deterministic(tmp_path: Path) -> None:
    """Two assessments over the same directory produce the same filenames in the same order."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        orders = []
        for name in ("First", "Second"):
            created = service.create(
                name, default_configuration("primary-development", "stride-scenario-based")
            )
            documents = DocumentLoader(service.handle(created.id)).load_directory(FORGEFLOW_INPUT)
            orders.append([document.filename for document in documents])

    assert orders[0] == orders[1]


def test_the_hash_is_reproducible_and_change_sensitive(
    loader: DocumentLoader, tmp_path: Path
) -> None:
    first = tmp_path / "a.md"
    first.write_bytes(b"# Title\n\nWebhook requests are validated.\n")
    second = tmp_path / "b.md"
    second.write_bytes(b"# Title\n\nWebhook requests are validated!\n")

    assert load(loader, first).content_hash == content_hash(first.read_bytes())
    assert load(loader, first).content_hash != load(loader, second).content_hash


# ------------------------------------------------------------------------------------------
# Origin is a channel, not a content shape
# ------------------------------------------------------------------------------------------


def test_the_structured_input_file_is_an_uploaded_document(loader: DocumentLoader) -> None:
    """Pinned, because the name invites the other answer.

    Section 4.4 defines `SourceOrigin` as where information originated, and this file originated
    the same way the Markdown files did: somebody put it in a directory. `structured_input` is
    information entered through the interface. The loader could not implement the alternative
    without reading the file to decide what it was.
    """
    documents = {d.filename: d for d in loader.load_directory(FORGEFLOW_INPUT)}
    structured = documents["structured-system-input.yaml"]

    assert structured.origin is SourceOrigin.UPLOADED_DOCUMENT
    # The alternative exists and was not chosen. mypy rejects comparing against it directly, now
    # that the return type is known, which is itself a small proof the choice is pinned.
    assert SourceOrigin.STRUCTURED_INPUT.value == "structured_input"


def test_origin_and_trust_level_are_required_and_never_inferred() -> None:
    """Inferring either would mean deciding from the file what to believe about the file."""
    import inspect

    parameters = inspect.signature(DocumentLoader.load_document).parameters
    for name in ("origin", "trust_level"):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is inspect.Parameter.empty


# ------------------------------------------------------------------------------------------
# Refusals
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["report.pdf", "notes.docx", "README", "archive.tar.gz"])
def test_an_unsupported_format_is_refused_by_name(
    loader: DocumentLoader, tmp_path: Path, name: str
) -> None:
    """Refusing is the specified behaviour under section 5.4, not a limitation."""
    path = tmp_path / name
    path.write_bytes(b"content")

    with pytest.raises(UnsupportedFormatError) as caught:
        load(loader, path)

    message = str(caught.value)
    for supported in ("text/markdown", "text/plain", "application/json", "application/yaml"):
        assert supported in message
    assert "section 5.4" in message


def test_the_extension_allowlist_is_the_documented_set() -> None:
    assert set(SUFFIXES) == {".md", ".markdown", ".txt", ".json", ".yaml", ".yml"}


def test_format_is_decided_by_extension_and_not_by_content(
    loader: DocumentLoader, tmp_path: Path
) -> None:
    """Content sniffing would let a document choose how it is parsed.

    A file of JSON named `.md` loads as Markdown, which is correct: the reviewer named it.
    """
    path = tmp_path / "looks-like-json.md"
    path.write_bytes(b'{"components": []}')

    assert load(loader, path).media_type is MediaType.MARKDOWN


def test_a_yaml_object_tag_is_refused_rather_than_constructed(
    loader: DocumentLoader, tmp_path: Path
) -> None:
    """`yaml.safe_load` rather than `yaml.load`, asserted directly.

    The default loader constructs arbitrary Python objects from document content, which is code
    execution chosen by an untrusted input file. This is the test that proves which one is used.
    """
    path = tmp_path / "payload.yaml"
    path.write_bytes(b"!!python/object/apply:os.system ['echo pwned']\n")

    with pytest.raises(MalformedDocumentError):
        load(loader, path)


def test_a_yaml_alias_bomb_is_not_expanded(loader: DocumentLoader, tmp_path: Path) -> None:
    """A small file that expands to a large structure. `safe_load` still parses it.

    Recorded rather than mitigated: the size limit is measured in bytes on disk, so a billion-laughs
    document passes it. Nothing in the corpus asks for an expansion limit, and PyYAML offers none;
    the practical guard is that ingestion runs locally on documents a reviewer chose.
    """
    path = tmp_path / "aliases.yaml"
    path.write_bytes(b"a: &a [1, 2]\nb: [*a, *a]\n")

    assert load(loader, path).media_type is MediaType.YAML


def test_malformed_json_is_refused(loader: DocumentLoader, tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_bytes(b'{"components": [}')

    with pytest.raises(MalformedDocumentError, match="does not parse"):
        load(loader, path)


@pytest.mark.parametrize("content", [b"42", b'"a string"', b"true", b"null"])
def test_a_structured_document_that_is_a_bare_scalar_is_refused(
    loader: DocumentLoader, tmp_path: Path, content: bytes
) -> None:
    """The stated rule, not an accident.

    DEC-015 makes an addressable node a top-level mapping key or sequence element. A scalar has
    neither, so no evidence could ever cite the document -- it would ingest successfully and be
    permanently uncitable.
    """
    path = tmp_path / "scalar.json"
    path.write_bytes(content)

    with pytest.raises(UnaddressableDocumentError, match="bare scalar"):
        load(loader, path)


@pytest.mark.parametrize("content", [b'{"a": 1}', b"[1, 2]", b"{}", b"[]"])
def test_a_mapping_or_sequence_is_accepted(
    loader: DocumentLoader, tmp_path: Path, content: bytes
) -> None:
    path = tmp_path / "structured.json"
    path.write_bytes(content)
    assert load(loader, path).media_type is MediaType.JSON


def test_a_markdown_file_is_not_subject_to_the_addressability_rule(
    loader: DocumentLoader, tmp_path: Path
) -> None:
    """Prose is addressed by chunk and line, so a document with no headings is still citable."""
    path = tmp_path / "prose.md"
    path.write_bytes(b"Just a sentence with no heading.\n")
    assert load(loader, path).metadata["heading_count"] == 0


def test_an_oversized_file_is_refused_without_being_read(tmp_path: Path) -> None:
    """The size is taken from the directory entry, so nothing is loaded into memory."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Small", default_configuration("primary-development", "stride-scenario-based")
        )
        loader = DocumentLoader(service.handle(created.id), maximum_bytes=64)

        path = tmp_path / "big.md"
        path.write_bytes(b"x" * 128)

        with pytest.raises(TooLargeError, match="Nothing was read"):
            load(loader, path)

        assert not (tmp_path / "assessments" / created.id / "sources" / "big.md").exists()


def test_invalid_utf8_produces_a_named_error(loader: DocumentLoader, tmp_path: Path) -> None:
    """Not a `UnicodeDecodeError` traceback: a binary file named `.md` is a supplied-input problem."""
    path = tmp_path / "binary.md"
    path.write_bytes(b"\xff\xfe\x00\x01 not text")

    with pytest.raises(NotUnicodeError, match="not valid UTF-8"):
        load(loader, path)


def test_a_directory_is_not_a_document(loader: DocumentLoader, tmp_path: Path) -> None:
    nested = tmp_path / "nested.md"
    nested.mkdir()
    with pytest.raises(DocumentLoadError, match="not a file"):
        load(loader, nested)


def test_load_directory_refuses_an_unsupported_file_rather_than_skipping_it(
    loader: DocumentLoader, tmp_path: Path
) -> None:
    """A directory containing a PDF is a reviewer expecting the PDF to be assessed.

    Skipping it silently would produce an assessment missing a document nobody was told about,
    which is the same class of failure as a finding nobody can trace.
    """
    directory = tmp_path / "inputs"
    directory.mkdir()
    (directory / "overview.md").write_bytes(b"# Overview\n")
    (directory / "diagram.pdf").write_bytes(b"%PDF-1.4\n")

    with pytest.raises(UnsupportedFormatError):
        loader.load_directory(directory)


def test_a_failed_load_leaves_no_document_row(loader: DocumentLoader, tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_bytes(b"{")

    with pytest.raises(MalformedDocumentError):
        load(loader, path)

    assert loader.handle.objects.list(SourceDocument) == []


# ------------------------------------------------------------------------------------------
# Metadata is countable, not interpretive
# ------------------------------------------------------------------------------------------


def test_metadata_holds_format_derived_facts_only(loader: DocumentLoader) -> None:
    document = load(loader, FORGEFLOW_INPUT / "architecture-overview.md")
    metadata = document.metadata

    assert set(metadata) == {"byte_length", "line_count", "heading_count"}
    assert metadata["byte_length"] == (FORGEFLOW_INPUT / "architecture-overview.md").stat().st_size
    assert metadata["line_count"] > 0


def test_metadata_says_nothing_about_meaning(loader: DocumentLoader) -> None:
    """Every key is countable from the bytes without reading them for sense."""
    document = load(loader, FORGEFLOW_INPUT / "sample-repository-notes.md")
    interpretive = [
        key
        for key in document.metadata
        if any(word in key for word in ("security", "risk", "injection", "summary", "topic"))
    ]
    assert not interpretive


def test_a_structured_document_records_no_heading_count(loader: DocumentLoader) -> None:
    document = load(loader, FORGEFLOW_INPUT / "structured-system-input.yaml")
    assert "heading_count" not in document.metadata


def test_the_loader_needs_no_api_key(
    loader: DocumentLoader, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ingestion is a deterministic node: `agent-design.md` sections 3 and 4."""
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert load(loader, FORGEFLOW_INPUT / "product-overview.md") is not None
