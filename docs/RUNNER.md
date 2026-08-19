# The benchmark runner (record profile)

The benchmark job (`.github/workflows/benchmark.yml`, dispatched by Yukon)
runs on a **dedicated self-hosted runner** so that record-scale proofs are
verified and scored **inside the job** — in particular the certificate a
legitimate `Hc = 5, Hh = 6` candidate needs, `F(S,7)` UNSAT, for every size
a record candidate realistically has (11–20 cells), and `F(S,8)` (the
`Hc = 6, Hh = 7` case) for ≤ 12 cells. Measured costs are in
`docs/ml-feasibility.md`; the budgets the harness applies are
`heesch_verify/profile.py` `RECORD`.

## Machine

| | minimum | why |
|---|---|---|
| CPU | 8 vCPU x86-64 | `cake_lpr` is x86-64 Linux only; the encoder is single-threaded, the checkers run sequentially — cores are margin, not speed |
| RAM | 64 GB (MemAvailable ≥ 56 GiB when idle) | 20-cell `F(S,7)` encode peaks ~12 GB RSS; `F(S,8)` ~25 GB; `cake_lpr` heap up to 48 GB on a full CNF (a core-list proof needs far less) |
| Scratch | ≥ 200 GB NVMe, ≥ 150 GiB free at job start, mounted at the path in the `HEESCH_SCRATCH` repository variable (default `/tmp`) | the regenerated DIMACS is up to ~27 GB, the decompressed payload up to 8 GiB, LRAT conversion a few GB more |
| OS | Ubuntu 24.04 LTS, `bubblewrap`, `gcc`, `python3.11+`, `jq`, `git` | `benchmark.sh` sandboxes the verify under bwrap (needs passwordless `sudo` *or* `setpriv`, see the escalation ladder in `benchmark.sh`) |
| Job time | `timeout-minutes: 240` in the workflow | worst case: encode ≤ 3600 s + checkers ≤ 9000 s overall (`RECORD.checker_deadline_s`) + witness/startup |

One job at a time (the runner has a single slot; the workflow's
`concurrency` group cancels superseded runs).

## Registration

1. Create the instance; mount the NVMe scratch; `sudo apt-get install
   bubblewrap build-essential python3 python3-venv jq git`.
2. Register it as a GitHub Actions self-hosted runner for this repository
   with the labels **`linux`, `x64`, `heesch-record`** (Settings → Actions →
   Runners → New self-hosted runner; run it as a service).
3. Set the repository variable `HEESCH_SCRATCH` to the scratch mount
   (Settings → Variables → Actions) if it is not `/tmp`.
4. Dispatch `benchmark.yml` once on the baseline: the **preflight step must
   pass** (`tools/runner_preflight.py --require record`), `score.json` must
   say `"resource_profile": "record"`.
5. Dispatch `record-e2e.yml` once: it produces an `F(S,7)` proof and scores
   it in-harness — that is the acceptance test for the runner.

## What the preflight checks and why it fails loud

`tools/runner_preflight.py --require record` asserts MemAvailable ≥ 56 GiB,
scratch free ≥ 150 GiB, ≥ 8 CPUs, x86-64 Linux, `bwrap` present — the same
thresholds `heesch_verify.profile.detect()` uses inside the sandbox. If the
machine is smaller, the harness would *silently* select the `standard`
profile (8 GB / 30-min budgets) and answer `RESOURCE_EXCEEDED` to every
record-scale proof; failing the job instead makes a misprovisioned runner
visible immediately. The harness never reads a profile name from the
environment: the machine is the policy, and only `submission/` is
participant-editable.

## Security posture (unchanged)

The verify stage still runs under bubblewrap: read-only filesystem, no
network, no capabilities, writable only in the throwaway scratch dir;
participant files are parsed, never executed; the checkers are the vendored,
hash-pinned binaries built by `setup.sh`. See `docs/THREAT-MODEL.md`.

## If the runner is down

`benchmark.yml` queues until a `heesch-record` runner is online. There is no
automatic fallback to a hosted runner, by design: a hosted 8 GB runner would
score the same submissions under the `standard` profile and reject record
proofs with `RESOURCE_EXCEEDED`, which is a worse outcome than a delayed
score. To run on a hosted runner temporarily, change `runs-on` and expect
`resource_profile: standard` in every score.
