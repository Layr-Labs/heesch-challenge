# Heesch verifier — architecture specification

Normative description of what the verifier and the Yukon harness accept, in
what order they check it, and what they record. Section numbers are cited
from code comments and docstrings (`spec §N`, `architecture §N`); keep them
stable. Companion documents: `heesch-cnf-encoder-spec.md` (encoder v1),
`heesch-multilevel-encoder-spec.md` (encoder v2, the enforced proof formula),
`THREAT-MODEL.md`, `CONVENTIONS.md` (the frozen constants), and
`soundness-note.md` (the two soundness theorems and their obligations).

Terminology follows Kaplan 2022 (arXiv:2105.09438): a *corona* is a ring of
copies surrounding the accumulated patch; `Hc` is the largest number of
hole-free coronas, `Hh` allows holes in the outermost corona only;
`Hc <= Hh <= Hc + 1` for non-tilers, and a plane tiler has `Hc = Hh = ∞`.

## 1. Purpose

Grade a participant's claim "shape `S` has Heesch number at least `k`" from a
plain-text file, and admit it to the board only when the claim is *proven*:
the witness proves the lower bound, and the shape's non-tilerhood — without
which "Heesch number" is not finite — is proven by census or by a checked
UNSAT proof. Nothing is trusted from the participant except bytes.

## 2. Jobs and gates

The system is three jobs with one-way dependencies:

- **Job A — witness verifier** (`heesch_verify.witness`, stdlib only): parses
  the file and independently establishes `Hc >= k` (and `Hh >= k'`) from the
  submitted patch. Published to participants; identical code runs server-side.
- **Job B — non-tiler gates** (`heesch_verify.gates`, `heesch_verify.proofgate`):
  decide whether the shape is proven not to tile the plane.
- **Job C — encoder and proof pipeline** (`heesch_encoder`): regenerates the
  CNF a proof refers to and drives the vendored checkers.

Job A never imports B or C. B imports C lazily inside the proof gate only.

### 2.1 Gates

| Gate | Module | Verdicts | Basis |
|---|---|---|---|
| 1 census + constructive criteria | `gates.IsohedralGate` | `NON_TILER` (census), `TILER` (census complement, boundary-word factorization, periodic tiling), `INCONCLUSIVE` | Kaplan 2022's complete non-tiler lists (`known_nontilers.json`, `third_party/kaplan-heesch/PIN`); Beauquier–Nivat / Conway / quarter-turn factorizations; periodic-tiling search |
| 3 proof-carrying | `proofgate.ProofCarryingGate` | `VERIFIED` or a rejection code | machine-checked UNSAT proof of the multilevel `F(S, m)` (§13) |

(Gate 2, a bare SAT-solver triage verdict, was removed: a solver's say-so is
not independently checkable and never influences acceptance.)

Gate 1 semantics are load-bearing. Inside the census (polyominoes `n <= 10`,
polyhexes `n <= 8`, polyiamonds `n <= 12`) every hole-free shape is decided
exactly: listed → `NON_TILER` with the published `Hc/Hh`; unlisted →
`TILER` (Kaplan removed tilers before computing Heesch numbers). Above the
census the gate returns `TILER` only on a constructive proof that a tiling
exists and never returns `NON_TILER` — anisohedral tilers exist, so a failed
criterion proves nothing. Missing criteria (reflection factorization forms,
hex 60°/120° rotation forms) only weaken the constructive filter; under §2.2
they never admit a tiler.

Every gate verdict carries a machine-readable `gate_detail`
(`nontiler:census`, `tiler:census`, `tiler:translation|conway|quarter_turn`,
`tiler:periodic:…`, `unchecked:boundary_error|boundary_length|unsupported_grid`,
`evaluated:no_factorization`).

### 2.2 The acceptance rule (fail closed)

A submission is **accepted and scored** iff

1. the witness verifies (Job A, §7 stages 1–5, and the defect pass if a
   `#DEFECT` block is present), **and**
2. Gate 1 does not return `TILER`, **and**
3. non-tilerhood is **proven** by at least one of
   - `census`: Gate 1 returned `NON_TILER`, or
   - `proof`: the submission carries a `#PROOF` block and Gate 3 returns
     `VERIFIED`, **and**
