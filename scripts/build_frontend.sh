#!/usr/bin/env bash
# Build the React frontend and place the dist/ inside frontend/
# Run from the project root: bash scripts/build_frontend.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"

echo "── Building React frontend ────────────────────────────────────"
cd "$FRONTEND"
npm install
npm run build
echo "── Build complete → frontend/dist/ ───────────────────────────"
ls -lh "$FRONTEND/dist"
