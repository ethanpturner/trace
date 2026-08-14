"""The error taxonomy: a closed vocabulary, and the line between a failure and a conclusion.

`agent-design.md` section 26 draws the distinction this module exists for. An output that failed to
parse and an analysis that genuinely cannot be concluded look similar at the call site and are
opposites: the first is worth another attempt, and the second is an answer. Retrying the second
spends money to no purpose and — the part that matters — invites an agent to fabricate something on
the third attempt, because the only way to stop being retried is to produce an answer.

So the vocabulary is closed. A free-text error class appearing in a log is a class nobody decided
on, and the first thing anyone does with one is decide whether to retry it.

**Six classes come from section 26's default retry policy**, three retryable and three not. A
seventh, `unexpected_application_failure`, exists because `current-architecture.md` section 11 names
a failure class the retry policy does not: a bug is neither a provider condition nor an analysis
condition, and folding it into either would make it retryable or make it read as a judgment about
the material. It is not retryable, and it is the one class that says the fault is ours.

**"Awaiting a reviewer decision" is not a failure** (DEC-017). Section 11 used to describe a
human-review timeout; a paused run holds nothing in memory, waiting costs nothing, and there is no
timeout. `reviewer_input_required` is in the taxonomy as the *reason a run stopped*, not as an
error — which is why it is non-retryable rather than absent.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from trace_ai.infrastructure.model.seam import FailureReason

__all__ = [
    "NON_RETRYABLE",
    "RETRYABLE",
    "SECTION_11_FAILURE_CLASSES",
    "ErrorClass",
    "WorkflowError",
    "classify_model_failure",
]


class ErrorClass(StrEnum):
    """Why a step did not produce what it was asked for.

    Section 26's six, plus one for a fault in this application. Closed: adding a member is a
    deliberate change to what the workflow can say about itself.
    """

    SCHEMA_VALIDATION_FAILURE = "schema_validation_failure"
    """The output did not fit the schema — invalid JSON, missing fields, a bad identifier."""

    TRANSIENT_PROVIDER_FAILURE = "transient_provider_failure"
    """The provider was unavailable, timed out, or rate-limited."""

    MISSING_REQUIRED_RELATIONSHIP = "missing_required_relationship"
    """A proposed object referenced something that does not exist — a flow naming an absent
    component. Retryable because it is a shape error the agent can be told about."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    """The material cannot support a conclusion. **Not a technical failure** (section 11): the
    response is a question, an assumption, or a documentation gap (DEC-009).

    No code path constructs this class today, and that is a property of the routing rather than
    an oversight (DEC-086): the pipeline expresses the condition as the Question or gap it
    resolves to, so there is nothing left to raise. The member stays because the taxonomy is
    section 26's vocabulary — the non-retryable rule is stated where retry decisions read it,
    and a future producer inherits the classification instead of inventing one."""

    UNRESOLVED_CONTRADICTION = "unresolved_contradiction"
    """Two passages disagree and the answer would change the assessment. Retrying cannot resolve
    it, and `SourceObservation` plus a `Question` is what does — which is also why nothing
    raises it today (DEC-086, same reasoning as `INSUFFICIENT_EVIDENCE`)."""

    REVIEWER_INPUT_REQUIRED = "reviewer_input_required"
    """A human decision is needed. Not an error — the reason a run stopped (DEC-017)."""

    UNEXPECTED_APPLICATION_FAILURE = "unexpected_application_failure"
    """A fault in this application. Section 11's response is to preserve the last valid checkpoint,
    record the error, and allow a controlled restart."""


# Section 26's `retry_on`. Each is a condition of the attempt rather than of the material, which is
# the property that makes another attempt meaningful.
RETRYABLE: Final[frozenset[ErrorClass]] = frozenset(
    {
        ErrorClass.SCHEMA_VALIDATION_FAILURE,
        ErrorClass.TRANSIENT_PROVIDER_FAILURE,
        ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
    }
)

# Everything else. Section 26's `do_not_retry_on` plus the application fault: three are statements
# about the material and one is a statement about our code, and no number of attempts changes any
# of them.
NON_RETRYABLE: Final[frozenset[ErrorClass]] = frozenset(ErrorClass) - RETRYABLE

# `current-architecture.md` section 11's failure classes, mapped onto the taxonomy. Total by
# construction and asserted by a test: a section 11 class with no member is a documented condition
# the code cannot name.
SECTION_11_FAILURE_CLASSES: Final[dict[str, ErrorClass]] = {
    "validation failure": ErrorClass.SCHEMA_VALIDATION_FAILURE,
    "model-service failure": ErrorClass.TRANSIENT_PROVIDER_FAILURE,
    "insufficient evidence": ErrorClass.INSUFFICIENT_EVIDENCE,
    "awaiting a reviewer decision": ErrorClass.REVIEWER_INPUT_REQUIRED,
    "unexpected application failure": ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
}

# How the model seam's per-attempt reasons land in the taxonomy. The seam classifies what happened
# to one call; this classifies what it means for the workflow, and the two are not the same
# vocabulary — a refusal is a provider condition to the adapter and an application fault here,
# because nothing the workflow can retry will change it.
_MODEL_FAILURES: Final[dict[FailureReason, ErrorClass]] = {
    FailureReason.SCHEMA_VALIDATION_FAILURE: ErrorClass.SCHEMA_VALIDATION_FAILURE,
    FailureReason.OUTPUT_TRUNCATED: ErrorClass.SCHEMA_VALIDATION_FAILURE,
    FailureReason.TRANSIENT_PROVIDER_FAILURE: ErrorClass.TRANSIENT_PROVIDER_FAILURE,
    FailureReason.TIMEOUT: ErrorClass.TRANSIENT_PROVIDER_FAILURE,
    FailureReason.CONNECTION_FAILURE: ErrorClass.TRANSIENT_PROVIDER_FAILURE,
    FailureReason.REFUSED: ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
    FailureReason.INVALID_REQUEST: ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
    FailureReason.AUTHENTICATION_FAILURE: ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
}


def classify_model_failure(reason: FailureReason) -> ErrorClass:
    """The workflow's name for one model attempt's failure.

    A `FailureReason` the seam adds but this map has not caught up with falls back to
    `UNEXPECTED_APPLICATION_FAILURE` rather than raising `KeyError` inside a node's attempt loop --
    non-retryable, so an unclassified provider condition cannot invite a fabricated third attempt.
    `test_errors.py` asserts the map is total, so the fallback is a runtime safety net, not a
    licence to leave a reason unmapped.
    """
    return _MODEL_FAILURES.get(reason, ErrorClass.UNEXPECTED_APPLICATION_FAILURE)


class WorkflowError(RuntimeError):
    """A classified failure, carrying no content.

    `data-model.md` section 27 requires `ExecutionRecord.error_message` to be safe, and this is
    where that is enforced rather than hoped for: the raw output of a failed attempt goes to a
    debug artifact and the message names the artifact. A message built from what the model said
    would put prompt text, a source excerpt, or a credential into a row nobody expected to hold
    one.
    """

    def __init__(
        self,
        error_class: ErrorClass,
        message: str,
        *,
        artifact_path: str | None = None,
        attempts: int = 1,
    ) -> None:
        detail = f" The failed output is preserved at {artifact_path}." if artifact_path else ""
        super().__init__(f"{error_class.value}: {message}{detail}")
        self.error_class = error_class
        self.artifact_path = artifact_path
        self.attempts = attempts

    @property
    def retryable(self) -> bool:
        return self.error_class in RETRYABLE
