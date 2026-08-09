"""Tests for normalization, segmentation, and evidence indexing, against the real corpus.

This is the node that makes `current-architecture.md` section 5.4's claim checkable: that every
extracted claim can link back to a source document, a section, its text, a content hash, and a
timestamp. So the tests verify locations **by re-reading the file**, not by trusting the indexer's
own bookkeeping — an indexer that recorded consistent nonsense would pass any test written against
its own output.

The corpus is what makes the segmentation rule worth testing rather than asserting. Two documents
use `#` once as a title and `##` for every section; five use `#` for every section. DEC-015's rule —
the shallowest heading level occurring *more than once* — is the only one that handles both, and
both failure modes are covered here by name. Issue #55.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from pathlib import Path

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import JSON_POINTER_KEY, EvidenceReference
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.source_document import (
    IngestionStatus,
    MediaType,
    SourceDocument,
    TrustLevel,
)
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.evidence.indexing import IndexingError, index_document
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.ingestion.normalize import line_count, normalize
from trace_ai.services.ingestion.segment import Segment, segment, segmenting_level

FORGEFLOW_INPUT = PROJECT_ROOT / "demo" / "forgeflow" / "input"


@pytest.fixture
def loader(tmp_path: Path) -> Iterator[DocumentLoader]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        yield DocumentLoader(service.handle(created.id))


def register(loader: DocumentLoader, name: str) -> SourceDocument:
    return loader.load_document(
        FORGEFLOW_INPUT / name,
        origin=SourceOrigin.UPLOADED_DOCUMENT,
        trust_level=TrustLevel.UNTRUSTED,
    )


def index(loader: DocumentLoader, name: str) -> list[EvidenceReference]:
    return index_document(loader.handle, register(loader, name))


# ------------------------------------------------------------------------------------------
# Normalization is line-count preserving
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(FORGEFLOW_INPUT.iterdir()), ids=lambda p: p.name)
def test_normalization_preserves_the_line_count_of_every_corpus_document(path: Path) -> None:
    """DEC-015's load-bearing property, checked against every real document.

    If line counts can change, addressing the original and addressing the normalized artifact stop
    being the same address, and every evidence location in the document silently moves.
    """
    original = path.read_text(encoding="utf-8")
    assert line_count(normalize(original)) == line_count(original)


@pytest.mark.parametrize(
    "text",
    [
        "a\r\nb\r\n",
        "a\n\n\n\nb\n",
        "trailing   \nspaces  \n",
        "---\nfront: matter\n---\n\nbody\n",
        "\n\n\n",
        "no trailing newline",
    ],
)
def test_normalization_preserves_line_counts_on_the_forbidden_transformations(text: str) -> None:
    """Each case is one of the things DEC-015 forbids, and each is a plausible tidy-up.

    Collapsing blank lines, unwrapping paragraphs, and stripping front matter all look like
    improvements. They are forbidden because each one moves every citation below it.
    """
    assert line_count(normalize(text)) == line_count(text)


def test_normalization_is_idempotent() -> None:
    """A re-ingested document produces byte-identical output, so hashes compare across runs."""
    for path in sorted(FORGEFLOW_INPUT.iterdir()):
        once = normalize(path.read_text(encoding="utf-8"))
        assert normalize(once) == once, path.name


def test_normalization_does_what_it_is_permitted_to_do() -> None:
    assert normalize("a\r\nb") == "a\nb"
    assert normalize("trailing   \n") == "trailing\n"
    decomposed = "café"
    assert normalize(decomposed) == unicodedata.normalize("NFC", decomposed)


def test_normalization_does_not_remove_blank_lines() -> None:
    assert normalize("a\n\n\nb\n") == "a\n\n\nb\n"


# ------------------------------------------------------------------------------------------
# Segmentation, against both corpus shapes
# ------------------------------------------------------------------------------------------


def test_a_title_used_once_does_not_segment_the_document() -> None:
    """`architecture-overview.md`: 734 lines, one `#`, thirty-five `##`.

    The intuitive rule -- shallowest level *present* -- gives one chunk here, which is the exact
    failure segmentation exists to prevent.
    """
    lines = (FORGEFLOW_INPUT / "architecture-overview.md").read_text(encoding="utf-8").splitlines()

    assert len(lines) == 734
    assert segmenting_level(lines) == 2

    units = segment("\n".join(lines), MediaType.MARKDOWN)
    assert len(units) > 30, "the document collapsed to a handful of chunks"


def test_first_level_headings_still_segment() -> None:
    """`sample-repository-notes.md` uses `#` for every section; a fixed `##` rule gives one chunk."""
    text = (FORGEFLOW_INPUT / "sample-repository-notes.md").read_text(encoding="utf-8")

    assert segmenting_level(text.splitlines()) == 1
    units = segment(text, MediaType.MARKDOWN)
    assert len(units) > 5
    assert all(unit.section_title for unit in units)


def test_section_titles_match_the_documents_real_headings() -> None:
    """Taken from the file rather than from the segmenter's output."""
    text = (FORGEFLOW_INPUT / "architecture-overview.md").read_text(encoding="utf-8")
    headings = [
        line.removeprefix("## ").strip() for line in text.splitlines() if line.startswith("## ")
    ]
    titles = [
        unit.section_title for unit in segment(text, MediaType.MARKDOWN) if unit.section_title
    ]

    assert titles == headings


