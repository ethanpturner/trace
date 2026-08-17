"""The guard that keeps `docs/guide/` naming commands and flags that exist.

The guide is hand-written, and a hand-written reference drifts the way the demo script did:
`context show` once told the reviewer to run `--resolve-contradiction`, a flag the parser never
defined, and nothing failed until a person copy-pasted it (#472). Every other test asserts what
the code does; none reads what the guide says. So this file reads every fenced code block under
`docs/guide/`, extracts each `trace` invocation, and walks it against the parser `build_parser`
actually builds: the subcommand path must resolve, and every long flag must be defined on a
parser along that path.

It validates names, not behavior — no command runs, no provider is touched, and positional
values (`asm-001`, file paths, `ID=VALUE` pairs) are deliberately ignored. A validator that
passes on everything is the most dangerous kind of green, so the mutation tests hold it to
rejecting a misspelled subcommand and the exact flag that shipped wrong. Issue #473.
"""

from __future__ import annotations

import argparse
import re
import shlex

import pytest

from trace_ai.cli import build_parser
from trace_ai.config import PROJECT_ROOT

GUIDE_DIR = PROJECT_ROOT / "docs" / "guide"

GUIDE_FILES = (
    "getting-started.md",
    "assessment-walkthrough.md",
    "cli-reference.md",
    "reading-the-report.md",
    "troubleshooting.md",
)

FENCE = re.compile(r"^```")
SEPARATORS = frozenset({"|", "||", "&&", ";"})


def _fenced_lines(text: str) -> list[str]:
    """Every line inside a fenced code block, fence markers excluded."""
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if FENCE.match(line.strip()):
            inside = not inside
            continue
        if inside:
            lines.append(line)
    return lines


def _trace_invocations(text: str) -> list[list[str]]:
    """Token lists for each `trace` command in the text's fenced blocks.

    Backslash continuations are joined first, a leading `$` prompt and a `uv run` prefix are
    stripped, and the token list is cut at the first shell separator so a downstream `| head`
    is never mistaken for arguments.
    """
    joined: list[str] = []
    pending = ""
    for line in _fenced_lines(text):
        if line.rstrip().endswith("\\"):
            pending += line.rstrip()[:-1] + " "
            continue
        joined.append(pending + line)
        pending = ""
    if pending:
        joined.append(pending)

    invocations: list[list[str]] = []
    for line in joined:
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            continue
        if tokens[:1] == ["$"]:
            tokens = tokens[1:]
        if tokens[:2] == ["uv", "run"]:
            tokens = tokens[2:]
        if tokens[:1] != ["trace"]:
            continue
        command = tokens[1:]
        for index, token in enumerate(command):
            if token in SEPARATORS:
                command = command[:index]
                break
        invocations.append(command)
    return invocations


