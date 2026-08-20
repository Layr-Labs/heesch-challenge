"""V7/V8 regression (2026-08 audit, docs/audits/2026-08-vuln-review.md).

V7: the #DEFECT block was detected by startswith('#DEFECT'), so '#DEFECTXYZ …'
    parsed as a defect block — out-of-spec bytes admitted to the record (and to
    --emit-epoch exports). The marker token must equal '#DEFECT' exactly.
V8: assert_exhausted never enforced MAX_LINE_CHARS, so an oversized whitespace
    trailing line was silently accepted and the defect peek swallowed the
    "line too long" error as generic trailing garbage.
"""

import pytest

from util import ROOT  # noqa: F401

from heesch_verify import VerifyError, parse_submission, verify_witness
from heesch_verify.parse import MAX_LINE_CHARS
from heesch_verify.patch import required_set
from heesch_verify.result import ErrorCode

BASELINE = (ROOT / "submission" / "best.heesch").read_text(encoding="ascii")


def _defect_witness(marker: str) -> str:
    out = verify_witness(BASELINE)
    r = len(required_set(out.hc_corona.patch_cells, out.contact))
    return BASELINE.rstrip("\n") + f"\n{marker} 2 {r} {r} {r}\n0\n"


def test_exact_defect_marker_accepted():
    sub = parse_submission(_defect_witness("#DEFECT"))
    assert sub.defect is not None


def test_bogus_defect_marker_rejected():
    # '#DEFECTXYZ' is not the marker token, so it is not a defect block; it
    # lands as trailing garbage rather than being scored.
    with pytest.raises(VerifyError) as ei:
        parse_submission(_defect_witness("#DEFECTXYZ"))
    assert ei.value.code is ErrorCode.PARSE_SYNTAX


def test_oversized_trailing_line_rejected():
    text = BASELINE.rstrip("\n") + "\n" + " " * (MAX_LINE_CHARS + 1)
    with pytest.raises(VerifyError) as ei:
        parse_submission(text)
    assert ei.value.code is ErrorCode.PARSE_SYNTAX
    assert "too long" in ei.value.message


def test_oversized_whitespace_after_defect_block_rejected():
    # Exercises assert_exhausted's new length check (audit V8): a valid defect
    # block fully parses, then an oversized whitespace-only trailing line must
    # still be rejected — previously strip() made it falsy and it was accepted.
    text = _defect_witness("#DEFECT").rstrip("\n") + "\n" + " " * (MAX_LINE_CHARS + 1)
    with pytest.raises(VerifyError) as ei:
        parse_submission(text)
    assert ei.value.code is ErrorCode.PARSE_SYNTAX
    assert "too long" in ei.value.message
