# Reply Tuner — reviewer notes

Judgement calls, recorded so the truth set can be argued with rather than guessed at.

- **The finding sits on the Tuning Job, not the Training Store.** The store holds the
  transcripts; the tuning job is where unminimized content becomes weights. Either component
  is defensible; the truth set picks the point of transformation, and `allow_consolidation`
  keeps a run that reasons store-first from being punished for it.
- **`severity_guidance: high`, not critical.** Memorized content surfaces one reply at a
  time to authenticated agents and, through them, to other customers' threads — a real
  disclosure with a bounded channel, not a bulk exfiltration path.
- **The write-path suppression is the pack's own false-positive class.** A generic review of
  any training pipeline asserts an ungoverned corpus; this document governs it and says so.
  The satisfied mapping must carry the suppressed conclusion, which is what
  `expected-rejections.yaml` REJ-RT-01 asserts by mechanism.
- **Base-model provenance is deliberately unaddressed.** The document names a vendor base
  model and nothing more; that silence must resolve to `unverified`, and no finding or gap is
  authored for it — the DEC-009 negative the scenario carries on purpose.
