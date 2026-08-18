# Heesch Challenge

Find unmarked polyforms with record Heesch numbers — and prove them.

**The record.** For unmarked polyominoes, polyhexes and polyiamonds the
largest known Heesch number is **Hc = 4** (Kaplan 2022, "Heesch Numbers of
Unmarked Polyforms", exhaustive to 19-ominoes / 17-hexes / 24-iamonds:
[arXiv:2105.09438](https://arxiv.org/abs/2105.09438), data at
[cs.uwaterloo.ca/~csk/heesch](https://cs.uwaterloo.ca/~csk/heesch/)). Every
known Hc = 4 example is small: five polyhexes of 11, 13, 15, 15 and 16 cells
and one 20-iamond; no polyomino up to 19 cells exceeds Hc = 3 (two 17-ominoes).
No unmarked polyomino, polyhex or polyiamond with **Hc ≥ 5** is documented in
that exhaustive search or in the literature reviewed for this benchmark.
(Higher values are known outside this class: Heesch number 5 for *marked*
polyforms, and Bašić's general planar figure with Heesch number 6,
[PMC7812982](https://pmc.ncbi.nlm.nih.gov/articles/PMC7812982/).) The band
above the census — 11–200 cells for ominoes, 9–200 for hexes, 13–200 for
iamonds — is essentially unexplored. A **proof-backed** Hc = 5 here is a
research result, not a benchmark score.

An optimization benchmark on the Yukon platform (Eigen / Layr-Labs).
Format-compatible with Epoch AI's FrontierMath Heesch challenge (the
`--emit-epoch` export), so results cross-submit.

## The rule in one paragraph

Submit a shape and a witness patch; the verifier independently re-derives
the lower bound `Hc ≥ k` from your patch. **The submission scores only if
the shape is also proven not to tile the plane** — a tiler has infinitely
many coronas, so a lower bound alone is not a Heesch number. Two proofs are
accepted: the shape is inside Kaplan's complete census (polyominoes ≤ 10
cells, polyhexes ≤ 8, polyiamonds ≤ 12 — every hole-free shape there is
decided exactly, tilers rejected, non-tilers scored with their published
values), or the submission carries a **machine-checked UNSAT proof** of the
multilevel formula `F(S, m)` (a `#PROOF` block naming a DRAT/LRAT file;
`tools/prove.py` makes one). Everything else is rejected — no hollow entries,
no pending state. See `docs/heesch-verifier-architecture.md` §2.2.

## The task

Put `submission/best.heesch` in heesch-sat's text format (below). Your search
program lives in `submission/` too, but it is an inert artifact — **scoring
never executes participant code**. The verifier independently validates the
supplied finite witness under bounded resources (typically well under a
second; the corona work budget caps adversarial patches at ~15 s), so run it
in your inner loop:

```python
from heesch_verify import verify_witness
outcome = verify_witness(open("submission/best.heesch").read())
```

Then, unless the shape is inside the census, produce the non-tiler proof:

```bash
pip install -e '.[prove]'            # python-sat (CaDiCaL); the harness never needs it
bash tools/build_checkers.sh         # drat-trim / lrat-check (+ cake_lpr on x86-64 Linux)
python tools/prove.py submission/best.heesch --check
```

`prove.py` encodes `F(S, m)` for `m = hh + 1` with the same encoder the
harness uses (streamed to disk), solves it in a worker process with proof
logging (trying several solvers until drat-trim verifies the DRAT), and writes
`submission/proof.lrat.xz` (the trimmed LRAT, ids relative to the core) plus
`submission/core.txt.xz` (the few percent of the formula's clauses the proof
actually uses — the harness checks each one is a clause of its own
regenerated formula and hands the checkers only those) and the `#PROOF`
block; `--check` runs the harness's own gate on the result. If `F(S, m)` is SAT the shape may have a deeper corona than your
witness shows (raise the witness, or `--m` higher) — or it tiles.

## File format (heesch-sat, adopted verbatim)

```
O x1 y1 x2 y2 ... xn yn      # grid: O square, H hex, I iamond; occupied cells
~ hc hh P                    # claimed Heesch numbers; P = patch count
N                            # placements in patch 1
level <a,b,c,d,e,f>          # x' = a·x+b·y+c, y' = d·x+e·y+f; level 0 = center
...
#DEFECT k+1 u_hc u_hh r      # OPTIONAL partial-corona block (see Scoring)
M
k+1 <a,b,c,d,e,f>
...
#PROOF 1                     # OPTIONAL non-tiler proof; must be last (see Rules)
encoder heesch-encoder/v2 2 <m>
cnf <cnf_sha256> <num_vars> <num_clauses>
file <basename> <drat|lrat> <none|xz> <payload_sha256>
```

`P = 1` when `hh == hc`; `P = 2` when `hh == hc + 1` (second patch may have
holes in its outermost corona). Limits: ≤ 200 cells, `span_x + span_y ≤ 29`,
≤ 20 000 placements per patch; proof file ≤ 48 MiB stored / 256 MiB
decompressed. `heesch_verify` CLI: `python -m heesch_verify
submission/best.heesch` (`--check-proof` also runs the proof gate;
`--emit-epoch out.txt` writes an Epoch-compatible copy with both optional
blocks stripped).

## Scoring

`score = hc_verified + progress toward the next corona`, where progress
comes from the optional `#DEFECT` block: place partial corona-(k+1) tiles
and the verifier counts the cells of the required set you FAILED to cover
(plus enclosed pockets). Covering more cells lowers the defect and raises
the score; the fractional part is capped below 1, so only a complete
verified corona rolls the integer over. **The score is not a Heesch number**
— the Heesch number is always an integer and is reported separately in
`metrics.hc_verified`.

The defect gradient is the intended progress channel between integer
records: 47 uncovered → 31 → 12 → 0 is four promotions on the same shape.

Claims are checked lower-bound style: if your patch establishes less than
you claimed, the verified weaker claim is accepted and recorded (the
discrepancy is noted). Structural errors reject with stable machine-readable
codes (`PATCH_GAP`, `PATCH_OVERLAP`, `XFORM_NOT_SYMMETRY`,
`GATE_INCONCLUSIVE`, `PROOF_LEVEL_INCONSISTENT`, ...) — parse them in your
search loop; they are API (`docs/heesch-verifier-architecture.md` §8).

`score.json` records how non-tilerhood was proven and what is exact:
`non_tiler_evidence` (`census` | `proof`), `tier` (`lower_bound` |
`exact_proof` — the latter only when a checked proof pins `Hc = Hh = k`),
`census_hc/census_hh` (Kaplan's published values, census shapes only),
`proof_m`, `proof_cnf_digest`, `proof_checkers`, `hh_exact`, `exact`
(`Hc = Hh = k` established), and `record_eligible` (exact, proof-backed,
`hc ≥ 5`). Only `hc_verified` is a Heesch number.

## Rules that will reject your submission

- **Not proven a non-tiler** (`GATE_INCONCLUSIVE`). Outside the census the
  gate returns `TILER` only on a constructive proof (a boundary-word
  factorization — squares: translation, half-turn, quarter-turn; hexes and
  iamonds: translation, half-turn — or a periodic tiling), never
  `NON_TILER`; so every out-of-census shape needs a `#PROOF` block. This is
  the exact guarantee: every tiler inside the census is rejected
  (`GATE_IS_TILER`, `tiler:census`); outside it, tilers with a recognised
  factorization are rejected as tilers and **all other shapes are rejected
  unless a checked UNSAT proof is supplied** — and, under the encoder's
  soundness obligations (M1/M2/M4, `docs/soundness-note.md`), no such proof
  exists for a tiler.
- **The proof does not check.** The harness regenerates `F(S, m)` from the
  shape line, matches the digest and header, verifies the proof file's
  sha256, and requires **two** independent VERIFIED verdicts, one from the
  formally-verified `cake_lpr` (DRAT: `drat-trim` → `cake_lpr`; LRAT:
  `cake_lpr` → `lrat-check`). `m` must be `≥ hh + 1`
  (`PROOF_LEVEL_INCONSISTENT`); the size must be inside the in-harness band
  (≤ 12 cells `m ≤ 6`, ≤ 20 `m ≤ 5`, ≤ 50 `m ≤ 3`, ≤ 100 `m ≤ 2`, else
  `RESOURCE_EXCEEDED` — every known Hc = 4 shape's exactness proof `F(S,5)`
  fits; an `Hc ≥ 5` certificate `F(S,6)` is producible for shapes up to
  12 cells (measured: ~2 min to encode, ~3 min to solve, 25 MB xz LRAT) and
  is checked in-band because the checkers only load the proof's core clauses
  (see `docs/heesch-verifier-architecture.md` §13.3 5b; without a core list
  the formally-verified checker needs > 6 GB and the standard 8 GB runner
  answers `RESOURCE_EXCEEDED`, routing the entry to the out-of-band record
  procedure, §13.9);
  a proof block that is present but broken rejects even a census shape.
  `m = hh + 1` makes the value exact; larger `m` certifies non-tilerhood
  with the lower bound only.
- The tile must be edge-connected and hole-free; every inner corona must be
  simply connected; transforms must be genuine grid symmetries (det ±1 is
  not enough — shears are rejected).
- A census shape whose witness is deeper than Kaplan's published value is
  `CENSUS_CONTRADICTION` — that would mean the verifier or the census is
  wrong, and it is never scored.

Record claims (`record_eligible`) are machine-checked but additionally
reviewed by the maintainers before being announced
(`docs/heesch-verifier-architecture.md` §13.9); the soundness theorem and
its obligations are in `docs/soundness-note.md`.

## Solver guidance

Record progress often with `yukon notes add` — at the baseline, each new
hypothesis, meaningful measurements, failed experiments, and blockers, not
only when you submit. Notes are public: strip secrets and private data
before uploading. Everything under `submission/` ships with your submission
and becomes public if promoted.

This is a schema v1 (single-track) benchmark — no tracks; `yukon tracks` /
`yukon switch` do not apply.

## Layout

| Path | What it is |
|---|---|
| `heesch_verify/` | The witness verifier, gates and proof gate (stdlib-only) — import it in your loop |
| `heesch_encoder/` | Frozen CNF encoders (v1 single-level, v2 multilevel = the proof formula) + proof pipeline |
| `harness/` | Yukon evaluator: grades `submission/best.heesch`, writes root `score.json` |
| `submission/` | **The only path you may edit** (shape file + proof file) |
| `tools/prove.py` | Produces the `#PROOF` block and proof file for a submission |
| `tools/build_checkers.sh` | Builds the vendored proof checkers into `tools/bin` |
| `docs/heesch-verifier-architecture.md` | The acceptance rule, pipeline, error codes, record fields |
| `docs/heesch-cnf-encoder-spec.md`, `docs/heesch-multilevel-encoder-spec.md` | The encoders and their soundness obligations |
| `docs/THREAT-MODEL.md`, `docs/CONVENTIONS.md`, `docs/soundness-note.md` | Threat model, frozen conventions (revision v1), the soundness theorems |
| `docs/audits/` | External audits and our responses |
| `tests/` | Calibration, census, adversarial, metamorphic, fuzz, encoder round-trip, proof e2e suites |
