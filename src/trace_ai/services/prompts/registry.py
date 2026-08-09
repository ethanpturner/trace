"""The prompt registry and composition loader: prompts as files, assembled in a recorded order.

`current-architecture.md` section 10 requires prompts to be version-controlled project artifacts
rather than strings embedded across application code, and `agent-design.md` section 34 names the
tree — including a `shared/` directory whose content is "composed into agents through application
code rather than copied manually into every prompt". This module is that composition.

**Composition exists to keep three blocks single-sourced.** `source-content-boundary-v1`,
`evidence-policy-v1`, and `uncertainty-policy-v1` are the rules that make an agent safe to run:
what to do with instructions found inside a source document, when a claim may cite evidence, and
where uncertainty goes. A copy of one of those in an agent prompt is the defect this module exists
to prevent, because the copy is what stops being updated.

**A missing block is loud.** A prompt that composes to something shorter than intended still runs,
still returns a plausible object, and has quietly lost the untrusted-source boundary — which is the
worst failure available here. Both a missing prompt file and a missing declared block raise, and
the error names what was missing.

**The hash covers the composed text, not the file** (DEC-019). One edit to a shared block changes
the hash of every prompt that includes it, which is exactly the change most likely to alter
behaviour without anyone noticing.

**A prompt substitutes rather than restates.** `{{ schema.context_extraction_proposal }}` in a
prompt is filled at composition from the application's own exported schema, so the two cannot drift
-- a copy pasted into the file drifts until a test notices, and this cannot drift at all. An
unresolved marker is refused for the same reason a missing shared block is: a prompt that composes
with a hole in it still runs and still answers.

**`PromptMetadata` is a dataclass rather than a domain object.** `data-model.md` section 40 defers
persisting `PromptDefinition` until the workflow operates, and `tests/unit/test_data_model_conformance.py`
holds that deferral. The fields match section 29 and a test compares them to the document; what is
deferred is the *record*, not the metadata.

The tree follows section 34's hyphenated names, and `current-architecture.md` section 10 — which
showed underscored names and a different file set — is corrected to match. Two documents describing
one directory differently is a directory nobody can create correctly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 -- a runtime default, not only an annotation
from typing import TYPE_CHECKING, Any, Final

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.hashing import content_hash

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "PROMPT_ROOT",
    "SHARED_DIRECTORY",
    "ComposedPrompt",
    "MissingSharedBlockError",
    "PromptError",
    "PromptMetadata",
    "PromptNotFoundError",
    "PromptRegistry",
    "PromptSyntaxError",
    "UnresolvedMarkerError",
    "duplicated_shared_blocks",
]

PROMPT_ROOT: Final = PROJECT_ROOT / "prompts"

# Section 34's shared tree. Blocks live here and are referenced by name from an agent prompt.
SHARED_DIRECTORY: Final = "shared"

# The separator between a prompt's metadata and its text. YAML front matter, because the metadata
# is section 29's field list and a prompt file has to be readable as a prompt.
_FENCE: Final = "---"

# What separates one composed part from the next. Fixed, so composing the same parts twice produces
# byte-identical text and the hash is a property of the content rather than of the run.
_JOIN: Final = "\n\n"

# `{{ schema.context_extraction_proposal }}` -- a value the application supplies at composition.
_MARKER = re.compile(r"\{\{\s*([a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)\s*\}\}")


class PromptError(RuntimeError):
    """Anything that prevented a prompt from being loaded as written."""


class PromptNotFoundError(PromptError):
    """No prompt file for the requested identifier and version."""

    def __init__(self, prompt_id: str, version: str, known: list[str]) -> None:
        available = ", ".join(known) if known else "none — the prompt tree is empty"
        super().__init__(f"no prompt {prompt_id!r} at version {version!r}. Available: {available}")
        self.prompt_id = prompt_id
        self.version = version


class MissingSharedBlockError(PromptError):
    """A prompt declared a shared block that is not in the tree.

    Named separately from a missing prompt because the consequence is different and worse: the
    prompt still exists, still composes, and is missing the part that made it safe to run.
    """

    def __init__(self, prompt: str, block: str) -> None:
        super().__init__(
            f"prompt {prompt!r} requires shared block {block!r}, which is not in "
            f"prompts/{SHARED_DIRECTORY}/. Refusing to compose a prompt that is missing a block "
            f"it declared: a shorter prompt still runs and still answers."
        )
        self.prompt = prompt
        self.block = block


class UnresolvedMarkerError(PromptError):
    """A composed prompt still carries a substitution marker nobody filled.

    Named separately because the consequence matches a missing shared block rather than a missing
    file: the prompt exists, composes, and is missing the part that told the agent what to return.
    """

    def __init__(self, prompt: str, markers: list[str]) -> None:
        super().__init__(
            f"prompt {prompt!r} still contains {', '.join(sorted(markers))} after composition. "
            f"Supply a substitution for each; a prompt composed with a hole in it still runs."
        )
        self.markers = markers


class PromptSyntaxError(PromptError):
    """A prompt file's front matter is absent, unparseable, or missing a required field."""