4. every block present verifies: a `#PROOF` block that fails rejects the
   submission even when the census already proved non-tilerhood (mirrors
   `#DEFECT`), **and**
5. the census tripwire holds: for a census shape, `hc_verified <= census_hc`
   and `hh_verified <= census_hh` (§8 `CENSUS_CONTRADICTION`).

Everything else is `REJECTED` with a stable code, nonzero exit, and no
`score.json`. In particular an `INCONCLUSIVE` shape without a proof is
`GATE_INCONCLUSIVE`. There is no pending state and no "hollow" entry: a
scored entry is a proven non-tiler.

Decision table (after the witness and defect passes):

| Gate 1 | `#PROOF` | Gate 3 | Outcome |
|---|---|---|---|
| `TILER` | any | not run | `GATE_IS_TILER` |
| `NON_TILER` | absent | — | accept, `non_tiler_evidence=census` |
| `NON_TILER` | present | `VERIFIED` | accept, `non_tiler_evidence=proof`, `gate_detail=nontiler:census+proof:v2:m=<m>` |
| `NON_TILER` | present | failure | that failure's code |
| `INCONCLUSIVE` | absent | — | `GATE_INCONCLUSIVE` |
| `INCONCLUSIVE` | present | `VERIFIED` | accept, `non_tiler_evidence=proof` |
| `INCONCLUSIVE` | present | failure | that failure's code |

### 2.3 Tiers, exactness and records

- Census evidence: `census_hc/census_hh` are recorded; `exact` is true iff
  the verified values equal the published ones
  (`hc_verified == census_hc == census_hh == hh_verified`) — exactness that
  rests on Kaplan's published computation (threat model R1).
- Proof evidence: a verified proof of `F(S, m)` proves `Hh <= m - 1` over all
  patches (multilevel spec §2.2). With the verified witness
  `hh_verified = m - 1` the value `Hh` is exact (`hh_exact`); if additionally
  `hc_verified == hh_verified` then `Hc = Hh = k` exactly (`exact`). If
  `hh = hc + 1` and `hh_exact`, `Hc` is undecided between `k` and `k+1`
  (`Status.EXACT_UNDECIDED_HOLE_CASE`).
- `tier = exact_proof` iff `exact` was established by a checked proof;
  every other accepted entry is `tier = lower_bound` (census-backed, or a
  proof at `m > hh + 1` that certifies non-tilerhood without pinning the
  value).
- `record_eligible = exact and non_tiler_evidence == proof and hc_verified >= 5`
  — the machine-checkable precondition for claiming a new class record. A
  record claim additionally requires the human review in §13.9.

The score scalar (§9.2.6) is `hc_verified + fractional defect progress` for
every accepted entry; tier and evidence are metadata for the board, never a
multiplier.

## 3. No participant code

The harness executes nothing under `submission/`. Its inputs are
`submission/best.heesch` (text, ≤ 2 MiB, regular file, no symlinks) and, when
named by a `#PROOF` block, one proof file in the same directory (regular
file, size-capped, optionally xz-compressed with bounded decompression). Both
are hostile data: the shape file is parsed by our verifier, the proof file by
the vendored checkers, all inside the benchmark sandbox (`THREAT-MODEL.md`).
Search programs, notebooks and anything else under `submission/` are inert
artifacts.

## 4. File format

heesch-sat's text format, adopted verbatim, plus two optional trailing blocks:

```
<G> x1 y1 x2 y2 ... xn yn      # grid O/H/I and the tile's cells
~ hc hh P                      # claim; P = 1 (hh == hc) or 2 (hh == hc + 1)
N                              # placement count of patch 1
level <a,b,c,d,e,f>            # x' = a·x + b·y + c,  y' = d·x + e·y + f
...                            # (patch 2 follows if P = 2)
#DEFECT k+1 u_hc u_hh r        # OPTIONAL partial next corona (§9.2.7)
M
k+1 <a,b,c,d,e,f>
...
#PROOF 1                       # OPTIONAL non-tiler proof (§13.2); must be last
encoder heesch-encoder/v2 2 <m>
cnf <cnf_sha256> <num_vars> <num_clauses>
file <basename> <drat|lrat> <none|xz> <payload_sha256>
core <basename> <none|xz> <payload_sha256> <num_clauses>   # optional, lrat only (§13.3 5b)
```

