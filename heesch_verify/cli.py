"""CLI: verify a shape file -> exit code + JSON on stdout."""

from __future__ import annotations

import argparse
import json
import sys

from .result import VerifyError
from .witness import VerifyConfig, verify_witness


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="heesch_verify", description="Heesch witness verifier")
    ap.add_argument("file", help="shape file (heesch-sat text format)")
    ap.add_argument("--strict", action="store_true", help="reject weaker-than-claimed witnesses")
    ap.add_argument("--no-reflections", action="store_true", help="ban reflected placements")
    ap.add_argument(
        "--emit-epoch",
        metavar="OUT",
        help="after successful verification, write an Epoch-compatible copy (defect block stripped)",
    )
    args = ap.parse_args(argv)

    try:
        with open(args.file, "r", encoding="utf-8", errors="strict") as fh:
            text = fh.read()
    except OSError as e:
        print(json.dumps({"error": "IO", "message": str(e)}))
        return 1
    except UnicodeDecodeError as e:
        print(json.dumps({"error": "PARSE_SYNTAX", "message": f"not utf-8: {e}"}))
        return 1

    config = VerifyConfig(
        strict_claims=args.strict,
        allow_reflections=not args.no_reflections,
    )
    try:
        outcome = verify_witness(text, config)
    except VerifyError as e:
        print(json.dumps(e.to_json(), sort_keys=True))
        return 1

    if args.emit_epoch:
        # Strip the optional defect block (§9.2.7): everything from the
        # #DEFECT marker line onward. Only a verified witness is exported —
        # an invalid submission must not leave an "Epoch-compatible" file.
        out_lines = []
        for line in text.split("\n"):
            toks = line.split()
            if toks and toks[0] == "#DEFECT":  # exact marker token (audit V7)
                break
            out_lines.append(line)
        body = "\n".join(out_lines).rstrip("\n") + "\n"
        try:
            with open(args.emit_epoch, "w", encoding="ascii", newline="\n") as fh:
                fh.write(body)
        except (OSError, UnicodeEncodeError) as e:
            print(json.dumps({"error": "IO", "message": f"emit-epoch: {e}"}))
            return 1

    print(outcome.result.to_json_str())
    return 0


if __name__ == "__main__":
    sys.exit(main())