@dataclass(frozen=True, slots=True)
class PromptMetadata:
    """`data-model.md` section 29's fields, computed at load rather than persisted.

    `id` is a slug and `version` is separate, which is what DEC-034 says a prompt is named by:
    authored configuration carries a name rather than an identifier, and identity is
    `(id, version)`. The composed reference a workflow run records — `extract-context-v1` — is the
    two joined, which is how the corpus writes it in generation metadata.
    """

    id: str
    version: str
    name: str
    purpose: str
    file_path: str
    expected_input_schema: str
    expected_output_schema: str
    status: str
    content_hash: str
    model_constraints: list[str] = field(default_factory=list)

    @property
    def reference(self) -> str:
        """`extract-context-v1`: what `WorkflowRun.prompt_versions` records."""
        return f"{self.id}-{self.version}"


@dataclass(frozen=True, slots=True)
class ComposedPrompt:
    """One agent prompt, assembled and hashed."""

    metadata: PromptMetadata
    text: str
    composed_from: tuple[str, ...]
    """The parts, in the order they were joined: each shared block, then the prompt's own body.

    Recorded rather than implied, because a composition order that changes silently changes the
    prompt, and the hash alone says that something changed without saying what.
    """

    @property
    def reference(self) -> str:
        return self.metadata.reference


def _split_front_matter(source: Path) -> tuple[dict[str, Any], str]:
    """Parse `---` fenced YAML front matter and return it with the body text."""
    raw = source.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise PromptSyntaxError(
            f"{source} does not begin with {_FENCE!r} front matter carrying its "
            f"data-model.md section 29 metadata"
        )
    try:
        closing = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == _FENCE)
    except StopIteration:
        raise PromptSyntaxError(f"{source}: front matter is never closed with {_FENCE!r}") from None

    try:
        parsed = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as error:
        raise PromptSyntaxError(f"{source}: front matter is not valid YAML: {error}") from error

    if not isinstance(parsed, dict):
        raise PromptSyntaxError(f"{source}: front matter must be a mapping")

    return parsed, "\n".join(lines[closing + 1 :]).strip()


def _repo_relative(path: Path) -> str:
    """A prompt's path as section 29 wants it: relative to the repository it is version-controlled
    in. A tree outside the repository -- a test fixture -- keeps its absolute path rather than
    being forced into a relative one that would point somewhere else."""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


@dataclass(frozen=True, slots=True)
class _PromptFile:
    """One parsed file, before composition."""

    path: Path
    front_matter: dict[str, Any]
    body: str


