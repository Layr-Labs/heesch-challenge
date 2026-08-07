# Soundness note — heesch-encoder/v1

The encoder is the entire trust boundary of the exactness claim: a DRAT/LRAT
proof certifies that one specific CNF is unsatisfiable, and nothing in the
proof, the checker, or the solver says anything about whether that CNF
faithfully encodes the geometry. This note states the obligations (encoder
spec §7) with their arguments; each has a test in `tests/encoder/`.

**Status: DRAFT — requires external review before the first record-tier
promotion (spec §13.9). The ProofCarryingGate remains disabled until then.**

## ⚠ E8 (found in implementation review): the per-patch quantifier gap

**The spec's central inference is unsound as stated for k ≥ 1.** The formula
`F(S, P_k)` (encoder spec §3.1) is parametrized by ONE submitted patch.
UNSAT of `F` proves "this particular `P_k` admits no corona `k+1`" — but
`Hh >= k+1` requires only that SOME hole-free k-patch extends, and patches
are not interchangeable (corona search genuinely backtracks across patch
choices; that is why heesch-sat encodes ALL levels in a single formula).
So a checked UNSAT proof does NOT establish `Hh <= k`, and by the same
argument does not establish non-tilerhood, except in one case:

- **k = 0 is sound**: `P_0` is the tile itself, unique up to the motions the
  formula already quantifies over. UNSAT of `F(S, P_0)` proves `Hh = 0`.

Consequences until fixed:
1. The ProofCarryingGate must not promote exactness records for k >= 1 from
   single-level proofs. (It is already disabled wholesale.)
2. The fix is a **multi-level encoder** — variables for placements at every
   level 1..k+1 with level-adjacency constraints (touch level i−1, not
   i−2), Kaplan-style — whose UNSAT genuinely quantifies over all patches.
   **Fully specified in `heesch-multilevel-encoder-spec.md` (workspace root)
   as heesch-encoder/v2**: weak-configuration relaxation (Hc <= Hh <= W),
   obligations M1–M9, weak-gap measurement plan, feasibility gates, build
   order. Budgeted as a project, not a patch.
3. The witness/lower-bound path is entirely unaffected.

This is exactly the class of defect the external-review requirement exists
to catch; it must be resolved in the spec before any exactness claim ships.

### E8 resolution status (2026-08-07): heesch-encoder/v2 BUILT

The multilevel encoder is implemented (`heesch_encoder/multilevel/`,
epoch-2.json) per `heesch-multilevel-encoder-spec.md`, with all M-obligation
suites green:

- M1 per-level universe completeness: brute-force list equality across all
  three grids (`test_ml_universe_m1.py`).
- M3/M4/M6/M7: model↔geometry round trips against the hole-agnostic Stage 5
  oracle, label-equality checks, geometric cross-counts, window-vs-family-5
  structural test (`test_ml_roundtrip.py`).
- M9 determinism: hash-seed-randomized subprocess goldens
  (`test_ml_determinism.py`); §9.6 v1-continuity at m=1 over the whole
  corpus (`test_ml_continuity.py`).
- **§9.4 calibration: weak gap = 0/46.** Every corpus shape with known exact
  Heesch values is UNSAT at F(S, k+1) — 46 machine-proven exactness
  reproductions (docs/ml-weak-gap.md). B = 0 empirically suffices on all
  measured real shapes.
- Census results: the v2 encoder CLOSED the octomino-8 census (the last
  non-tiler proven Hc=Hh=1 by F(S,2) UNSAT) and proved the three known
  6-hex non-tilers exactly Hc=Hh=1. One 6-hex remains open: proven
  non-tiler with W<=2 and Hc∈{1,2}, in tension with heesch-sat's README
  example ("1 with Hc=2") — under arbitration by a current heesch-sat run
  (see tests/corpus/MANIFEST.json).
- Feasibility band measured and frozen in epoch-2 (docs/ml-feasibility.md).

**Still required before the first record-tier promotion: external review of
this note and the M1–M9 arguments.** The ProofCarryingGate remains disabled;
`check_proof_v2` is wired and negative-suite-tested.

## The claim

For tile `S`, verified patch `P_k` (coronas 0..k, hole-free), and the formula
`F(S, P_k)` produced by this encoder:

- witness ⇒ `Hc >= k` (geometry verifier, architecture §7)
- UNSAT of `F` ⇒ no hole-allowed corona `k+1` exists ⇒ `Hh <= k`
- `Hc <= Hh` and (for non-tilers) `Hh <= Hc + 1` ⇒ **`Hc = Hh = k` exactly**,
  and since a plane-tiler has coronas at every level, `S` is not a tiler.

