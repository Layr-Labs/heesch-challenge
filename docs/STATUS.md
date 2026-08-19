# Verifier status — implementation and audit tracker

A living document: what the verifier does today (the true values, kept in
step with the code) and where every external-audit finding stands. Update
the relevant row in the same commit that changes the behaviour.

Last updated: 2026-08-19 (Plans 1 and 2 of the 2026-08-19 audit response
landed; formal response: `docs/audits/2026-08-19-update-audit-response.md`).

## 1. Current implementation (one screen)

**Acceptance rule (fail-closed, `harness/verify.py`).** A submission scores
only when its shape is *proven* not to tile the plane:
- `TILER` (constructive: census membership, boundary-word criteria, bounded
  toroidal exact cover) → `GATE_IS_TILER`;
- `NON_TILER` by the embedded Kaplan 2022 census (complete for polyominoes
  ≤ 10, polyhexes ≤ 8, polyiamonds ≤ 12; `heesch_verify/known_nontilers.json`,
  3 943 shapes) → scores with `non_tiler_evidence=census`; a witness deeper
  than the published value is `CENSUS_CONTRADICTION`;
- `INCONCLUSIVE` + a verified `#PROOF` block → scores with
  `non_tiler_evidence=proof`; `INCONCLUSIVE` without one → `GATE_INCONCLUSIVE`;
- any present-but-failing `#PROOF` or `#DEFECT` block rejects with its code.

**Witness verification (`heesch_verify/`).** Independently re-derives levels,
contact, surround, holes and symmetry validity from the submitted placements;
limits: ≤ 200 cells, `span_x + span_y ≤ 29`, ≤ 20 000 placements per patch,
corona work budget 8 000 000 cell·levels, shape file ≤ 2 MiB, symlinks /
non-regular files refused.

**Proof path (`heesch_verify/proofgate.py` → `heesch_encoder/proofcheck/`).**
`F(S, m)` UNSAT ⇒ `Hh ≤ m − 1` ⇒ finite non-tiler (multilevel encoder,
revision 2; `docs/heesch-multilevel-encoder-spec.md`, `docs/soundness-note.md`).
Order: level rule `m ≥ hh + 1` → checker preflight (regular, executable
files) → band → proof/core materialised to scratch (≤ 48 MiB stored,
≤ 1 GiB payload, lzma memlimit 256 MiB, sha256 = declared) → regenerate
`F(S, m)` (streamed; encode guard 600 s on the encoder call only, clipped to
the budget) → CNF digest + header match → argv guard → size gate → format
sniff, **declared format must equal the sniffed class** → optional core
subset (exact membership in F) → checkers at record tier: two independent
VERIFIED verdicts, one of them `cake_lpr` (DRAT: `drat-trim` → `cake_lpr`;
LRAT: `cake_lpr` → `lrat-check`). `CheckBudget`: drat-trim 600 s /
cake_lpr 900 s / lrat-check 300 s, 1500 s overall for the whole proof stage
(built before the gate runs) — those are the `standard` profile's values;
the `record` profile's are in the next paragraph. Encoder feasibility band
`((12,8),(20,7),(50,4),(100,3),(200,2))`.

**Record path — in-harness (Plan 3, 2026-08-19).** The benchmark job runs on
a dedicated self-hosted runner (`docs/RUNNER.md`: ≥ 8 vCPU, 64 GB, 200 GB
NVMe, 240-min job, label `heesch-record`, fail-loud preflight). Every
proof-path budget comes from `heesch_verify/profile.py`, selected by the
machine (`record` iff MemAvailable ≥ 56 GiB and scratch ≥ 150 GiB, else
`standard`; `resource_profile` in `score.json`). The `record` band
`(12,8) (20,7) (50,4) (100,3) (200,2)` admits `F(S,7)` — the `Hc = 5, Hh = 6`
certificate — for every record-candidate size and `F(S,8)` to 12 cells;
encode guard 3600 s, checker deadline 9000 s, payload 8 GiB, stored 200 MiB
(`maxSubmissionBytes` 512 MiB), core 32 M clauses. Participants produce the
proof with `tools/prove.py` + an external CaDiCaL (`tools/build_solver.sh`,
DRAT streams to disk). `record-e2e.yml` scores an `F(S,7)` proof in-harness
on every run; `measure.yml` times the cycle on the runner. Beyond the record
band (> 20 cells at `m ≥ 5`, `(20, 8)` until measured) the harness still
answers `RESOURCE_EXCEEDED` and the maintainers run the identical code path
with `--profile record --band encoder|none`, then widen the band by
measurement (architecture §13.9).

