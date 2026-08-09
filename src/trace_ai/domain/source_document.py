"""`SourceDocument`: one original source supplied to an assessment.

`data-model.md` section 7 is authoritative for the fields. Two vocabularies live here rather than in
`domain/enums.py`, for the reason section 4's own members do not: section 7 defines `trust_level` on
the field and leaves `ingestion_status` undefined entirely, so both belong to this object the way
`ContextClaim`'s status values belong to that one.

**`trust_level` is required and carries no default**, which is a departure from the issue that asked
for it and is deliberate. Section 7 marks it `Required: Yes`, and the conformance guard reads
required as "the constructor must be given a value" -- the same collision #49 hit with
`AssessmentConfiguration`.

The issue's reasoning was that a field whose safe value must be chosen is a field that will
eventually not be. That is the right instinct and it argues for the opposite conclusion here: a
required field cannot be *not chosen*. Omitting it raises at construction, so a new call site added
later fails loudly instead of silently inheriting `untrusted`. Both designs fail safe; only this one
fails visibly, and for a security-relevant field being told about the new call site is worth more
than being quietly protected from it.

Section 7 is what makes any of this bearable: even `reviewer_supplied` documents are generally data
rather than workflow instructions, and `agent-design.md` section 25 gives agents no way to act on
any of it. `trust_level` records a provenance claim; it does not unlock a capability.

**`ingestion_status` distinguishes registration from ingestion**, which is why section 7 makes
`ingested_at` optional: a document can exist, with its bytes preserved and hashed, before anything
has read it. DEC-033 records the three values and what each requires.

A failed ingestion says *that* it failed and not *why*. The reason belongs on the `ExecutionRecord`
for the ingestion node, which section 27 gives `error_type` and a safe `error_message` — putting it
here as well would be two records of one event, and the two would disagree the first time one was
written and the other was not.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Self

from pydantic import Field, field_validator, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.hashing import ContentHash
from trace_ai.domain.identifiers import AssessmentId, SourceDocumentId

__all__ = [
    "DEFAULT_TRUST_LEVEL",
    "IngestionStatus",
    "MediaType",
    "SourceDocument",
    "TrustLevel",
]


class MediaType(StrEnum):
    """The four MVP input formats (`current-architecture.md` section 5.4).

    PDF, Microsoft Office, repository, and web-page ingestion are deferred there and are absent
    here, so a document in an unsupported format is refused at the schema rather than reaching a
    loader that has no branch for it.
    """

    MARKDOWN = "text/markdown"
    PLAIN_TEXT = "text/plain"
    JSON = "application/json"
    YAML = "application/yaml"


class TrustLevel(StrEnum):
    """How a source should be treated (section 7).

    `untrusted` covers everything supplied for review and is what a caller states unless they have
    a reason not to. The others narrow it:
    `reviewer_supplied` marks a document the reviewer wrote themselves, `system_fixture` a file
    Trace ships, and `trusted_catalog` the requirements catalog. None of them makes a document's
    content into instructions -- section 7 is explicit that even reviewer-supplied documents are
    generally data, and `agent-design.md` section 25 gives agents no way to act on any of it.
    """

    UNTRUSTED = "untrusted"
    REVIEWER_SUPPLIED = "reviewer_supplied"
    SYSTEM_FIXTURE = "system_fixture"
    TRUSTED_CATALOG = "trusted_catalog"


class IngestionStatus(StrEnum):
    """Where a document has reached in ingestion (DEC-033).

    Three values, because section 5.4's responsibilities produce two states plus a failure, and
    normalization, segmentation, and evidence indexing complete together in one node rather than
    separately.
    """

    REGISTERED = "registered"
    """Recorded and preserved. Its bytes are stored and hashed; nothing has read them."""

    INGESTED = "ingested"
    """Normalized, segmented, and indexed. `ingested_at` and `normalized_path` are both set."""

    FAILED = "failed"
    """Ingestion was attempted and did not complete. The reason is on the `ExecutionRecord`."""


# The value a caller states for a document supplied for review. Not a default -- section 7 marks
# `trust_level` required, so this is what to pass rather than what happens if you pass nothing.
DEFAULT_TRUST_LEVEL: Final = TrustLevel.UNTRUSTED

# Statuses that assert ingestion succeeded, and therefore require its outputs to exist.
_SUCCEEDED: Final = frozenset({IngestionStatus.INGESTED})


class SourceDocument(DomainModel):
    """An original source supplied to the assessment (section 7)."""

    id: SourceDocumentId
    assessment_id: AssessmentId

    filename: str = Field(min_length=1)
    """The original filename, and untrusted input.

    It reaches a path expression in the artifact store, which refuses traversal by shape and again
    by resolution. Nothing here re-implements that check: the store owns it, and a second
    implementation would be a second thing to keep correct.
    """

    media_type: MediaType
    origin: SourceOrigin
    original_path: str | None = None
    normalized_path: str | None = None
    content_hash: ContentHash
    """`sha256:<hex>` over the original file's raw bytes (DEC-019), not over normalized text.

    Normalizing before hashing would mask exactly the changes this hash exists to detect.
    """

    title: str | None = None
    created_at: datetime
    ingested_at: datetime | None = None
    ingestion_status: IngestionStatus
    trust_level: TrustLevel
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("media_type", mode="before")
    @classmethod
    def _known_media_type(cls, value: object) -> object:
        """Refuse an unsupported format by name, rather than with a bare enum error."""
        if isinstance(value, str) and value not in set(MediaType):
            supported = ", ".join(sorted(member.value for member in MediaType))
            raise ValueError(
                f"{value!r} is not one of the MVP input formats. Supported: {supported}. "
                f"PDF and Office ingestion are deferred (current-architecture.md section 5.4)."
            )
        return value

    @model_validator(mode="after")
    def _ingestion_state_is_consistent(self) -> Self:
        """A status claiming success must have the outputs that prove it (DEC-033).

        Section 7 makes `ingested_at` and `normalized_path` optional because a registered document
        has neither. That optionality is what would otherwise let a document claim it was ingested
        while carrying nothing an evidence reference could point at.
        """
        if self.ingestion_status in _SUCCEEDED:
            missing = [
                name
                for name, value in (
                    ("ingested_at", self.ingested_at),
                    ("normalized_path", self.normalized_path),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    f"ingestion_status is {self.ingestion_status} but {', '.join(missing)} "
                    f"{'is' if len(missing) == 1 else 'are'} unset. A document is only ingested "
                    f"once normalization has produced something to address."
                )
        elif self.normalized_path is not None:
            raise ValueError(
                f"ingestion_status is {self.ingestion_status} but normalized_path is set. "
                f"A document that has not been ingested has no normalized artifact."
            )

        if self.ingested_at is not None and self.ingested_at < self.created_at:
            raise ValueError(
                f"ingested_at ({self.ingested_at.isoformat()}) precedes created_at "
                f"({self.created_at.isoformat()}); a document cannot be ingested before it exists"
            )
        return self
