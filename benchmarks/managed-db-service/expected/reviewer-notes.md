# Managed DB Service reviewer notes

## Construction method

An original small architecture authored for this project (design-principles section 19), built
to exercise inherited platform controls: encryption at rest and in transit provided by a
managed database, which a generic review turns into encryption findings. The truth set derives
from `input/system-overview.md` and nothing else; each encryption rejection cites a
`common_false_positives` entry that exists in catalog 0.1 for req-DATA-001.

Single annotator (the project author), with re-derivation after an interval as the
self-agreement check: the empty finding set and the three rejections reproduced identically;
GAP-MD-01 reproduced with the same requirement. No count is declared (DEC-028).

## Why zero findings is the correct output

Encryption at rest is default and platform-managed, key management is a managed KMS, and
transport terminates at the managed endpoint — all stated. req-DATA-001 is satisfied by an
inherited control, so the encryption findings a generic review invents are false positives the
catalog names. GAP-MD-01 (retention) is the one undetermined item, and REJ-MD-03 records that
the internal API's authorization is silent rather than absent.

## Deliberately not authored

`expected-context.yaml`, `expected-control-mappings.yaml`, and `expected-threats.yaml` are not
authored for this scenario, as above.
