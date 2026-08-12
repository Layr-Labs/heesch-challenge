"""V2 regression (2026-08 audit, docs/VULN-REVIEW.md): for the iamond grid
the gate returned INCONCLUSIVE unconditionally beyond the n <= 9 table, so
every tiler with >= 10 cells scored by default — and its score.json was
indistinguishable from an honest non-tiler's. `check_detailed` now says WHY
a shape was inconclusive, and the harness emits `gate_detail` in metrics:
`unchecked:*` entries never saw the gate and are presumptively hollow.
"""

import json
import os
import subprocess
import sys

from util import ROOT  # noqa: F401

from heesch_verify import GRIDS
from heesch_verify.gates import IsohedralGate, Verdict

# Side-4 equilateral triangle (the audit PoC): 16 unit triangles, tiles the
# plane. Kaplan encoding: up (3a,3b), down (3a+1,3b+1).
IAMOND_TRIANGLE = frozenset(
    [(3 * i, 3 * j) for i in range(4) for j in range(4 - i)]
    + [(3 * i + 1, 3 * j + 1) for i in range(4) for j in range(3 - i)]
)
# A holed square ring: boundary_word raises BoundaryError (two cycles), and
# the gate must report that instead of a plain inconclusive.
HOLED_RING = frozenset((x, y) for x in range(3) for y in range(3)) - {(1, 1)}

BASELINE = (ROOT / "submission" / "best.heesch").read_text(encoding="ascii")


def _cells_from_corpus(name: str) -> frozenset:
    line = (ROOT / "tests" / "corpus" / f"{name}.txt").read_text().splitlines()[0]
    toks = line.split()[1:]
    return frozenset(zip(map(int, toks[0::2]), map(int, toks[1::2])))


def test_table_hit_names_the_proof():
    assert IsohedralGate(GRIDS["O"]).check_detailed(frozenset({(0, 0)})) == (
        Verdict.TILER,
        "tiler:table",
    )


def test_iamond_beyond_table_is_flagged_unchecked():
    assert IsohedralGate(GRIDS["I"]).check_detailed(IAMOND_TRIANGLE) == (
        Verdict.INCONCLUSIVE,
        "unchecked:iamond_beyond_table",
    )


def test_iamond_within_table_cap_is_exhaustively_evaluated():
    # An n <= 9 iamond absent from the table is a census-proven non-tiler.
    cells = _cells_from_corpus("iamond9-nontiler-0-hc0hh0")
    verdict, detail = IsohedralGate(GRIDS["I"]).check_detailed(cells)
    assert verdict is Verdict.INCONCLUSIVE
    assert detail == "evaluated:table_exhaustive"


def test_boundary_error_is_flagged_unchecked():
    verdict, detail = IsohedralGate(GRIDS["O"]).check_detailed(HOLED_RING)
    assert verdict is Verdict.INCONCLUSIVE
    assert detail == "unchecked:boundary_error"


def test_honest_nontiler_is_evaluated():
    cells = _cells_from_corpus("omino7-nontiler-0-hc1hh1")
    verdict, detail = IsohedralGate(GRIDS["O"]).check_detailed(cells)
    assert verdict is Verdict.INCONCLUSIVE
    assert detail == "evaluated:no_factorization"


def test_check_remains_verdict_only():
    # Backward-compatible: check() keeps returning a bare Verdict.
    assert IsohedralGate(GRIDS["I"]).check(IAMOND_TRIANGLE) is Verdict.INCONCLUSIVE


def test_gate_detail_reaches_score_json(tmp_path):
    repo = tmp_path / "repo"
    (repo / "submission").mkdir(parents=True)
    (repo / "submission" / "best.heesch").write_text(BASELINE, encoding="ascii")
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    proc = subprocess.run(
        [sys.executable, "-P", "-m", "harness.verify"],
        cwd=repo, env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    metrics = json.loads((repo / "score.json").read_text())["metrics"]
    assert metrics["gate_tier"] == "isohedral_inconclusive"  # unchanged contract
    assert metrics["gate_detail"] == "evaluated:no_factorization"
