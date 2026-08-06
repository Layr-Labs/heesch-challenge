"""Error codes, statuses, and the Result record.

Error codes are API (spec §8): agents parse them in search loops. Every
rejection carries a stable code, a human message, and, where meaningful,
offending coordinates.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field


class ErrorCode(str, enum.Enum):
    # Parse
    PARSE_SYNTAX = "PARSE_SYNTAX"
    PARSE_COUNT_MISMATCH = "PARSE_COUNT_MISMATCH"
    PARSE_UNKNOWN_GRID = "PARSE_UNKNOWN_GRID"
    # Shape
    SHAPE_TOO_LARGE = "SHAPE_TOO_LARGE"
    SHAPE_SPAN_EXCEEDED = "SHAPE_SPAN_EXCEEDED"
    SHAPE_DISCONNECTED = "SHAPE_DISCONNECTED"
    SHAPE_HAS_HOLE = "SHAPE_HAS_HOLE"
    SHAPE_DUPLICATE_CELL = "SHAPE_DUPLICATE_CELL"
    SHAPE_EMPTY = "SHAPE_EMPTY"
    # Transform
    XFORM_NOT_SYMMETRY = "XFORM_NOT_SYMMETRY"
    XFORM_REFLECTION_BANNED = "XFORM_REFLECTION_BANNED"
    # Patch
    PATCH_OVERLAP = "PATCH_OVERLAP"
    PATCH_LEVEL_MISMATCH = "PATCH_LEVEL_MISMATCH"
    PATCH_ORPHAN_TILE = "PATCH_ORPHAN_TILE"
    PATCH_GAP = "PATCH_GAP"
    PATCH_HOLE_IN_CORONA = "PATCH_HOLE_IN_CORONA"
    PATCH_NO_CENTRAL_TILE = "PATCH_NO_CENTRAL_TILE"
    PATCH_MULTIPLE_CENTRAL = "PATCH_MULTIPLE_CENTRAL"
    # Claims
    CLAIM_BELOW_THRESHOLD = "CLAIM_BELOW_THRESHOLD"
    CLAIM_WEAKER_THAN_STATED = "CLAIM_WEAKER_THAN_STATED"
    # Defect (§9.2)
    DEFECT_XFORM_INVALID = "DEFECT_XFORM_INVALID"
    DEFECT_TILE_OVERLAP = "DEFECT_TILE_OVERLAP"
    DEFECT_TILE_NOT_TOUCHING = "DEFECT_TILE_NOT_TOUCHING"
    DEFECT_TILE_OUT_OF_BAND = "DEFECT_TILE_OUT_OF_BAND"
    DEFECT_CLAIM_MISMATCH = "DEFECT_CLAIM_MISMATCH"
    DEFECT_LEVEL_MISMATCH = "DEFECT_LEVEL_MISMATCH"
    # Gates
    GATE_IS_TILER = "GATE_IS_TILER"
    GATE_INCONCLUSIVE = "GATE_INCONCLUSIVE"
    GATE_PROOF_INVALID = "GATE_PROOF_INVALID"
    PROOF_CNF_DIGEST_MISMATCH = "PROOF_CNF_DIGEST_MISMATCH"
    PROOF_TRUNCATED = "PROOF_TRUNCATED"
    PROOF_HEADER_MISMATCH = "PROOF_HEADER_MISMATCH"
    # Store / resources
    DUPLICATE = "DUPLICATE"
    RESOURCE_EXCEEDED = "RESOURCE_EXCEEDED"


class Status(str, enum.Enum):
    """Non-terminal statuses, distinct from rejection codes (spec §8)."""

    PROMOTED = "PROMOTED"
    SUPERSEDED = "SUPERSEDED"
    PENDING_GATE = "PENDING_GATE"
    EXACT_UNDECIDED_HOLE_CASE = "EXACT_UNDECIDED_HOLE_CASE"


class VerifyError(Exception):
    def __init__(self, code: ErrorCode, message: str, cells: tuple = ()):
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message
        self.cells = tuple(cells)

    def to_json(self) -> dict:
        out = {"error": self.code.value, "message": self.message}
        if self.cells:
            out["cells"] = [list(c) for c in self.cells]
        return out


@dataclass(frozen=True)
class Result:
    """Everything recorded per accepted submission (spec §9, §9.2.8)."""

    hc_verified: int
    hh_verified: int
    cell_count: int
    span_x: int
    span_y: int
    symmetry_order: int
    patch_size: int
    grid: str
    reflections_used: bool
    canonical_digest: str
    gate_tier: str = "none"
    verified_claim: str = ""
    claim_discrepancy: bool = False
    hc_claimed: int = 0
    hh_claimed: int = 0
    # Defect fields (§9.2.8) — recorded on every submission regardless of the
    # board flag, so enabling the board later needs no re-verification.
    defect_enabled: bool = False
    defect_block_present: bool = False
    defect_corona_level: int = 0
    defect_hc: int = 0
    defect_hh: int = 0
    defect_required: int = 0
    defect_pocket_cells: int = 0
    defect_partial_tiles: int = 0
    # Frozen conventions (§11) written into every record.
    conventions: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        out = {
            "hc_verified": self.hc_verified,
            "hh_verified": self.hh_verified,
            "cell_count": self.cell_count,
            "span_x": self.span_x,
            "span_y": self.span_y,
            "symmetry_order": self.symmetry_order,
            "patch_size": self.patch_size,
            "grid": self.grid,
            "reflections_used": self.reflections_used,
            "canonical_digest": self.canonical_digest,
            "gate_tier": self.gate_tier,
            "verified_claim": self.verified_claim,
            "claim_discrepancy": self.claim_discrepancy,
            "hc_claimed": self.hc_claimed,
            "hh_claimed": self.hh_claimed,
            "defect_enabled": self.defect_enabled,
            "defect_block_present": self.defect_block_present,
            "defect_corona_level": self.defect_corona_level,
            "defect_hc": self.defect_hc,
            "defect_hh": self.defect_hh,
            "defect_required": self.defect_required,
            "defect_pocket_cells": self.defect_pocket_cells,
            "defect_partial_tiles": self.defect_partial_tiles,
            "conventions": dict(self.conventions),
        }
        return out

    def to_json_str(self) -> str:
        return json.dumps(self.to_json(), sort_keys=True, separators=(",", ":"))
