"""The guard that makes "provider code lives behind the seam" true rather than aspirational.

DEC-014 keeps the model interface provider-agnostic and puts provider-specific code in an adapter
"and nowhere else". That is a property of the whole source tree, so it is asserted over the whole
source tree rather than trusted to review: one `import anthropic` in a service is not a test
failure anywhere else, and once one exists the next is unremarkable.

The list of forbidden packages is wider than what is installed. `langchain` and `instructor`
were declared and removed by DEC-014 and DEC-016; naming them here is about where an import may
appear rather than which packages happen to be installed this week, so a dependency that returns
does not find the tree already open to it. `openai` returned with DEC-095's second adapter, and
the rule generalized rather than opened: each adapter may import exactly its own SDK.

The check reads the source rather than the imported module, so an import inside a function body
counts the same as one at the top of a file — which is exactly where a provider import would be
hidden by someone working around this test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from trace_ai.config import PROJECT_ROOT

PACKAGE_ROOT = PROJECT_ROOT / "src" / "trace_ai"

# The modules allowed to import a provider SDK, each exactly its own (DEC-014, DEC-095).
ADAPTERS = {
    PACKAGE_ROOT / "infrastructure" / "model" / "anthropic_adapter.py": "anthropic",
    PACKAGE_ROOT / "infrastructure" / "model" / "openai_adapter.py": "openai",
}

PROVIDER_PACKAGES = frozenset(
    {"anthropic", "openai", "langchain", "langchain_anthropic", "langgraph", "instructor"}
)


def imported_packages(source: Path) -> set[str]:
    """Every top-level package a module imports, however it imports it."""
    found: set[str] = set()
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def package_modules() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def test_the_source_tree_was_found() -> None:
    """A parser that finds nothing makes every comparison below vacuously true."""
    assert len(package_modules()) > 10
    for adapter in ADAPTERS:
        assert adapter.exists(), "an adapter moved; this guard names each by path"


@pytest.mark.parametrize("module", package_modules(), ids=lambda path: path.name)
def test_only_the_adapter_imports_a_provider_sdk(module: Path) -> None:
    """DEC-014's "and nowhere else", asserted rather than reviewed."""
    allowed = {ADAPTERS[module]} if module in ADAPTERS else set()
    offending = imported_packages(module) & PROVIDER_PACKAGES - allowed
    assert not offending, (
        f"{module.relative_to(PROJECT_ROOT)} imports {sorted(offending)}. Provider code lives in "
        f"its own adapter and nowhere else (DEC-014) -- an adapter may import exactly its own "
        f"SDK; depend on the `StructuredModel` protocol instead."
    )


@pytest.mark.parametrize(("adapter", "sdk"), ADAPTERS.items(), ids=lambda value: str(value)[-20:])
def test_each_adapter_does_import_its_sdk(adapter: Path, sdk: str) -> None:
    """The inverse. A guard that passes because the adapter was gutted is a guard about nothing."""
    assert sdk in imported_packages(adapter)


def test_the_seam_package_does_not_re_export_the_adapter() -> None:
    """`trace_ai.infrastructure.model` is imported by everything that touches a model. Re-exporting
    the adapter there would pull the provider SDK into every one of those modules — the coupling
    the seam exists to prevent, reintroduced by an import line."""
    exported = imported_packages(PACKAGE_ROOT / "infrastructure" / "model" / "__init__.py")
    assert not exported & PROVIDER_PACKAGES


@pytest.mark.parametrize("adapter", ADAPTERS, ids=lambda path: path.name)
def test_the_provider_client_is_not_constructed_at_import_time(adapter: Path) -> None:
    """A client built at import makes `import trace_ai` require an API key, which is what
    `Settings.require()` exists to avoid and what would break a bare `uv run pytest` on a machine
    with no `.env`. Module-level constants are fine; a call into the SDK is not."""
    tree = ast.parse(adapter.read_text(encoding="utf-8"), filename=str(adapter))
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            if isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name):
                assert callee.value.id not in PROVIDER_PACKAGES, (
                    f"{adapter.name} calls into a provider SDK at import time, line {node.lineno}"
                )
