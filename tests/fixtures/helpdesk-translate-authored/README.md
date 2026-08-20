# helpdesk-translate-authored

The Helpdesk Translate scenario as it existed before its live capture: the authored recording
(#328), with the scenario's input and truth set copied unchanged. Frozen here as a test fixture
the day the live capture replaced `benchmarks/translation-gateway/recorded/` (#484).

Tests that need a scenario with a known, stable replay shape register this directory under a
synthetic slug through `registry_path` rather than borrowing a registered scenario. Every
registered scenario now carries a live recording, and a live recording's scores move when a
scenario is re-captured — retargeting harness tests from slug to slug as captures landed was
the churn this fixture ends. The authored recording is deterministic by construction: it
matches its truth set's findings exactly (false-negative rate 0.0), loses them when evidence
validation is ablated, and carries no offline report pin.

Nothing here is registered in `benchmarks/scenarios.yaml`, replayed by `trace evaluate`, or
counted by the scorecard. It is test input, not evaluation evidence.
