"""Epoch manifest (spec §11): the frozen constants, introspected from live
code for drift detection. Any change to the placement universe, variable
ordering, clause schema, emission order, or contact relation is a new
version and a new epoch — bug fixes are not exempt."""

from __future__ import annotations

import hashlib
import json
import pathlib

from heesch_verify.grids import GRIDS

from . import amo

EPOCH_DIR = pathlib.Path(__file__).parent / "epoch"


def live_constants() -> dict:
    """The values whose drift invalidates historical proofs, read from the
    running code (not from the manifest)."""
    point_groups = {}
    for gid, grid in sorted(GRIDS.items()):
        point_groups[gid] = [
            [s.a, s.b, s.c0, s.d, s.e, s.f0] for s in grid.orientations
        ]
    return {
        "amo_threshold": amo.AMO_THRESHOLD,
        "placement_order": "(symmetry_index, ty, tx)",
        "cell_order": "(y, x)",
        "literal_order": "(abs, negative-first)",
        "clause_emission": "amo-by-cell-then-pair, coverage-by-cell",
        "dimacs_profile": "p-cnf/newline/space/zero-terminated/no-comments/v1",
        "digest_algo": "sha256",
        "contact_relation": "point",
        "point_groups": point_groups,
    }


def constants_digest() -> str:
    payload = json.dumps(live_constants(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def load_epoch(n: int = 1) -> dict:
    return json.loads((EPOCH_DIR / f"epoch-{n}.json").read_text(encoding="utf-8"))
