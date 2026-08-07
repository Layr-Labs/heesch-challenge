"""§11 freeze assertions: live-code constants must match the epoch manifest;
golden CNF digests catch semantic drift the constants digest can't see;
the manifest itself is immutability-pinned."""

import hashlib
import json
import pathlib

from conftest import ROOT  # noqa: F401

from heesch_encoder import manifest

GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


def test_live_constants_match_epoch():
    epoch = manifest.load_epoch(1)
    assert epoch["frozen_constants_digest"] == manifest.constants_digest(), (
        "encoder constants drifted from epoch-1.json — a point group, "
        "ordering, threshold or emission rule changed. That is a NEW EPOCH "
        "(heesch-encoder/v2 + re-verification), never an in-place edit."
    )


def test_epoch_fields():
    epoch = manifest.load_epoch(1)
    for key in ("encoder_version", "epoch", "amo_threshold", "placement_order",
                "cell_order", "dimacs_profile", "digest_algo", "point_groups",
                "checkers", "frozen_constants_digest"):
        assert key in epoch, f"epoch manifest missing {key}"
    assert epoch["encoder_version"] == "heesch-encoder/v1"
    assert epoch["epoch"] == 1


def test_manifest_immutability_pin():
    """epoch-1.json's own sha256 is committed; editing the manifest without
    adding epoch-2.json fails here."""
    p = manifest.EPOCH_DIR / "epoch-1.json"
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    pin_file = GOLDEN_DIR / "manifest.sha256"
    if not pin_file.exists():
        pin_file.parent.mkdir(parents=True, exist_ok=True)
        pin_file.write_text(digest + "\n")
    assert pin_file.read_text().strip() == digest, (
        "epoch-1.json was edited. Epoch manifests are immutable — write "
        "epoch-2.json and bump the version instead."
    )


def test_live_constants_v2_match_epoch2():
    epoch = manifest.load_epoch(2)
    assert epoch["frozen_constants_digest"] == manifest.constants_digest_v2(), (
        "v2 encoder constants drifted from epoch-2.json — that is heesch-"
        "encoder/v3 + re-verification, never an in-place edit."
    )
    assert epoch["encoder_version"] == "heesch-encoder/v2"
    assert epoch["epoch"] == 2
    for key in ("families_active", "weak_bound_B", "level_window",
                "universe_construction", "feasibility_band", "checkers"):
        assert key in epoch, f"epoch-2 manifest missing {key}"
    assert epoch["weak_bound_B"] == 0
    assert epoch["families_active"] == ["1", "2", "4", "5", "6"]


def test_epoch2_manifest_immutability_pin():
    p = manifest.EPOCH_DIR / "epoch-2.json"
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    pin_file = GOLDEN_DIR / "manifest-2.sha256"
    if not pin_file.exists():
        pin_file.write_text(digest + "\n")
    assert pin_file.read_text().strip() == digest, (
        "epoch-2.json was edited. Epoch manifests are immutable — write "
        "epoch-3.json and bump the version instead."
    )


def test_golden_digests_present_and_stable():
    goldens = json.loads((GOLDEN_DIR / "digests.json").read_text())
    assert len(goldens) >= 10
    # Regeneration equality is asserted per-fixture in test_determinism.py;
    # here just pin that the golden file itself is tracked and non-empty.
    for name, digest in goldens.items():
        assert len(digest) == 64, f"{name}: malformed digest"
