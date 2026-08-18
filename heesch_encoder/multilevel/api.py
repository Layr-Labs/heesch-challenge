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


# Feasibility band (multilevel spec §10.2): (max_cells, max_m) pairs the
# proof pipeline will ENCODE. This is measured policy, not a frozen constant
# — it changes no CNF byte, so widening it is not a new encoder revision (the
# revision-2 manifest carries the 2026-08-07 measurement as history).
# 2026-08-18: (<= 12, 6) added after measuring F(S,6) for the 11-hex Hc=4
# shape with the streaming encoder: 112 s encode, 2.5 GB RSS, 17.2 M
# clauses; UNSAT in 157 s; LRAT 513 MB (25 MB xz). See docs/ml-feasibility.md.
FEASIBILITY_BAND = ((12, 6), (20, 5), (50, 4), (100, 3), (200, 2))


def feasibility_band() -> tuple[tuple[int, int], ...]:
    """The enforced band as ((max_cells, max_m), ...), ascending in
    max_cells."""
    return FEASIBILITY_BAND


def in_feasibility_band(n_cells: int, m: int) -> bool:
    """True iff encoding F(S, m) for an n_cells shape is inside the band.
    Outside it check_proof_v2 answers RESOURCE_EXCEEDED by policy."""
    if m < 1 or n_cells < 1:
        return False
    for max_cells, max_m in feasibility_band():
        if n_cells <= max_cells:
            return m <= max_m
    return False


@dataclass(frozen=True)
class MLStreamedEncoding:
    """F(S, m) written straight to disk (multilevel spec §6): the same bytes
    `encode_multilevel` produces, without materialising the clause list —
    peak memory is the universe plus the per-cell cover lists, not the
    formula. Digest and counts are computed while streaming."""

    path: str
    digest: str
    num_vars: int
    num_clauses: int
    m: int
    universe_sizes: tuple
    family_counts: tuple
    cnf_bytes: int
    has_empty_clause: bool

    def write_dimacs(self, dst: str) -> None:
        import shutil

        if str(dst) != str(self.path):
            shutil.copyfile(self.path, dst)


def encode_multilevel_stream(tile_cells, grid: Grid, contact: Contact, m: int,
                             out_path, amo_threshold: int = AMO_THRESHOLD) -> MLStreamedEncoding:
    """Encode F(S, m) to `out_path` in the frozen DIMACS profile. Two passes
    over the output file (the header needs the final counts): clauses stream
    to `<out_path>.body`, then header + body are concatenated into out_path
    while the sha256 is computed. Byte-identical to encode_multilevel()."""
    import hashlib
    import os

    from .clauses import MLClauseStream

    stream = MLClauseStream(tile_cells, grid, contact, m, amo_threshold)
    out_path = str(out_path)
    body_path = out_path + ".body"
    empty = False
    with open(body_path, "wb") as body:
        buf = []
        n = 0
        for cl in stream.clauses():
            if cl:
                buf.append(" ".join(str(l) for l in cl) + " 0\n")
            else:
                empty = True
                buf.append("0\n")
            n += 1
            if n % 4096 == 0:
                body.write("".join(buf).encode("ascii"))
                buf = []
        if buf:
            body.write("".join(buf).encode("ascii"))
    header = f"p cnf {stream.num_vars} {stream.num_clauses}\n".encode("ascii")
    h = hashlib.sha256(header)
    size = len(header)
    with open(out_path, "wb") as out, open(body_path, "rb") as body:
        out.write(header)
        while True:
            chunk = body.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
            out.write(chunk)
    os.unlink(body_path)
    return MLStreamedEncoding(
        path=out_path, digest=h.hexdigest(), num_vars=stream.num_vars,
        num_clauses=stream.num_clauses, m=m,
        universe_sizes=tuple(len(lv) for lv in stream.uni.levels),
        family_counts=stream.family_counts, cnf_bytes=size, has_empty_clause=empty,
    )
