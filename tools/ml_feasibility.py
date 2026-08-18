"""v2 feasibility table (multilevel spec §10.2): variable/clause COUNTS for F(S, m)
without building clause objects. This is the Phase B gate — the published
(cells, m) band decision comes from this table.

Usage: python tools/ml_feasibility.py out.md
"""

from __future__ import annotations

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from heesch_encoder.amo import AMO_THRESHOLD  # noqa: E402
from heesch_encoder.multilevel.universe import (  # noqa: E402
    multilevel_universe,
    touching_cellset_pairs,
)
from heesch_verify.grids import GRIDS  # noqa: E402
from heesch_verify.parse import parse_submission  # noqa: E402
from heesch_verify.patch import contact_neighbors, required_set  # noqa: E402

ROW_BUDGET_S = 120.0


def count_formula(tile, grid, contact, m):
    """(vars, aux, per-family clause counts) from universes alone."""
    t0 = time.time()
    uni = multilevel_universe(tile, grid, contact, m)
    if time.time() - t0 > ROW_BUDGET_S:
        raise TimeoutError
    tile_set = frozenset(tile)

    u = [len(lv) for lv in uni.levels]
    n_x = sum(u)

    # multiplicity per (level, cellset) + per-cell cover counts
    mult = []
    cover_count: dict = {}
    for lv in uni.levels:
        d: dict = {}
        for p in lv:
            cs = uni.cells_of[p]
            d[cs] = d.get(cs, 0) + 1
            for c in cs:
                cover_count[c] = cover_count.get(c, 0) + 1
        mult.append(d)

    R0 = required_set(tile_set, contact)
    f1 = len(R0)

    f2 = 0
    aux = 0
    for n in cover_count.values():
        if n < 2:
            continue
        if n <= AMO_THRESHOLD:
            f2 += n * (n - 1) // 2
        else:
            f2 += 3 * n - 4
            aux += n - 1

    f4 = sum(u[1:])

    # union cellsets with ids for the touch graph
    all_sets = sorted({cs for d in mult for cs in d},
                      key=lambda cs: tuple(sorted(cs)))
    idx = {cs: i for i, cs in enumerate(all_sets)}
    pairs = touching_cellset_pairs(all_sets, contact)

    f5 = 0
    for (a, b) in pairs:
        A, B = all_sets[a], all_sets[b]
        for l in range(m):
            for j in range(m):
                if abs(l - j) < 2:
                    continue
                if l > j:
                    f5 += mult[l].get(A, 0) * mult[j].get(B, 0)
                    f5 += mult[l].get(B, 0) * mult[j].get(A, 0)

    f6 = 0
    for l in range(m - 1):
        for cs, k in mult[l].items():
            halo = contact_neighbors(cs, contact) - tile_set
            f6 += len(halo) * k

    clauses = f1 + f2 + f4 + f5 + f6
    return {
        "u": u, "vars": n_x, "aux": aux,
        "f1": f1, "f2": f2, "f4": f4, "f5": f5, "f6": f6,
        "clauses": clauses,
        "secs": round(time.time() - t0, 1),
    }


def synth_shapes():
    return [
        ("rect5x10", "O", [(x, y) for x in range(10) for y in range(5)]),
        ("square10", "O", [(x, y) for x in range(10) for y in range(10)]),
        ("rect10x20", "O", [(x, y) for x in range(20) for y in range(10)]),
    ]


def main():
    out_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "ml-feasibility.md"
    rows = []

    shapes = []
    for p in sorted((ROOT / "tests" / "corpus").glob("*nontiler*.txt")):
        sub = parse_submission(p.read_text(encoding="ascii"))
        shapes.append((p.stem, sub.grid_id, list(sub.cells)))
    shapes.extend(synth_shapes())

    for name, gid, cells in shapes:
        grid = GRIDS[gid]
        contact = grid.contact("point")
        max_m = 5 if len(cells) >= 50 else 3
        for m in range(2, max_m + 1):
            try:
                r = count_formula(frozenset(cells), grid, contact, m)
            except (TimeoutError, MemoryError):
                rows.append((name, gid, len(cells), m, None))
                break
            rows.append((name, gid, len(cells), m, r))
            print(f"{name} m={m}: vars={r['vars']+r['aux']} clauses={r['clauses']} "
                  f"({r['secs']}s)", flush=True)
            if r["clauses"] > 50_000_000:
                break

    lines = [
        "# v2 feasibility table (multilevel spec §10.2)", "",
        "Counts from universes alone — no clause objects. DNF = row budget "
        f"({ROW_BUDGET_S:.0f}s) or memory exceeded.", "",
        "| shape | grid | cells | m | u_l | vars | f1 | f2 | f4 | f5 | f6 | clauses | secs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, gid, n, m, r in rows:
        if r is None:
            lines.append(f"| {name} | {gid} | {n} | {m} | DNF | | | | | | | | |")
        else:
            lines.append(
                f"| {name} | {gid} | {n} | {m} | {'/'.join(map(str, r['u']))} "
                f"| {r['vars'] + r['aux']} | {r['f1']} | {r['f2']} | {r['f4']} "
                f"| {r['f5']} | {r['f6']} | {r['clauses']} | {r['secs']} |"
            )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
