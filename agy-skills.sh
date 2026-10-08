#!/bin/sh
# agy-skills — Curses-based Antigravity Skills & Rules Manager
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$DIR:$PYTHONPATH"
PYTHON="${PYTHON:-/usr/bin/python3}"

exec "$PYTHON" -m agy_skills.main "$@"
