"""The frozen proof-check order of operations (encoder spec §8, arch §13.3):

1. Regenerate the CNF server-side from the shape + verified patch.
2. Digest match — BEFORE touching any submitted proof bytes.
3. Header var/clause counts match.
4. Size gate.
5. Format sniff on a bounded window; reject SAT models and empty files.
6. Dispatch to checkers; record tier requires TWO independent VERIFIED
   verdicts (a formally verified checker plus drat-trim/lrat-check).

UNSAT verified  =>  no hole-allowed corona k+1 exists  =>  Hh <= k, and with
the witness (Hc >= k): Hc = Hh = k exactly, and the shape is not a tiler.
A SAT outcome is EXACT_UNDECIDED_HOLE_CASE — an honest "not yet", never
shown as a failure (spec §5).
"""

from __future__ import annotations

import enum
import hashlib
import os
import tempfile
from dataclasses import dataclass, field

from ..api import encode
from . import checkers as ck
from .formats import ProofFormat, sniff, tail_wellformed

MAX_PROOF_BYTES = 8 * 1024**3  # 8 GiB size gate; oversized -> requeue out-of-band


class Tier(str, enum.Enum):
    TRIAGE = "triage"
    RECORD = "record"


class ProofStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    PROOF_CNF_DIGEST_MISMATCH = "PROOF_CNF_DIGEST_MISMATCH"
    PROOF_HEADER_MISMATCH = "PROOF_HEADER_MISMATCH"
    PROOF_TRUNCATED = "PROOF_TRUNCATED"
    GATE_PROOF_INVALID = "GATE_PROOF_INVALID"
    RESOURCE_EXCEEDED = "RESOURCE_EXCEEDED"
    CHECKER_UNAVAILABLE = "CHECKER_UNAVAILABLE"


@dataclass(frozen=True)
class ProofOutcome:
    status: ProofStatus
    detail: str = ""
    cnf_digest: str = ""
    encoder_vars: int = 0
    encoder_clauses: int = 0
    cnf_bytes: int = 0
    proof_bytes: int = 0
    check_seconds: float = 0.0
    checker_results: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class ProofSubmission:
    proof_path: str
    claimed_cnf_digest: str
    claimed_vars: int
    claimed_clauses: int


