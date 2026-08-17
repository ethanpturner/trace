# Reviewer notes: Relay Answers

The judgment guide used when authoring the recorded checkpoint decisions.

- Approve the whole context: the extraction reads both documents accurately, and the
  tenant-isolation boundary with the shared index inside it is the load-bearing observation.
- FND-RSB-01 is approvable at high severity because the statement is affirmative — relevance
  alone selects from a shared index — and the operations notes establish the ticket text
  includes pasted configuration with only email masking. This is not a silence being read as
  absence.
- The prompt-injection concern is real as a threat but not a finding: the documented fencing
  and plain-text rendering are exactly what req-AI-001 asks documentation to state.
- The retention question stays a gap, not a finding: nothing states deletions fail to
  propagate; nothing states they do. Concluding either way would be the DEC-009 failure.
