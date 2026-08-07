"""v2 clause construction (multilevel spec §5), B = 0.

Frozen emission order (§6 there — deliberately different from v1's; do not
harmonize either direction): family 1 (base coverage, by cell), family 2
(per-cell AMO across levels, by cell then pair), family 4 (adjacency, by
(l, placement)), family 5 (separation, by (l, p, j, q)), family 6 (per-tile
surround, by (l, q, cell)). Family 3 is deliberately absent — implied by
family 2 because same-cellset copies share every cell; family 7 and the cov
auxiliaries do not exist at B = 0.

Emission-path module: sorted containers only; the shared cellset touch graph
comes from universe.touching_cellset_pairs so feasibility counts and emitted
clauses cannot drift.
"""

from __future__ import annotations

from heesch_verify.grids import Contact, Grid
from heesch_verify.patch import contact_neighbors, required_set

from ..amo import AMO_THRESHOLD, pairwise, sequential
from ..ordering import literal_key, sorted_cells
from ..types import AmoGroup
from .types import MLFormula
from .universe import multilevel_universe, touching_cellset_pairs


def build_ml_formula(tile_cells, grid: Grid, contact: Contact, m: int,
                     amo_threshold: int = AMO_THRESHOLD) -> MLFormula:
    tile = frozenset(tile_cells)
    uni = multilevel_universe(tile, grid, contact, m)

    # Variable numbering: concatenated per-level sorted lists (level-major
    # xvar order by construction).
    level_offsets = []
    off = 0
    for lv in uni.levels:
        level_offsets.append(off)
        off += len(lv)
    total_x = off

    # cell -> ascending var list; also the level-1 slice boundary for F1.
    cover: dict = {}
    var_meta = {}  # var -> (level, placement); lookup only
    for li, lv in enumerate(uni.levels):
        for i, p in enumerate(lv):
            v = level_offsets[li] + i + 1
            var_meta[v] = (li + 1, p)
            for c in uni.cells_of[p]:
                cover.setdefault(c, []).append(v)
    for c, vs in cover.items():  # ordered-ok: assertion only, no emission
        assert vs == sorted(vs)

    clauses: list = []
    counts = {"1": 0, "2": 0, "4": 0, "5": 0, "6": 0}

    # ---- family 1: base coverage of R_0 by level-1 placements (W1) ----
    R0 = sorted_cells(required_set(tile, contact))  # ordered-ok: sorted
    lvl1_end = level_offsets[1] if m >= 2 else total_x
    for c in R0:
        vs = tuple(v for v in cover.get(c, ()) if v <= lvl1_end)
        clauses.append(vs)  # empty clause is a real, deliberate artifact
        counts["1"] += 1

    # ---- family 2: per-cell at-most-one across levels ----
    amo_groups: list = []
    next_aux = total_x + 1
    multi = sorted_cells([c for c, vs in cover.items() if len(vs) >= 2])  # ordered-ok: sorted
    for c in multi:
        vs = cover[c]
        if len(vs) <= amo_threshold:
            pcs = pairwise(vs)
            clauses.extend(pcs)
            counts["2"] += len(pcs)
            amo_groups.append(AmoGroup(cell=c, variables=tuple(vs), kind="pairwise"))
        else:
            scs, aux_count = sequential(vs, next_aux)
            clauses.extend(scs)
            counts["2"] += len(scs)
            amo_groups.append(
                AmoGroup(cell=c, variables=tuple(vs), kind="sequential",
                         aux_start=next_aux, aux_count=aux_count)
            )
            next_aux += aux_count

    # Shared geometric touch graph over the union of level cellsets.
    all_sets = sorted({cs for lv in uni.level_cellsets for cs in lv},
                      key=lambda cs: tuple(sorted_cells(cs)))  # ordered-ok: sorted
    set_id = {cs: i for i, cs in enumerate(all_sets)}
    adj: dict = {i: [] for i in range(len(all_sets))}
    for (a, b) in touching_cellset_pairs(all_sets, contact):
        adj[a].append(b)
        adj[b].append(a)
    for i in range(len(all_sets)):
        adj[i] = sorted(adj[i])

    # per level: cellset -> ascending var list of its representatives
    reps: list = []
    for li, lv in enumerate(uni.levels):
        d: dict = {}
        for i, p in enumerate(lv):
            d.setdefault(uni.cells_of[p], []).append(level_offsets[li] + i + 1)
        reps.append(d)

    def _touch_vars(cs: frozenset, level: int) -> list:
        """Vars at `level` whose placements touch cellset cs, ascending."""
        out = []
        for b in adj[set_id[cs]]:
            out.extend(reps[level - 1].get(all_sets[b], ()))
        return sorted(out)

    # ---- family 4: adjacency (W2) ----
    for li in range(1, m):
        lv = uni.levels[li]
        for i, p in enumerate(lv):
            v = level_offsets[li] + i + 1
            below = _touch_vars(uni.cells_of[p], li)  # level li == l-1 (1-indexed)
            clauses.append(tuple([-v] + below))
            counts["4"] += 1

    # ---- family 5: separation (W3) ----
    for li in range(2, m):
        lv = uni.levels[li]
        for i, p in enumerate(lv):
            v = level_offsets[li] + i + 1
            for j in range(1, li):  # levels 1..l-2 (1-indexed j)
                for w in _touch_vars(uni.cells_of[p], j):
                    clauses.append((-v, -w))
                    counts["5"] += 1

    # ---- family 6: per-tile surround (W4) ----
    for li in range(0, m - 1):
        l = li + 1
        lv = uni.levels[li]
        for i, q in enumerate(lv):
            v = level_offsets[li] + i + 1
            halo = sorted_cells(
                contact_neighbors(uni.cells_of[q], contact) - tile
            )  # ordered-ok: sorted
            for h in halo:
                lo, hi = max(1, l - 1), min(m, l + 1)
                window = tuple(
                    w for w in cover.get(h, ())
                    if lo <= var_meta[w][0] <= hi
                )
                clauses.append(tuple([-v] + list(window)))
                counts["6"] += 1

    ordered = tuple(tuple(sorted(cl, key=literal_key)) for cl in clauses)
    return MLFormula(
        m=m,
        num_vars=next_aux - 1,
        clauses=ordered,
        levels=uni.levels,
        level_offsets=tuple(level_offsets),
        amo_groups=tuple(amo_groups),
        required_cells=tuple(R0),
        family_counts=tuple(sorted(counts.items())),
    )
