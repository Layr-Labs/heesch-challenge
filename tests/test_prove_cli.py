"""tools/prove.py as a CLI (audit 2026-08-19 High 2): an illegal `--out` is
refused BEFORE any encoding, nothing is ever written outside the submission
directory, best.heesch is never the proof target, every intermediate lives in
a private temp dir that is removed on every exit path, and the outputs are
installed atomically only after the new #PROOF block parses."""

import importlib.util
import os
import sys

import pytest

from util import ROOT, omino11_hc1

from heesch_verify.parse import parse_submission


def _load_prove():
    spec = importlib.util.spec_from_file_location("prove_cli", ROOT / "tools" / "prove.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def prove():
    return _load_prove()


@pytest.fixture
def subdir(tmp_path):
    d = tmp_path / "submission"
    d.mkdir()
    (d / "best.heesch").write_text(omino11_hc1(), encoding="ascii")
    return d


def _never_encode(monkeypatch, prove):
    def boom(*a, **k):
        raise AssertionError("encoder was invoked before --out validation")
    monkeypatch.setattr(prove, "encode_multilevel_stream", boom)


@pytest.mark.parametrize("out", [
    "../escaped.lrat.xz",
    "best.heesch",
    "sub/x.lrat.xz",
    "proof.drat.xz",          # suffix does not match --format lrat
    ".hidden.lrat.xz",
    "-S.lrat.xz",
    "x" * 70 + ".lrat.xz",
])
def test_illegal_out_is_refused_before_any_work(prove, subdir, monkeypatch, capsys, out):
    _never_encode(monkeypatch, prove)
    before = sorted(os.listdir(subdir.parent))
    shape_before = (subdir / "best.heesch").read_bytes()
    rc = prove.main([str(subdir / "best.heesch"), "--out=" + out])
    assert rc == 1
    assert "error:" in capsys.readouterr().err
    assert (subdir / "best.heesch").read_bytes() == shape_before
    assert sorted(os.listdir(subdir.parent)) == before          # nothing escaped
    assert sorted(os.listdir(subdir)) == ["best.heesch"]         # nothing written, no temp dir


def test_existing_output_needs_force(prove, subdir, monkeypatch, capsys):
    _never_encode(monkeypatch, prove)
    # --format drat: its default name needs no drat-trim (which may not be
    # built, e.g. on Windows CI, where lrat would fall back to drat).
    (subdir / "proof.drat.xz").write_bytes(b"old")
    rc = prove.main([str(subdir / "best.heesch"), "--format", "drat"])
    assert rc == 1
    assert "--force" in capsys.readouterr().err
    assert (subdir / "proof.drat.xz").read_bytes() == b"old"


def test_non_ascii_shape_refused_up_front(prove, subdir, monkeypatch, capsys):
    _never_encode(monkeypatch, prove)
    (subdir / "best.heesch").write_bytes(omino11_hc1().encode() + "# café\n".encode("utf-8"))
    rc = prove.main([str(subdir / "best.heesch")])
    assert rc == 1
    assert "ASCII" in capsys.readouterr().err


def _need_solving():
    if not (ROOT / "tools" / "bin" / "drat-trim").exists():
        pytest.skip("tools/bin/drat-trim not built")
    pytest.importorskip("pysat")


def test_failed_solver_leaves_no_leftovers(prove, subdir, capsys):
    _need_solving()
    rc = prove.main([str(subdir / "best.heesch"), "--solver", "no-such-solver"])
    assert rc == 1
    assert sorted(os.listdir(subdir)) == ["best.heesch"]
    assert "#PROOF" not in (subdir / "best.heesch").read_text()


def test_happy_path_installs_atomically_and_cleans_up(prove, subdir):
    _need_solving()
    # The 11-omino has Hh = 2 (Kaplan), so F(S,2) is SAT and F(S,3) is UNSAT.
    assert prove.main([str(subdir / "best.heesch"), "--solver", "cadical153", "--no-xz"]) == 2
    assert sorted(os.listdir(subdir)) == ["best.heesch"]        # SAT path cleaned up too
    rc = prove.main([str(subdir / "best.heesch"), "--m", "3", "--solver", "cadical153", "--no-xz"])
    assert rc == 0
    names = sorted(os.listdir(subdir))
    assert names == ["best.heesch", "core.txt", "proof.lrat"], names   # no .prove-* left behind
    sub = parse_submission((subdir / "best.heesch").read_text(encoding="ascii"))
    assert sub.proof is not None and sub.proof.file_name == "proof.lrat"
    assert sub.proof.core_file == "core.txt"
    # Re-running without --force refuses to clobber the installed proof.
    assert prove.main([str(subdir / "best.heesch"), "--m", "3", "--solver", "cadical153", "--no-xz"]) == 1
    # --force re-proves over the existing files.
    assert prove.main([str(subdir / "best.heesch"), "--m", "3", "--solver", "cadical153",
                       "--no-xz", "--force"]) == 0
