"""Checker subprocess wrappers. Success is a checker-specific, LINE-ANCHORED
verdict on stdout — exit codes are NOT a reliable signal from drat-trim, and
substring matching is unsound (drat-trim prints a non-verdict
`c VERIFIED derivation: ...` progress line; lrat-check's actual verdict is
`c VERIFIED`, not `s VERIFIED`). Any line containing NOT VERIFIED forces
failure regardless. Timeout / OOM map to RESOURCE_EXCEEDED (requeueable)."""

from __future__ import annotations

import enum
import os
import pathlib
import subprocess
from dataclasses import dataclass

_BIN = pathlib.Path(__file__).resolve().parents[2] / "tools" / "bin"


class CheckStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    RESOURCE_EXCEEDED = "RESOURCE_EXCEEDED"
    CHECKER_MISSING = "CHECKER_MISSING"


@dataclass(frozen=True)
class CheckResult:
    checker: str
    status: CheckStatus
    seconds: float
    detail: str = ""


def _verdict(out: str, success_line) -> bool:
    """True iff some stdout/stderr line satisfies the checker's success
    predicate AND no line anywhere says NOT VERIFIED."""
    lines = [ln.strip().lstrip("\r") for ln in out.split("\n")]
    if any("NOT VERIFIED" in ln for ln in lines):
        return False
    return any(success_line(ln) for ln in lines)


# Per-checker verdict lines, verified against the vendored sources:
#   drat-trim.c:1480-1483  ->  "s VERIFIED" / "s NOT VERIFIED"
#     (drat-trim.c:858 also prints "c VERIFIED derivation: ..." — a progress
#      line, NOT a verdict; exact-line matching excludes it)
#   lrat-check.c:490/496   ->  "c VERIFIED" / "c NOT VERIFIED"
#   cake_lpr               ->  "s VERIFIED UNSAT"
_SUCCESS = {
    "drat-trim": lambda ln: ln == "s VERIFIED",
    "lrat-check": lambda ln: ln == "c VERIFIED",
    "cake_lpr": lambda ln: ln.startswith("s VERIFIED"),
}


def _run(name: str, args: list[str], timeout: float) -> CheckResult:
    exe = _BIN / (name + (".exe" if os.name == "nt" else ""))
    if not exe.exists():
        return CheckResult(name, CheckStatus.CHECKER_MISSING, 0.0,
                           f"{exe} not built (tools/build_checkers.sh)")
    import time

    t0 = time.time()
    try:
        proc = subprocess.run(
            [str(exe), *args],
            capture_output=True,
            text=True,
            # F4: hostile proof bytes echoed by the checker must not crash the
            # decode with an unstructured UnicodeDecodeError — replace instead.
            errors="replace",
            # F3: never let a checker read a forged proof from our stdin
            # (drat-trim -S). We pass proofs by path only.
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, time.time() - t0,
                           "wall-clock timeout")
    except MemoryError:
        return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, time.time() - t0, "oom")
    dt = time.time() - t0
    out = proc.stdout + "\n" + proc.stderr
    if _verdict(out, _SUCCESS[name]):
        return CheckResult(name, CheckStatus.VERIFIED, dt)
    return CheckResult(name, CheckStatus.NOT_VERIFIED, dt, out[-500:])


def drat_trim(cnf_path: str, proof_path: str, *, emit_lrat: str | None = None,
              timeout: float = 3600.0) -> CheckResult:
    args = [cnf_path, proof_path]
    if emit_lrat:
        args += ["-L", emit_lrat]
    return _run("drat-trim", args, timeout)


def lrat_check(cnf_path: str, lrat_path: str, *, timeout: float = 3600.0) -> CheckResult:
    return _run("lrat-check", [cnf_path, lrat_path], timeout)


def cake_lpr(cnf_path: str, lrat_path: str, *, timeout: float = 3600.0) -> CheckResult:
    return _run("cake_lpr", [cnf_path, lrat_path], timeout)
