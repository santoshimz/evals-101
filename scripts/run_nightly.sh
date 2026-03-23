#!/usr/bin/env bash
set -euo pipefail

. .venv/bin/activate
python -m evals_101.deepeval_runner --dataset datasets/nightly/tool_use.json --system mcp-201
