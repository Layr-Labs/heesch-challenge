# Verifier status — audit tracker and open items

A living document: where every external-audit finding stands and what is
still open. Update the relevant row in the same commit that changes the
behaviour. What the verifier *does* is specified once, in
`heesch-verifier-architecture.md` (acceptance rule §2.2, pipeline §7/§13,
budgets/profiles §13.5, record procedure §13.9) — this file does not
duplicate it.

Last updated: 2026-08-20 (Plans 1–3 landed; documentation restructured).

## 1. Snapshot

- Acceptance is fail-closed; a scored entry is a proven non-tiler; the
  harness never executes participant code. Confirmed by the 2026-08-19
  external audit: no false-acceptance route found.
- The record path runs **in-harness** on Blacksmith's
  `blacksmith-32vcpu-ubuntu-2404` runner (128 GB / 1.5 TB, `RUNNER.md`):
  record band `(16,8) (20,7) (50,4) (100,3)
  (200,2)` — every `Hc = 5` certificate to 20 cells, `Hc = 6` to 16 —
  measured in `ml-feasibility.md`; guarded end-to-end by
  `.github/workflows/record-e2e.yml`.
- Record claims are worded *"accepted by the revision-2 verifier and its
  checked UNSAT proof, conditional on the stated encoder soundness
  obligations"* until the external M1–M9 review (below) is filed.

## 2. Audit tracker — 2026-08-19 update audit (`docs/audits/2026-08-19-update-audit.md`)

Formal response: `docs/audits/2026-08-19-update-audit-response.md`.
Status values: FIXED `<commit>` · OPEN · ACCEPTED (with reason).