**Record flags (`score.json` metrics).** `record_eligible` = proof-backed
non-tiler with `hc_verified ≥ 5` (record-breaking whatever the exact value,
since `Hc ∈ {Hh − 1, Hh}`); `record_exact` = `record_eligible and exact`;
`exact` = `Hc = Hh = hc` pinned (`m = hh + 1`, `hc = hh`); `tier` ∈
`{lower_bound, exact_proof}`; `proof_format` (declared) and
`proof_format_detected` (sniffed). Every record claim is additionally reviewed
by hand before announcement; until the encoder's soundness obligations
M1/M2/M4/M5/M9 have been externally reviewed, a record is described as
*"accepted by the revision-2 verifier and its checked UNSAT proof,
conditional on the stated encoder soundness obligations"*.

**Participant tooling.** `tools/prove.py` (encode → solve with proof logging →
drat-trim self-check → core extraction → atomic install of proof, core and
`#PROOF` block; `--out` validated before any work; private temp dir removed
on every exit path), `python -m heesch_verify` (verify, `--emit-epoch`,
`--check-proof`), `tools/ml_feasibility.py` (`--shape NAME|FILE --m M` counts).

**Not in scope / not claimed.** No harness-side execution of participant code;
no census beyond 10/8/12 cells; no automatic promotion of out-of-band records.

## 2. Audit tracker — 2026-08-19 update audit (`docs/audits/2026-08-19-update-audit.md`)

Status values: FIXED `<commit>` · OPEN · PLAN 2 · ACCEPTED (with reason).

