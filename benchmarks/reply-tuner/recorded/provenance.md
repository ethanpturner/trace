# Reply Tuner — recording provenance

Authored offline (#531, DEC-114), not captured from a live run: each response was written by
driving the pipeline's replay path stage by stage, the same convention as the other authored
scenarios (every provenance says which). The recording replays with `trace evaluate
reply-tuner` and completes with the expected outcomes: one approved finding (fnd-001,
req-TRAIN-002, severity high per the recorded decision), one documentation gap
(req-TRAIN-003, from the unverified mapping whose evidence assessment recommends a gap), and
the satisfied req-TRAIN-001 mapping carrying its suppressed conclusion.

No baseline recordings are staged yet: baselines are captured, not authored (DEC-100), and
`trace capture reply-tuner baseline-generic|baseline-structured` is the keyed step that adds
them.
