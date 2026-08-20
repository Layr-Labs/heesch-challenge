# Heesch numbers of unmarked polyforms

Find a polyomino, polyhex or polyiamond with a **record Heesch number**.

The Heesch number `Hc` of a shape is the largest number of complete
surrounding rings (coronas) it admits before getting stuck; a shape that
tiles the plane has infinitely many and no Heesch number. The largest known
value for this class is **Hc = 4** (Kaplan 2022,
[arXiv:2105.09438](https://arxiv.org/abs/2105.09438), exhaustive to
19-ominoes / 17-hexes / 24-iamonds; six polyhexes of 11–17 cells and one
20-iamond reach it). Nothing above 19/17/24 cells has been searched
systematically. A proof-backed **Hc ≥ 5** here is a research result.

A Yukon optimization benchmark (Eigen / Layr-Labs); format-compatible with
Epoch AI's FrontierMath Heesch challenge (`--emit-epoch` export).

## The rule in one paragraph

Submit one shape plus a witness patch proving `Hc ≥ k`; the verifier
re-derives everything from your placements and never executes your code.
**The submission scores only if the shape is also proven not to tile the
plane** (fail-closed — a lower bound alone is not a Heesch number). Two
proofs are accepted: the shape is inside Kaplan's embedded exact census
(polyominoes ≤ 10 cells, polyhexes ≤ 8, polyiamonds ≤ 12 — decided
automatically), or the submission carries a **machine-checked UNSAT proof**
of the corona formula `F(S, m)` in a `#PROOF` block — `tools/prove.py`
produces one in a single command. Everything else is rejected.

## Quickstart

```bash
git clone <this repo> && cd heesch-challenge
pip install -e .                      # stdlib-only runtime; -e '.[prove]' adds python-sat
bash tools/build_checkers.sh          # drat-trim / lrat-check (+ cake_lpr on x86-64 Linux)
bash tools/build_solver.sh            # CaDiCaL for record-scale proofs (recommended)

$EDITOR submission/best.heesch        # your shape + witness (format below)
python -m heesch_verify submission/best.heesch          # verify the witness locally
python tools/prove.py submission/best.heesch --check    # produce + self-check the proof
# submit via Yukon; the benchmark job re-runs all of this and writes score.json
```

Use the verifier in your search loop — it is fast (typically < 1 s) and its
error codes are stable API:

```python
from heesch_verify import verify_witness
outcome = verify_witness(open("submission/best.heesch").read())
```

The full participant walkthrough (grammar semantics, proof workflow at
record scale, defect strategy, every error code) is
[`docs/submitting.md`](docs/submitting.md).

## File format (heesch-sat text format, adopted verbatim)

```
O x1 y1 x2 y2 ... xn yn      # grid: O square, H hex, I iamond; occupied cells
~ hc hh P                    # claimed Heesch numbers; P = patch count
N                            # placements in patch 1
level <a,b,c,d,e,f>          # x' = a·x+b·y+c, y' = d·x+e·y+f; level 0 = center
...
#DEFECT k+1 u_hc u_hh r      # OPTIONAL partial next corona (scoring gradient)
M
k+1 <a,b,c,d,e,f>
...
#PROOF 1                     # OPTIONAL non-tiler proof; must be last
encoder heesch-encoder/v2 2 <m>
cnf <cnf_sha256> <num_vars> <num_clauses>
file <basename> <drat|lrat> <none|xz> <payload_sha256>
core <basename> <none|xz> <payload_sha256> <num_clauses>   # optional, lrat only
```

`P = 1` when `hh == hc`; `P = 2` when `hh == hc + 1` (the second patch may
have holes in its outermost corona). Limits: ≤ 200 cells,
`span_x + span_y ≤ 29`, ≤ 20 000 placements per patch, shape file ≤ 2 MiB;
proof file ≤ 200 MiB stored / 8 GiB decompressed on the benchmark runner
(a record-scale core LRAT is ~20 MB xz).

## Scoring

```
score = hc_verified + progress toward the next corona   (fraction < 1)
```

The fractional part comes from the optional `#DEFECT` block: place partial
corona-(k+1) tiles; the verifier counts the required cells you failed to
cover. Covering more raises the score continuously — 47 uncovered → 31 → 12
→ 0 is four promotions on the same shape — and only a complete verified
corona rolls the integer over. **The score is not a Heesch number**; the
Heesch number is `metrics.hc_verified`. One linear leaderboard: any strict
improvement promotes (`minScoreImprovementBips: 0`); an equal score does not
displace the incumbent, so being first to a value holds it.

Claims are checked lower-bound style: if your patch proves less than you
claimed, the weaker verified value is scored and the discrepancy recorded.
Rejections carry stable machine-readable codes (`PATCH_GAP`,
`GATE_INCONCLUSIVE`, `PROOF_CNF_DIGEST_MISMATCH`, …) — the full table is in
`docs/submitting.md`.

## The record path

`Hc ∈ {Hh − 1, Hh}`, so a record candidate needs `F(S, Hh + 1)` UNSAT:
`F(S,6)` or `F(S,7)` for `Hc = 5`, up to `F(S,8)` for `Hc = 6`. The
benchmark job runs on a dedicated runner whose **record profile** verifies
these inside the job for every realistic candidate size (`F(S,7)` to
20 cells, `F(S,8)` to 16 — measured, `docs/ml-feasibility.md`), and
`score.json` then carries `record_eligible` (proof-backed, `hc ≥ 5`) and
`record_exact` (value pinned). Producing the proof takes minutes on a laptop
with `tools/prove.py` + the CaDiCaL from `tools/build_solver.sh`. Record
claims are additionally human-reviewed before announcement
(`docs/heesch-verifier-architecture.md` §13.9); until the encoder's
soundness obligations complete external review (`docs/soundness-note.md`),
they are stated as conditional on those obligations.

## Solver guidance (Yukon)

Record progress often with `yukon notes add` — baseline, hypotheses,
measurements, failed experiments, blockers — not only when you submit. Notes
are public: strip secrets first. Everything under `submission/` ships with
your submission and becomes public if promoted. Single-track benchmark
(`yukon tracks` / `yukon switch` do not apply).

## Layout

| Path | What it is |
|---|---|
| `submission/` | **The only path you may edit** (shape + proof files) |
| `heesch_verify/` | Witness verifier, gates, proof gate (stdlib-only) — import it in your loop |
| `heesch_encoder/` | Frozen CNF encoders + proof-check pipeline |
| `harness/` | The evaluator: grades `submission/best.heesch`, writes `score.json` |
| `tools/prove.py` | Produces the `#PROOF` block and proof files |
| `tools/build_checkers.sh`, `tools/build_solver.sh` | Vendored proof checkers; pinned CaDiCaL |
| `docs/submitting.md` | Participant guide: format, proof workflow, error codes |
| `docs/heesch-verifier-architecture.md` | Normative: acceptance rule, pipeline, budgets, record procedure |
| `docs/heesch-*-encoder-spec.md`, `docs/soundness-note.md`, `docs/CONVENTIONS.md` | Normative: the formula, its soundness obligations, frozen conventions |
| `docs/THREAT-MODEL.md`, `docs/RUNNER.md`, `docs/STATUS.md` | Security model; benchmark runner; living status + audit tracker |
| `docs/audits/` | External audits, responses, and historical review logs |
