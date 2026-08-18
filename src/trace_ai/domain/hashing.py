"""Content hashing: one utility, four stated inputs.

DEC-019 fixes `content_hash` as SHA-256 rendered as `sha256:` followed by 64 lowercase hex
characters, and fixes **what** is hashed per object type. The per-type inputs are not four
conventions but one principle applied four times: *hash the thing whose change you want to
detect.*

| Object | Hashed input |
|---|---|
| `SourceDocument` | the original file's raw bytes, before any normalization |
| `EvidenceReference` | the UTF-8 bytes of `quoted_text` |
| `PromptDefinition` | two hashes: `content_hash` over the composed, substituted prompt text; `template_hash` over the pre-substitution composition, shared blocks merged (DEC-094) |
| `RequirementsCatalog` | a canonical re-serialization of the parsed catalog |

The first two have helpers here. The last two do not: they are computed at prompt load and
catalog load, by loaders that do not exist yet, and a helper that cannot be called from anywhere
is a guess at an interface rather than an implementation of one. Both will call `content_hash`
when they arrive -- DEC-019's requirement is that one utility computes and verifies every hash,
and that is this module, not that every call site be written in advance.

Everything hashes **bytes**. Encoding and line-ending differences are exactly what a source
document's hash exists to catch, and a helper taking `str` would decide the encoding on the
caller's behalf and absorb the difference silently.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Annotated

from pydantic import AfterValidator

__all__ = [
    "ALGORITHM",
    "ContentHash",
    "content_hash",
    "hash_quoted_text",
    "hash_source_bytes",
    "is_content_hash",
    "verify_hash",
]

ALGORITHM = "sha256"

# `sha256:` and 64 lowercase hex. Uppercase is rejected rather than normalized: two spellings of
# one hash compare unequal as strings, and a value that is sometimes normalized and sometimes not
# is worse than one that is always rejected.
_CONTENT_HASH = re.compile(rf"^{ALGORITHM}:[0-9a-f]{{64}}$")


def content_hash(data: bytes) -> str:
    """The `sha256:<hex>` hash of `data`. Every hash in the system comes from here."""
    return f"{ALGORITHM}:{hashlib.sha256(data).hexdigest()}"


def hash_source_bytes(raw: bytes) -> str:
    """Hash a source document: the original file's bytes, before any normalization (DEC-019).

    Normalizing first would mask the changes this hash exists to detect. A re-encoded or
    re-line-ended file is a changed file, and the reviewer needs to know the material under
    review is not the material that was assessed.
    """
    return content_hash(raw)


def hash_quoted_text(quoted_text: str) -> str:
    """Hash an evidence reference: the UTF-8 bytes of its `quoted_text` (DEC-019).

    DEC-015 makes `quoted_text` the verbatim excerpt from the original and forbids modifying it
    after creation, which is what makes it a meaningful thing to hash.

    This detects a changed passage, not a moved one: an edit above the excerpt shifts its line
    numbers while the hash still matches. That gap is DEC-019's, recorded there as a tradeoff.
    """
    return content_hash(quoted_text.encode("utf-8"))


def is_content_hash(value: str) -> bool:
    """Whether `value` is well-formed. Says nothing about what it hashes."""
    return isinstance(value, str) and _CONTENT_HASH.match(value) is not None


def verify_hash(expected: str, data: bytes) -> bool:
    """Whether `data` still hashes to `expected`.

    Compared with `compare_digest`. Nothing here is a secret and no attacker is timing this, but
    the habit is worth more than the microseconds: a hash comparison written with `==` is the one
    that gets copied into a place where it does matter.
    """
    if not is_content_hash(expected):
        raise ValueError(
            f"{expected!r} is not a content hash. Expected '{ALGORITHM}:' followed by 64 "
            f"lowercase hexadecimal characters."
        )
    return hmac.compare_digest(expected, content_hash(data))


def _check_content_hash(value: str) -> str:
    if not is_content_hash(value):
        raise ValueError(
            f"{value!r} is not a content hash. Expected '{ALGORITHM}:' followed by 64 "
            f"lowercase hexadecimal characters (DEC-019)."
        )
    return value


# The annotated type for every `content_hash` field, so a truncated or uppercase digest fails at
# the schema rather than at the comparison that silently never matches.
ContentHash = Annotated[str, AfterValidator(_check_content_hash)]
