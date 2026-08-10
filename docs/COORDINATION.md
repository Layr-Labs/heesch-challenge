# Eigen / Yukon coordination checklist

## External review 2026-08 — resolution status

1. **[P0] Plane tilers could score** — FIXED: known-tiler tables extended to
   every polyhex ≤ 6 and polyiamond ≤ 9 (census arithmetic vs Kaplan's
   published counts) + hex boundary-word criteria (BN/Conway over the
   6-letter alphabet); monohex reproducer is now a permanent harness test.
   Residual (documented in README/CONVENTIONS): very large tilers outside
   both layers can hold true-but-hollow lower bounds until identified;
   record tier still requires the proof path.
2. **[P2] Stale score survived failed runs** — FIXED: benchmark.sh wipes
   score.json before any fallible work (flock pattern) and the harness
   unlinks it at start; regression test added.
3. **[P2] lrat-check verdicts misread** — FIXED: per-checker line-anchored
   verdict matching (`s VERIFIED` / `c VERIFIED` / `s VERIFIED UNSAT`), with
   the drat-trim `c VERIFIED derivation` false-positive trap tested.
4. **[P2] Non-hermetic workflow** — FIXED: SHA-pinned actions, ubuntu-24.04,
   persist-credentials false, pinned setup-python + setuptools==84.0.0,
   submission-surface check, preflight/diagnostics artifacts, strict jq
   score extraction (ecdsafail/flock template).
Also adopted from the reference challenges: top-level setup.sh/benchmark.sh
invoked by benchmark.json, root score.json, generalized Python discovery
($PYTHON override + version floor), and a bubblewrap/Seatbelt sandbox around
the verify stage (defense-in-depth; our harness executes no competitor code).

## Open decisions to settle with the Yukon team

- `minScoreImprovementBips` is currently **0**: the defect gradient moves in
  single-cell increments, and at hc=4 one cell of a 200-cell required set is
  ~0.5 bips of the scalar — any positive threshold would swallow legitimate
  progress. Confirm Yukon accepts 0, or we quantize the fractional part.
- The scalar in score.json is `hc_verified + defect progress` and is NOT a
  Heesch number; frontend copy must never render it as one (§9.2.6 of the
  architecture doc). The true integers ship in `metrics`.
- Record-tier exactness (ProofCarryingGate) is dark pending (a) the encoder
  round-trip suite passing on hex/iamond calibration data, (b) resolution of
  the E8 per-patch quantifier gap (docs/soundness-note.md) — the exactness
  protocol needs a multi-level encoder revision, and (c) external review of
  the soundness note. The lower-bound board does not wait on any of this.

## Questions for Bartosz (architecture §15, unchanged)

Contact convention (settled: boundary point, from heesch-sat); the ladder
problem; defect-board legitimacy; Hh as its own track; the 20–200 cell band;
machine-checked witness acceptance.

Everything Yukon-side that has to happen before and at import. Mirrors the
process used for TNCOO and the author guide's private-repo path.

- [ ] Create private repo under `Layr-Labs/` (private is required so
      submission PRs are not world-readable mid-competition).
- [ ] Push this challenge repo (default branch = the branch Yukon imports).
- [ ] Install the Yukon GitHub App on the repo:
      - Dev: https://github.com/apps/yukon-eigen/installations/new
      - Prod: https://github.com/apps/yukon-autoresearch/installations/new
- [ ] Invite solvers / org as read collaborators (needed for `yukon clone`;
      Yukon does not mint clone tokens).
- [ ] Verify `benchmark.json` final: name, description, direction,
      `minScoreImprovementBips`, `maxSubmissionBytes`.
- [ ] Verify workflow runs green on `workflow_dispatch` and uploads
      root `score.json` as an artifact (≤ 50 MiB).
- [ ] Contact Yukon team for import; they queue the baseline run and wire
      CLI, database, and frontend.
- [ ] Never merge submission PRs manually — promotion is Yukon's
      fast-forward of the scored commit.