def _subparser_choices(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _options(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    return {option: action for action in parser._actions for option in action.option_strings}


def validate(tokens: list[str]) -> list[str]:
    """The names a documented invocation gets wrong, empty when it gets them all right."""
    parser = build_parser()
    allowed = _options(parser)
    current = parser
    errors: list[str] = []
    skip_value = False
    for token in tokens:
        if skip_value:
            skip_value = False
            continue
        if token.startswith("-"):
            name, _, inline_value = token.partition("=")
            action = allowed.get(name)
            if action is None:
                errors.append(f"unknown flag {name!r}")
            elif action.nargs != 0 and not inline_value:
                skip_value = True
            continue
        choices = _subparser_choices(current)
        if choices:
            if token in choices:
                current = choices[token]
                allowed |= _options(current)
            else:
                errors.append(f"unknown subcommand {token!r}")
                break
    return errors


def test_the_five_guide_files_exist() -> None:
    """A conformance loop over zero files is the most dangerous kind of green."""
    missing = [name for name in GUIDE_FILES if not (GUIDE_DIR / name).is_file()]
    assert not missing, f"docs/guide/ is missing {missing}"


@pytest.mark.parametrize("name", GUIDE_FILES)
def test_every_documented_invocation_names_real_commands_and_flags(name: str) -> None:
    text = (GUIDE_DIR / name).read_text(encoding="utf-8")
    invocations = _trace_invocations(text)
    assert invocations, f"{name} documents no runnable trace command; is the extractor broken?"
    failures = [
        f"trace {' '.join(tokens)}: {'; '.join(problems)}"
        for tokens in invocations
        if (problems := validate(tokens))
    ]
    assert not failures, f"{name} documents commands the CLI does not define:\n" + "\n".join(
        failures
    )


def test_the_validator_rejects_a_misspelled_subcommand() -> None:
    assert validate(["contxt", "show", "asm-001"]) == ["unknown subcommand 'contxt'"]


def test_the_validator_rejects_the_flag_that_shipped_wrong() -> None:
    """#472's bug, expressed as the mutation this guard exists to catch."""
    errors = validate(["context", "review", "asm-001", "--resolve-contradiction", "clm-001=v1"])
    assert errors == ["unknown flag '--resolve-contradiction'"]


def test_the_validator_accepts_a_real_invocation_with_values_and_pipes() -> None:
    text = (
        "```bash\n"
        'uv run trace assessment create --name "ForgeFlow Security Review"\n'
        "uv run trace context show asm-001 --evidence | head -40\n"
        "uv run trace findings review asm-001 --severity fnd-001=high --approve fnd-001\n"
        "uv run trace run asm-001 --model-profile offline-fake \\\n"
        "    --response demo/forgeflow/recorded/extraction\n"
        "```\n"
    )
    invocations = _trace_invocations(text)
    assert len(invocations) == 4
    assert all(validate(tokens) == [] for tokens in invocations)


# ------------------------------------------------------------------------------------------
# The reverse direction (#502): every parser flag is documented where its command is
# ------------------------------------------------------------------------------------------


def _reference_sections() -> dict[str, str]:
    """The cli-reference text, split by `## ` heading, keyed by the heading's first word.

    The reference's own layout rule: one `## <group>` section per command group, subcommands
    inside it. Splitting on headings scopes the flag check to the command's own section, so a
    flag documented under a different command cannot vouch for this one.
    """
    text = (GUIDE_DIR / "cli-reference.md").read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current: list[str] = []
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            for key in current:
                sections[key] = sections.get(key, "") + "\n".join(lines)
            # A heading names every command it documents ("run and resume" documents both).
            current = [word for word in line.removeprefix("## ").strip().split() if word != "and"]
            lines = []
        else:
            lines.append(line)
    for key in current:
        sections[key] = sections.get(key, "") + "\n".join(lines)
    return sections


def _documented_flags_hold(group: str, parser: argparse.ArgumentParser, section: str) -> list[str]:
    missing: list[str] = []
    for action in parser._actions:
        for option in action.option_strings:
            if option in {"-h", "--help"}:
                continue
            if option.startswith("--") and option not in section:
                missing.append(option)
            break  # one spelling per action is enough
    return missing


def test_every_parser_flag_is_documented_in_its_reference_section() -> None:
    """The guard's missing direction (#502): the forward check validates that documented flags
    exist, and was structurally incapable of catching a flag that exists but is undocumented —
    which is exactly how a wave of new flags strands the reference silently. Every long option
    of every command must appear somewhere in its group's `## ` section of cli-reference.md."""
    parser = build_parser()
    sections = _reference_sections()
    # The shared model flags are documented once, deliberately ("Shared model flags" under
    # Global behavior); the global sections vouch for any command, so single-sourcing survives.
    global_text = "".join(text for key, text in sections.items() if key in {"Exit", "Global"})
    failures: list[str] = []
    for group, group_parser in _subparser_choices(parser).items():
        section = sections.get(group)
        if section is None:
            failures.append(f"group {group!r} has no `## {group}` section in cli-reference.md")
            continue
        scoped = section + global_text
        failures.extend(
            f"{group}: {flag} exists and is undocumented in its section"
            for flag in _documented_flags_hold(group, group_parser, scoped)
        )
        for sub_name, sub_parser in _subparser_choices(group_parser).items():
            failures.extend(
                f"{group} {sub_name}: {flag} exists and is undocumented in its section"
                for flag in _documented_flags_hold(group, sub_parser, scoped)
            )
    assert not failures, "\n".join(failures)


def test_the_reverse_guard_has_teeth() -> None:
    """A guard that passes because its vouching absorbed everything is a guard about nothing:
    an option string absent from both the section and the global text must be reported."""
    probe = argparse.ArgumentParser()
    probe.add_argument("--flag-nobody-documented")
    assert _documented_flags_hold("probe", probe, "a section without the flag") == [
        "--flag-nobody-documented"
    ]
    assert _documented_flags_hold("probe", probe, "mentions --flag-nobody-documented") == []
