#!/usr/bin/env bash
set -euo pipefail

# Run from repository root so package imports resolve deterministically.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" python -m deploy_local.doctor
