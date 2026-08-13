"""Regenerate heesch_verify/known_tilers.json — the exhaustive known-tiler
digest table (review finding 1a).

Provenance per family: a shape is entered as a tiler ONLY by census
arithmetic against Kaplan 2022's published per-size non-tiler counts
(arXiv:2105.09438 Tables 1/3/5), which our own sweeps independently
reproduced for every family included here:

  O n<=7 : 4 non-tiling heptominoes known (corpus); everything else tiles.
  O n=8  : 369 free = 6 holed + 20 corpus non-tilers + 343 tilers.
  H n<=5 : ALL free polyhexes tile (first non-tilers at n=6).
  H n=6  : 82 free = 1 holed + 3 corpus non-tilers + 1 PROVEN non-tiler
           (the open F(S,3)-UNSAT shape, hardcoded below) + 77 tilers.
  I n<=6 : all free polyiamonds tile.
  I n=7  : 24 free = 23 tilers + 1 corpus non-tiler (the V-heptiamond,
           Hc=Hh=1 exactly by exhaustive corona search).
  I n=8  : all 66 free octiamonds tile.
  I n=9  : 160 free = 1 holed + 20 corpus non-tilers + 139 tilers.

Holed shapes are excluded (they are rejected upstream, not tilers). The
script asserts every published count exactly and refuses to write the table
on any mismatch.

Usage: python tools/gen_tiler_table.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import classify  # noqa: E402
from heesch_verify.canonical import canonical_digest  # noqa: E402
from heesch_verify.grids import GRIDS  # noqa: E402
from heesch_verify.parse import parse_submission  # noqa: E402
from heesch_verify.shape import holes_of  # noqa: E402

CORPUS = ROOT / "tests" / "corpus"

# The open 6-hex: proven non-tiler (F(S,3) UNSAT => W <= 2), exact Hc pending
# arbitration. Never a tiler either way.
OPEN_HEX = frozenset([(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (3, 1)])

# Published (family, n) -> expected non-tiler count among hole-free shapes.
EXPECTED_NONTILERS = {
    ("O", 7): 3, ("O", 8): 20,
    ("H", 6): 4,
    ("I", 7): 1, ("I", 8): 0, ("I", 9): 20,
}


def corpus_nontiler_digests(grid_id: str, n: int, grid) -> set:
    prefix = {"O": "omino", "H": "hex", "I": "iamond"}[grid_id]
    out = set()
    for p in sorted(CORPUS.glob(f"{prefix}{n}-nontiler-*.txt")):
        sub = parse_submission(p.read_text(encoding="ascii"))
        out.add(canonical_digest(sub.cells, grid, True))
    return out


def family_tilers(grid_id: str, n: int) -> list[str]:
    grid = GRIDS[grid_id]
    nontilers = corpus_nontiler_digests(grid_id, n, grid)
    if grid_id == "H" and n == 6:
        nontilers = set(nontilers)
        nontilers.add(canonical_digest(sorted(OPEN_HEX), grid, True))
    expected = EXPECTED_NONTILERS.get((grid_id, n))
    if expected is not None:
        assert len(nontilers) == expected, (
            f"{grid_id}{n}: {len(nontilers)} known non-tilers, published "
            f"count is {expected} — refusing to build an unsound table"
        )

    tilers = []
    holed = 0
    for cells in classify.free_polyforms(grid_id, n):
        tile = frozenset(cells)
        if holes_of(tile, grid):
            holed += 1
            continue
        d = canonical_digest(cells, grid, True)
        if d in nontilers:
            continue
        tilers.append(d)
    print(f"  {grid_id} n={n}: {len(tilers)} tilers, {holed} holed, "
          f"{len(nontilers)} non-tilers excluded", flush=True)
    return tilers


def main():
    table: dict[str, set] = {"O": set(), "H": set(), "I": set()}
    for n in range(1, 9):
        table["O"].update(family_tilers("O", n))
    for n in range(1, 7):
        table["H"].update(family_tilers("H", n))
    for n in range(1, 10):
        table["I"].update(family_tilers("I", n))

    out = {gid: sorted(ds) for gid, ds in table.items()}
    path = ROOT / "heesch_verify" / "known_tilers.json"
    with open(path, "w", newline="\n") as fh:
        json.dump(out, fh, indent=0)
        fh.write("\n")
    print(f"wrote {path}: " + ", ".join(f"{g}={len(d)}" for g, d in out.items()))


if __name__ == "__main__":
    main()
