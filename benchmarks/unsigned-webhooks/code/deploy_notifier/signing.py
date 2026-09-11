"""The CI platform's delivery signing scheme.

The platform signs each delivery by computing HMAC-SHA256 over the raw request body with the shared
secret and sending the hex digest in the `X-CI-Signature-256` header as `sha256=<digest>`.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-CI-Signature-256"
_PREFIX = "sha256="


def compute_signature(secret: str, body: bytes) -> str:
    """The header value the platform sends for `body` under `secret`."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{_PREFIX}{digest}"


def verify_signature(secret: str, body: bytes, header_value: str | None) -> bool:
    """Whether `header_value` is the platform's signature over `body` under `secret`.

    Constant-time on the digest comparison; a missing or malformed header is a failed
    verification, not an error.
    """
    if header_value is None or not header_value.startswith(_PREFIX):
        return False
    expected = compute_signature(secret, body)
    return hmac.compare_digest(expected, header_value)
