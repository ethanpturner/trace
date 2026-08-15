"""Tests holding the package skeleton and the one dependency direction that matters.

`docs/architecture/current-architecture.md` section 15 proposes a repository organization and
says the important property is that domain models, workflow logic, prompts, infrastructure, and
user-interface code stay reasonably separated. The tree itself is cheap to create and cheap to
erode: nothing stops a later module putting a database import into a domain object, and once one
does, every object after it inherits the coupling.

So the layering is asserted rather than described. `trace_ai.domain` holds the objects DEC-006
makes authoritative, and it must remain importable without dragging SQLite, the filesystem, or a
model provider along with it -- the objects are the thing every other layer depends on, and a
domain package that depends back on its callers cannot be reasoned about in isolation.

The check reads the source rather than the imported module, so an import buried inside a function
body counts the same as one at the top of the file. Issue #41.
"""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest

from trace_ai.config import PROJECT_ROOT

PACKAGE_ROOT = PROJECT_ROOT / "src" / "trace_ai"
DOMAIN_ROOT = PACKAGE_ROOT / "domain"

# The skeleton section 15 calls for, adapted to the real package name. `api/`, `application/`,
# `reporting/` and `evaluation/` are deliberately absent: section 15 proposes them,
# nothing in this milestone puts a file in them, and an empty package reads as a commitment that
# has not been made.
PACKAGES = (
    "trace_ai.domain",
    # What an agent returns (agent-design.md section 22): proposed objects carrying local keys and
    # nothing the application owns. Inside `domain/` because a proposal is validated data, and it
    # imports no service and no store.
    "trace_ai.domain.proposals",
    # Orchestration (DEC-016): phases, the transition table, execution limits, and the node
    # protocol. There is no framework; this is what the decision names instead.
    "trace_ai.workflow",
    "trace_ai.services",
    "trace_ai.services.ingestion",
    "trace_ai.services.context",
    "trace_ai.services.evidence",
    # Prompts are version-controlled files (current-architecture.md section 10); this package
    # reads and composes them, and holds no prompt text of its own.
    "trace_ai.services.prompts",
    # The requirements catalog is version-controlled YAML outside the package (DEC-010); this
    # package is the only thing that reads it, and computes its DEC-019 content hash.
    "trace_ai.services.requirements",
    # What the Threat Analysis agent sees (agent-design.md section 23): an approved architecture
    # and the evidence behind it, fenced with the same helper the extractor's package uses.
    "trace_ai.services.threats",
    # What the Requirement and Control Mapping agent sees. Its own package rather than a module
    # under `requirements/`, because that package is the catalog's reader (DEC-010) and this one
    # assembles a payload from the catalog, the approved context, and the store. DEC-024 removed
    # the deterministic requirement matcher the backlog put here, so there is one mapping step and
    # one package for it.
    "trace_ai.services.mapping",
    # What the Critical Review agent sees: one threat's lineage and nothing wider (DEC-049).
    # Its own package because the bound is the whole design -- an agent shown everything
    # re-derives everything, which is section 15's second-full-assessment prohibition.
    "trace_ai.services.critique",
    # The finding-side query surface: section 32's lineage walk, which the checkpoint 2 review
    # package and the "why was this generated" view consume (issue #100). A service because it
    # spans most of the object model; nothing in it is persisted (DEC-053).
    "trace_ai.services.findings",
    # The report input assembly (DEC-035, issue #104): approved state gathered once, so the
    # Report Generation agent and the deterministic renderer cannot disagree about what was
    # approved. Findings come solely from the DEC-055 accessor.
    "trace_ai.services.report",
    # The finding-quality metrics (DEC-056, issue #110): deterministic computation over
    # persisted objects, with benchmark matching against the authored truth sets. No model on
    # the default path.
    "trace_ai.services.evaluation",
    # The interop exports (DEC-072, issue #347): post-approval serializers of approved objects,
    # TM-BOM first. Not report formats — no prose, no model call, `outputs/` artifacts only.
    "trace_ai.services.export",
    "trace_ai.infrastructure",
    "trace_ai.infrastructure.filesystem",
    "trace_ai.infrastructure.database",
    # The model seam (DEC-014). `tests/unit/test_model_boundary.py` holds the rule this package
    # exists to enforce: the adapter inside it is the only module that may import a provider SDK.
    "trace_ai.infrastructure.model",
    # The read-only demonstration interface (DEC-032, issue #276): the Stage 5 view that renders
    # persisted objects to HTML over localhost and drives nothing. Its own top-level package
    # rather than a service, because it is a presentation surface over the services, not one of
    # them, and stdlib `http.server` is the whole stack (no framework, DEC-016).
    "trace_ai.interface",
)