| # | Finding | Severity | Status | Where | Test |
|---|---|---|---|---|---|
| H1 | Automatic record path excludes the legitimate `Hc = 5, Hh = 6` case; `record_eligible` required exactness | High | FIXED `fd254c4` (classification), `05b055a` (band plumbing), `81082cc`/`49d4125` (measured; bands widened), `2bee047`… (resource profiles + record runner: **in-harness**). Remaining: runner creation + `measure.yml` (§3) | `harness/verify.py::_record_eligible`, `heesch_verify/profile.py`, `heesch_verify/proofgate.py`, `heesch_encoder/proofcheck/pipeline.py`, architecture §2.3/§13.5/§13.9 | `tests/test_record_flag.py`, `tests/test_profile.py`, `tests/test_proof_gate.py` (band tests), `record-e2e.yml` |
| H2 | `tools/prove.py --out` escapes the submission dir / overwrites `best.heesch`; shared temp dir; no cleanup | High | FIXED `0c4b08d` | `tools/prove.py`, `heesch_verify/parse.py::validate_proof_basename` | `tests/test_prove_cli.py` |
| M3 | Non-ASCII core data crashes the gate | Medium | FIXED `db45315` | `heesch_encoder/proofcheck/core.py` | `tests/test_core_proof.py::test_non_ascii_core_*` |
| M4 | Declared proof format not enforced; false provenance | Medium | FIXED `556134e` | `ProofSubmission.declared_format`, `Result.proof_format_detected` | `tests/test_proof_gate.py::test_declared_format_must_match_detected` |
| M5 | 600 s "encoding" alarm covered the checkers too | Medium | FIXED `191121e` (+ portable deadline `4eb3532`) | `heesch_encoder/proofcheck/guard.py`, `pipeline.check_proof_v2` | `tests/encoder/test_ml_proof_pipeline.py::test_encode_*` |
| M6 | Proof bytes materialised before the CNF digest check (spec said the reverse) | Medium | ACCEPTED — code order kept, spec corrected `191121e`: bounded decompression precedes the expensive regeneration by design; bytes never parsed/checked before the digest matches | architecture §13.3 step 4, THREAT-MODEL A-3 | `test_wrong_cnf_digest_rejected_before_checkers` |
| M7 | Non-executable checker passes preflight then crashes | Medium | FIXED `db45315` | `checkers.checker_problem` | `tests/encoder/test_checker_verdicts.py`, `tests/test_proof_gate.py::test_non_executable_checkers_reject_closed` |
| M8 | README miscounts the `Hc = 4` polyhexes | Medium | FIXED `05b055a` (six: 11, 13, 15, 15, 16, 17 — verified against Kaplan's table) | `README.md` | — |
| M9 | "Essentially unexplored" band began at the census cutoff | Medium | FIXED `05b055a` | `README.md` | — |
| L10 | Size caps disagreed across docs | Low | FIXED `33c66f7`; caps are per-profile since `2bee047` | architecture §13.5 | — |
| L11 | README grammar omitted the `core` line | Low | FIXED `05b055a` | `README.md` | — |
| L12 | rev-2 manifest records a stale checker policy | Low | FIXED `9a87535` (code-checked addendum; frozen manifest untouched) | `heesch_encoder/revisions/rev-2-addendum.json` | `test_revision_freeze.py::test_rev2_addendum_matches_code` |
| L13 | `defect_board_enabled` disagreed with scoring | Low | FIXED `33c66f7` (flag live, on by default, honoured by scalar + boards) | `heesch_verify/score.py` | `tests/test_score_store.py::test_defect_enabled_flag_gates_the_fraction` |
| L14 | Stale values in the 2026-08-16 response | Low | FIXED `33c66f7` | `docs/audits/2026-08-16-comparative-audit-response.md` | — |
| L15 | CakeML heap comment vs code | Low | FIXED `db45315` | `heesch_encoder/proofcheck/checkers.py` | — |
| TB | Encoder soundness (M1/M2/M4/M5/M9) needs independent mathematical review | Trust boundary | **OPEN** — external; procedure + reviewer brief + filing format in `soundness-note.md` / `docs/reviews/`; conditional record wording until filed | `docs/soundness-note.md` | round-trip + 46/46 exact-case suites (empirical) |

The 2026-08-16 comparative audit's findings (two criticals) were closed by
`a58e13b`/`4f2634b`; detail in `docs/audits/2026-08-16-comparative-audit-response.md`.

## 2a. Independent re-verification, 2026-08-20

The six headline items of the external audit were re-verified
adversarially against the code. Verdicts, with what remains:

| Audit item | Verdict | Remaining |
|---|---|---|
| `prove.py --out` escape/clobber | FIXED | The hidden `--worker` self-exec mode now refuses to overwrite any existing file (open mode `x`, tested); nothing remains. |
| `Hc = 5, Hh = 6` passes the limits | FIXED to 20 cells (record profile) | 21+ cells and `(20, 8)` still go through the maintainer path (§3.2); the record path has not yet run on the real runner (§3.1). |
| Malformed input → crash, not rejection | FIXED | Write-side `OSError` during proof/core materialisation and the CNF scratch copy now reject with `RESOURCE_EXCEEDED` (ENOSPC/EDQUOT) or `PROOF_FILE_INVALID`; `--check-proof` reports I/O errors as JSON; the parser enforces ASCII integers (`-?[0-9]+` — Unicode digits, `1_0`, `+1` reject). |
| Proof-format metadata recorded incorrectly | FIXED | Declared-vs-detected enforced before any checker; both recorded. |
| Documented timeout policy ≠ implementation | FIXED | The §13.5 table matches `profile.py` exactly; the stale comments in `proofgate.py` / `profile.py` / `checkers.py` / `benchmark.yml` are corrected; the gate now passes the profile's deadline as the pipeline timeout ceiling, removing the latent 3600 s clip. |
| Encoder soundness externally reviewed | OPEN (unchanged) | Procedure + reviewer packet ready; zero reviews filed (row TB). |

## 3. Open items (all outside the repository)

1. **Install the Blacksmith GitHub App** for this repo (app.blacksmith.sh —
   5-minute admin step, `RUNNER.md`), then dispatch:
   `benchmark.yml` on the baseline (preflight must pass;
   `resource_profile: record` in score.json) → `record-e2e.yml` (the
   acceptance test: an `F(S,7)` proof scored in-harness) → `measure.yml`
   for the `ml-feasibility.md` shapes at `m = 7/8`.
2. **Band completion:** one 20-cell-hex-scale `F(S,8)` measurement on the
   Blacksmith runner (128 GB — memory is no longer the constraint) admits
   `(20, 8)`; until then `Hc = 6, Hh = 7` at 17–20 cells goes through the
   maintainer path of architecture §13.9.
3. **External M1–M9 review** (`soundness-note.md`): gates record
   *announcements*, not scoring; drop the conditional wording in the same
   commit that files the first review.

## 4. How to verify

```
python -m pytest -q                                   # full suite
python -m compileall -q heesch_verify heesch_encoder harness tools
```
CI: `.github/workflows/ci.yml` (Ubuntu + Windows, real checkers on Linux);
`record-e2e.yml` and `measure.yml` on the record runner.