def test_deeper_headings_sit_inside_their_chunk() -> None:
    """DEC-015: headings deeper than the segmenting level do not create sub-chunks."""
    text = (FORGEFLOW_INPUT / "architecture-overview.md").read_text(encoding="utf-8")
    units = segment(text, MediaType.MARKDOWN)

    third_level = [line for line in text.splitlines() if line.startswith("### ")]
    assert third_level, "the fixture no longer has third-level headings"
    assert all(
        unit.section_title != heading.removeprefix("### ")
        for unit in units
        for heading in third_level
    )


def test_content_before_the_first_heading_is_still_addressable() -> None:
    """Dropping it would make a document's title and introduction uncitable."""
    text = (FORGEFLOW_INPUT / "product-overview.md").read_text(encoding="utf-8")
    units = segment(text, MediaType.MARKDOWN)

    assert units[0].section_title is None
    assert units[0].start_line == 1
    assert units[0].text.startswith("#")


def test_a_document_with_no_repeated_heading_level_is_one_chunk() -> None:
    text = "# Only Title\n\nSome prose with no sections.\n"
    units = segment(text, MediaType.MARKDOWN)

    assert len(units) == 1
    assert units[0].section_title is None


def test_a_document_with_no_headings_at_all_produces_a_reference() -> None:
    units = segment("Just prose.\nMore prose.\n", MediaType.PLAIN_TEXT)
    assert len(units) == 1
    assert units[0].text.strip()


def test_headings_inside_a_fenced_block_do_not_segment() -> None:
    """The corpus has no fences, which is why this is easy to get wrong before one appears."""
    text = "# A\n\ntext\n\n```\n# not a heading\n# nor this\n```\n\n# B\n\nmore\n"
    units = segment(text, MediaType.MARKDOWN)

    assert [unit.section_title for unit in units] == ["A", "B"]


def test_whitespace_only_segments_are_dropped() -> None:
    """`EvidenceReference` refuses empty `quoted_text`, so an empty chunk could not become one."""
    units = segment("# A\n\n\n\n# B\n\ncontent\n", MediaType.MARKDOWN)
    assert all(unit.text.strip() for unit in units)


# ------------------------------------------------------------------------------------------
# Structural addressing
# ------------------------------------------------------------------------------------------


def test_yaml_is_addressed_by_json_pointer() -> None:
    text = (FORGEFLOW_INPUT / "structured-system-input.yaml").read_text(encoding="utf-8")
    units = {unit.json_pointer: unit for unit in segment(text, MediaType.YAML)}

    assert "/components" in units, "the nested components list is not addressable"
    assert "/security_controls" in units, "the security_controls mapping is not addressable"
    assert units["/components"].section_title == "components"
    assert all(unit.start_line >= 1 for unit in units.values())


