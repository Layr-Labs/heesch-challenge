"""The enforced proof path (architecture §2.2/§13), end to end through the
real harness entrypoint.

Fail-closed rule: a shape outside Kaplan's census scores ONLY with a verified
`#PROOF` block; every proof failure rejects with its own code; a census shape
scores without a proof but a present-and-broken proof still rejects.

Real-checker tests use tests/util.checker_dir_for_tests: the vendored
drat-trim/lrat-check plus (off x86-64 Linux) a shim standing in for cake_lpr
so the record-tier control flow runs everywhere; the formally-verified
cake_lpr itself is exercised on the Linux CI/benchmark runner.
"""

import hashlib
import json
import lzma
import os
import subprocess
import sys

import pytest

from util import ROOT, checker_dir_for_tests, omino11_hc1, solve_drat

from heesch_verify.canonical import canonical_form
from heesch_verify.parse import parse_submission
from heesch_verify.proofgate import PROOF_MAX_PAYLOAD_BYTES, ProofCarryingGate
from heesch_verify.result import ErrorCode
from heesch_verify.witness import verify_witness

CENSUS_11 = omino11_hc1()  # Kaplan non-tiler (Hc=1, Hh=2), above the O<=10 census


def _run_harness(tmp_path, shape_text, files=(), checker_dir=None):
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True, exist_ok=True)
    (repo / "submission" / "best.heesch").write_text(shape_text, encoding="ascii")
    for name, data in files:
        (repo / "submission" / name).write_bytes(data)
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "HEESCH_CHECKER_DIR": str(checker_dir if checker_dir else tmp_path / "no-checkers"),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=600,
    )
    score_path = repo / "score.json"
    score = json.loads(score_path.read_text()) if score_path.exists() else None
    return proc, score


def _block(m, cnf, nv, nc, name, fmt, comp, payload):
    return f"#PROOF 1\nencoder heesch-encoder/v2 2 {m}\ncnf {cnf} {nv} {nc}\nfile {name} {fmt} {comp} {payload}\n"


@pytest.fixture(scope="module")
def unsat_proof(tmp_path_factory):
    """A real F(S,3) DRAT for the 11-omino (Hh = 2, so F(S,3) is UNSAT),
    produced by tools/prove.py's worker (pysat in a child process — the same
    path participants use; see util.solve_drat)."""
    pytest.importorskip("pysat.solvers")
    from heesch_encoder.multilevel.api import encode_multilevel

    out = verify_witness(CENSUS_11)
    sub = out.submission
    tile = frozenset(canonical_form(sub.cells, sub.grid, True))
    enc = encode_multilevel(tile, sub.grid, out.contact, 3)
    sat, drat = solve_drat(enc.dimacs, tmp_path_factory.mktemp("proof"))
    assert not sat
    return {"enc": enc, "drat": drat, "sha": hashlib.sha256(drat).hexdigest()}


# --- rejections that need no checkers ---------------------------------------

def test_inconclusive_without_proof_is_rejected(tmp_path):
    proc, score = _run_harness(tmp_path, CENSUS_11)
    assert proc.returncode != 0 and score is None
    assert "REJECTED: GATE_INCONCLUSIVE" in proc.stdout


