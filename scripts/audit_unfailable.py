"""Find checks that cannot come out false.

Six defects of one shape were found across this repository and a sibling in two days: a filter
naming a status nothing assigned, a metric computed over authored data, a boundary claim true of one
path and silent about another, a requirement satisfied by a fallback that is always present, a
question shown to a model as the negation of the label it was filed under, and a state function
whose only reachable return was the passing one. In every case the code agreed with itself and
nobody had tested the direction.

This script finds the part of that class a machine can find, and only that part. It reports:

* `enum_member_never_assigned` -- a `StrEnum` member named nowhere under `src/`, whose enum
  annotates no field. Only code naming it could produce it, so a filter keyed on it selects nothing.
* `enum_member_parse_only` -- the same, except the enum *does* annotate a field, so parsing can
  produce the member from agent JSON, a decision file, or a recorded fixture. A candidate to read,
  not a finding.
* `exception_never_raised` -- an exception class defined under `src/` and never raised there, so the
  `except` clause naming it is unreachable from production code.
* `test_without_failing_assertion` -- a test function whose every assertion compares two literals, or
  which asserts nothing at all.

Each is a *worklist*, not a verdict. A member assigned through `getattr`, a `model_validate` over a
JSON payload, or a string literal that happens to equal the member's value will be reported and is a
false positive; the audit's write-up records which candidates were cleared and why, so a later run
does not redo the reading. The three shapes a machine cannot find -- polarity, a metric over
authored inputs, and a claim silent about a second path -- are listed in
`docs/architecture/unfailable-checks.md` and were found by reading.

Usage: `uv run python scripts/audit_unfailable.py [--json] [--root .]`
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class Finding:
    kind: str
    name: str
    location: str
    detail: str

    def render(self) -> str:
        return f"{self.kind}: {self.name} ({self.location}) -- {self.detail}"


@dataclass
class _Module:
    path: Path
    tree: ast.Module
    text: str


def _modules(root: Path, subdir: str) -> Iterator[_Module]:
    base = root / subdir
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:  # pragma: no cover -- a file that does not parse is not our business
            continue
        yield _Module(path=path, tree=tree, text=text)


def _is_str_enum(node: ast.ClassDef) -> bool:
    return any(
        (isinstance(base, ast.Name) and base.id in {"StrEnum", "Enum"})
        or (isinstance(base, ast.Attribute) and base.attr in {"StrEnum", "Enum"})
        for base in node.bases
    )


@dataclass
class _EnumMember:
    enum: str
    member: str
    value: str | None
    location: str


def _enum_members(modules: list[_Module]) -> list[_EnumMember]:
    members: list[_EnumMember] = []
    for module in modules:
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.ClassDef) or not _is_str_enum(node):
                continue
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                    continue
                target = stmt.targets[0]
                if not isinstance(target, ast.Name):
                    continue
                value = stmt.value.value if isinstance(stmt.value, ast.Constant) else None
                members.append(
                    _EnumMember(
                        enum=node.name,
                        member=target.id,
                        value=value if isinstance(value, str) else None,
                        location=f"{module.path}:{stmt.lineno}",
                    )
                )
    return members


def _attribute_uses(modules: list[_Module]) -> set[tuple[str, str]]:
    """Every `Enum.MEMBER` reference, as (enum, member)."""
    uses: set[tuple[str, str]] = set()
    for module in modules:
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                uses.add((node.value.id, node.attr))
    return uses


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """`id()` of every docstring constant, which is prose and not a use of a value."""
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docstrings.add(id(first.value))
    return docstrings


def _enum_definition_constants(tree: ast.Module) -> set[int]:
    """`id()` of the right-hand side of every enum member assignment.

    A member's own definition (`PERMISSIVE = "permissive"`) is a string literal under `src/`, and
    counting it as a use makes every member look used. It is the declaration, not a producer.
    """
    defined: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _is_str_enum(node):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                defined.add(id(stmt.value))
    return defined


def _string_constants(modules: list[_Module]) -> set[str]:
    """Every string literal under `src/` that is neither a docstring nor an enum declaration.

    Both exclusions are load-bearing. Docstrings are prose: an enum value named in a sentence is
    documentation, not a code path that produces the value. An enum member's own right-hand side is
    the declaration itself. Counting either masked every candidate.
    """
    constants: set[str] = set()
    for module in modules:
        excluded = _docstring_nodes(module.tree) | _enum_definition_constants(module.tree)
        for node in ast.walk(module.tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in excluded
            ):
                constants.add(node.value)
    return constants


def _annotated_enums(modules: list[_Module]) -> set[str]:
    """Every enum named as a field annotation, so parsing can produce its members.

    This is the detector's single most important distinction. A member of an enum that annotates a
    field arrives by `model_validate` over agent JSON, a reviewer's decision file, or a recorded
    fixture; production never names it, and never having to is the point. A member of an enum that
    annotates nothing can only be produced by code that names it, so one nothing names is dead.
    """
    annotated: set[str] = set()

    def record(annotation: ast.expr | None) -> None:
        if annotation is None:
            return
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name):
                annotated.add(node.id)
            elif isinstance(node, ast.Attribute):
                annotated.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                annotated.add(node.value.strip("'\"[] |"))

    for module in modules:
        for node in ast.walk(module.tree):
            if isinstance(node, ast.AnnAssign):
                record(node.annotation)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for argument in [*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs]:
                    record(argument.annotation)
                record(node.returns)
    return annotated


def _enum_findings(
    src: list[_Module], tests: list[_Module], scripts: list[_Module]
) -> list[Finding]:
    members = _enum_members(src)
    src_uses = _attribute_uses(src)
    src_strings = _string_constants(src)
    annotated = _annotated_enums(src)
    elsewhere = _attribute_uses(tests) | _attribute_uses(scripts)
    findings: list[Finding] = []
    for member in members:
        key = (member.enum, member.member)
        if key in src_uses:
            continue
        # A member whose *value* appears as a non-docstring literal under src/ is produced by that
        # literal. That is a use, and not one to flag.
        if member.value is not None and member.value in src_strings:
            continue
        where = "named only in tests or scripts" if key in elsewhere else "named nowhere"
        if member.enum in annotated:
            findings.append(
                Finding(
                    kind="enum_member_parse_only",
                    name=f"{member.enum}.{member.member}",
                    location=member.location,
                    detail=(
                        f"{where} under src/, but {member.enum} annotates a field, so parsing can "
                        "produce it; confirm a real producer exists before treating as dead"
                    ),
                )
            )
        else:
            findings.append(
                Finding(
                    kind="enum_member_never_assigned",
                    name=f"{member.enum}.{member.member}",
                    location=member.location,
                    detail=(
                        f"{where} under src/, and {member.enum} annotates no field, so only code "
                        "naming it could produce it"
                    ),
                )
            )
    return findings


def _exception_classes(modules: list[_Module]) -> dict[str, str]:
    classes: dict[str, str] = {}
    for module in modules:
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                name = (
                    base.id
                    if isinstance(base, ast.Name)
                    else base.attr
                    if isinstance(base, ast.Attribute)
                    else ""
                )
                if name.endswith(("Error", "Exception", "Warning")):
                    classes[node.name] = f"{module.path}:{node.lineno}"
                    break
    return classes


def _raised_names(modules: list[_Module]) -> set[str]:
    raised: set[str] = set()
    for module in modules:
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            exc = node.exc
            if isinstance(exc, ast.Call):
                exc = exc.func
            if isinstance(exc, ast.Name):
                raised.add(exc.id)
            elif isinstance(exc, ast.Attribute):
                raised.add(exc.attr)
    return raised


def _exception_findings(src: list[_Module]) -> list[Finding]:
    classes = _exception_classes(src)
    raised = _raised_names(src)
    subclassed = {
        base.id
        for module in src
        for node in ast.walk(module.tree)
        if isinstance(node, ast.ClassDef)
        for base in node.bases
        if isinstance(base, ast.Name)
    }
    return [
        Finding(
            kind="exception_never_raised",
            name=name,
            location=location,
            detail="defined under src/ and never raised there",
        )
        for name, location in sorted(classes.items())
        if name not in raised and name not in subclassed
    ]


def _is_literal(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_literal(element) for element in node.elts)
    if isinstance(node, ast.Dict):
        return all(key is not None and _is_literal(key) for key in node.keys) and all(
            _is_literal(value) for value in node.values
        )
    if isinstance(node, ast.UnaryOp):
        return _is_literal(node.operand)
    return False


def _assertion_can_fail(node: ast.Assert) -> bool:
    """A comparison of two literals, or a bare literal, cannot fail on any input."""
    test = node.test
    if _is_literal(test):
        return False
    if isinstance(test, ast.Compare):
        operands = [test.left, *test.comparators]
        return not all(_is_literal(operand) for operand in operands)
    return True


def _test_findings(tests: list[_Module]) -> list[Finding]:
    findings: list[Finding] = []
    for module in tests:
        for node in ast.walk(module.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            asserts = [child for child in ast.walk(node) if isinstance(child, ast.Assert)]
            calls = [
                child
                for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and (
                    (isinstance(child.func, ast.Attribute) and child.func.attr.startswith("assert"))
                    or (isinstance(child.func, ast.Name) and child.func.id.startswith("assert"))
                )
            ]
            raises = [
                child
                for child in ast.walk(node)
                if isinstance(child, (ast.With, ast.AsyncWith))
                for item in child.items
                if isinstance(item.context_expr, ast.Call)
                and (
                    (
                        isinstance(item.context_expr.func, ast.Attribute)
                        and item.context_expr.func.attr in {"raises", "warns"}
                    )
                    or (
                        isinstance(item.context_expr.func, ast.Name)
                        and item.context_expr.func.id in {"raises", "warns"}
                    )
                )
            ]
            location = f"{module.path}:{node.lineno}"
            if not asserts and not calls and not raises:
                findings.append(
                    Finding(
                        kind="test_without_failing_assertion",
                        name=node.name,
                        location=location,
                        detail="no assertion, assert-helper call, or raises/warns context",
                    )
                )
                continue
            if (
                asserts
                and not calls
                and not raises
                and not any(_assertion_can_fail(statement) for statement in asserts)
            ):
                findings.append(
                    Finding(
                        kind="test_without_failing_assertion",
                        name=node.name,
                        location=location,
                        detail="every assertion compares literals only",
                    )
                )
    return findings


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def by_kind(self) -> dict[str, list[Finding]]:
        grouped: dict[str, list[Finding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.kind, []).append(finding)
        return grouped


def audit(root: Path) -> Report:
    src = list(_modules(root, "src"))
    tests = list(_modules(root, "tests"))
    scripts = list(_modules(root, "scripts"))
    findings = [
        *_enum_findings(src, tests, scripts),
        *_exception_findings(src),
        *_test_findings(tests),
    ]
    return Report(findings=sorted(findings, key=lambda f: (f.kind, f.name)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", dest="as_json")
    arguments = parser.parse_args(argv)

    report = audit(arguments.root.resolve())
    grouped = report.by_kind()

    if arguments.as_json:
        payload = {
            kind: [{"name": f.name, "location": f.location, "detail": f.detail} for f in findings]
            for kind, findings in sorted(grouped.items())
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if not report.findings:
        print("no candidates")
        return 0
    for kind, findings in sorted(grouped.items()):
        print(f"{kind} ({len(findings)})")
        for finding in findings:
            relative = finding.location
            print(f"  {finding.name}  {relative}")
            print(f"      {finding.detail}")
    print(f"\n{len(report.findings)} candidates; each needs reading before it is a finding")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
