#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Session TUI - Linux build
#  Builds dist/session-tui: one file, runs without Python installed.
#  Needs only Python 3.10+ with venv (Debian/Ubuntu: sudo apt install python3-venv).
#
#    ./build.sh          build the binary
#    ./build.sh test     run the offline tests first, then build
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    echo "Python 3.10 or newer is required (set PYTHON=/path/to/python3.x to pick one)"
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    echo "[1/4] creating the virtual environment .venv ..."
    "$PY" -m venv .venv || {
        echo "could not create the venv -- Debian/Ubuntu: sudo apt install python3-venv"
        exit 1
    }
else
    echo "[1/4] using the existing .venv"
fi
VENV_PY=.venv/bin/python

echo "[2/4] installing dependencies ..."
"$VENV_PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt -r requirements-build.txt

if [ "${1:-}" = "test" ]; then
    echo "[3/4] running the offline tests ..."
    "$VENV_PY" selftest.py
else
    echo "[3/4] tests skipped (use './build.sh test' to run them)"
fi

echo "[4/4] building dist/session-tui ..."
"$VENV_PY" build_exe.py

echo
echo "done: dist/session-tui"
echo "try:  ./dist/session-tui --help"
