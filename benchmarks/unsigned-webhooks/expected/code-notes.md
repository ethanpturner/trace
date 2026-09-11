# Unsigned Webhooks: notes on the code layer

`../code/` is a running implementation of the system `../input/system-overview.md` describes,
authored from this truth set (DEC-156). It exists so a code reviewer and a documentation reviewer
can be measured on the same system. Nothing here or under `../code/` is supplied to Trace, and
nothing in this file or in `code-ground-truth.yaml` is supplied to a code reviewer: the reviewer
receives `../code/` alone.

This note was written before the code. It records what each module is for, which truth-set item
it realises, and which item is deliberately reachable only from code, so the experiment measures
the reviewers rather than the author's memory of what was intended.

## Module intent

| Module | Realises | Intent |
|---|---|---|
| `deploy_notifier/main.py` | FND-UW-01 | The public receiver. Parses the JSON body, validates its shape, records the delivery, and hands it to the notifier. It reads no signature header and calls nothing in `signing.py`. This is the documented negative, made literal. |
| `deploy_notifier/signing.py` | trap | A correct HMAC-SHA256 helper with a constant-time compare, matching the CI platform's documented signing scheme. It is importable and tested and never called by the receiver. A reviewer must decide whether an unused correct control is a control. Flagging the helper itself is the wrong answer; the weakness is at the receiver. |
| `deploy_notifier/replay.py` | GAP-UW-01, non-scoring | A bounded in-memory ledger of delivery identifiers. A repeated identifier is acknowledged and not re-posted while the process lives and the identifier has not been evicted. Whether that is replay protection depends on deployment (process count, restart cadence, eviction under load), which is exactly why the documentation layer records a gap and the code layer records a non-scoring entry rather than a verdict. |
| `deploy_notifier/notifier.py` | trap | Posts to the chat platform with a bearer token read from the environment. Without a token it writes to an in-memory outbox so the service runs in tests. The token is never hardcoded and never logged. |
| `deploy_notifier/events.py` | trap | The event model and the message formatter. The message is a plain-text field in a JSON body to the chat API; there is no template or markup interpretation to inject into. |
| `deploy_notifier/config.py` | trap | Settings from environment variables. `CI_SIGNING_SECRET` is accepted here, which makes the receiver's silence about it more pointed rather than less. |

## Reachable only from code

- That `signing.verify_signature` exists and is unused. The documentation says signing is
  supported by the platform and not checked by the receiver; it does not say the receiver ships
  the code to check it.
- The delivery ledger. The documentation is silent on replay; the code has a mechanism whose
  adequacy is a judgment call.

## Reachable only from documentation

- Nothing in this scenario. The system is small enough that the code states everything the
  document states. The asymmetry runs the other way here; `rag-support-bot` carries the case
  where documentation establishes something code cannot.

## How the truth was derived

FND-UW-01 maps to the receiver function that dispatches without verification. Its CWE is 345
(insufficient verification of data authenticity), with 306, 347, and 287 acceptable because tools
name the same fact under different headings. Every trap names a location a scanner is likely to
flag on pattern alone. Nothing under `../code/` was changed after this note and the truth file were
written except to make the tests pass.
