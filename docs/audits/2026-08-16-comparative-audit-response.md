# Response to the 2026-08-16 comparative audit

Audit: `2026-08-16-comparative-audit.md` (external; reviewed commit
`e50e6ca`, 2026-08-13). Response date: 2026-08-17. Every finding is listed
with what changed, where, and how it is tested. Reproduction commands are at
the end.

## Summary of the change

The audit's central point was correct: the enabled harness scored any shape
whose tiler gate was `INCONCLUSIVE`, so a plane tiler with a valid witness
scored, and the "record tier requires a proof" statement had no executable
counterpart. Both are closed by making the acceptance rule **fail-closed**
and the proof path **enforced**:

- A submission scores only when non-tilerhood is *proven*: by Kaplan 2022's
  complete census (exact for polyominoes ≤ 10, polyhexes ≤ 8, polyiamonds
  ≤ 12) or by a machine-checked UNSAT proof of the multilevel `F(S, m)`
  carried in a new `#PROOF` block. Everything else is `REJECTED:
  GATE_INCONCLUSIVE`. There is no lower-bound board that permits tilers, no
  hollow entry, no pending state.
- The proof path is executable code end to end: parser grammar,
  `ProofCarryingGate` wired into `harness/verify.py`, checkers built by
  `setup.sh` and located inside the sandbox, `tools/prove.py` for
  participants, e2e tests that submit a real proof and score.
- The four normative documents cited by the code now exist; the soundness
  note is two versioned theorems; public claims are rewritten to the exact
  guarantee.

## Findings

### Critical 1 — the enabled scorer does not enforce a finite, non-tiling record — CLOSED
- **Was:** `harness/verify.py` rejected only on `TILER`; `INCONCLUSIVE`
  scored. Reproduced before fixing: the audit's census script gave 89 / 37 /
  79 misses at 9-ominoes / 7-hexes / 10-iamonds, and the 9-omino tiler
  `0 0 … 0 6 1 0 1 3` with an hc = 1 witness scored 1.0 with `gate_detail`
  identical to the honest baseline's.
- **Now:** decision table in `harness/verify.py` (architecture §2.2):
  `TILER` → `GATE_IS_TILER`; `NON_TILER` (census) → score with
  `non_tiler_evidence=census`; `INCONCLUSIVE` + verified proof → score with
  `non_tiler_evidence=proof`; `INCONCLUSIVE` without proof →
  `GATE_INCONCLUSIVE`; any present-but-failing proof → its code; census
  tripwire `CENSUS_CONTRADICTION`.
- **Census layer:** `heesch_verify/known_nontilers.json` (3 943 non-tilers
  with published Hc/Hh; `tools/gen_census_tables.py`; sources pinned in
  `third_party/kaplan-heesch/PIN`; per-size counts asserted). Inside the
  census every hole-free shape is decided; the old known-tiler table
  (503/111/250) is deleted.
- **Tests:** `tests/test_census_gate.py` re-runs the audit's experiment at
  9/10-ominoes, 7/8-hexes, 10/11/12-iamonds — **0 misses**, every listed
  shape `NON_TILER` with its published values, and zero false `TILER` from
  the constructive criteria across all published non-tilers;
  `test_audit_examples_are_now_tilers` pins the three shapes the audit
  named. `tests/test_proof_gate.py::test_inconclusive_without_proof_is_rejected`
  (an 11-omino Kaplan non-tiler above the census is rejected without a
  proof); `tests/test_harness.py::test_tiler_rejected`,
  `test_p0_monohex_tiler_rejected`, `tests/test_gate_boundary_cap.py`.

### Critical 2 — the advertised record-tier proof gate is not operational — CLOSED
- **Was:** `ProofCarryingGate.ENABLED = False`, `check` raised, harness never
  called it, no proof field in the grammar, no proof step in the workflow.
- **Now:** `heesch_verify/parse.py` — `#PROOF` block (schema, encoder/revision,
  m, CNF digest + header, proof file basename/format/compression/payload
  sha256), must be last, exact marker; `heesch_verify/proofgate.py` —
  `ProofCarryingGate.check`: level rule `m ≥ hh + 1`, checker preflight,
  in-harness + revision-2 bands, hardened proof-file materialisation (regular
  file, `O_NOFOLLOW`, size caps, bounded xz), sha256 check, then
  `check_proof_v2` at RECORD tier (two VERIFIED, one `cake_lpr`); mapped 1:1
  to stable codes. `harness/verify.py` calls it (Stage 6). `setup.sh` builds
  `tools/bin/{drat-trim,lrat-check,cake_lpr}`; `benchmark.sh` passes
  `HEESCH_CHECKER_DIR` into the sandbox; the checker path bug for the
  installed package (would have made every proof `CHECKER_UNAVAILABLE`) is
  fixed by threading `bin_dir`. `tools/prove.py` produces the proof and the
  block; `python -m heesch_verify --check-proof` runs the same gate.
  `benchmark.json maxSubmissionBytes` = 64 MiB. Score metrics record
  `proof_m`, `proof_cnf_digest`, `proof_sha256`, `proof_checkers`, `tier`,
  `hh_exact`, `exact`, `record_eligible`.
