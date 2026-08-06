#!/usr/bin/env bash
# Yukon benchmark step. Must write .yukon/score.json with a finite numeric
# "score", or exit nonzero. Never write a fake score on failure.
set -euo pipefail

python -m harness.verify
