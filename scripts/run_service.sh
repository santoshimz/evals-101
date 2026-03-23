#!/usr/bin/env bash
set -euo pipefail

. .venv/bin/activate
python -m evals_101.api
