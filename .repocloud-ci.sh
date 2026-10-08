#!/bin/sh
# repocloud Native CI Pipeline Definition
set -e

echo "=================================================="
echo "    repocloud CI Runner: agy-skills Pipeline      "
echo "=================================================="

# Run test harness
./scripts/ci.sh