Rules: CRLF and repeated spaces tolerated; markers are exact first tokens
(`#DEFECT`, `#PROOF`); `#DEFECT` precedes `#PROOF`; each block appears at
most once; anything after the last block is `PARSE_SYNTAX` (trailing
garbage); lines ≤ 1 000 000 chars; integers `|v| <= 2^31`; placement counts
≤ 20 000 per patch. `P = 0` only with `hc = 0`. `~` claims are lower-bound
claims: a weaker verified value is accepted and recorded with
`claim_discrepancy` unless `--strict`. `python -m heesch_verify --emit-epoch`
writes the Epoch-compatible file with both optional blocks stripped.

## 5. Stdlib-only rule

`heesch_verify`, `heesch_encoder` and `harness` have no third-party runtime
dependency (hard rule). Solvers (`python-sat`) live only in the `test` and
`prove` extras and in `tools/`; the proof checkers are vendored C/CakeML
sources compiled by `setup.sh` into `tools/bin`.

## 6. Calibration against heesch-sat

Grid encodings, orientation tables and the contact relation are transcribed
from Kaplan's `heesch-sat` (`tools/NOTES-kaplan.md`) and re-confirmed by the
calibration corpus (§10) and by the census table: every corpus witness
verifies at exactly its published value, and every census shape's
`Hc/Hh` in `known_nontilers.json` is Kaplan's published value. Divergences
are recorded, never smoothed over (currently one: the 6-hex
`-2 2 -1 1 0 0 1 0 2 0 2 1`, published `Hc = Hh = 2`; our own capped searches
have found only a 1-corona so far — `tests/corpus/MANIFEST.json`).

## 7. Pipeline

Stages, in order; each rejection is a `VerifyError` with a §8 code.

1. **Parse** (`parse.parse_submission`) — §4 grammar.
2. **Shape validity** (`shape.check_shape`) — non-empty, ≤ 200 cells,
   edge-connected, hole-free (padded-bbox flood fill of the complement, edge
   adjacency — the one hole detector), `span_x + span_y <= 29`.
3. **Canonical form** (`canonical.canonical_digest`) — lexicographic minimum
   over the grid's point group (reflections included), sha256 of
   `grid_id + repr(form)`; plus `symmetry_order`.
4. **Transform validity** (`transform.check_symmetry`) — every placement's
   linear part must be one of the frozen orientations AND its residual
   translation lattice-legal (iamond: `≡ (0,0) mod 3`); `det = ±1` alone is
   never enough (shears are `XFORM_NOT_SYMMETRY`).
5. **Patch legality** (`patch.check_corona`) with the single threaded
   `Contact` (§11.1):
   5a disjointness (`PATCH_OVERLAP`); 5b recompute levels from adjacency —
   submitted labels are never trusted (`PATCH_LEVEL_MISMATCH`,
   `PATCH_ORPHAN_TILE`, exactly one level-0 tile); 5c surround — every
   contact-neighbour cell of the accumulated patch is covered by the next
   level (`PATCH_GAP`); 5d holes — hole-free everywhere for `hc`, outermost
   corona may enclose holes for `hh` (`PATCH_HOLE_IN_CORONA` in strict mode,
   otherwise `hc = hh - 1` is recorded); 5e report what was established.
   The cumulative **corona work budget** (`patch.MAX_CORONA_WORK`, 8 000 000
   cell·levels) bounds 5c/5d on the participant path: a maximal hc = 12
   witness of a 200-cell tile is ~1.2 M, an adversarial 64-level ring patch
   that took ~380 s now stops at ~15 s with `RESOURCE_EXCEEDED`.
6. **Non-tiler rule** — Gate 1, then the defect pass, then Gate 3 if a
   `#PROOF` block is present, then §2.2. (Harness only.)
7. **Record** — `Result` fields (§9) written to `score.json`; the append-only
   `store.RecordStore` keeps the best result per canonical digest for the
   leaderboard service (§9.2.5 ordering).

## 8. Error codes (API)

Codes are stable strings participants parse in their search loops. Every
rejection is `REJECTED: <CODE>: message`, exit 1, no `score.json`.

