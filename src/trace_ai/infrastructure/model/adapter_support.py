"""Provider-neutral helpers every adapter owes, in one place (DEC-014, WS11).

`factory.py` claims adding a provider means "adding an adapter and a branch, and nothing else
changes." That was not quite true: a second adapter had to reimplement obligations that lived only
as private functions inside the Anthropic adapter — and two of them are security-sensitive, because
`data-model.md` section 27 requires a failure's `error_message` to be safe to store and read. These
are those obligations, factored out so a second adapter inherits the safe rendering rather than
writing its own and getting it subtly wrong. They hold zero provider types; the exception-to-reason
ladder that does stays in the adapter, and calls `classify_http_error` for the status-code half.

`tests/unit/test_adapter_conformance.py` runs the contract these support against every
`StructuredModel` implementation.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from trace_ai.infrastructure.model.seam import FailureReason

if TYPE_CHECKING:
    import pydantic

__all__ = ["classify_http_error", "error_locations", "json_candidate"]

_LOC_PART = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def error_locations(invalid: pydantic.ValidationError, *, limit: int = 20) -> str:
    """The failing field paths with their error types, and nothing the model wrote.

    `loc` is normally a path through the application's own schema and `type` is pydantic's
    classification — safe in a message (section 27). The exception is `extra_forbidden`, whose
    final path element is the *invented* key, which is model-authored text: any part that does not
    look like a schema identifier is masked rather than quoted. Capped so a wholesale-invalid
    response cannot flood the record. This is a security obligation: an adapter that let raw model
    output into `error_message` would republish it into the ledger, so every adapter uses this.
    """

    def part_of(part: object) -> str:
        if isinstance(part, int):
            return str(part)
        return part if isinstance(part, str) and _LOC_PART.match(part) else "<unnamable-key>"

    errors = invalid.errors()
    listed = "; ".join(
        ".".join(part_of(part) for part in error["loc"]) + f" ({error['type']})"
        for error in errors[:limit]
    )
    more = f" and {len(errors) - limit} more" if len(errors) > limit else ""
    return f"{listed}{more}"


def json_candidate(raw: str) -> str:
    """The text with a Markdown code fence stripped, when the whole response is one fence.

    With a server-side output grammar omitted, nothing stops a model from wrapping its JSON in
    ```json fences. The unwrap is deliberately narrow — a single fence enclosing the entire trimmed
    response — so it cannot mistake fenced content inside a legitimate answer for packaging. The raw
    output preserved on a failure stays the original text.
    """
    text = raw.strip()
    if not text.startswith("```"):
        return raw
    first_break = text.find("\n")
    if first_break == -1 or not text.endswith("```"):
        return raw
    return text[first_break + 1 : -3].strip()


def classify_http_error(status_code: int) -> FailureReason:
    """The reason a provider's HTTP status maps to, provider-neutrally (section 26).

    The 5xx band is the provider's fault and worth another attempt; a 4xx is the request's and is
    not. An adapter's own exception ladder handles the provider-specific exception types and defers
    the status-code decision here, so a second adapter inherits the retryability boundary rather
    than reinventing where it sits.
    """
    if status_code >= 500:
        return FailureReason.TRANSIENT_PROVIDER_FAILURE
    return FailureReason.INVALID_REQUEST