- **Tests:** `tests/test_parse_proof.py` (38 grammar cases),
  `tests/test_proof_gate.py` (17: level rule, missing checkers, symlink,
  missing file, digest mismatch, xz bomb bounded, trailing data, oversized,
  out-of-band, wrong CNF digest, SAT model, tampered proof, and the positive
  path — a real `F(S,3)` proof for an 11-omino scores through the harness;
  a census octomino with `F(S,2)` scores exact), `tests/encoder/*` (band
  enforcement before encoding, explicit `bin_dir`, budget). On x86-64 Linux
  CI the real `cake_lpr` runs; elsewhere the tests use a labelled shim for
  the control flow only.

### Constructive filter strengthened (audit "recommended combined architecture", fast constructive tiler filters)
- New `heesch_verify/periodic.py`: a deterministic, budget-bounded exact-cover
  search for a periodic (torus) tiling by K ≤ 8 copies in any orientation;
  every hit is re-verified as an exact partition of the torus, so a `TILER`
  verdict stays constructive. Bypassing the census, it catches all 89 / 37 /
  79 tilers the audit reported missed at 9-ominoes / 7-hexes / 10-iamonds
  (`tests/test_periodic.py`), with zero false `TILER`s over the published
  non-tilers (`tests/test_census_gate.py`). Under fail-closed it only improves
  the rejection reason (`GATE_IS_TILER` vs `GATE_INCONCLUSIVE`) for
  anisohedral tilers above the census.

### High 3 — documentation understates the tiler-gate gap — CLOSED
- README, `docs/CONVENTIONS.md`, `docs/COORDINATION.md`, `docs/REVIEW-FIXES.md`
  (dated addendum) now state the exact guarantee in the audit's own words:
  every tiler in the census is rejected; outside it, tilers with a recognised
  factorization are rejected as tilers; **all other shapes are rejected
  unless a checked UNSAT proof is supplied**. "Very large exotic" is gone.

### High 4 — essential proof specifications referenced but absent — CLOSED
- Added `docs/heesch-verifier-architecture.md` (§2.1 gates, §2.2 fail-closed
  rule, §2.3 tiers, §3 no participant code, §4 format, §5 stdlib rule, §7
  pipeline, §8 codes, §9 record fields incl. §9.2.1–9.2.8, §11/§11.1
  conventions, §12 suites, §13 proof pipeline, §14 bounds, §15 open
  questions), `docs/heesch-cnf-encoder-spec.md` (v1: §3 universe, §4 clauses,
  §5–§6 checker semantics and DIMACS, §7 E1–E8, §8 order of operations, §9
  suites, §11 revision freeze, §14 Q2), `docs/heesch-multilevel-encoder-spec.md`
  (v2: §2.2 theorem, §4.2 universes, §5 families, §6 order, §7 model
  self-check, §8 M1–M9 defined, §9 suites, §10.2 band — now enforced, §11
  constants), `docs/THREAT-MODEL.md` (TB1–TB5, C1–C9, A-1–A-4, R1–R5). Every
  code/doc citation resolves to a section that exists.

### High 5 — the soundness note mixes the unsound v1 claim with v2 — CLOSED
- `docs/soundness-note.md` rewritten: Theorem v1 (exactness sound only at
  k = 0; the old inference explicitly withdrawn), Theorem v2 (UNSAT of
  `F(S, m)` ⇒ `Hh ≤ m−1` over all patches, with M1/M2/M4/M5/M9 as
  assumptions), E7 status, and the census divergence record.

### Medium 6 — the record statement needs a precise class qualifier — CLOSED
- README headline uses the audit's recommended wording, cites Kaplan (paper +
  data), Bašić (Heesch number 6, general figure) and marked polyforms
  (Heesch number 5), and adds the sizes of every known Hc = 4 shape (11–20
  cells) from Kaplan's data.

### Medium 7 — "re-derives every claim … in milliseconds" overstates — CLOSED
- README: "independently validates the supplied finite witness under
  bounded resources (typically well under a second; the corona work budget
  caps adversarial patches at ~15 s)".

### Medium 8 — the search domain is narrower than the manifest summary — CLOSED
- `benchmark.json` description states `≤ 200 cells, span_x + span_y ≤ 29`,
  the fail-closed rule, the census bounds, the proof requirement and that the
  score is not a Heesch number.

## The audit's "required before treating the external benchmark as a record verifier"