# What a domain module may not reach for. Named as module prefixes so that
# `trace_ai.infrastructure.database.session` is caught by `trace_ai.infrastructure`.
FORBIDDEN_IN_DOMAIN = ("trace_ai.services", "trace_ai.infrastructure")

# Third-party packages a domain object must not reach for.
#
# Provider and orchestration SDKs. `anthropic` is the only one declared today; `openai`,
# `langchain`, `langgraph`, `instructor`, and `langsmith` were declared and removed (DEC-014,
# DEC-016, DEC-090). All are listed anyway, because the guard is about where an import may appear
# rather than about which packages happen to be installed this week -- a dependency that comes back
# should not find `domain/` already open to it.
#
# The direction is the same one the layering test asserts. Domain objects are validated data:
# they are constructed from a model response by a service and persisted by infrastructure, and a
# domain module that talks to a provider directly has made the objects depend on the thing that
# proposes them. `pydantic` is not on this list -- the objects are Pydantic models.
FORBIDDEN_SDKS_IN_DOMAIN = (
    "anthropic",
    "openai",
    "langchain",
    "langgraph",
    "langsmith",
    "instructor",
    # Not an SDK, and forbidden for a different reason. Domain objects are validated data; parsing
    # a serialization format is ingestion, which is a service. A domain module importing `yaml`
    # would be a domain object that knows how documents are stored on disk.
    "yaml",
)


def package_of(source: Path) -> str:
    """The dotted package a source file lives in, e.g. `trace_ai.domain`."""
    return ".".join(source.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts[:-1])


