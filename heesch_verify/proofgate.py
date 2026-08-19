"""Gate 3 — the proof-carrying non-tiler gate (architecture §2.3, §13).

A submission whose shape is outside the census can only score by carrying a
machine-checked UNSAT proof of the multilevel formula F(S, m) (encoder v2).
UNSAT of F(S, m) means no weak m-configuration exists over ALL patches, so
Hh <= m-1 and the shape is not a plane tiler; with a verified witness of
hh = m-1 the value is exact (multilevel spec §2.2). This module turns the
`#PROOF` block of a parsed submission into an enforced verdict:

  1. level rule        m >= hh_verified + 1, else PROOF_LEVEL_INCONSISTENT
                       (a witness deeper than the proof allows is a
                       contradiction — never scored, never "fixed up")
  2. checker preflight all three vendored checkers present, else
                       CHECKER_UNAVAILABLE (fail closed; never a downgrade)
  3. bands             harness band and the encoder feasibility band, else RESOURCE_EXCEEDED
  4. proof file        regular file inside submission/, size caps, optional
                       xz with bounded decompression, sha256 verified before
                       any checker sees a byte (same for the optional core
                       clause list — the subset of F an LRAT proof refutes;
                       heesch_encoder.proofcheck.core checks every clause is
                       a clause of the regenerated F, exactly)
  5. check_proof_v2    regenerate F(S, m), digest/header match, sniff, then
                       RECORD tier: two independent VERIFIED verdicts, one of
                       them cake_lpr (formally verified)

Never imported by witness.py or anything it imports; heesch_encoder is
imported lazily inside check() so the lower-bound path stays independent.
"""

from __future__ import annotations

import dataclasses
import hashlib
import lzma
import os
import pathlib
import shutil
import stat
import tempfile

from .canonical import canonical_form
from .result import ErrorCode

# On-disk cap for the proof file as submitted (plain or .xz) and the cap on
# the decompressed payload the checkers read. Coupled to benchmark.json's
# maxSubmissionBytes (128 MiB): best.heesch (<= 2 MiB) + proof + core must fit.
PROOF_MAX_STORED_BYTES = 48 * 1024 * 1024
# A record-scale LRAT (F(S,6) of an 11-cell shape) is ~513 MB raw / 25 MB xz;
# the payload lands in scratch on disk, never in memory.
PROOF_MAX_PAYLOAD_BYTES = 1024 * 1024 * 1024
_XZ_MEMLIMIT = 256 * 1024 * 1024
_CHUNK = 1024 * 1024

# In-harness proof band (cells, max m): the encoder's feasibility band minus
# its two heaviest cells ((50, 4) and (200, 2)), because the harness must
# ENCODE F(S, m) inside the benchmark job as well as check it. (<= 20, 5)
# admits the exactness proof of every known Hc = 4 shape (11-20 cells);
# (<= 12, 6) admits an Hc = 5 certificate for a shape up to 12 cells
# (measured: F(S,6) of the 11-hex — 112 s encode at 2.5 GB RSS, drat-trim
# 61 s, lrat-check 16 s on the 513 MB LRAT). See docs/ml-feasibility.md.
HARNESS_PROOF_BAND = ((12, 6), (20, 5), (50, 3), (100, 2))
# Wall-clock guard around the in-process ENCODING step only (pipeline passes
# it to heesch_encoder.proofcheck.guard); the checkers are bounded separately
# by the CheckBudget the caller supplies (per-checker caps drat-trim 600 s /
# cake_lpr 900 s / lrat-check 300 s, overall deadline 1500 s counted from the
# budget's construction, which the harness does before this gate runs — so the
# whole proof stage is <= 1500 s end to end, with the encoder allowed at most
# the first 600 s of it). Exceeding either is RESOURCE_EXCEEDED, never a crash.
ENCODE_TIMEOUT_S = 600

CHECKER_NAMES = ("drat-trim", "lrat-check", "cake_lpr")


def in_harness_band(n_cells: int, m: int) -> bool:
    for max_cells, max_m in HARNESS_PROOF_BAND:
        if n_cells <= max_cells:
            return 1 <= m <= max_m
    return False


