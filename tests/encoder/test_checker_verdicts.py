"""Review finding 3: per-checker line-anchored verdict matching.

The six-way matrix (each checker x pass/fail) plus the traps: drat-trim's
non-verdict "c VERIFIED derivation" progress line must not satisfy any
checker, and NOT VERIFIED overrides everything."""

import subprocess
import types

import pytest

from conftest import ROOT  # noqa: F401

from heesch_encoder.proofcheck import checkers as ck


def _fake_run(stdout):
    def run(cmd, *args, **kwargs):
        # Tolerant of _run's kwargs (capture_output, text, timeout, and the
        # audit F3/F4 additions stdin=DEVNULL, errors="replace").
        return types.SimpleNamespace(stdout=stdout, stderr="", returncode=0)
    return run


@pytest.fixture
def with_binary(monkeypatch, tmp_path):
    """Pretend all checker binaries exist so _run reaches verdict parsing."""
    class FakePath:
        def __init__(self, name):
            self.name = name
        def exists(self):
            return True
        def __str__(self):
            return self.name

    monkeypatch.setattr(ck, "_BIN", types.SimpleNamespace(
        __truediv__=lambda self, name: FakePath(name)))
    # _BIN / name uses __truediv__ on the namespace instance
    class BinDir:
        def __truediv__(self, name):
            return FakePath(name)
    monkeypatch.setattr(ck, "_BIN", BinDir())
    return monkeypatch


CASES = [
    # (checker fn, name, stdout, expected VERIFIED?)
    (ck.drat_trim, ("c", "p"), "c parsing...\ns VERIFIED\n", True),
    (ck.drat_trim, ("c", "p"), "s NOT VERIFIED\n", False),
    # The trap: derivation progress line alone is NOT a verdict.
    (ck.drat_trim, ("c", "p"),
     "c VERIFIED derivation: all lemmas preserve satisfiability\n", False),
    (ck.lrat_check, ("c", "p"), "c parsing\nc VERIFIED\n", True),
    (ck.lrat_check, ("c", "p"), "c NOT VERIFIED\n", False),
    # lrat-check's success line must not be accepted for drat-trim...
    (ck.drat_trim, ("c", "p"), "c VERIFIED\n", False),
    # ...and vice versa.
    (ck.lrat_check, ("c", "p"), "s VERIFIED\n", False),
    (ck.cake_lpr, ("c", "p"), "s VERIFIED UNSAT\n", True),
    (ck.cake_lpr, ("c", "p"), "c error: proof step failed\n", False),
    # NOT VERIFIED anywhere overrides an (impossible) later success line.
    (ck.drat_trim, ("c", "p"), "s NOT VERIFIED\ns VERIFIED\n", False),
    # \r-prefixed lines (drat-trim uses \r overwrites) still match.
    (ck.drat_trim, ("c", "p"), "\rs VERIFIED\n", True),
]


@pytest.mark.parametrize("fn,args,stdout,expect", CASES,
                         ids=[f"{c[0].__name__}-{i}" for i, c in enumerate(CASES)])
def test_verdict_matrix(fn, args, stdout, expect, with_binary, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout))
    result = fn(*args)
    got = result.status is ck.CheckStatus.VERIFIED
    assert got == expect, f"{fn.__name__} on {stdout!r}: {result.status}"


def test_cake_lpr_heap_exhaustion_is_resource_not_verdict(monkeypatch, tmp_path):
    """A checker running out of its fixed heap says nothing about the proof:
    RESOURCE_EXCEEDED, never NOT_VERIFIED (seen on the benchmark runner for a
    record-scale LRAT: 'CakeML heap space exhausted.')."""
    monkeypatch.setattr(ck, "_BIN", tmp_path)
    ck.checker_path("cake_lpr", tmp_path).write_text("")  # .exe on Windows
    seen = {}

    def run(cmd, *a, **k):
        seen["cmd"] = cmd

        class P:
            stdout = ""
            stderr = "CakeML heap space exhausted.\n"
        return P()

    monkeypatch.setattr(ck.subprocess, "run", run)
    r = ck.cake_lpr("f.cnf", "p.lrat")
    assert r.status is ck.CheckStatus.RESOURCE_EXCEEDED
    assert "heap" in r.detail
    # The wrapper sizes the heap explicitly instead of trusting the 4 GB default.
    assert any(str(x).startswith("--CML_HEAP_SIZE=") for x in seen["cmd"])
    assert any(str(x).startswith("--CML_STACK_SIZE=") for x in seen["cmd"])
    heap = int([x for x in seen["cmd"] if str(x).startswith("--CML_HEAP_SIZE=")][0].split("=")[1])
    assert heap >= ck.CAKE_LPR_HEAP_MB_MIN


def test_cake_lpr_heap_override(monkeypatch):
    monkeypatch.setenv("HEESCH_CAKE_HEAP_MB", "6000")
    assert ck.cake_lpr_heap_mb() == 6000
