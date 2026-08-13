#!/usr/bin/env bash
# Builds and pushes both CareConnect images to a container registry --
# Option A manual deployment (build locally, push, `docker pull` on the
# VPS), not Coolify's auto-build. Exists so the two-image build+tag+push
# sequence is never typed out by hand (and therefore never half-done or
# mistagged) -- see DEPLOYMENT.md's "Manual image-based deployment" section
# for the full workflow this script is one step of.
#
# Every image gets TWO tags: a version tag (git describe --always --dirty --
# an annotated tag if one exists, otherwise the short commit hash, "-dirty"
# appended if the working tree has uncommitted changes) AND `latest`. The
# version tag is what actually matters for a real deploy -- it's how you
# roll back to a specific build; `latest` is a convenience for
# docker-compose.prod.yml's default and quick manual testing, not a
# promise of what's currently running in production.
#
# Usage:
#   ./docker-publish.sh                          # build + push both images
#   ./docker-publish.sh --no-push                # build + tag only, skip the push (e.g. to test the build)
#   REGISTRY=someotheruser ./docker-publish.sh   # override the default Docker Hub namespace
#
# Required before pushing: `docker login -u daaprime` (Docker Hub -- no
# registry hostname needed, docker.io is the CLI's default) with either your
# Docker Hub password or, better, an Access Token (Docker Hub -> Account
# Settings -> Security -> New Access Token) instead of the real password --
# see DEPLOYMENT.md.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

REGISTRY="${REGISTRY:-daaprime}"
# The frontend bakes this into its client JS bundle at build time (Next.js's
# NEXT_PUBLIC_* rule -- see frontend/Dockerfile's own comment) -- it MUST be
# the backend's real, publicly reachable URL, not a placeholder, or every
# image this script builds will ship pointed at the wrong API. No safe
# default exists, so this is required, not optional.
: "${NEXT_PUBLIC_API_BASE_URL:?Set NEXT_PUBLIC_API_BASE_URL to the backend public URL (e.g. https://api.yourdomain.com) before running this script.}"

PUSH=1
if [[ "${1:-}" == "--no-push" ]]; then
  PUSH=0
fi

VERSION="$(git describe --tags --always --dirty 2>/dev/null || date +%Y%m%d%H%M%S)"

BACKEND_IMAGE="${REGISTRY}/careconnect-backend"
FRONTEND_IMAGE="${REGISTRY}/careconnect-frontend"

echo "==> Building ${BACKEND_IMAGE}:${VERSION} (and :latest)"
docker build \
  -t "${BACKEND_IMAGE}:${VERSION}" \
  -t "${BACKEND_IMAGE}:latest" \
  -f Dockerfile .

echo "==> Building ${FRONTEND_IMAGE}:${VERSION} (and :latest)"
docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL}" \
  -t "${FRONTEND_IMAGE}:${VERSION}" \
  -t "${FRONTEND_IMAGE}:latest" \
  -f frontend/Dockerfile frontend

echo
echo "==> Image sizes"
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" \
  | grep -E "REPOSITORY|careconnect-(backend|frontend)"

if [[ "$PUSH" -eq 0 ]]; then
  echo
  echo "==> --no-push given, skipping push. Built tags:"
  echo "    ${BACKEND_IMAGE}:${VERSION}  ${BACKEND_IMAGE}:latest"
  echo "    ${FRONTEND_IMAGE}:${VERSION}  ${FRONTEND_IMAGE}:latest"
  exit 0
fi

echo
echo "==> Pushing ${BACKEND_IMAGE} (${VERSION}, latest)"
docker push "${BACKEND_IMAGE}:${VERSION}"
docker push "${BACKEND_IMAGE}:latest"

echo "==> Pushing ${FRONTEND_IMAGE} (${VERSION}, latest)"
docker push "${FRONTEND_IMAGE}:${VERSION}"
docker push "${FRONTEND_IMAGE}:latest"

echo
echo "==> Done. On the VPS:"
echo "    IMAGE_TAG=${VERSION} docker compose -f docker-compose.prod.yml pull"
echo "    IMAGE_TAG=${VERSION} docker compose -f docker-compose.prod.yml up -d"
