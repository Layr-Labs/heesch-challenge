# Response to the 2026-08-19 update audit

> Historical record (2026-08-19); superseded by `docs/STATUS.md`. File
> references may be stale.

Audit: `2026-08-19-update-audit.md` (external; reviewed commit `4f2634b`,
2026-08-18). Response date: 2026-08-19. Every finding is listed with what
changed, where, and how it is tested; the running state of each row is kept
in `docs/STATUS.md` §2 (update that table, not this file, when something
moves). Commits: `0c4b08d` … `4eb3532` on `master`; CI run 32292386753
green on Ubuntu/Windows × Python 3.11/3.12 with the real `cake_lpr`.

## Summary

The audit confirmed the two 2026-08-16 criticals closed and found no route
by which a tiler is accepted. Its remaining findings are false-negative,
availability, provenance and operator-safety issues; all fifteen are now
either fixed, accepted with a written justification, or (the one genuinely
external item — mathematical review of M1–M9) turned into a recorded
procedure with an interim wording for record claims. The fail-closed
acceptance rule is unchanged.

## Findings

### High 1 — the automatic record path excludes the legitimate `Hc = 5, Hh = 6` case — CLOSED
- **Was:** `record_eligible` required `exact`; no band admitted `m = 7`;
  docs said "an `Hc = 5` certificate is `F(S,6)`" unconditionally.
- **Now:** `record_eligible = non_tiler_evidence == proof and hc_verified >= 5`
  (`harness/verify.py::_record_eligible`) — a checked finite upper bound on
  `Hh` plus a verified 5-corona beats the known 4 whatever the exact value
  (`Hc ∈ {Hh−1, Hh}`); new `record_exact = record_eligible and exact`;
  `verified_claim` states the certified bounds. Band selection is a
  parameter, not a constant: `ProofCarryingGate(band=)`,
  `check_proof_v2(enforce_band=)`, `python -m heesch_verify --check-proof
  --band {harness,encoder,none}`, `tools/prove.py --band …`; the harness has
  no switch (no env var — `python -I` does not strip env). `F(S,7)` for the
  Kaplan `Hc = 4` 11-hex was measured (187 s encode, 3.1 GB RSS, 36.5 M
  clauses, UNSAT 227 s, core LRAT 18 MB xz) and `(12, 7)` added to the
  encoder band; the in-harness band stays `(12, 6)` until the same cycle is
  timed on the runner (`docs/ml-feasibility.md`). Wording corrected
  everywhere (`F(S,6)` iff `Hh = 5`, `F(S,7)` iff `Hh = 6`); §13.9 names the
  concrete out-of-band commands.
- **Tests:** `tests/test_record_flag.py`; `tests/test_proof_gate.py::
  test_gate_band_*`, `::test_named_bands`,
  `::test_check_proof_v2_enforce_band_false_reaches_the_encoder`,
  `::test_cli_check_proof_matches_harness`.

### High 2 — `tools/prove.py --out` can escape the submission directory or destroy the input — CLOSED
- **Now:** `--out` (and the core name) validated before any work by the
  parser's own rule (`heesch_verify/parse.py::validate_proof_basename`,
  `validate_core_basename`), resolved-parent check, `--force` required to
  overwrite; no silent lrat→drat fallback with an explicit `--out`; all
  intermediates in `tempfile.TemporaryDirectory(prefix=".prove-", dir=dest)`
  (cleaned on every exit path); proof, core and shape installed by
  `os.replace` only after `parse_submission(new_text)` accepts the block.
- **Tests:** `tests/test_prove_cli.py` (escape, clobber, suffix, hidden/`-`
  names, `--force`, failed solver leaves nothing, happy path, SAT path).

### Medium 3 — non-ASCII core data crashes the proof gate — CLOSED
- `parse_core_file` maps `UnicodeDecodeError`/`OSError` to
  `CoreError("GATE_PROOF_INVALID")`; pipeline second net.
  `HEESCH_CAKE_HEAP_MB=abc` no longer raises. Tests:
  `tests/test_core_proof.py::test_non_ascii_core_*`,
  `::test_unreadable_core_is_structured_rejection`,
  `::test_non_ascii_core_rejected_through_pipeline`.

### Medium 4 — declared proof format not enforced; false provenance — CLOSED
- `ProofSubmission.declared_format` compared with the sniffed class
  (`GATE_PROOF_INVALID` before any checker); `format_detected` /
  `proof_format_detected` recorded next to the declared format. Test:
  `tests/test_proof_gate.py::test_declared_format_must_match_detected`.

