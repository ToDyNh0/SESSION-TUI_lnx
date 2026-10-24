#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Session TUI - run from source, no build needed.
#  The first run creates .venv and installs the dependencies.
#
#    ./run.sh                     opens the TUI
#    ./run.sh send 05ab... "hi"   any command, same as dist/session-tui
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    PY="${PYTHON:-python3}"
    if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        echo "Python 3.10 or newer is required (set PYTHON=/path/to/python3.x to pick one)"
        exit 1
    fi
    echo "first run: creating .venv and installing dependencies ..."
    "$PY" -m venv .venv || {
        echo "could not create the venv -- Debian/Ubuntu: sudo apt install python3-venv"
        exit 1
    }
    .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt
fi
exec .venv/bin/python main.py "$@"
