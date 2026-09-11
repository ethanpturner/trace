"""A deterministic text embedding so the index runs with no model in the loop.

Hashed bag of words over a fixed number of dimensions, L2-normalised. Exact and repeatable, which
is what a review target and its tests need; not a claim about retrieval quality.
"""

from __future__ import annotations

import hashlib
import math
import re

DIMENSIONS = 256
_TOKEN = re.compile(r"[a-z0-9]+")


def embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for token in _TOKEN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
