#!/usr/bin/env bash
# Yukon setup step. Must leave the environment ready for .yukon/run.sh.
set -euo pipefail

python -m pip install --upgrade pip
pip install .