def test_a_yaml_location_resolves_to_the_right_lines() -> None:
    """Checked against the file, not against the segmenter's own record."""
    path = FORGEFLOW_INPUT / "structured-system-input.yaml"
    lines = path.read_text(encoding="utf-8").splitlines()
    unit = next(
        u
        for u in segment(path.read_text(encoding="utf-8"), MediaType.YAML)
        if u.json_pointer == "/components"
    )

    assert lines[unit.start_line - 1].startswith("components")
    assert unit.text == "\n".join(lines[unit.start_line - 1 : unit.end_line])


def test_a_top_level_sequence_is_addressed_by_index() -> None:
    units = segment("- first\n- second\n", MediaType.YAML)
    assert [unit.json_pointer for unit in units] == ["/0", "/1"]
    assert [unit.section_title for unit in units] == ["[0]", "[1]"]


def test_a_pointer_token_is_rfc_6901_escaped() -> None:
    """`~` and `/` in a key would otherwise produce a pointer addressing something else."""
    units = segment('{"a/b": 1, "c~d": 2}\n', MediaType.JSON)
    assert [unit.json_pointer for unit in units] == ["/a~1b", "/c~0d"]


def test_json_is_addressed_the_same_way(tmp_path: Path) -> None:
    units = segment('{"system": {"name": "x"}, "components": []}\n', MediaType.JSON)
    assert {unit.json_pointer for unit in units} == {"/system", "/components"}


# ------------------------------------------------------------------------------------------
# Indexing the real corpus
# ------------------------------------------------------------------------------------------


def test_every_corpus_document_indexes(loader: DocumentLoader) -> None:
    documents = loader.load_directory(FORGEFLOW_INPUT)
    total = 0
    for document in documents:
        references = index_document(loader.handle, document)
        assert references, document.filename
        total += len(references)

    assert total > 100, f"only {total} references across eight documents"


def test_every_reference_belongs_to_its_document_and_assessment(loader: DocumentLoader) -> None:
    """The section 12 boundary, asserted directly rather than implied by the arguments."""
    document = register(loader, "security-overview.md")
    references = index_document(loader.handle, document)

    assert all(reference.assessment_id == document.assessment_id for reference in references)
    assert all(reference.source_document_id == document.id for reference in references)


def test_the_indexer_takes_no_assessment_or_origin_argument() -> None:
    """Derived from the parent document, so the boundary does not depend on argument discipline."""
    import inspect

    parameters = set(inspect.signature(index_document).parameters)
    assert "assessment_id" not in parameters
    assert "source_origin" not in parameters


def test_quoted_text_appears_verbatim_at_the_recorded_location(loader: DocumentLoader) -> None:
    """Verified by re-reading the file.

    An indexer that recorded internally consistent nonsense would pass any test written against
    its own output, which is why this one goes back to the source.
    """
    for name in ("architecture-overview.md", "sample-repository-notes.md", "product-overview.md"):
        document = register(loader, name)
        lines = (FORGEFLOW_INPUT / name).read_text(encoding="utf-8").splitlines()

        for reference in index_document(loader.handle, document):
            assert reference.start_line is not None
            assert reference.end_line is not None
            expected = "\n".join(lines[reference.start_line - 1 : reference.end_line])
            assert reference.quoted_text == expected, f"{name} {reference.id}"


def test_chunk_index_is_contiguous_from_zero_in_document_order(loader: DocumentLoader) -> None:
    references = index(loader, "operations-guide.md")

    assert [reference.chunk_index for reference in references] == list(range(len(references)))
    starts = [reference.start_line for reference in references]
    assert all(start is not None for start in starts)
    assert starts == sorted(starts, key=lambda value: value or 0)


def test_each_reference_hashes_its_own_quoted_text(loader: DocumentLoader) -> None:
    """Separate from the document hash, so a citation is verifiable without the whole file."""
    for reference in index(loader, "github-integration.md"):
        assert reference.content_hash == content_hash(reference.quoted_text.encode("utf-8"))


