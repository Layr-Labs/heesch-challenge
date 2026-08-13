"""Yukon evaluator: grade submission/best.heesch, write score.json (root; HEESCH_SCORE_DIR overrides for the sandbox).

Run as `PYTHONHASHSEED=0 python -P -m harness.verify` from the repo root
(benchmark.sh runs it as `python -I -m harness.verify`, which implies -P and
ignores the environment; determinism comes from canonical ordering in the
code, not the hash-seed pin).

Policy (mirrors the verifier architecture §3): the solver's search program
under submission/ is an inert artifact — nothing there is ever imported or
executed. The only input is the plain-text shape file, and the verifier
re-derives every claim from scratch.

score.json is written only on full success; every rejection exits nonzero
with a REJECTED line naming the stable error code, and never writes a score.
"""

from __future__ import annotations

import json
import math
import pathlib
import stat
import sys

from heesch_verify import VerifyError, defect as defect_mod, score as score_mod
from heesch_verify.gates import IsohedralGate, Verdict
from heesch_verify.result import Result
from heesch_verify.witness import VerifyConfig, verify_witness

import os

ROOT = pathlib.Path.cwd()
SHAPE_PATH = ROOT / "submission" / "best.heesch"
# benchmark.sh points HEESCH_SCORE_DIR at a sandbox scratch dir and copies
# the score to the repo root only after full success; direct invocations
# write to the repo root themselves.
SCORE_PATH = pathlib.Path(os.environ.get("HEESCH_SCORE_DIR", str(ROOT))) / "score.json"
MAX_SHAPE_BYTES = 2 * 1024 * 1024


class Reject(Exception):
    pass


def _strict_load_text(path: pathlib.Path, max_bytes: int) -> str:
    # Audit V3/V5: the submission file must be a real regular file, not a
    # symlink or a device. A symlinked best.heesch would read an arbitrary
    # runner-readable path (host-file exfil / existence oracle); a character
    # device (/dev/zero) never EOFs and read_bytes() would exhaust memory into
    # an unstructured SIGKILL before the size cap engages. O_NOFOLLOW refuses a
    # symlink at the final component, fstat/S_ISREG refuses every non-regular
    # file, and the read is bounded to max_bytes+1 so an endless source cannot
    # blow past the cap.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise Reject(f"SHAPE_NOT_REGULAR_FILE: cannot open {path.name}: {e}")
    with os.fdopen(fd, "rb", closefd=True) as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            raise Reject(f"SHAPE_NOT_REGULAR_FILE: {path.name} is not a regular file")
        try:
            raw = fh.read(max_bytes + 1)
        except OSError as e:
            raise Reject(f"cannot read {path.name}: {e}")
    if len(raw) > max_bytes:
        raise Reject(f"{path.name} exceeds the {max_bytes}-byte cap")
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        raise Reject(f"{path.name} is not valid utf-8: {e}")


def _score_payload(result: Result, defect_res, gate: Verdict, gate_detail: str) -> dict:
    score = score_mod.yukon_score(result)
    if not math.isfinite(score):
        raise Reject("computed score is not finite")
    metrics = result.to_json()
    metrics["gate_tier"] = f"isohedral_{gate.value.lower()}"
    # Board-visible hollow-entry marker (audit V2): "unchecked:*" means the
    # gate never evaluated this shape class — segregate these entries.
    metrics["gate_detail"] = gate_detail
    if defect_res is not None:
        frac_num = max(0, defect_res.required - defect_res.defect_hc)
        metrics["score_fraction_num"] = frac_num
        metrics["score_fraction_den"] = defect_res.required
    # §9.2.2 / §9.2.6: what was established, never "minimum defect", and the
    # scalar is never labelled a Heesch number.
    claim = result.verified_claim
    if defect_res is not None:
        claim += (
            f"; defect_achieved {defect_res.defect_hc}/{defect_res.required}"
            f" at corona {defect_res.corona_level}"
        )
    metrics["verified_claim"] = claim
    return {"score": round(score, 6), "metrics": metrics}


def main() -> None:
    # Review finding 2: a stale score must never survive into a failed run
    # (benchmark.sh also wipes the repo-root copy before anything fallible).
    try:
        SCORE_PATH.unlink()
    except OSError:
        pass

    text = _strict_load_text(SHAPE_PATH, MAX_SHAPE_BYTES)

    config = VerifyConfig()
    try:
        outcome = verify_witness(text, config)
    except VerifyError as e:
        raise Reject(f"{e.code.value}: {e.message}")

    result = outcome.result
    sub = outcome.submission

    # Defect pass (§9.2): runs after Stage 5, reusing the same threaded
    # contact relation.
    defect_res = None
    if sub.defect is not None:
        if outcome.hc_corona is None:
            raise Reject("DEFECT_LEVEL_MISMATCH: defect block requires a witness patch")
        try:
            defect_res = defect_mod.verify_defect(
                frozenset(sub.cells), sub.grid, outcome.hc_corona, sub.defect,
                outcome.contact, allow_reflections=config.allow_reflections,
            )
        except VerifyError as e:
            raise Reject(f"{e.code.value}: {e.message}")
        # Rebuild the frozen Result with defect fields populated.
        kwargs = {**result.__dict__}
        kwargs.update(
            defect_corona_level=defect_res.corona_level,
            defect_hc=defect_res.defect_hc,
            defect_hh=defect_res.defect_hh,
            defect_required=defect_res.required,
            defect_pocket_cells=defect_res.pocket_cells,
            defect_partial_tiles=defect_res.partial_tiles,
        )
        result = Result(**kwargs)

    # Stage 6 — non-tiler gate 1 (cheap filter). A constructive isohedral
    # factorization means infinite Heesch number: reject.
    gate, gate_detail = IsohedralGate(sub.grid).check_detailed(frozenset(sub.cells))
    if gate is Verdict.TILER:
        raise Reject(
            "GATE_IS_TILER: shape tiles the plane isohedrally; "
            "its Heesch number is not finite"
        )

    payload = _score_payload(result, defect_res, gate, gate_detail)
    SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORE_PATH, "w", encoding="ascii", newline="\n") as fh:
        json.dump(payload, fh, sort_keys=True)
    print(f"score {payload['score']}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Reject as e:
        print(f"REJECTED: {e}", flush=True)
        sys.exit(1)
