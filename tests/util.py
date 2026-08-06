"""Shared test helpers: programmatic witness construction and mutation.

Negative fixtures are never stored — each test mutates a valid witness so it
isolates exactly one property (spec §12.2).
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from heesch_verify.transform import Xform  # noqa: E402


def xf_t(dx: int, dy: int) -> str:
    """Pure translation transform text."""
    return f"<1,0,{dx},0,1,{dy}>"


def witness_text(grid_id: str, cells, hc: int, hh: int, patches,
                 defect: str | None = None) -> str:
    """Assemble a submission file. `patches` is a list of lists of
    (level, xform_text)."""
    lines = [grid_id + " " + " ".join(f"{x} {y}" for x, y in cells)]
    lines.append(f"~ {hc} {hh} {len(patches)}")
    for p in patches:
        lines.append(str(len(p)))
        for lvl, xf in p:
            lines.append(f"{lvl} {xf}")
    if defect:
        lines.append(defect)
    return "\n".join(lines) + "\n"


def monomino_hc1() -> str:
    """Monomino with a complete 1-corona: the minimal valid witness."""
    placements = [(0, xf_t(0, 0))]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx, dy) != (0, 0):
                placements.append((1, xf_t(dx, dy)))
    return witness_text("O", [(0, 0)], 1, 1, [placements])


def monomino_hc2() -> str:
    """Monomino with two complete coronas (5x5 block of copies)."""
    placements = [(0, xf_t(0, 0))]
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if (dx, dy) == (0, 0):
                continue
            lvl = max(abs(dx), abs(dy))
            placements.append((lvl, xf_t(dx, dy)))
    return witness_text("O", [(0, 0)], 2, 2, [placements])


def domino_hc1() -> str:
    """Horizontal domino with a complete 1-corona of dominoes.

    Central: (0,0),(1,0). Corona: a ring of horizontal dominoes covering
    the 12 contact neighbors exactly plus overhang."""
    placements = [(0, xf_t(0, 0))]
    # Row below (y=-1): cells -1..2 -> dominoes at x=-1 and x=1
    placements.append((1, xf_t(-1, -1)))
    placements.append((1, xf_t(1, -1)))
    # Row above (y=1): same
    placements.append((1, xf_t(-1, 1)))
    placements.append((1, xf_t(1, 1)))
    # Left cell (-1,0) and right cell (2,0)
    placements.append((1, xf_t(-2, 0)))
    placements.append((1, xf_t(2, 0)))
    return witness_text("O", [(0, 0), (1, 0)], 1, 1, [placements])