| Family | Codes |
|---|---|
| Parse | `PARSE_SYNTAX`, `PARSE_COUNT_MISMATCH`, `PARSE_UNKNOWN_GRID` |
| Shape | `SHAPE_EMPTY`, `SHAPE_TOO_LARGE`, `SHAPE_SPAN_EXCEEDED`, `SHAPE_DISCONNECTED`, `SHAPE_HAS_HOLE`, `SHAPE_DUPLICATE_CELL`, `SHAPE_NOT_REGULAR_FILE` (harness) |
| Transform | `XFORM_NOT_SYMMETRY`, `XFORM_REFLECTION_BANNED` |
| Patch | `PATCH_OVERLAP`, `PATCH_LEVEL_MISMATCH`, `PATCH_ORPHAN_TILE`, `PATCH_GAP`, `PATCH_HOLE_IN_CORONA`, `PATCH_NO_CENTRAL_TILE`, `PATCH_MULTIPLE_CENTRAL` |
| Claims | `CLAIM_BELOW_THRESHOLD`, `CLAIM_WEAKER_THAN_STATED` |
| Defect (§9.2) | `DEFECT_XFORM_INVALID`, `DEFECT_TILE_OVERLAP`, `DEFECT_TILE_NOT_TOUCHING`, `DEFECT_TILE_OUT_OF_BAND`, `DEFECT_CLAIM_MISMATCH`, `DEFECT_LEVEL_MISMATCH` |
| Gates (§2.2) | `GATE_IS_TILER`, `GATE_INCONCLUSIVE`, `CENSUS_CONTRADICTION` |
| Proof (§13) | `PROOF_LEVEL_INCONSISTENT`, `CHECKER_UNAVAILABLE`, `PROOF_FILE_INVALID`, `PROOF_FILE_DIGEST_MISMATCH`, `PROOF_CNF_DIGEST_MISMATCH`, `PROOF_HEADER_MISMATCH`, `PROOF_TRUNCATED`, `GATE_PROOF_INVALID` |
| Store / resources | `DUPLICATE`, `RESOURCE_EXCEEDED` |

Non-terminal statuses (`Status`): `PROMOTED`, `SUPERSEDED`,
`EXACT_UNDECIDED_HOLE_CASE`. (`PENDING_GATE` no longer exists: under §2.2 a
gate never leaves a submission pending.)

## 9. Record fields

### 9.1 Base fields
`hc_verified`, `hh_verified`, `cell_count`, `span_x`, `span_y`,
`symmetry_order`, `patch_size`, `grid`, `reflections_used`,
`canonical_digest`, `gate_tier`, `gate_detail` (harness metrics),
`verified_claim` (a sentence stating exactly what was established — never
"minimum defect", never the scalar as a Heesch number), `claim_discrepancy`,
`hc_claimed`, `hh_claimed`, `conventions` (§11).

### 9.2 Defect board
9.2.1 The defect is what a partial corona `k+1` FAILS to cover — cells of the
required set `R = contact_neighbors(P_k) \ P_k` left uncovered (plus enclosed
pockets for `defect_hc`); a gradient participants can descend on one shape.
9.2.2 Claims are lower-bound-shaped: the verifier confirms "a placement with
defect ≤ d exists", never minimality.
9.2.3 Computation: tiles must be legal symmetries, disjoint from `P_k` and
each other, touching `P_k`, inside the band; `defect_hh` = uncovered `R`
cells; `defect_hc` adds enclosed pockets (same flood fill as stages 2/5d).
9.2.4 Fractions are compared exactly (`fractions.Fraction`), never floats.
9.2.5 Board ordering: `(hc_verified, -defect fraction, hh_verified,
-cell_count, -(span_x+span_y), -patch_size)`; an Hc board reads `defect_hc`
only.
9.2.6 The scalar `score = hc_verified + min(1 - defect/required, 0.999999)`
is not a Heesch number and must never be rendered as one; `hc_verified` is.
9.2.7 The `#DEFECT` block grammar is §4; `--emit-epoch` strips it.
9.2.8 Recorded on every submission regardless of the board flag:
`defect_enabled`, `defect_block_present`, `defect_corona_level`, `defect_hc`,
`defect_hh`, `defect_required`, `defect_pocket_cells`, `defect_partial_tiles`,
plus `score_fraction_num/den` in metrics.

