# Order Notifier reviewer notes

Guidance for whoever plays the reviewer at the two checkpoints in a benchmark run.

## Checkpoint 1 — context

Approve the context as extracted. Both documents describe the same Callback Receiver; the
two documented claims about its intake are two statements of one fact, and that is what the
pipeline is being graded on downstream.

## Checkpoint 2 — findings

Exactly one finding is expected (severity guidance `medium`). If two unsigned-intake
findings reach the checkpoint separately, the run has failed the scenario — the duplicate
should already be merged with `duplicate_of_id` set and a merge record retained. Approve
the survivor; its evidence should cite both documents.
