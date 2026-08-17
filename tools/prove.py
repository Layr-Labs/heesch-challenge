"""Produce the non-tiler proof a submission needs (architecture §13.2).

The harness is fail-closed: a shape outside Kaplan's census scores only if
best.heesch carries a `#PROOF` block naming a machine-checkable UNSAT proof of
the multilevel formula F(S, m), m >= hh + 1. This tool builds that proof with
the SAME encoder call the harness makes, solves it with CaDiCaL (pysat) with
proof logging on, writes the DRAT (optionally converted to LRAT with the
vendored drat-trim), computes the digests and rewrites the `#PROOF` block.

    python tools/prove.py submission/best.heesch                # m = hh + 1
    python tools/prove.py submission/best.heesch --m 3 --xz
    python tools/prove.py submission/best.heesch --format lrat --check

Requires the `prove` extra (`pip install -e '.[prove]'`, i.e. python-sat).
Exit codes: 0 proof written; 2 F(S, m) is SATISFIABLE (no proof exists at
this m — either the shape has a deeper corona than your witness shows or it
is a tiler); 1 any other failure.

`--check` runs the finished submission through the same ProofCarryingGate the
harness uses (checkers from $HEESCH_CHECKER_DIR or ./tools/bin; cake_lpr is
x86-64-Linux-only, so on other hosts expect CHECKER_UNAVAILABLE — the record
tier is checked on the Linux benchmark runner).
"""

from __future__ import annotations

import argparse
import hashlib
import lzma
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from heesch_verify.canonical import canonical_form  # noqa: E402
from heesch_verify.parse import (  # noqa: E402
    PROOF_ENCODER_EPOCH, PROOF_ENCODER_VERSION, PROOF_SCHEMA_VERSION,
)
from heesch_verify.proofgate import HARNESS_PROOF_BAND, in_harness_band  # noqa: E402
from heesch_verify.witness import VerifyConfig, verify_witness  # noqa: E402
from heesch_encoder.multilevel.api import encode_multilevel, in_feasibility_band  # noqa: E402


def strip_proof_block(text: str) -> str:
    out = []
    for line in text.split("\n"):
        toks = line.split()
        if toks and toks[0] == "#PROOF":
            break
        out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