def store_proof(path: str, store_dir: str) -> str:
    """Content-addressed sidecar storage; hashing streams in 1 MiB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    digest = h.hexdigest()
    dest_dir = os.path.join(store_dir, digest[:2])
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, digest)
    if not os.path.exists(dest):
        os.replace(path, dest) if os.path.dirname(path) == dest_dir else _copy(path, dest)
    return digest


def _copy(src, dst):
    with open(src, "rb") as a, open(dst, "wb") as b:
        while True:
            chunk = a.read(1024 * 1024)
            if not chunk:
                break
            b.write(chunk)


def check_proof(sub: ProofSubmission, tile_cells, patch_cells, grid, contact,
                tier: Tier = Tier.RECORD, timeout: float = 3600.0) -> ProofOutcome:
    """v1 path: regenerate F_v1(S, P_k) then run the frozen steps 2-6."""
    enc = encode(tile_cells, patch_cells, grid, contact)
    return check_proof_encoded(sub, enc, tier=tier, timeout=timeout)


def check_proof_v2(sub: ProofSubmission, tile_cells, grid, contact, m: int,
                   tier: Tier = Tier.RECORD, timeout: float = 3600.0) -> ProofOutcome:
    """v2 path: regenerate the multilevel F(S, m) then the same frozen
    steps. UNSAT verified here means no weak m-configuration exists —
    Hh <= m-1 over ALL patches (multilevel spec §2.2)."""
    from ..multilevel.api import encode_multilevel

    enc = encode_multilevel(tile_cells, grid, contact, m)
    return check_proof_encoded(sub, enc, tier=tier, timeout=timeout)


def check_proof_encoded(sub: ProofSubmission, enc, tier: Tier = Tier.RECORD,
                        timeout: float = 3600.0) -> ProofOutcome:
    """Steps 2-6 of the frozen order, schema-blind: works for any encoding
    object exposing digest/num_vars/num_clauses/dimacs."""
    # 2. Digest match before touching the proof.
    if enc.digest != sub.claimed_cnf_digest:
        return ProofOutcome(
            ProofStatus.PROOF_CNF_DIGEST_MISMATCH,
            f"claimed {sub.claimed_cnf_digest[:16]}…, regenerated {enc.digest[:16]}…",
            cnf_digest=enc.digest,
        )
    # 3. Header counts.
    if (sub.claimed_vars, sub.claimed_clauses) != (enc.num_vars, enc.num_clauses):
        return ProofOutcome(
            ProofStatus.PROOF_HEADER_MISMATCH,
            f"claimed {sub.claimed_vars}v/{sub.claimed_clauses}c, "
            f"regenerated {enc.num_vars}v/{enc.num_clauses}c",
            cnf_digest=enc.digest,
        )
    # 4. Size gate.
    try:
        proof_bytes = os.stat(sub.proof_path).st_size
    except OSError as e:
        return ProofOutcome(ProofStatus.GATE_PROOF_INVALID, str(e), cnf_digest=enc.digest)
    if proof_bytes > MAX_PROOF_BYTES:
        return ProofOutcome(
            ProofStatus.RESOURCE_EXCEEDED,
            f"proof is {proof_bytes} bytes (cap {MAX_PROOF_BYTES}); requeue out-of-band",
            cnf_digest=enc.digest, proof_bytes=proof_bytes,
        )
    # 5. Sniff (bounded windows only).
    fmt = sniff(sub.proof_path)
    if fmt in (ProofFormat.EMPTY, ProofFormat.UNKNOWN):
        return ProofOutcome(ProofStatus.GATE_PROOF_INVALID, f"unrecognized proof ({fmt.value})",
                            cnf_digest=enc.digest, proof_bytes=proof_bytes)
    if fmt is ProofFormat.SAT_MODEL:
        return ProofOutcome(
            ProofStatus.GATE_PROOF_INVALID,
            "a SAT model is not an UNSAT proof",
            cnf_digest=enc.digest, proof_bytes=proof_bytes,
        )
    if fmt in (ProofFormat.DRAT_TEXT, ProofFormat.LRAT_TEXT) and not tail_wellformed(sub.proof_path):
        return ProofOutcome(ProofStatus.PROOF_TRUNCATED, "proof does not end on a terminated line",
                            cnf_digest=enc.digest, proof_bytes=proof_bytes)

    # 6. Checkers.
    with tempfile.TemporaryDirectory() as td:
        cnf_path = os.path.join(td, "formula.cnf")
        with open(cnf_path, "wb") as fh:
            fh.write(enc.dimacs)

        results = []
        if fmt in (ProofFormat.DRAT_TEXT, ProofFormat.DRAT_BINARY):
            lrat_out = os.path.join(td, "converted.lrat")
            r1 = ck.drat_trim(cnf_path, sub.proof_path, emit_lrat=lrat_out,
                              timeout=timeout)
            results.append(r1)
            if tier is Tier.RECORD and r1.status is ck.CheckStatus.VERIFIED:
                r2 = ck.cake_lpr(cnf_path, lrat_out, timeout=timeout)
                if r2.status is ck.CheckStatus.CHECKER_MISSING:
                    r2 = ck.lrat_check(cnf_path, lrat_out, timeout=timeout)
                results.append(r2)
        else:  # LRAT_TEXT
            r1 = ck.cake_lpr(cnf_path, sub.proof_path, timeout=timeout)
            if r1.status is ck.CheckStatus.CHECKER_MISSING:
                r1 = ck.lrat_check(cnf_path, sub.proof_path, timeout=timeout)
            results.append(r1)
            if tier is Tier.RECORD and r1.status is ck.CheckStatus.VERIFIED:
                r2 = ck.lrat_check(cnf_path, sub.proof_path, timeout=timeout) \
                    if results[0].checker == "cake_lpr" \
                    else ck.drat_trim(cnf_path, sub.proof_path, timeout=timeout)
                results.append(r2)

    seconds = sum(r.seconds for r in results)

    if any(r.status is ck.CheckStatus.CHECKER_MISSING for r in results):
        return ProofOutcome(ProofStatus.CHECKER_UNAVAILABLE,
                            "; ".join(f"{r.checker}: {r.detail}" for r in results),
                            cnf_digest=enc.digest, proof_bytes=proof_bytes,
                            checker_results=tuple(results), check_seconds=seconds)
    if any(r.status is ck.CheckStatus.RESOURCE_EXCEEDED for r in results):
        return ProofOutcome(ProofStatus.RESOURCE_EXCEEDED, "checker timeout/oom",
                            cnf_digest=enc.digest, proof_bytes=proof_bytes,
                            checker_results=tuple(results), check_seconds=seconds)

    need = 2 if tier is Tier.RECORD else 1
    verified = [r for r in results if r.status is ck.CheckStatus.VERIFIED]
    if len(verified) >= need:
        return ProofOutcome(
            ProofStatus.VERIFIED,
            f"{len(verified)} checker(s): " + ", ".join(r.checker for r in verified),
            cnf_digest=enc.digest, encoder_vars=enc.num_vars,
            encoder_clauses=enc.num_clauses, cnf_bytes=len(enc.dimacs),
            proof_bytes=proof_bytes, check_seconds=seconds,
            checker_results=tuple(results),
        )
    return ProofOutcome(
        ProofStatus.GATE_PROOF_INVALID,
        "; ".join(f"{r.checker}: {r.status.value} {r.detail[:120]}" for r in results),
        cnf_digest=enc.digest, proof_bytes=proof_bytes,
        checker_results=tuple(results), check_seconds=seconds,
    )
