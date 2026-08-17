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


def feasibility_band() -> tuple[tuple[int, int], ...]:
    """The epoch-2 band (multilevel spec §10.2) as ((max_cells, max_m), ...),
    ascending in max_cells, read from the frozen manifest."""
    from ..manifest import load_epoch

    band = load_epoch(2)["feasibility_band"]["supported"]
    return tuple(sorted((int(b["max_cells"]), int(b["max_m"])) for b in band))


def in_feasibility_band(n_cells: int, m: int) -> bool:
    """True iff encoding F(S, m) for an n_cells shape is inside the epoch-2
    band. Outside it check_proof_v2 answers RESOURCE_EXCEEDED by policy."""
    if m < 1 or n_cells < 1:
        return False
    for max_cells, max_m in feasibility_band():
        if n_cells <= max_cells:
            return m <= max_m
    return False
