#!/usr/bin/env bash
# Yukon benchmark step — keep aligned with benchmark.json benchmarkCommand.
# Writes .yukon/score.json with a finite numeric "score" on success, exits
# nonzero otherwise; never writes a fake score. -P prevents anything under
# the competitor-editable submission/ directory from shadowing installed
# packages.
set -euo pipefail
PYTHONHASHSEED=0 python -P -m harness.verify