@dataclasses.dataclass(frozen=True)
class ProofVerdict:
    code: ErrorCode | None      # None == VERIFIED
    detail: str
    m: int = 0
    cnf_digest: str = ""
    proof_sha256: str = ""
    fmt: str = ""
    checkers_verified: tuple = ()
    hh_exact: bool = False
    exact: bool = False
    core_clauses: int = 0
    detected_format: str = ""   # what the bytes were (formats.ProofFormat value)

    def to_json(self) -> dict:
        return {
            "status": "VERIFIED" if self.code is None else self.code.value,
            "detail": self.detail,
            "m": self.m,
            "cnf_digest": self.cnf_digest,
            "proof_sha256": self.proof_sha256,
            "format": self.fmt,
            "format_detected": self.detected_format,
            "checkers_verified": list(self.checkers_verified),
            "hh_exact": self.hh_exact,
            "exact": self.exact,
            "core_clauses": self.core_clauses,
        }


class ProofFileError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _open_regular(path: pathlib.Path) -> int:
    """Open a submission-side file refusing symlinks and non-regular files
    (the same discipline harness/verify.py applies to best.heesch)."""
    try:
        st = os.lstat(path)
    except OSError as e:
        raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, f"cannot stat proof file: {e}")
    if not stat.S_ISREG(st.st_mode):
        raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, "proof file is not a regular file")
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
             | getattr(os, "O_BINARY", 0))
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, f"cannot open proof file: {e}")
    fst = os.fstat(fd)
    if not stat.S_ISREG(fst.st_mode) or (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
        os.close(fd)
        raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, "proof file changed under us")
    return fd


def materialize_proof(src: pathlib.Path, dst: pathlib.Path, compression: str) -> tuple[int, str]:
    """Stream the submitted proof into `dst` (decompressing xz with a bounded
    output), returning (payload_bytes, payload_sha256). Raises ProofFileError."""
    fd = _open_regular(src)
    with os.fdopen(fd, "rb", closefd=True) as fh:
        size = os.fstat(fh.fileno()).st_size
        if size > PROOF_MAX_STORED_BYTES:
            raise ProofFileError(
                ErrorCode.RESOURCE_EXCEEDED,
                f"proof file is {size} bytes (cap {PROOF_MAX_STORED_BYTES})",
            )
        h = hashlib.sha256()
        total = 0
        with open(dst, "wb") as out:
            if compression == "none":
                while True:
                    chunk = fh.read(_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > PROOF_MAX_PAYLOAD_BYTES:
                        raise ProofFileError(
                            ErrorCode.RESOURCE_EXCEEDED,
                            f"proof payload exceeds {PROOF_MAX_PAYLOAD_BYTES} bytes",
                        )
                    h.update(chunk)
                    out.write(chunk)
            else:
                dec = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=_XZ_MEMLIMIT)
                try:
                    while True:
                        chunk = fh.read(_CHUNK)
                        if not chunk and dec.needs_input:
                            break
                        data = dec.decompress(chunk, max_length=_CHUNK)
                        while True:
                            total += len(data)
                            if total > PROOF_MAX_PAYLOAD_BYTES:
                                raise ProofFileError(
                                    ErrorCode.RESOURCE_EXCEEDED,
                                    f"decompressed proof exceeds {PROOF_MAX_PAYLOAD_BYTES} bytes",
                                )
                            h.update(data)
                            out.write(data)
                            if dec.needs_input or dec.eof:
                                break
                            data = dec.decompress(b"", max_length=_CHUNK)
                        if dec.eof:
                            break
                except lzma.LZMAError as e:
                    raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, f"xz: {e}")
                if not dec.eof:
                    raise ProofFileError(ErrorCode.PROOF_FILE_INVALID, "xz stream truncated")
                if dec.unused_data or fh.read(1):
                    raise ProofFileError(ErrorCode.PROOF_FILE_INVALID,
                                         "trailing data after the xz stream")
    return total, h.hexdigest()


