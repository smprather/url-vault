#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

if [[ -n "${WSL_EXE:-}" ]]; then
  :
elif [[ -x /c/Windows/System32/wsl.exe ]]; then
  WSL_EXE=/c/Windows/System32/wsl.exe
elif command -v wsl.exe >/dev/null 2>&1; then
  WSL_EXE=$(command -v wsl.exe)
else
  echo "wsl.exe was not found. Install WSL or set WSL_EXE before running this script." >&2
  exit 1
fi

if ! command -v cygpath >/dev/null 2>&1; then
  echo "cygpath is required when running from Git Bash." >&2
  exit 1
fi

WINDOWS_REPO_ROOT=$(cygpath -w "$REPO_ROOT")
WINDOWS_REPO_ROOT=${WINDOWS_REPO_ROOT//\\//}
WSL_DRIVE_LETTER=${WINDOWS_REPO_ROOT:0:1}
WSL_DRIVE_LETTER=${WSL_DRIVE_LETTER,,}
WSL_PATH_SUFFIX=${WINDOWS_REPO_ROOT:2}
WSL_REPO_ROOT="/mnt/$WSL_DRIVE_LETTER$WSL_PATH_SUFFIX"

"$WSL_EXE" bash -lc "set -euo pipefail; exec bash \"$WSL_REPO_ROOT/scripts/run-e2e-clone-smoke.wsl.sh\" \"$WSL_REPO_ROOT\""
