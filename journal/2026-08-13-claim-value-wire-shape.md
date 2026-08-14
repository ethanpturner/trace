# The claim value learns what the wire accepts

## What changed

`ProposedContextClaim.value` narrowed from `JsonValue` to a scalar or a list of scalars, recorded
as DEC-083. The domain `ContextClaim.value` stays `JsonValue`. A regression test now transforms
all six agent proposal schemas through the provider's own schema transformation, so the class of
failure #412 named — a wire schema the structured-output format refuses — cannot return silently.

## Why this shape and not another

Two facts fell out of investigating the fix, and both narrowed the answer.

The obvious repair — replace `JsonValue` with an explicit recursive union so the schema renders
as `anyOf` instead of `{}` — transforms cleanly, but inspection of the transformed output showed
the provider's strictifier rewriting the open-mapping arm into an object that accepts only `{}`.
The prompt substitutes the application's *untransformed* export, so a mapping arm would have been
taught by the prompt and forbidden by the wire grammar simultaneously: an instruction to fail,
shipped as latitude. Dropping the mapping arm was therefore not a concession but the honest
shape — and a claim that wants to assert a mapping asserts one claim per key, which the
subject-predicate-value form already expresses.

The second fact made the narrowing cheap: a survey of every committed recording and truth set
found fifty claim values, all plain strings. The union to scalars-and-lists is headroom, not a
migration, and no fixture moved.

## The boundary it draws

The interesting line is proposal versus domain. The proposal schema crosses the wire, so the
provider's format constrains it; the domain object never does, and a reviewer's checkpoint-1 edit
should not be bound by what a provider can be asked for. The two types now differ where they used
to coincide, and both modules explain why — the kind of asymmetry that erodes unless the reason
is written where the reader stands.

## Open next

The retry-accounting pair (#397, #398) remains the natural joint change. With #395 and #412 both
closed, the first live call's known blockers are cleared — #324's live ForgeFlow capture is now
gated only on someone choosing to spend the money.