def proof_block(m, cnf_digest, num_vars, num_clauses, name, fmt, comp, payload_sha) -> str:
    return (
        f"#PROOF {PROOF_SCHEMA_VERSION}\n"
        f"encoder {PROOF_ENCODER_VERSION} {PROOF_ENCODER_EPOCH} {m}\n"
        f"cnf {cnf_digest} {num_vars} {num_clauses}\n"
        f"file {name} {fmt} {comp} {payload_sha}\n"
    )


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="prove.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("shape_file", help="submission/best.heesch")
    ap.add_argument("--m", type=int, default=None, help="proof level (default hh_verified + 1)")
    ap.add_argument("--format", choices=("drat", "lrat"), default="drat")
    ap.add_argument("--xz", action="store_true", help="store the proof xz-compressed")
    ap.add_argument("--out", default=None, help="proof file name (basename, next to the shape file)")
    ap.add_argument("--solver", default="cadical195")
    ap.add_argument("--check", action="store_true", help="run the harness's ProofCarryingGate afterwards")
    args = ap.parse_args(argv)

    shape_path = pathlib.Path(args.shape_file).resolve()
    text = shape_path.read_text(encoding="utf-8")
    body = strip_proof_block(text)
    outcome = verify_witness(body, VerifyConfig())
    sub = outcome.submission
    hh = outcome.result.hh_verified
    m = args.m if args.m is not None else hh + 1
    if m < hh + 1:
        print(f"error: m={m} but the witness verifies hh={hh}; need m >= {hh + 1}", file=sys.stderr)
        return 1
    n = len(sub.cells)
    if not in_feasibility_band(n, m):
        print(f"error: ({n} cells, m={m}) is outside the epoch-2 feasibility band", file=sys.stderr)
        return 1
    if not in_harness_band(n, m):
        print(f"warning: ({n} cells, m={m}) is outside the in-harness proof band "
              f"{HARNESS_PROOF_BAND}; the harness will answer RESOURCE_EXCEEDED", file=sys.stderr)

    tile = frozenset(canonical_form(sub.cells, sub.grid, True))
    print(f"encoding F(S,{m}) for {n} cells ...", flush=True)
    enc = encode_multilevel(tile, sub.grid, outcome.contact, m)
    print(f"  {enc.num_vars} vars, {enc.num_clauses} clauses, digest {enc.digest[:16]}…", flush=True)

    try:
        from pysat.solvers import Solver
    except ImportError:
        print("error: python-sat not installed (pip install -e '.[prove]')", file=sys.stderr)
        return 1
    print(f"solving with {args.solver} (proof logging on) ...", flush=True)
    with Solver(name=args.solver, bootstrap_with=[list(c) for c in enc.formula.clauses],
                with_proof=True) as s:
        sat = s.solve()
        if sat:
            print(f"SAT: F(S,{m}) is satisfiable — a weak {m}-configuration exists, so no "
                  f"UNSAT proof at this m. Try a deeper witness / larger m, or the shape may tile.")
            return 2
        proof_lines = s.get_proof()

    name = args.out or ("proof." + args.format + (".xz" if args.xz else ""))
    dest_dir = shape_path.parent
    tmpdir = dest_dir / ".prove-tmp"
    tmpdir.mkdir(exist_ok=True)
    drat_path = tmpdir / "proof.drat"
    drat_path.write_text("\n".join(proof_lines) + "\n0\n", encoding="ascii")
    payload_path = drat_path
    if args.format == "lrat":
        drat_trim = pathlib.Path(os.environ.get("HEESCH_CHECKER_DIR") or (ROOT / "tools" / "bin")) / "drat-trim"
        if not drat_trim.exists():
            print(f"error: {drat_trim} not built (bash tools/build_checkers.sh)", file=sys.stderr)
            return 1
        cnf_path = tmpdir / "formula.cnf"
        cnf_path.write_bytes(enc.dimacs)
        lrat_path = tmpdir / "proof.lrat"
        proc = subprocess.run([str(drat_trim), str(cnf_path), str(drat_path), "-L", str(lrat_path)],
                              capture_output=True, text=True, errors="replace", stdin=subprocess.DEVNULL)
        if not any(ln.strip() == "s VERIFIED" for ln in proc.stdout.splitlines()):
            print("error: drat-trim did not verify the DRAT while converting to LRAT:\n" + proc.stdout[-800:],
                  file=sys.stderr)
            return 1
        payload_path = lrat_path
    payload_sha = sha256_file(payload_path)
    final = dest_dir / name
    if args.xz:
        with open(payload_path, "rb") as src, lzma.open(final, "wb", preset=6) as dst:
            for chunk in iter(lambda: src.read(1 << 20), b""):
                dst.write(chunk)
    else:
        os.replace(payload_path, final)
    for leftover in tmpdir.iterdir():
        leftover.unlink()
    tmpdir.rmdir()

    block = proof_block(m, enc.digest, enc.num_vars, enc.num_clauses, name, args.format,
                        "xz" if args.xz else "none", payload_sha)
    new_text = body + block
    from heesch_verify.parse import parse_submission
    parse_submission(new_text)  # self-check: the block we wrote is grammatical
    shape_path.write_text(new_text, encoding="ascii", newline="\n")
    print(f"wrote {final} ({final.stat().st_size} bytes) and the #PROOF block in {shape_path.name}")
    print(f"  m={m}: UNSAT F(S,{m}) => Hh <= {m - 1}"
          + (" — exact (m = hh + 1)" if m == hh + 1 else " — non-tiler certificate (lower bound stays)"))

    if args.check:
        from heesch_verify.proofgate import ProofCarryingGate

        outcome2 = verify_witness(new_text, VerifyConfig())
        checker_dir = pathlib.Path(os.environ.get("HEESCH_CHECKER_DIR") or (ROOT / "tools" / "bin"))
        verdict = ProofCarryingGate(shape_path.parent, checker_dir).check(outcome2.submission, outcome2)
        print("gate:", verdict.to_json())
        return 0 if verdict.code is None else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
