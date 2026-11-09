#!/usr/bin/env bash
# Runs the catalog's own tests: the rule script and the style tools.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s tools/tests -t tools -v
