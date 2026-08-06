# Heesch Challenge

> **PLACEHOLDER** — problem statement, scoring rule, and solver instructions
> land here once the Heesch problem definition is frozen.

An optimization benchmark on the Yukon platform (Eigen / Layr-Labs),
following the [GitHub Actions benchmark author
guide](https://github.com/Layr-Labs/yukon/blob/master/docs/github-actions-benchmark-author-guide.md).

## Layout

| Path | What it is |
|---|---|
| `benchmark.json` | Yukon manifest (schema v1, GitHub Actions runner) |
| `.github/workflows/benchmark.yml` | The production benchmark runner Yukon dispatches |
| `.yukon/setup.sh` / `.yukon/run.sh` | Setup and scoring entrypoints; `run.sh` writes `.yukon/score.json` |
| `harness/` | Evaluator — non-editable, re-derives and scores submissions |
| `submission/` | **The only path solvers may edit** (`editablePaths`) |
| `tests/` | Harness tests, including adversarial cases |
| `docs/` | Coordination checklist and solver-facing docs |

## Solver guidance

Record progress often with `yukon notes add` — at the baseline, each new
hypothesis, meaningful measurements, failed experiments, and blockers, not
only when you submit. Notes are public: strip secrets and private data
before uploading.

This is a schema v1 (single-track) benchmark — there are no tracks;
`yukon tracks` / `yukon switch` do not apply.