class ProofCarryingGate:
    """Enforced non-tiler proof gate. `submission_dir` is the directory that
    holds best.heesch and the proof file it names; `checker_dir` holds the
    vendored checker binaries."""

    def __init__(self, submission_dir, checker_dir, budget=None):
        self.submission_dir = pathlib.Path(submission_dir)
        self.checker_dir = pathlib.Path(checker_dir)
        self.budget = budget

    def missing_checkers(self) -> list[str]:
        """Names of checkers that are not regular, executable files in
        checker_dir (the same predicate checkers._run applies at spawn)."""
        from heesch_encoder.proofcheck.checkers import checker_path, checker_problem

        return [name for name in CHECKER_NAMES
                if checker_problem(checker_path(name, self.checker_dir)) is not None]

    def check(self, sub, outcome) -> ProofVerdict:
        block = sub.proof
        hc, hh = outcome.result.hc_verified, outcome.result.hh_verified
        m = block.m
        # 1. Level rule.
        if m < hh + 1:
            return ProofVerdict(
                ErrorCode.PROOF_LEVEL_INCONSISTENT,
                f"F(S,{m}) UNSAT would give Hh <= {m - 1} but the witness verifies "
                f"hh = {hh}; the proof must be for m >= {hh + 1}",
                m=m,
            )
        hh_exact = (m - 1 == hh)
        exact = hh_exact and hc == hh
        # 2. Checker preflight — fail closed before touching the proof.
        missing = self.missing_checkers()
        if missing:
            return ProofVerdict(
                ErrorCode.CHECKER_UNAVAILABLE,
                "proof checkers not available: " + ", ".join(missing)
                + f" (looked in {self.checker_dir})",
                m=m,
            )
        # 3. Bands.
        n_cells = len(sub.cells)
        if not in_harness_band(n_cells, m):
            return ProofVerdict(
                ErrorCode.RESOURCE_EXCEEDED,
                f"({n_cells} cells, m={m}) is outside the in-harness proof band "
                f"{HARNESS_PROOF_BAND}",
                m=m,
            )
        # 4. Materialize the proof file into scratch.
        src = self.submission_dir / block.file_name
        scratch = pathlib.Path(tempfile.mkdtemp(prefix="heesch-proof-"))
        try:
            dst = scratch / f"proof.{block.fmt}"
            try:
                _, payload_sha = materialize_proof(src, dst, block.compression)
            except ProofFileError as e:
                return ProofVerdict(e.code, e.message, m=m)
            if payload_sha != block.payload_sha256:
                return ProofVerdict(
                    ErrorCode.PROOF_FILE_DIGEST_MISMATCH,
                    f"proof payload sha256 {payload_sha[:16]}… != declared "
                    f"{block.payload_sha256[:16]}…",
                    m=m,
                )
            # 5. Regenerate F(S, m) and run the frozen check order.
            from heesch_encoder.proofcheck.pipeline import (
                ProofStatus, ProofSubmission, Tier, check_proof_v2,
            )

            core_dst = None
            if block.core_file is not None:
                core_src = self.submission_dir / block.core_file
                core_dst = scratch / "core.txt"
                try:
                    _, core_sha = materialize_proof(core_src, core_dst, block.core_compression)
                except ProofFileError as e:
                    return ProofVerdict(e.code, "core: " + e.message, m=m)
                if core_sha != block.core_sha256:
                    return ProofVerdict(
                        ErrorCode.PROOF_FILE_DIGEST_MISMATCH,
                        f"core payload sha256 {core_sha[:16]}… != declared {block.core_sha256[:16]}…",
                        m=m,
                    )
            psub = ProofSubmission(
                proof_path=str(dst),
                claimed_cnf_digest=block.cnf_digest,
                claimed_vars=block.num_vars,
                claimed_clauses=block.num_clauses,
                claimed_core_clauses=block.core_clauses,
                declared_format=block.fmt,
            )
            tile = frozenset(canonical_form(sub.cells, sub.grid, True))
            out = check_proof_v2(
                psub, tile, sub.grid, outcome.contact, m,
                tier=Tier.RECORD, bin_dir=self.checker_dir, budget=self.budget,
                core_path=(str(core_dst) if core_dst is not None else None),
                encode_timeout_s=ENCODE_TIMEOUT_S,
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

        if out.status is not ProofStatus.VERIFIED:
            return ProofVerdict(
                ErrorCode(out.status.value), out.detail, m=m,
                cnf_digest=out.cnf_digest, proof_sha256=payload_sha, fmt=block.fmt,
                detected_format=out.detected_format,
            )
        verified = tuple(sorted(
            r.checker for r in out.checker_results if r.status.value == "VERIFIED"
        ))
        return ProofVerdict(
            None, out.detail, m=m, cnf_digest=out.cnf_digest,
            proof_sha256=payload_sha, fmt=block.fmt, checkers_verified=verified,
            hh_exact=hh_exact, exact=exact, core_clauses=out.core_clauses,
            detected_format=out.detected_format,
        )