### 9.3 Non-tiler evidence (§2.2/§2.3)
`non_tiler_evidence` (`census|proof`), `tier` (`lower_bound|exact_proof`),
`census_hc`, `census_hh` (null unless a census shape), `proof_status`,
`proof_m`, `proof_cnf_digest`, `proof_sha256`, `proof_format` (declared),
`proof_format_detected` (sniffed from the bytes; a disagreement is
`GATE_PROOF_INVALID` before any checker runs),
`proof_checkers` (sorted names of the checkers that returned VERIFIED),
`hh_exact`, `exact`, `record_eligible`. `gate_tier ∈ {nontiler_census,
nontiler_proof}`. Timings are never recorded (determinism).

## 10. Calibration corpus

`tests/corpus/`: heesch-sat-format witnesses for every non-tiler in the
complete small families (7/8-ominoes, 6-hexes, 7/9-iamonds), each verifying
at exactly Kaplan's published `Hc/Hh` in strict mode, plus holed shapes that
must reject. `MANIFEST.json` records population counts and the one open
divergence (§6). The census table extends the same anchor to 3 943 shapes:
`tests/test_census_gate.py` enumerates every free polyform at the census
sizes and asserts zero gate misses and zero false `TILER`s from the
constructive criteria.

## 11. Frozen conventions

`CONVENTIONS.md` is normative: contact relation (boundary point), reflections
allowed, hole rules, tile is a disk, central transform need not be identity,
span/cell/placement/level caps, grid encodings. Every convention is written
into each record (`conventions`); changing any is a new revision.

### 11.1 One contact relation
`R` and `touches` are computed by `heesch_verify.patch.required_set /
touches` from ONE `Contact` object created per run and threaded through the
verifier, the defect pass and both encoders (`tests/test_contact_threading.py`
and the AST lint enforce this structurally). There is no second adjacency
implementation anywhere.

## 12. Test suites

12.1 calibration (`test_calibration.py`, corpus values reproduced; gate never
calls a corpus non-tiler `TILER`); 12.2 negative (`test_negative.py`: each
test mutates a valid witness to isolate one property; fixtures are never
stored); 12.3 metamorphic (`test_metamorphic.py`: invariance under global
symmetry/translation/line order); 12.4 differential
(`test_differential.py` vs `reference_impl.py`); 12.5 defect
(`test_defect.py`); 12.6 record store (`test_score_store.py`); 12.7 fuzz
(`tests/fuzz`); 12.8 harness e2e (`test_harness.py`, `test_gate_detail.py`,
`test_gate_boundary_cap.py`, `test_file_load_hardening.py`,
`test_parser_hygiene.py`, `test_corona_work_budget.py`); 12.9 performance
(`test_perf.py`, p95 < 250 ms). Added 2026-08: `test_census_gate.py` (§10),
`test_parse_proof.py` and `test_proof_gate.py` (§13, real checkers, e2e),
`tests/encoder/*` (encoder spec §9, multilevel spec §9).

## 13. Proof pipeline

### 13.1 Overview
The only accepted proof object is an UNSAT proof (DRAT or LRAT) of the
multilevel formula `F(S, m)` produced by the frozen encoder v2 (revision 2). The
server regenerates `F(S, m)` from the shape line alone — the participant's
CNF is never read — matches its digest and header, then runs the checkers.
Encoder v1's per-patch formula `F(S, P_k)` is not accepted for acceptance
purposes (soundness-note E8: sound only at `k = 0`).

### 13.2 Submission channel
The `#PROOF` block (§4) binds a proof file to the shape: schema version `1`;
`encoder heesch-encoder/v2 2 m` with `1 <= m <= 8`; the regenerated CNF's
sha256 and header counts; the proof file's basename
(`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`, extension matching format and
compression, never `best.heesch`), format `drat|lrat`, compression
`none|xz`, and the sha256 of the *decompressed* payload. The CNF is encoded
from the tile's canonical form (`canonical.canonical_form(cells, grid, True)`)
by both `tools/prove.py` and the harness — that is the digest contract. An
optional `core` line names a clause list — the subset of `F(S, m)` the LRAT
proof refutes, one clause per line, its ids in the LRAT being positions in
that list — so the checkers load only the clauses the proof uses (measured
3.5–12 % of F); this is what makes record-scale proofs checkable in-band
(§13.3 step 5b). `tools/prove.py` produces it by default.

