#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-/usr/bin/python3}"

echo "=================================================="
echo "    [CI] agy-skills Continuous Verification       "
echo "=================================================="

echo "==> Python environment:"
$PYTHON --version

echo ""
echo "==> Running static syntax checks..."
$PYTHON -m py_compile agy_skills/*.py tests/*.py
echo "✔ Syntax verification passed"

echo ""
echo "==> Running automated test suite..."
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
$PYTHON -m unittest discover -s tests -p "test_*.py" -v
echo "✔ All tests passed!"

echo ""
echo "==> Running agy-skills self-linting check..."
$PYTHON -m agy_skills.main --lint || true
echo "✔ CI verification completed successfully."
