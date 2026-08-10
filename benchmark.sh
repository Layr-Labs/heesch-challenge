#!/usr/bin/env bash
# Benchmark a submission.
#
#   1. Wipe the stale score.json before ANY fallible work, so a failed run
#      can never expose a result from an older invocation.
#   2. Resolve the venv created by ./setup.sh; fail closed if absent
#      (environment does not persist between Yukon's setup and benchmark
#      commands).
#   3. Run `python -I -m harness.verify`. The harness executes NO competitor
#      code — the submission is a plain-text shape file — but the file is
#      hostile input to our own parser, so on Linux the verify stage runs
#      under bubblewrap (read-only filesystem, no network, no capabilities,
#      writable only in a throwaway scratch dir) and on macOS under
#      sandbox-exec. Defense in depth against parser-exploit classes; if no
#      sandbox is available we warn and run unconfined (dev fallback).
#   4. The harness writes score.json into the scratch dir
#      (HEESCH_SCORE_DIR); it is copied to ./score.json only after success.
#      Nonzero exit therefore always means: no score file.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${root}"

# 1. Clean slate (review finding 2; flock pattern).
rm -f score.json

# 2. Venv from setup.sh.
if [[ -x "${root}/.venv-bench/bin/python" ]]; then
  vpy="${root}/.venv-bench/bin/python"
elif [[ -x "${root}/.venv-bench/Scripts/python.exe" ]]; then
  vpy="${root}/.venv-bench/Scripts/python.exe"
else
  echo "!! venv missing; run ./setup.sh first" >&2
  exit 1
fi

# 3. Sandboxed verification.
scratch="$(cd "$(mktemp -d)" && pwd -P)"
cleanup() { [[ -z "${scratch:-}" ]] || rm -rf "${scratch}" 2>/dev/null || true; }
trap cleanup EXIT
chmod 755 "${scratch}"

run_verify=()
if command -v bwrap >/dev/null 2>&1; then
  run_verify=(
    bwrap
      --ro-bind / / --dev /dev --ro-bind /proc /proc
      --bind "${scratch}" "${scratch}"
      --setenv TMPDIR "${scratch}"
      --setenv HEESCH_SCORE_DIR "${scratch}"
      --setenv PYTHONHASHSEED 0
      --chdir "${root}"
      --unshare-net --unshare-ipc --unshare-uts --unshare-cgroup
      --cap-drop ALL --new-session --die-with-parent
      -- "${vpy}" -I -m harness.verify
  )
elif [[ "$(uname -s)" == "Darwin" ]] && command -v sandbox-exec >/dev/null 2>&1; then
  profile="(version 1)(allow default)(deny network*)(deny file-write*)(allow file-write* (subpath \"${scratch}\"))(allow file-write* (subpath \"/dev\"))"
  run_verify=(
    sandbox-exec -p "${profile}"
      /usr/bin/env TMPDIR="${scratch}" HEESCH_SCORE_DIR="${scratch}" PYTHONHASHSEED=0
      "${vpy}" -I -m harness.verify
  )
else
  echo "!! no sandbox available (bubblewrap/sandbox-exec); running verify UNCONFINED (dev fallback)" >&2
  run_verify=(
    env TMPDIR="${scratch}" HEESCH_SCORE_DIR="${scratch}" PYTHONHASHSEED=0
    "${vpy}" -I -m harness.verify
  )
fi

"${run_verify[@]}"

# 4. Copy the score out only after full success.
if [[ ! -s "${scratch}/score.json" ]]; then
  echo "!! harness exited 0 but produced no score.json" >&2
  exit 1
fi
cp "${scratch}/score.json" "${root}/score.json"
