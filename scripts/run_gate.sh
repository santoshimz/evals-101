#!/usr/bin/env bash
set -euo pipefail

. .venv/bin/activate
python -m evals_101.cli --dataset datasets/gate/workflow_routing.json --system mcp-201
