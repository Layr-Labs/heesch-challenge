"""Checker subprocess wrappers. Success is the literal `s VERIFIED` line on
stdout — exit codes are NOT a reliable signal from drat-trim. Timeout / OOM
map to RESOURCE_EXCEEDED (requeueable), everything else to failure."""

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


def _run(name: str, args: list[str], timeout: float) -> CheckResult:
    exe = _BIN / (name + (".exe" if os.name == "nt" else ""))
    if not exe.exists():
        return CheckResult(name, CheckStatus.CHECKER_MISSING, 0.0,
                           f"{exe} not built (tools/build_checkers.sh)")
    import time

    t0 = time.time()
    try:
        proc = subprocess.run(
            [str(exe), *args], capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, time.time() - t0,
                           "wall-clock timeout")
    except MemoryError:
        return CheckResult(name, CheckStatus.RESOURCE_EXCEEDED, time.time() - t0, "oom")
    dt = time.time() - t0
    out = proc.stdout + "\n" + proc.stderr
    if "s VERIFIED" in out:
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