class PromptRegistry:
    """Prompts discovered from the tree, resolved by identifier and version.

    It reads the tree and holds no prompt text of its own. A prompt that exists only in Python is
    a prompt that is not version-controlled as an artifact, which is what section 10 rules out.
    """

    _REQUIRED_FIELDS: Final = (
        "id",
        "version",
        "name",
        "purpose",
        "expected_input_schema",
        "expected_output_schema",
        "status",
    )

    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else PROMPT_ROOT
        self._prompts: dict[tuple[str, str], _PromptFile] = {}
        self._shared: dict[str, str] = {}
        self._load()

    # -- discovery -------------------------------------------------------------------------

    def _load(self) -> None:
        shared_root = self.root / SHARED_DIRECTORY
        for path in sorted(self.root.rglob("*.md")):
            if shared_root in path.parents:
                self._shared[path.stem] = path.read_text(encoding="utf-8").strip()
                continue

            front_matter, body = _split_front_matter(path)
            missing = [name for name in self._REQUIRED_FIELDS if not front_matter.get(name)]
            if missing:
                raise PromptSyntaxError(
                    f"{path}: front matter is missing {', '.join(missing)}; "
                    f"data-model.md section 29 requires them"
                )
            key = (str(front_matter["id"]), str(front_matter["version"]))
            if key in self._prompts:
                raise PromptSyntaxError(
                    f"{path} and {self._prompts[key].path} both declare {key[0]!r} {key[1]!r}"
                )
            self._prompts[key] = _PromptFile(path=path, front_matter=front_matter, body=body)

    # -- reading ---------------------------------------------------------------------------

    @property
    def shared_blocks(self) -> dict[str, str]:
        """The shared blocks in the tree, by name. A copy: the registry owns the originals."""
        return dict(self._shared)

    def references(self) -> list[str]:
        """Every prompt in the tree as `id-version`, sorted."""
        return sorted(f"{prompt_id}-{version}" for prompt_id, version in self._prompts)

    def __len__(self) -> int:
        return len(self._prompts)

    def __iter__(self) -> Iterator[str]:
        return iter(self.references())

    def markers(self, prompt_id: str, version: str) -> list[str]:
        """The substitution markers a prompt declares, sorted."""
        found = self._prompts.get((prompt_id, version))
        if found is None:
            raise PromptNotFoundError(prompt_id, version, self.references())
        return sorted(set(_MARKER.findall(found.body)))

    def compose(
        self,
        prompt_id: str,
        version: str,
        substitutions: dict[str, str] | None = None,
    ) -> ComposedPrompt:
        """Assemble one prompt from its declared shared blocks, its own text, and its substitutions.

        Shared blocks come first, in the order the prompt declares them, then the prompt's own
        text. The order is fixed and recorded: composing the same parts twice produces byte-
        identical output, which is what makes the hash a property of the content.

        Substitutions fill `{{ namespace.name }}` markers. Every marker must be supplied: a prompt
        composed with an unfilled one still runs and still answers, missing the part the marker was
        carrying.
        """
        found = self._prompts.get((prompt_id, version))
        if found is None:
            raise PromptNotFoundError(prompt_id, version, self.references())

        declared = found.front_matter.get("requires") or []
        if not isinstance(declared, list):
            raise PromptSyntaxError(f"{found.path}: `requires` must be a list of block names")

        parts: list[str] = []
        composed_from: list[str] = []
        for raw_name in declared:
            name = str(raw_name)
            block = self._shared.get(name)
            if block is None:
                raise MissingSharedBlockError(f"{prompt_id}-{version}", name)
            parts.append(block)
            composed_from.append(f"{SHARED_DIRECTORY}/{name}")

        body = found.body
        for name, value in (substitutions or {}).items():
            body = _MARKER.sub(
                lambda match, name=name, value=value: (  # type: ignore[misc]
                    value if match.group(1) == name else match.group(0)
                ),
                body,
            )

        remaining = sorted(set(_MARKER.findall(body)))
        if remaining:
            raise UnresolvedMarkerError(f"{prompt_id}-{version}", remaining)

        parts.append(body)
        composed_from.append(str(found.path.relative_to(self.root)))
        text = _JOIN.join(parts)

        constraints = found.front_matter.get("model_constraints") or []
        metadata = PromptMetadata(
            id=prompt_id,
            version=version,
            name=str(found.front_matter["name"]),
            purpose=str(found.front_matter["purpose"]),
            file_path=_repo_relative(found.path),
            expected_input_schema=str(found.front_matter["expected_input_schema"]),
            expected_output_schema=str(found.front_matter["expected_output_schema"]),
            status=str(found.front_matter["status"]),
            content_hash=content_hash(text.encode("utf-8")),
            model_constraints=[str(value) for value in constraints],
        )
        return ComposedPrompt(metadata=metadata, text=text, composed_from=tuple(composed_from))


def duplicated_shared_blocks(root: Path | None = None) -> dict[str, list[str]]:
    """Shared blocks whose text also appears in a prompt file: block name to the files copying it.

    Composition is the mechanism that keeps these single-sourced, and a copy defeats it silently —
    the copy keeps working, stops being updated, and the prompt that holds it drifts away from the
    rule everything else follows. An empty result is the healthy state.
    """
    registry = PromptRegistry(root)
    copies: dict[str, list[str]] = {}
    for name, block in registry.shared_blocks.items():
        needle = block.strip()
        if not needle:
            continue
        for path in sorted((registry.root).rglob("*.md")):
            if (registry.root / SHARED_DIRECTORY) in path.parents:
                continue
            if needle in path.read_text(encoding="utf-8"):
                copies.setdefault(name, []).append(str(path.relative_to(registry.root)))
    return copies
