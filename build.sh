#!/usr/bin/env bash
# build.sh -- runs the same checks CI/a deploy should gate on, in order,
# stopping at the first failure (set -e): lint, format (auto-fix), format
# check (verify nothing was left unformatted), then the production build.
set -e

cd "$(dirname "$0")"

echo "==> Lint (eslint)"
npm run lint

echo "==> Format (prettier --write)"
npm run format

echo "==> Format check (prettier --check)"
npm run format:check

echo "==> Build (next build)"
npm run build

echo "==> All checks passed, build complete."