def test_indexing_is_deterministic_apart_from_identifiers(tmp_path: Path) -> None:
    """Two assessments over the same file produce identical hashes, locations, and titles."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        runs = []
        for name in ("First", "Second"):
            created = service.create(
                name, default_configuration("primary-development", "stride-scenario-based")
            )
            handle = service.handle(created.id)
            document = DocumentLoader(handle).load_document(
                FORGEFLOW_INPUT / "ai-analysis.md",
                origin=SourceOrigin.UPLOADED_DOCUMENT,
                trust_level=TrustLevel.UNTRUSTED,
            )
            runs.append(
                [
                    (r.chunk_index, r.section_title, r.start_line, r.end_line, r.content_hash)
                    for r in index_document(handle, document)
                ]
            )

    assert runs[0] == runs[1]


def test_the_injection_block_is_indexed_like_any_other_content(loader: DocumentLoader) -> None:
    """Preserved in `quoted_text`, not skipped and not flagged."""
    references = index(loader, "sample-repository-notes.md")
    carrying = [r for r in references if "AI ANALYSIS OVERRIDE" in r.quoted_text]

    assert carrying, "the injection block is not in any evidence reference"
    for reference in carrying:
        assert reference.chunk_index is not None
        assert reference.content_hash == content_hash(reference.quoted_text.encode("utf-8"))
        assert JSON_POINTER_KEY not in reference.metadata


# ------------------------------------------------------------------------------------------
# The document is completed, once
# ------------------------------------------------------------------------------------------


def test_indexing_completes_the_document(loader: DocumentLoader) -> None:
    document = register(loader, "product-overview.md")
    assert document.ingestion_status is IngestionStatus.REGISTERED

    index_document(loader.handle, document)
    stored = loader.handle.objects.get(SourceDocument, document.id)

    assert stored.ingestion_status is IngestionStatus.INGESTED
    assert stored.ingested_at is not None
    assert stored.normalized_path is not None
    assert stored.id == document.id, "the document keeps its identity (DEC-023)"


def test_the_normalized_artifact_is_written(loader: DocumentLoader) -> None:
    document = register(loader, "product-overview.md")
    index_document(loader.handle, document)

    normalized = loader.handle.artifacts.read("normalized", document.filename).decode("utf-8")
    original = (FORGEFLOW_INPUT / document.filename).read_text(encoding="utf-8")

    assert normalized == normalize(original)
    assert line_count(normalized) == line_count(original)


def test_indexing_twice_is_refused(loader: DocumentLoader) -> None:
    """A second pass would mint a second set of references for the same passages."""
    document = register(loader, "product-overview.md")
    index_document(loader.handle, document)
    completed = loader.handle.objects.get(SourceDocument, document.id)

    with pytest.raises(IndexingError, match="not registered"):
        index_document(loader.handle, completed)


def test_a_document_from_another_assessment_is_refused(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        configuration = default_configuration("primary-development", "stride-scenario-based")
        first = service.handle(service.create("First", configuration).id)
        second = service.handle(service.create("Second", configuration).id)

        document = DocumentLoader(first).load_document(
            FORGEFLOW_INPUT / "product-overview.md",
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )

        with pytest.raises(IndexingError, match="belongs to"):
            index_document(second, document)


def test_the_indexer_needs_no_api_key(
    loader: DocumentLoader, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deterministic node: `agent-design.md` sections 3 and 4."""
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert index(loader, "product-overview.md")


def test_references_are_persisted_and_readable(loader: DocumentLoader) -> None:
    document = register(loader, "ai-analysis.md")
    produced = index_document(loader.handle, document)

    stored = loader.handle.objects.list(EvidenceReference)
    assert len(stored) == len(produced)
    assert {reference.id for reference in stored} == {reference.id for reference in produced}


def test_a_segment_carries_its_own_location(loader: DocumentLoader) -> None:
    """`Segment` is the internal shape; asserted so a refactor keeps the fields evidence needs."""
    unit = Segment(text="x", start_line=1, end_line=1)
    assert unit.section_title is None
    assert unit.json_pointer is None
