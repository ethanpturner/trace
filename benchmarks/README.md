# The benchmark corpus

Fifteen security-architecture assessment scenarios with authored truth sets, offline-replayable
recordings, and live baselines. `scenarios.yaml` is the authoritative list (DEC-027); nothing is
discovered by scanning directories.

Replay the whole corpus with no provider key, no network, and no account:

```bash
uv sync
uv run trace evaluate --all
```

**Read [`docs/eval/benchmark-package.md`](../docs/eval/benchmark-package.md) first** if you are
consuming this from outside the repository. It is the specification: what each scenario measures,
how the corpus was built, the licensing and provenance of every scenario, what the package version
promises, and — at length, because it matters most — what these numbers do not establish.

`manifest.yaml` describes the package: every scenario's files, its catalog and workflow pins, the
models its recordings attribute to, and a digest over each group. It is generated, never
hand-edited:

```bash
uv run python scripts/build_benchmark_manifest.py           # regenerate
uv run python scripts/build_benchmark_manifest.py --check   # fail if stale
```

Each scenario directory holds `input/` (what Trace is given), `expected/` (the truth set, never
supplied to the pipeline), and `recorded/` (the response envelopes, the checkpoint decision files,
the report-hash pins, and `baselines/`). `results/` is derived output from local runs and is
gitignored.
