"""`EvidenceReference`: the joint the traceability argument turns on.

`data-model.md` section 2.2 says a source document alone is not sufficiently precise, and ten other
objects carry `evidence_ids`. Every conclusion Trace defends is defended through this object, so
what it can and cannot express is a design statement rather than a schema detail.

**It can only cite text that exists.** There is no field, flag, or convention by which an evidence
reference says a document is silent about something. `quoted_text` is required and may not be
empty, which is the DEC-009 separation expressed in the schema: "the document does not say" is a
`DocumentationGap` (section 23) or a `Question` (section 22), and both are separate objects. An
evidence reference with empty `quoted_text` would be a citation of nothing, and a citation of
nothing is exactly how missing documentation becomes an asserted weakness.

**Every location addresses the original document, never the normalized artifact** (DEC-015).
`start_line`, `end_line`, and `quoted_text` are all taken from the file as supplied. Normalization
is line-count preserving by construction, so the two addressings are the same address and the
ambiguity cannot be reintroduced by a later reader choosing differently.

**Evidence is not edited.** Section 8 states that evidence text is not modified after creation and
that corrections create a new reference. `DomainModel` is frozen, which enforces it, and DEC-019
hashes `content_hash` over `quoted_text`, which makes a modification detectable if one were made
some other way. Both facts exist because a quotation that can change is not a citation.

The location fields vary by format, and DEC-015 fixes which is used where:

| Format | Address | `section_title` |
|---|---|---|
| Markdown, plain text | `chunk_index`, segmented at the shallowest heading level appearing at least twice | the chunk's own heading, flattened |
| JSON, YAML | a JSON Pointer in `metadata["json_pointer"]` | the readable dotted path |
| PDF | `page_number`, one addressable unit per textual page (DEC-123) | `Page N` |

Line numbers are populated for structured formats too, so a reviewer can find the passage, but a
line range is not an address there: two sequence elements can be textually identical.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Final, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.hashing import ContentHash
from trace_ai.domain.identifiers import AssessmentId, EvidenceReferenceId, SourceDocumentId

__all__ = ["JSON_POINTER_KEY", "LOCATION_FIELDS", "EvidenceReference"]

# The reserved `metadata` key holding a JSON Pointer for a structured source (DEC-015, RFC 6901).
# It lives in metadata rather than in a field of its own because section 8 is authoritative and
# already types metadata as "additional location details" -- adding a field would be a schema
# change, and DEC-015 explicitly declines to make one.
JSON_POINTER_KEY: Final = "json_pointer"

# What counts as addressing a passage. Section 8 requires at least one usable location field, and
# these are the ones a format can supply.
LOCATION_FIELDS: Final = (
    "section_title",
    "chunk_index",
    "start_line",
    "end_line",
    "page_number",
    f"metadata[{JSON_POINTER_KEY!r}]",
)


class EvidenceReference(DomainModel):
    """An addressable passage of a source document (section 8)."""

    id: EvidenceReferenceId
    source_document_id: SourceDocumentId
    assessment_id: AssessmentId

    section_title: str | None = None
    """The chunk's own heading, flattened rather than nested; the dotted path for JSON and YAML."""

    chunk_index: int | None = Field(default=None, ge=0)
    """Position among the document's chunks, contiguous from zero in document order (DEC-015)."""

    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    page_number: int | None = Field(default=None, ge=1)

    quoted_text: Annotated[str, StringConstraints(strip_whitespace=False)]
    """The verbatim excerpt from the original: what a reviewer sees and what the report quotes.

    **Whitespace stripping is disabled for this field alone.** `DomainModel` sets
    `str_strip_whitespace=True`, which is right for text extracted from a document and wrong here:
    DEC-015 makes this the verbatim excerpt, DEC-019 hashes it, and the indexer records the line
    range it came from. Stripping would leave the stored text disagreeing with both its own hash
    and its own line numbers, and the disagreement would surface as an unverifiable citation rather
    than as a bug in this class.

    Emptiness is still refused, by `_must_quote_something` rather than by `min_length`: with
    stripping off, a whitespace-only quotation has a length and would otherwise pass.
    """

    normalized_text: str | None = None
    """The derived form, for machine comparison. `quoted_text` is what is shown and hashed."""

    content_hash: ContentHash
    source_origin: SourceOrigin
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    """Additional location details, including `json_pointer` for a structured source (DEC-015)."""

    @field_validator("quoted_text")
    @classmethod
    def _must_quote_something(cls, value: str) -> str:
        """Evidence cites text that exists.

        A citation of blank space is the DEC-009 failure in miniature: it looks like evidence,
        carries a location, and supports nothing. "The document does not say" is a
        `DocumentationGap` or a `Question`.
        """
        if not value.strip():
            raise ValueError("quoted_text must not be empty or whitespace only")
        return value

    @model_validator(mode="after")
    def _must_address_a_passage(self) -> Self:
        """Section 8: at least one usable source-location field.

        A reference with none names a document and not a place in it, which
        `data-model.md` section 2.2 says explicitly is not sufficiently precise. It would still
        carry a quotation, so nothing downstream would notice it was unaddressable.
        """
        located = any(
            (
                self.section_title,
                self.chunk_index is not None,
                self.start_line is not None,
                self.end_line is not None,
                self.page_number is not None,
                self.metadata.get(JSON_POINTER_KEY),
            )
        )
        if not located:
            raise ValueError(
                f"an evidence reference must address a passage, not just a document. "
                f"Supply at least one of: {', '.join(LOCATION_FIELDS)}."
            )
        return self

    @model_validator(mode="after")
    def _line_range_is_ordered(self) -> Self:
        both_present = self.start_line is not None and self.end_line is not None
        if both_present and self.end_line < self.start_line:  # type: ignore[operator]
            raise ValueError(f"end_line ({self.end_line}) precedes start_line ({self.start_line})")
        return self

    @property
    def json_pointer(self) -> str | None:
        """The RFC 6901 pointer for a structured source, if this reference has one."""
        pointer = self.metadata.get(JSON_POINTER_KEY)
        return pointer if isinstance(pointer, str) else None
