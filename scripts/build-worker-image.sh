#!/usr/bin/env bash
# Build + optionally push the zer0one-cinema Blender worker image.
#
# Usage:
#     scripts/build-worker-image.sh                     # build local, tag :dev
#     scripts/build-worker-image.sh --push v0.1.1       # build + push to ghcr.io
#
# Env:
#     ZOCINEMA_VERSION   package version pinned into the image (default: read from pyproject.toml)
#     BLENDER_VERSION    Blender full version (default: 4.2.11)
#     BLENDER_MAJOR      Blender major series (default: 4.2)
#     IMAGE_REPO         image name w/o tag (default: ghcr.io/0xxcool/zer0one-cinema-worker)
#
# GHCR login (one-time): echo $GH_PAT | docker login ghcr.io -u <user> --password-stdin
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ZOCINEMA_VERSION="${ZOCINEMA_VERSION:-$(grep -m1 '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')}"
BLENDER_VERSION="${BLENDER_VERSION:-4.2.11}"
BLENDER_MAJOR="${BLENDER_MAJOR:-4.2}"
IMAGE_REPO="${IMAGE_REPO:-ghcr.io/0xxcool/zer0one-cinema-worker}"

PUSH=0
TAG="${1:-dev}"
if [[ "${1:-}" == "--push" ]]; then
  PUSH=1
  TAG="${2:?tag required with --push, e.g. v0.1.1}"
fi

FULL_TAG="${IMAGE_REPO}:${TAG}"

echo "==> Building $FULL_TAG"
echo "    ZOCINEMA_VERSION=$ZOCINEMA_VERSION"
echo "    BLENDER_VERSION=$BLENDER_VERSION"
docker build \
  --build-arg "ZOCINEMA_VERSION=${ZOCINEMA_VERSION}" \
  --build-arg "BLENDER_VERSION=${BLENDER_VERSION}" \
  --build-arg "BLENDER_MAJOR=${BLENDER_MAJOR}" \
  -t "${FULL_TAG}" \
  -f Dockerfile .

echo "==> Local smoke test: zocinema --version"
docker run --rm "${FULL_TAG}" zocinema --version

if [[ $PUSH -eq 1 ]]; then
  echo "==> Pushing $FULL_TAG"
  docker push "${FULL_TAG}"
  # Also tag as :latest when publishing a real version
  if [[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    docker tag "${FULL_TAG}" "${IMAGE_REPO}:latest"
    docker push "${IMAGE_REPO}:latest"
    echo "==> Also pushed :latest"
  fi
fi

echo "==> Done. $FULL_TAG ready."
