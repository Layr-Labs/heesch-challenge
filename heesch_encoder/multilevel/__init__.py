"""heesch_encoder.multilevel — the v2 multi-level encoder.

Implements heesch-multilevel-encoder-spec.md: one formula F(S, m) whose UNSAT
proves no weak m-configuration exists (obligations M1–M9). Everything here is
additive to v1: the v1 modules, epoch-1 manifest, and their digests are
byte-stable.
"""

ENCODER_VERSION_V2 = "heesch-encoder/v2"
EPOCH_V2 = 2
