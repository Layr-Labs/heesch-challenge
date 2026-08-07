"""JOB B/C: non-tiler gates (spec §2.1). May shell out; never imported by
witness.py or anything it imports.

Verdict semantics are the load-bearing decision: a gate returns TILER only on
a constructive proof that a tiling exists (a matching boundary factorization
is such a proof). It never returns NON_TILER from failed criteria —
anisohedral tilers exist, so absence of an isohedral factorization proves
nothing. Incompleteness of the criterion set costs filter strength, never
soundness.
"""

from __future__ import annotations

import enum


class Verdict(str, enum.Enum):
    TILER = "TILER"
    NON_TILER = "NON_TILER"
    INCONCLUSIVE = "INCONCLUSIVE"


def _load_known_tilers() -> dict:
    import json
    import pathlib

    path = pathlib.Path(__file__).parent / "known_tilers.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {gid: frozenset(digests) for gid, digests in data.items()}


class IsohedralGate:
    """Gate 1: boundary-word isohedral tiling criteria plus a digest table
    of exhaustively-known tilers (from published classifications — catches
    small anisohedral tilers the factorization criteria cannot). Fast,
    deterministic, polynomial; runs on every submission as a cheap
    pre-filter."""

    _KNOWN = None

    def __init__(self, grid):
        self.grid = grid
        if IsohedralGate._KNOWN is None:
            IsohedralGate._KNOWN = _load_known_tilers()

    def check(self, cells) -> Verdict:
        from . import boundary
        from .canonical import canonical_digest

        known = IsohedralGate._KNOWN.get(self.grid.grid_id)
        if known and canonical_digest(cells, self.grid, True) in known:
            return Verdict.TILER

        try:
            word = boundary.boundary_word(cells, self.grid)
        except (boundary.UnsupportedGrid, boundary.BoundaryError):
            return Verdict.INCONCLUSIVE
        if len(word) > boundary.MAX_BOUNDARY:
            return Verdict.INCONCLUSIVE
        if boundary.translation_criterion(word):
            return Verdict.TILER
        if boundary.conway_criterion(word):
            return Verdict.TILER
        if boundary.quarter_turn_criterion(word):
            return Verdict.TILER
        # Reflection factorization forms (Langerman–Winslow types 4–7) are
        # deliberately not implemented yet: a wrong TILER verdict rejects a
        # legitimate submission, so each form ships only after differential
        # validation against heesch-sat classifications. Their absence only
        # weakens the filter, never soundness.
        return Verdict.INCONCLUSIVE


class SatClassifierGate:
    """Gate 2: delegates to a heesch-sat binary with a corona cap. Triage
    only — a bare solver verdict is not independently checkable and is never
    sufficient for a record (§2.1)."""

    def __init__(self, binary_path: str | None = None, corona_cap: int = 12):
        self.binary_path = binary_path
        self.corona_cap = corona_cap

    def check(self, cells) -> Verdict:
        if self.binary_path is None:
            return Verdict.INCONCLUSIVE
        raise NotImplementedError("configured SatClassifierGate is a record-tier tool")


class ProofCarryingGate:
    """Gate 3: the promotion path. Regenerates the CNF with the frozen
    encoder, digest-matches, and validates a DRAT/LRAT proof via
    heesch_encoder.proofcheck.pipeline.check_proof_v2 (the multilevel
    F(S, k+1), which resolves the E8 per-patch quantifier gap — see
    docs/soundness-note.md and heesch-multilevel-encoder-spec.md). The v1
    single-level path remains sound only at k = 0.

    Hard-disabled pending external review of the v2 soundness obligations
    (M1-M9) — the round-trip, determinism, continuity and census-closing
    suites are green, but the spec requires review before the first
    record-tier promotion."""

    ENABLED = False

    def check(self, cells, k, proof_path) -> Verdict:
        if not self.ENABLED:
            raise RuntimeError(
                "ProofCarryingGate is disabled until the encoder round-trip "
                "suite (heesch-cnf-encoder-spec.md §9) passes"
            )
        raise NotImplementedError
