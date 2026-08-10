# Heesch Challenge

Find unmarked polyforms with record Heesch numbers. The class record for
unmarked polyforms is **Hc = 4** (Kaplan 2022, exhaustive to 19-ominoes /
17-hexes / 24-iamonds); **5 has never been exhibited by anyone**, and the
20–200 cell band is essentially unexplored. A verified 5 here is a research
result, not a benchmark score.

An optimization benchmark on the Yukon platform (Eigen / Layr-Labs). Format-
compatible with Epoch AI's FrontierMath Heesch challenge, so results
cross-submit.

## The task

Submit a shape and a witness patch proving its Heesch number lower bound:
`submission/best.heesch` in heesch-sat's text format (see below). Your
search program lives in `submission/` too, but it is an inert artifact —
**scoring never executes participant code**. The verifier re-derives every
claim from the shape file alone, in milliseconds, so run it locally in your
inner loop:

```python
from heesch_verify import verify_witness
outcome = verify_witness(open("submission/best.heesch").read())
```

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
```

`P = 1` when `hh == hc`; `P = 2` when `hh == hc + 1` (second patch may have
holes in its outermost corona). Limits: ≤ 200 cells, span_x + span_y ≤ 29.
`heesch_verify` CLI: `python -m heesch_verify submission/best.heesch`;
`--emit-epoch out.txt` writes an Epoch-compatible copy (defect block
stripped).

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
codes (`PATCH_GAP`, `PATCH_OVERLAP`, `XFORM_NOT_SYMMETRY`, ... ) — parse
them in your search loop; they are API.

## Rules that will reject your submission

- **Plane-tiler screening** (`GATE_IS_TILER`) is constructive, in two layers:
  boundary-word factorization criteria (squares: translation, half-turn,
  quarter-turn; hexes: translation, half-turn) prove tilings of any size,
  and exhaustive known-tiler tables cover every polyomino ≤ 8 cells, every
  polyhex ≤ 6, and every polyiamond ≤ 9. A large tiler outside both layers
  can hold a lower-bound entry — the claim `Hc ≥ k` is mathematically true
  even for tilers — but it is hollow, is purged when identified, and can
  never reach the record tier: record-tier promotion requires a
  machine-checked proof that simultaneously establishes non-tilerhood
  (`PENDING_GATE` policy, architecture spec §2.2–2.3).
- The tile must be edge-connected and hole-free; every inner corona must be
  simply connected; transforms must be genuine grid symmetries (det ±1 is
  not enough — shears are rejected).
- Record-tier and exactness claims additionally require a machine-checkable
  UNSAT proof (DRAT/LRAT) that no (k+1)-corona exists, generated against the
  frozen CNF encoder (`heesch_encoder/`, epoch v1) and validated by two
  independent checkers. One proof settles `Hc = Hh = k` exactly AND
  non-tilerhood. See `docs/soundness-note.md`.

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
| `heesch_verify/` | The witness verifier (stdlib-only) — import it in your loop |
| `heesch_encoder/` | Frozen CNF encoder + proof pipeline (record tier) |
| `harness/` | Yukon evaluator: grades `submission/best.heesch`, writes root `score.json` |
| `submission/` | **The only path you may edit** |
| `docs/CONVENTIONS.md` | The frozen geometry conventions (epoch v1) |
| `tests/` | Calibration, adversarial, metamorphic, fuzz, encoder round-trip suites |