| # | Requirement | Status |
|---|---|---|
| 1 | Split the boards | Superseded by fail-closed: there is no board that permits tilers. `non_tiler_evidence` (`census` / `proof`) and `tier` (`lower_bound` / `exact_proof`) are recorded on the single board. |
| 2 | Fail closed for record promotion | Done — and for *all* scoring (`GATE_INCONCLUSIVE`). |
| 3 | Integrate the proof path | Done (Critical 2). |
| 4 | Publish the missing specifications | Done (High 4). |
| 5 | Version the soundness theorem | Done (High 5). |
| 6 | Census-regression tests at the first out-of-table sizes | Done — `tests/test_census_gate.py`, at 9/7/10 and the census bounds. |
| 7 | Correct public claims | Done (High 3, Medium 6–8). |

The audit's recommended combined architecture (independent geometry verifier
→ constructive tiler filters → all-level CNF for corona k+1 → UNSAT + checked
proof → `Hc = Hh = k` and non-tiler → record board) is now the enforced
pipeline (architecture §7 stage 6, §13). The remaining component of that
diagram, an independent heesch-sat cross-check, is not part of acceptance
(a solver's verdict is not independently checkable) but Kaplan's published
census — heesch-sat's own output — is the calibration anchor.

## What is honestly still open

- External review of the revision-2 obligations (M1–M9) and a citable proof of
  E7 gate record *announcements*, not scoring (architecture §13.9).
- Proof feasibility: the enforced in-harness band is ≤ 12 cells m ≤ 6,
  ≤ 20 m ≤ 5, ≤ 50 m ≤ 3, ≤ 100 m ≤ 2 (the encoder band adds (50, 4) and
  (200, 2)). Every known Hc = 4 shape's exactness proof `F(S,5)` fits
  (measured: 11-hex 60 s encode / 26 s UNSAT; 20-iamond 173 s encode), and
  an Hc = 5 certificate `F(S,6)` fits for shapes up to 12 cells (11-hex:
  112 s encode at 2.5 GB with the streamed encoder, UNSAT in 157 s, LRAT
  513 MB / 25 MB xz, checked in ~80 s). Larger shapes at m = 6 go through the
  out-of-band record procedure (architecture §13.9). Stated plainly in README
  and the multilevel spec §10.2.
- Census evidence is a trusted published computation, not a proof
  certificate; replacing it with maintainer-generated checked proofs for the
  small shapes is listed as future work (architecture §15, threat model R1).
- One 6-hex divergence with Kaplan's published Hc (soundness note); the
  tripwire makes any over-claim a rejection.

## Reproduction

The audit's census script, unchanged except that the table it needs is now
`known_nontilers.json` (used implicitly by the gate):

```python
import sys; from pathlib import Path
sys.path.insert(0, str(Path.cwd())); sys.path.insert(0, str(Path.cwd() / "tools"))
from polyforms import free_polyforms, parse_kaplan_file
from heesch_verify.canonical import canonical_digest
from heesch_verify.gates import IsohedralGate, Verdict
from heesch_verify.grids import GRIDS
from heesch_verify.shape import holes_of
for gid, size, path in [("O", 9, "09omino_0up.txt"), ("H", 7, "07hex_0up.txt"), ("I", 10, "10iamond_0up.txt")]:
    grid = GRIDS[gid]
    non_tilers = {canonical_digest(c, grid, True) for c, _, _ in parse_kaplan_file(Path(path).read_text())}
    total = holed = tilers = caught = missed = 0
    for cells in free_polyforms(gid, size):
        total += 1
        tile = frozenset(cells)
        if holes_of(tile, grid): holed += 1; continue
        if canonical_digest(cells, grid, True) in non_tilers: continue
        tilers += 1
        verdict, _ = IsohedralGate(grid).check_detailed(tile)
        caught += verdict is Verdict.TILER; missed += verdict is not Verdict.TILER
    print(gid, size, total, holed, len(non_tilers), tilers, caught, missed)
```

Observed after the change (`grid size free holed non-tilers tilers caught missed`):

```
O 9 1285 37 198 1050 1050 0
H 7 333 2 37 294 294 0
I 10 448 4 103 341 341 0
```

Harness on the audit's tiler (`0 0 … 0 6 1 0 1 3`, hc = 1 witness):
`REJECTED: GATE_IS_TILER: shape tiles the plane (tiler:census)`. Harness on
an 11-omino Kaplan non-tiler without a proof: `REJECTED: GATE_INCONCLUSIVE`;
with the `#PROOF` block written by `tools/prove.py --m 3`: `score 1.0`,
`non_tiler_evidence: proof`, `tier: record`. Baseline (7-omino, census):
`score 1.0`, `non_tiler_evidence: census`, `exact: true`.