## E1 — universe completeness (the false-record obligation)

**Claim.** `U` contains every legal corona-(k+1) placement.

**Argument.** A legal corona-(k+1) copy `T·S` touches `P_k` under the frozen
contact relation and does not overlap it. Touching without overlap means some
cell of `T·S` is a contact-neighbour of a cell of `P_k` and not itself in
`P_k`; that is, `cells(T·S) ∩ R ≠ ∅` where `R = contact_neighbors(P_k) \ P_k`.
The enumeration (`placements.enumerate_universe`) iterates every point-group
element `M` and every pair (tile cell `c`, required cell `h`), forming the
translation `t = h − M(c)`. For the legal placement above, choose `c` with
`M(c) + t ∈ R`: the pair (`c`, that R-cell) generates exactly `t`. Hence every
legal placement is generated, then kept by the membership predicate
(`in_universe`), which restates §3.1 verbatim. ∎

No halo-radius arithmetic is involved — the enumeration is direct, so there
is no off-by-one to get wrong. If `U` were incomplete, UNSAT would mean "no
corona among the placements generated", which is not a theorem about the
shape; this is the failure direction that produces false records. Tested by
brute force over an oversized region with margin-band saturation
(`test_universe_e1.py`).

## E2 — equisatisfiability, up to projection

`F`'s variables are `x_p` for `p ∈ U` plus, for cells whose cover exceeds the
frozen AMO threshold (20), Sinz sequential auxiliaries. The auxiliaries are
functionally determined by the `x` variables (`amo.aux_assignment` computes
the canonical extension `s_i = OR(x_1..x_i)`), so `F` is satisfiable iff a
legal hole-allowed corona exists, and the model ↔ geometry correspondence is
stated **up to projection onto the `x` variables**. Tested:
`test_amo_dimacs.py::test_sequential_amo_exact_model_count` (exact model
counts per group) and the E3/E4 round trips.

## E3 / E4 — the two directions

- E3 (over-permissive detector): every SAT model projects to a placement set
  the geometry verifier's standalone Stage 5 corona check accepts
  (hole-allowed). `test_roundtrip.py::test_e3_*`.
- E4 (over-restrictive detector — the false-record direction): every
  oracle-legal corona satisfies `F` under the canonical aux extension,
  checked with a pure-Python clause evaluator, no solver in the loop.
  `test_roundtrip.py::test_e4_*`, including a geometric cross-count.

## E5 — one contact relation

`R` and `touches` in the encoder ARE `heesch_verify.patch.required_set` and
`heesch_verify.patch.touches`, called with the same threaded `Contact`
object the verifier uses (architecture §11.1). There is no second adjacency
implementation; `tests/test_contact_threading.py` and the AST lint enforce
this structurally.

## E6 — deterministic regeneration

Byte-identical DIMACS across hosts, architectures, Python versions, and
randomized `PYTHONHASHSEED` (the specific test that catches accidental set
iteration). Canonical orders live only in `ordering.py`; the emission path
passes an AST lint forbidding unordered iteration; fresh-subprocess digests
against committed goldens run in the CI matrix. `test_determinism.py`,
`test_no_unordered_iteration.py`, `test_epoch_freeze.py`.

## E7 — `Hc <= Hh <= Hc + 1` for non-tilers

`Hc <= Hh` is immediate (a hole-free corona is a hole-allowed corona).
`Hh <= Hc + 1`: given a hole-allowed patch with coronas `1..m`, coronas
`1..m−1` enclose no holes (holes are permitted only in the outermost layer),
so the same patch truncated to `m−1` coronas is a hole-free witness, giving
`Hc >= m − 1 = Hh − 1`.

**Citation status: OPEN.** This one-line argument assumes the definitional
convention that only the outermost corona may contain holes (architecture
§11, matching Kaplan's `Hc`/`Hh`). Kaplan 2022 ("Heesch numbers of unmarked
polyforms", arXiv:2105.09438) uses exactly these definitions and observes
`Hh ∈ {Hc, Hc+1}`; before the first record promotion, either locate a citable
statement with proof in the literature or have the argument above reviewed
with the rest of this note (encoder spec §14 Q2).

## Deliberately absent (spec §4.5)

No symmetry breaking, no implied clauses, no preprocessing. Every one is an
opportunity to change the solution set; the solver's own preprocessing is
covered by its proof.

## Frozen constants

See `heesch_encoder/epoch/epoch-1.json`. Any change to the placement
universe, variable ordering, clause schema, emission order, contact
relation, or AMO threshold is `heesch-encoder/v2` and a new epoch: historical
proofs stay valid against their recorded version, never re-checked against a
new encoder, never silently migrated. Bug fixes are not exempt.
