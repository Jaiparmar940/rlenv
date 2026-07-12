#!/usr/bin/env bash
# Cheap post-change check: ONE model x all 3 scenarios x 3 epochs, uncoached.
# Do not run the full model matrix per tweak — this is the gate before it.
#
#   scripts/smoke_eval.sh                          # default mid-tier model
#   scripts/smoke_eval.sh anthropic/claude-sonnet-5
set -euo pipefail

MODEL="${1:-anthropic/claude-haiku-4-5}"
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

"$PY" scripts/run_evals.py \
  --models "$MODEL" \
  --epochs 3 \
  --prompt-variant uncoached \
  --out results-smoke

echo
cat results-smoke/results.md
