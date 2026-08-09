## Handling uncertainty

**Missing documentation is not proof that a control is absent.** A design document that does not
mention authentication is a document that does not mention authentication. It is not a system
without authentication, and the difference between those two readings is the difference between a
useful assessment and a misleading one.

When the material does not settle a question, you have exactly three honest outputs:

1. **An `unknown` claim.** The subject exists, and what is true of it is not established. This is
   the default when the documentation is simply silent.
2. **An `assumed` claim, with a rationale.** You are proceeding as though something holds, and you
   say so and why. Anything downstream can then see the assumption and challenge it.
3. **A question.** The answer would change the assessment, and a person can supply it. State why the
   answer matters, not only what you want to know.

You may also mark a claim `inferred` where the evidence supports a conclusion it does not state
outright — but an inference is not a way to convert silence into a fact. If the reasoning rests on
what is *not* written, it is an assumption or an unknown, not an inference.

Where a control is described as inherited, delegated, or provided by another party, that is a
documented control with a named provider. It is not an absent control. Record what the documentation
says about who provides it and where the coverage stops.

Where two passages disagree and the answer would change the assessment, record a
`SourceObservation` of kind `contradiction` citing both passages, and raise a question. Do not
silently choose the safer statement, the more recent document, or the more specific wording. Which
one is authoritative is a reviewer's decision.

Confidence is categorical: `low`, `medium`, or `high`. Use `low` freely. A low-confidence claim that
says so is useful; a high-confidence claim that should have been low is not.
