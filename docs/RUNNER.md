# The benchmark runner (record profile)

The benchmark job (`.github/workflows/benchmark.yml`, dispatched by Yukon)
runs on a runner labelled **`heesch-record`** so that record-scale proofs are
verified and scored **inside the job** — in particular the certificate a
legitimate `Hc = 5, Hh = 6` candidate needs, `F(S,7)` UNSAT, for every size a
record candidate realistically has (11–20 cells), and `F(S,8)` (the
`Hc = 6, Hh = 7` case) for ≤ 16 cells. Measured costs are in
`docs/ml-feasibility.md`; the budgets the harness applies are
`heesch_verify/profile.py` `RECORD`.

## Recommended: a GitHub larger hosted runner (no box to manage)

Create it once (org/repo admin): Settings → Actions → Runners → *New runner*
→ *New GitHub-hosted runner* → name **`heesch-record`**, Ubuntu 24.04 x64,
size **8-core / 32 GB RAM / 300 GB SSD**, and grant this repository access to
its runner group. `runs-on: heesch-record` in the workflows then matches it.
Billing is per-minute while a job runs (~$0.032/min → roughly $1–2 per
record-scale scoring; $0 idle).

Why 8-core / 32 GB is enough: the harness's binding cost is regenerating
`F(S,m)` — ~12 GB RSS and 13 GB of scratch at the band's edge (20-cell
`F(S,7)`); the checkers then run on the proof's core list (~2 % of the
formula, seconds, < 1 GB). Solving is the participant's job, not the
harness's. The one case beyond 32 GB is `F(S,8)` at 17–20 cells
(`Hc = 6, Hh = 7` on a large shape, ~25 GB RSS): if such a candidate ever
appears, create a 16-core / 64 GB runner with the same name — nothing else
changes.

## Alternative: a self-hosted box

x86-64 Ubuntu 24.04, ≥ 8 vCPU, **≥ 32 GB RAM** (MemAvailable ≥ 24 GiB idle),
**≥ 100 GB disk** (≥ 60 GiB free at job start) on the path in the
`HEESCH_SCRATCH` repository variable (default `/tmp`); `bubblewrap`,
`build-essential`, `python3.11+`, `jq`, `git`; passwordless `sudo` for bwrap
*or* `setpriv`. Register it for this repository with the label
`heesch-record`; run it as a service, one job at a time.

## Acceptance

1. Dispatch `benchmark.yml` on the baseline: the **preflight step must pass**
   (`tools/runner_preflight.py --require record` asserts MemAvailable ≥ 24 GiB,
   scratch free ≥ 60 GiB, ≥ 8 CPUs, x86-64 Linux, `bwrap`), and `score.json`
   must say `"resource_profile": "record"`.
2. Dispatch `record-e2e.yml`: it produces an `F(S,7)` proof with the
   participant tooling and scores it in-harness — the acceptance test for
   the whole record path.
3. Dispatch `measure.yml` for the shapes listed in `docs/STATUS.md` §3 and
   paste the rows into `docs/ml-feasibility.md`; widen the band from those
   numbers.

## Why the preflight fails loud

If the machine is below the record minima, the harness would *silently*
select the `standard` profile (8 GB / 30-min budgets) and answer
`RESOURCE_EXCEEDED` to every record-scale proof; failing the job instead
makes a misprovisioned runner visible immediately. The harness never reads a
profile name from the environment: the machine is the policy, and only
`submission/` is participant-editable.

## Security posture (unchanged)

The verify stage still runs under bubblewrap (GitHub larger runners include
it after `setup.sh`'s best-effort apt install): read-only filesystem, no
network, no capabilities, writable only in the throwaway scratch dir;
participant files are parsed, never executed; the checkers are the vendored,
hash-pinned binaries built by `setup.sh`. See `docs/THREAT-MODEL.md`.

## If the runner is missing

`benchmark.yml` queues until a `heesch-record` runner exists. There is no
automatic fallback to a standard runner, by design: it would score the same
submissions under the `standard` profile and reject record proofs with
`RESOURCE_EXCEEDED`, which is a worse outcome than a delayed score.
