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

# Default checker location for source checkouts. When the package runs from
# an installed copy (the benchmark runs `python -I` against .venv-bench), this
# resolves inside site-packages and does not exist — callers on that path MUST
# pass an explicit `bin_dir` (the harness passes $HEESCH_CHECKER_DIR or
# <repo>/tools/bin).
_BIN = pathlib.Path(__file__).resolve().parents[2] / "tools" / "bin"

CHECKER_NAMES = ("drat-trim", "lrat-check", "cake_lpr")


def checker_path(name: str, bin_dir=None) -> pathlib.Path:
    base = pathlib.Path(bin_dir) if bin_dir is not None else _BIN
    return base / (name + (".exe" if os.name == "nt" else ""))


class CheckBudget:
    """Wall-clock budget for one proof check: a per-checker cap plus an
    overall deadline. Every spawn gets min(cap, time left); a non-positive
    remainder is RESOURCE_EXCEEDED without spawning."""

    DEFAULT_CAPS = {"drat-trim": 540.0, "cake_lpr": 420.0, "lrat-check": 180.0}

    def __init__(self, per_checker: dict | None = None, deadline_seconds: float = 1200.0):
        import time

        self.caps = dict(self.DEFAULT_CAPS)
        if per_checker:
            self.caps.update(per_checker)
        self.deadline = time.monotonic() + float(deadline_seconds)

    def timeout_for(self, name: str) -> float:
        import time

        return min(self.caps.get(name, 3600.0), self.deadline - time.monotonic())


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


def _run(name: str, args: list[str], timeout: float, bin_dir=None,
         budget: CheckBudget | None = None) -> CheckResult:
    exe = checker_path(name, bin_dir)
    if not exe.exists():
        return CheckResult(name, CheckStatus.CHECKER_MISSING, 0.0,
                           f"{exe} not built (tools/build_checkers.sh)")
    import time

    if budget is not None:
        timeout = min(timeout, budget.timeout_for(name))
    if timeout <= 0:
        return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, 0.0,
                           "proof-check deadline exhausted before spawn")
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
              timeout: float = 3600.0, bin_dir=None, budget=None) -> CheckResult:
    args = [cnf_path, proof_path]
    if emit_lrat:
        args += ["-L", emit_lrat]
    return _run("drat-trim", args, timeout, bin_dir, budget)


def lrat_check(cnf_path: str, lrat_path: str, *, timeout: float = 3600.0,
               bin_dir=None, budget=None) -> CheckResult:
    return _run("lrat-check", [cnf_path, lrat_path], timeout, bin_dir, budget)


def cake_lpr(cnf_path: str, lrat_path: str, *, timeout: float = 3600.0,
             bin_dir=None, budget=None) -> CheckResult:
    return _run("cake_lpr", [cnf_path, lrat_path], timeout, bin_dir, budget)
