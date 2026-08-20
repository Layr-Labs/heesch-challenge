# The benchmark runner (record profile)

The benchmark job (`.github/workflows/benchmark.yml`, dispatched by Yukon)
runs on **Blacksmith** (blacksmith.sh) managed runners — the same provider
the reference challenges use — so record-scale proofs are verified and
scored **inside the job**: `F(S,7)` (the `Hc = 5, Hh = 6` certificate) for
every realistic candidate size, `F(S,8)` (the `Hc = 6, Hh = 7` case) to
16 cells today and to 20 after one measurement (below). Measured costs:
`docs/ml-feasibility.md`; the budgets the harness applies:
`heesch_verify/profile.py` `RECORD`.

## Setup: install the Blacksmith GitHub App (one-time, admin)

1. Sign in at [app.blacksmith.sh](https://app.blacksmith.sh) with the
   GitHub org and **install the Blacksmith GitHub App**, granting it this
   repository. No runner registration, no labels to create — Blacksmith
   provisions a fresh VM per job for any `runs-on: blacksmith-*` label.
2. Until the App is installed, `benchmark.yml` / `record-e2e.yml` /
   `measure.yml` sit queued with "no runner matching" — nothing scores
   incorrectly, it just waits.

## Instance

The workflows use **`blacksmith-32vcpu-ubuntu-2404` — 32 vCPU / 128 GB RAM /
1.5 TB disk** (Ubuntu 24.04, GitHub-image-compatible: `sudo`, gcc, apt all
work; billed per-minute while a job runs). This mirrors
`ecdsafail-challenge` and clears the record profile's minima
(MemAvailable ≥ 24 GiB, scratch free ≥ 60 GiB) roughly 5× over — including
the heaviest instance in the class, a 20-cell-hex `F(S,8)` (~275 M clauses,
~30 GB DIMACS, ~15–18 GB RSS).

Changing tier is a one-line `runs-on` edit; documented smaller Blacksmith
sizes that still meet the record minima:

| label | vCPU | RAM | disk |
|---|---|---|---|
| `blacksmith-32vcpu-ubuntu-2404` (used) | 32 | 128 GB | 1.5 TB |
| `blacksmith-16vcpu-ubuntu-2404` | 16 | 64 GB | 750 GB |
| `blacksmith-8vcpu-ubuntu-2404` | 8 | 32 GB | 160 GB |

(The workload is single-core-dominated — the encoder and each checker use
one core — so the vCPU count is margin; RAM and disk are what the record
profile actually consumes.)

## Acceptance (after the App is installed)

1. Dispatch `benchmark.yml` on the baseline: the **preflight step must
   pass** (`tools/runner_preflight.py --require record` asserts
   MemAvailable ≥ 24 GiB, scratch free ≥ 60 GiB, ≥ 8 CPUs, x86-64 Linux,
   `bwrap`), and `score.json` must say `"resource_profile": "record"`.
2. Dispatch `record-e2e.yml`: it produces an `F(S,7)` proof with the
   participant tooling and scores it in-harness — the acceptance test for
   the whole record path.
3. Dispatch `measure.yml` for the shapes listed in `docs/STATUS.md` §3;
   extend `docs/ml-feasibility.md` with the rows and widen the band to
   `(20, 8)` — on 128 GB, memory is no longer the constraint.

## Why the preflight fails loud

If the machine is below the record minima (wrong label, provider
downgrade), the harness would *silently* select the `standard` profile
(8 GB / 30-min budgets) and answer `RESOURCE_EXCEEDED` to every
record-scale proof; failing the job instead makes a misprovisioned runner
visible immediately. The harness never reads a profile name from the
environment: the machine is the policy, and only `submission/` is
participant-editable.

## Security posture (unchanged)

The verify stage still runs under bubblewrap (installed by `setup.sh`'s
best-effort apt step on Blacksmith's GitHub-compatible image): read-only
filesystem, no network, no capabilities, writable only in the throwaway
scratch dir; participant files are parsed, never executed; the checkers are
the vendored, hash-pinned binaries built by `setup.sh`. See
`docs/THREAT-MODEL.md`.

## Alternative: a self-hosted box

Equivalent hardware works too: x86-64 Ubuntu 24.04, ≥ 8 vCPU, ≥ 32 GB RAM
(MemAvailable ≥ 24 GiB idle), ≥ 100 GB disk (≥ 60 GiB free) at
`HEESCH_SCRATCH` (repo variable, default `/tmp`), `bubblewrap`,
`build-essential`, `python3.11+`, `jq`, `git`, passwordless `sudo` or
`setpriv`. Register it for this repository with a label of your choice and
point `runs-on` at it.
