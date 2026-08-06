# Frozen conventions — epoch v1

Every one of these changes the answer (architecture spec §11). They were
derived from Kaplan's heesch-sat source (see `tools/NOTES-kaplan.md` for the
transcription) and are re-confirmed by the calibration corpus; they are
written into every result record. Changing any of them is a new epoch and
all prior results must be re-verified.

| Convention | Frozen value | Source |
|---|---|---|
| Contact relation | **Boundary point** (share ≥1 boundary point, incl. corners) | heesch-sat: corona adjacency is border-cell-on-vertex-halo (`cloud.h`); §10 calibration |
| Reflections | Allowed (separate board if ever banned) | Kaplan free polyforms |
| Corona mode | Hc (hole-free) primary; Hh computed alongside | spec §11 |
| Inner-corona holes | Never permitted, either mode | heesch-sat Hc/Hh semantics |
| Tile itself | Must be hole-free (topological disk) | spec §11; holed heptomino rejects |
| Central transform | Need not be identity | spec §11 |
| Hole test | Padded-bbox flood fill of the complement, edge adjacency | spec §7 Stage 2 (heesch-sat's halo-connectivity definition is differentially tested as equivalent) |
| Span | Extent (max − min + 1) per axis in grid coordinates; span_x + span_y ≤ 29 | Epoch limit, adopted verbatim (bitmap-size workaround) |
| Cell cap | ≤ 200 cells | Epoch limit |
| Placement cap | 20 000 per patch (RESOURCE_EXCEEDED beyond, requeueable) | resource bound |
| Corona level cap | 64 (resource bound, far above the search cap of 12) | resource bound |

## Grid encodings (transcribed verbatim from heesch-sat)

- **O** (polyomino): cells (x, y); D4, 8 orientations in frozen order; edge
  neighbours 4, contact neighbours 8.
- **H** (polyhex): axial (q, r); D6, 12 orientations; edge and point contact
  coincide (6 neighbours) — verified in `hexgrid.h`, not assumed.
- **I** (polyiamond): Kaplan's x-mod-3 encoding — NOT a parity bit. Valid
  cells: x ≡ y ≡ 0 (mod 3) (up triangle) or x ≡ y ≡ 1 (mod 3) (down).
  Legal translations ≡ (0,0) mod 3 componentwise. Six of the twelve
  orientations carry affine offset (1, 1). Edge neighbours 3, contact
  neighbours 12, both parity-dependent.

Symmetry membership for a placement is affine-aware everywhere: the linear
part must match a frozen orientation AND the residual translation must be
lattice-legal. On O/H the second condition is vacuous; one code path covers
all grids. det = ±1 alone is never sufficient (shears).

## Non-tiler gate coverage (v1)

`IsohedralGate` proves TILER constructively via boundary-word
factorizations: Beauquier–Nivat translation, Conway half-turn, and
Langerman–Winslow quarter-turn forms. Reflection forms (L–W types 4–7) are
not yet enabled — each ships only after differential validation against
heesch-sat classifications, because a wrong TILER verdict rejects a
legitimate submission. The gate never returns NON_TILER: anisohedral tilers
exist, so failed criteria prove nothing (INCONCLUSIVE). Boundary words
longer than 160 edges are not tested (criteria are O(n³)); such shapes fall
through to INCONCLUSIVE and the record tier's proof requirement.