### Medium 5 — the 600 s "encoding" alarm covers the checkers too — CLOSED
- Guard moved to `heesch_encoder/proofcheck/guard.py` and applied to the
  encoder call only (clipped to the budget's remaining time); checkers are
  bounded solely by `CheckBudget` (600/900/300 s, 1500 s overall for the
  proof stage, constructed before the gate). A portable monotonic deadline
  inside `encode_multilevel_stream` covers platforms without `SIGALRM`.
  Docs §13.3/§13.5, THREAT-MODEL A-3/A-4, `ml-feasibility.md` state the true
  budget. Tests: `tests/encoder/test_ml_proof_pipeline.py::
  test_encode_timeout_is_resource_exceeded`,
  `::test_encode_guard_does_not_cover_checkers`,
  `::test_encode_limit_is_clipped_to_budget_deadline`,
  `::test_portable_encode_deadline_without_sigalrm`;
  `tests/test_proof_gate.py::test_checker_cap_is_the_checkers_own_budget`.

### Medium 6 — proof bytes materialised before the CNF digest check — ACCEPTED, spec corrected
- The code order is kept deliberately: decompressing/hashing the payload is
  bounded (≤ 48 MiB stored → ≤ 1 GiB on scratch disk, lzma memlimit
  256 MiB) and comes after the level/preflight/band rejections, whereas
  regenerating `F(S,m)` costs up to 600 s and GBs of scratch — encoding
  first would make a bogus digest *more* expensive for the server. The bytes
  are never parsed, sniffed or passed to a checker before the digest matches.
  `pipeline.py` docstring, architecture §13.3 step 4 and THREAT-MODEL A-3
  now say exactly this.

### Medium 7 — a non-executable checker passes preflight and then crashes — CLOSED
- `checkers.checker_problem` (regular file + `X_OK`) used by the gate's
  preflight and by `_run`; spawn-time `OSError` → `CHECKER_MISSING` →
  `CHECKER_UNAVAILABLE`. Tests: `tests/encoder/test_checker_verdicts.py::
  test_non_executable_checker_*`, `::test_directory_named_like_a_checker_*`,
  `::test_spawn_oserror_is_missing`;
  `tests/test_proof_gate.py::test_non_executable_checkers_reject_closed`.

### Medium 8 — README miscounts the known `Hc = 4` polyhexes — CLOSED
- Six polyhexes (11, 13, 15, 15, 16, 17) and one 20-iamond; verified against
  Kaplan's Table `tab:hnh` (arXiv source) — the 17-hex row has one `Hc = 4`
  entry.

### Medium 9 — "essentially unexplored" band begins too early — CLOSED
- README distinguishes the embedded exact census (≤ 10/8/12) from Kaplan's
  exhaustive search (≤ 19/17/24) and calls only the tail beyond 19/17/24
  broadly unexplored.

### Low 10 — proof-size caps disagree — CLOSED
- 1 GiB decompressed everywhere (README, THREAT-MODEL C7/A-4, architecture
  §13.3/§14), with the disk implication stated.

### Low 11 — README grammar omits the `core` line — CLOSED

### Low 12 — rev-2 manifest records a stale checker policy — CLOSED
- The frozen manifest stays byte-identical (pinned);
  `heesch_encoder/revisions/rev-2-addendum.json` carries the enforced checker
  policy and the current measured band, loaded by
  `manifest.load_revision_addendum(2)` and checked against the code by
  `tests/encoder/test_revision_freeze.py::test_rev2_addendum_matches_code`.

### Low 13 — `defect_board_enabled` disagrees with actual scoring — CLOSED
- The flag is live and on by default: `yukon_score` and both board keys
  honour `Result.defect_enabled`, so the emitted flag and the scalar agree.
  Architecture §9.2.8/§15 updated. Tests: `tests/test_score_store.py::
  test_defect_enabled_flag_gates_the_fraction`,
  `tests/test_harness.py::test_defect_block_scores_gradient`.

### Low 14 — historical response text has stale values — CLOSED
- 64 MiB → 128 MiB (with the date it changed); `tier: record` → the schema
  values, with the correction noted in place.

### Low 15 — CakeML heap comment vs implementation — CLOSED
- Comment says 85 %, clamped to [1, 12] GB; non-numeric override ignored.

### Trust boundary — encoder soundness (M1/M2/M4/M5/M9) needs independent review — OPEN, procedure recorded
- `docs/soundness-note.md` "External review of M1–M9 — procedure and
  status": what a reviewer confirms, where each argument lives, what
  mechanical evidence exists, and how the outcome is filed
  (`docs/reviews/<date>-<reviewer>.md`). Until then every record claim is
  worded "accepted by the revision-2 verifier and its checked UNSAT proof,
  conditional on the stated encoder soundness obligations".

## What is honestly still open

1. External mathematical review of M1/M2/M4/M5/M9 (above).
2. Timing the `F(S,7)` cycle on the benchmark runner before `(12, 7)`
   enters the in-harness band (`docs/STATUS.md` §3).
3. The 6-hex census divergence and the other §15 open questions of the
   architecture document, unchanged by this audit.

## Reproduction

```
python -m pytest -q                                   # 535 passed, 8 skipped (macOS, checkers built)
python -m pytest -q tests/test_prove_cli.py tests/test_record_flag.py \
    tests/test_proof_gate.py tests/test_core_proof.py \
    tests/encoder/test_checker_verdicts.py tests/encoder/test_ml_proof_pipeline.py \
    tests/encoder/test_revision_freeze.py tests/test_score_store.py
python tools/prove.py submission/best.heesch --out ../escaped.lrat.xz   # error before any work
python tools/prove.py submission/best.heesch --out best.heesch          # error before any work
python tools/ml_feasibility.py --shape hex11-kaplan-hc4hh4 --m 7 --budget 3600
```
