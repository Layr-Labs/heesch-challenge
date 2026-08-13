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
    # Fail loud (audit 2026-08): a missing table would silently drop the
    # gate's strongest layer and let small anisohedral tilers score.
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
        return self.check_detailed(cells)[0]

    def check_detailed(self, cells) -> tuple[Verdict, str]:
        """check() plus a machine-readable detail naming WHICH constructive
        proof fired (TILER) or WHY an INCONCLUSIVE shape escaped evaluation:

          tiler:*                  — constructive proof (table / criterion)
          unchecked:boundary_*     — word extraction failed / over cap
          unchecked:unsupported_grid — no criteria for this grid at all
          evaluated:table_exhaustive — below the iamond census cap (n <= 9);
                                     table absence is a published-census
                                     non-tiler proof
          evaluated:no_factorization — the full layer ran, nothing matched

        Board consumers should treat `unchecked:*` entries as presumptively
        hollow; honest non-tilers land in `evaluated:*`. (Audit V2: the iamond
        gate now runs the boundary-word criteria on every polyiamond, so a
        >=10-cell iamond tiler is caught here instead of scoring by default.)
        """
        from . import boundary
        from .canonical import canonical_digest

        known = IsohedralGate._KNOWN.get(self.grid.grid_id)
        if known and canonical_digest(cells, self.grid, True) in known:
            return Verdict.TILER, "tiler:table"

        gid = self.grid.grid_id
        try:
            if gid == "O":
                word, n_dirs = boundary.boundary_word(cells, self.grid), 4
            elif gid == "H":
                word, n_dirs = boundary.hex_boundary_word(cells, self.grid), 6
            elif gid == "I":
                # Audit V2: the iamond gate is no longer structurally absent —
                # the boundary-word criteria now run on every polyiamond, so a
                # >=10-cell iamond tiler is caught constructively, not scored.
                word, n_dirs = boundary.iamond_boundary_word(cells, self.grid), 6
            else:
                return Verdict.INCONCLUSIVE, "unchecked:unsupported_grid"
        except (boundary.UnsupportedGrid, boundary.BoundaryError):
            return Verdict.INCONCLUSIVE, "unchecked:boundary_error"
        # Belt-and-braces (audit V1): the per-grid caps sit above the longest
        # boundary any legal (<= 200-cell, hole-free) shape can have, so this
        # branch is unreachable for every submittable O/H shape. Kept so that
        # if the cell cap or perimeter bound ever changes, an over-cap word
        # segregates as unchecked rather than silently scoring.
        if len(word) > boundary.max_boundary(n_dirs):
            return Verdict.INCONCLUSIVE, "unchecked:boundary_length"
        if boundary.translation_criterion(word, n_dirs):
            return Verdict.TILER, "tiler:translation"
        if boundary.conway_criterion(word, n_dirs):
            return Verdict.TILER, "tiler:conway"
        if n_dirs == 4 and boundary.quarter_turn_criterion(word):
            return Verdict.TILER, "tiler:quarter_turn"
        # Reflection factorization forms (Langerman–Winslow types 4–7) and
        # the hex 60/120-degree rotation forms are deliberately not
        # implemented yet: a wrong TILER verdict rejects a legitimate
        # submission, so each form ships only after differential validation
        # against heesch-sat classifications. Their absence only weakens the
        # filter, never soundness.
        if gid == "I" and len(cells) <= 9:
            # The criteria ran AND the iamond census table (n <= 9) is
            # exhaustive, so absence from it additionally proves non-tilerhood.
            return Verdict.INCONCLUSIVE, "evaluated:table_exhaustive"
        return Verdict.INCONCLUSIVE, "evaluated:no_factorization"


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
