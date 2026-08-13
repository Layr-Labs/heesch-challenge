"""Text format -> Submission (spec §4, §9.2.7). Syntax only.

Accepts heesch-sat's canonical output byte-for-byte (CRLF and repeated spaces
tolerated); rejects structural garbage with distinct codes, never a crash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .grids import GRIDS, Cell, Grid
from .result import ErrorCode, VerifyError
from .transform import Xform

MAX_INT = 2**31
MAX_LINE_CHARS = 1_000_000

_PLACEMENT_RE = re.compile(
    r"^\s*(-?\d+)\s*<\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,"
    r"\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*>\s*$"
)

Placement = tuple[int, Xform]


def _is_defect_marker(line: str) -> bool:
    """True iff the line's first whitespace token is exactly '#DEFECT' (audit
    V7): the old startswith('#DEFECT') test accepted '#DEFECTXYZ ...' as a
    defect block, admitting out-of-spec bytes into the record."""
    toks = line.split()
    return bool(toks) and toks[0] == "#DEFECT"


@dataclass(frozen=True)
class DefectBlock:
    level: int
    u_hc: int
    u_hh: int
    required: int
    tiles: tuple[Placement, ...]


@dataclass(frozen=True)
class Submission:
    grid_id: str
    grid: Grid
    cells: tuple[Cell, ...]
    hc_claim: int
    hh_claim: int
    patch_count: int
    patches: tuple[tuple[Placement, ...], ...]
    defect: DefectBlock | None


def _int(tok: str, what: str) -> int:
    try:
        v = int(tok)
    except ValueError:
        # Truncate the echoed token (audit V6): an attacker-controlled first
        # token can be up to MAX_LINE_CHARS long and would otherwise flood the
        # CI log verbatim (and amplify V3's exfil channel).
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"expected integer for {what}, got {tok[:80]!r}")
    if abs(v) > MAX_INT:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"oversized integer for {what}: {tok[:80]}")
    return v


class _Lines:
    def __init__(self, text: str):
        self.lines = text.split("\n")
        self.pos = 0

    def next(self, what: str) -> str:
        while self.pos < len(self.lines):
            raw = self.lines[self.pos]
            if len(raw) > MAX_LINE_CHARS:
                raise VerifyError(ErrorCode.PARSE_SYNTAX, f"line {self.pos + 1} too long")
            self.pos += 1
            line = raw.rstrip("\r")
            if line.strip():
                return line
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"unexpected end of file: expected {what}")

    def assert_exhausted(self):
        for i in range(self.pos, len(self.lines)):
            # Enforce the line-length cap on trailing lines too (audit V8):
            # next() enforces it, assert_exhausted did not, so an oversized
            # whitespace-only trailing line was silently accepted.
            if len(self.lines[i]) > MAX_LINE_CHARS:
                raise VerifyError(ErrorCode.PARSE_SYNTAX, f"line {i + 1} too long")
            if self.lines[i].strip():
                raise VerifyError(
                    ErrorCode.PARSE_SYNTAX,
                    f"trailing garbage at line {i + 1}: {self.lines[i][:60]!r}",
                )


def _parse_placement(line: str, what: str) -> Placement:
    m = _PLACEMENT_RE.match(line)
    if not m:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"bad placement line in {what}: {line[:80]!r}")
    vals = [_int(g, what) for g in m.groups()]
    level = vals[0]
    return (level, Xform(*vals[1:]))


def _parse_patch(lines: _Lines, what: str, max_placements: int) -> tuple[Placement, ...]:
    count_line = lines.next(f"{what} placement count")
    toks = count_line.split()
    if len(toks) != 1:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"expected bare placement count for {what}")
    n = _int(toks[0], f"{what} placement count")
    if n < 0:
        raise VerifyError(ErrorCode.PARSE_COUNT_MISMATCH, f"negative placement count for {what}")
    if n > max_placements:
        raise VerifyError(
            ErrorCode.RESOURCE_EXCEEDED,
            f"{what} has {n} placements, cap is {max_placements}",
        )
    out = []
    for i in range(n):
        try:
            line = lines.next(f"{what} placement {i + 1}/{n}")
        except VerifyError as e:
            if e.code is ErrorCode.PARSE_SYNTAX and "unexpected end" in e.message:
                raise VerifyError(
                    ErrorCode.PARSE_COUNT_MISMATCH,
                    f"{what} declares {n} placements but file ends after {i}",
                )
            raise
        # A stray section marker where a placement should be means the declared
        # count disagrees with the actual line count.
        if _is_defect_marker(line):
            raise VerifyError(
                ErrorCode.PARSE_COUNT_MISMATCH,
                f"{what} declares {n} placements but only {i} present before #DEFECT",
            )
        out.append(_parse_placement(line, what))
    return tuple(out)


def parse_submission(text: str, *, max_placements: int = 20_000) -> Submission:
    if not isinstance(text, str):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "submission is not text")
    lines = _Lines(text)

    # --- shape line: "<G> x1 y1 x2 y2 ..." ---
    shape_line = lines.next("shape line")
    toks = shape_line.split()
    head = toks[0]
    if head.endswith("?"):
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX, "unclassified ('?') record is not a valid submission"
        )
    if len(head) != 1:
        # Truncate (audit V6): head is the untrusted first token of the file.
        raise VerifyError(ErrorCode.PARSE_UNKNOWN_GRID, f"bad grid designator {head[:80]!r}")
    grid = GRIDS.get(head)
    if grid is None:
        raise VerifyError(ErrorCode.PARSE_UNKNOWN_GRID, f"unknown grid {head!r}")
    coord_toks = toks[1:]
    if not coord_toks:
        raise VerifyError(ErrorCode.SHAPE_EMPTY, "no cells on shape line")
    if len(coord_toks) % 2 != 0:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "odd number of coordinates on shape line")
    coords = [_int(t, "cell coordinate") for t in coord_toks]
    cells = tuple(zip(coords[0::2], coords[1::2]))
    seen = set()
    for c in cells:
        if c in seen:
            raise VerifyError(
                ErrorCode.SHAPE_DUPLICATE_CELL, f"duplicate cell on shape line: {c}", (c,)
            )
        seen.add(c)
    for c in cells:
        if not grid.cell_valid(c):
            raise VerifyError(
                ErrorCode.PARSE_SYNTAX, f"cell {c} is not on the {head} grid lattice", (c,)
            )

    # --- claim line: "~ hc hh P" ---
    claim_line = lines.next("claim line")
    ctoks = claim_line.split()
    if not ctoks or ctoks[0] != "~":
        raise VerifyError(
            ErrorCode.PARSE_SYNTAX,
            f"expected non-tiler claim line '~ hc hh P', got {claim_line[:60]!r}",
        )
    if len(ctoks) != 4:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "claim line must be '~ hc hh P'")
    hc = _int(ctoks[1], "hc")
    hh = _int(ctoks[2], "hh")
    pcount = _int(ctoks[3], "patch count")
    if hc < 0 or hh < 0:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "negative Heesch claim")
    if hh not in (hc, hc + 1):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"hh must be hc or hc+1, got hc={hc} hh={hh}")
    if pcount not in (0, 1, 2):
        raise VerifyError(ErrorCode.PARSE_SYNTAX, f"patch count must be 0, 1 or 2, got {pcount}")
    if pcount == 2 and hh != hc + 1:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "second patch requires hh == hc + 1")
    if pcount < 2 and hh != hc:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "hh == hc + 1 requires a second patch")
    if pcount == 0 and hc != 0:
        raise VerifyError(ErrorCode.PARSE_SYNTAX, "hc > 0 requires a witness patch")

    patches = tuple(
        _parse_patch(lines, f"patch {i + 1}", max_placements) for i in range(pcount)
    )

    # --- optional defect block (§9.2.7) ---
    defect = None
    if lines.pos < len(lines.lines):
        # Peek for a #DEFECT marker among remaining non-blank lines.
        save = lines.pos
        try:
            nxt = lines.next("end of file")
        except VerifyError as e:
            # Re-raise a line-length violation instead of swallowing it as
            # generic trailing garbage (audit V8); only a clean end-of-file
            # (no non-blank lines left) should fall through to "no defect".
            if "too long" in e.message:
                raise
            nxt = None
        if nxt is not None:
            if _is_defect_marker(nxt):
                dtoks = nxt.split()
                if len(dtoks) != 5:
                    raise VerifyError(
                        ErrorCode.PARSE_SYNTAX, "defect header must be '#DEFECT k u_hc u_hh r'"
                    )
                d_level = _int(dtoks[1], "defect corona level")
                d_uhc = _int(dtoks[2], "defect u_hc")
                d_uhh = _int(dtoks[3], "defect u_hh")
                d_req = _int(dtoks[4], "defect required")
                if min(d_level, d_uhc, d_uhh, d_req) < 0:
                    raise VerifyError(ErrorCode.PARSE_SYNTAX, "negative value in defect header")
                tiles = _parse_patch(lines, "defect block", max_placements)
                defect = DefectBlock(
                    level=d_level, u_hc=d_uhc, u_hh=d_uhh, required=d_req, tiles=tiles
                )
            else:
                lines.pos = save
    lines.assert_exhausted()

    return Submission(
        grid_id=head,
        grid=grid,
        cells=cells,
        hc_claim=hc,
        hh_claim=hh,
        patch_count=pcount,
        patches=patches,
        defect=defect,
    )
