"""v2 entry points. The digest depends only on (S, m) — tile_cells is taken
verbatim; callers pass the verifier's canonical form, same contract as v1."""

from __future__ import annotations

from dataclasses import dataclass

from heesch_verify.grids import Contact, Grid

from ..amo import AMO_THRESHOLD
from ..api import DigestMismatch
from ..dimacs import cnf_digest, emit_dimacs
from .clauses import build_ml_formula
from .types import MLFormula


@dataclass(frozen=True)
class MLEncodingResult:
    dimacs: bytes
    digest: str
    num_vars: int
    num_clauses: int
    m: int
    universe_sizes: tuple
    family_counts: tuple
    formula: MLFormula


def encode_multilevel(tile_cells, grid: Grid, contact: Contact, m: int,
                      amo_threshold: int = AMO_THRESHOLD) -> MLEncodingResult:
    formula = build_ml_formula(tile_cells, grid, contact, m, amo_threshold)
    dimacs = emit_dimacs(formula)
    return MLEncodingResult(
        dimacs=dimacs,
        digest=cnf_digest(dimacs),
        num_vars=formula.num_vars,
        num_clauses=len(formula.clauses),
        m=m,
        universe_sizes=tuple(len(lv) for lv in formula.levels),
        family_counts=formula.family_counts,
        formula=formula,
    )


def regenerate_and_match_v2(claimed_digest: str, tile_cells, grid: Grid,
                            contact: Contact, m: int):
    enc = encode_multilevel(tile_cells, grid, contact, m)
    if enc.digest != claimed_digest:
        return DigestMismatch(expected=claimed_digest, computed=enc.digest)
    return enc
