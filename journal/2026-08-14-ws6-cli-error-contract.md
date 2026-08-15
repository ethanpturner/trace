# WS6: CLI error contract

Sixth workstream of the robustness program (#447), the first of phase 3. It carries a decision-log
entry (DEC-088) because it changes a decided contract: the CLI's exit codes.

## What changed

**Four exit codes, and "refused" is no longer "crashed" (DEC-088).** The CLI returned `1` for both a
genuine error and every stated refusal — a context not approvable, an approval blocked, evidence or
a report that drifted, a `reset` dry run — so a script could not tell the two apart without parsing
the prose the exit code exists to make unnecessary. Refusals now exit `3`; `1` is an error, `2` is
argparse, `0` is success. The `--help` epilog and the module docstring state the table.

**Argparse converters for the cost and count ceilings.** `--max-cost abc` built a `Decimal` inline,
whose `decimal.InvalidOperation` (an `ArithmeticError`, not a `ValueError`) escaped `EXPECTED_ERRORS`
as a traceback. `_decimal` and `_non_negative_int` are argparse `type=` converters that reject a
non-number and a negative as exit `2`, matching `--max-model-calls` and `--treatment-review-by`.

**A pipeline `ValidationError` keeps its traceback.** `ValueError` in `EXPECTED_ERRORS` swallowed
every `pydantic.ValidationError` (a `ValueError` subclass) and rendered it as a one-line error —
inverting the module's own contract, since DEC-006 says a domain object never fails validation, so
one that does is a bug. The dispatch now re-raises `ValidationError` ahead of the `EXPECTED_ERRORS`
handler. `ValueError` stays in the tuple because the domain raises it on an operator-supplied
identifier (`parse_id`) and a few services raise it on operator input — removing it would traceback
a mistyped `asm-001`, which is why the narrower re-raise is the right cut (the issue's sanctioned
"at minimum").

**`CommandInputError` and clean I/O messages.** A `CommandInputError(ValueError)` names the CLI's own
input errors; the CLI's `raise ValueError` sites became it, the `Severity`/`RiskTreatment` coercions
and operator file reads/writes are wrapped so an unknown enum value, a missing `--apply` file, a
malformed `--response`, or an unwritable `--export` is a one-line message rather than a traceback.

**`trace view` on a busy port is a message.** `_view` catches `OSError`; EADDRINUSE prints
`port N is already in use; pass --port` — running the demo view twice is the likeliest slip.

**`context extract` reuses `_model_flags`.** It hand-rolled a singular `--response` that read a
directory as a file (`IsADirectoryError`); it now takes the repeatable, directory-expanding
`--response` that `run` and `resume` use. Dead `_evidence_type` deleted. The 490-line `build_parser`
split was left for later (the issue marks it optional) to keep this diff reviewable.

## Tests

`--max-cost abc` / `-5` and `--max-model-calls -1` exit 2 with a message; a pipeline
`ValidationError` keeps its traceback (a monkeypatched handler); `trace view` on an occupied port
exits 1 with the busy-port message; `context extract --response <dir>` works; and the five refusal
commands now assert exit 3. Full suite green (3701); the ForgeFlow replay reproduces byte-for-byte.

## Open next

WS7 (#448, evaluation harness integrity) is the next workstream, still phase 3. No dependency on
this one.
