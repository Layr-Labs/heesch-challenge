# Soundness note — heesch-encoder/v1

The encoder is the entire trust boundary of the exactness claim: a DRAT/LRAT
proof certifies that one specific CNF is unsatisfiable, and nothing in the
proof, the checker, or the solver says anything about whether that CNF
faithfully encodes the geometry. This note states the obligations (encoder
spec §7) with their arguments; each has a test in `tests/encoder/`.

**Status: DRAFT — requires external review before the first record-tier
promotion (spec §13.9). The ProofCarryingGate remains disabled until then.**

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
