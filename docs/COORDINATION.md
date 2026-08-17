# Eigen / Yukon coordination checklist

## Comparative audit 2026-08-16 — resolution status

See `docs/audits/2026-08-16-comparative-audit-response.md` for the
item-by-item response. Headline changes: the acceptance rule is now
**fail-closed** (a shape scores only when proven a non-tiler — by Kaplan's
complete census for polyominoes ≤ 10 / polyhexes ≤ 8 / polyiamonds ≤ 12, or by
a checked UNSAT proof of `F(S, m)` carried in a `#PROOF` block); the proof
tier is enforced code (`ProofCarryingGate`, checkers built by `setup.sh`,
`tools/prove.py` for participants); the four normative documents cited by the
code now exist under `docs/`; the soundness note is two versioned theorems.
The item 1 residual below ("hollow lower bounds") no longer exists.

## External review 2026-08 — resolution status

1. **[P0] Plane tilers could score** — FIXED: known-tiler tables extended to
   every polyhex ≤ 6 and polyiamond ≤ 9 (census arithmetic vs Kaplan's
   published counts) + hex boundary-word criteria (BN/Conway over the
   6-letter alphabet); monohex reproducer is now a permanent harness test.
   Residual at the time: tilers outside both layers could hold
   true-but-hollow lower bounds — the 2026-08-16 comparative audit showed
   this began at 9-ominoes / 7-hexes / 10-iamonds, not "very large" shapes;
   closed on 2026-08-17 by the fail-closed rule (`GATE_INCONCLUSIVE`) and
   the exact census layer.
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
- Record-tier exactness (ProofCarryingGate) is LIVE and enforced: (a) the
  encoder round-trip suites pass on all three grids, (b) the E8 per-patch
  quantifier gap is resolved by encoder v2 (multilevel `F(S, m)`), which is
  the only proof formula accepted. Still open, and gating record
  *announcements* rather than scoring: (c) external review of the M1–M9
  arguments (docs/soundness-note.md, docs/heesch-multilevel-encoder-spec.md
  §8) and a citable proof of E7. `benchmark.json maxSubmissionBytes` is
  64 MiB to carry proof files (48 MiB cap in the harness); confirm the
  platform ceiling.

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