### 13.3 Order of operations (`ProofCarryingGate.check`, then `check_proof_v2`)
1. Level rule: `m >= hh_verified + 1`, else `PROOF_LEVEL_INCONSISTENT`
   (a witness deeper than the proof allows is a contradiction; never
   "corrected").
2. Checker preflight: `drat-trim`, `lrat-check`, `cake_lpr` all present as
   regular files in the checker directory, else `CHECKER_UNAVAILABLE`.
3. Bands: in-harness band `HARNESS_PROOF_BAND = ((12,6),(20,5),(50,3),(100,2))`
   (cells, max m) and the encoder feasibility band
   (`multilevel.api.FEASIBILITY_BAND`, measured policy), else `RESOURCE_EXCEEDED`
   before any encoding; the encoding step is additionally wall-clock guarded
   (600 s → `RESOURCE_EXCEEDED`).
4. Proof file: `lstat`/`open(O_NOFOLLOW)`/`fstat` regular-file discipline,
   stored size ≤ 48 MiB, streamed into scratch (`TMPDIR`) under a fixed safe
   name, xz decompressed with `lzma` (memlimit 256 MiB, decompressed cap
   256 MiB, no trailing data), sha256 compared with the block
   (`PROOF_FILE_INVALID`, `RESOURCE_EXCEEDED`, `PROOF_FILE_DIGEST_MISMATCH`).
5. Regenerate `F(S, m)` (streamed to scratch); digest match
   (`PROOF_CNF_DIGEST_MISMATCH`), header match (`PROOF_HEADER_MISMATCH`), argv
   guard, size gate, format sniff on bounded windows (`GATE_PROOF_INVALID` for
   SAT models/empty/unknown, `PROOF_TRUNCATED`), then checkers.
   5b. **Core subset** (`heesch_encoder/proofcheck/core.py`, LRAT only, when a
   `core` line is present): the submitted clause list is parsed with a strict
   grammar (one clause per line, integers, `0`-terminated, no comments/headers,
   no tautologies), each clause canonicalised (duplicate literals removed,
   encoder literal order — the order F is emitted in), and **every clause must
   be, by exact string equality against F's own streamed DIMACS lines, a
   clause of F**; the checkers then run on a core CNF *we* write from F's own
   lines in the submitter's order under a header naming F's variable count.
   Soundness: a refutation of a subset of F refutes F (every model of F
   satisfies the subset), for RUP and RAT steps alike; the only trust added is
   the exact-membership check, the same class as the digest/header match. Any
   missing clause, count mismatch or grammar deviation rejects
   (`GATE_PROOF_INVALID` / `PROOF_HEADER_MISMATCH`) before a checker runs;
   caps (`CORE_MAX_CLAUSES`, `CORE_MAX_BYTES`) bound the work.
6. Verdict mapping is 1:1 from `ProofStatus` to §8 codes; `VERIFIED` yields
   the §9.3 fields.

### 13.4 Tiers and checkers
The harness always checks at **record tier**: two independent `VERIFIED`
verdicts, one of which must be the formally-verified `cake_lpr`. DRAT:
`drat-trim` (which also emits LRAT) then `cake_lpr` on that LRAT. LRAT:
`cake_lpr` then `lrat-check`. `lrat-check` never substitutes for `cake_lpr`
(it is not formally verified and `N 0 0` vacuously verifies). Verdicts are
line-anchored (`s VERIFIED` / `c VERIFIED` / `s VERIFIED…`); any
`NOT VERIFIED` line forces failure; exit codes are ignored. A missing checker
is `CHECKER_UNAVAILABLE`, never a downgrade. Triage tier (one checker) exists
for library/tests only.

### 13.5 Budgets
`checkers.CheckBudget`: per-checker caps drat-trim 600 s, cake_lpr 900 s,
lrat-check 300 s, overall deadline 1500 s; each spawn gets
`min(cap, deadline - now)`; a non-positive remainder is `RESOURCE_EXCEEDED`
without spawning. Together with the witness stage and the encoding this fits
the 30-minute benchmark job.

