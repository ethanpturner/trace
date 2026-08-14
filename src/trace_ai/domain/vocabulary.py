"""Open vocabularies: type fields the document illustrates rather than enumerates.

`data-model.md` heads several lists "Component-type examples", "Asset-type examples",
"Actor-type examples", "Boundary-type examples", and types each of the fields they describe as
`string`. DEC-036 reads that literally: those fields are **open vocabularies**, normalized to one
spelling and never rejected for being unfamiliar.

The alternative fails on the project's own benchmark. `demo/forgeflow/input/structured-system-input.yaml`
uses `web_application`, `managed_database`, `managed_cache`, `managed_storage`,
`managed_security_service`, and `internal_application`, and only one of the seven types it uses
appears in section 11's list. A closed enum would reject the scenario Trace is built to assess.

What is refused is *drift*, not vocabulary. `Web Application`, `web-application`, and
`web_application` are one type spelled three ways, and three spellings of one type are what make a
report's counts wrong and a benchmark comparison meaningless. `normalize_term` collapses them, so
the vocabulary stays open while the spelling does not.

A closed enum is still right where the document enumerates rather than illustrates: a description
reading "Service, datastore, external system, etc." is a list of examples, and one reading "One-way
or bidirectional" is a list of values. The `etc.` is the signal, and DEC-036 uses it as the rule.

**Normalization collapses spellings, never methodologies** (issue #226, survey item A8). The
surveyed corpora describe overlapping ground in different category systems, and a rough crosswalk
exists: LINDDUN's `linkability` concerns what STRIDE files under `information_disclosure` and the
CIA triad under `confidentiality`. That crosswalk is documentation for a reader, deliberately not
a normalization rule, and Threat Dragon's category lists show why: LINDDUN and PLOT4ai both carry
`unawareness` and `non_compliance` as category names, with different meanings -- LINDDUN's are
privacy categories, PLOT4ai's are AI ones. One spelling of `non_compliance` therefore names two
different categories depending on the methodology that produced it, which is exactly the case a
term-level mapping table would silently decide wrong. `normalize_term` unifies `Non-compliance`
and `non_compliance` because those are one term spelled two ways; nothing here maps a term of one
methodology onto a term of another, because sharing a spelling is not sharing a meaning.
"""

from __future__ import annotations

import re
from typing import Annotated, Final

from pydantic import BeforeValidator, Field

__all__ = ["UNKNOWN", "VocabularyTerm", "normalize_term"]

# What an unknown value says explicitly, in the fields where absence would otherwise be read as a
# negative answer. `data-model.md` section 14 requires it of `DataFlow.encryption_in_transit` and
# `DataFlow.authentication`: unknown encryption is `unknown`, never `false` and never absent.
UNKNOWN: Final = "unknown"

# The shape a normalized term ends up in: lowercase words joined by single underscores.
_TERM = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")

# Everything that separates words in the wild -- spaces, hyphens, slashes, dots, repeated
# underscores -- collapses to one underscore.
_SEPARATORS = re.compile(r"[\s\-/.]+")
_REPEATS = re.compile(r"_{2,}")


def normalize_term(value: str) -> str:
    """Reduce one vocabulary term to its canonical spelling.

    `"Web Application"`, `"web-application"`, and `"WEB_APPLICATION"` all become
    `"web_application"`. A term that is empty, or that still contains something other than
    lowercase words and underscores afterwards, is refused: normalization exists to remove
    incidental variation, not to launder a value that was never a term.
    """
    collapsed = _REPEATS.sub("_", _SEPARATORS.sub("_", value.strip())).strip("_").casefold()
    if not collapsed:
        raise ValueError("a vocabulary term must not be empty")
    if not _TERM.match(collapsed):
        raise ValueError(
            f"{value!r} does not normalize to a vocabulary term. Expected words made of letters "
            f"and digits, separated by spaces, hyphens, or underscores; got {collapsed!r}."
        )
    return collapsed


def _normalize(value: object) -> object:
    """Normalize a string, and refuse a boolean before Pydantic can describe it unhelpfully.

    `False` reaching a type field is the specific mistake DEC-009 argues about at field level: it
    reads as an answer where there is none. The message says so rather than reporting a type error.
    """
    if isinstance(value, bool):
        raise ValueError(
            f"{value!r} is not a vocabulary term. An unknown value is the explicit string "
            f"{UNKNOWN!r}; a boolean here would record an answer nobody gave."
        )
    return normalize_term(value) if isinstance(value, str) else value


VocabularyTerm = Annotated[str, BeforeValidator(_normalize), Field(min_length=1)]
"""A term from an open vocabulary: normalized on the way in, never checked against a list.

Each object module names the terms the corpus already uses in a `KNOWN_*` constant. Those are
documentation and a starting point for a reader, never a validation rule -- the same relationship
`acceptable_implementations` has to the requirements catalog, and for the same reason: a list of
examples treated as the set of allowed values is a list that decides cases it was never shown.
"""