def imported_modules(source: Path, package: str) -> set[str]:
    """Every absolute module name a source file imports, relative imports resolved.

    A relative import is resolved against the file's own package, so `from ..services import x`
    inside `trace_ai/domain/` yields `trace_ai.services.x` and is caught like any other.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                parts = package.split(".")
                anchor = parts[: len(parts) - (node.level - 1)]
                base = ".".join([*anchor, node.module] if node.module else anchor)
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("module", PACKAGES)
def test_package_is_importable(module: str) -> None:
    assert import_module(module) is not None


@pytest.mark.parametrize("module", PACKAGES)
def test_package_states_what_belongs_in_it(module: str) -> None:
    """An `__init__.py` without a docstring leaves the next author guessing."""
    doc = import_module(module).__doc__
    assert doc is not None, f"{module} has no docstring saying what belongs in it"
    assert doc.strip(), f"{module} has an empty docstring"


def domain_imports_under(prefixes: tuple[str, ...]) -> dict[str, set[str]]:
    """Every domain module that imports one of `prefixes`, and what it reached for.

    Matching is by module prefix, so `trace_ai.infrastructure.database.session` is caught by
    `trace_ai.infrastructure` and `anthropic.types` by `anthropic`.
    """
    offenders: dict[str, set[str]] = {}
    for source in sorted(DOMAIN_ROOT.rglob("*.py")):
        reached = {
            name
            for name in imported_modules(source, package_of(source))
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
        }
        if reached:
            offenders[str(source.relative_to(PROJECT_ROOT))] = reached
    return offenders


def test_domain_does_not_import_services_or_infrastructure() -> None:
    """The direction section 15 names, and the one that erodes quietly.

    Domain objects are validated data. They are constructed by services and persisted by
    infrastructure, and they must not know either exists.
    """
    offenders = domain_imports_under(FORBIDDEN_IN_DOMAIN)
    assert not offenders, (
        f"domain modules must not import services or infrastructure: {offenders}. "
        f"Move the dependency to the caller; domain objects are constructed by services, "
        f"not the other way round."
    )


def test_domain_does_not_import_a_provider_or_orchestration_sdk() -> None:
    """The same direction, one layer further out.

    An agent proposes an object and the application validates it. A domain module that imports a
    provider SDK has inverted that: the schema would depend on the thing it exists to check.
    """
    offenders = domain_imports_under(FORBIDDEN_SDKS_IN_DOMAIN)
    assert not offenders, (
        f"domain modules must not import a provider or orchestration SDK: {offenders}. "
        f"Model access belongs behind the adapter seam DEC-014 describes, and the objects on "
        f"either side of it are plain validated data."
    )


def test_the_sdk_guard_covers_the_declared_dependencies() -> None:
    """A declared runtime dependency that the guard does not name is a gap in it.

    `pydantic`, `pydantic-settings`, and `python-dotenv` are excluded deliberately: the domain
    objects are Pydantic models, and configuration is not a domain concern but is not a provider
    either. Anything else declared should be on the list or explicitly waived here.
    """
    # A distribution name is not an import name, and the guard matches imports. Mapping the two
    # that differ is more honest than putting `pyyaml` in a list the AST walk compares against
    # `import yaml` and never matches.
    import_names = {"pyyaml": "yaml", "python-dotenv": "dotenv", "pydantic-settings": "pydantic"}

    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = pyproject.split("dependencies = [", 1)[1].split("]", 1)[0]
    declared = {
        line.strip().strip('",').split(">=")[0].split("[")[0].strip('"')
        for line in block.splitlines()
        if line.strip().startswith('"')
    }
    declared = {import_names.get(name, name) for name in declared}
    waived = {"pydantic", "dotenv"}
    uncovered = declared - waived - set(FORBIDDEN_SDKS_IN_DOMAIN)
    assert not uncovered, (
        f"{sorted(uncovered)} is a declared dependency that domain/ is not guarded against. "
        f"Add it to FORBIDDEN_SDKS_IN_DOMAIN, or to the waived set with a reason."
    )


def test_the_layering_check_can_fail(tmp_path: Path) -> None:
    """The guard above is worthless if the parser silently finds nothing.

    Both forms are checked because they resolve differently: an absolute import carries its
    full name, a relative one has to be resolved against the file's package first.
    """
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from trace_ai.infrastructure.database import session\n"
        "\n"
        "def load():\n"
        "    from ..services.ingestion import loader\n"
        "    return session, loader\n",
        encoding="utf-8",
    )
    reached = imported_modules(probe, package="trace_ai.domain")

    assert "trace_ai.infrastructure.database" in reached
    assert "trace_ai.services.ingestion" in reached


def test_no_unlisted_package_appeared() -> None:
    """A new subpackage is a structural decision; it should not arrive as a side effect."""
    found = {
        "trace_ai." + ".".join(path.parent.relative_to(PACKAGE_ROOT).parts)
        for path in PACKAGE_ROOT.rglob("__init__.py")
        if path.parent != PACKAGE_ROOT
    }
    assert found == set(PACKAGES), (
        f"unexpected packages {sorted(found - set(PACKAGES))}, "
        f"missing {sorted(set(PACKAGES) - found)}"
    )


# Runtime distribution names mapped to the module they import as. Distribution name and import name
# differ often enough (`python-dotenv` -> `dotenv`, `pyyaml` -> `yaml`) that the mapping is stated.
_IMPORT_NAME = {
    "anthropic": "anthropic",
    "pydantic": "pydantic",
    "pydantic-settings": "pydantic_settings",
    "python-dotenv": "dotenv",
    "pyyaml": "yaml",
}


def _declared_runtime_dependencies() -> set[str]:
    """The distribution names in pyproject's `[project].dependencies`, versions stripped."""
    import re

    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    names = set()
    for raw in block.splitlines():
        line = raw.strip().strip(",").strip('"')
        if not line or line.startswith("#"):
            continue
        names.add(re.split(r"[<>=!~ ]", line, maxsplit=1)[0])
    return names


def test_every_declared_runtime_dependency_is_imported() -> None:
    """A dependency in the wheel that no code imports is dead weight shipped to every install --
    `langsmith` was exactly that (DEC-090). Every declared runtime dependency must be imported
    somewhere in `src/`, so a re-added-and-unwired dependency fails here rather than shipping."""
    imported: set[str] = set()
    for source in PACKAGE_ROOT.rglob("*.py"):
        package = ".".join(source.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts[:-1])
        for module in imported_modules(source, package=package):
            imported.add(module.split(".", 1)[0])

    for distribution in _declared_runtime_dependencies():
        import_name = _IMPORT_NAME.get(distribution)
        assert import_name is not None, (
            f"{distribution!r} is declared but this test does not know its import name; add it to "
            f"_IMPORT_NAME"
        )
        assert import_name in imported, (
            f"{distribution!r} is a declared runtime dependency imported nowhere in src/; wire it "
            f"or drop it from pyproject"
        )