### 13.6 Round-trip oracle
`patch.check_corona(..., hole_mode="none")` is the hole-agnostic geometric
oracle the encoder suites use to prove model ↔ geometry correspondence
(encoder spec §9, multilevel spec §9); it is unbudgeted (`max_work=None`)
because it is never on the participant path.

### 13.7 Checker availability
`setup.sh` builds `tools/bin/{drat-trim,lrat-check,cake_lpr}` from
`third_party/` (sha256-pinned sources) and, on x86-64 Linux, fails if any is
missing. The harness locates them via `HEESCH_CHECKER_DIR` or
`<repo>/tools/bin` (it runs from the installed package, so the
package-relative default does not apply). `benchmark.sh` sets
`HEESCH_CHECKER_DIR` inside the sandbox.

### 13.8 Sandbox
The checkers run inside the same bubblewrap/`sandbox-exec` confinement as the
parser: read-only repo bind, writable scratch only (`TMPDIR`), no network, no
capabilities. They read two path arguments and stdin is `/dev/null`.

### 13.9 Record procedure (in-band and out-of-band)

A `record_eligible` entry (exact, proof-backed, `hc_verified >= 5`) is a
machine-checked research claim. Two ways it can arise:

**In-band.** The submission carries the `F(S, k+1)` proof and the harness
verifies it inside the benchmark job (bands in §13.3: an `Hc = 5` certificate
for shapes up to 12 cells is producible and inside the band, but checking it
needs a runner with ≥ 12 GB RAM for `cake_lpr`'s heap — the standard 8 GB
runner answers `RESOURCE_EXCEEDED`; `docs/ml-feasibility.md`). The score is
recorded like any other; the `record_eligible` flag is set from the metrics.

**Out-of-band.** A witness whose shape or depth is outside the in-harness
band cannot score by itself (fail closed: `RESOURCE_EXCEEDED` for the proof,
or `GATE_INCONCLUSIVE` without one). The participant should still submit it,
with `hc_verified` as deep as they can prove, and file the proof (or the
request to produce one) with the maintainers, who:

1. regenerate `F(S, m)` with the frozen encoder revision named in the
   `#PROOF` block, on a machine without the job's memory/time caps
   (`encode_multilevel_stream`, then `check_proof_v2` at record tier with the
   real `cake_lpr`; the exact same code path, only the caps differ);
2. record the outcome — CNF digest, proof sha256, checker verdicts and
   versions — in `docs/records/` next to the shape and witness, and, if
   VERIFIED, promote the entry with `non_tiler_evidence=proof` by re-running
   the harness with the widened band pinned for that submission (the score
   itself is the ordinary `hc_verified + defect` scalar);
3. widen the in-band limits for everyone once the measurement shows the new
   size/depth fits the job (a policy change, not a new encoder revision).

Before **announcing** any record, in-band or out, the maintainers (i)
re-run the proof check out of band, (ii) confirm the encoder revision's
soundness obligations (multilevel spec M1–M9, `soundness-note.md`) have been
externally reviewed for that revision, and (iii) publish the shape, witness,
proof and digests. None of this alters the score.

## 14. Resource bounds

Shape ≤ 200 cells, `span_x + span_y <= 29`; ≤ 20 000 placements per patch;
≤ 64 corona levels; corona work budget 8 000 000 cell·levels; shape file
≤ 2 MiB, proof file ≤ 48 MiB stored / 256 MiB decompressed; boundary-word
caps 410 (square) / 810 (hex, iamond) edges — above the longest legal
boundary; checker budgets §13.5; benchmark job 30 min. Bounds are not frozen
conventions: raising one is not a new revision, but every accepted result stays
valid.

## 15. Open questions

Recorded, not hidden: (1) the 6-hex divergence (§6); (2) whether the
Hh board should be its own track; (3) whether defect-board ranking should be
enabled on the public board (`defect_board_enabled=False` today; the fields
are always recorded); (4) proof feasibility above ~50 cells / m > 2 — the
enforced band is the measured one and is widened as measurements allow — a
policy change, not a new encoder revision; (5) replacing census evidence with
maintainer-generated checked proofs for the small shapes (feasible: F(S,2)/
F(S,3) at ≤ 12 cells solve in seconds), so that every scored entry is
proof-backed rather than census-backed.