| # | Finding | Severity | Status | Where | Test |
|---|---|---|---|---|---|
| H1 | Automatic record path excludes the legitimate `Hc = 5, Hh = 6` case; `record_eligible` required exactness | High | FIXED `fd254c4` (classification), `05b055a` (band plumbing), `81082cc` (`F(S,7)` measured), **Plan 3 (`2bee047`…): in-harness** — resource profiles + dedicated record runner; the `record` band admits `F(S,7)` to 20 cells / `F(S,8)` to 12; `record-e2e.yml` is the regression guard. Remaining: runner registration + `measure.yml` timings (§4) | `harness/verify.py::_record_eligible`, `heesch_verify/result.py`, `heesch_verify/proofgate.py` (`in_band`, `named_band`, `ProofCarryingGate(band=)`), `heesch_encoder/proofcheck/pipeline.py` (`enforce_band`), `heesch_verify/cli.py --band`, `tools/prove.py --band`, docs §2.3/§13.9, multilevel spec §10.2a | `tests/test_record_flag.py`; `tests/test_proof_gate.py::test_gate_band_*`, `::test_named_bands`, `::test_check_proof_v2_enforce_band_false_reaches_the_encoder`, `::test_cli_check_proof_matches_harness` |
| H2 | `tools/prove.py --out` escapes the submission dir / overwrites `best.heesch`; shared `.prove-tmp`; no cleanup on failure | High | FIXED `0c4b08d` | `tools/prove.py` (validate before work, `TemporaryDirectory(dir=dest)`, atomic install after `parse_submission`), `heesch_verify/parse.py::validate_proof_basename/validate_core_basename` | `tests/test_prove_cli.py` |
| M3 | Non-ASCII core data crashes the gate (UnicodeDecodeError) | Medium | FIXED `db45315` | `heesch_encoder/proofcheck/core.py::parse_core_file` (decode/IO → `CoreError GATE_PROOF_INVALID`), pipeline second net | `tests/test_core_proof.py::test_non_ascii_core_*`, `::test_unreadable_core_is_structured_rejection` |
| M4 | Declared proof format not enforced; false provenance (`format: drat` for an LRAT) | Medium | FIXED `556134e` | `ProofSubmission.declared_format`, `ProofOutcome.detected_format`, `ProofVerdict.detected_format`, `Result.proof_format_detected` | `tests/test_proof_gate.py::test_declared_format_must_match_detected` |
| M5 | 600 s "encoding" alarm covered the checkers too | Medium | FIXED `191121e` | `heesch_encoder/proofcheck/guard.py`, `pipeline.check_proof_v2(encode_timeout_s=)` (encoder call only, clipped to the budget), docs §13.3/§13.5, THREAT-MODEL A-3/A-4 | `tests/encoder/test_ml_proof_pipeline.py::test_encode_timeout_*`, `::test_encode_guard_does_not_cover_checkers`, `tests/test_proof_gate.py::test_checker_cap_is_the_checkers_own_budget` |
| M6 | Proof bytes materialised before the CNF digest is checked (spec said the reverse) | Medium | ACCEPTED — code order kept, spec corrected and justified `191121e`: the bounded decompression (≤ 48 MiB → ≤ 1 GiB, streamed to disk) precedes the expensive regeneration (≤ 600 s, GBs of scratch); bytes are never parsed/checked before the digest matches | `pipeline.py` docstring, architecture §13.3 step 4, THREAT-MODEL A-3 | existing ordering tests (`test_wrong_cnf_digest_rejected_before_checkers`) |
| M7 | Non-executable checker passes preflight then crashes | Medium | FIXED `db45315` | `checkers.checker_problem` (regular + `X_OK`) used by preflight and `_run`; spawn `OSError` → `CHECKER_MISSING` | `tests/encoder/test_checker_verdicts.py::test_non_executable_checker_*`, `::test_directory_named_like_a_checker_*`, `::test_spawn_oserror_is_missing`, `tests/test_proof_gate.py::test_non_executable_checkers_reject_closed` |
| M8 | README miscounts the `Hc = 4` polyhexes (five → six; 17-hex omitted) | Medium | FIXED `05b055a` (verified against Kaplan's Table `tab:hnh`: sizes 11, 13, 15, 15, 16, 17) | `README.md` | — |
| M9 | "Essentially unexplored" band started at the census cutoff, not the exhaustive-search cutoff | Medium | FIXED `05b055a` | `README.md` (embedded census ≤ 10/8/12 vs published exhaustive ≤ 19/17/24) | — |
| L10 | Proof-size caps disagree (256 MiB in docs vs 1 GiB in code) | Low | FIXED `33c66f7` (1 GiB everywhere, disk implication stated) | `README.md`, `docs/THREAT-MODEL.md` C7/A-4, architecture §13.3/§14 | — |
| L11 | README grammar omits the optional `core` line | Low | FIXED `05b055a` | `README.md` | — |
| L12 | rev-2 manifest records a stale checker policy (`cake_lpr-or-lrat-check`) | Low | FIXED `9a87535` (code-checked `rev-2-addendum.json`; frozen manifest untouched) | `heesch_encoder/revisions/rev-2-addendum.json`, `manifest.load_revision_addendum` | `tests/encoder/test_revision_freeze.py::test_rev2_addendum_matches_code` |
| L13 | `defect_board_enabled` disagrees with actual scoring | Low | FIXED `33c66f7` (flag live, on by default; `yukon_score` + board keys honour it) | `heesch_verify/witness.py`, `heesch_verify/score.py`, `heesch_verify/result.py`, architecture §9.2.8/§15 | `tests/test_score_store.py::test_defect_enabled_flag_gates_the_fraction`, `tests/test_harness.py::test_defect_block_scores_gradient` |
| L14 | Historical response text has stale values (64 MiB; `tier: record`) | Low | FIXED `33c66f7` (corrected in place, dated) | `docs/audits/2026-08-16-comparative-audit-response.md` | — |
| L15 | CakeML heap comment (70 %) vs code (85 %) | Low | FIXED `db45315` (comment now says 85 %, clamped to [1, 12] GB) | `heesch_encoder/proofcheck/checkers.py` | — |
| TB | Encoder soundness (M1/M2/M4/M5/M9) needs independent mathematical review | Trust boundary | OPEN — external review; procedure, reviewer brief and filing format recorded (`docs/soundness-note.md`, `docs/reviews/`); until a review is filed every record claim carries the conditional wording in §1 | `docs/soundness-note.md`, `docs/reviews/README.md`, multilevel spec §8 | round-trip + 46/46 exact-case tests (empirical) |

## 3. Audit tracker — 2026-08-16 comparative audit

Closed by `a58e13b` / `4f2634b`; per-finding detail in
`docs/audits/2026-08-16-comparative-audit-response.md`. The 2026-08-19 audit
confirms both criticals closed (fail-closed acceptance; enforced proof path)
and found no false-acceptance route.

## 4. Measurements pending / in progress

- `F(S,7)` for the Kaplan `Hc = 4` 11-hex: **done 2026-08-19** (laptop).
  `F(S,5..7)` counts for the 13/15/16-hex `Hc = 4` shapes: **done 2026-08-19**
  (`docs/ml-feasibility.md`). These set the `record` profile's band.
- **Pending (needs the runner registered, `docs/RUNNER.md`):** dispatch
  `measure.yml` for 11-hex m=7/8, 13-hex m=7, 16-hex m=7/8 and a 20-iamond
  m=6/7/8 on `heesch-record`; paste the rows into `ml-feasibility.md`; add
  `(20, 8)` to `RECORD.harness_band` (+ `FEASIBILITY_BAND`, addendum,
  tests) iff it fits. Then dispatch `record-e2e.yml` (the acceptance test:
  an `F(S,7)` proof scored in-harness with `resource_profile=record`) and
  `benchmark.yml` on the baseline.

## 5. Plan 2 — done 2026-08-19

1. L10 size-cap wording — `33c66f7`.
2. L12 rev-2 manifest addendum — `9a87535`.
3. L13 `defect_board_enabled` live and honoured by scoring — `33c66f7`.
4. L14 stale values in the 2026-08-16 response — `33c66f7`.
5. `docs/audits/2026-08-19-update-audit-response.md` — this round.
6. External soundness review: procedure + filing format in
   `docs/soundness-note.md` and `docs/reviews/` (the review itself is
   external and still OPEN — see TB above).
7. Portable encode guard (monotonic deadline inside
   `encode_multilevel_stream`) — `4eb3532`.

Plan 3 (2026-08-19, `2bee047`…): record path in-harness — resource profiles,
dedicated runner workflow + preflight + `docs/RUNNER.md`, pipeline scale
fixes, `prove.py --solver-bin` + `tools/build_solver.sh`,
`tools/measure_record_cycle.py`, `measure.yml`, `record-e2e.yml`, docs.
Remaining outside the repository: register the runner (`docs/RUNNER.md`),
run `measure.yml` / `record-e2e.yml` (§4), the external M1–M9 review (TB).

## 6. How to verify

```
python -m pytest -q                                   # full suite
python -m pytest -q tests/test_proof_gate.py tests/test_core_proof.py \
    tests/test_prove_cli.py tests/test_record_flag.py \
    tests/encoder/test_checker_verdicts.py tests/encoder/test_ml_proof_pipeline.py
python -m compileall -q heesch_verify heesch_encoder harness tools
```
CI: `.github/workflows/benchmark.yml` (Linux job builds and uses the real
`cake_lpr`; macOS uses the documented test shim).
