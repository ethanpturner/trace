"""Assembling what the extractor sees, and fencing what it must not obey.

`agent-design.md` section 23 says the Context Extraction Agent receives source chunks, document
metadata, and existing structured input — and nothing else — and gives the reasons directly: fewer
tokens, less cross-contamination, less irrelevant reasoning, less prompt-injection exposure, less
cost, less latency. Section 22 adds that evidence reaches an agent through an application-controlled
interface rather than through the filesystem or the database. This module is that interface's output.

**The fence is the security boundary, and a document that can close it escapes it.** Every excerpt
is wrapped in a marker carrying its evidence identifier, and any delimiter appearing *inside* an
excerpt is neutralised before it is written. `demo/forgeflow/input/sample-repository-notes.md` is a
live test of the whole arrangement: it contains a block that addresses its reader directly, and the
assertion that matters is not that the block is absent — it is present, because it is evidence —
but that it appears only inside the fence and never in the trusted half.

**Precedence is stated, not inferred.** `structured-system-input.yaml` says structured metadata is
authoritative only for the fields it represents, that the Markdown documents remain primary for
architectural reasoning, and that conflicts are surfaced rather than resolved. That is a rule about
how to read the material, so it belongs in the trusted region as a sentence rather than being left
to the model to work out from the shape of what it was given.

**Exceeding the budget names what was dropped.** Silent truncation is the worst available failure
here: it removes the passage a claim rests on, and the claim then appears to lack evidence that was
in fact supplied. Excluded identifiers are returned, and the caller decides what to do.

**Assembly is deterministic.** The same assessment and the same evidence produce byte-identical
output, which is what makes the replay cache usable — a key computed over a prompt that varies by
dictionary ordering matches nothing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.source_document import SourceDocument

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.evidence.index import EvidenceIndex

__all__ = [
    "FENCE_CLOSE",
    "FENCE_OPEN",
    "PRECEDENCE_RULE",
    "ExtractorInput",
    "assemble_extractor_input",
    "neutralize_fence",
]

# The markers the prompt names in its trusted half. Changing either means changing the prompt.
FENCE_OPEN: Final = "<source-content"
FENCE_CLOSE: Final = "</source-content>"

# Anything that could close or open a fence, however spelled. Matched loosely on purpose: the goal
# is to leave nothing a parser or a reader could take for a delimiter, not to recognise the exact
# token the application writes.
_FENCE_LIKE: Final = re.compile(r"<\s*/?\s*source-content[^>]*>", re.IGNORECASE)

# What a neutralised delimiter becomes. The text stays readable and stays quotable as evidence; it
# simply is not a delimiter any more. An invisible character would have been shorter and would have
# made the transformation impossible to see in a diff or a log.
_NEUTRALIZED: Final = "&lt;source-content-removed&gt;"

# The rule `structured-system-input.yaml` states about itself, carried into the trusted region.
PRECEDENCE_RULE: Final = (
    "Structured input is authoritative only for the fields it represents. The prose documents "
    "remain the primary source for architectural reasoning. Where the two conflict, record the "
    "conflict as an observation and raise a question; do not silently prefer either."
)


def neutralize_fence(text: str) -> str:
    """Remove anything in `text` that could act as a fence delimiter.

    Applied to every excerpt before it is written. A source document that can close its own fence
    can put text into the trusted region, which is the one failure the fence exists to prevent.
    """
    return _FENCE_LIKE.sub(_NEUTRALIZED, text)


@dataclass(frozen=True, slots=True)
class ExtractorInput:
    """The assembled package: a trusted region, a fenced untrusted region, and what was dropped."""

    trusted: str
    untrusted: str
    evidence_ids: tuple[str, ...]
    excluded_evidence_ids: tuple[str, ...] = ()
    """Evidence the budget excluded. Named rather than silently dropped: a claim missing the passage
    it rested on looks like a claim that never had one."""

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """Whether every supplied reference reached the package."""
        return not self.excluded_evidence_ids

    def substitutions(self) -> dict[str, str]:
        """What the prompt registry substitutes into `extract-context-v1`."""
        return {"input.source_content": self.untrusted}


def _fenced(excerpt: dict[str, Any]) -> str:
    """One evidence reference as a fenced block carrying its identifier and its location."""
    location = excerpt.get("location") or {}
    parts = [f'{FENCE_OPEN} evidence_id="{excerpt["evidence_id"]}"']
    filename = excerpt.get("source_filename")
    if filename:
        parts.append(f'document="{filename}"')
    if location.get("json_pointer"):
        parts.append(f'json_pointer="{location["json_pointer"]}"')
    elif location.get("start_line") is not None:
        end = location.get("end_line", location["start_line"])
        parts.append(f'lines="{location["start_line"]}-{end}"')
    if location.get("section_title"):
        parts.append(f'section="{location["section_title"]}"')

    opening = " ".join(parts) + ">"
    return f"{opening}\n{neutralize_fence(excerpt['quoted_text'])}\n{FENCE_CLOSE}"


def _trusted_region(
    *,
    assessment_name: str,
    documents: Sequence[SourceDocument],
    excerpts: Sequence[dict[str, Any]],
    structured_input: dict[str, Any] | None,
) -> str:
    """The half of the package the agent may take as instruction.

    It carries metadata, the precedence rule, and a manifest of which evidence identifiers are
    present — never the excerpt text. The manifest is here so the agent can see the shape of what
    it was given without the text appearing twice, and so a citation of an absent identifier is
    visibly a citation of something absent.
    """
    manifest = [
        {
            "evidence_id": excerpt["evidence_id"],
            "document": excerpt.get("source_filename"),
            "location": {
                key: value
                for key, value in (excerpt.get("location") or {}).items()
                if value is not None
            },
        }
        for excerpt in excerpts
    ]

    lines = [
        "## Assessment",
        "",
        f"name: {assessment_name}",
        "",
        "## Source documents",
        "",
        json.dumps(
            [
                {
                    "source_document_id": document.id,
                    "filename": document.filename,
                    "media_type": document.media_type.value,
                    "trust_level": document.trust_level.value,
                }
                for document in documents
            ],
            indent=2,
            sort_keys=True,
        ),
        "",
        "## Source precedence",
        "",
        PRECEDENCE_RULE,
        "",
        "## Evidence available",
        "",
        json.dumps(manifest, indent=2, sort_keys=True),
    ]

    if structured_input is not None:
        lines += [
            "",
            "## Structured input",
            "",
            json.dumps(structured_input, indent=2, sort_keys=True),
        ]

    return "\n".join(lines)


def assemble_extractor_input(
    handle: AssessmentHandle,
    *,
    index: EvidenceIndex,
    evidence_ids: Sequence[str],
    profile: ModelProfile,
    assessment_name: str,
    structured_input: dict[str, Any] | None = None,
) -> ExtractorInput:
    """Build the extractor's input from evidence the application already holds.

    `evidence_ids` are supplied by the caller rather than discovered here, so what the agent sees is
    a decision made in one place. Nothing in the package is a path, a credential, or a
    configuration object: the agent receives data about documents, never a way to reach one.
    """
    excerpts = index.render_for_prompt(list(evidence_ids))
    documents = sorted(handle.objects.list(SourceDocument), key=lambda document: document.id)

    blocks: list[str] = []
    included: list[str] = []
    excluded: list[str] = []
    used = 0
    budget = profile.max_input_characters

    for excerpt in excerpts:
        block = _fenced(excerpt)
        if used + len(block) > budget:
            excluded.append(excerpt["evidence_id"])
            continue
        blocks.append(block)
        included.append(excerpt["evidence_id"])
        used += len(block)

    present = [excerpt for excerpt in excerpts if excerpt["evidence_id"] in set(included)]
    trusted = _trusted_region(
        assessment_name=assessment_name,
        documents=documents,
        excerpts=present,
        structured_input=structured_input,
    )

    return ExtractorInput(
        trusted=trusted,
        untrusted="\n\n".join(blocks),
        evidence_ids=tuple(included),
        excluded_evidence_ids=tuple(excluded),
        metadata={
            "documents": len(documents),
            "evidence_included": len(included),
            "evidence_excluded": len(excluded),
            "characters": used,
            "budget_characters": budget,
        },
    )