def test_level_below_witness_is_inconsistent(tmp_path):
    text = CENSUS_11 + _block(1, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", b"0\n")])
    assert proc.returncode != 0 and score is None
    assert "REJECTED: PROOF_LEVEL_INCONSISTENT" in proc.stdout


def test_missing_checkers_reject_closed(tmp_path):
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", b"0\n")])
    assert proc.returncode != 0 and score is None
    assert "REJECTED: CHECKER_UNAVAILABLE" in proc.stdout


def test_census_shape_with_broken_proof_still_rejects(tmp_path):
    baseline = (ROOT / "submission" / "best.heesch").read_text(encoding="ascii")
    text = baseline + _block(1, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", b"0\n")])
    assert proc.returncode != 0 and score is None
    assert "REJECTED: PROOF_LEVEL_INCONSISTENT" in proc.stdout


# --- proof-file handling (checkers present, gate run in-process) -------------

def _gate(tmp_path, text, files):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    subdir = tmp_path / "submission"
    subdir.mkdir(exist_ok=True)
    for name, data in files:
        (subdir / name).write_bytes(data)
    out = verify_witness(text)
    return ProofCarryingGate(subdir, d).check(out.submission, out)


def test_symlinked_proof_rejected(tmp_path):
    if os.name == "nt":
        pytest.skip("symlinks")
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    (tmp_path / "submission").mkdir()
    target = tmp_path / "outside.drat"
    target.write_bytes(b"0\n")
    (tmp_path / "submission" / "p.drat").symlink_to(target)
    v = _gate(tmp_path, text, [])
    assert v.code is ErrorCode.PROOF_FILE_INVALID


def test_missing_proof_file_rejected(tmp_path):
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    assert _gate(tmp_path, text, []).code is ErrorCode.PROOF_FILE_INVALID


def test_payload_digest_mismatch_rejected(tmp_path):
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    assert _gate(tmp_path, text, [("p.drat", b"0\n")]).code is ErrorCode.PROOF_FILE_DIGEST_MISMATCH


def test_xz_bomb_is_bounded(tmp_path, monkeypatch):
    # A few KB of xz that inflates past the payload cap: the gate must stop
    # at the cap, quickly, without materializing the whole payload.
    import heesch_verify.proofgate as pg
    monkeypatch.setattr(pg, "PROOF_MAX_PAYLOAD_BYTES", 4 * 1024 * 1024)
    bomb = lzma.compress(b"0" * (16 * 1024 * 1024), preset=9)
    assert len(bomb) < 64 * 1024
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat.xz", "drat", "xz", "b" * 64)
    v = _gate(tmp_path, text, [("p.drat.xz", bomb)])
    assert v.code is ErrorCode.RESOURCE_EXCEEDED
    assert "decompressed" in v.detail


def test_xz_trailing_garbage_rejected(tmp_path):
    payload = b"0\n"
    data = lzma.compress(payload) + b"junk"
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat.xz", "drat", "xz",
                              hashlib.sha256(payload).hexdigest())
    v = _gate(tmp_path, text, [("p.drat.xz", data)])
    assert v.code is ErrorCode.PROOF_FILE_INVALID


def test_oversized_stored_proof_rejected(tmp_path, monkeypatch):
    import heesch_verify.proofgate as pg
    monkeypatch.setattr(pg, "PROOF_MAX_STORED_BYTES", 16)
    text = CENSUS_11 + _block(3, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    v = _gate(tmp_path, text, [("p.drat", b"0\n" * 100)])
    assert v.code is ErrorCode.RESOURCE_EXCEEDED


def test_out_of_band_rejected(tmp_path):
    text = CENSUS_11 + _block(8, "a" * 64, 1, 1, "p.drat", "drat", "none", "b" * 64)
    v = _gate(tmp_path, text, [("p.drat", b"0\n")])
    assert v.code is ErrorCode.RESOURCE_EXCEEDED
    assert "band" in v.detail


def test_wrong_cnf_digest_rejected_before_checkers(tmp_path, unsat_proof):
    text = CENSUS_11 + _block(3, "a" * 64, unsat_proof["enc"].num_vars,
                              unsat_proof["enc"].num_clauses, "p.drat", "drat", "none",
                              unsat_proof["sha"])
    v = _gate(tmp_path, text, [("p.drat", unsat_proof["drat"])])
    assert v.code is ErrorCode.PROOF_CNF_DIGEST_MISMATCH


def test_sat_model_is_not_a_proof(tmp_path, unsat_proof):
    enc = unsat_proof["enc"]
    fake = b"v 1 -2 3 0\n"
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "p.drat", "drat",
                              "none", hashlib.sha256(fake).hexdigest())
    v = _gate(tmp_path, text, [("p.drat", fake)])
    assert v.code is ErrorCode.GATE_PROOF_INVALID


# --- the positive path -------------------------------------------------------

def test_real_proof_scores_through_the_harness(tmp_path, unsat_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    enc = unsat_proof["enc"]
    xz = lzma.compress(unsat_proof["drat"], preset=6)
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "proof.drat.xz",
                              "drat", "xz", unsat_proof["sha"])
    proc, score = _run_harness(tmp_path, text, files=[("proof.drat.xz", xz)], checker_dir=d)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m = score["metrics"]
    assert score["score"] == 1.0
    assert m["non_tiler_evidence"] == "proof"
    assert m["tier"] == "lower_bound"   # m = hh + 2: non-tiler certified, not exact
    assert m["gate_tier"] == "nontiler_proof"
    assert m["gate_detail"] == "nontiler:proof:v2:m=3"
    assert m["proof_m"] == 3 and m["proof_status"] == "VERIFIED"
    assert m["proof_cnf_digest"] == enc.digest and m["proof_sha256"] == unsat_proof["sha"]
    assert m["proof_checkers"] == ["cake_lpr", "drat-trim"]
    # m = 3 = hh + 2: non-tiler certified, hh NOT pinned exactly (Hh in {1,2}).
    assert m["hh_exact"] is False and m["exact"] is False
    assert m["record_eligible"] is False
    assert "checked UNSAT proof of F(S,3)" in m["verified_claim"]


def test_tampered_proof_is_rejected(tmp_path, unsat_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    enc = unsat_proof["enc"]
    # A syntactically fine DRAT that asserts an unjustified unit and then the
    # empty clause: drat-trim must say NOT VERIFIED.
    tampered = b"1 0\n0\n"
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "p.drat", "drat",
                              "none", hashlib.sha256(tampered).hexdigest())
    proc, score = _run_harness(tmp_path, text, files=[("p.drat", tampered)], checker_dir=d)
    assert proc.returncode != 0 and score is None
    assert "REJECTED: GATE_PROOF_INVALID" in proc.stdout or "REJECTED: PROOF_TRUNCATED" in proc.stdout


def test_cli_check_proof_matches_harness(tmp_path, unsat_proof):
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    enc = unsat_proof["enc"]
    sub = tmp_path / "submission"
    sub.mkdir(exist_ok=True)
    (sub / "proof.drat").write_bytes(unsat_proof["drat"])
    text = CENSUS_11 + _block(3, enc.digest, enc.num_vars, enc.num_clauses, "proof.drat",
                              "drat", "none", unsat_proof["sha"])
    (sub / "best.heesch").write_text(text, encoding="ascii")
    env = {**os.environ, "HEESCH_CHECKER_DIR": str(d), "PYTHONPATH": str(ROOT)}
    proc = subprocess.run([sys.executable, "-m", "heesch_verify", str(sub / "best.heesch"), "--check-proof"],
                          capture_output=True, text=True, env=env, timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["proof"]["status"] == "VERIFIED" and out["proof"]["m"] == 3


def test_census_shape_plus_exact_proof(tmp_path):
    """A census shape may ALSO carry a proof: with m = hh + 1 the value is
    exact and both evidences are recorded (census+proof)."""
    pytest.importorskip("pysat.solvers")
    d = checker_dir_for_tests(tmp_path)
    if d is None:
        pytest.skip("tools/bin checkers not built")
    from heesch_encoder.multilevel.api import encode_multilevel

    text = sorted((ROOT / "tests" / "corpus").glob("omino8-nontiler-*-hc1hh1.txt"))[0].read_text()
    out = verify_witness(text)
    sub = out.submission
    tile = frozenset(canonical_form(sub.cells, sub.grid, True))
    enc = encode_multilevel(tile, sub.grid, out.contact, 2)
    sat, drat = solve_drat(enc.dimacs, tmp_path)
    assert not sat
    sha = hashlib.sha256(drat).hexdigest()
    full = text + _block(2, enc.digest, enc.num_vars, enc.num_clauses, "p.drat", "drat", "none", sha)
    proc, score = _run_harness(tmp_path, full, files=[("p.drat", drat)], checker_dir=d)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m = score["metrics"]
    assert m["non_tiler_evidence"] == "proof" and m["tier"] == "exact_proof"
    assert m["gate_detail"] == "nontiler:census+proof:v2:m=2"
    assert (m["census_hc"], m["census_hh"]) == (1, 1)
    assert m["hh_exact"] is True and m["exact"] is True
    assert m["record_eligible"] is False  # exact, but hc = 1 < 5
    assert "Hc = Hh = 1 exactly" in m["verified_claim"]
